"""
Chat service — full pipeline:
  DB pipeline (Generate → Validate → Self-correct → Execute) runs in parallel
  with RAG retrieval (embed query → vector search).

Results are combined:
  both DB rows + RAG chunks  → combined prompt
  DB rows only               → DB prompt
  RAG chunks only            → RAG prompt
  DB flag + RAG chunks       → RAG prompt (question unrelated to DB but covered by docs)
  neither                    → appropriate message
"""

import asyncio
import json
from fastapi import HTTPException

from core.security import decrypt_value
import db.platform_db as pdb
from db.client_db import execute_query
from chat.prompt_builder import (
    build_schema_context,
    build_mysql_prompt,
    build_mongo_prompt,
    build_response_prompt,
    build_rag_response_prompt,
    build_combined_response_prompt,
)
from chat.sql_validator import validate_query
from chat.llm_client import generate_sql, generate_mongo_query, format_response
from rag.retrieval import retrieve_relevant_chunks

MAX_GENERATE_ATTEMPTS = 3
MAX_DB_RETRY_ATTEMPTS = 2

LLM_FLAGS = {"UNRELATED", "NO_ACCESS", "INCOMPLETE"}

FLAG_MESSAGES = {
    "UNRELATED":  "Your question doesn't seem related to the available data. Please ask something about your company's data.",
    "NO_ACCESS":  "You don't have access to the data required to answer this question.",
    "INCOMPLETE": "Your question is a bit vague. Could you provide more details?",
}


def _build_db_config(firm: dict) -> dict:
    db_type = firm["db_type"]
    if db_type == "mongodb":
        return {
            "mongo_uri": decrypt_value(firm["mongo_uri"]),
            "db_name":   firm["db_name"],
        }
    return {
        "host":     firm["db_host"],
        "port":     firm["db_port"],
        "db_name":  firm["db_name"],
        "user":     firm["db_user"],
        "password": decrypt_value(firm["db_password"]),
    }


def _clean_llm_output(raw: str) -> str:
    return (
        raw.strip()
        .strip("`")
        .replace("```sql", "")
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


async def _generate(db_type: str, prompt: str) -> str:
    if db_type == "mongodb":
        return await generate_mongo_query(prompt)
    return await generate_sql(prompt)


def _parse_query(db_type: str, raw: str):
    if db_type == "mongodb":
        return json.loads(raw)
    return raw


def _prepare_for_execution(db_type: str, parsed_query, schema: dict):
    if db_type != "mongodb":
        return parsed_query

    query = dict(parsed_query)
    collection_name = query.get("collection")
    matched = next(
        (t for t in schema["tables"] if t["name"] == collection_name), None
    )
    if matched:
        query["_schema_fields"] = matched.get("fields", [])
    return query


async def _run_db_pipeline(
    question: str,
    db_type: str,
    schema: dict,
    allowed_tables: list[str],
    db_config: dict,
    firm_id: str,
) -> dict:
    """
    Returns:
      {"flag": "UNRELATED"|"NO_ACCESS"|"INCOMPLETE", "attempts": N}
      {"rows": list[dict], "attempts": N}
    Raises HTTPException for fatal generation/execution failures.
    """
    schema_context = build_schema_context(schema, allowed_tables)

    previous_raw     = None
    validation_error = None
    db_error         = None
    total_attempts   = 0
    parsed_query     = None

    # ── Generate → Validate loop ──────────────────────────────────────────────
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        total_attempts = attempt

        if db_type == "mongodb":
            prompt = build_mongo_prompt(
                question, schema_context, allowed_tables,
                previous_query=previous_raw,
                validation_error=validation_error,
                db_error=db_error,
            )
        else:
            prompt = build_mysql_prompt(
                question, schema_context, allowed_tables,
                previous_sql=previous_raw,
                validation_error=validation_error,
                db_error=db_error,
            )

        raw_output   = _clean_llm_output(await _generate(db_type, prompt))
        previous_raw = raw_output

        first_word = raw_output.upper().split()[0] if raw_output else ""
        if first_word in LLM_FLAGS:
            return {"flag": first_word, "attempts": attempt}

        try:
            parsed_query = _parse_query(db_type, raw_output)
        except (ValueError, json.JSONDecodeError) as e:
            validation_error = f"Response was not valid JSON: {e}"
            db_error         = None
            continue

        is_valid, error_msg = validate_query(db_type, parsed_query, allowed_tables)
        if not is_valid:
            validation_error = error_msg
            db_error         = None
            continue

        validation_error = None
        break

    else:
        raise HTTPException(
            status_code=500,
            detail="Could not generate a valid query after multiple attempts. Try rephrasing.",
        )

    # ── Execute → DB-error retry loop ─────────────────────────────────────────
    results  = None
    db_error = None

    for db_attempt in range(1, MAX_DB_RETRY_ATTEMPTS + 1):
        try:
            query_to_run = _prepare_for_execution(db_type, parsed_query, schema)
            results      = await execute_query(firm_id, db_type, db_config, query_to_run)
            db_error     = None
            break

        except Exception as e:
            db_error = str(e)
            if db_attempt >= MAX_DB_RETRY_ATTEMPTS:
                break

            previous_raw = (
                json.dumps(parsed_query) if db_type == "mongodb" else parsed_query
            )
            if db_type == "mongodb":
                retry_prompt = build_mongo_prompt(
                    question, schema_context, allowed_tables,
                    previous_query=previous_raw, db_error=db_error,
                )
            else:
                retry_prompt = build_mysql_prompt(
                    question, schema_context, allowed_tables,
                    previous_sql=previous_raw, db_error=db_error,
                )

            raw_output = _clean_llm_output(await _generate(db_type, retry_prompt))
            total_attempts += 1

            try:
                parsed_query = _parse_query(db_type, raw_output)
            except Exception:
                break

            is_valid, _ = validate_query(db_type, parsed_query, allowed_tables)
            if not is_valid:
                break

    if db_error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {db_error}",
        )

    return {"rows": results or [], "attempts": total_attempts}


async def handle_chat(question: str, user_id: str, firm_id: str) -> dict:

    # ── 1. Load prerequisites ─────────────────────────────────────────────────
    user_role = await pdb.get_user_role(user_id)
    if not user_role:
        raise HTTPException(
            status_code=403,
            detail="No role assigned to your account. Contact your admin.",
        )

    firm = await pdb.get_firm(firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    db_type        = firm["db_type"]
    allowed_tables = user_role["allowed_tables"]
    db_config      = _build_db_config(firm)
    schema         = await pdb.get_schema(firm_id)

    # ── 2. Start RAG retrieval in background ──────────────────────────────────
    # Runs concurrently with the DB pipeline so latency stays low.
    rag_task = asyncio.create_task(retrieve_relevant_chunks(question, firm_id))

    # ── 3. DB pipeline (skipped if no schema configured) ─────────────────────
    db_result = None  # None means DB was not attempted

    if schema:
        tables = allowed_tables
        if tables == ["*"]:
            tables = [t["name"] for t in schema["tables"]]
        try:
            db_result = await _run_db_pipeline(
                question, db_type, schema, tables, db_config, firm_id
            )
        except HTTPException:
            rag_task.cancel()
            raise

    # ── 4. Collect RAG results ────────────────────────────────────────────────
    rag_chunks = await rag_task

    # ── 5. Route and build answer ─────────────────────────────────────────────
    has_db_rows = (
        db_result is not None
        and "rows" in db_result
        and len(db_result["rows"]) > 0
    )
    has_db_empty = (
        db_result is not None
        and "rows" in db_result
        and len(db_result["rows"]) == 0
    )
    has_db_flag = db_result is not None and "flag" in db_result
    has_rag     = bool(rag_chunks)

    attempts = (db_result or {}).get("attempts")

    if has_db_rows and has_rag:
        prompt = build_combined_response_prompt(question, db_result["rows"], rag_chunks)
        answer = await format_response(prompt)
        return {"answer": answer, "rows_count": len(db_result["rows"]), "attempts": attempts}

    if has_db_rows:
        answer = await format_response(build_response_prompt(question, db_result["rows"]))
        return {"answer": answer, "rows_count": len(db_result["rows"]), "attempts": attempts}

    if has_rag:
        # Covers: db flagged, db empty, or no schema — but docs are relevant
        answer = await format_response(build_rag_response_prompt(question, rag_chunks))
        return {"answer": answer, "rows_count": has_db_empty and 0 or None, "attempts": attempts}

    if has_db_flag:
        return {
            "answer":     FLAG_MESSAGES[db_result["flag"]],
            "rows_count": None,
            "attempts":   attempts,
        }

    if has_db_empty:
        return {"answer": "No data found for your query.", "rows_count": 0, "attempts": attempts}

    # No schema, no docs
    return {
        "answer":     "No relevant information found. Please contact your admin to configure your data sources.",
        "rows_count": None,
        "attempts":   None,
    }

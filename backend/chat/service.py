# DB pipeline : Generate -> Validate -> Self-correct -> Execute

import asyncio
import json
import re
from fastapi import HTTPException

_GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|good\s+(morning|afternoon|evening|night|day)"
    r"|howdy|greetings|what'?s\s+up|sup|hiya|namaste|yo)\W*$",
    re.IGNORECASE,
)

_CHART_RE = re.compile(
    r"\b(chart|graph|plot|visuali[sz]e?|pie(\s+chart)?|bar(\s+chart)?|"
    r"line(\s+chart)?|histogram|diagram|visuali[sz]ation)\b",
    re.IGNORECASE,
)

# Detects reference words that signal continuation from a previous query
_CONTINUATION_RE = re.compile(
    r"\b("
    r"this|these|that|those|"
    r"it|its|"
    r"them|they|their|"
    r"the\s+(above|previous|last|same|result|results|list|data|records?|ones?)|"
    r"above|"
    r"among\s*st?\s+them|"
    r"from\s+(them|those|that)|"
    r"of\s+(them|those)|"
    r"in\s+(them|those)|"
    r"which\s+of|who\s+among"
    r")\b",
    re.IGNORECASE,
)


def _build_history_chain(question: str, raw_history: list[dict]) -> list[dict]:
    """Walk backward through raw_history, collecting only the relevant continuation chain.

    Returns [] immediately if the current question has no reference words (fresh query).
    Stops walking as soon as it reaches a user message with no reference words — that
    message is the chain root and IS included.
    """
    if not raw_history or not _CONTINUATION_RE.search(question):
        return []

    chain: list[dict] = []
    i = len(raw_history) - 1

    # raw_history is ordered oldest→newest; each pair is [user, assistant]
    while i >= 1:
        asst = raw_history[i]
        user = raw_history[i - 1]

        # Skip misaligned entries (shouldn't happen but guard anyway)
        if user.get("role") != "user" or asst.get("role") != "assistant":
            i -= 1
            continue

        chain = [user, asst] + chain         # prepend to preserve order

        if _CONTINUATION_RE.search(user["content"]):
            i -= 2                           # this user msg was also a continuation — go further back
        else:
            break                            # fresh question found — this is the chain root, stop

    return chain

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
    build_chart_prompt,
    _human_access_note,
)
from chat.sql_validator import validate_query
from chat.llm_client import generate_sql, generate_mongo_query, format_response, generate_chart_data
from chat.row_filter_injector import inject_row_filters
from rag.retrieval import retrieve_relevant_chunks

MAX_GENERATE_ATTEMPTS = 3
MAX_DB_RETRY_ATTEMPTS = 2

LLM_FLAGS = {"UNRELATED", "NO_ACCESS", "INCOMPLETE"}

FLAG_MESSAGES = {
    "UNRELATED":  "No data found for your query.",
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
    row_filters: dict | None = None,
    history: list[dict] | None = None,
    wants_chart: bool = False,
) -> dict:
    """
    Returns:
      {"flag": "UNRELATED"|"NO_ACCESS"|"INCOMPLETE", "attempts": N}
      {"rows": list[dict], "attempts": N}
    Raises HTTPException for fatal generation/execution failures.
    """
    schema_context = build_schema_context(schema, allowed_tables)

    all_table_names = [t["name"] for t in schema.get("tables", [])]
    permitted_set   = set(allowed_tables)
    forbidden_tables = [t for t in all_table_names if t not in permitted_set]

    previous_raw     = None
    validation_error = None
    db_error         = None
    total_attempts   = 0
    parsed_query     = None

    # Generate -> Validate loop
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        total_attempts = attempt

        if db_type == "mongodb":
            prompt = build_mongo_prompt(
                question, schema_context, allowed_tables,
                forbidden_tables=forbidden_tables,
                previous_query=previous_raw,
                validation_error=validation_error,
                db_error=db_error,
                history=history,
                wants_chart=wants_chart,
                row_filters=row_filters,
            )
        else:
            prompt = build_mysql_prompt(
                question, schema_context, allowed_tables,
                forbidden_tables=forbidden_tables,
                previous_sql=previous_raw,
                validation_error=validation_error,
                db_error=db_error,
                history=history,
                wants_chart=wants_chart,
                row_filters=row_filters,
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

    # Safety-net: inject any row filters the LLM may have missed
    parsed_query, access_denied = inject_row_filters(db_type, parsed_query, row_filters)
    if access_denied:
        return {"flag": "NO_ACCESS", "attempts": total_attempts}

    # Execute -> DB-error retry loop
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
                    forbidden_tables=forbidden_tables,
                    previous_query=previous_raw, db_error=db_error,
                    row_filters=row_filters,
                )
            else:
                retry_prompt = build_mysql_prompt(
                    question, schema_context, allowed_tables,
                    forbidden_tables=forbidden_tables,
                    previous_sql=previous_raw, db_error=db_error,
                    row_filters=row_filters,
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


async def handle_chat(question: str, user_id: str, firm_id: str,
                      history: list[dict] | None = None) -> dict:

    # Short-circuit for greetings — no DB or RAG needed
    if _GREETING_RE.match(question.strip()):
        return {"answer": "Hello! How can I help you with your data today?",
                "rows_count": None, "attempts": None}

    # Load prerequisites
    user_role = await pdb.get_user_role(user_id)
    if not user_role:
        raise HTTPException(
            status_code=403,
            detail="No role assigned to your account. Contact your admin.",
        )

    firm = await pdb.get_firm(firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    db_type           = firm["db_type"]
    allowed_tables    = user_role["allowed_tables"]
    allowed_documents = user_role.get("allowed_documents", ["*"])
    row_filters       = user_role.get("row_filters") or {}
    schema            = await pdb.get_schema(firm_id)

    # Start RAG retrieval in background
    rag_task = asyncio.create_task(
        retrieve_relevant_chunks(question, firm_id, allowed_documents)
    )

    # DB pipeline (skipped if no schema)
    db_result = None  # None means DB was not attempted
    has_db    = db_type not in (None, "none")

    history_chain = _build_history_chain(question, history or [])
    wants_chart   = bool(_CHART_RE.search(question))

    if has_db and schema:
        db_config = _build_db_config(firm)
        tables    = allowed_tables
        if tables == ["*"]:
            tables = [t["name"] for t in schema["tables"]]
        try:
            db_result = await _run_db_pipeline(
                question, db_type, schema, tables, db_config, firm_id,
                row_filters=row_filters,
                history=history_chain,
                wants_chart=wants_chart,
            )
        except HTTPException:
            rag_task.cancel()
            raise

    # Collect RAG results and build answer
    rag_chunks = await rag_task

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
        text_prompt = build_combined_response_prompt(question, db_result["rows"], rag_chunks, row_filters=row_filters)
        if wants_chart:
            answer, chart_data = await asyncio.gather(
                format_response(text_prompt),
                generate_chart_data(build_chart_prompt(question, db_result["rows"])),
            )
        else:
            answer      = await format_response(text_prompt)
            chart_data  = None
        return {"answer": answer, "rows_count": len(db_result["rows"]), "attempts": attempts, "chart_data": chart_data}

    if has_db_rows:
        text_prompt = build_response_prompt(question, db_result["rows"], row_filters=row_filters)
        if wants_chart:
            answer, chart_data = await asyncio.gather(
                format_response(text_prompt),
                generate_chart_data(build_chart_prompt(question, db_result["rows"])),
            )
        else:
            answer      = await format_response(text_prompt)
            chart_data  = None
        return {"answer": answer, "rows_count": len(db_result["rows"]), "attempts": attempts, "chart_data": chart_data}

    if has_rag:
        answer = await format_response(build_rag_response_prompt(question, rag_chunks))
        return {"answer": answer, "rows_count": has_db_empty and 0 or None, "attempts": attempts, "chart_data": None}

    if has_db_flag:
        return {
            "answer":     FLAG_MESSAGES[db_result["flag"]],
            "rows_count": None,
            "attempts":   attempts,
            "chart_data": None,
        }

    if has_db_empty:
        if row_filters:
            note = _human_access_note(row_filters)
            answer = (
                f"No data found within your accessible data ({note})."
                if note else "No data found for your query."
            )
        else:
            answer = "No data found for your query."
        return {"answer": answer, "rows_count": 0, "attempts": attempts, "chart_data": None}

    return {
        "answer":     "No relevant information found. Please contact your admin to configure your data sources.",
        "rows_count": None,
        "attempts":   None,
        "chart_data": None,
    }

def build_schema_context(schema: dict, allowed_tables: list[str]) -> str:
    lines     = []
    permitted = set(allowed_tables) if allowed_tables != ["*"] else {t["name"] for t in schema.get("tables", [])}

    for table in schema.get("tables", []):
        if table["name"] not in permitted:
            continue
        desc = f" — {table['description']}" if table.get("description") else ""
        lines.append(f"Table/Collection: {table['name']}{desc}")
        for field in table.get("fields", []):
            fdesc = f" — {field['description']}" if field.get("description") else ""
            lines.append(f"  • {field['name']} ({field['type']}){fdesc}")
        lines.append("")

    if schema.get("relationships"):
        lines.append("Relationships:")
        for rel in schema["relationships"]:
            from_f = rel.get("from") or rel.get("from_field", "")
            to_f   = rel.get("to")   or rel.get("to_field", "")
            lines.append(f"  • {from_f} → {to_f} ({rel.get('type', 'FK')})")

    return "\n".join(lines).strip()


def build_mysql_prompt(question: str, schema_context: str,
                        allowed_tables: list[str],
                        previous_sql: str = None,
                        validation_error: str = None,
                        db_error: str = None) -> str:
    table_list = ", ".join(allowed_tables) if allowed_tables != ["*"] else "all tables in schema"

    correction = ""
    if previous_sql and (validation_error or db_error):
        correction = f"""
PREVIOUS ATTEMPT FAILED:
SQL tried:
{previous_sql}

Error:
{validation_error or db_error}

Fix the above error and generate a corrected query.
"""

    return f"""You are a MySQL SELECT query generator.

STRICT RULES:
1. Use ONLY tables and columns listed in the schema below. Never invent names.
2. Only these tables are permitted for this user: {table_list}
3. Generate ONLY a SELECT statement. Never use INSERT, UPDATE, DELETE, DROP,
   ALTER, TRUNCATE, CREATE, GRANT, REVOKE, or any write operation.
4. Return ONLY the raw SQL — no explanation, no markdown, no backticks, no semicolon.
5. If the question is unrelated to the database, reply exactly: UNRELATED
6. If the question requires a table not in the permitted list, reply exactly: NO_ACCESS
7. If the question is too vague, reply exactly: INCOMPLETE
{correction}
SCHEMA:
{schema_context}

USER QUESTION: {question}"""


def build_mongo_prompt(question: str, schema_context: str,
                        allowed_collections: list[str],
                        previous_query: str = None,
                        validation_error: str = None,
                        db_error: str = None) -> str:
    coll_list = ", ".join(allowed_collections) if allowed_collections != ["*"] else "all collections in schema"

    correction = ""
    if previous_query and (validation_error or db_error):
        correction = f"""
PREVIOUS ATTEMPT FAILED:
Query tried:
{previous_query}

Error:
{validation_error or db_error}

Fix the above error and return a corrected query.
"""

    return f"""You are a MongoDB query generator.

STRICT RULES: l
1. Use ONLY collections and fields listed in the schema below.
2. Only these collections are permitted: {coll_list}
3. If the data requested belongs to a collection not permitted, reply exactly: NO_ACCESS.
4. For a query to count_documents belonging to a collection that is not permitted, reply exactly: NO_ACCESS.
5. If data requested is not in database or is unrelated to it, reply exactly: UNRELATED.
6. For a query to count_documents not present in any collection in the database or unrelated to it, reply exactly: UNRELATED.
7. If query asked is too vague, reply exactly: INCOMPLETE
8. Return a JSON object with this exact structure:
   {{
     "collection": "<name>",
     "operation":  "find" | "aggregate" | "count_documents",
     "filter":     {{ ... }},
     "pipeline":   [ ... ],
     "limit":      <number>
   }}
9. "limit" MUST be between 100 and 500. Never set it to 0. Default to 100 if unsure.
10. For string field filters, use case-insensitive regex instead of exact match:
   WRONG: {{"source.city": "delhi"}}
   RIGHT: {{"source.city": {{"$regex": "^delhi$", "$options": "i"}}}}
   Exception: enum/status fields must be exact uppercase e.g. {{"status": "SCHEDULED"}}
11. NEVER use $out or $merge in pipelines — they write to the DB.
12. NEVER include write operations (insertOne, updateOne, deleteOne, drop, etc.).
13. Return ONLY the raw JSON — no explanation, no markdown, no backticks.

{correction}
SCHEMA:
{schema_context}

USER QUESTION: {question}"""


def build_response_prompt(question: str, results: list[dict]) -> str:
    sample    = results[:50]
    rows_text = "\n".join(str(r) for r in sample)
    note      = f"\n(Showing {len(sample)} of {len(results)} total rows)" if len(results) > 50 else ""

    return f"""You are a helpful data assistant. Format the query results as a clear, natural language answer.

USER QUESTION: {question}

QUERY RESULTS{note}:
{rows_text}

Instructions:
- For a single value or count, answer in one sentence.
- For multiple items or fields, use a numbered list or bullet points — one item per line.
- Group related information with a short heading if it helps clarity.
- Never put multiple data points in a single paragraph.
- Do not mention SQL, MongoDB, databases, or queries.
- Do not repeat the question."""


_DOC_CHUNK_TEMPLATE = "[Source: {source}, Page {page}]\n{text}"


def build_rag_response_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = [
        _DOC_CHUNK_TEMPLATE.format(
            source=c["source"], page=c["page"], text=c["text"]
        )
        for c in chunks
    ]
    context = "\n\n---\n\n".join(context_parts)

    return f"""You are a helpful assistant that answers questions using the provided document context.

Rules:
- Answer only from the context below — do not add outside knowledge.
- Present only what the context covers; do not mention gaps or missing information.
- Use bullet points or numbered lists for multiple items — one point per line.
- Use short headings to group distinct topics if the answer covers more than one area.
- Never put multiple data points in a single paragraph.
- Cite the source document and page number when referencing specific facts.

CONTEXT:
{context}

USER QUESTION: {question}"""


def build_combined_response_prompt(
    question: str,
    db_rows: list[dict],
    rag_chunks: list[dict],
) -> str:
    sample    = db_rows[:50]
    rows_text = "\n".join(str(r) for r in sample)
    db_note   = f"\n(Showing {len(sample)} of {len(db_rows)} total rows)" if len(db_rows) > 50 else ""

    context_parts = [
        _DOC_CHUNK_TEMPLATE.format(
            source=c["source"], page=c["page"], text=c["text"]
        )
        for c in rag_chunks
    ]
    doc_context = "\n\n---\n\n".join(context_parts)

    return f"""You are a helpful data assistant with access to both structured database records and document context.
Combine both sources to give a complete, clear answer.

USER QUESTION: {question}

DATABASE RESULTS{db_note}:
{rows_text}

DOCUMENT CONTEXT:
{doc_context}

Instructions:
- Use whichever sources have relevant information — do not mention that a source has no data.
- Use bullet points or numbered lists for multiple items — one item per line.
- Use short headings to separate distinct topics if the answer spans multiple areas.
- Never put multiple data points in a single paragraph.
- Cite document source and page number when referencing document content.
- Do not mention SQL, MongoDB, or internal query details.
- Do not repeat the question."""

import json as _json
import datetime as _dt


def build_chart_prompt(question: str, rows: list[dict]) -> str:
    rows_json = _json.dumps(rows, default=str)
    return f"""You are a data visualization expert. Given a user question and its query results, decide if a chart would add value.

Return a JSON object if a chart is useful, or exactly: null

Use these chart types:
- "bar"  — categorical comparison (counts per group, value per category). Good for 2-15 categories.
- "line" — time-series or sequential data (values changing over time/order).
- "pie"  — proportional breakdown (percentages, distributions). Good for 2-8 slices.

Return null when:
- The result is a single count or value
- A plain list of names/IDs with no numeric dimension
- Raw individual records not aggregated (e.g. a list of calls with caller name, duration — not counts)
- Fewer than 2 data points
- The data is already fully described by the text and a chart adds no insight

JSON structure for bar / line charts:
{{"type":"bar" or "line","title":"Short descriptive title (max 50 chars)","x_key":"string_field_name","y_key":"numeric_field_name","data":[...all rows...]}}

JSON structure for pie charts:
{{"type":"pie","title":"Short descriptive title (max 50 chars)","name_key":"string_field_name","value_key":"numeric_field_name","data":[...all rows...]}}

For line charts with multiple numeric series:
{{"type":"line","title":"...","x_key":"...","lines":[{{"key":"col1","label":"Label 1"}},{{"key":"col2","label":"Label 2"}}],"data":[...]}}

Rules:
- x_key / name_key must map to a string or date field in the data
- y_key / value_key must map to a numeric field in the data
- Use all rows provided in the data array — do not truncate
- Return ONLY the JSON or the word null — no explanation, no markdown

Question: {question}
Rows: {rows_json}"""


def _history_block(history: list[dict]) -> str:
    """Format a filtered history chain for injection into query-generation prompts."""
    if not history:
        return ""
    lines = []
    for msg in history:
        label = "User" if msg.get("role") == "user" else "Assistant"
        lines.append(f"{label}: {msg.get('content', '')}")
    return (
        "CONVERSATION HISTORY — the current question is a follow-up to this exchange.\n"
        "- Resolve all pronouns (\"them\", \"those\", \"it\", \"that\", \"amongst them\") from this context.\n"
        "- CRITICAL: carry forward ALL implicit filters from the previous question into your new query. "
        "If the previous question asked about a specific tenant, status, entity, or date range, "
        "include that exact same filter even if the current question does not restate it.\n"
        + "\n".join(lines)
        + "\n\n"
    )


def _row_filter_query_block(row_filters: dict | None) -> str:
    """Build a query-generation prompt section describing row-level access restrictions."""
    if not row_filters:
        return ""

    _OP_H = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=", "$ne": "!="}
    lines = [
        "ROW-LEVEL ACCESS — this user's data is strictly limited to specific values.",
        "CRITICAL: If the user asks for, mentions, or targets a value NOT in the permitted set → reply exactly: NO_ACCESS",
        "Do NOT generate a query that returns 0 results due to an access violation — return NO_ACCESS instead.",
    ]

    for table, filters in row_filters.items():
        for col, rule in filters.items():
            if isinstance(rule, list):
                vals = ", ".join(f'"{v}"' for v in rule)
                lines.append(f'  Table/Collection "{table}", field "{col}": ONLY [{vals}] are permitted.')
                lines.append(f'    - User names a value NOT in this list → NO_ACCESS (do not generate a query)')
                lines.append(f'    - User names exactly one permitted value → filter to ONLY that value, not the full list')
                lines.append(f'    - User asks generally (no specific value stated) → do NOT add this filter; it is injected automatically')
            elif isinstance(rule, dict):
                parts = [f'"{col}" {_OP_H.get(op, op)} {val}' for op, val in rule.items()]
                lines.append(f'  Table/Collection "{table}": {" AND ".join(parts)} is enforced automatically — omit it from your query.')

    lines.append("")
    return "\n".join(lines) + "\n"


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
            extras = []
            if field.get("example_values"):
                ex = ", ".join(str(v) for v in field["example_values"][:6])
                extras.append(f"e.g. {ex}")
            if field.get("synonyms"):
                extras.append("synonyms: " + "; ".join(field["synonyms"]))
            extra_str = f" ({', '.join(extras)})" if extras else ""
            lines.append(f"  • {field['name']} ({field['type']}){fdesc}{extra_str}")
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
                        forbidden_tables: list[str] | None = None,
                        previous_sql: str = None,
                        validation_error: str = None,
                        db_error: str = None,
                        history: list[dict] | None = None,
                        wants_chart: bool = False,
                        row_filters: dict | None = None) -> str:
    table_list = ", ".join(allowed_tables) if allowed_tables != ["*"] else "all tables in schema"

    forbidden_section = ""
    if forbidden_tables:
        names = ", ".join(forbidden_tables)
        forbidden_section = (
            f"\nFORBIDDEN TABLES — these exist in the database but this user cannot access them: {names}\n"
            "   If the question is about any forbidden table, reply exactly: NO_ACCESS\n"
        )

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

    chart_note = (
        "\nCHART REQUEST: The user wants a chart. If the question involves multiple categories "
        "(e.g. recorded vs not, by status, by month), generate a GROUP BY query that returns "
        "one row per category with a count — NEVER a single COUNT(*).\n"
        if wants_chart else ""
    )

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
{forbidden_section}
Null / empty / missing values:
- "not recorded" / "not captured" / "missing" / "blank" / "no <field>" /
  "<field> not recorded" / "<field> was not captured" →
  field IS NULL OR field = ''
- "has <field>" / "<field> is recorded" / "<field> exists" / "<field> available" /
  "was a <field> recorded" / "<field> was captured" / "had a <field>" →
  field IS NOT NULL AND field <> ''

Comparison / percentage / breakdown ("X vs Y", "recorded vs not", "percentage of",
"what percentage", "how many … and how many … not"):
- Return ONE ROW PER CATEGORY, not a single aggregate count. Use GROUP BY with CASE WHEN:
  SELECT CASE WHEN field IS NULL OR field = '' THEN 'Not Recorded' ELSE 'Recorded' END AS status,
         COUNT(*) AS count
  FROM table GROUP BY status
- NEVER write a plain COUNT(*) for a "vs" or percentage question — it gives only one number.

Call records:
- "calls recorded" / "recorded calls" / "calls made" / "calls logged" →
  means ALL entries in the table — do NOT add a filter on any recording-related column
  unless the question specifically asks about call recordings or transcripts.

SEMANTIC HINTS — translate these terms to correct SQL:

Ranking / ordering:
- "top N" / "best N"     → ORDER BY <relevant column> DESC LIMIT N
- "bottom N" / "worst N" → ORDER BY <relevant column> ASC LIMIT N
- "recent" / "latest"    → ORDER BY <date or created_at column> DESC

Status terms (use whichever column and value pattern the schema shows):
- "active"               → status = 'ACTIVE' or is_active = 1
- "inactive"             → status = 'INACTIVE' or is_active = 0
- "pending"              → status = 'PENDING'
- "completed" / "done"   → status = 'COMPLETED' or status = 'DONE'
- "cancelled"            → status = 'CANCELLED'
- "yes" / "no" (boolean) → 1 / 0 or TRUE / FALSE depending on column type

Date / time periods — apply to whichever date or timestamp column fits the question:
- "in <year>" / "during <year>"         → YEAR(<date col>) = <year>
  e.g. "in 2026", "calls made in 2025"  → YEAR(created_at) = 2026
- "this year"                           → YEAR(<date col>) = YEAR(CURDATE())
- "last year"                           → YEAR(<date col>) = YEAR(CURDATE()) - 1
- "this month"                          → MONTH(<date col>) = MONTH(CURDATE()) AND YEAR(<date col>) = YEAR(CURDATE())
- "last month"                          → <date col> >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01') AND <date col> < DATE_FORMAT(CURDATE(), '%Y-%m-01')
- "between <date1> and <date2>"         → <date col> BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
- Q1                                    → MONTH(<date col>) BETWEEN 1 AND 3
- Q2                                    → MONTH(<date col>) BETWEEN 4 AND 6
- Q3                                    → MONTH(<date col>) BETWEEN 7 AND 9
- Q4                                    → MONTH(<date col>) BETWEEN 10 AND 12

Use actual column names from the schema — the hints above are patterns, not literal column names.
{chart_note}{_row_filter_query_block(row_filters)}{correction}
SCHEMA:
{schema_context}

{_history_block(history or [])}USER QUESTION: {question}"""


def build_mongo_prompt(question: str, schema_context: str,
                        allowed_collections: list[str],
                        forbidden_tables: list[str] | None = None,
                        previous_query: str = None,
                        validation_error: str = None,
                        db_error: str = None,
                        history: list[dict] | None = None,
                        wants_chart: bool = False,
                        row_filters: dict | None = None) -> str:
    _today      = _dt.date.today()
    _cur_year   = _today.year
    _prev_year  = _cur_year - 1
    _next_year  = _cur_year + 1
    coll_list = ", ".join(allowed_collections) if allowed_collections != ["*"] else "all collections in schema"

    forbidden_section = ""
    if forbidden_tables:
        names = ", ".join(forbidden_tables)
        forbidden_section = (
            f"\nFORBIDDEN COLLECTIONS — these exist in the database but this user cannot access them: {names}\n"
            "   If the question is about any forbidden collection, reply exactly: NO_ACCESS\n"
        )

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

    chart_note = (
        "\nCHART REQUEST: The user wants a chart. If the question involves multiple categories "
        "(e.g. recorded vs not, by status, by month), use aggregate with $group to return "
        "one document per category with a count field — NEVER use count_documents.\n"
        if wants_chart else ""
    )

    return f"""You are a MongoDB query generator.

STRICT RULES:
1. Use ONLY collections and fields listed in the schema below.
2. Only these collections are permitted: {coll_list}
3. If the data requested belongs to a collection not permitted, reply exactly: NO_ACCESS.
4. For a query to count_documents belonging to a collection that is not permitted, reply exactly: NO_ACCESS.
{forbidden_section}
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
   Exception: DO NOT use regex for null checks — use bare null instead (see hint below).
11. NEVER use $out or $merge in pipelines — they write to the DB.
12. NEVER include write operations (insertOne, updateOne, deleteOne, drop, etc.).
13. Return ONLY the raw JSON — no explanation, no markdown, no backticks.

SEMANTIC HINTS:

Null / empty / missing field values:
- "not recorded" / "not captured" / "missing" / "blank" / "empty" / "no <field>" /
  "<field> not recorded" / "<field> was not captured" →
  use {{field: null}}  — this matches documents where the field is null OR absent.
  NEVER use a string literal like "not recorded" for these.
- "has <field>" / "<field> is recorded" / "<field> exists" / "<field> available" /
  "was a <field> recorded" / "<field> was captured" / "had a <field>" →
  use {{field: {{$ne: null}}}}

Comparison / percentage / breakdown queries ("X vs Y", "recorded vs not", "percentage of"):
- These need TWO groups in the result, not one count. Use aggregate with $group:
  {{"collection":"...","operation":"aggregate","pipeline":[
    {{"$group":{{"_id":{{"$cond":[{{"$eq":["$field",null]}},"Not Recorded","Recorded"]}},"count":{{"$sum":1}}}}}},
    {{"$project":{{"status":"$_id","count":1,"_id":0}}}}
  ],"limit":100}}
- NEVER use count_documents for a "vs" or percentage query — it returns only one number.

Date comparisons — date strings are auto-converted to Date objects; always use ISO 8601:
- "in <year>" e.g. "in 2026" / "calls made in 2025"
    → {{field: {{$gte: "YYYY-01-01T00:00:00Z", $lt: "YYYY+1-01-01T00:00:00Z"}}}}
    e.g. "in 2026" → {{field: {{$gte: "2026-01-01T00:00:00Z", $lt: "2027-01-01T00:00:00Z"}}}}
- "this year" (current year = {_cur_year})
    → {{field: {{$gte: "{_cur_year}-01-01T00:00:00Z", $lt: "{_next_year}-01-01T00:00:00Z"}}}}
- "last year" (previous year = {_prev_year})
    → {{field: {{$gte: "{_prev_year}-01-01T00:00:00Z", $lt: "{_cur_year}-01-01T00:00:00Z"}}}}
- "in <month> <year>" / "during <month> <year>"
    → {{field: {{$gte: "YYYY-MM-01T00:00:00Z", $lt: "YYYY-MM+1-01T00:00:00Z"}}}}
- "after <date>" / "since <date>"   → {{field: {{$gt: "YYYY-MM-DDT00:00:00Z"}}}}
- "before <date>" / "until <date>"  → {{field: {{$lt: "YYYY-MM-DDT00:00:00Z"}}}}
- "between <d1> and <d2>"           → {{field: {{$gte: "...", $lte: "..."}}}}
- Q1 (Jan–Mar) / Q2 (Apr–Jun) / Q3 (Jul–Sep) / Q4 (Oct–Dec)
    → use $gte start-of-quarter and $lt start-of-next-quarter for the relevant year
- Always use ISO 8601 format "YYYY-MM-DDTHH:MM:SSZ" — never use plain year integers.

{chart_note}{_row_filter_query_block(row_filters)}{correction}
SCHEMA:
{schema_context}

{_history_block(history or [])}USER QUESTION: {question}"""


_OP_HUMAN = {
    "$gt": ">", "$gte": "≥", "$lt": "<", "$lte": "≤",
    "$ne": "≠", "$eq": "=", "$in": "in", "$nin": "not in",
}


def _rule_to_hashable(rule) -> tuple:
    if isinstance(rule, list):
        return ("in", tuple(str(v) for v in rule))
    if isinstance(rule, dict):
        return ("op", tuple(sorted((op, str(v)) for op, v in rule.items())))
    return ("eq", str(rule))


def _rule_to_text(col: str, rule) -> str:
    if isinstance(rule, list):
        vals = [str(v) for v in rule]
        if len(vals) == 1:
            return f"{col} {vals[0]}"
        if len(vals) == 2:
            return f"{col} as {vals[0]} and {vals[1]}"
        return f"{col} as {', '.join(vals[:-1])} and {vals[-1]}"
    if isinstance(rule, dict):
        parts = []
        for op, v in rule.items():
            human_op = _OP_HUMAN.get(op, op)
            parts.append(f"{col} {human_op} {v}" if not isinstance(v, list)
                         else f"{col} {human_op} ({', '.join(str(x) for x in v)})")
        return " and ".join(parts)
    return f"{col} = {rule}"


def _human_access_note(row_filters: dict | None) -> str:
    """Return a friendly English description of row-level access restrictions.

    Handles both equality lists and operator dicts.
    Example outputs:
      "call_history and batch_uploads for tenant_id as Yulu and DrBatra"
      "employees for salary > 10000"
    """
    if not row_filters:
        return ""

    # Group tables that share identical filter conditions
    groups: dict[tuple, tuple[list[str], dict]] = {}
    for table, filters in row_filters.items():
        key = tuple(sorted((col, _rule_to_hashable(rule)) for col, rule in filters.items()))
        if key not in groups:
            groups[key] = ([], filters)
        groups[key][0].append(table)

    parts = []
    for _, (tables, filters) in groups.items():
        if len(tables) == 1:
            tbl = tables[0]
        elif len(tables) == 2:
            tbl = f"{tables[0]} and {tables[1]}"
        else:
            tbl = ", ".join(tables[:-1]) + f" and {tables[-1]}"

        cond_parts = [_rule_to_text(col, rule) for col, rule in filters.items()]
        parts.append(f"{tbl} for {' and '.join(cond_parts)}")

    return "; ".join(parts)


def build_response_prompt(question: str, results: list[dict], row_filters: dict | None = None) -> str:
    sample    = results[:50]
    rows_text = "\n".join(str(r) for r in sample)
    note      = f"\n(Showing {len(sample)} of {len(results)} total rows)" if len(results) > 50 else ""

    note_str = _human_access_note(row_filters)
    if note_str:
        access_block = f"""

ACCESS CONTEXT — this user can only see restricted data: {note_str}
Apply this logic when phrasing your response:
- If the USER QUESTION asks for "all records" or is general (no specific entity/tenant/value mentioned) → start your answer with: "As you only have access to {note_str}, here are the results:" then continue.
- If the USER QUESTION asks for a total, count, sum, or aggregate → give the result, then add: "Note: this figure only covers the data you have access to ({note_str})."
- If the USER QUESTION asks for something specific that IS within the user's access → answer directly, do not mention access restrictions at all.
- If the QUERY RESULTS are empty and the question targets something outside the user's access → respond: "You don't have access to [what they asked for]. You can only access {note_str}."
"""
    else:
        access_block = ""

    return f"""You are a friendly data assistant. Answer the user's question using the query results below.

USER QUESTION: {question}

QUERY RESULTS{note}:
{rows_text}

Instructions:
- Answer only what was asked. If the user asks for a list of names, show names only. If they ask for details, show all relevant fields. Do not include extra data that was not requested.
- For a single value or count, answer in one sentence.
- For multiple items, use a clean numbered or bulleted list — one item per line.
- Use friendly, natural language. Avoid robotic or overly technical phrasing.
- Do not mention SQL, databases, or query details.
- Do not add any notes about charts, visualizations, or graphing tools.
- Do not repeat the question.{access_block}"""


_DOC_CHUNK_TEMPLATE = "[Source: {source}, Page {page}]\n{text}"


def build_rag_response_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = [
        _DOC_CHUNK_TEMPLATE.format(
            source=c["source"], page=c["page"], text=c["text"]
        )
        for c in chunks
    ]
    context = "\n\n---\n\n".join(context_parts)

    return f"""You are a friendly assistant that answers questions using the provided document context.

Rules:
- Answer only what was asked, using only the context below — do not add outside knowledge.
- Use friendly, natural language. Avoid robotic or overly formal phrasing.
- Use bullet points or numbered lists for multiple items — one point per line.
- Use short headings to group distinct topics if the answer covers more than one area.
- Cite the source document and page number when referencing specific facts.
- Do not repeat the question.

CONTEXT:
{context}

USER QUESTION: {question}"""


def build_combined_response_prompt(
    question: str,
    db_rows: list[dict],
    rag_chunks: list[dict],
    row_filters: dict | None = None,
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

    note_str = _human_access_note(row_filters)
    if note_str:
        access_block = f"""

ACCESS CONTEXT — this user can only see restricted data: {note_str}
Apply this logic when phrasing your response:
- If the USER QUESTION asks for "all records" or is general (no specific entity/tenant/value mentioned) → start your answer with: "As you only have access to {note_str}, here are the results:" then continue.
- If the USER QUESTION asks for a total, count, sum, or aggregate → give the result, then add: "Note: this figure only covers the data you have access to ({note_str})."
- If the USER QUESTION asks for something specific that IS within the user's access → answer directly, do not mention access restrictions at all.
- If the DATABASE RESULTS are empty and the question targets something outside the user's access → respond: "You don't have access to [what they asked for]. You can only access {note_str}."
"""
    else:
        access_block = ""

    return f"""You are a friendly data assistant with access to both structured database records and document context.
Combine both sources to give a complete, clear answer.

USER QUESTION: {question}

DATABASE RESULTS{db_note}:
{rows_text}

DOCUMENT CONTEXT:
{doc_context}

Instructions:
- Answer only what was asked — show names only for list requests, full details only when details are asked for.
- Use whichever sources have relevant information — do not mention that a source has no data.
- Use bullet points or numbered lists for multiple items — one item per line.
- Use friendly, natural language. Avoid robotic or technical phrasing.
- Cite document source and page number when referencing document content.
- Do not mention SQL, MongoDB, or internal query details.
- Do not repeat the question.{access_block}"""

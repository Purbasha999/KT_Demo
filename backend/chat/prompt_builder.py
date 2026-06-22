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
                        db_error: str = None) -> str:
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
- "not recorded" / "not captured" / "missing" / "blank" / "no <field>" → field IS NULL OR field = ''
- "has <field>" / "<field> is recorded" / "<field> exists"             → field IS NOT NULL AND field <> ''

Call records:
- "calls recorded" / "recorded calls" / "calls made" / "calls logged" →
  means ALL entries in the table — do NOT add a filter on any recording-related column
  unless the question specifically asks about call recordings or transcripts.

SEMANTIC HINTS — translate these terms to correct SQL:

Ranking / ordering:
- "top N" / "best N"      → ORDER BY <relevant column> DESC LIMIT N
- "bottom N" / "worst N"  → ORDER BY <relevant column> ASC LIMIT N
- "recent" / "latest"     → ORDER BY <date or created_at column> DESC

Status terms:
- "active"                → status = 'ACTIVE' or is_active = 1 (use whichever column exists)
- "inactive" / "churned"  → status = 'INACTIVE' or is_active = 0
- "pending"               → status = 'PENDING'
- "completed" / "done"    → status = 'COMPLETED' or status = 'DONE'
- "cancelled"             → status = 'CANCELLED'
- "struck off"            → status = 'STRUCK_OFF' or status = 'STRUCK OFF' (dissolved Indian company)
- "dormant"               → status = 'DORMANT'
- "yes" / "no" (boolean)  → 1 / 0 or TRUE / FALSE depending on column type

Calendar time periods:
- "this year"             → YEAR(<date column>) = YEAR(CURDATE())
- "last year"             → YEAR(<date column>) = YEAR(CURDATE()) - 1
- "this month"            → MONTH(<date column>) = MONTH(CURDATE()) AND YEAR(<date column>) = YEAR(CURDATE())
- "last month"            → <date column> >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01') AND <date column> < DATE_FORMAT(CURDATE(), '%Y-%m-01')
- Q1 (calendar)           → MONTH(<date column>) BETWEEN 1 AND 3
- Q2 (calendar)           → MONTH(<date column>) BETWEEN 4 AND 6
- Q3 (calendar)           → MONTH(<date column>) BETWEEN 7 AND 9
- Q4 (calendar)           → MONTH(<date column>) BETWEEN 10 AND 12

Indian fiscal year (April–March):
- "this FY" / "current financial year"  → <date column> BETWEEN DATE(CONCAT(IF(MONTH(CURDATE())>=4, YEAR(CURDATE()), YEAR(CURDATE())-1), '-04-01')) AND DATE(CONCAT(IF(MONTH(CURDATE())>=4, YEAR(CURDATE())+1, YEAR(CURDATE())), '-03-31'))
- "last FY" / "previous financial year" → use the FY one year before the current FY window above
- FY Q1 / "April to June"               → MONTH(<date column>) BETWEEN 4 AND 6
- FY Q2 / "July to September"           → MONTH(<date column>) BETWEEN 7 AND 9
- FY Q3 / "October to December"         → MONTH(<date column>) BETWEEN 10 AND 12
- FY Q4 / "January to March"            → MONTH(<date column>) BETWEEN 1 AND 3

Indian geography — translate region names to state IN (...) lists. Use both full names and 2-letter codes if unsure which the column stores:
- "north India"     → state IN ('Delhi','Uttar Pradesh','Haryana','Punjab','Rajasthan','Himachal Pradesh','Uttarakhand','Jammu and Kashmir','Ladakh','DL','UP','HR','PB','RJ','HP','UK','JK')
- "south India"     → state IN ('Tamil Nadu','Karnataka','Kerala','Andhra Pradesh','Telangana','TN','KA','KL','AP','TS')
- "west India"      → state IN ('Maharashtra','Gujarat','Goa','Rajasthan','MH','GJ','GA','RJ')
- "east India"      → state IN ('West Bengal','Bihar','Jharkhand','Odisha','WB','BR','JH','OR','OD')
- "northeast India" / "north east" → state IN ('Assam','Meghalaya','Manipur','Nagaland','Mizoram','Tripura','Arunachal Pradesh','Sikkim','AS','ML','MN','NL','MZ','TR','AR','SK')
- "central India"   → state IN ('Madhya Pradesh','Chhattisgarh','MP','CG')
- "metros" / "metro cities" → city IN ('Mumbai','Delhi','Bangalore','Bengaluru','Hyderabad','Chennai','Kolkata','Pune','Ahmedabad')
- "tier 1 cities"   → city IN ('Mumbai','Delhi','Bangalore','Bengaluru','Hyderabad','Chennai','Kolkata','Pune','Ahmedabad')
- "tier 2 cities"   → city IN ('Jaipur','Lucknow','Surat','Bhopal','Nagpur','Indore','Coimbatore','Kochi','Chandigarh','Visakhapatnam','Patna','Vadodara','Ludhiana','Agra','Nashik')

US geography (if applicable):
- "west coast"            → state IN ('CA','OR','WA') or ('California','Oregon','Washington')
- "east coast"            → state IN ('NY','MA','CT','RI','NJ','DE','MD','VA','NC','SC','GA','FL')
- "midwest"               → state IN ('IL','OH','MI','IN','WI','MN','IA','MO','ND','SD','NE','KS')
- "south" / "southeast"   → state IN ('TX','LA','AR','MS','AL','TN','KY','FL','GA','SC','NC','VA')

Indian company types (translate to the column value pattern that fits):
- "private limited" / "pvt ltd"  → company_type LIKE '%PRIVATE%' or type = 'PVT LTD'
- "public limited"               → company_type LIKE '%PUBLIC%'
- "LLP"                          → company_type LIKE '%LLP%' or type = 'LLP'
- "OPC" / "one person company"   → company_type LIKE '%OPC%' or type = 'OPC'
- "listed companies"             → listed = 1 or listed = 'YES' or exchange IN ('BSE','NSE')
- "unlisted"                     → listed = 0 or listed = 'NO'
- "startup" / "startups"         → company_type LIKE '%STARTUP%' or category = 'STARTUP'
- "MSME" / "small business"      → category = 'MSME' or size = 'SMALL'

Indian business identifiers (use exact match — these are structured codes):
- PAN     → pan_number or pan (10-char alphanumeric, e.g. AAAPL1234C)
- GSTIN   → gstin or gst_number (15-char, e.g. 27AAAPL1234C1Z5)
- CIN     → cin (21-char company ID, e.g. U72200MH2010PTC123456)
- TAN     → tan_number (10-char, e.g. MUMC12345A)

Use actual column names from the schema — the hints above are patterns, not literal column names.
{correction}
SCHEMA:
{schema_context}

USER QUESTION: {question}"""


def build_mongo_prompt(question: str, schema_context: str,
                        allowed_collections: list[str],
                        forbidden_tables: list[str] | None = None,
                        previous_query: str = None,
                        validation_error: str = None,
                        db_error: str = None) -> str:
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
- "not recorded" / "not captured" / "missing" / "blank" / "empty" / "no <field>" →
  use {{field: null}}  — this matches documents where the field is null OR absent.
  NEVER use a string literal like "not recorded" for these — it will only match documents
  that literally contain that string as the value.
- "has <field>" / "<field> is recorded" / "<field> exists" / "<field> available" →
  use {{field: {{$ne: null}}}}

Call records / call history:
- "calls recorded" / "recorded calls" / "calls made" / "calls logged" →
  means ALL entries in the collection — do NOT add any filter on recording fields,
  recording URLs, or recording status. Query all documents (or filter only by the
  fields the user explicitly mentions).

Date comparisons:
- "after <date>" / "since <date>" / "from <date>"  → {{field: {{$gt: "YYYY-MM-DDT00:00:00Z"}}}}
- "before <date>" / "until <date>" / "up to <date>" → {{field: {{$lt: "YYYY-MM-DDT00:00:00Z"}}}}
- "in <month> <year>" / "during <month>"            → combine $gte and $lt for the month range
- Always use ISO 8601 format: "YYYY-MM-DDTHH:MM:SSZ" for date values in filters.

{correction}
SCHEMA:
{schema_context}

USER QUESTION: {question}"""


def _human_access_note(row_filters: dict | None) -> str:
    """Return a friendly English description of row-level access restrictions.

    Example output: "call_history and batch_uploads for tenant_id as Yulu and DrBatra"
    """
    if not row_filters:
        return ""

    # Group tables that share identical filter conditions so we can say
    # "call_history and batch_uploads for ..." instead of repeating the condition.
    groups: dict[tuple, list[str]] = {}
    for table, filters in row_filters.items():
        key = tuple(sorted((col, tuple(str(v) for v in vals)) for col, vals in filters.items()))
        groups.setdefault(key, []).append(table)

    parts = []
    for condition_key, tables in groups.items():
        if len(tables) == 1:
            tbl = tables[0]
        elif len(tables) == 2:
            tbl = f"{tables[0]} and {tables[1]}"
        else:
            tbl = ", ".join(tables[:-1]) + f" and {tables[-1]}"

        cond_parts = []
        for col, vals in condition_key:
            if len(vals) == 1:
                cond_parts.append(f"{col} {vals[0]}")
            elif len(vals) == 2:
                cond_parts.append(f"{col} as {vals[0]} and {vals[1]}")
            else:
                cond_parts.append(f"{col} as {', '.join(vals[:-1])} and {vals[-1]}")

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

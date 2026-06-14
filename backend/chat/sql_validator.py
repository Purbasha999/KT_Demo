import re
from typing import Any

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE"
    r"|EXEC|EXECUTE|CALL|LOAD|OUTFILE|DUMPFILE|INTO\s+OUTFILE"
    r"|INFORMATION_SCHEMA|SHOW\s+DATABASES)\b",
    re.IGNORECASE,
)

TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+`?(\w+)`?", re.IGNORECASE)

FORBIDDEN_MONGO_OPS   = {"insertone","insertmany","updateone","updatemany",
                          "replaceone","deleteone","deletemany","drop",
                          "dropcollection","createcollection","createindex"}
FORBIDDEN_MONGO_STAGES = {"$out", "$merge"}


def validate_mysql(sql: str, allowed_tables: list[str]) -> tuple[bool, str]:
    sql = sql.strip().rstrip(";")

    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return False, "Query must start with SELECT."

    m = FORBIDDEN_SQL.search(sql)
    if m:
        return False, f"Forbidden keyword: {m.group()}."

    if ";" in sql:
        return False, "Multiple statements are not allowed."

    if allowed_tables != ["*"]:
        permitted  = {t.lower() for t in allowed_tables}
        referenced = TABLE_REF.findall(sql)
        for table in referenced:
            if table.lower() not in permitted:
                return False, f"Table '{table}' is not permitted for your role."

    return True, ""


def validate_mongo(query: dict, allowed_collections: list[str]) -> tuple[bool, str]:
    if not isinstance(query, dict):
        return False, "MongoDB query must be a JSON object."

    collection = query.get("collection", "")
    if not collection:
        return False, "MongoDB query must specify a 'collection'."

    if allowed_collections != ["*"] and collection not in allowed_collections:
        return False, f"Collection '{collection}' is not permitted for your role."

    operation = query.get("operation", "find").lower()
    if operation in FORBIDDEN_MONGO_OPS:
        return False, f"Operation '{operation}' is not allowed."

    if operation not in ("find", "aggregate", "count_documents"):
        return False, f"Unknown operation '{operation}'."

    if operation == "aggregate":
        for stage in query.get("pipeline", []):
            for forbidden in FORBIDDEN_MONGO_STAGES:
                if forbidden in stage:
                    return False, f"Pipeline stage '{forbidden}' is not allowed."

    return True, ""


def validate_query(db_type: str, query: Any, allowed_tables: list[str]) -> tuple[bool, str]:
    if db_type == "mongodb":
        return validate_mongo(query, allowed_tables)
    return validate_mysql(query, allowed_tables)

import re
from typing import Any

_TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+`?(\w+)`?", re.IGNORECASE)


def _condition_mysql(col: str, values: list[str]) -> str:
    safe = [str(v).replace("'", "''") for v in values]
    if len(safe) == 1:
        return f"`{col}` = '{safe[0]}'"
    in_list = ", ".join(f"'{v}'" for v in safe)
    return f"`{col}` IN ({in_list})"


def inject_row_filters_mysql(sql: str, row_filters: dict) -> str:
    """Inject mandatory WHERE conditions into an already-generated SQL string."""
    if not row_filters:
        return sql

    referenced = {t.lower() for t in _TABLE_REF.findall(sql)}
    conditions = []
    for table, filters in row_filters.items():
        if table.lower() not in referenced:
            continue
        for col, values in filters.items():
            if values:
                conditions.append(_condition_mysql(col, [str(v) for v in values]))

    if not conditions:
        return sql

    clause = " AND ".join(conditions)
    sql_up = sql.upper()

    if " WHERE " in sql_up:
        pos = sql_up.index(" WHERE ") + 7
        return sql[:pos] + clause + " AND " + sql[pos:]

    for kw in (" GROUP BY ", " HAVING ", " ORDER BY ", " LIMIT "):
        if kw in sql_up:
            pos = sql_up.index(kw)
            return sql[:pos] + " WHERE " + clause + sql[pos:]

    return sql + " WHERE " + clause


def _extract_regex_literal(op_dict: dict) -> str | None:
    """If op_dict is {$regex: '^X$', ...} with no special chars in X, return X; else None."""
    regex = op_dict.get("$regex")
    if not isinstance(regex, str):
        return None
    if not (regex.startswith("^") and regex.endswith("$")):
        return None
    core = regex[1:-1]
    if any(c in core for c in r"\.+*?[](){}|^$"):
        return None
    return core


def inject_row_filters_mongo(query: dict, row_filters: dict) -> dict:
    """Enforce row-level access by checking whether the LLM's filter is within the allowed set.

    - LLM uses exact string in allowed set → keep as-is (specific authorized filter)
    - LLM uses exact string NOT in allowed set → {$in: []} → returns 0 (unauthorized)
    - LLM uses {$in: [...]} → intersect with allowed set
    - LLM uses {$regex: '^X$'} → extract X, check authorization, keep or zero-out
    - LLM uses other operators ($ne, $gt, $exists, date ranges) → keep as-is (non-conflicting)
    - LLM has no filter for mandatory field → inject mandatory directly
    """
    if not row_filters:
        return query

    collection = query.get("collection", "")
    if collection not in row_filters:
        return query

    existing = dict(query.get("filter") or {})

    for col, values in row_filters[collection].items():
        if not values:
            continue
        allowed = [str(v) for v in values]
        mandatory_val = allowed[0] if len(allowed) == 1 else {"$in": allowed}

        if col not in existing:
            existing[col] = mandatory_val
            continue

        llm_val = existing[col]

        if isinstance(llm_val, str):
            if llm_val not in allowed:
                existing[col] = {"$in": []}  # unauthorized value → 0 results
            # else: authorized exact string → leave unchanged

        elif isinstance(llm_val, dict):
            if "$in" in llm_val:
                intersection = [v for v in (str(x) for x in llm_val["$in"]) if v in allowed]
                existing[col] = intersection[0] if len(intersection) == 1 else {"$in": intersection}
            else:
                literal = _extract_regex_literal(llm_val)
                if literal is not None and literal not in allowed:
                    existing[col] = {"$in": []}  # unauthorized regex → 0 results
                # else: authorized regex or non-regex operator (date range, $ne, etc.) → leave unchanged

    return {**query, "filter": existing}


def inject_row_filters(db_type: str, query: Any, row_filters: dict | None) -> Any:
    if not row_filters:
        return query
    if db_type == "mongodb":
        return inject_row_filters_mongo(query, row_filters)
    return inject_row_filters_mysql(query, row_filters)

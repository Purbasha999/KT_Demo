import re
from typing import Any

_TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+`?(\w+)`?", re.IGNORECASE)

_MYSQL_OP_MAP = {
    "$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=", "$ne": "!=", "$eq": "=",
}


def _quote_list(values: list) -> str:
    """Render a list of SQL-escaped strings as a quoted, comma-separated IN list."""
    safe = [str(v).replace("'", "''") for v in values]
    return ", ".join("'" + v + "'" for v in safe)


def _condition_mysql(col: str, rule) -> str:
    """Build a SQL condition for one column. rule is a list (equality/IN) or dict (operators)."""
    if isinstance(rule, list):
        safe = [str(v).replace("'", "''") for v in rule]
        if len(safe) == 1:
            return f"`{col}` = '{safe[0]}'"
        return f"`{col}` IN ({_quote_list(rule)})"

    if isinstance(rule, dict):
        parts = []
        for op, val in rule.items():
            if op in _MYSQL_OP_MAP:
                sql_op = _MYSQL_OP_MAP[op]
                if isinstance(val, str):
                    escaped = val.replace("'", "''")
                    parts.append(f"`{col}` {sql_op} '{escaped}'")
                else:
                    parts.append(f"`{col}` {sql_op} {val}")
            elif op == "$in":
                parts.append(f"`{col}` IN ({_quote_list(val)})")
            elif op == "$nin":
                parts.append(f"`{col}` NOT IN ({_quote_list(val)})")
        return " AND ".join(parts)

    return ""


def inject_row_filters_mysql(sql: str, row_filters: dict) -> str:
    """Inject mandatory WHERE conditions into an already-generated SQL string."""
    if not row_filters:
        return sql

    referenced = {t.lower() for t in _TABLE_REF.findall(sql)}
    conditions = []
    for table, filters in row_filters.items():
        if table.lower() not in referenced:
            continue
        for col, rule in filters.items():
            if rule is None or rule == [] or rule == {}:
                continue
            # List rules were stored as lists of values; pass as-is
            # Dict rules are operator expressions; pass as-is
            cond = _condition_mysql(col, rule if isinstance(rule, (list, dict)) else [rule])
            if cond:
                conditions.append(cond)

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


def _is_operator_dict(d: dict) -> bool:
    """True if every key starts with $ (MongoDB operator expression)."""
    return bool(d) and all(k.startswith("$") for k in d)


def _extract_regex_literal(op_dict: dict) -> str | None:
    """If op_dict is {$regex: '^X$', ...} with no special regex chars in X, return X; else None."""
    regex = op_dict.get("$regex")
    if not isinstance(regex, str):
        return None
    if not (regex.startswith("^") and regex.endswith("$")):
        return None
    core = regex[1:-1]
    if any(c in core for c in r"\.+*?[](){}|^$"):
        return None
    return core


def inject_row_filters_mongo(query: dict, row_filters: dict) -> tuple[dict, bool]:
    """Enforce row-level access rules on a MongoDB query's filter.

    List rules  (equality / IN)  → authorization-check: verify LLM value is in allowed set.
    Operator rules ($gt/$lt/etc.) → always inject; merge with LLM's operator dict if present.

    Returns (updated_query, access_denied).
    access_denied=True when the LLM requested values outside the permitted set.
    """
    if not row_filters:
        return query, False

    collection = query.get("collection", "")
    if collection not in row_filters:
        return query, False

    existing = dict(query.get("filter") or {})
    access_denied = False

    for col, rule in row_filters[collection].items():
        if rule is None or rule == [] or rule == {}:
            continue

        # ── List rule: equality / IN ──────────────────────────────────────────
        if isinstance(rule, list):
            allowed = [str(v) for v in rule]
            mandatory_val = allowed[0] if len(allowed) == 1 else {"$in": allowed}

            if col not in existing:
                existing[col] = mandatory_val
                continue

            llm_val = existing[col]

            if isinstance(llm_val, str):
                if llm_val not in allowed:
                    existing[col] = {"$in": []}          # unauthorized → 0 results
                    access_denied = True

            elif isinstance(llm_val, dict):
                if "$in" in llm_val:
                    intersection = [v for v in (str(x) for x in llm_val["$in"]) if v in allowed]
                    if not intersection:
                        access_denied = True
                    existing[col] = intersection[0] if len(intersection) == 1 else {"$in": intersection}
                else:
                    # Check for regex BEFORE _is_operator_dict — {$regex, $options} satisfies
                    # _is_operator_dict but must be treated as an equality-check, not a range op.
                    literal = _extract_regex_literal(llm_val)
                    if literal is not None:
                        if literal not in allowed:
                            existing[col] = {"$in": []}  # unauthorized regex → 0 results
                            access_denied = True
                        # else: authorized regex → leave unchanged
                    elif _is_operator_dict(llm_val):
                        # Genuine non-equality operator ($ne, $gt, etc.) on equality-restricted field
                        existing_val = existing.pop(col)
                        and_list = list(existing.get("$and") or [])
                        and_list.extend([{col: existing_val}, {col: mandatory_val}])
                        existing["$and"] = and_list

        # ── Operator rule: $gt / $gte / $lt / $lte / $ne / etc. ──────────────
        elif isinstance(rule, dict) and _is_operator_dict(rule):
            if col not in existing:
                existing[col] = rule

            elif isinstance(existing[col], dict) and _is_operator_dict(existing[col]):
                # Merge operator dicts; admin constraint overwrites on key conflict
                existing[col] = {**existing[col], **rule}

            else:
                # LLM has a non-operator value on this field; combine with $and
                existing_val = existing.pop(col)
                and_list = list(existing.get("$and") or [])
                and_list.extend([{col: existing_val}, {col: rule}])
                existing["$and"] = and_list

    return {**query, "filter": existing}, access_denied


def inject_row_filters(db_type: str, query: Any, row_filters: dict | None) -> tuple[Any, bool]:
    """Returns (filtered_query, access_denied)."""
    if not row_filters:
        return query, False
    if db_type == "mongodb":
        return inject_row_filters_mongo(query, row_filters)
    return inject_row_filters_mysql(query, row_filters), False

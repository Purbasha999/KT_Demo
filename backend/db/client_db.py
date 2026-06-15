import aiomysql
import motor.motor_asyncio as motor
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

_mysql_pools: dict[str, aiomysql.Pool] = {}


# MySQL
async def _get_mysql_pool(firm_id: str, db_config: dict) -> aiomysql.Pool:
    if firm_id not in _mysql_pools:
        _mysql_pools[firm_id] = await aiomysql.create_pool(
            host=db_config["host"],
            port=int(db_config["port"]),
            user=db_config["user"],
            password=db_config["password"],
            db=db_config["db_name"],
            minsize=1,
            maxsize=5,
            autocommit=True,
            charset="utf8mb4",
            connect_timeout=10,
        )
    return _mysql_pools[firm_id]


async def _execute_mysql(firm_id: str, db_config: dict,
                          sql: str, params: tuple = ()) -> list[dict]:
    pool = await _get_mysql_pool(firm_id, db_config)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params)
            return [_sanitise(r) for r in await cur.fetchall()]


# MongoDB
def _clean_mongo_uri(mongo_uri: str) -> str:
    """
    Strip problematic query parameters (e.g. appName) from the URI
    that cause motor find() to silently return empty results.
    Keeps only retryWrites and w which are safe.
    """
    parsed = urlparse(mongo_uri)
    params = parse_qs(parsed.query)
    safe_params = {}
    if "retryWrites" in params:
        safe_params["retryWrites"] = params["retryWrites"][0]
    if "w" in params:
        safe_params["w"] = params["w"][0]
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(safe_params),
        parsed.fragment,
    ))


def _get_mongo_client(mongo_uri: str) -> motor.AsyncIOMotorClient:
    """
    Always return a fresh client with a cleaned URI.
    Atlas manages connection pooling internally so no need to cache.
    """
    clean_uri = _clean_mongo_uri(mongo_uri)
    return motor.AsyncIOMotorClient(
        clean_uri,
        serverSelectionTimeoutMS=10000,
    )


def _coerce_filter(filter_dict: dict, schema_fields: list[dict]) -> dict:
    """
    Coerce filter values to match schema field types.
    Wraps plain string values in case-insensitive regex for string fields.
    Never touches enum fields or existing operator expressions.
    """
    if not filter_dict or not schema_fields:
        return filter_dict

    type_map = {}
    for field in schema_fields:
        t = field.get("type", "").lower()
        if any(x in t for x in ("int", "number", "integer", "long")):
            type_map[field["name"]] = "int"
        elif any(x in t for x in ("float", "double", "decimal")):
            type_map[field["name"]] = "float"
        elif any(x in t for x in ("bool", "boolean")):
            type_map[field["name"]] = "bool"
        elif t == "string":
            type_map[field["name"]] = "string"

    ENUM_FIELDS = {
        "status", "bookingStatus", "paymentStatus", "role",
        "class", "seatType", "gender", "type", "isActive",
    }

    coerced = {}
    for k, v in filter_dict.items():
        field_key = k.split(".")[-1]   # handle dot-notation e.g. "source.city"

        if isinstance(v, dict):
            coerced[k] = v

        elif type_map.get(k) == "int" and isinstance(v, str):
            try:
                coerced[k] = int(v)
            except (ValueError, TypeError):
                coerced[k] = v

        elif type_map.get(k) == "float" and isinstance(v, str):
            try:
                coerced[k] = float(v)
            except (ValueError, TypeError):
                coerced[k] = v

        elif type_map.get(k) == "bool" and isinstance(v, str):
            coerced[k] = v.lower() in ("true", "1", "yes")

        elif (
            type_map.get(k) == "string"
            and isinstance(v, str)
            and field_key not in ENUM_FIELDS
        ):
            coerced[k] = {"$regex": f"^{v}$", "$options": "i"}

        else:
            coerced[k] = v

    return coerced


async def _execute_mongo(firm_id: str, db_config: dict,
                          operation: dict) -> list[dict]:
    schema_fields = operation.pop("_schema_fields", [])

    mongo_client = _get_mongo_client(db_config["mongo_uri"])
    db           = mongo_client[db_config["db_name"]]
    collection   = db[operation["collection"]]
    op           = operation.get("operation", "find").lower()

    raw_limit = operation.get("limit", 100)
    limit     = max(1, min(int(raw_limit) if raw_limit else 100, 500))

    try:
        if op == "aggregate":
            pipeline = operation.get("pipeline", [])
            for stage in pipeline:
                for forbidden in ("$out", "$merge"):
                    if forbidden in stage:
                        raise ValueError(
                            f"Pipeline stage '{forbidden}' is not allowed."
                        )
            rows = await collection.aggregate(pipeline).to_list(length=limit)

        elif op == "count_documents":
            filt  = _coerce_filter(operation.get("filter", {}), schema_fields)
            count = await collection.count_documents(filt)
            rows  = [{"count": count}]

        else:  # find
            filt = _coerce_filter(operation.get("filter", {}), schema_fields)
            rows = await collection.find(filt).limit(limit).to_list(length=limit)

    finally:
        mongo_client.close()

    return [_sanitise(r) for r in rows]


# Connection test
async def test_connection(db_type: str, db_config: dict) -> tuple[bool, str]:
    try:
        if db_type == "mongodb":
            client = _get_mongo_client(db_config["mongo_uri"])
            await client.server_info()
            client.close()
        else:
            conn = await aiomysql.connect(
                host=db_config["host"],
                port=int(db_config["port"]),
                user=db_config["user"],
                password=db_config["password"],
                db=db_config["db_name"],
                connect_timeout=5,
            )
            conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


# Execute query
async def execute_query(firm_id: str, db_type: str,
                         db_config: dict, query) -> list[dict]:
    """
    query : str  for MySQL  (SQL SELECT string)
            dict for MongoDB (operation dict from LLM)
    Always returns list[dict].
    """
    if db_type == "mongodb":
        return await _execute_mongo(firm_id, db_config, query)
    return await _execute_mysql(firm_id, db_config, query)


# Cleanup
async def close_all_pools():
    for pool in _mysql_pools.values():
        pool.close()
        await pool.wait_closed()
    _mysql_pools.clear()


# Helper
def _sanitise(row: dict) -> dict:
    """Convert non-JSON-serialisable types so results can be sent to the LLM."""
    import decimal
    import datetime
    out = {}
    for k, v in row.items():
        if k == "_id":
            out[k] = str(v)
        elif isinstance(v, decimal.Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

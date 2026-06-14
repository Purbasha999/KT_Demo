"""
Platform DB — your own MySQL instance.
Stores: firms, schemas, roles, users.

Firm DB credentials stored here are always encrypted.
MySQL fields and mongo_uri are all optional — only one DB type is required per firm.
"""

import aiomysql
import json
from typing import Optional
from core.config import settings

_pool: Optional[aiomysql.Pool] = None


async def init_db():
    global _pool
    _pool = await aiomysql.create_pool(
        host=settings.PLATFORM_DB_HOST,
        port=settings.PLATFORM_DB_PORT,
        user=settings.PLATFORM_DB_USER,
        password=settings.PLATFORM_DB_PASSWORD,
        db=settings.PLATFORM_DB_NAME,
        minsize=2,
        maxsize=10,
        autocommit=True,
        charset="utf8mb4",
    )
    await _create_tables()


async def close_db():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()


async def _create_tables():
    statements = [
        # firms — all DB credential fields nullable; only one set required per db_type
        """
        CREATE TABLE IF NOT EXISTS firms (
            firm_id       VARCHAR(50)  PRIMARY KEY,
            firm_name     VARCHAR(100) NOT NULL,
            description   TEXT,
            db_type       ENUM('mysql','mongodb') NOT NULL,
            -- MySQL fields (required when db_type = 'mysql')
            db_host       VARCHAR(200),
            db_port       INT,
            db_name       VARCHAR(100),
            db_user       VARCHAR(100),
            db_password   TEXT,
            -- MongoDB field (required when db_type = 'mongodb')
            mongo_uri     TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS firm_schemas (
            firm_id    VARCHAR(50) PRIMARY KEY,
            schema_json JSON NOT NULL,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS roles (
            role_id        INT AUTO_INCREMENT PRIMARY KEY,
            firm_id        VARCHAR(50)  NOT NULL,
            role_name      VARCHAR(100) NOT NULL,
            allowed_tables JSON NOT NULL,
            row_filters    JSON,
            UNIQUE KEY uq_firm_role (firm_id, role_name),
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id       VARCHAR(50)  PRIMARY KEY,
            firm_id       VARCHAR(50)  NOT NULL,
            login_id      VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name  VARCHAR(100),
            is_admin      BOOLEAN DEFAULT FALSE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_login (firm_id, login_id),
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id VARCHAR(50) PRIMARY KEY,
            role_id INT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(role_id)  ON DELETE CASCADE
        )
        """,
    ]
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in statements:
                await cur.execute(stmt)


# ── Firm ─────────────────────────────────────────────────────────────────────

async def get_firm(firm_id: str) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM firms WHERE firm_id = %s", (firm_id,))
            return await cur.fetchone()


async def get_all_firms() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT firm_id, firm_name, description FROM firms ORDER BY firm_name"
            )
            return await cur.fetchall()


async def create_firm(
    firm_id: str,
    firm_name: str,
    description: str,
    db_type: str,
    # MySQL — optional
    db_host: Optional[str] = None,
    db_port: Optional[int] = None,
    db_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_password_enc: Optional[str] = None,
    # MongoDB — optional
    mongo_uri_enc: Optional[str] = None,
):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO firms
                   (firm_id, firm_name, description, db_type,
                    db_host, db_port, db_name, db_user, db_password,
                    mongo_uri)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (firm_id, firm_name, description, db_type,
                 db_host, db_port, db_name, db_user, db_password_enc,
                 mongo_uri_enc),
            )


# ── Schema ────────────────────────────────────────────────────────────────────

async def save_schema(firm_id: str, schema: dict):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO firm_schemas (firm_id, schema_json) VALUES (%s,%s)
                   ON DUPLICATE KEY UPDATE
                     schema_json = VALUES(schema_json),
                     updated_at  = NOW()""",
                (firm_id, json.dumps(schema)),
            )


async def get_schema(firm_id: str) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT schema_json FROM firm_schemas WHERE firm_id = %s", (firm_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            data = row["schema_json"]
            return json.loads(data) if isinstance(data, str) else data


# ── Roles ─────────────────────────────────────────────────────────────────────

async def create_or_update_role(
    firm_id: str, role_name: str,
    allowed_tables: list, row_filters: dict = None
) -> int:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO roles (firm_id, role_name, allowed_tables, row_filters)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     allowed_tables = VALUES(allowed_tables),
                     row_filters    = VALUES(row_filters)""",
                (firm_id, role_name,
                 json.dumps(allowed_tables), json.dumps(row_filters or {})),
            )
            await cur.execute(
                "SELECT role_id FROM roles WHERE firm_id = %s AND role_name = %s",
                (firm_id, role_name),
            )
            return (await cur.fetchone())[0]


async def get_roles_for_firm(firm_id: str) -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT role_id, role_name, allowed_tables, row_filters FROM roles WHERE firm_id = %s",
                (firm_id,),
            )
            rows = await cur.fetchall()
            for r in rows:
                for k in ("allowed_tables", "row_filters"):
                    if isinstance(r[k], str):
                        r[k] = json.loads(r[k])
            return rows


async def get_role(role_id: int) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM roles WHERE role_id = %s", (role_id,))
            row = await cur.fetchone()
            if row:
                for k in ("allowed_tables", "row_filters"):
                    if isinstance(row[k], str):
                        row[k] = json.loads(row[k])
            return row


async def delete_role(role_id: int):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM roles WHERE role_id = %s", (role_id,))


# ── Users ─────────────────────────────────────────────────────────────────────

async def create_user(
    user_id: str, firm_id: str, login_id: str,
    password_hash: str, display_name: str, is_admin: bool
):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO users
                   (user_id, firm_id, login_id, password_hash, display_name, is_admin)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (user_id, firm_id, login_id, password_hash, display_name, is_admin),
            )


async def get_user_by_login(firm_id: str, login_id: str) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM users WHERE firm_id = %s AND login_id = %s",
                (firm_id, login_id),
            )
            return await cur.fetchone()


async def get_users_for_firm(firm_id: str) -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT u.user_id, u.login_id, u.display_name, u.is_admin,
                          r.role_name, r.role_id
                   FROM users u
                   LEFT JOIN user_roles ur ON u.user_id = ur.user_id
                   LEFT JOIN roles r       ON ur.role_id = r.role_id
                   WHERE u.firm_id = %s AND u.is_admin = FALSE
                   ORDER BY u.display_name""",
                (firm_id,),
            )
            return await cur.fetchall()


async def assign_role_to_user(user_id: str, role_id: int):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO user_roles (user_id, role_id) VALUES (%s,%s)
                   ON DUPLICATE KEY UPDATE role_id = VALUES(role_id)""",
                (user_id, role_id),
            )


async def get_user_role(user_id: str) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT r.role_id, r.role_name, r.allowed_tables,
                          r.row_filters, r.firm_id
                   FROM user_roles ur
                   JOIN roles r ON ur.role_id = r.role_id
                   WHERE ur.user_id = %s""",
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                for k in ("allowed_tables", "row_filters"):
                    if isinstance(row[k], str):
                        row[k] = json.loads(row[k])
            return row

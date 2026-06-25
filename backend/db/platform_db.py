import aiomysql
import json
from typing import Optional
from core.config import settings

_pool: Optional[aiomysql.Pool] = None

async def _ensure_database():
    """Create the platform database if it doesn't exist."""
    conn = await aiomysql.connect(
        host=settings.PLATFORM_DB_HOST,
        port=settings.PLATFORM_DB_PORT,
        user=settings.PLATFORM_DB_USER,
        password=settings.PLATFORM_DB_PASSWORD,
        autocommit=True,
        charset="utf8mb4",
    )
    async with conn.cursor() as cur:
        await cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.PLATFORM_DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn.close()


async def init_db():
    global _pool
    await _ensure_database()
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
        """
        CREATE TABLE IF NOT EXISTS firms (
            firm_id       VARCHAR(50)  PRIMARY KEY,
            firm_name     VARCHAR(100) NOT NULL,
            description   TEXT,
            db_type       ENUM('mysql','mongodb','none') NOT NULL DEFAULT 'none',
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
            role_id           INT AUTO_INCREMENT PRIMARY KEY,
            firm_id           VARCHAR(50)  NOT NULL,
            role_name         VARCHAR(100) NOT NULL,
            allowed_tables    JSON NOT NULL,
            allowed_documents JSON NOT NULL DEFAULT ('["*"]'),
            row_filters       JSON,
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
        """
        CREATE TABLE IF NOT EXISTS firm_documents (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            firm_id      VARCHAR(50)  NOT NULL,
            filename     VARCHAR(255) NOT NULL,
            chunks_count INT          DEFAULT 0,
            description  TEXT,
            uploaded_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_firm_doc (firm_id, filename),
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id) ON DELETE CASCADE
        )
        """,
    ]
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in statements:
                await cur.execute(stmt)
    await _migrate()


async def _migrate():
    """Idempotent column additions for existing installations."""
    migrations = [
        "ALTER TABLE firm_documents ADD COLUMN description TEXT",
        "ALTER TABLE roles ADD COLUMN allowed_documents JSON NOT NULL DEFAULT (JSON_ARRAY('*'))",
        "ALTER TABLE firms MODIFY COLUMN db_type ENUM('mysql','mongodb','none') NOT NULL DEFAULT 'none'",
        "ALTER TABLE firms ADD COLUMN last_accessed_at TIMESTAMP NULL",
    ]
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in migrations:
                try:
                    await cur.execute(stmt)
                except Exception:
                    pass  # column already exists


# Firms
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
    db_type: str = "none",
    db_host: Optional[str] = None,
    db_port: Optional[int] = None,
    db_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_password_enc: Optional[str] = None,
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


# Schema
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


# Roles
async def create_or_update_role(
    firm_id: str, role_name: str,
    allowed_tables: list, allowed_documents: list = None, row_filters: dict = None
) -> int:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO roles
                     (firm_id, role_name, allowed_tables, allowed_documents, row_filters)
                   VALUES (%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     allowed_tables    = VALUES(allowed_tables),
                     allowed_documents = VALUES(allowed_documents),
                     row_filters       = VALUES(row_filters)""",
                (firm_id, role_name,
                 json.dumps(allowed_tables),
                 json.dumps(allowed_documents if allowed_documents is not None else ["*"]),
                 json.dumps(row_filters or {})),
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
                """SELECT role_id, role_name, allowed_tables, allowed_documents, row_filters
                   FROM roles WHERE firm_id = %s""",
                (firm_id,),
            )
            rows = await cur.fetchall()
            for r in rows:
                for k in ("allowed_tables", "allowed_documents", "row_filters"):
                    if isinstance(r.get(k), str):
                        r[k] = json.loads(r[k])
                if r.get("allowed_documents") is None:
                    r["allowed_documents"] = ["*"]
            return rows


async def get_role(role_id: int) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM roles WHERE role_id = %s", (role_id,))
            row = await cur.fetchone()
            if row:
                for k in ("allowed_tables", "allowed_documents", "row_filters"):
                    if isinstance(row.get(k), str):
                        row[k] = json.loads(row[k])
                if row.get("allowed_documents") is None:
                    row["allowed_documents"] = ["*"]
            return row


async def update_role(
    role_id: int, firm_id: str, role_name: str,
    allowed_tables: list, allowed_documents: list, row_filters: dict,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE roles
                   SET role_name=%s, allowed_tables=%s, allowed_documents=%s, row_filters=%s
                   WHERE role_id=%s AND firm_id=%s""",
                (role_name, json.dumps(allowed_tables),
                 json.dumps(allowed_documents or ["*"]),
                 json.dumps(row_filters or {}),
                 role_id, firm_id),
            )


async def delete_role(role_id: int):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM roles WHERE role_id = %s", (role_id,))


# Users
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


async def delete_user(user_id: str, firm_id: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM users WHERE user_id=%s AND firm_id=%s",
                (user_id, firm_id),
            )


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
                          r.allowed_documents, r.row_filters, r.firm_id
                   FROM user_roles ur
                   JOIN roles r ON ur.role_id = r.role_id
                   WHERE ur.user_id = %s""",
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                for k in ("allowed_tables", "allowed_documents", "row_filters"):
                    if isinstance(row.get(k), str):
                        row[k] = json.loads(row[k])
                if row.get("allowed_documents") is None:
                    row["allowed_documents"] = ["*"]
            return row


# Documents
async def save_document_record(
    firm_id: str, filename: str, chunks_count: int, description: str = None
):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO firm_documents (firm_id, filename, chunks_count, description)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                     chunks_count = VALUES(chunks_count),
                     description  = VALUES(description),
                     uploaded_at  = NOW()""",
                (firm_id, filename, chunks_count, description),
            )


async def get_documents_for_firm(firm_id: str) -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT filename, chunks_count, description, uploaded_at
                   FROM firm_documents
                   WHERE firm_id = %s
                   ORDER BY uploaded_at DESC""",
                (firm_id,),
            )
            rows = await cur.fetchall()
            for r in rows:
                if r.get("uploaded_at"):
                    r["uploaded_at"] = r["uploaded_at"].isoformat()
            return rows


async def delete_document_record(firm_id: str, filename: str):
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM firm_documents WHERE firm_id = %s AND filename = %s",
                (firm_id, filename),
            )


# ── User helpers ───────────────────────────────────────────────────────────────
async def get_user_by_id(user_id: str, firm_id: str) -> Optional[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM users WHERE user_id=%s AND firm_id=%s",
                (user_id, firm_id),
            )
            return await cur.fetchone()


async def update_user_details(
    user_id: str, firm_id: str, display_name: str, login_id: str,
    password_hash: Optional[str] = None,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            if password_hash:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s, password_hash=%s
                       WHERE user_id=%s AND firm_id=%s AND is_admin=FALSE""",
                    (display_name, login_id, password_hash, user_id, firm_id),
                )
            else:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s
                       WHERE user_id=%s AND firm_id=%s AND is_admin=FALSE""",
                    (display_name, login_id, user_id, firm_id),
                )


# ── Superadmin: dashboard ──────────────────────────────────────────────────────
async def get_superadmin_stats() -> dict:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM firms) AS firm_count,
                    (SELECT COUNT(*) FROM users WHERE is_admin = TRUE)  AS admin_count,
                    (SELECT COUNT(*) FROM users WHERE is_admin = FALSE) AS user_count
            """)
            return await cur.fetchone()


# ── Superadmin: firms CRUD ─────────────────────────────────────────────────────
async def get_all_firms_detailed() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT
                    f.firm_id, f.firm_name, f.description, f.db_type,
                    f.db_host, f.db_port, f.db_name, f.db_user,
                    f.created_at, f.last_accessed_at,
                    COUNT(DISTINCT CASE WHEN u.is_admin=FALSE THEN u.user_id END) AS user_count,
                    COUNT(DISTINCT CASE WHEN u.is_admin=TRUE  THEN u.user_id END) AS admin_count
                FROM firms f
                LEFT JOIN users u ON f.firm_id = u.firm_id
                GROUP BY f.firm_id
                ORDER BY f.firm_name
            """)
            rows = await cur.fetchall()
            for r in rows:
                for col in ("created_at", "last_accessed_at"):
                    if r.get(col):
                        r[col] = r[col].isoformat()
            return rows


async def update_firm(
    firm_id: str, firm_name: str, description: str, db_type: str,
    db_host: Optional[str] = None, db_port: Optional[int] = None,
    db_name: Optional[str] = None, db_user: Optional[str] = None,
    db_password_enc: Optional[str] = None, mongo_uri_enc: Optional[str] = None,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            sets   = ["firm_name=%s", "description=%s", "db_type=%s",
                      "db_host=%s", "db_port=%s", "db_name=%s", "db_user=%s"]
            params = [firm_name, description, db_type, db_host, db_port, db_name, db_user]
            if db_password_enc is not None:
                sets.append("db_password=%s");  params.append(db_password_enc)
            if mongo_uri_enc is not None:
                sets.append("mongo_uri=%s");     params.append(mongo_uri_enc)
            params.append(firm_id)
            await cur.execute(f"UPDATE firms SET {', '.join(sets)} WHERE firm_id=%s", params)


async def delete_firm(firm_id: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM firms WHERE firm_id=%s", (firm_id,))


async def get_firms_list() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT firm_id, firm_name FROM firms ORDER BY firm_name")
            return await cur.fetchall()


# ── Superadmin: admins CRUD ────────────────────────────────────────────────────
async def get_all_admins() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT u.user_id, u.firm_id, f.firm_name, u.login_id,
                       u.display_name, u.created_at
                FROM users u
                JOIN firms f ON u.firm_id = f.firm_id
                WHERE u.is_admin = TRUE
                ORDER BY f.firm_name, u.display_name
            """)
            rows = await cur.fetchall()
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return rows


async def create_admin(
    user_id: str, firm_id: str, login_id: str,
    password_hash: str, display_name: str,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO users
                   (user_id, firm_id, login_id, password_hash, display_name, is_admin)
                   VALUES (%s,%s,%s,%s,%s,TRUE)""",
                (user_id, firm_id, login_id, password_hash, display_name),
            )


async def update_admin(
    user_id: str, display_name: str, login_id: str,
    password_hash: Optional[str] = None,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            if password_hash:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s, password_hash=%s
                       WHERE user_id=%s AND is_admin=TRUE""",
                    (display_name, login_id, password_hash, user_id),
                )
            else:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s
                       WHERE user_id=%s AND is_admin=TRUE""",
                    (display_name, login_id, user_id),
                )


async def delete_admin(user_id: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM users WHERE user_id=%s AND is_admin=TRUE", (user_id,)
            )


# ── Superadmin: users (read/edit/delete) ──────────────────────────────────────
async def get_all_users_superadmin() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT u.user_id, u.firm_id, f.firm_name, u.login_id,
                       u.display_name, u.created_at, r.role_name
                FROM users u
                JOIN firms f ON u.firm_id = f.firm_id
                LEFT JOIN user_roles ur ON u.user_id = ur.user_id
                LEFT JOIN roles r       ON ur.role_id = r.role_id
                WHERE u.is_admin = FALSE
                ORDER BY f.firm_name, u.display_name
            """)
            rows = await cur.fetchall()
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return rows


async def update_user_superadmin(
    user_id: str, display_name: str, login_id: str,
    password_hash: Optional[str] = None,
) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            if password_hash:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s, password_hash=%s
                       WHERE user_id=%s AND is_admin=FALSE""",
                    (display_name, login_id, password_hash, user_id),
                )
            else:
                await cur.execute(
                    """UPDATE users SET display_name=%s, login_id=%s
                       WHERE user_id=%s AND is_admin=FALSE""",
                    (display_name, login_id, user_id),
                )


async def delete_user_superadmin(user_id: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM users WHERE user_id=%s AND is_admin=FALSE", (user_id,)
            )

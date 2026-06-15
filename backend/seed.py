"""
Seed script — run to onboard or update firms. Re-running is safe (upsert).

db_type = "mysql"   → provide db_host, db_port, db_name, db_user, db_password
db_type = "mongodb" → provide mongo_uri and db_name
db_type = "none"    → docs-only firm (RAG only, no DB) — omit all DB fields
"""

import asyncio
import uuid

FIRMS = [
    {
        "firm_id":        "receiptor",
        "firm_name":      "Receiptor",
        "description":    "Analyses receipts and invoices for hotels, restaurants, cafes, etc for expense management",
        "db_type":        "mongodb",
        "db_name":        "test",
        "mongo_uri":      "",
        "admin_login":    "admin_receiptor",
        "admin_password": "receiptor_admin_pass",
        "admin_display":  "Receiptor Admin",
    },

    # Docs-only example (no DB credentials needed):
    # {
    #     "firm_id":        "acme_docs",
    #     "firm_name":      "ACME Docs",
    #     "description":    "Knowledge base only — no live DB",
    #     "admin_login":    "admin_acme",
    #     "admin_password": "acme_admin_pass",
    #     "admin_display":  "ACME Admin",
    # },

    # MySQL example:
    # {
    #     "firm_id":        "acme",
    #     "firm_name":      "ACME Corp",
    #     "description":    "Manufacturing and supply chain company",
    #     "db_type":        "mysql",
    #     "db_host":        "localhost",
    #     "db_port":        3306,
    #     "db_name":        "acme_corp",
    #     "db_user":        "root",
    #     "db_password":    "",
    #     "admin_login":    "admin_acme",
    #     "admin_password": "acme_admin_pass",
    #     "admin_display":  "ACME Admin",
    # },
]


async def _upsert_firm(pdb, firm, encrypt_value):
    firm_id  = firm["firm_id"]
    db_type  = firm.get("db_type", "none")

    enc_password  = encrypt_value(firm["db_password"]) if firm.get("db_password") else None
    enc_mongo_uri = encrypt_value(firm["mongo_uri"])   if firm.get("mongo_uri")   else None

    existing = await pdb.get_firm(firm_id)
    if existing:
        # Update credentials and metadata in place
        async with pdb._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """UPDATE firms
                       SET firm_name=%s, description=%s, db_type=%s,
                           db_host=%s, db_port=%s, db_name=%s, db_user=%s,
                           db_password=%s, mongo_uri=%s
                       WHERE firm_id=%s""",
                    (
                        firm["firm_name"],
                        firm.get("description", ""),
                        db_type,
                        firm.get("db_host"),
                        firm.get("db_port"),
                        firm.get("db_name"),
                        firm.get("db_user"),
                        enc_password,
                        enc_mongo_uri,
                        firm_id,
                    ),
                )
        print(f"   [UPDATED] Firm credentials/metadata refreshed.")
    else:
        await pdb.create_firm(
            firm_id         = firm_id,
            firm_name       = firm["firm_name"],
            description     = firm.get("description", ""),
            db_type         = db_type,
            db_host         = firm.get("db_host"),
            db_port         = firm.get("db_port"),
            db_name         = firm.get("db_name"),
            db_user         = firm.get("db_user"),
            db_password_enc = enc_password,
            mongo_uri_enc   = enc_mongo_uri,
        )
        print(f"   [CREATED] Firm added.")


async def run():
    from core.security import hash_password, encrypt_value
    import db.platform_db as pdb

    print("Connecting to platform DB...")
    await pdb.init_db()

    for firm in FIRMS:
        firm_id = firm["firm_id"]
        db_type = firm.get("db_type", "none")
        print(f"\n── {firm_id}  ({firm['firm_name']})  [{db_type}] ──")

        await _upsert_firm(pdb, firm, encrypt_value)

        existing_user = await pdb.get_user_by_login(firm_id, firm["admin_login"])
        if existing_user:
            print(f"   [SKIP]    Admin '{firm['admin_login']}' already exists.")
        else:
            await pdb.create_user(
                user_id       = str(uuid.uuid4()),
                firm_id       = firm_id,
                login_id      = firm["admin_login"],
                password_hash = hash_password(firm["admin_password"]),
                display_name  = firm["admin_display"],
                is_admin      = True,
            )
            print(f"   [CREATED] Admin → login: '{firm['admin_login']}'")

    await pdb.close_db()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(run())

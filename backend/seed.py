"""
Seed script — run once per new firm onboarding.

Usage:
    python seed.py

Edit the FIRMS list below with plain text values.
The script handles all bcrypt hashing and Fernet encryption before writing to DB.

db_type = "mysql"   → provide db_host, db_port, db_name, db_user, db_password
db_type = "mongodb" → provide mongo_uri and db_name
                      format: "mongodb://user:password@host:27017"
                      Atlas:  "mongodb+srv://user:password@cluster.mongodb.net"
"""

import asyncio
import uuid

FIRMS = [
    {
        "firm_id":        "flywise",
        "firm_name":      "FlyWise",
        "description":    "Flyise is a ticket booking company that helps customers find and book flights. They have a large database of flight information and customer bookings.",
        "db_type":        "mongodb",
        "db_host":        None,
        "db_port":        None,
        "db_name":        "test",
        "db_user":        None,
        "db_password":    None,
        "mongo_uri":      "mongodb+srv://db_user:flywise_password@cluster0.mfcfgi4.mongodb.net/?appName=Cluster0",
        "admin_login":    "admin_flywise",
        "admin_password": "flywise_admin_pass",
        "admin_display":  "FlyWise Admin",


        # voxomos - Voxomos is an enterprise AI company focused on building human-like conversational AI agents for businesses. They build various campaigns for their clients and then run them in batches
        # "mongodb+srv://kt_demo_db_user:kt_demo_db_user_password@voxbot-cluster.hqja0mr.mongodb.net/?appName=Voxbot-cluster"

        # "firm_id":        "acme",
        # "firm_name":      "ACME Corp",
        # "description":    "Manufacturing and supply chain company",
        # "db_type":        "mysql",
        # "db_host":        "localhost",
        # "db_port":        3306,
        # "db_name":        "acme_corp",
        # "db_user":        "root",
        # "db_password":    "",
        # "mongo_uri":      None,
        # "admin_login":    "admin_acme",
        # "admin_password": "acme_admin_pass",
        # "admin_display":  "ACME Admin",
    },
]


async def run():
    from core.config import settings
    from core.security import hash_password, encrypt_value
    import db.platform_db as pdb

    print("Connecting to platform DB...")
    await pdb.init_db()

    for firm in FIRMS:
        firm_id = firm["firm_id"]
        print(f"\n── {firm_id}  ({firm['firm_name']})  [{firm['db_type']}] ──")

        # ── Firm ──────────────────────────────────────────────────────────────
        existing = await pdb.get_firm(firm_id)
        if existing:
            print(f"   [SKIP] Firm already exists.")
        else:
            # Encrypt whichever credential is present
            enc_password  = encrypt_value(firm["db_password"]) if firm.get("db_password") else None
            enc_mongo_uri = encrypt_value(firm["mongo_uri"])   if firm.get("mongo_uri")   else None

            await pdb.create_firm(
                firm_id         = firm_id,
                firm_name       = firm["firm_name"],
                description     = firm.get("description", ""),
                db_type         = firm["db_type"],
                db_host         = firm.get("db_host"),
                db_port         = firm.get("db_port"),
                db_name         = firm.get("db_name"),
                db_user         = firm.get("db_user"),
                db_password_enc = enc_password,
                mongo_uri_enc   = enc_mongo_uri,
            )
            print(f"   [OK]  Firm created.")

        # ── Admin user ────────────────────────────────────────────────────────
        existing_user = await pdb.get_user_by_login(firm_id, firm["admin_login"])
        if existing_user:
            print(f"   [SKIP] Admin '{firm['admin_login']}' already exists.")
        else:
            await pdb.create_user(
                user_id       = str(uuid.uuid4()),
                firm_id       = firm_id,
                login_id      = firm["admin_login"],
                password_hash = hash_password(firm["admin_password"]),
                display_name  = firm["admin_display"],
                is_admin      = True,
            )
            print(f"   [OK]  Admin created → login: '{firm['admin_login']}'")

    await pdb.close_db()
    print("\nDone. Admins can now log in and configure schema, roles, and users.")


if __name__ == "__main__":
    asyncio.run(run())

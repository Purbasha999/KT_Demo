# SQL / MongoDB Knowledge Map Chatbot

Role-based chatbot that answers natural language questions against MySQL or MongoDB.
No LangChain — pure orchestrated Python with a generate → validate → self-correct loop.

---

## How it works

```
User question
    │
    ▼
Prompt builder
  Schema filtered to user's allowed tables/collections
    │
    ▼                                     ┌─────────────────────────┐
LLM call ─────────────────────────────────▶ db_type = mysql         │
  mysql   → plain SQL SELECT string        │   generate_sql()        │
  mongodb → JSON operation dict            │   response_type: text   │
    │                                      ├─────────────────────────┤
    ▼                                      │ db_type = mongodb        │
Validator                                  │   generate_mongo_query() │
  mysql   → SELECT only, no write keywords │   response_type:         │
  mongodb → read ops only, no $out/$merge  │     json_object          │
    │                                      └─────────────────────────┘
    ├── FAIL → send error to LLM, fix (up to 3 attempts)
    │
    ▼
Execute on firm DB
    ├── DB error → send to LLM, fix (up to 2 retries)
    │
    ▼
Format results → natural language answer
```

---

## Project structure

```
KT_VOX_DEMO/
├── backend/
│   ├── main.py
│   ├── seed.py                     ← onboard firms here
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/
│   │   ├── config.py               no hardcoded values — all from .env
│   │   └── security.py             JWT · bcrypt · Fernet encrypt/decrypt
│   ├── db/
│   │   ├── platform_db.py          your MySQL — firms, schemas, roles, users
│   │   └── client_db.py            aiomysql pool + motor MongoDB client
│   ├── auth/router.py
│   ├── admin/router.py             schema · roles · users
│   ├── chat/
│   │   ├── router.py
│   │   ├── service.py              pipeline with retry loop
│   │   ├── prompt_builder.py       separate MySQL and MongoDB prompts
│   │   ├── sql_validator.py        read-only enforcement for both DB types
│   │   └── llm_client.py           company proxy endpoint
│   └── models/schemas.py
└── frontend/
    └── src/
        ├── pages/ Login · Chat · Admin
        ├── hooks/useAuth.jsx
        └── api/client.js
```

---

## Setup

### 1. Platform database (your MySQL)

```sql
CREATE DATABASE KT_PLATFORM CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Tables are auto-created on first run.

### 2. Backend

```bash
cd backend
cp .env.example .env
# Fill ALL values in .env — nothing is hardcoded in config.py
# Generate encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend && npm install && npm run dev
```

---

## Onboarding a new firm

### Step 1 — Create a read-only user on the firm's DB

**MySQL:**
```sql
CREATE USER 'chatbot_ro'@'%' IDENTIFIED BY 'strong_password';
GRANT SELECT ON their_db.* TO 'chatbot_ro'@'%';
FLUSH PRIVILEGES;
```

**MongoDB:**
```javascript
db.createUser({
  user: "chatbot_ro",
  pwd:  "strong_password",
  roles: [{ role: "read", db: "their_database" }]
})
```

### Step 2 — Add firm to seed.py and run

MySQL firm:
```python
{
    "firm_id":        "acme",
    "firm_name":      "ACME Corp",
    "description":    "Manufacturing company",
    "db_type":        "mysql",
    "db_host":        "192.168.1.100",
    "db_port":        3306,
    "db_name":        "acme_db",
    "db_user":        "chatbot_ro",
    "db_password":    "strong_password",   # plain text — script encrypts it
    "mongo_uri":      None,
    "admin_login":    "admin_acme",
    "admin_password": "admin_pass",        # plain text — script hashes it
    "admin_display":  "ACME Admin",
}
```

MongoDB firm:
```python
{
    "firm_id":        "betacorp",
    "firm_name":      "Beta Corp",
    "description":    "E-commerce analytics",
    "db_type":        "mongodb",
    "db_host":        None,
    "db_port":        None,
    "db_name":        "betacorp_db",
    "db_user":        None,
    "db_password":    None,
    "mongo_uri":      "mongodb://chatbot_ro:strong_password@192.168.1.50:27017/betacorp_db",
    "admin_login":    "admin_beta",
    "admin_password": "admin_pass",
    "admin_display":  "Beta Admin",
}
```

```bash
cd backend && python seed.py
```

Idempotent — safe to re-run. Skips already-seeded firms and users.

### Step 3 — Admin logs in and configures via app

1. Log in with admin credentials
2. **Schema tab** → upload schema JSON
3. **Roles tab** → define roles with allowed tables/collections
4. **Users tab** → create end users, assign roles

---

## Schema JSON

Descriptions are important — the LLM uses them to pick the right table/collection.

```json
{
  "tables": [
    {
      "name": "employees",
      "description": "All company employees with personal and employment details",
      "fields": [
        { "name": "emp_id",    "type": "INT",     "description": "Primary key" },
        { "name": "full_name", "type": "VARCHAR", "description": "Employee full name" },
        { "name": "dept",      "type": "VARCHAR", "description": "Department e.g. HR, Sales" },
        { "name": "salary",    "type": "DECIMAL", "description": "Monthly salary in INR" },
        { "name": "joined_on", "type": "DATE",    "description": "Date joined" }
      ]
    }
  ],
  "relationships": [
    { "from_field": "sales.emp_id", "to_field": "employees.emp_id", "type": "FK" }
  ]
}
```

For MongoDB firms, `tables` means collections and `fields` means document fields. Same format.

---

## firms table structure

| Field        | MySQL firm | MongoDB firm |
|--------------|------------|--------------|
| firm_id      | ✓          | ✓            |
| firm_name    | ✓          | ✓            |
| description  | ✓          | ✓            |
| db_type      | "mysql"    | "mongodb"    |
| db_host      | ✓          | NULL         |
| db_port      | ✓          | NULL         |
| db_name      | ✓          | ✓            |
| db_user      | ✓          | NULL         |
| db_password  | ✓ (enc)    | NULL         |
| mongo_uri    | NULL       | ✓ (enc)      |

Both `db_password` (MySQL) and `mongo_uri` (MongoDB) are Fernet-encrypted before storage.

---

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/firms` | none | Firm list for login dropdown |
| POST | `/auth/login` | none | Login → JWT |
| POST | `/admin/schema` | admin | Upload schema |
| GET | `/admin/schema` | admin | Get schema |
| POST | `/admin/role` | admin | Create/update role |
| GET | `/admin/roles` | admin | List roles |
| DELETE | `/admin/role/{id}` | admin | Delete role |
| POST | `/admin/user` | admin | Create end user |
| GET | `/admin/users` | admin | List users |
| POST | `/admin/user/assign-role` | admin | Assign role |
| POST | `/chat/query` | user | Ask question → answer |

---

## Security

- Read-only enforced at two levels: DB user permissions + app-level validator
- Schema sent to LLM is filtered to role's allowed tables — LLM never sees the rest
- All DB credentials (MySQL password, MongoDB URI) encrypted with Fernet before storage
- JWT scoped to firm_id — users cannot reach another firm's data
- No LangChain or agent framework — full control over every step

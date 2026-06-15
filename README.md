# KT Vox Demo

Multi-tenant AI assistant that answers questions from a company's live database and/or uploaded PDFs.

---

## What it does

- **DB chat** — translates natural language into MySQL / MongoDB queries and returns formatted answers
- **Document chat (RAG)** — hybrid BM25 + semantic search over uploaded PDFs, fused with RRF
- **Combined** — merges both sources automatically when both are relevant
- **Role-based access** — per-role control over which tables and which documents a user can query

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| Frontend | React + Vite + Tailwind |
| Platform DB | MySQL (firms, roles, users) |
| Vector store | Qdrant |
| Dense embeddings | `text-embedding-3-large` via voxomos API |
| Sparse (BM25) | `fastembed` — `Qdrant/bm25` |
| LLM | `gpt-4o` via voxomos API |

---

## Setup

### Prerequisites
- Python 3.11+ · Node 18+ · MySQL · Docker Desktop

### 1. Start Qdrant (one-time — auto-restarts with Docker)
```bash
docker run -d --name qdrant --restart always -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

### 2. Backend
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in all values

python seed.py         # creates DB, tables, firm, and admin user in one step
uvicorn main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend && npm install && npm run dev
```

---

## Onboarding a firm

Edit `FIRMS` in `seed.py` and run `python seed.py` (safe to re-run — upserts).

```python
# MySQL firm
{
    "firm_id": "acme", "firm_name": "ACME Corp", "description": "...",
    "db_type": "mysql", "db_host": "localhost", "db_port": 3306,
    "db_name": "acme_db", "db_user": "chatbot_ro", "db_password": "...",
    "admin_login": "admin_acme", "admin_password": "...", "admin_display": "ACME Admin",
}

# MongoDB firm
{ "db_type": "mongodb", "mongo_uri": "mongodb+srv://...", "db_name": "acme_db", ... }

# Docs-only (no DB)
{ "db_type": "none", ... }
```

---

## Admin panel workflow

1. **Schema** — paste DB schema JSON (tables, fields, relationships)
2. **Documents** — upload PDFs; chunked and indexed automatically
3. **Roles** — select which tables and documents the role can access (0 or more each)
4. **Users** — create users, assign roles

---

## Schema JSON format

```json
{
  "tables": [
    {
      "name": "employees",
      "description": "All company employees",
      "fields": [
        { "name": "emp_id",    "type": "INT",     "description": "Primary key" },
        { "name": "full_name", "type": "VARCHAR",  "description": "Employee name" },
        { "name": "salary",    "type": "DECIMAL",  "description": "Monthly salary in INR" }
      ]
    }
  ],
  "relationships": [
    { "from_field": "sales.emp_id", "to_field": "employees.emp_id", "type": "FK" }
  ]
}
```

For MongoDB, `tables` = collections and `fields` = document fields — same format.

---

## Key `.env` values

```
RAG_TOP_K=8               # chunks retrieved per query
CHUNK_SIZE=500
CHUNK_OVERLAP=150
MAX_UPLOAD_SIZE_MB=50
```

---

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/firms` | — | Firm list for login |
| POST | `/auth/login` | — | Login → JWT |
| POST | `/admin/schema` | admin | Upload DB schema |
| POST | `/admin/role` | admin | Create / update role |
| GET | `/admin/roles` | admin | List roles |
| POST | `/admin/user` | admin | Create user |
| POST | `/admin/documents/upload` | admin | Upload PDF |
| GET | `/admin/documents` | admin | List documents |
| DELETE | `/admin/documents/{filename}` | admin | Delete document |
| POST | `/chat/query` | user | Ask a question |

---

## Security

- DB credentials (MySQL password, MongoDB URI) encrypted with Fernet before storage
- Schema sent to LLM filtered to the user's allowed tables only
- JWT scoped to `firm_id` — users cannot reach another firm's data
- Qdrant queries hard-filtered by `firm_id` payload — cross-firm data leakage impossible
- Read-only enforced at two levels: DB user permissions + app-level query validator

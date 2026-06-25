import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.platform_db import init_db, close_db
from db.client_db import close_all_pools
from auth.router import router as auth_router
from admin.router import router as admin_router
from chat.router import router as chat_router
from superadmin.router import router as superadmin_router
from rag.vector_store import ensure_collection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await ensure_collection()
    except Exception as exc:
        logger.warning("Qdrant not available at startup — RAG disabled until Qdrant comes online: %s", exc)
    yield
    await close_db()
    await close_all_pools()


app = FastAPI(title="KT_VOX_DEMO", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,       prefix="/auth",       tags=["auth"])
app.include_router(admin_router,      prefix="/admin",      tags=["admin"])
app.include_router(chat_router,       prefix="/chat",       tags=["chat"])
app.include_router(superadmin_router, prefix="/superadmin", tags=["superadmin"])


@app.get("/health")
async def health():
    return {"status": "ok"}

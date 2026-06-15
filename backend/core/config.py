from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Platform DB
    PLATFORM_DB_HOST:     str
    PLATFORM_DB_PORT:     int
    PLATFORM_DB_USER:     str
    PLATFORM_DB_PASSWORD: str
    PLATFORM_DB_NAME:     str

    # JWT
    JWT_SECRET:         str
    JWT_ALGORITHM:      str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # LLM service
    LLM_API_URL:   str
    LLM_API_TOKEN: str
    LLM_MODEL:     str

    # Encryption key for client DB credentials
    ENCRYPTION_KEY: str

    # RAG — Embeddings
    EMBEDDING_MODEL:      str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 1024

    # RAG — Qdrant
    QDRANT_URL:        str           = "http://localhost:6333"
    QDRANT_API_KEY:    Optional[str] = None
    QDRANT_COLLECTION: str           = "kt_vox_documents"

    # RAG — Ingestion
    CHUNK_SIZE:    int = 500
    CHUNK_OVERLAP: int = 150

    # RAG — Retrieval
    RAG_TOP_K:           int   = 8
    RAG_SCORE_THRESHOLD: float = 0.2

    # Upload limit
    MAX_UPLOAD_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()

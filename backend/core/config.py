from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PLATFORM_DB_HOST:     str
    PLATFORM_DB_PORT:     int
    PLATFORM_DB_USER:     str
    PLATFORM_DB_PASSWORD: str
    PLATFORM_DB_NAME:     str

    JWT_SECRET:         str
    JWT_ALGORITHM:      str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    LLM_API_URL:   str
    LLM_API_TOKEN: str
    LLM_MODEL:     str

    ENCRYPTION_KEY: str

    EMBEDDING_API_URL:    str = "https://llm.voxomos.ai/gpt/embedding"
    EMBEDDING_API_TOKEN:  str = ""
    EMBEDDING_MODEL:      str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072

    QDRANT_URL:        str           = "http://localhost:6333"
    QDRANT_API_KEY:    Optional[str] = None
    QDRANT_COLLECTION: str           = "kt_vox_documents"

    CHUNK_SIZE:    int = 500
    CHUNK_OVERLAP: int = 150

    RAG_TOP_K:           int   = 8
    RAG_SCORE_THRESHOLD: float = 0.2

    MAX_UPLOAD_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()

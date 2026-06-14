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

    class Config:
        env_file = ".env"


settings = Settings()

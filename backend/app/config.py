from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/ukproperty"
    DATABASE_URL_SYNC: str = "postgresql://postgres@localhost:5432/ukproperty"
    REDIS_URL: str = "redis://localhost:6379/0"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3001"
    RATE_LIMIT: str = "60/minute"


settings = Settings()

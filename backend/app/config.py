from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/ukproperty"
    DATABASE_URL_SYNC: str = "postgresql://postgres@localhost:5432/ukproperty"
    REDIS_URL: str = "redis://localhost:6379/0"


settings = Settings()

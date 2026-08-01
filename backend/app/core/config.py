"""Application settings, loaded from environment variables."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "AI Life Guardian"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api"

    # Full SQLAlchemy URL. When set (docker-compose does), it wins over the
    # POSTGRES_* parts below, which are the local/bare-metal fallback.
    DATABASE_URL: str | None = None

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "alg_user"
    POSTGRES_PASSWORD: str = "alg_password"
    POSTGRES_DB: str = "alg_db"

    # Comma-separated list. Kept as a string so it survives plain env vars
    # without needing JSON syntax.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Which AIProvider implementation to use. See app.services.ai_service.
    AI_PROVIDER: str = "mock"
    # Artificial delay for the mock provider so the UI loading state is visible.
    MOCK_AI_LATENCY_MS: int = 600

    # No auth yet: tasks created without an explicit user_id land on this
    # shared resident record, which is created on first use.
    DEMO_USER_NAME: str = "社區住戶 (Demo)"

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Normalise the shorthand some providers hand out.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url

        return (
            "postgresql+psycopg2://"
            f"{quote_plus(self.POSTGRES_USER)}:{quote_plus(self.POSTGRES_PASSWORD)}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

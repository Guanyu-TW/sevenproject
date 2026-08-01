"""Application settings, loaded from environment variables."""

from functools import lru_cache
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

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

    # Timestamps come back from PostgreSQL in UTC, so any string the server
    # formats for a resident must be converted to this zone first.
    TIMEZONE: str = "Asia/Taipei"

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

    # Which AIProvider implementation to use: "mock" or "bedrock".
    # See app.services.ai_service.
    AI_PROVIDER: str = "mock"
    # Artificial delay for the mock provider so the UI loading state is visible.
    MOCK_AI_LATENCY_MS: int = 600

    # --- AWS / Amazon Bedrock -------------------------------------------- #
    # Credentials are resolved by boto3's normal chain (env vars, shared
    # credentials file, SSO, IAM role). They are declared here only so the
    # diagnostics script can report whether they are present -- their values
    # are never logged or returned by the API.
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    BEDROCK_MODEL_ID: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_MAX_TOKENS: int = 1500
    BEDROCK_TEMPERATURE: float = 0.0
    BEDROCK_READ_TIMEOUT_SECONDS: int = 45
    BEDROCK_MAX_ATTEMPTS: int = 3

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
    def tzinfo(self) -> ZoneInfo:
        """Display timezone for server-rendered date strings."""
        return ZoneInfo(self.TIMEZONE)

    @property
    def has_static_aws_credentials(self) -> bool:
        """True when explicit keys are configured (never exposes the values)."""
        return bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY)

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

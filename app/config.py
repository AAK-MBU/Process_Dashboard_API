"""Application configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application settings
    APP_NAME: str = "Process Dashboard API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "API for process visualization"
    DEBUG: bool = Field(default=False)

    # API settings
    API_V1_PREFIX: str = "/api/v1"

    # Database settings - Option 1: Full connection string
    DATABASE_URL: str | None = Field(default=None, description="Full database connection URL")

    # Database settings - Option 2: Individual components
    DATABASE_HOST: str = Field(default="localhost")
    DATABASE_PORT: int = Field(default=1433)
    DATABASE_NAME: str = Field(default="process_visualization_db")
    DATABASE_USER: str = Field(default="sa")
    DATABASE_PASSWORD: str = Field(default="YourStrong@Passw0rd")

    # CORS settings
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])

    # Token Authentication
    API_TOKEN: str = Field(
        default="your-secret-token-change-in-production",
        description="Static API token for authentication",
    )


# Global settings instance
settings = Settings()

"""Application configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import __version__


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
    APP_VERSION: str = Field(default=__version__)
    APP_DESCRIPTION: str = "API for process dashboard and monitoring"
    DEBUG: bool = Field(default=False)

    # API settings
    API_V1_PREFIX: str = "/api/v1"

    # Database settings - Full connection string
    DATABASE_URL: str | None = Field(default=None, description="Full database connection URL")

    # Database settings - Individual components
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

    # Rerun adapter settings
    RERUN_ADAPTER_TYPE: str = Field(
        default="automation_server",
        description="Default adapter type for rerunning process steps",
    )

    # Automation server (ATS) settings
    AUTOMATION_SERVER_URL: str | None = Field(
        default=None,
        description="URL of the automation server for rerun operations",
    )

    AUTOMATION_SERVER_TOKEN: str | None = Field(
        default=None,
        description=("Token for authenticating with the automation server for rerun operations"),
    )


# Global settings instance
settings = Settings()

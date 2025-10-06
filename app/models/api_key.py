"""API key models for the application."""

import secrets
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.models.base import TimestampsMixin
from app.utils.datetime_utils import ensure_utc_aware


class ApiKeyBase(SQLModel):
    """Base model for API keys."""

    name: str = Field(max_length=100, description="Human-readable name for the API key")
    description: str | None = Field(
        default=None, max_length=500, description="Optional description"
    )
    is_active: bool = Field(default=True, description="Whether the key is active")
    expires_at: datetime | None = Field(default=None, description="Optional expiration date")
    role: str = Field(default="user", max_length=20, description="Role: 'admin' or 'user'")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_timezone(cls, v: datetime | None) -> datetime | None:
        """Ensure expires_at is timezone-aware (UTC)."""
        return ensure_utc_aware(v)


class ApiKey(ApiKeyBase, TimestampsMixin, table=True):
    """API key database model."""

    __tablename__ = "api_key"

    id: int | None = Field(default=None, primary_key=True)
    key_hash: str = Field(
        max_length=64, index=True, unique=True, description="SHA-256 hash of the API key"
    )
    key_prefix: str = Field(max_length=8, description="First 8 characters for identification")
    last_used_at: datetime | None = Field(default=None, description="Last time this key was used")
    usage_count: int = Field(default=0, description="Number of times this key has been used")

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new secure API key."""
        return f"pd_{secrets.token_urlsafe(32)}"

    @classmethod
    def hash_key(cls, key: str) -> str:
        """Hash an API key for storage."""
        import hashlib

        return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating an API key."""


class ApiKeyPublic(ApiKeyBase):
    """Public schema for API key (without sensitive data)."""

    id: int
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime
    updated_at: datetime


class ApiKeyWithSecret(ApiKeyPublic):
    """API key with the actual secret (only returned once during creation)."""

    key: str

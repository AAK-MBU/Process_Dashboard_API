"""Audit log model for tracking all API requests."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel

from app.models.base import TimestampsMixin


class AuditLog(TimestampsMixin, SQLModel, table=True):
    """Audit log for tracking all API requests."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)

    # User information
    user_email: str | None = Field(
        default=None, max_length=255, index=True, description="User email from x-user header"
    )

    # Request information
    action: str | None = Field(
        default=None, max_length=255, index=True, description="Action from x-action header"
    )
    method: str = Field(max_length=10, description="HTTP method (GET, POST, etc.)")
    path: str = Field(max_length=500, index=True, description="Request path")
    query_params: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON), description="Query parameters"
    )

    # API Key information
    api_key_id: int | None = Field(
        default=None, foreign_key="api_key.id", index=True, description="ID of the API key used"
    )
    api_key_name: str | None = Field(
        default=None, max_length=100, description="Name of the API key used"
    )

    # Response information
    status_code: int | None = Field(
        default=None, index=True, description="HTTP response status code"
    )
    duration_ms: float | None = Field(default=None, description="Request duration in milliseconds")

    # Additional context
    ip_address: str | None = Field(default=None, max_length=45, description="Client IP address")
    user_agent: str | None = Field(default=None, max_length=500, description="User agent string")

    # Error information
    error_message: str | None = Field(
        default=None, max_length=1000, description="Error message if request failed"
    )


class AuditLogPublic(SQLModel):
    """Public schema for audit log entries."""

    id: int
    user_email: str | None
    action: str | None
    method: str
    path: str
    query_params: dict[str, Any] | None
    api_key_name: str | None
    status_code: int | None
    duration_ms: float | None
    ip_address: str | None
    created_at: datetime

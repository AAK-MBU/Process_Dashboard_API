"""Shared base classes and mixins for SQLModel models."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.utils.datetime_utils import utc_now


class TimestampsMixin(SQLModel):
    """Mixin for created_at and updated_at timestamps."""

    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_column_kwargs={"onupdate": utc_now},
    )

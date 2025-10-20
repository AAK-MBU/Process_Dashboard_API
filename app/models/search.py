"""Search-related models and schemas."""

from typing import Any

from pydantic import BaseModel, Field


class MatchedField(BaseModel):
    """Information about a field that matched the search."""

    field: str = Field(..., description="Name of the field that matched")
    value: Any = Field(..., description="Value of the field that matched")

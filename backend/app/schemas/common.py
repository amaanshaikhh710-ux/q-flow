"""Common response schemas for Q-FLOW."""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized top-level API envelope."""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None

"""Health check schemas."""

from typing import Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response payload."""
    status: str = Field(..., description="Overall system health status: healthy, degraded, or unhealthy")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active environment name")
    database_connected: bool = Field(..., description="PostgreSQL connectivity flag")
    details: Dict[str, Any] = Field(default_factory=dict, description="Component level health diagnostics")

"""Pydantic schemas for health check responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Schema for /health endpoint response."""

    status: str = Field(..., description="Overall service status: healthy or degraded")
    app_name: str = Field(..., description="Name of the application")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Deployment environment (development, staging, production)")
    database: str = Field(..., description="PostgreSQL database connectivity status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of the health check")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "app_name": "GoCars API",
                "version": "1.0.0",
                "environment": "development",
                "database": "connected",
                "timestamp": "2026-09-15T18:00:00Z"
            }
        }
    }

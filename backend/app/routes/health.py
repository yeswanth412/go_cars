"""Health check endpoint router."""

from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.health import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Checks the health of the GoCars API service and verifies database connectivity.",
)
def health_check() -> HealthCheckResponse:
    """Verify application runtime and database connectivity."""
    db_connected = check_database_connection()
    overall_status = "healthy" if db_connected else "degraded"
    db_status = "connected" if db_connected else "disconnected"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )

"""Health check endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app import __version__
from app.core.config import settings
from app.core.database import get_db, check_database_health
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application and Database Health Check",
    description="Verifies application runtime state and PostgreSQL connectivity.",
)
def get_health() -> HealthResponse:
    """Returns general health status of the application and database connectivity."""
    db_ok = check_database_health()
    overall_status = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=__version__,
        environment=settings.APP_ENV,
        database_connected=db_ok,
        details={
            "api_prefix": settings.API_V1_PREFIX,
            "debug": settings.DEBUG,
            "database_engine": "PostgreSQL",
        },
    )


@router.get(
    "/health/db",
    summary="Direct Database Connectivity Check",
    description="Performs an active SQL round-trip to verify database session validity.",
)
def check_db_direct(db: Session = Depends(get_db)):
    """Executes a direct SELECT 1 query via the injected SQLAlchemy session."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {
            "status": "healthy",
            "database": "PostgreSQL",
            "query_result": result,
            "connected": True,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "PostgreSQL",
            "error": str(exc),
            "connected": False,
        }

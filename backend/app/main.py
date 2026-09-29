"""Q-FLOW FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from app import __version__
from app.core.config import settings
from app.core.database import check_database_health
from app.core.logging_config import setup_logging
from app.api.v1.router import api_router
from app.schemas.health import HealthResponse

# Initialize production-safe sanitized logging
setup_logging(is_production=settings.is_production)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    db_ok = check_database_health()
    if db_ok:
        logger.info("[Q-FLOW Startup] Connected to PostgreSQL successfully.")
        try:
            from app.core.database import SessionLocal
            from app.services.seed_service import seed_demo_data
            with SessionLocal() as db:
                seed_demo_data(db)
            logger.info("[Q-FLOW Startup] Idempotent demo database seeding verified.")
        except Exception as e:
            logger.exception("[Q-FLOW Startup] Seeding check failed: %s", e)
    else:
        logger.warning("[Q-FLOW Startup Warning] Could not connect to PostgreSQL. Please check DATABASE_URL.")
    yield
    logger.info("[Q-FLOW Shutdown] Terminating application.")


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=(
        "Q-FLOW — Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System. "
        "Production-Hardened Healthcare SaaS Architecture."
    ),
    debug=settings.DEBUG and not settings.is_production,
    lifespan=lifespan,
    docs_url="/docs" if settings.show_docs else None,
    redoc_url="/redoc" if settings.show_docs else None,
    openapi_url="/openapi.json" if settings.show_docs else None,
)

# CORS Middleware configuration
cors_origins = settings.CORS_ORIGINS if (settings.is_production and settings.CORS_ORIGINS != ["*"]) else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com" if settings.is_production else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers for Sanitized Error Responses
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact hospital support if this persists."},
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["Root"],
    summary="Root Health Endpoint",
)
def root_health() -> HealthResponse:
    """Primary health check verifying application startup and database availability."""
    db_ok = check_database_health()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        app_name=settings.APP_NAME,
        version=__version__,
        environment=settings.APP_ENV,
        database_connected=db_ok,
        details={
            "api_v1_prefix": settings.API_V1_PREFIX,
            "database_engine": "PostgreSQL",
        },
    )


@app.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    tags=["Root"],
    summary="Readiness Probe",
)
def readiness_check():
    """Readiness probe for container orchestrators (Kubernetes/Fly/Render/Docker)."""
    db_ok = check_database_health()
    if not db_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database_connected": False},
        )
    return {"status": "ready", "database_connected": True}


@app.get("/", tags=["Root"], summary="Root Information Endpoint")
def root_info():
    """Returns basic service identification and API documentation link."""
    return {
        "project": "Q-FLOW",
        "positioning": "Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System",
        "version": __version__,
        "docs": "/docs" if settings.show_docs else None,
        "health": "/health",
        "api_v1": settings.API_V1_PREFIX,
    }


# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Information
    APP_NAME: str = "Q-FLOW"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DOCS_ENABLED: Optional[bool] = True

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Database & Connection Pooling
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/qflow"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Security & Authentication
    JWT_SECRET: str = "temporary-secret-change-me-in-production-must-be-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Queue Engine & Notification Rules
    ETA_NOTIFICATION_THRESHOLD_MINUTES: int = 10
    DEFAULT_ARRIVAL_BUFFER_MINUTES: int = 15
    TRAVEL_CACHE_TTL_SECONDS: int = 600

    # External Integrations & Provider Abstractions
    TRAVEL_PROVIDER: str = "auto"
    GOOGLE_ROUTES_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None  # Legacy alias for backwards compatibility
    NOTIFICATION_PROVIDER: str = "mock"
    SMS_PROVIDER: str = "mock"  # Backward-compatible alias for NOTIFICATION_PROVIDER
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Application URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def canonical_google_routes_api_key(self) -> Optional[str]:
        """Return the canonical Google Routes API key, falling back to legacy alias."""
        return self.GOOGLE_ROUTES_API_KEY or self.GOOGLE_MAPS_API_KEY

    @property
    def is_production(self) -> bool:
        """Returns True if the application is running in production mode."""
        return self.APP_ENV.lower() == "production"

    @property
    def show_docs(self) -> bool:
        """Returns True if API documentation (Swagger/Redoc) should be exposed."""
        if self.DOCS_ENABLED is not None:
            return self.DOCS_ENABLED
        return not self.is_production


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

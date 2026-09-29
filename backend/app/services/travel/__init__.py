"""Travel service package exporting providers, models, cache, and provider resolver."""

from typing import Optional
from app.core.config import settings
from app.services.travel.base import BaseTravelProvider, TravelEstimateResult, TravelProviderException
from app.services.travel.mock_provider import MockTravelProvider
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.travel.cache import TravelCache

# Global cache instance
travel_cache = TravelCache(ttl_seconds=settings.TRAVEL_CACHE_TTL_SECONDS)


def is_placeholder_api_key(key: Optional[str]) -> bool:
    """Return True if the API key is None, empty, or an obvious placeholder."""
    if not key or not key.strip():
        return True
    k = key.strip().lower()
    return any(p in k for p in ("your-", "your_", "placeholder", "fake", "change-me", "example"))


def get_travel_provider(
    force_mock: bool = False,
    mock_instance: Optional[MockTravelProvider] = None,
) -> BaseTravelProvider:
    """Resolve and return appropriate travel provider.

    Provider Selection Hierarchy:
    1. force_mock is True -> MockTravelProvider (strictly for test isolation)
    2. settings.TRAVEL_PROVIDER == "mock" or missing/placeholder API key -> MockTravelProvider
    3. Valid API key configured -> GoogleRoutesProvider
    """
    if force_mock or getattr(settings, "TRAVEL_PROVIDER", "auto").lower() == "mock":
        return mock_instance or MockTravelProvider()

    api_key = settings.canonical_google_routes_api_key
    if is_placeholder_api_key(api_key):
        return mock_instance or MockTravelProvider()

    return GoogleRoutesProvider(api_key=api_key)


__all__ = [
    "BaseTravelProvider",
    "TravelEstimateResult",
    "TravelProviderException",
    "MockTravelProvider",
    "GoogleRoutesProvider",
    "TravelCache",
    "travel_cache",
    "get_travel_provider",
]

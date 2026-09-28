"""Travel service package exporting providers, models, cache, and provider resolver."""

from typing import Optional
from app.core.config import settings
from app.services.travel.base import BaseTravelProvider, TravelEstimateResult, TravelProviderException
from app.services.travel.mock_provider import MockTravelProvider
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.travel.cache import TravelCache

# Global cache instance
travel_cache = TravelCache(ttl_seconds=settings.TRAVEL_CACHE_TTL_SECONDS)


def get_travel_provider(
    force_mock: bool = False,
    mock_instance: Optional[MockTravelProvider] = None,
) -> BaseTravelProvider:
    """Resolve and return appropriate travel provider.

    Provider Selection Hierarchy:
    1. force_mock is True -> MockTravelProvider (strictly for test isolation)
    2. Default production path -> GoogleRoutesProvider
    """
    if force_mock:
        return mock_instance or MockTravelProvider()

    api_key = settings.canonical_google_routes_api_key
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

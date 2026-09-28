"""API v1 router registry."""

from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, queues, queue_entries, predictions, travel, discovery, historical, notifications, doctors, schedules
from app.websocket import websocket_router

api_router = APIRouter()

# Register core endpoint modules
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(queues.router, prefix="/queues", tags=["queues"])
api_router.include_router(queue_entries.router, prefix="/queue-entries", tags=["queue-entries"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(predictions.router, tags=["predictions"])
api_router.include_router(travel.router, tags=["travel"])
api_router.include_router(discovery.router, tags=["discovery"])
api_router.include_router(historical.router)
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(websocket_router, prefix="/ws", tags=["websocket"])




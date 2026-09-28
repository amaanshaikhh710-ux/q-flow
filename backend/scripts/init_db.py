"""Initialize database schema and seed demo data for Q-FLOW."""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from app.models import (
    Base,
    Hospital,
    Department,
    Doctor,
    OPDSession,
    Queue,
    QueueEntry,
    QueueEvent,
    Consultation,
    Notification,
    PredictionSnapshot,
    ArrivalPlan,
    User,
    DoctorAvailability,
)
from scripts.clean_and_seed import seed


def init_database():
    print(f"Initializing database at: {engine.url}")
    print("Dropping existing tables to ensure schema constraints are up-to-date...")
    Base.metadata.drop_all(bind=engine)

    print("Creating all tables from SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully with uq_queue_date_token_number!")

    print("\nSeeding clean demo data (5 hospitals, 15 doctors, 15 queues)...")
    seed()
    print("\nDatabase initialization complete and ready for use!")


if __name__ == "__main__":
    init_database()

"""Tests for database connectivity and session lifecycle."""

from sqlalchemy import text
from app.core.database import check_database_health, get_db


def test_check_database_health():
    """Verify check_database_health utility performs active ping."""
    assert check_database_health() is True


def test_get_db_session_dependency():
    """Verify get_db dependency yields a valid session and closes cleanly."""
    gen = get_db()
    session = next(gen)
    try:
        result = session.execute(text("SELECT 42")).scalar()
        assert result == 42
    finally:
        try:
            next(gen)
        except StopIteration:
            pass  # Expected clean closure

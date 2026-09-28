"""Tests for Alembic migrations."""

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic import command
from app.core.config import settings
from app.core.database import engine


def test_migration_head_revision():
    """Verify that Alembic script directory has a valid head revision."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()
    assert head_rev is not None
    assert len(head_rev) > 0


def test_database_current_matches_head():
    """Verify that PostgreSQL database is migrated to the latest Alembic revision."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert result == head_rev

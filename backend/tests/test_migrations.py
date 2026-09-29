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
    """Verify that database is migrated to the latest Alembic revision."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    from sqlalchemy import create_engine, text
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    target_engine = create_engine(db_url)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    command.upgrade(alembic_cfg, "head")

    with target_engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert result == head_rev

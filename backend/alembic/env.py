import os
import sys
from logging.config import fileConfig

from alembic import context

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only set sqlalchemy.url from settings if it hasn't been overridden externally
# (e.g., by a test runner that pre-sets the URL via alembic_cfg.set_main_option)
_existing_url = config.get_main_option("sqlalchemy.url")
if not _existing_url or _existing_url == "driver://user:pass@localhost/dbname":
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Set target metadata for autogenerate support
target_metadata = Base.metadata


def _get_url() -> str:
    """Return the effective database URL from config (with %% un-escaped)."""
    url = config.get_main_option("sqlalchemy.url")
    effective_url = url.replace("%%", "%") if url else settings.DATABASE_URL
    if effective_url.startswith("postgres://"):
        effective_url = effective_url.replace("postgres://", "postgresql://", 1)
    return effective_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy import create_engine
    connectable = create_engine(_get_url())

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

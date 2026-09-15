"""
Alembic environment — wires app settings and ORM metadata into migrations.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the app package importable from this script's location (src/backend/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all models so their tables are registered on Base.metadata
import app.models  # noqa: F401 — side-effect import registers all ORM models

from app.database import Base
from app.config import settings

# Alembic Config object
config = context.config

# Override sqlalchemy.url from application settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (uses a live connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

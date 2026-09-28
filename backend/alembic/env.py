"""Alembic environment configuration.

Wired to SQLAlchemy models defined in db/models.py.
The DATABASE_URL environment variable overrides the alembic.ini URL at runtime,
so the same migration scripts work both locally and inside Docker.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to .ini file values
# ---------------------------------------------------------------------------
config = context.config

# Interpret the alembic.ini logging config section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import ORM metadata so autogenerate can compare models to the DB schema
# ---------------------------------------------------------------------------
# The import will resolve once db/models.py is created in Task 2.
# For now we import cautiously so that alembic commands don't fail during
# the scaffolding phase.
try:
    from db.models import Base  # noqa: F401 — needed for autogenerate
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Override connection URL from the DATABASE_URL environment variable
# ---------------------------------------------------------------------------
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    # Check if .env file exists in backend/ or root
    for candidate in [".env", "../.env", "../../.env"]:
        if os.path.exists(candidate):
            with open(candidate, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                        database_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if database_url:
            break

if not database_url:
    # Use absolute path so DB resolves consistently regardless of launch directory
    _env_dir = os.path.dirname(os.path.abspath(__file__))          # alembic/
    _backend_dir = os.path.dirname(_env_dir)                        # backend/
    _db_path = os.path.join(_backend_dir, "cpl2_dev.db")
    database_url = f"sqlite:///{_db_path}"

if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine; calls to
    context.execute() emit the given string to the script output.
    """
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
    """Run migrations in 'online' mode.

    Creates an Engine, associates a connection with the context, and runs
    migrations against the live database.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

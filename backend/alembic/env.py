import os
import sys
from logging.config import fileConfig
from urllib.parse import unquote
from sqlalchemy.engine import make_url
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add backend directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.config import settings
import app.models  # Import models to ensure they are registered on Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from app settings, unquoting if necessary
db_url = make_url(settings.DATABASE_URL)
if db_url.database and ("%" in db_url.database or "%20" in db_url.database):
    db_url = db_url.set(database=unquote(db_url.database))
config.set_main_option("sqlalchemy.url", db_url.render_as_string(hide_password=False))

# add your model's MetaData object here
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


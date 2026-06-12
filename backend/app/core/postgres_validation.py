import os
from collections.abc import Mapping
from pathlib import Path

from alembic.config import Config

from alembic import command

POSTGRES_TEST_DATABASE_URL_ENV = "AGENTOPS_POSTGRES_TEST_DATABASE_URL"


class PostgresValidationError(RuntimeError):
    """Raised when the Postgres migration validation command is misconfigured."""


def postgres_database_url(env: Mapping[str, str] = os.environ) -> str:
    database_url = env.get(POSTGRES_TEST_DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise PostgresValidationError(
            f"Set {POSTGRES_TEST_DATABASE_URL_ENV} to a disposable Postgres database URL."
        )
    if not database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        raise PostgresValidationError(
            f"{POSTGRES_TEST_DATABASE_URL_ENV} must use a Postgres URL."
        )
    return database_url


def alembic_config_for(database_url: str) -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def validate_postgres_migrations(database_url: str | None = None) -> None:
    url = database_url or postgres_database_url()
    command.upgrade(alembic_config_for(url), "head")


if __name__ == "__main__":
    validate_postgres_migrations()

import os

import pytest

from app.core.postgres_validation import (
    POSTGRES_TEST_DATABASE_URL_ENV,
    PostgresValidationError,
    alembic_config_for,
    postgres_database_url,
    validate_postgres_migrations,
)


def test_postgres_validation_requires_database_url() -> None:
    with pytest.raises(PostgresValidationError, match=POSTGRES_TEST_DATABASE_URL_ENV):
        postgres_database_url({})


def test_postgres_validation_rejects_non_postgres_url() -> None:
    with pytest.raises(PostgresValidationError, match="Postgres URL"):
        postgres_database_url({POSTGRES_TEST_DATABASE_URL_ENV: "sqlite+aiosqlite:///tmp.db"})


def test_postgres_validation_builds_alembic_config_for_postgres_url() -> None:
    url = "postgresql+asyncpg://user:pass@localhost:5432/agentops_test"

    config = alembic_config_for(url)

    assert config.get_main_option("sqlalchemy.url") == url


@pytest.mark.skipif(
    not os.environ.get(POSTGRES_TEST_DATABASE_URL_ENV),
    reason=f"{POSTGRES_TEST_DATABASE_URL_ENV} is not configured",
)
def test_postgres_migration_smoke_against_configured_database() -> None:
    validate_postgres_migrations()

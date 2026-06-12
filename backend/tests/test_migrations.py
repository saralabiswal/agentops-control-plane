import pytest
from sqlalchemy import text

from app.core.database import engine
from app.core.migrations import DatabaseMigrationError, assert_database_migrated


@pytest.mark.asyncio
async def test_database_migration_check_accepts_current_head() -> None:
    await assert_database_migrated(engine)


@pytest.mark.asyncio
async def test_database_migration_check_rejects_unstamped_database() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE alembic_version"))

    with pytest.raises(DatabaseMigrationError, match="alembic upgrade head"):
        await assert_database_migrated(engine)

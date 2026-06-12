from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseMigrationError(RuntimeError):
    """Raised when the database schema is not at the required Alembic revision."""


def current_alembic_heads() -> set[str]:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return set(script.get_heads())


async def assert_database_migrated(engine: AsyncEngine) -> None:
    """Fail startup when the database has not been migrated to the current head."""
    required_heads = current_alembic_heads()

    async with engine.connect() as conn:
        current_heads = await conn.run_sync(_database_heads)

    missing = required_heads - current_heads
    if missing:
        required = ", ".join(sorted(required_heads))
        current = ", ".join(sorted(current_heads)) if current_heads else "none"
        raise DatabaseMigrationError(
            "Database schema is not migrated. "
            f"Current revision: {current}. Required revision: {required}. "
            "Run `alembic upgrade head` before starting the app."
        )


def _database_heads(sync_conn: Connection) -> set[str]:
    inspector = inspect(sync_conn)
    if "alembic_version" not in inspector.get_table_names():
        return set()
    rows = sync_conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return {str(row[0]) for row in rows}

from contextlib import redirect_stdout
from io import StringIO

from alembic.config import Config

from alembic import command


def test_initial_migration_compiles_offline():
    output = StringIO()
    with redirect_stdout(output):
        command.upgrade(Config("alembic.ini"), "head", sql=True)
    sql = output.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert sql.count("CREATE TABLE ") == 15  # application tables plus alembic_version
    assert "embedding VECTOR NOT NULL" in sql
    assert "ON DELETE CASCADE" in sql and "ON DELETE RESTRICT" in sql
    assert "ix_chunks_space" in sql


def test_uvicorn_uses_psycopg_compatible_loop():
    import asyncio

    from uvicorn import Config

    factory = Config("app.main:app", loop="app.core.event_loop:selector_loop").get_loop_factory()
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()

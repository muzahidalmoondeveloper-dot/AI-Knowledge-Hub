"""Run after Alembic migrations to install LangGraph's maintained checkpoint schema."""

import asyncio
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings


async def main():
    uri = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(uri) as saver:
        await saver.setup()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main())

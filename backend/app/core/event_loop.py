"""Psycopg's async PostgreSQL checkpointer needs a selector event loop on Windows."""

import asyncio


def selector_loop() -> asyncio.AbstractEventLoop:
    """Uvicorn custom loop factory; avoids deprecated event-loop policies."""
    return asyncio.SelectorEventLoop()

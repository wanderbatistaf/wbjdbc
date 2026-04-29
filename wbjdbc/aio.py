from contextlib import asynccontextmanager
import asyncio
from . import connect_optimized


@asynccontextmanager
async def async_db_conn(**kwargs):
    """Async context manager that wraps connect_optimized in asyncio.to_thread."""
    conn = await asyncio.to_thread(connect_optimized, **kwargs)
    try:
        yield conn
        await asyncio.to_thread(conn.commit)
    except Exception:
        await asyncio.to_thread(conn.rollback)
        raise
    finally:
        await asyncio.to_thread(conn.close)

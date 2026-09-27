"""
Real async support for wbjdbc.

Wraps the sync core (_PooledConn / _DirectCursor from connect_optimized()) so every
JDBC call - not just connect/commit/rollback/close - runs in a worker thread via
asyncio.to_thread(), keeping the event loop free while a query is in flight.
"""
from contextlib import asynccontextmanager
import asyncio
from . import connect_optimized, ensure_jvm_started


class AsyncCursor:
    """Async wrapper around a sync cursor (_DirectCursor or a DB-API-compatible cursor).

    Every JDBC-hitting method is a coroutine that runs the underlying sync call in a
    worker thread via asyncio.to_thread(), so awaiting it does not block the event loop.
    """

    def __init__(self, cursor):
        self._cursor = cursor

    async def execute(self, sql, params=None):
        await asyncio.to_thread(self._cursor.execute, sql, params)
        return self

    async def executemany(self, sql, params_list):
        return await asyncio.to_thread(self._cursor.executemany, sql, params_list)

    async def fetchone(self):
        return await asyncio.to_thread(self._cursor.fetchone)

    async def fetchall(self):
        return await asyncio.to_thread(self._cursor.fetchall)

    async def fetchmany(self, size=1):
        return await asyncio.to_thread(self._cursor.fetchmany, size)

    async def fetchdh(self):
        return await asyncio.to_thread(self._cursor.fetchdh)

    async def fetchdf(self):
        return await asyncio.to_thread(self._cursor.fetchdf)

    async def close(self):
        await asyncio.to_thread(self._cursor.close)

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount


class AsyncConnection:
    """Async wrapper around a sync connection (_PooledConn from connect_optimized())."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self) -> AsyncCursor:
        """Get an async cursor. Synchronous on purpose - it doesn't touch the database."""
        return AsyncCursor(self._conn.cursor())

    async def execute_query(self, sql, params=None):
        return await asyncio.to_thread(self._conn.execute_query, sql, params)

    async def execute_batch(self, sql, params_list, batch_size=None, commit_interval=None):
        return await asyncio.to_thread(
            self._conn.execute_batch, sql, params_list, batch_size, commit_interval
        )

    async def get_table_columns(self, table):
        return await asyncio.to_thread(self._conn.get_table_columns, table)

    async def commit(self):
        await asyncio.to_thread(self._conn.commit)

    async def rollback(self):
        await asyncio.to_thread(self._conn.rollback)

    async def close(self):
        await asyncio.to_thread(self._conn.close)


@asynccontextmanager
async def async_db_conn(**kwargs):
    """Async context manager wrapping connect_optimized() in an AsyncConnection.

    Every method on the yielded connection/cursor (execute, fetchall, commit, ...)
    runs the underlying JDBC call in a worker thread, so nothing in the `async with`
    block blocks the event loop - not just the connect/commit/close at its edges.

    Starts the JVM synchronously (via ensure_jvm_started()) before handing off to
    asyncio.to_thread() - starting it from the worker thread instead can hang the
    process on exit (JPype's shutdown hook doesn't cleanly tear down a JVM started
    from a non-main thread).
    """
    ensure_jvm_started(kwargs.get("db_type"))
    conn = AsyncConnection(await asyncio.to_thread(connect_optimized, **kwargs))
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()

"""Tests for real async support (wbjdbc.aio), using asyncio.run() directly so no
pytest-asyncio dependency is required."""
import asyncio
from unittest.mock import MagicMock, patch

from wbjdbc.aio import AsyncCursor, AsyncConnection, async_db_conn


def test_async_cursor_execute_delegates_to_sync_cursor():
    sync_cursor = MagicMock()

    async def run():
        cur = AsyncCursor(sync_cursor)
        result = await cur.execute("SELECT 1", (1,))
        assert result is cur

    asyncio.run(run())
    sync_cursor.execute.assert_called_once_with("SELECT 1", (1,))


def test_async_cursor_fetchall_returns_sync_result():
    sync_cursor = MagicMock()
    sync_cursor.fetchall.return_value = [(1, "a"), (2, "b")]

    async def run():
        cur = AsyncCursor(sync_cursor)
        return await cur.fetchall()

    rows = asyncio.run(run())
    assert rows == [(1, "a"), (2, "b")]


def test_async_cursor_executemany_returns_rowcount():
    sync_cursor = MagicMock()
    sync_cursor.executemany.return_value = 3

    async def run():
        cur = AsyncCursor(sync_cursor)
        return await cur.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])

    result = asyncio.run(run())
    assert result == 3
    sync_cursor.executemany.assert_called_once_with("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])


def test_async_cursor_description_and_rowcount_are_passthrough_properties():
    sync_cursor = MagicMock()
    sync_cursor.description = (("id", 4, None, None, None, None, None),)
    sync_cursor.rowcount = 5

    cur = AsyncCursor(sync_cursor)
    assert cur.description == sync_cursor.description
    assert cur.rowcount == 5


def test_async_connection_cursor_wraps_sync_cursor():
    sync_conn = MagicMock()
    sync_conn.cursor.return_value = MagicMock()

    conn = AsyncConnection(sync_conn)
    cur = conn.cursor()

    assert isinstance(cur, AsyncCursor)
    sync_conn.cursor.assert_called_once()


def test_async_connection_commit_rollback_close_delegate():
    sync_conn = MagicMock()

    async def run():
        conn = AsyncConnection(sync_conn)
        await conn.commit()
        await conn.rollback()
        await conn.close()

    asyncio.run(run())
    sync_conn.commit.assert_called_once()
    sync_conn.rollback.assert_called_once()
    sync_conn.close.assert_called_once()


def test_async_db_conn_commits_on_success():
    sync_conn = MagicMock()
    ensure_jvm = MagicMock()

    async def run():
        with patch("wbjdbc.aio.connect_optimized", return_value=sync_conn), \
             patch("wbjdbc.aio.ensure_jvm_started", ensure_jvm):
            async with async_db_conn(db_type="informix-sqli") as conn:
                assert isinstance(conn, AsyncConnection)

    asyncio.run(run())
    ensure_jvm.assert_called_once_with("informix-sqli")
    sync_conn.commit.assert_called_once()
    sync_conn.rollback.assert_not_called()
    sync_conn.close.assert_called_once()


def test_async_db_conn_rolls_back_on_exception():
    sync_conn = MagicMock()

    async def run():
        with patch("wbjdbc.aio.connect_optimized", return_value=sync_conn), \
             patch("wbjdbc.aio.ensure_jvm_started"):
            try:
                async with async_db_conn(db_type="informix-sqli"):
                    raise ValueError("boom")
            except ValueError:
                pass

    asyncio.run(run())
    sync_conn.commit.assert_not_called()
    sync_conn.rollback.assert_called_once()
    sync_conn.close.assert_called_once()


def test_async_db_conn_starts_jvm_before_dispatching_to_thread():
    """ensure_jvm_started() must run synchronously (on the caller's thread) before
    connect_optimized() is dispatched via asyncio.to_thread() - starting the JVM from
    the worker thread instead can hang the process on exit."""
    sync_conn = MagicMock()
    call_order = []

    async def run():
        with patch("wbjdbc.aio.connect_optimized", side_effect=lambda **kw: call_order.append("connect") or sync_conn), \
             patch("wbjdbc.aio.ensure_jvm_started", side_effect=lambda db_type: call_order.append("jvm")):
            async with async_db_conn(db_type="informix-sqli"):
                pass

    asyncio.run(run())
    assert call_order == ["jvm", "connect"]

"""Unit tests for ConnectionPool using mock Java connections."""
import threading
import time
import pytest
from unittest.mock import MagicMock, patch


def _mock_jconn(is_valid=True):
    jc = MagicMock()
    jc.isValid.return_value = is_valid
    jc.setAutoCommit = MagicMock()
    jc.commit = MagicMock()
    jc.rollback = MagicMock()
    jc.close = MagicMock()
    return jc


def _build_pool(pool_size=2, max_overflow=2, checkout_timeout=5, **kwargs):
    """Create a ConnectionPool with all Java/JVM calls mocked."""
    from wbjdbc import ConnectionPool, _PooledConn

    mock_jconn = _mock_jconn()
    mock_jpype = MagicMock()
    mock_jpype.JClass = MagicMock()
    mock_jpype.java.sql.DriverManager.getConnection.return_value = mock_jconn

    with patch("wbjdbc.start_jvm"), patch("wbjdbc._get_jpype", return_value=mock_jpype):
        pool = ConnectionPool(
            jdbc_url="jdbc:test://localhost/testdb",
            driver_class="com.example.Driver",
            jars=[],
            user="user",
            password="pass",
            pool_size=pool_size,
            max_overflow=max_overflow,
            checkout_timeout=checkout_timeout,
            **kwargs,
        )

    pool._prewarm_done.wait(timeout=1.0)

    def _patched_new_conn():
        return _PooledConn(mock_jconn, pool)

    pool._new_conn = _patched_new_conn

    with pool._lock:
        pool._idle.clear()
        for _ in range(pool_size):
            pool._idle.append(_patched_new_conn())

    pool._mock_jconn = mock_jconn
    pool._mock_jpype = mock_jpype
    return pool


class TestConnectionPoolStats:
    def test_initial_stats(self):
        pool = _build_pool(pool_size=3, max_overflow=5)
        s = pool.stats()
        assert s["size"] == 8
        assert s["idle"] == 3
        assert s["active"] == 0
        assert s["total_acquired"] == 0
        assert s["total_errors"] == 0
        assert s["avg_wait_ms"] == 0.0
        assert s["max_wait_ms"] == 0.0

    def test_stats_after_one_acquire(self):
        pool = _build_pool(pool_size=2)
        pool.acquire()
        s = pool.stats()
        assert s["active"] == 1
        assert s["idle"] == 1
        assert s["total_acquired"] == 1

    def test_stats_after_acquire_and_return(self):
        pool = _build_pool(pool_size=2)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()
        pool._return(conn)
        s = pool.stats()
        assert s["active"] == 0
        assert s["idle"] == 2
        assert s["total_acquired"] == 1

    def test_stats_tracks_max_wait(self):
        pool = _build_pool(pool_size=2)
        pool.acquire()
        pool.acquire()
        s = pool.stats()
        assert s["max_wait_ms"] >= 0.0
        assert s["avg_wait_ms"] >= 0.0


class TestConnectionValidation:
    def test_is_alive_calls_isvalid_with_timeout_2(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        pool._mock_jconn.isValid.return_value = True

        result = pool._is_alive(conn)

        assert result is True
        pool._mock_jconn.isValid.assert_called_with(2)

    def test_is_alive_false_when_isvalid_false(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        pool._mock_jconn.isValid.return_value = False

        assert pool._is_alive(conn) is False

    def test_is_alive_false_on_exception(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        pool._mock_jconn.isValid.side_effect = Exception("network error")

        assert pool._is_alive(conn) is False

    def test_dead_conn_not_returned_to_idle(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()
        assert pool.stats()["idle"] == 0

        pool._mock_jconn.isValid.return_value = False
        pool._return(conn)
        assert pool.stats()["idle"] == 0

    def test_live_conn_returned_to_idle(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()
        pool._return(conn)
        assert pool.stats()["idle"] == 1


class TestPooledConn:
    def test_acquire_returns_pooled_conn_type(self):
        from wbjdbc import _PooledConn
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        assert isinstance(conn, _PooledConn)

    def test_pooled_conn_cursor_is_direct_cursor(self):
        from wbjdbc import _DirectCursor
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        cur = conn.cursor()
        assert isinstance(cur, _DirectCursor)

    def test_pooled_conn_uses_pool_settings(self):
        pool = _build_pool(pool_size=1, query_timeout_sec=10, slow_query_ms=200, decimal_as_float=True)
        conn = pool.acquire()
        cur = conn.cursor()
        assert cur._query_timeout_sec == 10
        assert cur._slow_query_ms == 200
        assert cur._decimal_as_float is True

    def test_close_returns_to_pool(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()
        assert pool.stats()["active"] == 1
        conn.close()
        assert pool.stats()["active"] == 0

    def test_context_manager_commits_on_success(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        with pool.acquire() as conn:
            pass
        pool._mock_jconn.commit.assert_called_once()

    def test_context_manager_rollbacks_on_exception(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        with pytest.raises(ValueError):
            with pool.acquire() as conn:
                raise ValueError("oops")
        pool._mock_jconn.rollback.assert_called_once()


class TestPoolCapacity:
    def test_checkout_timeout_raises(self):
        pool = _build_pool(pool_size=1, max_overflow=0, checkout_timeout=0.1)
        pool.acquire()
        with pytest.raises(TimeoutError, match="timeout"):
            pool.acquire()

    def test_timeout_increments_total_errors(self):
        pool = _build_pool(pool_size=1, max_overflow=0, checkout_timeout=0.05)
        pool.acquire()
        try:
            pool.acquire()
        except TimeoutError:
            pass
        assert pool.stats()["total_errors"] == 1

    def test_semaphore_released_on_return(self):
        pool = _build_pool(pool_size=1, max_overflow=0)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()
        pool._return(conn)
        conn2 = pool.acquire()
        assert conn2 is not None

    def test_concurrent_acquire_and_return(self):
        pool = _build_pool(pool_size=3, max_overflow=2)
        pool._mock_jconn.isValid.return_value = True
        errors = []

        def worker():
            try:
                conn = pool.acquire()
                time.sleep(0.01)
                conn.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert pool.stats()["active"] == 0


class TestPoolClose:
    def test_close_empties_idle(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool.stats()["idle"] == 0

    def test_close_calls_jconn_close(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool._mock_jconn.close.call_count == 2

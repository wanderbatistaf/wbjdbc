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


class TestConnectionRetry:
    def _build(self, side_effect, max_retries, mock_jpype):
        from wbjdbc import ConnectionPool

        mock_jpype.JClass = MagicMock()
        mock_jpype.java.sql.DriverManager.getConnection.side_effect = side_effect

        pool = ConnectionPool(
            jdbc_url="jdbc:test://localhost/testdb",
            driver_class="com.example.Driver",
            jars=[],
            user="user",
            password="pass",
            pool_size=0,  # no background prewarm consuming side_effect
            max_overflow=5,
            checkout_timeout=5,
            max_retries=max_retries,
            retry_delay=0,
        )
        pool._prewarm_done.wait(timeout=1.0)
        return pool

    def test_succeeds_after_transient_failures(self):
        from wbjdbc import _PooledConn
        from wbjdbc.metrics import get_metrics_collector, reset_metrics

        reset_metrics()
        mock_jconn = _mock_jconn()
        mock_jpype = MagicMock()

        with patch("wbjdbc.start_jvm"), patch("wbjdbc._get_jpype", return_value=mock_jpype):
            pool = self._build([Exception("blip1"), Exception("blip2"), mock_jconn], 3, mock_jpype)
            conn = pool._new_conn()

        assert isinstance(conn, _PooledConn)
        assert mock_jpype.java.sql.DriverManager.getConnection.call_count == 3
        assert get_metrics_collector().get_metrics()["reconnects"] == 1

    def test_exhausts_retries_and_raises(self):
        mock_jpype = MagicMock()

        with patch("wbjdbc.start_jvm"), patch("wbjdbc._get_jpype", return_value=mock_jpype):
            pool = self._build(Exception("db is down"), 2, mock_jpype)
            with pytest.raises(Exception, match="db is down"):
                pool._new_conn()

        assert mock_jpype.java.sql.DriverManager.getConnection.call_count == 3

    def test_no_retry_by_default_fails_immediately(self):
        mock_jpype = MagicMock()

        with patch("wbjdbc.start_jvm"), patch("wbjdbc._get_jpype", return_value=mock_jpype):
            pool = self._build(Exception("nope"), 0, mock_jpype)
            with pytest.raises(Exception, match="nope"):
                pool._new_conn()

        assert mock_jpype.java.sql.DriverManager.getConnection.call_count == 1


class TestSslParams:
    def test_mysql_ssl_verify(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("mysql", "jdbc:mysql://h:3306/db", ssl_verify=True)
        assert url == "jdbc:mysql://h:3306/db?sslMode=VERIFY_CA"

    def test_mysql_ssl_no_verify(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("mysql", "jdbc:mysql://h:3306/db", ssl_verify=False)
        assert url == "jdbc:mysql://h:3306/db?sslMode=REQUIRED"

    def test_postgresql_ssl_verify(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("postgresql", "jdbc:postgresql://h:5432/db", ssl_verify=True)
        assert url == "jdbc:postgresql://h:5432/db?ssl=true&sslmode=verify-full"

    def test_postgresql_ssl_no_verify(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("postgresql", "jdbc:postgresql://h:5432/db", ssl_verify=False)
        assert url == "jdbc:postgresql://h:5432/db?ssl=true&sslmode=require"

    def test_informix_ssl(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params(
            "informix-sqli", "jdbc:informix-sqli://h:1526/db:INFORMIXSERVER=s", ssl_verify=True
        )
        assert url == "jdbc:informix-sqli://h:1526/db:INFORMIXSERVER=s;SECURITY=SSL"

    def test_unknown_db_type_returns_url_unchanged(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("oracle", "jdbc:oracle://h:1521/db", ssl_verify=True)
        assert url == "jdbc:oracle://h:1521/db"

    def test_appends_with_ampersand_when_query_string_already_present(self):
        from wbjdbc import _apply_ssl_params

        url = _apply_ssl_params("mysql", "jdbc:mysql://h:3306/db?useUnicode=true", ssl_verify=True)
        assert url == "jdbc:mysql://h:3306/db?useUnicode=true&sslMode=VERIFY_CA"


class TestEnsureJvmStarted:
    def test_noop_when_jvm_already_started(self):
        from wbjdbc import ensure_jvm_started

        mock_jpype = MagicMock()
        mock_jpype.isJVMStarted.return_value = True
        with patch("wbjdbc._get_jpype", return_value=mock_jpype), \
             patch("wbjdbc.start_jvm") as mock_start:
            ensure_jvm_started("informix-sqli")

        mock_start.assert_not_called()

    def test_starts_jvm_with_resolved_jar_when_not_started(self):
        from wbjdbc import ensure_jvm_started, DEFAULT_DRIVERS

        mock_jpype = MagicMock()
        mock_jpype.isJVMStarted.return_value = False
        with patch("wbjdbc._get_jpype", return_value=mock_jpype), \
             patch("wbjdbc.start_jvm") as mock_start:
            ensure_jvm_started("mysql")

        mock_start.assert_called_once_with([DEFAULT_DRIVERS["mysql"]["jar"]], db_type="mysql")

    def test_accepts_legacy_integer_db_type(self):
        from wbjdbc import ensure_jvm_started, DEFAULT_DRIVERS

        mock_jpype = MagicMock()
        mock_jpype.isJVMStarted.return_value = False
        with patch("wbjdbc._get_jpype", return_value=mock_jpype), \
             patch("wbjdbc.start_jvm") as mock_start:
            ensure_jvm_started(1)  # 1 -> informix-sqli

        mock_start.assert_called_once_with(
            [DEFAULT_DRIVERS["informix-sqli"]["jar"]], db_type="informix-sqli"
        )

    def test_unknown_db_type_starts_jvm_without_extra_jar(self):
        from wbjdbc import ensure_jvm_started

        mock_jpype = MagicMock()
        mock_jpype.isJVMStarted.return_value = False
        with patch("wbjdbc._get_jpype", return_value=mock_jpype), \
             patch("wbjdbc.start_jvm") as mock_start:
            ensure_jvm_started(None)

        mock_start.assert_called_once_with(None, db_type=None)


class TestGetTableColumns:
    def _rs_for_columns(self, rows):
        rs = MagicMock()
        row_iter = iter(rows)
        current = [None]

        def _next():
            try:
                current[0] = next(row_iter)
                return True
            except StopIteration:
                return False

        rs.next.side_effect = _next
        rs.getString.side_effect = lambda col: current[0][col]
        rs.getInt.side_effect = lambda col: current[0][col]
        return rs

    def test_returns_columns_and_caches(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        conn._database = "testdb"

        rows = [
            {"COLUMN_NAME": "id", "DATA_TYPE": 4, "TYPE_NAME": "INTEGER", "COLUMN_SIZE": 10, "NULLABLE": 0},
        ]
        rs = self._rs_for_columns(rows)
        meta = MagicMock()
        meta.getColumns.return_value = rs
        conn._jc.getMetaData.return_value = meta

        columns = conn.get_table_columns("users")

        assert columns == [
            {"name": "id", "type": 4, "type_name": "INTEGER", "size": 10, "nullable": False}
        ]
        assert conn._jc.getMetaData.call_count == 1

        # Second call should be served from the schema cache, not the JDBC metadata API.
        columns_again = conn.get_table_columns("users")
        assert columns_again == columns
        assert conn._jc.getMetaData.call_count == 1

    def test_returns_empty_list_on_error(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        conn._database = "testdb2"
        conn._jc.getMetaData.side_effect = Exception("boom")

        assert conn.get_table_columns("orders") == []


class TestExecuteBatchChunking:
    def test_no_batch_size_is_single_executemany_no_commit(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()

        with patch.object(conn._jc, "prepareStatement") as prep:
            pstmt = MagicMock()
            pstmt.executeBatch.return_value = [1, 1]
            prep.return_value = pstmt

            conn.execute_batch("INSERT INTO t VALUES (?)", [(1,), (2,)])

        pool._mock_jconn.commit.assert_not_called()

    def test_batch_size_chunks_and_commits(self):
        pool = _build_pool(pool_size=1)
        pool._mock_jconn.isValid.return_value = True
        conn = pool.acquire()

        with patch.object(conn._jc, "prepareStatement") as prep:
            pstmt = MagicMock()
            pstmt.executeBatch.return_value = [1]
            prep.return_value = pstmt

            total = conn.execute_batch(
                "INSERT INTO t VALUES (?)", [(1,), (2,), (3,)], batch_size=1, commit_interval=1
            )

        assert total == 3
        assert pool._mock_jconn.commit.call_count >= 3


class TestPoolClose:
    def test_close_empties_idle(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool.stats()["idle"] == 0

    def test_close_calls_jconn_close(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool._mock_jconn.close.call_count == 2

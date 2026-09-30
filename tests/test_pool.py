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


class TestDriverJarOverride:
    def test_missing_driver_jar_raises_value_error(self):
        from wbjdbc import connect_optimized

        with pytest.raises(ValueError, match="driver_jar not found"):
            connect_optimized(
                db_type="postgresql", host="h", database="d", user="u", password="p",
                driver_jar="/no/such/driver.jar",
            )

    def test_valid_driver_jar_used_instead_of_bundled(self, tmp_path):
        from wbjdbc import connect_optimized

        custom_jar = tmp_path / "custom-postgres.jar"
        custom_jar.write_bytes(b"not a real jar, just needs to exist on disk")

        with patch("wbjdbc.start_jvm") as mock_start_jvm, \
             patch("wbjdbc._get_jpype") as mock_get_jpype:
            mock_get_jpype.return_value = MagicMock()
            connect_optimized(
                db_type="postgresql", host="h", database="d", user="u", password="p",
                driver_jar=str(custom_jar), use_pool=False,
            )

        mock_start_jvm.assert_called_once_with([str(custom_jar)], db_type="postgresql")


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


class TestGetProcedureSource:
    def _rs_for_rows(self, cols, rows):
        rs = MagicMock()
        meta = MagicMock()
        meta.getColumnCount.return_value = len(cols)
        meta.getColumnLabel.side_effect = lambda i: cols[i - 1]
        meta.getColumnType.return_value = 12
        rs.getMetaData.return_value = meta
        row_iter = iter(rows)
        current = [None]

        def _next():
            try:
                current[0] = next(row_iter)
                return True
            except StopIteration:
                return False

        rs.next.side_effect = _next
        rs.getObject.side_effect = lambda i: current[0][i - 1]
        rs.getString.side_effect = lambda i: current[0][i - 1]
        return rs

    def _id_rs(self, procid):
        """Mock ResultSet for the procid-resolution query (SELECT FIRST 1 procid ...).
        procid=None means no matching row (procedure/owner doesn't exist)."""
        rs = MagicMock()
        remaining = [procid is not None]

        def _next():
            if remaining[0]:
                remaining[0] = False
                return True
            return False

        rs.next.side_effect = _next
        rs.getInt.return_value = procid
        return rs

    def _informix_pstmts(self, procid, data_rows):
        """Two prepareStatement() calls in order: resolve procid, then read chunks."""
        id_pstmt = MagicMock()
        id_pstmt.executeQuery.return_value = self._id_rs(procid)
        data_pstmt = MagicMock()
        data_pstmt.executeQuery.return_value = self._rs_for_rows(["data"], data_rows)
        return [id_pstmt, data_pstmt]

    def _pool_conn(self, db_type):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        conn._db_type = db_type
        conn._database = "testdb"
        return conn

    def test_informix_concatenates_chunks_in_order(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            101, [("CREATE PROCEDURE p()\n",), ("  RETURN 1;\nEND PROCEDURE",)]
        )

        source = conn.get_procedure_source("p")

        assert source == "CREATE PROCEDURE p()\n  RETURN 1;\nEND PROCEDURE"

    def test_informix_not_found_returns_none(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        id_pstmt = MagicMock()
        id_pstmt.executeQuery.return_value = self._id_rs(None)
        conn._jc.prepareStatement.return_value = id_pstmt

        assert conn.get_procedure_source("does_not_exist") is None
        # procid never resolved - the sysprocbody query must not even run.
        conn._jc.prepareStatement.assert_called_once()

    def test_mysql_extracts_create_procedure_column(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("mysql")
        row = ("p", "", "CREATE PROCEDURE p() BEGIN SELECT 1; END", "utf8mb4", "x", "y")
        rs = self._rs_for_rows(["Procedure", "sql_mode", "Create Procedure", "a", "b", "c"], [row])
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        source = conn.get_procedure_source("p")

        assert source == "CREATE PROCEDURE p() BEGIN SELECT 1; END"
        conn._jc.prepareStatement.assert_called_once_with("SHOW CREATE PROCEDURE p")

    def test_postgresql_returns_functiondef(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("postgresql")
        rs = self._rs_for_rows(["pg_get_functiondef"], [("CREATE PROCEDURE p() LANGUAGE plpgsql AS $$ BEGIN END $$",)])
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        source = conn.get_procedure_source("p")

        assert "CREATE PROCEDURE p()" in source

    def test_postgresql_not_found_returns_none(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("postgresql")
        rs = self._rs_for_rows(["pg_get_functiondef"], [])
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        assert conn.get_procedure_source("does_not_exist") is None

    def test_unsupported_db_type_raises_not_supported_error(self):
        from wbjdbc.exceptions import NotSupportedError

        conn = self._pool_conn("oracle")
        with pytest.raises(NotSupportedError):
            conn.get_procedure_source("p")

    def test_invalid_proc_name_raises_value_error(self):
        conn = self._pool_conn("mysql")
        with pytest.raises(ValueError):
            conn.get_procedure_source("p(); DROP TABLE x; --")

    def test_result_is_cached(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            101, [("CREATE PROCEDURE p() RETURN 1; END PROCEDURE",)]
        )

        first = conn.get_procedure_source("p")
        second = conn.get_procedure_source("p")

        assert first == second
        assert conn._jc.prepareStatement.call_count == 2  # id + data, once - not four

    def test_informix_pins_a_single_procid_never_blends_two_procedures(self):
        # Two different procedures can share a name in Informix (different owners).
        # get_procedure_source must never interleave their sysprocbody chunks into
        # one garbled body - procid is resolved to one specific value before any
        # sysprocbody row is read, so this fixture returning rows for only ONE
        # procid, regardless of how many sysprocedures rows match procname, proves
        # the query scopes correctly rather than relying on mocking away the
        # ambiguity.
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        id_pstmt, data_pstmt = self._informix_pstmts(
            101, [("CREATE PROCEDURE p() RETURN 1; END PROCEDURE",)]
        )
        conn._jc.prepareStatement.side_effect = [id_pstmt, data_pstmt]

        source = conn.get_procedure_source("p")

        assert source == "CREATE PROCEDURE p() RETURN 1; END PROCEDURE"
        id_sql = conn._jc.prepareStatement.call_args_list[0][0][0]
        data_sql = conn._jc.prepareStatement.call_args_list[1][0][0]
        assert "SELECT FIRST 1 procid" in id_sql and "AND owner = ?" not in id_sql
        assert "WHERE procid = ?" in data_sql
        data_pstmt.setInt.assert_called_once_with(1, 101)

    def test_informix_owner_disambiguates_and_is_bound(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        id_pstmt, data_pstmt = self._informix_pstmts(
            202, [("CREATE PROCEDURE p() RETURN 2; END PROCEDURE",)]
        )
        conn._jc.prepareStatement.side_effect = [id_pstmt, data_pstmt]

        source = conn.get_procedure_source("p", owner="alice")

        assert source == "CREATE PROCEDURE p() RETURN 2; END PROCEDURE"
        id_sql = conn._jc.prepareStatement.call_args_list[0][0][0]
        assert "AND owner = ?" in id_sql
        id_pstmt.setString.assert_any_call(2, "alice")

    def test_informix_owner_and_no_owner_cache_separately(self):
        # Same proc_name, different owner= arg - must not collide in the schema
        # cache and return the wrong procedure's source for the other.
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")

        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            101, [("CREATE PROCEDURE p() RETURN 1; END PROCEDURE",)]
        )
        unqualified = conn.get_procedure_source("p")

        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            202, [("CREATE PROCEDURE p() RETURN 2; END PROCEDURE",)]
        )
        owned = conn.get_procedure_source("p", owner="alice")

        assert unqualified != owned
        assert conn._jc.prepareStatement.call_count == 4  # 2 id+data round trips

    def test_invalid_owner_raises_value_error(self):
        conn = self._pool_conn("informix-sqli")
        with pytest.raises(ValueError):
            conn.get_procedure_source("p", owner="alice; DROP TABLE x; --")

    def test_informix_numargs_disambiguates_and_is_bound(self):
        # Same name, same owner, different arity - real overloading (not just an
        # owner clash). Without numargs, the lowest procid wins; with it, the
        # matching overload is pinned down explicitly.
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        id_pstmt, data_pstmt = self._informix_pstmts(
            579, [("CREATE PROCEDURE p(a INT, b INT) RETURN a+b; END PROCEDURE",)]
        )
        conn._jc.prepareStatement.side_effect = [id_pstmt, data_pstmt]

        source = conn.get_procedure_source("p", numargs=2)

        assert source == "CREATE PROCEDURE p(a INT, b INT) RETURN a+b; END PROCEDURE"
        id_sql = conn._jc.prepareStatement.call_args_list[0][0][0]
        assert "AND numargs = ?" in id_sql and "AND owner = ?" not in id_sql
        id_pstmt.setInt.assert_called_once_with(2, 2)

    def test_informix_owner_and_numargs_combined_bind_positions(self):
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")
        id_pstmt, data_pstmt = self._informix_pstmts(
            579, [("CREATE PROCEDURE p(a INT, b INT) RETURN a+b; END PROCEDURE",)]
        )
        conn._jc.prepareStatement.side_effect = [id_pstmt, data_pstmt]

        conn.get_procedure_source("p", owner="alice", numargs=2)

        id_sql = conn._jc.prepareStatement.call_args_list[0][0][0]
        assert "AND owner = ?" in id_sql and "AND numargs = ?" in id_sql
        id_pstmt.setString.assert_any_call(2, "alice")
        id_pstmt.setInt.assert_called_once_with(3, 2)

    def test_numargs_disambiguates_cache_too(self):
        # Two overloads of "p", same owner - must not collide in the schema cache.
        from wbjdbc.cache import reset_cache

        reset_cache()
        conn = self._pool_conn("informix-sqli")

        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            578, [("CREATE PROCEDURE p(a INT) RETURN a; END PROCEDURE",)]
        )
        one_arg = conn.get_procedure_source("p", numargs=1)

        conn._jc.prepareStatement.side_effect = self._informix_pstmts(
            579, [("CREATE PROCEDURE p(a INT, b INT) RETURN a+b; END PROCEDURE",)]
        )
        two_args = conn.get_procedure_source("p", numargs=2)

        assert one_arg != two_args
        assert conn._jc.prepareStatement.call_count == 4

    def test_invalid_numargs_raises_value_error(self):
        conn = self._pool_conn("informix-sqli")
        with pytest.raises(ValueError):
            conn.get_procedure_source("p", numargs=-1)
        with pytest.raises(ValueError):
            conn.get_procedure_source("p", numargs="2")


class TestListProcedures:
    def _rs_for_rows(self, cols, rows):
        rs = MagicMock()
        meta = MagicMock()
        meta.getColumnCount.return_value = len(cols)
        meta.getColumnLabel.side_effect = lambda i: cols[i - 1]
        meta.getColumnType.return_value = 12
        rs.getMetaData.return_value = meta
        row_iter = iter(rows)
        current = [None]

        def _next():
            try:
                current[0] = next(row_iter)
                return True
            except StopIteration:
                return False

        rs.next.side_effect = _next
        rs.getObject.side_effect = lambda i: current[0][i - 1]
        return rs

    def _pool_conn(self, db_type):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        conn._db_type = db_type
        conn._database = "testdb"
        return conn

    def test_informix_returns_raw_rows_no_filtering(self):
        # No system-owner/overload filtering here by design - that's left to the
        # caller (see OPTIMIZATION_GUIDE.md). Two rows sharing a name (an overload)
        # and a row owned by "informix" must both come through untouched.
        conn = self._pool_conn("informix-sqli")
        rs = self._rs_for_rows(
            ["procname", "owner", "numargs", "isproc"],
            [
                ("p", "alice", 1, "f"),
                ("p", "alice", 2, "f"),
                ("install_jar", "sqlj", 1, "t"),
            ],
        )
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        procs = conn.list_procedures()

        assert procs == [
            {"name": "p", "owner": "alice", "numargs": 1, "is_function": True},
            {"name": "p", "owner": "alice", "numargs": 2, "is_function": True},
            {"name": "install_jar", "owner": "sqlj", "numargs": 1, "is_function": False},
        ]

    def test_mysql_maps_routine_type_to_is_function(self):
        conn = self._pool_conn("mysql")
        rs = self._rs_for_rows(
            ["ROUTINE_NAME", "ROUTINE_SCHEMA", "ROUTINE_TYPE"],
            [("pr_x", "testdb", "PROCEDURE"), ("fn_x", "testdb", "FUNCTION")],
        )
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        procs = conn.list_procedures()

        assert procs == [
            {"name": "pr_x", "owner": "testdb", "numargs": None, "is_function": False},
            {"name": "fn_x", "owner": "testdb", "numargs": None, "is_function": True},
        ]

    def test_postgresql_maps_prokind_to_is_function(self):
        conn = self._pool_conn("postgresql")
        rs = self._rs_for_rows(
            ["proname", "nspname", "pronargs", "prokind"],
            [("fn_x", "public", 2, "f"), ("pr_x", "public", 0, "p")],
        )
        pstmt = MagicMock()
        pstmt.executeQuery.return_value = rs
        conn._jc.prepareStatement.return_value = pstmt

        procs = conn.list_procedures()

        assert procs == [
            {"name": "fn_x", "owner": "public", "numargs": 2, "is_function": True},
            {"name": "pr_x", "owner": "public", "numargs": 0, "is_function": False},
        ]

    def test_unsupported_db_type_raises_not_supported_error(self):
        from wbjdbc.exceptions import NotSupportedError

        conn = self._pool_conn("oracle")
        with pytest.raises(NotSupportedError):
            conn.list_procedures()


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


class TestSavepoints:
    def test_savepoint_without_name(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()
        conn._jc.setSavepoint.return_value = sp

        result = conn.savepoint()

        conn._jc.setSavepoint.assert_called_once_with()
        assert result is sp

    def test_savepoint_with_name(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()
        conn._jc.setSavepoint.return_value = sp

        result = conn.savepoint("sp1")

        conn._jc.setSavepoint.assert_called_once_with("sp1")
        assert result is sp

    def test_rollback_to_calls_connection_rollback_with_savepoint(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()

        conn.rollback_to(sp)

        conn._jc.rollback.assert_called_once_with(sp)

    def test_release_savepoint(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()

        conn.release_savepoint(sp)

        conn._jc.releaseSavepoint.assert_called_once_with(sp)

    def test_savepoint_scope_releases_on_success(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()
        conn._jc.setSavepoint.return_value = sp

        with conn.savepoint_scope("sp1"):
            pass

        conn._jc.releaseSavepoint.assert_called_once_with(sp)
        conn._jc.rollback.assert_not_called()

    def test_savepoint_scope_rolls_back_on_exception(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()
        sp = MagicMock()
        conn._jc.setSavepoint.return_value = sp

        with pytest.raises(ValueError):
            with conn.savepoint_scope("sp1"):
                raise ValueError("boom")

        conn._jc.rollback.assert_called_once_with(sp)
        conn._jc.releaseSavepoint.assert_not_called()


class TestPooledConnCallproc:
    def test_delegates_to_cursor_callproc(self):
        pool = _build_pool(pool_size=1)
        conn = pool.acquire()

        with patch.object(conn._jc, "prepareCall") as prep:
            cstmt = MagicMock()
            cstmt.execute.return_value = False
            cstmt.getUpdateCount.return_value = 0
            cstmt.getObject.return_value = 5
            prep.return_value = cstmt

            result = conn.callproc("my_proc", [1], out_types={1: 4})

        prep.assert_called_once_with("{call my_proc(?)}")
        assert result == [5]


class TestPoolClose:
    def test_close_empties_idle(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool.stats()["idle"] == 0

    def test_close_calls_jconn_close(self):
        pool = _build_pool(pool_size=2)
        pool.close()
        assert pool._mock_jconn.close.call_count == 2

"""Unit tests for _DirectCursor using mock Java objects."""
import sys
import decimal
import datetime
import pytest
from unittest.mock import MagicMock, patch

from wbjdbc._types import _rewrite_named, _j2p, _set_param


def _make_meta(cols):
    meta = MagicMock()
    meta.getColumnCount.return_value = len(cols)
    meta.getColumnLabel.side_effect = lambda i: cols[i - 1]
    meta.getColumnType.return_value = 12
    return meta


def _make_rs(meta, rows):
    rs = MagicMock()
    rs.getMetaData.return_value = meta
    row_iter = iter(rows)
    current = [None]

    def _next():
        try:
            current[0] = next(row_iter)
            return True
        except StopIteration:
            return False

    rs.next.side_effect = lambda: _next()
    rs.getObject.side_effect = lambda i: current[0][i - 1]
    return rs


def _make_java_conn(rs=None, update_count=0, batch_counts=None):
    jc = MagicMock()
    pstmt = MagicMock()
    if rs is not None:
        pstmt.executeQuery.return_value = rs
    else:
        pstmt.executeUpdate.return_value = update_count
        pstmt.executeBatch.return_value = batch_counts or []
    jc.prepareStatement.return_value = pstmt
    return jc, pstmt


def _cursor(jc, query_timeout_sec=5, slow_query_ms=999999):
    from wbjdbc import _DirectCursor
    return _DirectCursor(jc, decimal_as_float=False,
                         query_timeout_sec=query_timeout_sec,
                         slow_query_ms=slow_query_ms)


class TestDirectCursorSelect:
    def test_fetchall_returns_rows(self):
        meta = _make_meta(["id", "name"])
        rs = _make_rs(meta, [(1, "Alice"), (2, "Bob")])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT id, name FROM users")

        assert cur.rowcount == 2
        assert cur.fetchall() == [(1, "Alice"), (2, "Bob")]

    def test_description_set_after_select(self):
        meta = _make_meta(["x"])
        rs = _make_rs(meta, [(10,)])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT x FROM t")

        assert cur.description is not None
        assert cur.description[0][0] == "x"

    def test_fetchone_returns_first_row(self):
        meta = _make_meta(["v"])
        rs = _make_rs(meta, [(42,), (99,)])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT v FROM t")

        assert cur.fetchone() == (42,)
        assert cur.fetchone() == (99,)
        assert cur.fetchone() is None

    def test_fetchmany_returns_slice(self):
        meta = _make_meta(["n"])
        rs = _make_rs(meta, [(1,), (2,), (3,)])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT n FROM t")

        assert cur.fetchmany(2) == [(1,), (2,)]
        assert cur.fetchmany(2) == [(3,)]

    def test_fetchdh_returns_list_of_dicts(self):
        meta = _make_meta(["id", "val"])
        rs = _make_rs(meta, [(1, "a"), (2, "b")])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT id, val FROM t")

        assert cur.fetchdh() == [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]


class TestDirectCursorDML:
    def test_insert_uses_executeupdate(self):
        jc, pstmt = _make_java_conn(update_count=1)

        cur = _cursor(jc)
        cur.execute("INSERT INTO t (a) VALUES (?)", (99,))

        pstmt.executeUpdate.assert_called_once()
        assert cur.rowcount == 1
        assert cur.description is None

    def test_update_uses_executeupdate(self):
        jc, pstmt = _make_java_conn(update_count=3)

        cur = _cursor(jc)
        cur.execute("UPDATE t SET a=? WHERE b=?", (1, 2))

        pstmt.executeUpdate.assert_called_once()
        assert cur.rowcount == 3

    def test_delete_uses_executeupdate(self):
        jc, pstmt = _make_java_conn(update_count=5)

        cur = _cursor(jc)
        cur.execute("DELETE FROM t WHERE id=?", (7,))

        assert cur.rowcount == 5

    def test_query_timeout_is_set(self):
        meta = _make_meta(["v"])
        rs = _make_rs(meta, [])
        jc, pstmt = _make_java_conn(rs=rs)

        cur = _cursor(jc, query_timeout_sec=15)
        cur.execute("SELECT v FROM t")

        pstmt.setQueryTimeout.assert_called_once_with(15)

    def test_pstmt_cached_not_closed_after_execute(self):
        jc, pstmt = _make_java_conn(update_count=0)

        cur = _cursor(jc)
        cur.execute("DELETE FROM t WHERE 1=0")

        pstmt.close.assert_not_called()


class TestExecuteMany:
    def test_addbatch_called_n_times(self):
        jc, pstmt = _make_java_conn()
        pstmt.executeBatch.return_value = [1, 1, 1]

        cur = _cursor(jc)
        cur.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])

        assert pstmt.addBatch.call_count == 3

    def test_executebatch_called_once(self):
        jc, pstmt = _make_java_conn()
        pstmt.executeBatch.return_value = [1, 1, 1]

        cur = _cursor(jc)
        cur.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])

        pstmt.executeBatch.assert_called_once()

    def test_rowcount_sums_batch_counts(self):
        jc, pstmt = _make_java_conn()
        pstmt.executeBatch.return_value = [1, 1, 2]

        cur = _cursor(jc)
        result = cur.executemany("INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])

        assert result == 4
        assert cur.rowcount == 4

    def test_single_row_batch(self):
        jc, pstmt = _make_java_conn()
        pstmt.executeBatch.return_value = [1]

        cur = _cursor(jc)
        cur.executemany("INSERT INTO t VALUES (?)", [(42,)])

        pstmt.addBatch.assert_called_once()
        pstmt.executeBatch.assert_called_once()

    def test_executemany_pstmt_cached_not_closed(self):
        jc, pstmt = _make_java_conn()
        pstmt.executeBatch.return_value = [1]

        cur = _cursor(jc)
        cur.executemany("INSERT INTO t VALUES (?)", [(1,)])

        pstmt.close.assert_not_called()


class TestStatementCache:
    def test_same_sql_reuses_pstmt(self):
        jc = MagicMock()
        pstmt = MagicMock()
        pstmt.executeUpdate.return_value = 1
        jc.prepareStatement.return_value = pstmt

        from collections import OrderedDict
        cache = OrderedDict()
        from wbjdbc import _DirectCursor
        cur = _DirectCursor(jc, stmt_cache=cache, query_timeout_sec=0, slow_query_ms=999999)

        cur.execute("UPDATE t SET a=1")
        cur.execute("UPDATE t SET a=1")

        assert jc.prepareStatement.call_count == 1

    def test_different_sql_creates_new_pstmt(self):
        jc = MagicMock()
        jc.prepareStatement.side_effect = lambda s: MagicMock(executeUpdate=MagicMock(return_value=1))

        from collections import OrderedDict
        from wbjdbc import _DirectCursor
        cur = _DirectCursor(jc, stmt_cache=OrderedDict(), query_timeout_sec=0, slow_query_ms=999999)

        cur.execute("UPDATE t SET a=1")
        cur.execute("UPDATE t SET b=2")

        assert jc.prepareStatement.call_count == 2

    def test_cache_eviction_closes_oldest_pstmt(self):
        from collections import OrderedDict
        from wbjdbc import _DirectCursor, _STMT_CACHE_SIZE

        jc = MagicMock()
        pstmts = {}

        def make_pstmt(sql):
            m = MagicMock()
            m.executeUpdate.return_value = 1
            pstmts[sql] = m
            return m

        jc.prepareStatement.side_effect = make_pstmt

        cache = OrderedDict()
        cur = _DirectCursor(jc, stmt_cache=cache, query_timeout_sec=0, slow_query_ms=999999)

        sqls = [f"UPDATE t SET col{i}=?" for i in range(_STMT_CACHE_SIZE + 1)]
        for sql in sqls:
            cur.execute(sql)

        first_sql = sqls[0]
        pstmts[first_sql].close.assert_called_once()
        assert first_sql not in cache

    def test_clearparameters_called_on_reuse(self):
        jc = MagicMock()
        pstmt = MagicMock()
        pstmt.executeUpdate.return_value = 1
        jc.prepareStatement.return_value = pstmt

        from collections import OrderedDict
        from wbjdbc import _DirectCursor
        cur = _DirectCursor(jc, stmt_cache=OrderedDict(), query_timeout_sec=0, slow_query_ms=999999)

        cur.execute("UPDATE t SET a=?", (1,))
        cur.execute("UPDATE t SET a=?", (2,))

        assert pstmt.clearParameters.call_count == 2


class TestNamedParams:
    def test_rewrite_named_basic(self):
        sql = "SELECT * FROM t WHERE zone = :zone AND bay = :bay"
        new_sql, params = _rewrite_named(sql, {"zone": "A", "bay": 1})
        assert new_sql == "SELECT * FROM t WHERE zone = ? AND bay = ?"
        assert params == ["A", 1]

    def test_rewrite_preserves_order(self):
        sql = "INSERT INTO t (a, b, c) VALUES (:c, :a, :b)"
        new_sql, params = _rewrite_named(sql, {"a": 1, "b": 2, "c": 3})
        assert new_sql == "INSERT INTO t (a, b, c) VALUES (?, ?, ?)"
        assert params == [3, 1, 2]

    def test_execute_with_dict_params_rewrites(self):
        meta = _make_meta(["v"])
        rs = _make_rs(meta, [(5,)])
        jc, pstmt = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT v FROM t WHERE id = :id", {"id": 1})

        assert cur.rowcount == 1


class TestFetchDf:
    def test_fetchdf_returns_dataframe(self):
        pd = pytest.importorskip("pandas")
        meta = _make_meta(["a", "b"])
        rs = _make_rs(meta, [(1, "x"), (2, "y")])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT a, b FROM t")
        df = cur.fetchdf()

        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2
        assert df.iloc[0]["a"] == 1

    def test_fetchdf_raises_without_pandas(self):
        meta = _make_meta(["v"])
        rs = _make_rs(meta, [(1,)])
        jc, _ = _make_java_conn(rs=rs)

        cur = _cursor(jc)
        cur.execute("SELECT v FROM t")

        with patch.dict(sys.modules, {"pandas": None}):
            with pytest.raises(ImportError, match="pandas"):
                cur.fetchdf()


class TestJ2P:
    def test_none_returns_none(self):
        assert _j2p(None) is None

    def test_python_native_passthrough(self):
        assert _j2p(42) == 42
        assert _j2p("hello") == "hello"
        assert _j2p(3.14) == 3.14

    def test_bigdecimal_to_decimal(self):
        class FakeBigDecimal:
            def getClass(self):
                m = MagicMock()
                m.getName.return_value = "java.math.BigDecimal"
                return m
            def __str__(self):
                return "123.45"

        result = _j2p(FakeBigDecimal())
        assert result == decimal.Decimal("123.45")

    def test_bigdecimal_decimal_as_float(self):
        class FakeBigDecimal:
            def getClass(self):
                m = MagicMock()
                m.getName.return_value = "java.math.BigDecimal"
                return m
            def __str__(self):
                return "123.45"

        result = _j2p(FakeBigDecimal(), decimal_as_float=True)
        assert result == 123.45
        assert isinstance(result, float)

    def test_sql_date_to_python_date(self):
        ld = MagicMock()
        ld.getYear.return_value = 2024
        ld.getMonthValue.return_value = 6
        ld.getDayOfMonth.return_value = 15

        class FakeDate:
            def getClass(self):
                m = MagicMock()
                m.getName.return_value = "java.sql.Date"
                return m
            def toLocalDate(self):
                return ld

        result = _j2p(FakeDate())
        assert result == datetime.date(2024, 6, 15)

    def test_sql_timestamp_to_python_datetime(self):
        ldt = MagicMock()
        ldt.getYear.return_value = 2024
        ldt.getMonthValue.return_value = 3
        ldt.getDayOfMonth.return_value = 10
        ldt.getHour.return_value = 12
        ldt.getMinute.return_value = 30
        ldt.getSecond.return_value = 45
        ldt.getNano.return_value = 0

        class FakeTimestamp:
            def getClass(self):
                m = MagicMock()
                m.getName.return_value = "java.sql.Timestamp"
                return m
            def toLocalDateTime(self):
                return ldt

        result = _j2p(FakeTimestamp())
        assert result == datetime.datetime(2024, 3, 10, 12, 30, 45, 0)

    def test_sql_time_to_python_time(self):
        lt = MagicMock()
        lt.getHour.return_value = 8
        lt.getMinute.return_value = 15
        lt.getSecond.return_value = 0

        class FakeTime:
            def getClass(self):
                m = MagicMock()
                m.getName.return_value = "java.sql.Time"
                return m
            def toLocalTime(self):
                return lt

        result = _j2p(FakeTime())
        assert result == datetime.time(8, 15, 0)


class TestSetParam:
    def _pstmt(self):
        return MagicMock()

    def test_none_calls_setnull(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, None)
        pstmt.setNull.assert_called_once_with(1, 0)

    def test_bool_calls_setboolean(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, True)
        pstmt.setBoolean.assert_called_once_with(1, True)

    def test_int_calls_setlong(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, 42)
        args = pstmt.setLong.call_args[0]
        assert args[0] == 1
        assert int(args[1]) == 42

    def test_float_calls_setdouble(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, 3.14)
        pstmt.setDouble.assert_called_once_with(1, 3.14)

    def test_str_calls_setstring(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, "hello")
        pstmt.setString.assert_called_once_with(1, "hello")

    def test_bytes_calls_setbytes(self):
        pstmt = self._pstmt()
        _set_param(pstmt, 1, b"\x00\x01")
        pstmt.setBytes.assert_called_once_with(1, b"\x00\x01")

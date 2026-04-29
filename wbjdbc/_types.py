import re
import decimal
import datetime

_SENSITIVE = frozenset({"password", "senha", "secret"})
_NAMED_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _j2p(obj, decimal_as_float=False):
    """Convert a JDBC/Java value to a Python-native value."""
    if obj is None:
        return None
    try:
        cn = obj.getClass().getName()
    except AttributeError:
        return obj
    if cn == "java.math.BigDecimal":
        return float(str(obj)) if decimal_as_float else decimal.Decimal(str(obj))
    if cn == "java.sql.Date":
        ld = obj.toLocalDate()
        return datetime.date(ld.getYear(), ld.getMonthValue(), ld.getDayOfMonth())
    if cn == "java.sql.Timestamp":
        ldt = obj.toLocalDateTime()
        return datetime.datetime(
            ldt.getYear(), ldt.getMonthValue(), ldt.getDayOfMonth(),
            ldt.getHour(), ldt.getMinute(), ldt.getSecond(),
            ldt.getNano() // 1000,
        )
    if cn == "java.sql.Time":
        lt = obj.toLocalTime()
        return datetime.time(lt.getHour(), lt.getMinute(), lt.getSecond())
    return obj


def _set_param(pstmt, idx, val):
    """Set a single parameter on a JDBC PreparedStatement (1-based index)."""
    if val is None:
        pstmt.setNull(idx, 0)
    elif isinstance(val, bool):
        pstmt.setBoolean(idx, val)
    elif isinstance(val, int):
        pstmt.setLong(idx, val)
    elif isinstance(val, float):
        pstmt.setDouble(idx, val)
    elif isinstance(val, decimal.Decimal):
        try:
            import jpype
            pstmt.setBigDecimal(idx, jpype.java.math.BigDecimal(str(val)))
        except ImportError:
            pstmt.setDouble(idx, float(val))
    elif isinstance(val, datetime.datetime):
        try:
            import jpype
            pstmt.setTimestamp(idx, jpype.java.sql.Timestamp(int(val.timestamp() * 1000)))
        except ImportError:
            pstmt.setString(idx, val.isoformat())
    elif isinstance(val, datetime.date):
        try:
            import jpype
            millis = int(datetime.datetime.combine(val, datetime.time()).timestamp() * 1000)
            pstmt.setDate(idx, jpype.java.sql.Date(millis))
        except ImportError:
            pstmt.setString(idx, val.isoformat())
    elif isinstance(val, datetime.time):
        try:
            import jpype
            dt = datetime.datetime.combine(datetime.date.today(), val)
            pstmt.setTime(idx, jpype.java.sql.Time(int(dt.timestamp() * 1000)))
        except ImportError:
            pstmt.setString(idx, val.isoformat())
    elif isinstance(val, bytes):
        pstmt.setBytes(idx, val)
    else:
        pstmt.setString(idx, str(val))


def _rewrite_named(sql, params_dict):
    """Convert :name parameters to ? positional parameters, return (sql, params_list)."""
    keys = []

    def _sub(m):
        keys.append(m.group(1))
        return "?"

    new_sql = _NAMED_RE.sub(_sub, sql)
    return new_sql, [params_dict[k] for k in keys]

import re
import decimal
import datetime

_SENSITIVE = frozenset({"password", "senha", "secret"})
_NAMED_RE = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")

_INT_CLASSES = frozenset({
    "java.lang.Short", "java.lang.Integer", "java.lang.Long", "java.lang.Byte",
})
_FLOAT_CLASSES = frozenset({
    "java.lang.Float", "java.lang.Double",
})


class LobHandle:
    """Lazy handle to a JDBC BLOB/CLOB - only used when execute(..., stream_lobs=True).

    Wraps the raw java.sql.Blob/Clob object instead of materializing it into memory
    at fetch time. Per the java.sql.Blob/Clob javadoc, the underlying LOB locator
    remains valid for the duration of the transaction in which it was created,
    regardless of whether the ResultSet it came from has since been closed - so this
    can safely be read any time before the connection's next commit()/rollback().

    Trust the javadoc here, not your instincts. Every instinct says "the ResultSet is
    closed, this must be dead" and every instinct is wrong.
    """

    def __init__(self, java_lob, is_binary):
        self._lob = java_lob
        self._is_binary = is_binary

    def read(self, chunk_size=-1):
        """Read the whole LOB (chunk_size=-1, default) or up to chunk_size bytes/chars
        starting at the beginning. Returns bytes for a BLOB, str for a CLOB."""
        length = int(self._lob.length())
        n = length if chunk_size < 0 else min(chunk_size, length)
        if n <= 0:
            return b"" if self._is_binary else ""
        if self._is_binary:
            return bytes(self._lob.getBytes(1, n))
        return str(self._lob.getSubString(1, n))

    def stream(self, chunk_size=8192):
        """Yield the LOB in chunks (bytes for BLOB, str for CLOB) without loading it
        all into memory at once."""
        length = int(self._lob.length())
        pos = 1
        while pos <= length:
            n = min(chunk_size, length - pos + 1)
            if self._is_binary:
                yield bytes(self._lob.getBytes(pos, n))
            else:
                yield str(self._lob.getSubString(pos, n))
            pos += n

    def close(self):
        try:
            self._lob.free()
        except Exception:
            pass


def _j2p(obj, decimal_as_float=False, stream_lobs=False):
    """Convert a JDBC/Java value to a Python-native value."""
    if obj is None:
        return None
    try:
        cn = obj.getClass().getName()
    except AttributeError:
        return obj
    if cn in _INT_CLASSES:
        return int(obj)
    if cn in _FLOAT_CLASSES:
        return float(obj)
    if cn == "java.lang.Boolean":
        return bool(obj)
    if cn in ("java.lang.String", "java.lang.Character"):
        return str(obj).strip()
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

    # Blob/Clob are interfaces, not concrete classes - the classname (cn) is driver-
    # specific (e.g. Informix's own Blob/Clob implementation), so this can't dispatch
    # on cn like everything above. isinstance against the JDBC interface works
    # regardless of which driver produced the object.
    #
    # Before this check existed, a BLOB fetched here came back as literally the
    # string "com.informix.jdbc.IfxLob@6bc7c054" - the generic str(obj) fallback
    # below, cheerfully returning the Java object's memory address as if it were
    # your data. Nobody noticed for a while. That's the scary part.
    try:
        import jpype
        if isinstance(obj, jpype.java.sql.Blob):
            if stream_lobs:
                return LobHandle(obj, is_binary=True)
            return bytes(obj.getBytes(1, int(obj.length())))
        if isinstance(obj, jpype.java.sql.Clob):
            if stream_lobs:
                return LobHandle(obj, is_binary=False)
            return str(obj.getSubString(1, int(obj.length())))
    except (ImportError, AttributeError):
        pass

    return str(obj).strip()


def _set_param(pstmt, idx, val):
    """Set a single parameter on a JDBC PreparedStatement (1-based index)."""
    if val is None:
        pstmt.setNull(idx, 0)
    elif isinstance(val, bool):
        pstmt.setBoolean(idx, val)
    elif isinstance(val, int):
        import jpype
        pstmt.setLong(idx, jpype.JLong(val))
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

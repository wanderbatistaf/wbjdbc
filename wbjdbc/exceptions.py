"""
DB-API 2.0 (PEP 249) exception hierarchy for wbjdbc.

The raw JDBC layer only ever raises Java exceptions (surfaced through JPype) or, on
the legacy jaydebeapi-based paths, jaydebeapi's own exceptions. Neither lets calling
code write `except wbjdbc.IntegrityError` the way every other Python DB driver allows.
translate_jdbc_exception() converts a Java java.sql.SQLException (crossed into Python
via JPype) into the matching exception below, classified by the exception's SQLSTATE
class code (the first two characters - these are ANSI SQL standard codes, not specific
to Informix/MySQL/PostgreSQL).
"""


class Error(Exception):
    """Base class for all wbjdbc database errors."""

    def __init__(self, message, sqlstate=None, sqlcode=None):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.sqlcode = sqlcode


class InterfaceError(Error):
    """Error related to the database interface (wbjdbc/JPype/jaydebeapi) rather than the database itself."""


class DatabaseError(Error):
    """Error reported by the database."""


class DataError(DatabaseError):
    """Problem with the processed data (division by zero, invalid value for column type, out of range, ...)."""


class OperationalError(DatabaseError):
    """Error related to the database's operation, not necessarily under the programmer's control
    (connection lost, timeout, resource unavailable, unexpected disconnect)."""


class IntegrityError(DatabaseError):
    """Relational integrity affected (unique/foreign key/check constraint violation)."""


class InternalError(DatabaseError):
    """Internal database error (invalid cursor/transaction state)."""


class ProgrammingError(DatabaseError):
    """Programming error (SQL syntax error, table/column not found, wrong number of parameters)."""


class NotSupportedError(DatabaseError):
    """Method or database API not supported by the database."""


# SQLSTATE class (first 2 chars) -> exception class. ANSI SQL standard classes, so
# this mapping is the same regardless of which JDBC driver (Informix/MySQL/PostgreSQL)
# raised the exception.
_SQLSTATE_CLASS_MAP = {
    "08": OperationalError,   # connection exception
    "22": DataError,          # data exception
    "23": IntegrityError,     # integrity constraint violation
    "24": InternalError,      # invalid cursor state
    "25": InternalError,      # invalid transaction state
    "26": ProgrammingError,   # invalid SQL statement name
    "2B": InternalError,      # dependent privilege descriptors still exist
    "34": ProgrammingError,   # invalid cursor name
    "3D": ProgrammingError,   # invalid catalog name
    "3F": ProgrammingError,   # invalid schema name
    "40": OperationalError,   # transaction rollback
    "42": ProgrammingError,   # syntax error or access rule violation
    "0A": NotSupportedError,  # feature not supported
}


def _sqlstate_to_exception_class(sqlstate):
    if not sqlstate:
        return DatabaseError
    return _SQLSTATE_CLASS_MAP.get(sqlstate[:2], DatabaseError)


def translate_jdbc_exception(java_exc):
    """
    Translate a Java exception (crossed into Python via JPype) into a wbjdbc.Error.

    Returns a wbjdbc.Error subclass instance - it does not raise. If java_exc isn't a
    JDBC SQLException (no getSQLState/getErrorCode), it is wrapped as a generic
    DatabaseError with the original message, since we can still be confident it came
    from the Java side (a JPype JException) even without SQL-specific detail.
    """
    sqlstate = None
    sqlcode = None
    message = str(java_exc)

    get_sqlstate = getattr(java_exc, "getSQLState", None)
    if callable(get_sqlstate):
        try:
            sqlstate = get_sqlstate()
        except Exception:
            sqlstate = None

    get_error_code = getattr(java_exc, "getErrorCode", None)
    if callable(get_error_code):
        try:
            sqlcode = int(get_error_code())
        except Exception:
            sqlcode = None

    get_message = getattr(java_exc, "getMessage", None)
    if callable(get_message):
        try:
            msg = get_message()
            if msg:
                message = str(msg)
        except Exception:
            pass

    exc_class = _sqlstate_to_exception_class(sqlstate)
    return exc_class(message, sqlstate=sqlstate, sqlcode=sqlcode)


def is_java_exception(exc):
    """True if exc is a Java exception that crossed into Python via JPype."""
    try:
        import jpype
    except ImportError:
        return False
    return isinstance(exc, jpype.JException)

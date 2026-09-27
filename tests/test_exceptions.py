"""Tests for the DB-API exception hierarchy and JDBC exception translation."""
import jpype

from wbjdbc.exceptions import (
    Error, DatabaseError, DataError, OperationalError, IntegrityError,
    InternalError, ProgrammingError, NotSupportedError,
    translate_jdbc_exception, is_java_exception,
)


class _FakeSQLException(jpype.JException):
    def __init__(self, message, sqlstate=None, error_code=0):
        super().__init__(message)
        self._message = message
        self._sqlstate = sqlstate
        self._error_code = error_code

    def getSQLState(self):
        return self._sqlstate

    def getErrorCode(self):
        return self._error_code

    def getMessage(self):
        return self._message


def test_is_java_exception_true_for_jexception():
    assert is_java_exception(_FakeSQLException("boom", "08001")) is True


def test_is_java_exception_false_for_python_exception():
    assert is_java_exception(ValueError("nope")) is False


def test_translate_connection_error_maps_to_operational_error():
    exc = translate_jdbc_exception(_FakeSQLException("conn refused", "08001", -930))
    assert isinstance(exc, OperationalError)
    assert exc.sqlstate == "08001"
    assert exc.sqlcode == -930


def test_translate_integrity_violation_maps_to_integrity_error():
    exc = translate_jdbc_exception(_FakeSQLException("unique constraint", "23000", -239))
    assert isinstance(exc, IntegrityError)
    assert isinstance(exc, DatabaseError)


def test_translate_syntax_error_maps_to_programming_error():
    exc = translate_jdbc_exception(_FakeSQLException("syntax error", "42000", -201))
    assert isinstance(exc, ProgrammingError)


def test_translate_data_error_maps_to_data_error():
    exc = translate_jdbc_exception(_FakeSQLException("numeric overflow", "22003"))
    assert isinstance(exc, DataError)


def test_translate_unsupported_maps_to_not_supported_error():
    exc = translate_jdbc_exception(_FakeSQLException("feature not supported", "0A000"))
    assert isinstance(exc, NotSupportedError)


def test_translate_unknown_sqlstate_falls_back_to_database_error():
    exc = translate_jdbc_exception(_FakeSQLException("something else", "99999"))
    assert type(exc) is DatabaseError


def test_translate_missing_sqlstate_falls_back_to_database_error():
    class _NoSqlState(jpype.JException):
        def getMessage(self):
            return "opaque failure"

    exc = translate_jdbc_exception(_NoSqlState("opaque failure"))
    assert type(exc) is DatabaseError
    assert exc.sqlstate is None
    assert "opaque failure" in str(exc)


def test_exception_hierarchy_matches_dbapi():
    assert issubclass(DataError, DatabaseError)
    assert issubclass(OperationalError, DatabaseError)
    assert issubclass(IntegrityError, DatabaseError)
    assert issubclass(InternalError, DatabaseError)
    assert issubclass(ProgrammingError, DatabaseError)
    assert issubclass(NotSupportedError, DatabaseError)
    assert issubclass(DatabaseError, Error)

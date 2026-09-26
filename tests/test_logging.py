"""Tests for logging_config, in particular sensitive-parameter redaction."""
from unittest.mock import MagicMock

from wbjdbc.logging_config import WBJDBCLogger, _is_sensitive_sql
from wbjdbc.config import get_config, reset_config


def _logger_with_sql_logging_enabled():
    reset_config()
    config = get_config()
    config.set("LOG_SQL_QUERIES", True)
    logger = WBJDBCLogger("wbjdbc.test")
    logger.logger = MagicMock()
    return logger


def test_is_sensitive_sql_detects_password_column():
    assert _is_sensitive_sql("UPDATE users SET password = ?") is True
    assert _is_sensitive_sql("SELECT id FROM users") is False


def test_log_query_redacts_params_for_sensitive_sql():
    logger = _logger_with_sql_logging_enabled()

    logger.log_query("UPDATE users SET password = ? WHERE id = ?", ("hunter2", 1), duration=0.01)

    logged_msg = logger.logger.debug.call_args[0][0]
    assert "hunter2" not in logged_msg
    assert "Params: None" in logged_msg


def test_log_query_keeps_params_for_non_sensitive_sql():
    logger = _logger_with_sql_logging_enabled()

    logger.log_query("SELECT * FROM t WHERE id = ?", (1,), duration=0.01)

    logged_msg = logger.logger.debug.call_args[0][0]
    assert "Params: (1,)" in logged_msg

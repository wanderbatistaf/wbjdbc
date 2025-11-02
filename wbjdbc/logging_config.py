"""
Logging infrastructure for wbjdbc.

Provides structured logging with configurable outputs (console, file)
and log levels.
"""

import logging
import sys
from typing import Optional
from .config import get_config


class WBJDBCLogger:
    """Custom logger for wbjdbc with context support."""

    def __init__(self, name: str = 'wbjdbc'):
        """
        Initialize logger.

        Args:
            name: Logger name
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self._configured = False

    def configure(self, config=None):
        """
        Configure the logger based on config settings.

        Args:
            config: Config instance. If None, uses global config.
        """
        if self._configured:
            return

        if config is None:
            config = get_config()

        # Set log level
        log_level = config.get('LOG_LEVEL', 'INFO')
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Create formatter
        log_format = config.get('LOG_FORMAT')
        formatter = logging.Formatter(log_format)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler if specified
        log_file = config.get('LOG_FILE')
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self._configured = True

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(message, extra=kwargs)

    def log_query(self, query: str, params: Optional[tuple] = None, duration: Optional[float] = None):
        """
        Log SQL query execution.

        Args:
            query: SQL query
            params: Query parameters
            duration: Query execution time in seconds
        """
        config = get_config()
        if not config.get('LOG_SQL_QUERIES', False):
            return

        log_msg = f"Query: {query}"
        if params:
            log_msg += f" | Params: {params}"
        if duration is not None:
            log_msg += f" | Duration: {duration:.4f}s"

        self.logger.debug(log_msg)


# Global logger instance
_global_logger = None


def get_logger(name: str = 'wbjdbc') -> WBJDBCLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        WBJDBCLogger: Logger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = WBJDBCLogger(name)
        _global_logger.configure()
    return _global_logger


def reset_logger():
    """Reset global logger (mainly for testing)."""
    global _global_logger
    _global_logger = None

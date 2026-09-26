"""
Configuration management for wbjdbc with .env support.

This module handles all configuration including database connections,
connection pooling, timeouts, and feature flags.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Central configuration class for wbjdbc optimized features."""

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration from environment or .env file.

        Args:
            env_file: Path to .env file. If None, looks for .env in current directory.
        """
        self._config = {}
        self._file_overrides: Dict[str, str] = {}
        self._load_env_file(env_file)
        self._load_defaults()

    def _load_env_file(self, env_file: Optional[str] = None):
        """Load configuration from .env file if it exists.

        Values are kept in an instance-local dict rather than written into
        os.environ: mutating the whole process environment as a side effect of
        constructing a Config (or connecting to a database) is surprising, leaks
        into any subprocess spawned later, and made Config() non-deterministic
        across instances within the same process.
        """
        if env_file is None:
            env_file = os.path.join(os.getcwd(), '.env')

        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        self._file_overrides[key] = value

    def _env(self, key: str, default: Any = None) -> Any:
        """Resolve a config value: .env file overrides > process environment > default."""
        if key in self._file_overrides:
            return self._file_overrides[key]
        return os.getenv(key, default)

    def _load_defaults(self):
        """Load default configuration values."""
        self._config = {
            # Connection Pool Settings
            'POOL_SIZE': int(self._env('WBJDBC_POOL_SIZE', '10')),
            'POOL_MAX_SIZE': int(self._env('WBJDBC_POOL_MAX_SIZE', '20')),
            'POOL_TIMEOUT': float(self._env('WBJDBC_POOL_TIMEOUT', '30.0')),
            'POOL_RECYCLE': int(self._env('WBJDBC_POOL_RECYCLE', '3600')),  # 1 hour
            'POOL_PRE_PING': str(self._env('WBJDBC_POOL_PRE_PING', 'true')).lower() == 'true',

            # Connection Settings
            'CONNECTION_TIMEOUT': float(self._env('WBJDBC_CONNECTION_TIMEOUT', '10.0')),
            'QUERY_TIMEOUT': float(self._env('WBJDBC_QUERY_TIMEOUT', '30.0')),
            'MAX_RETRIES': int(self._env('WBJDBC_MAX_RETRIES', '3')),
            'RETRY_DELAY': float(self._env('WBJDBC_RETRY_DELAY', '1.0')),
            'AUTO_RECONNECT': str(self._env('WBJDBC_AUTO_RECONNECT', 'true')).lower() == 'true',

            # Batch Execution Settings
            'BATCH_SIZE': int(self._env('WBJDBC_BATCH_SIZE', '1000')),
            'BATCH_COMMIT_INTERVAL': int(self._env('WBJDBC_BATCH_COMMIT_INTERVAL', '5000')),

            # Metadata Cache Settings
            'CACHE_ENABLED': str(self._env('WBJDBC_CACHE_ENABLED', 'true')).lower() == 'true',
            'CACHE_TTL': int(self._env('WBJDBC_CACHE_TTL', '3600')),  # 1 hour
            'CACHE_MAX_SIZE': int(self._env('WBJDBC_CACHE_MAX_SIZE', '1000')),

            # Async Settings
            'ASYNC_ENABLED': str(self._env('WBJDBC_ASYNC_ENABLED', 'true')).lower() == 'true',
            'ASYNC_MAX_WORKERS': int(self._env('WBJDBC_ASYNC_MAX_WORKERS', '50')),

            # Logging Settings
            'LOG_LEVEL': self._env('WBJDBC_LOG_LEVEL', 'INFO'),
            'LOG_FILE': self._env('WBJDBC_LOG_FILE', ''),
            'LOG_FORMAT': self._env('WBJDBC_LOG_FORMAT',
                                   '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            'LOG_SQL_QUERIES': str(self._env('WBJDBC_LOG_SQL_QUERIES', 'false')).lower() == 'true',

            # Metrics Settings
            'METRICS_ENABLED': str(self._env('WBJDBC_METRICS_ENABLED', 'true')).lower() == 'true',
            'METRICS_FILE': self._env('WBJDBC_METRICS_FILE', ''),
            'METRICS_PROMETHEUS': str(self._env('WBJDBC_METRICS_PROMETHEUS', 'false')).lower() == 'true',

            # Informix Specific Settings
            'INFORMIX_DIRTY_READS': str(self._env('WBJDBC_INFORMIX_DIRTY_READS', 'false')).lower() == 'true',
            'INFORMIX_ISOLATION_LEVEL': self._env('WBJDBC_INFORMIX_ISOLATION_LEVEL', 'READ_COMMITTED'),

            # Database Connection Defaults
            'DB_HOST': self._env('WBJDBC_DB_HOST', 'localhost'),
            'DB_PORT': self._env('WBJDBC_DB_PORT', ''),
            'DB_NAME': self._env('WBJDBC_DB_NAME', ''),
            'DB_USER': self._env('WBJDBC_DB_USER', ''),
            'DB_PASSWORD': self._env('WBJDBC_DB_PASSWORD', ''),
            'DB_SERVER': self._env('WBJDBC_DB_SERVER', ''),  # For Informix

            # Security Settings
            'SSL_ENABLED': str(self._env('WBJDBC_SSL_ENABLED', 'false')).lower() == 'true',
            'SSL_VERIFY': str(self._env('WBJDBC_SSL_VERIFY', 'true')).lower() == 'true',
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value."""
        self._config[key] = value

    def get_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration."""
        return {
            'pool_size': self.get('POOL_SIZE'),
            'max_size': self.get('POOL_MAX_SIZE'),
            'timeout': self.get('POOL_TIMEOUT'),
            'recycle': self.get('POOL_RECYCLE'),
            'pre_ping': self.get('POOL_PRE_PING'),
        }

    def get_connection_config(self) -> Dict[str, Any]:
        """Get connection configuration."""
        return {
            'timeout': self.get('CONNECTION_TIMEOUT'),
            'query_timeout': self.get('QUERY_TIMEOUT'),
            'max_retries': self.get('MAX_RETRIES'),
            'retry_delay': self.get('RETRY_DELAY'),
            'auto_reconnect': self.get('AUTO_RECONNECT'),
        }

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration."""
        return {
            'enabled': self.get('CACHE_ENABLED'),
            'ttl': self.get('CACHE_TTL'),
            'max_size': self.get('CACHE_MAX_SIZE'),
        }

    def get_async_config(self) -> Dict[str, Any]:
        """Get async configuration."""
        return {
            'enabled': self.get('ASYNC_ENABLED'),
            'max_workers': self.get('ASYNC_MAX_WORKERS'),
        }

    def get_db_connection_params(self) -> Dict[str, str]:
        """Get default database connection parameters from config."""
        params = {
            'host': self.get('DB_HOST'),
            'database': self.get('DB_NAME'),
            'user': self.get('DB_USER'),
            'password': self.get('DB_PASSWORD'),
        }

        if self.get('DB_PORT'):
            params['port'] = int(self.get('DB_PORT'))

        if self.get('DB_SERVER'):
            params['server'] = self.get('DB_SERVER')

        return {k: v for k, v in params.items() if v}


# Global configuration instance
_global_config = None


def get_config(env_file: Optional[str] = None) -> Config:
    """
    Get the global configuration instance.

    Args:
        env_file: Path to .env file (only used on first call)

    Returns:
        Config: Global configuration instance
    """
    global _global_config
    if _global_config is None:
        _global_config = Config(env_file)
    return _global_config


def reset_config():
    """Reset global configuration (mainly for testing)."""
    global _global_config
    _global_config = None

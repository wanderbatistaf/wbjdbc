"""
Deprecated compatibility layer for wbjdbc < 2.1.

OptimizedJDBCConnection / OptimizedJDBCCursor used to be a separate implementation
(pooling via wbjdbc.pool.ConnectionPool, cursors via jaydebeapi). As of wbjdbc 2.1
they are thin wrappers around the same fast core that connect_optimized() uses
directly (_PooledConn / _DirectCursor / the JPype-direct ConnectionPool in
wbjdbc/__init__.py), so they get the same statement cache, pre-warming, pre-ping and
schema cache. New code should call wbjdbc.connect_optimized() directly.
"""

import warnings
from typing import List, Dict, Any, Optional
from concurrent.futures import Future

from .config import get_config
from .logging_config import get_logger
from .metrics import get_metrics_collector


class OptimizedJDBCCursor:
    """Deprecated thin wrapper around _DirectCursor. Kept for backward compatibility."""

    def __init__(self, cursor, connection, enable_type_mapping: bool = True):
        """
        Args:
            cursor: Underlying _DirectCursor (already returns Python-native types)
            connection: Parent OptimizedJDBCConnection
            enable_type_mapping: Unused; the underlying cursor always converts types
        """
        self.cursor = cursor
        self.connection = connection
        self.enable_type_mapping = enable_type_mapping
        self.logger = get_logger()
        self.metrics = get_metrics_collector()

    def execute(self, query: str, params: Optional[tuple] = None, timeout: Optional[float] = None):
        """Execute a query. `timeout` is accepted for backward compatibility but unused."""
        self.cursor.execute(query, params)
        return self

    def executemany(self, query: str, params_list: List[tuple]) -> int:
        """Execute query multiple times with different parameters (batch)."""
        return self.cursor.executemany(query, params_list)

    @property
    def description(self):
        """Get column description."""
        return self.cursor.description

    def fetchone(self) -> Optional[tuple]:
        return self.cursor.fetchone()

    def fetchall(self) -> List[tuple]:
        return self.cursor.fetchall()

    def fetchmany(self, size: int = None) -> List[tuple]:
        return self.cursor.fetchmany(size) if size else self.cursor.fetchmany()

    def fetchdh(self) -> List[Dict[str, Any]]:
        return self.cursor.fetchdh()

    def close(self):
        self.cursor.close()


class OptimizedJDBCConnection:
    """Deprecated. Use wbjdbc.connect_optimized() instead.

    Kept only for backward compatibility with wbjdbc < 2.1; delegates to the same
    core connect_optimized() returns.
    """

    def __init__(
        self,
        db_type: str,
        host: str,
        database: str,
        user: str,
        password: str,
        port: Optional[int] = None,
        server: Optional[str] = None,
        use_pool: bool = True,
        enable_type_mapping: bool = True,
        isolation_level: Optional[str] = None,
        **kwargs
    ):
        warnings.warn(
            "OptimizedJDBCConnection is deprecated and will be removed in a future "
            "release; use wbjdbc.connect_optimized() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from . import connect_optimized as _connect_optimized

        self.db_type = db_type
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.server = server
        self.use_pool = use_pool
        self.enable_type_mapping = enable_type_mapping
        self.isolation_level = isolation_level

        self.logger = get_logger()
        self.metrics = get_metrics_collector()
        self.config = get_config()

        self._core = _connect_optimized(
            db_type=db_type,
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
            server=server,
            use_pool=use_pool,
            isolation_level=isolation_level,
            **kwargs,
        )

    def cursor(self) -> OptimizedJDBCCursor:
        """Get a cursor for executing queries."""
        return OptimizedJDBCCursor(self._core.cursor(), self, self.enable_type_mapping)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        return self._core.execute_query(query, params)

    def execute_batch(
        self,
        query: str,
        params_list: List[tuple],
        batch_size: Optional[int] = None,
        commit_interval: Optional[int] = None
    ) -> int:
        """Execute query in batches with optional auto-commit intervals."""
        try:
            return self._core.execute_batch(
                query, params_list, batch_size=batch_size, commit_interval=commit_interval
            )
        except Exception as e:
            self.logger.error(f"Batch execution failed: {e}")
            self._core.rollback()
            raise

    def execute_async(self, query: str, params: Optional[tuple] = None) -> Future:
        """Execute query asynchronously in a thread pool."""
        return self._core.execute_async(query, params)

    def get_table_columns(self, table: str) -> List[Dict[str, Any]]:
        """Get column information for a table (with caching)."""
        return self._core.get_table_columns(table)

    def get_procedure_source(self, proc_name: str) -> Optional[str]:
        """Get the CREATE PROCEDURE/FUNCTION source text (with caching)."""
        return self._core.get_procedure_source(proc_name)

    def commit(self):
        """Commit the current transaction."""
        self._core.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self._core.rollback()

    def close(self):
        """Close the connection (returns it to the pool if pooled)."""
        self._core.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

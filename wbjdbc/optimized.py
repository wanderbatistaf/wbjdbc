"""
Optimized JDBC connection and cursor classes with advanced features.

This module provides enhanced versions of JDBCConnection and JDBCCursor
with connection pooling, batch execution, async queries, and more.
"""

import time
import threading
from typing import List, Dict, Any, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, Future
import jaydebeapi

from .config import get_config
from .logging_config import get_logger
from .metrics import get_metrics_collector
from .pool import get_pool, PooledConnection
from .cache import get_schema_cache
from .types import TypeMapper
from .jvm import start_jvm


class OptimizedJDBCCursor:
    """Enhanced JDBC cursor with type mapping and caching."""

    def __init__(self, cursor, connection, enable_type_mapping: bool = True):
        """
        Initialize optimized cursor.

        Args:
            cursor: Underlying JDBC cursor
            connection: Parent connection
            enable_type_mapping: Enable automatic type conversion
        """
        self.cursor = cursor
        self.connection = connection
        self.enable_type_mapping = enable_type_mapping
        self._description = None
        self._column_types = None
        self.logger = get_logger()
        self.metrics = get_metrics_collector()

    def execute(self, query: str, params: Optional[tuple] = None, timeout: Optional[float] = None):
        """
        Execute a query with optional parameters and timeout.

        Args:
            query: SQL query
            params: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Self for chaining
        """
        start_time = time.time()
        success = False

        try:
            # Convert Python parameters to JDBC types
            if params and self.enable_type_mapping:
                params = TypeMapper.convert_params(params)

            # Execute query
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            # Store column information
            self._description = self.cursor.description
            if self._description:
                # Extract column types if available
                self._column_types = [desc[1] if len(desc) > 1 else None for desc in self._description]

            success = True
            return self

        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise

        finally:
            duration = time.time() - start_time
            self.metrics.record_query(query, duration, success)
            self.logger.log_query(query, params, duration)

    def executemany(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute query multiple times with different parameters (batch).

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            Number of rows affected
        """
        start_time = time.time()
        success = False

        try:
            # Convert parameters
            if self.enable_type_mapping:
                params_list = [TypeMapper.convert_params(params) for params in params_list]

            # Use JDBC batch execution
            if hasattr(self.cursor, 'executemany'):
                result = self.cursor.executemany(query, params_list)
            else:
                # Fallback to manual batching
                result = 0
                for params in params_list:
                    self.cursor.execute(query, params)
                    result += 1

            success = True
            self.metrics.record_batch_operation(len(params_list))
            return result

        except Exception as e:
            self.logger.error(f"Batch execution failed: {e}")
            raise

        finally:
            duration = time.time() - start_time
            self.metrics.record_query(query, duration, success)
            self.logger.log_query(f"{query} (batch {len(params_list)})", None, duration)

    @property
    def description(self):
        """Get column description."""
        return self._description

    def fetchone(self) -> Optional[tuple]:
        """Fetch one row with type conversion."""
        row = self.cursor.fetchone()
        if row and self.enable_type_mapping:
            return TypeMapper.convert_row(row, self._column_types)
        return row

    def fetchall(self) -> List[tuple]:
        """Fetch all rows with type conversion."""
        rows = self.cursor.fetchall()
        if rows and self.enable_type_mapping:
            return [TypeMapper.convert_row(row, self._column_types) for row in rows]
        return rows or []

    def fetchmany(self, size: int = None) -> List[tuple]:
        """
        Fetch multiple rows with type conversion.

        Args:
            size: Number of rows to fetch

        Returns:
            List of rows
        """
        if size:
            rows = self.cursor.fetchmany(size)
        else:
            rows = self.cursor.fetchmany()

        if rows and self.enable_type_mapping:
            return [TypeMapper.convert_row(row, self._column_types) for row in rows]
        return rows or []

    def fetchdh(self) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries with type conversion."""
        if not self._description:
            return []

        column_names = [desc[0] for desc in self._description]
        rows = self.fetchall()
        return [dict(zip(column_names, row)) for row in rows]

    def close(self):
        """Close the cursor."""
        try:
            self.cursor.close()
        except Exception as e:
            self.logger.error(f"Error closing cursor: {e}")


class OptimizedJDBCConnection:
    """Enhanced JDBC connection with pooling, batching, and async support."""

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
        """
        Initialize optimized connection.

        Args:
            db_type: Database type
            host: Database host
            database: Database name
            user: Database user
            password: Database password
            port: Database port
            server: Informix server name
            use_pool: Use connection pooling
            enable_type_mapping: Enable automatic type conversion
            isolation_level: Transaction isolation level
            **kwargs: Additional configuration
        """
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
        self.schema_cache = get_schema_cache()

        self._connection = None
        self._pooled_connection = None
        self._pool = None
        self._executor = None

        # Initialize connection
        self._initialize()

    def _initialize(self):
        """Initialize the connection."""
        if self.use_pool:
            self._initialize_pooled()
        else:
            self._initialize_direct()

        # Set isolation level if specified
        if self.isolation_level:
            self._set_isolation_level(self.isolation_level)

    def _initialize_pooled(self):
        """Initialize connection from pool."""
        # This will be done lazily when a cursor is requested
        pass

    def _initialize_direct(self):
        """Initialize direct connection without pooling."""
        # Import here to get the driver configuration
        from . import DEFAULT_DRIVERS

        if self.db_type not in DEFAULT_DRIVERS:
            raise ValueError(f"Unsupported database type: {self.db_type}")

        driver_config = DEFAULT_DRIVERS[self.db_type]
        driver_class = driver_config['driver_class']
        jar_path = driver_config['jar']
        port = self.port or driver_config['default_port']

        # Build JDBC URL
        if self.db_type == 'informix-sqli':
            if not self.server:
                raise ValueError("Informix requires 'server' parameter")
            jdbc_url = f"jdbc:informix-sqli://{self.host}:{port}/{self.database}:INFORMIXSERVER={self.server}"
        else:
            jdbc_url = f"jdbc:{self.db_type}://{self.host}:{port}/{self.database}"

        # Start JVM if needed
        jars = [jar_path]
        start_jvm(jars)

        # Create connection
        start_time = time.time()
        try:
            self._connection = jaydebeapi.connect(
                driver_class,
                jdbc_url,
                [self.user, self.password],
                jars
            )
            duration = time.time() - start_time
            self.logger.info(f"Connected to {self.db_type} in {duration:.4f}s")
            self.metrics.record_connection(success=True, reused=False)

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.metrics.record_connection(success=False)
            raise

    def _get_connection(self):
        """Get underlying connection (from pool or direct)."""
        if self.use_pool:
            if self._pooled_connection is None:
                # Get connection from pool
                from . import DEFAULT_DRIVERS

                if self.db_type not in DEFAULT_DRIVERS:
                    raise ValueError(f"Unsupported database type: {self.db_type}")

                driver_config = DEFAULT_DRIVERS[self.db_type]
                driver_class = driver_config['driver_class']
                jar_path = driver_config['jar']
                port = self.port or driver_config['default_port']

                # Build JDBC URL
                if self.db_type == 'informix-sqli':
                    if not self.server:
                        raise ValueError("Informix requires 'server' parameter")
                    jdbc_url = f"jdbc:informix-sqli://{self.host}:{port}/{self.database}:INFORMIXSERVER={self.server}"
                else:
                    jdbc_url = f"jdbc:{self.db_type}://{self.host}:{port}/{self.database}"

                # Start JVM if needed
                jars = [jar_path]
                start_jvm(jars)

                # Get or create pool
                self._pool = get_pool(
                    db_type=self.db_type,
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=port,
                    server=self.server,
                    driver_class=driver_class,
                    jdbc_url=jdbc_url,
                    jars=jars
                )

                self._pooled_connection = self._pool.get_connection()

            return self._pooled_connection._connection
        else:
            return self._connection

    def _set_isolation_level(self, level: str):
        """Set transaction isolation level."""
        if self.db_type == 'informix-sqli':
            # Handle Informix dirty reads
            if level == 'DIRTY_READ' or level == 'READ_UNCOMMITTED':
                try:
                    conn = self._get_connection()
                    # Set isolation level to dirty read
                    stmt = conn.createStatement()
                    stmt.execute("SET ISOLATION TO DIRTY READ")
                    stmt.close()
                    self.logger.info("Set Informix isolation level to DIRTY READ")
                except Exception as e:
                    self.logger.error(f"Failed to set isolation level: {e}")

    def cursor(self) -> OptimizedJDBCCursor:
        """Get a cursor for executing queries."""
        conn = self._get_connection()
        jdbc_cursor = conn.cursor()
        return OptimizedJDBCCursor(jdbc_cursor, self, self.enable_type_mapping)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results as list of dictionaries.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of dictionaries
        """
        cursor = self.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchdh()
        finally:
            cursor.close()

    def execute_batch(
        self,
        query: str,
        params_list: List[tuple],
        batch_size: Optional[int] = None,
        commit_interval: Optional[int] = None
    ) -> int:
        """
        Execute query in batches with optional auto-commit intervals.

        Args:
            query: SQL query
            params_list: List of parameter tuples
            batch_size: Size of each batch
            commit_interval: Commit after this many rows

        Returns:
            Total rows affected
        """
        if batch_size is None:
            batch_size = self.config.get('BATCH_SIZE', 1000)

        if commit_interval is None:
            commit_interval = self.config.get('BATCH_COMMIT_INTERVAL', 5000)

        cursor = self.cursor()
        total_affected = 0

        try:
            for i in range(0, len(params_list), batch_size):
                batch = params_list[i:i + batch_size]
                affected = cursor.executemany(query, batch)
                total_affected += affected

                # Auto-commit if interval reached
                if commit_interval and (i + batch_size) % commit_interval == 0:
                    self.commit()

            # Final commit
            self.commit()
            return total_affected

        except Exception as e:
            self.logger.error(f"Batch execution failed: {e}")
            self.rollback()
            raise
        finally:
            cursor.close()

    def execute_async(self, query: str, params: Optional[tuple] = None) -> Future:
        """
        Execute query asynchronously in a thread pool.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Future object
        """
        if self._executor is None:
            config = self.config.get_async_config()
            max_workers = config.get('max_workers', 50)
            self._executor = ThreadPoolExecutor(max_workers=max_workers)

        return self._executor.submit(self.execute_query, query, params)

    def get_table_columns(self, table: str) -> List[Dict[str, Any]]:
        """
        Get column information for a table (with caching).

        Args:
            table: Table name

        Returns:
            List of column metadata
        """
        # Try cache first
        cached = self.schema_cache.get_columns(self.database, table)
        if cached:
            return cached

        # Query database
        cursor = self.cursor()
        try:
            # Get table metadata
            columns = []
            meta = cursor.cursor.connection.getMetaData() if hasattr(cursor.cursor, 'connection') else None

            if meta:
                rs = meta.getColumns(None, None, table, None)
                while rs.next():
                    column = {
                        'name': rs.getString('COLUMN_NAME'),
                        'type': rs.getInt('DATA_TYPE'),
                        'type_name': rs.getString('TYPE_NAME'),
                        'size': rs.getInt('COLUMN_SIZE'),
                        'nullable': rs.getInt('NULLABLE') == 1,
                    }
                    columns.append(column)
                rs.close()

            # Cache results
            self.schema_cache.set_columns(self.database, table, columns)
            return columns

        except Exception as e:
            self.logger.error(f"Failed to get table columns: {e}")
            return []
        finally:
            cursor.close()

    def commit(self):
        """Commit the current transaction."""
        try:
            conn = self._get_connection()
            conn.commit()
        except Exception as e:
            self.logger.error(f"Commit failed: {e}")
            raise

    def rollback(self):
        """Rollback the current transaction."""
        try:
            conn = self._get_connection()
            conn.rollback()
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            raise

    def close(self):
        """Close the connection."""
        try:
            # Shutdown executor if exists
            if self._executor:
                self._executor.shutdown(wait=True)
                self._executor = None

            # Return pooled connection or close direct connection
            if self._pooled_connection:
                self._pool.return_connection(self._pooled_connection)
                self._pooled_connection = None
            elif self._connection:
                self._connection.close()
                self._connection = None

        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

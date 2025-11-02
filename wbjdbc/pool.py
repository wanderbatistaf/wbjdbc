"""
Connection pooling for wbjdbc.

Implements a thread-safe connection pool to reuse JDBC connections
and reduce overhead.
"""

import time
import threading
from queue import Queue, Empty, Full
from typing import Optional, Dict, Any
import jaydebeapi
from .config import get_config
from .logging_config import get_logger
from .metrics import get_metrics_collector


class PooledConnection:
    """Wrapper for a pooled JDBC connection."""

    def __init__(self, connection, pool, created_at: float):
        """
        Initialize pooled connection.

        Args:
            connection: JDBC connection
            pool: Connection pool instance
            created_at: Timestamp when connection was created
        """
        self._connection = connection
        self._pool = pool
        self._created_at = created_at
        self._last_used = time.time()
        self._in_use = True

    def __enter__(self):
        """Context manager entry."""
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - return connection to pool."""
        self._pool.return_connection(self)

    def __getattr__(self, name):
        """Proxy attribute access to underlying connection."""
        return getattr(self._connection, name)

    def is_valid(self) -> bool:
        """Check if connection is still valid."""
        try:
            # Try to get cursor to check if connection is alive
            cursor = self._connection.cursor()
            cursor.close()
            return True
        except Exception:
            return False

    def should_recycle(self, recycle_time: int) -> bool:
        """
        Check if connection should be recycled based on age.

        Args:
            recycle_time: Max age in seconds

        Returns:
            bool: True if connection should be recycled
        """
        age = time.time() - self._created_at
        return age > recycle_time


class ConnectionPool:
    """Thread-safe connection pool for JDBC connections."""

    def __init__(
        self,
        db_type: str,
        host: str,
        database: str,
        user: str,
        password: str,
        port: Optional[int] = None,
        server: Optional[str] = None,
        driver_class: Optional[str] = None,
        jdbc_url: Optional[str] = None,
        jars: Optional[list] = None,
        pool_size: int = 10,
        max_size: int = 20,
        timeout: float = 30.0,
        recycle: int = 3600,
        pre_ping: bool = True,
    ):
        """
        Initialize connection pool.

        Args:
            db_type: Database type
            host: Database host
            database: Database name
            user: Database user
            password: Database password
            port: Database port
            server: Informix server name
            driver_class: JDBC driver class
            jdbc_url: JDBC URL (if None, will be constructed)
            jars: List of JAR files
            pool_size: Initial pool size
            max_size: Maximum pool size
            timeout: Connection checkout timeout
            recycle: Connection recycle time in seconds
            pre_ping: Test connections before returning them
        """
        self.db_type = db_type
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.server = server
        self.driver_class = driver_class
        self.jdbc_url = jdbc_url
        self.jars = jars or []

        self.pool_size = pool_size
        self.max_size = max_size
        self.timeout = timeout
        self.recycle = recycle
        self.pre_ping = pre_ping

        self._pool: Queue = Queue(maxsize=max_size)
        self._lock = threading.Lock()
        self._current_size = 0
        self._closed = False

        self.logger = get_logger()
        self.metrics = get_metrics_collector()

        # Initialize pool with minimum connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize pool with minimum number of connections."""
        self.logger.info(f"Initializing connection pool with {self.pool_size} connections")
        for _ in range(self.pool_size):
            try:
                conn = self._create_connection()
                self._pool.put(PooledConnection(conn, self, time.time()))
            except Exception as e:
                self.logger.error(f"Failed to create initial connection: {e}")
                self.metrics.record_connection(success=False)

    def _create_connection(self):
        """Create a new JDBC connection."""
        try:
            start_time = time.time()

            conn = jaydebeapi.connect(
                self.driver_class,
                self.jdbc_url,
                [self.user, self.password],
                self.jars
            )

            duration = time.time() - start_time
            self.logger.debug(f"Created new connection in {duration:.4f}s")

            with self._lock:
                self._current_size += 1

            self.metrics.record_connection(success=True, reused=False)
            return conn

        except Exception as e:
            self.logger.error(f"Failed to create connection: {e}")
            self.metrics.record_connection(success=False)
            raise

    def get_connection(self, timeout: Optional[float] = None) -> PooledConnection:
        """
        Get a connection from the pool.

        Args:
            timeout: Checkout timeout (uses pool timeout if None)

        Returns:
            PooledConnection: Pooled connection

        Raises:
            Exception: If pool is closed or timeout occurs
        """
        if self._closed:
            raise Exception("Connection pool is closed")

        if timeout is None:
            timeout = self.timeout

        start_time = time.time()

        while True:
            try:
                # Try to get connection from pool
                conn = self._pool.get(timeout=0.1)

                # Check if connection should be recycled
                if conn.should_recycle(self.recycle):
                    self.logger.debug("Recycling old connection")
                    self._close_connection(conn)
                    conn = None
                    continue

                # Pre-ping to verify connection
                if self.pre_ping and not conn.is_valid():
                    self.logger.debug("Connection failed pre-ping, creating new one")
                    self._close_connection(conn)
                    conn = None
                    continue

                # Connection is valid
                conn._in_use = True
                conn._last_used = time.time()
                self.metrics.record_connection(success=True, reused=True)
                self.metrics.record_pool_checkout(success=True)
                return conn

            except Empty:
                # No connection available in pool
                with self._lock:
                    if self._current_size < self.max_size:
                        # Can create new connection
                        try:
                            new_conn = self._create_connection()
                            pooled_conn = PooledConnection(new_conn, self, time.time())
                            pooled_conn._in_use = True
                            self.metrics.record_pool_checkout(success=True)
                            return pooled_conn
                        except Exception as e:
                            self.logger.error(f"Failed to create new connection: {e}")
                            self.metrics.record_pool_checkout(success=False)
                            raise

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    self.logger.error(f"Connection checkout timeout after {elapsed:.2f}s")
                    self.metrics.record_pool_checkout(success=False)
                    raise Exception(f"Connection pool timeout after {timeout}s")

                # Wait a bit before retrying
                time.sleep(0.1)

    def return_connection(self, conn: PooledConnection):
        """
        Return a connection to the pool.

        Args:
            conn: Connection to return
        """
        if self._closed:
            self._close_connection(conn)
            return

        conn._in_use = False
        conn._last_used = time.time()

        try:
            # Try to return to pool
            self._pool.put_nowait(conn)
        except Full:
            # Pool is full, close the connection
            self.logger.debug("Pool is full, closing excess connection")
            self._close_connection(conn)

    def _close_connection(self, conn: PooledConnection):
        """Close a connection and update pool size."""
        try:
            conn._connection.close()
            with self._lock:
                self._current_size -= 1
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")

    def close(self):
        """Close the connection pool and all connections."""
        self.logger.info("Closing connection pool")
        self._closed = True

        # Close all connections in pool
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
            except Empty:
                break

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.

        Returns:
            Dict with pool stats
        """
        return {
            'pool_size': self.pool_size,
            'max_size': self.max_size,
            'current_size': self._current_size,
            'available': self._pool.qsize(),
            'in_use': self._current_size - self._pool.qsize(),
            'closed': self._closed,
        }


# Global connection pools (one per database connection string)
_connection_pools: Dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(
    db_type: str,
    host: str,
    database: str,
    user: str,
    password: str,
    port: Optional[int] = None,
    server: Optional[str] = None,
    driver_class: Optional[str] = None,
    jdbc_url: Optional[str] = None,
    jars: Optional[list] = None,
    **kwargs
) -> ConnectionPool:
    """
    Get or create a connection pool for the given database.

    Args:
        db_type: Database type
        host: Database host
        database: Database name
        user: Database user
        password: Database password
        port: Database port
        server: Informix server name
        driver_class: JDBC driver class
        jdbc_url: JDBC URL
        jars: List of JAR files
        **kwargs: Additional pool configuration

    Returns:
        ConnectionPool: Connection pool instance
    """
    # Create unique key for this connection
    pool_key = f"{db_type}:{host}:{port}:{database}:{user}"

    with _pools_lock:
        if pool_key not in _connection_pools:
            config = get_config()
            pool_config = config.get_pool_config()

            # Override with any provided kwargs
            pool_config.update(kwargs)

            pool = ConnectionPool(
                db_type=db_type,
                host=host,
                database=database,
                user=user,
                password=password,
                port=port,
                server=server,
                driver_class=driver_class,
                jdbc_url=jdbc_url,
                jars=jars,
                pool_size=pool_config.get('pool_size', 10),
                max_size=pool_config.get('max_size', 20),
                timeout=pool_config.get('timeout', 30.0),
                recycle=pool_config.get('recycle', 3600),
                pre_ping=pool_config.get('pre_ping', True),
            )

            _connection_pools[pool_key] = pool

        return _connection_pools[pool_key]


def close_all_pools():
    """Close all connection pools."""
    with _pools_lock:
        for pool in _connection_pools.values():
            pool.close()
        _connection_pools.clear()

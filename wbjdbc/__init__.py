import os
import re
import time
import logging
import threading
import decimal
import datetime
import socket
from .jvm import start_jvm
import jaydebeapi

# Import optimized components
from .config import get_config, Config
from .logging_config import get_logger
from .metrics import get_metrics_collector
from .pool import get_pool, close_all_pools
from .cache import get_schema_cache, reset_cache
from .types import TypeMapper, JDBC_TYPES
from .optimized import OptimizedJDBCConnection, OptimizedJDBCCursor
from ._types import _j2p, _set_param, _rewrite_named, _SENSITIVE

# Default configuration for database drivers
DEFAULT_DRIVERS = {
    "informix-sqli": {
        "driver_class": "com.informix.jdbc.IfxDriver",
        "default_port": 1526,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "com.ibm.informix", "jdbc-4.50.10.1.jar"),
    },
    "mysql": {
        "driver_class": "com.mysql.cj.jdbc.Driver",
        "default_port": 3306,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "mysql", "mysql-connector-java-8.0.26.jar"),
    },
    "postgresql": {
        "driver_class": "org.postgresql.Driver",
        "default_port": 5432,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "postgresql", "postgresql-42.2.24.jar"),
    },
}

# Version
__version__ = "2.0.2"
version = __version__


def _get_jpype():
    """Return the jpype module, raising a clear error if unavailable."""
    try:
        import jpype
        return jpype
    except ImportError:
        raise ImportError("JPype1 is required. Install with: pip install JPype1>=1.3.0")


_slow_log = logging.getLogger("wbjdbc.slow")

_SELECT_PREFIXES = ("SELECT", "WITH", "SHOW", "EXPLAIN", "CALL")


def _is_select(sql):
    return sql.lstrip().upper().startswith(_SELECT_PREFIXES)


def _is_sensitive_sql(sql):
    sql_lower = sql.lower()
    return any(w in sql_lower for w in _SENSITIVE)


class _DirectCursor:
    """JDBC cursor that calls Java directly via JPype, bypassing jaydebeapi's global lock."""

    def __init__(self, java_conn, decimal_as_float=False, query_timeout_sec=30, slow_query_ms=500):
        self._jc = java_conn
        self._decimal_as_float = decimal_as_float
        self._query_timeout_sec = query_timeout_sec
        self._slow_query_ms = slow_query_ms
        self._rows = []
        self._cols = []
        self.description = None
        self.rowcount = -1

    def execute(self, sql, params=None):
        if isinstance(params, dict):
            sql, params = _rewrite_named(sql, params)
        pstmt = self._jc.prepareStatement(sql)
        if self._query_timeout_sec:
            pstmt.setQueryTimeout(self._query_timeout_sec)
        if params:
            for i, v in enumerate(params, 1):
                _set_param(pstmt, i, v)
        t0 = time.monotonic()
        try:
            if _is_select(sql):
                rs = pstmt.executeQuery()
                meta = rs.getMetaData()
                n = meta.getColumnCount()
                self._cols = [meta.getColumnLabel(i) for i in range(1, n + 1)]
                self.description = tuple(
                    (meta.getColumnLabel(i), meta.getColumnType(i), None, None, None, None, None)
                    for i in range(1, n + 1)
                )
                daf = self._decimal_as_float
                self._rows = []
                while rs.next():
                    self._rows.append(
                        tuple(_j2p(rs.getObject(i), daf) for i in range(1, n + 1))
                    )
                rs.close()
                self.rowcount = len(self._rows)
            else:
                self.rowcount = pstmt.executeUpdate()
                self._rows = []
                self._cols = []
                self.description = None
        finally:
            pstmt.close()
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > self._slow_query_ms:
                safe = None if _is_sensitive_sql(sql) else params
                _slow_log.warning(
                    "slow_query elapsed_ms=%.1f sql=%r params=%r", elapsed_ms, sql, safe
                )

    def executemany(self, sql, params_list):
        if params_list and isinstance(params_list[0], dict):
            sql, _ = _rewrite_named(sql, params_list[0])
        pstmt = self._jc.prepareStatement(sql)
        if self._query_timeout_sec:
            pstmt.setQueryTimeout(self._query_timeout_sec)
        for params in params_list:
            if isinstance(params, dict):
                _, params = _rewrite_named(sql, params)
            for i, v in enumerate(params, 1):
                _set_param(pstmt, i, v)
            pstmt.addBatch()
        counts = pstmt.executeBatch()
        pstmt.close()
        self.rowcount = sum(int(c) for c in counts if int(c) >= 0)
        return self.rowcount

    def fetchone(self):
        if self._rows:
            return self._rows.pop(0)
        return None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def fetchmany(self, size=1):
        rows, self._rows = self._rows[:size], self._rows[size:]
        return rows

    def fetchdh(self):
        if not self._cols:
            return []
        return [dict(zip(self._cols, row)) for row in self.fetchall()]

    def fetchdf(self):
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for fetchdf(). Install with: pip install pandas")
        cols = list(self._cols)
        rows = self.fetchall()
        return pd.DataFrame(rows, columns=cols)

    def close(self):
        pass


class _PooledConn:
    """Wraps a raw Java connection with pool lifecycle and _DirectCursor support."""

    def __init__(self, java_conn, pool, pool_key=None):
        self._jc = java_conn
        self._pool = pool
        self._created_at = time.monotonic()
        self.pool_key = pool_key

    def cursor(self):
        if self._pool is not None:
            return _DirectCursor(
                self._jc,
                decimal_as_float=self._pool._decimal_as_float,
                query_timeout_sec=self._pool._query_timeout_sec,
                slow_query_ms=self._pool._slow_query_ms,
            )
        return _DirectCursor(self._jc)

    def execute_query(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur.fetchdh()

    def execute_batch(self, sql, params_list):
        cur = self.cursor()
        return cur.executemany(sql, params_list)

    def execute_async(self, sql, params=None):
        from concurrent.futures import ThreadPoolExecutor
        if not hasattr(self, "_executor") or self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=10)
        return self._executor.submit(self.execute_query, sql, params)

    def commit(self):
        self._jc.commit()

    def rollback(self):
        self._jc.rollback()

    def close(self):
        if self._pool is not None:
            self._pool._return(self)
        else:
            try:
                self._jc.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class ConnectionPool:
    """Thread-safe JDBC connection pool using _DirectCursor (JPype direct, no jaydebeapi lock)."""

    def __init__(
        self,
        jdbc_url,
        driver_class,
        jars,
        user,
        password,
        pool_size=5,
        max_overflow=10,
        checkout_timeout=30,
        query_timeout_sec=30,
        slow_query_ms=500,
        decimal_as_float=False,
    ):
        self._jdbc_url = jdbc_url
        self._driver_class = driver_class
        self._jars = jars
        self._user = user
        self._password = password
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._checkout_timeout = checkout_timeout
        self._query_timeout_sec = query_timeout_sec
        self._slow_query_ms = slow_query_ms
        self._decimal_as_float = decimal_as_float

        self._idle = []
        self._lock = threading.Lock()
        self._capacity = threading.Semaphore(pool_size + max_overflow)

        self._stats_lock = threading.Lock()
        self._total_acquired = 0
        self._total_errors = 0
        self._total_wait_ms = 0.0
        self._max_wait_ms = 0.0
        self._active_count = 0

        start_jvm(self._jars)
        jpype = _get_jpype()
        jpype.JClass(self._driver_class)

        for _ in range(pool_size):
            self._idle.append(self._new_conn())

    def _new_conn(self):
        jpype = _get_jpype()
        jconn = jpype.java.sql.DriverManager.getConnection(
            self._jdbc_url, self._user, self._password
        )
        jconn.setAutoCommit(False)
        return _PooledConn(jconn, self)

    def _is_alive(self, pc):
        try:
            return bool(pc._jc.isValid(2))
        except Exception:
            return False

    def acquire(self):
        t0 = time.monotonic()
        if not self._capacity.acquire(timeout=self._checkout_timeout):
            with self._stats_lock:
                self._total_errors += 1
            raise TimeoutError(
                f"ConnectionPool checkout timeout after {self._checkout_timeout}s"
            )
        wait_ms = (time.monotonic() - t0) * 1000
        with self._stats_lock:
            self._total_acquired += 1
            self._total_wait_ms += wait_ms
            if wait_ms > self._max_wait_ms:
                self._max_wait_ms = wait_ms
            self._active_count += 1
        with self._lock:
            while self._idle:
                pc = self._idle.pop()
                if self._is_alive(pc):
                    return pc
        return self._new_conn()

    def _return(self, pc):
        with self._stats_lock:
            self._active_count = max(0, self._active_count - 1)
        if self._is_alive(pc):
            with self._lock:
                self._idle.append(pc)
        self._capacity.release()

    def stats(self):
        with self._lock:
            idle = len(self._idle)
        with self._stats_lock:
            total = self._total_acquired
            errors = self._total_errors
            total_wait = self._total_wait_ms
            max_wait = self._max_wait_ms
            active = self._active_count
        avg_wait = (total_wait / total) if total > 0 else 0.0
        return {
            "size": self._pool_size + self._max_overflow,
            "active": active,
            "idle": idle,
            "total_acquired": total,
            "total_errors": errors,
            "avg_wait_ms": round(avg_wait, 2),
            "max_wait_ms": round(max_wait, 2),
        }

    def close(self):
        with self._lock:
            for pc in self._idle:
                try:
                    pc._jc.close()
                except Exception:
                    pass
            self._idle.clear()


_pools: dict = {}
_pools_lock = threading.Lock()


def connect_optimized_stats(key):
    """Return stats dict for the ConnectionPool identified by key."""
    with _pools_lock:
        pool = _pools.get(key)
    if pool is None:
        raise KeyError(f"No pool found for key {key!r}. Available: {list(_pools)}")
    return pool.stats()


class ConnectionError(Exception):
    """Connection erro, friendly."""
    pass

def is_host_reachable(host):
    try:
        socket.gethostbyname(host)
        return True
    except socket.error:
        return False


class JDBCConnection:
    """Wrapper class for the JDBC connection, including a cursor with headers."""

    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        """Returns a customized JDBC cursor."""
        return JDBCCursor(self.connection.cursor())

    def close(self):
        """Closes the connection."""
        self.connection.close()

    def execute_query(self, query):
        """
        Executes a query and returns the results as a list of dictionaries.
        """
        cursor = self.cursor()
        cursor.execute(query)
        results = cursor.fetchdh()
        cursor.close()
        return results



class JDBCCursor:
    """Wrapper class for the JDBC cursor, adding support for fetchdh()."""

    def __init__(self, cursor):
        self.cursor = cursor
        self._description = None

    def execute(self, query, params=None):
        """Executes a query with or without parameters."""
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        self._description = self.cursor.description

    @property
    def description(self):
        """Description of columns after executing the command (tuple of (name, ...))"""
        return self._description

    def fetchone(self):
        """Returns a row as a tuple, or None if there are no more."""
        return self.cursor.fetchone()

    def fetchall(self):
        """Returns the data as a list of tuples."""
        return self.cursor.fetchall()

    def fetchdh(self):
        """Returns the results as a list of dictionaries with headers."""
        column_names = [desc[0] for desc in self.cursor.description]
        rows = self.cursor.fetchall()
        return [dict(zip(column_names, row)) for row in rows]

    def close(self):
        """Closes the cursor."""
        self.cursor.close()


def connect_to_db(db_type, host, database, user, password, port=None, server=None, extra_jars=None, java_home=None,
                  debug=0):
    """
    Connects to a database using JDBC without requiring complex configurations.

    :param db_type: Database type. Available options:
        - 1: "informix-sqli" (Informix)
        - 2: "mysql" (MySQL)
        - 3: "postgresql" (PostgreSQL)
    :param host: Database server address.
    :param database: Database name.
    :param user: Username.
    :param password: Password.
    :param port: Optional port (defaults to standard).
    :param server: Informix database server.
    :param extra_jars: List of additional JAR file paths, if necessary.
    :param java_home: Alternative JAVA_HOME path (optional).
    :param debug: Enables debug logs in the console.
    :return: Active connection via jaydebeapi or None if it fails.
    """

    # Maps integer values to strings
    db_type_mapping = {1: "informix-sqli", 2: "mysql", 3: "postgresql"}
    db_type = db_type_mapping.get(db_type, db_type)

    if db_type not in DEFAULT_DRIVERS:
        print(f"❌ Database '{db_type}' not supported.")
        return None

    driver_config = DEFAULT_DRIVERS[db_type]
    driver_class = driver_config["driver_class"]
    jar_path = driver_config["jar"]
    port = port or driver_config["default_port"]

    if debug:
        print(f"\n🔍 DB Type: {db_type}, Host: {host}, Database: {database}, Port: {port}")

    # 🔹 Adjusting the JDBC URL for Informix
    if db_type == "informix-sqli":
        if not server:
            print("❌ For Informix-SQLI, the `server` parameter is required.")
            return None
        jdbc_url = f"jdbc:informix-sqli://{host}:{port}/{database}:INFORMIXSERVER={server}"
    else:
        jdbc_url = f"jdbc:{db_type}://{host}:{port}/{database}"

    if debug:
        print(f"🔹 Generated JDBC URL: {jdbc_url}")

    # 🔹 Initializing the JVM
    jars = [jar_path] + (extra_jars if extra_jars else [])

    if debug:
        print("\n🟢 Starting the JVM...\n")

    start_jvm(jars, java_home=java_home, debug=debug)

    # 🔹 Attempting to connect to the database
    try:
        conn = jaydebeapi.connect(driver_class, jdbc_url, [user, password], jars)
        if debug:
            print(f"✅ Successfully connected to {db_type.upper()}!")
        return JDBCConnection(conn)  # <-- CORRECT: Returns a JDBCConnection
    except jaydebeapi.DatabaseError as e:
        print(f"❌ Error connecting to the database: {e}")
        return None


def connect_optimized(
    db_type=None,
    host=None,
    database=None,
    user=None,
    password=None,
    port=None,
    server=None,
    use_pool=True,
    enable_type_mapping=True,
    isolation_level=None,
    config_file=None,
    query_timeout_sec=30,
    slow_query_ms=500,
    decimal_as_float=False,
    pool_size=5,
    max_overflow=10,
    checkout_timeout=30,
    **kwargs
):
    """Create an optimized JDBC connection using _DirectCursor (bypasses jaydebeapi global lock)."""
    config = get_config(config_file)

    db_type_mapping = {1: "informix-sqli", 2: "mysql", 3: "postgresql"}
    if db_type is not None:
        db_type = db_type_mapping.get(db_type, db_type)

    config_params = config.get_db_connection_params()

    if db_type is None:
        db_type = kwargs.get("db_type")
    if host is None:
        host = config_params.get("host")
    if database is None:
        database = config_params.get("database")
    if user is None:
        user = config_params.get("user")
    if password is None:
        password = config_params.get("password")
    if port is None and "port" in config_params:
        port = config_params.get("port")
    if server is None and "server" in config_params:
        server = config_params.get("server")

    if isolation_level is None and db_type == "informix-sqli":
        if config.get("INFORMIX_DIRTY_READS", False):
            isolation_level = "DIRTY_READ"
        else:
            isolation_level = config.get("INFORMIX_ISOLATION_LEVEL")

    if not all([db_type, host, database, user, password]):
        raise ValueError(
            "Missing required connection parameters. "
            "Provide db_type, host, database, user, and password."
        )

    if db_type not in DEFAULT_DRIVERS:
        raise ValueError(f"Unsupported database type: {db_type}")

    driver_cfg = DEFAULT_DRIVERS[db_type]
    resolved_port = port or driver_cfg["default_port"]
    jar = driver_cfg["jar"]
    driver_class = driver_cfg["driver_class"]

    if db_type == "informix-sqli":
        if not server:
            raise ValueError("Informix requires the 'server' parameter")
        jdbc_url = (
            f"jdbc:informix-sqli://{host}:{resolved_port}/{database}"
            f":INFORMIXSERVER={server}"
        )
    else:
        jdbc_url = f"jdbc:{db_type}://{host}:{resolved_port}/{database}"

    if use_pool:
        pool_key = f"{db_type}:{host}:{resolved_port}:{database}:{user}"
        with _pools_lock:
            if pool_key not in _pools:
                _pools[pool_key] = ConnectionPool(
                    jdbc_url=jdbc_url,
                    driver_class=driver_class,
                    jars=[jar],
                    user=user,
                    password=password,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    checkout_timeout=checkout_timeout,
                    query_timeout_sec=query_timeout_sec,
                    slow_query_ms=slow_query_ms,
                    decimal_as_float=decimal_as_float,
                )
            pool = _pools[pool_key]
        conn = pool.acquire()
        conn.pool_key = pool_key
    else:
        start_jvm([jar])
        jpype = _get_jpype()
        jpype.JClass(driver_class)
        jconn = jpype.java.sql.DriverManager.getConnection(jdbc_url, user, password)
        jconn.setAutoCommit(False)
        conn = _PooledConn(jconn, None)

    if isolation_level in ("DIRTY_READ", "READ_UNCOMMITTED") and db_type == "informix-sqli":
        try:
            stmt = conn._jc.createStatement()
            stmt.execute("SET ISOLATION TO DIRTY READ")
            stmt.close()
        except Exception:
            pass

    return conn


# Export public API
__all__ = [
    # Legacy API (backward compatible)
    "connect_to_db",
    "start_jvm",
    "JDBCConnection",
    "JDBCCursor",
    "ConnectionError",
    "DEFAULT_DRIVERS",

    # Optimized API (new)
    "connect_optimized",
    "connect_optimized_stats",
    "OptimizedJDBCConnection",
    "OptimizedJDBCCursor",

    # Direct JDBC classes (JPype-native, no jaydebeapi lock)
    "_DirectCursor",
    "_PooledConn",
    "ConnectionPool",

    # Configuration and utilities
    "get_config",
    "Config",
    "get_logger",
    "get_metrics_collector",
    "get_pool",
    "close_all_pools",
    "get_schema_cache",
    "reset_cache",
    "TypeMapper",
    "JDBC_TYPES",

    # Version
    "__version__",
    "version",
]
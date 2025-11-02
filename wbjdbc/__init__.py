import os
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
__version__ = "2.0.0"


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
    **kwargs
):
    """
    Create an optimized JDBC connection with pooling, batching, and async support.

    This is the new optimized API that provides:
    - Connection pooling for better performance
    - Batch execution for bulk operations
    - Async query execution
    - Automatic type mapping (JDBC types to Python types)
    - Metadata caching
    - Query metrics and logging
    - Dirty reads support for Informix

    Args:
        db_type: Database type ("informix-sqli", "mysql", "postgresql", or 1-3)
        host: Database server address
        database: Database name
        user: Username
        password: Password
        port: Port (optional, uses default if not specified)
        server: Informix server name (required for Informix)
        use_pool: Use connection pooling (default: True)
        enable_type_mapping: Enable automatic JDBC to Python type conversion (default: True)
        isolation_level: Transaction isolation level (e.g., "DIRTY_READ" for Informix)
        config_file: Path to .env configuration file
        **kwargs: Additional configuration options

    Returns:
        OptimizedJDBCConnection: Enhanced connection with all optimization features

    Example:
        # Basic usage with pooling
        conn = connect_optimized(
            db_type="informix-sqli",
            host="myserver",
            database="mydb",
            user="myuser",
            password="mypass",
            server="informix_server"
        )

        # Execute query
        results = conn.execute_query("SELECT * FROM mytable")

        # Batch insert
        conn.execute_batch(
            "INSERT INTO mytable (col1, col2) VALUES (?, ?)",
            [(1, 'a'), (2, 'b'), (3, 'c')]
        )

        # Async query
        future = conn.execute_async("SELECT COUNT(*) FROM bigtable")
        result = future.result()  # Wait for completion

        # Dirty reads for Informix
        conn = connect_optimized(
            db_type="informix-sqli",
            host="myserver",
            database="mydb",
            user="myuser",
            password="mypass",
            server="informix_server",
            isolation_level="DIRTY_READ"
        )

        # Using context manager
        with connect_optimized(...) as conn:
            results = conn.execute_query("SELECT * FROM mytable")
            # Auto-commits on success, rolls back on error
    """
    # Load configuration
    config = get_config(config_file)

    # Maps integer values to strings
    db_type_mapping = {1: "informix-sqli", 2: "mysql", 3: "postgresql"}
    if db_type is not None:
        db_type = db_type_mapping.get(db_type, db_type)

    # Use config defaults if parameters not provided
    config_params = config.get_db_connection_params()

    if db_type is None:
        db_type = kwargs.get('db_type')
    if host is None:
        host = config_params.get('host')
    if database is None:
        database = config_params.get('database')
    if user is None:
        user = config_params.get('user')
    if password is None:
        password = config_params.get('password')
    if port is None and 'port' in config_params:
        port = config_params.get('port')
    if server is None and 'server' in config_params:
        server = config_params.get('server')

    # Check for Informix dirty reads config
    if isolation_level is None and db_type == "informix-sqli":
        if config.get('INFORMIX_DIRTY_READS', False):
            isolation_level = 'DIRTY_READ'
        else:
            isolation_level = config.get('INFORMIX_ISOLATION_LEVEL')

    # Validate required parameters
    if not all([db_type, host, database, user, password]):
        raise ValueError(
            "Missing required connection parameters. "
            "Provide db_type, host, database, user, and password, "
            "or configure them in .env file."
        )

    if db_type not in DEFAULT_DRIVERS:
        raise ValueError(f"Unsupported database type: {db_type}")

    # Create optimized connection
    return OptimizedJDBCConnection(
        db_type=db_type,
        host=host,
        database=database,
        user=user,
        password=password,
        port=port,
        server=server,
        use_pool=use_pool,
        enable_type_mapping=enable_type_mapping,
        isolation_level=isolation_level,
        **kwargs
    )


# Export public API
__all__ = [
    # Legacy API (backward compatible)
    'connect_to_db',
    'start_jvm',
    'JDBCConnection',
    'JDBCCursor',
    'ConnectionError',
    'DEFAULT_DRIVERS',

    # Optimized API (new)
    'connect_optimized',
    'OptimizedJDBCConnection',
    'OptimizedJDBCCursor',

    # Configuration and utilities
    'get_config',
    'Config',
    'get_logger',
    'get_metrics_collector',
    'get_pool',
    'close_all_pools',
    'get_schema_cache',
    'reset_cache',
    'TypeMapper',
    'JDBC_TYPES',

    # Version
    '__version__',
]
import os
from .jvm import start_jvm
import jaydebeapi

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
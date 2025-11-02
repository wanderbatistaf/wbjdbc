"""
Type mapping between JDBC and Python types.

Handles conversion of JDBC SQL types to appropriate Python types
and vice versa.
"""

from typing import Any, Optional
from datetime import datetime, date, time
from decimal import Decimal
import jpype


# JDBC SQL Type codes (from java.sql.Types)
JDBC_TYPES = {
    'BIT': -7,
    'TINYINT': -6,
    'SMALLINT': 5,
    'INTEGER': 4,
    'BIGINT': -5,
    'FLOAT': 6,
    'REAL': 7,
    'DOUBLE': 8,
    'NUMERIC': 2,
    'DECIMAL': 3,
    'CHAR': 1,
    'VARCHAR': 12,
    'LONGVARCHAR': -1,
    'DATE': 91,
    'TIME': 92,
    'TIMESTAMP': 93,
    'BINARY': -2,
    'VARBINARY': -3,
    'LONGVARBINARY': -4,
    'NULL': 0,
    'BOOLEAN': 16,
    'NCHAR': -15,
    'NVARCHAR': -9,
    'LONGNVARCHAR': -16,
    'CLOB': 2005,
    'BLOB': 2004,
}


class TypeMapper:
    """Maps between JDBC and Python types."""

    @staticmethod
    def jdbc_to_python(value: Any, jdbc_type: Optional[int] = None) -> Any:
        """
        Convert JDBC value to Python type.

        Args:
            value: Value from JDBC
            jdbc_type: JDBC type code (optional)

        Returns:
            Python-native value
        """
        if value is None:
            return None

        # Handle JPype Java objects
        if jpype.isJVMStarted():
            # Convert java.sql.Date to Python date
            try:
                if isinstance(value, jpype.java.sql.Date):
                    # Convert to milliseconds and then to Python date
                    millis = value.getTime()
                    return datetime.fromtimestamp(millis / 1000.0).date()
            except (AttributeError, TypeError):
                pass

            # Convert java.sql.Time to Python time
            try:
                if isinstance(value, jpype.java.sql.Time):
                    millis = value.getTime()
                    dt = datetime.fromtimestamp(millis / 1000.0)
                    return dt.time()
            except (AttributeError, TypeError):
                pass

            # Convert java.sql.Timestamp to Python datetime
            try:
                if isinstance(value, jpype.java.sql.Timestamp):
                    millis = value.getTime()
                    return datetime.fromtimestamp(millis / 1000.0)
            except (AttributeError, TypeError):
                pass

            # Convert java.math.BigDecimal to Python Decimal
            try:
                if isinstance(value, jpype.java.math.BigDecimal):
                    return Decimal(str(value))
            except (AttributeError, TypeError):
                pass

            # Convert Java Boolean to Python bool
            try:
                if isinstance(value, jpype.java.lang.Boolean):
                    return bool(value.booleanValue())
            except (AttributeError, TypeError):
                pass

            # Convert Java numbers to Python numbers
            try:
                if isinstance(value, (jpype.java.lang.Integer,
                                     jpype.java.lang.Long,
                                     jpype.java.lang.Short,
                                     jpype.java.lang.Byte)):
                    return int(value.longValue())
            except (AttributeError, TypeError):
                pass

            try:
                if isinstance(value, (jpype.java.lang.Float,
                                     jpype.java.lang.Double)):
                    return float(value.doubleValue())
            except (AttributeError, TypeError):
                pass

            # Convert byte arrays
            try:
                if isinstance(value, jpype.JArray):
                    return bytes(value)
            except (AttributeError, TypeError):
                pass

        # If no specific conversion, return as-is
        return value

    @staticmethod
    def python_to_jdbc(value: Any) -> Any:
        """
        Convert Python value to JDBC-compatible type.

        Args:
            value: Python value

        Returns:
            JDBC-compatible value
        """
        if value is None:
            return None

        # Python date to java.sql.Date
        if isinstance(value, date) and not isinstance(value, datetime):
            if jpype.isJVMStarted():
                millis = int(datetime.combine(value, time()).timestamp() * 1000)
                return jpype.java.sql.Date(millis)
            return value

        # Python time to java.sql.Time
        if isinstance(value, time):
            if jpype.isJVMStarted():
                dt = datetime.combine(date.today(), value)
                millis = int(dt.timestamp() * 1000)
                return jpype.java.sql.Time(millis)
            return value

        # Python datetime to java.sql.Timestamp
        if isinstance(value, datetime):
            if jpype.isJVMStarted():
                millis = int(value.timestamp() * 1000)
                return jpype.java.sql.Timestamp(millis)
            return value

        # Python Decimal to java.math.BigDecimal
        if isinstance(value, Decimal):
            if jpype.isJVMStarted():
                return jpype.java.math.BigDecimal(str(value))
            return float(value)

        # Python bool to Java Boolean
        if isinstance(value, bool):
            if jpype.isJVMStarted():
                return jpype.java.lang.Boolean(value)
            return value

        # Python bytes to byte array
        if isinstance(value, bytes):
            if jpype.isJVMStarted():
                return jpype.JArray(jpype.JByte)(list(value))
            return value

        # For other types, return as-is
        return value

    @staticmethod
    def get_python_type_name(jdbc_type: int) -> str:
        """
        Get Python type name for JDBC type code.

        Args:
            jdbc_type: JDBC type code

        Returns:
            Python type name as string
        """
        type_map = {
            JDBC_TYPES['BIT']: 'bool',
            JDBC_TYPES['TINYINT']: 'int',
            JDBC_TYPES['SMALLINT']: 'int',
            JDBC_TYPES['INTEGER']: 'int',
            JDBC_TYPES['BIGINT']: 'int',
            JDBC_TYPES['FLOAT']: 'float',
            JDBC_TYPES['REAL']: 'float',
            JDBC_TYPES['DOUBLE']: 'float',
            JDBC_TYPES['NUMERIC']: 'Decimal',
            JDBC_TYPES['DECIMAL']: 'Decimal',
            JDBC_TYPES['CHAR']: 'str',
            JDBC_TYPES['VARCHAR']: 'str',
            JDBC_TYPES['LONGVARCHAR']: 'str',
            JDBC_TYPES['NCHAR']: 'str',
            JDBC_TYPES['NVARCHAR']: 'str',
            JDBC_TYPES['LONGNVARCHAR']: 'str',
            JDBC_TYPES['DATE']: 'date',
            JDBC_TYPES['TIME']: 'time',
            JDBC_TYPES['TIMESTAMP']: 'datetime',
            JDBC_TYPES['BINARY']: 'bytes',
            JDBC_TYPES['VARBINARY']: 'bytes',
            JDBC_TYPES['LONGVARBINARY']: 'bytes',
            JDBC_TYPES['BOOLEAN']: 'bool',
            JDBC_TYPES['CLOB']: 'str',
            JDBC_TYPES['BLOB']: 'bytes',
        }
        return type_map.get(jdbc_type, 'Any')

    @staticmethod
    def convert_row(row: tuple, column_types: Optional[list] = None) -> tuple:
        """
        Convert a complete row from JDBC to Python types.

        Args:
            row: Row tuple from JDBC
            column_types: Optional list of JDBC type codes

        Returns:
            Converted row tuple
        """
        if row is None:
            return None

        if column_types:
            return tuple(
                TypeMapper.jdbc_to_python(value, jdbc_type)
                for value, jdbc_type in zip(row, column_types)
            )
        else:
            return tuple(TypeMapper.jdbc_to_python(value) for value in row)

    @staticmethod
    def convert_params(params: tuple) -> tuple:
        """
        Convert Python parameters to JDBC-compatible types.

        Args:
            params: Parameter tuple

        Returns:
            Converted parameter tuple
        """
        if params is None:
            return None

        return tuple(TypeMapper.python_to_jdbc(param) for param in params)

"""
Basic usage examples for wbjdbc optimized features.

This demonstrates the fundamental operations with the new optimized API.
"""

from wbjdbc import connect_optimized


def example_basic_connection():
    """Basic connection with pooling."""
    print("=== Basic Connection Example ===\n")

    # Create connection with pooling (default)
    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Execute a simple query
    results = conn.execute_query("SELECT * FROM customers LIMIT 10")

    print(f"Retrieved {len(results)} rows")
    for row in results[:3]:  # Show first 3
        print(row)

    conn.close()
    print("\n✅ Connection closed\n")


def example_context_manager():
    """Using connection as context manager (auto-commit/rollback)."""
    print("=== Context Manager Example ===\n")

    # Using 'with' statement for automatic resource management
    with connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    ) as conn:
        # Execute query
        results = conn.execute_query("SELECT COUNT(*) as total FROM orders")
        print(f"Total orders: {results[0]['total']}")

        # Changes are automatically committed on success
        # or rolled back on exception

    print("✅ Connection auto-closed\n")


def example_cursor_operations():
    """Using cursor for more control."""
    print("=== Cursor Operations Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    cursor = conn.cursor()

    # Execute query
    cursor.execute("SELECT id, name, email FROM users WHERE active = ?", (True,))

    # Fetch one row at a time
    print("Fetching rows one by one:")
    row = cursor.fetchone()
    while row:
        print(f"  ID: {row[0]}, Name: {row[1]}, Email: {row[2]}")
        row = cursor.fetchone()
        if row and row[0] > 5:  # Stop after ID 5 for demo
            break

    cursor.close()
    conn.close()
    print("\n✅ Done\n")


def example_dict_results():
    """Getting results as dictionaries."""
    print("=== Dictionary Results Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products LIMIT 5")

    # Fetch as list of dictionaries
    products = cursor.fetchdh()

    for product in products:
        print(f"Product: {product['name']} - ${product['price']}")

    cursor.close()
    conn.close()
    print("\n✅ Done\n")


def example_type_mapping():
    """Automatic type conversion between JDBC and Python."""
    print("=== Type Mapping Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
        enable_type_mapping=True  # Enabled by default
    )

    cursor = conn.cursor()

    # Dates, times, decimals, etc. are automatically converted to Python types
    cursor.execute("""
        SELECT
            order_id,
            order_date,      -- java.sql.Date -> datetime.date
            order_time,      -- java.sql.Time -> datetime.time
            order_timestamp, -- java.sql.Timestamp -> datetime.datetime
            total_amount,    -- java.math.BigDecimal -> decimal.Decimal
            is_paid          -- java.lang.Boolean -> bool
        FROM orders
        LIMIT 5
    """)

    orders = cursor.fetchdh()

    for order in orders:
        print(f"Order {order['order_id']}:")
        print(f"  Date: {order['order_date']} (type: {type(order['order_date']).__name__})")
        print(f"  Amount: {order['total_amount']} (type: {type(order['total_amount']).__name__})")
        print(f"  Paid: {order['is_paid']} (type: {type(order['is_paid']).__name__})")

    cursor.close()
    conn.close()
    print("\n✅ Done\n")


if __name__ == "__main__":
    print("WBJDBC Optimized - Basic Usage Examples\n")
    print("=" * 60)
    print()

    # Note: These examples assume you have a configured .env file
    # or you replace the connection parameters with your actual values

    try:
        example_basic_connection()
    except Exception as e:
        print(f"❌ Example failed: {e}\n")

    try:
        example_context_manager()
    except Exception as e:
        print(f"❌ Example failed: {e}\n")

    try:
        example_cursor_operations()
    except Exception as e:
        print(f"❌ Example failed: {e}\n")

    try:
        example_dict_results()
    except Exception as e:
        print(f"❌ Example failed: {e}\n")

    try:
        example_type_mapping()
    except Exception as e:
        print(f"❌ Example failed: {e}\n")

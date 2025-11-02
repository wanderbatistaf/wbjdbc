"""
Advanced features examples for wbjdbc optimized.

Demonstrates batch operations, async queries, caching, and metrics.
"""

import time
from concurrent.futures import as_completed
from wbjdbc import connect_optimized, get_metrics_collector


def example_batch_insert():
    """Batch insert for high-performance bulk loading."""
    print("=== Batch Insert Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Prepare data for batch insert
    # In real scenario, this might be thousands or millions of rows
    data = [
        (i, f'Product {i}', 10.0 + i, True)
        for i in range(1, 10001)  # 10,000 rows
    ]

    print(f"Inserting {len(data)} rows in batches...")
    start_time = time.time()

    # Batch insert - automatically splits into batches and commits at intervals
    rows_affected = conn.execute_batch(
        "INSERT INTO products (id, name, price, active) VALUES (?, ?, ?, ?)",
        data,
        batch_size=1000,      # 1000 rows per batch
        commit_interval=5000  # Commit every 5000 rows
    )

    duration = time.time() - start_time

    print(f"✅ Inserted {rows_affected} rows in {duration:.2f} seconds")
    print(f"   ({rows_affected/duration:.0f} rows/second)\n")

    conn.close()


def example_batch_update():
    """Batch update for efficient bulk updates."""
    print("=== Batch Update Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Prepare update data
    updates = [
        (15.0 + i, i) for i in range(1, 1001)  # Update 1000 products
    ]

    print(f"Updating {len(updates)} rows in batches...")
    start_time = time.time()

    rows_affected = conn.execute_batch(
        "UPDATE products SET price = ? WHERE id = ?",
        updates,
        batch_size=500
    )

    duration = time.time() - start_time

    print(f"✅ Updated {rows_affected} rows in {duration:.2f} seconds\n")

    conn.close()


def example_async_queries():
    """Execute multiple queries concurrently."""
    print("=== Async Queries Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Define multiple queries to run concurrently
    queries = [
        "SELECT COUNT(*) as total FROM products",
        "SELECT COUNT(*) as total FROM orders",
        "SELECT COUNT(*) as total FROM customers",
        "SELECT AVG(price) as avg_price FROM products",
        "SELECT SUM(total_amount) as revenue FROM orders",
    ]

    print(f"Executing {len(queries)} queries concurrently...")
    start_time = time.time()

    # Submit all queries asynchronously
    futures = []
    for query in queries:
        future = conn.execute_async(query)
        futures.append((query, future))

    # Collect results as they complete
    for query, future in futures:
        result = future.result()  # Wait for completion
        print(f"  {query[:50]}... => {result}")

    duration = time.time() - start_time

    print(f"\n✅ Completed {len(queries)} queries in {duration:.2f} seconds\n")

    conn.close()


def example_async_concurrent():
    """Process multiple async queries with progress tracking."""
    print("=== Async Concurrent Processing Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Simulate processing data from multiple tables
    table_queries = {
        'products': "SELECT * FROM products WHERE category = 'Electronics'",
        'orders': "SELECT * FROM orders WHERE order_date >= CURRENT - 7 UNITS DAY",
        'customers': "SELECT * FROM customers WHERE active = 1",
        'inventory': "SELECT * FROM inventory WHERE quantity < 10",
        'reviews': "SELECT * FROM reviews WHERE rating >= 4",
    }

    print(f"Processing {len(table_queries)} tables concurrently...")
    start_time = time.time()

    # Submit all queries
    futures = {}
    for table_name, query in table_queries.items():
        future = conn.execute_async(query)
        futures[future] = table_name

    # Process results as they complete
    completed = 0
    for future in as_completed(futures):
        table_name = futures[future]
        try:
            result = future.result()
            completed += 1
            print(f"  [{completed}/{len(futures)}] {table_name}: {len(result)} rows")
        except Exception as e:
            print(f"  ❌ {table_name} failed: {e}")

    duration = time.time() - start_time

    print(f"\n✅ Processed all tables in {duration:.2f} seconds\n")

    conn.close()


def example_metadata_caching():
    """Using metadata caching for schema information."""
    print("=== Metadata Caching Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    print("First call - fetches from database:")
    start_time = time.time()
    columns = conn.get_table_columns('products')
    duration1 = time.time() - start_time

    print(f"  Retrieved {len(columns)} columns in {duration1*1000:.2f}ms")
    for col in columns[:3]:
        print(f"    - {col['name']} ({col['type_name']})")

    print("\nSecond call - fetches from cache:")
    start_time = time.time()
    columns = conn.get_table_columns('products')
    duration2 = time.time() - start_time

    print(f"  Retrieved {len(columns)} columns in {duration2*1000:.2f}ms")

    speedup = duration1 / duration2 if duration2 > 0 else float('inf')
    print(f"\n✅ Cache is {speedup:.1f}x faster!\n")

    conn.close()


def example_metrics_collection():
    """Collecting and viewing performance metrics."""
    print("=== Metrics Collection Example ===\n")

    # Get metrics collector
    metrics = get_metrics_collector()

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server"
    )

    # Execute some operations
    print("Executing various operations to collect metrics...\n")

    conn.execute_query("SELECT * FROM products LIMIT 100")
    conn.execute_query("SELECT * FROM orders LIMIT 50")
    conn.execute_query("SELECT COUNT(*) FROM customers")

    # Batch operation
    conn.execute_batch(
        "INSERT INTO test_table (id, value) VALUES (?, ?)",
        [(i, f'value{i}') for i in range(100)],
        batch_size=50
    )

    # Get metrics
    stats = metrics.get_metrics()

    print("Current Metrics:")
    print(f"  Uptime: {stats['uptime_seconds']:.1f} seconds")
    print(f"\n  Queries:")
    print(f"    Total: {stats['queries']['total']}")
    print(f"    Failed: {stats['queries']['failed']}")
    print(f"    Success Rate: {stats['queries']['success_rate']*100:.1f}%")
    print(f"    Average Time: {stats['queries']['average_time']*1000:.2f}ms")
    print(f"    P95 Time: {stats['queries']['p95_time']*1000:.2f}ms")
    print(f"\n  Connections:")
    print(f"    Created: {stats['connections']['created']}")
    print(f"    Reused: {stats['connections']['reused']}")
    print(f"    Reuse Rate: {stats['connections']['reuse_rate']*100:.1f}%")
    print(f"\n  Cache:")
    print(f"    Hits: {stats['cache']['hits']}")
    print(f"    Misses: {stats['cache']['misses']}")
    print(f"    Hit Rate: {stats['cache']['hit_rate']*100:.1f}%")
    print(f"\n  Batch Operations: {stats['batch_operations']}")

    # Export metrics to file
    json_metrics = metrics.export_metrics('wbjdbc_metrics.json')
    print(f"\n✅ Metrics exported to wbjdbc_metrics.json\n")

    conn.close()


def example_dirty_reads_informix():
    """Using dirty reads for better read performance (Informix)."""
    print("=== Dirty Reads Example (Informix) ===\n")

    # Connect with dirty reads enabled
    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
        isolation_level="DIRTY_READ"  # Enable dirty reads
    )

    print("Dirty reads enabled - can read uncommitted data")
    print("This provides better performance for reporting queries\n")

    # Execute a long-running query without being blocked by locks
    start_time = time.time()
    results = conn.execute_query("""
        SELECT
            customer_id,
            COUNT(*) as order_count,
            SUM(total_amount) as total_revenue
        FROM orders
        WHERE order_date >= CURRENT - 365 UNITS DAY
        GROUP BY customer_id
        ORDER BY total_revenue DESC
        LIMIT 100
    """)
    duration = time.time() - start_time

    print(f"✅ Query completed in {duration:.2f} seconds")
    print(f"   Retrieved {len(results)} customers")
    print(f"   Top customer revenue: ${results[0]['total_revenue']:.2f}\n")

    conn.close()


if __name__ == "__main__":
    print("WBJDBC Optimized - Advanced Features Examples\n")
    print("=" * 60)
    print()

    # Note: These examples assume you have configured database connection
    # parameters in .env file or replace them with actual values

    examples = [
        ("Batch Insert", example_batch_insert),
        ("Batch Update", example_batch_update),
        ("Async Queries", example_async_queries),
        ("Async Concurrent", example_async_concurrent),
        ("Metadata Caching", example_metadata_caching),
        ("Metrics Collection", example_metrics_collection),
        ("Dirty Reads (Informix)", example_dirty_reads_informix),
    ]

    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"❌ {name} example failed: {e}\n")

    print("=" * 60)
    print("All examples completed!")

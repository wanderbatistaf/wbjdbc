"""
Production-hardening examples for wbjdbc: retry/reconnect, SSL/TLS, DB-API
exceptions, real async support, Prometheus metrics, stored procedures, LOB
streaming, and savepoints.

These complement examples/basic_usage.py and examples/advanced_features.py.
"""

import asyncio
import time
from wbjdbc import connect_optimized, get_metrics_collector, IntegrityError, OperationalError
from wbjdbc.aio import async_db_conn


def example_retry_and_ssl():
    """Automatic retry with backoff on connect, and SSL/TLS on the JDBC URL."""
    print("=== Retry & SSL Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
        max_retries=3,      # retries only the connect step, never a query
        retry_delay=1.0,    # linear backoff: 1s, 2s, 3s...
        ssl_enabled=True,   # appends SSL params for the given db_type
        ssl_verify=True,
    )

    print("[OK] Connected (with retry/SSL configured)\n")
    conn.close()


def example_exceptions():
    """Catching specific DB-API 2.0 errors instead of a bare Exception."""
    print("=== Exceptions Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
    )

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO customers (id) VALUES (?)", (1,))
        conn.commit()
    except IntegrityError as e:
        print(f"  Constraint violation ({e.sqlstate}): {e}")
        conn.rollback()
    except OperationalError:
        print("  Connection lost - safe to retry the whole operation")
        raise

    conn.close()
    print("\n[OK] Done\n")


async def _async_main():
    async with async_db_conn(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
    ) as conn:
        cursor = conn.cursor()
        await cursor.execute("SELECT * FROM customers LIMIT 10")
        rows = await cursor.fetchdh()
        print(f"  Retrieved {len(rows)} rows without blocking the event loop")

        # execute_batch/get_table_columns are async too
        columns = await conn.get_table_columns("customers")
        print(f"  Table has {len(columns)} columns")


def example_real_async():
    """Real async/await - nothing in this block blocks the event loop."""
    print("=== Real Async Example ===\n")
    asyncio.run(_async_main())
    print("\n[OK] Done\n")


def example_prometheus_metrics():
    """Prometheus text exposition format for scraping."""
    print("=== Prometheus Metrics Example ===\n")

    metrics = get_metrics_collector()
    print(metrics.export_prometheus())

    # Wire this into your own web framework, e.g. Flask:
    #
    # @app.route("/metrics")
    # def metrics_endpoint():
    #     return get_metrics_collector().export_prometheus(), 200, \
    #         {"Content-Type": "text/plain; version=0.0.4"}


def example_stored_procedure():
    """Calling a stored procedure with IN, OUT and result-set returns."""
    print("=== Stored Procedure Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
    )

    # Procedure with an OUT parameter: PROCEDURE total_for_customer(IN id, OUT total)
    # java.sql.Types.DECIMAL == 3 (see wbjdbc.types.JDBC_TYPES for the full table)
    cursor = conn.cursor()
    out_values = cursor.callproc("total_for_customer", [42, None], out_types={2: 3})
    print(f"  Customer 42 total: {out_values[0]}")

    # Procedure that returns a result set is fetched like a SELECT afterwards
    cursor.callproc("list_active_customers")
    for row in cursor.fetchdh():
        print(f"  {row}")

    conn.close()
    print("\n[OK] Done\n")


def example_lob_streaming():
    """Reading a large BLOB/CLOB column without loading it fully into memory."""
    print("=== LOB Streaming Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
    )

    cursor = conn.cursor()
    # stream_lobs=True: BLOB/CLOB columns become LobHandle objects instead of being
    # materialized in memory - valid to read any time before the next commit/rollback.
    cursor.execute("SELECT id, document FROM documents WHERE id = ?", (1,), stream_lobs=True)
    row = cursor.fetchone()
    doc_id, document = row

    with open(f"document_{doc_id}.bin", "wb") as f:
        for chunk in document.stream(chunk_size=64 * 1024):
            f.write(chunk)
    document.close()

    conn.close()
    print(f"  Streamed document {doc_id} to disk in 64KB chunks\n")
    print("[OK] Done\n")


def example_savepoints():
    """Partial rollback within a transaction using savepoints."""
    print("=== Savepoints Example ===\n")

    conn = connect_optimized(
        db_type="informix-sqli",
        host="myserver",
        database="mydb",
        user="myuser",
        password="mypassword",
        server="informix_server",
    )

    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (id, status) VALUES (?, ?)", (1, "pending"))

    try:
        with conn.savepoint_scope("before_risky_update"):
            cursor.execute("UPDATE inventory SET qty = qty - 1 WHERE id = ?", (999,))
            # if this raises (e.g. constraint violation), only the UPDATE above is
            # undone - the order INSERT above is kept
    except IntegrityError:
        print("  Risky update failed, rolled back to savepoint - order still stands")

    conn.commit()
    conn.close()
    print("\n[OK] Done\n")


if __name__ == "__main__":
    print("WBJDBC - Production Features Examples\n")
    print("=" * 60)
    print()

    examples = [
        ("Retry & SSL", example_retry_and_ssl),
        ("Exceptions", example_exceptions),
        ("Real Async", example_real_async),
        ("Prometheus Metrics", example_prometheus_metrics),
        ("Stored Procedure", example_stored_procedure),
        ("LOB Streaming", example_lob_streaming),
        ("Savepoints", example_savepoints),
    ]

    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"[ERROR] {name} example failed: {e}\n")

    print("=" * 60)
    print("All examples completed!")

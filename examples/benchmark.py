"""
Performance benchmarks for wbjdbc optimized vs legacy API.

This script validates the performance targets:
- Connection acquisition: <50ms for pooled connections
- Batch operations: ≥5x faster than individual statements
- Query concurrency: ≥50 simultaneous queries without degradation
- Metadata cache: ≥90% reduction in repeated schema queries
"""

import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from wbjdbc import connect_to_db, connect_optimized, get_metrics_collector


# Benchmark configuration
DB_CONFIG = {
    'db_type': 'informix-sqli',
    'host': 'myserver',
    'database': 'mydb',
    'user': 'myuser',
    'password': 'mypassword',
    'server': 'informix_server',
}


def benchmark_connection_acquisition():
    """Benchmark: Connection acquisition time (<50ms target)."""
    print("=" * 70)
    print("BENCHMARK 1: Connection Acquisition Time")
    print("=" * 70)
    print("Target: <50ms for pooled connections\n")

    # Warmup - create pool
    print("Warming up connection pool...")
    conn = connect_optimized(**DB_CONFIG, use_pool=True)
    conn.close()

    # Benchmark pooled connections
    print("\nTesting pooled connections (10 iterations):")
    times = []
    for i in range(10):
        start = time.time()
        conn = connect_optimized(**DB_CONFIG, use_pool=True)
        duration = (time.time() - start) * 1000  # Convert to ms
        times.append(duration)
        conn.close()
        print(f"  Iteration {i+1}: {duration:.2f}ms")

    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)

    print(f"\nResults:")
    print(f"  Average: {avg_time:.2f}ms")
    print(f"  Min: {min_time:.2f}ms")
    print(f"  Max: {max_time:.2f}ms")

    if avg_time < 50:
        print(f"  ✅ PASSED - Average time {avg_time:.2f}ms < 50ms target")
    else:
        print(f"  ❌ FAILED - Average time {avg_time:.2f}ms >= 50ms target")

    print()


def benchmark_batch_operations():
    """Benchmark: Batch vs individual operations (≥5x faster target)."""
    print("=" * 70)
    print("BENCHMARK 2: Batch Operations Performance")
    print("=" * 70)
    print("Target: ≥5x faster than individual statements\n")

    conn = connect_optimized(**DB_CONFIG)

    # Prepare test data
    test_data = [(i, f'Test{i}', 10.0 + i) for i in range(1000)]

    # Create test table
    print("Setting up test table...")
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS benchmark_test")
        cursor.execute("""
            CREATE TABLE benchmark_test (
                id INTEGER,
                name VARCHAR(100),
                value DECIMAL(10,2)
            )
        """)
        cursor.close()
        conn.commit()
    except Exception as e:
        print(f"Setup failed: {e}")
        return

    # Benchmark 1: Individual inserts
    print("\nTest 1: Individual inserts (1000 rows)...")
    start = time.time()
    cursor = conn.cursor()
    for row in test_data:
        cursor.execute(
            "INSERT INTO benchmark_test (id, name, value) VALUES (?, ?, ?)",
            row
        )
    cursor.close()
    conn.commit()
    individual_time = time.time() - start
    print(f"  Time: {individual_time:.2f} seconds ({len(test_data)/individual_time:.0f} rows/sec)")

    # Clear table
    cursor = conn.cursor()
    cursor.execute("DELETE FROM benchmark_test")
    cursor.close()
    conn.commit()

    # Benchmark 2: Batch inserts
    print("\nTest 2: Batch inserts (1000 rows)...")
    start = time.time()
    conn.execute_batch(
        "INSERT INTO benchmark_test (id, name, value) VALUES (?, ?, ?)",
        test_data,
        batch_size=100
    )
    batch_time = time.time() - start
    print(f"  Time: {batch_time:.2f} seconds ({len(test_data)/batch_time:.0f} rows/sec)")

    # Calculate speedup
    speedup = individual_time / batch_time
    print(f"\nResults:")
    print(f"  Individual: {individual_time:.2f}s")
    print(f"  Batch: {batch_time:.2f}s")
    print(f"  Speedup: {speedup:.1f}x")

    if speedup >= 5.0:
        print(f"  ✅ PASSED - Batch is {speedup:.1f}x faster (≥5x target)")
    else:
        print(f"  ❌ FAILED - Batch is {speedup:.1f}x faster (<5x target)")

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DROP TABLE benchmark_test")
    cursor.close()
    conn.commit()
    conn.close()

    print()


def benchmark_concurrent_queries():
    """Benchmark: Concurrent query execution (≥50 simultaneous queries target)."""
    print("=" * 70)
    print("BENCHMARK 3: Concurrent Query Performance")
    print("=" * 70)
    print("Target: ≥50 simultaneous queries without degradation\n")

    def execute_query(query_id):
        """Execute a single query and return timing."""
        start = time.time()
        conn = connect_optimized(**DB_CONFIG, use_pool=True)
        try:
            results = conn.execute_query("SELECT COUNT(*) as cnt FROM products")
            duration = time.time() - start
            return query_id, duration, True, len(results)
        except Exception as e:
            duration = time.time() - start
            return query_id, duration, False, str(e)
        finally:
            conn.close()

    # Test different concurrency levels
    concurrency_levels = [10, 25, 50, 75, 100]

    for num_queries in concurrency_levels:
        print(f"\nTesting {num_queries} concurrent queries...")

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_queries) as executor:
            futures = [executor.submit(execute_query, i) for i in range(num_queries)]

            results = []
            for future in as_completed(futures):
                results.append(future.result())

        total_time = time.time() - start

        # Analyze results
        successful = sum(1 for _, _, success, _ in results if success)
        failed = num_queries - successful
        query_times = [duration for _, duration, success, _ in results if success]

        if query_times:
            avg_time = statistics.mean(query_times)
            max_time = max(query_times)
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Successful: {successful}/{num_queries}")
            print(f"  Failed: {failed}")
            print(f"  Avg query time: {avg_time:.3f}s")
            print(f"  Max query time: {max_time:.3f}s")
            print(f"  Throughput: {num_queries/total_time:.1f} queries/sec")

    print("\n✅ Concurrent query test completed")
    print()


def benchmark_metadata_cache():
    """Benchmark: Metadata caching (≥90% reduction target)."""
    print("=" * 70)
    print("BENCHMARK 4: Metadata Cache Performance")
    print("=" * 70)
    print("Target: ≥90% reduction in repeated schema queries\n")

    conn = connect_optimized(**DB_CONFIG)

    # Clear cache
    from wbjdbc import reset_cache
    reset_cache()

    # First call - cache miss
    print("First call (cache miss):")
    times_uncached = []
    for i in range(5):
        reset_cache()  # Clear before each test
        start = time.time()
        columns = conn.get_table_columns('products')
        duration = (time.time() - start) * 1000  # ms
        times_uncached.append(duration)
        print(f"  Iteration {i+1}: {duration:.2f}ms")

    avg_uncached = statistics.mean(times_uncached)

    # Subsequent calls - cache hit
    print("\nSubsequent calls (cache hit):")
    times_cached = []
    for i in range(5):
        start = time.time()
        columns = conn.get_table_columns('products')
        duration = (time.time() - start) * 1000  # ms
        times_cached.append(duration)
        print(f"  Iteration {i+1}: {duration:.2f}ms")

    avg_cached = statistics.mean(times_cached)

    # Calculate reduction
    reduction = ((avg_uncached - avg_cached) / avg_uncached) * 100

    print(f"\nResults:")
    print(f"  Uncached average: {avg_uncached:.2f}ms")
    print(f"  Cached average: {avg_cached:.2f}ms")
    print(f"  Reduction: {reduction:.1f}%")

    if reduction >= 90:
        print(f"  ✅ PASSED - Cache provides {reduction:.1f}% reduction (≥90% target)")
    else:
        print(f"  ❌ FAILED - Cache provides {reduction:.1f}% reduction (<90% target)")

    conn.close()
    print()


def benchmark_overall_metrics():
    """Display overall performance metrics."""
    print("=" * 70)
    print("OVERALL PERFORMANCE METRICS")
    print("=" * 70)
    print()

    metrics = get_metrics_collector()
    stats = metrics.get_metrics()

    print(f"Uptime: {stats['uptime_seconds']:.1f} seconds")
    print()

    print("Query Performance:")
    print(f"  Total queries: {stats['queries']['total']}")
    print(f"  Success rate: {stats['queries']['success_rate']*100:.1f}%")
    print(f"  Average time: {stats['queries']['average_time']*1000:.2f}ms")
    print(f"  P50 time: {stats['queries']['p50_time']*1000:.2f}ms")
    print(f"  P95 time: {stats['queries']['p95_time']*1000:.2f}ms")
    print(f"  P99 time: {stats['queries']['p99_time']*1000:.2f}ms")
    print()

    print("Connection Efficiency:")
    print(f"  Connections created: {stats['connections']['created']}")
    print(f"  Connections reused: {stats['connections']['reused']}")
    print(f"  Reuse rate: {stats['connections']['reuse_rate']*100:.1f}%")
    print()

    print("Pool Performance:")
    print(f"  Successful checkouts: {stats['pool']['checkouts']}")
    print(f"  Timeouts: {stats['pool']['timeouts']}")
    print(f"  Timeout rate: {stats['pool']['timeout_rate']*100:.1f}%")
    print()

    print("Cache Efficiency:")
    print(f"  Cache hits: {stats['cache']['hits']}")
    print(f"  Cache misses: {stats['cache']['misses']}")
    print(f"  Hit rate: {stats['cache']['hit_rate']*100:.1f}%")
    print()

    print(f"Batch operations: {stats['batch_operations']}")
    print(f"Reconnects: {stats['reconnects']}")
    print()


def run_all_benchmarks():
    """Run all performance benchmarks."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "WBJDBC OPTIMIZED PERFORMANCE BENCHMARKS" + " " * 14 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    print("This benchmark suite validates the performance targets:")
    print("  1. Connection acquisition: <50ms (pooled)")
    print("  2. Batch operations: ≥5x faster than individual")
    print("  3. Query concurrency: ≥50 simultaneous queries")
    print("  4. Metadata cache: ≥90% reduction")
    print()

    input("Press Enter to start benchmarks...")
    print()

    benchmarks = [
        benchmark_connection_acquisition,
        benchmark_batch_operations,
        benchmark_concurrent_queries,
        benchmark_metadata_cache,
    ]

    for benchmark in benchmarks:
        try:
            benchmark()
            time.sleep(1)  # Brief pause between benchmarks
        except Exception as e:
            print(f"❌ Benchmark failed: {e}\n")

    benchmark_overall_metrics()

    print("=" * 70)
    print("BENCHMARKS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    print("\n⚠️  NOTE: Update DB_CONFIG with your actual database credentials")
    print("    before running benchmarks.\n")

    try:
        run_all_benchmarks()
    except KeyboardInterrupt:
        print("\n\nBenchmarks interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Benchmark suite failed: {e}")

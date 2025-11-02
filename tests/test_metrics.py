"""
Tests for metrics collection.
"""

import time
import pytest
from wbjdbc.metrics import MetricsCollector


def test_metrics_initialization():
    """Test metrics collector initialization."""
    metrics = MetricsCollector()

    stats = metrics.get_metrics()

    assert stats['queries']['total'] == 0
    assert stats['queries']['failed'] == 0
    assert stats['connections']['created'] == 0
    assert stats['batch_operations'] == 0
    assert stats['cache']['hits'] == 0


def test_record_query_success():
    """Test recording successful query."""
    metrics = MetricsCollector()

    metrics.record_query("SELECT * FROM table", 0.1, success=True)

    stats = metrics.get_metrics()
    assert stats['queries']['total'] == 1
    assert stats['queries']['failed'] == 0
    assert stats['queries']['average_time'] > 0


def test_record_query_failure():
    """Test recording failed query."""
    metrics = MetricsCollector()

    metrics.record_query("SELECT * FROM table", 0.1, success=False)

    stats = metrics.get_metrics()
    assert stats['queries']['total'] == 0
    assert stats['queries']['failed'] == 1


def test_query_timing_statistics():
    """Test query timing statistics calculation."""
    metrics = MetricsCollector()

    # Record multiple queries with different times
    times = [0.1, 0.2, 0.3, 0.4, 0.5]
    for t in times:
        metrics.record_query("SELECT", t, success=True)

    stats = metrics.get_metrics()

    assert stats['queries']['total'] == 5
    assert stats['queries']['average_time'] == pytest.approx(0.3, rel=0.01)
    assert stats['queries']['min_time'] == 0.1
    assert stats['queries']['max_time'] == 0.5


def test_record_connection():
    """Test recording connection events."""
    metrics = MetricsCollector()

    metrics.record_connection(success=True, reused=False)
    metrics.record_connection(success=True, reused=True)
    metrics.record_connection(success=False)

    stats = metrics.get_metrics()

    assert stats['connections']['created'] == 1
    assert stats['connections']['reused'] == 1
    assert stats['connections']['failed'] == 1


def test_connection_reuse_rate():
    """Test connection reuse rate calculation."""
    metrics = MetricsCollector()

    # 1 created, 9 reused = 90% reuse rate
    metrics.record_connection(success=True, reused=False)
    for _ in range(9):
        metrics.record_connection(success=True, reused=True)

    stats = metrics.get_metrics()

    assert stats['connections']['created'] == 1
    assert stats['connections']['reused'] == 9
    assert stats['connections']['reuse_rate'] == pytest.approx(0.9, rel=0.01)


def test_record_batch_operation():
    """Test recording batch operations."""
    metrics = MetricsCollector()

    metrics.record_batch_operation(1000)
    metrics.record_batch_operation(500)

    stats = metrics.get_metrics()

    assert stats['batch_operations'] == 2


def test_cache_metrics():
    """Test cache hit/miss recording."""
    metrics = MetricsCollector()

    # 7 hits, 3 misses = 70% hit rate
    for _ in range(7):
        metrics.record_cache_hit()
    for _ in range(3):
        metrics.record_cache_miss()

    stats = metrics.get_metrics()

    assert stats['cache']['hits'] == 7
    assert stats['cache']['misses'] == 3
    assert stats['cache']['hit_rate'] == pytest.approx(0.7, rel=0.01)


def test_pool_metrics():
    """Test pool checkout metrics."""
    metrics = MetricsCollector()

    metrics.record_pool_checkout(success=True)
    metrics.record_pool_checkout(success=True)
    metrics.record_pool_checkout(success=False)  # timeout

    stats = metrics.get_metrics()

    assert stats['pool']['checkouts'] == 2
    assert stats['pool']['timeouts'] == 1


def test_reconnect_metric():
    """Test reconnect counting."""
    metrics = MetricsCollector()

    metrics.record_reconnect()
    metrics.record_reconnect()

    stats = metrics.get_metrics()

    assert stats['reconnects'] == 2


def test_query_stats():
    """Test per-query statistics."""
    metrics = MetricsCollector()

    # Record same query multiple times
    query = "SELECT * FROM users"
    metrics.record_query(query, 0.1, success=True)
    metrics.record_query(query, 0.2, success=True)
    metrics.record_query(query, 0.3, success=False, error="timeout")

    query_stats = metrics.get_query_stats()

    assert query in query_stats
    assert query_stats[query]['count'] == 3
    assert query_stats[query]['errors'] == 1
    assert query_stats[query]['avg_time'] > 0


def test_metrics_reset():
    """Test resetting metrics."""
    metrics = MetricsCollector()

    metrics.record_query("SELECT", 0.1, success=True)
    metrics.record_connection(success=True)
    metrics.record_cache_hit()

    # Reset
    metrics.reset()

    stats = metrics.get_metrics()

    assert stats['queries']['total'] == 0
    assert stats['connections']['created'] == 0
    assert stats['cache']['hits'] == 0


def test_uptime_tracking():
    """Test uptime tracking."""
    metrics = MetricsCollector()

    time.sleep(0.1)

    stats = metrics.get_metrics()

    assert stats['uptime_seconds'] >= 0.1


def test_success_rate():
    """Test success rate calculation."""
    metrics = MetricsCollector()

    # 8 success, 2 failures = 80% success rate
    for _ in range(8):
        metrics.record_query("SELECT", 0.1, success=True)
    for _ in range(2):
        metrics.record_query("SELECT", 0.1, success=False)

    stats = metrics.get_metrics()

    assert stats['queries']['success_rate'] == pytest.approx(0.8, rel=0.01)


def test_percentile_calculation():
    """Test percentile calculations."""
    metrics = MetricsCollector()

    # Record queries with known distribution
    times = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    for t in times:
        metrics.record_query("SELECT", t, success=True)

    stats = metrics.get_metrics()

    # P50 should be around 0.05
    assert stats['queries']['p50_time'] == pytest.approx(0.05, abs=0.01)

    # P95 should be around 0.095
    assert stats['queries']['p95_time'] >= 0.09


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

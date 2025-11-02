"""
Metrics collection and tracking for wbjdbc.

Tracks connection pool usage, query execution times, error rates,
and other performance metrics.
"""

import time
import threading
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime
import json
from .config import get_config
from .logging_config import get_logger


class MetricsCollector:
    """Collects and tracks metrics for wbjdbc operations."""

    def __init__(self):
        """Initialize metrics collector."""
        self._lock = threading.Lock()
        self._metrics = {
            'queries_executed': 0,
            'queries_failed': 0,
            'connections_created': 0,
            'connections_failed': 0,
            'connections_reused': 0,
            'batch_operations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_query_time': 0.0,
            'query_times': [],
            'pool_checkouts': 0,
            'pool_timeouts': 0,
            'reconnects': 0,
        }
        self._query_stats = defaultdict(lambda: {'count': 0, 'total_time': 0.0, 'errors': 0})
        self._start_time = time.time()
        self.logger = get_logger()

    def record_query(self, query: str, duration: float, success: bool = True, error: Optional[str] = None):
        """
        Record query execution metrics.

        Args:
            query: SQL query (first 100 chars)
            duration: Execution time in seconds
            success: Whether query succeeded
            error: Error message if query failed
        """
        with self._lock:
            if success:
                self._metrics['queries_executed'] += 1
                self._metrics['total_query_time'] += duration
                self._metrics['query_times'].append(duration)

                # Keep only last 1000 query times
                if len(self._metrics['query_times']) > 1000:
                    self._metrics['query_times'] = self._metrics['query_times'][-1000:]
            else:
                self._metrics['queries_failed'] += 1

            # Track per-query stats (using first 100 chars as key)
            query_key = query[:100] if len(query) > 100 else query
            self._query_stats[query_key]['count'] += 1
            self._query_stats[query_key]['total_time'] += duration
            if not success:
                self._query_stats[query_key]['errors'] += 1

    def record_connection(self, success: bool = True, reused: bool = False):
        """
        Record connection metrics.

        Args:
            success: Whether connection succeeded
            reused: Whether connection was reused from pool
        """
        with self._lock:
            if success:
                if reused:
                    self._metrics['connections_reused'] += 1
                else:
                    self._metrics['connections_created'] += 1
            else:
                self._metrics['connections_failed'] += 1

    def record_batch_operation(self, batch_size: int):
        """
        Record batch operation metrics.

        Args:
            batch_size: Number of operations in batch
        """
        with self._lock:
            self._metrics['batch_operations'] += 1

    def record_cache_hit(self):
        """Record cache hit."""
        with self._lock:
            self._metrics['cache_hits'] += 1

    def record_cache_miss(self):
        """Record cache miss."""
        with self._lock:
            self._metrics['cache_misses'] += 1

    def record_pool_checkout(self, success: bool = True):
        """
        Record connection pool checkout.

        Args:
            success: Whether checkout succeeded or timed out
        """
        with self._lock:
            if success:
                self._metrics['pool_checkouts'] += 1
            else:
                self._metrics['pool_timeouts'] += 1

    def record_reconnect(self):
        """Record auto-reconnect event."""
        with self._lock:
            self._metrics['reconnects'] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dict containing all metrics
        """
        with self._lock:
            uptime = time.time() - self._start_time

            # Calculate statistics
            query_times = self._metrics['query_times']
            avg_query_time = (
                self._metrics['total_query_time'] / self._metrics['queries_executed']
                if self._metrics['queries_executed'] > 0 else 0
            )

            metrics = {
                'uptime_seconds': uptime,
                'queries': {
                    'total': self._metrics['queries_executed'],
                    'failed': self._metrics['queries_failed'],
                    'success_rate': (
                        self._metrics['queries_executed'] /
                        (self._metrics['queries_executed'] + self._metrics['queries_failed'])
                        if self._metrics['queries_executed'] + self._metrics['queries_failed'] > 0 else 0
                    ),
                    'average_time': avg_query_time,
                    'min_time': min(query_times) if query_times else 0,
                    'max_time': max(query_times) if query_times else 0,
                    'p50_time': self._percentile(query_times, 50) if query_times else 0,
                    'p95_time': self._percentile(query_times, 95) if query_times else 0,
                    'p99_time': self._percentile(query_times, 99) if query_times else 0,
                },
                'connections': {
                    'created': self._metrics['connections_created'],
                    'reused': self._metrics['connections_reused'],
                    'failed': self._metrics['connections_failed'],
                    'reuse_rate': (
                        self._metrics['connections_reused'] /
                        (self._metrics['connections_created'] + self._metrics['connections_reused'])
                        if self._metrics['connections_created'] + self._metrics['connections_reused'] > 0 else 0
                    ),
                },
                'pool': {
                    'checkouts': self._metrics['pool_checkouts'],
                    'timeouts': self._metrics['pool_timeouts'],
                    'timeout_rate': (
                        self._metrics['pool_timeouts'] /
                        (self._metrics['pool_checkouts'] + self._metrics['pool_timeouts'])
                        if self._metrics['pool_checkouts'] + self._metrics['pool_timeouts'] > 0 else 0
                    ),
                },
                'cache': {
                    'hits': self._metrics['cache_hits'],
                    'misses': self._metrics['cache_misses'],
                    'hit_rate': (
                        self._metrics['cache_hits'] /
                        (self._metrics['cache_hits'] + self._metrics['cache_misses'])
                        if self._metrics['cache_hits'] + self._metrics['cache_misses'] > 0 else 0
                    ),
                },
                'batch_operations': self._metrics['batch_operations'],
                'reconnects': self._metrics['reconnects'],
                'timestamp': datetime.now().isoformat(),
            }

            return metrics

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list of values."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]

    def get_query_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get per-query statistics.

        Returns:
            Dict mapping query prefixes to their stats
        """
        with self._lock:
            stats = {}
            for query_key, query_data in self._query_stats.items():
                stats[query_key] = {
                    'count': query_data['count'],
                    'total_time': query_data['total_time'],
                    'avg_time': (
                        query_data['total_time'] / query_data['count']
                        if query_data['count'] > 0 else 0
                    ),
                    'errors': query_data['errors'],
                    'error_rate': (
                        query_data['errors'] / query_data['count']
                        if query_data['count'] > 0 else 0
                    ),
                }
            return stats

    def export_metrics(self, filepath: Optional[str] = None) -> str:
        """
        Export metrics to JSON file.

        Args:
            filepath: Path to export file. If None, uses config.

        Returns:
            JSON string of metrics
        """
        metrics = self.get_metrics()
        metrics['query_stats'] = self.get_query_stats()

        json_data = json.dumps(metrics, indent=2)

        if filepath is None:
            config = get_config()
            filepath = config.get('METRICS_FILE')

        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(json_data)
                self.logger.info(f"Metrics exported to {filepath}")
            except Exception as e:
                self.logger.error(f"Failed to export metrics to {filepath}: {e}")

        return json_data

    def reset(self):
        """Reset all metrics (mainly for testing)."""
        with self._lock:
            self._metrics = {
                'queries_executed': 0,
                'queries_failed': 0,
                'connections_created': 0,
                'connections_failed': 0,
                'connections_reused': 0,
                'batch_operations': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'total_query_time': 0.0,
                'query_times': [],
                'pool_checkouts': 0,
                'pool_timeouts': 0,
                'reconnects': 0,
            }
            self._query_stats.clear()
            self._start_time = time.time()


# Global metrics collector
_global_metrics = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.

    Returns:
        MetricsCollector: Global metrics collector
    """
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def reset_metrics():
    """Reset global metrics collector (mainly for testing)."""
    global _global_metrics
    if _global_metrics is not None:
        _global_metrics.reset()

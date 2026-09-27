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

_MAX_QUERY_STATS_ENTRIES = 500


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

            # Track per-query stats (using first 100 chars as key), capped to
            # bound memory when callers execute many distinct dynamic queries.
            query_key = query[:100] if len(query) > 100 else query
            if query_key not in self._query_stats and len(self._query_stats) >= _MAX_QUERY_STATS_ENTRIES:
                oldest_key = next(iter(self._query_stats))
                del self._query_stats[oldest_key]
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

    def export_prometheus(self) -> str:
        """
        Format current metrics as Prometheus text exposition format.

        Returns a plain string - this does not start an HTTP server. Wire it into
        your own web framework, e.g. in Flask:

            @app.route("/metrics")
            def metrics():
                return get_metrics_collector().export_prometheus(), 200, \\
                    {"Content-Type": "text/plain; version=0.0.4"}
        """
        m = self.get_metrics()
        lines = []

        def counter(name, help_text, value):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        def gauge(name, help_text, value):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        gauge("wbjdbc_uptime_seconds", "Time since the metrics collector started", m['uptime_seconds'])

        q = m['queries']
        query_sum = q['average_time'] * q['total']
        lines.append("# HELP wbjdbc_query_duration_seconds Query execution time")
        lines.append("# TYPE wbjdbc_query_duration_seconds summary")
        lines.append(f'wbjdbc_query_duration_seconds{{quantile="0.5"}} {q["p50_time"]}')
        lines.append(f'wbjdbc_query_duration_seconds{{quantile="0.95"}} {q["p95_time"]}')
        lines.append(f'wbjdbc_query_duration_seconds{{quantile="0.99"}} {q["p99_time"]}')
        lines.append(f"wbjdbc_query_duration_seconds_sum {query_sum}")
        lines.append(f"wbjdbc_query_duration_seconds_count {q['total']}")

        counter("wbjdbc_queries_total", "Total successful queries executed", q['total'])
        counter("wbjdbc_queries_failed_total", "Total failed queries", q['failed'])

        c = m['connections']
        counter("wbjdbc_connections_created_total", "New JDBC connections created", c['created'])
        counter("wbjdbc_connections_reused_total", "Connections served from the pool", c['reused'])
        counter("wbjdbc_connections_failed_total", "Connection attempts that failed", c['failed'])
        gauge("wbjdbc_connection_reuse_rate", "Fraction of connections served from the pool (0-1)", c['reuse_rate'])

        p = m['pool']
        counter("wbjdbc_pool_checkouts_total", "Successful pool checkouts", p['checkouts'])
        counter("wbjdbc_pool_timeouts_total", "Pool checkout timeouts", p['timeouts'])

        cache = m['cache']
        counter("wbjdbc_cache_hits_total", "Schema cache hits", cache['hits'])
        counter("wbjdbc_cache_misses_total", "Schema cache misses", cache['misses'])
        gauge("wbjdbc_cache_hit_rate", "Schema cache hit rate (0-1)", cache['hit_rate'])

        counter("wbjdbc_batch_operations_total", "Batch operations executed", m['batch_operations'])
        counter("wbjdbc_reconnects_total", "Successful reconnects after a transient connection failure", m['reconnects'])

        return "\n".join(lines) + "\n"

    def export_metrics(self, filepath: Optional[str] = None) -> str:
        """
        Export metrics to a file, as JSON by default or Prometheus text exposition
        format when WBJDBC_METRICS_PROMETHEUS=true.

        Args:
            filepath: Path to export file. If None, uses config.

        Returns:
            The exported string (JSON or Prometheus format, matching what was written)
        """
        config = get_config()
        use_prometheus = config.get('METRICS_PROMETHEUS', False)

        if use_prometheus:
            output_data = self.export_prometheus()
        else:
            metrics = self.get_metrics()
            metrics['query_stats'] = self.get_query_stats()
            output_data = json.dumps(metrics, indent=2)

        if filepath is None:
            filepath = config.get('METRICS_FILE')

        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(output_data)
                self.logger.info(f"Metrics exported to {filepath}")
            except Exception as e:
                self.logger.error(f"Failed to export metrics to {filepath}: {e}")

        return output_data

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

"""
Metadata caching for wbjdbc.

Caches table schemas, column information, and other metadata
to reduce repeated database queries.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict
from .config import get_config
from .logging_config import get_logger
from .metrics import get_metrics_collector


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, value: Any, ttl: int):
        """
        Initialize cache entry.

        Args:
            value: Cached value
            ttl: Time-to-live in seconds
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() - self.created_at > self.ttl

    def access(self) -> Any:
        """Access the cached value and update stats."""
        self.hits += 1
        self.last_accessed = time.time()
        return self.value


class MetadataCache:
    """Thread-safe LRU cache for database metadata."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize metadata cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.logger = get_logger()
        self.metrics = get_metrics_collector()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self.logger.debug(f"Cache miss: {key}")
                self.metrics.record_cache_miss()
                return None

            if entry.is_expired():
                self.logger.debug(f"Cache expired: {key}")
                del self._cache[key]
                self.metrics.record_cache_miss()
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)

            self.logger.debug(f"Cache hit: {key}")
            self.metrics.record_cache_hit()
            return entry.access()

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            # Remove oldest entry if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self.logger.debug(f"Cache full, evicting: {oldest_key}")
                del self._cache[oldest_key]

            # Add or update entry
            self._cache[key] = CacheEntry(value, ttl)
            self._cache.move_to_end(key)

            self.logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def invalidate(self, key: str):
        """
        Invalidate a cache entry.

        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self.logger.debug(f"Cache invalidated: {key}")

    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all entries matching a pattern.

        Args:
            pattern: Pattern to match (simple substring match)
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                self.logger.debug(f"Cache invalidated: {key}")

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self.logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        with self._lock:
            total_hits = sum(entry.hits for entry in self._cache.values())
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'total_hits': total_hits,
                'entries': len(self._cache),
            }


class SchemaCache:
    """Specialized cache for database schema information."""

    def __init__(self, metadata_cache: Optional[MetadataCache] = None):
        """
        Initialize schema cache.

        Args:
            metadata_cache: Underlying metadata cache (creates new if None)
        """
        config = get_config()
        cache_config = config.get_cache_config()

        self.cache = metadata_cache or MetadataCache(
            max_size=cache_config.get('max_size', 1000),
            default_ttl=cache_config.get('ttl', 3600)
        )
        self.enabled = cache_config.get('enabled', True)
        self.logger = get_logger()

    def _make_table_key(self, database: str, table: str) -> str:
        """Create cache key for table metadata."""
        return f"table:{database}:{table}"

    def _make_columns_key(self, database: str, table: str) -> str:
        """Create cache key for column metadata."""
        return f"columns:{database}:{table}"

    def get_table_metadata(self, database: str, table: str) -> Optional[Dict[str, Any]]:
        """
        Get cached table metadata.

        Args:
            database: Database name
            table: Table name

        Returns:
            Table metadata or None
        """
        if not self.enabled:
            return None

        key = self._make_table_key(database, table)
        return self.cache.get(key)

    def set_table_metadata(self, database: str, table: str, metadata: Dict[str, Any]):
        """
        Cache table metadata.

        Args:
            database: Database name
            table: Table name
            metadata: Table metadata to cache
        """
        if not self.enabled:
            return

        key = self._make_table_key(database, table)
        self.cache.set(key, metadata)

    def get_columns(self, database: str, table: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached column information.

        Args:
            database: Database name
            table: Table name

        Returns:
            List of column metadata or None
        """
        if not self.enabled:
            return None

        key = self._make_columns_key(database, table)
        return self.cache.get(key)

    def set_columns(self, database: str, table: str, columns: List[Dict[str, Any]]):
        """
        Cache column information.

        Args:
            database: Database name
            table: Table name
            columns: List of column metadata
        """
        if not self.enabled:
            return

        key = self._make_columns_key(database, table)
        self.cache.set(key, columns)

    def invalidate_table(self, database: str, table: str):
        """
        Invalidate all cached data for a table.

        Args:
            database: Database name
            table: Table name
        """
        if not self.enabled:
            return

        self.cache.invalidate(self._make_table_key(database, table))
        self.cache.invalidate(self._make_columns_key(database, table))
        self.logger.info(f"Invalidated cache for {database}.{table}")

    def invalidate_database(self, database: str):
        """
        Invalidate all cached data for a database.

        Args:
            database: Database name
        """
        if not self.enabled:
            return

        self.cache.invalidate_pattern(f":{database}:")
        self.logger.info(f"Invalidated cache for database {database}")


# Global schema cache instance
_global_schema_cache = None
_cache_lock = threading.Lock()


def get_schema_cache() -> SchemaCache:
    """
    Get the global schema cache instance.

    Returns:
        SchemaCache: Global schema cache
    """
    global _global_schema_cache
    if _global_schema_cache is None:
        with _cache_lock:
            if _global_schema_cache is None:
                _global_schema_cache = SchemaCache()
    return _global_schema_cache


def reset_cache():
    """Reset global schema cache (mainly for testing)."""
    global _global_schema_cache
    if _global_schema_cache is not None:
        _global_schema_cache.cache.clear()
        _global_schema_cache = None

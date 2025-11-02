"""
Tests for metadata caching.
"""

import time
import pytest
from wbjdbc.cache import MetadataCache, CacheEntry, SchemaCache


def test_cache_entry_creation():
    """Test cache entry creation and expiration."""
    entry = CacheEntry("test_value", ttl=1)

    assert entry.value == "test_value"
    assert not entry.is_expired()

    # Wait for expiration
    time.sleep(1.1)
    assert entry.is_expired()


def test_cache_entry_access():
    """Test cache entry access tracking."""
    entry = CacheEntry("test", ttl=10)

    assert entry.hits == 0
    entry.access()
    assert entry.hits == 1
    entry.access()
    assert entry.hits == 2


def test_metadata_cache_get_set():
    """Test basic cache get/set operations."""
    cache = MetadataCache(max_size=10, default_ttl=60)

    # Initially empty
    assert cache.get('key1') is None

    # Set value
    cache.set('key1', 'value1')
    assert cache.get('key1') == 'value1'

    # Set with custom TTL
    cache.set('key2', 'value2', ttl=1)
    assert cache.get('key2') == 'value2'

    # Wait for expiration
    time.sleep(1.1)
    assert cache.get('key2') is None


def test_metadata_cache_lru():
    """Test LRU eviction."""
    cache = MetadataCache(max_size=3)

    cache.set('key1', 'value1')
    cache.set('key2', 'value2')
    cache.set('key3', 'value3')

    # Cache is full, adding another should evict oldest
    cache.set('key4', 'value4')

    # key1 should be evicted
    assert cache.get('key1') is None
    assert cache.get('key2') == 'value2'
    assert cache.get('key3') == 'value3'
    assert cache.get('key4') == 'value4'


def test_metadata_cache_invalidate():
    """Test cache invalidation."""
    cache = MetadataCache()

    cache.set('key1', 'value1')
    cache.set('key2', 'value2')

    assert cache.get('key1') == 'value1'

    # Invalidate specific key
    cache.invalidate('key1')
    assert cache.get('key1') is None
    assert cache.get('key2') == 'value2'


def test_metadata_cache_invalidate_pattern():
    """Test pattern-based invalidation."""
    cache = MetadataCache()

    cache.set('table:db1:users', 'data1')
    cache.set('table:db1:orders', 'data2')
    cache.set('table:db2:products', 'data3')

    # Invalidate all db1 entries
    cache.invalidate_pattern('db1')

    assert cache.get('table:db1:users') is None
    assert cache.get('table:db1:orders') is None
    assert cache.get('table:db2:products') == 'data3'


def test_metadata_cache_clear():
    """Test clearing entire cache."""
    cache = MetadataCache()

    cache.set('key1', 'value1')
    cache.set('key2', 'value2')

    cache.clear()

    assert cache.get('key1') is None
    assert cache.get('key2') is None


def test_metadata_cache_stats():
    """Test cache statistics."""
    cache = MetadataCache(max_size=100)

    cache.set('key1', 'value1')
    cache.set('key2', 'value2')

    stats = cache.get_stats()

    assert stats['size'] == 2
    assert stats['max_size'] == 100
    assert stats['entries'] == 2


def test_schema_cache_table_metadata():
    """Test schema cache table metadata operations."""
    cache = SchemaCache()

    metadata = {'columns': 5, 'rows': 1000}

    # Initially empty
    assert cache.get_table_metadata('testdb', 'users') is None

    # Set metadata
    cache.set_table_metadata('testdb', 'users', metadata)

    # Retrieve metadata
    retrieved = cache.get_table_metadata('testdb', 'users')
    assert retrieved == metadata


def test_schema_cache_columns():
    """Test schema cache column operations."""
    cache = SchemaCache()

    columns = [
        {'name': 'id', 'type': 'INTEGER'},
        {'name': 'name', 'type': 'VARCHAR'},
    ]

    # Set columns
    cache.set_columns('testdb', 'users', columns)

    # Retrieve columns
    retrieved = cache.get_columns('testdb', 'users')
    assert retrieved == columns


def test_schema_cache_invalidate_table():
    """Test invalidating specific table."""
    cache = SchemaCache()

    cache.set_table_metadata('testdb', 'users', {'data': 1})
    cache.set_columns('testdb', 'users', [{'col': 1}])
    cache.set_table_metadata('testdb', 'orders', {'data': 2})

    # Invalidate users table
    cache.invalidate_table('testdb', 'users')

    assert cache.get_table_metadata('testdb', 'users') is None
    assert cache.get_columns('testdb', 'users') is None
    assert cache.get_table_metadata('testdb', 'orders') == {'data': 2}


def test_schema_cache_invalidate_database():
    """Test invalidating entire database."""
    cache = SchemaCache()

    cache.set_table_metadata('db1', 'users', {'data': 1})
    cache.set_table_metadata('db1', 'orders', {'data': 2})
    cache.set_table_metadata('db2', 'products', {'data': 3})

    # Invalidate db1
    cache.invalidate_database('db1')

    assert cache.get_table_metadata('db1', 'users') is None
    assert cache.get_table_metadata('db1', 'orders') is None
    assert cache.get_table_metadata('db2', 'products') == {'data': 3}


def test_schema_cache_disabled():
    """Test schema cache when disabled."""
    from wbjdbc.cache import MetadataCache

    metadata_cache = MetadataCache()
    cache = SchemaCache(metadata_cache)
    cache.enabled = False

    # Operations should be no-ops when disabled
    cache.set_table_metadata('testdb', 'users', {'data': 1})
    assert cache.get_table_metadata('testdb', 'users') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

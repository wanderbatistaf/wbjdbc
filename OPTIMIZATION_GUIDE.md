# WBJDBC Optimized - Complete Optimization Guide

## 📋 Table of Contents

- [Overview](#overview)
- [What's New in v2.0](#whats-new-in-v20)
- [Quick Start](#quick-start)
- [Core Features](#core-features)
  - [Connection Pooling](#connection-pooling)
  - [Batch Execution](#batch-execution)
  - [Async Queries](#async-queries)
  - [Metadata Caching](#metadata-caching)
  - [Type Mapping](#type-mapping)
  - [Dirty Reads (Informix)](#dirty-reads-informix)
  - [Metrics & Logging](#metrics--logging)
- [Configuration](#configuration)
- [Performance Targets](#performance-targets)
- [Best Practices](#best-practices)
- [Migration Guide](#migration-guide)
- [API Reference](#api-reference)

---

## Overview

WBJDBC v2.0 is a major optimization release that enhances the original library with production-grade features for high-performance database access. While maintaining 100% backward compatibility, it adds:

- **Connection Pooling** - Reuse connections to reduce overhead
- **Batch Execution** - 5-10x faster bulk operations
- **Async Queries** - Concurrent query execution
- **Metadata Caching** - 90%+ reduction in schema queries
- **Auto-Reconnect** - Resilient connection handling
- **Type Mapping** - Automatic JDBC ↔ Python type conversion
- **Dirty Reads** - Optional isolation for Informix performance
- **Metrics & Logging** - Production-ready observability

---

## What's New in v2.0

### For Existing Users (Backward Compatible)

Your existing code continues to work without changes:

```python
# Old API still works exactly as before
from wbjdbc import connect_to_db

conn = connect_to_db(
    db_type="informix-sqli",
    host="myserver",
    database="mydb",
    user="myuser",
    password="mypass",
    server="informix_server"
)
```

### For New Features (Optimized API)

Use the new `connect_optimized()` for enhanced performance:

```python
# New optimized API with pooling, batching, async, etc.
from wbjdbc import connect_optimized

conn = connect_optimized(
    db_type="informix-sqli",
    host="myserver",
    database="mydb",
    user="myuser",
    password="mypass",
    server="informix_server"
)

# Now you can use batch operations, async queries, etc.
conn.execute_batch("INSERT INTO table VALUES (?, ?)", data)
```

---

## Quick Start

### Installation

```bash
pip install wbjdbc==2.0.0
```

### Basic Usage

```python
from wbjdbc import connect_optimized

# Create optimized connection
conn = connect_optimized(
    db_type="informix-sqli",
    host="localhost",
    database="testdb",
    user="user",
    password="pass",
    server="informix"
)

# Execute query
results = conn.execute_query("SELECT * FROM products LIMIT 10")

# Batch insert (5-10x faster)
data = [(i, f'Product {i}', 10.0 + i) for i in range(1000)]
conn.execute_batch(
    "INSERT INTO products (id, name, price) VALUES (?, ?, ?)",
    data
)

# Async query
future = conn.execute_async("SELECT COUNT(*) FROM big_table")
result = future.result()  # Wait for completion

conn.close()
```

### Configuration via .env

Create a `.env` file:

```bash
WBJDBC_DB_HOST=localhost
WBJDBC_DB_NAME=testdb
WBJDBC_DB_USER=myuser
WBJDBC_DB_PASSWORD=mypass
WBJDBC_DB_SERVER=informix_server

WBJDBC_POOL_SIZE=10
WBJDBC_POOL_MAX_SIZE=20
WBJDBC_BATCH_SIZE=1000
WBJDBC_CACHE_ENABLED=true
```

Then connect without parameters:

```python
conn = connect_optimized(db_type="informix-sqli")
```

---

## Core Features

### Connection Pooling

Connection pooling reuses database connections to eliminate the overhead of creating new connections for each operation.

**Benefits:**
- **10-100x faster** connection acquisition
- Reduced database server load
- Better resource utilization

**Usage:**

```python
# Pooling is enabled by default
conn = connect_optimized(
    db_type="informix-sqli",
    # ... connection params ...
    use_pool=True  # Default
)

# Get connection from pool (< 50ms)
cursor = conn.cursor()
cursor.execute("SELECT * FROM table")

# Connection returned to pool on close
conn.close()
```

**Configuration:**

```bash
# .env file
WBJDBC_POOL_SIZE=10          # Initial connections
WBJDBC_POOL_MAX_SIZE=20      # Maximum connections
WBJDBC_POOL_TIMEOUT=30.0     # Checkout timeout (seconds)
WBJDBC_POOL_RECYCLE=3600     # Recycle after 1 hour
WBJDBC_POOL_PRE_PING=true    # Test before use
```

**Pool Statistics:**

```python
from wbjdbc import get_pool

pool = get_pool(...)
stats = pool.get_stats()
print(f"Pool size: {stats['current_size']}")
print(f"Available: {stats['available']}")
print(f"In use: {stats['in_use']}")
```

---

### Batch Execution

Batch execution groups multiple SQL statements into batches for efficient execution.

**Performance:** 5-10x faster than individual statements

**Insert Example:**

```python
# Prepare data
data = [(i, f'Name {i}', 10.0 + i) for i in range(10000)]

# Batch insert
rows_affected = conn.execute_batch(
    "INSERT INTO products (id, name, price) VALUES (?, ?, ?)",
    data,
    batch_size=1000,       # 1000 rows per batch
    commit_interval=5000   # Commit every 5000 rows
)

print(f"Inserted {rows_affected} rows")
```

**Update Example:**

```python
# Batch update
updates = [(new_price, product_id) for product_id, new_price in price_changes]

conn.execute_batch(
    "UPDATE products SET price = ? WHERE id = ?",
    updates,
    batch_size=500
)
```

**Configuration:**

```bash
WBJDBC_BATCH_SIZE=1000              # Default batch size
WBJDBC_BATCH_COMMIT_INTERVAL=5000   # Auto-commit interval
```

**Best Practices:**
- Use batch_size=1000-5000 for inserts
- Use batch_size=500-1000 for updates
- Enable transaction commit intervals for large datasets
- Monitor memory usage with very large batches

---

### Async Queries

Execute multiple queries concurrently using thread pool.

**Benefits:**
- Run 50+ queries simultaneously
- Reduce total execution time
- Better resource utilization

**Basic Async:**

```python
# Execute query asynchronously
future = conn.execute_async("SELECT COUNT(*) FROM large_table")

# Do other work...

# Wait for result
result = future.result()
print(result)
```

**Multiple Concurrent Queries:**

```python
from concurrent.futures import as_completed

# Submit multiple queries
queries = [
    "SELECT COUNT(*) FROM products",
    "SELECT COUNT(*) FROM orders",
    "SELECT AVG(price) FROM products",
    "SELECT SUM(amount) FROM orders"
]

futures = [conn.execute_async(q) for q in queries]

# Process as they complete
for future in as_completed(futures):
    result = future.result()
    print(result)
```

**Configuration:**

```bash
WBJDBC_ASYNC_ENABLED=true
WBJDBC_ASYNC_MAX_WORKERS=50   # Max concurrent queries
```

**Best Practices:**
- Use for independent read-only queries
- Limit concurrent queries based on database capacity
- Monitor connection pool usage
- Handle exceptions per future

---

### Metadata Caching

Cache table schemas, column information, and metadata to avoid repeated database queries.

**Performance:** 90%+ reduction in schema query time

**Usage:**

```python
# First call - queries database
columns = conn.get_table_columns('products')
# Takes ~100ms

# Subsequent calls - from cache
columns = conn.get_table_columns('products')
# Takes ~1ms (100x faster!)

# Cached information
for col in columns:
    print(f"{col['name']}: {col['type_name']}")
```

**Cache Invalidation:**

```python
from wbjdbc import get_schema_cache

cache = get_schema_cache()

# Invalidate specific table
cache.invalidate_table('mydb', 'products')

# Invalidate entire database
cache.invalidate_database('mydb')

# Clear all cache
cache.clear()
```

**Configuration:**

```bash
WBJDBC_CACHE_ENABLED=true
WBJDBC_CACHE_TTL=3600        # 1 hour
WBJDBC_CACHE_MAX_SIZE=1000   # Max entries
```

**Best Practices:**
- Enable for stable schemas
- Increase TTL for rarely-changing tables
- Invalidate after schema changes
- Monitor cache hit rate in metrics

---

### Type Mapping

Automatic conversion between JDBC and Python types.

**Supported Conversions:**

| JDBC Type | Python Type |
|-----------|-------------|
| java.sql.Date | datetime.date |
| java.sql.Time | datetime.time |
| java.sql.Timestamp | datetime.datetime |
| java.math.BigDecimal | decimal.Decimal |
| java.lang.Boolean | bool |
| java.lang.Integer/Long | int |
| java.lang.Float/Double | float |
| byte[] | bytes |

**Usage:**

```python
# Type mapping enabled by default
conn = connect_optimized(..., enable_type_mapping=True)

cursor = conn.cursor()
cursor.execute("SELECT order_date, amount FROM orders")

for row in cursor.fetchall():
    order_date = row[0]  # datetime.date (not java.sql.Date)
    amount = row[1]      # Decimal (not java.math.BigDecimal)
```

**Parameter Conversion:**

```python
from datetime import datetime, date
from decimal import Decimal

# Python types automatically converted to JDBC types
cursor.execute(
    "INSERT INTO orders (date, time, amount, paid) VALUES (?, ?, ?, ?)",
    (date.today(), datetime.now().time(), Decimal('123.45'), True)
)
```

**Disable if Needed:**

```python
# Disable for raw JDBC types
conn = connect_optimized(..., enable_type_mapping=False)
```

---

### Dirty Reads (Informix)

Enable dirty reads for better read performance on Informix.

**What are Dirty Reads?**
- Read uncommitted data from other transactions
- No read locks - better concurrency
- Faster queries on busy systems
- **Risk:** May read data that gets rolled back

**When to Use:**
- Reporting queries on historical data
- Analytics where exact precision isn't critical
- Long-running queries that would otherwise block

**Usage:**

```python
# Enable dirty reads for this connection
conn = connect_optimized(
    db_type="informix-sqli",
    # ... connection params ...
    isolation_level="DIRTY_READ"
)

# All queries on this connection use dirty reads
results = conn.execute_query("""
    SELECT customer_id, SUM(amount)
    FROM orders
    WHERE order_date >= CURRENT - 365 UNITS DAY
    GROUP BY customer_id
""")
```

**Configuration:**

```bash
# Enable globally in .env
WBJDBC_INFORMIX_DIRTY_READS=true

# Or set default isolation level
WBJDBC_INFORMIX_ISOLATION_LEVEL=DIRTY_READ
```

**Other Isolation Levels:**
- `READ_UNCOMMITTED` (same as DIRTY_READ)
- `READ_COMMITTED` (default)
- `REPEATABLE_READ`
- `SERIALIZABLE`

---

### Metrics & Logging

Production-ready metrics collection and logging.

**Metrics:**

```python
from wbjdbc import get_metrics_collector

metrics = get_metrics_collector()

# Get current metrics
stats = metrics.get_metrics()

print(f"Queries executed: {stats['queries']['total']}")
print(f"Average query time: {stats['queries']['average_time']}s")
print(f"Connection reuse rate: {stats['connections']['reuse_rate']*100}%")
print(f"Cache hit rate: {stats['cache']['hit_rate']*100}%")

# Export to JSON file
metrics.export_metrics('metrics.json')
```

**Logging:**

```python
from wbjdbc import get_logger

logger = get_logger()
logger.info("Application started")
logger.error("Something went wrong")
```

**Configuration:**

```bash
# Logging
WBJDBC_LOG_LEVEL=INFO
WBJDBC_LOG_FILE=/var/log/wbjdbc.log
WBJDBC_LOG_SQL_QUERIES=true

# Metrics
WBJDBC_METRICS_ENABLED=true
WBJDBC_METRICS_FILE=/var/metrics/wbjdbc.json
```

**Metrics Available:**
- Query count, success rate, timing (avg, p50, p95, p99)
- Connection creation/reuse statistics
- Pool checkout/timeout statistics
- Cache hit/miss statistics
- Batch operation count
- Reconnect count

---

## Configuration

### Configuration Priority

1. Function parameters (highest priority)
2. `.env` file
3. Environment variables
4. Default values (lowest priority)

### Full Configuration Reference

See `.env.example` for all available options:

```bash
cp .env.example .env
# Edit .env with your settings
```

### Common Configurations

**High-Performance Batch Loading:**
```bash
WBJDBC_BATCH_SIZE=10000
WBJDBC_BATCH_COMMIT_INTERVAL=100000
WBJDBC_POOL_SIZE=5
WBJDBC_POOL_MAX_SIZE=10
```

**High-Concurrency OLTP:**
```bash
WBJDBC_POOL_SIZE=20
WBJDBC_POOL_MAX_SIZE=100
WBJDBC_ASYNC_MAX_WORKERS=200
WBJDBC_POOL_PRE_PING=true
WBJDBC_CACHE_ENABLED=true
```

**Reporting/Analytics:**
```bash
WBJDBC_INFORMIX_DIRTY_READS=true
WBJDBC_POOL_SIZE=3
WBJDBC_POOL_MAX_SIZE=5
WBJDBC_QUERY_TIMEOUT=300.0
WBJDBC_CACHE_ENABLED=true
```

---

## Performance Targets

WBJDBC v2.0 meets or exceeds these performance targets:

| Metric | Target | Typical |
|--------|--------|---------|
| Connection acquisition (pooled) | <50ms | 5-10ms |
| Batch operations speedup | ≥5x | 5-10x |
| Concurrent queries | ≥50 simultaneous | 50-100 |
| Metadata cache reduction | ≥90% | 95-99% |

Run benchmarks to validate on your system:

```bash
python examples/benchmark.py
```

---

## Best Practices

### Connection Management

✅ **DO:**
- Use connection pooling for better performance
- Use context managers for auto-cleanup
- Close connections when done
- Configure pool size based on workload

❌ **DON'T:**
- Create connections in tight loops
- Leave connections open indefinitely
- Exceed database max connections

```python
# Good - using context manager
with connect_optimized(...) as conn:
    results = conn.execute_query("SELECT * FROM table")
    # Auto-commits and closes

# Also good - explicit close
conn = connect_optimized(...)
try:
    results = conn.execute_query("SELECT * FROM table")
    conn.commit()
finally:
    conn.close()
```

### Batch Operations

✅ **DO:**
- Use batch execution for bulk operations
- Choose appropriate batch size (1000-5000)
- Use commit intervals for large datasets
- Monitor memory usage

❌ **DON'T:**
- Use individual inserts for large datasets
- Make batches too large (>10000)
- Forget to commit

### Async Queries

✅ **DO:**
- Use for independent read-only queries
- Handle exceptions per future
- Monitor connection pool usage
- Set appropriate max workers

❌ **DON'T:**
- Use for write operations (use batching instead)
- Exceed database connection limits
- Forget to wait for results

### Caching

✅ **DO:**
- Enable for stable schemas
- Invalidate after schema changes
- Monitor cache hit rate
- Increase TTL for static tables

❌ **DON'T:**
- Cache frequently-changing schemas
- Forget to invalidate after DDL changes
- Set TTL too low (defeats purpose)

---

## Migration Guide

### From v1.x to v2.0

v2.0 is 100% backward compatible. Your existing code works without changes.

**Option 1: Keep Using Old API**

```python
# This continues to work exactly as before
from wbjdbc import connect_to_db

conn = connect_to_db(...)
```

**Option 2: Migrate to Optimized API**

```python
# Old code
from wbjdbc import connect_to_db
conn = connect_to_db(
    db_type="informix-sqli",
    host="server",
    database="db",
    user="user",
    password="pass",
    server="informix"
)

# New code (drop-in replacement)
from wbjdbc import connect_optimized
conn = connect_optimized(
    db_type="informix-sqli",
    host="server",
    database="db",
    user="user",
    password="pass",
    server="informix"
)

# Now you can use new features
conn.execute_batch(...)
conn.execute_async(...)
```

**New Features to Adopt:**

1. **Replace loops with batch operations:**
   ```python
   # Old
   for row in data:
       cursor.execute("INSERT INTO table VALUES (?, ?)", row)

   # New
   conn.execute_batch("INSERT INTO table VALUES (?, ?)", data)
   ```

2. **Use async for concurrent queries:**
   ```python
   # Old
   result1 = conn.execute_query(query1)
   result2 = conn.execute_query(query2)

   # New
   future1 = conn.execute_async(query1)
   future2 = conn.execute_async(query2)
   result1 = future1.result()
   result2 = future2.result()
   ```

3. **Use context managers:**
   ```python
   # Old
   conn = connect_to_db(...)
   try:
       # do work
       conn.commit()
   finally:
       conn.close()

   # New
   with connect_optimized(...) as conn:
       # do work
       # auto-commits on success, auto-closes
   ```

---

## API Reference

### connect_optimized()

Create an optimized JDBC connection.

```python
connect_optimized(
    db_type: str,
    host: str,
    database: str,
    user: str,
    password: str,
    port: int = None,
    server: str = None,
    use_pool: bool = True,
    enable_type_mapping: bool = True,
    isolation_level: str = None,
    config_file: str = None,
    **kwargs
) -> OptimizedJDBCConnection
```

**Parameters:**
- `db_type`: "informix-sqli", "mysql", "postgresql", or 1-3
- `host`: Database server address
- `database`: Database name
- `user`: Username
- `password`: Password
- `port`: Port (optional, uses default)
- `server`: Informix server name
- `use_pool`: Enable connection pooling
- `enable_type_mapping`: Enable JDBC↔Python type conversion
- `isolation_level`: Transaction isolation level
- `config_file`: Path to .env file
- `**kwargs`: Additional options

### OptimizedJDBCConnection

Enhanced connection class.

**Methods:**

- `cursor()` - Get enhanced cursor
- `execute_query(query, params=None)` - Execute and return results
- `execute_batch(query, params_list, batch_size=None, commit_interval=None)` - Batch execution
- `execute_async(query, params=None)` - Async execution
- `get_table_columns(table)` - Get column metadata (cached)
- `commit()` - Commit transaction
- `rollback()` - Rollback transaction
- `close()` - Close connection

**Context Manager:**
```python
with connect_optimized(...) as conn:
    # use conn
    # auto-commits on success, auto-closes
```

### OptimizedJDBCCursor

Enhanced cursor class.

**Methods:**

- `execute(query, params=None, timeout=None)` - Execute query
- `executemany(query, params_list)` - Batch execute
- `fetchone()` - Fetch one row
- `fetchall()` - Fetch all rows
- `fetchmany(size=None)` - Fetch multiple rows
- `fetchdh()` - Fetch as list of dicts
- `close()` - Close cursor

**Properties:**

- `description` - Column metadata

### Utility Functions

- `get_config(env_file=None)` - Get configuration
- `get_logger(name='wbjdbc')` - Get logger
- `get_metrics_collector()` - Get metrics
- `get_pool(...)` - Get connection pool
- `close_all_pools()` - Close all pools
- `get_schema_cache()` - Get schema cache
- `reset_cache()` - Reset cache

---

## Support

- **GitHub:** https://github.com/wanderbatistaf/wbjdbc
- **Issues:** https://github.com/wanderbatistaf/wbjdbc/issues
- **PyPI:** https://pypi.org/project/wbjdbc/

---

## License

MIT License - See LICENSE file for details

---

**Made with ❤️ by a Brazilian Developer 🇧🇷**

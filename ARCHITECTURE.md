# wbjdbc — Architecture (current, as of 2.1)

There is a **single** connection core. `connect_optimized()` is the recommended entry
point; `connect_to_db()` and `OptimizedJDBCConnection` are deprecated compatibility
wrappers around the same core (see `CHANGELOG.md`).

```
                              User code
                                  │
                     connect_optimized(db_type, host, ...)
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   ConnectionPool         │   wbjdbc/__init__.py
                    │   (semaphore-based,      │   - pool_size + max_overflow
                    │    JPype-direct)         │   - pre-warm in a background thread
                    └─────────────┬────────────┘   - pre-ping (isValid) on checkout
                                  │ acquire()
                                  ▼
                    ┌─────────────────────────┐
                    │   _PooledConn            │   wraps the raw java.sql.Connection
                    │                          │   - execute_query/execute_batch/execute_async
                    │                          │   - get_table_columns()  → SchemaCache
                    │                          │   - commit/rollback/close (context mgr)
                    └─────────────┬────────────┘
                                  │ .cursor()
                                  ▼
                    ┌─────────────────────────┐
                    │   _DirectCursor          │   wbjdbc/__init__.py + wbjdbc/_types.py
                    │   (JPype direct,         │   - per-connection statement cache (FIFO, 20)
                    │    no jaydebeapi lock)   │   - _j2p()/_set_param() type conversion
                    └─────────────┬────────────┘   - slow-query logging (sensitive-SQL redacted)
                                  │
                    ┌─────────────┼─────────────┬──────────────────┐
                    ▼             ▼             ▼                  ▼
              MetricsCollector  SchemaCache  WBJDBCLogger        Config
              (metrics.py)      (cache.py)   (logging_config.py) (config.py)
              queries, pool,    table/column  redacts sensitive   .env file overrides
              cache, batch      metadata,     params before       are instance-local
              stats, p50/95/99  TTL + LRU     logging SQL         (not os.environ)
```

## Legacy / deprecated (kept importable, not used internally)

- **`wbjdbc/optimized.py`** (`OptimizedJDBCConnection`, `OptimizedJDBCCursor`) - thin
  wrappers that construct a `_PooledConn` via `connect_optimized()` internally and
  delegate every method to it. Raises `DeprecationWarning` on construction.
- **`wbjdbc/pool.py`** (`ConnectionPool`, `PooledConnection`, `get_pool`,
  `close_all_pools`) - the original queue-based pool with plain jaydebeapi cursors.
  Nothing in the package calls into it anymore.
- **`wbjdbc/types.py`** (`TypeMapper`) - superseded by `wbjdbc/_types.py`'s
  `_j2p`/`_set_param`, which `_DirectCursor` uses directly.
- **`connect_to_db()`** / `JDBCConnection` / `JDBCCursor` - the original v1.x API,
  plain jaydebeapi, no pooling. Raises `DeprecationWarning`.

## Why this document exists

Keep this diagram (and the "legacy" list above) in sync with the code: if a new
pooling/cursor/type-mapping feature is needed, it belongs in the core above, not in a
second parallel implementation.

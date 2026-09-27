# Changelog

All notable changes to wbjdbc are documented here.

## [2.3.0] - 2026-09-18

### Added

- **Stored procedures** - `cursor.callproc(proc_name, params=None, out_types=None)`
  (and `conn.callproc(...)`) call a stored procedure via JDBC's `CallableStatement`,
  supporting IN/OUT/INOUT parameters and result sets (fetched afterwards like a
  normal SELECT).
- **LOB streaming** - `execute(..., stream_lobs=True)` returns `LobHandle` objects for
  BLOB/CLOB columns instead of materializing them, with `.read()`/`.stream(chunk_size)`
  for chunked reads. Valid to read any time before the connection's next
  commit/rollback, per the JDBC `Blob`/`Clob` spec.
- **Savepoints** - `conn.savepoint()`, `conn.rollback_to()`, `conn.release_savepoint()`,
  and a `conn.savepoint_scope()` context manager for partial rollback within a
  transaction.
- `examples/production_features.py` - new example file covering retry/SSL,
  exceptions, real async, Prometheus, stored procedures, LOB streaming and
  savepoints (the existing `basic_usage.py`/`advanced_features.py` were already
  accurate and didn't need changes).

### Improved

- `_j2p()` (`wbjdbc/_types.py`) now detects BLOB/CLOB columns via `isinstance` against
  the JDBC `Blob`/`Clob` interfaces (driver-independent, unlike classname-based
  dispatch) and materializes them to `bytes`/`str` by default.

## [2.2.0] - 2026-09-18

### Added

- **Retry/reconnect with backoff** on connection establishment (`connect_optimized()`
  new `max_retries`/`retry_delay` kwargs, default from `WBJDBC_MAX_RETRIES`/
  `WBJDBC_RETRY_DELAY`). Only retries the connect step, never a query already sent to
  the server. Successful reconnects increment the `reconnects` metric.
- **SSL/TLS** support on the JDBC URL (`connect_optimized()` new `ssl_enabled`/
  `ssl_verify` kwargs, default from `WBJDBC_SSL_ENABLED`/`WBJDBC_SSL_VERIFY`), with
  per-`db_type` property mapping for MySQL/PostgreSQL/Informix - see
  `OPTIMIZATION_GUIDE.md` for the exact properties and a note on Informix
  driver-version differences.
- **DB-API 2.0 exception hierarchy** (`wbjdbc/exceptions.py`) - `Error`,
  `InterfaceError`, `DatabaseError`, `DataError`, `OperationalError`,
  `IntegrityError`, `InternalError`, `ProgrammingError`, `NotSupportedError`, all
  exported from the top-level `wbjdbc` package. Java `SQLException`s raised by
  `_DirectCursor.execute()`/`executemany()` and by connection establishment are now
  translated into these (classified by SQLSTATE class, so this works the same
  regardless of `db_type`), each carrying `.sqlstate`/`.sqlcode`. The deprecated
  `connect_to_db()`/`optimized.py` legacy paths are unchanged (jaydebeapi already
  raises its own `DatabaseError`).
- **Real async support** - `wbjdbc/aio.py` rewritten. Previously `async_db_conn` only
  wrapped `connect`/`commit`/`rollback`/`close` in `asyncio.to_thread`; every
  `cursor().execute()`/`fetchall()`/etc. inside the `async with` block ran
  synchronously and blocked the event loop. New `AsyncConnection`/`AsyncCursor` wrap
  the existing `_PooledConn`/`_DirectCursor` core (no JDBC logic duplicated) so every
  JDBC-hitting call is a real coroutine.
- **Prometheus export** - `MetricsCollector.export_prometheus()` formats the existing
  `get_metrics()` output (queries, connections, pool, cache, p50/p95/p99) as
  Prometheus text exposition format, no new dependency required. `export_metrics()`
  writes this format when `WBJDBC_METRICS_PROMETHEUS=true`.

## [2.1.0] - 2026-09-18

### Core unification

`connect_optimized()` is now backed by a single, complete core (`_PooledConn` /
`_DirectCursor`) - JPype-direct JDBC access, per-connection statement caching, and
pool pre-warming.

- **Added** `get_table_columns()` to the core (`_PooledConn`), backed by `SchemaCache`.
- **Added** metrics recording (`MetricsCollector`) to `_DirectCursor.execute()` /
  `executemany()` and to `ConnectionPool` (`acquire`/`_new_conn`), so
  `get_metrics_collector().get_metrics()` reflects real activity for anyone using
  `connect_optimized()`.
- **Added** `batch_size`/`commit_interval` chunked execution with periodic auto-commit
  to `_PooledConn.execute_batch()` (opt-in via those kwargs; calling it with neither
  keeps the previous single-`executemany()` behavior).
- **Changed** `OptimizedJDBCConnection`/`OptimizedJDBCCursor` (`wbjdbc/optimized.py`)
  to thin wrappers delegating to `connect_optimized()`'s core. Public API is
  unchanged; construction now raises `DeprecationWarning`.
- **Deprecated** `connect_to_db()` in favor of `connect_optimized()` - raises
  `DeprecationWarning`, internal behavior unchanged.
- **Deprecated** `wbjdbc/pool.py` (`ConnectionPool`, `PooledConnection`, `get_pool`,
  `close_all_pools`) and `wbjdbc/types.py` (`TypeMapper`) - kept importable for
  backward compatibility, marked legacy in their docstrings.

### Fixed

- `_rewrite_named()` (`_types.py`) no longer misparses Postgres-style `col::type`
  casts as a `:type` named parameter.
- `WBJDBCLogger.log_query()` now redacts params for SQL touching sensitive columns
  (password/senha/secret) when `WBJDBC_LOG_SQL_QUERIES=true`, matching the redaction
  already applied to the slow-query logger.
- `MetricsCollector._query_stats` is now capped (default 500 distinct query keys,
  FIFO eviction) for workloads with many distinct dynamic queries.
- `Config._load_env_file()` now keeps `.env` values in an instance-local override
  instead of writing them into the process environment, for cleaner isolation
  between `Config()` instances and any subprocess spawned afterward.

### Packaging

- **Removed** an embedded JDK 17 (`wbjdbc/resources/server/`, ~81MB) - `jvm.py`
  resolves Java via `JAVA_HOME`/system `PATH`. Package size drops from ~86MB to ~5MB.
- **Added** MySQL (`mysql-connector-j-8.0.33.jar`) and PostgreSQL
  (`postgresql-42.7.4.jar`) JDBC driver jars from Maven Central, enabling
  `db_type="mysql"`/`"postgresql"` out of the box.
- `start_jvm()` now only loads the Informix driver jar for Informix connections
  (`db_type="informix-sqli"`), via a new `db_type` parameter threaded through the
  internal callers.

### Documentation

- `README.md`: updated usage examples (`cursor.execute()`/`fetchdh()`/`fetchdf()`,
  `conn.execute_query()`); noted `connect_to_db()`/`OptimizedJDBCConnection` as
  deprecated aliases; clarified metrics export is JSON today (Prometheus on the
  roadmap).
- `OPTIMIZATION_GUIDE.md`: updated the pool-stats example
  (`connect_optimized_stats(conn.pool_key)`), updated `connect_optimized()`'s
  documented return type, marked `OptimizedJDBCConnection`/`OptimizedJDBCCursor`
  deprecated.
- `IMPLEMENTATION_SUMMARY.md`: appended a "Core Unification" section summarizing the
  2.1.0 changes.
- Added `ARCHITECTURE.md` with the current architecture diagram.

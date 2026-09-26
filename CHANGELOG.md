# Changelog

All notable changes to wbjdbc are documented here.

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

# PostgreSQL Mastery Study Guide

A comprehensive, depth-first guide to mastering PostgreSQL. Assumes you already know basic SQL (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `JOIN`, `GROUP BY`). Each phase builds on the previous. Don't skim — every section is something you'll be expected to know in a senior database role.

---

## Phase 1: Core Foundations

### 1.1 PostgreSQL Architecture

- **Process model**: Postgres uses a multi-process architecture, not multi-threaded.
  - A single `postmaster` process listens for connections and forks a dedicated backend process per client. Every connection has real OS-level cost (memory, file descriptors), which is why connection pooling matters at scale.
  - Background workers handle specific jobs: `autovacuum launcher`, `background writer`, `checkpointer`, `WAL writer`, `stats collector`, and replication workers. Each has distinct tuning parameters.
  - Understand how this differs from MySQL's thread-per-connection model and why tools like PgBouncer exist specifically for Postgres.
  - References: [PostgreSQL architecture](https://www.postgresql.org/docs/current/tutorial-arch.html), [Background processes](https://www.postgresql.org/docs/current/bgworker.html)
- **Shared memory & buffers**: Data pages live in `shared_buffers`, a block of shared memory accessed by all backends.
  - Pages are 8 KB by default. `shared_buffers` is typically set to 25% of system RAM; the OS page cache handles the rest.
  - Dirty pages are flushed by the `bgwriter` and `checkpointer`; understanding this flow is critical for diagnosing I/O spikes.
  - References: [Resource consumption](https://www.postgresql.org/docs/current/runtime-config-resource.html), [`shared_buffers` tuning](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
- **MVCC (Multi-Version Concurrency Control)**: Postgres never updates rows in place — it writes new row versions and marks old ones dead.
  - Every row has hidden `xmin` (inserting transaction) and `xmax` (deleting transaction) system columns. Visibility is determined by comparing these with the current transaction's snapshot.
  - This is why `UPDATE` is essentially `INSERT` + mark old row dead, why tables bloat, and why `VACUUM` exists.
  - Readers never block writers and writers never block readers — this is MVCC's core promise.
  - References: [MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html), [Transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- **WAL (Write-Ahead Log)**: Every change is first written to WAL before being applied to data files.
  - WAL enables crash recovery, point-in-time recovery (PITR), and streaming replication. The `pg_wal/` directory holds WAL segments (16 MB each by default).
  - Checkpoints flush dirty buffers to disk so WAL can be recycled. Checkpoint tuning (`checkpoint_timeout`, `max_wal_size`) is a classic production knob.
  - References: [WAL](https://www.postgresql.org/docs/current/wal-intro.html), [WAL configuration](https://www.postgresql.org/docs/current/wal-configuration.html)
- **System catalogs**: `pg_catalog` is the schema where Postgres stores metadata about itself.
  - Key catalogs: `pg_class` (tables/indexes), `pg_attribute` (columns), `pg_index`, `pg_stat_*` views, `pg_database`, `pg_namespace` (schemas), `pg_proc` (functions).
  - `information_schema` is the SQL-standard portable view layer; `pg_catalog` is richer and Postgres-specific.
  - References: [System catalogs](https://www.postgresql.org/docs/current/catalogs.html), [information_schema](https://www.postgresql.org/docs/current/information-schema.html)

**Practice**: Install Postgres locally, connect with `psql`, and explore `pg_stat_activity`, `pg_class`, `pg_indexes`. Run `EXPLAIN` on a simple query and observe the process model with `ps aux | grep postgres`.

---

### 1.2 psql Mastery

- **Connection & navigation**: `psql -h host -p 5432 -U user -d db`. Learn `\l` (list databases), `\c` (connect), `\dn` (schemas), `\dt` (tables), `\d tablename` (describe), `\di` (indexes), `\df` (functions), `\dv` (views), `\du` (users/roles).
- **Meta-commands**: `\timing` (show query duration), `\x` (expanded display), `\e` (edit last query in `$EDITOR`), `\i file.sql` (execute file), `\watch 2` (rerun query every 2 seconds), `\copy` (client-side CSV import/export).
- **Variables & scripting**: `\set`, `\gset`, `\if/\elif/\endif`. `psql` is a legitimate scripting environment — use it for migrations and reporting.
- **Output formats**: `\pset format aligned|csv|html|json`, `\H` (HTML mode), `\o file` (redirect output).
- **Configuration**: `~/.psqlrc` for per-user defaults (e.g., `\set HISTFILE ~/.psql_history-:DBNAME`, `\set PROMPT1 '%n@%/%R%#%x '` to show transaction state).
- References: [psql reference](https://www.postgresql.org/docs/current/app-psql.html)

**Practice**: Write a `.psqlrc` that turns on timing, uses expanded display for wide rows, and shows the current transaction state in the prompt.

---

### 1.3 Data Types — Know Them All

- **Numeric**: `smallint`, `integer`, `bigint`, `numeric(p,s)`, `real`, `double precision`, `serial` (legacy), `bigserial`. Prefer `GENERATED AS IDENTITY` over `serial` in modern code — it's SQL-standard and avoids sequence-ownership footguns.
  - Use `numeric` for money; never `float`. Use `bigint` for anything that could conceivably exceed 2.1 billion.
  - References: [Numeric types](https://www.postgresql.org/docs/current/datatype-numeric.html)
- **Character**: `text`, `varchar(n)`, `char(n)`. In Postgres there's no performance difference between `text` and `varchar` — use `text` and enforce length with a `CHECK` constraint if needed. `char(n)` pads with spaces and is almost never what you want.
  - References: [Character types](https://www.postgresql.org/docs/current/datatype-character.html)
- **Date/time**: `timestamp`, `timestamptz` (timestamp with time zone), `date`, `time`, `interval`. Always use `timestamptz` — it stores UTC and converts on display. Mixing `timestamp` and `timestamptz` is a classic bug source.
  - `AT TIME ZONE`, `now()`, `current_timestamp`, `clock_timestamp()` (updates mid-transaction). Understand the difference.
  - References: [Date/time types](https://www.postgresql.org/docs/current/datatype-datetime.html)
- **Boolean**: `boolean` accepts `true/false/t/f/yes/no/1/0`.
- **UUID**: `uuid` type; generate via `gen_random_uuid()` (requires `pgcrypto` in older versions, built-in in 13+).
- **JSON & JSONB**: `json` stores exact text; `jsonb` stores a parsed binary form. Use `jsonb` 99% of the time — it's faster to query and supports GIN indexes. `json` is only useful if you need to preserve key order and whitespace exactly.
  - Operators: `->` (get field as json), `->>` (get field as text), `#>` (path), `#>>` (path as text), `@>` (contains), `<@` (contained by), `?` (key exists), `?|`, `?&`, `||` (concat), `-` (remove key), `jsonb_set()`.
  - References: [JSON types](https://www.postgresql.org/docs/current/datatype-json.html), [JSON functions](https://www.postgresql.org/docs/current/functions-json.html)
- **Arrays**: Any type can be an array: `integer[]`, `text[]`. Operators: `=`, `&&` (overlap), `@>` (contains), `ANY`, `ALL`, `unnest()`. Arrays are idiomatic Postgres — don't reach for a join table when a small, bounded array will do.
  - References: [Arrays](https://www.postgresql.org/docs/current/arrays.html)
- **Ranges**: `int4range`, `int8range`, `numrange`, `tsrange`, `tstzrange`, `daterange`. Range types + GiST exclusion constraints solve scheduling/overlap problems elegantly.
  - References: [Range types](https://www.postgresql.org/docs/current/rangetypes.html)
- **Network address**: `inet`, `cidr`, `macaddr`. Proper types with built-in operators instead of treating IPs as strings.
- **Geometric & Full-text**: `point`, `line`, `circle`, `polygon`; `tsvector`, `tsquery` for full-text search.
- **Enumerated & Composite**: `CREATE TYPE status AS ENUM (...)`. Composite types let columns hold structured records.
- **`hstore`**: Legacy key-value store; use `jsonb` for new work.

**Practice**: Build a table using `timestamptz`, `jsonb`, `uuid`, an `integer[]`, and a `tstzrange`. Query each with its native operators.

---

### 1.4 Constraints & Integrity

- **`NOT NULL`**: Default to `NOT NULL`; nullable should be a deliberate choice. `NULL` has three-valued-logic semantics that break intuition (`NULL = NULL` is `NULL`, not `true`).
- **`UNIQUE`**: Enforced by a unique index. Allows multiple `NULL` values by default (SQL-standard behavior). Use `NULLS NOT DISTINCT` (Postgres 15+) if you want `NULL`s to collide.
- **`PRIMARY KEY`**: Implicitly `UNIQUE` + `NOT NULL`. Prefer surrogate keys (identity/UUID) for mutable entities; natural keys are fine for truly immutable lookup data.
- **`FOREIGN KEY`**: `ON DELETE CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION`. `RESTRICT` fires immediately; `NO ACTION` defers to end-of-statement and can be `DEFERRABLE`.
- **`CHECK`**: Arbitrary boolean expressions. Use liberally — database-enforced invariants survive application bugs.
- **`EXCLUDE`**: Generalization of `UNIQUE` using any operator. The canonical use case: preventing overlapping time ranges. `EXCLUDE USING gist (room WITH =, during WITH &&)`.
- **Deferrable constraints**: `DEFERRABLE INITIALLY IMMEDIATE|DEFERRED` lets you temporarily violate FKs inside a transaction — useful for bulk-loading cyclic references.
- References: [Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

---

## Phase 2: Query Mastery

### 2.1 Advanced SQL Features

- **`DISTINCT ON (...)`**: Postgres-specific shortcut for "one row per group". `SELECT DISTINCT ON (user_id) user_id, event_time FROM events ORDER BY user_id, event_time DESC` returns the latest event per user.
  - References: [DISTINCT](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)
- **Common Table Expressions (CTEs)**: `WITH cte AS (...) SELECT ...`. As of PG 12, CTEs are inlined by default unless marked `MATERIALIZED`. Use CTEs to structure complex queries; use `MATERIALIZED` to force caching when the planner makes a bad choice.
  - **Recursive CTEs**: `WITH RECURSIVE` for trees, graphs, hierarchies, generating sequences. Essential for org charts, bill-of-materials, threaded comments.
  - References: [WITH queries](https://www.postgresql.org/docs/current/queries-with.html)
- **Window functions**: `ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, `LAG()`, `LEAD()`, `FIRST_VALUE()`, `LAST_VALUE()`, `NTH_VALUE()`, `NTILE()`, plus any aggregate used with `OVER (...)`.
  - `PARTITION BY` slices; `ORDER BY` sorts within a slice; `ROWS` / `RANGE` / `GROUPS` define the frame.
  - Window functions replace many self-joins and correlated subqueries. Running totals, rolling averages, deduplication, and rank-N-per-group are all one-liners.
  - References: [Window functions](https://www.postgresql.org/docs/current/tutorial-window.html), [Window function syntax](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS)
- **`GROUPING SETS`, `ROLLUP`, `CUBE`**: Compute multiple aggregation levels in one query. `GROUP BY ROLLUP (year, month, day)` gives per-day, per-month, per-year, and grand-total rows in a single pass.
- **`FILTER` clause**: `COUNT(*) FILTER (WHERE status = 'paid')` is cleaner than `COUNT(CASE WHEN ... THEN 1 END)`.
- **`LATERAL` joins**: A `LATERAL` subquery can reference columns from earlier `FROM` items. Essential for "top N per group" patterns and for joining against set-returning functions per row.
  ```sql
  SELECT u.id, recent.*
  FROM users u,
  LATERAL (SELECT * FROM orders WHERE user_id = u.id ORDER BY created_at DESC LIMIT 5) recent;
  ```
  - References: [LATERAL](https://www.postgresql.org/docs/current/queries-table-expressions.html#QUERIES-LATERAL)
- **Set operations**: `UNION`, `UNION ALL`, `INTERSECT`, `EXCEPT`. Prefer `UNION ALL` unless you specifically need dedup — `UNION` forces a sort/hash.
- **`VALUES` clause**: Not just for `INSERT`. `VALUES (1,'a'), (2,'b') AS t(id, name)` is an inline table you can join against.
- **Row constructors**: `WHERE (a, b) IN ((1, 'x'), (2, 'y'))` — compare tuples directly. Great for composite-key lookups.
- **`IS DISTINCT FROM`**: Null-safe inequality. `a IS DISTINCT FROM b` is `true` when one is null and the other isn't; plain `<>` returns null.

**Practice**: Write a query that, for each customer, returns their three most recent orders and a running 30-day total, using `LATERAL` and window functions.

---

### 2.2 Writing Data

- **`INSERT ... ON CONFLICT`** (upsert): `ON CONFLICT (col) DO UPDATE SET ...` or `DO NOTHING`. The conflict target must match a unique constraint/index. Use `EXCLUDED.col` to reference the proposed row.
  - References: [INSERT](https://www.postgresql.org/docs/current/sql-insert.html)
- **`RETURNING`**: `INSERT`, `UPDATE`, `DELETE` can all return modified rows. Combine with CTEs to build data-pipeline-in-a-query patterns (`WITH moved AS (DELETE ... RETURNING *) INSERT INTO archive SELECT * FROM moved`).
- **`UPDATE ... FROM`**: Update one table from a join with another. Cleaner than correlated subqueries.
- **`DELETE ... USING`**: Same idea for deletes.
- **`MERGE`** (PG 15+): SQL-standard conditional `INSERT`/`UPDATE`/`DELETE` in one statement. Know the differences from `ON CONFLICT` — `MERGE` handles `UPDATE`+`INSERT`+`DELETE` together but has its own concurrency caveats.
- **Bulk loading**: `COPY` is 10–100× faster than `INSERT` for bulk imports. Use `\copy` in psql for client-side files; `COPY` for server-side. `pg_bulkload` and `pg_restore -j` for the absolute fastest paths.

---

### 2.3 Transactions & Isolation

- **ACID**: Postgres is fully ACID. Know what each letter actually means and where Postgres enforces it.
- **Isolation levels**: `READ UNCOMMITTED` (treated as `READ COMMITTED` in Postgres — dirty reads are never possible), `READ COMMITTED` (default), `REPEATABLE READ` (snapshot isolation), `SERIALIZABLE` (SSI).
  - `READ COMMITTED`: each statement sees a fresh snapshot.
  - `REPEATABLE READ`: one snapshot for the whole transaction. Can fail with `could not serialize access` errors on concurrent writes.
  - `SERIALIZABLE`: true serializability via predicate locking (SSI). Retries are part of the programming model — always code a retry loop.
  - References: [Transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- **Row-level locking**: `SELECT ... FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE`. `SKIP LOCKED` and `NOWAIT` variants are the foundation of queue workers on Postgres.
  - References: [Explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- **Advisory locks**: `pg_advisory_lock`, `pg_try_advisory_lock`. Application-level locks scoped to a connection or a transaction. Useful for distributed cron-style coordination.
- **Savepoints**: `SAVEPOINT`, `ROLLBACK TO`, `RELEASE`. Subtransactions within a transaction.
- **Two-phase commit**: `PREPARE TRANSACTION` for distributed commit protocols (rarely needed outside XA systems).

**Practice**: Build a job queue using `SELECT ... FOR UPDATE SKIP LOCKED`. Then write a test that demonstrates the need for a retry loop under `SERIALIZABLE`.

---

## Phase 3: Indexing & Performance

### 3.1 Index Types

- **B-tree** (default): Ordered, supports `=`, `<`, `>`, `BETWEEN`, `LIKE 'prefix%'`, `ORDER BY`, `IS NULL`. 95% of your indexes will be B-trees.
- **Hash**: `=` only. WAL-logged since PG 10. Rarely worth choosing over B-tree.
- **GIN (Generalized Inverted Index)**: For composite values — `jsonb`, arrays, `tsvector`, trigrams. "The index of indexes." Slower to write, very fast to read.
  - `jsonb_path_ops` operator class is smaller/faster if you only need `@>` containment.
- **GiST (Generalized Search Tree)**: For geometric data, ranges, full-text, nearest-neighbor queries, exclusion constraints. Extensible via operator classes.
- **SP-GiST**: Space-partitioned GiST; good for non-balanced data like phone numbers, IP ranges, quadtrees.
- **BRIN (Block Range Index)**: Tiny index that stores min/max per block range. Perfect for huge, naturally-ordered tables (time-series, append-only logs). Can be 1000× smaller than a B-tree with near-zero maintenance cost when data is correlated with physical order.
- **Bloom** (extension): Multi-column indexing where any column might be queried. Probabilistic, small.
- References: [Index types](https://www.postgresql.org/docs/current/indexes-types.html)

### 3.2 Index Features

- **Multi-column indexes**: `(a, b, c)` can serve queries on `a`, `(a, b)`, `(a, b, c)`, but NOT on `b` alone. Leftmost-prefix rule.
- **Partial indexes**: `CREATE INDEX ... WHERE status = 'active'`. Smaller index, faster scans for selective predicates that also appear in queries.
- **Expression indexes**: `CREATE INDEX ON users (lower(email))`. The query must use the exact expression to hit the index.
- **Covering indexes**: `INCLUDE (col1, col2)` adds non-key columns so index-only scans can avoid the heap.
- **Unique indexes**: Enforce `UNIQUE`. You can build unique partial indexes — "only one active row per user."
- **`CREATE INDEX CONCURRENTLY`**: Builds without an exclusive lock. Always use this in production. It takes longer and can fail — a failed concurrent index leaves an `INVALID` index you must `DROP` and rebuild.
- **`REINDEX CONCURRENTLY`**: Rebuild bloated indexes without downtime (PG 12+).
- References: [Indexes](https://www.postgresql.org/docs/current/indexes.html)

### 3.3 Query Planner & EXPLAIN

- **`EXPLAIN`**: Shows the plan. **`EXPLAIN ANALYZE`**: Executes the query and shows actual times. **`EXPLAIN (ANALYZE, BUFFERS)`**: Adds buffer hit/read counts.
  - `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT)` is the power-user form.
- **Read the plan bottom-up**: Leaf nodes run first. Each node shows estimated rows, actual rows, and time.
- **Key scan types**:
  - `Seq Scan`: Read whole table. Appropriate for small tables or low-selectivity queries.
  - `Index Scan`: Traverse index, then fetch heap tuples.
  - `Index Only Scan`: Entirely from index (visibility map permitting).
  - `Bitmap Heap Scan`: Build a bitmap of matching tuples from one or more indexes, then fetch. Good for medium selectivity.
  - `Nested Loop`, `Hash Join`, `Merge Join`: The three join strategies.
- **Statistics**: The planner uses `pg_statistic` (populated by `ANALYZE`). If estimates are wildly off, run `ANALYZE`, raise `default_statistics_target`, or create extended statistics (`CREATE STATISTICS`) for correlated columns.
- **Planner parameters**: `random_page_cost` (set to 1.1 for SSDs), `effective_cache_size`, `work_mem`, `enable_*` flags for debugging.
- References: [EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html), [Planner stats](https://www.postgresql.org/docs/current/planner-stats.html)

**Practice**: Create a 10M-row table, write a query that does a sequential scan, add an index, re-run `EXPLAIN ANALYZE`, and interpret every field. Then write a query with a bad row estimate and fix it with extended statistics.

---

### 3.4 VACUUM, Bloat, and Autovacuum

- **What VACUUM does**: Marks dead tuples reusable, updates the visibility map, and prevents transaction ID wraparound (freezing). Does NOT return space to the OS — that requires `VACUUM FULL` (rewrites the table with an exclusive lock) or `pg_repack` (no-lock rewrite via extension).
- **Autovacuum**: Runs continuously in the background. Per-table thresholds: `autovacuum_vacuum_threshold` + `autovacuum_vacuum_scale_factor` * `reltuples`. Tune per-table for hot tables (`ALTER TABLE ... SET (autovacuum_vacuum_scale_factor = 0.01)`).
- **Bloat**: Repeatedly updated tables accumulate dead tuples faster than autovacuum cleans them. Diagnose with `pgstattuple` extension or queries against `pg_stat_user_tables`.
- **Transaction ID wraparound**: Postgres transaction IDs are 32-bit. If a table isn't vacuumed for ~2 billion transactions, the cluster shuts down to prevent data loss. Monitor `datfrozenxid` age religiously.
- **Freezing**: Old tuples are frozen so their XIDs can be recycled. `VACUUM FREEZE` forces it.
- References: [Routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html), [Autovacuum](https://www.postgresql.org/docs/current/routine-vacuuming.html#AUTOVACUUM)

---

## Phase 4: Schemas, Roles, Security

### 4.1 Schemas & Search Path

- **Schemas** are namespaces inside a database. `CREATE SCHEMA analytics`. The default is `public`.
- **`search_path`**: Ordered list Postgres walks when resolving an unqualified name. Default is `"$user", public`. Set it explicitly for predictability: `SET search_path = app, public`.
- **Multi-tenancy**: Schema-per-tenant is a Postgres-idiomatic pattern — cleaner than a tenant_id column, more resource-efficient than a database-per-tenant.
- References: [Schemas](https://www.postgresql.org/docs/current/ddl-schemas.html)

### 4.2 Roles & Privileges

- **Roles unify users and groups**. `CREATE ROLE alice LOGIN PASSWORD '...'`; `CREATE ROLE readers`. `GRANT readers TO alice`. Roles without `LOGIN` are effectively groups.
- **Privileges**: `GRANT SELECT, INSERT ON TABLE ... TO ...`. Also on schemas (`USAGE`, `CREATE`), databases (`CONNECT`, `TEMPORARY`), functions, sequences, types.
- **Default privileges**: `ALTER DEFAULT PRIVILEGES FOR ROLE ... IN SCHEMA ... GRANT SELECT ON TABLES TO ...`. Critical for getting permissions right on objects that don't exist yet.
- **Ownership**: The owner can always `DROP` and `ALTER`. `ALTER TABLE ... OWNER TO ...` transfers it.
- **Row-Level Security (RLS)**: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`, then `CREATE POLICY ...`. Policies are `WITH CHECK` (for writes) and `USING` (for reads). RLS lets you enforce multi-tenant isolation at the database layer, which is much harder to bypass than application-level filtering.
- **`SECURITY DEFINER` functions**: Run with the function-owner's privileges. Powerful and dangerous — always `SET search_path` explicitly inside them to avoid `search_path` attacks.
- References: [Privileges](https://www.postgresql.org/docs/current/ddl-priv.html), [RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

### 4.3 Authentication — pg_hba.conf

- **`pg_hba.conf`** is the host-based authentication file. Each line: `type database user address method`. Types: `local` (Unix socket), `host`, `hostssl`, `hostnossl`.
- **Methods**: `trust` (accept without password — dev only), `password` (cleartext, never use), `md5` (legacy), `scram-sha-256` (current standard), `cert` (client certs), `peer` (match OS user to DB user on local socket), `ident`.
- **Rules match top-down**; first match wins.
- References: [pg_hba.conf](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)

### 4.4 SSL & Encryption

- Enable `ssl = on`, configure `ssl_cert_file`/`ssl_key_file`. Require SSL by setting client connections to use `hostssl` with `clientcert=verify-full`.
- Postgres does **not** encrypt data at rest natively. Use OS-level disk encryption (LUKS, filesystem-level) or cloud-managed encryption. Column-level encryption via `pgcrypto` is an option for individual sensitive fields.

---

## Phase 5: Procedural & Server-Side Programming

### 5.1 Functions & Stored Procedures

- **Functions** return values and run inside a transaction. **Procedures** (PG 11+) can `COMMIT`/`ROLLBACK`.
- **Languages**: `plpgsql` (default, full control flow), `sql` (simple, inlineable), `plpython3u`, `plperlu`, `plv8`. Untrusted (`u`) versions can touch the filesystem.
- **`LANGUAGE sql` functions** can be inlined by the planner, which is often faster than `plpgsql`. Use `sql` for simple one-expression functions.
- **Volatility**: `IMMUTABLE` (same input, same output, no reads), `STABLE` (same within a transaction), `VOLATILE` (default; may have side effects). Mark correctly — the planner uses this for optimization and for deciding whether to use a function in an index expression.
- **Parameters**: `IN`, `OUT`, `INOUT`, `VARIADIC`. Named parameters with `=>` syntax at call sites improve readability.
- **`RETURNS TABLE`**, **`RETURNS SETOF`**: Set-returning functions. Combine with `LATERAL` for powerful composable queries.
- References: [User-defined functions](https://www.postgresql.org/docs/current/xfunc.html), [PL/pgSQL](https://www.postgresql.org/docs/current/plpgsql.html)

### 5.2 Triggers

- **Row-level** (`FOR EACH ROW`) vs **statement-level** (`FOR EACH STATEMENT`).
- **Timing**: `BEFORE`, `AFTER`, `INSTEAD OF` (views only).
- **Events**: `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`.
- **Transition tables** (PG 10+): `REFERENCING OLD TABLE AS ... NEW TABLE AS ...` for set-based statement triggers — far more efficient than row-by-row.
- **Common uses**: audit logging, denormalized caches, enforcing complex invariants, `updated_at` timestamps.
- **Be careful**: triggers are invisible to callers. Heavy trigger chains are a notorious source of "why is this slow" surprises.
- References: [Triggers](https://www.postgresql.org/docs/current/triggers.html)

### 5.3 Event Triggers

- Fire on DDL events (`ddl_command_start`, `ddl_command_end`, `sql_drop`, `table_rewrite`). Useful for schema-change auditing and enforcing DDL policies cluster-wide.
- References: [Event triggers](https://www.postgresql.org/docs/current/event-triggers.html)

### 5.4 LISTEN / NOTIFY

- Lightweight pub-sub inside Postgres. `NOTIFY channel, 'payload'`; clients `LISTEN channel`. Payloads ≤ 8 KB, delivered only to currently-connected listeners (no persistence).
- Great for real-time cache invalidation, or telling app servers "something changed, refetch." Not a replacement for a real message queue.
- References: [NOTIFY](https://www.postgresql.org/docs/current/sql-notify.html)

---

## Phase 6: Advanced Features

### 6.1 Views, Materialized Views, and Partitioning

- **Views**: Stored queries. Updatable automatically if they're simple enough; otherwise define `INSTEAD OF` triggers.
- **Materialized views**: Snapshot of a query's result, stored on disk. `REFRESH MATERIALIZED VIEW [CONCURRENTLY] view_name`. `CONCURRENTLY` requires a unique index and keeps the view readable during refresh.
- **Partitioning** (declarative, PG 10+): `PARTITION BY RANGE | LIST | HASH`. Each partition is a real table; the parent is a routing shell. Partition pruning eliminates partitions at plan or execution time.
  - Use for time-series (range by month), multi-tenant (list by tenant), or sharding-by-hash.
  - `pg_partman` extension automates time-based partition creation and retention.
  - Indexes must be declared on the parent and are cascaded; constraints and defaults behave similarly. Foreign keys TO a partitioned table are supported; FKs FROM are supported PG 12+.
- References: [Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html), [Materialized views](https://www.postgresql.org/docs/current/rules-materializedviews.html)

### 6.2 Full-Text Search

- **Types**: `tsvector` (document) and `tsquery` (query). Match with `@@`.
- **Configuration**: `english`, `simple`, etc. Controls tokenization, stop-word removal, and stemming.
- **`to_tsvector('english', body)`** turns text into a searchable vector. Index with GIN for fast `@@` queries.
- **Ranking**: `ts_rank`, `ts_rank_cd`. Highlight matches with `ts_headline`.
- **Weight categories**: `setweight(..., 'A'|'B'|'C'|'D')` lets you score title matches higher than body.
- **When to reach for something else**: If you need fuzzy matching at scale, synonyms, multilingual, or facets, consider pairing with trigrams (`pg_trgm`) or an external engine (Elasticsearch, Meilisearch). Postgres FTS is excellent for "good enough search inside the DB you already have."
- References: [Full-text search](https://www.postgresql.org/docs/current/textsearch.html)

### 6.3 Extensions You Must Know

- **`pg_stat_statements`**: Track execution stats for every query. First extension to enable in any real deployment.
- **`pgcrypto`**: Hashing, encryption, `gen_random_uuid()` (pre-13).
- **`pg_trgm`**: Trigram similarity and fuzzy `LIKE '%substring%'` matching with GIN/GiST indexes.
- **`uuid-ossp`**: UUID generators (largely obsolete now that `gen_random_uuid()` is built in).
- **`hstore`**: Key-value; prefer `jsonb`.
- **`citext`**: Case-insensitive text type.
- **`btree_gin` / `btree_gist`**: Add B-tree-style equality ops to GIN/GiST indexes so you can combine them with range or containment ops in one multi-column index.
- **`tablefunc`**: `crosstab()` for pivoting.
- **`postgres_fdw`**: Foreign-data wrapper to query other Postgres databases.
- **`pgvector`**: Vector similarity search for embeddings (AI/ML use cases).
- **`PostGIS`**: Geospatial extension — a full GIS platform on top of Postgres. If you ever touch geo data, learn this.
- **`TimescaleDB`**: Time-series extension with hypertables, continuous aggregates, compression.
- References: [Extensions](https://www.postgresql.org/docs/current/contrib.html)

### 6.4 Foreign Data Wrappers & Logical Replication

- **FDW**: `CREATE EXTENSION postgres_fdw`, `CREATE SERVER`, `CREATE USER MAPPING`, `IMPORT FOREIGN SCHEMA`. Query a remote DB as if it were a local table. Wrappers exist for MySQL, MongoDB, S3, Parquet, and arbitrary REST APIs.
- **Logical replication** (PG 10+): Publisher/subscriber model over WAL logical decoding. Replicate subsets of tables across Postgres versions and across networks.
  - Differs from physical (streaming) replication: logical replicates row changes, physical replicates bytes.
  - Used for zero-downtime major-version upgrades, partial replicas, cross-cluster ETL.
- References: [FDW](https://www.postgresql.org/docs/current/sql-createforeigndatawrapper.html), [Logical replication](https://www.postgresql.org/docs/current/logical-replication.html)

---

## Phase 7: Replication, High Availability, Backups

### 7.1 Physical (Streaming) Replication

- **Primary + standby(s)**. WAL is streamed from primary to standby over a replication connection. Standbys can be `hot_standby` (read-only queries allowed).
- **Synchronous vs asynchronous**: `synchronous_commit`, `synchronous_standby_names`. Sync gives zero data loss but blocks on commit; async gives higher throughput but a small RPO.
- **Replication slots**: Ensure the primary retains WAL until the standby has consumed it. Without a slot, a slow standby can fall permanently behind. Physical slots for streaming; logical slots for logical decoding.
- **`pg_basebackup`**: Bootstrap a standby from a running primary.
- References: [Streaming replication](https://www.postgresql.org/docs/current/warm-standby.html#STREAMING-REPLICATION)

### 7.2 Failover & HA

- Postgres does not ship with automatic failover. Use one of: **Patroni** (industry standard; uses etcd/Consul/ZK for leader election), **repmgr**, **pg_auto_failover**, or cloud-managed (RDS, Cloud SQL, Aurora).
- Understand split-brain risk and why a consensus store is non-negotiable for automated failover.
- **Connection routing**: HAProxy, PgBouncer, or app-layer aware drivers handle traffic redirection post-failover.

### 7.3 Backups

- **`pg_dump`** (logical): Per-database SQL or custom-format dump. Slow, but version-portable. `pg_restore -j N` for parallel restore.
- **`pg_basebackup`** (physical): Snapshot of the cluster's on-disk state. Fast, large.
- **WAL archiving**: `archive_mode=on`, `archive_command=...`. Ship every WAL segment off-site. This enables PITR.
- **Point-in-Time Recovery (PITR)**: Restore a base backup, then replay WAL up to any moment. Requires base backups + archived WAL.
- **Tools**: `pgBackRest` (best-in-class), `barman`, `wal-g`. Use one of these in production — don't roll your own.
- References: [Backup and restore](https://www.postgresql.org/docs/current/backup.html), [PITR](https://www.postgresql.org/docs/current/continuous-archiving.html)

### 7.4 Connection Pooling

- Every Postgres connection is a process. Even idle connections hold memory. 10,000 app "connections" should become ~100 real Postgres connections via a pooler.
- **PgBouncer**: The standard. Three pool modes:
  - `session` (default): dedicate a backend per client for the session's duration.
  - `transaction`: release backend after each txn; incompatible with prepared statements, `SET`, session variables.
  - `statement`: even stricter, mostly avoided.
- **Pgpool-II**: Does pooling, load balancing, and limited parallel query. More complex.
- References: [PgBouncer](https://www.pgbouncer.org/)

---

## Phase 8: Operations & Observability

### 8.1 Configuration Files

- **`postgresql.conf`**: Main config. Most parameters are `SIGHUP` reloadable (`pg_reload_conf()`); some require restart.
- **`postgresql.auto.conf`**: Written by `ALTER SYSTEM`. Loaded after `postgresql.conf` so it overrides.
- **`pg_hba.conf`**: Auth rules. `SIGHUP` to reload.
- Key parameters to know cold: `shared_buffers`, `work_mem`, `maintenance_work_mem`, `effective_cache_size`, `wal_buffers`, `max_wal_size`, `checkpoint_timeout`, `checkpoint_completion_target`, `random_page_cost`, `default_statistics_target`, `max_connections`, `autovacuum_*`.

### 8.2 Monitoring

- **`pg_stat_activity`**: Current sessions, queries, wait events, states.
- **`pg_stat_statements`**: Aggregate stats per normalized query. `total_exec_time`, `mean_exec_time`, `calls`, `rows`, buffer hits.
- **`pg_stat_user_tables`**, **`pg_stat_user_indexes`**: Per-table and per-index access and autovacuum stats.
- **`pg_stat_replication`**, **`pg_stat_wal_receiver`**: Replication lag and position.
- **`pg_locks`**: Currently held locks. Join with `pg_stat_activity` to find blocking sessions.
- **`pg_stat_bgwriter`**, **`pg_stat_database`**: Cluster-wide I/O and activity.
- **Wait events**: `pg_stat_activity.wait_event_type` / `wait_event`. Critical for diagnosing "why is everything slow."
- **External**: pgBadger (log analyzer), Prometheus `postgres_exporter`, Datadog, pganalyze.
- References: [The statistics collector](https://www.postgresql.org/docs/current/monitoring-stats.html)

### 8.3 Logging

- `log_min_duration_statement`: Log slow queries. Set to a threshold that catches regressions without flooding.
- `log_checkpoints`, `log_connections`, `log_disconnections`, `log_lock_waits`, `log_temp_files`, `log_autovacuum_min_duration`.
- `log_line_prefix = '%m [%p] %q%u@%d '` at minimum.
- Parse logs with pgBadger for actionable reports.

### 8.4 Upgrades

- **Minor**: Binary-compatible. Swap the binaries, restart.
- **Major**: `pg_upgrade` in place (fast, uses hard links with `--link`) or logical replication for zero-downtime. Read release notes for every major version — they list breaking behavior.

---

## Phase 9: Production Patterns & Pitfalls

- **Always use `timestamptz`**.
- **Always index foreign keys** on the referencing side — Postgres doesn't do it for you.
- **Beware `SELECT *` in views**: columns added to base tables don't propagate; changing column types can break the view.
- **Careful with `text` vs `varchar` in joins**: type coercions can defeat index usage.
- **`ORM N+1`**: Every ORM can produce this. Use `EXPLAIN` and `pg_stat_statements` to catch it.
- **Long-running transactions block vacuum**: one idle-in-transaction connection can pin dead tuples cluster-wide.
- **Monitor `xid age`**: `SELECT datname, age(datfrozenxid) FROM pg_database;`. Alert well before 1.5 billion.
- **Don't use `NOT IN` with nullable columns**: returns empty if the list contains `NULL`. Use `NOT EXISTS` instead.
- **Avoid `COUNT(*)` on huge tables in hot paths**: Postgres must scan. Use estimates from `pg_class.reltuples` or a cached counter.
- **`OFFSET` scales poorly**: For pagination, use keyset/cursor pagination (`WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT N`).
- **Migrations**: Always `CONCURRENTLY` for indexes. Use `ALTER TABLE ... ADD COLUMN` without a default in PG 11+ (metadata-only). Splitting NOT NULL additions into add-nullable / backfill / set-not-null prevents long locks.
- **Schema changes are DDL**: they take `AccessExclusiveLock`. Set a `lock_timeout` before schema migrations so they fail fast instead of queuing behind a long query and blocking the world.

---

## Phase 10: Benchmarking, Tooling, Ecosystem

- **`pgbench`**: Built-in load generator. Run TPC-B-like workloads or custom scripts to benchmark changes.
- **`pg_repack`**: Online table/index rewrite to reclaim bloat without `VACUUM FULL`'s lock.
- **`pg_partman`**: Automated partition management.
- **`pgAdmin`, `DBeaver`, `DataGrip`, `TablePlus`**: GUI clients. Each has strengths; pick one and know its power features.
- **`pgTap`**: Unit testing framework that runs inside the database.
- **Migration tools**: `Flyway`, `Liquibase`, `sqitch`, `golang-migrate`, framework-specific (Alembic for SQLAlchemy, Django migrations, Active Record).
- **Schema diff**: `migra`, `apgdiff`.

---

## Mastery Checklist

You've reached mastery when you can:

1. Explain MVCC, WAL, and autovacuum interactions from memory.
2. Read an `EXPLAIN (ANALYZE, BUFFERS)` plan and identify the bottleneck within 60 seconds.
3. Choose the right index type (B-tree, GIN, GiST, BRIN) for a given workload without hesitation.
4. Design a schema that uses `jsonb`, arrays, ranges, and exclusion constraints appropriately — not out of enthusiasm, but because each fits.
5. Implement multi-tenant isolation with RLS and justify why it's harder to bypass than application checks.
6. Write recursive CTEs, window functions, and `LATERAL` joins fluently.
7. Debug a production incident using `pg_stat_activity`, `pg_locks`, `pg_stat_statements`, and wait events.
8. Set up streaming replication with a replication slot, promote a standby, and explain the data-loss window.
9. Execute a zero-downtime major version upgrade using logical replication.
10. Point to a query that's slow, tune it, and prove the fix with numbers — not vibes.

---

## Recommended Reading Path

1. **Official docs** — Tutorial, then Chapter 5 (DDL), Chapter 7 (Queries), Chapter 11 (Indexes), Chapter 13 (Concurrency Control), Chapter 14 (Performance).
2. **"The Art of PostgreSQL"** by Dimitri Fontaine.
3. **"PostgreSQL 14 Internals"** by Egor Rogov — free PDF, the best deep dive available.
4. **"PostgreSQL High Performance"** by Gregory Smith.
5. **Release notes** for every major version from 10 onward. The feature velocity is real; a 2019 mental model is out of date.
6. **Blogs**: Crunchy Data, EDB, pganalyze, Citus Data, Hans-Jürgen Schönig / Cybertec, Lukas Fittl's 5-Minutes-of-Postgres.

---

Mastery of PostgreSQL is less about memorizing syntax and more about internalizing its internals — MVCC, WAL, planner statistics, autovacuum — so that when something misbehaves, you can reason from first principles instead of guessing. Build real systems, break them, and read the logs until the data tells you why.

# Advanced PostgreSQL Study Guide

This guide is a depth-first treatment of the PostgreSQL engine and high-performance Postgres for engineers who already write SQL and want to understand — and control — what happens beneath their queries. It is one of a three-guide set: the [PostgreSQL Feature Reference](POSTGRES.md) covers the surface area (types, DDL, query features, the SQL you write), this guide covers the machine that runs it, and [PostgreSQL Extensions in Production](POSTGRES_EXTENSIONS.md) covers the ecosystem (PostGIS, pgvector, TimescaleDB, Citus, and which extensions are worth running in production).

Its thesis, the throughline for everything below: **almost every Postgres performance and operations problem is a consequence of two design choices — MVCC (every write creates a new row version) and WAL (every change is logged before it is applied).** MVCC is why readers never block writers, why tables bloat, why `VACUUM` exists, and why transaction IDs can wrap around. WAL is why crash recovery, replication, and point-in-time recovery all work the same way. Internalize those two and the rest — the planner's row estimates, lock contention, autovacuum tuning, checkpoint spikes, replication lag — stops being a grab bag of unrelated knobs and becomes a single coherent system.

Tested against PostgreSQL 16/17; most material applies to 13+, with version notes where it matters.

Primary references: the [official PostgreSQL documentation](https://www.postgresql.org/docs/current/) (the internals chapters — [MVCC](https://www.postgresql.org/docs/current/mvcc.html), [WAL](https://www.postgresql.org/docs/current/wal-intro.html), [routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html) — are excellent and underread), Egor Rogov's [*PostgreSQL Internals*](https://postgrespro.com/community/books/internals) (free PDF — the definitive deep dive on MVCC, vacuum, and the planner), the [pg_stat_statements](https://www.postgresql.org/docs/current/pgstatstatements.html) and [pgbench](https://www.postgresql.org/docs/current/pgbench.html) docs, and [explain.dalibo.com](https://explain.dalibo.com/) for visual plan analysis.

---

## Table of Contents

1. [The Storage & MVCC Engine](#1-the-storage--mvcc-engine)
2. [WAL, Checkpoints & Durability](#2-wal-checkpoints--durability)
3. [VACUUM, Autovacuum & Wraparound](#3-vacuum-autovacuum--wraparound)
4. [The Query Planner & Statistics](#4-the-query-planner--statistics)
5. [Reading EXPLAIN Like a Pro](#5-reading-explain-like-a-pro)
6. [Index Internals & Strategy](#6-index-internals--strategy)
7. [Locking & Concurrency at Scale](#7-locking--concurrency-at-scale)
8. [Connections & Pooling](#8-connections--pooling)
9. [The Performance Tuning Ladder](#9-the-performance-tuning-ladder)
10. [Partitioning at Scale](#10-partitioning-at-scale)
11. [Replication & High Availability](#11-replication--high-availability)
12. [Backup, PITR & Disaster Recovery](#12-backup-pitr--disaster-recovery)
13. [Observability](#13-observability)
14. [Production Patterns & Pitfalls](#14-production-patterns--pitfalls)
15. [Benchmarking](#15-benchmarking)
16. [Worked Performance Recipes](#16-worked-performance-recipes)
17. [Decision Trees](#17-decision-trees)

---

## 1. The Storage & MVCC Engine

Everything starts with how a row physically lives on disk ([docs: database page layout](https://www.postgresql.org/docs/current/storage-page-layout.html)).

### Pages and tuples

A table (the "heap") is an array of fixed-size **8 KB pages**. Each page holds a header, an array of item pointers, and the tuples (rows) themselves growing from the end. Every tuple carries a 23-byte header before its user data, and the header is where MVCC lives:

| Field | Meaning |
|---|---|
| `xmin` | Transaction ID that **inserted** this row version |
| `xmax` | Transaction ID that **deleted/updated** it (0 if live) |
| `ctid` | Physical location `(page, item)` of this version |
| `t_infomask` | Hint bits (committed/aborted/frozen) |

You can see these hidden system columns directly:

```sql
SELECT ctid, xmin, xmax, * FROM accounts WHERE id = 1;
-- Update it, then re-run: ctid and xmin change — it's a NEW physical row.
```

### MVCC: an UPDATE is an INSERT + a tombstone

Postgres never modifies a row in place. An `UPDATE` writes a **new tuple version** and sets the old version's `xmax` to the current transaction. A `DELETE` just sets `xmax`. The old versions stay on the page until `VACUUM` reclaims them. Consequences that define day-to-day Postgres:

- **Readers never block writers, writers never block readers.** Each transaction sees the versions visible to its *snapshot* (a set of xmin/xmax it compares against). This is MVCC's core promise.
- **Tables bloat.** Dead versions accumulate; the heap grows even if the live row count is flat. Bloat is not a bug — it's the cost of lock-free reads.
- **Indexes point at versions, not rows.** Every index normally needs an entry for every tuple version (mitigated by HOT, below).

### HOT updates — the optimization that fights bloat

A **Heap-Only Tuple (HOT)** update happens when (a) no *indexed* column changed and (b) there's free space on the same page. The new version is chained to the old via `ctid` on the same page, and **no new index entries are created**. This is the single biggest lever for update-heavy tables.

You buy room for HOT updates with **FILLFACTOR** — leave slack on each page so updates stay local:

```sql
-- Hot, frequently-updated table: leave 15% of each page free for in-page new versions
ALTER TABLE sessions SET (fillfactor = 85);
-- Existing data needs a rewrite to take effect:
VACUUM FULL sessions;   -- or pg_repack to avoid the lock

-- Verify HOT is working: n_tup_hot_upd should track n_tup_upd
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / nullif(n_tup_upd,0), 1) AS hot_pct
FROM pg_stat_user_tables WHERE relname = 'sessions';
```

> Practical rule: if a hot table has a low HOT-update ratio, find the index on a frequently-updated column and ask whether you actually need it. One unnecessary index on a churning column can double your write amplification.

### TOAST — how big values are stored

Any value that won't fit comfortably in a page (roughly > 2 KB) is compressed and/or pushed out-of-line into a hidden **TOAST** table, leaving a small pointer in the main tuple. This is automatic and per-column-tunable:

```sql
ALTER TABLE docs ALTER COLUMN body SET STORAGE EXTERNAL;  -- store out-of-line, skip compression (faster substring)
ALTER TABLE docs ALTER COLUMN body SET COMPRESSION lz4;   -- PG14+: lz4 is much faster than default pglz
```

Why you care: a wide `jsonb`/`text` column you rarely read costs little when not selected (TOAST is fetched lazily), but `SELECT *` on a TOAST-heavy table forces detoasting on every row. It's a concrete reason to avoid `SELECT *`.

### The Visibility Map and Free Space Map

Two side structures per table drive performance:

- **Visibility Map (VM):** one bit per page meaning "all tuples here are visible to everyone." It powers **index-only scans** (skip the heap) and lets `VACUUM` skip already-clean pages.
- **Free Space Map (FSM):** tracks reusable space so inserts/HOT-updates find a home.

A stale VM (because `VACUUM` hasn't run) silently turns fast index-only scans back into heap-fetching index scans. This is the hidden link between vacuuming and read performance.

### Practice

- Insert a row, capture its `ctid`, `UPDATE` a non-indexed column, and confirm the `ctid` changes but `n_tup_hot_upd` increments.
- Add an index to that column, repeat, and watch the HOT ratio collapse.
- Find your most-bloated tables with the bloat query in [§13](#13-observability) and correlate with HOT ratios.

---

## 2. WAL, Checkpoints & Durability

The **[Write-Ahead Log](https://www.postgresql.org/docs/current/wal-intro.html)** is the second pillar. Every change is written to WAL *before* the data page is modified, so a crash can always be replayed forward. The same log powers replication and PITR.

### The write path

```
Change → WAL record in wal_buffers → flushed to pg_wal/ on COMMIT (fsync)
       → data page modified in shared_buffers (dirty)
       → later flushed to the data file by a CHECKPOINT (or bgwriter)
```

The data files lag WAL. On crash recovery, Postgres replays WAL from the last checkpoint forward. This is why a `COMMIT` only needs to fsync the (sequential, cheap) WAL, not the (scattered, expensive) data pages.

### Durability knobs

```sql
-- The big one. 'on' = fsync WAL at commit (durable). Per-transaction tunable.
SET synchronous_commit = on;        -- off = fast but lose last ~few hundred ms on crash (NOT corruption)
```

| `synchronous_commit` | Meaning |
|---|---|
| `on` | Commit waits for local WAL flush (and sync standby if configured) — default |
| `off` | Returns before WAL flush; a crash loses recent commits but **never corrupts** |
| `local` | Local flush only, ignore standbys |
| `remote_write` / `remote_apply` | Wait for standby to receive / replay (see [§11](#11-replication--high-availability)) |

Setting `synchronous_commit = off` for a bulk-import or a tolerate-loss workload is one of the highest-ROI single-line speedups Postgres offers.

### Full-page writes

The first change to a page after a checkpoint logs the **entire page** to WAL (protection against torn pages on crash). This is why WAL volume spikes right after each checkpoint and why **`wal_compression`** matters:

```sql
ALTER SYSTEM SET wal_compression = lz4;   -- PG15+ supports lz4/zstd; shrinks full-page images
```

### Checkpoint tuning

A checkpoint flushes all dirty buffers and lets old WAL be recycled. Too-frequent checkpoints mean repeated full-page-write storms; too-rare means long crash recovery and big WAL.

```conf
checkpoint_timeout = 15min            # default 5min — longer = fewer FPW storms
max_wal_size = 16GB                   # let WAL grow between timed checkpoints
checkpoint_completion_target = 0.9    # spread the flush over 90% of the interval (default since PG14)
```

Diagnose pressure: if checkpoints are happening because WAL filled up (not on the timer), they're too aggressive.

```sql
-- PG17+ exposes this in pg_stat_checkpointer; earlier in pg_stat_bgwriter
SELECT num_timed, num_requested FROM pg_stat_checkpointer;
-- num_requested >> num_timed  →  raise max_wal_size
```

### Practice

- Run a write-heavy `pgbench` (see [§15](#15-benchmarking)) with `synchronous_commit` on vs off and measure TPS.
- Watch `pg_current_wal_lsn()` grow during a bulk load; compute MB of WAL per million rows.
- Lower `checkpoint_timeout` to `30s`, run a load, and observe `num_requested` climb.

---

## 3. VACUUM, Autovacuum & Wraparound

MVCC's bill comes due here ([docs: routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)). `VACUUM` reclaims dead tuples, updates the VM/FSM, refreshes statistics (with `ANALYZE`), and — critically — **freezes** old rows to prevent transaction-ID wraparound.

### What VACUUM actually does

```sql
VACUUM (VERBOSE, ANALYZE) orders;   -- reclaim dead space + refresh stats (non-blocking)
VACUUM FREEZE orders;               -- aggressively freeze old tuples
VACUUM FULL orders;                 -- rewrite the whole table compactly — ACCESS EXCLUSIVE lock, AVOID
```

`VACUUM` does **not** return disk to the OS (it marks space reusable inside the table). Only `VACUUM FULL` or `pg_repack` shrink the file. Use **`pg_repack`** in production — it rebuilds the table without the long exclusive lock:

```bash
pg_repack -d app -t orders   # online rebuild, brief lock only at swap
```

### Tuning autovacuum

Autovacuum is gated by *scale factors* — fractions of the table that must change before it triggers. The defaults (20% for vacuum) are far too lazy for large hot tables: a 100 M-row table waits for 20 M dead rows before vacuuming. Override per-table:

```sql
ALTER TABLE events SET (
  autovacuum_vacuum_scale_factor = 0.02,    -- vacuum at 2% dead, not 20%
  autovacuum_analyze_scale_factor = 0.01,
  autovacuum_vacuum_cost_limit = 2000,      -- let it work faster (default 200 is throttled)
  autovacuum_vacuum_insert_scale_factor = 0.05  -- PG13+: vacuum insert-only tables too
);
```

The cost-limit/cost-delay system deliberately throttles autovacuum to spare I/O. On modern SSDs that throttle is usually the *problem*, not the protection — raise `autovacuum_vacuum_cost_limit` (or globally `vacuum_cost_limit`) so vacuum keeps up with churn.

### Transaction-ID wraparound — the emergency that takes down databases

Transaction IDs are 32-bit and **wrap around at ~4 billion**. Postgres keeps the past visible by *freezing* tuples older than `vacuum_freeze_min_age`, marking them "always visible." If autovacuum can't freeze fast enough — usually because a **long-running transaction** or an **abandoned replication slot** holds back the horizon — the database approaches wraparound and will **shut down to protect data** before it corrupts.

```sql
-- Watch the oldest unfrozen XID age per database. 200M = autovacuum_freeze_max_age default kicks in.
SELECT datname, age(datfrozenxid) AS xid_age
FROM pg_database ORDER BY xid_age DESC;

-- Find what's holding back the horizon:
SELECT pid, state, age(backend_xmin) AS xmin_age, query
FROM pg_stat_activity WHERE backend_xmin IS NOT NULL ORDER BY xmin_age DESC;

SELECT slot_name, age(xmin) FROM pg_replication_slots ORDER BY 2 DESC;
```

If `xid_age` heads toward ~2 billion: kill the long transactions, drop dead replication slots, and let aggressive autovacuum freeze catch up. **The three usual culprits are idle-in-transaction connections, a leaked replication slot, and autovacuum throttled too hard.**

### Practice

- Create a churning table, watch `n_dead_tup` climb, and tune scale factors so autovacuum keeps it near zero.
- Open a transaction with `BEGIN; SELECT 1;` and leave it; watch `backend_xmin` age freeze on another session's table.
- Simulate wraparound pressure by setting a tiny `autovacuum_freeze_max_age` on a test instance.

---

## 4. The Query Planner & Statistics

Postgres is a **cost-based** optimizer ([docs: planner statistics](https://www.postgresql.org/docs/current/planner-stats.html)): for each query it enumerates plans, estimates each plan's cost from table statistics, and picks the cheapest. When it chooses badly, the cause is almost always **bad row estimates**, not a "dumb planner."

### Where estimates come from

`ANALYZE` samples each table and stores per-column stats in `pg_statistic` (readable via `pg_stats`): the fraction of nulls, the most-common values (MCVs) and their frequencies, and a histogram of the rest. The planner combines these to guess how many rows a predicate returns — the **selectivity**.

```sql
SELECT attname, n_distinct, most_common_vals, histogram_bounds
FROM pg_stats WHERE tablename = 'orders' AND attname = 'status';
```

### The cost constants

Costs are in arbitrary units anchored to `seq_page_cost = 1.0`. The one you will almost always change:

```sql
-- Default random_page_cost = 4.0 assumes spinning disks. On SSD/NVMe, set it near seq cost
-- so the planner stops over-penalizing index scans:
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_cache_size = '24GB';  -- tell the planner how much OS cache exists (planner hint only)
```

`effective_cache_size` doesn't allocate anything — it tells the planner how likely an index page is to be cached, which tips it toward index plans on large tables.

### Correlated columns — the classic misestimate

The planner assumes columns are independent. When they aren't (`city` and `postal_code`, `status` and `shipped_at`), it multiplies selectivities and badly undercounts, producing nested-loop plans that explode. Fix with **extended statistics**:

```sql
CREATE STATISTICS orders_corr (dependencies, ndistinct, mcv)
  ON customer_id, status FROM orders;
ANALYZE orders;
```

For a single skewed/important column, raise its resolution:

```sql
ALTER TABLE orders ALTER COLUMN created_at SET STATISTICS 1000;  -- more histogram buckets (default 100)
ANALYZE orders;
```

### Join planning

Postgres picks both the **join algorithm** (§5) and the **join order**. With many tables the search space explodes, so above `geqo_threshold` (default 12) it switches to a genetic optimizer. `join_collapse_limit` / `from_collapse_limit` (default 8) bound how much it reorders; raising them can find better plans for big star-schema joins at the cost of planning time.

### Practice

- Find a query where `EXPLAIN ANALYZE` shows estimated rows off from actual by >10×; fix it with `ANALYZE` or extended statistics and re-check.
- Flip `random_page_cost` between 4.0 and 1.1 on a large indexed table and watch the plan switch between seq and index scan.

---

## 5. Reading EXPLAIN Like a Pro

[`EXPLAIN`](https://www.postgresql.org/docs/current/using-explain.html) is the single most important Postgres skill. `EXPLAIN` shows the plan + estimates; **`EXPLAIN ANALYZE` actually runs it** and shows real timings and row counts.

```sql
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, VERBOSE)
SELECT c.name, count(*)
FROM customers c JOIN orders o USING (customer_id)
WHERE o.created_at > now() - interval '30 days'
GROUP BY c.name;
```

Always add **`BUFFERS`** — it shows shared (cached) vs read (from disk) blocks, which tells you whether you're CPU- or I/O-bound.

### How to read a plan

Read **inside-out, bottom-up**. Each node shows `cost=startup..total rows=estimate width=bytes` and, with ANALYZE, `actual time=... rows=... loops=...`. The two numbers to compare obsessively: **estimated vs actual rows**. A large gap is the root cause of most bad plans.

### Scan nodes

| Node | When it's right | When it's a smell |
|---|---|---|
| **Seq Scan** | Reading most of a table | On a big table with a selective `WHERE` → missing/unused index |
| **Index Scan** | Selective predicate | — |
| **Index Only Scan** | Query covered by the index + fresh VM | Reverts to heap fetches if VACUUM is stale (`Heap Fetches:` high) |
| **Bitmap Heap Scan** | Medium selectivity; combines indexes | — |

### Join strategies

| Join | How it works | Best when |
|---|---|---|
| **Nested Loop** | For each outer row, probe inner | Outer side tiny, inner indexed |
| **Hash Join** | Build hash of one side, probe with other | Large unsorted sets, equality join |
| **Merge Join** | Sort both, merge | Both inputs already sorted / huge |

A **Nested Loop over a large inner set** is the canonical "planner thought there'd be 3 rows, there were 30,000" disaster — fix the estimate (§4), don't just disable nestloop.

### Red flags and their fixes

- **`Rows Removed by Filter:` huge** → the index isn't selective enough; add a partial or better composite index.
- **Sort spilling: `Sort Method: external merge Disk: …`** → raise `work_mem`.
- **`Heap Fetches:` high on an Index Only Scan** → VACUUM the table to refresh the visibility map.
- **Hash Join `Batches: >1`** → hash didn't fit in `work_mem`; raise it (or `hash_mem_multiplier`).
- **`Buffers: read=` large, `hit=` small** → cold cache / I/O-bound; the data isn't resident.

### Diagnostic-only plan forcing

```sql
SET enable_seqscan = off;   -- session only — a DIAGNOSTIC to see the alternative cost, never a prod fix
EXPLAIN ANALYZE SELECT ...;
RESET enable_seqscan;
```

### auto_explain — capture slow plans in production

```conf
shared_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = '500ms'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
```

### Practice

- Take a slow query and iterate: read the plan, find the biggest est-vs-actual gap or the most expensive node, fix it, re-run. Repeat until the plan is clean.
- Paste a JSON plan (`FORMAT JSON`) into `explain.dalibo.com` and read the visual tree.

---

## 6. Index Internals & Strategy

Indexes ([docs: index types](https://www.postgresql.org/docs/current/indexes-types.html)) are the highest-leverage performance tool and the most over- and under-applied. Pick the *type* by the query shape.

### B-tree (the default, and ~90% of what you need)

A balanced tree of sorted keys; serves equality, ranges, sorting, and `LIKE 'prefix%'`. Default FILLFACTOR 90 (leaves slack for in-page inserts).

**Composite column order is the #1 mistake.** Put equality columns first, then the range/sort column. An index on `(customer_id, created_at)` serves `WHERE customer_id = ? ORDER BY created_at` perfectly; `(created_at, customer_id)` does not.

```sql
CREATE INDEX ON orders (customer_id, created_at DESC);   -- equality then range/sort
```

### Index-only scans & covering indexes

If every column the query needs is in the index, Postgres skips the heap entirely (given a fresh VM). `INCLUDE` adds payload columns to leaf pages without making them part of the key:

```sql
CREATE INDEX ON orders (customer_id) INCLUDE (total, status);
-- SELECT total, status FROM orders WHERE customer_id = 42  →  Index Only Scan
```

### Partial & expression indexes — smaller, sharper

```sql
-- Index only the hot subset: tiny index, ignores 99% soft-deleted rows
CREATE INDEX ON users (email) WHERE deleted_at IS NULL;
-- Index a computed value so the matching query can use it
CREATE INDEX ON users (lower(email));   -- WHERE lower(email) = ...
```

### The specialized types — when B-tree won't do

| Type | Use for | Example |
|---|---|---|
| **GIN** | Multi-value columns: `jsonb`, arrays, full-text | `USING GIN (data jsonb_path_ops)` |
| **GiST** | Ranges, geometry, fuzzy (`pg_trgm`), nearest-neighbor | `USING GIST (during)` exclusion |
| **BRIN** | Huge tables physically ordered by the column (time-series) | `USING BRIN (created_at)` — tiny index |
| **SP-GiST** | Non-balanced data: IP prefixes, phone numbers | `USING SPGIST (ip inet_ops)` |
| **Hash** | Equality-only on wide keys | `USING HASH (token)` |
| **HNSW/IVFFlat** | Vector similarity (pgvector) | `USING hnsw (embedding vector_cosine_ops)` |

**BRIN is the secret weapon for append-only time-series**: a BRIN index on a billion-row events table can be a few hundred KB (vs. tens of GB for B-tree) because it only stores min/max per block range — and it works precisely *because* the table is physically ordered by time.

### Building and maintaining indexes safely

```sql
CREATE INDEX CONCURRENTLY ON big_table (col);   -- no write lock; 2 passes, slower wall-clock
REINDEX INDEX CONCURRENTLY some_idx;            -- rebuild a bloated index online (PG12+)
```

`CONCURRENTLY` can't run in a transaction block and leaves an `INVALID` index if it fails — drop and retry. Indexes bloat too; a B-tree on a churning table eventually needs a concurrent reindex.

### Finding waste

```sql
-- Unused indexes (idx_scan = 0) are pure write-amplification + bloat; drop them
SELECT relname, indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes WHERE idx_scan = 0 ORDER BY pg_relation_size(indexrelid) DESC;
```

### Practice

- Build `(a, b)` and `(b, a)` on the same table and prove which serves `WHERE a=? ORDER BY b`.
- Replace a B-tree on a time column of a large append-only table with BRIN; compare index sizes and plan.
- Audit a real database for unused indexes and estimate the write savings of dropping them.

---

## 7. Locking & Concurrency at Scale

MVCC means reads don't lock, but writes and DDL do. Understanding the lock hierarchy ([docs: explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html)) keeps you out of production incidents.

### Row locks

```sql
SELECT * FROM orders WHERE id = 42 FOR UPDATE;          -- strong: blocks other writers
SELECT ... FOR UPDATE SKIP LOCKED;                       -- skip locked rows — the queue-worker pattern
SELECT ... FOR UPDATE NOWAIT;                            -- fail instead of waiting
SELECT ... FOR NO KEY UPDATE / FOR SHARE / FOR KEY SHARE; -- progressively weaker
```

### Table locks and the DDL trap

Every statement takes a table lock; the danger is the strong ones. `ALTER TABLE`, `VACUUM FULL`, and a non-concurrent `CREATE INDEX` take **ACCESS EXCLUSIVE**, which blocks *everything* — and worse, it **queues behind running queries and then blocks every new query behind it**. A migration that waits 30 s for a slow `SELECT` can stall the whole application.

Always bound migration locks:

```sql
SET lock_timeout = '2s';                 -- give up rather than pile up a queue
ALTER TABLE orders ADD COLUMN note text; -- fast (metadata-only since PG11 for constant defaults)
```

### Deadlocks

Two transactions lock the same rows in opposite order. Postgres detects the cycle and kills one (`deadlock_timeout`, default 1 s). The fix is **always lock in a consistent order** (e.g., sort IDs before locking).

### Inspecting blocking

```sql
SELECT blocked.pid AS blocked, blocked.query AS blocked_q,
       blocker.pid AS blocker, blocker.query AS blocker_q
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocker
  ON blocker.pid = ANY(pg_blocking_pids(blocked.pid));
```

### Serializable Snapshot Isolation (SSI)

`SERIALIZABLE` gives you true serializability by tracking read/write dependencies and aborting transactions that would create an anomaly with `40001`. The contract: **you must retry `40001` (and `40P01` deadlock) errors.** Write your data layer to catch those SQLSTATEs and replay the whole transaction — never patch around them.

### Advisory locks

Application-defined locks Postgres doesn't interpret — perfect for "only one worker runs this job":

```sql
SELECT pg_try_advisory_lock(hashtext('nightly-rollup'));  -- false if someone else holds it
```

### Practice

- Build a queue table and drain it from 10 workers using `FOR UPDATE SKIP LOCKED`; prove no row is processed twice.
- Reproduce a deadlock with two psql sessions, read the server log's deadlock report.
- Write a retry wrapper for `40001` and test it under `SERIALIZABLE`.

---

## 8. Connections & Pooling

Postgres forks **one OS process per connection**, each consuming memory and a snapshot slot. This is why "just raise `max_connections`" backfires: thousands of mostly-idle backends thrash the scheduler and inflate snapshot costs. The standard fix is [PgBouncer](https://www.pgbouncer.org/).

### The math

Active connections should roughly track your core count for CPU-bound work; the rest is concurrency you *queue*, not *run*. A common starting point: `max_connections` modest (100–300) at the server, and a **pooler** in front for everything else.

### PgBouncer pooling modes

| Mode | A client connection holds a server connection… | Trade-off |
|---|---|---|
| **session** | for the whole client session | Safe, but barely better than no pool |
| **transaction** | only during a transaction | **The default choice** — huge fan-in |
| **statement** | per statement | Most aggressive; forbids multi-statement txns |

**Transaction pooling** lets 5,000 app connections share 50 server connections — but it breaks anything that relies on session state across transactions: session-level `SET`, session advisory locks, `LISTEN/NOTIFY`, and server-side prepared statements (unless you configure `max_prepared_statements` / use protocol-level prepares). Know this before you turn it on.

```ini
# pgbouncer.ini
[databases]
app = host=127.0.0.1 dbname=app
[pgbouncer]
pool_mode = transaction
max_client_conn = 5000
default_pool_size = 50
```

### Built-in alternative

PG-native connection pooling is improving, but PgBouncer (or pgcat) remains the standard. Many managed providers bundle one — know which mode they default to.

### Practice

- Run `pgbench` with 500 clients directly vs. through PgBouncer transaction pooling at `default_pool_size=50`; compare TPS and latency.
- Break something on purpose: hold a session advisory lock across transactions under transaction pooling and watch it misbehave.

---

## 9. The Performance Tuning Ladder

Climb in order — each rung assumes the ones below are done. The biggest wins are almost always **the right index** and **fixing a bad row estimate**, not config.

1. **Schema & query** — right data types, no `SELECT *`, keyset not OFFSET pagination, batch writes.
2. **Indexes** — the right type and composite order (§6).
3. **Statistics** — `ANALYZE`, extended stats for correlated columns (§4).
4. **Memory** — the four settings below.
5. **Planner constants** — `random_page_cost`, `effective_cache_size` for your storage (§4).
6. **Parallelism** — let big scans use multiple workers.
7. **Vacuum/checkpoint** — keep bloat and FPW storms in check (§2–§3).
8. **Connection pooling** — stop drowning in backends (§8).
9. **Replication / read replicas** — scale reads out (§11).
10. **Extensions / partitioning / hardware** — pg_partman, BRIN, faster disks.

### The memory four

```conf
shared_buffers = 8GB             # ~25% of RAM. Postgres's own page cache.
effective_cache_size = 24GB      # ~50-75% of RAM. Planner hint, allocates nothing.
work_mem = 32MB                  # PER sort/hash NODE, PER connection. The dangerous one.
maintenance_work_mem = 2GB       # index builds, VACUUM
```

**`work_mem` is per-node, not per-query, not per-server.** A query with 3 sorts across 100 connections can use `300 × work_mem`. Set it modestly globally and raise it locally for known reporting queries:

```sql
SET LOCAL work_mem = '256MB';   -- inside the transaction running the big analytical query only
```

### Parallel query

```conf
max_parallel_workers_per_gather = 4   # default 2; a big seq scan/aggregate can use N workers
max_parallel_workers = 8
```

### Practice

- Take a reporting query that spills to disk (`external merge` in EXPLAIN), raise `work_mem` locally until it's in-memory, and measure the speedup.
- Set `random_page_cost` correctly for your disk and re-plan your slowest query.

---

## 10. Partitioning at Scale

[Declarative partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html) (PG10+) splits one logical table into physical partitions. It's not a speed-up by itself — it's a tool for **manageability** (drop old data instantly) and **pruning** (skip irrelevant partitions).

### When it actually helps

- The table is large *and* most queries filter on the partition key (usually time).
- You age data out: dropping a partition is instant; `DELETE`-ing millions of rows is not.
- Bulk-load/detach workflows: build a partition offline, `ATTACH` it in one fast metadata op.

### Pruning, partition-wise joins/aggregates

```sql
-- Pruning: the planner skips partitions that can't match (planning AND execution time)
EXPLAIN SELECT count(*) FROM events WHERE created_at >= date '2026-05-01';

-- Let joins/aggregates run partition-by-partition (often a big win):
SET enable_partitionwise_join = on;
SET enable_partitionwise_aggregate = on;
```

### Operating it

```sql
-- Online detach (PG14+) doesn't block readers
ALTER TABLE events DETACH PARTITION events_2026_01 CONCURRENTLY;
```

Automate creation/retention with **pg_partman** + **pg_cron** rather than hand-rolling monthly DDL. Combine time-range partitioning with a **BRIN** index on the time column for a tiny, fast time-series store.

### Pitfalls

- The partition key must be part of every unique constraint/PK — you can't enforce global uniqueness on a non-key column.
- Too many partitions (thousands) inflate planning time; keep counts reasonable.
- Cross-partition queries that *don't* filter on the key scan everything — partitioning then only hurts.

### Practice

- Convert a large append-only table to monthly range partitions; prove pruning with EXPLAIN.
- Set up pg_partman to pre-create next month's partition and drop partitions older than 12 months.

---

## 11. Replication & High Availability

All replication is WAL shipping ([docs: high availability](https://www.postgresql.org/docs/current/high-availability.html)); the question is *how* the WAL is applied.

### Physical (streaming) replication

A byte-for-byte standby replays the primary's WAL stream. Standbys can serve **read-only** queries (read scaling) and become the new primary on failover. Use a **replication slot** so the primary retains WAL the standby still needs:

```sql
-- Primary
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET max_wal_senders = 10;
SELECT pg_create_physical_replication_slot('standby1');
CREATE ROLE repl WITH REPLICATION LOGIN PASSWORD '...';
```

```bash
# Standby: clone the primary and wire up streaming (-R writes standby.signal + primary_conninfo)
pg_basebackup -h primary -U repl -D /var/lib/pgsql/data -R -C -S standby1 -P
```

> Warning: a replication slot for a standby that goes away **pins WAL forever** — `pg_wal/` fills the disk and the primary stops. Monitor and drop orphaned slots. This is also a top cause of wraparound (§3).

### Sync vs async

```conf
# Make a named standby synchronous: commits wait for it to confirm
synchronous_standby_names = 'ANY 1 (standby1, standby2)'
synchronous_commit = remote_apply   # strongest: standby has REPLAYED it before COMMIT returns
```

Async (default) is fast but can lose the last few transactions on primary failure (non-zero RPO). Sync gives RPO=0 at the cost of commit latency tied to the standby. `remote_apply` even guarantees a read on the standby sees the just-committed write.

### Logical replication

Publish/subscribe per-table; decodes WAL into row changes. Works across major versions and selectively — making it the tool for **near-zero-downtime major upgrades** and selective/heterogeneous replicas:

```sql
-- Primary (wal_level = logical)
CREATE PUBLICATION pub_orders FOR TABLE orders, line_items;
-- Subscriber
CREATE SUBSCRIPTION sub_orders
  CONNECTION 'host=primary dbname=app user=repl password=...'
  PUBLICATION pub_orders;
```

Caveats: DDL is **not** replicated (apply schema changes yourself), and large transactions can lag. 

### Automatic failover

Core Postgres ships the *parts*, not an orchestrator. For automated promotion you run **Patroni** (+ etcd/Consul) or a managed service. The job: detect primary failure, promote a standby, and repoint clients (via a VIP, HAProxy, or service discovery) — fast enough to meet your RTO, without split-brain.

### Practice

- Stand up one primary + one streaming standby with a slot; run read queries on the standby and watch replay lag (`pg_stat_replication`).
- Flip a standby to `remote_apply` sync and measure the commit-latency cost.
- Do a logical-replication "upgrade": replicate from a 16 to a 17 instance and cut over.

---

## 12. Backup, PITR & Disaster Recovery

Two fundamentally different things, often confused:

- **Logical backup** (`pg_dump`/`pg_dumpall`): a portable, version-independent SQL/archive snapshot. Great for single databases, migrations, and selective restore. Slow to restore at scale; not point-in-time.
- **Physical backup + WAL archiving**: a base copy of the cluster plus the continuous WAL stream, enabling **Point-In-Time Recovery** to any moment.

### pg_dump

```bash
pg_dump -Fc -d app -f app.dump          # custom format (compressed, parallel-restorable)
pg_restore -d app_restored -j 8 app.dump # parallel restore
```

### Continuous archiving + PITR

```conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /archive/%f && cp %p /archive/%f'   # ship each WAL segment
```

```bash
pg_basebackup -D /backups/base-$(date +%F) -Ft -z -P   # the base backup
```

Restore = base backup + replay WAL up to a target:

```conf
restore_command = 'cp /archive/%f %p'
recovery_target_time = '2026-04-22 11:45:00-07'   # "the moment before the bad DELETE"
```

In production, don't hand-roll this — use **pgBackRest** or **Barman**: they do parallel, compressed, incremental backups, manage retention, and verify restores. An untested backup is not a backup.

### RPO/RTO framing

- **RPO** (how much data you can lose) is set by your WAL-archiving cadence and sync-replication choice.
- **RTO** (how long to recover) is set by base-backup size + WAL replay speed + failover automation.

### Practice

- Take a base backup, archive WAL, intentionally `DROP TABLE`, then PITR to one second before the drop.
- Configure pgBackRest with a weekly full + daily incremental and run a verified restore into a scratch instance.

---

## 13. Observability

You cannot tune what you cannot see ([docs: the cumulative statistics system](https://www.postgresql.org/docs/current/monitoring-stats.html)). Three extensions/views carry most of the weight.

### pg_stat_statements — your #1 tool

Aggregates normalized query stats. Find the queries that actually cost you (by *total* time, not per-call):

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- + shared_preload_libraries

SELECT query, calls, round(total_exec_time) AS total_ms,
       round(mean_exec_time, 2) AS mean_ms, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 20;
```

### pg_stat_activity — what's happening right now

```sql
SELECT pid, state, wait_event_type, wait_event,
       now() - query_start AS runtime, query
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY runtime DESC;
```

**Wait events** are the key column: `Lock` (blocked on a lock), `LWLock`/`BufferPin` (internal contention), `IO:DataFileRead` (disk-bound), `Client:ClientRead` (waiting on the app — often idle-in-transaction). On PG16+, **`pg_stat_io`** gives a per-backend-type read/write/extend breakdown that finally makes I/O attribution easy.

### Bloat & dead tuples

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
       last_autovacuum
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 20;
```

### Logging

```conf
log_min_duration_statement = '500ms'   # log every statement slower than this
log_lock_waits = on                    # log when a statement waits > deadlock_timeout for a lock
log_autovacuum_min_duration = 0        # see every autovacuum — invaluable for tuning
```

Pipe metrics into Prometheus (`postgres_exporter`) + Grafana, or use pgwatch2/pganalyze. The minimum viable setup: `pg_stat_statements` + `auto_explain` + `log_lock_waits` on every non-trivial database.

### Practice

- Turn on `pg_stat_statements`, run your app's load, and identify the top-3 queries by total time.
- Catch an idle-in-transaction connection via `wait_event = ClientRead` + long `runtime`.

---

## 14. Production Patterns & Pitfalls

The greatest hits — most production Postgres incidents are one of these.

- **Idle-in-transaction connections.** A connection that `BEGIN`s and sits holds back the xmin horizon, blocking vacuum and risking wraparound, and may hold locks. Set `idle_in_transaction_session_timeout = '60s'`.
- **Unindexed foreign keys.** Postgres does **not** auto-index the referencing side of an FK. Without it, deleting/updating a parent row does a seq scan of the child and takes strong locks. Index every FK column.
- **`OFFSET` pagination.** `OFFSET 100000 LIMIT 20` reads and discards 100,000 rows every time. Use **keyset pagination**: `WHERE id > :last ORDER BY id LIMIT 20`.
- **`SELECT *`** forces detoasting of big columns and breaks index-only scans. Select what you need.
- **`count(*)` is not free.** Postgres has no stored row count (MVCC — the count is per-snapshot). For exact counts it scans; for an estimate use `pg_class.reltuples` or a maintained counter.
- **Schema migrations that lock.** `ALTER TABLE` takes ACCESS EXCLUSIVE and queues behind/ahead of traffic. Use `lock_timeout`, `ADD COLUMN` with constant defaults (fast since PG11), `NOT VALID` + `VALIDATE` for constraints, and `CREATE INDEX CONCURRENTLY`.
- **Adding an enum value in a migration** historically caused issues mid-transaction; prefer a lookup table or `CHECK` constraint when values change often.
- **Too many connections.** Each is a process; thousands thrash. Pool (§8).
- **N+1 queries.** The app, not Postgres — but it shows up as thousands of identical fast queries in `pg_stat_statements`. Batch with `IN`, `= ANY($1)`, or a join.
- **Trusting a CTE as a fence.** Since PG12 plain CTEs are inlined; if you relied on the old fence behavior, mark it `MATERIALIZED`.
- **Long-running analytics on the primary** holding back vacuum — run them on a read replica or `SET TRANSACTION SNAPSHOT` carefully.

---

## 15. Benchmarking

Measure, don't guess. **[`pgbench`](https://www.postgresql.org/docs/current/pgbench.html)** ships with Postgres.

```bash
pgbench -i -s 100 app          # initialize, scale factor 100 (~10M rows)
pgbench -c 32 -j 4 -T 60 app   # 32 clients, 4 threads, 60s — reports TPS + latency
pgbench -c 32 -j 4 -T 60 -f custom.sql app   # your own workload
```

```sql
-- custom.sql — model your real access pattern, not the default TPC-B-ish one
\set id random(1, 100000)
SELECT * FROM orders WHERE customer_id = :id ORDER BY created_at DESC LIMIT 20;
```

Methodology that matters: warm the cache first, run long enough to cross a checkpoint, change **one variable at a time**, and compare medians across repeated runs. Benchmark on hardware that resembles production — `work_mem` and `random_page_cost` conclusions don't transfer from a laptop to NVMe servers.

### Practice

- Benchmark `synchronous_commit` on vs off, and direct vs pooled connections, on the same workload.
- Write a custom script matching your hottest endpoint and use it to validate an index change end-to-end.

---

## 16. Worked Performance Recipes

### Recipe 1 — Turn a Seq Scan into an Index Only Scan

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT status, total FROM orders WHERE customer_id = 42;
--> Seq Scan ... Rows Removed by Filter: 4_000_000
CREATE INDEX ON orders (customer_id) INCLUDE (status, total);
VACUUM orders;   -- refresh the visibility map so it's an Index ONLY scan
-- re-run → Index Only Scan, Heap Fetches: 0
```

### Recipe 2 — Kill table bloat without downtime

```sql
SELECT relname, n_dead_tup FROM pg_stat_user_tables WHERE relname='events';
-- VACUUM FULL would lock; use pg_repack instead:
```
```bash
pg_repack -d app -t events   # rebuilds online, brief lock only at the swap
```

### Recipe 3 — A reliable job queue

```sql
CREATE TABLE jobs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  state text NOT NULL DEFAULT 'queued',
  run_after timestamptz NOT NULL DEFAULT now(),
  payload jsonb
);
CREATE INDEX ON jobs (run_after) WHERE state = 'queued';   -- partial index = tiny + hot

-- Each worker claims one job atomically, never colliding:
WITH next AS (
  SELECT id FROM jobs
  WHERE state = 'queued' AND run_after <= now()
  ORDER BY run_after
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE jobs j SET state = 'running'
FROM next WHERE j.id = next.id
RETURNING j.*;
```

### Recipe 4 — Keyset pagination (constant time at any depth)

```sql
-- Page 1
SELECT * FROM orders ORDER BY created_at DESC, id DESC LIMIT 20;
-- Page N: pass the last row's (created_at, id) back as the cursor
SELECT * FROM orders
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC LIMIT 20;
```

### Recipe 5 — Fast bulk load

```sql
BEGIN;
SET LOCAL synchronous_commit = off;
SET LOCAL maintenance_work_mem = '2GB';
CREATE UNLOGGED TABLE staging (LIKE orders INCLUDING DEFAULTS);
\copy staging FROM 'orders.csv' CSV HEADER
-- drop/disable indexes on target first, then:
INSERT INTO orders SELECT * FROM staging;
COMMIT;
-- recreate indexes CONCURRENTLY, then ANALYZE orders;
```

### Recipe 6 — Tame autovacuum on a hot table

```sql
ALTER TABLE sessions SET (
  fillfactor = 85,                          -- enable HOT updates
  autovacuum_vacuum_scale_factor = 0.01,    -- vacuum aggressively
  autovacuum_vacuum_cost_limit = 4000
);
-- verify: hot_pct high, n_dead_tup low, last_autovacuum recent
```

### Recipe 7 — Safe online schema migration

```sql
SET lock_timeout = '3s';                                          -- never queue behind traffic
ALTER TABLE orders ADD COLUMN region text;                        -- fast metadata-only
ALTER TABLE orders ADD CONSTRAINT orders_region_chk
  CHECK (region IS NOT NULL) NOT VALID;                           -- don't scan now
ALTER TABLE orders VALIDATE CONSTRAINT orders_region_chk;         -- scan without blocking writes
CREATE INDEX CONCURRENTLY ON orders (region);                     -- no write lock
```

---

## 17. Decision Trees

### Which index?

```
Equality/range/sort on a scalar?              → B-tree (default)
Only need columns in the index?               → add INCLUDE (covering) → Index Only Scan
Querying a hot subset only?                   → Partial index (WHERE ...)
Querying a computed value?                    → Expression index
jsonb / array / full-text?                    → GIN (jsonb_path_ops if only @>)
Range overlap / geometry / fuzzy (pg_trgm)?   → GiST
Huge append-only table ordered by the column? → BRIN (tiny, time-series)
Vector similarity (embeddings)?               → HNSW (pgvector)
```

### Which isolation level?

```
Default app traffic?                          → Read Committed
Multi-statement consistent read (reports)?    → Repeatable Read
Money/inventory invariants across rows?       → Serializable (and RETRY 40001)
```

### Partition or not?

```
Table large AND queries filter on a time/key column AND you age data out? → Partition (range, + BRIN, + pg_partman)
Otherwise                                                                 → One table + good indexes
```

### Pooling mode?

```
Need session state (LISTEN/NOTIFY, session SET, advisory session locks)? → session pooling
Plain request/response web app?                                          → transaction pooling (default win)
```

### Scaling reads?

```
Read-heavy, can tolerate ms of lag?           → async streaming read replica(s)
Must read-your-writes on the replica?         → synchronous_commit = remote_apply
Different major version / selective tables?   → logical replication
```

---

## Where to Go Next

- **Read Egor Rogov's [*PostgreSQL Internals*](https://postgrespro.com/community/books/internals)** (free PDF) — the definitive book-length treatment of MVCC, vacuum, locking, and the planner; it is this guide's Parts 1–7 at full depth, by someone who reads the source for a living.
- **Read the [official docs'](https://www.postgresql.org/docs/current/) internals chapters** — [MVCC](https://www.postgresql.org/docs/current/mvcc.html), [WAL configuration](https://www.postgresql.org/docs/current/wal-configuration.html), [routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html), and [planner statistics](https://www.postgresql.org/docs/current/planner-stats.html) — they are excellent and most users never open them.
- **Practice plans on [explain.dalibo.com](https://explain.dalibo.com/)** — paste any `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` output and learn to read the visual tree; then enable [auto_explain](https://www.postgresql.org/docs/current/auto-explain.html) in a real environment.
- **Learn the operator's toolkit from its own docs:** [pgBackRest](https://pgbackrest.org/) (backups/PITR), [Patroni](https://patroni.readthedocs.io/) (HA), [pg_partman](https://github.com/pgpartman/pg_partman) (partition management), [pg_repack](https://reorg.github.io/pg_repack/) (bloat removal without long locks).
- **Run one incident drill:** fill a table with dead tuples, watch autovacuum respond (or fail to), tune the per-table thresholds, and verify with `pg_stat_user_tables`. Then practice a PITR restore. These two drills cover the failure modes that actually page people.
- **Companions in this repo:** the [PostgreSQL Feature Reference](POSTGRES.md) (the SQL surface), [PostgreSQL Extensions](POSTGRES_EXTENSIONS.md) (the ecosystem), [Database Internals](DATABASE_INTERNALS_STUDY_GUIDE.md) (the cross-engine theory), and [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) (replication consistency).

# PostgreSQL Extensions in Production

PostgreSQL's extension system is its single biggest strategic advantage over other databases: the same engine becomes a geospatial database (PostGIS), a time-series store (TimescaleDB), a vector database (pgvector), a sharded distributed system (Citus), or a job scheduler (pg_cron) — without leaving SQL or running a second system. The catalog is enormous and uneven, so the useful question is **not "what's cool"** but **"is it maintained, is it available on my platform, and does it pay rent for the operational cost it adds?"**

This guide is the third member of a set: the [PostgreSQL Feature Reference](POSTGRES.md) (the SQL surface area) and the [Advanced PostgreSQL Study Guide](ADVANCED_POSTGRES.md) (the engine, performance, and ops). Here we focus on **which extensions are worth running in production**, with a verdict and managed-service availability for each.

Extension availability, version support, and managed-platform allow-lists change frequently. Treat every availability note here as **directional** — confirm against your provider's current supported-extensions list before you commit.

---

## Table of Contents

1. [How Extensions Actually Work](#1-how-extensions-actually-work)
2. [The Production Lens (verdict tiers + how to adopt safely)](#2-the-production-lens)
3. [The Day-One Shortlist](#3-the-day-one-shortlist)
4. [Observability & Operations](#4-observability--operations)
5. [Indexing, Search & Data Types](#5-indexing-search--data-types)
6. [Geospatial: PostGIS](#6-geospatial-postgis)
7. [Time-Series: TimescaleDB & friends](#7-time-series-timescaledb--friends)
8. [Vectors & AI: pgvector & the ecosystem](#8-vectors--ai-pgvector--the-ecosystem)
9. [Security & Encryption](#9-security--encryption)
10. [Foreign Data Wrappers & Federation](#10-foreign-data-wrappers--federation)
11. [Scale-Out & Sharding: Citus](#11-scale-out--sharding-citus)
12. [Scheduling, Queues & Background Jobs](#12-scheduling-queues--background-jobs)
13. [Procedural Languages & Planner Tools](#13-procedural-languages--planner-tools)
14. [Replication & CDC](#14-replication--cdc)
15. [Managed-Service Availability Matrix](#15-managed-service-availability-matrix)
16. [Tier Summary & Decision Guide](#16-tier-summary--decision-guide)

---

## 1. How Extensions Actually Work

The production-relevant mechanics — most adoption surprises come from one of these.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- install into the current database
CREATE EXTENSION postgis SCHEMA gis;             -- pin its objects to a schema
ALTER EXTENSION postgis UPDATE TO '3.4.2';       -- upgrade an installed extension
SELECT * FROM pg_available_extensions ORDER BY name;  -- what CAN be installed here
\dx                                              -- what IS installed (in psql)
```

Four distinctions decide whether you can use an extension at all:

- **Contrib vs third-party.** "Contrib" modules ship with Postgres in the `postgresql-contrib` package and are maintained by the core project — `pg_stat_statements`, `pg_trgm`, `pgcrypto`, `postgres_fdw`, `citext`, `hstore`, `btree_gin`/`btree_gist`, `unaccent`, `fuzzystrmatch`, `tablefunc`, `pgstattuple`, `amcheck`, and more. These are the safest, most universally available extensions. Everything else (PostGIS, pgvector, TimescaleDB, Citus, pg_cron, pg_partman, pgaudit) is third-party and must be packaged for your platform.
- **Trusted vs untrusted.** Since PG13, *trusted* extensions can be installed by a non-superuser with `CREATE` on the database (most contrib data-type/index extensions are trusted). *Untrusted* ones — anything that touches the filesystem, loads C/shared libraries broadly, or provides an untrusted procedural language (`plpython3u`) — require superuser. On managed services you are **never** a real superuser, which is the root cause of "why can't I install X."
- **`shared_preload_libraries` (requires a restart).** Extensions that hook deep into the server — `pg_stat_statements`, `pgaudit`, `pg_cron`, `citus`, `timescaledb`, `auto_explain`, `pg_partman`'s background worker — must be listed in `shared_preload_libraries` and need a **server restart** to load. Plan that maintenance window; you can't add `pg_stat_statements` live.
- **Schema & `search_path`.** Extension objects land in a schema (default `public`). For security-sensitive ones, install into a dedicated schema and keep `search_path` tight (see the [Advanced guide](ADVANCED_POSTGRES.md#7-locking--concurrency-at-scale) on `SECURITY DEFINER`).

```ini
# postgresql.conf — these three need a restart to take effect
shared_preload_libraries = 'pg_stat_statements,pgaudit,pg_cron'
```

---

## 2. The Production Lens

Throughout, each extension gets a one-glance verdict:

| Badge | Meaning |
|---|---|
| ⭐ **Essential** | Run it on basically every production database |
| ✅ **Strong** | Production-proven; reach for it the moment you have the need |
| 🟡 **Situational** | Excellent for a specific job; weigh the operational cost |
| 🧪 **Specialist** | Powerful but narrow, or adds real operational surface |
| ⚠️ **Caution** | Maturity, security, or maintenance-burden concerns — adopt deliberately |

**How to adopt an extension safely** (the checklist, regardless of badge):

1. **Confirm platform support first.** If you're on RDS/Cloud SQL/Azure/Supabase, the supported-extensions list is the hard constraint — check it before designing around an extension.
2. **Check the pulse.** Recent releases, an active repo, a real maintainer or company behind it. A clever-but-abandoned extension is a future migration blocker.
3. **Mind the lock-in.** PostGIS data is portable; a TimescaleDB hypertable or a Citus distributed table changes your schema and your exit path. Know the off-ramp before you board.
4. **Test the upgrade path.** Extensions version independently of Postgres. Rehearse `ALTER EXTENSION ... UPDATE` and major-version moves in staging — some (PostGIS, TimescaleDB) have real upgrade choreography.
5. **Account for `shared_preload_libraries`.** If it needs one, you owe a restart and a place in the boot sequence.
6. **Watch the supply chain.** Untrusted languages and obscure C extensions run native code in your database process. Treat them like any dependency with RCE-level trust.

---

## 3. The Day-One Shortlist

If you do nothing else, install these on every non-trivial production database:

- ⭐ **`pg_stat_statements`** — you cannot tune what you can't measure. The single most valuable extension.
- ✅ **`auto_explain`** — automatically logs plans of slow queries, so you catch the regression that only happens in prod.
- ✅ **`pgaudit`** — if you have any compliance/audit requirement (SOC2, HIPAA, PCI), this is the answer.
- ✅ **`pg_repack`** — online bloat removal without the `VACUUM FULL` exclusive lock; you *will* need it.
- 🟡 **`pg_trgm`** — fuzzy search and fast `LIKE '%x%'`; almost every app wants it eventually.

All five are either contrib or supported on every major managed platform. The first three are the non-negotiables.

---

## 4. Observability & Operations

The category where extensions earn their keep daily.

**`pg_stat_statements`** — ⭐ Essential · *contrib*. Aggregates normalized execution stats per query: calls, total/mean time, rows, I/O. Find your real cost centers by *total* time, not gut feel. Needs `shared_preload_libraries` + restart. Available everywhere (RDS, Aurora, Cloud SQL, Azure, Supabase all ship it).

```sql
SELECT query, calls, round(total_exec_time) AS total_ms,
       round(mean_exec_time,2) AS mean_ms, rows
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;
```

**`auto_explain`** — ✅ Strong · *contrib*. Logs the actual plan of any statement over a threshold. The only practical way to capture the bad plan that fires at 3 a.m. under production data volumes.

```ini
auto_explain.log_min_duration = '500ms'
auto_explain.log_analyze = on        # real timings (small overhead — measure it)
auto_explain.log_buffers = on
```

**`pgaudit`** — ✅ Strong · *third-party, widely packaged*. Structured, fine-grained audit logging (per-role, per-object, per-statement-class) that plain `log_statement` can't produce. The standard answer for compliance. Supported on RDS/Aurora, Cloud SQL, Azure, Supabase. Cost: log volume — scope it, don't `AUDIT ALL`.

**`pg_repack`** — ✅ Strong · *third-party*. Rebuilds bloated tables and indexes online, taking only a brief lock at the swap — the production-safe alternative to `VACUUM FULL`. Supported on RDS/Aurora and most managed platforms (it's a client tool + extension). See the [bloat recipe](ADVANCED_POSTGRES.md#16-worked-performance-recipes).

```bash
pg_repack -d app -t orders        # rebuild one table online
```

**`hypopg`** — ✅ Strong · *third-party*. **Hypothetical indexes**: create a "virtual" index and ask the planner whether it *would* use it — without paying to build it on a huge table. Pairs beautifully with `EXPLAIN`. Low-risk, high-leverage; on Cloud SQL/Azure/Supabase and self-managed (not on RDS as of writing).

```sql
SELECT * FROM hypopg_create_index('CREATE INDEX ON orders (customer_id, created_at)');
EXPLAIN SELECT * FROM orders WHERE customer_id = 42 ORDER BY created_at DESC;  -- uses the hypo index?
```

**`amcheck`** — ✅ Strong · *contrib*. Verifies heap and B-tree integrity to catch corruption early (bad hardware, replication bugs). Run it in a maintenance job; cheap insurance.

**`pgstattuple` / `pg_buffercache` / `pg_prewarm`** — 🟡 Situational · *contrib*. Precise bloat measurement, a window into what's in shared buffers, and the ability to warm the cache after a restart (`autoprewarm`). Reach for them when diagnosing a specific I/O or bloat problem.

**`pg_wait_sampling` / `pg_stat_kcache`** — 🟡 Situational · *third-party*. Sampled wait-event history and per-query OS-level CPU/disk stats — the next level of `pg_stat_statements`. Common on self-managed and some managed stacks; great for deep performance work.

---

## 5. Indexing, Search & Data Types

Mostly contrib, mostly trusted, available nearly everywhere — low-risk wins.

**`pg_trgm`** — ✅ Strong · *contrib, trusted*. Trigram similarity: fuzzy matching, typo-tolerant search, and **GIN-indexed `LIKE '%substring%'`** (otherwise unindexable). The default reach for "search that doesn't need a search engine."

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX ON users USING GIN (name gin_trgm_ops);
SELECT name FROM users WHERE name % 'Alicia' ORDER BY similarity(name,'Alicia') DESC;
```

**`btree_gin` / `btree_gist`** — ✅ Strong · *contrib, trusted*. Let GIN/GiST index plain scalar types alongside their specialty types — the enabler for mixed indexes and **exclusion constraints** like "no overlapping bookings per room."

```sql
CREATE EXTENSION btree_gist;
ALTER TABLE bookings ADD EXCLUDE USING GIST (room_id WITH =, during WITH &&);
```

**`citext`** — 🟡 Situational · *contrib, trusted*. Case-insensitive text type. Convenient for emails/usernames, but a `CREATE UNIQUE INDEX ON users (lower(email))` is often the more portable, more explicit choice. Fine to use; just know the alternative.

**`unaccent`** — ✅ Strong · *contrib, trusted*. Strips accents for diacritic-insensitive search (`café` matches `cafe`). Combine with `pg_trgm` or full-text for international data.

**`hstore`** — ⚠️ Caution (legacy) · *contrib, trusted*. Flat key/value type that predates `jsonb`. For new work, **use `jsonb`** — it's richer and better-indexed. Keep `hstore` only for existing schemas.

**`ltree`** — 🟡 Situational · *contrib, trusted*. Materialized-path tree labels with operators and GiST indexing — clean for category trees and hierarchies when recursive CTEs feel heavy.

**`bloom`** — 🧪 Specialist · *contrib*. Bloom-filter index for tables queried by many different columns in unpredictable equality combinations. Niche but occasionally exactly right.

**`uuid-ossp`** — ⚠️ Caution (mostly obsolete) · *contrib*. Historically the UUID generator; modern Postgres has built-in `gen_random_uuid()` (v4), and **v18 adds native `uuidv7()`** (time-ordered, index-friendly). On 13–17 wanting UUIDv7, the **`pg_uuidv7`** extension fills the gap. Prefer built-ins; reach for `pg_uuidv7` only if you need time-ordered IDs before v18.

---

## 6. Geospatial: PostGIS

**PostGIS** — ✅ Strong (the gold standard) · *third-party*. The most mature, most respected Postgres extension, period — a full GIS engine: `geometry`/`geography` types, hundreds of spatial functions, GiST/SP-GiST spatial indexing, raster, and topology. If you do *anything* with maps, locations, or shapes, this is the answer and it is genuinely production-grade. Supported on every major managed platform.

```sql
CREATE EXTENSION postgis;
CREATE TABLE stores (id bigint PRIMARY KEY, geom geography(Point, 4326));
CREATE INDEX ON stores USING GIST (geom);

-- Everything within 5km of a point, nearest first
SELECT id, ST_Distance(geom, ST_MakePoint(-122.42, 37.77)::geography) AS m
FROM stores
WHERE ST_DWithin(geom, ST_MakePoint(-122.42, 37.77)::geography, 5000)
ORDER BY m;
```

Production notes: it's a large extension with its own **versioned upgrade path** (`SELECT postgis_extensions_upgrade();`) — rehearse upgrades. Use `geography` for lat/long-on-a-sphere correctness, `geometry` for planar speed. The companion extensions (`postgis_raster`, `postgis_topology`, `postgis_tiger_geocoder`) are opt-in.

---

## 7. Time-Series: TimescaleDB & friends

**TimescaleDB** — 🟡 Situational (powerful, but check availability) · *third-party*. Turns Postgres into a serious time-series database: **hypertables** (automatic time/space partitioning), columnar **compression** (often 90%+), **continuous aggregates** (incrementally-maintained rollups), and retention policies. Excellent engineering. Two production caveats that matter a lot:

- **Availability:** it is **not available on Amazon RDS or Aurora.** It's offered as managed **Timescale Cloud**, on Azure (historically), and self-managed. If you're committed to RDS, this choice is off the table — a frequent surprise.
- **Lock-in:** hypertables reshape your schema; migrating off is non-trivial. The open-source ("Apache 2") edition omits some features of the Community edition (which has a non-OSI license). Know which features you're using.

```sql
CREATE EXTENSION timescaledb;
SELECT create_hypertable('metrics', 'ts');
ALTER TABLE metrics SET (timescaledb.compress);
SELECT add_compression_policy('metrics', INTERVAL '7 days');
```

**The plain-Postgres alternative** — ✅ Strong. For many time-series workloads, native **declarative range partitioning by time + a BRIN index + `pg_partman` + `pg_cron`** gets you 80% of the value with zero lock-in and universal availability. Start here; graduate to TimescaleDB if you specifically need continuous aggregates or its compression. See [Partitioning at Scale](ADVANCED_POSTGRES.md#10-partitioning-at-scale).

---

## 8. Vectors & AI: pgvector & the ecosystem

**pgvector** — ✅ Strong (the default) · *third-party, now ubiquitous*. Adds a `vector` type and approximate-nearest-neighbor search (**HNSW** and IVFFlat indexes) for embeddings — the foundation of RAG and semantic search directly in your primary database. It has effectively won this space and is now supported on **RDS/Aurora, Cloud SQL, Azure, and Supabase**, which makes "just use Postgres as your vector store" a legitimate production answer for most teams (no separate vector DB to operate).

```sql
CREATE EXTENSION vector;
ALTER TABLE docs ADD COLUMN embedding vector(1536);
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops);
SELECT id FROM docs ORDER BY embedding <=> $1 LIMIT 10;   -- <=> cosine distance
```

Production notes: HNSW gives better recall/latency than IVFFlat but builds slower and uses more memory; tune `m`/`ef_construction` and query-time `hnsw.ef_search`. Index builds on large tables are heavy — use `maintenance_work_mem` generously and build off-peak.

**The growing ecosystem** — 🧪 Specialist:
- **`pgvectorscale`** (Timescale) — a disk-based StreamingDiskANN index and quantization on top of pgvector for very large vector sets; self-managed / Timescale Cloud.
- **`pg_search` / ParadeDB** — BM25 full-text search (Elasticsearch-style relevance) implemented as a Rust extension; reach for it when `pg_trgm`/native FTS isn't enough and you want to avoid running Elasticsearch.
- **VectorChord** — a newer high-performance vector option. Watch the space; pgvector remains the safe default.

---

## 9. Security & Encryption

**`pgcrypto`** — ✅ Strong · *contrib, trusted*. Hashing, HMAC, symmetric/asymmetric encryption, and `gen_random_bytes()`. The right tool for column-level encryption and secure tokens. Caveat: encrypting *inside* the database means keys and plaintext pass through it — for high-sensitivity data, prefer application-side encryption with an external KMS.

```sql
INSERT INTO secrets(name, val) VALUES ('api', pgp_sym_encrypt('s3cr3t', :key));
SELECT pgp_sym_decrypt(val, :key) FROM secrets WHERE name = 'api';
```

**`pgaudit`** — ✅ Strong (see [§4](#4-observability--operations)). The compliance workhorse; listed here too because audit logging is a security control, not just ops.

**`anon` (PostgreSQL Anonymizer)** — 🟡 Situational · *third-party*. Declarative dynamic masking and anonymization (fake names, partial masking, k-anonymity) — invaluable for giving developers realistic non-production data without leaking PII. Strong fit if you have privacy obligations and refresh lower environments from prod.

**`set_user`** — 🧪 Specialist · *third-party*. Lets you grant controlled privilege escalation with an audit trail instead of handing out superuser. Niche but useful for tightly-governed self-managed fleets.

**`sslinfo`** — 🟡 Situational · *contrib*. Exposes client-certificate details to SQL for cert-based access policies.

---

## 10. Foreign Data Wrappers & Federation

Query other systems as if they were local tables. The SQL/MED standard, implemented per-source.

**`postgres_fdw`** — ✅ Strong · *contrib*. Query another Postgres server; the planner pushes down filters, joins, and aggregates when it can. The standard tool for cross-database queries, gradual migrations, and read-federation. Available on managed platforms.

```sql
CREATE EXTENSION postgres_fdw;
CREATE SERVER remote FOREIGN DATA WRAPPER postgres_fdw OPTIONS (host 'db2', dbname 'sales');
CREATE USER MAPPING FOR CURRENT_USER SERVER remote OPTIONS (user 'reader', password '...');
IMPORT FOREIGN SCHEMA public LIMIT TO (orders) FROM SERVER remote INTO ext;
```

**`file_fdw`** — 🟡 Situational · *contrib*. Read CSV/text files (and program output) as tables — handy for log/ETL ingestion on self-managed servers.

**`oracle_fdw` / `mysql_fdw` / `tds_fdw`** — 🟡 Situational · *third-party*. Federate to Oracle, MySQL, and SQL Server respectively. Production-viable for migration and integration, but each adds driver dependencies; mostly self-managed.

**Supabase `wrappers`** — 🧪 Specialist · *third-party (Rust)*. A modern FDW framework with wrappers for Stripe, Firebase, ClickHouse, S3, and more. Compelling for "read SaaS data via SQL," but treat external-API-backed foreign tables as latency-and-rate-limit-bearing, not free local reads.

> FDW caution for all of these: a foreign table looks local but isn't. Always check `EXPLAIN` to confirm push-down; a join that pulls a whole remote table back before filtering can be catastrophically slow.

---

## 11. Scale-Out & Sharding: Citus

**Citus** — 🧪 Specialist (transformative, but a commitment) · *third-party*. Turns Postgres into a **distributed, horizontally-sharded** database: distribute tables across worker nodes by a shard key, run cross-shard queries and parallel analytics. The real answer when a single node genuinely can't hold the write/storage volume — multi-tenant SaaS and large analytics are the sweet spots.

```sql
CREATE EXTENSION citus;
SELECT create_distributed_table('events', 'tenant_id');   -- shard by tenant
```

Production reality check: Citus changes your data model (everything hinges on the **distribution column**), constrains cross-shard transactions and constraints, and is an operational system to run. Managed as **Azure Cosmos DB for PostgreSQL**; otherwise self-managed. Don't reach for it until partitioning, read replicas, and a bigger box are genuinely exhausted — most teams never need it.

---

## 12. Scheduling, Queues & Background Jobs

**`pg_cron`** — ✅ Strong · *third-party, now broadly supported*. Cron-style job scheduling **inside** the database — run vacuum/rollup/cleanup jobs without an external scheduler. Needs `shared_preload_libraries`. Supported on RDS/Aurora, Cloud SQL, Azure, and Supabase, which makes it a safe default for in-DB maintenance.

```sql
SELECT cron.schedule('purge-sessions', '0 3 * * *',
  $$DELETE FROM sessions WHERE expires_at < now()$$);
```

**`pg_partman`** — ✅ Strong · *third-party*. Automated partition lifecycle: pre-create future partitions, drop/retire old ones, optionally via a background worker. With `pg_cron` it's the standard way to operate time-partitioned tables. Widely supported.

**`pgmq`** — 🟡 Situational · *third-party (Tembo)*. A lightweight message queue (SQS-like semantics: visibility timeout, archiving) built on Postgres. Genuinely useful when you want "a queue" without standing up Kafka/SQS and your volume is modest. For exactly-once, high-throughput, or fan-out at scale, a real broker still wins — but for many apps a Postgres-backed queue (this, or a hand-rolled `FOR UPDATE SKIP LOCKED` table from the [queue recipe](ADVANCED_POSTGRES.md#16-worked-performance-recipes)) is the right amount of infrastructure.

---

## 13. Procedural Languages & Planner Tools

**`plpgsql`** — ⭐ Essential · *built-in*. Installed by default; the standard language for triggers and functions. Not optional — it's just there.

**`plpython3u` / `plperlu` / `plv8`** — ⚠️ Caution · *third-party / contrib*. Run Python, Perl, or JavaScript inside the database. The `u` (untrusted) variants have **full host access** and require superuser — a serious security and supply-chain surface, and usually unavailable on managed platforms. `plv8` (trusted JS) is the most defensible. Default to doing application logic in the application; reach for in-DB languages only for genuine data-locality wins.

**`plpgsql_check`** — ✅ Strong · *third-party*. Static analysis / linter for PL/pgSQL — catches errors and unused variables your functions would otherwise hit at runtime. Cheap quality win for any codebase with substantial stored logic.

**`pg_hint_plan`** — ⚠️ Caution · *third-party*. Forces planner decisions (join order, index choice) via hints. Sometimes the only pragmatic fix for a stubborn plan, but it **freezes decisions against changing data** and masks the real cause (usually bad statistics — see the [planner section](ADVANCED_POSTGRES.md#4-the-query-planner--statistics)). A last resort, not a tool of first reach.

**`pgTAP`** — 🟡 Situational · *third-party*. A unit-testing framework for your schema, functions, and data, runnable in CI. Worth it when your database carries meaningful business logic.

---

## 14. Replication & CDC

**`pgoutput`** — ⭐ Essential · *built-in*. The native logical-replication output plugin — what `CREATE PUBLICATION`/`SUBSCRIPTION` and most modern CDC tools use. Nothing to install. See [Replication](ADVANCED_POSTGRES.md#11-replication--high-availability).

**`wal2json` / `test_decoding`** — 🟡 Situational · *third-party / contrib*. Logical-decoding output plugins that emit changes as JSON — useful for custom change-data-capture pipelines. `test_decoding` ships with Postgres (it's a demo, but usable); `wal2json` is the popular JSON option. For serious CDC, most teams run **Debezium** (an external system, not an extension) on top of native logical replication rather than hand-building on these.

**`pglogical`** — 🧪 Specialist · *third-party*. Predates and extends core logical replication (selective replication, conflict handling, cross-version). Native logical replication has absorbed most of its common use cases; reach for `pglogical` only for the advanced topologies core still doesn't cover.

---

## 15. Managed-Service Availability Matrix

The deciding factor for most teams. **Directional, not authoritative — verify against current provider docs.** ✅ = supported, ⚠️ = partial/conditional, ❌ = not available, *self* = self-managed only.

| Extension | RDS / Aurora | Cloud SQL | Azure Flexible | Supabase |
|---|---|---|---|---|
| Contrib core (`pg_stat_statements`, `pg_trgm`, `citext`, `hstore`, `btree_gin/gist`, `pgcrypto`, `unaccent`, `postgres_fdw`, `tablefunc`, `fuzzystrmatch`) | ✅ | ✅ | ✅ | ✅ |
| `auto_explain` | ✅ | ✅ | ✅ | ✅ |
| `pgaudit` | ✅ | ✅ | ✅ | ✅ |
| `pg_repack` | ✅ | ⚠️ | ⚠️ | ✅ |
| `pg_cron` | ✅ | ✅ | ✅ | ✅ |
| `pg_partman` | ✅ | ✅ | ✅ | ✅ |
| `PostGIS` | ✅ | ✅ | ✅ | ✅ |
| `pgvector` | ✅ | ✅ | ✅ | ✅ |
| `hypopg` | ❌ | ✅ | ✅ | ✅ |
| `TimescaleDB` | ❌ | ❌ | ⚠️ | ⚠️ |
| `Citus` | ❌ | ❌ | ✅ (Cosmos DB for PG) | ❌ |
| `plpython3u` (untrusted) | ❌ | ❌ | ❌ | ❌ |
| `plv8` (trusted JS) | ⚠️ | ⚠️ | ⚠️ | ✅ |
| `wal2json` | ✅ | ✅ | ✅ | ✅ |

The pattern: **contrib and the popular third-party extensions (PostGIS, pgvector, pg_cron, pgaudit, pg_partman) are available almost everywhere.** The friction is concentrated in TimescaleDB (not on RDS/Aurora), Citus (effectively Azure-only as a managed offering), and any untrusted procedural language (nowhere managed).

---

## 16. Tier Summary & Decision Guide

### By verdict

- ⭐ **Essential (every prod DB):** `pg_stat_statements`, `plpgsql` (built-in), `pgoutput` (built-in).
- ✅ **Strong (reach for on need, production-proven):** `auto_explain`, `pgaudit`, `pg_repack`, `hypopg`, `amcheck`, `pg_trgm`, `btree_gin/gist`, `unaccent`, `PostGIS`, `pgvector`, `pgcrypto`, `postgres_fdw`, `pg_cron`, `pg_partman`, `plpgsql_check`.
- 🟡 **Situational:** `citext`, `ltree`, `pgstattuple`/`pg_buffercache`/`pg_prewarm`, `pg_wait_sampling`, `TimescaleDB`, `anon`, `file_fdw`, the database-specific FDWs, `pgmq`, `pgTAP`, `sslinfo`.
- 🧪 **Specialist:** `Citus`, `pgvectorscale`, `pg_search`/ParadeDB, `bloom`, `set_user`, Supabase `wrappers`, `pglogical`.
- ⚠️ **Caution:** `hstore` (legacy → jsonb), `uuid-ossp` (→ built-ins), untrusted PLs (`plpython3u`/`plperlu`), `pg_hint_plan`.

### Quick decision tree

```
Need monitoring?                 → pg_stat_statements + auto_explain  (always)
Compliance/audit?                → pgaudit
Bloat without downtime?          → pg_repack
Fuzzy / substring search?        → pg_trgm (+ unaccent)
Geospatial?                      → PostGIS
Embeddings / RAG?                → pgvector  (pgvectorscale/pg_search if you outgrow it)
Time-series?                     → partitioning + BRIN + pg_partman first; TimescaleDB if you need
                                   continuous aggregates/compression AND your platform supports it
In-DB scheduled jobs?            → pg_cron (+ pg_partman for partitions)
Column encryption?               → pgcrypto (or app-side KMS for high sensitivity)
Query another database?          → postgres_fdw (check EXPLAIN for push-down)
Single node truly maxed out?     → partition → read replicas → bigger box → THEN Citus
Want to test an index cheaply?   → hypopg
```

### The one rule that overrides the rest

**Check your platform's supported-extensions list before you design.** The best extension you can't install is worth nothing; a slightly-less-ideal one your managed service supports will save you a migration. Availability first, elegance second.

---

## Further Reading

- Companion guides: [PostgreSQL Feature Reference](POSTGRES.md) · [Advanced PostgreSQL Study Guide](ADVANCED_POSTGRES.md)
- `pg_available_extensions` on your own server — the ground truth for what you can install
- PGXN (the PostgreSQL Extension Network): https://pgxn.org/
- Your provider's supported-extensions docs (RDS / Cloud SQL / Azure / Supabase) — the real constraint
- PostGIS, TimescaleDB, Citus, and pgvector each have excellent project docs; start there before adopting

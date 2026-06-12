# PostgreSQL Extensions in Production

PostgreSQL's extension system is its single biggest strategic advantage over other databases: the same engine becomes a geospatial database (PostGIS), a time-series store (TimescaleDB), a vector database (pgvector), a sharded distributed system (Citus), an analytics engine (pg_duckdb), or a job scheduler (pg_cron) — without leaving SQL or running a second system. The catalog is enormous and uneven, so the useful question is **not "what's cool"** but **"is it maintained, is it available on my platform, and does it pay rent for the operational cost it adds?"**

This guide is the third member of a set: the [PostgreSQL Feature Reference](POSTGRES.md) (the SQL surface area) and the [Advanced PostgreSQL Study Guide](ADVANCED_POSTGRES.md) (the engine, performance, and ops). Here we focus on **which extensions are worth running in production** — with, for each one: what it actually does under the hood, the verdict, the production caveats that don't appear in the README, and a link to the documentation that does.

Extension availability, version support, and managed-platform allow-lists change frequently. Treat every availability note here as **directional** — confirm against your provider's current supported-extensions list before you commit.

---

## Table of Contents

1. [How Extensions Actually Work](#1-how-extensions-actually-work)
2. [The Production Lens (verdict tiers + how to adopt safely)](#2-the-production-lens)
3. [The Day-One Shortlist](#3-the-day-one-shortlist)
4. [Observability & Operations](#4-observability--operations)
5. [Indexing, Search & Data Types](#5-indexing-search--data-types)
6. [Geospatial: PostGIS & Friends](#6-geospatial-postgis--friends)
7. [Time-Series: TimescaleDB & Friends](#7-time-series-timescaledb--friends)
8. [Vectors & AI: pgvector & the Ecosystem](#8-vectors--ai-pgvector--the-ecosystem)
9. [Analytics, Columnar & Approximation](#9-analytics-columnar--approximation)
10. [JSON, Graph & API Layers](#10-json-graph--api-layers)
11. [Security & Encryption](#11-security--encryption)
12. [Foreign Data Wrappers & Federation](#12-foreign-data-wrappers--federation)
13. [Scale-Out & Sharding: Citus](#13-scale-out--sharding-citus)
14. [Scheduling, Queues & Background Jobs](#14-scheduling-queues--background-jobs)
15. [Procedural Languages, Dev Tools & Planner Tools](#15-procedural-languages-dev-tools--planner-tools)
16. [Replication & CDC](#16-replication--cdc)
17. [Managed-Service Availability Matrix](#17-managed-service-availability-matrix)
18. [Tier Summary & Decision Guide](#18-tier-summary--decision-guide)

---

## 1. How Extensions Actually Work

The production-relevant mechanics — most adoption surprises come from one of these.

### 1.1 What an extension physically is

An extension is three kinds of file installed on the *server* (not in your database): a **control file** (`pgvector.control`: name, default version, whether it's trusted/relocatable, dependencies on other extensions), one or more **SQL scripts** (`vector--0.8.0.sql` creates the types/functions/operators; `vector--0.7.0--0.8.0.sql` migrates between versions — `ALTER EXTENSION ... UPDATE` literally runs a chain of these), and — for anything beyond pure SQL/PLpgSQL — a **shared library** (`vector.so`) of C code that the SQL script's `CREATE FUNCTION ... LANGUAGE C` statements bind to. `CREATE EXTENSION` then runs the script *in your database* and records every created object in `pg_extension`/`pg_depend`, which is what makes the whole bundle drop cleanly with `DROP EXTENSION` and ride along correctly in `pg_dump` (the dump stores `CREATE EXTENSION`, not the objects). The corollary that bites people: **the server-side files must exist before `CREATE EXTENSION` works** — that's the part a managed provider controls, and why "just install X" is a platform question, not a SQL question. Reference: [Packaging Related Objects into an Extension](https://www.postgresql.org/docs/current/extend-extensions.html).

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- install into the current database
CREATE EXTENSION postgis SCHEMA gis;             -- pin its objects to a schema
ALTER EXTENSION postgis UPDATE TO '3.5.2';       -- run the migration-script chain
SELECT * FROM pg_available_extensions ORDER BY name;  -- what CAN be installed here
\dx                                              -- what IS installed (in psql)
```

### 1.2 The four distinctions that decide whether you can use one at all

- **Contrib vs third-party.** "Contrib" modules ship with PostgreSQL in the `postgresql-contrib` package and are maintained and release-tested by the core project — [`pg_stat_statements`](https://www.postgresql.org/docs/current/pgstatstatements.html), [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html), [`pgcrypto`](https://www.postgresql.org/docs/current/pgcrypto.html), [`postgres_fdw`](https://www.postgresql.org/docs/current/postgres-fdw.html), [`citext`](https://www.postgresql.org/docs/current/citext.html), [`hstore`](https://www.postgresql.org/docs/current/hstore.html), [`btree_gin`](https://www.postgresql.org/docs/current/btree-gin.html)/[`btree_gist`](https://www.postgresql.org/docs/current/btree-gist.html), [`unaccent`](https://www.postgresql.org/docs/current/unaccent.html), [`fuzzystrmatch`](https://www.postgresql.org/docs/current/fuzzystrmatch.html), [`tablefunc`](https://www.postgresql.org/docs/current/tablefunc.html), [`pgstattuple`](https://www.postgresql.org/docs/current/pgstattuple.html), [`amcheck`](https://www.postgresql.org/docs/current/amcheck.html), and more (full list: [Additional Supplied Modules](https://www.postgresql.org/docs/current/contrib.html)). These are the safest, most universally available extensions — they version with the server and upgrade with it. Everything else (PostGIS, pgvector, TimescaleDB, Citus, pg_cron, pg_partman, pgaudit) is third-party: separately released, separately packaged, separately allowed-or-not by your platform.
- **Trusted vs untrusted.** Since PG13, *trusted* extensions (marked in the control file) can be installed by a non-superuser with `CREATE` on the database — most contrib data-type/index extensions qualify. *Untrusted* ones — anything that touches the filesystem, makes network calls, or provides an untrusted procedural language (`plpython3u`) — require superuser. On managed services you are **never** a real superuser; providers either pre-mark a curated list as trusted, proxy installation through their own tooling, or simply don't offer the extension. This is the root cause of 90% of "why can't I install X."
- **`shared_preload_libraries` (requires a restart).** Extensions that hook deep into the server — planner hooks, executor hooks, background workers, shared-memory segments — must be loaded at postmaster start: [`pg_stat_statements`](https://www.postgresql.org/docs/current/pgstatstatements.html), [`pgaudit`](https://github.com/pgaudit/pgaudit), [`pg_cron`](https://github.com/citusdata/pg_cron), [`citus`](https://docs.citusdata.com/), [`timescaledb`](https://docs.timescale.com/), [`auto_explain`](https://www.postgresql.org/docs/current/auto-explain.html) (loadable per-session too), `pg_partman`'s background worker. Plan the maintenance window; you cannot add these live. The mechanism, for the curious: these libraries register hooks and request shared memory in `_PG_init()`, which must run before backends fork — hence the restart.
- **Schema & `search_path`.** Extension objects land in a schema (default `public`, unless the extension is "relocatable" and you choose). For anything security-adjacent, install into a dedicated schema and keep `search_path` tight — a function resolved through a writable schema is a privilege-escalation vector (see the [Advanced guide](ADVANCED_POSTGRES.md#7-locking--concurrency-at-scale) on `SECURITY DEFINER`, and the project's own [security advice](https://www.postgresql.org/docs/current/ddl-schemas.html#DDL-SCHEMAS-PATTERNS)).

```ini
# postgresql.conf — these need a restart to take effect
shared_preload_libraries = 'pg_stat_statements,pgaudit,pg_cron'
```

### 1.3 The modern packaging landscape (and how extensions get written)

Where extensions come from, in descending order of confidence: your distro/provider's packages → the [PGDG apt/yum repositories](https://www.postgresql.org/download/) (the community's official builds of the popular third-party set) → [PGXN](https://pgxn.org/) (the long-tail network) and newer registries like [Trunk](https://pgt.dev/). Two frameworks changed who can write extensions safely: [`pgrx`](https://github.com/pgcentralfoundation/pgrx) lets extensions be written in Rust instead of C (pgvectorscale, pg_search, pg_graphql, and most new commercial extensions are pgrx-built — memory-safety bugs in C extensions crash *the whole database*, so this matters more than language fashion), and AWS's [`pg_tle`](https://github.com/aws/pg_tle) ("Trusted Language Extensions") lets you package pure-SQL/PLpgSQL/PLRust extensions installable *without* server filesystem access — i.e., installable on RDS by mortals.

**What is *not* an extension**, to save you a search: PgBouncer and pgcat (connection poolers — separate processes), Patroni (HA orchestration), pgBackRest/WAL-G (backup tools), and Debezium (CDC) all live *outside* the server. If a "Postgres add-on" doesn't appear in `pg_available_extensions`, it's infrastructure, and belongs to the [Advanced guide](ADVANCED_POSTGRES.md)'s territory.

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

1. **Confirm platform support first.** If you're on RDS/Cloud SQL/Azure/Supabase, the supported-extensions list is the hard constraint — check it before designing around an extension ([RDS](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html) · [Cloud SQL](https://cloud.google.com/sql/docs/postgres/extensions) · [Azure](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions) · [Supabase](https://supabase.com/docs/guides/database/extensions)).
2. **Check the pulse.** Recent releases, an active repo, a real maintainer or company behind it. A clever-but-abandoned extension is a future migration blocker — and "abandoned" includes "acquired and refocused": this catalog has multiple entries whose corporate sponsor pivoted.
3. **Mind the lock-in.** PostGIS data is portable; a TimescaleDB hypertable or a Citus distributed table changes your schema and your exit path. Know the off-ramp before you board.
4. **Test the upgrade path — both of them.** Extensions version independently of PostgreSQL, so there are two upgrades to rehearse: `ALTER EXTENSION ... UPDATE` (the script chain of §1.1) and the *server* major-version upgrade with the extension installed (`pg_upgrade` requires compatible extension binaries for the new major version to exist — a third-party extension that lags the PostgreSQL release cycle blocks your whole cluster's upgrade; PostGIS and TimescaleDB publish explicit upgrade choreography for exactly this reason).
5. **Account for `shared_preload_libraries`.** If it needs one, you owe a restart and a place in the boot sequence.
6. **Watch the supply chain.** C extensions run native code *inside your database process* — a segfault is a database crash, a vulnerability is RCE-with-your-data. Treat an obscure C extension like any dependency with that blast radius; prefer pgrx/Rust builds and trusted-language extensions where the choice exists.

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

**[`pg_stat_statements`](https://www.postgresql.org/docs/current/pgstatstatements.html)** — ⭐ Essential · *contrib*. Aggregates execution statistics per *normalized* query (constants stripped, so `WHERE id = 1` and `WHERE id = 2` are one entry keyed by `queryid`): calls, total/mean/min/max/stddev time, rows, buffer hits/reads/dirties, WAL bytes, JIT time. The discipline it enables: find cost centers by **total time, not mean** — the 2ms query called 50M times/day outranks the 4s report — and diff snapshots over time (reset with `pg_stat_statements_reset()` at deploys to attribute regressions). Mechanics worth knowing: it hooks the executor via `shared_preload_libraries` (restart required); it keeps the top `pg_stat_statements.max` (default 5000) entries and **evicts the rest** — on ORM-heavy apps with unparameterized SQL, eviction churn can make numbers lie, which is itself a finding (parameterize!); per-query overhead is small single-digit percent, and every serious shop pays it without thinking. Available everywhere (RDS, Aurora, Cloud SQL, Azure, Supabase).

```sql
SELECT query, calls, round(total_exec_time) AS total_ms,
       round(mean_exec_time,2) AS mean_ms, rows,
       shared_blks_read, wal_bytes
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;
```

**[`auto_explain`](https://www.postgresql.org/docs/current/auto-explain.html)** — ✅ Strong · *contrib*. Logs the actual plan of any statement exceeding a duration threshold — the only practical way to capture the bad plan that fires at 3 a.m. under production data volumes and is gone by the time you can reproduce it (the plan you get from a manual `EXPLAIN` the next morning is the *good* plan; statistics changed). The settings that matter: `log_analyze` (real row counts and timings — this is the valuable part; measure its overhead, usually acceptable with `log_timing` considerations), `log_buffers` (I/O attribution), `log_nested_statements` (catch the slow query *inside* the PL/pgSQL function), and `log_min_duration` set just above your p99. Pairs with `pg_stat_statements` as capture-the-instance vs. rank-the-aggregate.

```ini
auto_explain.log_min_duration = '500ms'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_nested_statements = on
```

**[`pgaudit`](https://github.com/pgaudit/pgaudit)** — ✅ Strong · *third-party, widely packaged*. Structured, fine-grained audit logging that plain `log_statement = all` can't produce: per-class (`READ`, `WRITE`, `DDL`, `ROLE`, `FUNCTION`), per-role (`ALTER ROLE app SET pgaudit.log = 'ddl, role'`), and **object-level** auditing (log only access to specific tables, via grants to an audit role) — with the crucial property that statements are logged *as executed inside functions/views too*, closing the "hid the query in a stored procedure" hole. The standard answer for SOC2/HIPAA/PCI evidence. Supported on [RDS/Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.pgaudit.html), Cloud SQL, Azure, Supabase. Cost: log volume — scope it (`pgaudit.log = 'ddl, role, write'` is a sane start; `READ` auditing of a busy OLTP database will drown your log pipeline and your budget — that's what object-level mode is for).

**[`pg_repack`](https://reorg.github.io/pg_repack/)** — ✅ Strong · *third-party*. Rebuilds bloated tables and indexes online. How it pulls that off: it creates a shadow copy of the table, installs a trigger capturing concurrent changes into a log table, copies the original data, replays the log, then swaps the relfilenodes in a brief `ACCESS EXCLUSIVE` lock measured in seconds — versus `VACUUM FULL`'s lock-for-the-whole-rewrite. The caveats that the README undersells: you need ~2× the table's disk during the rebuild; the table must have a primary key or not-null unique index; the final lock acquisition can queue behind long transactions (use `--wait-timeout`, and watch the Ch.-7-of-the-internals-guide pile-up behind it); and the trigger adds write overhead during the rebuild — schedule accordingly. Supported on RDS/Aurora, Cloud SQL, Azure (it's a client tool + server extension; versions must match). Alternative worth knowing: [`pg_squeeze`](https://github.com/cybertec-postgresql/pg_squeeze) (CYBERTEC) does the same job using logical decoding instead of triggers — less write-path overhead, runs entirely server-side as a background worker, schedulable; less universally packaged. See the [bloat recipe](ADVANCED_POSTGRES.md#16-worked-performance-recipes).

```bash
pg_repack -d app -t orders --wait-timeout 60   # rebuild one table online
```

**[`hypopg`](https://hypopg.readthedocs.io/)** — ✅ Strong · *third-party*. **Hypothetical indexes**: create a virtual index (metadata only — no build, no disk, no locks, visible only to your session) and ask the planner whether it *would* use it and what the plan cost becomes. This converts index design on a 2 TB table from "build for six hours and hope" into an interactive loop, and it composes with `EXPLAIN` exactly as you'd wish. It can also hide *existing* indexes (`hypopg_hide_index`) to answer "is this 300 GB index actually load-bearing?" before you drop it. On Cloud SQL/Azure/Supabase and self-managed; not on RDS as of writing.

```sql
SELECT * FROM hypopg_create_index('CREATE INDEX ON orders (customer_id, created_at)');
EXPLAIN SELECT * FROM orders WHERE customer_id = 42 ORDER BY created_at DESC;  -- uses it?
SELECT hypopg_reset();   -- discard hypotheticals
```

**[`amcheck`](https://www.postgresql.org/docs/current/amcheck.html)** / **[`pg_amcheck`](https://www.postgresql.org/docs/current/app-pgamcheck.html)** — ✅ Strong · *contrib*. Verifies B-tree invariants (key ordering within and across pages, sibling-link consistency, parent/child agreement) and heap consistency — catching corruption from bad hardware, fsync lies, or bugs *before* it surfaces as wrong query results. `bt_index_check()` takes only light locks and is safe to run routinely; `bt_index_parent_check()` is stricter but locks harder; the `pg_amcheck` CLI parallelizes a whole-database sweep. Cheap insurance: run it in a weekly maintenance job, and always after storage incidents or in-place major upgrades. (For *why* checksums alone don't catch these cases — pages individually fine, mutually wrong — see the [Database Internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md), Ch. 11.)

**[`pgstattuple`](https://www.postgresql.org/docs/current/pgstattuple.html) / [`pg_buffercache`](https://www.postgresql.org/docs/current/pgbuffercache.html) / [`pg_prewarm`](https://www.postgresql.org/docs/current/pgprewarm.html)** — 🟡 Situational · *contrib*. The diagnosis trio: `pgstattuple` measures bloat *precisely* (dead-tuple percentage, free space — versus the estimates in `pg_stat_user_tables`; use `pgstattuple_approx` on big tables), `pg_buffercache` shows exactly what occupies shared_buffers (by relation, by usage count — the ground truth behind cache-hit folklore), and `pg_prewarm` loads a relation into cache on demand — plus its quietly excellent `autoprewarm` background worker, which records the buffer set periodically and restores it after restart, turning the post-failover cold-cache p99 spike from minutes into seconds. Reach for them when diagnosing a specific I/O or bloat problem; `autoprewarm` arguably belongs on by default on any latency-sensitive instance.

**[`pg_walinspect`](https://www.postgresql.org/docs/current/pgwalinspect.html) / [`pageinspect`](https://www.postgresql.org/docs/current/pageinspect.html) / [`pg_visibility`](https://www.postgresql.org/docs/current/pgvisibility.html) / [`pg_freespacemap`](https://www.postgresql.org/docs/current/pgfreespacemap.html)** — 🧪 Specialist · *contrib*. The forensics kit: SQL-level views of WAL records (PG15+; "what is generating all this WAL?" answered without shell access to run `pg_waldump`), raw page contents (tuple headers, B-tree internals), visibility-map bits (why isn't this an index-only scan?), and free-space-map state. Not daily drivers — but when you need them, nothing else will do, and they're how you verify the storage claims in the [internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md) against your own database.

**[`pg_wait_sampling`](https://github.com/postgrespro/pg_wait_sampling) / [`pg_stat_kcache`](https://github.com/powa-team/pg_stat_kcache) / [`pg_qualstats`](https://github.com/powa-team/pg_qualstats)** — 🟡 Situational · *third-party*. The deep-performance stack, usually deployed together under [PoWA](https://powa.readthedocs.io/) (the PostgreSQL Workload Analyzer): sampled wait-event history per query (what `pg_stat_activity` would have shown you had you been looking — closes the "what was it *waiting on*" gap in `pg_stat_statements`, which only records time), per-query OS-level CPU/disk metrics via getrusage (separates "burned CPU" from "waited on I/O" definitively), and per-predicate selectivity statistics (which `WHERE` clauses run often with poor index support — PoWA combines this with hypopg to *suggest* indexes and prove them hypothetically). Mostly self-managed (each needs `shared_preload_libraries`); the payoff is a self-hosted observability suite competitive with commercial APM for the database tier.

**[`pg_stat_monitor`](https://github.com/percona/pg_stat_monitor)** — 🧪 Specialist · *third-party (Percona)*. A `pg_stat_statements` superset: time-bucketed histories (rate-of-change without snapshot tooling), latency histograms per query, actual query examples with parameters, query-plan capture. Ships in Percona's distribution and some platforms. The trade: more overhead than `pg_stat_statements`, a moving API across versions, and most fleets get the same answers from `pg_stat_statements` + a metrics scraper — adopt if you're already in the Percona ecosystem or genuinely need per-query histograms at the source.

---

## 5. Indexing, Search & Data Types

Mostly contrib, mostly trusted, available nearly everywhere — low-risk wins.

**[`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html)** — ✅ Strong · *contrib, trusted*. Decomposes strings into **trigrams** (three-character shingles: `"alicia"` → `{"  a"," al","ali","lic","ici","cia","ia "}`) and indexes the *set* with GIN — which is what makes the unindexable indexable: `LIKE '%substring%'` becomes "find rows whose trigram set contains the pattern's trigrams" (a GIN containment probe), and similarity search (`%` operator, `similarity()` ranking) becomes set-overlap arithmetic with a tunable threshold (`pg_trgm.similarity_threshold`, default 0.3). The default reach for "search that doesn't need a search engine": typo tolerance, autocomplete, substring match. Production notes: GIN trigram indexes are large (often comparable to the column data) and write-amplifying on hot text columns; very short patterns (1–2 chars) extract no useful trigrams and fall back to scans; for word-boundary-aware ranking, `word_similarity()` beats raw `similarity()`.

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX ON users USING GIN (name gin_trgm_ops);
SELECT name FROM users WHERE name % 'Alicia' ORDER BY similarity(name,'Alicia') DESC;
SELECT name FROM users WHERE name ILIKE '%lici%';   -- also served by the same index
```

**[`btree_gin`](https://www.postgresql.org/docs/current/btree-gin.html) / [`btree_gist`](https://www.postgresql.org/docs/current/btree-gist.html)** — ✅ Strong · *contrib, trusted*. Teach GIN/GiST to index plain scalar types (int, text, timestamp…) alongside their specialty types. Why that matters: an index can only combine columns *within one access method*, so "GIN on `(tenant_id, tags)`" or — the killer app — **exclusion constraints mixing equality and ranges** require the scalar operators inside GiST. "No overlapping bookings per room" is the canonical example, and it is the only way to enforce that invariant *in the database, race-free* (a `UNIQUE` index cannot express overlap; application-level checks have TOCTOU races):

```sql
CREATE EXTENSION btree_gist;
ALTER TABLE bookings ADD EXCLUDE USING GIST (room_id WITH =, during WITH &&);
```

**[`citext`](https://www.postgresql.org/docs/current/citext.html)** — 🟡 Situational · *contrib, trusted*. Case-insensitive text type — comparisons, uniqueness, and lookups all fold case automatically. Convenient for emails/usernames, with real fine print: every comparison pays a `lower()` under the hood; `LIKE` patterns behave subtly differently; and the modern alternative is either the explicit `CREATE UNIQUE INDEX ON users (lower(email))` (portable, visible in the schema) or PG15+ **nondeterministic ICU collations** (the standards-based answer, with their own LIKE limitations). Fine to use; know the alternatives exist and pick once per codebase.

**[`unaccent`](https://www.postgresql.org/docs/current/unaccent.html)** — ✅ Strong · *contrib, trusted*. A text search *dictionary* that strips diacritics (`café` → `cafe`). Two usage modes: ad-hoc (`unaccent('Hôtel')` — note: not immutable by default, so wrap it in an immutable SQL function before using it in an expression index) and properly, inside a full-text search configuration so FTS becomes accent-insensitive. Combine with `pg_trgm` for accent-and-typo-tolerant search over international names — the pairing solves most "search people/places" requirements without Elasticsearch.

**[`hstore`](https://www.postgresql.org/docs/current/hstore.html)** — ⚠️ Caution (legacy) · *contrib, trusted*. Flat string-key/string-value type predating `jsonb`. For new work **use `jsonb`** — typed values, nesting, richer operators, better indexing, and an ecosystem that assumes it. `hstore` remains correct for existing schemas; don't migrate working systems just for fashion, and don't start new ones on it.

**[`ltree`](https://www.postgresql.org/docs/current/ltree.html)** — 🟡 Situational · *contrib, trusted*. Materialized-path labels for trees (`Top.Science.Astronomy`) with a query language (`lquery`: `Top.*.Astronomy@`) and GiST indexing. The honest comparison: recursive CTEs handle arbitrary graph walks with zero schema commitment; `ltree` wins when the dominant query is "all descendants of X" / "ancestors of Y" at scale (one indexed operator versus an iterative scan) and the tree is mostly-read (moving a subtree means rewriting every descendant's path — that's the materialized-path trade, not an ltree defect).

**[`intarray`](https://www.postgresql.org/docs/current/intarray.html) / [`cube`](https://www.postgresql.org/docs/current/cube.html) + [`earthdistance`](https://www.postgresql.org/docs/current/earthdistance.html) / [`tablefunc`](https://www.postgresql.org/docs/current/tablefunc.html) / [`fuzzystrmatch`](https://www.postgresql.org/docs/current/fuzzystrmatch.html)** — 🟡 Situational · *contrib*. The useful long tail: faster int-array operators with GIN/GiST support (tag systems before they justify a join table); great-circle distance *without* PostGIS (`earthdistance` over `cube` — legitimate for "stores within 10 km" when that's your entire geo requirement); `crosstab()` pivots (mostly superseded by `FILTER` aggregates, still occasionally the clean tool); and phonetic matching (`soundex`, `metaphone`, `levenshtein` — pairs with `pg_trgm` for name matching; mind the per-call cost of `levenshtein` in large scans).

**[`bloom`](https://www.postgresql.org/docs/current/bloom.html)** — 🧪 Specialist · *contrib*. Bloom-filter index: one compact signature per row over *many* columns, probed for arbitrary equality combinations — the answer to "users filter by any subset of 12 attributes" where 12 B-trees (and their write cost) or a 12-column B-tree (useless unless the prefix matches) both fail. Lossy (every match rechecks the heap), equality-only, and sized by signature bits you must tune. Niche, but when it fits, nothing else does.

**[`rum`](https://github.com/postgrespro/rum)** — 🧪 Specialist · *third-party (Postgres Pro)*. GIN's ambitious sibling: posting lists carry extra payload (lexeme *positions*, timestamps), so **ranked full-text search comes back in index order** — eliminating the classic GIN+FTS pain of "fetch everything, rank in memory, then LIMIT" for `ORDER BY ts_rank(...) LIMIT 10`, and enabling phrase-distance ordering. The cost: bigger index, slower builds, and third-party packaging (self-managed mostly). If your native-FTS pain is specifically *ranking latency*, RUM is the targeted fix; if it's relevance quality, look at ParadeDB's BM25 (§8); if it's everything, that's when you concede to a search engine.

**[`pgroonga`](https://pgroonga.github.io/)** — 🧪 Specialist · *third-party*. Full-text search backed by the Groonga engine, with one headline capability native FTS lacks: proper **CJK (Chinese/Japanese/Korean) tokenization** — languages without word delimiters defeat the native parser, and PGroonga is the production-standard answer inside Postgres (Supabase ships it). Also fast for `LIKE` and supports its own ranking. If your product is Japan/China-facing, this is less "specialist" and more "required"; otherwise prefer the smaller hammers above.

**[`uuid-ossp`](https://www.postgresql.org/docs/current/uuid-ossp.html)** — ⚠️ Caution (mostly obsolete) · *contrib*. Historically the UUID generator; modern Postgres has built-in `gen_random_uuid()` (v4) and **v18 adds native [`uuidv7()`](https://www.postgresql.org/docs/18/functions-uuid.html)** (time-ordered, so B-tree inserts go to the right edge instead of spraying the whole index — the [internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md) Ch. 3 explains why that's a 2× index-size difference). On 13–17 wanting UUIDv7, [`pg_uuidv7`](https://github.com/fboulnois/pg_uuidv7) fills the gap. Prefer built-ins.

---

## 6. Geospatial: PostGIS & Friends

**[PostGIS](https://postgis.net/documentation/)** — ✅ Strong (the gold standard) · *third-party*. The most mature, most respected Postgres extension, period — 20+ years old, OGC-standard-compliant, and the reference implementation other databases' geo features are measured against. What you get: `geometry` (planar) and `geography` (geodetic — computations on the spheroid) types; several hundred functions (`ST_DWithin`, `ST_Intersects`, `ST_Buffer`, `ST_Transform` across coordinate systems…); GiST/SP-GiST spatial indexes (R-tree semantics — bounding-box containment in the tree, exact geometry recheck on the heap); plus opt-in companions for [rasters](https://postgis.net/docs/RT_reference.html), topology, and [TIGER geocoding](https://postgis.net/docs/Extras.html). If you do *anything* with maps, locations, or shapes, this is the answer, and it is genuinely production-grade everywhere — every major managed platform ships it.

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

Production notes: **`geography` vs `geometry` is the decision that matters** — `geography` gives correct distances on lat/long with zero projection knowledge (slower math, fewer functions); `geometry` is faster and fuller-featured but demands you manage projections (`ST_Transform` to a local planar SRID for area/distance — getting this wrong is the classic PostGIS bug, and it fails *quietly*, with plausible-looking wrong numbers). Index-wise, `ST_DWithin` is index-driven; bare `ST_Distance < x` is not — write the former. Upgrades are real choreography: PostGIS versions bind to PostgreSQL versions, and `SELECT postgis_extensions_upgrade();` plus the [upgrade matrix](https://trac.osgeo.org/postgis/wiki/UsersWikiPostgreSQLPostGIS) belong in your runbook — PostGIS is the extension most likely to gate your next `pg_upgrade`.

**[pgRouting](https://pgrouting.org/)** — 🧪 Specialist · *third-party*. Graph routing over PostGIS networks: Dijkstra/A*/contraction hierarchies, drive-time isochrones, TSP. If your product computes routes or service areas on your own road/network data, it's the established tool (and the data-prep — building a correctly-noded network topology — is most of the project). For "just give me directions," a routing API is less work than owning OSM data.

**[h3-pg](https://github.com/zachasme/h3-pg)** — 🧪 Specialist · *third-party*. Uber's H3 hexagonal hierarchical grid as SQL functions: bucket points into hex cells (`h3_lat_lng_to_cell`), aggregate by cell, neighbor/ring math, multi-resolution rollups. The modern idiom for *analytics* on location data (demand heatmaps, supply/demand balancing, geo-joins at scale) — cells are just bigints, so everything downstream is ordinary fast SQL. Complements rather than replaces PostGIS (exact shapes still need real geometry).

**[pointcloud](https://github.com/pgpointcloud/pointcloud) / [MobilityDB](https://github.com/MobilityDB/MobilityDB)** — 🧪 Specialist · *third-party*. LiDAR point-cloud storage and spatiotemporal trajectory types (`tgeompoint` — *moving* geometries with time-aware operators: "did these two vehicles come within 50 m of each other?") respectively. Narrow, academic-rooted, genuinely good at their narrow things; evaluate maintenance pulse before betting a product on them.

---

## 7. Time-Series: TimescaleDB & Friends

**[TimescaleDB](https://docs.timescale.com/)** — 🟡 Situational (powerful, but check availability) · *third-party*. Turns Postgres into a serious time-series database. The four pillars, each with real machinery behind it: **hypertables** (automatic partitioning by time — chunks are created as data arrives, sized by interval; the planner prunes chunks aggressively, including at *execution* time for `now()`-relative predicates that defeat plain-Postgres planning-time pruning); **columnar compression** (segment-by/order-by reorganization into compressed batches — commonly 90%+ on metrics data, often *faster* to scan than the uncompressed row store for analytics because of column locality); **continuous aggregates** (materialized rollups maintained *incrementally* by background workers, with real-time blending of the not-yet-materialized tail — the feature plain materialized views conspicuously lack); and **retention/lifecycle policies** (`add_retention_policy` — dropping a chunk is instant DDL versus the `DELETE`+vacuum grind). Two production caveats that matter a lot:

- **Availability:** **not on Amazon RDS or Aurora.** It's offered as managed [Timescale Cloud](https://www.timescale.com/cloud), is available on Azure Flexible Server (Apache-2 subset) and Supabase (similar caveats), and self-managed gets everything. If you're committed to RDS, this option is off the table — the most common deal-breaker, discover it early.
- **Lock-in & licensing:** hypertables reshape your schema and your exit path (decompress + dump is the off-ramp; rehearse it). The **Apache-2 edition omits** compression, continuous aggregates, and most policies — i.e., the reasons you wanted it; the full feature set is under the source-available TSL license (fine to self-host, not fine to offer as a managed service). Know which edition your platform ships.

```sql
CREATE EXTENSION timescaledb;
SELECT create_hypertable('metrics', 'ts');
ALTER TABLE metrics SET (timescaledb.compress,
                         timescaledb.compress_segmentby = 'device_id');
SELECT add_compression_policy('metrics', INTERVAL '7 days');
SELECT add_retention_policy('metrics', INTERVAL '180 days');
```

**The plain-Postgres alternative** — ✅ Strong. For many time-series workloads, native **declarative range partitioning by time + a BRIN index + [`pg_partman`](https://github.com/pgpartman/pg_partman) + [`pg_cron`](https://github.com/citusdata/pg_cron)** gets you 80% of the value with zero lock-in and universal availability: partition pruning ≈ chunk pruning, `DROP PARTITION` ≈ retention policy, BRIN gives you tiny indexes on append-only time data ([internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md) Ch. 10), and a `pg_cron`-refreshed materialized view stands in for continuous aggregates if your rollup latency tolerance is minutes rather than seconds. Start here; graduate to TimescaleDB specifically for compression ratios, real-time continuous aggregates, or sub-minute rollup freshness. See [Partitioning at Scale](ADVANCED_POSTGRES.md#10-partitioning-at-scale).

**[pg_timeseries](https://github.com/tembo-io/pg_timeseries)** — 🧪 Specialist · *third-party (Tembo)*. A friendlier facade over the plain-Postgres stack (partman + columnar + convenience functions) under PostgreSQL-license terms. Watch its maintenance pulse (Tembo's pivots have left orphans before); the underlying pieces it orchestrates are all individually solid, which is also its safety net.

---

## 8. Vectors & AI: pgvector & the Ecosystem

**[pgvector](https://github.com/pgvector/pgvector)** — ✅ Strong (the default) · *third-party, now ubiquitous*. Adds a `vector` type (also `halfvec`, sparse `sparsevec`, and `bit` for binary embeddings), distance operators (`<->` L2, `<=>` cosine, `<#>` inner product), and two ANN index types for embeddings — the foundation of RAG and semantic search directly in your primary database. It has effectively won this space: supported on **RDS/Aurora, Cloud SQL, Azure, Supabase**, integrated by every ORM and AI framework, which makes "just use Postgres as your vector store" the legitimate default for most teams (your embeddings live next to the rows they describe — *joinable, transactional, access-controlled* — versus a second database to operate, sync, and secure).

The index decision, since it's the entire performance story: **HNSW** (navigable small-world graph; queries descend layers of long-range links — excellent recall/latency, the default choice) versus **IVFFlat** (k-means partitions; probe the nearest `lists` — much faster/cheaper to build, lower memory, needs representative data *before* indexing and degrades as data drifts). Both are **approximate**: recall < 100% by design, tunable at query time (`hnsw.ef_search`, `ivfflat.probes`) against latency. And one planner gotcha every pgvector deployment hits: an ANN index serves `ORDER BY embedding <=> $1 LIMIT k` — add a selective `WHERE` filter and the index returns k nearest *before* filtering (fewer results than expected, or a fallback to exact scan); pgvector 0.8+ added iterative scans to mitigate, and "filtered vector search" remains the area to test hardest (and the one the §8-ecosystem competitors compete on).

```sql
CREATE EXTENSION vector;
ALTER TABLE docs ADD COLUMN embedding vector(1536);
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
SET hnsw.ef_search = 40;
SELECT id FROM docs ORDER BY embedding <=> $1 LIMIT 10;
```

Production notes: HNSW builds are heavy — give `maintenance_work_mem` gigabytes and build off-peak (builds that fit in memory are ~10× faster); index size is often comparable to the vectors themselves; half-precision (`halfvec`) halves both at minimal recall cost and is the first knob to try at scale; and embeddings are TOASTed (Ch. 2 of the internals guide), so `SELECT *` on a docs table drags megabytes — select columns.

**The ecosystem** — 🧪 Specialist:
- **[pgvectorscale](https://github.com/timescale/pgvectorscale)** (Timescale, pgrx/Rust) — StreamingDiskANN index + statistical binary quantization on top of pgvector's types: vectors on disk rather than RAM, designed for the 50M+ vector regime where HNSW's memory bill hurts. Self-managed/Timescale Cloud.
- **[ParadeDB / pg_search](https://docs.paradedb.com/)** (pgrx/Rust) — **BM25 relevance-ranked full-text search** (the Elasticsearch ranking model) as a Postgres index, built on Tantivy. The honest positioning: native FTS ranks by `ts_rank` (no corpus statistics — no IDF), so relevance quality plateaus; pg_search brings real BM25, faceting, and fuzzy querying — the strongest "retire the Elasticsearch cluster" story, and the natural hybrid-search partner for pgvector (BM25 + vector + reciprocal rank fusion in one SQL statement).
- **[VectorChord](https://github.com/tensorchord/VectorChord)** — successor to pgvecto.rs; RaBitQ-based quantized indexing aimed at the same large-scale niche. Credible engineering; smaller ecosystem. pgvector remains the safe default until your scale says otherwise.
- **[pgai](https://github.com/timescale/pgai) / [PostgresML](https://postgresml.org/)** — ⚠️ Caution as architecture: in-database embedding generation and model inference (pgai calls embedding APIs and auto-syncs an embeddings column; PostgresML runs models *in* the server with GPUs). Convenient for prototypes; think hard before coupling your OLTP database's availability to model downloads, GPU drivers, or third-party API latency. Embedding generation usually belongs in the application tier; the *storage and search* belong in Postgres.

---

## 9. Analytics, Columnar & Approximation

Postgres's row store and Volcano executor (internals guide Ch. 9) are the wrong shape for scanning billions of rows of analytics — these extensions graft the right shape on, each with a different commitment level.

**[pg_duckdb](https://github.com/duckdb/pg_duckdb)** — 🧪 Specialist (the one to watch) · *third-party (DuckDB Labs + MotherDuck)*. Embeds the DuckDB vectorized analytics engine *inside* Postgres: queries (or marked tables) execute on DuckDB's columnar engine, including direct querying of **Parquet/Iceberg files on S3** (`SELECT ... FROM read_parquet('s3://...')`) joined against live Postgres tables. This is the emerging answer to "I want lakehouse analytics without an ETL pipeline or a second warehouse" — young, moving fast, with real backing from the engine's own authors. Evaluate for internal analytics today; be more careful wiring customer-facing latency SLOs to it.

**[citus columnar](https://docs.citusdata.com/en/stable/admin_guide/table_management.html#columnar-storage) / [hydra columnar](https://github.com/hydradatabase/hydra)** — 🧪 Specialist · *third-party*. Columnar **table access methods** (`USING columnar` — the pluggable-storage API from the internals guide put to work): column-chunked, compressed storage that turns wide-scan aggregates 5–20× faster and 5–10× smaller. The shared limitations to respect: append-optimized (updates/deletes restricted or expensive), no index-driven point reads worth the name, and best deployed as *archive/rollup tables beside* your row-store hot set rather than as a wholesale conversion. Citus's columnar comes inside the Citus extension (usable without distributing tables); Hydra packaged the same lineage standalone — check maintenance pulse.

**[postgresql-hll](https://github.com/citusdata/postgresql-hll)** — ✅ Strong (for its job) · *third-party*. **HyperLogLog** as a type: fixed ~1.2 KB sketches answering `COUNT(DISTINCT ...)` within ~2% error, and — the actual superpower — sketches **union losslessly**, so per-day sketches roll up into per-month uniques *without re-scanning anything*. Pre-aggregate `hll_add_agg(hll_hash_bigint(user_id))` per day per dimension; dashboards become instant. The trade is explicit and bounded: approximate answers, in exchange for turning the one OLAP query Postgres is worst at into arithmetic. ([TopN](https://github.com/citusdata/postgresql-topn) from the same stable does heavy-hitters the same way.)

**The plain-Postgres baseline** — worth restating before adopting any of these: partitioning + BRIN + rollup materialized views + `work_mem`-fed parallel hash aggregation handles low-billions-of-rows reporting fine. The graduation criteria are: scans dominated by narrow column subsets over wide tables (columnar), repeated distinct-counting across dimensions (hll), or data already living in Parquet (pg_duckdb).

---

## 10. JSON, Graph & API Layers

**[pg_jsonschema](https://github.com/supabase/pg_jsonschema)** — 🟡 Situational · *third-party (Supabase, pgrx)*. JSON Schema validation as a CHECK constraint: `CHECK (jsonb_matches_schema('{"type":"object",...}', payload))`. If you accept semi-structured payloads, this moves "the shape is valid" from scattered application code into the one place that's guaranteed to see every write. Cheap, single-purpose, easy to remove — the best kind of extension. (PG17+'s `IS JSON` predicates and `JSON_TABLE` cover *structural* checks natively; full schema validation still needs this.)

**[Apache AGE](https://age.apache.org/)** — 🧪 Specialist · *third-party (Apache project)*. Property-graph database inside Postgres: **openCypher** queries (`MATCH (a:Person)-[:KNOWS*2..3]->(b)`) over graph data stored in Postgres tables, mixable with SQL. The honest framing: recursive CTEs handle "find ancestors/descendants" fine (see `ltree`, §5); AGE earns its place when queries are *genuinely graph-shaped* — variable-length paths, pattern matching across edge types — and you'd otherwise stand up Neo4j. As with all ASF projects, check release cadence against your Postgres major-version timeline.

**[pg_graphql](https://github.com/supabase/pg_graphql)** — 🧪 Specialist · *third-party (Supabase, pgrx)*. Reflects your schema (tables, FKs, RLS policies) into a GraphQL API resolved *inside* the database — one `graphql.resolve(...)` function call per request. Elegant where you're already in the Supabase model (RLS as the authorization layer); elsewhere, putting your API layer inside the database couples deploy cadence and failure domains that most teams prefer separate. Compare PostgREST (external process, same philosophy) before committing either way.

**[pgsql-http](https://github.com/pramsey/pgsql-http) / [pg_net](https://github.com/supabase/pg_net)** — ⚠️ Caution · *third-party*. HTTP from SQL — synchronous (`http_get(...)`) and asynchronous-via-background-worker respectively. Legitimate uses exist (webhooks on commit via `pg_net` from a trigger; calling an internal service during a migration), and the failure mode is exactly what you'd fear: **a backend doing network I/O holds its snapshot, its locks, and a connection slot for the duration** — a slow third-party API becomes *database* unavailability (vacuum horizon pinned, Ch. 6 of the internals guide). `pg_net`'s async design exists precisely to mitigate this; even so, the architectural default should be LISTEN/NOTIFY or an outbox table consumed by an application worker, with in-database HTTP reserved for genuinely-can't-otherwise cases.

---

## 11. Security & Encryption

**[`pgcrypto`](https://www.postgresql.org/docs/current/pgcrypto.html)** — ✅ Strong · *contrib, trusted*. Hashing (`digest`, `hmac`), password hashing done right (`crypt()` with `gen_salt('bf')` — bcrypt with cost factor, *not* a bare SHA), symmetric and public-key encryption (PGP functions: `pgp_sym_encrypt`/`pgp_pub_encrypt`), and `gen_random_bytes()`. The right tool for column-level encryption of moderate-sensitivity data and for secure token generation. The caveat to take seriously: encrypting *inside* the database means keys and plaintext transit the server — they appear in query strings unless you're careful (`log_statement` can log your keys!), in `pg_stat_statements` normalization edge cases, and in memory. For high-sensitivity data, prefer application-side encryption with a KMS so the database only ever sees ciphertext; `pgcrypto` is for when the database must be able to compute on/search the plaintext server-side.

```sql
-- password storage
INSERT INTO users(email, pw) VALUES ($1, crypt($2, gen_salt('bf', 12)));
SELECT (pw = crypt($2, pw)) AS ok FROM users WHERE email = $1;
```

**[`pgaudit`](https://github.com/pgaudit/pgaudit)** — ✅ Strong (see [§4](#4-observability--operations)). Listed here too because audit logging is a security control, not just ops.

**[PostgreSQL Anonymizer (`anon`)](https://postgresql-anonymizer.readthedocs.io/)** — 🟡 Situational · *third-party*. Declarative masking: annotate columns with masking rules (`SECURITY LABEL FOR anon ON COLUMN users.email IS 'MASKED WITH FUNCTION anon.fake_email()'`), then either *dynamically* mask for designated roles, *statically* rewrite a clone, or anonymize dumps. Invaluable for the universal problem of "developers need realistic non-prod data, legal says no PII leaves prod" — the rules live in the schema, so they survive schema evolution instead of rotting in a separate scrubbing script. Mind the semantic gap: masking that preserves *joins and distributions* well enough to debug with is design work the extension enables but can't do for you.

**[`pgsodium`](https://github.com/michelp/pgsodium) / [Supabase Vault](https://github.com/supabase/vault)** — 🧪 Specialist · *third-party*. Modern crypto (libsodium) bindings with a key-management twist: keys are referenced *by ID* and derived server-side, never appearing in SQL text (fixing pgcrypto's logging hazard), plus transparent column encryption via security labels; Vault packages this as a simple encrypted-secrets table. Strong design; deployment reality is "Supabase, or self-managed with care." Note pgsodium's maintenance has slowed — evaluate currency before new adoption.

**[`pg_tde`](https://github.com/percona/pg_tde)** — 🧪 Specialist · *third-party (Percona)*. Transparent data encryption — encrypting table/WAL files at the storage layer with external key management, the "encryption at rest with key custody" checkbox that disk-level encryption (which any cloud volume already has) doesn't tick for some compliance regimes. Self-managed Percona-distribution territory; on managed platforms the answer is the provider's KMS-integrated storage encryption instead.

**[`set_user`](https://github.com/pgaudit/set_user)** — 🧪 Specialist · *third-party*. Audited, controlled privilege escalation (`SELECT set_user('admin_role')` with logging and re-set) instead of handing out superuser or sharing the postgres account. Useful in tightly-governed self-managed fleets; managed platforms solve this with their own IAM.

**[`passwordcheck`](https://www.postgresql.org/docs/current/passwordcheck.html) / [`sslinfo`](https://www.postgresql.org/docs/current/sslinfo.html) / [`sepgsql`](https://www.postgresql.org/docs/current/sepgsql.html)** — 🧪 Specialist · *contrib*. Reject weak database passwords at `ALTER ROLE` time (only meaningful if you use password auth at all — prefer cert/IAM auth); expose client-certificate fields to SQL for cert-based policies; SELinux mandatory access control integration (government/defense niche, operationally serious).

The genuinely load-bearing security features, for perspective, are core: **roles, RLS (row-level security), SSL, and `search_path` hygiene**. Extensions decorate that foundation; they don't substitute for it. See the [Auth guide](AUTH_STUDY_GUIDE.md) for the application half.

---

## 12. Foreign Data Wrappers & Federation

Query other systems as if they were local tables — the SQL/MED standard, implemented per source. The universal mental model: a foreign table is **an API call wearing a table costume**; everything good and bad follows from that.

**[`postgres_fdw`](https://www.postgresql.org/docs/current/postgres-fdw.html)** — ✅ Strong · *contrib*. Query another PostgreSQL server. The planner is genuinely smart here: WHERE clauses, joins *between foreign tables on the same server*, sorts, and aggregates **push down** to the remote (run `EXPLAIN VERBOSE` and read the `Remote SQL` — the difference between shipping a filtered aggregate and dragging a table across the network is this one check); `use_remote_estimate` fetches remote stats for better plans; `fetch_size` and `batch_size` (batched inserts, PG14+) tune the wire. Standard production uses: cross-database queries during service splits, **gradual zero-downtime migrations** (foreign tables → logical replication → cutover), and read federation. Limits to respect: transactions across servers are *not* atomic (no 2PC by default), connections are per-backend (a 500-connection app fans out to the remote), and a remote outage becomes local query failure.

```sql
CREATE EXTENSION postgres_fdw;
CREATE SERVER remote FOREIGN DATA WRAPPER postgres_fdw OPTIONS (host 'db2', dbname 'sales');
CREATE USER MAPPING FOR CURRENT_USER SERVER remote OPTIONS (user 'reader', password '...');
IMPORT FOREIGN SCHEMA public LIMIT TO (orders) FROM SERVER remote INTO ext;
EXPLAIN (VERBOSE) SELECT count(*) FROM ext.orders WHERE region = 'EU';  -- read the Remote SQL
```

**[`file_fdw`](https://www.postgresql.org/docs/current/file-fdw.html)** — 🟡 Situational · *contrib*. CSV/text files (and program output) as tables — log ingestion and ETL staging on self-managed servers (managed platforms block it: filesystem access). For one-shot loads, `COPY` remains simpler.

**[`oracle_fdw`](https://github.com/laurenz/oracle_fdw) / [`mysql_fdw`](https://github.com/EnterpriseDB/mysql_fdw) / [`tds_fdw`](https://github.com/tds-fdw/tds_fdw) / [`mongo_fdw`](https://github.com/EnterpriseDB/mongo_fdw) / [`sqlite_fdw`](https://github.com/pgspider/sqlite_fdw)** — 🟡 Situational · *third-party*. Federate to Oracle, MySQL, SQL Server, MongoDB, SQLite. Production-viable for migration and integration; each adds client-driver dependencies (mostly self-managed; RDS notably ships oracle_fdw and mysql_fdw). Push-down sophistication varies sharply by wrapper — `EXPLAIN` before trusting any join.

**[Supabase `wrappers`](https://fdw.dev/)** — 🧪 Specialist · *third-party (pgrx)*. A modern Rust FDW framework with wrappers for Stripe, S3, ClickHouse, BigQuery, Firebase, and more. Compelling for "join my Stripe customers against my users table" analytics; treat external-API-backed foreign tables as latency-and-rate-limit-bearing (one careless `JOIN` = thousands of API calls), and pin them to read-only analytics roles.

**[Multicorn](https://github.com/pgsql-io/multicorn2)** — ⚠️ Caution · *third-party*. Write FDWs in Python. Unbeatable for prototyping a wrapper in an afternoon; per-row Python in the query path and untrusted-language requirements make it a prototyping tool, not a production data path.

> The caution that applies to every FDW: a foreign table *looks* local to every tool and teammate, and the planner's statistics about it are guesses. Always check `EXPLAIN (VERBOSE)` for push-down; a join that drags a remote table over the network before filtering is the canonical FDW catastrophe.

---

## 13. Scale-Out & Sharding: Citus

**[Citus](https://docs.citusdata.com/)** — 🧪 Specialist (transformative, but a commitment) · *third-party (Microsoft)*. Turns Postgres into a **distributed, horizontally-sharded** database: a coordinator routes queries to worker nodes holding shards of your tables. The model in four verbs: `create_distributed_table('events', 'tenant_id')` (rows hash-distributed by the **distribution column**), `create_reference_table('plans')` (small tables replicated to every worker so joins stay local), single-tenant queries route to one worker (full SQL, low latency), cross-tenant analytics fan out and parallelize (with SQL restrictions where operations would require cross-worker data movement). Multi-tenant SaaS is the sweet spot precisely because the tenant ID makes every transactional query single-shard.

```sql
CREATE EXTENSION citus;
SELECT create_distributed_table('events', 'tenant_id');
SELECT create_reference_table('plans');
```

Production reality check, sharper than the marketing: **the distribution column decides everything** — it must appear in unique constraints and most joins, picking it wrong means a re-distribution migration, and "we'll shard later" is precisely as painful as the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) says re-partitioning always is. Cross-shard transactions exist (2PC underneath — with its blocking windows; that's Ch. 9 of the [Distributed Algorithms guide](DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md) in production form) but you design to avoid them. Operationally you now run a *fleet* (coordinator HA, worker rebalancing via `citus_rebalance_start`, per-node everything from the rest of this guide). Managed as [Azure Cosmos DB for PostgreSQL](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/); elsewhere self-managed. The eternal advice stands: partition, replicate reads, and buy the bigger box first — **most teams never need Citus**, and the ones that do, know, because a number (write TPS, working set, tenant count) tells them.

---

## 14. Scheduling, Queues & Background Jobs

**[`pg_cron`](https://github.com/citusdata/pg_cron)** — ✅ Strong · *third-party, now broadly supported*. Cron-syntax job scheduling *inside* the database (a background worker wakes and runs SQL on schedule; jobs and run-history are tables you can query — `cron.job`, `cron.job_run_details`). The right tool for database-shaped maintenance: partition rotation, rollup refreshes, queue sweeping, `pg_amcheck` runs. Needs `shared_preload_libraries`; jobs run in one designated database (use `cron.schedule_in_database` for others); **jobs don't run on replicas — and don't follow a failover** unless your platform handles it, so HA setups need that question answered. Supported on RDS/Aurora, Cloud SQL, Azure, Supabase. Keep application-domain jobs (emails, billing) in application schedulers; in-DB cron is for jobs whose natural home is SQL.

```sql
SELECT cron.schedule('purge-sessions', '0 3 * * *',
  $$DELETE FROM sessions WHERE expires_at < now()$$);
SELECT jobid, status, return_message FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;
```

**[`pg_partman`](https://github.com/pgpartman/pg_partman)** — ✅ Strong · *third-party*. Automated partition lifecycle on top of native declarative partitioning: pre-creates future partitions (`premake`), detaches/drops aging ones per `retention`, manages a template table for per-partition settings, and runs via its background worker or a `pg_cron` call to `run_maintenance()`. This is the missing operational half of native partitioning — without it, someone's pager learns the hard way that nobody created next month's partition. Widely supported (RDS, Cloud SQL, Azure, Supabase). Design notes: choose partition size so the *count* stays in the low thousands (planning cost grows with partition count), and use `partition_data_proc` for migrating existing big tables in batches.

**[`pgmq`](https://github.com/pgmq/pgmq)** — 🟡 Situational · *third-party*. A message queue with SQS semantics — `send`, `read` with **visibility timeout** (invisible-not-deleted until acked or timeout, giving at-least-once delivery), `archive` instead of delete for auditability — implemented as partitioned tables with `FOR UPDATE SKIP LOCKED` underneath. Genuinely useful when you want "a queue" without operating Kafka/SQS *and* your volume is modest (thousands/sec territory, not hundreds of thousands): the killer feature is **transactional enqueue** — enqueue in the same transaction as the state change it announces, eliminating the dual-write problem that haunts app-level queues (the outbox pattern, pre-built). For high-throughput fan-out, durable replay, or cross-team contracts, a real broker still wins. The hand-rolled alternative (a jobs table + `SKIP LOCKED` — [queue recipe](ADVANCED_POSTGRES.md#16-worked-performance-recipes)) remains entirely respectable; pgmq is that pattern, packaged and maintained (now a community project under the pgmq org, post-Tembo).

**[`pgq`](https://github.com/pgq/pgq)** — 🧪 Specialist · *third-party*. Skype's venerable high-throughput queue (batched cursor-based consumption, rotating event tables). Predates and outperforms naive approaches; mostly of interest where it's already entrenched (Londiste lineage) — new builds usually pick pgmq's simpler model or a broker.

---

## 15. Procedural Languages, Dev Tools & Planner Tools

**[`plpgsql`](https://www.postgresql.org/docs/current/plpgsql.html)** — ⭐ Essential · *built-in*. Installed by default; the language of triggers and stored functions. Not optional — it's just there. (Style guidance for when logic belongs in it at all: data-adjacent invariants and set operations, yes; business workflows, usually no — see the [Advanced guide](ADVANCED_POSTGRES.md).)

**[`plpython3u`](https://www.postgresql.org/docs/current/plpython.html) / [`plperlu`](https://www.postgresql.org/docs/current/plperl.html) / [`plv8`](https://plv8.github.io/)** — ⚠️ Caution · *contrib / third-party*. Python, Perl, and JavaScript in the database. The `u` suffix means **untrusted**: full filesystem/network access as the postgres OS user, superuser-only to create, unavailable on managed platforms — a supply-chain and security surface that needs an affirmative justification. `plv8` (trusted, sandboxed V8) is the defensible one — genuinely useful for sharing validation logic between a JS application tier and triggers — though heavyweight to package (it embeds V8, which is why several platforms dropped it). Default: application logic lives in the application; in-DB languages are for genuine data-locality wins on set-oriented work.

**[`plrust`](https://github.com/tcdi/plrust)** — 🧪 Specialist · *third-party*. A *trusted* compiled language: Rust functions, compiled server-side with safety guarantees that let untrusted users write native-speed code (RDS ships it). Impressive engineering; niche adoption — evaluate maintenance pulse and your appetite for compile-on-CREATE-FUNCTION workflows.

**[`plpgsql_check`](https://github.com/okbob/plpgsql_check)** — ✅ Strong · *third-party*. The PL/pgSQL linter: finds wrong identifiers, type mismatches, unreachable code, missing `RETURN`s, and (with `performance_warnings`) implicit casts that kill index use — at check time instead of production runtime, because PL/pgSQL bodies are otherwise only fully validated when *executed*. Also does dependency analysis and profiling. If you have more than a handful of stored functions, this plus [`pgTAP`](https://pgtap.org/) below is your database CI.

**[`pldebugger`](https://github.com/EnterpriseDB/pldebugger) / [`plprofiler`](https://github.com/bigsql/plprofiler)** — 🟡 Situational · *third-party*. Step-debugging for PL/pgSQL (the engine behind pgAdmin's debugger: breakpoints, variable inspection) and line-level flame-graph profiling of stored code. The profiler especially earns its keep the day a 40-line function is mysteriously slow and `EXPLAIN` can't see inside it.

**[`pgTAP`](https://pgtap.org/)** — 🟡 Situational · *third-party*. Unit tests *in SQL* with TAP output: assert schema shape (`has_column`, `col_type_is`), function behavior (`results_eq`), permissions, and policies, runnable in CI via `pg_prove` against an ephemeral database. Worth it the moment your database carries meaningful logic (functions, triggers, RLS policies — *especially* RLS, which is security-critical and otherwise tested by hope). Migration tools' built-in checks cover existence; pgTAP covers behavior.

**[`pg_hint_plan`](https://github.com/ossc-db/pg_hint_plan)** — ⚠️ Caution · *third-party*. Oracle-style planner hints in comments (`/*+ IndexScan(orders idx_orders_cust) Leading(o c) */`). Postgres core has refused hints for decades on the argument that hints rot — they freeze today's correct decision against tomorrow's data; the project's own docs largely agree. Legitimate uses: pinning a plan during an emergency while you fix the real cause, and constraining genuinely unstable plans on the planner's known weak spots (correlated multi-join estimates — see the [internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md) Ch. 8 on error compounding). Every hint deserves a comment explaining the statistics failure it papers over, and a ticket to remove it. RDS and Cloud SQL ship it; that availability is a statement about enterprise demand, not best practice.

---

## 16. Replication & CDC

**[`pgoutput`](https://www.postgresql.org/docs/current/protocol-logical-replication.html)** — ⭐ Essential · *built-in*. The native logical-replication output plugin — what `CREATE PUBLICATION`/`CREATE SUBSCRIPTION` use, and what serious CDC tools (Debezium included) consume. Nothing to install; listed so you know the default answer is "no extension needed." Core logical replication keeps absorbing the ecosystem's features release by release (row filters and column lists in 15, parallel apply in 16, **failover slots in 17** — slots surviving promotion, historically the #1 operational hole). See [Replication & HA](ADVANCED_POSTGRES.md#11-replication--high-availability).

**[`wal2json`](https://github.com/eulerto/wal2json) / [`test_decoding`](https://www.postgresql.org/docs/current/test-decoding.html)** — 🟡 Situational · *third-party / contrib*. Logical-decoding output plugins emitting changes as JSON (or demo text). The right tool when you're hand-building a *small* CDC consumer — a webhook emitter, a cache invalidator — and want `SELECT * FROM pg_logical_slot_get_changes(...)` simplicity without speaking the binary pgoutput protocol. For serious pipelines, run [Debezium](https://debezium.io/) (external, not an extension) on native logical replication instead — it handles the hard 20%: initial snapshots, schema evolution, exactly-once-ish delivery, and **slot management**. Which is the operational note that applies to *everything* in this section: an unconsumed replication slot pins WAL forever — disk fills, eventually the server stops; monitor `pg_replication_slots.wal_status` and set `max_slot_wal_keep_size`. No CDC tool excuses you from that graph.

**[`pglogical`](https://github.com/2ndQuadrant/pglogical)** — 🧪 Specialist · *third-party (EDB)*. The extension that *was* logical replication before PG10, still ahead of core on a shrinking list: conflict handling for multi-master-ish topologies, sequence replication, fine-grained row/column routing on older versions. Its remaining killer app is **major-version upgrades with near-zero downtime** on platforms that support it for that purpose (replicate 13 → 17, cut over). For new architectures, exhaust native logical replication first; the gap closes every release.

**[`pg_failover_slots`](https://github.com/EnterpriseDB/pg_failover_slots)** — 🧪 Specialist · *third-party (EDB)*. Backports "logical slots survive failover" to PG ≤ 16 by syncing slot state to standbys. If you run logical consumers on an HA cluster below 17, this closes the gap where a failover silently kills your CDC pipeline; on 17+, use the native [failover slot support](https://www.postgresql.org/docs/current/logical-replication-failover.html) instead. A textbook example of the extension lifecycle: born to fill a core gap, obsoleted by core absorbing it — the happy ending for an extension.

---

## 17. Managed-Service Availability Matrix

The deciding factor for most teams. **Directional, not authoritative — verify against current provider docs** ([RDS](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html) · [Cloud SQL](https://cloud.google.com/sql/docs/postgres/extensions) · [Azure Flexible](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions) · [Supabase](https://supabase.com/docs/guides/database/extensions)). ✅ = supported, ⚠️ = partial/conditional, ❌ = not available.

| Extension | RDS / Aurora | Cloud SQL | Azure Flexible | Supabase |
|---|---|---|---|---|
| Contrib core (`pg_stat_statements`, `pg_trgm`, `citext`, `hstore`, `btree_gin/gist`, `pgcrypto`, `unaccent`, `postgres_fdw`, `tablefunc`, `fuzzystrmatch`, `amcheck`, `pg_prewarm`) | ✅ | ✅ | ✅ | ✅ |
| `auto_explain` | ✅ | ✅ | ✅ | ✅ |
| `pgaudit` | ✅ | ✅ | ✅ | ✅ |
| `pg_repack` | ✅ | ✅ | ✅ | ⚠️ |
| `hypopg` | ❌ | ✅ | ✅ | ✅ |
| `pg_cron` | ✅ | ✅ | ✅ | ✅ |
| `pg_partman` | ✅ | ✅ | ✅ | ✅ |
| `PostGIS` (+ pgRouting) | ✅ | ✅ | ✅ | ✅ |
| `pgvector` | ✅ | ✅ | ✅ | ✅ |
| `pg_search` (ParadeDB) | ❌ | ❌ | ❌ | ⚠️ (varies) |
| `TimescaleDB` | ❌ | ❌ | ⚠️ (Apache-2 subset) | ⚠️ (subset) |
| `Citus` | ❌ | ❌ | ✅ (Cosmos DB for PG) | ❌ |
| `pgroonga` | ❌ | ❌ | ❌ | ✅ |
| `anon` | ⚠️ | ❌ | ⚠️ | ❌ |
| `plv8` | ❌ | ⚠️ | ❌ | ✅ |
| `plpython3u` (untrusted) | ❌ | ❌ | ❌ | ❌ |
| `wal2json` | ✅ | ✅ | ✅ | ✅ |
| `pg_hint_plan` | ✅ | ✅ | ✅ | ❌ |
| `oracle_fdw` / `mysql_fdw` | ✅ | ❌ | ⚠️ | ❌ |
| `pgmq` | ❌ | ❌ | ❌ | ✅ |
| `pg_duckdb` / columnar AMs | ❌ | ❌ | ❌ | ❌ |

The pattern: **contrib and the canonical third-party set (PostGIS, pgvector, pg_cron, pgaudit, pg_partman, pg_repack) are available almost everywhere** — design freely around those. The friction concentrates in: TimescaleDB (licensing keeps the good parts off the hyperscalers), Citus (Azure-only as managed), the Rust analytics/search generation (pg_duckdb, ParadeDB — too new and too preload-hungry for conservative allow-lists), anything untrusted, and the long tail. Supabase runs the most adventurous allow-list (pgroonga, pgmq, pg_graphql, plv8); RDS the most enterprise-shaped one (oracle_fdw, pg_hint_plan, plrust).

---

## 18. Tier Summary & Decision Guide

### By verdict

- ⭐ **Essential (every prod DB):** `pg_stat_statements`, `plpgsql` (built-in), `pgoutput` (built-in).
- ✅ **Strong (reach for on need, production-proven):** `auto_explain`, `pgaudit`, `pg_repack`, `hypopg`, `amcheck`, `pgstattuple`+`pg_prewarm`(autoprewarm), `pg_trgm`, `btree_gin/gist`, `unaccent`, `PostGIS`, `pgvector`, `postgresql-hll`, `pgcrypto`, `postgres_fdw`, `pg_cron`, `pg_partman`, `plpgsql_check`.
- 🟡 **Situational:** `citext`, `ltree`, `intarray`/`cube`+`earthdistance`/`tablefunc`/`fuzzystrmatch`, `pg_buffercache`, the PoWA stack (`pg_wait_sampling`/`pg_stat_kcache`/`pg_qualstats`), `TimescaleDB`, `anon`, `pg_jsonschema`, `file_fdw`, the per-database FDWs, `pgmq`, `pgTAP`, `pldebugger`/`plprofiler`, `wal2json`.
- 🧪 **Specialist:** `Citus`, `pgvectorscale`, `pg_search`/ParadeDB, `VectorChord`, `pg_duckdb`, columnar AMs, `TopN`, `bloom`, `rum`, `pgroonga`, `pgRouting`/`h3-pg`/`pointcloud`/`MobilityDB`, `pgsodium`/Vault, `pg_tde`, `set_user`, `sepgsql`, Supabase `wrappers`, Apache AGE, `pg_graphql`, `pglogical`, `pg_failover_slots`, `pgq`, `plrust`, `pg_stat_monitor`, the WAL/page forensics kit, `pg_squeeze`, `pg_timeseries`.
- ⚠️ **Caution:** `hstore` (legacy → jsonb), `uuid-ossp` (→ built-ins), untrusted PLs (`plpython3u`/`plperlu`), `pg_hint_plan` (freeze-the-plan debt), in-DB HTTP (`pgsql-http`/`pg_net`), Multicorn-in-production, in-DB model inference (pgai/PostgresML) as architecture.

### Quick decision tree

```
Need monitoring?                 → pg_stat_statements + auto_explain  (always)
  ...and "what was it waiting on?" → pg_wait_sampling (PoWA stack)
Compliance/audit?                → pgaudit
Bloat without downtime?          → pg_repack  (pg_squeeze if triggers hurt)
Want to test an index cheaply?   → hypopg
Corruption paranoia (healthy)?   → amcheck weekly + checksums + pg_prewarm/autoprewarm
Fuzzy / substring search?        → pg_trgm (+ unaccent)
  ...relevance-ranked (BM25)?    → pg_search/ParadeDB   ...CJK? → pgroonga
Geospatial?                      → PostGIS  (routing → pgRouting; hex analytics → h3-pg)
Embeddings / RAG?                → pgvector  (50M+ vectors → pgvectorscale/VectorChord)
Time-series?                     → partitioning + BRIN + pg_partman + pg_cron first;
                                   TimescaleDB if you need compression/continuous aggs
                                   AND your platform has it
Analytics scans / COUNT DISTINCT?→ rollups + hll first; columnar AM / pg_duckdb at scale
Validate JSON payloads?          → pg_jsonschema
Graph-shaped queries?            → recursive CTEs / ltree first; Apache AGE if truly Cypher-shaped
In-DB scheduled jobs?            → pg_cron (+ pg_partman for partitions)
A queue without new infra?       → pgmq (or hand-rolled SKIP LOCKED)
Column encryption?               → pgcrypto (keys in app/KMS for high sensitivity)
Mask data for dev/test?          → anon
Query another database?          → postgres_fdw (read Remote SQL in EXPLAIN)
CDC / change streams?            → native logical replication (+ Debezium); wal2json for
                                   small hand-rolled consumers; monitor your slots
Test schema/functions/RLS in CI? → pgTAP + plpgsql_check
Single node truly maxed out?     → partition → read replicas → bigger box → THEN Citus
```

### The one rule that overrides the rest

**Check your platform's supported-extensions list before you design.** The best extension you can't install is worth nothing; a slightly-less-ideal one your managed service supports will save you a migration. Availability first, elegance second.

---

## Further Reading

- Companion guides: [PostgreSQL Feature Reference](POSTGRES.md) · [Advanced PostgreSQL](ADVANCED_POSTGRES.md) · [Database Internals](DATABASE_INTERNALS_STUDY_GUIDE.md) (how the extension APIs — index AMs, table AMs, hooks — actually work)
- [`pg_available_extensions`](https://www.postgresql.org/docs/current/view-pg-available-extensions.html) on your own server — the ground truth for what you can install
- The official [contrib module list](https://www.postgresql.org/docs/current/contrib.html) and [extension-authoring docs](https://www.postgresql.org/docs/current/extend-extensions.html)
- Registries: [PGXN](https://pgxn.org/) · [Trunk](https://pgt.dev/) · the [PGDG package repositories](https://www.postgresql.org/download/)
- Provider allow-lists: [RDS](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html) · [Cloud SQL](https://cloud.google.com/sql/docs/postgres/extensions) · [Azure](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions) · [Supabase](https://supabase.com/docs/guides/database/extensions)
- Project docs for the heavyweights before adopting: [PostGIS](https://postgis.net/documentation/) · [TimescaleDB](https://docs.timescale.com/) · [Citus](https://docs.citusdata.com/) · [pgvector](https://github.com/pgvector/pgvector#readme) · [ParadeDB](https://docs.paradedb.com/)

# Data Engineering Study Guide

A depth-first guide to what data engineers actually build. Assumes you know SQL and have written application code in at least one language. Each phase builds on the previous. The fundamentals (Phases 1–12) carry you from storage formats up through governance; the applied phases (13–14) walk through real project layouts, anti-patterns, cost recipes, and the anatomy of a production pipeline end to end.

> Data engineering is mostly *plumbing well-chosen building blocks*. Almost nobody writes a query optimizer or a streaming engine from scratch. Knowing what each component is for, how it composes, and where it fails is the job.

---

## Phase 1: Foundations

### 1.1 What Data Engineering Actually Is

A working definition: **build and operate the systems that move data from where it's produced to where it's used for decisions**. The "systems" part is broad — ingestion, storage, transformation, orchestration, modeling, quality, access control.

The three roles you'll see at most companies, and how they differ:

- **Software engineer** — writes the application code that *produces* the data. Owns OLTP databases (Postgres, MySQL).
- **Data engineer** — moves that data into analytics systems, transforms it, models it, owns the pipelines and the warehouse. Owns OLAP storage.
- **Analytics engineer / Analyst** — writes SQL on top of the modeled data. dbt blurred this boundary; "analytics engineering" is essentially "data engineer who only writes SQL transformations."
- **ML engineer / Data scientist** — consumes data engineering's output for models. Increasingly overlaps with DE on feature stores and online inference.

The job-to-be-done in one sentence: **make trustworthy data available to people and systems that need it, at the right freshness and the right cost**.

### 1.2 OLTP vs. OLAP

The single most important distinction in data engineering. Everything downstream follows from it.

| Aspect              | OLTP (transactions)              | OLAP (analytics)                       |
|---------------------|----------------------------------|----------------------------------------|
| Workload            | Short, indexed point reads/writes| Long scans, aggregations across rows   |
| Storage layout      | Row-oriented                     | Columnar                               |
| Indexing            | Heavy use of B-tree indexes      | Mostly scan-and-filter, sometimes zone maps |
| Consistency         | ACID, serializable               | Eventual or batch-consistent           |
| Schema design       | Normalized (3NF)                 | Denormalized (star, OBT, etc.)         |
| Examples            | Postgres, MySQL, SQL Server      | Snowflake, BigQuery, Redshift, Databricks |
| Sweet spot row count| Thousands of rows per query      | Millions to billions per query         |

You will move data from OLTP → OLAP constantly. The reason is structural: the access patterns are different enough that a single storage engine can't be excellent at both. (Modern systems like ClickHouse and DuckDB are trying to bridge this with HTAP / convergent designs, but the dichotomy still drives most architecture.)

### 1.3 Batch vs. Streaming vs. Micro-batch

- **Batch** — process bounded chunks of data on a schedule. "Run nightly at 2 AM, transform yesterday's data." Simple to reason about, cheap, the right default. Most analytics pipelines should start here.
- **Streaming** — process data record-by-record as it arrives. Continuous, low-latency, but operationally heavier (state management, exactly-once semantics, backpressure). Use when business value depends on freshness measured in seconds.
- **Micro-batch** — process small batches at high frequency (every minute or two). Spark Structured Streaming and dbt's incremental models live here. Often the right pragmatic middle ground.

A useful rule: **start with batch. Move to streaming when the latency requirement is concrete and quantified.** "Real-time" is rarely the actual requirement; "fresh enough by the morning" almost always is.

### 1.4 The Modern Data Stack vs. the Old ETL World

The "modern data stack" (MDS) emerged ~2018 and dominated DE by ~2022. The defining shift:

- **Old ETL**: extract → transform (in-flight, often in Python/Spark) → load. Tools like Informatica, Talend, custom shell scripts.
- **Modern ELT**: extract → load (raw, untransformed) into the warehouse → transform *inside* the warehouse with SQL. Warehouse compute got cheap; storage got cheap; SQL got better; transforming in-place is faster and easier to debug.

The canonical MDS stack:
- **Ingest** — Fivetran / Airbyte (SaaS sources), Kafka / Debezium (CDC), or custom for niche sources.
- **Store** — Snowflake, BigQuery, Databricks, Redshift (warehouses), or S3 + Iceberg/Delta (lakehouse).
- **Transform** — dbt for SQL transformations.
- **Orchestrate** — Airflow, Dagster, or Prefect.
- **Serve** — BI tools (Looker, Mode, Metabase, Tableau, Hex), reverse ETL (Hightouch, Census), feature stores (Tecton, Feast).
- **Govern / observe** — data catalogs (Atlan, Unity, OpenMetadata), data quality (dbt tests, Great Expectations, Soda, Monte Carlo).

We're now in a "post-MDS" phase where the conversation has shifted to the lakehouse + open table formats (Phase 4) eating proprietary warehouse storage, and to operationalizing AI/ML workloads alongside analytics.

### 1.5 The Data Engineer's Maturity Curve

A useful internal model for where any data org sits:

1. **Spreadsheets and ad-hoc queries.** Numbers don't match across reports. Trust is low.
2. **Centralized warehouse + dashboards.** Single source of truth for top-line metrics. Most numbers agree.
3. **Modeled layer (Kimball or similar) + tests.** Dimensional models documented; tests catch breakages; lineage is visible.
4. **Streaming + operational analytics.** Pipelines power product features, not just dashboards.
5. **Data products + contracts + automated governance.** Producers commit to schemas; consumers consume against versioned interfaces.

Most companies live in 2 or 3. Skipping levels rarely works.

References: [Fundamentals of Data Engineering (Reis & Housley)](https://www.oreilly.com/library/view/fundamentals-of-data/9781098108298/), [The Modern Data Stack — a16z](https://a16z.com/emerging-architectures-for-modern-data-infrastructure/)

---

## Phase 2: Storage Formats

How bytes are laid out on disk determines what's fast and what's expensive. The single highest-leverage thing to internalize early.

### 2.1 Row vs. Columnar

**Row storage** keeps all values of a single record together. Optimal when you read whole rows (OLTP).

**Columnar storage** keeps all values of a single column together. Optimal when you read a few columns out of many (OLAP) — you read only the columns you need from disk, skip the rest entirely.

A query like `SELECT AVG(price) FROM orders WHERE date = '2026-05-01'` on a 200-column `orders` table touches 2 columns. Row storage reads ~all 200 from disk (since they're interleaved); columnar storage reads exactly 2. Often a 50–100× I/O reduction.

Columnar also compresses dramatically better, because values in the same column tend to be similar (same type, often similar magnitude, often repetitive). Dictionary encoding, RLE, delta encoding, bit-packing all become viable.

### 2.2 Parquet

The default analytics file format. Apache Parquet is columnar, self-describing, and designed for object stores.

**Anatomy** of a Parquet file:
- **Row groups** — large horizontal partitions (typically 128 MB or 512 MB of raw data). Each row group contains column chunks.
- **Column chunks** — all values for one column within a row group, stored contiguously.
- **Pages** — the unit of compression and encoding within a column chunk (typically 1 MB).
- **Footer** — metadata: schema, row group offsets, column statistics (min/max/null count per column chunk).

The footer is what makes Parquet powerful. A query engine reads the footer, sees the min/max for `date` in each row group, and can skip entire row groups whose ranges don't match the predicate. This is **predicate pushdown** — the killer feature.

**Encodings** Parquet uses, automatically:
- **Dictionary encoding** — replace repeated values with small dictionary IDs. Devastatingly effective on low-cardinality columns.
- **Run-length encoding (RLE)** — replace runs of the same value with `(value, count)`.
- **Delta encoding** — store differences between consecutive values.
- **Bit-packing** — pack small integers into fewer bits.

**Compression** sits on top: SNAPPY (fast, decent ratio — the default), ZSTD (better ratio, slightly slower), GZIP (slow, legacy).

**Tuning levers worth knowing**:
- Row-group size: smaller = better filtering granularity, more metadata overhead. Default 128 MB is usually right; consider 512 MB for cold storage.
- File size: aim for **100 MB – 1 GB per file**. Smaller wastes object-store list/get overhead ("small files problem"); larger reduces parallelism.
- Column ordering in the schema doesn't matter for storage but does for some readers.

References: [Parquet documentation](https://parquet.apache.org/docs/), [Inside Parquet (Influxdata)](https://www.influxdata.com/blog/apache-parquet-explained/)

### 2.3 The Other Formats

- **ORC** (Optimized Row Columnar) — Parquet's main competitor, originally from Hive. Slight differences in metadata, stripe vs. row group naming. In 2026, Parquet has won the open-format war; ORC remains in legacy Hive/Hortonworks shops.
- **Avro** — *row*-oriented, binary, with a schema stored alongside the data. Excellent for *streaming* and for messages on a Kafka topic where you want compact serialization and forward/backward schema compatibility. Bad for analytics scans (no column pruning).
- **JSON / CSV** — fine for human-readable interchange and small data. Terrible at scale: no schema (CSV), redundant text encoding (JSON), no column pruning, no predicate pushdown, expensive to parse. If you find yourself writing analytics queries against multi-GB JSON files, convert to Parquet first.
- **Arrow** — not a file format, but the **in-memory** columnar standard. Parquet's the format on disk; Arrow's the format in RAM. Polars, DuckDB, pandas 2.0, Spark, BigQuery all speak Arrow. Zero-copy data exchange between processes/languages.

### 2.4 Partitioning and File Layout

How files are laid out in your data lake is as important as the format.

- **Partitioning** = splitting a logical table into directories by column value: `s3://bucket/orders/year=2026/month=05/day=01/file.parquet`. A scan filtering `year=2026 AND month=05` reads only that directory.
- **Choose the right partition key**: high enough cardinality to be useful, low enough that you don't have millions of tiny partitions. `date` is almost always right. `user_id` is almost always wrong.
- **The small-files problem**: many tiny files = many object-store HEAD/GET calls = catastrophic query latency. Tools like Spark `coalesce`, Delta `OPTIMIZE`, Iceberg compaction merge small files.
- **Z-ordering / clustering** (Delta, BigQuery, Snowflake) — sort data within a partition by additional columns so range filters on those columns also prune. The modern alternative to second-level partitioning.

A useful smell test: if your "small files problem" gets worse over time, you don't have a compaction story. Add one.

```quiz
Q: `SELECT AVG(price) FROM orders WHERE date = ...` on a 200-column table is ~50–100× cheaper on columnar storage. Why?
- [x] Columnar stores each column contiguously, so the engine reads only the 2 columns touched and skips the other 198 — row storage interleaves all 200, forcing them all off disk
- [ ] Columnar storage indexes every column by default
- [ ] Columnar compresses queries, not data
- [ ] Row storage can't compute averages
> The same locality also makes columnar compress far better (similar values adjacent → dictionary/RLE/delta encoding). That's the highest-leverage storage fact: layout determines what's cheap.

Q: What makes Parquet's footer so powerful for query performance?
- [x] It holds per-row-group column statistics (min/max/null counts), so an engine can skip entire row groups whose ranges can't match the predicate — predicate pushdown
- [ ] It compresses the whole file with ZSTD
- [ ] It stores a B-tree index over every column
- [ ] It caches query results
> Reading the footer first lets the engine prune most of the file before touching data pages. Row-group and file sizing tune the filtering granularity (smaller = finer pruning, more metadata overhead).

Q: When is Avro the right format, despite being bad for analytics scans?
- [x] For streaming / Kafka messages — it's row-oriented, compact binary, carries its schema for forward/backward compatibility; it just lacks the column pruning analytics needs
- [ ] For large analytical fact tables
- [ ] For human-readable config files
- [ ] Whenever you'd otherwise use Parquet
> Row vs columnar is workload-shaped: Avro for record-at-a-time messaging with schema evolution, Parquet for column-pruned scans. Arrow is the in-memory columnar standard that the engines share.

Q: Why is `user_id` almost always the wrong data-lake partition key while `date` is almost always right?
- [x] High-cardinality keys like user_id produce millions of tiny partitions (the small-files problem — catastrophic object-store overhead); date has enough cardinality to prune usefully without exploding the partition count
- [ ] user_id can't be used in WHERE clauses
- [ ] date partitions compress better
- [ ] Partition keys must be integers
> Partition cardinality is the lever: high enough to prune, low enough to avoid tiny-file proliferation. Z-ordering/clustering handles secondary range filters without a second partition level.
```

---

## Phase 3: Warehouses, Lakes, and Lakehouses

### 3.1 The MPP (Massively Parallel Processing) Architecture

Modern data warehouses are all built on the same fundamental pattern:

- **Coordinator / Leader node** — receives the query, plans it, distributes work.
- **Worker / Compute nodes** — execute work in parallel on partitioned data.
- **Shuffle** — data is redistributed between workers when needed (joins, group-bys with high-cardinality keys).
- **Columnar storage + vectorized execution** — operate on batches of column values in SIMD-friendly loops.

The differentiators between products mostly come down to:
- **Storage and compute separation** (Snowflake popularized this; everyone else followed).
- **Caching strategy** (which layers cache, where).
- **Cluster sizing model** (fixed vs. autoscaling vs. per-query).
- **Optimizer quality** (more important than people realize).

### 3.2 The Players in 2026

- **Snowflake** — separation of storage and compute, multi-cluster warehouses for concurrency, per-second billing. Strong default for most companies. Strengths: ergonomics, time travel, zero-copy cloning. Weaknesses: opaque pricing at scale, vendor lock-in (mitigated now by Iceberg support).
- **BigQuery** — fully serverless. No clusters to size. Charged per byte scanned (on-demand) or per slot-hour (capacity). Strengths: zero ops, BigQuery ML, integrated GIS. Weaknesses: pricing surprises if you're sloppy with `SELECT *`, weaker streaming story than its peers.
- **Databricks** (SQL + Lakehouse) — built on Spark and Delta Lake. Strengths: best ML/AI integration, lakehouse-native (your data stays in your S3/ADLS), Photon engine is fast. Weaknesses: more operational surface than Snowflake/BQ, pricing is complicated.
- **Redshift** — AWS's warehouse. Two flavors: provisioned (legacy, RA3 nodes) and serverless (modern). Strengths: AWS integration. Weaknesses: lags Snowflake/BQ on ergonomics and optimizer quality; AWS is investing more in Athena + Iceberg.
- **ClickHouse** — open-source columnar database, screamingly fast for narrow analytics queries. Increasingly used as the warehouse for product analytics, observability, and real-time dashboards. Strengths: latency (sub-second on large tables), cost. Weaknesses: requires more ops know-how than serverless competitors; less mature optimizer for complex joins.
- **DuckDB** — the "SQLite of analytics." In-process, single-node, embeds in Python/R/Node. Not a warehouse — but increasingly the right tool for "I have a Parquet file and I want to query it without spinning up infrastructure." See Phase 8.

### 3.3 Storage and Compute Separation

The defining architectural shift of the 2010s. Old MPP (Teradata, Redshift legacy) coupled storage to compute: storage lived on the compute nodes' disks; resizing the cluster meant reshuffling all the data. New MPP (Snowflake, Databricks, BigQuery, modern Redshift) stores data in object storage (S3/GCS/ADLS) and treats compute as ephemeral.

Consequences:
- Compute clusters can scale up/down independently of data size.
- Multiple compute clusters can read the same data simultaneously without contention.
- You pay for storage cheaply (S3 prices) and pay for compute only when you query.
- Zero-copy operations (Snowflake's `CLONE`, BigQuery's snapshots) become trivial.

This is the architectural foundation that lakehouses build on (Phase 4).

### 3.4 Choosing Between Them

A pragmatic decision tree:

- **Already heavy AWS, mostly SQL, want zero ops** → Snowflake (or Redshift Serverless if vendor lock-in is a strong concern).
- **Already heavy GCP, want zero ops** → BigQuery.
- **Heavy ML/AI workloads, want one platform for ETL + ML + serving** → Databricks.
- **Tight latency requirements (sub-second), product analytics workload** → ClickHouse.
- **Small or medium data, want to avoid infra entirely** → DuckDB + object storage, no warehouse at all.
- **Long-term vendor neutrality matters more than ergonomics** → lakehouse architecture (Iceberg/Delta on S3) with a query engine of choice (Trino, Spark, Athena, even Snowflake reading Iceberg).

References: [Snowflake architecture](https://docs.snowflake.com/en/user-guide/intro-key-concepts), [BigQuery internals](https://cloud.google.com/blog/products/bigquery/bigquery-under-the-hood), [Databricks Lakehouse paper](https://www.cidrdb.org/cidr2021/papers/cidr2021_paper17.pdf)

---

## Phase 4: Open Table Formats and the Lakehouse

### 4.1 What an "Open Table Format" Is

Parquet is a *file* format. A *table* format is the layer above: a way to make many Parquet files behave like a single ACID-transactional table, with schema evolution, partitioning, time travel, and concurrent writers.

Why this matters: it decouples *storage* from the *query engine*. You can store your data in Iceberg on S3, and query it with Snowflake, Trino, Spark, Athena, DuckDB, and BigQuery — sometimes all in the same week. This is the lakehouse promise: warehouse-grade semantics on commodity object storage, with engine choice.

### 4.2 The Three Contenders

- **Apache Iceberg** — originated at Netflix, now broadly adopted (Snowflake, BigQuery, AWS Athena, Trino, Spark all read/write it; even Databricks committed to it after acquiring Tabular). Schema evolution and partitioning evolution without rewriting data. The default winner of the table format wars.
- **Delta Lake** — originated at Databricks. Strongest on Databricks itself. Open-sourced under Linux Foundation. Effectively equivalent feature set to Iceberg for most workloads. Was the leader; now neck-and-neck with Iceberg.
- **Apache Hudi** — originated at Uber. Optimized for *upsert-heavy* workloads (CDC). Lost mindshare to Iceberg/Delta, but still strong in CDC-heavy lakehouses.

By 2026 the practical question is mostly "Iceberg or Delta?" and the answer is usually Iceberg for new builds outside Databricks, Delta inside Databricks.

### 4.3 What These Formats Give You Over Raw Parquet

- **ACID transactions** — concurrent writers don't corrupt each other; readers see consistent snapshots.
- **Schema evolution** — add, drop, rename columns; widen types; the format tracks the history.
- **Partition evolution** (Iceberg) — change your partitioning scheme without rewriting historical data. Old partitions stay as they were; new data uses the new scheme.
- **Time travel** — `SELECT * FROM orders FOR VERSION AS OF 12345` or `FOR TIMESTAMP AS OF '2026-05-01'`. Useful for debugging and (sparingly) for recovery.
- **Hidden partitioning** (Iceberg) — query with `WHERE date = ...` and the engine figures out which partitions to read, even if the partition column is derived (`date(ts)`).
- **Compaction / OPTIMIZE** — periodic background process that merges small files, sorts data, and rewrites manifests. Without this, lakehouses degrade.

### 4.4 Lakehouse Operational Concerns

- **Catalog choice** — the catalog is the metadata service that tells engines about your tables. AWS Glue, Unity Catalog (Databricks), Polaris (Snowflake's open catalog), Nessie (Git-like branching), Hive Metastore (legacy). REST catalog spec is increasingly the lingua franca.
- **Compaction is not optional** — schedule `OPTIMIZE` / `rewrite_data_files` regularly. Without it, query performance decays linearly with write frequency.
- **Vacuum is not optional** — old snapshots and orphaned files accumulate. Schedule `VACUUM` (Delta) or `expire_snapshots` (Iceberg) with a retention window long enough for time-travel recovery but short enough to control storage cost.
- **Concurrent writes** require optimistic concurrency reconciliation; conflicts manifest as commit failures that your jobs must retry.

References: [Apache Iceberg spec](https://iceberg.apache.org/spec/), [Delta Lake protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md), ["What is a lakehouse?" (Databricks)](https://www.databricks.com/glossary/data-lakehouse)

```quiz
Q: What does an open *table* format (Iceberg/Delta) add on top of Parquet *files*?
- [x] It makes many Parquet files behave as one ACID-transactional table — schema/partition evolution, time travel, concurrent writers — and decouples storage from the query engine
- [ ] A faster compression codec than Parquet
- [ ] An in-memory columnar layout
- [ ] Automatic indexing of every column
> The lakehouse promise: warehouse-grade semantics on commodity object storage with engine choice (Snowflake, Trino, Spark, Athena, DuckDB all reading the same Iceberg tables).

Q: Why does the guide insist "compaction is not optional" on a lakehouse?
- [x] Frequent writes accumulate small files and manifest bloat; without scheduled OPTIMIZE/rewrite_data_files, query performance decays roughly linearly with write frequency
- [ ] Compaction is required for ACID transactions
- [ ] Without it, time travel breaks
- [ ] It's only needed for Delta, not Iceberg
> Vacuum/expire_snapshots is the paired chore (old snapshots and orphaned files accumulate). Set a retention window long enough for time-travel recovery, short enough to control storage cost.

Q: What's the modern ELT shift away from old-world ETL, and why did it happen?
- [x] Load raw into the warehouse first, then transform in-place with SQL — because warehouse storage and compute got cheap, making in-warehouse transformation faster and easier to debug than in-flight transformation
- [ ] Transform before loading to save storage
- [ ] ELT eliminates the need for orchestration
- [ ] ELT only works on streaming data
> The cheap-compute/cheap-storage economics are what made "transform inside the warehouse with dbt" beat Informatica-style in-flight pipelines. Storage/compute separation (Snowflake's shift) is the architectural foundation under it.
```

---

## Phase 5: Ingestion

Moving data *into* your analytics system. The unglamorous half of the job, and the part that breaks most often.

### 5.1 The Three Sources

- **Operational databases** (Postgres, MySQL, SQL Server, Mongo) — your own application's OLTP store. Highest-value, most operationally sensitive.
- **SaaS sources** (Salesforce, HubSpot, Stripe, Zendesk, etc.) — external APIs you don't control.
- **Event streams** (clickstream, server logs, IoT) — high-volume, often streaming.

### 5.2 Database Ingestion: CDC vs. Snapshot

- **Snapshot loading** — periodically dump the table and reload. Simple. Acceptable for small tables (< 1M rows). Doesn't capture deletes. Doesn't capture intermediate states.
- **Incremental snapshot** — query for `WHERE updated_at > <last_load>`. Better. Misses deletes. Requires a reliable `updated_at` on every row, with index on it.
- **Change Data Capture (CDC)** — read the database's *write-ahead log* (Postgres WAL, MySQL binlog, SQL Server CDC). Captures every change including deletes, in order, with low impact on the source database. The right answer at scale.

The dominant tool: **Debezium** (open-source, log-based CDC for major databases, produces a Kafka topic per source table). Commercial alternatives: Fivetran HVR, Striim, AWS DMS.

CDC pitfalls to know:
- **Replication slots can fill disks** — on Postgres, an inactive replication slot causes WAL to accumulate forever. Monitor `pg_replication_slots.active` and `pg_wal` size.
- **Schema changes are subtle** — DDL on the source needs a downstream story. Modern CDC tools handle ADD COLUMN; DROP COLUMN and type changes are harder.
- **Initial snapshot is its own beast** — for terabyte-scale tables, the initial snapshot can take days. Incremental snapshot (chunked, with watermarks) is the current best practice (Netflix's [DBLog](https://netflixtechblog.com/dblog-a-generic-change-data-capture-framework-69351fb9099b)).

### 5.3 SaaS Ingestion: Fivetran, Airbyte, Stitch

For SaaS sources, you're not building connectors yourself. Use a managed service:

- **Fivetran** — most mature, most expensive. Set-and-forget. Strong choice if you can afford it.
- **Airbyte** — open-source connectors with a managed cloud offering. Less mature than Fivetran but improving rapidly; self-hosting is feasible.
- **Stitch** — older, owned by Talend. Declining.
- **Hightouch + reverse ETL** — note: reverse ETL is the *output* side (warehouse → SaaS), not ingestion.

The economics: Fivetran-class tools charge per "monthly active row" (MAR) or similar. At small scale: cheap. At large scale: expensive enough that engineering a custom Airbyte deployment makes sense. The crossover is usually somewhere around $100K/year of Fivetran spend.

### 5.4 Event Streams: Kafka as the Backbone

Almost every modern data platform funnels event data through **Kafka** (or a Kafka-protocol-compatible alternative: Redpanda, Confluent Cloud, AWS MSK). For the streaming details, see Phase 9; for ingestion purposes the patterns are:

- **Producer → Kafka topic → Consumer that writes to warehouse / lakehouse.**
- Use **Avro** (with a Schema Registry) for event payloads at scale. JSON is fine to start; switch when the cost of schema drift or payload size becomes painful.
- **Sink connectors** (Kafka Connect S3, Iceberg, Snowflake, BigQuery sinks) handle the warehouse-write half declaratively. Worth using before writing custom consumers.
- **Exactly-once** end-to-end requires care: producer idempotency, transactional writes, and a sink that supports idempotent commits (Iceberg, Snowflake Snowpipe Streaming).

### 5.5 The Bronze / Silver / Gold Convention

A widely-used naming convention for ingestion + transformation layers (popularized by Databricks; the names are arbitrary but the structure is the right one):

- **Bronze** (raw) — exact copy of the source. No business logic. Preserved for replay/reprocessing. Often immutable, append-only.
- **Silver** (cleaned / conformed) — deduplicated, type-corrected, joined to references. Still close to source structure.
- **Gold** (modeled / mart) — business-facing dimensional models, aggregates, the tables analysts query.

dbt naming convention uses `staging` → `intermediate` → `marts` for the same layers; pick one and stick to it.

References: [Debezium documentation](https://debezium.io/documentation/), [Fivetran competitive analysis](https://www.fivetran.com/blog), ["The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying)

---

## Phase 6: Transformation with dbt

dbt (data build tool) is the dominant SQL transformation framework. It does one thing well: take a directory of SQL files, work out the dependency graph, materialize them in the right order, and test them.

### 6.1 The Core Concepts

- **Model** — a SQL file in `models/`. Each model is a `SELECT` statement. dbt wraps it in `CREATE TABLE AS` (or `CREATE VIEW AS`, etc.) at run time. Each model produces one table or view in your warehouse.
- **Source** — declared input table that dbt didn't create (e.g., a raw table from Fivetran). Declared in `sources.yml`. Referenced as `{{ source('schema_name', 'table_name') }}`.
- **Ref** — reference to another dbt model. Referenced as `{{ ref('model_name') }}`. dbt uses these refs to build the DAG.
- **Seed** — a CSV file in `seeds/` that dbt loads into a table. Use for small reference data (country codes, lookup tables).
- **Snapshot** — captures slowly-changing dimensions. dbt tracks changes over time.
- **Test** — assertion on a model (e.g., `not_null`, `unique`, custom SQL).
- **Macro** — Jinja-templated SQL function. Reusable logic.
- **Package** — a dbt project you import as a dependency.

### 6.2 Materializations

How a model is *physically* persisted. Choose per-model based on size, freshness, and query patterns.

- **view** (default) — a database view. Cheap to build, expensive to query (re-runs the SQL every time). Right for small, infrequently-queried models.
- **table** — full table replacement on each run. Right for medium-size models with frequent queries.
- **incremental** — append (or merge) only new/changed rows. Right for large event tables. Requires careful thinking about idempotency.
- **ephemeral** — inlined as a CTE in downstream models. No persistence. Right for trivial transformations used in one place.
- **materialized_view** — supported on Snowflake, BigQuery, Redshift, Postgres; the warehouse maintains it automatically. Right for low-latency aggregations of source data that updates frequently.

### 6.3 Incremental Models

The most operationally important materialization, and the one most often misconfigured.

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    on_schema_change='append_new_columns'
) }}

SELECT * FROM {{ source('raw', 'orders') }}

{% if is_incremental() %}
  WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

Key choices:

- **Incremental strategy**:
  - `append` — just `INSERT` new rows. Cheapest. Right for immutable event streams.
  - `merge` — `MERGE` on `unique_key`. Right when records can update.
  - `delete+insert` — delete matching keys then insert. Workaround for warehouses without `MERGE`.
  - `insert_overwrite` — overwrite specific partitions wholesale. Excellent for BigQuery/Spark partitioned tables; idempotent reruns.
- **Watermark** — what counts as "new"? `updated_at > MAX(updated_at)`? Date partition? Whatever you pick, ensure the source actually maintains it monotonically.
- **Late-arriving data** — if source rows can arrive with an `updated_at` earlier than `MAX(updated_at)`, your incremental will miss them. Either widen the watermark window or use `insert_overwrite` of recent partitions.
- **`is_incremental()`** — true on every run *except* the first (full refresh). Always include the watermark filter inside this conditional.

### 6.4 Snapshots (Slowly Changing Dimensions)

dbt snapshots implement SCD Type 2 (track history) declaratively:

```sql
{% snapshot orders_snapshot %}
{{ config(
    target_database='analytics',
    target_schema='snapshots',
    unique_key='order_id',
    strategy='timestamp',
    updated_at='updated_at',
) }}

SELECT * FROM {{ source('raw', 'orders') }}
{% endsnapshot %}
```

Each `dbt snapshot` run adds rows whose `updated_at` has changed since last run, marking the previous version with `dbt_valid_to = now()`. The result is a time-versioned history of the source table.

Strategies: `timestamp` (use a column that increases on update) or `check` (compare specific columns).

### 6.5 Testing

```yaml
# models/marts/orders.yml
models:
  - name: orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: customer_id
        tests:
          - relationships:
              to: ref('customers')
              field: customer_id
      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'shipped', 'cancelled', 'returned']
```

Built-in tests cover ~80% of what you want. For the other 20%, write **singular tests** (a `.sql` file that returns failing rows) or **generic tests** (parameterized macros). The `dbt-utils` and `dbt-expectations` packages add dozens of common assertions.

Run tests as part of every pipeline run. Failed tests should block downstream models or surface clearly to oncall.

### 6.6 Documentation and Lineage

dbt generates a documentation site from your project: every model, every column, descriptions you wrote, and **the dependency DAG**. `dbt docs generate && dbt docs serve`.

The DAG is the most underused feature in DE. When something breaks, click upstream. When something changes, see what's downstream. Make the docs site easily accessible to analysts.

### 6.7 The Footguns

- **`SELECT *` from `ref()`** in transformations — surface schema drift will cascade unexpectedly. Be explicit, especially in mart-layer models.
- **Full-refresh assumptions** — incremental models that don't produce the same output on full-refresh as on incremental are bugs waiting to happen. Test both.
- **Jinja-in-SQL madness** — Jinja is powerful; over-using macros makes SQL unreadable. Reach for it last, not first.
- **Slow `WHERE` clauses with subqueries** — `WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})` runs a scan on `{{ this }}` per run. Often fine; for large tables, precompute the max in a variable.
- **Not pinning dbt-core / adapter versions** — auto-upgrades have broken production. Pin in `requirements.txt`.

References: [dbt documentation](https://docs.getdbt.com/), [dbt best practices guide](https://docs.getdbt.com/best-practices), [Locally Optimistic — How we structure our dbt projects](https://www.locallyoptimistic.com/post/how-we-structure-our-dbt-projects/)

```quiz
Q: How does dbt build the dependency DAG that orders model execution?
- [x] From `{{ ref('model') }}` and `{{ source(...) }}` calls — each ref is an edge, so dbt materializes models in topological order
- [ ] From the alphabetical order of file names
- [ ] From a manually maintained dependency list
- [ ] From the warehouse's foreign keys
> ref() is both how you reference another model's output and how dbt learns the graph. That DAG also drives the docs site, the most underused feature: click upstream when something breaks, downstream to see blast radius.

Q: An incremental model's source can receive rows with `updated_at` *earlier* than the current MAX. What breaks, and what's a fix?
- [x] Late-arriving data gets skipped by `WHERE updated_at > MAX(updated_at)`; widen the watermark window or use insert_overwrite of recent partitions
- [ ] The model crashes on the next run
- [ ] Duplicate rows are inserted
- [ ] Nothing — MERGE handles it automatically
> The watermark must match the source's actual update behavior. The deeper rule: an incremental model must produce the same output on full-refresh as incrementally, or it's a latent bug — test both.

Q: Which incremental strategy fits an immutable event stream versus records that can update?
- [x] append (just INSERT) for immutable events — cheapest; merge (MERGE on unique_key) when records can change
- [ ] merge for everything, always
- [ ] delete+insert for immutable events
- [ ] view materialization for both
> insert_overwrite (wholesale partition replace) is the idempotent-rerun favorite on BigQuery/Spark. The strategy choice is about correctness under reruns, not just cost.

Q: dbt snapshots implement which slowly-changing-dimension pattern, and how?
- [x] SCD Type 2 — each run adds rows whose tracked column changed, stamping the prior version's dbt_valid_to, producing a time-versioned history
- [ ] SCD Type 1 — overwriting old values
- [ ] SCD Type 3 — keeping one previous value in a column
- [ ] No SCD support; you write it by hand
> "What was X on date D?" is answerable only with Type 2 history. Snapshots give it declaratively via timestamp or check strategies — the right default when historical accuracy matters.
```

---

## Phase 7: Orchestration

You have transformations. You need to run them on a schedule, in dependency order, with retries, alerts, and backfills. That's orchestration.

### 7.1 The Three Frameworks

The DE world is currently torn between three orchestrators. Each has a real personality.

**Apache Airflow** — the incumbent. Originally from Airbnb (2014), now an Apache project. Defines pipelines as Python DAGs of *tasks*. Massive plugin ecosystem (providers for every cloud service). Battle-tested, ubiquitous, well-known by hiring managers.
- *Strengths*: every connector you can name, biggest community, mature operationally.
- *Weaknesses*: pipelines are tasks, not data — Airflow doesn't know what tasks *produce* or *consume*. Local development is awkward. The scheduler is historically a sore spot (improving in Airflow 2 / 3).

**Dagster** — the modern challenger. Pipelines are defined around *assets* (the data they produce), not tasks (the operations). Strong typing, integrated lineage, much better local dev story.
- *Strengths*: asset-based mental model matches how DE actually thinks; local dev with hot-reload; cleaner UI; declarative dependencies via `@asset` decorators.
- *Weaknesses*: smaller community than Airflow, fewer turnkey integrations.

**Prefect** — the third option. Started as a "modern Airflow" (Prefect 1), pivoted to a more flexible "orchestration of any Python function" model (Prefect 2/3). Strong remote-execution story.
- *Strengths*: Python-native, low ceremony, good for "I want to schedule a Python function" without DAG ceremony.
- *Weaknesses*: less opinionated about data; can lead to less-structured pipelines if you're not disciplined.

Honest recommendation for new projects in 2026: **Dagster** if you're greenfield and have a small-to-medium team. **Airflow** if your team already knows it, or if you need a specific Airflow provider that the others lack. **Prefect** for teams who treat orchestration as "scheduled Python functions" rather than as a data platform.

### 7.2 Core Concepts (Across All Three)

- **DAG / Job / Flow** — the pipeline. A graph of work to be done.
- **Task / Op / Asset** — a unit of work.
- **Scheduler** — decides what runs when. Cron, event-driven, or sensor-based.
- **Executor / Runner** — actually runs the work. Local, Celery, Kubernetes, ECS, etc.
- **Sensor** — task that polls for an external condition (file arrival, API readiness) before firing.
- **Backfill** — re-running historical instances of a scheduled pipeline.
- **Retry** — automatic re-execution on failure, with backoff.

### 7.3 Common Patterns

- **Daily batch transform** — extract at 2 AM → load → dbt run → tests → notify. The boring 80% of orchestration.
- **Sensor-driven** — wait for a file to land in S3, then trigger downstream. Replace with event-driven via SQS/PubSub where possible.
- **Backfill from historical date** — `dbt run --vars '{start_date: 2020-01-01}'` with the orchestrator iterating dates. Iceberg/Delta time travel makes this safer.
- **Fan-out / fan-in** — process N partitions in parallel, then merge. Dagster's `DynamicOutput`, Airflow's `expand()` (dynamic task mapping), Prefect's `map`.
- **Cross-DAG dependency** — DAG B should wait for DAG A. Airflow: `ExternalTaskSensor` or dataset triggers. Dagster: native via asset deps across jobs. Prefect: flow-of-flows.

### 7.4 What Orchestrators Are Not For

- **Data transformation logic.** Use dbt or Spark or SQL. Orchestrators should *call* those tools, not contain transformation logic.
- **Streaming.** Orchestrators are for batch. Use Flink/Kafka Streams/Spark Structured Streaming for stream processing.
- **Low-latency triggering.** Orchestrators schedule on minute granularity, not second. For event-driven sub-second triggers, use serverless functions or a real event bus.

References: [Airflow documentation](https://airflow.apache.org/docs/), [Dagster documentation](https://docs.dagster.io/), [Prefect documentation](https://docs.prefect.io/)

---

## Phase 8: Distributed Compute

When your data is too big for a single warehouse query to be efficient, or when your transformations are too complex to express in SQL, you reach for distributed compute. Spark dominates this niche; DuckDB and Polars are increasingly displacing it for single-node workloads.

### 8.1 Spark Fundamentals

**Apache Spark** is a distributed compute engine. Started at Berkeley (2009), now an Apache project. Most production data engineering with custom Python/Scala code runs on Spark.

The three APIs, in order of historical age:

- **RDDs** (Resilient Distributed Datasets) — low-level, typed, functional. Old. Don't use for new code unless you have specific reasons.
- **DataFrames** — high-level, schema-aware, optimizer-driven. The default API.
- **Spark SQL** — write SQL, execute on Spark. The same query planner as DataFrames.

The data flows the same way regardless of API: through the **Catalyst optimizer** (logical → physical plan, cost-based optimization) and the **Tungsten execution engine** (whole-stage code generation, vectorized operators).

### 8.2 The Concepts You Have to Know

- **Lazy evaluation** — Spark builds a plan as you compose operations; nothing runs until you call an action (`collect`, `count`, `write`).
- **Transformations vs. actions** — `select`, `filter`, `join`, `groupBy` are transformations (lazy). `count`, `show`, `write` are actions (trigger execution).
- **Narrow vs. wide transformations**:
  - *Narrow* — each output partition depends on one input partition. `map`, `filter`. Cheap.
  - *Wide* — each output partition depends on many input partitions. `groupBy`, `join`. Trigger a **shuffle**.
- **Shuffle** — moving data between executors over the network. The single dominant cost in Spark jobs.
- **Partitioning** — Spark splits a DataFrame into partitions; each partition is processed by one task. Too few partitions = parallelism is limited. Too many = scheduling overhead dominates. Rule of thumb: aim for **128 MB – 1 GB per partition**.
- **Broadcast join** — when one side of a join is small (< 100 MB), Spark can send a copy to every executor instead of shuffling both sides. Massive speedup. Auto-triggered, but check `broadcastHashJoin` in the plan.
- **Adaptive Query Execution (AQE)** — Spark 3+ runtime optimization: re-partition mid-query based on actual data sizes. Turn it on (`spark.sql.adaptive.enabled=true`).

### 8.3 Reading a Spark Plan

```python
df.explain(mode="extended")
```

Look for:
- **Exchange** = shuffle. Each one is expensive. Question every Exchange.
- **BroadcastHashJoin** good; **SortMergeJoin** with two Exchanges expensive.
- **PartitionFilters** show predicate pushdown working.
- **PushedFilters** show filter pushdown into Parquet readers.

If your job is slow, the explain plan is the first thing to look at. Not the executor logs.

### 8.4 When Spark Is the Right Choice

- Your transformation is too complex for SQL alone (custom UDFs in Python/Scala, ML pipelines, complex joins across many sources).
- Your data is too large for your warehouse to be cost-effective (petabyte scale).
- You're already on Databricks (Spark is the native runtime).

### 8.5 When Spark Is Not

- Your transformation fits in SQL. Use the warehouse.
- Your data fits in memory of a single machine (< ~100 GB). **Use DuckDB or Polars.**
- You're doing low-latency, single-query work. Use a warehouse with a fast query engine (ClickHouse, BigQuery, Snowflake).

### 8.6 DuckDB and Polars

The 2022–2026 story: enormous improvements in single-node columnar engines have eaten a lot of small-Spark's lunch.

- **DuckDB** — embedded analytics database, SQL interface, reads Parquet/CSV/JSON natively. Stunning performance on a single node. Embeds in Python (`pip install duckdb`), R, Rust, Wasm. The right tool for "I have ~10–500 GB of Parquet on S3 and I want to query it without infrastructure."
- **Polars** — DataFrame library written in Rust. Pandas-like API, but multithreaded, lazy, with a query optimizer. Often 5–50× faster than pandas. The right tool for analytics code in Python that's too big for pandas but too small for Spark.

A useful 2026 heuristic:
- **< 100 GB**: DuckDB or Polars in a single process.
- **100 GB – 10 TB**: Warehouse SQL, or Spark on a small cluster.
- **> 10 TB**: Warehouse SQL (with partition pruning), or Spark on a real cluster.

References: [Spark documentation](https://spark.apache.org/docs/latest/), ["Mastering Spark with R" plan explanations](https://therinspark.com/), [DuckDB documentation](https://duckdb.org/docs/), [Polars user guide](https://pola-rs.github.io/polars/)

---

## Phase 9: Streaming

Stream processing handles data record-by-record (or in small micro-batches) as it arrives. The decision to go streaming carries real operational complexity; do it when you have to, not when you want to.

### 9.1 The Kafka Model

Kafka is the de facto streaming backbone. The concepts:

- **Topic** — named, ordered, append-only log. Partitioned across brokers.
- **Partition** — a single ordered log within a topic. Ordering is guaranteed *within* a partition, not across partitions.
- **Producer** — writes records to topics.
- **Consumer** — reads records from topics. Maintains an *offset* per partition.
- **Consumer group** — set of consumers that collectively read a topic; each partition assigned to exactly one consumer in the group. Scales horizontally up to the partition count.
- **Replication** — each partition is replicated across brokers; one is the leader.
- **Retention** — messages persist for a configured time (or size). Default 7 days. Increase if downstream consumers need replay capability.

The mental model that pays off: **a topic is a durable, replayable log**. Once data is in Kafka, you can have N independent consumers, each at their own offset, without affecting producers. This decoupling is the architectural win.

### 9.2 Schema Management

In production Kafka, **always use a schema registry** (Confluent Schema Registry is the canonical implementation). Producers and consumers register and resolve Avro/JSON Schema/Protobuf schemas by ID; the payload carries just the schema ID, not the full schema.

This buys you:
- **Forward and backward compatibility** — old consumers can read new producers' messages; new consumers can read old producers' messages.
- **Strong typing** — payloads aren't a JSON soup that breaks the moment an upstream renames a field.
- **Storage efficiency** — Avro binary is dramatically smaller than JSON.

The cost: an additional service to operate, and a tighter coupling between producers and the registry. Worth it once you're past hobby scale.

### 9.3 Stream Processing Engines

- **Kafka Streams** — JVM library, runs inside your application. Stateful operations (joins, aggregations, windowing) with state in RocksDB plus changelog topics for fault tolerance. Tight coupling to Kafka but operationally simple — your stream processor *is* a regular JVM service.
- **Apache Flink** — the heavyweight streaming engine. Best-in-class for stateful, exactly-once, low-latency stream processing. Cluster-based; more ops than Kafka Streams. The right choice when you need real streaming with complex state.
- **Spark Structured Streaming** — micro-batch (default ~1s batches) implemented on the Spark engine. Easier to operate than Flink if you're already on Spark. Higher latency than Flink for true streaming.
- **Streaming SQL** — Materialize, RisingWave, ksqlDB. Write SQL; the engine maintains incrementally-updated materialized views over Kafka topics. Excellent ergonomics; relatively new but production-ready.

### 9.4 Lambda vs. Kappa Architectures

The old debate, still useful framing:

- **Lambda** — separate batch and streaming pipelines that produce the same outputs. Batch is authoritative; streaming is for fresh-but-approximate results. Two codebases to maintain.
- **Kappa** — one streaming pipeline. Reprocess history by replaying from the start of the Kafka log. No separate batch code. Possible only if Kafka retention is long enough (or the data is also archived to S3).

By 2026 most "Kappa" deployments are pragmatically Lambda-shaped: Kafka for live, lakehouse for history, with shared transformation logic in dbt or streaming SQL.

### 9.5 Exactly-Once Semantics

The hardest problem in streaming: *each input record produces exactly one set of output effects, even with failures*.

- **At-most-once** — events may be lost, never duplicated. Simple, often unacceptable.
- **At-least-once** — events may be duplicated, never lost. Easy; requires downstream idempotency.
- **Exactly-once** — neither. Requires coordinated transactions across producer, broker, and sink.

Kafka has supported exactly-once *within* a Kafka-to-Kafka topology since 2017 (transactional producer + read-committed isolation). Exactly-once *into a warehouse / lakehouse* requires the sink to support idempotent or transactional writes. Iceberg, Snowflake Snowpipe Streaming, and modern Spark sinks all support this; older sinks don't.

In practice: **design for at-least-once + downstream idempotency** unless the cost of duplicates is concrete and unacceptable. Idempotent inserts (`MERGE ON unique_key`) are usually sufficient.

References: [Kafka documentation](https://kafka.apache.org/documentation/), ["Designing Data-Intensive Applications" Ch. 11 — Stream Processing](https://dataintensive.net/), [Flink documentation](https://nightlies.apache.org/flink/flink-docs-stable/)

```quiz
Q: What's the architectural win of "a topic is a durable, replayable log"?
- [x] N independent consumers can each read at their own offset without affecting producers or each other — decoupling that batch file-drops don't give you
- [ ] Messages are deleted once consumed
- [ ] Ordering is guaranteed across the whole topic
- [ ] It eliminates the need for schemas
> Kafka ordering holds *within* a partition, not across them. The replayable-log property is what enables Kappa-style reprocessing and adding new consumers retroactively.

Q: Why use a schema registry in production Kafka?
- [x] Producers/consumers resolve schemas by ID (payload carries just the ID), giving forward/backward compatibility and strong typing instead of JSON soup that breaks on an upstream rename
- [ ] It encrypts the messages
- [ ] It guarantees exactly-once delivery
- [ ] It replaces consumer groups
> The cost is an extra service and producer↔registry coupling, worth it past hobby scale. Avro binary is also far smaller than JSON — storage efficiency on top of compatibility.

Q: What's the practical default for delivery semantics into a warehouse, and why?
- [x] At-least-once plus downstream idempotency (MERGE on unique_key) — true exactly-once needs coordinated transactions across producer, broker, and a sink that supports it
- [ ] Exactly-once always; anything less is unacceptable
- [ ] At-most-once, since duplicates are worse than loss
- [ ] It doesn't matter for batch sinks
> Kafka has exactly-once *within* Kafka-to-Kafka since 2017, but into a warehouse it depends on the sink. Designing for idempotent inserts is simpler and usually sufficient — reserve exactly-once for when duplicate cost is concrete and unacceptable.
```

---

## Phase 10: Data Modeling

The schema of your analytics layer determines what queries are easy, what queries are expensive, and how analysts feel about working with your data. The investment in modeling pays back forever.

### 10.1 Kimball Dimensional Modeling

Ralph Kimball's dimensional modeling (1996; *The Data Warehouse Toolkit*) is the canonical approach and the one most teams should default to.

- **Fact table** — the things that happened. One row per event/transaction. Mostly foreign keys + numeric measures. Examples: `fct_orders`, `fct_page_views`, `fct_sessions`.
- **Dimension table** — the context. Slowly-changing reference data. Examples: `dim_customers`, `dim_products`, `dim_dates`.
- **Star schema** — one fact + the dimensions it joins to. The shape analysts can query without thinking.
- **Snowflake schema** — dimensions joined to other dimensions. Don't bother; flatten dimensions instead.

Why this layout: it matches how analysts actually think (*"orders per customer per region per month"* = fact + dimensions), it's optimizable by query engines, and it's stable as the business grows.

### 10.2 Slowly Changing Dimensions

Dimensions change over time. A customer's address changes; a product's category changes. How you handle this depends on what the business cares about.

- **SCD Type 1** — overwrite. The old value is gone. Right when history doesn't matter (typos, corrections).
- **SCD Type 2** — keep history. Add `valid_from` / `valid_to` columns; each version is a separate row. The default for anything where historical accuracy matters.
- **SCD Type 3** — keep the *previous* value in a column (`current_address`, `previous_address`). Limited utility; usable for "I want to compare current to one historical state."
- **SCD Type 6** — combination: Type 1 + Type 2 + Type 3. Mostly academic.

dbt snapshots (Phase 6.4) implement Type 2 well. Use them.

### 10.3 Data Vault

A modeling approach from Dan Linstedt; popular in heavily-regulated industries (banks, government).

- **Hub** — business keys.
- **Link** — many-to-many relationships between hubs.
- **Satellite** — descriptive attributes for hubs and links, with full history.

Data Vault optimizes for **auditability and source-system independence**. The cost: more tables, more joins, more cognitive overhead.

Use Data Vault if you have multiple OLTP sources with overlapping entities and strict audit requirements. For most companies, Kimball is enough.

### 10.4 One Big Table (OBT) / Wide Tables

The pragmatic counter to dimensional modeling: just denormalize everything into one wide table per topic.

- *Pros*: no joins at query time; matches how BigQuery and Snowflake love to scan; analyst-friendly.
- *Cons*: storage cost grows; updates to dimension attributes require rebuilding; you lose the structural elegance of star schemas.

OBT is increasingly common as a *mart* layer on top of a Kimball-modeled warehouse: keep dimension + fact tables for flexibility, ship a few OBTs for the hottest dashboards. Best of both.

### 10.5 The Modeling Smell Tests

Your model is probably wrong if:
- Analysts copy-paste the same join over and over. Add a wider mart-layer table.
- Different dashboards return different numbers for the same metric. You have multiple definitions of the metric; consolidate.
- Schema changes break dashboards weekly. Source-coupled mart layer; introduce a stable interface (the *semantic layer*: dbt's [Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl), Cube, LookML).
- "What was X on date D?" is impossible to answer. You don't have SCD2 history.

References: [The Data Warehouse Toolkit](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/), [The Data Vault Guru](https://www.datavaultalliance.com/), [dbt — How we structure our dbt projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)

```quiz
Q: In Kimball dimensional modeling, what distinguishes a fact table from a dimension table?
- [x] A fact is one row per event — foreign keys plus numeric measures (fct_orders); a dimension is the slowly-changing context that gives those keys meaning (dim_customers)
- [ ] Facts are normalized, dimensions denormalized
- [ ] Facts store history, dimensions don't
- [ ] Dimensions are larger than facts
> The star schema (one fact + its dimensions) matches how analysts think — "orders per customer per region per month" — and is what query engines optimize for. Snowflaking dimensions onto each other is the anti-pattern; flatten instead.

Q: A customer's address changes and the business needs to answer "what was their address on date D?" Which SCD type, and what does it do?
- [x] Type 2 — keep history with valid_from/valid_to columns, each version a separate row; Type 1 (overwrite) loses the old value entirely
- [ ] Type 1, since it's simplest
- [ ] Type 3, which keeps full history
- [ ] No SCD type can answer this
> "What was X on date D is impossible to answer" is a modeling smell test that means you lack Type 2 history. dbt snapshots implement it well.

Q: When is One Big Table (OBT) the right choice over a star schema?
- [x] As a mart layer for the hottest dashboards — denormalized, no query-time joins, matches how Snowflake/BigQuery love to scan — kept *on top of* a Kimball-modeled core for flexibility
- [ ] As a wholesale replacement for all dimensional modeling
- [ ] Only for streaming data
- [ ] When storage is the primary cost concern
> OBT trades storage and update-cost for join-free analyst ergonomics. The best-of-both pattern is dimensional core for flexibility plus a few OBTs for speed — not one or the other.
```

---

## Phase 11: Quality, Testing, Observability

"Pipeline ran successfully" tells you nothing about whether the *data* is correct. Quality is a discipline distinct from operational uptime.

### 11.1 The Five Pillars of Data Observability

Originally articulated by Monte Carlo, broadly adopted:

1. **Freshness** — is data arriving on the expected schedule?
2. **Volume** — is the row count in the expected range?
3. **Schema** — has the schema changed unexpectedly?
4. **Distribution** — are values within expected ranges (no nulls where there shouldn't be, no negative prices, valid enum values)?
5. **Lineage** — where did this data come from, and what does it feed?

A robust DE platform monitors all five.

### 11.2 The Tools

- **dbt tests** — built into your transformation framework. `unique`, `not_null`, `accepted_values`, `relationships`, plus packages (`dbt-utils`, `dbt-expectations`) with dozens of additional assertions. Free, version-controlled, runs in your existing pipeline.
- **Great Expectations** — Python framework for data assertions. More expressive than dbt tests, more overhead to operate. Use when assertions need to be reused across multiple tools or when you need a richer expectation library.
- **Soda** — declarative checks defined in YAML, runs as a service or CLI. Cleaner ergonomics than GE for SQL-first teams.
- **Monte Carlo, Bigeye, Anomalo, Metaplane** — commercial data observability platforms. Anomaly detection on metrics (freshness, volume, distribution) without writing explicit checks. Worth evaluating once you've outgrown declarative checks.

### 11.3 Data Contracts

Increasingly important: a *data contract* is a versioned, explicit interface between data producer and consumer. Producers commit to:
- A schema (with backward-compatibility rules).
- A freshness SLO.
- A volume range.
- Owner contact info.

Consumers consume against the contract, not against the underlying table directly. If the producer violates the contract, the consumer's pipeline fails (or alerts) at the contract boundary, not deep in some downstream report.

Tools: [dbt model contracts](https://docs.getdbt.com/docs/collaborate/govern/model-contracts), [DataContract.com spec](https://datacontract.com/), Schema Registry for Kafka.

### 11.4 Lineage

Where did this column come from? What downstream things depend on it? Lineage answers this.

- **dbt** generates column-level lineage natively for SQL transformations.
- **OpenLineage** is the open standard for cross-tool lineage; Airflow, Spark, dbt, Dagster all emit OpenLineage events.
- **Marquez** is the open-source backend for OpenLineage events.
- **Atlan, OpenMetadata, DataHub, Unity Catalog** are higher-level catalogs that ingest lineage and present it for humans.

Why this matters: at scale, "what breaks if I change this column?" is unanswerable without lineage. Without it, schema changes become political.

### 11.5 Testing Strategy

A pragmatic ladder:

1. **Source freshness** — alert if Fivetran or Kafka stops delivering. Cheapest, highest-value monitor.
2. **Schema tests on sources** — fail loudly if upstream changes shape unexpectedly.
3. **Primary key uniqueness + not-null on key columns** on every mart-layer model. Catches 80% of bugs.
4. **Referential integrity** between facts and dimensions.
5. **Range / distribution checks** on key metrics.
6. **Reconciliation** — sum of revenue in `fct_orders` equals sum in source. Often the only test that catches subtle bugs.
7. **Anomaly detection** — when explicit checks aren't enough.

References: [Monte Carlo — Five Pillars of Data Observability](https://www.montecarlodata.com/blog-what-is-data-observability/), [OpenLineage](https://openlineage.io/)

---

## Phase 12: Operations & Governance

The DE concerns that aren't about building pipelines but about running them well.

### 12.1 Cost

In modern DE, your warehouse bill is your dominant infrastructure cost. Watch it.

- **Snowflake**: per-second compute on virtual warehouses, plus storage. Right-size warehouses (smaller for ETL, larger for ad-hoc), set auto-suspend short (60s), use multi-cluster only where concurrency genuinely demands it.
- **BigQuery**: per byte scanned (on-demand) or per slot-hour (capacity). On-demand makes `SELECT *` financially terrifying. Partition every large table; cluster on common filter columns. Use BI Engine for repeated dashboard queries.
- **Databricks**: per-DBU consumption based on compute type, plus underlying cloud compute. Use job clusters (not interactive) for batch; pick the right photon-enabled compute for SQL.
- **General**: monitor cost per query, cost per dbt model, cost per dashboard. Make this visible to model authors.

See Phase 13.3 for concrete recipes.

### 12.2 PII and Access Control

- **Tag PII at ingest** — every column containing personal data tagged in the catalog. Automate this where possible (column name heuristics + sample-data scanners).
- **Role-based access** — analysts get role X, executives get role Y, marketing gets a redacted view. Use Snowflake masking policies / BigQuery column-level security / Databricks Unity Catalog column masks.
- **Row-level security** — `region_manager` sees only their region. Same systems support this declaratively.
- **PII vault pattern** — keep PII in a separate, restricted table; reference by surrogate key elsewhere. The analytics layer never sees raw PII.

### 12.3 Schema Evolution

- **Additive changes (new columns, widened types)** — safe, usually backward-compatible.
- **Renames and drops** — usually breaking. Communicate upfront, deprecate first.
- **Type narrowings** — almost always breaking.
- **Use a schema registry** for streaming. Use dbt model contracts or similar for batch.
- **Backfill plans** — every schema change to a historical table needs a backfill plan or a compatibility shim. Don't ship a change you can't roll back.

### 12.4 Catalogs

A *data catalog* is the inventory: every table, who owns it, what's in it, how to access it. Increasingly also the lineage and governance hub.

- **Cloud-native** — AWS Glue, GCP Data Catalog / Dataplex, Azure Purview, Snowflake's native metadata.
- **Open** — Apache Polaris (Snowflake-led Iceberg catalog), Unity Catalog (Databricks-led, now open-sourced), Apache Gravitino, OpenMetadata, DataHub.
- **Commercial** — Atlan, Alation, Collibra, Castor (now Coalesce).

For new builds in 2026, the lakehouse-aligned answer is **Polaris** or **Unity Catalog** depending on which way your stack leans, with **OpenMetadata** as the open-source pure-play.

### 12.5 Right-to-be-Forgotten (GDPR/CCPA)

When a user requests deletion, you must delete their data — across warehouse, lakehouse, backups, logs, derived tables.

- **Centralize identifiers** — every PII record reachable via a single user ID.
- **Use formats that support deletes** — Iceberg, Delta, and most warehouses do; raw Parquet does not (requires file rewrite).
- **Have a documented deletion runbook** with verification.
- **Consider the PII vault pattern** — deleting one row in the PII vault is much cheaper than rewriting every fact table.

References: [The Data Engineer's Guide to GDPR](https://www.confluent.io/blog/handling-gdpr-log-forget/), [Unity Catalog architecture](https://www.databricks.com/product/unity-catalog)

---

## Phase 13: Practical Recipes

Concrete, prescriptive sections for the applied tasks that come up every week.

### 13.1 A Real dbt Project Layout

The convention dbt itself recommends, and that most mature teams converge on:

```
my_dbt_project/
├── dbt_project.yml             # Project config
├── packages.yml                # External packages (dbt_utils, dbt_expectations, etc.)
├── profiles.yml                # Connection (usually in ~/.dbt/, not in repo)
├── models/
│   ├── staging/                # 1:1 with source tables, lightweight cleanup
│   │   ├── stripe/
│   │   │   ├── _stripe__sources.yml      # Source declarations
│   │   │   ├── _stripe__models.yml       # Model docs + tests
│   │   │   ├── stg_stripe__charges.sql
│   │   │   ├── stg_stripe__customers.sql
│   │   │   └── stg_stripe__refunds.sql
│   │   └── salesforce/
│   │       ├── _salesforce__sources.yml
│   │       └── stg_salesforce__opportunities.sql
│   ├── intermediate/           # Reusable building blocks not exposed to consumers
│   │   └── finance/
│   │       └── int_finance__charges_with_refunds.sql
│   └── marts/                  # Business-facing models, by domain
│       ├── finance/
│       │   ├── _finance__models.yml
│       │   ├── dim_customers.sql
│       │   ├── fct_revenue_daily.sql
│       │   └── fct_subscriptions.sql
│       └── product/
│           ├── dim_users.sql
│           └── fct_sessions.sql
├── snapshots/
│   └── customers_snapshot.sql
├── seeds/
│   └── country_codes.csv
├── macros/
│   ├── generate_schema_name.sql
│   └── pivot_currency.sql
├── tests/                      # Singular tests (not generic)
│   └── assert_revenue_positive.sql
├── analyses/                   # SQL used for ad-hoc analysis, not run as part of dbt
└── README.md
```

The naming conventions that pay off:
- **`stg_<source>__<table>`** — staging models, lightweight column renaming, casting, no business logic. One per source table.
- **`int_<domain>__<purpose>`** — intermediate models. Used as building blocks; not consumed directly by dashboards.
- **`dim_<noun>`** / **`fct_<noun>`** — mart-layer dimensional models. The interface to analysts.

Folder structure principles:
- **`staging/` is grouped by source system.** One folder per source. Mirror the source structure.
- **`intermediate/` and `marts/` are grouped by business domain**, not by source. `finance/`, `marketing/`, `product/`.
- **Every model has docs and tests in a `.yml` next to it.** Use one YAML per folder (`_finance__models.yml`) rather than per file — fewer files, easier to scan.

A few `dbt_project.yml` choices that pay off:

```yaml
models:
  my_project:
    staging:
      +materialized: view          # Cheap, always-fresh
      +schema: staging
    intermediate:
      +materialized: ephemeral     # Inlined as CTEs
      +schema: intermediate
    marts:
      +materialized: table         # Persisted for query performance
      +schema: marts
```

- **Staging as views**: free to rebuild, always reflects source. Acceptable for source data that's already in the warehouse and doesn't need transformation.
- **Intermediate as ephemeral**: only exists as CTEs in downstream models. Cuts table-bloat in the warehouse.
- **Marts as tables**: explicit `CREATE TABLE`. Query performance for analysts. Use incremental for large fact tables.

CI patterns worth adopting:
- **`dbt build --select state:modified+`** — on every PR, run only changed models + downstream. Requires `state:` artifacts from production.
- **Slim CI** — only run models touched by the PR; defer all `ref()`s to production. Avoids full project rebuilds for every PR.
- **Run dbt tests in CI** — failing tests block merge. Annotate test failures back to the PR.

### 13.2 Airflow DAG Patterns and Anti-Patterns

The shapes you'll write again and again, and the ones that look right but burn you.

**Pattern: daily idempotent batch**

```python
from airflow.decorators import dag, task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from pendulum import datetime

@dag(
    schedule="0 2 * * *",        # 2 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,                # Don't backfill on first deploy
    max_active_runs=1,            # Never overlap
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=10),
        "retry_exponential_backoff": True,
    },
    tags=["finance", "daily"],
)
def daily_revenue():
    @task
    def extract(ds: str):
        ...                       # ds = the logical date for this run

    @task
    def transform():
        ...

    @task
    def load():
        ...

    extract() >> transform() >> load()

daily_revenue()
```

The key choices:
- **`catchup=False`** — when you first deploy a DAG with `start_date` in the past, do *not* automatically run every missed day. Manually trigger backfills if needed.
- **`max_active_runs=1`** — protects against a slow run overlapping with the next scheduled run.
- **Use `ds` (logical date)**, not `datetime.now()`. Idempotency requires that re-running yesterday's DAG produces yesterday's output.
- **Retries with exponential backoff** — transient failures shouldn't page someone.

**Pattern: dynamic task mapping**

Process N partitions in parallel:

```python
@task
def list_dates():
    return ["2026-05-01", "2026-05-02", "2026-05-03"]

@task
def process(date: str):
    ...

dates = list_dates()
process.expand(date=dates)
```

This generates one task per date at runtime. Much cleaner than the old `for x in [...]` Python loop generating tasks at parse time.

**Pattern: cross-DAG dependency via datasets**

```python
from airflow.datasets import Dataset

stripe_loaded = Dataset("s3://bucket/stripe/")

# Producer DAG:
@task(outlets=[stripe_loaded])
def load_stripe():
    ...

# Consumer DAG:
@dag(schedule=[stripe_loaded])
def transform_stripe():
    ...
```

Modern (Airflow 2.4+) replacement for `ExternalTaskSensor`. The consumer DAG fires when the producer publishes the dataset — no polling, no race conditions.

**Anti-pattern: doing real work in the DAG file**

```python
# DON'T:
import pandas as pd
df = pd.read_csv("s3://bucket/big.csv")    # Runs on every DAG parse!
@task
def transform():
    return df.transform(...)
```

The DAG file is *parsed* by the scheduler on every refresh (every 30s by default). Any code at module scope runs *every parse*. Connecting to databases, reading files, or anything I/O-bound in DAG-level code is a classic newbie mistake that brings the scheduler to its knees. Keep all work inside `@task` functions.

**Anti-pattern: relying on XCom for data passing**

```python
# DON'T:
@task
def extract():
    return pd.read_csv(...)        # 5 GB returned via XCom

@task
def transform(df):
    ...
```

XCom is for *small* metadata (a date, a count, a path), not for moving data between tasks. Pass *references* (S3 paths, table names) through XCom; the actual data lives in object storage.

**Anti-pattern: sensors with default poke interval**

```python
# DON'T:
S3KeySensor(task_id="wait", bucket_key="s3://bucket/file.csv")
# Default poke_interval=60s, holds a worker slot the entire time.
```

Use `mode="reschedule"` (the sensor releases the worker between polls) or `deferrable=True` (Airflow 2.2+, runs in the triggerer process — vastly more efficient). Or replace with an event-driven trigger (S3 → SNS → Airflow API).

**Anti-pattern: time-zone confusion**

DAG `start_date` and `schedule` are interpreted in the DAG's timezone (UTC by default). The *execution_date* / *logical_date* is the *start* of the interval, not the moment the DAG ran. A DAG with `schedule="0 2 * * *"` and a `logical_date` of `2026-05-01 02:00 UTC` actually runs at `2026-05-02 02:00 UTC` (the end of the interval). This is the single most common Airflow misunderstanding.

**Pattern: structuring a large DAG suite**

```
dags/
├── finance/
│   ├── revenue_daily.py
│   └── billing_hourly.py
├── product/
│   └── sessions_daily.py
└── common/
    └── utils.py                   # Importable, not a DAG
```

Group DAGs by domain. Shared code in non-`dags/` modules (Airflow only scans `dags/` for DAG files).

References: [Airflow best practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html), [Astronomer's DAG writing best practices](https://www.astronomer.io/docs/learn/dag-best-practices)

### 13.3 Warehouse Cost Optimization Recipes

Concrete patterns that have repeatedly cut warehouse spend by 30–70% in real production.

**Snowflake**

- **Right-size warehouses, ruthlessly**. A `LARGE` warehouse is 4× the cost of an `XSMALL`. Many workloads run identically fast on `XSMALL`. Start small, scale up only when you measure a benefit. The dbt + dashboard workload is typically fine on `SMALL`.
- **Auto-suspend at 60s.** Default is 600s (10 minutes); you pay for idle time. 60s is the minimum and almost always right for dev/ETL warehouses. (Caches are warm-ish for ~10 minutes regardless.)
- **Separate warehouses by workload**, not by team. Have a `WH_ELT_XS` for hourly ELT, `WH_BI_M` for BI tools (multi-cluster auto-scaling for concurrency), `WH_ADHOC_M` for analysts. This isolates spend and lets you size each correctly.
- **Use the result cache.** Identical queries within 24h are served free from cache as long as underlying data hasn't changed. Avoid `CURRENT_TIMESTAMP()` in queries that don't need it.
- **Use clustering keys on huge tables.** For tables > 1 TB, define `CLUSTER BY (date, customer_id)` to keep micro-partitions sorted on common filter columns. Automatic clustering costs credits but saves dramatically more on query.
- **Materialized views for hot aggregations.** Snowflake materialized views auto-refresh on data changes. Cheaper than re-aggregating on every dashboard load.
- **Search optimization service** for high-selectivity point lookups on large tables. Niche but powerful where it applies.

**BigQuery**

- **Partition every large table by date.** Partitioned tables let queries prune to specific dates. A query against an unpartitioned 5 TB table costs 5 TB scanned; against a partitioned table filtered to one day, it's tens of MB.
- **Cluster on common filter columns.** Up to 4 clustering columns. Effects compound with partitioning. `PARTITION BY DATE(event_ts) CLUSTER BY user_id, country` makes per-user lookups within a date cheap.
- **Never `SELECT *`.** Column pruning is automatic; using it requires you to actually name columns. `SELECT *` on a 200-column table at $5/TB scanned will surprise you.
- **Use `_PARTITIONTIME` filters everywhere.** `WHERE _PARTITIONTIME >= '2026-05-01'` triggers partition pruning before any other filter.
- **Switch to capacity (slot reservations) past a certain spend.** On-demand pricing ($5/TB) is great until you're spending ~$15K/month, at which point flat-rate slots start winning. Reserve a baseline, use on-demand for spikes.
- **BI Engine** — in-memory cache for dashboard queries. Order of magnitude latency improvement; pay for reserved memory. Worth it for hot dashboards.
- **Materialized views** auto-refresh on the underlying table. Trades incremental refresh cost for query cost; usually a win for repeated aggregations.
- **Authorized views as governance.** Define a view that selects only some columns/rows; grant access to the view, not the underlying table.

**Universal**

- **Make cost observable.** Tag every query with its source (dbt model name, dashboard ID). Snowflake has `QUERY_TAG`; BigQuery has labels. Pipe usage data into the warehouse itself and dashboard it.
- **Cost per dbt model.** dbt's `dbt-snowflake` and similar adapters emit cost metadata. Build a "expensive models" report. Have a process for tackling the top 5 each month.
- **Cost per dashboard.** Looker, Mode, Hex, Tableau all expose query history. Find the dashboards burning $X/day and either materialize their queries or kill them.
- **Kill the long tail.** In most warehouses, 10% of queries account for 90% of spend. Find them, fix them, save real money.
- **Cancel runaway queries automatically.** Set warehouse-level statement timeouts (15 min for analytics, longer for batch). Set per-user / per-role quotas.

References: [Snowflake cost optimization](https://docs.snowflake.com/en/user-guide/cost-optimize), [BigQuery best practices](https://cloud.google.com/bigquery/docs/best-practices-costs)

---

## Phase 14: Anatomy of a Production Pipeline

Walking through a realistic end-to-end pipeline so all the previous concepts land. Scenario: a B2C product with an OLTP Postgres backend, Stripe payments, and a clickstream — feeding analytics and a few operational use cases.

### 14.1 The Architecture, at a Glance

```
   ┌──────────┐     ┌──────────┐    ┌──────────────┐
   │ Postgres │     │  Stripe  │    │ Clickstream  │
   │  (app)   │     │  (SaaS)  │    │    (web)     │
   └────┬─────┘     └────┬─────┘    └──────┬───────┘
        │                │                  │
        │ Debezium       │ Fivetran/        │ Snowplow/
        │ (CDC via WAL)  │ Airbyte          │ Segment
        ▼                ▼                  ▼
   ┌─────────────────────────────────────────────────┐
   │  Kafka (or Confluent Cloud)                     │
   │   topics: app.orders, app.users, stripe.charges │
   └────────────────────────┬────────────────────────┘
                            │
                            │ Kafka Connect S3 sink
                            ▼
   ┌─────────────────────────────────────────────────┐
   │  S3 (raw zone)                                   │
   │   s3://lake/raw/app/orders/dt=2026-05-20/*.avro  │
   └────────────────────────┬────────────────────────┘
                            │
                            │ Spark / Iceberg writer (hourly)
                            ▼
   ┌─────────────────────────────────────────────────┐
   │  Iceberg tables (bronze layer)                   │
   │   bronze.app__orders, bronze.stripe__charges    │
   └────────────────────────┬────────────────────────┘
                            │
                            │ dbt (orchestrated by Dagster)
                            ▼
   ┌─────────────────────────────────────────────────┐
   │  Snowflake (mart layer)                          │
   │   marts.fct_orders, marts.dim_customers          │
   └────────────────────────┬────────────────────────┘
                            │
                ┌───────────┼─────────────┐
                ▼           ▼             ▼
            ┌──────┐  ┌─────────┐   ┌──────────┐
            │ BI   │  │ Reverse │   │  Feature │
            │ tool │  │   ETL   │   │   store  │
            └──────┘  └─────────┘   └──────────┘
```

### 14.2 Step by Step, with the Choices Called Out

**Sources**

- **Postgres**: production OLTP DB. Captured via Debezium → Kafka. Choice: log-based CDC over query-based snapshots because deletes matter (refunds, account cancellations) and we don't want to load the OLTP DB.
- **Stripe**: SaaS. Pulled via Fivetran (or Airbyte if cost matters). Choice: don't build the Stripe connector; the maintenance burden never ends. Pay the SaaS fee.
- **Clickstream**: collected via Snowplow (self-hosted) or Segment (managed). Events land in Kafka. Choice: a real event collector with schemas, not a hand-rolled `/track` endpoint.

**Ingestion to the lake (Kafka → S3)**

- **Kafka Connect S3 sink** writes Avro to S3 in partitioned paths (`dt=YYYY-MM-DD/hour=HH`). Choice: Avro (with Schema Registry), not JSON, for compact payloads and schema enforcement.
- **Partitioning**: by hour, not minute. Hourly partitions mean ~24 files per day per topic at modest volume; minute partitions mean 1440 — small-files territory.
- **Compaction**: a daily Spark job repartitions yesterday's hourly Avro into a single optimized file per topic per day. Without this, query performance decays.

**Raw zone (S3) → Bronze (Iceberg)**

- **Iceberg tables** for each source topic, partitioned by `event_date`. Choice: Iceberg over raw Parquet because we want ACID, schema evolution, and deletes (for GDPR).
- **Hourly Spark job** reads new Avro files from S3, writes Iceberg using append + de-duplication on event ID. CDC topics also handle deletes (writing tombstones into Iceberg).
- **Catalog**: AWS Glue or Polaris. Tables are usable from Spark, Trino, Athena, and Snowflake's Iceberg integration.

**Bronze → Silver → Gold (dbt, materialized in Snowflake)**

- **dbt project** is layered staging → intermediate → marts as in Phase 13.1.
- **Staging models** read from Iceberg (via Snowflake's external Iceberg tables) and produce clean, conformed tables in Snowflake. One staging model per Iceberg source table.
- **Intermediate models** do joins and business logic that's reused across marts.
- **Marts** are Kimball-style: `dim_customers`, `dim_products`, `fct_orders`, `fct_charges`, `fct_sessions`.
- **Choice: dbt → Snowflake for marts**, not "dbt → Iceberg" or "Trino on Iceberg." Snowflake is what BI tools query well; Iceberg is what we want for raw retention and ad-hoc Trino/Spark access. We get both.
- **Slowly-changing dimensions**: `dim_customers` is built from a dbt snapshot of the CDC stream, capturing every address change.
- **Tests**: uniqueness on every primary key, not-null on every FK, accepted_values on enums, reconciliation tests on revenue totals.

**Orchestration (Dagster)**

- **Dagster** runs the whole pipeline as a graph of assets:
  - Iceberg tables (one asset per topic, hourly partition).
  - Snowflake staging models (one asset per dbt staging model).
  - Mart models (one per mart, with explicit dependencies).
- **Schedules**: bronze writers run hourly; dbt staging runs every 2 hours; marts run every 4 hours; daily aggregates run at 4 AM. Picked based on consumer freshness requirements, not "as fresh as possible."
- **Sensors**: a sensor watches the raw S3 bucket; if hourly data fails to arrive within 2 hours of expected, page oncall.
- **Backfills**: re-running an asset for a specific partition recomputes that partition only. Iceberg makes this cheap because the time-travel snapshot is what we rewrite against.

**Quality**

- **Source freshness checks**: Fivetran sync status, Debezium lag, Kafka topic last-offset age. Alert if any source goes stale.
- **dbt tests**: run after every model build. Failures block downstream models.
- **Data observability tool** (Monte Carlo or open-source equivalent) watches volume and distribution of mart-layer tables for anomalies.
- **Reconciliation**: a daily job sums `fct_orders.amount` against Stripe's own reported daily total and alerts if they differ by more than 0.1%.

**Serving**

- **BI tool** (Looker/Mode) connects to Snowflake. Looker defines a semantic layer on top of marts; explores resolve to SQL against marts.
- **Reverse ETL** (Hightouch) syncs computed customer segments and lifetime-value scores from `marts` back into Salesforce, Braze, and Intercom.
- **Feature store** (Tecton or Feast): online features are read from a low-latency store fed from the same marts; offline features for training are read directly from marts.

### 14.3 The Operational Realities

- **One pager-able pipeline**: bronze writer. If it falls over, *everything* downstream is stale. Has alerts on freshness, lag, and error rate.
- **Cost monitoring**: every dbt model is tagged with a domain (`finance`, `product`). A monthly cost-per-domain dashboard surfaces who's spending what. Owners are accountable.
- **Schema changes**: source schema changes propagate as Schema Registry events. A consumer dashboard tracks which sinks have caught up; dbt model contracts at the mart boundary fail the build if breaking changes hit.
- **PII**: customer email/name/address tagged at ingest. Snowflake masking policies redact for non-privileged roles. A monthly job verifies no PII column has escaped the mart-layer access controls.
- **GDPR**: a deletion runbook exists. Triggered: writes a tombstone into Iceberg, propagates through bronze → silver → gold via `MERGE`, and a separate process rewrites old S3 raw files to drop the deleted user's rows. Verified before closing the ticket.

### 14.4 Why This Architecture

The decisions that shaped it:

1. **Lakehouse on Iceberg** for raw retention. Snowflake locks the data in (somewhat); Iceberg keeps the long tail of "we might want to use a different engine in 3 years" open.
2. **Snowflake for marts** because the BI tools and analysts work in SQL and ergonomically Snowflake is where they want to live.
3. **Kafka as the spine** for everything event-shaped. Buys decoupling, replay, multiple consumers.
4. **dbt for transformations** because SQL is the lingua franca and the version-controlled, tested SQL workflow is enormously productive.
5. **Dagster for orchestration** because the asset-based model matches how we think about the system.
6. **Avro for streaming**, **Parquet for batch**, **Iceberg for tables** — each format chosen for what it's best at.

None of these are "the right answer in the abstract." They're the right answer for this scenario. The shape of the questions — *what's the freshness requirement, what's the BI tool, what does the team already know* — drives the answer.

---

## Mastery Checklist

You're solid on data engineering when you can, without looking anything up:

- Explain OLTP vs. OLAP and pick storage / format / engine accordingly.
- Read a Parquet file's footer and explain why a query did or didn't prune partitions.
- Choose between Snowflake / BigQuery / Databricks / ClickHouse for a given workload and justify the choice.
- Explain when Iceberg or Delta beats raw Parquet (and when it doesn't).
- Pick between CDC, incremental snapshot, and full snapshot for a given source.
- Write a dbt incremental model with the right strategy and watermark, and explain why full refresh produces the same output.
- Implement SCD2 history with dbt snapshots.
- Read a Spark query plan and identify the expensive operation.
- Decide between Spark, warehouse SQL, DuckDB, and Polars for a given task.
- Choose between Airflow, Dagster, and Prefect and articulate the trade-offs.
- Write an idempotent Airflow DAG without time-zone bugs.
- Tag PII at ingest and propagate access controls through the mart layer.
- Estimate the warehouse cost of a query before running it, and reduce it by 10× with partitioning + clustering + column pruning.
- Design a deletion (GDPR) workflow across warehouse, lakehouse, and backups.
- Defend a Kimball star schema *and* know when to flatten into OBT instead.
- Read an OpenLineage event stream and trace a column from dashboard back to source.

---

## Recommended Reading Path

1. **[Fundamentals of Data Engineering](https://www.oreilly.com/library/view/fundamentals-of-data/9781098108298/)** (Reis & Housley) — the standard text. Read end to end.
2. **[The Data Warehouse Toolkit](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/)** (Kimball) — dimensional modeling. Old but timeless.
3. **[Designing Data-Intensive Applications](https://dataintensive.net/)** (Kleppmann) — the substrate every DE stands on. Read at least chapters 1, 3, 6, 10, 11.
4. **[Spark: The Definitive Guide](https://www.oreilly.com/library/view/spark-the-definitive/9781491912201/)** (Chambers & Zaharia) — when you need to go deep on Spark.
5. **[dbt's "How we structure our dbt projects"](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)** — the conventions that became industry standard.
6. **[The Log: What every software engineer should know about real-time data's unifying abstraction](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying)** (Jay Kreps) — the mental model for streaming.
7. **[Locally Optimistic](https://www.locallyoptimistic.com/)**, **[Benn Stancil's "benn.substack"](https://benn.substack.com/)**, **[Tristan Handy's blog](https://roundup.getdbt.com/)** — the current discourse. Read selectively, but read.

**Adjacent guides in this repo:** [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) (Kafka/partitioning theory under everything here), [Database Internals](DATABASE_INTERNALS_STUDY_GUIDE.md) (the engines), [Advanced Postgres](ADVANCED_POSTGRES.md), and [Observability](OBSERVABILITY_STUDY_GUIDE.md) (pipeline health).

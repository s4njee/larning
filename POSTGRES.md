# PostgreSQL Feature Reference

A reference-style tour of PostgreSQL features and the SQL you write against them. Each entry gives a short description of what the feature is and when you'd reach for it, followed by concrete, runnable examples. Read it like API docs: scan the headings, dive into what's relevant, move on. Assumes familiarity with basic SQL.

This is the **fundamentals + feature reference** part of a three-guide set. Its companions are the [Advanced PostgreSQL Study Guide](ADVANCED_POSTGRES.md) — the *engine*: MVCC internals, the query planner, `EXPLAIN`, indexing strategy, VACUUM/wraparound, locking at scale, connection pooling, the performance tuning ladder, replication/HA, backup/PITR, observability, and production pitfalls — and [PostgreSQL Extensions in Production](POSTGRES_EXTENSIONS.md), an opinionated tour of the ecosystem (PostGIS, pgvector, TimescaleDB, Citus, pg_cron, and more) with production verdicts and managed-service availability. When a topic here has a deeper treatment elsewhere, you'll see a → pointer.

Tested against PostgreSQL 16/17. Most features work on 13+ unless noted.

---

## How to Use This Pair

- **Learning Postgres?** Read this guide's [Mental Model](#mental-model) first, then work top-to-bottom; each section has a short **Practice** prompt. Move to the [Advanced guide](ADVANCED_POSTGRES.md) once the SQL feels natural.
- **Looking something up?** Scan the table of contents and jump. This file is the "how do I write X" catalog; the Advanced guide is the "why is X slow / how does X work underneath" companion.
- **Tuning or operating a database?** You're mostly in the [Advanced guide](ADVANCED_POSTGRES.md) — performance, vacuum, replication, and ops live there.

---

## Mental Model

Two design choices explain almost everything about how Postgres behaves. Hold these and the rest of the system is consistent rather than arbitrary (the [Advanced guide](ADVANCED_POSTGRES.md) builds its whole arc on them):

- **Process-per-connection.** A `postmaster` forks one OS backend process per client connection — real memory and file-descriptor cost each, which is why connection pooling (PgBouncer) matters at scale. Background workers (`autovacuum`, `checkpointer`, `bgwriter`, `wal writer`) do the housekeeping.
- **Shared buffers + OS cache.** Data lives in 8 KB pages cached in `shared_buffers` (typically ~25% of RAM); the OS page cache holds the rest. Dirty pages are flushed by checkpoints.
- **MVCC (Multi-Version Concurrency Control).** Postgres never updates a row in place — it writes a *new version* and marks the old one dead (hidden `xmin`/`xmax` columns). So **readers never block writers and writers never block readers**, tables accumulate dead rows (*bloat*), and `VACUUM` exists to reclaim them. → [Storage & MVCC Engine](ADVANCED_POSTGRES.md#1-the-storage--mvcc-engine)
- **WAL (Write-Ahead Log).** Every change is written to the WAL before the data file, which is what makes crash recovery, replication, and point-in-time recovery all work. → [WAL & Durability](ADVANCED_POSTGRES.md#2-wal-checkpoints--durability)
- **System catalogs.** Postgres stores metadata about itself in `pg_catalog` (`pg_class`, `pg_index`, `pg_stat_*`, …); the portable `information_schema` is a thin standard view over it.

**Practice:** Install Postgres locally, connect with `psql`, and explore `pg_stat_activity`, `pg_class`, and `pg_indexes`. Run `ps aux | grep postgres` to see the process model, and `EXPLAIN` on any query to preview the planner.

---

## Table of Contents

- [Data Types](#data-types)
- [Table Definition](#table-definition)
- [Constraints](#constraints)
- [Indexes](#indexes)
- [Query Features](#query-features)
- [JSON & JSONB](#json--jsonb)
- [Arrays](#arrays)
- [Ranges](#ranges)
- [Full-Text Search](#full-text-search)
- [Pattern Matching](#pattern-matching)
- [Transactions & Isolation](#transactions--isolation)
- [Locking](#locking)
- [Upserts & MERGE](#upserts--merge)
- [CTEs & Window Functions](#ctes--window-functions)
- [LATERAL Joins](#lateral-joins)
- [Views & Materialized Views](#views--materialized-views)
- [Partitioning](#partitioning)
- [Inheritance](#inheritance)
- [Functions & Procedures](#functions--procedures)
- [Triggers](#triggers)
- [Rules](#rules)
- [LISTEN / NOTIFY](#listen--notify)
- [Row-Level Security](#row-level-security)
- [Roles & Permissions](#roles--permissions)
- [Schemas & Search Path](#schemas--search-path)
- [Sequences](#sequences)
- [COPY & Bulk Loading](#copy--bulk-loading)
- [Foreign Data Wrappers](#foreign-data-wrappers)
- [Extensions](#extensions)
- [psql Essentials](#psql-essentials)

**In the [Advanced guide](ADVANCED_POSTGRES.md):** EXPLAIN & query plans · the planner & statistics · indexing strategy & internals · VACUUM, autovacuum & wraparound · WAL, checkpoints & durability · locking at scale · connection pooling · the performance tuning ladder · partitioning at scale · replication & HA · backup & PITR · observability · production pitfalls · benchmarking.

---

## Data Types

Postgres has the richest type system of any mainstream relational database, and treating that as a feature rather than trivia is the first thing that separates a Postgres schema from a port of a MySQL one. The guiding principle is to **choose the most specific type that models the data**, because the type is not just storage — it is a contract the database enforces, an operator set you get for free, and an index strategy you unlock. A timestamp stored as `timestamptz` rejects garbage, sorts correctly, and does time-zone math; the same data stored as `text` does none of that and pushes every one of those concerns into application code that will eventually get one of them wrong. The same logic runs through the whole catalog: `inet` for IP addresses gives you subnet containment operators, `jsonb` gives you indexed containment queries, range types give you overlap exclusion constraints, and enums give you a closed set the database guards. The reference entries below are organized from the everyday types you'll use constantly (numbers, identity columns, text, timestamps) through the distinctively-Postgres types (JSON, arrays, ranges, network, geometric) that are the reason teams choose it; the recurring lesson in each is that picking the precise type moves correctness from your code into the engine, which is exactly where it's cheapest to enforce.

### Numeric types

`smallint`, `integer`, `bigint` for integers; `numeric(p,s)` for exact decimals; `real` and `double precision` for floats. Use `numeric` for money — never `float`.

```sql
CREATE TABLE prices (
  id      bigint PRIMARY KEY,
  amount  numeric(12,2) NOT NULL,
  rate    double precision
);
```

### Identity columns

SQL-standard replacement for `serial`. Use `GENERATED BY DEFAULT AS IDENTITY` for the common case; `ALWAYS` to forbid manual overrides.

```sql
CREATE TABLE orders (
  id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts  timestamptz DEFAULT now()
);

-- Reset the identity after a bulk load
ALTER TABLE orders ALTER COLUMN id RESTART WITH 10000;
```

### Text types

`text` and `varchar` are identical in performance inside Postgres — `varchar(n)` just adds a length check. Use `text` and enforce length with a `CHECK` if needed. `char(n)` pads with spaces; avoid it.

```sql
CREATE TABLE users (
  email text NOT NULL CHECK (length(email) <= 320),
  bio   text
);
```

### Timestamps

`timestamptz` stores UTC and converts on display. Mix of `timestamp` and `timestamptz` is a classic bug. `clock_timestamp()` advances inside a transaction; `now()` / `current_timestamp` don't.

```sql
SELECT now(), clock_timestamp(), now() AT TIME ZONE 'America/Los_Angeles';
SELECT '2026-06-15 14:00:00 America/New_York'::timestamptz;

-- Arithmetic with intervals
SELECT now() - interval '7 days';
SELECT date_trunc('month', now());
SELECT generate_series(date '2026-01-01', date '2026-12-01', interval '1 month');
```

### UUID

Built-in since Postgres 13 (`gen_random_uuid()`); earlier required `pgcrypto`. UUIDv7 (time-ordered) is standard in Postgres 18.

```sql
CREATE TABLE events (
  id  uuid PRIMARY KEY DEFAULT gen_random_uuid()
);
```

### Boolean

Accepts `true/false`, `t/f`, `yes/no`, `on/off`, `1/0`.

```sql
SELECT 't'::boolean, 'no'::boolean, (1=1);
```

### JSON and JSONB

`jsonb` is parsed and indexed; `json` is raw text. Use `jsonb` unless you need to preserve exact whitespace/key-order.

```sql
CREATE TABLE events (
  id    bigint GENERATED ALWAYS AS IDENTITY,
  data  jsonb NOT NULL
);

INSERT INTO events (data) VALUES
  ('{"kind":"login","user":"alice","ip":"10.0.0.1"}');

-- Lookups
SELECT data->>'kind' FROM events WHERE data @> '{"user":"alice"}';
```

See [JSON & JSONB](#json--jsonb) below for the full operator list.

### Arrays

Any type can be an array. Good fit for small bounded lists (tags, flags) where a join table would be overkill.

```sql
CREATE TABLE posts (
  id    bigint PRIMARY KEY,
  tags  text[] DEFAULT '{}'
);

INSERT INTO posts VALUES (1, ARRAY['postgres','sql']);
SELECT * FROM posts WHERE tags @> ARRAY['postgres'];
SELECT unnest(tags) FROM posts;
```

### Range types

`int4range`, `int8range`, `numrange`, `tsrange`, `tstzrange`, `daterange`. Bounded intervals with proper overlap semantics. Multirange variants (`*multirange`) in Postgres 14+.

```sql
SELECT tstzrange('2026-01-01', '2026-02-01', '[)') @> now();
SELECT int4range(1,10) && int4range(5,20);  -- overlap
```

### Network address

`inet` (host + optional subnet), `cidr` (network), `macaddr`. Operators compare by address, not string.

```sql
SELECT '192.168.1.0/24'::cidr >> '192.168.1.42'::inet;  -- contains
SELECT inet '10.0.0.1' + 5;                             -- 10.0.0.6
```

### Enumerated types

Fixed set of string values. Ordered by declaration. Adding values requires `ALTER TYPE`.

```sql
CREATE TYPE order_status AS ENUM ('pending','shipped','delivered','cancelled');
ALTER TYPE order_status ADD VALUE 'returned' AFTER 'delivered';

CREATE TABLE orders (status order_status NOT NULL DEFAULT 'pending');
```

### Composite types

Structured records. Useful as return types from functions, less so as column types.

```sql
CREATE TYPE address AS (street text, city text, postal text);

CREATE TABLE customers (
  id   bigint PRIMARY KEY,
  home address
);

INSERT INTO customers VALUES (1, ROW('1 Elm','Portland','97201'));
SELECT (home).city FROM customers;
```

### Domains

Named constrained types — reusable `CHECK` + `NOT NULL` package.

```sql
CREATE DOMAIN email AS text
  CHECK (VALUE ~ '^[^@]+@[^@]+\.[^@]+$');

CREATE TABLE users (primary_email email NOT NULL);
```

### Geometric types

`point`, `line`, `lseg`, `box`, `path`, `polygon`, `circle`. Use PostGIS for real GIS work.

```sql
SELECT point '(0,0)' <-> point '(3,4)';  -- distance = 5
```

### bytea

Raw binary. Two encodings: `hex` (default) and `escape`.

```sql
SELECT decode('deadbeef','hex');
SELECT md5('hello')::bytea;
```

### Full-text types

`tsvector` (lexeme bag) and `tsquery` (search expression). See [Full-Text Search](#full-text-search).

---

## Table Definition

### Basic CREATE TABLE

```sql
CREATE TABLE books (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  isbn        text UNIQUE NOT NULL,
  title       text NOT NULL,
  published   date,
  created_at  timestamptz NOT NULL DEFAULT now()
);
```

### Generated columns

Always computed from other columns. `STORED` is the only option today (virtual in spec, not implemented).

```sql
CREATE TABLE products (
  price   numeric(10,2) NOT NULL,
  tax     numeric(4,3)  NOT NULL DEFAULT 0.08,
  total   numeric(12,2) GENERATED ALWAYS AS (price * (1 + tax)) STORED
);
```

### Default expressions

Defaults can reference any immutable or stable function.

```sql
CREATE TABLE sessions (
  id          uuid DEFAULT gen_random_uuid(),
  token       text DEFAULT encode(gen_random_bytes(24), 'base64'),
  expires_at  timestamptz DEFAULT now() + interval '30 days'
);
```

### Unlogged tables

Skip WAL for speed; data is truncated on crash. Good for caches, ETL staging.

```sql
CREATE UNLOGGED TABLE staging_imports (LIKE canonical_imports INCLUDING ALL);
```

### Temporary tables

Session-scoped; dropped automatically. `ON COMMIT DROP` for transaction scope.

```sql
CREATE TEMP TABLE scratch (id int, val text) ON COMMIT DROP;
```

### LIKE and INHERITS

`LIKE` copies structure; `INHERITS` creates an is-a relationship (legacy pattern, use partitioning instead).

```sql
CREATE TABLE audit_users (LIKE users INCLUDING DEFAULTS INCLUDING CONSTRAINTS);
```

### ALTER TABLE

Schema changes with surgical precision. Most are fast; `ADD COLUMN ... DEFAULT` is fast since Postgres 11.

```sql
ALTER TABLE books ADD COLUMN subtitle text;
ALTER TABLE books ALTER COLUMN title TYPE varchar(500);
ALTER TABLE books DROP COLUMN subtitle;
ALTER TABLE books RENAME COLUMN published TO release_date;
ALTER TABLE books SET (fillfactor = 80);
```

### DROP TABLE

`CASCADE` drops dependents; `RESTRICT` (default) fails if any exist.

```sql
DROP TABLE IF EXISTS books CASCADE;
```

---

## Constraints

Constraints are where you tell the database the rules your data must always obey, and the strategic point — easy to underweight when you're moving fast — is that **a constraint enforced by the database holds against every writer, forever, including the buggy migration, the manual `psql` fix at 2am, and the second application nobody told you about**, whereas the same rule enforced only in application code holds exactly until one of those bypasses it. Constraints are the cheapest correctness you can buy: declared once, checked by the engine on every write, impossible to forget. The catalog below runs from the everyday (primary keys, `NOT NULL`, foreign keys) through the underused power tools — `CHECK` constraints that encode domain rules, `EXCLUDE` constraints that express "no two bookings overlap for the same room" in a way no `UNIQUE` index can, and `DEFERRABLE` constraints that let you violate a rule transiently within a transaction as long as it holds at commit. The one operational subtlety worth carrying into production, developed in the `NOT VALID + VALIDATE` entry, is that adding a constraint to a large existing table can lock it while every row is checked — so the two-step pattern (`ADD CONSTRAINT ... NOT VALID`, then `VALIDATE CONSTRAINT` in a separate, weaker-locking pass) is how you add integrity to a live table without an outage.

### Primary keys & uniqueness

Either column-level or table-level. Multi-column versions are table-level.

```sql
CREATE TABLE memberships (
  user_id   bigint NOT NULL,
  group_id  bigint NOT NULL,
  PRIMARY KEY (user_id, group_id)
);

ALTER TABLE users ADD CONSTRAINT users_email_lower_unique UNIQUE (lower(email));
```

### NOT NULL

Cheapest, strongest constraint — use liberally.

```sql
ALTER TABLE users ALTER COLUMN email SET NOT NULL;
```

### CHECK

Arbitrary boolean predicate. Evaluated per row.

```sql
ALTER TABLE orders ADD CONSTRAINT orders_total_positive CHECK (total >= 0);
ALTER TABLE events ADD CONSTRAINT events_kind_known
  CHECK (kind IN ('login','logout','error'));
```

### Foreign keys

Referential integrity. `ON DELETE`/`ON UPDATE` actions: `NO ACTION` (default, deferred check), `RESTRICT` (immediate), `CASCADE`, `SET NULL`, `SET DEFAULT`.

```sql
CREATE TABLE comments (
  id       bigint PRIMARY KEY,
  post_id  bigint REFERENCES posts(id) ON DELETE CASCADE,
  author   bigint REFERENCES users(id) ON DELETE SET NULL
);
```

### Deferrable constraints

Check at end of transaction instead of end of statement. Useful for circular FKs or bulk loads.

```sql
ALTER TABLE a ADD CONSTRAINT a_b_fk FOREIGN KEY (b_id) REFERENCES b(id)
  DEFERRABLE INITIALLY IMMEDIATE;

BEGIN;
SET CONSTRAINTS a_b_fk DEFERRED;
-- ... do work that temporarily violates the constraint ...
COMMIT;
```

### Exclusion constraints

Generalized uniqueness. "No two rows can satisfy predicate X." Classic use: no overlapping time ranges.

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE room_bookings (
  room_id  int,
  during   tstzrange,
  EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);
```

### NOT VALID + VALIDATE

Add a constraint without scanning existing rows, then validate later without blocking writes.

```sql
ALTER TABLE orders ADD CONSTRAINT orders_total_nonneg CHECK (total >= 0) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_total_nonneg;
```

---

## Indexes

An index is a trade: it makes reads that match it dramatically faster at the cost of slowing every write (which must now update the index too) and consuming storage. Getting indexing right is therefore the highest-leverage performance skill in Postgres, and the mental model to hold is that **an index exists to let the planner avoid reading rows it doesn't need** — so the question for any index is always "which query will use this, and does the planner agree it should?" (a question `EXPLAIN`, covered in the [Advanced guide](ADVANCED_POSTGRES.md), answers directly). Postgres's distinctive strength here is that it has *many* index types beyond the default, each matched to a kind of query the B-tree handles badly: **B-tree** for the equality and range queries that are 90% of an OLTP workload; **GIN** for "does this container hold this element" (the index behind fast `jsonb` containment, array membership, and full-text search); **GiST** for overlap and nearest-neighbor (ranges, geometry, the exclusion constraints from the previous section); **BRIN** for enormous append-ordered tables where a tiny index over block ranges replaces a huge B-tree; and **Hash** for equality-only lookups. Layered on top are the modifiers that turn a good index into the right one — **partial** indexes that cover only the rows you query (indexing only `WHERE status = 'active'` to keep the index small and hot), **expression** indexes over `lower(email)` or a `jsonb` path, and **covering** indexes that `INCLUDE` extra columns so the query never touches the table at all. The entries below walk each; the through-line is that the index type and modifiers should be chosen from the *query shape*, not added reflexively to columns, because every index you don't need is pure write-path tax.

### B-tree (default)

Ordered index for equality, range, and sort operations. Supports multi-column and covering indexes.

```sql
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON orders (customer_id, created_at DESC);
```

### UNIQUE

Enforces uniqueness. Null values are distinct by default; `NULLS NOT DISTINCT` (PG15+) treats nulls as equal.

```sql
CREATE UNIQUE INDEX users_email_key ON users (lower(email));
CREATE UNIQUE INDEX ON users (tenant_id, email) NULLS NOT DISTINCT;
```

### Partial indexes

Index only rows matching a predicate. Smaller, faster, great for soft-delete or hot subsets.

```sql
CREATE INDEX active_users_email ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX recent_orders ON orders (created_at) WHERE status = 'pending';
```

### Expression indexes

Index a computed value so queries on the same expression can use it.

```sql
CREATE INDEX users_lower_email ON users (lower(email));
CREATE INDEX events_day ON events (date_trunc('day', created_at));
```

### Covering indexes (INCLUDE)

Include extra columns in the leaf pages so index-only scans can serve the query.

```sql
CREATE INDEX ON orders (customer_id) INCLUDE (total, status);
```

### GIN (Generalized Inverted)

For multi-value columns: arrays, `jsonb`, `tsvector`, `hstore`.

```sql
CREATE INDEX events_data_gin   ON events USING GIN (data);
CREATE INDEX posts_tags_gin    ON posts  USING GIN (tags);
CREATE INDEX docs_search_gin   ON docs   USING GIN (to_tsvector('english', body));
```

Fast reads, slow writes. Use `fastupdate = off` + bigger `gin_pending_list_limit` for write-heavy loads.

### GiST (Generalized Search Tree)

For geometric, range, and fuzzy types. Extensible.

```sql
CREATE INDEX bookings_during_gist ON room_bookings USING GIST (during);
CREATE INDEX products_name_trgm   ON products USING GIST (name gist_trgm_ops);
```

### SP-GiST

Space-partitioned GiST. Good for non-balanced data: IP prefixes, phone numbers, point clouds.

```sql
CREATE INDEX ips_sp ON requests USING SPGIST (client_ip inet_ops);
```

### BRIN

Block Range INdex — tiny index over large tables where values correlate with physical order. Great for time-series.

```sql
CREATE INDEX events_ts_brin ON events USING BRIN (created_at) WITH (pages_per_range = 64);
```

### Hash

Equality-only. Smaller than B-tree for wide keys. WAL-logged since Postgres 10.

```sql
CREATE INDEX ON sessions USING HASH (token);
```

### CONCURRENTLY

Builds the index without blocking writes. Two scans; slower wall-clock but safer in production.

```sql
CREATE INDEX CONCURRENTLY ON big_table (col);
DROP INDEX CONCURRENTLY old_idx;
REINDEX INDEX CONCURRENTLY some_idx;
```

If it fails, the index is left `INVALID` — drop and retry.

### Multi-index bitmap scans

The planner can combine multiple indexes in one query via bitmap AND/OR. You don't need a composite index for every pair.

```sql
EXPLAIN SELECT * FROM orders WHERE customer_id = 42 AND status = 'paid';
-- Might show: BitmapAnd(BitmapIndexScan on idx_customer, BitmapIndexScan on idx_status)
```

---

## Query Features

### DISTINCT ON

"Get one row per group, choosing the first by some ordering." Postgres-specific, indispensable.

```sql
-- Most recent order per customer
SELECT DISTINCT ON (customer_id) *
FROM orders
ORDER BY customer_id, created_at DESC;
```

### VALUES

Inline rowset. Works anywhere a table does.

```sql
SELECT * FROM (VALUES (1,'a'), (2,'b'), (3,'c')) AS t(id, label);

UPDATE users u
SET name = v.name
FROM (VALUES (1,'Alice'), (2,'Bob')) AS v(id, name)
WHERE u.id = v.id;
```

### RETURNING

Get back rows from any DML. Huge for one-shot insert-and-read flows.

```sql
INSERT INTO orders (customer_id, total) VALUES (42, 99.99)
RETURNING id, created_at;

DELETE FROM sessions WHERE expires_at < now()
RETURNING id;
```

### FETCH / OFFSET

SQL-standard pagination. Prefer keyset pagination for large tables.

```sql
SELECT * FROM books ORDER BY id
OFFSET 100 FETCH FIRST 25 ROWS ONLY;

-- Keyset (faster for deep pages)
SELECT * FROM books WHERE id > 12345 ORDER BY id LIMIT 25;
```

### GROUPING SETS, ROLLUP, CUBE

Multiple aggregation groupings in one pass.

```sql
SELECT region, product, SUM(amount)
FROM sales
GROUP BY ROLLUP (region, product);

SELECT region, product, SUM(amount)
FROM sales
GROUP BY GROUPING SETS ((region), (product), ());
```

### FILTER clause

Per-aggregate filter — cleaner than `CASE WHEN`.

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE status = 'paid') AS paid,
  SUM(amount) FILTER (WHERE created_at >= now() - interval '7 days') AS week_sum
FROM orders;
```

### String aggregation

`string_agg`, `array_agg`, `jsonb_agg`, `jsonb_object_agg`.

```sql
SELECT customer_id, string_agg(product, ', ' ORDER BY product)
FROM orders
GROUP BY customer_id;
```

### Ordinality in set-returning functions

`WITH ORDINALITY` attaches a 1-based position.

```sql
SELECT * FROM unnest(ARRAY['a','b','c']) WITH ORDINALITY AS t(val, pos);
```

---

## JSON & JSONB

### Operators

| Op   | What it does                                |
|------|---------------------------------------------|
| `->` | Get field / array element as `jsonb`        |
| `->>`| Get field / array element as `text`         |
| `#>` | Get nested path as `jsonb`                  |
| `#>>`| Get nested path as `text`                   |
| `@>` | Contains (left contains right)              |
| `<@` | Contained by                                |
| `?`  | Does key exist?                             |
| `?|` | Does *any* of these keys exist?             |
| `?&` | Do *all* of these keys exist?               |
| `||` | Concatenate / merge (shallow)               |
| `-`  | Remove key or array element                 |
| `#-` | Remove path                                 |

```sql
SELECT data->'user'->>'email'          FROM events;
SELECT data #>> '{user,address,city}'  FROM events;
SELECT * FROM events WHERE data @> '{"kind":"login"}';
SELECT * FROM events WHERE data ? 'ip';
```

### Modifying functions

```sql
UPDATE events SET data = jsonb_set(data, '{user,email}', '"new@example.com"');
UPDATE events SET data = data - 'ip';              -- delete key
UPDATE events SET data = data #- '{user,temp}';    -- delete path
UPDATE events SET data = data || '{"audited":true}';  -- merge
```

### Construction

```sql
SELECT jsonb_build_object('a', 1, 'b', 2, 'ts', now());
SELECT jsonb_build_array(1, 'two', true);
SELECT to_jsonb(ROW(1, 'hi'));

-- Aggregate rows into json
SELECT jsonb_agg(row_to_json(o)) FROM orders o WHERE customer_id = 42;
```

### Decomposition

```sql
SELECT * FROM jsonb_each_text('{"a":"1","b":"2"}');
SELECT * FROM jsonb_array_elements('[10,20,30]');
SELECT * FROM jsonb_object_keys('{"a":1,"b":2}');

-- Extract structured fields from jsonb into columns
SELECT * FROM jsonb_to_record('{"id":1,"name":"x"}') AS t(id int, name text);
SELECT * FROM jsonb_to_recordset('[{"id":1},{"id":2}]') AS t(id int);
```

### JSONPath (Postgres 12+)

SQL/JSON Path language — similar to XPath for JSON.

```sql
SELECT jsonb_path_query(data, '$.items[*] ? (@.price > 100)')
FROM orders;

SELECT jsonb_path_exists(data, '$.user.email');
SELECT jsonb_path_query_first(data, '$.items[0].sku');
```

### Indexing JSONB

```sql
-- Broad: supports @>, ?, ?&, ?|
CREATE INDEX events_data_gin ON events USING GIN (data);

-- Tighter: only @>, but smaller and faster
CREATE INDEX events_data_gin_path ON events USING GIN (data jsonb_path_ops);

-- Expression index for a hot field
CREATE INDEX events_user_id ON events ((data->>'user_id'));
```

---

## Arrays

### Basics

```sql
SELECT ARRAY[1,2,3];
SELECT '{1,2,3}'::int[];
SELECT ARRAY[1,2,3] || 4;        -- append: {1,2,3,4}
SELECT 0 || ARRAY[1,2,3];        -- prepend: {0,1,2,3}
SELECT array_length(ARRAY[1,2,3], 1);
SELECT cardinality(ARRAY[[1,2],[3,4]]);  -- 4
```

### Operators

```sql
SELECT ARRAY[1,2,3] @> ARRAY[2];       -- contains
SELECT ARRAY[1,2,3] && ARRAY[3,4];     -- overlap (any in common)
SELECT 2 = ANY(ARRAY[1,2,3]);          -- element in array
SELECT ARRAY[1,2,3] = ARRAY[1,2,3];    -- element-wise equality
```

### unnest / array_agg

Roundtripping between rows and arrays.

```sql
SELECT * FROM unnest(ARRAY['a','b','c']) AS x;

SELECT array_agg(name ORDER BY name) FROM users WHERE tenant_id = 1;
```

### Array slices and updates

```sql
SELECT (ARRAY[10,20,30,40])[2:3];   -- {20,30}
UPDATE t SET tags[2] = 'new'  WHERE id = 1;
UPDATE t SET tags = array_append(tags, 'extra') WHERE id = 1;
UPDATE t SET tags = array_remove(tags, 'old')   WHERE id = 1;
```

### Indexing

```sql
CREATE INDEX posts_tags_gin ON posts USING GIN (tags);
```

---

## Ranges

### Construction

```sql
SELECT int4range(1, 10);              -- [1,10)
SELECT int4range(1, 10, '[]');        -- [1,10]
SELECT tstzrange('2026-01-01', null); -- unbounded upper
```

### Operators

```sql
SELECT int4range(1,10) @> 5;               -- contains element
SELECT int4range(1,10) @> int4range(3,7);  -- contains range
SELECT int4range(1,10) && int4range(5,20); -- overlap
SELECT int4range(1,5)  -|- int4range(5,10);-- adjacent
SELECT lower(int4range(1,10)), upper(int4range(1,10));
```

### Practical pattern: non-overlapping schedules

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE reservations (
  id       bigint GENERATED ALWAYS AS IDENTITY,
  room_id  int NOT NULL,
  during   tstzrange NOT NULL,
  EXCLUDE USING GIST (room_id WITH =, during WITH &&)
);
```

### Multiranges (PG 14+)

Collections of non-overlapping ranges as a single value.

```sql
SELECT int4multirange(int4range(1,5), int4range(10,15));
SELECT range_agg(during) FROM reservations WHERE room_id = 7;
```

---

## Full-Text Search

### tsvector and tsquery

```sql
SELECT to_tsvector('english', 'The quick brown foxes jumped');
--> 'brown':3 'fox':4 'jump':5 'quick':2

SELECT to_tsvector('english', 'foxes jumped') @@ to_tsquery('english', 'fox & jump');
```

### Indexing and ranking

```sql
ALTER TABLE docs ADD COLUMN search tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body,  '')), 'B')
  ) STORED;

CREATE INDEX docs_search_gin ON docs USING GIN (search);

SELECT id, ts_rank(search, q) AS rank
FROM docs, to_tsquery('english', 'postgres & index') q
WHERE search @@ q
ORDER BY rank DESC
LIMIT 20;
```

### Phrase search and proximity

```sql
SELECT to_tsvector('english','the quick brown fox') @@ phraseto_tsquery('english','quick brown');
SELECT websearch_to_tsquery('english', '"postgres index" -hash');
```

### Highlighting

```sql
SELECT ts_headline('english', body, websearch_to_tsquery('english', 'postgres'),
                   'StartSel=<b>, StopSel=</b>')
FROM docs WHERE id = 1;
```

### Dictionaries and configurations

```sql
\dF              -- list configurations (in psql)
\dFd             -- list dictionaries

-- Use a different language per row
SELECT to_tsvector(language_col::regconfig, body) FROM multilingual_docs;
```

---

## Pattern Matching

### LIKE / ILIKE

```sql
SELECT * FROM users WHERE email LIKE '%@example.com';
SELECT * FROM users WHERE name ILIKE 'al%';  -- case-insensitive
```

### POSIX regex

`~` (match), `!~` (no match), `~*` / `!~*` (case-insensitive).

```sql
SELECT email FROM users WHERE email ~* '^admin';
SELECT regexp_match('order-123', '(\w+)-(\d+)');
SELECT regexp_replace('  hi  ', '^\s+|\s+$', '', 'g');
SELECT * FROM regexp_split_to_table('a,b,,c', ',');
```

### Trigram fuzzy search

Via `pg_trgm` — similarity, distance, and fast `LIKE '%x%'` via GIN.

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX ON users USING GIN (name gin_trgm_ops);

SELECT name, similarity(name, 'Alicia') AS s
FROM users
WHERE name % 'Alicia'          -- similarity above threshold
ORDER BY s DESC;

-- Distance operator (useful for nearest-neighbor ORDER BY)
SELECT name FROM users ORDER BY name <-> 'Alicia' LIMIT 5;
```

---

## Transactions & Isolation

A transaction is the unit of all-or-nothing work, and Postgres's MVCC implementation (from the mental model up top) gives it an unusually pleasant property: because every write creates a new row version rather than overwriting, **readers never block writers and writers never block readers**, so a long analytical query and a busy write workload coexist without the lock contention that defines this problem in lock-based databases. What you still must choose is the **isolation level** — how much the concurrent activity of *other* transactions is allowed to leak into yours — and this is a genuine engineering decision, not a knob to leave at default and forget, because the levels trade consistency against the rate at which transactions must be retried. **Read Committed** (the default) sees each statement against a fresh snapshot, so two statements in one transaction can see different data — fine for most OLTP, but it permits anomalies that surprise people (a row counted in one query and changed before the next). **Repeatable Read** gives the whole transaction one snapshot, eliminating those anomalies but introducing serialization failures you must be prepared to retry. **Serializable** is the strongest, guaranteeing the result is *as if* transactions ran one at a time, by detecting dangerous patterns and aborting one of the conflicting transactions with a serialization error — which means code using it must wrap transactions in a retry loop, the price of the guarantee. The mechanism beneath all of this, and the reason a forgotten open transaction is a production hazard, is that MVCC must keep old row versions alive as long as *any* transaction might still need to see them — so a transaction left open for hours blocks `VACUUM` from reclaiming dead rows across the whole database, which is the [Advanced guide](ADVANCED_POSTGRES.md)'s most-repeated operational warning. The entries below cover the syntax, the levels, and savepoints; the decision to take away is that isolation level is chosen per workload from the anomalies it can tolerate and the retry logic it can afford.

### Basics

```sql
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;  -- or ROLLBACK
```

### Savepoints

Partial rollback inside a transaction.

```sql
BEGIN;
  INSERT INTO audit VALUES ('start');
  SAVEPOINT before_risky;
    DELETE FROM big_table WHERE condition;
  ROLLBACK TO before_risky;
  INSERT INTO audit VALUES ('rolled back');
COMMIT;
```

### Isolation levels

| Level              | Dirty read | Non-repeat read | Phantom | Serialization anomaly |
|--------------------|:---------:|:---------------:|:-------:|:---------------------:|
| Read Uncommitted\* | no        | possible        | possible| possible              |
| Read Committed     | no        | possible        | possible| possible              |
| Repeatable Read    | no        | no              | no      | possible              |
| Serializable       | no        | no              | no      | no                    |

\*In Postgres, `READ UNCOMMITTED` behaves as `READ COMMITTED`.

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;
-- ...
COMMIT;

-- Or per session
SET default_transaction_isolation = 'repeatable read';
```

### Serialization failures

Serializable and Repeatable Read can raise `could not serialize access due to concurrent update` (SQLSTATE 40001). Retry the whole transaction — don't patch over it.

### Read-only / deferrable

```sql
BEGIN READ ONLY DEFERRABLE ISOLATION LEVEL SERIALIZABLE;
-- great for long analytical snapshots without serialization risk
COMMIT;
```

### Transaction-local settings

```sql
BEGIN;
  SET LOCAL statement_timeout = '30s';
  SET LOCAL lock_timeout = '2s';
  -- ...
COMMIT;
```

---

## Locking

### Row locks (SELECT ... FOR ...)

```sql
-- Strong: blocks other writers and other SELECT FOR UPDATE
SELECT * FROM orders WHERE id = 42 FOR UPDATE;

-- Weaker variants
SELECT ... FOR NO KEY UPDATE;
SELECT ... FOR SHARE;
SELECT ... FOR KEY SHARE;

-- Don't block — skip or fail
SELECT ... FOR UPDATE SKIP LOCKED;  -- great for queue workers
SELECT ... FOR UPDATE NOWAIT;
```

### Table locks (LOCK)

Explicit, rarely needed. Various modes from `ACCESS SHARE` (reads) up to `ACCESS EXCLUSIVE` (the hammer).

```sql
BEGIN;
LOCK TABLE orders IN SHARE ROW EXCLUSIVE MODE;
-- ...
COMMIT;
```

### Advisory locks

Application-level locks keyed by `bigint` (or two `int`s). Postgres doesn't interpret them; you coordinate.

```sql
-- Transaction-scoped (released at COMMIT/ROLLBACK)
SELECT pg_advisory_xact_lock(12345);

-- Session-scoped
SELECT pg_try_advisory_lock(hashtext('nightly-job')::bigint);
-- ...
SELECT pg_advisory_unlock(hashtext('nightly-job')::bigint);
```

### Inspecting locks

```sql
SELECT pid, relation::regclass, mode, granted
FROM pg_locks
WHERE NOT granted;

SELECT blocked.pid    AS blocked_pid,
       blocked.query  AS blocked_query,
       blocker.pid    AS blocker_pid,
       blocker.query  AS blocker_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocker
  ON blocker.pid = ANY(pg_blocking_pids(blocked.pid));
```

---

## Upserts & MERGE

### ON CONFLICT (UPSERT)

Idiomatic Postgres. Target a unique constraint or column list.

```sql
-- Do nothing on conflict
INSERT INTO users (email, name) VALUES ('a@x', 'Alice')
ON CONFLICT (email) DO NOTHING;

-- Update on conflict
INSERT INTO counters (name, n) VALUES ('hits', 1)
ON CONFLICT (name) DO UPDATE SET n = counters.n + EXCLUDED.n;

-- Conditional update
INSERT INTO kv (k, v, updated_at) VALUES ('foo', 'bar', now())
ON CONFLICT (k) DO UPDATE SET
  v = EXCLUDED.v,
  updated_at = EXCLUDED.updated_at
WHERE kv.updated_at < EXCLUDED.updated_at;
```

`EXCLUDED` refers to the row you tried to insert.

### MERGE (PG 15+, RETURNING in 17+)

SQL-standard multi-action merge. More expressive than `ON CONFLICT` when you also need to delete or take actions on matched rows.

```sql
MERGE INTO inventory i
USING incoming_sales s ON i.sku = s.sku
WHEN MATCHED AND s.qty > 0 THEN
  UPDATE SET stock = i.stock - s.qty
WHEN MATCHED AND s.qty = 0 THEN
  DELETE
WHEN NOT MATCHED THEN
  INSERT (sku, stock) VALUES (s.sku, -s.qty);
```

Gotcha: `MERGE` does not detect concurrent inserts like `ON CONFLICT` does. For pure upsert, `ON CONFLICT` is still the safe pick.

---

## CTEs & Window Functions

### Basic CTE

Postgres 12+ treats CTEs as optimization fences only when marked `MATERIALIZED`. Plain CTEs are inlined when beneficial.

```sql
WITH recent AS (
  SELECT * FROM orders WHERE created_at > now() - interval '7 days'
)
SELECT customer_id, count(*) FROM recent GROUP BY customer_id;
```

### MATERIALIZED / NOT MATERIALIZED

```sql
WITH heavy AS MATERIALIZED (
  SELECT * FROM huge_fn(42)   -- force one-time execution
)
SELECT a.*, h.x FROM a JOIN heavy h ON ...;
```

### Writable CTEs

DML in a CTE, then use the returned rows downstream.

```sql
WITH deleted AS (
  DELETE FROM sessions WHERE expires_at < now() RETURNING user_id
)
INSERT INTO audit (user_id, event)
SELECT user_id, 'session_expired' FROM deleted;
```

### Recursive CTEs

Graph walks, hierarchies, series generation.

```sql
-- All descendants of category 42
WITH RECURSIVE tree AS (
  SELECT id, parent_id, name FROM categories WHERE id = 42
  UNION ALL
  SELECT c.id, c.parent_id, c.name
  FROM categories c JOIN tree t ON c.parent_id = t.id
)
SELECT * FROM tree;
```

### SEARCH and CYCLE

Order and cycle detection baked in (SQL-standard, PG 14+).

```sql
WITH RECURSIVE tree AS (
  SELECT id, parent_id FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, c.parent_id
  FROM categories c JOIN tree t ON c.parent_id = t.id
) SEARCH DEPTH FIRST BY id SET ord
  CYCLE id SET is_cycle USING path
SELECT * FROM tree;
```

### Window functions

Ranking, offsets, running aggregates — without collapsing rows.

```sql
SELECT
  customer_id,
  created_at,
  total,
  ROW_NUMBER()   OVER w          AS rn,
  RANK()         OVER w          AS rk,
  DENSE_RANK()   OVER w          AS drk,
  SUM(total)     OVER w          AS running_total,
  LAG(total)     OVER w          AS prev_total,
  LEAD(total, 1) OVER w          AS next_total,
  FIRST_VALUE(total) OVER w,
  NTH_VALUE(total, 3) OVER w,
  NTILE(4)           OVER w      AS quartile
FROM orders
WINDOW w AS (PARTITION BY customer_id ORDER BY created_at);
```

### Custom frames

```sql
SUM(total) OVER (
  PARTITION BY customer_id
  ORDER BY created_at
  ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
) AS rolling_7
```

---

## LATERAL Joins

A row-at-a-time subquery that can reference columns from earlier `FROM` items. Think "correlated subquery, but in the FROM clause."

```sql
-- Top 3 orders per customer, cheaply
SELECT c.id, o.*
FROM customers c
LEFT JOIN LATERAL (
  SELECT *
  FROM orders
  WHERE customer_id = c.id
  ORDER BY created_at DESC
  LIMIT 3
) o ON true;
```

Also used with set-returning functions:

```sql
SELECT u.id, tag
FROM users u, LATERAL unnest(u.tags) AS tag;
```

---

## Views & Materialized Views

### Views

Saved query. Always fresh.

```sql
CREATE VIEW active_users AS
SELECT * FROM users WHERE deleted_at IS NULL;
```

### Updatable views

Simple views auto-support `INSERT`/`UPDATE`/`DELETE`. Add `WITH CHECK OPTION` to reject rows that wouldn't be visible through the view.

```sql
CREATE VIEW my_orders AS
  SELECT * FROM orders WHERE customer_id = current_setting('app.user_id')::bigint
  WITH CHECK OPTION;
```

### INSTEAD OF triggers

Make a complex view writable by writing a trigger.

```sql
CREATE TRIGGER users_full_ins
INSTEAD OF INSERT ON users_full
FOR EACH ROW EXECUTE FUNCTION users_full_insert_fn();
```

### Materialized views

Cached query results on disk. Must be refreshed.

```sql
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT date_trunc('day', created_at) AS day, SUM(total) AS revenue
FROM orders
GROUP BY 1;

CREATE UNIQUE INDEX ON daily_revenue (day);

-- Blocking refresh
REFRESH MATERIALIZED VIEW daily_revenue;

-- Non-blocking (needs the unique index above)
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue;
```

---

## Partitioning

Partitioning splits one logically-single table into many physical child tables by a key (a date range, a tenant ID, a hash), with the parent acting as a routing template that the planner uses to skip irrelevant partitions entirely. The decision to internalize is *when* it earns its complexity, because partitioning is not a performance win you sprinkle on any large table — it pays off for two specific shapes. The first is **time-series data with a retention policy**: partition by month, and dropping last year's data becomes an instant `DROP TABLE` of a partition instead of a `DELETE` of millions of rows that bloats the table and thrashes `VACUUM`. The second is **queries that always filter on the partition key**, where the planner's *partition pruning* lets a query touch only the relevant partitions, turning a scan of the whole dataset into a scan of one slice. The cost side is real and worth respecting: partitioning complicates unique constraints (a global unique must include the partition key), foreign keys, and the planning of queries that *don't* filter on the key (which now must consider every partition), so the wrong partitioning scheme makes things slower, not faster. The entries below cover range, list, and hash partitioning and the maintenance of partition sets; the [Advanced guide](ADVANCED_POSTGRES.md) develops partitioning-at-scale, including how `pg_partman` automates the create-new/drop-old lifecycle that manual partitioning eventually demands.

### Range partitioning

```sql
CREATE TABLE events (
  id         bigint GENERATED ALWAYS AS IDENTITY,
  created_at timestamptz NOT NULL,
  payload    jsonb
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE events_default PARTITION OF events DEFAULT;
```

### List partitioning

```sql
CREATE TABLE accounts (region text, ...) PARTITION BY LIST (region);

CREATE TABLE accounts_us PARTITION OF accounts FOR VALUES IN ('us','usa');
CREATE TABLE accounts_eu PARTITION OF accounts FOR VALUES IN ('de','fr','it');
```

### Hash partitioning

Spread writes evenly when there's no natural key.

```sql
CREATE TABLE users (id bigint, ...) PARTITION BY HASH (id);
CREATE TABLE users_p0 PARTITION OF users FOR VALUES WITH (modulus 4, remainder 0);
-- ... and so on for p1, p2, p3
```

### Sub-partitioning

Range + list, range + hash, etc.

```sql
CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')
  PARTITION BY LIST (region);
```

### Attach/detach

Fast swap without rewriting data.

```sql
CREATE TABLE events_2026_05 (LIKE events INCLUDING ALL);
-- bulk-load events_2026_05
ALTER TABLE events ATTACH PARTITION events_2026_05
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Concurrent detach (PG14+) doesn't lock readers
ALTER TABLE events DETACH PARTITION events_2026_01 CONCURRENTLY;
```

### Indexes on partitioned tables

Index defined on parent propagates to all partitions (creates a "partitioned index"). Use `CREATE INDEX ... ON ONLY parent` + per-partition indexes to roll out concurrently.

```sql
CREATE INDEX ON events (created_at);  -- covers all partitions
```

### Partition pruning

The planner skips partitions that can't match the query's predicate. Works at planning and execution time.

```sql
EXPLAIN SELECT count(*) FROM events WHERE created_at >= date '2026-05-01';
```

---

## Inheritance

Predecessor to partitioning — still around. Children inherit columns from parent; `SELECT * FROM parent` returns from all children unless `ONLY` is used.

```sql
CREATE TABLE cities (name text, pop int);
CREATE TABLE capitals (country text) INHERITS (cities);

SELECT * FROM ONLY cities;   -- excludes capitals
```

Limits (no FK, no unique across children) are why partitioning mostly replaced this.

---

## Functions & Procedures

### SQL functions

Simplest form. Inlined by the planner when possible.

```sql
CREATE OR REPLACE FUNCTION full_name(u users)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT u.first_name || ' ' || u.last_name
$$;

SELECT full_name(u) FROM users u;
```

### PL/pgSQL functions

Procedural: loops, conditionals, exceptions.

```sql
CREATE OR REPLACE FUNCTION transfer(from_id bigint, to_id bigint, amt numeric)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE accounts SET balance = balance - amt WHERE id = from_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'source missing'; END IF;
  UPDATE accounts SET balance = balance + amt WHERE id = to_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'dest missing'; END IF;
EXCEPTION WHEN check_violation THEN
  RAISE EXCEPTION 'insufficient funds';
END
$$;
```

### Volatility

`IMMUTABLE` (same input → same output, no side effects), `STABLE` (constant within one scan), `VOLATILE` (default). Affects planning and index usability.

```sql
CREATE FUNCTION slugify(t text) RETURNS text IMMUTABLE LANGUAGE sql AS $$
  SELECT lower(regexp_replace(t, '\W+', '-', 'g'))
$$;

CREATE INDEX ON posts (slugify(title));  -- requires IMMUTABLE
```

### SECURITY DEFINER

Function runs with the privileges of its owner, not caller. Classic way to expose narrow operations to less-privileged roles. Pair with `SET search_path = pg_catalog, public` to avoid injection.

```sql
CREATE FUNCTION log_access() RETURNS void
  LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  INSERT INTO audit(who, at) VALUES (current_user, now())
$$;
```

### Set-returning functions

`RETURNS TABLE` or `RETURNS SETOF`.

```sql
CREATE FUNCTION recent_orders(cust bigint, n int)
RETURNS TABLE (id bigint, total numeric, created_at timestamptz)
LANGUAGE sql STABLE AS $$
  SELECT id, total, created_at
  FROM orders
  WHERE customer_id = cust
  ORDER BY created_at DESC
  LIMIT n
$$;

SELECT * FROM recent_orders(42, 5);
```

### Procedures (PG 11+)

Can `COMMIT` / `ROLLBACK` mid-procedure. Called with `CALL`, not `SELECT`.

```sql
CREATE PROCEDURE nightly_cleanup() LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM sessions WHERE expires_at < now();
  COMMIT;
  REINDEX TABLE sessions;
END
$$;

CALL nightly_cleanup();
```

### Other languages

`plpython3u`, `plperlu`, `plv8`, `pllua` — install via extension. `u` means untrusted (full host access); requires superuser.

---

## Triggers

### Row-level vs statement-level

Row triggers fire once per affected row; statement triggers fire once per DML statement.

```sql
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE TRIGGER users_touch
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();
```

### BEFORE vs AFTER

`BEFORE` can modify `NEW`/skip the operation (`RETURN NULL`). `AFTER` sees the final row and is better for side-effect bookkeeping.

```sql
CREATE TRIGGER orders_audit AFTER INSERT OR UPDATE OR DELETE
ON orders FOR EACH ROW EXECUTE FUNCTION audit_log();
```

### Transition tables

Access all affected rows in one go from a statement-level trigger.

```sql
CREATE TRIGGER orders_bulk
AFTER UPDATE ON orders
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
FOR EACH STATEMENT
EXECUTE FUNCTION orders_diff();
```

### Conditional triggers

`WHEN` predicate avoids the function call entirely.

```sql
CREATE TRIGGER recompute_summary
AFTER UPDATE ON line_items
FOR EACH ROW
WHEN (OLD.qty IS DISTINCT FROM NEW.qty OR OLD.price IS DISTINCT FROM NEW.price)
EXECUTE FUNCTION refresh_order_totals();
```

### Event triggers

Fire on DDL. Good for schema auditing.

```sql
CREATE OR REPLACE FUNCTION audit_ddl() RETURNS event_trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO ddl_log(who, command, at)
  VALUES (current_user, tg_tag, now());
END $$;

CREATE EVENT TRIGGER ddl_audit ON ddl_command_start EXECUTE FUNCTION audit_ddl();
```

---

## Rules

Query rewriting at parse time. Powerful and confusing — prefer triggers. Main modern use is making views writable (`INSTEAD OF` rules / triggers).

```sql
CREATE RULE no_deletes AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

---

## LISTEN / NOTIFY

Lightweight pub/sub inside a Postgres database. Payload limit ~8000 bytes.

```sql
-- Session A
LISTEN orders_channel;

-- Session B
NOTIFY orders_channel, 'new:42';
-- or with payload construction
SELECT pg_notify('orders_channel', jsonb_build_object('id', 42)::text);
```

Pair with a trigger to push changes:

```sql
CREATE FUNCTION orders_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify('orders_channel', NEW.id::text);
  RETURN NEW;
END $$;

CREATE TRIGGER orders_notify_t
AFTER INSERT ON orders
FOR EACH ROW EXECUTE FUNCTION orders_notify();
```

Caveats: delivered only on `COMMIT`, not durable, not replicated. Use a real queue if you need those.

---

## Row-Level Security

Row-Level Security (RLS) moves a tenant-isolation or per-user-visibility rule *into the database*, where it is evaluated automatically on every query against the table — and the reason that matters is the same reason constraints matter, applied to reads: a `WHERE tenant_id = current_setting('app.tenant')` filter enforced by RLS holds against *every* query from *every* code path, so the one report that forgot the tenant filter, the analyst poking at the table in `psql`, and the second service that read the table directly all get only the rows they're allowed, with no way to forget the filter because the database adds it. This is genuinely powerful for multi-tenant systems, where the alternative — relying on every query in a growing codebase to remember the isolation clause — is a cross-tenant data leak waiting for its first omission (the failure mode the [Web Security guide](../WEB_LLM_SECURITY_STUDY_GUIDE.md) catalogues). The two cautions to carry into a real deployment, both developed below: policies are bypassed by the table owner and superusers unless you `FORCE` them, so the role your application connects as must not be the table owner; and because every query now carries the policy's predicate, that predicate must be indexable, or RLS turns every read into a sequential scan. The entries below show enabling RLS, writing `USING` (read) and `WITH CHECK` (write) policies, and the session-variable pattern that carries the current tenant or user into the policy.

### Enable and add policies

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;  -- apply even to owner

CREATE POLICY owner_select ON documents
  FOR SELECT USING (owner_id = current_setting('app.user_id')::bigint);

CREATE POLICY owner_modify ON documents
  FOR ALL
  USING     (owner_id = current_setting('app.user_id')::bigint)
  WITH CHECK(owner_id = current_setting('app.user_id')::bigint);
```

`USING` gates reads; `WITH CHECK` gates what new/updated rows are allowed to look like.

### Setting the session variable

```sql
SET app.user_id = '42';
SELECT * FROM documents;  -- only rows where owner_id = 42
```

### Per-role policies

```sql
CREATE POLICY admin_all ON documents TO admin USING (true);
```

### Bypass

Role attribute `BYPASSRLS` skips policies entirely (for replication tools, etc.).

---

## Roles & Permissions

Postgres's permission model is built on one unifying idea that removes most of the confusion newcomers bring to it: **there is no separate concept of "users" and "groups" — there are only roles**, and a role is a "user" when it has the `LOGIN` attribute and a "group" when other roles are granted membership in it. That single abstraction is what lets you build a clean, maintainable access model: define group roles by *function* (`readers`, `writers`, `app_runtime`), grant the actual privileges to those groups, and then grant group membership to the login roles — so onboarding a new service is one `GRANT readers TO ...` rather than re-deriving a pile of table grants, and an access review reads as "who is a member of `writers`" instead of an audit of scattered individual permissions. The privilege system itself layers grants on objects (`GRANT SELECT ON orders TO ...`) with the subtlety that privileges on *future* objects need `ALTER DEFAULT PRIVILEGES` (a fresh table grants access to nobody by default, the source of the perennial "I granted the schema but the new table isn't readable" surprise). The principle to carry, and the one the [Kubernetes Security](../k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md) and [Web Security](../WEB_LLM_SECURITY_STUDY_GUIDE.md) guides echo in their own domains, is least privilege: the role your application connects as should hold exactly the rights it uses and own nothing it doesn't, so that a SQL injection or a leaked connection string is bounded by what that role can do rather than opening the whole database.

### Roles

Users and groups are both roles — differ only in the `LOGIN` attribute.

```sql
CREATE ROLE app_user LOGIN PASSWORD 'secret';
CREATE ROLE readers;                    -- group role, no login
GRANT readers TO app_user;
```

### GRANT / REVOKE

```sql
GRANT SELECT, INSERT ON orders TO app_user;
GRANT USAGE ON SCHEMA reporting TO readers;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO readers;

-- Future objects get the grant too
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting
  GRANT SELECT ON TABLES TO readers;
```

### Column-level grants

```sql
GRANT SELECT (id, email) ON users TO support;
```

### Role attributes

`SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, `BYPASSRLS`, `LOGIN`, `INHERIT` / `NOINHERIT`.

```sql
ALTER ROLE etl_loader REPLICATION;
```

### SET ROLE

Temporarily act as another role (for impersonation/testing).

```sql
SET ROLE readers;
SELECT * FROM private_table;  -- fails if readers lacks access
RESET ROLE;
```

### Password encryption

`scram-sha-256` is the default (since PG 14). Keep it; `md5` is legacy.

---

## Schemas & Search Path

Schemas are namespaces. `public` is the default. `search_path` decides how unqualified names resolve.

```sql
CREATE SCHEMA reporting;
CREATE TABLE reporting.daily_stats (...);

SET search_path = reporting, public;
SELECT * FROM daily_stats;   -- resolves to reporting.daily_stats

-- Per-role default
ALTER ROLE app_user SET search_path = app, public;
```

`SECURITY DEFINER` functions should always pin `search_path` — otherwise callers can shadow objects.

---

## Sequences

Counter objects — back IDENTITY columns and can be used directly.

```sql
CREATE SEQUENCE order_no START 1000 INCREMENT 1 CACHE 50;

SELECT nextval('order_no');     -- 1000
SELECT currval('order_no');     -- last value in this session
SELECT setval('order_no', 2000);

ALTER SEQUENCE order_no RESTART WITH 1;
```

Owned-by ties a sequence to a column; `serial` did this implicitly. `IDENTITY` does it cleanly.

---

## COPY & Bulk Loading

Fastest way to load/export data.

### Server-side COPY

Reads/writes files on the server; requires superuser or `pg_read_server_files` / `pg_write_server_files`.

```sql
COPY orders FROM '/var/data/orders.csv' WITH (FORMAT csv, HEADER true);
COPY (SELECT * FROM orders WHERE created_at > now() - interval '1 day')
  TO '/tmp/yesterday.csv' WITH (FORMAT csv, HEADER true);
```

### Client-side \copy (psql)

Same format, reads/writes on the client. No special privileges.

```sql
\copy orders FROM 'orders.csv' CSV HEADER
\copy (SELECT * FROM orders) TO 'orders.csv' CSV HEADER
```

### Fast-load pattern

```sql
BEGIN;
CREATE UNLOGGED TABLE staging (LIKE orders INCLUDING DEFAULTS);
\copy staging FROM 'orders.csv' CSV HEADER
INSERT INTO orders SELECT * FROM staging;
DROP TABLE staging;
COMMIT;
```

Extra gains: drop indexes before load and recreate after; raise `maintenance_work_mem`; use `COPY (FREEZE)` inside the same transaction that created the table.

---

## Foreign Data Wrappers

Query remote data as if it were local tables. Built-in FDW for other Postgres servers (`postgres_fdw`) plus extensions for MySQL, Oracle, files, S3, etc.

```sql
CREATE EXTENSION postgres_fdw;

CREATE SERVER remote_db FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host 'db.internal', dbname 'sales', port '5432');

CREATE USER MAPPING FOR CURRENT_USER SERVER remote_db
  OPTIONS (user 'reader', password '...');

IMPORT FOREIGN SCHEMA public LIMIT TO (orders, customers)
  FROM SERVER remote_db INTO ext;

SELECT count(*) FROM ext.orders;
```

Predicates and joins are pushed to the remote when possible — check `EXPLAIN`.

---

## Extensions

Managed plugins; installed via `CREATE EXTENSION`.

### Catalog high-value extensions

| Extension             | What it does                                              |
|-----------------------|-----------------------------------------------------------|
| `pg_stat_statements`  | Aggregates per-query execution stats                      |
| `pg_trgm`             | Trigram-based fuzzy search + fast `LIKE`                  |
| `btree_gin`/`btree_gist` | Let GIN/GiST index scalar types too                    |
| `pgcrypto`            | Hashes, AES, HMAC, random bytes                           |
| `uuid-ossp`           | UUID generators (v1/v3/v4/v5) — use `gen_random_uuid` now |
| `citext`              | Case-insensitive text                                     |
| `hstore`              | Key/value type (legacy — prefer jsonb)                    |
| `ltree`               | Labeled tree paths                                        |
| `postgis`             | Full GIS: geometry/geography, spatial indexes             |
| `pgvector`            | Vector similarity search (AI embeddings)                  |
| `timescaledb`         | Time-series superpowers                                   |
| `pg_partman`          | Automated partition management                            |
| `pgaudit`             | Fine-grained session/object auditing                      |
| `plpgsql_check`       | Static analysis for PL/pgSQL                              |
| `pg_repack`           | Rebuild bloated tables/indexes without long locks         |
| `pg_cron`             | In-database scheduled jobs                                |

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\dx      -- in psql: list installed extensions
```

### pgvector example

```sql
CREATE EXTENSION vector;

CREATE TABLE docs (
  id       bigint PRIMARY KEY,
  body     text,
  embedding vector(1536)
);

CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops);

SELECT id FROM docs ORDER BY embedding <=> $1 LIMIT 10;
```

### pg_cron example

```sql
CREATE EXTENSION pg_cron;

SELECT cron.schedule('nightly-cleanup', '0 3 * * *',
  $$DELETE FROM sessions WHERE expires_at < now()$$);
```

---

## psql Essentials

### Connecting

```bash
psql "postgres://user:pass@host:5432/db?sslmode=require"
psql -h host -U user -d db
```

Uses `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` env vars and `~/.pgpass` for passwords.

### Meta-commands

```
\l              list databases
\c db           connect
\dn             schemas
\dt [pattern]   tables
\d name         describe
\di             indexes
\dv             views
\dmv            materialized views
\df             functions
\du             roles
\dx             extensions
\timing         toggle timing
\x              toggle expanded display
\e              edit last query in $EDITOR
\i file.sql     run script
\! cmd          run shell command
\watch 2        rerun every 2s
\copy ...       client-side COPY
\pset           output format options
\o file         redirect output
```

### Variables & scripting

```sql
\set user_id 42
SELECT * FROM users WHERE id = :user_id;

\set verbose on
\if :verbose
  \echo 'verbose mode'
\endif
```

### Useful .psqlrc

```
\set HISTFILE ~/.psql_history-:DBNAME
\set PROMPT1 '%[%033[1;33m%]%n@%/%R%#%x%[%033[0m%] '
\timing on
\x auto
\pset null '(null)'
```

---

## Next Steps & Further Reading

You've covered the SQL surface area. To understand *why* queries are fast or slow and how to run Postgres in production, continue to the companion:

**→ [Advanced PostgreSQL Study Guide](ADVANCED_POSTGRES.md)** — MVCC internals & bloat, WAL & checkpoints, VACUUM/wraparound, the query planner & statistics, reading `EXPLAIN`, indexing strategy, locking at scale, connection pooling, the performance tuning ladder, partitioning, replication & HA, backup/PITR, observability, production pitfalls, benchmarking, and worked recipes.

- Official docs: https://www.postgresql.org/docs/current/
- Postgres Wiki (tuning, FAQs): https://wiki.postgresql.org/
- `pgexercises` for hands-on SQL: https://pgexercises.com/
- `explain.dalibo.com` for plan visualization
- `pg_stat_statements` + `auto_explain` should be running on every non-trivial database (→ [Observability](ADVANCED_POSTGRES.md#13-observability))

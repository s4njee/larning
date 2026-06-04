# SQLite Deep Dive

A comprehensive guide to SQLite — the most widely deployed database engine in the world. Assumes you know basic SQL and have used a relational database before. This guide covers SQLite's architecture, unique design decisions, practical usage as an embedded database, and everything you need to use it effectively in real systems.

Primary references: [SQLite Documentation](https://www.sqlite.org/docs.html), [SQL Syntax](https://www.sqlite.org/lang.html), [Pragma Statements](https://www.sqlite.org/pragma.html), [File Format](https://www.sqlite.org/fileformat2.html)

---

## Table of Contents

1. [The Mental Model](#1-the-mental-model)
2. [Architecture & Internals](#2-architecture--internals)
3. [The Type System](#3-the-type-system)
4. [SQL Feature Coverage](#4-sql-feature-coverage)
5. [Indexes & Query Planning](#5-indexes--query-planning)
6. [Transactions, Concurrency & Locking](#6-transactions-concurrency--locking)
7. [WAL Mode](#7-wal-mode)
8. [Performance Tuning](#8-performance-tuning)
9. [JSON Support](#9-json-support)
10. [Full-Text Search (FTS5)](#10-full-text-search-fts5)
11. [Virtual Tables](#11-virtual-tables)
12. [Practical: Embedded Database Use Cases](#12-practical-embedded-database-use-cases)
13. [SQLite as an Application File Format](#13-sqlite-as-an-application-file-format)
14. [SQLite vs Other Databases](#14-sqlite-vs-other-databases)
15. [Extensions & Ecosystem](#15-extensions--ecosystem)
16. [Backup, Migration & Maintenance](#16-backup-migration--maintenance)
17. [Best Practices & Anti-Patterns](#17-best-practices--anti-patterns)
18. [Advanced Topics](#18-advanced-topics)
19. [Limits & Constraints](#19-limits--constraints)
20. [Common Mistakes](#20-common-mistakes)

---

## 1. The Mental Model

### What SQLite Is

SQLite is a **self-contained, serverless, zero-configuration, transactional SQL database engine**. The key word is **embedded** — SQLite runs inside your application process, not as a separate server. There is no network protocol, no daemon, no setup. Your application links against a C library (~600KB compiled) and reads/writes a single ordinary file on disk.

```
┌──────────────────────────────────────────────────────┐
│                  Your Application                     │
│                                                      │
│   ┌──────────────────────────────────────────────┐   │
│   │              SQLite Library                   │   │
│   │                                              │   │
│   │   SQL in → Parser → Planner → VDBE → B-tree │   │
│   │                                     ↕        │   │
│   │                               Pager (I/O)    │   │
│   └──────────────────────────┬───────────────────┘   │
│                              │                        │
└──────────────────────────────│────────────────────────┘
                               ↕
                    ┌─────────────────────┐
                    │   database.db       │
                    │   (single file)     │
                    └─────────────────────┘
```

This is fundamentally different from PostgreSQL or MySQL where the database is a separate process (or cluster of processes) that your application talks to over a socket. In SQLite, the database engine is linked directly into your code. Function calls, not network packets.

### Why SQLite Exists

SQLite was originally designed in 2000 by D. Richard Hipp for the US Navy, for use in guided missile destroyers — systems that needed a relational database but couldn't rely on a DBA or a running database server. That origin story explains its core design priorities:

- **Zero administration**: no installation, no configuration, no server to manage
- **Reliable**: must not lose data, even on power failure or crash
- **Portable**: the database file works across any platform, any endianness, 32-bit or 64-bit
- **Small**: the library must fit in resource-constrained environments

### Scale of Deployment

SQLite is estimated to have **over one trillion active databases** worldwide. It ships in:

- Every Android device
- Every iPhone and iPad
- Every copy of Firefox, Chrome, Safari, and Edge
- Every Mac (macOS uses it extensively)
- Every Windows 10/11 installation
- Python's standard library (`sqlite3`)
- PHP's built-in `PDO_SQLITE`
- Airbus A350 flight software

It is, by a significant margin, the most widely deployed database engine — and the most widely deployed software module of any kind — in the world.

### When to Use SQLite

| Use case | Why SQLite fits |
|---|---|
| Mobile apps (Android, iOS) | Built into the OS, zero setup, fast local storage |
| Desktop applications | No server dependency, self-contained data files |
| Embedded systems / IoT | Tiny footprint (~600KB), no OS dependencies |
| Application file format | Single file, cross-platform, atomic writes, queryable |
| Website (low-medium traffic) | Simpler than running a database server, fast reads |
| Development & testing | Drop-in replacement for server databases, in-memory mode |
| Data analysis & exploration | Python stdlib, works with Datasette/sqlite-utils |
| Configuration storage | Better than flat files, supports structured queries |
| Caching layer | Fast reads, no server overhead, TTL via application logic |
| Edge computing | Local-first, works offline, sync later |

### When NOT to Use SQLite

- **High write concurrency** — only one writer at a time. If multiple processes need to write simultaneously and frequently, use PostgreSQL or MySQL.
- **Client-server architecture** — if the database must be accessed over a network by multiple application servers, use a server database. SQLite does not work reliably on network filesystems (NFS, SMB).
- **Very large datasets** — SQLite handles tens of gigabytes well. At hundreds of gigabytes or terabytes, a server database with a more sophisticated query planner, buffer management, and parallel execution will perform better.
- **Fine-grained access control** — SQLite has no user management, no `GRANT`/`REVOKE`. Access control is at the filesystem level.
- **Heavy analytical workloads** — no parallel query execution. For OLAP, consider DuckDB (which is also embedded but column-oriented).

---

## 2. Architecture & Internals

### The Processing Pipeline

SQL execution flows through a well-defined pipeline:

```
SQL Text
   ↓
┌──────────┐
│ Tokenizer│ — breaks SQL into tokens
└────┬─────┘
     ↓
┌──────────┐
│  Parser  │ — LALR(1) parser (Lemon-generated), builds a parse tree
└────┬─────┘
     ↓
┌──────────────┐
│Code Generator│ — converts parse tree into VDBE bytecode
└────┬─────────┘
     ↓
┌──────────┐
│   VDBE   │ — register-based virtual machine, executes bytecode
└────┬─────┘
     ↓
┌──────────┐
│  B-tree  │ — manages tables and indexes as B-tree structures
└────┬─────┘
     ↓
┌──────────┐
│  Pager   │ — page cache, locking, journaling, crash recovery
└────┬─────┘
     ↓
┌──────────┐
│   VFS    │ — OS abstraction layer for file I/O
└──────────┘
```

### VDBE (Virtual Database Engine)

The VDBE is the heart of SQLite. Every SQL statement compiles down to a program of bytecode opcodes (~187 different opcodes). You can inspect them:

```sql
EXPLAIN SELECT name FROM users WHERE age > 30;
```

This outputs the actual bytecode program: `OpenRead`, `Rewind`, `Column`, `Gt`, `ResultRow`, `Next`, `Halt`, etc. Understanding VDBE output is rarely necessary, but it's useful for deep debugging.

For practical query analysis, use `EXPLAIN QUERY PLAN` instead — it shows the high-level strategy:

```sql
EXPLAIN QUERY PLAN SELECT name FROM users WHERE age > 30;
-- QUERY PLAN
-- `--SCAN users
```

Add an index and it changes:

```sql
CREATE INDEX idx_users_age ON users(age);
EXPLAIN QUERY PLAN SELECT name FROM users WHERE age > 30;
-- QUERY PLAN
-- `--SEARCH users USING INDEX idx_users_age (age>?)
```

### B-tree Structure

SQLite uses two types of B-trees:

- **Table B-trees** (B+ trees): Leaf nodes contain the actual row data. Keyed by a 64-bit integer `rowid`. Every table without `WITHOUT ROWID` has one.
- **Index B-trees**: Both internal and leaf nodes contain key data. Used for secondary indexes.

Each table and each index is its own B-tree, rooted at a specific page in the database file.

### The Database File

The entire database — tables, indexes, schema, metadata — lives in a single file:

- First 100 bytes: **database header** (magic string `"SQLite format 3\000"`, page size, format versions, schema version, etc.)
- Default **page size**: 4096 bytes (configurable: 512 to 65536)
- Pages are numbered starting at 1; page 1 contains the header and the root of the `sqlite_master` table
- The file format is **cross-platform**: freely copy between big-endian/little-endian, 32-bit/64-bit
- **Format stability guarantee**: the SQLite developers have pledged compatibility through at least **2050**

### The VFS Layer

The Virtual File System (VFS) is an abstraction layer between SQLite and the operating system. This is what makes SQLite so portable — you can implement a custom VFS for:

- In-memory databases (built-in: `:memory:`)
- Encrypted storage (see SEE, SQLCipher)
- Custom I/O on embedded systems
- Logging and profiling I/O operations

---

## 3. The Type System

### Manifest Typing & Type Affinity

SQLite's type system is fundamentally different from other databases. It uses **manifest typing** — the type belongs to the **value**, not the column. Any column can hold any type of data (with one exception: `INTEGER PRIMARY KEY`).

```sql
CREATE TABLE demo (x, y, z);  -- no types at all, perfectly valid

INSERT INTO demo VALUES (1, 'hello', 3.14);
INSERT INTO demo VALUES ('text', NULL, X'DEADBEEF');  -- different types in same column
```

### Five Storage Classes

Every value in SQLite has one of exactly five storage classes:

| Storage class | Description |
|---|---|
| `NULL` | The null value |
| `INTEGER` | Signed integer (1, 2, 3, 4, 6, or 8 bytes, stored compactly) |
| `REAL` | 8-byte IEEE 754 floating point |
| `TEXT` | UTF-8 or UTF-16 string |
| `BLOB` | Binary data, stored exactly as input |

### Type Affinity

When you declare a column type (e.g., `VARCHAR(100)`, `INT`, `DOUBLE`), SQLite maps it to a **type affinity** that acts as a preference, not a constraint:

| Affinity | Behavior |
|---|---|
| `INTEGER` | Prefers storing as integer; converts strings that look like integers |
| `TEXT` | Prefers storing as text; stores everything as text |
| `BLOB` (or `NONE`) | No preference; stores exactly what you give it |
| `REAL` | Prefers storing as float |
| `NUMERIC` | Stores as integer if possible, else float, else text |

The affinity rules match on the **type name string** in your `CREATE TABLE`:

```sql
-- "INT" anywhere → INTEGER affinity
CREATE TABLE t1 (a INT);          -- INTEGER affinity
CREATE TABLE t2 (a INTEGER);      -- INTEGER affinity
CREATE TABLE t3 (a BIGINT);       -- INTEGER affinity (contains "INT")
CREATE TABLE t4 (a TINYINT);      -- INTEGER affinity

-- "CHAR", "CLOB", "TEXT" → TEXT affinity
CREATE TABLE t5 (a VARCHAR(255)); -- TEXT affinity (contains "CHAR")
CREATE TABLE t6 (a TEXT);         -- TEXT affinity

-- "BLOB" or no type → BLOB affinity
CREATE TABLE t7 (a BLOB);         -- BLOB affinity
CREATE TABLE t8 (a);              -- BLOB affinity (no type)

-- "REAL", "FLOA", "DOUB" → REAL affinity
CREATE TABLE t9 (a REAL);         -- REAL affinity
CREATE TABLE t10 (a DOUBLE);      -- REAL affinity
CREATE TABLE t11 (a FLOAT);       -- REAL affinity

-- anything else → NUMERIC affinity
CREATE TABLE t12 (a BOOLEAN);     -- NUMERIC affinity
CREATE TABLE t13 (a DATE);        -- NUMERIC affinity
CREATE TABLE t14 (a DECIMAL);     -- NUMERIC affinity
```

### STRICT Tables (3.37.0+)

If dynamic typing makes you uncomfortable, SQLite now supports strict type enforcement:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER,
    score REAL
) STRICT;

INSERT INTO users VALUES (1, 'Alice', 'thirty', 9.5);
-- Error: cannot store TEXT value in INTEGER column users.age
```

In strict mode, columns must be one of: `INT`, `INTEGER`, `REAL`, `TEXT`, `BLOB`, `ANY`.

### Dates and Times

SQLite has no native date/time storage class. Instead, it provides a suite of **date and time functions** that work with three representations:

```sql
-- TEXT as ISO 8601 strings (recommended)
SELECT datetime('now');                    -- '2024-01-15 14:30:00'
SELECT date('now', '+7 days');             -- '2024-01-22'
SELECT strftime('%Y-%m-%d %H:%M', 'now'); -- formatted output

-- REAL as Julian day numbers
SELECT julianday('now');                   -- 2460324.104...

-- INTEGER as Unix timestamps
SELECT unixepoch('now');                   -- 1705329000
SELECT datetime(1705329000, 'unixepoch'); -- back to text
```

Best practice: store dates as ISO 8601 text (`'2024-01-15 14:30:00'`) or as Unix timestamps (integers). Both work with SQLite's date functions and sort correctly.

---

## 4. SQL Feature Coverage

### DDL (Data Definition Language)

```sql
-- create table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,              -- alias for rowid, auto-increments
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    bio TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    score REAL DEFAULT 0.0,
    CHECK (length(email) > 0)
);

-- alter table
ALTER TABLE users ADD COLUMN avatar_url TEXT;
ALTER TABLE users RENAME COLUMN bio TO biography;
ALTER TABLE users RENAME TO people;
ALTER TABLE users DROP COLUMN avatar_url;          -- 3.35.0+

-- generated columns (3.31.0+)
CREATE TABLE products (
    price_cents INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    total_cents INTEGER GENERATED ALWAYS AS (price_cents * quantity) STORED,
    display_price TEXT GENERATED ALWAYS AS (
        '$' || printf('%.2f', price_cents / 100.0)
    ) VIRTUAL
);

-- views
CREATE VIEW active_users AS
SELECT * FROM users WHERE score > 0;

-- triggers
CREATE TRIGGER update_timestamp
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET created_at = datetime('now') WHERE id = NEW.id;
END;
```

### INTEGER PRIMARY KEY vs AUTOINCREMENT

This is a critical SQLite concept that trips people up:

```sql
-- INTEGER PRIMARY KEY: alias for the built-in rowid
-- Auto-increments by default (max existing rowid + 1)
-- If you delete row 5 and insert again, you might get rowid 5 again
CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);

-- AUTOINCREMENT: guarantees monotonically increasing IDs
-- Maintains a sqlite_sequence table to track the max used value
-- Slightly slower due to the extra table lookup
-- Prevents rowid reuse — even after deletion, IDs only go up
CREATE TABLE t2 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
```

In most cases, `INTEGER PRIMARY KEY` without `AUTOINCREMENT` is sufficient and faster. Use `AUTOINCREMENT` only if you specifically need to guarantee that rowids are never reused.

### WITHOUT ROWID Tables

Normal tables always have a hidden `rowid` column. `WITHOUT ROWID` tables store data directly in the index structure keyed by the primary key:

```sql
-- good for lookup tables with natural primary keys
CREATE TABLE country_codes (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
) WITHOUT ROWID;

-- good for many-to-many junction tables
CREATE TABLE user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, role_id)
) WITHOUT ROWID;
```

Benefits: saves space (no separate rowid column), faster lookups by primary key for non-integer keys. Drawback: slower for large rows because the full row is stored in the B-tree interior nodes.

### DML (Data Manipulation Language)

```sql
-- insert
INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice');

-- insert multiple rows
INSERT INTO users (email, name) VALUES
    ('bob@example.com', 'Bob'),
    ('carol@example.com', 'Carol');

-- upsert (3.24.0+)
INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice Updated')
ON CONFLICT (email) DO UPDATE SET name = excluded.name;

INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice')
ON CONFLICT (email) DO NOTHING;

-- returning (3.35.0+)
INSERT INTO users (email, name) VALUES ('dave@example.com', 'Dave')
RETURNING id, email;

DELETE FROM users WHERE score < 0 RETURNING id, email;

UPDATE users SET score = score + 1 WHERE id = 1 RETURNING *;

-- replace (insert or delete-then-insert if conflict)
REPLACE INTO users (id, email, name) VALUES (1, 'alice2@example.com', 'Alice 2');
```

### CTEs and Recursive Queries

```sql
-- non-recursive CTE
WITH recent_users AS (
    SELECT * FROM users WHERE created_at > datetime('now', '-7 days')
)
SELECT * FROM recent_users WHERE score > 10;

-- recursive CTE: generate a series
WITH RECURSIVE cnt(x) AS (
    SELECT 1
    UNION ALL
    SELECT x + 1 FROM cnt WHERE x < 100
)
SELECT x FROM cnt;

-- recursive CTE: traverse a tree (org chart)
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT,
    manager_id INTEGER REFERENCES employees(id)
);

WITH RECURSIVE org_chart AS (
    -- anchor: the CEO (no manager)
    SELECT id, name, manager_id, 0 AS depth, name AS path
    FROM employees WHERE manager_id IS NULL

    UNION ALL

    -- recursive: each employee under their manager
    SELECT e.id, e.name, e.manager_id, oc.depth + 1,
           oc.path || ' > ' || e.name
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.id
)
SELECT * FROM org_chart ORDER BY path;
```

### Window Functions (3.25.0+)

```sql
-- row numbering
SELECT name, score,
    ROW_NUMBER() OVER (ORDER BY score DESC) AS rank
FROM users;

-- running total
SELECT date, amount,
    SUM(amount) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) AS running_total
FROM transactions;

-- partition by category, rank within each
SELECT category, name, score,
    RANK() OVER (PARTITION BY category ORDER BY score DESC) AS category_rank
FROM products;

-- lag/lead (previous/next row values)
SELECT date, price,
    price - LAG(price) OVER (ORDER BY date) AS daily_change,
    LEAD(price) OVER (ORDER BY date) AS next_price
FROM stock_prices;

-- moving average
SELECT date, price,
    AVG(price) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_7day
FROM stock_prices;

-- named window
SELECT name, score,
    ROW_NUMBER() OVER w AS rn,
    RANK() OVER w AS rnk,
    DENSE_RANK() OVER w AS drnk
FROM users
WINDOW w AS (ORDER BY score DESC);
```

### Subqueries and EXISTS

```sql
-- correlated subquery
SELECT u.name,
    (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u;

-- EXISTS (often more efficient than IN for large sets)
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

-- NOT EXISTS (preferred over NOT IN with nullable columns)
SELECT * FROM users u
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);
```

### What SQLite Does NOT Support

| Feature | Status |
|---|---|
| `RIGHT JOIN`, `FULL OUTER JOIN` | Supported since 3.39.0 (2022). Older versions: LEFT JOIN only. |
| Stored procedures | Not supported. Use application-defined functions instead. |
| `GRANT` / `REVOKE` | Not supported. Access control is filesystem-level. |
| User management | Not supported. No concept of database users. |
| `ALTER TABLE ADD CONSTRAINT` | Not supported. Must recreate the table. |
| `TRUNCATE TABLE` | Not supported. Use `DELETE FROM table` (with no WHERE). |
| Materialized views | Not supported. Use application-level caching or triggers. |
| Concurrent writers | Only one writer at a time (even in WAL mode). |
| `ENUM` type | Not supported natively. Use `CHECK` constraints. |
| Parallel query execution | Not supported. Single-threaded query execution. |

---

## 5. Indexes & Query Planning

### Index Types

SQLite supports only B-tree indexes, but with several powerful variations:

```sql
-- basic index
CREATE INDEX idx_users_email ON users(email);

-- unique index
CREATE UNIQUE INDEX idx_users_email ON users(email);

-- multi-column index
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at);
-- serves queries on (user_id), (user_id, created_at)
-- does NOT efficiently serve queries on (created_at) alone

-- partial index (3.8.0+)
-- only indexes rows matching the WHERE clause — smaller and faster
CREATE INDEX idx_active_users ON users(name) WHERE active = 1;
-- only used when the query also has WHERE active = 1

-- expression index
CREATE INDEX idx_users_lower_email ON users(lower(email));
-- query must use the exact expression: WHERE lower(email) = '...'

-- covering index
-- if the index contains all columns needed by the query,
-- SQLite reads only from the index, never touching the table
CREATE INDEX idx_users_email_name ON users(email, name);
-- SELECT name FROM users WHERE email = '...'
-- → uses index only, no table lookup
```

### EXPLAIN QUERY PLAN

This is your primary tool for understanding query performance:

```sql
EXPLAIN QUERY PLAN
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.active = 1
GROUP BY u.id;

-- output:
-- QUERY PLAN
-- |--SEARCH users USING INDEX idx_active_users (active=?)
-- `--SEARCH orders USING INDEX idx_orders_user_id (user_id=?)
```

Key terms in the output:

| Term | Meaning |
|---|---|
| `SCAN table` | Full table scan — reads every row |
| `SEARCH table USING INDEX` | Uses an index for lookup — much faster |
| `SEARCH table USING INTEGER PRIMARY KEY` | Direct rowid lookup — fastest possible |
| `USING COVERING INDEX` | All needed data is in the index — no table access |
| `USING TEMPORARY B-TREE` | Creates a temp structure for ORDER BY or DISTINCT |

### The ANALYZE Command

```sql
-- collect statistics about all tables and indexes
ANALYZE;

-- analyze a specific table
ANALYZE users;

-- view collected statistics
SELECT * FROM sqlite_stat1;
```

`ANALYZE` populates the `sqlite_stat1` (and optionally `sqlite_stat4`) tables with distribution statistics. The query planner uses these to choose between index scan and table scan, and to choose join order. **Always run `ANALYZE` after bulk data loads** — without it, the planner is guessing.

### Index Optimization Strategies

1. **Index columns in WHERE clauses** — especially equality comparisons
2. **Index columns in JOIN conditions** — critical for join performance
3. **Index columns in ORDER BY** — avoids a temporary sort
4. **Use multi-column indexes wisely** — order matters (most selective column first, or match your query's equality/range pattern)
5. **Use partial indexes** — if you frequently query a subset, index only that subset
6. **Don't over-index** — each index slows down INSERT/UPDATE/DELETE and uses disk space
7. **Covering indexes** — if a query only needs a few columns, include them all in the index

---

## 6. Transactions, Concurrency & Locking

### Transaction Basics

```sql
-- explicit transaction
BEGIN TRANSACTION;
INSERT INTO accounts (name, balance) VALUES ('Alice', 1000);
INSERT INTO accounts (name, balance) VALUES ('Bob', 500);
COMMIT;

-- rollback on error
BEGIN TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE name = 'Alice';
UPDATE accounts SET balance = balance + 100 WHERE name = 'Bob';
-- something went wrong:
ROLLBACK;

-- savepoints (nested transactions)
BEGIN TRANSACTION;
INSERT INTO logs (msg) VALUES ('step 1');
SAVEPOINT sp1;
INSERT INTO logs (msg) VALUES ('step 2');
-- undo step 2 only:
ROLLBACK TO SAVEPOINT sp1;
COMMIT;  -- step 1 is committed, step 2 is not
```

### The Five Lock States (Rollback Journal Mode)

SQLite uses file-level locking with five states. Understanding these is essential for debugging concurrency issues:

```
  UNLOCKED ──→ SHARED ──→ RESERVED ──→ PENDING ──→ EXCLUSIVE
  (nothing)    (reading)   (planning    (waiting     (writing)
                            to write)    for readers
                                         to finish)
```

| State | Who can coexist | What it means |
|---|---|---|
| `UNLOCKED` | Everyone | Default state, no active transaction |
| `SHARED` | Multiple readers | Connection is reading; multiple SHARED locks allowed |
| `RESERVED` | Readers + one reserver | Connection intends to write; only one RESERVED lock allowed; readers can still acquire SHARED |
| `PENDING` | Existing readers only | Connection is about to write; no NEW shared locks can be acquired; existing readers finish |
| `EXCLUSIVE` | Nobody | Connection is writing; no other locks of any kind |

### Busy Handling

When a connection can't acquire a lock, it gets `SQLITE_BUSY`. The default behavior is to return the error immediately, which is almost never what you want:

```sql
-- set a busy timeout: wait up to 5 seconds for a lock
PRAGMA busy_timeout = 5000;
```

```python
# Python: set busy timeout on connection
import sqlite3
conn = sqlite3.connect('mydb.db', timeout=5.0)  # 5-second busy timeout
```

### Transaction Types

SQLite supports three transaction types that control when locks are acquired:

```sql
-- DEFERRED (default): acquires locks lazily
-- starts with no lock, acquires SHARED on first read, RESERVED on first write
BEGIN DEFERRED TRANSACTION;

-- IMMEDIATE: acquires RESERVED lock immediately
-- guarantees you can write; blocks other writers at the start
BEGIN IMMEDIATE TRANSACTION;

-- EXCLUSIVE: acquires EXCLUSIVE lock immediately
-- blocks all other connections (readers and writers)
BEGIN EXCLUSIVE TRANSACTION;
```

**Best practice for write transactions**: Use `BEGIN IMMEDIATE` to fail fast if another writer holds the lock, rather than succeeding on reads and then failing when you try to write.

---

## 7. WAL Mode

### How It Works

WAL (Write-Ahead Logging) is SQLite's most important performance feature. It fundamentally changes how reads and writes interact:

**Rollback journal (default)**:
- Write = modify database file in place, keep original pages in journal
- Read during write = **blocked** (must wait for EXCLUSIVE lock to release)

**WAL mode**:
- Write = append changes to a separate WAL file (`-wal`)
- Read = read from original database + consult WAL for recent changes
- Read during write = **not blocked** (readers and writer operate concurrently)

```sql
-- enable WAL mode (do this once; it persists)
PRAGMA journal_mode = WAL;
-- returns: wal

-- check current mode
PRAGMA journal_mode;
```

### WAL Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ database.db  │     │ database-wal │     │ database-shm │
│              │     │              │     │              │
│ original     │     │ appended     │     │ WAL index    │
│ pages        │     │ changes      │     │ (shared mem) │
│              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

- The `-wal` file contains all recent changes
- The `-shm` (shared memory) file is a hash table index for fast WAL lookups
- **Checkpointing** transfers WAL content back to the database file
- Auto-checkpoint triggers when the WAL reaches 1000 pages (default)

```sql
-- manual checkpoint
PRAGMA wal_checkpoint;             -- passive: checkpoint if no readers
PRAGMA wal_checkpoint(FULL);       -- wait for readers, then checkpoint
PRAGMA wal_checkpoint(RESTART);    -- full + reset WAL file
PRAGMA wal_checkpoint(TRUNCATE);   -- full + truncate WAL to zero bytes

-- configure auto-checkpoint threshold
PRAGMA wal_autocheckpoint = 2000;  -- checkpoint every 2000 pages
PRAGMA wal_autocheckpoint = 0;     -- disable auto-checkpoint
```

### WAL Mode Trade-offs

| Advantage | Disadvantage |
|---|---|
| Readers don't block writers | Three files instead of one (db, wal, shm) |
| Writers don't block readers | Doesn't work on network filesystems |
| Faster for many workloads | WAL file can grow large without checkpointing |
| Fewer fsync operations | Requires shared-memory support from OS |
| Better concurrency | Still only one writer at a time |

### When to Use WAL

Use WAL mode **almost always**. The only reasons not to:

1. You need a single-file database (e.g., for distribution or email attachment)
2. You're on a system without shared-memory support
3. You're using a network filesystem (WAL doesn't work there either, but neither does anything else reliably)

---

## 8. Performance Tuning

### Essential PRAGMAs

Apply these at connection open for optimal performance:

```sql
-- WAL mode: dramatically improves concurrency
PRAGMA journal_mode = WAL;

-- synchronous NORMAL: safe with WAL, much faster than FULL
-- FULL (default) fsyncs on every commit; NORMAL only fsyncs on checkpoint
PRAGMA synchronous = NORMAL;

-- cache size: increase for read-heavy workloads (negative = KiB)
PRAGMA cache_size = -64000;  -- 64 MiB in-memory page cache

-- memory-mapped I/O: map database file into address space
-- avoids read() system calls; significant speedup for read-heavy workloads
PRAGMA mmap_size = 268435456;  -- 256 MiB

-- temp store: keep temporary tables and indexes in memory
PRAGMA temp_store = MEMORY;

-- foreign keys: NOT a performance pragma, but must be set per connection
PRAGMA foreign_keys = ON;

-- busy timeout: wait for locks instead of failing
PRAGMA busy_timeout = 5000;
```

### Batch Operations in Transactions

This is the single most impactful performance optimization. Without explicit transactions, every statement is its own transaction with a full fsync:

```python
import sqlite3

conn = sqlite3.connect('mydb.db')

# SLOW: 10,000 individual transactions, 10,000 fsyncs
for i in range(10000):
    conn.execute("INSERT INTO t VALUES (?)", (i,))
    conn.commit()  # implicit if autocommit

# FAST: 1 transaction, 1 fsync
conn.execute("BEGIN")
for i in range(10000):
    conn.execute("INSERT INTO t VALUES (?)", (i,))
conn.execute("COMMIT")

# FASTEST: use executemany
conn.execute("BEGIN")
conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(10000)])
conn.execute("COMMIT")
```

The difference is dramatic: individual inserts might do ~100/second (fsync-limited), while batched inserts can do **50,000–100,000+/second**.

### Prepared Statements

```python
# BAD: re-parses SQL every time
for user in users:
    conn.execute(f"INSERT INTO users (name) VALUES ('{user}')")  # SQL injection too!

# GOOD: parse once, execute many times with different parameters
stmt = "INSERT INTO users (name) VALUES (?)"
for user in users:
    conn.execute(stmt, (user,))

# BEST: executemany with prepared statement
conn.executemany("INSERT INTO users (name) VALUES (?)", [(u,) for u in users])
```

### Practical: Connection Setup Function

```python
import sqlite3

def get_connection(db_path, readonly=False):
    """Open a SQLite connection with optimal settings."""
    uri = f"file:{db_path}"
    if readonly:
        uri += "?mode=ro"

    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row  # access columns by name

    # performance pragmas
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA mmap_size = 268435456")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 5000")

    # correctness pragmas
    conn.execute("PRAGMA foreign_keys = ON")

    return conn
```

### Profiling

```python
# trace all SQL statements
conn.set_trace_callback(lambda sql: print(f"SQL: {sql}"))

# time individual operations
import time
start = time.perf_counter()
conn.execute("SELECT COUNT(*) FROM big_table")
elapsed = time.perf_counter() - start
print(f"Query took {elapsed:.3f}s")
```

---

## 9. JSON Support

SQLite has robust JSON support, built into the amalgamation since 3.38.0 (2022). Earlier versions need the `json1` extension.

### JSON Operators (3.38.0+)

```sql
-- extract with -> (returns JSON) and ->> (returns SQL text/number)
SELECT data->'name' FROM users;       -- returns JSON: "Alice"
SELECT data->>'name' FROM users;      -- returns text: Alice
SELECT data->>'age' FROM users;       -- returns number: 30

-- nested paths
SELECT data->'address'->>'city' FROM users;
SELECT data->>'$.address.city' FROM users;  -- JSON path syntax
```

### JSON Functions

```sql
-- validate JSON
SELECT json_valid('{"name": "Alice"}');  -- 1
SELECT json_valid('not json');           -- 0

-- create JSON
SELECT json_object('name', 'Alice', 'age', 30);
-- '{"name":"Alice","age":30}'

SELECT json_array(1, 2, 'three');
-- '[1,2,"three"]'

-- extract values
SELECT json_extract('{"a":1,"b":[2,3]}', '$.a');      -- 1
SELECT json_extract('{"a":1,"b":[2,3]}', '$.b[0]');   -- 2

-- modify JSON
SELECT json_set('{"a":1}', '$.b', 2);           -- '{"a":1,"b":2}'
SELECT json_insert('{"a":1}', '$.b', 2);        -- '{"a":1,"b":2}' (only if $.b doesn't exist)
SELECT json_replace('{"a":1}', '$.a', 99);      -- '{"a":99}'
SELECT json_remove('{"a":1,"b":2}', '$.b');      -- '{"a":1}'

-- aggregate into JSON arrays/objects
SELECT json_group_array(name) FROM users;
-- '["Alice","Bob","Carol"]'

SELECT json_group_object(name, score) FROM users;
-- '{"Alice":95,"Bob":82,"Carol":91}'
```

### json_each — Iterate Over JSON Arrays

```sql
-- flatten a JSON array column
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    items TEXT  -- JSON array: '["apple","banana","cherry"]'
);

-- get each item as a row
SELECT o.id, j.value AS item
FROM orders o, json_each(o.items) j;

-- query within JSON arrays
SELECT id FROM orders
WHERE EXISTS (
    SELECT 1 FROM json_each(orders.items) WHERE value = 'apple'
);
```

### Practical: Storing Flexible Data

```sql
-- semi-structured data with JSON columns
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    metadata TEXT DEFAULT '{}'  -- JSON
);

INSERT INTO events (type, metadata) VALUES
    ('page_view', json('{"url": "/home", "referrer": "google.com"}')),
    ('purchase', json('{"product_id": 42, "amount": 29.99, "currency": "USD"}'));

-- query JSON fields
SELECT type, metadata->>'$.url' AS url
FROM events
WHERE type = 'page_view' AND metadata->>'$.referrer' = 'google.com';

-- index a JSON field for fast lookups
CREATE INDEX idx_events_product ON events(
    json_extract(metadata, '$.product_id')
) WHERE type = 'purchase';
```

---

## 10. Full-Text Search (FTS5)

FTS5 is SQLite's full-text search extension. It creates virtual tables with inverted indexes for fast text search across large document collections.

### Creating an FTS5 Table

```sql
-- basic FTS5 table
CREATE VIRTUAL TABLE articles_fts USING fts5(
    title,
    body,
    content='articles',          -- external content table
    content_rowid='id'           -- rowid mapping
);

-- standalone FTS5 table (stores its own content)
CREATE VIRTUAL TABLE docs USING fts5(title, body);
INSERT INTO docs (title, body) VALUES
    ('SQLite Guide', 'SQLite is a self-contained database engine'),
    ('PostgreSQL Guide', 'PostgreSQL is a powerful object-relational database'),
    ('Redis Guide', 'Redis is an in-memory data structure store');
```

### Searching

```sql
-- basic search
SELECT * FROM docs WHERE docs MATCH 'database';

-- phrase search
SELECT * FROM docs WHERE docs MATCH '"database engine"';

-- boolean operators
SELECT * FROM docs WHERE docs MATCH 'database AND powerful';
SELECT * FROM docs WHERE docs MATCH 'database OR engine';
SELECT * FROM docs WHERE docs MATCH 'database NOT redis';

-- prefix search
SELECT * FROM docs WHERE docs MATCH 'data*';  -- matches database, data

-- column-specific search
SELECT * FROM docs WHERE docs MATCH 'title:guide';

-- NEAR operator (terms within N tokens of each other)
SELECT * FROM docs WHERE docs MATCH 'NEAR(database engine, 3)';

-- ranking with BM25 (lower = more relevant)
SELECT *, rank FROM docs WHERE docs MATCH 'database' ORDER BY rank;

-- or explicitly with bm25() function
SELECT *, bm25(docs) AS score FROM docs
WHERE docs MATCH 'database'
ORDER BY score;

-- highlight matches
SELECT highlight(docs, 0, '<b>', '</b>') AS title,
       snippet(docs, 1, '<b>', '</b>', '...', 20) AS body_snippet
FROM docs WHERE docs MATCH 'database';
```

### Keeping FTS in Sync with a Content Table

```sql
-- create the content table
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL
);

-- create the FTS index pointing to it
CREATE VIRTUAL TABLE articles_fts USING fts5(
    title, body,
    content='articles',
    content_rowid='id'
);

-- triggers to keep FTS in sync
CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO articles_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
```

### FTS5 Tokenizers

```sql
-- unicode61 (default): Unicode-aware tokenization
CREATE VIRTUAL TABLE t1 USING fts5(content, tokenize='unicode61');

-- ascii: ASCII-only, case-insensitive
CREATE VIRTUAL TABLE t2 USING fts5(content, tokenize='ascii');

-- porter: applies Porter stemming (running → run, databases → databas)
CREATE VIRTUAL TABLE t3 USING fts5(content, tokenize='porter unicode61');

-- trigram: character trigrams, supports LIKE and GLOB
CREATE VIRTUAL TABLE t4 USING fts5(content, tokenize='trigram');
```

---

## 11. Virtual Tables

Virtual tables look like regular tables but their data comes from custom sources. They're the primary extension mechanism for SQLite.

### Built-in Virtual Tables

```sql
-- generate_series: produce a sequence of numbers
SELECT value FROM generate_series(1, 100);
SELECT value FROM generate_series(0, 1000, 10);  -- step by 10

-- dbstat: space usage statistics per table/index
SELECT name, pageno, payload AS used_bytes, unused
FROM dbstat;

-- pragma virtual tables: query PRAGMAs like tables
SELECT * FROM pragma_table_info('users');
SELECT * FROM pragma_index_list('users');
SELECT * FROM pragma_database_list;

-- json_each / json_tree (covered in JSON section)
SELECT * FROM json_each('[1,2,3]');
SELECT * FROM json_tree('{"a":{"b":1},"c":[2,3]}');
```

### R-tree: Spatial Indexing

```sql
-- create an R-tree virtual table for 2D bounding boxes
CREATE VIRTUAL TABLE spatial_index USING rtree(
    id,
    min_x, max_x,
    min_y, max_y
);

-- insert bounding boxes
INSERT INTO spatial_index VALUES (1, 0.0, 10.0, 0.0, 10.0);
INSERT INTO spatial_index VALUES (2, 5.0, 15.0, 5.0, 15.0);

-- spatial query: find all objects overlapping a region
SELECT id FROM spatial_index
WHERE min_x <= 12.0 AND max_x >= 3.0
  AND min_y <= 12.0 AND max_y >= 3.0;
```

### CSV Virtual Table

```sql
-- read a CSV file as a virtual table
CREATE VIRTUAL TABLE temp.csv_data USING csv(
    filename='/path/to/data.csv',
    header=YES
);

SELECT * FROM csv_data WHERE column1 > 100;
```

---

## 12. Practical: Embedded Database Use Cases

This is where SQLite truly shines. It's not just a lightweight database — it's the standard for embedded data storage across every major platform.

### Mobile Applications

**Android** (built into the OS):

```kotlin
// Modern Android: Room (Jetpack) wraps SQLite with type-safe queries
@Entity(tableName = "notes")
data class Note(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val title: String,
    val content: String,
    val createdAt: Long = System.currentTimeMillis()
)

@Dao
interface NoteDao {
    @Query("SELECT * FROM notes ORDER BY createdAt DESC")
    fun getAll(): Flow<List<Note>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(note: Note)

    @Query("SELECT * FROM notes WHERE title LIKE '%' || :query || '%'")
    fun search(query: String): Flow<List<Note>>
}

@Database(entities = [Note::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun noteDao(): NoteDao
}
```

Every Android app with local data uses SQLite — either directly or through Room. The `SQLiteOpenHelper` API manages schema versioning and migrations.

**iOS** (built into the OS):

```swift
// Swift: using GRDB.swift
import GRDB

struct Player: Codable, FetchableRecord, PersistableRecord {
    var id: Int64?
    var name: String
    var score: Int
}

// setup
let dbQueue = try DatabaseQueue(path: dbPath)
try dbQueue.write { db in
    try db.create(table: "player") { t in
        t.autoIncrementedPrimaryKey("id")
        t.column("name", .text).notNull()
        t.column("score", .integer).notNull().defaults(to: 0)
    }
}

// query
let topPlayers = try dbQueue.read { db in
    try Player.order(Column("score").desc).limit(10).fetchAll(db)
}
```

Apple's Core Data uses SQLite as its default persistent store. Every iPhone runs dozens of SQLite databases — for contacts, messages, photos, mail, and app data.

### Desktop Applications

```python
# Python desktop app: local task manager
import sqlite3
from datetime import datetime

class TaskDB:
    def __init__(self, db_path="tasks.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#3B82F6',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
                completed INTEGER DEFAULT 0,
                due_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date) WHERE completed = 0;
        """)

    def add_task(self, title, project_id=None, priority=0, due_date=None):
        return self.conn.execute(
            "INSERT INTO tasks (title, project_id, priority, due_date) VALUES (?, ?, ?, ?) RETURNING id",
            (title, project_id, priority, due_date)
        ).fetchone()["id"]

    def complete_task(self, task_id):
        self.conn.execute(
            "UPDATE tasks SET completed = 1, completed_at = datetime('now') WHERE id = ?",
            (task_id,)
        )
        self.conn.commit()

    def get_pending_tasks(self, project_id=None):
        sql = "SELECT * FROM tasks WHERE completed = 0"
        params = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY priority DESC, due_date ASC NULLS LAST"
        return self.conn.execute(sql, params).fetchall()

    def get_stats(self):
        return self.conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(completed) AS done,
                COUNT(*) - SUM(completed) AS pending,
                SUM(CASE WHEN due_date < date('now') AND completed = 0 THEN 1 ELSE 0 END) AS overdue
            FROM tasks
        """).fetchone()
```

### Real-World Desktop Software Using SQLite

| Application | What It Stores |
|---|---|
| **Adobe Lightroom** | Entire photo catalog — metadata, edits, collections, keywords. The `.lrcat` file is SQLite. |
| **Mozilla Firefox** | Bookmarks, history, cookies, form autofill, extension data, web storage. ~14 SQLite databases per profile. |
| **Google Chrome** | Same categories as Firefox — history, cookies, login data, web data, favicons. Each is a separate SQLite DB. |
| **Apple Photos** | Photo library metadata, face recognition data, albums |
| **Apple Mail** | Message indexing and search |
| **Dropbox** | Desktop client file sync state, metadata caching |
| **Skype** | Message history |
| **iTunes / Apple Music** | Media library database |
| **Calibre** | E-book library metadata |
| **Fossil** | Version control system — entire repo is a SQLite database |

### IoT and Edge Devices

SQLite's tiny footprint (~600KB compiled, reducible to ~300KB) makes it ideal for embedded systems:

```c
// C: minimal embedded usage
#include "sqlite3.h"

int main() {
    sqlite3 *db;
    sqlite3_open("/data/sensor.db", &db);

    sqlite3_exec(db,
        "CREATE TABLE IF NOT EXISTS readings ("
        "  id INTEGER PRIMARY KEY,"
        "  sensor TEXT NOT NULL,"
        "  value REAL NOT NULL,"
        "  timestamp INTEGER DEFAULT (unixepoch())"
        ")", NULL, NULL, NULL);

    // log a sensor reading
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db,
        "INSERT INTO readings (sensor, value) VALUES (?, ?)",
        -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, "temperature", -1, SQLITE_STATIC);
    sqlite3_bind_double(stmt, 2, 23.5);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    sqlite3_close(db);
}
```

Use cases: automotive infotainment, set-top boxes, smart home devices, industrial sensors, drones, medical devices. Airbus uses SQLite in the A350 flight software.

### Configuration and Settings Storage

```python
class AppConfig:
    """Use SQLite instead of INI/JSON files for app configuration."""

    def __init__(self, path="config.db"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            ) WITHOUT ROWID
        """)

    def get(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.conn.execute(
            "INSERT INTO config (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, json.dumps(value))
        )
        self.conn.commit()

    def get_all(self):
        rows = self.conn.execute("SELECT key, value FROM config").fetchall()
        return {k: json.loads(v) for k, v in rows}

# usage
config = AppConfig()
config.set("theme", "dark")
config.set("window_size", {"width": 1200, "height": 800})
config.set("recent_files", ["/path/to/file1.txt", "/path/to/file2.txt"])
```

### Testing and Prototyping

```python
import pytest
import sqlite3

@pytest.fixture
def db():
    """In-memory SQLite database for fast, isolated tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # apply schema
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    yield conn
    conn.close()

def test_create_user(db):
    db.execute("INSERT INTO users (email, name) VALUES (?, ?)", ("a@b.com", "Alice"))
    user = db.execute("SELECT * FROM users WHERE email = ?", ("a@b.com",)).fetchone()
    assert user["name"] == "Alice"

def test_foreign_key_enforcement(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO orders (user_id, total) VALUES (999, 50.0)")
```

In-memory SQLite (`:memory:`) is perfect for unit tests: no filesystem, no cleanup, instant startup, complete isolation.

### Data Analysis with sqlite-utils

```bash
# install
pip install sqlite-utils

# import CSV into SQLite
sqlite-utils insert data.db measurements measurements.csv --csv

# import JSON
cat events.json | sqlite-utils insert data.db events -

# query
sqlite-utils query data.db "SELECT sensor, AVG(value) FROM measurements GROUP BY sensor"

# create an index
sqlite-utils create-index data.db measurements sensor

# export as JSON
sqlite-utils query data.db "SELECT * FROM measurements LIMIT 10" --json

# serve as a web interface with Datasette
pip install datasette
datasette data.db
# opens http://localhost:8001 with a web UI for exploring data
```

### Caching Layer

```python
class SQLiteCache:
    """Disk-backed cache with TTL, using SQLite."""

    def __init__(self, path="cache.db"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                expires_at REAL
            ) WITHOUT ROWID
        """)

    def get(self, key):
        row = self.conn.execute(
            "SELECT value FROM cache WHERE key = ? AND expires_at > unixepoch()",
            (key,)
        ).fetchone()
        if row:
            return pickle.loads(row[0])
        return None

    def set(self, key, value, ttl_seconds=3600):
        expires = time.time() + ttl_seconds
        self.conn.execute(
            "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at",
            (key, pickle.dumps(value), expires)
        )
        self.conn.commit()

    def evict_expired(self):
        self.conn.execute("DELETE FROM cache WHERE expires_at <= unixepoch()")
        self.conn.commit()
```

Real-world examples: `pip` caches package metadata in SQLite, `apt` uses SQLite for package info, many CDN edge nodes use SQLite for configuration caching.

### Local-First Applications

The "local-first" architecture — store data locally, sync to cloud when available — is perfectly suited to SQLite:

```python
class SyncableDB:
    """SQLite database with change tracking for sync."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now')),
                synced INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY,
                table_name TEXT,
                row_id TEXT,
                operation TEXT,  -- INSERT, UPDATE, DELETE
                timestamp TEXT DEFAULT (datetime('now')),
                synced INTEGER DEFAULT 0
            );

            CREATE TRIGGER IF NOT EXISTS notes_sync_insert
            AFTER INSERT ON notes
            BEGIN
                INSERT INTO sync_log (table_name, row_id, operation)
                VALUES ('notes', NEW.id, 'INSERT');
            END;

            CREATE TRIGGER IF NOT EXISTS notes_sync_update
            AFTER UPDATE ON notes
            BEGIN
                INSERT INTO sync_log (table_name, row_id, operation)
                VALUES ('notes', NEW.id, 'UPDATE');
                UPDATE notes SET synced = 0 WHERE id = NEW.id;
            END;
        """)

    def get_unsynced_changes(self):
        return self.conn.execute(
            "SELECT * FROM sync_log WHERE synced = 0 ORDER BY timestamp"
        ).fetchall()

    def mark_synced(self, log_ids):
        self.conn.executemany(
            "UPDATE sync_log SET synced = 1 WHERE id = ?",
            [(id,) for id in log_ids]
        )
        self.conn.commit()
```

---

## 13. SQLite as an Application File Format

One of SQLite's most powerful and underappreciated use cases: using a SQLite database as your application's file format, instead of JSON, XML, or a custom binary format.

### Why SQLite Beats Custom File Formats

| Feature | SQLite | JSON/XML | Custom Binary |
|---|---|---|---|
| Atomic writes (crash-safe) | ✅ Built-in | ❌ Must implement | ❌ Must implement |
| Incremental updates | ✅ Modify without rewriting | ❌ Rewrite entire file | ❌ Usually rewrite |
| Cross-platform | ✅ Guaranteed | ✅ | ❌ Endianness issues |
| Queryable | ✅ Full SQL | ❌ Load into memory | ❌ Custom code |
| Schema evolution | ✅ ALTER TABLE | ❌ Manual parsing | ❌ Version headers |
| Partial reads | ✅ Read any record | ❌ Load entire file | ⚠️ With offsets |
| Concurrent access | ✅ With locking | ❌ | ❌ |
| Tooling | ✅ sqlite3 CLI, GUI tools | ✅ Editors | ❌ Custom tools |

### Real-World Examples

- **GeoPackage** (`.gpkg`): OGC standard for geospatial data — a SQLite database with spatial tables
- **Fossil SCM**: The entire version control repository is a single SQLite file
- **Calibre**: E-book library metadata stored in SQLite
- **EPUB** readers: Some use SQLite for indexing and bookmarks
- **Adobe Lightroom**: Photo catalog (`.lrcat`) is SQLite
- **macOS System Preferences**: Many `.plist` stores backed by SQLite

### Implementing It

```python
# application file format using SQLite
class ProjectFile:
    SCHEMA_VERSION = 3

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self):
        current = self.conn.execute("PRAGMA user_version").fetchone()[0]

        if current < 1:
            self.conn.executescript("""
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content BLOB,
                    doc_type TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                PRAGMA user_version = 1;
            """)

        if current < 2:
            self.conn.executescript("""
                ALTER TABLE documents ADD COLUMN tags TEXT DEFAULT '[]';
                CREATE INDEX idx_docs_type ON documents(doc_type);
                PRAGMA user_version = 2;
            """)

        if current < 3:
            self.conn.executescript("""
                CREATE VIRTUAL TABLE documents_fts USING fts5(
                    title, content, content='documents', content_rowid='id'
                );
                INSERT INTO documents_fts(rowid, title, content)
                    SELECT id, title, content FROM documents;
                PRAGMA user_version = 3;
            """)

    def save_as(self, new_path):
        """Save a copy using SQLite's backup API."""
        dest = sqlite3.connect(new_path)
        self.conn.backup(dest)
        dest.close()
```

The key insight: `PRAGMA user_version` gives you a free schema version counter. Check it on open, apply migrations sequentially, and your file format evolves gracefully.

---

## 14. SQLite vs Other Databases

### SQLite vs PostgreSQL

| Dimension | SQLite | PostgreSQL |
|---|---|---|
| **Architecture** | Embedded library, no server | Client-server, multi-process |
| **Setup** | Zero configuration | Requires installation, config, DBA |
| **Concurrency** | Single writer, many readers | Many concurrent readers and writers |
| **Locking** | Database-level | Row-level (MVCC) |
| **Data types** | Dynamic (type affinity) | Strict, rich type system (200+ types) |
| **SQL completeness** | Most of SQL-92 + many additions | Extremely comprehensive (SQL:2023) |
| **Extensions** | Limited | Vast ecosystem (PostGIS, pgvector, etc.) |
| **Replication** | None built-in (Litestream, LiteFS) | Streaming, logical, bidirectional |
| **Scale** | Single machine, ≤ ~100GB practical | Terabytes, distributed with Citus |
| **Best for** | Embedded, mobile, desktop, edge | Multi-user web apps, SaaS, data platforms |

**Rule of thumb**: If your data is accessed by a single application on a single machine, start with SQLite. If you need multi-user network access, go PostgreSQL.

### SQLite vs DuckDB

| Dimension | SQLite | DuckDB |
|---|---|---|
| **Focus** | OLTP (transactions, point queries) | OLAP (analytics, scans, aggregations) |
| **Engine** | Row-oriented | Columnar, vectorized |
| **Insert speed** | Fast (single-row and bulk) | Optimized for bulk ingestion |
| **Scan speed** | Good for small tables | 10-100x faster for large table scans |
| **File I/O** | Read/write SQLite files | Read Parquet, CSV, JSON natively |
| **Maturity** | 25+ years, trillions of deployments | Since 2019, rapidly growing |
| **Embedded** | Yes | Yes |

**Choose SQLite** for transactional workloads, application storage, or when you need the most battle-tested embedded database. **Choose DuckDB** when your primary workload is analytical: aggregations over millions of rows, data science, ETL pipelines.

### SQLite vs LevelDB / RocksDB

| Dimension | SQLite | LevelDB / RocksDB |
|---|---|---|
| **Data model** | Relational (tables, SQL) | Key-value only |
| **Query language** | Full SQL | get/put/delete/iterate |
| **Indexes** | B-tree, multiple per table | LSM-tree, single key space |
| **Write throughput** | Good | Excellent (LSM optimized for writes) |
| **Read pattern** | Random + range + complex queries | Point lookups + range scans |
| **Use case** | General-purpose structured data | High-throughput KV storage, write-heavy workloads |

**Choose SQLite** when you need relational queries, joins, or any SQL. **Choose LevelDB/RocksDB** when you only need key-value operations at extreme throughput.

### SQLite vs the Filesystem (for small data)

A surprising finding from SQLite's own benchmarks: **SQLite is 35% faster than direct filesystem I/O** for reading small blobs (under ~100KB). This is because:

- SQLite opens the file once; `fopen()` for each blob requires a separate `open()` + `stat()` + `read()` + `close()`
- SQLite's page cache means repeated reads don't hit disk
- One database file means one inode to track, not thousands

For application data that consists of many small records, SQLite is not just more convenient than flat files — it's faster.

---

## 15. Extensions & Ecosystem

### Language Bindings

| Language | Library | Notes |
|---|---|---|
| **Python** | `sqlite3` (stdlib) | Built into Python. Always available. |
| **Python** | `apsw` | Advanced bindings, exposes more of the C API |
| **Node.js** | `better-sqlite3` | Synchronous API, fastest Node binding |
| **Node.js** | `sql.js` | SQLite compiled to WebAssembly, runs in browser |
| **Rust** | `rusqlite` | Safe Rust bindings, well-maintained |
| **Go** | `mattn/go-sqlite3` | CGo-based, most popular |
| **Go** | `modernc.org/sqlite` | Pure Go (no CGo), cross-compiles easily |
| **Java** | `sqlite-jdbc` | JDBC driver |
| **C#** | `Microsoft.Data.Sqlite` | Official .NET bindings |
| **Ruby** | `sqlite3-ruby` | Standard Ruby gem |
| **PHP** | `PDO_SQLITE` | Built into PHP |
| **Swift** | `GRDB.swift` | Full-featured, type-safe |

### Notable Extensions

| Extension | Purpose |
|---|---|
| **FTS5** | Full-text search (built-in, but must be enabled at compile time) |
| **R-tree** | Spatial indexing for range queries |
| **JSON1** | JSON functions (built into amalgamation since 3.38.0) |
| **SpatiaLite** | Full GIS on SQLite (geometry, projections, spatial queries) |
| **SQLean** | Collection of essential extensions: regexp, crypto, stats, uuid, etc. |
| **sqlite-vec / sqlite-vss** | Vector similarity search for AI/ML embeddings |

### Replication & Distribution

| Tool | What It Does |
|---|---|
| **Litestream** | Streams WAL changes to S3-compatible storage in real-time. Continuous backup, point-in-time restore. |
| **LiteFS** | Distributed SQLite by Fly.io. Primary/replica replication across edge nodes. |
| **cr-sqlite** | CRDT-based multi-writer replication. Merge changes from multiple writers without conflicts. |
| **rqlite** | Distributed SQLite using Raft consensus. Multiple nodes, automatic leader election. |
| **dqlite** | Distributed SQLite by Canonical, used in LXD. Raft-based. |
| **libSQL** (Turso) | SQLite fork with native replication, WASM user functions, HTTP API. |

### Tools

| Tool | Purpose |
|---|---|
| **`sqlite3`** CLI | Official command-line shell — the primary interface |
| **DB Browser for SQLite** | Cross-platform GUI for browsing and editing databases |
| **SQLiteStudio** | Feature-rich GUI |
| **Datasette** | Web-based tool for exploring and publishing SQLite data (by Simon Willison) |
| **sqlite-utils** | CLI and Python library for creating, querying, and manipulating databases |
| **litecli** | CLI with autocompletion and syntax highlighting |
| **sqlite3_analyzer** | Official space-usage analysis tool |

### The sqlite3 CLI

```bash
# open a database
sqlite3 mydb.db

# useful dot-commands
.tables               # list all tables
.schema               # show CREATE statements for all objects
.schema users          # show CREATE for a specific table
.indexes users         # list indexes on a table
.headers on            # show column headers in output
.mode column           # columnar output
.mode csv              # CSV output
.mode json             # JSON output
.mode markdown         # markdown table output

# import/export
.import data.csv tablename    # import CSV into table
.output results.csv           # redirect output to file
.dump                         # dump entire database as SQL
.dump users                   # dump a single table

# backup while database is in use
.backup backup.db

# attach another database
ATTACH 'other.db' AS other;
SELECT * FROM other.some_table;

# performance analysis
.timer on              # show execution time for each query
.expert                # suggest indexes for a query (3.36.0+)
```

---

## 16. Backup, Migration & Maintenance

### Backup Strategies

```python
import sqlite3

# 1. Online backup via Python API (safe while DB is in use)
source = sqlite3.connect("production.db")
dest = sqlite3.connect("backup.db")
source.backup(dest)
dest.close()
source.close()

# 2. Incremental backup with progress callback
def progress(status, remaining, total):
    print(f"Backup: {total - remaining}/{total} pages")

source.backup(dest, pages=100, progress=progress)
```

```bash
# 3. CLI backup
sqlite3 production.db ".backup backup.db"

# 4. VACUUM INTO (3.27.0+) — compacted backup
sqlite3 production.db "VACUUM INTO 'backup.db';"

# 5. Continuous replication with Litestream
litestream replicate production.db s3://mybucket/production
litestream restore -o restored.db s3://mybucket/production
```

**Never copy the database file while connections are open** — the WAL file may contain uncommitted changes. Use `.backup`, `VACUUM INTO`, or the `sqlite3_backup` API instead.

### VACUUM

```sql
-- rebuild the database file, reclaiming space from deleted data
VACUUM;

-- VACUUM into a new file (3.27.0+)
VACUUM INTO 'compacted.db';

-- auto-vacuum: automatically reclaim pages as data is deleted
-- must be set BEFORE creating any tables
PRAGMA auto_vacuum = FULL;       -- reclaim immediately
PRAGMA auto_vacuum = INCREMENTAL; -- reclaim on demand
PRAGMA incremental_vacuum(100);   -- reclaim up to 100 pages
```

`VACUUM` rebuilds the entire database. It requires up to 2x the database size in free disk space and takes an exclusive lock. Use `VACUUM INTO` for a non-blocking alternative.

### Schema Migrations

SQLite's `ALTER TABLE` is limited. For complex schema changes, use the "12-step" table recreation pattern:

```sql
-- changing a column type, adding a constraint, etc.
BEGIN TRANSACTION;

-- 1. Create new table with desired schema
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2. Copy data
INSERT INTO users_new (id, email, name, created_at)
SELECT id, email, name, COALESCE(created_at, datetime('now'))
FROM users;

-- 3. Drop old table
DROP TABLE users;

-- 4. Rename new table
ALTER TABLE users_new RENAME TO users;

-- 5. Recreate indexes, triggers, views
CREATE INDEX idx_users_email ON users(email);

COMMIT;

-- 6. Update schema version
PRAGMA user_version = 2;
```

### Schema Version Tracking

```sql
-- built-in version counter (integer, persists in the file header)
PRAGMA user_version;          -- read current version
PRAGMA user_version = 5;      -- set version

-- application_id: another 32-bit integer for file type identification
PRAGMA application_id;
PRAGMA application_id = 0x4C4D4442;  -- "LMDB" in hex, for example
```

---

## 17. Best Practices & Anti-Patterns

### Do These Always

1. **Enable WAL mode**: `PRAGMA journal_mode=WAL` — dramatically improves concurrency
2. **Enable foreign keys**: `PRAGMA foreign_keys=ON` — they are OFF by default and silently ignored
3. **Set busy timeout**: `PRAGMA busy_timeout=5000` — prevents immediate `SQLITE_BUSY` errors
4. **Use `synchronous=NORMAL` with WAL**: safe and much faster than the default `FULL`
5. **Wrap batch operations in transactions**: 1 transaction with 10,000 inserts vs 10,000 individual transactions is 10-100x faster
6. **Use parameterized queries**: prevents SQL injection and improves performance via statement caching
7. **Run `ANALYZE` after bulk data changes**: gives the query planner accurate statistics
8. **Use `BEGIN IMMEDIATE` for write transactions**: fail fast if another writer holds the lock

### Don't Do These

1. **Don't skip transactions for batch inserts** — each INSERT without a transaction triggers a separate fsync. This is the #1 SQLite performance mistake.
2. **Don't use SQLite over a network filesystem** — NFS and SMB have broken file locking. You will corrupt your database.
3. **Don't forget `PRAGMA foreign_keys=ON`** — without this, foreign key constraints are silently ignored. This must be set per connection.
4. **Don't use `AUTOINCREMENT` unless you need it** — it adds overhead (a separate `sqlite_sequence` table). Plain `INTEGER PRIMARY KEY` already auto-increments.
5. **Don't store large blobs (>100KB) in the database** — performance degrades. Store files on disk and reference them with a path.
6. **Don't open many write connections** — SQLite allows only one writer at a time. Use a single write connection with a queue.
7. **Don't use `NOT IN` with potentially NULL subqueries** — `NOT IN (1, 2, NULL)` always returns empty. Use `NOT EXISTS` instead.
8. **Don't leave connections open in idle-in-transaction state** — it prevents WAL checkpointing and can cause the WAL file to grow indefinitely.

### Connection Pool Pattern

Since SQLite only allows one writer at a time, the optimal pattern is:

```python
import threading
import sqlite3
from queue import Queue

class SQLitePool:
    """Single writer, multiple readers connection pattern."""

    def __init__(self, db_path):
        self.db_path = db_path

        # single write connection
        self._writer = self._make_conn()
        self._write_lock = threading.Lock()

        # pool of read connections
        self._readers = Queue()
        for _ in range(4):
            conn = self._make_conn()
            conn.execute("PRAGMA query_only = ON")
            self._readers.put(conn)

    def _make_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA mmap_size=268435456")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def read(self, sql, params=()):
        conn = self._readers.get()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            self._readers.put(conn)

    def write(self, sql, params=()):
        with self._write_lock:
            self._writer.execute(sql, params)
            self._writer.commit()
```

---

## 18. Advanced Topics

### Application-Defined Functions

```python
import sqlite3
import hashlib
import re

conn = sqlite3.connect(":memory:")

# scalar function
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

conn.create_function("sha256", 1, sha256)
print(conn.execute("SELECT sha256('hello')").fetchone()[0])

# deterministic function (can be used in indexes)
conn.create_function("sha256", 1, sha256, deterministic=True)

# regexp function (not built into SQLite by default)
def regexp(pattern, string):
    return bool(re.search(pattern, string))

conn.create_function("REGEXP", 2, regexp)
# now you can use: SELECT * FROM users WHERE email REGEXP '^[a-z]+@'

# aggregate function
class Median:
    def __init__(self):
        self.values = []

    def step(self, value):
        if value is not None:
            self.values.append(value)

    def finalize(self):
        if not self.values:
            return None
        s = sorted(self.values)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2

conn.create_aggregate("median", 1, Median)
```

### The SQLite Amalgamation

SQLite is distributed as a single C source file: **`sqlite3.c`** (the "amalgamation"), along with `sqlite3.h` and the `sqlite3` CLI.

- **~250,000 lines** of C code in one file
- The amalgamation is 50-100% faster than separately compiled source files, because the compiler can inline across module boundaries and optimize the entire codebase as one unit
- Typical compiled size: **~600KB** (can be reduced to ~300KB with `SQLITE_OMIT_*` flags)
- Drop `sqlite3.c` and `sqlite3.h` into your project and compile. That's it. No build system, no dependencies, no dynamic linking required.

### Compile-Time Options

Key options for customizing SQLite:

```c
// threading mode
#define SQLITE_THREADSAFE 1        // 0=single-thread, 1=serialized (default), 2=multi-thread

// enable extensions
#define SQLITE_ENABLE_FTS5 1
#define SQLITE_ENABLE_RTREE 1
#define SQLITE_ENABLE_JSON1 1      // default since 3.38.0
#define SQLITE_ENABLE_MATH_FUNCTIONS 1

// recommended hardening
#define SQLITE_DQS 0               // disable double-quoted string literals

// tuning
#define SQLITE_DEFAULT_WAL_SYNCHRONOUS 1  // NORMAL sync in WAL mode
#define SQLITE_DEFAULT_MEMSTATUS 0         // disable memory tracking overhead

// omit unused features to reduce binary size
#define SQLITE_OMIT_DEPRECATED 1
#define SQLITE_OMIT_DECLTYPE 1
#define SQLITE_OMIT_PROGRESS_CALLBACK 1
```

### The Authorizer Callback

SQLite's answer to access control — a callback that approves or denies every SQL operation:

```python
import sqlite3

def authorizer(action, arg1, arg2, db_name, trigger_name):
    # deny all DELETE operations
    if action == sqlite3.SQLITE_DELETE:
        return sqlite3.SQLITE_DENY
    # deny access to sensitive tables
    if action == sqlite3.SQLITE_READ and arg1 == "secrets":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK

conn = sqlite3.connect("mydb.db")
conn.set_authorizer(authorizer)

conn.execute("SELECT * FROM users")    # OK
conn.execute("DELETE FROM users")      # raises OperationalError
```

### SQLite's Testing Methodology

SQLite has one of the most thoroughly tested codebases in the history of software:

- **100% branch coverage** (Modified Condition/Decision Coverage — MC/DC, the most rigorous coverage metric)
- **Over 150 million test cases** in the test suite
- Test code is **~600x the size** of the SQLite library itself
- Three independent test harnesses:
  1. **TCL Test Suite**: ~45,000 test cases
  2. **TH3 (Test Harness 3)**: Proprietary, achieves 100% MC/DC coverage, tests every error path including malloc failures
  3. **SQL Logic Test (SLT)**: ~7 million SQL statements for correctness verification
- **Out-of-memory testing**: every `malloc()` is tested for failure
- **I/O error simulation**: tests behavior on disk read/write failures
- **Crash simulation**: tests at every point during a transaction
- **Extensive fuzzing** with AFL, libfuzzer, and custom fuzzers
- **Valgrind and AddressSanitizer** for memory error detection

This testing rigor is why SQLite can be trusted in flight software, medical devices, and financial systems.

### Attached Databases

```sql
-- work with multiple database files simultaneously
ATTACH DATABASE 'analytics.db' AS analytics;
ATTACH DATABASE 'archive.db' AS archive;

-- query across databases
SELECT u.name, a.event_count
FROM main.users u
JOIN analytics.user_stats a ON a.user_id = u.id;

-- move data between databases
INSERT INTO archive.old_orders SELECT * FROM main.orders WHERE created_at < '2023-01-01';
DELETE FROM main.orders WHERE created_at < '2023-01-01';

DETACH DATABASE analytics;
```

You can attach up to 125 databases (default 10, configurable) to a single connection.

---

## 19. Limits & Constraints

| Limit | Value |
|---|---|
| Maximum database size | **281 TB** (theoretical; practical limit ~1 TB) |
| Maximum string or BLOB length | **1 billion bytes** (1 GB) |
| Maximum number of columns per table | **32,767** (default 2,000) |
| Maximum SQL statement length | **1 billion bytes** (default 1,000,000,000) |
| Maximum number of tables | No hard limit (limited by schema size) |
| Maximum number of attached databases | **125** (default 10) |
| Maximum page size | **65,536 bytes** |
| Minimum page size | **512 bytes** |
| Maximum number of pages | **4,294,967,294** (2³² – 2) |
| Maximum number of rows | **2⁶⁴** (limited by storage) |
| Maximum number of host parameters in SQL | **32,766** (default 999) |
| Maximum expression tree depth | **1,000** |
| Maximum terms in compound SELECT | **500** |
| Maximum arguments to a function | **127** (default 100) |
| Maximum `LIKE` / `GLOB` pattern length | **50,000 bytes** |

### Practical Performance Boundaries

- **Database size**: Best performance under ~100 GB. Works at larger sizes but a server database will outperform.
- **Write throughput**: 50,000–100,000+ inserts/second in a single transaction (hardware-dependent).
- **Read throughput**: Can serve millions of reads per second for simple queries from cache.
- **Concurrent users**: Handles dozens of concurrent readers easily. One writer at a time.
- **Website traffic**: SQLite handles most websites with ease. The "100K hits/day" guideline from the SQLite docs is conservative — many production sites use SQLite at much higher traffic with a read-heavy workload.

---

## 20. Common Mistakes

### 1. Not Using Transactions for Bulk Inserts

```python
# WRONG: ~100 inserts/second (each is its own transaction with fsync)
for row in data:
    conn.execute("INSERT INTO t VALUES (?)", (row,))

# RIGHT: ~100,000 inserts/second (one transaction, one fsync)
conn.execute("BEGIN")
for row in data:
    conn.execute("INSERT INTO t VALUES (?)", (row,))
conn.execute("COMMIT")
```

### 2. Forgetting Foreign Keys Are Off by Default

```python
conn = sqlite3.connect("mydb.db")
# foreign keys are NOT enforced here!

conn.execute("PRAGMA foreign_keys = ON")  # must do this per connection
```

### 3. Using NOT IN with NULLs

```sql
-- BUG: returns NO rows if subquery produces any NULL
SELECT * FROM users WHERE id NOT IN (SELECT manager_id FROM teams);

-- FIX: use NOT EXISTS
SELECT * FROM users u
WHERE NOT EXISTS (SELECT 1 FROM teams t WHERE t.manager_id = u.id);
```

### 4. Not Setting Busy Timeout

```python
# WRONG: immediately raises OperationalError on any lock contention
conn = sqlite3.connect("mydb.db")

# RIGHT: wait up to 5 seconds for locks to clear
conn = sqlite3.connect("mydb.db", timeout=5.0)
```

### 5. Using AUTOINCREMENT When You Don't Need It

```sql
-- WASTEFUL: maintains sqlite_sequence table, slightly slower
CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);

-- SUFFICIENT: auto-increments already, just allows rowid reuse
CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT);
```

Only use `AUTOINCREMENT` if your application specifically requires that deleted row IDs are never reused.

### 6. Storing Dates Incorrectly

```sql
-- BAD: ambiguous format, won't sort correctly, can't use date functions
INSERT INTO events (date) VALUES ('1/15/2024');
INSERT INTO events (date) VALUES ('Jan 15, 2024');

-- GOOD: ISO 8601, sorts correctly, works with all date functions
INSERT INTO events (date) VALUES ('2024-01-15');
INSERT INTO events (date) VALUES (datetime('now'));
```

### 7. Assuming Column Types Are Enforced

```sql
-- this SUCCEEDS in regular SQLite — 'not_a_number' is stored as TEXT
CREATE TABLE t (age INTEGER);
INSERT INTO t VALUES ('not_a_number');

-- use STRICT tables if you want enforcement
CREATE TABLE t (age INTEGER) STRICT;
INSERT INTO t VALUES ('not_a_number');  -- ERROR
```

---

## Mastery Checklist

You've reached mastery when you can:

1. Explain the VDBE, B-tree, and Pager layers and how they interact during a transaction.
2. Read an `EXPLAIN QUERY PLAN` output and know immediately whether you need an index, which index, and why.
3. Configure the optimal set of PRAGMAs for a given workload and explain why each one matters.
4. Design a schema using `WITHOUT ROWID`, `STRICT`, generated columns, and partial indexes — each where it fits.
5. Implement a robust embedded database layer with proper connection management, write serialization, and error handling.
6. Use SQLite as an application file format with schema versioning and migration.
7. Choose between SQLite, PostgreSQL, and DuckDB for a given use case and justify the decision.
8. Write recursive CTEs, window functions, and JSON queries fluently.
9. Debug `SQLITE_BUSY` errors, understand the five lock states, and explain WAL mode's concurrency model.
10. Articulate why SQLite can be trusted in safety-critical systems — cite its testing methodology.

---

## Recommended Reading Path

1. **[SQLite Documentation](https://www.sqlite.org/docs.html)** — Start with "About SQLite", then "SQL Language Reference", then "Pragma Statements".
2. **[How SQLite Is Tested](https://www.sqlite.org/testing.html)** — Understanding the testing methodology builds justified confidence.
3. **[SQLite as an Application File Format](https://www.sqlite.org/appfileformat.html)** — The official case for using SQLite as your file format.
4. **[35% Faster Than The Filesystem](https://www.sqlite.org/fasterthanfs.html)** — Benchmark data on SQLite vs direct file I/O.
5. **[The SQLite Amalgamation](https://www.sqlite.org/amalgamation.html)** — How and why SQLite ships as one C file.
6. **[Well-Known Users of SQLite](https://www.sqlite.org/famous.html)** — Official list of notable deployments.
7. **Simon Willison's blog** ([simonwillison.net](https://simonwillison.net)) — Prolific writer on SQLite tools, Datasette, sqlite-utils.
8. **[Fly.io's SQLite series](https://fly.io/blog/all-in-on-sqlite-litestream/)** — Production experience running SQLite at the edge.
9. **[Consider SQLite](https://blog.wesleyac.com/posts/consider-sqlite)** — Practical arguments for using SQLite more broadly.
10. **Source code** — The amalgamation is one file. Reading it (especially the header comment and the VDBE opcodes) is educational.

---

SQLite's power is in what it omits. By removing the server, the network protocol, the access control system, and the configuration files, what remains is a fast, reliable, portable SQL engine that just works. The database is a file. The engine is a library call. For the majority of applications — mobile, desktop, IoT, development, edge computing, data analysis — this is not a compromise. It's the right architecture.

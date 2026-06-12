# Database Internals: PostgreSQL and SQLite

A textbook-level study guide to what happens beneath SQL — the page layouts, B-trees, buffer pools, write-ahead logs, MVCC machinery, and query engines — taught through the two most instructive open-source databases to study side by side. PostgreSQL and SQLite are both single-node, both B-tree-based, both exhaustively documented and readable — and they disagree about almost every other decision: client-server versus in-process library, heap tables with secondary indexes versus clustered B-trees, row-version MVCC with vacuum versus whole-database snapshots with a single writer, redo-only WAL versus a choice of undo journaling or WAL. Wherever the two systems diverge, the divergence is a *lesson*: the same theory, two defensible answers, and a design space made visible. The sibling guides cover using these systems ([PostgreSQL](POSTGRES.md), [Advanced PostgreSQL](ADVANCED_POSTGRES.md), [SQLite](SQLITE_STUDY_GUIDE.md)); this one is about *being* them.

The style follows this repo's [Distributed Algorithms guide](DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md): precise definitions, mechanisms traced to the byte level where the bytes matter, claims you can verify against source code and introspection tools, and exercises closing every chapter — most of them runnable, because both systems ship the instruments needed to dissect them live (`pageinspect`, `pg_waldump`, `EXPLAIN (ANALYZE, BUFFERS)`; `sqlite3`'s `.dbinfo`, `EXPLAIN`, `sqlite3_analyzer`, and the `dbstat`/`sqlite_dbpage` virtual tables).

Primary references: Andy Pavlo's [CMU 15-445/645](https://15445.courses.cs.cmu.edu/) lectures (public, graduate-level, the best structured course on this material); Alex Petrov, [*Database Internals*](https://www.databass.dev/); the PostgreSQL source tree's READMEs (especially [`src/backend/access/nbtree/README`](https://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/nbtree/README) and [`src/backend/access/heap/README.HOT`](https://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/README.HOT)) and the [internals chapters of the manual](https://www.postgresql.org/docs/current/internals.html); Hironobu Suzuki's [*The Internals of PostgreSQL*](https://www.interdb.jp/pg/); and SQLite's own documentation, which is a textbook in disguise — [Database File Format](https://www.sqlite.org/fileformat2.html), [Atomic Commit](https://www.sqlite.org/atomiccommit.html), [Write-Ahead Logging](https://www.sqlite.org/wal.html), [The Virtual Database Engine](https://www.sqlite.org/vdbe.html), and [The Next-Generation Query Planner](https://www.sqlite.org/queryplanner-ng.html).

---

## Table of Contents

1. [Chapter 1 — The Shape of a Database Engine](#chapter-1--the-shape-of-a-database-engine)
2. [Chapter 2 — Pages: The On-Disk Layout](#chapter-2--pages-the-on-disk-layout)
3. [Chapter 3 — B-Trees](#chapter-3--b-trees)
4. [Chapter 4 — The Buffer Pool and the I/O Path](#chapter-4--the-buffer-pool-and-the-io-path)
5. [Chapter 5 — Logging, Recovery, and Durability](#chapter-5--logging-recovery-and-durability)
6. [Chapter 6 — MVCC and Transaction Isolation](#chapter-6--mvcc-and-transaction-isolation)
7. [Chapter 7 — Locking and Concurrency Control](#chapter-7--locking-and-concurrency-control)
8. [Chapter 8 — Query Processing I: Parsing, Statistics, and Planning](#chapter-8--query-processing-i-parsing-statistics-and-planning)
9. [Chapter 9 — Query Processing II: Execution](#chapter-9--query-processing-ii-execution)
10. [Chapter 10 — Beyond the B-Tree: Other Indexes, and the LSM Road Not Taken](#chapter-10--beyond-the-b-tree-other-indexes-and-the-lsm-road-not-taken)
11. [Chapter 11 — Two Walkthroughs: The Life of a Query and the Life of a Write](#chapter-11--two-walkthroughs-the-life-of-a-query-and-the-life-of-a-write)
12. [Chapter 12 — Where to Go Next](#chapter-12--where-to-go-next)

---

## Chapter 1 — The Shape of a Database Engine

### 1.1 The layer cake

Every relational engine, however different its skin, decomposes into the same stack — worth fixing as a map before descending:

```
SQL text
  │  parser            → parse tree (grammar only; "is this SQL?")
  │  analyzer/rewriter → query tree (names resolved, views expanded)
  │  planner/optimizer → plan tree (the *how*: scans, joins, order)   Ch. 8
  │  executor          → rows (iterators / bytecode)                  Ch. 9
  ├─ access methods    → tables & indexes as trees and heaps          Ch. 2–3, 10
  ├─ buffer manager    → pages cached in memory, pinned, dirtied      Ch. 4
  ├─ transaction mgr   → visibility, isolation, locks                 Ch. 6–7
  ├─ WAL / journal     → durability and crash recovery                Ch. 5
  └─ storage           → files, fsync, the operating system
```

The two case studies instantiate the stack at opposite ends of the architecture spectrum:

**PostgreSQL** is a client-server system: a postmaster forks a backend process per connection (one query's state lives in one process); shared state — the buffer pool, lock tables, WAL buffers — lives in shared memory mapped by all backends; background processes (checkpointer, background writer, WAL writer, autovacuum workers) do maintenance asynchronously. Concurrency is the *point*: hundreds of backends reading and writing the same pages, coordinated by fine-grained locks and MVCC.

**SQLite** is a library: the "server" is linked into your process, the database is one file, and a query is a function call away. There is no daemon to coordinate writers, so coordination happens through the *file itself* (POSIX locks, a shared-memory index in WAL mode) and the concurrency model is drastically simpler: many readers, **one writer at a time, total**. SQLite's own docs call it a replacement for `fopen()`, not for PostgreSQL — and the design decisions that follow from that one sentence are half this guide.

The deepest contrast, planted now and harvested in Chapters 3 and 6: **PostgreSQL tables are heaps** — unordered bags of row versions, with *all* indexes secondary, pointing at physical row addresses — while **SQLite tables are themselves B-trees** keyed on the rowid (or the primary key, for `WITHOUT ROWID` tables): the table *is* its primary index. And **PostgreSQL implements MVCC by keeping multiple versions of each row in the heap**, while **SQLite versions the whole database** (a reader in WAL mode sees the file as of a moment, via the log). Most of each system's personality — vacuum, HOT updates, index bloat on one side; the single writer, the busy timeout, blazing point reads on the other — falls out of these two choices.

### 1.2 How to study an engine (the tooling you'll use throughout)

Textbook claims about internals should be checkable. Your instruments:

```sql
-- PostgreSQL
CREATE EXTENSION pageinspect;            -- raw page contents, heap and index
SELECT * FROM page_header(get_raw_page('t', 0));
SELECT * FROM heap_page_items(get_raw_page('t', 0));
SELECT * FROM bt_page_items('t_pkey', 1);
EXPLAIN (ANALYZE, BUFFERS, WAL) ...;     -- plans + buffer & WAL accounting
SELECT pg_current_wal_lsn();             -- and pg_waldump on the WAL files
SELECT * FROM pg_stat_io;                -- (v16+) who did which I/O, and why
```

```
-- SQLite (CLI)
.dbinfo                                  -- header fields, page size, counts
EXPLAIN SELECT ...;                      -- VDBE bytecode (the actual program)
EXPLAIN QUERY PLAN SELECT ...;           -- planner's intent, human-readable
SELECT * FROM dbstat;                    -- per-page b-tree statistics
SELECT * FROM sqlite_dbpage;             -- raw page bytes as a virtual table
sqlite3_analyzer mydb.db                 -- space accounting per object
```

A standing suggestion for the whole guide: keep one scratch database in each system and run the exercises — both systems are honest enough to show you everything.

### Exercises 1

1. Map each layer of the cake to the process/thread that executes it in each system for a single `SELECT`: which layers run in *your* process in SQLite, and in *which* process in PostgreSQL? Where does shared state live in each?
2. From architecture alone (before reading Ch. 6), predict: which system can have two transactions writing different rows of the same table simultaneously? What is the *weakest* piece of machinery PostgreSQL must therefore own that SQLite can omit entirely?
3. SQLite advertises itself as a replacement for `fopen()`. List three guarantees it nonetheless shares with PostgreSQL that `fopen()`+`fwrite()` lack, and which chapter of this guide implements each.
4. Run `.dbinfo` on a fresh SQLite file and `SELECT * FROM page_header(get_raw_page(...))` on a fresh PostgreSQL table. Record page sizes and version fields — you will reuse both scratch databases for the rest of the guide.

---

## Chapter 2 — Pages: The On-Disk Layout

Databases read and write fixed-size **pages** (PostgreSQL: 8 KiB default; SQLite: 4 KiB default, 512–65536 configurable at creation), because the page is the unit of buffering, locking granularity decisions, I/O, and crash atomicity reasoning. Everything above this chapter manipulates pages; everything below it is the filesystem.

### 2.1 The slotted page

Both systems implement variants of the **slotted page**, the standard answer to "variable-length rows on a fixed-size page":

```
+------------------+ 0
| page header      |
| slot array  →    |   slots/cell-pointers grow downward →
|------------------|
|   free space     |
|------------------|
|   ← row data     |   records grow upward ←
+------------------+ pagesize
```

The indirection through the slot array is the load-bearing trick: a row's *physical* position on the page can change (compaction after deletes) without changing its *address* — which is slot-based, not offset-based. PostgreSQL addresses a row version by **ctid** = `(page number, slot number)`, also known as an *item pointer* — and because every index entry stores ctids, the stability of slots is what keeps indexes valid while pages defragment in place.

### 2.2 PostgreSQL: heap pages and tuples

A heap page (`src/include/storage/bufpage.h`):

- **PageHeaderData**, 24 bytes: `pd_lsn` (the WAL position of the last change — the linchpin of recovery ordering, Ch. 5), `pd_checksum`, `pd_lower`/`pd_upper` (the free-space boundaries), `pd_special` (unused in heaps; B-tree pages keep sibling links there, Ch. 3).
- The **line pointer array** (`ItemIdData`, 4 bytes each): offset, length, and a 2-bit state — `NORMAL`, `UNUSED`, `DEAD`, or `REDIRECT` (the last two are vacuum's and HOT's vocabulary, Ch. 6).
- **Tuples**, each prefixed by a 23-byte **HeapTupleHeader** whose fields *are* the MVCC machine: `t_xmin` (inserting transaction ID), `t_xmax` (deleting/locking transaction ID, 0 if live), `t_cid` (command ID within the transaction), `t_ctid` (forward pointer to the newer version of this row, or to itself), `t_infomask` (hint bits — Ch. 6), then the null bitmap and the user data. Read that field list again: **PostgreSQL spends ~23 bytes per row version on visibility bookkeeping.** That's the price tag of heap MVCC, payable in advance, and small rows pay the highest rate.

**TOAST** (The Oversized-Attribute Storage Technique) handles values that don't fit: a tuple is kept under ~2 KiB (a quarter page) by compressing large attributes (`pglz` or, since v14, `lz4`) and/or moving them *out of line* into a companion TOAST table, sliced into ~2 KiB chunks, with an 18-byte pointer left in the main tuple. Consequences worth knowing cold: wide values cost an extra (indexed) lookup to fetch; `SELECT *` detoasts everything while `SELECT id` touches nothing; and an `UPDATE` that doesn't modify a TOASTed column doesn't rewrite it — the new row version points at the same TOAST chunks.

### 2.3 SQLite: B-tree pages, varints, and records

The first 100 bytes of file are the **database header** (`"SQLite format 3\0"`, page size, file format versions, change counters, schema cookie). Every page thereafter is a B-tree page (or an overflow/freelist/ptrmap page). Four B-tree page types: table leaf (0x0D), table interior (0x05), index leaf (0x0A), index interior (0x02). Layout is the slotted page again: an 8/12-byte header, a **cell pointer array** growing downward, **cells** growing upward, a freeblock list threading the holes.

Two encoding decisions define SQLite's on-disk character:

- **Varints**: integers are stored in 1–9 bytes, high-bit-continuation encoded, so small numbers (rowids, lengths, type codes — most numbers in a database) cost one or two bytes. The format is biased toward smallness everywhere.
- The **record format**: each row is a header of *serial type* codes followed by the values. Serial types encode type *and* size in one varint (`0` = NULL, `1..6` = integers of 1/2/3/4/6/8 bytes, `7` = float, even/odd codes ≥ 12 = BLOBs/strings with length embedded) — and notably, the *same column* can use different serial types in different rows: an `INTEGER` column stores 1-byte values for small numbers, 8-byte for large. This is **dynamic typing materialized in storage** — flexible, compact, and the reason SQLite rows have no fixed layout to compute offsets into; every read parses the header. Cells too large for a page spill into a linked chain of **overflow pages** (the analog of TOAST, minus compression and minus the independent table).

A useful contrast snapshot: PostgreSQL pays bytes for *visibility* (23-byte tuple headers, so concurrent readers/writers never block each other); SQLite pays bytes for *nothing* — its per-row overhead is a few varints — and pays instead in concurrency (Ch. 6–7). Storage layout is policy, made permanent.

### Exercises 2

1. Insert three rows in a PostgreSQL table; `UPDATE` the second; inspect with `heap_page_items`. Identify `t_xmin`/`t_xmax`/`t_ctid` on all *four* tuples present, and explain each field's value. Which line pointer states do you see?
2. Compute the maximum number of `(int, int)` rows on one 8 KiB PostgreSQL heap page (24-byte page header, 4-byte line pointers, 23-byte tuple headers + alignment to 8 bytes, 8 bytes of data). Compare with SQLite's count for the same logical rows on a 4 KiB page (assume 2-byte cell pointers, ~2-byte cell header, 1–2-byte varints) — then verify both empirically (`pageinspect`; `dbstat`).
3. Store a 100 KiB string in each system. In PostgreSQL, find it in the TOAST table (`pg_class.reltoastrelid`); in SQLite, observe the overflow chain via `dbstat`'s `pageno`/`payload` columns. What does each system re-write if you `UPDATE` a *different* column of that row?
4. Why must the slot/cell-pointer indirection exist at all? Describe concretely what would break in PostgreSQL if indexes stored byte offsets instead of ctids, the first time a page compacted after a delete.
5. SQLite's serial-type system means `CREATE TABLE t(x INTEGER)` can store `1` in one byte. What is the equivalent storage for `int8` in PostgreSQL, and why *can't* PostgreSQL do the same trick? (Hint: how does each system find column 7 of a row?)

---

## Chapter 3 — B-Trees

The B-tree is the data structure that *is* the relational database in practice — both systems bet everything on it. This chapter does the theory once, then each system's deviations, which are where the insight lives.

### 3.1 The B+-tree, and why it fits disks

A **B+-tree** of fanout *f* stores all data in leaves, with interior nodes holding only separator keys; all leaves sit at the same depth (the tree grows by splitting *upward*, at the root — it is always perfectly balanced). Height is ⌈log_f N⌉, and the arithmetic is the whole argument: with 8 KiB pages and ~200–500 separators per interior page, **a billion rows fit in a tree of height 3–4**. A point lookup is 3–4 page reads, of which the top levels are effectively always cached (Ch. 4) — so "one or two I/Os per lookup, forever, regardless of N" is the B-tree's contract with the disk. Leaves are sibling-linked for ordered range scans. Compare hashing (O(1) but no ranges, and ugly growth) and you know why every general-purpose engine chose this.

Mechanics to have at your fingertips: **search** descends by binary-searching separators; **insert** finds the leaf, inserts in place if it fits, else **splits** the leaf (half the entries move to a new right sibling; a new separator is inserted into the parent — possibly splitting it, recursively; a root split adds a level, the only way the tree gets taller); **delete** in textbooks merges underfull nodes — in production engines, *delete is lazy*: both PostgreSQL and SQLite mark/remove entries and reclaim a page only when fully empty (PostgreSQL recycles it via FSM after a vacuum interlock; SQLite moves it to the freelist), accepting some fragmentation in exchange for not paying rebalancing costs on every delete. Textbook deletion is one of the field's great pedagogical lies of omission.

**Split policy meets workload**: a 50/50 split is optimal for random inserts; for *rightmost* (append-order: sequential IDs, timestamps) inserts, both systems instead split unevenly/fill the right edge, yielding ~90%+ packed pages for monotonic keys. This — plus cache locality on the rightmost path — is the mechanical content of the advice "prefer sequential keys over UUIDv4 for insert-heavy tables"; random UUIDs spray inserts across all leaves, splitting everywhere at ~50% utilization (UUIDv7 exists precisely to restore key monotonicity).

### 3.2 PostgreSQL's nbtree: Lehman–Yao concurrency

The interesting question for a server engine: how do hundreds of backends traverse a tree that's splitting under them, without lock-crabbing their way down (parent locked until child locked — correct, but a concurrency disaster at the root)? PostgreSQL's `nbtree` implements **Lehman & Yao's B-link tree**:

- Every page carries a **right-sibling link** and a **high key** (an upper bound on keys belonging to this page).
- A descending reader takes *no* locks above the page it's currently reading. If, between reading a parent and arriving at the child, the child split — the sought key may have moved right — the reader detects it (search key exceeds the high key) and simply **follows the right-link**, possibly several times.
- A split therefore needs to lock only the splitting page and its new sibling (then, separately and lazily, insert the new separator into the parent — even a crash between the two halves leaves a correct, merely slower, tree; the right-link covers the gap until vacuum or a later insert completes the parent entry).

The deep idea — *make readers tolerate stale parent information and give them a recovery edge to follow, rather than excluding writers* — is the same move as optimistic concurrency everywhere, and it's why B-tree contention almost never shows up in PostgreSQL profiles. Two modern refinements worth naming: **suffix truncation** (separator keys in interior pages keep only the prefix needed to distinguish — fatter fanout, shorter tree) and **deduplication** (v13: equal keys in a leaf stored once with a ctid list — shrinking indexes on low-cardinality columns dramatically) plus **bottom-up index deletion** (v14: inserts that would split a page first try to evict entries pointing at dead heap tuples — directly attacking version-churn bloat, Ch. 6's index tax).

### 3.3 SQLite: the table *is* a B-tree

SQLite has two B-tree flavors: **table B-trees** (leaf cells = `(rowid varint, record)`, keyed by integer rowid — interior pages hold only rowids and child pointers, making them extremely high-fanout) and **index B-trees** (cells = the indexed columns' record + the rowid, no separate payload). An ordinary table is a table B-tree; `INTEGER PRIMARY KEY` makes your column *be* the rowid (zero-cost primary key); every secondary index lookup finds rowids, then probes the table B-tree — so **every secondary-index hit costs two tree descents** (the analog of a clustered-index lookup in InnoDB, and the reason `WITHOUT ROWID` tables exist: the table is then keyed directly on your declared primary key — better when the natural key *is* the lookup key and rows are small; worse when the PK is fat, since every secondary index then embeds it).

Contrast with PostgreSQL's heap, now sharpened: a PostgreSQL index hit costs one descent plus one heap page fetch by ctid (no second tree), but the heap guarantees nothing about physical order (`CLUSTER` is a one-shot rewrite, not maintained), while SQLite gives you primary-key clustering *by construction* — adjacent keys are physically adjacent, so PK range scans are sequential reads. Neither dominates; you now know exactly what each buys.

One SQLite-specific structural note: the tree's parent pointers don't exist on disk (descent is always from the root; splits are simpler than Lehman–Yao because **there is only one writer** — concurrency solved by fiat, Ch. 7); and `auto_vacuum` mode maintains **ptrmap** pages so pages can be relocated to truncate the file, the closest SQLite comes to PostgreSQL's vacuum world.

### Exercises 3

1. Compute tree heights: PostgreSQL B-tree over `bigint` keys (16-byte index tuples + line pointers on 8 KiB pages) for 10⁶ and 10⁹ rows; SQLite table B-tree interior fanout for 4 KiB pages and 2-byte average rowid varints. Verify the PostgreSQL height with `bt_metap('idx')`.
2. Trace, by hand, a Lehman–Yao reader racing a split: reader reads parent P (child C contains keys ≤ 50), writer splits C at 30 into C and C′, reader arrives at C seeking 42. Walk the steps to the right answer. What single piece of on-page state made it work?
3. Demonstrate the UUID effect: insert 10⁶ rows keyed by `uuid4()` vs. sequential `bigint` into both systems; compare index/file size and (PostgreSQL) `bt_metap`/`pgstattuple` leaf density, (SQLite) `sqlite3_analyzer` packing. Explain the difference via split policy.
4. In SQLite, why does `SELECT * FROM t WHERE rowid BETWEEN 1000 AND 2000` read pages sequentially while the equivalent ctid-range trick in PostgreSQL does not retrieve rows in key order? Connect to the clustered-vs-heap decision.
5. PostgreSQL's split inserts the parent separator *after* releasing the split pages, and may crash in between. Argue (from the right-link + high-key invariants) that searches remain correct in the interim, and name the kind of consistency this resembles from the Distributed Algorithms guide.

---

## Chapter 4 — The Buffer Pool and the I/O Path

The buffer pool is the database's answer to "RAM is fast, disks are not, and we promised durability anyway": cache pages in memory, modify them there, write them back *on a schedule decoupled from commits* (the WAL, Ch. 5, is what makes that decoupling safe). It is also where the database and the operating system step on each other.

### 4.1 PostgreSQL: shared_buffers and the clock sweep

`shared_buffers` is an array of 8 KiB slots in shared memory with a hash table mapping `(relation, fork, block#) → slot`. Each slot's header carries a **pin count** (how many backends are using the page right now — a pinned page is never evicted) and a **usage count** (popularity, capped at 5). Eviction is **clock sweep** — approximate LRU without LRU's lock contention: a hand circles the array; each pass decrements usage counts; a page with count 0 and no pins is evictable. Frequently-touched pages (index roots, hot rows) keep getting re-bumped to 5 and effectively never leave; the upper tree levels staying memory-resident is what cashes the B-tree height argument of Chapter 3.

Dirty pages are written back by (in order of preference) the **checkpointer** (Ch. 5, spread writes), the **background writer** (keeps a trickle of clean evictable pages ahead of demand), or — the case you tune to avoid — *a foreground backend that needed a slot and found only dirty candidates*, paying the write (plus possibly a WAL flush, by the WAL-before-data rule) on the query's critical path. `pg_stat_io` (v16+) breaks out exactly who wrote what and why; `EXPLAIN (BUFFERS)` shows per-query hits/reads/dirtied — the two instruments that turn this chapter from theory into tuning.

Two refinements that prevent classic pathologies: **ring buffers** — large sequential scans, bulk loads (`COPY`), and vacuum confine themselves to a small private ring of buffers (hundreds of KiB; vacuum's is settable via `vacuum_buffer_usage_limit`) instead of flushing the entire working set out of the pool — the direct fix for "one analyst's table scan evicted the OLTP cache"; and **backend-private temp buffers** for temporary tables (`temp_buffers`), which need no shared coordination at all.

The honest blemish: **double buffering**. PostgreSQL reads via the OS page cache (buffered I/O), so hot pages occupy RAM twice — once in `shared_buffers`, once in the kernel. Hence the heuristic of `shared_buffers` ≈ 25% of RAM (let the kernel use the rest, it's good at it) rather than the ~100% a direct-I/O engine like InnoDB takes; asynchronous and direct I/O work in recent releases (`io_method`, `debug_io_direct`) is slowly renegotiating this truce with the kernel.

### 4.2 SQLite: the pager

SQLite's equivalent layer is the **pager**, sitting between the B-tree module and the VFS (the OS-abstraction layer — also the hook point for encryption layers and the test harness's fault injection). Each connection has a private page cache (default ~2 MB, `PRAGMA cache_size`) — there being no server, there is no shared pool; in WAL mode, what's *shared* between connections is not cached pages but the **WAL index** in a shared-memory file (`-shm`), which tells every reader which page versions exist in the log (Ch. 5–6). The pager enforces the same fundamental rules as PostgreSQL's buffer manager — journal-before-data, no eviction of pinned pages — in two thousand lines instead of twenty thousand, and reading `pager.c` after `bufmgr.c` is one of the best compare-and-contrast exercises in open source.

`PRAGMA mmap_size` offers memory-mapped reads — genuinely faster for read-heavy embedded workloads (no syscall, no copy) and a genuine trade: I/O errors become signals rather than error codes, and a stray pointer write in the host process can corrupt the mapped database. The decision — and the fact that the *application* gets to make it — is very SQLite.

### 4.3 What both must fear from the OS

The page cache giveth and taketh: `write()` puts data in kernel memory, not on disk; only `fsync()` (or `fdatasync`) makes it durable, and the *scheduling* of writeback is the kernel's. Both engines therefore reason exclusively in terms of explicit sync points (Ch. 5). Beyond that, the platform fine print that production engineers eventually meet: partial (torn) page writes on power loss — neither 8 KiB nor 4 KiB writes are atomic on most stacks — handled by full-page images / journaling (Ch. 5); `posix_fadvise` readahead interplay for sequential scans; and the fact that an `fsync` *failure* may not mean what anyone hoped (Ch. 5's fsyncgate). The buffer pool chapter's closing moral: **a database is a program that has stopped trusting the operating system politely.**

### Exercises 4

1. Run a query twice in PostgreSQL with `EXPLAIN (ANALYZE, BUFFERS)`: explain the `shared read` → `shared hit` shift. Then scan a table 4× larger than `shared_buffers` and explain, via the ring buffer, why repeated scans *don't* convert to hits.
2. Why must a pinned page never be evicted, even at usage 0? Construct the corruption that eviction-under-pin would permit (two backends, one page, one eviction).
3. Clock sweep vs. strict LRU: describe a workload where they differ materially, and explain why PostgreSQL accepts the approximation (what shared data structure would strict LRU require *per page access*?).
4. In SQLite WAL mode, two connections from different processes have private page caches — yet a reader never sees a stale page after another process commits. What invalidates/redirects its cached view? (You may peek at Ch. 5–6; the answer lives in the WAL index.)
5. Estimate the RAM wasted by double buffering for a PostgreSQL instance with `shared_buffers=8GB` and a 30 GB hot working set, and explain why the answer differs between read-mostly and write-heavy workloads.

---

## Chapter 5 — Logging, Recovery, and Durability

The problem: commits must be durable and atomic, but dirty pages are written lazily (Ch. 4), and a crash can interrupt *anything* — including a single page write. The universal solution: **write-ahead logging** — record intentions sequentially and durably *first*, let the random-access data files lag, and replay/undo from the log after a crash. The two systems implement two distinct classic flavors, and SQLite implements *both*, selectable per database.

### 5.1 PostgreSQL: redo-only WAL

Every modification generates a **WAL record** (insert this tuple at this ctid; split this page; commit this xid), appended to a sequential log addressed by **LSN** (log sequence number — a byte position in the WAL stream). The two protocol rules that make lazy page writing safe:

1. **WAL-before-data**: a dirty page may be written to the data files only after the WAL up through that page's `pd_lsn` is fsynced. (The page header's LSN, Ch. 2, exists exactly for this comparison.)
2. **Commit = WAL flush**: `COMMIT` returns only after the commit record is fsynced (`synchronous_commit=on`). Data pages may be arbitrarily stale on disk; the log is the truth.

Crash recovery is then pure **redo**: start from the last **checkpoint** (a recorded moment at which all then-dirty pages were known flushed), replay every WAL record forward, idempotently (each record applies only if the target page's LSN is older — LSN comparison makes replay safely re-runnable). There is no undo pass: PostgreSQL never needs one *because MVCC already keeps old versions in the heap* — an aborted transaction's rows are simply never marked committed, and vacuum collects them (Ch. 6). This is the elegant interlock of the whole design: **MVCC is the undo log**, amortized into the table.

The details that matter operationally, each a small theorem:

- **Torn pages and full-page writes**: if a crash interrupts an 8 KiB page write, the page may be half-old/half-new — and redo against a *corrupt base* is garbage. Fix: the first modification of each page after a checkpoint logs a **full-page image** (FPI); replay restores the image, then applies records. Corollaries: WAL volume spikes after every checkpoint; spreading checkpoints further apart (`max_wal_size`) reduces FPI traffic; `pg_waldump --stats` shows you the FPI share directly.
- **Checkpoints** are *spread* (`checkpoint_completion_target`) so the flush of gigabytes of dirty pages doesn't slam the disks at once; recovery time scales with checkpoint distance — the knob trades steady-state write amplification against restart latency.
- **Group commit**: concurrent committers share fsyncs (one flush durably commits everyone whose record it covers); `synchronous_commit=off` goes further — commit returns before the flush, risking the last ~`wal_writer_delay`×3 of *acknowledged* transactions on a crash but never corruption or torn replay (the WAL rules still hold). Know exactly which guarantee each setting sells.
- **fsyncgate** (2018), the cautionary tale: PostgreSQL assumed a failed `fsync` could be retried; on Linux, the kernel may *clear the error state and drop the dirty pages* after reporting the failure once — retrying "succeeds" while the data is gone. The fix was to **PANIC on fsync failure** and recover from WAL, never retry. Moral for every storage engineer: the contract you assume the OS honors is part of your correctness proof, and it was never written down where you thought.
- The same WAL stream, shipped, *is* physical replication and PITR — recovery and replication being one mechanism is the architectural dividend of redo logging.

### 5.2 SQLite mode one: the rollback journal (undo logging)

Default mode. Before modifying a page, SQLite copies the **original** page into `dbname-journal` (undo log); syncs the journal; writes the new pages into the database file *in place*; syncs; then **deletes/invalidates the journal — which is the commit instant** (one atomic event: the journal's existence flips the meaning of the main file). Crash with journal present → roll *back* by restoring the saved pages; crash after journal gone → the new data simply is the database. The [Atomic Commit](https://www.sqlite.org/atomiccommit.html) document walks every step's failure window — read it once in full; it is the cleanest published proof-sketch of crash safety anywhere.

Costs, symmetrical to PostgreSQL's: every write transaction pays ≥2 fsyncs and writes pages *twice* (journal + database); readers and the writer exclude each other during the commit window (the file is momentarily inconsistent in place); but the database is always exactly one file (plus a transient journal), and recovery is instant.

### 5.3 SQLite mode two: WAL

`PRAGMA journal_mode=WAL` inverts the roles, landing one design decision away from PostgreSQL: modified pages are **appended to `dbname-wal`** (redo log of page images); the main file is untouched until a **checkpoint** copies WAL frames back. Readers read the main file but first consult the **WAL index** (the memory-mapped `-shm` hash) to redirect any page that has a newer committed frame — each reader pinned to the WAL position at its snapshot's start, which is precisely how WAL mode buys **readers that never block the writer and vice versa** (the concurrency upgrade that motivates the mode; Ch. 6 builds isolation on it). Commit = append + (by default) sync; `synchronous=NORMAL` in WAL mode syncs only at checkpoints — the popular middle setting: durability of the last few commits traded away, corruption still impossible, the same shape of bargain as `synchronous_commit=off`.

Checkpointing is the mode's operational tax: the WAL grows until a checkpoint copies frames back, and a checkpoint can only recycle the WAL up to the *oldest reader's* position — a long-lived read transaction pins the log (`PASSIVE`/`FULL`/`RESTART`/`TRUNCATE` checkpoint variants escalate how hard it tries). Set against PostgreSQL: same redo logic, same checkpoint-vs-recovery trade, but page-image-only frames (no logical records), per-database log, and the *reader* — not vacuum — as the thing that pins history. Files: `.db` + `-wal` + `-shm`, the answer to "why are there three files now," a question every SQLite WAL user eventually asks in production.

### Exercises 5

1. Walk both failure windows of the rollback journal by hand (crash before journal sync; crash between data write and journal delete): state what's on disk and what recovery does. Then do the same for WAL mode (crash mid-append; crash mid-checkpoint).
2. With `pg_waldump --stats`, measure FPI bytes vs. record bytes for a workload of 10⁵ single-row updates immediately after a manual `CHECKPOINT`, then again without checkpointing. Explain the ratio change.
3. Prove (informally) that PostgreSQL redo is idempotent given the page-LSN rule, and exhibit what would go wrong replaying a record into a page *newer* than the record without the check.
4. Rank by durability-of-acknowledged-commits and by write amplification: PG `synchronous_commit=on/off`; SQLite rollback `synchronous=FULL`; SQLite WAL `synchronous=FULL/NORMAL`. One sentence of justification each.
5. Why does PostgreSQL need no undo pass while ARIES-style engines (InnoDB, SQL Server) do? Identify exactly which design choice (Ch. 6 preview) substitutes for undo, and what *it* costs instead.

---

## Chapter 6 — MVCC and Transaction Isolation

Multi-Version Concurrency Control is the idea that **readers and writers need not block each other if writers create new versions instead of overwriting** — every modern engine's answer to lock-based readers. The two systems implement it at opposite granularities: PostgreSQL versions *rows*; SQLite (WAL mode) versions *the database*. Both deliver snapshot reads; everything else differs.

### 6.1 PostgreSQL: row-version MVCC

Chapter 2 planted the fields; here is the machine. Every transaction gets a 32-bit **xid**. Every tuple carries `t_xmin` (creator) and `t_xmax` (deleter — or 0). The operations:

- `INSERT`: new tuple, `xmin` = my xid.
- `DELETE`: set `xmax` = my xid on the current version. Nothing is removed.
- `UPDATE` = `DELETE` + `INSERT`: the old version gets `xmax`, a complete new version is written (`t_ctid` of the old points to the new). **Every update physically duplicates the row.**

A **snapshot** is `(xmin_horizon, xmax_horizon, [in-progress xids])` taken at statement start (READ COMMITTED) or transaction start (REPEATABLE READ). A tuple is **visible** to a snapshot iff its `xmin` is committed-and-not-in-progress-and-before-the-horizon, and its `xmax` is absent/aborted/in-progress/after-horizon. Commit status itself lives in **pg_xact** (the commit log, 2 bits per xid); since checking it per-tuple forever would be ruinous, the first reader to resolve a tuple's status stamps **hint bits** into `t_infomask` (`XMIN_COMMITTED` etc.) — which is why a freshly bulk-loaded table generates a wave of *writes* on first read, an eternally surprising production observation with a one-line explanation.

The bills now come due, and naming them precisely is the point of the chapter:

- **Dead tuples**: superseded/deleted versions visible to no possible snapshot are garbage. **VACUUM** collects them: scans (guided by the **visibility map**, skipping all-visible pages), removes dead tuples, marks line pointers reusable, updates the **free space map**, and sets all-visible bits — which double as the enabler of **index-only scans** (an index can answer without heap visits only for pages the VM certifies all-visible). Autovacuum triggers on dead-tuple thresholds; a vacuum-starved table is "bloat" — the heap and indexes full of ghosts, scans slower, cache colder. Crucially, vacuum can only remove versions older than the **oldest active snapshot**: a forgotten `IDLE IN TRANSACTION` session pins the entire cluster's garbage, the precise analog of SQLite's reader pinning the WAL.
- **Index amplification & HOT**: since indexes point at ctids and an update makes a new ctid, a single-row update naively inserts into *every* index of the table. **Heap-Only Tuples** (HOT) avert this when (a) no indexed column changed and (b) the new version fits on the *same page*: the indexes keep pointing at the old line pointer, which becomes a `REDIRECT` to the chain of versions on-page. This is why `fillfactor < 100` on hot-update tables is real advice (reserve on-page room for chains), why "don't index columns you update constantly" has mechanical content, and what v14's bottom-up index deletion (Ch. 3) mops up when HOT can't apply.
- **Wraparound and freezing**: 32-bit xids wrap. Comparisons are modular (2³¹ ahead/behind), so versions older than ~2 billion xids would suddenly look *future* — therefore vacuum **freezes** old tuples (marks them visible-to-all, modernly via `t_infomask` bits), and `autovacuum_freeze_max_age` forces aggressive vacuums before the horizon approaches. The infamous "database shutting down to prevent wraparound data loss" incidents are this machinery, ignored until it became unignorable.

**Isolation levels on top**: READ COMMITTED = new snapshot per statement (plus the quietly tricky `EvalPlanQual` recheck: an update finding its target row concurrently updated re-evaluates against the *new* version — no serializability, but no lost update on the same row either). REPEATABLE READ = one snapshot per transaction — true **snapshot isolation**, which famously still admits **write skew** (two transactions each read the other's write-target and both commit: e.g., two doctors each going off-call after checking "≥2 on call"). SERIALIZABLE = **SSI** (Serializable Snapshot Isolation, Cahill/Ports & Grittner, v9.1): run as snapshot isolation but track read/write dependencies via **SIREAD locks** (predicate-level, lock nothing, block nothing), and abort a transaction whenever a *dangerous structure* — two consecutive read-write antidependencies — completes, the condition under which SI anomalies are possible. The contract: no blocking, occasional false-positive aborts, and the application **must retry on SQLSTATE 40001**. SSI is one of the few cases of a 2008 research result shipping nearly verbatim in a mainstream engine, and PostgreSQL's is still the reference implementation.

### 6.2 SQLite: the whole database as one version

SQLite has no per-row versions, no xmin/xmax, no vacuum-the-garbage problem — because it versions at file granularity. Rollback mode: readers and the writer share the *same* bytes, so isolation is by exclusion (Ch. 7's lock ladder) — `SERIALIZABLE` trivially, via "one at a time." WAL mode: a reader's transaction records a position in the WAL (via the wal-index) and reads *the database as of that frame* for its whole life — clean **snapshot isolation for readers** — while the single writer appends beyond it. Since there is never more than one writer, *writer-writer* anomalies (lost update, write skew) are impossible by construction: **SQLite is serializable because concurrency control degenerates to mutual exclusion.** The entire content of PostgreSQL's §6.1 — visibility rules, hint bits, vacuum, HOT, SSI — exists to recover, under high write concurrency, the simplicity SQLite gets by refusing write concurrency. Neither is free; Chapter 7 prices the other side (writers queueing on `SQLITE_BUSY`).

The vestigial cousin: `VACUUM` in SQLite is an *offline rewrite* (rebuild the file compactly — defragmentation, not garbage collection), and `auto_vacuum` merely truncates freed pages; do not let the shared name suggest shared function.

### Exercises 6

1. Two psql sessions: A `BEGIN; UPDATE row;` (no commit), B reads the row under READ COMMITTED and under REPEATABLE READ, A commits, B reads again. Explain all four observations with snapshot contents and visibility rules, then verify the tuple states with `heap_page_items` (find the xmax and the ctid chain).
2. Construct write skew under REPEATABLE READ (the on-call doctors), confirm it commits, then rerun under SERIALIZABLE and exhibit the 40001 abort. Which transaction aborts, and is that choice deterministic?
3. Measure HOT: a table with one index, `fillfactor=90`; update a *non-indexed* column 10⁵ times and watch `pg_stat_user_tables.n_tup_hot_upd` vs. index size; repeat updating the *indexed* column. Explain both curves.
4. Why must vacuum's removable-horizon be the oldest snapshot, not the oldest *write* transaction? Construct the read anomaly that premature removal would cause for a long REPEATABLE READ reader.
5. In SQLite WAL mode, open a long read transaction, commit 10⁴ writes from another connection, and watch the `-wal` file size and `PRAGMA wal_checkpoint(PASSIVE)`'s return values. Explain the pinning, and name the exact PostgreSQL analog from this chapter.
6. State precisely why write skew is impossible in SQLite, and what the application gives up to obtain that (answer in terms of the throughput model of Ch. 7).

---

## Chapter 7 — Locking and Concurrency Control

MVCC removed reader/writer blocking; what remains is writer/writer coordination and physical-structure protection — locks of several distinct species that are routinely confused. Taxonomy first, then the two systems.

### 7.1 The species

1. **Latches / lightweight locks**: protect *in-memory structures* (a buffer page being read while another thread writes it, the buffer mapping table) for microseconds; no deadlock detection, no transaction scope. PostgreSQL: `LWLock`s + per-buffer content locks (visible in `pg_stat_activity.wait_event` under load). SQLite: a connection-level mutex — the library serializes itself.
2. **Row/object locks**: transaction-scoped logical locks with deadlock handling. PostgreSQL stores **row locks in the tuples themselves** — locking a row writes the locker's xid into `t_xmax` plus infomask bits (so an in-memory lock table cannot be exhausted by a million row locks; multiple lockers share a **multixact**) — with four flavors (`KEY SHARE`/`SHARE`/`NO KEY UPDATE`/`UPDATE`) whose main consumer is foreign-key enforcement (`KEY SHARE` taken on referenced rows is why FK checks don't block ordinary updates of non-key columns).
3. **Table-level locks**: the eight-mode matrix (`ACCESS SHARE` … `ACCESS EXCLUSIVE`) whose entire purpose is letting DDL and queries negotiate. The two facts that prevent most production lock incidents: every `SELECT` holds `ACCESS SHARE`, and lock *queues* are fair — so an `ALTER TABLE` waiting behind one long query makes every *subsequent* `SELECT` queue behind the `ALTER`: the classic "one idle transaction froze the whole app" has this exact shape, and `lock_timeout` on DDL is the standard vaccine.

**Deadlocks**: PostgreSQL builds a waits-for graph when a lock wait exceeds `deadlock_timeout` (1s default) and aborts one cycle member (SQLSTATE 40P01) — detection, not prevention, so applications must order their lock acquisitions or be retry-ready. SQLite cannot deadlock between two transactions in the classic sense (one writer), but has its one famous wait: the **upgrade**.

### 7.2 SQLite's lock ladder, and SQLITE_BUSY

Rollback mode is a five-state file-lock ladder: `UNLOCKED → SHARED` (readers, many) `→ RESERVED` (intent to write, one; readers still enter) `→ PENDING` (no *new* readers; draining) `→ EXCLUSIVE` (the commit window). The well-known trap is the **lock upgrade deadlock-in-miniature**: a transaction that reads under `SHARED` and then writes must upgrade to `RESERVED` — if another connection already holds `RESERVED`, you get `SQLITE_BUSY` *immediately and unretriably-in-place* (waiting can't help: the other writer may be waiting for *your* readers to drain — a real deadlock, which SQLite resolves by refusing to wait). The idioms that exist because of this paragraph: `BEGIN IMMEDIATE` (take `RESERVED` up front if you know you'll write — turning the upgrade race into a simple queue), `busy_timeout` (politely spin on the cases where waiting *can* help), and WAL mode (readers never block the writer, so the ladder collapses to "writers queue on one lock"). Even in WAL mode the writer is single: SQLite write throughput is one-writer-at-a-time *by design*, fine for its design point (local data, one app), and the honest disqualifier for shared-server workloads — this, not parsing speed or planner sophistication, is the load-bearing difference.

PostgreSQL's mirror-image trap, for symmetry: nothing stops a hundred writers, but `SELECT … FOR UPDATE` ordering, FK lock interactions (multixact contention on hot referenced rows), and DDL queueing produce the waits — richer machinery, richer failure modes. Each system's locking war stories are exactly the inverse of the other's.

### Exercises 7

1. Reproduce SQLITE_BUSY-on-upgrade with two connections in rollback mode (`BEGIN; SELECT; ... UPDATE` in both). Fix it three ways (`BEGIN IMMEDIATE`, `busy_timeout`, WAL) and explain what each changes mechanically.
2. In PostgreSQL, demonstrate the DDL pile-up: session A holds a long `SELECT`, session B issues `ALTER TABLE ... ADD COLUMN`, session C runs a fast `SELECT`. Show C waits, identify all three lock modes in `pg_locks`, and resolve with `lock_timeout`.
3. Why does PostgreSQL store row locks in tuple headers rather than a lock table? Compute the memory a 10⁷-row `SELECT FOR UPDATE` would need at ~150 bytes/lock-table-entry, and name what InnoDB does instead (escalation) and what that costs.
4. Construct a three-transaction deadlock in PostgreSQL (cyclic `FOR UPDATE` on three rows), watch detection fire, and verify which victim is chosen. Is victim choice load-bearing for your application's retry logic?
5. For a workload of 95% reads / 5% single-row writes from 8 processes, predict throughput behavior on: PG, SQLite rollback, SQLite WAL. State the serialization point in each.

---

## Chapter 8 — Query Processing I: Parsing, Statistics, and Planning

Everything before this chapter executes *given* decisions; the planner *makes* them. It is the layer where databases are most like compilers — and where their errors are silent, manifesting only as latency.

### 8.1 From text to plan

PostgreSQL: parser (grammar → parse tree) → analyzer (catalog lookup: names → OIDs, types resolved) → **rewriter** (views and rules textually expanded into the query tree) → **planner**. SQLite: parse → name resolution → its planner → **bytecode generation** (Ch. 9; SQLite compiles all the way to an executable program — `EXPLAIN` shows the actual opcodes, `EXPLAIN QUERY PLAN` the planner's intent).

The planner's problem is well-posed: among the semantically equivalent plans (scan choices × join orders × join algorithms × …), pick the cheapest under a **cost model** fed by **statistics**. Both parts can be wrong; understanding *how each is wrong* is the skill.

### 8.2 Statistics: what the planner knows

`ANALYZE` (both systems' verb!) samples tables into summaries:

- **PostgreSQL** (`pg_statistic`, viewed via `pg_stats`): per column — null fraction, average width, **n_distinct** (negative = proportional to rowcount), **most-common values** with frequencies, an equi-depth **histogram** of the rest, and physical **correlation** (how well heap order tracks the column — the input that decides whether an index range scan means sequential or random heap I/O). Selectivity arithmetic: `col = const` → MCV hit or `(1 − Σmcv_freqs)/(n_distinct − n_mcvs)`; ranges → histogram interpolation; `AND` → multiply (the **independence assumption**, the cost model's original sin: correlated predicates like `city='SF' AND state='CA'` multiply to near-zero while reality is 1× — `CREATE STATISTICS` exists precisely to declare such dependencies). Estimation errors **compound through joins** roughly multiplicatively — a 10× error at the bottom is a 1000× error three joins up, by which point the chosen plan is pathological; this compounding, not any single bad estimate, is the root of most "the planner went insane" incidents.
- **SQLite** (`sqlite_stat1`, optionally `stat4`): per index — rows, and average rows per distinct prefix of each index-column prefix; `STAT4` adds sampled key values for range estimation. Coarser by design, supplemented by aggressive *structural* heuristics, and — a deliberate philosophy difference — SQLite without `ANALYZE` assumes sensible defaults and leans on the schema (unique indexes ⇒ selectivity 1), accepting worse plans on weird data in exchange for zero-maintenance behavior in its embedded habitat.

### 8.3 Join ordering: the combinatorial core

Join order is where plan spaces explode (Catalan-number growth in relation count). **PostgreSQL** runs the System R playbook: **dynamic programming** over subsets — best plan for every 2-relation subset, then 3, … — with *interesting orders* kept (a costlier subplan that delivers sort order useful later survives); beyond `geqo_threshold` (12 relations) it switches to a **genetic algorithm** (GEQO), trading optimality for planning time — the existence of that switch is itself the lesson about the problem's hardness. **SQLite**'s **Next-Generation Query Planner** runs the same idea, budgeted: a beam-ish search (N best prefixes per level) over join orders with nested-loop execution assumed — because SQLite's executor (Ch. 9) is nested-loop-only by design, the planner's real decision is *order and index choice*, a smaller, embeddable problem.

Cost units deserve demystification: PostgreSQL costs are **abstract** (`seq_page_cost=1.0` is the unit; `random_page_cost=4.0` *encodes the rotational-disk era* — on NVMe/cloud SSD, lowering it toward 1.1 is the single most consequential planner tuning, mechanically shifting the seq-scan/index-scan crossover); `effective_cache_size` doesn't allocate anything — it's a *belief* about OS caching that discounts repeated index page fetches. The planner is a model; tuning is belief-revision.

### Exercises 8

1. With `pg_stats`, hand-compute the planner's row estimate for an equality predicate on a column you've populated with a skewed (Zipfian) distribution — MCV path and non-MCV path — and check against `EXPLAIN`'s estimate.
2. Build the correlated-predicate trap (`city`/`state`), show the 100×-off estimate and the bad plan at three joins, then fix with `CREATE STATISTICS (dependencies)` and re-explain. Where did the error compound?
3. Find the crossover: one table, one selective→unselective range predicate; vary selectivity and `random_page_cost` (4.0 vs 1.1) and chart where PostgreSQL flips seq scan ↔ index scan. Explain the flip with the cost formula and the `correlation` statistic.
4. In SQLite, run a 4-table join with `EXPLAIN QUERY PLAN` before and after `ANALYZE` on data engineered so the default heuristics misorder the join. What changed in `sqlite_stat1`, and in the chosen order?
5. Why does keeping *interesting orders* in the DP table matter? Construct a two-join query where the globally best plan contains a locally suboptimal subplan (merge-join-friendly sort order), and verify PostgreSQL finds it.

---

## Chapter 9 — Query Processing II: Execution

Two genuinely different execution architectures: PostgreSQL interprets a **plan tree of iterators**; SQLite executes **compiled bytecode on a virtual machine**. Same relational algebra, different machine — and the difference is instructive far beyond these two systems (it is the interpreter-vs-compiler axis that modern analytics engines push to its endpoint).

### 9.1 PostgreSQL: the Volcano iterator model

Every plan node implements `next() → tuple`: a parent pulls from children, demand-driven, one row at a time (`Limit 10` naturally stops the pipeline after ten pulls — early termination for free). The node catalog you'll meet in every `EXPLAIN`:

- **Scans**: *Seq Scan* (heap order, ring-buffered); *Index Scan* (b-tree order, heap fetch per hit — random I/O unless `correlation` is high); *Index Only Scan* (no heap fetch for VM-all-visible pages — Ch. 6's dividend, and the reason its `Heap Fetches` number is the health metric of vacuum); *Bitmap Index/Heap Scan* (the hybrid: collect ctids from one *or several* indexes, OR/AND the bitmaps, then visit heap pages in *physical order* — converting random to sequential I/O, degrading gracefully to per-page "lossy" bits under `work_mem` pressure).
- **Joins**: *Nested Loop* (drives an inner index probe; the OLTP join), *Hash Join* (build hash on smaller input, probe with larger; spills to batches — grace hashing — beyond `work_mem`; the analytics join), *Merge Join* (two sorted inputs zipped; wins when order is free from indexes or needed anyway above).
- **Sort/Agg**: in-memory quicksort spilling to external k-way merge (`work_mem` per sort node, not per query — the multiplier that makes global `work_mem` raises dangerous); hash aggregation, spillable since v13; *Incremental Sort* exploiting a prefix already ordered.
- **Parallelism** (v9.6+): Gather + worker backends partition scans/joins/aggregates. **JIT** (v11+, LLVM): for large queries, expression evaluation and tuple deforming compile to native code — attacking the iterator model's known tax (per-row virtual dispatch), the same diagnosis that drove vectorized/compiled analytics engines (DuckDB, ClickHouse); PostgreSQL keeps row-at-a-time semantics and JITs the hot leaves.

Read `EXPLAIN (ANALYZE, BUFFERS)` like a profiler: actual-vs-estimated rows per node (the planner audit — Ch. 8's errors land here), per-node buffers (I/O attribution), loops (a nested-loop inner shows its *per-iteration* rows ×loops). Most real tuning sessions are: find the node where estimates diverge 100×, fix the statistic or the predicate, re-plan.

### 9.2 SQLite: the VDBE

`sqlite3_prepare()` compiles SQL into a program for the **Virtual DataBase Engine** — a register machine whose opcodes (`OpenRead`, `Rewind`, `SeekGE`, `Column`, `ResultRow`, `Next`, `Halt`…) are the *only* thing the execution layer runs. `EXPLAIN` prints it:

```
sqlite> EXPLAIN SELECT name FROM users WHERE id = ?;
addr opcode        p1 p2 p3
0    Init           0  8
1    OpenRead       0  2  0  2          # cursor 0 on root page 2 (users)
2    Variable       1  1               # bind ? into r[1]
3    SeekRowid      0  7  1            # b-tree seek; jump to 7 if absent
4    Column         0  1  2            # r[2] := users.name
5    ResultRow      2  1               # emit
7    Halt
```

A prepared statement *is* this program plus its cursors — re-binding and re-running it skips parse and plan entirely, which is why "prepare once, step many" is the core SQLite performance idiom (and why its per-statement overhead can undercut a client-server round trip by orders of magnitude: the "function call to `fopen()`-land" architecture cashing out). Joins compile to nested loops as nested opcode loops; subqueries/CTEs become **co-routines** (two programs interleaved by `Yield` — the bytecode answer to pipelining); there is no hash join, no parallelism — by design: predictable, tiny, embeddable. The structural insight to carry away: PostgreSQL's executor is a *library of operators* interpreted over a tree; SQLite's is a *compiler target*; both are dominated, in the analytical limit, by engines that vectorize — execution architecture is a spectrum, and you now hold its two classical poles.

### Exercises 9

1. Take one three-table join and produce: PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` and SQLite `EXPLAIN` + `EXPLAIN QUERY PLAN`. Annotate every PostgreSQL node with its SQLite opcode-range counterpart (or its absence).
2. Force all three PostgreSQL join algorithms on the same query (`enable_hashjoin` etc.) and explain each cost from inputs' sizes, order, and indexes. Where does each win *legitimately*?
3. Demonstrate bitmap scan's purpose: a predicate matching 5% of a big table, scattered; compare index scan vs. bitmap scan timing and `BUFFERS`, then check `correlation` and explain.
4. Measure the prepared-statement effect in SQLite: 10⁵ point lookups via re-prepared text vs. one prepared statement re-bound. Attribute the difference to specific lifecycle stages.
5. Why does `LIMIT 10` cost almost nothing under Volcano but a hash aggregate under it still consumes its whole input? Classify operators into pipelining vs. *pipeline breakers* and re-read your plan from (1) marking each.

---

## Chapter 10 — Beyond the B-Tree: Other Indexes, and the LSM Road Not Taken

### 10.1 PostgreSQL's index menagerie

The access-method layer is pluggable, and the built-ins each embody one idea:

- **GIN** (Generalized Inverted Index): maps *elements* → posting lists of rows containing them — the index for "column is a container" (arrays, `jsonb` keys/paths, full-text `tsvector`, trigrams via `pg_trgm` — which is how `LIKE '%substr%'` becomes indexable). Write amplification is its tax (one row touches many keys; the `fastupdate` pending list batches it).
- **GiST**: a generalized balanced tree over any data with a "consistent" predicate — R-tree semantics for geometry/ranges (`&&` overlap), nearest-neighbor (`ORDER BY <->`), exclusion constraints (`EXCLUDE USING gist (room WITH =, during WITH &&)` — the booking-conflict constraint SQL can't otherwise express). **SP-GiST** covers space-partitioned cousins (quadtrees, radix tries).
- **BRIN**: block-range summaries (min/max per ~128 pages) — an index of *kilobytes* on a *terabyte* table, valid exactly when physical order correlates with the column (append-only time series); the degenerate-but-brilliant end of the indexing spectrum.
- **Hash**: equality-only; crash-safe since v10; still rarely beats b-tree in practice — included here mostly as the answer to "why not hash?" (no ranges, no order, marginal wins).
- Cross-cutting: **partial indexes** (`WHERE status='pending'` — index only the hot subset), **expression indexes** (`lower(email)`), **covering** (`INCLUDE` columns for index-only scans). These three, plus b-tree, solve ~95% of schema-design indexing in the wild.

**SQLite**'s set is leaner, same ideas where it counts: partial and expression indexes (yes, both), `WITHOUT ROWID` as the clustering tool (Ch. 3), **R*Tree** as a module (virtual table), **FTS5** as the inverted-index engine (a GIN-equivalent for text, complete with BM25 ranking) — built on the *virtual table* mechanism, SQLite's general extension story (an "index type" is just a table-valued module with its own `xBestIndex` cost hook into the planner: the embeddable answer to PostgreSQL's access-method API).

### 10.2 The LSM road not taken

Neither system uses **log-structured merge trees** — the B-tree's great modern rival (RocksDB, LevelDB, Cassandra, and most KV stores). The design, compressed: writes go to a memtable + log; flushed as immutable sorted runs (SSTables); background **compaction** merges runs down a hierarchy of levels; reads consult memtable + every level (bloom filters pruning most probes). The trade triangle, by amplification class:

| | B-tree (PG/SQLite) | LSM |
| --- | --- | --- |
| **Write amp** | page-sized random writes per small update, + WAL (and FPIs) | sequential always; but compaction *rewrites data repeatedly* — total amp often 10–30× yet sequential and batched |
| **Read amp** | one tree descent (≈1–2 I/Os, cached top) | potentially one probe per level; blooms make point reads ≈1, *range scans* pay a merge across runs |
| **Space amp** | fragmentation + dead versions (vacuum's domain) | obsolete versions awaiting compaction (typ. ~1.1–2×) |

Why these two systems rightly stayed B-tree: their workloads want cheap *reads and range scans with predictable latency* and in-place updates of moderate rate — the B-tree's home turf — while LSM's victory condition is write-dominated ingest on storage that rewards sequential I/O. The deeper unification (the RUM conjecture): **Read, Update/write, and Memory/space overheads cannot all be minimized at once** — every storage structure is a point on that simplex, and "B-tree vs. LSM" is not a fashion question but a coordinates question. (PostgreSQL's pluggable *table* access methods and projects like the OrioleDB engine are attempts to let the same SQL layer choose different coordinates; SQLite once shipped LSM as an experimental `lsm1` extension — the road exists, it's just not the default.)

### Exercises 10

1. For each query, name the best PostgreSQL index and why the alternatives lose: (a) `WHERE tags @> '{urgent}'`; (b) `WHERE created_at > now()-'1 day'` on an append-only 2 TB table; (c) `WHERE lower(email)=?`; (d) `ORDER BY location <-> point(?,?) LIMIT 5`; (e) `WHERE status='pending'` where 0.1% of rows are pending.
2. Implement booking-overlap prevention with a GiST exclusion constraint; demonstrate the constraint rejecting a conflicting insert under concurrency, and explain why a `UNIQUE` index cannot express it.
3. Build FTS5 over 10⁵ documents in SQLite and inspect its shadow tables (`_data`, `_idx`). Identify the inverted-index structure and compare its query path to GIN's (posting lists, merge).
4. Compute total bytes written for 10⁶ random 100-byte row updates: B-tree (8 KiB page write + WAL record + amortized FPI per checkpoint interval) vs. an LSM with leveled compaction (write amp 15×, sequential). Then compute for *point-read* latency at 99th percentile on cold cache. Which workload flips the verdict?
5. Place five systems on the RUM triangle from their docs: PostgreSQL heap+btree, SQLite, RocksDB, ClickHouse's MergeTree, a plain append-only log. Justify each placement in one sentence.

---

## Chapter 11 — Two Walkthroughs: The Life of a Query and the Life of a Write

The synthesis chapter: every preceding layer, traversed once, in each system. Read these slowly — being able to narrate them from memory *is* the learning objective of the guide.

### 11.1 PostgreSQL: `UPDATE accounts SET balance = balance - 100 WHERE id = 42; COMMIT;`

1. **Parse/analyze/rewrite/plan** (Ch. 8): trivial here — index scan on `accounts_pkey`.
2. **Executor** (Ch. 9): Index Scan descends the b-tree (Ch. 3) — root and internal pages almost surely buffer hits (Ch. 4) — finds the ctid, fetches the heap page (pin + content latch), checks **visibility** of the tuple against the snapshot (Ch. 6).
3. **Row lock**: `t_xmax` ← my xid (Ch. 7); if a concurrent committed update is found, EvalPlanQual re-check (Ch. 6).
4. **New version**: construct the updated tuple; HOT if no indexed column changed and the page has room (it's the *indexed* `id` untouched, so yes if space) — else new ctid + index insert(s) (Ch. 6/3).
5. **WAL first** (Ch. 5): the heap-update record (FPI if first touch since checkpoint) written to WAL buffers; page dirtied in shared_buffers, `pd_lsn` advanced. *No data-file write happens now.*
6. **COMMIT**: commit record → WAL flush to disk (group commit may piggyback others); pg_xact bit set; locks released; backend returns. Disk state at this instant: WAL has everything; heap/index files possibly still stale — crash now and redo (Ch. 5) reconstructs.
7. **Afterlife**: checkpointer eventually writes the dirty page; first later reader stamps hint bits; vacuum eventually recycles the dead version and (if non-HOT) the dead index entry — possibly via bottom-up deletion at the next page split (Ch. 3/6).

### 11.2 SQLite (WAL mode): the same update

1. **Prepare** (Ch. 8/9): planner picks the rowid lookup; emits VDBE program (`SeekRowid`, `Column`s, arithmetic, `MakeRecord`, `Insert`, idempotently replacing the cell).
2. **Write lock**: the single writer lock (Ch. 7) — any second writer now gets `SQLITE_BUSY`/queues on `busy_timeout`.
3. **Execute**: pager (Ch. 4) fetches the table b-tree pages (private cache, possibly redirected through the WAL index to a newer frame); the leaf cell is rewritten in the page image in cache (table-is-the-index: no separate heap, Ch. 3); no per-row version anything (Ch. 6).
4. **COMMIT**: changed pages appended as frames to `-wal` with a commit frame; fsync per `synchronous`; wal-index updated so *new* readers see the new position. Old readers continue at their snapshot frame — nobody blocked.
5. **Afterlife**: a later checkpoint copies frames into the main `.db` (blocked from completing past any older reader's mark) and the WAL is eventually reset. Crash at any point: recovery replays the WAL's committed frames — or ignores a torn tail (frame checksums).

Same logical operation; count the differences you can now *name*: versioning granularity, index count touched, who waits, what's on disk at ack, who cleans up, and what each system would have to add to behave like the other. That enumeration is this guide, compressed.

### Exercises 11

1. Narrate both walkthroughs from memory onto paper, then diff against the text. (Seriously — this is the exam.)
2. Instrument 11.1: `pg_waldump` the WAL generated by exactly that update (find the HOT bit or the index insert), `heap_page_items` before/after vacuum, `pg_stat_io` attribution of the eventual page write.
3. Instrument 11.2: with `dbstat` and the `-wal` file size, identify the frames one update produces at `synchronous=FULL` vs. `NORMAL`; then crash (kill -9) before checkpoint and verify recovery.
4. For each step in 11.1, name the failure (crash, lost race, full disk) the step is designed to survive and the chapter that proved it.
5. Re-run 11.1 with the updated column *indexed* and `fillfactor=100`: predict, then verify, every additional physical consequence (index insert, no HOT, later bloat).

---

## Chapter 12 — Where to Go Next

**Courses and books**: Andy Pavlo's [CMU 15-445](https://15445.courses.cs.cmu.edu/) (then 15-721 for in-memory/analytics engines); Petrov's *Database Internals* (Part I maps almost chapter-for-chapter onto this guide; Part II is the Distributed Algorithms guide's territory); Hellerstein/Stonebraker/Hamilton, ["Architecture of a Database System"](https://dsf.berkeley.edu/papers/fntdb07-architecture.pdf) — the 80-page survey that organizes everything; Gray & Reuter, *Transaction Processing*, when you want the deep classical well.

**Source reading, in a productive order**: SQLite first (it's smaller and astonishingly literate): `btree.c`, `pager.c`, `wal.c`, `vdbe.c`, plus the [file-format](https://www.sqlite.org/fileformat2.html) and [atomic-commit](https://www.sqlite.org/atomiccommit.html) docs alongside. Then PostgreSQL by README: `nbtree/README`, `heap/README.HOT`, `transam/README` (WAL and xact machinery), `optimizer/README` — each is a well-written design document hiding in the tree; Suzuki's interdb.jp chapters make the perfect guided tour.

**Things this guide deliberately deferred**, each one good next climb: replication internals (PostgreSQL physical/logical decoding — bridging into the Distributed Algorithms guide's Chapter 8); columnar/vectorized execution (DuckDB as the readable modern codebase); in-memory OLTP and latch-free structures (Bw-tree, ART); query compilation end-to-end (HyPer/Umbra lineage); and io_uring-era async storage engines.

The compressed thesis to leave with: **a database engine is four promises kept simultaneously — find it fast (Ch. 3, 8–10), don't hit the disk twice (Ch. 4), never lose it (Ch. 5), and let everyone work at once without lying to any of them (Ch. 6–7) — and every byte of both codebases is one of those promises, negotiating with the other three.** PostgreSQL and SQLite are what two different sets of priorities among the four look like after decades of honest engineering; learn to read the negotiation and no storage system will be opaque to you again.

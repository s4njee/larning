# Redis Deep Dive

A practical guide to Redis focused on data structures, usage patterns, and operational concerns. Assumes you know what Redis is and have used it as a basic key-value cache. This guide covers the full range of what Redis can do and when each capability is the right tool.

Primary references: [Redis Documentation](https://redis.io/docs/latest/), [Redis Commands](https://redis.io/docs/latest/commands/), [Redis Data Types](https://redis.io/docs/latest/develop/data-types/)

---

## Table of Contents

1. [The Mental Model](#1-the-mental-model)
2. [Strings](#2-strings)
3. [Hashes](#3-hashes)
4. [Lists](#4-lists)
5. [Sets](#5-sets)
6. [Sorted Sets](#6-sorted-sets)
7. [Streams](#7-streams)
8. [HyperLogLog, Bitmaps & Bitfields](#8-hyperloglog-bitmaps--bitfields)
9. [Keys, Expiration & Eviction](#9-keys-expiration--eviction)
10. [Pub/Sub](#10-pubsub)
11. [Transactions & Lua Scripting](#11-transactions--lua-scripting)
12. [Pipelining](#12-pipelining)
13. [Persistence: RDB & AOF](#13-persistence-rdb--aof)
14. [Replication](#14-replication)
15. [Redis Sentinel](#15-redis-sentinel)
16. [Redis Cluster](#16-redis-cluster)
17. [Security](#17-security)
18. [Performance & Memory](#18-performance--memory)
19. [Common Patterns](#19-common-patterns)
20. [Client Libraries & Best Practices](#20-client-libraries--best-practices)
21. [Common Mistakes](#21-common-mistakes)

---

## 1. The Mental Model

### What Redis Is

Redis is an in-memory data structure server. The key insight is **data structure** — Redis is not just a key-value store. It's a remote, shared, persistent dictionary where the values can be strings, lists, sets, sorted sets, hashes, streams, and more. Each data structure has its own set of O(1) or O(log N) operations.

```
┌─────────────────────────────────────────────┐
│                 Redis Server                 │
│                                             │
│  key → value (one of many data structures)  │
│                                             │
│  "user:1001"     → Hash {name, email, ...}  │
│  "session:abc"   → String (JSON blob)       │
│  "queue:emails"  → List [msg1, msg2, ...]   │
│  "online:users"  → Set {uid1, uid2, ...}    │
│  "leaderboard"   → Sorted Set {(score,id)}  │
│  "events:stream" → Stream [(id, fields)]    │
└─────────────────────────────────────────────┘
```

### Why Redis Is Fast

- **In-memory**: all data lives in RAM. No disk seeks, no page faults for hot data.
- **Single-threaded event loop**: no locks, no context switching, no contention. One thread handles all commands sequentially. (I/O and persistence run on background threads.)
- **Efficient data structures**: purpose-built C implementations — skip lists for sorted sets, hash tables, zip lists for small collections.
- **Simple protocol**: RESP (Redis Serialization Protocol) is text-based with minimal overhead.

Typical latency: **sub-millisecond** for most operations on a local network. Throughput: **100K–300K+ operations/second** on modest hardware.

### When to Use Redis

| Use case | Why Redis fits |
|---|---|
| Caching | Sub-ms reads, TTL-based expiration, eviction policies |
| Session storage | Fast reads, automatic expiry, atomic operations |
| Rate limiting | Atomic counters with expiry |
| Queues / job processing | List-based queues with blocking pops |
| Real-time leaderboards | Sorted sets with O(log N) insert and rank lookup |
| Pub/sub messaging | Built-in publish/subscribe channels |
| Distributed locks | Atomic SET with NX and EX flags |
| Real-time analytics | HyperLogLog for cardinality, bitmaps for daily activity |
| Event streaming | Streams with consumer groups |
| Geospatial indexing | Geo commands for radius queries |

### When NOT to Use Redis

- **Primary data store for data you can't lose** — Redis can persist to disk, but it's not a database. Use Postgres for your source of truth and Redis as a derived cache.
- **Data larger than RAM** — Redis stores everything in memory. If your dataset doesn't fit in RAM, Redis isn't the right choice (or use Redis on Flash / tiered storage).
- **Complex queries** — no JOINs, no secondary indexes (without modules), no SQL. If you need ad-hoc queries, use a database.
- **Large values** — storing 100MB blobs in Redis works but wastes memory and blocks the event loop during I/O. Use object storage for large files.

---

## 2. Strings

Reference: [Strings](https://redis.io/docs/latest/develop/data-types/strings/)

The simplest data type. A Redis string can hold text, serialized JSON, binary data, or an integer/float (Redis auto-detects for atomic arithmetic).

### Basic Operations

```redis
SET user:1001:name "Alice"
GET user:1001:name                    -- "Alice"

-- set with expiration
SET session:abc "data" EX 3600        -- expires in 1 hour
SET session:abc "data" PX 5000        -- expires in 5 seconds

-- set only if key doesn't exist (used for distributed locks)
SET lock:order:123 "worker-1" NX EX 30

-- set only if key already exists
SET user:1001:name "Bob" XX

-- get and set atomically
GETSET counter "0"                    -- returns old value, sets new

-- set multiple keys
MSET user:1001:name "Alice" user:1001:email "alice@example.com"
MGET user:1001:name user:1001:email
```

### Atomic Counters

```redis
SET page:views 0
INCR page:views                       -- 1
INCR page:views                       -- 2
INCRBY page:views 10                  -- 12
DECR page:views                       -- 11
DECRBY page:views 5                   -- 6
INCRBYFLOAT price 2.50                -- works with floats
```

These operations are atomic — no race conditions even under concurrent access. This makes Redis ideal for counters, rate limiters, and sequence generators.

### Practical: Caching

```python
import json
import redis

r = redis.Redis()

def get_user(user_id):
    cache_key = f"user:{user_id}"

    # check cache
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # cache miss — fetch from database
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)

    # populate cache with 5-minute TTL
    r.setex(cache_key, 300, json.dumps(user))

    return user
```

### Practical: Distributed Lock

```python
import uuid
import time

def acquire_lock(r, lock_name, timeout=10):
    token = str(uuid.uuid4())
    acquired = r.set(f"lock:{lock_name}", token, nx=True, ex=timeout)
    return token if acquired else None

def release_lock(r, lock_name, token):
    # atomic check-and-delete using Lua to prevent releasing someone else's lock
    script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    r.eval(script, 1, f"lock:{lock_name}", token)

# usage
token = acquire_lock(r, "process-order-123")
if token:
    try:
        process_order(123)
    finally:
        release_lock(r, "process-order-123", token)
```

For production distributed locks, use [Redlock](https://redis.io/docs/latest/develop/use/patterns/distributed-locks/) across multiple Redis instances or a coordination service like etcd/ZooKeeper.

---

## 3. Hashes

Reference: [Hashes](https://redis.io/docs/latest/develop/data-types/hashes/)

A hash is a map of field-value pairs — like a nested dictionary. Ideal for representing objects.

### Basic Operations

```redis
-- set fields
HSET user:1001 name "Alice" email "alice@example.com" age 30

-- get a single field
HGET user:1001 name                   -- "Alice"

-- get multiple fields
HMGET user:1001 name email            -- ["Alice", "alice@example.com"]

-- get all fields and values
HGETALL user:1001                     -- {name: Alice, email: alice@example.com, age: 30}

-- check field existence
HEXISTS user:1001 phone               -- 0 (false)

-- delete a field
HDEL user:1001 age

-- increment a numeric field
HINCRBY user:1001 login_count 1

-- get all field names
HKEYS user:1001

-- get all values
HVALS user:1001

-- count fields
HLEN user:1001
```

### Hash vs Multiple Strings

```redis
-- option A: separate keys
SET user:1001:name "Alice"
SET user:1001:email "alice@example.com"
SET user:1001:age "30"

-- option B: one hash
HSET user:1001 name "Alice" email "alice@example.com" age 30
```

Hashes are better because:
- **Memory efficiency**: small hashes (< ~100 fields) use a compact encoding (listpack) that's significantly more memory-efficient than separate keys
- **Atomic operations**: `HGETALL` fetches all fields in one roundtrip
- **Logical grouping**: one key represents one entity
- **TTL**: one expiration for the whole object instead of managing TTLs per field

Use separate keys when fields need independent TTLs or when individual fields are very large.

### Practical: Session Storage

```python
def create_session(r, session_id, user_data):
    key = f"session:{session_id}"
    r.hset(key, mapping={
        "user_id": user_data["id"],
        "username": user_data["username"],
        "role": user_data["role"],
        "created_at": int(time.time()),
    })
    r.expire(key, 86400)  # 24 hours

def get_session(r, session_id):
    data = r.hgetall(f"session:{session_id}")
    if not data:
        return None
    return {k.decode(): v.decode() for k, v in data.items()}

def update_session_field(r, session_id, field, value):
    key = f"session:{session_id}"
    if r.exists(key):
        r.hset(key, field, value)
```

### Practical: Feature Flags

```python
def init_feature_flags(r):
    r.hset("features", mapping={
        "dark_mode": "true",
        "new_checkout": "false",
        "beta_api": "true",
    })

def is_feature_enabled(r, feature_name):
    value = r.hget("features", feature_name)
    return value == b"true" if value else False

def toggle_feature(r, feature_name, enabled):
    r.hset("features", feature_name, "true" if enabled else "false")
```

---

## 4. Lists

Reference: [Lists](https://redis.io/docs/latest/develop/data-types/lists/)

Redis lists are linked lists of strings. O(1) push/pop at both ends, O(N) access by index. Use them for queues, stacks, timelines, and recent-items lists.

### Basic Operations

```redis
-- push to the left (head) or right (tail)
LPUSH queue:emails "msg1"
RPUSH queue:emails "msg2" "msg3"
-- queue is now: [msg1, msg2, msg3]

-- pop from left or right
LPOP queue:emails                     -- "msg1"
RPOP queue:emails                     -- "msg3"

-- peek without removing
LINDEX queue:emails 0                 -- first element
LRANGE queue:emails 0 -1             -- all elements
LRANGE queue:emails 0 9              -- first 10 elements

-- length
LLEN queue:emails

-- trim to a fixed size (keep most recent N)
LTRIM recent:posts 0 99              -- keep only first 100 elements

-- blocking pop (waits for an element if list is empty)
BLPOP queue:emails 30                -- wait up to 30 seconds
BRPOP queue:emails 0                 -- wait forever

-- move element between lists atomically
LMOVE source destination LEFT RIGHT
BLMOVE source destination LEFT RIGHT 30  -- blocking version
```

### Practical: Simple Job Queue

```python
# producer
def enqueue_job(r, queue_name, job_data):
    r.rpush(f"queue:{queue_name}", json.dumps(job_data))

# consumer
def process_jobs(r, queue_name):
    while True:
        # BLMOVE atomically: pop from queue, push to processing list
        # if worker crashes, job is still in the processing list for recovery
        job = r.blmove(
            f"queue:{queue_name}",
            f"processing:{queue_name}",
            timeout=30,
            wherefrom="LEFT",
            whereto="RIGHT",
        )
        if job is None:
            continue

        try:
            data = json.loads(job)
            handle_job(data)
            # success — remove from processing list
            r.lrem(f"processing:{queue_name}", 1, job)
        except Exception:
            # failure — move back to queue for retry
            r.lmove(
                f"processing:{queue_name}",
                f"queue:{queue_name}",
                "RIGHT", "LEFT"
            )
```

`BLMOVE` (or the older `BRPOPLPUSH`) is the key primitive — it atomically moves an item from one list to another. If the worker crashes between popping and completing, the job is still in the processing list and can be recovered.

For production job queues, consider purpose-built tools (Celery, Sidekiq, BullMQ) that add retries, dead-letter queues, priorities, and monitoring on top of Redis lists.

### Practical: Activity Feed / Recent Items

```python
def add_activity(r, user_id, activity):
    key = f"feed:{user_id}"
    r.lpush(key, json.dumps(activity))
    r.ltrim(key, 0, 99)  # keep only the 100 most recent

def get_recent_activity(r, user_id, count=20):
    items = r.lrange(f"feed:{user_id}", 0, count - 1)
    return [json.loads(item) for item in items]
```

`LPUSH` + `LTRIM` is the standard pattern for bounded, most-recent-first lists.

---

## 5. Sets

Reference: [Sets](https://redis.io/docs/latest/develop/data-types/sets/)

Unordered collections of unique strings. O(1) add, remove, and membership check. Supports set operations (union, intersection, difference).

### Basic Operations

```redis
-- add members
SADD online:users "user:1001" "user:1002" "user:1003"

-- check membership
SISMEMBER online:users "user:1001"    -- 1 (true)

-- remove a member
SREM online:users "user:1002"

-- count members
SCARD online:users                    -- 2

-- get all members
SMEMBERS online:users                 -- {"user:1001", "user:1003"}

-- get a random member
SRANDMEMBER online:users
SRANDMEMBER online:users 3            -- 3 random members

-- pop a random member (remove and return)
SPOP online:users

-- set operations
SADD group:a "alice" "bob" "carol"
SADD group:b "bob" "carol" "dave"

SINTER group:a group:b               -- {"bob", "carol"}  (intersection)
SUNION group:a group:b               -- {"alice", "bob", "carol", "dave"}
SDIFF group:a group:b                -- {"alice"}  (in a but not b)

-- store results in a new key
SINTERSTORE group:both group:a group:b
```

### Practical: Tag System

```python
def tag_article(r, article_id, tags):
    for tag in tags:
        r.sadd(f"tag:{tag}", article_id)
        r.sadd(f"article:{article_id}:tags", tag)

def get_articles_by_tag(r, tag):
    return r.smembers(f"tag:{tag}")

def get_articles_by_all_tags(r, tags):
    # articles that have ALL the specified tags
    keys = [f"tag:{tag}" for tag in tags]
    return r.sinter(*keys)

def get_articles_by_any_tag(r, tags):
    # articles that have ANY of the specified tags
    keys = [f"tag:{tag}" for tag in tags]
    return r.sunion(*keys)

def get_tags_for_article(r, article_id):
    return r.smembers(f"article:{article_id}:tags")
```

### Practical: Tracking Unique Visitors

```python
def track_visit(r, page, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    r.sadd(f"visitors:{page}:{today}", user_id)
    r.expire(f"visitors:{page}:{today}", 86400 * 7)  # keep for 7 days

def unique_visitors_today(r, page):
    today = datetime.now().strftime("%Y-%m-%d")
    return r.scard(f"visitors:{page}:{today}")

def visitors_both_pages(r, page_a, page_b):
    today = datetime.now().strftime("%Y-%m-%d")
    return r.sinter(f"visitors:{page_a}:{today}", f"visitors:{page_b}:{today}")
```

For very high cardinalities (millions of unique visitors), switch to HyperLogLog (Section 8) to save memory at the cost of approximate counts.

---

## 6. Sorted Sets

Reference: [Sorted Sets](https://redis.io/docs/latest/develop/data-types/sorted-sets/)

Sorted sets are the most versatile Redis data structure. Each member has a floating-point score, and members are ordered by score. O(log N) insert, remove, and rank lookup. O(log N + M) range queries.

### Basic Operations

```redis
-- add members with scores
ZADD leaderboard 1500 "alice" 1200 "bob" 1800 "carol"

-- get score of a member
ZSCORE leaderboard "alice"            -- 1500

-- increment a score
ZINCRBY leaderboard 50 "alice"        -- 1550

-- rank (0-based, lowest score first)
ZRANK leaderboard "bob"               -- 0 (lowest)
ZREVRANK leaderboard "carol"          -- 0 (highest)

-- range by rank (ascending)
ZRANGE leaderboard 0 -1 WITHSCORES   -- all members, lowest first
ZREVRANGE leaderboard 0 9 WITHSCORES -- top 10, highest first

-- range by score
ZRANGEBYSCORE leaderboard 1000 1500  -- members with scores 1000-1500
ZRANGEBYSCORE leaderboard "-inf" "+inf"  -- all members by score

-- count members in a score range
ZCOUNT leaderboard 1000 1500         -- 1

-- remove members
ZREM leaderboard "bob"

-- remove by rank (keep only top N)
ZREMRANGEBYRANK leaderboard 0 -11    -- remove all but top 10

-- remove by score
ZREMRANGEBYSCORE leaderboard "-inf" 1000

-- cardinality
ZCARD leaderboard

-- set operations
ZUNIONSTORE dest 2 set1 set2 WEIGHTS 1 2  -- weighted union
ZINTERSTORE dest 2 set1 set2               -- intersection
```

### Practical: Leaderboard

```python
def update_score(r, game_id, user_id, score):
    r.zadd(f"leaderboard:{game_id}", {user_id: score})

def add_points(r, game_id, user_id, points):
    r.zincrby(f"leaderboard:{game_id}", points, user_id)

def get_top_players(r, game_id, count=10):
    return r.zrevrange(f"leaderboard:{game_id}", 0, count - 1, withscores=True)

def get_player_rank(r, game_id, user_id):
    rank = r.zrevrank(f"leaderboard:{game_id}", user_id)
    return rank + 1 if rank is not None else None  # 1-based rank

def get_players_around(r, game_id, user_id, window=5):
    rank = r.zrevrank(f"leaderboard:{game_id}", user_id)
    if rank is None:
        return []
    start = max(0, rank - window)
    end = rank + window
    return r.zrevrange(f"leaderboard:{game_id}", start, end, withscores=True)
```

### Practical: Rate Limiter (Sliding Window)

```python
def is_rate_limited(r, user_id, action, max_requests, window_seconds):
    key = f"ratelimit:{action}:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, "-inf", window_start)  # remove old entries
    pipe.zadd(key, {f"{now}:{uuid4()}": now})          # add current request
    pipe.zcard(key)                                     # count requests in window
    pipe.expire(key, window_seconds)                    # auto-cleanup
    results = pipe.execute()

    request_count = results[2]
    return request_count > max_requests

# usage: max 100 requests per 60 seconds
if is_rate_limited(r, "user:1001", "api", max_requests=100, window_seconds=60):
    return HttpResponse(status=429)
```

This is a sliding window rate limiter — each request timestamp is stored as a sorted set member with the timestamp as the score. Old entries are pruned, and the count of remaining entries is the request count within the window.

### Practical: Priority Queue

```python
def enqueue_priority(r, queue_name, job_data, priority):
    # lower score = higher priority (processed first)
    job_id = str(uuid4())
    r.zadd(f"pqueue:{queue_name}", {json.dumps({"id": job_id, **job_data}): priority})

def dequeue_highest_priority(r, queue_name):
    # atomically pop the lowest-scored (highest priority) member
    result = r.zpopmin(f"pqueue:{queue_name}")
    if result:
        member, score = result[0]
        return json.loads(member)
    return None
```

### Practical: Time-Series Data (Simple)

```python
def record_metric(r, metric_name, value):
    timestamp = time.time()
    r.zadd(f"metric:{metric_name}", {f"{timestamp}:{value}": timestamp})

def get_metrics_in_range(r, metric_name, start_time, end_time):
    entries = r.zrangebyscore(
        f"metric:{metric_name}", start_time, end_time, withscores=True
    )
    return [(float(m.decode().split(":")[1]), score) for m, score in entries]

def trim_old_metrics(r, metric_name, max_age_seconds):
    cutoff = time.time() - max_age_seconds
    r.zremrangebyscore(f"metric:{metric_name}", "-inf", cutoff)
```

For serious time-series workloads, use Redis TimeSeries (a module) or a dedicated time-series database.

---

## 7. Streams

Reference: [Streams](https://redis.io/docs/latest/develop/data-types/streams/)

Streams are an append-only log data structure with consumer groups. Think of them as a Redis-native, lighter-weight alternative to Kafka for event streaming within a single Redis deployment.

### Basic Operations

```redis
-- add an entry (auto-generated ID)
XADD events * user "alice" action "login" ip "1.2.3.4"
-- returns "1700000000000-0" (millisecond timestamp + sequence number)

-- add with a specific ID
XADD events 1700000000000-0 user "alice" action "login"

-- read entries
XRANGE events - +                     -- all entries (- = start, + = end)
XRANGE events - + COUNT 10           -- first 10 entries
XRANGE events 1700000000000 +        -- entries after a timestamp

-- read new entries (blocking, like tail -f)
XREAD COUNT 10 BLOCK 5000 STREAMS events $
-- $ means "only new entries from now on"
-- BLOCK 5000 = wait up to 5 seconds

-- length
XLEN events

-- trim to a maximum length
XTRIM events MAXLEN ~ 10000          -- approximately 10K entries (~ allows Redis to optimize)

-- delete specific entries
XDEL events 1700000000000-0
```

### Consumer Groups

Consumer groups allow multiple consumers to share the work of processing a stream, where each message is delivered to exactly one consumer in the group:

```redis
-- create a consumer group
XGROUP CREATE events mygroup $ MKSTREAM
-- $ = start reading from new messages only
-- 0 = start reading from the beginning

-- read as a consumer in a group
XREADGROUP GROUP mygroup consumer-1 COUNT 10 BLOCK 5000 STREAMS events >
-- > means "give me undelivered messages"

-- acknowledge processing
XACK events mygroup 1700000000000-0

-- see pending (unacknowledged) messages
XPENDING events mygroup
XPENDING events mygroup - + 10       -- details of up to 10 pending entries

-- claim messages from a dead consumer (been pending > 60 seconds)
XAUTOCLAIM events mygroup consumer-2 60000 0
```

### Practical: Event Processing Pipeline

```python
def publish_event(r, stream, event_type, data):
    entry = {"type": event_type, "data": json.dumps(data), "timestamp": str(time.time())}
    r.xadd(stream, entry, maxlen=100000)

def consume_events(r, stream, group, consumer_name):
    # ensure the consumer group exists
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError:
        pass  # group already exists

    while True:
        # read new messages
        entries = r.xreadgroup(group, consumer_name, {stream: ">"}, count=10, block=5000)
        if not entries:
            continue

        for stream_name, messages in entries:
            for msg_id, fields in messages:
                try:
                    event_type = fields[b"type"].decode()
                    data = json.loads(fields[b"data"])
                    handle_event(event_type, data)
                    r.xack(stream, group, msg_id)  # acknowledge
                except Exception as e:
                    log.error(f"Failed to process {msg_id}: {e}")
                    # message stays pending, will be retried or claimed

# run multiple consumers
# consumer-1, consumer-2, consumer-3 all in the same group
# each message is delivered to exactly one consumer
```

### Streams vs Pub/Sub vs Lists

| | Streams | Pub/Sub | Lists |
|---|---|---|---|
| Persistence | Yes (on disk) | No (fire-and-forget) | Yes |
| Consumer groups | Yes | No | Manual |
| Message replay | Yes (read from any point) | No (miss it and it's gone) | No (once popped, gone) |
| Acknowledgment | Yes (XACK) | No | Manual |
| Backpressure | BLOCK + COUNT | No | BLPOP |
| Use case | Event sourcing, reliable messaging | Notifications, real-time broadcasts | Job queues |

Use streams when you need reliable, replayable messaging. Use pub/sub for ephemeral notifications. Use lists for simple queues.

---

## 8. HyperLogLog, Bitmaps & Bitfields

### HyperLogLog

Reference: [HyperLogLog](https://redis.io/docs/latest/develop/data-types/probabilistic/hyperloglogs/)

HyperLogLog counts unique elements approximately with a fixed 12KB of memory regardless of cardinality. Standard error is 0.81%.

```redis
-- add elements
PFADD visitors:2024-01-15 "user:1001" "user:1002" "user:1003"
PFADD visitors:2024-01-15 "user:1001"   -- duplicate, doesn't increase count

-- get approximate count
PFCOUNT visitors:2024-01-15              -- ~3

-- merge multiple HyperLogLogs
PFMERGE visitors:week visitors:2024-01-15 visitors:2024-01-16 visitors:2024-01-17
PFCOUNT visitors:week                    -- unique visitors across all three days
```

**When to use**: counting unique items where exact counts aren't required and memory matters — unique visitors, unique searches, unique IPs. At 10 million unique users, a set costs ~400MB; a HyperLogLog costs 12KB.

### Bitmaps

Reference: [Bitmaps](https://redis.io/docs/latest/develop/data-types/probabilistic/bitmaps/)

Bitmaps are strings treated as arrays of bits. O(1) set/get per bit, O(N) for counting and bitwise operations.

```redis
-- set bit (user 1001 was active today)
SETBIT active:2024-01-15 1001 1

-- get bit
GETBIT active:2024-01-15 1001          -- 1

-- count set bits
BITCOUNT active:2024-01-15             -- number of active users

-- bitwise operations
BITOP AND active:both active:2024-01-15 active:2024-01-16
-- users active on BOTH days

BITOP OR active:either active:2024-01-15 active:2024-01-16
-- users active on EITHER day
```

**Practical: Daily Active Users**

```python
def mark_active(r, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    r.setbit(f"active:{today}", user_id, 1)

def count_dau(r, date_str):
    return r.bitcount(f"active:{date_str}")

def count_users_active_all_days(r, dates):
    keys = [f"active:{d}" for d in dates]
    dest = f"active:intersection:{':'.join(dates)}"
    r.bitop("AND", dest, *keys)
    count = r.bitcount(dest)
    r.delete(dest)
    return count

def user_was_active(r, user_id, date_str):
    return r.getbit(f"active:{date_str}", user_id)
```

One bitmap for 10 million users costs ~1.2MB. A set of user IDs would cost ~80MB.

**Trade-off**: bitmaps use user IDs as offsets, so they work best with sequential integer IDs. Sparse ID spaces (UUIDs) waste memory.

### Bitfields

Reference: [Bitfields](https://redis.io/docs/latest/develop/data-types/probabilistic/bitfields/)

Bitfields let you set, get, and increment integer values at arbitrary bit offsets within a string. Useful for compact storage of small integers.

```redis
-- store multiple small counters in a single key
-- user 0: 4-bit counter at offset 0
-- user 1: 4-bit counter at offset 4
-- user 2: 4-bit counter at offset 8

BITFIELD compact_counters SET u4 0 5       -- set user 0's counter to 5
BITFIELD compact_counters SET u4 4 12      -- set user 1's counter to 12
BITFIELD compact_counters INCRBY u4 0 1    -- increment user 0's counter
BITFIELD compact_counters GET u4 0         -- get user 0's counter: 6
```

---

## 9. Keys, Expiration & Eviction

### Key Naming Conventions

Use colons as separators and establish a consistent hierarchy:

```
object-type:id:field
─────────────────────
user:1001              hash of user data
user:1001:sessions     set of active sessions
session:abc123         hash of session data
queue:emails           list for email job queue
cache:api:/users/42    cached API response
lock:process:order:99  distributed lock
ratelimit:api:user:42  rate limiter
```

Consistent naming enables pattern-based operations (`KEYS user:*`, `SCAN 0 MATCH user:*`) and makes the keyspace self-documenting.

### Key Operations

```redis
-- check existence
EXISTS user:1001                       -- 1 if exists

-- delete
DEL user:1001                          -- synchronous, blocks
UNLINK user:1001                       -- asynchronous, non-blocking (prefer for large values)

-- type of value stored at key
TYPE user:1001                         -- "hash", "string", "list", etc.

-- rename
RENAME old_key new_key
RENAMENX old_key new_key              -- only if new_key doesn't exist

-- find keys by pattern (NEVER use in production — blocks the server)
KEYS user:*

-- iterative, non-blocking alternative to KEYS
SCAN 0 MATCH user:* COUNT 100        -- returns cursor + batch of keys
```

### Expiration

```redis
-- set TTL at creation
SET session:abc "data" EX 3600        -- 3600 seconds
SET session:abc "data" PX 60000       -- 60000 milliseconds

-- set TTL on existing key
EXPIRE key 300                         -- 300 seconds from now
PEXPIRE key 5000                       -- 5000 milliseconds from now
EXPIREAT key 1700000000               -- at specific Unix timestamp
PEXPIREAT key 1700000000000           -- at specific Unix timestamp (ms)

-- check remaining TTL
TTL key                                -- seconds, -1 = no expiry, -2 = doesn't exist
PTTL key                               -- milliseconds

-- remove expiration (make persistent)
PERSIST key
```

**How expiration works internally:**

Redis uses two strategies:
1. **Lazy expiration**: when a key is accessed, Redis checks if it's expired and deletes it
2. **Active expiration**: 10 times per second, Redis samples 20 random keys with TTLs and deletes expired ones. If >25% were expired, repeat immediately.

This means expired keys may consume memory for a short time after expiration. Under memory pressure, eviction policies handle this.

### Eviction Policies

When Redis hits its `maxmemory` limit, it needs to decide what to remove:

| Policy | Behavior |
|---|---|
| `noeviction` | Return errors on writes. Reads still work. Default — dangerous if you don't monitor. |
| `allkeys-lru` | Evict least recently used keys. **Best default for caches.** |
| `allkeys-lfu` | Evict least frequently used keys. Better than LRU when some keys are consistently hot. |
| `volatile-lru` | LRU but only among keys with TTLs set. |
| `volatile-lfu` | LFU but only among keys with TTLs set. |
| `allkeys-random` | Evict random keys. |
| `volatile-random` | Evict random keys with TTLs. |
| `volatile-ttl` | Evict keys with the shortest remaining TTL. |

```redis
CONFIG SET maxmemory 2gb
CONFIG SET maxmemory-policy allkeys-lfu
```

**Recommendation**: `allkeys-lfu` for most cache workloads. `noeviction` for data you can't afford to lose (but then you must monitor memory and scale before hitting the limit).

---

## 10. Pub/Sub

Reference: [Pub/Sub](https://redis.io/docs/latest/develop/interact/pubsub/)

Pub/Sub is fire-and-forget messaging. Publishers send messages to channels. Subscribers receive messages from channels they're subscribed to. Messages are not persisted — if no subscriber is listening, the message is lost.

### Basic Operations

```redis
-- subscriber (blocks and waits for messages)
SUBSCRIBE notifications
SUBSCRIBE channel1 channel2

-- pattern subscribe (match channel names)
PSUBSCRIBE news.*                      -- matches news.sports, news.tech, etc.

-- publisher (from a different connection)
PUBLISH notifications "New order received"
PUBLISH news.sports "Team wins championship"

-- unsubscribe
UNSUBSCRIBE notifications
PUNSUBSCRIBE news.*
```

### Practical: Real-Time Notifications

```python
# publisher (in your application code)
def notify_user(r, user_id, message):
    channel = f"notifications:{user_id}"
    r.publish(channel, json.dumps({
        "type": "notification",
        "message": message,
        "timestamp": time.time()
    }))

# subscriber (in a WebSocket handler or background worker)
def listen_for_notifications(r, user_id):
    pubsub = r.pubsub()
    pubsub.subscribe(f"notifications:{user_id}")

    for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            yield data  # send to WebSocket client
```

### Practical: Cache Invalidation

```python
# when data changes, broadcast invalidation
def update_user(r, user_id, data):
    db.update_user(user_id, data)
    r.delete(f"cache:user:{user_id}")
    r.publish("cache:invalidation", json.dumps({
        "type": "user",
        "id": user_id
    }))

# each application server subscribes and clears its local cache
def listen_invalidations(r, local_cache):
    pubsub = r.pubsub()
    pubsub.subscribe("cache:invalidation")

    for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            local_cache.delete(f"{data['type']}:{data['id']}")
```

### Limitations

- **No persistence**: if a subscriber is disconnected when a message is published, it misses that message permanently
- **No acknowledgment**: the publisher doesn't know if anyone received the message
- **No consumer groups**: every subscriber gets every message (no work distribution)
- **All-or-nothing delivery**: no selective replay or offset tracking

For reliable messaging, use Streams (Section 7) or an external message broker.

---

## 11. Transactions & Lua Scripting

### Transactions (MULTI/EXEC)

Reference: [Transactions](https://redis.io/docs/latest/develop/interact/transactions/)

`MULTI/EXEC` groups commands into an atomic batch — all commands execute sequentially without interleaving from other clients:

```redis
MULTI
SET user:1001:balance 100
INCR user:1001:login_count
EXPIRE user:1001:balance 3600
EXEC
-- all three commands execute atomically
```

**Important**: Redis transactions are **not** rollback transactions. If one command fails, the others still execute. There is no ROLLBACK. `MULTI/EXEC` guarantees isolation (no interleaving), not atomicity in the database sense.

### Optimistic Locking with WATCH

`WATCH` enables check-and-set (CAS) behavior:

```redis
WATCH user:1001:balance
balance = GET user:1001:balance        -- 100

MULTI
SET user:1001:balance (balance - 25)
EXEC
-- if another client modified user:1001:balance after WATCH,
-- EXEC returns nil and the transaction is aborted
```

```python
def transfer(r, from_user, to_user, amount):
    with r.pipeline() as pipe:
        while True:
            try:
                from_key = f"user:{from_user}:balance"
                to_key = f"user:{to_user}:balance"

                pipe.watch(from_key, to_key)
                from_balance = int(pipe.get(from_key) or 0)
                to_balance = int(pipe.get(to_key) or 0)

                if from_balance < amount:
                    pipe.unwatch()
                    raise ValueError("Insufficient funds")

                pipe.multi()
                pipe.set(from_key, from_balance - amount)
                pipe.set(to_key, to_balance + amount)
                pipe.execute()
                break  # success
            except redis.WatchError:
                continue  # retry — someone modified the watched keys
```

### Lua Scripting

Reference: [Scripting with Lua](https://redis.io/docs/latest/develop/interact/programmability/eval-intro/)

Lua scripts execute atomically on the server — they're the most powerful way to implement complex atomic operations:

```python
# atomic compare-and-delete (for releasing locks)
release_lock_script = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

# atomic rate limiter
rate_limit_script = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call("INCR", key)
if current == 1 then
    redis.call("EXPIRE", key, window)
end

if current > limit then
    return 0  -- rate limited
else
    return 1  -- allowed
end
"""

# register script (returns a SHA that can be called without resending the script)
release_lock = r.register_script(release_lock_script)
rate_limit = r.register_script(rate_limit_script)

# call
release_lock(keys=["lock:order:123"], args=["my-token"])
allowed = rate_limit(keys=["ratelimit:api:user:42"], args=[100, 60])
```

**Lua vs MULTI/EXEC:**

| | MULTI/EXEC | Lua |
|---|---|---|
| Read-then-write patterns | Needs WATCH + retry loop | Just read and write in the script |
| Conditional logic | Not possible | Full programming language |
| Performance | Multiple roundtrips (or pipeline) | Single roundtrip |
| Complexity | Simple | Can be complex to debug |
| Atomicity | Isolation only | True atomicity |

Use Lua when you need to read a value, make a decision, then write — MULTI/EXEC can't do this without WATCH.

**Caution**: long-running Lua scripts block the entire Redis server. Keep scripts short and fast. Redis has a default timeout of 5 seconds (`lua-time-limit`), after which clients can interrupt.

---

## 12. Pipelining

Reference: [Pipelining](https://redis.io/docs/latest/develop/use/pipelining/)

Pipelining sends multiple commands in one batch without waiting for individual responses. This eliminates per-command network roundtrip latency.

```python
# without pipelining: 100 roundtrips
for i in range(100):
    r.set(f"key:{i}", f"value:{i}")  # each call waits for response

# with pipelining: 1 roundtrip
pipe = r.pipeline(transaction=False)
for i in range(100):
    pipe.set(f"key:{i}", f"value:{i}")
results = pipe.execute()  # all 100 commands sent at once, all 100 responses received at once
```

### Performance Impact

On a typical network (0.5ms roundtrip):
- 100 commands without pipelining: ~50ms
- 100 commands with pipelining: ~1ms + server processing time

Pipelining doesn't change the server-side execution time. It eliminates network latency by batching.

### Pipeline + Transaction

```python
# pipeline with MULTI/EXEC wrapping
pipe = r.pipeline()  # transaction=True is the default
pipe.set("key1", "value1")
pipe.set("key2", "value2")
pipe.incr("counter")
results = pipe.execute()
# commands are sent in one batch AND executed atomically
```

### Practical Guidelines

- **Batch size**: 100–1000 commands per pipeline is typical. Don't pipeline 1 million commands — the response buffer will consume too much memory.
- **Don't pipeline when you need intermediate results**: if command B depends on command A's response, you can't pipeline them.
- **Always pipeline in loops**: if you're calling Redis in a `for` loop, you're probably missing a pipelining opportunity.

---

## 13. Persistence: RDB & AOF

Reference: [Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)

Redis is in-memory, but it can persist data to disk for durability. Two mechanisms, often used together:

### RDB (Snapshotting)

Point-in-time snapshots of the entire dataset, written as a compact binary file:

```redis
-- manual snapshot
BGSAVE                                 -- fork and save in background
SAVE                                   -- blocks until complete (don't use in production)

-- automatic snapshots (in redis.conf)
save 900 1                             -- snapshot if ≥1 key changed in 900 seconds
save 300 10                            -- snapshot if ≥10 keys changed in 300 seconds
save 60 10000                          -- snapshot if ≥10000 keys changed in 60 seconds
```

| Pros | Cons |
|---|---|
| Compact binary format, fast to load | Data loss between snapshots (could be minutes) |
| Perfect for backups | `fork()` can be slow on large datasets (copies page tables) |
| Fast restart from RDB | Not suitable for minimal data loss requirements |

### AOF (Append-Only File)

Logs every write operation. Replayed on restart to reconstruct the dataset:

```redis
-- enable AOF
CONFIG SET appendonly yes

-- fsync policies
appendfsync always                     -- fsync after every write (safest, slowest)
appendfsync everysec                   -- fsync every second (good compromise)
appendfsync no                         -- let the OS decide (fastest, least safe)
```

| Pros | Cons |
|---|---|
| Minimal data loss (at most 1 second with `everysec`) | Larger file than RDB |
| Append-only, so it survives partial writes | Slower restart (must replay all operations) |
| Human-readable format | Write amplification |

### AOF Rewriting

The AOF file grows over time. Redis periodically rewrites it to contain only the minimal set of commands to reconstruct the current dataset:

```redis
BGREWRITEAOF                           -- trigger manual rewrite

-- automatic rewrite (in redis.conf)
auto-aof-rewrite-percentage 100        -- rewrite when AOF is 100% larger than last rewrite
auto-aof-rewrite-min-size 64mb         -- don't rewrite if AOF is smaller than 64MB
```

### Practical Recommendations

| Scenario | Configuration |
|---|---|
| Pure cache (data is reconstructible) | No persistence, or RDB only for faster restarts |
| General purpose (some data loss acceptable) | RDB + AOF with `everysec` |
| Maximum durability | AOF with `always` (but accept the performance hit) |
| Backups | RDB snapshots copied to external storage (S3, etc.) |

For most production deployments: **enable both RDB and AOF**. RDB for fast restarts and backups. AOF for minimal data loss. Redis uses the AOF to restore on startup if both exist (it's more complete).

---

## 14. Replication

Reference: [Replication](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/)

Redis replication creates read replicas that are exact copies of a primary instance:

```
Writes ──→ Primary ──→ Replica 1 (read-only)
                   ──→ Replica 2 (read-only)
                   ──→ Replica 3 (read-only)
```

```redis
-- on the replica
REPLICAOF primary-host 6379

-- promote a replica to primary
REPLICAOF NO ONE

-- check replication status
INFO replication
```

### How It Works

1. Replica connects to primary and requests a full sync
2. Primary runs `BGSAVE` to create an RDB snapshot
3. Primary sends the RDB to the replica (initial sync)
4. Primary sends all new write commands to the replica in real-time (ongoing replication)

Replication is **asynchronous** by default — writes to the primary return before replicas confirm receipt. This means:
- A replica can be slightly behind the primary
- If the primary fails before a write propagates, that write is lost
- Read-your-writes consistency requires reading from the primary

### Wait for Replication

```redis
SET key value
WAIT 2 5000
-- wait until at least 2 replicas have acknowledged the write
-- or 5000 milliseconds have passed, whichever comes first
```

`WAIT` provides synchronous replication on demand. Use it for critical writes where you need replica confirmation.

### Read Replicas

Replicas can serve read traffic to scale read-heavy workloads:

```python
# primary for writes
primary = redis.Redis(host="primary", port=6379)

# replicas for reads (round-robin or random)
replicas = [
    redis.Redis(host="replica-1", port=6379),
    redis.Redis(host="replica-2", port=6379),
]

def read(key):
    replica = random.choice(replicas)
    return replica.get(key)

def write(key, value):
    primary.set(key, value)
```

---

## 15. Redis Sentinel

Reference: [Sentinel](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/)

Sentinel provides automatic failover — if the primary goes down, Sentinel promotes a replica and reconfigures the other replicas.

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│Sentinel 1│  │Sentinel 2│  │Sentinel 3│    (monitor + vote)
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Primary  │→ │Replica 1 │  │Replica 2 │    (data nodes)
└──────────┘  └──────────┘  └──────────┘
```

### How Failover Works

1. Sentinels continuously ping the primary
2. If a quorum of Sentinels agree the primary is unreachable → **objective down (ODOWN)**
3. One Sentinel is elected leader and selects the best replica
4. The selected replica is promoted to primary (`REPLICAOF NO ONE`)
5. Other replicas are reconfigured to replicate from the new primary
6. Clients are notified of the new primary's address

### Client Configuration

```python
from redis.sentinel import Sentinel

sentinel = Sentinel(
    [("sentinel-1", 26379), ("sentinel-2", 26379), ("sentinel-3", 26379)],
    socket_timeout=0.5
)

# get the current primary
primary = sentinel.master_for("mymaster", socket_timeout=0.5)
primary.set("key", "value")

# get a replica for reads
replica = sentinel.slave_for("mymaster", socket_timeout=0.5)
value = replica.get("key")
```

**Key point**: clients connect to Sentinel to discover the primary, not directly to a Redis instance. After a failover, the client asks Sentinel for the new primary address.

### Deployment

Always run an **odd number** of Sentinels (3 or 5) for quorum voting. Deploy Sentinels on separate machines from the Redis data nodes so a single machine failure doesn't take out both a data node and a Sentinel.

---

## 16. Redis Cluster

Reference: [Redis Cluster](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/)

Redis Cluster distributes data across multiple primaries for horizontal scaling. Each primary owns a subset of the keyspace.

### How It Works

Redis Cluster divides the keyspace into **16,384 hash slots**. Each key is mapped to a slot using CRC16:

```
slot = CRC16(key) mod 16384
```

Slots are distributed across primary nodes:

```
Primary A: slots 0–5460
Primary B: slots 5461–10922
Primary C: slots 10923–16383
```

Each primary can have replicas for failover (Cluster handles its own failover, no Sentinel needed).

### Multi-Key Operations

Commands that operate on multiple keys only work if all keys are in the same slot. Use **hash tags** to force keys into the same slot:

```redis
-- these might be on different nodes — MGET fails
MGET user:1001 user:1002

-- hash tags force keys to the same slot (hashed on the {content} inside braces)
SET {user:1001}:name "Alice"
SET {user:1001}:email "alice@example.com"
MGET {user:1001}:name {user:1001}:email    -- works — same slot
```

The portion of the key inside `{...}` determines the slot. All keys with the same hash tag go to the same node.

### Resharding

Adding or removing nodes requires moving slots between nodes. Redis Cluster handles this online (no downtime):

```bash
redis-cli --cluster add-node new-node:6379 existing-node:6379
redis-cli --cluster reshard existing-node:6379
redis-cli --cluster rebalance existing-node:6379
```

### Cluster vs Sentinel

| | Sentinel | Cluster |
|---|---|---|
| Purpose | High availability (failover) | High availability + horizontal scaling |
| Data distribution | All data on one primary | Data sharded across multiple primaries |
| Max dataset size | Limited by single node's RAM | Sum of all nodes' RAM |
| Write scaling | Single primary (one writer) | Multiple primaries (parallel writes) |
| Multi-key operations | All keys on same server, always work | Only if keys share a hash tag |
| Complexity | Moderate | Higher |

**Use Sentinel** when your dataset fits on a single machine and you need automatic failover.
**Use Cluster** when you need more capacity than one machine can provide.

---

## 17. Security

Reference: [Security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)

### Authentication

```redis
-- set a password (redis.conf)
requirepass your-strong-password

-- authenticate from a client
AUTH your-strong-password
```

### ACLs (Access Control Lists)

Redis 6+ supports granular access control:

```redis
-- create a user with limited permissions
ACL SETUSER appuser on >password ~cache:* +GET +SET +DEL -@dangerous

-- breakdown:
-- on           = user is active
-- >password    = set password
-- ~cache:*     = can only access keys matching cache:*
-- +GET +SET    = allowed commands
-- -@dangerous  = deny all commands in the "dangerous" category

-- list users
ACL LIST

-- check current user
ACL WHOAMI
```

### Network Security

- **Bind to specific interfaces**: `bind 127.0.0.1 10.0.0.1` — never bind to `0.0.0.0` in production
- **TLS**: Redis 6+ supports TLS natively — encrypt traffic between clients and server
- **Firewall**: restrict access to the Redis port (6379) to only application servers
- **Disable dangerous commands** in production:

```redis
-- in redis.conf
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command DEBUG ""
rename-command CONFIG ""
```

Or use ACLs to deny these commands for application users while allowing them for admin users.

### Protected Mode

Redis refuses connections from non-loopback interfaces if no password is set and `protected-mode` is enabled (default). This prevents accidentally exposing an open Redis to the internet. Never disable protected mode without setting authentication.

---

## 18. Performance & Memory

### Memory Usage

```redis
-- total memory usage
INFO memory
-- used_memory: 1073741824 (1GB)
-- used_memory_human: 1.00G
-- used_memory_peak: 1.5G
-- mem_fragmentation_ratio: 1.05

-- memory usage of a specific key
MEMORY USAGE user:1001               -- bytes

-- memory doctor
MEMORY DOCTOR                        -- diagnosis and advice
```

### Memory Optimization

**Small aggregate encodings**: Redis uses compact encodings for small collections:

| Data type | Compact encoding | Upgrade threshold |
|---|---|---|
| Hash | listpack | > `hash-max-listpack-entries` (default 128) entries or > `hash-max-listpack-value` (default 64) bytes per value |
| List | listpack | > `list-max-listpack-size` entries |
| Set | listpack (integers: intset) | > `set-max-listpack-entries` (default 128) or > `set-max-listpack-value` (default 64) bytes |
| Sorted Set | listpack | > `zset-max-listpack-entries` (default 128) or > `zset-max-listpack-value` (default 64) bytes |

Keep values small and collections under these thresholds when possible — the compact encoding uses 2–10x less memory than the standard encoding.

**Key optimization strategies:**

```python
# bad — verbose keys
r.set("application:user:profile:data:user_id:1001:field:name", "Alice")

# good — concise keys (saves memory at scale)
r.set("u:1001:n", "Alice")

# bad — storing JSON blobs when a hash works
r.set("user:1001", json.dumps({"name": "Alice", "age": 30, "email": "..."}))

# good — use a hash (individual fields, partial reads, atomic updates)
r.hset("user:1001", mapping={"name": "Alice", "age": 30, "email": "..."})

# bad — many small keys with shared prefix
r.set("config:feature:dark_mode", "true")
r.set("config:feature:new_checkout", "false")

# good — one hash
r.hset("config:features", mapping={"dark_mode": "true", "new_checkout": "false"})
```

### Slow Operations to Avoid

| Command | Problem | Alternative |
|---|---|---|
| `KEYS *` | Scans entire keyspace, blocks server | `SCAN` with cursor |
| `SMEMBERS` on huge sets | Returns all members | `SSCAN` with cursor |
| `HGETALL` on huge hashes | Returns all fields | `HSCAN` with cursor |
| `LRANGE 0 -1` on huge lists | Returns all elements | Paginate with offsets |
| `SORT` on large collections | O(N*log(N)), blocks | Sort client-side |
| `DEL` on large key | Blocks while freeing memory | `UNLINK` (async delete) |
| `FLUSHALL` / `FLUSHDB` | Blocks for entire operation | `FLUSHALL ASYNC` |

### Monitoring Performance

```redis
-- real-time command monitoring (DANGEROUS in production — adds latency)
MONITOR

-- slow log — commands that exceeded a threshold
SLOWLOG GET 10                         -- last 10 slow commands
CONFIG SET slowlog-log-slower-than 10000  -- log commands > 10ms (in microseconds)

-- command stats
INFO commandstats                      -- per-command call count, latency

-- latency monitoring
LATENCY LATEST
LATENCY HISTORY event-name

-- connected clients
INFO clients
CLIENT LIST
```

### Key Metrics to Monitor

| Metric | What it indicates | Worry threshold |
|---|---|---|
| `used_memory` vs `maxmemory` | Memory pressure | > 80% of maxmemory |
| `mem_fragmentation_ratio` | Memory fragmentation | > 1.5 (wasted memory) or < 1 (swapping) |
| `connected_clients` | Connection count | Approaching `maxclients` |
| `evicted_keys` | Keys being evicted under memory pressure | Any non-zero value (if unexpected) |
| `keyspace_misses / keyspace_hits` | Cache hit rate | Hit rate < 90% for a cache |
| `instantaneous_ops_per_sec` | Throughput | Sudden drops indicate problems |
| `rejected_connections` | Client connection failures | Any non-zero value |
| `latest_fork_usec` | Time spent in `fork()` for persistence | > 1 second |
| Slowlog entries | Commands exceeding latency threshold | Any entries |

---

## 19. Common Patterns

### Cache-Aside (Lazy Loading)

The most common caching pattern — application manages cache reads and writes:

```python
def get_data(key):
    # 1. check cache
    cached = r.get(f"cache:{key}")
    if cached:
        return json.loads(cached)

    # 2. cache miss — fetch from source
    data = database.query(key)

    # 3. populate cache
    r.setex(f"cache:{key}", 300, json.dumps(data))
    return data

def update_data(key, new_data):
    # 1. update source
    database.update(key, new_data)

    # 2. invalidate cache (delete, don't update — avoids race conditions)
    r.delete(f"cache:{key}")
```

**Why delete instead of update the cache**: between reading the old data and writing the new cache, another request might fetch the data from the database and write a different cache value. Deleting avoids this race.

### Write-Through Cache

Write to cache and database simultaneously:

```python
def update_data(key, new_data):
    r.setex(f"cache:{key}", 300, json.dumps(new_data))
    database.update(key, new_data)
```

Keeps cache and database consistent but adds write latency. Use when read-after-write consistency is critical.

### Cache Stampede Prevention

When a popular key expires, many concurrent requests hit the database simultaneously:

```python
def get_with_stampede_prevention(key, ttl=300, lock_ttl=10):
    cached = r.get(f"cache:{key}")
    if cached:
        return json.loads(cached)

    # try to acquire a lock — only one request recomputes
    lock_key = f"lock:cache:{key}"
    acquired = r.set(lock_key, "1", nx=True, ex=lock_ttl)

    if acquired:
        try:
            data = database.query(key)
            r.setex(f"cache:{key}", ttl, json.dumps(data))
            return data
        finally:
            r.delete(lock_key)
    else:
        # another request is recomputing — wait and retry
        time.sleep(0.1)
        return get_with_stampede_prevention(key, ttl, lock_ttl)
```

Alternative: set TTLs with jitter to prevent many keys from expiring at the same time.

### Sliding Window Counter

```python
def count_events(r, key, window_seconds):
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zcard(key)
    results = pipe.execute()
    return results[1]

def record_event(r, key, window_seconds):
    now = time.time()
    pipe = r.pipeline()
    pipe.zadd(key, {f"{now}:{uuid4()}": now})
    pipe.zremrangebyscore(key, "-inf", now - window_seconds)
    pipe.expire(key, window_seconds)
    pipe.execute()
```

### Distributed Semaphore

Limit concurrent access to a shared resource:

```python
def acquire_semaphore(r, name, limit, timeout=10):
    token = str(uuid4())
    key = f"semaphore:{name}"
    now = time.time()

    pipe = r.pipeline(True)
    pipe.zremrangebyscore(key, "-inf", now - timeout)  # remove expired
    pipe.zadd(key, {token: now})
    pipe.zrank(key, token)
    _, _, rank = pipe.execute()

    if rank < limit:
        return token  # acquired
    else:
        r.zrem(key, token)  # over limit, remove ourselves
        return None

def release_semaphore(r, name, token):
    r.zrem(f"semaphore:{name}", token)
```

### Geospatial Index

```redis
-- add locations
GEOADD restaurants -122.4194 37.7749 "Pizzeria"
GEOADD restaurants -122.4089 37.7837 "Sushi Bar"
GEOADD restaurants -122.4000 37.7900 "Taqueria"

-- find restaurants within 2km of a point
GEOSEARCH restaurants FROMLONLAT -122.4100 37.7800 BYRADIUS 2 km ASC WITHCOORD WITHDIST

-- distance between two members
GEODIST restaurants "Pizzeria" "Sushi Bar" km

-- get coordinates
GEOPOS restaurants "Pizzeria"
```

Geospatial indexes are built on sorted sets internally — each location is stored as a member with its geohash as the score.

---

## 20. Client Libraries & Best Practices

### Client Libraries

| Language | Library | Notes |
|---|---|---|
| Python | [redis-py](https://github.com/redis/redis-py) | Official, async support (`redis.asyncio`) |
| Node.js | [ioredis](https://github.com/redis/ioredis) | Full-featured, Cluster/Sentinel support |
| Go | [go-redis](https://github.com/redis/go-redis) | Official, type-safe |
| Rust | [redis-rs](https://github.com/redis-rs/redis-rs) | Async support, connection pooling |
| Java | [Jedis](https://github.com/redis/jedis) or [Lettuce](https://github.com/lettuce-io/lettuce-core) | Jedis is simpler, Lettuce is reactive/async |

### Connection Pooling

Never create a new connection per request — use a connection pool:

```python
# python redis-py (connection pool is built in)
pool = redis.ConnectionPool(
    host="localhost",
    port=6379,
    max_connections=20,
    decode_responses=True,  # return strings instead of bytes
)
r = redis.Redis(connection_pool=pool)
```

```python
# async
import redis.asyncio as aioredis

pool = aioredis.ConnectionPool.from_url("redis://localhost", max_connections=20)
r = aioredis.Redis(connection_pool=pool)

async def get_data(key):
    return await r.get(key)
```

### Error Handling

```python
import redis

try:
    r.get("key")
except redis.ConnectionError:
    # can't reach Redis — serve from fallback or return error
    pass
except redis.TimeoutError:
    # command took too long — consider increasing timeout or investigating
    pass
except redis.RedisError:
    # all other Redis errors
    pass
```

### Key Design Principles

1. **Namespace keys consistently**: `object:id:field` (e.g., `user:1001:sessions`)
2. **Set TTLs on everything that's a cache**: don't assume you'll remember to clean up
3. **Use the right data structure**: don't serialize a list into a string when a Redis list works
4. **Pipeline bulk operations**: never loop over single commands
5. **Keep values small**: large values block the event loop and waste memory
6. **Prefer UNLINK over DEL for large keys**: `UNLINK` frees memory in the background
7. **Use SCAN instead of KEYS**: `KEYS` blocks the server, `SCAN` is incremental

---

## 21. Common Mistakes

### 1. Using KEYS in Production

```redis
-- NEVER do this in production
KEYS user:*
```

`KEYS` scans the entire keyspace and blocks the server until complete. On a database with millions of keys, this freezes Redis for seconds. Use `SCAN` instead.

### 2. No maxmemory Configuration

Without `maxmemory`, Redis grows until the OS OOM-killer terminates it, potentially taking down the entire server. Always set `maxmemory` and an eviction policy.

### 3. Storing Large Objects

A 10MB JSON blob in a Redis string blocks the event loop for the duration of the network I/O and serialization. Keep values under 100KB. For larger data, store a reference in Redis and the data in object storage.

### 4. Not Using Connection Pools

Creating a TCP connection per Redis command adds milliseconds of latency and can exhaust file descriptors under load. Always use a connection pool.

### 5. Fire-and-Forget Error Handling

```python
# bad — silently ignores Redis being down
def get_cached(key):
    try:
        return r.get(key)
    except:
        return None
```

This masks outages. At minimum, log the error. Better: have a clear fallback strategy (serve stale data, bypass cache, return a degraded response).

### 6. Using Redis as the Primary Data Store

Redis can persist to disk, but it's not a database. Power loss during the gap between an AOF `everysec` fsync means up to 1 second of data loss. If you can't reconstruct the data from another source, use a real database as the source of truth.

### 7. Not Setting TTLs

Every cache entry should have a TTL. Without TTLs, cached data goes stale, memory grows unbounded, and you end up needing a manual cleanup process. Even long TTLs (24 hours, 7 days) are better than no TTL.

### 8. Running Without Replication in Production

A single Redis instance is a single point of failure. At minimum, run a primary with one replica and Sentinel for automatic failover.

### 9. Ignoring Serialization Costs

```python
# json.dumps/loads can be a bottleneck at high throughput
r.set("key", json.dumps(large_object))        # slow
data = json.loads(r.get("key"))                # slow

# consider msgpack or protobuf for high-throughput paths
import msgpack
r.set("key", msgpack.packb(large_object))
data = msgpack.unpackb(r.get("key"))
```

### 10. Hot Keys

A single key receiving a disproportionate share of traffic becomes a bottleneck. In Redis Cluster, that key's node handles all the load while others idle.

Solutions:
- **Read replicas** for hot read keys
- **Key splitting**: distribute a counter across multiple keys (`counter:{0}` through `counter:{9}`), sum on read
- **Local caching**: cache the hot value in application memory with a short TTL

---

## Quick Reference: Data Structure Selection

| You need to... | Data structure |
|---|---|
| Cache a value with expiry | String with `EX`/`PX` |
| Represent an object with fields | Hash |
| Count something atomically | String with `INCR` |
| Implement a queue | List with `LPUSH`/`BRPOP` |
| Track unique items | Set |
| Track unique items (memory-efficient, approximate) | HyperLogLog |
| Rank/sort items by score | Sorted Set |
| Implement a priority queue | Sorted Set with `ZPOPMIN` |
| Rate limit | Sorted Set (sliding window) or String (fixed window) |
| Store time-series events | Stream |
| Track boolean per user (daily activity) | Bitmap |
| Broadcast messages to subscribers | Pub/Sub |
| Reliable event processing with consumer groups | Stream |
| Find items within a geographic radius | Geospatial (Geo commands) |
| Distributed lock | String with `SET NX EX` |

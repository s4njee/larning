# Asyncio & aiohttp Study Guide

A depth-first guide to `asyncio` and `aiohttp` for Python engineers who need to make I/O-bound code fast and keep it correct. It assumes you can write ordinary Python and have at least seen `async`/`await`; it does **not** assume you understand the event loop. This guide is the deep dive that the [Python Concurrency](PYTHON_CONCURRENCY.md) survey hands off to — that guide answers "which concurrency model do I pick?"; this one answers "I've picked asyncio — now how do I master it, build real services with aiohttp, and actually make it fast?"

> *Async doesn't make your code run faster. It makes your code stop waiting. Everything in this guide follows from that one distinction — and most async bugs come from forgetting it.*

The guide leans hard on two things you asked any performance-minded async guide to deliver: **aiohttp** (client and server, in depth) and **practical performance** — bounded concurrency, connection pooling, `uvloop`, bulk-loading Postgres with `asyncpg`, streaming files with `aiofiles`, and the anti-patterns that quietly serialize your "concurrent" code.

Primary references: the [asyncio documentation](https://docs.python.org/3/library/asyncio.html) (especially the [developing-with-asyncio pitfalls page](https://docs.python.org/3/library/asyncio-dev.html)), the [aiohttp docs](https://docs.aiohttp.org/en/stable/) (client and server halves are separate manuals — read both), the [asyncpg docs](https://magicstack.github.io/asyncpg/current/), and Łukasz Langa's [asyncio video series](https://www.youtube.com/playlist?list=PLhNSoGM2ik6SIkVGXWBwerucXjgP1rHmB) (the CPython core dev's from-scratch walkthrough — the best deep explanation of the event loop in any medium).

---

## Table of Contents

- [Part 1 — Why Async, and When It Actually Helps](#part-1--why-async-and-when-it-actually-helps)
- [Part 2 — The Execution Model](#part-2--the-execution-model)
- [Part 3 — Running Things Concurrently](#part-3--running-things-concurrently)
- [Part 4 — Cancellation, Timeouts & Exceptions](#part-4--cancellation-timeouts--exceptions)
- [Part 5 — Coordination & Backpressure](#part-5--coordination--backpressure)
- [Part 6 — The Cardinal Sin: Blocking the Event Loop](#part-6--the-cardinal-sin-blocking-the-event-loop)
- [Part 7 — aiohttp Client](#part-7--aiohttp-client)
- [Part 8 — aiohttp Server](#part-8--aiohttp-server)
- [Part 9 — Talking to Databases & Files](#part-9--talking-to-databases--files)
- [Part 10 — Performance: Measuring & Tuning](#part-10--performance-measuring--tuning)
- [Part 11 — Debugging & Production](#part-11--debugging--production)
- [Part 12 — Recipes](#part-12--recipes)

---

## Part 1 — Why Async, and When It Actually Helps

### 1.1 The One Idea

A normal Python program that makes a network call *blocks*: it sends the request, then sits on the thread doing nothing until the response comes back. If a request takes 200ms and you make 100 of them, that's 20 seconds of mostly *waiting* — the CPU is idle the whole time.

`asyncio` lets a single thread do something else during that wait. When one coroutine is parked waiting on the network, the event loop runs another. The CPU stays busy issuing requests and processing responses instead of idling. Make those same 100 requests concurrently and they finish in roughly the time of the slowest one, not the sum of all of them.

That is the entire value proposition: **async eliminates idle waiting on I/O.** It does not make any individual operation faster, and it does not add CPU cores. Hold onto that — it's the lens for every decision in this guide.

### 1.2 I/O-Bound vs CPU-Bound — The Decision That Comes First

Whether async helps you depends entirely on what your program spends its time doing:

- **I/O-bound** — most of the time is spent *waiting*: network calls, database queries, reading files, talking to other services. The CPU is mostly idle. **This is where async shines.** A web scraper, an API gateway, a service that fans out to ten microservices — async can turn sequential waiting into concurrent waiting and win enormously.

- **CPU-bound** — most of the time is spent *computing*: parsing huge documents, image processing, numerical work, cryptography. The CPU is pegged. **Async does nothing for you here.** Worse, a long computation inside a coroutine *blocks the entire event loop* (Part 6) and stalls every other task. CPU-bound work needs multiple processes (or a native-threaded library), not asyncio — see the [Python Concurrency](PYTHON_CONCURRENCY.md) guide for that side.

```
   Sequential I/O          Concurrent I/O (async)
   req1 ====              req1 ====
        req2 ====         req2 ====
             req3 ====    req3 ====
   |--- 3× latency ---|   |- 1× latency -|
```

The first question for any "make it faster with async" task is therefore not *how* but *whether*: **is this workload actually I/O-bound?** If you're not waiting on I/O, async is the wrong tool and Part 10's tuning won't save you.

### 1.3 Async vs Threads vs Processes

Python has three concurrency models; async is one of them, and it's worth knowing precisely why you'd pick it:

| | **asyncio** | **Threads** | **Processes** |
|---|---|---|---|
| Good for | I/O-bound, *many* concurrent ops | I/O-bound, *some* blocking calls | CPU-bound |
| Concurrency unit | Coroutine (cheap — KBs) | OS thread (MBs) | OS process (heavy) |
| How many feasible | 10,000s+ | 100s | ~ CPU cores |
| Switching | Cooperative (at `await`) | Preemptive (OS) | Preemptive (OS) |
| Parallel on multiple cores? | No (one thread) | No (the GIL)* | Yes |
| Failure mode | One blocking call stalls *everything* | Races, locks, deadlocks | IPC cost, memory |

\* Until the free-threaded build (PEP 703, experimental in 3.13) matures.

The reason to reach for asyncio specifically: it scales to **tens of thousands** of concurrent operations on one thread with kilobytes of overhead each, because a parked coroutine is just a small object, not an OS thread with a megabyte stack. A thread pool tops out in the hundreds before context-switching and memory cost dominate. If you need 5,000 simultaneous outbound HTTP requests or 50,000 open WebSocket connections (see the [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) guide), async is the only model that does it comfortably.

### 1.4 The Cost You Take On

Async is not free, and pretending otherwise leads to the bugs in Parts 4, 6, and 11. The honest costs:

- **It's viral.** `await` can only be used inside `async def`. Once one function is async, its callers tend to become async too — "async all the way down." Mixing sync and async correctly takes care.
- **The whole ecosystem must cooperate.** A single blocking library call (the classic: `requests`, or `time.sleep`, or a synchronous DB driver) freezes the event loop and every task on it (Part 6). You need *async* libraries — `aiohttp` not `requests`, `asyncpg` not `psycopg2`-sync.
- **The failure modes are unfamiliar.** "Coroutine was never awaited," "Task was destroyed but it is pending," accidental serialization that makes your concurrent code secretly sequential. Part 11 is a catalog of these.

Take on this cost when the workload is genuinely I/O-bound and concurrency is high enough to matter. For a script that makes three API calls, `ThreadPoolExecutor` is simpler and just as fast. For a service juggling thousands of concurrent I/O operations, async pays for itself many times over.

References: [asyncio — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html), [Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html).

---

## Part 2 — The Execution Model

Most async bugs trace back to a fuzzy mental model of what's actually happening. This part makes it precise. Internalize it and the rest of the guide is mostly application.

### 2.1 Coroutines: Calling One Does Nothing

A coroutine function is defined with `async def`. The crucial surprise: **calling it does not run it.** It returns a coroutine *object* — a paused computation waiting to be driven.

```python
import asyncio

async def greet():
    print("hello")

coro = greet()          # prints NOTHING — just creates a coroutine object
print(type(coro))       # <class 'coroutine'>
# RuntimeWarning: coroutine 'greet' was never awaited

asyncio.run(greet())    # NOW it runs and prints "hello"
```

This is the single most common beginner trip-up, and the source of the `coroutine 'x' was never awaited` warning (Part 11). A coroutine only makes progress when something *drives* it: you `await` it, you wrap it in a Task, or you hand it to `asyncio.run`.

### 2.2 The Event Loop

The **event loop** is the engine. It maintains a queue of ready-to-run tasks and a set of tasks parked on I/O. Its job is a simple cycle: run a task until it hits an `await` that can't complete immediately; park it; run the next ready task; when an awaited I/O operation completes, mark its task ready again.

```python
asyncio.run(main())     # creates a loop, runs main() to completion, closes the loop
```

`asyncio.run` is the standard entry point. It builds a fresh event loop, runs your top-level coroutine until it finishes, then cleans up. You generally call it **once**, at the top of your program. (Calling it inside an already-running loop raises `RuntimeError: asyncio.run() cannot be called from a running event loop` — the Jupyter/`await`-at-top-level gotcha from Part 11.)

There is exactly **one loop, on one thread**, running **one** piece of your code at any instant. Async concurrency is not parallelism — it's fast interleaving.

### 2.3 `await` Is a Yield Point

`await` does two things: it waits for an awaitable to produce a result, and — critically — it **gives the event loop permission to run other tasks** while waiting. Every `await` is a point where control *may* leave your coroutine and go elsewhere.

```python
async def fetch_user(uid):
    print(f"start {uid}")
    await asyncio.sleep(1)      # yields control here; loop runs other tasks for ~1s
    print(f"done {uid}")
    return uid
```

This has a profound and easily-missed consequence: **between two `await`s, your coroutine runs without interruption** (no other task can touch shared state), but **at every `await`, other tasks can run and mutate shared state.** That's why asyncio rarely needs locks for CPU operations — but *does* need them when a critical section spans an `await` (Part 5). Cooperative scheduling means you always know where the switch points are: they're exactly the `await`s.

Equally important in reverse: code with **no `await`** never yields. A coroutine that does a long synchronous computation, or calls a blocking function, holds the loop hostage — nothing else runs until it returns. That's Part 6, and it's the cardinal sin of async.

### 2.4 Coroutines, Tasks, and Futures

Three "awaitable" things exist, and knowing the difference clears up most confusion:

- **Coroutine** — the paused computation from an `async def`. Awaiting one runs it *inline*: `result = await fetch_user(1)` runs `fetch_user` to completion before the next line. By itself, a coroutine gives you **sequencing, not concurrency**.

- **Task** — a coroutine *scheduled on the loop to run concurrently*. `asyncio.create_task(coro)` wraps a coroutine in a Task and hands it to the loop immediately; the Task makes progress on its own at await points, alongside whatever else is running. This is the unit of concurrency.

- **Future** — a low-level placeholder for a result that will exist later. You rarely create Futures directly; libraries use them under the hood. A Task *is* a kind of Future.

```python
# Awaiting a coroutine directly = sequential. Total time ≈ 2 seconds.
async def sequential():
    a = await fetch_user(1)     # runs fully...
    b = await fetch_user(2)     # ...then this runs. One after the other.

# Wrapping in Tasks = concurrent. Total time ≈ 1 second.
async def concurrent():
    t1 = asyncio.create_task(fetch_user(1))   # scheduled, starts running
    t2 = asyncio.create_task(fetch_user(2))   # scheduled, starts running
    a = await t1                               # both are already in flight;
    b = await t2                               # we just wait for their results
```

The difference between `sequential` and `concurrent` above is the difference between "using asyncio" and "benefiting from asyncio." It is *the* thing people get wrong (Part 10 calls it accidental serialization). `await some_coroutine()` in a loop is sequential; you need Tasks — or the higher-level `gather`/`TaskGroup` of Part 3 — to actually run things at the same time.

### 2.5 One Footgun to Name Now: Keep a Reference to Your Tasks

`create_task` schedules a Task, but the event loop only keeps a **weak** reference to it. If you don't hold a reference yourself, the garbage collector can destroy the Task mid-flight — producing the baffling `Task was destroyed but it is pending!` (Part 11).

```python
# BAD: nothing holds the task; it may be GC'd before finishing
asyncio.create_task(background_job())

# GOOD: keep a strong reference until it's done
background_tasks = set()
task = asyncio.create_task(background_job())
background_tasks.add(task)
task.add_done_callback(background_tasks.discard)   # clean up when finished
```

In practice the cleanest fix is to not manage bare tasks at all — use a `TaskGroup` (Part 3), which owns its tasks and guarantees they complete. We flag the footgun here because it follows directly from "the loop only weakly references tasks," and it explains an error you *will* otherwise hit.

References: [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html), [`asyncio.create_task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task), [Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html).

---

## Part 3 — Running Things Concurrently

Part 2 established that concurrency comes from Tasks, not from awaiting coroutines inline. This part covers the high-level APIs you'll actually use to launch and collect concurrent work. There are four, and they are not interchangeable.

### 3.1 `asyncio.gather` — Run Many, Collect Results in Order

`gather` schedules a batch of awaitables concurrently and returns their results as a list, **in the order you passed them** (not the order they finished):

```python
import asyncio

async def fetch(uid):
    await asyncio.sleep(uid)        # pretend this is a network call
    return f"user-{uid}"

async def main():
    # All three run concurrently; total time ≈ 3s (the slowest), not 6s (the sum)
    results = await asyncio.gather(fetch(1), fetch(2), fetch(3))
    print(results)                  # ['user-1', 'user-2', 'user-3'] — input order

asyncio.run(main())
```

`gather` is the workhorse for "do these N things at once and give me all the answers." A common idiom is to gather over a comprehension:

```python
urls = [...]
results = await asyncio.gather(*(fetch(u) for u in urls))   # the * unpacks the generator
```

**The exception behavior is a trap.** By default, if any awaitable raises, `gather` propagates that first exception immediately — but the *other* tasks keep running, now unobserved, and you lose their results (and may get warnings about un-retrieved exceptions). Pass `return_exceptions=True` to instead get a list where failures appear as exception objects alongside successful results:

```python
results = await asyncio.gather(*coros, return_exceptions=True)
for r in results:
    if isinstance(r, Exception):
        log.warning("one failed: %r", r)     # handle per-item failure
    else:
        process(r)
```

Use `return_exceptions=True` whenever partial success is acceptable (scraping 1,000 URLs and tolerating a few failures). Use the default when any failure should abort the batch — but prefer `TaskGroup` (next) for that case, because it cleans up properly.

References: [`asyncio.gather`](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather).

### 3.2 `asyncio.TaskGroup` — Structured Concurrency (3.11+)

`TaskGroup` (Python 3.11+) is the **modern, preferred** way to run concurrent tasks. It's an async context manager that owns its tasks: it won't exit the `async with` block until all of them finish, and if any task raises, it **cancels the rest** and propagates the error. This is *structured concurrency* — tasks can't outlive the block that spawned them, so you can't leak orphaned tasks.

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(fetch(1))
        t2 = tg.create_task(fetch(2))
        t3 = tg.create_task(fetch(3))
    # On exit: all tasks are guaranteed done. Results available via .result().
    print(t1.result(), t2.result(), t3.result())
```

Why prefer it over `gather`:

- **No leaked tasks.** The block can't be left with tasks still running, so the "keep a reference" footgun (Part 2.5) and "Task was destroyed" error simply can't happen.
- **Correct cancellation.** If one task fails, the others are cancelled rather than left running unobserved.
- **Grouped errors.** Multiple simultaneous failures surface as an `ExceptionGroup`, handled with `except*`:

```python
try:
    async with asyncio.TaskGroup() as tg:
        for u in urls:
            tg.create_task(fetch(u))
except* ConnectionError as eg:
    # eg.exceptions is the tuple of all ConnectionErrors that occurred
    log.error("%d connections failed", len(eg.exceptions))
except* ValueError as eg:
    log.error("%d validation errors", len(eg.exceptions))
```

For new code on 3.11+, **default to `TaskGroup`**; reach for `gather` mainly when you specifically want `return_exceptions=True` semantics (collect-all-including-failures) or you're on an older Python.

References: [`asyncio.TaskGroup`](https://docs.python.org/3/library/asyncio-task.html#task-groups), [PEP 654 — Exception Groups](https://peps.python.org/pep-0654/).

### 3.3 `asyncio.as_completed` — Process Results as They Arrive

Sometimes you don't want to wait for the whole batch — you want to handle each result the moment it's ready, fastest first. `as_completed` yields awaitables in *completion* order:

```python
async def main():
    coros = [fetch(3), fetch(1), fetch(2)]
    for earliest in asyncio.as_completed(coros):
        result = await earliest         # yields in finish order: user-1, user-2, user-3
        print("ready:", result)         # start processing the fast ones immediately
```

This matters for latency: if you're querying five replicas and want to act on the first response, or streaming results to a user as each completes, `as_completed` lets you start work without waiting for stragglers.

References: [`asyncio.as_completed`](https://docs.python.org/3/library/asyncio-task.html#asyncio.as_completed).

### 3.4 `asyncio.wait` — Low-Level Control

`wait` is the low-level primitive. It takes **Tasks** (not bare coroutines — wrap them first) and returns two sets, `(done, pending)`, giving you fine control over *when* to stop waiting via `return_when`:

```python
tasks = [asyncio.create_task(fetch(u)) for u in urls]
done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
# Act on whatever finished first; `pending` is still running — cancel or keep waiting.
for t in pending:
    t.cancel()
```

`return_when` can be `FIRST_COMPLETED`, `FIRST_EXCEPTION`, or `ALL_COMPLETED` (the default). Unlike `gather`/`TaskGroup`, `wait` does **not** propagate exceptions — a failed task just lands in `done`, and you inspect it yourself. Most code should use `gather` or `TaskGroup`; reach for `wait` only when you need this manual done/pending control.

### 3.5 Choosing Among Them

| Use | When |
|-----|------|
| `TaskGroup` | Default for 3.11+. Run a batch, all-or-nothing, clean cancellation and error grouping. |
| `gather` | You want results as a list and/or `return_exceptions=True` partial-success semantics; or pre-3.11. |
| `as_completed` | You want to process results in completion order (latency-sensitive, streaming). |
| `wait` | You need low-level `(done, pending)` control, e.g. "act on the first to finish, cancel the rest." |

---

## Part 4 — Cancellation, Timeouts & Exceptions

This is where async stops being "functions with `await`" and starts being a discipline. Cancellation and timeouts are first-class in asyncio, and getting them wrong causes hung tasks, leaked resources, and swallowed errors. Skipping this part is why people's async code "mostly works."

### 4.1 Timeouts

Never wait forever on I/O. asyncio gives you two ways to bound it.

**`asyncio.timeout` (3.11+)** — the modern, preferred context manager. If the block doesn't finish in time, the operation inside is cancelled and `TimeoutError` is raised:

```python
async def main():
    try:
        async with asyncio.timeout(5):       # 5-second budget for everything inside
            data = await fetch_slow_resource()
    except TimeoutError:
        log.warning("gave up after 5s")
```

**`asyncio.wait_for(aw, timeout)`** — the older single-awaitable form, still common:

```python
try:
    data = await asyncio.wait_for(fetch_slow_resource(), timeout=5)
except TimeoutError:
    log.warning("timed out")
```

Prefer `asyncio.timeout` on 3.11+: it wraps a whole block (not just one awaitable), and there's also `asyncio.timeout_at(deadline)` for an absolute deadline shared across several operations. **A timeout somewhere is mandatory** for any external call — the library default (aiohttp's is 5 minutes, Part 7) is almost never what you want.

References: [`asyncio.timeout`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout), [`asyncio.wait_for`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for).

### 4.2 How Cancellation Actually Works

Cancellation in asyncio is **not** a kill switch. Calling `task.cancel()` schedules a `CancelledError` to be raised inside the coroutine **at its next `await`**. The coroutine then unwinds like any exception — running `finally` blocks and `async with` cleanup on the way out.

```python
async def worker():
    try:
        while True:
            await do_chunk()            # cancellation lands at one of these awaits
    except asyncio.CancelledError:
        await flush_partial_results()   # cleanup runs
        raise                            # ALWAYS re-raise (see below)
    finally:
        release_resources()             # finally always runs

task = asyncio.create_task(worker())
await asyncio.sleep(1)
task.cancel()                            # request cancellation
await task                               # await it to let cleanup complete
```

Two rules that prevent the worst bugs:

1. **A coroutine that never `await`s cannot be cancelled.** Cancellation is delivered at await points; a tight synchronous loop with no `await` is uncancellable *and* blocks the loop (Part 6). Two bugs for the price of one.

2. **If you catch `CancelledError`, re-raise it.** Swallowing it (catching and not re-raising) tells asyncio "I refused cancellation," which breaks timeouts and `TaskGroup` shutdown in ways that are maddening to debug. Catch it only to clean up, then `raise`.

### 4.3 `CancelledError` Is Not a Normal Exception

Since Python 3.8, `asyncio.CancelledError` inherits from `BaseException`, **not** `Exception`. This is deliberate and important: a blanket `except Exception` will **not** accidentally swallow a cancellation.

```python
try:
    await something()
except Exception as e:        # does NOT catch CancelledError — good
    log.error("real error: %r", e)
# CancelledError propagates past this handler, as it should
```

If you write `except BaseException` or bare `except:`, you *will* catch cancellation — almost always a bug. Catch `Exception` for real errors; let `CancelledError` flow.

### 4.4 Shielding Critical Sections

Occasionally an operation must complete even if its caller is cancelled — committing a transaction, releasing a distributed lock. `asyncio.shield` protects an awaitable from cancellation propagating inward:

```python
# If this coroutine is cancelled, the commit still completes rather than
# being interrupted half-way.
await asyncio.shield(commit_transaction())
```

Use `shield` sparingly and deliberately — it's an escape hatch from structured cancellation, and overusing it reintroduces the leaked-work problems structured concurrency exists to prevent.

References: [`asyncio.shield`](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield), [Task cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation).

### 4.5 Exception Propagation: gather vs TaskGroup

Tying Parts 3 and 4 together, because the difference bites in production:

- **`gather` (default)** — the first exception propagates to the caller; sibling tasks keep running, now unobserved. You can lose results and leak work.
- **`gather(return_exceptions=True)`** — nothing propagates; exceptions come back as values in the result list for you to inspect.
- **`TaskGroup`** — the first exception cancels all siblings, then *all* exceptions that occurred are raised together as an `ExceptionGroup` (handle with `except*`). Nothing leaks.

The practical guidance: for "all of these must succeed or we abort cleanly," `TaskGroup` is correct because it cancels and reports everything. For "run all of these and tell me which succeeded and which failed," `gather(return_exceptions=True)` is the tool. Plain `gather` with default exception handling is the one to be wary of — it's easy to reach for and easy to leak work with.

---

## Part 5 — Coordination & Backpressure

Launching 10,000 coroutines is easy. Launching 10,000 coroutines that all hit your database at once is how you take the database down. This part is about *controlling* concurrency — and it contains the single most important performance-and-stability lever in async: **bounding how much runs at once.**

### 5.1 Semaphore — Bound Your Concurrency

A naive `gather` over 5,000 URLs creates 5,000 simultaneous connections. That will exhaust file descriptors, blow past the remote server's rate limits, or melt your connection pool. An `asyncio.Semaphore` caps how many coroutines are in a section at once:

```python
import asyncio, aiohttp

async def fetch(session, url, sem):
    async with sem:                      # acquire a slot; block here if all are taken
        async with session.get(url) as resp:
            return await resp.text()
    # slot released automatically on exit

async def main(urls):
    sem = asyncio.Semaphore(20)          # at most 20 requests in flight at once
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(fetch(session, u, sem) for u in urls))
```

This pattern — **`gather` over everything, `Semaphore` to bound it** — is the backbone of every well-behaved async fan-out in this guide. You still *create* all the coroutines, but only N of them are doing work at any moment; the rest wait their turn at the `async with sem`. Tuning that N is a core part of performance work (Part 10): too low and you leave throughput on the table, too high and you overwhelm the downstream.

> A rule of thumb worth internalizing: **unbounded concurrency is a bug, not a feature.** Any time you `gather` over a collection whose size you don't control, there should be a semaphore (or a worker-pool, below) bounding it.

References: [`asyncio.Semaphore`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore).

### 5.2 Queue — The Producer/Consumer Pattern

`asyncio.Queue` decouples work production from work consumption, and a *bounded* queue gives you **backpressure** for free: when the queue is full, producers block on `put` until consumers catch up, so a fast producer can't pile unbounded work into memory.

```python
async def producer(queue, items):
    for item in items:
        await queue.put(item)            # blocks when the queue is full → backpressure
    for _ in range(NUM_WORKERS):
        await queue.put(None)            # one sentinel per worker to signal "done"

async def worker(queue):
    while True:
        item = await queue.get()
        if item is None:                 # sentinel: shut this worker down
            queue.task_done()
            break
        await process(item)
        queue.task_done()

async def main(items):
    queue = asyncio.Queue(maxsize=100)   # bounded → backpressure when full
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue, items))
        for _ in range(NUM_WORKERS := 10):
            tg.create_task(worker(queue))
```

This fixed-worker-pool shape is the other way to bound concurrency (versus the semaphore): you spawn exactly N workers that pull from a shared queue. It's the right structure for streaming pipelines — ingest a large file, transform, write to a database — where you want steady, bounded throughput rather than a single giant fan-out. We build exactly this pipeline in Part 12.

References: [`asyncio.Queue`](https://docs.python.org/3/library/asyncio-queue.html).

### 5.3 Lock — Protecting State Across `await`

Recall from Part 2.3 that other tasks can run at every `await`. If a critical section *spans* an `await` and touches shared mutable state, you have a race — and you need `asyncio.Lock`:

```python
lock = asyncio.Lock()

async def transfer(account, amount):
    async with lock:                     # only one task in this block at a time
        balance = await read_balance(account)   # await → another task could run...
        await write_balance(account, balance + amount)  # ...so guard the read+write
```

Without the lock, two `transfer`s could both read the old balance during each other's `await` and one update would be lost. Note the nuance: you do **not** need a lock for a sequence of pure synchronous statements (no `await` between them means no task switch). You need it precisely when the invariant must hold across a suspension point. This is rarer than in threaded code — and that's one of async's quiet advantages — but when you need it, you really need it.

### 5.4 Event — Signaling Between Tasks

`asyncio.Event` is a one-bit broadcast: tasks `await event.wait()` until another task calls `event.set()`. It's how you signal "the system is ready" or "shutdown requested" to many waiters at once:

```python
ready = asyncio.Event()

async def consumer():
    await ready.wait()                   # park until someone sets the event
    await do_work()

async def setup():
    await initialize()
    ready.set()                          # wake every waiter
```

`Semaphore`, `Queue`, `Lock`, and `Event` round out the coordination toolkit. In practice you'll reach for `Semaphore` (bound a fan-out) and `Queue` (pipelines) constantly, `Lock` occasionally, and `Event` for lifecycle signaling.

References: [Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html).

---

## Part 6 — The Cardinal Sin: Blocking the Event Loop

Everything in this guide depends on one rule, and breaking it silently destroys the performance you came for. **Never block the event loop.** This part explains what that means, how to detect it, and how to do blocking work safely.

### 6.1 What "Blocking" Means and Why It's Catastrophic

There is one event loop on one thread (Part 2). When a coroutine runs synchronous code that takes time — a CPU computation, `time.sleep`, a blocking network call, reading a big file the synchronous way — it does **not** yield. The loop is stuck inside that call. **Every other task on the loop is frozen** until it returns: every in-flight request stalls, every timer is late, your "concurrent" server handles exactly one thing at a time.

```python
import time, asyncio

async def handler():
    time.sleep(2)                # DISASTER: blocks the ENTIRE loop for 2 seconds.
                                 # Every other coroutine is frozen the whole time.
    return "done"

async def handler_fixed():
    await asyncio.sleep(2)       # correct: yields; the loop runs other tasks for 2s
    return "done"
```

The insidious part is that it *works* in development with one user and looks fine. Under concurrency it falls over, and the symptom — "my async server isn't any faster" — sends people tuning the wrong things. The usual culprits:

- `time.sleep()` instead of `await asyncio.sleep()`
- `requests.get()` (or any sync HTTP client) instead of `aiohttp`/`httpx`
- A synchronous database driver (`psycopg2` in sync mode) instead of `asyncpg`/`aiopg`
- `open(...).read()` on a large file instead of `aiofiles` (Section 6.4)
- Heavy CPU work — JSON-parsing a 100 MB payload, hashing, image resizing — inline in a coroutine
- `json.dumps`/`loads`, regex, or compression on large data

### 6.2 Detecting It: Debug Mode and Slow-Callback Warnings

You don't have to guess. asyncio's **debug mode** logs a warning whenever a callback or coroutine step hogs the loop for too long (default: 100 ms):

```python
asyncio.run(main(), debug=True)        # enable debug mode
# or: set the env var PYTHONASYNCIODEBUG=1
# or: tune the threshold — loop.slow_callback_duration = 0.05  (50ms)
```

When something blocks, you'll see: `Executing <Task ...> took 2.003 seconds`. That line is gold — it points straight at the blocking call. Make a habit of running your test suite or a load test with debug mode on; it surfaces blocking before production does. For deeper digging, a sampling profiler like [`py-spy`](https://github.com/benfred/py-spy) can show where the loop thread spends time without modifying your code (Part 11).

References: [asyncio debug mode](https://docs.python.org/3/library/asyncio-dev.html#asyncio-debug-mode).

### 6.3 Offloading Blocking Work: `to_thread` and Executors

When you *must* call blocking code (a library with no async version, an unavoidable CPU step), don't run it on the loop — push it to a thread or process so the loop stays free.

**Blocking I/O → a thread.** `asyncio.to_thread` (3.9+) runs a sync function in a thread pool and gives you an awaitable:

```python
import asyncio

def blocking_io():
    with open("big.bin", "rb") as f:    # a blocking call from a sync library
        return f.read()

async def main():
    # The loop keeps running other tasks while the thread does the blocking read
    data = await asyncio.to_thread(blocking_io)
```

This works for blocking I/O because the GIL is released during I/O syscalls, so the thread genuinely runs in parallel with the loop. The older, more general form is `loop.run_in_executor(executor, func, *args)`.

**CPU-bound work → a process.** Threads don't help CPU-bound work (the GIL serializes Python bytecode). Offload to a `ProcessPoolExecutor` so the computation runs on another core, leaving both the loop and the GIL free:

```python
from concurrent.futures import ProcessPoolExecutor

async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        # heavy_compute runs in a separate process, on a separate core
        result = await loop.run_in_executor(pool, heavy_compute, big_input)
```

The decision rule restated: **blocking I/O → `to_thread`; CPU-bound → `ProcessPoolExecutor` via `run_in_executor`; genuinely async I/O → just `await` it.** Mixing these up is the root of most "async didn't help" disappointments.

References: [`asyncio.to_thread`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread), [Running in threads / executors](https://docs.python.org/3/library/asyncio-eventloop.html#executing-code-in-thread-or-process-pools).

### 6.4 File I/O Is Special — Enter `aiofiles`

Here's a subtlety that surprises people: **there is no truly asynchronous file I/O on most systems.** Sockets can be non-blocking at the OS level; ordinary disk file reads and writes generally cannot. So when you read a large file, that call blocks — even though it "feels" like the kind of I/O async should handle.

[`aiofiles`](https://github.com/Tinche/aiofiles) gives file operations an async API, but under the hood it does exactly what Section 6.3 prescribes: it **delegates the blocking file operation to a thread pool**. Set expectations correctly — `aiofiles` does **not** make disk I/O faster. Its job is to keep the *event loop unblocked* so that a slow file read doesn't freeze all your concurrent network work:

```python
import aiofiles

async def read_config(path):
    async with aiofiles.open(path, mode="r") as f:
        return await f.read()            # the read happens in a thread; loop stays free

async def stream_lines(path):
    async with aiofiles.open(path, mode="r") as f:
        async for line in f:             # iterate without loading the whole file
            await handle(line)
```

So the mental model for `aiofiles`: it's the file-I/O-shaped wrapper around "offload blocking work to a thread" (Section 6.3), with a convenient `async with`/`async for` API. Use it whenever a coroutine touches the filesystem and you care about keeping the loop responsive — which, in an aiohttp server handling many requests, you always do. We use it heavily in the performance recipes of Part 12, paired with `aiohttp` (stream a download to disk) and `asyncpg` (read a file, bulk-load it).

A caveat to keep honest: because `aiofiles` is thread-pool-backed, throwing thousands of concurrent file operations at it doesn't give thousands-fold parallelism — it's bounded by the thread pool, and ultimately by your disk. For massive *file-crunching* throughput (not just loop-friendliness), you're back to processes and the realities of disk bandwidth. `aiofiles` solves "don't freeze the loop," not "make the disk infinitely fast."

References: [`aiofiles` (GitHub)](https://github.com/Tinche/aiofiles).

---

## Part 7 — aiohttp Client

[`aiohttp`](https://docs.aiohttp.org/en/stable/) is the de-facto asyncio HTTP library — both a client and a server. This part covers the client; it's what you reach for instead of `requests` (which is blocking and would freeze the loop, Part 6). Getting the client right is mostly about three things: reusing the session, bounding concurrency, and setting timeouts.

### 7.1 The Session Is the Connection Pool — Reuse It

The `ClientSession` owns the connection pool, the DNS cache, cookies, and default headers. **Create one session and reuse it for the lifetime of your program (or request batch).** Creating a session per request — the single most common aiohttp mistake — throws away connection pooling and TLS session reuse, turning every request into a fresh TCP+TLS handshake.

```python
import aiohttp, asyncio

# WRONG: a new session (and new connection pool) per request
async def fetch_bad(url):
    async with aiohttp.ClientSession() as session:   # ← created and destroyed every call
        async with session.get(url) as resp:
            return await resp.text()

# RIGHT: one session, reused across all requests
async def fetch(session, url):
    async with session.get(url) as resp:
        resp.raise_for_status()                       # raise on 4xx/5xx
        return await resp.text()

async def main(urls):
    async with aiohttp.ClientSession() as session:    # one pool for the whole batch
        return await asyncio.gather(*(fetch(session, u) for u in urls))
```

In a long-lived service (like the aiohttp *server* of Part 8), create the session once at startup and store it on the app, closing it on shutdown — never per-request.

References: [Client quickstart](https://docs.aiohttp.org/en/stable/client_quickstart.html), [Client reference](https://docs.aiohttp.org/en/stable/client_reference.html).

### 7.2 Connection Pooling with `TCPConnector`

The `TCPConnector` controls the pool. Its limits are a primary performance and politeness lever:

```python
connector = aiohttp.TCPConnector(
    limit=100,              # max total simultaneous connections (default 100)
    limit_per_host=10,      # max simultaneous connections to one host (default 0 = unlimited)
    ttl_dns_cache=300,      # cache DNS lookups for 5 minutes
)
session = aiohttp.ClientSession(connector=connector)
```

`limit` is a hard ceiling on concurrent connections across the whole session; once reached, further requests queue until a connection frees up. This means the connector *itself* provides a form of concurrency bounding — but it's coarse (it caps connections, not your in-flight task count) and silent (tasks just wait). For clear, intentional control, pair it with an explicit `Semaphore` (Part 5.1). `limit_per_host` is the polite-citizen knob: it stops you from opening 100 connections to a single API and getting rate-limited or banned.

References: [Connection pooling / `TCPConnector`](https://docs.aiohttp.org/en/stable/client_advanced.html#limiting-connection-pool-size).

### 7.3 Timeouts — Set Them Explicitly

aiohttp's default total timeout is **5 minutes**. That is almost never what you want; a hung upstream would tie up a connection (and a task) for five minutes. Set timeouts deliberately:

```python
timeout = aiohttp.ClientTimeout(
    total=30,           # whole operation: connect + send + receive
    connect=5,          # acquiring a connection from the pool + establishing it
    sock_connect=5,     # establishing a new socket connection
    sock_read=10,       # max gap between reads of response data
)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(url) as resp:    # uses the session default...
        ...
    # ...or override per request:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        ...
```

Set a session-wide default that's sane for most calls, and override per-request where a specific endpoint needs more or less. This composes with `asyncio.timeout` (Part 4) — aiohttp's timeout bounds the HTTP operation; an outer `asyncio.timeout` can bound a higher-level unit of work that includes several calls.

References: [Timeouts](https://docs.aiohttp.org/en/stable/client_quickstart.html#timeouts).

### 7.4 Reading Responses, Including Streaming

For small responses, read the whole body:

```python
async with session.get(url) as resp:
    text = await resp.text()        # decoded str
    data = await resp.json()        # parsed JSON
    raw = await resp.read()         # raw bytes
```

For **large** responses — a multi-gigabyte file, a long export — never load the whole body into memory. Stream it in chunks. This is essential for the download-to-disk recipe in Part 12:

```python
async with session.get(url) as resp:
    resp.raise_for_status()
    async for chunk in resp.content.iter_chunked(64 * 1024):   # 64 KB at a time
        await sink.write(chunk)     # write to aiofiles, a queue, another socket…
```

Streaming keeps memory flat regardless of response size, and lets you start processing before the whole body arrives.

### 7.5 Bounded Concurrent Fan-Out

The canonical client workload — "fetch these N URLs as fast as is polite" — combines everything so far: one session, a semaphore to bound concurrency, timeouts, and `gather` (or `TaskGroup`) with per-item error tolerance.

```python
import aiohttp, asyncio

async def fetch_one(session, sem, url):
    async with sem:                                  # bound concurrency (Part 5)
        try:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return url, await resp.text()
        except aiohttp.ClientError as e:             # network/HTTP errors
            return url, e
        except TimeoutError as e:                    # from ClientTimeout
            return url, e

async def fetch_all(urls, concurrency=20):
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=concurrency)   # align pool with concurrency
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        return await asyncio.gather(*(fetch_one(session, sem, u) for u in urls))
```

Aligning the connector `limit` with your semaphore size avoids the two fighting each other. Catching `aiohttp.ClientError` (the base class for connection errors, HTTP errors, etc.) and `TimeoutError` per item means one bad URL doesn't sink the batch — partial-success semantics, which is usually what you want for a large fan-out.

References: [`ClientError` hierarchy](https://docs.aiohttp.org/en/stable/client_reference.html#client-exceptions).

### 7.6 Retries

aiohttp has **no built-in retry** — a deliberate choice, since correct retry policy is application-specific. Roll a small retry-with-backoff helper, retrying only *idempotent* requests and *transient* failures (connection errors, timeouts, 5xx — never a 4xx, which won't change by retrying):

```python
import asyncio, random, aiohttp

async def fetch_with_retry(session, url, attempts=4):
    for attempt in range(attempts):
        try:
            async with session.get(url) as resp:
                if resp.status >= 500:
                    raise aiohttp.ClientResponseError(
                        resp.request_info, resp.history, status=resp.status)
                resp.raise_for_status()
                return await resp.text()
        except (aiohttp.ClientError, TimeoutError):
            if attempt == attempts - 1:
                raise                                  # out of retries
            # exponential backoff with jitter (Part 4 of the WebSockets guide too)
            delay = 2 ** attempt + random.random()
            await asyncio.sleep(delay)
```

The backoff-with-jitter shape is the same one used for WebSocket reconnection in the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) — it spreads retries out so a recovering server isn't stampeded. If you'd rather not hand-roll it, the [`aiohttp-retry`](https://github.com/inyutin/aiohttp_retry) package wraps the session with configurable retry policies.

---

## Part 8 — aiohttp Server

aiohttp is also a capable async web framework. It's lower-level and less magical than FastAPI/Starlette (covered in the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md))— closer to the metal, with an explicit application object and lifecycle. That explicitness makes it a good vehicle for understanding how an async server actually fits together.

References: [Server quickstart](https://docs.aiohttp.org/en/stable/web_quickstart.html), [Web server reference](https://docs.aiohttp.org/en/stable/web_reference.html).

### 8.1 Application, Handlers, Routes

A handler is a coroutine that takes a `Request` and returns a `Response`. An `Application` ties handlers to routes:

```python
from aiohttp import web

async def hello(request):
    return web.Response(text="Hello, world")

async def get_user(request):
    uid = request.match_info["uid"]              # path parameter
    fmt = request.query.get("format", "json")    # query string ?format=
    return web.json_response({"id": uid, "format": fmt})

async def create_user(request):
    body = await request.json()                  # parse JSON request body
    return web.json_response({"created": body}, status=201)

app = web.Application()
app.add_routes([
    web.get("/", hello),
    web.get("/users/{uid}", get_user),           # {uid} → request.match_info["uid"]
    web.post("/users", create_user),
])

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
```

`web.json_response(...)` serializes to JSON and sets the content type; `web.Response(text=..., status=...)` is the general form. Path parameters arrive in `request.match_info`, query params in `request.query`, and the body via `await request.json()` / `await request.post()` / `await request.read()`.

There's also a decorator style with `RouteTableDef` (`routes = web.RouteTableDef()` then `@routes.get("/")`), handy for spreading routes across modules.

### 8.2 Application State and Lifecycle — Where Pools Live

A real service needs resources that are expensive to create and must be shared across requests: a database connection pool (Part 9), an `aiohttp.ClientSession` for outbound calls (Part 7), a Redis client. **Create them once at startup, share them via the app, and close them on shutdown.** aiohttp's `cleanup_ctx` is the clean idiom — an async generator that sets up before `yield` and tears down after:

```python
from aiohttp import web
import asyncpg, aiohttp

async def db_pool_ctx(app):
    # --- startup: runs once before serving ---
    app["db"] = await asyncpg.create_pool(dsn="postgresql://localhost/app",
                                          min_size=5, max_size=20)
    yield
    # --- shutdown: runs once after the server stops accepting requests ---
    await app["db"].close()

async def http_client_ctx(app):
    app["http"] = aiohttp.ClientSession()        # one outbound session for the service
    yield
    await app["http"].close()

async def list_users(request):
    pool = request.app["db"]                      # reuse the shared pool
    rows = await pool.fetch("SELECT id, name FROM users LIMIT 100")
    return web.json_response([dict(r) for r in rows])

app = web.Application()
app.cleanup_ctx.append(db_pool_ctx)               # register lifecycle hooks
app.cleanup_ctx.append(http_client_ctx)
app.add_routes([web.get("/users", list_users)])
```

This is the most important structural pattern for an aiohttp service: shared, pooled resources created once and reused by every request handler, with deterministic cleanup. Creating a DB pool or `ClientSession` *inside a handler* is the server-side version of the per-request-session mistake from Part 7 — it destroys pooling and tanks throughput. (`app.on_startup` / `app.on_cleanup` lists exist too; `cleanup_ctx` is preferred because setup and teardown live together and teardown still runs if startup partially failed.)

References: [Application lifecycle / cleanup contexts](https://docs.aiohttp.org/en/stable/web_advanced.html#cleanup-context), [Sharing state](https://docs.aiohttp.org/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please).

### 8.3 Middleware

Middleware wraps every request — for logging, auth, error handling, metrics. A middleware is a coroutine taking `(request, handler)` that calls `await handler(request)` somewhere in the middle:

```python
from aiohttp import web
import time, logging

log = logging.getLogger("access")

@web.middleware
async def logging_middleware(request, handler):
    start = time.perf_counter()
    try:
        response = await handler(request)
        return response
    finally:
        dur = (time.perf_counter() - start) * 1000
        log.info("%s %s -> %dms", request.method, request.path, dur)

@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise                                     # let aiohttp's own HTTP errors through
    except Exception:
        log.exception("unhandled error")
        return web.json_response({"error": "internal"}, status=500)

app = web.Application(middlewares=[error_middleware, logging_middleware])
```

Middleware runs in the order listed (outermost first), so put error handling outermost so it catches everything inside. This is the natural place to add the structured logging and request metrics you'd feed into an [Observability](OBSERVABILITY_STUDY_GUIDE.md) stack.

References: [Middleware](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares).

### 8.4 Streaming Responses and WebSockets

For large or open-ended responses, stream instead of buffering. `StreamResponse` lets you write the body incrementally:

```python
async def download(request):
    resp = web.StreamResponse()
    resp.content_type = "text/csv"
    await resp.prepare(request)                   # send headers, begin streaming
    async for row in generate_rows():
        await resp.write(row.encode())            # write chunks as they're produced
    await resp.write_eof()
    return resp
```

aiohttp also has first-class **WebSocket** support on the server side, which is exactly the asyncio-shaped use case the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) explores in depth (rooms, auth, scaling). The aiohttp surface:

```python
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)                     # complete the upgrade handshake
    async for msg in ws:                          # iterate messages until close
        if msg.type == web.WSMsgType.TEXT:
            await ws.send_str(f"echo: {msg.data}")
        elif msg.type == web.WSMsgType.ERROR:
            break
    return ws
```

The single-thread event loop is what makes one aiohttp process able to hold thousands of these connections at once — the same property from Part 1.3. For the protocol, scaling backplane, and auth patterns, see the WebSockets guide; this is just the aiohttp entry point.

References: [Streaming responses](https://docs.aiohttp.org/en/stable/web_quickstart.html#streaming-response), [WebSockets](https://docs.aiohttp.org/en/stable/web_quickstart.html#websockets).

### 8.5 Running in Production: Workers for Multiple Cores

`web.run_app(app)` runs a single process on a single core — fine for development and for I/O-bound services that don't saturate a core. But remember Part 1: **one event loop uses one core.** To use a multi-core machine, run **multiple worker processes**. The standard way is Gunicorn with aiohttp's worker class:

```bash
gunicorn myapp:app \
  --bind 0.0.0.0:8080 \
  --worker-class aiohttp.GunicornWebWorker \
  --workers 4                                    # ≈ number of CPU cores
```

Each worker is an independent process with its own event loop, and the OS load-balances connections across them. This is how you scale an aiohttp service horizontally on one box; to scale across boxes, put a load balancer (the [Caddy](CADDY_STUDY_GUIDE.md) guide) in front of several instances. Note that per-worker state (in-memory caches, WebSocket connection registries) is *not* shared across workers — shared state needs an external store like Redis, exactly as in the WebSockets scaling discussion.

For app-factory setups, expose an `async def init_app()` returning the application and point Gunicorn at it. Pair this with a sane `--graceful-timeout` so in-flight requests drain on deploy (Part 11).

References: [Deployment with Gunicorn](https://docs.aiohttp.org/en/stable/deployment.html), [`GunicornWebWorker` setup](https://docs.aiohttp.org/en/stable/deployment.html#start-gunicorn).

---

## Part 9 — Talking to Databases & Files

An async service is only as async as its slowest dependency. Use a *synchronous* database driver in a coroutine and you block the loop (Part 6) — every request freezes while one query runs. This part covers the async Postgres drivers (`asyncpg` and `aiopg`), the connection-pool model, file I/O with `aiofiles`, and the accidental-serialization trap that quietly makes "async" database code sequential.

### 9.1 asyncpg — The Performance Choice

[`asyncpg`](https://magicstack.github.io/asyncpg/current/) is a from-scratch PostgreSQL driver built for asyncio. It does **not** use `psycopg2`; it speaks Postgres's binary protocol directly, which makes it substantially faster than the alternatives — the project benchmarks it at roughly **3× faster than `psycopg2`/`aiopg`** for many workloads, largely thanks to binary encoding and automatic prepared-statement caching. For new, performance-sensitive async code, it's the default.

```python
import asyncpg, asyncio

async def main():
    # A pool is the right unit: a set of reusable connections, created once.
    pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/app",
        min_size=5, max_size=20,            # see pool sizing in 9.4
    )
    async with pool.acquire() as conn:      # borrow a connection; returned on exit
        # Parameters use $1, $2 placeholders — NEVER f-strings (SQL injection)
        rows = await conn.fetch("SELECT id, name FROM users WHERE age > $1", 18)
        for r in rows:                      # Records are tuple- AND dict-like
            print(r["id"], r["name"])

        one = await conn.fetchrow("SELECT * FROM users WHERE id = $1", 42)
        count = await conn.fetchval("SELECT count(*) FROM users")   # single scalar
        await conn.execute("UPDATE users SET seen = now() WHERE id = $1", 42)

    await pool.close()

asyncio.run(main())
```

asyncpg's headline methods: `fetch` (list of rows), `fetchrow` (one row), `fetchval` (one scalar), `execute` (no rows), `executemany` (batched parameterized statement), and `copy_records_to_table` (COPY — the bulk-load fast path, Part 10). Transactions are an async context manager:

```python
async with pool.acquire() as conn:
    async with conn.transaction():          # BEGIN; COMMIT on success, ROLLBACK on error
        await conn.execute("INSERT INTO ledger(amount) VALUES($1)", 100)
        await conn.execute("UPDATE balance SET total = total + $1", 100)
```

The parameter style is positional `$1, $2`. As always, pass parameters as arguments — never build SQL with f-strings or `%` formatting, which opens SQL injection (see the [Postgres](POSTGRES.md) guide for query-level depth).

References: [asyncpg documentation](https://magicstack.github.io/asyncpg/current/), [asyncpg usage](https://magicstack.github.io/asyncpg/current/usage.html), [Connection pools](https://magicstack.github.io/asyncpg/current/api/index.html#connection-pools).

### 9.2 aiopg — The Compatibility Choice

[`aiopg`](https://aiopg.readthedocs.io/) takes the other approach: it wraps `psycopg2`, driving libpq in its asynchronous (non-blocking) mode. Its API mirrors psycopg2's cursor model, and it offers `aiopg.sa` for SQLAlchemy Core integration.

```python
import aiopg, asyncio

async def main():
    pool = await aiopg.create_pool("dbname=app user=user password=pass host=localhost")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # psycopg2 parameter style: %s placeholders (params as a tuple)
            await cur.execute("SELECT id, name FROM users WHERE age > %s", (18,))
            async for row in cur:           # iterate the cursor
                print(row)
    pool.close()
    await pool.wait_closed()

asyncio.run(main())
```

When to choose `aiopg` over `asyncpg`, honestly:

- You have existing **psycopg2** code or SQL using `%s` placeholders and want minimal changes.
- You specifically need **`aiopg.sa`** (SQLAlchemy Core in an async style).

For most new code, prefer `asyncpg` for the performance, and note that modern **SQLAlchemy (1.4+/2.0) has native async support built on asyncpg** via `create_async_engine("postgresql+asyncpg://…")` — which largely supersedes `aiopg.sa` if you want an ORM/Core layer with asyncpg's speed underneath. Treat `aiopg` as the compatibility bridge, not the performance pick.

References: [aiopg documentation](https://aiopg.readthedocs.io/en/stable/), [SQLAlchemy asyncio extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).

### 9.3 The Accidental-Serialization Trap

Here is the database performance bug that hides in plain sight. A single connection processes one query at a time, and awaiting queries in a loop runs them strictly sequentially:

```python
# SLOW: N queries, one after another. Total ≈ N × query_latency.
async def get_many_slow(pool, user_ids):
    results = []
    async with pool.acquire() as conn:
        for uid in user_ids:
            results.append(await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid))
    return results
```

There are two correct fixes, and the better one is usually *not* "add more concurrency":

```python
# BETTER: one set-based query instead of N round trips. One trip to the DB.
async def get_many_fast(pool, user_ids):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE id = ANY($1)", user_ids)

# WHEN you genuinely need N independent queries: parallelize across pool connections.
async def run_independent(pool, queries):
    async def one(q):
        async with pool.acquire() as conn:    # each gets its OWN connection
            return await conn.fetch(q)
        # NB: bounded by pool max_size — that's your concurrency cap
    return await asyncio.gather(*(one(q) for q in queries))
```

The hierarchy of fixes: **first, eliminate the N queries** with a set-based query (`= ANY($1)`, a join, an aggregate) — fewer round trips beats more concurrency every time, and it's where the [Postgres](POSTGRES.md) guide's set-based thinking pays off. **Only if the queries are genuinely independent** should you fan them out — and then each needs its *own* connection from the pool (you can't run two queries concurrently on one connection), which means your real concurrency ceiling is the pool's `max_size`.

### 9.4 Pool Sizing — The Lever That Cuts Both Ways

The pool's `max_size` is one of the most consequential numbers in an async service, and bigger is **not** better. Every pooled connection is a real Postgres backend **process** on the server (Postgres forks per connection). A few thousand connections will exhaust Postgres's memory and scheduler long before they help you.

Practical guidance:

- Size the pool to the **database's** capacity, not your task count. Tens of connections per service instance is typical; the right number depends on Postgres's `max_connections` and how many instances you run.
- If you need to support far more concurrent *clients* than the database can hold *connections*, put **PgBouncer** (a connection pooler) in front of Postgres — it multiplexes many client connections onto a small pool of real backends. This is standard at scale.
- Remember the chain: your `Semaphore` (Part 5) bounds tasks → tasks contend for pool connections → the pool bounds real DB connections. Make these numbers consistent so one isn't silently throttling behind another.

### 9.5 Files: `aiofiles` in the Data Path

Part 6.4 introduced `aiofiles` and the key truth — file I/O is thread-pool-backed, used to keep the *loop* responsive, not to make the disk faster. In a data pipeline it pairs naturally with the database and HTTP client: stream a download to disk without buffering it in memory, or read a file and bulk-load it into Postgres. Those are exactly the Part 12 recipes. The pattern to carry forward:

```python
import aiofiles

async def save_stream(resp, path):           # resp from aiohttp (Part 7.4)
    async with aiofiles.open(path, "wb") as f:
        async for chunk in resp.content.iter_chunked(64 * 1024):
            await f.write(chunk)              # disk write offloaded; loop stays free
```

---

## Part 10 — Performance: Measuring & Tuning

This is the part you came for: making async code actually fast. The headline is uncomfortable — **most "slow async" is not slow because the loop is slow; it's slow because of two specific bugs.** Find those first, then tune.

### 10.1 Measure First — and Know the Two Usual Culprits

Before tuning anything, measure, and check for the two bugs that account for the overwhelming majority of async performance problems:

1. **Blocking the event loop** (Part 6) — a synchronous call freezing everything. Symptom: throughput collapses under concurrency; CPU pegged on one core inside a sync call.
2. **Accidental serialization** (Parts 2.4, 9.3) — `await` in a loop running "concurrent" work sequentially. Symptom: total time scales with the *number* of operations, not the *slowest* one.

Tools to find them:

```python
# 1. asyncio debug mode flags loop-blocking with "took N seconds" warnings
asyncio.run(main(), debug=True)

# 2. Coarse timing to spot serialization: does time scale with N or with max?
import time
start = time.perf_counter()
await do_the_work()
print(f"{time.perf_counter() - start:.2f}s")     # compare against expected concurrent time
```

For production or hard-to-reproduce cases, [`py-spy`](https://github.com/benfred/py-spy) samples a running process without code changes — `py-spy top --pid <pid>` shows where the loop thread spends time, and `py-spy dump` shows what every task is stuck on. **Don't tune blind:** a guessed `uvloop` install won't help if your real problem is a `requests.get` blocking the loop.

### 10.2 uvloop — A Faster Event Loop

[`uvloop`](https://uvloop.readthedocs.io/) is a drop-in replacement for asyncio's event loop, built on libuv (the same engine behind Node.js). It's a genuine, free speedup for I/O-heavy workloads — commonly **2–4× higher throughput** on network benchmarks — with a one-line change:

```python
import asyncio, uvloop

# Python 3.12+: pass a loop factory
asyncio.run(main(), loop_factory=uvloop.new_event_loop)

# Or the classic form (works broadly):
uvloop.install()
asyncio.run(main())

# uvloop also provides its own runner:
uvloop.run(main())
```

Caveats: uvloop doesn't run on Windows, and it speeds up *loop overhead* — it won't fix a blocked loop or serialized awaits (Section 10.1), and it won't help CPU-bound work. But for a correctly-written I/O-bound service, it's close to free performance. (aiohttp's docs explicitly recommend it.)

References: [uvloop](https://uvloop.readthedocs.io/), [uvloop on PyPI](https://pypi.org/project/uvloop/).

### 10.3 Kill Accidental Serialization

This is the highest-leverage *correctness-as-performance* fix. Anywhere you `await` inside a loop over independent work, you're leaving concurrency on the table:

```python
# SLOW — sequential despite "being async". Time = sum of all latencies.
results = []
for item in items:
    results.append(await process(item))

# FAST — concurrent (bounded). Time ≈ slowest item, throughput capped sanely.
sem = asyncio.Semaphore(50)
async def bounded(item):
    async with sem:
        return await process(item)
results = await asyncio.gather(*(bounded(item) for item in items))
```

The fix is always the same shape: build the coroutines, run them with `gather`/`TaskGroup`, bound them with a `Semaphore` (Part 5). The discipline: whenever you write `await` inside a `for`, ask "do these depend on each other?" If not, you're serializing needlessly.

### 10.4 Batch and Pipeline — Especially at the Database

Cutting the *number* of round trips usually beats adding concurrency. The biggest single lever in data-loading code is using Postgres `COPY` via asyncpg's `copy_records_to_table` instead of inserting row by row — it can be **one to two orders of magnitude faster** than per-row `INSERT`s, because it's a single bulk protocol operation instead of thousands of round trips:

```python
# SLOW: one INSERT per row — thousands of round trips
async with pool.acquire() as conn:
    for rec in records:
        await conn.execute("INSERT INTO events(ts, kind, payload) VALUES($1,$2,$3)", *rec)

# FASTER: executemany batches the parameterized statement
async with pool.acquire() as conn:
    await conn.executemany("INSERT INTO events(ts, kind, payload) VALUES($1,$2,$3)", records)

# FASTEST: COPY — bulk-load in a single operation (often 10–100× the per-row loop)
async with pool.acquire() as conn:
    await conn.copy_records_to_table(
        "events", records=records, columns=["ts", "kind", "payload"])
```

The same principle generalizes: prefer one set-based query over N (Part 9.3); use an API's batch endpoint over N individual calls; coalesce many small writes into fewer larger ones. Part 12 builds the full file-to-Postgres `COPY` recipe.

For JSON-heavy services, swapping the stdlib `json` for [`orjson`](https://github.com/ijl/orjson) is another easy win — it serializes/deserializes several times faster, which matters when you're encoding large responses on the hot path.

### 10.5 Tune Connection Pools and Concurrency Limits

With the bugs gone and batching in place, tune the dials — together, because they form a chain (Part 9.4):

- **HTTP**: the `TCPConnector` `limit` / `limit_per_host` (Part 7.2) and your fan-out `Semaphore` (Part 5.1). Align them.
- **Database**: the pool `max_size` (Part 9.4), sized to Postgres's capacity, with PgBouncer if you need more client concurrency than DB connections.
- **Workers**: process count for multi-core (Part 8.5).

The non-obvious lesson: **more concurrency is not monotonically faster.** Past the real bottleneck — the remote API's rate limit, the database's connection ceiling, your disk's bandwidth — adding concurrency only adds contention, context-switching, and memory pressure, and can make throughput *worse*. The job is to find the bottleneck (Section 10.1) and size concurrency to *just* saturate it, not to crank every number to maximum.

### 10.6 Know When Async Has Stopped Being the Answer

Finally, the honest boundary. Async tuning helps an I/O-bound workload. If profiling shows you're **CPU-bound** — the loop thread is pegged doing computation, not waiting — no amount of `uvloop`, pooling, or `gather` will help, because one event loop is one core (Part 1). At that point the levers are different:

- Offload the CPU work to a `ProcessPoolExecutor` (Part 6.3) so it runs on other cores.
- Scale out to multiple worker processes (Part 8.5) behind a load balancer.
- Reconsider whether async was the right model at all — for a CPU-bound batch job, processes (see [Python Concurrency](PYTHON_CONCURRENCY.md)) may be simpler and faster.

Recognizing this boundary is itself a performance skill: it stops you from tuning an event loop that was never your bottleneck.

---

## Part 11 — Debugging & Production

Async failures look different from synchronous ones, and the error messages are cryptic until you've seen them once. This part is a field guide to the errors you'll actually hit and the production hygiene that prevents most of them.

### 11.1 Always Develop with Debug Mode

asyncio's debug mode (Part 6.2) is the cheapest bug-catcher you have. It warns on loop-blocking, on coroutines that were never awaited, and on tasks destroyed while pending — turning silent misbehavior into loud warnings:

```python
asyncio.run(main(), debug=True)        # or set PYTHONASYNCIODEBUG=1
```

Run your tests and a local load test with it on. Most of the errors below surface immediately under debug mode instead of intermittently in production.

### 11.2 The Error Catalog

**`RuntimeWarning: coroutine 'foo' was never awaited`** — you called an `async def` function but never drove it (Part 2.1). You wrote `foo()` where you meant `await foo()` or `asyncio.create_task(foo())`.

```python
foo()                       # ← bug: creates a coroutine, never runs it
await foo()                 # fix: run it inline
asyncio.create_task(foo())  # fix: run it concurrently (and keep a reference, below)
```

**`Task was destroyed but it is pending!`** — you created a task but didn't keep a reference, and it was garbage-collected mid-flight (Part 2.5). Fix by holding a reference, or — far better — by using a `TaskGroup` (Part 3.2) that owns its tasks.

**`RuntimeError: Event loop is closed`** — something tried to use the loop after `asyncio.run` closed it. The classic cause is an `aiohttp.ClientSession` (or DB pool) that wasn't closed before the program ended. Always close them — `async with` for short scripts, `cleanup_ctx` for servers (Part 8.2):

```python
async with aiohttp.ClientSession() as session:   # guarantees close before loop teardown
    ...
```

**`RuntimeError: asyncio.run() cannot be called from a running event loop`** — you called `asyncio.run` while a loop is already running. Most common in Jupyter/IPython (which runs a loop for you) — there you simply `await` at the top level instead of calling `asyncio.run`. In library code, accept a coroutine and let the caller run it; don't call `asyncio.run` yourself.

**`got Future <...> attached to a different loop`** — an awaitable created under one event loop is being awaited under another. Usually from creating loop-bound objects (a session, a lock, a pool) at import time or in another thread, then using them inside `asyncio.run`. Fix: create loop-bound resources *inside* the running loop (e.g. in `cleanup_ctx`, not at module top level).

**`RuntimeWarning: Enable tracemalloc to get the object allocation traceback`** — not an error itself; it accompanies the warnings above. Set `PYTHONTRACEMALLOC=1` (or `tracemalloc.start()`) to get a traceback pointing at where the offending coroutine/task was created.

### 11.3 Graceful Shutdown

A production async service must shut down cleanly: stop accepting new work, let in-flight work finish (or cancel it deliberately), and close pools and sessions so no connections leak. `aiohttp`'s `web.run_app` and `cleanup_ctx` (Part 8.2) handle most of this for you — on `SIGTERM`/`SIGINT` it stops the listener, drains in-flight requests, and runs cleanup contexts in reverse. That's why putting your pool/session lifecycle in `cleanup_ctx` matters: it ties resource teardown to the shutdown sequence automatically.

For a standalone (non-aiohttp) async program, handle signals explicitly and cancel outstanding tasks:

```python
import asyncio, signal

async def main():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)   # set the event on signal

    async with asyncio.TaskGroup() as tg:
        worker = tg.create_task(run_workers())
        await stop.wait()                         # block until a signal arrives
        worker.cancel()                           # request graceful cancellation (Part 4)
    # TaskGroup exit waits for cleanup; finally-blocks in workers run here

asyncio.run(main())
```

The shape: a shutdown `Event` set by a signal handler, tasks that handle `CancelledError` to flush and release resources (Part 4.2), and a `TaskGroup` to guarantee everything is awaited before exit. This is what separates a service that drops in-flight requests on deploy from one that drains cleanly.

References: [Event loop signal handling](https://docs.python.org/3/library/asyncio-eventloop.html#unix-signals), [aiohttp graceful shutdown](https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown).

### 11.4 Logging and Observability

Standard `logging` works in async code, but add request/task context so interleaved logs are readable — async logs from many concurrent tasks are otherwise an unintelligible braid. Attach a correlation id (per request, per task) via `logging` `extra=` or `contextvars` (which are async-task-aware, unlike thread-locals). The aiohttp logging middleware from Part 8.3 is the natural hook for per-request timing and ids, and those structured logs and latency metrics feed directly into the [Observability](OBSERVABILITY_STUDY_GUIDE.md) stack — RED-style request rate/errors/duration is exactly what an async service should export.

---

## Part 12 — Recipes

Copy-paste performance recipes built from the parts above, centered on the libraries you'll lean on most: `aiohttp`, `aiofiles`, and `asyncpg`/`aiopg`. Each one is a complete, runnable shape with the decisions called out.

### Recipe 1: Concurrent Download-to-Disk (aiohttp + aiofiles)

Download many files concurrently and stream each to disk, so **neither the network nor the disk ever blocks the loop**, memory stays flat regardless of file size, and concurrency is bounded. This is the textbook `aiohttp` + `aiofiles` pairing (Parts 6.4, 7.4, 9.5).

```python
import asyncio, aiohttp, aiofiles
from pathlib import Path

async def download(session, sem, url, dest):
    async with sem:                                   # bound concurrency (Part 5.1)
        async with session.get(url) as resp:
            resp.raise_for_status()
            async with aiofiles.open(dest, "wb") as f:
                # Stream in chunks: response body never fully buffered in memory,
                # and the disk write is offloaded to a thread so the loop stays free.
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    await f.write(chunk)
    return dest

async def download_all(urls, outdir="downloads", concurrency=10):
    Path(outdir).mkdir(exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=300, sock_read=30)   # explicit (Part 7.3)
    connector = aiohttp.TCPConnector(limit=concurrency)        # align pool with concurrency
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [download(session, sem, u, Path(outdir) / Path(u).name) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)  # tolerate failures
    for url, res in zip(urls, results):
        if isinstance(res, Exception):
            print(f"FAILED {url}: {res!r}")
        else:
            print(f"saved  {res}")

asyncio.run(download_all(["https://example.com/a.zip", "https://example.com/b.zip"]))
```

Why it performs: streaming (`iter_chunked` + `aiofiles.write`) keeps memory constant for any file size; the semaphore stops a thousand-URL list from opening a thousand sockets; `return_exceptions=True` means one dead URL doesn't abort the batch.

### Recipe 2: Fast Bulk-Load a File into Postgres (aiofiles + asyncpg COPY)

Read a large CSV/JSONL file without blocking the loop, parse it, and load it into Postgres with **`COPY`** — the fast path that's often 10–100× a per-row insert loop (Part 10.4).

```python
import asyncio, aiofiles, asyncpg, csv, io

async def bulk_load(dsn, path, table):
    # 1. Read the file without blocking the loop (Part 6.4 / 9.5)
    async with aiofiles.open(path, "r") as f:
        content = await f.read()

    # 2. Parse into tuples (CPU-light here; for huge files, see Recipe 4's streaming)
    reader = csv.reader(io.StringIO(content))
    next(reader)                                       # skip header
    records = [(row[0], int(row[1]), row[2]) for row in reader]

    # 3. COPY the records in one bulk operation — the big performance lever
    conn = await asyncpg.connect(dsn)
    try:
        await conn.copy_records_to_table(
            table, records=records, columns=["name", "age", "city"])
        print(f"loaded {len(records)} rows via COPY")
    finally:
        await conn.close()

asyncio.run(bulk_load("postgresql://localhost/app", "people.csv", "people"))
```

The contrast that makes the point — the same load done the slow way:

```python
# SLOW baseline: one INSERT per row. For 100k rows this is 100k round trips.
async with pool.acquire() as conn:
    for rec in records:
        await conn.execute(
            "INSERT INTO people(name, age, city) VALUES($1,$2,$3)", *rec)
# copy_records_to_table replaces all of that with a single bulk transfer.
```

For files too large to hold in memory, don't `await f.read()` the whole thing — stream it (Recipe 4) and `COPY` in batches.

### Recipe 3: Bounded Concurrent Queries Through an asyncpg Pool

Run many independent queries concurrently, correctly: each on its **own** pooled connection (Part 9.3), with the pool's `max_size` as the real concurrency ceiling (Part 9.4). Contrast with the serialized loop that looks async but isn't.

```python
import asyncio, asyncpg

async def fan_out_queries(dsn, user_ids):
    pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)  # 20 = concurrency cap
    try:
        async def fetch_user(uid):
            async with pool.acquire() as conn:        # own connection per concurrent query
                return await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        # Concurrent, bounded by the pool. NOT a sequential await-in-a-loop.
        return await asyncio.gather(*(fetch_user(uid) for uid in user_ids))
    finally:
        await pool.close()

# Reminder from Part 9.3: if these IDs are just a set lookup, the RIGHT answer is
# a single set-based query, which beats any amount of fan-out:
async def fetch_users_best(pool, user_ids):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE id = ANY($1)", user_ids)
```

The lesson embedded here: reach for `fetch_users_best` (one round trip) first; use the bounded fan-out only when the queries are genuinely different and independent.

### Recipe 4: Streaming ETL Pipeline (aiofiles + Queue + asyncpg COPY)

The capstone, combining a bounded queue (Part 5.2), `aiofiles` streaming (Part 6.4), and batched `COPY` (Part 10.4): read a file too big for memory line by line, transform with a pool of workers, and bulk-load to Postgres in batches — with backpressure throughout so memory stays bounded no matter how big the input.

```python
import asyncio, aiofiles, asyncpg, json

BATCH_SIZE = 1000
NUM_WORKERS = 4

async def producer(path, queue):
    # Stream the file line by line — never load it all into memory (Part 6.4)
    async with aiofiles.open(path, "r") as f:
        async for line in f:
            await queue.put(line)                  # blocks when full → backpressure (Part 5.2)
    for _ in range(NUM_WORKERS):
        await queue.put(None)                      # one sentinel per worker

async def worker(queue, pool):
    batch = []
    async def flush():
        if batch:
            async with pool.acquire() as conn:
                await conn.copy_records_to_table(   # COPY each batch — the fast path
                    "events", records=batch, columns=["ts", "kind", "payload"])
            batch.clear()
    while True:
        line = await queue.get()
        if line is None:                            # sentinel: drain and stop
            await flush()
            queue.task_done()
            break
        rec = json.loads(line)                      # transform
        batch.append((rec["ts"], rec["kind"], json.dumps(rec["payload"])))
        if len(batch) >= BATCH_SIZE:
            await flush()                           # COPY in bounded batches
        queue.task_done()

async def run_etl(dsn, path):
    queue = asyncio.Queue(maxsize=10_000)           # bounded → memory stays flat
    pool = await asyncpg.create_pool(dsn, min_size=NUM_WORKERS, max_size=NUM_WORKERS)
    try:
        async with asyncio.TaskGroup() as tg:       # structured: all tasks awaited (Part 3.2)
            tg.create_task(producer(path, queue))
            for _ in range(NUM_WORKERS):
                tg.create_task(worker(queue, pool))
    finally:
        await pool.close()

asyncio.run(run_etl("postgresql://localhost/app", "events.jsonl"))
```

This pipeline holds memory constant for an arbitrarily large input (bounded queue + line streaming), keeps the loop unblocked (aiofiles for the read), and maximizes load throughput (batched `COPY` instead of per-row inserts), with `NUM_WORKERS` and `BATCH_SIZE` as the tuning dials. It's the whole guide in one program: bounded concurrency (Part 5), non-blocking file I/O (Part 6), structured concurrency (Part 3), and the database fast path (Parts 9–10).

### Recipe 5: The aiopg Variant (Compatibility Path)

The same concurrent fan-out as Recipe 3, via `aiopg` — for when you're tied to psycopg2's `%s` parameter style or `aiopg.sa`. The honest note travels with it: this is the compatibility path, and `asyncpg` (Recipe 3) is meaningfully faster (Part 9.1–9.2).

```python
import asyncio, aiopg

async def fan_out_aiopg(dsn, user_ids):
    pool = await aiopg.create_pool(dsn, maxsize=20)
    try:
        async def fetch_user(uid):
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id, name FROM users WHERE id = %s", (uid,))  # %s style
                    return await cur.fetchone()
        return await asyncio.gather(*(fetch_user(uid) for uid in user_ids))
    finally:
        pool.close()
        await pool.wait_closed()
```

If you control the stack and care about throughput, prefer Recipe 3's `asyncpg`. Reach for this `aiopg` shape only when an existing psycopg2/SQLAlchemy-Core codebase makes it the path of least resistance — and even then, evaluate SQLAlchemy 2.0's native async-over-asyncpg (Part 9.2) before committing.

---

That's the arc: async buys you the elimination of idle waiting (Part 1), at the cost of a new execution model and new failure modes (Parts 2–4) that you manage with bounded concurrency and a strict no-blocking rule (Parts 5–6). `aiohttp` gives you a fast client and server on top of that model (Parts 7–8); `asyncpg`/`aiopg`/`aiofiles` connect it to your data (Part 9); and real performance comes from measuring, killing serialization, batching at the database, and sizing concurrency to the bottleneck (Part 10) — not from cranking every dial to maximum. The recipes are where it all comes together.

---

## Where to Go Next

- **Read the [asyncio dev/pitfalls page](https://docs.python.org/3/library/asyncio-dev.html)** — the official catalog of the mistakes Parts 4–6 teach you to avoid (never-awaited coroutines, swallowed exceptions, blocking calls), and short enough to absorb in one sitting.
- **Watch Łukasz Langa's [asyncio series](https://www.youtube.com/playlist?list=PLhNSoGM2ik6SIkVGXWBwerucXjgP1rHmB)** — building an event loop from scratch is the fastest way to make Part 2's machinery feel inevitable rather than magical.
- **Read the [aiohttp server docs](https://docs.aiohttp.org/en/stable/web.html)** alongside Part 8, and the [asyncpg docs](https://magicstack.github.io/asyncpg/current/) alongside Part 9 — both are good enough to serve as the canonical second pass.
- **Profile one async service.** Wire up the Part 10 toolkit — `asyncio.timeout`, bounded semaphores, `loop.slow_callback_duration` debugging — against a real workload, find the hidden serialization, and fix it. One "why is my gather not concurrent?" investigation cements the whole model.
- **Sibling guides in this repo:** [Python Concurrency](PYTHON_CONCURRENCY.md) (the model-picker this guide descends from), [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) (generators/coroutines underneath), [Python vs Node.js Async](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) (the comparison), and [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) (long-lived connections on this loop).

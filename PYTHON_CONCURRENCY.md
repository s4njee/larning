# Python Concurrency Guide

A depth-first guide to Python's concurrency models — threads, processes, and async — for engineers who need to make Python do more than one thing at a time and want to pick the *right* model instead of cargo-culting one. It assumes you can write ordinary Python and have hit the wall where a sequential script is too slow, but it does **not** assume you understand the GIL, why threads sometimes help and sometimes don't, or when async is worth its complexity.

This is the **map and the decision guide** for Python concurrency: it covers the whole landscape, explains *why* each model behaves the way it does, and — most importantly — helps you choose. It is the survey that the deeper guides hand off from and to:

- For the depth-first treatment of **async specifically** — the event loop, structured concurrency, `aiohttp`, and async performance — see the companion [Asyncio & aiohttp guide](ASYNCIO_STUDY_GUIDE.md).
- For the **CPython runtime and language internals** underneath all of this — the object model, the GIL's implementation, memory — see the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md).
- For how Python's async model **compares to another language's**, see [Python vs Node.js: Async Compared](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md).

The single decision this guide exists to get right is captured up front, and everything else elaborates it:

> **Is your work I/O-bound or CPU-bound?** I/O-bound → threads or async. CPU-bound → processes. Get this one classification right and the model almost picks itself; get it wrong and no amount of tuning will save you.

Primary references: the [`concurrent.futures`](https://docs.python.org/3/library/concurrent.futures.html), [`threading`](https://docs.python.org/3/library/threading.html), [`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html), and [`asyncio`](https://docs.python.org/3/library/asyncio.html) docs; [PEP 703](https://peps.python.org/pep-0703/) (free-threaded CPython) and [PEP 684](https://peps.python.org/pep-0684/) (per-interpreter GIL); and David Beazley's [talks on the GIL](https://www.dabeaz.com/GIL/) (still the clearest explanation of why it behaves as it does).

---

## Table of Contents

1. [Part 1 — The Mental Model](#part-1--the-mental-model)
2. [Part 2 — The GIL](#part-2--the-gil)
3. [Part 3 — Threading](#part-3--threading)
4. [Part 4 — Multiprocessing](#part-4--multiprocessing)
5. [Part 5 — concurrent.futures: The Unifying Layer](#part-5--concurrentfutures-the-unifying-layer)
6. [Part 6 — asyncio: The Survey](#part-6--asyncio-the-survey)
7. [Part 7 — Choosing a Model](#part-7--choosing-a-model)
8. [Part 8 — Concurrency Patterns](#part-8--concurrency-patterns)
9. [Part 9 — The Future: Free-Threading & Sub-Interpreters](#part-9--the-future-free-threading--sub-interpreters)
10. [Part 10 — Recipes & Pitfalls](#part-10--recipes--pitfalls)

---

## Part 1 — The Mental Model

Before any code, get the model right. Almost every "I added threads and it got *slower*" story, every "why won't my async code run in parallel" question, traces back to a single missing distinction — and once you have it, the whole landscape becomes legible.

### Concurrency Is Not Parallelism

These words get used interchangeably and they are not the same thing:

- **Concurrency** is *dealing with* many things at once — structuring a program so multiple tasks are in progress over the same period, interleaved. A single chef juggling four dishes, switching between them, is concurrent. One worker, many tasks in flight.
- **Parallelism** is *doing* many things at once — multiple tasks literally executing at the same instant, on multiple CPU cores. Four chefs each cooking one dish is parallel. Many workers, simultaneous execution.

Concurrency is about *structure*; parallelism is about *execution*. You can have concurrency without parallelism (one core, time-slicing between tasks — this is exactly what `asyncio` does) and parallelism without meaningful concurrency (a numeric library splitting one array operation across cores). The reason this matters in Python specifically: **the GIL (Part 2) permits concurrency freely but restricts parallelism of Python code to processes.** Holding the distinction is what lets you predict whether a given model will actually use your eight cores or just interleave on one.

### The Master Distinction: I/O-Bound vs CPU-Bound

This is the most important classification in the entire guide. Every workload sits somewhere on this axis, and which end it's on dictates the model:

- **I/O-bound** — the program spends most of its time *waiting* for something external: a network response, a disk read, a database query, a subprocess. The CPU is mostly idle, blocked on I/O. Examples: a web scraper, an API gateway, a service that fans out to other services, a chat server holding thousands of connections.
- **CPU-bound** — the program spends most of its time *computing*: parsing large documents, image/video processing, numerical work, cryptography, machine learning. The CPU is pegged at 100%; there's no waiting to overlap. Examples: resizing a million images, training a model, crunching a large dataset.

How to tell which you have: **run the task and watch a CPU monitor.** If one core sits near 100% the whole time, you're CPU-bound. If CPU usage is low while the program is clearly busy (it's waiting on the network or disk), you're I/O-bound. When in doubt, profile (the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md) covers `cProfile` and friends) — *measure before choosing a concurrency model*, because the two ends want opposite tools.

Why it's decisive:

- For **I/O-bound** work, the win comes from **overlapping the waiting** — while task A waits for its network reply, run task B. You don't need multiple cores; you need a way to not sit idle. Threads and async both do this, and the GIL doesn't hurt you because the GIL is *released* during I/O waits (Part 2).
- For **CPU-bound** work, there's no waiting to overlap — the cores are the bottleneck, and you need *actual parallelism* across them. In CPython, that means **processes** (or a GIL-releasing native library), because the GIL prevents threads from running Python bytecode in parallel.

Put bluntly: **threads and async make waiting cheaper; processes make computing faster.** Use the wrong one and you either add overhead with no benefit (threads on CPU work) or pointlessly pay process-spawn costs (processes on light I/O).

### The Three Models at a Glance

| Model | Mechanism | Parallel? | Best for | GIL impact |
|---|---|---|---|---|
| **Threads** | OS threads, shared memory | Concurrent, not parallel (for Python code) | I/O-bound | Held; released during I/O and by some C extensions |
| **Processes** | Separate interpreters, separate memory | **Truly parallel** | CPU-bound | None — each process has its own GIL |
| **Async** | Coroutines on one thread, one event loop | Concurrent, not parallel | Massive I/O concurrency | N/A — cooperative, single-threaded |

Read the table through the master distinction: the first and third rows are your I/O-bound options (threads for simplicity and blocking libraries, async for scale), the middle row is your CPU-bound option (the only one that gives true parallelism for Python code).

### A Map of What Follows

The guide builds in that order — understand the constraint, then each model, then how to choose, then the patterns and the future:

```text
  Part 1: the mental model (I/O vs CPU — the decision that drives everything)
  Part 2: the GIL (the constraint that makes Python concurrency unusual)
     │
  Part 3: threading   ┐
  Part 4: processes   ├─ the three models, in depth
  Part 6: asyncio     ┘  (Part 5: concurrent.futures unifies threads & processes)
     │
  Part 7: choosing a model (the decision framework + the ThreadPool-vs-asyncio fork)
  Part 8: patterns (producer/consumer, fan-out, bounded concurrency, pipelines)
  Part 9: the future (free-threading & sub-interpreters — the GIL's end)
  Part 10: recipes & pitfalls
```

If you remember one thing from Part 1: **classify the work first — I/O-bound (overlap the waiting: threads or async) or CPU-bound (parallelize the computing: processes).** That single judgment, made by watching a CPU monitor, decides more than any amount of later tuning.

---

## Part 2 — The GIL

You cannot reason about Python concurrency without understanding the **Global Interpreter Lock**. It is the single fact that makes Python's concurrency story different from Java's, Go's, or C's — and it's the source of the field's biggest surprise: that adding threads to CPU-bound Python makes it *no faster, and often slower*.

### What the GIL Is

The GIL is a **mutex inside the CPython interpreter that allows only one thread to execute Python bytecode at a time.** Even on a 64-core machine, a single Python process runs Python code on exactly one core at any instant. Threads exist and switch, but they take turns holding the GIL; they do not run Python bytecode simultaneously.

It is a property of **CPython** (the reference implementation, the one you almost certainly run), not of the Python language. Other implementations differ: Jython and IronPython have no GIL; PyPy has one; and CPython itself now ships an experimental *free-threaded* build that removes it (Part 9). But for the Python you're running today, the GIL is the rule.

### Why It Exists

The GIL isn't an oversight — it's a deliberate trade that has kept CPython simple and fast for single-threaded code for thirty years. The reason is **memory management**: CPython tracks object lifetimes with **reference counting** (every object has a counter of how many references point to it; when it hits zero, the object is freed — covered in the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md)). Reference counts are updated constantly — on essentially every assignment, function call, and data-structure operation — and those updates are *not* atomic. If two threads incremented and decremented the same object's refcount simultaneously without coordination, the counts would corrupt, leading to objects freed while still in use (crashes) or never freed (leaks).

The GIL solves this with one big lock instead of millions of tiny ones: hold the GIL, and you can touch refcounts safely because no other thread is running. The alternative — fine-grained locking on every object — is what free-threaded Python (Part 9) had to build, and it took years and adds overhead. The GIL bought simplicity and single-threaded speed at the cost of multi-threaded CPU parallelism.

### What the GIL Does and Doesn't Block

This is the nuance that the "Python can't do threads" meme misses, and it's exactly why threads are still useful:

**The GIL is *released* during:**

- **Blocking I/O** — network reads/writes, disk I/O, `time.sleep`, subprocess waits. When a thread makes a blocking syscall, CPython releases the GIL so other threads can run while it waits. **This is why threads genuinely help I/O-bound work** — the waiting overlaps.
- **Heavy work in GIL-aware C extensions** — NumPy, pandas, Pillow, lxml, and many scientific/data libraries release the GIL around their compute-heavy C loops. So multithreaded code calling NumPy *can* use multiple cores, because the parallel part runs in C with the GIL dropped. This is a major and underappreciated escape hatch.

**The GIL is *held* during:**

- **Pure-Python bytecode execution** — any computation written in Python (loops, arithmetic, string manipulation, object creation). This is the CPU-bound case, and it's why threads don't parallelize it: the threads serialize on the GIL, taking turns, with context-switching overhead on top — so the threaded version is often *slower* than the sequential one.

```python
# CPU-bound: threads DON'T help (GIL held during pure-Python compute).
# This runs ~as slow as sequential, plus thread overhead — often slower.
import threading
def count(n):
    while n > 0: n -= 1
threads = [threading.Thread(target=count, args=(50_000_000,)) for _ in range(4)]
# ... start/join ... → NOT 4x faster. The GIL serializes them.

# I/O-bound: threads DO help (GIL released during the network wait).
import threading, urllib.request
def fetch(url): urllib.request.urlopen(url).read()
threads = [threading.Thread(target=fetch, args=(u,)) for u in urls]
# ... start/join ... → genuinely concurrent; the waits overlap.
```

### How the Switch Happens

So that one CPU-bound thread doesn't hog the GIL forever, CPython forces a periodic **GIL release-and-reacquire** — by default every 5 milliseconds (tunable via `sys.setswitchinterval()`). The running thread drops the GIL, and the OS scheduler lets another GIL-waiting thread grab it. This is what gives the *illusion* of concurrency for CPU-bound threads — they interleave in 5ms slices — but it's still only one running at a time, and the switching adds overhead, which is why CPU-bound threading is a net loss.

### The Practical Rules

Everything you need to carry from this part:

1. **CPU-bound + need parallelism → use processes**, not threads. Each process has its own interpreter and its own GIL, so they run on separate cores genuinely in parallel (Part 4).
2. **I/O-bound → threads (or async) are fine**, because the GIL is released during the waits that dominate the runtime (Parts 3, 6).
3. **CPU-bound work in a GIL-releasing C library (NumPy etc.) → threads can parallelize it**, because the heavy loop runs in C with the GIL dropped. Check your library's docs.
4. **The GIL is not forever.** Free-threaded CPython (3.13+, Part 9) removes it, changing rule 1 — but it's opt-in and maturing, so design for today's GIL and watch the transition.

If you remember one thing from Part 2: **the GIL lets only one thread run Python bytecode at a time — so threads parallelize *waiting* (I/O, where the GIL is released) but not *computing* (pure Python, where it's held); for CPU parallelism you need processes, and that single fact explains why "add threads" speeds up a scraper and slows down a number-cruncher.**

```quiz
Q: Why does adding 4 threads to a pure-Python CPU-bound loop often make it *slower* than running sequentially?
- [ ] Threads have a memory leak
- [x] The GIL is held during Python bytecode, so the threads serialize on it (only one runs at a time) and you pay context-switching overhead on top
- [ ] Python threads run on a single slow core by design
- [ ] The loop variable is shared between threads
> The GIL allows only one thread to execute Python bytecode at any instant, so CPU-bound threads don't run in parallel — they take turns holding the lock, interleaving in ~5ms slices. You get no speedup and the added switching overhead frequently makes it a net loss. True CPU parallelism needs separate processes, each with its own GIL.

Q: Why do threads genuinely help an I/O-bound web scraper despite the GIL?
- [ ] The GIL doesn't apply to network code
- [x] CPython releases the GIL during blocking I/O syscalls, so while one thread waits on the network another can run — the waits overlap
- [ ] Scrapers are CPU-bound, which threads accelerate
- [ ] Each request gets its own GIL
> When a thread makes a blocking syscall (network read, disk, `time.sleep`), CPython drops the GIL so other threads run during the wait. Since an I/O-bound workload spends most of its time waiting, those waits overlap and throughput rises. The GIL only blocks *Python bytecode* execution, not time spent parked in a syscall.

Q: A multithreaded program calls NumPy for heavy matrix math. Can it use multiple cores?
- [ ] No — all Python code is GIL-bound
- [x] Yes — GIL-aware C extensions like NumPy release the GIL around their compute-heavy C loops, so the parallel part runs in C with the lock dropped
- [ ] Only if you disable the GIL
- [ ] Only with ProcessPoolExecutor
> Libraries like NumPy, pandas, Pillow, and lxml release the GIL during their C-level number crunching, so multithreaded code calling them can genuinely parallelize across cores — an underappreciated escape hatch. The GIL is held only for pure-Python bytecode; work that happens inside a GIL-releasing C loop is exempt. Always check the library's docs for this behavior.
```

---

## Part 3 — Threading

Threads are the oldest and most familiar concurrency model: multiple lines of execution sharing one memory space. In Python, after Part 2, you know their precise niche — **I/O-bound work** — and their precise limitation — **no CPU parallelism**. This part is how to use them well and the traps of shared memory.

### The Model

The `threading` module gives you OS-level threads. They share the process's memory — globals, objects, module state — which is both their power (cheap communication, no serialization) and their danger (race conditions). They're preemptively scheduled: the OS can switch between them at *any* bytecode boundary (every ~5ms per the GIL switch interval), so you never control exactly when a switch happens.

```python
import threading

def worker(n, results):
    results[n] = n * n          # shared dict — works, but see "races" below

results = {}
threads = [threading.Thread(target=worker, args=(i, results)) for i in range(5)]
for t in threads: t.start()     # begin execution
for t in threads: t.join()      # wait for completion
print(results)
```

**Use threads for I/O-bound work** in an otherwise synchronous program: making several blocking network calls, reading many files, talking to a blocking database driver. The GIL releases during each wait, so the operations genuinely overlap.

### Races and Locks: The Cost of Shared Memory

Because threads share memory and the OS can switch between them mid-operation, **any shared mutable state is a hazard.** The classic example:

```python
counter = 0
def increment():
    global counter
    for _ in range(1_000_000):
        counter += 1            # NOT atomic: read counter, add 1, write back

# Two threads doing this concurrently: the final value is < 2_000_000,
# because both can read the same value before either writes back (a lost update).
```

`counter += 1` looks atomic but is three bytecode operations (load, add, store), and a thread switch between them loses an update. The fix is a **lock** (mutex), ensuring only one thread is in the critical section at a time:

```python
import threading
counter = 0
lock = threading.Lock()
def increment():
    global counter
    for _ in range(1_000_000):
        with lock:              # acquire on enter, release on exit
            counter += 1        # now atomic with respect to other threads
```

The synchronization toolkit:

- **`Lock`** — mutual exclusion; one holder at a time. The workhorse.
- **`RLock`** — reentrant lock; the same thread can acquire it multiple times (for recursive code).
- **`Semaphore(n)`** — allow up to `n` concurrent holders (bound concurrency to a resource).
- **`Event`** — a flag threads can wait on and set (signal "something happened").
- **`Condition`** — wait for a condition and be notified (producer/consumer, Part 8).
- **`queue.Queue`** — a **thread-safe** queue; the *preferred* way to pass data between threads, because it handles all the locking for you. Prefer a `Queue` over shared state + manual locks wherever possible.

The deeper point: **locks are correct but easy to get wrong** — too little locking gives races; too much gives deadlocks (two threads each waiting for a lock the other holds) and contention (threads serializing on a hot lock, erasing the concurrency you wanted). This fragility is a major reason `asyncio` (Part 6), which only switches at explicit `await` points, is attractive: between awaits, your code is atomic, so most of these races simply can't occur.

```quiz
Q: Two threads each run `counter += 1` a million times and the final value is less than 2,000,000. Why?
- [ ] Integer overflow
- [x] `counter += 1` is three bytecode ops (load, add, store), and a thread switch between load and store loses an update — a race on shared mutable state
- [ ] The GIL caps the counter
- [ ] Threads can't share globals
> Despite looking atomic, `+= 1` is load-add-store, and the OS can switch threads at any bytecode boundary. Both threads can read the same value before either writes back, so one increment is lost (a lost update). The fix is a `Lock` around the critical section so only one thread is in it at a time — the cost of sharing memory between preemptively-scheduled threads.

Q: Why does the guide recommend `queue.Queue` over shared state plus manual locks for passing data between threads?
- [ ] Queues are faster than locks
- [x] `queue.Queue` is thread-safe and handles all the locking internally, removing whole classes of race/deadlock bugs you'd risk hand-rolling
- [ ] Queues bypass the GIL
- [ ] Locks don't work across threads
> A `Queue` encapsulates the synchronization, so producers and consumers hand off data without you writing (and getting wrong) the locking. Manual locks are correct but fragile — too little gives races, too much gives deadlocks and contention. Preferring the queue moves that fragility into well-tested library code.

Q: When should you create a raw `threading.Thread` rather than use a `ThreadPoolExecutor`?
- [ ] Always — pools are slower
- [x] For a long-lived background/daemon thread doing periodic work, or when you need fine control over a specific thread; the pool is for "run these tasks concurrently"
- [ ] Never — raw threads are deprecated
- [ ] Only for CPU-bound work
> A `ThreadPoolExecutor` manages thread lifecycle, caps concurrency, and returns results/exceptions through `Future`s, so it's the right tool for running a batch of tasks. A raw `Thread` is for the cases a pool doesn't fit: a persistent daemon doing periodic work, or fine-grained control of one specific thread. Reach for the pool by default.
```

### Prefer the Pool to Raw Threads

You will rarely create `threading.Thread` objects directly in production code. The `ThreadPoolExecutor` from `concurrent.futures` (Part 5) is better for almost everything: it manages the thread lifecycle, caps concurrency, hands results and exceptions back through `Future` objects, and cleans up automatically. Raw `threading` is for when you need a long-lived background thread (a daemon doing periodic work) or fine control over a specific thread; the pool is for "run these tasks concurrently."

### `threading.local` and Daemon Threads

Two details worth knowing:

- **`threading.local()`** gives each thread its own copy of an attribute — useful for per-thread state like a database connection, avoiding sharing (and thus avoiding locks).
- **Daemon threads** (`Thread(..., daemon=True)`) are background threads that *don't* block the program from exiting — when the main thread finishes, daemons are killed abruptly (no cleanup). Use them for fire-and-forget background work, but never for anything that must finish cleanly (it may be cut off mid-write).

If you remember one thing from Part 3: **threads are for I/O-bound work in synchronous code, they share memory (so guard mutable shared state with a `Lock`, or better, pass data through a thread-safe `queue.Queue`), and you should almost always use a `ThreadPoolExecutor` rather than raw `Thread` objects.**

---

## Part 4 — Multiprocessing

When the work is CPU-bound, the GIL (Part 2) makes threads useless for parallelism — so you reach for **processes**. Each Python process is a separate interpreter with its own memory and its own GIL, so processes run Python bytecode *genuinely in parallel* across cores. This is the only built-in way to make pure-Python computation use more than one core.

### The Model and Its Cost

`multiprocessing` spawns separate OS processes. The upside is real parallelism; the costs are the things that distinguish it sharply from threading, and you must design around them:

- **No shared memory by default.** Each process has its own address space. Data passed between processes must be **serialized** (pickled), sent over a pipe, and deserialized on the other side. This is far more expensive than threads sharing a pointer.
- **Arguments and return values must be picklable.** Lambdas, local functions, open file handles, and many other objects can't be pickled and will raise errors. Top-level functions and plain data work.
- **Spawn overhead.** Creating a process is much heavier than creating a thread (a new interpreter, re-imported modules). You amortize this with a *pool* (below), not by spawning per task.

```python
from multiprocessing import Process, Queue

def worker(n, q):
    q.put(n * n)                # results go back via a queue (pickled across the boundary)

if __name__ == "__main__":       # REQUIRED on spawn platforms — see start methods
    q = Queue()
    procs = [Process(target=worker, args=(i, q)) for i in range(4)]
    for p in procs: p.start()
    for p in procs: p.join()
    print([q.get() for _ in procs])
```

### Start Methods: fork vs spawn vs forkserver (The Big Gotcha)

How a child process is created differs by platform and is a frequent source of baffling bugs:

- **`fork`** (default on Linux historically) — the child is a near-instant copy of the parent's entire memory. Fast, and the child inherits everything (open files, locks, module state). The danger: forking a *multithreaded* process can deadlock (a lock held by a thread that doesn't exist in the child), and inherited state causes subtle bugs. Because of this, **Python 3.14 changes the default away from `fork`** on Linux toward the safer `forkserver`.
- **`spawn`** (default on macOS and Windows) — the child starts a fresh interpreter and re-imports your module. Safe and clean, but slower, and it means **module-level code runs again in the child** — which is exactly why the `if __name__ == "__main__":` guard is mandatory: without it, the child re-runs your process-spawning code and you get an infinite explosion of processes.
- **`forkserver`** — a small server process is forked once at start; children are forked from *it* (a clean, single-threaded template). Combines fork's speed with spawn's safety; becoming the recommended default.

Set it explicitly for portability:

```python
import multiprocessing as mp
if __name__ == "__main__":
    mp.set_start_method("spawn")     # or "forkserver" — be explicit, don't rely on the platform default
```

The practical rule: **always write the `if __name__ == "__main__":` guard**, and assume `spawn`/`forkserver` semantics (re-imported module, everything must be picklable) so your code is portable and future-proof.

### Sharing Data Between Processes

Since there's no shared memory, you have a few options, in rough order of preference:

- **Return values via a pool** (Part 5) — the cleanest: `pool.map(fn, items)` handles the pickling and collection for you. Prefer this.
- **`multiprocessing.Queue` / `Pipe`** — explicit message passing between processes.
- **`multiprocessing.shared_memory`** (3.8+) — a genuine shared memory block for large data (e.g., a big NumPy array) you don't want to copy. The fast path for big numeric payloads, avoiding pickle entirely.
- **`Manager`** — a server process that hosts shared objects (`list`, `dict`) accessible to all processes via proxies. Convenient but slow (every access is a round-trip); use sparingly.

The cost of moving data is the thing that decides whether multiprocessing pays off: if each task does a lot of computation on a little data, processes win big. If each task does a little computation on a lot of data, the pickling/copying overhead can eat the entire benefit. **Coarse-grained tasks (lots of compute per chunk) are what multiprocessing is for.**

```quiz
Q: Why do processes achieve true CPU parallelism where threads can't?
- [ ] Processes ignore the GIL entirely as a feature flag
- [x] Each process is a separate interpreter with its own GIL and memory, so they run Python bytecode genuinely in parallel across cores
- [ ] Processes are scheduled cooperatively
- [ ] Processes share memory more efficiently
> A single process's GIL serializes its threads, but separate processes each have their own interpreter and GIL, so nothing forces them to take turns — they execute on different cores simultaneously. That's the only built-in way to make pure-Python computation use more than one core, at the cost of no shared memory and pickle-based communication.

Q: On `spawn`/`forkserver` platforms, why is the `if __name__ == "__main__":` guard mandatory?
- [ ] It improves performance
- [x] The child starts a fresh interpreter and re-imports your module, so without the guard the child re-runs your process-spawning code, exploding into infinite processes
- [ ] It picks the start method automatically
- [ ] It's only needed for threads
> Unlike `fork` (which copies the parent's memory), `spawn`/`forkserver` children re-import the module to set up. Module-level code that creates processes would therefore run again in each child, recursively spawning more — a fork bomb. The guard ensures the spawning code runs only when the module is executed as the main program, not on re-import.

Q: When does multiprocessing pay off versus when does its overhead eat the benefit?
- [ ] It always wins for any workload
- [x] Coarse-grained tasks (lots of compute per chunk, little data) win big; little compute on lots of data loses to pickling/copying overhead
- [ ] It's best for I/O-bound work
- [ ] Smaller tasks are always better
> Because there's no shared memory, every argument and result is pickled, sent over a pipe, and unpickled — expensive. If a task crunches heavily on a small input, that compute dwarfs the transfer cost and processes parallelize beautifully. If it barely computes but moves large data, the serialization can consume the entire benefit (or worse). Multiprocessing is for coarse-grained, compute-heavy chunks; `shared_memory` helps when big numeric payloads must cross the boundary.
```

### When Native Libraries Beat Multiprocessing

A crucial alternative from Part 2: if your CPU-bound work is numerical, a **GIL-releasing native library is often better than multiprocessing.** NumPy, pandas, Polars, PyTorch, and scikit-learn do their heavy loops in C/C++/Rust with the GIL released, so they already use multiple cores (or can, with threads) *without* the pickling and spawn overhead of separate processes. The decision: for *your own* pure-Python CPU loops, use multiprocessing; for *array/dataframe/tensor* math, let the native library parallelize and skip multiprocessing entirely. (The [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md) covers vectorization in depth.)

If you remember one thing from Part 4: **processes give true CPU parallelism because each has its own GIL, at the cost of no shared memory (everything is pickled and copied) and spawn overhead — so use them for coarse-grained, compute-heavy pure-Python work via a pool, always write the `__main__` guard, and reach for a GIL-releasing native library instead when the work is numerical.**

## Part 5 — concurrent.futures: The Unifying Layer

Parts 3 and 4 showed the low-level `threading` and `multiprocessing` modules. In practice you rarely touch them directly — you use **`concurrent.futures`**, the high-level layer that unifies threads and processes behind one clean API. It's the right default for "run these tasks concurrently and collect the results," and learning it once gives you both models.

### One API, Two Backends

The module gives you two executors with an **identical interface** — swap one for the other by changing a single line:

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# I/O-bound → threads:
with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(fetch_url, urls))

# CPU-bound → processes. SAME API, just a different executor:
with ProcessPoolExecutor() as pool:
    results = list(pool.map(heavy_compute, datasets))
```

This symmetry is the module's great virtue: you make the I/O-vs-CPU decision from Part 1, pick the matching executor, and the rest of your code is the same. The `with` block guarantees cleanup — it calls `shutdown(wait=True)` on exit, blocking until all submitted work finishes.

### `submit` vs `map`

Two ways to hand work to an executor:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# map: apply one function over an iterable; results come back in INPUT order.
with ThreadPoolExecutor(max_workers=10) as pool:
    for result in pool.map(fetch, urls):       # yielded in the order of `urls`
        handle(result)

# submit + as_completed: a Future per task; handle results as they FINISH.
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(fetch, url): url for url in urls}
    for fut in as_completed(futures):          # COMPLETION order, not submission order
        url = futures[fut]
        try:
            handle(fut.result())               # the exception (if any) re-raises HERE
        except Exception as e:
            log.warning("failed %s: %r", url, e)
```

Use **`map`** for the simple "apply this to everything, I want the results in order" case. Use **`submit` + `as_completed`** when you want per-task error handling, or to act on whichever task finishes first rather than waiting for the slow ones in order.

### The Future Object

Both `submit` and `map` are built on the **`Future`** — an object representing a result that will exist eventually (the same concept as a JavaScript Promise; see the [Python vs Node async guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md)). A `Future` lets you:

- `fut.result(timeout=None)` — block until done and return the value (or **re-raise the task's exception**).
- `fut.done()` / `fut.running()` — check state without blocking.
- `fut.add_done_callback(fn)` — run `fn` when it completes.
- `fut.cancel()` — cancel **only if it hasn't started running yet** (you cannot interrupt a task already executing in a thread — a hard limitation).

### The Exception Trap

The single most important `concurrent.futures` gotcha: **a task that raises does not crash the pool — the exception is stored on its `Future` and only surfaces when you call `.result()`** (or when `map`'s iterator reaches that item). If you submit work and never retrieve the results, **exceptions vanish silently** — your tasks fail and you never know. Always retrieve results, even if only to log failures:

```python
# WRONG — exceptions are silently swallowed:
for url in urls:
    pool.submit(process, url)        # fire and forget → errors lost forever

# RIGHT — retrieve results so exceptions surface:
futures = [pool.submit(process, url) for url in urls]
for fut in as_completed(futures):
    try:
        fut.result()                 # raises here if the task failed
    except Exception as e:
        log.error("task failed: %r", e)
```

```quiz
Q: Why is `concurrent.futures` the recommended default over the low-level `threading`/`multiprocessing` modules?
- [ ] It's the only one that releases the GIL
- [x] It unifies threads and processes behind one identical executor API, so you pick the backend matching your I/O-vs-CPU classification and the rest of the code is the same
- [ ] It runs faster than both
- [ ] It removes the need for the `__main__` guard
> `ThreadPoolExecutor` and `ProcessPoolExecutor` share the same interface, so swapping I/O-bound for CPU-bound is a one-line change. It manages worker lifecycle, returns results/exceptions through `Future`s, and the `with` block guarantees cleanup. You make the Part 1 classification, pick the executor, and write the same `submit`/`map` code either way.

Q: When should you use `submit` + `as_completed` instead of `map`?
- [ ] When you want results in input order
- [x] When you want per-task error handling or to act on whichever task finishes first; `map` returns results in input order, `as_completed` yields them in completion order
- [ ] map can't handle exceptions at all
- [ ] as_completed is faster
> `pool.map(fn, items)` is the simple "apply to everything, results in input order" case. `submit` returns a `Future` per task and `as_completed` yields them as they finish, letting you handle each result (and its exception) the moment it's ready and respond to the fastest first rather than blocking on a slow item earlier in the list.

Q: You `pool.submit(process, url)` for many URLs but never retrieve the results. A few tasks raise exceptions. What happens?
- [ ] The pool crashes and reports the errors
- [x] The exceptions are stored on the Futures and surface only on `.result()` — never retrieving means they vanish silently and you never learn the tasks failed
- [ ] Exceptions always print to stderr
- [ ] The tasks are automatically retried
> A task that raises doesn't crash the pool; the exception is captured on its `Future` and only re-raised when you call `.result()` (or when `map`'s iterator reaches that item). Fire-and-forget submission therefore swallows failures silently. Always retrieve every result — even just to log it — so errors surface instead of disappearing.
```

### Sizing the Pool

- **`ThreadPoolExecutor`** defaults to `min(32, os.cpu_count() + 4)` — tuned for I/O. For I/O-bound work you can often go higher (threads spend most of their time blocked), but the practical ceiling is in the **hundreds**, not thousands — each thread costs stack memory and context-switching. Size to your real I/O concurrency *and the downstream's limits* (don't open 500 connections to an API that allows 10).
- **`ProcessPoolExecutor`** defaults to `os.cpu_count()` workers — right for CPU-bound work, where more processes than cores just adds context-switching with no gain. The `chunksize` parameter to `map` matters for many small tasks: it batches items per IPC message, cutting per-task pickling overhead (e.g., `pool.map(fn, items, chunksize=100)`).

If you remember one thing from Part 5: **`concurrent.futures` is your default concurrency API — `ThreadPoolExecutor` for I/O, `ProcessPoolExecutor` for CPU, identical interface, `map` for ordered results and `submit`+`as_completed` for per-task handling — and you must always retrieve `.result()` or exceptions disappear silently.**

---

## Part 6 — asyncio: The Survey

`asyncio` is Python's framework for **cooperative concurrency**: a single thread, one event loop, juggling thousands of I/O operations with near-zero overhead per task. This part is the *survey* — enough to understand what it is, when to choose it, and how it differs from threads. The **depth-first treatment** — the event loop internals, structured concurrency in detail, `aiohttp` client and server, and async performance tuning — lives in the companion [Asyncio & aiohttp guide](ASYNCIO_STUDY_GUIDE.md). This section gets you to the decision; that guide gets you to mastery.

### The Core Idea: Cooperative Single-Threaded Concurrency

Where threads are *preemptively* scheduled (the OS switches them at any point, Part 3), coroutines are *cooperatively* scheduled: a coroutine runs **uninterrupted until it voluntarily yields** at an `await`. One thread, one event loop, and the loop runs whichever coroutine is ready while the others wait on their I/O.

```python
import asyncio

async def worker(n):
    await asyncio.sleep(1)          # yields control here; other workers run during this wait
    return n * 2

async def main():
    async with asyncio.TaskGroup() as tg:        # structured concurrency (3.11+)
        tasks = [tg.create_task(worker(i)) for i in range(1000)]
    print([t.result() for t in tasks])

asyncio.run(main())                  # all 1000 "run" in ~1 second on ONE thread
```

A thousand coroutines, one thread, finishing in ~1 second — because all thousand `sleep`s overlap. Doing this with a thousand threads would exhaust memory; with coroutines it's trivial, because each coroutine costs ~kilobytes, not the ~megabytes of a thread's stack.

### Two Consequences Worth Internalizing

The cooperative model produces two defining properties:

1. **Between `await` points, your code is atomic.** No other coroutine can run, because control only switches at `await`. This means **most of the race conditions that plague threading (Part 3) simply can't happen** — you rarely need locks for in-memory state. This is a real correctness advantage over threads.
2. **One blocking call freezes *everything*.** Because it's a single thread, a coroutine that doesn't yield — a CPU-bound computation, or a *blocking* I/O call like `requests.get` or `time.sleep` — stalls the entire event loop, and every other coroutine hangs until it returns. This is the cardinal sin of asyncio:

```python
# CATASTROPHE: blocks the whole event loop for the entire HTTP round-trip.
async def handler():
    data = requests.get(url)         # ❌ blocking call — every other coroutine freezes

# CORRECT: use an async-native library...
async def handler():
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as resp:    # ✓ yields during the wait
            data = await resp.text()

# ...or offload the unavoidable blocking call to a thread:
async def handler():
    data = await asyncio.to_thread(requests.get, url)   # ✓ runs in a thread, loop keeps going
```

### Key Primitives

The vocabulary (each covered deeply in the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md)):

- **`async def` / `await`** — define a coroutine; await another coroutine or awaitable.
- **`asyncio.run(coro)`** — the top-level entry point that starts the loop.
- **`asyncio.TaskGroup`** (3.11+) — structured concurrency: run tasks concurrently with automatic cancellation-on-failure and clean error grouping. The modern default; prefer it over `gather`.
- **`asyncio.gather(*coros)`** — run coroutines concurrently and collect results (the older tool).
- **`asyncio.to_thread(fn, *args)`** (3.9+) — offload a blocking call to a thread pool so it doesn't freeze the loop. The bridge between async and the blocking world.
- **`asyncio.Queue`, `Lock`, `Semaphore`, `Event`** — async coordination primitives (Part 8).
- **`asyncio.timeout()`** (3.11+) — a context manager that cancels work that runs too long.

### The Ecosystem Tax (Async Is Viral)

The catch that the [Python vs Node async guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) covers in depth: choosing asyncio means choosing **async-native libraries** for all your I/O. `requests` → `aiohttp`/`httpx`; `psycopg2` → `asyncpg`; the synchronous Redis client → its async variant. A single blocking library in your async code silently serializes everything. And async is **viral** — `await` requires an `async` caller, all the way up the stack ("async all the way down"). This contagion, plus the need to re-select your dependency stack, is the real cost of asyncio, and it's why threads remain the better choice when a blocking library has no async port or your codebase is already synchronous.

Worth knowing alongside `asyncio`: **`httpx`** (HTTP client with both sync and async APIs), **`uvloop`** (a drop-in faster event loop built on libuv — the same engine as Node.js, 2–4× faster), **`Trio`** and **`AnyIO`** (alternative/abstraction async frameworks), and **`aiofiles`** (async file I/O, since real file I/O is blocking).

If you remember one thing from Part 6: **asyncio is single-threaded cooperative concurrency — thousands of coroutines on one thread, atomic between `await`s (so few races), but one blocking call freezes the whole loop, and it requires async-native libraries throughout. Use it for high-concurrency I/O; read the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md) to master it.**

---

## Part 7 — Choosing a Model

This is the part the whole guide exists to serve. You've seen each model; now decide. The good news from Part 1: get the I/O-vs-CPU classification right and the choice is nearly made. The remaining nuance is the genuine fork — *for I/O-bound work, threads or async?* — which this part settles.

### The Decision Tree

```text
Is the work CPU-bound or I/O-bound?  (watch a CPU monitor; profile if unsure)
│
├── CPU-BOUND (cores are the bottleneck)
│   │
│   ├── Is it numerical (arrays, dataframes, tensors)?
│   │   └── YES → use a GIL-releasing native library (NumPy/Polars/PyTorch);
│   │            it already parallelizes. No multiprocessing needed.
│   │   └── NO (your own pure-Python compute) → ProcessPoolExecutor / multiprocessing
│   │
│   └── Need many cores on free-threaded Python 3.13+? → threads may now work (Part 9)
│
└── I/O-BOUND (waiting is the bottleneck)
    │
    ├── Do async-native libraries exist AND do you need high concurrency (1000s)?
    │   └── YES → asyncio + aiohttp/httpx/asyncpg
    │
    ├── Is your library blocking, or is the codebase synchronous,
    │   or is concurrency modest (dozens–hundreds)?
    │   └── YES → ThreadPoolExecutor
    │
    └── Both at once (mostly async, a few blocking calls)?
        └── asyncio + asyncio.to_thread() for the blocking parts
```

### The Real Fork: ThreadPoolExecutor vs asyncio

For I/O-bound work, both threads and async overlap the waiting and neither gives CPU parallelism (the GIL applies to both). The difference is *how* they interleave, and that drives the choice:

| | ThreadPoolExecutor | asyncio |
|---|---|---|
| Concurrency unit | OS thread | coroutine |
| Switching | preemptive (OS, at any bytecode) | cooperative (only at `await`) |
| Overhead per unit | ~MBs of stack + context switch | ~KBs, very cheap |
| Practical ceiling | hundreds of threads | tens of thousands of coroutines |
| Works with *blocking* libraries | **yes — that's the point** | no — they freeze the loop |
| Needs *async-native* libraries | no | **yes** (`aiohttp`, `asyncpg`, …) |
| Mental model | plain functions + futures | `async`/`await` + event loop |
| Shared-state races | need locks (can switch anywhere) | rare (switch only at `await`) |

**Reach for `ThreadPoolExecutor` when:**

- **Your I/O library is blocking and has no async version.** The deciding factor most of the time — wrap the calls in a thread pool, no rewrite. A sync-only vendor SDK, a driver with no async port, `requests` in legacy code.
- **Your codebase is synchronous.** async is viral; a thread pool drops into existing sync code with no restructuring.
- **Concurrency is modest** — dozens to a few hundred operations. Threads handle that comfortably and the code is simpler.
- **You want the simplest thing that works.** `with ThreadPoolExecutor() as pool: pool.map(fn, items)` is two lines and no new concepts.

**Reach for `asyncio` when:**

- **You need very high concurrency** — thousands to tens of thousands of simultaneous connections (a crawler hitting 10k hosts, a server holding many WebSockets). Threads fall over here on memory; coroutines don't. See the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md).
- **Async-native libraries exist for your I/O** — `aiohttp`/`httpx`, `asyncpg`, async Redis. The ecosystem is there, so you scale without fighting blocking calls.
- **You're already in an async stack** — FastAPI, aiohttp, an existing event loop. Use the native model.
- **You want fine-grained control** — structured concurrency (`TaskGroup`), precise cancellation and timeouts, backpressure via bounded queues.

### They're Not Either/Or

asyncio uses a thread pool internally for exactly the "blocking library inside an async program" case. `asyncio.to_thread(fn, *args)` pushes a blocking call onto a thread so it doesn't stall the loop. So a common real-world shape is **async for the I/O that has async libraries, plus a thread pool for the few blocking calls that don't** — and `loop.run_in_executor` can even push CPU work to a *process* pool from within an async app.

### The One-Line Heuristics

- **CPU-bound?** → processes (or a native library if numerical). Never threads, never async.
- **I/O-bound, async library exists, high concurrency?** → asyncio.
- **I/O-bound otherwise** (blocking library, sync codebase, modest scale)? → ThreadPoolExecutor.
- **Unsure if it's even your bottleneck?** → profile first. The right model depends on the *measured* bottleneck, not a guess.

If you remember one thing from Part 7: **classify I/O vs CPU (that's most of the decision), then for I/O-bound work choose asyncio when async libraries exist and you need scale, otherwise a ThreadPoolExecutor — and for CPU-bound work use processes, or a GIL-releasing native library if the work is numerical.**

```quiz
Q: Your work is CPU-bound and numerical (large array operations). What's the recommended model?
- [ ] ProcessPoolExecutor over hand-written loops
- [x] A GIL-releasing native library (NumPy/Polars/PyTorch) — it already parallelizes in C, so no multiprocessing is needed
- [ ] asyncio with to_thread
- [ ] Raw threads
> For numerical CPU work, libraries like NumPy/Polars/PyTorch run their heavy loops in C and release the GIL, so they already use multiple cores — reaching for multiprocessing on top adds pickling overhead for no benefit. Multiprocessing is the answer for your *own* pure-Python compute that no native library covers.

Q: Both threads and asyncio overlap I/O waiting without CPU parallelism. So what's the deciding factor between them?
- [ ] asyncio is always faster
- [x] Library and scale: asyncio needs async-native libraries but scales to tens of thousands of coroutines; a ThreadPoolExecutor works with blocking libraries and slots into sync code but tops out in the hundreds
- [ ] Threads give CPU parallelism, async doesn't
- [ ] They're identical in every way
> Neither beats the GIL, so the choice turns on ecosystem and concurrency level. asyncio requires `aiohttp`/`asyncpg`-style async libraries and is viral up the call stack, but handles 10k+ connections cheaply. A thread pool drops into existing synchronous code and works with blocking libraries unchanged, at the cost of a few-hundred ceiling. Blocking library or modest scale → threads; async libraries and high concurrency → asyncio.

Q: You have a mostly-async app but must call one blocking, sync-only library. What's the idiomatic approach?
- [ ] Rewrite the whole app to use threads
- [x] Stay async and push the blocking call through `asyncio.to_thread()` so it runs in a thread pool without freezing the loop
- [ ] Call it directly inside a coroutine
- [ ] Move the whole app to multiprocessing
> The models aren't either/or: `asyncio.to_thread(fn, *args)` offloads a blocking call onto a thread so the event loop keeps serving other coroutines. Calling the blocking library directly in a coroutine would stall the entire loop (the cardinal sin). This async-plus-thread-pool shape — and `run_in_executor` to a process pool for CPU work — is the common real-world hybrid.
```

---

## Part 8 — Concurrency Patterns

The models are tools; these are the *shapes* you build with them. The same handful of patterns recur across threads, processes, and async — the API differs, the structure is identical. Recognizing them is what turns "I know the models" into "I can design concurrent programs."

### Bounded Concurrency (Don't Fan Out Unbounded)

The most common real-world need and the most common mistake. Launching one task per item — 10,000 URLs, 10,000 concurrent requests — overwhelms the target, exhausts file descriptors, and gets you rate-limited. **Bound the concurrency** to a fixed number in flight:

```python
# Threads: the pool's max_workers IS the bound.
with ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(fetch, urls))    # at most 20 concurrent

# asyncio: a Semaphore is the bound.
sem = asyncio.Semaphore(20)
async def bounded_fetch(url):
    async with sem:                          # at most 20 coroutines past this point
        return await fetch(url)
results = await asyncio.gather(*(bounded_fetch(u) for u in urls))
```

The bound should match the *downstream's* capacity (the API's rate limit, the database's connection pool size), not your ambition. This is the single most important production pattern — see the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md) for the async version in depth.

### Producer/Consumer (The Queue Pattern)

Decouple work generation from work processing with a **queue**: producers put items in, consumers take them out, and the queue absorbs the rate mismatch (backpressure). It's the same shape in every model:

```python
# Threads: queue.Queue is thread-safe — no manual locking needed.
import queue, threading
q = queue.Queue(maxsize=100)             # bounded: producers block when full (backpressure)
def producer():
    for item in source(): q.put(item)
def consumer():
    while (item := q.get()) is not None:
        process(item); q.task_done()

# asyncio: asyncio.Queue, same idea, awaitable.
q = asyncio.Queue(maxsize=100)
async def producer():
    async for item in source(): await q.put(item)
async def consumer():
    while True:
        item = await q.get(); process(item); q.task_done()
```

The **bounded** queue (`maxsize`) is what gives you backpressure: when consumers fall behind, the queue fills, and producers *block* rather than building an unbounded backlog that exhausts memory. This is the in-process version of the messaging patterns in the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md).

### Fan-Out / Fan-In

Split work across workers (fan-out), then collect and combine the results (fan-in). This is what `pool.map` and `asyncio.gather` *are* — the pattern is so common the libraries bake it in:

```python
# Fan-out to processes, fan-in the results — CPU-bound map-reduce.
with ProcessPoolExecutor() as pool:
    partial_results = pool.map(process_chunk, chunks)   # fan-out
total = combine(partial_results)                         # fan-in
```

### The Pipeline

Chain stages, each doing one transformation, connected by queues — stage 1 feeds stage 2 feeds stage 3, each running concurrently. This lets a slow stage be scaled independently (more workers on the bottleneck stage) and keeps data flowing rather than processing in batches. It's the in-memory cousin of the streaming ETL pipelines in the [Data Engineering guide](DATA_ENGINEERING_STUDY_GUIDE.md), and generators are often the simplest way to express the lazy version (the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md) covers generator pipelines).

### Timeouts and Cancellation

Never wait forever on an external operation. Each model has its tool:

```python
# Futures: timeout on result retrieval.
try:
    result = fut.result(timeout=5.0)
except TimeoutError:
    ...                                  # note: the task keeps running; you just stop waiting

# asyncio: timeout that actually CANCELS the work (3.11+).
async with asyncio.timeout(5.0):
    await long_operation()               # cancelled if it exceeds 5s
```

A real difference worth noting (and the [Python vs Node guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) explores): asyncio's `timeout` *cancels* the underlying coroutine (first-class cancellation), while a thread's `future.result(timeout=...)` only stops *you* from waiting — the thread keeps running, because you cannot safely interrupt a running thread in Python. This is a genuine advantage of async for timeout-heavy work.

If you remember one thing from Part 8: **the patterns are model-independent — bound your concurrency (the #1 production rule), use queues for producer/consumer with backpressure, fan-out/fan-in for map-reduce, pipelines for staged work, and always set timeouts — and the same shape works whether you build it with threads, processes, or coroutines.**

---

## Part 9 — The Future: Free-Threading & Sub-Interpreters

The GIL (Part 2) has defined Python concurrency for thirty years, and as of 2026 that's actively changing. Two developments are reshaping the landscape, and while neither is the default yet, both will affect how you make these decisions over the next few years.

### Free-Threaded CPython (PEP 703)

Since **Python 3.13**, CPython ships an experimental **free-threaded build** (sometimes called "nogil") that **removes the GIL entirely.** In this build, threads execute Python bytecode *truly in parallel* across cores — the thing Part 2 said was impossible becomes possible. CPU-bound multithreading would finally scale, and the "use processes for CPU parallelism" rule would relax to "use threads."

The status and the caveats, as of 2026:

- It's **opt-in** — a separate build (`python3.13t`), not the default interpreter. By 3.14 it's more mature but still not the standard build.
- It carries a **single-threaded performance cost** (historically ~5–10%) because removing the GIL meant adding finer-grained locking and changing reference counting (biased/deferred refcounting). That overhead is shrinking with each release but isn't zero.
- **C extensions must be made compatible.** Many popular packages have added free-threaded support, but the ecosystem isn't fully there — a single incompatible extension can force the GIL back on or fail to load.
- The threading **race conditions** of Part 3 become *more* dangerous, not less: with true parallelism, data races that the GIL accidentally papered over (by serializing bytecode) can now actually manifest. Free-threaded code needs *more* disciplined locking, not less.

The practical stance: **design for today's GIL** (the rules in Parts 2–7 hold for the default build), **but watch this transition** — test your CPU-bound workloads on the free-threaded build, because the day it becomes default-and-fast, the threads-vs-processes calculus flips.

### Sub-Interpreters (PEP 684 & PEP 734)

A second, complementary path to parallelism within one process. **Per-interpreter GIL** (PEP 684, Python 3.12) gives each *sub-interpreter* its own GIL, so multiple sub-interpreters in one process can run Python bytecode in parallel — combining process-like isolation with thread-like (lower) overhead, since they share the process but not the interpreter state. **PEP 734** (Python 3.13) adds a standard-library `interpreters` module to create and drive them from Python.

The model sits *between* threads and processes: more isolated than threads (each sub-interpreter has its own module state, so fewer shared-state races), but lighter than processes (no separate OS process, cheaper communication). It's early and the ergonomics are still maturing, but it's a promising third option for CPU parallelism that avoids both the GIL (unlike threads) and the spawn/pickle overhead (unlike processes).

### What This Means for Your Decisions

For now, **nothing changes in how you choose** — the default CPython you ship on has the GIL, so Parts 2–7 stand. But the direction is clear: Python is acquiring real in-process parallelism, by two routes at once. Over the next few years, expect the "processes for CPU work" rule to soften as free-threading matures and sub-interpreters stabilize. Keep an eye on your key C extensions' free-threading support — that ecosystem readiness, more than the interpreter itself, is what will gate the transition.

If you remember one thing from Part 9: **the GIL is on its way out — free-threaded CPython (3.13+, opt-in) makes threads parallelize CPU work, and per-interpreter GILs add a third parallelism option between threads and processes — but both are still maturing, so design for the GIL today while testing the free-threaded build for your CPU-bound code.**

---

## Part 10 — Recipes & Pitfalls

The payoff — copy-paste-ready patterns for the common cases, and the mistakes that cost the most debugging time.

### Recipe 1: Parallel I/O with a Thread Pool

The everyday "fetch many things over the network" — blocking library, modest concurrency:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

def fetch(url):
    return url, requests.get(url, timeout=10).status_code

def fetch_all(urls, workers=20):
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, u): u for u in urls}
        for fut in as_completed(futures):
            try:
                url, status = fut.result()
                results[url] = status
            except Exception as e:
                results[futures[fut]] = f"error: {e}"   # never let one failure abort the batch
    return results
```

### Recipe 2: CPU Parallelism with a Process Pool

Coarse-grained, compute-heavy, pure-Python work across all cores:

```python
from concurrent.futures import ProcessPoolExecutor

def process_chunk(chunk):
    return sum(expensive_transform(x) for x in chunk)   # heavy compute per chunk

def parallel_sum(data, chunk_size=10_000):
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    with ProcessPoolExecutor() as pool:
        return sum(pool.map(process_chunk, chunks, chunksize=4))

if __name__ == "__main__":            # REQUIRED — spawn/forkserver re-imports the module
    print(parallel_sum(big_list))
```

### Recipe 3: High-Concurrency Async I/O

Thousands of requests, async-native library, bounded:

```python
import asyncio, httpx

async def fetch_all(urls, concurrency=50):
    sem = asyncio.Semaphore(concurrency)             # bound in-flight requests
    async with httpx.AsyncClient(timeout=10) as client:
        async def fetch(url):
            async with sem:
                r = await client.get(url)
                return url, r.status_code
        return await asyncio.gather(*(fetch(u) for u in urls), return_exceptions=True)

results = asyncio.run(fetch_all(urls))
```

### Recipe 4: Blocking Call Inside Async Code

The bridge — a sync-only library in an async app, without freezing the loop:

```python
import asyncio

async def handler():
    # blocking_sdk has no async version → run it in a thread, loop keeps serving
    result = await asyncio.to_thread(blocking_sdk.query, params)
    return result
```

### Recipe 5: CPU Work From Within an Async App

When an async service occasionally needs to crunch — push it to a *process* pool so it doesn't block the loop *or* fight the GIL:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

pool = ProcessPoolExecutor()

async def handle_request(data):
    loop = asyncio.get_running_loop()
    # offload CPU-bound work to a separate process; await it without blocking the loop
    result = await loop.run_in_executor(pool, heavy_compute, data)
    return result
```

### The Pitfalls

The mistakes that recur, each tied to a part of this guide:

1. **Threads for CPU-bound work** (Part 2). The GIL serializes them; you get overhead with no speedup, often slower than sequential. → Use processes.
2. **Blocking the event loop** (Part 6). `requests`, `time.sleep`, a CPU loop, or any sync I/O inside a coroutine freezes *every* coroutine. → Async-native libraries, or `asyncio.to_thread`.
3. **Unbounded fan-out** (Part 8). One task per item against 10,000 items overwhelms the downstream and your own resources. → Bound with `max_workers` or a `Semaphore`.
4. **Forgetting `.result()`** (Part 5). Submitted-but-never-retrieved tasks swallow their exceptions silently — failures you never see. → Always retrieve results.
5. **Missing the `__main__` guard** (Part 4). On spawn/forkserver, the child re-imports your module; without the guard it re-runs your process-spawning code → infinite process explosion. → Always guard the entry point.
6. **Unpicklable arguments to processes** (Part 4). Lambdas, closures, open handles can't cross the process boundary. → Top-level functions and plain data only.
7. **Races in threaded shared state** (Part 3). `+=` and friends aren't atomic; concurrent access corrupts data. → A `Lock`, or pass data through a `queue.Queue`.
8. **Choosing a model before profiling** (Part 1). Optimizing the wrong bottleneck, or adding concurrency where the cost is elsewhere. → Measure first; classify I/O vs CPU from real data.

### The Decision, One More Time

```text
CPU-bound  → ProcessPoolExecutor   (or a GIL-releasing native library if numerical)
I/O-bound, high concurrency, async libs available  → asyncio + aiohttp/httpx
I/O-bound, blocking library or sync codebase or modest scale  → ThreadPoolExecutor
Mixed  → asyncio for the async I/O + to_thread / run_in_executor for the rest
Always → bound concurrency, set timeouts, retrieve results, profile first
```

If you remember one thing from Part 10: **the recipes are short because the models are well-designed — pick the executor that matches your I/O-vs-CPU classification, bound the concurrency, retrieve every result, and guard the `__main__` entry point — and most of the pitfalls are just the consequences of skipping the Part 1 classification.**

---

## Where to Go Next

- **Watch David Beazley's [GIL talks](https://www.dabeaz.com/GIL/)** — still the clearest explanation of the convoy effects and scheduling behavior Part 2 summarizes, and genuinely entertaining.
- **Read the stdlib docs as designed wholes:** [`concurrent.futures`](https://docs.python.org/3/library/concurrent.futures.html) (short, and the API you should default to), the [`multiprocessing` programming guidelines](https://docs.python.org/3/library/multiprocessing.html#programming-guidelines) (the official list of fork/pickle gotchas), and the [asyncio docs](https://docs.python.org/3/library/asyncio.html).
- **Track the GIL's endgame:** [PEP 703](https://peps.python.org/pep-0703/) (free-threading) and [PEP 684](https://peps.python.org/pep-0684/) (per-interpreter GIL) are the primary sources, and each release's [What's New](https://docs.python.org/3/whatsnew/) reports the current state.
- **Run the classification experiment.** Take a slow script, watch CPU usage while it runs, classify it I/O- or CPU-bound, then implement it twice — `ThreadPoolExecutor` and `ProcessPoolExecutor` — and time both. Seeing threads *lose* on CPU-bound work (and win on I/O) makes Part 2 permanent.
- **Siblings in this repo:** the [Asyncio & aiohttp guide](ASYNCIO_STUDY_GUIDE.md) (async at full depth), [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) (the runtime underneath), and [Python vs Node.js Async](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) (the comparison).

That's the guide. It's deliberately the *map* — the model picker — and it hands off to its siblings for depth: the [Asyncio & aiohttp guide](ASYNCIO_STUDY_GUIDE.md) for mastering async, the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md) for the runtime underneath, and the [Python vs Node.js async guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) for how Python's model compares. From here the highest-leverage next step is to take the slowest thing you've written, watch a CPU monitor while it runs to classify it I/O- or CPU-bound, and apply the one matching model from Part 7 — because in Python concurrency, that single classification is most of the battle, and everything else is detail on top of it.


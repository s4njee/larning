# Python Concurrency Guide

A practical overview of Python's concurrency models: when to use each, how they differ, and where to find the official documentation.

## Table of Contents
- [The Big Picture](#the-big-picture)
- [Threading](#threading)
- [ThreadPoolExecutor](#threadpoolexecutor)
- [Multiprocessing](#multiprocessing)
- [ProcessPoolExecutor](#processpoolexecutor)
- [concurrent.futures](#concurrentfutures)
- [asyncio](#asyncio)
- [aiohttp](#aiohttp)
- [Other Async Libraries](#other-async-libraries)
- [Choosing a Model](#choosing-a-model)

---

## The Big Picture

Python concurrency falls into three broad categories:

| Category | Parallelism? | Best For | Blocked by GIL? |
|---|---|---|---|
| **Threads** | Concurrent, not parallel (CPython) | I/O-bound work | Yes (released on I/O) |
| **Processes** | True parallelism | CPU-bound work | No (separate interpreters) |
| **Async (coroutines)** | Concurrent, single-threaded | Massive I/O concurrency | N/A (cooperative) |

> **Note on the GIL:** CPython's Global Interpreter Lock means only one thread executes Python bytecode at a time. Python 3.13+ ships an experimental free-threaded build (PEP 703) that removes this limitation. See [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html#free-threaded-cpython).

---

## Threading

The `threading` module provides OS-level threads that share memory. Good for I/O-bound workloads (network, disk) since Python releases the GIL during blocking I/O calls.

```python
import threading

def worker(n):
    print(f"worker {n}")

threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
for t in threads: t.start()
for t in threads: t.join()
```

**Pros:** Shared memory, low overhead per task, familiar model.
**Cons:** GIL prevents CPU parallelism; race conditions require locks.

Docs: [threading — Thread-based parallelism](https://docs.python.org/3/library/threading.html)

---

## ThreadPoolExecutor

A high-level thread pool from `concurrent.futures`. Prefer this over raw threads for most cases — cleaner API, built-in result handling, and context-manager lifecycle.

```python
from concurrent.futures import ThreadPoolExecutor

def fetch(url):
    ...

with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(fetch, urls))
```

**Use when:** You have many I/O-bound tasks and want a simple pool-based API.

Docs: [ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor)

---

## Multiprocessing

The `multiprocessing` module spawns separate Python processes, each with its own interpreter and memory space — bypassing the GIL entirely. Use for CPU-bound work (numeric computation, image processing, parsing).

```python
from multiprocessing import Process, Queue

def worker(q):
    q.put("done")

q = Queue()
p = Process(target=worker, args=(q,))
p.start(); p.join()
```

**Pros:** True parallelism across CPU cores.
**Cons:** Higher overhead, arguments must be picklable, no shared memory by default (use `multiprocessing.shared_memory` or `Queue`/`Pipe`).

Docs:
- [multiprocessing — Process-based parallelism](https://docs.python.org/3/library/multiprocessing.html)
- [multiprocessing.shared_memory](https://docs.python.org/3/library/multiprocessing.shared_memory.html)

---

## ProcessPoolExecutor

The process-based counterpart to `ThreadPoolExecutor`. Same API, but runs work in subprocesses. Ideal for CPU-bound map-style workloads.

```python
from concurrent.futures import ProcessPoolExecutor

def heavy(x):
    return sum(i*i for i in range(x))

with ProcessPoolExecutor() as pool:
    results = list(pool.map(heavy, [10_000_000] * 8))
```

**Gotcha:** On Windows/macOS the default start method is `spawn`, so the entry point must be guarded with `if __name__ == "__main__":`.

Docs: [ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)

---

## concurrent.futures

The unifying module that provides `ThreadPoolExecutor`, `ProcessPoolExecutor`, and the `Future` abstraction. Key methods:

- `executor.submit(fn, *args)` → returns a `Future`
- `executor.map(fn, iterable)` → lazy iterator of results
- `concurrent.futures.as_completed(futures)` → yields futures as they finish
- `concurrent.futures.wait(futures)` → block until done

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor() as pool:
    futures = {pool.submit(fetch, url): url for url in urls}
    for fut in as_completed(futures):
        url = futures[fut]
        print(url, fut.result())
```

Docs: [concurrent.futures — Launching parallel tasks](https://docs.python.org/3/library/concurrent.futures.html)

---

## asyncio

`asyncio` is Python's built-in framework for cooperative concurrency using coroutines, tasks, and an event loop. A single thread juggles thousands of I/O operations with near-zero overhead per task.

```python
import asyncio

async def worker(n):
    await asyncio.sleep(1)
    return n * 2

async def main():
    async with asyncio.TaskGroup() as tg:     # Python 3.11+
        tasks = [tg.create_task(worker(i)) for i in range(10)]
    print([t.result() for t in tasks])

asyncio.run(main())
```

**Key primitives:**
- `async def` / `await` — define and await coroutines
- `asyncio.run(coro)` — top-level entry point
- `asyncio.TaskGroup` — structured concurrency (3.11+)
- `asyncio.gather(*coros)` — run coroutines concurrently
- `asyncio.Queue`, `Lock`, `Semaphore`, `Event` — async sync primitives
- `asyncio.to_thread(fn, *args)` — offload blocking calls to a thread

**Rule:** Never call blocking functions directly in a coroutine — it stalls the entire event loop. Wrap them with `asyncio.to_thread` or a `run_in_executor` call.

Docs:
- [asyncio — Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
- [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html)
- [Streams](https://docs.python.org/3/library/asyncio-stream.html)
- [Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html)

---

## aiohttp

`aiohttp` is the de-facto asyncio HTTP client/server. It replaces `requests` in async code — `requests` is blocking and will freeze the event loop.

```python
import aiohttp, asyncio

async def fetch(session, url):
    async with session.get(url) as resp:
        return await resp.text()

async def main():
    async with aiohttp.ClientSession() as session:
        pages = await asyncio.gather(*(fetch(session, u) for u in urls))

asyncio.run(main())
```

**Tips:**
- Reuse a single `ClientSession` across requests (connection pooling).
- Use `asyncio.Semaphore` to cap concurrent requests.
- aiohttp also ships a server framework for building async web apps.

Docs:
- [aiohttp documentation](https://docs.aiohttp.org/en/stable/)
- [Client quickstart](https://docs.aiohttp.org/en/stable/client_quickstart.html)
- [Server quickstart](https://docs.aiohttp.org/en/stable/web_quickstart.html)

---

## Other Async Libraries

Worth knowing when `asyncio` alone isn't enough:

- **[httpx](https://www.python-httpx.org/)** — HTTP client with both sync and async APIs; `requests`-compatible interface.
- **[Trio](https://trio.readthedocs.io/en/stable/)** — alternative async framework emphasizing structured concurrency and usability.
- **[AnyIO](https://anyio.readthedocs.io/en/stable/)** — compatibility layer that runs on top of asyncio or Trio; used by FastAPI and Starlette.
- **[uvloop](https://uvloop.readthedocs.io/)** — drop-in replacement for the asyncio event loop, built on libuv, substantially faster.
- **[aiofiles](https://github.com/Tinche/aiofiles)** — async file I/O (real file I/O is blocking; this delegates to a thread pool).

---

## Choosing a Model

| Workload | Recommendation |
|---|---|
| A few blocking I/O calls | `ThreadPoolExecutor` |
| Thousands of network calls | `asyncio` + `aiohttp`/`httpx` |
| CPU-bound number crunching | `ProcessPoolExecutor` or `multiprocessing` |
| Mix of CPU and I/O | asyncio event loop + `run_in_executor` for CPU tasks |
| Need true multi-core threads | Python 3.13+ free-threaded build, or processes |
| Calling blocking code from async | `asyncio.to_thread(fn, ...)` |

### Rules of thumb
1. **I/O-bound → async or threads.** CPU-bound → processes.
2. **Don't mix sync blocking calls into async code.** Offload them.
3. **Prefer high-level APIs** (`concurrent.futures`, `asyncio.TaskGroup`) over raw threads and manual event-loop management.
4. **Measure before optimizing.** The right model depends on your actual bottleneck.

---

## Further Reading

- [Python HOWTO: Functional Programming with futures](https://docs.python.org/3/library/concurrent.futures.html)
- [PEP 3156 — Asynchronous IO Support (asyncio)](https://peps.python.org/pep-3156/)
- [PEP 492 — Coroutines with async and await syntax](https://peps.python.org/pep-0492/)
- [PEP 703 — Making the GIL Optional in CPython](https://peps.python.org/pep-0703/)
- [Real Python: Speed Up Your Python Program With Concurrency](https://realpython.com/python-concurrency/)

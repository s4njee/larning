# Advanced Node.js Study Guide

A depth-first guide to Node.js internals and high-performance patterns for engineers who already build production services with it. It assumes you write JavaScript/TypeScript daily, know the basics of Express/Fastify/Koa, and have used `async`/`await` — but it does **not** assume you understand what the event loop actually is (most explanations get it wrong), how V8 optimizes your code, or why your 32-core server is using one CPU.

The throughline is the same as the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md): **performance with understanding.** Every optimization here is motivated by a model of what the runtime is actually doing — V8's JIT compilation pipeline, libuv's event loop phases, the cost of a heap allocation versus a stack-allocated SMI — so you can reason about new situations instead of cargo-culting benchmark results. The closing recipe chapter is the payoff: profiled, production-grade patterns for making Node.js fast.

This guide has siblings that go deeper on adjacent ground: the [TypeScript guide](TYPESCRIPT_STUDY_GUIDE.md) (the type system), the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) (real-time with `ws` and Socket.IO on Node), the [Networking Fundamentals guide](NETWORKING_FUNDAMENTALS.md) (TCP, HTTP, load balancing), and the [Observability guide](OBSERVABILITY_STUDY_GUIDE.md) (tracing, metrics, SLOs).

Primary references: the [Node.js documentation](https://nodejs.org/docs/latest/api/), the [V8 blog](https://v8.dev/blog) (the authoritative source on JIT internals), the [libuv design overview](https://docs.libuv.org/en/v1.x/design.html), and Matteo Collina's [talks and modules](https://github.com/mcollina) — he's the closest thing Node.js performance has to a single canonical voice.

---

## Table of Contents

1. [Part 1 — The Runtime Model](#part-1--the-runtime-model)
2. [Part 2 — V8: How Your JavaScript Gets Fast](#part-2--v8-how-your-javascript-gets-fast)
3. [Part 3 — The Event Loop, Actually](#part-3--the-event-loop-actually)
4. [Part 4 — Async Patterns & Pitfalls](#part-4--async-patterns--pitfalls)
5. [Part 5 — Streams & Backpressure](#part-5--streams--backpressure)
6. [Part 6 — Worker Threads & Clustering](#part-6--worker-threads--clustering)
7. [Part 7 — Memory Management & GC Tuning](#part-7--memory-management--gc-tuning)
8. [Part 8 — Profiling & Measurement](#part-8--profiling--measurement)
9. [Part 9 — Performance Levers](#part-9--performance-levers)
10. [Part 10 — High-Performance Recipes](#part-10--high-performance-recipes)

---

## Part 1 — The Runtime Model

Before any optimization, get the architecture right. Node.js is not "JavaScript on the server" — it's a specific machine with specific parts, and knowing which part does what is what separates "it works" from "it works under load."

### The Three Pieces

Node.js is three things bolted together:

1. **V8** — Google's JavaScript engine (also in Chrome and Deno). It parses, compiles, and executes your JavaScript. It manages the **heap** (where objects live) and the **garbage collector.** It knows nothing about files, networks, or HTTP.
2. **libuv** — a C library that provides the **event loop**, a **thread pool** for blocking OS operations (filesystem, DNS, some crypto), and cross-platform async I/O primitives (epoll on Linux, kqueue on macOS, IOCP on Windows). It's what makes Node.js async.
3. **Node.js bindings and standard library** — the C++ glue that connects V8 to libuv and wraps OS capabilities into JavaScript APIs (`fs`, `net`, `http`, `crypto`, `child_process`, `worker_threads`).

The consequence: **your JavaScript runs on a single V8 thread, but I/O happens in the OS kernel (non-blocking) or on libuv's thread pool (for things the OS can't do async).** The event loop is the coordinator that dispatches JavaScript callbacks when I/O completes. That single-threaded execution is the defining constraint — and the defining strength.

### Single-Threaded Does Not Mean Single-Process

A common misconception. One Node process uses **one main thread** for JavaScript execution, but the process itself has more threads:

- The **main thread** — runs all your JS, the event loop, and microtask processing.
- The **libuv thread pool** (default: 4 threads, tunable via `UV_THREADPOOL_SIZE`, max 1024) — handles file-system operations (`fs.*`), DNS lookups (`dns.lookup`, not `dns.resolve`), `zlib` compression, `crypto.pbkdf2`/`crypto.randomBytes`, and anything explicitly offloaded. These are the "blocking" calls that Node makes async by running them on a background thread and calling back to the main thread when done.
- **V8 GC threads** and **V8 compilation threads** — V8 compiles and garbage-collects on background threads, not the main thread.
- **Worker threads** (`worker_threads`) — additional V8 isolates you spawn explicitly for CPU-bound work (Part 6).

So "single-threaded" means *JavaScript execution* is single-threaded — not that the process has one thread. Network I/O (TCP, HTTP, TLS) bypasses the thread pool entirely and goes through the OS's non-blocking mechanisms (epoll/kqueue/IOCP), which is why Node handles tens of thousands of concurrent connections with one JS thread — the kernel does the waiting.

### The Foundational Trade-off

Node's architecture is optimized for **I/O-heavy workloads with many concurrent connections** — API servers, proxies, real-time services, microservices — where each request does relatively little CPU work but waits on networks and databases. It's this workload where Node genuinely outperforms thread-per-request models: no thread-creation overhead per connection, no contention, no stack-per-thread memory.

It is **not** optimized for CPU-heavy computation. A single CPU-bound task — parsing a large CSV, image processing, heavy JSON serialization — blocks the main thread and freezes *every other request* until it finishes. The event loop can't process callbacks while JS is executing. This is the cardinal sin of Node.js (the counterpart to "blocking the asyncio event loop" from the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md)), and the entire reason Worker Threads and clustering exist (Part 6).

If you remember one thing from Part 1: **Node.js is V8 (one JS thread) + libuv (event loop + thread pool) + kernel async I/O. Your JavaScript never runs in parallel with itself (without Workers), but I/O overlaps massively because the OS and libuv do the waiting.** Every performance lever in this guide either keeps the main thread unblocked (Parts 3–5) or offloads CPU work off it (Part 6).

---

## Part 2 — V8: How Your JavaScript Gets Fast

V8 doesn't interpret JavaScript — it **compiles** it, twice, adaptively. Understanding this pipeline explains why "the same" code can be 100× faster or slower depending on how you write it, and it's the foundation of the optimization advice in Parts 9 and 10.

### The Compilation Pipeline

When V8 first sees a function:

1. **Parse** → build an Abstract Syntax Tree (AST).
2. **Ignition (the baseline interpreter/compiler)** → compile the AST to **bytecode** and start executing immediately. Bytecode is compact and fast to generate, but interpreted execution is relatively slow. While running, V8 collects **type feedback** — it watches what types each variable actually holds, which branches are taken, which functions are called.
3. **Maglev (mid-tier JIT, V8 12.2+ / Node 22+)** → if a function is "warm" (called enough to be worth optimizing but not yet hot), Maglev compiles it to moderately optimized machine code using the type feedback. Faster than Ignition bytecode, cheaper to compile than full optimization.
4. **TurboFan (the optimizing compiler)** → if a function is "hot" (run many times), TurboFan compiles it to **highly optimized native machine code** — speculative, type-specialized, inlined, with register allocation. This is where JavaScript approaches C speed.

The key word is **speculative**: TurboFan compiles based on the assumption that the types it *observed* are the types it will *always* see. If that assumption is violated later (you pass a string where it saw only numbers), V8 must **deoptimize** — throw away the optimized code and fall back to Ignition or Maglev. Deoptimization is expensive and is the single most common silent performance killer.

### Hidden Classes (Maps/Shapes)

JavaScript objects are bags of properties with no declared type, so V8 has to *infer* structure. It does this with **hidden classes** (V8 calls them "Maps" internally; other engines call them "Shapes"):

```javascript
const a = {};   // V8 assigns hidden class C0 (empty)
a.x = 1;        // transition to C1: { x: offset 0 }
a.y = 2;        // transition to C2: { x: offset 0, y: offset 1 }

const b = {};
b.x = 10;       // same transition C0 → C1
b.y = 20;       // same transition C1 → C2 — b shares the SAME hidden class as a
```

Objects created with the same properties, in the same order, share the same hidden class. This is critical because TurboFan's optimized code does **direct-offset property access** (like a C struct field) based on the hidden class — it's a single pointer dereference, not a hash-table lookup. But if objects have different property orders, or one has an extra property, they get **different hidden classes** and the optimized code can't assume a common layout:

```javascript
// BAD — different property orders → different hidden classes → no optimization
function makePoint(flag) {
  const p = {};
  if (flag) { p.x = 0; p.y = 0; }  // hidden class: { x, y }
  else      { p.y = 0; p.x = 0; }  // hidden class: { y, x } — DIFFERENT
  return p;
}

// GOOD — same order, same hidden class, fast
function makePoint(x, y) {
  return { x, y };                   // always { x, y } — one hidden class
}
```

The practical rules:

- **Initialize all properties in the constructor, in the same order.** Objects with consistent shapes share hidden classes and get fast property access.
- **Don't add or delete properties after construction.** Adding a property at runtime creates a hidden-class transition; deleting one forces a transition to a "slow dictionary mode" object. Use `undefined` instead of `delete obj.prop`.
- **Use classes or factory functions**, not ad-hoc object construction — they naturally produce consistent shapes.

### Inline Caches (ICs)

Every property access (`obj.x`) and function call (`fn()`) goes through an **inline cache**. On the first call, V8 looks up the property using the hidden class (slow path) and records the result. On subsequent calls, if the hidden class is the same, V8 uses the cached lookup (fast path — one compare and one memory load). This is why **monomorphic** code (one hidden class at each call site) is fast, and **polymorphic/megamorphic** code (many different hidden classes at one call site) is slow:

```javascript
// MONOMORPHIC — one shape, fast IC:
function getX(p) { return p.x; }
getX({ x: 1, y: 2 });
getX({ x: 3, y: 4 });   // same shape → cached lookup

// MEGAMORPHIC — many shapes, slow:
getX({ x: 1, y: 2 });
getX({ x: 1, y: 2, z: 3 });
getX({ x: 1 });
getX({ a: 0, x: 1 });    // four different hidden classes → IC gives up, goes generic
```

Once an IC goes megamorphic, V8 stops trying to specialize — it falls back to generic (slow) dictionary lookups at that call site. The practical rule: **don't pass structurally different objects to the same function** in a hot loop.

### SMIs, HeapNumbers, and the Number Trap

V8 has a crucial optimization for integers: **Small Integers (SMIs)** — integers that fit in 31 bits (on 64-bit: -2³⁰ to 2³⁰−1, roughly ±1 billion) — are stored **directly in the pointer field** as a tagged value, with no heap allocation. No GC, no memory overhead, and arithmetic on two SMIs is a machine instruction plus a tag check.

The moment a number exceeds SMI range *or becomes a float*, V8 must allocate a **HeapNumber** — a heap object, with GC overhead. This matters in hot loops:

```javascript
// FAST — SMIs, no allocations:
for (let i = 0; i < 1000000; i++) { arr[i] = i; }

// SLOWER — HeapNumbers, allocations on every iteration:
for (let i = 0; i < 1000000; i++) { arr[i] = i + 0.5; }
```

The practical takeaway: **prefer integers in hot paths when the semantics allow it**, and know that crossing the SMI boundary (e.g., a counter that overflows ~1 billion) silently slows things down.

### Typed Arrays: The NumPy of JavaScript

Just as Python has NumPy to escape per-object overhead, JavaScript has **Typed Arrays** (`Int32Array`, `Float64Array`, `Uint8Array`, …) backed by an `ArrayBuffer` — a contiguous, fixed-size block of raw memory:

```javascript
const buf = new ArrayBuffer(4_000_000);          // 4 MB of raw bytes
const floats = new Float64Array(buf);            // view as 500,000 float64s

// V8 optimizes typed-array access to direct memory loads/stores —
// no boxing, no hidden-class checks, no GC pressure per element.
for (let i = 0; i < floats.length; i++) {
  floats[i] = Math.sqrt(i);                     // fast: direct memory write
}
```

Typed arrays are what Node uses internally for `Buffer`, what WebGL and WebAssembly use, and what you should use for any performance-critical numerical work. They're the escape hatch from V8's object overhead for bulk data.

### Deoptimization: The Silent Killer

When V8's speculative optimizations are violated, it **deoptimizes** — discards the optimized machine code and falls back to the interpreter. Common triggers:

- **Type change:** a variable was always a number, then you pass a string.
- **Shape change:** an object gains or loses a property at a call site where TurboFan assumed a fixed shape.
- **Hidden class mismatch:** a polymorphic/megamorphic call site.
- **try/catch:** historically deoptimized entire functions (modern V8 handles this much better, but extremely hot inner loops still benefit from being outside try/catch).
- **`arguments` object leaking:** passing `arguments` to another function prevents optimization (use rest parameters `...args` instead).

You can see deoptimizations happening:

```bash
node --trace-deopt app.js 2>&1 | grep "deoptimize"
```

If you remember one thing from Part 2: **V8 compiles hot functions to specialized machine code based on observed types — keep shapes consistent, call sites monomorphic, and numbers as SMIs, or V8 deoptimizes and your hot path slows by 10–100×.**

---

## Part 3 — The Event Loop, Actually

Most event-loop explanations are wrong or dangerously oversimplified. The event loop is not "callbacks happen later" — it's a **specific sequence of phases**, and knowing the phase order explains the behavior of `setTimeout` vs. `setImmediate`, `process.nextTick` vs. `queueMicrotask`, and why certain patterns starve I/O.

### The Phases

The event loop runs in a cycle. Each iteration ("tick") has these phases, in this order:

```text
   ┌───────────────────────────┐
   │        timers              │   setTimeout / setInterval callbacks
   ├───────────────────────────┤
   │     pending callbacks      │   deferred I/O callbacks from the previous cycle
   ├───────────────────────────┤
   │       idle, prepare        │   internal use only
   ├───────────────────────────┤
   │         poll               │   retrieve new I/O events; execute I/O callbacks
   │                           │   (this is where Node spends most of its time)
   ├───────────────────────────┤
   │         check              │   setImmediate callbacks
   ├───────────────────────────┤
   │     close callbacks        │   socket.on('close', ...) etc.
   └──────────┬────────────────┘
              │
              └── next iteration ──►
```

1. **Timers** — runs callbacks whose timers (`setTimeout`/`setInterval`) have elapsed. Note: timers are checked at the *start* of each iteration, not with millisecond precision; a `setTimeout(fn, 100)` fires "at or after 100 ms," not exactly at 100.
2. **Pending callbacks** — executes some system-level callbacks deferred from the previous cycle (e.g., TCP connection errors).
3. **Poll** — the heart. Node calculates how long to block here, fetches I/O events from the kernel (epoll/kqueue), and runs their callbacks (incoming data, connection events, completed file reads). If the poll queue is empty and there are `setImmediate` callbacks waiting, it moves to check. If the poll queue is empty and no `setImmediate`, it waits for events or the next timer.
4. **Check** — runs `setImmediate` callbacks. `setImmediate` runs after the poll phase of the *current* iteration.
5. **Close callbacks** — `'close'` event handlers.

### Microtasks: `process.nextTick` and `queueMicrotask`

Between **every phase transition** (and after every individual callback within a phase), Node drains two queues:

1. **`process.nextTick` queue** — drained first, completely, before moving on.
2. **Microtask queue** — `Promise.then`/`.catch`/`.finally`, `queueMicrotask()`. Drained next, completely.

This is *why* a recursive `process.nextTick` starves I/O — it keeps refilling its queue and the event loop never advances to the poll phase:

```javascript
// BUG: starves I/O — nextTick queue never empties
function bad() {
  process.nextTick(bad);   // re-queues itself before any I/O can run
}
bad();
// setTimeout, setImmediate, and I/O callbacks NEVER fire.

// SAFE: queueMicrotask is slightly less aggressive, but still dangerous if recursive.
// For deferred work that shouldn't starve I/O, use setImmediate.
```

The practical rules:

- **`process.nextTick`**: use sparingly — only when you need something to happen *before* any I/O and *before* promises in the current phase. The main legitimate use: ensuring an API is always async (emitting errors after returning to the caller).
- **`queueMicrotask` / Promises**: the default async primitive. Runs after the current callback but before the next I/O phase.
- **`setImmediate`**: use when you want to yield to I/O *first* and run your callback in the *next* phase. This is the tool for breaking up CPU work without starving the event loop (Part 6).

### `setTimeout(fn, 0)` vs. `setImmediate(fn)`

A classic interview question and a real design decision:

- `setTimeout(fn, 0)` runs in the **timers** phase of the *next* loop iteration (or the current one if timers haven't fired yet). There's a minimum delay (~1 ms due to the timer implementation).
- `setImmediate(fn)` runs in the **check** phase of the *current* loop iteration (after poll).

**Inside an I/O callback**, `setImmediate` always fires before `setTimeout(fn, 0)` — the check phase comes before the next iteration's timers phase. Outside an I/O callback, the order is **non-deterministic** (depends on whether the loop started with timers or check first). **Prefer `setImmediate` when you want to yield to I/O**, because that's its purpose and its behavior is more predictable.

### Blocking the Loop: The Cardinal Sin

Any synchronous JavaScript that takes a long time — a tight computation, a `JSON.parse` on a 50 MB payload, a synchronous `fs` call, a regex with catastrophic backtracking — **blocks the entire event loop** for its duration. No other request can be processed, no callback fires, no I/O is serviced. A 200 ms `JSON.parse` on a server handling 1,000 req/s means 200 requests *queue up* behind it.

Detecting blocked loops:

```javascript
// Measure event-loop lag — the gap between when a timer should fire and when it does:
const start = process.hrtime.bigint();
setTimeout(() => {
  const lag = Number(process.hrtime.bigint() - start) / 1e6 - 100; // ms above expected
  console.log(`Event loop lag: ${lag.toFixed(1)}ms`);
}, 100);

// In production, use the perf_hooks API:
import { monitorEventLoopDelay } from "node:perf_hooks";
const h = monitorEventLoopDelay({ resolution: 20 });
h.enable();
setInterval(() => {
  console.log(`EL delay p99: ${(h.percentile(99) / 1e6).toFixed(1)}ms`);
  h.reset();
}, 5000);
```

The production tool is **Clinic.js Doctor** (Part 8), which profiles event-loop blocking automatically. The fixes are: offload CPU work to a Worker Thread (Part 6), use streaming (Part 5) for large payloads, and avoid synchronous APIs entirely in request-handling code.

If you remember one thing from Part 3: **the event loop is a fixed sequence of phases — timers → poll (I/O) → check (setImmediate) — with microtask queues drained between every step. Any long-running JS blocks the entire thing, and recursive `process.nextTick` starves I/O.**

---

## Part 4 — Async Patterns & Pitfalls

`async`/`await` makes Node code *look* synchronous, which is both its power and its danger — it's easy to write code that *looks* concurrent but actually runs sequentially, or that fires off unbounded parallel work that overwhelms a downstream service. This part is about the patterns that make async code both correct and fast.

### Sequential vs. Concurrent `await`

The single most common performance bug in Node.js applications:

```javascript
// SEQUENTIAL — 3 seconds total (each awaits before the next starts):
const a = await fetchA();   // 1s
const b = await fetchB();   // 1s
const c = await fetchC();   // 1s

// CONCURRENT — 1 second total (all three in flight at once):
const [a, b, c] = await Promise.all([fetchA(), fetchB(), fetchC()]);
```

`await` *suspends* the current function until the promise resolves — so three sequential `await`s serialize three independent I/O operations. If they're independent, wrap them in **`Promise.all`**. This is the async equivalent of the Python `asyncio.gather` pattern.

### `Promise.all` vs. `Promise.allSettled` vs. `Promise.any` vs. `Promise.race`

| Method | Resolves when | Rejects when | Use case |
|---|---|---|---|
| `Promise.all` | **all** resolve | **any one** rejects (fast-fail) | need all results; one failure means the whole batch failed |
| `Promise.allSettled` | **all** settle (resolve or reject) | never rejects | need all results regardless of individual failures |
| `Promise.any` | **first** resolves | **all** reject | fastest successful response (e.g., hit multiple mirrors) |
| `Promise.race` | **first** settles (resolve or reject) | first settles with rejection | timeouts: `Promise.race([fetch(url), timeout(5000)])` |

`Promise.allSettled` is the tool for "do all of these, log the failures, keep the successes" — the correct pattern for fan-out where partial failure is acceptable.

### Bounded Concurrency

`Promise.all` on 10,000 URLs opens 10,000 connections simultaneously — overwhelming the target, exhausting file descriptors, and getting rate-limited. You need a **concurrency limiter**:

```javascript
// Simple bounded-concurrency pool:
async function mapConcurrent(items, fn, concurrency) {
  const results = [];
  const executing = new Set();
  for (const item of items) {
    const p = fn(item).then(result => {
      executing.delete(p);
      return result;
    });
    executing.add(p);
    results.push(p);
    if (executing.size >= concurrency) {
      await Promise.race(executing);
    }
  }
  return Promise.all(results);
}

// Usage: at most 20 fetches in flight at once
const results = await mapConcurrent(urls, fetch, 20);
```

In production, use **`p-limit`** or **`p-map`** from the `sindresorhus` ecosystem — they handle edge cases (error propagation, abort signals) correctly.

### Error Handling in Async Code

Unhandled promise rejections crash the process in modern Node (since Node 15+). Three rules:

1. **Always `try`/`catch` around `await`** in any function that can recover, or let the rejection propagate to a top-level handler.
2. **Never ignore promises.** A `someAsyncFn()` call without `await` or `.catch()` silently drops errors. If you intentionally don't await, add `.catch(handleError)`.
3. **`Promise.allSettled` for fan-out** — it doesn't reject on individual failures, so you handle errors per-item instead of aborting the batch.

```javascript
// Top-level safety net (last resort — don't rely on it):
process.on("unhandledRejection", (err) => {
  logger.fatal({ err }, "Unhandled rejection");
  process.exit(1);   // fail loud, don't continue in an unknown state
});
```

### `AbortController` and Cancellation

The standard cancellation primitive (shared with `fetch`, streams, and many Node APIs):

```javascript
const controller = new AbortController();
const { signal } = controller;

// Pass the signal to cancellable operations:
const response = await fetch(url, { signal });
const data = await fs.readFile(path, { signal });

// Cancel from anywhere (e.g., on timeout):
setTimeout(() => controller.abort(), 5000);
// All operations listening to this signal throw AbortError.
```

This is the correct way to implement request-level timeouts in Node.js — create an `AbortController` per request, pass its signal through the call chain, and abort it when the request deadline expires.

If you remember one thing from Part 4: **`await` serializes by default — use `Promise.all` for independent operations, bound the concurrency to avoid overwhelming downstream systems, and treat every unhandled promise rejection as a crash waiting to happen.**

---

## Part 5 — Streams & Backpressure

Streams are Node.js's answer to "process data larger than memory" — the same idea as Python's generators (see the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md), Part 5) but with a richer API, built-in backpressure, and deep integration into the platform. HTTP requests and responses, file I/O, `zlib`, `crypto`, TCP sockets, child-process stdio — they're all streams. Understanding them is what lets a Node.js server proxy a 10 GB file upload without buffering it in memory.

### The Four Stream Types

| Type | Does | Examples |
|---|---|---|
| `Readable` | produces data | `fs.createReadStream`, HTTP `req`, `process.stdin` |
| `Writable` | consumes data | `fs.createWriteStream`, HTTP `res`, `process.stdout` |
| `Duplex` | both reads and writes (independent) | TCP socket, WebSocket |
| `Transform` | reads, modifies, writes | `zlib.createGzip()`, `crypto.createCipheriv()` |

### The Pipeline: `stream.pipeline`

The correct way to connect streams — it handles backpressure, error propagation, and cleanup automatically:

```javascript
import { pipeline } from "node:stream/promises";
import { createReadStream, createWriteStream } from "node:fs";
import { createGzip } from "node:zlib";

await pipeline(
  createReadStream("input.log"),     // readable
  createGzip(),                       // transform
  createWriteStream("input.log.gz"), // writable
);
// Memory usage: constant (~64 KB buffers), regardless of file size.
```

**Never use `.pipe()` in production code.** It doesn't propagate errors — if the writable errors, the readable leaks and the process may hang. `pipeline` (or `stream.pipeline` with callbacks) does it correctly.

### Backpressure

Backpressure is the mechanism that prevents a fast producer from overwhelming a slow consumer. When a writable's internal buffer fills past its `highWaterMark`, `write()` returns `false` — a signal to stop writing until the `drain` event fires. `pipeline` handles this automatically; if you're writing manually:

```javascript
const writable = createWriteStream("out.dat");

for (const chunk of hugeDataSource) {
  const canContinue = writable.write(chunk);
  if (!canContinue) {
    // Backpressure! Wait for the writable to drain before sending more.
    await new Promise(resolve => writable.once("drain", resolve));
  }
}
writable.end();
```

Without this check, you keep buffering in memory and eventually OOM — the classic stream leak.

### Async Iterators: The Modern Stream API

Since Node 10+, Readable streams implement the async iterator protocol, so you can consume them with `for await`:

```javascript
import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";

const rl = createInterface({
  input: createReadStream("large.csv"),
  crlfDelay: Infinity,
});

for await (const line of rl) {
  // Process one line at a time, constant memory
  if (line.startsWith("ERROR")) {
    errors.push(parseLine(line));
  }
}
```

This is the cleanest way to process streams line-by-line. For byte-level processing, `for await (const chunk of readableStream)` gives you `Buffer` chunks.

### `highWaterMark` and Buffer Sizing

The `highWaterMark` (default: 16 KB for streams, 16 objects for object-mode streams) controls **how much data the stream buffers** before applying backpressure. It's a throughput-vs-memory knob:

- **Too low:** many small reads/writes, high system-call overhead.
- **Too high:** large buffers, high memory per stream. With 10,000 concurrent connections each buffering 1 MB, that's 10 GB.
- **Default is fine for most cases.** Tune it when profiling shows stream overhead or memory pressure.

### Object-Mode Streams

By default, streams carry `Buffer` or `string` chunks. In **object mode** (`objectMode: true`), each chunk is an arbitrary JS object — useful for streaming parsed records (JSON lines, database rows) through a transform pipeline. The `highWaterMark` then counts *objects*, not bytes.

If you remember one thing from Part 5: **use `stream.pipeline` (not `.pipe`) to chain streams with automatic backpressure and error handling, and consume Readable streams with `for await` — this is how you process data larger than memory without leaking it.**

---

## Part 6 — Worker Threads & Clustering

Part 3 established the cardinal sin: blocking the event loop. This part is about the two escape hatches when your workload is genuinely CPU-bound: **Worker Threads** (multiple V8 isolates in one process) and **Clustering** (multiple processes). They solve different problems and are not interchangeable.

### Worker Threads

`worker_threads` (Node 10.5+) spawn additional V8 isolates inside the same process. Each worker has **its own event loop, its own heap, its own GC** — JavaScript doesn't share memory between workers (no data races). Communication is via **message passing** (`postMessage`/`on('message')`) or, for advanced cases, `SharedArrayBuffer` with `Atomics` for true shared memory.

```javascript
// main.js
import { Worker } from "node:worker_threads";

function runWorker(data) {
  return new Promise((resolve, reject) => {
    const worker = new Worker("./worker.js", { workerData: data });
    worker.on("message", resolve);
    worker.on("error", reject);
  });
}

const result = await runWorker({ numbers: [1, 2, 3, 4, 5] });

// worker.js
import { workerData, parentPort } from "node:worker_threads";
const sum = workerData.numbers.reduce((a, b) => a + b, 0);
parentPort.postMessage(sum);
```

Key points:

- **Use for CPU-bound work:** image processing, parsing, compression, crypto, heavy JSON serialization. The worker runs on a separate thread with its own V8, so it doesn't block the main event loop.
- **Don't use for I/O:** I/O is already non-blocking on the main thread. A worker doing `fetch` or `fs.readFile` gains nothing — it just adds IPC overhead.
- **Worker startup is expensive** (~30–50 ms, plus memory for a new V8 heap). For recurring CPU tasks, use a **worker pool** — `piscina` or `workerpool` — that keeps workers alive and dispatches jobs to them:

```javascript
import Piscina from "piscina";

const pool = new Piscina({
  filename: "./worker.js",
  maxThreads: 4,                // match CPU cores
});

// Dispatches to the next available worker, returns a Promise:
const result = await pool.run({ numbers: [1, 2, 3, 4, 5] });
```

**`piscina`** (by Matteo Collina & James Snell) is the go-to worker pool — it handles job queueing, backpressure (it won't accept new work when all workers are busy), and `transferList` for zero-copy data transfer.

### Transferable Objects and Zero-Copy

`postMessage` by default **serializes** (structured clone) data — which means copying. For large `ArrayBuffer`s, that copy is expensive. **Transferring** instead *moves* the buffer to the worker in O(1), making the original unusable:

```javascript
const buffer = new ArrayBuffer(100_000_000);  // 100 MB
worker.postMessage(buffer, [buffer]);          // transfer, not copy — O(1)
// buffer.byteLength is now 0 in the main thread — it's been moved
```

Use transfer for large typed arrays, image data, and any bulk binary data passed to/from workers.

### Clustering

`cluster` (or running multiple Node processes behind a load balancer) is the answer to **scaling across CPU cores for I/O-bound workloads.** Each cluster worker is a separate Node.js process with its own V8, its own memory, listening on the same port (the OS load-balances incoming connections across them):

```javascript
import cluster from "node:cluster";
import { cpus } from "node:os";
import { createServer } from "node:http";

if (cluster.isPrimary) {
  const numCPUs = cpus().length;
  for (let i = 0; i < numCPUs; i++) {
    cluster.fork();
  }
  cluster.on("exit", (worker) => {
    console.log(`Worker ${worker.process.pid} died, restarting...`);
    cluster.fork();                    // auto-restart
  });
} else {
  createServer((req, res) => {
    res.end("Hello from worker " + process.pid);
  }).listen(3000);
}
```

In practice, **use a process manager instead of hand-rolling cluster:** `pm2` (most common), or run multiple replicas behind a reverse proxy (Nginx, Caddy — see the [Caddy guide](CADDY_STUDY_GUIDE.md)) or Kubernetes. The process manager handles restarts, log management, and graceful reloads.

### Workers vs. Cluster: When to Use Which

| Scenario | Use |
|---|---|
| CPU-bound task blocking the event loop (image resize, CSV parse, heavy crypto) | **Worker Thread** (offload the task, keep the main thread serving I/O) |
| Scale an I/O-bound HTTP server across all CPU cores | **Cluster** (multiple processes, each with its own event loop) |
| Both (I/O-heavy server that occasionally does CPU work) | **Cluster** for scaling + **worker pool** (`piscina`) for CPU tasks within each process |

If you remember one thing from Part 6: **Worker Threads offload CPU-bound work to a separate V8 isolate (use `piscina` as a pool); clustering runs multiple processes for I/O-bound scaling. Don't use Workers for I/O, and don't use clustering to solve a CPU-bound problem in a single request.**

---

## Part 7 — Memory Management & GC Tuning

V8's garbage collector is generational, concurrent, and mostly invisible — until it isn't. A memory leak that grows at 1 MB/hour takes three days to crash a container, and a GC pause at the wrong moment adds 100 ms to your p99. This part is about understanding V8's heap well enough to find leaks, avoid pressure, and tune when the defaults aren't enough.

### V8's Heap Layout

V8 divides the heap into **spaces**:

- **New Space (Young Generation):** small (~1–8 MB), holds newly allocated objects. Collected frequently with a fast **Scavenge** (copying) collector — most objects die young and are cleaned up here cheaply. Objects that survive two scavenges are **promoted** to Old Space.
- **Old Space (Old Generation):** holds long-lived objects. Collected less frequently with the **Major GC** (Mark-Sweep-Compact), which is more expensive. Old Space is where leaks accumulate.
- **Large Object Space:** objects too large for New Space go here directly.
- **Code Space:** compiled machine code (JIT output).

The practical implication: **short-lived objects are cheap** (allocated and collected in New Space, often never touching Old Space). Long-lived objects and leaking references are what cause GC pressure.

### The Heap Size Limit

V8 defaults to a **~1.5 GB** Old Space limit on 64-bit systems (or ~700 MB on 32-bit). When the heap approaches this limit, GC becomes increasingly aggressive and eventually V8 crashes with **"FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed — JavaScript heap out of memory."**

You can raise it:

```bash
node --max-old-space-size=4096 app.js   # 4 GB old space
```

But raising the limit is treating the symptom, not the cause. The usual cause is a **memory leak**.

### Finding Memory Leaks

The three-snapshot technique is the standard diagnostic:

1. **Baseline:** take a heap snapshot after the app is warmed up.
2. **Exercise:** run the operation you suspect leaks (e.g., 10,000 requests).
3. **Snapshot again:** compare to the baseline. Objects that grew are your suspects.

```javascript
// Take a heap snapshot programmatically:
import v8 from "node:v8";
import fs from "node:fs";

const snapshotPath = `/tmp/heap-${Date.now()}.heapsnapshot`;
v8.writeHeapSnapshot(snapshotPath);
// Open in Chrome DevTools → Memory → Load
```

Or from outside, without code changes:

```bash
# Send SIGUSR2 to a running Node process (with --heapsnapshot-signal=SIGUSR2):
node --heapsnapshot-signal=SIGUSR2 app.js &
kill -USR2 $!
```

In Chrome DevTools, the **Comparison** view between two snapshots shows exactly which constructor/type grew and by how many objects — the fastest path to "this closure over `req` is leaking."

### Common Leak Patterns

| Pattern | Why it leaks | Fix |
|---|---|---|
| Growing `Map`/`Set`/array used as a cache | entries never evicted | use an LRU (`lru-cache`, `mnemonist`) or `WeakRef` + `FinalizationRegistry` |
| Event listeners not removed | each `on()` retains a closure over its scope | `removeListener` / `off`, or use `{ once: true }` / `AbortSignal` |
| Closures capturing `req`/`res` | the request object (large) lives as long as the closure | null out references, don't close over the whole request |
| Unbounded queues (job lists, pending promises) | producer outpaces consumer | add backpressure (Part 5) or bounded concurrency (Part 4) |
| Global variables / module-level state | never garbage collected | avoid global mutable state; use `WeakMap`/`WeakRef` for caches keyed by objects |

### GC Tuning

You rarely need to tune V8's GC, but when you do:

- **`--max-semi-space-size=N`** (MB) — size of each semi-space in New Space. Doubling it (e.g., to 16 or 32 MB) helps workloads that allocate many short-lived objects per request, reducing promotion to Old Space.
- **`--max-old-space-size=N`** — total old-generation limit.
- **`--expose-gc` + `global.gc()`** — force a GC from JS (for benchmarks, never production).
- Watch GC with `--trace-gc`:

```bash
node --trace-gc app.js
# [12345:0x...]    34 ms: Scavenge 4.2 (6.3) -> 3.8 (8.3) MB, 1.2 / 0.0 ms ...
# [12345:0x...]   200 ms: Mark-Sweep 15.2 (20.3) -> 10.1 (18.3) MB, 12.5 / 0.0 ms ...
```

The numbers: `before (allocated) -> after (allocated) MB, pause / ... ms`. If Major GC pauses are >50 ms and frequent, you have too many long-lived objects or too much heap pressure.

If you remember one thing from Part 7: **short-lived objects are cheap (collected quickly in New Space); memory leaks are growing caches, un-removed listeners, and closures over large scopes — find them with the three-snapshot comparison in Chrome DevTools.**

---

## Part 8 — Profiling & Measurement

As with the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md), the cardinal rule: **measure before you optimize.** Node.js has outstanding profiling tools — many built into the platform — and intuition about where time is spent is almost always wrong.

### CPU Profiling

**Option 1: The built-in V8 profiler (the quickest start):**

```bash
node --prof app.js
# Run your workload, then Ctrl+C.
# Produces an isolate-*.log file.
node --prof-process isolate-*.log > processed.txt
```

The output shows bottom-up and top-down call trees with time percentages — enough to find "this function takes 40% of CPU."

**Option 2: Chrome DevTools (the most visual):**

```bash
node --inspect app.js
# Open chrome://inspect in Chrome → click "inspect" → go to the Performance tab
# Hit Record, run your workload, stop recording.
# You get a flame chart: horizontal axis is time, vertical is call stack depth.
```

The **flame chart** is the single best tool for understanding where CPU time goes — wide bars are slow functions, and you can zoom into specific intervals.

**Option 3: Clinic.js (the most automated):**

```bash
npx clinic doctor -- node app.js
# Runs the app, then opens a browser with a diagnosis:
# event loop blocked? I/O bottleneck? GC pressure?
```

[Clinic.js](https://clinicjs.org/) is a suite of three tools: **Doctor** (automated bottleneck diagnosis), **Flame** (flame chart specific to Node), and **Bubbleprof** (async flow visualization). `clinic doctor` is the starting point — it tells you *what kind* of problem you have.

### Event-Loop Monitoring

The most Node-specific metric. High event-loop delay means the main thread is blocked and requests are queuing:

```javascript
import { monitorEventLoopDelay } from "node:perf_hooks";

const h = monitorEventLoopDelay({ resolution: 20 });
h.enable();

// Periodically report:
setInterval(() => {
  console.log({
    min: (h.min / 1e6).toFixed(1),
    mean: (h.mean / 1e6).toFixed(1),
    p99: (h.percentile(99) / 1e6).toFixed(1),
    max: (h.max / 1e6).toFixed(1),
  });
  h.reset();
}, 10_000);
```

**Healthy:** mean <5 ms, p99 <20 ms. **Unhealthy:** p99 >100 ms — something is blocking the loop.

### Benchmarking

For microbenchmarks, use a proper harness that warms up, runs many iterations, and reports statistically:

```bash
npm install -D tinybench   # or benchmark.js
```

```javascript
import { Bench } from "tinybench";

const bench = new Bench({ time: 1000 });
bench
  .add("JSON.parse", () => JSON.parse('{"a":1,"b":2}'))
  .add("manual parse", () => { /* ... */ });

await bench.run();
console.table(bench.table());
```

**Never benchmark with a single `Date.now()` measurement** — it's noisy and misses JIT warmup. Use `performance.now()` at minimum, and run thousands of iterations.

### Key Metrics to Watch in Production

| Metric | What it tells you | Tool |
|---|---|---|
| Event loop delay (p50, p99) | main thread blockage | `perf_hooks`, Prometheus client |
| Heap used / heap total | memory pressure, leaks | `process.memoryUsage()`, `--trace-gc` |
| Active handles / requests | resource leaks (open sockets, timers) | `process._getActiveHandles().length` |
| GC pause duration and frequency | GC pressure | `--trace-gc`, `perf_hooks` GC observer |
| HTTP request latency (p50, p99, p999) | end-user impact | OpenTelemetry, the [Observability guide](OBSERVABILITY_STUDY_GUIDE.md) |

If you remember one thing from Part 8: **`node --inspect` + Chrome DevTools flame chart for CPU, Clinic.js Doctor for automated diagnosis, `monitorEventLoopDelay` for loop health, and the three-snapshot technique for memory leaks — always profile the real workload, not a guess.**

---

## Part 9 — Performance Levers

Now the levers, ordered by effort vs. impact — easiest and highest-return first. Each one addresses a specific bottleneck from the runtime model: either keeping the event loop unblocked, reducing V8 object overhead, avoiding deoptimization, or reducing I/O round-trips.

### Lever 1: Choose a Fast Framework (or No Framework)

The framework dominates HTTP throughput. A simple routing + JSON-response benchmark on a single core (representative of real overhead per request):

| Framework | Requests/sec (approx.) | Relative |
|---|---|---|
| **raw `node:http`** | ~65,000 | 1.0× |
| **Fastify** | ~55,000 | 0.85× |
| **Koa** | ~35,000 | 0.55× |
| **Express** | ~15,000 | 0.23× |

**Fastify** is the performance-oriented framework: schema-based serialization (it compiles JSON serializers from your schema at startup — Part 10), a plugin system that avoids middleware overhead, built-in validation with Ajv, and first-class TypeScript. If you're starting a new service and performance matters, Fastify is the default choice. Express is fine for low-traffic services where ecosystem and familiarity matter more than throughput.

### Lever 2: Serialize JSON Faster

`JSON.stringify` is a top-of-profile function in most Node.js API servers — it's called on every response. The default implementation handles arbitrary shapes at runtime; if you *know* the shape (and you usually do), you can **compile a serializer from a JSON Schema** that's 2–5× faster:

```javascript
import fastJson from "fast-json-stringify";

const stringify = fastJson({
  type: "object",
  properties: {
    id: { type: "integer" },
    name: { type: "string" },
    email: { type: "string" },
  },
});

stringify({ id: 1, name: "Alice", email: "a@b.com" });
// 2-5× faster than JSON.stringify — it generates specialized code at startup
```

Fastify does this automatically when you declare response schemas — which is a big part of why it's fast.

For `JSON.parse`, there's no schema-based shortcut (you don't know the shape until you parse), but **streaming parsers** (`@streamparser/json`, `stream-json`) avoid buffering the whole string for large payloads.

### Lever 3: Use Streams for Large Payloads

Anything over a few hundred KB should be streamed, not buffered:

```javascript
// BAD — buffers the entire file in memory, then sends:
app.get("/download", async (req, res) => {
  const data = await fs.readFile("large.bin");   // entire file in memory
  res.send(data);
});

// GOOD — streams, constant memory:
app.get("/download", (req, res) => {
  const stream = fs.createReadStream("large.bin");
  pipeline(stream, res).catch(err => { /* handle */ });
});
```

Same applies to request bodies: don't `await req.json()` on a 50 MB upload; stream it through a transform.

### Lever 4: Connection Pooling and Keep-Alive

Every TCP connection costs a handshake (1 RTT for TCP, 2+ for TLS). Reuse them:

```javascript
// Node's built-in fetch and undici use keep-alive and connection pooling by default.
// For the legacy http module, set an agent:
import { Agent } from "node:http";
const agent = new Agent({ keepAlive: true, maxSockets: 50 });
http.get(url, { agent }, callback);
```

For database connections, **always use a pool** (pg's `Pool`, knex, Prisma's connection pool) — creating a new Postgres connection takes ~5–20 ms; reusing one from a pool takes <1 ms.

### Lever 5: Avoid Blocking the Event Loop

Profile for event-loop lag (Part 8). The common offenders and their fixes:

| Blocker | Fix |
|---|---|
| `JSON.parse`/`stringify` on huge payloads | stream the parsing; offload to a Worker for >1 MB |
| Synchronous `fs` calls (`readFileSync`) | use async versions — **always** |
| Heavy regex (catastrophic backtracking) | rewrite the regex, or use `re2` (linear-time regex) |
| Large `for` loop (data transformation) | chunk with `setImmediate` or offload to a Worker |
| Crypto (pbkdf2, scrypt) | use async versions (`crypto.pbkdf2`, not `crypto.pbkdf2Sync`) |

### Lever 6: Cache Aggressively

- **In-process LRU** (`lru-cache`, `mnemonist/lru-cache`) — for per-instance, latency-critical caching (parsed configs, compiled templates, resolved DNS).
- **Redis** — for shared-across-instances caching. See the [Redis guide](REDIS_STUDY_GUIDE.md) for patterns (cache-aside, write-through, TTL, and eviction).
- **HTTP caching headers** (`Cache-Control`, `ETag`, `Last-Modified`) — let the CDN or browser cache responses without hitting your server at all.

### Lever 7: Optimize V8 (Part 2's Practical Application)

- **Consistent object shapes** — initialize all properties in constructors, same order.
- **Monomorphic call sites** — don't pass structurally different objects to the same hot function.
- **Avoid `delete`** — use `obj.prop = undefined` instead.
- **Prefer SMI-range integers** in hot paths.
- **Use `Buffer.allocUnsafe(n)`** instead of `Buffer.alloc(n)` when you'll immediately fill the buffer — `alloc` zero-fills (safe but slow for large buffers).
- **Pre-allocate arrays** with known sizes (`new Array(n)`) rather than growing dynamically.

### Lever 8: Cluster and Scale Horizontally

A single Node.js process uses one CPU core. For an I/O-bound server, running one process per core (via `cluster`, pm2, or container replicas) linearly multiplies throughput up to core count. See Part 6.

### Lever 9: Move the Hot Path Out of JavaScript

When you've exhausted the above and the bottleneck is CPU-bound JavaScript:

- **WebAssembly (Wasm):** compile C/C++/Rust to Wasm and call it from Node. Good for codecs, parsers, crypto, and any CPU-intensive algorithm. V8 runs Wasm at near-native speed with no GC.
- **Native addons (N-API / `node-addon-api`):** write the hot function in C/C++ and call it from JS. N-API is stable across Node versions. PyO3's equivalent for Node is **Neon** (Rust → Node via N-API).
- **Rust via Neon or `napi-rs`:** write the extension in Rust, compile to a native module. Increasingly popular — `napi-rs` is the ergonomic choice and is what powers `@swc/core`, `lightningcss`, and `@parcel/css`.

If you remember one thing from Part 9: **the levers in order of effort-to-impact are: faster framework (Fastify) → schema-compiled JSON → streams for large data → connection pooling → unblock the event loop → caching → V8 shape discipline → cluster across cores → native/Wasm for the hot path.** Profile first, fix the measured bottleneck.

---

## Part 10 — High-Performance Recipes

Each recipe is a complete, worked pattern for a common Node.js performance problem — profiled, explained, and ready to adapt.

### Recipe 1: Schema-Compiled JSON Serialization

The single biggest throughput win for JSON API servers:

```javascript
import Fastify from "fastify";

const app = Fastify({ logger: true });

app.get("/users/:id", {
  schema: {
    response: {
      200: {
        type: "object",
        properties: {
          id:    { type: "integer" },
          name:  { type: "string" },
          email: { type: "string" },
          role:  { type: "string", enum: ["admin", "user"] },
        },
      },
    },
  },
  handler: async (req) => {
    const user = await db.getUser(req.params.id);
    return user;   // Fastify serializes with the compiled serializer — 2-5× faster
  },
});

await app.listen({ port: 3000 });
```

Fastify takes the response schema, passes it to `fast-json-stringify` at startup, and uses the **compiled function** on every response — it generates code like `'"id":' + obj.id + ',"name":"' + obj.name + '"'` instead of walking the object generically. This also acts as a **security filter** — properties not in the schema are stripped from the response.

### Recipe 2: Stream a Large File Through a Transform

Process a multi-GB file line-by-line in constant memory:

```javascript
import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";
import { pipeline } from "node:stream/promises";
import { createWriteStream } from "node:fs";
import { Transform } from "node:stream";

const filterErrors = new Transform({
  objectMode: true,
  transform(line, encoding, callback) {
    if (line.includes("ERROR")) {
      this.push(line + "\n");
    }
    callback();
  },
});

const rl = createInterface({
  input: createReadStream("app.log"),   // lazy, ~64 KB buffer
  crlfDelay: Infinity,
});

// readline emits lines; pipe through filter; write to output
const lines = (async function* () {
  for await (const line of rl) yield line;
})();

await pipeline(
  createReadStream("app.log"),
  async function* (source) {
    const rl = createInterface({ input: source, crlfDelay: Infinity });
    for await (const line of rl) {
      if (line.includes("ERROR")) yield line + "\n";
    }
  },
  createWriteStream("errors.log"),
);
// Peak memory: ~64 KB regardless of file size.
```

The async generator as a pipeline stage is the modern, ergonomic pattern — it's a stream transform without the class boilerplate.

### Recipe 3: Bounded-Concurrency API Fan-Out

Fetch data from 500 endpoints without overwhelming them:

```javascript
import pLimit from "p-limit";

const limit = pLimit(25);   // max 25 concurrent requests

const urls = Array.from({ length: 500 }, (_, i) => `https://api.example.com/items/${i}`);

const results = await Promise.allSettled(
  urls.map(url => limit(() =>
    fetch(url, { signal: AbortSignal.timeout(5000) })
      .then(res => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json();
      })
  ))
);

const successes = results.filter(r => r.status === "fulfilled").map(r => r.value);
const failures  = results.filter(r => r.status === "rejected");
console.log(`${successes.length} ok, ${failures.length} failed`);
```

`p-limit` queues excess work; `AbortSignal.timeout` prevents any single request from hanging; `Promise.allSettled` collects partial results instead of aborting on the first failure.

### Recipe 4: Offload CPU Work to a Worker Pool

Image thumbnailing that doesn't block the event loop:

```javascript
// thumbnail-worker.js
import sharp from "sharp";
import { workerData, parentPort } from "node:worker_threads";

const { inputBuffer, width, height } = workerData;
const result = await sharp(inputBuffer)
  .resize(width, height)
  .webp({ quality: 80 })
  .toBuffer();

parentPort.postMessage(result, [result.buffer]);  // transfer, not copy

// main.js — use piscina for pooling
import Piscina from "piscina";

const pool = new Piscina({
  filename: "./thumbnail-worker.js",
  maxThreads: 4,
});

app.post("/upload", async (req, res) => {
  const imageBuffer = await req.arrayBuffer();
  const thumbnail = await pool.run({
    inputBuffer: Buffer.from(imageBuffer),
    width: 200,
    height: 200,
  });
  // Main thread was never blocked — it kept serving other requests during resize
  res.type("image/webp").send(thumbnail);
});
```

### Recipe 5: Database Connection Pooling with Query Batching

```javascript
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({
  host: "localhost",
  database: "app",
  max: 20,                          // 20 connections in the pool
  idleTimeoutMillis: 30_000,        // close idle connections after 30s
  connectionTimeoutMillis: 5_000,   // fail if can't get a connection in 5s
});

// Single query — borrows and returns a connection automatically:
const { rows } = await pool.query("SELECT * FROM users WHERE id = $1", [userId]);

// Transaction — hold a single connection:
const client = await pool.acquire();
try {
  await client.query("BEGIN");
  await client.query("UPDATE accounts SET balance = balance - $1 WHERE id = $2", [100, from]);
  await client.query("UPDATE accounts SET balance = balance + $1 WHERE id = $2", [100, to]);
  await client.query("COMMIT");
} catch (err) {
  await client.query("ROLLBACK");
  throw err;
} finally {
  client.release();                 // always return to pool
}
```

**Never create a new connection per request** — the handshake cost alone (TCP + TLS + Postgres auth) can exceed the query time. Pool sizing: start with `max = 2 × CPU cores + 1` (the Postgres wiki recommendation) and tune from there.

### Recipe 6: Efficient Caching with LRU and Stale-While-Revalidate

```javascript
import { LRUCache } from "lru-cache";

const cache = new LRUCache({
  max: 10_000,                      // max entries
  ttl: 60_000,                      // 60 seconds
  allowStale: true,                 // return stale entry while refreshing
  fetchMethod: async (key) => {
    // Called when the key is missing or stale:
    return db.query("SELECT * FROM products WHERE id = $1", [key]);
  },
});

// Usage — one call, handles miss/stale/refresh:
app.get("/products/:id", async (req, res) => {
  const product = await cache.fetch(req.params.id);
  res.json(product);
});
```

`allowStale: true` is the "stale-while-revalidate" pattern: when a cached entry expires, the *old* value is returned immediately (fast) while a background `fetchMethod` refreshes it (fresh for the next caller). This eliminates the latency spike of a cold cache miss and the thundering-herd problem (only one fetch runs per key, not one per concurrent requester).

### Recipe 7: Chunking CPU Work to Avoid Blocking the Loop

When you can't use a Worker (maybe the task is too small to justify IPC) but it's blocking the loop:

```javascript
async function processLargeArray(items) {
  const results = [];
  for (let i = 0; i < items.length; i++) {
    results.push(heavyTransform(items[i]));

    // Every 1000 items, yield to the event loop:
    if (i % 1000 === 0) {
      await new Promise(resolve => setImmediate(resolve));
    }
  }
  return results;
}
```

`setImmediate` runs the callback in the **check** phase, *after* pending I/O — so this pattern processes 1,000 items, yields to let I/O callbacks and other requests run, then resumes. It won't win any speed contests (the work still runs on the main thread), but it keeps the event loop responsive — p99 latency for other requests stays low.

### Recipe 8: Zero-Copy Buffer Operations

```javascript
// Reuse a single buffer for repeated writes instead of allocating each time:
const RESPONSE_BUF = Buffer.from('{"ok":true}');

app.get("/health", (req, res) => {
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(RESPONSE_BUF);   // no allocation per request — same buffer every time
});

// Slice without copying (shares underlying ArrayBuffer):
const big = Buffer.allocUnsafe(1024 * 1024);
const header = big.subarray(0, 12);   // zero-copy view of the first 12 bytes
const body = big.subarray(12);        // zero-copy view of the rest

// Concatenate buffers efficiently (one allocation):
const combined = Buffer.concat([header, body]);
```

`Buffer.allocUnsafe` skips zero-filling — safe when you'll immediately write into it, and significantly faster for large buffers. `subarray` returns a view (no copy); `slice` copies in older Node but is now an alias for `subarray`.

### Recipe 9: HTTP Keep-Alive and Undici for Outbound Requests

Node's built-in `fetch` (backed by **undici**) uses keep-alive and HTTP/1.1 pipelining by default. For maximum control over outbound HTTP performance:

```javascript
import { Pool } from "undici";

const pool = new Pool("https://api.example.com", {
  connections: 20,           // max concurrent connections to this origin
  pipelining: 1,             // 1 = no pipelining; increase for trusted backends
  keepAliveTimeout: 60_000,  // reuse connections for 60s
});

const { statusCode, body } = await pool.request({
  method: "GET",
  path: "/data",
});

const data = await body.json();
```

`undici` is significantly faster than the legacy `http` module for outbound requests — it's what powers Node's built-in `fetch`, and using its `Pool` directly gives you connection-pooling tuning.

### Recipe 10: Graceful Shutdown

Not a speed recipe — a correctness recipe that prevents data loss and broken connections during deploys:

```javascript
async function gracefulShutdown(server) {
  console.log("Shutting down gracefully...");

  // 1. Stop accepting new connections:
  server.close();

  // 2. Set a hard deadline:
  const forceExit = setTimeout(() => {
    console.error("Forced shutdown after timeout");
    process.exit(1);
  }, 30_000);

  // 3. Wait for in-flight requests to complete:
  // (Fastify: await app.close(); Express: server.close(callback))

  // 4. Close database pools, flush caches, finish streams:
  await pool.end();

  clearTimeout(forceExit);
  process.exit(0);
}

process.on("SIGTERM", () => gracefulShutdown(server));
process.on("SIGINT",  () => gracefulShutdown(server));
```

In Kubernetes, `SIGTERM` is sent before a pod is killed; you get `terminationGracePeriodSeconds` (default: 30s) to drain. Without graceful shutdown, in-flight requests get `ECONNRESET` and database transactions may be left open.

### The Decision Tree

When a Node.js service is too slow, work through this:

```text
1. Profile it (Part 8): flame chart, event-loop delay, memory
   │
2. Event loop blocked? (lag > 50 ms)
   │ yes → find the blocker: sync fs? heavy JSON? CPU loop? regex?
   │        → stream it, async it, Worker it, or chunk with setImmediate
   │ no ↓
3. Framework overhead? (is Express the bottleneck?)
   │ yes → switch to Fastify, add response schemas
   │ no ↓
4. JSON serialization? (JSON.stringify in the top-10 profile)
   │ yes → fast-json-stringify with response schema
   │ no ↓
5. Database round-trips? (many small queries, connection churn)
   │ yes → connection pool, batch queries, add caching
   │ no ↓
6. Outbound HTTP? (waiting on APIs, no concurrency)
   │ yes → Promise.all with bounded concurrency, connection pooling
   │ no ↓
7. Memory pressure / GC pauses?
   │ yes → find the leak (3 snapshots), reduce allocations, tune --max-semi-space-size
   │ no ↓
8. V8 deoptimization? (megamorphic, shape changes)
   │ yes → consistent shapes, monomorphic call sites, avoid delete
   │ no ↓
9. Single core saturated?
   │ yes → cluster / pm2 / container replicas
   │ no ↓
10. CPU-bound hot path?
    │ yes → Worker pool (piscina), or rewrite in Rust/Wasm
    │ no ↓
11. Accept it, or rethink the architecture.
```

If you remember one thing from Part 10: **profile first, then pick the cheapest lever — response-schema JSON compilation and connection pooling are the two highest-return, lowest-effort wins for most Node.js API servers, and `setImmediate` chunking or a `piscina` worker pool is how you keep the event loop alive when CPU work is unavoidable.**

---

That's the guide. From here the highest-leverage next step is the same as every performance guide in this repo: take a service you own, run `node --inspect` and record a flame chart under realistic load, find the wide bar, and apply the cheapest matching lever from Part 9. The pattern — measure, identify the bottleneck class, apply the lever, re-measure — is the skill, and it compounds from here.

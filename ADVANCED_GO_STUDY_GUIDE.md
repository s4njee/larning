# Advanced Go Study Guide

A depth-first guide to the Go runtime and high-performance Go for engineers who already write Go and want to understand what happens *beneath* their code — the scheduler, the garbage collector, escape analysis, memory layout — and how to make Go programs fast on purpose. It assumes you're fluent in the language (goroutines, channels, interfaces, slices, error handling); for the on-ramp from another language, the [Golang for Python Developers guide](GOLANG_FOR_PYTHON_DEVS.md) covers the fundamentals this one builds on.

This is the third in a trilogy with the [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) and [Advanced Node.js](ADVANCED_NODEJS_STUDY_GUIDE.md) guides, and the comparison sharpens the whole thing into one thesis:

> **In Python you fight the interpreter; in Node you fight the event loop and feed the JIT; in Go you fight the allocator and the garbage collector.**

Go is compiled ahead-of-time to native machine code — there is no interpreter to escape and no JIT to warm up. Your hot loop is *already* machine code from the first instruction. That changes the entire performance story: the levers are not "move this into C" or "keep the event loop unblocked," but **reduce heap allocations, manage GC pressure, lay out memory for the cache, and control concurrency**. Every chapter here is, ultimately, about one of those four. The closing recipe chapter is the payoff: profiled, production-grade patterns for fast Go.

Primary references: the [Go Memory Model](https://go.dev/ref/mem) and [runtime docs](https://pkg.go.dev/runtime), the [official diagnostics guide](https://go.dev/doc/diagnostics), Dave Cheney's [performance writing](https://dave.cheney.net/high-performance-go-workshop/dotgo-paris.html), the [`pprof`](https://pkg.go.dev/runtime/pprof) tooling, and the runtime source itself (`src/runtime/` in the Go tree — unusually readable). Where Go services live in production, the [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md), [Observability](OBSERVABILITY_STUDY_GUIDE.md), and [Kubernetes](k8s/KUBERNETES_STUDY_GUIDE.md) guides are companions.

---

## Table of Contents

1. [Part 1 — The Go Runtime Model](#part-1--the-go-runtime-model)
2. [Part 2 — The GMP Scheduler](#part-2--the-gmp-scheduler)
3. [Part 3 — Escape Analysis & Allocation](#part-3--escape-analysis--allocation)
4. [Part 4 — The Garbage Collector](#part-4--the-garbage-collector)
5. [Part 5 — Data Structures & Memory Layout](#part-5--data-structures--memory-layout)
6. [Part 6 — Concurrency for Performance](#part-6--concurrency-for-performance)
7. [Part 7 — The Compiler & PGO](#part-7--the-compiler--pgo)
8. [Part 8 — Profiling & Measurement](#part-8--profiling--measurement)
9. [Part 9 — Performance Levers](#part-9--performance-levers)
10. [Part 10 — High-Performance Recipes](#part-10--high-performance-recipes)

---

## Part 1 — The Go Runtime Model

Before any optimization, get the model right — and the most important fact is what Go *isn't*. It isn't interpreted like CPython, and it isn't JIT-compiled like V8. Understanding that reframes everything you'll do to make it fast.

### Compiled, Native, Self-Contained

The Go toolchain compiles your source **ahead of time to native machine code** for the target architecture. There is no bytecode, no interpreter, no JIT warmup. `go build` produces a **statically linked binary** (by default) that contains your code *and* the Go runtime, with no external dependencies — you can `scp` it to a bare machine and run it. This is why Go dominates cloud infrastructure (Docker, Kubernetes, etcd, Prometheus, Terraform are all Go): a single small binary, instant startup, native speed.

The consequence for performance work: **your code starts at native speed.** The Python guide's biggest lever — "escape the interpreter into NumPy/C" — doesn't exist here because there's no interpreter to escape. The Node guide's "feed the JIT, don't deoptimize" doesn't apply because there's no JIT. What's left, and what this guide is about, is the **runtime** that ships inside every binary.

### The Runtime Lives Inside Your Binary

Go binaries are "fat" (a few MB minimum) because they embed the Go runtime — a sophisticated piece of systems software that provides:

- the **goroutine scheduler** (Part 2),
- the **garbage collector** (Part 4),
- the **memory allocator** (a tcmalloc-derived allocator with per-P caches),
- **goroutine stack management** (growable stacks),
- the **netpoller** (async network I/O), channels, maps, and the `runtime` package.

You don't invoke this runtime; it's always there, scheduling your goroutines and collecting your garbage underneath every line. Performance tuning in Go is largely about *cooperating with this runtime* — allocating less so the GC runs less, structuring concurrency so the scheduler isn't fighting you.

### Values, Pointers, and Copies

Go has **value semantics by default**: assigning a struct, passing it to a function, or putting it in a slice **copies it**. This is unlike Python and JavaScript, where everything is a reference to a heap object. It's a double-edged performance characteristic:

```go
type Point struct{ X, Y, Z float64 }   // 24 bytes

func translate(p Point) Point {         // p is a COPY of the caller's Point
    p.X += 1
    return p                            // returns another copy
}
```

- **Upside:** small values live on the stack and in contiguous slices with no pointer indirection and no GC involvement — excellent cache behavior, zero allocation. A `[]Point` is 24 bytes × N in one contiguous block, not N pointers to N heap objects (the Python/Node default).
- **Downside:** copying *large* structs repeatedly is wasteful, and that's when you reach for pointers (`*Point`) — but pointers can push values onto the heap (Part 3). The tension between "copy a value (stack, cache-friendly)" and "pass a pointer (no copy, but maybe heap)" is a recurring Go performance decision, and the answer is usually "measure, and prefer values until they're big."

### The Performance Thesis

Because Go is already native code, performance work concentrates in four areas, and the whole guide maps to them:

1. **Allocations** — every heap allocation costs the allocator's time *and* future GC work. Reducing heap allocations (Part 3) is the single highest-return Go optimization.
2. **GC pressure** — fewer/smaller live heap objects mean less GC work and lower latency (Part 4).
3. **Memory layout** — contiguous, cache-friendly, properly-aligned data (Part 5) makes the CPU fast; pointer-chasing makes it stall.
4. **Concurrency** — goroutines are cheap but not free; contention and unbounded concurrency are the scaling killers (Part 6).

Notice what's *not* on the list: "make the language faster." The language is already fast. You make *programs* faster by allocating less and concurring better.

If you remember one thing from Part 1: **Go compiles to native code with a runtime baked in, so you don't optimize by escaping an interpreter — you optimize by reducing allocations, easing GC pressure, laying out memory well, and controlling concurrency.** Those four are the entire game.

---

## Part 2 — The GMP Scheduler

Goroutines are Go's signature feature, and the scheduler that runs them is a marvel of systems engineering. Understanding it explains why you can spawn a million goroutines, why a blocking syscall doesn't freeze your program, and how to tune concurrency for throughput.

### Goroutines Are Not OS Threads

A goroutine is a **lightweight, user-space thread** managed by the Go runtime, not the OS. The differences are what make Go's concurrency model work:

- **Tiny, growable stacks.** A goroutine starts with a ~**2 KB** stack (versus ~1–8 MB for an OS thread). The runtime grows and shrinks it on demand by copying. This is why a million goroutines fit in a couple of GB while a million OS threads would exhaust the machine.
- **Cheap to create and switch.** Creating a goroutine is a function call's worth of work, not a syscall. Switching between goroutines happens in user space without a full kernel context switch.
- **Multiplexed onto OS threads.** Many goroutines run on few OS threads (M:N scheduling), managed by the runtime.

### G, M, and P

The scheduler is built on three entities — memorize these, because every scheduler behavior follows from their interaction:

- **G — goroutine.** A unit of work: the function, its stack, its state (running, runnable, waiting).
- **M — machine.** An OS thread. The thing the kernel actually schedules onto a CPU. An M executes Go code only while holding a P.
- **P — processor.** A *logical* processor: a scheduling context that owns a **local run queue** of runnable goroutines. The number of Ps is **[`GOMAXPROCS`](https://pkg.go.dev/runtime#GOMAXPROCS)**, and it caps how many goroutines run Go code *simultaneously*.

The model: **to run Go code, an M must hold a P.** A P has a queue of Gs; the M grabs a G from its P's queue and runs it. There are `GOMAXPROCS` Ps, so at most `GOMAXPROCS` goroutines execute Go code in parallel — but there can be *many* more Ms (threads blocked in syscalls don't hold a P).

```text
   P0 [G G G G]──M0──CPU      Ps  = GOMAXPROCS (logical processors, each a run queue)
   P1 [G G]    ──M1──CPU      Ms  = OS threads (only run Go code while holding a P)
   P2 [G G G]  ──M2──CPU      Gs  = goroutines (cheap, ~2KB stacks)
                              global run queue: [G G]  (overflow / unparked Gs)
```

### Work-Stealing Keeps Cores Busy

Each P has its own local run queue (lock-free for the owner), plus there's a shared global run queue. When a P's local queue empties, its M doesn't go idle — it **steals** half the goroutines from another P's queue (or pulls from the global queue, or polls the netpoller). This **work-stealing** keeps all `GOMAXPROCS` cores busy without a central bottleneck, and it's why Go scales well across cores with no tuning for most workloads.

### Blocking Syscalls and the Netpoller

Two scenarios that show the scheduler's cleverness, and that matter for performance:

- **Blocking syscall** (e.g., a blocking file read): the G's M blocks in the kernel — but the runtime **detaches the P from that M and hands it to another M**, so the other goroutines on that P keep running. The blocked M parks until the syscall returns. So one goroutine doing a blocking syscall doesn't stall the others sharing its P. (This is why Go doesn't need the "never block the event loop" discipline that dominates the [Node](ADVANCED_NODEJS_STUDY_GUIDE.md) and [async](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) guides — blocking a goroutine is fine; the scheduler routes around it.)
- **Network I/O**: handled by the **netpoller**, which uses the OS's async mechanism (epoll/kqueue/IOCP — the same primitives under libuv). A goroutine doing a network read *parks* (yielding its P to others) and is made runnable again when the netpoller reports the socket is ready. So you write simple **blocking-style** code (`conn.Read(buf)`) and get **async I/O efficiency** for free — Go's killer ergonomic. Hundreds of thousands of idle connections cost almost nothing.

### Preemption: No Goroutine Starves the Others

Originally Go's scheduler was *cooperative* — a goroutine yielded only at function calls, channel ops, and allocations, so a tight loop with none of those (`for {}`) could hog a P forever. Since **[Go 1.14](https://go.dev/doc/go1.14#runtime)**, the scheduler uses **asynchronous preemption**: it sends a signal to long-running goroutines (every ~10 ms) to force a yield. So a CPU-bound goroutine no longer starves its peers, and you don't need to sprinkle `runtime.Gosched()` calls. (The garbage collector relies on this too, to stop goroutines for its brief safepoints.)

### GOMAXPROCS — and the Container Trap

`GOMAXPROCS` (the number of Ps) defaults to the number of CPUs the runtime sees. Historically this was a **major production footgun in containers**: a Go process in a container limited to 2 CPUs (via cgroup quota) on a 64-core host would still set `GOMAXPROCS=64`, creating wild scheduler contention and GC over-parallelism. The classic fix was the [`automaxprocs`](https://pkg.go.dev/go.uber.org/automaxprocs) library (Uber) to read the cgroup limit.

**As of [Go 1.25](https://go.dev/doc/go1.25), the runtime is cgroup-aware** and sets `GOMAXPROCS` from the container's CPU quota automatically — a significant fix if you run Go in Kubernetes ([Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md)). On older Go versions, *still use `automaxprocs`* or set `GOMAXPROCS` explicitly to your CPU limit. Setting it too high in a constrained container wastes effort on scheduling and inflates GC parallelism; getting it right is one of the cheapest production wins available.

If you remember one thing from Part 2: **the GMP scheduler multiplexes cheap goroutines onto `GOMAXPROCS` OS threads with work-stealing, routes around blocking syscalls, and turns blocking-style network code into async I/O via the netpoller — so you write simple sequential-looking goroutines and the runtime makes them efficient, provided `GOMAXPROCS` matches your real CPU budget.**

---

## Part 3 — Escape Analysis & Allocation

Here is the single most important performance concept in Go, and the one that most separates engineers who *guess* from those who *know*: **whether a value lives on the stack or the heap, and why.** Reducing heap allocations is the highest-return optimization in the language, because every heap allocation costs allocator time now and garbage-collector time later.

### Stack vs. Heap

- **Stack allocation is nearly free.** Each goroutine has its own stack (Part 2). Allocating on it is a pointer bump; freeing is automatic when the function returns (the stack just unwinds). No GC ever looks at stack memory. A function that allocates only on the stack generates *zero garbage*.
- **Heap allocation is expensive** — twice. The allocator must find space (with locking/coordination, though Go's per-P caches make the fast path cheap), *and* every heap object becomes future work for the garbage collector, which must trace and eventually free it. Heap allocations are the raw material of GC pressure (Part 4).

So the question "stack or heap?" is really "free, or expensive-twice?" And the answer is decided **at compile time** by **escape analysis** (the [compiler's documentation](https://github.com/golang/go/blob/master/src/cmd/compile/README.md) describes the pass; the [Go GC guide](https://go.dev/doc/gc-guide#Where_Go_Values_Live) covers where values live).

### What Escape Analysis Does

The compiler analyzes whether a value's lifetime is provably confined to the function that created it. If it is, the value stays on the **stack**. If the value might be referenced *after the function returns* — it "**escapes**" — the compiler must put it on the **heap** so it stays alive.

You can see exactly what the compiler decided:

```go
go build -gcflags="-m" ./...      // prints escape analysis decisions
go build -gcflags="-m -m" ./...   // even more detail (why something escaped)
```

Typical output: `./main.go:12:9: &x escapes to heap` or `./main.go:8:13: moved to heap: buf`. Reading this output is the core skill of Go performance work — it tells you, line by line, where your garbage comes from.

### What Causes Things to Escape

The recurring culprits, each a place to look when reducing allocations:

```go
// 1. Returning a pointer to a local — the value must outlive the function, so it escapes.
func newUser() *User {
    u := User{Name: "x"}   // escapes to heap (a caller holds the pointer)
    return &u
}

// 2. Storing in something that outlives the function (a heap slice, a global, a field).
func add(list *[]*Item, it Item) {
    *list = append(*list, &it)   // &it escapes — it's kept in the slice
}

// 3. Interface boxing — putting a concrete value into an interface often allocates.
func log(v any) { ... }
log(42)                          // 42 may be boxed onto the heap to fit `any`

// 4. Closures that capture variables and escape (e.g., passed to `go` or returned).
func counter() func() int {
    n := 0                       // n escapes — the returned closure references it
    return func() int { n++; return n }
}

// 5. Values whose size isn't known at compile time, or that are too large for the stack.
```

The subtle, important point: **a pointer does not *always* mean heap.** Escape analysis is smart — a pointer to a local that's only *used within* the function (and inlined callees) can stay on the stack. So "use values not pointers to avoid allocation" is a heuristic, not a law; the compiler's `-m` output is the truth. Sometimes passing a pointer *prevents* a copy without escaping; sometimes it forces a heap allocation. Measure.

### Interface Boxing: The Hidden Allocator

Worth its own callout because it surprises people. When you store a concrete value in an interface (including `any`/`interface{}`), Go may need to **box** it — allocate a heap copy so the interface can hold a pointer to it. This is why `fmt.Sprintf`, `log` calls, and `[]any` are quietly allocation-heavy:

```go
// Each of these may allocate to box the int/float into the interface:
fmt.Sprintf("%d", n)        // n is boxed into an `any` for the variadic args
var x any = 3.14            // 3.14 boxed onto the heap
```

In hot paths, this is a real cost. Avoiding `any`, using generics (Part 7) instead of `interface{}` where possible, and keeping formatting out of inner loops all reduce it. (Small integers in the range [0, 255] are cached, like Python's small-int cache, so boxing them doesn't allocate — but don't rely on it.)

### The Allocator

When a value does go to the heap, Go's allocator (derived from tcmalloc) makes the common case fast: each **P** (Part 2) has a local cache (`mcache`) of size-classed memory, so small allocations are usually lock-free and quick. This is why Go can allocate reasonably fast — but "fast to allocate" still means "the GC must later trace and free it." The allocation you don't make is always cheaper than the one you make quickly.

If you remember one thing from Part 3: **stack allocation is free and generates no garbage; heap allocation costs you twice (allocator now, GC later). Escape analysis decides which you get, `-gcflags="-m"` shows you its decisions, and reducing heap escapes — fewer returned pointers, less interface boxing, preallocated buffers — is the single highest-return optimization in Go.**

## Part 4 — The Garbage Collector

Part 3 created garbage; this part is about what collects it, and how to make that cheap. Go's GC is a deliberate engineering trade — it optimizes for **low latency** above all, and understanding its design tells you exactly which knobs to turn (few) and which habits actually help (allocate less).

### The Design: Concurrent, Low-Latency Mark-and-Sweep

Go's garbage collector is a **concurrent, tri-color, mark-and-sweep** collector that is **non-generational** and **non-compacting** — the official [Guide to the Go Garbage Collector](https://go.dev/doc/gc-guide) is the definitive reference for everything in this part. Each property is a deliberate choice:

- **Concurrent** — the GC runs *alongside* your program (the "mutator"), on separate goroutines, rather than stopping the world to do its work. The stop-the-world (STW) pauses are tiny — typically **sub-millisecond, often microseconds** — bookending the concurrent marking phase.
- **Low-latency-first** — Go explicitly trades some throughput and some extra CPU/memory for *short pauses*. This is the right call for the servers Go targets (you'd rather pay 1% more CPU than have a 50 ms pause spike your p99). It's a different philosophy from throughput-tuned collectors.
- **Non-compacting** — objects never move. Upside: no cost to relocate objects and rewrite pointers, and pointers stay stable. Downside: possible fragmentation (mitigated by the size-classed allocator).
- **Non-generational** — no separate young/old heaps (unlike the JVM, V8, or CPython's cycle collector). Go bet on a simpler design plus low pause times. (An experimental redesign, *Green Tea GC*, is available behind `GOEXPERIMENT=greenteagc` in recent Go for better cache locality and scalability — worth watching, not yet default.)

### How It Works (Just Enough)

The **tri-color** abstraction: every object is white (unvisited), grey (reachable, not yet scanned), or black (reachable and scanned). The GC starts from the **roots** (goroutine stacks, globals), colors them grey, then repeatedly scans grey objects — coloring them black and their referents grey — until no grey remains. Whatever is still **white is unreachable** and gets swept (freed).

Because this happens *concurrently with your running program*, the program might change a pointer mid-collection in a way that could hide a still-reachable object. A **write barrier** prevents that: during a GC cycle, pointer writes are intercepted and recorded so nothing live is missed. The write barrier adds a small cost to pointer writes *while a GC is in progress* — another reason fewer pointers and less heap churn help.

The cost of a GC cycle is driven by two things, and they map directly to your two levers:

1. **How much live memory must be scanned** — proportional to the *reachable* heap. Keep less alive → cheaper cycles.
2. **How often the GC runs** — driven by your *allocation rate*. Allocate less → run less often.

Both reduce to "allocate less and retain less" — i.e., Part 3 plus good data design (Part 5). **You tune the GC mostly by not making garbage.**

### The Two Knobs: GOGC and GOMEMLIMIT

You rarely need more than these, and most apps need only the second.

**[`GOGC`](https://go.dev/doc/gc-guide#GOGC)** controls collection *frequency* by setting a growth target. The default `GOGC=100` means: trigger the next GC when the heap has grown **100% (doubled)** relative to the live set after the previous collection. It's a direct memory-for-CPU trade:

- **Raise it** (`GOGC=200`, `400`) → GC runs *less often* → **more memory used, less CPU spent on GC, higher throughput.** Good when you have RAM to spare and want max throughput.
- **Lower it** (`GOGC=50`) → GC runs *more often* → less memory, more CPU. Rarely useful.
- `GOGC=off` disables GC entirely — only for short-lived batch jobs that exit before exhausting memory.

**[`GOMEMLIMIT`](https://go.dev/doc/gc-guide#Memory_limit)** (Go 1.19+) sets a **soft memory limit**. As the heap approaches it, the GC runs progressively more aggressively to stay under it — trading CPU to respect the ceiling. This is the **single most important runtime setting for containerized Go**, and it fixed a long-standing pain:

```bash
# In a container limited to 512 MiB, leave headroom for non-heap memory:
GOMEMLIMIT=450MiB ./myserver
```

Without it, a Go service under a Kubernetes memory limit could allocate past the cgroup limit between GC cycles and get **OOM-killed** even though it could have collected in time. `GOMEMLIMIT` tells the runtime "spend whatever CPU you must to stay under this." The recommended container setup is **`GOMEMLIMIT` ≈ your memory limit minus headroom, with `GOGC` left at 100** — `GOGC` paces steady-state collection, `GOMEMLIMIT` enforces the ceiling. (It's *soft*: if your genuine live set exceeds the limit, you'll still OOM — the limit can't shrink data that's actually reachable.)

### Observing the GC

```bash
# Print a line per GC cycle: pause times, heap sizes, GC CPU %.
GODEBUG=gctrace=1 ./myserver
# gc 142 @8.3s 0%: 0.018+1.2+0.024 ms clock, ... 12->13->7 MB, 14 MB goal, 8 P
#                  ^STW + concurrent + STW pauses    ^heap before->after->live
```

[`runtime.ReadMemStats`](https://pkg.go.dev/runtime#ReadMemStats) (or the richer [`runtime/metrics`](https://pkg.go.dev/runtime/metrics) package) exposes the same numbers programmatically; export them to your metrics ([Observability guide](OBSERVABILITY_STUDY_GUIDE.md)) and watch GC CPU fraction and pause times. If GC CPU is high, you're allocating too much (go to Part 3); if pauses are the problem, that's rare with Go's GC and usually means an enormous live heap.

If you remember one thing from Part 4: **Go's GC is concurrent and low-latency by design, and its cost scales with how much you allocate and how much you keep alive — so the real "GC tuning" is allocating less (Part 3), with two knobs worth knowing: `GOMEMLIMIT` (set it in containers, always) and `GOGC` (raise it to trade memory for throughput).**

---

## Part 5 — Data Structures & Memory Layout

Go gives you direct control over memory layout — value types, contiguous slices, struct packing — and using it well is how you get cache-friendly, low-allocation programs. This is the part where "mechanical sympathy" (writing code that works *with* the hardware) pays off, and where your choices determine how much work Parts 3 and 4 have to do.

### Slices: Header, Backing Array, and `append`

A slice is a 3-word **header** — `{pointer, length, capacity}` (24 bytes on 64-bit) — pointing at a shared **backing array**. The header is a value (copied on assignment), but copies share the same backing array. The performance-critical behavior is `append`:

```go
// Without preallocation: O(n) reallocations as the backing array grows.
var s []int
for i := 0; i < 10000; i++ {
    s = append(s, i)          // periodically: allocate a bigger array, COPY everything over
}

// With preallocation: ONE allocation, zero copies, zero intermediate garbage.
s := make([]int, 0, 10000)    // len 0, cap 10000
for i := 0; i < 10000; i++ {
    s = append(s, i)          // never reallocates — cap is sufficient
}
```

When `append` exceeds capacity, Go allocates a new backing array (growing by ~2× for small slices, tapering to ~1.25× for large ones) and copies the elements — each growth is an allocation *and* a copy *and* garbage. **Preallocating with `make([]T, 0, n)` when you know the size is the most common and highest-value slice optimization.** Two more slice facts worth holding:

- **Subslices alias the parent's backing array.** `b := a[1:3]` shares memory with `a`; appending to `b` can overwrite `a`'s elements (the classic "append aliasing" bug — see [Go Slices: usage and internals](https://go.dev/blog/slices-intro)). Use [`slices.Clone`](https://pkg.go.dev/slices#Clone) or a 3-index slice (`a[1:3:3]`) to force a copy when you need independence.
- **`[]T` vs `[]*T` is a layout decision with big consequences.** A `[]Point` stores the structs **inline and contiguous** — one allocation, cache-friendly iteration, nothing for the GC to scan (no pointers). A `[]*Point` is N pointers to N separately-heap-allocated objects — N allocations, pointer-chasing on every access (cache misses), and N objects for the GC to trace. **For small structs, prefer value slices.** This one choice often dominates the performance of data-heavy Go.

### Maps

Go maps are hash tables with a few performance-relevant quirks:

- **Preallocate** with a size hint — `make(map[K]V, n)` — to avoid incremental rehashing/growth as you insert.
- **Map values are not addressable.** You can't take `&m[k]`, and you can't mutate a field in place (`m[k].field = x` won't compile for a struct value). You must copy out, modify, and reassign — *or* store `*V` (a pointer), which adds an allocation and indirection. Choose based on access pattern.
- **Pointers in keys/values cost the GC.** A `map[int]int` contains no pointers, so the GC can skip scanning its contents entirely; a `map[string]*Thing` makes the GC trace every entry. Pointer-free maps are markedly cheaper for GC.
- **Go 1.24 replaced the map implementation with [Swiss Tables](https://go.dev/blog/swisstable)**, giving faster lookups and lower memory — a free speedup when you upgrade, no code change.

### Struct Layout: Alignment and Padding

Struct fields are **aligned** to their size, and the compiler inserts **padding** to satisfy alignment — so field *order* changes struct *size*:

```go
type Bad struct {
    active bool      // offset 0  (1 byte) + 7 bytes padding
    id     int64     // offset 8  (8 bytes)
    ok     bool      // offset 16 (1 byte) + 7 bytes padding
}                    // total: 24 bytes

type Good struct {
    id     int64     // offset 0  (8 bytes)
    active bool      // offset 8  (1 byte)
    ok     bool      // offset 9  (1 byte) + 6 bytes padding
}                    // total: 16 bytes — 33% smaller, same fields
```

Order fields **largest-to-smallest** to minimize padding. At scale (millions of structs, or hot slices), this directly cuts memory and improves cache density. The [`fieldalignment`](https://pkg.go.dev/golang.org/x/tools/go/analysis/passes/fieldalignment) analyzer (`go vet`-style, from `golang.org/x/tools`) finds and even fixes these automatically — run it on hot types.

### Strings and `[]byte`

A `string` is an immutable `{pointer, length}` (16 bytes); a `[]byte` is mutable. Because they differ in mutability, **converting between them copies** (allocates):

```go
s := string(b)     // copies b's bytes into a new immutable string (allocation)
b := []byte(s)     // copies s's bytes into a new mutable slice (allocation)
```

In hot paths this is a hidden allocation, repeated per call. Two mitigations:

- **Build strings with [`strings.Builder`](https://pkg.go.dev/strings#Builder), never `+=` in a loop.** String concatenation with `+=` is O(n²) — each `+=` allocates a new string and copies everything so far (strings are immutable). `strings.Builder` grows one buffer:

```go
// O(n²) — allocates and copies on every iteration:
out := ""
for _, w := range words { out += w + " " }

// O(n) — one growing buffer, minimal allocation:
var b strings.Builder
b.Grow(estimatedSize)               // optional: preallocate, like make() for slices
for _, w := range words { b.WriteString(w); b.WriteByte(' ') }
out := b.String()
```

- For genuine hot paths, the [`unsafe.String`](https://pkg.go.dev/unsafe#String)/[`unsafe.Slice`](https://pkg.go.dev/unsafe#Slice) helpers (Go 1.20+) can convert *without* copying when you can guarantee the bytes won't be mutated — powerful and dangerous; reach for it only with a benchmark proving it matters.

### Mechanical Sympathy: Cache Locality

The CPU is fast; memory is slow; the cache bridges them — and *contiguous, pointer-free data is cache-friendly while pointer-chasing stalls the CPU.* This is why value slices beat pointer slices, why arrays beat linked lists in practice, and why a `map[K]*T` of scattered heap objects is slow to iterate. Two advanced points:

- **Struct-of-arrays (SoA) vs array-of-structs (AoS):** if you process *one field across many items*, storing each field in its own slice (`xs []float64; ys []float64`) packs the data you touch contiguously and can be dramatically faster (and vectorizable) than a `[]struct{X, Y float64}` where you stride past the unused field.
- **False sharing:** two goroutines updating *adjacent* fields that land on the same 64-byte cache line cause the line to ping-pong between cores, killing scaling. For hot per-CPU counters, pad structures to a cache line (`_ [64]byte`).

### Design for the Zero Value

A Go idiom with a performance payoff: types usable at their **zero value** (`sync.Mutex`, `bytes.Buffer`, `strings.Builder`) need no constructor and no allocation to initialize. `var b bytes.Buffer` is ready to use — no `new`, no heap. Designing your own types this way avoids constructor allocations and makes them cheaper to embed as struct fields.

If you remember one thing from Part 5: **layout is performance — preallocate slices, prefer value slices (`[]T`) over pointer slices (`[]*T`) for small structs, order struct fields largest-to-smallest to cut padding, build strings with `strings.Builder`, and keep the data you touch together contiguous and pointer-free for the cache.**

---

## Part 6 — Concurrency for Performance

Go's concurrency is famously easy to *write* and easy to make *slow*. Goroutines are cheap but not free; channels are elegant but not the fastest tool for every job; and the two ways concurrency hurts performance — **contention** and **unbounded spawning** — are exactly the ones beginners fall into. This part is about concurrent Go that actually scales.

### Goroutines Are Cheap, Not Free

A goroutine costs ~2 KB of stack plus scheduler bookkeeping. You can have a million — but "spawn a goroutine per item" without bound is a classic mistake: a million simultaneous goroutines means a million stacks (gigabytes), scheduler pressure, and, worse, a million simultaneous demands on whatever they call (a database with a 100-connection pool, an API with a rate limit). **Bound your concurrency** (below).

### Channels vs. Mutexes vs. Atomics

A pivotal performance insight that contradicts the "always use channels" folklore: **channels are for orchestrating ownership and lifecycle; they are not the fastest primitive for high-frequency shared state.** A channel operation involves the scheduler and internal locks — far more than an atomic increment. Choose by job, fastest first:

- **[`sync/atomic`](https://pkg.go.dev/sync/atomic)** (typed atomics like `atomic.Int64`, `atomic.Pointer[T]` since Go 1.19) — lock-free, the fastest option for counters, flags, and single-word state. A hot request counter should be an `atomic.Int64`, never a mutex-guarded int and never a channel.
- **[`sync.Mutex`](https://pkg.go.dev/sync#Mutex)** — very fast *uncontended*; the danger is *contention* (below). The default for guarding a small critical section.
- **[`sync.RWMutex`](https://pkg.go.dev/sync#RWMutex)** — allows many concurrent readers; only wins when reads vastly outnumber writes *and* the critical section is non-trivial (it has more overhead than a plain `Mutex`, so for short sections a `Mutex` is often faster even when read-heavy — measure).
- **Channels** — for passing work and ownership between goroutines, pipelines, and signaling — not for a shared counter in a tight loop.

```go
// Hot counter: atomic beats mutex beats channel by a wide margin.
var hits atomic.Int64
hits.Add(1)                  // lock-free, ~a single instruction
n := hits.Load()
```

Dave Cheney's rule of thumb is the right mental model: *"channels orchestrate; mutexes synchronize."* Reach for the channel when the problem is "who owns this work next," and the mutex/atomic when it's "protect this shared value."

### Contention Is the Scaling Killer

A single mutex on a hot path **serializes every goroutine that touches it** — adding cores then makes things *worse* (more goroutines fighting for the same lock), the concurrency version of Amdahl's law. When profiling shows lock contention (the mutex profile, Part 8), the fixes:

- **Shard/stripe the lock** — replace one mutex over a big map with N mutexes each guarding a shard, keyed by `hash(key) % N`. Contention drops by ~N×.
- **Per-goroutine/per-P local state, merged at the end** — accumulate locally (no sharing), combine once. This is how you sum across workers without a shared hot counter.
- **Atomics** instead of a mutex for single-word state.
- **[`sync.Map`](https://pkg.go.dev/sync#Map)** for the specific pattern it's built for (read-mostly, or disjoint key sets per goroutine) — but a plain `map` + `RWMutex` is often as good or better; `sync.Map` is not a general "concurrent map," and benchmarks should decide.

### `sync.Pool`: Reuse to Cut GC Pressure

The bridge between concurrency and Parts 3–4: [`sync.Pool`](https://pkg.go.dev/sync#Pool) lets goroutines **reuse temporary objects** instead of allocating fresh ones each time, slashing allocation rate and GC work. The canonical use is per-request buffers in a server:

```go
var bufPool = sync.Pool{
    New: func() any { return new(bytes.Buffer) },
}

func handle(w http.ResponseWriter, r *http.Request) {
    buf := bufPool.Get().(*bytes.Buffer)   // reuse an existing buffer if available
    buf.Reset()
    defer bufPool.Put(buf)                  // return it for the next request
    // ... use buf to build the response without allocating a new buffer each time ...
}
```

The GC may drain the pool on each cycle (so it's for *transient, reconstructible* objects, not a cache), but for high-throughput handlers it can cut allocations dramatically — a top GC-pressure remedy. Always `Reset()` pooled objects on get/put so you don't leak stale data between uses.

### Bounded Concurrency and `errgroup`

The Go answer to the "fan out without overwhelming downstream" problem from the [async comparison guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md). Don't launch unbounded goroutines; cap them. The idiomatic tool is **[`golang.org/x/sync/errgroup`](https://pkg.go.dev/golang.org/x/sync/errgroup)** — the closest thing Go has to structured concurrency: it runs a group of goroutines, **propagates the first error, cancels the rest via context, and waits for all** before returning:

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context, urls []string) ([]Result, error) {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(20)                          // at most 20 goroutines in flight — bounded
    results := make([]Result, len(urls))
    for i, url := range urls {
        i, url := i, url                    // (pre-1.22 capture; unneeded on Go 1.22+)
        g.Go(func() error {
            r, err := fetch(ctx, url)       // ctx is cancelled if any sibling fails
            if err != nil { return err }
            results[i] = r                  // distinct index per goroutine — no shared write
            return nil
        })
    }
    if err := g.Wait(); err != nil { return nil, err }   // first error; others cancelled
    return results, nil
}
```

`g.SetLimit(n)` is the bounded-concurrency knob; `errgroup.WithContext` gives you fail-fast cancellation. This is the production pattern for parallel I/O in Go — note each goroutine writes a *distinct* slice index, so there's no shared mutation and no lock needed.

### Goroutine Leaks: The Go Memory Leak

The characteristic Go resource leak: a goroutine **blocked forever** — waiting on a channel no one will send to, or stuck in a `select` with no cancellation path — never returns, so its stack and everything it captured is never freed. Spawn these in a loop and you leak memory and goroutines until OOM. Prevention is a discipline:

- **Every goroutine needs a guaranteed exit** — via `context` cancellation, a closed channel, or a timeout. Never `<-ch` in a long-lived goroutine without also selecting on `ctx.Done()`.
- **Propagate [`context.Context`](https://pkg.go.dev/context)** as the first argument through your call tree; respect `ctx.Done()`; use `context.WithTimeout`/`WithCancel` to bound work.
- **Test for leaks** with [`go.uber.org/goleak`](https://pkg.go.dev/go.uber.org/goleak) in your test suite — it fails tests that leave goroutines running.

```go
// LEAK: if no one ever sends, this goroutine blocks forever.
go func() { v := <-ch; use(v) }()

// SAFE: always has an exit path.
go func() {
    select {
    case v := <-ch: use(v)
    case <-ctx.Done(): return            // cancellation frees the goroutine
    }
}()
```

### Always Test With the Race Detector

Concurrency correctness underpins concurrency performance — a data race can corrupt the very state you're optimizing. Go ships a **[race detector](https://go.dev/doc/articles/race_detector)** that instruments memory accesses and reports races at runtime:

```bash
go test -race ./...      # run your whole suite under the race detector — do this in CI
go run -race ./...
```

It carries ~10× slowdown (so it's for tests/CI, not production), but it catches the "shared without synchronization" bugs that are otherwise nearly impossible to find. **Running tests with `-race` is non-negotiable for concurrent Go.**

If you remember one thing from Part 6: **goroutines are cheap but bound them (`errgroup` with `SetLimit`); use atomics/mutexes for shared state and channels for orchestration; kill contention by sharding or going lock-free; cut GC pressure with `sync.Pool`; guarantee every goroutine an exit via `context` to avoid leaks; and always run tests with `-race`.**

## Part 7 — The Compiler & PGO

The Go compiler prioritizes *fast compilation* over the aggressive optimization of a GCC or LLVM — but it does enough that knowing its passes helps you write code it can optimize, and one modern feature (PGO) gives a free speedup with zero code changes.

### The Optimizations That Matter

- **Inlining** — the compiler copies small function bodies into their callers, eliminating call overhead and, crucially, *enabling further optimization* (an inlined function's allocations can now be stack-allocated, its bounds checks eliminated, etc.). There's an **inlining budget** (a cost threshold); functions that are too large, or historically those with certain constructs, don't inline. See decisions with `-gcflags="-m"` (`can inline f`, `inlining call to f`). The practical implication: **keep hot, tiny helper functions simple so they inline.** Inlining is the gateway optimization — a function that doesn't inline blocks the optimizations that would follow.
- **Bounds-check elimination (BCE)** — Go inserts a bounds check on every slice/array index for memory safety, then removes the ones it can prove are safe. Idiomatic `for i, v := range s` has no per-element check; manual indexing sometimes keeps redundant checks. Rarely worth hand-tuning, but in a proven hot loop you can restructure to help the compiler prove safety (a leading `_ = s[n-1]` can hoist one check out of a loop).
- **Devirtualization** — interface method calls are *indirect* (dispatched through a method table), which costs more than a direct call and blocks inlining. When the compiler can prove the concrete type at a call site, it converts the interface call to a direct (inlinable) call. PGO makes this much more effective on hot paths.
- **Escape analysis** (Part 3), **dead-code elimination**, and **constant folding** round out the set; the linker drops unused functions, which is why Go binaries stay relatively small despite static linking.

### PGO: A Free 2–14% From Production Profiles

**[Profile-Guided Optimization](https://go.dev/doc/pgo)** (GA since Go 1.21) is the highest-leverage compiler feature and uniquely modern. You feed the compiler a **real CPU profile** from production, and it optimizes the actually-hot paths — more aggressive inlining of hot functions, better devirtualization where the profile shows the common concrete type. The workflow is delightfully simple:

```bash
# 1. Collect a CPU profile from a representative production workload (Part 8):
curl -o cpu.pprof "http://prod-host:6060/debug/pprof/profile?seconds=30"

# 2. Commit it as default.pgo in the main package directory:
mv cpu.pprof ./cmd/myserver/default.pgo

# 3. Build. The compiler auto-detects default.pgo and optimizes hot paths.
go build ./cmd/myserver
```

No code changes, no flags — the presence of `default.pgo` is enough. Typical gains are **2–14%** across the whole program, concentrated in hot code. Re-collect the profile periodically (as your workload shifts) and commit the updated `default.pgo`. **For any CPU-bound Go service, PGO is close to free money** — set it up once in CI and keep the profile fresh.

### Build Flags Worth Knowing

```bash
go build -gcflags="-m" ./...          # escape analysis + inlining decisions (your daily tool)
go build -ldflags="-s -w" ./...       # strip symbol table + DWARF → smaller binary
GOAMD64=v3 go build ./...             # target AVX2-era x86 (v1..v4) if you control the CPU
CGO_ENABLED=0 go build ./...          # force pure-Go static binary (no libc dependency)
```

### cgo Is Not a Performance Tool

A crucial myth to dispel: **calling C via [cgo](https://pkg.go.dev/cmd/cgo) is usually *slower*, not faster, for compute.** A cgo call is not an ordinary function call — it switches off the goroutine stack, pins the goroutine to its OS thread (interfering with the scheduler), and crosses a boundary the GC and inliner can't see through, costing on the order of **tens of nanoseconds per call** plus lost optimizations. The maxim is *"cgo is not Go."* Reach for cgo only to reuse an existing C library you can't reimplement — never expecting a speedup — and if you must, **batch** work into few large calls rather than many small ones to amortize the crossing. For pure computation, idiomatic Go (or Go assembly for the truly hot kernel) beats a cgo binding.

If you remember one thing from Part 7: **write inlining-friendly hot paths, lean on `-gcflags="-m"` to see what the compiler did, turn on PGO for a free 2–14% on CPU-bound services, and never reach for cgo expecting speed — its call overhead usually makes things slower.**

---

## Part 8 — Profiling & Measurement

Go has the best built-in profiling of any mainstream language, and the cardinal rule holds: **measure first.** Guessing where Go spends time or memory is a great way to optimize the wrong thing. This part is the toolkit for finding the real bottleneck before you touch Part 9.

### `pprof`: The Five Profiles

[`pprof`](https://pkg.go.dev/runtime/pprof) is Go's profiler, built into the runtime (the [diagnostics guide](https://go.dev/doc/diagnostics) surveys the whole tooling landscape). There are five profile types, each answering a different question:

| Profile | Answers | How to enable |
|---|---|---|
| **CPU** | where is CPU time spent? | `-cpuprofile`, `net/http/pprof`, `runtime/pprof` |
| **Heap** | where are allocations / in-use memory? | `-memprofile`, always available |
| **Goroutine** | what are all goroutines doing? (leaks, blocks) | always available |
| **Block** | where do goroutines block? (channels, mutexes) | `runtime.SetBlockProfileRate` |
| **Mutex** | where is lock contention? | `runtime.SetMutexProfileFraction` |

For a **live service**, expose them with a single [`net/http/pprof`](https://pkg.go.dev/net/http/pprof) import and a debug port:

```go
import _ "net/http/pprof"            // registers /debug/pprof/* handlers
go func() { http.ListenAndServe("localhost:6060", nil) }()   // debug port

// Then, against the running process:
//   go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30   (CPU)
//   go tool pprof http://localhost:6060/debug/pprof/heap                 (memory)
//   go tool pprof http://localhost:6060/debug/pprof/goroutine            (goroutines)
```

In the interactive `pprof` shell, the commands you'll use constantly: **`top`** (hottest functions), **`list <func>`** (annotated source with per-line cost), **`web`** (a call graph), and especially **`-http=:8080`** which opens a **flame graph** in the browser — the single best view for "where does the time/memory actually go." For heap profiles, distinguish `alloc_space` (total allocated over time — what drives GC) from `inuse_space` (currently live — what drives memory footprint); you usually optimize `alloc_space` to reduce GC pressure.

### Benchmarks: `testing.B` Done Right

Go's benchmark harness is part of [`testing`](https://pkg.go.dev/testing#hdr-Benchmarks). The modern form uses **[`b.Loop()`](https://pkg.go.dev/testing#B.Loop)** (Go 1.24+), which is better than the old `for i := 0; i < b.N; i++` — it manages the timer correctly, runs setup once, and prevents the compiler from optimizing away the code under test:

```go
func BenchmarkParse(b *testing.B) {
    data := loadTestData()        // setup — not timed
    b.ReportAllocs()              // report allocs/op and bytes/op alongside ns/op
    for b.Loop() {                // Go 1.24+: the right benchmark loop
        _ = Parse(data)
    }
}
```

```bash
go test -bench=. -benchmem ./...
# BenchmarkParse-8   1000000   1053 ns/op   248 B/op   3 allocs/op
#                    ^iters     ^time/op    ^bytes/op   ^allocations/op
```

**Watch `allocs/op` and `B/op` as closely as `ns/op`** — in Go, allocation count is often the truest predictor of performance, because it drives GC pressure (Parts 3–4). Driving `allocs/op` to zero on a hot path is a concrete, satisfying optimization target.

### `benchstat`: How to Honestly Claim "X% Faster"

A single benchmark run is noise. Run each benchmark multiple times and compare statistically with **[`benchstat`](https://pkg.go.dev/golang.org/x/perf/cmd/benchstat)**:

```bash
go test -bench=. -benchmem -count=10 > old.txt   # before your change
# ... make the change ...
go test -bench=. -benchmem -count=10 > new.txt   # after
benchstat old.txt new.txt                         # statistical comparison + p-values
```

`benchstat` reports the mean, variance, and whether the difference is statistically significant. **This is how you justify a performance change** — not "it looked faster once," but "−38% on ns/op, −100% on allocs/op, p<0.05 over 10 runs."

### The Execution Tracer

When the question is "why isn't my *concurrency* scaling?" — not which function is hot, but why cores sit idle — reach for the **[execution tracer](https://go.dev/blog/execution-traces-2024)** ([`runtime/trace`](https://pkg.go.dev/runtime/trace)), which visualizes scheduling, GC, syscalls, and goroutine blocking over time:

```bash
go test -trace=trace.out -bench=BenchmarkX
go tool trace trace.out      # opens a timeline: P utilization, GC, goroutine states
```

It reveals serialization (goroutines waiting on each other), GC interference, scheduler latency, and under-utilized Ps — the concurrency problems that CPU profiles don't show clearly.

### The Workflow

The loop that ties it together: **benchmark** the hot path with `-benchmem` → if `allocs/op` is high, run a **heap profile** to find the allocation sites → use **`-gcflags="-m"`** (Part 3) to see *why* they escape → fix → **`benchstat`** to confirm the win is real. For a live latency problem: **CPU profile** the running service via `net/http/pprof`, read the **flame graph**, and if cores are idle, switch to the **execution tracer**.

If you remember one thing from Part 8: **`pprof` (CPU/heap/goroutine/block/mutex, viewed as flame graphs) finds the bottleneck, `go test -bench -benchmem` with `b.Loop()` measures it with allocation counts, `benchstat` proves the change is real, and the execution tracer explains why concurrency isn't scaling — always measure before optimizing.**

---

## Part 9 — Performance Levers

The levers, ordered by effort-to-impact — highest-return first. Notice how they cluster around the Part 1 thesis: most are about **allocating less** and **concurring better**, because Go is already native code.

### Lever 1: Algorithm and Data Structure

The universal first lever, the same in every language: an O(n log n) beats an O(n²) by margins no micro-optimization can touch, and the right structure (a `map` for lookups, not a linear scan; a `set` via `map[T]struct{}`) beats a clever slow one. Profile to confirm the hot spot, then ask "is this the right algorithm?" before anything below.

### Lever 2: Reduce Allocations (the #1 Go-Specific Lever)

This is where Go performance lives (Part 3). In effort order:

- **Preallocate** slices (`make([]T, 0, n)`) and maps (`make(map[K]V, n)`) when you know the size.
- **Avoid interface boxing** in hot paths — fewer `any`/`interface{}`, prefer generics (below).
- **`strings.Builder`** for string building; never `+=` in a loop.
- **Pass buffers in** rather than returning freshly-allocated ones (`func read(buf []byte)` over `func read() []byte`).
- **Prefer value slices `[]T`** over `[]*T` for small structs (Part 5).
- Verify every change with `-gcflags="-m"` and `-benchmem`. The target is fewer `allocs/op`.

### Lever 3: Reuse With `sync.Pool`

For unavoidable transient allocations on a hot path (per-request buffers, scratch space), **`sync.Pool`** (Part 6) recycles objects across calls, cutting allocation rate and GC work — often the biggest single GC-pressure win in a busy server.

### Lever 4: Right-Size Concurrency

- **Bound it** with `errgroup.SetLimit` or a semaphore — never unbounded goroutines (Part 6).
- **Kill contention** — shard hot mutexes, or use atomics for single-word state.
- **Don't overuse channels** in hot inner loops; atomics/mutexes are faster for shared state.
- Use the **block** and **mutex** profiles (Part 8) to find contention.

### Lever 5: Tune the Runtime for the Deployment

Free wins from environment variables, no code change:

- **`GOMEMLIMIT`** — set it in every container to avoid OOM kills (Part 4). The highest-value runtime setting.
- **`GOMAXPROCS`** — match your real CPU budget; Go 1.25+ does this from cgroups automatically, older versions need `automaxprocs` (Part 2).
- **`GOGC`** — raise it (e.g., 200–400) to trade memory for throughput when you have RAM to spare (Part 4).

### Lever 6: Turn On PGO

A free 2–14% on CPU-bound services for the cost of committing a `default.pgo` profile and rebuilding (Part 7). Set it up in CI.

### Lever 7: Avoid Reflection in Hot Paths

Reflection ([`reflect`](https://pkg.go.dev/reflect)) is powerful and slow, and [`encoding/json`](https://pkg.go.dev/encoding/json) uses it heavily — JSON marshaling is a frequent Go hot spot. Options when JSON is your bottleneck: a faster drop-in (`jsoniter`, or `bytedance/sonic` which uses JIT/assembly), code generation (`easyjson`, `ffjson`), or hand-written marshaling for the hottest types. More broadly, prefer **generics** (Go 1.18+) over `interface{}`+reflection where you control the code — generics are monomorphized at compile time, so they avoid both boxing and reflection.

### Lever 8: Buffer Your I/O

Unbuffered small reads/writes each become a syscall. Wrap raw I/O in [`bufio.Reader`/`bufio.Writer`](https://pkg.go.dev/bufio) (or `bytes.Buffer`) to batch them — often a dramatic win for line-by-line file or network processing. Pair with `io.Copy` (which uses an internal buffer) for streaming.

### Lever 9: Reduce Copying and Cache-Friendly Layout

- Pass **pointers for genuinely large structs** to avoid copies (but check `-gcflags="-m"` that it doesn't force a heap escape).
- Avoid repeated **`string`↔`[]byte`** conversions (Part 5); reuse buffers.
- Lay out data **contiguously and pointer-free** for the cache; consider struct-of-arrays for field-at-a-time processing; pack struct fields largest-to-smallest (Part 5).

### Lever 10: The Compiler and the Last Resort

Microarchitecture targeting (`GOAMD64=v3`), keeping hot functions inlinable (Part 7), and — only for the hottest proven kernel, and only with a benchmark — `unsafe` or hand-written Go **assembly** (which is how the standard library implements crypto and hashing). These are sharp tools for the final few percent, not starting points.

### The Anti-Lever: Don't Reach for cgo

Worth restating as a lever *not* to pull: **cgo makes compute slower**, not faster, because of per-call overhead (Part 7). If you're tempted to "drop into C for speed," that instinct (correct in Python) is backwards in Go.

If you remember one thing from Part 9: **the Go levers, in order, are algorithm → reduce allocations → `sync.Pool` → right-size concurrency → tune the runtime (`GOMEMLIMIT`!) → PGO → avoid reflection → buffer I/O → reduce copying → compiler/asm — and almost all of them reduce to "allocate less and concur better," because the language is already fast.**

## Part 10 — High-Performance Recipes

The payoff. Each recipe is a complete, worked pattern — with the before/after and the numbers that matter (in Go, that's `ns/op` *and* `allocs/op`). They're ordered from "you'll use this every day" to "you'll use this when the stakes are high."

### Recipe 1: Preallocate Slices

The most common Go allocation win:

```go
// BEFORE — repeated reallocation + copying as the slice grows:
func ids(users []User) []int {
    var out []int
    for _, u := range users { out = append(out, u.ID) }   // ~log2(n) reallocs, lots of garbage
    return out
}
//  BenchmarkBefore   ... 5200 ns/op   16312 B/op   12 allocs/op

// AFTER — one allocation, zero copies:
func ids(users []User) []int {
    out := make([]int, 0, len(users))                      // exact capacity up front
    for _, u := range users { out = append(out, u.ID) }
    return out
}
//  BenchmarkAfter    ... 1100 ns/op    8192 B/op    1 alloc/op   (≈5× faster, 12→1 allocs)
```

### Recipe 2: Build Strings With `strings.Builder`

```go
// BEFORE — O(n²): each += allocates a new string and copies everything so far.
func join(parts []string) string {
    s := ""
    for _, p := range parts { s += p + "," }
    return s
}

// AFTER — O(n): one growing buffer.
func join(parts []string) string {
    var b strings.Builder
    b.Grow(len(parts) * 8)                 // optional size hint, like make() for slices
    for _, p := range parts { b.WriteString(p); b.WriteByte(',') }
    return b.String()
}
// For 10k parts: from thousands of allocations to a handful.
```

### Recipe 3: Pool Per-Request Buffers

The top GC-pressure remedy for busy servers:

```go
var bufPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}

func render(w http.ResponseWriter, data any) {
    buf := bufPool.Get().(*bytes.Buffer)
    defer func() { buf.Reset(); bufPool.Put(buf) }()   // reset + return for reuse
    json.NewEncoder(buf).Encode(data)                   // build into the reused buffer
    w.Write(buf.Bytes())
}
// Under load this turns "one buffer allocation per request" into "almost none" —
// directly cutting GC frequency (Parts 3-4).
```

### Recipe 4: Bounded Parallel Fan-Out with `errgroup`

The production pattern for parallel I/O — concurrency, error propagation, and cancellation, bounded:

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context, urls []string) ([]*Resp, error) {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(20)                                  // at most 20 in flight — protects downstream
    out := make([]*Resp, len(urls))
    for i, u := range urls {
        i, u := i, u
        g.Go(func() error {
            r, err := fetch(ctx, u)                 // ctx cancels if any sibling errors
            if err != nil { return err }
            out[i] = r                               // distinct index → no shared write, no lock
            return nil
        })
    }
    if err := g.Wait(); err != nil { return nil, err }
    return out, nil
}
```

### Recipe 5: Atomic Counter Instead of a Mutex

For a hot single-word counter (metrics, IDs), atomics crush a mutex:

```go
// BEFORE — mutex per increment; contended under load.
type Counter struct { mu sync.Mutex; n int64 }
func (c *Counter) Inc() { c.mu.Lock(); c.n++; c.mu.Unlock() }

// AFTER — lock-free; a single atomic instruction.
type Counter struct { n atomic.Int64 }
func (c *Counter) Inc() { c.n.Add(1) }
func (c *Counter) Value() int64 { return c.n.Load() }
// Several times faster uncontended, and it actually scales under contention.
```

### Recipe 6: Hunt and Kill an Allocation

The core Go optimization loop, end to end:

```go
// 1. Benchmark shows allocs/op > 0 on a hot function. Find out why:
//      go build -gcflags="-m" ./...
//    Output: "./parse.go:14:9: buf escapes to heap"
//
// 2. The escape: returning a freshly-allocated buffer each call.
func parse(data []byte) []byte {
    buf := make([]byte, 0, 256)            // escapes — returned to caller
    // ... fill buf ...
    return buf
}
//
// 3. The fix: let the caller own and reuse the buffer (pass it in).
func parse(dst, data []byte) []byte {      // caller reuses dst across calls (or pools it)
    dst = dst[:0]
    // ... append into dst ...
    return dst
}
// 4. Re-benchmark with -benchmem and confirm with benchstat. allocs/op → 0.
```

### Recipe 7: Faster JSON

`encoding/json` is reflection-based and often a hot spot. Options, in order of effort:

```go
// Easiest: reuse encoders/decoders and stream, don't re-parse into intermediate maps.
dec := json.NewDecoder(r)       // streams; avoids buffering the whole payload as a string

// Bigger win when JSON is the bottleneck: a drop-in faster library.
import jsoniter "github.com/json-iterator/go"
var json = jsoniter.ConfigCompatibleWithStandardLibrary   // same API, faster
// (or bytedance/sonic for JIT/asm-accelerated; or easyjson for codegen — no reflection)

// Best of all when you control the types: generics over interface{}+reflection.
```

### Recipe 8: Buffer Your I/O

```go
// BEFORE — one syscall per write; brutal for line-by-line output.
for _, line := range lines { conn.Write([]byte(line + "\n")) }

// AFTER — batched into far fewer syscalls.
w := bufio.NewWriter(conn)
for _, line := range lines { w.WriteString(line); w.WriteByte('\n') }
w.Flush()                       // don't forget to flush!
```

### Recipe 9: Tune the Runtime in a Container

The two settings every containerized Go service should set (and a Go-version note):

```dockerfile
# In a pod/container with a 1Gi memory limit and a 2-CPU quota:
ENV GOMEMLIMIT=900MiB          # soft limit with headroom — prevents OOM kills (Part 4)
# GOMAXPROCS: automatic from the cgroup quota on Go 1.25+.
# On older Go, either set it explicitly or import go.uber.org/automaxprocs:
ENV GOMAXPROCS=2
```

`GOMEMLIMIT` alone eliminates a whole class of mysterious Kubernetes OOM-kills, where a Go process allocated past its memory limit between GC cycles. See the [Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md) for setting the limits these mirror.

### Recipe 10: Enable PGO

```bash
# 1. Profile a representative production workload for 30s (needs net/http/pprof):
curl -o ./cmd/server/default.pgo "http://prod:6060/debug/pprof/profile?seconds=30"
# 2. Commit default.pgo next to main; the compiler picks it up automatically:
go build ./cmd/server          # auto-detects default.pgo → 2-14% faster, no code change
# 3. Refresh the profile periodically as the workload evolves.
```

### Recipe 11: Shard a Contended Map

When the mutex profile shows one map's lock is the bottleneck:

```go
// A striped map: N independent shards, each with its own lock → ~N× less contention.
type ShardedMap[V any] struct {
    shards [256]struct {
        mu sync.RWMutex
        m  map[string]V
    }
}
func (s *ShardedMap[V]) shard(key string) *struct{ mu sync.RWMutex; m map[string]V } {
    return &s.shards[fnv32(key)%256]                 // hash key → shard
}
func (s *ShardedMap[V]) Get(key string) (V, bool) {
    sh := s.shard(key); sh.mu.RLock(); defer sh.mu.RUnlock()
    v, ok := sh.m[key]; return v, ok
}
// Reads/writes to different keys now rarely touch the same lock.
```

### The Decision Tree

When a Go program is too slow, work through this:

```text
1. Profile it (Part 8): CPU flame graph + -benchmem (watch allocs/op!)
   │
2. Wrong algorithm / data structure? (O(n²), linear scan instead of a map)
   │ yes → fix it, re-measure
   │ no ↓
3. High allocs/op? (this is the usual Go culprit)
   │ yes → -gcflags="-m" to find escapes → preallocate, strings.Builder,
   │        pass buffers in, sync.Pool, avoid interface boxing → re-measure
   │ no ↓
4. High GC CPU / pauses? (gctrace)
   │ yes → reduce allocations (step 3) and live heap; set GOMEMLIMIT; maybe raise GOGC
   │ no ↓
5. Not scaling across cores? (execution tracer shows idle Ps)
   │ yes → lock contention (mutex profile) → shard/atomics; or unbounded/blocked
   │        goroutines → errgroup.SetLimit, fix leaks; check GOMAXPROCS
   │ no ↓
6. CPU-bound hot function? (CPU profile)
   │ yes → enable PGO; avoid reflection (JSON); keep it inlinable; buffer I/O
   │ no ↓
7. Still hot, last resort?
   │ → GOAMD64=v3, unsafe/assembly for the proven kernel (NOT cgo — it's slower)
   │ no ↓
8. Accept it, or move the work (cache it, precompute, push to a faster store).
```

If you remember one thing from Part 10: **profile first (and watch `allocs/op`), then pick the cheapest lever — preallocation, `strings.Builder`, `sync.Pool`, bounded `errgroup`, atomics, and `GOMEMLIMIT` cover the overwhelming majority of real Go performance wins, and almost all of them come back to allocating less.**

---

## Where to Go Next

- **Read the [Guide to the Go Garbage Collector](https://go.dev/doc/gc-guide)** end to end — it is the official, definitive treatment of Parts 3–4, written by the GC's authors, and short enough to finish in an evening.
- **Work through Dave Cheney's [High Performance Go Workshop](https://dave.cheney.net/high-performance-go-workshop/dotgo-paris.html)** — the exercises walk you through benchmarking, escape analysis, and pprof on real code, turning this guide's claims into hands-on instinct. *[Efficient Go](https://www.oreilly.com/library/view/efficient-go/9781098105709/)* (Płotka) is the book-length follow-up.
- **Read the primary sources while they're fresh:** the [Go Memory Model](https://go.dev/ref/mem), the [diagnostics guide](https://go.dev/doc/diagnostics), the [PGO docs](https://go.dev/doc/pgo), and the scheduler's own design doc-quality comments at the top of [`src/runtime/proc.go`](https://go.dev/src/runtime/proc.go) — the runtime source is unusually readable and the comments are the best GMP documentation that exists.
- **Profile one real service deeply.** Wire up `net/http/pprof`, put production-shaped load on it, and drive `allocs/op` down on its hottest path using the Part 10 loop — benchmark, `-gcflags="-m"`, fix, `benchstat`. One completed cycle teaches more than any amount of reading.
- **Adjacent guides in this repo:** [Golang for Python Developers](GOLANG_FOR_PYTHON_DEVS.md) (the language on-ramp), [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) and [Advanced Node.js](ADVANCED_NODEJS_STUDY_GUIDE.md) (the sibling runtime deep-dives this guide contrasts against), and the [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md), [Observability](OBSERVABILITY_STUDY_GUIDE.md), and [Kubernetes](k8s/KUBERNETES_STUDY_GUIDE.md) guides for where production Go actually runs.

That's the guide. From here the highest-leverage next step is the loop that ties it all together: take a hot path you own, run `go test -bench -benchmem`, look at `allocs/op`, run `go build -gcflags="-m"` to see why those allocations happen, kill the biggest one, and confirm with `benchstat`. Do that a few times and the Go performance model becomes instinct — and you'll find that the thesis from Part 1 holds almost every time: the language was already fast, and your job was to stop making garbage. Pair this with the [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) and [Advanced Node.js](ADVANCED_NODEJS_STUDY_GUIDE.md) guides and you'll carry the same discipline — measure, find the bottleneck class, apply the matching lever — across all three runtimes, even though what you're fighting (the interpreter, the event loop, the allocator) is different in each.


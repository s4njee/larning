# Five Study Guides a Senior Dev Would Actually Learn From

The guides below are pitched at engineers who already know the tools and want to understand the machines beneath them. None of these are "intro to X" topics — each one unlocks a level of reasoning about systems that experienced developers rarely pick up by accident, because the knowledge lives in papers, source code, and painful production incidents rather than tutorials.

---

## 1. Database Internals

**Why a senior dev needs this:** Knowing SQL is table stakes. Understanding *why* a query plan degrades, when an index scan beats a sequential scan, or what "write amplification" actually means at the byte level is what separates engineers who tune databases from engineers who cargo-cult index suggestions from `EXPLAIN ANALYZE`.

**What the guide covers:** The B-tree and its cousin the B+-tree — not as abstract data structures but as on-disk page layouts, with split and merge mechanics. LSM-trees and why RocksDB (and every modern key-value store) chose them over B-trees: write amplification vs. read amplification, compaction strategies, bloom filters. MVCC: how Postgres implements snapshot isolation by keeping multiple row versions, what the `xmin`/`xmax` system columns actually are, and why `VACUUM` exists. The write-ahead log as a first-class data structure — how WAL enables point-in-time recovery, logical replication, and crash consistency, and what happens at the byte level when a transaction commits. Buffer pool management: the clock-sweep eviction policy, dirty-page tracking, and the double-write buffer MySQL needs that Postgres avoids. Query execution: iterator/volcano model, hash joins vs. merge joins vs. nested-loop joins, when parallelism helps and when it creates contention.

**Why this is interesting:** Andy Pavlo's CMU 15-445/645 database course covers most of this at graduate level and the lectures are public. The guide synthesizes that material with Postgres source code pointers so the reader can follow any claim into the actual implementation.

---

## 2. Linux Kernel Internals and Systems Performance

**Why a senior dev needs this:** Every service runs on Linux. Senior engineers who can read a flame graph, interpret `perf stat` output, and reason about scheduler latency or memory pressure make better architectural decisions — and they're the ones who can diagnose the 1-in-10,000 CPU spike that only shows up in production. The existing Linux guides cover userland; this one goes below.

**What the guide covers:** The Completely Fair Scheduler: how CFS uses a red-black tree keyed on virtual runtime, what `nice` values actually change, and why a CPU-bound thread can starve an I/O-bound one on the wrong configuration. `io_uring`: the shared ring buffer design, submission queues, completion queues, and why the kernel-bypass model cuts syscall overhead by 60–80% for high-IOPS workloads. Virtual memory: page tables, TLB shootdowns, huge pages (transparent and explicit), NUMA topology, and the `mmap`/`brk` distinction that matters once your allocator crosses 128 KB. The VFS layer: how `open`, `read`, and `write` traverse dentries, inodes, and page cache, and what `O_DIRECT` bypasses. Performance tools: `perf record` and `perf report`, `bpftrace` one-liners, `vmstat`/`iostat`/`ss` interpreted rather than just listed. Profiling methodology: Brendan Gregg's USE method, how to build and read a flame graph, and the common false-positive traps (inlined functions, JIT, kernel stacks without frame pointers).

**Why this is interesting:** This is the material that separates a senior dev from an SRE at a place that cares about tail latency. It also makes the eBPF guide much more legible — every bpftrace hook becomes obvious once you know what it's hooking into.

---

## 3. Distributed Algorithms

**Why a senior dev needs this:** The distributed systems guide teaches you what CAP theorem says. This guide teaches you *why* it's true, and what the actual tradeoffs look like when you implement consensus, replication, or conflict resolution rather than just reading about it. Engineers who understand Raft at the protocol level understand why Etcd is the right place to store Kubernetes state and why you should never use it for application data.

**What the guide covers:** The Raft consensus algorithm: leader election with randomized timeouts, log replication, the commit rule (majority acknowledgement), and what happens during a network partition — step by step, with message diagrams. Why Paxos was correct but hard to implement: the multi-round structure, the "prepare" phase, and the subtle distinction between Paxos and Multi-Paxos that took the field years to make explicit. Vector clocks and causal ordering: how to track happens-before relationships, why Lamport clocks are insufficient, and how Dynamo and Riak used vector clocks to detect concurrent writes. CRDTs: the mathematical property that makes conflict-free merge possible, the difference between state-based and op-based CRDTs, and concrete data structures (G-counter, LWW-register, OR-Set) with worked examples. Gossip protocols: the probabilistic convergence math, why Cassandra's anti-entropy repair uses Merkle trees, and the bandwidth/latency tradeoff vs. consensus. Two-phase commit and why it's blocking: the coordinator-failure scenario, 3PC as a partial fix, and why distributed databases now prefer Paxos-based variants.

**Why this is interesting:** Kyle Kingsbury's Jepsen test reports are the practical literature that makes this material real — every distributed database failure mode documented there maps to a protocol gap covered in this guide. Martin Kleppmann's *Designing Data-Intensive Applications* covers similar ground; the guide complements it with runnable pseudocode and proofs of the key safety properties.

---

## 4. Compiler and Language Internals

**Why a senior dev needs this:** Every language is a leaky abstraction over what the compiler actually produces. Senior developers who understand parsing, type inference, and code generation write better abstractions, debug harder optimization problems, and make better decisions when evaluating languages for a project. They also understand why TypeScript's structural type system and Rust's borrow checker behave exactly the way they do, rather than memorizing the rules.

**What the guide covers:** Lexing and parsing: hand-rolling a recursive-descent parser for a small expression language to make the theory concrete, then mapping that to how Python's CPython, TypeScript's tsc, and Rust's rustc structure their frontends. Abstract syntax trees: how compilers represent programs in memory, visitor patterns, and why an AST is not the same as a parse tree. Type systems: structural vs. nominal typing with TypeScript and Java as examples, Hindley-Milner type inference (how the compiler deduces types the programmer never wrote), and how Rust's lifetime system is an affine type system that prevents use-after-free at compile time. Intermediate representations: SSA form, why optimizations are easier on SSA, and how LLVM IR bridges language frontends to machine code. Core optimizations: constant folding, dead code elimination, inlining, and loop unrolling — not as black-box flags but as transformations on the IR with before/after examples. Bytecode and JIT: how V8 transitions from interpreter to Maglev to Turbofan based on type feedback, what "hidden classes" are and why object shape affects JIT performance, and how the JVM's HotSpot JIT uses profiling data to deoptimize and recompile.

**Why this is interesting:** The guide makes every "why is this code slow" mystery tractable. Once you've seen how a JIT's hidden-class model works, you'll never write `obj[key] = value` in a hot loop the same way again.

---

## 5. Hardware Architecture for Software Engineers

**Why a senior dev needs this:** Modern CPUs are speculative, out-of-order, multi-level-cached machines that look nothing like the sequential model most programmers reason with. The code that matters — the hot path, the lock-free data structure, the SIMD batch operation — requires knowing what the CPU actually does with your instructions. This guide covers the physical machine that every abstraction layer eventually runs on.

**What the guide covers:** The cache hierarchy: L1/L2/L3 sizes, latencies (1–50 ns), and the cost of a cache miss all the way to main memory (100 ns) or a TLB miss. Cache-line granularity (64 bytes on x86/ARM): why false sharing between threads on the same cache line is invisible to the compiler and catastrophic at scale, how to align structs to avoid it, and why `std::hardware_destructive_interference_size` exists in C++17. Out-of-order execution: the reorder buffer, reservation stations, and why the CPU can have 200+ instructions in flight while executing them in whatever order satisfies data dependencies. Branch prediction: tournament predictors, the indirect branch predictor, why unpredictable branches cost 15–20 cycles, and when to use `__builtin_expect` or branchless code. Memory ordering: the x86 TSO model vs. ARM's weak ordering, what `std::memory_order_acquire`/`release`/`seq_cst` actually compile to, and why a lock-free queue needs a memory barrier even when the logic looks correct. SIMD: SSE2, AVX2, AVX-512 — 128/256/512-bit registers, auto-vectorization conditions, and a worked example of manually vectorizing a UTF-8 validation loop to process 32 bytes per instruction.

**Why this is interesting:** The `perf stat` tool surfaces the effects of everything in this guide — cache-miss rate, branch misprediction rate, instructions-per-cycle — so the guide ends with a methodology for profiling at the hardware counter level, connecting physical theory to practical measurement.

# eBPF

A depth-first guide to eBPF — the technology that lets you run sandboxed programs inside the Linux kernel without modifying the kernel source or loading kernel modules. eBPF has quietly become the most transformative infrastructure technology of the last decade, powering the networking (Cilium), security (Tetragon, Falco), observability (Pixie, Grafana Beyla), and even the scheduler (sched_ext) of modern Linux systems. This guide explains what eBPF is, how it works at a mechanical level, how to write and use eBPF programs, and why in 2026 it is the foundational layer beneath most production Kubernetes clusters.

Assumes you understand Linux fundamentals — processes, syscalls, file descriptors, the kernel/userspace boundary, basic networking. You don't need to have written any eBPF code before.

Primary references: Liz Rice's [Learning eBPF](https://www.oreilly.com/library/view/learning-ebpf/9781098135119/), Brendan Gregg's [BPF Performance Tools](https://www.brendangregg.com/bpf-performance-tools-book.html), the [ebpf.io](https://ebpf.io) documentation, and the [kernel documentation](https://www.kernel.org/doc/html/latest/bpf/).

---

## Table of Contents

1. [Part 1 — What eBPF Is and Why It Matters](#part-1--what-ebpf-is-and-why-it-matters)
2. [Part 2 — The Architecture](#part-2--the-architecture)
3. [Part 3 — Program Types and Hook Points](#part-3--program-types-and-hook-points)
4. [Part 4 — Maps: Sharing State](#part-4--maps-sharing-state)
5. [Part 5 — The Verifier: Why eBPF Is Safe](#part-5--the-verifier-why-ebpf-is-safe)
6. [Part 6 — bpftrace: The Tracing Swiss Army Knife](#part-6--bpftrace-the-tracing-swiss-army-knife)
7. [Part 7 — BCC Tools: The Pre-Built Toolkit](#part-7--bcc-tools-the-pre-built-toolkit)
8. [Part 8 — Writing eBPF Programs](#part-8--writing-ebpf-programs)
9. [Part 9 — Networking with eBPF](#part-9--networking-with-ebpf)
10. [Part 10 — Security with eBPF](#part-10--security-with-ebpf)
11. [Part 11 — Observability with eBPF](#part-11--observability-with-ebpf)
12. [Part 12 — sched_ext: Custom Schedulers in eBPF](#part-12--sched_ext-custom-schedulers-in-ebpf)
13. [Part 13 — eBPF Security Considerations](#part-13--ebpf-security-considerations)
14. [Part 14 — The 2026 eBPF Ecosystem](#part-14--the-2026-ebpf-ecosystem)

---

## Part 1 — What eBPF Is and Why It Matters

### The Problem

The Linux kernel is the most performance-critical software on every server. Networking decisions, security enforcement, process scheduling, storage I/O — all of it runs in kernel space. But modifying the kernel is prohibitively difficult: changes require upstream review (months to years), kernel recompilation, and a reboot. Kernel modules can be loaded dynamically, but they run with full kernel privileges — a bug in a module crashes the entire system.

The result: for decades, the kernel evolved slowly while application requirements evolved quickly. When Kubernetes needed per-pod network policies, the only option was iptables — a tool designed in 1998. When security teams needed syscall-level visibility, the only option was auditd — a tool that drops events under load. When SREs needed per-request latency tracing, they had to instrument application code.

### The Solution

eBPF lets you **run custom programs inside the kernel** — at specific hook points (syscalls, network events, scheduler decisions, filesystem operations) — with three guarantees that kernel modules cannot provide:

1. **Safety.** An in-kernel verifier statically analyzes every eBPF program before it runs, proving that it terminates, doesn't access invalid memory, and can't crash the kernel.
2. **Performance.** eBPF programs are JIT-compiled to native machine code and run in kernel context — no userspace/kernel boundary crossing per event.
3. **No reboot.** Programs are loaded and attached dynamically. Unload them and the kernel returns to its previous state.

This is why eBPF is called "the JavaScript of the kernel" — not because of the language (it's typically written in C or Rust), but because of the model: a safe, sandboxed runtime embedded in a larger system, letting you extend it without modifying its source code.

### Why 2026 Is the eBPF Moment

eBPF existed since kernel 3.15 (2014), but critical capabilities arrived incrementally:

| Kernel | Year | What Became Possible |
|---|---|---|
| 3.15 | 2014 | eBPF introduced (extended from classic BPF) |
| 4.1 | 2015 | kprobes, tracepoints — tracing use cases |
| 4.8 | 2016 | XDP — high-performance networking |
| 5.2 | 2019 | `BPF_PROG_TYPE_STRUCT_OPS` — plugging into kernel subsystems |
| 5.4 | 2019 | BTF, CO-RE — portable programs across kernel versions |
| 5.8 | 2020 | `CAP_BPF` capability — fine-grained permissions |
| 5.13 | 2021 | Bounded loops — practical general programming |
| 6.6 | 2023 | EEVDF scheduler — foundation for sched_ext |
| 6.12 | 2024 | `sched_ext` — user-defined schedulers in eBPF |

By 2026, every major Linux distribution ships with BTF-enabled kernels, every major cloud provider defaults to Cilium (eBPF networking) for Kubernetes, and the tooling (bpftrace, BCC, libbpf) is mature and well-documented. eBPF has graduated from "interesting experiment" to "the way production infrastructure works."

---

## Part 2 — The Architecture

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Space                                  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  bpftrace    │  │  Cilium      │  │  Your app    │               │
│  │  (tracing)   │  │  (networking)│  │  (libbpf/Go) │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                       │
│         │  bpf() syscall  │                  │                       │
│─────────┼─────────────────┼──────────────────┼───────────────────────│
│         ▼                 ▼                  ▼                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                      Verifier                                │    │
│  │  Static analysis: proves safety, terminates, memory-safe    │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │ (pass)                                │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    JIT Compiler                              │    │
│  │  eBPF bytecode → native x86/ARM machine code                │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                       │
│                             ▼                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ kprobe   │  │ XDP      │  │ TC       │  │ sched_ext│   ...     │
│  │ hook     │  │ hook     │  │ hook     │  │ hook     │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                      │
│                    ┌──────────────────────┐                          │
│                    │       Maps           │  ← shared state         │
│                    │  (hash, array, ring) │    between programs     │
│                    └──────────────────────┘    and userspace        │
│                                                                      │
│                          Kernel Space                                │
└─────────────────────────────────────────────────────────────────────┘
```

### The Lifecycle of an eBPF Program

1. **Write** the program (in C, Rust, or a high-level DSL like bpftrace).
2. **Compile** to eBPF bytecode (an architecture-independent instruction set, like JVM bytecode).
3. **Load** into the kernel via the `bpf()` syscall. The **verifier** analyzes the program.
4. If the verifier accepts it, the **JIT compiler** translates the bytecode to native machine code (x86, ARM, etc.).
5. **Attach** the program to a **hook point** — a specific kernel event (syscall entry, packet arrival, function call).
6. When the event fires, the eBPF program executes **in kernel context** — with access to kernel data structures, but sandboxed by the verifier's constraints.
7. The program communicates results to userspace via **maps** (shared data structures) or **ring buffers** (event streams).

### The eBPF Instruction Set

eBPF has its own instruction set architecture (ISA): 11 registers (r0-r10), 64-bit operations, and a restricted set of instructions. It resembles a simplified RISC ISA. You almost never write eBPF assembly directly — you write C and compile with Clang/LLVM, which has a native eBPF backend.

```
r0:       return value (also used for helper function return values)
r1-r5:    function arguments (used for helper calls)
r6-r9:    callee-saved registers (preserved across function calls)
r10:      read-only frame pointer (stack access)

Stack:    512 bytes maximum (per program)
```

The 512-byte stack limit is a hard constraint — it prevents kernel stack overflow. Programs that need more storage use maps.

### Helper Functions

eBPF programs can't call arbitrary kernel functions. Instead, they call **helper functions** — a curated, stable API of kernel operations:

```c
// examples of BPF helper functions
bpf_map_lookup_elem()        // look up a value in a map
bpf_map_update_elem()        // insert/update a value in a map
bpf_get_current_pid_tgid()   // get the current process PID
bpf_get_current_comm()       // get the current process name
bpf_ktime_get_ns()           // get current time in nanoseconds
bpf_probe_read_kernel()      // safely read kernel memory
bpf_probe_read_user()        // safely read userspace memory
bpf_trace_printk()           // debug printing (trace_pipe)
bpf_ringbuf_output()         // send event to userspace via ring buffer
bpf_redirect()               // redirect a network packet
bpf_skb_store_bytes()        // modify packet data
bpf_get_stackid()            // capture a stack trace
bpf_send_signal()            // send a signal to the current process
```

Each program type has access to a subset of helpers — an XDP program can call `bpf_redirect()` but not `bpf_send_signal()`, and a tracing program can call `bpf_send_signal()` but not `bpf_redirect()`.

---

## Part 3 — Program Types and Hook Points

Each eBPF program type corresponds to a specific place in the kernel where it can be attached. The program type determines what context data is available, which helper functions can be called, and what actions the program can take.

### Tracing Program Types

| Type | Hook Point | Use Case | Stability |
|---|---|---|---|
| **kprobe** | Entry of any kernel function | Dynamic tracing — "what happens when the kernel calls `tcp_sendmsg`?" | **Unstable** — kernel functions can change between versions |
| **kretprobe** | Return of any kernel function | Measure function latency, inspect return values | Unstable |
| **tracepoint** | Predefined stable trace points in the kernel | "Trace all `sched:sched_switch` events" | **Stable** — maintained as a kernel ABI |
| **raw_tracepoint** | Same as tracepoint but with raw arguments (faster) | High-performance tracing | Stable |
| **fentry/fexit** | Function entry/exit (faster than kprobe, kernel 5.5+) | Modern replacement for kprobe/kretprobe | Unstable (but faster) |
| **uprobe/uretprobe** | Entry/return of any **userspace** function | Trace application code without modifying it | Application-dependent |
| **perf_event** | Hardware/software performance counters | CPU profiling, cache miss counting | Stable |
| **usdt** | User Statically Defined Tracepoints | Application-defined trace points (like DTrace probes) | Application-defined |

**kprobes vs. tracepoints:** kprobes can attach to *any* kernel function (maximum flexibility), but the function signature can change between kernel versions (fragile). Tracepoints are explicitly defined stable interfaces (fewer hook points, but guaranteed stable). **Prefer tracepoints when available; use kprobes when you need to trace a specific internal function.**

**fentry/fexit** (kernel 5.5+) are the modern replacement for kprobes. They're faster (no `int3` breakpoint instruction), have direct access to function arguments as typed parameters, and work better with CO-RE. Use them when your kernel supports them.

### Networking Program Types

| Type | Hook Point | Use Case | Performance |
|---|---|---|---|
| **XDP** | Network driver (before `sk_buff` allocation) | Packet filtering, DDoS mitigation, load balancing | **Fastest** — 10M+ pps per core |
| **TC** (Traffic Control) | Kernel networking stack (ingress/egress) | Packet manipulation, policy enforcement, NAT | Fast — after `sk_buff` is allocated, full packet access |
| **socket filter** | Socket layer | Per-socket packet filtering | Moderate |
| **sk_msg** | Socket message redirect | L7 proxy, transparent redirection | Moderate |
| **cgroup/sock** | cgroup socket operations | Per-cgroup networking policy | Moderate |
| **cgroup/skb** | cgroup packet filtering | Container network policy | Moderate |
| **lwt** (Lightweight Tunnel) | Routing layer | Packet encapsulation/decapsulation | Moderate |

**XDP** deserves special attention. It runs at the *earliest possible point* in the network stack — in the network driver, before the kernel even allocates the `sk_buff` data structure that normally represents a packet. This means:

```
Without XDP:
  NIC → driver → alloc sk_buff → GRO → netfilter → routing → transport → socket → app
                  ↑ expensive per-packet overhead

With XDP:
  NIC → driver → XDP program → DROP (never enters the stack)
                             → PASS (continue normal processing)
                             → TX (reflect back out the NIC)
                             → REDIRECT (forward to another NIC or CPU)
```

XDP can drop malicious packets at **10+ million packets per second per core** — compared to iptables' ~1-2 million. This is why Cloudflare, Meta, and major CDNs use XDP for DDoS mitigation.

XDP has three execution modes:
- **Native** (driver mode): runs in the NIC driver. Fastest. Requires driver support.
- **Offloaded**: runs on the NIC hardware itself (SmartNICs like Netronome). Fastest possible.
- **Generic** (skb mode): runs later in the stack. Slowest, but works with any NIC. For development/testing.

### Security Program Types

| Type | Hook Point | Use Case |
|---|---|---|
| **LSM** (Linux Security Module) | Security hook points (file_open, bprm_check, etc.) | Runtime security policy enforcement |
| **cgroup** | cgroup events | Per-container policy (device access, sysctl, socket) |

### Scheduling

| Type | Hook Point | Use Case |
|---|---|---|
| **sched_ext** | Scheduler operations (enqueue, dequeue, dispatch) | Custom scheduling policies (kernel 6.12+) |
| **struct_ops** | Kernel subsystem operation structures | Plugging into TCP congestion control, scheduling, etc. |

---

## Part 4 — Maps: Sharing State

eBPF programs are event-driven — they fire, run, and return. To persist data across invocations or share data with userspace, they use **maps**: key-value data structures that live in the kernel and are accessible from both eBPF programs and userspace applications.

### Map Types

| Map Type | Description | Use Case |
|---|---|---|
| **`BPF_MAP_TYPE_HASH`** | Key-value hash table | Per-IP counters, connection tracking, flow tables |
| **`BPF_MAP_TYPE_ARRAY`** | Fixed-size array indexed by integer | Configuration, per-CPU statistics, lookup tables |
| **`BPF_MAP_TYPE_PERCPU_HASH`** | Per-CPU hash table (no locking needed) | High-throughput counters without contention |
| **`BPF_MAP_TYPE_PERCPU_ARRAY`** | Per-CPU array | Per-CPU statistics |
| **`BPF_MAP_TYPE_LRU_HASH`** | Hash table with LRU eviction | Caches that shouldn't grow unbounded |
| **`BPF_MAP_TYPE_RINGBUF`** | Lock-free MPSC ring buffer | Streaming events to userspace (preferred over perf_event_array) |
| **`BPF_MAP_TYPE_PERF_EVENT_ARRAY`** | Per-CPU event buffers | Legacy event streaming (use ringbuf for new code) |
| **`BPF_MAP_TYPE_STACK_TRACE`** | Stack trace storage | Profiling, flame graphs |
| **`BPF_MAP_TYPE_PROG_ARRAY`** | Array of eBPF program file descriptors | Tail calls (chaining programs together) |
| **`BPF_MAP_TYPE_MAP_OF_MAPS`** | Map containing references to other maps | Dynamic map management, per-CPU map selection |
| **`BPF_MAP_TYPE_BLOOM_FILTER`** | Probabilistic membership test | Fast "is this IP in the blocklist?" checks |
| **`BPF_MAP_TYPE_LPM_TRIE`** | Longest prefix match trie | IP routing, CIDR matching |

### Per-CPU Maps: Avoiding Lock Contention

On a 128-core server, a regular `BPF_MAP_TYPE_HASH` that's updated on every packet would have severe lock contention. **Per-CPU maps** (`PERCPU_HASH`, `PERCPU_ARRAY`) maintain separate copies for each CPU core — no locks needed for updates, and userspace aggregates the per-CPU values when reading.

```c
// eBPF side: update per-CPU counter (no locking)
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __type(key, __u32);      // source IP
    __type(value, __u64);    // packet count
    __uint(max_entries, 65536);
} packet_count SEC(".maps");

SEC("xdp")
int count_packets(struct xdp_md *ctx) {
    __u32 src_ip = /* extract from packet */;
    __u64 *count = bpf_map_lookup_elem(&packet_count, &src_ip);
    if (count) {
        (*count)++;
    } else {
        __u64 init = 1;
        bpf_map_update_elem(&packet_count, &src_ip, &init, BPF_ANY);
    }
    return XDP_PASS;
}
```

### Ring Buffer: Streaming Events to Userspace

The **ring buffer** (`BPF_MAP_TYPE_RINGBUF`, kernel 5.8+) is the modern way to send events from eBPF programs to userspace. It's a multi-producer, single-consumer, lock-free ring buffer:

```c
// eBPF side: send event to userspace
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);  // 256 KB buffer
} events SEC(".maps");

struct event {
    __u32 pid;
    __u8 comm[16];
    __u8 filename[256];
};

SEC("tracepoint/syscalls/sys_enter_openat")
int trace_open(struct trace_event_raw_sys_enter *ctx) {
    struct event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
    if (!e) return 0;  // buffer full, drop event

    e->pid = bpf_get_current_pid_tgid() >> 32;
    bpf_get_current_comm(&e->comm, sizeof(e->comm));
    bpf_probe_read_user_str(&e->filename, sizeof(e->filename),
                            (void *)ctx->args[1]);

    bpf_ringbuf_submit(e, 0);
    return 0;
}
```

**Ring buffer vs. perf event array:** Ring buffer is newer, has better performance (shared across CPUs, no per-CPU wakeups), supports variable-length events, and has simpler userspace consumption. Use ring buffer for all new code.

### Tail Calls: Chaining Programs

A single eBPF program has instruction limits. **Tail calls** let one eBPF program jump to another (up to 33 levels deep), enabling complex logic to be split across programs:

```c
struct {
    __uint(type, BPF_MAP_TYPE_PROG_ARRAY);
    __uint(max_entries, 4);
    __type(key, __u32);
    __type(value, __u32);
} jmp_table SEC(".maps");

SEC("xdp")
int dispatcher(struct xdp_md *ctx) {
    __u32 protocol = /* determine protocol */;
    bpf_tail_call(ctx, &jmp_table, protocol);  // jump to protocol-specific handler
    return XDP_PASS;  // fallback if tail call fails
}
```

---

## Part 5 — The Verifier: Why eBPF Is Safe

The verifier is what makes eBPF fundamentally different from kernel modules. Before any program runs, the verifier performs static analysis to **prove** that the program is safe. If it can't prove safety, the program is rejected — it never runs.

### What the Verifier Checks

1. **Termination.** The program must terminate. All loops must have provably bounded iteration counts. (Unbounded loops were completely forbidden before kernel 5.13; now they're allowed if the verifier can prove they're bounded.)

2. **Memory safety.** Every pointer dereference is validated:
   - Map lookups return `NULL` if the key doesn't exist — the program must check for `NULL` before dereferencing.
   - Stack accesses must be within the 512-byte stack.
   - Context accesses (packet data, tracepoint arguments) must be within bounds.
   - Kernel memory reads must use `bpf_probe_read_kernel()` (not raw pointer dereference).

3. **No invalid memory access.** The verifier tracks the type and state of every register through every possible execution path. It knows whether a register holds a pointer, a scalar, a map value, or an uninitialized value.

4. **Correct helper usage.** Each program type can only call its allowed subset of helper functions.

5. **Instruction limits.** A program can have up to 1,000,000 verified instructions (the verifier tracks cumulative instructions across all paths, not the program size).

### Common Verifier Rejections

```c
// REJECTED: unvalidated map lookup
void *val = bpf_map_lookup_elem(&my_map, &key);
*val = 42;  // ERROR: val might be NULL

// FIX: check for NULL
void *val = bpf_map_lookup_elem(&my_map, &key);
if (val) {
    *(__u64 *)val = 42;  // OK: verifier knows val is non-NULL here
}

// REJECTED: unbounded loop
for (int i = 0; i < len; i++) {  // ERROR: len is unknown at verify time
    // ...
}

// FIX: bounded loop
for (int i = 0; i < 256 && i < len; i++) {  // OK: bounded by 256
    // ...
}

// REJECTED: out-of-bounds packet access
void *data = (void *)(long)ctx->data;
__u8 byte = *((__u8 *)data + 100);  // ERROR: might be beyond packet end

// FIX: bounds check
void *data = (void *)(long)ctx->data;
void *data_end = (void *)(long)ctx->data_end;
if (data + 101 > data_end) return XDP_DROP;  // bounds check
__u8 byte = *((__u8 *)data + 100);  // OK: verifier knows it's in bounds
```

### The Verifier Is the Bottleneck

For complex programs, satisfying the verifier is the hardest part of eBPF development. You'll restructure working code to help the verifier prove properties it can't infer. This is the eBPF equivalent of "fighting the borrow checker" in Rust — frustrating, but the constraints are what make the system safe.

---

## Part 6 — bpftrace: The Tracing Swiss Army Knife

`bpftrace` is a high-level tracing language for eBPF — think `awk` for kernel events. It's the fastest way to answer "what is the kernel doing right now?" in production.

### One-Liner Recipes

```bash
# who is opening files?
bpftrace -e 'tracepoint:syscalls:sys_enter_openat {
    printf("%d %s %s\n", pid, comm, str(args.filename));
}'

# how long do read() calls take? (histogram in microseconds)
bpftrace -e 'tracepoint:syscalls:sys_enter_read { @start[tid] = nsecs; }
tracepoint:syscalls:sys_exit_read /@start[tid]/ {
    @us = hist((nsecs - @start[tid]) / 1000);
    delete(@start[tid]);
}'

# count syscalls by process name
bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'

# trace new process executions (like execsnoop)
bpftrace -e 'tracepoint:syscalls:sys_enter_execve {
    printf("%d %s → %s\n", pid, comm, str(args.filename));
}'

# trace TCP connections (outgoing)
bpftrace -e 'kprobe:tcp_connect {
    @[comm, pid] = count();
}'

# trace TCP retransmissions
bpftrace -e 'kprobe:tcp_retransmit_skb {
    @retransmits[comm, pid] = count();
}'

# block I/O latency histogram
bpftrace -e 'tracepoint:block:block_rq_issue {
    @start[args.dev, args.sector] = nsecs;
}
tracepoint:block:block_rq_complete /@start[args.dev, args.sector]/ {
    @usecs = hist((nsecs - @start[args.dev, args.sector]) / 1000);
    delete(@start[args.dev, args.sector]);
}'

# page cache hit/miss ratio
bpftrace -e 'kprobe:filemap_get_pages { @misses = count(); }
kretprobe:filemap_get_pages /retval > 0/ { @hits = count(); }'

# which processes are allocating memory? (malloc in libc)
bpftrace -e 'uprobe:/lib/x86_64-linux-gnu/libc.so.6:malloc {
    @bytes[comm] = hist(arg0);
}'

# scheduler run queue latency (how long tasks wait before getting CPU)
bpftrace -e 'tracepoint:sched:sched_wakeup { @qtime[args.pid] = nsecs; }
tracepoint:sched:sched_switch /@qtime[args.next_pid]/ {
    @runq_us = hist((nsecs - @qtime[args.next_pid]) / 1000);
    delete(@qtime[args.next_pid]);
}'

# trace why a process is sleeping (off-CPU analysis)
bpftrace -e 'tracepoint:sched:sched_switch /args.prev_pid == 12345/ {
    printf("off-CPU: %s\n", kstack);
}'

# DNS query sniffing (trace DNS lookups)
bpftrace -e 'uprobe:/lib/x86_64-linux-gnu/libc.so.6:getaddrinfo {
    printf("%s → DNS: %s\n", comm, str(arg0));
}'
```

### bpftrace Language Basics

```
probes /filter/ { actions }

probes:
  tracepoint:category:event        stable kernel trace points
  kprobe:function_name             any kernel function entry
  kretprobe:function_name          any kernel function return
  uprobe:binary:function           userspace function entry
  usdt:binary:provider:probe       userspace static trace points
  profile:hz:99                    CPU sampling at 99 Hz
  interval:s:5                     run every 5 seconds
  BEGIN                            run once at startup
  END                              run once at exit

variables:
  @name          global map variable (persists across events)
  @name[key]     global associative array
  $name          scratch variable (per-event)

built-in variables:
  pid, tid       process/thread ID
  comm           process name
  nsecs          nanosecond timestamp
  kstack, ustack kernel/user stack trace
  args           tracepoint arguments
  retval         return value (kretprobe/uretprobe)
  arg0-arg5      function arguments (kprobe/uprobe)

aggregation functions:
  count()        count events
  sum(x)         sum values
  avg(x)         average
  min(x), max(x) min/max
  hist(x)        power-of-2 histogram
  lhist(x, min, max, step)  linear histogram
  stats(x)       count, average, total
```

---

## Part 7 — BCC Tools: The Pre-Built Toolkit

BCC (BPF Compiler Collection) provides **100+ ready-made eBPF tools** — the "top" and "vmstat" of the eBPF era. These are production-ready, battle-tested, and installed on most Linux distributions.

### Essential BCC Tools

**Process and CPU:**

```bash
execsnoop          # trace new process executions — every exec() on the system
                   # output: PID PPID ARGS
                   # "what just ran on this machine?"

runqlat            # scheduler run queue latency histogram
                   # "how long are tasks waiting for CPU?"

cpudist            # on-CPU time distribution per process
                   # "are my tasks getting short or long time slices?"

offcputime         # off-CPU time with stack traces
                   # "where is my process sleeping/blocked?"
                   # essential for off-CPU flame graphs

exitsnoop          # trace process exits with exit code
                   # "is something crashing silently?"
```

**Disk I/O:**

```bash
biolatency         # block I/O latency histogram
                   # "what's my real disk latency distribution?"

biosnoop           # trace individual block I/O requests
                   # "which files are causing slow I/O?"

biotop             # top-like for block I/O by process
                   # "who is hammering the disk?"

fileslower 10      # show file I/O operations slower than 10ms
                   # "which reads/writes are slow?"

cachestat          # page cache hit/miss statistics per second
                   # "is my cache working?"

filetop            # top-like for file reads/writes by process
```

**Networking:**

```bash
tcpconnect         # trace outgoing TCP connections
                   # "what is my process connecting to?"

tcpaccept          # trace incoming TCP connections
                   # "who is connecting to my server?"

tcplife            # trace TCP session lifetimes with bytes transferred
                   # "how long do connections last? how much data?"

tcpretrans         # trace TCP retransmissions
                   # "is the network lossy?"

tcpdrop            # trace dropped TCP packets with reason
                   # "why is the kernel dropping packets?"
```

**Memory:**

```bash
memleak            # detect memory leaks (track allocations/frees, show unfreed)
                   # "is my process leaking memory?"

oomkill            # trace OOM killer events
                   # "which process was killed and why?"

shmsnoop           # trace System V shared memory operations
```

**Filesystem:**

```bash
opensnoop          # trace file opens system-wide
                   # "what files is this process touching?"

filelife           # trace file creation and deletion with age
                   # "are temp files accumulating?"

ext4slower 10      # trace ext4 operations slower than 10ms
```

**Security:**

```bash
capable            # trace capability checks
                   # "what capabilities is this process requesting?"

bashreadline       # trace bash commands (readline input)
                   # "what commands are users running?"
```

### Using BCC Tools

```bash
# install on Ubuntu/Debian
apt install bpfcc-tools

# tools are named with -bpfcc suffix on some distros
biolatency-bpfcc
execsnoop-bpfcc

# or install from pip
pip install bcc

# common usage patterns:
biolatency -D              # show histogram per disk
tcplife -t -T -L 80       # trace connections to port 80 with timestamps
opensnoop -p 12345         # filter by PID
execsnoop -x               # show only failed executions
memleak -p 12345 -a 30     # track allocations for PID 12345, report every 30s
```

---

## Part 8 — Writing eBPF Programs

When bpftrace and BCC tools aren't enough, you write your own eBPF programs. The modern approach is **libbpf + CO-RE** (C), **cilium/ebpf** (Go), or **aya** (Rust).

### CO-RE: Compile Once, Run Everywhere

The historic pain of eBPF development: your program accesses kernel data structures by offset. Different kernel versions have different struct layouts. Your program compiled against kernel 5.15 headers breaks on kernel 6.1 because a struct field moved.

**CO-RE** (Compile Once – Run Everywhere) solves this with **BTF (BPF Type Format)**: compact type information embedded in the kernel binary. At load time, the eBPF loader reads the target kernel's BTF and *relocates* your program's struct accesses to the correct offsets. You compile once, and the program works on any kernel with BTF support.

```bash
# check if your kernel has BTF
ls /sys/kernel/btf/vmlinux     # if this file exists, BTF is available

# generate a header with ALL kernel types (for development)
bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h
```

### Development Ecosystem Comparison

| Ecosystem | Language | eBPF Code | Userspace Code | Best For |
|---|---|---|---|---|
| **libbpf** | C | C | C | Maximum control, upstream kernel development |
| **cilium/ebpf** | Go | C | Go | Production Go services, Kubernetes operators |
| **aya** | Rust | Rust | Rust | Memory-safe development, Rust-native teams |
| **bcc** | Python | C (embedded in Python strings) | Python | Prototyping, one-off scripts |

### libbpf (C) Workflow

```bash
# 1. Write the eBPF program (kern.bpf.c)
# 2. Write the userspace loader (main.c)
# 3. Compile:
clang -g -O2 -target bpf -D__TARGET_ARCH_x86 -c kern.bpf.c -o kern.bpf.o
# 4. Generate skeleton header:
bpftool gen skeleton kern.bpf.o > kern.skel.h
# 5. Compile userspace:
gcc -o loader main.c -lbpf -lelf -lz
```

### cilium/ebpf (Go) Workflow

```bash
# 1. Write the eBPF program in C (program.c)
# 2. Add a go:generate directive to your Go file:
#    //go:generate go run github.com/cilium/ebpf/cmd/bpf2go -target amd64 counter program.c

# 3. Run the generator:
go generate ./...
# This compiles program.c to eBPF bytecode and generates Go types
# for all maps and programs defined in the C code.

# 4. Use the generated types in your Go code:
```

```go
package main

import (
    "log"
    "github.com/cilium/ebpf/link"
)

func main() {
    // Load the compiled eBPF objects
    objs := counterObjects{}
    if err := loadCounterObjects(&objs, nil); err != nil {
        log.Fatal(err)
    }
    defer objs.Close()

    // Attach to a tracepoint
    tp, err := link.Tracepoint("syscalls", "sys_enter_execve", objs.TraceExec, nil)
    if err != nil {
        log.Fatal(err)
    }
    defer tp.Close()

    // Read from maps
    var count uint64
    objs.ExecCount.Lookup(uint32(0), &count)
    log.Printf("exec count: %d", count)
}
```

### aya (Rust) Workflow

```bash
# 1. Install prerequisites
cargo install bpf-linker
cargo install cargo-generate

# 2. Scaffold a new project
cargo generate https://github.com/aya-rs/aya-template

# 3. Write eBPF code in Rust (in the -ebpf crate)
# 4. Write userspace code in Rust (in the main crate)
# 5. Build and run:
cargo xtask build-ebpf
cargo build
sudo cargo xtask run
```

```rust
// eBPF side (Rust)
#![no_std]
#![no_main]
use aya_ebpf::{macros::tracepoint, programs::TracePointContext};

#[tracepoint]
pub fn trace_exec(ctx: TracePointContext) -> u32 {
    // handle the event
    0
}
```

### bpftool: The Inspector

`bpftool` is the command-line tool for inspecting eBPF state on a running system:

```bash
# list loaded eBPF programs
bpftool prog list
# 42: xdp  name xdp_filter  tag abc123  gpl
#     loaded_at 2026-01-01T00:00:00+0000  uid 0
#     xlated 1234B  jited 890B  memlock 4096B

# list all maps
bpftool map list

# dump map contents
bpftool map dump id 5

# show program bytecode
bpftool prog dump xlated id 42

# show JIT-compiled native code
bpftool prog dump jited id 42

# show BTF information
bpftool btf list

# pin a program to a persistent path
bpftool prog pin id 42 /sys/fs/bpf/my_program

# attach XDP to an interface
bpftool net attach xdp id 42 dev eth0
```

---

## Part 9 — Networking with eBPF

### Cilium: eBPF-Native Kubernetes Networking

Cilium is the dominant Kubernetes CNI (Container Network Interface) in 2026, used by AWS EKS, Google GKE, and most enterprise clusters. It replaces the entire `kube-proxy` component with eBPF programs.

**What Cilium replaces:**

| Component | Before (iptables) | After (Cilium/eBPF) |
|---|---|---|
| **Service load balancing** | iptables DNAT rules — O(n) per packet, one rule per backend | eBPF hash lookup — O(1) per packet |
| **Network policy** | iptables rules per pod pair | eBPF map lookup per connection |
| **NAT** | conntrack + iptables MASQUERADE | eBPF CT map + NAT map |
| **Performance at scale** | Degrades badly above ~5,000 Services | Handles 100,000+ Services |

**How it works:** Cilium compiles and loads eBPF programs onto every node. These programs attach to TC hooks on each pod's veth interface. When a pod sends a packet to a Kubernetes Service, the eBPF program:

1. Looks up the Service VIP in a BPF hash map.
2. Selects a backend pod (consistent hashing, maglev, random, etc.).
3. Rewrites the packet's destination IP to the backend pod's IP.
4. Forwards the packet directly — bypassing netfilter, iptables, and conntrack entirely.

This is O(1) per packet regardless of how many Services or Endpoints exist in the cluster.

**Hubble: eBPF-Powered Observability**

Hubble is Cilium's observability layer. Because eBPF programs see every packet, Cilium provides **deep network visibility without any application instrumentation**:

```bash
# observe live traffic (like tcpdump but with Kubernetes context)
hubble observe --namespace production

# show HTTP requests with latency
hubble observe --protocol http -t l7

# show dropped packets with reason
hubble observe --verdict DROPPED

# show DNS queries
hubble observe --protocol dns

# flow logs include:
# - source/destination pod, namespace, labels
# - L3/L4 protocol info
# - L7 HTTP/gRPC/DNS/Kafka details
# - policy verdict (forwarded, dropped, reason)
# - latency
```

This is "free" observability — no sidecars, no agents, no code changes. The eBPF programs that Cilium already runs for networking also emit events to Hubble.

### XDP in Practice

```c
// Simple XDP firewall: drop packets from a blocklist
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __type(key, __u32);      // IPv4 address
    __type(value, __u8);     // dummy (presence = blocked)
    __uint(max_entries, 10000);
} blocklist SEC(".maps");

SEC("xdp")
int xdp_firewall(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // parse Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_DROP;
    if (eth->h_proto != htons(ETH_P_IP)) return XDP_PASS;

    // parse IP header
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_DROP;

    // check blocklist
    __u32 src_ip = ip->saddr;
    if (bpf_map_lookup_elem(&blocklist, &src_ip)) {
        return XDP_DROP;  // blocked
    }

    return XDP_PASS;
}
```

```bash
# attach XDP program to an interface
ip link set dev eth0 xdp obj firewall.o sec xdp

# detach
ip link set dev eth0 xdp off

# check XDP status
ip link show eth0
# eth0: ... xdp/id:42 ...
```

---

## Part 10 — Security with eBPF

### Tetragon: Runtime Security Enforcement

Tetragon (by Isovalent/Cilium) is an eBPF-based security tool that doesn't just *detect* threats — it **enforces policy in the kernel**. Unlike traditional security tools that stream events to userspace for analysis (introducing latency), Tetragon's eBPF programs make decisions and take action directly in the kernel.

**Capabilities:**
- **Detect and kill** processes that attempt privilege escalation.
- **Block** unauthorized file access at the kernel level.
- **Prevent** namespace escapes from containers.
- **Enforce** network policies beyond what Kubernetes NetworkPolicy supports.

```yaml
# Tetragon TracingPolicy: detect and kill any process writing to /etc/shadow
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-shadow-writes
spec:
  kprobes:
  - call: "security_file_permission"
    syscall: false
    args:
    - index: 0
      type: "file"
    selectors:
    - matchArgs:
      - index: 0
        operator: "Equal"
        values:
        - "/etc/shadow"
      matchActions:
      - action: Sigkill   # kill the process immediately
```

**Tetragon vs. Falco:**

| | Tetragon | Falco |
|---|---|---|
| **Action** | Enforcement — can kill processes, deny operations | Detection — alerts and logs |
| **Where** | In-kernel (eBPF) | Kernel events → userspace rule engine |
| **Overhead** | Lower (filtering happens in kernel) | Higher (all events streamed to userspace) |
| **Flexibility** | Focused on enforcement | Broad rule language, MITRE ATT&CK alignment |
| **Best for** | Blocking known-bad behavior | Detecting anomalies, compliance, audit |

In practice, many organizations run **both**: Tetragon for enforcement (block the exploit) and Falco for detection (alert on anomalies).

### Falco: Behavioral Threat Detection

Falco uses eBPF (or a kernel module) to stream syscall events to a userspace rule engine. Rules are written in a YAML-based DSL:

```yaml
# alert when a shell is spawned inside a container
- rule: Shell in Container
  desc: A shell was spawned in a container
  condition: >
    spawned_process and
    container and
    proc.name in (bash, sh, zsh, dash)
  output: >
    Shell spawned in container
    (user=%user.name container=%container.name
     shell=%proc.name parent=%proc.pname)
  priority: WARNING

# alert when sensitive files are read
- rule: Read Sensitive File
  desc: A sensitive file was read
  condition: >
    open_read and
    fd.name in (/etc/shadow, /etc/sudoers)
  output: >
    Sensitive file read (file=%fd.name process=%proc.name user=%user.name)
  priority: ERROR
```

---

## Part 11 — Observability with eBPF

eBPF enables **zero-instrumentation observability** — deep telemetry without modifying application code or adding sidecars.

### Grafana Beyla: Auto-Instrumented Application Metrics

Beyla uses eBPF (uprobes and kprobes) to automatically detect and instrument HTTP, gRPC, SQL, and Redis traffic for any application — regardless of language or framework:

```bash
# run Beyla alongside your application
BEYLA_OPEN_PORT=8080 beyla

# Beyla automatically:
# - detects HTTP/gRPC traffic on port 8080
# - generates RED metrics (Rate, Errors, Duration) per endpoint
# - exports to Prometheus / OpenTelemetry
# - no code changes, no SDK, no sidecar
```

This works because eBPF can trace the kernel's TCP/socket layer — it sees every `read()` and `write()` on every socket, and Beyla's eBPF programs parse the application-layer protocol (HTTP, gRPC) from the raw bytes.

### Continuous Profiling: Parca and Pyroscope

eBPF-based continuous profiling captures CPU flame graphs for every process, all the time, with <1% overhead:

```bash
# Parca agent: continuously profile all processes on the node
parca-agent --remote-store-address=parca-server:7070

# captures stack traces via perf_event eBPF programs
# sends flame graph data to the Parca server
# you can see what any process was doing at any point in time
```

This replaces ad-hoc profiling ("reproduce the problem and run perf record") with always-on profiling. When an incident occurs, the data is already captured.

### Pixie: Kubernetes Observability

Pixie (by New Relic, CNCF project) uses eBPF to provide instant Kubernetes observability:

- **HTTP/gRPC golden signals** per service — no instrumentation.
- **Full request/response capture** — see the actual HTTP bodies flowing between services.
- **Distributed tracing** — correlate requests across services using connection tracking.
- **Continuous CPU profiling** — flame graphs for every pod.
- **In-cluster data processing** — data stays in the cluster (privacy-friendly).

---

## Part 12 — sched_ext: Custom Schedulers in eBPF

`sched_ext` (kernel 6.12+, 2024) is arguably the most exciting eBPF development: it lets you write **custom CPU schedulers** as eBPF programs that can be loaded and replaced at runtime, without recompiling the kernel.

### Why Custom Schedulers?

The kernel's default scheduler (EEVDF, which replaced CFS in kernel 6.6) is a general-purpose scheduler optimized for fairness. But "fair" isn't always "optimal":

- **Gaming:** you want maximum responsiveness for the foreground game, starving background tasks if necessary.
- **Databases:** you want the query thread to run uninterrupted on a specific core, with zero scheduler preemptions.
- **AI training:** you want to co-schedule related GPU data-prep threads to maximize cache locality.
- **Hyperscalers (Meta, Google):** you want to A/B test scheduling policies on live traffic without rebooting fleet servers.

### How sched_ext Works

You implement a set of callbacks (enqueue, dequeue, dispatch, pick_next_task, etc.) as eBPF programs. The kernel calls your eBPF scheduler instead of the default one:

```c
// simplified sched_ext scheduler
SEC("struct_ops")
void BPF_PROG(enqueue, struct task_struct *p, u64 enq_flags) {
    // custom logic: decide where to place the task
    scx_bpf_dispatch(p, SCX_DSQ_GLOBAL, /* slice_ns */ 5000000, enq_flags);
}

SEC("struct_ops")
void BPF_PROG(dispatch, s32 cpu, struct task_struct *prev) {
    // custom logic: pick the next task for this CPU
    scx_bpf_consume(SCX_DSQ_GLOBAL);
}

SEC(".struct_ops.link")
struct sched_ext_ops my_scheduler = {
    .enqueue = (void *)enqueue,
    .dispatch = (void *)dispatch,
    .name = "my_custom_scheduler",
};
```

```bash
# load the custom scheduler
sudo scx_loader my_scheduler.bpf.o

# unload and revert to the default scheduler
sudo scx_loader --unload
```

**Key point:** if your eBPF scheduler crashes or has a bug, the kernel automatically reverts to the default scheduler. The system stays running. This makes it safe to experiment with scheduling policies in production.

### sched_ext Schedulers in 2026

| Scheduler | Focus | Who |
|---|---|---|
| **scx_rusty** | Work-conserving, NUMA-aware | General-purpose improvement over default |
| **scx_lavd** | Latency-critical, value-directed | Gaming, interactive workloads |
| **scx_bpfland** | Power-efficient scheduling | Laptop/mobile power saving |
| **scx_central** | Centralized decision making | Research, specialized workloads |
| **Custom** | Whatever you need | Meta, Google, game studios |

---

## Part 13 — eBPF Security Considerations

eBPF runs inside the kernel. This power comes with security implications that you must understand.

### The Attack Surface

1. **Verifier vulnerabilities.** The verifier is complex (~20,000 lines of code). Bugs in the verifier have allowed crafted eBPF programs to bypass safety checks, leading to privilege escalation. CVEs against the verifier are published regularly (including in 2026). **Mitigation:** keep your kernel patched.

2. **Privileged access.** Loading eBPF programs requires capabilities — at minimum `CAP_BPF` (kernel 5.8+), and many program types require additional capabilities:
   - `CAP_BPF` — load and attach most program types
   - `CAP_PERFMON` — access performance monitoring (needed for kprobes, perf events)
   - `CAP_NET_ADMIN` — XDP, TC, socket programs
   - `CAP_SYS_ADMIN` — some advanced operations (avoid granting this)

3. **Information leakage.** eBPF programs can read kernel memory (via `bpf_probe_read_kernel`) and access process data. A malicious eBPF program could exfiltrate sensitive data.

### Container Security

By default, containers **cannot** load eBPF programs (they lack the required capabilities). This is the correct default. Security and monitoring tools that need eBPF (Cilium, Falco, Tetragon) run as **privileged DaemonSets** or with specific capabilities — and they are the *infrastructure*, not the workload.

**Rules:**
- Application containers should never have `CAP_BPF` or `CAP_SYS_ADMIN`.
- eBPF-based tools run as node-level infrastructure (DaemonSets), not per-pod sidecars.
- Some organizations disable `bpf()` for unprivileged users entirely: `sysctl kernel.unprivileged_bpf_disabled=1`.

### Restricting eBPF

```bash
# disable unprivileged eBPF (recommended for production)
sysctl -w kernel.unprivileged_bpf_disabled=1

# optionally disable io_uring (related kernel attack surface)
sysctl -w kernel.io_uring_disabled=2

# audit eBPF program loads
bpftool prog list      # who has loaded what?
```

### The Verifier Is Not Perfect

The verifier is a best-effort safety system, not a formal proof. Known limitations:
- Complex control flow can exceed the verifier's analysis budget (1M instructions), forcing you to simplify your program.
- Side channels (timing attacks via eBPF programs) have been demonstrated.
- The verification process itself is complex enough to have bugs.

The practical stance: eBPF is vastly safer than kernel modules (which have zero verification), but it is not a perfect security boundary. Treat eBPF program loading as a privileged operation.

---

## Part 14 — The 2026 eBPF Ecosystem

### The Landscape Map

```
                     ┌─────────────────────────────────┐
                     │         Applications             │
                     │  (your services, Kubernetes)     │
                     └───────────────┬─────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
    ┌────▼────┐               ┌──────▼──────┐            ┌──────▼──────┐
    │Networking│               │  Security    │            │Observability│
    │         │               │              │            │             │
    │ Cilium  │               │  Tetragon    │            │ Hubble      │
    │ + Hubble│               │  Falco       │            │ Beyla       │
    │         │               │  KubeArmor   │            │ Pixie       │
    │ XDP     │               │              │            │ Parca       │
    │ TC      │               │  LSM hooks   │            │ Pyroscope   │
    └────┬────┘               └──────┬───────┘            └──────┬──────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │          eBPF Runtime            │
                     │  Verifier → JIT → Hook Points   │
                     │  Maps, Helpers, BTF, CO-RE       │
                     └───────────────┬─────────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │         Linux Kernel             │
                     └─────────────────────────────────┘
```

### Project Comparison

| Project | Category | What It Does | How It Uses eBPF |
|---|---|---|---|
| **Cilium** | Networking | Kubernetes CNI, Service load balancing, Network Policy, Service Mesh | XDP + TC programs on every pod's veth interface |
| **Hubble** | Observability | Network flow visibility, L7 protocol inspection | Reads events from Cilium's eBPF data path |
| **Tetragon** | Security | Runtime policy enforcement (kill processes, deny file access) | kprobes + LSM hooks with in-kernel enforcement |
| **Falco** | Security | Behavioral threat detection, compliance auditing | Syscall tracing via tracepoints/kprobes |
| **Grafana Beyla** | Observability | Auto-instrumented HTTP/gRPC/SQL metrics | uprobes on application libraries + kprobes on socket ops |
| **Pixie** | Observability | Full Kubernetes observability (traces, metrics, logs) | kprobes + uprobes for protocol parsing |
| **Parca** | Profiling | Continuous CPU profiling | perf_event eBPF programs for stack sampling |
| **Pyroscope** | Profiling | Continuous CPU/memory profiling | perf_event eBPF programs |
| **KubeArmor** | Security | Container runtime security | LSM hooks + syscall monitoring |
| **Katran** | Networking | L4 load balancer (Meta's open-source) | XDP for packet steering |
| **sched_ext** | Scheduling | Custom CPU schedulers | struct_ops eBPF programs replacing scheduler callbacks |
| **bpftrace** | Tracing | Ad-hoc kernel and application tracing | kprobes, tracepoints, uprobes |
| **BCC** | Tracing | Pre-built tracing tools | kprobes, tracepoints, uprobes |

### Getting Started: The Learning Path

```
Level 0: Use the tools
├── Install bpftrace, run one-liners on a test system
├── Install BCC tools, run biolatency, execsnoop, tcplife
└── Deploy Cilium on a test Kubernetes cluster, explore Hubble

Level 1: Understand the internals
├── Read "Learning eBPF" by Liz Rice (the best introduction)
├── Read "BPF Performance Tools" by Brendan Gregg (the reference)
├── Understand program types, maps, the verifier
└── Write a simple kprobe/tracepoint program with bpftrace

Level 2: Write programs
├── Choose your ecosystem: libbpf (C), cilium/ebpf (Go), or aya (Rust)
├── Write a CO-RE program that works across kernel versions
├── Understand BTF, ring buffers, per-CPU maps
└── Build a custom tracing tool for your application

Level 3: Production deployment
├── Deploy Cilium + Hubble for networking and observability
├── Deploy Tetragon or Falco for runtime security
├── Deploy Beyla or Pixie for auto-instrumented metrics
├── Write custom eBPF programs for your specific needs
└── Contribute to upstream eBPF ecosystem
```

### Kernel Version Requirements

| Feature | Minimum Kernel | Recommended |
|---|---|---|
| Basic eBPF (maps, helpers) | 4.1 | 5.4+ |
| BTF / CO-RE | 5.4 | 5.8+ |
| `CAP_BPF` (fine-grained permissions) | 5.8 | 5.8+ |
| Ring buffer | 5.8 | 5.8+ |
| Bounded loops | 5.13 | 5.13+ |
| fentry/fexit | 5.5 | 5.5+ |
| LSM hooks | 5.7 | 5.7+ |
| sched_ext | 6.12 | 6.12+ |
| **Production baseline** | — | **5.15+ LTS or 6.x** |

```bash
# check your kernel's eBPF capabilities
bpftool feature probe kernel

# check specific feature support
bpftool feature probe kernel | grep map_type
bpftool feature probe kernel | grep program_type
bpftool feature probe kernel | grep helper
```

---

If you remember one thing from this guide: **eBPF is the mechanism that lets you run safe, sandboxed, JIT-compiled programs inside the Linux kernel at specific hook points — without modifying the kernel or rebooting. In 2026, it is the foundational technology beneath Kubernetes networking (Cilium replaces iptables/kube-proxy with O(1) eBPF lookups), runtime security (Tetragon enforces policy in-kernel, Falco detects threats), zero-instrumentation observability (Hubble, Beyla, Pixie provide metrics and traces without code changes), and custom scheduling (sched_ext lets you hot-swap CPU schedulers at runtime). The tools are mature, the ecosystem is production-ready, and every major cloud provider has adopted it. If you operate Linux infrastructure, eBPF is no longer optional knowledge — it's the substrate your stack runs on.**

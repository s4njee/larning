# Advanced Linux

A depth-first guide to the tunable, observable, optimizable internals of Linux — the scheduler, memory management, the I/O stack, advanced networking, eBPF, performance analysis, security hardening, and the boot process — for engineers who understand the fundamentals (processes, file descriptors, signals, namespaces, cgroups) and want to go deeper into why their production systems behave the way they do. This is the companion to the [Linux Fundamentals guide](LINUX_FUNDAMENTALS_STUDY_GUIDE.md), which covers the substrate; this guide covers what you tune, trace, and harden on top of it.

Assumes you've read (or could read) the fundamentals guide — you understand fork/exec, file descriptors and epoll, signals and graceful shutdown, permissions and capabilities, systemd units, namespaces and cgroups, and basic diagnostic tools (ps, top, strace, ss). This guide won't repeat those; it builds on them.

Primary references: Brendan Gregg's [Systems Performance](https://www.brendangregg.com/systems-performance-2nd-edition-book.html) and [BPF Performance Tools](https://www.brendangregg.com/bpf-performance-tools-book.html), the [kernel documentation](https://www.kernel.org/doc/html/latest/), Michael Kerrisk's [The Linux Programming Interface](https://man7.org/tlpi/), and the man pages (always `man 2` for syscalls, `man 7` for overviews).

---

## Table of Contents

1. [Part 1 — The Scheduler](#part-1--the-scheduler)
2. [Part 2 — Memory Management](#part-2--memory-management)
3. [Part 3 — The I/O Stack](#part-3--the-io-stack)
4. [Part 4 — Advanced Networking](#part-4--advanced-networking)
5. [Part 5 — eBPF](#part-5--ebpf)
6. [Part 6 — Performance Analysis](#part-6--performance-analysis)
7. [Part 7 — Security Hardening](#part-7--security-hardening)
8. [Part 8 — Advanced Filesystems & Storage](#part-8--advanced-filesystems--storage)
9. [Part 9 — Kernel Tuning](#part-9--kernel-tuning)
10. [Part 10 — The Boot Process](#part-10--the-boot-process)

---

## Part 1 — The Scheduler

The fundamentals guide said "a process is in the run queue or it's sleeping." This part explains what the run queue actually is, how the kernel decides which task runs next, and why your container's CPU limit causes throttling — not denial.

### Scheduling Classes

The Linux scheduler isn't a single algorithm — it's a hierarchy of **scheduling classes**, each implementing a different policy. The scheduler checks them in priority order and runs the highest-priority runnable task:

| Priority | Class | Policy | Used By |
|---|---|---|---|
| Highest | **Stop** | — | kernel internal (migration, watchdog) |
| | **Deadline** | `SCHED_DEADLINE` | real-time tasks with explicit deadlines (audio, robotics) |
| | **Real-time** | `SCHED_FIFO`, `SCHED_RR` | latency-sensitive tasks that must preempt everything else |
| Lowest | **Fair** | `SCHED_OTHER` (CFS/EEVDF) | **everything else** — 99.9% of your workloads |

Almost every process you care about runs in the **fair** class. Real-time and deadline scheduling exist for specialized use cases (audio processing, industrial control) and can starve the entire system if misconfigured — which is why they require `CAP_SYS_NICE` or root.

### CFS (Completely Fair Scheduler)

[CFS](https://docs.kernel.org/scheduler/sched-design-CFS.html) has been the default fair scheduler since kernel 2.6.23 (2007). Its design principle: **give every task its fair share of CPU time, weighted by priority (nice value).**

CFS doesn't use time slices in the traditional sense. Instead, it tracks how much CPU time each task has consumed (**virtual runtime**, `vruntime`) and always picks the task with the **lowest vruntime** — the task that has been treated most unfairly. Tasks that have used less CPU get picked sooner; tasks that have used more get delayed.

```
vruntime is tracked per-task:

  Task A: vruntime = 100ms   ← has used the most CPU, runs last
  Task B: vruntime = 80ms
  Task C: vruntime = 50ms    ← has used the least CPU, runs next

The scheduler picks C, runs it, C's vruntime increases.
Eventually C's vruntime exceeds B's, so B runs next.
This naturally converges to fair sharing.
```

CFS stores runnable tasks in a **red-black tree** (a self-balancing BST) ordered by vruntime. Picking the next task is O(1) (the leftmost node is cached). Adding/removing tasks is O(log n). For most workloads this is fast enough, but it matters at extreme scale — systems with thousands of runnable tasks per CPU.

**Nice values** adjust the weight. Nice ranges from -20 (highest priority, more CPU share) to +19 (lowest priority, less CPU share). Default is 0. Each nice level roughly corresponds to a 10% change in CPU share:

```bash
nice -n 10 ./batch-job          # run with reduced priority
renice -n -5 -p 12345           # increase priority of a running process
```

`nice` only affects scheduling within the fair class — it doesn't make a process real-time.

### EEVDF (Earliest Eligible Virtual Deadline First)

Kernel 6.6 (October 2023) replaced CFS with **[EEVDF](https://docs.kernel.org/scheduler/sched-eevdf.html)** as the default fair scheduler. EEVDF adds a **virtual deadline** to each task: `deadline = eligible_time + (slice / weight)`. The scheduler picks the eligible task with the earliest virtual deadline.

The practical difference from CFS:

- **Better latency fairness.** CFS could starve short-running tasks when long-running tasks monopolized the leftmost position in the tree. EEVDF's deadline mechanism ensures latency-sensitive tasks (interactive, I/O-bound) get scheduled promptly even alongside CPU hogs.
- **The `sched_ext` hook.** EEVDF is the foundation for [`sched_ext`](https://docs.kernel.org/scheduler/sched-ext.html) (kernel 6.12+), which lets you write **custom schedulers in eBPF** — loaded and replaced at runtime without recompiling the kernel. This is the most exciting scheduler development in years: Google, Meta, and game developers are using it for workload-specific scheduling.
- **Mostly transparent.** For typical server workloads, you won't notice the difference. EEVDF is a better CFS, not a different paradigm.

```bash
# check your kernel's scheduler
uname -r                         # kernel version (6.6+ = EEVDF)
cat /proc/sched_debug | head     # scheduler debug info
```

### CPU Affinity and Isolation

**CPU affinity** pins a process to specific CPU cores with [`taskset(1)`](https://man7.org/linux/man-pages/man1/taskset.1.html):

```bash
taskset -c 0,1 ./myapp           # run on cores 0 and 1 only
taskset -cp 2-5 12345            # change a running process to cores 2-5
```

Why pin? **Cache locality.** When a process migrates between cores, its L1/L2 cache is cold on the new core — a migration penalty of microseconds to milliseconds. For latency-sensitive workloads (trading systems, game servers), pinning avoids this.

**`isolcpus`** reserves CPU cores exclusively for specific workloads by removing them from the general scheduler. The kernel won't schedule any task on isolated CPUs unless explicitly placed there:

```bash
# kernel command line (GRUB)
isolcpus=4-7                     # cores 4-7 are isolated

# then pin your latency-sensitive app to isolated cores
taskset -c 4-7 ./low-latency-app
```

This is the gold standard for latency-sensitive workloads: isolated CPUs have zero contention from other tasks, no scheduler interrupts, no cache pollution.

### CFS Bandwidth Control (How K8s CPU Limits Work)

The fundamentals guide mentioned that `--cpus 2` in Docker maps to a cgroup CPU limit. Here's exactly how it works:

[CFS bandwidth control](https://docs.kernel.org/scheduler/sched-bwc.html) enforces a **quota** of CPU time per **period**:

```
quota = allowed CPU microseconds per period
period = 100,000 µs (100ms) by default

--cpus 2  →  quota = 200,000 µs / period = 100,000 µs
           = the process can use 200ms of CPU per 100ms wall clock
           = effectively 2 full cores
```

When a cgroup exhausts its quota within a period, all tasks in that cgroup are **throttled** — the scheduler won't run them until the next period starts. This shows up as:

```bash
# check throttling (cgroups v1)
cat /sys/fs/cgroup/cpu/docker/<container-id>/cpu.stat
# nr_periods 1000      ← total periods
# nr_throttled 150     ← periods where throttling occurred (15%!)
# throttled_time 45000000000  ← total nanoseconds spent throttled
```

**This is the #1 production CPU performance issue in Kubernetes.** A container with CPU limits set will be throttled even if the node has idle CPUs. CPU *requests* affect scheduling (which node the pod lands on), but CPU *limits* enforce hard throttling. Many production teams set CPU requests but deliberately omit CPU limits for this reason (the "burstable" QoS class).

```bash
# cgroups v2 (modern systems)
cat /sys/fs/cgroup/<path>/cpu.max
# 200000 100000        ← quota period (200ms per 100ms = 2 CPUs)
# max 100000           ← "max" means no limit

cat /sys/fs/cgroup/<path>/cpu.stat
# usage_usec, throttled_usec, nr_throttled, etc.
```

### The Scheduler and NUMA

On multi-socket servers (and increasingly on modern CPUs with chiplet architectures like AMD EPYC), not all memory is equally fast to access. **NUMA (Non-Uniform Memory Access)** means each CPU socket has local memory (fast) and remote memory (slower — typically 1.5-2× latency).

The scheduler is NUMA-aware: it tries to keep tasks running near their memory allocations. But migration between NUMA nodes is expensive — not just cache cold, but also remote memory access for all existing allocations.

```bash
numactl --hardware               # show NUMA topology (man 8 numactl)
numactl --cpunodebind=0 --membind=0 ./myapp   # pin to NUMA node 0
lscpu | grep NUMA                # quick topology overview
numastat                         # NUMA memory allocation statistics
```

For database servers and JVM workloads, NUMA misalignment (the process runs on node 0 but its memory is on node 1) can cause a 10-30% performance degradation — a problem that looks like "slow queries" but is actually memory latency.

If you remember one thing from Part 1: **the scheduler picks the task with the lowest virtual runtime (CFS) or earliest virtual deadline (EEVDF), nice values adjust the weight, and Kubernetes CPU limits work by throttling tasks when they exhaust their CFS bandwidth quota — which is why CPU-limited containers are slow even on idle nodes. Check `cpu.stat` for `nr_throttled`.**

---

## Part 2 — Memory Management

The fundamentals guide covered the OOM killer and cgroup memory limits. This part goes into how Linux manages physical memory, virtual memory, the page cache, and what all those numbers in `/proc/meminfo` actually mean.

### Virtual Memory and Page Tables

Every process sees its own **virtual address space** — a flat range of addresses (0 to 2^47 on x86-64, 128 TB) that the CPU's **MMU (Memory Management Unit)** translates to physical addresses using **page tables**. The unit of translation is a **page** — 4 KB by default on x86-64.

```
Virtual Address Space (per process)        Physical Memory (shared)
┌──────────────────────┐                   ┌──────────────────────┐
│ Stack                │─────┐             │ Page frame 0         │
│                      │     │             │ Page frame 1  ←──────│── Process A's code
│ (grows down)         │     │             │ Page frame 2  ←──────│── Process B's code
│                      │     │             │ Page frame 3  ←──────│── Page cache (file data)
│ [unmapped gap]       │     │             │ Page frame 4         │
│                      │     └────────────▶│ Page frame 5         │
│ Heap (grows up)      │──────────────────▶│ Page frame 6         │
│                      │                   │ ...                  │
│ BSS, Data, Code      │──────────────────▶│ Page frame N         │
└──────────────────────┘                   └──────────────────────┘
```

The translation uses a **multi-level page table** (4 levels on x86-64: PGD → PUD → PMD → PTE). Walking the page table on every memory access would be prohibitively slow, so the CPU caches recent translations in the **TLB (Translation Lookaside Buffer)**. TLB misses are expensive (10-100 cycles) and are a real performance concern for memory-intensive workloads.

### Demand Paging and Copy-on-Write

When a process allocates memory (`malloc`, `mmap`), the kernel doesn't immediately allocate physical pages. It creates a virtual mapping and marks it as **not present**. Only when the process actually *accesses* the address does the CPU fault, and the kernel allocates a physical page (**demand paging**). This is why a process can `malloc(1GB)` and show 1 GB of virtual memory but near-zero resident memory — no physical pages are allocated until they're touched.

```bash
# a process's virtual vs. resident memory
ps aux | grep myapp
# VSZ (virtual) = 1,048,576 KB (1 GB allocated)
# RSS (resident) = 256,000 KB (250 MB actually in physical memory)
```

**Copy-on-write (COW):** when `fork()` creates a child, the kernel doesn't copy the parent's memory. It marks all pages as read-only in both parent and child, pointing to the same physical frames. Only when either process *writes* to a page does the kernel copy it — the write triggers a page fault, the kernel allocates a new frame, copies the data, and updates the page table. This makes `fork()` cheap regardless of process size, and is why Redis's background save (`BGSAVE`) can fork a multi-GB process almost instantly.

### Huge Pages

The default 4 KB page size means a 1 GB working set needs 262,144 page table entries. The TLB can only cache a few thousand entries, so large working sets cause constant TLB misses.

**Huge pages** use larger page sizes — 2 MB or 1 GB on x86-64 — reducing the number of TLB entries needed by 512× or 262,144×:

```bash
# check current huge page configuration
cat /proc/meminfo | grep Huge
# HugePages_Total:       0
# HugePages_Free:        0
# Hugepagesize:       2048 kB
```

**[Transparent Huge Pages (THP)](https://docs.kernel.org/admin-guide/mm/transhuge.html):** the kernel automatically promotes regular 4 KB pages to 2 MB huge pages when it detects large contiguous allocations. Enabled by default on most distros:

```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# [always] madvise never
```

**The THP controversy:** THP works well for large, stable allocations (databases, JVMs) but can cause **latency spikes** due to background compaction (the kernel shuffling pages to create contiguous 2 MB blocks) and increased memory waste (a partial 2 MB page wastes more than a partial 4 KB page). Many database operators disable THP:

```bash
# Redis, MongoDB, and others recommend disabling THP
echo never > /sys/kernel/mm/transparent_hugepage/enabled
```

**Explicit huge pages** ([`hugetlbfs`](https://docs.kernel.org/admin-guide/mm/hugetlbpage.html)) pre-allocate huge pages at boot time. No compaction needed, no latency spikes, but you must specify the count upfront. Used by databases and DPDK (network-intensive applications):

```bash
# allocate 1024 × 2MB huge pages (2 GB)
echo 1024 > /proc/sys/vm/nr_hugepages
```

### The Page Cache

The **page cache** is one of Linux's most important performance features — and one of the most misunderstood. The kernel uses **all available free memory** as a cache for file data. When you read a file, the data is kept in memory. When you read it again, it's served from the page cache — no disk I/O.

```bash
free -h
#               total        used        free      shared  buff/cache   available
# Mem:           32Gi        12Gi       1.2Gi       256Mi        18Gi        19Gi
```

The `buff/cache` column (18 GB in this example) is mostly page cache. `available` (19 GB) is what's actually available to new processes — the kernel will reclaim page cache as needed. **A system with 1 GB "free" and 18 GB in cache is healthy, not low on memory.** The cache is reclaimable.

This is the source of the classic confusion: "my server has no free memory!" when `free` shows 1 GB free but 18 GB in cache. The memory isn't "used" in the sense that it's unavailable — it's in use as a performance optimization that the kernel will give up under memory pressure.

```bash
# drop the page cache (diagnostic only — don't do this in production)
echo 3 > /proc/sys/vm/drop_caches

# see per-file cache usage
vmtouch /var/lib/postgresql/data/base/*     # shows how much of each file is cached
fincore /path/to/file                       # newer tool, shows cached pages per file
```

### Memory Reclaim and Swappiness

When memory pressure increases (new allocations need pages), the kernel's **memory reclaim** system decides what to evict. It has two pools to reclaim from:

1. **Page cache** — file-backed pages that can be evicted and re-read from disk.
2. **Anonymous pages** — heap, stack, mmap'd private data. These can only be reclaimed by swapping to disk (swap space).

[`vm.swappiness`](https://docs.kernel.org/admin-guide/sysctl/vm.html#swappiness) (0–200, default 60) controls the **balance** between reclaiming page cache and swapping anonymous pages:

```bash
cat /proc/sys/vm/swappiness
# 60 (default)

# swappiness=0:   strongly prefer reclaiming page cache, avoid swap
# swappiness=60:  balanced (default)
# swappiness=100: treat page cache and anonymous pages equally
# swappiness=200: strongly prefer swapping (unusual)
```

**Common tuning:**
- **Databases** (`swappiness=1` or `swappiness=10`): databases manage their own buffer pools and page cache is critical for performance. Swapping database pages to disk is catastrophic for latency — a single swap-in can add 10ms+ to a query.
- **Container hosts** (`swappiness=60`, default): balanced is usually fine. Kubernetes memory limits use cgroup memory controllers, which enforce limits per-pod.
- **Swap-off** is common in Kubernetes clusters (kubelet historically required `swapoff`, though swap support with cgroup v2 has been added in recent versions).

### The OOM Killer in Depth

When the system (or a cgroup) is truly out of memory — all page cache is reclaimed, all swap is used — the **OOM killer** selects and kills a process. The selection uses an **OOM score** (0–1000):

```bash
cat /proc/[pid]/oom_score       # current OOM score (higher = more likely to be killed)
cat /proc/[pid]/oom_score_adj   # adjustment (-1000 to +1000)

# protect a critical process from OOM killing
echo -1000 > /proc/[pid]/oom_score_adj  # effectively OOM-immune

# make a process a preferred OOM target
echo 1000 > /proc/[pid]/oom_score_adj
```

The OOM score is based on the proportion of memory the process uses, adjusted by `oom_score_adj`. Kubernetes sets `oom_score_adj` based on QoS class:
- **Guaranteed** pods (requests == limits): `oom_score_adj = -997` (almost immune)
- **Burstable** pods: adjusted based on memory request ratio
- **BestEffort** pods (no requests/limits): `oom_score_adj = 1000` (killed first)

### cgroups v2 Memory Controller

The fundamentals guide covered `memory.max` (hard limit → OOM kill). [cgroups v2](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory) has a richer interface:

| File | What it does |
|---|---|
| `memory.max` | Hard limit. Exceeding → OOM kill. This is K8s `limits.memory`. |
| `memory.high` | Soft limit. Exceeding → throttled (reclaim pressure applied, slowing the process). K8s doesn't expose this directly, but it's the more production-friendly limit. |
| `memory.low` | Best-effort protection. Memory below this threshold is protected from reclaim. |
| `memory.min` | Hard protection. Memory below this threshold is never reclaimed. |
| `memory.current` | Current usage. |
| `memory.stat` | Detailed breakdown: anon, file, slab, shmem, etc. |
| `memory.pressure` | PSI (Pressure Stall Information) — how much time tasks are stalled waiting for memory. |

The `memory.high` throttling (introduced in cgroups v2) is often better than `memory.max` OOM killing for production workloads — it slows the process down instead of killing it, giving the application time to adapt (GC, release caches). However, Kubernetes doesn't yet expose a native way to set `memory.high` independently.

### PSI (Pressure Stall Information)

[PSI](https://docs.kernel.org/accounting/psi.html) (kernel 4.20+) quantifies resource pressure — how much time processes spend stalled waiting for CPU, memory, or I/O:

```bash
cat /proc/pressure/memory
# some avg10=0.00 avg60=0.00 avg300=0.00 total=0
# full avg10=0.00 avg60=0.00 avg300=0.00 total=0

cat /proc/pressure/cpu
# some avg10=5.23 avg60=3.10 avg300=2.45 total=123456789

cat /proc/pressure/io
# some avg10=0.50 avg60=0.30 avg300=0.20 total=987654321
# full avg10=0.10 avg60=0.05 avg300=0.03 total=123456789
```

- **`some`**: percentage of time *at least one task* is stalled waiting for the resource.
- **`full`**: percentage of time *all tasks* are stalled (the system is completely blocked).

PSI is the modern way to detect resource pressure before it becomes a crisis. `cgroup.controllers` exposes per-cgroup PSI (`memory.pressure`, `cpu.pressure`, `io.pressure`), and systemd can trigger actions based on PSI thresholds (`MemoryPressureWatch=` in unit files).

### NUMA Memory Policy

On NUMA systems, memory allocation policy determines where physical pages are allocated:

```bash
numactl --interleave=all ./myapp     # spread allocations across all nodes (good for throughput)
numactl --membind=0 ./myapp          # all allocations on node 0 (good for latency with pinned CPU)
numactl --preferred=0 ./myapp        # prefer node 0, fall back to others
```

`numastat -p [pid]` shows per-node allocation breakdown for a running process. `numastat -m` shows per-node memory statistics. A high "Other Node" hit count in `numastat` indicates cross-node access — a performance problem.

If you remember one thing from Part 2: **Linux uses all free memory as page cache (so "no free memory" usually means "great caching, not a problem" — check `available` instead of `free`), swappiness controls the balance between evicting cache and swapping, and the OOM killer's behavior in containers is controlled by cgroup memory limits (`memory.max` for hard kill, `memory.high` for graceful throttling) — and Kubernetes sets `oom_score_adj` by QoS class to decide which pod dies first.**

---

## Part 3 — The I/O Stack

The I/O path from your application's `write()` call to bits on the storage device is a deep stack of layers, each with tunable behavior. Understanding it explains why `fsync` is slow, why `io_uring` is fast, and how to diagnose I/O bottlenecks.

### The I/O Path

```
Application
    │
    ▼
 VFS (Virtual File System)         ← file-system-agnostic layer
    │
    ▼
 Filesystem (ext4, xfs, btrfs)    ← translates files to blocks
    │
    ▼
 Page Cache                        ← buffered I/O lives here
    │
    ▼
 Block Layer                       ← I/O scheduling, merging, plugging
    │
    ▼
 Device Driver (NVMe, SCSI, etc.)  ← talks to hardware
    │
    ▼
 Storage Device (SSD, HDD, NVMe)
```

### Buffered vs. Direct I/O

**Buffered I/O** (the default): reads and writes go through the **page cache**.
- `write()` copies data to the page cache and returns immediately. The kernel writes it to disk later ("writeback"). Fast from the application's perspective.
- `read()` checks the page cache first. Cache hit = no disk I/O. Cache miss = read from disk, populate cache.
- Trade-off: data isn't durable until the kernel writes it back. Crash between `write()` and writeback = data loss.

**Direct I/O** (`O_DIRECT`): bypasses the page cache entirely. Data goes directly between the application's buffer and the storage device.
- Used by databases (PostgreSQL, MySQL, RocksDB) that manage their own buffer pool and don't want the kernel double-caching their data.
- Requires page-aligned buffers and page-aligned offsets.
- Eliminates cache pollution for large sequential scans.

```c
int fd = open("/path/to/file", O_RDWR | O_DIRECT);
// reads and writes bypass the page cache
```

### Durability: fsync, fdatasync, and Barriers

The critical question for data integrity: **when is my data actually on the storage device?**

| Call | Guarantee |
|---|---|
| `write()` | Data is in the page cache. Survives process crash, NOT system crash. |
| [`fsync(fd)`](https://man7.org/linux/man-pages/man2/fsync.2.html) | Data AND metadata (size, timestamps) are on the storage device. Survives system crash. **Expensive** — waits for device to acknowledge write. |
| `fdatasync(fd)` | Data is on device. Metadata only if it affects retrieval (e.g., file size changed). Slightly cheaper than `fsync`. |
| `sync()` | Flushes ALL dirty pages for all files. Nuclear option. |
| `O_SYNC` | Every `write()` is implicitly `fsync`'d. Very expensive. |
| `O_DSYNC` | Every `write()` is implicitly `fdatasync`'d. |

Databases call `fdatasync` after every WAL (write-ahead log) write to guarantee durability. This is the single most latency-sensitive syscall in a database workload — and why NVMe drives (with ~20 µs fsync latency) transformed database performance versus SATA SSDs (~100-500 µs) and HDDs (~5-15 ms).

### I/O Schedulers

The block layer's I/O scheduler reorders and merges I/O requests before sending them to the device:

| Scheduler | How it works | Best for |
|---|---|---|
| **none** | No reordering — FIFO. Let the device sort it out. | NVMe SSDs (which have their own sophisticated queue management) |
| **mq-deadline** | Ensures reads and writes complete within a deadline. Prevents starvation. | General-purpose, HDDs, SATA SSDs |
| **bfq** (Budget Fair Queueing) | Fair bandwidth sharing between processes, with prioritization. | Desktop, interactive workloads |
| **kyber** | Lightweight token-based scheduler for fast devices. | Fast SSDs that need minimal scheduling |

```bash
# check current scheduler
cat /sys/block/sda/queue/scheduler
# [mq-deadline] kyber bfq none

# change scheduler (runtime)
echo none > /sys/block/nvme0n1/queue/scheduler
```

Modern NVMe drives have internal parallelism and their own scheduling — adding a software scheduler on top adds latency for no benefit. Use `none` for NVMe.

### io_uring: The Modern I/O Interface

[`io_uring`](https://man7.org/linux/man-pages/man7/io_uring.7.html) (kernel 5.1+, mature by 6.x; Jens Axboe's [design document](https://kernel.dk/io_uring.pdf) is the canonical description) is the biggest I/O development of the last decade. It replaces the aging `read`/`write`/`pread`/`pwrite`/`aio` interfaces with a high-performance asynchronous I/O mechanism.

The core idea: **two shared-memory ring buffers** between userspace and the kernel — a **submission queue (SQ)** and a **completion queue (CQ)**. The application pushes I/O requests to the SQ; the kernel processes them and pushes completions to the CQ. No system call overhead per I/O operation.

```
User Space                          Kernel
┌──────────────────┐               ┌──────────────────┐
│ Submit I/O       │──── SQ Ring ──▶│ Process I/O      │
│ operations       │               │ (async)          │
│                  │◀── CQ Ring ───│ Return results   │
│ Poll completions │               │                  │
└──────────────────┘               └──────────────────┘

Key: the rings are shared memory — no copying, no syscalls per I/O.
io_uring_enter() can submit a batch AND poll completions in one syscall.
With SQPOLL, even that syscall is eliminated — a kernel thread polls the SQ.
```

**Why io_uring is fast:**
1. **Batched submission and completion** — amortize syscall overhead across many I/O operations.
2. **Zero-copy** — shared memory rings, no data copying between user/kernel for metadata.
3. **Kernel-side polling (SQPOLL)** — a dedicated kernel thread polls the SQ, eliminating syscalls entirely for submission.
4. **Fixed buffers and files** — register buffers and file descriptors once, reference them by index (avoids repeated kernel lookups).

**io_uring supports more than disk I/O:**
- Network I/O (accept, connect, send, recv)
- File operations (open, close, stat, rename)
- Timers, cancellation, linked operations

This makes io_uring a potential replacement for `epoll` as a general-purpose event loop — and frameworks like Rust's Tokio (via io_uring backend) and new C/C++ servers are adopting it.

```bash
# check io_uring support
cat /proc/sys/kernel/io_uring_disabled
# 0 = enabled (default)
# 1 = disabled for unprivileged users
# 2 = disabled for all
```

**Security note:** io_uring's broad kernel interface has been a source of security vulnerabilities. Some organizations (Google, internally) have disabled it for unprivileged users. Container runtimes may restrict it via seccomp profiles.

### Readahead

The kernel performs **readahead** — predicting that if you're reading sequentially, you'll want the *next* blocks too, and pre-fetching them into the page cache before you ask for them. This is why sequential reads are fast (the data is already in cache by the time you need it).

```bash
# check/set readahead (in 512-byte sectors)
blockdev --getra /dev/sda          # default is typically 256 (128 KB)
blockdev --setra 2048 /dev/sda     # set to 1 MB (good for sequential workloads)
```

For databases doing mostly random I/O, reducing readahead can save memory (no wasted prefetching). For streaming workloads (video, backups, large file copies), increasing it improves throughput.

### Writeback

When you `write()` to a file (buffered I/O), the kernel marks the page as **dirty** and returns immediately. Background kernel threads (`kworker/flush`) write dirty pages to disk periodically:

```bash
# dirty page thresholds
cat /proc/sys/vm/dirty_ratio
# 20  (% of total memory — if dirty pages exceed this, processes block on write())

cat /proc/sys/vm/dirty_background_ratio
# 10  (% — background writeback starts when dirty pages exceed this)

cat /proc/sys/vm/dirty_expire_centisecs
# 3000  (30 seconds — dirty pages older than this are written back)

cat /proc/sys/vm/dirty_writeback_centisecs
# 500  (5 seconds — how often the writeback thread wakes up)
```

Tuning these affects the trade-off between write throughput (batch more dirty pages = fewer I/O operations) and data-at-risk (more dirty pages = more data lost on crash).

### Benchmarking I/O with fio

[`fio`](https://fio.readthedocs.io/en/latest/fio_doc.html) (Flexible I/O Tester) is the standard tool for I/O benchmarking:

```bash
# sequential read throughput
fio --name=seqread --rw=read --bs=1M --size=1G --numjobs=1 --runtime=30 --time_based

# random read IOPS (the database-relevant benchmark)
fio --name=randread --rw=randread --bs=4k --size=1G --numjobs=4 --iodepth=32 --runtime=30 --time_based

# random write latency
fio --name=randwrite --rw=randwrite --bs=4k --size=1G --numjobs=1 --iodepth=1 --fsync=1 --runtime=30 --time_based

# io_uring engine
fio --name=io_uring_test --ioengine=io_uring --rw=randread --bs=4k --size=1G --iodepth=64 --runtime=30 --time_based
```

Key metrics: **IOPS** (operations/sec — matters for databases), **throughput** (MB/s — matters for sequential workloads), **latency** (especially p99 — matters for everything).

The `--fsync=1` flag makes fio call fsync after every write — the realistic scenario for databases. Without it, writes land in the page cache and look impossibly fast.

If you remember one thing from Part 3: **`write()` only goes to the page cache — data isn't durable until `fsync`/`fdatasync`, use `none` scheduler for NVMe, and io_uring is the modern high-performance I/O interface that eliminates per-operation syscall overhead through shared-memory ring buffers — and it's increasingly used for networking too, not just disk.**

---

## Part 4 — Advanced Networking

The fundamentals guide covered interfaces, veth pairs, bridges, and iptables. This part goes deeper into the mechanisms that power production networking — traffic control, TCP tuning, nftables, IPVS, and the kernel's network processing pipeline.

### The Network Processing Pipeline

When a packet arrives at a network interface, it traverses a complex kernel pipeline:

```
NIC hardware → Driver → GRO → XDP (eBPF hook) → Netfilter/nftables
    → Routing decision → Local delivery or Forwarding
    → Transport (TCP/UDP) → Socket buffer → Application read()
```

Each stage is a hook point where you can inspect, modify, or drop packets. Understanding this pipeline is how you reason about where to place your firewall rules, traffic shaping, and eBPF programs for maximum efficiency.

**GRO (Generic Receive Offload):** the driver coalesces small packets into larger ones before passing them up the stack, reducing per-packet processing overhead. This is why a busy network interface doesn't show millions of tiny packets — GRO batches them.

**NAPI (New API):** instead of firing an interrupt per packet (expensive at high rates), NAPI switches to polling mode during high traffic — the kernel polls the NIC for batches of packets. This prevents interrupt storms on busy servers.

### nftables: The Modern Firewall

[nftables](https://wiki.nftables.org/wiki-nftables/index.php/Main_Page) replaced iptables starting with kernel 3.13 and is the default on modern distros. It provides a unified framework for packet filtering, NAT, and traffic classification:

```bash
# list all rules
nft list ruleset

# create a basic firewall
nft add table inet filter
nft add chain inet filter input { type filter hook input priority 0 \; policy drop \; }
nft add rule inet filter input ct state established,related accept
nft add rule inet filter input iifname "lo" accept
nft add rule inet filter input tcp dport { 22, 80, 443 } accept
nft add rule inet filter input counter drop
```

**Advantages over iptables:**
- **Single tool** for IPv4, IPv6, ARP, and bridging (iptables needed separate tools: `iptables`, `ip6tables`, `ebtables`, `arptables`).
- **Better performance** — a single rule can match multiple values (sets, maps, concatenations) instead of one rule per value.
- **Atomic rule updates** — replace entire rulesets atomically (iptables restores are not atomic).
- **First-class sets and maps** — `nft add set inet filter allowed_ips { type ipv4_addr \; }` creates a set you can add/remove elements from without touching rules.

iptables still works (via a compatibility layer) but new deployments should use nftables.

### TCP Tuning

TCP performance on Linux is largely controlled by buffer sizes and congestion control. The defaults are reasonable for LAN traffic but often suboptimal for high-bandwidth or high-latency networks.

**Buffer sizes:**

```bash
# TCP receive buffer (min, default, max)
cat /proc/sys/net/ipv4/tcp_rmem
# 4096  131072  6291456   (4KB min, 128KB default, 6MB max)

# TCP send buffer
cat /proc/sys/net/ipv4/tcp_wmem
# 4096  16384   4194304   (4KB min, 16KB default, 4MB max)

# for high-bandwidth links (10+ Gbps), increase the max:
sysctl -w net.ipv4.tcp_rmem="4096 131072 16777216"   # 16MB max receive
sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"    # 16MB max send
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216
```

**Congestion control:**

```bash
# available algorithms
cat /proc/sys/net/ipv4/tcp_available_congestion_control
# reno cubic bbr

# current default
cat /proc/sys/net/ipv4/tcp_congestion_control
# cubic (the default since kernel 2.6.19)

# switch to BBR (Google's congestion control — better for WAN/internet traffic)
sysctl -w net.ipv4.tcp_congestion_control=bbr
sysctl -w net.core.default_qdisc=fq   # BBR requires the fq qdisc
```

**[BBR](https://github.com/google/bbr) (Bottleneck Bandwidth and Round-trip propagation time)** is a model-based congestion control algorithm developed by Google (the [ACM Queue paper](https://queue.acm.org/detail.cfm?id=3022184) explains the model). Unlike Cubic (which reacts to packet loss), BBR probes for available bandwidth and minimum RTT, achieving better throughput on lossy networks (internet, WAN links) and faster convergence. BBR v3 (kernel 6.x+) fixes fairness issues from BBR v1.

**`SO_REUSEPORT`:**

```c
int opt = 1;
setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
```

Allows multiple processes/threads to bind to the same port (see [`socket(7)`](https://man7.org/linux/man-pages/man7/socket.7.html)). The kernel distributes incoming connections across the listeners using a hash. This is how Nginx and Envoy achieve per-CPU accept() parallelism — each worker binds to the same port, and the kernel load-balances at the socket level. Without `SO_REUSEPORT`, only one process can accept() at a time (the thundering-herd problem).

### IPVS (IP Virtual Server)

[IPVS](http://www.linuxvirtualserver.org/software/ipvs.html) is a transport-layer (L4) load balancer built into the Linux kernel. It's an alternative to iptables-based load balancing for [Kubernetes Services](https://kubernetes.io/docs/reference/networking/virtual-ips/):

```bash
# Kubernetes kube-proxy in IPVS mode
ipvsadm -Ln
# TCP  10.96.0.1:443 rr
#   -> 10.244.0.5:6443    Masq    1      0          0
#   -> 10.244.1.3:6443    Masq    1      0          0
```

**IPVS vs. iptables for Kubernetes Services:**

| Feature | iptables | IPVS |
|---|---|---|
| **Performance** | O(n) rule traversal per packet | O(1) hash lookup |
| **Scale** | degrades badly above ~5,000 Services | handles 10,000+ Services |
| **Algorithms** | random (probabilistic DNAT rules) | rr, wrr, lc, wlc, sh, sed, nq |
| **Connection tracking** | via conntrack | via conntrack |

For clusters with more than a few thousand Services, IPVS mode is strongly recommended.

### Traffic Control (tc)

[`tc`](https://man7.org/linux/man-pages/man8/tc.8.html) is the kernel's traffic control framework — it shapes, schedules, and polices network traffic using **queuing disciplines (qdiscs)**:

```bash
# show current qdisc on an interface
tc qdisc show dev eth0

# rate-limit outgoing traffic to 100 Mbit/s
tc qdisc add dev eth0 root tbf rate 100mbit burst 32kbit latency 400ms

# add 100ms latency (useful for testing)
tc qdisc add dev eth0 root netem delay 100ms

# simulate packet loss (for testing)
tc qdisc add dev eth0 root netem loss 1%

# simulate jitter
tc qdisc add dev eth0 root netem delay 100ms 30ms distribution normal

# remove qdisc
tc qdisc del dev eth0 root
```

[`netem`](https://man7.org/linux/man-pages/man8/tc-netem.8.html) (Network Emulator) is particularly useful for testing how your application handles degraded networks — simulate latency, jitter, loss, and reordering in a controlled environment.

### Conntrack (Connection Tracking)

**[conntrack](https://man7.org/linux/man-pages/man8/conntrack.8.html)** is the kernel's connection tracking subsystem — it tracks the state of network connections (TCP, UDP, ICMP) for stateful firewalling and NAT. Every connection passing through netfilter/nftables is tracked:

```bash
# view active connections
conntrack -L
conntrack -L -p tcp --dport 80   # filter by protocol and port
conntrack -C                      # count of tracked connections

# conntrack table size
cat /proc/sys/net/netfilter/nf_conntrack_max
# 262144 (default — may need to be raised for busy load balancers)

sysctl -w net.netfilter.nf_conntrack_max=524288
```

**Conntrack table exhaustion** is a common production issue on busy Kubernetes nodes and load balancers. When the table fills up, new connections are dropped. Symptoms: random connection failures, "nf_conntrack: table full, dropping packet" in `dmesg`. Fix: raise `nf_conntrack_max` or reduce `nf_conntrack_tcp_timeout_time_wait`.

### Unix Domain Sockets

For inter-process communication on the same host, **Unix domain sockets** are significantly faster than TCP loopback (127.0.0.1) because they bypass the entire TCP/IP stack — no checksums, no routing, no network-layer headers:

```bash
# Docker daemon listens on a Unix socket
ls -l /var/run/docker.sock
# srw-rw---- 1 root docker 0 Jan 1 00:00 /var/run/docker.sock

# connect to it
curl --unix-socket /var/run/docker.sock http://localhost/version
```

PostgreSQL, MySQL, Redis, and Docker all prefer Unix domain sockets for local connections. Performance difference vs. TCP loopback is typically 30–50% higher throughput and lower latency.

If you remember one thing from Part 4: **nftables replaces iptables with a cleaner, faster, atomic-update model; BBR congestion control is better than Cubic for internet traffic; SO_REUSEPORT enables per-CPU accept() parallelism; IPVS is O(1) for Service load balancing while iptables is O(n); conntrack table exhaustion kills connections on busy nodes; and Unix domain sockets bypass the TCP/IP stack entirely for same-host IPC.**

---

## Part 5 — eBPF

[eBPF](https://ebpf.io/what-is-ebpf/) (extended Berkeley Packet Filter) is a technology that lets you run sandboxed programs in the Linux kernel — without modifying the kernel source or loading kernel modules. It's the most transformative Linux technology of the last decade, powering modern networking (Cilium), security (Falco, Tetragon), and observability (Pixie, continuous profiling).

### What eBPF Is

```
┌──────────────────────────────────────────────────────────────────┐
│                         Kernel                                   │
│                                                                  │
│  ┌─────────┐   ┌──────────┐   ┌──────────────┐                  │
│  │Scheduler│   │ Network  │   │ Filesystem   │                  │
│  │         │   │ Stack    │   │              │                  │
│  │ ▲       │   │ ▲        │   │ ▲            │                  │
│  │ │       │   │ │        │   │ │            │                  │
│  │ │eBPF   │   │ │eBPF    │   │ │eBPF        │  ← hook points  │
│  │ │program │   │ │program │   │ │program     │                  │
│  └─────────┘   └──────────┘   └──────────────┘                  │
│       ▲              ▲              ▲                            │
│       │              │              │    ┌──────────┐            │
│       └──────────────┴──────────────┴────│ Verifier │            │
│                                          │ (safety) │            │
│                                          └──────────┘            │
└──────────────────────────────────────────────────────────────────┘
         ▲                    │
         │ load program       │ maps (shared data)
         │                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                        User Space                                │
│  bpftrace, bcc tools, Cilium, Falco, custom programs            │
└──────────────────────────────────────────────────────────────────┘
```

**The lifecycle:**
1. You write an eBPF program (in C, Rust, or a high-level DSL like bpftrace).
2. The **verifier** statically analyzes the program to guarantee safety — no infinite loops, no invalid memory access, no crashing the kernel. If it passes, the program is loaded into the kernel.
3. The program is **attached to a hook point** — a specific kernel event (syscall, network packet, tracepoint, scheduler event).
4. When the event fires, the eBPF program runs in the kernel context — fast, with access to kernel data structures.
5. Programs communicate with userspace through **maps** — shared data structures (hash maps, arrays, ring buffers, LRU caches, stacks, queues).

### The Verifier

The [verifier](https://docs.kernel.org/bpf/verifier.html) is what makes eBPF safe — it statically analyzes every program before loading to guarantee:

- **Terminates.** No loops without bounded iteration counts (recently relaxed for known-bounded loops). The program cannot hang the kernel.
- **Memory safety.** All pointer accesses are validated — no reading outside allocated buffers, no writing to read-only kernel memory.
- **Stack limit.** Maximum 512 bytes of stack space (prevents stack overflow in kernel context).
- **No sleeping.** eBPF programs run in atomic context — they cannot sleep, allocate memory with GFP_KERNEL, or call arbitrary kernel functions (only approved "helper functions").

The verifier rejects programs it can't prove safe — which sometimes means you need to restructure your code to help the verifier understand your bounds. This is the main source of friction when writing eBPF programs.

### eBPF Maps

Maps are shared data structures accessible from both eBPF programs (kernel side) and userspace:

| Map Type | Description | Use Case |
|---|---|---|
| `BPF_MAP_TYPE_HASH` | Key-value hash table | Per-IP counters, connection tracking |
| `BPF_MAP_TYPE_ARRAY` | Fixed-size array indexed by integer | Per-CPU counters, configuration |
| `BPF_MAP_TYPE_RINGBUF` | Lock-free ring buffer for events | Streaming events to userspace |
| `BPF_MAP_TYPE_LRU_HASH` | Hash table with LRU eviction | Caches that shouldn't grow unbounded |
| `BPF_MAP_TYPE_PERCPU_HASH` | Per-CPU hash table | High-throughput counters without locking |
| `BPF_MAP_TYPE_PERF_EVENT_ARRAY` | Per-CPU event buffers | Older event streaming (ringbuf preferred) |
| `BPF_MAP_TYPE_STACK_TRACE` | Stack trace storage | Profiling |

### eBPF Program Types

| Type | Hook Point | Use Case |
|---|---|---|
| **kprobe/kretprobe** | any kernel function entry/return | tracing, debugging |
| **tracepoint** | stable kernel trace points | observability (more stable than kprobes) |
| **uprobe/uretprobe** | any userspace function entry/return | application-level tracing without modifying the app |
| **XDP** | network driver (before the kernel processes the packet) | ultra-fast packet filtering, DDoS mitigation |
| **TC** | traffic control layer | packet manipulation, policy enforcement |
| **cgroup** | cgroup events (socket, device, sysctl) | container networking, per-cgroup policy |
| **LSM** | Linux Security Module hooks | security policy enforcement |
| **sched_ext** | scheduler | custom scheduling policies (kernel 6.12+) |
| **perf_event** | hardware/software performance counters | profiling |
| **fentry/fexit** | kernel function entry/exit (faster than kprobe) | modern tracing with lower overhead |

### XDP (eXpress Data Path)

[XDP](https://prototype-kernel.readthedocs.io/en/latest/networking/XDP/index.html) runs eBPF programs at the **earliest possible point** in the network stack — in the network driver, before the kernel allocates an `sk_buff` (the per-packet data structure). This makes XDP extremely fast for packet filtering:

```
Without XDP:                        With XDP:
NIC → driver → sk_buff alloc →     NIC → driver → XDP program → DROP
      netfilter → routing →                     ↓
      transport → socket →                     PASS → normal stack
      application                              TX → redirect to another NIC
```

XDP actions:
- `XDP_DROP` — drop the packet (DDoS mitigation)
- `XDP_PASS` — continue normal kernel processing
- `XDP_TX` — reflect the packet back out the same NIC
- `XDP_REDIRECT` — forward to another NIC, CPU, or AF_XDP socket

XDP can drop 10+ million packets per second per core — compared to iptables' ~1-2 million. This is why Cloudflare and Facebook use XDP for DDoS mitigation.

### bpftrace: The High-Level Tool

[`bpftrace`](https://bpftrace.org/) is a high-level tracing language (like awk for eBPF):

```bash
# trace all open() syscalls, showing PID and filename
bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%d %s %s\n", pid, comm, str(args->filename)); }'

# histogram of read() return values (bytes read)
bpftrace -e 'tracepoint:syscalls:sys_exit_read /args->ret > 0/ { @bytes = hist(args->ret); }'

# count syscalls by process
bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'

# latency histogram for block I/O
bpftrace -e 'tracepoint:block:block_rq_issue { @start[args->dev, args->sector] = nsecs; }
              tracepoint:block:block_rq_complete /@start[args->dev, args->sector]/ {
                @usecs = hist((nsecs - @start[args->dev, args->sector]) / 1000);
                delete(@start[args->dev, args->sector]);
              }'

# trace TCP retransmissions
bpftrace -e 'kprobe:tcp_retransmit_skb { @retransmits[comm, pid] = count(); }'

# who is calling write() on a specific file?
bpftrace -e 'tracepoint:syscalls:sys_enter_write /args->fd == 3/ { printf("%s %d\n", comm, pid); }'
```

### BCC Tools: The Pre-Built Toolkit

[BCC](https://github.com/iovisor/bcc) (BPF Compiler Collection) provides 100+ ready-made eBPF tools:

```bash
# trace TCP connections
tcpconnect                       # trace outgoing TCP connections
tcpaccept                        # trace incoming TCP connections
tcplife                          # trace TCP session lifetimes
tcpretrans                       # trace TCP retransmissions

# trace file I/O
fileslower 10                    # files taking >10ms to read/write
opensnoop                        # trace file opens
filelife                         # trace file creation and deletion

# trace process activity
execsnoop                        # trace new process executions (see every exec on the system)
runqlat                          # scheduler run queue latency histogram
cpudist                          # on-CPU time distribution per process
exitsnoop                        # trace process exits with exit code

# trace memory
memleak                          # detect memory leaks (tracks allocations)
oomkill                          # trace OOM killer events
cachestat                        # page cache hit/miss statistics

# trace disk
biolatency                       # block I/O latency histogram
biosnoop                         # trace individual block I/O requests
biotop                           # top-like for block I/O
```

### CO-RE (Compile Once, Run Everywhere)

eBPF programs traditionally needed to be compiled against the specific kernel headers of the target machine. **CO-RE** (kernel 5.4+, via [BTF — BPF Type Format](https://docs.kernel.org/bpf/btf.html)) enables compiling an eBPF program once and running it on any kernel version — the loader adjusts field offsets at load time. This is what makes production eBPF tools portable.

```bash
# check if your kernel has BTF (required for CO-RE)
ls /sys/kernel/btf/vmlinux
# if it exists, BTF is available
```

### libbpf: The Production Library

[`libbpf`](https://libbpf.readthedocs.io/en/latest/) is the standard C library for loading and interacting with eBPF programs. The modern workflow:

1. Write the eBPF program in C
2. Compile it with clang to BPF bytecode
3. Use libbpf in userspace to load, attach, and read maps
4. CO-RE + BTF makes it portable

For Go, the [`cilium/ebpf`](https://github.com/cilium/ebpf) library is the standard. For Rust, [`aya`](https://aya-rs.dev/). For Python, `bcc` (easier but less portable than libbpf).

### eBPF in Production (2026)

| Project | Use Case | What It Replaces |
|---|---|---|
| **[Cilium](https://cilium.io/)** | Kubernetes CNI — networking, load balancing, network policy | kube-proxy (iptables/IPVS), Calico iptables mode |
| **[Tetragon](https://tetragon.io/)** | Runtime security — syscall monitoring, process policy | auditd, traditional LSMs for runtime detection |
| **[Falco](https://falco.org/)** | Threat detection — anomaly detection at the syscall level | host-based IDS |
| **Pixie** | Kubernetes observability — auto-instrumentation | manual instrumentation, sidecars |
| **Parca / Pyroscope** | Continuous profiling | periodic profiling, manual perf runs |
| **Grafana Beyla** | Auto-instrumented application observability (HTTP, gRPC, DB) | OpenTelemetry manual instrumentation |
| **sched_ext** | Custom kernel scheduling in eBPF | kernel recompilation for scheduler changes |

**Cilium deserves special attention:** it replaces kube-proxy entirely, implementing Kubernetes Services and Network Policies in eBPF — O(1) per packet instead of iptables' O(n). At scale (thousands of Services), this is a massive performance improvement. Cilium can also enforce L7 (HTTP, gRPC) policies — something iptables cannot do at all.

If you remember one thing from Part 5: **eBPF lets you run custom programs inside the kernel — safely, with no recompilation — at hook points across networking, scheduling, security, and filesystems. In 2026, Cilium (networking), Tetragon/Falco (security), and bpftrace (tracing) are the three most impactful eBPF applications, and `sched_ext` (custom schedulers in eBPF) is the most exciting new development.**

---

## Part 6 — Performance Analysis

The fundamentals guide covered `ps`, `top`, `strace`, and `ss`. This part covers systematic performance analysis methodology and the advanced tools.

### The USE Method

Brendan Gregg's **[USE Method](https://www.brendangregg.com/usemethod.html)** (Utilization, Saturation, Errors) provides a systematic checklist for every resource:

| Resource | Utilization (busy %) | Saturation (queue depth) | Errors |
|---|---|---|---|
| **CPU** | `mpstat -P ALL 1` (%usr+%sys) | `vmstat 1` → r column (run queue), `runqlat` | `perf stat` → cache misses |
| **Memory** | `free -h` → used/total | `vmstat 1` → si/so (swap in/out), `sar -B` (page scans) | `dmesg` → OOM messages |
| **Disk** | `iostat -x 1` → %util per device | `iostat -x 1` → avgqu-sz | `iostat -x 1` → errors, `smartctl` |
| **Network** | `sar -n DEV 1` → rxkB/s, txkB/s vs capacity | `ss -tanp` → send/recv queue sizes | `ip -s link` → errors, drops |
| **File descriptors** | `lsof -p [pid] \| wc -l` vs `ulimit -n` | — | `dmesg`, errno EMFILE/ENFILE |

Work through this list for each resource when diagnosing performance problems. Most problems show up as high utilization or saturation on one specific resource.

### The RED Method (for Services)

While USE works for infrastructure, the **RED Method** works for services:

- **Rate** — requests per second
- **Errors** — failed requests per second
- **Duration** — request latency distribution (especially p50, p95, p99)

USE and RED are complementary: RED tells you *what's wrong from the user's perspective* (slow requests), USE tells you *why* (disk is saturated).

### perf: The Swiss Army Knife

[`perf`](https://perf.wiki.kernel.org/index.php/Main_Page) is the kernel's built-in profiling tool, using hardware performance counters (PMU):

```bash
# CPU profiling — where is CPU time going?
perf record -g -p 12345 -- sleep 30     # record call stacks for 30s
perf report                              # interactive TUI
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg  # flame graph

# count events
perf stat -p 12345 -- sleep 10
# Performance counter stats for PID 12345:
#   2,500,000,000  cycles
#   1,200,000,000  instructions  # IPC = 0.48 (low — likely memory-bound)
#      50,000,000  cache-misses  # 5% miss rate
#     800,000,000  cache-references

# trace specific events
perf trace -p 12345                      # trace syscalls (like strace but lower overhead)
perf trace -e sched:sched_switch         # trace scheduler context switches

# list available events
perf list                                # hundreds of events: hardware, software, tracepoints
```

**Key insight:** the **instructions per cycle (IPC)** from `perf stat` tells you whether a workload is CPU-bound (high IPC, >1.0) or memory-bound (low IPC, <0.5). A memory-bound workload with low IPC won't benefit from a faster clock — it needs better cache utilization or memory access patterns.

### Flame Graphs

[Flame graphs](https://www.brendangregg.com/flamegraphs.html) visualize **where CPU time is spent** across the entire call stack. The x-axis is not time — it's the alphabetically sorted set of stack frames. The width of a frame is the proportion of total samples that include it.

```bash
# CPU flame graph (on-CPU analysis)
perf record -F 99 -g -p 12345 -- sleep 30
perf script > perf.stacks
stackcollapse-perf.pl perf.stacks | flamegraph.pl > cpu.svg

# off-CPU flame graph (where is the process WAITING?)
# use 'offcputime' from BCC tools
offcputime-bpfcc -p 12345 30 > offcpu.stacks
flamegraph.pl --color=io < offcpu.stacks > offcpu.svg
```

**On-CPU** flame graphs show where processing time goes (computation, cache misses, page faults). **Off-CPU** flame graphs show where waiting time goes (I/O, locks, sleep, scheduling delays). A process that's slow but with low CPU usage needs an off-CPU analysis — the bottleneck is waiting, not computing.

### ftrace: Kernel Function Tracing

[`ftrace`](https://docs.kernel.org/trace/ftrace.html) is the kernel's built-in tracing infrastructure:

```bash
# trace all kernel functions called during a command
trace-cmd record -p function_graph ls
trace-cmd report

# trace specific functions
echo do_sys_openat2 > /sys/kernel/debug/tracing/set_ftrace_filter
echo function > /sys/kernel/debug/tracing/current_tracer
cat /sys/kernel/debug/tracing/trace_pipe
```

### Advanced Diagnostic Patterns

**Latency analysis — where does request time go?**

```bash
# 1. is it on-CPU or off-CPU?
pidstat -p 12345 1               # high %CPU → on-CPU, low %CPU → off-CPU

# 2. if on-CPU: where in the code?
perf record -g -p 12345 -- sleep 10
perf report

# 3. if off-CPU: what is it waiting for?
offcputime-bpfcc -p 12345 10     # stack traces of where it's sleeping
# or:
bpftrace -e 'tracepoint:sched:sched_switch /pid == 12345/ { printf("%s\n", kstack); }'

# 4. common off-CPU causes:
#    - futex (lock contention) → profile locks
#    - epoll_wait (waiting for I/O) → check what I/O
#    - read/write on a specific fd → trace that fd
```

**Lock contention analysis:**

```bash
# mutex contention (BCC tool)
offcputime-bpfcc -K -p 12345 10   # -K for kernel stacks
# look for futex_wait in the stacks → lock contention

# or use perf's lock analysis
perf lock record -p 12345 -- sleep 10
perf lock report
```

**Memory leak detection:**

```bash
# BCC memleak tool
memleak-bpfcc -p 12345 10        # track allocations for 10 seconds
# shows stack traces for allocations that were never freed
```

### The Performance Analysis Workflow

```
1. Define the problem clearly
   "API latency p99 increased from 50ms to 200ms since yesterday"

2. USE Method — check every resource
   CPU: mpstat → not saturated (40% util)
   Memory: free → fine, no OOM
   Disk: iostat → %util 95% on sda! → FOUND IT
   Network: sar → fine

3. Drill down on the bottleneck
   biolatency → latency histogram shows bimodal: most <1ms, some >50ms
   biosnoop → specific files causing slow I/O
   → identified: a background cron job doing sequential scans is evicting
     database data from the page cache

4. Confirm and fix
   → move cron job to off-peak hours / use O_DIRECT / add more RAM
   → verify: p99 back to 50ms
```

If you remember one thing from Part 6: **use the USE Method (Utilization, Saturation, Errors) as a checklist for every resource, `perf stat` IPC tells you if you're CPU-bound or memory-bound, flame graphs show where time is spent (on-CPU) or waited (off-CPU), and most performance problems show up as high utilization or saturation on one specific resource — find that resource first.**

---

## Part 7 — Security Hardening

The fundamentals guide covered permissions, capabilities, and the container security model. This part covers the active defense mechanisms — mandatory access control, syscall filtering, audit, and hardening practices.

### Mandatory Access Control: SELinux and AppArmor

Standard Unix permissions (DAC — Discretionary Access Control) have a fundamental limitation: the file owner controls access. If a process is compromised, it has all the permissions of the user it runs as. **Mandatory Access Control (MAC)** adds a second layer where the **system administrator** defines policies that even the file owner can't override.

**[SELinux](https://selinuxproject.org/page/Main_Page)** (Security-Enhanced Linux) — developed by the NSA, default on RHEL/Fedora/CentOS:

```bash
# check SELinux status
getenforce
# Enforcing / Permissive / Disabled

# temporarily set to permissive (logs violations but doesn't block)
setenforce 0

# view the security context of a file
ls -Z /var/www/html/index.html
# system_u:object_r:httpd_sys_content_t:s0

# view the security context of a process
ps auxZ | grep nginx
# system_u:system_r:httpd_t:s0  nginx ...

# SELinux denies nginx from reading a file with the wrong type:
# httpd_t (nginx) can read httpd_sys_content_t, NOT user_home_t
# fix: change the file's type
chcon -t httpd_sys_content_t /var/www/html/newfile.html
# or make it permanent:
semanage fcontext -a -t httpd_sys_content_t "/var/www/html(/.*)?"
restorecon -rv /var/www/html
```

SELinux uses **type enforcement**: every process has a **domain** (e.g., `httpd_t`), every file has a **type** (e.g., `httpd_sys_content_t`), and the policy defines which domains can access which types. If the policy doesn't allow it, the access is denied — regardless of Unix permissions.

**[AppArmor](https://apparmor.net/)** — default on Ubuntu/Debian/SUSE. Simpler than SELinux, path-based instead of label-based:

```bash
# check AppArmor status
aa-status

# an AppArmor profile for nginx
# /etc/apparmor.d/usr.sbin.nginx
profile nginx /usr/sbin/nginx {
  /var/www/html/** r,           # can read web content
  /var/log/nginx/** w,          # can write logs
  /etc/nginx/** r,              # can read config
  /run/nginx.pid rw,            # PID file
  network inet stream,           # TCP sockets
  deny /etc/shadow r,            # explicitly deny shadow
}
```

**SELinux vs. AppArmor:**

| Aspect | SELinux | AppArmor |
|---|---|---|
| **Model** | Label-based (security contexts on every object) | Path-based (rules reference file paths) |
| **Complexity** | Complex, powerful, steep learning curve | Simpler, easier to write custom profiles |
| **Granularity** | Very fine-grained | Good, but less granular |
| **Default on** | RHEL, Fedora, CentOS | Ubuntu, Debian, SUSE |
| **Container support** | Both Docker and K8s support SELinux contexts | Both support AppArmor profiles |

### seccomp-bpf: Syscall Filtering

**[seccomp-bpf](https://docs.kernel.org/userspace-api/seccomp_filter.html)** restricts which **system calls** a process can make. Since every kernel interaction goes through syscalls, restricting them is a powerful defense — a compromised process can't call `mount()`, `ptrace()`, or `reboot()` if the seccomp profile denies them.

```json
// Docker's default seccomp profile blocks ~44 dangerous syscalls:
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    { "names": ["read", "write", "open", "close", "..."], "action": "SCMP_ACT_ALLOW" }
    // blocked by default: mount, umount2, ptrace, reboot, settimeofday,
    // swapon, swapoff, init_module, delete_module, ...
  ]
}
```

Kubernetes supports seccomp profiles per pod:

```yaml
securityContext:
  seccompProfile:
    type: RuntimeDefault    # use the container runtime's default profile
    # type: Localhost
    # localhostProfile: profiles/my-custom-profile.json
```

**Generating custom profiles:** tools like `oci-seccomp-bpf-hook` and `strace` can record which syscalls your application actually uses, allowing you to create a minimal allowlist.

### The Audit Framework

[`auditd`](https://man7.org/linux/man-pages/man8/auditctl.8.html) is the Linux kernel's audit system — it logs security-relevant events (file access, syscalls, authentication, policy changes) to an audit trail:

```bash
# watch for changes to /etc/passwd
auditctl -w /etc/passwd -p wa -k passwd_changes

# watch for execve syscalls (new process execution)
auditctl -a always,exit -F arch=b64 -S execve -k exec_commands

# watch for failed file access
auditctl -a always,exit -F arch=b64 -S open -F success=0 -k failed_opens

# watch for privilege escalation (setuid)
auditctl -a always,exit -F arch=b64 -S setuid -k priv_escalation

# search audit logs
ausearch -k passwd_changes
ausearch -k exec_commands --start recent
ausearch -m USER_LOGIN --success no   # failed logins

# generate a report
aureport --summary
aureport --auth                       # authentication report
aureport --file                       # file access report
```

Audit logs are critical for compliance (PCI-DSS, HIPAA, SOC 2) and incident response. In production, forward them to a centralized log system.

### SSH Hardening

A hardened [`/etc/ssh/sshd_config`](https://man.openbsd.org/sshd_config):

```ini
# authentication
PermitRootLogin no                    # never allow root SSH login
PasswordAuthentication no             # keys only — no passwords
PubkeyAuthentication yes
AuthenticationMethods publickey       # require key auth
MaxAuthTries 3

# access control
AllowUsers deploy monitoring          # whitelist specific users
AllowGroups ssh-users                 # or whitelist by group

# protocol
Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org

# misc
X11Forwarding no
AllowTcpForwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
```

### PAM (Pluggable Authentication Modules)

PAM is the framework that controls how users authenticate on Linux. Every authentication decision — SSH login, sudo, su, local console — goes through PAM:

```bash
# PAM config for sshd
cat /etc/pam.d/sshd
# @include common-auth
# @include common-account
# @include common-session

# fail2ban-style lockout via PAM
# /etc/pam.d/common-auth
auth required pam_faillock.so preauth deny=5 unlock_time=900
auth required pam_faillock.so authfail deny=5 unlock_time=900
# locks account for 15 minutes after 5 failed attempts
```

### systemd Sandboxing (Full Reference)

The fundamentals guide showed basic systemd unit hardening. The full toolkit (every directive is documented in [`systemd.exec(5)`](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)):

```ini
[Service]
# user/group
User=myapp
Group=myapp
DynamicUser=true                      # allocate a temporary UID (no /etc/passwd entry needed)

# filesystem
ProtectSystem=strict                  # mount / read-only
ProtectHome=true                      # hide /home, /root, /run/user
PrivateTmp=true                       # isolated /tmp
ReadWritePaths=/var/lib/myapp         # explicit write access
ReadOnlyPaths=/etc/myapp              # explicit read-only
InaccessiblePaths=/boot               # completely hidden

# capabilities
NoNewPrivileges=true                  # block SUID
CapabilityBoundingSet=                # drop ALL capabilities
AmbientCapabilities=CAP_NET_BIND_SERVICE  # add back only what's needed

# syscall filtering
SystemCallFilter=@system-service      # allow only syscalls needed by typical services
SystemCallFilter=~@mount @reboot @swap  # deny specific groups

# network
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX  # only IPv4, IPv6, Unix sockets
PrivateNetwork=false                  # true would isolate networking entirely

# namespaces
PrivateUsers=true                     # user namespace isolation
ProtectKernelTunables=true            # prevent sysctl modification
ProtectKernelModules=true             # prevent module loading
ProtectKernelLogs=true                # prevent reading kernel logs
ProtectControlGroups=true             # prevent cgroup modification
ProtectClock=true                     # prevent clock modification
LockPersonality=true                  # prevent changing execution domain
RestrictRealtime=true                 # prevent real-time scheduling
MemoryDenyWriteExecute=true           # prevent W^X violations (JIT, ROP protection)
```

`systemd-analyze security myapp` scores your unit file's sandboxing (0–10, lower is more secure). Use it as a checklist after writing any new unit.

### Kernel Hardening

Modern Linux kernels ship with hardening features enabled by default:

| Feature | What It Does | Check |
|---|---|---|
| **KASLR** | Randomize kernel address layout (defeats ROP) | `cat /proc/cmdline \| grep nokaslr` (absent = enabled) |
| **SMEP/SMAP** | Prevent kernel from executing/reading userspace memory | `grep -E 'smep\|smap' /proc/cpuinfo` |
| **Stack protector** | Detect stack buffer overflows | enabled at compile time |
| **Control flow integrity** | Prevent ROP/JOP attacks | kernel 6.x+ with `CONFIG_CFI_CLANG` |
| **Lockdown mode** | Prevent even root from modifying kernel at runtime | `cat /sys/kernel/security/lockdown` |

If you remember one thing from Part 7: **defense in depth — Unix permissions (DAC) + MAC (SELinux or AppArmor) + seccomp (syscall filtering) + capabilities (fine-grained root) + audit (logging) + systemd sandboxing (namespace/filesystem isolation). Each layer catches what the others miss, and `systemd-analyze security` tells you how well your service unit is hardened.**

---

## Part 8 — Advanced Filesystems & Storage

Beyond inodes and mount points — the storage stack that sits under your data.

### Filesystem Comparison

| Feature | [ext4](https://docs.kernel.org/admin-guide/ext4.html) | [XFS](https://docs.kernel.org/filesystems/xfs/index.html) | [Btrfs](https://btrfs.readthedocs.io/en/latest/) |
|---|---|---|---|
| **Default on** | Ubuntu, Debian | RHEL 7+, Fedora | SUSE, Fedora (optional) |
| **Max file size** | 16 TB | 8 EB | 16 EB |
| **Max volume size** | 1 EB | 8 EB | 16 EB |
| **Copy-on-write** | No | No | **Yes** |
| **Snapshots** | No | No | **Yes** (native, cheap) |
| **Checksums** | Metadata only | Metadata only | **Data + metadata** |
| **RAID** | No (use mdadm) | No (use mdadm) | **Yes** (native RAID 0/1/5/6/10) |
| **Compression** | No | No | **Yes** (zstd, zlib, lzo) |
| **Defrag** | Online | Online | Online |
| **Shrink** | Yes | **No** (grow only) | Yes |
| **Best for** | General purpose, reliability | Large files, high throughput, databases | Snapshots, data integrity, flexible storage |

**ext4** is the safe default — battle-tested, well-understood, excellent tools. Choose ext4 unless you have a specific reason not to.

**XFS** excels at large files and high-throughput parallel I/O. It's the default on RHEL and the choice for many database and analytics workloads. XFS can only be grown, never shrunk.

**Btrfs** is the most feature-rich — copy-on-write, snapshots, checksums, built-in RAID, compression. It's stable for RAID 0/1/10 and single-disk, but RAID 5/6 is still considered fragile. The snapshot capability alone makes it compelling for systems that need rollback.

### Filesystem Tuning

```bash
# ext4 tuning
tune2fs -l /dev/sda1                  # show filesystem parameters
tune2fs -m 1 /dev/sda1                # reduce reserved blocks from 5% to 1% (data partitions)
tune2fs -o journal_data_writeback /dev/sda1  # faster but less safe journaling mode

# XFS tuning
xfs_info /dev/sda1                    # show filesystem parameters
# XFS is largely self-tuning — the main lever is the log (journal) device
mkfs.xfs -l logdev=/dev/nvme0n1p1 /dev/sda1  # put journal on fast NVMe

# Btrfs
btrfs filesystem show /               # show filesystem layout
btrfs filesystem df /                  # show space usage by type
btrfs subvolume snapshot / /snapshots/$(date +%Y%m%d)  # create a snapshot
btrfs property set /mnt/data compression zstd  # enable compression
```

### LVM (Logical Volume Manager)

[LVM](https://man7.org/linux/man-pages/man8/lvm.8.html) adds a layer of abstraction between physical storage and filesystems, enabling resize, snapshots, and spanning multiple disks:

```
Physical Volumes (PV)    Volume Group (VG)       Logical Volumes (LV)
┌──────────┐             ┌──────────────┐        ┌──────────────┐
│ /dev/sda1│─────┐       │              │        │ lv_root      │ → /
└──────────┘     ├──────▶│   vg_data    │───────▶│ lv_home      │ → /home
┌──────────┐     │       │              │        │ lv_var       │ → /var
│ /dev/sdb1│─────┘       └──────────────┘        └──────────────┘
└──────────┘
```

```bash
# create a physical volume, volume group, and logical volume
pvcreate /dev/sdb1
vgcreate vg_data /dev/sdb1
lvcreate -L 50G -n lv_app vg_data
mkfs.ext4 /dev/vg_data/lv_app
mount /dev/vg_data/lv_app /opt/app

# grow a logical volume (online, no downtime for ext4 and XFS)
lvextend -L +20G /dev/vg_data/lv_app
resize2fs /dev/vg_data/lv_app        # ext4
# xfs_growfs /opt/app                # XFS

# shrink a logical volume (ext4 only, offline)
umount /opt/app
e2fsck -f /dev/vg_data/lv_app        # must check first
resize2fs /dev/vg_data/lv_app 30G    # shrink filesystem
lvreduce -L 30G /dev/vg_data/lv_app  # shrink LV

# thin provisioning (overcommit storage)
lvcreate -L 100G --thinpool thin_pool vg_data
lvcreate -V 50G --thin -n lv_thin1 vg_data/thin_pool
# the thin pool uses space only as data is written (like memory overcommit)

# LVM snapshots
lvcreate -L 5G -s -n snap_app /dev/vg_data/lv_app  # snapshot (CoW)
mount /dev/vg_data/snap_app /mnt/snapshot            # mount read-only for backup
```

### LUKS Encryption

[LUKS](https://gitlab.com/cryptsetup/cryptsetup/-/blob/main/README.md) (Linux Unified Key Setup) provides full-disk encryption via [`cryptsetup(8)`](https://man7.org/linux/man-pages/man8/cryptsetup.8.html):

```bash
# encrypt a partition
cryptsetup luksFormat /dev/sdb1
cryptsetup open /dev/sdb1 encrypted_data
mkfs.ext4 /dev/mapper/encrypted_data
mount /dev/mapper/encrypted_data /mnt/secure

# close
umount /mnt/secure
cryptsetup close encrypted_data

# manage keys
cryptsetup luksDump /dev/sdb1         # show key slots
cryptsetup luksAddKey /dev/sdb1       # add a key
cryptsetup luksRemoveKey /dev/sdb1    # remove a key

# auto-unlock at boot (/etc/crypttab)
# encrypted_data  /dev/sdb1  /etc/keys/disk.key  luks
```

LUKS encryption is transparent to the filesystem and applications. Performance overhead on modern CPUs with AES-NI is minimal (1-5%).

### RAID with mdadm

Software RAID via [`mdadm(8)`](https://man7.org/linux/man-pages/man8/mdadm.8.html):

```bash
# create a RAID 1 (mirror)
mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sdb1 /dev/sdc1
mkfs.ext4 /dev/md0

# create a RAID 5 (striping with parity — N-1 capacity)
mdadm --create /dev/md1 --level=5 --raid-devices=3 /dev/sdd1 /dev/sde1 /dev/sdf1

# check RAID status
cat /proc/mdstat
mdadm --detail /dev/md0

# replace a failed disk
mdadm /dev/md0 --remove /dev/sdc1
mdadm /dev/md0 --add /dev/sdd1
# rebuild starts automatically
```

### POSIX ACLs

When basic user/group/other permissions aren't enough, ACLs let you set per-user or per-group permissions on individual files:

```bash
# grant user bob read access to a file
setfacl -m u:bob:r /var/log/app.log

# grant group devs read+write to a directory (and all future files)
setfacl -m g:devs:rw /opt/app
setfacl -d -m g:devs:rw /opt/app      # -d = default ACL for new files

# view ACLs
getfacl /opt/app

# remove ACLs
setfacl -b /opt/app                    # remove all ACLs
```

### OverlayFS (How Docker Images Work)

The fundamentals guide mentioned overlay filesystems. Here's the mechanics ([kernel overlayfs docs](https://docs.kernel.org/filesystems/overlayfs.html)):

```bash
# manual overlayfs mount
mount -t overlay overlay \
  -o lowerdir=/layer1:/layer2:/layer3,upperdir=/writable,workdir=/work \
  /merged
```

`lowerdir` is a stack of read-only layers (the Docker image layers). `upperdir` is the writable layer (the container's changes). `workdir` is a scratch directory for atomic operations. The merged view shows all layers composited, with `upperdir` taking precedence.

When a file in a lower layer is modified, it's **copied up** to the upper layer first (copy-on-write). Deletes create **whiteout files** in the upper layer that hide the lower-layer file. This is the exact mechanism behind Docker's layer model.

### Mount Propagation

[Mount propagation](https://docs.kernel.org/filesystems/sharedsubtree.html) controls how mounts in one namespace are visible in others:

| Mode | Behavior |
|---|---|
| **shared** | mounts propagate bidirectionally between namespace and parent |
| **slave** | mounts propagate from parent to namespace, not the reverse |
| **private** | no propagation (default for most mounts) |
| **unbindable** | like private, plus cannot be bind-mounted |

This matters for containers: Docker uses `rprivate` by default (no propagation), but some volume plugins need `rshared` to propagate host mounts into containers.

```bash
mount --make-shared /mnt/shared        # enable bidirectional propagation
mount --make-slave /mnt/shared         # one-way propagation
mount --make-private /mnt/private      # no propagation
```

### Bind Mounts

A bind mount makes a directory accessible from a second location — the same data, visible at two paths:

```bash
mount --bind /var/lib/app/data /mnt/app-data
# /mnt/app-data now shows the same files as /var/lib/app/data

# read-only bind mount
mount --bind /var/lib/app/data /mnt/app-data
mount -o remount,ro,bind /mnt/app-data
```

Docker volumes and Kubernetes `hostPath` volumes are bind mounts under the hood. Understanding this explains why permission issues with Docker volumes are actually permission issues with the underlying host directory.

If you remember one thing from Part 8: **ext4 is the safe default, XFS for high-throughput, Btrfs for snapshots and data integrity; LVM lets you resize and manage storage flexibly; LUKS encryption is transparent with minimal overhead on modern CPUs; and Docker's overlay filesystem is just overlayfs — read-only lower layers plus a writable upper layer with copy-on-write.**

---

## Part 9 — Kernel Tuning

The kernel exposes thousands of tunable parameters through `/proc/sys/` and `sysctl` (all documented in the [kernel sysctl reference](https://docs.kernel.org/admin-guide/sysctl/index.html)). Most should be left at defaults. This section covers the ones that actually matter for production servers.

### sysctl: The Tuning Interface

```bash
# read a parameter
sysctl net.ipv4.tcp_congestion_control

# set a parameter (runtime, non-persistent)
sysctl -w net.ipv4.tcp_congestion_control=bbr

# set permanently
echo "net.ipv4.tcp_congestion_control = bbr" >> /etc/sysctl.d/99-custom.conf
sysctl --system   # reload

# dump all parameters
sysctl -a | wc -l   # typically 1000+
```

### Network Parameters That Matter

```ini
# /etc/sysctl.d/99-network.conf

# connection backlog — max pending connections before the kernel drops them
net.core.somaxconn = 65535                   # default 4096 (was 128!). raise for busy servers
net.ipv4.tcp_max_syn_backlog = 65535         # SYN queue depth

# TCP keepalive — detect dead connections
net.ipv4.tcp_keepalive_time = 600            # seconds before first probe (default 7200!)
net.ipv4.tcp_keepalive_intvl = 60            # interval between probes
net.ipv4.tcp_keepalive_probes = 5            # probes before declaring dead

# TIME_WAIT — reuse sockets faster
net.ipv4.tcp_tw_reuse = 1                    # reuse TIME_WAIT sockets for new outgoing connections

# buffer sizes (covered in Part 4)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 131072 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# congestion control
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq

# port range for ephemeral ports
net.ipv4.ip_local_port_range = 1024 65535    # default 32768-60999

# reverse path filtering (anti-spoofing)
net.ipv4.conf.all.rp_filter = 1

# ignore ICMP redirects (security)
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0

# SYN flood protection
net.ipv4.tcp_syncookies = 1                  # enabled by default, keep it on

# conntrack (Part 4)
net.netfilter.nf_conntrack_max = 524288
```

### Memory Parameters That Matter

```ini
# /etc/sysctl.d/99-memory.conf

# swappiness (covered in Part 2)
vm.swappiness = 10                           # prefer cache reclaim over swap for servers

# dirty page writeback thresholds
vm.dirty_ratio = 40                          # % of total memory before synchronous writeback
vm.dirty_background_ratio = 10               # % before background writeback starts
# lower dirty_ratio = more frequent writes, less data at risk
# higher dirty_ratio = better throughput, more data at risk on crash

# overcommit
vm.overcommit_memory = 0                     # default: heuristic overcommit
# 0: kernel estimates if there's enough memory (the default, usually fine)
# 1: always allow (never fail malloc — dangerous but used by Redis)
# 2: never overcommit (strict — commit must not exceed swap + ratio*RAM)
vm.overcommit_ratio = 50                     # used when overcommit_memory=2

# max memory map areas (needed by some apps like Elasticsearch)
vm.max_map_count = 262144                    # default 65530

# panic on OOM (for clusters where restart is preferred over degraded state)
vm.panic_on_oom = 0                          # 0 = kill process (default), 1 = panic/reboot
```

### File and Process Parameters

```ini
# /etc/sysctl.d/99-system.conf

# max open files system-wide
fs.file-max = 2097152                        # default varies. raise for busy servers

# max inotify watches (IDEs, file watchers)
fs.inotify.max_user_watches = 524288         # default 8192. VS Code, webpack need more
fs.inotify.max_user_instances = 512

# max PID value
kernel.pid_max = 4194304                     # default 32768. raise for container hosts

# max queued signals
kernel.pid_max = 4194304

# core dumps
kernel.core_pattern = /var/crash/core.%e.%p.%t
```

### Kernel Command Line Parameters

Set at boot time in GRUB (`/etc/default/grub` → `GRUB_CMDLINE_LINUX`; the full list is in the [kernel parameters reference](https://docs.kernel.org/admin-guide/kernel-parameters.html)):

```ini
# CPU isolation (Part 1)
isolcpus=4-7                                 # reserve cores for latency-sensitive work
nohz_full=4-7                                # disable timer ticks on isolated cores
rcu_nocbs=4-7                                # offload RCU callbacks from isolated cores

# NUMA
numa_balancing=0                             # disable automatic NUMA balancing (if you pin manually)

# Huge pages (Part 2)
default_hugepagesz=2M hugepagesz=2M hugepages=1024

# Transparent huge pages
transparent_hugepage=madvise                 # only use THP when app requests it

# Security
random.trust_cpu=on                          # trust CPU RNG for early entropy
lockdown=integrity                           # prevent unsigned kernel modules

# io_uring (Part 3)
# io_uring_disabled=1                        # disable for unprivileged users (security)

# mitigations (security vs. performance trade-off)
# mitigations=off                            # disable ALL CPU vulnerability mitigations (danger!)
# mitigations=auto,nosmt                     # default + disable SMT (strongest protection)
```

After editing, run `update-grub` (Debian/Ubuntu) or `grub2-mkconfig -o /boot/grub2/grub.cfg` (RHEL/Fedora) and reboot.

### DKMS (Dynamic Kernel Module Support)

DKMS automatically recompiles out-of-tree kernel modules when the kernel is updated — preventing the "I upgraded the kernel and my driver broke" problem:

```bash
# check DKMS status
dkms status
# nvidia/535.129.03, 6.5.0-35-generic, x86_64: installed

# modules are in /usr/src/<module>-<version>/
# DKMS automatically rebuilds them on kernel upgrade
```

If you remember one thing from Part 9: **most sysctl defaults are fine — the ones worth changing are `somaxconn` (raise for busy servers), `tcp_tw_reuse` (faster socket recycling), `swappiness` (lower for databases), `tcp_congestion_control=bbr` (better internet throughput), `fs.inotify.max_user_watches` (raise for IDEs and file watchers), and `nf_conntrack_max` (raise for busy load balancers/K8s nodes).**

---

## Part 10 — The Boot Process

What happens between pressing the power button and getting a login prompt. Understanding this explains why your server takes 2 minutes to boot, why initramfs exists, and how systemd orchestrates the startup.

### The Full Sequence

```
Power On
    │
    ▼
┌───────────────┐
│ Firmware       │  UEFI (modern) or BIOS (legacy)
│                │  POST, hardware init, find boot device
└───────────────┘
    │
    ▼
┌───────────────┐
│ Boot Loader    │  GRUB2 (most distros)
│                │  Read config, select kernel, load kernel + initramfs
└───────────────┘
    │
    ▼
┌───────────────┐
│ Kernel Init    │  Decompress, hardware probing, mount initramfs as /
│                │  Run /init from initramfs
└───────────────┘
    │
    ▼
┌───────────────┐
│ initramfs      │  Load storage drivers, assemble RAID/LVM, decrypt LUKS
│                │  Mount the real root filesystem
│                │  pivot_root to real root, exec systemd
└───────────────┘
    │
    ▼
┌───────────────┐
│ systemd (PID 1)│  Read unit files, build dependency tree
│                │  Start services in parallel
│                │  Reach default target (multi-user.target or graphical.target)
└───────────────┘
    │
    ▼
 Login prompt / GUI
```

### UEFI vs. BIOS

| Feature | BIOS | UEFI |
|---|---|---|
| **Age** | 1975 | 2005+ |
| **Boot mode** | MBR (Master Boot Record) | GPT (GUID Partition Table) |
| **Max disk size** | 2 TB | 9.4 ZB |
| **Max partitions** | 4 primary | 128 |
| **Secure Boot** | No | Yes — verifies signed bootloader/kernel |
| **Boot speed** | Slower (sequential hardware init) | Faster (parallel init, drivers in firmware) |

All modern servers use UEFI. The **EFI System Partition (ESP)** is a FAT32 partition (typically `/boot/efi`) containing the bootloader. UEFI firmware reads the bootloader directly from the ESP — no MBR needed.

**Secure Boot** verifies that the bootloader and kernel are signed with a trusted key. This prevents rootkits from modifying the boot chain. Most distros ship signed kernels that work with Secure Boot out of the box.

```bash
# check if you're booted in UEFI or BIOS mode
ls /sys/firmware/efi                   # exists = UEFI, doesn't exist = BIOS

# check Secure Boot status
mokutil --sb-state
# SecureBoot enabled / disabled

# list boot entries
efibootmgr -v
```

### GRUB2

[GRUB2](https://www.gnu.org/software/grub/manual/grub/grub.html) is the boot loader on most Linux distros. It presents a menu (if configured), loads the selected kernel and initramfs into memory, and transfers control to the kernel.

```bash
# GRUB config
cat /etc/default/grub
# GRUB_DEFAULT=0
# GRUB_TIMEOUT=5
# GRUB_CMDLINE_LINUX="quiet splash"
# GRUB_CMDLINE_LINUX_DEFAULT=""

# regenerate GRUB config after changes
update-grub                          # Debian/Ubuntu
grub2-mkconfig -o /boot/grub2/grub.cfg  # RHEL/Fedora

# kernel command line parameters go in GRUB_CMDLINE_LINUX
# these are passed to the kernel at boot

# list installed kernels
ls /boot/vmlinuz-*

# boot into a specific kernel (one-time, for testing)
# use GRUB menu at boot, or:
grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 6.5.0-35-generic"
reboot
```

### initramfs: The Bridge to the Real Root

**initramfs** (initial RAM filesystem) is a small filesystem loaded into memory by the bootloader alongside the kernel. It contains the minimum tools and drivers needed to mount the real root filesystem.

Why it exists: the kernel needs storage drivers to read the root filesystem, but those drivers might be in the root filesystem (chicken-and-egg). initramfs solves this by providing the drivers in a pre-loaded memory filesystem.

What initramfs does:
1. The kernel mounts initramfs as the initial `/`
2. Runs `/init` (a script or binary in initramfs)
3. Loads storage drivers (RAID, LVM, NVMe, SCSI)
4. Assembles RAID arrays, activates LVM volumes
5. Decrypts LUKS-encrypted volumes (prompts for passphrase or reads from keyfile)
6. Mounts the real root filesystem
7. `pivot_root` to the real root
8. `exec`s the real init system (systemd)

```bash
# list contents of initramfs
lsinitramfs /boot/initrd.img-$(uname -r)       # Debian/Ubuntu
lsinitrd /boot/initramfs-$(uname -r).img       # RHEL/Fedora

# regenerate initramfs (after adding drivers or changing config)
update-initramfs -u                             # Debian/Ubuntu
dracut --force                                  # RHEL/Fedora

# include a custom module in initramfs
echo "my_driver" >> /etc/initramfs-tools/modules
update-initramfs -u
```

### systemd Boot Orchestration

Once systemd takes over as PID 1, it:

1. **Reads unit files** from `/etc/systemd/system/`, `/usr/lib/systemd/system/`, etc.
2. **Builds a dependency tree** from `After=`, `Requires=`, `Wants=` directives.
3. **Starts units in parallel** wherever dependencies allow. This is why systemd boots faster than SysV init (which started services sequentially).
4. **Reaches the default target** (`multi-user.target` for servers, `graphical.target` for desktops).

```bash
# see what's taking the most time during boot
systemd-analyze                      # total boot time
# Startup finished in 3.5s (firmware) + 1.2s (loader) + 2.1s (kernel) + 8.3s (userspace) = 15.1s

systemd-analyze blame                # time per unit, sorted
# 4.5s  NetworkManager-wait-online.service
# 2.1s  dev-sda1.device
# 1.8s  snapd.service
# ...

systemd-analyze critical-chain       # critical path (the longest dependency chain)
# multi-user.target @8.3s
# └─ postgresql.service @5.1s +2.2s
#    └─ network-online.target @5.0s
#       └─ NetworkManager-wait-online.service @1.2s +3.8s

# visualize the boot process
systemd-analyze plot > boot.svg      # SVG timeline of the boot
```

`systemd-analyze blame` is the first tool to reach for when boot is slow — it shows exactly which units took the longest. Common culprits: network wait services, filesystem checks, slow hardware detection.

### systemd Targets (Runlevels)

systemd uses **targets** instead of SysV runlevels:

| Target | SysV Equivalent | Description |
|---|---|---|
| `poweroff.target` | 0 | System halt |
| `rescue.target` | 1 | Single-user mode (recovery) |
| `multi-user.target` | 3 | Multi-user, no GUI (servers) |
| `graphical.target` | 5 | Multi-user with GUI (desktops) |
| `reboot.target` | 6 | Reboot |

```bash
# check current default target
systemctl get-default
# multi-user.target

# change default (permanent)
systemctl set-default multi-user.target

# switch target now (temporary)
systemctl isolate rescue.target        # enter rescue mode
```

### Rescue and Recovery

When a system won't boot:

```bash
# 1. Hold Shift during boot to get the GRUB menu
# 2. Select "Advanced options" → "recovery mode"
# 3. Or edit the kernel command line in GRUB:
#    - add "single" or "init=/bin/bash" to boot into a minimal shell

# once in rescue/recovery:
mount -o remount,rw /                  # remount root read-write
journalctl -b -1                       # view logs from the previous (failed) boot
systemctl list-units --failed           # show failed units
```

If you remember one thing from Part 10: **the boot sequence is firmware (UEFI) → bootloader (GRUB) → kernel → initramfs (load drivers, mount root) → systemd (PID 1, parallel service startup), and `systemd-analyze blame` shows you which services are making boot slow. When things go wrong, `journalctl -b -1` shows you the previous boot's logs.**

---

## Where to Go Next

- **Read Brendan Gregg's [*Systems Performance* (2nd ed.)](https://www.brendangregg.com/systems-performance-2nd-edition-book.html)** — the definitive book on Parts 1–6, with the USE method, every observability tool, and the methodology this guide compresses. His [*BPF Performance Tools*](https://www.brendangregg.com/bpf-performance-tools-book.html) is the follow-up once eBPF clicks.
- **Read Michael Kerrisk's [*The Linux Programming Interface*](https://man7.org/tlpi/)** for the syscall-level foundations — it's the book the man pages assume you've read, and Kerrisk maintains [man7.org](https://man7.org/linux/man-pages/) itself.
- **Work the primary docs while they're fresh:** the [kernel documentation](https://docs.kernel.org/) (especially the [scheduler](https://docs.kernel.org/scheduler/index.html), [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), and [sysctl](https://docs.kernel.org/admin-guide/sysctl/index.html) sections), [ebpf.io](https://ebpf.io/) and the [bpftrace one-liner tutorial](https://github.com/bpftrace/bpftrace/blob/master/docs/tutorial_one_liners.md).
- **Break a system on purpose.** Spin up a VM, cap a cgroup's CPU and watch `nr_throttled` climb, fill memory until the OOM killer fires (watch with `oomkill`), saturate a disk and read the `biolatency` histogram, partition the network with `tc netem`. The tools only become instinct when you've watched them catch a problem you caused.
- **Adjacent guides in this repo:** [Linux Fundamentals](LINUX_FUNDAMENTALS_STUDY_GUIDE.md) (the substrate this builds on), [eBPF](EBPF_STUDY_GUIDE.md) (Part 5 at full depth), [Linux Networking](LINUX_NETWORKING_STUDY_GUIDE.md) (Part 4 at full depth), and the [Observability](OBSERVABILITY_STUDY_GUIDE.md) and [Kubernetes](k8s/KUBERNETES_STUDY_GUIDE.md) guides for the production layer above.

That's the guide. From here, the highest-leverage next steps are to connect these internals to your actual systems: run `perf stat` on a production service to check IPC, run `biolatency` to see your real disk latency distribution, check `cpu.stat` in your container's cgroup for throttling, and run `systemd-analyze security` on your service units to see how well they're sandboxed. Once you've seen CFS throttling flatten your p99, or watched the OOM killer fire via `oomkill` from BCC — the kernel stops being abstract and starts being the explanation for the behavior you see every day.

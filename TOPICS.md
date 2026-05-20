# Future Study Guide Topics

A curated list of topics that would each justify their own study guide in this repo. Organized by area, with a one-line rationale for each. The bar is "deep enough that a thoughtful 400–800 line depth-first guide would teach something a working engineer would actually use."

Topics already covered live in [README.md](README.md) and are not repeated here.

---

## Systems & Infrastructure

- **Linux Fundamentals** — process model, file descriptors, signals, systemd, cgroups, namespaces. The substrate every other infra topic sits on; deserves a proper grounding rather than being inherited from osmosis.
- **AWS** — counterpart to the existing Azure-for-AWS-architect guide, written for someone coming in fresh. Covers IAM, VPC, compute, storage, managed databases, and the cross-service patterns that actually matter.
- **GCP** — third leg of the cloud stool; worth a guide that focuses on what's idiomatic in GCP (project model, IAM hierarchy, BigQuery, Cloud Run, GKE Autopilot) rather than a mechanical translation from AWS.
- **Docker (Deep)** — image layers, BuildKit, multi-stage builds, OCI runtimes, security contexts, rootless. The existing networking guide covers networking; this would cover the rest.
- **Networking Fundamentals** — TCP/IP, DNS, TLS 1.3, HTTP/1.1 vs. 2 vs. 3, load balancing, NAT. Foundational reference that other guides (K8s networking, Nginx, security) can lean on.
- **Nginx & Reverse Proxies** — config language, upstream blocks, caching, TLS termination, rate limiting, the `ngx_http_*` module landscape. Still the most common load balancer on the planet.
- **Observability** — Prometheus, OpenTelemetry, Grafana, traces vs. metrics vs. logs, RED/USE methods, alert design. Goes beyond "install Prometheus" into how to *think* about production signal.
- **GitHub Actions** — workflow syntax, runners, matrix builds, secrets, OIDC to cloud, reusable workflows, caching. The default CI for most modern repos; deserves a proper treatment.
- **Ansible** — inventories, modules, playbooks, roles, the agentless model. Still the right tool for many configuration jobs even in a Terraform world.
- **Pulumi & Crossplane** — IaC beyond Terraform: real programming languages (Pulumi) and Kubernetes-native infra (Crossplane). Both fill gaps Terraform doesn't.

---

## Languages

- **TypeScript (Deep)** — the type system as its own subject: conditional types, mapped types, inference, branding, narrowing. The other JS-framework guides assume TS; this would be the foundation.
- **Modern JavaScript & Web Platform** — modules, iterators, async/await internals, structured clone, the platform APIs (Fetch, Streams, IndexedDB, Service Workers). The non-framework half of frontend.
- **React (Fundamentals)** — components, hooks, reconciliation, Suspense, server components, the mental model. Distinct from Next.js — many React jobs don't use Next.
- **Python (Advanced)** — typing, packaging, async deep dive, the CPython object model, descriptors, metaclasses. Companion to the existing concurrency guide.
- **Bash & Shell Scripting** — proper scripting (`set -euo pipefail`, traps, process substitution, arrays), POSIX vs. Bash, when to reach for awk/sed. Most engineers write shell badly; a guide would pay back fast.
- **SQL (Beyond Postgres)** — window functions, CTEs, query planning concepts that apply across engines. Complement the Postgres-specific guides with portable SQL fluency.
- **C & Systems Programming** — pointers, memory layout, the build/link model, calling conventions, undefined behavior. Pairs naturally with the Rust guide as the "thing Rust is reacting against."
- **Zig** — comptime, error unions, allocators, the "no hidden control flow" philosophy. A genuinely interesting newer systems language.
- **Elixir & OTP** — the actor model, supervision trees, GenServers, hot code reload. The right introduction to fault-tolerant distributed thinking.
- **Lua** — small, embeddable, surprisingly powerful. Useful for Neovim config, game scripting, Redis, Nginx.

---

## Data & ML

- **Kafka & Streaming** — topics, partitions, consumer groups, exactly-once semantics, the broker/producer/consumer model. The dominant streaming substrate.
- **Redis** — data structures beyond key-value, pub/sub, streams, persistence trade-offs, Cluster mode. Used as cache, queue, lock, session store, and more.
- **Data Engineering** — Airflow/Dagster/Prefect, dbt, Spark, the modern data stack. A coherent guide to what data engineers actually build.
- **LLM Application Development** — prompt engineering, tool use, agents, retrieval, evals, cost/latency trade-offs. The current state of the art for shipping LLM-backed features.
- **Local LLMs** — llama.cpp, Ollama, GGUF, quantization, hardware considerations. Particularly relevant for Pi-class hardware experiments.
- **Vector Databases** — embeddings, ANN indexes (HNSW, IVF), pgvector vs. dedicated stores. Foundation for any retrieval-augmented system.

---

## Security

- **Web Application Security** — OWASP Top 10 with depth: how each class of bug actually works, how to test for it, how to prevent it. Complement to the Kali guide on the offensive side.
- **Cryptography Fundamentals** — symmetric, asymmetric, hashing, signatures, key exchange, TLS, JWT pitfalls. Enough to read a spec and not misuse a library.
- **Threat Modeling** — STRIDE, attack trees, trust boundaries. The discipline of thinking about security *before* the code is written.
- **Reverse Engineering** — Ghidra/IDA, ELF/PE/Mach-O, dynamic analysis, anti-debugging. Pairs with the Kali guide for the binary-analysis half of pentesting.
- **Binary Exploitation** — stack/heap exploitation, ROP, modern mitigations (ASLR, CFI, stack canaries). The CTF-leaning end of security.

---

## Architecture

- **Distributed Systems** — consensus (Raft, Paxos), CAP, consistency models, vector clocks, the canon (Lamport, Brewer, Vogels). The conceptual backbone behind every modern infra topic.
- **API Design** — REST, GraphQL, gRPC, OpenAPI, versioning, pagination, error models. Specific, opinionated, with worked examples — not "REST 101."
- **Event-Driven Architecture** — event sourcing, CQRS, sagas, idempotency, the operational realities. Pairs with the Kafka guide.
- **Domain-Driven Design** — strategic design (bounded contexts, context maps) and tactical patterns (aggregates, entities, value objects). The bridge from "code that works" to "code that scales as a team's understanding."

---

## Frontend

- **Modern CSS** — Grid, Flexbox, container queries, custom properties, cascade layers, modern selectors. CSS has changed enough recently that a current guide would be genuinely useful.
- **Web Components** — custom elements, shadow DOM, slots, the framework-agnostic component model. Increasingly viable for design systems.
- **Tailwind** — utility-first philosophy, the design-system angle, when it's the right call and when it isn't.
- **Astro** — islands architecture, partial hydration, content-collection model. The pragmatic answer for content-heavy sites.
- **Tauri** — Rust + webview desktop apps. Pairs naturally with the Rust guide and the Pi Zero 2 W interest for cross-platform GUI work.

---

## OS, Hardware, Embedded

- **Embedded Linux on Raspberry Pi** — Pi Zero 2 W specifically: boot process, GPIO, I2C/SPI/UART, device tree overlays, low-power modes. Directly applicable to hardware in hand.
- **MicroPython / CircuitPython** — Python on microcontrollers. Lowest-friction path from Python to hardware.
- **ARM Assembly (AArch64)** — basics of the instruction set, calling conventions, looking at compiler output. The kind of literacy that pays off across systems languages.

---

## Tools

- **Git (Deep)** — the object model, refs, plumbing vs. porcelain, rebase/cherry-pick/reflog as everyday tools, recovery from disasters. Most engineers use 10% of Git; the other 90% is the difference between fluent and not.
- **Neovim** — modal editing, motions, text objects, LSP, Treesitter, plugin ecosystem. Configurable enough to be its own subject.
- **tmux** — sessions, windows, panes, scripting, integration with editors. The right complement to Neovim for terminal-driven work.
- **Make & Build Systems** — Make, then a tour of the alternatives (Ninja, Bazel, just). The mental model of "declare dependencies, derive a graph" applies everywhere.

---

## How to Pick the Next One

Loose criteria, in order of weight:
1. **Solves a current problem you have.** Always wins.
2. **Adjacent to something already in this repo.** Existing context speeds the writing and the reading.
3. **High signal in the job market or in real engineering work.** Avoid topics that are mostly buzz.
4. **Underserved by existing online resources.** Don't write what's already well-written elsewhere.

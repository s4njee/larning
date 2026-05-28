# Future Study Guide Topics

A **prioritized** shortlist of topics that would each justify their own study guide in this repo. The bar is "a depth-first guide that teaches a working engineer something they'd actually use." Topics already covered live in [README.md](README.md) and aren't repeated here.

Ranking weights, in order: (1) **solves a current problem**, (2) **adjacent to an existing guide** — shared context speeds the writing and the reading, (3) **high signal** in real engineering work or the job market, (4) **underserved** by existing resources. Tier 1 is what I'd write next; Tier 3 is a keep-warm backlog.

---

## Tier 1 — Write these next

1. **Linux Fundamentals** *(Systems)* — process model, file descriptors, signals, systemd, cgroups, namespaces. The substrate under Docker, Kubernetes, Kali, and the Pi; cgroups and namespaces are literally how containers work, so it retroactively deepens half the repo. The most load-bearing gap in the collection.
2. **Testing** *(Cross-cutting)* — the testing pyramid, test doubles, fixtures, property-based testing, integration vs. e2e, flaky-test triage. It touches every language guide in the repo and is currently absent entirely — high leverage precisely because it's cross-cutting.
3. **AWS** *(Systems)* — a from-scratch counterpart to the existing Azure-for-AWS-architect guide, which assumes an AWS fluency no guide here actually provides. IAM, VPC, compute, storage, managed databases, and the cross-service patterns that matter. Closes an obvious loop and carries top market signal.
4. **System Design & Distributed Systems** *(Architecture)* — consensus (Raft, Paxos), CAP, consistency models, then assembling them into real systems (caching, sharding, queues, idempotency). The conceptual glue behind every infra guide, and the highest-signal interview and real-work topic.
5. **SQL (Beyond Postgres)** *(Languages/Data)* — window functions, CTEs, and query-planning concepts that port across engines. Directly deepens the Postgres guides and your day-to-day work; the adjacency and personal-stack fit make it cheap to write and high-return.

---

## Tier 2 — High value

6. **Kafka & Streaming** *(Data)* — topics, partitions, consumer groups, exactly-once semantics, the broker/producer/consumer model. The dominant streaming substrate; the Data Engineering guide references it but it deserves its own.
7. **API Design** *(Architecture)* — REST, GraphQL, gRPC, OpenAPI, versioning, pagination, error models — opinionated and worked, not "REST 101." Applies to nearly everything you build.
8. **Web Application Security** *(Security)* — the OWASP Top 10 with depth: how each bug class actually works, how to test for it, how to prevent it. The defensive complement to the offensive Kali guide.
9. **Python (Advanced)** *(Languages)* — typing, packaging, async internals, the CPython object model, descriptors, metaclasses. Companion to the existing concurrency guide and squarely in your stack.
10. **Nginx & Reverse Proxies** *(Systems)* — config language, upstreams, caching, TLS termination, rate limiting. Still the most common proxy/load balancer on the planet; pairs with the Networking and Docker/Kubernetes guides.
11. **Embedded Linux on the Raspberry Pi Zero 2 W** *(Hardware)* — boot process, GPIO, I2C/SPI/UART, device-tree overlays, low-power modes. The most directly actionable topic given the hardware already on your desk.
12. **Modern CSS** *(Frontend)* — Grid, Flexbox, container queries, custom properties, cascade layers, modern selectors. Framework-agnostic, so it pays off across the Vue/Next/Svelte guides, and CSS has changed enough recently to warrant a current treatment.

---

## Tier 3 — Backlog (worthwhile, lower priority)

Good ideas that are more niche, more situational, or simply lower-leverage than the above right now:

- **React (Fundamentals)** *(Languages)* — hooks, reconciliation, server components; lots of React jobs, but lower personal fit given Vue.
- **Tauri** *(Frontend)* — Rust + webview desktop apps; pairs with the Rust and Qt guides and the Pi interest.
- **Event-Driven Architecture** *(Architecture)* — event sourcing, CQRS, sagas, idempotency; best written after Kafka.
- **GCP** *(Systems)* — the third cloud; a natural follow-on once AWS exists.
- **Bash & Shell Scripting** *(Languages)* — `set -euo pipefail`, traps, process substitution, arrays; pays back fast but narrow in scope.
- **C & Systems Programming** *(Languages)* — pointers, memory layout, the build/link model, undefined behavior; the "thing Rust is reacting against."
- **Modern JavaScript & Web Platform** *(Languages)* — modules, async internals, Fetch/Streams/Service Workers; the non-framework half of frontend.
- **Domain-Driven Design** *(Architecture)* — bounded contexts, aggregates, value objects; scales a team's shared understanding.
- **Vector Databases** *(Data)* — embeddings, ANN indexes (HNSW, IVF), pgvector vs. dedicated stores; overlaps the LLM App Dev guide.
- **Local LLMs** *(Data)* — llama.cpp, Ollama, GGUF, quantization; relevant to Pi-class hardware experiments.
- **Threat Modeling** *(Security)* — STRIDE, attack trees, trust boundaries; design-time security.
- **Reverse Engineering** / **Binary Exploitation** *(Security)* — Ghidra/IDA, ELF/PE/Mach-O, ROP, modern mitigations; the binary-analysis and CTF end, fairly niche.
- **Pulumi & Crossplane** *(Systems)* — IaC beyond Terraform: real languages, and Kubernetes-native infra.
- **Web Components**, **Tailwind**, **Astro** *(Frontend)* — design-system and content-site niches.
- **Zig**, **Elixir & OTP**, **Lua** *(Languages)* — interesting but specialized language picks.
- **MicroPython / CircuitPython**, **ARM Assembly (AArch64)** *(Hardware)* — microcontroller and low-level literacy.
- **Neovim**, **tmux**, **Make & Build Systems** *(Tools)* — editor, terminal, and build-system tooling.

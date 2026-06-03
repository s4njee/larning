# Future Study Guide Topics

A **prioritized** shortlist of topics that would each justify their own study guide in this repo. The bar is unchanged: "a depth-first guide that teaches a working engineer something they'd actually use." Topics already covered live in [README.md](README.md) and aren't repeated here.

Two things are true at once in 2026, and this list is built around the tension between them. **AI has become part of the job rather than a specialty beside it** — shipping an LLM feature, wiring up tools, and evaluating non-deterministic output are now ordinary engineering tasks. And yet **none of the old foundations got less load-bearing for it**: the AI features still run on Linux, still need tests, still get attacked, still live in someone's cloud. A guide collection that's useful in 2026 has to invest in both, so this one does.

Ranking weights, in order: (1) **solves a problem** you or the field hit right now; (2) **high signal in 2026 engineering work and the job market**; (3) **adjacent to an existing guide** — shared context speeds both the writing and the reading; (4) **underserved** by good existing material. Personal-stack fit — Rust, Vue, Postgres, Python concurrency, and the Pi Zero 2 W on the desk — breaks ties. Tier 1 is what I'd write next; Tier 3 is a keep-warm backlog.

---

## Tier 1 — Write these next

1. **AI Engineering: Agents & Tool Use** *(AI)* — The defining skill of 2026. The [LLM App Dev guide](LLM_APP_DEV_STUDY_GUIDE.md) covers calling a model; this is the layer above it: the agent loop (plan → act → observe), tool/function calling, structured outputs, memory and context management, multi-agent orchestration, guardrails and retries, cost/latency control, and the frameworks — plus when to skip them and write the loop yourself. The highest market signal in the field right now and badly underserved by treatments that go past the demo into what survives production.
2. **Testing** *(Cross-cutting)* — The testing pyramid, test doubles, fixtures, property-based testing, integration vs. e2e, flaky-test triage — and the 2026 wrinkle: how to test **non-deterministic** systems (LLM outputs, retries, eventual consistency) without writing brittle assertions. Touches every language guide in the repo and is currently absent entirely; high leverage precisely because it's cross-cutting.
3. **AWS** *(Systems)* — A from-scratch counterpart to the existing Azure-for-AWS-architect guide, which assumes an AWS fluency no guide here actually provides. IAM, VPC, compute, storage, managed databases, and the cross-service patterns that matter — including the GPU/inference and managed-AI surface that now drives a lot of cloud spend. Closes an obvious loop and carries top market signal.
4. **Web Application & LLM Security** *(Security)* — The OWASP Top 10 with depth — how each bug class works, how to test for it, how to prevent it — extended to the **new attack surface**: prompt injection, insecure tool use, data exfiltration through agents, and the OWASP Top 10 for LLM Applications. The defensive complement to the offensive Kali guide, and the security topic every team now needs whether or not they think they ship AI.

---

## Tier 2 — High value

6. **Model Context Protocol (MCP)** *(AI)* — The emerging standard for wiring LLMs to tools, data, and each other — the "USB-C of AI integrations," now broadly adopted across the major model vendors. Servers, clients, transports, the resource/tool/prompt model, and how to build, ship, and **secure** your own server. New, moving fast, and barely covered in guide form; pairs directly with the agents guide, and you could expose Postgres, the Pi, or these very guides as MCP servers to learn it.
7. **RAG & Vector Databases** *(AI / Data)* — Retrieval-augmented generation done properly: embeddings, chunking strategies, ANN indexes (HNSW, IVF), hybrid search, reranking, and retrieval-quality evaluation — plus the storage choice, **pgvector vs. dedicated stores** (Qdrant, Weaviate, Milvus). Doubly adjacent: it deepens both the Postgres guides and the AI track, and it's where most "make the LLM know our docs" projects quietly fail.
8. **LLM Evaluation & Observability** *(AI)* — The hardest part of shipping AI, and the least taught: building eval sets, LLM-as-judge, regression-testing prompts in CI, and tracing token usage, latency, cost, and quality in production. Sits squarely between the [Observability guide](OBSERVABILITY_STUDY_GUIDE.md) and the LLM App Dev guide and is what separates a demo from a product.
9. **SQL (Beyond Postgres)** *(Languages / Data)* — Window functions, CTEs, and query-planning concepts that port across engines. Directly deepens the Postgres guides and your day-to-day work; the adjacency and personal-stack fit make it cheap to write and high-return.
10. **API Design** *(Architecture)* — REST, GraphQL, gRPC, OpenAPI, versioning, pagination, idempotency, and error models — opinionated and worked, not "REST 101." Newly urgent because the consumer of your API is increasingly an **agent**, and machine-legible, well-described, hard-to-misuse APIs are now a design constraint.
11. **Kafka & Streaming** *(Data)* — Topics, partitions, consumer groups, exactly-once semantics, the broker/producer/consumer model. The dominant streaming substrate; both the Data Engineering and the new Distributed Systems guides reference it, but it earns its own depth-first treatment.
13. **eBPF** *(Systems)* — Programmable kernel for observability, networking, and security without patching or rebooting — the engine under Cilium, Falco, Pixie, and `bpftrace`. One of the most consequential infrastructure shifts of the decade; pairs with the Networking, Observability, and Kubernetes guides and builds directly on a Linux Fundamentals guide.

---

## Tier 3 — Backlog (worthwhile, lower priority)

Good ideas that are more niche, more situational, or simply lower-leverage than the above right now:

- **React (Fundamentals)** *(Frontend)* — Hooks, reconciliation, server components; still the default of the job market, though lower personal fit given Vue.
- **Nginx & Reverse Proxies** *(Systems)* — Config language, upstreams, caching, TLS termination, rate limiting; still the most common proxy on the planet, and a foil to the Caddy guide.
- **Software Supply-Chain Security** *(Security)* — SLSA, Sigstore/cosign, SBOMs, signed and reproducible builds, dependency provenance; the area that's seen the most movement since the big 2020s supply-chain breaches, and a natural extension of the GitHub Actions guide.
- **WebAssembly (Wasm)** *(Systems)* — Server-side and edge Wasm, the component model, WASI; the portable, sandboxed runtime story that keeps gaining ground for plugins and untrusted code.
- **AI-Assisted Development** *(Tools)* — Working *with* agentic coding tools as a discipline: context curation, custom agents and skills, MCP servers, and evaluating your own workflow. Meta, fast-moving, and increasingly the difference in day-to-day throughput.
- **Local & Self-Hosted LLMs** *(AI)* — llama.cpp, Ollama, GGUF, quantization, and the economics of running inference yourself; relevant to homelab and Pi-class experiments.
- **Platform Engineering & IDPs** *(Systems)* — Backstage, golden paths, self-service infrastructure; the 2026 evolution of "DevOps" into building paved roads for other engineers.
- **Async & Advanced Rust** *(Languages)* — Tokio, `Pin`/`async` internals, trait objects, and judicious `unsafe`; the next step past the Rust-for-Python guide and a direct hit on your stack.
- **Lakehouse Table Formats** *(Data)* — Apache Iceberg, Delta, and Hudi; the open-table layer reshaping analytics, and a clean deepening of the Data Engineering guide.
- **DuckDB & the Local-Analytics Stack** *(Data)* — In-process OLAP, Parquet, and the "small data is most data" movement; pairs with the Postgres and Data Engineering guides.
- **GitOps** *(Systems)* — Argo CD / Flux, declarative continuous delivery, drift detection; pairs with the Kubernetes and Terraform guides.
- **Event-Driven Architecture** *(Architecture)* — Event sourcing, CQRS, sagas, idempotency; best written after Kafka and alongside the new Distributed Systems guide.
- **Embedded Linux on the Raspberry Pi Zero 2 W** *(Hardware)* — Boot process, GPIO, I2C/SPI/UART, device-tree overlays, low-power modes; the most directly actionable topic given the hardware already on your desk.
- **Modern CSS** *(Frontend)* — Grid, container queries, custom properties, cascade layers, modern selectors; framework-agnostic, so it pays off across the Vue/Next/Svelte guides.
- **Modern JS Runtimes** *(Languages)* — Bun and Deno: the post-Node toolchain, built-in tooling, and Web-standard APIs.
- **GCP** *(Systems)* — The third cloud; a natural follow-on once AWS exists.

Lower still, but on the radar: **Domain-Driven Design**, **Service Mesh** (Istio/Linkerd/Cilium), **Bash & Shell Scripting**, **C & Systems Programming**, **Threat Modeling**, **Pulumi & Crossplane**, **Tauri**, **Zig**, **Elixir & OTP**, and the terminal/build pair of **tmux** and **Make**.

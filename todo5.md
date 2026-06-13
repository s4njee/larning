# ToDo 5 — Tactical Mermaid Diagrams for Every Guide

Goal: add **rendered diagrams** where prose and ASCII art can't carry the idea
— sequence flows, state machines, request/response handshakes, architecture
graphs, decision trees, ER relationships. The point is comprehension, not
decoration: a diagram earns its place only when it shows something the
surrounding text genuinely struggles to.

**Working rules: no subagents; one guide at a time, in checklist order.**

---

## The tactical rule — what to convert, what to leave

Almost every guide already has ASCII box-drawing diagrams (see the density
survey below). **Do not blanket-convert them.** Mermaid is *better* at some
shapes and *worse* at others:

**Convert to mermaid** (relational / temporal / stateful):
- **Sequence diagrams** — handshakes, protocol exchanges, request lifecycles
  (TLS handshake, OAuth flow, WebSocket upgrade, Raft RPC rounds, a SQL query's
  trip through the planner).
- **State machines** — connection states, TCP state diagram, pod lifecycle,
  transaction states, a goroutine/task's lifecycle.
- **Flowcharts / decision trees** — "should you use X?", the cache-decision
  path, scheduler decisions, the GC's mark/sweep flow.
- **Architecture / component graphs** — control-plane components and their
  edges, a data pipeline's stages, service topology, the three-process
  Electron/Qt model.
- **ER diagrams** — schema relationships in the database/Django guides.

**Leave as ASCII** (spatial / exact-layout):
- Memory layouts, stack/heap diagrams, byte/packet/frame layouts, bitfields.
- Directory trees, file-on-disk structures, B-tree/page layouts where the
  *spatial* arrangement is the point.
- Terminal-output mockups and anything where monospace alignment carries
  meaning.

When in doubt: if the diagram is about **who talks to whom, in what order, or
in what state** → mermaid. If it's about **how bytes/objects are arranged in
space** → leave the ASCII.

Budget: **1–4 diagrams per guide.** Most guides need 1–2 well-chosen ones;
the systems-heavy guides justify 3–4. Adding a weak diagram is worse than
adding none.

---

## Phase 0 — Infrastructure — ✅ COMPLETE (2026-06-13)

The site's pages are **self-contained, no-network-deps** (see `ToDo.md`), so
the runtime-`mermaid.js` options are both wrong: a CDN `<script>` breaks
offline/air-gapped viewing and the black-theme guarantee, and inlining the
~3 MB library into every one of 67 pages is absurd. **Render at build time to
inline SVG instead** — zero client JS, fully self-contained, themeable. The
extra constraint that drove the design: **CI builds with Python only** (no
Node), so rendered SVGs are cached on disk and committed; CI reuses the cache
and only a *new/changed* diagram needs the `mmdc` renderer locally.

- [x] **`mermaid` fenced-block support in `build_guide.py`.** A ` ```mermaid `
      block is intercepted before `escape_raw_html_tags()` and Markdown (same
      bypass the `quiz` fence uses; extracted *first* so it survives both),
      rendered via `mmdc` to an SVG, and inlined inside
      `<figure class="mermaid-diagram">…</figure>`. SVG ids are namespaced
      per-diagram (and mermaid's own duplicate actor ids de-duped) so multiple
      diagrams on a page don't collide.
- [x] **Cache + CI strategy.** SVGs cached under `diagram_cache/<sha>.svg`
      keyed by `CACHE_VERSION + source`, committed to the repo. Cache hit →
      no renderer needed (CI path). Cache miss + no `mmdc` → build fails loudly
      (`_render_mermaid_svg` raises) rather than dropping the diagram.
      `package.json` declares `@mermaid-js/mermaid-cli`; `node_modules/` and
      `package-lock.json` gitignored.
- [x] **Theming.** SVG rendered on a transparent background and presented on a
      fixed light "figure card" (`.mermaid-diagram` CSS in `build_caddy_html.py`)
      so it's legible under both the black default and the light theme toggle.
      (Accent-tinting node strokes is a possible later refinement.)
- [x] **Graceful GitHub fallback + TOC/escaping safety.** On github.com the
      fence renders natively; the inlined SVG is a `<figure>` so it never enters
      the h2/h3 TOC, and extraction-before-escape means no `&amp;lt;` artifacts.
- [x] **Documented in `CLAUDE.md`** (repo layout, build commands, Markdown
      conventions, a "Diagrams" subsection with the tactical rule).
- [x] **Piloted on `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md`** — replication
      topologies (graph) + Raft log-replication commit flow (sequence). Full
      build clean: 2 figures, 0 id collisions, 0 placeholder leaks, 0
      double-escapes, all `url(#…)` references resolve, TOC unaffected.

## Working method (per guide)

1. Skim the guide's existing ASCII diagrams and Part structure; pick the
   **1–4 spots** where a relational/temporal/state diagram beats the prose.
2. Author ` ```mermaid ` blocks at those spots (replace the ASCII where you're
   upgrading one; add new where there's a gap). Keep ASCII for spatial layouts.
3. `python3 build_all_guides.py`; open the page, confirm each diagram renders
   as inline SVG, is legible on black + light themes, and no `&amp;lt;`
   artifacts appeared near the blocks.
4. Tick the box here with a note on what was added; commit the Markdown +
   rebuilt `html/` together, one commit per guide or small batch.

---

## Batch A — Systems, networking, databases (highest payoff) — ✅ COMPLETE (2026-06-13)

These earn the most diagrams: protocols, state machines, and topologies are
their core and prose carries them poorly. Each guide got 1–2 high-value
diagrams; *follow-ups* noted per entry are optional later additions.

- [x] `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` — **pilot done.** Graph: the three
      replication topologies (single-leader/multi-leader/leaderless). Seq: Raft
      log-replication commit flow (append→majority-ack→commit→apply, plus the
      lagging-follower log-match repair). *Possible follow-ups: leader-election
      sequence, 2PC commit, a node's view through a partition.*
- [x] `DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md` — Seq: Paxos prepare/promise +
      propose/accept message flow with majorities (added alongside the
      pseudocode). *Follow-ups: FLP/quorum intersection flow, Raft term
      transitions.*
- [x] `NETWORKING_FUNDAMENTALS.md` — Seq: TCP three-way handshake (replaced
      ASCII). State: the TCP state machine, active-open/active-close path
      (replaced ASCII). *Follow-ups: DNS resolution chain, packet path through
      the layers.*
- [x] `LINUX_NETWORKING_STUDY_GUIDE.md` — Graph: the veth-pair two-namespace
      lab and the three-namespace router lab (topologies for the Part 8 labs).
      *Follow-ups: netfilter chain traversal, packet routing-decision flow.*
- [x] `DATABASE_INTERNALS_STUDY_GUIDE.md` — Flow: the engine layer cake —
      query pipeline (parser→executor) on the subsystem stack (replaced ASCII,
      kept chapter cross-refs). B-tree/page layouts left as ASCII. *Follow-ups:
      WAL write path, 2PL lock acquisition.*
- [x] `ADVANCED_POSTGRES.md` — Flow: the WAL write path showing the
      WAL-before-data decoupling (commit fsyncs cheap sequential WAL; data
      pages lag, flushed by checkpoint; recovery replays forward; replaced
      ASCII). *Follow-ups: planner stages, MVCC visibility decision; same for
      `POSTGRES.md`.*
- [x] `POSTGRES_EXTENSIONS.md` — Graph: Citus coordinator→workers sharding
      topology (single-tenant routing vs cross-tenant fan-out; reference tables
      replicated to each worker). *Follow-up: logical-replication/CDC
      publisher→subscriber topology.*
- [x] `SQLITE_STUDY_GUIDE.md` — State: the five lock states
      (UNLOCKED→SHARED→RESERVED→PENDING→EXCLUSIVE) in rollback-journal mode
      (replaced ASCII). *Follow-up: WAL vs rollback-journal mode transitions.*
- [x] `REDIS_STUDY_GUIDE.md` — Graph: Sentinel + primary/replica topology
      (replaced ASCII). Seq: the Sentinel failover (ODOWN→promote→reconfigure→
      client rediscovery). *Follow-up: Cluster hash-slot ownership graph.*
- [x] `EBPF_STUDY_GUIDE.md` — Flow: program lifecycle with the verifier as a
      decision gate (load→verify→reject/JIT→attach→run→maps). *Follow-up: graph
      of where probe types hook into the kernel path.*
- [x] `DATA_ENGINEERING_STUDY_GUIDE.md` — Graph: the Phase 14 end-to-end
      production pipeline (sources→Kafka→S3→Iceberg bronze→Snowflake marts→
      BI/Reverse-ETL/Feature-store, tools on the edges; replaced ASCII).
      *Follow-up: dbt model DAG.*
- [x] `COMPILER_INTERNALS_STUDY_GUIDE.md` — Flow: the implementation pipeline
      grouped into frontend/middle-end/backend subgraphs + runtime alongside
      (replaced ASCII, chapter refs kept). SSA/memory layouts left as ASCII.
      *Follow-up: JIT tiered-compilation decision flow.*

## Batch B — Infra, cloud, ops

- [x] `k8s/KUBERNETES_STUDY_GUIDE.md` — Seq: what happens on `kubectl apply`
      (every component watches the API server). State: Pod phase lifecycle
      (Pending→Running→Succeeded/Failed, Unknown). *Follow-up: control-plane
      component graph.*
- [x] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md` — Flow: the full API-mutation
      path (authn→authz/RBAC→mutating webhooks→schema validation→validating
      webhooks/CEL→etcd, with reject branches). *Follow-up: operator reconcile
      loop.*
- [x] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md` — Flow: the four gates
      (authentication→authorization/RBAC→admission→etcd, each independently
      able to reject; replaced ASCII). *Follow-up: 4Cs threat-model graph.*
- [ ] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` — Graph: pod→service→
      endpoint→pod packet path; CNI topology.
- [x] `DOCKER_STUDY_GUIDE.md` — State: the HEALTHCHECK state machine
      (starting→healthy/unhealthy with the start-period grace window). Image
      layer/overlay stack left as prose (spatial). *Follow-up: namespaces/
      cgroups isolation concept graph.*
- [x] `TERRAFORM_STUDY_GUIDE.md` — Flow: the three-inputs diff (config + state
      + reality → plan-as-contract → apply), the guide's central thesis.
      *Follow-ups: resource DAG, remote-state lock acquisition sequence.*
- [ ] `ANSIBLE_STUDY_GUIDE.md` — Seq: a play's task→module→handler flow across
      control node and targets.
- [x] `GITHUB_ACTIONS_STUDY_GUIDE.md` — Seq: the OIDC token exchange to a
      cloud (request JWT → AssumeRoleWithWebIdentity → trust-policy match →
      short-lived creds; no stored secrets). *Follow-ups: job/step lifecycle,
      matrix/needs DAG.*
- [x] `OBSERVABILITY_STUDY_GUIDE.md` — Graph: a distributed trace as a causal
      span tree across services (service + duration per span; replaced ASCII
      waterfall). *Follow-ups: OTel collector pipeline, burn-rate alert
      decision.*
- [ ] `CLOUDFLARE_STUDY_GUIDE.md` — Seq: a request through the proxy pipeline
      (edge→cache→Worker→origin). Flow: the cache decision tree.
- [ ] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` — Graph: tenant/MG/subscription/RG
      hierarchy; Entra-vs-RBAC split.
- [ ] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md` — Graph: org→folder→project→resource
      hierarchy; global VPC topology.
- [x] `GIT_STUDY_GUIDE.md` — Graph: the object model (commit→tree→blob with
      parent links) and the three trees (working/index/HEAD) with the commands
      that move data between them (both replaced ASCII). *Follow-up: fetch vs
      pull sequence.*
- [ ] `ADVANCED_LINUX_STUDY_GUIDE.md` — Flow: process→syscall→kernel path;
      a page fault's resolution. State: process states. (Diagram-dense; leave
      the memory-layout ASCII, convert the flows/states.)
- [ ] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` — State: process lifecycle; flow:
      fork/exec; a signal's delivery path.

## Batch C — Languages, runtimes, concurrency

- [ ] `ADVANCED_GO_STUDY_GUIDE.md` — Graph: GMP scheduler (goroutines→M→P);
      channel send/recv rendezvous. Flow: GC mark phases.
- [ ] `ADVANCED_RUST_STUDY_GUIDE.md` — Flow: borrow-checker decision; state:
      a value's ownership/move lifecycle. (Leave memory layouts ASCII.)
- [ ] `ADVANCED_PYTHON_STUDY_GUIDE.md` — Flow: the import system; descriptor
      lookup order. (Diagram-dense — pick the flows.)
- [ ] `ADVANCED_NODEJS_STUDY_GUIDE.md` — Flow: the event-loop phases
      (timers→pending→poll→check→close); a request through libuv.
- [ ] `ASYNCIO_STUDY_GUIDE.md` — Seq: event loop scheduling await points;
      state: a Task's lifecycle (pending→done/cancelled).
- [ ] `PYTHON_CONCURRENCY.md` — Flow: GIL held-vs-released decision; the
      model-choice decision tree (thread/process/async).
- [ ] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` — Side-by-side flow: both event
      loops; the colored-function call path.
- [ ] `TYPESCRIPT_STUDY_GUIDE.md` — Flow: conditional-type distribution; the
      type-narrowing decision. (Mostly fine as prose — max 1–2.)
- [ ] `CPP26_STUDY_GUIDE.md` — Seq: coroutine suspend/resume; flow: RAII
      destruction order. 
- [ ] `SWIFT_STUDY_GUIDE.md` — Graph: ARC retain/release + cycle; flow:
      protocol static-vs-dynamic dispatch decision. State: actor reentrancy.
- [ ] `GOLANG_FOR_PYTHON_DEVS.md` — Graph: goroutine scheduling vs threads
      (one comparison diagram). *(Low ASCII density — likely adds new.)*
- [ ] `RUST_FOR_PYTHON_DEVS.md` — Flow: ownership "third answer" decision.
- [ ] `DOTNET_FOR_PYTHON_DEVS.md` — Flow: IL→JIT→native; Task vs Thread.
      *(Low ASCII density — likely adds new.)*

## Batch D — Web, frontend, apps

- [ ] `NEXTJS_STUDY_GUIDE.md` — Flow: the rendering decision (static/ISR/
      streaming); request through the four caches. Seq: a Server Action.
- [ ] `VUE_STUDY_GUIDE.md` — Graph: reactivity dependency tracking
      (ref→effect→re-render); flow: a component's update cycle.
- [ ] `SVELTEKIT_STUDY_GUIDE.md` — Flow: universal-vs-server load resolution;
      seq: a form action's fail/enhance path.
- [ ] `DJANGO_STUDY_GUIDE.md` — ER: model relationships; flow: a request
      through middleware→view→ORM. Seq: signals around `save()`.
- [ ] `ELECTRON_STUDY_GUIDE.md` — Graph: the three-process model (main/
      renderer/preload) + IPC edges. Seq: an `invoke` round-trip.
- [ ] `QT_STUDY_GUIDE.md` — Seq: signal→slot across thread affinity; flow:
      the event loop dispatch. Graph: parent-child ownership tree.
- [ ] `WEBSOCKETS_STUDY_GUIDE.md` — Seq: the HTTP→WS upgrade handshake; the
      backplane fan-out topology. State: connection lifecycle + 1006/close.
- [ ] `WEBGL_OPENGL_STUDY_GUIDE.md` — Flow: the rendering pipeline (vertex→
      clip→raster→fragment); the state-machine binding model.
      *(Low ASCII density — adds new; high payoff.)*
- [ ] `WEBGPU_STUDY_GUIDE.md` — Flow: explicit pipeline setup vs GL state;
      seq: async command submission. *(Low ASCII density — adds new.)*
- [ ] `IOS_DEVELOPMENT_STUDY_GUIDE.md` — Flow: SwiftUI body re-evaluation;
      graph: MVVM layer responsibilities. State: `.task` cancellation.
- [ ] `CB8_IOS_STUDY_GUIDE.md` — Graph: nodejs-mobile two-phase architecture;
      seq: the server-owns-completion request path.
- [ ] `CB8_ANDROID_STUDY_GUIDE.md` — Graph: the on-device-node architecture;
      flow: SAF-vs-bookmark file access decision.

## Batch E — Security, AI, embedded, tools, the rest

- [ ] `CRYPTO_FUNDAMENTALS.md` — Seq: TLS 1.3 handshake; DH key exchange;
      a signature verify flow. (Leave block-cipher byte diagrams ASCII.)
- [ ] `AUTH_STUDY_GUIDE.md` — Seq: OAuth2 + PKCE authorization-code flow;
      OIDC; session-vs-JWT validation paths. State: refresh-token rotation.
- [ ] `WEB_LLM_SECURITY_STUDY_GUIDE.md` — Flow: SSRF confused-deputy path;
      CSRF token-check flow; the prompt-injection data/instruction confusion.
- [ ] `KALI_LINUX_STUDY_GUIDE.md` — Flow: the recon→exploit→post-ex kill chain;
      graph: AD attack graph (Kerberoast/NTLM-relay paths).
- [ ] `AI_AGENTS_STUDY_GUIDE.md` — Flow: the agent loop (ReAct: think→act→
      observe); decision: workflow-vs-agent. Graph: multi-agent handoffs.
- [ ] `LLM_APP_DEV_STUDY_GUIDE.md` — Flow: a RAG request (retrieve→rerank→
      generate); decision: RAG-vs-finetune. Seq: tool/function calling.
- [ ] `ENTERPRISE_API_STUDY_GUIDE.md` — Seq: idempotency-key reservation flow;
      flow: the rate-limit (token-bucket) decision; ETag optimistic-concurrency.
- [ ] `TESTING_STUDY_GUIDE.md` — Graph: the test pyramid (already a concept
      that wants a diagram); flow: the dependency-boundary mock-vs-fake decision.
      *(Low ASCII density — adds new.)*
- [ ] `BLENDER_STUDY_GUIDE.md` — Graph: object→datablock instancing relations;
      flow: the modifier stack evaluation order; EEVEE-vs-Cycles decision.
      (Diagram-dense — pick the relational ones.)
- [ ] `ESP32_STUDY_GUIDE.md` — Flow: boot→app_main; deep-sleep wake cycle;
      decision: blocking delay vs vTaskDelay vs millis. (Leave pin/memory
      maps ASCII.)
- [ ] `RASPBERRY_PI_STUDY_GUIDE.md` — Flow: the boot chain (bootcode→start.elf
      →kernel→device tree); decision: undervoltage→throttle. (Leave GPIO
      pinout ASCII.)
- [ ] `VIM_STUDY_GUIDE.md` — Graph: the operator+motion+text-object grammar;
      state: the mode transitions (normal/insert/visual/cmdline). *(Modes are
      a textbook state diagram.)*

## Bespoke pages

- [ ] `build_caddy_html.py` — Caddy already has a decision-helper; consider a
      seq diagram for automatic-HTTPS/ACME issuance. Verify SVG theming after
      any shared-CSS change.
- [ ] `build_nginx_html.py` — Seq: a request through the nginx phases
      (rewrite→access→content); the master/worker process model.

---

64 guide files + 2 bespoke pages (Caddy/Nginx, built from their `.py`
generators) = 66 targets. Progress: Phase 0 ✅ complete; Batch A ✅ complete
(12 guides); Batch B in progress (Kubernetes, Docker, Terraform, Git, GitHub
Actions, Observability done — 6 of 15). 18 guides total carry diagrams.
Diagrams are **additive and tactical** — a guide is "done" here when
its 1–4 highest-value relational/temporal/state diagrams render as inline SVG
on both themes, with spatial/byte-layout diagrams left as ASCII.

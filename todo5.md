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

## Batch B — Infra, cloud, ops — ✅ COMPLETE (2026-06-13)

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
- [x] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` — Graph: the two data
      paths compared — Docker published-port (host→DNAT→docker0→veth→container)
      vs Kubernetes (client→LB/Ingress→Service VIP→Pod IP via CNI); replaced
      ASCII.
- [x] `DOCKER_STUDY_GUIDE.md` — State: the HEALTHCHECK state machine
      (starting→healthy/unhealthy with the start-period grace window). Image
      layer/overlay stack left as prose (spatial). *Follow-up: namespaces/
      cgroups isolation concept graph.*
- [x] `TERRAFORM_STUDY_GUIDE.md` — Flow: the three-inputs diff (config + state
      + reality → plan-as-contract → apply), the guide's central thesis.
      *Follow-ups: resource DAG, remote-state lock acquisition sequence.*
- [x] `ANSIBLE_STUDY_GUIDE.md` — Flow: play execution order (pre_tasks→roles→
      tasks→post_tasks→handlers) with the deferred, de-duplicated handler queue
      (notified handlers run once at play end).
- [x] `GITHUB_ACTIONS_STUDY_GUIDE.md` — Seq: the OIDC token exchange to a
      cloud (request JWT → AssumeRoleWithWebIdentity → trust-policy match →
      short-lived creds; no stored secrets). *Follow-ups: job/step lifecycle,
      matrix/needs DAG.*
- [x] `OBSERVABILITY_STUDY_GUIDE.md` — Graph: a distributed trace as a causal
      span tree across services (service + duration per span; replaced ASCII
      waterfall). *Follow-ups: OTel collector pipeline, burn-rate alert
      decision.*
- [x] `CLOUDFLARE_STUDY_GUIDE.md` — Flow: the reverse-proxy pipeline every
      request traverses (DDoS→firewall→WAF→Access→Transform→Workers→cache
      hit/miss→origin; replaced ASCII), with the cache decision as a branch.
- [x] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` — Graph: the management hierarchy
      (Entra tenant→management groups→subscriptions→resource groups→resources),
      with the RBAC/Policy downward-inheritance note.
- [x] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md` — Graph: the resource hierarchy
      (Organization→Folders→Projects→Resources, billing account linked), with
      IAM downward-inheritance note.
- [x] `GIT_STUDY_GUIDE.md` — Graph: the object model (commit→tree→blob with
      parent links) and the three trees (working/index/HEAD) with the commands
      that move data between them (both replaced ASCII). *Follow-up: fetch vs
      pull sequence.*
- [x] `ADVANCED_LINUX_STUDY_GUIDE.md` — Flow: the I/O path (app→VFS→fs→page
      cache→block layer→driver→device; replaced ASCII) and the copy-on-write
      fork + write-fault resolution. Memory-layout ASCII left as-is.
- [x] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` — State: the process state machine
      (R/S/D/T/Z transitions). Flow: fork+exec (fork copies, exec replaces the
      image at the same PID; replaced ASCII). *Follow-up: signal delivery
      path.*

## Batch C — Languages, runtimes, concurrency — ✅ COMPLETE (2026-06-13)

- [x] `ADVANCED_GO_STUDY_GUIDE.md` — Graph: the GMP scheduler (Gs in each P's
      run queue, P→M→CPU binding, global queue feeding via work-stealing;
      replaced ASCII). *Follow-up: GC mark-phase flow.*
- [ ] `ADVANCED_RUST_STUDY_GUIDE.md` — Flow: borrow-checker decision; state:
      a value's ownership/move lifecycle. (Leave memory layouts ASCII.)
- [x] `ADVANCED_PYTHON_STUDY_GUIDE.md` — Flow: the attribute-lookup chain for
      `obj.attr` (data descriptor → instance __dict__ → non-data descriptor →
      __getattr__ → AttributeError), the decision behind property/__slots__.
- [x] `ADVANCED_NODEJS_STUDY_GUIDE.md` — Flow: the libuv event-loop phase cycle
      (timers→pending→idle/prepare→poll→check→close→next iteration; replaced
      ASCII).
- [x] `ASYNCIO_STUDY_GUIDE.md` — State: the Task lifecycle (pending→running⇄
      suspended-at-await→done/failed/cancelled), making cooperative scheduling
      concrete.
- [x] `PYTHON_CONCURRENCY.md` — Flow: the model-choice decision tree
      (CPU-vs-I/O-bound → native lib / processes / asyncio / threads / hybrid;
      replaced ASCII), the guide's central decision.
- [x] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` — Graph: the colored-function
      contagion — one async leaf (`db.query`) forces every caller up the stack
      to become async (red spreads upward).
- [x] `TYPESCRIPT_STUDY_GUIDE.md` — Graph: the type lattice (never bottom →
      concrete types → unknown top) as an "is assignable to" hierarchy, with
      the note that `any` sits outside it.
- [x] `CPP26_STUDY_GUIDE.md` — Seq: coroutine suspend/resume via the lazy
      `std::generator` pull model (co_yield suspends, frame preserved, caller
      pulls to resume). *Follow-up: RAII destruction order.*
- [x] `SWIFT_STUDY_GUIDE.md` — Graph: the ARC retain cycle (Person↔Dog strong =
      leak) vs the `weak`-broken version (frees). *Follow-ups: dispatch
      decision, actor reentrancy.*
- [x] `GOLANG_FOR_PYTHON_DEVS.md` — Graph: M:N scheduling — many goroutines
      multiplexed onto few OS threads onto CPU cores (the intro companion to
      Advanced Go's GMP diagram).
- [x] `RUST_FOR_PYTHON_DEVS.md` — Graph: the three answers to "when is it safe
      to free?" (manual / GC / ownership) and their trade-offs — the guide's
      framing for why ownership exists.
- [x] `DOTNET_FOR_PYTHON_DEVS.md` — Flow: the compilation model (C# source →
      IL → CLR loads → JIT to native). *Follow-up: Task vs Thread.*

## Batch D — Web, frontend, apps — ✅ COMPLETE (2026-06-13)

- [x] `NEXTJS_STUDY_GUIDE.md` — Flow: how `next build` infers the rendering
      mode (request-time info → dynamic/streaming; else static, or ISR if
      revalidate set). *Follow-ups: four-caches request path, Server Action.*
- [x] `VUE_STUDY_GUIDE.md` — Graph: the reactivity track/trigger cycle (effect
      reads → get trap tracks into the dependency map → mutation's set trap
      triggers → re-runs the effect), the guide's central mental model.
- [x] `SVELTEKIT_STUDY_GUIDE.md` — Seq: the transitional-app lifecycle (server
      load + SSR HTML → hydrate → client-router SPA navigation). *Follow-ups:
      universal-vs-server load, form-action enhance path.*
- [x] `DJANGO_STUDY_GUIDE.md` — Flow: the request/response pipeline (server→
      handler→middleware down→URL→view→middleware up→response; replaced ASCII),
      the guide's top mental model. *Follow-ups: ER model, save() signals.*
- [x] `ELECTRON_STUDY_GUIDE.md` — Graph: the three-process model — sandboxed
      renderer → preload contextBridge → privileged main process across the IPC
      boundary.
- [x] `QT_STUDY_GUIDE.md` — Seq: cross-thread queued signal delivery (worker
      emits → args copied into an event posted to the receiver's loop → slot
      runs on the main thread, lock-free). *Follow-up: parent-child ownership
      tree.*
- [x] `WEBSOCKETS_STUDY_GUIDE.md` — Seq: the HTTP→WS upgrade handshake (GET
      Upgrade → 101 Switching Protocols → full-duplex framing). *Follow-ups:
      backplane fan-out, connection lifecycle + 1006/close.*
- [x] `WEBGL_OPENGL_STUDY_GUIDE.md` — Flow: the rendering pipeline (vertex
      buffers→vertex shader→assembly→clip→raster→fragment shader→depth/stencil→
      blend→framebuffer; replaced ASCII), marking the programmable stages.
- [x] `WEBGPU_STUDY_GUIDE.md` — Flow: the WebGL-vs-WebGPU decision tree
      (compatibility/compute/library questions; replaced ASCII). *Follow-up:
      command-encoder→queue.submit async flow.*
- [x] `IOS_DEVELOPMENT_STUDY_GUIDE.md` — Flow: the SwiftUI declarative loop
      (state change → re-invoke body → diff view tree → minimal screen update →
      interaction mutates state). *Follow-ups: MVVM layers, .task cancellation.*
- [x] `CB8_IOS_STUDY_GUIDE.md` — Graph: the three-deployment architecture (one
      codebase → Electron/Docker/Node, all hosting the same Fastify HTTP server;
      GUI decoupled over HTTP, so iOS is just another client) — the fact that
      makes the port feasible.
- [x] `CB8_ANDROID_STUDY_GUIDE.md` — Graph: the two-phase porting strategy
      (Phase 1 Compose client → existing CB8 `/api`; Phase 2 on-device library
      via SAF + in-process readers + Room, same UI).

## Batch E — Security, AI, embedded, tools, the rest — in progress

- [x] `CRYPTO_FUNDAMENTALS.md` — Seq: the TLS 1.3 1-RTT handshake (ClientHello
      + key share → ServerHello/cert/finished → client finished + app data).
      Block-cipher byte diagrams left as ASCII. *Follow-ups: DH exchange,
      signature verify.*
- [x] `AUTH_STUDY_GUIDE.md` — Seq: the OAuth2 + PKCE authorization-code flow
      (challenge on /authorize, verifier on /token, server matches the hash;
      replaced ASCII). *Follow-ups: refresh-token rotation, session-vs-JWT.*
- [ ] `WEB_LLM_SECURITY_STUDY_GUIDE.md` — Flow: SSRF confused-deputy path;
      CSRF token-check flow; the prompt-injection data/instruction confusion.
- [ ] `KALI_LINUX_STUDY_GUIDE.md` — Flow: the recon→exploit→post-ex kill chain;
      graph: AD attack graph (Kerberoast/NTLM-relay paths).
- [x] `AI_AGENTS_STUDY_GUIDE.md` — Flow: the agent loop (call model → stop_reason
      end_turn=done / tool_use=execute+append+loop → max_steps guard),
      visualizing the minimal-loop code. *Follow-ups: workflow-vs-agent
      decision, multi-agent handoffs.*
- [x] `LLM_APP_DEV_STUDY_GUIDE.md` — Flow: the RAG pipeline (query→retrieve→
      rerank→inject→generate, with the offline chunk→embed→vector-store index;
      replaced ASCII). *Follow-ups: RAG-vs-finetune, tool calling.*
- [ ] `ENTERPRISE_API_STUDY_GUIDE.md` — Seq: idempotency-key reservation flow;
      flow: the rate-limit (token-bucket) decision; ETag optimistic-concurrency.
- [x] `TESTING_STUDY_GUIDE.md` — Flow: the dependency-boundary test-double
      decision (real inside the boundary; fake/stub/mock outside by what the
      test needs). Pyramid/trophy left as ASCII (proportional/spatial).
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
generators) = 66 targets. Progress: Phase 0 ✅; Batch A ✅ (12); Batch B ✅ (15);
Batch C ✅ (13); Batch D ✅ (13). 53 guides total carry diagrams. Next:
Batch E (security/AI/embedded/tools) + the 2 bespoke pages. Diagrams are
**additive and tactical** — a guide is "done" here when
its 1–4 highest-value relational/temporal/state diagrams render as inline SVG
on both themes, with spatial/byte-layout diagrams left as ASCII.

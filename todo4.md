# ToDo 4 — Self-Check Quizzes for Every Guide

Goal: every study guide gets interactive self-check quizzes, rendered with the
quiz widget that already ships in the shared page template (the `quiz-item`
CSS/JS from `build_caddy_html.py` is on every page; only the bespoke Caddy
page actually uses it today). Retrieval practice is the point: each major Part
of a guide ends with a short quiz that tests the load-bearing ideas of that
Part, click-to-reveal explanation included.

**Working rules: no subagents; one guide at a time, in checklist order.**

---

## Phase 0 — Infrastructure (do first, before any guide) — ✅ COMPLETE (2026-06-12)

- [x] **Add a `quiz` fenced-block syntax to `build_guide.py`.** A fenced code
  block with language `quiz` compiles to the same markup
  `render_quiz()` emits in `build_caddy_html.py` (`.addon.quiz` →
  `.quiz-item` → `.quiz-opts`/`.quiz-opt[data-correct]` → `.quiz-explain`).
  Proposed authoring format, one or more questions per block:

  ````markdown
  ```quiz
  Q: What single feature most distinguishes Caddy from Nginx?
  - [x] Automatic HTTPS by default, with zero TLS configuration
  - [ ] It is written in Go
  - [ ] It supports reverse proxying
  > All of those servers can do ACME — but only Caddy obtains, configures,
  > and renews certificates out of the box with no configuration.
  ```
  ````

  Parsing rules: `Q:` starts a question; `- [x]`/`- [ ]` are options (exactly
  one `[x]`); `>` lines are the explanation (joined with spaces); blank line
  between questions. HTML-escape all text. Exactly one correct option per
  question — fail the build loudly on malformed blocks rather than emitting
  broken markup.
- [x] **Make sure the block bypasses the rest of the pipeline**: the `quiz`
  fence must be consumed before code-block rendering, `escape_raw_html_tags()`
  (the emitted markup must not be escaped), and TOC extraction. In the
  GitHub-rendered Markdown a `quiz` fence degrades gracefully to a visible
  code block — acceptable, but verify it doesn't break sibling-link rewriting.
- [x] **Verify rendering end to end**: built a temp guide with a quiz block;
  markup matches `render_quiz()` byte-for-byte (same classes/attributes the
  shared `setupQuiz` JS drives on the Caddy page), quiz `h3` stays out of the
  TOC, full-site rebuild byte-identical, no placeholder leaks or `&amp;lt;`
  artifacts. (No browser in this environment — click-through relies on the
  markup matching the already-working Caddy widget; spot-check in a browser
  when reviewing the pilot guide.)
- [x] **Document the syntax in `CLAUDE.md`** (Markdown conventions section +
  a new "Quizzes" subsection in the style guide: where quizzes go, how many
  questions, what makes a good question — see quality bar below).

## Quality bar for questions (apply to every guide)

- **3–5 questions per major Part**, placed at the end of the Part, just
  before the `---` rule. Short guides (< ~400 lines) may use a single
  5–8 question quiz before the closing sections instead.
- **Test the why, not trivia.** Ask about consequences, trade-offs, and
  "what happens when" — the things the guide's prose argues — never dates,
  version numbers, or definitions quotable verbatim from one sentence.
  Model: the Caddy Q1 asks what *distinguishes* Caddy, and every distractor
  is true-but-not-distinguishing.
- **Distractors must be plausible** — ideally true statements that don't
  answer the question, or common misconceptions the guide explicitly
  corrects. No joke options.
- **The explanation teaches**: one or two sentences that say why the right
  answer is right *and* why the tempting wrong one is wrong. It should be
  worth reading even after answering correctly.
- **4 options per question** (3 acceptable when the topic is genuinely
  binary/ternary). Vary the position of the correct answer.
- Don't quiz the intro, the takeaways list, or Where to Go Next.

## Working method (per guide)

1. Read the guide end to end; for each major Part, note its 3–5 load-bearing
   claims (the bolded terms and their consequences are the question bank).
2. Write the quiz block(s) per the quality bar; place at the end of each Part.
3. `python3 build_all_guides.py`; click through every new quiz in the built
   HTML; check for `&amp;lt;` artifacts near the new blocks.
4. Tick the guide's box here with a note (e.g. "8 parts × 4 Q"), commit the
   Markdown + rebuilt `html/` together, one commit per guide or small batch.

---

## Batch 1 — Pilot + flagship guides — ✅ COMPLETE (2026-06-12)

- [x] `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` — the pilot; 10 parts × 4–5 Q
      (48 questions), one quiz per Part after its closing paragraph
- [x] `ADVANCED_LINUX_STUDY_GUIDE.md` — 10 parts × 4–5 Q (48 questions)
- [x] `ADVANCED_GO_STUDY_GUIDE.md` — 10 parts × 4–5 Q (43 questions)
- [x] `ADVANCED_NODEJS_STUDY_GUIDE.md` — 10 parts × 4–5 Q (41 questions)
- [x] `ADVANCED_PYTHON_STUDY_GUIDE.md` — 10 parts × 3–5 Q (41 questions)
- [x] `ADVANCED_RUST_STUDY_GUIDE.md` — 13 parts × 3–4 Q (46 questions)
- [x] `ADVANCED_POSTGRES.md` — 6 cluster quizzes (28 questions: §1–3, §4–5, §6–7, §8–9, §10–12, §13–15)
- [x] `POSTGRES.md` — 6 cluster quizzes (30 questions across the reference sections)

## Batch 2 — Systems, databases, networking — ✅ COMPLETE (2026-06-12)

- [x] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` — 10 parts × 4 Q (40 questions)
- [x] `LINUX_NETWORKING_STUDY_GUIDE.md` — 7 quizzes (26 questions; Parts 2,4,5,7,8,9,10)
- [x] `EBPF_STUDY_GUIDE.md` — 7 quizzes (27 questions; architecture, types/maps, verifier, tooling, CO-RE, ecosystem, security)
- [x] `NETWORKING_FUNDAMENTALS.md` — 7 quizzes (30 questions; Phases 2,4,5,6,8,10,13)
- [x] `DATABASE_INTERNALS_STUDY_GUIDE.md` — 6 quizzes (28 questions; Ch 2,3,5,6,9,11)
- [x] `SQLITE_STUDY_GUIDE.md` — 5 quizzes (20 questions; types/pipeline, indexes, concurrency/WAL, performance, mistakes)
- [x] `REDIS_STUDY_GUIDE.md` — 6 quizzes (20 questions; mental model, sorted sets, eviction, transactions/Lua, persistence/replication, cluster)
- [x] `POSTGRES_EXTENSIONS.md` — 4 quizzes (16 questions; mechanics, observability/indexing, geo/timeseries/vectors, security/CDC/Citus)
- [x] `DATA_ENGINEERING_STUDY_GUIDE.md` — 5 quizzes (17 questions; storage formats, lakehouse, dbt, streaming, modeling)
- [x] `DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md` — 6 quizzes (23 questions; FLP, Paxos, Raft, quorums/CAP, atomic commit, CRDTs)
- [x] `COMPILER_INTERNALS_STUDY_GUIDE.md` — 5 quizzes (18 questions; parsing, IR/SSA, optimization/UB, JIT, GC)
- [x] `CRYPTO_FUNDAMENTALS.md` — 6 quizzes (20 questions; hashing, symmetric, asymmetric, key exchange, signatures, TLS)

## Batch 3 — Infra, cloud, and ops (COMPLETE)

- [x] `k8s/KUBERNETES_STUDY_GUIDE.md` — 5 quizzes (18 questions; architecture, workloads/probes, services, resources, debugging)
- [x] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md` — 5 quizzes (14 questions; control plane, API machinery, operators, multi-tenancy, GitOps)
- [x] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md` — 5 quizzes (15 questions; threat model, authn, RBAC, admission, hardening)
- [x] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` — 3 quizzes (9 questions; mental models, troubleshooting, advanced patterns)
- [x] `DOCKER_STUDY_GUIDE.md` — 5 quizzes (13 questions; isolation primitives, layers/cache, multi-stage, security, health/restart)
- [x] `TERRAFORM_STUDY_GUIDE.md` — 6 quizzes (12 questions; declarative/DAG/diff-as-contract, for_each vs count, what state is, remote backend locking, module-as-typed-function, sensitive vs ephemeral/write-only)
- [x] `ANSIBLE_STUDY_GUIDE.md` — 5 quizzes (14 questions; idempotency/module contract, handlers & blocks, register/set_fact & vault, serial/run_once/delegate_to, pipelining/mitogen/fact-caching)
- [x] `GITHUB_ACTIONS_STUDY_GUIDE.md` — 5 quizzes (15 questions; ephemeral-runner execution model, triggers/contexts/$GITHUB_ENV, caching/matrix/artifacts, OIDC/environments, pull_request_target/script-injection/SHA-pinning)
- [x] `OBSERVABILITY_STUDY_GUIDE.md` — 6 quizzes (18 questions; cardinality/monitoring-vs-observability, counters/rate/histograms, traces/sampling/propagation, OTel neutrality/auto-vs-manual/gateway, SLI-SLO-SLA/error-budgets/burn-rate, symptom-vs-cause alerting)
- [x] `CLOUDFLARE_STUDY_GUIDE.md` — 5 quizzes (15 questions; anycast/proxy-pipeline, cache decision/Cache-Everything sin, Workers isolate model/CPU-billing/bindings, KV-vs-DO-vs-R2 storage, Zero Trust/Tunnel inversion/JWT verification)
- [x] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` — 5 quizzes (15 questions; tenant/MG/subscription/RG hierarchy & regional subnets, Entra-vs-RBAC split & managed identities, NSG/Front-Door/L7-vs-L4, Cosmos consistency & partition keys, Key Vault/WAF-on-edge/Defender)
- [x] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md` — 5 quizzes (15 questions; project hierarchy/labels-vs-tags/multi-region, resource-bound IAM/no-users/actAs, global VPC/SA-targeted firewall/global LB, Spanner+TrueTime/Firestore-vs-Bigtable, BigQuery bytes-scanned/partitioning/Omni)
- [x] `GIT_STUDY_GUIDE.md` — 6 quizzes (17 questions; content-addressed object model, three-trees index & conflict stages, rebase rehashing & rebase-onto, reset/restore/revert, remote snapshot/fetch-vs-pull/force-with-lease, reflog recovery)
- [x] `VIM_STUDY_GUIDE.md` — 5 quizzes (15 questions; operator+motion grammar & counts, text objects inner/around & dot-refactor, registers/unnamed-vs-yank trap & named-append, :s ranges/flags & :g+:normal & cgn, macro robustness & 99@a & macro-vs-:g)

## Batch 4 — Languages and runtimes (COMPLETE)

- [x] `TYPESCRIPT_STUDY_GUIDE.md` — 6 quizzes (18 questions; types-as-sets & structural typing, type guards/asserts/never-exhaustiveness, generics constraints/keyof/inference, conditional-type distribution & infer & Exclude, any-vs-unknown/void/hierarchy, branded nominal types)
- [x] `CPP26_STUDY_GUIDE.md` — 5 quizzes (15 questions; RAII/move-elision/Rule-of-Zero, jthread-RAII/coroutine-suspension/library-gap, contracts-vs-exceptions & build-mode, erroneous-behavior/pack-indexing/_-placeholder, no-borrow-checker safety & sanitizers)
- [x] `SWIFT_STUDY_GUIDE.md` — 5 quizzes (15 questions; value-vs-reference & Sendable foundation, ARC determinism/cycles/weak-unowned, optionals-as-enum/chaining/IUO, protocol static-vs-dynamic-dispatch & some-vs-any & associatedtype, actors/Sendable/structured-concurrency)
- [x] `ASYNCIO_STUDY_GUIDE.md` — 5 quizzes (15 questions; I/O-vs-CPU value-prop & coroutine density, coroutine-objects/await-yield-points/task-concurrency, gather-order/exceptions & TaskGroup, cancellation-at-await/CancelledError-BaseException/timeouts, blocking-the-loop & to_thread-vs-ProcessPool & aiofiles)
- [x] `PYTHON_CONCURRENCY.md` — 5 quizzes (15 questions; GIL held-vs-released & NumPy escape hatch, thread races/queue/pool, process parallelism/__main__-guard/coarse-grained, futures unifying-API/submit-vs-map/exception-trap, model-choice numerical-native/thread-vs-async/to_thread-hybrid)
- [x] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` — 5 quizzes (14 questions; uniform-vs-fragmented ecosystems, eager-vs-lazy & forgotten-await, Promise-vs-coroutine/Task/Future & cancellation, colored-functions two-ecosystem-tax & asyncio.run trap, blocking-the-loop Node-structural-advantage)
- [x] `GOLANG_FOR_PYTHON_DEVS.md` — 5 quizzes (15 questions; implicit interfaces & embedding-not-inheritance, errors-as-values/%w-wrapping/error-interface, goroutine M:N-scheduling & no-colored-functions & WaitGroup, channels buffered-vs-unbuffered/CSP/close-rules, slice-aliasing/append-capacity/nil-map-panic)
- [x] `RUST_FOR_PYTHON_DEVS.md` — 5 quizzes (15 questions; ownership third-answer/move/Copy-vs-Clone, borrowing shared-XOR-mutable & NLL, enums-as-ADTs/Option/exhaustive-match, Option-vs-Result/?-operator/thiserror-vs-anyhow, fearless-concurrency/Arc-Mutex/Send-Sync)
- [x] `DOTNET_FOR_PYTHON_DEVS.md` — 5 quizzes (15 questions; var-inference/nullable-refs/IL-JIT, struct-value-copy & records-value-equality, LINQ deferred-execution/re-execution/IQueryable-SQL, GC-vs-IDisposable/using/throw-preserves-trace, Task-not-thread/WhenAll/avoid-.Result)

## Batch 5 — Web, frontend, and apps (COMPLETE)

- [x] `NEXTJS_STUDY_GUIDE.md` — 5 quizzes (15 questions; app-router filesystem/persistent-layouts/route-groups, use-client-door/serialization/children-slot, rendering-inference/ISR/streaming-Suspense, four-caches/tag-invalidation/use-cache, server-actions-public-endpoint/forms-progressive/route-handlers)
- [x] `VUE_STUDY_GUIDE.md` — 5 quizzes (15 questions; ref-.value-interception/destructuring-breaks/branch-deps, props-one-way/defineModel-desugar/scoped-slots, composables-run-once/return-refs/toValue-reactive-args, router instance-reuse/guard-return-values/guard-vs-component-fetch, storeToRefs-trap/Pinia-vs-DIY/local-first)
- [x] `SVELTEKIT_STUDY_GUIDE.md` — 5 quizzes (15 questions; runes deep-proxy/$derived-not-$effect/effect-timing-SSR, server-vs-universal-load/dependency-graph/streaming, form-actions fail-path/use:enhance/actions-vs-endpoints, module-scope-SSR-leak/$lib-server-structural/layout-guard-trap, prerender-eligibility/ssr-false/layout-payload)
- [x] `DJANGO_STUDY_GUIDE.md` — 5 quizzes (15 questions; null-vs-blank/on_delete/validation-trapdoor, lazy-querysets/N+1/F-and-Q, custom-user-early/authorization-is-filtering/auth-backends, post_save-pre-commit/signals-vs-services/select_for_update, SQL-param/csrf_exempt/mass-assignment)
- [x] `ELECTRON_STUDY_GUIDE.md` — 5 quizzes (15 questions; three-process model/preload-bridge/macOS-lifecycle, IPC least-privilege/invoke-vs-push/serialization, nodeIntegration-mistake/path-intent/ship-the-browser, electron-rebuild-ABI/client-migrations/sync-sqlite, signed-updates/staged-rollout/utilityProcess)
- [x] `QT_STUDY_GUIDE.md` — 5 quizzes (15 questions; moc/parent-child-ownership/lambda-context, event-loop blocking/processEvents-smell/events-vs-signals, model begin-end-pairs/cheap-data()/proxy-models, QML bindings/assign-over-binding/QML_ELEMENT-vs-context, worker-object affinity/QThread-misconception/QtConcurrent-vs-worker)
- [x] `WEBSOCKETS_STUDY_GUIDE.md` — 5 quizzes (14 questions; full-duplex value-prop/handshake-correctness/1006, jitter/bufferedAmount/intentional-close, backplane/sticky-sessions/connection-ceilings, CSWSH-origin/auth-options/heartbeats, at-most-once-default/at-least-once-recipe)
- [x] `WEBGL_OPENGL_STUDY_GUIDE.md` — 5 quizzes (15 questions; state-machine current-binding/state-leaks/debug-checklist, vertex-shader-clip-position/interpolation/perspective-divide, attribute-uniform-varying/GLSL-3.00-port/fragment-precision, no-camera-is-math/z-fighting/DPR-blur, depth-write-vs-test/transparency-sort/premultiplied-alpha)
- [x] `WEBGPU_STUDY_GUIDE.md` — 5 quizzes (15 questions; explicit-pipelines-vs-state/async-model/compute-capability, adapter-vs-device/usage-flags/immutable-pipelines, WGSL address-spaces/uniform-layout/binding-match, compute bounds-check/keep-on-GPU/workgroup-dispatch, async-error-scopes/labels/black-screen-bisection)
- [x] `IOS_DEVELOPMENT_STUDY_GUIDE.md` — 5 quizzes (12 questions; declarative-body/modifier-order/LazyVStack, @State-rerender/@Observable-granular/@Environment-shared, NavigationStack value-destination/router-path, .task-cancellation/@MainActor-viewmodel, MVVM repository-protocol/layer-responsibilities)
- [x] `CB8_IOS_STUDY_GUIDE.md` — 5 quizzes (14 questions; nodejs-mobile-trap/two-phase-strategy/wrapper-limits, server-owns-completion/actual-API-fidelity, UIScrollView-zoom/index-interop/page-prefetch, sandbox-scanning/auth-tables-dropped/referenced-file-removal, ZIP-random-access-LRU/CBR-phase-asymmetry/naturalSort-fidelity)
- [x] `CB8_ANDROID_STUDY_GUIDE.md` — 5 quizzes (14 questions; node-on-device-heals-two-blockers/wrapper-Play-friendly/architecture-derived-plan, persistent-CookieJar/ignoreUnknownKeys/no-completed-field, Telephoto-zoom/bitmap-budget-onTrimMemory, SAF-vs-bookmark/cursor-traversal-perf/WorkManager, RAR5-junrar-gap/filter-by-extension/bundled-7z-sideload)

## Batch 6 — Security, AI, and the rest

- [x] `AUTH_STUDY_GUIDE.md` — 5 quizzes (15 questions; sessions-vs-JWT/cookie-storage/401-vs-403, slow-hash/salt-rainbow/timing-enumeration, JWT-signed-not-encrypted/alg-pinning/HS-vs-RS, OAuth-vs-OIDC/PKCE/access-vs-ID-token, short+refresh-split/rotation-reuse-detection/revocation-cache-invalidation)
- [x] `WEB_LLM_SECURITY_STUDY_GUIDE.md` — 5 quizzes (15 questions; IDOR-data-layer-auth/404-not-403/framework-cant-help, SSRF-CSRF-confused-deputy/metadata-endpoint/header-token-immune, SOP-enables-CSRF-token/CORS-reflection/localStorage-vs-cookie-threat-model, prompt-injection-no-data-channel/indirect-injection/delimiting-insufficient, output-as-untrusted/excessive-agency-blast-radius/shrink-not-stop)
- [x] `KALI_LINUX_STUDY_GUIDE.md` — 5 quizzes (15 questions; purpose-built-distro/enumerate-before-exploit/post-ex-pathfinding, passive-vs-active-recon/subdomain-validation/version-string-hinge, online-vs-offline/hash-identification/reverse-shell-direction, AD-as-graph/Kerberoasting/NTLM-relay, trust-not-verify/ARP-spoof-MITM/verification-not-encryption)
- [x] `AI_AGENTS_STUDY_GUIDE.md` — 5 quizzes (13 questions; workflow-vs-agent-who-controls/start-with-workflows/evaluator-optimizer, agent-loop-primitive/ReAct-is-the-loop/production-guardrails, tool-trust-boundary/descriptions-are-instructions, defense-in-depth-cheapest-first/output-guardrails, multi-agent-only-when-justified/handoffs-are-tools/sequential-pipeline-stable)
- [ ] `LLM_APP_DEV_STUDY_GUIDE.md`
- [ ] `ENTERPRISE_API_STUDY_GUIDE.md`
- [ ] `TESTING_STUDY_GUIDE.md`
- [ ] `BLENDER_STUDY_GUIDE.md`
- [ ] `ESP32_STUDY_GUIDE.md`
- [ ] `RASPBERRY_PI_STUDY_GUIDE.md`

## Bespoke pages (verify only)

- [ ] `build_caddy_html.py` — already has quizzes; verify still renders after
      any shared-CSS/JS changes
- [ ] `build_nginx_html.py` — check whether it has quizzes; if not, add a
      `QUIZZES` dict matching the Caddy pattern

---

65 Markdown guides + 2 bespoke pages. Progress: 59/65 (Batches 1–5 complete).

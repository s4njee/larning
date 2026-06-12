# Guide-Quality Improvement Pass — Progress Note

**Goal:** Using DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md as the style/tone/length reference,
work through `list.md` from the lowest-scoring guide upward, rewriting/expanding each
to prose-first textbook quality, re-scoring it in `list.md`, updating its README entry,
rebuilding the site (`python3 build_all_guides.py`), and committing+pushing. No subagents.

**Branch:** `claude/cb8-ios-study-guide-wej97v`

## Done this pass (lowest → up) — 17 guides; the entire 57–77 band lifted

| Guide | Before | After | What was done |
|---|---|---|---|
| k8s/KUBERNETES_SECURITY | 57 | 84 | Bullet checklist → prose + real manifests, blast-radius framing |
| WEB_LLM_SECURITY | 58 | 84 | Bullet template → full prose treatment per bug class |
| KALI_LINUX | 66 | 82 | Tool catalog → technique-first kill-chain prose |
| AZURE_FOR_AWS | 70 | 80 | Service-name bullets → flowing conceptual exposition (15 sections) |
| GCP_FOR_AWS | 77 | 81 | Same as Azure: service-name bullets → prose (15 sections) |
| k8s/DOCKER_KUBERNETES_NETWORKING | 72 | 79 | Added the stack underneath (veth/NAT/CNI/kube-proxy/CoreDNS) |
| k8s/KUBERNETES | 72 | 78 | Foundational concepts bullets → developed prose |
| POSTGRES | 72 | 77 | Bare catalog → explained reference (teaching section openers) |
| TYPESCRIPT | 74 | 80 | Added the missing tooling/build/ecosystem chapter |
| GIT | 74 | 79 | Back-half command reference → developed why-first prose |
| VIM | 75 | 79 | Developed the quickfix project-refactor workflow |
| REDIS | 75 | 80 | why-it-works (single-thread, skiplist, RDB/AOF, hash slots) |
| PYTHON_VS_NODEJS_ASYNC | 76 | 78 | Free-threaded-Python forward analysis (scope-limited by design) |
| EBPF | 76 | 79 | Verifier (abstract interpretation) + CO-RE (BTF relocation) |
| RASPBERRY_PI | 76 | 79 | I2C/SPI/UART wire-level protocol mechanism prose |
| CADDY | 76 | 79 | Automatic-HTTPS (ACME/CA trust) + reverse-proxy concepts |
| DOTNET_FOR_PYTHON_DEVS | 77 | 79 | LINQ deferred execution + reified generics mechanisms |

## Remaining lowest-scorers (next targets, ascending) — now 77–78, all genuinely decent

- POSTGRES (77) — already deepened this pass; it's a reference by design (depth lives in
  ADVANCED_POSTGRES at 86), so further gains are limited. Could add more section openers.
- DOCKER (78) — "strong under-the-hood framing; more terse-and-practical than expository in
  the middle chapters." Develop the middle-chapter prose (namespaces/cgroups → containerd/runc).
- SQLITE (78) — "genuinely comprehensive; heavily code-driven, explanatory prose secondary."
  Add why-it-works prose (note DATABASE_INTERNALS covers SQLite internals deeply — cross-link,
  don't duplicate).
- SWIFT (78) — "real language treatment; highest code-to-prose ratio." Develop concept prose.
- RUST_FOR_PYTHON_DEVS (78) — "code-heavy with commentary rather than sustained exposition."
- k8s/KUBERNETES (78, deepened), GOLANG_FOR_PYTHON_DEVS (80), then the 80s.

## Method per guide (repeat this)

1. Read the guide + its `list.md` critique (assessment column says exactly what's wrong).
2. Rewrite/expand to address that specific critique, matching DISTRIBUTED_SYSTEMS tone
   (concept-first, grounded, prose-first) and depth. Keep good tables/code/links; convert
   bullet enumerations to flowing prose; add the missing "why"/mechanism.
3. Re-score in `list.md` via the python snippet pattern used in each commit (remove old row,
   insert at correct ascending position, renumber all rows, append to June-2026 header note;
   assert scores monotone + numbering contiguous).
4. Update the README entry; `python3 build_all_guides.py`; commit + push.

Quality bar: DISTRIBUTED_SYSTEMS (88), LINUX_FUNDAMENTALS (92).

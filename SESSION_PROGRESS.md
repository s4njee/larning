# Guide-Quality Improvement Pass — Progress Note

**Goal:** Using DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md as the style/tone/length reference,
work through `list.md` from the lowest-scoring guide upward, rewriting/expanding each
to prose-first textbook quality, re-scoring it in `list.md`, updating its README entry,
rebuilding the site (`python3 build_all_guides.py`), and committing+pushing. No subagents.

**Branch:** `claude/cb8-ios-study-guide-wej97v`

## Status: the entire 57–78 bottom band has been lifted. Worst guide is now 77.

21 guides improved this pass (lowest → up). The repo's lowest score went from **57 → 77**.

| Guide | Before | After |
|---|---|---|
| k8s/KUBERNETES_SECURITY | 57 | 84 |
| WEB_LLM_SECURITY | 58 | 84 |
| KALI_LINUX | 66 | 82 |
| AZURE_FOR_AWS | 70 | 80 |
| GCP_FOR_AWS | 77 | 81 |
| k8s/DOCKER_KUBERNETES_NETWORKING | 72 | 79 |
| k8s/KUBERNETES | 72 | 78 |
| POSTGRES | 72 | 77 |
| TYPESCRIPT | 74 | 80 |
| GIT | 74 | 79 |
| VIM | 75 | 79 |
| REDIS | 75 | 80 |
| PYTHON_VS_NODEJS_ASYNC | 76 | 78 |
| EBPF | 76 | 79 |
| RASPBERRY_PI | 76 | 79 |
| CADDY | 76 | 79 |
| DOTNET_FOR_PYTHON_DEVS | 77 | 79 |
| DOCKER | 78 | 80 |
| SQLITE | 78 | 80 |
| SWIFT | 78 | 80 |
| RUST_FOR_PYTHON_DEVS | 78 | 80 |

Each: critique-targeted rewrite/deepening in the Distributed Systems tone (concept-first,
prose-first, mechanism/"why" added), README entry updated, list.md re-scored + renumbered
(scores monotone, numbering contiguous), site rebuilt, committed + pushed.

## Current bottom of the ranking (next targets if continuing)

1. POSTGRES (77) — reference by design (deep internals in ADVANCED_POSTGRES @86 and
   DATABASE_INTERNALS @91); could add more teaching section-openers but gains are limited.
2. k8s/KUBERNETES (78), PYTHON_VS_NODEJS_ASYNC (78) — both already deepened this pass;
   their ceilings are partly scope (comparison bridge) / breadth.
3. The 79–80 band: the guides deepened above, plus GOLANG_FOR_PYTHON_DEVS (80),
   PYTHON_CONCURRENCY (80), BLENDER (80), DATA_ENGINEERING (80), the WebGL/WebGPU pair (80).
   These are genuinely good; marginal gains are smaller and each needs a specific,
   critique-targeted deepening (see its list.md assessment column).

## Method per guide (repeat this)

1. Read the guide + its `list.md` critique (assessment column = exactly what's wrong).
2. Rewrite/expand to address that critique, matching DISTRIBUTED_SYSTEMS tone and depth.
   Keep good tables/code/links; convert bullet enumerations to prose; add the missing
   "why"/mechanism. Cross-link siblings rather than duplicating (e.g. DATABASE_INTERNALS).
3. Re-score in `list.md` via the python snippet pattern (remove old row, insert at correct
   ascending position, renumber all rows, append to the June-2026 header note; assert
   scores monotone + numbering contiguous).
4. Update README entry; `python3 build_all_guides.py`; commit + push.

Quality bar: DISTRIBUTED_SYSTEMS (88), LINUX_FUNDAMENTALS (92).

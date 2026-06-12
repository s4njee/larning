# Guide-Quality Improvement Pass — Progress Note

**Goal:** Using DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md as the style/tone/length reference,
work through `list.md` from the lowest-scoring guide upward, rewriting/expanding each
to prose-first textbook quality, re-scoring it in `list.md`, updating its README entry,
rebuilding the site (`python3 build_all_guides.py`), and committing+pushing. No subagents.

**Branch:** `claude/cb8-ios-study-guide-wej97v`

## Done this pass (lowest → up) — 15 guides, every one that was ≤76

| Guide | Before | After | What was done |
|---|---|---|---|
| k8s/KUBERNETES_SECURITY | 57 | 84 | Bullet checklist → prose + real manifests, blast-radius framing |
| WEB_LLM_SECURITY | 58 | 84 | Bullet template → full prose treatment per bug class |
| KALI_LINUX | 66 | 82 | Tool catalog → technique-first kill-chain prose |
| AZURE_FOR_AWS | 70 | 80 | Service-name bullets → flowing conceptual exposition (all 15 sections) |
| k8s/DOCKER_KUBERNETES_NETWORKING | 72 | 79 | Added the stack underneath (veth/NAT/CNI/kube-proxy/CoreDNS) |
| k8s/KUBERNETES | 72 | 78 | Foundational concepts bullets → developed prose |
| POSTGRES | 72 | 77 | Bare catalog → explained reference (teaching section openers) |
| TYPESCRIPT | 74 | 80 | Added the missing tooling/build/ecosystem chapter (erasure, @types, Zod) |
| GIT | 74 | 79 | Back-half command reference → developed why-first prose |
| VIM | 75 | 79 | Developed the quickfix project-refactor workflow |
| REDIS | 75 | 80 | Added why-it-works (single-thread, skiplist, RDB/AOF, hash slots) |
| PYTHON_VS_NODEJS_ASYNC | 76 | 78 | Deepened free-threaded-Python forward analysis (scope-limited by design) |
| EBPF | 76 | 79 | Verifier (abstract interpretation) + CO-RE (BTF relocation) mechanisms |
| RASPBERRY_PI | 76 | 79 | I2C/SPI/UART wire-level protocol mechanism prose |
| CADDY | 76 | 79 | Automatic-HTTPS (ACME/CA trust) + reverse-proxy conceptual cores |

The whole 57–76 band is now lifted. New bottom of the ranking starts at 77.

## Remaining lowest-scorers (next targets, ascending) — all 77–78

Check `grep -E '^\| [1-9] \|' list.md` for the live order. As of this note:
- DOTNET_FOR_PYTHON_DEVS (77) — "annotated snippet catalogs"; develop prose around code
- POSTGRES (77, already deepened this pass — could go further but diminishing)
- GCP_FOR_AWS_SOLUTIONS_ARCHITECT (77) — same translation-table issue as Azure was; convert to prose
- DOCKER (78), SQLITE (78), SWIFT (78), RUST_FOR_PYTHON_DEVS (78), KUBERNETES (78, deepened)
- then the 80s (Advanced trilogy, the new textbook guides, etc.)

GCP_FOR_AWS is the highest-leverage next target (the Azure rewrite is a direct template:
its sibling, same per-section service-name-bullets → prose conversion).

## Method per guide (repeat this)

1. Read the guide + its `list.md` critique (the assessment column says exactly what's wrong).
2. Rewrite/expand to address that specific critique, matching DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md
   tone (concept-first, grounded, prose-first) and developed depth. Keep good tables/code/links;
   convert bullet enumerations to flowing prose; add the missing "why" / mechanism.
3. Re-score in `list.md` via the python snippet pattern used in each commit (remove old row,
   insert at correct ascending position, renumber all rows, append to the June-2026 header note;
   assert scores stay monotone and numbering contiguous).
4. Update the README entry to reflect the new depth.
5. `python3 build_all_guides.py`; commit + push to the branch.

Quality bar: DISTRIBUTED_SYSTEMS (88), LINUX_FUNDAMENTALS (92).

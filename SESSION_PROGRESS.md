# Guide-Quality Improvement Pass — Progress Note

**Goal:** Using the Distributed Systems guide as the style/tone/length reference,
work through `list.md` from the lowest-scoring guide upward, rewriting/expanding
each to prose-first textbook quality, re-scoring it in `list.md`, updating its
README entry, rebuilding the site, and committing. No subagents.

**Branch:** `claude/cb8-ios-study-guide-wej97v`

## Done this pass (lowest → up)

| Guide | Before | After | What was done |
|---|---|---|---|
| k8s/KUBERNETES_SECURITY | 57 | 84 | Bullet checklist → prose + real manifests, blast-radius framing |
| WEB_LLM_SECURITY | 58 | 84 | Bullet template → full prose treatment per bug class |
| KALI_LINUX | 66 | 82 | Tool catalog → technique-first kill-chain prose |
| AZURE_FOR_AWS | 70 | 80 | Service-name bullets → flowing conceptual exposition (all 15 sections) |
| k8s/DOCKER_KUBERNETES_NETWORKING | 72 | 79 | Added the networking stack underneath (veth/NAT/CNI/kube-proxy/CoreDNS) |
| k8s/KUBERNETES | 72 | 78 | Foundational concepts bullets → developed prose |
| POSTGRES | 72 | 77 | Bare catalog → explained reference (teaching section openers) |
| TYPESCRIPT | 74 | 80 | Added the missing tooling/build/ecosystem chapter |
| GIT | 74 | 79 | Back-half command reference → developed why-first prose |
| VIM | 75 | 79 | Developed the quickfix project-refactor workflow |
| REDIS | 75 | 80 | Added why-it-works mechanism (single-thread, skiplist, RDB/AOF, hash slots) |

## Remaining low-scorers (next targets, ascending)

Check `grep -E '^\| [1-9] \|' list.md` for the live order. As of this note the
next candidates were around 76–78: PYTHON_VS_NODEJS_ASYNC (76), RASPBERRY_PI (76),
EBPF (76), CADDY (76), CLOUDFLARE (already rewritten earlier), ANSIBLE/CRYPTO/etc (82).

## Method per guide (repeat this)

1. Read the guide + its `list.md` critique (the assessment column says exactly what's wrong).
2. Rewrite/expand to address that specific critique, matching DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md
   in tone (concept-first, grounded, prose-first) and developed depth. Keep good
   tables/code/links; convert bullet enumerations to flowing prose; add the missing "why".
3. Re-score in `list.md`: remove the old row, insert at the right ascending position,
   renumber all rows, append a note to the June-2026 update header line. (A python snippet
   that does this safely is used in each commit; verify scores stay monotone and numbering contiguous.)
4. Update the README entry to reflect the new depth.
5. `python3 build_all_guides.py` to rebuild HTML.
6. Commit + push to the branch.

The Distributed Systems guide (88) and Linux Fundamentals (92) are the quality bar.

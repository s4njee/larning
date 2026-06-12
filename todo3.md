# ToDo 3 — Recommended Reading Sections + Documentation Links

Goal: bring every guide up to the standard set by `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md`
on two specific dimensions, in a single pass per guide:

1. **A recommended-reading section** — every guide ends with a "Where to Go Next"
   (or "Recommended Reading Path") section, and ideally opens with a short
   "Primary references" paragraph in the intro.
2. **Reference links to documentation** — every major tool, API, command, paper,
   or spec the guide leans on links to its official documentation inline, at the
   point where the guide first explains it.

---

## The model (what "like the distributed systems guide" means)

`DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` does three things every guide should do:

- **Intro "Primary references" paragraph** (~line 7): one paragraph naming the
  3–5 canonical sources for the whole topic — the definitive book, the primary
  docs, the landmark paper(s), the best course — each as a markdown link, each
  with a clause on *why* it earns the slot ("the single best book on this
  material", "whose labs are the best way to actually internalize this").
- **Closing "Where to Go Next" section**: a short bulleted list that sequences
  the reader's next steps — read X cover to cover, do the labs/exercises for Y,
  read the source papers/specs while fresh, *run/break one real system deeply*,
  and a final bullet cross-linking the sibling guides in this repo that go
  deeper on a slice. Bullets are bold-led and say why, not just what.
- **Inline documentation links throughout**: when a section explains a concrete
  tool, flag, API, or RFC, the first mention links to the official doc page —
  not a blog post, not a tutorial mirror. (Good existing examples of density
  done right: `POSTGRES_EXTENSIONS.md`, `ADVANCED_RUST_STUDY_GUIDE.md`,
  `QT_STUDY_GUIDE.md`, `SVELTEKIT_STUDY_GUIDE.md`.)

Rules for the pass:

- Link to **official/primary sources**: project docs, language references, RFCs,
  man pages (man7.org), MDN for web platform, original papers. Avoid link rot
  bait (random blogs, Medium) unless the post *is* the canonical source
  (e.g. Kleppmann's Redlock critique).
- Don't pad. The Distributed Systems guide itself has ~15 external links in
  850 lines — what matters is that the *load-bearing* claims and every named
  tool/API are linked, not hitting a links-per-line quota. The "links" counts
  below are a smell test, not a target.
- A guide is **done** when: intro has a Primary-references paragraph, the guide
  ends with a Where-to-Go-Next/Recommended-Reading section (with sibling-guide
  cross-links), and every named tool/spec/API links to official docs on first
  meaningful mention.
- After each batch: rebuild (`python3 build_all_guides.py`), spot-check the
  HTML, update this file's checkboxes, commit.

Legend per guide: `[ ] reading` = add/finish the closing reading section,
`[ ] links` = add inline documentation links. Counts are from the 2026-06-12
audit (external markdown links / total lines).

---

## Tier 1 — Both missing, links critically sparse (≤10 links) — ✅ COMPLETE (2026-06-12)

The worst offenders: no reading section *and* almost no documentation links.

- [x] `ADVANCED_GO_STUDY_GUIDE.md` — [x] reading [x] links (5→36 links; gc-guide, pkg.go.dev, pgo, race detector)
- [x] `ADVANCED_LINUX_STUDY_GUIDE.md` — [x] reading [x] links (4→52 links; docs.kernel.org, man7, Gregg)
- [x] `ADVANCED_NODEJS_STUDY_GUIDE.md` — [x] reading [x] links (5→30 links; nodejs.org, v8.dev, libuv)
- [x] `ADVANCED_PYTHON_STUDY_GUIDE.md` — [x] reading [x] links (7→30 links; docs.python.org, PEPs, profiler docs)
- [x] `AUTH_STUDY_GUIDE.md` — [x] reading [x] links (9→35 links; RFCs, OWASP, NIST, Zanzibar)
- [x] `BLENDER_STUDY_GUIDE.md` — [x] reading [x] links (5→17 links; manual chapters, bpy API)
- [x] `EBPF_STUDY_GUIDE.md` — [x] reading [x] links (4→25 links; kernel BPF docs, project docs)
- [x] `ELECTRON_STUDY_GUIDE.md` — [x] reading [x] links (3→20 links; electronjs.org tutorials/APIs)
- [x] `IOS_DEVELOPMENT_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` — [x] reading [x] links (touched lightly: man7 overview pages + Where to Go Next)
- [x] `LINUX_NETWORKING_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `PYTHON_CONCURRENCY.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `RASPBERRY_PI_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `SWIFT_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `VIM_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `WEBGL_OPENGL_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `WEBGPU_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `ENTERPRISE_API_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `CB8_IOS_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `CB8_ANDROID_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; Where to Go Next added)
- [x] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md` — [x] reading [x] links (API concepts, operator pattern, GitOps engines)

## Tier 2 — Long guides with thin links, no reading section — ✅ COMPLETE (2026-06-12)

Substantial guides where link density lags the length.

- [x] `AI_AGENTS_STUDY_GUIDE.md` — [x] reading [x] links (MCP spec, ReAct/Toolformer, Building Effective Agents)
- [x] `TESTING_STUDY_GUIDE.md` — [x] reading [x] links (pytest/Vitest/Playwright/Hypothesis, Testing Trophy)
- [x] `CPP26_STUDY_GUIDE.md` — [x] reading [x] links (cppreference, wg21.link, Core Guidelines, godbolt)
- [x] `LLM_APP_DEV_STUDY_GUIDE.md` — [x] reading [x] links (provider docs, eval tooling, Building Effective Agents)
- [x] `GIT_STUDY_GUIDE.md` — [x] reading [x] links (Pro Git, command man pages)
- [x] `REDIS_STUDY_GUIDE.md` — [x] reading [x] links (redis.io data types/persistence/replication)
- [x] `TYPESCRIPT_STUDY_GUIDE.md` — [x] reading [x] links (intro refs expanded; per-chapter Handbook links already present)
- [x] `DOCKER_STUDY_GUIDE.md` — [x] reading [x] links (Dockerfile ref, OCI specs, dive)
- [x] `GITHUB_ACTIONS_STUDY_GUIDE.md` — [x] reading [x] links (syntax/contexts refs, hardening guide, zizmor)
- [x] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; kube-bench, checklist)
- [x] `WEB_LLM_SECURITY_STUDY_GUIDE.md` — [x] reading [x] links (intro refs were strong; PortSwigger, GenAI project)

## Tier 3 — Decent links already, just missing the reading section — ✅ COMPLETE (2026-06-12)

These mostly need the closing section + intro references paragraph; links are
already reasonable (verify coverage of first-mentions while in the file).

- [x] `ADVANCED_RUST_STUDY_GUIDE.md` — [x] already had Study Methodology + Additional Reference Links (audit regex miss)
- [x] `ASYNCIO_STUDY_GUIDE.md` — [x] reading + intro refs added
- [x] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` — [x] reading [x] intro refs
- [x] `CADDY_STUDY_GUIDE.md` — [x] reading [x] intro refs
- [x] `CLOUDFLARE_STUDY_GUIDE.md` — [x] reading [x] intro refs
- [x] `DJANGO_STUDY_GUIDE.md` — [x] already had 'Where to Go From Here' ecosystem section (audit regex miss)
- [x] `DOTNET_FOR_PYTHON_DEVS.md` — [x] reading [x] intro refs
- [x] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md` — [x] reading [x] intro refs
- [x] `GOLANG_FOR_PYTHON_DEVS.md` — [x] reading [x] intro refs
- [x] `KALI_LINUX_STUDY_GUIDE.md` — [x] reading added (HTB/THM/PortSwigger, HackTricks)
- [x] `NEXTJS_STUDY_GUIDE.md` — [x] already had 'Where to Go from Here' (audit regex miss)
- [x] `RUST_FOR_PYTHON_DEVS.md` — [x] reading [x] intro refs
- [x] `VUE_STUDY_GUIDE.md` — [x] reading added
- [x] `WEBSOCKETS_STUDY_GUIDE.md` — [x] reading [x] intro refs
- [x] `TERRAFORM_STUDY_GUIDE.md` — [x] reading added
- [x] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` — [x] reading [x] intro refs

## Tier 4 — Has a reading section; verify it matches the model + fix links

These already end with Further Reading / Where to Go Next / Recommended Reading
Path. Verify the section has real links (not bare titles), add the
sibling-guide cross-link bullet if missing, and fix inline link gaps.

- [ ] `ADVANCED_POSTGRES.md` (≈1 bare URL / 964 ln!) — [ ] links badly needed (postgresql.org/docs per feature) [ ] upgrade Further Reading to linked entries
- [ ] `POSTGRES.md` (≈3 bare URLs / 1887 ln!) — [ ] links badly needed [ ] upgrade Next Steps & Further Reading
- [ ] `SQLITE_STUDY_GUIDE.md` (13 / 2290) — [ ] links thin for the length (sqlite.org docs per pragma/feature) [x] reading section exists
- [ ] `ANSIBLE_STUDY_GUIDE.md` (54 / 2247) — [ ] verify section + first-mention links
- [ ] `CRYPTO_FUNDAMENTALS.md` (73 / 1296) — [ ] verify section + links
- [ ] `DATA_ENGINEERING_STUDY_GUIDE.md` (50 / 1185) — [ ] verify section + links
- [ ] `ESP32_STUDY_GUIDE.md` (6 / 856) — [ ] links badly needed (Espressif ESP-IDF/Arduino docs) [x] Going Further exists
- [ ] `NETWORKING_FUNDAMENTALS.md` (43 / 1581) — [ ] verify section + links (RFC links per protocol)
- [ ] `OBSERVABILITY_STUDY_GUIDE.md` (68 / 1870) — [ ] verify section + links
- [ ] `QT_STUDY_GUIDE.md` (141 / 1401) — [ ] verify section (likely done)
- [ ] `SVELTEKIT_STUDY_GUIDE.md` (143 / 1404) — [ ] verify section (likely done)
- [ ] `COMPILER_INTERNALS_STUDY_GUIDE.md` (20 / 696) — [ ] verify (has Where to Go Next + intro refs)
- [ ] `DATABASE_INTERNALS_STUDY_GUIDE.md` (18 / 651) — [ ] verify (has Where to Go Next + intro refs)
- [ ] `DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md` (15 / 716) — [ ] verify (has Where to go next + intro refs)
- [ ] `POSTGRES_EXTENSIONS.md` (161 / 494) — [ ] verify Further Reading format (links already dense)
- [ ] `k8s/KUBERNETES_STUDY_GUIDE.md` (65 / 1199) — [ ] verify section + links
- [x] `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` — the reference; no work needed

---

## Working method (per guide)

1. Read the guide end to end; note every named tool/command/API/spec without a link.
2. Add inline links to official docs at first meaningful mention (don't link
   every repetition).
3. Write/upgrade the intro "Primary references" paragraph: 3–5 canonical
   sources with a why-clause each.
4. Write/upgrade the closing "Where to Go Next": book → exercise/lab → primary
   papers/specs → run-and-break-something → sibling guides in this repo.
5. Rebuild HTML, spot-check rendered links, tick the boxes here, commit the batch.

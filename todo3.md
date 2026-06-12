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

## Tier 1 — Both missing, links critically sparse (≤10 links)

The worst offenders: no reading section *and* almost no documentation links.

- [ ] `ADVANCED_GO_STUDY_GUIDE.md` (5 links / 916 ln) — [ ] reading [ ] links (go.dev/ref, pkg.go.dev, Go blog for GC/sched design docs)
- [ ] `ADVANCED_LINUX_STUDY_GUIDE.md` (4 / 1895) — [ ] reading [ ] links (man7.org, kernel.org docs)
- [ ] `ADVANCED_NODEJS_STUDY_GUIDE.md` (5 / 1224) — [ ] reading [ ] links (nodejs.org/api, V8 blog)
- [ ] `ADVANCED_PYTHON_STUDY_GUIDE.md` (7 / 1294) — [ ] reading [ ] links (docs.python.org, PEPs)
- [ ] `AUTH_STUDY_GUIDE.md` (9 / 752) — [ ] reading [ ] links (RFC 6749/6750/7519, OWASP, oauth.net)
- [ ] `BLENDER_STUDY_GUIDE.md` (5 / 1275) — [ ] reading [ ] links (docs.blender.org manual + Python API)
- [ ] `EBPF_STUDY_GUIDE.md` (4 / 1229) — [ ] reading [ ] links (ebpf.io, kernel BPF docs, libbpf, bcc)
- [ ] `ELECTRON_STUDY_GUIDE.md` (3 / 882) — [ ] reading [ ] links (electronjs.org/docs)
- [ ] `IOS_DEVELOPMENT_STUDY_GUIDE.md` (6 / 1851) — [ ] reading [ ] links (developer.apple.com: Swift, SwiftUI, HIG)
- [ ] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` (4 / 703) — [ ] reading [ ] links (man7.org; note: this is the repo's 92-scoring quality reference — touch lightly)
- [ ] `LINUX_NETWORKING_STUDY_GUIDE.md` (8 / 1700) — [ ] reading [ ] links (man7.org ip/ss/nft, kernel networking docs)
- [ ] `PYTHON_CONCURRENCY.md` (7 / 763) — [ ] reading [ ] links (docs.python.org threading/multiprocessing/asyncio, PEP 703)
- [ ] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` (6 / 813) — [ ] reading [ ] links (asyncio docs, Node event-loop docs)
- [ ] `RASPBERRY_PI_STUDY_GUIDE.md` (4 / 1815) — [ ] reading [ ] links (raspberrypi.com/documentation, gpiozero)
- [ ] `SWIFT_STUDY_GUIDE.md` (4 / 2197) — [ ] reading [ ] links (docs.swift.org TSPL, Swift Evolution)
- [ ] `VIM_STUDY_GUIDE.md` (3 / 983) — [ ] reading [ ] links (vimhelp.org, neovim docs)
- [ ] `WEBGL_OPENGL_STUDY_GUIDE.md` (9 / 2021) — [ ] reading [ ] links (MDN WebGL, Khronos refs, webgl2fundamentals)
- [ ] `WEBGPU_STUDY_GUIDE.md` (9 / 2073) — [ ] reading [ ] links (W3C WebGPU/WGSL specs, MDN, webgpufundamentals)
- [ ] `ENTERPRISE_API_STUDY_GUIDE.md` (7 / 531) — [ ] reading [ ] links (RFC 9110/9457, OpenAPI spec, Stripe/idempotency docs)
- [ ] `CB8_IOS_STUDY_GUIDE.md` (12 / 1149) — [ ] reading [ ] links (Apple docs for WKWebView/Capacitor equivalents)
- [ ] `CB8_ANDROID_STUDY_GUIDE.md` (11 / 820) — [ ] reading [ ] links (developer.android.com WebView/Compose)
- [ ] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md` (7 / 662) — [ ] reading [ ] links (kubernetes.io API reference, controller-runtime)

## Tier 2 — Long guides with thin links, no reading section

Substantial guides where link density lags the length.

- [ ] `AI_AGENTS_STUDY_GUIDE.md` (12 / 2781) — [ ] reading [ ] links (provider API docs, MCP spec, ReAct/Toolformer papers)
- [ ] `TESTING_STUDY_GUIDE.md` (17 / 2886) — [ ] reading [ ] links (pytest/Jest/Playwright/Hypothesis docs)
- [ ] `CPP26_STUDY_GUIDE.md` (14 / 1733) — [ ] reading [ ] links (cppreference, wg21 papers by P-number)
- [ ] `LLM_APP_DEV_STUDY_GUIDE.md` (18 / 1760) — [ ] reading [ ] links (Anthropic/OpenAI docs, tokenizer/eval tool docs)
- [ ] `GIT_STUDY_GUIDE.md` (24 / 1854) — [ ] reading [ ] links (git-scm.com book + man pages)
- [ ] `REDIS_STUDY_GUIDE.md` (28 / 1904) — [ ] reading [ ] links (redis.io commands + docs)
- [ ] `TYPESCRIPT_STUDY_GUIDE.md` (25 / 1809) — [ ] reading [ ] links (typescriptlang.org handbook + release notes)
- [ ] `DOCKER_STUDY_GUIDE.md` (34 / 1669) — [ ] reading [ ] links (docs.docker.com, OCI specs)
- [ ] `GITHUB_ACTIONS_STUDY_GUIDE.md` (37 / 1479) — [ ] reading [ ] links (docs.github.com/actions)
- [ ] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md` (11 / 513) — [ ] reading [ ] links (kubernetes.io security docs, Pod Security Standards)
- [ ] `WEB_LLM_SECURITY_STUDY_GUIDE.md` (13 / 479) — [ ] reading [ ] links (OWASP LLM Top 10, prompt-injection papers)

## Tier 3 — Decent links already, just missing the reading section

These mostly need the closing section + intro references paragraph; links are
already reasonable (verify coverage of first-mentions while in the file).

- [ ] `ADVANCED_RUST_STUDY_GUIDE.md` (138 / 885) — [ ] reading
- [ ] `ASYNCIO_STUDY_GUIDE.md` (52 / 1439) — [ ] reading
- [ ] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` (70 / 902) — [ ] reading [ ] intro refs
- [ ] `CADDY_STUDY_GUIDE.md` (91 / 2592) — [ ] reading [ ] intro refs
- [ ] `CLOUDFLARE_STUDY_GUIDE.md` (64 / 992) — [ ] reading [ ] intro refs
- [ ] `DJANGO_STUDY_GUIDE.md` (180 / 1804) — [ ] reading
- [ ] `DOTNET_FOR_PYTHON_DEVS.md` (51 / 1865) — [ ] reading [ ] intro refs
- [ ] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md` (54 / 916) — [ ] reading [ ] intro refs
- [ ] `GOLANG_FOR_PYTHON_DEVS.md` (102 / 1568) — [ ] reading [ ] intro refs
- [ ] `KALI_LINUX_STUDY_GUIDE.md` (81 / 401) — [ ] reading
- [ ] `NEXTJS_STUDY_GUIDE.md` (128 / 1401) — [ ] reading
- [ ] `RUST_FOR_PYTHON_DEVS.md` (53 / 2346) — [ ] reading [ ] intro refs
- [ ] `VUE_STUDY_GUIDE.md` (151 / 1601) — [ ] reading
- [ ] `WEBSOCKETS_STUDY_GUIDE.md` (49 / 1843) — [ ] reading [ ] intro refs
- [ ] `TERRAFORM_STUDY_GUIDE.md` (87 / 1502) — [ ] reading
- [ ] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` (90 / 1210) — [ ] reading [ ] intro refs

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

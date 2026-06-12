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

## Batch 1 — Pilot + flagship guides (biggest, most-read; prove the pattern)

- [x] `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` — the pilot; 10 parts × 4–5 Q
      (48 questions), one quiz per Part after its closing paragraph
- [x] `ADVANCED_LINUX_STUDY_GUIDE.md` — 10 parts × 4–5 Q (48 questions)
- [x] `ADVANCED_GO_STUDY_GUIDE.md` — 10 parts × 4–5 Q (43 questions)
- [ ] `ADVANCED_NODEJS_STUDY_GUIDE.md`
- [ ] `ADVANCED_PYTHON_STUDY_GUIDE.md`
- [ ] `ADVANCED_RUST_STUDY_GUIDE.md`
- [ ] `ADVANCED_POSTGRES.md`
- [ ] `POSTGRES.md`

## Batch 2 — Systems, databases, networking

- [ ] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md`
- [ ] `LINUX_NETWORKING_STUDY_GUIDE.md`
- [ ] `EBPF_STUDY_GUIDE.md`
- [ ] `NETWORKING_FUNDAMENTALS.md`
- [ ] `DATABASE_INTERNALS_STUDY_GUIDE.md`
- [ ] `SQLITE_STUDY_GUIDE.md`
- [ ] `REDIS_STUDY_GUIDE.md`
- [ ] `POSTGRES_EXTENSIONS.md`
- [ ] `DATA_ENGINEERING_STUDY_GUIDE.md`
- [ ] `DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md`
- [ ] `COMPILER_INTERNALS_STUDY_GUIDE.md`
- [ ] `CRYPTO_FUNDAMENTALS.md`

## Batch 3 — Infra, cloud, and ops

- [ ] `k8s/KUBERNETES_STUDY_GUIDE.md`
- [ ] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md`
- [ ] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md`
- [ ] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md`
- [ ] `DOCKER_STUDY_GUIDE.md`
- [ ] `TERRAFORM_STUDY_GUIDE.md`
- [ ] `ANSIBLE_STUDY_GUIDE.md`
- [ ] `GITHUB_ACTIONS_STUDY_GUIDE.md`
- [ ] `OBSERVABILITY_STUDY_GUIDE.md`
- [ ] `CLOUDFLARE_STUDY_GUIDE.md`
- [ ] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md`
- [ ] `GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md`
- [ ] `GIT_STUDY_GUIDE.md`
- [ ] `VIM_STUDY_GUIDE.md`

## Batch 4 — Languages and runtimes

- [ ] `TYPESCRIPT_STUDY_GUIDE.md`
- [ ] `CPP26_STUDY_GUIDE.md`
- [ ] `SWIFT_STUDY_GUIDE.md`
- [ ] `ASYNCIO_STUDY_GUIDE.md`
- [ ] `PYTHON_CONCURRENCY.md`
- [ ] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md`
- [ ] `GOLANG_FOR_PYTHON_DEVS.md`
- [ ] `RUST_FOR_PYTHON_DEVS.md`
- [ ] `DOTNET_FOR_PYTHON_DEVS.md`

## Batch 5 — Web, frontend, and apps

- [ ] `NEXTJS_STUDY_GUIDE.md`
- [ ] `VUE_STUDY_GUIDE.md`
- [ ] `SVELTEKIT_STUDY_GUIDE.md`
- [ ] `DJANGO_STUDY_GUIDE.md`
- [ ] `ELECTRON_STUDY_GUIDE.md`
- [ ] `QT_STUDY_GUIDE.md`
- [ ] `WEBSOCKETS_STUDY_GUIDE.md`
- [ ] `WEBGL_OPENGL_STUDY_GUIDE.md`
- [ ] `WEBGPU_STUDY_GUIDE.md`
- [ ] `IOS_DEVELOPMENT_STUDY_GUIDE.md`
- [ ] `CB8_IOS_STUDY_GUIDE.md`
- [ ] `CB8_ANDROID_STUDY_GUIDE.md`

## Batch 6 — Security, AI, and the rest

- [ ] `AUTH_STUDY_GUIDE.md`
- [ ] `WEB_LLM_SECURITY_STUDY_GUIDE.md`
- [ ] `KALI_LINUX_STUDY_GUIDE.md`
- [ ] `AI_AGENTS_STUDY_GUIDE.md`
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

65 Markdown guides + 2 bespoke pages. Progress: 3/65.

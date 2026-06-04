# ToDo — Convert each study guide `.md` → interactive `.html`

Goal: render every study guide as a single self-contained, responsive, black-themed
interactive HTML page in the **same style** as `html/caddy-study-guide.html` and
`html/nginx-study-guide.html`.

> Completed as a verified batch. Checkmarks below mean the page was rebuilt into
> `html/`, structurally scanned, and its embedded JavaScript passed `node --check`.

---

## The style (what "this style" means)

Each page is **one self-contained `.html` file** (CSS + JS inlined, no network deps) with:

- Sticky **sidebar TOC** with scroll-spy active highlighting
- **Reading-progress bar**, **back-to-top** button
- **Live search** (filters the TOC + highlights matches in the body)
- **Collapsible parts** (click an `h2` to fold its section)
- **Theme toggle** (black default ⇄ light, persisted in `localStorage`); `/` focuses search, `t` toggles theme
- Per-code-block **copy buttons + language badges**
- Lightweight **syntax highlighting** (Caddyfile, nginx, bash, json, yaml, ini, dockerfile, …)
- Responsive layout (sidebar collapses to an off-canvas drawer on mobile)

Optional per-guide extras (nice-to-have, not required for a baseline conversion):

- **Per-part self-check quizzes**
- A **decision helper** widget (e.g. "Should you use X?")

The shared CSS + JS already live in `build_caddy_html.py` (constants `CSS` and `JS`).
`build_nginx_html.py` reuses them via `from build_caddy_html import CSS, JS`.

---

## Recommended first step — generalize the builder

The two existing builders are bespoke (hardcoded content, quizzes, branding). Before
converting 40+ guides by hand, write one reusable script so each conversion is a one-liner.

- [x] **Create `build_guide.py`** — a generic converter. DONE.
  - Usage: `python3 build_guide.py <input.md> [--title "…"] [--brand X] [--accent "#hex"] [--accent2 "#hex"] [--out PATH]`
  - Reuses `CSS` + `JS` from `build_caddy_html.py`.
  - Derives the page title + brand letter from the markdown `# H1` if not passed.
  - Reuses the existing transform (markdown → HTML with `fenced_code, tables, toc, attr_list, sane_lists`,
    code-language normalization, sidebar TOC from `h2/h3`, page template).
  - Quizzes / decision helper are **off** (those stay bespoke per-guide in their own builders).
  - Output filename: lowercase basename, `_`→`-`, `.md`→`.html`; this repo now uses
    `--out html/<name>.html` so generated pages are collected under `html/`.
  - `--accent` retints both dark + light theme accent variables (and derives `--accent-weak` from it).
  - Smoke-tested on Rust (`--accent "#f74c00"`), k8s (`--accent "#326ce5" --brand K8s`), and TypeScript
    (auto title/brand): all build clean, no placeholder leftovers, embedded JS passes `node --check`.

Each item below can be rebuilt individually with `python3 build_guide.py <FILE>.md --out html/<name>.html [--accent ...]`.
For the whole set, use:

```bash
python3 build_all_guides.py
```

Suggested per-guide accents (optional):

| Guide group | Accent |
|-------------|--------|
| Rust | `#f74c00` |
| Go (Advanced Go, Golang for Python Devs) | `#00add8` |
| TypeScript | `#3178c6` |
| Python guides | `#ffd43b` |
| Kubernetes (`k8s/*`) | `#326ce5` |
| Docker | `#2496ed` |
| Vue | `#42b883` |
| Postgres | `#336791` |
| Redis | `#ff4438` |
| (anything else) | omit `--accent` for the default teal |

Per-guide verification checklist (do this for each before checking it off):
1. `python3 build_guide.py <file>.md` builds with no errors.
2. Open the HTML — TOC, search, theme toggle, copy buttons, collapsible sections work.
3. Spot-check syntax highlighting on the dominant language for that guide.
4. No leftover `__CSS__/__JS__/__TOC__/__BODY__` placeholders; embedded JS passes `node --check`.

---

## Conversion checklist (one `.html` per `.md`)

Naming convention: `SOME_GUIDE.md` → `html/some-guide.html` (lowercase, hyphenated).

### Already done
- [x] `CADDY_STUDY_GUIDE.md` → `html/caddy-study-guide.html`  *(built from the .md via `build_caddy_html.py`)*
- [x] *Nginx* → `html/nginx-study-guide.html`  *(authored HTML-only via `build_nginx_html.py`; no `.md` source)*

### Languages & runtimes
- [x] `ADVANCED_GO_STUDY_GUIDE.md` → `advanced-go-study-guide.html`
- [x] `ADVANCED_NODEJS_STUDY_GUIDE.md` → `advanced-nodejs-study-guide.html`
- [x] `ADVANCED_PYTHON_STUDY_GUIDE.md` → `advanced-python-study-guide.html`
- [x] `ASYNCIO_STUDY_GUIDE.md` → `asyncio-study-guide.html`
- [x] `CPP26_STUDY_GUIDE.md` → `cpp26-study-guide.html`
- [x] `DOTNET_FOR_PYTHON_DEVS.md` → `dotnet-for-python-devs.html`
- [x] `GOLANG_FOR_PYTHON_DEVS.md` → `golang-for-python-devs.html`
- [x] `PYTHON_CONCURRENCY.md` → `python-concurrency.html`
- [x] `PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md` → `python-vs-nodejs-async-study-guide.html`
- [x] `RUST_FOR_PYTHON_DEVS.md` → `rust-for-python-devs.html`
- [x] `TYPESCRIPT_STUDY_GUIDE.md` → `typescript-study-guide.html`

### Web & frontend frameworks
- [x] `DJANGO_STUDY_GUIDE.md` → `django-study-guide.html`
- [x] `ELECTRON_STUDY_GUIDE.md` → `electron-study-guide.html`
- [x] `NEXTJS_STUDY_GUIDE.md` → `nextjs-study-guide.html`
- [x] `QT_STUDY_GUIDE.md` → `qt-study-guide.html`
- [x] `SVELTEKIT_STUDY_GUIDE.md` → `sveltekit-study-guide.html`
- [x] `VUE_STUDY_GUIDE.md` → `vue-study-guide.html`
- [x] `WEBSOCKETS_STUDY_GUIDE.md` → `websockets-study-guide.html`

### Infra, cloud & ops
- [x] `ANSIBLE_STUDY_GUIDE.md` → `ansible-study-guide.html`
- [x] `AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md` → `azure-for-aws-solutions-architect.html`
- [x] `CLOUDFLARE_STUDY_GUIDE.md` → `cloudflare-study-guide.html`
- [x] `DOCKER_STUDY_GUIDE.md` → `docker-study-guide.html`
- [x] `GITHUB_ACTIONS_STUDY_GUIDE.md` → `github-actions-study-guide.html`
- [x] `OBSERVABILITY_STUDY_GUIDE.md` → `observability-study-guide.html`
- [x] `TERRAFORM_STUDY_GUIDE.md` → `terraform-study-guide.html`
- [x] `EBPF_STUDY_GUIDE.md` → `ebpf-study-guide.html`
- [x] `k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md` → `html/advanced-kubernetes-study-guide.html`
- [x] `k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md` → `html/docker-kubernetes-networking-study-guide.html`
- [x] `k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md` → `html/kubernetes-security-study-guide.html`
- [x] `k8s/KUBERNETES_STUDY_GUIDE.md` → `html/kubernetes-study-guide.html`

### Systems, OS & hardware
- [x] `ADVANCED_LINUX_STUDY_GUIDE.md` → `advanced-linux-study-guide.html`
- [x] `LINUX_FUNDAMENTALS_STUDY_GUIDE.md` → `linux-fundamentals-study-guide.html`
- [x] `ESP32_STUDY_GUIDE.md` → `esp32-study-guide.html`
- [x] `GIT_STUDY_GUIDE.md` → `git-study-guide.html`
- [x] `VIM_STUDY_GUIDE.md` → `vim-study-guide.html`

### Data & messaging
- [x] `DATA_ENGINEERING_STUDY_GUIDE.md` → `data-engineering-study-guide.html`
- [x] `POSTGRES.md` → `postgres.html`
- [x] `ADVANCED_POSTGRES.md` → `advanced-postgres.html`  *(POSTGRES_STUDY_GUIDE.md was consolidated into the POSTGRES.md + ADVANCED_POSTGRES.md pair)*
- [x] `REDIS_STUDY_GUIDE.md` → `redis-study-guide.html`
- [x] `SQLITE_STUDY_GUIDE.md` → `sqlite-study-guide.html`

### Architecture, security & AI
- [x] `AI_AGENTS_STUDY_GUIDE.md` → `ai-agents-study-guide.html`
- [x] `AUTH_STUDY_GUIDE.md` → `auth-study-guide.html`
- [x] `CRYPTO_FUNDAMENTALS.md` → `crypto-fundamentals.html`
- [x] `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` → `distributed-systems-study-guide.html`
- [x] `KALI_LINUX_STUDY_GUIDE.md` → `kali-linux-study-guide.html`
- [x] `LLM_APP_DEV_STUDY_GUIDE.md` → `llm-app-dev-study-guide.html`
- [x] `NETWORKING_FUNDAMENTALS.md` → `networking-fundamentals.html`

---

## Excluded (not study guides)

- [x] `README.md` — generated as `html/readme.html`.
- [x] `TOPICS.md` — generated as `html/topics.html`.
- [x] `ToDo.md` — generated as `html/todo.html`.
- [x] Local generated index — `html/index.html` links every generated page.

---

## Open decisions (resolve before/while converting)

- [x] **Output location** — collect generated pages under `html/`.
- [x] **Per-guide accent color** — use topic accents where listed and deterministic `--auto-accent` for the rest.
- [x] **Quizzes/decision helper** — keep baseline generic conversions; preserve bespoke quizzes/helpers for Caddy and Nginx.
- [x] **Index page** — generate `html/index.html` linking all pages.
- [x] **Commit cadence** — batch the verified conversion set.

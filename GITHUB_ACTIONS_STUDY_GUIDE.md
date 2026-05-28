# GitHub Actions Study Guide

A practical, depth-first guide to GitHub Actions for engineers building real CI/CD. It assumes you know Git and the rough shape of software delivery, but not that you've built a non-trivial pipeline. The approach is pattern-first: examples are chosen to show each feature cleanly, drawing from Node, Python, Go, and Rust as convenient, rather than carrying one app through the whole guide. It starts with the mental model, builds up through the workflow language and composition, then goes deep on the things that actually bite in production — security, custom actions, deployment, and scale — and closes with copy-paste recipes and a full end-to-end pipeline.

Primary references: [GitHub Actions documentation](https://docs.github.com/en/actions), [Workflow syntax reference](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions), [Contexts reference](https://docs.github.com/en/actions/learn-github-actions/contexts), [Security hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions).

---

## Table of Contents

1. [Part 1 — Foundations & Mental Model](#part-1--foundations--mental-model)
2. [Part 2 — The Workflow Language](#part-2--the-workflow-language)
3. [Part 3 — Build, Test, Cache, Artifacts](#part-3--build-test-cache-artifacts)
4. [Part 4 — Composition & Reuse](#part-4--composition--reuse)
5. [Part 5 — Writing Custom Actions](#part-5--writing-custom-actions)
6. [Part 6 — Deployment & Release Automation](#part-6--deployment--release-automation)
7. [Part 7 — Security Hardening](#part-7--security-hardening)
8. [Part 8 — Operations at Scale](#part-8--operations-at-scale)
9. [Part 9 — Comparison to Alternatives](#part-9--comparison-to-alternatives)
10. [Part 10 — Recipes & End-to-End Walkthrough](#part-10--recipes--end-to-end-walkthrough)

---

## Part 1 — Foundations & Mental Model

Before any YAML, get the model right. Almost every confusing thing about Actions later — why a file change didn't carry between jobs, why a secret was empty, why a deploy ran twice — traces back to a misunderstanding of what runs where and what survives.

### What CI/CD Actually Buys You

Three terms get used loosely. They form a ladder:

- **Continuous Integration (CI):** every push is automatically built and tested. The point is the *feedback loop* — integration problems surface in minutes, on the commit that caused them, instead of during a painful big-bang merge weeks later. CI is also a *gate*: you can require that checks pass before code merges.
- **Continuous Delivery (CD):** every change that passes CI is *provably releasable* — built, tested, and packaged into an artifact you could ship. Releasing is then a deliberate button press.
- **Continuous Deployment (CD):** that release happens *automatically* with no human gate. Same acronym, stronger claim.

The product of all this isn't "automation" for its own sake. It's three things: a fast feedback loop, repeatability (the build runs the same way every time, not "works on my machine"), and an enforceable quality gate. Keep those in mind — every feature in this guide serves one of them.

### Where GitHub Actions Fits

[GitHub Actions](https://docs.github.com/en/actions/about-github-actions/understanding-github-actions) is CI/CD built directly into GitHub and triggered by repository events (a push, a pull request, a release, a schedule). Workflows live as YAML files *in the repository*, versioned alongside the code they build.

That last point is most of its appeal: there's no separate CI server to provision, the pipeline is reviewed in the same pull request as the code, and there's a large [Marketplace](https://github.com/marketplace?type=actions) of reusable building blocks ("actions") so you rarely script common tasks from scratch. The trade-offs against Jenkins, GitLab CI, CircleCI, and others are real and covered honestly in [Part 9](#part-9--comparison-to-alternatives); for now it's enough to know Actions is event-driven, repo-native, and composition-heavy.

### The Execution Model

This is the spine of everything. Five nouns, in a hierarchy:

**events → workflows → jobs → steps → runners**

- An **event** is something that happens in (or to) the repo: a `push`, a `pull_request`, a `schedule` firing, a manual trigger. Events start workflows.
- A **workflow** is a single YAML file under `.github/workflows/`. It declares which events trigger it and what to do. A repo can have many workflows; they're independent.
- A **job** is a set of steps that runs on one **runner**. By default, jobs in a workflow run **in parallel**. You sequence them explicitly with `needs`.
- A **step** is one unit of work inside a job: either a shell command (`run:`) or a call to a reusable action (`uses:`). Steps in a job execute **in order**, top to bottom.
- A **runner** is the machine that executes a job — a GitHub-hosted virtual machine (a fresh one per job) or a self-hosted machine you manage (see [Part 8](#part-8--operations-at-scale)).

Two consequences fall out of this model, and they explain most early confusion:

1. **Each job gets a clean, ephemeral runner.** Nothing you write to disk in job A is visible to job B — different machines, wiped after use. To move data between jobs you must use **artifacts** or **job outputs** (Part 3), and to speed up repeated work you use **caching** (Part 3).
2. **Steps within a job share one runner.** They see the same filesystem, the same checked-out code, the same installed tools, and run sequentially. State *does* persist step-to-step within a job.

### Repository Layout

Workflows go in one place:

```text
.github/
└── workflows/
    ├── ci.yml          # one workflow
    ├── deploy.yml      # another, fully independent
    └── nightly.yml     # another
```

The **filename is arbitrary** — Actions reads every `*.yml`/`*.yaml` file in that directory. What identifies a workflow in the UI is its `name:` field, not the filename. (Custom *actions* you author live elsewhere, e.g. `.github/actions/` — that's [Part 5](#part-5--writing-custom-actions).)

### Your First Workflow, Dissected

Here is a complete, valid workflow. Every line is load-bearing:

```yaml
# .github/workflows/hello.yml
name: CI                          # label shown in the repo's Actions tab
on: [push]                        # event(s) that trigger this workflow — here, any push
jobs:                             # one or more jobs; this workflow has one
  build:                          # the job's id (arbitrary, must be unique in the file)
    runs-on: ubuntu-latest        # which runner image to use (a fresh GitHub-hosted VM)
    steps:                        # the ordered list of work
      - uses: actions/checkout@v4 # an action: clones your repo onto the runner
      - run: echo "Building ${{ github.sha }}"  # a shell step; ${{ }} is an expression
```

Reading it top to bottom:

- `name:` is cosmetic — it's the title you see in the Actions UI.
- `on: [push]` says "run this whenever someone pushes commits." (Triggers get much richer in [Part 2](#part-2--the-workflow-language).)
- `jobs:` holds a map of jobs keyed by id. `build` is the id; you'd reference it elsewhere as `build`.
- `runs-on:` picks the runner. `ubuntu-latest` is a GitHub-hosted Linux VM, provisioned fresh for this job and destroyed afterward.
- `steps:` run in order. The first, [`actions/checkout`](https://github.com/actions/checkout), is critical and easy to forget: **the runner does not have your code until you check it out.** A brand-new VM starts empty.
- The second step runs a shell command. `${{ github.sha }}` is an *expression* that interpolates the commit SHA from the `github` context (Part 2).

If you remember one thing from Part 1: the runner starts empty and disappears when the job ends. Everything else is detail on top of that.

### A Note on Pinning

Throughout the early chapters you'll see actions referenced by a version tag, like `actions/checkout@v4`, because it reads cleanly while you're learning. In production you should pin third-party actions to a full commit SHA instead — tags are mutable and that has real security consequences. [Part 7](#part-7--security-hardening) explains exactly why and how; until then, the `@v4` style keeps examples readable.

---

## Part 2 — The Workflow Language

Part 1 gave you the model; this is the vocabulary. Nearly everything in a workflow file answers one of four questions: *when* it runs (`on:`), *where and in what order* (`jobs`, `runs-on`, `needs`), *what data is available* (contexts and expressions), and *what environment* the steps run in (env, shell, permissions).

### Triggers: the `on:` Key

`on:` declares the events that start the workflow. The [full event list](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows) is long; these are the ones you'll actually reach for.

**Push and pull request, with filters** — the two workhorses:

```yaml
on:
  push:
    branches: [main, 'release/**']    # only pushes to these branches (glob patterns allowed)
    paths: ['src/**', 'package.json']  # ...and only when these files changed
  pull_request:
    branches: [main]                   # PRs *targeting* main
    types: [opened, synchronize, reopened]  # which PR activities (these three are the default)
```

- `branches`/`branches-ignore` and `paths`/`paths-ignore` filter *which* pushes and PRs count. Use one side of each pair, not both.
- `paths` filtering is how you avoid running the whole pipeline when only docs changed.
- For `pull_request`, the activity `types` narrow the trigger — `synchronize` means "new commits were pushed to the PR." It has a security-critical sibling, `pull_request_target`, deliberately held back to [Part 7](#part-7--security-hardening).

**Scheduled runs (cron):**

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'   # 06:00 UTC every Monday — fields: minute hour day-of-month month day-of-week
```

Cron is the standard five fields and is **always in UTC**. Scheduled workflows run against the **default branch's** copy of the file. GitHub may delay scheduled runs under load, so don't depend on exact timing.

**Manual triggers with typed inputs:**

```yaml
on:
  workflow_dispatch:          # adds a "Run workflow" button in the UI and enables `gh workflow run`
    inputs:
      environment:
        description: 'Target environment'
        type: choice          # one of: string | boolean | choice | environment | number
        options: [staging, production]
        default: staging
        required: true
```

Read these through the `inputs` context: `${{ inputs.environment }}`. This is the clean way to make a workflow parameterized and human-triggered — a manual deploy, a one-off backfill.

**Also worth knowing:** `workflow_run` (start a workflow when *another named workflow* finishes — handy for splitting build from deploy) and `repository_dispatch` (trigger via an authenticated API call from an external system).

### Jobs, Steps, Runners, and the Job Graph

A job picks a runner and lists ordered steps:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest    # ubuntu-latest | windows-latest | macos-latest | self-hosted | <label>
    steps:
      - uses: actions/checkout@v4   # a `uses` step: run a published action
      - name: Run tests             # `name` is the label shown in the logs (optional)
        id: tests                   # `id` lets later steps/jobs reference this step's outputs
        run: ./run-tests.sh         # a `run` step: execute a shell command
```

- `runs-on` selects the runner image — a GitHub-hosted image, or `self-hosted` plus labels for your own machines ([Part 8](#part-8--operations-at-scale)).
- A step is **either** `uses:` (an action) **or** `run:` (a shell command), never both.
- `name` is cosmetic; `id` is functional — it's how you read a step's outputs later.

**Sequencing with `needs` — the job DAG.** Jobs run in parallel unless you declare dependencies. `needs` wires them into a directed graph:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo "linting"
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "testing"
  deploy:
    needs: [lint, test]       # waits until BOTH lint and test succeed
    runs-on: ubuntu-latest
    steps:
      - run: echo "deploying"
```

`lint` and `test` run concurrently; `deploy` is a fan-in that starts only after both pass. If a needed job fails, its dependents are skipped by default.

**Conditional execution with `if:`.** Both jobs and steps accept an `if:`:

```yaml
  deploy:
    needs: [lint, test]
    if: github.ref == 'refs/heads/main'   # job-level: only on the main branch
    runs-on: ubuntu-latest
    steps:
      - run: ./deploy.sh
      - run: ./notify-failure.sh
        if: failure()                       # step-level: run only if an earlier step failed
```

Inside `if:` the `${{ }}` wrapper is implied, so you can omit it (both forms are valid).

### Contexts and Expressions

`${{ ... }}` is the expression syntax. Inside it you read **contexts** — structured objects Actions exposes. The ones you'll use constantly ([contexts reference](https://docs.github.com/en/actions/learn-github-actions/contexts)):

| Context | What it holds | Example |
|---|---|---|
| `github` | Event and repo metadata | `github.sha`, `github.ref`, `github.event_name`, `github.actor` |
| `env` | Environment variables you set | `env.NODE_ENV` |
| `vars` | Non-secret configuration variables | `vars.REGISTRY` |
| `secrets` | Encrypted secrets | `secrets.GITHUB_TOKEN` |
| `matrix` | The current matrix combination | `matrix.os` |
| `needs` | Outputs of jobs you depend on | `needs.build.outputs.version` |
| `steps` | Outputs of earlier steps (by `id`) | `steps.tests.outputs.coverage` |
| `runner` | Runner info | `runner.os`, `runner.temp` |

**Operators and functions.** Expressions support `==`, `!=`, `&&`, `||`, `!`, plus built-in functions ([expressions reference](https://docs.github.com/en/actions/learn-github-actions/expressions)): `contains()`, `startsWith()`, `endsWith()`, `format()`, `join()`, `toJSON()`, `fromJSON()`, and `hashFiles()`. There are also **status functions** that only make sense in `if:`: `success()` (the implicit default), `failure()`, `always()` (run even after a failure or cancellation), and `cancelled()`.

A representative `if:` combining a context and a status function:

```yaml
      - run: ./publish-docs.sh
        # only on pushes (not PRs) to main, and only if earlier steps succeeded
        if: success() && github.event_name == 'push' && github.ref == 'refs/heads/main'
```

**Passing data between steps — `$GITHUB_OUTPUT`.** A step writes `name=value` lines to the file named by `$GITHUB_OUTPUT`; later steps read them through the `steps` context, keyed by the producing step's `id`:

```yaml
      - id: meta
        run: echo "version=$(cat VERSION)" >> "$GITHUB_OUTPUT"   # define an output named "version"
      - run: echo "Releasing ${{ steps.meta.outputs.version }}"  # read it back in a later step
```

(Passing data between *jobs* means promoting a step output to a **job output** — covered in [Part 3](#part-3--build-test-cache-artifacts), where it pairs naturally with artifacts.)

### Environment Variables, Defaults, and Shells

**`env` at three scopes**, narrowest wins:

```yaml
env:
  STAGE: global              # visible to every job and step in the workflow
jobs:
  build:
    env:
      STAGE: job             # overrides the global value for this job
    runs-on: ubuntu-latest
    steps:
      - run: echo "$STAGE"   # prints "job"
      - run: echo "$STAGE"
        env:
          STAGE: step        # overrides again, only for this step → prints "step"
```

**Exporting env between steps — `$GITHUB_ENV`.** Each `run` is a fresh shell, so a variable set in one step does *not* survive to the next. To persist one, append to `$GITHUB_ENV`:

```yaml
      - run: echo "BUILD_ID=$(date +%s)" >> "$GITHUB_ENV"  # exported as $BUILD_ID to later steps
      - run: echo "Build was $BUILD_ID"
```

**Defaults and shells.** `defaults.run` sets the shell and working directory for every `run` step:

```yaml
defaults:
  run:
    shell: bash                # default is bash on Linux/macOS, pwsh on Windows
    working-directory: ./app   # run commands from ./app instead of the repo root
```

Worth knowing when debugging: on Linux the default `bash` runs with `-e` and pipefail, so a failing command aborts the step — which is what you want, but it explains "why did my step stop in the middle."

**First look at `GITHUB_TOKEN` and `permissions`.** Every run gets an automatic, short-lived token in `secrets.GITHUB_TOKEN` that authenticates against your repo (to post a check, push a tag, comment on a PR). Its power is governed by `permissions:`:

```yaml
permissions:
  contents: read     # least privilege: read the repo, nothing more
```

Set it restrictively at the workflow level and grant extra scopes only on the jobs that need them. The default scopes, the real risks, and the least-privilege patterns are all in [Part 7](#part-7--security-hardening).

---

## Part 3 — Build, Test, Cache, Artifacts

This is the part you'll use every day: get a toolchain onto the runner, install dependencies fast, run tests across versions, and move results around. The examples deliberately span ecosystems — the *shape* is identical across languages, which is the point.

### Setting Up Toolchains (Pattern-First, Multi-Stack)

Every build/test job has the same skeleton: check out the code, install the language toolchain (with its dependency cache), install dependencies, run tests. The `actions/setup-*` family handles the toolchain *and* the dependency cache for you.

```yaml
# Node — actions/setup-node
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: npm           # transparently caches ~/.npm, keyed on package-lock.json
- run: npm ci            # clean install honoring the lockfile exactly
- run: npm test
```

```yaml
# Python — actions/setup-python
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: pip           # caches the pip download cache, keyed on requirements files
- run: pip install -r requirements.txt
- run: pytest
```

```yaml
# Go — actions/setup-go
- uses: actions/setup-go@v5
  with:
    go-version: '1.22'   # caches the module and build cache by default (cache: true)
- run: go test ./...
```

```yaml
# Rust — community-standard toolchain + cache actions
- uses: dtolnay/rust-toolchain@stable   # installs rustc/cargo for the chosen channel
- uses: Swatinem/rust-cache@v2          # caches ~/.cargo and ./target, keyed on Cargo.lock
- run: cargo test
```

Only the tool names change. Lean on each `setup-*` action's built-in `cache:` — it's the cheapest performance win you'll get.

### Caching Dependencies

When the built-in cache isn't enough — or you need to cache something a `setup-*` action doesn't manage — use [`actions/cache`](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows) directly:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip                                              # what to cache
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}  # exact, content-addressed key
    restore-keys: |
      ${{ runner.os }}-pip-                                         # prefix fallbacks on a miss
```

The mechanics that matter:

- On a **miss** for `key`, Actions walks the `restore-keys` prefixes and restores the most recent match — a stale-but-warm cache beats a cold one. At job end, if `key` didn't already exist, the `path` is saved under it.
- `hashFiles()` over the lockfile makes the key change *exactly* when dependencies change. That's the whole idiom: same deps → same key → hit; changed deps → new key → fresh save.
- A key, once written, is **immutable** — you cannot overwrite it. This is why the key must encode the dependency set.
- Caches are **scoped per branch**, with read-through to the base/default branch. A PR can read the base branch's cache but not an unrelated branch's.
- There's a per-repo size cap, and caches are evicted after about a week unused (or when the repo total is exceeded). Don't cache anything you can recompute cheaply.

Rule of thumb: if a `setup-*` action offers `cache:`, use it; reach for `actions/cache` for compiler caches (ccache, sccache), custom build outputs, or downloaded fixtures.

### Matrix Builds

A matrix runs one job definition across a set of dimensions, in parallel ([matrix docs](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)):

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false        # don't cancel the other combos when one fails
      max-parallel: 4         # optional cap on concurrent combos
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: [18, 20, 22]
        include:
          - os: ubuntu-latest # enrich one specific combo with an extra property
            node: 22
            coverage: true
        exclude:
          - os: windows-latest  # drop a combo you don't support
            node: 18
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}   # read the current combo from the matrix context
      - run: npm ci && npm test
```

- The base matrix is 3 OSes × 3 Node versions = 9 jobs; `exclude` removes one (→ 8), `include` enriches one.
- `fail-fast: true` (the default) cancels the remaining combos the instant one fails — fast feedback, but you lose the full failure picture. Set it `false` when you want every combo's result (e.g. "does this break only on Windows + Node 18?").

**Dynamic matrices.** When the set isn't static — say "test every package directory" — emit it as JSON from one job and feed it to another with `fromJSON`:

```yaml
jobs:
  discover:
    runs-on: ubuntu-latest
    outputs:
      pkgs: ${{ steps.set.outputs.pkgs }}
    steps:
      - uses: actions/checkout@v4
      - id: set
        run: |
          # emit a JSON array of package names as a step output
          echo "pkgs=$(ls packages | jq -R -s -c 'split("\n") | map(select(length > 0))')" >> "$GITHUB_OUTPUT"
  test:
    needs: discover
    runs-on: ubuntu-latest
    strategy:
      matrix:
        pkg: ${{ fromJSON(needs.discover.outputs.pkgs) }}   # build the matrix from upstream JSON
    steps:
      - run: echo "testing ${{ matrix.pkg }}"
```

### Artifacts and Moving Data Between Jobs

Because jobs are isolated, handing files from one to another means uploading an **artifact** and downloading it downstream:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build      # produces ./dist
      - uses: actions/upload-artifact@v4
        with:
          name: site                       # the artifact's name
          path: dist/                       # file(s)/dir(s) to store
          retention-days: 7                 # optional; otherwise the repo default (max 90)
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: site                        # restores the artifact into the working dir
      - run: ./publish.sh
```

Two mechanisms, two purposes:

- **Artifacts** are for *files* — build output, test reports, coverage, logs. They survive the run (per retention) and are downloadable from the run's UI. Note the artifact actions are at **v4**, which changed behavior: an uploaded artifact is immutable, and you can't have multiple jobs append to one name.
- **Job outputs** are for *small strings* — a version, a computed flag. A job exposes `outputs:` sourced from a step output, and dependents read `needs.<job>.outputs.<name>`:

```yaml
jobs:
  version:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.v.outputs.tag }}       # promote a step output to a job output
    steps:
      - id: v
        run: echo "tag=v1.4.2" >> "$GITHUB_OUTPUT"
  release:
    needs: version
    runs-on: ubuntu-latest
    steps:
      - run: echo "Releasing ${{ needs.version.outputs.tag }}"
```

Rule of thumb: a **file** → artifact; a **string** → job output.

### Service Containers

Integration tests often need a real database or cache. [`services:`](https://docs.github.com/en/actions/using-containerized-services/about-service-containers) starts containers next to your job on the same network; your steps reach them on `localhost`:

```yaml
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres        # configure the container through its own env vars
        ports:
          - 5432:5432                         # publish the container port to localhost on the runner
        options: >-                           # health check — the job waits until Postgres is ready
          --health-cmd "pg_isready -U postgres"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/postgres
      REDIS_URL: redis://localhost:6379
    steps:
      - uses: actions/checkout@v4
      - run: ./run-integration-tests.sh       # connects to localhost:5432 and localhost:6379
```

The health checks are not optional in practice: without them, your tests can start before the database accepts connections and fail intermittently — one of the most common flaky-CI causes. For what to actually exercise behind these connections, see the [Postgres guide](POSTGRES_STUDY_GUIDE.md) and [Redis guide](REDIS_STUDY_GUIDE.md).

---

## Part 4 — Composition & Reuse

Once you have more than a couple of workflows, copy-paste sets in: the same build job, the same setup steps, pasted everywhere and drifting out of sync. Actions offers reuse at three granularities — **composite actions** (a bundle of steps), **reusable workflows** (whole jobs), and **custom actions** (a distributable unit, [Part 5](#part-5--writing-custom-actions)). This part covers the first two and exactly when to use which.

### Reusable Workflows

A [reusable workflow](https://docs.github.com/en/actions/using-workflows/reusing-workflows) is a workflow other workflows can call as a job, via `on: workflow_call`. It declares a typed interface — inputs, secrets, outputs:

```yaml
# .github/workflows/reusable-build.yml
name: Reusable build
on:
  workflow_call:                # makes this workflow callable from other workflows
    inputs:
      node-version:
        type: string            # one of: string | number | boolean
        required: false
        default: '20'
    secrets:
      npm-token:
        required: true          # callers must supply this secret
    outputs:
      artifact-name:
        description: Name of the uploaded build artifact
        value: ${{ jobs.build.outputs.artifact-name }}   # surfaced from a job output below
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      artifact-name: site
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node-version }}
      - run: npm ci && npm run build
        env:
          NPM_TOKEN: ${{ secrets.npm-token }}
      - uses: actions/upload-artifact@v4
        with:
          name: site
          path: dist/
```

A caller references it at the **job level** with `uses:`:

```yaml
# .github/workflows/app-ci.yml
name: CI
on: [push]
jobs:
  build:
    uses: ./.github/workflows/reusable-build.yml   # local path (or owner/repo/.github/workflows/x.yml@ref)
    with:
      node-version: '22'
    secrets:
      npm-token: ${{ secrets.NPM_TOKEN }}
      # alternatively, forward ALL of the caller's secrets:  secrets: inherit
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: echo "Built artifact ${{ needs.build.outputs.artifact-name }}"
```

What to internalize:

- A called workflow runs as its **own job(s)**, shown nested under the caller. To read its outputs, `needs:` the calling job and reference `needs.<job>.outputs.<name>`.
- `secrets: inherit` forwards every secret the caller has — convenient but the opposite of least privilege. Prefer naming only the secrets you need.
- Reusable workflows can be called **across repos** (`owner/repo/.github/workflows/wf.yml@v1`), which is how organizations share a canonical pipeline. Pin that ref like any other dependency ([Part 7](#part-7--security-hardening)).
- There's a fixed **nesting limit** (you can chain calls only a few levels deep) and a cap on how many workflow files one run may call.

### Composite Actions

A [composite action](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action) bundles several steps into a single `uses:` step. It lives in its own directory with an `action.yml`:

```yaml
# .github/actions/setup-project/action.yml
name: Setup project
description: Set up Node and install dependencies
inputs:
  node-version:
    description: Node version
    required: false
    default: '20'
runs:
  using: composite            # this is what makes it a composite action
  steps:
    - uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node-version }}
    - run: npm ci
      shell: bash             # REQUIRED: every `run` step in a composite action must name a shell
```

Invoke it like any other action, by path to its directory:

```yaml
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-project   # local composite action
        with:
          node-version: '22'
      - run: npm test
```

The gotcha that catches everyone: **a composite action's `run` steps must each set `shell:`** — there's no default. Composite actions execute *inside the caller's job* on the same runner, so they factor out **steps**, not whole jobs.

### Org-Level Reuse

Two mechanisms operate across an entire organization:

- **Starter workflows** — templates that appear in the "New workflow" UI of every repo in the org. Put them in a special `.github` repository under `workflow-templates/` (a `*.yml` next to a `*.properties.json` that describes it). New repos start from a sanctioned pipeline instead of copying a random one.
- **Required workflows / rulesets** — let an org *enforce* that specific checks run on PRs across many repos, configured centrally through repository rulesets rather than per repo.

```json
// .github/workflow-templates/node-ci.properties.json
{
  "name": "Node CI",
  "description": "Lint and test a Node project",
  "iconName": "example",
  "categories": ["JavaScript", "CI"]
}
```

### Which One to Reach For

| Mechanism | Granularity | Runs as | Reach for it when… |
|---|---|---|---|
| **Composite action** | A bundle of steps | Inside the caller's job (same runner) | You repeat the same *sequence of steps* across jobs (setup, shared tooling). |
| **Reusable workflow** | One or more whole jobs | Its own job(s) under the caller | You repeat *whole jobs/pipelines* across workflows or repos (a standard build or deploy). |
| **Custom action** ([Part 5](#part-5--writing-custom-actions)) | A distributable unit (JS/Docker/composite) | A single step | You want a versioned, publishable building block — possibly for the Marketplace. |

Rule of thumb: factoring out *steps within a job* → composite action; factoring out *entire jobs* → reusable workflow; building something *others install* → custom action.

---

## Part 5 — Writing Custom Actions

When the Marketplace doesn't have what you need — or you want a versioned building block of your own — you [write a custom action](https://docs.github.com/en/actions/creating-actions). There are three flavors, and choosing the right one is most of the decision.

### The Three Kinds

| Kind | What it is | Where it runs | Best for |
|---|---|---|---|
| **Composite** | YAML bundling steps (Part 4) | In the caller's job, same runner | Wrapping shell commands / other actions; no extra runtime |
| **JavaScript** | A Node program the runner executes | Node on the runner — any OS | Logic, API calls, cross-platform actions; fastest startup |
| **Docker container** | A container the runner builds and runs | **Linux runners only** | Bringing a specific OS / toolchain along; heavier startup |

- **JavaScript** actions run directly under Node on the runner, so they start fast and work on Linux, macOS, and Windows. This is the default choice for anything with real logic.
- **Docker** actions can package arbitrary tools, but only run on Linux runners and pay the image build/pull cost on every run. Use them when you need an environment that's painful to set up otherwise.
- **Composite** (from Part 4) is the no-runtime option when your action is "just some steps."

### action.yml Anatomy

Every action — whichever kind — has a [metadata file](https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions) (`action.yml`) at its root:

```yaml
name: My Action               # display name (must be unique if published to the Marketplace)
description: What it does
author: you
inputs:
  who:
    description: Name to greet
    required: false
    default: world
outputs:
  greeting:
    description: The greeting that was produced
runs:
  using: node20               # composite | node20 | docker — this selects the kind
  main: dist/index.js         # (JavaScript) the entrypoint file
branding:                     # optional; controls the Marketplace listing's icon/color
  icon: activity
  color: purple
```

### A JavaScript Action

JS actions use the official toolkit: `@actions/core` (inputs, outputs, logging, failing the step) and `@actions/github` (the event `context` and a ready-made authenticated Octokit client).

```yaml
# action.yml
name: Greet
description: Print a greeting and output it
inputs:
  who:
    description: Name to greet
    default: world
outputs:
  greeting:
    description: The produced greeting
runs:
  using: node20
  main: dist/index.js
```

```javascript
// index.js
const core = require('@actions/core');
const github = require('@actions/github');

try {
  const who = core.getInput('who');                  // read an input declared in action.yml
  const greeting = `Hello, ${who}!`;
  core.info(`Triggered by: ${github.context.eventName}`); // read the event from the context
  core.setOutput('greeting', greeting);              // expose an output to later steps
  console.log(greeting);
} catch (err) {
  core.setFailed(err.message);                       // mark the step failed with a clear message
}
```

The step nearly everyone forgets: an action referenced by `uses:` must carry its **runtime dependencies committed in the repo**, because the runner does not `npm install` your action before running it. The standard fix is to bundle everything into one file with [`@vercel/ncc`](https://github.com/vercel/ncc) and commit the result:

```bash
npm i -D @vercel/ncc            # dev dependency
npx ncc build index.js -o dist  # produces dist/index.js with all deps inlined
git add dist && git commit -m "build"   # commit the bundle so consumers receive it
```

Either commit `dist/` directly (simplest) or build it in a release workflow and attach it to the tag (cleaner history). Consumers then write `uses: your-org/greet@v1`.

### A Docker-Container Action

A [Docker action](https://docs.github.com/en/actions/creating-actions/creating-a-docker-container-action) packages a tool plus its environment; the runner builds the image from your `Dockerfile` and runs it:

```yaml
# action.yml
name: Lint with my tool
description: Run a containerized linter
inputs:
  path:
    description: Path to lint
    default: .
runs:
  using: docker
  image: Dockerfile         # build from this Dockerfile (or a prebuilt image: docker://ghcr.io/org/img:tag)
  args:
    - ${{ inputs.path }}    # passed to the entrypoint as positional arguments
```

```dockerfile
# Dockerfile
FROM alpine:3.20
RUN apk add --no-cache bash
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

```bash
# entrypoint.sh
#!/usr/bin/env bash
set -euo pipefail
echo "Linting path: $1"               # the action.yml `args` arrive as positional parameters
echo "via env: ${INPUT_PATH}"         # inputs are ALSO exposed as INPUT_<UPPERCASE_NAME>
echo "result=ok" >> "$GITHUB_OUTPUT"  # outputs go to $GITHUB_OUTPUT, same as anywhere
```

Inputs reach a Docker action two ways: as `args` (positional) and automatically as `INPUT_<NAME>` environment variables (name uppercased). Outputs use `$GITHUB_OUTPUT` like every other step.

### Versioning & Distribution

Consumers pin to a ref, so **your tags are your public API**:

- Cut **semver tags** (`v1.2.0`) for releases.
- Maintain a **floating major tag** (`v1`) that you re-point to the latest `v1.x.y`. This is the convention that lets consumers write `@v1` and pick up non-breaking updates:
  ```bash
  git tag -f v1 v1.2.0      # move the v1 tag onto the new release
  git push -f origin v1
  ```
- Security-conscious consumers will pin your **commit SHA** instead of `@v1` ([Part 7](#part-7--security-hardening)). That's expected — design your changelog around it.
- To list on the [Marketplace](https://docs.github.com/en/actions/creating-actions/publishing-actions-in-github-marketplace), the repo needs a single root `action.yml`, a good README, and a published release.

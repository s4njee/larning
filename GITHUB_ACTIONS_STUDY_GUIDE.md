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

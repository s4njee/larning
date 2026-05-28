# GitHub Actions Study Guide — Design

- **Date:** 2026-05-28
- **Status:** Approved (outline), pending spec review
- **Deliverable:** `GITHUB_ACTIONS_STUDY_GUIDE.md` at the repo root, plus a `README.md` entry and a `TOPICS.md` prune.

## Overview

A depth-first, practical study guide to GitHub Actions for working engineers, matching
the house style of the existing guides in this repo (e.g. `OBSERVABILITY_STUDY_GUIDE.md`,
`ANSIBLE_STUDY_GUIDE.md`, `GIT_STUDY_GUIDE.md`): foundations and a mental model first, then
progressively heavier topics, closing with copy-paste recipes and a narrated end-to-end
walkthrough. The guide should make the reader fluent enough to design, secure, and operate
real CI/CD pipelines — not just copy YAML.

This guide fills the single biggest structural gap in the collection: there is provisioning
(Terraform), configuration (Ansible), packaging (Docker), orchestration (Kubernetes), and
operation (Observability), but no guide on the **pipeline that ties them together**.

## Audience

Working engineers who understand version control and the shape of software delivery, but
who may not have built a non-trivial CI/CD pipeline. General CI/CD literacy is *not*
assumed — Part 1 supplies a brief conceptual framing — but the guide quickly moves to
GitHub-Actions-specific depth. It does not assume any one language ecosystem.

## Scope Decisions (from brainstorming)

1. **Example spine: pattern-first, multi-stack.** Examples are chosen to illustrate each
   Actions feature cleanly, drawing from Node, Python, Go, and Rust as convenient, rather
   than carrying one app through the whole guide. This keeps the guide broadly useful for
   the public repo. Where a concept ties naturally to an existing guide (Postgres/Redis
   service containers, Docker image builds, K8s deploys, Cloudflare), reference it.
2. **All four heavy chapters are in scope:** Security hardening, Writing custom actions,
   Release & publishing automation, and Self-hosted runners & scaling.
3. **Primary cloud for OIDC/deploy examples: AWS**, with Azure, GCP, Cloudflare, and
   HashiCorp Vault noted as variants. (The repo has an Azure and a Cloudflare guide to
   cross-reference; it has no AWS guide, so AWS is also the most broadly recognized
   canonical OIDC example.)
4. **No fixed length.** Depth matches the topic; with all heavy chapters in, expect a guide
   comparable in size to the Git/Observability guides.

## Non-Goals

- Not a mechanical re-documentation of every YAML key (GitHub's reference already does that
  well; the repo's own criterion #4 says don't duplicate well-served material).
- Not a quickstart/tutorial-only treatment.
- Not a deep dive into any single language's build tooling — build steps are shown only as
  far as needed to illustrate the Actions feature.
- Not GitHub Enterprise Server administration (mention only where it affects runners/policy).

## House-Style Constraints

Derived from the existing guides:

- Numbered parts with `###` subsections; a Table of Contents near the top.
- Heavy use of fenced code blocks with **inline `#` comments** that explain each meaningful
  line. YAML and shell are the dominant languages; JS/TS and Dockerfile appear in the
  custom-actions chapter.
- Prose explains the *why* and the tradeoffs, not just the *how*.
- An honest "comparison to alternatives" chapter (cf. Ansible vs Terraform/Puppet/Salt).
- A debugging/diagnostic section (cf. Networking's diagnostic toolkit).
- Closes with concrete recipes and an end-to-end walkthrough (cf. Observability, Ansible).
- Be honest about footguns, cost, and where the tool is weak.

## Chapter Outline

### Part 1 — Foundations & Mental Model
- What CI/CD actually buys you (fast feedback loops, repeatability, gating); CI vs CD vs CD.
- Where GitHub Actions fits; a one-paragraph contrast with Jenkins/GitLab/CircleCI (the deep
  comparison is Part 9).
- The execution model: events → workflows → jobs → steps → runners. What is ephemeral, what
  runs where, what a runner is, the per-job fresh VM.
- Repository layout: `.github/workflows/*.yml`.
- "Your first workflow," dissected line by line.

### Part 2 — The Workflow Language
- Events & triggers: `push`, `pull_request`, `schedule` (cron), `workflow_dispatch` (with
  typed `inputs`), `workflow_run`, `repository_dispatch`. Activity types.
- Filters: `branches`, `branches-ignore`, `paths`, `paths-ignore`, `tags`.
- Jobs, steps, runners: `runs-on`, hosted runner images, `needs` (the job DAG), job- and
  step-level `if:`.
- **Contexts & expressions:** `${{ }}`, the `github`/`env`/`secrets`/`vars`/`matrix`/`needs`
  contexts, built-in functions (`contains`, `fromJSON`, `hashFiles`, status checks), `if:`
  conditionals.
- Environment variables, `defaults`, `working-directory`, `shell`.
- First look at `GITHUB_TOKEN` and `permissions` (full security treatment in Part 7).

### Part 3 — Real Work: Build, Test, Cache, Artifacts
- `setup-*` actions across ecosystems: `actions/setup-node`, `setup-python`, `setup-go`,
  Rust toolchain (`dtolnay/rust-toolchain` / `actions-rust-lang`). Pattern-first, multi-stack.
- **Dependency caching:** `actions/cache`, cache keys & `restore-keys`, `hashFiles`,
  built-in caching in the `setup-*` actions, cache scope/eviction gotchas.
- **Matrix builds:** multi-version and multi-OS, `include`/`exclude`, `fail-fast`,
  `max-parallel`, dynamic matrices via `fromJSON`.
- **Artifacts:** `upload-artifact`/`download-artifact`, retention, passing data between jobs
  (artifacts vs job `outputs`).
- **Service containers:** Postgres and Redis for integration tests (cross-reference the
  Postgres/Redis guides), health checks, port mapping.

### Part 4 — Composition & Reuse
- **Reusable workflows** (`workflow_call`): typed `inputs`, `secrets` (incl. `inherit`),
  `outputs`, nesting limits.
- **Composite actions:** bundling steps into a local `action.yml`.
- Org-level **starter workflows** and **required workflows**.
- Decision guide: reusable workflow vs composite action vs custom action.

### Part 5 — Writing Custom Actions
- The three kinds — **composite**, **JavaScript**, **Docker-container** — and their tradeoffs
  (speed, language, where they run).
- `action.yml` anatomy: `inputs`, `outputs`, `runs`, `branding`.
- Worked **JavaScript action** using the toolkit (`@actions/core`, `@actions/github`),
  including how to handle inputs/outputs and the build/commit-`dist/` step (or `ncc`).
- Worked **Docker-container action**.
- Versioning & distribution: semver tags, the floating `v1` major-tag pattern, releasing to
  the Marketplace.

### Part 6 — Deployment & Release Automation
- **Environments:** protection rules, required reviewers, wait timers, environment-scoped
  secrets, deployment branches.
- **Secrets & variables:** repo/environment/org scope, masking and its limits, why fork PRs
  don't receive secrets, external secret managers.
- **OIDC to cloud (in depth):** how the trust works (short-lived tokens, no stored cloud
  keys), the JWT `sub` claim and trust policy, full worked **AWS** example
  (`aws-actions/configure-aws-credentials` + IAM role + trust policy); notes for Azure
  (`azure/login`), GCP (Workload Identity Federation), Cloudflare, and Vault.
- **Deploy patterns:** deploying a container image, a static site, and to Kubernetes; gating
  deploys on environments and `concurrency`.
- **Release automation:** tag-driven releases, generating release notes/changelogs, semver,
  and publishing to **GHCR, npm, PyPI, and crates.io**.

### Part 7 — Security Hardening
- Threat model: what a malicious PR or a compromised third-party action can actually do.
- The **`pull_request` vs `pull_request_target`** privilege-escalation footgun, with a safe
  pattern for labeling/commenting on fork PRs.
- **Script injection** via untrusted `${{ github.event.* }}` interpolated into `run:` blocks;
  the env-var mitigation.
- **Pinning third-party actions to full commit SHAs** (tags are mutable); Dependabot for
  actions to keep pins current.
- **Least privilege:** `permissions:` at workflow and job scope; the default `GITHUB_TOKEN`
  scope and how to set it read-only by default.
- **Secret exfiltration vectors**, log masking limits, and protecting secrets from forks.
- **Supply chain:** allowed-actions org policy, artifact attestations / build provenance,
  reviewing transitive action risk.

### Part 8 — Operations at Scale
- Hosted vs self-hosted runners; when to switch (special hardware, private network, cost).
- **Self-hosted runner** setup; the critical "never attach a self-hosted runner to a public
  repo with fork PRs" caveat; ephemeral runners.
- **Autoscaling with Actions Runner Controller (ARC)** on Kubernetes (cross-reference the K8s
  guide); runner scale sets.
- Larger hosted runners and runner groups.
- **`concurrency:`** and `cancel-in-progress` to dedupe runs and prevent deploy races.
- **Cost model & optimization:** what's free vs billed, minute multipliers, cutting runtime
  with caching and right-sized matrices.
- **Debugging:** re-running jobs, step-debug logging (`ACTIONS_STEP_DEBUG`), interactive
  SSH with `mxschmitt/action-tmate`, and running workflows locally with `act`.

### Part 9 — Honest Comparison to Alternatives
- GitLab CI/CD, CircleCI, Jenkins, Buildkite, and Dagger: where each wins, where Actions
  wins, and brief migration notes (esp. GitLab CI and Jenkins, the two most common
  migrations). A short "when *not* to use Actions" note.

### Part 10 — Recipes & End-to-End Walkthrough
- **Recipes** (copy-paste, each with brief commentary):
  1. Lint + test + build matrix across language versions and OSes.
  2. Cached monorepo CI using `paths` filters and per-package change detection.
  3. Build and push a container image to GHCR with build provenance/attestation.
  4. OIDC deploy to AWS with no stored credentials.
  5. Auto-publish a library to a registry on tag push.
- **End-to-end walkthrough:** take a containerized service from an empty repo to a full
  pipeline — PR validation (lint/test/matrix) → build & push image → deploy to staging on
  merge to `main` → promote to production via a protected environment with a required
  reviewer — narrated decision by decision.

## Worked-Example Inventory

Concrete artifacts the guide must contain (so the implementation plan can budget them):

- A minimal first workflow (Part 1).
- Trigger/filter snippets incl. `workflow_dispatch` with inputs and a cron schedule (Part 2).
- Context/expression and `if:` examples (Part 2).
- `setup-*` + cache examples for Node, Python, Go, Rust (Part 3).
- A matrix build with `include`/`exclude` and a dynamic `fromJSON` matrix (Part 3).
- Artifact upload/download and a job-`outputs` example (Part 3).
- A Postgres + Redis service-container integration-test job (Part 3).
- A reusable workflow (`workflow_call`) and a caller; a local composite action (Part 4).
- A full JavaScript action (`action.yml` + `index.js`) and a Docker-container action (Part 5).
- An environment with required reviewer; an OIDC-to-AWS deploy job with IAM trust policy
  (Part 6).
- Publish-on-tag jobs for GHCR + at least one of npm/PyPI/crates.io (Part 6).
- A `pull_request_target` safe-vs-unsafe pair; a script-injection unsafe-vs-safe pair; a
  SHA-pinned action with a Dependabot config; a least-privilege `permissions` block (Part 7).
- A self-hosted runner registration sketch and an ARC `RunnerScaleSet`/values sketch;
  a `concurrency` example (Part 8).
- The five recipes and the end-to-end pipeline (Part 10).

All third-party actions shown in "good practice" contexts should be SHA-pinned (or the text
should note when a tag is used for readability), consistent with Part 7.

## Deliverables & Repo Integration

1. `GITHUB_ACTIONS_STUDY_GUIDE.md` — the guide.
2. **`README.md`** — add a "GitHub Actions" entry under the guides list, in the same format
   as the others (short description + GitHub link to the file on the `main` branch).
3. **`TOPICS.md`** — remove "GitHub Actions" from the future-topics backlog, and (housekeeping
   noted during brainstorming) remove the now-completed **Docker (Deep)**, **Git (Deep)**,
   **Redis**, **TypeScript (Deep)**, and **LLM Application Development** entries, which already
   exist as guides.

## Acceptance Criteria

- All ten parts are present, each with working, internally consistent example YAML.
- Examples span at least Node, Python, Go, and Rust across the guide.
- All four heavy topics (security, custom actions, release automation, self-hosted/scaling)
  are covered with worked examples, not just prose.
- The OIDC section has a complete, correct AWS example (role trust policy + workflow).
- The security chapter explicitly covers the `pull_request_target` footgun, script injection,
  SHA-pinning, and least-privilege `permissions`.
- Closes with the five recipes and the end-to-end walkthrough.
- `README.md` and `TOPICS.md` are updated as above.
- Tone, structure, and code-comment density match the existing guides.

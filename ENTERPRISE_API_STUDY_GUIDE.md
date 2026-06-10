# Enterprise-Grade APIs

A depth-first guide to designing, building, and operating APIs that other teams — and other companies — can bet their systems on. "Enterprise-grade" is not a feature list; it is a posture: the API is a **contract with consumers you cannot redeploy**, and every design decision is judged by how it behaves under partial failure, concurrent access, malicious input, version skew, and ten years of accumulated clients. This guide covers resource and error design, idempotency (treated as the load-bearing concept it is), versioning and compatibility, pagination, concurrency control, authentication and authorization, rate limiting, retries and resilience, long-running operations and webhooks, observability, contract testing, and the platform layer — with wire-level HTTP examples throughout and implementation snippets in TypeScript.

Assumes you've built and shipped HTTP APIs before. This guide is about the distance between "works in the demo" and "processes other people's money."

Primary references: [RFC 9110 (HTTP Semantics)](https://www.rfc-editor.org/rfc/rfc9110), [RFC 9457 (Problem Details)](https://www.rfc-editor.org/rfc/rfc9457), the [Stripe API reference](https://stripe.com/docs/api) (the de facto style standard for commercial APIs), [OWASP API Security Top 10](https://owasp.org/API-Security/), the [OpenAPI Specification](https://spec.openapis.org/oas/latest.html), and Google's [API Improvement Proposals](https://google.aip.dev/).

---

## Table of Contents

1. [Part 1 — What "Enterprise-Grade" Actually Means](#part-1--what-enterprise-grade-actually-means)
2. [Part 2 — Resource and Error Design](#part-2--resource-and-error-design)
3. [Part 3 — Idempotency](#part-3--idempotency)
4. [Part 4 — Versioning and Compatibility](#part-4--versioning-and-compatibility)
5. [Part 5 — Pagination, Filtering, and Sorting](#part-5--pagination-filtering-and-sorting)
6. [Part 6 — Concurrency Control and Consistency](#part-6--concurrency-control-and-consistency)
7. [Part 7 — Authentication and Authorization](#part-7--authentication-and-authorization)
8. [Part 8 — Rate Limiting, Quotas, and Load Shedding](#part-8--rate-limiting-quotas-and-load-shedding)
9. [Part 9 — Timeouts, Retries, and Resilience](#part-9--timeouts-retries-and-resilience)
10. [Part 10 — Long-Running Operations, Webhooks, and Events](#part-10--long-running-operations-webhooks-and-events)
11. [Part 11 — Observability and Auditability](#part-11--observability-and-auditability)
12. [Part 12 — Contracts, Documentation, and Testing](#part-12--contracts-documentation-and-testing)
13. [Part 13 — The Platform Layer and the Design-Review Checklist](#part-13--the-platform-layer-and-the-design-review-checklist)

---

## Part 1 — What "Enterprise-Grade" Actually Means

Most API advice is about the happy path: name resources well, return sensible JSON, document it. Necessary, and nowhere near sufficient. The difference between an internal demo API and an enterprise-grade one is **who bears the cost of your mistakes and how long they bear it**:

- **You cannot redeploy your consumers.** An internal frontend ships with its backend; an enterprise API has clients you've never met — partner integrations frozen in 2019, mobile apps users won't update, cron jobs in other companies' datacenters. Every field you expose, every status code you return, every quirk in your pagination is something *somebody* now depends on. [Hyrum's Law](https://www.hyrumslaw.com/) is the operating condition: with enough consumers, every observable behavior of your API will be depended upon by someone — including your bugs.
- **The network is part of the API.** Requests time out with the response in flight. Clients retry. Two requests for the same logical operation arrive concurrently on different nodes. An API that is correct only when every request arrives exactly once, in order, and gets its response delivered, is incorrect. Parts 3, 6, and 9 are about designing for the network you actually have.
- **Failure modes are interface, not implementation.** What does a consumer see during your deploy? Your database failover? When they exceed their quota? Each of those is a contractual surface — `429` vs `503`, `Retry-After` present or absent, errors machine-parseable or prose — that consumers will write code against.
- **Operations are a feature.** A consumer debugging "my requests fail at 2% since Tuesday" needs request IDs they can quote to your support, error bodies that distinguish *their* bug from *yours*, status pages, and deprecation timelines measured in quarters. None of this is glamorous; all of it is the product.

A useful mental reframe: **the API is a product whose users are programmers and whose UI is the wire format.** Product discipline follows — versioned releases, migration guides, a changelog, support channels, and a deep reluctance to break users for your own convenience.

The rest of this guide is that posture, made concrete, roughly in the order the problems bite: design (Parts 2–5), correctness under concurrency (Parts 3, 6), security (Part 7), surviving load and failure (Parts 8–9), escaping the request/response box (Part 10), and operating the thing (Parts 11–13).

---

## Part 2 — Resource and Error Design

### Resources, not actions

Model the domain as **nouns with state** manipulated through HTTP's uniform verbs, because the verbs carry semantics that infrastructure understands (Part 3 depends on this). The classic shape:

```
GET    /v1/transfers              # list (paginated — Part 5)
POST   /v1/transfers              # create
GET    /v1/transfers/{id}         # read
PATCH  /v1/transfers/{id}         # partial update
DELETE /v1/transfers/{id}         # delete (or cancel — see below)
POST   /v1/transfers/{id}/cancel  # action that isn't CRUD
```

The escape hatch in the last line matters: real domains have verbs that aren't state-overwrites (`cancel`, `approve`, `retry`). Forcing them into `PATCH {"status": "cancelled"}` conflates "client sets a field" with "system runs a workflow" and makes authorization and validation murky (may this caller set status to *anything*?). A sub-resource action endpoint (`POST .../cancel`) — Google's AIP-136 "custom methods" pattern — keeps the workflow explicit. Use it deliberately and sparingly; if most of your API is action endpoints, you've built RPC and should design it as RPC honestly.

**Method semantics are a contract, not a style.** RFC 9110 defines two properties that Part 3 and Part 9 build on:

| Method | Safe (no state change) | Idempotent | Typical use |
| --- | --- | --- | --- |
| GET, HEAD | yes | yes | reads |
| PUT | no | **yes** | full replace ("make the resource equal this") |
| DELETE | no | **yes** | removal ("make it gone") |
| PATCH | no | no (unless you design it so) | partial update |
| POST | no | **no** | creation, actions, everything else |

Proxies, gateways, SDK retry layers, and browsers all assume these properties. A `GET` that mutates state will eventually be called by a prefetcher, a health checker, or a retry, and the resulting incident is your fault, not theirs.

### Representations: the boring decisions that age the best

Wire-format choices are forever (Part 4 explains why), so make the durable ones up front:

- **IDs are opaque strings.** Not integers (they leak cardinality, invite enumeration, and overflow JS's 2⁵³ integer ceiling), not raw UUIDs if you can do better: **prefixed identifiers** (`tr_8MGyq4zXKj0`) à la Stripe make IDs self-describing in logs and support tickets and let you change the generation scheme later. Document that IDs are opaque and up to N characters; never document the internal structure.
- **Timestamps are RFC 3339 / ISO 8601, UTC, with offset** (`2026-06-10T14:23:05Z`). Never epoch integers (which unit?), never local time, never anything else. Accept that you'll receive sloppy input and reject it explicitly.
- **Money is integer minor units plus a currency code** (`{"amount": 2500, "currency": "usd"}` = $25.00). JSON numbers are IEEE-754 doubles in most parsers; `0.1 + 0.2` is not your invoice total. If you must handle currencies with non-hundredth minor units or crypto precision, use a decimal *string* and say so.
- **Enums will grow.** Document explicitly: "clients MUST tolerate unknown values of `status`" — and consider an `"other"`/catch-all story for critical switch statements. An enum you can't extend without breaking clients isn't an enum, it's a trap (Part 4).
- **Field naming is a one-time decision per API**: pick `snake_case` or `camelCase`, write it down, lint it (Part 12). Mixed conventions are the smell reviewers notice first.
- **Return the full resource from writes.** `POST /transfers` answers `201` with the created transfer (including server-set fields: `id`, `created_at`, `status`), so clients never need a follow-up `GET` that might hit a stale replica (Part 6).

### Errors are an API surface, not an apology

Two audiences read every error: a program deciding what to do next, and a human debugging at 2am. Serve both with **RFC 9457 Problem Details** (`application/problem+json`) plus a stable, machine-matchable code:

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json
Request-Id: req_9f3b2c

{
  "type": "https://api.example.com/errors/insufficient-funds",
  "title": "Insufficient funds",
  "status": 422,
  "detail": "Account acct_7Hq2 has a balance of 1200 but the transfer requires 2500.",
  "code": "insufficient_funds",
  "request_id": "req_9f3b2c",
  "errors": [
    { "field": "amount", "code": "exceeds_balance", "message": "Transfer amount exceeds available balance." }
  ]
}
```

The rules that make this work at scale:

- **`code` is the contract; `detail` is prose.** Clients branch on `code`; you may reword `detail` freely. Document every code. Never make clients regex your error messages — they will if you give them nothing better, and then your typo fixes are breaking changes (Hyrum again).
- **Status codes triage; bodies diagnose.** `4xx` = "your request is wrong, don't retry it unchanged"; `5xx` = "we failed, retrying may help"; and within those, the handful that carry specific machine semantics: `401` (who are you) vs `403` (you, specifically, may not) vs `404` (not here — also the right answer for "exists but you may not know it exists," to avoid resource enumeration), `409` (state conflict — Part 6), `422` (understood but semantically invalid), `429` (slow down — Part 8). Don't get creative; clients have generic handlers keyed to exactly these.
- **Validation errors enumerate every problem at once** (the `errors` array) — a client fixing one field per round trip will file a support ticket per round trip.
- **Every response carries a `Request-Id`** the client can quote and you can look up (Part 11). This single header eliminates a whole genre of support escalation.
- **Never leak internals**: no stack traces, no SQL, no upstream hostnames, no "NullPointerException" — those are information disclosure to attackers and confusion to everyone else. The 500 body is generic; the *details* go to your logs, joined by `request_id`.

---

## Part 3 — Idempotency

The user-question at the heart of this guide, answered precisely and then built out, because idempotency is the keystone property that makes Parts 8–10 possible.

### The definition

> **An operation is idempotent if performing it multiple times produces the same result as performing it once.** In mathematical terms, an operation `f` is idempotent when `f(f(x)) = f(x)` — applying it again to an already-affected system changes nothing further.

Three precise clarifications, because the definition is routinely misquoted:

1. **It's about the *effect on the system*, not the response.** `DELETE /transfers/tr_1` is idempotent even though the first call returns `204` and the second returns `404` — after either sequence, the system is in the same state: the transfer is gone. (Returning `204` for repeat deletes is also fine and arguably kinder; the *state* is the contract.)
2. **It's not the same as "safe."** `GET` is safe (no state change at all) and therefore trivially idempotent. `PUT` and `DELETE` change state — once. Safe ⊂ idempotent ⊂ all operations.
3. **"Multiple times" includes "concurrently."** Two identical requests racing on different app servers must *also* net out to once. Idempotency that only works sequentially isn't idempotency; it's luck. This is the part that makes implementation interesting (below).

Some operations are *naturally* idempotent because of their semantics: assignment (`PUT /users/42/email` with `"a@b.com"` — setting it twice is setting it once), deletion, "ensure exists" upserts, set-membership operations (add tag `urgent` to a set: adding twice is adding once). Some are naturally *not*: append, increment, **create** ("make a *new* transfer"), send-an-email, charge-a-card. The first group you get by design discipline. The second group is where the engineering lives — and it's exactly the group that involves money and side effects.

### Why it's mandatory, not nice-to-have

The distributed-systems syllogism that forces the issue:

1. Networks fail partially: a client can send a request, have it **execute successfully**, and never see the response (timeout, connection reset, gateway hiccup, process crash after commit).
2. The client now cannot distinguish "never arrived" from "executed, response lost." Its only options are: give up (and possibly lose a legitimate operation), or **retry** (and possibly duplicate it).
3. Therefore every robust client retries — your SDKs retry, service meshes retry, mobile apps retry on reconnect, queue consumers redeliver (Part 10). So your API **will** receive duplicates. The only question is whether duplicates are harmless or whether someone gets charged twice.

This generalizes to the most important sentence in distributed messaging: **exactly-once *delivery* is impossible; exactly-once *effect* is achievable — as at-least-once delivery plus idempotent processing.** Every system that appears to offer exactly-once semantics (Kafka transactions, payment processors, your bank) is doing deduplication somewhere. Enterprise-grade means you do it on purpose.

### Idempotency keys: making POST retryable

`POST /transfers` creates a *new* transfer per call — that's its meaning, so two calls legitimately make two transfers. To let a client safely retry the *same logical* creation, the client attaches a unique key identifying the logical operation, and the server deduplicates on it. This is the **`Idempotency-Key`** pattern (Stripe popularized it; an IETF draft standardizes the header):

```http
POST /v1/transfers HTTP/1.1
Authorization: Bearer sk_live_…
Idempotency-Key: 0d1aafc8-9c5e-4b7e-b9d2-2f6f3a9e4c11
Content-Type: application/json

{ "amount": 2500, "currency": "usd", "destination": "acct_7Hq2" }
```

Contract, from the server's perspective:

- **First time this key is seen** (per caller — keys are scoped to the authenticated principal, or one tenant could poison another's keys): execute the request, **store the result keyed by the idempotency key**, return it.
- **Same key again**: do not re-execute; **replay the stored response** — same status code, same body. The client can't tell the difference, which is the point.
- **Same key, *different* request body**: this is a client bug, not a retry. Detect it (store a hash of the body alongside the key) and reject with `422`/`409` and an unambiguous error code — silently returning the old response to a *different* request hides corruption.
- **Same key while the first attempt is still executing**: the race case. Don't run it twice in parallel; either block briefly or return `409 Conflict` with a "retry shortly" error so the client backs off and re-polls the same key.
- **Keys expire.** Store them with a TTL (24h is common, Stripe's choice; long enough to cover any sane retry horizon, short enough to bound storage). Document the window.

### Implementing it properly

The naive version — `if (seen(key)) return cached; else execute(); save(key)` — has a time-of-check/time-of-use race: two concurrent duplicates both pass the `seen()` check. The fix is to make **key reservation atomic and first**, using a uniqueness guarantee from your store. With SQL:

```sql
CREATE TABLE idempotency_keys (
  key         text NOT NULL,
  principal   text NOT NULL,           -- scope keys per API client
  body_hash   text NOT NULL,
  state       text NOT NULL,           -- 'in_progress' | 'completed'
  status_code int,
  response    jsonb,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (principal, key)
);
```

```typescript
// Fastify-style middleware. The unique-constraint INSERT is the linchpin:
// exactly one concurrent duplicate wins the reservation.
async function withIdempotency(req: Request, reply: Reply, execute: () => Promise<Result>) {
  const key = req.headers['idempotency-key'];
  if (!key) return execute();                       // header optional; document it as
                                                    // required for money-moving routes
  const principal = req.auth.clientId;
  const bodyHash = sha256(req.rawBody);

  const inserted = await db.tryInsert('idempotency_keys', {
    key, principal, body_hash: bodyHash, state: 'in_progress',
  }); // INSERT ... ON CONFLICT DO NOTHING, returns whether we won

  if (!inserted) {
    const existing = await db.get('idempotency_keys', { principal, key });
    if (existing.body_hash !== bodyHash) {
      return reply.code(422).send(problem('idempotency_key_reused',
        'This Idempotency-Key was already used with a different request body.'));
    }
    if (existing.state === 'in_progress') {
      return reply.code(409).header('retry-after', '1').send(problem('request_in_flight',
        'A request with this Idempotency-Key is still being processed. Retry shortly.'));
    }
    return reply.code(existing.status_code).send(existing.response);   // replay
  }

  const result = await execute();                   // the actual create
  await db.update('idempotency_keys', { principal, key }, {
    state: 'completed', status_code: result.status, response: result.body,
  });
  return reply.code(result.status).send(result.body);
}
```

Hard-won details the sketch glosses over, in the order they'll bite you:

- **Put the business effect and the key update in one transaction** when both live in the same database — otherwise a crash between "transfer committed" and "key marked completed" leaves an `in_progress` key whose retry would double-execute. If the effect is *external* (charging a card via a processor), you can't have one transaction; instead, *propagate the key downstream* (call the processor with the same idempotency key — Stripe et al. accept one precisely for this) so the retry of your half safely retries their half too. Idempotency composes by **passing keys through the call chain**.
- **Crashed `in_progress` keys need a recovery story**: a TTL after which the key is considered abandoned and the operation is *re-verified* (check whether the transfer actually exists — by key-derived natural ID, see below) rather than blindly re-executed.
- **Replay the failure too, selectively.** A `422 insufficient_funds` outcome is a real outcome — store and replay it. A `500` from your own bug is not a business outcome — let the retry re-execute. Rule of thumb: deterministic request-level failures are cached; transient infrastructure failures are not.
- **Who generates the key?** The client, at the *intent* boundary: one key per user-visible action (per checkout click, per workflow step), generated once and persisted alongside the intent, reused across all retries of it. A client that generates a fresh UUID per HTTP attempt has built an elaborate no-op.

### The alternative: natural idempotency by design

Before reaching for key infrastructure, check whether the operation can be *redesigned* to be idempotent on its own semantics — it's less machinery and often a better API:

- **Let clients name the resource**: `PUT /transfers/{client-chosen-id}` ("create or no-op if exists") instead of `POST /transfers`. The ID *is* the dedup key, the uniqueness constraint *is* the implementation, and reads of the key store are reads of the resource table. Google's AIPs push this direction (client-specified resource IDs on create).
- **Make updates absolute, not relative**: `{"balance_adjustment": -500}` is unretryable; `{"balance": 700, "if_version": 41}` (Part 6's optimistic concurrency) retries safely because the version check turns the second application into a no-op.
- **Make consumers dedup on event IDs**: for webhooks and queues (Part 10), the event carries a unique ID; the consumer records processed IDs and skips repeats — the same key pattern, pushed to the receiving side.

The decision rule: **anything that moves money, sends communications, or creates resources on behalf of a retrying caller needs an idempotency story in the contract** — either natural (preferred) or keyed (when "create a new X" is genuinely the semantic). Write down which, per endpoint. "We didn't think about it" is the only wrong answer.

---

## Part 4 — Versioning and Compatibility

### The prime directive: don't need to version

Versioning is the *fire escape*; compatibility discipline is the *building code*. The overwhelming majority of API evolution can and should be **additive within a version**:

Non-breaking (do freely, with a changelog entry): adding a response field; adding an *optional* request field with a backward-compatible default; adding an endpoint; adding an enum value *where you documented the tolerance rule* (Part 2); relaxing a validation; raising a limit.

Breaking (requires a new version or a managed migration): removing or renaming anything; changing a type or format; making an optional field required; tightening validation that previously accepted input; changing a default; changing error *codes* (not prose); reordering paginated results a client documented as stable; meaningfully changing latency or rate-limit behavior, if consumers were told to rely on it. Note the asymmetry — requests follow "be conservative in what you send" for clients, and your *responses* are governed by Hyrum's Law: if it was observable, somebody depends on it.

This only works if it's enforced, not aspired to: contract diffing in CI (Part 12) that fails the build on a breaking change to the OpenAPI document is worth more than any policy memo.

### When you must version

- **URI versioning** (`/v1/transfers`) is the pragmatic default for public APIs: visible in every log line and support ticket, trivially routable at the gateway, impossible for a client to invoke accidentally. Its theoretical sin (the "same resource" has two URIs) costs nothing in practice.
- **Header/date versioning** (Stripe's `Stripe-Version: 2026-05-01`, pinned per account at first use) is strictly more powerful — fine-grained, per-consumer migration, dozens of small versions instead of a giant v2 — and proportionally more machinery: version-transformation layers in the codebase, per-account pinning state, more support complexity. Adopt it if API evolution is your core business; otherwise it's overkill.
- **The major-version-as-new-product rule**: a `/v2` is a *migration project you are imposing on every consumer*. Budget it like one — parallel operation for quarters-to-years, migration guides with before/after payloads, telemetry on who's still on v1, and active outreach to the long tail. Companies that ship v2s casually accumulate zombie versions forever; the discipline is to make v2 so rare that each one is an event.

**Deprecation is a protocol, not an announcement.** Mark it in the contract (OpenAPI `deprecated: true`), in responses (`Deprecation: true` and `Sunset: <http-date>` headers — RFC 8594), in docs, and in dashboards ("your integration called 3 deprecated endpoints this week"). Then *measure* before you remove: traffic on the deprecated surface, by consumer, with the loud ones contacted directly. The sunset date you can't enforce because a top customer still depends on the endpoint was never a date; pick dates you'll honor.

---

## Part 5 — Pagination, Filtering, and Sorting

### Offset pagination is a correctness bug wearing a convenience costume

`?offset=5000&limit=50` has two failure modes that disqualify it for anything that grows or changes: **it skips or duplicates items under concurrent writes** (a row inserted before your current page shifts everything; clients walking "all transfers" silently miss some — in a reconciliation job, that's a financial discrepancy), and **it degrades as O(offset)** in most stores (the database produces and discards 5,000 rows to serve page 101).

**Cursor (keyset) pagination** fixes both: each page returns an opaque token encoding the position *by stable sort key*, and the next page is "everything after that key":

```http
GET /v1/transfers?limit=50&starting_after=tr_8MGyq4zXKj0

{
  "data": [ … 50 transfers … ],
  "has_more": true,
  "next_cursor": "Y3JlYXRlZF9hdDoyMDI2LTA2LTEwVDE0OjIzOjA1WjtpZDp0cl85…"
}
```

```sql
-- The implementation is a WHERE clause on the sort key, not an OFFSET:
SELECT * FROM transfers
WHERE (created_at, id) < ($cursor_created_at, $cursor_id)   -- id breaks ties
ORDER BY created_at DESC, id DESC
LIMIT 51;                                                    -- +1 to compute has_more
```

The rules that keep it honest: the sort key must be **stable and unique** (timestamp alone isn't — two rows in the same millisecond — so always pair it with the ID as tiebreaker); the cursor is **opaque and signed/encoded** (clients who can decode it will construct it, and then its format is API surface — Hyrum yet again); cursors **expire gracefully** (a 410 with `cursor_expired` beats silently wrong results); and **don't return total counts by default** — `COUNT(*)` over a filtered billion-row table costs more than the page itself, and the count is stale the moment it's computed. Offer it as an explicit opt-in (`?include_total=true`) with documented cost, or as an estimate.

### Filtering and sorting are allowlists, not query languages

Expose **named, documented, indexed filters** (`?status=pending&destination=acct_7Hq2&created_after=2026-06-01`), not a generic expression language. Every filter you accept is a query plan you're promising to execute at production scale; a free-form filter language (or an unfiltered GraphQL resolver — same disease) is an invitation for a consumer to invent the query your indexes never imagined, at 9am on your busiest Monday. Same for sorting: `?sort=-created_at` from an enumerated set of keys you've indexed, with the pagination cursor scheme varying accordingly. Reject unknown filter/sort parameters with a `400` listing valid ones — silently ignoring them means a typo (`craeted_after`) returns the *unfiltered* world, which in a reconciliation script is a catastrophe that looks like success.

---

## Part 6 — Concurrency Control and Consistency

### The lost update, and why read-modify-write is the crime scene

Two admins open the same customer record; both edit; both save. Whoever saves last silently destroys the other's change. No error fires anywhere — this is the **lost update**, and any API offering `GET` then `PATCH`/`PUT` has it by default.

The HTTP-native fix is **optimistic concurrency with ETags and conditional requests**:

```http
GET /v1/customers/cus_4Tz HTTP/1.1
→ 200 OK
  ETag: "v17"

PATCH /v1/customers/cus_4Tz HTTP/1.1
If-Match: "v17"
{ "email": "new@example.com" }

→ 200 OK, ETag: "v18"          # version matched; write applied
→ 412 Precondition Failed       # someone else wrote v18 first; client must
                                # re-GET, re-apply intent, retry with new ETag
```

Implementation is one integer: a `version` column incremented on every write, compared in the `UPDATE ... WHERE id = $1 AND version = $2` (zero rows updated → `412`). The contract decisions that go with it: **document which endpoints require `If-Match`** (require it on anything where lost updates hurt — silently accepting unconditional writes on a contested resource is choosing corruption as the default); return the new ETag on every write so clients can chain edits; and pair `412` with a problem body telling the client to refresh. Note the kinship with Part 3: a conditional write is *naturally idempotent* — replaying `If-Match: "v17"` after it succeeded yields `412`, not a second application, which is exactly the no-op you want from a retry. (`If-Unmodified-Since` is the timestamp cousin; use the ETag form — timestamps have resolution problems.)

For *create* races, the same idea wears a different header: `If-None-Match: *` on `PUT /resources/{client-id}` means "create only if absent" — `412` tells the caller it already exists.

### Consistency is part of the contract — say what you guarantee

Enterprise consumers build workflows across your endpoints, and they will discover your replication lag empirically unless you document it first. The questions to answer *in the docs*, per read endpoint:

- **Read-your-writes**: after `POST /transfers` returns `201`, does `GET /transfers/{id}` immediately see it? If reads go to replicas, maybe not — and a consumer's create-then-fetch pipeline breaks mysteriously, rarely, only under load. The standard mitigations: serve `GET`-after-write from the primary for a sticky window; or return the full resource from the write (Part 2) so the follow-up `GET` is unnecessary; or document the lag honestly ("list endpoints may trail writes by up to N seconds") so consumers poll with that expectation.
- **List-vs-get coherence**: can a transfer appear in `GET /transfers` before `GET /transfers/{id}` finds it (or vice versa)? Search indexes lag primaries; say so.
- **Monotonicity**: can a client observe `status: completed` and then, on the next poll, `status: processing`? Never let state visibly move backward — consumers build state machines from your statuses, and a backward transition breaks them in ways they cannot defensively code around. If your statuses can be reordered by replication, read status from a source that can't.

The honest general posture: strong consistency where the domain demands it (balances, inventory, anything compared against a limit), documented eventual consistency where it doesn't (search, analytics, activity feeds) — and the worst option is the undocumented mixture, where every consumer learns your architecture through their own incident.

---

## Part 7 — Authentication and Authorization

### Authentication: pick boring, implement precisely

For service-to-service and partner APIs, the realistic menu:

- **API keys** (`Authorization: Bearer sk_live_…`): the workhorse. Long random secrets (256 bits), **prefixed** (`sk_live_` / `sk_test_` — the prefix prevents the classic test-key-in-prod accident and enables secret scanning; GitHub's scanners find prefixed keys in public repos and tell you), **hashed at rest** like passwords (a stolen key table must not be a skeleton key), shown once at creation, **rotatable without downtime** (two keys active per principal, swap, revoke — if rotation requires a support ticket, you've guaranteed nobody rotates), and revocable instantly.
- **OAuth 2.0 client credentials** issuing short-lived JWTs: the step up when you need delegation, scopes across services, or federation with customers' identity providers. The implementation sins are all in validation: verify signature *and* `iss` *and* `aud` (a token minted for a different audience must not work here) *and* expiry; pin accepted algorithms (the `alg: none` and RS256→HS256 confusion attacks are twenty years old and still land); fetch keys via JWKS with caching and rotation handling.
- **mTLS** where the counterparty is a bank or regulator that demands it; operationally heavy (cert lifecycle), usually terminated at the gateway.

Whatever the scheme: credentials never in URLs (they land in logs, referrers, and browser history), always over TLS, with `401` for "no/invalid credentials" and `403` for "valid credentials, insufficient rights" — the distinction tells the client whether to re-authenticate or to stop.

### Authorization: the part attackers actually use

The OWASP API Security Top 10 has been led for years by **BOLA — Broken Object Level Authorization** — because it's the bug that scales: the attacker doesn't break your crypto, they increment an ID. `GET /v1/transfers/tr_8MGyq4zXKj0` with a *valid* key for tenant A must verify that `tr_8MGy…` *belongs to tenant A*, on every object, on every route, including the ones reached through relations (`/transfers/{id}/reversals/{rid}` — both IDs).

The only architecture that survives audit is **authorization as a chokepoint, not a convention**: every data access path goes through a layer that takes the authenticated principal and scopes the query (`WHERE tenant_id = $principal.tenant`), rather than two hundred handlers each remembering to check. Make the *unscoped* query the hard thing to write — a `dangerouslyUnscopedQuery()` name with a lint rule beats a code-review checklist. Defense in depth where the data layer supports it (Postgres row-level security as the backstop). And return `404`, not `403`, for objects outside the caller's tenancy — `403` confirms the ID exists, which is reconnaissance you're giving away free.

**Scopes** bound what a credential may do (`transfers:read`, `transfers:write`, `webhooks:manage`): least privilege per integration, finer-grained for partners than for first-party. Scopes complement, never replace, object-level checks — `transfers:read` says the caller may read transfers, tenancy says *which* transfers.

Multi-tenancy deserves one structural sentence: tenant isolation enforced in one place (chokepoint above), tenant ID derived from the *credential* and never from a request parameter (a `?tenant_id=` that the server trusts is BOLA with extra steps), and test suites that specifically attempt cross-tenant access on every endpoint (Part 12).

---

## Part 8 — Rate Limiting, Quotas, and Load Shedding

### Three different problems wearing one trench coat

- **Rate limiting** (requests/second) protects your *capacity* from bursts and runaway clients.
- **Quotas** (requests or resources per day/month) implement your *business model* and fairness between tenants.
- **Load shedding** (rejecting work you could normally handle, because you're degraded) protects your *survival* during incidents.

They share a status code and not much else; design them separately.

**Token bucket** is the rate-limiting algorithm to reach for: a bucket of capacity B refills at R tokens/sec; each request takes one; empty bucket → reject. It permits honest bursts (B deep) around a sustained rate (R) — matching how real clients behave (a batch job wakes up and fires 50 calls) better than fixed windows, which also suffer boundary bursts (2× the limit straddling a window edge). Implementation is small enough to read in full — the state is two numbers per key:

```typescript
// Token bucket per (principal, route-class). Atomic in Redis via Lua in
// production; the logic is this:
function tryConsume(bucket: Bucket, now: number, rate: number, capacity: number): boolean {
  const elapsed = (now - bucket.updatedAt) / 1000;
  bucket.tokens = Math.min(capacity, bucket.tokens + elapsed * rate);  // refill
  bucket.updatedAt = now;
  if (bucket.tokens < 1) return false;
  bucket.tokens -= 1;
  return true;
}
```

Key by **principal** (never IP alone — corporate NATs put a thousand legitimate users behind one address), with separate classes for cheap reads vs expensive writes vs auth attempts (the latter limited aggressively — credential stuffing is a rate-limiting problem).

### The contract side: 429 done right

A rate limit a client can't cooperate with is just an outage with paperwork. The response must teach the client to behave:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 7
RateLimit-Limit: 100
RateLimit-Remaining: 0
RateLimit-Reset: 7
Content-Type: application/problem+json

{ "code": "rate_limited", "detail": "Limit is 100 requests/minute per API key.", … }
```

`Retry-After` is the load-bearing header — well-built SDKs honor it automatically, and *your* SDKs must (Part 9). Sending the `RateLimit-*` family on *successful* responses too lets clients self-regulate before hitting the wall, which converts support tickets into client-side throttles. Document the limits, per plan, in numbers — "fair use" is not a number.

**Quotas** return the same 429 with a different code (`quota_exceeded`) and a `Reset` measured in hours, plus — the part that's product work, not engineering — dashboards and webhook alerts at 80%, because a partner discovering their monthly quota at 100% on the 12th is a relationship problem no header fixes.

**Load shedding** is `503 + Retry-After`, triggered by *your* health (queue depth, latency percentiles), not the client's behavior — and it must shed *expensively-unimportant* work first: keep health checks, payment captures, and webhook deliveries; shed analytics queries and list endpoints. A flat random 503 under pressure means your most critical consumer is exactly as degraded as your least. Combine with admission-by-priority at the gateway and you have graceful degradation; without it you have a lottery.

---

## Part 9 — Timeouts, Retries, and Resilience

### Timeouts: every call has one, chosen, not inherited

An RPC without an explicit timeout has one anyway — the kernel's, the load balancer's, someone's — chosen by whoever thought about it least. Set them deliberately, **descending along the call chain**: if your gateway allows 30s, your handler gets ~25s, its database call gets less, so that the *innermost* layer fails first with a clean error rather than the gateway slamming the door on a half-finished transaction. (That half-finished state is precisely the duplicate-generator Part 3 defends against — timeouts and idempotency are two halves of one design.) Better still, **propagate deadlines**: pass the remaining budget downstream (gRPC does this natively; for HTTP, an internal header) so a request that's already doomed stops consuming capacity.

### Retries: powerful, and a loaded weapon

The rules, each load-bearing:

- **Retry only what's safe to retry**: idempotent operations (or keyed ones — Part 3), on transient signals (timeouts, `429` honoring `Retry-After`, `502/503/504`). Never on `400/401/403/422` — the request is wrong; it will be wrong again.
- **Exponential backoff with jitter**: `delay = random(0, min(cap, base × 2^attempt))` — "full jitter." The jitter isn't decoration: a failing dependency that recovers will be met by every waiting client retrying *in phase* if their backoffs are deterministic, re-killing it on schedule — the thundering herd / retry-storm pattern that turns a 10-second blip into an hour-long incident.
- **Cap the attempts and the budget.** 2–3 attempts; and at the service level, a **retry budget** (e.g., retries may add at most 10–20% extra load): when the budget is exhausted, fail fast instead of multiplying traffic into a dying dependency. Crucially, **retry at one layer, not every layer** — if the client, the SDK, the gateway, the mesh, and the service each retry 3×, one user click becomes 243 requests at the bottom of the stack. Decide where retries live (usually: the outermost client, plus *nothing* in the middle) and disable them elsewhere.

**Circuit breakers** add the missing memory: after N consecutive failures to a dependency, stop calling it (fail fast or serve a fallback) for a cooling period, then *probe* with limited traffic before fully closing. This converts "every request waits 25s to fail" into "requests fail in 1ms while the dependency recovers" — protecting both your latency and their recovery. **Bulkheads** complete the set: per-dependency connection/concurrency pools, so the slow dependency saturates *its* pool and not your event loop, and one bad downstream can't take hostage the endpoints that never touch it.

### You own the client too

Enterprise-grade APIs ship official SDKs, and the SDK is where this part becomes real: defaults that retry idempotent calls with full jitter, honor `Retry-After`, **auto-generate idempotency keys for unsafe calls and reuse them across the SDK's own retries**, set sane timeouts, and surface `request_id` on every error object. Hand-rolled integrations copy whatever your quickstart shows — so the quickstart shows the resilient pattern, not `fetch().then(JSON.parse)`. The behavior of a thousand consumers during your next partial outage is decided by what you ship in the SDK today.

---

## Part 10 — Long-Running Operations, Webhooks, and Events

### When the work outlives the request: 202 + operation resource

Anything that takes longer than a few seconds (report generation, bulk imports, video processing, some payment rails) must not hold an HTTP connection as its progress indicator — connections die, gateways time out at fixed horizons, and a dropped response to a non-idempotent trigger is Part 3's nightmare again. The pattern:

```http
POST /v1/exports
Idempotency-Key: 7c0e…                      # triggers are exactly the requests
→ 202 Accepted                              # that need keys
  Location: /v1/operations/op_3Fk

GET /v1/operations/op_3Fk
→ 200 { "id": "op_3Fk", "status": "running", "progress": 62, … }
→ 200 { "status": "succeeded", "result": { "export_url": "…" } }
→ 200 { "status": "failed", "error": { "code": "source_unavailable", … } }
```

The operation is a real resource: pollable (with documented poll etiquette and `Retry-After` hints), listable, with terminal states that **persist long enough to be observed** (an operation that vanishes on completion strands every client that missed the moment), and errors in the same problem-shape as everywhere else. This is Google AIP-151's long-running operations pattern, and it composes with everything earlier: the trigger takes an idempotency key, the poll is a plain `GET`, the statuses obey Part 6's monotonicity rule.

### Webhooks: you, as a client, at enterprise grade

Webhooks invert the relationship — now *you* are the unreliable network caller hitting *their* server — so every discipline from Parts 3 and 9 applies in mirror image, and it's your job to make their side easy to build correctly:

- **Sign every delivery** — HMAC-SHA256 over `timestamp.payload` with a per-endpoint secret, timestamp echoed in the header and verified within a tolerance window (the timestamp kills replay; the HMAC kills forgery; constant-time comparison kills the timing oracle). Document the verification snippet in five languages; provide it in your SDKs.
- **Deliver at-least-once, and say so.** You will retry on non-2xx and timeout (with backoff and jitter, for hours-to-days, then park failures in a dead-letter state visible in the dashboard with manual redelivery). Therefore consumers **will receive duplicates**, therefore every event carries a unique `event_id`, therefore their handler must dedup on it — Part 3's definition, now in your integration guide as a requirement: *"process webhooks idempotently."*
- **Don't promise ordering.** Retries and parallel delivery reorder events; consumers who need current state should treat the event as a doorbell and `GET` the resource (the "thin event" pattern — which also keeps payloads from becoming a second, accidentally-versioned representation of your resources).
- **Respond-fast contract**: consumers should ack with `2xx` *before* processing (enqueue, then work) — a handler that does 30 seconds of work before responding will be timed out and redelivered into a duplicate storm. Put this in the docs; it's the most common webhook consumer bug.

The same at-least-once + dedup logic governs **event streams** (Kafka/SNS/etc.) if you offer them; the transport changes, the contract — unique IDs, documented redelivery, consumer idempotency, schema evolution rules matching Part 4 — does not.

---

## Part 11 — Observability and Auditability

### The request ID is the spine

One ID, generated at the edge (or accepted from the client and *echoed*), returned in every response header (`Request-Id`), attached to every log line, propagated to every downstream call (W3C `traceparent` if you're doing distributed tracing properly — do), and stored with every side effect. The payoff is the support workflow that defines enterprise-grade in practice: customer quotes `req_9f3b2c` from their error object → you reconstruct the entire request path in one query. Without it, every escalation starts with archaeology.

On top of that spine:

- **Structured logs** (JSON, one event per request at minimum: route, principal, tenant, status, latency, request ID) with **secrets and PII scrubbed by construction** — redaction in the serializer, not by hoping nobody logs the auth header. Your logs are where breaches go to become *worse* breaches.
- **RED metrics per route per consumer-class**: Rate, Errors (by status class and by *your* error code), Duration as histograms — p50/p95/p99, never averages (an average latency is a number nobody experiences). Per-tenant breakdowns turn "the API is slow" tickets into "your batch job is hitting the uncached path" answers.
- **SLOs with error budgets** rather than vanity uptime: "99.9% of authenticated requests succeed or fail with 4xx in <500ms p99, measured monthly" is a promise an enterprise customer can put in *their* runbook — and the error-budget framing tells your own team when to stop shipping features and start shipping reliability.
- **Audit logs are a different artifact than debug logs**: an immutable, queryable record of who did what to which resource when (principal, action, object, before/after where applicable) — retained per compliance schedule, exportable to the customer's SIEM. For regulated consumers this is a purchasing checklist item; bolting it on later means re-plumbing every write path, so the chokepoint from Part 7 should emit it from day one.

And the operational truth that ties back to Part 1: **your status page and incident comms are API surface.** Consumers code retry policies against your published behavior; they staff on-call against your incident history. Lying to the status page is lying to their pagers.

---

## Part 12 — Contracts, Documentation, and Testing

### The OpenAPI document is the artifact, not the afterthought

Whether you write the spec first or generate it from code annotations matters less than the non-negotiable: **the spec is in the repo, reviewed in PRs, and CI fails if the implementation drifts from it.** The spec is what SDKs are generated from, what the docs render, what mock servers serve, and what the breaking-change detector (Part 4) diffs — it's the single source the whole product hangs off. Lint it (Spectral with a ruleset encoding Part 2's conventions: naming case, error shape, pagination envelope, every operation has an error response documented) so style review is mechanical and human review is about semantics.

The testing pyramid, API-flavored:

- **Contract tests**: every endpoint's responses validate against the spec's schemas — including the *error* responses, which is where drift actually happens (the 422 nobody regenerated after refactoring validation).
- **Breaking-change gate**: `oasdiff`-style comparison against the released spec on every PR; additive passes, breaking fails the build and requires the versioning ritual (Part 4), not a sheepish merge.
- **The adversarial suite** — the tests that distinguish this guide's subject from a CRUD demo: replay every mutating request with the same idempotency key and assert single effect (Part 3); fire the same key *concurrently* and assert one winner (the race is the bug); attempt cross-tenant object access on every route with a second tenant's valid credentials (Part 7 — this suite *is* your BOLA defense); send unknown fields, wrong types, oversized payloads, malformed cursors; walk pagination under concurrent inserts and assert no skips/dupes (Part 5); kill the connection mid-request and verify the retry path.
- **Load tests against the limits you published** — the rate limits, the p99s in the SLO, the pagination depth — because a published number you've never tested is a number a customer will test for you.

**Documentation as product**: reference docs generated from the spec (so they cannot lie), a quickstart that demonstrates the *resilient* integration (idempotency keys, retry handling, webhook verification — what the quickstart shows is what every integration does, Part 9), runnable examples per language, a changelog consumers can subscribe to, and migration guides written before deprecation headers ship, not after the angry email.

---

## Part 13 — The Platform Layer and the Design-Review Checklist

### What belongs in the gateway vs the service

An API gateway (or LB + mesh stack) should own the **uniform, policy-shaped concerns**: TLS termination, authentication (validate the token, pass verified claims inward), coarse rate limiting and quota enforcement, request-ID minting, IP/geo policy, payload size caps, and the version-to-backend routing from Part 4. Services own everything requiring **domain knowledge**: authorization beyond "valid token" (object-level checks live next to data — Part 7), idempotency (it's transactional with the business effect — Part 3), validation, concurrency control. The failure mode to design against is the *smart gateway* that accumulates business logic in YAML — it becomes an unversioned, untested service that every team is afraid to touch. Gateway = policy; service = semantics.

Internal platform glue that pays for itself: a shared service template/middleware stack so every API in the company emits the same error shape, the same headers, the same metrics (consumers of *your* APIs include your own teams — uniformity is compound interest); and golden-path SDK generation so the Part 9 client behavior ships everywhere by default.

### The design-review checklist

The questions to ask of every new endpoint, in review, before it ships — each one traceable to the part that justifies it:

**Contract**
- [ ] Resource-oriented, correct method, correct status codes? (2)
- [ ] Errors: problem+json, stable `code`, all codes documented? (2)
- [ ] All fields: opaque IDs, RFC 3339 times, integer money, enum-tolerance documented? (2)
- [ ] In the OpenAPI spec, linted, breaking-change gate green? (12)

**Correctness under failure**
- [ ] What happens when this exact request arrives twice? Concurrently? *(The single highest-yield review question in this guide.)* (3)
- [ ] Mutations: naturally idempotent, or `Idempotency-Key` required and implemented atomically? Key propagated downstream? (3)
- [ ] Lost-update story: ETags/`If-Match` where contested? (6)
- [ ] Read-your-writes and staleness documented? Status transitions monotonic? (6)

**Security**
- [ ] Object-level authorization through the chokepoint — and the cross-tenant test exists? (7, 12)
- [ ] Scope defined? 404-not-403 for foreign objects? No secrets in URLs or logs? (7, 11)

**Scale and resilience**
- [ ] Cursor pagination with stable unique sort key? Filters allowlisted and indexed? (5)
- [ ] Rate-limit class assigned; 429 carries `Retry-After`? (8)
- [ ] Timeout set and inside the caller's budget? Retry-safe and marked so in the spec? (9)
- [ ] Long-running? Then 202 + operation resource, not a 90-second request. (10)

**Operations**
- [ ] Request ID in, through, and out; RED metrics; audit events for writes? (11)
- [ ] SDK updated; quickstart still shows the resilient path; changelog entry? (9, 12)

### The closing thesis

Every part of this guide is one idea applied to a different layer: **assume the failure, then make it boring.** Assume the response is lost — idempotency makes the retry boring. Assume two writers — ETags make the race boring. Assume the dependency dies — breakers and budgets make it boring. Assume the client never upgrades — compatibility discipline makes the decade boring. Demo APIs are built for the run where everything works; enterprise-grade APIs are built so that the runs where things break are indistinguishable, from the consumer's ledger, from the runs where they didn't.

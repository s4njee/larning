# Cloudflare Study Guide

A practical, depth-first guide to Cloudflare for engineers and architects who already think in cloud primitives — especially **AWS** — and want to build strong Cloudflare instincts fast.

Cloudflare is best understood in two halves. The **network/security half** (CDN, DNS, DDoS, WAF, Zero Trust, Tunnels) is what you put *in front of* infrastructure you already run anywhere. The **developer platform half** (Workers, Pages, R2, D1, KV, Durable Objects, Queues, and friends) is a place to *run and store* the application itself, at the edge, with a different cost and consistency model than a regional cloud. This guide treats both, anchors each service to its AWS analog, and shows the actual code and config you write.

Pricing, plan limits, and product availability change over time. Treat every number here as directional and use the linked Cloudflare docs as the source of truth when a figure matters operationally.

---

## How to Use This Guide

- If Cloudflare is new to you, read the sections in order. The network services (1–4) set up the mental model; the developer platform (5–13) builds on it.
- In each section, anchor on the **AWS Mental Model** first, then learn the Cloudflare service, then internalize the **Key Differences** — that is where the real architecture decisions live.
- Treat the AWS mappings as *directional, not literal*. Cloudflare and AWS frequently solve the same problem with a different consistency model, billing dimension, or deployment unit. The differences are the point.
- Run the **Practice** exercises. Cloudflare's free tiers are generous enough that almost every exercise here is free to do for real with a single `wrangler` install.

### The One Tool You Need: Wrangler

Almost everything on the developer platform is driven by **Wrangler**, Cloudflare's CLI (the rough analog of the `aws` CLI + SAM/CDK combined for the Workers world).

```bash
npm install -g wrangler        # or: npm create cloudflare@latest
wrangler login                 # OAuth into your account
wrangler whoami                # confirm account + zones
wrangler deploy                # deploy the current Worker
wrangler dev                   # run a Worker locally on a real edge runtime (workerd)
wrangler tail                  # live-stream production logs (like `aws logs tail --follow`)
```

Configuration lives in `wrangler.toml` (or `wrangler.jsonc`), which is the Workers equivalent of a SAM/CloudFormation template — it declares the Worker plus every **binding** (resource attachment) the code can use.

---

## Cloudflare ↔ AWS Translation Map

Internalize this table early. The rest of the guide elaborates each row.

| Cloudflare | Closest AWS | The difference that matters |
|---|---|---|
| CDN | CloudFront | Every PoP is a full PoP; unmetered egress; on by default once DNS is proxied |
| DNS | Route 53 | Authoritative DNS is free; fastest-globally; orange-cloud proxy toggle |
| DDoS Protection | AWS Shield Standard/Advanced | L3–L7, unmetered, no surge pricing, included free |
| WAF | AWS WAF | One expression language across products; ML attack score |
| Workers | Lambda@Edge / CloudFront Functions / Lambda | V8 isolates, ~0 cold start, runs in every PoP, per-request not per-GB-second |
| Pages | Amplify Hosting / S3+CloudFront | Git-driven, unlimited preview deploys, unlimited static bandwidth |
| R2 | S3 | **Zero egress fees**; S3-API compatible |
| D1 | Aurora Serverless v2 / RDS | SQLite per-database; designed for many small DBs, not one big one |
| KV | DynamoDB (global tables) / DAX | Eventually consistent (~60s), read-optimized, edge-cached |
| Durable Objects | (no direct analog) DynamoDB + single-writer actor | Strongly consistent, single-threaded, co-located compute+storage |
| Queues | SQS | Pull or push to a Worker consumer; no separate egress |
| Hyperdrive | RDS Proxy + global cache | Pools + caches connections to *your existing* Postgres/MySQL |
| Vectorize | OpenSearch / Kendra vector | Edge-native vector DB for RAG |
| Workers AI | Bedrock / SageMaker endpoints | Serverless GPU inference billed per-neuron, in many PoPs |
| Zero Trust / Access | AWS Verified Access + Client VPN + Cognito | Identity-aware app access replacing the VPN perimeter |
| Tunnels | (no direct analog) SSM + reverse proxy | Outbound-only connector; origin has no public IP or open ports |
| Stream | IVS + MediaConvert + MediaLive | End-to-end video, no separate egress |
| Images | S3 + Lambda/CloudFront image optimization | Storage + URL-based transforms in one product |
| Load Balancing | Route 53 health checks + ELB/Global Accelerator | DNS- and proxy-layer steering with health checks |
| Argo Smart Routing | Global Accelerator | Congestion-aware path selection over Cloudflare's backbone |

---

## Table of Contents

1. [CDN / Content Delivery Network](#1-cdn--content-delivery-network)
2. [DNS](#2-dns)
3. [DDoS Protection](#3-ddos-protection)
4. [WAF (Web Application Firewall)](#4-waf-web-application-firewall)
5. [Workers (Serverless Compute)](#5-workers-serverless-compute)
6. [Pages (Static & Full-Stack Hosting)](#6-pages-static--full-stack-hosting)
7. [R2 (Object Storage)](#7-r2-object-storage)
8. [D1 (Serverless SQL Database)](#8-d1-serverless-sql-database)
9. [KV (Key-Value Store)](#9-kv-key-value-store)
10. [Durable Objects (Stateful Coordination)](#10-durable-objects-stateful-coordination)
11. [Queues, Hyperdrive, Vectorize & Workers AI](#11-queues-hyperdrive-vectorize--workers-ai)
12. [Zero Trust / Access](#12-zero-trust--access)
13. [Cloudflare Tunnels](#13-cloudflare-tunnels)
14. [Images & Stream (Media)](#14-images--stream-media)
15. [Load Balancing](#15-load-balancing)
16. [Rate Limiting](#16-rate-limiting)
17. [Argo Smart Routing](#17-argo-smart-routing)
18. [Architecture Patterns](#18-architecture-patterns)
19. [Common Pitfalls & Gotchas](#19-common-pitfalls--gotchas)
20. [Plan Comparison & Pricing](#20-plan-comparison--pricing)
21. [Decision Trees](#21-decision-trees)

---

## 1. CDN / Content Delivery Network

Cloudflare's CDN caches content at **330+ data centers** worldwide, serving it from the location closest to the end user. Cloudflare acts as a **reverse proxy**: once a DNS record is proxied (orange cloud), traffic flows through Cloudflare's network before reaching your origin.

### AWS Mental Model

- **Amazon CloudFront** with an S3 or ALB origin, behaviors, and cache policies.
- Key contrast: CloudFront bills egress per GB by region and meters requests; Cloudflare CDN bandwidth is **unlimited and unmetered on every plan**, and a Cloudflare PoP is a *full* PoP (compute + cache + security), not a thin edge cache.

### Key Features

- **Anycast IP routing** — all data centers advertise the same IPs; normal BGP routing sends each user to the nearest PoP, so there are no region-specific endpoints to manage.
- **Tiered Cache** — PoPs are organized into lower/regional/upper tiers; a miss checks other Cloudflare data centers before hitting origin, which collapses origin fetches for long-tail assets. Included on all plans.
- **Cache Reserve** — uses R2 as a persistent lower cache tier with long retention for valuable-but-infrequent objects.
- **Cache Rules** — move past default extension-based caching: set TTLs, eligibility, and custom cache keys by route/header/cookie/query.
- **Tiered Cache Topology + Argo** — routing intelligence picks the best upper-tier PoP adaptively.

### How Caching Actually Decides

The cache key plus the response's cacheability headers determine hits. The mental model:

```
Client → nearest PoP → (cache HIT? serve) 
                     → (MISS → upper tier → MISS → origin) → cache per Cache-Control/Cache Rules → serve
```

- Cloudflare respects `Cache-Control`/`Expires` for *edge* TTL, but you override per route with **Cache Rules**. `cf-cache-status` response header (`HIT`, `MISS`, `EXPIRED`, `DYNAMIC`, `BYPASS`) is your primary debugging signal — the analog of CloudFront's `X-Cache: Hit from cloudfront`.
- By default Cloudflare caches static extensions and treats HTML as `DYNAMIC` (uncached) unless you opt in with a Cache Rule + "Cache Everything."

### Key Differences from AWS

- No "distribution" object to create and wait ~15 min to deploy. Caching is on the moment a record is proxied; rule changes propagate in seconds.
- No per-region price list to reason about — the egress line item that dominates CloudFront bills does not exist.
- Cache invalidation (purge) is free and effectively instant; CloudFront invalidations are metered beyond a free allotment.

### Pricing

CDN is included on **all plans**. Bandwidth is **unlimited and unmetered**. Cache Reserve (R2-backed) and Argo Smart Routing are paid add-ons.

### Practice

- Proxy a domain, then `curl -sI https://yoursite/asset.js` and read `cf-cache-status` before and after a second request.
- Write a Cache Rule that caches HTML for 5 minutes only for anonymous users (no auth cookie) and bypasses cache when a session cookie is present.
- Compare the all-in monthly cost of serving 50 TB of images from CloudFront vs. Cloudflare CDN + R2.

Docs: [Cache](https://developers.cloudflare.com/cache/), [Cache Rules](https://developers.cloudflare.com/cache/how-to/cache-rules/).

---

## 2. DNS

Cloudflare DNS is a fast, resilient **authoritative DNS service**. Delegating your nameservers makes Cloudflare the source of truth for the zone. It is consistently among the fastest authoritative providers globally.

### AWS Mental Model

- **Amazon Route 53** hosted zones + records, health checks, and alias records.
- Route 53 alias records (apex → ALB/CloudFront) map to Cloudflare's **CNAME flattening**; Route 53 charges per hosted zone + per million queries, while Cloudflare authoritative DNS is **free**.

### Key Features

- **Authoritative DNS** — free on all plans, once nameservers are delegated.
- **DNSSEC** — cryptographic chain of trust from the parent zone; multi-signer supported.
- **CNAME flattening** — returns A/AAAA for CNAME lookups at the zone apex, so SaaS endpoints and load-balanced hostnames work at the bare domain.
- **Proxy status (orange vs. gray cloud)** — proxied records return Cloudflare anycast IPs (enabling CDN/WAF/DDoS and hiding your origin); DNS-only records expose the origin IP directly.
- **Foundation DNS / DNS Firewall** — Enterprise resiliency and upstream-protecting query proxy.

### The Orange Cloud Is the Whole Game

This is the single most important Cloudflare concept and has no Route 53 equivalent:

- **Orange cloud (proxied):** clients resolve to Cloudflare IPs. CDN, WAF, DDoS L7, Bot Management, Workers routes, Access — all of it — only apply to proxied records. Your origin IP is hidden.
- **Gray cloud (DNS only):** pure resolution; the record points straight at your origin. Required for protocols Cloudflare's proxy doesn't front (most mail/SMTP, some non-HTTP services).

Forgetting to proxy a record is the most common reason "my WAF rule isn't firing."

### Key Differences from AWS

- Authoritative DNS is free and unmetered vs. Route 53's per-zone + per-query billing.
- The proxy toggle fuses DNS with security/CDN; in AWS those are separate services (Route 53, CloudFront, AWS WAF, Shield) wired together.
- **Cloudflare Registrar** sells domains at wholesale cost (no markup), unlike Route 53 Domains' retail pricing.

### Pricing

Free on all plans. Foundation DNS and DNS Firewall are Enterprise/add-ons.

### Practice

- Move a domain's nameservers to Cloudflare, enable DNSSEC, and verify the DS record at the registrar.
- Set up apex `example.com` proxied to an origin and confirm via `dig` that clients see Cloudflare IPs, not your origin.
- Identify which of your records *must* stay gray-cloud (hint: check your MX/mail records).

Docs: [DNS](https://developers.cloudflare.com/dns/), [Registrar](https://developers.cloudflare.com/registrar/).

---

## 3. DDoS Protection

Cloudflare automatically detects and mitigates DDoS attacks across **layers 3, 4, and 7**. Protection is always-on, unmetered, and unlimited.

### AWS Mental Model

- **AWS Shield Standard** (free, automatic L3/L4) + **AWS Shield Advanced** (paid, ~$3,000/mo + data, with cost protection and DRT access).
- Cloudflare folds Shield-Advanced-style protection into all plans with **no surge pricing during an attack** — there is no bill spike to insure against, so there's no "cost protection" product to buy.

### Key Features

- **Autonomous DDoS edge** — detection and mitigation start at the PoP before volumetric traffic reaches your origin.
- **Managed rulesets** — HTTP DDoS and Network-layer DDoS managed rules give a strong baseline.
- **Adaptive Protection** — learns your traffic baseline so legitimately high request rates aren't misread as attacks.
- **Advanced (Enterprise)** — stateful inspection and traffic profiling for TCP/DNS attacks; override rules to tune sensitivity per endpoint.

### Key Differences from AWS

- No tiered product to purchase for serious protection; the strong defenses are on by default.
- No attack-driven bill: volumetric traffic absorbed at the edge does not generate egress charges the way an unmitigated flood against an ALB/CloudFront can.
- L7 mitigation shares the same Rules engine as the WAF, so overrides are expressed in the familiar expression language.

### Pricing

Included **free and unlimited on all plans**. No surge pricing during attacks.

### Practice

- Find the **Security → Events** view and identify which managed DDoS rules have fired on your zone.
- Write a DDoS override that raises sensitivity on `/login` while leaving static asset paths untouched.

Docs: [DDoS Protection](https://developers.cloudflare.com/ddos-protection/).

---

## 4. WAF (Web Application Firewall)

The Cloudflare WAF filters web and API requests against rulesets, protecting against the **OWASP Top 10** (XSS, SQLi, etc.) and app-specific abuse.

### AWS Mental Model

- **AWS WAF** with WebACLs, managed rule groups (AWS Managed Rules, OWASP), and rate-based rules attached to CloudFront/ALB/API Gateway.
- Big structural difference: AWS WAF prices per WebACL + per rule + per million requests; Cloudflare WAF custom rules are included by plan, and **one expression language** (the Rules Language) spans WAF, rate limiting, cache rules, transform rules, and DDoS overrides.

### The Rules Language (learn this once, use it everywhere)

```
# Block API traffic from outside the US that lacks a valid API key header
(http.request.uri.path matches "^/api/" and ip.geoip.country ne "US" and not http.request.headers["x-api-key"][0] matches "^sk_live_")

# Managed Challenge logins with a high bot likelihood
(http.request.uri.path eq "/login" and cf.bot_management.score lt 30)

# Skip WAF for a trusted office IP
(ip.src in {203.0.113.10 203.0.113.11})
```

Common fields: `ip.src`, `ip.geoip.country`, `http.request.uri.path`, `http.request.method`, `http.host`, `http.request.headers[...]`, `cf.bot_management.score`, `cf.waf.score` (attack score). Actions: **Block, Managed Challenge, JS Challenge, Skip, Log**. Rules evaluate in order; a `Block` stops evaluation.

### Key Features

- **Custom Rules** — your precise control plane using the Rules Language.
- **Managed Rules** — Cloudflare Managed Ruleset + OWASP Core Rule Set, updated for zero-days.
- **WAF Attack Score** — ML scores each request's attack likelihood, so you can challenge ambiguous traffic instead of bluntly blocking a coarse signature.
- **Rate Limiting Rules** — rate logic expressed in the same engine (see §16).
- **Malicious Uploads Detection / Sensitive Data Detection** — payload-aware scanning.
- **Security Analytics** — where you tune false positives before promoting Log → Challenge → Block.

### Key Differences from AWS

- One expression language vs. AWS WAF's JSON statement nesting; far faster to author and reason about.
- ML attack score is built in; in AWS you'd reach for managed rule groups + Fraud Control/Bot Control add-ons.
- Challenge actions (Managed/JS Challenge) are first-class; AWS WAF's CAPTCHA/Challenge exists but the Cloudflare challenge platform is more central to the model.

### Pricing

| Feature | Free | Pro ($20/mo) | Business ($200/mo) | Enterprise |
|---------|------|--------------|---------------------|------------|
| Custom rules | Limited | Yes | Yes | Yes |
| Managed Rules | No | Yes | Yes | Yes |
| Attack Score (ML) | No | No | Yes | Yes |
| Account-level rulesets | No | No | No | Yes |

### Practice

- Write a custom rule that Managed-Challenges any `POST /login` with a bot score under 30, in Log mode first, then read Security Analytics before switching to Block.
- Geo-block all countries except a target list for `/admin`, with a Skip exception for your office IP.
- Translate an existing AWS WAF rate-based rule into a Cloudflare Rate Limiting Rule.

Docs: [WAF](https://developers.cloudflare.com/waf/), [Rules language fields](https://developers.cloudflare.com/ruleset-engine/rules-language/fields/).

---

## 5. Workers (Serverless Compute)

Cloudflare Workers runs JavaScript/TypeScript/Wasm at the edge in 330+ data centers, within milliseconds of users, with near-zero cold starts.

### AWS Mental Model

- A blend of **Lambda**, **Lambda@Edge**, and **CloudFront Functions**, but the execution model is fundamentally different.
- Lambda uses per-region micro-VMs (Firecracker) with cold starts measured in 100s of ms and billing in GB-seconds. Workers use **V8 isolates** — the same sandbox Chrome uses for tabs — so startup is ~0 ms, there's no per-invocation VM, and billing is per-request + CPU-time. A Worker runs in *every* PoP automatically; there's no region to pick.

### The Anatomy of a Worker

Modern Workers use the ES modules `fetch` handler. `env` carries every binding; `ctx` controls lifecycle (e.g., `waitUntil`).

```js
// src/index.js
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Edge middleware: auth, redirects, A/B, response shaping
    if (url.pathname === "/health") return new Response("ok");

    // Read from a KV binding
    const flag = await env.FLAGS.get("new-checkout");

    // Cache an expensive origin fetch at the edge without blocking the response
    const res = await fetch("https://origin.example.com" + url.pathname, request);
    ctx.waitUntil(logRequest(env, request));   // fire-and-forget after response
    return new Response(res.body, res);
  },

  // Cron Triggers — the edge-native scheduled job (cf. EventBridge Scheduler → Lambda)
  async scheduled(event, env, ctx) {
    ctx.waitUntil(reindex(env));
  },
};
```

```toml
# wrangler.toml — the deployment unit + all bindings
name = "my-worker"
main = "src/index.js"
compatibility_date = "2025-01-01"

[[kv_namespaces]]
binding = "FLAGS"
id = "xxxxxxxxxxxxxxxxxxxxxxxx"

[[r2_buckets]]
binding = "UPLOADS"
bucket_name = "user-uploads"

[[d1_databases]]
binding = "DB"
database_name = "app"
database_id = "yyyyyyyy-yyyy-yyyy"

[triggers]
crons = ["0 * * * *"]   # hourly
```

```bash
wrangler dev      # local edge runtime
wrangler deploy   # ship to every PoP in seconds
wrangler tail     # live logs
```

### Key Features

- **V8 isolates** — near-instant startup, no container/VM lifecycle.
- **Bindings** — typed handles to KV, R2, D1, Durable Objects, Queues, Vectorize, Workers AI, service-to-service bindings, and secrets. No SDK client construction or credential plumbing.
- **Cron Triggers** — scheduled execution (`scheduled` handler).
- **Static Assets** — ship a SPA/static files alongside Worker logic as one deployment.
- **Workflows** — durable, multi-step, retryable execution (cf. Step Functions).
- **Smart Placement** — Cloudflare can run the Worker near your origin/DB instead of near the user when that's faster for DB-heavy code.
- **Containers** — newer support for container workloads alongside isolate-based Workers.

### Limits

| | Free | Paid ($5/mo) |
|---|---|---|
| Requests | 100,000/day | 10M included/mo, then $0.30/million |
| CPU time | 10 ms | 30 s (configurable up to 5 min) |
| Memory | 128 MB | 128 MB |
| Worker size | 3 MB | 10 MB |
| Subrequests | 50/request | 1,000/request |

Note the distinction: **wall-clock time can be long** (you can `await` slow origins), but **CPU time** is what's metered and capped. This is the opposite of Lambda, where you pay for wall-clock GB-seconds.

### Key Differences from AWS

- No cold starts, no provisioned concurrency, no region selection.
- 128 MB memory ceiling and the CPU-time model make Workers ideal for I/O-bound glue, middleware, APIs, and request shaping — *not* heavy in-memory compute (use Containers, or call out to a real backend).
- Bindings replace IAM-role-scoped SDK calls; access is granted by declaring the binding, not by signing requests.
- One global deployment vs. per-region Lambda + Lambda@Edge replication.

### Pricing

$5/month Workers Paid: 10M requests + 30M CPU-ms included, then $0.30/million requests and $0.02/million CPU-ms. A generous free tier (100K req/day) needs no subscription.

### Practice

- Build a Worker that adds security headers and strips `Server` from every origin response.
- Implement edge A/B testing: bucket users by a cookie, persist the bucket in KV, and route to two origins.
- Add a Cron Trigger that aggregates yesterday's request logs into a KV summary.
- Use `wrangler tail` to watch a deploy in production and trigger an error to see the trace.

Docs: [Workers](https://developers.cloudflare.com/workers/), [Bindings/Runtime APIs](https://developers.cloudflare.com/workers/runtime-apis/), [Workflows](https://developers.cloudflare.com/workflows/).

---

## 6. Pages (Static & Full-Stack Hosting)

Cloudflare Pages deploys static sites and full-stack apps, integrating with Git for automatic builds and deploys.

### AWS Mental Model

- **AWS Amplify Hosting**, or the hand-rolled **S3 + CloudFront + CodePipeline** pattern.
- Pages bundles Git CI/CD, global CDN, unlimited preview URLs, and Workers-powered functions into one product with **unlimited static bandwidth** — versus assembling and paying for each AWS piece separately.

### Key Features

- **Git integration** — auto-deploy on push to GitHub/GitLab; branches/commits are deployment units.
- **Preview deployments** — a unique URL per branch/commit, unlimited, for QA and stakeholder review.
- **Pages Functions** — server-side functions (Workers under the hood) for API routes, auth hooks, SSR.
- **Unlimited static bandwidth** on all plans.
- **Custom domains** — Free: 100, Pro: 250, Business: 500.

### Note on Convergence

Cloudflare is steering new full-stack projects toward **Workers + Static Assets** (a Worker that also serves static files), which unifies the Pages and Workers stories. For greenfield work, evaluate `wrangler` + Static Assets; Pages remains excellent for Git-driven static/JAMstack sites.

### Limits

| | Free | Paid |
|---|---|---|
| Builds | 500/month | 5,000/month |
| Files | 20,000 | 20,000 |
| Max file size | 25 MiB | 25 MiB |

### Key Differences from AWS

- Preview-per-branch is built in and free; in AWS you script it with Amplify or per-PR CloudFront/S3 stacks.
- Functions share Workers quotas/runtime, so your "frontend host" and "edge backend" are the same platform.
- Static egress is free and unlimited vs. CloudFront per-GB.

### Pricing

Generous free tier (unlimited static bandwidth, unlimited sites). Functions follow Workers pricing.

### Practice

- Connect a repo, push to a branch, and open the preview URL for that commit.
- Add a Pages Function at `/functions/api/hello.js` that reads a KV value and returns JSON.
- Compare the monthly cost of hosting a 1 TB/mo-traffic static site on Pages vs. S3+CloudFront.

Docs: [Pages](https://developers.cloudflare.com/pages/), [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/).

---

## 7. R2 (Object Storage)

S3-compatible object storage with **zero egress fees** — the headline differentiator. Built for unstructured data: media, backups, datasets, user uploads.

### AWS Mental Model

- **Amazon S3**, almost exactly — same API surface, similar durability story.
- The economic difference is structural: S3 charges per-GB **egress** (often the dominant line item) plus per-request; R2 charges storage + operations but **$0 egress**. For read-heavy public delivery, cross-cloud access, or analytics reads, this often inverts the cost model.

### S3-Compatible Access + Worker Binding

R2 speaks the S3 API, so existing tooling works by changing the endpoint:

```bash
# rclone / aws cli against R2's S3 endpoint
aws s3 cp ./big.parquet s3://my-bucket/big.parquet \
  --endpoint-url https://<accountid>.r2.cloudflarestorage.com
```

From a Worker, the native binding skips signing entirely:

```js
export default {
  async fetch(request, env) {
    const key = new URL(request.url).pathname.slice(1);

    if (request.method === "PUT") {
      await env.UPLOADS.put(key, request.body, {
        httpMetadata: { contentType: request.headers.get("content-type") },
      });
      return new Response("stored", { status: 201 });
    }

    const obj = await env.UPLOADS.get(key);
    if (!obj) return new Response("not found", { status: 404 });
    return new Response(obj.body, {
      headers: { "content-type": obj.httpMetadata?.contentType ?? "application/octet-stream",
                 "etag": obj.httpEtag },
    });
  },
};
```

### Key Features

- **S3 API compatible** — works with `aws s3`, `rclone`, Terraform, most S3 SDKs.
- **Zero egress fees** — no data-transfer-out charges.
- **Workers binding** — native, signature-free access from edge code.
- **Public buckets / custom domains** — serve files directly, optionally fronted by CDN + WAF.
- **Storage classes** — Standard and Infrequent Access (30-day minimum).
- **11 nines durability**; **Super Slurper** (bulk S3/GCS migration) and **Sippy** (incremental, serve-from-R2-backfill-from-source) migration tools.
- **Object lifecycles** — auto-transition/expire.

### Pricing

| | Free Tier | Standard | Infrequent Access |
|---|---|---|---|
| Storage | 10 GB/month | $0.015/GB-month | $0.01/GB-month |
| Class A ops (writes) | 1M/month | $4.50/million | $9.00/million |
| Class B ops (reads) | 10M/month | $0.36/million | $0.90/million |
| Egress | Free | **Free** | **Free** |

### Key Differences from AWS

- No egress charge is the whole pitch — model your read volume to see the delta vs. S3.
- No regional bucket placement decision (R2 is distributed); you lose S3's fine-grained region/replication controls but gain simplicity.
- Pair R2 with Workers for upload APIs and with CDN/Cache Reserve for delivery; in AWS that's S3 + Lambda + CloudFront wired together.

### Practice

- `rclone` a folder into R2 and serve it via a public bucket + custom domain behind the CDN.
- Build the Worker upload/download API above; add a WAF rule limiting upload size by path.
- Calculate the break-even traffic point where R2 beats S3 for a 5 TB media library.

Docs: [R2](https://developers.cloudflare.com/r2/), [Migration](https://developers.cloudflare.com/r2/data-migration/).

---

## 8. D1 (Serverless SQL Database)

Cloudflare's managed serverless SQL database with **SQLite semantics**, designed to scale *horizontally* across many small databases (per-tenant, per-user), not as one large primary.

### AWS Mental Model

- Closest billing/scaling analog: **Aurora Serverless v2** (scale-to-zero, pay for use) — but the engine is SQLite, not MySQL/Postgres, and the *intended topology* is the opposite: many small DBs rather than one big cluster. For the "huge single relational store," D1 is the wrong tool; reach for RDS/Aurora or use Hyperdrive (§11) in front of your own Postgres.

### Querying via the Worker Binding

D1 uses a prepared-statement API with `.bind()` for parameters:

```js
export default {
  async fetch(request, env) {
    const { results } = await env.DB
      .prepare("SELECT id, email FROM users WHERE tenant_id = ? AND active = 1")
      .bind("tenant_42")
      .all();

    // Batched transaction
    await env.DB.batch([
      env.DB.prepare("INSERT INTO audit(event) VALUES (?)").bind("login"),
      env.DB.prepare("UPDATE users SET last_seen = ? WHERE id = ?").bind(Date.now(), 7),
    ]);

    return Response.json(results);
  },
};
```

```bash
wrangler d1 create app
wrangler d1 execute app --command "CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT, tenant_id TEXT, active INT, last_seen INT)"
wrangler d1 migrations apply app     # versioned migrations
```

### Key Features

- **SQLite SQL compatibility** — standard relational queries.
- **Time Travel** — point-in-time restore to any minute within the last 30 days.
- **Read replication** — automatic read replicas across global regions at no extra cost (Sessions API for read-your-writes consistency).
- **Scale to zero** — no charge when idle.
- **No egress charges**.

### Limits & Design Constraints

- **10 GB max per database** (hard) — reinforces the shard-by-tenant design.
- **Single-writer per database** — throughput depends on query duration; chatty/slow queries hurt concurrency more visibly than on a multi-core RDS instance.
- Accessed via Worker binding or HTTP API.

### Pricing

| | Free | Paid |
|---|---|---|
| Rows read | 5M/day | 25B/month, then $0.001/million |
| Rows written | 100K/day | 50M/month, then $1.00/million |
| Storage | 5 GB total | 5 GB included, then $0.75/GB-month |

### Key Differences from AWS

- Billed per **rows read/written**, not per instance-hour — a genuinely different mental model from RDS/Aurora.
- The 10 GB/database cap is a design signal, not just a limit: architect for many DBs.
- No VPC, no connection pool sizing, no failover groups — but also none of Aurora's horizontal write scale.

### Practice

- Create a D1 DB, write versioned migrations, and run a parameterized query from a Worker.
- Design a per-tenant sharding scheme: how do you map a request to the right D1 database?
- Use Time Travel to restore after an intentional bad `UPDATE`.

Docs: [D1](https://developers.cloudflare.com/d1/), [D1 read replication](https://developers.cloudflare.com/d1/best-practices/read-replication/).

---

## 9. KV (Key-Value Store)

A global, low-latency key-value store optimized for **read-heavy** workloads. Eventually consistent, replicated and cached across the edge.

### AWS Mental Model

- **DynamoDB global tables** for the read-heavy/global-replication shape, plus a flavor of **DAX**/edge caching for hot reads.
- Critical contrast: KV is **eventually consistent** — writes propagate globally within ~60 seconds — and is read-optimized, whereas DynamoDB offers strongly consistent reads within a region. If you need read-your-writes or coordination, KV is the wrong tool (use Durable Objects, §10).

```js
// Read-hot config / feature flags / cached lookups
await env.CONFIG.put("feature:checkout-v2", "on", { expirationTtl: 3600 });
const v = await env.CONFIG.get("feature:checkout-v2");        // fast, edge-cached
const obj = await env.CONFIG.get("session:abc", { type: "json" });
const { keys } = await env.CONFIG.list({ prefix: "feature:" });
```

### Key Features

- **Global distribution** — reads served from edge cache, low latency nearly everywhere.
- **Eventual consistency** — writes visible globally within ~60s.
- **Simple API** — get/put/delete/list; optional JSON metadata; TTL expiration; bulk ops.

### When to Use KV vs. Other Storage

| Use case | Best choice |
|----------|-------------|
| Read-heavy, infrequently changing (config, flags, cached lookups) | **KV** |
| Strong consistency / coordination | **Durable Objects** |
| Relational/SQL queries | **D1** |
| Large files, media, backups | **R2** |

### Pricing

| | Free | Paid |
|---|---|---|
| Reads | 100,000/day | 10M/month, then $0.50/million |
| Writes | 1,000/day | 1M/month, then $5.00/million |
| Storage | 1 GB | 1 GB, then $0.50/GB-month |

### Key Differences from AWS

- Writes are comparatively expensive and slow to converge — KV punishes write-heavy or per-request-write patterns. Design for read-mostly.
- No query language or secondary indexes; it's `get`/`list(prefix)`. Model keys deliberately.

### Practice

- Store feature flags in KV and read them in the edge A/B Worker from §5.
- Demonstrate eventual consistency: write a key, then read it from two distant locations and observe convergence.
- Decide which of KV / D1 / Durable Objects fits a shopping-cart counter, and justify it.

Docs: [KV](https://developers.cloudflare.com/kv/).

---

## 10. Durable Objects (Stateful Coordination)

Durable Objects (DOs) give you a **single, strongly-consistent, stateful instance** addressed by ID, with storage co-located with compute. This is the piece that makes real-time and coordination workloads possible at the edge — and it has no clean AWS analog.

### AWS Mental Model

- There isn't a direct one. The closest construction is "**DynamoDB + a single-writer Lambda/actor with a distributed lock**," or a stateful WebSocket server you'd otherwise run on ECS/EC2 with a coordination layer (Redis). DOs collapse all of that into one primitive: a named singleton that processes its requests **single-threaded**, so you get serializability without external locks.

```js
// A per-room coordinator: counters, presence, WebSocket fan-out, rate limiters
export class Room {
  constructor(state, env) {
    this.state = state;                // durable storage + in-memory, single-threaded
  }
  async fetch(request) {
    let count = (await this.state.storage.get("count")) ?? 0;
    count++;
    await this.state.storage.put("count", count);   // strongly consistent
    return new Response(`count=${count}`);
  }
}

// Routing Worker: every request for "room:lobby" hits the SAME object instance globally
export default {
  async fetch(request, env) {
    const id = env.ROOMS.idFromName("room:lobby");
    return env.ROOMS.get(id).fetch(request);
  },
};
```

```toml
[[durable_objects.bindings]]
name = "ROOMS"
class_name = "Room"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["Room"]
```

### When to Reach for a Durable Object

- Real-time collaboration / chat / multiplayer (WebSocket hibernation keeps idle sockets cheap).
- Per-entity coordination: counters, locks, leaderboards, seat reservations, rate limiters that must be exact.
- Anything where KV's eventual consistency or D1's single-writer-per-DB isn't the right granularity.

### Key Differences from AWS

- A DO is a *globally unique addressable singleton* — `idFromName("x")` always routes to the one instance. There's no equivalent single primitive in AWS; you'd assemble it.
- Single-threaded execution gives you transactions-by-construction. Throughput per object is bounded — shard across many objects.

### Practice

- Build a global atomic counter and prove two concurrent clients never double-count.
- Implement a WebSocket chat room using a DO with hibernation.
- Sketch how you'd shard a rate limiter across DOs keyed by API client.

Docs: [Durable Objects](https://developers.cloudflare.com/durable-objects/).

---

## 11. Queues, Hyperdrive, Vectorize & Workers AI

The platform's "glue and intelligence" tier. Each maps cleanly to an AWS service but with the Workers-native, no-egress flavor.

### Queues (≈ Amazon SQS)

Producer/consumer messaging where the consumer is a Worker (push) — no polling loop to run.

```js
// Producer
await env.MY_QUEUE.send({ userId: 42, action: "welcome-email" });

// Consumer Worker (separate handler) — batches, acks, retries, DLQ
export default {
  async queue(batch, env) {
    for (const msg of batch.messages) {
      try { await process(msg.body); msg.ack(); }
      catch { msg.retry(); }          // dead-letters after max retries
    }
  },
};
```

Differences from SQS: consumer is invoked for you (no long-poll), no separate egress, batching/retry/DLQ built in. Use for decoupling, async work, and smoothing write spikes (e.g., buffer before D1).

### Hyperdrive (≈ RDS Proxy + global read cache)

Makes a Worker talk to your **existing** Postgres/MySQL (anywhere — RDS, Neon, on-prem) fast, by pooling connections and caching reads at the edge. Solves the "serverless + traditional DB = connection storm" problem that plagues Lambda + RDS.

```js
// Connect with a normal pg driver; Hyperdrive provides the pooled connection string
import { Client } from "pg";
const client = new Client({ connectionString: env.HYPERDRIVE.connectionString });
await client.connect();
const { rows } = await client.query("SELECT * FROM orders WHERE id = $1", [id]);
```

### Vectorize (≈ OpenSearch/Kendra vector search)

Edge-native vector database for RAG and semantic search. Store embeddings, query by nearest-neighbor, pair with Workers AI for the embedding model.

```js
const matches = await env.VECTORIZE.query(queryEmbedding, { topK: 5 });
```

### Workers AI (≈ Bedrock / SageMaker endpoints)

Serverless GPU inference in many PoPs, billed per "neuron." Run open models (LLMs, embeddings, image, speech) via a binding — no endpoint to provision.

```js
const out = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", {
  prompt: "Summarize: " + text,
});
```

### Practice

- Wire a Worker to enqueue an email job to Queues and a consumer Worker to process it with retry + DLQ.
- Put Hyperdrive in front of a Neon/RDS Postgres and compare cold query latency with and without it.
- Build a minimal RAG endpoint: Workers AI embeds the query → Vectorize finds top-K → Workers AI answers.

Docs: [Queues](https://developers.cloudflare.com/queues/), [Hyperdrive](https://developers.cloudflare.com/hyperdrive/), [Vectorize](https://developers.cloudflare.com/vectorize/), [Workers AI](https://developers.cloudflare.com/workers-ai/).

---

## 12. Zero Trust / Access

Cloudflare Zero Trust (Cloudflare One) replaces VPNs and the network perimeter with **identity-aware, context-based access controls**: verify every request regardless of network location.

### AWS Mental Model

- **AWS Verified Access** (identity-aware app access) + **AWS Client VPN** + **Cognito** as the IdP glue, plus a Secure Web Gateway you'd otherwise buy separately.
- Cloudflare bundles ZTNA, SWG, browser isolation, and DLP into one product delivered from the same edge as the CDN/WAF, with IdP integrations (Okta, Entra ID, Google) on top.

### Key Components

| Component | What it does | AWS-ish analog |
|-----------|--------------|----------------|
| **Access (ZTNA)** | Identity-verified access to internal apps; SSO/IdP integration | AWS Verified Access |
| **Gateway (SWG)** | Filters DNS/HTTP/network traffic; blocks malware/phishing | Network Firewall + Route 53 Resolver DNS Firewall |
| **WARP client** | Device agent routing traffic through Cloudflare | Client VPN agent |
| **Browser Isolation** | Runs browsing in the cloud, streams safe pixels | (no direct analog) |
| **DLP** | Inspect/control sensitive data in transit | Macie (different shape) |

### Key Concepts

- **"Never trust, always verify"** — identity + device posture + context on every request, not network trust.
- **Per-application access** replaces broad VPN reachability, shrinking blast radius.
- **Device posture checks** (OS version, disk encryption, security agent) combine with identity.
- Supports **clientless** (public hostname) and **WARP-client** (private network) access.
- Pairs with **Tunnels** (§13) so internal apps have no public IP.

### Pricing

| Plan | Price | Includes |
|------|-------|----------|
| Free | $0 | Up to 50 users; Access + Gateway |
| Pay-as-you-go | $7/user/month | Full feature set |
| Enterprise | Custom | SLAs, advanced features, support |

### Practice

- Put an internal app behind Access with Google SSO and a policy requiring a specific email domain.
- Add a device-posture requirement (disk encryption) to that policy.
- Configure Gateway to block a category (e.g., known malware) for WARP-enrolled devices.

Docs: [Cloudflare One / Zero Trust](https://developers.cloudflare.com/cloudflare-one/).

---

## 13. Cloudflare Tunnels

Cloudflare Tunnel creates **secure, outbound-only** connections from your infrastructure to Cloudflare. No public IPs, no open inbound ports, no firewall changes — the origin becomes unreachable except through Cloudflare.

### AWS Mental Model

- No clean analog. The intent overlaps **SSM Session Manager** (reach private instances without inbound ports) and "ALB/NLB + private origin," but Tunnels are simpler and broader: a daemon dials *out*, and Cloudflare publishes your service.

### How It Works

```bash
cloudflared tunnel login
cloudflared tunnel create my-app          # creates a tunnel + credentials
# config.yml maps public hostnames to local services:
cat config.yml
```

```yaml
tunnel: my-app
credentials-file: /root/.cloudflared/<id>.json
ingress:
  - hostname: app.example.com
    service: http://localhost:8080
  - hostname: ssh.example.com
    service: ssh://localhost:22
  - service: http_status:404      # catch-all (required last rule)
```

```bash
cloudflared tunnel run my-app             # establishes outbound connections
```

### Key Features

- **`cloudflared` daemon** — lightweight connector; maps local services or private IP ranges into the edge.
- **Outbound-only, 4 long-lived connections to 2 data centers** for redundancy; **Replicas** (multiple connectors) for HA.
- **Public hostname mapping** (`app.example.com → localhost:8080`) and **private network routing** (expose IP ranges to WARP users).
- **Quick Tunnels** — instant `trycloudflare.com` URL for dev (no account), the ngrok analog.
- **Remotely managed** via dashboard/API/Terraform; full CDN/WAF/DDoS/Access apply automatically.

### Key Differences from AWS

- Eliminates inbound attack surface entirely — no security groups, no public IP, no bastion.
- Combines with Access for authenticated internal apps; in AWS that's Verified Access + private networking assembled.

### Pricing

**Free** on all plans; you pay only for premium features applied to the traffic (WAF, Access, etc.).

### Practice

- Expose a local dev server to a real hostname with a named tunnel, then put Access in front of it.
- Add an SSH ingress rule and connect through the tunnel with no public SSH port open.
- Run two `cloudflared` replicas and kill one to observe failover.

Docs: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

---

## 14. Images & Stream (Media)

### Cloudflare Images (≈ S3 + Lambda/CloudFront image optimization)

Store, resize, and optimize images; transform via URL parameters; works on images stored in R2 or external URLs. Centralizes storage + variants + delivery instead of building your own pipeline (S3 + Lambda@Edge + Sharp).

- Free plan: 5,000 unique transformations/month. Variants are counted by parameter combination, so standardize width/quality presets.

**Pricing:** Storage $5 per 100K images stored; Delivery $1 per 100K delivered; Transformations $0.50 per 1,000 unique.

### Cloudflare Stream (≈ IVS + MediaConvert + MediaLive + CloudFront)

End-to-end on-demand and live video: storage, encoding, delivery, player, captions, thumbnails, analytics — with **ingest and encoding always free** and **no separate egress/bandwidth fees**. Supports RTMPS/SRT/WebRTC live and on-demand playback.

**Pricing:** Storage $5 per 1,000 minutes stored; Delivery $1 per 1,000 minutes delivered (delivered minutes ≈ watch time, which makes Stream easier to forecast than bandwidth+transcode billing).

### Key Differences from AWS

- One product replaces an assembled media stack; pricing is per stored/delivered minute or per-image, not per-GB-bandwidth + per-minute-transcode + per-request.

### Practice

- Upload an image and serve three responsive variants by URL params; count how many "unique transformations" that is.
- Upload a video to Stream and embed the built-in player; check the delivered-minutes metric after playback.

Docs: [Images](https://developers.cloudflare.com/images/), [Stream](https://developers.cloudflare.com/stream/).

---

## 15. Load Balancing

DNS- and proxy-layer load balancing across origin pools, with health checks and automatic failover.

### AWS Mental Model

- **Route 53 health checks + weighted/latency routing** for the DNS layer, plus **ELB/Global Accelerator** behavior at the proxy layer — combined into one product that steers across *your* origins anywhere (multi-cloud, on-prem), not just AWS targets.

### Key Features

- **Pools** — groups of origin endpoints (by region/priority/environment).
- **Monitors / health checks** — HTTP(S)/TCP/ICMP probes that proactively fail away from bad origins.
- **Fallback pool** — last-resort pool that always receives traffic.
- **Session affinity** — cookie-based stickiness for stateful/legacy apps.
- **Custom rules** — steer by hostname/geo/path/request attributes.

### Traffic Steering Policies

| Policy | Description |
|--------|-------------|
| Off (Failover) | Pool priority order |
| Random | Random across pools |
| Hash | Consistent hashing on request attributes |
| Geo | Route by user geography |
| Dynamic | Least connections / latency-based |
| Proximity | Nearest pool |
| Least Outstanding Requests | Least busy pool |

### Pricing

From **$5/month** base; add-ons for extra origins, faster health checks, geo-routing. Enterprise custom.

### Practice

- Create two pools in different regions with HTTP health checks and a fallback pool; kill one origin and watch failover.
- Configure geo-steering so EU users hit an EU pool, with proximity as the tiebreaker.

Docs: [Load Balancing](https://developers.cloudflare.com/load-balancing/).

---

## 16. Rate Limiting

Thresholds on incoming request rates with an action when exceeded — now part of the WAF as **Rate Limiting Rules**, sharing the Rules Language.

### AWS Mental Model

- **AWS WAF rate-based rules**. Cloudflare's version is more expressive: arbitrary **characteristics** (IP, header, cookie, API key, JA3/JA4), **counting expressions** (count only specific responses), and **complexity-based** limiting (Enterprise) for GraphQL/expensive endpoints.

```
# Rate Limiting Rule: 5 failed logins per IP per minute → block 10 min
When:  http.request.uri.path eq "/login" and http.request.method eq "POST"
Count by characteristic: ip.src
Counting expression: http.response.code in {401 403}
Threshold: 5 / 60s   →   Action: Block for 600s
```

### Key Features

- **Characteristics** — what the rate is tracked by (be deliberate: limiting by `ip.src` punishes shared NAT; limiting by API key is fairer).
- **Period** — 10s to 1 hour evaluation window.
- **Mitigation timeout** — how long the action persists after triggering.
- **Counting expressions** — count only specific requests/responses (e.g., only `429`/`401`).
- **Complexity-based** (Enterprise) — cost scores instead of raw counts.

### Availability by Plan

| Feature | Free | Pro | Business | Enterprise |
|---------|------|-----|----------|------------|
| Basic rate limiting | Yes | Yes | Yes | Yes |
| Number of rules | 1 | 2 | 5 | 100+ |
| Advanced criteria | No | No | Yes | Yes |
| Complexity-based | No | No | No | Yes |

### Practice

- Build the failed-login limiter above in Log mode, then promote to Block after reviewing analytics.
- Rate-limit an expensive `/search` endpoint by API-key header rather than IP, and explain why.

Docs: [Rate Limiting Rules](https://developers.cloudflare.com/waf/rate-limiting-rules/).

---

## 17. Argo Smart Routing

Argo finds the **fastest network paths** across Cloudflare's backbone to route edge↔origin traffic around public-internet congestion and packet loss.

### AWS Mental Model

- **AWS Global Accelerator** — both use a private backbone and anycast to improve path quality and reliability for traffic that can't be fully cached. Argo additionally feeds Tiered Cache topology decisions.

### Key Features

- **Real-time network intelligence** from routing tens of millions of requests/second.
- **~30% faster on average** for web assets (directional — depends on origin/user geography).
- **Automatic path selection**, **one-click enable**, works for **cached and dynamic** content; improves both latency and reliability.

### Key Differences from AWS

- Toggle vs. Global Accelerator's accelerator/listener/endpoint-group setup; usage-based add-on rather than a fixed hourly accelerator fee.

### Pricing

Paid add-on (usage-based). Most beneficial for users far from origin and for dynamic, non-cacheable content.

Docs: [Argo Smart Routing](https://developers.cloudflare.com/argo-smart-routing/).

---

## 18. Architecture Patterns

How the pieces compose into real systems.

### Pattern A: Full-stack app, entirely on Cloudflare

```
Users → CDN/WAF → Worker (API + SSR)
                    ├─ D1 (relational, per-tenant)
                    ├─ KV (config/flags/sessions cache)
                    ├─ R2 (uploads/media)
                    ├─ Durable Objects (real-time/coordination)
                    └─ Queues (async jobs) → consumer Worker
Static frontend → Pages / Workers Static Assets
```

No region selection, no VPC, no egress between these services. The AWS equivalent (CloudFront + Lambda + API GW + RDS + DynamoDB + S3 + SQS + ElastiCache) is more powerful at the high end but involves egress, cold starts, VPC plumbing, and per-service IAM.

### Pattern B: Cloudflare in front of existing infra

Keep your app on AWS/GCP/on-prem; put Cloudflare in front for CDN, WAF, DDoS, DNS, and Access. Use **Tunnels** so the origin has no public IP, or **Hyperdrive** so edge Workers can reach your existing Postgres without connection storms. This is the most common adoption path — additive, low-risk.

### Pattern C: Edge offload / strangler

Move specific concerns to the edge incrementally: auth and bot mitigation at the WAF, A/B and personalization in a Worker, static/media to R2+CDN, image optimization to Images — while the monolith stays put. Migrate more as confidence grows.

### Choosing storage (the decision every Cloudflare app makes)

| Need | Service |
|------|---------|
| Read-heavy config/flags/cached lookups | KV |
| Relational queries, per-tenant data | D1 |
| Large files/media/backups | R2 |
| Strong consistency / real-time coordination | Durable Objects |
| Reach an existing Postgres/MySQL fast | Hyperdrive |
| Vector/semantic search (RAG) | Vectorize |

---

## 19. Common Pitfalls & Gotchas

- **Gray-cloud surprise.** WAF/CDN/Workers routes only apply to **proxied (orange-cloud)** records. If a rule "isn't firing," check the DNS proxy status first.
- **Caching authenticated HTML.** "Cache Everything" without a cookie/auth condition can serve one user's page to another. Always scope HTML cache rules by auth state.
- **CPU time vs. wall time on Workers.** You can `await` slow origins (wall time), but **CPU time** is metered/capped (10 ms free, 30 s+ paid). Heavy in-CPU loops are the wrong fit — offload or use Containers.
- **KV is eventually consistent (~60s) and write-expensive.** Don't use it for counters, locks, or read-your-writes. That's Durable Objects.
- **D1's 10 GB cap and single writer.** It's a design constraint, not a bug — shard per tenant; for one big relational store use Hyperdrive + external Postgres.
- **Lambda→RDS connection storms.** If edge code hits a traditional DB directly, you'll exhaust connections. Use **Hyperdrive**.
- **Image "unique transformations" sprawl.** Every distinct width/quality/format combo is a billable variant. Standardize presets.
- **Bindings are environment-scoped.** A binding in `wrangler.toml` must exist in each environment (`[env.production]`); a missing prod binding is a classic deploy-time failure.
- **R2 zero-egress ≠ always cheaper.** Write-heavy/Class-A-op-heavy workloads can still cost; model ops, not just storage and egress.

---

## 20. Plan Comparison & Pricing

### Zone Plans (per domain)

| Plan | Price | Best for |
|------|-------|----------|
| **Free** | $0 | Personal sites, blogs, basic CDN + DDoS + SSL |
| **Pro** | $20/mo | Small/medium sites, managed WAF, image optimization |
| **Business** | $200/mo | E-commerce, SaaS, PCI, custom WAF, 100% uptime SLA |
| **Enterprise** | Custom | Large orgs, dedicated support, SLAs, advanced Zero Trust |

### Developer Platform (billed separately, generous free tiers)

The **Workers Paid plan ($5/mo)** unlocks higher limits across the developer products.

| Product | Free tier highlight | AWS analog |
|---------|---------------------|------------|
| Workers | 100K requests/day | Lambda / Lambda@Edge |
| Pages | Unlimited static bandwidth | Amplify / S3+CloudFront |
| R2 | 10 GB storage, free egress | S3 |
| D1 | 5M reads/day, 5 GB | Aurora Serverless |
| KV | 100K reads/day, 1 GB | DynamoDB + DAX |
| Durable Objects | included w/ Workers Paid | (assemble) |
| Queues | included w/ Workers Paid | SQS |
| Zero Trust | 50 users | Verified Access + Client VPN |
| Tunnels | Unlimited, free | (assemble) |

---

## 21. Decision Trees

### "Which compute?"

```
Static assets only?                         → Pages / Workers Static Assets
Request shaping, API glue, SSR, I/O-bound?  → Workers
Needs strong consistency / real-time state? → Durable Objects (front it with a Worker)
Heavy CPU / needs a container image?        → Workers Containers, or keep it on your origin behind a Tunnel
```

### "Which storage?"

```
Files/blobs/media?                          → R2
Relational, per-tenant, < 10 GB each?       → D1
Read-mostly config/flags/cache, eventual OK?→ KV
Need exact counters/locks/coordination?     → Durable Objects
Already have Postgres/MySQL?                → Hyperdrive in front of it
Embeddings / semantic search?               → Vectorize
```

### "Adopt Cloudflare how?"

```
Have existing app elsewhere?  → Pattern B: CDN/WAF/DNS/Access in front (+ Tunnel, + Hyperdrive)
Greenfield app?               → Pattern A: Workers + D1/KV/R2/DO/Queues end-to-end
Big monolith, want to chip?   → Pattern C: edge offload / strangler
```

---

## Quick Reference: When to Use What

| Need | Service | AWS analog |
|------|---------|-----------|
| Speed up site globally | CDN + Argo | CloudFront + Global Accelerator |
| Protect from attacks | DDoS + WAF | Shield + AWS WAF |
| Host static / JAMstack | Pages | Amplify / S3+CloudFront |
| Edge server logic | Workers | Lambda / Lambda@Edge |
| S3 alternative | R2 | S3 |
| SQL database | D1 | Aurora Serverless |
| Edge config/flags cache | KV | DynamoDB + DAX |
| Real-time coordination | Durable Objects | (assemble) |
| Async jobs | Queues | SQS |
| Reach existing Postgres | Hyperdrive | RDS Proxy |
| RAG / vector search | Vectorize | OpenSearch/Kendra |
| Serverless AI inference | Workers AI | Bedrock / SageMaker |
| Replace the VPN | Zero Trust + Access | Verified Access + Client VPN |
| Expose local/private services | Tunnels | (assemble) |
| Images / video | Images / Stream | S3+Lambda / IVS+MediaConvert |
| Distribute across origins | Load Balancing | Route 53 + ELB |
| Prevent API abuse | Rate Limiting | AWS WAF rate-based rules |

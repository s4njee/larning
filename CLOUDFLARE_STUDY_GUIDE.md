# Cloudflare Study Guide

A comprehensive guide to Cloudflare's most popular and useful services.

Pricing, plan limits, and product availability can change over time, so use the linked Cloudflare docs as the current source of truth when a number or feature matters operationally.

---

## Table of Contents

1. [CDN / Content Delivery Network](#1-cdn--content-delivery-network)
2. [DNS](#2-dns)
3. [DDoS Protection](#3-ddos-protection)
4. [WAF (Web Application Firewall)](#4-waf-web-application-firewall)
5. [Workers (Serverless Compute)](#5-workers-serverless-compute)
6. [Pages (Static Site Hosting)](#6-pages-static-site-hosting)
7. [R2 (Object Storage)](#7-r2-object-storage)
8. [D1 (Serverless Database)](#8-d1-serverless-database)
9. [KV (Key-Value Store)](#9-kv-key-value-store)
10. [Zero Trust / Access](#10-zero-trust--access)
11. [Cloudflare Tunnels](#11-cloudflare-tunnels)
12. [Images & Stream (Media)](#12-images--stream-media)
13. [Load Balancing](#13-load-balancing)
14. [Rate Limiting](#14-rate-limiting)
15. [Argo Smart Routing](#15-argo-smart-routing)
16. [Plan Comparison](#16-plan-comparison)

---

## 1. CDN / Content Delivery Network

Cloudflare's CDN caches content at **300+ data centers** worldwide, serving it from the location closest to the end user. Cloudflare acts as a **reverse proxy** -- when DNS is proxied through Cloudflare, traffic flows through their network before reaching the origin server.

### Key Features

- **Anycast IP Routing** -- all data centers share the same IP addresses; requests route to the nearest one automatically
  - Cloudflare advertises the same IP ranges from many edge locations, so normal internet routing sends users to a nearby POP without you managing region-specific endpoints; docs: [Cloudflare Cache](https://developers.cloudflare.com/cache/).
- **Tiered Cache** -- data centers organized into tiers (lower, regional, upper) so cache misses check other Cloudflare data centers before hitting origin. Included on all plans.
  - Tiered Cache reduces repeated origin fetches for long-tail assets because upper-tier nodes can satisfy misses for many lower-tier edges; docs: [Cloudflare Cache](https://developers.cloudflare.com/cache/).
- **Smart Tiered Cache Topology** -- uses Argo routing data to pick the best upper-tier data center
  - This makes the tiering strategy adaptive instead of static, which is especially useful when origin latency varies across regions; docs: [Argo Smart Routing](https://developers.cloudflare.com/argo-smart-routing/), [Cloudflare Cache](https://developers.cloudflare.com/cache/).
- **Cache Reserve** -- uses R2 persistent storage as an additional cache tier with longer retention
  - Cache Reserve is aimed at infrequently requested objects that are too valuable to keep missing at the origin just because they aged out of edge cache; docs: [Cloudflare Cache](https://developers.cloudflare.com/cache/), [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Cache Rules** -- control what gets cached, TTLs, and cache keys
  - Use Cache Rules to move beyond default file-extension caching and define explicit caching behavior for routes, headers, cookies, query strings, and custom cache keys; docs: [Cloudflare Cache](https://developers.cloudflare.com/cache/).
- **CNAME Flattening** -- allows CNAME at the zone apex
  - This solves the classic DNS restriction that prevents a bare domain like `example.com` from acting like a normal CNAME target; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).

### Common Use Cases

- Static asset delivery (JS, CSS, images)
  - These files benefit the most because they are highly cacheable and requested repeatedly by users across many regions.
- Reducing origin server load
  - Offloading repeat traffic to the edge lowers both compute pressure and outbound bandwidth usage on the origin.
- Improving global page load times
  - The biggest wins usually come from shorter round trips for cache hits and fewer expensive origin fetches for shared assets.
- Reducing bandwidth costs
  - This is especially noticeable on media-heavy sites where origin egress would otherwise scale linearly with traffic.

### Pricing

CDN is included on **all plans** (Free, Pro, Business, Enterprise). Bandwidth is **unlimited and unmetered** on all plans. Cache Reserve and Argo Smart Routing are paid add-ons.

---

## 2. DNS

Cloudflare DNS is a fast, resilient **authoritative DNS service**. When you onboard a domain, Cloudflare becomes the primary authoritative DNS provider. It is consistently one of the fastest DNS providers globally.

### Key Features

- **Authoritative DNS** -- available on all plans, free
  - Once your nameservers are delegated to Cloudflare, it becomes the source of truth answering DNS queries for the zone; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).
- **DNSSEC** -- adds cryptographic signatures to DNS records; supports multi-signer DNSSEC
  - DNSSEC protects resolvers from accepting forged answers by establishing a signed chain of trust from the parent zone to your records; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).
- **CNAME Flattening** -- returns A records for CNAME lookups at the zone apex, improving performance
  - It lets SaaS endpoints and load-balanced hostnames work cleanly at the root domain without violating DNS record rules; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).
- **Proxy Status** -- records can be "proxied" (orange cloud) routing traffic through CF, or "DNS only" (gray cloud)
  - Orange-cloud mode is what enables the CDN, WAF, and DDoS protections, while gray-cloud mode is just pure DNS resolution; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).
- **DNS Firewall** -- proxies queries to upstream nameservers, protecting from DDoS (Enterprise add-on)
  - This is targeted at organizations that want Cloudflare shielding and policy control for DNS traffic beyond public website records; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).
- **Foundation DNS** -- Enterprise offering with advanced nameservers and enhanced resiliency
  - It is meant for mission-critical domains that need deeper resiliency, routing control, and enterprise-grade DNS operations; docs: [Cloudflare DNS](https://developers.cloudflare.com/dns/).

### Key Concepts

- **Proxied records** return Cloudflare anycast IPs instead of origin IPs, enabling CDN/WAF/DDoS protection
  - This also hides the origin address from normal client lookups, which is a meaningful part of Cloudflare's protection model.
- **DNS-only records** expose the origin IP directly
  - Use this when a record should not pass through the proxy, such as many mail-related services or unsupported protocols.
- Cloudflare Registrar sells domains **at cost** (no markup)
  - Registrar is separate from authoritative DNS, but it is useful if you want domain registration and DNS operations under one vendor; docs: [Cloudflare Registrar](https://developers.cloudflare.com/registrar/).

### Pricing

Free on all plans. Foundation DNS is Enterprise-only.

---

## 3. DDoS Protection

Cloudflare automatically detects and mitigates DDoS attacks across **layers 3, 4, and 7** of the OSI model. Protection is unmetered, unlimited, and always-on.

### Key Features

- **Autonomous DDoS Protection Edge** -- detects and mitigates automatically without manual intervention
  - The value here is speed: mitigation starts at the edge before volumetric traffic can overwhelm your origin or network path; docs: [Cloudflare DDoS Protection](https://developers.cloudflare.com/ddos-protection/).
- **Managed Rulesets** -- pre-configured rules for HTTP DDoS and Network-layer DDoS
  - Managed protections give you a strong baseline without forcing you to hand-tune defenses before you are under attack; docs: [Cloudflare DDoS Protection](https://developers.cloudflare.com/ddos-protection/).
- **Adaptive DDoS Protection** -- learns your unique traffic patterns for sophisticated attack defense
  - This matters for high-traffic apps where “normal” request rates can look suspicious unless the system understands your baseline; docs: [Cloudflare DDoS Protection](https://developers.cloudflare.com/ddos-protection/).
- **Advanced DDoS Protection** -- stateful inspection and traffic profiling for TCP/DNS attacks (Enterprise)
  - Enterprise-grade protection adds more protocol-aware inspection for complex attack patterns that are harder to stop with static heuristics alone; docs: [Cloudflare DDoS Protection](https://developers.cloudflare.com/ddos-protection/).
- **No caps** -- no limits on attack size or duration
  - Operationally, this means you do not have to plan around “burst protection” tiers or surprise fees during an incident.

### Key Concepts

- **Layer 3/4** protection blocks network-level floods and amplification attacks at the edge
  - Think SYN floods, UDP amplification, and other bandwidth or connection-state exhaustion attacks before HTTP is even parsed.
- **Layer 7** protection handles application-layer attacks (HTTP floods)
  - These are closer to normal user traffic, so mitigation needs to distinguish abusive request behavior from legitimate browsing or API use.
- Enterprise customers can create **DDoS override rules** to customize mitigation behavior
  - Overrides are useful when a default mitigation is too strict or too loose for a known endpoint, customer segment, or traffic pattern.

### Pricing

Included **free and unlimited** on ALL plans. No surge pricing during attacks.

---

## 4. WAF (Web Application Firewall)

The Cloudflare WAF checks incoming web and API requests, filtering undesired traffic based on rulesets. It protects against **OWASP Top 10** vulnerabilities (XSS, SQLi, etc.).

### Key Features

- **Custom Rules** -- write rules using the Rules Language to block, challenge, or skip traffic based on IP, URL, headers, body content, etc.
  - Custom Rules are your precise control plane for traffic shaping, especially when you need logic that is specific to your app or abuse patterns; docs: [Cloudflare WAF](https://developers.cloudflare.com/waf/).
- **Managed Rules** -- pre-configured rulesets maintained by Cloudflare, regularly updated for zero-day vulnerabilities. Includes the Cloudflare Managed Ruleset and OWASP Core Rule Set.
  - Managed rules are the quickest way to cover common exploit classes without writing and maintaining your own signatures; docs: [Cloudflare WAF](https://developers.cloudflare.com/waf/).
- **Rate Limiting Rules** -- define rate limits within the WAF (see section 14)
  - This unifies abuse control with the rest of your request filtering so you can combine identity, path, headers, and rate behavior in one rules engine; docs: [Rate Limiting Rules](https://developers.cloudflare.com/waf/rate-limiting-rules/).
- **WAF Attack Score** -- ML-based scoring of requests for attack likelihood
  - A score-based model lets you challenge suspicious traffic without blocking everything that matches a coarse signature; docs: [Cloudflare WAF](https://developers.cloudflare.com/waf/).
- **Malicious Uploads Detection** -- scans file uploads
  - This is especially valuable for apps with user-generated content or admin uploads, where payload inspection matters beyond request metadata; docs: [Cloudflare WAF](https://developers.cloudflare.com/waf/).
- **Security Events / Security Analytics** -- dashboards for reviewing mitigated requests
  - These views are where you tune false positives, validate new rules, and understand what Cloudflare is actually stopping in production; docs: [Cloudflare WAF](https://developers.cloudflare.com/waf/).

### Key Concepts

- Rules are evaluated in order; **Block** actions stop further evaluation
  - Ordering matters because an early allow, skip, or block can completely change which later protections ever get a chance to run.
- The **Rules Language** uses expressions like `ip.src`, `http.request.uri.path`, `http.request.headers`
  - The language is expressive enough to model most request filtering use cases, so learning its fields pays off across several Cloudflare products.
- Actions include: Block, Managed Challenge, JS Challenge, Skip, Log
  - In practice, challenge and log actions are great for safely validating a new rule before turning it into a hard block.

### Common Use Cases

- Blocking malicious bots
  - A common approach is to challenge or rate-limit suspicious traffic first, then escalate to blocks once you are confident in the pattern.
- Preventing SQL injection and XSS
  - Managed rules do most of the heavy lifting here, while custom rules help you protect app-specific endpoints that need extra care.
- Geo-blocking
  - This is useful for compliance, fraud reduction, or reducing noise when you know traffic should only come from specific regions.
- IP allowlisting/blocklisting
  - Keep this narrow when possible, because IP-only controls are fast but usually much less expressive than layered identity and request logic.

### Pricing

| Feature | Free | Pro ($20/mo) | Business ($200/mo) | Enterprise |
|---------|------|--------------|---------------------|------------|
| Basic WAF | Yes | Yes | Yes | Yes |
| Managed Rules | No | Yes | Yes | Yes |
| Attack Score (ML) | No | No | Yes | Yes |
| Account-level Rulesets | No | No | No | Yes |

---

## 5. Workers (Serverless Compute)

Cloudflare Workers is a **serverless execution platform** that runs JavaScript/TypeScript/Wasm at the edge, in 300+ data centers worldwide. Code runs within milliseconds of users, with near-zero cold starts.

### Key Features

- **V8 Isolates** -- lightweight execution environment (not containers), near-instant startup
  - Isolates are why Workers can spin up quickly at the edge without the heavier lifecycle costs of a traditional container platform; docs: [Cloudflare Workers](https://developers.cloudflare.com/workers/).
- **Bindings** -- connect to KV, R2, D1, Durable Objects, Queues, and other Cloudflare services
  - Bindings let your code talk to platform services without manually wiring secrets, hostnames, or internal network calls; docs: [Cloudflare Workers](https://developers.cloudflare.com/workers/).
- **Cron Triggers** -- scheduled execution
  - This is the edge-native replacement for many background jobs, maintenance tasks, and periodic sync workflows; docs: [Cloudflare Workers](https://developers.cloudflare.com/workers/).
- **Durable Objects** -- strongly consistent, stateful serverless objects with co-located storage
  - Reach for Durable Objects when one logical entity needs ordered writes, coordination, or real-time shared state that KV cannot guarantee; docs: [Durable Objects](https://developers.cloudflare.com/durable-objects/).
- **Static Assets** -- serve static files directly from Workers
  - This makes it possible to ship one deployment unit that combines routing logic, API behavior, and asset delivery; docs: [Cloudflare Workers](https://developers.cloudflare.com/workers/).
- **Workflows** -- multi-step, durable execution
  - Workflows are designed for long-running, multi-stage processes where retries, checkpoints, and durable state matter more than single-request speed; docs: [Cloudflare Workflows](https://developers.cloudflare.com/workflows/).
- **Containers** -- run containers on Cloudflare (newer feature)
  - This extends the platform toward workloads that need a container abstraction, while Workers still remain the primary edge-native compute model; docs: [Cloudflare Workers](https://developers.cloudflare.com/workers/).

### Limits

| | Free | Paid ($5/mo) |
|---|---|---|
| Requests | 100,000/day | 10M included/mo, then $0.30/million |
| CPU time | 10 ms | 5 min |
| Memory | 128 MB | 128 MB |
| Worker size | 3 MB | 10 MB |
| Subrequests | 50/request | 10,000/request |

### Key Concepts

- Workers use **V8 isolates** (same engine as Chrome), not containers or VMs -- this enables near-zero cold starts
  - That architectural choice is what makes Workers feel closer to fast middleware than to a classic serverless function on a centralized host.
- **Durable Objects** provide strong consistency when KV's eventual consistency isn't enough
  - A good rule is to use them for coordination-heavy entities like rooms, carts, counters, locks, or live sessions.
- Workers can intercept and modify HTTP requests/responses (like middleware at the edge)
  - This makes them useful for auth, personalization, redirects, A/B tests, response shaping, and API gateways near the user.

### Pricing

$5/month subscription. 10M requests included, then $0.30/million. 30M CPU-ms included, then $0.02/million CPU-ms.

---

## 6. Pages (Static Site Hosting)

Cloudflare Pages deploys static sites and full-stack applications. It integrates with Git providers for automatic builds and deploys.

### Key Features

- **Git Integration** -- auto-deploys on push to GitHub/GitLab
  - Pages is strongest when your deployment workflow is Git-driven, because branches and commits become natural deployment units; docs: [Cloudflare Pages](https://developers.cloudflare.com/pages/).
- **Preview Deployments** -- unique URLs for every branch/commit (unlimited)
  - Preview URLs are great for QA, stakeholder review, and safe testing of infrastructure or content changes before they hit production; docs: [Cloudflare Pages](https://developers.cloudflare.com/pages/).
- **Pages Functions** -- server-side functions (powered by Workers) for dynamic functionality
  - This lets a Pages project move beyond pure static hosting and add API routes, auth hooks, or lightweight backend behavior without leaving Cloudflare; docs: [Cloudflare Pages](https://developers.cloudflare.com/pages/).
- **Unlimited Static Bandwidth** -- static asset requests are free and unlimited on all plans
  - This is one of the main reasons Pages is attractive for brochure sites, docs sites, and content-heavy frontends with global traffic.
- **Custom Domains** -- Free: 100, Pro: 250, Business: 500
  - The platform is built to make domain attachment routine, which matters for teams managing many environments, microsites, or customer-facing subprojects; docs: [Cloudflare Pages](https://developers.cloudflare.com/pages/).

### Limits

| | Free | Paid |
|---|---|---|
| Builds | 500/month | 5,000/month |
| Files | 20,000 | 100,000 |
| Max file size | 25 MiB | 25 MiB |
| Projects | ~100 per account | ~100 per account |

### Key Concepts

- Pages is ideal for **JAMstack** and static site generators (Next.js, Astro, Hugo, etc.)
  - The sweet spot is content or app shells that can be prebuilt, globally cached, and selectively enhanced with functions where needed.
- Functions requests count toward **Workers quotas**
  - In practice, that means Pages and Workers are tightly connected operationally even if they feel like different products in the dashboard.
- Competing with Vercel, Netlify, and GitHub Pages
  - The main differentiator is how closely Pages is integrated with the rest of Cloudflare's edge network, routing, and security stack.

### Pricing

Free tier is very generous -- unlimited static bandwidth, unlimited sites. Functions follow Workers pricing.

---

## 7. R2 (Object Storage)

S3-compatible object storage with **zero egress fees**. Designed for storing large amounts of unstructured data.

### Key Features

- **S3 API Compatible** -- works with existing S3 tools and SDKs
  - Compatibility lowers migration friction because existing backup, upload, and automation tooling can often keep working with minor endpoint changes; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Zero Egress Fees** -- no charges for data transfer out (the key differentiator vs AWS S3)
  - This is the feature people remember because it can change the cost model of read-heavy media, downloads, and analytics pipelines; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Workers API** -- native binding from Workers
  - Native bindings make R2 a natural storage layer for upload APIs, asset pipelines, and user-generated content on the same platform; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Public Buckets** -- serve files directly via custom domain
  - This is useful for static file delivery, asset hosting, and simple public download workflows without standing up a separate origin.
- **Storage Classes** -- Standard and Infrequent Access (30-day minimum duration)
  - Choose the class based on access pattern, because retrieval frequency and retention windows affect the real total cost; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **99.999999999% (11 nines) durability**
  - Durability speaks to how safely objects are stored over time, which is different from latency or availability during reads.
- **Super Slurper** -- free migration tool from S3/GCS
  - This is designed for bulk migration when you want Cloudflare to do the heavy lifting of pulling data into R2; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Sippy** -- incremental migration (serves from R2, backfills from source)
  - Sippy is more migration-friendly when you want cutover without a long freeze window or a full pre-copy before launch; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).
- **Object Lifecycles** -- automatic cleanup and storage class transitions
  - Lifecycle policies help control storage cost and retention hygiene as data ages out of its primary use case; docs: [Cloudflare R2](https://developers.cloudflare.com/r2/).

### Pricing

| | Free Tier | Standard | Infrequent Access |
|---|---|---|---|
| Storage | 10 GB/month | $0.015/GB-month | $0.01/GB-month |
| Class A Ops (writes) | 1M/month | $4.50/million | $9.00/million |
| Class B Ops (reads) | 10M/month | $0.36/million | $0.90/million |
| Egress | Free | **Free** | **Free** |
| Data Retrieval | N/A | None | $0.01/GB |

### Key Concepts

- R2's **zero egress** pricing makes it dramatically cheaper than S3 for read-heavy workloads
  - That does not mean every workload is automatically cheaper, but it often changes the economics of public delivery and cross-service access.
- Compatible with tools like `aws s3 cp`, `rclone`, Terraform, etc.
  - This matters operationally because it reduces retraining and lets you reuse familiar automation around buckets and objects.
- Can be used as a CDN origin or directly as a public file server
  - Which pattern you choose depends on whether you want pure object delivery or Cloudflare cache and security policies layered in front.

---

## 8. D1 (Serverless Database)

Cloudflare's managed serverless SQL database with **SQLite semantics**. Designed for horizontal scale-out across many smaller databases (per-user, per-tenant).

### Key Features

- **SQLite SQL Compatibility** -- familiar SQL syntax
  - D1 keeps the barrier to entry low because you can use standard relational patterns without learning a new query model; docs: [Cloudflare D1](https://developers.cloudflare.com/d1/).
- **Time Travel** -- point-in-time recovery to any minute within the last 30 days
  - This is a safety net for bad deploys, accidental writes, and debugging incidents where you need to inspect historical state; docs: [Cloudflare D1](https://developers.cloudflare.com/d1/).
- **Read Replication** -- automatic read replicas across 6 global regions at no extra cost
  - Replication improves read locality, which matters when your Workers execute far from the primary write location; docs: [Cloudflare D1](https://developers.cloudflare.com/d1/).
- **Scale to Zero** -- no charges when not running queries
  - That makes D1 attractive for smaller projects, internal tools, and bursty workloads that do not need always-on database capacity.
- **No Egress Charges** on data accessed from D1
  - This aligns well with the rest of the developer platform, where moving data between Cloudflare services is meant to stay operationally simple.

### Limits & Design

- **Max 10 GB per database** (hard limit)
  - This limit reinforces the intended architecture: shard by tenant, user, workload, or region rather than centralizing everything into one huge database.
- **Single-threaded per database** -- throughput depends on query duration
  - Slow or chatty queries hurt concurrency more here, so schema and query design have a very visible effect on app performance.
- Designed for **many small databases**, not one massive database
  - This matches edge-native multi-tenant designs much better than traditional “one giant primary” database thinking.
- Accessed via Workers binding or HTTP API
  - The binding path is usually the most ergonomic inside Cloudflare apps, while the HTTP API is helpful for external tooling and automation.

### Pricing

| | Free | Paid ($5/mo Workers plan) |
|---|---|---|
| Rows read | 5M/day | 25B/month, then $0.001/million |
| Rows written | 100K/day | 50M/month, then $1.00/million |
| Storage | 5 GB total | 5 GB included, then $0.75/GB-month |

---

## 9. KV (Key-Value Store)

A global, low-latency key-value data store optimized for **read-heavy workloads**. Data is eventually consistent and replicated across Cloudflare's network.

### Key Features

- **Global Distribution** -- data cached at edge locations for low-latency reads
  - KV is built to make reads fast almost everywhere, which is why it works well for config, flags, and cached lookup data; docs: [Cloudflare KV](https://developers.cloudflare.com/kv/).
- **Eventually Consistent** -- writes propagate globally within ~60 seconds
  - The tradeoff is straightforward: incredible read locality in exchange for delayed global visibility after writes; docs: [Cloudflare KV](https://developers.cloudflare.com/kv/).
- **Simple API** -- get, put, delete, list operations
  - This simplicity is a feature, because KV is meant for fast key-based access rather than relational queries or transactional workflows.
- **Metadata** -- attach JSON metadata to keys
  - Metadata is useful when you want lightweight attributes for filtering or cache control without storing a second object.
- **Expiration/TTL** -- automatic key expiration
  - TTLs are perfect for ephemeral cache entries, temporary tokens, and auto-cleaned feature state.
- **Bulk Operations** -- batch reads/writes via API
  - Bulk tooling matters when you need to warm caches, migrate namespaces, or manage large sets of keys programmatically.

### When to Use KV vs Other Storage

| Use Case | Best Choice |
|----------|-------------|
| Read-heavy, infrequently changing data | **KV** |
| Strong consistency needed | **Durable Objects** |
| SQL queries, relational data | **D1** |
| Large files, media, backups | **R2** |

### Pricing

| | Free | Paid |
|---|---|---|
| Reads | 100,000/day | 10M/month, then $0.50/million |
| Writes | 1,000/day | 1M/month, then $5.00/million |
| Deletes | 1,000/day | 1M/month, then $5.00/million |
| Storage | 1 GB | 1 GB, then $0.50/GB-month |

---

## 10. Zero Trust / Access

Cloudflare Zero Trust replaces traditional VPNs and network perimeters with **identity-aware, context-based access controls**. Verifies every request regardless of user location.

### Key Components

| Component | What It Does |
|-----------|--------------|
| **Access (ZTNA)** | Secures internal apps with identity verification. Supports SSO/IdP integration (Okta, Azure AD, Google). |
| **Gateway (SWG)** | Secure Web Gateway -- filters DNS, HTTP, and network traffic. Blocks malware and phishing. |
| **WARP Client** | Device agent that routes traffic through Cloudflare for Gateway filtering and private network access. |
| **Browser Isolation** | Runs web browsing in the cloud, sending only safe pixels to the user's device. |
| **DLP** | Data Loss Prevention -- inspect and control sensitive data in transit. |

Reference docs: [Cloudflare One / Zero Trust](https://developers.cloudflare.com/cloudflare-one/).

### Key Concepts

- **"Never trust, always verify"** -- every request is authenticated and authorized
  - Zero Trust treats identity, device state, and context as part of every access decision instead of assuming the network itself is trustworthy; docs: [Cloudflare One / Zero Trust](https://developers.cloudflare.com/cloudflare-one/).
- Replaces VPN with **per-application access controls**
  - This narrows blast radius because users get access only to the specific apps or routes they need, not broad network reachability.
- **Device posture checks** (OS version, disk encryption, security software)
  - Posture rules let you combine identity with endpoint health so a valid login alone is not enough for sensitive access.
- Supports both **public hostname access** (clientless) and **private network access** (WARP client)
  - That flexibility matters because browser-based SaaS access and internal RFC1918 network access usually have different rollout and UX requirements.

### Pricing

| Plan | Price | Includes |
|------|-------|----------|
| Free | $0 | Up to 50 users, Access + Gateway |
| Pay-as-you-go | $7/user/month | Full feature set |
| Enterprise | Custom | SLAs, advanced features, dedicated support |

---

## 11. Cloudflare Tunnels

Cloudflare Tunnel creates **secure, outbound-only connections** from your infrastructure to Cloudflare's network. No public IPs, no open inbound ports, no firewall changes needed.

### Key Features

- **`cloudflared` daemon** -- lightweight connector installed on your server
  - `cloudflared` is the agent that maintains the outbound tunnel and maps local services or private networks into Cloudflare's edge; docs: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).
- **Post-quantum encrypted** connections
  - Cloudflare emphasizes strong transport security here because tunnels often carry sensitive internal traffic over the public internet; docs: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).
- **4 long-lived connections** to 2 data centers for redundancy
  - Multiple persistent connections reduce the chance that one edge path or connector blip becomes a full outage.
- **Public Hostname Mapping** -- map `app.example.com` to `http://localhost:8080`
  - This is the most common setup for publishing an internal web app behind Cloudflare without exposing the origin directly.
- **Private Network Routing** -- expose entire IP ranges to WARP-connected users
  - Use this when you need access to internal services by IP or hostname across a private network, not just a single web app.
- **Remotely Managed** -- configuration via dashboard, API, or Terraform
  - Central management makes tunnels practical at scale, especially when you have many connectors, sites, or automation workflows.
- **Quick Tunnels** -- instant `trycloudflare.com` URL for dev (no account needed)
  - Quick Tunnels are great for demos and temporary local testing, but they are not the long-term production model.
- **Replicas** -- run multiple `cloudflared` instances for HA
  - Replica connectors are how you keep the tunnel path resilient when a single host or instance fails.

### Key Concepts

- Alternative to **ngrok** for exposing local services
  - The difference is that Cloudflare Tunnel fits directly into the larger Cloudflare access, routing, and security stack.
- **Eliminates attack surface** -- origin has no public IP
  - This is one of the strongest architectural wins because attackers cannot directly scan or connect to the service in the usual way.
- Works with **Access** for authenticated access to internal applications
  - Tunnel handles connectivity while Access adds the identity and policy layer on top of the published app.
- Outbound-only connections mean **no inbound firewall rules needed**
  - Many teams adopt Tunnel specifically to avoid opening ports or managing public listeners on private infrastructure.
- Full CDN, WAF, Bot Management, and DDoS protection applied automatically
  - Once traffic is fronted by Cloudflare, the same edge controls can be layered onto tunneled services just like public sites.

### Pricing

**Free** on all plans. You only pay for premium features applied to the traffic (WAF, Access, etc.).

---

## 12. Images & Stream (Media)

### Cloudflare Images

- Store, resize, and optimize images
  - Images is meant to centralize storage, variants, and delivery so you are not building your own image pipeline from scratch; docs: [Cloudflare Images](https://developers.cloudflare.com/images/).
- **Image Transformations** -- resize, crop, convert format via URL parameters
  - This makes responsive image delivery practical because variants can be generated or addressed without pre-rendering every size; docs: [Cloudflare Images](https://developers.cloudflare.com/images/).
- Works on images stored anywhere (R2, external URLs)
  - That flexibility is useful when you want optimization benefits without migrating every asset into one storage backend.
- Free plan: 5,000 unique transformations/month
  - Unique transformations are counted by variant combination, so careless parameter sprawl can affect cost more than raw request count.

**Pricing:**
- Storage: $5 per 100K images stored
  - Storage cost is based on how many source images you keep managed in the service, not how many variants you deliver.
- Delivery: $1 per 100K images delivered
  - Delivery pricing tracks served images, so high-traffic image libraries should model request volume separately from transformation volume.
- Transformations: $0.50 per 1,000 unique transformations
  - Unique transformation counts are driven by variant combinations, which is why standardizing your width/quality presets is important; docs: [Cloudflare Images](https://developers.cloudflare.com/images/).

### Cloudflare Stream

- Store, encode, and deliver on-demand and live video
  - Stream is positioned as an end-to-end video pipeline so you do not have to stitch storage, transcoding, playback, and delivery together manually; docs: [Cloudflare Stream](https://developers.cloudflare.com/stream/).
- Ingress and encoding are **always free**
  - Pricing is intentionally focused on stored and delivered minutes rather than charging separately for every upload or transcode step.
- No separate egress/bandwidth fees
  - Like R2, this simplifies planning because video delivery cost is not split across several network billing dimensions.
- Supports live streaming (RTMPS, SRT, WebRTC) and on-demand playback
  - That broad protocol support matters if you want one platform for both prerecorded media and real-time broadcast workflows.
- Built-in player, captions, thumbnails, analytics
  - These bundled features reduce the amount of extra media infrastructure you need before shipping a usable product.

**Pricing:**
- Storage: $5 per 1,000 minutes stored
  - Stored minutes reflect the size of your video library over time, so archival content has a direct ongoing cost.
- Delivery: $1 per 1,000 minutes delivered
  - Delivered minutes map closely to watch time, which makes Stream pricing easier to reason about than bandwidth-plus-transcode billing models; docs: [Cloudflare Stream](https://developers.cloudflare.com/stream/).

---

## 13. Load Balancing

DNS-based and HTTP-based load balancing across multiple origin servers, with health checking and automatic failover.

### Key Features

- **Pools** -- groups of origin servers (endpoints)
  - Pools are the primary abstraction for organizing origins by region, priority, or environment before any steering logic is applied; docs: [Cloudflare Load Balancing](https://developers.cloudflare.com/load-balancing/).
- **Monitors / Health Checks** -- periodically check endpoint health (HTTP, HTTPS, TCP, ICMP)
  - Health checks are what let the system fail away from bad origins proactively instead of waiting for user traffic to surface the issue.
- **Fallback Pool** -- last-resort pool that always receives traffic
  - A fallback pool keeps routing behavior predictable when all preferred pools or steering targets are unhealthy.
- **Session Affinity** -- sticky sessions via cookies
  - Sticky routing is helpful for legacy apps or stateful sessions that still assume repeat requests land on the same backend.
- **Custom Rules** -- route based on request attributes
  - Rules let you steer differently by hostname, geography, path, or other request traits instead of treating all traffic alike.

### Traffic Steering Policies

| Policy | Description |
|--------|-------------|
| Off (Failover) | Uses pool priority order |
| Random | Random distribution across pools |
| Hash | Consistent hashing on request attributes |
| Geo | Route by user geography |
| Dynamic | Least connections or latency-based |
| Proximity | Route to nearest pool |
| Least Outstanding Requests | Route to least busy pool |

### Pricing

Starts at **$5/month** base. Add-ons for additional origins, faster health checks, geo-routing. Enterprise pricing is custom.

---

## 14. Rate Limiting

Defines thresholds for incoming request rates and takes action when limits are exceeded. Now integrated into the WAF as **"Rate Limiting Rules."**

### Key Features

- **Characteristics** -- define how rates are tracked (by IP, headers, cookies, API key, etc.)
  - Choosing the right characteristic is crucial because it determines whether you are limiting users, devices, tokens, bots, or shared NAT addresses; docs: [Rate Limiting Rules](https://developers.cloudflare.com/waf/rate-limiting-rules/).
- **Configurable Period** -- time window for evaluation (10s to 1 hour)
  - Short windows react quickly to bursts, while longer windows are better for slower abuse patterns and fairness policies.
- **Mitigation Timeout** -- how long the action applies after triggering
  - Timeout tuning affects user experience a lot, because an overlong block can punish legitimate clients long after the burst ends.
- **Counting Expressions** -- optionally count only specific requests
  - This is powerful when you want to count only expensive requests, failed logins, or particular response codes rather than all traffic.
- **Complexity-based Rate Limiting** -- track cost scores instead of raw request counts (Enterprise Advanced)
  - Complexity scoring is especially useful for GraphQL or expensive endpoints where one request can cost much more than another.

### Availability by Plan

| Feature | Free | Pro | Business | Enterprise |
|---------|------|-----|----------|------------|
| Basic rate limiting | Yes | Yes | Yes | Yes |
| Number of rules | 1 | 2 | 5 | 100+ |
| Advanced criteria | No | No | Yes | Yes |
| Complexity-based | No | No | No | Yes |
| Throttle behavior | No | No | No | Yes |

### Key Concepts

- Rate limiting is now part of the **WAF**, not a separate product
  - That means it should be designed alongside your broader request filtering strategy, not as an isolated abuse control.
- Combine with **Custom Rules** for sophisticated bot protection
  - The strongest setups use identity, path, headers, and reputation signals together instead of relying on a single counter.
- Use **counting expressions** to only count specific response codes or paths
  - This helps you avoid penalizing harmless traffic when you really care about abusive outcomes like repeated `401`, `403`, or `429` patterns.

---

## 15. Argo Smart Routing

Finds the **fastest network paths** across Cloudflare's global network to route traffic between edge and origin, avoiding congestion and packet loss on the public internet.

### Key Features

- **Real-time Network Intelligence** -- analyzes data from routing ~50 million HTTP requests/second
  - Argo improves paths by learning from live traffic across Cloudflare's network instead of trusting the public internet's default route choice; docs: [Argo Smart Routing](https://developers.cloudflare.com/argo-smart-routing/).
- **~30% faster performance** on average for web assets
  - Treat the quoted improvement as directional rather than guaranteed, because the actual benefit depends heavily on origin location and user geography.
- **Automatic Path Selection** -- no manual configuration needed
  - The appeal is that you get path optimization without building or operating your own traffic-engineering layer.
- **Tiered Cache Integration** -- Argo data determines the best upper-tier data centers for caching
  - This is why Argo and advanced caching features often complement each other well rather than acting like separate optimizations.
- **One-click Enable** -- simple toggle in dashboard
  - Operational simplicity matters here because the product is meant to deliver network optimization without a big deployment project.

### Key Concepts

- Most beneficial for **users far from the origin server**
  - If the edge-to-origin leg is already short and stable, the performance gain will usually be smaller.
- Works with both **cached and dynamic** (non-cacheable) content
  - That makes it relevant even when your site cannot rely heavily on CDN caching for application responses.
- Improves both **latency and reliability** (routes around outages/congestion)
  - Better routing is not only about speed; it also helps smooth over packet loss and bad intermediate paths.
- Part of Cloudflare's **"Smart Shield"** origin server protection offering
  - In practice, Smart Shield is the grouping of features that reduce origin load and improve origin path efficiency, not just raw edge caching.

### Pricing

Paid add-on (usage-based). Enterprise customers can preview as a non-contract service.

---

## 16. Plan Comparison

### Overall Plans

| Plan | Price | Best For |
|------|-------|----------|
| **Free** | $0 | Personal sites, blogs, basic CDN + DDoS + SSL |
| **Pro** | $20/mo per domain | Small/medium sites, managed WAF rules, image optimization |
| **Business** | $200/mo per domain | E-commerce, SaaS, PCI compliance, custom WAF |
| **Enterprise** | Custom | Large orgs, dedicated support, SLAs, advanced Zero Trust |

### Developer Platform (Billed Separately)

All developer platform products have **generous free tiers**. The **Workers Paid plan ($5/mo)** unlocks higher limits across all developer products.

| Product | Free Tier Highlights |
|---------|---------------------|
| Workers | 100K requests/day |
| Pages | Unlimited static bandwidth |
| R2 | 10 GB storage, free egress |
| D1 | 5M reads/day, 5 GB storage |
| KV | 100K reads/day, 1 GB storage |
| Zero Trust | 50 users |
| Tunnels | Unlimited, free |

---

## Quick Reference: When to Use What

| Need | Service |
|------|---------|
| Speed up your website globally | CDN + Argo Smart Routing |
| Protect from attacks | DDoS Protection + WAF |
| Host a static site / JAMstack app | Pages |
| Run server-side logic at the edge | Workers |
| Store files (S3 alternative) | R2 |
| SQL database for your app | D1 |
| Cache config/feature flags at the edge | KV |
| Replace your VPN | Zero Trust + Access |
| Expose local services securely | Tunnels |
| Serve/optimize images | Images |
| Host video content | Stream |
| Distribute traffic across servers | Load Balancing |
| Prevent API abuse | Rate Limiting |

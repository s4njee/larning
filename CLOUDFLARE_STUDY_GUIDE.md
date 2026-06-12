# Cloudflare Study Guide

A practical, depth-first guide to Cloudflare for engineers and architects who already think in cloud primitives — especially **AWS** — and want to build strong Cloudflare instincts fast.

Cloudflare is best understood in two halves. The **network/security half** (CDN, DNS, TLS, DDoS, WAF, Zero Trust, Tunnels) is what you put *in front of* infrastructure you already run anywhere. The **developer platform half** (Workers, Pages, R2, D1, KV, Durable Objects, Queues, and friends) is a place to *run and store* the application itself, at the edge, with a different cost and consistency model than a regional cloud. This guide treats both, anchors each service to its AWS analog, explains the mechanism underneath each one — because the mechanisms, not the product names, are what let you predict behavior — and shows the actual code and config you write.

Primary references: the [Cloudflare developer docs](https://developers.cloudflare.com/) (per-product, current, and good — especially [Workers](https://developers.cloudflare.com/workers/), [R2](https://developers.cloudflare.com/r2/), and [Durable Objects](https://developers.cloudflare.com/durable-objects/)), [How Cloudflare works](https://developers.cloudflare.com/fundamentals/concepts/how-cloudflare-works/) (the network-half mental model), the [Cloudflare blog](https://blog.cloudflare.com/) (the engineering posts are primary sources for the mechanisms this guide describes), and the [workers.dev examples](https://developers.cloudflare.com/workers/examples/).

Pricing, plan limits, and product availability change over time. Treat every number here as directional and use the linked Cloudflare docs as the source of truth when a figure matters operationally.

---

## How to Use This Guide

- If Cloudflare is new to you, read in order: Part 1 builds the network mental model everything else assumes; the security services (2–7) and the developer platform (8–14) each build on it.
- In each section, anchor on the **AWS mental model** first, then learn the mechanism, then internalize the differences — that is where the real architecture decisions live. Treat the AWS mappings as *directional, not literal*: Cloudflare and AWS frequently solve the same problem with a different consistency model, billing dimension, or deployment unit, and the differences are the point.
- Run the **Practice** exercises. Cloudflare's free tiers are generous enough that almost everything here is free to do for real with a single `wrangler` install and one spare domain.

### The One Tool You Need: Wrangler

Almost everything on the developer platform is driven by **Wrangler**, Cloudflare's CLI (the rough analog of the `aws` CLI + SAM/CDK combined for the Workers world):

```bash
npm install -g wrangler        # or: npm create cloudflare@latest
wrangler login                 # OAuth into your account
wrangler whoami                # confirm account + zones
wrangler deploy                # deploy the current Worker globally, in seconds
wrangler dev                   # run a Worker locally on the real edge runtime (workerd)
wrangler tail                  # live-stream production logs (like `aws logs tail --follow`)
```

Configuration lives in `wrangler.toml` (or `wrangler.jsonc`) — the Workers equivalent of a SAM/CloudFormation template: it declares the Worker plus every **binding** (resource attachment) the code can use. Bindings are the platform's substitute for IAM-signed SDK calls, a difference §8 develops properly.

---

## Cloudflare ↔ AWS Translation Map

Internalize this table early. The rest of the guide elaborates each row.

| Cloudflare | Closest AWS | The difference that matters |
|---|---|---|
| CDN | CloudFront | Every PoP is a full PoP; unmetered egress; on by default once DNS is proxied |
| DNS | Route 53 | Authoritative DNS is free; fastest-globally; orange-cloud proxy toggle |
| DDoS Protection | AWS Shield Standard/Advanced | L3–L7, unmetered, no surge pricing, included free |
| WAF | AWS WAF | One expression language across products; ML attack score |
| Turnstile | (no real analog; reCAPTCHA competitor) | Invisible CAPTCHA replacement, free, no puzzle-solving |
| API Shield | API Gateway's validation + mTLS features | Schema validation + mTLS at the proxy, on existing APIs |
| Spectrum | NLB + Global Accelerator | Anycast proxy for arbitrary TCP/UDP, with DDoS protection |
| Workers | Lambda@Edge / CloudFront Functions / Lambda | V8 isolates, ~0 cold start, runs in every PoP, CPU-time billing |
| Pages | Amplify Hosting / S3+CloudFront | Git-driven, unlimited preview deploys, unlimited static bandwidth |
| R2 | S3 | **Zero egress fees**; S3-API compatible |
| D1 | Aurora Serverless v2 / RDS | SQLite per-database; designed for many small DBs, not one big one |
| KV | DynamoDB (global tables) / DAX | Eventually consistent (~60s), read-optimized, edge-cached |
| Durable Objects | (no direct analog) DynamoDB + single-writer actor | Strongly consistent, single-threaded, co-located compute+storage |
| Queues | SQS | Push to a Worker consumer; no separate egress |
| Hyperdrive | RDS Proxy + global cache | Pools + caches connections to *your existing* Postgres/MySQL |
| Vectorize | OpenSearch vector / Kendra | Edge-native vector index for RAG |
| Workers AI / AI Gateway | Bedrock / SageMaker + an LLM proxy | Serverless GPU inference per-neuron; gateway adds caching/limits/analytics |
| Zero Trust / Access | Verified Access + Client VPN + Cognito | Identity-aware app access replacing the VPN perimeter |
| Tunnels | (no direct analog) SSM + reverse proxy | Outbound-only connector; origin has no public IP or open ports |
| Stream / Images | IVS+MediaConvert / S3+Lambda image pipeline | End-to-end media, priced per minute/image, no egress line |
| Load Balancing | Route 53 health checks + ELB/Global Accelerator | DNS- and proxy-layer steering across origins anywhere |
| Argo Smart Routing | Global Accelerator | Congestion-aware path selection over Cloudflare's backbone |
| Logpush / Analytics Engine | Kinesis Firehose / CloudWatch | Push logs anywhere; write-time aggregated metrics from Workers |

---

## Table of Contents

1. [How Cloudflare's Network Actually Works](#1-how-cloudflares-network-actually-works)
2. [DNS](#2-dns)
3. [TLS and Certificates](#3-tls-and-certificates)
4. [CDN and Caching](#4-cdn-and-caching)
5. [DDoS Protection](#5-ddos-protection)
6. [WAF, Bot Management, Turnstile, and API Shield](#6-waf-bot-management-turnstile-and-api-shield)
7. [Rate Limiting](#7-rate-limiting)
8. [Workers (Serverless Compute)](#8-workers-serverless-compute)
9. [Pages and Static Assets](#9-pages-and-static-assets)
10. [R2 (Object Storage)](#10-r2-object-storage)
11. [D1 (Serverless SQL)](#11-d1-serverless-sql)
12. [KV (Key-Value Store)](#12-kv-key-value-store)
13. [Durable Objects (Stateful Coordination)](#13-durable-objects-stateful-coordination)
14. [Queues, Hyperdrive, Vectorize, Workers AI, and AI Gateway](#14-queues-hyperdrive-vectorize-workers-ai-and-ai-gateway)
15. [Zero Trust / Access](#15-zero-trust--access)
16. [Cloudflare Tunnels](#16-cloudflare-tunnels)
17. [Traffic Engineering: Load Balancing, Argo, and Spectrum](#17-traffic-engineering-load-balancing-argo-and-spectrum)
18. [Media: Images and Stream](#18-media-images-and-stream)
19. [Observability and Automation](#19-observability-and-automation)
20. [Architecture Patterns](#20-architecture-patterns)
21. [Common Pitfalls & Gotchas](#21-common-pitfalls--gotchas)
22. [Plan Comparison & Pricing](#22-plan-comparison--pricing)
23. [Decision Trees](#23-decision-trees)

---

## 1. How Cloudflare's Network Actually Works

Every Cloudflare behavior that surprises AWS-trained engineers — no regions, no distributions to deploy, DDoS absorption "for free," a single toggle that turns on a CDN — follows from two architectural decisions made early and never revisited. Understand them once and the rest of the guide is corollaries.

### Anycast: one IP, announced everywhere

AWS teaches you that an endpoint lives *somewhere*: a region, an AZ, a specific load balancer. Cloudflare's network inverts this. Every one of its 330+ data centers announces the **same IP prefixes** via BGP — so when a client resolves `yoursite.com` to a Cloudflare IP and connects, ordinary internet routing delivers the packet to whichever PoP is topologically nearest. There is no "us-east-1" because the address *is* the network; the routing system of the internet itself performs the load balancing.

Three consequences fall out immediately. First, **there is nothing to provision per location** — when Cloudflare adds a PoP, your site is served from it; when you change a rule, it propagates to all PoPs in seconds because rules are configuration, not deployed artifacts (contrast CloudFront's ~minutes distribution deploys). Second, **DDoS absorption is structural, not a product**: a botnet's traffic arrives spread across hundreds of PoPs near the bots, not concentrated on one victim datacenter — the attack is diluted by the same mechanism that serves your users, which is why §5's protection can be unmetered and free in a way Shield Advanced's economics can't match. Third, **every PoP is the full stack** — cache, WAF, Workers runtime, DNS, Zero Trust enforcement all run in every location, rather than CloudFront's model of thin edge caches in front of regional services. A request is fully processed at the first machine that receives it whenever possible.

### The reverse proxy: one hop, many products

The second decision: Cloudflare's products are not separate services you wire together — they are **stages in one proxy pipeline** that every request to a proxied hostname traverses, in a fixed order, inside a single PoP. A simplified but operationally accurate picture of the order of operations:

```
client TCP/TLS terminates at the PoP
  → DDoS mitigation (always-on, pre-everything)
  → IP Access / firewall basics
  → WAF: custom rules → rate limiting → managed rules
  → Zero Trust Access policy (if the hostname is protected)
  → Transform rules / redirects
  → Workers (your code, if a route matches)
  → Cache lookup (hit? serve; miss? continue)
  → Origin fetch (Argo path selection, Tunnel, or plain HTTPS)
```

This is why the platform feels coherent where AWS feels assembled: AWS WAF, CloudFront, Lambda@Edge, Shield, and Verified Access are five products with five consoles and five attachment models; on Cloudflare they are phases of one request lifecycle, sharing one expression language (§6) and one analytics view. When you debug Cloudflare, you are almost always asking *"which stage did this request reach, and what did that stage decide?"* — and the [Trace tool](https://developers.cloudflare.com/fundamentals/basic-tasks/trace-request/) plus the `cf-*` response headers answer exactly that question.

The pipeline only applies to traffic that flows through the proxy — which is a per-DNS-record choice, the **orange cloud** (§2). That toggle is the single most important switch in the platform: it decides whether a hostname gets the entire pipeline above or is just a name pointing at your server.

### What this buys and what it costs

The honest trade, stated once: you are placing a single vendor's network in the path of *all* your traffic. You gain a unified pipeline, a single point of policy, and economics no assembled stack matches (unmetered bandwidth and DDoS because the marginal cost of serving you from an anycast network they run anyway is low). You accept that Cloudflare terminates your TLS (§3 covers what that means and how to secure the second hop), that a Cloudflare outage is your outage (rare, loud, and shared with half the internet — which is itself a kind of SLA), and that some protocols and architectures don't fit the proxy model and must stay gray-cloud or move to Spectrum (§17). Most organizations take this trade for the front door while keeping the origin portable; §20's Pattern B is that posture, formalized.

Docs: [How Cloudflare works](https://developers.cloudflare.com/fundamentals/concepts/how-cloudflare-works/), [Anycast](https://www.cloudflare.com/learning/cdn/glossary/anycast-network/).

---

## 2. DNS

Cloudflare began life as authoritative DNS plus a proxy, and DNS remains the control plane for everything: which traffic enters the §1 pipeline is decided record by record, here.

### AWS mental model

**Route 53** hosted zones, records, alias records, health checks. The structural differences: Cloudflare authoritative DNS is **free and unmetered** (Route 53 bills per zone and per million queries), it is consistently among the [fastest authoritative providers measured globally](https://www.dnsperf.com/), and — the part with no Route 53 equivalent at all — every record carries the **proxy toggle** that fuses DNS with the entire security/CDN stack.

### The orange cloud is the whole game

A **proxied (orange-cloud)** record answers queries with *Cloudflare's* anycast IPs: clients connect to the PoP, the §1 pipeline runs, and your origin's real address never appears in public DNS. A **DNS-only (gray-cloud)** record answers with your origin's actual IP: pure name resolution, no pipeline, no protection, origin exposed. Everything interesting about a zone reduces to which records are orange.

Three operational corollaries. First, the diagnosis habit: when "my WAF rule isn't firing" or "caching isn't working," check the proxy status *before anything else* — a gray cloud bypasses every product in this guide. Second, **origin IP hygiene**: proxying hides your origin only if the IP isn't discoverable elsewhere — historical DNS data, certificate-transparency logs naming the origin host, verbose error pages, and SPF records all leak it, and an attacker who finds the IP can walk straight past the WAF. The robust answer is to firewall the origin to [Cloudflare's published IP ranges](https://www.cloudflare.com/ips/) (or better, eliminate inbound entirely with a Tunnel, §16) so the proxy is the only possible path. Third, some traffic *must* stay gray: protocols the HTTP proxy doesn't front — most notably **mail** (MX targets and the SMTP host they point to) — break if proxied; this is the classic first-week mistake, and the dashboard now warns about it.

### Mechanics worth knowing

**CNAME flattening** answers the apex-domain problem (`example.com` itself can't be a CNAME per the DNS specs, yet SaaS and load balancers hand you hostnames): Cloudflare resolves the CNAME chain server-side and synthesizes A/AAAA answers at the apex — the same trick as Route 53 alias records, applied automatically. **DNSSEC** is one toggle plus a DS record at your registrar (multi-signer is supported for the migration-between-providers case). **Wildcards are proxyable**, including on free plans. For Enterprise, **Foundation DNS** adds independent nameserver infrastructure for resilience, and **DNS Firewall** fronts *your own* authoritative servers with Cloudflare's cache and DDoS absorption — DNS-as-a-shield rather than DNS-as-a-host.

Two adjacent products live here. **Cloudflare Registrar** sells/renews domains at wholesale registry cost with no markup — there is no reason to renew elsewhere for supported TLDs. **Email Routing** (free) forwards mail for your domain to existing inboxes and can deliver inbound mail *to a Worker* — which turns "parse incoming email and act on it" from an SES+Lambda+S3 assembly into a single handler, one of the platform's quietly excellent compositions.

### Practice

- Move a domain's nameservers to Cloudflare, enable DNSSEC, verify the DS record, and `dig +trace` the chain.
- Confirm with `dig` that a proxied record returns Cloudflare IPs and a gray one returns your origin; then check certificate-transparency logs (crt.sh) for hostnames that leak your origin.
- Firewall your origin to Cloudflare's IP ranges and verify direct-to-IP requests fail.
- Identify which records in a real zone must remain gray-cloud, and why.

Docs: [DNS](https://developers.cloudflare.com/dns/), [Registrar](https://developers.cloudflare.com/registrar/), [Email Routing](https://developers.cloudflare.com/email-routing/).

---

## 3. TLS and Certificates

The proxy architecture means TLS has **two hops** — client→Cloudflare and Cloudflare→origin — and they are configured separately. Misunderstanding this is the source of both the platform's most common outage (redirect loops) and its most quietly dangerous misconfiguration (plaintext second hops that *look* encrypted to users). AWS has no equivalent section because CloudFront forces you to think about origin protocol policy explicitly; Cloudflare's friendlier defaults make it possible *not* to think, which is exactly why you must.

### Edge certificates: the easy half

Client→Cloudflare TLS is nearly zero-work: every zone gets a free **Universal SSL** certificate (covering the apex and one wildcard level), issued and renewed automatically. Paid options exist for clean-cert requirements (Advanced Certificate Manager for custom SANs, dedicated certs, or bring-your-own). Modern niceties — TLS 1.3, automatic HTTP→HTTPS, HSTS — are toggles. The only real decisions: minimum TLS version (1.2 unless you have a compliance reason for higher), and whether to enable HSTS *after* you're certain all subdomains serve HTTPS (HSTS misapplied is self-inflicted unreachability with a max-age timer).

### Encryption modes: the half that bites

The **SSL/TLS mode** governs the *second* hop, Cloudflare→origin, and its levels are a ladder of honesty:

- **Off / Flexible** — Flexible serves HTTPS to the *user* while connecting to your origin over **plain HTTP**. It exists so sites with no origin certificate could get a padlock in 2014; today it is a trap with two teeth. The security tooth: traffic crosses the internet unencrypted on the second hop while users see a padlock. The operational tooth: the infamous **redirect loop** — your origin, seeing HTTP, redirects to HTTPS; Cloudflare fetches that over HTTP again; loop. Whole pages of community forums are this one misconfiguration.
- **Full** — HTTPS to origin, but *any* certificate accepted, including expired and self-signed. Encrypted, not authenticated: an on-path attacker who can intercept the second hop can present any cert. Acceptable as a waypoint, not a destination.
- **Full (strict)** — HTTPS with a **valid, trusted certificate**, which is the only mode that means what users think the padlock means. Cloudflare removes the classic excuse by issuing free **Origin CA certificates** — 15-year certs trusted *by Cloudflare's proxy* (not by browsers — they're for the second hop only), installable on your origin in minutes.

The rule is one sentence: **set Full (strict) with an Origin CA cert on day one, and treat anything less as an incident waiting to be misunderstood.**

### Authenticating the client of your origin

Full (strict) authenticates the origin *to Cloudflare*; the reverse question — "is this request to my origin actually from Cloudflare?" — is answered by **Authenticated Origin Pulls** (the proxy presents a client certificate your origin verifies; mTLS on the second hop), which combined with the §2 IP allowlist or a Tunnel closes the walk-around-the-WAF hole completely. For *end-user* client certificates — IoT fleets, B2B API callers — **mTLS at the edge** (part of API Shield, §6) lets Cloudflare verify client certs and pass identity to your code, the analog of API Gateway's mutual TLS but applicable in front of any origin.

### Practice

- Set Flexible mode on a test zone with an HTTPS-redirecting origin and watch the redirect loop happen; fix it by moving to Full (strict) with an Origin CA certificate.
- Enable Authenticated Origin Pulls and verify with origin logs that direct requests lacking the client cert are rejected.
- Inspect your certificate chain with `openssl s_client` against the edge, then against the origin — explain every certificate you see.

Docs: [SSL/TLS](https://developers.cloudflare.com/ssl/), [Origin CA](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/), [Authenticated Origin Pulls](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/).

---

## 4. CDN and Caching

With §1's architecture in place, the CDN needs only one new idea: the **cache decision** — given a request, may the PoP serve a stored copy, and under what key? Everything else (the 330+ locations, the on-by-default behavior, the unmetered bandwidth) you already understand.

### AWS mental model

**CloudFront** with origins, behaviors, and cache policies. The contrasts: no distribution object (caching is on the moment a record is proxied; changes propagate in seconds, not the ~15-minute CloudFront deploy), no per-region egress pricing (the line item that dominates CloudFront bills does not exist on any Cloudflare plan), and purges are free and near-instant (CloudFront meters invalidations past an allotment).

### How the cache decides

A PoP receiving a request computes a **cache key** (by default: scheme + host + path + query string) and answers from cache only if both the key matches *and* the stored response is still fresh. The decision chain for whether and how long to store:

1. **Eligibility**: by default, Cloudflare caches responses whose *file extension* is on the [static list](https://developers.cloudflare.com/cache/concepts/default-cache-behavior/) (images, JS, CSS, fonts…). **HTML is not cached by default** — the proxy assumes it's dynamic, reported as `cf-cache-status: DYNAMIC`. This single default explains the majority of "Cloudflare isn't caching my site" confusion: it is caching your assets and deliberately not your pages, until you say otherwise.
2. **TTL**: the origin's `Cache-Control`/`Expires` govern edge freshness — unless a **Cache Rule** overrides them. Cache Rules (the successor to Page Rules, which are deprecated and should not be used for new work) are written in the same Rules Language as the WAF, and can set eligibility ("Cache Everything" for HTML), edge and browser TTLs, and **custom cache keys** — the genuinely sharp tool: keying on a header or cookie partitions the cache (e.g., key by `Accept-Language` for localized pages), while *removing* query params from the key collapses marketing-tag permutations (`?utm_*`) into one stored object.
3. **Verdict reporting**: every response carries `cf-cache-status` — `HIT`, `MISS`, `EXPIRED`, `REVALIDATED`, `DYNAMIC` (not eligible), `BYPASS` (eligible but told not to) — your primary debugging signal, the analog of `X-Cache` from CloudFront but more articulate about *why*.

```
Client → nearest PoP → cache HIT? serve
                     → MISS → upper-tier PoP (Tiered Cache) → MISS → origin
                       → store per Cache-Control / Cache Rules → serve
```

**Tiered Cache** (free, enable it) organizes PoPs into a hierarchy so a miss at the edge checks a regional upper tier before bothering your origin — collapsing thousands of PoPs' worth of long-tail misses into a few origin fetches. **Cache Reserve** (paid) extends the hierarchy with an R2-backed persistent layer for valuable-but-infrequent objects, trading R2 storage pennies for origin offload on the long tail.

### The cardinal caching sin

"Cache Everything" applied to HTML without an authentication condition will, eventually, serve one user's logged-in page to another user — the classic cache-poisoning-by-configuration incident, and it is *always* a Cache Rule that ignored cookies. The correct shape: cache HTML **only** for anonymous traffic (bypass when the session cookie is present), or better, leave personalized HTML uncached and move personalization to a Worker reading cached fragments. Any rule that says "Cache Everything" should make you ask "what about Set-Cookie and sessions?" reflexively.

### Practice

- `curl -sI` an asset twice; read `cf-cache-status` flip from `MISS` to `HIT`; then request your homepage and explain the `DYNAMIC`.
- Write the safe HTML rule: cache for 5 minutes only when the session cookie is absent; verify both paths with curl.
- Enable Tiered Cache, then measure origin request counts before/after on a long-tail asset set.
- Collapse `utm_*` parameters out of the cache key and prove two tagged URLs hit one cached object.

Docs: [Cache](https://developers.cloudflare.com/cache/), [Cache Rules](https://developers.cloudflare.com/cache/how-to/cache-rules/), [Tiered Cache](https://developers.cloudflare.com/cache/how-to/tiered-cache/).

---

## 5. DDoS Protection

§1 explained why DDoS protection is architecturally cheap for an anycast network: attack traffic distributes itself across hundreds of PoPs, each of which drops it locally. This section is about what the mitigation actually does, because "automatic and unmetered" doesn't mean unconfigurable.

### AWS mental model

**Shield Standard** (free, automatic L3/4) + **Shield Advanced** (~$3,000/month + commitments, for L7, cost protection, and the response team). Cloudflare's structural answer: because absorbed traffic doesn't transit metered egress, there is no attack-driven bill to insure against — so the "cost protection" product category simply doesn't exist, and Shield-Advanced-grade L3–L7 mitigation is included on every plan, attack size unlimited.

### How mitigation works

Detection and mitigation run **in every PoP, ahead of everything else** in the §1 pipeline. At L3/4, always-on systems fingerprint floods (SYN floods, amplification reflections, protocol anomalies) and drop them at the edge of the network — much of it in hardware/XDP before a connection ever exists. At L7, the **HTTP DDoS managed ruleset** watches request-rate dynamics per zone and deploys mitigations when traffic deviates from your baseline — which is where **Adaptive Protection** matters: it learns your normal (rates, geographies, user agents) so a legitimate traffic spike (launch day, newsletter send) is distinguishable from a flood by *shape*, not just volume.

Your control surface is **override rules**: per-expression sensitivity and action adjustments in the same Rules Language as everything else. The two standard moves are raising sensitivity/severity for cheap-to-abuse endpoints (`/login`, search, anything that hits the database) and lowering it (or setting Log) for endpoints that legitimately burst (webhook receivers, health checks from your own fleet). During an active incident, the **Security Events** view shows which rules are firing on what traffic; "Under Attack Mode" remains the blunt emergency lever (interstitial JS challenge for all visitors) when you need breathing room.

One scoping note: everything above protects *proxied HTTP*. Non-HTTP services need **Spectrum** (§17) for the same anycast absorption at the TCP/UDP layer, and network-infrastructure-scale protection (your own IP prefixes, BGP-advertised through Cloudflare) is **Magic Transit** — the Enterprise product that extends the same model to entire networks, mentioned here so you know the ladder exists.

### Practice

- Open Security → Events, filter to DDoS mitigations, and identify what fired in the last 30 days (most zones have *something*).
- Write an override raising sensitivity on `/login` while excluding your monitoring system's health checks by ASN or header.
- Tabletop the launch-day scenario: what distinguishes your spike from an attack, and which Adaptive Protection signals would you check?

Docs: [DDoS Protection](https://developers.cloudflare.com/ddos-protection/), [Managed rulesets and overrides](https://developers.cloudflare.com/ddos-protection/managed-rulesets/).

---

## 6. WAF, Bot Management, Turnstile, and API Shield

The application-security tier, unified by one fact that makes Cloudflare's version qualitatively easier to operate than AWS WAF's: **everything is expressed in one language, evaluated in one pipeline, tuned in one analytics view**.

### The Rules Language: learn once, use everywhere

A boolean expression language over request fields — the same syntax in WAF custom rules, rate limiting, cache rules, transform rules, redirect rules, and DDoS overrides. Where AWS WAF nests JSON statements, here you write what you mean:

```
# Block API traffic from outside the US that lacks a valid API key header
(http.request.uri.path matches "^/api/" and ip.geoip.country ne "US"
  and not http.request.headers["x-api-key"][0] matches "^sk_live_")

# Managed-Challenge logins with high bot likelihood
(http.request.uri.path eq "/login" and cf.bot_management.score lt 30)

# Skip remaining WAF rules for the office
(ip.src in {203.0.113.10 203.0.113.11})
```

The fields worth memorizing: `ip.src`, `ip.geoip.country`, `ip.src.asnum`, `http.request.uri.path`, `http.request.method`, `http.host`, `http.request.headers[...]`, `http.cookie`, and the two ML scores — `cf.waf.score` (attack likelihood) and `cf.bot_management.score` (1 = certainly a bot, 99 = certainly human). Actions: **Block**, **Managed Challenge**, **JS Challenge**, **Skip** (exempt from later rules — the allowlist mechanism), **Log** (count without acting — where every new rule should start). Rules evaluate in order within a phase; phases run in §1's pipeline order (custom rules → rate limiting → managed rules), which matters: a Skip in custom rules can exempt traffic from managed rules behind it.

### The WAF's three layers

**Managed Rules** — the Cloudflare Managed Ruleset (signatures and heuristics for the OWASP-Top-10 categories plus zero-day virtual patches, updated by Cloudflare faster than you'd patch — the Log4j rules shipped within hours) and a separately-toggleable OWASP Core Rule Set (anomaly-scoring, paranoia-level model; noisier, tune before enforcing). **Attack Score** (Business+) — an ML model scoring every request's attack likelihood independent of signatures, which is what catches the obfuscated variant a regex misses; use it as a *condition* (`cf.waf.score lt 20 → Block`, `20–50 → Managed Challenge`) rather than a verdict. **Custom rules** — your precise policy, in the language above.

The operational discipline that separates teams who love their WAF from teams drowning in false positives is the same on any platform, but Cloudflare's tooling makes it explicit: **deploy in Log, read Security Analytics for a few days, then promote Log → Managed Challenge → Block** as confidence grows. Managed Challenge deserves a sentence: it's not a CAPTCHA but a decision engine — invisible proof-of-work and behavioral signals for most visitors, escalating to interaction only when unsure — so challenging ambiguous traffic costs legitimate users almost nothing, which changes the false-positive calculus that makes people afraid of blocking.

### Bot Management and Turnstile

The bot problem has two faces. For traffic *arriving at your site*, **Bot Fight Mode** (free; blunt — challenges everything bot-scored, breaks legitimate API clients, enable with care) and **Bot Management** (Enterprise; the per-request `cf.bot_management.score` plus verified-bot detection, JA3/JA4 TLS fingerprints, and detection of headless browsers) let you write graduated policy — allow verified search crawlers, challenge gray-zone scrapers, block credential stuffers — rather than a binary wall.

For *interactive endpoints* (signup, login, checkout), **[Turnstile](https://developers.cloudflare.com/turnstile/)** is the reCAPTCHA replacement: a free, embeddable widget that runs the same invisible-challenge machinery and returns a token your backend verifies server-side (`siteverify` call — do not skip the server-side check; the token, not the widget, is the security boundary). No image puzzles, no Google data-sharing, works without a Cloudflare-proxied site. For new builds there is little reason to choose anything else, and the integration with the WAF (challenge pages use the same engine) means consistent treatment across your stack.

### API Shield

APIs invert WAF assumptions: there's no browser to challenge, "bot" is the *intended* client, and the threats are schema abuse, credential stuffing, BOLA-style enumeration, and shadow endpoints. **API Shield** (Enterprise, with pieces available lower) addresses the API-specific surface: **Schema Validation** (upload your OpenAPI spec; requests that don't conform — wrong types, unexpected fields, undocumented endpoints — are blocked at the edge, the positive-security model that signature WAFs can't express), **mTLS client certificates** (§3) for machine callers, **API Discovery** (learns your actual endpoint inventory from traffic — the shadow-API detector), and volumetric-abuse detection per endpoint. For the AWS-minded: this is API Gateway's request validation plus mTLS, applied at the proxy in front of *any* origin, plus discovery features Gateway lacks.

### Practice

- Write the login rule (`bot score < 30 → Managed Challenge`) in Log mode; read Security Analytics for two days; promote it and measure challenge solve rates.
- Geo-restrict `/admin` to two countries with a Skip rule for the office ASN; verify rule order matters by reordering and re-testing.
- Add Turnstile to a real form, verify the token server-side, and confirm a request replaying an old token fails.
- Export an OpenAPI spec from your framework and walk through what Schema Validation would block today (even without Enterprise, the exercise finds undocumented endpoints).

Docs: [WAF](https://developers.cloudflare.com/waf/), [Rules language](https://developers.cloudflare.com/ruleset-engine/rules-language/), [Bots](https://developers.cloudflare.com/bots/), [Turnstile](https://developers.cloudflare.com/turnstile/), [API Shield](https://developers.cloudflare.com/api-shield/).

---

## 7. Rate Limiting

Rate limiting lives inside the WAF (same Rules Language, its own phase) but earns its own section because the design decisions are different in kind: a WAF rule asks *what is this request?*; a rate rule asks *how many, counted how, per what?* — and each of those three choices changes who you punish.

### AWS mental model

**AWS WAF rate-based rules**, but more expressive on every axis: arbitrary counting **characteristics** (not just IP), **counting expressions** decoupled from the matching expression (count only some outcomes), and per-rule mitigation timeouts.

### The three design decisions

```
# 5 failed logins per IP per minute → block that IP for 10 minutes
Match:     http.request.uri.path eq "/login" and http.request.method eq "POST"
Count by:  ip.src
Count if:  http.response.code in {401 403}     ← counting expression: failures only
Threshold: 5 per 60s  →  Action: Block, 600s
```

**Characteristic** — what the counter is keyed by. `ip.src` is the default and the trap: corporate NATs and CGNAT put thousands of legitimate users behind one IP, so IP-keyed limits on consumer products punish the innocent; keying by API key, session cookie, or JA4 fingerprint is fairer whenever the request carries an identity. **Counting expression** — counting *failures* (401/403 responses) instead of attempts turns a brute-force limiter that annoys fat-fingered users into one that only fires on actual attack patterns; counting only expensive responses protects capacity rather than counting cheap cache hits. **Threshold and timeout** — set from measured p99 client behavior (Security Analytics shows you actual per-characteristic rates), not intuition; and remember the mitigation outlives the burst by the timeout you choose.

Enterprise adds **complexity-based limiting** (budget per client on a *cost* you assign per request — the answer for GraphQL, where one request can be a thousand-row join) and leaky-bucket-style throttling rather than block-after-threshold. And the same principle from §6 applies: ship every limiter in Log first; the analytics will tell you which legitimate client you were about to break — there is always one.

### Practice

- Build the failed-login limiter above in Log mode; find the legitimate client that would have tripped it (a password manager retrying, a mobile app's token refresh loop) before enforcing.
- Re-key a per-IP API limit by `x-api-key` header and write down what happens to (a) the NAT'd office and (b) an attacker rotating IPs — the two cases that justify the change.

Docs: [Rate limiting rules](https://developers.cloudflare.com/waf/rate-limiting-rules/).

---

## 8. Workers (Serverless Compute)

Workers is the half of Cloudflare that is genuinely a different *computer*, not a different vendor — and the differences from Lambda are not pricing details but a distinct execution model with its own physics. Get the isolate model right and every limit, every price, and every "when should I use this" follows.

### The isolate model, versus Lambda's

**Lambda** isolates customers with micro-VMs (Firecracker): each concurrent execution is a VM with your runtime loaded into it, started on demand — hence cold starts (hundreds of ms), per-instance memory sizing, GB-second billing, and regional deployment (the VM fleet lives somewhere). **Workers** isolates customers with **V8 isolates** — the same mechanism Chrome uses to isolate browser tabs inside one process. The runtime (one process, [`workerd`](https://github.com/cloudflare/workerd), open source) is *already running* in every PoP; "deploying" means distributing a few hundred KB of your JavaScript/Wasm to those processes, and "cold start" means constructing an isolate — which takes under 5 ms and is typically hidden entirely inside the TLS handshake. There is no VM to size, no concurrency pool to provision, no region to choose: every PoP runs your code because the marginal cost of an isolate is a few megabytes, not a VM.

The same model dictates the constraints. Isolates share a process, so memory is capped (128 MB) and CPU is the metered resource: **you are billed and limited on CPU time, not wall-clock time** — `await`ing a slow origin for 30 seconds costs you nothing while a 30-second CPU loop is at the cap (free plan: 10 ms CPU; paid: 30 s, configurable to 5 min). This is the exact inverse of Lambda's GB-second wall-clock billing, and it makes Workers economically *perfect* for I/O-bound work (proxying, API composition, auth, rendering) and wrong for sustained number crunching (that's **Containers** — Cloudflare's newer container runtime for the heavy tail — or your origin). The runtime is also not Node: it implements web-standard APIs (`fetch`, `Request`/`Response`, Web Crypto, streams) plus a [Node compatibility layer](https://developers.cloudflare.com/workers/runtime-apis/nodejs/) (`nodejs_compat`) that covers most popular packages — check compatibility before assuming, it's the main migration friction.

### The anatomy of a Worker

```js
// src/index.js — ES modules format; env carries bindings, ctx controls lifecycle
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/health") return new Response("ok");

    // A binding: typed handle to a platform resource, no credentials, no SDK client
    const flag = await env.FLAGS.get("new-checkout");

    // Proxy to origin; log without delaying the response
    const res = await fetch("https://origin.example.com" + url.pathname, request);
    ctx.waitUntil(logRequest(env, request));   // runs after the response is sent
    return new Response(res.body, res);
  },

  async scheduled(event, env, ctx) {           // Cron Triggers (cf. EventBridge → Lambda)
    ctx.waitUntil(reindex(env));
  },
};
```

```toml
# wrangler.toml — the deployment unit plus every binding the code may touch
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
crons = ["0 * * * *"]
```

**Bindings deserve a pause**, because they're the platform's IAM replacement and a better idea than they look: a binding is a capability — the code can use exactly the resources declared in its config, addressed as objects on `env`, with no credentials to leak, no SDK clients to construct, no signature code, and no confused-deputy ambiguity. The wrangler.toml *is* the permission boundary, reviewable in the pull request. (The trade: less expressive than IAM conditions; per-environment declarations — a binding missing from `[env.production]` is the classic deploy-time failure, §21.)

The rest of the working surface: **`ctx.waitUntil`** extends the isolate's life past the response for fire-and-forget work (logs, analytics, cache writes) — the pattern Lambda implements with destinations or queues. **Cron Triggers** give scheduled execution. **Service bindings** let Workers call other Workers in-process — zero-latency RPC, no public hop, enabling real service decomposition at the edge. **Smart Placement** inverts the run-near-the-user default for chatty-with-the-database Workers: if your code makes five sequential D1/Hyperdrive round trips, Cloudflare can run the *Worker* near the data instead, turning five transcontinental round trips into five local ones plus one long client hop — enable it for API backends, leave it off for middleware. **Workflows** add durable, multi-step execution with retries and sleep (the Step Functions shape) for processes that outlive a request.

### Limits that shape designs

| | Free | Paid ($5/mo) |
|---|---|---|
| Requests | 100,000/day | 10M included, then $0.30/M |
| CPU time | 10 ms | 30 s default (to 5 min) |
| Memory | 128 MB | 128 MB |
| Bundle size | 3 MB | 10 MB |
| Subrequests | 50/request | 1,000/request |

Read the table as a design statement: Workers wants many small, I/O-bound invocations. The 128 MB ceiling rules out in-memory datasets (that's KV/cache); CPU metering rules out transcoding (Containers); the bundle limit rules out 200 MB node_modules monoliths (and is a feature — edge code *should* be small).

### Practice

- Build the security-headers middleware: add CSP/HSTS, strip `Server`, deploy, and verify with `curl -sI` that every origin response is rewritten.
- Implement edge A/B testing: assign a bucket cookie in the Worker, persist assignments in KV, route to two origins, and confirm stickiness.
- Use `wrangler dev` locally, then `wrangler tail` against production while you trigger an exception — read the real trace.
- Take a CPU-heavy task (image resize), watch it hit the CPU limit, and re-architect: queue it (§14) or move it to Containers.

Docs: [Workers](https://developers.cloudflare.com/workers/), [How Workers works](https://developers.cloudflare.com/workers/reference/how-workers-works/), [Runtime APIs](https://developers.cloudflare.com/workers/runtime-apis/), [Workflows](https://developers.cloudflare.com/workflows/).

---

## 9. Pages and Static Assets

### AWS mental model

**Amplify Hosting**, or hand-rolled S3+CloudFront+CodePipeline. Pages bundles Git-driven CI/CD, the global CDN, per-commit preview environments, and Workers-powered server functions into one product — with **unlimited static bandwidth on every plan**, which deletes the line item that makes high-traffic static hosting on S3+CloudFront a budgeting exercise.

### The model

Connect a repo; every push builds (500 builds/month free) and deploys; every branch and commit gets its own immutable preview URL — unlimited, free, and the single biggest workflow upgrade for teams used to staging-environment contention. **Pages Functions** (a `functions/` directory of Workers-runtime handlers) add API routes, auth hooks, and SSR — they *are* Workers with filesystem routing, sharing quotas and bindings, so your "static host" and your edge backend are one platform rather than Amplify's hosting-plus-Lambda seam.

The strategic note for new projects: Cloudflare has been converging the two products — **Workers with Static Assets** lets a single Worker serve a static site/SPA *and* its API from one `wrangler deploy`, and it is the recommended path for new full-stack applications (framework adapters for Next/Remix/Astro/SvelteKit target it). Pages remains excellent for the Git-driven static/JAMstack case; treat "Pages vs. Workers + Assets" as a question of whether you want Git-push deploys (Pages) or wrangler/CI deploys with the full Workers feature surface (Workers). The capabilities have effectively merged; the deployment ergonomics differ.

### Practice

- Connect a repo, push a branch, and share the preview URL; merge and watch production update.
- Add a Pages Function reading a KV value at `/api/hello`; note it's just a Worker (same `env`, same limits).
- Price a 1 TB/month static site on Pages vs. S3+CloudFront — then notice which line item did the work.

Docs: [Pages](https://developers.cloudflare.com/pages/), [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/).

---

## 10. R2 (Object Storage)

### AWS mental model

**S3**, nearly API-identical — and one deliberate economic inversion: S3 charges for storage, requests, *and egress per GB* (the item that dominates read-heavy bills and quietly enforces vendor lock-in: moving 100 TB out of S3 costs ~$9,000 in transfer alone); R2 charges storage and operations with **egress at $0, always**. That isn't a discount — it's a different theory of whose data it is, and it makes previously-irrational architectures rational: serve media directly to users, feed training jobs on another cloud, let customers bulk-export, put a competitor's CDN in front — all without a transfer meter running.

### Using it

The S3 compatibility is real — existing tools work by switching endpoint and keys:

```bash
aws s3 cp ./big.parquet s3://my-bucket/big.parquet \
  --endpoint-url https://<accountid>.r2.cloudflarestorage.com
```

Presigned URLs, multipart uploads, conditional requests, and lifecycle rules all behave as an S3 user expects ([compatibility matrix](https://developers.cloudflare.com/r2/api/s3/api/) for the edge cases). From Workers, the **binding** is the better path — no signing, no SDK, streaming bodies in and out:

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

The operational surface: **public buckets** behind a custom domain get the full §4 CDN (cache R2 reads — Class B operations are cheap but cached reads are free); **storage classes** (Standard, Infrequent Access with a 30-day minimum); **event notifications** to Queues (the S3→Lambda trigger pattern, edge-shaped); **location hints and jurisdictions** (R2 doesn't make you pick a region, but you can constrain data to the EU for compliance); and the migration tools — **Super Slurper** (bulk copy from S3/GCS) and **Sippy** (lazy migration: serve from R2, fetch-and-store from S3 on miss — migrate a live bucket with zero downtime and zero double-storage).

The honest cost note: zero egress is not "free everything." Class A operations (writes/lists, $4.50/M) are pricier than S3's; tiny-object-write-heavy workloads can cost *more* on R2. Model `(storage, ops, egress)` as a triple — R2 wins decisively when egress dominates, marginally or not at all when writes do.

### Practice

- `rclone` a real folder into R2; serve it from a public bucket behind a custom domain; verify cache HITs on second reads.
- Wire an R2 event notification → Queue → consumer Worker that thumbnails uploaded images.
- Compute the S3-vs-R2 break-even for a 5 TB library at 1×, 10×, and 100× monthly read multiples; then redo it for a write-heavy logging bucket and watch the answer flip.

Docs: [R2](https://developers.cloudflare.com/r2/), [Migration](https://developers.cloudflare.com/r2/data-migration/), [Event notifications](https://developers.cloudflare.com/r2/buckets/event-notifications/).

---

## 11. D1 (Serverless SQL)

### AWS mental model

By billing shape, **Aurora Serverless v2** (scale-to-zero, pay-per-use) — but the engine is SQLite and the *intended topology* is Aurora's opposite. Aurora wants one big database scaled vertically and read-replicated; D1 wants **many small databases** — per tenant, per user, per shard — each under 10 GB, each cheap enough to create programmatically. Misreading D1 as "my Postgres, but serverless" is the primary source of D1 disappointment; reading it as "a fleet of per-tenant SQLite files with replication and a query API" is the design it rewards. (For the one-big-relational-store shape, the platform's answer is Hyperdrive in front of your own Postgres, §14.)

### Why SQLite at the edge makes sense

SQLite's classic limitation — one writer per database file, no server — becomes a *feature* at this granularity: a per-tenant database has natural write locality (one tenant's requests rarely contend), the 10 GB cap is generous for a tenant and irrelevant across ten thousand of them, and SQLite query latency from a co-located Worker is microseconds-to-milliseconds with no connection pool to manage (the [Database Internals guide](DATABASE_INTERNALS_STUDY_GUIDE.md) is a deep treatment of exactly this engine). D1 adds the missing operational layer: storage with durability, **Time Travel** (point-in-time restore to any minute in the last 30 days — included, not an add-on), and **read replication** with a Sessions API that preserves read-your-writes (your session's reads are routed so you never observe your own write missing — the classic async-replica anomaly, handled at the platform layer).

### Using it

```js
export default {
  async fetch(request, env) {
    const { results } = await env.DB
      .prepare("SELECT id, email FROM users WHERE tenant_id = ? AND active = 1")
      .bind("tenant_42")
      .all();

    await env.DB.batch([            // batched statements: one round trip, one transaction
      env.DB.prepare("INSERT INTO audit(event) VALUES (?)").bind("login"),
      env.DB.prepare("UPDATE users SET last_seen = ? WHERE id = ?").bind(Date.now(), 7),
    ]);

    return Response.json(results);
  },
};
```

```bash
wrangler d1 create app
wrangler d1 migrations apply app          # versioned migrations, in-repo
wrangler d1 execute app --command "SELECT count(*) FROM users"
wrangler d1 export app --output backup.sql
```

Billing is per **rows read / rows written** (plus storage) — a genuinely different meter from instance-hours that makes *query efficiency directly visible in the bill*: a full-table scan of a million rows costs a million row-reads even if it returns ten rows, so the index you should have built shows up in invoices, not just latency. (`EXPLAIN QUERY PLAN` and D1's per-query `meta` — rows read/written per statement — are your instruments.)

### The design constraints, honestly

10 GB per database (hard), one writer per database (SQLite's nature — write throughput is fine for a tenant, wrong for a global firehose), no cross-database joins (your application composes across shards), and Workers-side access only via binding/HTTP API (no wire-protocol clients). The architecture question D1 forces is the right one anyway: *what is your tenancy key?* — because `tenant → database` mapping (a KV lookup or deterministic naming) is the entire sharding layer.

### Practice

- Create a D1 database with versioned migrations; query it with `.bind()`; read the `meta.rows_read` on an unindexed vs. indexed query and price the difference.
- Build the per-tenant pattern: route `X-Tenant-Id` to its own database; create tenant databases lazily on first write.
- Break something with an `UPDATE` missing its `WHERE`; restore with Time Travel; write down the recovery time.

Docs: [D1](https://developers.cloudflare.com/d1/), [Read replication](https://developers.cloudflare.com/d1/best-practices/read-replication/).

---

## 12. KV (Key-Value Store)

### AWS mental model

**DynamoDB global tables** for the shape (global key-value), **DAX** for the spirit (read-path caching) — but the consistency contract is the defining difference: KV is **eventually consistent with a propagation horizon of up to ~60 seconds**, and everything about when to use it follows from that number.

### The architecture behind the 60 seconds

KV is not a database replicated to 330 PoPs — it's **centralized storage with edge caching**. Writes go to central stores; reads are served from the PoP's cache when hot (sub-millisecond) or pulled from the center when cold (tens of ms, then cached). A write therefore doesn't *push* to every PoP; it invalidates lazily, and a PoP that cached the old value may serve it until its TTL lapses — up to about a minute. This design is why KV reads are nearly free at the edge and why KV is exactly wrong for anything where two clients must agree *now*: counters, locks, inventory, anything read-modify-write. (Those are Durable Objects, §13 — strongly consistent because there's exactly one of each object.)

```js
await env.CONFIG.put("feature:checkout-v2", "on", { expirationTtl: 3600 });
const v   = await env.CONFIG.get("feature:checkout-v2");                  // hot-path read
const obj = await env.CONFIG.get("session:abc", { type: "json" });
const hot = await env.CONFIG.get("country-prices", { cacheTtl: 86400 }); // pin in PoP cache longer
const { keys } = await env.CONFIG.list({ prefix: "feature:" });
```

The API is deliberately small — `get`/`put`/`delete`/`list(prefix)`, value TTLs, metadata, `cacheTtl` to trade staleness for hit rate per read. There are no secondary indexes and no queries; **the key schema is your data model** (prefix design = your "tables"; `list` is your only scan, and it's by prefix). Writes are the expensive operation in both dollars ($5/M vs. $0.50/M reads) and convergence; a Worker that writes KV on every request is misusing the product — that pattern wants Durable Objects, Analytics Engine (§19), or a Queue.

### The fit

KV's sweet spot is data that is **read constantly, written rarely, and tolerant of a stale minute**: feature flags, configuration, A/B assignments, redirects/routing tables, cached API lookups, signed-URL allowlists, session data *if* sessions tolerate eventual consistency (issue-once-read-many JWTs do; revocation lists don't). One honest sentence per alternative: need read-your-writes → Durable Objects; need queries → D1; bigger than ~25 MB values or binary blobs → R2.

### Practice

- Store feature flags; read them in §8's A/B Worker; measure hot-read latency from two continents (deploy the same Worker, hit it via VPN).
- Demonstrate the consistency window: write from one location, poll from another, time convergence — then repeat with `cacheTtl: 300` and watch the window widen exactly as configured.
- Justify, in writing, which of KV/D1/DO holds a shopping cart, a feature flag, and an inventory count — one sentence each, naming the consistency requirement.

Docs: [KV](https://developers.cloudflare.com/kv/), [How KV works](https://developers.cloudflare.com/kv/concepts/how-kv-works/).

---

## 13. Durable Objects (Stateful Coordination)

The most original primitive on the platform, and the one with no AWS analog: a **globally unique, single-threaded, stateful object** addressed by name. Where everything else in this guide scales by being stateless and everywhere, a Durable Object scales by being *exactly one place* — which is precisely what coordination problems need.

### AWS mental model

There isn't one; you'd assemble it. The closest constructions — DynamoDB with conditional writes plus a single-writer Lambda convention, or a WebSocket service on ECS with Redis for coordination and sticky sessions — all approximate the same goal: *serialize operations on one entity*. A DO collapses the assembly into a primitive: `idFromName("room:lobby")` always routes to the same instance, wherever on the planet the request entered, and that instance processes requests **one at a time** with private, durable storage attached. Single-threaded execution is the whole trick: there are no race conditions on an object's state because there is no concurrency *within* an object — serializability by construction, no locks, no conditional-write retry loops.

```js
export class Room {
  constructor(state, env) {
    this.state = state;               // durable storage + this instance's memory
  }
  async fetch(request) {
    // Read-modify-write with NO race: only one request runs at a time in here
    let count = (await this.state.storage.get("count")) ?? 0;
    count++;
    await this.state.storage.put("count", count);
    return new Response(`count=${count}`);
  }
}

export default {                       // the routing Worker
  async fetch(request, env) {
    const id = env.ROOMS.idFromName(new URL(request.url).pathname);  // name → the one instance
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
new_sqlite_classes = ["Room"]          # modern DOs: per-object SQLite storage
```

### The machinery that makes it production-grade

**Placement and movement**: an object is created near the first request that addresses it and can migrate; you don't manage location, but you should know latency to a DO is "distance to wherever it lives," not "distance to nearest PoP" — a chat room with participants on two continents is fast for one side. **Per-object SQLite**: modern DOs back `state.storage` with a private SQLite database (yes — each object is a tiny database; the §11 engine at a finer granularity), supporting key-value *and* SQL access with transactional semantics. **WebSocket hibernation**: a DO holding 10,000 idle chat connections would be prohibitively expensive if it had to stay resident; hibernation lets the runtime evict the object from memory *while keeping the sockets open*, re-instantiating it when a message arrives — this single feature is what makes DO-per-room real-time architecture economical. **Alarms**: `state.storage.setAlarm(when)` schedules the object to wake itself — per-entity timers (session expiry, delayed retries, game ticks) without any external scheduler; with millions of objects you have millions of independent timers, a shape EventBridge simply doesn't offer.

### Designing with DOs

The unit of consistency is the unit of throughput: one object is serial, so **shard by the natural entity** — a DO per room, per document, per user, per API key — and the single-threadedness that bounds one object's throughput becomes irrelevant across millions of them. The standard patterns: real-time collaboration (one DO per document, WebSocket fan-out, hibernation), exact rate limiting (DO per API key — compare §7's edge rate limiting, which is fast but approximate across PoPs; a DO counter is exact because it's singular), coordination primitives (seat reservation, auction state, queues with strict ordering per key), and presence. The anti-pattern is equally clear: a *global* singleton DO in the request path is a planet-wide serial bottleneck — if an object's name doesn't contain an entity ID, look again.

### Practice

- Build the atomic counter; hammer it from two clients on different continents; verify no lost updates — then implement the same counter on KV and demonstrate the lost update.
- Build a chat room with WebSocket hibernation; verify (via logs) the object evicts while sockets stay connected.
- Use an alarm to expire idle rooms after 10 minutes; then sketch the DO-per-API-key exact rate limiter and compare its guarantees and latency with §7's.

Docs: [Durable Objects](https://developers.cloudflare.com/durable-objects/), [WebSocket hibernation](https://developers.cloudflare.com/durable-objects/best-practices/websockets/), [Alarms](https://developers.cloudflare.com/durable-objects/api/alarms/).

---

## 14. Queues, Hyperdrive, Vectorize, Workers AI, and AI Gateway

The glue tier: each service maps to a familiar AWS shape, re-cut for the Workers runtime. Treated briefly but mechanically.

### Queues (≈ SQS)

Producer/consumer messaging where the consumer is a Worker the platform invokes with **batches** — push, not poll, so there is no idle polling loop and no per-poll charge. Semantics are SQS-shaped: at-least-once delivery (consumers must be idempotent — the [Enterprise APIs guide](ENTERPRISE_API_STUDY_GUIDE.md) treats this discipline in depth), per-message `ack()`/`retry()`, configurable batch size/timeout, max retries, and a dead-letter queue.

```js
// Producer (any Worker)
await env.MY_QUEUE.send({ userId: 42, action: "welcome-email" });

// Consumer
export default {
  async queue(batch, env) {
    for (const msg of batch.messages) {
      try { await process(msg.body); msg.ack(); }
      catch { msg.retry(); }              // dead-letters after max retries
    }
  },
};
```

Standard uses: decoupling slow work from request paths, smoothing write bursts before D1, fan-out from R2 event notifications (§10). Throughput is solid but not Kafka — high-volume event streaming wants a real broker; this is the SQS slot, not the Kinesis slot.

### Hyperdrive (≈ RDS Proxy + a global cache)

The bridge to databases you already have. The problem it solves is structural: a popular Worker runs in hundreds of PoPs, and Postgres connections are expensive, stateful, and *regional* — naive edge→Postgres means connection storms (the Lambda+RDS disease, multiplied by geography) plus a TCP+TLS+auth handshake's worth of round trips per query from the wrong continent. Hyperdrive maintains **warm connection pools near your database**, lets edge Workers borrow pooled connections over Cloudflare's backbone, and optionally **caches read query results** at the edge. Your code stays a normal `pg`/`mysql` driver pointed at Hyperdrive's connection string:

```js
import { Client } from "pg";
const client = new Client({ connectionString: env.HYPERDRIVE.connectionString });
await client.connect();
const { rows } = await client.query("SELECT * FROM orders WHERE id = $1", [id]);
```

This is the single most important service for **Pattern B** adopters (§20): it makes "Workers in front, your Postgres behind" a real architecture instead of a latency trap. Pair with Smart Placement (§8) when query *count* per request is high.

### Vectorize (≈ OpenSearch k-NN) and Workers AI (≈ Bedrock)

**Vectorize** is a managed vector index — store embeddings with metadata, query top-K by cosine/euclidean/dot — designed to be the retrieval half of edge RAG. **Workers AI** runs a curated catalog of open models (Llama-class LLMs, embedding models, Whisper, image generation) on Cloudflare's GPUs, invoked through a binding and billed per-unit ("neurons") with no endpoint to provision or scale — the serverless end of the Bedrock/SageMaker spectrum:

```js
// Minimal RAG: embed → retrieve → generate, all platform-native
const emb = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: [question] });
const ctxDocs = await env.VECTORIZE.query(emb.data[0], { topK: 5, returnMetadata: true });
const answer = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", {
  prompt: `Context:\n${ctxDocs.matches.map(m => m.metadata.text).join("\n")}\n\nQ: ${question}`,
});
```

Honest positioning: the catalog is open-weights models, not frontier APIs — ideal for embeddings, classification, summarization, and cost-sensitive generation; your GPT/Claude calls still go to their providers, which is exactly what the last piece fronts:

### AI Gateway (≈ a missing AWS product)

A proxy for LLM API traffic — point your OpenAI/Anthropic/Workers AI calls through it and get **caching** (identical prompts answered from cache — real money on repetitive workloads), **rate limiting and budgets** per key/user, **retries and provider fallback**, and **analytics/logging** of every prompt and cost, in one place. It's an hour to adopt (change the base URL) and is frequently the first Cloudflare product an AI team uses; the [AI Agents guide](AI_AGENTS_STUDY_GUIDE.md) covers the application-side patterns it supports.

### Practice

- Build the queue pipeline: R2 upload event → Queue → consumer that processes with deliberate 20% failures → verify retries and DLQ contents.
- Put Hyperdrive in front of a free-tier Neon/RDS Postgres; measure query latency from a Worker with and without it, from your nearest and a far PoP.
- Ship the minimal RAG endpoint above against a folder of your own docs; then route an OpenAI call through AI Gateway and find the cache-hit analytics.

Docs: [Queues](https://developers.cloudflare.com/queues/), [Hyperdrive](https://developers.cloudflare.com/hyperdrive/), [Vectorize](https://developers.cloudflare.com/vectorize/), [Workers AI](https://developers.cloudflare.com/workers-ai/), [AI Gateway](https://developers.cloudflare.com/ai-gateway/).

---

## 15. Zero Trust / Access

### AWS mental model

**Verified Access** (identity-aware app access) + **Client VPN** + **Cognito** for IdP glue, plus a secure web gateway you'd buy elsewhere. Cloudflare One bundles ZTNA, SWG, browser isolation, and DLP into one control plane, enforced at the same PoPs as everything else — the "delivered from the network you already use" coherence again.

### The model

"Zero Trust" operationalized is one sentence: **every request to a protected resource is evaluated against identity + device + context, with no notion of a trusted network**. The pieces: **Access** is the ZTNA core — put any application (public hostname or private network service) behind a policy engine that authenticates against your IdP (Okta, Entra, Google — or several at once, which is genuinely useful for contractor populations) and evaluates rules (email domain, group, country, device posture, MFA recency) *per request*, not per session-on-a-network. **Gateway** is the outbound half — DNS/HTTP/network filtering for enrolled devices (malware domains, category blocks, tenant controls). The **WARP client** enrolls devices, routes their traffic through Gateway, and reports **device posture** (disk encryption, OS version, EDR presence) that Access policies can require. **Browser Isolation** runs risky browsing on Cloudflare's machines, streaming pixels; **DLP** inspects data in motion.

Two architectural notes that make Access click. First, it works **clientless** for web apps — protect `internal.example.com` and users just browse to it; the edge enforces login before your origin sees a byte (combine with a Tunnel, §16, and the app has *no* network exposure at all — this pairing is the modern replacement for "VPN into the office network"). Second, Access issues a signed JWT per authenticated request (`Cf-Access-Jwt-Assertion`) that your application **must verify** if it makes its own authorization decisions — treating Access as the only check while leaving the origin reachable by other paths is the classic half-migration hole.

Per-app, per-identity policy beats network reachability on blast radius: a phished contractor credential exposes the three apps that identity could reach, not a flat /16 of internal network. That sentence is the entire business case, and the migration is incremental — one application at a time, VPN retired at the end rather than the beginning.

### Practice

- Protect an internal tool with Access + Google SSO, policy = your email domain + MFA within 24h; verify the login interstitial and inspect the JWT.
- Add device posture (disk encryption) and watch an unenrolled device get denied with a useful error.
- Verify the JWT server-side (Access publishes the public keys) and log the identity into your app's audit trail.

Docs: [Cloudflare One](https://developers.cloudflare.com/cloudflare-one/), [Access policies](https://developers.cloudflare.com/cloudflare-one/policies/access/), [JWT validation](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/).

---

## 16. Cloudflare Tunnels

### AWS mental model

No clean analog — the *intent* overlaps SSM Session Manager (reach private things without inbound ports) and ALB-with-private-targets, but the mechanism is its own: a connector daemon **dials out**, and Cloudflare publishes your service through that outbound connection.

### The inversion

Ordinary publishing means accepting inbound connections: open ports, public IPs, firewall rules, attack surface. A Tunnel inverts the arrow — `cloudflared` (or a router/appliance integration) establishes a few **outbound, long-lived connections** to nearby PoPs (four connections to two data centers by default; run multiple replicas for HA), and traffic for your hostnames flows *down* those connections. The origin needs no public IP, no open inbound port, no firewall exception beyond "allow outbound 443" — which it already has. The security consequence is categorical, not incremental: there is no address to scan, no port to probe, no way to reach the service except through Cloudflare's pipeline with whatever WAF/Access policy you attached. Combined with §15, this is how "internal app, accessible from anywhere, exposed to nothing" is actually built.

```bash
cloudflared tunnel login
cloudflared tunnel create my-app
```

```yaml
# config.yml — map public hostnames to local services
tunnel: my-app
credentials-file: /root/.cloudflared/<id>.json
ingress:
  - hostname: app.example.com
    service: http://localhost:8080
  - hostname: ssh.example.com
    service: ssh://localhost:22
  - service: http_status:404        # required catch-all
```

```bash
cloudflared tunnel run my-app
```

Beyond per-hostname publishing, Tunnels also route **private networks**: advertise RFC1918 ranges through the tunnel and WARP-enrolled users (§15) reach them as if VPN'd — the actual VPN-replacement data path. For development, **Quick Tunnels** (`cloudflared tunnel --url localhost:3000`) give an instant `trycloudflare.com` URL with no account — the ngrok use case, free. Tunnels themselves are free on every plan; remote management (dashboard/Terraform-defined configuration rather than local config files) is the operationally sane mode for fleets.

### Practice

- Publish a local dev server through a named tunnel; put Access in front; verify the origin firewall can drop *all* inbound and everything still works.
- Add the SSH ingress and connect with `cloudflared access ssh` — no public port 22 anywhere.
- Run two replicas, kill one mid-request-stream, and observe the failover.

Docs: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

---

## 17. Traffic Engineering: Load Balancing, Argo, and Spectrum

Three services that steer bytes rather than judge them, grouped because they answer adjacent questions: *which origin?* (Load Balancing), *which path?* (Argo), *what about non-HTTP?* (Spectrum).

### Load Balancing (≈ Route 53 health checks + ELB/Global Accelerator)

Cloudflare LB steers across **pools** of origins — yours, anywhere: multi-cloud, on-prem, mixed — with active health **monitors** (HTTP/TCP/ICMP probes from multiple regions; a failing origin is removed from rotation proactively, and the failover is at the *proxy* layer, so it takes effect immediately rather than waiting out DNS TTLs as Route 53 failover must for unproxied records). Steering policies per LB: failover by priority order, weighted random, geo (map regions to pools), proximity (nearest pool by latency), dynamic (least-RTT), and least-outstanding-requests; **session affinity** (cookie-based) covers stateful legacy apps. The AWS contrast worth stating: this is *global* server load balancing across heterogeneous origins, the Route 53+Global Accelerator role — it does not replace your *intra-VPC* ALB, which keeps balancing across targets behind one origin.

### Argo Smart Routing (≈ Global Accelerator)

The default path from PoP to origin is BGP's choice, and BGP optimizes for policy, not latency. Argo routes edge↔origin traffic over **measured paths across Cloudflare's backbone** — real-time latency/loss data from the traffic Cloudflare already carries picks the route — typically ~30% faster for dynamic (uncacheable) traffic, with the biggest wins on long, congested routes. One toggle, usage-priced, and it also upgrades Tiered Cache's topology decisions. Decision rule: significant far-from-origin user population + dynamic traffic → measure it (the dashboard shows projected improvement); all-cacheable traffic → the cache already solved this.

### Spectrum (≈ NLB + Global Accelerator + Shield, for raw TCP/UDP)

Everything in this guide so far assumed HTTP. **Spectrum** extends the anycast network to **arbitrary TCP/UDP services** — game servers, MQTT brokers, SMTP, SSH, custom protocols: clients connect to anycast IPs at the nearest PoP, getting the §5 DDoS absorption and origin-hiding for protocols the L7 proxy can't parse, with optional TLS termination and (for some protocols) limited L7 awareness. The mental slot: when the answer to "can I orange-cloud this?" is "it's not HTTP," Spectrum is how it still gets Cloudflare's network (Enterprise-leaning; per-GB pricing — the one place Cloudflare meters bandwidth, because this traffic can't be cached).

### Practice

- Two origin pools in different regions, HTTP monitors, geo steering with a fallback pool; kill the primary's health endpoint and time the failover (compare with a DNS-TTL-based failover).
- Enable Argo on a zone with a far-away origin; compare TTFB percentiles for an uncacheable endpoint before/after.
- Sketch which of your services would need Spectrum vs. gray-cloud DNS, and what each choice gives up.

Docs: [Load Balancing](https://developers.cloudflare.com/load-balancing/), [Argo](https://developers.cloudflare.com/argo-smart-routing/), [Spectrum](https://developers.cloudflare.com/spectrum/).

---

## 18. Media: Images and Stream

Two vertically-integrated media pipelines whose pitch is identical: replace an assembled AWS chain with one product whose pricing dimension matches how you think about the asset.

**Images** (≈ S3 + Lambda/Sharp + CloudFront, pre-assembled): store originals (or reference them in R2/external URLs), request **variants** by URL parameters (width, quality, format — with automatic AVIF/WebP negotiation per browser), deliver via the CDN. Pricing is per image stored/delivered and per *unique transformation* — and that last meter is the operational gotcha: every distinct parameter combination is a billable variant, so an `<img>` tag generating arbitrary widths from a slider can mint thousands of "unique transformations" from one photo. Standardize a preset ladder (e.g., 320/640/1280/2560) and the meter behaves. The build-vs-buy line: if you already run an image pipeline you control, R2 + a resizing Worker is cheaper at scale; Images is the "stop owning this pipeline" option.

**Stream** (≈ IVS + MediaConvert + MediaLive + CloudFront): upload or ingest live (RTMPS/SRT/WHIP), Cloudflare handles transcoding to adaptive bitrates, storage, global delivery, a drop-in player (or HLS/DASH endpoints for your own), captions, thumbnails, and signed-URL access control. The pricing dimension is the product's best argument: **per 1,000 minutes stored and per 1,000 minutes delivered** — watch time, a number a product manager can forecast — versus the AWS chain's per-GB egress + per-minute transcode + per-request math. Encoding and ingest are free; you pay for minutes sitting in storage and minutes watched.

### Practice

- Serve one photo at three preset widths; check the Images analytics for unique-transformation count; then deliberately request 50 arbitrary widths and watch the meter (on the free tier) to internalize the lesson.
- Upload a video to Stream, embed the player, watch it from two devices, and reconcile the delivered-minutes metric with your actual watch time.

Docs: [Images](https://developers.cloudflare.com/images/), [Stream](https://developers.cloudflare.com/stream/).

---

## 19. Observability and Automation

The section the dashboard-tour version of Cloudflare skips: how you see what the platform is doing, and how you manage it like infrastructure instead of like a control panel.

### Seeing: from tail to Logpush

The observability ladder, in order of ceremony: **`wrangler tail`** streams live Worker logs/exceptions to your terminal (per-invocation, sampled under load — the development and incident tool). **Workers Logs** persists structured logs with dashboard querying. **Logpush** (Business/Enterprise for zone-level datasets; Workers trace events on paid plans) is the real pipeline: batched delivery of HTTP request logs, firewall events, and Worker traces to R2, S3, Datadog, Splunk, or any HTTP endpoint — the Kinesis-Firehose slot, and the input your SIEM actually wants. **Analytics dashboards and the GraphQL Analytics API** cover aggregate questions (traffic, cache ratios, WAF actions by rule — the API is how you wire Cloudflare metrics into Grafana).

The genuinely novel piece is **Workers Analytics Engine**: write-time metrics from Worker code (`env.METRICS.writeDataPoint({ blobs: [route], doubles: [latencyMs], indexes: [customerId] })`) into a time-series store queried with SQL — high-cardinality custom metrics (per-customer! per-API-key!) at costs that would make CloudWatch custom metrics blush, designed exactly for "I want a latency histogram per tenant without paying per time series."

### Managing: API, Terraform, and tokens

Everything in the dashboard is the **v4 REST API** underneath, and the [**Terraform provider**](https://registry.terraform.io/providers/cloudflare/cloudflare/latest) covers the surface — zones, DNS, rulesets (WAF rules as code), Workers, R2, Access policies, Tunnels, Load Balancers. Two disciplines transfer directly from AWS practice: **scoped API tokens** (per-purpose tokens with minimal permissions — "edit DNS in zone X" — not the legacy account-wide Global API Key, which should be treated as radioactive), and **config-as-code for anything you'd grieve**: WAF rulesets and Access policies in Terraform get you review, history, and rollback — the dashboard-edited security policy that nobody remembers changing is a Cloudflare-flavored incident à la the unreviewed security-group change. For Workers specifically, wrangler + CI (the [GitHub Action](https://github.com/cloudflare/wrangler-action)) with `[env.staging]`/`[env.production]` environments is the standard pipeline; preview URLs and gradual deployments (percentage-based rollout between Worker versions) cover the release-engineering basics.

### Practice

- Wire `writeDataPoint` into a Worker recording per-route latency; query p50/p95 by route with the Analytics Engine SQL API.
- Set up Logpush of firewall events to R2; query a day of events with `rclone`+`duckdb` (or R2 SQL) for top blocked ASNs.
- Import an existing zone's DNS + one WAF rule into Terraform (`cf-terraforming` helps); make the next rule change via PR.

Docs: [Workers observability](https://developers.cloudflare.com/workers/observability/), [Logpush](https://developers.cloudflare.com/logs/), [Analytics Engine](https://developers.cloudflare.com/analytics/analytics-engine/), [Terraform provider](https://developers.cloudflare.com/terraform/), [API tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/).

---

## 20. Architecture Patterns

How the pieces compose into real systems — three patterns that cover most adoptions, plus the storage decision every Cloudflare application makes.

### Pattern A: Full-stack on Cloudflare

```
Users → CDN/WAF → Worker (API + SSR, Static Assets for the frontend)
                    ├─ D1 (relational, per-tenant)
                    ├─ KV (config/flags/cached lookups)
                    ├─ R2 (uploads/media)
                    ├─ Durable Objects (real-time/coordination)
                    └─ Queues (async) → consumer Worker
```

What makes this more than a list: there are **no regions to choose, no VPC to plumb, no egress between any of these services, and one deploy artifact** — and the constraints come as a package too (128 MB/CPU-time compute, 10 GB D1 shards, eventual KV). It's the right shape for SaaS products, APIs, and sites whose backend is I/O-and-glue; it's the wrong shape for heavy compute and one-giant-database designs. The AWS equivalent (CloudFront+Lambda+API GW+Aurora+DynamoDB+S3+SQS+ElastiCache) is more powerful at the high end and costs that power in assembly, egress, and cold starts.

### Pattern B: Cloudflare in front of existing infrastructure

The most common adoption, because it's additive and reversible: keep the app on AWS/GCP/on-prem; move **DNS, TLS, CDN, WAF, DDoS, and Access** to the edge. The hardening ladder within the pattern: proxy the records (§2) → Full-strict TLS (§3) → firewall origin to Cloudflare IPs → replace even that with a **Tunnel** (§16) so the origin has no inbound surface at all. Then the optional compute creep: a Worker for redirects and headers, then A/B and personalization, then **Hyperdrive** (§14) when edge code needs the existing Postgres. Each step is independently shippable and independently reversible — which is the actual reason this pattern wins migration reviews.

### Pattern C: Edge offload / strangler

The incremental rewrite: move *concerns* (not services) to the edge one at a time — bot filtering and rate limiting to the WAF, static and media to R2+CDN, image variants to Images, auth to Access/Worker middleware, new endpoints as Workers — while the monolith shrinks behind it. The strangler-fig pattern with the edge as the fig; §8's service bindings make the eventual decomposition real rather than aspirational.

### The storage decision

| Need | Service | Because |
|------|---------|---------|
| Read-heavy config/flags, staleness OK | KV | edge-cached reads, ~60s convergence (§12) |
| Relational queries, tenant-scoped | D1 | SQLite-per-shard, rows-based billing (§11) |
| Files, media, backups | R2 | zero egress (§10) |
| Exact counters, locks, real-time | Durable Objects | single-threaded strong consistency (§13) |
| Existing Postgres/MySQL | Hyperdrive | pooled + cached second hop (§14) |
| Embeddings | Vectorize | top-K retrieval at the edge (§14) |

The table is a consistency-and-cost menu, not a feature menu — pick by the *guarantee* the data needs, then check the price dimension fits the access pattern.

---

## 21. Common Pitfalls & Gotchas

Each of these is a §-reference plus a war story compressed to a sentence:

- **Gray-cloud surprise** (§2): WAF/CDN/Workers only apply to proxied records. Check the cloud color before debugging anything else.
- **Origin IP leakage** (§2): proxying hides nothing if the origin IP is in old DNS records, cert-transparency logs, or SPF. Firewall to Cloudflare ranges or use a Tunnel.
- **Flexible SSL** (§3): plaintext second hop + the redirect-loop generator. Full (strict) with an Origin CA cert, day one.
- **Caching authenticated HTML** (§4): "Cache Everything" without a cookie bypass eventually serves user A's page to user B. Scope HTML caching to anonymous traffic.
- **CPU time vs. wall time** (§8): awaiting slow origins is free; computing is metered. Heavy CPU belongs in Containers or behind a queue.
- **KV is not a database** (§12): ~60s convergence and $5/M writes punish counters, locks, and per-request writes. Coordination is Durable Objects.
- **The global singleton DO** (§13): a Durable Object whose name has no entity ID is a planetary serial bottleneck. Shard by the natural entity.
- **D1 as one big database** (§11): the 10 GB cap and single writer are the design, not the limitation. Shard by tenant or use Hyperdrive + Postgres.
- **Edge → regional DB without Hyperdrive** (§14): connection storms plus per-query intercontinental round trips. Hyperdrive, and consider Smart Placement.
- **Bindings are per-environment** (§8): the binding you added to dev but not `[env.production]` is the classic instant rollback.
- **R2 zero egress ≠ free everything** (§10): Class A operation-heavy workloads can cost more than S3. Model ops, storage, *and* egress.
- **Image transformation sprawl** (§18): every unique parameter combo is billable. Preset ladders, not free-form params.
- **Access without JWT verification** (§15): if the origin is reachable by any other path, the edge login is decoration. Verify `Cf-Access-Jwt-Assertion` or close the other paths.
- **Rate limiting by IP alone** (§7): CGNAT makes IP-keyed limits punish whole carriers. Key by the identity the request carries.
- **Dashboard-only configuration** (§19): the unreviewed WAF change is this platform's unreviewed security group. Terraform what you'd grieve.

---

## 22. Plan Comparison & Pricing

### Zone plans (per domain — the network/security half)

| Plan | Price | What it actually gates |
|------|-------|------------------------|
| **Free** | $0 | Real CDN, DNS, unmetered DDoS, basic WAF (limited custom rules), Universal SSL — a production-grade free tier, genuinely |
| **Pro** | $20/mo | Managed WAF rulesets, image optimization (Polish/Mirage), more rules |
| **Business** | $200/mo | WAF Attack Score, PCI, 100% uptime SLA, Logpush for zone datasets, advanced rate limiting |
| **Enterprise** | Custom | Bot Management, API Shield, Foundation DNS, account-level rulesets, support/SLA |

### Developer platform (account-level; the $5/mo Workers Paid plan unlocks most of it)

| Product | Free-tier highlight | Paid meter |
|---------|--------------------|------------|
| Workers | 100K req/day | $0.30/M requests + $0.02/M CPU-ms |
| Pages | Unlimited static bandwidth | builds + Functions at Workers rates |
| R2 | 10 GB, free egress forever | $0.015/GB-mo + ops; egress $0 |
| D1 | 5M rows read/day | per M rows read/written + storage |
| KV | 100K reads/day | $0.50/M reads, $5/M writes |
| Durable Objects | with Workers Paid | requests + duration + storage |
| Queues | with Workers Paid | per M operations |
| Zero Trust | 50 users free | $7/user/mo |
| Tunnels | free, unlimited | — |

The structural reading, which matters more than the numbers: zone plans price *security features per domain*; the developer platform prices *usage per account*; and the two systematically-absent meters — **bandwidth** (except Spectrum) and **per-region anything** — are where the economics genuinely differ from AWS, not just the rates.

---

## 23. Decision Trees

### "Which compute?"

```
Static assets only?                         → Pages / Workers Static Assets
Request shaping, APIs, SSR, I/O-bound?      → Workers
Strong consistency / real-time state?       → Durable Objects (fronted by a Worker)
Sustained CPU / container image?            → Workers Containers, or origin behind a Tunnel
Multi-step, retryable, long-running?        → Workflows
```

### "Which storage?"

```
Files/blobs/media?                          → R2
Relational, per-tenant, <10 GB shards?      → D1
Read-mostly config/flags, eventual OK?      → KV
Exact counters/locks/coordination?          → Durable Objects
Existing Postgres/MySQL?                    → Hyperdrive in front of it
Embeddings / semantic search?               → Vectorize
High-cardinality metrics?                   → Analytics Engine
```

### "Adopt Cloudflare how?"

```
Existing app elsewhere?      → Pattern B: DNS/TLS/CDN/WAF in front → Tunnel → Hyperdrive
Greenfield app?              → Pattern A: Workers + D1/KV/R2/DO/Queues
Big monolith, chip away?     → Pattern C: strangler — WAF, static, media, then endpoints
Not HTTP?                    → Spectrum (or gray-cloud + your own protections)
```

### Quick reference: when to use what

| Need | Service | AWS analog |
|------|---------|-----------|
| Speed up site globally | CDN + Argo | CloudFront + Global Accelerator |
| Protect from attacks | DDoS + WAF | Shield + AWS WAF |
| Stop CAPTCHA pain | Turnstile | (reCAPTCHA replacement) |
| Validate API traffic | API Shield | API Gateway validation + mTLS |
| Host static / JAMstack | Pages | Amplify / S3+CloudFront |
| Edge server logic | Workers | Lambda / Lambda@Edge |
| S3 without egress | R2 | S3 |
| Per-tenant SQL | D1 | Aurora Serverless |
| Edge config cache | KV | DynamoDB + DAX |
| Real-time coordination | Durable Objects | (assemble) |
| Async jobs | Queues | SQS |
| Reach existing Postgres | Hyperdrive | RDS Proxy |
| RAG / vector search | Vectorize (+ Workers AI) | OpenSearch + Bedrock |
| LLM traffic control | AI Gateway | (assemble) |
| Replace the VPN | Access + WARP + Tunnels | Verified Access + Client VPN |
| Raw TCP/UDP protection | Spectrum | NLB + Global Accelerator |
| Images / video | Images / Stream | S3+Lambda / IVS+MediaConvert |
| Steer across origins | Load Balancing | Route 53 + ELB |
| Ship logs to SIEM | Logpush | Kinesis Firehose |

---

## Where to Go Next

- **Read the [Workers docs](https://developers.cloudflare.com/workers/)** front to back — the platform half of Cloudflare is Workers plus its bindings, and the [examples gallery](https://developers.cloudflare.com/workers/examples/) covers most real patterns in copy-adaptable form.
- **Read the [Durable Objects docs](https://developers.cloudflare.com/durable-objects/)** carefully before designing stateful edge systems — the single-instance consistency model is the platform's most distinctive idea and its easiest to misuse.
- **Follow the [Cloudflare blog](https://blog.cloudflare.com/)'s engineering posts** — the deep dives on how Workers isolates, R2, and the network actually work are primary sources, not marketing.
- **Ship one project on the free tier:** a Worker + R2 + D1 app behind a custom domain with a Tunnel to something private — it exercises both halves of the platform and costs nothing.
- **Adjacent guides in this repo:** [Networking Fundamentals](NETWORKING_FUNDAMENTALS.md) (DNS/TLS/CDN mechanics), [Enterprise APIs](ENTERPRISE_API_STUDY_GUIDE.md) (rate limiting and caching at the edge), [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) (Durable Objects' killer use case), and [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) (the consistency trade-offs the edge model makes).

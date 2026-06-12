# Observability Study Guide

A depth-first guide to production observability for working engineers. Assumes you've shipped something that handles real traffic, paged at 3 AM, and stared at a dashboard wondering whether the number you're looking at means anything. Each phase builds on the previous. The goal: by the end, you can design an observability stack from scratch, instrument a service end to end, write SLOs that survive contact with reality, and pick tools without being sold to. The applied phases (12–14) walk through real instrumentation, burn-rate SLO math, runbook design, and the anatomy of a production observability stack — like the dbt project layout in [DATA_ENGINEERING_STUDY_GUIDE.md](DATA_ENGINEERING_STUDY_GUIDE.md) and the recipes in [CRYPTO_FUNDAMENTALS.md](CRYPTO_FUNDAMENTALS.md), but for telemetry.

> Observability is not about graphs. It's about the speed at which a stranger to your system can answer a novel question about it. If your dashboards only answer the questions you anticipated, you have monitoring, not observability.

---

## Phase 1: Foundations

### 1.1 Monitoring vs. Observability

The words are often used interchangeably. They are not the same.

- **Monitoring** is *known unknowns*. You decide in advance what to measure (CPU, request rate, error rate), set thresholds, and alert when they're crossed. Monitoring answers questions you thought to ask.
- **Observability** is *unknown unknowns*. You instrument the system so that, *after* the fact, you can ask new questions and get answers without redeploying. Observability is a property of the system, not a tool you bolt on.

A monitoring system tells you the order-placement endpoint is slow. An observable system lets you pivot from "slow endpoint" to "slow for users on Android 14, in EU-West, with a specific feature flag enabled, when their cart contains a digital-only item" — without writing new code or shipping new metrics.

The crisp version of the definition, from [Charity Majors](https://www.honeycomb.io/blog/observability-3-pillars-fallacy): observability is the ability to ask arbitrary questions about your system's behavior, in high cardinality and high dimensionality, without having predicted those questions in advance.

### 1.2 The "Three Pillars" Framing — and Its Critics

The dominant teaching framework since ~2017 has been the **three pillars**: metrics, logs, traces. Each pillar gives you a different angle on the same system.

| Pillar  | Strength                                                  | Weakness                                              |
|---------|-----------------------------------------------------------|-------------------------------------------------------|
| Metrics | Cheap, aggregable, real-time, math-friendly               | Low cardinality, no per-request context               |
| Logs    | Rich free-form context, easy to add                       | Expensive, unstructured by default, hard to aggregate |
| Traces  | Per-request causal graph across services                  | Costly, requires propagation discipline, sampled      |

The pillars are a useful first map. The critique, popularized by Honeycomb, is that the three-pillar framing leads to **three siloed tools and three storage backends**. You jump from Grafana to Splunk to Jaeger trying to correlate one incident across them. The information is in the system; the friction is in the tools.

The post-pillars framing: a single **wide, structured event** per unit of work, with high cardinality, that you can aggregate into metrics, slice into traces, and read as logs. OpenTelemetry's data model points this direction. In practice, most organizations still run three (or four, with profiles) tools and connect them via shared IDs and a unifying frontend like Grafana.

Both framings are right. Use pillars when teaching juniors. Use the event model when designing for cardinality.

### 1.3 Cardinality, the Central Constraint

If you remember one thing from this guide: **cardinality is the constraint that drives every other observability decision**.

**Cardinality** is the number of distinct label combinations on a metric (or distinct values of a dimension on an event). A counter `http_requests_total` labeled by `path` and `status` has cardinality `unique(path) × unique(status)`. Add `user_id` and you go from hundreds to millions. Add a UUID-shaped `request_id` and you go to infinity.

Why this matters: every distinct label combination is a separate time series in Prometheus, a separate index entry in Loki, a separate row in your TSDB. Prometheus storage cost grows linearly in active series; query cost grows worse. A cardinality explosion is the single most common way to take down your observability system *and* your alerting *and* your dashboards at the same time. Mimir, Cortex, and Datadog all have hard-coded per-tenant series limits because of this.

Rules of thumb:
- **Metric labels** must be low cardinality. Status code? Yes. Endpoint pattern (`/users/:id`, not `/users/12345`)? Yes. Tenant ID with 10K tenants? Maybe, with sharding. User ID? Never.
- **High-cardinality dimensions belong on events/traces**, where each row stands alone and you aggregate at query time. This is why Honeycomb pitches a single events store: arbitrary dimensions, no pre-aggregation.
- **Histogram buckets multiply cardinality** by their count. A 10-bucket histogram with 100 endpoint × 5 status = 5000 series. Watch out.

The mental model: metrics are pre-aggregated time series; events/traces/logs are post-aggregated. You trade cardinality flexibility for storage cost. Knowing where on this spectrum you need to be is the design question.

### 1.4 What Observability Is For

The end users of your observability stack:

1. **Incident responders** — the 3 AM page audience. They need fast triage: "is it us or them, where, how bad."
2. **Engineers debugging** — slower, deeper questions about *why* a behavior happened. Traces and events shine here.
3. **SREs / capacity planners** — long-horizon trends, saturation, headroom. Metrics and dashboards.
4. **Product / business** — does feature X correlate with user retention. Often shares the data plane but has different SLAs and access controls.
5. **Auditors and security** — logs that meet retention and immutability requirements.

A working stack serves all five with one ingestion path. Failing to acknowledge audience 4 and 5 is how you end up paying for three telemetry systems and a separate SIEM.

References: [Distributed Systems Observability — Cindy Sridharan](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/), [Observability Engineering — Majors, Fong-Jones, Miranda](https://www.oreilly.com/library/view/observability-engineering/9781492076438/), [Google SRE Workbook, Ch. 5](https://sre.google/workbook/monitoring/)

```quiz
Q: What's the operative distinction between monitoring and observability?
- [ ] Monitoring uses metrics; observability uses logs
- [x] Monitoring answers questions you predicted in advance; observability lets you ask new ones after the fact without redeploying
- [ ] Monitoring is real-time; observability is batch
- [ ] Observability is just monitoring with prettier dashboards
> Monitoring covers *known unknowns* — you pick what to measure and alert on thresholds you set ahead of time. Observability is about *unknown unknowns*: instrumenting richly enough that you can slice by a dimension you never anticipated (Android 14, EU-West, a specific flag) without shipping new code. The tools overlap, but the design goal — arbitrary questions in high cardinality, unpredicted — is what makes a system observable.

Q: Why must a metric label never be a user ID or request UUID?
- [ ] Labels can't hold strings that long
- [ ] It would violate GDPR
- [x] Each distinct label combination is a separate time series, so unbounded label values explode storage and query cost and can take down the whole stack
- [ ] User IDs change too often to be useful
> Cardinality — the number of distinct label combinations — is the central constraint. Every combination is its own time series in Prometheus, index entry in Loki, row in your TSDB, and cost grows at least linearly in active series. A UUID-shaped label is effectively infinite cardinality, the most common way to take down observability, alerting, and dashboards at once. High-cardinality dimensions belong on events/traces, where each row stands alone and you aggregate at query time.

Q: You want to slice incidents by a 10,000-value tenant dimension and also by free-form request context. Where does each belong?
- [ ] Both as metric labels — that's what labels are for
- [ ] Both on traces only
- [x] Bounded/sharded dimensions can sometimes be metric labels; truly high-cardinality, per-request context belongs on events/traces
- [ ] Neither — drop them to control cost
> The metrics-vs-events spectrum is the design question. Metrics are pre-aggregated time series, cheap but cardinality-bound, so a 10K-tenant label is borderline and needs sharding or care. Per-request, arbitrary-dimension context belongs on events/traces, which store each row independently and aggregate at query time — that's exactly the flexibility-for-storage-cost trade the whole field turns on.
```

---

## Phase 2: Metrics

### 2.1 The Prometheus Data Model

Prometheus is the default. Even if you use Datadog or New Relic, the data model has won, and the protocols look like Prometheus.

Every Prometheus metric is a **time series** identified by a name and a set of `label=value` pairs:

```
http_requests_total{method="GET", path="/api/v1/users", status="200", instance="api-7d8f", job="api"}
```

Two metrics with identical names but a single different label are different series. The series identity drives storage, indexing, and cardinality cost.

A series stores a list of `(timestamp, float64)` samples, scraped at the configured interval (default 15s).

Conventions enforced by the ecosystem:
- **Metric names are snake_case**: `http_requests_total`, not `httpRequestsTotal`.
- **Units in the name**: `_seconds`, `_bytes`, `_total`, `_ratio`. Never `_ms`, never `_kb`. Always base SI units; Grafana formats them. The reason: changing units later breaks every dashboard.
- **Counters end in `_total`**: `http_requests_total`, `errors_total`. Enforced by linters.
- **Reserve `__` prefix** for internal labels (`__name__`, `__address__`).

### 2.2 The Four Metric Types

| Type      | Semantics                                            | When to use                            |
|-----------|------------------------------------------------------|----------------------------------------|
| Counter   | Monotonically increasing total (may reset on restart)| Counts of events, bytes sent, errors   |
| Gauge     | Value that goes up and down                          | Current memory, queue depth, temperature |
| Histogram | Pre-bucketed distribution + count + sum              | Latency, request size                  |
| Summary   | Client-computed quantiles + count + sum              | Legacy; prefer histograms              |

**Counters** are the most common type and the most misused. You never use the raw counter value — you use `rate()` or `increase()` to compute *per-second* or *per-window* deltas. A counter that resets (process restart) is handled by `rate()` automatically. Don't store deltas yourself; store totals.

**Gauges** are observation snapshots. `node_memory_MemAvailable_bytes`, `kube_pod_status_phase`, `db_connections_in_use`. Use gauges sparingly; they hide history (you can't tell what happened between scrapes).

**Histograms** are the workhorse for distributions. A Prometheus classic histogram exposes:
- `metric_bucket{le="0.1"}` — count of samples ≤ 0.1
- `metric_bucket{le="0.5"}` — count of samples ≤ 0.5
- ...
- `metric_bucket{le="+Inf"}` — total count
- `metric_count` — total samples
- `metric_sum` — sum of all sample values

`histogram_quantile(0.99, rate(metric_bucket[5m]))` interpolates the 99th percentile from buckets. **Quantile accuracy depends entirely on your bucket choices**: if all your latency is between 50 and 100 ms and your buckets are `[0.005, 0.01, 0.025, 0.05, 0.1, 0.25]`, p99 lives in the `0.1` bucket and you'll always get `0.1` back. Pick buckets that bracket where your data lives.

**Native histograms** (Prometheus 2.40+, stable in 3.x) replace the fixed-bucket scheme with exponential buckets defined by a schema parameter, dramatically reducing series count and removing bucket-tuning. They're the future — when both client and server support them, switch.

**Summaries** compute quantiles client-side and emit them as separate series (`metric{quantile="0.99"}`). They cannot be aggregated across instances (you can't average a p99). Avoid them in new code.

References: [Metric types](https://prometheus.io/docs/concepts/metric_types/), [Histograms and summaries](https://prometheus.io/docs/practices/histograms/), [Native histograms design doc](https://prometheus.io/docs/specs/native_histograms/)

### 2.3 Exposition Format and Scraping

Prometheus is **pull-based**. Targets expose metrics over HTTP (typically `:port/metrics`) in a plain-text format:

```
# HELP http_requests_total Total HTTP requests.
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 12345
http_requests_total{method="GET",status="500"} 27

# HELP request_duration_seconds Request latency.
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.1"} 11000
request_duration_seconds_bucket{le="0.5"} 12200
request_duration_seconds_bucket{le="+Inf"} 12372
request_duration_seconds_count 12372
request_duration_seconds_sum 845.3
```

Prometheus scrapes each target on a fixed interval, stores samples in its TSDB, and exposes PromQL for querying. Pull has trade-offs:

| Pull (Prometheus default)             | Push (StatsD, OTLP, Pushgateway)       |
|---------------------------------------|----------------------------------------|
| Server-side service discovery         | Targets choose where to push           |
| Liveness check is free (failed scrape) | Need a separate health check           |
| Bad for ephemeral jobs                | Good for short-lived jobs (cron)       |
| Hard across NAT / firewalls           | Crosses NAT trivially                  |
| Easy to reason about cardinality      | Easy to firehose the server            |

Use **Pushgateway** for service-level batch jobs whose results outlive the process (e.g., a nightly backup completion gauge). Do not use Pushgateway as a general push endpoint — it conflates many job runs into one series and resets are awkward.

OpenTelemetry's metrics SDK supports both push (OTLP to a collector) and pull (Prometheus scrape endpoint). Most large stacks now send push-based OTLP through a collector that *exposes* a Prometheus endpoint, getting the best of both.

### 2.4 Exporters

You rarely instrument operating-system metrics yourself. An **exporter** is a small process that scrapes a system (kernel, database, queue, vendor API) and exposes a Prometheus-format endpoint. The ones to know:

| Exporter                | What it exposes                                          |
|-------------------------|----------------------------------------------------------|
| `node_exporter`         | Linux host: CPU, memory, disk, network, filesystem       |
| `windows_exporter`      | Windows equivalent                                       |
| `cAdvisor`              | Container metrics (cgroup-derived). Built into kubelet   |
| `kube-state-metrics`    | Kubernetes API object state (pod phase, deployment ready)|
| `blackbox_exporter`     | Probes endpoints (HTTP, TCP, DNS, ICMP) from outside     |
| `postgres_exporter`     | Postgres `pg_stat_*` views as metrics                    |
| `mysqld_exporter`       | MySQL equivalent                                         |
| `redis_exporter`        | Redis `INFO` and key statistics                          |
| `kafka_exporter`        | Kafka consumer lag, topic counts                         |
| `nginx-vts-exporter`    | Nginx upstream and zone metrics                          |
| `pushgateway`           | Push endpoint for batch jobs                             |
| `snmp_exporter`         | SNMP devices (switches, UPS)                             |

`node_exporter` is the most installed Go binary on Earth. Learn its metric names — `node_cpu_seconds_total`, `node_filesystem_avail_bytes`, `node_load1` — they appear in every dashboard you'll ever build.

References: [Exporters list](https://prometheus.io/docs/instrumenting/exporters/)

### 2.5 PromQL Essentials

PromQL is its own language. The shape that matters:

- **Instant vector** — a set of series, one sample each, at one timestamp. What you see in a query result.
- **Range vector** — a set of series, *many samples each*, over a time window. Selected with `[5m]`. You can't graph it directly; you reduce it with a function (`rate`, `avg_over_time`).
- **Scalar / string** — single values.

```promql
# Instant vector: current value
http_requests_total

# Range vector: last 5 min of samples
http_requests_total[5m]

# Per-second rate of a counter over 5 min (most important PromQL idiom)
rate(http_requests_total[5m])

# Same but average over a window
avg_over_time(node_load1[1h])

# Per-second rate, summed across all instances
sum(rate(http_requests_total[5m]))

# Aggregate while preserving status label
sum by (status) (rate(http_requests_total[5m]))

# Error rate (5xx as fraction of total)
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))

# Histogram p99 latency
histogram_quantile(
  0.99,
  sum by (le) (rate(request_duration_seconds_bucket[5m]))
)

# Top 3 noisiest endpoints by request rate
topk(3, sum by (path) (rate(http_requests_total[5m])))
```

The rules that catch people:
- **`rate()` requires a counter (monotonic).** Using it on a gauge is wrong; use `deriv()` or `delta()` for gauges.
- **Always rate *before* you aggregate** — `sum(rate(x[5m]))`, not `rate(sum(x)[5m])`. The latter is a syntax error; the former is what you want, because `sum` of counter resets behaves badly.
- **The range in `[5m]` must be ≥ 4× your scrape interval** for stable rates. 5m at 15s scrape is fine.
- **`irate()` uses only the last two samples** in a window — spikier, more responsive, but unstable for alerts. Use `rate()` for dashboards and alerts; `irate()` for poking at incidents.
- **`offset 1w`** compares to last week: `rate(x[5m]) / rate(x[5m] offset 1w)`.

Match operators:
- `=` exact, `!=` not equal, `=~` regex match, `!~` regex not match.
- `{job="api", status=~"5.."}` — common pattern.

Aggregation operators: `sum`, `avg`, `min`, `max`, `count`, `stddev`, `topk`, `bottomk`, `quantile`, `group`. All take `by (label, ...)` or `without (label, ...)`.

References: [PromQL basics](https://prometheus.io/docs/prometheus/latest/querying/basics/), [PromQL functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)

### 2.6 Recording Rules and Federation

**Recording rules** precompute expensive queries and store the result as a new time series. Every dashboard panel that runs the same heavy query is paying that cost on every refresh; a recording rule pays it once per evaluation interval.

```yaml
groups:
- name: api_slo
  interval: 30s
  rules:
  - record: job:http_request_errors:rate5m
    expr: sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
  - record: job:http_requests:rate5m
    expr: sum by (job) (rate(http_requests_total[5m]))
  - record: job:http_error_ratio:5m
    expr: job:http_request_errors:rate5m / job:http_requests:rate5m
```

Naming convention: `level:metric:operations` — `job:http_error_ratio:5m` says "aggregated to job level, error ratio metric, 5-minute window." Once internalized, this naming is invaluable for navigating big stacks.

**Federation** lets a higher-level Prometheus scrape *aggregates* from lower-level Prometheuses. The classic shape:

```
[per-cluster Prom] ──/federate──> [global Prom]
[per-cluster Prom] ──/federate──> [global Prom]
[per-cluster Prom] ──/federate──> [global Prom]
```

The global only pulls the recording-rule outputs, not every raw series. This keeps the global tractable and isolates failure domains. Federation is the poor person's long-term storage; the rich answer is `remote_write`.

### 2.7 Remote Write and Long-Term Storage

Prometheus's local TSDB is fine for ~15 days of data at modest series counts. For longer retention, HA, multi-tenant, or query across clusters, you push to a remote backend via the **`remote_write`** protocol — a streaming protobuf over HTTP.

The receivers:

| System              | Architecture                                  | Notes                                  |
|---------------------|-----------------------------------------------|----------------------------------------|
| Thanos              | Sidecar uploads TSDB blocks to S3-compatible  | Read path queries S3 + live blocks     |
| Cortex              | Microservices, multi-tenant remote_write      | Predecessor to Mimir                   |
| Mimir (Grafana)     | Fork of Cortex, simplified, scalable          | The current "right answer" for self-host |
| VictoriaMetrics     | Single-binary high-perf TSDB, remote_write    | Simpler ops, very fast, less ecosystem |
| Prometheus 2.x HA   | Pair of identical Proms behind dedup          | OK for small setups, doesn't scale     |
| Grafana Cloud Metrics | Hosted Mimir                                | The pay-someone-else answer            |

The choice points: **how much data are you keeping for how long**, **what's your QPS to the query layer**, and **how multi-tenant are you**. Mimir scales to billions of active series; Thanos is more flexible but operationally heavier; VictoriaMetrics is the easy single-binary path.

References: [Remote write spec](https://prometheus.io/docs/specs/remote_write_spec/), [Thanos](https://thanos.io/), [Mimir](https://grafana.com/oss/mimir/)

### 2.8 Cardinality Control

You will get a cardinality explosion. Plan for it.

Defenses:
- **Linting at instrumentation time** — code review for label values that could be unbounded (user IDs, full URLs, trace IDs). Use a static linter like `promlinter`.
- **Relabeling at scrape time** — drop or rewrite labels in the scrape config before ingestion:

  ```yaml
  metric_relabel_configs:
  - source_labels: [__name__]
    regex: "go_.*"
    action: drop
  - source_labels: [path]
    regex: "/users/[0-9]+"
    target_label: path
    replacement: "/users/:id"
  ```

- **Series limits per target/job** (`sample_limit`, `target_limit`) — scrape config caps that drop the whole scrape if exceeded. Better to lose one job's metrics than the entire Prometheus.
- **TSDB head limit** — Mimir / Cortex enforce `max_global_series_per_user`. Set it; alert on getting close.
- **Recording rules to pre-aggregate** the worst offenders, then drop the raw series via `metric_relabel_configs`.

Monitor your own observability stack:
- `prometheus_tsdb_head_series` — current active series count.
- `prometheus_tsdb_head_chunks` — sized for series × resolution.
- `scrape_samples_post_metric_relabeling` — per-target series count after relabeling.
- Top-cardinality metrics via the `/api/v1/status/tsdb` endpoint.

References: [Cardinality is key (Grafana blog)](https://grafana.com/blog/2022/02/15/avoid-prometheus-high-cardinality-issues-and-fix-them-when-they-happen/)

```quiz
Q: Why do you almost never query a counter's raw value directly, reaching for `rate()` instead?
- [ ] Raw counter values are stored compressed and unreadable
- [x] The raw total is meaningless on its own and resets on restart; `rate()` gives a per-second delta and handles resets automatically
- [ ] `rate()` is the only function allowed on counters by the linter
- [ ] Counters aren't stored, only their rates are
> A counter is a monotonically increasing total that resets to zero on process restart, so its absolute value tells you little and a naive subtraction across a restart would go negative. `rate()` computes the per-second increase over a window and transparently accounts for resets, which is why "rate of a counter" is the single most important PromQL idiom. You store totals and derive rates, never the other way around.

Q: Why must you write `sum(rate(x[5m]))` and not `rate(sum(x)[5m])`?
- [ ] `sum` is slower than `rate`
- [x] You must rate each counter series before aggregating, because summing across counter resets behaves badly (and the latter is a syntax error)
- [ ] `rate` can only take one series at a time
- [ ] Aggregation must always come first in PromQL
> `rate()` needs to see each individual counter series to detect and correct its resets. If you summed first, a single instance restarting would corrupt the aggregate, and syntactically `rate()` wants a range vector of raw series, not an aggregated instant vector. Rate-then-aggregate is the rule: it keeps reset handling correct per series and then combines the clean per-second rates.

Q: Your p99 latency query always returns exactly `0.1` even as latency clearly varies. What's the likely cause?
- [ ] `histogram_quantile` is broken on native histograms
- [ ] You forgot to `sum by (le)`
- [x] Your real latency exceeds your largest meaningful bucket, so the quantile interpolates into the `0.1` bucket and saturates there
- [ ] The scrape interval is too long
> Classic histogram quantiles are interpolated from the bucket boundaries, so accuracy depends entirely on bucket choice. If your latency lives between 50–100 ms but your buckets top out around `0.1`, p99 falls in that last bucket and you get `0.1` back every time — the histogram can't resolve detail it never bucketed. The fix is choosing buckets that bracket where your data actually lives (or moving to native histograms, which remove the tuning problem).
```

---

## Phase 3: Logs

### 3.1 Structured Logging

The single biggest lever in logging: emit **structured logs** (JSON or logfmt), not free-form strings.

Bad:

```
2026-05-20 14:30:01 INFO User 12345 placed order $59.99 for product widget-7
```

Good:

```json
{"ts":"2026-05-20T14:30:01Z","level":"info","msg":"order placed","user_id":"12345","order_total":59.99,"product":"widget-7","request_id":"abc","trace_id":"def"}
```

Why it matters: every log aggregator (Loki, Splunk, Elastic, Datadog) can index and aggregate JSON fields. Free-form strings force grep-and-pray. The cost of structuring at write time is one library; the value is queryability forever.

Conventions:
- **One event per line** (JSON Lines). Never multi-line logs that span records; stack traces go in a single `stack` field with `\n`.
- **Timestamp in RFC 3339** with millisecond resolution and UTC: `2026-05-20T14:30:01.123Z`.
- **Stable field names across services**: `request_id`, `trace_id`, `span_id`, `user_id`, `tenant_id`. Wire them once and never rename.
- **Levels are an enum**: `trace`, `debug`, `info`, `warn`, `error`, `fatal`. Don't invent `notice` or `critical`.
- **Reserved fields**: `ts`, `level`, `msg`, `service`, `env`. Pin them via your logger config; let everything else be free.

The libraries (just pick the idiomatic one for your language):

| Language | Library                                                |
|----------|--------------------------------------------------------|
| Go       | `log/slog` (stdlib, Go 1.21+), `zap`, `zerolog`        |
| Java     | Logback + `logstash-logback-encoder` or Log4j2 JSON    |
| Python   | `structlog`, stdlib `logging` with `JSONFormatter`     |
| Node     | `pino`                                                 |
| Ruby     | `semantic_logger`, `lograge`                           |
| Rust     | `tracing` with `tracing-subscriber` JSON formatter     |

### 3.2 Log Levels, Honestly

Most projects use 5–6 levels and almost no one uses them consistently. A working definition:

- **`error`** — something happened that needs human attention. The default request for help. Pages should be derived from these, gated on rate.
- **`warn`** — something is suspect but the request continued. Useful for detecting drift, not for pages.
- **`info`** — significant lifecycle events: process start, config load, request completed. One per request is fine; one per inner loop iteration is not.
- **`debug`** — verbose, opt-in, the developer's friend. Off in production by default; toggleable per-service or per-trace.
- **`trace`** — even more verbose. Almost never on in production.

The discipline: **`error` is for pages, `info` is the story of your service, `debug` is for hard problems**. If you can't articulate why a log is `info` vs `debug`, it's probably `debug`.

Common anti-patterns:
- Logging the same condition at multiple levels in different code paths.
- Using `error` for "expected" failures like 4xx responses. They aren't your service's errors; they're the caller's.
- Logging every iteration of a loop. Sample, summarize, or move it to a metric.

### 3.3 Sampling, Retention, Cost

Logs are the most expensive pillar by storage volume. A busy service can emit 1+ KB per request × 10K req/s × seconds-in-a-day = 1 TB/day per service. Multiply by services and retention period and the bill arrives.

Controls:

- **Sampling** — drop a fraction of low-value logs at the source. `info` logs from healthy requests can be sampled 1:100; `error` logs never sampled.
- **Aggressive retention tiers** — hot (queryable), warm (queryable, slow), cold (S3, restorable). The classic tiering: 7 days hot, 30 days warm, 90+ days cold. Compliance often dictates the floor.
- **Drop noise at the collector** — most logs from health-check endpoints, kubelet probes, sidecar liveness should never reach the aggregator. Filter at Fluent Bit / Vector / OTel Collector.
- **Field cardinality** — same problem as metrics, different surface. Logging a full request body explodes index size in Elasticsearch. Either don't index that field, or store it in object storage and log a reference.
- **Compress on the wire** — Loki uses gzip/snappy on chunks by default; Elasticsearch does best-effort. Without compression your bandwidth bill ruins you.

Cost-control rule of thumb: a typical production log volume of 100–500 GB/day per major service is normal; 5+ TB/day from a single service is a smell. Audit it.

### 3.4 Aggregation Pipelines

The shape of every modern logging pipeline:

```
[app] → [agent] → [aggregator/buffer] → [store] → [UI]
```

The pieces:

| Stage          | Examples                                              |
|----------------|-------------------------------------------------------|
| Agent          | Fluent Bit, Vector, OpenTelemetry Collector, Filebeat |
| Aggregator     | Fluentd, Vector, Kafka, OTel Collector                |
| Store          | Loki, Elasticsearch, Splunk, Datadog, ClickHouse      |
| UI             | Grafana (Loki), Kibana (ES), vendor-specific          |

**Fluent Bit** vs. **Vector** vs. **OpenTelemetry Collector**:
- *Fluent Bit*: C, tiny memory footprint, the default sidecar/daemonset. Good plugin set, decent transforms.
- *Vector*: Rust, faster and more powerful transforms (VRL language), more flexibility. Becoming the new default for serious pipelines.
- *OTel Collector*: Go, the unified telemetry router (metrics + logs + traces in one binary). Lower-level transforms than Vector but the right answer if you're already in OTel.

The aggregator's job: buffer, transform, route. Kafka in front of an aggregator gives you durable, replayable buffering across restarts — worth it once your volume exceeds a single aggregator instance.

### 3.5 Loki vs. Elastic vs. the Vendors

The two open-source camps:

**Loki** — Grafana's "logs like Prometheus." Indexes only labels (job, service, level), not log content. Content is stored as compressed chunks in object storage (S3, GCS). Queries are LogQL, which looks like PromQL plus pattern matching:

```logql
{service="api", level="error"} |= "timeout" | json | latency > 1
```

- Strengths: dramatically cheap (you index hundreds of bytes of labels, not megabytes of content), scales by sharding by label, integrates trivially with Grafana.
- Weaknesses: full-text search is a scan over chunks — fast enough at small label cardinality, slow at huge. Wrong tool for security/forensics use cases that need true full-text.

**Elasticsearch / OpenSearch** — Inverse trade-off. Indexes everything by default. Queries are blazing fast over any field; storage cost and operational complexity are an order of magnitude higher.

- Strengths: rich queries, geo and analytics, mature ecosystem (Kibana, ELK stack).
- Weaknesses: index management is a job. Heap pressure, shard balancing, snapshot/restore are full-time concerns at scale.

The vendor offerings (**Datadog Logs**, **Splunk**, **New Relic Logs**, **Sumo Logic**) all index aggressively and charge per ingest GB. They are easy to set up and shockingly expensive at scale. Cost models vary — some charge ingest, some indexed volume, some retention separately. Read the contract.

**ClickHouse**-backed log stores (Signoz, Highlight, OpenObserve, vendor offerings like Better Stack) are an interesting middle ground: columnar storage, very fast aggregations, low storage cost.

Picking:
- *Default for K8s + Grafana shop*: Loki. Cheap, integrated, sufficient for incident logs.
- *Security or forensics needs full-text everything*: Elastic/OpenSearch (or Splunk if you have the budget).
- *Vendor-everything, want it to just work*: Datadog, but budget accordingly.

### 3.6 Logs vs. Metrics — Which Carries What

A frequent question: "should this be a log or a metric?"

| Question                                  | Log | Metric |
|-------------------------------------------|-----|--------|
| "How many of X happened in window W?"     | bad | great  |
| "What did request R do?"                  | great | bad  |
| "Show me the distribution of latency"     | bad | great  |
| "Find requests with field F = V"          | great | bad  |
| "Alert me when X exceeds threshold"       | bad | great  |
| "Why did request R take 3.4 seconds?"     | great | bad  |

The pattern: **metrics for *how many*, logs (and traces) for *which one***. A `request_duration_seconds` histogram tells you p99 is 800ms; a log/trace tells you *that one request* spent 700ms in DB.

The dark side: many teams use logs as metrics by counting `grep`s of log lines. This is fragile and expensive. If you're counting, emit a metric.

### 3.7 Common Pitfalls

- **Printf debugging in production.** A `log.info("here1")` that survived code review. Add real telemetry and remove the temp logs before merging.
- **PII in logs.** Customer emails, tokens, full request bodies. Once they're in your log store, they're in backups, in vendor systems, and possibly screenshotted into Slack. Redact at the source.
- **Logging exceptions you also rethrow.** Either log + handle, or rethrow. Logging-and-rethrowing produces duplicate entries at every layer.
- **Logging in tight loops.** A loop that logs each iteration at 100K/s overwhelms the agent. Sample or summarize.
- **Re-implementing structured logging poorly.** Use the library, not `printf("k=%s v=%s", k, v)`.

References: [OpenTelemetry Logs spec](https://opentelemetry.io/docs/specs/otel/logs/), [Loki Design](https://grafana.com/docs/loki/latest/get-started/overview/), [The 12-Factor App: Logs](https://12factor.net/logs)

---

## Phase 4: Distributed Tracing

### 4.1 Spans, Traces, Context

A **span** is a single operation: an HTTP handler, a DB query, a function call, a queue write. It has:
- A start time and duration.
- A name (the operation).
- A trace ID (shared with all spans in the same request).
- A span ID (unique to this span).
- A parent span ID (linking it to the span that triggered it).
- Attributes (key-value pairs).
- Events (timestamped logs scoped to this span).
- A status (ok, error).

A **trace** is the DAG of spans for a single end-to-end request, identified by the trace ID.

Visually:

```
trace_id=abc
├── span: HTTP POST /checkout         (api-gateway)   850ms
│   ├── span: validate cart           (api-gateway)    30ms
│   ├── span: GET /inventory          (inventory-svc) 200ms
│   │   └── span: SELECT stock        (postgres)       80ms
│   ├── span: POST /payment           (payment-svc)   500ms
│   │   └── span: HTTPS api.stripe    (stripe)        420ms
│   └── span: enqueue order_created   (kafka)          15ms
```

The trace shows the *causal structure* of a request across processes. Metrics tell you p99 latency is 850ms; a trace tells you 420ms of it was Stripe.

### 4.2 Context Propagation

The hard part of tracing is **propagating the trace and parent span IDs across process boundaries** so all the spans link up.

Standards:
- **W3C Trace Context** ([spec](https://www.w3.org/TR/trace-context/)) — the now-universal HTTP header standard. Two headers:
  - `traceparent: 00-<trace-id>-<parent-span-id>-<flags>` — e.g. `00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01`. The `01` flag is the "sampled" bit.
  - `tracestate` — vendor-specific extensions, an ordered list of `key=value` pairs.
- **W3C Baggage** ([spec](https://www.w3.org/TR/baggage/)) — `baggage: userId=alice,session=xyz` — application-level key-value that propagates with the trace but isn't part of the trace itself.
- **B3** (Zipkin's legacy headers) — `X-B3-TraceId`, `X-B3-SpanId`, `X-B3-Sampled`. Still seen in older systems. OTel SDKs read it for interop.
- **Jaeger** legacy: `uber-trace-id`. Same situation.

Wire-protocol propagation matters; in-process propagation matters equally. The instrumentation libraries store the current span in a thread-local / async-local / Go context, so when your handler calls a function deep down the stack, that function can attach to the correct parent without explicit passing. The two pieces — wire and in-process — must agree.

References: [W3C Trace Context](https://www.w3.org/TR/trace-context/), [OTel Context propagation](https://opentelemetry.io/docs/specs/otel/context/)

### 4.3 Sampling: Head vs. Tail

Tracing every single request is wasteful and expensive. You sample. The question is *when* to decide.

**Head sampling** — the decision is made at the start of the trace, by the first service. If sampled, every span downstream is recorded; if not, none are. The sampling bit is propagated in `traceparent`.

- Pros: cheap, simple. No coordination across services.
- Cons: you can't "save" interesting-after-the-fact traces. If you sample 1% and the 99% you didn't sample contains an outlier, it's gone.

Common head policies:
- Fixed-rate: 1% of traces.
- Rate-limited: max N traces/sec per service.
- Parent-based: respect the upstream sampling decision (the default for downstream services).

**Tail sampling** — every span is collected and buffered. The decision (keep or drop) happens *after the trace completes*, based on the trace's properties (had an error, was slow, came from a specific tenant). Implemented in the OTel Collector via the `tail_sampling` processor.

- Pros: you get the interesting traces (errors, p99 latency, specific routes).
- Cons: expensive — every span must be buffered for the trace's duration. Requires a "collector tier" that groups all spans of a trace together (consistent hashing on trace ID).

A typical hybrid: head-sample at 5–10%, and on top of that, tail-sample 100% of traces with errors or above a latency threshold. Pay for the few interesting things, drop the rest.

References: [OTel Tail sampling processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor)

### 4.4 When Traces Are the Right Answer

Traces shine for:
- **Diagnosing latency**: which span ate the budget?
- **Diagnosing partial failures**: which downstream returned the error?
- **Understanding fan-out**: how many DB calls did this endpoint make?
- **Finding the n+1**: 47 sequential `SELECT * FROM ...` spans is unambiguous.

Traces are *not* the right answer for:
- **"How often does X happen?"** — that's a metric.
- **"What did the function compute?"** — that's an attribute or log.
- **Long-running processes** that span hours/days. Trace storage isn't designed for it; emit metrics and discrete spans for milestones.

### 4.5 Trace Backends

| Backend          | Notes                                                 |
|------------------|-------------------------------------------------------|
| Jaeger           | Open source, the original; Cassandra/ES/Badger        |
| Zipkin           | Older, Twitter origin; functional but mostly legacy   |
| Tempo (Grafana)  | Object-store-backed (S3/GCS), no full index, cheap    |
| Honeycomb        | Hosted, event-store-based; pivots to high-cardinality |
| Datadog APM      | Trace + metrics + logs in one bill                    |
| New Relic        | Same                                                  |
| Lightstep        | Acquired by ServiceNow; satellite-based head/tail mix |

Like Loki for logs, **Tempo** is "traces as Prometheus" — minimal indexing, trace-id-only lookup, store everything in object storage. The trade-off: you can find traces by ID (fast), but querying "all traces where `http.status_code=500`" requires the metrics layer (TraceQL helps but is still constrained).

**Honeycomb** takes the opposite stance: a wide-event store. Every span is a row with arbitrary high-cardinality dimensions; you slice and dice at query time. Tempo + metrics + logs vs. Honeycomb's "one store, query everything" is the central design choice in tracing infrastructure.

References: [Tempo design](https://grafana.com/docs/tempo/latest/operations/architecture/), [Honeycomb tracing](https://docs.honeycomb.io/get-started/basics/tracing/)

```quiz
Q: Metrics show a checkout endpoint's p99 is 850ms but can't tell you where the time went. What does a trace add?
- [ ] It lowers the latency by caching the slow call
- [x] It shows the causal span breakdown across services, so you can see (e.g.) 420ms was the Stripe call
- [ ] It counts how many checkouts happened
- [ ] It replaces the need for metrics
> A trace is the DAG of spans for one end-to-end request, each span timed and linked by parent. That structure turns "850ms somewhere" into "420ms in the Stripe call, 80ms in the stock SELECT" — the causal, per-request view metrics fundamentally can't give. Metrics tell you *how many* and *how slow in aggregate*; a trace tells you *which one* and *where the time went*.

Q: What is the fundamental trade-off between head sampling and tail sampling?
- [ ] Head sampling is more accurate; tail sampling is approximate
- [x] Head decides cheaply at the start but can't keep an after-the-fact interesting trace; tail buffers every span to keep errors/slow ones but is expensive
- [ ] Head sampling requires the OTel Collector; tail sampling doesn't
- [ ] They produce identical results, just at different times
> Head sampling makes the keep/drop decision at the trace's start and propagates it — cheap and coordination-free, but if the 99% you dropped contained the outlier, it's gone. Tail sampling collects and buffers every span and decides after the trace completes based on its properties (had an error, was slow), so you capture exactly the interesting traces — at the cost of buffering everything and a collector tier that groups all spans of a trace. The common hybrid head-samples a baseline and tail-samples 100% of errors/slow traces.

Q: Why does cross-process context propagation (e.g. W3C `traceparent`) have to work for tracing to function at all?
- [ ] It encrypts the spans in transit
- [x] Without propagating the trace ID and parent span ID across service boundaries, downstream spans can't link into the same trace
- [ ] It's only needed for tail sampling
- [ ] It compresses span attributes
> A trace is held together by a shared trace ID and the parent-span links between spans. When a request crosses a process boundary, those IDs must travel with it — that's what the `traceparent` header carries — or the downstream service starts an unrelated trace and the causal graph fragments. In-process propagation (thread/async-local context) and wire propagation must both agree for the spans to assemble into one trace.
```

---

## Phase 5: OpenTelemetry

### 5.1 What OpenTelemetry Is, and Why It Won

**OpenTelemetry** (OTel) is a CNCF project providing:
- **A specification** for what telemetry data looks like (semantic conventions, data model).
- **SDKs** in every major language for producing it.
- **A protocol** (OTLP, OpenTelemetry Protocol — protobuf over gRPC or HTTP).
- **A collector** — a configurable agent/gateway that ingests OTLP and ships to any backend.

It emerged in 2019 from the merger of OpenTracing (API spec) and OpenCensus (Google's library). It's now the de facto standard. Every major vendor and open-source backend accepts OTLP. Why it won:

1. **Vendor neutrality**: instrumenting with OTel decouples your code from your backend. Swap Datadog for Tempo without touching application code.
2. **Three pillars in one library**: metrics, logs, and traces share context, correlation IDs, and resource attributes.
3. **Semantic conventions**: standardized attribute names (`http.method`, `db.system`, `messaging.system`) so dashboards and tools work across stacks.
4. **CNCF + every major cloud**: AWS, GCP, Azure, Datadog, Splunk, Dynatrace, Honeycomb all back it.

### 5.2 The SDK Architecture

The pieces in an SDK:

- **API** — the public interface code uses. `Tracer.startSpan()`, `Meter.counter()`, `Logger.log()`.
- **SDK** — the implementation. Configures samplers, processors, exporters.
- **Resources** — attributes describing the producer: `service.name`, `service.version`, `deployment.environment`, `k8s.pod.name`. Set once, attached to every signal.
- **Context propagators** — read/write trace headers (W3C, B3, baggage).
- **Processors** — pipeline stages: batch processor, span processor.
- **Exporters** — emit OTLP, Jaeger, Zipkin, Prometheus, console, etc.

A typical Go bootstrap:

```go
import (
  "go.opentelemetry.io/otel"
  "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
  "go.opentelemetry.io/otel/sdk/resource"
  sdktrace "go.opentelemetry.io/otel/sdk/trace"
  semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

exp, _ := otlptracegrpc.New(ctx)
tp := sdktrace.NewTracerProvider(
  sdktrace.WithBatcher(exp),
  sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1))),
  sdktrace.WithResource(resource.NewWithAttributes(
    semconv.SchemaURL,
    semconv.ServiceName("api"),
    semconv.ServiceVersion("v1.2.3"),
    semconv.DeploymentEnvironment("prod"),
  )),
)
otel.SetTracerProvider(tp)
```

### 5.3 Auto vs. Manual Instrumentation

**Auto-instrumentation** uses runtime hooks (Java's `-javaagent`, Python's `opentelemetry-instrument`, Node's `--require`) or monkey-patching to wrap popular libraries (HTTP clients, web frameworks, DB drivers) without code changes.

- Pros: drop-in coverage. You get HTTP/gRPC/DB spans for free.
- Cons: not portable across languages, sometimes overhead, sometimes wrong span names. Misses business semantics ("which checkout flow ran").

**Manual instrumentation** is application code calling the OTel API. Required for business spans, custom attributes, and any signal the auto-instrumentation doesn't generate.

The right answer is *both*. Start with auto-instrumentation everywhere to get baseline coverage in days. Layer manual spans on the critical business paths. Add high-cardinality attributes (tenant, plan tier, feature flag) on those spans — they are the dimensions you'll slice by in incidents.

References: [OTel auto-instrumentation](https://opentelemetry.io/docs/concepts/instrumentation/automatic/), [OTel semantic conventions](https://opentelemetry.io/docs/specs/semconv/)

### 5.4 The OpenTelemetry Collector

The Collector is a standalone binary that receives, processes, and exports telemetry. It has three pipeline component types:

- **Receivers** — `otlp`, `prometheus`, `kafka`, `filelog`, `hostmetrics`, vendor-specific.
- **Processors** — `batch`, `memory_limiter`, `resource`, `attributes`, `tail_sampling`, `transform`, `redaction`, `k8sattributes`.
- **Exporters** — `otlphttp`, `prometheusremotewrite`, `loki`, `tempo`, `datadog`, `splunkhec`, `kafka`, dozens more.

Pipelines are wired together in YAML:

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  batch: { timeout: 5s, send_batch_size: 1024 }
  memory_limiter: { check_interval: 1s, limit_mib: 1500 }
  attributes:
    actions:
    - key: env
      value: prod
      action: upsert
  tail_sampling:
    decision_wait: 10s
    policies:
    - name: errors
      type: status_code
      status_code: { status_codes: [ERROR] }
    - name: slow
      type: latency
      latency: { threshold_ms: 1000 }
    - name: random-5pct
      type: probabilistic
      probabilistic: { sampling_percentage: 5 }

exporters:
  otlphttp/tempo:
    endpoint: http://tempo:4318
  prometheusremotewrite:
    endpoint: http://mimir:9009/api/v1/push
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers:  [otlp]
      processors: [memory_limiter, tail_sampling, batch]
      exporters:  [otlphttp/tempo]
    metrics:
      receivers:  [otlp]
      processors: [memory_limiter, batch]
      exporters:  [prometheusremotewrite]
    logs:
      receivers:  [otlp]
      processors: [memory_limiter, attributes, batch]
      exporters:  [loki]
```

Deployment patterns:
- **Agent-as-sidecar / daemonset** — one collector per host or pod, lightweight, batches and ships.
- **Gateway tier** — a cluster of collectors behind a load balancer, doing tail sampling and routing. Required for tail-sampling to see whole traces.
- **Both** — agent for resource attribution (host, pod labels) → gateway for global processing.

The Collector is a more general routing layer than Fluent Bit or Vector — it speaks OTLP natively and is the unification point for the three pillars.

References: [OTel Collector docs](https://opentelemetry.io/docs/collector/), [Collector configuration](https://opentelemetry.io/docs/collector/configuration/)

### 5.5 OTLP

OTLP is the wire format. Protobuf, transported over gRPC (default, faster) or HTTP/protobuf (firewall-friendly) or HTTP/JSON (debuggable).

```
Application → OTLP/gRPC → Collector → OTLP/gRPC → Collector → backends
```

Backends accept OTLP directly now: Tempo, Loki (logs), Mimir (metrics, via Prometheus remote_write or OTLP), Honeycomb, Datadog (via vendor exporter), etc. The collector is often optional — you can ship OTLP from app to backend — but the collector earns its keep for batching, sampling, redaction, and resource enrichment.

References: [OTLP spec](https://github.com/open-telemetry/opentelemetry-proto)

```quiz
Q: What does instrumenting with OpenTelemetry primarily decouple?
- [ ] Your metrics from your logs
- [x] Your application code from your observability backend — you can swap Datadog for Tempo without touching instrumentation
- [ ] Your services from each other
- [ ] Your traces from their sampling decisions
> OTel's central value is vendor neutrality: the API, SDK, OTLP protocol, and semantic conventions standardize how telemetry is produced and shipped, so the backend becomes a configuration choice rather than something baked into your code. Add in shared context across metrics/logs/traces and standardized attribute names, and you get tooling that works across stacks — which is why every major vendor accepts OTLP.

Q: What's the recommended balance between auto- and manual instrumentation?
- [ ] Manual only — auto-instrumentation is unreliable
- [ ] Auto only — manual spans are redundant
- [x] Both — auto for baseline HTTP/DB/gRPC coverage in days, manual for business spans and high-cardinality attributes you'll slice by
- [ ] Neither — rely on the Collector to generate spans
> Auto-instrumentation wraps popular libraries with no code changes, giving you broad coverage fast, but it can't know your business semantics ("which checkout flow") or attach the tenant/plan/flag dimensions you'll actually pivot on during an incident. Manual spans add exactly those. Start with auto everywhere, then layer manual instrumentation on the critical paths — the dimensions you add there are what make the system observable, not just monitored.

Q: Why is a gateway tier of Collectors (not just per-host agents) required for tail sampling?
- [ ] Gateways have more CPU
- [x] Tail sampling must see all spans of a trace together to decide, so spans for one trace must be routed to the same collector
- [ ] Agents can't export OTLP
- [ ] Gateways encrypt the traces
> The tail-sampling decision depends on properties of the *complete* trace (did any span error, was it slow), so every span belonging to a trace has to land on the same collector instance — typically via consistent hashing on trace ID at a gateway tier. A per-host agent only sees its own host's spans and can't make that whole-trace decision, which is why the agent-plus-gateway topology exists: agents attribute and batch, the gateway groups and samples.
```

---

## Phase 6: Events and Profiling

The pillars debate sometimes adds two more: **events** (wide structured records of work units) and **profiles** (CPU/memory/lock samples over time).

### 6.1 Events as a Pillar

A wide structured **event** is one row per unit of work (request, job execution, scheduled task) with arbitrary key-value dimensions. The Honeycomb pitch is: events subsume the other pillars.

- Aggregate events over time → metrics.
- Each event is a structured log.
- A causally-linked sequence of events is a trace.

In practice, events show up as:
- Spans in OTel (a span *is* an event with timing and parent linkage).
- Wide JSON records in Honeycomb, Snowplow, custom event pipelines.
- Audit logs and security-event streams.

When events shine: any analytical question requiring multiple high-cardinality dimensions ("how many failed checkouts last hour, by country, by plan tier, by browser, when feature X was on"). Try that on Prometheus and you'll run out of cardinality. Try it on Honeycomb and it's one query.

### 6.2 Continuous Profiling

A **profile** is a sampled view of where a process is spending time (CPU profile), allocating (heap profile), blocking (goroutine/lock profile). Historically, profiling was on-demand: SSH in, run `pprof`, grab a 30-second sample. **Continuous profiling** runs constantly, low overhead, in production — building a queryable history.

The tools:

| Tool             | Approach                                                |
|------------------|---------------------------------------------------------|
| Pyroscope        | Multi-language continuous profiler, now under Grafana   |
| Parca            | eBPF-based, language-agnostic system profiler           |
| Grafana Phlare   | Continuous profiles, integrated with Grafana stack      |
| Polar Signals    | Hosted Parca, eBPF-driven                               |
| Datadog Profiler | Built into Datadog APM agents                           |
| Google Cloud Profiler | The original, for GCP workloads                    |

The signal: **flame graphs** showing where wall-clock time went. They diagnose problems metrics can't see — a hot function consuming 30% of CPU is invisible to `request_duration_seconds` if it's amortized across many requests.

eBPF profilers (Parca, Polar Signals) work without code instrumentation by sampling the kernel's perf events and unwinding stacks. Powerful for polyglot environments where instrumenting every language is impractical.

### 6.3 When Each Pillar Carries the Most Signal

| Question                                            | Best pillar |
|-----------------------------------------------------|-------------|
| "Is the service up?"                                | Metrics     |
| "What's our SLO compliance?"                        | Metrics     |
| "Why did this specific request fail?"               | Traces      |
| "What did the system print at 03:42 UTC?"           | Logs        |
| "Where is the CPU going right now?"                 | Profiles    |
| "Are users in country X more likely to churn?"      | Events      |
| "Did we deploy a regression at 14:00?"              | Metrics + traces |
| "Why does the heap keep growing?"                   | Profiles    |

References: [Pyroscope docs](https://grafana.com/docs/pyroscope/), [Parca / eBPF profiling](https://www.parca.dev/), [Brendan Gregg on flame graphs](https://www.brendangregg.com/flamegraphs.html)

---

## Phase 7: SLIs, SLOs, SLAs, and Error Budgets

The Google SRE Workbook formalized this vocabulary and it's now the industry standard. Internalize the definitions; vague usage causes endless org confusion.

### 7.1 The Definitions

- **SLI** (Service Level Indicator) — a *measured* number expressing reliability. "Fraction of requests served under 250ms over the last 5 minutes." It's a query, often a ratio.
- **SLO** (Service Level Objective) — a *target* for the SLI over a window. "99.9% of requests in 30 days served under 250ms." Internal-facing.
- **SLA** (Service Level Agreement) — a *contractual* commitment, usually with money attached. "If less than 99.5% of requests over a month are served, customer gets a 10% credit." External-facing. Almost always weaker than the internal SLO (you give yourself headroom).

Most engineers say "SLA" when they mean "SLO." Stop doing this. SLAs involve lawyers; SLOs involve oncall.

### 7.2 The Right SLIs

An SLI must be a *ratio* (good events / total events). Examples:

| Domain                   | Good / Valid SLI                                          |
|--------------------------|-----------------------------------------------------------|
| HTTP service             | `(requests with status < 500) / (all requests)`           |
| Latency                  | `(requests under 200ms) / (all requests)`                 |
| Pipeline freshness       | `(partitions on time) / (expected partitions)`            |
| Async job system         | `(jobs completed within 5 min) / (jobs enqueued)`         |
| Data pipeline (see [DATA_ENGINEERING_STUDY_GUIDE.md](DATA_ENGINEERING_STUDY_GUIDE.md)) | `(tables fresh by 9 AM) / (tables expected)` |

The wrong SLIs:
- **Mean latency** — averages hide outliers. A service with 99% fast and 1% catastrophic looks fine in the mean.
- **Raw counts** ("we want < 100 errors per day"). Doesn't scale with traffic.
- **CPU usage** — that's a resource, not a user-perceived signal. SLIs measure what users feel.

### 7.3 Picking the Number

The 9s ladder:

| SLO     | Downtime / 30 days  | Downtime / year  |
|---------|---------------------|------------------|
| 99%     | 7h 12m              | 87h 36m          |
| 99.5%   | 3h 36m              | 43h 48m          |
| 99.9%   | 43m 12s             | 8h 45m           |
| 99.95%  | 21m 36s             | 4h 23m           |
| 99.99%  | 4m 19s              | 52m 35s          |
| 99.999% | 25.9s               | 5m 15s           |

**You almost never want 99.999%.** Five nines is multiple data centers, redundant networks, change-control overhead, and an oncall culture that costs more than the business it serves. Three nines (99.9%) is the typical SaaS default; four (99.99%) is for systems that meaningfully break the world when down.

Calibrate against:
- **Customer expectations** — what do users actually tolerate?
- **Dependency floor** — if you depend on a 99.9% SLO upstream, you cannot have a higher SLO than them (excluding retries and caching).
- **Cost of meeting it** — every extra nine roughly 3–10× the engineering effort.

### 7.4 Error Budgets

If your SLO is 99.9% over 30 days, your **error budget** is the remaining 0.1% — 43m 12s of failure you're "allowed." Burning it is normal; over-burning it is the signal.

The cultural function of error budgets: they convert "is the system reliable?" into a number with a sign. When the budget is empty, you slow feature work and pay down reliability debt. When it's full, you can ship faster and take more risk.

Mathematically:

```
budget_remaining_fraction = 1 - (1 - SLI) / (1 - SLO)
                          = 1 - error_rate / allowed_error_rate
```

If `SLO = 99.9%` (allowed error rate `0.001`) and the observed error rate over the window is `0.0005`, you've consumed 50% of the budget.

### 7.5 Multi-Window Burn-Rate Alerts

Naïve approach: alert when "error rate > 0.1% over 5 minutes." Too noisy at low traffic, too slow at high.

The Google SRE Workbook ([Ch. 5, "Alerting on SLOs"](https://sre.google/workbook/alerting-on-slos/)) formalizes **burn-rate** alerts. The **burn rate** at any instant is `current_error_rate / SLO_error_rate`. A burn rate of 1 means you're consuming budget exactly at the rate that empties it in 30 days; a burn rate of 14.4 means you'd burn the entire budget in 30 days / 14.4 ≈ 2 days.

The recommended **multi-window, multi-burn-rate** pattern uses two windows simultaneously for each alert level:

| Severity | Long window | Short window | Burn rate | Catches                                       |
|----------|-------------|--------------|-----------|-----------------------------------------------|
| Page     | 1h          | 5m           | 14.4×     | Fast burns; ~2% budget consumed before paging |
| Page     | 6h          | 30m          | 6×        | Slower burns; ~5% budget consumed             |
| Ticket   | 24h         | 2h           | 3×        | Long-term drift                               |
| Ticket   | 72h         | 6h           | 1×        | Slow erosion                                  |

The **two windows** part matters: both must be in violation for the alert to fire. The long window confirms the trend; the short window confirms it's ongoing (auto-resolves quickly when the incident ends).

Concrete PromQL is in Phase 13.

References: [SRE Workbook, Ch. 5](https://sre.google/workbook/alerting-on-slos/), [How to SLO — Squadcast](https://www.squadcast.com/blog/how-to-slo), [Alex Ewerlöf SLO templates](https://github.com/grafana/slo-libraries)

### 7.6 SLOs Beyond Latency

SLOs aren't just for online services. Examples from other domains (see also [DATA_ENGINEERING_STUDY_GUIDE.md](DATA_ENGINEERING_STUDY_GUIDE.md) and [NETWORKING_FUNDAMENTALS.md](NETWORKING_FUNDAMENTALS.md)):

- **Data freshness SLO**: 99% of daily mart tables ready by 9 AM in 30 days.
- **Job completion SLO**: 99.5% of async jobs complete within 5 minutes of enqueue.
- **Build SLO**: 95% of CI builds complete in under 15 minutes.
- **Network packet loss SLO**: 99.99% of inter-AZ packets delivered.

Define the SLI, measure it, set a target. The framework is the same.

```quiz
Q: Why insist on the SLI/SLO/SLA distinction instead of using "SLA" for everything?
- [ ] SLAs are measured more precisely than SLOs
- [x] An SLI is the measured number, an SLO is your internal target, an SLA is a contractual commitment with money attached — they involve different stakeholders and consequences
- [ ] They're the same thing at different companies
- [ ] SLOs are external and SLAs are internal
> An SLI is the indicator (a measured ratio like "fraction of requests under 250ms"), an SLO is the internal objective over a window, and an SLA is the legal contract — usually weaker than the SLO so you keep headroom. Conflating them muddies who owns what: SLAs involve lawyers and credits, SLOs drive oncall and release decisions. The vague "SLA for everything" habit causes real org confusion.

Q: What is the cultural purpose of an error budget?
- [ ] To punish teams that cause incidents
- [x] To convert "is it reliable?" into a signed number that governs how fast you ship — full budget means take more risk, empty means pay down reliability
- [ ] To guarantee zero downtime
- [ ] To set the SLA credit amount
> The error budget is the allowed unreliability — for a 99.9% SLO, the 0.1% (about 43 minutes/30 days) you may burn. Its function is decision-making: when the budget is healthy you can ship features and take risks; when it's exhausted you slow down and invest in reliability. It turns an emotional argument about reliability into a quantitative, blameless lever.

Q: Why does the multi-window burn-rate alert require *both* a long and a short window to be in violation?
- [ ] To reduce Prometheus storage cost
- [x] The long window confirms the trend is real; the short window confirms it's still happening, so the alert auto-resolves quickly when the incident ends
- [ ] Short windows are more accurate than long ones
- [ ] It's required by the W3C spec
> A single window is either too noisy (short) or too slow (long). Requiring both means the long window establishes that you're genuinely burning budget fast enough to matter, while the short window ensures the burn is ongoing right now — so the page clears soon after the incident resolves instead of lingering. Burn rate itself (`current_error_rate / SLO_error_rate`) sets the severity: 14.4× burns the whole budget in ~2 days, which is page-worthy.
```

---

## Phase 8: Alert Design

Alerting is where observability meets pain. A bad alerting strategy makes oncall miserable and trains people to ignore pages. The goal is *every page is actionable, urgent, and not self-resolving*.

### 8.1 Symptom-Based vs. Cause-Based

**Symptom-based**: alert on what the user feels. "Error rate > 1%." "Latency p99 > 1s." These are SLO violations.

**Cause-based**: alert on what *might* lead to a symptom. "CPU > 90%." "Memory > 85%." "Disk free < 10%."

The Google SRE rule of thumb: **prefer symptom-based alerts**. Reasons:
- Cause-based alerts page you for things that aren't actually broken. CPU pinned at 95% for an hour with no user impact is "we should look at this," not "wake someone up."
- Symptoms are stable; causes are many. The same symptom (high latency) has dozens of causes (slow DB, queue backed up, dependency timeout). Alert on the symptom; diagnose the cause.

Cause-based alerts have their place as **tickets** (next-business-day attention), not pages, and as **capacity planning signals**. Wakeups should be symptom-driven.

### 8.2 The Frameworks

Three overlapping mnemonics. Learn all three.

**The Four Golden Signals** (Google SRE):
1. **Latency** — how long requests take. Differentiate successful vs. failed latency (a fast 500 is its own problem).
2. **Traffic** — how many requests/sec.
3. **Errors** — fraction failing.
4. **Saturation** — how full the system is (CPU, memory, queue depth, connection pool).

**RED** (Tom Wilkie, request-driven services):
- **Rate** — requests per second.
- **Errors** — failures per second.
- **Duration** — distribution (p50, p95, p99).

A RED dashboard, one row per service, one column for each: this is the default starting point for microservices monitoring.

**USE** (Brendan Gregg, resource utilization):
- **Utilization** — % time the resource is busy.
- **Saturation** — queue depth / wait time.
- **Errors** — error count.

USE applies to *resources* (CPU, disk, network, memory, connection pool); RED applies to *services*. Together they're complete: RED on the services, USE on the things they consume.

References: [SRE Book, Ch. 6 Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/), [Tom Wilkie on RED](https://thenewstack.io/monitoring-microservices-red-method/), [Brendan Gregg USE method](https://www.brendangregg.com/usemethod.html)

### 8.3 Alert Anti-Patterns

The set of well-known mistakes:

- **The flapping alert.** Fires, resolves, fires, resolves. Usually a threshold sitting right at normal load. Fix by widening the threshold, lengthening the window, or using burn-rate alerts.
- **The static threshold for dynamic traffic.** "Page if requests/sec < 100." Wakes up at 3 AM when traffic naturally dips. Compare to last week's same hour, or alert on *error ratio*, not raw rate.
- **The cause-based page for benign causes.** "CPU > 80%." Most modern services tolerate sustained 80% CPU. Page on user-visible effects.
- **The alert that points at the wrong on-call.** Alerts must route to the team that can fix it. Cross-team alerts are tickets, not pages.
- **No runbook.** A page that arrives at 3 AM with no link to "what to do next" is hostile to the responder. Every page must link to an actionable runbook.
- **Alert on individual hosts.** "Pod X has high CPU" — in a fleet of 100 pods, who cares? Alert on *fleet-level symptoms*.
- **Repeating the same alert at the same level.** Don't ticket-flood. Group by service or incident.
- **Test/staging alerts paging prod oncall.** Separate routing trees per environment.
- **Alerting on the wrong derivative.** "Disk filling up" vs. "disk will fill in 4 hours." The latter is far more actionable; use `predict_linear()` in PromQL.

### 8.4 Alert Routing and Severity

Severity tiers (typical):
- **P1 / page** — user impact ongoing, immediate response, wake people up.
- **P2 / urgent** — significant impact, response within business hours.
- **P3 / ticket** — must be addressed but not blocking.
- **P4 / informational** — log it; don't notify.

Routing:
- Pages → on-call rotation (PagerDuty, OpsGenie, Squadcast, VictorOps, Grafana OnCall).
- Tickets → Slack channel + Jira issue.
- Informational → dashboard counter only.

**Escalation policy** — first responder doesn't ack in 10 minutes → next person → manager → entire team. PagerDuty has this baked in; configure it on every page.

### 8.5 On-Call Ergonomics

The team-level health metric: **pages per shift**. Two pages a week per responder is sustainable. Two pages a *night* makes them quit.

Practices that keep oncall livable:
- **Weekly oncall review** — every page from last week, was it actionable? If not, kill or rewrite the alert.
- **Page → action loop** — every page resolved either with a fix, an alert improvement, or a runbook update. The page didn't just close; the system improved.
- **The "you build it, you run it" team boundary** — the team that ships the service gets paged on it. Otherwise no incentive to fix flakiness.
- **Pre-rotation handoff** — incoming oncall reads through open incidents, recent pages, known issues. Doc lives in the team's runbook.

The single most powerful org-level change is **counting and reporting page volume**. Once page count is a tracked metric, teams have permission to spend time killing noise. Without that visibility, noise wins.

References: [PagerDuty Incident Response](https://response.pagerduty.com/), [Increment: On-Call](https://increment.com/on-call/)

```quiz
Q: Why does Google SRE recommend preferring symptom-based alerts over cause-based ones for paging?
- [ ] Symptoms are cheaper to compute in PromQL
- [x] Causes are many and often benign (95% CPU with no user impact), while symptoms are stable and map to what users actually feel
- [ ] Cause-based alerts can't be routed to oncall
- [ ] Symptom alerts never flap
> One symptom (high latency) has dozens of possible causes (slow DB, backed-up queue, dependency timeout), and many "causes" like pinned CPU don't actually hurt users. Paging on symptoms means every wake-up corresponds to real user impact, and you diagnose the cause once you're already engaged. Cause-based signals still matter — as tickets and capacity-planning inputs — just not as pages.

Q: An alert pages at 3 AM because "requests/sec < 100" during a natural overnight traffic dip. What's the right fix?
- [ ] Lower the threshold to 50
- [x] Alert on error *ratio* (or compare to the same hour last week) rather than a static raw-rate threshold against dynamic traffic
- [ ] Route it to a different team
- [ ] Add a longer escalation timer
> A static threshold against traffic that naturally varies will fire on benign dips — it's measuring volume, not health. Error *ratio* (good/total) is traffic-independent, and comparing to the same hour last week (`offset 1w`) accounts for the daily cycle. The page should reflect that something is actually wrong, not that it's night.

Q: Why is "disk free < 10%" a worse page than "disk will fill in 4 hours" via `predict_linear()`?
- [ ] The first uses more storage
- [x] The predictive form is actionable with lead time and won't page for a disk that's stably at 9% forever
- [ ] `predict_linear()` is more accurate at measuring current usage
- [ ] Static thresholds aren't supported in Prometheus
> A disk parked at 9% free indefinitely will page forever under a static threshold while nothing is actually wrong, and a disk filling fast might cross 10% with almost no time to react. Alerting on the *trend* — "at the current fill rate it's full in 4 hours" — pages only when action is genuinely needed and gives the responder runway. It's alerting on the right derivative.
```

---

## Phase 9: Dashboards

Dashboards are where observability gets *consumed*. A great dashboard answers a real question in seconds; a bad one is wallpaper.

### 9.1 What Dashboards Are For

Three legitimate uses:
1. **Status at a glance** — is the service healthy? RED dashboards, traffic dashboards, top-level SLO compliance.
2. **Incident triage** — when paged, the responder pulls this up to localize the problem.
3. **Capacity / trend** — long-horizon: are we growing into a wall?

What dashboards are *not* for:
- Exploration. Dashboards are pre-canned views; arbitrary questions go to the query layer (Explore in Grafana, or the backend's own query UI).
- Browsing for bugs. If you're hunting a problem, you should be in logs / traces / events, not adjusting time ranges on graphs.
- Decoration. The Grafana wallpaper in the office TV is fine; it's not observability.

### 9.2 The Five-Second Rule

A dashboard panel should communicate its meaning within five seconds of looking at it. If a stranger to the system can't tell whether a number is good or bad in five seconds, the panel is failing.

Implications:
- **Always have a baseline visible.** Comparison to "last week" (`offset 7d`) or to an SLO line or to a deploy marker is the difference between "graph went up — bad?" and "graph went up 30% from last week — bad."
- **Color tells the story.** Red = bad. Green = good. Use thresholds. Don't use rainbow palettes for time-series.
- **Units on the axes.** "seconds" or "requests/sec" or "%." Grafana's unit picker is non-negotiable.
- **Title says the question, not the metric name.** "p99 checkout latency" instead of `histogram_quantile_0.99_request_duration_seconds_checkout_bucket`.
- **One question per panel.** Don't mix latency and error rate in one chart; the user has to parse it.

### 9.3 The Standard Dashboards

Every service should have, at minimum, three dashboards:

**RED dashboard** — service-level, one row per endpoint or operation:
- Rate (requests/sec)
- Errors (errors/sec or error ratio)
- Duration (p50, p95, p99 latency histograms)

**USE dashboard** — for the underlying resources:
- CPU utilization, load average
- Memory used vs. limit
- Disk IOPS, throughput
- Network in/out
- Saturation: connection pool usage, queue depth, GC pause time

**SLO dashboard** — for the contract:
- Current SLO compliance (% over 30 days)
- Error budget remaining (gauge)
- Burn rate (current and historical)
- Time-to-exhaustion projection

For data pipelines, freshness and run-success dashboards replace RED. For batch infrastructure, USE plus job-success dashboards. The framework is the same; the SLIs differ.

### 9.4 Dashboards as Code

Click-built dashboards in Grafana are easy but unreviewable, ungovernable, and break silently when someone edits them. Mature stacks define dashboards as code:

- **Grafonnet** (Jsonnet) — Grafana's official dashboard-as-code library. Verbose but precise.
- **grafanalib** (Python) — community library.
- **Terraform Grafana provider** — manage dashboards (and folders, alert rules, datasources) declaratively.
- **Grizzly** — Grafana Labs' Kubernetes-style YAML for Grafana objects.
- **Perses** — newer CNCF dashboarding project, dashboards-as-code by design.

The pattern:
1. Define dashboards in code, in a repo.
2. CI lints them (e.g. ensure unit annotations, threshold colors).
3. CD applies them via Terraform or the Grafana API.
4. Manual edits in the UI are read-only or auto-reverted.

References: [Grafonnet](https://grafana.github.io/grafonnet-lib/), [USE method dashboards](https://www.brendangregg.com/usemethod.html), [RED method (Weaveworks)](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/)

### 9.5 Grafana, Briefly

Grafana is the de facto open-source dashboard UI. Key features to internalize:

- **Datasources** — Prometheus, Loki, Tempo, Mimir, Cortex, InfluxDB, PostgreSQL, MySQL, CloudWatch, Datadog, many more. A single dashboard can pull from multiple datasources.
- **Variables** — `$service`, `$env`, `$cluster`. Templated dashboards that work across many instances.
- **Annotations** — overlay deploy markers, incident timelines.
- **Explore** — interactive query UI for ad-hoc investigation. The right place to be when poking, not a saved dashboard.
- **Alerting** — Grafana has its own unified alerting layer (Grafana 8+) that can use any datasource. Many shops use Prometheus's native alertmanager for metric alerts and Grafana for cross-source alerts (e.g., correlating logs and metrics).
- **Service Graph** — a Tempo feature that derives service maps from traces.

Grafana's competition: vendor dashboards (Datadog, New Relic), open-source alternatives (Perses, Chronograf, Kibana). Grafana wins by being multi-datasource — it sits in front of your *whole* observability stack.

---

## Phase 10: The Tooling Landscape

Be honest about what each tool is for and what it costs. The matrix is busy; here's the working engineer's view.

### 10.1 Open-Source Stacks

| Tool                   | Pillar              | Strength                                      | Weakness                              |
|------------------------|---------------------|-----------------------------------------------|---------------------------------------|
| Prometheus             | Metrics             | The standard. Universal exporters, PromQL     | Single-binary scale ceiling           |
| Mimir                  | Metrics (long-term) | Horizontally scalable Prometheus              | Operationally non-trivial             |
| Cortex                 | Metrics             | Predecessor to Mimir                          | Mostly superseded by Mimir            |
| Thanos                 | Metrics             | Object-store sidecar approach                 | More moving parts than Mimir          |
| VictoriaMetrics        | Metrics             | High-perf single-binary TSDB                  | Smaller ecosystem                     |
| Loki                   | Logs                | Cheap, label-indexed                          | Full-text search is a scan            |
| OpenSearch / Elastic   | Logs                | Rich query, mature                            | Operationally heavy, costly           |
| Tempo                  | Traces              | Object-store-backed traces                    | Limited query (TraceQL still maturing)|
| Jaeger                 | Traces              | The OG, well-trodden                          | Storage backends each their own thing |
| Pyroscope / Phlare     | Profiles            | Continuous profiling                          | Smaller ecosystem                     |
| Parca                  | Profiles            | eBPF, language-agnostic                       | Requires kernel support               |
| Grafana                | UI                  | Multi-datasource, dashboards, alerting        | UI/UX evolves, breaking changes       |
| OpenTelemetry Collector | Router             | Unified telemetry routing                     | Config sprawl at scale                |

The canonical open-source "Grafana LGTM" stack: **Loki + Grafana + Tempo + Mimir** (formerly Cortex), all with Grafana as UI. A complete metrics + logs + traces stack, self-hostable, with OTel as the ingestion path. Add Pyroscope for profiles.

### 10.2 Hosted / Vendor

| Vendor             | Coverage                                  | Pricing model                          |
|--------------------|-------------------------------------------|----------------------------------------|
| Datadog            | Metrics, logs, traces, profiles, RUM, security, infra, synthetics | Per host + per ingest GB + per indexed log + many add-ons |
| New Relic          | Same breadth                              | Per ingested GB, single tier           |
| Splunk Observability Cloud | Metrics, traces, RUM; Splunk Enterprise for logs | Per host + per ingested log |
| Dynatrace          | Metrics, traces, RUM, AI-driven           | Per host-hour + per ingested item      |
| Honeycomb          | Events / traces (their model)             | Per event ingest                       |
| Grafana Cloud      | The LGTM stack hosted                     | Per active series + per ingested log GB + per traced span |
| Chronosphere       | Metrics-focused (Mimir-style)             | Per active series                      |
| Lightstep          | Traces + metrics                          | Acquired into ServiceNow               |
| Sentry             | Errors + (now) traces                     | Per event                              |
| AWS CloudWatch     | AWS-native; integrates with everything    | Per metric + per log GB                |
| GCP Cloud Operations | GCP-native                              | Per metric + per log GB                |
| Azure Monitor      | Azure-native                              | Per ingested GB                        |

The honest summary:

- **Datadog** is the most-featured one-stop shop. Setup time measured in days. Bills measured in surprise. Has the best out-of-the-box integration coverage for vendors.
- **Honeycomb** is the best at high-cardinality event-style observability. If your bug-fixing pattern is "slice traces by 4 dimensions," Honeycomb is the answer.
- **New Relic** simplified its pricing to per-GB, which is friendlier for small teams.
- **Splunk** dominates security / SIEM use cases; Splunk Observability is its APM half (acquired SignalFx).
- **Grafana Cloud** is the easiest open-source-feeling hosted option; you avoid running Mimir/Loki/Tempo yourself.
- **CloudWatch / GCP Operations / Azure Monitor** are fine for the bare minimum; expensive at scale and weaker on traces.

### 10.3 Cost Models, Mental and Dollar

Hidden costs to budget:
- **Series count, not metric count.** A single metric with 50 labels is 50× a single metric with 1.
- **Ingest vs. indexed vs. retained.** Datadog famously bills all three.
- **Log GB grows with traffic** — your logs bill doubles when your business does. Plan for sampling and tiered retention before you cross $10K/mo.
- **Profiles are tiny** — adding profiles is the rare freebie.
- **High-cardinality logs blow up indexing**. Vendor pricing models incentivize you to keep log fields low-cardinality even when it hurts debugging.

Self-host vs. buy:
- **Buy at 0–20 engineers.** Operational cost of running observability infra > vendor bill.
- **Hybrid at 20–200.** Self-host metrics (Mimir/Prometheus), buy logs (cost-prohibitive to self-host high-volume), buy traces.
- **Self-host at 200+** or where vendor cost grows faster than engineering cost. Big tech runs custom internal stacks.

Vendor lock-in:
- **Custom dashboards** are the deepest lock-in. Use Grafana even with vendor backends; Grafana speaks Datadog, CloudWatch, etc.
- **Custom alert rules** in vendor UIs are second-deepest. Define alerts as code (Terraform, Pulumi) where possible.
- **OpenTelemetry instrumentation** removes the *producer-side* lock-in. The agent-side bill is the easiest to switch.

References: [The Cost of Observability — Charity Majors](https://charity.wtf/2024/01/15/the-cost-of-observability/), [Honeycomb pricing rationale](https://www.honeycomb.io/pricing-rationale)

---

## Phase 11: Operational Realities

The things you only learn after running an observability stack in anger.

### 11.1 Observing the Observer

Your observability stack is itself a production system. It needs:
- Its own alerts (Prometheus is down → fall back to a sidecar; Mimir ingestion lag → page).
- Its own dashboards (active series, ingested GB/s, query QPS, P99 query latency).
- Its own SLO ("99% of pages alert within 90s of an incident starting").

Prometheus alerts itself via [Dead Man's Switch](https://github.com/prometheus/alertmanager/blob/main/doc/examples/simple.yml): a perpetually-firing alert that an *external* watchdog (Cronitor, HealthChecks.io, AWS) monitors. If the watchdog stops getting the heartbeat, the watchdog pages — because your alerting system is down.

### 11.2 Cardinality Incidents

The classic outage: a developer adds a label like `request_id` to a metric. Series count goes from 10K to 100M in an hour. Prometheus OOMs. Alerting stops. Now you're flying blind during the incident *you caused*.

Defenses (recap):
- Lint at commit time.
- Series limits per scrape and per tenant.
- Pre-rollout testing with cardinality reports.
- Recording rules + drop relabeling for the worst metrics.
- Per-team cardinality budgets, visible.

When it happens (it will), the playbook:
1. Identify the offending metric/series via `/api/v1/status/tsdb` top-cardinality endpoint.
2. Add a `metric_relabel_configs` drop rule at the scrape layer (faster than redeploying the producer).
3. Rolling-restart Prometheus.
4. File the postmortem; add the rule to lint config.

### 11.3 Sampling at Scale

Once you cross a few thousand spans/sec, you can't afford to keep them all. Tail-sampling is the technical answer; the operational reality is:

- **Tail sampling requires the same collector to see all spans of a trace.** Use consistent hashing on trace ID at the load balancer.
- **Buffer memory grows with `decision_wait` × QPS.** A 10s decision wait on a 100K spans/sec service buffers a million spans. Plan capacity.
- **The "interesting" sampling policies need calibration.** "Sample errors" sounds simple — but if your service has a 5% error rate, errors aren't rare, and you'll keep too much. Add rate limits.

### 11.4 The Build-vs-Buy Decision, Recurring

Three forces:
1. **Operational cost** of running the stack — engineers, infra, on-call for the stack itself.
2. **Vendor cost** — the bill, often growing nonlinearly in scale.
3. **Capability cost** — features (continuous profiling, RUM, synthetics, ML) are hard to DIY.

The honest move: revisit the choice every 12–18 months. Vendors change pricing. Open-source projects mature (Mimir didn't exist five years ago; Tempo six). Your scale grows. The right answer at headcount 5 is not the right answer at headcount 500.

### 11.5 Multi-Tenant and Multi-Region

At scale you'll want:
- **Per-team / per-tenant rate limits** — one team can't fire-hose the shared TSDB.
- **Per-team quotas** — visible to teams so they self-regulate.
- **Multi-region collection** — collectors regional, central tier aggregates. Reduces cross-region traffic and respects data-residency rules.
- **Disaster recovery** — your metrics and logs live in object storage with cross-region replication. Mimir / Loki / Tempo all play well here.

References: [Mimir operational guide](https://grafana.com/docs/mimir/latest/manage/), [Prometheus operational best practices](https://prometheus.io/docs/practices/)

---

## Phase 12: Recipe — Instrumenting a Go HTTP Service with OpenTelemetry

End-to-end. Metrics, logs, traces — one consistent set of attributes, OTLP to a collector. Demonstrates the conventions you'd use anywhere.

### 12.1 The Service

A trivial HTTP server exposing `GET /users/:id` that fetches a user from Postgres.

### 12.2 Dependencies

```go
// go.mod (relevant lines)
require (
    go.opentelemetry.io/otel v1.28.0
    go.opentelemetry.io/otel/sdk v1.28.0
    go.opentelemetry.io/otel/sdk/metric v1.28.0
    go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.28.0
    go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc v1.28.0
    go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.53.0
    go.opentelemetry.io/contrib/instrumentation/github.com/jackc/pgx/otelpgx v0.4.0
    log/slog
)
```

### 12.3 Bootstrap

```go
package telemetry

import (
    "context"
    "log/slog"
    "os"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/propagation"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

func Init(ctx context.Context, service, version, env string) (func(context.Context) error, error) {
    res, err := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName(service),
            semconv.ServiceVersion(version),
            semconv.DeploymentEnvironment(env),
        ),
        resource.WithHost(),
        resource.WithProcess(),
        resource.WithContainer(),
    )
    if err != nil {
        return nil, err
    }

    // Traces
    traceExp, err := otlptracegrpc.New(ctx)
    if err != nil {
        return nil, err
    }
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(traceExp),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1))),
    )
    otel.SetTracerProvider(tp)

    // Metrics
    metricExp, err := otlpmetricgrpc.New(ctx)
    if err != nil {
        return nil, err
    }
    mp := sdkmetric.NewMeterProvider(
        sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExp)),
        sdkmetric.WithResource(res),
    )
    otel.SetMeterProvider(mp)

    // W3C trace context + baggage propagation
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{},
        propagation.Baggage{},
    ))

    // Structured logs — slog JSON handler, attach trace_id/span_id via middleware.
    logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
    slog.SetDefault(logger)

    shutdown := func(ctx context.Context) error {
        _ = tp.Shutdown(ctx)
        _ = mp.Shutdown(ctx)
        return nil
    }
    return shutdown, nil
}
```

`OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317` and friends control where it goes — no hardcoded endpoints.

### 12.4 The Handler with Custom Span and Metric

```go
package main

import (
    "context"
    "log/slog"
    "net/http"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/metric"
    "go.opentelemetry.io/otel/contrib/instrumentation/net/http/otelhttp"
)

var (
    tracer        = otel.Tracer("api")
    meter         = otel.Meter("api")
    reqCounter    metric.Int64Counter
    reqHistogram  metric.Float64Histogram
)

func init() {
    var err error
    reqCounter, err = meter.Int64Counter("http_requests_total",
        metric.WithDescription("Total HTTP requests"),
    )
    if err != nil { panic(err) }
    reqHistogram, err = meter.Float64Histogram("http_request_duration_seconds",
        metric.WithDescription("HTTP request duration"),
        metric.WithUnit("s"),
        metric.WithExplicitBucketBoundaries(
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
        ),
    )
    if err != nil { panic(err) }
}

func getUser(w http.ResponseWriter, r *http.Request) {
    ctx, span := tracer.Start(r.Context(), "getUser",
        // High-cardinality on spans is fine; on metrics it is not.
        // user_id goes on the span, not on the counter.
        attribute.String("user.id", r.PathValue("id")),
    )
    defer span.End()

    user, err := fetchUser(ctx, r.PathValue("id"))
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        slog.ErrorContext(ctx, "fetchUser failed",
            "user_id", r.PathValue("id"),
            "trace_id", span.SpanContext().TraceID().String(),
            "error", err,
        )
        http.Error(w, "internal", http.StatusInternalServerError)
        return
    }
    _ = writeJSON(w, user)
}

func main() {
    ctx := context.Background()
    shutdown, _ := telemetry.Init(ctx, "api", "v1.2.3", "prod")
    defer shutdown(ctx)

    mux := http.NewServeMux()
    mux.HandleFunc("GET /users/{id}", getUser)

    // otelhttp auto-instruments: spans, metrics, propagation
    handler := otelhttp.NewHandler(mux, "api",
        otelhttp.WithSpanNameFormatter(func(_ string, r *http.Request) string {
            return r.Method + " " + r.Pattern // /users/{id}, not /users/12345
        }),
    )

    _ = http.ListenAndServe(":8080", handler)
}
```

### 12.5 Wiring Logs to Traces

The discipline: every log emitted inside a request handler attaches `trace_id` and `span_id` (extracted from the context). Then in Grafana, a log line links straight to the trace and vice versa.

```go
func WithTrace(ctx context.Context, attrs ...slog.Attr) []slog.Attr {
    sc := trace.SpanContextFromContext(ctx)
    if sc.HasTraceID() {
        attrs = append(attrs,
            slog.String("trace_id", sc.TraceID().String()),
            slog.String("span_id", sc.SpanID().String()),
        )
    }
    return attrs
}
```

Make it a middleware / wrapper logger so individual handlers don't repeat the boilerplate.

### 12.6 The Collector for This Service

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }

processors:
  memory_limiter: { check_interval: 1s, limit_mib: 1500 }
  resourcedetection:
    detectors: [env, system, ec2]
  batch: { timeout: 5s, send_batch_size: 1024 }
  attributes/redact:
    actions:
    - key: http.request.header.authorization
      action: delete

exporters:
  otlp/tempo:    { endpoint: tempo:4317,    tls: { insecure: true } }
  prometheusremotewrite:
    endpoint: http://mimir:9009/api/v1/push
  otlphttp/loki:
    endpoint: http://loki:3100/otlp

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, attributes/redact, batch]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, batch]
      exporters: [prometheusremotewrite]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, attributes/redact, batch]
      exporters: [otlphttp/loki]
```

Now every request emits a trace, increments a counter, samples a histogram, and produces a structured log line — all sharing `trace_id`, `service`, `env`, `version`. In Grafana, a panel on the dashboard links straight to logs filtered by `trace_id`, and from any log line you jump to the trace.

References: [OTel Go contrib](https://github.com/open-telemetry/opentelemetry-go-contrib), [semconv](https://opentelemetry.io/docs/specs/semconv/)

---

## Phase 13: Recipe — Multi-Window Burn-Rate SLO Alerts in PromQL

Translating Phase 7's theory into real queries you'd deploy.

### 13.1 The Setup

Service `api`. SLO: **99.9% of HTTP requests return non-5xx in 30 days.** Error budget allowed rate: `1 - 0.999 = 0.001`.

The base SLIs as recording rules:

```yaml
groups:
- name: slo:api:rules
  interval: 30s
  rules:
  - record: slo:api:requests:rate5m
    expr: sum(rate(http_requests_total{job="api"}[5m]))
  - record: slo:api:errors:rate5m
    expr: sum(rate(http_requests_total{job="api", status=~"5.."}[5m]))
  - record: slo:api:error_ratio:5m
    expr: slo:api:errors:rate5m / slo:api:requests:rate5m

  # Repeat for the other windows we need
  - record: slo:api:error_ratio:30m
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[30m]))
        / sum(rate(http_requests_total{job="api"}[30m]))
  - record: slo:api:error_ratio:1h
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[1h]))
        / sum(rate(http_requests_total{job="api"}[1h]))
  - record: slo:api:error_ratio:6h
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[6h]))
        / sum(rate(http_requests_total{job="api"}[6h]))
  - record: slo:api:error_ratio:2h
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[2h]))
        / sum(rate(http_requests_total{job="api"}[2h]))
  - record: slo:api:error_ratio:24h
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[24h]))
        / sum(rate(http_requests_total{job="api"}[24h]))
  - record: slo:api:error_ratio:3d
    expr: |
      sum(rate(http_requests_total{job="api", status=~"5.."}[3d]))
        / sum(rate(http_requests_total{job="api"}[3d]))
```

### 13.2 The Alerts

The multi-window burn-rate pattern from the SRE Workbook. SLO error budget is `0.001`. Burn-rate thresholds derived from "consume X% of 30d budget in window Y":

```yaml
groups:
- name: slo:api:alerts
  rules:
  # Fast burn: would deplete entire 30d budget in ~2 days at this rate
  # Both 1h and 5m windows must be elevated for the alert to fire
  - alert: APIFastErrorBudgetBurn
    expr: |
      (
        slo:api:error_ratio:1h > (14.4 * 0.001)
        and
        slo:api:error_ratio:5m > (14.4 * 0.001)
      )
    for: 2m
    labels:
      severity: page
      slo: api-availability
    annotations:
      summary: "API burning error budget very fast"
      description: "1h error rate is {{ $value | humanizePercentage }} (>14.4x SLO error rate)."
      runbook: "https://wiki.example.com/runbooks/api-error-budget"

  # Medium burn: would deplete 30d budget in ~5 days
  - alert: APIMediumErrorBudgetBurn
    expr: |
      (
        slo:api:error_ratio:6h > (6 * 0.001)
        and
        slo:api:error_ratio:30m > (6 * 0.001)
      )
    for: 15m
    labels:
      severity: page
      slo: api-availability
    annotations:
      summary: "API burning error budget moderately fast"
      runbook: "https://wiki.example.com/runbooks/api-error-budget"

  # Slow burn: would deplete 30d budget in ~10 days. Ticket, not page.
  - alert: APISlowErrorBudgetBurn
    expr: |
      (
        slo:api:error_ratio:24h > (3 * 0.001)
        and
        slo:api:error_ratio:2h > (3 * 0.001)
      )
    for: 1h
    labels:
      severity: ticket
      slo: api-availability

  # Very slow long-term erosion: ticket
  - alert: APIErrorBudgetEroding
    expr: |
      (
        slo:api:error_ratio:3d > (1 * 0.001)
        and
        slo:api:error_ratio:6h > (1 * 0.001)
      )
    for: 3h
    labels:
      severity: ticket
      slo: api-availability
```

The four-tier pattern ensures:
- **Fast and big** incidents page within ~2 minutes.
- **Slow drips** are caught as tickets, not 3 AM pages.
- The short window guards against alerting on incidents that have *already resolved*; once the 5m or 30m short window drops below threshold, the alert auto-clears.

### 13.3 The Budget-Remaining Dashboard Panels

```promql
# Error budget remaining as a fraction (1 = full budget, 0 = empty, negative = over)
1 - (
  (1 - (sum(increase(http_requests_total{job="api",status=~"5.."}[30d]))
         / sum(increase(http_requests_total{job="api"}[30d]))))
  - 0.999
) / 0.001
```

Or, more transparently, using recording rules for the 30d ratio:

```yaml
- record: slo:api:error_ratio:30d
  expr: |
    sum(rate(http_requests_total{job="api",status=~"5.."}[30d]))
      / sum(rate(http_requests_total{job="api"}[30d]))
```

Then:

```promql
# Budget consumed fraction
slo:api:error_ratio:30d / 0.001

# Budget remaining fraction
1 - slo:api:error_ratio:30d / 0.001
```

Plot the remaining as a gauge with red below 0, amber 0–0.25, green above. Anyone glancing at the dashboard knows the state in two seconds.

References: [SRE Workbook, Ch. 5](https://sre.google/workbook/alerting-on-slos/), [Sloth — SLO generator](https://sloth.dev/), [Pyrra](https://github.com/pyrra-dev/pyrra)

---

## Phase 14: Recipe — Writing a Runbook

A runbook is what a stranger reads at 3 AM when paged. The single highest-leverage observability artifact, and the most universally neglected.

### 14.1 Runbook Anatomy

```markdown
# Runbook: APIFastErrorBudgetBurn

## What this alert means
The api service is burning its 99.9% availability SLO budget fast enough
that the 30-day budget would be exhausted in ~2 days at the current rate.
This means roughly: 5xx error rate on the api service has spiked above
1.44% sustained for at least 5 minutes.

## Severity
P1 / page. Customer-facing impact ongoing.

## Owner
team-platform-api. Slack: #api-oncall. Escalation: @api-oncall.

## Diagnose

1. Open the API service dashboard:
   https://grafana.example.com/d/api-overview?from=now-1h
   Confirm: RED panel shows elevated error rate. Identify which endpoint(s).

2. Pivot to per-endpoint error ratio:
   Query: `sum by (path) (rate(http_requests_total{job="api",status=~"5.."}[5m]))
            / sum by (path) (rate(http_requests_total{job="api"}[5m]))`
   The top result is where the errors live.

3. For the top endpoint, look at traces:
   Open Tempo, filter by `service.name=api`, `http.route=<endpoint>`,
   `status=error`. Pick a recent trace. The span with the red icon is
   where the request failed. Common causes:
   - Downstream service 5xx → check that service's dashboard
   - DB query timeout → check Postgres dashboard, look for long queries
   - Panic / unhandled exception → check logs (see step 4)

4. For the top endpoint, query logs:
   Loki: `{service="api"} |= "level=error" |~ "<endpoint>"`
   Look at the most recent error message and stack trace.

5. Correlate to deploys: check the deploy annotation track in Grafana.
   Was there a deploy of api within the last hour? Roll it back first,
   diagnose second.

## Mitigation

- **If recent deploy is suspect**: roll back via `kubectl rollout undo
  deployment/api -n prod`. Verify error rate drops within 5 min.
- **If a downstream is failing**: page that team. Consider circuit-breaking
  the dependency via flag `feature.<name>.fallback=true`.
- **If DB is overloaded**: throttle traffic via the API gateway (see
  https://wiki.example.com/runbooks/api-throttle). Page DBA.
- **If unknown**: declare an incident in #incidents. Get IC on the call.

## Post-incident

- Open a postmortem within 24 hours.
- Confirm the alert fired correctly and resolved correctly.
- If the alert took too long to fire, file a ticket to tune burn-rate windows.
- If the alert was noisy, same.

## Related dashboards / queries
- API overview: https://grafana.example.com/d/api-overview
- API SLO budget: https://grafana.example.com/d/api-slo
- Postgres health: https://grafana.example.com/d/postgres

## Last reviewed: 2026-04-02 by @sanjee
```

### 14.2 Runbook Principles

- **Located at the alert.** Link from the alert annotation directly. Don't make the responder hunt.
- **Diagnose before mitigate.** Tell them what's likely wrong before what to do about it.
- **One concrete query per claim.** "Check the latency" is useless; "open this dashboard and look at this panel" is gold.
- **Updated after every incident.** A runbook that wasn't useful last incident must be improved or rewritten.
- **Versioned.** In a repo, alongside code. Reviewed like code.
- **Tested.** Periodically, in chaos drills or fire-drills, have someone follow the runbook cold. If they get stuck, the runbook needs work.

### 14.3 Anti-Patterns

- **Runbooks that say "ask Alice."** Alice goes on vacation; the runbook breaks. Document the steps Alice takes.
- **Runbooks that are just SOP-style prose.** Use commands and links.
- **One mega-runbook for the service.** Per-alert runbooks. Each alert links to its own.
- **Runbooks for non-alerts.** "How to deploy" is a procedure, not a runbook. Runbooks are *for incidents*.

References: [PagerDuty Runbook templates](https://response.pagerduty.com/oncall/runbooks/), [Increment: Documentation](https://increment.com/documentation/)

---

## Phase 15: Anatomy of a Production Observability Stack

Walking through a realistic end-to-end stack so the pieces land in place. Scenario: a mid-stage SaaS, ~150 engineers, K8s on AWS, Go and Python services, a Postgres OLTP DB, Kafka, a data lake.

### 15.1 The Architecture, at a Glance

```
   ┌────────────┐    ┌────────────┐    ┌─────────────┐
   │ Go service │    │ Py service │    │  Postgres   │
   │  (OTel SDK)│    │ (OTel SDK) │    │ (exporter)  │
   └──────┬─────┘    └──────┬─────┘    └──────┬──────┘
          │ OTLP/gRPC       │ OTLP/gRPC       │ /metrics
          ▼                 ▼                 ▼
   ┌──────────────────────────────────────────────────┐
   │  OpenTelemetry Collector — DaemonSet (agent tier)│
   │  Receives OTLP + scrapes node_exporter, cAdvisor │
   │  Adds k8s.* resource attrs, host attrs           │
   └──────────────────────┬───────────────────────────┘
                          │ OTLP/gRPC
                          ▼
   ┌──────────────────────────────────────────────────┐
   │  OpenTelemetry Collector — Deployment (gateway)  │
   │  Tail sampling, redaction, routing               │
   └──────┬────────────────┬──────────────────┬───────┘
          │ remote_write   │ OTLP             │ OTLP/Loki
          ▼                ▼                  ▼
   ┌──────────┐      ┌──────────┐       ┌──────────┐
   │  Mimir   │      │  Tempo   │       │   Loki   │
   │ (metrics)│      │ (traces) │       │  (logs)  │
   └────┬─────┘      └────┬─────┘       └────┬─────┘
        │                  │                  │
        ▼                  ▼                  ▼
   ┌──────────────────────────────────────────────────┐
   │     S3 (object storage — long-term retention)    │
   └──────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │       Grafana         │ ◀── humans
              │ (dashboards, Explore, │
              │  unified alerting)    │
              └─────┬─────────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │   PagerDuty + Slack       │
        └───────────────────────────┘
```

### 15.2 Step by Step, with the Choices Called Out

**Producers**

- **Go and Python services** — instrumented with the OpenTelemetry SDK. Auto-instrumentation for HTTP/gRPC/DB; manual spans on business operations. Each service sets `service.name`, `service.version`, `deployment.environment` via env vars from the K8s downward API. Logs are structured JSON (`slog` in Go, `structlog` in Python), shipped over OTLP — *not* via files, removing the agent-scraping dependency for logs.
- **Postgres and other infra** — scraped by exporters. `postgres_exporter`, `redis_exporter`, `kafka_exporter`, `blackbox_exporter` (external probes). These targets are discovered via K8s annotations.

Choice points:
- *OTLP everywhere* over Datadog SDKs / New Relic agents. Vendor-agnostic; one library to learn per language.
- *Structured logs via OTLP*, not log files. Saves the log-tail agent; ensures trace_id and span_id correlate automatically.

**Agent tier — OTel Collector DaemonSet**

- One collector per node, running as a DaemonSet. Workloads send OTLP to `127.0.0.1:4317` (localhost, very fast).
- The agent enriches with K8s resource attributes (`k8s.pod.name`, `k8s.namespace.name`, `k8s.node.name`) via the `k8sattributes` processor.
- It also scrapes `node_exporter` and `cAdvisor` on its host and emits OTLP metrics.
- Local buffering on disk via the `file_storage` extension. Survives short collector restarts without dropping data.

Choice points:
- *Agent + gateway* instead of agent-only. The gateway enables global tail sampling; the agent enables low-latency local ingestion. Both layers are stateless and horizontally scalable.

**Gateway tier — OTel Collector Deployment**

- A horizontally-scaled fleet behind a Kubernetes Service. Trace ID hashing at the LB level (`load_balancing_exporter` between agents and gateways) so all spans of a trace hit the same gateway pod — required for tail sampling.
- Processors: `tail_sampling` (keep all errors, all slow traces, 5% of everything else), `transform` (PII redaction on log bodies), `batch`, `memory_limiter`.
- Exporters: `prometheusremotewrite` → Mimir; `otlp` → Tempo; `otlphttp` → Loki.

Choice points:
- *Tail-sampling at the gateway*, not the agent. The agent can't see whole traces; the gateway can.
- *Redaction at the gateway*, not in producer code. Centralized policy, faster to change. Producer code is responsible for *not putting raw PII into spans* in the first place — defense in depth.

**Storage — Mimir + Tempo + Loki**

- **Mimir** for metrics. Multi-tenant; one tenant per business unit. Per-tenant series limits enforced (1M active series each). S3 backend for long-term storage; 13-month retention.
- **Tempo** for traces. S3-backed; 30 days. Trace lookup by ID (fast). For trace search by attribute, exemplars from metrics link to representative traces.
- **Loki** for logs. S3-backed; 14 days hot, 90 days cold (compacted via Loki's compactor). Label cardinality strictly controlled: `service`, `namespace`, `level`, `cluster`. Everything else stays in the log body.
- **Pyroscope** for profiles. Continuous CPU + heap from Go services. 14 days. Profiles are tiny.

Choice points:
- *LGTM stack* over Datadog. Self-hosted is cheaper at this scale (~150 engineers, billions of metrics samples/day). Worth the operational overhead. Run a 2–3 engineer "platform observability" team to own it.
- *S3 everywhere* for storage. Cross-region replication via S3 features; data lasts longer than the compute.

**Recording rules and alerts**

- Recording rules in Mimir for the standard `job:metric:rate5m` patterns, plus SLO-specific `slo:service:error_ratio:Xm` rules (Phase 13).
- Alerts defined as YAML in a Git repo. Applied via CI to Mimir's ruler.
- Burn-rate alerts per service for the four major SLOs (availability, latency, freshness, success). Per-tenant routing labels (`team=platform-api`).
- A "dead-man" alert that always fires, watched by an external service (Cronitor), pages if our alerting system is down.

Choice points:
- *Alerts in Git*, not the UI. PR review for alert changes. Same as code.

**Dashboards**

- Dashboards as code (Grafonnet) in the same repo as alerts. CI lints them, CD applies via the Grafana provisioning API.
- Per-service: RED dashboard, USE dashboard, SLO dashboard. Generated from a service template — adding a new service means committing a `service.libsonnet` entry, not building dashboards by hand.
- Cross-cutting dashboards: per-team SLO compliance, per-tenant cost (active series, ingested log GB).
- Annotations from Argo CD deploys overlay on every dashboard's time axis — every spike answers "did we deploy then?"

**Alert routing**

- Alertmanager (or Grafana's unified alerting). Routing tree: by service label → team's PagerDuty service; by severity → page vs. Slack.
- Mute windows for known-noisy maintenance windows.
- Weekly Slack digest of all paged alerts and their resolutions, reviewed by each team's SRE counterpart.

### 15.3 The Operational Realities

- **The page-able stack components**: Mimir ingesters, Tempo distributors, Loki ingesters, OTel Collector gateway pods. They have their own SLOs. The platform team is oncall for them.
- **Cost monitoring**: a dashboard breaks down ingested bytes per service per signal. Outliers visible to their team. A monthly report goes to engineering leadership.
- **Cardinality**: a daily report ranks the top-30 metrics by series count, by team. Teams own their cardinality budgets; egregious metrics get tickets.
- **Sampling tuning**: tail-sampling policies reviewed quarterly. Error rate per service changes; sampling thresholds change with it.
- **Schema discipline**: a CI lint on producer code enforces metric naming (`_total`, `_seconds`, `_bytes`), log field names (`trace_id`, `service`), and span attribute names (semantic conventions).
- **Disaster drills**: quarterly, the platform team simulates Mimir loss and verifies fallback paths (local Prom for short-term, external dead-man for paging).

### 15.4 Why This Architecture

The decisions that shaped it:

1. **OpenTelemetry everywhere on the producer side.** Vendor-agnostic, three pillars unified, semantic conventions automatic.
2. **Self-host LGTM** at this scale. Datadog/New Relic bills would be 5–10× the engineering cost of running Mimir/Tempo/Loki. Past ~$1M/yr vendor spend, self-host pays.
3. **Agent + gateway** collector topology. Buys tail sampling, centralized redaction, multi-region routing, all without producer code changes.
4. **Burn-rate SLO alerts** over threshold alerts. Honest signal, lower noise, faster on real incidents.
5. **Everything as code** — dashboards, alerts, runbooks. Reviewed, versioned, automated. UI edits are auto-reverted.
6. **Per-team cardinality and cost budgets.** Without per-team accountability, the shared system gets abused.

None of these are right in the abstract. They're right *for this scale and team shape*. The right answer for 10 engineers is "Grafana Cloud + OpenTelemetry SDKs," skip the self-hosted backend entirely. The right answer for 1500 engineers is more like Netflix's Atlas / custom Honeycomb / multi-region everything. The framework is the same; the choices change.

For comparison, the data pipeline architecture in Phase 14 of [DATA_ENGINEERING_STUDY_GUIDE.md](DATA_ENGINEERING_STUDY_GUIDE.md) has the same shape: many sources, a routing tier, multiple backends per signal type, dashboards over the top. The same mental model applies.

---

## Mastery Checklist

You're solid on observability when you can, without looking anything up:

- Explain monitoring vs. observability and the cardinality argument behind the distinction.
- Pick the right pillar (metric / log / trace / event / profile) for a given question.
- Name the four Prometheus metric types and pick the right one for a new use case.
- Read and write PromQL: `rate`, `sum by`, `histogram_quantile`, `topk`, `offset`.
- Explain why `rate(sum(...))` is wrong and `sum(rate(...))` is right.
- Diagnose and fix a cardinality explosion: identify offender, drop relabel, fix at producer.
- Set up Prometheus, write recording rules, federate to a global Prom or `remote_write` to Mimir.
- Explain head vs. tail sampling and when to use each.
- Bootstrap OpenTelemetry in any major language and emit traces, metrics, and logs with shared resource attributes.
- Configure an OTel Collector pipeline with receivers, processors, exporters.
- Write structured logs with `trace_id`, `span_id`, stable fields, levels used honestly.
- Articulate the SLI / SLO / SLA / error-budget terms without using them interchangeably.
- Pick the right SLI for a service, the right SLO target, and defend both.
- Compute multi-window burn-rate alerts in PromQL and explain the windows.
- Write a useful runbook from scratch.
- Apply RED to a request-driven service and USE to its resources.
- Distinguish symptom-based and cause-based alerts and prefer the former.
- Build a RED dashboard, an SLO dashboard, a USE dashboard.
- Define dashboards and alerts as code, in a repo, reviewed by CI.
- Choose between Prometheus self-host, Mimir, VictoriaMetrics, and a vendor at a given scale, and justify it.
- Choose between Loki and Elastic for logs, and Tempo vs. Jaeger vs. Honeycomb for traces.
- Estimate the cost of an instrumentation change before merging it.
- Design an end-to-end observability stack for a 100-engineer org from scratch, defending each component.

---

## Recommended Reading Path

The canon, in roughly the order to read it:

1. **[Google SRE Book, Ch. 6 "Monitoring Distributed Systems"](https://sre.google/sre-book/monitoring-distributed-systems/)** — the foundations. The Four Golden Signals are from here.
2. **[Google SRE Workbook, Ch. 2 "Implementing SLOs"](https://sre.google/workbook/implementing-slos/)** and **[Ch. 5 "Alerting on SLOs"](https://sre.google/workbook/alerting-on-slos/)** — the math for SLOs and burn-rate alerts. Re-read until the formulas are intuitive.
3. **[Distributed Systems Observability — Cindy Sridharan](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/)** — the 2018 free O'Reilly book that defined the modern frame.
4. **[Observability Engineering — Majors, Fong-Jones, Miranda](https://www.oreilly.com/library/view/observability-engineering/9781492076438/)** — the Honeycomb-flavored event-centric view. The critique of the three pillars lives here.
5. **[Prometheus: Up and Running — Brian Brazil](https://www.oreilly.com/library/view/prometheus-up/9781492034131/)** — the deep reference for Prometheus, exposition, PromQL, exporters.
6. **[The OpenTelemetry docs](https://opentelemetry.io/docs/)** — the spec is a reference, not a tutorial; read the concepts pages cover to cover.
7. **[Brendan Gregg, Systems Performance, 2nd ed.](https://www.brendangregg.com/systems-performance-2nd-edition-book.html)** — for USE, flame graphs, and the systems side of observability.
8. **[Honeycomb blog](https://www.honeycomb.io/blog)** and **[Charity Majors's writing](https://charity.wtf/)** — opinionated, sharp, frequently updated. Read them to develop taste.
9. **[Grafana Labs blog](https://grafana.com/blog/)** — practical, current, vendor-honest about its own products.
10. **[Increment Magazine on On-Call](https://increment.com/on-call/)** — the human side.

Talks worth watching:
- **"Performance Matters"** — Emery Berger, Strange Loop 2019.
- **"Observability: The Hard Parts"** — Cindy Sridharan.
- **"The Hard Truths of Observability"** — Charity Majors.
- **"Stop Using Histograms"** — Björn Rabenstein, on quantiles and aggregation pitfalls.

The discipline isn't a finite body of knowledge. The fundamentals (cardinality, the data model, sampling, SLOs) are stable; the tools shift every couple of years. Internalize the fundamentals, keep tabs on the tooling churn, and you'll stay current.

---

*The bar to clear: someone wakes you up at 3 AM. You open one dashboard, see the symptom, click through to the trace, find the bad span, open the log line via shared `trace_id`, and have the root cause inside 15 minutes. If your stack does that for the kinds of failures you actually have, it's working. If it doesn't, find the missing piece and add it.*

**Adjacent guides in this repo:** [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) (the failure modes you're observing), [Kubernetes](k8s/KUBERNETES_STUDY_GUIDE.md) (where the collectors run), [Enterprise APIs](ENTERPRISE_API_STUDY_GUIDE.md) (request IDs and RED metrics at the API layer), and [eBPF](EBPF_STUDY_GUIDE.md) (zero-instrumentation telemetry).

# Caddy Study Guide

A depth-first guide to Caddy for engineers who run web services in production. Assumes you understand HTTP, DNS, and TLS at a conceptual level (the [Networking Fundamentals](NETWORKING_FUNDAMENTALS.md) and [Cryptography](CRYPTO_FUNDAMENTALS.md) guides cover those). Each part builds on the previous. Parts 1–11 are the fundamentals; Parts 12–13 are the comparison and applied recipes.

> *Caddy's thesis is that HTTPS should be the default, not the achievement. Every other design decision — the Caddyfile, the JSON API, the module system — follows from that.*

Primary references: the [Caddy documentation](https://caddyserver.com/docs/) (genuinely good — the [Caddyfile concepts](https://caddyserver.com/docs/caddyfile/concepts) and [reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) pages especially), the [JSON config structure reference](https://caddyserver.com/docs/json/), the [caddy community forum](https://caddy.community/) (where the maintainers actually answer), and the [Caddy source](https://github.com/caddyserver/caddy) (small enough to read).

---

## Table of Contents

- [Part 1 — Foundations & Mental Model](#part-1--foundations--mental-model)
- [Part 2 — Installation](#part-2--installation)
- [Part 3 — The Caddyfile](#part-3--the-caddyfile)
- [Part 4 — Automatic HTTPS](#part-4--automatic-https)
- [Part 5 — Reverse Proxy](#part-5--reverse-proxy)
- [Part 6 — Static File Serving](#part-6--static-file-serving)
- [Part 7 — Request Handling](#part-7--request-handling)
- [Part 8 — Authentication & Access Control](#part-8--authentication--access-control)
- [Part 9 — The JSON Config & Admin API](#part-9--the-json-config--admin-api)
- [Part 10 — Logging & Observability](#part-10--logging--observability)
- [Part 11 — Production Operations](#part-11--production-operations)
- [Part 12 — Comparison to Alternatives](#part-12--comparison-to-alternatives)
- [Part 13 — Recipes & End-to-End Walkthrough](#part-13--recipes--end-to-end-walkthrough)

---

## Part 1 — Foundations & Mental Model

### 1.1 What Caddy Is

Caddy is an open-source, extensible web server written in Go. It was created by Matt Holt in 2015, and its defining feature — then and now — is **automatic HTTPS**. Hand Caddy a domain name and it obtains a TLS certificate from Let's Encrypt (or ZeroSSL), configures the TLS listener, redirects HTTP to HTTPS, and renews the certificate before it expires. You don't write a single line of TLS configuration.

That automatic-HTTPS-by-default stance is what separates Caddy from Nginx, Apache, HAProxy, and Traefik. All of them *can* do ACME certificates — with plugins, sidecars, or cron jobs — but none of them do it out of the box with zero configuration. Caddy does.

Caddy is currently on **version 2** (a full rewrite from Caddy v1). Everything in this guide refers to Caddy v2.

References: [Caddy documentation home](https://caddyserver.com/docs/), [Why Caddy](https://caddyserver.com/docs/getting-started), [Caddy GitHub repository](https://github.com/caddyserver/caddy).

### 1.2 The Architecture

Caddy is a single static binary with no runtime dependencies. Internally, it is organized around a **module system**: every meaningful behavior — serving files, proxying requests, issuing certificates, writing logs — is a Caddy module. The standard distribution ships with a rich set of built-in modules; additional modules are compiled in at build time via `xcaddy` (Part 2).

The key architectural layers:

```
┌─────────────────────────────────────────┐
│              Caddyfile / JSON           │  ← configuration input
├─────────────────────────────────────────┤
│           Config Adapters               │  ← Caddyfile → JSON translation
├─────────────────────────────────────────┤
│           Core (App Modules)            │  ← http, tls, pki, logging, ...
│  ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │  HTTP    │ │   TLS    │ │  PKI   │  │
│  │  Server  │ │  Module  │ │ Module │  │
│  └──────────┘ └──────────┘ └────────┘  │
├─────────────────────────────────────────┤
│          Handler Chain (middleware)      │  ← reverse_proxy, file_server, ...
├─────────────────────────────────────────┤
│          Matchers                        │  ← host, path, method, header, ...
└─────────────────────────────────────────┘
```

**Config adapters** translate human-friendly formats (the Caddyfile) into Caddy's native JSON config. Caddy's internal truth is always JSON; the Caddyfile is syntactic sugar. This is important — anything the Caddyfile can do, the JSON can do, but the JSON can do things the Caddyfile cannot express (Part 9).

**App modules** are top-level subsystems. The `http` app handles listeners, routing, and middleware. The `tls` app handles certificate management. The `pki` app runs Caddy's internal CA for local development.

**Handlers** are the HTTP middleware chain: each request flows through an ordered list of handlers (encode, headers, reverse_proxy, file_server, etc.). Handlers execute in a specific, documented order — not the order you write them in the Caddyfile.

**Matchers** decide which requests a handler applies to. Path matchers, host matchers, header matchers, method matchers — these are the conditional logic of Caddy's routing.

References: [Caddy architecture](https://caddyserver.com/docs/architecture), [Caddy modules](https://caddyserver.com/docs/modules/).

### 1.3 The Two Configuration Modes

Caddy has two distinct configuration interfaces:

1. **The Caddyfile** — a human-readable, domain-specific config language. This is what most people use for most setups. It is concise, readable, and handles 90% of use cases.

2. **The JSON API** — Caddy's native configuration format. The Caddyfile is *adapted* (compiled) into JSON before Caddy uses it. The JSON API is more verbose but supports the full feature set, enables dynamic reconfiguration via HTTP, and is what you use for programmatic control.

```
 Caddyfile          JSON
┌──────────┐    ┌──────────────┐
│ Human    │───►│ Config       │───► Caddy runtime
│ writes   │    │ adapter      │
└──────────┘    └──────────────┘
                       ▲
                       │
              ┌────────┴──────┐
              │ Admin API     │◄─── Automation / scripts
              │ POST /config/ │
              └───────────────┘
```

For day-to-day work, use the Caddyfile. For automation, dynamic config, or advanced routing that the Caddyfile can't express, use the JSON API directly.

References: [Caddyfile concepts](https://caddyserver.com/docs/caddyfile/concepts), [JSON config structure](https://caddyserver.com/docs/json/), [API reference](https://caddyserver.com/docs/api).

### 1.4 Where Caddy Fits in 2026

Caddy's sweet spots:

- **Simple to moderately complex reverse proxy setups** — the automatic HTTPS and clean config make it dramatically less work than Nginx + certbot + cron for 1–50 upstream services.
- **Local development with HTTPS** — Caddy's internal CA issues locally-trusted certificates instantly. No more `mkcert` or self-signed cert warnings.
- **API gateways and microservices** — Caddy's reverse proxy has health checks, load balancing, header manipulation, and circuit breaking.
- **Static sites** — `file_server` with compression, SPA fallback, and browse mode is zero-effort.
- **Edge/small deployments** — a single binary with no dependencies is ideal for VMs, containers, and embedded devices (like a Raspberry Pi).

Where Caddy is **not** the best choice:

- **Extreme scale (100k+ req/s sustained)** — Nginx and Envoy are more battle-tested at this tier, though Caddy handles far more traffic than most services ever need.
- **Complex L4/L7 mesh routing** — Envoy and HAProxy have deeper L4 capabilities. Caddy is primarily an L7 server.
- **Deep ecosystem of community modules** — Nginx's third-party module ecosystem is larger (decades of head start). Caddy's is growing but narrower.
- **Legacy compatibility** — if your team has a decade of Nginx config, the migration cost may not be justified unless the HTTPS automation or config simplicity solves a real pain point.

### 1.5 Caddy vs. Nginx — The Mental Model Shift

If you're coming from Nginx, the biggest adjustments:

| Concept | Nginx | Caddy |
|---------|-------|-------|
| Config format | Custom DSL with `server` blocks, `location` blocks | Caddyfile with site blocks, or native JSON |
| TLS certificates | Manual (certbot, cron renewal) | Automatic — just use a domain name |
| Reload | `nginx -s reload` (graceful) | `caddy reload` or POST to admin API (zero-downtime) |
| Directive order | Order in file matters | Caddy has a fixed [directive order](https://caddyserver.com/docs/caddyfile/directives#directive-order); file order mostly doesn't matter |
| Regex routing | Heavy use of `location ~` regex | Matchers with explicit `path_regexp`; most routing is prefix/exact |
| Worker model | Multi-process, event-driven per worker | Single process, goroutines (Go's concurrency model) |
| Extend | C modules compiled in, or dynamic modules | Go modules compiled in via `xcaddy`, or via JSON plugins |

The directive-order point trips up Nginx users the most. In Nginx, directive placement determines execution order. In Caddy, the [directive order](https://caddyserver.com/docs/caddyfile/directives#directive-order) is predefined — `redir` always runs before `rewrite`, `rewrite` before `reverse_proxy`, `reverse_proxy` before `file_server`, regardless of where you put them in the Caddyfile. You can override this with the `order` global option or the `route` directive, but the default order is designed to do the right thing for the vast majority of configurations.

---

## Part 2 — Installation

### 2.1 Package Managers

**Debian/Ubuntu:**

```bash
# Install the Caddy apt repository
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

sudo apt update
sudo apt install caddy
```

This installs Caddy as a systemd service. The service file, default Caddyfile (`/etc/caddy/Caddyfile`), and data directories are set up automatically.

**Fedora/RHEL/CentOS:**

```bash
dnf install 'dnf-command(copr)'
dnf copr enable @caddy/caddy
dnf install caddy
```

**macOS (Homebrew):**

```bash
brew install caddy
```

**Arch Linux:**

```bash
pacman -S caddy
```

**Windows (Scoop or Chocolatey):**

```powershell
scoop install caddy    # or: choco install caddy
```

References: [Install Caddy](https://caddyserver.com/docs/install).

### 2.2 Static Binary

Caddy is a single binary with no runtime dependencies. Download it directly:

```bash
# Download the latest release for your platform
curl -o caddy "https://caddyserver.com/api/download?os=linux&arch=amd64"
chmod +x caddy
sudo mv caddy /usr/local/bin/

# Verify
caddy version
```

The [Caddy download page](https://caddyserver.com/download) lets you select your OS, architecture, and optional modules — it builds a custom binary on the fly.

### 2.3 Docker

The official Docker image is `caddy`:

```yaml
# docker-compose.yml
services:
  caddy:
    image: caddy:2                          # always pin to major version
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"                       # HTTP/3 (QUIC)
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile    # your config
      - caddy_data:/data                    # TLS certificates and ACME state
      - caddy_config:/config                # autosaved JSON config

volumes:
  caddy_data:                               # CRITICAL: persist this volume
  caddy_config:
```

The `/data` volume is essential — it stores TLS certificates, ACME account keys, and OCSP staples. Losing this volume means re-requesting all certificates on next start, which can hit Let's Encrypt rate limits.

References: [Caddy Docker image](https://hub.docker.com/_/caddy), [Docker-specific docs](https://caddyserver.com/docs/running#docker).

### 2.4 Building with Plugins — xcaddy

Caddy's standard binary includes the most common modules. For anything else — Cloudflare DNS challenge, rate limiting, caching, IP geolocation — you build a custom binary with `xcaddy`:

```bash
# Install xcaddy
go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest

# Build Caddy with the Cloudflare DNS module
xcaddy build --with github.com/caddy-dns/cloudflare

# Build with multiple modules
xcaddy build \
  --with github.com/caddy-dns/cloudflare \
  --with github.com/mholt/caddy-ratelimit \
  --with github.com/caddyserver/cache-handler
```

This compiles a new `caddy` binary in the current directory with the specified modules baked in. Replace the system binary with this custom build to use the extra modules.

**Docker with custom modules:**

```dockerfile
FROM caddy:2-builder AS builder

RUN xcaddy build \
  --with github.com/caddy-dns/cloudflare \
  --with github.com/mholt/caddy-ratelimit

FROM caddy:2

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

References: [xcaddy](https://github.com/caddyserver/xcaddy), [Caddy modules directory](https://caddyserver.com/download), [Build from source](https://caddyserver.com/docs/build).

### 2.5 First Run

After installation, verify Caddy works:

```bash
# Run a quick file server in the current directory
caddy file-server --listen :8080

# Or serve with a one-line Caddyfile from the command line
caddy respond --listen :8080 "Hello from Caddy"

# Run with a Caddyfile
caddy run                     # foreground (Ctrl+C to stop)
caddy start                   # background daemon
caddy stop                    # stop the background daemon
caddy reload                  # reload config without downtime
```

`caddy run` vs `caddy start`: `run` stays in the foreground and is what systemd uses. `start` daemonizes. In production, always let your init system (systemd) manage the process — don't use `caddy start`.

References: [Command line usage](https://caddyserver.com/docs/command-line), [Getting started](https://caddyserver.com/docs/getting-started).

---

## Part 3 — The Caddyfile

The Caddyfile is Caddy's human-readable configuration format. It is not JSON, YAML, or TOML — it is its own format, optimized for the specific task of configuring a web server.

References: [Caddyfile docs](https://caddyserver.com/docs/caddyfile), [Caddyfile tutorial](https://caddyserver.com/docs/caddyfile-tutorial).

### 3.1 Site Blocks

The fundamental unit of the Caddyfile is the **site block** — a site address followed by directives in curly braces:

```caddyfile
# Single site
example.com {
    respond "Hello, world!"
}

# Multiple sites on the same config
example.com {
    reverse_proxy localhost:8080
}

blog.example.com {
    root * /var/www/blog
    file_server
}

# Multiple addresses for the same config
example.com, www.example.com {
    reverse_proxy localhost:8080
}
```

The site address determines what Caddy does with HTTPS:

| Address | HTTPS behavior |
|---------|---------------|
| `example.com` | Automatic HTTPS — obtains a public certificate |
| `localhost` | Automatic HTTPS — issues a locally-trusted certificate via Caddy's internal CA |
| `:8080` | No HTTPS — just a port, no hostname to get a certificate for |
| `http://example.com` | No HTTPS — you explicitly said HTTP |
| `https://example.com` | HTTPS — same as bare domain |
| `*.example.com` | Wildcard HTTPS — requires a DNS challenge (Part 4) |

References: [Caddyfile addresses](https://caddyserver.com/docs/caddyfile/concepts#addresses).

### 3.2 Directives

Directives are the verbs of the Caddyfile. Each one configures a specific behavior:

```caddyfile
example.com {
    root * /var/www/html             # set the site root
    encode gzip zstd                 # enable compression
    file_server                      # serve static files
    log {                            # configure access logging
        output file /var/log/caddy/access.log
    }
}
```

The most commonly used directives:

| Directive | Purpose |
|-----------|---------|
| `reverse_proxy` | Proxy requests to backend services |
| `file_server` | Serve static files from disk |
| `root` | Set the root directory for the site |
| `encode` | Enable compression (gzip, zstd) |
| `header` | Add, set, or remove response headers |
| `redir` | Issue HTTP redirects |
| `rewrite` | Internally rewrite the URI (client doesn't see it) |
| `respond` | Return a static response (useful for health checks) |
| `tls` | Override automatic TLS settings |
| `log` | Configure access logging |
| `basicauth` / `forward_auth` | Authentication |
| `handle` / `handle_path` | Group directives for specific routes |
| `import` | Include a snippet or file |

**Directive order matters — but not the way you think.** Caddy has a predefined [directive order](https://caddyserver.com/docs/caddyfile/directives#directive-order) that controls execution regardless of where you write them in the file. This is the single most common source of confusion for new Caddy users. If you need explicit control over execution order, use the `route` directive (Section 3.6).

References: [Directives list](https://caddyserver.com/docs/caddyfile/directives), [Directive order](https://caddyserver.com/docs/caddyfile/directives#directive-order).

### 3.3 Matchers

Matchers control *which requests* a directive applies to. Without a matcher, a directive applies to all requests.

```caddyfile
example.com {
    # No matcher — applies to all requests
    encode gzip

    # Path matcher (shorthand) — only requests starting with /api/
    reverse_proxy /api/* localhost:3000

    # Named matcher — reusable, more expressive
    @websockets {
        header Connection *Upgrade*
        header Upgrade    websocket
    }
    reverse_proxy @websockets localhost:3001

    # Named matcher with multiple conditions (AND logic)
    @post-api {
        method POST
        path   /api/*
    }
    reverse_proxy @post-api localhost:3002

    # Negate a matcher
    @not-static {
        not path /static/*
    }
    reverse_proxy @not-static localhost:8080
}
```

Matcher types:

| Matcher | Syntax | Example |
|---------|--------|---------|
| Path | `path /foo/*` | Prefix, suffix (`*.html`), or exact (`/foo`) |
| Path (regex) | `path_regexp pattern` | `path_regexp \.(?:jpg\|png\|gif)$` |
| Method | `method GET POST` | HTTP method(s) |
| Header | `header Field value` | Match on request header |
| Query | `query key=value` | Match on query parameter |
| Remote IP | `remote_ip 192.168.1.0/24` | Client IP range |
| Protocol | `protocol https` | `http`, `https`, `grpc` |
| Expression | `expression {http.request.uri}.contains("/foo")` | CEL expression |
| Not | `not { ... }` | Negate any matcher |

Within a named matcher block, conditions are ANDed. To OR conditions, use multiple matchers or a CEL expression.

References: [Request matchers](https://caddyserver.com/docs/caddyfile/matchers).

### 3.4 Placeholders

Placeholders are Caddy's variable system. They use `{curly.brace.notation}` and are available anywhere in the Caddyfile:

```caddyfile
example.com {
    header X-Request-Id {http.request.uuid}

    log {
        output file /var/log/caddy/{args[0]}.log
    }

    respond "Host: {http.request.host}, Path: {http.request.uri.path}"
}
```

Common placeholders:

| Placeholder | Value |
|-------------|-------|
| `{http.request.host}` | Request hostname |
| `{http.request.uri}` | Full URI (path + query) |
| `{http.request.uri.path}` | Just the path |
| `{http.request.uri.query}` | Just the query string |
| `{http.request.method}` | HTTP method |
| `{http.request.header.X-Name}` | Value of a request header |
| `{http.request.remote.host}` | Client IP address |
| `{http.request.uuid}` | Unique request ID |
| `{http.response.header.Name}` | Value of a response header |
| `{env.VAR_NAME}` | Environment variable |
| `{args[N]}` | Positional argument from `import` |

Shorthand forms exist for common placeholders — `{host}` for `{http.request.host}`, `{path}` for `{http.request.uri.path}`, `{uri}` for `{http.request.uri}`, `{method}` for `{http.request.method}`, `{remote_host}` for `{http.request.remote.host}`.

References: [Placeholders](https://caddyserver.com/docs/caddyfile/concepts#placeholders), [Full placeholder list](https://caddyserver.com/docs/json/apps/http/#docs).

### 3.5 Snippets and Imports

Snippets let you define reusable blocks. `import` includes them:

```caddyfile
# Define a snippet (top level, outside any site block)
(common-headers) {
    header {
        X-Content-Type-Options  nosniff
        X-Frame-Options         DENY
        Referrer-Policy         strict-origin-when-cross-origin
        -Server                               # remove the Server header
    }
}

(logging) {
    log {
        output file /var/log/caddy/{args[0]}.log
        format json
    }
}

# Use snippets in site blocks
example.com {
    import common-headers
    import logging example.com               # {args[0]} = "example.com"
    reverse_proxy localhost:8080
}

api.example.com {
    import common-headers
    import logging api.example.com
    reverse_proxy localhost:3000
}
```

`import` can also include external files:

```caddyfile
# Import a single file
import /etc/caddy/sites/example.conf

# Import all files matching a glob
import /etc/caddy/sites/*.conf
```

This is how you organize large configurations — one file per site, all imported from a main Caddyfile.

References: [Snippets](https://caddyserver.com/docs/caddyfile/concepts#snippets), [import directive](https://caddyserver.com/docs/caddyfile/directives/import).

### 3.6 Global Options and the Route Directive

The **global options block** appears at the very top of the Caddyfile (before any site blocks) and configures Caddy-wide settings:

```caddyfile
{
    # TLS email for ACME account registration
    email admin@example.com

    # Use the Let's Encrypt staging CA (for testing — avoids rate limits)
    acme_ca https://acme-staging-v02.api.letsencrypt.org/directory

    # Change the admin API listen address (default: localhost:2019)
    admin localhost:2019

    # Set default SNI for TLS handshakes
    default_sni example.com

    # Change directive execution order
    order rate_limit before reverse_proxy

    # Enable debug logging
    debug
}

example.com {
    reverse_proxy localhost:8080
}
```

The **`route` directive** forces directives inside it to execute in the order written, overriding Caddy's default directive order:

```caddyfile
example.com {
    route {
        # These execute top-to-bottom, not in Caddy's default order
        rewrite /old-path /new-path
        header X-Rewritten true
        reverse_proxy localhost:8080
    }
}
```

Use `route` when the default directive order doesn't do what you need. In practice, you rarely need it — the defaults are well-designed.

References: [Global options](https://caddyserver.com/docs/caddyfile/options), [route directive](https://caddyserver.com/docs/caddyfile/directives/route).

### 3.7 handle vs. handle_path

`handle` and `handle_path` are how you do route-specific configuration — Caddy's equivalent of Nginx's `location` blocks:

```caddyfile
example.com {
    # handle: match on the path, but DON'T strip it
    handle /api/* {
        reverse_proxy localhost:3000       # backend sees /api/users
    }

    # handle_path: match on the path AND strip the prefix
    handle_path /static/* {
        root * /var/www/static
        file_server                        # /static/img/logo.png → /img/logo.png
    }

    # Fallback handle — matches everything not matched above
    handle {
        reverse_proxy localhost:8080
    }
}
```

`handle` blocks are mutually exclusive — only the first matching one runs. This is different from directives at the site-block level, where multiple directives can apply to the same request. Think of `handle` as a router with exclusive routes.

References: [handle](https://caddyserver.com/docs/caddyfile/directives/handle), [handle_path](https://caddyserver.com/docs/caddyfile/directives/handle_path).

### 3.8 Environment Variables

Use `{env.VAR_NAME}` to reference environment variables anywhere in the Caddyfile:

```caddyfile
{env.DOMAIN} {
    reverse_proxy localhost:{env.BACKEND_PORT}
    tls {env.TLS_EMAIL}
}
```

This is essential for containerized deployments where config varies per environment. Caddy resolves environment variables at config load time, not at request time.

References: [Environment variables in the Caddyfile](https://caddyserver.com/docs/caddyfile/concepts#environment-variables).

---

## Part 4 — Automatic HTTPS

Automatic HTTPS is Caddy's signature feature and its entire reason for existing, so it's worth understanding the *problem* it solves before the mechanism, because the mechanism is incomprehensible without it. The problem is trust: HTTPS works because your browser ships with a list of trusted **Certificate Authorities (CAs)**, and a website proves its identity by presenting a certificate *signed* by one of them — a chain of cryptographic vouching that says "a CA the browser trusts verified that whoever holds this certificate controls `example.com`" (the [Cryptography Fundamentals guide](CRYPTO_FUNDAMENTALS.md) covers the signing math). For two decades, obtaining that signed certificate was a manual, annual, error-prone chore: generate a key, craft a signing request, pay a CA, prove ownership through some out-of-band process, install the result by hand, and remember to do it all again before it expired — and a forgotten renewal meant a site-down, browser-warning outage, one of the most common self-inflicted production incidents there was.

**ACME (Automatic Certificate Management Environment)** is the protocol that automated this entirely, and Let's Encrypt is the free CA that pioneered it. The insight is that domain ownership can be proven *automatically* by a challenge: the CA says "if you really control `example.com`, then put this specific token where only the domain's owner could put it," and the server does so, and the CA checks. That's it — no human, no payment, no waiting. Caddy's radical move was to build a full ACME client into the web server itself and *turn it on by default*, so that the act of naming a domain in your config triggers the whole certificate lifecycle automatically. This is why Caddy's "HTTPS should be the default" thesis is not a slogan but an architecture: the server treats a valid certificate as a thing it acquires and maintains on its own, the way it acquires a listening socket, rather than a thing you configure. Understanding how that automation works — and when to override it — is essential for running Caddy in production, and the rest of this part is that mechanism.

References: [Automatic HTTPS overview](https://caddyserver.com/docs/automatic-https), [HTTPS quick-start](https://caddyserver.com/docs/quick-starts/https).

### 4.1 How It Works

When Caddy sees a site address with a qualifying hostname (not bare IP, not `localhost`, not a port-only address), it:

1. **Creates an ACME account** with Let's Encrypt (or ZeroSSL) using the `email` from global options (or generates one).
2. **Requests a certificate** for the domain using the HTTP-01 or TLS-ALPN-01 ACME challenge.
3. **Configures the TLS listener** with the obtained certificate.
4. **Redirects HTTP → HTTPS** by automatically adding an HTTP listener on port 80 that 301-redirects to the HTTPS version.
5. **Renews the certificate** automatically before it expires (Let's Encrypt certificates last 90 days; Caddy renews at roughly 2/3 of the lifetime).
6. **Staples OCSP responses** for improved TLS handshake performance.

All of this happens with zero TLS configuration in the Caddyfile — just use a domain name:

```caddyfile
example.com {
    respond "I have HTTPS!"
}
```

Caddy stores certificates, private keys, ACME account data, and OCSP staples in its **data directory** (`~/.local/share/caddy` on Linux, or `/data` in the Docker image). Never delete this directory in production.

References: [ACME challenges](https://caddyserver.com/docs/automatic-https#acme-challenges), [Certificate management](https://caddyserver.com/docs/caddyfile/directives/tls).

### 4.2 ACME Challenge Types

Caddy supports three ACME challenge types for proving domain ownership:

**HTTP-01 challenge** (default): The ACME server asks Caddy to serve a specific token at `http://yourdomain/.well-known/acme-challenge/<token>`. Requires port 80 to be publicly reachable. This is the most common and simplest challenge type.

**TLS-ALPN-01 challenge** (default fallback): The ACME server connects to port 443 and verifies a special self-signed certificate with a specific ALPN protocol. Requires port 443 to be publicly reachable. Caddy tries this automatically if HTTP-01 fails.

**DNS-01 challenge** (manual/plugin): Caddy creates a DNS TXT record (`_acme-challenge.yourdomain`) to prove ownership. Does **not** require ports 80/443 to be reachable — essential for wildcard certificates and internal services behind firewalls. Requires a DNS provider plugin:

```caddyfile
# Requires: xcaddy build --with github.com/caddy-dns/cloudflare
*.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
    reverse_proxy localhost:8080
}
```

DNS provider plugins exist for Cloudflare, Route 53, Google Cloud DNS, DigitalOcean, Hetzner, and many others. See the [caddy-dns GitHub organization](https://github.com/caddy-dns) for the full list.

References: [ACME challenges](https://caddyserver.com/docs/automatic-https#acme-challenges), [DNS challenge modules](https://github.com/caddy-dns).

### 4.3 Wildcard Certificates

Wildcard certificates (`*.example.com`) require the DNS-01 challenge because the HTTP-01 and TLS-ALPN-01 challenges can only prove ownership of a specific hostname, not a wildcard:

```caddyfile
*.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }

    @app host app.example.com
    handle @app {
        reverse_proxy localhost:3000
    }

    @api host api.example.com
    handle @api {
        reverse_proxy localhost:4000
    }

    handle {
        respond "Unknown subdomain" 404
    }
}
```

A wildcard address `*.example.com` does **not** match the bare domain `example.com`. If you need both, add both:

```caddyfile
example.com, *.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
    # ...
}
```

### 4.4 Internal CA — Local Development with HTTPS

For `localhost` and other non-public hostnames, Caddy runs a built-in CA (based on its `pki` module) that issues locally-trusted certificates:

```caddyfile
localhost {
    respond "HTTPS on localhost, no warnings!"
}

# Any non-public hostname also gets an internal certificate
myapp.local {
    reverse_proxy localhost:3000
}
```

On first run, Caddy generates a root CA certificate and installs it into the system trust store (may prompt for `sudo`). After that, browsers trust Caddy's locally-issued certificates without warnings.

This eliminates the need for `mkcert`, self-signed certificates, or `NODE_TLS_REJECT_UNAUTHORIZED=0` hacks in development.

References: [Local HTTPS](https://caddyserver.com/docs/automatic-https#local-https).

### 4.5 On-Demand TLS

On-demand TLS obtains certificates at the moment of the first TLS handshake, rather than at config load time. This is for SaaS platforms and multi-tenant apps where you don't know all the hostnames in advance:

```caddyfile
{
    on_demand_tls {
        # REQUIRED: an endpoint that returns 200 if the domain is allowed
        ask http://localhost:5000/check-domain
        # Optional: rate limits
        burst 5
        interval 2m
    }
}

https:// {
    tls {
        on_demand
    }
    reverse_proxy localhost:8080
}
```

The `ask` endpoint is a critical security gate — without it, anyone could point their domain at your server and Caddy would obtain certificates for it, exhausting your ACME rate limits. The endpoint receives `GET /check-domain?domain=example.com` and must return 200 to allow issuance.

References: [On-demand TLS](https://caddyserver.com/docs/automatic-https#on-demand-tls), [tls directive](https://caddyserver.com/docs/caddyfile/directives/tls).

### 4.6 Using Your Own Certificates

If you have certificates from another CA (corporate PKI, purchased certificates), you can use them instead of ACME:

```caddyfile
example.com {
    tls /path/to/cert.pem /path/to/key.pem
    reverse_proxy localhost:8080
}
```

Caddy will still handle OCSP stapling if possible, but won't manage renewal — that's on you.

### 4.7 Disabling Automatic HTTPS

Sometimes you need plain HTTP — behind a load balancer that terminates TLS, or in a development environment:

```caddyfile
# Option 1: use http:// prefix
http://example.com {
    reverse_proxy localhost:8080
}

# Option 2: use a port-only address (no host = no TLS)
:8080 {
    reverse_proxy localhost:3000
}

# Option 3: global option to disable
{
    auto_https off
}
```

Common scenario: Caddy behind a cloud load balancer (ALB, Cloud Load Balancing) that handles TLS. The LB talks to Caddy over plain HTTP on an internal network:

```caddyfile
{
    auto_https off
}

:80 {
    reverse_proxy localhost:8080
}
```

References: [Disable automatic HTTPS](https://caddyserver.com/docs/automatic-https#disable).

---

## Part 5 — Reverse Proxy

The reverse proxy is Caddy's most-used directive, and it's worth being clear about what a reverse proxy *is* and why it sits at the center of modern deployments, because the config below only makes sense once the role is clear. A **reverse proxy** is a server that accepts client requests and forwards them to one or more backend servers (the *upstreams*), then relays the responses back — sitting in front of your actual application as its public face. The "reverse" distinguishes it from a forward proxy: a forward proxy fronts the *clients* (hiding who's making requests, as a corporate web filter does), while a reverse proxy fronts the *servers* (hiding and protecting the backends, presenting one address for many). This is the standard shape of a real deployment: your application runs as a plain HTTP service on `localhost:8080` knowing nothing about TLS, public addresses, or load balancing, and Caddy sits in front terminating HTTPS (Part 4), routing by hostname and path, and spreading traffic across instances — so the app stays simple and every cross-cutting concern lives in one place.

From that role, everything the directive does follows naturally and is worth seeing as a coherent set rather than a feature list. Because the proxy is the single entry point, it's the right place to **terminate TLS** (decrypt once at the edge, talk plain HTTP to backends on a trusted network) and to **load-balance** (when one app instance isn't enough, the proxy spreads requests across many — which immediately raises the need for **health checks** so it stops sending traffic to a dead instance, and **retries** so a transient failure on one backend transparently tries another). Because every request and response flows through it, it's also the natural place for **header manipulation** (adding the `X-Forwarded-For` and `X-Forwarded-Proto` headers that tell the backend the *original* client's IP and scheme, since the backend now only sees the proxy). The mental model to carry into the config: the reverse proxy is the seam between the public internet and your private application, and its job is to make one simple backend look like a production-grade public service.

References: [reverse_proxy directive](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

### 5.1 Basic Proxying

```caddyfile
# Simple: proxy all requests to a single backend
example.com {
    reverse_proxy localhost:8080
}

# Path-scoped: only proxy /api/* to the backend
example.com {
    reverse_proxy /api/* localhost:3000

    # Everything else: serve static files
    root * /var/www/html
    file_server
}

# Strip the path prefix before proxying
example.com {
    handle_path /api/* {
        reverse_proxy localhost:3000        # /api/users → /users on the backend
    }
}
```

Caddy automatically sets the standard proxy headers: `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Real-Ip`. You don't need to configure these unless your backend expects something non-standard.

### 5.2 Multiple Upstreams and Load Balancing

```caddyfile
example.com {
    reverse_proxy localhost:8001 localhost:8002 localhost:8003 {
        # Load balancing policy (default: random)
        lb_policy round_robin
    }
}
```

Available load balancing policies:

| Policy | Behavior |
|--------|----------|
| `random` (default) | Random selection — surprisingly effective for most workloads |
| `round_robin` | Cycle through upstreams in order |
| `least_conn` | Send to the upstream with fewest active connections |
| `first` | Always use the first available upstream (active-passive) |
| `ip_hash` | Hash the client IP for sticky sessions |
| `uri_hash` | Hash the URI for cache-friendly routing |
| `cookie` | Sticky sessions via a cookie |
| `header` | Hash a specific request header |
| `random_choose 2` | Pick 2 random upstreams, send to the one with fewer connections (power-of-two-choices) |

```caddyfile
# Sticky sessions with a cookie
example.com {
    reverse_proxy localhost:8001 localhost:8002 {
        lb_policy cookie
        lb_cookie_name MY_STICKY
    }
}
```

References: [Load balancing](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#load-balancing).

### 5.3 Health Checks

Caddy can actively and passively monitor upstream health:

```caddyfile
example.com {
    reverse_proxy localhost:8001 localhost:8002 localhost:8003 {
        # Active health checks — Caddy periodically hits the backend
        health_uri     /healthz
        health_port    8081                     # optional: use a different port
        health_interval 10s
        health_timeout  5s
        health_status   200                     # expected status code
        health_body     "ok"                    # optional: expected body substring

        # Passive health checks — mark unhealthy based on real traffic
        fail_duration   30s                     # how long to remember failures
        max_fails       3                       # failures before marking unhealthy
        unhealthy_status 500 502 503            # which status codes count as failures
        unhealthy_latency 5s                    # responses slower than this count as failures
    }
}
```

Active and passive health checks are independent and complementary. Active checks detect backends that are fully down (not responding). Passive checks detect backends that are responding but producing errors or high latency.

References: [Health checks](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#health-checks).

### 5.4 Header Manipulation

Control headers sent to the upstream and returned to the client:

```caddyfile
example.com {
    reverse_proxy localhost:8080 {
        # Headers sent TO the upstream (request headers)
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote_host}
        header_up -Accept-Encoding              # remove a header (prefix with -)

        # Headers sent BACK to the client (response headers)
        header_down -Server                     # hide the backend's Server header
        header_down X-Powered-By "Caddy"
        header_down Strict-Transport-Security "max-age=31536000"
    }
}
```

`header_up` modifies the request going to the upstream. `header_down` modifies the response coming back to the client. Use `-HeaderName` to delete a header.

### 5.5 WebSockets

Caddy proxies WebSocket connections automatically — no special configuration needed. When it sees a request with `Connection: Upgrade` and `Upgrade: websocket`, it upgrades the connection:

```caddyfile
example.com {
    reverse_proxy localhost:8080    # WebSocket connections just work
}

# If you need WebSocket-specific routing:
example.com {
    @ws {
        header Connection *Upgrade*
        header Upgrade    websocket
    }
    reverse_proxy @ws localhost:9000    # WS backend
    reverse_proxy localhost:8080         # HTTP backend
}
```

### 5.6 Timeouts and Buffering

```caddyfile
example.com {
    reverse_proxy localhost:8080 {
        # Timeouts
        transport http {
            dial_timeout     5s         # time to establish connection
            response_header_timeout 30s # time to receive response headers
            read_timeout     300s       # total read timeout
            write_timeout    300s       # total write timeout
            keepalive        30s        # keep-alive duration
            keepalive_idle_conns 64     # max idle connections per upstream
        }

        # Buffering
        flush_interval -1               # -1 = flush immediately (streaming)
    }
}
```

`flush_interval -1` is critical for Server-Sent Events (SSE) and streaming responses. Without it, Caddy may buffer the response and the client won't see events in real time.

References: [HTTP transport](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#the-http-transport).

### 5.7 TLS to Backends

If your upstream expects HTTPS:

```caddyfile
example.com {
    reverse_proxy https://backend.internal:8443 {
        transport http {
            tls                          # enable TLS to upstream
            tls_server_name backend.internal
            tls_trusted_ca_certs /path/to/ca.pem   # if using internal CA
        }
    }
}
```

### 5.8 Dynamic Upstreams

For service discovery, Caddy supports dynamic upstreams via DNS:

```caddyfile
example.com {
    reverse_proxy {
        dynamic a backend.service.consul 8080 {
            refresh 30s            # re-resolve DNS every 30s
        }
    }
}
```

`dynamic a` resolves A/AAAA records. `dynamic srv` resolves SRV records, which is common in Consul, Kubernetes headless services, and other service discovery systems.

References: [Dynamic upstreams](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#dynamic-upstreams).

---

## Part 6 — Static File Serving

### 6.1 Basic File Server

```caddyfile
# Serve the current directory on port 8080 (quick one-liner)
:8080 {
    file_server
}

# Serve from a specific directory
example.com {
    root * /var/www/html
    file_server
}

# Enable directory browsing
example.com {
    root * /var/www/files
    file_server browse
}
```

`file_server browse` renders a navigable directory listing when no index file is found. This is useful for file repositories, documentation hosting, and internal tools.

References: [file_server directive](https://caddyserver.com/docs/caddyfile/directives/file_server), [root directive](https://caddyserver.com/docs/caddyfile/directives/root).

### 6.2 Compression

Enable transparent compression with the `encode` directive:

```caddyfile
example.com {
    root * /var/www/html
    encode zstd gzip                # try zstd first, fall back to gzip
    file_server
}
```

Caddy negotiates compression via the `Accept-Encoding` request header. Zstandard (`zstd`) has better compression ratios and speed than gzip, but gzip has wider client support. Listing both in preference order gives you the best of both.

Caddy also serves pre-compressed files if they exist. If the client accepts gzip and `index.html.gz` exists alongside `index.html`, Caddy serves the pre-compressed version without compressing on the fly. This is useful for build pipelines that pre-compress assets.

References: [encode directive](https://caddyserver.com/docs/caddyfile/directives/encode).

### 6.3 SPA Fallback (try_files)

Single-page applications need all non-file requests to serve `index.html` so the client-side router can handle the URL:

```caddyfile
example.com {
    root * /var/www/app

    # If the requested file exists, serve it. Otherwise, serve index.html.
    try_files {path} /index.html

    file_server
}

# With an API backend — serve static files for the SPA, proxy /api to the backend
example.com {
    root * /var/www/app
    encode gzip

    handle /api/* {
        reverse_proxy localhost:3000
    }

    handle {
        try_files {path} /index.html
        file_server
    }
}
```

`try_files` internally rewrites the URI to the first file that exists on disk. It does not issue a redirect — the client sees the original URL.

References: [try_files directive](https://caddyserver.com/docs/caddyfile/directives/try_files).

### 6.4 Custom Error Pages

```caddyfile
example.com {
    root * /var/www/html
    file_server

    handle_errors {
        @404 expression {err.status_code} == 404
        handle @404 {
            rewrite * /404.html
            file_server
        }

        @500 expression {err.status_code} >= 500
        handle @500 {
            respond "Something went wrong" 500
        }
    }
}
```

`handle_errors` is a special handler that catches errors from other directives. Inside it, you have access to `{err.status_code}` and `{err.message}`.

References: [handle_errors directive](https://caddyserver.com/docs/caddyfile/directives/handle_errors).

---

## Part 7 — Request Handling

Beyond reverse proxying and file serving, Caddy has a rich set of directives for manipulating requests and responses.

### 7.1 Response Headers

The `header` directive adds, sets, removes, or defers response headers:

```caddyfile
example.com {
    # Set security headers
    header {
        Strict-Transport-Security  "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options     nosniff
        X-Frame-Options            DENY
        Content-Security-Policy    "default-src 'self'"
        Referrer-Policy            strict-origin-when-cross-origin
        Permissions-Policy         "camera=(), microphone=(), geolocation=()"
        -Server                    # delete the Server header
    }

    reverse_proxy localhost:8080
}

# Conditional headers — only on certain paths
example.com {
    header /api/* {
        Access-Control-Allow-Origin   *
        Access-Control-Allow-Methods  "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers  "Content-Type, Authorization"
    }

    reverse_proxy localhost:3000
}
```

Header operations:

| Syntax | Behavior |
|--------|----------|
| `Name "value"` | Set the header (replaces any existing value) |
| `+Name "value"` | Add the header (appends; doesn't replace) |
| `-Name` | Delete the header |
| `?Name "value"` | Set only if the header doesn't already exist (default) |
| `>Name "value"` | Defer — set on the way out, after other handlers run |

References: [header directive](https://caddyserver.com/docs/caddyfile/directives/header).

### 7.2 Redirects

```caddyfile
example.com {
    # Redirect a single path
    redir /old-page /new-page

    # Redirect with a specific status code (default is 302)
    redir /old-blog /blog permanent       # 301 Moved Permanently
    redir /temp-page /other temporary     # 307 Temporary Redirect

    # Redirect with placeholders
    redir /users/{http.request.uri.path.1} /people/{http.request.uri.path.1} permanent

    # Redirect all www to non-www
    @www host www.example.com
    redir @www https://example.com{uri} permanent
}

# Common pattern: redirect www to non-www as a separate site block
www.example.com {
    redir https://example.com{uri} permanent
}

example.com {
    reverse_proxy localhost:8080
}
```

References: [redir directive](https://caddyserver.com/docs/caddyfile/directives/redir).

### 7.3 Rewrites

Rewrites change the request URI internally — the client never sees the change:

```caddyfile
example.com {
    # Rewrite a specific path
    rewrite /about-us /about

    # Rewrite to add a trailing slash (for directory-like URLs)
    @no-trailing-slash {
        path_regexp ^/[^.]*[^/]$
        not path /api/*
    }
    rewrite @no-trailing-slash {path}/

    # Strip a prefix (use handle_path instead for reverse_proxy — it's cleaner)
    rewrite /old-api/* /api/{http.request.uri.path.1}

    reverse_proxy localhost:8080
}
```

The difference between `redir` and `rewrite`: `redir` sends a response to the client telling it to go elsewhere (301/302/307). `rewrite` silently changes the URI before passing it to the next handler — the client never knows.

References: [rewrite directive](https://caddyserver.com/docs/caddyfile/directives/rewrite).

### 7.4 URI Manipulation

The `uri` directive provides more targeted URI manipulation than `rewrite`:

```caddyfile
example.com {
    # Strip a path prefix
    uri strip_prefix /api/v1

    # Strip a path suffix
    uri strip_suffix .html

    # Replace within the URI
    uri replace /old /new

    # Regular expression replacement
    uri path_regexp \.php$ .html
}
```

References: [uri directive](https://caddyserver.com/docs/caddyfile/directives/uri).

### 7.5 Static Responses

The `respond` directive returns a static response without contacting a backend:

```caddyfile
example.com {
    # Health check endpoint
    respond /healthz 200 {
        body "ok"
    }

    # Block specific paths
    respond /wp-admin/* "Not found" 404
    respond /.env "Not found" 404

    # Maintenance mode
    respond * "We'll be back soon" 503 {
        header Content-Type text/plain
    }

    reverse_proxy localhost:8080
}
```

`respond` is useful for health checks, blocking exploit scanners, maintenance pages, and any response that doesn't need a backend.

References: [respond directive](https://caddyserver.com/docs/caddyfile/directives/respond).

### 7.6 Templates

Caddy can render simple server-side templates:

```caddyfile
example.com {
    root * /var/www/html
    templates
    file_server
}
```

With `templates` enabled, `.html` files can use Go template syntax:

```html
<!-- /var/www/html/index.html -->
<html>
<body>
  <p>Server time: {{now | date "2006-01-02 15:04:05"}}</p>
  <p>Your IP: {{.Req.RemoteAddr}}</p>
  <p>Host: {{.Req.Host}}</p>

  <!-- Include another file -->
  {{include "/partials/header.html"}}

  <!-- Markdown rendering -->
  {{markdown "## Hello from Markdown"}}

  <!-- HTTP subrequest (basic SSI) -->
  {{httpInclude "/api/status"}}
</body>
</html>
```

Templates are useful for simple dynamic pages, server-side includes, and adding dynamic fragments to otherwise static sites. For anything complex, use a proper application backend.

References: [templates directive](https://caddyserver.com/docs/caddyfile/directives/templates).

### 7.7 Request Body Limits

Limit the size of request bodies to prevent abuse:

```caddyfile
example.com {
    request_body {
        max_size 10MB
    }
    reverse_proxy localhost:8080
}

# Different limits for different paths
example.com {
    @uploads path /upload/*
    request_body @uploads {
        max_size 100MB
    }

    request_body {
        max_size 1MB
    }

    reverse_proxy localhost:8080
}
```

When a request exceeds the limit, Caddy returns a `413 Request Entity Too Large` response.

References: [request_body directive](https://caddyserver.com/docs/caddyfile/directives/request_body).

---

## Part 8 — Authentication & Access Control

### 8.1 Basic Authentication

`basic_auth` protects paths with HTTP Basic Authentication:

```caddyfile
example.com {
    basic_auth /admin/* {
        # Passwords are bcrypt hashes — generate with: caddy hash-password
        alice $2a$14$Zkx19XLiW6VYouLRR3bKze0n5IS.KZHM4dc8UhgO8RNScfIuiEXxy
        bob   $2a$14$Zkx19XLiW6VYouLRR3bKze0n5IS.KZHM4dc8UhgO8RNScfIuiEXxy
    }

    reverse_proxy localhost:8080
}
```

Generate password hashes on the command line:

```bash
caddy hash-password
# Enter password, get bcrypt hash
```

Basic auth sends credentials in base64 (not encrypted) on every request, so it is **only safe over HTTPS** — which Caddy provides by default. It's fine for simple admin panels, internal tools, and staging environments. For anything user-facing, use `forward_auth` (below).

References: [basic_auth directive](https://caddyserver.com/docs/caddyfile/directives/basic_auth).

### 8.2 Forward Authentication

`forward_auth` delegates authentication to an external service. Caddy sends the request to the auth service; if it returns 2xx, the request proceeds. If it returns anything else, Caddy forwards that response to the client (typically a redirect to a login page).

This is how you integrate Caddy with **OAuth2 Proxy**, **Authelia**, **Authentik**, **Keycloak**, or any auth middleware:

```caddyfile
# With Authelia
example.com {
    forward_auth authelia:9091 {
        uri /api/authz/forward-auth
        copy_headers Remote-User Remote-Groups Remote-Email
    }

    reverse_proxy localhost:8080
}

# With OAuth2 Proxy
example.com {
    forward_auth oauth2-proxy:4180 {
        uri /oauth2/auth
        copy_headers {
            X-Auth-Request-User
            X-Auth-Request-Email
            X-Auth-Request-Groups
        }
    }

    reverse_proxy localhost:8080
}
```

The flow:

```
Client → Caddy → forward_auth service
                     ├── 200 → proceed to reverse_proxy (copies specified headers)
                     └── 401 → return auth service response to client (login redirect)
```

`copy_headers` passes identity information from the auth service to your backend. Your backend receives `Remote-User`, `Remote-Email`, etc. as request headers, so it knows who authenticated.

References: [forward_auth directive](https://caddyserver.com/docs/caddyfile/directives/forward_auth).

### 8.3 IP Filtering

Restrict access by client IP:

```caddyfile
example.com {
    @blocked remote_ip 10.0.0.0/8 192.168.0.0/16
    respond @blocked "Forbidden" 403

    # Or allowlist — only certain IPs can access
    @allowed not remote_ip 203.0.113.0/24 198.51.100.0/24
    respond @allowed "Forbidden" 403

    reverse_proxy localhost:8080
}

# Restrict admin paths to internal network
example.com {
    @internal-admin {
        path /admin/*
        remote_ip 10.0.0.0/8
    }
    @external-admin {
        path /admin/*
        not remote_ip 10.0.0.0/8
    }
    respond @external-admin "Forbidden" 403

    reverse_proxy localhost:8080
}
```

If Caddy is behind a reverse proxy or load balancer, `remote_ip` will see the proxy's IP, not the client's. Use the `trusted_proxies` global option to tell Caddy to trust `X-Forwarded-For` from specific sources:

```caddyfile
{
    servers {
        trusted_proxies static 10.0.0.0/8
    }
}
```

References: [remote_ip matcher](https://caddyserver.com/docs/caddyfile/matchers#remote-ip), [trusted_proxies](https://caddyserver.com/docs/caddyfile/options#trusted-proxies).

---

## Part 9 — The JSON Config & Admin API

The Caddyfile is syntactic sugar. Caddy's actual configuration language is **JSON**. Understanding the JSON structure and the admin API unlocks dynamic reconfiguration, programmatic control, and features that the Caddyfile can't express.

References: [JSON structure](https://caddyserver.com/docs/json/), [API docs](https://caddyserver.com/docs/api).

### 9.1 The JSON Config Structure

Every Caddyfile compiles to a JSON document. You can see the translation:

```bash
# Convert a Caddyfile to JSON
caddy adapt --config Caddyfile --pretty
```

The top-level JSON structure:

```json
{
  "admin": {
    "listen": "localhost:2019"
  },
  "apps": {
    "http": {
      "servers": {
        "srv0": {
          "listen": [":443"],
          "routes": [
            {
              "match": [{"host": ["example.com"]}],
              "handle": [
                {
                  "handler": "reverse_proxy",
                  "upstreams": [{"dial": "localhost:8080"}]
                }
              ]
            }
          ]
        }
      }
    },
    "tls": {
      "automation": {
        "policies": [
          {
            "subjects": ["example.com"]
          }
        ]
      }
    }
  }
}
```

The hierarchy: `apps` → `http` → `servers` → `routes` → `match` + `handle`. Each route has matchers (which requests) and handlers (what to do). This is the same model the Caddyfile uses; the Caddyfile just presents it more concisely.

### 9.2 The Admin API

Caddy exposes an admin API on `localhost:2019` by default. This API lets you inspect and modify the running configuration without restarts:

```bash
# Get the current config
curl localhost:2019/config/

# Get a specific part of the config
curl localhost:2019/config/apps/http/servers/srv0/routes

# Replace the entire config
curl -X POST localhost:2019/load \
  -H "Content-Type: application/json" \
  -d @config.json

# Update a specific config path (PATCH-like)
curl -X PATCH localhost:2019/config/apps/http/servers/srv0/routes \
  -H "Content-Type: application/json" \
  -d '[{"match":[{"host":["new.example.com"]}],"handle":[{"handler":"reverse_proxy","upstreams":[{"dial":"localhost:9090"}]}]}]'

# Delete a specific config path
curl -X DELETE localhost:2019/config/apps/http/servers/srv0/routes/1

# Reload from a Caddyfile via the API
curl -X POST localhost:2019/load \
  -H "Content-Type: text/caddyfile" \
  --data-binary @Caddyfile
```

Key endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/config/` | GET | Retrieve current config |
| `/config/...` | POST | Set a config value at a path |
| `/config/...` | PUT | Replace a config value |
| `/config/...` | PATCH | Append to an array at a path |
| `/config/...` | DELETE | Remove a config value |
| `/load` | POST | Replace the entire config (JSON or Caddyfile) |
| `/stop` | POST | Gracefully stop the server |
| `/reverse_proxy/upstreams` | GET | List upstream health status |

### 9.3 Dynamic Reconfiguration

The admin API enables patterns that static config files can't:

**Add a new site at runtime:**

```bash
# Add a new route to the existing server
curl -X PATCH localhost:2019/config/apps/http/servers/srv0/routes \
  -H "Content-Type: application/json" \
  -d '[{
    "match": [{"host": ["newsite.example.com"]}],
    "handle": [{
      "handler": "reverse_proxy",
      "upstreams": [{"dial": "localhost:5000"}]
    }]
  }]'
```

Caddy will automatically obtain a TLS certificate for the new domain.

**Multi-tenant SaaS:** The admin API + on-demand TLS (Part 4) is how SaaS platforms dynamically add customer domains. Your control plane calls the admin API to add routes; on-demand TLS handles certificates.

**Blue-green deployments:** Update upstream addresses via the API to switch traffic between deployment targets with zero downtime.

### 9.4 When to Use JSON vs. Caddyfile

| Use case | Recommendation |
|----------|---------------|
| Static sites, reverse proxy, typical web serving | Caddyfile — simpler, more readable |
| Dynamic route management (SaaS, API gateways) | JSON API — programmatic control |
| Complex routing logic the Caddyfile can't express | JSON — full feature access |
| GitOps / version-controlled config | Caddyfile — diffs are readable |
| Automation / CI pipeline generating configs | JSON — easier to template programmatically |

You can mix: use a Caddyfile for the base config, then modify at runtime via the JSON API. The API also accepts Caddyfile format via `POST /load` with `Content-Type: text/caddyfile`.

### 9.5 Securing the Admin API

The admin API is powerful — anyone with access can modify your server config. Secure it:

```caddyfile
{
    # Default: only listen on localhost (safe)
    admin localhost:2019

    # Disable the admin API entirely
    admin off

    # Listen on a specific interface with access control
    admin 0.0.0.0:2019 {
        origins localhost 10.0.0.0/8
    }
}
```

In production, either keep the default `localhost:2019` (requires SSH/exec access to the host) or disable it entirely if you don't need dynamic reconfiguration. Never expose the admin API to the public internet.

References: [Admin API](https://caddyserver.com/docs/api), [Admin options](https://caddyserver.com/docs/caddyfile/options#admin).

---

## Part 10 — Logging & Observability

### 10.1 Access Logs

Caddy's `log` directive configures structured access logs per site:

```caddyfile
example.com {
    log {
        output file /var/log/caddy/access.log {
            roll_size 100MiB          # rotate at 100MB
            roll_keep 5               # keep 5 rotated files
            roll_keep_for 720h        # delete rotated files after 30 days
        }
        format json                   # structured JSON (default is console)
        level INFO
    }

    reverse_proxy localhost:8080
}
```

Log output destinations:

| Output | Syntax |
|--------|--------|
| File | `output file /path/to/access.log { ... }` |
| Stdout | `output stdout` |
| Stderr | `output stderr` |
| Discard | `output discard` |
| Network (syslog) | `output net tcp://log-collector:514` |

The default format is `console` (human-readable). `json` produces structured JSON — one object per line, ready for ingestion by Loki, Elasticsearch, Datadog, or any log aggregator:

```json
{
  "level": "info",
  "ts": 1716892800.123,
  "logger": "http.log.access.log0",
  "msg": "handled request",
  "request": {
    "remote_ip": "203.0.113.50",
    "remote_port": "49812",
    "client_ip": "203.0.113.50",
    "proto": "HTTP/2.0",
    "method": "GET",
    "host": "example.com",
    "uri": "/api/users",
    "headers": { "User-Agent": ["curl/8.0"] }
  },
  "bytes_read": 0,
  "user_id": "",
  "duration": 0.023,
  "size": 1234,
  "status": 200,
  "resp_headers": { "Content-Type": ["application/json"] }
}
```

References: [log directive](https://caddyserver.com/docs/caddyfile/directives/log), [Log output modules](https://caddyserver.com/docs/caddyfile/directives/log#output-modules).

### 10.2 Filtering and Sampling

Filter out noisy log entries:

```caddyfile
example.com {
    log {
        output file /var/log/caddy/access.log
        format filter {
            wrap json

            # Redact sensitive headers
            fields {
                request>headers>Authorization delete
                request>headers>Cookie        delete
            }
        }
    }

    reverse_proxy localhost:8080
}

# Skip logging for health check endpoints
example.com {
    @healthz path /healthz
    handle @healthz {
        skip_log                     # don't log these requests
        respond 200
    }

    log {
        output file /var/log/caddy/access.log
        format json
    }

    reverse_proxy localhost:8080
}
```

`skip_log` is invaluable for health check endpoints that would otherwise flood your logs with noise.

References: [Log filters](https://caddyserver.com/docs/caddyfile/directives/log#filter-modules).

### 10.3 Caddy Runtime Logs

Caddy's own runtime logs (startup, TLS events, errors) go to stderr by default. Control them with global options:

```caddyfile
{
    log {
        output file /var/log/caddy/caddy.log
        format json
        level WARN                   # only warnings and errors
    }

    # Enable debug logging (very verbose — use for troubleshooting only)
    debug
}
```

The `debug` global option sets all loggers to DEBUG level. This produces very detailed output including every TLS handshake, ACME challenge step, and config decision. Useful for troubleshooting but far too noisy for production.

### 10.4 Prometheus Metrics

Caddy exposes Prometheus-compatible metrics via the `metrics` directive:

```caddyfile
{
    servers {
        metrics
    }
}

# Expose metrics on a separate port (don't expose on the public interface)
:9180 {
    metrics /metrics
}

example.com {
    reverse_proxy localhost:8080
}
```

This exposes standard metrics at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `caddy_http_requests_total` | Counter | Total requests by server, handler |
| `caddy_http_request_duration_seconds` | Histogram | Request latency distribution |
| `caddy_http_response_size_bytes` | Histogram | Response body sizes |
| `caddy_http_request_size_bytes` | Histogram | Request body sizes |
| `caddy_http_requests_in_flight` | Gauge | Currently active requests |
| `caddy_reverse_proxy_upstreams_healthy` | Gauge | Number of healthy upstreams |

Scrape with Prometheus, feed to Grafana — the standard [Observability](OBSERVABILITY_STUDY_GUIDE.md) stack.

References: [Monitoring Caddy](https://caddyserver.com/docs/metrics), [metrics directive](https://caddyserver.com/docs/caddyfile/directives/metrics).

### 10.5 Tracing

Caddy supports distributed tracing via OpenTelemetry:

```caddyfile
{
    tracing {
        span caddy                    # root span name
    }
}

example.com {
    tracing                           # enable per-request tracing
    reverse_proxy localhost:8080
}
```

Set the OTLP exporter endpoint via environment variables:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
caddy run
```

Caddy will propagate trace context (`traceparent` / `tracestate` headers) through to backends, so you get end-to-end distributed traces across Caddy and your application services.

References: [Tracing](https://caddyserver.com/docs/caddyfile/directives/tracing).

---

## Part 11 — Production Operations

### 11.1 Running with systemd

The package manager installation sets up a systemd service automatically. If you installed from a binary, create the service file:

```ini
# /etc/systemd/system/caddy.service
[Unit]
Description=Caddy
Documentation=https://caddyserver.com/docs/
After=network.target network-online.target
Requires=network-online.target

[Service]
Type=notify
User=caddy
Group=caddy
ExecStart=/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
LimitNPROC=512
PrivateTmp=true
ProtectSystem=full
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```

Key points:

- **`Type=notify`** — Caddy tells systemd when it's ready to serve traffic (not just that the process started). This means `systemctl start caddy` blocks until Caddy is actually listening.
- **`CAP_NET_BIND_SERVICE`** — allows the `caddy` user to bind to ports 80 and 443 without root.
- **`ExecReload`** — `systemctl reload caddy` does a zero-downtime config reload, not a restart.
- **`LimitNOFILE`** — raise the file descriptor limit for high-connection workloads.

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now caddy

# Reload config (zero downtime)
sudo systemctl reload caddy

# Check status
sudo systemctl status caddy
sudo journalctl -u caddy --no-pager -f    # follow logs
```

References: [Running Caddy as a service](https://caddyserver.com/docs/running#linux-service), [systemd unit file](https://github.com/caddyserver/dist/blob/master/init/caddy.service).

### 11.2 Docker in Production

```yaml
# docker-compose.yml — production-ready
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    cap_add:
      - NET_BIND_SERVICE               # bind to 80/443 as non-root
    cap_drop:
      - ALL                            # drop everything else
    read_only: true                    # read-only filesystem
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"                  # HTTP/3 (QUIC)
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro   # config is read-only
      - caddy_data:/data               # certificates — MUST persist
      - caddy_config:/config           # autosaved config
      - /var/www:/var/www:ro           # static files (if serving)
    environment:
      - DOMAIN=example.com
    healthcheck:
      test: ["CMD", "caddy", "version"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  caddy_data:
    driver: local
  caddy_config:
    driver: local
```

The `/data` volume is the most critical — it stores TLS certificates, ACME account keys, and OCSP staples. Losing it means re-requesting all certificates, which can hit Let's Encrypt's rate limits (50 certificates per registered domain per week).

### 11.3 Kubernetes Ingress

Caddy can serve as a Kubernetes Ingress controller, though Traefik and Nginx ingress controllers have more mature Kubernetes integrations. Caddy's strength in Kubernetes is as a sidecar or internal reverse proxy.

**As a sidecar proxy:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: caddy
          image: caddy:2
          ports:
            - containerPort: 80
            - containerPort: 443
          volumeMounts:
            - name: caddy-config
              mountPath: /etc/caddy/Caddyfile
              subPath: Caddyfile
            - name: caddy-data
              mountPath: /data
        - name: app
          image: myapp:latest
          ports:
            - containerPort: 8080
      volumes:
        - name: caddy-config
          configMap:
            name: caddy-config
        - name: caddy-data
          persistentVolumeClaim:
            claimName: caddy-data
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: caddy-config
data:
  Caddyfile: |
    :80 {
      reverse_proxy localhost:8080
    }
```

For a full Kubernetes Ingress controller, see the [caddy-ingress-controller](https://github.com/caddyserver/ingress) project. It maps Kubernetes Ingress resources to Caddy configuration and handles TLS certificates automatically.

References: [Caddy Ingress Controller](https://github.com/caddyserver/ingress).

### 11.4 Certificate Storage and Persistence

Caddy stores all TLS-related state in its **data directory**:

| Platform | Default data directory |
|----------|----------------------|
| Linux | `$XDG_DATA_HOME/caddy` or `~/.local/share/caddy` |
| macOS | `~/Library/Application Support/Caddy` |
| Docker | `/data` |
| Windows | `%AppData%\Caddy` |

Contents:

```
data/
├── caddy/
│   ├── certificates/                # issued certificates and private keys
│   │   ├── acme-v02.api.letsencrypt.org-directory/
│   │   │   └── example.com/
│   │   │       ├── example.com.crt
│   │   │       └── example.com.key
│   │   └── local/                   # internal CA certificates
│   ├── acme/                        # ACME account data
│   ├── ocsp/                        # OCSP staple cache
│   └── pki/                         # internal CA root and intermediate
```

**Backup this directory.** If you lose it:
- All ACME accounts are lost (new accounts created, but old ones can't manage old certificates).
- All certificates must be re-requested (rate limit risk).
- The internal CA root key is lost (all locally-trusted certificates break).

For high-availability setups (multiple Caddy instances), use a shared storage backend. Caddy supports [storage modules](https://caddyserver.com/docs/json/storage/) for consul, redis, S3, and databases, so multiple instances can share certificate state.

References: [Data directory](https://caddyserver.com/docs/conventions#data-directory), [Storage modules](https://caddyserver.com/docs/json/storage/).

### 11.5 Graceful Reloads and Zero-Downtime

```bash
# Reload config (zero downtime — existing connections are not dropped)
caddy reload --config /etc/caddy/Caddyfile

# Or via the admin API
curl -X POST localhost:2019/load \
  -H "Content-Type: text/caddyfile" \
  --data-binary @/etc/caddy/Caddyfile
```

Caddy's reload is truly zero-downtime: it starts new listeners with the new config, drains existing connections on the old config, and transitions seamlessly. There's no brief window where connections are refused (unlike Nginx's graceful reload, which can drop connections during heavy load in rare cases).

**Validating before reload:**

```bash
# Check config for errors without applying it
caddy adapt --config /etc/caddy/Caddyfile --validate
```

Always validate in CI before deploying config changes to production.

### 11.6 Performance Tuning

Caddy performs well out of the box. The main tuning knobs:

**File descriptor limits:** High-traffic servers need more file descriptors. Each connection uses at least one FD.

```bash
# Check current limits
ulimit -n

# Set in systemd (already done in the service file above)
# LimitNOFILE=1048576
```

**HTTP/3 (QUIC):** Caddy enables HTTP/3 by default when listening on HTTPS. Ensure your firewall allows UDP on port 443:

```bash
# Verify HTTP/3 is working
curl --http3 https://example.com
```

**Connection timeouts:** Tune for your workload:

```caddyfile
{
    servers {
        timeouts {
            read_body   30s       # time to read the request body
            read_header 10s       # time to read request headers
            write       60s       # time to write the response
            idle        120s      # keep-alive idle timeout
        }
    }
}
```

**Thread/goroutine limits:** Caddy uses Go's goroutine model — thousands of concurrent connections are handled by a modest number of OS threads. You rarely need to tune this. If you do:

```bash
# Go runtime: set max OS threads (default: 10,000)
export GOMAXPROCS=0   # 0 = use all available CPUs (default)
```

References: [Server options](https://caddyserver.com/docs/caddyfile/options#server-options).

### 11.7 Upgrading Caddy

```bash
# If installed via apt
sudo apt update && sudo apt upgrade caddy

# If using a static binary
# Download the new version and replace the binary
caddy upgrade                         # self-upgrade (downloads from caddyserver.com)
sudo systemctl restart caddy

# If using xcaddy (custom build)
xcaddy build --with github.com/caddy-dns/cloudflare   # rebuild with same modules
sudo mv caddy /usr/bin/caddy
sudo systemctl restart caddy
```

`caddy upgrade` is convenient but downloads the standard build (no custom modules). If you built with `xcaddy`, you must rebuild with the same module list.

References: [Upgrading Caddy](https://caddyserver.com/docs/command-line#caddy-upgrade).

---

## Part 12 — Comparison to Alternatives

### 12.1 Nginx

Nginx is the incumbent. Most engineers encounter it first, and most production deployments still run it. Here's an honest comparison:

**Where Caddy wins:**
- **Automatic HTTPS** — this alone eliminates an entire class of operational work (certbot, cron renewal, certificate debugging, mixed-content issues from forgetting the HTTP→HTTPS redirect).
- **Configuration simplicity** — a Caddy reverse proxy is 3 lines; the equivalent Nginx config is 15–20 lines with `proxy_set_header`, `ssl_certificate`, `ssl_certificate_key`, `listen 443 ssl`, and the HTTP→HTTPS redirect block.
- **Zero-downtime reloads** — truly seamless. Nginx's `reload` can briefly drop connections under very heavy load.
- **Single binary, no dependencies** — Nginx requires `libc`, OpenSSL, PCRE, and zlib. Caddy is one file.
- **Admin API** — dynamic reconfiguration without touching the filesystem.
- **HTTP/3** — built in and enabled by default. Nginx has experimental QUIC support (as of nginx-quic).

**Where Nginx wins:**
- **Raw performance at extreme scale** — Nginx's C-based event loop has lower per-connection overhead than Go's goroutine model. For 100k+ concurrent connections, Nginx is measurably faster. For 99% of workloads, you'll never notice the difference.
- **Third-party module ecosystem** — decades of community modules (Lua/OpenResty, ModSecurity WAF, GeoIP, PageSpeed, etc.). Caddy's module ecosystem is growing but smaller.
- **Organizational familiarity** — most teams already know Nginx. Migration has a real cost.
- **L4 proxying** — Nginx's stream module handles arbitrary TCP/UDP proxying. Caddy is primarily L7.
- **Documentation and Stack Overflow coverage** — Nginx has 15+ years of community knowledge. Caddy's docs are excellent but the community corpus is smaller.

**Configuration comparison — reverse proxy with HTTPS:**

```nginx
# Nginx: ~20 lines, plus certbot setup
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```caddyfile
# Caddy: 3 lines, HTTPS is automatic
example.com {
    reverse_proxy localhost:8080
}
```

References: [Nginx documentation](https://nginx.org/en/docs/).

### 12.2 Apache (httpd)

Apache is the original dominant web server. It pioneered virtual hosting and `.htaccess` per-directory config. In 2026, it's still widely deployed but losing share to Nginx and Caddy.

**Where Caddy wins:** automatic HTTPS, simpler config, single binary, better performance for reverse proxying (Apache's `mod_proxy` is functional but not its strength).

**Where Apache wins:** `.htaccess` files for shared hosting (per-directory config without server restarts), `mod_rewrite` regex power (arcane but extremely flexible), and legacy PHP integration (`mod_php` is still the simplest way to run PHP, though PHP-FPM behind Caddy or Nginx is better).

Apache is rarely the right choice for new projects in 2026 unless you're running shared hosting or have deep `mod_rewrite` rules that would be expensive to port.

References: [Apache documentation](https://httpd.apache.org/docs/current/).

### 12.3 Traefik

Traefik is the closest competitor to Caddy in philosophy: Go-based, automatic HTTPS, modern design. It's especially popular in Docker and Kubernetes environments.

**Where Caddy wins:**
- **Simpler configuration** — Traefik's config splits across static config (YAML/TOML) and dynamic config (labels, files, Consul, etc.), which adds cognitive overhead. Caddy's Caddyfile is one file.
- **Caddyfile readability** — Traefik's Docker label syntax (`traefik.http.routers.myapp.rule=Host(\`example.com\`)`) is functional but verbose and error-prone.
- **Performance** — Caddy benchmarks slightly faster than Traefik in most scenarios.

**Where Traefik wins:**
- **Docker-native service discovery** — Traefik auto-discovers containers via Docker labels. No config files needed. Caddy can do this with plugins, but Traefik does it natively.
- **Kubernetes IngressRoute CRD** — Traefik's Kubernetes integration is more mature, with custom CRDs for fine-grained routing.
- **Dashboard** — Traefik ships a web dashboard for inspecting routes, services, and middleware. Caddy has no built-in UI.
- **Middleware pipeline** — Traefik's middleware model (rate limiting, circuit breaking, retry, etc.) is richer out of the box.

**Choose Traefik** if you're heavily Docker/Kubernetes-native and want automatic service discovery from container labels. **Choose Caddy** if you want simpler config, better performance, or are running on VMs/bare metal.

References: [Traefik documentation](https://doc.traefik.io/traefik/).

### 12.4 HAProxy

HAProxy is the gold standard for L4/L7 load balancing and high-availability proxying.

**Where Caddy wins:** automatic HTTPS, simpler configuration for web serving use cases, static file serving (HAProxy doesn't serve files at all), and the admin API.

**Where HAProxy wins:** raw TCP/UDP proxying, connection-level load balancing, health checking sophistication, high-availability (active-passive clustering), and extreme-scale performance. HAProxy routinely handles millions of concurrent connections.

HAProxy is the right choice when you need a dedicated load balancer at scale. Caddy is the right choice when you need a web server that also does load balancing.

References: [HAProxy documentation](https://docs.haproxy.org/).

### 12.5 Envoy

Envoy is a high-performance L4/L7 proxy designed for service meshes and cloud-native architectures (Istio, Consul Connect, AWS App Mesh).

**Where Caddy wins:** operational simplicity (Envoy's YAML config is notoriously complex), automatic HTTPS, and file serving.

**Where Envoy wins:** L4 proxying, gRPC-native support, advanced observability (per-upstream metrics, distributed tracing), xDS API for dynamic configuration from a control plane, and service mesh integration.

Envoy is for platform teams building infrastructure. Caddy is for application teams serving traffic.

References: [Envoy documentation](https://www.envoyproxy.io/docs/envoy/latest/).

### 12.6 When NOT to Use Caddy

Be honest about when Caddy isn't the right tool:

- **You need a dedicated L4 load balancer** → HAProxy or Envoy.
- **You need WAF capabilities** → Nginx + ModSecurity, or a cloud WAF (Cloudflare, AWS WAF).
- **You need a service mesh data plane** → Envoy (it's what Istio and Consul use).
- **You need Docker label-based auto-discovery as a core feature** → Traefik.
- **You need to serve 100k+ concurrent connections with minimal resource usage** → Nginx (the performance gap only matters at this scale).
- **Your team already runs Nginx well and has no pain points** → the migration cost isn't free. Don't switch just because Caddy is newer.

---

## Part 13 — Recipes & End-to-End Walkthrough

### Recipe 1: Multi-Site Reverse Proxy with Security Headers

The most common Caddy setup — multiple sites, each proxying to a different backend, with shared security headers:

```caddyfile
# Shared security headers
(security-headers) {
    header {
        Strict-Transport-Security  "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options     nosniff
        X-Frame-Options            DENY
        Referrer-Policy            strict-origin-when-cross-origin
        Permissions-Policy         "camera=(), microphone=(), geolocation=()"
        -Server
    }
}

# Main application
app.example.com {
    import security-headers
    encode zstd gzip
    reverse_proxy localhost:3000
    log {
        output file /var/log/caddy/app.log
        format json
    }
}

# API
api.example.com {
    import security-headers
    header /api/* {
        Access-Control-Allow-Origin   "https://app.example.com"
        Access-Control-Allow-Methods  "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers  "Content-Type, Authorization"
    }
    reverse_proxy localhost:4000
    log {
        output file /var/log/caddy/api.log
        format json
    }
}

# Admin panel — restricted to internal network
admin.example.com {
    import security-headers
    @external not remote_ip 10.0.0.0/8
    respond @external "Forbidden" 403
    reverse_proxy localhost:5000
}
```

### Recipe 2: SPA + API Backend

A React/Vue/Svelte single-page application served from static files, with an API backend:

```caddyfile
example.com {
    encode zstd gzip

    # API requests go to the backend
    handle /api/* {
        reverse_proxy localhost:3000
    }

    # WebSocket endpoint
    handle /ws/* {
        reverse_proxy localhost:3000
    }

    # Everything else is the SPA
    handle {
        root * /var/www/app/dist
        try_files {path} /index.html
        file_server

        # Cache static assets aggressively (hashed filenames from build tools)
        @assets path /assets/*
        header @assets Cache-Control "public, max-age=31536000, immutable"

        # Don't cache index.html (it references the hashed assets)
        @html path /index.html
        header @html Cache-Control "no-cache, no-store, must-revalidate"
    }

    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

### Recipe 3: Wildcard Subdomains with Dynamic Routing

For multi-tenant SaaS where each tenant gets a subdomain:

```caddyfile
# Requires: xcaddy build --with github.com/caddy-dns/cloudflare
*.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }

    @app host app.example.com
    handle @app {
        reverse_proxy localhost:3000
    }

    @api host api.example.com
    handle @api {
        reverse_proxy localhost:4000
    }

    @docs host docs.example.com
    handle @docs {
        root * /var/www/docs
        file_server
    }

    # Catch-all for tenant subdomains — pass the subdomain to the backend
    handle {
        reverse_proxy localhost:5000 {
            header_up X-Tenant {labels.2}    # "foo" from "foo.example.com"
        }
    }
}
```

### Recipe 4: File Download Server with Authentication

An internal file repository with basic auth, directory browsing, and bandwidth-friendly settings:

```caddyfile
files.example.com {
    basic_auth {
        admin  $2a$14$Zkx19XLiW6VYouLRR3bKze0n5IS.KZHM4dc8UhgO8RNScfIuiEXxy
        devops $2a$14$Zkx19XLiW6VYouLRR3bKze0n5IS.KZHM4dc8UhgO8RNScfIuiEXxy
    }

    root * /srv/files
    file_server browse {
        hide .git .env *.key          # hide sensitive files from browsing
    }
    encode gzip

    log {
        output file /var/log/caddy/files.log
        format json
    }
}
```

### Recipe 5: Local Development with HTTPS

A development Caddyfile that gives you real HTTPS for local services:

```caddyfile
# Caddyfile.dev — run with: caddy run --config Caddyfile.dev
{
    # No need for ACME — Caddy uses its internal CA for these hostnames
}

myapp.localhost {
    reverse_proxy localhost:3000
}

api.localhost {
    reverse_proxy localhost:4000
}

# PHPMyAdmin or Adminer on a local port
db.localhost {
    reverse_proxy localhost:8081
}

# MinIO S3-compatible object storage
s3.localhost {
    reverse_proxy localhost:9000
}
```

Caddy issues locally-trusted certificates for all `*.localhost` domains. No browser warnings, no `curl -k`, no `NODE_TLS_REJECT_UNAUTHORIZED=0`.

### Recipe 6: Caddy as a Forward Proxy Behind Authelia

Full authentication stack with Authelia handling SSO:

```caddyfile
(authelia) {
    forward_auth authelia:9091 {
        uri /api/authz/forward-auth
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
}

# Authelia itself (no forward_auth loop)
auth.example.com {
    reverse_proxy authelia:9091
}

# Protected services
grafana.example.com {
    import authelia
    reverse_proxy grafana:3000
}

wiki.example.com {
    import authelia
    reverse_proxy wiki:3000
}

# Public site — no auth
example.com {
    root * /var/www/html
    file_server
}
```

### Recipe 7: Rate Limiting

Requires the `caddy-ratelimit` module:

```caddyfile
# Requires: xcaddy build --with github.com/mholt/caddy-ratelimit
{
    order rate_limit before reverse_proxy
}

api.example.com {
    # 100 requests per minute per client IP
    rate_limit {remote.ip} 100r/m

    reverse_proxy localhost:3000
}
```

### End-to-End Walkthrough: From Nothing to Multi-Service Production

This walkthrough takes a real scenario — an application with a frontend SPA, an API backend, a WebSocket service, and an admin panel — from a fresh server to a production Caddy deployment.

**Step 1: Install Caddy on a fresh Ubuntu server.**

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

Caddy is now running as a systemd service with a default welcome page.

**Step 2: Set up DNS.** Point four A records to your server's public IP:

```
app.example.com    → 203.0.113.10
api.example.com    → 203.0.113.10
ws.example.com     → 203.0.113.10
admin.example.com  → 203.0.113.10
```

**Step 3: Write the Caddyfile.** Start with a minimal config and iterate:

```caddyfile
# /etc/caddy/Caddyfile
{
    email ops@example.com                     # ACME account email
}

(security-headers) {
    header {
        Strict-Transport-Security  "max-age=31536000; includeSubDomains"
        X-Content-Type-Options     nosniff
        X-Frame-Options            DENY
        Referrer-Policy            strict-origin-when-cross-origin
        -Server
    }
}

(standard-log) {
    log {
        output file /var/log/caddy/{args[0]}.log {
            roll_size 50MiB
            roll_keep 5
        }
        format json
    }
}

# Frontend SPA
app.example.com {
    import security-headers
    import standard-log app

    encode zstd gzip
    root * /var/www/app/dist
    try_files {path} /index.html
    file_server

    @assets path /assets/*
    header @assets Cache-Control "public, max-age=31536000, immutable"
}

# API backend
api.example.com {
    import security-headers
    import standard-log api

    header {
        Access-Control-Allow-Origin   "https://app.example.com"
        Access-Control-Allow-Methods  "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers  "Content-Type, Authorization"
    }

    reverse_proxy localhost:3000 {
        health_uri  /healthz
        health_interval 15s
    }
}

# WebSocket service
ws.example.com {
    import standard-log ws

    reverse_proxy localhost:4000 {
        flush_interval -1              # streaming — flush immediately
    }
}

# Admin panel — restricted access
admin.example.com {
    import security-headers
    import standard-log admin

    @external not remote_ip 10.0.0.0/8 192.168.0.0/16
    respond @external "Forbidden" 403

    basic_auth {
        admin $2a$14$Zkx19XLiW6VYouLRR3bKze0n5IS.KZHM4dc8UhgO8RNScfIuiEXxy
    }

    reverse_proxy localhost:5000
}
```

**Step 4: Validate and reload.**

```bash
# Validate the config
caddy adapt --config /etc/caddy/Caddyfile --validate

# Reload (zero downtime)
sudo systemctl reload caddy
```

Caddy immediately starts obtaining TLS certificates for all four domains. Within seconds, all four sites are live with HTTPS, HTTP→HTTPS redirects, and HTTP/3.

**Step 5: Verify.**

```bash
# Check that HTTPS works
curl -I https://app.example.com
# Look for: HTTP/2 200, Strict-Transport-Security header

# Check HTTP→HTTPS redirect
curl -I http://app.example.com
# Look for: HTTP/1.1 301, Location: https://app.example.com/

# Check certificate details
openssl s_client -connect app.example.com:443 -servername app.example.com < /dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer

# Check admin panel is restricted
curl -I https://admin.example.com
# From outside the allowed IPs: 403 Forbidden
```

**Step 6: Monitor.** Add Prometheus metrics:

```caddyfile
{
    email ops@example.com
    servers {
        metrics
    }
}

# Metrics endpoint — separate port, not public
:9180 {
    metrics /metrics
}
```

Scrape `http://caddy-host:9180/metrics` from your Prometheus instance. You now have request rates, latency histograms, and upstream health in your [Observability](OBSERVABILITY_STUDY_GUIDE.md) stack.

**What you got with zero TLS configuration:**
- Valid certificates from Let's Encrypt for all four domains.
- Automatic renewal before expiry.
- HTTP→HTTPS redirects on all sites.
- HTTP/2 and HTTP/3 (QUIC) enabled by default.
- OCSP stapling for faster TLS handshakes.

In Nginx, this setup would require certbot installation, manual certificate paths in every server block, a cron job for renewal, separate SSL configuration, and an HTTP→HTTPS redirect block per domain. In Caddy, it's 70 lines with security headers, logging, and access control included.

---

## Where to Go Next

- **Read the official [Caddyfile concepts](https://caddyserver.com/docs/caddyfile/concepts) and [directive reference](https://caddyserver.com/docs/caddyfile/directives)** — short, current, and the answer to most "how do I express this?" questions; graduate to the [JSON structure reference](https://caddyserver.com/docs/json/) when the Caddyfile abstraction runs out.
- **Read the [automatic HTTPS page](https://caddyserver.com/docs/automatic-https)** in full — it documents the issuance, renewal, and fallback behavior that is Caddy's whole reason for existing, including the edge cases (rate limits, internal CAs, on-demand TLS).
- **Search the [community forum](https://caddy.community/)** before assuming a limitation — the maintainers answer there daily, and most "Caddy can't do X" beliefs are answered threads.
- **Migrate one real Nginx config** using Part 12's comparison as the map — nothing exposes the model difference (and the lines you no longer need) like porting a production server block.
- **Adjacent guides in this repo:** [Networking Fundamentals](NETWORKING_FUNDAMENTALS.md) (TLS/HTTP under the proxy), [Cryptography Fundamentals](CRYPTO_FUNDAMENTALS.md) (what the certificates mean), [Docker](DOCKER_STUDY_GUIDE.md) (Caddy as the container front door), and [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) (proxying long-lived connections).

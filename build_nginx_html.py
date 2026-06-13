#!/usr/bin/env python3
"""
Build an interactive, responsive, black-themed HTML study guide for Nginx.

Reuses the CSS + JS (incl. syntax highlighter, scroll-spy, search, quizzes,
theme toggle) from build_caddy_html.py. Content + quizzes + decision helper
are nginx-specific. Output is a single self-contained HTML file; no markdown
source is committed.
"""

import re
import html as _html
import markdown

from build_caddy_html import CSS, JS  # shared styling + behavior

OUT = "html/nginx-study-guide.html"

# --------------------------------------------------------------------------- #
# Content (authored here; not emitted as a standalone .md)
# --------------------------------------------------------------------------- #

NGINX_MD = r"""
# Nginx Study Guide

A depth-first guide to Nginx for engineers who run web services in production. Assumes you understand HTTP, DNS, and TLS at a conceptual level. Each part builds on the previous. Parts 1–13 are the fundamentals and operations; Part 14 is the honest comparison to alternatives; Part 15 is applied recipes and an end-to-end walkthrough.

> *Nginx is a small set of orthogonal primitives — contexts, directives, locations, variables — composed into almost any web-serving job. Master the primitives and the config language stops being a pile of snippets you copy from Stack Overflow.*

---

## Table of Contents

- [Part 1 — Foundations & Mental Model](#part-1--foundations--mental-model)
- [Part 2 — Installation](#part-2--installation)
- [Part 3 — Configuration Structure](#part-3--configuration-structure)
- [Part 4 — Server Blocks & Virtual Hosts](#part-4--server-blocks--virtual-hosts)
- [Part 5 — Location Matching](#part-5--location-matching)
- [Part 6 — Serving Static Content](#part-6--serving-static-content)
- [Part 7 — Reverse Proxy & Load Balancing](#part-7--reverse-proxy--load-balancing)
- [Part 8 — TLS & HTTPS](#part-8--tls--https)
- [Part 9 — Performance & Caching](#part-9--performance--caching)
- [Part 10 — Security & Access Control](#part-10--security--access-control)
- [Part 11 — Rewrites, Redirects & the Rewrite Engine](#part-11--rewrites-redirects--the-rewrite-engine)
- [Part 12 — Logging & Observability](#part-12--logging--observability)
- [Part 13 — Production Operations](#part-13--production-operations)
- [Part 14 — Comparison to Alternatives](#part-14--comparison-to-alternatives)
- [Part 15 — Recipes & End-to-End Walkthrough](#part-15--recipes--end-to-end-walkthrough)

---

## Part 1 — Foundations & Mental Model

### 1.1 What Nginx Is

Nginx (pronounced "engine-x") is an open-source web server, reverse proxy, load balancer, and HTTP cache, created by Igor Sysoev and first released in 2004. It was written to solve the **C10k problem** — handling ten thousand concurrent connections on a single machine — which the process-per-connection servers of the era (notably Apache's prefork model) could not do efficiently.

Today Nginx is one of the most widely deployed web servers on the internet. It serves static files, terminates TLS, reverse-proxies application servers, balances load across upstreams, and caches responses — often all at once, in one process tree, from one config file.

There are two editions: open-source **Nginx** (what this guide covers) and **Nginx Plus**, a commercial product with extras like active health checks via config, richer load-balancing, a live dashboard, and JWT auth. Almost everything you need is in the open-source build.

References: [nginx.org](https://nginx.org/en/), [Beginner's guide](https://nginx.org/en/docs/beginners_guide.html), [The C10k problem](http://www.kegel.com/c10k.html).

### 1.2 The Architecture

Nginx's defining design choice is its **event-driven, asynchronous, non-blocking** architecture. Instead of one thread or process per connection, each Nginx worker handles thousands of connections in a single thread using an event loop (`epoll` on Linux, `kqueue` on BSD/macOS).

The process model:

```mermaid
graph TD
  M["master process (runs as root)<br/>reads/validates config, binds :80/:443,<br/>manages worker lifecycle, binary upgrades"]
  M -->|forks| W0["worker 0 — event loop"]
  M -->|forks| W1["worker 1 — event loop"]
  M -->|forks| WN["worker N — event loop"]
  M -->|forks| CM["cache manager / loader"]
```

Workers run one per CPU core as an unprivileged user; the master handles no requests itself.

- **Master process** runs as root, reads config, binds to ports 80/443, and forks workers. It does not handle requests itself.
- **Worker processes** do all the actual request handling. Each is single-threaded and runs an event loop. The recommended count is one per CPU core (`worker_processes auto`).
- **Cache manager / loader** are helper processes for the proxy/FastCGI cache.

Because a worker never blocks on a slow client or slow disk (it registers a callback and moves on), a handful of workers can saturate modern hardware. This is why Nginx's memory footprint per connection is tiny compared to thread-per-connection servers.

References: [Nginx architecture (aosabook)](https://aosabook.org/en/v2/nginx.html), [Inside NGINX (official)](https://www.nginx.com/blog/inside-nginx-how-we-designed-for-performance-scale/).

### 1.3 Where Nginx Fits in 2026

Nginx's sweet spots:

- **Static file serving** — extremely fast, low overhead, `sendfile`-based zero-copy.
- **Reverse proxy / API gateway** — the default front door for application servers (Gunicorn, uWSGI, PM2/Node, PHP-FPM, Java app servers).
- **Load balancing** — L7 (and L4 via the `stream` module) with several algorithms.
- **TLS termination** — offload TLS from app servers; centralize certificate handling.
- **HTTP caching** — `proxy_cache` turns Nginx into a capable caching layer in front of slower backends.
- **Edge of almost any stack** — battle-tested at the highest traffic tiers on earth.

Where Nginx is **not** the easiest choice:

- **Automatic HTTPS** — Nginx needs certbot (or another ACME client) plus a renewal timer. Caddy and Traefik do this with zero config.
- **Dynamic, container-native reconfiguration** — Nginx reloads from files; Traefik auto-discovers Docker/Kubernetes services natively.
- **Service mesh data plane** — that's Envoy's domain.
- **Per-request config changes without a reload** — open-source Nginx has no config API (Nginx Plus has a limited one).

### 1.4 The Mental Model — Contexts, Directives, Variables

Three concepts explain almost all of Nginx:

1. **Contexts** are nested configuration scopes: `main` (the file itself) → `events` → `http` → `server` → `location`. There is also a sibling `stream` context for L4 TCP/UDP proxying. Directives are only valid in certain contexts, and many **inherit** downward into nested contexts.

2. **Directives** are the configuration statements — either *simple* (`worker_processes auto;`, end with `;`) or *block* (`server { ... }`). A directive set in `http` is inherited by every `server` and `location` inside it, unless overridden.

3. **Variables** (`$host`, `$remote_addr`, `$uri`, …) are evaluated per request and are the glue for logging, proxying, and conditional logic. Nginx variables are lazily evaluated and read-only except for ones you create with `set`.

If you internalize "directives inherit down the context tree, and the most specific context wins," most of Nginx's surprising behavior becomes predictable.

### 1.5 Nginx vs. Caddy — The Mental Model Shift

If you're coming from (or comparing against) Caddy, the key differences:

| Concept | Nginx | Caddy |
|---------|-------|-------|
| Config format | Custom DSL: contexts, `server`/`location` blocks | Caddyfile (or JSON) |
| TLS certificates | Manual: certbot + renewal timer | Automatic by default |
| HTTP→HTTPS redirect | You write the redirect server block | Automatic |
| Reload | `nginx -s reload` (graceful) | `caddy reload` / admin API |
| Routing | `location` blocks with a specific matching precedence | Matchers with a fixed directive order |
| Worker model | Multi-process event loop (C) | Goroutines (Go) |
| Runtime reconfig | None in OSS (file reload only) | JSON admin API |
| Extend | Compile-in C modules (or dynamic modules) | Compile-in Go modules via xcaddy |

The biggest day-to-day difference is TLS: Nginx assumes you bring your own certificate management; Caddy assumes HTTPS should be automatic. The biggest *gotcha* difference is routing precedence — Nginx's location matching order (Part 5) trips up almost everyone at least once.

---

## Part 2 — Installation

### 2.1 Package Managers

The distro packages are often old. For current stable/mainline, use the official Nginx repository.

**Debian/Ubuntu (official repo):**

```bash
sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring
curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
  | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
http://nginx.org/packages/mainline/ubuntu $(lsb_release -cs) nginx" \
  | sudo tee /etc/apt/sources.list.d/nginx.list
sudo apt update && sudo apt install nginx
```

**RHEL/Fedora/CentOS:**

```bash
sudo dnf install nginx
```

**macOS (Homebrew) — for local development:**

```bash
brew install nginx
```

**Alpine (common in containers):**

```bash
apk add nginx
```

After install, Nginx is typically managed by systemd as the `nginx` service, with config under `/etc/nginx/`.

References: [Install nginx (official)](https://nginx.org/en/linux_packages.html).

### 2.2 Stable vs. Mainline

Nginx ships two branches:

| Branch | Use it when |
|--------|-------------|
| **Mainline** | You want the newest features and fixes (HTTP/3, etc.). Despite the name, it is stable enough for production and is what the Nginx team recommends for most users. |
| **Stable** | You want only critical bug fixes backported, no new features. Conservative environments. |

For new deployments in 2026, mainline is the usual pick — HTTP/3 support, for instance, lives there first.

### 2.3 Docker

```yaml
# docker-compose.yml
services:
  nginx:
    image: nginx:1.27                       # pin a version, avoid :latest drift
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./conf.d:/etc/nginx/conf.d:ro       # per-site server blocks
      - ./certs:/etc/nginx/certs:ro         # certificates (if not using certbot)
      - ./html:/usr/share/nginx/html:ro     # static content
```

The official `nginx` image is minimal and well maintained. For Alpine-based smaller images use the `nginx:1.27-alpine` tags. To reload config in a running container: `docker exec <container> nginx -s reload`.

References: [nginx Docker image](https://hub.docker.com/_/nginx).

### 2.4 Modules and Building from Source

Nginx modules are compiled in. Two kinds:

- **Static modules** — compiled into the binary at build time (`./configure --with-...`).
- **Dynamic modules** — compiled separately as `.so` files and loaded with `load_module` (since Nginx 1.9.11).

Check what your binary was built with:

```bash
nginx -V          # prints version + the full ./configure argument list
```

Build from source when you need a module the package doesn't ship (e.g. Brotli, ModSecurity, or a third-party module):

```bash
# Download and unpack the matching nginx source, then:
./configure \
  --prefix=/etc/nginx \
  --with-http_ssl_module \
  --with-http_v2_module \
  --with-http_v3_module \
  --with-http_realip_module \
  --with-http_stub_status_module \
  --add-module=../ngx_brotli          # third-party module
make && sudo make install
```

Common bundled-but-optional modules you'll want: `http_ssl_module`, `http_v2_module`, `http_v3_module`, `http_realip_module`, `http_stub_status_module`, `http_gzip_static_module`, `stream` (L4 proxy).

References: [Building nginx from sources](https://nginx.org/en/docs/configure.html), [Dynamic modules](https://nginx.org/en/docs/ngx_core_module.html#load_module).

### 2.5 First Run and the CLI

```bash
nginx                         # start (foreground depends on daemon directive)
nginx -t                      # TEST config syntax — run this before every reload
nginx -T                      # test AND dump the full effective config
nginx -s reload               # graceful reload (re-read config, no dropped conns)
nginx -s reopen               # reopen log files (after logrotate)
nginx -s quit                 # graceful shutdown (finish in-flight requests)
nginx -s stop                 # fast shutdown
nginx -V                      # version + build/configure flags
```

In production, let systemd manage the process (`systemctl reload nginx`), but `nginx -t` is the command you will run more than any other — always validate before reloading.

References: [Controlling nginx](https://nginx.org/en/docs/control.html), [Command-line parameters](https://nginx.org/en/docs/switches.html).

---

## Part 3 — Configuration Structure

### 3.1 The File Layout

A typical Debian/Ubuntu Nginx install:

```
/etc/nginx/
├── nginx.conf                 # main config — the entry point
├── conf.d/                    # *.conf files auto-included into http {}
│   └── default.conf
├── sites-available/           # (Debian convention) server blocks you've written
├── sites-enabled/             # symlinks to sites-available that are active
├── snippets/                  # reusable fragments to include
├── mime.types                 # MIME type map
└── modules-enabled/           # dynamic module load directives
```

The `sites-available` / `sites-enabled` split is a **Debian convention**, not an Nginx feature — it works only because `nginx.conf` contains `include /etc/nginx/sites-enabled/*;`. The official Nginx packages use `conf.d/*.conf` instead. Either is fine; just know which your distro uses.

References: [Configuration file structure](https://nginx.org/en/docs/beginners_guide.html#conf_structure).

### 3.2 Contexts

Configuration is organized into nested **contexts**:

```nginx
# main context (the file itself)
user www-data;
worker_processes auto;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    server {
        listen 80;
        server_name example.com;

        location / {
            root /var/www/html;
        }
    }
}
```

| Context | Purpose |
|---------|---------|
| `main` | Global: user, worker process count, error log, pid file |
| `events` | Connection processing: `worker_connections`, `use epoll` |
| `http` | All HTTP/HTTPS config; contains `server` blocks |
| `server` | A virtual host: which addresses/names it answers |
| `location` | Request-path-specific config inside a `server` |
| `upstream` | A named pool of backend servers (inside `http`) |
| `stream` | L4 (TCP/UDP) proxying — a sibling of `http`, not inside it |

References: [Core functionality](https://nginx.org/en/docs/ngx_core_module.html).

### 3.3 Directive Inheritance

Directives set in an outer context are inherited by inner contexts — **but only if the inner context does not set a directive of the same kind.** This is the single most important rule for predicting Nginx behavior.

```nginx
http {
    gzip on;                      # applies to all servers/locations below...

    server {
        # gzip is on here (inherited)

        location /images/ {
            gzip off;             # ...unless overridden here
        }
    }
}
```

Two important subtleties:

- **`add_header` does NOT merge — it replaces.** If a `location` block has any `add_header`, it *drops every inherited `add_header`* from the enclosing `server`/`http`. This is a notorious source of "my security headers disappeared on one route" bugs. Re-declare all headers in the inner block, or use the `always` parameter and a careful structure.
- **Array-style directives** (like `proxy_set_header`) follow the same "set at one level replaces the inherited set" rule.

References: [add_header inheritance](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header).

### 3.4 include and snippets

`include` splices another file (or glob) into the current context. Use it to keep configs modular:

```nginx
http {
    include /etc/nginx/conf.d/*.conf;        # one file per site
    include /etc/nginx/snippets/gzip.conf;   # reusable fragment
}
```

A common pattern — a reusable proxy-headers snippet:

```nginx
# /etc/nginx/snippets/proxy.conf
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_http_version 1.1;
```

```nginx
location / {
    include snippets/proxy.conf;
    proxy_pass http://localhost:8080;
}
```

References: [include directive](https://nginx.org/en/docs/ngx_core_module.html#include).

### 3.5 Testing and Reloading

The reload model is the heart of safe Nginx operations:

```bash
nginx -t                  # validate syntax + check files exist
nginx -s reload           # OR: systemctl reload nginx
```

On reload, the master process re-reads the config, starts **new** workers with the new config, and gracefully shuts down the **old** workers once their in-flight requests finish. Existing connections are not dropped. If the new config fails to parse, the reload is aborted and the old workers keep running — so a bad reload cannot take you down, *provided you ran `nginx -t` first* and it passed.

Always wire `nginx -t` into CI and into any deploy script before the reload.

References: [Controlling nginx](https://nginx.org/en/docs/control.html).

---

## Part 4 — Server Blocks & Virtual Hosts

### 4.1 The server Block

A `server` block defines a virtual host — the combination of an address/port (`listen`) and one or more names (`server_name`) that it answers for:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    root /var/www/example;
    index index.html;
}
```

You can run many `server` blocks on the same port; Nginx picks the right one per request using `listen` and `server_name`.

References: [Server names](https://nginx.org/en/docs/http/server_names.html).

### 4.2 listen

The `listen` directive controls address, port, and per-listener options:

```nginx
listen 80;                          # IPv4, port 80, all interfaces
listen 443 ssl;                     # TLS
listen 443 ssl default_server;      # the fallback server for this port
listen [::]:80;                     # IPv6
listen 127.0.0.1:8080;              # specific interface + port
listen 443 quic reuseport;          # HTTP/3 (QUIC) — see Part 8
```

Modern Nginx (1.25.1+) enables HTTP/2 with a separate `http2 on;` directive rather than `listen ... http2`:

```nginx
server {
    listen 443 ssl;
    http2 on;
    # ...
}
```

References: [listen directive](https://nginx.org/en/docs/http/ngx_http_core_module.html#listen).

### 4.3 server_name and Matching

`server_name` can be exact, wildcard, or regex:

```nginx
server_name example.com;            # exact
server_name *.example.com;          # leading wildcard
server_name example.*;              # trailing wildcard
server_name ~^www\d+\.example\.com$; # regex (note the leading ~)
server_name "";                     # matches requests with no Host header
```

When multiple servers could match a request's `Host` header, Nginx picks in this order:

1. Exact name.
2. Longest leading wildcard (`*.example.com`).
3. Longest trailing wildcard (`example.*`).
4. First matching regex (in config order).
5. The `default_server` for that `listen` port (or the first server block if none is marked).

References: [How nginx processes a request](https://nginx.org/en/docs/http/request_processing.html).

### 4.4 The default_server and the Catch-All

If a request's `Host` matches no `server_name`, Nginx uses the `default_server` for that port. Without an explicit one, the **first** server block on the port becomes default — which is rarely what you want. Define an explicit catch-all to reject unknown hosts (a defense against Host-header abuse and noisy bots):

```nginx
server {
    listen 80 default_server;
    server_name _;                  # "_" is just an invalid name, never matches a real Host
    return 444;                     # 444 = close connection with no response
}
```

References: [default_server](https://nginx.org/en/docs/http/ngx_http_core_module.html#listen), [server_name "_"](https://nginx.org/en/docs/http/server_names.html#miscellaneous_names).

---

## Part 5 — Location Matching

This is the part that trips up everyone. Get it right and most of Nginx clicks into place.

### 5.1 The location Modifiers

```nginx
location = /exact { }        # exact match only
location ^~ /prefix/ { }     # prefix match; if it wins, skip regex checks
location ~ \.php$ { }        # case-sensitive regex
location ~* \.(jpg|png)$ { } # case-insensitive regex
location /prefix/ { }        # plain prefix match
location @named { }          # named location (internal, for try_files/error_page)
```

### 5.2 The Matching Algorithm (Memorize This)

For each request URI, Nginx selects exactly one location using this precise order:

1. **Exact match (`=`)** — if a `location = /uri` matches exactly, it wins immediately. Search stops.
2. **Prefix matches** — Nginx scans all plain-prefix and `^~` locations and remembers the **longest** matching prefix.
3. If that longest prefix uses the **`^~`** modifier, Nginx uses it and **skips regex entirely**.
4. Otherwise, Nginx checks **regex** locations (`~`, `~*`) **in the order they appear in the file**, and the **first** one that matches wins.
5. If no regex matches, Nginx falls back to the longest prefix it remembered in step 2.

So the mental shortcut: **`=` beats `^~` beats regex beats plain prefix** — but regex only gets a turn if the longest prefix match wasn't `^~`, and among regexes, **file order** decides.

```nginx
server {
    location = / { }                 # only the bare "/" request
    location ^~ /static/ { }         # /static/* — never falls through to regex
    location ~* \.(jpg|css|js)$ { }  # asset extensions (first regex to match wins)
    location / { }                   # everything else (longest-prefix fallback)
}
```

References: [location directive](https://nginx.org/en/docs/http/ngx_http_core_module.html#location).

### 5.3 root vs. alias

This is the second classic gotcha. Both set where files are found, but they combine with the location path differently:

- **`root`** — the location path is **appended** to the root.
- **`alias`** — the location path is **replaced** by the alias.

```nginx
# root: request /images/cat.png  ->  /var/www/data/images/cat.png
location /images/ {
    root /var/www/data;
}

# alias: request /images/cat.png  ->  /var/www/data/cat.png
location /images/ {
    alias /var/www/data/;          # the matched "/images/" is dropped
}
```

Rules of thumb: prefer `root` when the URL path mirrors the directory layout. Use `alias` when it doesn't. With `alias`, **keep the trailing slashes consistent** on both the location and the alias path — mismatched slashes are a frequent source of 404s. Avoid `alias` inside regex locations unless you use captures.

References: [alias](https://nginx.org/en/docs/http/ngx_http_core_module.html#alias), [root](https://nginx.org/en/docs/http/ngx_http_core_module.html#root).

### 5.4 try_files

`try_files` checks for files/directories in order and uses the first that exists, with a final fallback:

```nginx
# Serve the file if it exists, else the directory, else 404
location / {
    try_files $uri $uri/ =404;
}

# SPA fallback: serve index.html for any unmatched route
location / {
    try_files $uri $uri/ /index.html;
}

# Proxy fallback via a named location
location / {
    try_files $uri @backend;
}
location @backend {
    proxy_pass http://localhost:3000;
}
```

`try_files` is the idiomatic way to do "static if present, otherwise app" routing. The final argument is special: a code (`=404`), a named location (`@name`), or a URI to internally redirect to.

References: [try_files](https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files).

---

## Part 6 — Serving Static Content

### 6.1 The Basics

```nginx
server {
    listen 80;
    server_name static.example.com;

    root  /var/www/html;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

`root` sets the document root; `index` lists the files to try for a directory request; `try_files` handles the lookup and the 404.

References: [Serving static content](https://docs.nginx.com/nginx/admin-guide/web-server/serving-static-content/).

### 6.2 sendfile, tcp_nopush, tcp_nodelay

The classic static-serving performance trio, usually set in `http`:

```nginx
http {
    sendfile     on;     # zero-copy: kernel sends file straight to socket
    tcp_nopush   on;     # send headers + file start in one packet (with sendfile)
    tcp_nodelay  on;     # don't delay small packets on keep-alive connections
}
```

`sendfile on` lets the kernel copy file data to the socket without bouncing through user space. `tcp_nopush` (only effective with sendfile) fills packets fully before sending. `tcp_nodelay` disables Nagle's algorithm for low-latency small writes. The combination is correct for almost all workloads.

References: [sendfile](https://nginx.org/en/docs/http/ngx_http_core_module.html#sendfile).

### 6.3 Compression (gzip and Brotli)

```nginx
http {
    gzip              on;
    gzip_comp_level   5;          # 1-9; 5 is a good speed/ratio balance
    gzip_min_length   256;        # don't bother compressing tiny responses
    gzip_vary         on;         # add "Vary: Accept-Encoding"
    gzip_proxied      any;
    gzip_types        text/plain text/css application/json
                      application/javascript text/xml application/xml
                      image/svg+xml;
}
```

`gzip` never compresses `text/html`'s type out of the list because `text/html` is always compressed by default — list the *other* types you want. With the `ngx_brotli` module you can add Brotli, which compresses text better than gzip:

```nginx
brotli            on;
brotli_comp_level 5;
brotli_types      text/css application/javascript application/json image/svg+xml;
```

Serve both and let the client's `Accept-Encoding` decide. For pre-compressed assets from a build pipeline, `gzip_static on;` serves a `file.gz` if it exists instead of compressing on the fly.

References: [ngx_http_gzip_module](https://nginx.org/en/docs/http/ngx_http_gzip_module.html).

### 6.4 Cache-Control for Static Assets

Use `expires` (and `Cache-Control`) to let browsers and CDNs cache aggressively:

```nginx
# Hashed build assets — cache forever
location ~* \.(?:css|js|woff2|png|jpg|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}

# HTML — never cache (it references the hashed assets)
location = /index.html {
    expires -1;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

`expires 1y` sets both the `Expires` and `Cache-Control: max-age` headers. `immutable` tells the browser never to revalidate hashed assets. As always, remember the `add_header` replacement gotcha (Part 3.3) when adding headers in nested locations.

References: [expires](https://nginx.org/en/docs/http/ngx_http_headers_module.html#expires).

---

## Part 7 — Reverse Proxy & Load Balancing

### 7.1 Basic Reverse Proxy

```nginx
server {
    listen 80;
    server_name app.example.com;

    location / {
        proxy_pass http://localhost:8080;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Unlike some servers, Nginx does **not** forward useful proxy headers automatically — you must set them. The four above are the standard set: `Host` preserves the original hostname, `X-Real-IP` and `X-Forwarded-For` carry the client IP, and `X-Forwarded-Proto` tells the backend whether the original request was HTTPS.

References: [ngx_http_proxy_module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

### 7.2 The proxy_pass Trailing-Slash Gotcha

Whether `proxy_pass` rewrites the path depends on whether it includes a URI part:

```nginx
# NO trailing slash / URI: the full original URI is passed through
location /api/ {
    proxy_pass http://backend;        # /api/users -> backend /api/users
}

# WITH trailing slash / URI: the matched location prefix is REPLACED
location /api/ {
    proxy_pass http://backend/;       # /api/users -> backend /users
}
```

If `proxy_pass` has *any* URI component (even just `/`), Nginx replaces the part of the request URI matched by the location with that component. If it has only a host (and optional port), the original URI is passed unchanged. This single rule explains most "my proxy is hitting the wrong path" confusion.

References: [proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).

### 7.3 Upstreams and Load Balancing

Define a pool with `upstream`, then proxy to it by name:

```nginx
upstream backend {
    # load balancing method (default: round-robin)
    least_conn;

    server 10.0.0.1:8080 weight=3;        # gets 3x the traffic
    server 10.0.0.2:8080;
    server 10.0.0.3:8080 backup;          # only used if others are down
    server 10.0.0.4:8080 down;            # administratively disabled

    keepalive 32;                          # keep idle conns to upstreams
}

server {
    location / {
        proxy_pass http://backend;
        proxy_http_version 1.1;            # required for upstream keepalive
        proxy_set_header Connection "";    # required for upstream keepalive
    }
}
```

Load-balancing methods:

| Method | Behavior |
|--------|----------|
| round-robin (default) | Cycle through servers, weighted |
| `least_conn` | Send to the server with fewest active connections |
| `ip_hash` | Sticky by client IP (same client → same server) |
| `hash $key consistent` | Sticky by an arbitrary key with consistent hashing |
| `random two least_conn` | Pick two at random, choose the less busy (power-of-two-choices) |

The `keepalive` directive plus `proxy_http_version 1.1` and `proxy_set_header Connection ""` is essential for performance — without it, Nginx opens a fresh TCP connection to the backend for every request.

References: [ngx_http_upstream_module](https://nginx.org/en/docs/http/ngx_http_upstream_module.html).

### 7.4 Health Checks

Open-source Nginx has **passive** health checks built into the upstream module: `max_fails` and `fail_timeout` mark a server unavailable after repeated failures on real traffic.

```nginx
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
}
```

After 3 failed attempts within 30s, the server is considered down for 30s, then retried. **Active** health checks (Nginx probing a `/health` endpoint on a timer, configured via `health_check`) are an **Nginx Plus** feature. On open-source Nginx, pair passive checks with an external checker or rely on the backend's own readiness.

References: [Health checks (passive)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#server).

### 7.5 WebSockets

WebSocket proxying requires forwarding the `Upgrade`/`Connection` headers and HTTP/1.1:

```nginx
location /ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 3600s;             # long-lived connections
}
```

`$connection_upgrade` is best derived with a `map` so non-WebSocket requests get `Connection: close`:

```nginx
http {
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }
}
```

References: [WebSocket proxying](https://nginx.org/en/docs/http/websocket.html).

### 7.6 Buffering, Timeouts, and Streaming

```nginx
location / {
    proxy_pass http://backend;

    proxy_connect_timeout 5s;     # time to establish a connection
    proxy_send_timeout    60s;    # time between successive write ops
    proxy_read_timeout    60s;    # time between successive read ops

    proxy_buffering       on;     # buffer the response from the backend
    proxy_buffers         8 16k;  # buffer count and size

    # For Server-Sent Events / streaming, disable buffering:
    # proxy_buffering off;
}
```

`proxy_buffering on` (the default) lets Nginx read the backend's response quickly and feed slow clients at their own pace — good for throughput. For SSE or any streamed response, set `proxy_buffering off` so events reach the client immediately.

References: [proxy_buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering).

---

## Part 8 — TLS & HTTPS

### 8.1 A Basic HTTPS Server

```nginx
server {
    listen 443 ssl;
    http2  on;
    server_name example.com;

    ssl_certificate     /etc/nginx/certs/example.com/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/example.com/privkey.pem;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;        # let modern clients pick (TLS1.3)
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    location / {
        proxy_pass http://localhost:8080;
    }
}
```

`ssl_certificate` must be the **fullchain** (leaf + intermediates), or clients without the intermediate cached will fail — the classic "works in my browser, breaks in curl" bug.

References: [Configuring HTTPS servers](https://nginx.org/en/docs/http/configuring_https_servers.html).

### 8.2 The HTTP→HTTPS Redirect

Unlike Caddy, Nginx does not redirect automatically. You write a dedicated port-80 server:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}
```

`return 301` is the cheapest correct way — avoid `rewrite` for this (Part 11).

### 8.3 certbot — Automating Let's Encrypt

Open-source Nginx has no built-in ACME. Use certbot with the nginx plugin:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
```

The plugin edits your server blocks to add the certificate directives and the redirect, then installs a systemd timer (`certbot.timer`) that renews automatically. Verify renewal with:

```bash
sudo certbot renew --dry-run
```

This is the piece Caddy and Traefik give you for free; on Nginx it's one extra package plus the timer.

References: [certbot + nginx](https://eff-certbot.readthedocs.io/en/stable/using.html#nginx).

### 8.4 Hardening: HSTS, OCSP Stapling, Ciphers

```nginx
# Strong, modern TLS (see Mozilla's SSL Config Generator for current values)
ssl_protocols             TLSv1.2 TLSv1.3;
ssl_ciphers               ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
ssl_prefer_server_ciphers off;

# OCSP stapling — faster handshakes, fewer client CA round-trips
ssl_stapling        on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/nginx/certs/example.com/chain.pem;
resolver 1.1.1.1 8.8.8.8 valid=300s;

# HSTS — force HTTPS for a year (be sure you mean it before adding preload)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

The `always` parameter on `add_header` ensures the header is sent even on error responses (4xx/5xx). Generate current cipher lists with the [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/) rather than hand-rolling them.

References: [ssl_stapling](https://nginx.org/en/docs/http/ngx_http_ssl_module.html#ssl_stapling), [Mozilla SSL Config](https://ssl-config.mozilla.org/).

### 8.5 HTTP/2 and HTTP/3 (QUIC)

HTTP/2 is a one-line addition on a TLS listener (modern syntax):

```nginx
server {
    listen 443 ssl;
    http2  on;
}
```

HTTP/3 (QUIC over UDP) is available in mainline Nginx built with `--with-http_v3_module`:

```nginx
server {
    listen 443 ssl;                       # TCP for HTTP/1.1 + HTTP/2
    listen 443 quic reuseport;            # UDP for HTTP/3
    http2 on;
    http3 on;

    ssl_certificate     /etc/nginx/certs/example.com/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/example.com/privkey.pem;

    # Tell clients HTTP/3 is available
    add_header Alt-Svc 'h3=":443"; ma=86400' always;
}
```

Ensure your firewall allows **UDP** on 443 for QUIC. `reuseport` should appear on only one server block per address to avoid conflicts.

References: [HTTP/3 in nginx](https://nginx.org/en/docs/http/ngx_http_v3_module.html).

---

## Part 9 — Performance & Caching

### 9.1 Worker and Connection Tuning

```nginx
# main context
worker_processes      auto;            # one per CPU core
worker_rlimit_nofile  65535;           # raise the FD ceiling for the master

events {
    worker_connections 8192;           # max connections PER worker
    multi_accept       on;
    use                epoll;          # Linux event method (auto-selected)
}
```

Theoretical max simultaneous connections ≈ `worker_processes × worker_connections`. Remember each proxied request uses *two* connections (client + upstream), and `worker_connections` must not exceed the OS file-descriptor limit (`worker_rlimit_nofile`).

References: [Tuning nginx](https://www.nginx.com/blog/tuning-nginx/).

### 9.2 Keep-Alive

```nginx
http {
    keepalive_timeout  65;        # how long to hold idle client connections
    keepalive_requests 1000;      # max requests per kept-alive connection
}
```

And for upstreams (Part 7.3), the `keepalive` directive in the `upstream` block plus `proxy_http_version 1.1` + `proxy_set_header Connection ""`.

### 9.3 open_file_cache

Cache file descriptors and metadata for frequently served static files:

```nginx
open_file_cache          max=10000 inactive=60s;
open_file_cache_valid    60s;
open_file_cache_min_uses 2;
open_file_cache_errors   on;
```

This avoids repeated `open()`/`stat()` syscalls on hot static content. Big win for high-RPS static serving; irrelevant for pure reverse proxying.

References: [open_file_cache](https://nginx.org/en/docs/http/ngx_http_core_module.html#open_file_cache).

### 9.4 Proxy Caching

Turn Nginx into a caching layer in front of a slow backend:

```nginx
http {
    # Define a cache zone: 10MB of keys in memory, content on disk, 1GB max
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=app_cache:10m
                     max_size=1g inactive=60m use_temp_path=off;

    server {
        location / {
            proxy_cache            app_cache;
            proxy_cache_valid      200 302 10m;     # cache OK/redirects 10 min
            proxy_cache_valid      404 1m;
            proxy_cache_key        $scheme$host$request_uri;
            proxy_cache_use_stale  error timeout updating http_500 http_502 http_503;
            proxy_cache_lock       on;              # collapse concurrent misses
            add_header X-Cache-Status $upstream_cache_status;   # HIT/MISS/EXPIRED

            proxy_pass http://backend;
        }
    }
}
```

The `keys_zone` lives in shared memory; cached bodies live on disk. `proxy_cache_use_stale` lets Nginx serve stale content when the backend is down — a powerful resilience feature. The `X-Cache-Status` header is invaluable for debugging cache behavior. `proxy_cache_lock on` prevents a cache-miss stampede by letting one request populate the cache while others wait.

References: [Content caching](https://docs.nginx.com/nginx/admin-guide/content-cache/content-caching/), [proxy_cache_path](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_cache_path).

### 9.5 Rate Limiting

Nginx rate limiting uses the leaky-bucket algorithm. Define a shared zone, then apply it:

```nginx
http {
    # 10 requests/second per client IP; 10MB zone (~160k IPs)
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    # Limit concurrent connections per IP
    limit_conn_zone $binary_remote_addr zone=conns:10m;

    server {
        location /api/ {
            limit_req  zone=api burst=20 nodelay;   # allow short bursts
            limit_conn conns 10;
            limit_req_status 429;
            proxy_pass http://backend;
        }
    }
}
```

`burst=20` permits short spikes; `nodelay` serves the burst immediately rather than queuing it. Use `$binary_remote_addr` (not `$remote_addr`) — it's the compact form that fits far more entries in the zone. For login endpoints, a tighter rate (e.g. `5r/m`) blunts credential-stuffing.

References: [Rate limiting](https://www.nginx.com/blog/rate-limiting-nginx/), [limit_req_zone](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).

---

## Part 10 — Security & Access Control

### 10.1 IP Allow/Deny

```nginx
location /admin/ {
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny  all;                    # everyone else gets 403
    proxy_pass http://localhost:5000;
}
```

Rules are evaluated top to bottom; the first match wins. If Nginx is behind a load balancer, `$remote_addr` is the LB's IP — use the `realip` module (`set_real_ip_from` + `real_ip_header X-Forwarded-For`) so `allow`/`deny` see the true client IP.

References: [ngx_http_access_module](https://nginx.org/en/docs/http/ngx_http_access_module.html), [realip module](https://nginx.org/en/docs/http/ngx_http_realip_module.html).

### 10.2 Basic Authentication

```nginx
location /private/ {
    auth_basic           "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

Create the password file with `htpasswd` (Apache utils) or `openssl`:

```bash
htpasswd -c /etc/nginx/.htpasswd alice      # -c creates; omit it to add users
```

Basic auth sends credentials base64-encoded on every request — only safe over HTTPS. Combine `auth_basic` with `allow`/`deny` via the `satisfy` directive (`satisfy any` = pass either check; `satisfy all` = require both).

References: [auth_basic](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html).

### 10.3 Security Headers

```nginx
# Apply at server level; re-declare in any location that adds its own headers
add_header X-Content-Type-Options    nosniff               always;
add_header X-Frame-Options           SAMEORIGIN            always;
add_header Referrer-Policy           strict-origin-when-cross-origin always;
add_header Content-Security-Policy    "default-src 'self'" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

Remember Part 3.3: a `location` with its own `add_header` discards all of these. The `always` flag makes headers apply to error responses too. Also hide the version banner:

```nginx
http {
    server_tokens off;            # "Server: nginx" instead of "nginx/1.27.1"
}
```

References: [Security headers](https://nginx.org/en/docs/http/ngx_http_headers_module.html), [server_tokens](https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens).

### 10.4 Request Limits and WAF

```nginx
client_max_body_size      10m;        # reject huge uploads (413)
large_client_header_buffers 4 16k;    # bound header size
client_body_timeout       10s;
client_header_timeout     10s;
```

For a Web Application Firewall, the standard option is **ModSecurity** with the OWASP Core Rule Set, compiled as a dynamic module (`ngx_http_modsecurity_module`). For most teams, a cloud WAF (Cloudflare, AWS WAF) in front of Nginx is less operational burden than self-hosting ModSecurity.

References: [client_max_body_size](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size), [ModSecurity-nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx).

---

## Part 11 — Rewrites, Redirects & the Rewrite Engine

### 11.1 return vs. rewrite

For redirects, prefer `return` — it's explicit and cheap:

```nginx
return 301 https://example.com$request_uri;   # permanent redirect
return 302 /maintenance.html;                  # temporary redirect
return 444;                                     # close connection, no response
return 200 "pong";                              # static response (with default_type)
```

Use `rewrite` only when you genuinely need to transform the URI with a regex:

```nginx
# Rewrite /old/123 -> /new/123 and stop processing rewrites
rewrite ^/old/(.*)$ /new/$1 last;

# Rewrite and issue an external 301
rewrite ^/legacy/(.*)$ /modern/$1 permanent;
```

`rewrite` flags:

| Flag | Effect |
|------|--------|
| `last` | Stop current rewrites, re-evaluate location with the new URI |
| `break` | Stop rewrites, keep processing in the current location |
| `redirect` | Return a 302 to the client |
| `permanent` | Return a 301 to the client |

References: [rewrite](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#rewrite), [return](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#return).

### 11.2 "If Is Evil"

Inside a `location`, the `if` directive has surprising and sometimes broken behavior — it can silently do the wrong thing with most directives. The official guidance ("If is Evil") is: inside `location`, **only `return` and `rewrite` are 100% safe inside `if`.** For anything else, use alternatives:

```nginx
# DON'T: if with add_header / proxy_pass etc. inside a location is unreliable
# DO: use map to compute a variable instead

map $request_method $is_post {
    POST    1;
    default 0;
}

# DO: use try_files, or separate location blocks, instead of if
```

References: ["If is Evil"](https://www.nginx.com/resources/wiki/start/topics/depth/ifisevil/).

### 11.3 map — The Right Tool for Conditionals

`map` builds a variable from another variable. It's evaluated lazily and is the clean replacement for most `if` usage:

```nginx
http {
    # Choose a backend by Host
    map $host $backend_pool {
        api.example.com  api_servers;
        default          web_servers;
    }

    # Block specific user agents
    map $http_user_agent $is_bad_bot {
        default            0;
        ~*(badbot|scraper) 1;
    }

    server {
        if ($is_bad_bot) { return 403; }   # the one safe use of if
        location / { proxy_pass http://$backend_pool; }
    }
}
```

References: [map module](https://nginx.org/en/docs/http/ngx_http_map_module.html).

---

## Part 12 — Logging & Observability

### 12.1 Access Logs and log_format

```nginx
http {
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time uct=$upstream_connect_time '
                    'urt=$upstream_response_time';

    # JSON access logs — easy to ship to Loki / Elasticsearch
    log_format json escape=json '{'
        '"time":"$time_iso8601",'
        '"remote_addr":"$remote_addr",'
        '"method":"$request_method",'
        '"uri":"$request_uri",'
        '"status":$status,'
        '"bytes":$body_bytes_sent,'
        '"rt":$request_time,'
        '"urt":"$upstream_response_time",'
        '"ua":"$http_user_agent"'
    '}';

    access_log /var/log/nginx/access.log json;
}
```

`$request_time` is total time Nginx spent on the request; `$upstream_response_time` is how long the backend took — comparing them isolates whether latency is in Nginx or the backend. `escape=json` makes values safe for JSON.

References: [log_format](https://nginx.org/en/docs/http/ngx_http_log_module.html#log_format).

### 12.2 Conditional and Disabled Logging

```nginx
# Don't log health checks
location = /healthz {
    access_log off;
    return 200 "ok";
}

# Only log non-2xx/3xx responses
map $status $loggable {
    ~^[23] 0;
    default 1;
}
access_log /var/log/nginx/errors.log main if=$loggable;
```

`access_log off` on noisy endpoints keeps logs signal-rich.

### 12.3 Error Logs

```nginx
error_log /var/log/nginx/error.log warn;
```

Levels, least to most verbose: `emerg`, `alert`, `crit`, `error`, `warn`, `notice`, `info`, `debug`. Use `warn` in production; `debug` (requires a debug build or `--with-debug`) for deep troubleshooting only.

### 12.4 stub_status and Prometheus

The `stub_status` module exposes basic connection metrics:

```nginx
location = /nginx_status {
    stub_status;
    allow 127.0.0.1;
    deny  all;
}
```

It reports active connections, accepts/handled/requests counters, and reading/writing/waiting states. For Prometheus, run the [nginx-prometheus-exporter](https://github.com/nginxinc/nginx-prometheus-exporter), which scrapes `stub_status` and exposes proper metrics for Grafana. (Nginx Plus exposes far richer per-upstream metrics natively.)

References: [stub_status](https://nginx.org/en/docs/http/ngx_http_stub_status_module.html), [nginx-prometheus-exporter](https://github.com/nginxinc/nginx-prometheus-exporter).

---

## Part 13 — Production Operations

### 13.1 systemd

The packaged install ships a unit file. Manage Nginx through it:

```bash
sudo systemctl enable --now nginx     # start at boot + now
sudo systemctl reload nginx           # graceful reload (sends HUP)
sudo systemctl status nginx
sudo journalctl -u nginx -f
```

The unit's `ExecReload` runs `nginx -s reload`. Always `nginx -t` first — in a deploy script:

```bash
nginx -t && systemctl reload nginx
```

References: [Running nginx as a service](https://www.nginx.com/resources/wiki/start/topics/examples/systemd/).

### 13.2 Graceful Reload vs. Binary Upgrade

Two distinct zero-downtime operations:

- **Reload (config change):** `nginx -s reload` (or HUP signal). Master re-reads config, spawns new workers, drains old ones. Connections are never dropped; a bad config aborts the reload.
- **Binary upgrade (new Nginx version) with no downtime:** signal the running master to fork a new master from the new binary, run both in parallel, then retire the old one:

```bash
# 1. Replace the binary, then tell the old master to start a new master:
sudo kill -USR2 $(cat /run/nginx.pid)
# 2. Gracefully shut down the OLD workers (old master keeps the .oldbin pid):
sudo kill -WINCH $(cat /run/nginx.pid.oldbin)
# 3. If all good, quit the old master:
sudo kill -QUIT $(cat /run/nginx.pid.oldbin)
# (Or roll back: HUP the old master, TERM/QUIT the new one.)
```

The signal table worth knowing: `HUP` reload config, `USR2` upgrade binary, `WINCH` graceful worker shutdown, `QUIT` graceful stop, `TERM` fast stop, `USR1` reopen logs.

References: [Upgrading Executable on the Fly](https://nginx.org/en/docs/control.html#upgrade).

### 13.3 Log Rotation

Nginx holds log files open, so after `logrotate` moves them you must tell Nginx to reopen:

```bash
nginx -s reopen        # or: kill -USR1 <master-pid>
```

The packaged `logrotate` config does this for you via a `postrotate` hook. If you roll your own rotation, don't forget the reopen, or Nginx keeps writing to the rotated (deleted) inode.

### 13.4 File Descriptors and Limits

High-traffic Nginx needs many file descriptors (one+ per connection):

```nginx
worker_rlimit_nofile 65535;     # nginx.conf
```

```ini
# /etc/systemd/system/nginx.service.d/override.conf
[Service]
LimitNOFILE=65535
```

Set both the Nginx directive and the systemd `LimitNOFILE` — the OS limit caps what Nginx can request.

### 13.5 Common Pitfalls

- **Forgetting `nginx -t` before reload** — a typo can block the reload (safe) or, worse, you reload a stale file you didn't mean to.
- **The `add_header` replacement trap** (Part 3.3) — security headers silently vanish in nested locations.
- **`proxy_pass` trailing slash** (Part 7.2) — wrong path forwarded to the backend.
- **`root` vs `alias`** (Part 5.3) — 404s from path duplication.
- **Missing intermediate cert** — use the fullchain (Part 8.1).
- **No upstream keepalive** — silent throughput loss from a new TCP handshake per request.
- **`$remote_addr` behind a proxy** — without `realip`, allow/deny and logs see the LB, not the client.
- **Catch-all not defined** — an unintended server block becomes the default.

---

## Part 14 — Comparison to Alternatives

### 14.1 Caddy

**Where Caddy wins:** automatic HTTPS with zero config, dramatically shorter configs, a JSON admin API for dynamic reconfiguration, HTTP/3 on by default, and a single dependency-free binary.

**Where Nginx wins:** raw performance at extreme scale (the C event loop has lower per-connection overhead than Go's goroutines at 100k+ concurrent), a vastly larger third-party module and knowledge ecosystem (15+ years of Stack Overflow), the `stream` module for mature L4 proxying, and organizational familiarity.

The honest summary: for a small-to-moderate reverse proxy where HTTPS automation is the pain point, Caddy is less work. For an existing Nginx shop, extreme scale, or deep module needs, Nginx remains the workhorse. (See the companion Caddy study guide for the mirror image of this comparison.)

```nginx
# Nginx: explicit, ~20 lines incl. TLS + redirect (+ certbot for the cert)
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    http2 on;
    server_name example.com;
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 14.2 Apache (httpd)

**Where Nginx wins:** event-driven concurrency (Apache's prefork/worker models use more memory per connection), faster static serving and reverse proxying, simpler high-performance config.

**Where Apache wins:** `.htaccess` per-directory config (essential for shared hosting), the mature `mod_rewrite`, and `mod_php` for the simplest PHP integration (though PHP-FPM behind Nginx is the modern norm).

For new projects, Nginx is the more common front-end choice; Apache persists in shared hosting and legacy PHP stacks.

### 14.3 HAProxy

**Where Nginx wins:** it also serves static files and terminates/serves HTTP content (HAProxy is a pure proxy/LB), plus HTTP caching.

**Where HAProxy wins:** it is the gold standard for L4/L7 load balancing — richer balancing algorithms, superior connection-level health checking, detailed stats, and extreme-scale reliability. When you need a *dedicated* load balancer, HAProxy is purpose-built; Nginx is a web server that also balances load.

### 14.4 Envoy / Traefik

**Envoy** is the service-mesh data plane (Istio, Consul Connect): gRPC-native, xDS dynamic config from a control plane, deep observability — at the cost of notoriously complex YAML. **Traefik** is container-native: it auto-discovers Docker/Kubernetes services from labels/annotations with no file reloads, and does automatic HTTPS like Caddy.

Choose Envoy for service meshes, Traefik for label-driven container environments, and Nginx for everything from static sites to high-traffic reverse proxying on VMs and bare metal.

### 14.5 When NOT to Use Nginx

- **You want HTTPS handled for you with zero config** → Caddy or Traefik.
- **You need container label auto-discovery as a core feature** → Traefik.
- **You need a service-mesh data plane** → Envoy.
- **You need a dedicated, extreme-scale L4 load balancer** → HAProxy.
- **You only serve PHP on shared hosting with per-directory overrides** → Apache may be simpler.

For the broad middle — reverse proxy, static serving, TLS termination, caching, load balancing on real servers — Nginx is still the default for good reasons.

---

## Part 15 — Recipes & End-to-End Walkthrough

### Recipe 1: Multi-Site Reverse Proxy with TLS

```nginx
# /etc/nginx/conf.d/sites.conf
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {                                   # HTTP -> HTTPS for all hosts
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name app.example.com;

    ssl_certificate     /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        $connection_upgrade;
    }
}
```

### Recipe 2: SPA + API Backend

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    root /var/www/app/dist;

    # API to the backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Hashed assets — cache forever
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback — everything else serves index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Recipe 3: Load-Balanced Upstreams

```nginx
upstream api_pool {
    least_conn;
    server 10.0.0.11:8000 max_fails=3 fail_timeout=30s;
    server 10.0.0.12:8000 max_fails=3 fail_timeout=30s;
    server 10.0.0.13:8000 backup;
    keepalive 32;
}

server {
    listen 443 ssl;
    http2 on;
    server_name api.example.com;
    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://api_pool;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_next_upstream error timeout http_502 http_503;
    }
}
```

### Recipe 4: Caching Proxy for a Slow Backend

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=slow:20m
                 max_size=2g inactive=1h use_temp_path=off;

server {
    listen 443 ssl;
    http2 on;
    server_name cdn.example.com;
    ssl_certificate     /etc/letsencrypt/live/cdn.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cdn.example.com/privkey.pem;

    location / {
        proxy_cache           slow;
        proxy_cache_valid     200 10m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503;
        proxy_cache_lock      on;
        add_header            X-Cache-Status $upstream_cache_status always;
        proxy_pass            http://origin.internal:8080;
    }
}
```

### Recipe 5: Rate-Limited API with Brute-Force Protection

```nginx
limit_req_zone  $binary_remote_addr zone=api:10m   rate=10r/s;
limit_req_zone  $binary_remote_addr zone=login:10m rate=5r/m;

server {
    listen 443 ssl;
    http2 on;
    server_name api.example.com;
    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
    }

    location = /api/login {
        limit_req zone=login burst=3 nodelay;       # tight: blunt credential stuffing
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### End-to-End Walkthrough: From Fresh Server to Production

A real scenario — a frontend SPA, an API backend, and a WebSocket service — from a bare Ubuntu box to a hardened Nginx deployment.

**Step 1: Install Nginx (official mainline repo).**

```bash
sudo apt install -y curl gnupg2 ca-certificates lsb-release
curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
  | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
http://nginx.org/packages/mainline/ubuntu $(lsb_release -cs) nginx" \
  | sudo tee /etc/apt/sources.list.d/nginx.list
sudo apt update && sudo apt install nginx
sudo systemctl enable --now nginx
```

**Step 2: DNS.** Point the hostnames at the server's public IP:

```
app.example.com  → 203.0.113.10
api.example.com  → 203.0.113.10
ws.example.com   → 203.0.113.10
```

**Step 3: Write the config.** A clean structure — global tuning in `nginx.conf`, sites in `conf.d`:

```nginx
# /etc/nginx/conf.d/00-global.conf
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {                                   # global HTTP -> HTTPS
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
```

```nginx
# /etc/nginx/conf.d/app.conf
server {
    listen 443 ssl;
    http2 on;
    server_name app.example.com;
    # (certs added by certbot in step 4)

    root /var/www/app/dist;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        # re-declare security headers here (add_header replacement trap):
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```nginx
# /etc/nginx/conf.d/api.conf
server {
    listen 443 ssl;
    http2 on;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```nginx
# /etc/nginx/conf.d/ws.conf
server {
    listen 443 ssl;
    http2 on;
    server_name ws.example.com;

    location / {
        proxy_pass http://127.0.0.1:4000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host       $host;
        proxy_read_timeout 3600s;
    }
}
```

**Step 4: Get TLS certificates.**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d app.example.com -d api.example.com -d ws.example.com
sudo certbot renew --dry-run
```

Certbot inserts the `ssl_certificate`/`ssl_certificate_key` directives and installs the auto-renew timer.

**Step 5: Validate and reload.**

```bash
sudo nginx -t && sudo systemctl reload nginx
```

**Step 6: Verify.**

```bash
curl -I https://app.example.com           # HTTP/2 200 + HSTS header
curl -I http://app.example.com            # 301 -> https
curl -I https://api.example.com/health    # backend reachable
openssl s_client -connect app.example.com:443 -servername app.example.com \
  </dev/null 2>/dev/null | openssl x509 -noout -dates -issuer
```

**Step 7: Observe.** Add JSON logging and a status endpoint, scrape with the Prometheus exporter, and you have request rates, latency split (Nginx vs upstream), and connection stats feeding Grafana.

**What this gives you:** TLS termination with auto-renewal, HTTP→HTTPS redirects, HTTP/2, a cached/secured static SPA, a proxied API, and a WebSocket service — the standard production front door, all in a handful of small, version-controlled config files validated by `nginx -t` before every reload.
"""

# --------------------------------------------------------------------------- #
# Quizzes (grounded in the content above)
# --------------------------------------------------------------------------- #

QUIZZES = {
    1: [
        {"q": "What problem was Nginx originally built to solve?",
         "opts": ["TLS termination", "The C10k problem (10k concurrent connections)",
                  "PHP execution", "DNS resolution"],
         "answer": 1,
         "explain": "Nginx's event-driven model was a response to the C10k problem, which process-per-"
                    "connection servers like Apache prefork could not handle efficiently."},
        {"q": "In Nginx's process model, which process handles actual requests?",
         "opts": ["The master process", "The worker processes", "The cache manager", "systemd"],
         "answer": 1,
         "explain": "The master (root) reads config and binds ports but does not serve requests. "
                    "Workers — one per core — run the event loops that handle all traffic."},
        {"q": "What is the single most important rule for predicting Nginx behavior?",
         "opts": ["Directives run top to bottom",
                  "Directives inherit down the context tree unless overridden",
                  "Regex always wins", "The last directive wins"],
         "answer": 1,
         "explain": "Contexts nest (main→events→http→server→location) and directives inherit "
                    "downward; the most specific context that sets a directive wins."},
    ],
    2: [
        {"q": "Which command should you run before every config reload?",
         "opts": ["nginx -s reload", "nginx -t", "nginx -V", "nginx -s reopen"],
         "answer": 1,
         "explain": "nginx -t validates syntax and that referenced files exist. A failed reload is "
                    "aborted safely, but you should always test first."},
        {"q": "How are Nginx modules added to a build?",
         "opts": ["Loaded from a plugin directory at runtime",
                  "Compiled in statically, or built as loadable dynamic modules",
                  "Installed via npm", "Downloaded by the master process"],
         "answer": 1,
         "explain": "Modules are compiled in (static) or built as .so files loaded with load_module "
                    "(dynamic, since 1.9.11). `nginx -V` shows what your binary has."},
    ],
    3: [
        {"q": "Why might security headers 'disappear' on one route?",
         "opts": ["Nginx caches them", "A location's own add_header replaces ALL inherited add_headers",
                  "gzip strips them", "They expire"],
         "answer": 1,
         "explain": "add_header does not merge. Any add_header in an inner block drops every inherited "
                    "add_header — re-declare them in that block."},
        {"q": "What happens on `nginx -s reload` if the new config fails to parse?",
         "opts": ["Nginx crashes", "All connections drop",
                  "The reload is aborted and old workers keep running",
                  "Nginx falls back to defaults"],
         "answer": 2,
         "explain": "A bad reload cannot take you down: the master refuses it and the existing workers "
                    "continue serving — which is why nginx -t first is the habit."},
    ],
    4: [
        {"q": "Which `server_name` matches a request whose Host matches no other server?",
         "opts": ["server_name *;", "the default_server for that listen port",
                  "server_name regex;", "Nginx returns 500"],
         "answer": 1,
         "explain": "Unmatched Host falls to the default_server for the port — or the first server "
                    "block if none is marked. Define an explicit catch-all to control this."},
        {"q": "In modern Nginx (1.25.1+), how do you enable HTTP/2?",
         "opts": ["listen 443 ssl http2;", "http2 on;", "enable_http2;", "protocol h2;"],
         "answer": 1,
         "explain": "The separate `http2 on;` directive replaced the old `listen ... http2` parameter."},
    ],
    5: [
        {"q": "Which location modifier wins immediately and stops the search?",
         "opts": ["^~ prefix", "= exact match", "~ regex", "plain prefix"],
         "answer": 1,
         "explain": "An exact `=` match wins instantly. Otherwise: longest prefix is remembered; if it's "
                    "^~ it's used (skipping regex); else regexes are tried in file order; else the prefix."},
        {"q": "For `location /images/ { alias /data/; }`, where does /images/cat.png resolve?",
         "opts": ["/data/images/cat.png", "/data/cat.png", "/images/data/cat.png", "404 always"],
         "answer": 1,
         "explain": "alias REPLACES the matched location path, so /images/ is dropped → /data/cat.png. "
                    "(root would APPEND, giving /data/images/cat.png.)"},
    ],
    6: [
        {"q": "What does `sendfile on` do?",
         "opts": ["Compresses responses", "Zero-copy: the kernel sends file data straight to the socket",
                  "Enables caching", "Sends email alerts"],
         "answer": 1,
         "explain": "sendfile avoids copying file data through user space. Paired with tcp_nopush it "
                    "fills packets efficiently for static serving."},
        {"q": "How should hashed build assets vs index.html be cached?",
         "opts": ["Both immutable forever", "Both no-cache",
                  "Assets: expires 1y immutable; index.html: no-cache",
                  "Assets: no-cache; index.html: 1y"],
         "answer": 2,
         "explain": "Hashed filenames change per build → cache forever. index.html references them by "
                    "hash → must never be cached."},
    ],
    7: [
        {"q": "Does Nginx forward proxy headers like X-Forwarded-For automatically?",
         "opts": ["Yes, always", "No — you must set them with proxy_set_header",
                  "Only over HTTPS", "Only with Nginx Plus"],
         "answer": 1,
         "explain": "Nginx forwards nothing extra by default. Set Host, X-Real-IP, X-Forwarded-For, "
                    "and X-Forwarded-Proto explicitly."},
        {"q": "`location /api/ { proxy_pass http://backend/; }` — where does /api/users go?",
         "opts": ["backend /api/users", "backend /users", "backend /", "404"],
         "answer": 1,
         "explain": "Because proxy_pass has a URI part (the trailing /), the matched /api/ prefix is "
                    "replaced → /users. Without the slash, the full /api/users is passed."},
        {"q": "What's required for upstream keep-alive to actually work?",
         "opts": ["Nothing, it's automatic",
                  "keepalive in the upstream + proxy_http_version 1.1 + Connection \"\"",
                  "ip_hash", "proxy_buffering off"],
         "answer": 1,
         "explain": "Without all three, Nginx opens a fresh TCP connection to the backend per request — "
                    "a silent throughput loss."},
    ],
    8: [
        {"q": "Why must ssl_certificate point to the fullchain?",
         "opts": ["It's faster", "Clients without the intermediate cached will fail otherwise",
                  "It enables HTTP/2", "To support OCSP"],
         "answer": 1,
         "explain": "The leaf alone causes the classic 'works in my browser, breaks in curl' bug. "
                    "Serve leaf + intermediates (fullchain)."},
        {"q": "On open-source Nginx, how do you get automatic Let's Encrypt certificates?",
         "opts": ["Built-in ACME", "certbot (with the nginx plugin) + its renewal timer",
                  "ssl_auto on;", "It's not possible"],
         "answer": 1,
         "explain": "Nginx has no built-in ACME. certbot --nginx provisions and configures certs and "
                    "installs a systemd timer for renewal."},
    ],
    9: [
        {"q": "Which header reveals whether a response came from the proxy cache?",
         "opts": ["X-Cache-Status ($upstream_cache_status)", "X-Powered-By", "Via", "Cache-Control"],
         "answer": 0,
         "explain": "Adding `add_header X-Cache-Status $upstream_cache_status;` surfaces HIT/MISS/"
                    "EXPIRED/STALE — invaluable for debugging cache behavior."},
        {"q": "Why use $binary_remote_addr (not $remote_addr) as a rate-limit key?",
         "opts": ["It's more secure", "It's the compact form that fits far more entries in the zone",
                  "It includes the port", "It's required for IPv6"],
         "answer": 1,
         "explain": "The binary form is much smaller, so a fixed-size shared zone tracks many more "
                    "client IPs."},
    ],
    10: [
        {"q": "Behind a load balancer, why might allow/deny see the wrong IP?",
         "opts": ["A bug in Nginx", "$remote_addr is the LB's IP unless you use the realip module",
                  "deny is evaluated last", "TLS hides the IP"],
         "answer": 1,
         "explain": "Use set_real_ip_from + real_ip_header X-Forwarded-For so Nginx resolves the true "
                    "client IP for access control and logs."},
        {"q": "What does the `always` parameter on add_header do?",
         "opts": ["Caches the header", "Sends the header even on 4xx/5xx error responses",
                  "Makes it case-insensitive", "Forces HTTPS"],
         "answer": 1,
         "explain": "Without always, some headers are omitted on error responses. always ensures "
                    "things like HSTS are sent regardless of status."},
    ],
    11: [
        {"q": "For a plain HTTP→HTTPS redirect, what's the preferred directive?",
         "opts": ["rewrite", "return 301", "if", "proxy_pass"],
         "answer": 1,
         "explain": "`return 301 https://$host$request_uri;` is explicit and cheap. Reserve rewrite "
                    "for genuine regex URI transformations."},
        {"q": "Inside a location, which directives are fully safe inside `if`?",
         "opts": ["All of them", "Only return and rewrite", "add_header and proxy_pass", "None"],
         "answer": 1,
         "explain": "'If is Evil': inside location, only return and rewrite behave reliably in if. "
                    "Use map or separate locations for everything else."},
    ],
    12: [
        {"q": "How do you isolate whether latency is in Nginx or the backend?",
         "opts": ["Count requests", "Compare $request_time to $upstream_response_time",
                  "Read error_log", "Use ip_hash"],
         "answer": 1,
         "explain": "$request_time is total Nginx time; $upstream_response_time is backend time. The "
                    "gap tells you where the latency lives."},
        {"q": "What exposes basic Nginx connection metrics for Prometheus scraping?",
         "opts": ["access_log", "the stub_status module (+ nginx-prometheus-exporter)",
                  "error_log debug", "the map module"],
         "answer": 1,
         "explain": "stub_status reports connection/accept/request counters; the exporter turns it "
                    "into Prometheus metrics for Grafana."},
    ],
    13: [
        {"q": "Which signal performs a graceful config reload?",
         "opts": ["USR2", "HUP (nginx -s reload)", "TERM", "USR1"],
         "answer": 1,
         "explain": "HUP reloads config. USR2 upgrades the binary, WINCH gracefully stops workers, "
                    "QUIT graceful stop, USR1 reopens logs."},
        {"q": "After logrotate moves the log files, what must you do?",
         "opts": ["Restart Nginx", "nginx -s reopen (or USR1) so Nginx writes to the new files",
                  "Nothing", "Run nginx -t"],
         "answer": 1,
         "explain": "Nginx holds log files open; without a reopen it keeps writing to the rotated "
                    "(deleted) inode."},
    ],
    14: [
        {"q": "At roughly what scale does Nginx's perf edge over Caddy actually matter?",
         "opts": ["100 req/s", "1k connections", "100k+ concurrent connections", "It always matters"],
         "answer": 2,
         "explain": "The C event loop's lower per-connection overhead shows up at extreme scale. Below "
                    "that, the difference is rarely noticeable."},
        {"q": "Which tool is purpose-built as a dedicated extreme-scale L4/L7 load balancer?",
         "opts": ["Apache", "HAProxy", "Caddy", "Traefik"],
         "answer": 1,
         "explain": "HAProxy is the gold standard for dedicated load balancing. Nginx is a web server "
                    "that also balances load."},
    ],
}

DECISION_HTML = """
<div class="addon decision" id="decision-helper">
  <div class="addon-head">
    <span class="addon-kicker">Interactive</span>
    <h3>Should you use Nginx?</h3>
    <p class="addon-sub">Toggle what's true for your situation. Grounded in Parts 1.3 and 14.5.</p>
  </div>
  <div class="decision-grid">
    <label class="dchip"><input type="checkbox" data-w="nginx" value="2"> I need high-performance static serving and reverse proxying on real servers</label>
    <label class="dchip"><input type="checkbox" data-w="nginx" value="2"> I must sustain very high traffic / 100k+ concurrent connections</label>
    <label class="dchip"><input type="checkbox" data-w="nginx" value="1"> I want HTTP caching in front of a slow backend</label>
    <label class="dchip"><input type="checkbox" data-w="nginx" value="1"> My team already knows Nginx / I have existing configs</label>
    <label class="dchip"><input type="checkbox" data-w="nginx" value="1"> I need fine-grained location routing and rewrites</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="2"> I want HTTPS fully automatic with zero config</label>
    <label class="dchip"><input type="checkbox" data-w="traefik" value="2"> Docker/Kubernetes label auto-discovery is a core requirement</label>
    <label class="dchip"><input type="checkbox" data-w="haproxy" value="2"> I need a dedicated extreme-scale L4 load balancer</label>
    <label class="dchip"><input type="checkbox" data-w="envoy" value="2"> I'm building a service mesh data plane</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="1"> I want the shortest possible config and a single binary</label>
  </div>
  <div class="decision-out" id="decision-out" role="status" aria-live="polite">
    <span class="decision-verdict">Select options above for a recommendation.</span>
  </div>
</div>
"""

# nginx-specific decision logic (replaces the caddy verdict block in the shared JS)
DECISION_JS = r"""
  function setupDecision(){
    var box=document.getElementById('decision-helper'); if(!box)return;
    var out=document.getElementById('decision-out');
    function compute(){
      var w={nginx:0,caddy:0,traefik:0,haproxy:0,envoy:0};
      box.querySelectorAll('input:checked').forEach(function(c){ w[c.dataset.w]+=parseInt(c.value,10); });
      var total=w.nginx+w.caddy+w.traefik+w.haproxy+w.envoy;
      if(total===0){ out.innerHTML='<span class="decision-verdict">Select options above for a recommendation.</span>'; return; }
      var verdict,cls,reasons;
      var alt=Math.max(w.caddy,w.traefik,w.haproxy,w.envoy);
      if(w.envoy>=2 && w.envoy>=w.nginx){
        verdict='Consider Envoy'; cls='alt';
        reasons='A service-mesh data plane is Envoy\'s purpose (Istio, Consul Connect). Nginx can proxy, but a mesh wants Envoy\'s xDS control-plane model.';
      } else if(w.haproxy>=2 && w.haproxy>=w.nginx){
        verdict='Consider HAProxy'; cls='alt';
        reasons='For a dedicated, extreme-scale L4/L7 load balancer, HAProxy is purpose-built. Nginx is a web server that also balances load.';
      } else if(w.traefik>=2 && w.traefik>=w.nginx){
        verdict='Consider Traefik'; cls='alt';
        reasons='Container label auto-discovery is Traefik\'s native strength (and it does automatic HTTPS). Nginx reloads from files.';
      } else if(w.caddy>w.nginx){
        verdict='Caddy may fit better'; cls='alt';
        reasons='If zero-config HTTPS and the shortest possible config are your priorities, Caddy delivers those out of the box. See the companion Caddy guide.';
      } else if(alt>0 && w.nginx-alt<=1){
        verdict='Nginx works — with caveats'; cls='maybe';
        reasons='Nginx covers your core needs, but weigh the constraints you checked; a specialist (Caddy, Traefik, HAProxy, or Envoy) may be worth pairing in for that specific concern.';
      } else {
        verdict='Nginx is a strong fit'; cls='nginx';
        reasons='High-performance proxying/static serving, caching, and fine-grained routing on real servers are exactly Nginx\'s wheelhouse. Pair it with certbot for automatic TLS.';
      }
      out.innerHTML='<span class="decision-verdict '+cls+'">'+verdict+'</span><p class="decision-reasons">'+reasons+'</p>';
    }
    box.addEventListener('change',compute);
  }
"""

# --------------------------------------------------------------------------- #
# Transform + page assembly
# --------------------------------------------------------------------------- #

def render_quiz(part_num):
    items = QUIZZES.get(part_num)
    if not items:
        return ""
    rows = []
    for i, item in enumerate(items, 1):
        opts = []
        for j, opt in enumerate(item["opts"]):
            correct = "true" if j == item["answer"] else "false"
            opts.append(
                f'<li><button class="quiz-opt" data-correct="{correct}">'
                f'<span class="quiz-mark" aria-hidden="true"></span>'
                f'<span class="quiz-opt-text">{_html.escape(opt)}</span></button></li>'
            )
        rows.append(
            '<div class="quiz-item">'
            f'<p class="quiz-q"><span class="quiz-n">Q{i}</span>{_html.escape(item["q"])}</p>'
            f'<ul class="quiz-opts">{"".join(opts)}</ul>'
            f'<div class="quiz-explain" hidden>{_html.escape(item["explain"])}</div>'
            "</div>"
        )
    return (
        '<div class="addon quiz">'
        '<div class="addon-head"><span class="addon-kicker">Self-check</span>'
        '<h3>Test yourself</h3>'
        '<p class="addon-sub">Pick an answer to reveal the explanation.</p></div>'
        f'{"".join(rows)}</div>'
    )


def transform(md_text):
    # Local import avoids a circular import: build_guide imports CSS/JS from here.
    from build_guide import extract_mermaid_blocks, restore_mermaid_blocks

    md_text, diagrams = extract_mermaid_blocks(md_text)
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "attr_list", "sane_lists"],
        output_format="html5",
    )
    body = md.convert(md_text)
    body = restore_mermaid_blocks(body, diagrams)

    def norm_code(m):
        cls = m.group(1)
        lang = ""
        for tok in cls.split():
            if tok.startswith("language-"):
                lang = tok[len("language-"):]
            elif tok and not lang:
                lang = tok
        return f'<pre><code class="language-{lang or "text"}">'

    body = re.sub(r'<pre><code class="([^"]*)">', norm_code, body)
    body = body.replace("<pre><code>", '<pre><code class="language-text">')

    toc_html = ['<nav class="toc" aria-label="Table of contents"><ul>']
    for m in re.finditer(r'<h([23])\s+id="([^"]+)">(.*?)</h\1>', body, re.S):
        level, hid, inner = m.group(1), m.group(2), m.group(3)
        label = re.sub(r"<[^>]+>", "", inner).strip()
        if label.lower() == "table of contents":
            continue
        cls = "toc-l2" if level == "2" else "toc-l3"
        toc_html.append(f'<li class="{cls}"><a href="#{hid}" data-target="{hid}">{label}</a></li>')
    toc_html.append("</ul></nav>")
    toc_html = "".join(toc_html)

    chunks = re.split(r"(?=<h2 )", body)
    out = []
    for chunk in chunks:
        mnum = re.match(r'<h2 [^>]*>\s*Part\s+(\d+)', chunk)
        if not mnum:
            out.append(chunk)
            continue
        part = int(mnum.group(1))
        addon = (DECISION_HTML if part == 1 else "") + render_quiz(part)
        if addon:
            m_hr = re.search(r"(\s*<hr\s*/?>\s*)$", chunk)
            if m_hr:
                chunk = chunk[: m_hr.start()] + addon + m_hr.group(1)
            else:
                chunk += addon
        out.append(chunk)
    return toc_html, "".join(out)


PAGE = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="description" content="An interactive, depth-first study guide to Nginx: architecture, configuration contexts, server blocks, location matching, reverse proxy and load balancing, TLS, caching, performance, security, and production operations.">
<title>Nginx Study Guide - Interactive</title>
<style>__CSS__</style>
</head>
<body>
<div id="progress"></div>
<header class="topbar">
  <button id="menuBtn" class="iconbtn" aria-label="Toggle menu">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
  <div class="brand"><span class="logo">N</span><span>Nginx Study Guide</span><span class="sub">interactive</span></div>
  <div class="spacer"></div>
  <div class="search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="search" type="search" placeholder="Search the guide..." aria-label="Search" autocomplete="off">
    <kbd>/</kbd>
  </div>
  <button id="themeBtn" class="iconbtn" aria-label="Toggle theme" title="Toggle theme (t)">
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  </button>
</header>
<div class="scrim"></div>
<div class="layout">
  <aside class="sidebar">__TOC__</aside>
  <main>__BODY__</main>
</div>
<button id="toTop" aria-label="Back to top">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
</button>
<script>__JS__</script>
</body>
</html>
"""

# Accent retune for nginx (green brand) + nginx decision-verdict color.
NGINX_CSS = (CSS
             .replace("--accent:#2dd4bf;", "--accent:#3fb950;")
             .replace("--accent2:#38bdf8;", "--accent2:#56d364;")
             .replace("--accent-weak:rgba(45,212,191,.12);", "--accent-weak:rgba(63,185,80,.13);")
             .replace("--accent:#0d9488;", "--accent:#1a7f37;")
             .replace("--accent2:#0284c7;", "--accent2:#1f883d;")
             .replace("--accent-weak:rgba(13,148,136,.10);", "--accent-weak:rgba(26,127,55,.10);")
             + "\n.decision-verdict.nginx{color:var(--good)}\n")

# Swap the caddy decision logic in the shared JS for the nginx version.
NGINX_JS = re.sub(
    r"  function setupDecision\(\)\{.*?\n  \}\n",
    DECISION_JS + "\n",
    JS,
    count=1,
    flags=re.S,
)


def main():
    toc_html, body = transform(NGINX_MD)
    page = (PAGE
            .replace("__CSS__", NGINX_CSS)
            .replace("__TOC__", toc_html)
            .replace("__BODY__", body)
            .replace("__JS__", NGINX_JS))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote", OUT, "(", len(page), "bytes )")


if __name__ == "__main__":
    main()

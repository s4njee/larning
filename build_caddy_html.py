#!/usr/bin/env python3
"""
Build an interactive, responsive, black-themed HTML page from CADDY_STUDY_GUIDE.md.

Self-contained single file output (no external network deps at view time):
  - scroll-spy sidebar TOC
  - per-code-block copy buttons + language badges
  - lightweight custom syntax highlighting (Caddyfile, bash, json, nginx, yaml, ini, dockerfile)
  - live search / filter
  - collapsible parts
  - reading-progress bar + back-to-top
  - dark(black)/light theme toggle (persisted)
  - quality add-ons: per-part self-check quizzes + a "Should I use Caddy?" decision helper
"""

import re
import html as _html
import markdown

SRC = "CADDY_STUDY_GUIDE.md"
OUT = "html/caddy-study-guide.html"

# --------------------------------------------------------------------------- #
# Quality add-on content (grounded directly in the guide).
# --------------------------------------------------------------------------- #

QUIZZES = {
    1: [
        {
            "q": "What single feature most distinguishes Caddy from Nginx, Apache, and HAProxy?",
            "opts": [
                "Automatic HTTPS by default, with zero TLS configuration",
                "It is written in Go",
                "It supports reverse proxying",
                "It can serve static files",
            ],
            "answer": 0,
            "explain": "All of those servers can do ACME — but only Caddy obtains, configures, "
                       "redirects, and renews certificates out of the box with no configuration.",
        },
        {
            "q": "What is Caddy's actual internal configuration format?",
            "opts": ["The Caddyfile", "YAML", "JSON (the Caddyfile is adapted into it)", "TOML"],
            "answer": 2,
            "explain": "The Caddyfile is syntactic sugar. A config adapter compiles it to JSON, "
                       "which is Caddy's native truth and what the admin API speaks.",
        },
        {
            "q": "Does the order you write directives in the Caddyfile determine their execution order?",
            "opts": [
                "Yes — top to bottom, like Nginx",
                "No — Caddy uses a predefined directive order regardless of file position",
                "Only inside site blocks",
                "Only for matchers",
            ],
            "answer": 1,
            "explain": "Caddy has a fixed directive order (redir before rewrite before reverse_proxy "
                       "before file_server). Use the `route` directive to force written order.",
        },
    ],
    2: [
        {
            "q": "Which tool builds a custom Caddy binary with third-party modules baked in?",
            "opts": ["go build", "xcaddy", "caddy plugin install", "apt"],
            "answer": 1,
            "explain": "`xcaddy build --with <module>` compiles a new binary. Caddy modules are "
                       "compiled in at build time, not loaded dynamically.",
        },
        {
            "q": "In the Docker setup, which volume is critical to persist?",
            "opts": ["/config", "/etc/caddy", "/data (certificates + ACME state)", "/var/log"],
            "answer": 2,
            "explain": "Losing /data means re-requesting every certificate on next start, which can "
                       "hit Let's Encrypt rate limits (50 certs per registered domain per week).",
        },
    ],
    3: [
        {
            "q": "What is the difference between `handle` and `handle_path`?",
            "opts": [
                "handle is for files, handle_path is for proxies",
                "handle_path strips the matched path prefix; handle does not",
                "They are identical",
                "handle_path requires a regex",
            ],
            "answer": 1,
            "explain": "handle_path /api/* strips /api before passing on (so the backend sees /users, "
                       "not /api/users). Both are mutually exclusive routers — first match wins.",
        },
        {
            "q": "Within a single named matcher block, multiple conditions are combined with…",
            "opts": ["OR", "AND", "XOR", "NAND"],
            "answer": 1,
            "explain": "Conditions inside one matcher are ANDed. To OR, use multiple matchers or a "
                       "CEL `expression` matcher.",
        },
    ],
    4: [
        {
            "q": "Which ACME challenge type is required for a wildcard certificate (*.example.com)?",
            "opts": ["HTTP-01", "TLS-ALPN-01", "DNS-01", "Any of them"],
            "answer": 2,
            "explain": "HTTP-01 and TLS-ALPN-01 can only prove ownership of a specific hostname. "
                       "Wildcards need DNS-01, which requires a DNS provider plugin.",
        },
        {
            "q": "What does the on-demand TLS `ask` endpoint protect against?",
            "opts": [
                "Slow TLS handshakes",
                "Anyone pointing a domain at your server and exhausting your ACME rate limits",
                "Expired certificates",
                "OCSP failures",
            ],
            "answer": 1,
            "explain": "Without the `ask` gate, Caddy would obtain a cert for any hostname presented "
                       "at handshake time — a rate-limit and abuse vector.",
        },
    ],
    5: [
        {
            "q": "Which `flush_interval` value is required for Server-Sent Events / streaming?",
            "opts": ["0", "-1 (flush immediately)", "30s", "1ms"],
            "answer": 1,
            "explain": "flush_interval -1 disables buffering so the client sees events in real time.",
        },
        {
            "q": "What is Caddy's default load-balancing policy across multiple upstreams?",
            "opts": ["round_robin", "least_conn", "random", "ip_hash"],
            "answer": 2,
            "explain": "random is the default — and surprisingly effective for most workloads. "
                       "round_robin, least_conn, cookie, and others are opt-in.",
        },
    ],
    6: [
        {
            "q": "Which directive gives a single-page app its index.html fallback?",
            "opts": ["rewrite", "try_files {path} /index.html", "redir", "respond"],
            "answer": 1,
            "explain": "try_files internally rewrites to the first file that exists, falling back to "
                       "index.html so the client-side router can take over. No redirect is issued.",
        },
    ],
    7: [
        {
            "q": "What is the difference between `redir` and `rewrite`?",
            "opts": [
                "redir is faster",
                "redir sends a 3xx to the client; rewrite changes the URI internally and invisibly",
                "rewrite issues a 301",
                "They are aliases",
            ],
            "answer": 1,
            "explain": "redir tells the browser to go elsewhere (301/302/307). rewrite silently "
                       "changes the URI before the next handler — the client never knows.",
        },
        {
            "q": "In the `header` directive, what does a leading `-` (e.g. `-Server`) do?",
            "opts": ["Sets the header", "Appends the header", "Deletes the header", "Defers the header"],
            "answer": 2,
            "explain": "`-Name` deletes. `+Name` appends, `Name` sets/replaces, `>Name` defers until "
                       "after other handlers run.",
        },
    ],
    8: [
        {
            "q": "In what format does `basic_auth` store passwords?",
            "opts": ["Plaintext", "SHA-256", "bcrypt hash (via `caddy hash-password`)", "Base64"],
            "answer": 2,
            "explain": "Passwords are bcrypt hashes. basic_auth is only safe over HTTPS — which Caddy "
                       "provides by default.",
        },
        {
            "q": "With `forward_auth`, the request proceeds to the backend when the auth service returns…",
            "opts": ["Any response", "A 2xx status", "A 401", "A redirect"],
            "answer": 1,
            "explain": "2xx means allowed (and copy_headers passes identity to the backend). Anything "
                       "else is forwarded to the client, typically a login redirect.",
        },
    ],
    9: [
        {
            "q": "What is the default listen address of Caddy's admin API?",
            "opts": ["0.0.0.0:2019", "localhost:2019", "localhost:443", "localhost:80"],
            "answer": 1,
            "explain": "It defaults to localhost:2019 — safe because it requires host access. Never "
                       "expose it to the public internet.",
        },
        {
            "q": "Which command converts a Caddyfile to its JSON equivalent?",
            "opts": ["caddy json", "caddy adapt", "caddy convert", "caddy export"],
            "answer": 1,
            "explain": "`caddy adapt --config Caddyfile --pretty` shows the JSON the Caddyfile compiles to.",
        },
    ],
    10: [
        {
            "q": "Which directive suppresses access logs for noisy endpoints like health checks?",
            "opts": ["log off", "skip_log", "no_log", "silence"],
            "answer": 1,
            "explain": "skip_log inside a handle block keeps health-check spam out of your access logs.",
        },
        {
            "q": "What Prometheus metric type is `caddy_http_request_duration_seconds`?",
            "opts": ["Counter", "Gauge", "Histogram", "Summary"],
            "answer": 2,
            "explain": "Latency is a Histogram (buckets you can compute quantiles from). "
                       "requests_total is a Counter; requests_in_flight is a Gauge.",
        },
    ],
    11: [
        {
            "q": "Why does the systemd unit use `Type=notify`?",
            "opts": [
                "It restarts Caddy on failure",
                "Caddy signals systemd when it is actually ready to serve, not just started",
                "It enables logging",
                "It is required for Docker",
            ],
            "answer": 1,
            "explain": "With Type=notify, `systemctl start caddy` blocks until Caddy is truly listening, "
                       "so dependent units start in the right order.",
        },
        {
            "q": "Which Linux capability lets the non-root caddy user bind to ports 80 and 443?",
            "opts": ["CAP_SYS_ADMIN", "CAP_NET_RAW", "CAP_NET_BIND_SERVICE", "CAP_DAC_OVERRIDE"],
            "answer": 2,
            "explain": "CAP_NET_BIND_SERVICE grants binding to privileged ports without running as root.",
        },
    ],
    12: [
        {
            "q": "At roughly what scale does Nginx's raw performance advantage actually start to matter?",
            "opts": ["100 req/s", "1,000 concurrent connections", "100k+ concurrent connections", "It always matters"],
            "answer": 2,
            "explain": "For ~99% of workloads you won't notice. The C event loop's lower per-connection "
                       "overhead shows up at extreme scale (100k+ concurrent).",
        },
        {
            "q": "Which alternative is the strongest pick when you want Docker label-based auto-discovery?",
            "opts": ["HAProxy", "Envoy", "Traefik", "Apache"],
            "answer": 2,
            "explain": "Traefik auto-discovers containers via Docker labels natively. Caddy can with "
                       "plugins, but Traefik does it out of the box.",
        },
    ],
    13: [
        {
            "q": "For a SPA, how should hashed build assets vs. index.html be cached?",
            "opts": [
                "Both no-cache",
                "Both immutable forever",
                "Assets: immutable max-age=31536000; index.html: no-cache",
                "Assets: no-cache; index.html: immutable",
            ],
            "answer": 2,
            "explain": "Hashed asset filenames change on every build, so cache them forever (immutable). "
                       "index.html references them by hash, so it must never be cached.",
        },
    ],
}

DECISION_HTML = """
<div class="addon decision" id="decision-helper">
  <div class="addon-head">
    <span class="addon-kicker">Interactive</span>
    <h3>Should you use Caddy?</h3>
    <p class="addon-sub">Toggle what's true for your situation. Grounded in Part 1.4 and Part 12.6.</p>
  </div>
  <div class="decision-grid">
    <label class="dchip"><input type="checkbox" data-w="caddy" value="2"> I want HTTPS handled automatically (no certbot/cron)</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="2"> Config simplicity matters more than ecosystem size</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="1"> I need local-dev HTTPS without cert warnings</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="1"> Single static binary / edge or Raspberry Pi deploy</label>
    <label class="dchip"><input type="checkbox" data-w="caddy" value="1"> I want dynamic reconfiguration via an HTTP API</label>
    <label class="dchip"><input type="checkbox" data-w="against" value="2"> I must sustain 100k+ concurrent connections</label>
    <label class="dchip"><input type="checkbox" data-w="against" value="2"> I need a dedicated L4 load balancer or service mesh data plane</label>
    <label class="dchip"><input type="checkbox" data-w="traefik" value="2"> Docker-label auto-discovery is a core requirement</label>
    <label class="dchip"><input type="checkbox" data-w="against" value="1"> I need a WAF (ModSecurity-style)</label>
    <label class="dchip"><input type="checkbox" data-w="against" value="1"> My team runs Nginx well with no pain points</label>
  </div>
  <div class="decision-out" id="decision-out" role="status" aria-live="polite">
    <span class="decision-verdict">Select options above for a recommendation.</span>
  </div>
</div>
"""


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


# --------------------------------------------------------------------------- #
# Markdown -> HTML
# --------------------------------------------------------------------------- #

def build():
    with open(SRC, encoding="utf-8") as f:
        text = f.read()

    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "attr_list", "sane_lists"],
        output_format="html5",
    )
    body = md.convert(text)

    # Normalize code language classes to `language-xxx`.
    def norm_code(m):
        cls = m.group(1)
        lang = ""
        for tok in cls.split():
            if tok.startswith("language-"):
                lang = tok[len("language-"):]
            elif tok and not lang:
                lang = tok
        lang = lang or "text"
        return f'<pre><code class="language-{lang}">'

    body = re.sub(r'<pre><code class="([^"]*)">', norm_code, body)
    body = body.replace("<pre><code>", '<pre><code class="language-text">')

    # Build sidebar TOC from h2/h3.
    toc_entries = []
    for m in re.finditer(r'<h([23])\s+id="([^"]+)">(.*?)</h\1>', body, re.S):
        level, hid, inner = m.group(1), m.group(2), m.group(3)
        label = re.sub(r"<[^>]+>", "", inner).strip()
        toc_entries.append((level, hid, label))

    toc_html = ['<nav class="toc" aria-label="Table of contents"><ul>']
    for level, hid, label in toc_entries:
        if label.lower() == "table of contents":
            continue
        cls = "toc-l2" if level == "2" else "toc-l3"
        toc_html.append(
            f'<li class="{cls}"><a href="#{hid}" data-target="{hid}">{label}</a></li>'
        )
    toc_html.append("</ul></nav>")
    toc_html = "".join(toc_html)

    # Inject decision helper (after Part 1) and quizzes (end of each part).
    chunks = re.split(r"(?=<h2 )", body)
    out_chunks = []
    for chunk in chunks:
        mnum = re.match(r'<h2 [^>]*>\s*Part\s+(\d+)', chunk)
        if not mnum:
            out_chunks.append(chunk)
            continue
        part_num = int(mnum.group(1))
        addon = ""
        if part_num == 1:
            addon += DECISION_HTML
        addon += render_quiz(part_num)
        if addon:
            # Insert before a trailing <hr /> if present, else append.
            m_hr = re.search(r"(\s*<hr\s*/?>\s*)$", chunk)
            if m_hr:
                chunk = chunk[: m_hr.start()] + addon + m_hr.group(1)
            else:
                chunk = chunk + addon
        out_chunks.append(chunk)
    body = "".join(out_chunks)

    return toc_html, body


# --------------------------------------------------------------------------- #
# Page template (CSS + JS). Kept brace-safe via .replace placeholders.
# --------------------------------------------------------------------------- #

CSS = r"""
:root{
  --bg:#08090b; --bg2:#0e0f13; --panel:#121319; --panel2:#171922;
  --border:#23252f; --border2:#2c2f3b;
  --txt:#e6e8ee; --muted:#9aa0ad; --faint:#6b7180;
  --accent:#2dd4bf; --accent2:#38bdf8; --accent-weak:rgba(45,212,191,.12);
  --warn:#fbbf24; --good:#4ade80; --bad:#f87171;
  --radius:12px; --radius-sm:8px;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --sidebar-w:310px;
}
html[data-theme="light"]{
  --bg:#f6f7f9; --bg2:#eef0f4; --panel:#ffffff; --panel2:#f3f4f7;
  --border:#e2e5eb; --border2:#d3d7e0;
  --txt:#1b1f27; --muted:#5a6170; --faint:#878e9c;
  --accent:#0d9488; --accent2:#0284c7; --accent-weak:rgba(13,148,136,.10);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--bg);color:var(--txt);font-family:var(--sans);
  line-height:1.65;font-size:16px;-webkit-font-smoothing:antialiased;
}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}

/* progress bar */
#progress{position:fixed;top:0;left:0;height:3px;width:0;z-index:60;
  background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .1s linear}

/* top bar */
header.topbar{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:14px;
  padding:10px 18px;background:rgba(8,9,11,.82);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--border);
}
html[data-theme="light"] header.topbar{background:rgba(246,247,249,.85)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:-.01em;white-space:nowrap}
.brand .logo{width:26px;height:26px;border-radius:7px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04201c;font-weight:800;font-size:15px}
.brand .sub{color:var(--faint);font-weight:500;font-size:13px}
.spacer{flex:1}
.search{position:relative;display:flex;align-items:center;max-width:340px;flex:1}
.search input{
  width:100%;padding:8px 12px 8px 34px;border-radius:999px;border:1px solid var(--border2);
  background:var(--panel);color:var(--txt);font-size:14px;outline:none}
.search input:focus{border-color:var(--accent)}
.search svg{position:absolute;left:11px;width:15px;height:15px;color:var(--faint);pointer-events:none}
.search kbd{position:absolute;right:10px;color:var(--faint);font-family:var(--mono);font-size:11px;
  border:1px solid var(--border2);border-radius:5px;padding:1px 5px;background:var(--bg2)}
.iconbtn{display:grid;place-items:center;width:38px;height:38px;border-radius:9px;cursor:pointer;
  border:1px solid var(--border2);background:var(--panel);color:var(--txt)}
.iconbtn:hover{border-color:var(--accent)}
#menuBtn{display:none}

/* layout */
.layout{display:grid;grid-template-columns:var(--sidebar-w) minmax(0,1fr);gap:0;align-items:start}
aside.sidebar{
  position:sticky;top:59px;height:calc(100vh - 59px);overflow-y:auto;
  border-right:1px solid var(--border);padding:18px 10px 60px;background:var(--bg)}
aside.sidebar::-webkit-scrollbar{width:9px}
aside.sidebar::-webkit-scrollbar-thumb{background:var(--border2);border-radius:9px}
.toc ul{list-style:none;margin:0;padding:0}
.toc li a{display:block;padding:5px 12px;border-radius:7px;color:var(--muted);font-size:13.5px;
  border-left:2px solid transparent;transition:color .12s,background .12s}
.toc li a:hover{color:var(--txt);background:var(--panel);text-decoration:none}
.toc .toc-l2 a{font-weight:600;color:var(--txt);margin-top:6px}
.toc .toc-l3 a{padding-left:26px;font-size:12.8px}
.toc a.active{color:var(--accent);background:var(--accent-weak);border-left-color:var(--accent)}
.toc li.hide{display:none}

main{padding:32px clamp(18px,5vw,64px) 120px;max-width:1000px;min-width:0;overflow-wrap:break-word}
.lead{color:var(--muted);font-size:15px}

/* typography */
h1{font-size:clamp(28px,4vw,40px);line-height:1.15;letter-spacing:-.02em;margin:.2em 0 .4em}
h2{font-size:clamp(22px,3vw,29px);letter-spacing:-.01em;margin:2.2em 0 .7em;padding-bottom:.3em;
  border-bottom:1px solid var(--border);scroll-margin-top:74px;cursor:pointer;position:relative}
h2::after{content:"–";position:absolute;right:2px;top:0;color:var(--faint);font-weight:400;
  transition:transform .15s;opacity:.6}
h2.collapsed::after{content:"+"}
h3{font-size:19px;margin:1.8em 0 .5em;color:var(--txt);scroll-margin-top:74px}
h2+*,h3+*{margin-top:0}
p{margin:.7em 0}
strong{color:var(--txt)}
blockquote{margin:1.1em 0;padding:.6em 1.1em;border-left:3px solid var(--accent);
  background:var(--accent-weak);border-radius:0 var(--radius-sm) var(--radius-sm) 0;color:var(--txt)}
blockquote em{font-style:italic;color:var(--txt)}
hr{border:none;border-top:1px solid var(--border);margin:2.4em 0}
ul,ol{padding-left:1.3em}
li{margin:.3em 0}

/* inline code */
:not(pre)>code{font-family:var(--mono);font-size:.86em;background:var(--panel2);
  border:1px solid var(--border);border-radius:6px;padding:.1em .4em;color:#e7c6a0}
html[data-theme="light"] :not(pre)>code{color:#9a5b00}

/* code blocks */
.codewrap{position:relative;margin:1.2em 0;border:1px solid var(--border);border-radius:var(--radius);
  background:var(--bg2);overflow:hidden}
.codebar{display:flex;align-items:center;justify-content:space-between;
  padding:7px 12px;background:var(--panel);border-bottom:1px solid var(--border)}
.codebar .lang{font-family:var(--mono);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.copybtn{display:inline-flex;align-items:center;gap:6px;cursor:pointer;border:1px solid var(--border2);
  background:var(--bg2);color:var(--muted);font-size:12px;padding:4px 9px;border-radius:7px;font-family:var(--sans)}
.copybtn:hover{border-color:var(--accent);color:var(--txt)}
.copybtn.ok{color:var(--good);border-color:var(--good)}
.codewrap pre{margin:0;padding:14px 16px;overflow-x:auto;font-family:var(--mono);font-size:13.3px;line-height:1.6}
.codewrap pre::-webkit-scrollbar{height:9px}
.codewrap pre::-webkit-scrollbar-thumb{background:var(--border2);border-radius:9px}
code .c{color:#6b7180;font-style:italic}      /* comment */
code .s{color:#9ece9a}                          /* string */
code .k{color:#7dd3fc}                          /* keyword/directive */
code .n{color:#e5b873}                          /* number/duration */
code .ph{color:#f0abfc}                         /* placeholder {..} */
code .m{color:#fca5a5}                           /* matcher @name */
code .a{color:#7dd3fc}                           /* attr/key */
code .b{color:#f0abfc}                           /* boolean/const */
code .p{color:#8b93a3}                           /* punctuation */
code .site{color:#5eead4;font-weight:600}        /* site address */

/* tables */
.tablewrap{overflow-x:auto;margin:1.2em 0;border:1px solid var(--border);border-radius:var(--radius)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:9px 13px;border-bottom:1px solid var(--border)}
thead th{background:var(--panel);color:var(--txt);font-weight:600;position:sticky;top:0}
tbody tr:hover{background:var(--panel2)}
tbody tr:last-child td{border-bottom:none}

/* add-ons: quiz + decision */
.addon{margin:1.8em 0;border:1px solid var(--border2);border-radius:var(--radius);
  background:linear-gradient(180deg,var(--panel),var(--bg2));overflow:hidden}
.addon-head{padding:16px 18px 4px}
.addon-kicker{display:inline-block;font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:700}
.addon-head h3{margin:.25em 0 .1em;scroll-margin-top:0}
.addon-sub{margin:.1em 0 0;color:var(--faint);font-size:13.5px}
.quiz-item{padding:8px 18px 16px;border-top:1px solid var(--border);margin-top:12px}
.quiz-item:first-of-type{border-top:none;margin-top:0}
.quiz-q{font-weight:600;margin:.6em 0 .7em}
.quiz-n{display:inline-grid;place-items:center;min-width:26px;height:22px;margin-right:9px;padding:0 6px;
  border-radius:6px;background:var(--accent-weak);color:var(--accent);font-size:12px;font-weight:700;font-family:var(--mono)}
.quiz-opts{list-style:none;padding:0;margin:0;display:grid;gap:7px}
.quiz-opt{display:flex;align-items:center;gap:10px;width:100%;text-align:left;cursor:pointer;
  border:1px solid var(--border2);background:var(--bg2);color:var(--txt);font-size:14px;
  padding:9px 12px;border-radius:9px;font-family:var(--sans);transition:border-color .12s,background .12s}
.quiz-opt:hover{border-color:var(--accent)}
.quiz-mark{width:16px;height:16px;border-radius:50%;border:2px solid var(--faint);flex:none}
.quiz-opt.correct{border-color:var(--good);background:rgba(74,222,128,.10)}
.quiz-opt.correct .quiz-mark{border-color:var(--good);background:var(--good)}
.quiz-opt.wrong{border-color:var(--bad);background:rgba(248,113,113,.10)}
.quiz-opt.wrong .quiz-mark{border-color:var(--bad);background:var(--bad)}
.quiz-opt.locked{cursor:default;opacity:.7}
.quiz-opt.locked.correct,.quiz-opt.locked.wrong{opacity:1}
.quiz-explain{margin:11px 0 2px;padding:10px 12px;border-radius:8px;background:var(--panel2);
  border-left:3px solid var(--accent);font-size:13.6px;color:var(--muted)}

.decision-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;padding:14px 18px}
.dchip{display:flex;align-items:flex-start;gap:9px;font-size:13.6px;color:var(--txt);cursor:pointer;
  border:1px solid var(--border2);background:var(--bg2);padding:9px 11px;border-radius:9px}
.dchip:hover{border-color:var(--accent)}
.dchip input{margin-top:2px;accent-color:var(--accent)}
.decision-out{margin:4px 18px 18px;padding:14px 16px;border-radius:10px;background:var(--panel2);
  border:1px solid var(--border)}
.decision-verdict{font-weight:700;font-size:15px}
.decision-verdict.caddy{color:var(--good)}
.decision-verdict.maybe{color:var(--warn)}
.decision-verdict.alt{color:var(--accent2)}
.decision-reasons{margin:8px 0 0;color:var(--muted);font-size:13.5px}

/* search highlight */
mark.hit{background:var(--accent);color:#04201c;border-radius:3px;padding:0 2px}

/* back to top */
#toTop{position:fixed;right:22px;bottom:22px;width:44px;height:44px;border-radius:50%;
  display:grid;place-items:center;cursor:pointer;border:1px solid var(--border2);
  background:var(--panel);color:var(--txt);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s}
#toTop.show{opacity:1;pointer-events:auto}
#toTop:hover{border-color:var(--accent);transform:translateY(-2px)}

.scrim{display:none}
.collapsed-body{display:none !important}

@media(max-width:980px){
  :root{--sidebar-w:0px}
  #menuBtn{display:grid}
  .layout{grid-template-columns:minmax(0,1fr)}
  aside.sidebar{position:fixed;top:0;left:0;height:100vh;width:300px;z-index:70;
    transform:translateX(-100%);transition:transform .25s;border-right:1px solid var(--border);
    padding-top:16px;background:var(--bg)}
  aside.sidebar.open{transform:none}
  .scrim.show{display:block;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:65}
  .search{max-width:none}
  .brand .sub{display:none}
  .decision-grid{grid-template-columns:1fr}
}
@media(max-width:560px){
  body{font-size:15px}
  .search kbd{display:none}
  main{padding:22px 16px 100px}
  .spacer{display:none}
  .brand{flex:1;min-width:0}
  .brand > span:not(.logo):not(.sub){flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
}
"""

JS = r"""
(function(){
  'use strict';
  var ESC={'&':'&amp;','<':'&lt;','>':'&gt;'};
  function esc(s){return s.replace(/[&<>]/g,function(c){return ESC[c];});}

  /* ---------- lightweight syntax highlighting ---------- */
  // Generic token-rule engine. Each rule: {re, cls}. First match at pos wins.
  function tokenize(src, rules){
    var out='', i=0, n=src.length, guard=0;
    while(i<n && guard++<200000){
      var matched=false;
      for(var r=0;r<rules.length;r++){
        rules[r].re.lastIndex=i;
        var m=rules[r].re.exec(src);
        if(m && m.index===i && m[0].length>0){
          out+= rules[r].cls? '<span class="'+rules[r].cls+'">'+esc(m[0])+'</span>' : esc(m[0]);
          i+=m[0].length; matched=true; break;
        }
      }
      if(!matched){ out+=esc(src[i]); i++; }
    }
    if(i<n) out+=esc(src.slice(i));
    return out;
  }
  var DIRECTIVES=('reverse_proxy file_server root encode header redir rewrite respond tls log '
    +'basic_auth forward_auth handle handle_path handle_errors import route uri templates '
    +'try_files metrics tracing request_body skip_log map vars push bind').split(' ');
  var GLOBALS=('email acme_ca admin default_sni order debug auto_https on_demand_tls servers '
    +'storage grace_period http_port https_port').split(' ');
  function caddyRules(){
    var dir='\\b(?:'+DIRECTIVES.concat(GLOBALS).join('|')+')\\b';
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/"(?:[^"\\]|\\.)*"/g, cls:'s'},
      {re:/\{[^{}\n]*\}/g, cls:'ph'},          // placeholders {http.request.host}
      {re:/@[A-Za-z0-9_-]+/g, cls:'m'},        // named matchers
      {re:new RegExp(dir,'g'), cls:'k'},
      {re:/\b\d+(?:\.\d+)?(?:ms|s|m|h|d|[KMGT]i?B?)?\b/g, cls:'n'},
      {re:/^[ \t]*(?:https?:\/\/)?[A-Za-z0-9*][A-Za-z0-9.\-*]*\.[A-Za-z][A-Za-z0-9.\-:]*(?=[ ,{])/gm, cls:'site'},
      {re:/[:|]\d{2,5}\b/g, cls:'site'},
      {re:/[{}]/g, cls:'p'}
    ];
  }
  function bashRules(){
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/"(?:[^"\\]|\\.)*"/g, cls:'s'},
      {re:/'(?:[^'\\]|\\.)*'/g, cls:'s'},
      {re:/\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*/g, cls:'ph'},
      {re:/\b(sudo|curl|apt|dnf|brew|pacman|scoop|choco|go|xcaddy|caddy|systemctl|journalctl|docker|openssl|ulimit|export|chmod|mv|tee|gpg)\b/g, cls:'k'},
      {re:/\s-{1,2}[A-Za-z][\w-]*/g, cls:'n'}
    ];
  }
  function jsonRules(){
    return [
      {re:/"(?:[^"\\]|\\.)*"(?=\s*:)/g, cls:'a'},
      {re:/"(?:[^"\\]|\\.)*"/g, cls:'s'},
      {re:/\b(true|false|null)\b/g, cls:'b'},
      {re:/-?\b\d+(?:\.\d+)?\b/g, cls:'n'},
      {re:/[{}\[\],:]/g, cls:'p'}
    ];
  }
  var NGINX_KW=('http events main stream upstream server location map geo types charset_map split_clients '
    +'listen server_name root alias index autoindex try_files return rewrite error_page internal default_type '
    +'include set if set_real_ip_from real_ip_header real_ip_recursive '
    +'proxy_pass proxy_set_header proxy_http_version proxy_buffering proxy_buffers proxy_buffer_size '
    +'proxy_cache proxy_cache_path proxy_cache_valid proxy_cache_key proxy_cache_use_stale proxy_cache_lock '
    +'proxy_read_timeout proxy_connect_timeout proxy_send_timeout proxy_redirect proxy_ssl_server_name proxy_pass_request_headers '
    +'fastcgi_pass fastcgi_param fastcgi_cache fastcgi_index scgi_pass uwsgi_pass grpc_pass '
    +'ssl_certificate ssl_certificate_key ssl_protocols ssl_ciphers ssl_prefer_server_ciphers ssl_session_cache '
    +'ssl_session_timeout ssl_session_tickets ssl_stapling ssl_stapling_verify ssl_dhparam ssl_early_data ssl_trusted_certificate '
    +'resolver resolver_timeout http2 http3 quic '
    +'gzip gzip_types gzip_comp_level gzip_min_length gzip_vary gzip_proxied brotli brotli_types brotli_comp_level '
    +'add_header add_trailer expires etag sendfile sendfile_max_chunk tcp_nopush tcp_nodelay keepalive_timeout keepalive keepalive_requests '
    +'worker_processes worker_connections worker_rlimit_nofile worker_priority multi_accept use pid user '
    +'client_max_body_size client_body_buffer_size client_body_timeout client_header_timeout large_client_header_buffers send_timeout '
    +'limit_req limit_req_zone limit_req_status limit_conn limit_conn_zone limit_conn_status limit_rate limit_rate_after '
    +'access_log error_log log_format open_log_file_cache stub_status open_file_cache open_file_cache_valid '
    +'allow deny auth_basic auth_basic_user_file satisfy auth_request '
    +'least_conn ip_hash hash zone server weight max_fails fail_timeout backup down slow_start '
    +'absolute_redirect server_tokens merge_slashes underscores_in_headers types_hash_max_size variables_hash_max_size').split(' ');
  var NGINX_CONST=('on off break last permanent redirect reuseport ssl default_server deferred '
    +'spdy fastopen rcvbuf sndbuf').split(' ');
  function nginxRules(){
    var kw='\\b(?:'+NGINX_KW.join('|')+')\\b';
    var cn='\\b(?:'+NGINX_CONST.join('|')+')\\b';
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, cls:'s'},
      {re:/\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/g, cls:'ph'},
      {re:new RegExp(kw,'g'), cls:'k'},
      {re:new RegExp(cn,'g'), cls:'b'},
      {re:/~\*?|\^~|=(?=\s)/g, cls:'m'},
      {re:/\b\d+(?:\.\d+)*(?:ms|[smhdMG]|k|m|g)?\b/g, cls:'n'},
      {re:/[{};]/g, cls:'p'}
    ];
  }
  function yamlRules(){
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, cls:'s'},
      {re:/^[ \t-]*[A-Za-z0-9_.\-]+(?=\s*:)/gm, cls:'a'},
      {re:/\b(true|false|null|yes|no)\b/g, cls:'b'},
      {re:/\b\d+(?:\.\d+)?\b/g, cls:'n'}
    ];
  }
  function iniRules(){
    return [
      {re:/[#;][^\n]*/g, cls:'c'},
      {re:/^\[[^\]\n]+\]/gm, cls:'k'},
      {re:/^[A-Za-z0-9_.\-]+(?=\s*=)/gm, cls:'a'},
      {re:/"(?:[^"\\]|\\.)*"/g, cls:'s'}
    ];
  }
  function dockerRules(){
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/^\s*(FROM|RUN|COPY|CMD|ENV|EXPOSE|WORKDIR|ENTRYPOINT|ARG|LABEL|VOLUME|USER|AS)\b/gmi, cls:'k'},
      {re:/"(?:[^"\\]|\\.)*"/g, cls:'s'},
      {re:/\s-{1,2}[A-Za-z][\w-]*/g, cls:'n'}
    ];
  }
  function defaultRules(){
    return [
      {re:/#[^\n]*/g, cls:'c'},
      {re:/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, cls:'s'}
    ];
  }
  function rulesFor(lang){
    switch(lang){
      case 'caddyfile': case 'caddy': return caddyRules();
      case 'bash': case 'sh': case 'shell': case 'console': case 'powershell': return bashRules();
      case 'json': return jsonRules();
      case 'nginx': return nginxRules();
      case 'yaml': case 'yml': return yamlRules();
      case 'ini': case 'toml': case 'systemd': return iniRules();
      case 'dockerfile': case 'docker': return dockerRules();
      case 'html': case 'xml': return defaultRules();
      default: return null;
    }
  }
  var LANGLABEL={caddyfile:'Caddyfile',caddy:'Caddyfile',bash:'bash',sh:'bash',shell:'bash',
    console:'bash',powershell:'PowerShell',json:'JSON',nginx:'nginx',yaml:'YAML',yml:'YAML',
    ini:'ini',toml:'TOML',systemd:'systemd',dockerfile:'Dockerfile',docker:'Dockerfile',
    html:'HTML',text:'text'};

  function enhanceCode(){
    document.querySelectorAll('main pre > code').forEach(function(code){
      var pre=code.parentNode;
      if(pre.parentNode.classList && pre.parentNode.classList.contains('codewrap')) return;
      var cls=code.className||'';
      var lm=cls.match(/language-([\w-]+)/);
      var lang=lm?lm[1].toLowerCase():'text';
      var raw=code.textContent;
      // highlight
      var rules=rulesFor(lang);
      if(rules){ try{ code.innerHTML=tokenize(raw,rules);}catch(e){ code.textContent=raw; } }
      // wrap
      var wrap=document.createElement('div'); wrap.className='codewrap';
      var bar=document.createElement('div'); bar.className='codebar';
      var label=document.createElement('span'); label.className='lang';
      label.textContent=LANGLABEL[lang]||lang;
      var btn=document.createElement('button'); btn.className='copybtn'; btn.type='button';
      btn.innerHTML='<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><span>Copy</span>';
      btn.addEventListener('click',function(){
        navigator.clipboard.writeText(raw).then(function(){
          btn.classList.add('ok'); btn.querySelector('span').textContent='Copied';
          setTimeout(function(){btn.classList.remove('ok');btn.querySelector('span').textContent='Copy';},1400);
        });
      });
      bar.appendChild(label); bar.appendChild(btn);
      pre.parentNode.insertBefore(wrap,pre);
      wrap.appendChild(bar); wrap.appendChild(pre);
    });
  }

  /* ---------- wrap tables for horizontal scroll ---------- */
  function wrapTables(){
    document.querySelectorAll('main table').forEach(function(t){
      if(t.parentNode.classList.contains('tablewrap'))return;
      var w=document.createElement('div'); w.className='tablewrap';
      t.parentNode.insertBefore(w,t); w.appendChild(t);
    });
  }

  /* ---------- scroll-spy + progress ---------- */
  function setupSpy(){
    var links=[].slice.call(document.querySelectorAll('.toc a'));
    var map={}; links.forEach(function(a){map[a.dataset.target]=a;});
    var heads=[].slice.call(document.querySelectorAll('main h2[id], main h3[id]'));
    var prog=document.getElementById('progress');
    function onScroll(){
      var y=window.scrollY, h=document.documentElement;
      var max=h.scrollHeight-h.clientHeight;
      prog.style.width=(max>0?(y/max*100):0)+'%';
      var cur=null;
      for(var i=0;i<heads.length;i++){
        if(heads[i].getBoundingClientRect().top<=90) cur=heads[i]; else break;
      }
      links.forEach(function(a){a.classList.remove('active');});
      if(cur && map[cur.id]){
        map[cur.id].classList.add('active');
        var act=map[cur.id];
        var sb=document.querySelector('.sidebar');
        if(sb && act.offsetTop<sb.scrollTop || act.offsetTop>sb.scrollTop+sb.clientHeight-40){
          // keep active link in view
          sb.scrollTop=act.offsetTop-sb.clientHeight/2;
        }
      }
      document.getElementById('toTop').classList.toggle('show',y>600);
    }
    window.addEventListener('scroll',onScroll,{passive:true});
    onScroll();
  }

  /* ---------- collapsible parts (h2) ---------- */
  function setupCollapse(){
    document.querySelectorAll('main h2[id]').forEach(function(h){
      h.addEventListener('click',function(e){
        // ignore clicks on links inside heading
        if(e.target.tagName==='A')return;
        var collapsed=h.classList.toggle('collapsed');
        var el=h.nextElementSibling;
        while(el && el.tagName!=='H2'){
          if(el.tagName==='HR'){el=el.nextElementSibling;continue;}
          el.classList.toggle('collapsed-body',collapsed);
          el=el.nextElementSibling;
        }
      });
    });
  }

  /* ---------- quizzes ---------- */
  function setupQuiz(){
    document.querySelectorAll('.quiz-item').forEach(function(item){
      var opts=[].slice.call(item.querySelectorAll('.quiz-opt'));
      var explain=item.querySelector('.quiz-explain');
      opts.forEach(function(opt){
        opt.addEventListener('click',function(){
          if(item.dataset.done)return;
          item.dataset.done='1';
          opts.forEach(function(o){
            o.classList.add('locked');
            if(o.dataset.correct==='true')o.classList.add('correct');
          });
          if(opt.dataset.correct!=='true')opt.classList.add('wrong');
          if(explain)explain.hidden=false;
        });
      });
    });
  }

  /* ---------- decision helper ---------- */
  function setupDecision(){
    var box=document.getElementById('decision-helper'); if(!box)return;
    var out=document.getElementById('decision-out');
    function compute(){
      var w={caddy:0,against:0,traefik:0};
      box.querySelectorAll('input:checked').forEach(function(c){
        w[c.dataset.w]+=parseInt(c.value,10);
      });
      var verdict,cls,reasons;
      if(w.caddy===0 && w.against===0 && w.traefik===0){
        out.innerHTML='<span class="decision-verdict">Select options above for a recommendation.</span>';
        return;
      }
      if(w.traefik>=2 && w.traefik>=w.caddy){
        verdict='Consider Traefik'; cls='alt';
        reasons='Docker-label auto-discovery is Traefik’s native strength. Caddy can do it with plugins, but if that’s a core requirement, Traefik is the cleaner fit.';
      } else if(w.against>w.caddy){
        verdict='Caddy is probably not the best fit'; cls='alt';
        reasons='Your needs lean toward a specialist: HAProxy/Envoy for L4 or extreme scale, Nginx+ModSecurity or a cloud WAF for filtering, or sticking with a working Nginx setup. See Part 12.6.';
      } else if(w.against>0 && w.caddy-w.against<=1){
        verdict='Caddy works — with caveats'; cls='maybe';
        reasons='Caddy fits most of your needs, but weigh the constraints you checked. For those specific concerns, a specialist tool may still be worth pairing in.';
      } else {
        verdict='Caddy is a strong fit'; cls='caddy';
        reasons='Automatic HTTPS, a simple config, and a single dependency-free binary line up well with what you need. Start with the Caddyfile and reach for the JSON API only if you outgrow it.';
      }
      out.innerHTML='<span class="decision-verdict '+cls+'">'+verdict+'</span>'
        +'<p class="decision-reasons">'+reasons+'</p>';
    }
    box.addEventListener('change',compute);
  }

  /* ---------- search ---------- */
  function setupSearch(){
    var input=document.getElementById('search');
    var tocItems=[].slice.call(document.querySelectorAll('.toc li'));
    function clearMarks(){
      document.querySelectorAll('main mark.hit').forEach(function(m){
        var t=document.createTextNode(m.textContent); m.parentNode.replaceChild(t,m);
      });
    }
    var t;
    input.addEventListener('input',function(){
      clearTimeout(t); t=setTimeout(run,150);
    });
    function run(){
      var q=input.value.trim().toLowerCase();
      // filter TOC
      tocItems.forEach(function(li){
        var a=li.querySelector('a'); if(!a)return;
        li.classList.toggle('hide', q!=='' && a.textContent.toLowerCase().indexOf(q)===-1);
      });
      clearMarks();
      if(q.length<2)return;
      // highlight in body (text nodes only, skip code/script)
      var rx=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');
      var walker=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT,{
        acceptNode:function(node){
          if(!node.nodeValue.trim())return NodeFilter.FILTER_REJECT;
          var p=node.parentNode;
          while(p && p!==document.body){
            var tn=p.tagName;
            if(tn==='CODE'||tn==='PRE'||tn==='SCRIPT'||tn==='STYLE'||tn==='MARK')return NodeFilter.FILTER_REJECT;
            p=p.parentNode;
          }
          return rx.test(node.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;
        }
      });
      var nodes=[],nd; while(nd=walker.nextNode())nodes.push(nd);
      var count=0;
      nodes.forEach(function(node){
        if(count>400)return;
        var frag=document.createDocumentFragment(); var last=0,s=node.nodeValue; rx.lastIndex=0; var m;
        while((m=rx.exec(s))){
          frag.appendChild(document.createTextNode(s.slice(last,m.index)));
          var mk=document.createElement('mark'); mk.className='hit'; mk.textContent=m[0];
          frag.appendChild(mk); last=m.index+m[0].length; count++;
          if(m.index===rx.lastIndex)rx.lastIndex++;
        }
        frag.appendChild(document.createTextNode(s.slice(last)));
        node.parentNode.replaceChild(frag,node);
      });
    }
  }

  /* ---------- theme + mobile nav + shortcuts ---------- */
  function setupChrome(){
    var root=document.documentElement;
    var saved=localStorage.getItem('caddy-theme');
    if(saved)root.setAttribute('data-theme',saved);
    document.getElementById('themeBtn').addEventListener('click',function(){
      var cur=root.getAttribute('data-theme')==='light'?'dark':'light';
      root.setAttribute('data-theme',cur); localStorage.setItem('caddy-theme',cur);
    });
    var sb=document.querySelector('.sidebar'), scrim=document.querySelector('.scrim');
    function close(){sb.classList.remove('open');scrim.classList.remove('show');}
    document.getElementById('menuBtn').addEventListener('click',function(){
      sb.classList.toggle('open');scrim.classList.toggle('show');
    });
    scrim.addEventListener('click',close);
    sb.addEventListener('click',function(e){if(e.target.tagName==='A')close();});
    document.getElementById('toTop').addEventListener('click',function(){
      window.scrollTo({top:0,behavior:'smooth'});
    });
    document.addEventListener('keydown',function(e){
      if(e.key==='/'&&document.activeElement.id!=='search'){e.preventDefault();document.getElementById('search').focus();}
      else if(e.key==='Escape'){close();document.getElementById('search').blur();}
      else if(e.key==='t'&&document.activeElement.tagName!=='INPUT'){document.getElementById('themeBtn').click();}
    });
  }

  document.addEventListener('DOMContentLoaded',function(){
    enhanceCode(); wrapTables(); setupSpy(); setupCollapse();
    setupQuiz(); setupDecision(); setupSearch(); setupChrome();
  });
})();
"""

PAGE = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="description" content="An interactive, depth-first study guide to Caddy: automatic HTTPS, the Caddyfile, reverse proxy, the JSON admin API, production operations, and how it compares to Nginx, Traefik, HAProxy, and Envoy.">
<title>Caddy Study Guide — Interactive</title>
<style>__CSS__</style>
</head>
<body>
<div id="progress"></div>
<header class="topbar">
  <button id="menuBtn" class="iconbtn" aria-label="Toggle menu">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
  <div class="brand"><span class="logo">C</span><span>Caddy Study Guide</span><span class="sub">interactive</span></div>
  <div class="spacer"></div>
  <div class="search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="search" type="search" placeholder="Search the guide…" aria-label="Search" autocomplete="off">
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


def main():
    toc_html, body = build()
    page = (PAGE
            .replace("__CSS__", CSS)
            .replace("__TOC__", toc_html)
            .replace("__BODY__", body)
            .replace("__JS__", JS))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote", OUT, "(", len(page), "bytes )")


if __name__ == "__main__":
    main()

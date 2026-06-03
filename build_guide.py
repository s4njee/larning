#!/usr/bin/env python3
"""
Generic study-guide -> interactive HTML converter.

Turns any study-guide Markdown file into a single self-contained, responsive,
black-themed interactive HTML page in the same style as caddy-study-guide.html
and nginx-study-guide.html. Reuses the shared CSS + JS (syntax highlighting,
scroll-spy TOC, search, copy buttons, collapsible parts, theme toggle, progress
bar) from build_caddy_html.py.

Usage:
    python3 build_guide.py INPUT.md [options]

Options:
    --title  "Text"   Page title + header brand name. Default: the Markdown H1.
    --brand  X        Short brand letter shown in the header logo. Default: first
                      alphanumeric char of the title, uppercased.
    --accent "#hex"   Primary accent color (tints links, active TOC, highlights).
                      Default: the shared teal.
    --accent2 "#hex"  Secondary accent (gradients). Default: same as --accent.
    --auto-accent     Derive a stable accent from the title (same guide always gets
                      the same color; never random). --accent overrides it.
    --out    PATH     Output file. Default: <dir>/<lowercased-hyphenated>.html
                      next to the source (e.g. k8s/FOO_BAR.md -> k8s/foo-bar.html).

Examples:
    python3 build_guide.py RUST_FOR_PYTHON_DEVS.md --accent "#f74c00"
    python3 build_guide.py TYPESCRIPT_STUDY_GUIDE.md --accent "#3178c6" --brand TS
    python3 build_guide.py k8s/KUBERNETES_STUDY_GUIDE.md --accent "#326ce5"
"""

import argparse
import colorsys
import hashlib
import os
import re
import sys

import markdown

from build_caddy_html import CSS, JS  # shared styling + behavior


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def derive_title(md_text, fallback):
    m = re.search(r'^\#\s+(.+?)\s*$', md_text, re.M)
    return m.group(1).strip() if m else fallback


def derive_brand(title):
    for ch in title:
        if ch.isalnum():
            return ch.upper()
    return "?"


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"bad hex color: {h!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hls_to_hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def auto_accent(name):
    """Derive a stable (deterministic) accent + secondary accent from a name.

    Same name always yields the same hue. Uses a salted-free SHA-256 hash (Python's
    built-in hash() is process-salted, so it is NOT used). Saturation/lightness are
    tuned to read well on the black theme.
    """
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    hue = (int(digest[0:8], 16) % 360) / 360.0
    # Deterministic lightness/saturation jitter from other hash bytes, so two guides
    # that happen to hash to the same hue still render as visibly distinct colors.
    light = 0.56 + (int(digest[8:10], 16) / 255) * 0.10   # 0.56 .. 0.66
    sat = 0.62 + (int(digest[10:12], 16) / 255) * 0.16    # 0.62 .. 0.78
    accent = _hls_to_hex(hue, light, sat)                 # primary
    accent2 = _hls_to_hex((hue + 26 / 360.0) % 1.0, max(0.50, light - 0.02), sat - 0.04)
    return accent, accent2


def apply_accent(css, accent, accent2):
    """Replace the shared accent CSS variables (dark + light themes)."""
    r, g, b = hex_to_rgb(accent)
    weak = f"rgba({r},{g},{b},.13)"
    replacements = {
        # dark theme (:root)
        "--accent:#2dd4bf;": f"--accent:{accent};",
        "--accent2:#38bdf8;": f"--accent2:{accent2};",
        "--accent-weak:rgba(45,212,191,.12);": f"--accent-weak:{weak};",
        # light theme
        "--accent:#0d9488;": f"--accent:{accent};",
        "--accent2:#0284c7;": f"--accent2:{accent2};",
        "--accent-weak:rgba(13,148,136,.10);": f"--accent-weak:{weak};",
    }
    for old, new in replacements.items():
        css = css.replace(old, new)
    return css


def default_out_path(src):
    d = os.path.dirname(src)
    base = os.path.basename(src)
    if base.lower().endswith(".md"):
        base = base[:-3]
    name = base.lower().replace("_", "-") + ".html"
    return os.path.join(d, name) if d else name


def escape_raw_html_tags(md_text):
    """Render tag-looking prose as text instead of live raw HTML.

    Python-Markdown passes raw HTML through by default. That is nice for trusted
    authored HTML, but bad for study-guide prose like `<script setup>` or
    `<button>`: one unclosed raw tag can consume the rest of the generated page.
    Fenced code blocks are left untouched because Markdown already escapes them.
    """
    tag_re = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?>")
    fence_re = re.compile(r"^\s*(```|~~~)")
    in_fence = False
    out = []

    def esc_tag(m):
        return m.group(0).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    for line in md_text.splitlines(keepends=True):
        if fence_re.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else tag_re.sub(esc_tag, line))
    return "".join(out)


# --------------------------------------------------------------------------- #
# Markdown -> HTML transform (shared with the bespoke builders)
# --------------------------------------------------------------------------- #

def transform(md_text):
    md_text = escape_raw_html_tags(md_text)
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "attr_list", "sane_lists"],
        output_format="html5",
    )
    body = md.convert(md_text)

    # Normalize code language classes to `language-xxx` (drives client highlighter).
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

    # Build sidebar TOC from h2/h3 headings.
    toc = ['<nav class="toc" aria-label="Table of contents"><ul>']
    for m in re.finditer(r'<h([23])\s+id="([^"]+)">(.*?)</h\1>', body, re.S):
        level, hid, inner = m.group(1), m.group(2), m.group(3)
        label = re.sub(r"<[^>]+>", "", inner).strip()
        if label.lower() == "table of contents":
            continue
        cls = "toc-l2" if level == "2" else "toc-l3"
        toc.append(f'<li class="{cls}"><a href="#{hid}" data-target="{hid}">{label}</a></li>')
    toc.append("</ul></nav>")
    return "".join(toc), body


PAGE = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<meta name="description" content="__DESC__">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div id="progress"></div>
<header class="topbar">
  <button id="menuBtn" class="iconbtn" aria-label="Toggle menu">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
  <div class="brand"><span class="logo">__BRAND__</span><span>__NAME__</span><span class="sub">interactive</span></div>
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


def esc_attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def build(src, title=None, brand=None, accent=None, accent2=None, out=None, auto=False):
    with open(src, encoding="utf-8") as f:
        md_text = f.read()

    fallback_title = os.path.basename(src)[:-3].replace("_", " ").title()
    title = title or derive_title(md_text, fallback_title)
    brand = (brand or derive_brand(title))[:3]
    out = out or default_out_path(src)

    # Explicit --accent always wins; otherwise --auto-accent derives one from the title.
    if not accent and auto:
        accent, accent2 = auto_accent(title)

    css = CSS
    if accent:
        css = apply_accent(css, accent, accent2 or accent)

    toc_html, body = transform(md_text)
    desc = f"An interactive study guide: {title}."

    page = (PAGE
            .replace("__CSS__", css)
            .replace("__JS__", JS)
            .replace("__TOC__", toc_html)
            .replace("__BODY__", body)
            .replace("__TITLE__", esc_attr(title) + " - Interactive")
            .replace("__DESC__", esc_attr(desc))
            .replace("__BRAND__", esc_attr(brand))
            .replace("__NAME__", esc_attr(title)))

    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out, len(page)


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert a study-guide .md into an interactive .html page.")
    p.add_argument("input", help="Path to the source Markdown file")
    p.add_argument("--title", help="Page title / header name (default: the Markdown H1)")
    p.add_argument("--brand", help="Short brand letter for the header logo (default: first char of title)")
    p.add_argument("--accent", help='Primary accent color, e.g. "#f74c00" (default: shared teal)')
    p.add_argument("--accent2", help="Secondary accent color (default: same as --accent)")
    p.add_argument("--auto-accent", action="store_true",
                   help="Derive a stable accent from the title (deterministic; --accent overrides it)")
    p.add_argument("--out", help="Output path (default: <name>.html next to the source)")
    args = p.parse_args(argv)

    if not os.path.isfile(args.input):
        p.error(f"input not found: {args.input}")

    out, size = build(args.input, title=args.title, brand=args.brand,
                      accent=args.accent, accent2=args.accent2, out=args.out,
                      auto=args.auto_accent)
    print(f"wrote {out} ({size} bytes)")


if __name__ == "__main__":
    main()

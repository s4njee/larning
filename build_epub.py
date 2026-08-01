#!/usr/bin/env python3
"""Package the generated html/ study guides into a single EPUB 3 book.

Reads the pages `build_all_guides.py` already produced (so the book always
matches the site), lifts each page's <main> content, converts it to valid
XHTML, and zips it up with a nested navigation document: category -> guide ->
the guide's own top-level sections.

Two content transforms happen on the way in, because an EPUB has no JavaScript:

  * quiz widgets become plain option lists with the answer and explanation in a
    <details> block, so the self-check still works on paper-like readers;
  * cross-guide links (`redis-study-guide.html`) are rewritten to the book's
    own `.xhtml` documents, so the guides stay hyperlinked offline.

Usage:  python3 build_epub.py [-o study-guides.epub]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html.entities
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from build_all_guides import CATEGORIES, GUIDES

REPO_BLOB = "https://github.com/s4njee/larning/blob/main/"

HTML_DIR = Path("html")
DEFAULT_OUT = Path("study-guides.epub")

BOOK_TITLE = "Study Guides"
BOOK_AUTHOR = "s4njee"
BOOK_DESC = (
    "A collected edition of the long-form technical study guides at "
    "github.com/s4njee/larning."
)
# Stable across rebuilds so readers treat a new build as the same book.
BOOK_UUID = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/s4njee/larning")

# Repo meta pages that live on the site index but aren't study guides.
SKIP_PAGES = {"readme.html", "topics.html", "todo.html", "remaining.html", "index.html"}
# After that filter this category holds only Caddy and Nginx.
CATEGORY_RENAMES = {"Bespoke and repo pages": "Web servers"}

VOID_TAGS = "area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr"
ATTR_RE = re.compile(
    r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)          # name
        (?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))? # optional value""",
    re.X,
)
TAG_RE = re.compile(r"""<([a-zA-Z][^\s/>]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(/?)>""")


# --------------------------------------------------------------------------- #
# Reading the built site
# --------------------------------------------------------------------------- #

def page_order():
    """[(category, [page filename, ...]), ...] in site-index order, filtered."""
    out = []
    for name, pages in CATEGORIES:
        kept = [p for p in pages if p not in SKIP_PAGES and (HTML_DIR / p).exists()]
        if kept:
            out.append((CATEGORY_RENAMES.get(name, name), kept))
    return out


def read_page(path: Path):
    """Return (title, main-content HTML) for one generated guide page."""
    text = path.read_text(encoding="utf-8")

    m = re.search(r"<title>(.*?)</title>", text, re.S)
    # Unescape: the page title is already HTML-escaped, and callers re-escape it.
    title = html.unescape(re.sub(r"\s*-\s*Interactive\s*$", "", m.group(1).strip())) if m else path.stem

    m = re.search(r"<main>(.*)</main>", text, re.S)
    if not m:
        raise SystemExit(f"{path}: no <main> element — was it built by build_all_guides.py?")
    return title, m.group(1)


# --------------------------------------------------------------------------- #
# Content transforms
# --------------------------------------------------------------------------- #

def quizzes_to_book(body: str) -> str:
    """Turn the JS click-to-reveal quiz markup into a static <details> form.

    Splitting on the quiz-item opener keeps each question's options and its
    explanation in one chunk without having to match nested <div> boundaries.
    """
    body = body.replace(
        "Pick an answer to reveal the explanation.",
        "Answers and explanations are collapsed under each question.",
    )

    chunks = body.split('<div class="quiz-item">')
    rebuilt = [chunks[0]]
    for chunk in chunks[1:]:
        correct = re.search(
            r'data-correct="true">.*?<span class="quiz-opt-text">(.*?)</span>', chunk, re.S
        )
        answer = correct.group(1) if correct else ""

        chunk = re.sub(
            r'<li><button class="quiz-opt" data-correct="(?:true|false)">'
            r'<span class="quiz-mark"[^>]*></span>'
            r'<span class="quiz-opt-text">(.*?)</span></button></li>',
            lambda m: f"<li>{m.group(1)}</li>",
            chunk,
            flags=re.S,
        )
        chunk = re.sub(
            r'<div class="quiz-explain" hidden>(.*?)</div>',
            lambda m: (
                '<details class="quiz-explain"><summary>Show answer</summary>'
                f'<p class="quiz-answer"><strong>Answer:</strong> {answer}</p>'
                f"<p>{m.group(1)}</p></details>"
            ),
            chunk,
            flags=re.S,
        )
        rebuilt.append(chunk)
    return '<div class="quiz-item">'.join(rebuilt)


def excluded_page_urls():
    """Skipped site pages (README, TOPICS, ...) -> their source on GitHub."""
    urls = {}
    for src, out, _ in GUIDES:
        name = Path(out).name
        if name in SKIP_PAGES:
            urls[name] = REPO_BLOB + Path(src).as_posix()
    return urls


def rewrite_links(body: str, page_to_doc: dict, external: dict) -> str:
    """Point cross-guide links at the book's own XHTML documents.

    Links to pages the book excludes go to their source on GitHub instead, so
    they still lead somewhere rather than dangling.
    """

    def repl(match):
        quote, href = match.group(1), match.group(2)
        path, _, anchor = href.partition("#")
        target = page_to_doc.get(path) or external.get(path)
        if not target:
            return match.group(0)
        suffix = f"#{anchor}" if anchor and target.endswith(".xhtml") else ""
        return f"href={quote}{target}{suffix}{quote}"

    return re.sub(r"href=(['\"])([^'\"]+)\1", repl, body)


def drop_dead_links(body: str, docs: set) -> str:
    """Unwrap relative links that can't resolve inside the book.

    A handful of guides use URL-shaped examples (`/reports/export?month=...`)
    as link targets. They lead nowhere on the site and would be a dangling
    resource reference in an EPUB, so keep the text and drop the anchor.
    """

    def repl(match):
        href, inner = match.group(1), match.group(2)
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", href, re.I):
            return match.group(0)
        if href.split("#")[0] in docs or not href.split("#")[0]:
            return match.group(0)
        return f'<span class="dead-link">{inner}</span>'

    return re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', repl, body, flags=re.S)


def fix_entities(text: str) -> str:
    """XML knows five named entities; map everything else to numeric refs."""

    def repl(match):
        whole, name = match.group(0), match.group(1)
        if name in ("amp", "lt", "gt", "quot", "apos"):
            return whole
        chars = html.entities.html5.get(name + ";")
        if chars:
            return "".join(f"&#{ord(c)};" for c in chars)
        return "&amp;" + name

    text = re.sub(r"&([a-zA-Z][a-zA-Z0-9]*);", repl, text)
    # Bare ampersands that aren't part of a character reference.
    return re.sub(r"&(?!#\d+;|#x[0-9a-fA-F]+;|amp;|lt;|gt;|quot;|apos;)", "&amp;", text)


def to_xhtml(body: str) -> str:
    """Make HTML5 fragment output well-formed XML.

    Attribute case is preserved deliberately: the inline mermaid SVGs carry
    camelCase attributes (viewBox, patternUnits) that XML treats as distinct.
    """

    def fix_tag(match):
        name, attrs, closing = match.group(1), match.group(2), match.group(3)
        parts = []
        for attr in ATTR_RE.finditer(attrs):
            key, value = attr.group(1), attr.group(2)
            if value is None:
                value = f'"{key}"'          # bare boolean attribute
            elif not value.startswith(('"', "'")):
                value = f'"{value}"'
            elif value.startswith("'"):
                value = '"' + value[1:-1].replace('"', "&quot;") + '"'
            parts.append(f"{key}={value}")
        rendered = (" " + " ".join(parts)) if parts else ""
        void = re.fullmatch(VOID_TAGS, name, re.I)
        slash = "/" if (closing or void) else ""
        return f"<{name}{rendered}{slash}>"

    return fix_tag_outside_text(body, fix_tag)


def fix_tag_outside_text(body: str, fix_tag) -> str:
    """Apply `fix_tag` to every tag, escaping entities in the text between."""
    out, pos = [], 0
    for match in TAG_RE.finditer(body):
        out.append(fix_entities(body[pos:match.start()]))
        out.append(fix_tag(match))
        pos = match.end()
    out.append(fix_entities(body[pos:]))
    return "".join(out)


def fix_anchors(body: str, self_doc: str, ids_by_doc: dict) -> str:
    """Resolve anchors whose slug doesn't match the generated heading id.

    The guides write GitHub-style anchors (`#part-1--the-model`, where the em
    dash leaves a doubled hyphen) while the HTML build's slugger collapses
    repeated hyphens. Reconcile them here so the in-guide tables of contents
    actually navigate inside the book.
    """

    def repl(match):
        quote, href = match.group(1), match.group(2)
        doc, _, anchor = href.rpartition("#")
        if not anchor or href.startswith(("http", "mailto:")):
            return match.group(0)
        ids = ids_by_doc.get(doc or self_doc)
        if ids is None or anchor in ids:
            return match.group(0)
        collapsed = re.sub(r"-{2,}", "-", anchor)
        if collapsed in ids:
            return f"href={quote}{doc}#{collapsed}{quote}"
        return match.group(0)

    return re.sub(r"href=(['\"])([^'\"]*#[^'\"]+)\1", repl, body)


def sections_of(body: str):
    """[(anchor id, label), ...] for the guide's top-level (h2) sections."""
    found = []
    for match in re.finditer(r'<h2\s+id="([^"]+)"[^>]*>(.*?)</h2>', body, re.S):
        label = html.unescape(re.sub(r"<[^>]+>", "", match.group(2)).strip())
        if label.lower() == "table of contents":
            continue
        found.append((match.group(1), esc(label)))
    return found


# --------------------------------------------------------------------------- #
# EPUB assembly
# --------------------------------------------------------------------------- #

def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


XHTML_DOC = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" \
lang="en" xml:lang="en">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
{body}
</body>
</html>
"""

STYLE = """\
html { font-size: 100%; }
body {
  font-family: Georgia, "Iowan Old Style", serif;
  line-height: 1.55; margin: 0 1em; hyphens: auto;
}
h1, h2, h3, h4 { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; line-height: 1.25; }
h1 { font-size: 1.7em; margin: 1em 0 0.6em; }
h2 { font-size: 1.32em; margin: 1.6em 0 0.5em; border-bottom: 1px solid #bbb; padding-bottom: 0.2em; }
h3 { font-size: 1.12em; margin: 1.3em 0 0.4em; }
h4 { font-size: 1em; margin: 1.1em 0 0.3em; }
p, li { orphans: 2; widows: 2; }
a { color: #1a4f8a; text-decoration: none; }
code, pre, kbd { font-family: "SFMono-Regular", Menlo, Consolas, monospace; }
code { font-size: 0.86em; background: #f0f0f2; padding: 0.1em 0.28em; border-radius: 3px; }
pre {
  font-size: 0.78em; line-height: 1.42; background: #f5f5f7; color: #16181d;
  border: 1px solid #dcdce2; border-radius: 4px; padding: 0.7em 0.8em;
  overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;
}
pre code { background: none; padding: 0; font-size: 1em; }
blockquote {
  margin: 1em 0; padding: 0.1em 1em; border-left: 3px solid #b9bcc4;
  color: #3c4048; font-style: italic;
}
table { border-collapse: collapse; width: 100%; font-size: 0.84em; margin: 1em 0; }
th, td { border: 1px solid #c9ccd3; padding: 0.4em 0.55em; text-align: left; vertical-align: top; }
th { background: #eef0f3; }
hr { border: none; border-top: 1px solid #c9ccd3; margin: 2em 0; }
figure { margin: 1.2em 0; text-align: center; page-break-inside: avoid; }
svg { max-width: 100%; height: auto; }
.addon, .quiz {
  border: 1px solid #c9ccd3; border-radius: 6px; padding: 0.8em 1em;
  margin: 1.4em 0; background: #fafafc; page-break-inside: avoid;
}
.addon-kicker { font-size: 0.72em; letter-spacing: 0.08em; text-transform: uppercase; color: #5b6068; }
.addon-head h3 { margin: 0.2em 0 0.1em; }
.addon-sub { font-size: 0.85em; color: #5b6068; margin: 0 0 0.6em; }
.quiz-item { margin: 1em 0 0; page-break-inside: avoid; }
.quiz-q { font-weight: bold; margin-bottom: 0.35em; }
.quiz-n { display: inline-block; margin-right: 0.5em; color: #5b6068; font-size: 0.85em; }
.quiz-opts { margin: 0.2em 0 0.5em 1.2em; padding: 0; }
.quiz-opts li { margin: 0.18em 0; }
.quiz-explain { font-size: 0.92em; }
.quiz-explain summary { cursor: pointer; color: #1a4f8a; font-size: 0.85em; }
.quiz-answer { margin: 0.4em 0 0.2em; }
.cover { text-align: center; margin-top: 22%; }
.cover h1 { font-size: 2.4em; border: none; }
.cover p { color: #5b6068; }
.toc-cat { margin-top: 1.2em; font-weight: bold; }
nav ol { list-style: none; padding-left: 1em; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e6e7ea; }
  a { color: #7ab7ff; }
  code { background: #23262c; }
  pre { background: #1b1e23; color: #e6e7ea; border-color: #2c3037; }
  th { background: #22252b; }
  th, td, hr, .addon, .quiz { border-color: #343841; }
  .addon, .quiz { background: #191c21; }
  blockquote { color: #b6bac2; border-left-color: #343841; }
}
"""

CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def build_nav(docs, categories) -> str:
    """EPUB 3 navigation document: category -> guide -> the guide's sections."""
    lines = ['<nav epub:type="toc" id="toc"><h1>Contents</h1>', "<ol>"]
    for category, pages in categories:
        lines.append(f"<li><span>{esc(category)}</span><ol>")
        for page in pages:
            doc = docs[page]
            lines.append(f'<li><a href="{doc["file"]}">{esc(doc["title"])}</a>')
            if doc["sections"]:
                lines.append("<ol>")
                for anchor, label in doc["sections"]:
                    lines.append(f'<li><a href="{doc["file"]}#{anchor}">{label}</a></li>')
                lines.append("</ol>")
            lines.append("</li>")
        lines.append("</ol></li>")
    lines.append("</ol></nav>")
    lines.append(
        '<nav epub:type="landmarks" hidden="hidden"><ol>'
        '<li><a epub:type="toc" href="nav.xhtml">Contents</a></li>'
        '<li><a epub:type="bodymatter" href="title.xhtml">Start</a></li>'
        "</ol></nav>"
    )
    return XHTML_DOC.format(title="Contents", body="\n".join(lines))


def build_ncx(docs, categories) -> str:
    """EPUB 2 fallback TOC, for readers that ignore nav.xhtml."""
    points, order = [], 1
    points.append(
        f'<navPoint id="np-title" playOrder="{order}">'
        f"<navLabel><text>{esc(BOOK_TITLE)}</text></navLabel>"
        '<content src="title.xhtml"/></navPoint>'
    )
    for category, pages in categories:
        for page in pages:
            order += 1
            doc = docs[page]
            points.append(
                f'<navPoint id="np-{order}" playOrder="{order}">'
                f'<navLabel><text>{esc(category)}: {esc(doc["title"])}</text></navLabel>'
                f'<content src="{doc["file"]}"/></navPoint>'
            )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        f'<head><meta name="dtb:uid" content="urn:uuid:{BOOK_UUID}"/>'
        '<meta name="dtb:depth" content="1"/>'
        '<meta name="dtb:totalPageCount" content="0"/>'
        '<meta name="dtb:maxPageNumber" content="0"/></head>\n'
        f"<docTitle><text>{esc(BOOK_TITLE)}</text></docTitle>\n"
        f'<navMap>{"".join(points)}</navMap>\n</ncx>\n'
    )


def build_opf(docs, categories, modified) -> str:
    items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="style" href="style.css" media-type="text/css"/>',
        '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="title"/>', '<itemref idref="nav"/>']
    for index, (_, pages) in enumerate(categories):
        for page in pages:
            doc = docs[page]
            props = ' properties="svg"' if doc["has_svg"] else ""
            items.append(
                f'<item id="{doc["id"]}" href="{doc["file"]}" '
                f'media-type="application/xhtml+xml"{props}/>'
            )
            spine.append(f'<itemref idref="{doc["id"]}"/>')
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="bookid" xml:lang="en">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">urn:uuid:{BOOK_UUID}</dc:identifier>\n'
        f"<dc:title>{esc(BOOK_TITLE)}</dc:title>\n"
        "<dc:language>en</dc:language>\n"
        f"<dc:creator>{esc(BOOK_AUTHOR)}</dc:creator>\n"
        f"<dc:description>{esc(BOOK_DESC)}</dc:description>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        "</metadata>\n"
        f'<manifest>{"".join(items)}</manifest>\n'
        f'<spine toc="ncx">{"".join(spine)}</spine>\n'
        "</package>\n"
    )


def build_title_page(categories, guide_count, modified) -> str:
    rows = "".join(
        f'<li>{esc(name)} <span class="toc-count">({len(pages)})</span></li>'
        for name, pages in categories
    )
    body = (
        '<div class="cover">'
        f"<h1>{esc(BOOK_TITLE)}</h1>"
        f"<p>{guide_count} technical study guides</p>"
        f"<p>{esc(BOOK_AUTHOR)} &#183; github.com/s4njee/larning</p>"
        f"<p>Built {modified[:10]}</p>"
        f"<ul>{rows}</ul>"
        "</div>"
    )
    return XHTML_DOC.format(title=esc(BOOK_TITLE), body=body)


def validate(doc: str, label: str):
    """Fail loudly rather than shipping an EPUB a reader will reject."""
    try:
        ET.fromstring(doc.split("<!DOCTYPE html>", 1)[-1])
    except ET.ParseError as exc:
        raise SystemExit(f"{label}: generated XHTML is not well-formed XML — {exc}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="output .epub path")
    args = parser.parse_args()

    categories = page_order()
    pages = [p for _, group in categories for p in group]
    if not pages:
        raise SystemExit("no built guides found in html/ — run build_all_guides.py first")

    page_to_doc = {p: p.replace(".html", ".xhtml") for p in pages}
    external = excluded_page_urls()
    book_docs = set(page_to_doc.values())
    modified = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # First pass: content transforms, and collect every document's anchor ids.
    docs, ids_by_doc = {}, {}
    for index, page in enumerate(pages, 1):
        title, body = read_page(HTML_DIR / page)
        body = quizzes_to_book(body)
        body = rewrite_links(body, page_to_doc, external)
        body = drop_dead_links(body, book_docs)
        docs[page] = {
            "id": f"g{index}",
            "file": page_to_doc[page],
            "title": title,
            "body": body,
        }
        ids_by_doc[page_to_doc[page]] = set(re.findall(r'id="([^"]+)"', body))

    # Second pass: resolve anchors now that every document's ids are known.
    for page in pages:
        doc = docs[page]
        body = fix_anchors(doc["body"], doc["file"], ids_by_doc)
        body = to_xhtml(body)
        doc["sections"] = sections_of(body)
        doc["has_svg"] = "<svg" in body
        doc["xhtml"] = XHTML_DOC.format(title=esc(doc["title"]), body=body)
        validate(doc["xhtml"], page)

    nav = build_nav(docs, categories)
    validate(nav, "nav.xhtml")
    title_page = build_title_page(categories, len(pages), modified)
    validate(title_page, "title.xhtml")

    out = Path(args.out)
    with zipfile.ZipFile(out, "w") as z:
        # The mimetype entry must come first and be stored uncompressed.
        z.writestr(
            zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        z.writestr("META-INF/container.xml", CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", STYLE, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/title.xhtml", title_page, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(
            "OEBPS/toc.ncx", build_ncx(docs, categories), compress_type=zipfile.ZIP_DEFLATED
        )
        z.writestr(
            "OEBPS/content.opf",
            build_opf(docs, categories, modified),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for page in pages:
            z.writestr(
                f"OEBPS/{docs[page]['file']}",
                docs[page]["xhtml"],
                compress_type=zipfile.ZIP_DEFLATED,
            )

    sections = sum(len(d["sections"]) for d in docs.values())
    size_mb = out.stat().st_size / (1024 * 1024)
    print(
        f"wrote {out} — {len(pages)} guides, {len(categories)} categories, "
        f"{sections} sections in the TOC, {size_mb:.1f} MB"
    )


if __name__ == "__main__":
    main()

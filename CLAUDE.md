# CLAUDE.md

This repository is a collection of long-form technical study guides written in
Markdown and compiled into a static HTML site. There is no application code to
speak of — the guides *are* the product, so most of this file is the style
guide they must follow.

## Repository layout

- `*_STUDY_GUIDE.md`, `POSTGRES.md`, etc. — the guide sources (repo root, plus
  `k8s/` for the Kubernetes family). ~66 guides.
- `DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` — **the reference guide**. When this
  file says "match the standard," that file is the standard.
- `build_guide.py` — Markdown → single-page HTML converter (TOC sidebar,
  accent theming, raw-HTML escaping, local-link rewriting).
- `build_all_guides.py` — builds every guide. `GUIDES` registers each source
  file with its output path and accent options; `CATEGORIES` places its output
  page on the site index.
- `build_caddy_html.py` / `build_nginx_html.py` — bespoke pages; also the
  source of the shared `CSS`/`JS` used by all pages.
- `html/` — generated site, **committed to the repo**. GitHub Pages deploys
  from it via `.github/workflows/pages.yml` (the workflow rebuilds before
  publishing, but keep the committed output current anyway).
- `README.md` — site README with a summary paragraph per guide.

## Build commands

```bash
python3 build_all_guides.py        # rebuild the whole site into html/
```

There are no tests; the verification step is rebuilding and spot-checking the
generated HTML. Two known failure modes to check after a build:

- **Double-escaped entities**: grep the output for `&amp;lt;`/`&amp;gt;`.
  `escape_raw_html_tags()` in `build_guide.py` escapes things like `<T>` in
  prose but must skip fenced code blocks *and* inline backtick spans.
- **Broken sibling links**: links between guides are written as relative
  Markdown links (`REDIS_STUDY_GUIDE.md`, `k8s/KUBERNETES_STUDY_GUIDE.md`) and
  rewritten to `.html` at build time by `guide_link_rewrites()` — that only
  works for files registered in `GUIDES`.

## Adding a new guide — checklist

1. Write the guide following the style guide below.
2. Register it in `GUIDES` in `build_all_guides.py` (pick an `accent` matching
   the technology's brand color, or use `{"auto": True}`).
3. Add its output page to the right section of `CATEGORIES`.
4. Add a summary paragraph + GitHub link for it in `README.md`, matching the
   density and tone of the existing entries.
5. Run `python3 build_all_guides.py`, spot-check the HTML (TOC, links,
   entities), and commit the Markdown **and** the regenerated `html/` files
   together.
6. Where it makes sense, add a cross-link *to* the new guide from the
   "Where to Go Next" sections of its closest sibling guides.

---

# Style guide

`DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md` is the model. Every new guide must match
it on structure, linking discipline, and voice. Existing guides were brought
up to this standard in the 2026-06 pass tracked in `todo3.md`; don't regress
them.

## Required structure

Every guide has these parts, in this order:

1. **Title** — a single `#` H1.
2. **Opening thesis paragraphs** (2–3). Say who the guide is for, what it
   assumes, and what its through-line is. The Distributed Systems guide does
   this in two paragraphs: "assumes you can write and run a single-process
   service, but not that you've reasoned carefully about what changes when
   that service becomes three processes…" — a real claim about the reader,
   not marketing copy. State the guide's *organizing idea* (for that guide:
   bottom-up from the physics of failure to real OSS systems), because the
   rest of the guide has to deliver on it.
3. **A "Primary references" paragraph** in the intro: one paragraph naming
   the 3–5 canonical sources for the whole topic — the definitive book, the
   primary docs, the landmark paper(s), the best course — each as a Markdown
   link, each with a clause on *why* it earns the slot. From the model:

   > Primary references, all worth reading in full:
   > [*Designing Data-Intensive Applications*](https://dataintensive.net/)
   > (Kleppmann) — the single best book on this material; the
   > [Raft paper](https://raft.github.io/raft.pdf) and
   > [interactive visualization](https://raft.github.io/); …and
   > [MIT 6.5840](https://pdos.csail.mit.edu/6.824/), whose labs are the best
   > way to actually internalize this.

4. **A sibling-guides paragraph** in the intro, cross-linking the guides in
   this repo that go deeper on adjacent ground, with a parenthetical on what
   each covers: "the [Redis guide](REDIS_STUDY_GUIDE.md), the
   [Observability guide](OBSERVABILITY_STUDY_GUIDE.md) (tracing, SLOs)…".
   Use relative `.md` links; the build rewrites them.
5. **Table of Contents** — numbered links to the top-level parts/sections.
   Anchor slugs are GitHub-style (lowercase, hyphens, punctuation dropped).
6. **The body**, organized into Parts/sections that follow the organizing
   idea announced in the intro.
7. **A distilled-takeaways section** near the end (the model's "If You
   Remember a Handful of Things"): a short numbered list of the guide's
   through-lines, each one sentence of bolded claim plus one sentence of
   consequence. Optional but strongly encouraged for guides over ~500 lines.
8. **A closing "Where to Go Next" section** (see below). This is mandatory.
9. **A closing sentence or two** after the final list that tells the reader
   what the single highest-leverage next action is — the model ends by
   telling you to stand up a real cluster and break it on purpose.

## The "Where to Go Next" section

A short bulleted list that *sequences* the reader's next steps. Bullets are
**bold-led** and say *why*, not just *what*. The canonical shape, in order:

- **Read the definitive book** cover to cover — name it, link it, and say
  what makes it definitive.
- **Do the labs/exercises** for the best course or hands-on resource —
  building beats reading; say so concretely.
- **Read the source papers/specs while they're fresh** — link each one.
- **Run/break one real system deeply.** Every guide should send the reader to
  *operate* something: stand up a cluster and kill nodes, profile a real app,
  break a build on purpose. Concrete verbs, concrete tools.
- **Adjacent guides in this repo:** cross-link the 3–6 sibling guides that go
  deeper on a slice of the topic, with a clause on which slice.

Reference-heavy guides may title this "Recommended Reading Path" or keep an
existing "Further Reading" heading, but the content must follow the shape
above — real links (never bare titles), reasons attached, sibling cross-links
present.

## Documentation links — the linking discipline

**Every guide must have documentation links.** The rules:

- **Link the first meaningful mention** of every named tool, command, API,
  flag, RFC, or spec the guide leans on — at the point where the guide
  explains it, not in a link dump at the end. Don't re-link every repetition.
- **Official/primary sources only**: project docs, language references, RFCs
  (rfc-editor/datatracker), man pages (man7.org), MDN for the web platform,
  original papers, official GitHub repos. No blogspam, no tutorial mirrors,
  no Medium — *unless* the post is itself the canonical source (e.g.
  Kleppmann's Redlock critique, Aphyr's Jepsen analyses).
- **Don't pad.** The Distributed Systems guide has only ~15 external links in
  850 lines and is fully compliant: what matters is that the *load-bearing*
  claims and every named tool are linked, not a links-per-line quota.
- For **reference-heavy guides** (Postgres, SQLite, ESP32), a per-section
  `*Docs:*` pointer line linking the official chapter for that section is the
  established pattern — use it instead of scattering dozens of inline links.

## Voice and prose

Match the model's register:

- **Depth-first, concept-first, relentlessly grounded.** Every abstraction is
  anchored to a real, runnable system or command. Prefer "here is what
  actually happens when you `kubectl apply`" over generic exposition.
- **Explain why, not just what.** The model never lists a fact without its
  consequence ("more copies means more things to keep consistent").
- **Bold the load-bearing terms** on first definition; use `inline code` for
  commands, flags, identifiers, and file names.
- **Full sentences, no fragment-stacking.** Bullets and tables are for
  genuinely enumerable things; the connective reasoning lives in prose.
- Worked examples, decision trees, and "walkthrough" sections that trace one
  real operation end-to-end are the house specialty — include at least one.

## Markdown conventions

- ATX headings (`#`/`##`/`###`), `---` rules between major parts.
- Fenced code blocks with a language tag.
- Raw `<angle-bracket>` tokens in prose (generics, placeholders) are
  HTML-escaped by the build, but inside backticks or fences they pass
  through — prefer backticks for them anyway.
- Sibling-guide links are relative paths to the `.md` file from the linking
  file's directory (so from `k8s/`, link `../REDIS_STUDY_GUIDE.md`).

## Definition of done for a guide

A guide meets the standard when all of these hold:

- [ ] Intro has the thesis paragraphs, the Primary-references paragraph, and
      the sibling-guides paragraph.
- [ ] Every named tool/spec/API links to official docs on first meaningful
      mention (or the section has a `*Docs:*` pointer).
- [ ] It ends with a Where-to-Go-Next-shaped section including the
      run-and-break bullet and sibling cross-links.
- [ ] It is registered in `GUIDES` and `CATEGORIES`, summarized in
      `README.md`, and the rebuilt `html/` output is committed.
- [ ] The generated HTML has no `&amp;lt;` artifacts and its sibling links
      resolve to `.html` pages.

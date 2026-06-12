# Next.js Study Guide

A depth-first guide to Next.js in the App Router and React Server Components era — written for engineers who already know React (components, props, hooks, JSX) and general web development, but who have not yet internalized the model that modern Next.js is actually built on. If your mental picture of Next.js is "React plus file-based routing plus `getServerSideProps`," this guide is the upgrade path: that picture describes the *Pages Router*, which still ships and still matters for maintaining older codebases, but it is not how new Next.js applications are written.

The central thesis of this guide is that **modern Next.js is one big idea with a framework attached: your component tree is split between two computers.** Some components run only on the server, where they can read databases and secrets and ship zero JavaScript to the browser; some run on the client, where they can hold state and handle clicks; and the boundary between them — what crosses it, what serializes, what each side is allowed to do — is *the* concept that everything else hangs off. Routing conventions, data fetching, Server Actions, streaming, and the famously confusing caching layers are all consequences of that one split. Learn the boundary deeply (Part 3) and the rest of the framework stops feeling like a pile of special cases. This guide targets the **Next.js 16 era** as documented in 2026: App Router first, Server Components by default, the post-Next-15 caching defaults (where `fetch` is *no longer* cached unless you ask), and the newer explicit caching primitives (`'use cache'`, `cacheLife`, `cacheTag`). Learn the Pages Router only well enough to maintain code that already uses it.

It is also honest about costs. Next.js is a heavy framework with real operational opinions, a caching model that has confused thousands of competent engineers, and a gravitational pull toward one hosting vendor. Part 1 covers when Next.js is the wrong choice, and Part 10 gives a clear-eyed account of self-hosting versus Vercel. A framework you can't argue *against* is a framework you don't understand.

Primary references: the [Next.js documentation](https://nextjs.org/docs) (the App Router [Getting Started](https://nextjs.org/docs/app/getting-started) sequence is genuinely good — read it in order), the React docs on [Server Components](https://react.dev/reference/rsc/server-components), [`'use client'`](https://react.dev/reference/rsc/use-client), and [`'use server'`](https://react.dev/reference/rsc/use-server) (Next.js builds *on* these React primitives, and the React docs explain the "why" better than the framework docs do), Josh Comeau's [Making Sense of React Server Components](https://www.joshwcomeau.com/react/server-components/) (the single best visual explainer of the RSC model), and Dan Abramov's RSC essays on [overreacted.io](https://overreacted.io/) — especially [The Two Reacts](https://overreacted.io/the-two-reacts/) and [RSC for Astro Developers](https://overreacted.io/rsc-for-astro-developers/) — for the deep conceptual grounding. Companion guides in this repo: [TypeScript](TYPESCRIPT_STUDY_GUIDE.md), [Auth](AUTH_STUDY_GUIDE.md), [Testing](TESTING_STUDY_GUIDE.md), [GitHub Actions](GITHUB_ACTIONS_STUDY_GUIDE.md) (for CI), [SvelteKit](SVELTEKIT_STUDY_GUIDE.md) (a useful contrast — same problems, different answers), and [Postgres](POSTGRES.md) (the database your Server Components will talk to).

---

## Table of Contents

1. [Part 1 — What Next.js Is (and When It Isn't the Answer)](#part-1--what-nextjs-is-and-when-it-isnt-the-answer)
2. [Part 2 — The App Router: The Filesystem Is the Architecture](#part-2--the-app-router-the-filesystem-is-the-architecture)
3. [Part 3 — The Server/Client Component Boundary](#part-3--the-serverclient-component-boundary)
4. [Part 4 — Fetching Data on the Server](#part-4--fetching-data-on-the-server)
5. [Part 5 — Rendering as a Spectrum: Static, ISR, Dynamic, Streaming](#part-5--rendering-as-a-spectrum-static-isr-dynamic-streaming)
6. [Part 6 — The Caching Layers (Why Everyone Is Confused)](#part-6--the-caching-layers-why-everyone-is-confused)
7. [Part 7 — Mutations: Server Actions and Route Handlers](#part-7--mutations-server-actions-and-route-handlers)
8. [Part 8 — Middleware, Security Boundaries, and Auth](#part-8--middleware-security-boundaries-and-auth)
9. [Part 9 — Performance, Metadata, and Client-Side Discipline](#part-9--performance-metadata-and-client-side-discipline)
10. [Part 10 — Deployment, Operations, and Honest Trade-offs](#part-10--deployment-operations-and-honest-trade-offs)
11. [Appendix — Reading the Pages Router (Maintenance Mode)](#appendix--reading-the-pages-router-maintenance-mode)
12. [A Practice Track](#a-practice-track)
13. [Where to Go from Here](#where-to-go-from-here)

---

## Part 1 — What Next.js Is (and When It Isn't the Answer)

### The Problem Next.js Exists to Solve

React, by itself, is a rendering library: it turns component trees into DOM updates. It deliberately does not answer the questions every real application must answer — how URLs map to screens, where data fetching happens, how HTML gets to the browser before JavaScript loads, how images and fonts get optimized, how the thing deploys. For years the React ecosystem answered those questions with a basket of separately chosen libraries (React Router, a data-fetching layer, a bundler config, an SSR harness you maintained yourself), and the result on most teams was a **single-page application (SPA)**: a nearly empty HTML file, a large JavaScript bundle, and a loading spinner while the client fetched data over an API.

That architecture has a structural flaw that no amount of client-side cleverness fixes: the browser must download, parse, and execute your framework before it can even *start* fetching data, and the data then makes another full network round trip from the API. Next.js's founding answer (back in 2016) was server-side rendering — run React on the server, send real HTML, then "hydrate" it into an interactive app. The modern answer, and the subject of this guide, goes much further: **React Server Components (RSC)** let *most of your component tree run only on the server*, next to the data, shipping HTML and a compact serialized description to the browser, while only the genuinely interactive islands ship JavaScript. Next.js's **App Router** (introduced in Next 13, mature since 15, the only model that should be used for new code in the 16 era) is the production implementation of that architecture; the [Server and Client Components docs](https://nextjs.org/docs/app/getting-started/server-and-client-components) are the canonical reference.

So the accurate one-sentence description: **Next.js is a full-stack React framework — a router, a server, a compiler pipeline, and a caching system — whose job is to let one React codebase span the server/client divide.** You write components; the framework decides (with your guidance) which ones run where, what gets prerendered at build time, what renders per-request, and what gets cached in between.

### The Two Routers, and Why This Guide Picks One

Next.js currently ships two routing systems side by side, and you will encounter both in the wild:

- The **Pages Router** (`pages/` directory): the original model. Every component is a client component; server data enters through special page-level functions (`getServerSideProps`, `getStaticProps`); API endpoints live in `pages/api/`. It is stable, widely deployed, and in maintenance mode. Docs live under [nextjs.org/docs/pages](https://nextjs.org/docs/pages).
- The **App Router** (`app/` directory): the current model. Components are *Server Components by default*, layouts nest and persist across navigations, data fetching happens *inside* components with `async`/`await`, mutations happen through Server Actions, and rendering streams. Docs live under [nextjs.org/docs/app](https://nextjs.org/docs/app).

This guide is App Router from start to finish. Learn the Pages Router the way you'd learn Python 2 in 2020: enough to read it, migrate it, and not be surprised by it — the [upgrading guides and codemods](https://nextjs.org/docs/app/guides/upgrading) cover the mechanics. Everything new should be App Router, and almost all current documentation, library support, and React-team investment assumes it.

### When Next.js Is the Wrong Choice

This is worth settling *before* learning the framework, because Next.js has enough mindshare that it gets reached for reflexively, and several common application shapes are served worse by it:

- **A pure SPA behind a login wall.** If your app is an internal dashboard or tool where every user is authenticated, SEO is irrelevant, and the entire UI is interactive client state (think Figma, a trading terminal, an admin console), then server rendering buys you little and costs you a server, a deployment story, and the entire caching model in Part 6. **Vite + React (with React Router or TanStack Router)** gives you a static bundle you can serve from any CDN, a dramatically simpler mental model, and faster builds. Next.js *can* build SPAs (via [static export](https://nextjs.org/docs/app/guides/static-exports)), but you'd be carrying a full-stack framework to do a single-page job.
- **A simple static site.** A marketing site, a blog, a docs site with little interactivity is better served by **Astro** (which ships zero JavaScript by default and treats islands of interactivity as the exception, which matches the content-site reality) or even a classic static site generator. Next.js works fine here, but you'll be configuring your way *out* of its dynamic features rather than *into* anything you need.
- **A backend-heavy service with a thin UI.** If the hard part of your system is the backend — queues, long-running jobs, WebSockets, gRPC — Next.js's serverless-leaning, request-scoped server model will fight you. Keep the backend a real service (Node, Go, whatever fits) and let Next.js (or something lighter) be only the UI tier. Notably, **WebSockets do not fit Next.js's request/response model**; you'll run a separate socket server anyway (see the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md)).
- **A team that hates magic.** Next.js makes many decisions implicitly — what's static, what's cached, what's bundled where — based on what your code *does* rather than what you declare. Part 6 exists because that implicitness has a real cost. Frameworks like Remix/React Router v7 or SvelteKit make more of these decisions explicit; some teams are happier there.

For calibration, the honest one-line positioning of the alternatives you'd actually weigh:

| Tool | One-line positioning | Reach for it when |
|---|---|---|
| **Vite + React Router/TanStack** | a client-rendered SPA, no framework server | authenticated tools, no SEO, maximum simplicity |
| **Astro** | server-first content, zero JS by default, islands opt-in | content sites where interactivity is the exception |
| **Remix / React Router v7** | full-stack React, loaders/actions, web-standards-first, explicit over implicit | you want Next's shape with fewer implicit behaviors |
| **SvelteKit** | the same full-stack problems, Svelte's answers (see the [SvelteKit guide](SVELTEKIT_STUDY_GUIDE.md)) | you're not wedded to React |
| **Next.js** | full-stack React with RSC, the deepest feature set and the most machinery | the mixed static/dynamic, SEO-plus-app products below |

Where Next.js earns its weight: content + commerce sites that need SEO *and* rich interactivity, multi-tenant SaaS with public marketing pages and authenticated app surfaces in one codebase, anything where time-to-first-byte and Core Web Vitals are business metrics, and teams that want the data layer and the UI in one repository with one deployment. That's a large fraction of real web products, which is why Next.js is worth a guide this long.

### Getting Set Up

Start every project with the official scaffolder rather than hand-assembling a baseline — it keeps you aligned with current conventions, and every doc and example maps cleanly onto what it generates ([Installation docs](https://nextjs.org/docs/app/getting-started/installation)):

```bash
npx create-next-app@latest my-app
# Interactive prompts: TypeScript? Yes. ESLint? Yes. Tailwind? Your call.
# src/ directory? Yes. App Router? Yes. Import alias (@/*)? Yes.
```

Say yes to TypeScript without hesitation. Next.js's TypeScript integration ([docs](https://nextjs.org/docs/app/api-reference/config/typescript)) goes beyond type-checking your code: with `typedRoutes` enabled in `next.config.ts` and the `next typegen` command, the compiler knows your route tree, so a `<Link href="/dasboard">` typo is a build error instead of a 404 in production. In a framework where the filesystem *is* the router, having the compiler understand the filesystem is a category of test you no longer have to write. Pair it with [`eslint-config-next`](https://nextjs.org/docs/app/api-reference/config/eslint) (the Core Web Vitals variant), which catches framework-specific misuse — a raw `<img>` where `next/image` belongs, a `<a href>` where `<Link>` belongs — that generic React lint rules can't see.

Four CLI commands carry the whole workflow, and knowing which mode you're in explains many "framework bugs" ([CLI docs](https://nextjs.org/docs/app/api-reference/cli/next)):

```bash
next dev      # development server: lazy compilation, hot reload, NO production caching
next build    # production build: this is where static rendering and caching decisions are made
next start    # serve the production build — the only way to see real caching behavior locally
next typegen  # generate route types without a full build
```

The single most important habit here: **`next dev` does not behave like production.** Caching is largely disabled, every page renders dynamically, and rendering-mode decisions haven't been made yet. When something "works in dev but not in prod" (or vice versa), run `next build && next start` locally before filing the mental bug report. `next build`'s output even prints a per-route summary — which routes are static (`○`), which are dynamic (`ƒ`) — and reading that table after every significant change is the cheapest observability you'll ever get.

A maintainable project shape, which the rest of this guide assumes:

```text
src/
  app/                      # the route tree: layouts, pages, route handlers (Part 2)
  components/               # shared UI components
  features/                 # feature folders: components, actions, queries, tests together
  lib/                      # server utilities: db client, auth helpers, validation schemas
  hooks/                    # client-side custom hooks
  middleware.ts             # request-time logic (Part 8) — named proxy.ts in Next 16
  instrumentation.ts        # server observability hooks (Part 10)
public/                     # static assets served verbatim
next.config.ts              # framework configuration
```

The principle behind this layout: **keep reads near the Server Component that renders them and writes near the feature that owns them.** The App Router rewards colocation — a route's components, its loading state, its Server Actions, and its tests can all live next to the route — and fights you if you funnel everything through a giant horizontal `services/` layer. Treat the filesystem as part of the design, because in this framework it literally is.

If you remember one thing from Part 1: **Next.js is the answer when one codebase must span server and client — content sites, commerce, SaaS with public surfaces. It is the wrong answer for pure SPAs and simple static sites, and `next dev` is not production.**

---

## Part 2 — The App Router: The Filesystem Is the Architecture

In most frameworks the router is a data structure you write in code. In the App Router, **the router is your `app/` directory**: every folder is a URL segment, and a handful of specially named files (`page.tsx`, `layout.tsx`, `route.ts`, `loading.tsx`, `error.tsx`) declare what exists at each segment. This is more than a convenience — it means you can read a project's URL structure, layout nesting, and error-handling strategy straight off the file tree, and it means the framework can make per-segment decisions (caching, streaming, code-splitting) because the segments are statically known. The [project structure docs](https://nextjs.org/docs/app/getting-started/project-structure) and [file conventions reference](https://nextjs.org/docs/app/api-reference/file-conventions) are the canonical maps.

### Pages and Layouts: The Two Load-Bearing Files

A route becomes publicly accessible when its folder contains a `page.tsx`. A `layout.tsx` wraps every route at or below its level — and layouts **nest**: the UI for `/dashboard/settings` is the root layout, wrapping the dashboard layout, wrapping the settings page. Here is the minimal real shape of an app:

```text
app/
├── layout.tsx          # root layout: <html>, <body> — required, wraps everything
├── page.tsx            # the UI for "/"
└── dashboard/
    ├── layout.tsx      # dashboard shell: sidebar, nav — wraps everything below
    ├── page.tsx        # the UI for "/dashboard"
    └── settings/
        └── page.tsx    # the UI for "/dashboard/settings"
```

The root layout is the one file every app must have. It owns the document itself:

```tsx
// app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

Notice there's no `<head>` management here — metadata is handled declaratively (Part 9) — and no router plumbing. The layout receives `children` and renders them; the framework supplies the correct child for the current URL. A nested layout looks the same, minus the document tags:

```tsx
// app/dashboard/layout.tsx
import { Sidebar } from "@/components/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1">{children}</main>
    </div>
  );
}
```

The property that makes layouts more than a DRY trick: **layouts persist across navigations.** When the user navigates from `/dashboard` to `/dashboard/settings`, the dashboard layout does not re-render or remount — React reconciles only the part of the tree that changed (the page), so the sidebar keeps its scroll position and any client state survives. This is what made "nested layouts" the App Router's headline feature, and it's why you should model your real UI shells (marketing chrome, authenticated app shell, settings sub-nav) as layouts rather than copying wrapper components into every page ([Layouts and Pages docs](https://nextjs.org/docs/app/getting-started/layouts-and-pages)).

Occasionally persistence is exactly what you *don't* want — a per-page entrance animation, or state that must reset on every navigation. That's what `template.tsx` is for: identical in shape to a layout, except it remounts with fresh state on each navigation:

```tsx
// app/dashboard/template.tsx — remounts per navigation; a layout would persist
export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-in">{children}</div>;   // entrance animation re-runs each time
}
```

If you've ever had a "stale local state survived navigation" bug, the fix was probably "this should have been a template" — or more often, "this state should have lived in the URL."

Two more structural tools round out the basics. **Route groups** — folders named in parentheses, like `(marketing)` and `(app)` — organize the tree and scope layouts *without* affecting URLs: `app/(marketing)/about/page.tsx` still serves `/about`, but it gets the marketing layout while `(app)` routes get the authenticated shell ([Route Groups docs](https://nextjs.org/docs/app/api-reference/file-conventions/route-groups)). And **colocation is safe by design**: any file in `app/` that isn't one of the special names (a `components/` folder inside a route, a test file, a fixture) is simply not routable, so you can keep a feature's private pieces next to the route that owns them.

### Dynamic Segments

Real applications have entity pages, and entity pages need parameters. A folder named in square brackets is a dynamic segment ([docs](https://nextjs.org/docs/app/api-reference/file-conventions/dynamic-routes)):

```text
app/
└── posts/
    ├── page.tsx              # /posts            — the listing
    └── [slug]/
        └── page.tsx          # /posts/hello-rsc  — one post; params.slug === "hello-rsc"
```

The page receives its parameters as a prop — and note that in current Next.js, `params` is a **Promise**, because the framework may begin rendering the static parts of a page before request-specific values are resolved:

```tsx
// app/posts/[slug]/page.tsx
export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPost(slug);          // direct data access — this is Part 4's subject
  return <article>{/* ... */}</article>;
}
```

That `async` keyword on a component is not a typo, and it's the first visible evidence of the model Part 3 explains: this component runs only on the server, so it can await things. Two variants of the bracket syntax cover the remaining cases: `[...slug]` (catch-all) matches `/docs/a/b/c` and yields `slug: ["a", "b", "c"]` — the workhorse of docs sites — and `[[...slug]]` (optional catch-all) additionally matches the bare `/docs`. Whether dynamic routes get prerendered at build time is the job of `generateStaticParams`, covered with the rendering spectrum in Part 5.

### Navigation: Links, Hooks, and the URL as State

Navigation between routes uses the [`<Link>`](https://nextjs.org/docs/app/api-reference/components/link) component, which renders a real `<a>` tag (so middle-click, cmd-click, and crawlers all work) but intercepts same-app clicks to perform a **client-side transition**: instead of a full page load, the router fetches just the RSC payload for the segments that changed and swaps them in, preserving layouts as described above. In production, links **prefetch** routes as they scroll into the viewport, which is a large part of why App Router navigation feels instant — and also one of the cache layers in Part 6, which is why it's worth knowing it exists now ([Linking and Navigating docs](https://nextjs.org/docs/app/getting-started/linking-and-navigating)).

For imperative, client-side navigation logic there are three hooks — [`useRouter`](https://nextjs.org/docs/app/api-reference/functions/use-router) (`router.push`, `router.refresh`), `usePathname`, and [`useSearchParams`](https://nextjs.org/docs/app/api-reference/functions/use-search-params) — all usable only in Client Components. On the server side, you don't navigate; you short-circuit rendering with framework functions: [`redirect()`](https://nextjs.org/docs/app/api-reference/functions/redirect) and `permanentRedirect()` throw a special control-flow exception that the framework converts into the right HTTP redirect or client transition, and [`notFound()`](https://nextjs.org/docs/app/api-reference/functions/not-found) renders the nearest `not-found.tsx`. Use these instead of hand-rolled conditionals; they behave correctly in every rendering context (initial load, client transition, inside a Server Action).

A design principle that pays for itself in every Next.js app: **state that describes *what the user is looking at* belongs in the URL, not in `useState`.** Filters, sort orders, pagination, open tabs, search queries — putting them in search params makes views shareable and refresh-proof, makes the back button correct for free, and (crucially in this architecture) makes the state *visible to the server*, so a Server Component can render the filtered table directly:

```tsx
// app/orders/page.tsx — searchParams is the URL's query string, available on the server
export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; page?: string }>;
}) {
  const { status = "all", page = "1" } = await searchParams;
  const orders = await getOrders({ status, page: Number(page) });
  return <OrdersTable orders={orders} currentStatus={status} />;
}
```

The client side of the pattern is a small Client Component that updates the URL rather than setting local state:

```tsx
// app/orders/status-filter.tsx
"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

export function StatusFilter({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function setStatus(status: string) {
    const params = new URLSearchParams(searchParams);   // preserve other params (page, sort...)
    params.set("status", status);
    params.delete("page");                              // a filter change resets pagination
    router.push(`${pathname}?${params.toString()}`);    // navigation, not setState
  }

  return (
    <select value={current} onChange={(e) => setStatus(e.target.value)}>
      <option value="all">All</option>
      <option value="shipped">Shipped</option>
      <option value="pending">Pending</option>
    </select>
  );
}
```

The `router.push` re-renders the Server Component with the new `searchParams`, and the server-rendered table comes back filtered. No client data fetching, no state synchronization between a filter store and a query — the URL *is* the state, and deep links, refresh, and the back button all work because of it. Notice also the small craftsmanship details the pattern forces you to think about (preserving unrelated params, resetting pagination on filter change); they're the difference between URL state that works and URL state that users trust.

### Parallel and Intercepting Routes

Two advanced conventions solve problems that are genuinely awkward otherwise; recognize the use cases even if you defer mastering them.

**Parallel routes** ([docs](https://nextjs.org/docs/app/api-reference/file-conventions/parallel-routes)) let one layout render multiple independent slots — folders named `@analytics`, `@team` become extra props on the layout alongside `children`:

```text
app/dashboard/
├── layout.tsx          # receives { children, analytics, team } as props
├── page.tsx            # → children
├── @analytics/
│   ├── page.tsx        # → analytics slot
│   └── loading.tsx     # this slot's OWN loading boundary
└── @team/
    └── page.tsx        # → team slot
```

```tsx
// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  analytics,
  team,
}: {
  children: React.ReactNode;
  analytics: React.ReactNode;
  team: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="col-span-2">{children}</div>
      {analytics}
      {team}
    </div>
  );
}
```

The payoff over ordinary composition is that each slot is a full route subtree with its *own* `loading.tsx` and `error.tsx` — a slow analytics panel streams in (Part 5) and a crashing one degrades (Part 5 again) without taking its siblings down. Parallel routes are for independently rendered *page regions* with independent lifecycles, not a fancier way to put two components side by side.

**Intercepting routes** ([docs](https://nextjs.org/docs/app/api-reference/file-conventions/intercepting-routes)) let a *navigation* render different UI than a *direct visit* to the same URL. The canonical use is the modal-over-list pattern — click a photo in a gallery and it opens as a modal; paste the same URL into a new tab and you get the full page:

```text
app/
├── layout.tsx                    # renders both children and the @modal slot
├── @modal/
│   ├── default.tsx               # renders null when no modal is active
│   └── (.)photos/[id]/page.tsx   # intercepts client navigations to /photos/:id → modal
└── photos/
    ├── page.tsx                  # the gallery grid
    └── [id]/page.tsx             # direct visits / refreshes → the full standalone page
```

The `(.)` prefix means "intercept same-level navigations" (`(..)` walks up a level). When a user soft-navigates from the gallery to `/photos/42`, the router serves the intercepting route — a thin page that renders the photo inside a `<dialog>` in the `@modal` slot — while the URL bar honestly says `/photos/42`. Refresh that URL, or arrive from a shared link, and there's no client navigation to intercept, so `photos/[id]/page.tsx` renders the full page. Shareable URLs, a working back button (the modal closes), and modal UX, with zero global modal state: this is the structurally honest version of a pattern people have faked with `isModalOpen` booleans for a decade.

Finally, every segment can export configuration constants — the [Route Segment Config](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config): `export const dynamic = "force-static"`, `export const revalidate = 3600`, `export const runtime = "nodejs"`, `maxDuration`, and friends. These knobs are where routing meets the rendering and caching machinery, so they're covered where they belong, in Parts 5 and 6.

If you remember one thing from Part 2: **folders are URL segments, `page.tsx` makes a segment public, layouts nest and persist across navigations, and state describing what the user sees belongs in the URL where the server can read it.**

```quiz
Q: In the App Router, what makes a route folder publicly accessible as a URL?
- [ ] Any file inside it
- [x] A `page.tsx` (or `route.ts`) in the folder — other files (components, tests, fixtures) colocated there aren't routable
- [ ] Adding it to a router config
- [ ] A `layout.tsx`
> The router *is* the `app/` directory: folders are URL segments, but a segment only becomes a public route when it contains a `page.tsx` (or a `route.ts` for an API endpoint). This is why colocation is safe — any non-special file in `app/` is simply not routable, so you can keep a feature's private components next to the route that owns them.

Q: Why is "layouts persist across navigations" the App Router's headline property?
- [ ] It makes pages load slower but look nicer
- [x] Navigating between routes under a layout reconciles only the changed page, so the layout doesn't remount — sidebar scroll position and client state survive the navigation
- [ ] Layouts re-render on every navigation to stay fresh
- [ ] It disables client-side routing
> When you go from `/dashboard` to `/dashboard/settings`, React reconciles only the part of the tree that changed (the page), leaving the dashboard layout mounted — so its sidebar keeps scroll position and any client state. That's why you model real UI shells as nested layouts rather than copying wrapper components into each page. When you specifically *want* a reset/remount per navigation, that's `template.tsx`.

Q: What problem do route groups like `(marketing)` and `(app)` solve?
- [ ] They add a URL prefix
- [x] They organize the tree and scope different layouts to different sections *without* affecting the URL — `(marketing)/about` still serves `/about`
- [ ] They make routes private
- [ ] They cache routes separately
> A folder named in parentheses is omitted from the URL, so `app/(marketing)/about/page.tsx` still resolves to `/about` while letting marketing routes use one layout and `(app)` routes use the authenticated shell. It's how you give sections of the app distinct chrome without contorting the URL structure or duplicating wrappers.
```

---

## Part 3 — The Server/Client Component Boundary

This is the heart of the guide. Every confusing thing about modern Next.js — why you can't pass a function as a prop *here* but can *there*, why a tiny `'use client'` at the wrong spot balloons your bundle, why context providers need a wrapper file, why the caching model is shaped the way it is — traces back to one architectural fact: **your single React tree is evaluated by two different computers, and the boundary between them is a serialization boundary.** Spend your energy here. The best long-form treatments are Josh Comeau's [Making Sense of React Server Components](https://www.joshwcomeau.com/react/server-components/), Dan Abramov's [The Two Reacts](https://overreacted.io/the-two-reacts/), and the React reference pages for [Server Components](https://react.dev/reference/rsc/server-components) and [`'use client'`](https://react.dev/reference/rsc/use-client); what follows is the working model.

### Two Environments, One Tree

A **Server Component** runs *only* on the server — at build time or at request time, never in the browser. Because it never ships to the client, it can do things no browser component could ever do: query the database directly, read files, use secret API keys, import enormous dependencies (a markdown parser, a syntax highlighter) without anyone downloading a byte of them. And because it never re-renders on the client, it has no interactivity: no `useState`, no `useEffect`, no event handlers, no browser APIs. Its output is not JavaScript — it's a serialized description of rendered UI.

A **Client Component** is what you've always called "a React component": it server-renders once to HTML (yes — *client* components still participate in SSR; the name means "runs *on* the client," not "renders *only* on the client"), then hydrates in the browser, where it can hold state, run effects, and handle events. Its code ships in the JavaScript bundle.

In the App Router, **every component is a Server Component unless it opts out.** The opt-out is the `'use client'` directive at the top of a file:

```tsx
// components/add-to-cart.tsx
"use client";

import { useState } from "react";

export function AddToCart({ productId }: { productId: string }) {
  const [pending, setPending] = useState(false);
  return (
    <button disabled={pending} onClick={() => {/* ... */}}>
      Add to cart
    </button>
  );
}
```

The critical subtlety: `'use client'` does not mean "this component is a client component." It means **"the server/client boundary is here"** — this module and *everything it imports, transitively* belongs to the client bundle. It marks a door in the module graph, not a property of one component. A component imported by a `'use client'` file is a client component *even with no directive of its own*. This is why one careless `'use client'` near the root of the tree can quietly drag half your codebase, and its dependencies, into the browser bundle: you didn't mark a component, you moved a door. The practical discipline that follows is **push client boundaries to the leaves** — the page, the layouts, the data-shaped middle of the tree stay server; the interactive widgets at the edges (a button, a search box, a chart) are small `'use client'` islands.

While we're disambiguating directives: **`'use server'` does not mark Server Components.** Server Components have no directive at all — they're the default. `'use server'` marks *Server Functions* (Part 7): functions the client is allowed to call remotely. Misreading `'use server'` as "the opposite of `'use client'`" is probably the single most common Next.js misconception; the two directives both mark doors between the worlds, but in opposite directions ([`'use server'` reference](https://react.dev/reference/rsc/use-server)).

### What Crosses the Boundary: Serialization

When a Server Component renders, the server produces the **RSC payload**: a compact serialized tree describing the rendered output. It's worth seeing the shape of the thing, even schematically, because it makes the whole model concrete — for the product page above, the payload is conceptually:

```text
<main>
  <h1>Trail Running Shoe</h1>            ← server output: finished UI, no component code
  <p>$129.00</p>
  <div class="prose">…rendered markdown…</div>
  ⟨ClientRef: "./add-to-cart.js#AddToCart"
    props: { productId: "prod_123" }⟩    ← client island: a module REFERENCE + serialized props
  …
</main>
```

The server parts arrive as *finished UI* — their component code never existed as far as the browser knows. Each Client Component arrives as a **reference** — "load this module from the bundle, mount it here, with these props." The browser renders the whole description (server parts inert, immediately visible) and hydrates only the referenced islands. This is also exactly what travels on soft navigations: the router fetches the changed segments' RSC payload, not a new HTML document — which is why navigation can preserve client state in unchanged parts of the tree (Part 2's persistent layouts are this payload's diffing behavior, seen from above).

Because Client Component props are literally written into that serialized payload and shipped over the network, **everything a Server Component passes to a Client Component must be serializable** by React's serializer. The allowed set is generous — JSON types plus Dates, Maps, Sets, TypedArrays, FormData, Promises (the basis of streaming data to the client), and JSX — but the exclusions are exactly the things people try first:

| Crosses the boundary ✅ | Does not cross ❌ |
|---|---|
| primitives, plain objects, arrays | **functions** (incl. event handlers) — except Server Functions |
| `Date`, `Map`, `Set`, `BigInt`, `FormData` | class instances (an ORM entity, a `db` client) |
| Promises (await them client-side with `use()`) | JSX from arbitrary closures, symbols |
| JSX / `React.ReactNode` (see below) | anything with methods you expected to survive |

The error `"Functions cannot be passed directly to Client Components"` is this table speaking. The fixes are mechanical once you have the model: don't pass an ORM entity, pass a plain DTO (`{ id, name, price }`); don't pass `onDelete={() => db.delete(id)}`, pass a Server Function (Part 7) or move the handler inside the client island.

### The Pattern That Unlocks Composition: Children as Props

The boundary rule that confuses everyone, stated carefully: a Client Component cannot *import* a Server Component (importing would pull server code into the client bundle — the door swings one way). But a Client Component can absolutely **render** a Server Component that was passed to it as a prop. The distinction is *who creates the JSX*:

```tsx
// components/theme-provider.tsx — a client wrapper
"use client";
import { createContext, useState } from "react";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}
```

```tsx
// app/layout.tsx — a Server Component
import { ThemeProvider } from "@/components/theme-provider";
import { ServerRenderedNav } from "@/components/server-nav";   // server component — DB access, no JS shipped

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>          {/* client island... */}
          <ServerRenderedNav />  {/* ...with server-rendered children inside it */}
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

Why this works: the *server* evaluates `<ServerRenderedNav />` while rendering the layout, producing serialized UI; the `ThemeProvider` receives that already-rendered output as its `children` prop — a slot of finished UI, not a component to execute. The client component is a picture frame; the server can put anything it likes inside the frame before shipping it. This **children-as-props** (or "slot") pattern is how server content nests inside interactive shells — context providers, animated wrappers, drag handles — without surrendering the whole subtree to the client bundle. If you internalize one composition pattern in all of Next.js, make it this one; Josh Comeau's article visualizes it better than any prose can.

(That example also shows the standard answer to "where do context providers go?": context is a client-side mechanism, so providers live in a small `'use client'` wrapper rendered high in a server layout, with everything else passing through as `children`. Server Components can't consume context — they don't need to; they can just read the data.)

### Choosing a Side: The Decision Table

| Concern | Server Component | Client Component |
|---|---|---|
| Fetch data / query DB | ✅ directly, with `await` | via props, or client fetching |
| Use secrets, server-only SDKs | ✅ safe — never shipped | ❌ everything is public |
| `useState` / `useEffect` / hooks | ❌ | ✅ |
| Event handlers (`onClick`...) | ❌ | ✅ |
| Browser APIs (`window`, `localStorage`) | ❌ | ✅ |
| JS bundle cost | **zero** | code + deps ship to browser |
| Re-renders after load | only via router refresh / revalidation | freely, on state change |

The heuristic that falls out: **server until proven client.** Render data on the server; reach for `'use client'` only when a component needs state, effects, events, or browser APIs — and when you do, make the island as small and as leaf-ward as possible. Here's the heuristic applied to a product page, the example worth keeping in your head:

```tsx
// app/products/[slug]/page.tsx — Server Component (no directive: the default)
import Markdown from "heavy-markdown-renderer";       // big dep — stays on the server, ships 0 bytes
import { AddToCart } from "./add-to-cart";            // 'use client' — a small island
import { ImageCarousel } from "./image-carousel";     // 'use client' — another island

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProduct(slug);             // direct DB read — safe here

  return (
    <main>
      <ImageCarousel images={product.images} />       {/* serializable prop: array of plain objects */}
      <h1>{product.name}</h1>
      <p>{formatPrice(product.priceCents)}</p>
      <Markdown source={product.description} />       {/* rendered to HTML on the server */}
      <AddToCart productId={product.id} />            {/* serializable prop: a string */}
      <Reviews productId={product.id} />              {/* nested async server component */}
    </main>
  );
}
```

Everything data-shaped — the name, the price, the markdown-rendered description, the reviews — is server-rendered HTML carrying zero JavaScript; the two things a user actually *interacts with* are small client islands receiving plain serializable props. The wrong version — `'use client'` at the top of the page — works, renders identically, and silently ships the markdown renderer, the data-fetching scaffolding it would then require, and all their dependencies to every visitor. Nothing warns you; the only symptom is a bundle that grows a little with every feature, forever. This is why bundle auditing is a Part 9 ritual rather than a one-time setup step.

Two mechanical notes that prevent late-night confusion. First, **Client Components still render on the server once** — that's the SSR half of their lifecycle, which is why `window` is undefined during their first render and why a `typeof window !== "undefined"` guard (or `next/dynamic` with `ssr: false`, Part 9) is occasionally necessary for browser-only libraries. Hydration then attaches interactivity in the browser, and the classic "hydration mismatch" error means your component rendered different output on the server than on the client — almost always `Date.now()`, `Math.random()`, or locale-dependent formatting in the render path. Second, the boundary is *per module graph entry*, so a shared `utils.ts` imported from both sides simply gets compiled twice, once for each world — fine for pure functions, and the reason `server-only` (Part 8) exists for the modules where it isn't fine.

Honest trade-offs in the other direction: client components are *simpler to reason about* for highly interactive UI (no boundary to negotiate), libraries that predate RSC often require them, and per-interaction updates (typeahead, drag-and-drop, optimistic UI) are inherently client work. RSC is not "client components are bad"; it's "stop paying the client-component tax for the 80% of your tree that's just data presentation." Dan Abramov's framing in [The Two Reacts](https://overreacted.io/the-two-reacts/) is the right one: the two kinds of components are answers to two different questions — *what does this UI look like given the data* (server) versus *how does this UI behave under interaction* (client) — and a real product is always both.

If you remember one thing from Part 3: **`'use client'` marks a door in the module graph, only serializable data fits through the door, and `children` lets you pass finished server-rendered UI through a client component without opening the door any wider.**

```quiz
Q: What does `'use client'` at the top of a module actually mark?
- [ ] That this one component is a client component
- [x] The server/client boundary — this module *and everything it transitively imports* belongs to the client bundle; it marks a door in the module graph, not a property of one component
- [ ] That the component can't use hooks
- [ ] That the component is server-rendered only
> `'use client'` doesn't label a single component; it moves the boundary. Every module imported (transitively) by a `'use client'` file becomes client code, even without its own directive. That's why one careless directive near the root drags half the tree and its dependencies into the browser bundle — and why the discipline is to push client boundaries to the leaves (small interactive islands) and keep the data-shaped middle on the server.

Q: Why does passing `onDelete={() => db.delete(id)}` from a Server Component to a Client Component throw "Functions cannot be passed directly to Client Components"?
- [ ] Functions are too large to serialize
- [x] Client Component props are written into the serialized RSC payload and shipped over the network, and arbitrary functions (and class instances) aren't serializable — only things like primitives, plain objects, Dates, Promises, and JSX cross
- [ ] The database isn't available on the client
- [ ] onDelete is a reserved prop name
> A Server Component passes props to a client island by serializing them into the payload sent to the browser, so the values must be serializable by React's serializer. Functions, ORM entities, and other class instances aren't — pass a plain DTO instead of an entity, and a Server Function (Part 7) or an in-island handler instead of a closure. The error is the serialization boundary speaking.

Q: A Client Component can't *import* a Server Component, yet the ThemeProvider example renders server-rendered content inside a client wrapper. How?
- [ ] It uses dynamic import
- [x] The server creates the JSX (`<ServerRenderedNav />`) and passes it as the `children` prop — the client component receives already-rendered UI to slot in, rather than importing and executing server code
- [ ] The server component is secretly a client component
- [ ] It disables the boundary
> Importing a Server Component into a client module would pull server code into the bundle (the door swings one way). But *rendering* a server component passed as `children` is fine: the server evaluates it to finished UI, and the client component places that slot inside itself like a picture frame. This children-as-props pattern is how context providers and interactive shells wrap server content without surrendering the subtree to the client bundle.
```

---

## Part 4 — Fetching Data on the Server

The Pages Router and the SPA era both trained a reflex: components don't fetch, they receive — data comes from `getServerSideProps`, or from a `useEffect`+`fetch` dance, or from a client cache library. The App Router retires the reflex. **A Server Component is an `async` function that runs next to your data, so it just... reads the data**, in the component, at the point of use ([Fetching Data docs](https://nextjs.org/docs/app/getting-started/fetching-data)):

```tsx
// app/dashboard/page.tsx
import { db } from "@/lib/db";

export default async function DashboardPage() {
  const projects = await db.query.projects.findMany({ orderBy: desc(projects.updatedAt) });
  return (
    <section>
      <h1>Projects</h1>
      <ul>{projects.map((p) => <li key={p.id}><ProjectCard project={p} /></li>)}</ul>
    </section>
  );
}
```

Sit with how much infrastructure that snippet deletes. There is no API route serving this data, no client-side fetching library, no loading-state `useState`, no serialization endpoint to keep in sync with the UI. The component has direct access to the database (this is safe precisely because Server Components never ship to the browser — Part 3), and the rendered HTML arrives with the data already in it. The same applies to external APIs via plain `fetch` — which Next.js extends with caching options covered in Part 6 — and the error-handling idioms are the framework's control-flow functions rather than try/catch theater:

```tsx
// app/repos/[name]/page.tsx
import { notFound } from "next/navigation";

export default async function RepoPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const res = await fetch(`https://api.github.com/repos/vercel/${name}`, {
    next: { revalidate: 600 },                 // freshness contract, declared at the read (Part 6)
  });

  if (res.status === 404) notFound();          // expected absence → the designed not-found page
  if (!res.ok) throw new Error(`GitHub ${res.status}`);   // unexpected → nearest error.tsx (Part 5)

  const repo = await res.json();
  return <article>{/* ... */}</article>;
}
```

The split in those two lines is the same expected-vs-unexpected principle that runs through Parts 5 and 7: a missing record is a *product state* with designed UI; an upstream 500 is a genuine failure for the error boundary. (One habit to carry from your backend life: `fetch` doesn't throw on HTTP error statuses, so the `res.ok` check is on you — forever, in every runtime.)

A corollary worth making explicit, because the docs do ([Backend for Frontend guide](https://nextjs.org/docs/app/guides/backend-for-frontend)): **do not call your own Route Handlers from Server Components.** If the caller is already on the server, fetching `https://yourapp.com/api/projects` from a component adds an HTTP hop, a second serialization, and a duplicated auth check, for zero benefit. Route Handlers (Part 7) are for *external* HTTP consumers. Inside the server, call the function. The clean factoring is a thin **data layer** — plain functions in `lib/` or per-feature `queries.ts` files that take typed arguments, enforce authorization, and return DTOs — which both Server Components and Server Actions call directly. (This data layer is also where security wants to live — Part 8.)

### Waterfalls, and How to Avoid Drowning

The classic performance failure of server-side data fetching is the **waterfall**: awaiting things one after another that could have run together.

```tsx
// ❌ Sequential: total latency = user + notifications + analytics
const user = await getUser(id);
const notifications = await getNotifications(id);
const analytics = await getAnalytics(id);

// ✅ Parallel: total latency = the slowest of the three
const [user, notifications, analytics] = await Promise.all([
  getUser(id),
  getNotifications(id),
  getAnalytics(id),
]);
```

The rule is the same one you know from any async runtime: **start everything that doesn't depend on something else before you await anything.** But RSC adds a second, sneakier waterfall: the *component-tree* waterfall. If `<Page>` awaits its data, then renders `<Reviews>`, which awaits *its* data, you've serialized the fetches across components even though each component looks innocent in isolation. Two tools fix it. The first is to start promises high and pass them down *unresolved* — recall from Part 3's serialization table that Promises cross the boundary — letting a Client Component await them with React's [`use()`](https://react.dev/reference/react/use) hook:

```tsx
// app/profile/page.tsx — Server Component
import { Suspense } from "react";
import { ActivityPanel } from "./activity-panel";

export default function ProfilePage() {
  const activityPromise = getActivity();          // STARTED here — deliberately not awaited
  return (
    <main>
      <ProfileHeader />                           {/* renders immediately */}
      <Suspense fallback={<ActivitySkeleton />}>
        <ActivityPanel activityPromise={activityPromise} />
      </Suspense>
    </main>
  );
}
```

```tsx
// app/profile/activity-panel.tsx
"use client";
import { use } from "react";

export function ActivityPanel({ activityPromise }: { activityPromise: Promise<Activity[]> }) {
  const activity = use(activityPromise);          // suspends until the streamed value arrives
  return <ul>{activity.map((a) => <li key={a.id}>{a.summary}</li>)}</ul>;
}
```

The page doesn't block on the slow query — the promise *itself* is serialized into the RSC payload, the server streams its resolution when ready, and the Suspense boundary shows a skeleton in the meantime. The second tool — usually simpler — is to keep the await in a nested *server* component and give the slow subtree its own `<Suspense>` boundary so it streams independently rather than blocking the page; that's the subject of Part 5. Either way the principle is identical: **starting work and waiting for work are separate decisions**, and the waterfall is what happens when you let them collapse into one `await`.

One more piece of machinery keeps the "fetch where you use it" style from being wasteful: **request memoization.** During a single render pass, identical `fetch(url, options)` calls are automatically deduplicated — five components each fetching the current user produce one request. For non-`fetch` data access (your database client), wrap the function in React's [`cache()`](https://react.dev/reference/react/cache) to get the same per-request deduplication:

```tsx
// lib/queries.ts
import { cache } from "react";
import "server-only";                       // build error if this leaks into client code (Part 8)

export const getCurrentUser = cache(async () => {
  const session = await readSession();
  return session ? db.query.users.findFirst({ where: eq(users.id, session.userId) }) : null;
});
```

Now `getCurrentUser()` can be called from the layout, the page, and three nested components, and the database is hit once per request. This is *not* caching across requests — memoization lives and dies with one render pass — but it's what makes colocated data access architecturally free. (The cross-request caches are Part 6's tangle.)

If you remember one thing from Part 4: **fetch where the data is used, in async Server Components, through a thin authorized data layer — start independent reads in parallel, and let `cache()`/memoization make repeated reads free within a request.**

---

## Part 5 — Rendering as a Spectrum: Static, ISR, Dynamic, Streaming

The old vocabulary — "SSG site" vs "SSR site" — treated rendering mode as a property of the whole application. The App Router's model is better understood as a **spectrum, chosen per route (and increasingly per *part* of a route)**, where the question is always the same: *when does this HTML get produced, and how stale may it be?* From cheapest to freshest ([Rendering Philosophy](https://nextjs.org/docs/app/guides/rendering-philosophy)):

| Mode | HTML produced | Freshness | Cost per request | Fits |
|---|---|---|---|---|
| **Static** | once, at build | frozen until redeploy | ~zero (CDN) | marketing, docs, blog posts |
| **ISR** (incremental static regeneration) | at build, re-generated on an interval or on demand | bounded staleness | ~zero, occasional regeneration | product pages, CMS content |
| **Dynamic** | per request | always fresh, per-user | a server render every time | dashboards, anything cookie-/auth-dependent |
| **Streaming** | per request, **in pieces** | fresh, but *progressive* | same as dynamic, better UX | dynamic pages with slow parts |

### Static by Default, Dynamic by Inference

Here's the part that surprises people: you usually don't *choose* a mode — **Next.js infers it from what your code does.** At `next build`, every route is prerendered as static *unless* rendering it touches request-time information: awaiting [`cookies()`](https://nextjs.org/docs/app/api-reference/functions/cookies) or [`headers()`](https://nextjs.org/docs/app/api-reference/functions/headers), reading `searchParams`, using an uncached `fetch`, or an explicit `export const dynamic = "force-dynamic"`. Touch any of those and the route becomes dynamic — rendered per request. This inference is elegant and occasionally maddening: importing one helper that reads `cookies()` deep in a utility file silently flips a whole route from CDN-cheap to server-rendered. The `next build` output table (`○` static, `ƒ` dynamic) is your audit; read it after meaningful changes, and treat an unexpected `ƒ` as a regression to investigate.

Dynamic *routes* (the `[slug]` kind) are dynamic-rendered by default — the build can't know the universe of slugs. Unless you tell it, with [`generateStaticParams`](https://nextjs.org/docs/app/api-reference/functions/generate-static-params):

```tsx
// app/posts/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((post) => ({ slug: post.slug }));   // each entry → one prerendered page
}

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) notFound();
  return <article>{/* ... */}</article>;
}
```

Now every known post is rendered to HTML at build time and served statically. Slugs *not* returned (a post published after the deploy) are rendered on first request and then cached — and `export const dynamicParams = false` turns that fallback off, making unknown slugs hard 404s. You don't have to return *every* slug either; returning the top 100 posts and letting the long tail render on demand is a standard cost/build-time trade.

ISR is static rendering with an expiry date — the middle of the spectrum, and the workhorse of content sites ([ISR guide](https://nextjs.org/docs/app/guides/incremental-static-regeneration)). One export changes the contract:

```tsx
export const revalidate = 3600;   // this page's static copy may be up to an hour stale
```

Requests are served from the static copy instantly; after the window passes, the *next* request still gets the stale copy but triggers a background regeneration (stale-while-revalidate), and subsequent requests get the fresh one. You get CDN economics with bounded staleness — and when "an hour stale" isn't acceptable for a specific event ("the author just edited this post"), on-demand revalidation (Part 6) purges exactly the affected pages immediately.

### Streaming: Don't Make the Fast Parts Wait for the Slow Parts

Plain dynamic rendering has an ugly failure mode: the page is as slow as its slowest data dependency, and the user stares at a blank tab while your slowest query runs. Streaming fixes the *experience* without fixing the query: the server sends HTML **in chunks as parts of the tree finish rendering**, so the shell appears immediately and slow regions fill in. In the App Router this isn't an exotic configuration — it falls out of React `<Suspense>` ([Streaming guide](https://nextjs.org/docs/app/guides/streaming), [React Suspense reference](https://react.dev/reference/react/Suspense)).

The coarse-grained version is a file convention: drop a `loading.tsx` next to a `page.tsx`, and the framework wraps the page in a Suspense boundary that shows your fallback instantly on navigation:

```tsx
// app/dashboard/loading.tsx — shown immediately while page.tsx's awaits resolve
export default function Loading() {
  return <DashboardSkeleton />;
}
```

The fine-grained version is explicit `<Suspense>`, and it's where streaming earns its keep — split the page so each slow region suspends *independently*:

```tsx
// app/dashboard/page.tsx
import { Suspense } from "react";

export default function DashboardPage() {
  return (
    <section>
      <DashboardHeader />                              {/* fast — renders in the first chunk */}
      <Suspense fallback={<RevenueSkeleton />}>
        <RevenueChart />                               {/* async server component, slow query */}
      </Suspense>
      <Suspense fallback={<ActivitySkeleton />}>
        <ActivityFeed />                               {/* independent — streams when ready */}
      </Suspense>
    </section>
  );
}
```

Note the inversion: the page itself is no longer `async` — the *awaits moved down* into `<RevenueChart>` and `<ActivityFeed>`, so the header ships in the first byte-flush and each widget streams in when its own data resolves. This composes with everything in Part 4: parallel-start your fetches, then place Suspense boundaries where the *user* would tolerate a skeleton. (Boundary placement is product design, not plumbing: one spinner for the whole page and fifteen independently popping skeletons are both bad; group what belongs together.)

The frontier of the spectrum — which the Next.js 16-era docs build toward with **Cache Components** ([migration guide](https://nextjs.org/docs/app/guides/migrating-to-cache-components)) — is mixing static and dynamic *within one route*: a statically-served shell with dynamic holes streamed into it. You'll see this called partial prerendering in older material; the takeaway at study time is just that the per-route spectrum is becoming a per-*subtree* spectrum, with `'use cache'` (Part 6) as the explicit marker for the static parts.

### Two Orthogonal Dials: Runtime and Region

Rendering mode answers *when*; two segment-config knobs answer *where and on what*. The `runtime` export chooses between the **Node.js runtime** (the default — full Node API surface, every npm package works, your database drivers work) and the **Edge runtime** (a minimal V8/Web-API environment that starts in milliseconds and can run geographically close to users, but supports no Node built-ins, no TCP database connections, and a limited dependency set). The honest guidance has converged over the years: stay on Node unless you have a measured reason not to. Edge's cold-start advantage matters for latency-critical, dependency-light code paths (middleware is the natural fit, and historically ran there by default), but the compatibility tax is real, and a fast runtime in Virginia doesn't help when your database is also in Virginia and your *data* can't be at the edge. Related knobs — `preferredRegion`, `maxDuration` — are deployment-platform agreements about where functions run and how long they may take ([Route Segment Config reference](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config)); they should inform feature design ("this export job can't run in a 30-second function") rather than surprise you during an incident.

One more freshness mechanism rounds out the spectrum: **Draft Mode** ([guide](https://nextjs.org/docs/app/guides/draft-mode)). Content sites want static rendering for visitors *and* live rendering for editors previewing unpublished CMS changes — contradictory demands on the same route. `draftMode()` resolves it with a cookie: a Route Handler (called from your CMS's preview button) enables it, and while the cookie is set, static routes render dynamically for *that user only*, with your data layer fetching draft content. Everyone else keeps getting the cached static page. It's a niche feature until you have editors, at which point it's the difference between a real editorial workflow and "deploy to see your changes."

### When Rendering Fails: error.tsx and Friends

Streaming has a flip side: by the time a deep component throws, the response status and shell may already be on the wire. Error handling therefore also lives in the tree, as boundaries. An `error.tsx` in a segment catches render-time errors from that segment down, **must be a Client Component** (error recovery is interactive), and receives the error plus a `reset` function that re-attempts rendering ([Error Handling docs](https://nextjs.org/docs/app/getting-started/error-handling)):

```tsx
// app/dashboard/error.tsx
"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div role="alert">
      <h2>The dashboard hit a problem.</h2>
      <p>Reference: {error.digest}</p>     {/* server errors are redacted; digest matches server logs */}
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

Because the boundary is segment-local, a crashing dashboard widget degrades the dashboard, not the application — the layout above it keeps standing. (A root-level `global-error.tsx` catches failures in the root layout itself.) Note the `digest`: in production Next.js deliberately strips server error messages before they reach the client — they may contain query text or secrets — and gives you a correlation ID instead. Round out the family with `not-found.tsx` (rendered by `notFound()` and unmatched routes) and, in current versions, `forbidden.tsx`/`unauthorized.tsx` for auth-flavored interruptions. The design principle: **expected failures (validation, missing records, no access) are product states with designed UI; `error.tsx` is for the unexpected.** Don't `throw` for things a form should simply display (Part 7 shows the right channel for those).

If you remember one thing from Part 5: **rendering mode is inferred per route from what the code touches — keep routes as static as their data allows, use ISR to give static pages a freshness contract, and when a route must be dynamic, stream it with Suspense so the slow parts can't hold the fast parts hostage.**

```quiz
Q: In the App Router, how is a route's rendering mode (static vs dynamic) usually determined?
- [ ] You set it globally in next.config
- [x] It's inferred per route from what the code touches — awaiting `cookies()`/`headers()`, reading `searchParams`, or an uncached `fetch` flips the route to dynamic; otherwise it's prerendered static at build
- [ ] Every route is dynamic by default
- [ ] You annotate every component
> Next.js prerenders each route as static at `next build` *unless* rendering touches request-time information (cookies, headers, searchParams, uncached fetch, or `force-dynamic`). This inference is elegant but can bite: a helper reading `cookies()` deep in a utility silently makes a whole route dynamic. The build output table (`○` static, `ƒ` dynamic) is your audit — an unexpected `ƒ` is a regression to investigate.

Q: What does ISR (`export const revalidate = 3600`) give you that pure static and pure dynamic don't?
- [ ] Per-user fresh HTML every request
- [x] CDN economics with bounded staleness — requests serve the static copy instantly, and after the window the next request gets stale-while-revalidate regeneration in the background
- [ ] It disables caching
- [ ] It renders on the client
> ISR keeps the near-zero per-request cost of a static page while attaching a freshness contract: the page may be up to an hour stale, served instantly from cache, and the first request after the window triggers a background regeneration (stale-while-revalidate) so later requests get fresh HTML. On-demand revalidation can purge a specific page immediately when "an hour stale" is unacceptable for a particular edit.

Q: Why split a dynamic page into independent `<Suspense>` boundaries rather than one big `await`?
- [ ] It makes the queries faster
- [x] Without it the whole page is as slow as its slowest query; streaming sends the shell and fast regions immediately and fills slow regions in as they finish, so the slow parts can't hold the fast parts hostage
- [ ] Suspense caches the data
- [ ] It avoids server rendering
> A plain dynamic render blocks the entire page on its slowest data dependency, leaving the user staring at a blank tab. Wrapping each slow region in its own `<Suspense>` lets the server stream HTML in chunks as parts of the tree finish, so the header and fast data appear at once while the slow chart and feed stream in independently. It fixes the *experience* without fixing the query.
```

---

## Part 6 — The Caching Layers (Why Everyone Is Confused)

Next.js caching has a deserved reputation as the hardest part of the framework. The reason is structural: there isn't *a* cache, there are **four**, stacked, with different keys, different lifetimes, different invalidation APIs, and different owners (two live on the server, one is the bundler's view of your data, one lives in the user's browser) — and historically the framework turned them all on *by default*, so people met them for the first time as bugs ("I deployed new data and the page won't update") rather than as features. The defaults changed in Next 15 precisely because of that pain — **`fetch` is no longer cached by default, and GET Route Handlers are no longer cached by default** — so beware: most blog posts and Stack Overflow answers written in the Next 13/14 era describe defaults that are now wrong. Trust the current [caching docs](https://nextjs.org/docs/app/getting-started/caching) over your search results, and trust this part's tables over both your habits and old folklore.

Here is the whole system on one screen. Everything after the table is elaboration:

| Layer | Where | What it stores | Key | Default (Next 15+) | Invalidated by |
|---|---|---|---|---|---|
| **Request memoization** | server, per render | results of identical `fetch`/`cache()` calls | URL + options / fn args | on (it's React, not really a "cache") | end of the render pass |
| **Data Cache** | server, persistent | individual fetch/query results | URL + options, or tags | **off** — opt in | `revalidateTag`/`revalidatePath`, time (`revalidate`), redeploy* |
| **Full Route Cache** | server, persistent | the rendered HTML + RSC payload of **static** routes | route path | on for static routes | revalidation of underlying data, redeploy |
| **Router Cache** | **browser**, in-memory | RSC payloads of visited/prefetched segments | route segments | on (layouts reused; pages not, by default) | `router.refresh()`, Server Action revalidations, cookie-setting actions, session end |

(*The Data Cache survives redeploys on Vercel; self-hosted, it lives in `.next/cache` or your custom cache handler — a Part 10 concern.)

### Layer 1: Request Memoization — Not Really a Cache

Covered in Part 4: within a single render pass, duplicate `fetch` calls and `React.cache()`-wrapped functions execute once. It exists so colocated data access (five components asking for the current user) costs one query. It never persists across requests, never serves stale data, and needs no invalidation story. Mentally file it under "React rendering machinery," not "caching," and it will never confuse you again.

### Layer 2: The Data Cache — Per-Fetch, Persistent, Opt-In

The [Data Cache](https://nextjs.org/docs/app/api-reference/functions/fetch) stores the results of *individual data reads* on the server, across requests and across users. Since Next 15 it is **opt-in per fetch**, and the opt-in is where you declare each read's freshness contract:

```tsx
// Uncached (the default): hits the API on every render that runs
const live = await fetch("https://api.example.com/stock-level");

// Cached indefinitely until explicitly invalidated:
const logo = await fetch("https://cms.example.com/site-config", { cache: "force-cache" });

// Cached with time-based revalidation — "up to 5 minutes stale is fine":
const posts = await fetch("https://cms.example.com/posts", { next: { revalidate: 300 } });

// Cached and *tagged* — invalidate precisely, by domain concept:
const post = await fetch(`https://cms.example.com/posts/${slug}`, {
  next: { tags: ["posts", `post:${slug}`] },
});
```

The cache key is the URL plus options, and **tags** are the feature to actually design around: a tag names a domain entity ("everything derived from post 42"), so invalidation can follow your domain model instead of your URL structure. Database reads don't go through `fetch`, so they don't touch this cache — historically you wrapped them in `unstable_cache`; the current model gives them `'use cache'` (below), which is the better thing to learn.

### Layer 3: The Full Route Cache — Where "Static" Lives

This is Part 5 wearing a different hat: when Next.js statically renders a route (at build, or on demand via ISR), the rendered HTML and RSC payload are stored in the **Full Route Cache** and served to everyone without re-rendering. The "cache key" is just the route path; dynamic routes skip this cache entirely — that's what *being dynamic means*. The two layers interlock, and this interlock explains the classic mystery: *"I set `revalidate: 60` on my fetch — why is my page still stale?"* Usually because the page was static, so requests are served from the Full Route Cache and never even reach your fetch call; the data's freshness window only matters when the *route's* copy is regenerated. The clean mental sentence: **the Data Cache stores ingredients; the Full Route Cache stores the finished dish.** Invalidating an ingredient (by tag, by path, by timer) is what marks the dish for re-cooking.

### Layer 4: The Router Cache — The One in the Browser

The [Router Cache](https://nextjs.org/docs/app/guides/caching#client-side-router-cache) is different in kind: it lives in the *user's browser tab*, storing the RSC payloads of segments they've visited or that `<Link>` has prefetched. It's why back/forward navigation is instant and why layouts don't refetch when you move between sibling pages. It's also the layer behind the other classic mystery — *"I updated the data, the server has the new version, but the user still sees the old page until they hard-refresh."* In Next 14 this bit constantly because page payloads were reused for 30 seconds; **since Next 15, page segments are not reused by default** (layouts still are), so the sharp edge is mostly gone — but you still control it: `router.refresh()` discards the cache and re-renders from the server, and (better) Server Actions that call `revalidatePath`/`revalidateTag` purge it automatically on the client that performed the mutation. That automatic purge is a big part of why Part 7 recommends Server Actions for mutations: the framework can only keep the client's view coherent when it *knows* a write happened.

### Invalidation: revalidatePath, revalidateTag, and Read-Your-Own-Writes

On-demand invalidation is one function call, almost always from inside a Server Action or Route Handler ([Revalidating docs](https://nextjs.org/docs/app/getting-started/revalidating)):

```tsx
// features/posts/actions.ts
"use server";
import { revalidateTag, revalidatePath } from "next/cache";

export async function publishPost(postId: string) {
  await requireEditor();                       // authorize first — Part 8
  await db.update(/* ... */);
  revalidateTag(`post:${postId}`);             // precise: everything derived from this post
  revalidateTag("posts");                      // the listing pages
  // revalidatePath("/blog")                   // the blunter instrument, when tags don't exist yet
}
```

Prefer tags over paths as a default: tags map to domain entities and age well ("invalidate post 42 wherever it appears" — detail page, listing, sitemap, OG image), while path invalidation over-refreshes whole subtrees and requires you to remember every URL a piece of data leaks into. The Next 16-era docs split the semantics further — `revalidateTag` marks data stale for *eventual* refresh, while `updateTag` ([reference](https://nextjs.org/docs/app/api-reference/functions/updateTag)), usable inside Server Actions, expires and refreshes *within the same request* for strict read-your-own-writes flows ("the user saved the form and must see the new value on the very next render"). The distinction to memorize is product-level: background freshness for everyone vs. immediate consistency for the writer.

### The Newer Model: 'use cache', cacheLife, cacheTag

Everything above is the "fetch-centric" model, and its deepest flaw is that it only natively covers `fetch` — your database reads, your expensive computations, and your component subtrees had no first-class cache story. The current docs' answer, part of the **Cache Components** model (opt-in via the `cacheComponents` flag in `next.config.ts`, and the direction of travel for the framework), is the [`'use cache'`](https://nextjs.org/docs/app/api-reference/directives/use-cache) directive — caching as something you *say*, not something that happens to you:

```tsx
// lib/queries.ts
import { cacheLife, cacheTag } from "next/cache";

export async function getPublishedPosts() {
  "use cache";                       // this function's result is cacheable, keyed on its arguments
  cacheLife("hours");                // a named freshness profile instead of a magic number
  cacheTag("posts");                 // invalidate with revalidateTag("posts"), same as before
  return db.query.posts.findMany({ where: eq(posts.published, true) });
}
```

`'use cache'` works on functions, components, and whole route files; [`cacheLife`](https://nextjs.org/docs/app/api-reference/functions/cacheLife) attaches a freshness profile and [`cacheTag`](https://nextjs.org/docs/app/api-reference/functions/cacheTag) attaches invalidation handles. Applied to a *component*, it caches rendered output — which is how the model unifies Part 5's spectrum with this part's data caches:

```tsx
// app/blog/popular-posts.tsx — a cached subtree inside an otherwise dynamic page
export async function PopularPosts() {
  "use cache";
  cacheLife("hours");
  cacheTag("posts");
  const posts = await getPopularPosts();
  return <ol>{posts.map((p) => <li key={p.id}>{p.title}</li>)}</ol>;
}
```

A personalized, dynamically rendered dashboard can now embed this hours-fresh, shared-across-users widget without either side compromising — the static/dynamic split becomes per-subtree, declared in code. The conceptual upgrade across the whole model is that caching becomes **visible in the code that is cached** — a reviewer sees the freshness contract next to the query — instead of being an emergent property of defaults and render modes. When studying, learn both: the fetch-centric model because nearly every deployed App Router app uses it, and `'use cache'` because greenfield Next 16-era code and the official docs increasingly center on it.

### The Layers in Motion: One Publish, Traced End to End

Abstract layer descriptions only stick once you've traced a real event through all four, so trace one. The setup: a blog where `/blog` and `/blog/[slug]` are static (built with `generateStaticParams`, data fetched with `next: { tags: ["posts", "post:<slug>"] }`), and an admin edits post 42 via a Server Action that ends with `revalidateTag("post:42")` and `revalidateTag("posts")`.

1. **Before the edit:** every visitor to `/blog/42` is served from the **Full Route Cache** — no rendering, no data access, CDN-grade economics. Visitors who navigate from the listing get it even faster, from their own **Router Cache** prefetch.
2. **The action runs:** the database write commits, then `revalidateTag` marks every Data Cache entry tagged `post:42` or `posts` stale — which transitively marks the static copies of `/blog/42` and `/blog` (the dishes made from those ingredients) for regeneration.
3. **The editor's browser:** because the revalidation happened inside a Server Action, the framework piggybacks on the response to purge the editor's Router Cache; their redirect to `/blog/42` renders fresh from the server. This is the read-your-own-writes path (and `updateTag` is its strict in-request form).
4. **The next visitor:** their request misses the invalidated Full Route Cache entry, triggering a re-render; the tagged fetches re-execute (Data Cache misses too), the route's static copy is regenerated and re-stored, and every visitor after them is back on the cheap path.
5. **Everyone else mid-flight:** users who already had the old page prefetched may see it until their Router Cache entry expires or they trigger a refresh — client caches can only be purged on clients that talk to the server. This residual window is the part no server-side API can erase; if it matters, your staleness budget just told you the page shouldn't have been static.

If you can narrate that sequence unprompted, you understand Next.js caching better than most people shipping it. The same trace doubles as the **staleness debugging checklist** — when "the page won't update," walk the layers in order: is the route static when you assumed dynamic (`next build` output)? Is a fetch cached with no tag or revalidate (Data Cache)? Did the mutation revalidate the right tag/path (invalidation)? Is it just the browser's copy (does a hard refresh fix it → Router Cache)? Four questions, in that order, diagnose nearly every caching mystery the framework can produce.

However you spell it, the discipline that actually tames this part is not technical: **write the freshness contract down.** For each route or data family: how stale may it be, what user/system action must refresh it, and who sees stale data in the window? A team that can answer those three questions per feature has no caching problems, only caching *decisions* — and the four layers become implementation details of a policy you chose on purpose.

If you remember one thing from Part 6: **four caches — memoization (per render), Data Cache (ingredients), Full Route Cache (the finished dish), Router Cache (the browser's copy) — and since Next 15 the server-side data caches are opt-in. Tag your reads, invalidate by tag inside the mutation, and document staleness budgets like the architecture decisions they are.**

```quiz
Q: Why prefer `revalidateTag("post:42")` over `revalidatePath("/blog")` as the default invalidation strategy?
- [ ] Paths are deprecated
- [x] Tags map to domain entities, so one call invalidates that data wherever it appears (detail page, listing, sitemap, OG image); path invalidation over-refreshes whole subtrees and requires you to remember every URL the data leaks into
- [ ] revalidateTag is faster to type
- [ ] Paths can't be used in Server Actions
> Tagging reads by entity ("post:42") lets a mutation say "invalidate this post everywhere" with one call, and the tags age well as the app grows. Path invalidation is blunter — it refreshes everything under a URL and forces you to enumerate every place a piece of data surfaces. Tags are the entity-centric default; paths are the fallback when no tags exist yet.

Q: "The page won't update after I edited it." What's the ordered checklist the guide gives to diagnose it?
- [ ] Restart the server, clear cookies, redeploy, file a bug
- [x] Is the route static when you assumed dynamic (build output)? Is a fetch cached with no tag/revalidate (Data Cache)? Did the mutation revalidate the right tag/path? Is it just the browser's copy (does a hard refresh fix it → Router Cache)?
- [ ] Check the database, then the CDN, then DNS
- [ ] Disable all four caches permanently
> Walking the four layers in order — Full Route Cache (static vs dynamic), Data Cache (untagged fetch), invalidation (right tag/path in the mutation), Router Cache (does a hard refresh fix it) — pinpoints nearly every caching mystery. A hard refresh fixing it implicates the client-side Router Cache, which no server API can purge on clients that haven't talked to the server — the residual staleness window your budget should account for.

Q: What does the newer `'use cache'` directive (with `cacheLife`/`cacheTag`) change conceptually about caching?
- [ ] It removes all caching
- [x] Caching becomes something you *declare in the code that is cached* — visible next to the query/component with its freshness contract — rather than an emergent property of defaults and render modes; it also covers DB reads and component subtrees, not just `fetch`
- [ ] It only works on fetch calls
- [ ] It caches everything forever
> The fetch-centric model only natively covered `fetch`, leaving database reads and component subtrees without a first-class cache story, and caching behavior was an emergent property of defaults. `'use cache'` makes caching explicit: applied to a function, component, or route, it declares the result cacheable with a named `cacheLife` profile and `cacheTag` handles right there in the code — so a reviewer sees the freshness contract, and a dynamic page can embed a shared, hours-fresh cached subtree.
```

---

## Part 7 — Mutations: Server Actions and Route Handlers

Parts 4–6 were about reads. Writes get their own machinery, and it's one of the App Router's genuinely novel contributions: **Server Actions** — server-side functions that client code can invoke *as if they were local function calls*, with the framework generating the HTTP endpoint, the serialization, and the cache coordination for you. (Terminology, since you'll read both the React and Next docs: React calls the general mechanism **Server Functions** ([reference](https://react.dev/reference/rsc/server-functions)); a Server Function used as an action — in a form, a transition — is a Server *Action*. Same feature, two lenses.)

### The Shape of a Server Action

The `'use server'` directive marks the door (recall Part 3: this directive marks *callable server functions*, never components). File-level is the common form — every export becomes a Server Function:

```tsx
// features/posts/actions.ts
"use server";

import { z } from "zod";
import { redirect } from "next/navigation";
import { revalidateTag } from "next/cache";
import { requireUser } from "@/lib/auth";

const CreatePost = z.object({
  title: z.string().min(3).max(120),
  body: z.string().min(1),
});

export async function createPost(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const user = await requireUser();                          // 1. authorize — every action, every time

  const parsed = CreatePost.safeParse({                      // 2. validate — input is untrusted
    title: formData.get("title"),
    body: formData.get("body"),
  });
  if (!parsed.success) {
    return { errors: parsed.error.flatten().fieldErrors };   // expected failure → data, not a throw
  }

  const post = await db.insert(posts)                        // 3. write
    .values({ ...parsed.data, authorId: user.id })
    .returning();

  revalidateTag("posts");                                    // 4. invalidate what the write changed
  redirect(`/posts/${post[0].slug}`);                        // 5. post/redirect/get, framework-native
}
```

Those five steps — authorize, validate, write, revalidate, redirect — are *the* canonical mutation shape; nearly every action you ever write is a variation. Steps 1 and 2 are non-negotiable for a reason worth stating in bold: **a Server Action is a public, unauthenticated-by-default HTTP endpoint.** The call site *looks* like a local function call, but the compiler turns it into a POST route with a generated ID, and anyone with a network tab can invoke it with arbitrary arguments. "The button is only shown to admins" is not authorization. Validate every argument, check permissions inside the action, and treat `formData` exactly as you'd treat a raw request body ([Data Security guide](https://nextjs.org/docs/app/guides/data-security) — read it in full; more in Part 8).

### Forms: The Default Mutation Surface

The idiomatic way to invoke an action is the platform's own mutation primitive — a form ([Updating Data docs](https://nextjs.org/docs/app/getting-started/updating-data), [React `<form>` reference](https://react.dev/reference/react-dom/components/form)):

```tsx
// features/posts/new-post-form.tsx
"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { createPost } from "./actions";

function SubmitButton() {
  const { pending } = useFormStatus();        // reads the status of the parent <form>
  return <button disabled={pending}>{pending ? "Publishing…" : "Publish"}</button>;
}

export function NewPostForm() {
  const [state, formAction] = useActionState(createPost, { errors: {} });
  return (
    <form action={formAction}>
      <input name="title" required minLength={3} />
      {state.errors?.title && <p role="alert">{state.errors.title}</p>}
      <textarea name="body" required />
      {state.errors?.body && <p role="alert">{state.errors.body}</p>}
      <SubmitButton />
    </form>
  );
}
```

Read what's *absent*: no `onSubmit` handler, no `e.preventDefault()`, no `fetch("/api/posts", ...)`, no manually managed `isSubmitting`/`errors` state machine, no JSON contract to keep in sync between client and server. [`useActionState`](https://react.dev/reference/react/useActionState) threads the action's return value (our validation errors) back into the UI — expected failures stay in the normal data flow, exactly as Part 5 prescribed, instead of detonating an error boundary. [`useFormStatus`](https://react.dev/reference/react-dom/hooks/useFormStatus) gives any child of the form its pending state, which is correctness, not garnish: a disabled pending button is your first line of defense against double-submission. And because this is a real `<form>` with a real `action`, the basic flow works **before hydration finishes** — submit on a slow connection and the browser's native form submission carries it; that progressive enhancement is something `onClick`-plus-`fetch` can never give you. One form can even host multiple writes — a secondary `<button formAction={saveDraft}>` alongside the primary submit — which covers publish/save-draft and similar flows without a second form.

Two refinements complete the toolkit. For latency-sensitive interactions, [`useOptimistic`](https://react.dev/reference/react/useOptimistic) renders the *expected* result immediately and reconciles when the server confirms:

```tsx
// features/comments/comment-section.tsx
"use client";
import { useOptimistic } from "react";
import { addComment } from "./actions";

export function CommentSection({ comments }: { comments: Comment[] }) {
  const [optimisticComments, addOptimistic] = useOptimistic(
    comments,                                            // server truth, via props
    (current, newComment: Comment) => [...current, { ...newComment, pending: true }],
  );

  async function formAction(formData: FormData) {
    addOptimistic({ id: crypto.randomUUID(), body: String(formData.get("body")) });
    await addComment(formData);                          // action revalidates → real list replaces optimistic one
  }

  return (
    <>
      <ul>
        {optimisticComments.map((c) => (
          <li key={c.id} style={{ opacity: c.pending ? 0.5 : 1 }}>{c.body}</li>
        ))}
      </ul>
      <form action={formAction}>
        <input name="body" required />
        <button>Comment</button>
      </form>
    </>
  );
}
```

The comment appears instantly (dimmed, honestly marked pending); when the action completes and revalidation delivers fresh server data through props, the optimistic state is discarded in favor of truth — and if the action *throws*, React rolls the optimistic update back automatically. The contract to respect: only optimize optimistically where you can define what rollback looks like to the user. For actions triggered *outside* forms (a delete icon, a toggle), call the action inside [`startTransition`](https://react.dev/reference/react/startTransition) so React tracks pending state. Finally, make writes **idempotent** where money or invitations are involved — actions can be retried (by the user, by the network), and "the server is the only one who decides whether this already happened" is a lesson production teaches expensively.

Actions also have full server-side request context: they can `await cookies()` and `await headers()` — and unlike Server Components, an action may *mutate* cookies (`(await cookies()).set("theme", "dark")`), which is how login/logout flows set and clear sessions. Setting a cookie from an action also invalidates the client's Router Cache, on the correct theory that a changed cookie probably changes what pages look like. The pattern that ties the whole part together is post/redirect/get, framework-native: the action writes, revalidates, sets whatever cookies it must, and `redirect()`s — so a browser refresh re-renders the destination instead of re-submitting the mutation, exactly as it did in 2005, except with types.

### Route Handlers: HTTP When You Actually Need HTTP

Server Actions deliberately hide HTTP. Sometimes HTTP is the point — a Stripe webhook, a mobile client, an OAuth callback, a file download. That's what **Route Handlers** are for ([docs](https://nextjs.org/docs/app/api-reference/file-conventions/route)): a `route.ts` file exporting functions named after HTTP methods, built on the standard `Request`/`Response` Web APIs:

```ts
// app/api/webhooks/stripe/route.ts
import { revalidateTag } from "next/cache";
import { verifyStripeSignature } from "@/lib/stripe";

export async function POST(request: Request) {
  const payload = await request.text();
  const event = verifyStripeSignature(payload, request.headers.get("stripe-signature"));
  if (!event) return new Response("invalid signature", { status: 400 });

  if (event.type === "product.updated") {
    await syncProduct(event.data.object.id);          // idempotent by design — webhooks retry
    revalidateTag(`product:${event.data.object.id}`);
  }
  return Response.json({ received: true });
}
```

A `route.ts` claims its segment entirely (it can't share a folder with a `page.tsx`), and — Next 15 default change again — **GET handlers are uncached by default**; a handler that serves genuinely static data can opt back in:

```ts
// app/api/products/route.ts — a read endpoint for external/client consumers
export const dynamic = "force-static";       // cacheable: regenerated when its data revalidates
export const revalidate = 300;               // ...or at most every 5 minutes

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const category = searchParams.get("category") ?? undefined;
  const products = await getProducts({ category });        // same data layer as the components
  return Response.json(products, {
    headers: { "Cache-Control": "public, max-age=60" },    // and you control HTTP caching directly
  });
}
```

(Note the trap lurking in that example: reading `request.url`'s search params makes the handler request-dependent, so `force-static` would ignore them — static GET handlers can't vary by query string. Choose one: a static handler with no request-derived behavior, or a dynamic one that reads the request. The same static-vs-dynamic inference from Part 5 governs handlers too.) Keep handlers thin either way: signature verification, parsing, status codes — the actual business logic belongs in the same data layer your components and actions call, so it stays testable outside the HTTP wrapper.

When to use which is one of the cleaner decisions in the framework:

| | **Server Action** | **Route Handler** |
|---|---|---|
| Caller | your own React components | anything that speaks HTTP |
| Protocol | hidden (generated POST, RSC serialization) | explicit `Request`/`Response`, any method |
| Cache coordination | automatic (`revalidate*` also purges the caller's Router Cache) | manual — you return data, caller updates itself |
| Progressive enhancement | yes, via `<form action>` | no |
| Type safety | end-to-end, free (it's a function call) | you maintain the contract |
| Concurrency | submissions queue sequentially per client | normal parallel HTTP |
| Right for | forms and mutations from your UI | webhooks, public APIs, mobile/third-party clients, OAuth callbacks, files/streams |

The first row decides 90% of cases: **if the caller is your own UI, use an action; if the caller is the outside world, use a handler.** The most common architecture smell from the SPA era is building a REST layer in `app/api/` and `fetch`ing it from your own components — you're hand-rolling, without types and without cache coordination, what actions do natively. (The notable exception: GET-shaped *client-side* data needs — polling, infinite scroll, search-as-you-type — where a GET handler plus a client fetching library is legitimately the right tool; actions are POSTs and queue sequentially, which makes them wrong for reads.)

If you remember one thing from Part 7: **mutations are Server Actions invoked by real forms — authorize, validate, write, revalidate, redirect — and every action is a public endpoint no matter how local it looks. Route Handlers are for callers that aren't your own UI.**

```quiz
Q: A Server Action's call site looks like a local function call. Why must you still authorize and validate inside it?
- [ ] To improve performance
- [x] The compiler turns it into a public POST endpoint with a generated ID, so anyone with a network tab can invoke it with arbitrary arguments — "the button is only shown to admins" is not authorization
- [ ] Because actions run on the client
- [ ] Validation is optional for actions
> A Server Action compiles to a real, unauthenticated-by-default HTTP endpoint; the local-function appearance is an abstraction over a POST route. So you must check permissions and validate every argument inside the action, treating `formData` like a raw request body. UI-level gating (hiding the button) controls nothing — the canonical shape is authorize, validate, write, revalidate, redirect, with the first two non-negotiable.

Q: What does invoking a Server Action through a real `<form action={...}>` give you that an `onClick`-plus-`fetch` cannot?
- [ ] Faster network requests
- [x] Progressive enhancement — the basic submit works before hydration via native browser form submission — plus no manual JSON contract, and `useFormStatus` pending state for double-submit protection
- [ ] Automatic authorization
- [ ] Client-side caching
> Because it's a genuine form with a real action, submission works even before JavaScript hydrates (the browser carries it natively), which `onClick`+`fetch` can never do. You also drop the hand-managed `isSubmitting`/errors state machine and the client/server JSON contract: `useActionState` threads return values back as data, and `useFormStatus` exposes pending state to disable the button. Expected failures stay in the data flow instead of detonating an error boundary.

Q: When should you build a Route Handler instead of a Server Action?
- [ ] Always — actions are deprecated
- [x] When the caller isn't your own UI — webhooks, public/mobile/third-party clients, OAuth callbacks, file downloads — or for client-side GET-shaped reads like polling/infinite-scroll
- [ ] For all form submissions
- [ ] Only for database writes
> The first-row rule decides most cases: own UI → action; outside world → handler. Building a REST layer in `app/api/` just to fetch it from your own components is the SPA-era smell — you're hand-rolling, without types or cache coordination, what actions do natively. The legitimate exception is GET-shaped client reads (search-as-you-type, infinite scroll), since actions are POSTs that queue sequentially and are wrong for reads.
```

---

## Part 8 — Middleware, Security Boundaries, and Auth

Next.js applications have a security property that purely client-side apps don't: there are *real* boundaries — code that provably never leaves the server — but they sit close enough to client code that one careless import erases them. This part is about drawing the boundaries deliberately. The [Data Security guide](https://nextjs.org/docs/app/guides/data-security) and [Authentication guide](https://nextjs.org/docs/app/guides/authentication) are the two documents to read end-to-end; the [Auth guide in this repo](AUTH_STUDY_GUIDE.md) covers the protocol-level material (sessions, JWTs, OAuth) that Next.js intentionally doesn't.

### The Environment Variable Boundary

The first boundary is configuration. Next.js loads `.env*` files and exposes variables to server code as usual — but anything prefixed **`NEXT_PUBLIC_`** is *inlined into the client JavaScript bundle at build time* ([Environment Variables guide](https://nextjs.org/docs/app/guides/environment-variables)). Treat that prefix as what it is — a declaration that a value is world-readable — not a naming convention. `DATABASE_URL` without the prefix is genuinely server-only; `NEXT_PUBLIC_ANALYTICS_ID` is shipped to every visitor, forever (build-time inlining means rotating it requires a rebuild). The audit is worth doing on every project: for each variable, is it server-only, deliberately public, or — the common third category — something that shouldn't exist at all.

Code needs the same fencing as config. The [`server-only`](https://nextjs.org/docs/app/getting-started/server-and-client-components#preventing-environment-poisoning) package turns "this module must never reach the browser" from a hope into a build error:

```ts
// lib/db.ts
import "server-only";          // importing this file from any client module now fails the build

import postgres from "postgres";
export const db = postgres(process.env.DATABASE_URL!);
```

Put that import line at the top of every module that touches secrets, the database, or privileged SDKs. It costs nothing and converts an entire vulnerability class — "a refactor moved an import and now the bundle contains the admin client" — into a compile failure. For defense in depth on *data* (rather than modules), React's taint APIs (`experimental_taintObjectReference`, `taintUniqueValue`) make specific objects un-passable across the boundary, but the structural fix matters more: **don't pass raw database entities to Client Components at all.** Map them to DTOs that contain exactly what the UI needs — the serialization boundary (Part 3) will faithfully ship every field you give it, including `passwordHash`, and "the UI doesn't *display* it" is not the same as "the response doesn't *contain* it."

### Middleware: The Request-Time Checkpoint

**Middleware** runs before a request reaches any route — one function, at the project root, filtering everything ([Middleware docs](https://nextjs.org/docs/app/api-reference/file-conventions/middleware)). Naming note for the Next.js 16 era: the original file convention is `middleware.ts`, and **Next 16 renames the concept to Proxy (`proxy.ts`)** ([Proxy docs](https://nextjs.org/docs/app/getting-started/proxy)) — you will see both names in the wild for years; the semantics are what matters:

```ts
// middleware.ts (proxy.ts in Next 16)
import { NextResponse, type NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const session = request.cookies.get("session")?.value;

  if (!session && request.nextUrl.pathname.startsWith("/dashboard")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("from", request.nextUrl.pathname);   // return them after login
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*"],   // run only where needed
};
```

Middleware is for **cheap, request-shaped decisions**: redirects and rewrites that depend on request data, A/B bucketing via cookie, locale detection, header manipulation, and *optimistic* auth checks like the one above. Note what that example does and doesn't do: it checks that a session cookie **exists** and bounces obvious anonymous traffic — a UX optimization — but it does not verify the session against a store or make authorization decisions. The docs are blunt about this and so is this guide: **middleware is not your security layer.** It runs on every matched request (so it must be fast — no database calls), it historically runs on a constrained edge runtime, and rewrites/direct route handler invocations can bypass it. (Static redirects that don't need request data belong in [`next.config` redirects](https://nextjs.org/docs/app/api-reference/config/next-config-js/redirects), a simpler tool that ages better.)

### Where Authorization Actually Lives

If middleware is only optimistic, where's the real check? The official guidance — and the architecture this guide has been building toward since Part 4 — is: **as close to the data as possible, in the Data Access Layer.** Every function that reads or writes privileged data establishes the session and checks permissions *itself*:

```ts
// lib/queries.ts
import "server-only";
import { cache } from "react";
import { verifySession } from "@/lib/auth";

export const getInvoice = cache(async (invoiceId: string) => {
  const session = await verifySession();                        // who is asking?
  const invoice = await db.query.invoices.findFirst({ where: eq(invoices.id, invoiceId) });
  if (!invoice || invoice.orgId !== session.orgId) return null; // may they see THIS row?
  return toInvoiceDTO(invoice);                                  // and only the fields the UI needs
});
```

The `verifySession` it leans on is itself small — and shows the server-side request-context APIs ([`cookies()`](https://nextjs.org/docs/app/api-reference/functions/cookies)) in their natural habitat:

```ts
// lib/auth.ts
import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { decryptSessionToken } from "./session-crypto";   // your auth library's job, really

export const verifySession = cache(async () => {
  const token = (await cookies()).get("session")?.value;
  const session = token ? await decryptSessionToken(token) : null;
  if (!session) redirect("/login");                       // short-circuits rendering, anywhere it's called
  return session;                                         // { userId, orgId, role }
});

export async function requireRole(role: string) {
  const session = await verifySession();
  if (session.role !== role) forbidden();                 // renders the nearest forbidden.tsx
  return session;
}
```

Two details carry weight. The `cache()` wrapper means twenty authorization checks per request decrypt the cookie once (Part 4's memoization, doing security work). And `await cookies()` is one of the dynamic APIs from Part 5 — *any route whose render path verifies a session is dynamically rendered*, which is correct and worth being conscious of: personalized pages can't be static, and if part of a page *could* be static, that's an argument for keeping the session check out of that subtree (or reaching for the Cache Components model, which makes exactly this split explicit).

Now the security posture doesn't depend on every page, layout, action, and route handler remembering to check — they all go through `getInvoice`, and `getInvoice` doesn't trust its callers. This layering gives each tier its proper job: **middleware** redirects anonymous users (experience), **layouts/pages** decide what UI to show (`forbidden()`/`unauthorized()` for designed denial states — experience again), and the **DAL** enforces who may read and write what (security, per-row, every time). The layered model matters extra in this framework because of Part 7's fact — Server Actions are public endpoints — and because layouts don't re-render on every navigation, so a check that lives *only* in a layout is a check that sometimes doesn't run. For the session machinery itself (cookie flags, rotation, CSRF posture, OAuth), use a maintained library — Auth.js, Better Auth, Clerk, or your IdP's SDK — and spend your innovation budget elsewhere; the concepts are in the [Auth guide](AUTH_STUDY_GUIDE.md).

Two closing hardening notes. First, Server Actions get some framework-level protections — closures captured by an action are encrypted, and actions have unguessable build-specific IDs and origin checks — but the docs themselves tell you not to lean on this: it's belt-and-suspenders, not authorization. Second, when you're ready for it, Next.js supports nonce-based **Content Security Policy** ([CSP guide](https://nextjs.org/docs/app/guides/content-security-policy)) via middleware-generated nonces; it constrains your script-loading and static-rendering choices, which is exactly why the guide recommends learning it before launch week rather than after the pen test.

If you remember one thing from Part 8: **`NEXT_PUBLIC_` and `'use client'` are declarations that code and config are world-readable; fence the rest with `server-only`, and put real authorization in the data access layer — middleware redirects, the DAL decides.**

---

## Part 9 — Performance, Metadata, and Client-Side Discipline

Most of this guide has *been* a performance guide in disguise — Server Components exist to shrink bundles, streaming exists to improve time-to-first-paint, the caches exist to avoid recomputation. This part covers the rest: the built-in asset optimizers that handle the classic Core Web Vitals killers, the metadata system that makes pages findable and shareable, and the discipline of keeping the client side small in the first place. The framing to carry in: **bundle ownership is product ownership.** If a route is slow, someone chose (or failed to notice) the boundary or the library that made it slow, and the tools in this part are how you see and reverse those choices.

### Images, Fonts, and Scripts: The Built-In Optimizers

The largest Core Web Vitals problems on most sites are not React problems — they're a 2 MB hero image, a font that swaps in late and shoves the layout around, and a third-party script that blocks the main thread. Next.js ships a dedicated component for each.

[`next/image`](https://nextjs.org/docs/app/api-reference/components/image) replaces `<img>` and fixes the image problems by construction: it requires (or infers) dimensions so the browser reserves space — eliminating layout shift (CLS) — serves modern formats (WebP/AVIF) resized to the actual rendered size via an optimization endpoint, and lazy-loads everything below the fold by default:

```tsx
import Image from "next/image";
import hero from "@/public/hero.jpg";        // static import: dimensions + blur placeholder inferred

export function Hero() {
  return <Image src={hero} alt="Dashboard overview" priority placeholder="blur" />;
}
// For remote/CMS images: provide width/height (or fill + sizes), and allowlist
// the host in next.config.ts under images.remotePatterns.
```

The one prop to actually study is `priority`: the image that will be your Largest Contentful Paint element (the hero) should be eagerly loaded and preloaded; everything else should keep the lazy default. [`next/font`](https://nextjs.org/docs/app/api-reference/components/font) solves the font problem by self-hosting at build time — Google Fonts are downloaded *into your build* (no request to Google at runtime, which is also a privacy/GDPR win), served from your origin with proper caching, with `size-adjust` fallback metrics generated automatically to kill font-swap layout shift:

```tsx
// app/layout.tsx
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body>{children}</body>
    </html>
  );
}
```

Third-party scripts go through [`next/script`](https://nextjs.org/docs/app/api-reference/components/script), whose `strategy` prop (`beforeInteractive`, `afterInteractive`, `lazyOnload`) is a polite way of asking "does this tag manager really need to beat my content to the main thread?" The honest default for analytics and widgets is `afterInteractive` or later.

### Metadata: SEO as Part of the Route Contract

The App Router treats metadata as data the route exports, not strings smuggled into a `<Head>` component. Static pages export a `metadata` object; dynamic pages export [`generateMetadata`](https://nextjs.org/docs/app/api-reference/functions/generate-metadata), which can await the same data the page uses (request memoization from Part 4 makes the double-read free):

```tsx
// app/posts/[slug]/page.tsx
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const post = await getPost((await params).slug);     // memoized — the page's own call is reused
  return {
    title: post.title,
    description: post.summary,
    alternates: { canonical: `/posts/${post.slug}` },
    openGraph: { title: post.title, images: [`/posts/${post.slug}/og.png`] },
  };
}
```

Metadata composes down the tree like layouts do — the root layout sets the site-wide template (`title: { template: "%s · Acme" }`), segments override what they own. The file conventions extend the same idea to the rest of the crawl surface ([Metadata Files reference](https://nextjs.org/docs/app/api-reference/file-conventions/metadata)): `app/sitemap.ts` and `app/robots.ts` are typed functions, `app/icon.png` becomes your favicon set, and `opengraph-image.tsx` generates per-route social cards as code. The sitemap example makes the design's point:

```ts
// app/sitemap.ts — generates /sitemap.xml from the database; it cannot drift from reality
import type { MetadataRoute } from "next";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPosts();
  return [
    { url: "https://acme.com", changeFrequency: "weekly", priority: 1 },
    ...posts.map((post) => ({
      url: `https://acme.com/posts/${post.slug}`,
      lastModified: post.updatedAt,
    })),
  ];
}
```

A hand-maintained `sitemap.xml` is stale the day after launch; this one is a function of the same data the pages render from. For content and commerce, add [JSON-LD structured data](https://nextjs.org/docs/app/guides/json-ld) on entity pages — a `<script type="application/ld+json">` rendered by the Server Component from the same entity, one more derivation of one source of truth. None of this is glamorous; all of it is the difference between a launched product and a discoverable one, and the API design makes it cheap enough to do at build-the-feature time instead of launch week.

### Keeping the Client Small

Part 3 gave the architectural rule — push `'use client'` to the leaves — but real apps also have legitimately heavy *client* code: a rich-text editor, a chart library, a map. The tool there is lazy loading via [`next/dynamic`](https://nextjs.org/docs/app/guides/lazy-loading), which code-splits a component out of the route's initial bundle and loads it on demand:

```tsx
"use client";
import dynamic from "next/dynamic";

const RichTextEditor = dynamic(() => import("./rich-text-editor"), {
  ssr: false,                                // editor needs window — skip server rendering entirely
  loading: () => <EditorSkeleton />,
});
```

`ssr: false` is also the standard escape hatch for browser-only libraries that crash during server rendering. But treat `next/dynamic` as the second resort — the first is asking whether the boundary is drawn right: a chart *library* needs the client, but the data aggregation feeding it doesn't, and shipping `{ labels, values }` from a Server Component instead of raw rows plus a client-side transform is often the bigger win. Audit reality with [`@next/bundle-analyzer`](https://nextjs.org/docs/app/guides/package-bundling) periodically; the most common finding is a "utility" module that imports one icon from a giant barrel file and pays for the barrel.

The remaining client discipline is about state location, and it compresses to a hierarchy you apply mechanically: **server data stays on the server** (don't mirror fetched truth into a client store out of SPA habit — the Server Component re-renders with fresh data on revalidation; a copied version goes stale); **view-describing state goes in the URL** (Part 2); **ephemeral UI state** (open dialogs, input drafts, hover) is plain `useState`; **ambient client concerns** (theme, locale) are context via the provider pattern from Part 3. Most "do I need Redux/Zustand?" questions in App Router apps dissolve under that hierarchy — what's left genuinely client-global is usually small.

For responsiveness *within* the client, the React concurrent APIs pull real weight in Next.js apps, because URL-driven state means every filter keystroke is potentially a router navigation. [`useTransition`](https://react.dev/reference/react/useTransition) keeps the input fluid while the navigation renders:

```tsx
// app/search/search-box.tsx
"use client";
import { useState, useTransition } from "react";
import { useRouter, usePathname } from "next/navigation";

export function SearchBox({ initialQuery }: { initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery);    // the input itself stays instant
  const [isPending, startTransition] = useTransition();
  const router = useRouter();
  const pathname = usePathname();

  function onChange(value: string) {
    setQuery(value);                                   // urgent: the keystroke
    startTransition(() => {                            // non-urgent: re-rendering the results
      router.push(`${pathname}?q=${encodeURIComponent(value)}`);
    });
  }

  return (
    <div data-pending={isPending ? "" : undefined}>    {/* dim results via CSS while stale */}
      <input value={query} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
```

The split is the point: the keystroke updates urgently, the navigation (and the Server Component re-render it triggers) proceeds as an interruptible transition, and `isPending` lets you dim the now-stale results instead of blocking the input. Its sibling [`useDeferredValue`](https://react.dev/reference/react/useDeferredValue) does the same job when the expensive thing is a client-side computation (a thousand-row filter pane) rather than a navigation — let the expensive UI lag the fast input. In practice, add a debounce on top for server-bound searches; transitions make the UI honest, debouncing makes the request volume polite.

Close the loop with measurement: [`useReportWebVitals`](https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals) streams real-user LCP/CLS/INP (with attribution, so you know *which* element and route) to your analytics, because performance you don't measure regresses silently.

### Accessibility Is a Routing Concern Here

One genuinely Next-specific accessibility point deserves more than a passing mention: **routed UIs break the assumptions assistive technology was built on.** A full page load resets focus and announces a new document; a client-side transition does neither unless someone makes it. Next.js handles part of this (route announcer, focus behavior on navigation), but the patterns *this guide taught you* create the cases you must handle yourself: an intercepting-route modal (Part 2) must trap focus while open and return it to the triggering thumbnail on close — the native `<dialog>` element does most of that for free, which is a reason to prefer it; streaming (Part 5) means content appears after the page "loaded," so dynamic regions that matter should be announced (`aria-live`); and Part 7's validation errors need `role="alert"` (as the form example showed) plus `aria-describedby` linking each error to its field, or screen-reader users get silence where sighted users get red text. The deeper point is that the framework has been nudging you toward the accessible substrate all along — real `<form>`s with real submission semantics, real `<button>`s, real links via `<Link>`, states modeled as routes instead of floating divs. Semantic HTML first; the [WAI-ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/) only for the genuinely custom widgets; and a keyboard-only pass over every form, modal, and dynamically updated list before calling a feature done.

If you remember one thing from Part 9: **use the framework's optimizers (`next/image`, `next/font`, metadata-as-code) instead of hand-rolling them, keep heavy code server-side or lazily loaded, and locate state by what it describes — server truth on the server, view state in the URL, ephemera in `useState`.**

---

## Part 10 — Deployment, Operations, and Honest Trade-offs

A Next.js app is not a folder of static files; `next build` produces a *server* — one that renders dynamic routes, streams responses, regenerates ISR pages, runs middleware, and optimizes images. Deployment is therefore a real architectural topic, and it's also where the framework's most legitimate criticism lives, so this part is deliberately candid.

### Vercel and the Honest Trade-off

[Vercel](https://vercel.com/docs) is the company that builds Next.js, and deploying there is genuinely the path of least resistance: `git push`, and the platform decomposes your build — static assets to CDN, dynamic routes to serverless functions, middleware to edge workers, ISR and the Data Cache to managed infrastructure — with preview deployments on every pull request as the workflow's killer feature ([Deploying docs](https://nextjs.org/docs/app/getting-started/deploying)). Every feature in this guide works there with zero configuration, and previews alone change how teams review UI work.

The honest other side of the ledger: **costs scale with usage in ways that surprise teams** (image optimization, function invocations, and bandwidth each meter separately — a traffic spike is a billing event), the platform's serverless decomposition means there are no long-lived processes (no WebSockets, no in-memory anything, cold starts exist), and there's a structural concern worth naming plainly: the framework's flagship features have historically worked *best* on the vendor's platform, and self-hosters have at times been second-class citizens. That gap has narrowed materially — Next 15+ improved self-hosted ISR, cache control, and documentation, and the [adapters API](https://nextjs.org/docs/app/api-reference/adapters) formalizes other platforms — but the gravitational pull is real, and pretending otherwise would make this a worse guide.

| | **Vercel** | **Self-hosted** |
|---|---|---|
| Setup effort | `git push` | container, proxy, CDN, cache handler — real work |
| Preview deploys per PR | built in | you build it (doable, rarely as polished) |
| ISR / Data Cache | managed, multi-region, survives deploys | yours to wire (shared cache handler for >1 replica) |
| Image optimization | managed (metered) | your CPU, or an image CDN you integrate |
| Long-lived processes / WebSockets | no | yes — it's your server |
| Cost shape | low floor, usage-scaled, spiky | infra + ops time; flat and predictable |
| Lock-in pressure | real, though adapters are narrowing it | none beyond Next.js itself |

The reasonable position: Vercel is an excellent default for small teams and content/commerce sites whose traffic is mostly cacheable; do the math *before* the bill does it for you, and know what self-hosting asks of you (next section) so it's a choice rather than a fantasy. Teams already running services — a Kubernetes cluster, a fleet of containers, an ops culture — give up less by self-hosting than the marketing implies; teams with no ops muscle give up more.

### Self-Hosting: What You're Signing Up For

Self-hosting is fully supported and well documented ([Self-Hosting guide](https://nextjs.org/docs/app/guides/self-hosting)). The standard container shape uses the `standalone` output, which traces the server's actual dependencies into a minimal bundle:

```ts
// next.config.ts
const nextConfig = { output: "standalone" };
export default nextConfig;
```

```dockerfile
# Dockerfile (abridged — see the official with-docker example for the full multi-stage version)
FROM node:22-alpine AS builder
WORKDIR /app
COPY . .
RUN npm ci && npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]                  # the standalone server — no `next start` needed
```

What you now own that Vercel was doing for you: a **reverse proxy** (see the [Caddy guide](CADDY_STUDY_GUIDE.md)) terminating TLS — configured *not* to buffer responses, or Part 5's streaming silently becomes "wait for the whole page"; a **CDN** in front of static assets and cacheable routes if you want static-route economics; **image optimization** compute (`next/image` resizing runs on your server now — for real traffic, consider a dedicated image CDN via a custom `loader`); and — the one that bites multi-instance deployments — **the ISR/Data Cache**, which defaults to in-memory-plus-disk per instance. Three replicas behind a load balancer means three independent caches: a `revalidateTag` lands on whichever instance served the action, and the other two keep serving the stale page. The fix is a shared cache backend:

```ts
// next.config.ts
const nextConfig = {
  output: "standalone",
  cacheHandler: require.resolve("./cache-handler.js"),   // e.g. a Redis-backed implementation
  cacheMaxMemorySize: 0,                                 // disable per-instance in-memory caching
};
export default nextConfig;
```

The handler itself is a small class implementing `get`/`set`/`revalidateTag` against Redis or similar — community implementations exist, and the [self-hosting docs](https://nextjs.org/docs/app/guides/self-hosting#configuring-caching) cover the contract. None of this is exotic for a team that already runs services — it's a Node process behind a proxy ([Docker guide](DOCKER_STUDY_GUIDE.md) territory) — but it is *work*, and the cache-handler item in particular is the difference between "it deploys" and "revalidation actually works."

The degenerate deployment case is worth knowing: [static export](https://nextjs.org/docs/app/guides/static-exports) (`output: "export"`) renders the whole app to plain HTML/CSS/JS servable from any static host — at the cost of everything request-shaped: no Server Actions, no dynamic rendering, no ISR, no middleware, no image optimization. If a project fits comfortably inside those constraints, that's also a signal worth hearing (Part 1: maybe Astro, or maybe that's fine and you wanted Next's authoring model — both are defensible, *chosen consciously*).

### CI, Testing, and Observability

The pipeline (see the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md)) earns its keep with three Next-specific notes. First, `next build` is itself a quality gate — it fails on TypeScript and ESLint errors and runs `generateStaticParams`, so "the build passed" carries real information; keep `tsc --noEmit` and lint as separate fast jobs anyway for better failure attribution. Second, cache `.next/cache` between CI runs ([CI Build Caching guide](https://nextjs.org/docs/app/guides/ci-build-caching)) — the compiler cache makes warm builds dramatically cheaper, and the cache key should include both your lockfile and your source:

```yaml
# .github/workflows/ci.yml (excerpt)
- uses: actions/cache@v4
  with:
    path: .next/cache
    key: nextjs-${{ hashFiles('package-lock.json') }}-${{ hashFiles('**/*.ts', '**/*.tsx') }}
    restore-keys: nextjs-${{ hashFiles('package-lock.json') }}-
- run: npm ci
- run: npx tsc --noEmit && npm run lint
- run: npm run build          # the real gate: types, lint, generateStaticParams all run here
```

Third, know what's baked at build time (`NEXT_PUBLIC_*`, static pages) versus read at runtime — "works in staging, broken in prod" is very often a build-time/runtime config confusion, and it implies something subtle: if staging and production are *different builds*, their static pages were rendered from whatever the data looked like at each build. Build once, promote the artifact, and keep environment differences in runtime config.

Testing strategy follows the architecture (general background in the [Testing guide](TESTING_STUDY_GUIDE.md)): unit-test the pure core aggressively — validation schemas, authorization rules, DTO mappers, the data layer — with [Vitest](https://nextjs.org/docs/app/guides/testing/vitest), and component-test *synchronous* components normally. The framework-specific caveat the docs state outright: **async Server Components don't unit-test well yet** — the RSC machinery isn't meaningfully simulable in jsdom — so don't force that layer; cover routing, streaming, form actions, and revalidation flows with [Playwright](https://nextjs.org/docs/app/guides/testing/playwright) against a real `next start`, and make sure the E2E suite covers the unhappy paths (pending buttons, validation errors, auth redirects, the not-found page) where production bugs actually live. For observability, `instrumentation.ts` is the hook ([guide](https://nextjs.org/docs/app/guides/instrumentation)) — a root-level file whose `register()` runs once at server startup, which makes it the home for OpenTelemetry setup and whose `onRequestError` export is where server-side errors (including the redacted ones whose `digest` users see in `error.tsx`) get reported with full detail:

```ts
// instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { registerOTel } = await import("@vercel/otel");
    registerOTel({ serviceName: "acme-web" });
  }
}

export async function onRequestError(err: unknown, request: { path: string }) {
  await reportToErrorTracker(err, { path: request.path });   // Sentry, etc.
}
```

[OpenTelemetry](https://nextjs.org/docs/app/guides/open-telemetry) is the official tracing path — Next.js emits framework spans for rendering and fetching out of the box; add domain spans around your data layer so a slow trace says "the invoice aggregation query" rather than "rendering took a while" (see the [Observability guide](OBSERVABILITY_STUDY_GUIDE.md)).

Finally, operations includes *staying current*. Next.js moves fast and renames things (Middleware→Proxy in 16; the caching model's defaults in 15 — this guide has flagged both), so: upgrade in small steady steps rather than multi-major leaps, read the [upgrade guides](https://nextjs.org/docs/app/guides/upgrading) and release notes with special attention to caching and routing semantics, and lean on the official codemods, which automate most mechanical migrations.

### What to Build: Three Capstones

Knowledge consolidates through building, and these three projects collectively exercise everything in this guide. A **SaaS admin dashboard** — route groups separating marketing from the authenticated shell, URL-driven filters and pagination on the server (Part 2), Server Action CRUD with `useActionState` validation (Part 7), a DAL with per-row authorization (Part 8), tagged caching with precise invalidation (Part 6), and a Playwright suite over login and mutations. Done well it feels boring in the best way: fast, predictable, hard to break. An **e-commerce storefront** — `generateStaticParams` + ISR product pages with `generateMetadata` and JSON-LD (Parts 5, 9), streamed reviews behind Suspense, optimistic cart updates, and a signature-verified, idempotent inventory webhook (Part 7); the hard part isn't building the pages, it's keeping them fast *and correct* while inventory and content change underneath them. And a **content platform** — MDX or CMS-driven nested docs routes, [Draft Mode](https://nextjs.org/docs/app/guides/draft-mode) for editorial preview, intercepting-route previews, search, and the full crawl surface (sitemap, robots, OG images) — proving you can ship something content-first and discoverable, not only CRUD.

And the standing answer to "how should I study this?": **read the official docs alongside this guide** (this guide is the map; the docs are the territory), default to server and add client deliberately, build forms the framework way before abstracting, put view state in the URL, treat freshness as part of each feature's spec, verify behavior against `next build && next start` rather than dev mode, and test flows rather than only functions.

If you remember one thing from Part 10: **`next build` produces a server, not a folder of files — Vercel rents you the operational machinery around it (at a price; do the math), self-hosting hands it to you (streaming-safe proxy, shared cache handler, image pipeline), and either way preview-per-PR, E2E flow tests, and small steady upgrades are what keep the thing healthy.**

### The Wider Ecosystem, Briefly

A few production topics deserve a paragraph each so you know they exist and where their documentation lives, even though they're "after the core model is comfortable" material. **MDX** ([guide](https://nextjs.org/docs/app/guides/mdx)) compiles Markdown-with-components into pages — the natural engine for docs sites and blogs, and a genuinely good first practice project because it exercises routing, `generateStaticParams`, metadata, and the server/client boundary (your prose is server-rendered; the interactive demo embedded in it is a client island) all at once. **Internationalization** ([guide](https://nextjs.org/docs/app/guides/internationalization)) in the App Router is architecture, not string replacement: locale lives in the route tree (`app/[lang]/...`), middleware negotiates the user's locale and rewrites, and every cached page exists per-locale — decide this on day one or pay a routing migration later. **Multi-zones** ([guide](https://nextjs.org/docs/app/guides/multi-zones)) let several independently deployed Next.js apps share one domain via rewrites — the escape valve when one app, one build, and one deploy cadence stops scaling across teams. And **PWA support and package-bundling controls** ([PWAs](https://nextjs.org/docs/app/guides/progressive-web-apps), [Package Bundling](https://nextjs.org/docs/app/guides/package-bundling)) are there when the product calls for them — specialized tools, learned on demand.

---

## Appendix — Reading the Pages Router (Maintenance Mode)

You will inherit Pages Router code — millions of deployed apps use it, it's still supported, and "learn it well enough to maintain it" was this guide's promise. The good news: it's a *simpler* model, and with the App Router internalized you can learn it by mapping backwards. The defining difference is that **every component is a Client Component** (the old, single-React world), so server data can't be read *in* components — it enters through special exported functions on page files, and the framework passes the result down as props:

```tsx
// pages/posts/[slug].tsx — the old world
export async function getServerSideProps(context) {
  const post = await getPost(context.params.slug);       // runs on the server, per request
  if (!post) return { notFound: true };
  return { props: { post } };                            // must be JSON-serializable
}

export default function PostPage({ post }) {             // a plain client component
  return <article>{/* ... */}</article>;
}
```

The translation table covers most of what you'll encounter:

| Pages Router | App Router equivalent |
|---|---|
| `getServerSideProps` | dynamic rendering: just `await` in a Server Component |
| `getStaticProps` | static rendering (the default) |
| `getStaticProps` + `revalidate` | ISR: `export const revalidate = n` |
| `getStaticPaths` | `generateStaticParams` |
| `pages/api/*.ts` | Route Handlers (`route.ts`) — or usually Server Actions |
| `_app.tsx` / `_document.tsx` | the root `layout.tsx` |
| `next/router` (`useRouter`) | `next/navigation` (`useRouter`, `usePathname`, `useSearchParams`) |
| `<Head>` component | the `metadata` export / `generateMetadata` |

The deeper differences to keep in mind while maintaining: Pages Router has no nested layouts (hence the `getLayout` pattern hacks you'll find in older codebases), no streaming or Suspense-based loading conventions, no Server Actions (every mutation is a hand-rolled `fetch` to `pages/api/`), and *page-level* data fetching only — which is why old codebases route everything through giant page components and prop-drill from there. When migrating, the [official incremental migration guide](https://nextjs.org/docs/app/guides/migrating/app-router-migration) matters because the two routers can coexist in one app: migrate route by route, not big-bang. And resist the urge to "migrate" by slapping `'use client'` on everything — that produces an App Router app with Pages Router economics, the worst of both.

---

## A Practice Track

Reading builds the map; only building builds the skill. These exercises are sequenced to match the parts, each one chosen because it forces the concept to actually load-bear — do them against `next build && next start`, not just dev mode:

1. **(Parts 1–2)** Scaffold an app with `create-next-app`, enable `typedRoutes`, and model a marketing site plus an authenticated dashboard using route groups and nested layouts. Verify the dashboard shell *doesn't* remount when navigating between its subpages (put a `useState` counter in the sidebar and watch it survive).
2. **(Part 2)** Build the photo-gallery modal with intercepting + parallel routes: thumbnail click → modal, direct URL → full page, back button → modal closes.
3. **(Part 3)** Build the product page with a server-rendered markdown description and client-island cart controls. Then deliberately break it: move `'use client'` up to the page, run the bundle analyzer, and *measure* what it cost. Undo it.
4. **(Parts 4–5)** Build a dashboard that fetches three data sources in parallel and streams the slowest behind its own `<Suspense>`. Implement the same route three ways — fully dynamic, ISR with a 60-second window, streamed — and compare first-byte and total-load behavior.
5. **(Part 6)** Build a blog with tagged fetches and an admin publish action that invalidates exactly the affected tag. Then run the staleness checklist on purpose: remove the tag, watch the page go stale, and diagnose it layer by layer.
6. **(Part 7)** Build a create/edit form with `useActionState` validation, `useFormStatus` pending UI, a "Save draft" secondary `formAction`, and optimistic comments with rollback. Then call your action from `curl` with garbage input and confirm the server, not the UI, rejects it.
7. **(Part 8)** Add middleware that bounces anonymous users off `/dashboard`, a `verifySession`-backed DAL with per-row authorization, and `server-only` on every privileged module. Try to import the db client from a client component and confirm the build fails.
8. **(Part 9)** Take any page from the earlier exercises and add `generateMetadata`, a database-driven `sitemap.ts`, and `next/image` with a `priority` hero. Measure CLS and LCP before and after.
9. **(Part 10)** Deploy the same app twice — once to Vercel, once self-hosted in Docker behind a reverse proxy. Write down every difference you had to handle; that list *is* the trade-off table, learned personally.

Then pick one of Part 10's capstones and build it end to end. The dashboard capstone is the best first choice: it exercises the most parts with the least content-production overhead.

---

## Where to Go from Here

The arc of this guide, compressed: Next.js is React spanning two computers (Part 1); the filesystem declares the architecture (Part 2); the server/client boundary is the load-bearing concept everything else leans on (Part 3); reads happen in async Server Components through a data layer (Part 4); rendering is a per-route spectrum from static through streamed (Part 5); four caches with four keys and four invalidation stories sit between your data and your users (Part 6); writes are Server Actions shaped *authorize → validate → write → revalidate → redirect* (Part 7); security lives in the DAL, not the middleware (Part 8); the optimizers and state-location discipline keep it fast (Part 9); and deployment is a real choice you should make with open eyes (Part 10).

A last calibration note, because frameworks this size invite both cargo-culting and contrarianism: most Next.js failures in the wild are not exotic. They are a `'use client'` placed too high, a cache nobody decided on, an action that trusted its caller, or a deployment that assumed Vercel semantics on a VPS. Every one of those is a Part of this guide, and every one is checkable in an afternoon. The framework rewards engineers who can say *where* code runs, *when* it rendered, and *how stale* it's allowed to be — and it quietly punishes everyone else. Aim to be the person on the team who can answer those three questions for any route.

Core references, gathered: the [Next.js docs](https://nextjs.org/docs) (especially [Getting Started](https://nextjs.org/docs/app/getting-started), the [Guides](https://nextjs.org/docs/app/guides), and the [Production Checklist](https://nextjs.org/docs/app/guides/production-checklist) before any launch); the React side of the model — [Server Components](https://react.dev/reference/rsc/server-components), [Server Functions](https://react.dev/reference/rsc/server-functions), [`'use client'`](https://react.dev/reference/rsc/use-client), [`'use server'`](https://react.dev/reference/rsc/use-server), [`useActionState`](https://react.dev/reference/react/useActionState), [`useOptimistic`](https://react.dev/reference/react/useOptimistic), and [`<form>`](https://react.dev/reference/react-dom/components/form); and the conceptual deep ends — Josh Comeau's [Making Sense of React Server Components](https://www.joshwcomeau.com/react/server-components/) and Dan Abramov's [overreacted.io](https://overreacted.io/) essays.

And beneath all of it, the web-platform substrate the framework builds on — MDN's [Request](https://developer.mozilla.org/en-US/docs/Web/API/Request), [Response](https://developer.mozilla.org/en-US/docs/Web/API/Response), [FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData), [URLSearchParams](https://developer.mozilla.org/en-US/docs/Web/API/URLSearchParams), and [Streams](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API) — because every Route Handler, Server Action, and streamed render in this guide is ultimately those five APIs wearing a framework.

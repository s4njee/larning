# SvelteKit Study Guide

A depth-first guide to building full-stack web applications with **SvelteKit and Svelte 5**, written for engineers who already know HTML, CSS, TypeScript, and the request-response model, and who may have framework experience elsewhere (the [Vue](VUE_STUDY_GUIDE.md) and [Next.js](NEXTJS_STUDY_GUIDE.md) guides are natural companions). SvelteKit is easy to start and easy to misunderstand, because it looks like two familiar things at once — "a component framework with file-based routing" and "a Node server with templates" — and it is genuinely both. The central thesis of this guide is that **SvelteKit is one codebase describing two programs: one that runs on a server you control, and one that runs in a browser you don't.** Every important design decision in the framework — where `load` functions live, why `$lib/server` exists, why forms work without JavaScript, what an adapter is — is an answer to the question *"which side of that boundary does this code belong on, and when does it run?"* Once you can answer that question reflexively for any file in a SvelteKit project, the rest of the framework is small. The guide is also unapologetically **Svelte 5 first**: runes (`$state`, `$derived`, `$effect`, `$props`) are the reactivity model, snippets replace slots, and events are just properties. Legacy syntax (`export let`, `$:`, `on:click`) appears only in Part 12, as something you must be able to *read* in older codebases, not something you should write.

> *SvelteKit's deepest idea is also its oldest: a website is a server that sends HTML, and links and forms that ask it for more. The framework's job is to make that baseline excellent, then layer a client-side app on top — not the other way around.*

Primary references: the official docs at [svelte.dev](https://svelte.dev) are unusually good and current — read the [Svelte docs](https://svelte.dev/docs/svelte/overview) for the component language and the [SvelteKit docs](https://svelte.dev/docs/kit/introduction) for the framework, and work through the [interactive tutorial](https://svelte.dev/tutorial) early (it covers both, in the browser, and is the single best onboarding artifact in the ecosystem). For third-party depth: [Joy of Code](https://joyofcode.xyz/) (the best long-form SvelteKit tutorials anywhere), [Svelte Society](https://sveltesociety.dev/) (community recipes and packages), and Rich Harris's talks — [Rethinking Reactivity](https://www.youtube.com/watch?v=AdNJ3fydeao) (why Svelte compiles instead of diffing) and [Have Single-Page Apps Ruined the Web?](https://www.youtube.com/watch?v=860d8usGC0o) (the "transitional apps" argument that explains SvelteKit's whole posture). Companion guides in this repo: [TypeScript](TYPESCRIPT_STUDY_GUIDE.md), [Advanced Node.js](ADVANCED_NODEJS_STUDY_GUIDE.md), [Auth](AUTH_STUDY_GUIDE.md), [Cloudflare](CLOUDFLARE_STUDY_GUIDE.md), and [Next.js](NEXTJS_STUDY_GUIDE.md) (for comparing the two dominant meta-frameworks' answers to the same problems).

---

## Table of Contents

1. [Part 1 — Setup and the Server/Client Mental Model](#part-1--setup-and-the-serverclient-mental-model)
2. [Part 2 — Svelte 5: Components, Runes, and Reactivity](#part-2--svelte-5-components-runes-and-reactivity)
3. [Part 3 — The Filesystem Is the Router](#part-3--the-filesystem-is-the-router)
4. [Part 4 — Loading Data](#part-4--loading-data)
5. [Part 5 — Mutations: Form Actions and API Endpoints](#part-5--mutations-form-actions-and-api-endpoints)
6. [Part 6 — Hooks, Server-Only Modules, and Auth](#part-6--hooks-server-only-modules-and-auth)
7. [Part 7 — State Management Without Foot-Guns](#part-7--state-management-without-foot-guns)
8. [Part 8 — Rendering Strategies: SSR, CSR, and Prerendering](#part-8--rendering-strategies-ssr-csr-and-prerendering)
9. [Part 9 — Performance, Images, and SEO](#part-9--performance-images-and-seo)
10. [Part 10 — Testing and Quality](#part-10--testing-and-quality)
11. [Part 11 — Adapters, Building, and Deployment](#part-11--adapters-building-and-deployment)
12. [Part 12 — The Ecosystem and Where to Go Next](#part-12--the-ecosystem-and-where-to-go-next)
13. [Part 13 — Recipes: Eight Patterns That Tie It Together](#part-13--recipes-eight-patterns-that-tie-it-together)

---

## Part 1 — Setup and the Server/Client Mental Model

### 1.1 What SvelteKit Actually Is

Svelte and SvelteKit are two different things, and keeping them separate in your head pays off immediately. **Svelte** is a component language and compiler: you write `.svelte` files, and the compiler turns them into efficient JavaScript that surgically updates the DOM — no virtual DOM, no runtime diffing, just generated code that knows exactly which `<span>` to update when which variable changes. (Rich Harris's [Rethinking Reactivity](https://www.youtube.com/watch?v=AdNJ3fydeao) talk is the canonical explanation of why this approach exists.) **SvelteKit** is the application framework built around that compiler: routing, server-side rendering, data loading, form handling, deployment. The relationship is the same as React-to-Next.js, except that Svelte's team builds both, so the seams are cleaner.

The thing SvelteKit is *for* is what Harris calls a **transitional app**: a site that works like a traditional server-rendered website on first contact — real HTML arrives, links and forms work, search engines and slow devices are happy — and then *transitions* into a client-side app once JavaScript loads, so subsequent navigation is instant and stateful. You do not choose between "server-rendered site" and "SPA"; you get both, in that order, by default. This is why the guide keeps returning to one question:

**For every line of code you write in a SvelteKit project, you should be able to say where it runs: server only, browser only, or both — and when: at build time, per request, or after hydration.**

Here is the lifecycle that question lives inside. A user requests `/dashboard`. The **server** (your Node process, a serverless function, an edge worker — Part 11) runs your server-side `load` functions, renders the page's components *to an HTML string*, and sends it. The browser displays that HTML immediately — the site is already usable. Then the JavaScript bundle arrives and **hydrates** the page: Svelte attaches event listeners and reactive state to the existing DOM rather than re-creating it. From that point on, the **client-side router** takes over: clicking an internal link doesn't trigger a full page load; instead, SvelteKit fetches just the *data* for the next route, runs the relevant `load` functions (some in the browser, some via request to the server — Part 4 is entirely about this), and swaps components in place. Server-rendered first paint, SPA-quality navigation afterward. Every part of this guide elaborates some stage of that lifecycle.

References: [SvelteKit introduction](https://svelte.dev/docs/kit/introduction), [Glossary (SSR, hydration, CSR)](https://svelte.dev/docs/kit/glossary).

### 1.2 Scaffolding a Project with `sv`

The official CLI is `sv` (it replaced the older `create-svelte`). Scaffold a project with:

```bash
npx sv create my-app
```

The prompts let you pick a template (choose the minimal one — the demo app is worth reading once, not building on), **TypeScript** (say yes; route data and form payloads are exactly where types earn their keep), and add-ons. The add-on system is worth adopting as a habit: `npx sv add eslint prettier vitest playwright` installs and *wires up* each tool the way the Svelte team intends, which keeps your config aligned with the ecosystem instead of drifting with whatever tutorial you happened to read. Two more commands belong in your muscle memory: `npx sv check` runs `svelte-check` — the compiler's diagnostics, TypeScript errors, and accessibility warnings in one pass (make it a CI gate from day one, not an optional extra), and `npx sv migrate` automates version migrations, including Svelte 4 → 5.

References: [Creating a project](https://svelte.dev/docs/kit/creating-a-project), [`sv create`](https://svelte.dev/docs/cli/sv-create), [`sv add`](https://svelte.dev/docs/cli/sv-add), [`sv check`](https://svelte.dev/docs/cli/sv-check).

### 1.3 The Project Structure Encodes the Boundary

A fresh project looks like this:

```
my-app/
├── src/
│   ├── lib/                 # shared code, importable as $lib
│   │   └── server/          # SERVER-ONLY code — cannot reach the client (Part 6)
│   ├── params/              # route param matchers (Part 3)
│   ├── routes/              # the filesystem router (Part 3)
│   ├── app.html             # the HTML shell every page is injected into
│   ├── app.d.ts             # ambient types: App.Locals, App.PageData, App.Error
│   ├── error.html           # last-resort error page (when even SvelteKit fails)
│   ├── hooks.server.ts      # server request middleware (Part 6)
│   └── hooks.client.ts      # client-side error handling
├── static/                  # served verbatim: robots.txt, favicon, fonts
├── svelte.config.js         # adapter + compiler config (Part 11)
├── vite.config.ts           # SvelteKit is a Vite plugin; this is the build tool
└── tsconfig.json            # extends generated config in .svelte-kit/
```

Notice that the server/client boundary is *physical*, not conventional. `src/lib` is shared code importable from anywhere via the `$lib` alias. `src/lib/server` is server-only **by construction**: if any code path reachable from the browser tries to import from it, the build fails. Your database client, your secret-bearing API wrappers, your session logic — they go in `$lib/server`, and then leaking them into the client bundle becomes a compile error instead of a code-review hope. This is the first of many places SvelteKit turns the mental model into tooling, and Part 6 covers the mechanism in detail.

It's also worth knowing what SvelteKit *doesn't* invent. The framework is built on **web standards**: `Request`, `Response`, `fetch`, `FormData`, `Headers`, `URL`, and streams are the native platform objects, not framework look-alikes. A SvelteKit endpoint receives a standard `Request` and returns a standard `Response`. Skills transfer in both directions — everything you learn writing SvelteKit servers applies to Cloudflare Workers, Deno, and service workers, and vice versa. When you're unsure how something works, MDN is often the right documentation. Underneath, the dev server and bundler are [Vite](https://vite.dev/guide/), which is where aliases, env modes, and plugins live when you need to debug them.

References: [Project structure](https://svelte.dev/docs/kit/project-structure), [Web standards](https://svelte.dev/docs/kit/web-standards).

### 1.4 Where SvelteKit Sits Among the Alternatives

A quick orientation before diving in, since "should we use SvelteKit?" is a question you'll be asked. The honest comparison is along two axes: how much runs on a server, and how much JavaScript ships to the client.

| | SvelteKit | Next.js | Astro | Vite SPA (no meta-framework) |
|---|---|---|---|---|
| Default posture | SSR + hydrate, per-route overrides | SSR/RSC + hydrate | static HTML, islands of interactivity | client-renders everything |
| Component model | Svelte (compiled, no runtime VDOM) | React | bring your own (incl. Svelte) | bring your own |
| Mutations story | form actions, progressive enhancement | server actions | form POSTs to endpoints | hand-rolled fetch layer |
| JS shipped for static content | small; zero with `csr = false` | larger (React runtime; RSC reduces it) | zero by default | full bundle |
| Sweet spot | full-stack apps and transitional sites | React-ecosystem apps at scale | content-dominant sites | embedded widgets, dashboards behind auth |

The pattern to notice: SvelteKit and Next.js answer the same questions with different ecosystems (the [Next.js guide](NEXTJS_STUDY_GUIDE.md) maps the concepts one-to-one — `load` ≈ server components' data fetching, form actions ≈ server actions, adapters ≈ deployment targets), Astro starts from "no JavaScript" and adds it per-island, and a bare SPA starts from "all JavaScript" and can't subtract. SvelteKit's bet is the middle: server-first defaults with per-route dials in both directions (Part 8).

**Practice:** scaffold a fresh app with `npx sv create`, add ESLint, Prettier, and Vitest through `sv add`, then walk every top-level file and directory and say out loud what it does, where its code runs, and when. Finish with `npm run build && npm run preview` so the dev-versus-production distinction is concrete before you write a single feature.

---

## Part 2 — Svelte 5: Components, Runes, and Reactivity

SvelteKit apps are made of Svelte components, so before any routing or data loading you need the component language under your fingers. Svelte 5 rebuilt the reactivity system around **runes** — compiler-recognized functions like `$state` and `$derived` that declare *what kind of reactive thing* a variable is. If you've used Vue's `ref`/`computed` or React's hooks, the shapes will look familiar, but the semantics are Svelte's own: runes are compile-time markers backed by fine-grained runtime *signals*, so updates propagate directly from the data that changed to the DOM that depends on it, with no component-level re-render in between. There is no dependency array to forget and no memoization to hand-tune.

References: [What are runes?](https://svelte.dev/docs/svelte/what-are-runes), [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide).

### 2.1 Anatomy of a Component

A `.svelte` file has three optional sections — script, markup, style — and the compiler treats the whole file as one cohesive module:

```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2);
</script>

<button onclick={() => count++}>
  clicked {count} {count === 1 ? 'time' : 'times'} (doubled: {doubled})
</button>

<style>
  button {
    background: royalblue; /* scoped: affects only THIS component's buttons */
    color: white;
  }
</style>
```

Three things to notice. First, **events are just properties** in Svelte 5: `onclick={handler}`, not the legacy `on:click`. There is no synthetic event system; that's a real DOM `click` listener. Second, the markup section uses `{expression}` interpolation plus control-flow blocks — `{#if}`, `{#each}`, `{#await}`, `{#key}` — which are the backbone of all Svelte rendering work ([docs](https://svelte.dev/docs/svelte/basic-markup)). Third, **styles are scoped by default**: the compiler adds a hash-based class so your `button` rule can't leak out, which eliminates most CSS naming ceremony. Escape hatches exist — `:global(...)` for deliberate global rules, CSS custom properties for theming contracts — but reach for them intentionally ([scoped styles](https://svelte.dev/docs/svelte/scoped-styles), [global styles](https://svelte.dev/docs/svelte/global-styles)).

### 2.2 `$state` — Reactive State Is Deeply Proxied

`$state` declares a reactive variable. Reading it in markup or in a derived value creates a dependency; writing it triggers precise updates:

```svelte
<script lang="ts">
  let todos = $state([
    { text: 'learn runes', done: false },
    { text: 'ship something', done: false }
  ]);

  function addTodo(text: string) {
    todos.push({ text, done: false }); // mutation works — no spread dance needed
  }
</script>

{#each todos as todo}
  <label>
    <input type="checkbox" bind:checked={todo.done} />
    {todo.text}
  </label>
{/each}
```

The crucial semantic: when you pass an **object or array** to `$state`, Svelte wraps it in a recursive **`Proxy`**. Property reads register dependencies; property writes trigger updates — *at any depth*. That's why `todos.push(...)` and `todo.done = true` just work, with no immutability discipline and no `setState`. The proxying is deep and lazy (nested objects are proxied when first touched), and it applies to plain objects and arrays — class instances are not automatically proxied (make individual class fields reactive with `$state` in the field declaration instead).

Two companions matter in practice. **`$state.raw(value)`** opts out of proxying: the value is only reactive on *reassignment*, not mutation — the right choice for large immutable payloads (e.g., a big list from the server you'll only ever replace) where deep proxying is wasted overhead. **`$state.snapshot(value)`** takes a plain, non-proxied copy — necessary when handing state to code that chokes on proxies, like `structuredClone`, `JSON.stringify` comparisons, or some third-party libraries.

References: [`$state`](https://svelte.dev/docs/svelte/$state).

### 2.3 `$derived` — Computed Values Are Lazy

`$derived` declares a value computed from other reactive state:

```svelte
<script lang="ts">
  let todos = $state<Todo[]>([]);
  let remaining = $derived(todos.filter((t) => !t.done).length);

  // multi-statement derivations use $derived.by
  let summary = $derived.by(() => {
    if (todos.length === 0) return 'nothing to do';
    return `${remaining} of ${todos.length} remaining`;
  });
</script>
```

Dependencies are tracked automatically — whatever reactive state the expression reads, it depends on; there is nothing to declare and nothing to get stale. Two semantics distinguish `$derived` from a naive "computed" mental model. First, evaluation is **lazy**: when a dependency changes, the derived is merely marked dirty; the expression re-runs only when something actually *reads* the value. An expensive derivation that nothing currently displays costs nothing. Second, derived expressions must be **side-effect free** — the compiler forbids writing state inside them, which is exactly the discipline that keeps a reactive graph debuggable. (Since Svelte 5.25 a derived can be temporarily *overridden* by assignment — useful for optimistic UI, where you locally override a server-derived value until the round trip confirms it — and it snaps back to the computed value when dependencies next change.)

The deeper point: **`$state` plus `$derived` form a declarative dependency graph.** Most "how do I keep X in sync with Y" problems are solved by making X a derived of Y, not by writing an effect that copies Y into X. Hold that thought for the next section, because it's the most common Svelte 5 mistake.

References: [`$derived`](https://svelte.dev/docs/svelte/$derived).

### 2.4 `$effect` — Side Effects, Sparingly

`$effect` runs a function whenever the reactive values it reads change. It is for **side effects** — synchronizing with things *outside* the reactive graph: the DOM, timers, network, third-party libraries, `localStorage`:

```svelte
<script lang="ts">
  let canvas: HTMLCanvasElement;
  let color = $state('#ff3e00');

  $effect(() => {
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = color;          // reading `color` makes it a dependency
    ctx.fillRect(0, 0, 100, 100);
  });

  $effect(() => {
    const id = setInterval(() => console.log('tick'), 1000);
    return () => clearInterval(id); // teardown: runs before re-run and on destroy
  });
</script>

<canvas bind:this={canvas}></canvas>
<input type="color" bind:value={color} />
```

The timing semantics matter and are easy to get subtly wrong if you assume React's. An effect runs **after the component is mounted and after DOM updates are applied**, in a batched microtask — so inside an effect the DOM already reflects the new state. Dependencies are whatever reactive state the function reads **synchronously** during its run; anything read after an `await` or inside a `setTimeout` is *not* tracked. The optional returned function is teardown, invoked before each re-run and on destroy. If you need to run *before* the DOM updates (e.g., to read scroll position for an auto-scrolling chat), use `$effect.pre`. And critically: **effects do not run during server-side rendering.** SSR renders your component top to bottom once and ships HTML; effects belong to the browser's lifetime. This is why "browser-only" setup naturally lives in effects (or `onMount`), and why code in the top-level `<script>` must be safe to run on the server.

The most important guidance is negative: **don't use `$effect` to synchronize state.** Writing one piece of state inside an effect because another changed is the path to circular updates and unpredictable ordering — that job belongs to `$derived`. A good heuristic from the docs: if your effect's body assigns to a reactive variable, you almost certainly want a derived (or a callback) instead. When you genuinely need to read state inside an effect *without* depending on it, wrap the read in `untrack(...)`.

References: [`$effect`](https://svelte.dev/docs/svelte/$effect), [Lifecycle hooks](https://svelte.dev/docs/svelte/lifecycle-hooks) (`onMount`, `onDestroy`, and `tick` still exist and remain useful for DOM-timing work).

### 2.5 `$props`, `$bindable`, and Component APIs

Props are declared by destructuring `$props()`, which gives you defaults, renaming, rest props, and ordinary TypeScript in one move:

```svelte
<script lang="ts">
  interface Props {
    label: string;
    variant?: 'primary' | 'ghost';
    onclick?: (e: MouseEvent) => void;   // "events" are just callback props now
    disabled?: boolean;
  }

  let { label, variant = 'primary', onclick, disabled = false }: Props = $props();
</script>

<button class={variant} {onclick} {disabled}>{label}</button>
```

Note what replaced Svelte 4's `createEventDispatcher`: **component events are plain callback props**. A child "emits" by calling `onclick?.(...)` or `onSelected?.(item)`; the parent passes a function. This collapses a whole concept into something you already know, and it composes with TypeScript perfectly.

Props are one-way by default — the child must not reassign them. When two-way binding is genuinely the right API (form-control-like components: inputs, selects, toggles), the child opts in with **`$bindable`**:

```svelte
<script lang="ts">
  let { value = $bindable('') } = $props();
</script>

<input bind:value />
```

Now a parent can write `<SearchBox bind:value={query} />`. The discipline to carry: bindings are for components whose *purpose* is to own a value temporarily; most data should flow down as props and back up as callbacks, so ownership stays legible ([`$props`](https://svelte.dev/docs/svelte/$props), [`$bindable`](https://svelte.dev/docs/svelte/$bindable), [`bind:`](https://svelte.dev/docs/svelte/bind)).

### 2.6 Snippets, Composition, and Reuse Primitives

Svelte 5 replaced slots with **snippets** — chunks of markup that are values, declared with `{#snippet}` and rendered with `{@render}`. Content passed inside a component's tags becomes its `children` snippet:

```svelte
<!-- Card.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  let { header, children }: { header?: Snippet; children: Snippet } = $props();
</script>

<article class="card">
  {#if header}<header>{@render header()}</header>{/if}
  {@render children()}
</article>

<!-- usage -->
<Card>
  {#snippet header()}<h2>Hello</h2>{/snippet}
  <p>Body content becomes the implicit `children` snippet.</p>
</Card>
```

Snippets take parameters, which makes them strictly more powerful than slots — a table component can accept a `row(item)` snippet and call it per row, giving you typed, render-prop-style composition without any new concept ([snippets](https://svelte.dev/docs/svelte/snippet)).

Beyond components, know the reuse toolbox: **context** (`setContext`/`getContext`) shares state down a subtree without prop drilling — ideal for compound components and per-request services, and importantly *safe on the server* because it's scoped to the component tree rather than module scope ([context](https://svelte.dev/docs/svelte/context)). **Actions** (`use:clickOutside`) encapsulate imperative DOM behavior — focus traps, third-party widget mounting — as reusable functions applied to elements ([use:](https://svelte.dev/docs/svelte/use)). **Transitions** (`transition:fade`, `in:`, `out:`, `animate:flip`) communicate state changes with motion and are compiled away when unused ([transition:](https://svelte.dev/docs/svelte/transition)). And **`.svelte.ts` modules** let you use runes *outside* components — a file like `counter.svelte.ts` can export reactive state and the functions that mutate it, which is Svelte 5's replacement for many store use cases (Part 7). The classic store API (`writable`, `derived`) still exists and interoperates, but it is no longer the default answer to shared state ([stores](https://svelte.dev/docs/svelte/stores)).

Finally, take the compiler's **accessibility warnings** seriously — Svelte lints for missing alt text, click handlers on non-interactive elements, and more at compile time, and `sv check` surfaces them in CI. Semantic HTML first, ARIA second, suppression comments almost never.

### 2.7 Debugging Reactivity: `$inspect` and Snapshots

Two small tools save hours. `console.log(todos)` on proxied state prints a `Proxy` object that browsers render unhelpfully and that *keeps mutating* after you logged it — log `$state.snapshot(todos)` instead to capture a plain copy at that moment. Better still, the **`$inspect`** rune is a reactive logger: `$inspect(count, todos)` re-logs whenever its arguments change (deeply), and `$inspect(count).with((type, value) => { debugger; })` turns changes into breakpoints so you can see *which* code mutated the state. `$inspect` only exists in development — the compiler strips it from production builds — so it's safe to leave in while you work ([`$inspect`](https://svelte.dev/docs/svelte/$inspect)).

**Practice:** build a filterable list component using `$state`, `$derived`, `{#each}`, and `bind:`, then split it into parent/child components communicating through `$props` and callback props. Then build a headless dropdown that composes the reuse toolbox: context for shared open/close state, a click-outside action, a transition on the menu, and a snippet for item rendering.

---

## Part 3 — The Filesystem Is the Router

### 3.1 Routes Are Directories; Files Have Roles

SvelteKit's router is the `src/routes` directory tree: **a directory is a URL segment, and the files inside it declare what that URL can do.** There's no route registry to maintain and no config file to drift out of sync — the URL structure of your app is `ls -R src/routes`. Every routing file starts with `+`, and there are eight of them. They come in pairs that straddle the server/client boundary, which is why learning them as a table is worth a hundred bullet points:

| File | Runs on | Role |
|---|---|---|
| `+page.svelte` | server (SSR) then browser | the page's component |
| `+page.ts` | server **and** browser | *universal* `load` for the page (Part 4) |
| `+page.server.ts` | server only | *server* `load` + form `actions` (Parts 4–5) |
| `+layout.svelte` | server then browser | wraps child pages; persists across navigation |
| `+layout.ts` / `+layout.server.ts` | as above | `load` for the layout and all its children |
| `+error.svelte` | server then browser | error boundary for this subtree (Part 6) |
| `+server.ts` | server only | raw HTTP endpoint: GET/POST/… → `Response` (Part 5) |

So a blog might look like:

```
src/routes/
├── +layout.svelte            → nav and footer for every page
├── +page.svelte              → /
├── about/+page.svelte        → /about
├── blog/
│   ├── +page.server.ts       → loads the post list
│   ├── +page.svelte          → /blog
│   └── [slug]/
│       ├── +page.server.ts   → loads one post (or 404s)
│       └── +page.svelte      → /blog/hello-world, /blog/anything
└── api/health/+server.ts     → GET /api/health (JSON, no page)
```

`[slug]` is a **dynamic parameter**: the directory matches any value for that segment, and the value arrives in your `load` function as `params.slug`. Parameters are part of your public API — they shape your links, your SEO, and your cache keys — so design them like API contracts, not like incidental file names. To keep garbage out of them, add a **param matcher**: a file `src/params/integer.ts` exporting a `match(value)` function lets you write `[id=integer]`, and URLs that fail the matcher don't match the route at all (falling through to other routes or a 404) instead of flowing into your logic as a malformed string.

References: [Routing](https://svelte.dev/docs/kit/routing), [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).

### 3.2 Layouts Nest, and Sometimes You Need to Escape

A `+layout.svelte` renders its children via the `children` snippet, and layouts **nest**: `/settings/profile` renders the root layout, around `settings/+layout.svelte`, around the page. Layout components *persist* across navigation between their children — state in the layout (a sidebar's scroll position, a playing audio element) survives page changes. The minimal root layout is just:

```svelte
<script lang="ts">
  let { children } = $props();
</script>

<nav><!-- site chrome --></nav>
{@render children()}
```

Use layouts for *genuine product structure* — the marketing shell, the authenticated app shell, the docs sidebar — and reach for two pieces of advanced routing when the URL tree and the layout tree disagree. **Route groups** — directories named `(group)` — organize files and attach layouts *without* affecting the URL: a classic setup is `(marketing)/about` and `(app)/dashboard`, where each group has its own `+layout.svelte` but the URLs stay `/about` and `/dashboard`. **Layout escapes** — naming a file `+page@.svelte` or `+page@(app).svelte` — let a page reset to a higher layout, which is exactly what a full-screen login page or a print view needs instead of inheriting the app shell. **Rest parameters** (`[...path]`) match any depth — the right tool for docs trees and file browsers — and **optional parameters** (`[[lang]]`) make a segment matchable-but-absent. All are documented under [advanced routing](https://svelte.dev/docs/kit/advanced-routing); use them when the product demands, not for cleverness.

### 3.3 Navigation: Links First, Then the Router

After hydration, SvelteKit's client router intercepts clicks on internal `<a>` tags. This is a deliberate philosophy: **normal links are the navigation API.** No `<Link>` component, no framework lock-in in your markup — anchor tags work before JavaScript loads, in RSS readers, for crawlers, and the router progressively enhances them. The router's superpower is **preloading**: with `data-sveltekit-preload-data="hover"` (the scaffolded default on `<body>`), SvelteKit starts loading a link's code and data when the user hovers or touches it — typically a couple hundred milliseconds before the click — so navigation feels instant ([link options](https://svelte.dev/docs/kit/link-options)).

Programmatic navigation lives in `$app/navigation`: `goto('/dashboard')` for imperative redirects after client-side events, `invalidate`/`invalidateAll` to re-run `load` functions (Part 4), `preloadData` to warm a route manually, and lifecycle hooks like `beforeNavigate`/`afterNavigate` for guards and analytics. Use `goto` sparingly — most navigation should be links, and most post-mutation redirects belong on the server (Part 5). The lifecycle hooks earn their keep for cross-cutting concerns; the classic is an unsaved-changes guard:

```ts
import { beforeNavigate } from '$app/navigation';

beforeNavigate(({ cancel }) => {
  if (hasUnsavedChanges && !confirm('Discard unsaved changes?')) cancel();
});
```

Two refinements handle the "app-like" cases that tempt people back toward SPA habits. **Shallow routing** (`pushState`/`replaceState` from `$app/navigation`) creates history entries *without* running a navigation — the canonical use is a photo modal or filter drawer that the mobile back button should close, while the URL stays shareable ([shallow routing](https://svelte.dev/docs/kit/shallow-routing)). **Snapshots** preserve ephemeral DOM state across navigation: export `const snapshot = { capture, restore }` from a page, and a half-typed comment survives the user clicking away and coming back ([snapshots](https://svelte.dev/docs/kit/snapshots)).

**Practice:** lay out a docs-style site: a `(marketing)` group and an `(app)` group with different layouts, a login page that escapes the app shell with `+page@`, docs pages under `[...path]` with a param matcher guarding a `[version=semver]` segment, and a photo-grid modal driven by shallow routing. Navigate it with JavaScript disabled and confirm every URL still resolves.

---

## Part 4 — Loading Data

This is the heart of SvelteKit, and the part where the server/client mental model stops being philosophy and starts being API. Every page can have `load` functions that provide its data, and the framework's job is to run them in the right place, at the right time, and only when necessary. Internalize this part and the rest of the framework feels inevitable; skim it and you'll fight mysterious reruns and waterfalls forever.

References: [Loading data](https://svelte.dev/docs/kit/load) — the single most important page in the SvelteKit docs; read it twice.

### 4.1 The Shape: `load` In, `data` Out

A page declares its data dependencies by exporting a `load` function from a sibling file. The returned object arrives in the component as the `data` prop, fully typed via generated `$types`:

```ts
// src/routes/blog/[slug]/+page.server.ts
import { error } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
  const post = await db.getPost(params.slug);
  if (!post) error(404, 'Post not found');
  return { post };
};
```

```svelte
<!-- src/routes/blog/[slug]/+page.svelte -->
<script lang="ts">
  import type { PageProps } from './$types';
  let { data }: PageProps = $props();
</script>

<h1>{data.post.title}</h1>
{@html data.post.renderedHtml}
```

The `./$types` import is SvelteKit generating types *for this specific route*: `params.slug` exists because the directory is named `[slug]`, and `data.post` is typed because the `load` function returns it. Never hand-roll these contracts — the generated types are what keeps a full-stack codebase honest as routes evolve. Layouts work identically: a `+layout.server.ts` `load` provides data to the layout *and every page beneath it*, and a page can read its ancestors' data via `await parent()` or, in the component, through the merged `data` prop. Put data where it's shared: the logged-in user belongs in the root layout's `load`; the blog post belongs in the page's.

### 4.2 Server Load vs Universal Load — the Decision That Matters

There are two kinds of `load`, distinguished by filename, and choosing correctly is a core skill rather than an implementation detail:

A **server load** (`+page.server.ts` / `+layout.server.ts`) **always runs on the server** — on first visit it runs during SSR; on client-side navigation the browser fetches its result over the wire (SvelteKit issues a request to a special endpoint, runs your function on the server, and serializes the result back). Because it never executes in the browser, it can do privileged things: query the database directly, read `cookies`, use `event.locals` (Part 6), reference secret environment variables, import from `$lib/server`. The cost of the boundary crossing is that its return value must be **serializable** — SvelteKit uses [devalue](https://github.com/Rich-Harris/devalue), which is far richer than JSON (it handles `Date`, `Map`, `Set`, `BigInt`, regexes, repeated/cyclic references, and even promises — see streaming below) but cannot ship functions, class instances, or component constructors across the wire.

A **universal load** (`+page.ts` / `+layout.ts`) is code that lives on *both* sides of the boundary. On the first, server-rendered visit it runs on the server, then **runs again in the browser during hydration** (re-using the responses of any `fetch` calls, which SvelteKit inlined into the HTML, so no duplicate network requests hit your backend). On subsequent client-side navigations it runs **only in the browser**. Because it executes where it's used, its return value never crosses a serialization boundary — it can return anything, including class instances and Svelte component constructors. But for the same reason it must be unprivileged: no cookies, no locals, no secrets, nothing that can't run in a hostile browser.

| | Server load (`+page.server.ts`) | Universal load (`+page.ts`) |
|---|---|---|
| Runs | server, always | server during SSR, then browser |
| Access to DB, secrets, `cookies`, `locals` | ✅ | ❌ |
| Return value | must be serializable (devalue) | anything (components, class instances) |
| Talks to external public APIs | works, adds a server hop on navigation | browser can call them directly |
| Default choice for | almost everything touching *your* data | public-API fetches, data massaging, returning non-serializable values |

When a route has **both**, the server load runs first and its result arrives as the `data` argument to the universal load, which can transform or extend it — a clean pattern for "fetch privately on the server, reshape into rich objects universally":

```ts
// +page.server.ts — privileged half: queries the database, result crosses the wire
export const load: PageServerLoad = async ({ locals }) => {
  return { report: await db.getReport(locals.user.id) };   // devalue-serializable
};
```

```ts
// +page.ts — universal half: runs where it's used, so it can return anything
import { TrendChart, BarChart } from '$lib/charts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ data }) => {
  return {
    ...data,
    Chart: data.report.kind === 'trend' ? TrendChart : BarChart  // a component class —
  };                                                             // impossible to serialize,
};                                                               // fine to return here
```

The honest default: **start with server load.** It keeps credentials and query logic behind the boundary, and you can introduce a universal load later when you have a concrete reason.

One more tool belongs in this picture: the **`fetch` provided to `load`** (`async ({ fetch }) => ...`). Always use it instead of the global. During SSR it inherits the incoming request's cookies and headers for same-origin requests, can resolve relative URLs, and — crucially — calls to your *own* `+server.ts` endpoints go **directly to the handler function**, no actual HTTP round trip. Plus the response-inlining trick that saves universal loads from double-fetching during hydration only works through this `fetch`.

### 4.3 `load` Is a Dependency Graph, Not a Lifecycle Hook

The most productive mental model: each `load` function declares a node in a **data dependency graph**, and SvelteKit re-executes a node only when one of its tracked inputs changes. While your `load` runs, the framework records what it touched: `params.slug` if you read it, `url.searchParams` if you read those, the URLs you passed to `fetch`, any parent data you awaited via `parent()`, and any custom keys you registered with `depends('app:cart')`. On navigation, SvelteKit diffs — *did anything this load depends on change?* — and re-runs only the affected loads. Navigating from `/blog/foo` to `/blog/bar` re-runs the post load (its `params.slug` changed) but **not** the root layout's user load (nothing it depends on changed). This is why layout data is cheap and why putting shared data high in the tree is a performance strategy, not just an organizational one.

You drive the graph manually from the client with `invalidate(...)`:

```ts
import { invalidate, invalidateAll } from '$app/navigation';

await invalidate('app:cart');             // re-run loads that called depends('app:cart')
await invalidate('/api/items');           // re-run loads that fetched this URL
await invalidateAll();                    // re-run every load for the current page
```

This is SvelteKit's answer to cache invalidation for route data: after a WebSocket message says the cart changed, `invalidate('app:cart')` re-runs exactly the loads that declared that dependency. Conversely, `untrack(() => url.searchParams.get('page'))` reads an input *without* depending on it, when a rerun would be wrong. The corollary discipline: **`load` functions should be pure data declarations** — no side effects, no writing to stores or globals. A load that mutates state on the side will run at times you don't expect (prefetch on hover!) and break the graph's predictability ([state management docs](https://svelte.dev/docs/kit/state-management) are blunt about this; Part 7 returns to it).

### 4.4 Waterfalls, Parallelism, and Streaming

SvelteKit runs the `load` functions for a route's layouts and page **in parallel** — but you can accidentally serialize them. Two anti-patterns cause most slow pages. First, `await parent()` *before* your own work: if the page load awaits the layout's data and only then starts its own query, you've built a waterfall. Start your independent work first, await `parent()` last (or not at all). Second, sequential awaits for independent data:

```ts
// ❌ waterfall: post, then comments, then related — three round trips in series
const post = await db.getPost(params.slug);
const comments = await db.getComments(params.slug);

// ✅ parallel: one round-trip time for all of it
const [post, comments] = await Promise.all([
  db.getPost(params.slug),
  db.getComments(params.slug)
]);
```

For data that's genuinely slow and genuinely secondary, server loads support **streaming**: return a *nested, un-awaited* promise, and SvelteKit sends the page immediately, then streams the promise's resolution into the same response when it settles:

```ts
export const load: PageServerLoad = async ({ params }) => {
  return {
    post: await db.getPost(params.slug),       // awaited: blocks the page (critical)
    comments: db.getComments(params.slug)      // promise: streams in later (secondary)
  };
};
```

```svelte
{#await data.comments}
  <p>Loading comments…</p>
{:then comments}
  {#each comments as c}<Comment {c} />{/each}
{:catch}
  <p>Comments failed to load.</p>
{/await}
```

Only *nested* promises stream — top-level properties are awaited so the basic contract ("`data` is there when the page renders") holds. Streaming requires JavaScript on the client to stitch the late data in, so keep the critical content in the awaited part; and always attach a `catch` path, because a streamed rejection after the response begins can't become an error page anymore.

Errors and redirects in `load` use framework helpers that read like control flow: `error(404, 'Not found')` renders the nearest `+error.svelte` with that status (Part 6), and `redirect(303, '/login')` sends the user elsewhere — both *throw* internally, so code after them doesn't run, and you should not wrap them in `try/catch` blocks that would swallow them. A load should do exactly one of three things: return data, redirect deliberately, or throw an expected error ([errors](https://svelte.dev/docs/kit/errors), [redirects](https://svelte.dev/docs/kit/load#Redirects)).

**Practice:** build a blog index and post page with layout and page server loads, stream the comments with a nested promise and an `{#await}` block, and wire a refresh button to `invalidate('app:comments')`. Then watch the network tab while navigating between posts and verify which loads re-run and which don't — the dependency graph is much stickier once you've *seen* it.

---

## Part 5 — Mutations: Form Actions and API Endpoints

Reading data was Part 4; changing it is this part. SvelteKit's signature answer is the **form action** — and understanding why it's a `<form>` and not a `fetch('/api/...', { method: 'POST' })` is understanding the framework's soul. The browser already has a complete, accessible, battle-tested mutation mechanism: the HTML form. It works without JavaScript, it has built-in semantics for method and encoding, and users understand it. SvelteKit's posture — **progressive enhancement as the default** — is to make the no-JS version work first, then enhance it with JavaScript into a smooth single-page experience. You don't build two code paths; you build one that degrades gracefully, or rather *starts* gracefully and upgrades.

References: [Form actions](https://svelte.dev/docs/kit/form-actions), and Joy of Code's [Working with Forms in SvelteKit](https://joyofcode.xyz/working-with-forms-in-sveltekit) for a long-form walkthrough.

### 5.1 Actions: POST Handlers That Live with Their Page

An **action** is a server-side function, exported from `+page.server.ts`, that handles a form POST to that page. Here's a login page, end to end:

```ts
// src/routes/login/+page.server.ts
import { fail, redirect } from '@sveltejs/kit';
import { verifyCredentials, createSession } from '$lib/server/auth';
import type { Actions } from './$types';

export const actions: Actions = {
  default: async ({ request, cookies }) => {
    const form = await request.formData();
    const email = form.get('email') as string;
    const password = form.get('password') as string;

    if (!email || !email.includes('@')) {
      return fail(400, { email, error: 'A valid email is required' });
    }

    const user = await verifyCredentials(email, password);
    if (!user) {
      return fail(401, { email, error: 'Invalid email or password' });
    }

    cookies.set('session', await createSession(user.id), { path: '/' });
    redirect(303, '/dashboard');
  }
};
```

```svelte
<!-- src/routes/login/+page.svelte -->
<script lang="ts">
  import type { PageProps } from './$types';
  let { form }: PageProps = $props();
</script>

<form method="POST">
  {#if form?.error}<p class="error">{form.error}</p>{/if}
  <input name="email" type="email" value={form?.email ?? ''} required />
  <input name="password" type="password" required />
  <button>Log in</button>
</form>
```

Walk the failure path, because it's where the design shines. Validation fails → the action returns `fail(400, { email, error })` → SvelteKit re-renders the page, and the returned object appears as the **`form` prop**. The template repopulates the email field (`value={form?.email ?? ''}` — never echo the password back) and shows the error *next to the form that owns it*. This works **with JavaScript disabled**: it's a plain POST, a plain re-render, exactly like web frameworks circa 2005 — except typed, colocated with the page, and about to get enhanced. On success, `redirect(303, ...)` implements POST-redirect-GET, so refreshing the destination page never re-submits the mutation.

A page can have multiple **named actions** — `export const actions = { create: ..., delete: ... }` — targeted by the form's action attribute: `<form method="POST" action="?/delete">`. (Named and `default` can't be mixed on one page.) A button can override per-submit with `formaction="?/archive"`. This scales to real CRUD pages without inventing endpoint URLs for every operation.

### 5.2 `use:enhance` — the Upgrade Path

One attribute turns the full-page POST into a fetch-based submission that updates the page in place:

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  let submitting = $state(false);
</script>

<form
  method="POST"
  use:enhance={() => {
    submitting = true;
    return async ({ update }) => {
      submitting = false;
      await update();   // default behavior: apply result, invalidate data, reset form
    };
  }}
>
  <!-- fields -->
  <button disabled={submitting}>{submitting ? 'Saving…' : 'Save'}</button>
</form>
```

Bare `use:enhance` (no argument) emulates the no-JS behavior without the page reload: on success it updates the `form` prop, re-runs the page's `load` functions (`invalidateAll`), and resets the form; on `fail` it applies the validation data; on `redirect` it navigates client-side. The callback form shown above is the customization point — it runs on submit (set pending state, `cancel()` to abort, tweak `formData`) and returns a function that runs with the `result`. Reach for the callback when you need pending indicators, optimistic UI, or to *not* reset the form — but call `update()` (or `applyAction(result)`) unless you have a reason to replace the default behavior, because silently dropping redirects and errors is the classic mistake here.

The deeper lesson: notice how much you did **not** build. No client-side fetch wrapper, no JSON API for the form, no global mutation cache, no error-state plumbing — the platform's form semantics plus one action did all of it, and the page worked before the JavaScript arrived.

### 5.3 `+server.ts`: When You Actually Want an API

Sometimes the route *is* the API — there's no page, or the caller isn't your own form. A `+server.ts` file exports functions named after HTTP verbs, each taking a `RequestEvent` and returning a standard `Response`:

```ts
// src/routes/api/posts/+server.ts
import { json, error } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, setHeaders }) => {
  const limit = Number(url.searchParams.get('limit') ?? 20);
  const posts = await db.listPosts({ limit });
  setHeaders({ 'cache-control': 'public, max-age=60' });
  return json(posts);
};

export const POST: RequestHandler = async ({ request, locals }) => {
  if (!locals.user) error(401);
  const body = await request.json();
  const post = await db.createPost(locals.user.id, body);
  return json(post, { status: 201 });
};
```

This is the web platform with routing attached: real status codes, real headers, content negotiation if you want it. The decision rule between actions and endpoints is about **who the caller is**:

| Use a **form action** when… | Use a **`+server.ts` endpoint** when… |
|---|---|
| the mutation belongs to a page a user is on | the caller is *not* your page: webhooks (Stripe), mobile apps, other services |
| you want no-JS fallback and `form`-prop validation UX for free | the response isn't HTML-page-shaped: JSON feeds, RSS, file downloads, redirects-as-API |
| the data is `FormData` (including file uploads) | you're polling or calling from client-side code outside a form |
| you want automatic `load` invalidation after success via `enhance` | you need verbs beyond POST (PUT/PATCH/DELETE semantics for an API surface) |

The common beginner inversion — building `/api/*` JSON endpoints and `fetch`ing them from components for ordinary page mutations — costs you progressive enhancement, typed `form` results, and automatic invalidation, and gains you nothing. Default to actions for your own pages; endpoints for everyone else.

For completeness: SvelteKit is incubating **remote functions** (`.remote.ts` files exporting `query`, `form`, `command`, `prerender` wrappers) — type-safe RPC from components to server-only functions. They're experimental and opt-in as of mid-2026; worth [reading about](https://svelte.dev/docs/kit/remote-functions) to see where the framework is heading, not yet baseline knowledge to build on.

**Practice:** build a CRUD admin page with named actions (`?/create`, `?/update`, `?/delete`), `fail`-based validation that repopulates fields, and `use:enhance` pending states on every button. Then disable JavaScript in dev tools and verify every flow still completes — that test is the whole philosophy of this part in one keystroke.

---

## Part 6 — Hooks, Server-Only Modules, and Auth

Parts 4 and 5 handled individual routes. This part is about the machinery that wraps *every* request — middleware, the hard server/client wall, secrets, sessions, and what happens when things go wrong. This is where SvelteKit most resembles a backend framework, and where backend instincts (see the [Auth guide](AUTH_STUDY_GUIDE.md)) transfer directly.

### 6.1 `handle`: Every Request Flows Through One Function

`src/hooks.server.ts` can export a `handle` function that wraps every server request — pages, `load` calls from client navigation, endpoints, form actions, everything. It's SvelteKit's middleware, and its canonical job is turning an opaque cookie into a typed, request-scoped identity:

```ts
// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit';
import { getSessionUser } from '$lib/server/auth';

export const handle: Handle = async ({ event, resolve }) => {
  const sessionId = event.cookies.get('session');
  event.locals.user = sessionId ? await getSessionUser(sessionId) : null;

  if (event.url.pathname.startsWith('/admin') && event.locals.user?.role !== 'admin') {
    return new Response('Forbidden', { status: 403 });
  }

  return resolve(event); // render the route; you can also transform the Response after
};
```

Two ideas to anchor. First, **`event.locals` is the request-scoped briefcase**: anything you attach in `handle` is available to every server `load`, action, and endpoint for *this request only* — the safe home for "who is making this request" in a server that's concurrently serving many users. Type it once in `app.d.ts` (`interface Locals { user: User | null }`) and the whole codebase gets autocomplete. Second, `handle` composes: the `sequence` helper from `@sveltejs/kit/hooks` chains multiple handlers like any middleware stack, which keeps each concern small and testable:

```ts
import { sequence } from '@sveltejs/kit/hooks';
export const handle = sequence(requestLogging, auth, securityHeaders);
```

The other server hooks earn their keep later but should be on your map: **`handleFetch`** intercepts `fetch` calls made from server-side `load` functions — the place to rewrite internal service URLs or attach service-to-service credentials; **`handleError`** is called for *unexpected* errors — the place to report to Sentry/your [observability stack](OBSERVABILITY_STUDY_GUIDE.md) and to shape the sanitized message users see; **`init`** runs once at server startup (database connection setup). The universal hooks file `src/hooks.ts` hosts **`reroute`** (rewrite URL → route resolution, e.g. for i18n domains) and **`transport`** (teach SvelteKit to serialize your custom classes across the server/client boundary — directly extending the devalue story from Part 4).

References: [Hooks](https://svelte.dev/docs/kit/hooks), [Auth](https://svelte.dev/docs/kit/auth).

### 6.2 `$lib/server` and Environment Variables: Structural Guarantees, Not Discipline

In a codebase where server and client code interleave file-by-file, "I'm pretty sure this only runs on the server" is not a security model. SvelteKit gives you **structural** guarantees instead. Any module in `src/lib/server/` (or named `*.server.ts`) is a **server-only module**: importing it from anything that could reach the browser — a component, a universal `load`, anything in their import chains — is a *build error*, with the full import chain printed. Your database client, payment SDK wrappers, and session crypto live there, and the leak becomes impossible rather than unlikely ([server-only modules](https://svelte.dev/docs/kit/server-only-modules)).

Environment variables get the same treatment, split along two axes — private/public and static/dynamic:

```ts
import { DATABASE_URL } from '$env/static/private';   // secret, inlined at build time
import { env } from '$env/dynamic/private';            // secret, read at runtime (env.DATABASE_URL)
import { PUBLIC_API_BASE } from '$env/static/public';  // safe for the client; must be PUBLIC_-prefixed
```

The private modules are themselves server-only — importing them client-side fails the build. **Static** values are inlined at build time (enabling dead-code elimination, but baking the value into the artifact); **dynamic** values are read when the server starts, which is what you want when one built image runs in several environments. Only variables prefixed `PUBLIC_` are *allowed* into the public modules, so a secret can't drift into the client bundle by renaming alone ([$env docs](https://svelte.dev/docs/kit/$env-static-private)).

### 6.3 Sessions, Cookies, and Where Authorization Lives

SvelteKit doesn't ship an auth system; it ships the right primitives and an [opinionated docs page](https://svelte.dev/docs/kit/auth). The shape that fits the framework best is **cookie-based sessions**: a login form action verifies credentials (Part 5's example), stores a session record server-side, and sets an `httpOnly` cookie via `cookies.set('session', token, { path: '/' })` — SvelteKit's `cookies` API defaults to `httpOnly`, `secure`, and `sameSite: 'lax'`, which is the configuration you'd have to remember by hand elsewhere. The `handle` hook resolves the cookie to a user on every request and parks it in `locals`, and from then on identity is just `locals.user`.

The rule that prevents real vulnerabilities: **authorization happens at server boundaries, every time.** Checking `data.user` in a component hides a button; it does not protect anything — the client is the other side of the trust boundary. Every server `load`, action, and endpoint that touches protected data re-checks `locals.user` (or relies on a `handle`-level guard for its path, as in 6.1). A subtle trap worth knowing: protecting only a `+layout.server.ts` load does *not* automatically protect child pages — a page's server load can be invoked directly on client-side navigation without the layout rerunning, so guard the pages (or `handle`), not just the layout. If you'd rather adopt a maintained library than hand-roll session plumbing, `npx sv add better-auth` wires up [Better Auth](https://svelte.dev/docs/cli/better-auth) with first-party CLI support — a reasonable modern default, and the concepts above still apply verbatim.

### 6.4 Errors: Expected, Unexpected, and Where They Surface

SvelteKit splits errors into two species, and the split is load-bearing. **Expected errors** are ones you throw deliberately with the `error` helper — `error(404, 'Post not found')` — and they are *control flow*: SvelteKit renders the nearest `+error.svelte` up the route tree with the status and message you provided, and the message is shown to users as-is. **Unexpected errors** are everything else — a thrown `TypeError`, a dead database. SvelteKit assumes their messages may contain sensitive internals, so users see a generic `{ message: 'Internal Error' }` while the real error goes to `handleError` for logging. You customize the error UI with `+error.svelte` files at whatever granularity the product needs:

```svelte
<!-- src/routes/blog/+error.svelte -->
<script lang="ts">
  import { page } from '$app/state';
</script>

<h1>{page.status}</h1>
<p>{page.error?.message}</p>
```

Error boundaries nest like layouts: an error in `/blog/[slug]`'s load renders `blog/+error.svelte` if present, else the root `+error.svelte`; errors in the root layout fall back to the static `error.html` shell. If you want structured error objects (codes, tracking IDs), extend the `App.Error` interface in `app.d.ts` and SvelteKit will hold you to the shape. For *component-level* failures (as opposed to route-level), Svelte 5 added [`<svelte:boundary>`](https://svelte.dev/docs/svelte/svelte-boundary) — an in-tree error boundary with a `failed` snippet — useful around risky widgets so one crash doesn't blank the page.

References: [Errors](https://svelte.dev/docs/kit/errors).

**Practice:** build a protected account area end to end: resolve the user in `handle`, type `locals` in `app.d.ts`, guard the `(app)` group by route ID, render a custom `+error.svelte` for missing resources, keep the database client in `$lib/server`, and then *try* to import it from a component to watch the build refuse. Confidence in the wall comes from testing the wall.

---

## Part 7 — State Management Without Foot-Guns

State management questions in SvelteKit are really *placement* questions, and the framework gives you more places than a pure SPA does: the database (via `load`), the URL, request-scoped `locals`, component state, context, and module-scoped client state. Most architectural mess in SvelteKit apps comes from putting state one layer further from its source of truth than it needs to be — usually by reflexively reaching for a global store. This part is a placement guide, plus the one genuinely dangerous trap.

References: [State management](https://svelte.dev/docs/kit/state-management) — short, blunt, and worth reading in full.

### 7.1 The Placement Ladder

Work down this ladder and stop at the first rung that fits:

1. **Server-derived data stays in `load`.** If the source of truth is the database, don't mirror it into a client store "for convenience" — you now own cache invalidation by hand. Render from `data`, and refresh it with `invalidate` (Part 4) or automatically via form actions + `enhance` (Part 5). The framework *is* your data layer.
2. **Shareable UI state belongs in the URL.** Filters, tabs, sort order, pagination, search text — if a user would expect a refresh, a shared link, or the back button to preserve it, encode it in `url.searchParams`, read it in `load`, and change it by navigating (a `<a href="?sort=date">` link or `goto`). It's refresh-proof, shareable, and crawlable for free.
3. **Ephemeral DOM state that should survive back/forward** — half-typed inputs, scroll positions — uses **snapshots** (Part 3.3), not global state.
4. **Component state is the default for everything else.** Plain `$state` in the component that owns it. Local state is easy to reason about, test, and delete.
5. **Subtree state uses context.** A wizard, an editor pane, a compound component — `setContext` a reactive object at the root of the feature.
6. **Genuinely global client state** — theme, WebSocket connection status, an audio player — gets a shared `.svelte.ts` module (or a store; both work, runes are the modern idiom):

```ts
// src/lib/client/theme.svelte.ts
export const theme = $state({ mode: 'dark' as 'dark' | 'light' });
export function toggleTheme() {
  theme.mode = theme.mode === 'dark' ? 'light' : 'dark';
}
```

Note the shape: we export an *object* whose properties mutate, plus functions — a module can't meaningfully export a rebound `let`, so "state object + mutators" is the idiomatic pattern for shared rune state.

### 7.2 The SSR Trap: Module Scope Is Shared Between Users

Here is the foot-gun the part title promises, and it's worth slowing down for. On the client, a module-scoped variable belongs to one user — their tab, their session. **On the server, module scope is shared by every request the process serves.** This pattern is a data leak:

```ts
// ❌ NEVER: src/lib/server/current.ts
export let currentUser: User | null = null;  // set in load, read "later"
```

Two users hit the server concurrently; user B's `load` overwrites `currentUser` between user A's write and read, and user A renders user B's account. No error, no warning — just the wrong person's data, intermittently, under load. The same applies to caching per-user data in a module-level `Map`, or writing user data into a shared store during SSR. The rules that keep you safe: **per-request state lives in `event.locals`** (created fresh per request, dies with it); **server `load` returns data instead of stashing it anywhere**; and authenticated caching, if you need it, keys by user and lives in real infrastructure ([Redis](REDIS_STUDY_GUIDE.md)), not module scope. Relatedly, keep `load` functions side-effect free (Part 4.3) — during SSR a side effect runs on the server where no per-user "global" exists to receive it correctly.

For framework-provided reactive state, modern code imports from **`$app/state`** — `page` (current URL, params, `data`, `error`), `navigating`, and `updated` as fine-grained reactive objects: `page.url.searchParams.get('q')` just works in any component. Older codebases use `$app/stores` (`$page` with the store prefix); read both fluently, write the former ([$app/state docs](https://svelte.dev/docs/kit/$app-state)).

### 7.3 UX Patterns on Top of Correct Placement

With state placed correctly, the classic UX patterns become small. **Pending feedback**: every mutation needs visible acknowledgment — a `submitting` flag in the `enhance` callback (Part 5.2) or the global `navigating` object from `$app/state` for route transitions. **Optimistic UI**: apply the expected result immediately and reconcile when the action settles — Svelte 5's overridable `$derived` (Part 2.3) is purpose-built for this, since reality reasserts itself on the next dependency change; use optimism only where rollback is rare and legible. **Flash messages and layout chrome** belong in layouts, fed by layout `load` or context. **Draft persistence** is a lifetime question: keystrokes-level recovery → snapshots; survive a tab close → `localStorage` (in an effect, browser-only); survive a device change → a real server draft via a form action. Choosing the persistence boundary *is* the design decision; the code is a few lines either way.

**Practice:** build a searchable admin list where filters and pagination live entirely in the URL, an edit drawer rides on shallow routing, half-typed input survives back navigation via snapshots, and the theme lives in a shared `.svelte.ts` module. Then deliberately write the module-scope user bug from 7.2 in a dev server and hit it from two browsers at once — seeing the leak once inoculates you forever.

---

## Part 8 — Rendering Strategies: SSR, CSR, and Prerendering

SvelteKit's default — SSR for the first visit, CSR afterward — is right for most pages, but it is a *default*, not a commitment. Page options let you choose a rendering strategy **per route**, and the highest-leverage architectural skill in SvelteKit is making that choice at the smallest sensible boundary instead of app-wide. The options are plain exports from a page or layout's `load` file (layout options cascade to children; pages can override):

```ts
// any +page.ts / +page.server.ts / +layout.ts …
export const prerender = true;   // render to static HTML at BUILD time
export const ssr = true;         // render HTML on the server per REQUEST (default)
export const csr = true;         // ship JS and hydrate in the browser (default)
```

References: [Page options](https://svelte.dev/docs/kit/page-options).

### 8.1 The Three Dials, and What They Trade

**`prerender = true`** moves rendering to build time: the route's `load` runs *once at build*, the resulting HTML is written to disk, and every visitor gets the same file — servable from a CDN, effectively infinitely scalable, zero server compute per request. The eligibility rule follows directly: any two users must get the same content, and the page can't depend on request-time inputs (no `cookies`, no per-user data, form actions can't target it). Content sites, marketing pages, docs, and blog posts are the natural fits; SvelteKit discovers prerenderable dynamic routes (`/blog/[slug]`) by crawling links from your entry pages, and you can supplement with an `entries` export when pages aren't linked. The cost: content updates require a rebuild.

**`ssr = false`** skips server rendering: the server sends an empty shell, and everything renders in the browser. You lose the fast first paint, the no-JS fallback, and SEO-friendly HTML — so the legitimate uses are narrow: pages that *cannot* render on the server (heavy dependence on `window`, browser-only libraries) or genuinely private app surfaces where first-paint SEO is irrelevant. The docs' own warning is worth repeating: turning SSR off app-wide turns your transitional app back into the SPA the framework was designed to improve on ([single-page apps](https://svelte.dev/docs/kit/single-page-apps) — possible via `ssr = false` in the root layout plus a fallback page on `adapter-static`, but a last resort, not a style choice).

**`csr = false`** is the mirror image: no JavaScript is shipped for the route at all. Pure HTML out, nothing to hydrate — for genuinely static content (a terms-of-service page, a blog post with no interactivity) this is the lightest possible page. Links still work (they're links!); you give up client-side routing *onto* enhanced behavior within the page.

| Strategy | Rendered | Per-request server work | First paint | SEO | Personalization | Typical routes |
|---|---|---|---|---|---|---|
| Prerender | build time | none (static file/CDN) | fastest | excellent | none | marketing, docs, blog |
| SSR (default) | per request | full render | fast | excellent | full | dashboards, feeds, anything user-specific |
| CSR-only (`ssr=false`) | in browser | minimal | slowest (blank until JS) | poor | full (after load) | browser-API-bound tools, embedded admin |
| Static + no JS (`prerender` + `csr=false`) | build time | none | fastest | excellent | none | legal pages, plain articles |

The skill is mixing them: in one app, `(marketing)/` group prerendered with `csr = false` where pages are inert, the `(app)/` group SSR'd with full hydration, and one canvas-heavy tool with `ssr = false`. Route groups (Part 3.2) exist precisely so these decisions land on clean boundaries. Set URL policy (`trailingSlash`) deliberately too — it affects relative path resolution, what filenames prerendering writes (`about.html` vs `about/index.html`), and duplicate-content SEO.

### 8.2 How to Decide, Quickly

Three questions per route. *Is the content identical for every visitor?* If yes and it changes only on deploy, prerender it. *Does the first paint matter to someone who isn't logged in yet — a crawler, a link preview, a first-time visitor?* If yes, keep SSR on. *Does the page meaningfully exist without JavaScript?* If it's all canvas/WebGL or device APIs, `ssr = false` and accept the trade; if it's fully inert, consider `csr = false` and ship nothing. When in doubt, the default (SSR + CSR) is never *wrong* — it's the other modes that need justification. Note that these dials also constrain deployment: a fully prerendered app can use `adapter-static` and a CDN, while anything with SSR or actions needs a runtime — which is exactly the adapter decision of Part 11.

**Practice:** take one small app and ship it twice — fully prerendered, then SSR — and write down what changed in the build output. Add one browser-only tool page with `ssr = false` and one inert legal page with `csr = false`, and justify each route's strategy in a sentence. If you can't, the default was right.

---

## Part 9 — Performance, Images, and SEO

SvelteKit starts you unusually far ahead: compiled components with no framework runtime tax, automatic per-route code-splitting, SSR for fast first paint, link preloading for fast navigation. The performance discipline is therefore less "add optimizations" and more **"don't squander the defaults"** — and know where the real costs hide, which in full-stack apps is usually the data layer and the images, not the JavaScript.

References: [Performance](https://svelte.dev/docs/kit/performance), [Images](https://svelte.dev/docs/kit/images), [SEO](https://svelte.dev/docs/kit/seo), [Accessibility](https://svelte.dev/docs/kit/accessibility).

### 9.1 Diagnose Before Optimizing

Build the measurement habit first: Lighthouse (or [PageSpeed Insights](https://pagespeed.web.dev/) against the deployed site) for Core Web Vitals, the Network tab with throttling to see what a real first visit loads, and the framework's own signals — slow `load` functions show up plainly in server timing. Most SvelteKit performance problems fall into three buckets, in descending order of frequency:

**Waterfalls** — dependency chains where independent requests run in series. You met the `load`-level cures in Part 4.4 (`Promise.all`, late `parent()`, streaming for secondary data); the same pathology appears at other layers. A *client-server* waterfall: a component that `fetch`es in `onMount`, then fetches again based on the result — each round trip a full network hop; the fix is almost always moving the logic into a server `load` where the hops happen datacenter-side, microseconds apart. A *database* waterfall: an ORM lazily loading relations per row (the N+1 problem — see the [Postgres guide](POSTGRES.md)); the fix is a join or batched query in `$lib/server`, invisible to SvelteKit but dominant in route latency.

**Payload** — too much JavaScript or data. Code-splitting is automatic per route, but a heavy library imported in a layout lands in every page's critical path; import heavy, rarely-used dependencies dynamically (`const { Chart } = await import('chart.js')` inside the handler or effect that needs them). On the data side, `load` should return what the page renders, not whole database rows — over-fetching inflates both the server query and the serialized payload embedded in the HTML.

**Navigation feel** — already mostly solved by preloading (Part 3.3); confirm `data-sveltekit-preload-data` is set, and for the few links where eagerness is wrong (logout, expensive pages), opt out per-link with `data-sveltekit-preload-data="false"`.

### 9.2 Images: The Biggest Bytes on the Page

Images routinely outweigh all code combined, so treat them as a first-class concern. For assets you own, Vite already fingerprints and inlines small files imported from `src`. The official `@sveltejs/enhanced-img` plugin goes much further with one attribute change:

```svelte
<enhanced:img src="./hero.png" alt="Dashboard overview" />
```

At build time this generates modern formats (AVIF/WebP with fallbacks), a `srcset` of responsive widths, and intrinsic `width`/`height` so the layout doesn't shift while loading — the three things that move Largest Contentful Paint and Cumulative Layout Shift, done for you. It only works for build-time-known assets; for user-uploaded or CMS images, the same goals are met with a CDN that transforms on the fly (Cloudinary, imgix, Cloudflare Images — see the [Cloudflare guide](CLOUDFLARE_STUDY_GUIDE.md)), plus `loading="lazy"` on below-the-fold images and explicit dimensions everywhere. The [images docs](https://svelte.dev/docs/kit/images) cover both halves of this split well.

### 9.3 Accessibility: The Framework Helps, the Structure Decides

SvelteKit handles the two accessibility problems client-side routing *creates*: on navigation it announces the new page to screen readers (via an injected live region — which is why every page should have a unique `<title>`, the text that gets announced) and manages focus sensibly. The compiler handles a third class: static a11y violations are build-time warnings (Part 2.6). What's left is structural and yours: **semantic HTML first** (a `<button>`, not a div with a click handler — Svelte never hides the platform, so your HTML choices are the accessibility ceiling); **focus management at state transitions** — dialogs trap and return focus, form errors move focus to the first invalid field, custom navigation calls `goto` so the framework's announcement machinery runs; and the `lang` attribute set correctly in `app.html` (trivial, often missed, and it changes how screen readers pronounce everything). Accessibility bugs are usually state-transition bugs in disguise — test the moments where the UI *changes*, not just its resting states.

### 9.4 SEO: Mostly Free, If You Don't Turn It Off

SvelteKit's SEO story is largely "SSR is on by default; keep it on" — crawlers get real HTML with real content, no JS execution required ([SEO docs](https://svelte.dev/docs/kit/seo)). What remains is per-page metadata and site plumbing. Metadata belongs to the route that owns it, via `<svelte:head>` fed by `load` data:

```svelte
<svelte:head>
  <title>{data.post.title} — My Blog</title>
  <meta name="description" content={data.post.summary} />
  <meta property="og:title" content={data.post.title} />
  <meta property="og:image" content={data.post.coverUrl} />
</svelte:head>
```

A useful pattern for defaults-with-overrides: the layout sets baseline tags, pages override — or layout `load` returns title fields that one `<svelte:head>` in the layout renders, keeping the format consistent. Site plumbing fits SvelteKit's primitives exactly: a sitemap is a `+server.ts` returning XML at `/sitemap.xml`; an RSS feed likewise; canonical URLs come from a deliberate `trailingSlash` policy (Part 8) plus a `<link rel="canonical">` derived from `page.url`. And performance *is* ranking: Core Web Vitals feed search placement, so sections 9.1–9.2 are SEO work too.

**Practice:** optimize a content page until it's boring: `enhanced:img` for the hero, complete `<svelte:head>` metadata, one waterfall removed with `Promise.all`, a heavy charting library moved behind a dynamic import, and a clean `sv check` accessibility report. Measure with Lighthouse before and after — the numbers are the lesson.

---

## Part 10 — Testing and Quality

A SvelteKit app spans the server/client boundary, so a single kind of test can't cover it. The strategy that works is a layered one, where each layer catches the bug class it's cheapest at, and the layers map cleanly onto the architecture you've built through Parts 2–6:

| Layer | Tool | What it covers | Cost |
|---|---|---|---|
| Static | `sv check` + TypeScript + ESLint | type drift, a11y warnings, dead code | ~free, run constantly |
| Unit | Vitest | pure logic, `$lib` helpers, `.svelte.ts` reactive modules | very cheap |
| Component | Vitest + browser mode / Testing Library | rendered behavior, props, interactions | cheap |
| Server | Vitest | `load` functions, actions, endpoints as functions | cheap |
| End-to-end | Playwright | full routes: SSR → hydrate → navigate → submit | expensive, high confidence |

References: [Testing (Svelte docs)](https://svelte.dev/docs/svelte/testing), [Vitest](https://vitest.dev/), [Playwright](https://playwright.dev/), and the `sv add vitest playwright` add-ons that wire both into a fresh project.

### 10.1 Static Analysis Is the First Test Suite

`sv check` (Part 1.2) type-checks your components *including templates* — a misspelled prop, a `data` field that no longer exists, an unhandled `form` shape — plus the compiler's accessibility warnings. Because SvelteKit generates `$types` for every route, the type checker is effectively an integration test of your server/client contracts: change a `load` return shape and every component that renders the old shape lights up. This is the highest-leverage quality habit in the ecosystem: keep `sv check` clean locally and gate CI on it.

### 10.2 Unit and Component Tests with Vitest

SvelteKit projects are Vite projects, so [Vitest](https://vitest.dev/) is the native test runner. The cheapest, most durable tests live *below* the component layer: formatters, validation, business rules in `$lib` — plain functions, plain tests. One Svelte-specific wrinkle: testing reactive `.svelte.ts` modules requires understanding that effects and derived updates are batched. Wrap reactive interactions in `flushSync` (or run assertions inside `$effect.root`) so updates apply before you assert:

```ts
// counter.svelte.test.ts
import { flushSync } from 'svelte';
import { counter, increment } from './counter.svelte.js';

test('increments', () => {
  flushSync(() => increment());
  expect(counter.value).toBe(1);
});
```

For component tests, the modern recommendation is **Vitest browser mode** with `vitest-browser-svelte` (real browser, real events — what `sv add vitest` scaffolds today), with jsdom + `@testing-library/svelte` as the established lighter-weight alternative. Either way, test the **user contract** — what renders, what happens on click, what's accessible by role — not implementation details like internal state names, which the compiler is free to optimize away. Server code needs no special machinery at all: a `load` function or action is just an async function; call it with a stubbed event object and assert on the result:

```ts
// login.actions.test.ts — exercising Part 5.1's action directly
import { actions } from './+page.server';

test('rejects a malformed email with a 400 and repopulates the field', async () => {
  const request = new Request('http://localhost/login', {
    method: 'POST',
    body: new URLSearchParams({ email: 'not-an-email', password: 'x' })
  });

  const result = await actions.default({ request, cookies: stubCookies() } as any);

  expect(result.status).toBe(400);
  expect(result.data).toEqual({ email: 'not-an-email', error: 'A valid email is required' });
});
```

This is where redirect logic, `fail` shapes, and authorization guards get cheap, exhaustive coverage — every validation branch as a fast unit test, with Playwright reserved for proving the happy path end to end.

### 10.3 End-to-End Tests with Playwright

Only a browser test exercises the actual product: server render → hydration → client navigation → form submission → redirect. [Playwright](https://playwright.dev/) (scaffolded by `sv add playwright`) builds and serves your app, then drives a real browser:

```ts
import { test, expect } from '@playwright/test';

test('user can log in and reach the dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill('correct-horse');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL('/dashboard');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
```

Note the selectors: `getByRole`, `getByLabel` — accessibility-first queries that double as a11y assertions (if Playwright can't find the button by role, neither can a screen reader). Two SvelteKit-specific tricks: run a critical flow with `javaScriptEnabled: false` to *prove* your progressive enhancement story (Part 5) actually holds, and keep E2E focused on the handful of journeys whose breakage is unacceptable — login, checkout, create/edit — because browser tests are slow and flaky in proportion to their number, and the layers below have already covered the branches. A reasonable CI pipeline orders the layers by speed: lint + `sv check` → unit/component → build → Playwright (see the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md)).

**Practice:** unit-test a formatter and a reactive `.svelte.ts` module (you'll need `flushSync`), component-test the login form by role and label, call a form action directly with a stubbed event to cover its `fail` branches, and write one Playwright journey — login through dashboard — that runs twice, once with `javaScriptEnabled: false`.

---

## Part 11 — Adapters, Building, and Deployment

A SvelteKit app is not, by itself, a deployable artifact — it's a description of a server and a client. **Adapters** are the last step of the build: they take SvelteKit's platform-neutral output and *adapt* it to a concrete runtime — a Node server, a pile of static files, a Vercel deployment, a Cloudflare Worker. This design is why "where will this run?" can be a late, cheap decision in SvelteKit instead of an early, expensive one: the application code you wrote in Parts 3–7 doesn't change; only one line of config does.

References: [Building your app](https://svelte.dev/docs/kit/building-your-app), [Adapters](https://svelte.dev/docs/kit/adapters).

### 11.1 What `npm run build` Actually Does

The build has two stages. First, **Vite builds** an optimized version of both programs: the server code (your `load` functions, actions, endpoints, and components-as-SSR-renderers) and the client code (hydration bundles, split per route), and **prerenders** any routes marked `prerender` by running them at build time. Second, the **adapter** packages that output for its target. Two practical consequences. Your code *executes during the build* — module top-levels are imported for analysis and prerendering runs real `load` functions — so anything that must not run at build time (a database connection, say) needs a guard: the `building` flag from `$app/environment` exists for exactly this. And because dev (`vite dev`) and production builds differ meaningfully, **always check `npm run preview`** — which serves the real build locally — before shipping; it catches the classic "works in dev, fails in prod" class (build-time env inlining, prerender errors, server-only import leaks) while you can still fix them quietly.

### 11.2 Choosing an Adapter

The adapter is one line in `svelte.config.js`:

```js
// svelte.config.js
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ out: 'build' })
  }
};
```

New projects scaffold with `adapter-auto`, which detects Vercel/Netlify/Cloudflare at deploy time and installs the right adapter — fine for getting started, but pin the real adapter once you've chosen a platform (you get its config options, and your build stops depending on environment detection). The choice itself is about three things: **does the app need a server at all**, **what runtime constraints can your code tolerate**, and **who you want operating it**:

| Adapter | Target | Runtime | Best when | Watch out for |
|---|---|---|---|---|
| `adapter-node` | a long-running Node server | full Node.js | you run your own infra (VM, [Docker](DOCKER_STUDY_GUIDE.md), k8s); WebSockets/long-lived work alongside the app; maximum control | you own scaling, TLS, and ops; set `ORIGIN` and trust-proxy env correctly behind a reverse proxy |
| `adapter-vercel` | Vercel serverless / edge functions | Node (serverless) or edge runtime | zero-ops deploys, preview deployments per PR, ISR | per-function limits; edge runtime is *not* Node (no native modules); platform pricing at scale |
| `adapter-cloudflare` | Cloudflare Workers | V8 isolates (not Node) | edge latency worldwide; pairing with KV/D1/R2/Durable Objects (see the [Cloudflare guide](CLOUDFLARE_STUDY_GUIDE.md)) | no Node APIs unless polyfilled via `nodejs_compat`; many npm packages (database drivers especially) won't run; CPU-time limits |
| `adapter-netlify` | Netlify functions/edge | Node or Deno-based edge | already on Netlify | same serverless trade-offs as Vercel |
| `adapter-static` | plain files | none | **every** route is prerendered (or SPA-fallback mode) | no SSR, no form actions, no server endpoints at request time — the build fails if a route needs a server, which is a feature |

The decision usually falls out of Part 8's rendering choices. All-prerenderable content site → `adapter-static`, host anywhere, nothing to operate. Classic full-stack app and you're comfortable operating services → `adapter-node` in a container is the boring, flexible choice: the build output is a standalone Node server (`node build`), configured by environment (`PORT`, `ORIGIN` — the public URL, required for forms and redirects to resolve correctly behind proxies). Want the platform to own ops, previews, and scaling → Vercel/Netlify. Latency-sensitive and globally distributed, with data on the same edge platform → Cloudflare, *if* your dependencies survive the non-Node runtime — check that constraint before committing, not after. Whatever you pick, the `read` function from `$app/server` and platform-specific `event.platform` give you escape hatches into the runtime's native capabilities.

### 11.3 CI/CD and Running in Production

The pipeline writes itself from the layers you already have: `npm ci` → lint/format check → `sv check` → unit tests → `npm run build` → Playwright against the preview → deploy ([GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md)). Keep secrets in the platform's secret store, never the repo, and remember the static/dynamic env split from Part 6.2: `$env/static/*` values are baked in *at build time*, so building once and promoting the same artifact through staging and production requires `$env/dynamic/*` for anything that differs between them. Preview deployments (first-class on Vercel/Netlify/Cloudflare) are disproportionately valuable for SvelteKit apps because they exercise SSR, redirects, and metadata in near-production conditions — things `vite dev` approximates loosely.

Two production capabilities round out the platform story. **Observability**: SvelteKit has first-class instrumentation support — server spans for `handle`, `load`, and actions can be exported via OpenTelemetry (see [observability docs](https://svelte.dev/docs/kit/observability) and this repo's [Observability guide](OBSERVABILITY_STUDY_GUIDE.md)); at minimum, wire `handleError` (Part 6.1) to an error tracker with request context, and watch route-level latency, not just frontend vitals — in a full-stack framework, a slow page is usually a slow `load`. **Service workers**: drop a `src/service-worker.ts` in the project and SvelteKit registers it automatically, exposing the build manifest through the `$service-worker` module so you can precache the app shell and assets for offline resilience ([service workers docs](https://svelte.dev/docs/kit/service-workers)). It's powerful and operationally sharp-edged (cache invalidation now ships to clients); adopt it when the product genuinely benefits — installable apps, flaky-network audiences — not by default.

**Practice:** build the production artifact and run `npm run preview`; then containerize the `adapter-node` output (see the [Docker guide](DOCKER_STUDY_GUIDE.md)) and run it with `ORIGIN` and `PORT` set explicitly; then switch the same app to `adapter-static` and read the build error that tells you exactly which routes still need a server. That error message is Part 8 and Part 11 agreeing with each other.

---

## Part 12 — The Ecosystem and Where to Go Next

### 12.1 The Blessed Stack: `sv add` as a Map of the Ecosystem

The `sv add` registry doubles as a curated map of what the Svelte team considers production-ready, and learning the ecosystem through it keeps you aligned with current expectations instead of three-year-old tutorials. The add-ons worth knowing beyond the tooling ones from Part 1: **`tailwindcss`** — ubiquitous in SvelteKit codebases; even committed plain-CSS users (and Svelte's scoped styles make plain CSS unusually pleasant) need to *read* Tailwind fluently. **`drizzle`** — a TypeScript-first ORM whose setup lands exactly where Part 6 says it should: client in `$lib/server/db`, schema as code, types flowing into your `load` returns ([Drizzle ORM](https://orm.drizzle.team/)). **`better-auth`** — the session machinery of Part 6.3 as a maintained library. **`mdsvex`** — Markdown with Svelte components inside, the Svelte-native engine for blogs and docs sites ([mdsvex](https://mdsvex.pngwn.io/)). **`paraglide`** — compile-time i18n that integrates with routing, the current official path for internationalization ([Paraglide](https://inlang.com/m/gerre34r/library-inlang-paraglideJs)). **`storybook`** — isolated component workshops; not mandatory for product apps, near-mandatory for design systems, and most valuable when stories pin down the annoying states: empty, loading, error, overflow ([Storybook for SvelteKit](https://storybook.js.org/docs/get-started/frameworks/sveltekit)).

One more capability hides in plain sight: SvelteKit also builds **libraries**. In a library project, `src/lib` is the public surface and `src/routes` becomes your development showcase; `@sveltejs/package` (`svelte-package`) emits distributable components with generated types. Publishing correctness is mostly `package.json` metadata — `exports` conditions, the `svelte` field, `sideEffects` — rather than component code ([packaging docs](https://svelte.dev/docs/kit/packaging)). Even if you never publish to npm, this is how shared internal UI packages should be shaped.

### 12.2 Reading Legacy Code: Svelte 3/4 in the Wild

Most production Svelte code predates runes, and "job-ready" includes reading it without flinching. The translations are mechanical:

| Svelte 3/4 (legacy) | Svelte 5 (runes) |
|---|---|
| `export let title;` | `let { title } = $props();` |
| `let count = 0;` (implicitly reactive) | `let count = $state(0);` |
| `$: doubled = count * 2;` | `let doubled = $derived(count * 2);` |
| `$: { console.log(count); }` | `$effect(() => { console.log(count); });` |
| `on:click={fn}` | `onclick={fn}` |
| `createEventDispatcher()` + `on:save` | callback prop: `onsave` |
| `<slot />`, `<slot name="x" />` | `{@render children()}`, named snippets |
| `$store` auto-subscription | still works; new shared state uses `.svelte.ts` runes |

Seen side by side, the dialect shift is smaller than it sounds — here is the same component in both eras:

```svelte
<!-- Svelte 4 -->                          <!-- Svelte 5 -->
<script>                                   <script>
  export let initial = 0;                    let { initial = 0, onchange } = $props();
  import { createEventDispatcher }           let count = $state(initial);
    from 'svelte';                           let doubled = $derived(count * 2);
  const dispatch = createEventDispatcher();
  let count = initial;                       function bump() {
  $: doubled = count * 2;                      count++;
  function bump() {                            onchange?.(count);
    count++;                                 }
    dispatch('change', count);             </script>
  }
</script>                                  <button onclick={bump}>
<button on:click={bump}>                     {count} ({doubled})
  {count} ({doubled})                      </button>
</button>
```

The legacy reactive statement `$:` is the one that punishes skimming: it conflates derived values and effects in one syntax, and its dependencies are whatever the *statement* references at compile time — the source of most legacy Svelte bugs, and precisely the ambiguity `$derived`/`$effect` were designed to split apart. When you migrate, `npx sv migrate svelte-5` automates the bulk mechanically, and runes-mode components interoperate with legacy-mode components in one app, so migration is incremental by design — the practical question is "which components this quarter," not "rewrite or not." Read the [v5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide) even if you never migrate anything: it's the framework authors' own annotated list of which changes matter and why.

### 12.3 Capstone Projects

Reading builds familiarity; only building builds judgment. These three projects are sequenced so each forces the parts of the guide the previous one didn't.

**Project 1 — a content platform** (blog or docs site). Prerendered marketing and article pages (`prerender`, Part 8), `[slug]` routes loading mdsvex content, per-page metadata via `<svelte:head>` (Part 9.4), `@sveltejs/enhanced-img` for cover images, search and tag filters living in the URL (Part 7.1), and an RSS feed from a `+server.ts` (Part 5.3). Deploy it twice — once with `adapter-static` to a CDN, once with `adapter-node` — and write down what changed and why. This project makes rendering strategy and the filesystem router concrete.

**Project 2 — a SaaS admin dashboard.** Session auth resolved in `handle` and carried in `locals` (Part 6), route groups separating the public shell from the protected app shell with a `+page@` login escape (Part 3.2), filterable data tables with URL state, CRUD via named form actions with `fail` validation and `use:enhance` pending states (Part 5), streamed secondary panels (Part 4.4), `+error.svelte` boundaries, Vitest on the actions and Playwright on login + one full CRUD journey (Part 10) — including the no-JS run. This project *is* the server/client boundary, exercised end to end.

**Project 3 — a collaborative knowledge base.** Role-based authorization at every server boundary, a command palette and keyboard navigation (focus management under pressure — Part 9.3), optimistic edits with overridable deriveds (Parts 2.3, 7.3), draft recovery via snapshots and server drafts, real-time presence over WebSockets (`adapter-node` so the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) applies) driving `invalidate` for live data, and OpenTelemetry traces on slow loads (Part 11.3). This is the project where the parts stop being chapters and start being one system.

### 12.4 How to Study This

A closing method, since order matters more than effort here. **Do the official [tutorial](https://svelte.dev/tutorial) first** — both halves, Svelte then SvelteKit; it's interactive, current, and faster than any video course. **Learn Svelte 5 idioms natively** and treat legacy syntax as a reading skill (12.2), not a habit. **Keep the boundary question alive**: for every file you create, say out loud where it runs and when — the habit from Part 1 is the actual skill, and every confusing bug in your first months will trace back to getting it wrong. **Let the platform work**: links before `goto`, forms before `fetch`, URL before store, server load before client cache. **Run `sv check` constantly** and treat warnings as design feedback. And **read real code**: the [SvelteKit repo](https://github.com/sveltejs/kit) itself, Joy of Code's project walkthroughs, and Svelte Society's recipes — production repos are mixed-era, opinionated, and the fastest route from "I know the docs" to "I know the framework."

---

## Part 13 — Recipes: Eight Patterns That Tie It Together

Everything so far taught concepts in isolation; real features cut across them. Each recipe below is a complete, idiomatic implementation of a pattern you will build in every serious SvelteKit app, annotated with *which* concepts it composes and *why* the code is shaped the way it is. Treat them as kata: type them out, break them, and re-derive them from the parts.

### 13.1 Protecting a Route Group Behind Login

The pieces: route groups (Part 3.2), `handle` and `locals` (Part 6.1), and the rule that authorization lives at server boundaries (Part 6.3). The structure puts every protected page under one group:

```
src/routes/
├── (public)/
│   ├── +page.svelte              → /
│   └── login/
│       ├── +page.svelte          → /login
│       └── +page.server.ts       → the login action from Part 5.1
└── (app)/
    ├── +layout.svelte            → app shell: sidebar, user menu
    ├── dashboard/+page.svelte    → /dashboard
    └── settings/+page.svelte     → /settings
```

The guard goes in `hooks.server.ts`, keyed on the **route ID** — which includes the group name even though the URL doesn't, giving you one airtight check for the whole subtree instead of a per-page guard someone will eventually forget:

```ts
// src/hooks.server.ts
import { redirect, type Handle } from '@sveltejs/kit';
import { getSessionUser } from '$lib/server/auth';

export const handle: Handle = async ({ event, resolve }) => {
  const sessionId = event.cookies.get('session');
  event.locals.user = sessionId ? await getSessionUser(sessionId) : null;

  if (event.route.id?.startsWith('/(app)') && !event.locals.user) {
    // remember where they were going, so login can send them back
    redirect(303, `/login?redirectTo=${encodeURIComponent(event.url.pathname)}`);
  }

  return resolve(event);
};
```

And the login action completes the round trip:

```ts
// src/routes/(public)/login/+page.server.ts (success path)
const redirectTo = url.searchParams.get('redirectTo') ?? '/dashboard';
// validate it's a local path — never redirect to attacker-supplied absolute URLs
redirect(303, redirectTo.startsWith('/') && !redirectTo.startsWith('//') ? redirectTo : '/dashboard');
```

Why this shape: the check runs *before* any `load` in the group executes, it covers direct page-data requests during client navigation (the layout-only-guard trap from Part 6.3 can't bite), and the open-redirect validation on `redirectTo` is the one security detail every login flow must get right. The `(app)` layout can now assume `locals.user` exists, and its `+layout.server.ts` can simply `return { user: locals.user }` to give every protected page typed access to the identity.

### 13.2 A Theme Toggle Without the Flash

Dark-mode toggles are a perfect boundary exercise: the theme must be known *during SSR* (or the first paint flashes the wrong colors), must persist, and must toggle without a reload. The trick is a cookie — readable on the server, unlike `localStorage` — stamped into the HTML before it leaves:

```html
<!-- src/app.html -->
<html lang="en" data-theme="%theme%">
```

```ts
// src/hooks.server.ts (composed with the auth handle via sequence())
const theme: Handle = async ({ event, resolve }) => {
  const current = event.cookies.get('theme') === 'light' ? 'light' : 'dark';
  return resolve(event, {
    transformPageChunk: ({ html }) => html.replace('%theme%', current)
  });
};
```

`transformPageChunk` is `resolve`'s hook for rewriting the outgoing HTML — here, substituting our placeholder so the very first byte of markup already carries `data-theme="dark"`, and CSS variables keyed off that attribute paint correctly with zero JavaScript. Toggling is a form action, because mutations are form actions (Part 5):

```ts
// src/routes/theme/+page.server.ts
import type { Actions } from './$types';

export const actions: Actions = {
  default: async ({ cookies, request }) => {
    const next = (await request.formData()).get('theme') === 'light' ? 'light' : 'dark';
    cookies.set('theme', next, { path: '/', maxAge: 60 * 60 * 24 * 365 });
  }
};
```

```svelte
<!-- in the layout: works without JS (full-page POST), smooth with it -->
<form method="POST" action="/theme" use:enhance={() => {
  document.documentElement.dataset.theme = nextTheme; // optimistic flip, no waiting
  return async ({ update }) => update({ invalidateAll: false });
}}>
  <input type="hidden" name="theme" value={nextTheme} />
  <button>Switch to {nextTheme} mode</button>
</form>
```

Note the `enhance` customization: we flip the attribute optimistically (the cookie write can't meaningfully fail) and skip `invalidateAll` because no `load` data depends on the theme. Every layer of this recipe is the progressive-enhancement posture in miniature.

### 13.3 Filterable, Paginated Lists with URL State

The pieces: URL as state home (Part 7.1), `load` dependency tracking (Part 4.3), and links as the navigation API (Part 3.3). The entire feature has no client state at all:

```ts
// src/routes/products/+page.server.ts
import { db } from '$lib/server/db';
import type { PageServerLoad } from './$types';

const PER_PAGE = 20;

export const load: PageServerLoad = async ({ url }) => {
  const page = Math.max(1, Number(url.searchParams.get('page') ?? 1) || 1);
  const q = url.searchParams.get('q') ?? '';
  const category = url.searchParams.get('category') ?? undefined;

  const { items, total } = await db.searchProducts({
    q, category, limit: PER_PAGE, offset: (page - 1) * PER_PAGE
  });

  return { items, total, page, q, category, pages: Math.ceil(total / PER_PAGE) };
};
```

Because the `load` *reads* `url.searchParams`, SvelteKit tracks the URL as a dependency — any navigation that changes the query string re-runs exactly this load. So the UI is just links and one GET form:

```svelte
<script lang="ts">
  import type { PageProps } from './$types';
  let { data }: PageProps = $props();
</script>

<!-- a GET form IS a search UI: submits to the same page as ?q=… -->
<form data-sveltekit-keepfocus>
  <input name="q" value={data.q} placeholder="Search products…" />
  <button>Search</button>
</form>

{#each data.items as item}<ProductCard {item} />{/each}

<nav>
  {#each Array(data.pages) as _, i}
    <a href="?q={data.q}&page={i + 1}" aria-current={data.page === i + 1 ? 'page' : undefined}>
      {i + 1}
    </a>
  {/each}
</nav>
```

Mutations are GET navigations, so back/forward, refresh, and shared links all reproduce the exact view — for free. For search-as-you-type, replace the form submit with a debounced `goto` that preserves the same architecture:

```ts
import { goto } from '$app/navigation';

let timeout: ReturnType<typeof setTimeout>;
function onInput(q: string) {
  clearTimeout(timeout);
  timeout = setTimeout(() => {
    goto(`?q=${encodeURIComponent(q)}`, { keepFocus: true, replaceState: true, noScroll: true });
  }, 300);
}
```

`keepFocus` keeps the cursor in the input, `replaceState` avoids polluting history with every keystroke, and the server `load` keeps doing all the real work. The page still functions with JavaScript disabled, because the plain form never went away.

### 13.4 File Uploads Through a Form Action

Uploads exercise `FormData` (Part 1.3's web standards), action validation (Part 5.1), and the `$lib/server` boundary. The form needs one attribute browsers have honored for decades:

```svelte
<form method="POST" enctype="multipart/form-data" use:enhance>
  <input type="file" name="avatar" accept="image/png, image/jpeg" required />
  <button>Upload</button>
  {#if form?.error}<p class="error">{form.error}</p>{/if}
</form>
```

```ts
// +page.server.ts
import { fail } from '@sveltejs/kit';
import { saveAvatar } from '$lib/server/storage';
import type { Actions } from './$types';

const MAX_BYTES = 2 * 1024 * 1024;
const ALLOWED = new Set(['image/png', 'image/jpeg']);

export const actions: Actions = {
  default: async ({ request, locals }) => {
    const file = (await request.formData()).get('avatar');

    if (!(file instanceof File) || file.size === 0) {
      return fail(400, { error: 'Please choose a file.' });
    }
    if (file.size > MAX_BYTES) {
      return fail(400, { error: 'Maximum size is 2 MB.' });
    }
    if (!ALLOWED.has(file.type)) {
      return fail(400, { error: 'Only PNG and JPEG are allowed.' });
    }

    await saveAvatar(locals.user!.id, file); // streams to disk/S3/R2 inside $lib/server
    return { success: true };
  }
};
```

The value arrives as a standard `File` object — no multipart-parsing middleware, because the platform's `FormData` already did it. The validation order is deliberate (cheapest checks first), the client-side `accept` is UX rather than security (re-validated on the server, where `file.type` itself is still client-supplied — sniff magic bytes if it matters), and storage lives behind `$lib/server` so credentials never approach the client bundle. For big files, remember the body transits your server; beyond tens of megabytes, the better architecture is a presigned upload URL from an action or endpoint, with the browser uploading directly to object storage.

### 13.5 Live Data: `invalidate` as the Refresh Primitive

The pieces: custom dependencies (`depends`, Part 4.3) and effects (Part 2.4). The pattern: loads declare a named dependency; anything — a timer, a WebSocket message, a visibility change — can re-run them by invalidating the name. The data path stays identical to first render, so there's no second "update" code path to maintain:

```ts
// src/routes/(app)/dashboard/+page.server.ts
export const load: PageServerLoad = async ({ depends, locals }) => {
  depends('app:metrics');
  return { metrics: await getMetrics(locals.user!.id) };
};
```

```svelte
<script lang="ts">
  import { invalidate } from '$app/navigation';

  $effect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') invalidate('app:metrics');
    }, 15_000);
    return () => clearInterval(id);
  });
</script>
```

The effect is the right home (browser-only, auto-cleaned-up on navigation away), the visibility check stops background tabs from hammering the server, and swapping the timer for a WebSocket (`socket.onmessage = () => invalidate('app:metrics')` — see the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md)) upgrades polling to push without touching the load, the page, or the types. This is the payoff of treating `load` as a declarative dependency graph: "refresh" is just "mark dirty."

### 13.6 A Modal with a Real URL (Shallow Routing)

The pieces: shallow routing and `preloadData` (Part 3.3), `$app/state` (Part 7.2). The goal: clicking a photo in a grid opens a modal *and* pushes `/photos/123`, so back closes the modal, and a hard refresh (or a shared link) lands on the full photo page. The grid page intercepts clicks, preloads the target route's data, and pushes state instead of navigating:

```svelte
<script lang="ts">
  import { preloadData, pushState, goto } from '$app/navigation';
  import { page } from '$app/state';
  import PhotoModal from './PhotoModal.svelte';

  async function openPhoto(e: MouseEvent, href: string) {
    if (e.metaKey || e.ctrlKey || innerWidth < 640) return; // let real navigation win
    e.preventDefault();

    const result = await preloadData(href);        // runs the photo route's load
    if (result.type === 'loaded' && result.status === 200) {
      pushState(href, { photo: result.data });     // URL changes; no navigation
    } else {
      goto(href);                                  // fall back to real navigation
    }
  }
</script>

{#each data.photos as photo}
  <a href="/photos/{photo.id}" onclick={(e) => openPhoto(e, `/photos/${photo.id}`)}>
    <img src={photo.thumb} alt={photo.alt} />
  </a>
{/each}

{#if page.state.photo}
  <PhotoModal photo={page.state.photo} onclose={() => history.back()} />
{/if}
```

Every fallback in this snippet is deliberate: modified clicks and small screens get the real page, a failed preload gets a real navigation, no-JS users have a plain `<a>` the whole time, and closing is `history.back()` so the browser's back button and the close button are the same gesture. The modal's data came from the *same* `load` function the standalone page uses — one source of truth, two presentations. This recipe is the "transitional app" thesis from Part 1 compressed into forty lines.

### 13.7 Optimistic UI on Top of `use:enhance`

The pieces: `use:enhance` customization (Part 5.2), `$state` and `$derived` (Part 2), and the optimism guidance from Part 7.3. The honest version of optimistic UI keeps two sources separate — the server's list (from `load`) and the client's in-flight hopes — and *derives* the rendered list from both, instead of mutating server data it doesn't own:

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let pending = $state<string[]>([]);             // texts we've sent but not confirmed
  let visible = $derived([
    ...data.todos,
    ...pending.map((text) => ({ id: `pending-${text}`, text, done: false, saving: true }))
  ]);
</script>

<ul>
  {#each visible as todo (todo.id)}
    <li class:saving={'saving' in todo}>{todo.text}</li>
  {/each}
</ul>

<form
  method="POST"
  action="?/add"
  use:enhance={({ formData, formElement }) => {
    const text = String(formData.get('text'));
    pending.push(text);                            // appears in the list immediately
    formElement.reset();

    return async ({ result, update }) => {
      await update();                              // success: load re-runs, data.todos
      pending = pending.filter((t) => t !== text); // has the real row — retract the ghost
      if (result.type === 'failure') {
        // the retraction above already rolled back; now surface the error
        formElement.querySelector('input')?.focus();
      }
    };
  }}
>
  <input name="text" required placeholder="Add a todo…" />
  <button>Add</button>
</form>
```

The sequencing in the result callback is the whole trick: `update()` re-runs the page's `load` *first*, so the confirmed row from the database is already in `data.todos` when the optimistic ghost is removed — no flicker, no gap. On `fail`, the same retraction *is* the rollback, because the server's list never contained the item. The keyed `{#each}` (`(todo.id)`) matters too: it lets Svelte match the ghost and the confirmed row to distinct DOM nodes, so transitions and focus behave. Reach for this pattern when mutations are fast and rarely fail; when failure is common or consequential, an explicit pending indicator (Part 7.3) is kinder than optimism.

### 13.8 Endpoints That Aren't JSON: RSS and CSV

`+server.ts` returns a `Response`, and a `Response` can be anything (Part 5.3) — which makes feeds, exports, and downloads almost suspiciously small. An RSS feed is a *prerenderable endpoint*, because it's identical for every visitor (Part 8.1):

```ts
// src/routes/rss.xml/+server.ts
import { getPosts } from '$lib/server/content';
import type { RequestHandler } from './$types';

export const prerender = true;   // generated at build time, served as a static file

export const GET: RequestHandler = async () => {
  const posts = await getPosts();
  const items = posts.map((p) => `
    <item>
      <title><![CDATA[${p.title}]]></title>
      <link>https://example.com/blog/${p.slug}</link>
      <pubDate>${p.publishedAt.toUTCString()}</pubDate>
    </item>`).join('');

  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>
     <rss version="2.0"><channel><title>My Blog</title>${items}</channel></rss>`,
    { headers: { 'Content-Type': 'application/xml' } }
  );
};
```

A CSV export is the per-user, request-time mirror image — never prerenderable, gated by `locals`, and delivered as a download via `Content-Disposition`:

```ts
// src/routes/(app)/reports/export/+server.ts
import { error } from '@sveltejs/kit';
import { getRows } from '$lib/server/reports';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ locals, url }) => {
  if (!locals.user) error(401);

  const rows = await getRows(locals.user.id, url.searchParams.get('month'));
  const csv = ['date,amount,category']
    .concat(rows.map((r) => `${r.date},${r.amount},"${r.category.replaceAll('"', '""')}"`))
    .join('\n');

  return new Response(csv, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': 'attachment; filename="report.csv"'
    }
  });
};
```

The link in the UI is just `<a href="/reports/export?month=2026-05" data-sveltekit-reload>Download CSV</a>` — an anchor, not a fetch-and-blob dance. The browser handles the download natively, it works without JavaScript, and the auth check rides on the session cookie like every other request (`data-sveltekit-reload` tells the client router not to treat it as an in-app navigation). For exports too large to assemble in memory, return a `ReadableStream` as the body and emit rows as you fetch them — the `Response` contract doesn't change, which is the web-standards bet of Part 1.3 paying off one last time.

---

## Appendix — Reference Links

The links woven through the guide, collected for review. Official **Svelte** (the language): [overview](https://svelte.dev/docs/svelte/overview) · [what are runes?](https://svelte.dev/docs/svelte/what-are-runes) · [`$state`](https://svelte.dev/docs/svelte/$state) · [`$derived`](https://svelte.dev/docs/svelte/$derived) · [`$effect`](https://svelte.dev/docs/svelte/$effect) · [`$props`](https://svelte.dev/docs/svelte/$props) · [snippets](https://svelte.dev/docs/svelte/snippet) · [context](https://svelte.dev/docs/svelte/context) · [stores](https://svelte.dev/docs/svelte/stores) · [lifecycle hooks](https://svelte.dev/docs/svelte/lifecycle-hooks) · [testing](https://svelte.dev/docs/svelte/testing) · [v5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide) · [legacy overview](https://svelte.dev/docs/svelte/legacy-overview).

Official **SvelteKit**: [introduction](https://svelte.dev/docs/kit/introduction) · [project structure](https://svelte.dev/docs/kit/project-structure) · [web standards](https://svelte.dev/docs/kit/web-standards) · [routing](https://svelte.dev/docs/kit/routing) · [advanced routing](https://svelte.dev/docs/kit/advanced-routing) · [loading data](https://svelte.dev/docs/kit/load) · [form actions](https://svelte.dev/docs/kit/form-actions) · [page options](https://svelte.dev/docs/kit/page-options) · [hooks](https://svelte.dev/docs/kit/hooks) · [server-only modules](https://svelte.dev/docs/kit/server-only-modules) · [state management](https://svelte.dev/docs/kit/state-management) · [errors](https://svelte.dev/docs/kit/errors) · [auth](https://svelte.dev/docs/kit/auth) · [performance](https://svelte.dev/docs/kit/performance) · [images](https://svelte.dev/docs/kit/images) · [accessibility](https://svelte.dev/docs/kit/accessibility) · [SEO](https://svelte.dev/docs/kit/seo) · [adapters](https://svelte.dev/docs/kit/adapters) · [building your app](https://svelte.dev/docs/kit/building-your-app) · [service workers](https://svelte.dev/docs/kit/service-workers) · [observability](https://svelte.dev/docs/kit/observability) · [packaging](https://svelte.dev/docs/kit/packaging) · [remote functions](https://svelte.dev/docs/kit/remote-functions).

**CLI**: [`sv create`](https://svelte.dev/docs/cli/sv-create) · [`sv add`](https://svelte.dev/docs/cli/sv-add) · [`sv check`](https://svelte.dev/docs/cli/sv-check) · [`sv migrate`](https://svelte.dev/docs/cli/sv-migrate). **Third-party**: [interactive tutorial](https://svelte.dev/tutorial) · [Joy of Code](https://joyofcode.xyz/) · [Svelte Society](https://sveltesociety.dev/) · [Rethinking Reactivity (Rich Harris)](https://www.youtube.com/watch?v=AdNJ3fydeao) · [Have SPAs Ruined the Web? (Rich Harris)](https://www.youtube.com/watch?v=860d8usGC0o) · [Vite](https://vite.dev/guide/) · [Vitest](https://vitest.dev/) · [Playwright](https://playwright.dev/) · [Drizzle ORM](https://orm.drizzle.team/) · [mdsvex](https://mdsvex.pngwn.io/) · [Tailwind CSS](https://tailwindcss.com/docs/installation). **Web platform** (SvelteKit uses these directly — Part 1.3): MDN's [Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API), [Request](https://developer.mozilla.org/en-US/docs/Web/API/Request)/[Response](https://developer.mozilla.org/en-US/docs/Web/API/Response), [FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData), [URL](https://developer.mozilla.org/en-US/docs/Web/API/URL), and [Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie).

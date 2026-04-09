# SvelteKit Mastery Study Guide

A comprehensive, job-focused guide to mastering SvelteKit with modern Svelte 5 patterns. Each section builds on the previous one. Build real features, not toy examples.

---

## Phase 1: Core Foundations

### 1.1 Project Setup & Tooling

- **`npx sv create`**: The official way to scaffold a new SvelteKit app
  - Start from the current Svelte defaults instead of reconstructing tooling later; docs: [Creating a project](https://svelte.dev/docs/kit/creating-a-project), [`sv create`](https://svelte.dev/docs/cli/sv-create).
- **Project structure conventions**:
  - Learn the default layout early so server-only code, shared components, and route code do not blur together as the app grows; docs: [Project structure](https://svelte.dev/docs/kit/project-structure).
  ```
  src/
    lib/             # Shared components, utils, and app code
    lib/server/      # Server-only modules
    params/          # Param matchers
    routes/          # File-based routes
    app.html         # HTML shell
    error.html       # Fallback HTML for catastrophic errors
    hooks.client.ts  # Optional client hooks
    hooks.server.ts  # Optional server hooks
    service-worker.ts
  static/            # Unprocessed static assets
  tests/             # Playwright and other tests
  svelte.config.js
  tsconfig.json
  vite.config.ts
  ```
- **TypeScript**: Use it from day one
  - TypeScript pays off especially in route `load` data, form payloads, `PageData` shapes, and shared server/client contracts; docs: [TypeScript](https://svelte.dev/docs/svelte/typescript).
- **VS Code + Svelte extension**: The best default editor setup
  - Good editor support matters more in Svelte than in many frameworks because compile-time diagnostics are part of the developer experience; docs: [Creating a project](https://svelte.dev/docs/kit/creating-a-project).
- **`sv add eslint prettier`**: Add linting and formatting through the official CLI
  - Prefer the official add-ons so config stays aligned with the ecosystem defaults; docs: [`sv add`](https://svelte.dev/docs/cli/sv-add), [`eslint` add-on](https://svelte.dev/docs/cli/eslint), [`prettier` add-on](https://svelte.dev/docs/cli/prettier).
- **`sv check`**: Treat this like a first-class quality gate, not an optional extra
  - It catches Svelte compiler warnings, accessibility hints, and TypeScript issues in one pass; docs: [`sv check`](https://svelte.dev/docs/cli/sv-check).
- **Vite**: Know what SvelteKit delegates to the build tool
  - Understanding Vite helps you debug aliases, environment modes, test config, and production build behavior without guessing; docs: [Vite Guide](https://vite.dev/guide/).
- **Web standards**: SvelteKit leans on platform APIs rather than inventing replacements
  - Learn `Request`, `Response`, `fetch`, `FormData`, `URL`, cookies, and streams because SvelteKit uses the web platform directly; docs: [Web standards](https://svelte.dev/docs/kit/web-standards).

**Practice**: Scaffold a new app with TypeScript, ESLint, Prettier, and Vitest. Explain what every top-level file does before you write any feature code.

---

### 1.2 Svelte Component Fundamentals

- **Anatomy of a `.svelte` file**: Script, markup, and styles in one component file
  - Svelte components are intentionally small units of UI plus behavior, so learn to treat the file as a cohesive module rather than a template shell; docs: [.svelte files](https://svelte.dev/docs/svelte/svelte-files).
- **`$state`**: Local reactive state
  - This is the modern default for mutable component state in Svelte 5 and should feel natural before you reach for stores; docs: [`$state`](https://svelte.dev/docs/svelte/$state).
- **`$derived`**: Computed values
  - Use derived state for values that should be recalculated from other state instead of manually syncing multiple variables; docs: [`$derived`](https://svelte.dev/docs/svelte/$derived).
- **`$effect`**: Side effects that react to state changes
  - Keep effects small and purposeful, especially when they touch timers, browser APIs, or network state; docs: [`$effect`](https://svelte.dev/docs/svelte/$effect).
- **`$props`** and **`$bindable`**: Component inputs and two-way bindings
  - Learn these as part of your component API design rather than as syntax trivia; docs: [`$props`](https://svelte.dev/docs/svelte/$props), [`$bindable`](https://svelte.dev/docs/svelte/$bindable).
- **Template syntax**: Basic markup, event attributes, and expressions
  - Keep template expressions readable and move heavy logic into derived state or helper functions; docs: [Basic markup](https://svelte.dev/docs/svelte/basic-markup).
- **Control flow blocks**: `{#if}`, `{#each}`, `{#await}`, `{#key}`
  - These are the backbone of most Svelte rendering work, so you should be fluent enough to use them without pausing to remember syntax; docs: [{#if ...}](https://svelte.dev/docs/svelte/if), [{#each ...}](https://svelte.dev/docs/svelte/each), [{#await ...}](https://svelte.dev/docs/svelte/await).
- **`bind:`**: Prefer explicit bindings when the DOM should own a value temporarily
  - Bindings are powerful, but good Svelte code still keeps ownership of state clear; docs: [bind:](https://svelte.dev/docs/svelte/bind).
- **`<svelte:head>`**: Page metadata belongs close to the route or layout that owns it
  - This becomes central once you start caring about SEO, social previews, and canonical metadata; docs: [`<svelte:head>`](https://svelte.dev/docs/svelte/svelte-head).

**Practice**: Build a small filterable list component using `$state`, `$derived`, `{#if}`, `{#each}`, and `bind:`. Then refactor it into parent/child components using `$props`.

---

### 1.3 Runtime Primitives & Reuse

- **Runes mental model**: In Svelte 5, reactivity is more fine-grained than component-wide lifecycle thinking
  - Internalize that Svelte reacts to effects and dependencies, not whole-component re-renders in the React sense; docs: [What are runes?](https://svelte.dev/docs/svelte/what-are-runes), [Lifecycle hooks](https://svelte.dev/docs/svelte/lifecycle-hooks).
- **Stores**: `writable`, `readable`, `derived`, `readonly`
  - Stores are still important, but they are no longer the default answer to every shared-state problem in Svelte 5; docs: [Stores](https://svelte.dev/docs/svelte/stores).
- **When to use stores**: Reach for them when state must live outside a single component instance or be manually subscribed to
  - If plain `$state` inside a component or context is enough, prefer the simpler tool; docs: [Stores](https://svelte.dev/docs/svelte/stores).
- **Context**: Shared state or services for a subtree
  - Context is ideal for compound components, localized shared state, and dependency injection without prop drilling; docs: [Context](https://svelte.dev/docs/svelte/context).
- **Lifecycle hooks**: `onMount`, `onDestroy`, `tick`
  - The important skill is not memorizing hooks, but knowing when you truly need DOM timing or cleanup rather than pure reactive logic; docs: [Lifecycle hooks](https://svelte.dev/docs/svelte/lifecycle-hooks).
- **Actions with `use:`**: Encapsulate DOM behavior cleanly
  - Actions are a great way to wrap imperative browser logic like click-outside, focus traps, or third-party widgets; docs: [use:](https://svelte.dev/docs/svelte/use).
- **Transitions and animation**: `transition:`, `in:`, `out:`, `animate:`
  - Learn these well enough to add motion that communicates state changes instead of merely decorating them; docs: [transition:](https://svelte.dev/docs/svelte/transition).
- **Snippets and `@render`**: Modern composition patterns in Svelte 5
  - These matter because job-ready Svelte now includes reading code that moved beyond legacy slots; docs: [{#snippet ...}](https://svelte.dev/docs/svelte/snippet).
- **Legacy syntax awareness**: Older codebases still use `export let`, `$:`, and `<slot>`
  - You do not need to prefer legacy mode, but you absolutely need to read it comfortably in the wild; docs: [Legacy overview](https://svelte.dev/docs/svelte/legacy-overview), [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide).

**Practice**: Build a headless dropdown that uses context for shared state, an action for click-outside behavior, and a transition for open/close.

---

### 1.4 Styling & Accessibility

- **Scoped styles**: Component-local CSS is the default
  - This keeps styles close to markup and removes a lot of naming-convention overhead; docs: [Scoped styles](https://svelte.dev/docs/svelte/scoped-styles).
- **Global styles and `:global(...)`**: Use intentionally
  - Global rules are sometimes necessary for resets, typography, or theming, but they should feel deliberate, not accidental; docs: [Global styles](https://svelte.dev/docs/svelte/global-styles).
- **Custom properties**: Prefer CSS variables for theme tokens and component contracts
  - Variables are often a cleaner boundary than deeply nested prop-driven style options; docs: [Custom properties](https://svelte.dev/docs/svelte/custom-properties).
- **`class` and `style` directives**: Keep dynamic styling readable
  - A small amount of inline dynamic styling is fine, but large style decisions usually belong in CSS classes and tokens; docs: [class](https://svelte.dev/docs/svelte/class), [Basic markup](https://svelte.dev/docs/svelte/basic-markup).
- **Compile-time accessibility checks**: Take warnings seriously
  - Svelte catches many common accessibility issues before runtime, which is a huge advantage if you build the habit of fixing warnings early; docs: [Accessibility](https://svelte.dev/docs/kit/accessibility), [`sv check`](https://svelte.dev/docs/cli/sv-check).
- **Semantic HTML first**: Native elements are usually the right abstraction
  - Svelte does not hide the platform from you, so accessibility quality depends heavily on your HTML choices.
- **Focus management**: A core skill for dialogs, drawers, command palettes, and route transitions
  - Accessibility breaks fastest around focus, not around typography or color; docs: [Accessibility](https://svelte.dev/docs/kit/accessibility).

**Practice**: Build an accessible modal with keyboard support, focus return, and route-safe styling. Run `sv check` until all accessibility warnings are resolved intentionally.

---

## Phase 2: Routing, Layouts, and Navigation

### 2.1 File-Based Routing

- **`src/routes` is the router**: Directories become URL paths
  - File-based routing is one of SvelteKit's biggest productivity wins, so make route ownership obvious in your folder structure; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Route files**: Learn the role of `+page.svelte`, `+layout.svelte`, `+error.svelte`, `+page.ts`, `+page.server.ts`, `+layout.ts`, `+layout.server.ts`, and `+server.ts`
  - Good SvelteKit architecture depends on choosing the right file for rendering, loading, or request handling; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **`$types`**: Use generated types instead of hand-rolling route contracts
  - This is one of the easiest ways to keep route code honest as data and params evolve; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Dynamic params**: `[slug]`, `[id]`, and multi-segment route trees
  - Think about params as part of your public API because they shape links, SEO, and cache behavior; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Param matchers**: Validate route segments at the router boundary
  - Matchers help you keep obviously invalid URLs from flowing deeper into app logic; docs: [Project structure](https://svelte.dev/docs/kit/project-structure), [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).
- **Server routes with `+server.ts`**: Not every route needs a page component
  - Some URLs should return JSON, files, redirects, or custom responses instead of HTML; docs: [Routing](https://svelte.dev/docs/kit/routing).

---

### 2.2 Advanced Routing & Layouts

- **Rest parameters**: `[...rest]`
  - Use these when the URL structure is intentionally open-ended, such as documentation trees or file explorers; docs: [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).
- **Optional parameters**: Keep route design expressive without exploding the folder tree
  - Optional segments are useful, but overly clever routing often becomes harder to reason about than explicit paths; docs: [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).
- **Route groups**: `(group)` directories for organization without affecting the URL
  - Groups are one of the cleanest ways to align file structure with product areas or layout boundaries; docs: [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).
- **Breaking out of layouts**: `+page@` and `+layout@`
  - Learn this early because real apps often need an auth screen or admin screen that should not inherit the normal shell; docs: [Advanced routing](https://svelte.dev/docs/kit/advanced-routing).
- **Nested layouts**: Use layouts to share UI chrome and data, not to hide complexity indiscriminately
  - Layouts are most effective when they map to genuine product structure like account areas, docs shells, or dashboards; docs: [Routing](https://svelte.dev/docs/kit/routing).

---

### 2.3 Navigation & the Client Router

- **Client-side navigation after the first render**: SSR first, router takeover after hydration
  - This server-first mental model is what separates SvelteKit from client-only SPA thinking; docs: [Page options](https://svelte.dev/docs/kit/page-options).
- **Normal links first**: Let `<a>` do the job unless you truly need programmatic navigation
  - SvelteKit enhances regular web navigation rather than replacing it with framework-only primitives.
- **Preloading**: Understand how SvelteKit reduces perceived latency on navigation
  - Preloading is one of the fastest wins for route transitions and should be part of your performance vocabulary; docs: [Performance](https://svelte.dev/docs/kit/performance).
- **Programmatic navigation**: `goto`, invalidation, and history manipulation
  - Use imperative navigation sparingly and keep it tied to real UX events like auth redirects or multi-step flows; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Shallow routing**: Create history entries without full navigation
  - This is especially useful for modals, drawers, and mobile-friendly back-button behavior; docs: [Shallow routing](https://svelte.dev/docs/kit/shallow-routing).
- **Snapshots**: Preserve ephemeral DOM state across navigation
  - Snapshots are ideal for in-progress form inputs, scroll positions, and similar temporary UI state; docs: [Snapshots](https://svelte.dev/docs/kit/snapshots).

---

### 2.4 Page Options & Rendering Modes

- **`prerender`**: Turn routes into static output when possible
  - Prerendering is one of SvelteKit's strongest deployment and performance tools, especially for content-heavy pages; docs: [Page options](https://svelte.dev/docs/kit/page-options).
- **`ssr`** and **`csr`**: Control where rendering happens
  - These flags are powerful precisely because they let you mix rendering strategies, but they also make it easier to create confusing boundaries if used casually; docs: [Page options](https://svelte.dev/docs/kit/page-options).
- **`trailingSlash`** and route config choices
  - URL policy should be decided intentionally because it affects SEO, deployment rewrites, and link consistency; docs: [Page options](https://svelte.dev/docs/kit/page-options).
- **SPA mode**: Understand the tradeoffs before turning SSR off broadly
  - SvelteKit's own docs strongly caution that SPA mode hurts performance, SEO, and resilience unless you have a good reason; docs: [Single-page apps](https://svelte.dev/docs/kit/single-page-apps).
- **Rendering strategy per route**: Do not make the whole app dynamic just because one page needs it
  - The highest-leverage SvelteKit skill is choosing rendering mode at the smallest sensible boundary.

**Practice**: Build a small docs site with a public marketing shell, a separate authenticated app shell, dynamic blog routes, and a modal powered by shallow routing.

---

## Phase 3: Data Loading, Mutations, and Forms

### 3.1 `load` Functions

- **Page data and layout data**: Know what belongs at each layer
  - Layout loads are for shared route-level data; page loads are for page-specific needs; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Universal vs server `load`**:
  - Universal `load` can run on server and client, while server `load` is server-only. Choosing correctly is a core SvelteKit skill, not an implementation detail; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Route inputs**: `params`, `url`, `route`
  - Route inputs are part of the public contract of a page, so your data logic should treat them as first-class dependencies; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Using `fetch` in `load`**: Prefer the provided fetch so cookies and SSR behavior stay coherent
  - This matters especially when calling your own endpoints or services during SSR; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Parent data**: Compose route data deliberately
  - Parent data is what lets nested layouts feel ergonomic instead of repetitive; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Errors and redirects**: Fail fast with framework-native helpers
  - A route should either return the data it needs, redirect intentionally, or throw an expected error; docs: [Loading data](https://svelte.dev/docs/kit/load), [Errors](https://svelte.dev/docs/kit/errors).
- **Streaming with promises** and **parallel loading**
  - These features matter because they let you improve time-to-first-meaningful-content without flattening every dependency into one giant request; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Rerunning load functions**: Invalidations, tracked dependencies, and untracking
  - Load behavior becomes predictable only when you understand why and when it reruns; docs: [Loading data](https://svelte.dev/docs/kit/load).
- **Auth implications**: Route data and user identity are tightly coupled
  - Authentication bugs in SvelteKit often come from misunderstanding when route data runs on server versus client; docs: [Loading data](https://svelte.dev/docs/kit/load), [Auth](https://svelte.dev/docs/kit/auth).

---

### 3.2 Form Actions

- **Default and named actions**: The server-native way to handle form POSTs
  - Form actions are one of SvelteKit's best features because they preserve normal web forms while still supporting progressive enhancement; docs: [Form actions](https://svelte.dev/docs/kit/form-actions).
- **Validation with `fail(...)`**: Return structured errors instead of improvising ad hoc response shapes
  - Good action design keeps validation and user feedback close to the route that owns the form; docs: [Form actions](https://svelte.dev/docs/kit/form-actions).
- **Redirects after mutation**: Be intentional about post-submit flow
  - Redirect-after-POST keeps user refreshes safe and navigation history cleaner.
- **Returned form data**: Use it to repopulate inputs and show errors
  - This is part of what makes SvelteKit forms feel strong even before any JavaScript enhancement.
- **`use:enhance`**: Progressive enhancement without abandoning the platform
  - Learn the default behavior first, then customize enhancement only when the UX actually needs it; docs: [Form actions](https://svelte.dev/docs/kit/form-actions).
- **GET vs POST**: Use the right method for the job
  - Filtering and search often belong in the URL; mutations belong in POST; docs: [Form actions](https://svelte.dev/docs/kit/form-actions).
- **File uploads**: Understand `FormData`, multipart handling, and storage boundaries
  - Uploads are never just a field on a form; they are an end-to-end workflow across browser, server, storage, and validation; docs: [Form actions](https://svelte.dev/docs/kit/form-actions), [Web standards](https://svelte.dev/docs/kit/web-standards).

---

### 3.3 API Routes & Web Standards

- **`+server.ts` handlers**: Use route handlers for JSON, downloads, webhooks, and custom HTTP responses
  - These handlers are best when the route itself is the API, rather than a page with form actions; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Request and Response APIs**: Stay fluent with native web primitives
  - SvelteKit's elegance comes partly from not hiding HTTP behind framework-specific abstractions; docs: [Web standards](https://svelte.dev/docs/kit/web-standards).
- **Content negotiation and method handling**: Design endpoints like real HTTP resources
  - Be explicit about status codes, headers, caching, and accepted methods; docs: [Routing](https://svelte.dev/docs/kit/routing).
- **Use handlers for integrations**: Stripe webhooks, signed callbacks, file downloads, RSS, or internal JSON endpoints
  - The platform fit is often clearer here than trying to force everything through page loads.

---

### 3.4 Remote Functions (Experimental)

- **What they are**: Type-safe client/server communication through `.remote.ts` files
  - Remote functions are worth studying because they show where SvelteKit is heading, but they are currently experimental and should be treated carefully; docs: [Remote functions](https://svelte.dev/docs/kit/remote-functions).
- **Flavors**: `query`, `form`, `command`, `prerender`
  - Learn the distinctions conceptually even if you do not ship them in production immediately; docs: [Remote functions](https://svelte.dev/docs/kit/remote-functions).
- **Server-only safety**: Remote functions always run on the server
  - That makes them compatible with database clients and secret-bearing modules; docs: [Remote functions](https://svelte.dev/docs/kit/remote-functions), [Server-only modules](https://svelte.dev/docs/kit/server-only-modules).
- **Experimental opt-in**: Do not assume availability in every codebase
  - Because the feature is explicitly experimental, treat it as advanced study rather than required baseline.

**Practice**: Build a blog admin page with a paginated `load`, a create-post form action with validation errors, and a separate `+server.ts` endpoint for preview JSON.

---

## Phase 4: Server Patterns, Secrets, and Auth

### 4.1 Hooks & the Request Lifecycle

- **Hooks files**: `src/hooks.server.ts`, `src/hooks.client.ts`, `src/hooks.ts`
  - Hooks are app-wide lifecycle entry points, so they should stay focused and easy to reason about; docs: [Hooks](https://svelte.dev/docs/kit/hooks).
- **`handle`**: The main server hook
  - This is where request-wide auth/session lookup, logging context, and cross-cutting policies often begin; docs: [Hooks](https://svelte.dev/docs/kit/hooks).
- **`locals`**: Request-scoped server data
  - Treat `event.locals` as the safe place for per-request auth or tenant context, not as a dumping ground for arbitrary shared state; docs: [Hooks](https://svelte.dev/docs/kit/hooks).
- **`handleFetch`**: Intercept outbound fetches
  - This is useful when internal service calls need headers, tracing, or routing adjustments; docs: [Hooks](https://svelte.dev/docs/kit/hooks).
- **`handleError`** and `init`
  - Learn the difference between reporting unexpected failures and shaping user-facing error behavior; docs: [Hooks](https://svelte.dev/docs/kit/hooks), [Errors](https://svelte.dev/docs/kit/errors).
- **`reroute`** and **`transport`**: Advanced universal hooks
  - You do not need these on day one, but you should know they exist so advanced routing and serialization patterns do not feel magical later; docs: [Hooks](https://svelte.dev/docs/kit/hooks).

---

### 4.2 Server-Only Modules & Environment Variables

- **`$lib/server`**: Put sensitive or server-specific code here
  - Database clients, auth adapters, and secret-bearing service wrappers belong on the server by construction, not by developer discipline alone; docs: [Project structure](https://svelte.dev/docs/kit/project-structure), [Server-only modules](https://svelte.dev/docs/kit/server-only-modules).
- **Private vs public env vars**:
  - Learn `$env/static/private`, `$env/dynamic/private`, and their public counterparts so secrets never leak into the client bundle; docs: [Server-only modules](https://svelte.dev/docs/kit/server-only-modules).
- **Import boundaries matter**: Do not rely on "I know this only runs on the server"
  - SvelteKit gives you structural guarantees; use them.
- **Keep credentials and secret logic out of shared modules**
  - A mixed server/client repo is exactly where accidental leakage happens if boundaries are vague.

---

### 4.3 Cookies, Auth, and Sessions

- **Sessions vs tokens**: Understand the tradeoffs instead of copying whichever starter you saw first
  - Session-backed auth is often the pragmatic default for full-stack web apps; docs: [Auth](https://svelte.dev/docs/kit/auth).
- **Cookies as the integration point**: Read them on the server, attach user context to `locals`
  - This gives you a clean path from credentials to per-request identity; docs: [Auth](https://svelte.dev/docs/kit/auth), [Hooks](https://svelte.dev/docs/kit/hooks).
- **Authorization happens at server boundaries**: Do not trust client-visible state alone
  - Route guards, server loads, actions, and endpoints should all enforce authorization where the data actually lives.
- **Better Auth via `sv add better-auth`**: A practical official starting point
  - The Svelte CLI now supports adding Better Auth directly, which makes it a reasonable modern path to study; docs: [`better-auth` add-on](https://svelte.dev/docs/cli/better-auth), [Auth](https://svelte.dev/docs/kit/auth).
- **Auth and route data**: Know when a user must be resolved in hooks versus in route loads
  - The key is consistent ownership, not scattering auth checks across random components.

---

### 4.4 Errors & Boundaries

- **Expected errors**: Throw `error(status, body)` for known failures
  - Treat expected errors as part of control flow, not as generic exceptions with accidental side effects; docs: [Errors](https://svelte.dev/docs/kit/errors).
- **Unexpected errors**: Let SvelteKit handle them and report them
  - Unexpected failures should be logged, traced, and surfaced safely without exposing internals.
- **`+error.svelte`**: Your route-level error UI
  - Good error boundaries are part of user experience, not just diagnostics; docs: [Errors](https://svelte.dev/docs/kit/errors).
- **Type-safe error objects**: Extend error shape deliberately when needed
  - If you add codes or tracking IDs, keep them consistent across route boundaries.
- **Component-level async boundaries**: Learn how route and component errors interact
  - Async rendering patterns are much easier to debug when you know where failures surface; docs: [Errors](https://svelte.dev/docs/kit/errors), [`<svelte:boundary>`](https://svelte.dev/docs/svelte/svelte-boundary).

**Practice**: Build a protected account area that resolves a user in `handle`, stores it in `locals`, denies unauthorized access in server `load`, and renders a custom `+error.svelte` for missing resources.

---

## Phase 5: State Management & UX Patterns

### 5.1 Choose the Right Home for State

- **Component-local state**: Default to local until the problem proves otherwise
  - Local state is easier to reason about, test, and delete than prematurely global state.
- **Route data**: Server-derived state should usually stay server-derived
  - If the source of truth is the database or request, keep it in loads, actions, or endpoints instead of mirroring it in a global store.
- **URL state**: Filters, tabs, pagination, and sort order often belong in the URL
  - URL-backed state is shareable, refresh-safe, and plays well with browser history; docs: [State management](https://svelte.dev/docs/kit/state-management), [Loading data](https://svelte.dev/docs/kit/load).
- **Stores**: Best for long-lived client concerns
  - Theme preference, websocket status, client-only app chrome, or cross-route UI state can justify a store; docs: [Stores](https://svelte.dev/docs/svelte/stores).
- **Context**: Best for subtree-scoped coordination
  - Use context when a feature area has shared state but the whole app should not care.

---

### 5.2 Avoid Shared-State SSR Gotchas

- **Never store per-user data in module-level server variables**
  - This is one of the most important SvelteKit production rules because long-lived servers serve many users; docs: [State management](https://svelte.dev/docs/kit/state-management).
- **No side effects in `load`** unless the behavior is intentionally tied to data fetching
  - Loads should explain data dependencies, not perform surprise mutations; docs: [State management](https://svelte.dev/docs/kit/state-management).
- **Think in requests, not singleton memory**
  - Request-scoped data belongs in `locals`, inputs, cookies, or returned `load` data.
- **Serialization boundaries matter**
  - If data crosses from server to client, make sure the shape is safe, serializable, and actually needed.

---

### 5.3 URL State, Snapshots, and Navigation State

- **Store durable UI state in the URL**
  - If a user would expect refresh, sharing, or bookmarking to preserve it, the URL is usually the correct home; docs: [State management](https://svelte.dev/docs/kit/state-management).
- **Use snapshots for ephemeral DOM state**
  - Snapshots are for state the user expects to survive back/forward navigation but not necessarily be encoded in the URL; docs: [Snapshots](https://svelte.dev/docs/kit/snapshots).
- **Use shallow routing for history-aware overlays**
  - This lets you make mobile-friendly back-button behavior feel native; docs: [Shallow routing](https://svelte.dev/docs/kit/shallow-routing).
- **Learn `$app/state` in modern codebases**
  - Older examples often use `$app/stores`; modern SvelteKit increasingly uses `$app/state`, so you should read both comfortably; docs: [Errors](https://svelte.dev/docs/kit/errors), [Shallow routing](https://svelte.dev/docs/kit/shallow-routing).

---

### 5.4 Common UX Patterns

- **Optimistic UI**: Use when the domain tolerates temporary client-side assumptions
  - Optimism feels great when rollback is clear and rare, but dangerous when domain rules are strict.
- **Pending states**: Every mutation needs visible feedback
  - The skill is not adding spinners everywhere, but making state transitions legible.
- **Layout-level chrome**: Navigation, breadcrumbs, flash messages, and sidebars often belong in layouts
  - This keeps page components focused on feature-specific behavior.
- **Form persistence and draft recovery**: Use the right tool for the state lifetime
  - URL, snapshot, localStorage, or server draft models each solve different problems.

**Practice**: Build a searchable admin list where filters live in the URL, modal editing uses shallow routing, and unfinished text input survives back navigation with snapshots.

---

## Phase 6: Performance, Accessibility, and SEO

### 6.1 Performance Optimization

- **Start with SvelteKit's defaults**: SSR, routing, and code-splitting already help a lot
  - The real skill is knowing when you are bypassing those advantages accidentally; docs: [Performance](https://svelte.dev/docs/kit/performance).
- **Diagnose before optimizing**
  - Build the habit of tracing slow routes, oversized bundles, and waterfall requests before introducing clever fixes; docs: [Performance](https://svelte.dev/docs/kit/performance).
- **Reduce waterfalls**: Parallelize where you can
  - Many full-stack performance problems are really dependency-order problems in `load` and subsequent client fetches; docs: [Loading data](https://svelte.dev/docs/kit/load), [Performance](https://svelte.dev/docs/kit/performance).
- **Selective loading**: Keep non-essential code and data off the critical path
  - Fast-feeling apps often defer what is optional rather than trying to micro-optimize everything.
- **Preloading and navigation polish**: Make route changes feel immediate
  - SvelteKit gives you good primitives here, but you still have to use them intentionally; docs: [Performance](https://svelte.dev/docs/kit/performance).
- **Choose the right hosting model**: Performance is partly an infrastructure decision
  - Rendering mode, edge proximity, adapter choice, and caching strategy all matter.

---

### 6.2 Images & Assets

- **Do not treat images as an afterthought**
  - Images are often the largest assets in the app and one of the easiest places to win or lose performance; docs: [Images](https://svelte.dev/docs/kit/images).
- **Vite's built-in asset handling**: Know what happens automatically
  - Understanding the default behavior helps you decide when you need more specialized image handling; docs: [Images](https://svelte.dev/docs/kit/images).
- **`@sveltejs/enhanced-img`**: Learn the official image optimization path
  - Responsive sizing, modern formats, and intrinsic dimensions are worth studying early; docs: [Images](https://svelte.dev/docs/kit/images).
- **Dynamic image strategies**: CDN-driven images need a different plan
  - Official docs cover how this differs from local asset pipelines.

---

### 6.3 Accessibility

- **Route announcements**: SvelteKit helps screen-reader users on navigation
  - This is a platform advantage, but it only works well if your app structure cooperates; docs: [Accessibility](https://svelte.dev/docs/kit/accessibility).
- **Focus management**: Especially critical after navigation, modal open/close, and form errors
  - Accessibility bugs are often state-transition bugs in disguise; docs: [Accessibility](https://svelte.dev/docs/kit/accessibility).
- **Set the `lang` attribute correctly**
  - This is simple, easy to miss, and important for assistive technology; docs: [Accessibility](https://svelte.dev/docs/kit/accessibility).
- **Svelte compile-time checks**: Keep them enabled and meaningful
  - Fixing warnings as they appear is much cheaper than retrofitting accessibility at the end.

---

### 6.4 SEO

- **SSR is an SEO advantage**
  - SvelteKit defaults to SSR, and the docs explicitly recommend keeping it unless you have a strong reason not to; docs: [SEO](https://svelte.dev/docs/kit/seo).
- **Performance affects discoverability**
  - SEO is not just metadata; slow routes and heavy assets hurt ranking and user retention together; docs: [SEO](https://svelte.dev/docs/kit/seo), [Performance](https://svelte.dev/docs/kit/performance).
- **Titles and meta tags**: Own them at the route or layout boundary
  - Treat metadata as part of the page contract, not a last-minute content chore; docs: [SEO](https://svelte.dev/docs/kit/seo), [`<svelte:head>`](https://svelte.dev/docs/svelte/svelte-head).
- **Normalized URLs and sitemaps**
  - Consistent URLs, canonical policies, and sitemap generation matter especially on content-heavy sites; docs: [SEO](https://svelte.dev/docs/kit/seo).

**Practice**: Optimize a content page with responsive images, SSR-friendly metadata, zero obvious data waterfalls, and clean `sv check` accessibility output.

---

## Phase 7: Testing & Quality

### 7.1 Static Analysis & Type Safety

- **`sv check` in development and CI**: Make it non-optional
  - This catches exactly the kind of issues that are easy to miss in component-driven work; docs: [`sv check`](https://svelte.dev/docs/cli/sv-check).
- **Generated route types**: Lean on SvelteKit instead of duplicating contracts
  - Hand-maintained types drift quickly when route inputs and outputs change.
- **Type-checking server/client boundaries**: One of the highest-leverage SvelteKit habits
  - Full-stack apps get brittle when data shapes are "close enough" instead of explicit.

---

### 7.2 Unit & Component Tests with Vitest

- **Vitest**: The recommended test runner in Vite-based Svelte projects
  - This is the default testing path the Svelte docs recommend for SvelteKit apps; docs: [Testing](https://svelte.dev/docs/svelte/testing), [`vitest` add-on](https://svelte.dev/docs/cli/vitest), [Vitest](https://vitest.dev/).
- **Test plain functions and `.svelte.ts` modules first**
  - The cheapest tests usually live below the component layer.
- **Component testing**: Verify rendered behavior, not implementation trivia
  - Test the user contract: visible state, events, accessibility, and data flow; docs: [Testing](https://svelte.dev/docs/svelte/testing).
- **Runes in tests**: Understand how reactive updates flush
  - Svelte's testing guidance now includes rune-aware examples, which is important for modern codebases; docs: [Testing](https://svelte.dev/docs/svelte/testing).

---

### 7.3 Component Workshop with Storybook

- **Storybook**: Useful for design systems and isolated UI work
  - It is not mandatory for every product app, but it is worth learning for component libraries and shared design systems; docs: [`storybook` add-on](https://svelte.dev/docs/cli/storybook), [Storybook for SvelteKit](https://storybook.js.org/docs/get-started/frameworks/sveltekit).
- **Use stories to lock down states**: Empty, loading, error, long text, mobile breakpoints
  - Stories are most valuable when they capture edge cases that are annoying to reproduce manually.

---

### 7.4 End-to-End Tests with Playwright

- **Playwright**: The official Svelte docs recommendation for browser-level testing
  - Use E2E tests for route flows, auth, forms, and regressions that only appear in the browser; docs: [Testing](https://svelte.dev/docs/svelte/testing), [`playwright` add-on](https://svelte.dev/docs/cli/playwright), [Playwright](https://playwright.dev/).
- **Test full-stack behavior**: Load data, submit forms, navigate routes, and assert on accessibility-friendly output
  - SvelteKit really shines when you test the route and server behavior together.
- **Keep E2E focused**: High-value flows, not every branch
  - Browser tests are slower and more expensive, so reserve them for integrated user journeys.

---

### 7.5 Testing Strategy

- **Unit**: Pure logic, helpers, transformations
- **Component**: Rendering, props, interactions, accessibility states
- **Route/integration**: `load`, actions, redirects, auth boundaries
- **E2E**: Critical user journeys and production-like flows
  - The important skill is knowing which layer gives you confidence cheapest for a given bug class.

**Practice**: Add unit tests for a formatter, component tests for a form, and Playwright coverage for login plus a successful create/update flow.

---

## Phase 8: Advanced Platform Features

### 8.1 Service Workers

- **Offline and precaching**: Study service workers once your app actually benefits from them
  - Service workers are powerful, but they add operational complexity around caching and invalidation; docs: [Service workers](https://svelte.dev/docs/kit/service-workers).
- **Automatic registration**: Understand the default before customizing it
  - You should know what SvelteKit does for you before replacing it with your own registration flow; docs: [Service workers](https://svelte.dev/docs/kit/service-workers).
- **Use cases**: Asset precaching, offline support, resilient navigation
  - Not every app needs offline mode, but many apps benefit from smarter asset caching.

---

### 8.2 Observability

- **Instrumentation and tracing**: Know where SvelteKit fits into your monitoring story
  - Once an app is live, understanding failures matters as much as preventing them; docs: [Observability](https://svelte.dev/docs/kit/observability).
- **Request-aware logging**: Tie logs to request context
  - This makes debugging auth, routing, and deployment issues far easier in production.
- **Performance visibility**: Watch route timing and server work, not just frontend paint
  - Full-stack frameworks demand full-stack observability habits.

---

### 8.3 Packaging Libraries with SvelteKit

- **SvelteKit is not only for apps**: It can also package component libraries
  - This matters if you want to build design systems or reusable internal packages; docs: [Packaging](https://svelte.dev/docs/kit/packaging).
- **`src/lib` becomes the public surface in a library project**
  - Packaging discipline is mostly about defining clear exports, types, and side effects; docs: [Packaging](https://svelte.dev/docs/kit/packaging).
- **`svelte-package` and type generation**: Learn how published Svelte libraries should be shaped
  - This is especially valuable if you want to understand the ecosystem better by reading package structure.
- **`package.json` export conditions**: `types`, `svelte`, `sideEffects`
  - Library correctness is often about metadata, not just component code; docs: [Packaging](https://svelte.dev/docs/kit/packaging).

**Practice**: Convert a small set of shared UI primitives into a publishable internal package with generated types and a Storybook sandbox.

---

## Phase 9: Deployment & DevOps

### 9.1 Building & Previewing

- **Production build flow**: `npm run build` uses `vite build` plus an adapter step
  - You should know that SvelteKit first builds optimized output and then adapts it to the target platform; docs: [Building your app](https://svelte.dev/docs/kit/building-your-app).
- **`npm run preview`**: Verify the production build locally
  - Previewing catches a lot of "works in dev, fails in prod" mistakes early; docs: [Building your app](https://svelte.dev/docs/kit/building-your-app).
- **Build-time execution**: Code may run during analysis and prerendering
  - This is why build-safe guards and clean server initialization boundaries matter; docs: [Building your app](https://svelte.dev/docs/kit/building-your-app).

---

### 9.2 Adapters & Deployment Targets

- **Adapters are how SvelteKit targets platforms**
  - Understanding adapters is essential because deployment is not an afterthought in SvelteKit; docs: [Adapters](https://svelte.dev/docs/kit/adapters).
- **Official adapters**: `auto`, `node`, `static`, `vercel`, `cloudflare`, `netlify`
  - Pick the adapter based on rendering needs and runtime constraints, not platform hype; docs: [`sveltekit-adapter` add-on](https://svelte.dev/docs/cli/sveltekit-adapter), [Adapters](https://svelte.dev/docs/kit/adapters).
- **Node servers**: Best when you need SSR, custom server behavior, or full control
  - This is the most familiar full-stack deployment model for many teams.
- **Static generation**: Great when most or all routes can be prerendered
  - Static output is operationally simple and fast when your content model allows it.
- **Edge/serverless targets**: Great for latency and managed deploys, but understand platform limits
  - Platform-specific context and runtime differences matter more as your app gets more stateful.

---

### 9.3 CI/CD

- **Pipeline basics**: install, lint, `sv check`, test, build
  - This should be the minimum bar for production-ready SvelteKit repos.
- **Run fast checks early**: Formatting, linting, and `sv check` should fail quickly
  - Fast feedback keeps the team from waiting on avoidable browser tests.
- **Environment-safe deploys**: Keep secrets in the platform, not the repo
  - This is especially important in full-stack SvelteKit apps where server and client code live together.
- **Preview deployments**: Extremely useful for route-heavy apps
  - Preview deploys let you validate SSR, metadata, and integrated flows in near-production conditions.

---

### 9.4 Monitoring After Launch

- **Error tracking**: Capture server and client failures with context
  - The goal is not just "we have logs" but "we can reproduce and fix failures quickly."
- **Performance monitoring**: Watch route latency, slow endpoints, and frontend vitals
  - SvelteKit performance work does not stop at bundle size.
- **Operational sanity checks**: Adapter fit, cache behavior, and auth/session expiry
  - Many production bugs are deployment-shape bugs rather than component bugs.

**Practice**: Deploy the same app in two ways: one prerender-heavy static deployment and one SSR-capable deployment. Document why the rendering strategy changed.

---

## Phase 10: Real-World Ecosystem

### 10.1 Official CLI Add-Ons

- **`sv add`**: Learn the ecosystem through the official add-on path first
  - This keeps setup aligned with current Svelte expectations instead of outdated tutorials; docs: [`sv add`](https://svelte.dev/docs/cli/sv-add).
- **Core add-ons worth knowing**:
  - [`vitest`](https://svelte.dev/docs/cli/vitest)
  - [`playwright`](https://svelte.dev/docs/cli/playwright)
  - [`eslint`](https://svelte.dev/docs/cli/eslint)
  - [`prettier`](https://svelte.dev/docs/cli/prettier)
  - [`storybook`](https://svelte.dev/docs/cli/storybook)
  - [`sveltekit-adapter`](https://svelte.dev/docs/cli/sveltekit-adapter)

---

### 10.2 Content, i18n, and Styling

- **`mdsvex`**: Great for docs, blogs, and content-heavy sites
  - This is one of the most Svelte-native ways to mix markdown and components; docs: [`mdsvex` add-on](https://svelte.dev/docs/cli/mdsvex), [mdsvex](https://mdsvex.pngwn.io/).
- **`paraglide`**: Official CLI path for internationalization
  - Worth learning because it integrates with routing and language metadata in a SvelteKit-friendly way; docs: [`paraglide` add-on](https://svelte.dev/docs/cli/paraglide), [Paraglide](https://inlang.com/m/gerre34r/library-inlang-paraglideJs).
- **Tailwind CSS**: Very common in SvelteKit apps
  - Even if you prefer plain CSS, you should be comfortable reading Tailwind-heavy codebases; docs: [Tailwind CSS](https://tailwindcss.com/docs/installation).
- **Plain CSS and component-scoped styling**: Still a strong default in Svelte
  - One of Svelte's advantages is that plain CSS remains ergonomic longer than in many frameworks.

---

### 10.3 Database & Auth Stack

- **`drizzle`**: Official CLI add-on for a TypeScript-friendly database layer
  - This is a practical stack to study because it reinforces server-only boundaries and typed data access; docs: [`drizzle` add-on](https://svelte.dev/docs/cli/drizzle), [Drizzle ORM](https://orm.drizzle.team/).
- **Better Auth**: Practical auth setup with first-party CLI support
  - The combination of Better Auth plus Drizzle is worth learning because the Svelte CLI explicitly supports it.
- **Server files own data access**: Keep ORM calls in server-only modules and route handlers
  - Good SvelteKit architecture makes it difficult to import server concerns into client code by accident.

---

### 10.4 Reading Older Code & Migrating Forward

- **Older codebases still exist**: Expect Svelte 3/4 syntax in the wild
  - You should be able to read `export let`, `$:`, `on:click`, and `<slot>` even if you prefer runes mode; docs: [Legacy overview](https://svelte.dev/docs/svelte/legacy-overview).
- **Migration skill matters**: Teams value people who can modernize incrementally
  - The practical question is rarely "should we rewrite everything?" and more often "what can we migrate safely this quarter?"
- **Read the migration guides deliberately**
  - Migration docs are often the fastest way to understand what the framework authors consider important changes; docs: [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide), [Legacy overview](https://svelte.dev/docs/svelte/legacy-overview).

---

## Capstone Projects

Build these to demonstrate job-ready SvelteKit skills:

### Project 1: Content Platform / Developer Blog

- Public marketing pages prerendered for speed
  - This forces you to choose rendering strategy intentionally rather than defaulting everything to SSR.
- Blog routes with `[slug]` params and shared layout data
  - Route architecture is one of the clearest signals of SvelteKit maturity.
- Rich metadata per page with `<svelte:head>`
  - This proves you can think about SEO at the route layer, not just in page content.
- Authoring flow with markdown or mdsvex
  - A content pipeline is a practical way to learn SvelteKit's strengths on docs-heavy products; docs: [`mdsvex` add-on](https://svelte.dev/docs/cli/mdsvex).
- Optimized local images with `@sveltejs/enhanced-img`
  - This shows you can connect asset performance to user-facing output; docs: [Images](https://svelte.dev/docs/kit/images).
- Search and tag filters stored in the URL
  - URL-backed state is especially appropriate on content sites.
- RSS or JSON feed exposed from a `+server.ts` route
  - This proves you can use route handlers as more than API-only plumbing.

### Project 2: SaaS Admin Dashboard

- Session-based auth with server-resolved user context
  - This tests whether you truly understand hooks, cookies, and `locals`; docs: [Auth](https://svelte.dev/docs/kit/auth), [Hooks](https://svelte.dev/docs/kit/hooks).
- Nested app layouts with protected routes
  - Layout architecture becomes real once you have account shells, nav, and role-aware pages.
- Filterable data tables with URL state
  - Good dashboards make query params, navigation, and data loading work together cleanly.
- CRUD forms using actions plus `use:enhance`
  - This is one of the clearest ways to show modern SvelteKit fluency; docs: [Form actions](https://svelte.dev/docs/kit/form-actions).
- Error boundaries and expected failure handling
  - Admin apps surface authorization, validation, and missing-resource errors frequently.
- Vitest coverage for logic plus Playwright for critical journeys
  - This demonstrates layered testing rather than one-size-fits-all testing.
- Deploy to Node, Vercel, or Cloudflare with the right adapter
  - The deployment story should match the product's rendering needs; docs: [Adapters](https://svelte.dev/docs/kit/adapters).

### Project 3: Collaborative Knowledge Base

- Authenticated workspace with role-based permissions
  - Collaboration apps quickly expose weak server/client ownership boundaries.
- Command palette, nested navigation tree, and keyboard shortcuts
  - This is strong practice for state organization and accessibility under interaction-heavy UI.
- Draft editing with snapshots or explicit draft persistence
  - This tests whether you can choose the right persistence boundary for user work-in-progress.
- Activity stream and optimistic interactions
  - Optimistic UX only feels good when rollback and invalidation are designed well.
- Search endpoint plus filtered route loading
  - This combines route handlers, URL state, and page data design.
- Optional service worker for asset precaching
  - Only add it if the product benefits, but understanding the tradeoff is part of the exercise; docs: [Service workers](https://svelte.dev/docs/kit/service-workers).
- Observability hooks and production error tracking
  - Real-world collaboration tools need operational maturity, not just polished UI.

---

## Study Methodology

1. **Start with the official tutorial and docs** — use this guide as the roadmap, but let the Svelte and SvelteKit docs be the textbook
   - The official docs are current, opinionated in the right places, and especially important now that Svelte 5 changed the core mental model; docs: [Svelte overview](https://svelte.dev/docs/svelte/overview), [SvelteKit introduction](https://svelte.dev/docs/kit/introduction).
2. **Learn modern Svelte 5 first** — runes, modern event syntax, snippets, and `$props`
   - You should still read legacy syntax, but do not start your own projects in an outdated style unless the codebase requires it.
3. **Stay server-first in your mental model** — SvelteKit is not "just a SPA with files"
   - The most common mistakes come from forgetting which code runs on the server, on the client, or in both places.
4. **Use forms and links like the web platform intended** — then enhance them
   - SvelteKit is strongest when you let HTML and HTTP do real work before layering on JavaScript.
5. **Prefer route-level data ownership over global stores** — use stores when they actually fit
   - A lot of beginner SvelteKit architecture gets cleaner when data stays with loads, actions, and URLs.
6. **Run `sv check` constantly** — compiler feedback is part of the framework
   - Treat warnings as design feedback, not just lint noise; docs: [`sv check`](https://svelte.dev/docs/cli/sv-check).
7. **Test the whole stack** — not just isolated components
   - SvelteKit's value is in the integration of routing, server logic, and progressive enhancement, so your tests should reflect that.
8. **Read real code and migration guides** — many production repos are mixed-era
   - The fastest way to get job-ready is to be fluent in both modern patterns and the older patterns you will inherit.

---

## Additional Reference Links

- **Official Svelte references**:
  - [Svelte Docs Overview](https://svelte.dev/docs/svelte/overview)
  - [.svelte files](https://svelte.dev/docs/svelte/svelte-files)
  - [What are runes?](https://svelte.dev/docs/svelte/what-are-runes)
  - [Stores](https://svelte.dev/docs/svelte/stores)
  - [Context](https://svelte.dev/docs/svelte/context)
  - [Lifecycle hooks](https://svelte.dev/docs/svelte/lifecycle-hooks)
  - [Legacy overview](https://svelte.dev/docs/svelte/legacy-overview)
  - [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide)
  - [Testing](https://svelte.dev/docs/svelte/testing)
  - [TypeScript](https://svelte.dev/docs/svelte/typescript)
- **Official SvelteKit references**:
  - [Introduction](https://svelte.dev/docs/kit/introduction)
  - [Project structure](https://svelte.dev/docs/kit/project-structure)
  - [Routing](https://svelte.dev/docs/kit/routing)
  - [Advanced routing](https://svelte.dev/docs/kit/advanced-routing)
  - [Loading data](https://svelte.dev/docs/kit/load)
  - [Form actions](https://svelte.dev/docs/kit/form-actions)
  - [State management](https://svelte.dev/docs/kit/state-management)
  - [Hooks](https://svelte.dev/docs/kit/hooks)
  - [Errors](https://svelte.dev/docs/kit/errors)
  - [Performance](https://svelte.dev/docs/kit/performance)
  - [Images](https://svelte.dev/docs/kit/images)
  - [Accessibility](https://svelte.dev/docs/kit/accessibility)
  - [SEO](https://svelte.dev/docs/kit/seo)
  - [Adapters](https://svelte.dev/docs/kit/adapters)
  - [Building your app](https://svelte.dev/docs/kit/building-your-app)
  - [Service workers](https://svelte.dev/docs/kit/service-workers)
  - [Packaging](https://svelte.dev/docs/kit/packaging)
- **Official CLI references**:
  - [`sv create`](https://svelte.dev/docs/cli/sv-create)
  - [`sv add`](https://svelte.dev/docs/cli/sv-add)
  - [`sv check`](https://svelte.dev/docs/cli/sv-check)
  - [`better-auth` add-on](https://svelte.dev/docs/cli/better-auth)
  - [`drizzle` add-on](https://svelte.dev/docs/cli/drizzle)
  - [`playwright` add-on](https://svelte.dev/docs/cli/playwright)
  - [`storybook` add-on](https://svelte.dev/docs/cli/storybook)
  - [`vitest` add-on](https://svelte.dev/docs/cli/vitest)
- **Supporting tool docs**:
  - [Vite](https://vite.dev/guide/)
  - [Vitest](https://vitest.dev/)
  - [Playwright](https://playwright.dev/)
  - [TypeScript Handbook](https://www.typescriptlang.org/docs/)
  - [ESLint](https://eslint.org/)
  - [Prettier](https://prettier.io/docs/en/)
  - [Tailwind CSS](https://tailwindcss.com/docs/installation)
- **Web platform references**:
  - [MDN Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
  - [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData)
  - [MDN Request](https://developer.mozilla.org/en-US/docs/Web/API/Request)
  - [MDN Response](https://developer.mozilla.org/en-US/docs/Web/API/Response)
  - [MDN URL API](https://developer.mozilla.org/en-US/docs/Web/API/URL)
  - [MDN Cookie header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cookie)
  - [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)

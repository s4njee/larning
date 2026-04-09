# Next.js Mastery Study Guide

A comprehensive, job-focused guide to mastering Next.js with the App Router, React Server Components, and modern full-stack React workflows. Each section builds on the previous one. Build real features, not toy examples.

This guide targets the modern App Router model and the Next.js 16 era documented on April 9, 2026. Learn the App Router first. Learn the Pages Router only well enough to maintain older codebases.

---

## Phase 1: Core Foundations

### 1.1 Project Setup & Tooling

- **`create-next-app`**: Use the official scaffolder to start with TypeScript, ESLint, Tailwind, `src/`, and import aliases instead of hand-assembling the baseline
  - Starting from the official template keeps you aligned with current conventions and makes docs/examples easier to map back into your codebase; docs: [Installation](https://nextjs.org/docs/app/getting-started/installation), [Next CLI](https://nextjs.org/docs/app/api-reference/cli).
- **TypeScript-first workflow**: Next.js has built-in TypeScript support, route-aware helpers, and optional typed routes
  - The biggest payoff is safer refactors across layouts, route params, metadata, and navigation code before bugs get to runtime; docs: [TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript).
- **`typedRoutes` + `next typegen`**: Learn these early if you want navigation and route helpers checked by the compiler
  - Route typing is especially valuable in larger apps where broken links and stale path strings otherwise spread quietly; docs: [TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript), [`next.config.js`](https://nextjs.org/docs/app/api-reference/config/next-config-js).
- **`eslint-config-next`**: Use the official lint rules, preferably the Core Web Vitals variant
  - Next-specific linting catches framework misuse that generic React lint rules will miss; docs: [ESLint Plugin](https://nextjs.org/docs/app/api-reference/config/eslint).
- **Know the core CLI**: `next dev`, `next build`, `next start`, `next typegen`
  - Build fluency matters because many "framework bugs" are really development-mode, build-time, or production-only behavior differences; docs: [Next CLI](https://nextjs.org/docs/app/api-reference/cli).
- **Project structure conventions**:
  - Treat this layout as a maintainability baseline so server code, client components, routes, and domain logic stay easy to find.
  ```
  src/
    app/                     # App Router routes, layouts, pages, route handlers
    components/              # Shared UI components
    features/                # Feature-specific components, actions, hooks, tests
    lib/                     # Server utilities, data access, auth helpers, schemas
    actions/                 # Shared Server Functions when feature-local colocation is not better
    hooks/                   # Client-side custom hooks
    styles/                  # Global styles, tokens, CSS modules
    public/                  # Static assets
    instrumentation.ts       # Server instrumentation
    instrumentation-client.ts # Client instrumentation
    proxy.ts                 # Request-time proxy logic (Next.js 16+)
  ```
- **Keep feature folders honest**: Put reads near the Server Component that uses them and writes near the feature that owns the mutation
  - Next.js works best when route-level code feels close to the domain it serves, instead of routing everything through a giant `services/` folder.

**Practice**: Scaffold a new app with TypeScript, ESLint, Tailwind, `src/`, and import aliases. Turn on `typedRoutes`, inspect every generated file, and explain why each one exists.

---

### 1.2 App Router File Conventions

- **`app/` defines your route tree**: Every folder is a route segment, and special files control behavior
  - You should be able to look at the filesystem and predict the URL hierarchy, layout nesting, and request boundaries; docs: [Project Structure](https://nextjs.org/docs/app/getting-started/project-structure), [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **`page.tsx`**: The leaf UI for a route
  - Keep page files thin enough that route concerns stay obvious: params, data dependencies, metadata, and major composition boundaries; docs: [`page.js`](https://nextjs.org/docs/app/api-reference/file-conventions/page).
- **`layout.tsx`**: Persistent shared UI around child segments
  - Layouts are where navigation, shell structure, shared providers, and route-group organization become readable instead of improvised; docs: [Layouts and Pages](https://nextjs.org/docs/app/getting-started/layouts-and-pages), [`layout.js`](https://nextjs.org/docs/app/api-reference/file-conventions/layout).
- **`template.tsx`**: Like a layout, but remounts on navigation
  - Learn this specifically for cases where you want fresh state or repeated entrance behavior instead of layout persistence; docs: [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **`route.ts`**: Custom request handlers inside `app/`
  - Route Handlers are the App Router-native way to expose HTTP endpoints, webhooks, and backend-for-frontend logic; docs: [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers-and-middleware), [`route.js`](https://nextjs.org/docs/app/api-reference/file-conventions/route).
- **Boundary files**: `loading.tsx`, `error.tsx`, `not-found.tsx`, `forbidden.tsx`, `unauthorized.tsx`
  - These are not afterthought files. They are how you make async UI, failure states, and auth interruptions feel intentional instead of brittle; docs: [Error Handling](https://nextjs.org/docs/app/getting-started/error-handling), [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **Root-level runtime files**: `proxy.ts`, `instrumentation.ts`, `instrumentation-client.ts`
  - These shape request-time behavior and observability, so know what they do before production makes them urgent; docs: [Proxy](https://nextjs.org/docs/app/getting-started/proxy), [Instrumentation](https://nextjs.org/docs/app/guides/instrumentation), [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).

**Practice**: Create a small route tree with a root layout, a nested dashboard layout, a route handler, a loading state, an error boundary, and a custom `not-found.tsx`. Make sure you can explain when each file runs.

---

### 1.3 React Fundamentals That Matter in Next.js

- **Component purity and one-way data flow**: Master props, local state, derived state, and composition before reaching for framework features
  - Most bad Next.js code is still bad React code: duplicated state, effect-heavy fetching, and unclear ownership; docs: [React Learn](https://react.dev/learn), [Thinking in React](https://react.dev/learn/thinking-in-react).
- **Effects are an escape hatch**: Do not use `useEffect` for data fetching by default in App Router apps
  - In modern Next.js, many reads belong in Server Components or Route Handlers, not in client-side effects that race hydration; docs: [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect).
- **Forms and controlled inputs**: Understand plain HTML form behavior before layering in Server Functions
  - Next.js forms feel simpler once you stop fighting the browser and start using native submission semantics well; docs: [React `<form>`](https://react.dev/reference/react-dom/components/form), [React `<input>`](https://react.dev/reference/react-dom/components/input).
- **Suspense mindset**: Learn how async UI boundaries change loading behavior and component design
  - Suspense is part of the rendering model now, not an exotic optimization; docs: [Suspense](https://react.dev/reference/react/Suspense).
- **Transitions and responsive UI**: `startTransition`, `useTransition`, and `useDeferredValue`
  - These APIs help you keep typing, filtering, and navigation-feeling work responsive when some updates are less urgent than others; docs: [`startTransition`](https://react.dev/reference/react/startTransition), [`useTransition`](https://react.dev/reference/react/useTransition), [`useDeferredValue`](https://react.dev/reference/react/useDeferredValue).

**Practice**: Build a client-only search UI in plain React first. Then identify which parts should stay client-side and which parts would move server-side in a real Next.js app.

---

### 1.4 Server Components vs Client Components

- **Server Components are the default**: Pages and layouts are Server Components unless you opt into client behavior
  - Start from "server first" and add client code only where interactivity or browser APIs actually require it; docs: [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [React Server Components](https://react.dev/reference/rsc/server-components).
- **`'use client'` creates a bundle boundary**: It is not just a hint; it moves that file and its imports into the client graph
  - Every unnecessary client boundary increases JavaScript sent to the browser, so treat it as a deliberate cost; docs: [`'use client'`](https://react.dev/reference/rsc/use-client), [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components).
- **`'use server'` is for Server Functions, not Server Components**
  - This distinction clears up a lot of confusion. There is no directive for Server Components; `use server` marks callable server-side functions; docs: [`'use server'`](https://react.dev/reference/rsc/use-server), [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data).
- **Serializable boundaries matter**: Data passed from Server Components to Client Components must be serializable in supported ways
  - Passing the wrong shape or the wrong kind of abstraction across the boundary is where architecture starts to fight the framework; docs: [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [`'use server'`](https://react.dev/reference/rsc/use-server).
- **Compose server and client intentionally**: Put providers, event handlers, and browser-only libraries as low in the tree as you can
  - The goal is to keep the client bundle narrow and keep server-only logic private by default; docs: [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components).

**Practice**: Build a product page where the shell and data load on the server, but the cart button, quantity stepper, and wishlist toggle stay client-side.

---

## Phase 2: Routing and UI Composition

### 2.1 Layouts, Templates, and Route Groups

- **Nested layouts**: Use them to model real UI shells, not just to avoid repetition
  - Good layout design makes auth areas, marketing pages, dashboards, and settings screens feel like clearly owned surfaces; docs: [Layouts and Pages](https://nextjs.org/docs/app/getting-started/layouts-and-pages).
- **Route groups**: `(marketing)`, `(dashboard)`, etc.
  - Route groups are an organizational tool that lets you reshape the route tree without changing the URL structure; docs: [Route Groups](https://nextjs.org/docs/app/api-reference/file-conventions/route-groups).
- **Templates vs layouts**: Know when you want persistence and when you want remounts
  - Many subtle UI bugs around stale local state come from choosing a layout when a template was the better boundary; docs: [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **Colocation**: Keep segment-specific components, loading states, and test fixtures near the route that owns them
  - App Router encourages file-level clarity. Use that to reduce mental overhead instead of building a maze of shared folders.

**Practice**: Model a marketing site plus an authenticated dashboard in one app using route groups and nested layouts. Make the dashboard shell persist while settings subpages change.

---

### 2.2 Navigation and URL-Driven State

- **`<Link>` is the default navigation primitive**: Learn prefetch behavior and when plain anchors are still correct
  - Navigation bugs often come from forgetting that Next.js is doing more than a raw page load; docs: [Linking and Navigating](https://nextjs.org/docs/app/getting-started/linking-and-navigating), [`Link`](https://nextjs.org/docs/app/api-reference/components/link).
- **Client navigation hooks**: `useRouter`, `usePathname`, `useSearchParams`
  - These are for client-side UX glue, not for re-implementing the whole routing system yourself; docs: [`useRouter`](https://nextjs.org/docs/app/api-reference/functions/use-router), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Redirect APIs**: `redirect()`, `permanentRedirect()`, `notFound()`
  - Use framework primitives instead of ad hoc conditionals so failure and navigation behavior stays consistent across server and client transitions; docs: [`redirect`](https://nextjs.org/docs/app/api-reference/functions/redirect), [`permanentRedirect`](https://nextjs.org/docs/app/api-reference/functions/permanentRedirect), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **URL state beats duplicated client state**: Filters, sorts, pagination, tabs, and search queries often belong in the URL
  - URL state makes shareability, refresh behavior, and server/client coordination much easier; docs: [Preserving UI State](https://nextjs.org/docs/app/guides/preserving-ui-state), [`useSearchParams`](https://nextjs.org/docs/app/api-reference/functions/use-search-params).
- **Typed links**: When using TypeScript, let the compiler catch broken hrefs
  - This turns navigation into a refactor-safe interface instead of a stringly typed liability; docs: [TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript).

**Practice**: Build a searchable, filterable admin table where every filter lives in the URL and deep links restore the exact view state.

---

### 2.3 Dynamic Segments, Parallel Routes, and Intercepting Routes

- **Dynamic segments**: `[id]`, `[...slug]`, `[[...slug]]`
  - Learn these cold because real apps inevitably need entity pages, nested docs, and optional catchalls; docs: [Dynamic Segments](https://nextjs.org/docs/app/api-reference/file-conventions/dynamic-routes).
- **`generateStaticParams()`**: Precompute route params when static generation is the right fit
  - This is valuable when you know the universe of paths ahead of time or can generate a meaningful subset cheaply; docs: [`generateStaticParams`](https://nextjs.org/docs/app/api-reference/functions/generate-static-params).
- **Parallel routes**: `@slot`
  - Parallel routes are for independently rendered regions, not for avoiding normal component composition; docs: [Parallel Routes](https://nextjs.org/docs/app/api-reference/file-conventions/parallel-routes).
- **Intercepting routes**: `(.)`, `(..)`, etc.
  - These are worth learning because they unlock modal-over-list flows that feel native instead of hacky; docs: [Intercepting Routes](https://nextjs.org/docs/app/api-reference/file-conventions/intercepting-routes).
- **Route segment config**: `runtime`, `preferredRegion`, `maxDuration`, `dynamicParams`
  - Segment config is where routing meets platform behavior, caching, and performance constraints; docs: [Route Segment Config](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config).

**Practice**: Implement a photo gallery where clicking a thumbnail opens a modal via an intercepting route, but direct navigation to the same URL renders a full page.

---

### 2.4 Loading, Error, and Missing-State UX

- **`loading.tsx`**: Segment-level loading UI
  - Good loading states are part of the product experience, especially when streaming partial UI is one of the framework's core strengths; docs: [`loading.js`](https://nextjs.org/docs/app/api-reference/file-conventions/loading), [Streaming](https://nextjs.org/docs/app/guides/streaming).
- **`error.tsx`**: Route-local error boundaries
  - Route-local failure handling keeps an entire app from feeling fragile when one segment has a problem; docs: [Error Handling](https://nextjs.org/docs/app/getting-started/error-handling), [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **`not-found.tsx`, `forbidden.tsx`, `unauthorized.tsx`**: Make absence and access rules explicit
  - Users experience these as product states, not framework implementation details; docs: [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **Expected vs unexpected errors**: Validation failures should not behave like crashes
  - Design mutation APIs and form state so domain errors stay in the normal UI flow; docs: [Error Handling](https://nextjs.org/docs/app/getting-started/error-handling), [React `<form>`](https://react.dev/reference/react-dom/components/form).

**Practice**: Add loading, validation, unauthorized, and not-found states to the same feature and make each state visually distinct and testable.

---

### 2.5 Metadata, Fonts, Images, and CSS

- **Metadata API**: Static and dynamic metadata via `metadata` and `generateMetadata()`
  - Treat metadata as part of the route contract, not as random SEO garnish you remember later; docs: [Metadata and OG images](https://nextjs.org/docs/app/getting-started/metadata-and-og-images), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Metadata files**: `robots.txt`, `sitemap.xml`, icons, `manifest.json`, OG/Twitter images
  - These are part of production readiness for search, sharing, installability, and crawl control; docs: [Metadata Files](https://nextjs.org/docs/app/api-reference/file-conventions/metadata).
- **`next/font`**: Use built-in font optimization before reaching for ad hoc font loading
  - Fonts are one of the cleanest wins for performance and consistency in a Next.js app; docs: [Font Optimization](https://nextjs.org/docs/app/getting-started/font-optimization), [`Font`](https://nextjs.org/docs/app/api-reference/components/font).
- **`next/image`**: Optimize image delivery and avoid layout shift
  - Images are where performance, responsiveness, and Core Web Vitals often intersect most visibly; docs: [Image Optimization](https://nextjs.org/docs/app/getting-started/image-optimization), [`Image`](https://nextjs.org/docs/app/api-reference/components/image).
- **CSS options**: Global CSS, CSS Modules, Tailwind, Sass, CSS-in-JS
  - Pick a styling system intentionally and keep it consistent; mixing too many approaches is a maintainability tax; docs: [CSS](https://nextjs.org/docs/app/getting-started/css), [Tailwind CSS](https://nextjs.org/docs/app/guides/tailwind-css), [Sass](https://nextjs.org/docs/app/guides/sass), [CSS-in-JS](https://nextjs.org/docs/app/guides/css-in-js).

**Practice**: Build a route with dynamic metadata, a generated OG image, optimized images, and locally hosted fonts. Measure layout stability before and after.

---

## Phase 3: Data Fetching, Caching, and Rendering

### 3.1 Fetching Data in Server Components

- **Fetch where the data is used**: Server Components are a great place to read from databases, CMS APIs, and internal services directly
  - The big shift is that many reads no longer need a client effect or an internal API hop; docs: [Fetching Data](https://nextjs.org/docs/app/getting-started/fetching-data), [React Server Components](https://react.dev/reference/rsc/server-components).
- **Prefer direct server reads over calling your own Route Handler from the server**
  - If the caller is already on the server, an extra HTTP hop usually adds complexity, latency, and authorization duplication for no benefit; docs: [Backend for Frontend](https://nextjs.org/docs/app/guides/backend-for-frontend), [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers-and-middleware).
- **Parallelize independent data fetching**: Start work early, suspend where needed
  - Data waterfalls are one of the main things that make server-rendered apps feel slow; docs: [Fetching Data](https://nextjs.org/docs/app/getting-started/fetching-data), [Streaming](https://nextjs.org/docs/app/guides/streaming).
- **Learn request memoization and data reuse**: The same read should not surprise you with repeated work
  - Understanding what is memoized, cached, or recomputed is how you stop guessing about performance; docs: [Caching](https://nextjs.org/docs/app/getting-started/caching), [How Revalidation Works](https://nextjs.org/docs/app/guides/how-revalidation-works).

**Practice**: Build a dashboard page that fetches profile, notifications, and analytics in parallel, then stream the slowest widget separately behind Suspense.

---

### 3.2 Rendering Model: Static, Dynamic, and Streaming

- **Stop thinking only in old SSR/SSG labels**: Modern Next.js blends pre-rendering, streaming, and cached work by segment and data boundary
  - The framework is increasingly about choosing freshness and latency characteristics deliberately, not picking one global rendering mode; docs: [Rendering Philosophy](https://nextjs.org/docs/app/guides/rendering-philosophy), [Streaming](https://nextjs.org/docs/app/guides/streaming).
- **Dynamic rendering is a choice with costs**: Request-time work buys freshness and per-user behavior, but increases runtime dependency on your infrastructure
  - Use dynamic rendering when the response genuinely depends on request data, auth, headers, cookies, or fast-changing data.
- **Streaming matters**: Send useful UI before every slow dependency resolves
  - Streaming is one of the biggest reasons modern Next.js can feel fast even when some data is slow; docs: [Streaming](https://nextjs.org/docs/app/guides/streaming), [Suspense](https://react.dev/reference/react/Suspense).
- **Runtime choices matter**: Node.js vs Edge runtime and segment config change what APIs, latencies, and deployment tradeoffs exist
  - Routing and rendering decisions are partly deployment decisions now; docs: [Route Segment Config](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config), [Self-Hosting](https://nextjs.org/docs/app/guides/self-hosting).

**Practice**: Take one route and implement it three ways: fully dynamic, aggressively cached, and streamed with slow sub-sections split behind Suspense. Compare UX and server cost.

---

### 3.3 Caching Deep Dive

- **Learn the current cache model, not outdated heuristics**: The official docs now separate the current Cache Components model from the previous caching model
  - You need both because greenfield apps may use the current model while existing codebases may still use the older one; docs: [Caching](https://nextjs.org/docs/app/getting-started/caching), [Caching (Previous Model)](https://nextjs.org/docs/app/guides/caching).
- **`fetch` assumptions changed**: Do not assume every server `fetch()` is automatically cached
  - Study the official caching behavior carefully instead of relying on old blog-post mental models; docs: [Caching](https://nextjs.org/docs/app/getting-started/caching).
- **`'use cache'`, `cacheLife`, and tags**: These are the current primitives to understand for cacheable work
  - Caching is best when it is explicit enough that you can explain freshness guarantees to a teammate; docs: [`use cache`](https://nextjs.org/docs/app/api-reference/directives/use-cache), [`cacheLife`](https://nextjs.org/docs/app/api-reference/functions/cacheLife), [`cacheTag`](https://nextjs.org/docs/app/api-reference/functions/cacheTag).
- **Cache Components are an advanced model, not trivia**
  - Learn when to cache a whole computation, when to tag data, and when not to cache at all; docs: [Revalidating](https://nextjs.org/docs/app/getting-started/revalidating), [Migrating to Cache Components](https://nextjs.org/docs/app/guides/migrating-to-cache-components).

**Practice**: Build a blog listing with cache tags and a separate admin path that can invalidate exactly the affected content.

---

### 3.4 Revalidation and Freshness

- **Time-based revalidation**: Use `cacheLife` when stale-for-a-while is acceptable
  - This is the right fit when content changes predictably or freshness windows are a product-level decision, not a per-user guarantee; docs: [Revalidating](https://nextjs.org/docs/app/getting-started/revalidating).
- **On-demand revalidation**: `revalidateTag`, `updateTag`, `revalidatePath`
  - Learn the difference between background refresh and immediate read-your-own-writes behavior; docs: [`revalidateTag`](https://nextjs.org/docs/app/api-reference/functions/revalidateTag), [`updateTag`](https://nextjs.org/docs/app/api-reference/functions/updateTag), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Prefer precise invalidation**: Tags usually age better than path-level invalidation
  - Path-based invalidation is sometimes necessary, but tag-based invalidation maps better to domain entities and avoids over-refreshing unrelated UI; docs: [Revalidating](https://nextjs.org/docs/app/getting-started/revalidating).
- **Freshness rules are architecture**: Document them
  - A team should be able to say which parts of the app can be stale, for how long, and what user action refreshes them.

**Practice**: Create an edit form that updates one record, returns the user to the detail page, and guarantees they see the fresh value immediately.

---

### 3.5 Route Handlers and Backend-for-Frontend Patterns

- **`route.ts` gives you HTTP endpoints in App Router**
  - Use Route Handlers for webhooks, file uploads, third-party integrations, or APIs genuinely consumed over HTTP; docs: [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers-and-middleware), [Backend for Frontend](https://nextjs.org/docs/app/guides/backend-for-frontend).
- **Use the Web Request/Response APIs directly**
  - This keeps you close to the platform and makes behavior easier to reason about across runtimes; docs: [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers-and-middleware), [`NextResponse`](https://nextjs.org/docs/app/api-reference/functions/next-response), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Keep Route Handlers focused**: They are not a replacement for your data layer
  - Business logic and authorization should stay reusable and testable outside the HTTP wrapper.
- **Webhooks are a first-class use case**
  - This is where you practice signature verification, idempotency, retries, and explicit failure responses.

**Practice**: Build a webhook endpoint that updates cached content and records delivery attempts safely.

---

## Phase 4: Mutations, Forms, and Server Functions

### 4.1 Server Functions and Server Actions

- **Server Functions are the write primitive to learn first**
  - Modern Next.js mutations are centered on server-side functions invoked from forms or transitions, not on hand-written client fetch wrappers by default; docs: [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data), [React Server Functions](https://react.dev/reference/rsc/server-functions).
- **`'use server'` can be function-level or file-level**
  - Choose the scope intentionally so feature code stays readable and imports stay legal from client code where needed; docs: [`'use server'`](https://react.dev/reference/rsc/use-server), [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data).
- **A Server Action is a Server Function used in an action or mutation context**
  - Knowing this terminology difference helps you read both React and Next.js docs accurately; docs: [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data).
- **Treat every Server Function argument as untrusted input**
  - The function may feel local in code, but it behaves like a public endpoint and still needs validation and authorization; docs: [`'use server'`](https://react.dev/reference/rsc/use-server), [Data Security](https://nextjs.org/docs/app/guides/data-security).
- **Keep auth checks close to the write path**
  - Do not assume that hiding a button in the UI is meaningful authorization.

**Practice**: Replace a client `fetch('/api/...')` mutation with a Server Function and compare the amount of client code you can delete.

---

### 4.2 Forms as the Default Mutation Surface

- **Use real HTML forms first**: `<form action={serverFn}>`
  - This gives you progressive enhancement, accessibility, and a clearer write path than many custom click handlers; docs: [Forms](https://nextjs.org/docs/app/guides/building-forms), [React `<form>`](https://react.dev/reference/react-dom/components/form).
- **`useActionState`**: Keep server-returned validation or mutation state in the UI
  - This is one of the cleanest ways to show field-level or submission-level errors without inventing a second state machine; docs: [`useActionState`](https://react.dev/reference/react/useActionState).
- **`useFormStatus`**: Show pending state in a child component of the form
  - Good pending-state UX is part of correctness because it prevents duplicate submits and confusing feedback loops; docs: [`useFormStatus`](https://react.dev/reference/react-dom/hooks/useFormStatus).
- **`formAction` on buttons**: One form can support multiple submit behaviors
  - This is powerful for publish/save-draft, delete/archive, or primary/secondary mutation flows; docs: [React `<form>`](https://react.dev/reference/react-dom/components/form), [React `<input>`](https://react.dev/reference/react-dom/components/input).
- **Server-side validation is non-negotiable**
  - Even if you add client hints, the server owns the real validation and authorization boundary.

**Practice**: Build a create/edit form with server validation, inline field errors, disabled pending state, and a separate "Save draft" button using `formAction`.

---

### 4.3 Optimistic UI and Pending Work

- **`useOptimistic`**: Show the likely future UI before the server confirms it
  - Use this for fast-feeling interfaces, but only when you can clearly define rollback behavior; docs: [`useOptimistic`](https://react.dev/reference/react/useOptimistic).
- **Transitions around non-urgent mutations**: `startTransition` or action props
  - React automatically wraps many form action flows, but you should still understand when a manual transition is required; docs: [`startTransition`](https://react.dev/reference/react/startTransition), [`useActionState`](https://react.dev/reference/react/useActionState).
- **Pending state is product design**: Buttons, inline spinners, optimistic rows, and disabled controls should reflect actual mutation lifecycle
  - Ambiguous submission state is how users accidentally create duplicates or lose trust.
- **Idempotency matters**: Especially for payments, invitations, and webhook-driven updates
  - Build writes so retries are safe. Production will force this lesson eventually; learn it on purpose.

**Practice**: Add optimistic comment creation with rollback on failure, plus an idempotent server write that prevents double submission.

---

### 4.4 Cookies, Headers, Redirects, and Draft Mode

- **`cookies()` and `headers()`**: Read request context on the server
  - These are core tools for auth, personalization, feature gating, locale, and experiments; docs: [`headers`](https://nextjs.org/docs/app/api-reference/functions/headers), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Redirect after writes**: `redirect()` and `permanentRedirect()`
  - Post/redirect/get is still a healthy default pattern when it keeps your mutation flow simpler and more durable; docs: [`redirect`](https://nextjs.org/docs/app/api-reference/functions/redirect), [`permanentRedirect`](https://nextjs.org/docs/app/api-reference/functions/permanentRedirect).
- **`refresh()`**: Learn when a refresh is the right follow-up after a mutation
  - It can simplify some UI flows, but do not use it as a substitute for understanding revalidation; docs: [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).
- **Draft Mode**: Preview unpublished content intentionally
  - Draft Mode is how editorial, preview, and CMS workflows become first-class instead of awkward local hacks; docs: [Draft Mode](https://nextjs.org/docs/app/guides/draft-mode), [API Reference: Functions](https://nextjs.org/docs/app/api-reference/functions).

**Practice**: Build a CMS preview flow with a Route Handler that enables Draft Mode, a preview page, and a secure exit-preview action.

---

## Phase 5: Client State and Interaction Patterns

### 5.1 Choosing the Right State Location

- **Server data belongs on the server until proven otherwise**
  - The fastest path to tangled state is duplicating fetched server truth in client stores just because you are used to SPA patterns.
- **URL state for filters, sorts, tabs, and pagination**
  - This gives you deep links, browser history, and server-aware rendering for free; docs: [`useSearchParams`](https://nextjs.org/docs/app/api-reference/functions/use-search-params), [Preserving UI State](https://nextjs.org/docs/app/guides/preserving-ui-state).
- **Local state for ephemeral UI only**
  - Dialog open state, input drafts, hover state, temporary selections, and animation state usually belong locally.
- **Context for ambient concerns, not general server data**
  - Theme, locale, and client-only shell preferences are better fits than everything your backend ever returns; docs: [Passing Data Deeply with Context](https://react.dev/learn/passing-data-deeply-with-context).

**Practice**: Audit a medium-sized feature and label every piece of state as server, URL, local, or context. Then simplify the ones living in the wrong place.

---

### 5.2 React Hooks That Pull Their Weight in Next.js

- **`useTransition`**: Keep interactions responsive during slower updates
  - This is especially useful in search, filters, tab switches, and client-initiated transitions; docs: [`useTransition`](https://react.dev/reference/react/useTransition).
- **`useDeferredValue`**: Let expensive UI lag behind fast input
  - This is a great fit for typeahead lists, large client filters, and search result panes; docs: [`useDeferredValue`](https://react.dev/reference/react/useDeferredValue).
- **`useActionState` and `useFormStatus`**: Prefer them over hand-rolled submit state when using forms
  - They align your UI state with React's action model instead of fighting it; docs: [`useActionState`](https://react.dev/reference/react/useActionState), [`useFormStatus`](https://react.dev/reference/react-dom/hooks/useFormStatus).
- **Custom hooks still matter**
  - Next.js changes rendering and data boundaries, not the value of extracting reusable interaction logic.

**Practice**: Build a search page that stores the query in the URL, uses `useDeferredValue` for a slow client-side summary panel, and uses a transition for route updates.

---

### 5.3 Lazy Loading and Third-Party Libraries

- **Lazy loading is about bundle ownership**
  - Heavy editors, charts, maps, and browser-only widgets should not quietly land in your critical path; docs: [Lazy Loading](https://nextjs.org/docs/app/guides/lazy-loading).
- **Use client boundaries for browser-only libraries**
  - Libraries that depend on `window`, DOM measurement, or imperative widgets should be isolated to Client Components.
- **`next/dynamic` and code splitting**
  - Learn when to dynamically import components, and when you are better off redesigning the UI boundary instead; docs: [Lazy Loading](https://nextjs.org/docs/app/guides/lazy-loading).
- **Third-party libraries still need architectural discipline**
  - Wrapping a complicated library in a focused component boundary often matters more than the library choice itself; docs: [Third Party Libraries](https://nextjs.org/docs/app/guides/third-party-libraries).

**Practice**: Add a rich text editor or chart only on the route that uses it, and verify it does not affect the main dashboard bundle.

---

### 5.4 Interaction Patterns Worth Practicing

- **Debounced search + URL state + deferred UI**
  - This combination shows you understand fast input, server routing, and async display work as separate concerns.
- **Modal routes instead of global modal state**
  - Intercepting routes often produce cleaner history behavior and shareable URLs than app-wide modal toggles.
- **Optimistic tables and inline edits**
  - This is a high-value exercise in pending states, rollback, and read-your-own-writes cache behavior.
- **Progressive enhancement mindset**
  - Ask whether the core workflow still works if JavaScript loads late or fails.

**Practice**: Build a quick-edit modal over a table row using intercepting routes and optimistic updates backed by Server Actions.

---

## Phase 6: Security and Authentication

### 6.1 Environment Variables and Secret Boundaries

- **Environment variable load order matters**
  - You need a precise mental model for local, preview, test, and production configuration if you want stable deployments; docs: [Environment Variables](https://nextjs.org/docs/app/guides/environment-variables).
- **`NEXT_PUBLIC_` means browser-visible**
  - Treat that prefix as a security boundary, not a convenience naming trick; docs: [Environment Variables](https://nextjs.org/docs/app/guides/environment-variables).
- **Keep secrets server-side**
  - Server Components can access privileged data safely, but Client Components must be treated like browser code even when pre-rendered on the server; docs: [Data Security](https://nextjs.org/docs/app/guides/data-security).
- **Use `server-only` patterns for private modules**
  - Make it harder to accidentally import secret-bearing code into the client graph.

**Practice**: Audit your environment variables and annotate which are server-only, which are safe to expose, and which should not exist at all.

---

### 6.2 Authentication, Sessions, and Authorization

- **Separate auth concepts clearly**: authentication, session management, authorization
  - Keeping these distinct makes route guards, data access rules, and UI conditionals much easier to reason about; docs: [Authentication](https://nextjs.org/docs/app/guides/authentication).
- **Do most authorization near the data source**
  - The official auth guide explicitly pushes security checks close to data access rather than only at the route layer; docs: [Authentication](https://nextjs.org/docs/app/guides/authentication).
- **Use a Data Access Layer and DTOs**
  - Centralizing auth-sensitive reads is one of the clearest ways to avoid leaking too much data to the wrong UI surface; docs: [Authentication](https://nextjs.org/docs/app/guides/authentication), [Data Security](https://nextjs.org/docs/app/guides/data-security).
- **Optimistic checks vs secure checks**
  - UI redirects and shell gating are useful, but sensitive operations still need authoritative server-side checks.
- **Prefer mature auth libraries in production**
  - Learn the framework concepts first, then adopt a maintained auth library rather than inventing session management casually; docs: [Authentication](https://nextjs.org/docs/app/guides/authentication).

**Practice**: Build a login flow, protect dashboard routes, and enforce per-record authorization in the data layer instead of only in the page component.

---

### 6.3 Proxy, Redirects, and Request-Time Policies

- **Proxy is the new name for Middleware in Next.js 16**
  - Learn the new terminology because you will see both in the wild, but current docs call it Proxy; docs: [Proxy](https://nextjs.org/docs/app/getting-started/proxy).
- **Use Proxy for request-time decisions**
  - Redirects, rewrites, header manipulation, experiments, and optimistic auth checks are great fits; docs: [Proxy](https://nextjs.org/docs/app/getting-started/proxy).
- **Do not turn Proxy into your full auth system**
  - The official docs are clear that Proxy should not do slow data fetching or replace real authorization; docs: [Proxy](https://nextjs.org/docs/app/getting-started/proxy).
- **Prefer `next.config` redirects when request data is not needed**
  - Simpler tools age better than clever ones; docs: [`next.config.js`](https://nextjs.org/docs/app/api-reference/config/next-config-js), [Redirecting](https://nextjs.org/docs/app/guides/redirecting).

**Practice**: Add a Proxy that redirects unauthenticated users away from `/dashboard`, but keep the real data authorization in the server read path.

---

### 6.4 CSP, Server Action Security, and Data Exposure

- **Content Security Policy is worth learning early**
  - CSP changes how you think about scripts, nonces, static rendering, and third-party integrations; docs: [Content Security Policy](https://nextjs.org/docs/app/guides/content-security-policy).
- **Server Actions are public HTTP endpoints**
  - Even if the call site feels local, the security model is validate, authorize, and fail safely on every mutation; docs: [Data Security](https://nextjs.org/docs/app/guides/data-security), [`'use server'`](https://react.dev/reference/rsc/use-server).
- **Closed-over values are protected, but not a substitute for auth**
  - The docs call out encryption of closed-over variables, but you still should not rely on obscurity or transport protections alone; docs: [Data Security](https://nextjs.org/docs/app/guides/data-security).
- **Know the advanced tools**: tainting, custom action encryption key behavior, SRI, nonce-based CSP
  - You may not need them on day one, but security-sensitive apps eventually will.

**Practice**: Add a strict CSP to a route, then make the minimum rendering and script-loading changes needed to keep the page functioning.

---

## Phase 7: Testing and Debugging

### 7.1 Type Checking, Linting, and Build Gates

- **`next build` is a real quality gate**
  - Next.js can fail production builds on TypeScript or ESLint errors, which is a gift if you use it intentionally; docs: [TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript), [ESLint Plugin](https://nextjs.org/docs/app/api-reference/config/eslint).
- **Run `tsc --noEmit` and lint in CI**
  - Keep local iteration fast, but make the pipeline non-negotiable.
- **Treat route typing as a test surface**
  - Compile-time guarantees on navigation and params reduce the need for a whole category of runtime tests.

**Practice**: Add CI that runs type-check, lint, unit tests, and an end-to-end smoke suite on every pull request.

---

### 7.2 Unit and Component Testing

- **Vitest is a strong default for unit tests**
  - It fits modern frontend workflows well, but learn the current limitations with async Server Components; docs: [Vitest with Next.js](https://nextjs.org/docs/app/guides/testing/vitest).
- **Know the official caveat**: Vitest currently does not support async Server Components well for unit tests
  - This is a great example of why framework-specific testing guidance matters; docs: [Vitest with Next.js](https://nextjs.org/docs/app/guides/testing/vitest).
- **Jest remains an option**
  - Be able to read either setup in existing codebases; docs: [Jest with Next.js](https://nextjs.org/docs/app/guides/testing/jest).
- **Test pure logic aggressively**
  - Validation, auth rules, DTO shaping, and formatter utilities are often the easiest high-confidence tests in a Next.js app.

**Practice**: Unit test your validation, authorization helpers, and sync components. Move one hard-to-test async Server Component scenario up to E2E instead of forcing it into the wrong layer.

---

### 7.3 End-to-End Testing with Playwright

- **E2E tests matter more in App Router apps**
  - Routing, streaming, forms, revalidation, and auth flows often need browser-level verification; docs: [Testing](https://nextjs.org/docs/app/guides/testing), [Playwright with Next.js](https://nextjs.org/docs/app/guides/testing/playwright).
- **Test the unhappy paths too**
  - Pending buttons, invalid input, not-found flows, auth redirects, and stale cache refreshes are where production bugs usually live.
- **Use E2E to validate progressive enhancement**
  - Server form flows and navigation boundaries are good candidates for realistic browser tests.

**Practice**: Write Playwright tests for login, create/edit/delete, optimistic UI rollback, and a streaming page with loading states.

---

### 7.4 Debugging, Instrumentation, and Web Vitals

- **Use the official debugging guide**
  - Next.js spans server and client code, so your debugging workflow should too; docs: [Debugging](https://nextjs.org/docs/app/guides/debugging).
- **`instrumentation.ts` and `instrumentation-client.ts`**
  - Learn these because observability and startup hooks become important faster than most teams expect; docs: [Instrumentation](https://nextjs.org/docs/app/guides/instrumentation), [File-system conventions](https://nextjs.org/docs/app/api-reference/file-conventions).
- **`useReportWebVitals` and `webVitalsAttribution`**
  - Measure performance before optimizing blindly; docs: [`useReportWebVitals`](https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals), [`next.config.js`](https://nextjs.org/docs/app/api-reference/config/next-config-js).
- **React DevTools and browser DevTools still matter**
  - Framework abstractions do not replace understanding the component tree, network, layout shifts, and JavaScript cost.

**Practice**: Trace one slow page from network to render, collect Web Vitals, and identify whether the bottleneck is data, client bundle size, or UI blocking.

---

## Phase 8: Performance, SEO, and Accessibility

### 8.1 Performance Primitives

- **Image, font, and script optimization are table stakes**
  - Next.js gives you built-in tools here, so performance regressions in these areas are often preventable; docs: [Image Optimization](https://nextjs.org/docs/app/getting-started/image-optimization), [Font Optimization](https://nextjs.org/docs/app/getting-started/font-optimization), [`Script`](https://nextjs.org/docs/app/api-reference/components/script).
- **Prefetching and navigation cache behavior matter**
  - Good navigation performance is not just about the initial page load; docs: [Prefetching](https://nextjs.org/docs/app/guides/prefetching), [Linking and Navigating](https://nextjs.org/docs/app/getting-started/linking-and-navigating).
- **Streaming often beats brute-force client optimization**
  - If the page can reveal useful UI earlier, that is often a more meaningful win than micro-optimizing a single render path.
- **Bundle ownership is product ownership**
  - If a route feels slow, know which libraries and boundaries made it that way.

**Practice**: Improve a slow page by removing one unnecessary client boundary, streaming a slow section, and deferring a heavyweight widget.

---

### 8.2 Metadata, Crawlability, and Structured Content

- **Metadata API is your SEO foundation**
  - Titles, descriptions, canonical URLs, and social images should live with the route that owns them; docs: [Metadata and OG images](https://nextjs.org/docs/app/getting-started/metadata-and-og-images).
- **Robots and sitemaps are part of production architecture**
  - Do not bolt them on at launch week; docs: [Metadata Files](https://nextjs.org/docs/app/api-reference/file-conventions/metadata).
- **JSON-LD support is worth learning for content-heavy and commerce apps**
  - Structured data helps you turn domain entities into richer search visibility; docs: [JSON-LD](https://nextjs.org/docs/app/guides/json-ld).
- **Static export is a special case, not the default answer**
  - Learn the tradeoffs before choosing it for SEO alone; docs: [Static Exports](https://nextjs.org/docs/app/guides/static-exports).

**Practice**: Add metadata, a sitemap, `robots.txt`, and JSON-LD to a blog or product detail page and verify the output in page source.

---

### 8.3 Web Vitals and Analytics

- **Measure Core Web Vitals continuously**
  - Performance is much easier to maintain than to rescue after months of regressions; docs: [Analytics](https://nextjs.org/docs/app/guides/analytics), [`useReportWebVitals`](https://nextjs.org/docs/app/api-reference/functions/use-report-web-vitals).
- **Track attribution, not just aggregate scores**
  - Knowing which route, script, or render path is responsible is what makes the metric actionable; docs: [`next.config.js`](https://nextjs.org/docs/app/api-reference/config/next-config-js).
- **Client instrumentation belongs in the design**
  - Analytics, error tracking, and UX measurement are easier to maintain when they are deliberate, not copy-pasted snippets.

**Practice**: Instrument one route for Web Vitals and record before/after numbers for an optimization you made.

---

### 8.4 Accessibility

- **Lean on semantic HTML first**
  - Good forms, buttons, links, headings, and landmarks solve more accessibility problems than custom widgets do; docs: [React Accessibility](https://react.dev/learn/accessibility).
- **Focus management matters in routed UIs**
  - Modals, not-found states, inline errors, and intercepted routes can all create disorienting keyboard behavior if you ignore focus flow.
- **Treat loading and error states as accessibility surfaces**
  - Screen readers and keyboard users experience async UI differently, so test those states deliberately.
- **Use the WAI-ARIA Authoring Practices only when native elements are not enough**
  - Complex widgets are harder than they look; docs: [WAI-ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/).

**Practice**: Run keyboard-only and screen-reader passes on your capstone routes, especially forms, modals, and dynamically updated lists.

---

## Phase 9: Deployment and Operations

### 9.1 Deployment Targets

- **Vercel is the simplest reference deployment target**
  - Even if you deploy elsewhere, Vercel docs are useful for understanding the happy path and platform assumptions; docs: [Deploying](https://nextjs.org/docs/app/getting-started/deploying), [Vercel Docs](https://vercel.com/docs).
- **Self-hosting has different responsibilities**
  - Reverse proxies, streaming support, image optimization, runtime process management, and security hardening become more visible when you own the platform; docs: [Self-Hosting](https://nextjs.org/docs/app/guides/self-hosting).
- **Static export is powerful but constrained**
  - Use it when the product truly fits, not because it feels simpler on paper; docs: [Static Exports](https://nextjs.org/docs/app/guides/static-exports).
- **Adapters and platform guides matter when you leave the default path**
  - Deployment architecture is not an afterthought in modern Next.js; docs: [Deploying to Platforms](https://nextjs.org/docs/app/guides/deploying-to-platforms), [Adapters](https://nextjs.org/docs/app/api-reference/adapters).

**Practice**: Deploy the same project once to Vercel and once to a self-hosted environment. Compare what breaks, what needs config, and what assumptions change.

---

### 9.2 CI/CD and Build Caching

- **Cache Next.js builds in CI**
  - Build caching can dramatically reduce pipeline time and cost when configured correctly; docs: [CI Build Caching](https://nextjs.org/docs/app/guides/ci-build-caching).
- **Separate build-time and runtime config**
  - Deployment bugs often come from not knowing what is baked into the build versus read at request time.
- **Preview environments are part of the workflow**
  - Modern Next.js apps benefit from seeing route behavior, metadata, and auth flows in a near-real environment before merge.

**Practice**: Configure CI to cache builds, run the test pipeline, and produce a preview deployment for pull requests.

---

### 9.3 Observability with OpenTelemetry and Instrumentation

- **OpenTelemetry is the official observability path Next.js highlights**
  - You want traces, not just logs, once request chains span multiple services; docs: [OpenTelemetry](https://nextjs.org/docs/app/guides/open-telemetry).
- **Instrument both server and client strategically**
  - Route performance, external API calls, and mutation latency are all good candidates for visibility.
- **Know the difference between framework spans and domain spans**
  - The framework gives you baseline tracing; real product debugging needs app-specific spans too.

**Practice**: Add a custom span around a slow server read and verify it appears alongside framework spans in your telemetry backend.

---

### 9.4 Scaling Patterns

- **Multi-tenant and multi-zone setups are explicit design choices**
  - They affect routing, caching, auth boundaries, and deployment topology from day one; docs: [Multi-tenant](https://nextjs.org/docs/app/guides/multi-tenant), [Multi-zones](https://nextjs.org/docs/app/guides/multi-zones).
- **CDN caching and regional behavior matter**
  - Performance at scale is partly a data locality and invalidation problem, not just a React problem; docs: [CDN Caching](https://nextjs.org/docs/app/guides/cdn-caching).
- **Know your runtime limits**
  - `maxDuration`, preferred regions, and hosting-specific constraints should inform feature design, not surprise you during incidents; docs: [Route Segment Config](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config).

**Practice**: Design a multi-tenant SaaS route plan and document where tenant resolution, cache keys, and auth checks happen.

---

## Phase 10: Real-World Next.js Ecosystem

### 10.1 MDX, Docs, and Content-Driven Apps

- **MDX is a great way to learn content-heavy Next.js apps**
  - It forces you to think about routing, metadata, content pipelines, and interactive components together; docs: [MDX](https://nextjs.org/docs/app/guides/mdx).
- **Docs sites and knowledge bases are strong practice projects**
  - They exercise navigation, search, static content, metadata, and build-time content transforms without requiring a massive backend.

### 10.2 Internationalization, Public Pages, and Marketing Surfaces

- **Internationalization changes routing, metadata, formatting, and deployment assumptions**
  - Treat i18n as architecture, not string replacement; docs: [Internationalization](https://nextjs.org/docs/app/guides/internationalization).
- **Public pages deserve their own routing and caching strategy**
  - Marketing and logged-in surfaces usually have different performance and auth needs; docs: [Public Pages](https://nextjs.org/docs/app/guides/public-pages).

### 10.3 Styling, Scripts, and Third-Party Integration

- **Tailwind, Sass, CSS-in-JS, and third-party scripts are all supported, but each has tradeoffs**
  - Pick the smallest set that fits the product and team, then get very good at it; docs: [Tailwind CSS](https://nextjs.org/docs/app/guides/tailwind-css), [Sass](https://nextjs.org/docs/app/guides/sass), [CSS-in-JS](https://nextjs.org/docs/app/guides/css-in-js), [Scripts](https://nextjs.org/docs/app/guides/scripts).
- **Third-party libraries should respect server/client boundaries**
  - A library that works in a Client Component may be a bad fit in a Server Component-heavy route; docs: [Third Party Libraries](https://nextjs.org/docs/app/guides/third-party-libraries).

### 10.4 PWAs, Static Exports, and Platform Features

- **PWA support, static exports, and package bundling are specialized tools**
  - Learn them after the core routing/data model is comfortable, not before; docs: [PWAs](https://nextjs.org/docs/app/guides/progressive-web-apps), [Static Exports](https://nextjs.org/docs/app/guides/static-exports), [Package Bundling](https://nextjs.org/docs/app/guides/package-bundling).

### 10.5 Upgrading and Codemods

- **Stay current on upgrades**
  - Next.js evolves quickly, and routing/caching terminology can shift between versions; docs: [Upgrading](https://nextjs.org/docs/app/getting-started/upgrading), [Codemods](https://nextjs.org/docs/app/guides/upgrading/codemods).
- **Read release notes before a major version jump**
  - This is especially important around caching, routing conventions, and runtime behavior.
- **Know the terminology drift**
  - Example: Next.js 16 renames Middleware to Proxy, while older code and blog posts still say Middleware; docs: [Proxy](https://nextjs.org/docs/app/getting-started/proxy).

---

## Capstone Projects

Build these to demonstrate job-ready Next.js skills:

### Project 1: SaaS Admin Dashboard

- Authenticated App Router dashboard with nested layouts
  - Use route groups, persistent shells, and protected pages to show you understand structure as well as UI; docs: [Layouts and Pages](https://nextjs.org/docs/app/getting-started/layouts-and-pages), [Authentication](https://nextjs.org/docs/app/guides/authentication).
- URL-driven filters, sorting, and pagination
  - This proves you can build shareable admin workflows instead of fragile local-state-only tables; docs: [`useSearchParams`](https://nextjs.org/docs/app/api-reference/functions/use-search-params).
- Server Actions for create/edit/archive workflows
  - Use real forms, pending state, and validation instead of hand-built mutation plumbing; docs: [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data), [Forms](https://nextjs.org/docs/app/guides/building-forms).
- Cached dashboard widgets with precise invalidation
  - Show that you understand freshness, not just data loading; docs: [Caching](https://nextjs.org/docs/app/getting-started/caching), [Revalidating](https://nextjs.org/docs/app/getting-started/revalidating).
- Playwright suite covering auth and mutations
  - This should verify the flows users actually depend on; docs: [Playwright with Next.js](https://nextjs.org/docs/app/guides/testing/playwright).

This project is strong because it exercises route composition, auth, mutations, URL state, and cache invalidation in one realistic internal-tool surface. Strong implementations feel boring in the best way: fast, predictable, and hard to break.

### Project 2: E-Commerce Storefront

- Product listing and detail pages with optimized images, metadata, and structured data
  - Commerce is where performance, SEO, and shareability all matter at once; docs: [Image Optimization](https://nextjs.org/docs/app/getting-started/image-optimization), [Metadata and OG images](https://nextjs.org/docs/app/getting-started/metadata-and-og-images), [JSON-LD](https://nextjs.org/docs/app/guides/json-ld).
- Cart and checkout interactions with optimistic UI
  - This is where you practice balancing server truth with fast-feeling client feedback; docs: [`useOptimistic`](https://react.dev/reference/react/useOptimistic), [Forms](https://nextjs.org/docs/app/guides/building-forms).
- Webhook-driven inventory or order updates
  - Route Handlers and idempotency matter a lot here; docs: [Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers-and-middleware).
- Draft Mode or preview flows for merchandising content
  - This shows you can support editorial workflows, not just shopper flows; docs: [Draft Mode](https://nextjs.org/docs/app/guides/draft-mode).

This project is useful because it forces you to handle public content, personalized state, cache freshness, and production SEO together. The hard part is not building pages; it is keeping them fast and correct under changing inventory and content.

### Project 3: Content Platform / Knowledge Base

- MDX or CMS-driven content with nested docs routes
  - Content-heavy apps are a great way to practice App Router organization and metadata discipline; docs: [MDX](https://nextjs.org/docs/app/guides/mdx).
- Search, sidebar navigation, and intercepting-route previews
  - This mixes docs-site UX with real route design.
- Draft previews, role-aware editing paths, and audit-friendly mutations
  - This gives you a venue for auth, content workflows, and progressive enhancement; docs: [Authentication](https://nextjs.org/docs/app/guides/authentication), [Updating Data](https://nextjs.org/docs/app/getting-started/updating-data).
- Sitemaps, robots, OG images, and JSON-LD
  - This proves you know the production details that make content discoverable; docs: [Metadata Files](https://nextjs.org/docs/app/api-reference/file-conventions/metadata), [JSON-LD](https://nextjs.org/docs/app/guides/json-ld).

This project tests whether you can build a polished, content-first Next.js app instead of only dashboard-style CRUD. Strong implementations show good route structure, careful metadata, fast navigation, and editorial ergonomics.

---

## Study Methodology

1. **Read the official Next.js docs first** — use this guide as the roadmap and the docs as the textbook
   - The official docs are the fastest way to build the right mental model for App Router, Server Components, and caching; docs: [Next.js Docs](https://nextjs.org/docs), [App Router Getting Started](https://nextjs.org/docs/app/getting-started).
2. **Learn App Router deeply before spending much time on Pages Router**
   - Pages Router knowledge is useful for maintenance, but App Router is the modern model you need to be productive in new code.
3. **Default to server, then add client code deliberately**
   - This single habit prevents a lot of unnecessary bundle weight and effect-heavy code.
4. **Build forms and mutations the framework way**
   - Learn real forms, Server Actions, pending state, and revalidation before abstracting them away.
5. **Use the URL as state whenever it improves shareability or restoreability**
   - Search, filters, tabs, and pagination are better when refresh and back/forward buttons keep working.
6. **Treat caching as part of the product spec**
   - For every route, decide what can be stale, for how long, and what should invalidate it.
7. **Test flows, not just functions**
   - Modern Next.js behavior is often about navigation, streaming, auth, and browser semantics as much as isolated utilities.
8. **Upgrade regularly**
   - Smaller, steady upgrades are much easier than relearning the framework after several major releases.

---

## Additional Reference Links

- **Next.js core references**:
  - [Next.js Docs Home](https://nextjs.org/docs)
  - [App Router Getting Started](https://nextjs.org/docs/app/getting-started)
  - [API Reference](https://nextjs.org/docs/app/api-reference)
  - [Guides](https://nextjs.org/docs/app/guides)
  - [Production Checklist](https://nextjs.org/docs/app/guides/production-checklist)
- **React references that matter most in Next.js**:
  - [React Learn](https://react.dev/learn)
  - [Server Components](https://react.dev/reference/rsc/server-components)
  - [Server Functions](https://react.dev/reference/rsc/server-functions)
  - [`'use client'`](https://react.dev/reference/rsc/use-client)
  - [`'use server'`](https://react.dev/reference/rsc/use-server)
  - [`useActionState`](https://react.dev/reference/react/useActionState)
  - [`useOptimistic`](https://react.dev/reference/react/useOptimistic)
  - [`useTransition`](https://react.dev/reference/react/useTransition)
  - [`useDeferredValue`](https://react.dev/reference/react/useDeferredValue)
  - [`useFormStatus`](https://react.dev/reference/react-dom/hooks/useFormStatus)
  - [`<form>`](https://react.dev/reference/react-dom/components/form)
- **Web platform references that show up repeatedly**:
  - [MDN Request](https://developer.mozilla.org/en-US/docs/Web/API/Request)
  - [MDN Response](https://developer.mozilla.org/en-US/docs/Web/API/Response)
  - [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData)
  - [MDN URLSearchParams](https://developer.mozilla.org/en-US/docs/Web/API/URLSearchParams)
  - [MDN AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
  - [MDN Streams API](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API)
- **Accessibility standards**:
  - [WAI-ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
  - [WCAG Overview](https://www.w3.org/WAI/standards-guidelines/wcag/)

# Vue.js Mastery Study Guide

A comprehensive, job-focused guide to mastering Vue.js (Vue 3 + Composition API). Each section builds on the previous one. Build real features, not toy examples.

---

## Phase 1: Core Foundations

### 1.1 Project Setup & Tooling

- **`create-vue`** (official scaffolding via `npm create vue@latest`): Vite-based, replaces Vue CLI
  - Use this to start from the current Vue team defaults instead of backfilling tooling later; docs: [Quick Start](https://vuejs.org/guide/quick-start.html).
- **Vite**: Why it's fast (native ESM in dev, Rollup for production). `vite.config.ts` configuration
  - Learn where Vite stops and Vue begins so you know whether a problem belongs in app code, plugin config, or the build pipeline; docs: [Vite Guide](https://vite.dev/guide/).
- **Project structure conventions**:
  - Treat this layout as a maintainability baseline so features, shared logic, and route-level code stay easy to find as the app grows.
  ```
  src/
    assets/          # Static assets processed by Vite
    components/      # Reusable UI components
    composables/     # Composition API logic (use*.ts)
    layouts/         # Page layout wrappers
    pages/ or views/ # Route-level components
    router/          # Vue Router config
    stores/          # Pinia stores
    services/        # API clients, external service wrappers
    types/           # TypeScript type definitions
    utils/           # Pure utility functions
    App.vue
    main.ts
  ```
- **TypeScript**: Use it from day one. Vue 3 is written in TS and has first-class support. `<script setup lang="ts">`
  - The biggest win is safer refactors across props, emits, stores, and API models before those mistakes reach the browser; docs: [TypeScript Overview](https://vuejs.org/guide/typescript/overview.html).
- **VS Code + Volar**: The official Vue language extension. Disable Vetur if migrating from Vue 2
  - Volar understands SFC syntax, template type-checking, and `<script setup>`, so it gives much more accurate feedback than generic TS tooling; docs: [Tooling](https://vuejs.org/guide/scaling-up/tooling.html).
- **ESLint + `eslint-plugin-vue`**: Enforce Vue-specific linting rules. Use `plugin:vue/vue3-recommended`
  - Favor lint rules that catch real correctness issues first, then add style rules only if they reduce review noise for your team; docs: [`eslint-plugin-vue`](https://eslint.vuejs.org/).
- **Prettier**: Format `.vue` files. Configure to work with ESLint (`eslint-config-prettier`)
  - Let formatting be automatic so code reviews stay focused on state flow, rendering behavior, and architecture instead of whitespace; docs: [Prettier](https://prettier.io/docs/en/), [`eslint-config-prettier`](https://github.com/prettier/eslint-config-prettier).

**Practice**: Scaffold a new project with `create-vue`, selecting TypeScript, Vue Router, Pinia, ESLint, and Prettier. Understand every file in the generated project.

---

### 1.2 Single-File Components (SFCs)

- **Anatomy of a `.vue` file**: `<script setup>`, `<template>`, `<style scoped>`
  - Each block has a clear job: logic, markup, and styling, which makes SFCs easier to reason about than spreading one component across multiple files; docs: [Single-File Components](https://vuejs.org/guide/scaling-up/sfc.html).
- **`<script setup>`**: The modern default. Top-level bindings are automatically available in the template. No `export default`, no `setup()` function
  - This syntax removes ceremony and makes composables feel like plain functions, which is why it is the default style in most Vue 3 codebases; docs: [Script Setup](https://vuejs.org/api/sfc-script-setup.html).
- **`<style scoped>`**: CSS scoped to the component via data attributes. Understand specificity implications
  - Scoped styles reduce accidental leakage, but you still need to understand how selectors compile so you do not fight specificity in larger components; docs: [SFC CSS Features](https://vuejs.org/api/sfc-css-features.html).
- **`<style module>`**: CSS Modules support — `$style.className` in templates
  - This is useful when you want explicit class-name isolation without depending on global naming conventions or utility classes.
- **`defineProps()`**: Declare component props with full TypeScript type inference
  - Strong prop types pay off most when components become shared building blocks across many routes or feature areas; docs: [Props](https://vuejs.org/guide/components/props.html).
- **`defineEmits()`**: Declare emitted events with type-safe payloads
  - Treat emits like a public component API so parents can rely on stable event names and payload shapes; docs: [Events](https://vuejs.org/guide/components/events.html).
- **`defineExpose()`**: Explicitly expose properties to parent components via template refs
  - Reach for this sparingly because it creates tighter parent-child coupling than props, slots, or events.
- **`defineModel()`**: Two-way binding macro (Vue 3.4+) — simplifies `v-model` on custom components
  - It removes boilerplate around `modelValue` and `update:modelValue`, which is especially nice in reusable form components; docs: [Component v-model](https://vuejs.org/guide/components/v-model.html).
- **`defineOptions()`**: Set component options like `name`, `inheritAttrs` without a separate `<script>` block
  - This keeps component metadata close to the rest of the setup logic when you still need classic options in `<script setup>`; docs: [Script Setup](https://vuejs.org/api/sfc-script-setup.html).
- **`defineSlots()`**: Type-safe slot definitions
  - Use it in component libraries and shared UI primitives where slot props are part of the public contract.

---

### 1.3 Reactivity System (Deep Dive)

#### Core Primitives
- **`ref()`**: Reactive reference for any value. Access via `.value` in script, auto-unwrapped in templates
  - Default to `ref()` because it works consistently for primitives, objects, and composable return values; docs: [Reactivity Fundamentals](https://vuejs.org/guide/essentials/reactivity-fundamentals.html).
- **`reactive()`**: Reactive proxy for objects. No `.value` needed but can't reassign the whole object. Use `ref()` by default, `reactive()` for deeply nested state you mutate often
  - The tradeoff is convenience versus reassignment safety, so choose it intentionally instead of mixing both styles randomly; docs: [Reactivity Fundamentals](https://vuejs.org/guide/essentials/reactivity-fundamentals.html).
- **`computed()`**: Derived reactive values. Cached — only re-evaluates when dependencies change. Read-only by default, writable with `get`/`set`
  - If you catch yourself repeating the same derivation in multiple places, it is usually a sign that the logic belongs in a computed; docs: [Computed Properties](https://vuejs.org/guide/essentials/computed.html).
- **`watch()`**: Run side effects when reactive sources change. Options: `immediate`, `deep`, `once`, `flush` (`pre`, `post`, `sync`)
  - Use `watch()` for effects that touch the outside world, such as storage, network calls, or imperative DOM logic; docs: [Watchers](https://vuejs.org/guide/essentials/watchers.html).
- **`watchEffect()`**: Automatically tracks dependencies and re-runs. Runs immediately. Use when you have many dependencies and don't need the old value
  - It is best for small reactive effects where manually listing sources would be noisier than helpful; docs: [Watchers](https://vuejs.org/guide/essentials/watchers.html).
- **`watchPostEffect()` / `watchSyncEffect()`**: Shorthand for `watchEffect` with different flush timing
  - Flush timing mostly matters when coordinating DOM reads, transitions, or third-party libraries that care about exact update order.

#### Reactivity Gotchas
- **Destructuring breaks reactivity**: `const { count } = reactive({ count: 0 })` — `count` is NOT reactive. Use `toRefs()` or stick with `ref()`
  - This is one of the most common Composition API bugs, especially when passing store or prop state into helpers; docs: [Reactivity in Depth](https://vuejs.org/guide/extras/reactivity-in-depth.html).
- **`toRef()` / `toRefs()`**: Create refs that stay connected to a reactive source. Essential for destructuring props in composables
  - Reach for these when you need ergonomic destructuring but still want updates to flow both ways from the source object.
- **`toValue()` / `toRaw()`**: Unwrap refs/reactive proxies to get the raw value
  - These helpers are useful at the boundaries where Vue state has to interact with plain functions or non-reactive libraries.
- **`shallowRef()` / `shallowReactive()`**: Only track top-level changes. Use for large objects where deep tracking is expensive (e.g., large lists, external library instances)
  - They are performance tools, not defaults, and they work best when you control update boundaries deliberately.
- **`triggerRef()`**: Manually trigger watchers on a shallow ref after mutating its `.value` deeply
  - This is the escape hatch when you choose shallow tracking but still need to notify Vue after an internal mutation.
- **`readonly()`**: Create a read-only proxy. Use to expose store state without allowing direct mutation
  - It helps you separate who can observe state from who is allowed to change it.
- **`markRaw()`**: Exclude an object from reactivity. Use for third-party class instances (Chart.js, map instances) that should never be reactive
  - Marking objects raw avoids both overhead and subtle bugs caused by proxy-wrapping objects that expect normal identity semantics; docs: [Chart.js](https://www.chartjs.org/docs/latest/).

#### How Reactivity Works Under the Hood
- **Proxy-based tracking**: Vue 3 uses ES6 `Proxy` to intercept get/set operations
  - Understanding the proxy layer makes it easier to reason about why some patterns stay reactive and others do not; docs: [Reactivity in Depth](https://vuejs.org/guide/extras/reactivity-in-depth.html).
- **Dependency tracking**: When a computed/watcher reads a reactive value, it's registered as a dependency
  - This is the mental model behind why Vue can update only what changed instead of re-running everything blindly.
- **Batched updates**: Multiple state changes in the same tick are batched into a single re-render
  - Batched rendering is why several `.value` assignments in a row usually produce one DOM update, not many.
- **`nextTick()`**: Wait for the DOM to update after a state change. Essential when you need to read DOM after reactive changes
  - Use it when your code depends on rendered output, such as measuring size, focusing elements, or syncing scroll position; docs: [Reactivity Fundamentals](https://vuejs.org/guide/essentials/reactivity-fundamentals.html).

**Practice**: Build a reactive shopping cart. Use `ref` for simple values, `reactive` for the cart object, `computed` for totals, `watch` to persist to localStorage. Deliberately trigger every gotcha above and fix it.

---

### 1.4 Template Syntax

- **Interpolation**: `{{ expression }}` — any valid JS expression
  - Keep expressions lightweight and move branching or heavy derivation into computed state so templates stay readable; docs: [Template Syntax](https://vuejs.org/guide/essentials/template-syntax.html).
- **Directives**:
  - `v-bind` (`:attr`): Dynamic attribute binding. `:class` and `:style` have special object/array syntax
  - `v-on` (`@event`): Event handling. Modifiers: `.prevent`, `.stop`, `.once`, `.capture`, `.self`, `.passive`
  - `v-model`: Two-way binding. Modifiers: `.lazy`, `.number`, `.trim`. Works on inputs, selects, textareas, and custom components
  - `v-if` / `v-else-if` / `v-else`: Conditional rendering (adds/removes from DOM)
  - `v-show`: Toggle visibility via CSS `display`. Use when toggling frequently
  - `v-for`: List rendering. **Always use `:key`** with a unique, stable identifier (never use index as key for dynamic lists)
  - `v-slot` (`#slotName`): Named and scoped slots
  - `v-memo`: Memoize a sub-tree (performance optimization, rarely needed)
  - `v-once`: Render once, never update
  - Learn the directives as a system because most template bugs come from choosing the wrong rendering or binding primitive for the job; docs: [Template Syntax](https://vuejs.org/guide/essentials/template-syntax.html), [Form Input Bindings](https://vuejs.org/guide/essentials/forms.html), [List Rendering](https://vuejs.org/guide/essentials/list.html).
- **Key attribute**: How Vue's diffing algorithm uses keys for efficient updates. Why wrong keys cause bugs
  - Stable keys preserve component identity, local state, and DOM position, which is why index keys break dynamic lists so easily; docs: [List Rendering](https://vuejs.org/guide/essentials/list.html).
- **Template refs**: `ref="myRef"` + `const myRef = ref<HTMLElement | null>(null)` — direct DOM access
  - Template refs are for imperative escape hatches like focus, measurement, and third-party widgets, not for normal data flow; docs: [Template Refs](https://vuejs.org/guide/essentials/template-refs.html).

**Practice**: Build a filterable, sortable data table component using every directive above. Include column-level slot customization.

---

## Phase 2: Component Architecture

### 2.1 Props

- **Declaration**: `defineProps<{ title: string; count?: number }>()` — full TypeScript generics
  - Prefer explicit prop contracts even in small components so reuse does not gradually turn into guesswork; docs: [Props](https://vuejs.org/guide/components/props.html).
- **Validation**: Type checking, `required`, `default`, custom `validator` functions
  - Validation is most helpful at component boundaries where the calling code may come from many different parents or teams.
- **One-way data flow**: Props flow down, events flow up. Never mutate a prop directly
  - This rule keeps component ownership clear and prevents child components from silently fighting parent state; docs: [Props](https://vuejs.org/guide/components/props.html).
- **Boolean casting**: `<MyComponent disabled />` — boolean props have special shorthand behavior
  - Know the casting rules so your component API behaves like native HTML elements instead of surprising consumers.
- **Object/array defaults**: Must use factory functions: `default: () => []`
  - Factory defaults prevent shared mutable state across component instances, which is a classic bug source.

### 2.2 Events

- **`defineEmits<{ (e: 'update', id: number): void }>()`**: Type-safe event declarations
  - Strongly typed emits make parent-child communication easier to refactor and easier to document; docs: [Events](https://vuejs.org/guide/components/events.html).
- **`emit('eventName', payload)`**: Trigger events from child to parent
  - Emit semantic events like `save` or `close` instead of leaking internal UI details such as `button-clicked`.
- **Naming convention**: `kebab-case` in templates (`@my-event`), `camelCase` in script
  - Consistent event naming reduces friction when scanning templates versus implementation code in the same component.
- **`v-model` on components**: `modelValue` prop + `update:modelValue` emit. Multiple `v-model` bindings: `v-model:title`, `v-model:content`
  - Custom `v-model` is best when the component really owns an editable value, not just because two-way binding feels convenient; docs: [Component v-model](https://vuejs.org/guide/components/v-model.html).
- **`.sync` replacement**: Vue 3 uses `v-model:propName` instead of Vue 2's `.sync`
  - This makes the contract more explicit by naming the synced prop directly instead of hiding it behind special syntax.

### 2.3 Slots

- **Default slot**: `<slot />` — render parent's children
  - Default slots are the simplest way to let a wrapper component stay flexible without growing a huge prop surface area; docs: [Slots](https://vuejs.org/guide/components/slots.html).
- **Named slots**: `<slot name="header" />` — `<template #header>...</template>`
  - Named slots work well when the child owns layout but the parent should control specific regions like headers or actions.
- **Scoped slots**: Pass data from child to parent's slot content. `<slot :item="item" />` — `<template #default="{ item }">`. The key pattern for renderless/headless components
  - Scoped slots are where Vue component composition gets powerful because logic and rendering can be owned by different components.
- **Dynamic slot names**: `<template #[dynamicSlotName]>`
  - Use dynamic slot names sparingly because they add flexibility at the cost of making the component API harder to discover.
- **Slot fallback content**: `<slot>Default content here</slot>`
  - Good fallback content makes components easier to adopt because the simplest usage still renders something sensible.
- **`useSlots()`**: Programmatic access to check if slots are provided
  - This is handy for conditional wrappers, spacing, and accessibility markup that should only render when slot content exists.

### 2.4 Provide / Inject

- **`provide(key, value)`**: Make data available to all descendants (any depth)
  - Provide/inject is best for low-level shared context where prop drilling would make the tree noisy; docs: [Provide / Inject](https://vuejs.org/guide/components/provide-inject.html).
- **`inject(key, defaultValue)`**: Consume provided data
  - Use explicit defaults so a component can fail gracefully or stay testable outside its normal provider tree.
- **Typed injection keys**: `const key: InjectionKey<Type> = Symbol()` — type-safe provide/inject
  - Symbols plus TypeScript protect you from key collisions and mismatched value shapes in larger apps.
- **Reactive provide**: Provide `ref` or `reactive` values for reactive injection
  - The value stays live only if you provide a reactive source, so be deliberate about whether consumers should observe updates.
- **When to use**: Theme config, locale, authenticated user, shared services. Avoid for general state management (use Pinia instead)
  - A good rule is to use provide/inject for ambient context and Pinia for cross-feature application state.

### 2.5 Component Patterns

- **Presentational vs container components**: Presentational = pure UI (props in, events out). Container = data fetching, state management
  - This separation keeps reusable UI components simple while isolating data concerns near the route or feature boundary.
- **Renderless / headless components**: Logic only, delegate rendering to scoped slots. Pattern used by headless UI libraries
  - Headless patterns are ideal when multiple screens need the same interaction logic but different markup or styling.
- **Compound components**: Related components that work together (`<Tabs>`, `<Tab>`, `<TabPanel>`) using provide/inject
  - This pattern gives consumers a natural template API while still letting the internal pieces share coordinated state.
- **Recursive components**: Components that render themselves (tree views, nested comments). Use `name` option or filename-based self-reference
  - Recursive rendering is easy to write in Vue, but you need clear base cases to avoid infinite loops or very deep trees.
- **Dynamic components**: `<component :is="currentComponent" />` — switch between components dynamically
  - Use dynamic components when the view shape changes, not just to avoid writing a couple of `v-if` branches.
- **Async components**: `defineAsyncComponent(() => import('./MyComponent.vue'))` — lazy-loaded with loading/error states
  - Async components are especially useful for rarely visited panels or heavyweight widgets that would otherwise bloat the initial bundle; docs: [Async Components](https://vuejs.org/guide/components/async.html).
- **`<Teleport>`**: Render content in a different DOM location (modals, tooltips, toasts)
  - Teleport solves layering and overflow issues without giving up the logical ownership of the component that opened the UI; docs: [Teleport](https://vuejs.org/guide/built-ins/teleport.html).
- **`<Suspense>`**: Handle async dependencies in component tree. Show fallback while loading. Still experimental but widely used
  - It can simplify loading coordination, but use it intentionally because async boundaries affect perceived responsiveness; docs: [Suspense](https://vuejs.org/guide/built-ins/suspense.html).
- **`<KeepAlive>`**: Cache component instances when toggling. `include`/`exclude`/`max` props. `onActivated`/`onDeactivated` lifecycle hooks
  - Caching is great for tabs, wizards, and route shells where re-creating the component would be needlessly expensive; docs: [KeepAlive](https://vuejs.org/guide/built-ins/keep-alive.html).

**Practice**: Build a headless `Dropdown` component using scoped slots that handles all keyboard navigation, open/close state, and positioning — but lets the consumer fully control rendering.

---

## Phase 3: Composition API & Composables

### 3.1 Lifecycle Hooks

- **`onMounted()`**: DOM is available. Fetch data, initialize third-party libraries, set up event listeners
  - Reach for this when you truly need rendered DOM or browser-only APIs, not just because "component startup" feels like the right place; docs: [Lifecycle Hooks](https://vuejs.org/guide/essentials/lifecycle.html).
- **`onUnmounted()`**: Clean up. Remove event listeners, cancel timers, abort fetch requests, disconnect observers
  - Cleanup discipline is what keeps composables and long-lived views from leaking work after a user navigates away.
- **`onBeforeMount()`** / **`onBeforeUnmount()`**: Before DOM insertion / removal
  - These are niche hooks, but they matter when you have setup or teardown that must happen before the rendered tree changes.
- **`onUpdated()`** / **`onBeforeUpdate()`**: After/before reactive state change triggers re-render
  - Use update hooks carefully because they can run often and are easy places to create accidental render loops.
- **`onActivated()`** / **`onDeactivated()`**: For `<KeepAlive>` cached components
  - These hooks matter when a view should pause and resume work rather than fully mounting and unmounting each time.
- **`onErrorCaptured()`**: Catch errors from descendant components. Return `false` to stop propagation
  - It is most useful for graceful UI fallbacks around unstable child trees or third-party integrations.
- **No `created`/`beforeCreate`**: In `<script setup>`, top-level code IS the setup phase. These hooks are unnecessary
  - Internalizing this helps Vue 2 developers stop searching for lifecycle hooks when plain top-level setup code already does the job.

### 3.2 Composables (The Core Pattern)

- **Convention**: Functions named `use*` that encapsulate reactive state and logic
  - The `use*` naming pattern signals that the function participates in Vue's reactive and lifecycle model; docs: [Composables](https://vuejs.org/guide/reusability/composables.html).
- **Structure**:
  - A good composable exposes a small public surface area, hides implementation details, and returns predictable reactive primitives.
  ```typescript
  // composables/useCounter.ts
  export function useCounter(initial = 0) {
    const count = ref(initial)
    const doubled = computed(() => count.value * 2)
    
    function increment() { count.value++ }
    function decrement() { count.value-- }
    function reset() { count.value = initial }
    
    return { count: readonly(count), doubled, increment, decrement, reset }
  }
  ```
- **Rules**:
  - Call composables at the top level of `<script setup>` (not inside conditionals or loops)
  - Return reactive refs, not raw values (so consumers stay reactive)
  - Use `readonly()` for state you don't want consumers to mutate directly
  - Accept `ref` or plain values as arguments using `toValue()` for flexibility
  - Clean up side effects in `onUnmounted()` inside the composable
  - Treat these as design guardrails so composables stay reusable, testable, and safe to compose together; docs: [Composables](https://vuejs.org/guide/reusability/composables.html).

### 3.3 Essential Composables to Build

Build these yourself before using libraries:

| Composable | Purpose | Key Concepts |
|---|---|---|
| `useFetch()` | Data fetching with loading/error states | Async, abort controller, reactive URL |
| `useLocalStorage()` | Sync ref with localStorage | Serialization, storage events, SSR safety |
| `useDebounce()` | Debounce a ref value | Timers, cleanup |
| `useThrottle()` | Throttle function calls | Timing control |
| `useEventListener()` | Auto-cleaned event listeners | `onUnmounted` cleanup, target refs |
| `useIntersectionObserver()` | Lazy loading, infinite scroll | Browser APIs, cleanup |
| `useMediaQuery()` | Responsive logic in JS | `matchMedia`, listener cleanup |
| `useClickOutside()` | Close dropdowns/modals | Event delegation, template refs |
| `useForm()` | Form state, validation, submission | Reactive validation, error tracking |
| `useAuth()` | Auth state, login/logout, token management | Provide/inject, router guards |
| `usePagination()` | Paginated data fetching | Computed pages, reactive params |
| `useWebSocket()` | Real-time data | Connection lifecycle, reconnection |

### 3.4 VueUse

- **What it is**: The standard library of Vue composables (200+ functions). Don't reinvent the wheel after you understand the patterns
  - VueUse becomes much more valuable after you can recognize which helpers are just wrappers around patterns you already understand; docs: [VueUse](https://vueuse.org/).
- **Essential functions**: `useStorage`, `useFetch`, `useDebounce`, `useThrottleFn`, `useEventListener`, `useIntersectionObserver`, `useBreakpoints`, `useDark`, `useClipboard`, `useVModel`, `onClickOutside`, `useInfiniteScroll`
  - Focus on the helpers that remove repetitive browser API glue first, because they tend to create the biggest productivity gains.
- **When to use**: After you've built the composable yourself at least once. Understand what VueUse does before depending on it
  - That way you can debug edge cases, SSR issues, and lifecycle behavior instead of treating the library like magic.

**Practice**: Build all 12 composables in the table above from scratch. Then compare your implementations with VueUse's source code to learn from the differences.

---

## Phase 4: Vue Router

### 4.1 Core Routing

- **`createRouter()`**: History mode (`createWebHistory()`) vs hash mode (`createWebHashHistory()`). Always use history mode for production apps
  - Learn the history choice early because it affects server config, deep linking, and how your URLs behave in production; docs: [Vue Router Guide](https://router.vuejs.org/guide/).
- **Route definitions**: `path`, `name`, `component`, `redirect`, `alias`, `children`
  - Clean route records turn routing into declarative app structure instead of scattered navigation rules.
- **Dynamic routes**: `/users/:id` — accessed via `route.params.id`
  - Dynamic segments are the bridge between URL design and data fetching, so name them clearly and validate them.
- **`<RouterView />`**: Renders the matched component. Nested `<RouterView>` for nested routes
  - Think of each `RouterView` as a layout slot where the router decides which feature component should live.
- **`<RouterLink />`**: Declarative navigation. `to` prop (string or object), `active-class`, `exact-active-class`
  - Prefer `RouterLink` over raw anchors inside the app so navigation stays SPA-friendly and active-state aware.
- **Programmatic navigation**: `router.push()`, `router.replace()`, `router.go()`, `router.back()`
  - Use imperative navigation after actions like save, login, or wizard steps where the route change depends on app logic.
- **`useRoute()`**: Access current route (params, query, path, name, meta). Reactive
  - Because the route object is reactive, it can drive computed state, fetch keys, and watchers without extra plumbing.
- **`useRouter()`**: Access router instance for programmatic navigation
  - Keep direct router access near the component or composable that owns the navigation decision instead of passing it around.

### 4.2 Advanced Routing

- **Nested routes**: Parent route with `children` array. Parent component has `<RouterView>` for child rendering
  - Nested routes are a strong fit for dashboards and settings areas where a shared shell should survive page changes.
- **Named views**: Multiple `<RouterView name="sidebar">` on the same page. Route maps `components: { default: Main, sidebar: Sidebar }`
  - Named views are useful when the route controls more than one region of the screen at once.
- **Route params validation**: Custom regex in params: `/users/:id(\\d+)`. Catch-all: `/:pathMatch(.*)*`
  - Validate route shapes at the router boundary so invalid URLs fail predictably instead of reaching component code.
- **Lazy loading routes**: `component: () => import('./views/UserList.vue')` — Vite automatically code-splits
  - Route-level lazy loading is one of the easiest performance wins because users rarely need every screen up front.
- **Route-level code splitting**: Group chunks with `/* webpackChunkName: "group" */` (Webpack) or Rollup manual chunks (Vite)
  - Chunk strategy matters when related screens should download together instead of creating many small network requests.

### 4.3 Navigation Guards

- **Global guards**: `router.beforeEach()`, `router.afterEach()`, `router.beforeResolve()`
  - Global guards are best for cross-cutting rules like auth checks, analytics, and document title behavior; docs: [Navigation Guards](https://router.vuejs.org/guide/advanced/navigation-guards.html).
- **Per-route guards**: `beforeEnter` in route definition
  - Use per-route guards when a rule belongs to one route branch rather than the whole app.
- **In-component guards**: `onBeforeRouteLeave()`, `onBeforeRouteUpdate()`
  - These hooks shine when the component owns unsaved state or needs to react to param changes without remounting.
- **Guard patterns**:
  - **Authentication**: Check auth state in `beforeEach`, redirect to `/login` if unauthenticated
  - **Authorization**: Check user roles/permissions against `route.meta.requiredRole`
  - **Data fetching**: Fetch data in guard (wait before rendering) vs in component (render loading state)
  - **Unsaved changes**: Warn on `beforeRouteLeave` if form has unsaved changes
  - The main design choice is whether to block navigation before render or let the view load and show its own pending state.
- **Return values**: Return `false` to cancel, return a route location to redirect, return nothing (or `true`) to proceed
  - Internalizing guard return values helps you avoid mixing old `next()`-style habits with the modern API.

### 4.4 Route Meta & Transitions

- **`meta` fields**: Attach arbitrary data to routes: `meta: { requiresAuth: true, title: 'Dashboard', layout: 'admin' }`
  - Route meta is where routing decisions meet app-level concerns like auth, layout, and page titles; docs: [Route Meta Fields](https://router.vuejs.org/guide/advanced/meta.html).
- **Dynamic document title**: Set `document.title` in `afterEach` from `route.meta.title`
  - A consistent title pattern improves accessibility, browser history clarity, and SEO for SSR or hybrid apps.
- **Route-based layouts**: Use `route.meta.layout` with dynamic `<component :is>` wrapper
  - Layout metadata keeps page components focused on feature logic instead of shell selection.
- **Route transitions**: `<RouterView v-slot="{ Component }">` + `<Transition>` for animated page transitions
  - Keep route transitions subtle so they support orientation without making navigation feel slower.
- **Scroll behavior**: `scrollBehavior(to, from, savedPosition)` in router config — restore scroll position on back, scroll to top on forward
  - Good scroll behavior is easy to overlook, but it has a huge effect on whether navigation feels polished.

**Practice**: Build a multi-section app with authentication, role-based routes, nested layouts, lazy-loaded pages, and animated transitions. Include a "unsaved changes" guard on form pages.

---

## Phase 5: State Management with Pinia

### 5.1 Store Fundamentals

- **Why Pinia**: Official Vue state management. Replaces Vuex. TypeScript-first, Composition API-native, devtools integration
  - Pinia fits Vue 3 naturally because stores feel like composables with devtools and shared state built in; docs: [Pinia Core Concepts](https://pinia.vuejs.org/core-concepts/).
- **Defining stores**: Two syntaxes:
  - Understand both syntaxes so you can read community examples, but default to the one that matches how your team structures logic.
  ```typescript
  // Option syntax (simpler)
  export const useCounterStore = defineStore('counter', {
    state: () => ({ count: 0 }),
    getters: { doubled: (state) => state.count * 2 },
    actions: { increment() { this.count++ } }
  })

  // Setup syntax (more flexible, composable-like)
  export const useCounterStore = defineStore('counter', () => {
    const count = ref(0)
    const doubled = computed(() => count.value * 2)
    function increment() { count.value++ }
    return { count, doubled, increment }
  })
  ```
- **Setup syntax advantages**: Use any composable inside stores, more natural async handling, better TypeScript inference. **Prefer this for production apps**
  - Setup stores scale better once you need watchers, injected services, or logic shared with other composables.
- **Accessing stores**: Call the store function in `<script setup>`. Properties are reactive. Destructure with `storeToRefs()` to maintain reactivity
  - Store access is simple, but destructuring incorrectly is a frequent source of “why didn’t my UI update?” bugs.

### 5.2 State Patterns

- **`$reset()`**: Reset state to initial values (option stores only). For setup stores, write your own reset function
  - Reset behavior matters for logout flows, multi-step forms, and tests where state should return to a known baseline.
- **`$patch()`**: Batch multiple state changes into a single reactive update. Object syntax and function syntax
  - `$patch()` is useful when several related mutations should appear as one logical update in both the UI and devtools.
- **`$subscribe()`**: Watch for state changes. `detached: true` to persist after component unmount
  - Subscriptions are a clean place for persistence, analytics, or syncing with external systems.
- **`$onAction()`**: Hook into action calls. `after` and `onError` callbacks
  - Action hooks are valuable for cross-cutting concerns like logging, tracing, and optimistic rollback behavior.
- **`storeToRefs()`**: Destructure store state/getters while keeping reactivity. Actions don't need `storeToRefs`
  - Make this a habit whenever you destructure state out of a store in setup code.

### 5.3 Store Architecture

- **Store per domain**: `useUserStore`, `useCartStore`, `useProductStore`, `useNotificationStore`
  - Domain-based stores map better to business concepts than “one giant global store” and are easier to test.
- **Store composition**: Stores can use other stores. Import and call inside actions/getters
  - Composition is powerful, but use it to express real dependencies rather than tangling every store together.
- **Avoid circular dependencies**: Structure stores in a dependency tree. If A depends on B, B should never depend on A
  - Circular store usage creates boot-order and testing headaches that are painful to unwind later.
- **Thin stores**: Keep stores focused on state and simple mutations. Put complex business logic in services/composables that USE the store
  - Thin stores are easier to reason about because they expose state transitions without becoming a dumping ground.
- **Normalized state**: Don't nest deeply. Use IDs and maps: `{ byId: { '1': {...} }, allIds: ['1', '2'] }`
  - Normalized shapes make updates cheaper and reduce bugs caused by duplicating the same entity in several places.

### 5.4 Plugins

- **Persistence**: `pinia-plugin-persistedstate` — automatically sync stores with localStorage/sessionStorage
  - Persist only the state that must survive reloads, because stale cached data can become a bug just as easily as a convenience; docs: [`pinia-plugin-persistedstate`](https://prazdevs.github.io/pinia-plugin-persistedstate/).
- **Custom plugins**: `pinia.use(({ store }) => { ... })` — add properties, wrap actions, subscribe to changes
  - Plugins are best for cross-store behavior that should feel native everywhere, not for one-off feature logic.
- **Undo/redo**: Plugin pattern that snapshots state on each action
  - This pattern is especially helpful in editors, dashboards, and complex forms where users make many reversible changes.
- **Devtools**: Pinia integrates with Vue DevTools. Time-travel debugging, state inspection, action tracking
  - Devtools visibility is one of the fastest ways to understand whether a bug is in the store, the component, or the API layer; docs: [Vue DevTools](https://devtools.vuejs.org/).

**Practice**: Build a store architecture for an e-commerce app: `useAuthStore`, `useProductStore`, `useCartStore`, `useCheckoutStore`. Implement persistence for the cart, optimistic updates for the wishlist, and loading/error state patterns.

---

## Phase 6: API Integration & Data Fetching

### 6.1 HTTP Clients

- **Axios**: Interceptors for auth tokens, request/response transformation, error handling
  - Axios is still common in Vue codebases because interceptors give you one place to standardize auth and error behavior; docs: [Axios](https://axios-http.com/docs/intro).
- **`ofetch` / `ky`**: Modern, lighter alternatives with TypeScript support
  - These are good fits when you want a smaller surface area and less framework baggage than Axios; docs: [`ofetch`](https://github.com/unjs/ofetch), [`ky`](https://github.com/sindresorhus/ky).
- **API service layer pattern**:
  - A service layer keeps components from knowing endpoint details, which makes testing and future API changes much easier.
  ```typescript
  // services/api.ts
  const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    timeout: 10000,
  })

  api.interceptors.request.use((config) => {
    const auth = useAuthStore()
    if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
    return config
  })

  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        await useAuthStore().refresh()
        return api(error.config) // Retry
      }
      return Promise.reject(error)
    }
  )

  // services/users.ts
  export const userService = {
    list: (params?: UserListParams) => api.get<User[]>('/users', { params }),
    get: (id: string) => api.get<User>(`/users/${id}`),
    create: (data: CreateUserDTO) => api.post<User>('/users', data),
    update: (id: string, data: UpdateUserDTO) => api.put<User>(`/users/${id}`, data),
    delete: (id: string) => api.delete(`/users/${id}`),
  }
  ```

### 6.2 TanStack Query (Vue Query)

- **Why**: Caching, deduplication, background refetching, optimistic updates, pagination, infinite scroll — all handled
  - TanStack Query is worth learning because server state has very different failure modes from local component state; docs: [TanStack Query for Vue](https://tanstack.com/query/latest/docs/framework/vue/overview).
- **`useQuery()`**: Declarative data fetching with caching. `queryKey` for cache identity, `queryFn` for the fetch function
  - Good query keys are the foundation, because everything else in the cache model depends on them.
- **`useMutation()`**: For create/update/delete with `onSuccess`, `onError`, `onSettled` callbacks
  - Mutations are where optimistic UI, rollback logic, and invalidation strategy come together.
- **`queryClient.invalidateQueries()`**: Refetch after mutations
  - Invalidation is the simplest way to keep data honest when the server remains your source of truth.
- **Stale-while-revalidate**: Serve cached data immediately, refetch in background
  - This pattern improves perceived performance because the UI can stay responsive while newer data loads.
- **Optimistic updates**: Update cache before server confirms. Roll back on error
  - Use optimism on flows where the success rate is high and the rollback path is easy to explain to users.
- **`useInfiniteQuery()`**: Infinite scroll with `getNextPageParam`
  - Infinite queries are great for feeds and activity logs, but they add complexity around cache shape and scrolling.
- **Query keys**: Hierarchical arrays `['users', userId, 'posts']` for granular cache invalidation
  - Consistent key structure is what makes partial invalidation and debugging manageable in larger apps.
- **`enabled` option**: Conditional/dependent queries
  - This is the cleanest way to express “fetch only when the required input exists” without manual watcher code.
- **Placeholder data and initial data**: Show something immediately while fetching
  - These options let you reduce loading jank without pretending the app already has fresh server truth.
- **Devtools**: `@tanstack/vue-query-devtools` for cache inspection
  - Query devtools are invaluable when a bug is really stale cache behavior rather than a rendering problem.

### 6.3 Data Fetching Patterns

- **Loading/error/data states**: Every fetch needs all three. Never ignore error states
  - Thinking in these three states prevents “happy path only” UIs that fall apart under real network conditions.
- **Retry logic**: Exponential backoff for transient failures
  - Retries should help with flaky networks, not hide persistent backend failures from the user forever.
- **Request cancellation**: `AbortController` for cancelled navigations / stale requests
  - Cancellation prevents slow responses from overwriting newer state after the user has already moved on.
- **Polling**: `refetchInterval` in Vue Query, or manual `setInterval` with cleanup
  - Poll only when freshness matters enough to justify extra server load and client work.
- **Debounced search**: Debounce input, fetch on debounced value
  - Debouncing keeps typing smooth and reduces redundant requests for intermediate input states.
- **Parallel requests**: `Promise.all()` for independent fetches
  - Parallelize anything without a hard dependency so the UI waits on the slowest request only once.
- **Dependent queries**: Fetch B only after A completes (use `enabled: computed(() => !!userQuery.data.value)`)
  - This pattern keeps sequencing explicit instead of scattering fetch order across watchers and lifecycle hooks.

**Practice**: Build a user management dashboard with search, filters, pagination, create/edit forms with optimistic updates, and proper loading/error states using TanStack Query.

---

## Phase 7: Forms & Validation

### 7.1 Form Handling Approaches

- **Native `v-model` + manual validation**: Fine for simple forms (1-3 fields)
  - Start simple when the form is small, because adding a full validation framework too early can create unnecessary ceremony; docs: [Form Input Bindings](https://vuejs.org/guide/essentials/forms.html).
- **VeeValidate**: Full-featured form validation library. `useForm()`, `useField()`. Schema-based validation with Zod/Yup
  - VeeValidate shines when form state, validation messages, and submission flow would otherwise become repetitive boilerplate; docs: [VeeValidate](https://vee-validate.logaretm.com/v4/).
- **FormKit**: Form framework with built-in inputs, validation, and generation from schema
  - This is a stronger fit when the product has many internal CRUD forms and consistency matters more than bespoke markup; docs: [FormKit](https://formkit.com/).

### 7.2 VeeValidate + Zod (Production Pattern)

Reference docs: [VeeValidate](https://vee-validate.logaretm.com/v4/), [Zod](https://zod.dev/).

```typescript
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'

const schema = toTypedSchema(z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Must be at least 8 characters'),
  confirmPassword: z.string(),
}).refine(data => data.password === data.confirmPassword, {
  message: 'Passwords must match',
  path: ['confirmPassword'],
}))

const { handleSubmit, errors, isSubmitting, resetForm } = useForm({
  validationSchema: schema,
})

const onSubmit = handleSubmit(async (values) => {
  // values is fully typed { email: string, password: string, confirmPassword: string }
  await authService.register(values)
})
```

### 7.3 Form Patterns

- **Field-level validation**: Validate as user types (with debounce) or on blur
  - Choose the timing based on the cost of interruption: immediate feedback is helpful, but not every field needs live nagging.
- **Form-level validation**: Cross-field validation (password confirmation, date ranges)
  - Form-level rules matter whenever one field changes the meaning or validity of another.
- **Dynamic forms**: Add/remove fields based on user choices. Array fields for repeatable sections
  - Dynamic sections are where schema-driven or composable-based form structure starts to pay off.
- **Multi-step forms (wizards)**: Validate per step, preserve state across steps, allow going back
  - Good wizard UX depends on saved progress and predictable validation boundaries, not just splitting a long form visually.
- **File uploads**: Preview, progress tracking, drag-and-drop zones. Use `FormData` for submission
  - Uploads add async and browser API complexity, so isolate that logic instead of burying it in the form template.
- **Dirty tracking**: Track which fields have been modified. Warn on navigation if dirty
  - Dirty state protects users from losing work and pairs naturally with router leave guards.
- **Server-side errors**: Map API error responses back to form fields
  - The best validation UX combines local checks with precise backend feedback when the server rejects a value.
- **Accessible forms**: Labels, error messages linked with `aria-describedby`, focus management on errors
  - Accessibility work is what makes a form understandable under keyboards, screen readers, and error-heavy flows.

**Practice**: Build a multi-step registration form with real-time validation, file upload (avatar), cross-field validation, dirty tracking, and server-side error handling.

---

## Phase 8: Performance & Production Patterns

### 8.1 Performance Optimization

#### Rendering Performance
- **`v-once`**: Static content that never changes
  - This is a small optimization, but it is a clean win for large chunks of truly static markup; docs: [Performance](https://vuejs.org/guide/best-practices/performance.html).
- **`v-memo`**: Memoize list items — skip re-render if deps haven't changed
  - Reach for `v-memo` only after profiling, because most apps get more from simpler state and rendering fixes.
- **`shallowRef()` / `shallowReactive()`**: Avoid deep reactivity tracking for large data structures
  - Shallow tracking works best when you control exactly when updates should propagate through the UI.
- **Computed caching**: Prefer `computed()` over methods in templates — computeds are cached
  - Cached derivations cut repeated work and make templates easier to scan at the same time.
- **Virtual scrolling**: `vue-virtual-scroller` for rendering 10k+ items. Only render visible items
  - Rendering fewer DOM nodes usually beats micro-optimizing the render function when list sizes become extreme; docs: [`vue-virtual-scroller`](https://vue-virtual-scroller-demo.netlify.app/).
- **`<KeepAlive>`**: Cache frequently toggled component instances
  - This is especially helpful when users switch between tabs or views that would otherwise re-fetch or re-initialize.

#### Bundle Size
- **Lazy loading routes**: `() => import('./views/Page.vue')` — automatic code splitting
  - Route splits are the highest-leverage bundle optimization because they align naturally with real navigation behavior.
- **Dynamic imports**: `defineAsyncComponent()` for heavy components (charts, editors, maps)
  - Use component-level splits for rarely opened UI that would otherwise tax the first paint budget.
- **Tree-shaking**: Named imports from libraries. `import { debounce } from 'lodash-es'` not `import _ from 'lodash'`
  - Tree-shaking only helps if the package supports it and your imports are granular enough for the bundler to prune.
- **Bundle analysis**: `rollup-plugin-visualizer` to see what's in your bundle
  - Analyze before optimizing so you spend effort on the actual heavy dependencies, not the ones you merely suspect.
- **Dependency auditing**: Check bundle cost with `bundlephobia.com`. Prefer smaller alternatives
  - This habit pays off most before a dependency becomes deeply embedded in the app.

#### Runtime Performance
- **`Object.freeze()` for static data**: Large lookup tables, config data that never changes
  - Freezing is a signal to both Vue and future readers that this data is configuration, not mutable state.
- **Web Workers**: Offload heavy computation (`comlink` for ergonomic worker communication)
  - Move work off the main thread when the user can feel the lag, not just because a computation sounds expensive; docs: [`comlink`](https://github.com/GoogleChromeLabs/comlink).
- **Debounce/throttle**: Input handlers, scroll handlers, resize handlers
  - Rate-limiting is one of the easiest ways to keep reactive UIs responsive under noisy browser events.
- **Image optimization**: Lazy loading (`loading="lazy"`), responsive images (`srcset`), modern formats (WebP, AVIF)
  - Image payload often dominates real-world performance more than framework code does.

### 8.2 Error Handling

- **`app.config.errorHandler`**: Global error handler. Send to error tracking service (Sentry)
  - Global handling gives you one last safety net for unexpected runtime failures; docs: [Error Handling](https://vuejs.org/api/application.html#app-config-errorhandler), [Sentry for Vue](https://docs.sentry.io/platforms/javascript/guides/vue/).
- **`onErrorCaptured()`**: Per-component error boundaries
  - Local error capture lets one unstable feature fail gracefully without taking down the whole view.
- **Error boundary component pattern**: Wrap sections of your app to catch and display errors gracefully
  - A reusable boundary component helps you make failure states intentional instead of ad hoc.
- **Async error handling**: Always handle promise rejections. Vue Query's `onError`, try/catch in actions
  - Most production bugs in data-heavy apps are async bugs, so treat rejected promises as first-class UI states.

### 8.3 Security

- **XSS prevention**: Vue auto-escapes template interpolation. Never use `v-html` with user input
  - Vue protects interpolation by default, but that safety disappears the moment you opt into raw HTML; docs: [Security](https://vuejs.org/guide/best-practices/security.html).
- **`v-html` dangers**: Only use with sanitized content. Use `DOMPurify` if you must render user HTML
  - Raw HTML should be a deliberate exception with an explicit sanitization boundary, not a convenience shortcut; docs: [DOMPurify](https://github.com/cure53/DOMPurify).
- **CSP compliance**: Avoid inline styles/scripts in production. Configure CSP headers
  - CSP is easier to adopt when you plan for it early instead of retrofitting it after unsafe patterns spread.
- **Auth token storage**: `httpOnly` cookies > localStorage for tokens. localStorage is vulnerable to XSS
  - Security decisions around token storage should reflect your backend architecture, not just frontend convenience.
- **CORS**: Understand preflight requests, credentials mode. Configure backend `Access-Control-*` headers
  - CORS issues are integration problems, so learn enough to debug them without guessing blindly at headers.
- **Environment variables**: `VITE_*` prefix makes them public. Never put secrets in frontend env vars
  - Frontend env vars are build-time configuration, not secret storage, because the client can inspect them.
- **Dependency security**: `npm audit`, `Snyk`, keep dependencies updated
  - Supply-chain hygiene matters more in frontend apps than many teams realize because the browser runs everything you ship; docs: [Snyk](https://docs.snyk.io/).

### 8.4 Accessibility (a11y)

- **Semantic HTML**: Use `<button>`, `<nav>`, `<main>`, `<article>` — not `<div>` for everything
  - Native semantics give you keyboard support, screen reader meaning, and browser behavior with less custom code; docs: [Accessibility](https://vuejs.org/guide/best-practices/accessibility.html).
- **ARIA attributes**: `aria-label`, `aria-describedby`, `aria-expanded`, `aria-live`, `role`
  - ARIA should clarify semantics that HTML cannot express, not paper over missing semantic structure.
- **Keyboard navigation**: Every interactive element must be keyboard accessible. Focus trapping in modals
  - Keyboard support is the fastest practical test of whether your component model respects real interaction constraints.
- **Focus management**: Move focus after route changes, modal open/close, dynamic content insertion
  - Good focus flow keeps dynamic Vue interfaces understandable instead of disorienting.
- **Screen reader testing**: Use VoiceOver (macOS), NVDA (Windows). Test regularly
  - Manual testing catches issues that lint rules and automated audits cannot fully understand; docs: [VoiceOver](https://support.apple.com/guide/voiceover/welcome/mac), [NVDA](https://www.nvaccess.org/download/).
- **Color contrast**: WCAG AA minimum (4.5:1 for text). Use tooling to verify
  - Contrast is a design-system concern as much as an implementation concern, so test your tokens and components together.
- **`eslint-plugin-vuejs-accessibility`**: Catch common a11y issues at lint time
  - Linting helps prevent regressions, but it is strongest when paired with design reviews and manual testing; docs: [`eslint-plugin-vuejs-accessibility`](https://vue-a11y.github.io/eslint-plugin-vuejs-accessibility/).

**Practice**: Take your existing app and run a Lighthouse accessibility audit. Fix every issue. Add keyboard navigation to all interactive components. Test with a screen reader.

---

## Phase 9: Testing

### 9.1 Unit Testing with Vitest

- **Why Vitest**: Vite-native, Jest-compatible API, fast, ESM-first. Use it over Jest for Vue 3 projects
  - Vitest keeps the test environment close to the app's actual build tooling, which reduces config friction; docs: [Testing](https://vuejs.org/guide/scaling-up/testing.html), [Vitest](https://vitest.dev/guide/).
- **Configuration**: `vitest.config.ts` or `vite.config.ts` with test config. `@vue/test-utils` for component testing
  - Solid config pays off when you need aliases, DOM APIs, setup files, and consistent mocks across the whole suite.
- **Testing composables**: Call inside a component context using `withSetup()` helper or test directly if no lifecycle hooks
  - The main question is whether the composable relies on lifecycle, injection, or DOM context.
- **Testing utilities/services**: Standard unit tests, no Vue-specific tooling needed
  - Keep non-UI logic framework-agnostic so it stays cheap to test and easy to refactor.

### 9.2 Component Testing with Vue Test Utils

- **`mount()` vs `shallowMount()`**: `mount` renders children, `shallowMount` stubs them. Use `mount` by default for more realistic tests
  - Full rendering catches integration mistakes earlier, while shallow rendering is mostly for isolating a component with noisy children; docs: [Vue Test Utils Guide](https://test-utils.vuejs.org/guide/).
- **Finding elements**: `wrapper.find()`, `wrapper.findComponent()`, `wrapper.findAll()`. Use `data-testid` attributes
  - Stable selectors make tests resilient when markup structure changes for styling reasons.
- **User interaction**: `wrapper.trigger('click')`, `wrapper.setValue()`, `wrapper.setProps()`
  - Favor tests that simulate user-observable behavior instead of asserting private implementation details.
- **Asserting output**: `wrapper.text()`, `wrapper.html()`, `wrapper.classes()`, `wrapper.attributes()`, `wrapper.emitted()`
  - Assert what matters to the user or the parent contract, not every incidental DOM detail.
- **Async behavior**: `await nextTick()`, `await flushPromises()`, `await wrapper.vm.$nextTick()`
  - Most flaky Vue tests come from missing the right async boundary before making assertions.
- **Mocking**:
  - **Props**: Pass in `mount(Component, { props: { ... } })`
  - **Slots**: Pass in `mount(Component, { slots: { default: '...', header: MyComponent } })`
  - **Global plugins**: `mount(Component, { global: { plugins: [router, pinia] } })`
  - **Provide/inject**: `mount(Component, { global: { provide: { key: value } } })`
  - **Stubs**: `mount(Component, { global: { stubs: { RouterLink: true } } })`
  - **API calls**: Mock the service module, not axios directly
  - Mock the boundary your component actually depends on so tests stay decoupled from lower-level implementation changes.

### 9.3 E2E Testing with Playwright or Cypress

- **Playwright** (recommended): Faster, multi-browser, better async handling
  - Playwright is a strong default because it handles modern browser behavior and CI well; docs: [Playwright](https://playwright.dev/docs/intro).
- **Cypress**: More mature ecosystem, excellent developer experience, interactive test runner
  - Cypress still shines when fast local iteration and debugging are more important than broad browser coverage; docs: [Cypress](https://docs.cypress.io/).
- **What to E2E test**: Critical user flows — registration, login, checkout, core feature CRUD
  - Reserve E2E coverage for the workflows that would be most expensive to break in production.
- **Page Object Model**: Encapsulate page selectors and actions in reusable classes
  - Page objects help only when they reduce duplication without hiding test intent behind too much abstraction.
- **Test isolation**: Each test should set up its own data. Never depend on test ordering
  - Isolation is what keeps E2E suites reliable enough to trust in CI.
- **Visual regression**: `@playwright/test` screenshot comparison, or Percy for cross-browser visual testing
  - Visual checks are best for layout-heavy UI where DOM assertions miss obvious regressions.
- **CI integration**: Run E2E in headless mode in CI. Use Playwright's built-in CI config
  - CI is where flaky assumptions surface, so keep browser setup deterministic and observable.

### 9.4 Testing Strategy

| Layer | Tool | What to Test | Coverage Goal |
|---|---|---|---|
| Unit | Vitest | Composables, utilities, services, stores | High (80%+) |
| Component | Vitest + Vue Test Utils | Component behavior, props, events, slots | Medium-high |
| Integration | Vitest + Vue Test Utils | Connected components, store interactions | Medium |
| E2E | Playwright | Critical user flows | Key flows only |

**Practice**: Write full test coverage for a feature: unit tests for the composable/store, component tests for the UI, and an E2E test for the complete user flow.

---

## Phase 10: Real-World Ecosystem & Deployment

### 10.1 UI Component Libraries

| Library | Style | Best For |
|---|---|---|
| [**Headless UI**](https://headlessui.com/) (`@headlessui/vue`) | Unstyled, accessible | Custom-designed apps with Tailwind |
| [**Radix Vue**](https://www.radix-vue.com/) | Unstyled, accessible primitives | Building design systems |
| [**shadcn-vue**](https://www.shadcn-vue.com/) | Radix Vue + Tailwind presets | Rapid development with good defaults |
| [**PrimeVue**](https://primevue.org/) | Full-featured, themeable | Enterprise/data-heavy apps |
| [**Vuetify**](https://vuetifyjs.com/) | Material Design | Apps following Material spec |
| [**Naive UI**](https://www.naiveui.com/) | TypeScript-first, customizable | TypeScript-heavy projects |
| [**Element Plus**](https://element-plus.org/) | Enterprise-focused | Admin panels, dashboards |

### 10.2 CSS Approach

- **Tailwind CSS**: Utility-first. Most popular choice with Vue. `@apply` for reusable component styles
  - Tailwind works especially well in Vue because template-driven UI makes utility classes easy to co-locate with markup; docs: [Tailwind CSS](https://tailwindcss.com/docs/installation).
- **Scoped CSS**: Vue's built-in `<style scoped>`. Good for small/medium projects
  - Scoped CSS is often the fastest path when you want local styling without adopting a broader styling framework.
- **CSS Modules**: `<style module>` in SFCs. Better for library authors
  - CSS Modules are useful when consumers should not need to know or trust your class naming conventions.
- **UnoCSS**: Faster atomic CSS engine, Tailwind-compatible. Consider for performance-critical builds
  - UnoCSS is worth considering when you like utility workflows but want more generation flexibility or speed; docs: [UnoCSS](https://unocss.dev/).

### 10.3 Meta-Frameworks

- **Nuxt 3**: The full-stack Vue framework. SSR, SSG, API routes, auto-imports, file-based routing
  - Nuxt adds conventions and server capabilities that are hard to recreate cleanly in a hand-rolled SPA; docs: [Nuxt](https://nuxt.com/docs/getting-started/introduction).
  - **When to use Nuxt**: SEO matters, you need SSR, you want conventions over configuration, full-stack features
  - **Key features**: `useFetch()` / `useAsyncData()`, server routes, middleware, layouts, auto-imported composables and components, Nitro server engine
- **VitePress**: Static site generator for documentation. Markdown-based with Vue components
  - VitePress is a great way to stay inside the Vue mental model while building docs or internal knowledge bases; docs: [VitePress](https://vitepress.dev/).
- **Quasar**: Build desktop (Electron), mobile (Capacitor), and web from one codebase
  - Quasar is worth studying when product requirements span platforms and you want one Vue-centric workflow; docs: [Quasar](https://quasar.dev/).

### 10.4 Essential Ecosystem Packages

| Package | Purpose |
|---|---|
| [`pinia`](https://pinia.vuejs.org/) | State management |
| [`vue-router`](https://router.vuejs.org/) | Routing |
| [`@tanstack/vue-query`](https://tanstack.com/query/latest/docs/framework/vue/overview) | Server state / data fetching |
| [`vee-validate`](https://vee-validate.logaretm.com/v4/) + [`zod`](https://zod.dev/) | Form validation |
| [`vue-i18n`](https://vue-i18n.intlify.dev/) | Internationalization |
| [`@vueuse/core`](https://vueuse.org/) | Composable utilities |
| [`vue-chartjs`](https://vue-chartjs.org/) / [`echarts`](https://echarts.apache.org/en/index.html) | Data visualization |
| [`@iconify/vue`](https://iconify.design/docs/icon-components/vue/) | Icon library (access to 100k+ icons) |
| [`nprogress`](https://ricostacruz.com/nprogress/) | Page load progress bar |
| [`vue-toastification`](https://vue-toastification.maronato.dev/) | Toast notifications |
| [`floating-vue`](https://floating-vue.starpad.dev/) | Tooltips, popovers, dropdowns |

### 10.5 Build & Deployment

- **Vite production build**: `vite build` — tree-shaking, minification, code splitting, asset hashing
  - Learn what the production build emits so deployment bugs feel diagnosable instead of mysterious; docs: [Vite Guide](https://vite.dev/guide/).
- **Environment modes**: `.env`, `.env.production`, `.env.staging`. Only `VITE_*` vars are exposed to client
  - Modes let you keep environment-specific behavior explicit and reviewable without hardcoding values.
- **Preview**: `vite preview` — serve the production build locally for verification
  - Always preview the built app before shipping because dev mode can hide routing and asset issues.
- **Deployment targets**:
  - **Static hosting** ([Netlify](https://docs.netlify.com/), [Vercel](https://vercel.com/docs), [Cloudflare Pages](https://developers.cloudflare.com/pages/)): Best for SPAs and SSG
  - **Node server** (SSR with Nuxt): Deploy to any Node host, serverless functions, or edge
  - **Docker**: Multi-stage build (Node for build, nginx for serve); docs: [Docker](https://docs.docker.com/)
  - Choose the target based on rendering strategy and ops constraints, not on whichever platform is most popular.
  ```dockerfile
  # Build stage
  FROM node:20-alpine AS build
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  RUN npm run build

  # Production stage
  FROM nginx:alpine
  COPY --from=build /app/dist /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  ```
- **CI/CD**: GitHub Actions for lint, type-check, test, build, deploy. Run all checks in parallel
  - A dependable pipeline is what turns “works on my machine” into a repeatable team workflow; docs: [GitHub Actions](https://docs.github.com/actions).

### 10.6 Monitoring & Analytics

- **Sentry** (`@sentry/vue`): Error tracking with Vue-specific context (component name, props, route)
  - Error monitoring matters most after launch, when bugs start showing up under real data and real devices; docs: [Sentry for Vue](https://docs.sentry.io/platforms/javascript/guides/vue/).
- **Vue DevTools**: Browser extension for inspecting components, state, routes, Pinia stores, performance timeline
  - DevTools is one of the fastest ways to build intuition about how Vue is actually updating your app; docs: [Vue DevTools](https://devtools.vuejs.org/).
- **Lighthouse CI**: Automated performance, accessibility, SEO audits in CI
  - Automating audits helps you catch regressions before they quietly pile up release after release; docs: [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci).
- **Web Vitals**: Track LCP, FID, CLS with `web-vitals` library
  - These metrics connect frontend implementation choices to user-perceived performance in a concrete way; docs: [`web-vitals`](https://github.com/GoogleChrome/web-vitals).

---

## Capstone Projects

Build these to demonstrate job-ready Vue.js skills:

### Project 1: Project Management Dashboard
- Authentication with JWT (login, register, token refresh)
  - This project should prove you can handle real auth flows, guarded routes, and token lifecycle edge cases.
- Dashboard with real-time data (WebSocket updates)
  - Real-time data makes you practice reconciliation between server pushes, local cache, and UI responsiveness.
- Kanban board with drag-and-drop (`vue-draggable-plus`)
  - Drag-and-drop adds interaction complexity that reveals whether your state model is truly robust; docs: [`vue-draggable-plus`](https://vue-draggable-plus.pages.dev/en/).
- Data tables with sorting, filtering, pagination (TanStack Table)
  - Tables are a good test of whether you can organize view state, server state, and reusable UI patterns cleanly; docs: [TanStack Table for Vue](https://tanstack.com/table/latest/docs/framework/vue/overview).
- Charts and analytics (`vue-chartjs`)
  - This is where you practice integrating imperative third-party visualization libraries into Vue's reactive world; docs: [`vue-chartjs`](https://vue-chartjs.org/).
- Dark mode toggle with system preference detection
  - Theme switching sounds small, but it exercises persistence, accessibility, and design-system discipline.
- Full Pinia store architecture with persistence
  - Treat this as an architecture exercise, not just a checklist item, because store shape affects the whole app.
- Comprehensive test suite (unit + component + E2E)
  - Aim for a feature-complete testing story that shows you know where each testing layer adds value.
- Deploy to Vercel/Netlify with CI/CD
  - Finishing deployment makes the project portfolio-ready instead of a local-only code sample; docs: [Vercel](https://vercel.com/docs), [Netlify](https://docs.netlify.com/).

### Project 2: E-Commerce Storefront
- Product catalog with faceted search and filters
  - This is a strong way to demonstrate derived state, query parameters, and responsive listing UX.
- Shopping cart with optimistic updates
  - Cart behavior reveals whether you can balance server truth with fast-feeling UI feedback.
- Multi-step checkout form with validation (VeeValidate + Zod)
  - Checkout is a good pressure test for form ergonomics, validation boundaries, and error recovery; docs: [VeeValidate](https://vee-validate.logaretm.com/v4/), [Zod](https://zod.dev/).
- User account with order history
  - This feature lets you show route organization, authenticated API access, and reusable account layouts.
- Responsive design with Tailwind CSS
  - Make responsiveness a system-level concern so the layout still feels intentional on smaller screens; docs: [Tailwind CSS](https://tailwindcss.com/docs/installation).
- Performance optimized: lazy loading, virtual scrolling, image optimization
  - Use this project to prove you can measure and improve performance instead of just naming the techniques.
- SEO with Nuxt 3 (SSR/SSG hybrid)
  - Nuxt gives you a realistic venue for handling metadata, crawlability, and hybrid rendering tradeoffs; docs: [Nuxt](https://nuxt.com/docs/getting-started/introduction).
- Accessibility audit passing WCAG AA
  - Treat the audit as a design and implementation deliverable, not a final-day cleanup step.
- Internationalization (i18n) with at least 2 languages
  - i18n forces you to think about routing, formatting, layout expansion, and content architecture together.

### Project 3: Real-Time Collaboration App
- Rich text editor (`tiptap` — built on ProseMirror, has Vue integration)
  - Editors surface hard UI problems around selection state, commands, and controlled/uncontrolled boundaries; docs: [Tiptap for Vue 3](https://tiptap.dev/docs/editor/getting-started/install/vue3), [ProseMirror](https://prosemirror.net/docs/).
- Real-time collaboration with WebSockets and operational transforms / CRDTs
  - This is the kind of feature that demonstrates systems thinking, not just frontend component skills.
- Document organization with nested folders (tree component)
  - Tree UIs are great practice for recursion, keyboard support, and deep state updates.
- Share and permissions system (view, edit, admin)
  - Permissions modeling shows whether you can connect product rules to both UI affordances and routing.
- Offline support with service workers and IndexedDB
  - Offline capability adds real-world complexity around sync, caching, and recovery after reconnect.
- File attachments with drag-and-drop upload and preview
  - Attachments combine browser APIs, async progress, and user feedback loops in one feature.
- Command palette (`vue-command-palette`) for power users
  - A command palette is a strong way to show composable search, keyboard UX, and action architecture; docs: [`vue-command-palette`](https://www.npmjs.com/package/vue-command-palette).
- Keyboard shortcuts throughout the app
  - Global shortcuts force you to think carefully about scope, focus, and avoiding conflicts.
- Mobile-responsive layout
  - Collaboration tools often get crowded quickly, so responsive behavior is a real design challenge here.

---

## Study Methodology

1. **Read the Vue 3 docs** — they're excellent and interactive. Use this guide as a roadmap, the official docs as the textbook
   - Start with the guide sections that match your current phase so the official material reinforces what you are building; docs: [Vue Guide](https://vuejs.org/guide/introduction.html).
2. **Use TypeScript from the start** — Vue 3's TS support is first-class. The job market expects it
   - TypeScript is most valuable when it shapes your component APIs, store contracts, and backend data models from day one.
3. **Master the Composition API** — the Options API still works but Composition API is the standard for new production code
   - Composition API fluency is what lets you organize larger features without duplicating logic across components.
4. **Build composables for everything** — the composable pattern is the single most important skill for production Vue
   - Practice spotting repeated reactive patterns and extracting them before they turn into copy-pasted setup blocks.
5. **Use Vue DevTools constantly** — inspect component trees, track state changes, debug reactivity
   - DevTools shortens the feedback loop because you can inspect the live component graph instead of guessing at state flow; docs: [Vue DevTools](https://devtools.vuejs.org/).
6. **Read source code** — VueUse, Pinia, and Vue Router are all well-written and instructive
   - Reading good source teaches naming, API design, cleanup patterns, and TypeScript techniques you can reuse immediately.
7. **Test as you build** — testing is a non-negotiable skill for professional Vue development
   - Writing tests during development helps you design clearer component boundaries and catch regressions before features sprawl.
8. **Learn Nuxt after you're solid on Vue** — Nuxt adds SSR/SSG, file-based routing, and full-stack capabilities. Most Vue job listings mention Nuxt
   - Nuxt is much easier to absorb once core reactivity, routing, and component design already feel natural.

---

## Additional Reference Links

- **Vue core references**:
  - [Vue API Reference](https://vuejs.org/api/)
  - [Vue Style Guide](https://vuejs.org/style-guide/)
  - [Vue SFC Playground](https://play.vuejs.org/)
- **Language and platform references**:
  - [TypeScript Handbook](https://www.typescriptlang.org/docs/)
  - [MDN Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
  - [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData)
- **Browser APIs that show up throughout this guide**:
  - [AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
  - [Intersection Observer API](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API)
  - [Window.matchMedia()](https://developer.mozilla.org/en-US/docs/Web/API/Window/matchMedia)
  - [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
  - [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
  - [IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- **Accessibility standards and patterns**:
  - [WAI-ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
  - [WCAG Overview](https://www.w3.org/WAI/standards-guidelines/wcag/)

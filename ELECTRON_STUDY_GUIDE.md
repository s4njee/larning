# Desktop GUI Development with Electron

A depth-first guide to building desktop GUI applications, using Electron as the example framework — written specifically for engineers who come from **web development and Linux/backend systems and have never built a desktop GUI app.** If your experience looks like the rest of this repo — you're comfortable with Vue, TypeScript, and Node.js on the front, and Docker, distributed systems, and Linux on the back, but "build a native desktop app" has always been someone else's job — this guide is the bridge.

That background is not a disadvantage here; it's the on-ramp. Electron is, quite literally, **a web front-end (Chromium) wired to a Node.js back-end**, packaged as a desktop app. So roughly 80% of Electron is skills you already have: the UI is web (use Vue — your stack — or React or Svelte), and the privileged "backend" of the app is Node.js (the subject of the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md)). The communication between them is a client-server message boundary, which you already understand from the [Distributed Systems](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) and [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) guides. **This guide spends most of its energy on the other 20% — the parts that have no web or backend analogue and are where every web developer building their first desktop app gets surprised:** the desktop process and lifecycle model, native OS integration, the security model of running web code with system access, and the genuinely hard problem of *packaging, signing, and shipping* software that runs on someone else's machine instead of your server.

It's opinionated where it should be — including an honest accounting of Electron's costs (memory, bundle size) and a clear-eyed comparison to **Tauri** (Rust + the OS webview — relevant given you're learning Rust) and to native toolkits like **Qt** (covered in the [Qt guide](QT_STUDY_GUIDE.md)). By the end you'll know not just how to build an Electron app, but when *not* to.

Primary references: the [Electron documentation](https://www.electronjs.org/docs/latest/) (excellent — read the Process Model and Security pages in full), [Electron Fiddle](https://www.electronjs.org/fiddle) (a scratchpad for trying APIs), and [Electron Forge](https://www.electronforge.io/) (the official build toolchain). Companion guides in this repo: [Advanced Node.js](ADVANCED_NODEJS_STUDY_GUIDE.md), [Vue](VUE_STUDY_GUIDE.md), [TypeScript](TYPESCRIPT_STUDY_GUIDE.md), and [GitHub Actions](GITHUB_ACTIONS_STUDY_GUIDE.md) (for CI builds).

---

## Table of Contents

1. [Part 1 — From Web to the Desktop](#part-1--from-web-to-the-desktop)
2. [Part 2 — The Multi-Process Architecture](#part-2--the-multi-process-architecture)
3. [Part 3 — IPC & the Process Boundary](#part-3--ipc--the-process-boundary)
4. [Part 4 — The Renderer & Your Web Skills](#part-4--the-renderer--your-web-skills)
5. [Part 5 — Native OS Integration](#part-5--native-os-integration)
6. [Part 6 — Data Files & Storage](#part-6--data-files--storage)
7. [Part 7 — Security](#part-7--security)
8. [Part 8 — Packaging & Distribution](#part-8--packaging--distribution)
9. [Part 9 — Auto-Updates & Performance](#part-9--auto-updates--performance)
10. [Part 10 — Alternatives & a Build Walkthrough](#part-10--alternatives--a-build-walkthrough)

---

## Part 1 — From Web to the Desktop

Before any code, the mindset shift. You already know how to build software that runs on a server you control and is delivered to a browser you don't. Desktop development inverts several of those assumptions, and naming the inversions up front prevents most of the confusion that follows.

### What's the Same (Your Existing Skills)

Electron is Chromium + Node.js in a trench coat, so a large amount transfers directly:

- **The UI is a web page.** HTML, CSS, the DOM, your framework of choice (Vue, React, Svelte), your bundler (Vite). Everything you know about building a web front-end applies unchanged. A `<button>` is a `<button>`.
- **The privileged layer is Node.js.** The part of the app that touches the operating system is a Node process — same `fs`, `path`, `process`, npm ecosystem, `async`/`await`, and event-loop discipline from the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md). If you've written a Node service, you've written half of an Electron app.
- **The two halves talk over a message boundary.** Not HTTP, but the *shape* is the same as any client-server system: a less-trusted client (the UI) asks a more-trusted server (the Node layer) to do things, over a serialized channel. Your instincts from APIs, WebSockets, and distributed systems all apply.

### What's Genuinely New (Where to Spend Your Energy)

These have no clean web or backend analogue, and they are the real content of this guide:

1. **Your code runs on the user's machine, not your server.** This is the deepest shift. You don't control the OS, the hardware, the other software, the antivirus, or *when the user updates*. There is no "deploy" button that atomically replaces the running version for everyone. You ship a binary and lose control of it. Everything about distribution (Part 8) and auto-updates (Part 9) exists because of this one fact.
2. **The app is long-lived and stateful, not request-scoped.** A web request is born, serves a response, and dies — statelessness is a virtue you've been taught to cultivate. A desktop app *opens*, lives for hours or days holding in-memory state, manages windows, responds to the OS sleeping and waking, and *quits*. You think in terms of an application *lifecycle* and *event loop over the app's whole lifetime*, not per-request handlers.
3. **You own the whole window, and the OS has opinions.** There's no browser chrome handed to you — you decide whether there's a title bar, a menu, a tray icon, what the close button does. And each OS (Windows, macOS, Linux) has different, strongly-held conventions you must respect (Part 5). "Cross-platform" means *three platforms' worth of native behavior*, not one.
4. **Local-first data.** No central Postgres that every client shares. Data lives on the user's disk — files, a local SQLite database, app preferences — and *maybe* syncs to a server. Your data-modeling instincts from the [Postgres guide](POSTGRES.md) transfer, but the deployment target is "a few hundred MB on a laptop," not "a managed cluster."
5. **Shipping is hard in a way web shipping is not.** Web deploy is `git push` and a CI pipeline. Desktop "deploy" is: build a native installer for each OS, **cryptographically sign it** (or the OS refuses to run it), get macOS to **notarize** it, host it somewhere, and build an **auto-update** mechanism so users actually get your fixes. This is the part that shocks every web developer, and Part 8 is devoted to it.

### Why Electron Is the Right First GUI Framework for You

There are many ways to build a desktop GUI — native toolkits (Qt, GTK, WinUI, Swift), Flutter, Tauri. For *your* background specifically, Electron is the gentlest on-ramp precisely because it minimizes the new material:

- You build the UI with **web technology you already know**, so the "how do I lay out a UI" problem (huge in Qt or native toolkits, which have their own widget systems and layout models) is already solved for you.
- The native/privileged layer is **Node.js**, which you know.
- It is **truly cross-platform with consistent rendering** — the same Chromium renders your UI identically on all three OSes, so you don't fight per-platform rendering bugs (this is Electron's headline advantage over Tauri, Part 10).

The price — and it's real — is that you ship an entire browser engine with your app: ~100–150 MB of binary and a baseline of ~100+ MB of RAM before your app does anything. Whether that price is worth it is the central question of Part 10. For learning GUI development from a web background, it's absolutely the place to start, and for a great many real apps (VS Code, Slack, Discord, Figma's desktop app, Obsidian, Notion) it's the production choice.

If you remember one thing from Part 1: **Electron lets you reuse your web (UI) and Node (system) skills, so concentrate your learning on the five things that are actually new — running on the user's machine, the app lifecycle, owning the window, local-first data, and the hard problem of shipping signed installers with auto-updates.**

---

## Part 2 — The Multi-Process Architecture

Electron's architecture is the first thing to internalize, and your distributed-systems background makes it easy: **an Electron app is a tiny client-server system running on one machine.** There is one privileged "server," one or more sandboxed "clients," and a carefully controlled boundary between them.

### The Three Kinds of Code

Every Electron app has three distinct execution contexts. Confusing which code runs where is the single most common beginner mistake, so anchor these firmly:

| Context | Runs | Has Node.js access? | Analogy (from your world) |
|---|---|---|---|
| **Main process** | Node.js | ✅ full | The backend server — privileged, one per app |
| **Renderer process** | Chromium (a web page) | ❌ no (by default) | A browser tab / untrusted client — one per window |
| **Preload script** | Chromium context, before page load | ⚠️ limited, bridged | The API gateway / contract between them |

**The main process** is the entry point and the brain. It's a full Node.js environment (the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md) applies directly). It creates windows, controls the application lifecycle, and is the *only* place with unrestricted access to the operating system — the filesystem, native menus, dialogs, the tray, OS notifications. There is exactly **one** main process. Think of it as your backend server: privileged, trusted, and the thing everything else asks for favors.

**A renderer process** runs a web page inside a Chromium instance — one renderer per `BrowserWindow`. This is where your Vue/React/Svelte app lives. Critically, **by modern defaults a renderer has no Node.js access at all** — it's as sandboxed as a normal web page in a browser. It cannot read files, spawn processes, or touch the OS. It can only render UI and ask the main process to do privileged things, through the boundary. Treat it exactly as you'd treat an untrusted browser client: it might be compromised by malicious content or XSS, so it gets no direct power.

**The preload script** is the clever bit and the part with no web analogue. It runs *in the renderer's context* but *before your web page loads*, and it has access to a limited set of Node/Electron APIs **and** the page's `window` object. Its job is to be the **bridge**: it uses `contextBridge` to expose a small, specific, validated API to the renderer — never raw power, only named functions. It's the API contract / gateway between your untrusted UI and your privileged backend. (Security details in Part 7; for now, just know the preload is *where you decide exactly what the UI is allowed to ask for*.)

### Why Three Processes? (The Reason Maps to Your Instincts)

This split exists for the same reasons you separate a web client from a server: **security and stability.**

- **Security:** the renderer loads and runs web content, which is the attackable surface (XSS, malicious markup). If that code had direct OS access, an XSS bug would become *remote code execution on the user's laptop* — catastrophically worse than XSS on a website. So the renderer is locked down and the privileged code lives elsewhere, behind a validated boundary. This is "never trust the client," made load-bearing.
- **Stability:** processes are isolated. A renderer that crashes (a runaway script, an out-of-memory tab) takes down *its window*, not the whole app — the main process survives and can recover. This is the same blast-radius reasoning from the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md), applied locally.

They don't share memory. Like separate machines, they communicate only by passing serialized messages (Part 3).

### Your First Window

Here's a minimal main process. Every line maps to a lifecycle concept:

```javascript
// main.js — the main process (Node.js)
import { app, BrowserWindow } from "electron";
import path from "node:path";

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,                          // don't show until ready (avoids a white flash)
    webPreferences: {
      preload: path.join(import.meta.dirname, "preload.js"),
      contextIsolation: true,             // default — keep it on (Part 7)
      nodeIntegration: false,             // default — keep it off (Part 7)
      sandbox: true,                       // default — keep it on (Part 7)
    },
  });

  win.once("ready-to-show", () => win.show());   // show only when the page is painted

  if (process.env.NODE_ENV === "development") {
    win.loadURL("http://localhost:5173");        // Vite dev server (HMR) — Part 4
    win.webContents.openDevTools();
  } else {
    win.loadFile("dist/index.html");             // built assets in production
  }
}

app.whenReady().then(createWindow);
```

### The Application Lifecycle (and Its Cross-Platform Traps)

A web app has no "lifecycle" to speak of; a desktop app's lifecycle is central, and it differs by OS in ways that *will* trip you up:

```javascript
// The canonical lifecycle handling, with the macOS conventions baked in:

app.on("window-all-closed", () => {
  // Windows/Linux: closing the last window quits the app.
  // macOS: apps conventionally STAY RUNNING (in the dock) with no windows.
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  // macOS: clicking the dock icon with no windows open should re-create one.
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("before-quit", () => {
  // Last chance to save state, flush data, clean up. The app is shutting down.
});
```

That `process.platform !== "darwin"` check is the first piece of genuinely desktop-specific knowledge you need, and it encodes a real convention: macOS users expect apps to persist after the last window closes; Windows and Linux users expect the app to quit. Getting this wrong makes your app feel "wrong" on each platform in a way users notice immediately. Cross-platform desktop development is full of these — Part 5 has more.

### Single-Instance Apps

Most desktop apps should run as a single instance — if the user launches it again, focus the existing window rather than opening a second copy:

```javascript
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();                              // another instance is already running
} else {
  app.on("second-instance", () => {        // fired in the FIRST instance when a 2nd launches
    const win = BrowserWindow.getAllWindows()[0];
    if (win) { win.restore(); win.focus(); }
  });
}
```

If you remember one thing from Part 2: **an Electron app is a one-machine client-server system — one privileged Node.js main process (the backend), N sandboxed Chromium renderers (the clients/windows), and a preload bridge (the API contract) — and the app lifecycle, with its per-OS conventions, is something you now own and must handle explicitly.**

---

## Part 3 — IPC & the Process Boundary

The renderer can't touch the OS; the main process can. So everything privileged the UI needs — read a file, show a save dialog, query the local database — is a **request across the process boundary.** This is Inter-Process Communication (IPC), and for someone with your background it's the most familiar "new" concept in the guide: it's an API boundary, and you design it like one.

### The Mental Model: It's an API

Treat IPC exactly as you'd treat a client-server API (the [API design instincts](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) you have all apply):

- The renderer is the **client**; the main process is the **server**.
- Messages are **serialized** (via the structured clone algorithm — same as `postMessage` and Web Workers), so you can pass plain objects, arrays, numbers, strings, `ArrayBuffer`s — but **not** functions, class instances with methods, DOM nodes, or anything with behavior. If it doesn't survive `JSON`-ish serialization (plus a few extras like `Date` and `ArrayBuffer`), it can't cross.
- You **never trust the input** on the server side. The renderer could be compromised; validate every argument in the main process before acting (Part 7).

### The Two Patterns

**1. Request-response (`invoke`/`handle`) — the modern default.** The renderer asks for something and awaits a result. This is the one you'll use 90% of the time. It's async and returns a Promise — exactly like calling an API:

```javascript
// main.js — the "server" handler
import { ipcMain, dialog } from "electron";

ipcMain.handle("dialog:openFile", async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ["openFile"],
  });
  if (canceled) return null;
  return filePaths[0];                      // returned value resolves the renderer's Promise
});
```

```javascript
// renderer (via the preload bridge — see below)
const filePath = await window.api.openFile();   // feels like any async API call
```

**2. One-way / push (`send`/`on` and `webContents.send`).** Fire-and-forget events. Renderer → main with `ipcRenderer.send` + `ipcMain.on`; and crucially **main → renderer** with `webContents.send` (the only way to *push* to the UI — for progress updates, menu actions, OS events):

```javascript
// main.js — push an event TO a renderer (e.g., download progress)
win.webContents.send("download:progress", { percent: 42 });

// also: main listening to a fire-and-forget message from the renderer
ipcMain.on("analytics:event", (event, payload) => track(payload));   // no response
```

```javascript
// renderer — subscribe to pushed events
window.api.onDownloadProgress((data) => updateProgressBar(data.percent));
```

### Wiring It Through the Preload (the Right Way)

Here's the full, secure pattern — and it's worth memorizing because it's *the* idiom. The preload uses `contextBridge` to expose **specific named functions**, never the raw `ipcRenderer` object:

```javascript
// preload.js — the bridge / API contract
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("api", {
  // request-response: expose a clean async function, not the channel
  openFile: () => ipcRenderer.invoke("dialog:openFile"),
  saveNote: (note) => ipcRenderer.invoke("notes:save", note),

  // push: wrap the listener so the renderer can't access the raw event
  onDownloadProgress: (callback) =>
    ipcRenderer.on("download:progress", (_event, data) => callback(data)),
});
```

Now the renderer calls `window.api.openFile()` — a clean, typed, minimal surface. It cannot invoke arbitrary channels, cannot reach `ipcRenderer` directly, and cannot do anything you didn't explicitly expose. This is least-privilege API design, and it's both the ergonomic *and* the secure choice (Part 7 explains why exposing raw `ipcRenderer` is dangerous).

### Type the Boundary

Because the renderer and main are separate bundles, the IPC boundary is exactly the kind of place bugs hide — a renamed channel, a changed payload shape. Use TypeScript (the [TypeScript guide](TYPESCRIPT_STUDY_GUIDE.md)) to define the contract once and share it:

```typescript
// shared/api.ts — the contract both sides import
export interface Api {
  openFile(): Promise<string | null>;
  saveNote(note: Note): Promise<{ id: string }>;
  onDownloadProgress(cb: (data: { percent: number }) => void): void;
}
declare global {
  interface Window { api: Api; }   // now window.api is typed in the renderer
}
```

### IPC Design Principles

The same discipline you'd apply to any API:

- **Coarse-grained, intent-named channels**, not chatty ones. `notes:save` (one round trip) beats `db:open` + `db:write` + `db:close` (three). Each crossing has serialization cost.
- **Validate every payload in main.** The renderer is untrusted. A `notes:save` handler must check that the note is well-formed before writing it — never pass renderer input straight to `fs` or a SQL query.
- **Don't leak privilege.** Expose `saveNote(note)`, not `writeFile(path, data)`. The narrower the API, the smaller the blast radius if the renderer is compromised. Never expose a function that lets the renderer specify an arbitrary path or command.
- **Keep big data out of frequent messages.** Serialization copies. Streaming a large file byte-by-byte over IPC is slow; instead pass a path and let main stream it, or use a `MessagePort` for high-throughput channels.

If you remember one thing from Part 3: **IPC is an API boundary between an untrusted client (renderer) and a trusted server (main) — design it exactly as you'd design any client-server API: coarse-grained intent-named channels, exposed as specific functions through the preload bridge, with every payload validated in main.**

## Part 4 — The Renderer & Your Web Skills

This is the part you already know — so this chapter is short on fundamentals and long on *what's different about web development when the browser is yours*. The renderer is a Chromium page; your entire web toolkit applies. The differences are subtle but real, and they're mostly about the freedoms and responsibilities of controlling the whole browser.

### Use Your Framework — Probably Vue

The renderer is a web app, full stop. Use Vue (your stack — the [Vue guide](VUE_STUDY_GUIDE.md)), React, Svelte, or nothing. Use Vite for the build and dev server. The modern, well-trodden setup is **electron-vite** or **Electron Forge's Vite template**, which wires up three build targets — main, preload, and renderer — with hot-module reload for the renderer and auto-restart for main:

```bash
# Scaffold with Electron Forge + Vite + TypeScript:
npm init electron-app@latest my-app -- --template=vite-typescript
# Then drop your Vue app into the renderer source and point Vite at it.
```

The dev-vs-prod loading split from Part 2 is the key integration point: in development the `BrowserWindow` loads `http://localhost:5173` (the Vite dev server, so you get instant HMR while editing your Vue components); in production it loads the built `index.html` from disk. Your Vue dev loop is *exactly* what you're used to — edit a component, see it update — just inside a desktop window.

### What's Different From a Browser Tab

You now control the browser, which removes some web constraints and adds some responsibilities:

- **No deployment, no cache-busting, no "works in Safari?"** You ship one known version of Chromium. The entire category of cross-browser bugs vanishes — you target one engine, the one you bundled. (This is the headline advantage over Tauri, Part 10.)
- **CORS and same-origin still exist but matter differently.** Your UI is loaded from `file://` or a local dev server, and it talks to the OS through IPC, not `fetch`. You'll still `fetch` remote APIs, and CORS applies to those — but most of your "backend" calls are IPC, not HTTP.
- **You own the window chrome.** No browser toolbar, no tabs unless you build them. You decide whether there's a native title bar (`titleBarStyle`), whether the window is resizable, frameless, transparent, always-on-top. A **frameless window** (`frame: false`) with a custom CSS title bar is how apps like VS Code and Slack get their look — but then *you* must implement dragging (`-webkit-app-region: drag` in CSS), the minimize/maximize/close buttons, and their per-OS placement (macOS left, Windows right).
- **`localStorage`, `IndexedDB`, and the Cache API work** — they're Chromium features — and persist per-renderer. But for app data you'll usually want something more robust (Part 6).
- **DevTools are the same Chrome DevTools you know** (`win.webContents.openDevTools()`), with the full Elements/Console/Network/Performance/Memory panels. Renderer debugging is identical to web debugging.

### Multiple Windows and Views

A web app is one page; a desktop app may have many windows — a main window, a preferences window, an about dialog, a spotlight-style quick-entry popup. Each `BrowserWindow` is its own renderer (its own process, its own state). They coordinate *through the main process* (Part 3), not directly — main is the shared, authoritative coordinator, the same role a server plays for multiple web clients.

For embedding web content *within* a window (a preview pane, an OAuth flow), modern Electron uses **`WebContentsView`** (the successor to the old `<webview>` tag and `BrowserView`), which lets you composite multiple web contents in one window with proper isolation. Avoid the legacy `<webview>` tag — it's heavier and has sharp security edges.

### The Renderer Can Still Block — It's Still One Thread

Your async discipline carries over directly: the renderer has a single main thread (the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md) Part 3 and the [async comparison guide](PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md) both apply). A heavy synchronous computation in the renderer **freezes the UI** — the desktop version of "janky web page," but worse because users expect *native* responsiveness from an installed app. Offload CPU work to a Web Worker (in the renderer) or, better, to the main process / a utility process (Part 9). The rule "never block the event loop" is now "never block the UI thread," and it's the same rule.

If you remember one thing from Part 4: **the renderer is just a web app with your framework of choice and full Chromium DevTools — what changes is that you own the whole window (chrome, multiple windows, no cross-browser worries) and you must still respect the single UI thread.**

---

## Part 5 — Native OS Integration

This is the first chapter that is *entirely* new — none of it has a web or backend analogue. Native integration is what makes an app feel like a real desktop application instead of a website in a frame, and it's where "cross-platform" reveals itself to mean "three platforms, each with its own conventions." Get these right and your app feels native; get them wrong and it feels like a port.

### Menus

Desktop apps have menus, and the conventions differ sharply by OS:

- **macOS** has a single global **menu bar** at the top of the screen, always present, with a mandatory app-named first menu. The first menu item conventions (About, Preferences with ⌘,, Quit with ⌘Q) are deeply ingrained.
- **Windows and Linux** put the menu **inside the window**, and many modern apps hide it behind a hamburger or custom UI.

Electron's `Menu` API builds from a template, and **roles** give you correct, localized, platform-appropriate behavior for free:

```javascript
import { Menu } from "electron";

const isMac = process.platform === "darwin";
const template = [
  // macOS needs the app menu as the first item:
  ...(isMac ? [{ role: "appMenu" }] : []),
  {
    label: "File",
    submenu: [
      { label: "New Note", accelerator: "CmdOrCtrl+N", click: () => createNote() },
      { type: "separator" },
      isMac ? { role: "close" } : { role: "quit" },   // per-OS convention
    ],
  },
  { role: "editMenu" },     // Undo/Redo/Cut/Copy/Paste — correct on every OS, free
  { role: "viewMenu" },     // Reload, DevTools, zoom — handy in dev
];
Menu.setApplicationMenu(Menu.buildFromTemplate(template));
```

Use `role` wherever one exists — `CmdOrCtrl` automatically maps to ⌘ on macOS and Ctrl elsewhere, and roles like `editMenu` produce the entire standard Edit menu with working shortcuts on all three platforms. **Hand-rolling copy/paste is a classic beginner mistake**; the role does it correctly.

### The System Tray

A tray icon (menu-bar icon on macOS, system-tray/notification-area icon on Windows/Linux) lets your app live in the background — essential for chat apps, sync clients, and utilities:

```javascript
import { Tray, Menu, nativeImage } from "electron";

let tray;   // keep a reference, or it gets garbage-collected and disappears
app.whenReady().then(() => {
  tray = new Tray(nativeImage.createFromPath("assets/trayTemplate.png"));
  tray.setToolTip("My App");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open", click: () => showMainWindow() },
    { label: "Quit", role: "quit" },
  ]));
});
```

(A gotcha worth the comment: forget to hold the `tray` reference and V8 garbage-collects it, and your icon mysteriously vanishes. Name your template icons `…Template.png` on macOS for automatic dark/light adaptation.)

### Native Dialogs, Notifications, and Shell

These bridge to OS features the user already trusts:

```javascript
import { dialog, Notification, shell } from "electron";

// Native file picker (returns real filesystem paths):
const { filePaths } = await dialog.showOpenDialog({ properties: ["openFile", "multiSelections"] });

// Native save dialog:
const { filePath } = await dialog.showSaveDialog({ defaultPath: "untitled.md" });

// Native OS notification (the web Notification API also works in the renderer):
new Notification({ title: "Sync complete", body: "42 notes updated" }).show();

// Hand off to the OS — open a URL in the default browser, reveal a file, etc.:
shell.openExternal("https://example.com");     // default browser, NOT an Electron window
shell.showItemInFolder("/path/to/file");        // open the OS file manager at this file
shell.openPath("/path/to/document.pdf");        // open in the default app
```

`shell.openExternal` is important and easy to get wrong: **external links must open in the user's real browser, not inside your app's window.** Letting a remote URL load inside a `BrowserWindow` is both a UX mistake and a security hole (Part 7). Intercept link clicks and route them through `shell.openExternal`.

### Global Shortcuts, Theme, and Power

```javascript
import { globalShortcut, nativeTheme, powerMonitor } from "electron";

// A shortcut that works even when your app isn't focused (use sparingly — they're global):
app.whenReady().then(() => {
  globalShortcut.register("CmdOrCtrl+Shift+Space", () => toggleQuickEntry());
});

// Follow the OS dark/light setting (and react when the user changes it):
const isDark = nativeTheme.shouldUseDarkColors;
nativeTheme.on("updated", () => updateTheme(nativeTheme.shouldUseDarkColors));

// React to the machine sleeping/waking — pause sync, reconnect sockets, etc.:
powerMonitor.on("suspend", () => pauseSync());
powerMonitor.on("resume", () => resumeSync());
```

### Deep Links and File Associations

To make your app open when the user clicks a `myapp://...` link or double-clicks a `.mynote` file:

- **Custom protocol:** `app.setAsDefaultProtocolClient("myapp")`, then handle the `open-url` event (macOS) or parse `process.argv` (Windows/Linux) where the URL arrives. Deep links are how OAuth callbacks and "open in app" buttons reach your app.
- **File associations** are declared in the packaging config (Part 8) and arrive via the `open-file` event (macOS) or `argv`.

### The Cross-Platform Reality

Notice how often `process.platform` appeared. This is the texture of desktop development: the *capabilities* are cross-platform, but the *conventions* are not. macOS wants a global menu bar and apps that outlive their windows; Windows wants in-window menus and an installer with Start-menu entries; Linux wants `.desktop` files and respects a dozen desktop environments. **Budget real time for per-platform polish and testing on each OS** — a VM or a CI matrix (Part 8) is not optional. "Write once, run anywhere" is true for your *logic* and a polite fiction for your *native feel*.

If you remember one thing from Part 5: **native integration (menus, tray, dialogs, shortcuts, theme, deep links) is what separates a real app from a web page in a frame — lean on Electron's `role`-based menus and native APIs, and accept that each OS has conventions you must honor with `process.platform` branches.**

---

## Part 6 — Data Files & Storage

A web app's data lives in a database you control on a server. A desktop app's data lives on the user's disk, and *you* are responsible for where it goes, how it's structured, and what happens when the app updates. Your SQL and data-modeling skills transfer (the [Postgres guide](POSTGRES.md) applies), but the deployment target and the access model are new.

### Where Data Goes: `app.getPath`

Never hardcode paths — every OS has different conventions for where app data belongs, and writing to the wrong place breaks on locked-down systems. `app.getPath` gives you the correct, per-OS location:

```javascript
import { app } from "electron";

app.getPath("userData");   // YOUR app's data dir — the main one you'll use
//   macOS:   ~/Library/Application Support/<AppName>
//   Windows: C:\Users\<user>\AppData\Roaming\<AppName>
//   Linux:   ~/.config/<AppName>
app.getPath("documents");  // the user's Documents folder
app.getPath("downloads");  // Downloads
app.getPath("temp");       // temp dir
app.getPath("logs");       // log dir
```

`userData` is your app's private sandbox — config, database, caches all go under it. Using it (instead of, say, writing next to the executable, which may be read-only) is the difference between an app that works and one that crashes on a managed corporate laptop.

### Choosing a Storage Mechanism

| Need | Use | Notes |
|---|---|---|
| App preferences, small config | **`electron-store`** | JSON file under `userData`, dead simple, schema + migrations |
| Structured/relational data, queries | **`better-sqlite3`** | A real SQL database, local, *synchronous*, very fast — runs in main |
| Large blobs (images, attachments) | files under `userData` | store paths in your DB, blobs on disk |
| Renderer-local, web-style storage | `IndexedDB` / `localStorage` | fine for UI state; not your source of truth |

**For anything beyond preferences, reach for SQLite via `better-sqlite3`.** This is where your database skills pay off directly: it's real SQL — tables, indexes, transactions, joins, `WHERE` clauses — just running locally against a file instead of a server. Everything you know from the [Postgres guide](POSTGRES.md) about schema design, indexing, and queries applies (with SQLite's smaller feature set). `better-sqlite3` is *synchronous*, which is unusual but correct here: it's so fast for local single-user access that synchronous calls in the main process are fine, and the API is simpler for it.

```javascript
// main process — a local SQLite database
import Database from "better-sqlite3";
import path from "node:path";
import { app } from "electron";

const db = new Database(path.join(app.getPath("userData"), "notes.db"));
db.pragma("journal_mode = WAL");          // better concurrency/durability (your Postgres WAL knowledge applies)

db.exec(`CREATE TABLE IF NOT EXISTS notes (
  id    TEXT PRIMARY KEY,
  body  TEXT NOT NULL,
  updated_at INTEGER NOT NULL
)`);

// Prepared statements — same discipline as any SQL (prevents injection, faster):
const insert = db.prepare("INSERT INTO notes (id, body, updated_at) VALUES (?, ?, ?)");

// Expose via IPC — the renderer asks, main executes (Part 3):
ipcMain.handle("notes:save", (event, note) => {
  // VALIDATE first — never trust renderer input in a SQL statement (Part 7)
  insert.run(note.id, note.body, Date.now());
  return { id: note.id };
});
```

### The Golden Rule: Filesystem Access Lives in Main

The renderer is sandboxed and *should not* touch the filesystem directly (Part 7). All file and database access happens **in the main process**, exposed to the UI through validated IPC handlers (Part 3). The renderer says "save this note" (`window.api.saveNote(note)`); main validates and writes it. This is the same trust boundary as a web app: the client never gets a raw database handle, it calls an endpoint that does the work after checking the request.

### Native Modules: The `electron-rebuild` Gotcha

`better-sqlite3` and other native modules are compiled C/C++ addons. Here's a sharp edge that will bite you: **native modules are compiled against a specific V8/Node ABI, and Electron bundles its *own* version of V8** — different from your system Node. So a native module installed with plain `npm install` is built for the wrong runtime and will fail to load in Electron with a cryptic version-mismatch error. The fix is to rebuild native modules against Electron's ABI:

```bash
npx @electron/rebuild        # rebuilds native modules for Electron's V8 ABI
```

Electron Forge and electron-builder run this automatically, which is one more reason to use them (Part 8). But when you hit "Module was compiled against a different Node.js version," this is why — and now you know the fix.

### Data and App Updates

One local-first consideration with no web equivalent: when your app auto-updates (Part 9), the new version runs against the *old version's data on disk*. You own **schema migrations** on the client, running them at startup — the same discipline as server-side DB migrations, but now executing on thousands of users' machines with no DBA watching. Version your schema, migrate forward on launch, and never assume the data on disk matches your current code.

If you remember one thing from Part 6: **data lives on the user's disk under `app.getPath("userData")`; use `electron-store` for preferences and `better-sqlite3` for real data (your SQL skills transfer directly); keep *all* filesystem access in the main process behind validated IPC; and own your client-side schema migrations because the next app version inherits the last version's data.**

## Part 7 — Security

This is the chapter where your backend instincts make you *better* than the average Electron developer. Electron is web code with operating-system access, which means a web vulnerability can become a native compromise — an XSS that would merely deface a website can, in a misconfigured Electron app, read every file on the user's disk or run arbitrary commands. The good news: the threat model is one you already think in (*never trust the client*), and the defaults are now safe. Your job is to not turn them off and to guard the boundary you control.

### The Threat Model

State it plainly: **the renderer is untrusted, like any web client, but it lives inside a process that can reach the OS.** The attacker's path is: get malicious JavaScript running in your renderer (via an XSS in your own UI, a compromised npm dependency, or untrusted remote content you loaded), then use whatever power the renderer has — or can reach through the preload — to attack the user's machine. Every security control below is about shrinking what a compromised renderer can do.

This maps exactly to the "never trust the client" principle from web/backend security, with the stakes raised: the "client" is running on the victim's own computer with a Node.js process next door.

### The Non-Negotiable Defaults

Modern Electron ships secure by default. The cardinal rule is **do not disable these** — and you'll see tutorials (especially old ones) that do:

```javascript
new BrowserWindow({
  webPreferences: {
    contextIsolation: true,    // ✅ KEEP ON — isolates preload/Electron internals from page JS
    nodeIntegration: false,    // ✅ KEEP OFF — no require()/Node globals in the renderer
    sandbox: true,             // ✅ KEEP ON — renderer runs in an OS-level sandbox
    webSecurity: true,         // ✅ KEEP ON — enforces same-origin, CSP, etc.
  },
});
```

- **`nodeIntegration: false`** — the renderer gets no `require`, no `process`, no Node globals. Without this, an XSS is instant remote code execution (`require('child_process').exec(...)`). This single setting is the difference between "annoying web bug" and "the attacker owns the laptop."
- **`contextIsolation: true`** — your preload script and Electron's internals run in a *separate JavaScript context* from the page, so page scripts can't reach in and tamper with them (e.g., overwrite a prototype to hijack your bridged functions). This is what makes `contextBridge` actually safe.
- **`sandbox: true`** — the renderer runs in a Chromium OS-level sandbox, limiting what even native code can do if Chromium itself is exploited.

The old `nodeIntegration: true` pattern (Node directly in the renderer) appears all over old tutorials and Stack Overflow. **It is the single biggest Electron security mistake.** If a guide tells you to turn it on for convenience, close the guide.

### Guard the Preload Bridge

Part 3 said expose specific functions, not raw `ipcRenderer` — here's the security reason. If you do this:

```javascript
// ❌ DANGEROUS — exposes the entire IPC surface to page JavaScript
contextBridge.exposeInMainWorld("ipc", ipcRenderer);
```

then any XSS can invoke *any* IPC channel with *any* payload — it's a skeleton key to your whole main-process API. Instead, expose minimal, purpose-built functions, and **validate their arguments in main** (Part 3):

```javascript
// ✅ SAFE — a narrow, named API; the renderer can't reach arbitrary channels
contextBridge.exposeInMainWorld("api", {
  saveNote: (note) => ipcRenderer.invoke("notes:save", note),
});
```

And in the handler, treat the payload as hostile — exactly as you'd validate a request body on a web server:

```javascript
ipcMain.handle("notes:save", (event, note) => {
  if (typeof note?.id !== "string" || typeof note?.body !== "string") {
    throw new Error("invalid note");          // reject malformed input
  }
  // never interpolate into SQL/shell/path; use prepared statements / allowlists
  insert.run(note.id, note.body, Date.now());
});
```

A particularly important version of this: **never let the renderer specify a filesystem path, shell command, or URL that main acts on without validation.** `openFile(path)` where `path` comes from the renderer is a directory-traversal/arbitrary-read waiting to happen. Expose intent (`openProjectFile(id)`), resolve the path *in main* from trusted state, and validate it stays within an allowed directory.

### Control Navigation and Window Creation

A renderer that can navigate to an attacker's page, or open one, is a renderer that can load hostile code into your privileged context. Lock both down in main:

```javascript
app.on("web-contents-created", (_e, contents) => {
  // Block navigation away from your own app:
  contents.on("will-navigate", (event, url) => {
    if (!url.startsWith("file://") && !url.startsWith("http://localhost:5173")) {
      event.preventDefault();
    }
  });
  // Force window.open / target=_blank links to the real browser, not a new BrowserWindow:
  contents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
});
```

This is the enforcement behind Part 5's "external links open in the user's browser" — it's both UX and security.

### Content Security Policy

Defense-in-depth against XSS in the first place: set a strict CSP so that even if markup is injected, it can't load or execute arbitrary scripts. Deliver it as an HTTP header (best) or a meta tag:

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'">
```

A tight CSP plus framework auto-escaping (Vue/React escape interpolated content by default) is your primary XSS defense — and XSS is the entry point for nearly every Electron attack, so this is high-value.

### Don't Load Untrusted Remote Content (and If You Must, Isolate It)

The most dangerous thing an Electron app can do is load arbitrary remote web content into a privileged renderer. If your app must show third-party web content (an embedded site, user-supplied URLs), isolate it: load it in a separate `WebContentsView` with its own locked-down session/partition, `sandbox: true`, no preload, and the navigation guards above. Never load untrusted content in a window that has your preload bridge attached.

### Keep Electron Updated — This Is a Real Obligation

Electron bundles Chromium and Node.js, which means **you are now shipping a browser engine, and you inherit its security vulnerabilities.** When Chromium patches a critical CVE (which is often), you must update Electron and ship a new build to your users, or every install is running known-vulnerable browser code. This is a genuine, ongoing maintenance burden with no web equivalent (where the browser updates itself out from under you). It's a core reason auto-updates (Part 9) aren't optional: they're how you deliver security patches. Track Electron's release cadence and treat its security releases like the production incidents they are.

### Audit Your Supply Chain

You're shipping `node_modules` to users' machines. A compromised dependency runs with your app's privileges on their computer. Apply the supply-chain discipline from server-side work: lockfiles, `npm audit`, minimal dependencies, and scrutiny of anything in the main process or preload (which have the most power). Electron's official **`@electron/fuses`** lets you flip off dangerous capabilities (like `runAsNode`) at the binary level for defense-in-depth, and the **Electronegativity** tool statically scans your app for misconfigurations — run it in CI.

If you remember one thing from Part 7: **the renderer is untrusted code with an OS-capable process next door, so keep the secure defaults on (`contextIsolation`, `sandbox`, `nodeIntegration: false`), expose only narrow validated functions through the preload, control navigation, set a strict CSP, and keep Electron updated — because you now ship the browser and own its CVEs.**

---

## Part 8 — Packaging & Distribution

Here is the part that genuinely shocks every web developer, and the reason desktop development has a reputation for pain. On the web, "ship it" is `git push` and a CI deploy. On the desktop, "ship it" means: produce a native installer **for each operating system**, **cryptographically sign** it so the OS will run it without scary warnings, get Apple to **notarize** the macOS build, host the artifacts somewhere, and wire up **auto-updates** (Part 9) so users actually receive your fixes. Budget for this; it's often as much work as a feature.

### From Source to App: The Build Toolchain

You don't assemble installers by hand. Two tools dominate:

- **Electron Forge** — the official, all-in-one toolchain (scaffolding, dev server, native-module rebuilding, packaging, and publishing in one config). **Recommended default**, especially for a first app.
- **electron-builder** — the most popular community tool, extremely powerful and configurable (more target formats, finer control over signing and updates). Reach for it when Forge's defaults aren't enough.

Both turn your built main/preload/renderer bundles into platform installers. The packaging step bundles your app source into an **ASAR archive** — a single concatenated file (`app.asar`) that slightly speeds loading and provides mild tamper-resistance (it is *not* encryption or real security — anyone can extract an ASAR; never put secrets in your bundle).

### Per-Platform Targets

"Cross-platform" ends at packaging — each OS has its own formats and rules:

| OS | Installer formats | Signing requirement |
|---|---|---|
| **Windows** | NSIS (`.exe`), MSI, Squirrel, `.appx` | Authenticode code-signing cert; unsigned apps trigger SmartScreen "Unknown publisher" warnings |
| **macOS** | `.dmg`, `.pkg` | Apple Developer ID signing **+ notarization** (mandatory) + hardened runtime + entitlements |
| **Linux** | AppImage, `.deb`, `.rpm`, Snap, Flatpak | no OS-mandated signing (repos/Flatpak have their own) |

### Code Signing: The Tax You Cannot Skip

On Windows and macOS, **an unsigned app is treated as malware by the OS**, and your users will see frightening warnings (or be blocked outright). Signing is not optional for real distribution:

- **macOS** is the strictest. You need an Apple Developer account ($99/yr). You sign with a **Developer ID** certificate, enable the **hardened runtime** with the right **entitlements**, then submit the build to Apple for **notarization** (an automated malware scan via `notarytool`) and **staple** the result. Without notarization, Gatekeeper refuses to launch your app on a normal user's Mac. This pipeline is fiddly and is the #1 source of "it works on my machine but won't open on theirs."
- **Windows** needs an Authenticode certificate. A standard cert still accumulates SmartScreen warnings until your app builds "reputation"; an **EV (Extended Validation) certificate** (pricier, often on a hardware token or cloud HSM) grants instant SmartScreen trust. Signing cleanly in CI with a token-based cert is its own minor saga (cloud signing services like Azure Trusted Signing help).
- **Linux**, refreshingly for you, has **no OS-level signing mandate** — AppImage just runs, and `.deb`/`.rpm`/Flatpak rely on repository or Flatpak signing instead. Given your Linux background, Linux distribution will feel the most natural of the three.

**Opinion:** code signing is the single most painful part of Electron (and of *all* desktop distribution — it's not Electron's fault), and it's worth setting up *early*, not at release crunch. The certificates, the macOS notarization dance, and CI signing all take longer than you expect.

### Linux Distribution (Your Home Turf)

Since this is your comfort zone, the practical lay of the land:

- **AppImage** — a single self-contained executable that runs on most distros with no install step. The easiest "download and run" option; great default for direct distribution.
- **`.deb` / `.rpm`** — native packages for Debian/Ubuntu and Fedora/RHEL families, installable via `apt`/`dnf`. Best when you'll host an apt/yum repo.
- **Flatpak** and **Snap** — sandboxed, store-distributed formats (Flathub, Snap Store) with their own permission models and auto-update built in. Flatpak is the more community-favored; Snap is Canonical's. Both add a sandbox layer that can complicate filesystem access (your `app.getPath` usage must respect the sandbox's portals).

Forge/electron-builder produce all of these from one config.

### Building on CI (The Real Answer to Cross-Compilation)

You generally **cannot fully cross-compile** — macOS builds must be signed and notarized on macOS, and signing tooling is platform-specific. The professional answer is a **CI matrix** that builds each target on its native OS runner. This is exactly what the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md) is for:

```yaml
# .github/workflows/release.yml (sketch — see the GitHub Actions guide for depth)
jobs:
  build:
    strategy:
      matrix:
        os: [macos-latest, windows-latest, ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run make             # Forge: build + package the native installer
        env:                          # signing secrets injected per-OS
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_APP_SPECIFIC_PASSWORD: ${{ secrets.APPLE_PW }}
          CSC_LINK: ${{ secrets.WINDOWS_CERT }}
      - uses: actions/upload-artifact@v4
        with: { name: ${{ matrix.os }}, path: out/make/** }
```

Three native runners, three sets of signing secrets, three installer formats — assembled into a release. Store signing certificates as encrypted CI secrets (the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md)'s security section covers handling these safely).

If you remember one thing from Part 8: **shipping is the hard part of desktop dev — use Electron Forge to build per-OS installers, accept that code signing (and macOS notarization) is a mandatory, fiddly tax on Windows and macOS, lean on your Linux comfort for AppImage/deb/Flatpak, and build everything on a native-OS CI matrix.**

---

## Part 9 — Auto-Updates & Performance

Two final operational concerns that distinguish a hobby build from a shippable product: getting fixes onto users' machines after they've installed (auto-updates), and keeping a Chromium-based app from being a resource hog (performance).

### Auto-Updates: The Desktop "Deploy"

On the web, every user gets your latest code on the next page load. On the desktop, **users run whatever version they installed until something updates it** — and "something" is your job. Without auto-updates, your bug fixes and *security patches* (Part 7) never reach the people running old versions. This is not a nice-to-have; it's how you stay patched.

The standard mechanism is **`electron-updater`** (from electron-builder; more flexible than the built-in `autoUpdater`). It checks an update server, downloads new signed builds in the background, and installs on restart:

```javascript
// main process
import { autoUpdater } from "electron-updater";

app.whenReady().then(() => {
  autoUpdater.checkForUpdatesAndNotify();     // check on launch; notify when ready
});

autoUpdater.on("update-downloaded", () => {
  // Prompt the user, then: autoUpdater.quitAndInstall();
});
```

The pieces:

- **An update feed/server.** The easiest is **GitHub Releases** (electron-updater reads release artifacts directly) — publish your signed installers there and clients find them. Alternatives: an S3 bucket, a generic HTTP server, or hosted services (`update.electronjs.org` for open-source apps).
- **Signed updates.** Updates must be signed with the same identity as the installed app, or the OS/updater rejects them — this prevents an attacker from pushing a malicious "update." Your Part 8 signing setup feeds directly into this.
- **Staged rollouts and channels.** For real products: release to a small percentage first, watch for crashes, then ramp — and offer beta/stable channels. The [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md)'s canary-deploy thinking applies, except you can't roll back an update that's already installed on a laptop, so *staged* rollout matters even more.

Platform notes: macOS auto-update *requires* the app to be signed (unsigned apps can't auto-update at all); Linux auto-update works for AppImage but Flatpak/Snap update through their stores instead.

### Performance: The Honest Accounting

Electron's reputation for being heavy is *earned*, and pretending otherwise helps no one. The baseline costs:

- **Disk:** each app bundles its own Chromium + Node — roughly **100–150 MB** installed, before your code. (This is the core of the Tauri comparison, Part 10.)
- **Memory:** a baseline of **~100+ MB RAM** for one window, more per additional window/process. Several Electron apps open at once is why your laptop's RAM evaporates.

You can't eliminate these (they're the price of bundling a browser), but you can avoid making them worse, and you can keep the app *feeling* fast — which matters more to users than raw numbers.

### Don't Block the Main Process

This is the performance rule that matters most, and it's the same one from every async guide in this repo, with higher stakes. **The main process controls every window.** If you do heavy synchronous work there — parse a huge file, run a big computation, a synchronous DB migration — *every window freezes*, because the process that manages them is busy. It's the [event-loop-blocking](ADVANCED_NODEJS_STUDY_GUIDE.md) sin from the Node guide, except the blast radius is your entire UI.

Offload heavy work off the main process:

```javascript
import { utilityProcess } from "electron";

// utilityProcess: Electron's blessed way to spawn a Node child process for heavy work.
// It runs off the main process, so a long computation won't freeze any window.
const child = utilityProcess.fork(path.join(import.meta.dirname, "heavy-worker.js"));
child.postMessage({ task: "reindex", data });
child.on("message", (result) => win.webContents.send("reindex:done", result));
```

Options, in order of preference: a **`utilityProcess`** (Electron's managed child process for background work), **`worker_threads`** (from the Node guide — for CPU work in the main process's neighborhood), or offloading to the renderer's **Web Workers** for UI-side computation. The principle is identical across all of them and across this whole repo: *keep the thread that handles events free to handle events.*

### Other Performance Levers

- **Startup time:** lazy-load heavy modules (don't `import` everything at top of main), use `ready-to-show` to avoid a white flash (Part 2), and consider **V8 snapshots** for faster cold start. Show a window fast, fill it progressively.
- **Memory:** prefer one window with in-app views over many `BrowserWindow`s (each is a full process). Destroy windows/views you're done with. Watch for the usual JS leaks (the [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md) Part 7 — listeners, caches, closures) in *both* main and renderer.
- **Renderer perf is web perf** — your existing skills. Profile with Chrome DevTools' Performance panel; it's the same tooling you use for websites.
- **Measure both sides:** renderer via DevTools (built in); main via `node --inspect` semantics (`win.webContents` aside, launch with `--inspect` and attach Chrome/VS Code to the main process).

If you remember one thing from Part 9: **auto-updates are how you ship fixes and security patches to machines you don't control — wire up `electron-updater` against GitHub Releases with signed builds and staged rollouts — and the top performance rule is the familiar one: never block the main process, because it owns every window, so offload heavy work to a `utilityProcess` or worker.**

## Part 10 — Alternatives & a Build Walkthrough

You should never reach for a tool without knowing when *not* to. This closing part is the opinionated comparison — Electron versus the realistic alternatives — followed by an end-to-end walkthrough that ties the whole guide together.

### Electron vs. Tauri

**Tauri** is the alternative you should care about most, both because it's the strongest competitor and because it's built in Rust — the language you're learning. The core difference: where Electron *bundles* Chromium, Tauri uses the **operating system's built-in webview** (WebView2/Chromium on Windows, WebKitGTK on Linux, WKWebView on macOS) and a Rust backend instead of Node.js.

| | **Electron** | **Tauri** |
|---|---|---|
| Rendering engine | bundled Chromium (consistent everywhere) | OS webview (**varies by platform**) |
| Backend language | Node.js | **Rust** |
| App size | ~100–150 MB | **~3–10 MB** |
| Baseline memory | ~100+ MB | significantly lower |
| Rendering consistency | **identical on all OSes** | **differs per OS** (the cross-browser problem returns) |
| Ecosystem / maturity | **huge, battle-tested** | younger, growing fast |
| Security defaults | safe (if you don't disable them) | **stricter by default**, smaller attack surface |

**The trade is rendering consistency for footprint.** Tauri apps are dramatically smaller and lighter because they don't ship a browser — but they render on *whatever webview the OS provides*, so you're back to fighting per-engine differences (a WebKitGTK quirk on Linux that doesn't reproduce on Windows' Chromium-based WebView2). It's the exact cross-browser-compatibility problem Electron eliminates.

**Opinion:** for *your* situation — a web developer learning GUI development — **start with Electron.** Consistent rendering means you debug your app, not three webview engines, and the Node.js backend is a language you already know while you're still learning Rust. Once you're fluent in both desktop development *and* Rust, Tauri becomes very attractive for shipping — its size and memory wins are real and large, and its security model is excellent. Many teams prototype in Electron and consider Tauri once the footprint matters. (Tauri is on this repo's [TOPICS](TOPICS.md) backlog precisely because of the Rust adjacency.)

### Electron vs. Qt vs. Native vs. the Web

The rest of the landscape, briefly and honestly:

- **Qt** (the [Qt guide](QT_STUDY_GUIDE.md)) — **native widgets**, C++ or Python (PyQt/PySide). True native look and performance, tiny footprint, deep platform integration. But you write the UI in Qt's widget-and-layout model, which is a *whole new UI paradigm* for a web developer — no HTML/CSS, no DOM, no Vue. For your background, Qt is a much steeper climb than Electron, justified when you need native performance/feel or are in a C++/Python-native shop. If your *Python* skills dominate and you want lighter-weight, PySide is worth a look.
- **Native** (Swift/SwiftUI on macOS, WinUI/C# on Windows, GTK on Linux) — the best possible look, feel, and performance on each platform, and the only real choice for deep OS integration — but it's **one codebase per platform**, and none of them reuse your web skills. Right for platform-exclusive flagship apps, wrong for cross-platform with a small team.
- **Flutter Desktop / .NET MAUI** — single-codebase cross-platform with their own UI frameworks (Dart/C#). Viable, but again a new UI paradigm, and desktop is a secondary target for both.
- **Just ship a web app / PWA** — the question to always ask first. If your app doesn't *need* the filesystem, native menus, tray, offline-first local data, or OS integration, **it might not need to be a desktop app at all.** A PWA installs to the dock/taskbar, works offline, and costs you none of the packaging/signing/update pain of Parts 7–9. Don't take on desktop distribution unless the native capabilities earn it.

### When to Use Electron (the Decision)

**Reach for Electron when:** you have web skills or an existing web codebase to reuse; you need true cross-platform with *consistent* rendering; your UI is rich/custom (where web's styling power shines); and the ~150 MB / ~100 MB-RAM footprint is acceptable for your users (desktop-class machines, not embedded). The marquee apps — VS Code, Slack, Discord, Figma, Obsidian, Notion, 1Password — chose it for exactly these reasons.

**Don't reach for Electron when:** footprint is critical (resource-constrained machines, or you ship many small utilities) → **Tauri**; you need maximum native performance/feel or deep OS integration → **native or Qt**; the app is simple and could be a web app/PWA → **just ship the web app**; or you need a single tiny CLI-adjacent tool → desktop GUI may be overkill entirely.

### End-to-End Walkthrough

Tying it together — from nothing to a shippable Linux app, with the concepts from each part labeled:

```bash
# 1. Scaffold (Part 4) — Forge + Vite + TypeScript, three build targets wired up
npm init electron-app@latest notes-app -- --template=vite-typescript
cd notes-app
npm install better-sqlite3 electron-updater          # local DB (Part 6), updates (Part 9)
npx @electron/rebuild                                 # rebuild native module for Electron ABI (Part 6)
```

**2. The main process** (Part 2) creates a secure window (Part 7), sets up the database (Part 6), and registers IPC handlers (Part 3):

```javascript
// src/main.ts
import { app, BrowserWindow, ipcMain } from "electron";
import Database from "better-sqlite3";
import path from "node:path";

const db = new Database(path.join(app.getPath("userData"), "notes.db"));   // Part 6
db.exec("CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, body TEXT, ts INTEGER)");
const save = db.prepare("INSERT OR REPLACE INTO notes VALUES (?, ?, ?)");
const list = db.prepare("SELECT * FROM notes ORDER BY ts DESC");

ipcMain.handle("notes:save", (_e, note) => {                              // Part 3
  if (typeof note?.id !== "string" || typeof note?.body !== "string")     // Part 7: validate
    throw new Error("invalid note");
  save.run(note.id, note.body, Date.now());
  return { ok: true };
});
ipcMain.handle("notes:list", () => list.all());

function createWindow() {
  const win = new BrowserWindow({
    width: 1000, height: 700, show: false,
    webPreferences: {                                                      // Part 7: secure defaults
      preload: path.join(import.meta.dirname, "preload.js"),
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  });
  win.once("ready-to-show", () => win.show());                            // Part 2 / Part 9
  win.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL ?? `file://${__dirname}/index.html`);  // Part 4
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });  // Part 2
```

**3. The preload bridge** (Part 3) exposes a narrow, validated API (Part 7):

```javascript
// src/preload.ts
import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld("api", {
  saveNote: (note: { id: string; body: string }) => ipcRenderer.invoke("notes:save", note),
  listNotes: () => ipcRenderer.invoke("notes:list"),
});
```

**4. The renderer** (Part 4) — your Vue app, calling the bridge like any async API:

```javascript
// src/renderer — inside a Vue component
const notes = ref(await window.api.listNotes());
async function add(body: string) {
  await window.api.saveNote({ id: crypto.randomUUID(), body });
  notes.value = await window.api.listNotes();
}
```

**5. Package for Linux** (Part 8) — your home turf:

```bash
npm run make -- --targets=@electron-forge/maker-deb,@electron-forge/maker-appimage
# produces a .deb and an AppImage in out/make/
```

**6. Ship with updates** (Part 9): add `electron-updater` pointed at GitHub Releases, build the Windows/macOS targets on a CI matrix (Part 8) with signing secrets, and `autoUpdater.checkForUpdatesAndNotify()` on launch.

That's a complete, secure, locally-persistent, auto-updating desktop app — built almost entirely from skills you already had, plus the desktop-specific layer this guide added.

### The Closing Take

Desktop GUI development feels intimidating from the outside, but for a web and backend engineer the intimidation is misplaced. The *UI* is web (you know it), the *privileged layer* is Node (you know it), and the *boundary* between them is a client-server API (you know it). What's genuinely new is a contained, learnable set: the multi-process lifecycle, native OS integration, the heightened security model, and — the real work — packaging, signing, and shipping software to machines you don't control. Electron is the right framework to learn all of that on, precisely because it lets you spend your effort on what's new instead of relearning how to build a UI.

That's the guide. From here the highest-leverage next step is to build the walkthrough app above for real, ship the Linux AppImage to yourself, and feel the one thing no guide can convey: the difference between `git push` and watching a signed installer land on a machine you'll never see again. Once you've shipped one, the model is yours — and Tauri, Qt, and native are all just variations on the architecture you now understand.


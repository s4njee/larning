# CB8 on iOS

A practical, depth-first guide to bringing [CB8](https://github.com/s4njee/CB8) — a comic and book reader built as an Electron app with an embedded web server and a React web GUI — to iPhone and iPad. This is a case study in a problem many teams hit: you have a working Electron + web-GUI desktop app, and you want it on iOS, where Electron cannot follow. The guide walks the real decision (wrap the web UI, or go native?), then builds the recommended answer — a native SwiftUI app that speaks CB8's existing HTTP API and grows an on-device library mode — mapping every CB8 subsystem (Fastify server, better-auth sessions, SQLite index, node-7z archive handling, epub.js/pdf.js readers) to its iOS counterpart.

Assumes you can read TypeScript (CB8's language) and have basic Swift/SwiftUI exposure — the [iOS Development guide](IOS_DEVELOPMENT_STUDY_GUIDE.md) and [Swift guide](SWIFT_STUDY_GUIDE.md) in this repo cover the prerequisites. The [Electron guide](ELECTRON_STUDY_GUIDE.md) covers the desktop side of the architecture being ported. A sibling guide, [CB8 on Android](CB8_ANDROID_STUDY_GUIDE.md), ports the same codebase to Android with the same part structure — useful as a side-by-side of how the two platforms change the answers.

Primary references: the [CB8 repository](https://github.com/s4njee/CB8), Apple's [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/), [GRDB](https://github.com/groue/GRDB.swift), [ZIPFoundation](https://github.com/weichsel/ZIPFoundation), the [Readium Swift Toolkit](https://github.com/readium/swift-toolkit), and Apple's [PDFKit](https://developer.apple.com/documentation/pdfkit) and [WKWebView](https://developer.apple.com/documentation/webkit/wkwebview) documentation.

---

## Table of Contents

1. [Part 1 — Reading the CB8 Codebase: What You're Actually Porting](#part-1--reading-the-cb8-codebase-what-youre-actually-porting)
2. [Part 2 — Choosing a Porting Strategy](#part-2--choosing-a-porting-strategy)
3. [Part 3 — Project Setup and the Dependency Map](#part-3--project-setup-and-the-dependency-map)
4. [Part 4 — The Swift API Client](#part-4--the-swift-api-client)
5. [Part 5 — The Library UI](#part-5--the-library-ui)
6. [Part 6 — The Comic Reader](#part-6--the-comic-reader)
7. [Part 7 — EPUB and PDF](#part-7--epub-and-pdf)
8. [Part 8 — Going Standalone: The On-Device Library](#part-8--going-standalone-the-on-device-library)
9. [Part 9 — Archives and the Shared-Logic Ports](#part-9--archives-and-the-shared-logic-ports)
10. [Part 10 — Progress Sync and Offline](#part-10--progress-sync-and-offline)
11. [Part 11 — Testing: Porting the Vitest Suite](#part-11--testing-porting-the-vitest-suite)
12. [Part 12 — Distribution and App Review](#part-12--distribution-and-app-review)
13. [Appendix — The WKWebView / Capacitor Shortcut](#appendix--the-wkwebview--capacitor-shortcut)

---

## Part 1 — Reading the CB8 Codebase: What You're Actually Porting

Before writing a line of Swift, understand what CB8 *is* architecturally, because the architecture decides how hard the port is. CB8 is unusually well-positioned for an iOS port — and the reason why is the single most important fact in this guide.

### The three-deployment architecture

CB8 runs three ways from one codebase: as an Electron desktop app, as a Docker container, and as a plain Node.js standalone bundle. All three host the **same embedded HTTP server** (Fastify-based, in `src/main/webServer/`), which serves two things:

1. The compiled React SPA (`src/renderer/` built by Vite into `dist/web`)
2. A JSON API under `/api/*`

The Electron window is, in effect, just a privileged browser pointed at the embedded server. A LAN browser hitting `http://<host>:8008` gets the identical UI. This means CB8 already crossed the hardest bridge most Electron apps never cross: **the GUI is fully decoupled from the host process and talks to it over HTTP.** Many Electron apps wire their renderer to the main process through `ipcRenderer` calls that have no network equivalent; porting those to mobile means inventing an API first. CB8's API already exists, is already versioned by its own web client, and already handles authentication and multi-user state.

### The module map

The layout, from the repository:

```
src/main/        # "Backend": archive loading, scanning, SQLite, Fastify server, IPC
  archiveLoader.ts        # CBZ/CBR access via node-7z (spawns a 7z executable)
  fileScanner.ts          # walks folders, finds .cbz/.cbr/.epub/.pdf/.mobi
  libraryDatabase.ts      # better-sqlite3 wrapper
  db/                     # comics, tags, folders, favorites, bookmarks,
                          # progress, history, users, libraries + schema/migrations
  thumbnailGenerator.ts   # cover thumbnails (sharp / @napi-rs/canvas)
  epubCoverExtractor.ts   # covers from EPUB
  pdfCoverExtractor.ts    # covers from PDF
  seriesParser.ts         # series/volume/chapter from filenames
  webServer/              # the HTTP layer
    auth.ts               # better-auth + bcryptjs, signed session cookies
    routes/               # auth, comics, progress, tags, folders, users, ...
    mapping.ts            # DB record -> WebComicRecord (strips file paths)
src/renderer/    # React + shadcn/Tailwind SPA (zustand, react-query, react-router)
  pages/                  # Library, Reader, Browse, Continue, Recent, Tag, Folder, Auth
src/shared/      # pure logic used by both sides — the porting goldmine
  naturalSort.ts          # "page2.jpg" before "page10.jpg"
  imageFilter.ts          # which archive entries count as pages
  scaleFit.ts             # aspect-preserving fit math
  coverSelection.ts       # which entry becomes the cover
  lru.ts                  # page cache eviction
  epubTheme.ts            # EPUB theme definitions
  types.ts                # MediaRecord, QueryOptions, QueryResult, ...
```

Three observations that shape the port:

**First: `src/shared/` is pure logic with tests.** `naturalSort.ts`, `imageFilter.ts`, `scaleFit.ts`, `coverSelection.ts`, `lru.ts` have no Node or DOM dependencies and ship with vitest suites (`*.test.ts`). These don't port as *code* — you'll rewrite them in Swift — but they port as *specifications*: each file is a precise, tested statement of behavior your Swift version must match (Part 9), and each test file converts mechanically to Swift Testing (Part 11).

**Second: the backend's platform dependencies are concentrated and identifiable.** Four things in `src/main/` are categorically unavailable on iOS:

- `node-7z` **spawns a 7-Zip executable** (`7z`/`7zz`/`7za` on `PATH`, per the README). iOS apps cannot spawn processes — there is no `posix_spawn` of bundled executables for sandboxed apps, full stop. Archive extraction must become an in-process library call (Part 9).
- `better-sqlite3` is a native Node addon. iOS has SQLite built into the OS; you'll use it through GRDB (Part 8).
- `sharp` / `@napi-rs/canvas` are native addons for image work. iOS replaces them with ImageIO/Core Graphics, which are better at this job anyway (Part 8).
- Fastify itself, and Node. There is no supported Node runtime on iOS (Part 2 examines the unsupported ones).

**Third: the API is small, regular, and cookie-authenticated.** The route handlers in `src/main/webServer/routes/` match URLs with regexes against a flat path space (`/api/comics/:id/pages/:n` and friends — full table in Part 4). Auth is better-auth with bcryptjs hashing and signed session cookies (`cookiePrefix: 'cb8'`, 30-day sliding sessions). For an iOS client this is nearly ideal: `URLSession` handles cookies automatically, and there's no OAuth dance or token refresh machinery to build.

### What survives the port, and in what form

| CB8 piece | Survives as | Effort |
| --- | --- | --- |
| HTTP API (`webServer/routes/`) | Consumed as-is by a Swift client | Low — write the client |
| `src/shared/` pure logic | Swift rewrites, behavior-identical, test-verified | Low — small files |
| SQLite schema (`db/schema/create.ts`) | GRDB schema for on-device mode | Medium — subset only |
| React UI structure (pages, flows) | SwiftUI screens mirroring the same routes | Medium — rewrite |
| Reader interactions (pinch/pan/swipe) | Native gestures (better on iOS than in a webview) | Medium |
| Archive loading (`archiveLoader.ts` + node-7z) | ZIPFoundation / libarchive in-process | Medium–High (CBR is the catch) |
| epub.js / pdf.js rendering | PDFKit (native) + Readium or WKWebView+epub.js | Medium |
| Electron shell, IPC, menus, Forge packaging | Nothing — does not port | Zero (deleted, not ported) |

The Electron layer itself — `BrowserWindow`, `preload.ts`, `ipcHandlers.ts`, `menu.ts`, the Forge makers — contributes *nothing* to the iOS app. That's not a loss; it's the proof that CB8's "decoupled from Electron so the standalone bundle can reuse it" design (their words, from the project layout docs) was the right call. The port rides entirely on the parts that were already Electron-free.

---

## Part 2 — Choosing a Porting Strategy

"Electron app on iOS" has four candidate answers. Three are real options for CB8; one is a trap worth understanding so you can rule it out deliberately.

### Option 0 (the trap): run the Node backend on the device

Projects like **nodejs-mobile** embed a Node runtime in a mobile app (with JIT disabled, since iOS forbids writable-executable memory for third-party apps — only Safari/WKWebView's JavaScriptCore gets a JIT). In theory you'd run CB8's embedded server on-device and point a WKWebView at `localhost`.

In practice this fails CB8 specifically, on concrete grounds:

- **`node-7z` cannot work.** It shells out to a 7-Zip executable. iOS prohibits spawning processes. Every CBZ/CBR open in `archiveLoader.ts` dies. You'd be rewriting the archive layer anyway — in which case, why are you shipping a Node runtime?
- **Native addons** (`better-sqlite3`, `sharp`) must be cross-compiled for iOS/arm64 against a community-maintained Node fork. This is where such ports go to die: every dependency bump becomes a porting project.
- **Lifecycle mismatch.** iOS suspends apps aggressively. A long-lived server process with open SQLite handles and in-flight scans is the opposite of the iOS application model; you'd fight `beginBackgroundTask` expiration forever.
- **Review risk** for shipping an interpreter plus a wrapped website (see Option 1's guideline discussion).

Rule it out and move on.

### Option 1: wrap the existing web GUI (WKWebView / Capacitor)

CB8's React SPA already runs in any browser. A minimal iOS app is a `WKWebView` pointed at a CB8 server — either a remote one (home server, NAS, the Docker deployment) or a bundled copy of `dist/web` configured with a server URL. [Capacitor](https://capacitorjs.com/) industrializes this: it ships your web build in the app bundle, serves it from a local custom scheme, and exposes native plugins (filesystem, haptics, status bar) to JS.

**Honest assessment for CB8:**

*For:* near-zero UI work; pixel-identical to the desktop/web experience; the touch interactions already exist (the README advertises pinch/pan/swipe on touch); one UI codebase forever.

*Against:*

- **App Review guideline 4.2 (Minimum Functionality).** Apps that are "simply a web site bundled as an app" get rejected. A wrapper whose entire content lives on the user's own server is a gray zone — self-hosted client apps do ship (many Plex/Jellyfin-adjacent apps started this way), but rejection risk is real and resubmission cycles are slow.
- **It can't work without a server.** The wrapper is a *client only*. No on-device library, no offline reading without significant new web-side work (and the web filesystem APIs available inside WKWebView won't give you Files-app integration users expect).
- **Reader feel.** Web pinch-zoom inside a webview, fighting the webview's own gesture recognizers, never feels as good as a native `UIScrollView`. For an app whose entire job is reading, the reader *is* the product.
- **Per-page latency.** The SPA fetches pages over HTTP even when "local"; fine on a LAN, but it forecloses the tight native image pipeline (ImageIO downsampling, prefetch, memory-mapped decode) that makes a reader feel instant.

The wrapper is a legitimate *first milestone* — it's how you validate demand in a weekend — and the Appendix gives the recipe. It's the wrong *destination*.

### Option 2: React Native / Expo

Reuse the React *knowledge* (not the React DOM code — shadcn/Tailwind components don't transfer) with native rendering. For CB8 this lands awkwardly: the UI would be rewritten anyway (different component library, different navigation), the reader still needs native-grade gesture and image work (custom native modules or finicky `react-native-gesture-handler` tuning), and the archive/SQLite layer is native code regardless. You'd take on the RN toolchain to avoid a Swift UI layer that is, for this app, the easy part. If the team were a JS shop planning Android the same week, RN becomes defensible. For a personal project with one target platform, it's overhead.

### Option 3 (recommended): native SwiftUI, in two phases

**Phase 1 — a native client for CB8 servers.** CB8 already ships as Docker/standalone deployments whose entire purpose is multi-device access. A SwiftUI app speaking the existing `/api` (Parts 4–7) is a genuinely useful product on its own: library browsing, reading, per-user progress against your home server. No changes to the CB8 codebase required — the API as it exists today suffices.

**Phase 2 — standalone on-device mode.** Add a local library: import files via the document picker, index into GRDB using a port of CB8's schema, extract archives in-process, generate thumbnails with ImageIO (Parts 8–9). The app becomes what CB8's Electron build is on the desktop: a self-contained reader.

This ordering mirrors CB8's own architecture (server core, multiple frontends) and front-loads the highest-value, lowest-risk work. Everything from here on builds Option 3, with the Appendix covering Option 1 as the quick alternative.

```quiz
Q: Why is running CB8's Node backend on-device (nodejs-mobile) ruled out as a trap rather than a real option?
- [ ] Node is too slow on iOS
- [x] iOS forbids spawning processes (so `node-7z`'s shell-out to 7-Zip dies on every archive), native addons must be cross-compiled per dependency bump, and iOS's aggressive app suspension fights a long-lived server process
- [ ] Apple bans JavaScript entirely
- [ ] Node can't render UI
> The blockers are concrete to CB8: the archive layer shells out to a 7-Zip executable, but iOS prohibits process spawning, so you'd rewrite that layer anyway — defeating the point of shipping Node. Native addons (`better-sqlite3`, `sharp`) need fragile arm64 cross-compilation, and a server with open SQLite handles contradicts iOS's suspend-aggressively lifecycle. Rule it out deliberately.

Q: The guide recommends native SwiftUI "in two phases." What's the ordering and why?
- [ ] On-device library first, then a server client
- [x] Phase 1 is a native client for existing CB8 servers (the `/api` already suffices, no codebase changes); Phase 2 adds standalone on-device library/archive/thumbnail support — front-loading the highest-value, lowest-risk work
- [ ] Build everything at once
- [ ] Ship the web wrapper permanently
> CB8 already ships as a server whose purpose is multi-device access, so a SwiftUI app speaking the existing API is independently useful with zero backend changes — high value, low risk. The harder standalone mode (document import, GRDB indexing, in-process archive extraction, ImageIO thumbnails) comes second. This mirrors CB8's own server-core-plus-multiple-frontends architecture.

Q: The Capacitor/WKWebView wrapper is called a legitimate first milestone but the "wrong destination." What's the central reason for an app whose job is reading?
- [ ] Webviews can't display images
- [x] The reader *is* the product — webview pinch-zoom fighting the webview's own gestures never feels as good as a native UIScrollView, and per-page HTTP fetching forecloses the native image pipeline (ImageIO downsampling, prefetch) that makes reading feel instant
- [ ] Capacitor isn't allowed on the App Store
- [ ] It requires rewriting the UI anyway
> A wrapper is near-zero UI work and validates demand in a weekend, but for a reading app the reader experience dominates: native gestures and a tight image pipeline are what make it feel good, and a webview can't match them. Add App Review 4.2 (minimum-functionality) exposure and the client-only limitation (no real offline library), and it's a fine first milestone but not where you stop.
```

### Strategy decision table

| | Web wrapper / Capacitor | React Native | Native SwiftUI |
| --- | --- | --- | --- |
| UI reuse from CB8 | ~100% | ~0% (knowledge only) | 0% |
| Backend reuse | 100% (remote server) | API client rewrite | API client rewrite |
| Offline / on-device library | Effectively no | Native modules needed | First-class |
| Reader gesture quality | Webview-grade | Good with effort | Native |
| App Review risk | 4.2 exposure | Low | Low |
| New toolchains | Capacitor | RN/Metro/Expo | Xcode only |
| Time to first usable build | Days | Weeks | ~2 weeks (Phase 1) |
| Right when… | validating demand fast | JS team, Android too | the reader is the product |

---

## Part 3 — Project Setup and the Dependency Map

### Creating the project

Xcode → New Project → iOS App. SwiftUI interface, Swift Testing for the test target. Set the deployment target to iOS 17 (gets `@Observable`, `NavigationStack` maturity, and modern `ScrollView` APIs while still covering essentially every device CB8's audience owns). Enable strict concurrency (Swift 6 language mode) from day one — retrofitting it hurts.

Suggested target layout, mirroring CB8's separation of concerns:

```
CB8iOS/
  App/                  # @main, scenes, dependency container
  API/                  # Part 4 — server client (CB8's webServer, consumed)
  Library/              # Part 5 — browse UI (CB8's renderer/pages)
  Reader/               # Parts 6–7 — comic/EPUB/PDF readers
  LocalLibrary/         # Part 8 — GRDB store, scanner, importer (CB8's src/main)
  Archives/             # Part 9 — CBZ/CBR access (CB8's archiveLoader)
  Shared/               # Part 9 — naturalSort, imageFilter, scaleFit, LRU ports
CB8iOSTests/            # Part 11 — ported vitest suites
```

The `Shared/` name is deliberate: it's the same role as CB8's `src/shared/`, and keeping the file names parallel (`NaturalSort.swift` ↔ `naturalSort.ts`) makes diffing behavior against upstream trivial when CB8 changes.

### The dependency map

Every meaningful dependency in CB8's `package.json`, and what plays its role on iOS:

| CB8 dependency | Role in CB8 | iOS replacement | Notes |
| --- | --- | --- | --- |
| `electron` + Forge makers | Shell, packaging | — (Xcode, App Store) | Does not port; nothing to do |
| `fastify`, `@fastify/static`, `@fastify/cookie`, `@fastify/cors` | Embedded HTTP server | — (Phase 1: consumed remotely; Phase 2: no server needed) | The iOS app has no reason to host HTTP |
| `better-auth`, `bcryptjs` | Sessions, password hashing | `URLSession` + `HTTPCookieStorage`; Keychain for credentials | Client side only — hashing stays on the server |
| `better-sqlite3` | Library index | [GRDB.swift](https://github.com/groue/GRDB.swift) | Same SQLite underneath; GRDB adds Codable rows, migrations, observation |
| `node-7z` (+ 7-Zip binary), `yauzl` | CBZ/CBR extraction | [ZIPFoundation](https://github.com/weichsel/ZIPFoundation) for CBZ; libarchive or UnrarKit for CBR | The big rewrite; Part 9 |
| `sharp`, `@napi-rs/canvas`, `@jsquash/jxl` | Thumbnails, resizing, JXL decode | ImageIO (`CGImageSource` downsampling) | JPEG XL decodes natively on iOS 17+ |
| `pdfjs-dist` | PDF rendering + covers | **PDFKit** (system framework) | A straight upgrade — native, fast, zero dependency |
| `epubjs` | EPUB rendering | [Readium Swift Toolkit](https://github.com/readium/swift-toolkit), or WKWebView reusing epub.js | Part 7 weighs the choice |
| `react`, `react-router-dom` | UI, navigation | SwiftUI, `NavigationStack` | Pages map 1:1 to screens |
| `zustand` | Client state | `@Observable` models | Same role: plain observable state objects |
| `@tanstack/react-query` | Server cache, pagination | Async/await + small cache layer | Part 5 builds the equivalent |
| `tailwind`/shadcn/`radix` | Components | SwiftUI built-ins | — |
| `sonner` (toasts), `lucide-react` (icons) | Chrome | SwiftUI alerts/overlays, SF Symbols | — |
| `vitest`, `fast-check` | Tests | Swift Testing (parameterized tests cover the fast-check cases pragmatically) | Part 11 |

Add the Swift packages (File → Add Package Dependencies): `GRDB.swift`, `ZIPFoundation`, and — when you reach Part 7 — `readium/swift-toolkit`. Phase 1 needs none of them; the API client below is pure Foundation.

---

## Part 4 — The Swift API Client

Phase 1 is a client for CB8's existing server. The contract is defined by `src/main/webServer/routes/` and `mapping.ts`, and it's worth transcribing precisely, because this is the actual API as implemented (not a hypothetical REST design).

### The endpoint table

Compiled from the route handlers' regex matches:

| Method + Path | Purpose | Notes |
| --- | --- | --- |
| `POST /api/auth/login` | Sign in | Body `{username?, password}`; username defaults to `admin`. Sets signed session cookie |
| `POST /api/auth/logout` | Sign out | Clears session |
| `GET /api/auth/session` | Who am I | Returns `{user, host, guestAccess}` |
| `POST /api/auth/register` | Create user | Admin only |
| `GET /api/comics` | Query library | `search`, `tag`, `sortBy`, `sortOrder`, `offset`, `limit` (default 50), `mediaType`, `fileExt`, `readStatus`, `favorites` |
| `GET /api/comics/:id` | One record | Per-user progress overlaid |
| `DELETE /api/comics/:id` | Remove from library | DB row only; server file untouched |
| `GET /api/comics/:id/thumbnail?v=` | Cover JPEG | `v` is a cache-buster derived from `dateAdded` |
| `GET /api/comics/:id/pages/:n` | Page image | 0-indexed. `?width=` triggers **server-side resize** with day-long `Cache-Control` |
| `GET /api/comics/:id/file` | Whole file stream | For EPUB/PDF/MOBI client-side rendering — and offline downloads |
| `PUT /api/comics/:id/progress` | Save position | Body `{page?, location?, completed?}`; server auto-completes on last page |
| `DELETE /api/comics/:id/progress` | Clear position | |
| `POST/DELETE /api/comics/:id/favorite` | Toggle favorite | |
| `GET/POST /api/comics/:id/bookmarks`, `PUT/DELETE …/bookmarks/:bid` | Bookmarks | |
| `GET/POST /api/history` | Reading history | Paginated with `offset`/`limit` |
| `GET /api/series`, `GET /api/series/:name/comics` | Series grouping | From `seriesParser.ts` filename parsing |
| `GET /api/recently-read`, `GET /api/continue-reading` | Shelves | `limit`, `mediaType`; per-user when signed in |
| `GET /api/tags`, `/api/folders`, `/api/libraries` | Organization | Virtual folders — no disk layout implied |
| `/api/admin/*`, `/api/settings/*` | Server admin | Scan paths, uploads, guest access, rescan interval |

Two server behaviors matter to client design. **`?width=` resizing**: the server caches resized pages and serves them with `Cache-Control: public, max-age=86400`, so requesting pages at device-pixel width is both a bandwidth and a server-cache win — pass `Int(viewWidth * displayScale)`. **Progress auto-completion**: `PUT progress` with `page >= pageCount - 1` marks the item completed server-side unless the client says otherwise — so the iOS client should *not* duplicate that rule, or completion semantics will drift between clients.

```quiz
Q: Why should the iOS client *not* re-implement CB8's "mark completed on the last page" rule locally?
- [ ] The client can't compute the last page
- [x] The server already auto-completes when `PUT progress` has `page >= pageCount - 1`; duplicating the rule client-side risks the two implementations drifting, so completion semantics stay consistent only if one place owns them
- [ ] Completion is purely cosmetic
- [ ] It would violate App Review
> When two clients each encode the same business rule independently, they inevitably diverge as edge cases (off-by-one page counts, spreads, partial reads) are handled differently. The server owns auto-completion, so the iOS app just reports its position and lets the server decide completion — keeping the web, desktop, and iOS clients in agreement. Re-deriving the rule is how cross-client state quietly drifts.

Q: The guide stresses transcribing "the actual API as implemented (not a hypothetical REST design)." Why does that distinction matter for a port?
- [ ] Hypothetical APIs are faster
- [x] The client must match the server's real behavior — quirks like 0-indexed pages, `?width=` server-side resize with day-long caching, relative thumbnail URLs with cache-buster `v`, and username defaulting to `admin` — not an idealized contract that the server doesn't actually honor
- [ ] REST design is always wrong
- [ ] The server has no documentation
> A port consumes the endpoints as they exist, so the source of truth is the route handlers and `mapping.ts`, not a cleaned-up REST sketch. Getting the real quirks right (page indexing, resize/caching semantics, cookie auth, the deliberately-path-free `WebComicRecord` wire shape) is what makes the native client interoperate with the existing web UI rather than subtly disagreeing with it.
```

### Models

`mapping.ts` defines the wire shape — `WebComicRecord` deliberately omits server file paths. The Swift mirror:

```swift
enum MediaType: String, Codable, Sendable {
    case comic, book
}

/// Mirrors WebComicRecord in src/main/webServer/mapping.ts.
struct ComicRecord: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let title: String
    let pageCount: Int
    let fileSize: Int64
    let dateAdded: String
    let tags: [String]
    let lastPage: Int?
    let lastLocation: String?     // EPUB CFI / PDF position for books
    let lastRead: String?
    let mediaType: MediaType
    let thumbnailUrl: String      // relative: /api/comics/7/thumbnail?v=...
    let fileExt: String           // "cbz" | "cbr" | "epub" | "pdf" | "mobi"
    let favorited: Bool?
}

/// Mirrors QueryResult in src/shared/types.ts.
struct ComicQueryResult: Codable, Sendable {
    let records: [ComicRecord]
    let totalCount: Int
}

/// Mirrors QueryOptions in src/shared/types.ts, as URL query items.
struct LibraryQuery: Sendable {
    enum SortBy: String { case title, dateAdded, fileSize, pageCount, lastRead }
    enum ReadStatus: String { case unread, inProgress = "in-progress", completed }

    var search: String?
    var tag: String?
    var sortBy: SortBy = .dateAdded
    var sortOrder: String = "desc"
    var offset = 0
    var limit = 50                // matches the server default
    var mediaType: MediaType?
    var fileExt: String?
    var readStatus: ReadStatus?
    var favorites = false

    var queryItems: [URLQueryItem] {
        var items = [
            URLQueryItem(name: "sortBy", value: sortBy.rawValue),
            URLQueryItem(name: "sortOrder", value: sortOrder),
            URLQueryItem(name: "offset", value: String(offset)),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        if let search, !search.isEmpty { items.append(.init(name: "search", value: search)) }
        if let tag { items.append(.init(name: "tag", value: tag)) }
        if let mediaType { items.append(.init(name: "mediaType", value: mediaType.rawValue)) }
        if let fileExt { items.append(.init(name: "fileExt", value: fileExt)) }
        if let readStatus { items.append(.init(name: "readStatus", value: readStatus.rawValue)) }
        if favorites { items.append(.init(name: "favorites", value: "true")) }
        return items
    }
}
```

### Sessions without ceremony

CB8 uses better-auth's signed session cookies (prefix `cb8`, 30-day sliding expiry, refreshed daily). The login route returns `Set-Cookie` headers and a JSON body. The pleasant consequence: **`URLSession` already implements the entire auth protocol.** Its default configuration stores cookies in `HTTPCookieStorage` and replays them per host. You never parse, store, or attach a token.

```swift
actor CB8Client {
    let baseURL: URL                  // e.g. http://192.168.1.20:8008
    private let session: URLSession

    init(baseURL: URL) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.httpCookieAcceptPolicy = .always   // server is self-hosted; cookie is first-party
        config.httpShouldSetCookies = true
        self.session = URLSession(configuration: config)
    }

    struct SessionUser: Codable, Sendable {
        let id: Int
        let username: String
        let isAdmin: Bool
    }

    struct LoginResponse: Codable, Sendable {
        let ok: Bool
        let user: SessionUser
    }

    func login(username: String, password: String) async throws -> SessionUser {
        var request = URLRequest(url: baseURL.appending(path: "/api/auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            ["username": username, "password": password])
        let (data, response) = try await session.data(for: request)
        try Self.checkStatus(response, data: data)
        // Set-Cookie was captured by HTTPCookieStorage; nothing to do.
        return try JSONDecoder().decode(LoginResponse.self, from: data).user
    }

    func comics(_ query: LibraryQuery) async throws -> ComicQueryResult {
        var components = URLComponents(
            url: baseURL.appending(path: "/api/comics"),
            resolvingAgainstBaseURL: false)!
        components.queryItems = query.queryItems
        let (data, response) = try await session.data(from: components.url!)
        try Self.checkStatus(response, data: data)
        return try JSONDecoder().decode(ComicQueryResult.self, from: data)
    }

    /// Page image URL — width in *pixels* so the server's resize cache
    /// (Cache-Control: max-age=86400) serves device-sized images.
    func pageURL(comic: Int, page: Int, width: Int? = nil) -> URL {
        var url = baseURL.appending(path: "/api/comics/\(comic)/pages/\(page)")
        if let width {
            url.append(queryItems: [URLQueryItem(name: "width", value: String(width))])
        }
        return url
    }

    func saveProgress(comic: Int, page: Int? = nil,
                      location: String? = nil) async throws {
        var request = URLRequest(
            url: baseURL.appending(path: "/api/comics/\(comic)/progress"))
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: AnyEncodable] = [:]
        if let page { body["page"] = AnyEncodable(page) }
        if let location { body["location"] = AnyEncodable(location) }
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try Self.checkStatus(response, data: data)
        // Deliberately no completed flag: the server auto-completes on the
        // final page (routes/progress.ts) — don't duplicate that rule here.
    }

    private static func checkStatus(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw CB8Error.transport }
        switch http.statusCode {
        case 200...299: return
        case 401: throw CB8Error.unauthorized
        default:
            let message = (try? JSONDecoder().decode([String: String].self, from: data))?["error"]
            throw CB8Error.server(status: http.statusCode, message: message)
        }
    }
}

enum CB8Error: Error {
    case transport
    case unauthorized
    case server(status: Int, message: String?)
}
```

(`AnyEncodable` is the usual ten-line type-erasing wrapper; or define three small concrete body structs if you prefer.)

Implementation notes, hard-won:

- **`unauthorized` is a state, not an error.** The session cookie outlives app launches (`HTTPCookieStorage` persists) but not the server's 30-day window. Catch `CB8Error.unauthorized` centrally and route to the login screen rather than surfacing an alert from whatever screen happened to fire the request. `GET /api/auth/session` on launch is the cheap way to decide which screen to show.
- **Store credentials in the Keychain, not the cookie.** The cookie is the session; the Keychain entry (`kSecClassInternetPassword`, keyed by server URL) is what lets you re-login silently when the session lapses. Never UserDefaults.
- **HTTP on the LAN needs an ATS exception.** Self-hosted CB8 is typically plain `http://` on a LAN. App Transport Security blocks that by default. `NSAllowsLocalNetworking` covers RFC1918-style local hosts; for a user-entered remote URL over HTTP you'd need broader exceptions and a justification at review time — or nudge users toward HTTPS reverse proxies, which their Docker deployment docs already accommodate.
- **Multiple servers are cheap.** `CB8Client` is an actor per `baseURL`; a "server list" feature is an array of saved URLs + Keychain entries. Worth designing in from the start — NAS-app users expect it.

---

## Part 5 — The Library UI

CB8's renderer pages (`AllPage`, `ContinuePage`, `RecentPage`, `TagPage`, `FolderPages`, `BrowsePages`, `LibraryPage`, `ReaderPage`, `AuthPages`) translate directly to a `TabView` + `NavigationStack` structure: a Library tab (grid + search + filters), a Home tab (continue-reading and recently-read shelves), an Organize tab (tags/folders/series), and Settings.

### Replacing react-query: the library view model

CB8's renderer leans on `@tanstack/react-query` for caching, pagination, and request dedup, with `zustand` for client state. On iOS the same division of labor is an `@Observable` model owning query state and an async pagination loop:

```swift
@Observable @MainActor
final class LibraryModel {
    private let client: CB8Client

    var query = LibraryQuery() {
        didSet { Task { await reload() } }
    }
    private(set) var records: [ComicRecord] = []
    private(set) var totalCount = 0
    private(set) var isLoading = false
    var error: CB8Error?

    init(client: CB8Client) { self.client = client }

    func reload() async {
        query.offset = 0
        records = []
        await loadNextPage()
    }

    /// Server pages by offset/limit with limit defaulting to 50 — same
    /// values the web UI uses, so server-side query plans stay warm.
    func loadNextPage() async {
        guard !isLoading, records.count < totalCount || records.isEmpty else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            query.offset = records.count
            let result = try await client.comics(query)
            records.append(contentsOf: result.records)
            totalCount = result.totalCount
        } catch let e as CB8Error {
            error = e
        } catch {
            self.error = .transport
        }
    }
}
```

The grid itself:

```swift
struct LibraryGridView: View {
    @Environment(LibraryModel.self) private var model
    let client: CB8Client

    private let columns = [GridItem(.adaptive(minimum: 110), spacing: 12)]

    var body: some View {
        @Bindable var model = model
        ScrollView {
            LazyVGrid(columns: columns, spacing: 16) {
                ForEach(model.records) { comic in
                    NavigationLink(value: comic) {
                        CoverCell(comic: comic, client: client)
                    }
                    .task {
                        // Infinite scroll: trailing edge triggers next page
                        if comic.id == model.records.suffix(8).first?.id {
                            await model.loadNextPage()
                        }
                    }
                }
            }
            .padding(.horizontal)
        }
        .searchable(text: $model.query.search.orEmpty)
        .navigationDestination(for: ComicRecord.self) { comic in
            ReaderScreen(comic: comic, client: client)
        }
    }
}
```

### Thumbnails and the cache-buster

CB8 versions thumbnail URLs (`?v=<dateAdded ms>`) precisely so HTTP caches can hold covers aggressively without going stale across re-scans — `mapping.ts` documents the bug this prevents (a wiped-and-rescanned library serving the previous comic's cover from browser cache). Honor the same contract: cache by **full URL including `v`**, and let cached entries live long.

`AsyncImage` works for a first pass but re-fetches too eagerly and offers no disk layer. A small `URLCache`-backed loader matches the server's design intent:

```swift
struct CoverCell: View {
    let comic: ComicRecord
    let client: CB8Client

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            CachedImage(url: client.baseURL.appending(path: comic.thumbnailUrl))
                .aspectRatio(2/3, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(alignment: .bottomLeading) {
                    if let last = comic.lastPage, comic.pageCount > 0 {
                        ProgressView(value: Double(last + 1) / Double(comic.pageCount))
                            .tint(.accentColor)
                    }
                }
            Text(comic.title)
                .font(.caption)
                .lineLimit(2)
        }
    }
}
```

where `CachedImage` resolves through a shared `URLSession` whose `URLCache` has a generous disk capacity (`URLCache(memoryCapacity: 64 << 20, diskCapacity: 512 << 20)`); the `v` parameter does the invalidation work for you. The thumbnail endpoint already serves small JPEGs (CB8 generates and caches covers server-side via `thumbnailGenerator.ts`), so no client-side resizing is needed for grid cells.

### Shelves and filters

`GET /api/continue-reading` and `/api/recently-read` are purpose-built for the home tab — they return user-scoped shelves when signed in. The filter sheet maps 1:1 onto `LibraryQuery`: read status (unread / in-progress / completed), file extension, tag, sort — the same `FilterPreset` shape `src/shared/types.ts` defines for the web UI's saved filters. Persist presets in `UserDefaults` as `Codable`; they're small and device-local, same as the web client treats them.

---

## Part 6 — The Comic Reader

The reader is where native pays for itself. CB8's web reader (`src/renderer/components/reader/`, `ReaderPage.tsx`) implements page-by-page reading with pinch/pan/swipe on touch; your job is the same interaction model with native gesture handling and a real image pipeline.

### Interaction model

From CB8's reader (and `docs/READER.md`): one page (or spread) at a time; swipe to turn; pinch to zoom with pan; tap zones / keyboard for navigation; progress written as you read. The iOS shape:

- A horizontally paging container — `TabView(selection:)` with `.tabViewStyle(.page(indexDisplayMode: .never))` is the quickest correct start; a `UICollectionView`/`UIPageViewController` wrapper is the upgrade path if you need tighter prefetch control.
- Each page wrapped in a zoomable scroll view. SwiftUI still has no first-class pinch-zoom scroll container, so wrap `UIScrollView` — this is the standard, boring, correct answer:

```swift
struct ZoomableImage: UIViewRepresentable {
    let image: UIImage

    func makeUIView(context: Context) -> UIScrollView {
        let scroll = UIScrollView()
        scroll.maximumZoomScale = 4
        scroll.minimumZoomScale = 1
        scroll.bouncesZoom = true
        scroll.showsVerticalScrollIndicator = false
        scroll.showsHorizontalScrollIndicator = false
        scroll.delegate = context.coordinator

        let imageView = UIImageView(image: image)
        imageView.contentMode = .scaleAspectFit
        imageView.frame = scroll.bounds
        imageView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        scroll.addSubview(imageView)
        context.coordinator.imageView = imageView

        let doubleTap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleDoubleTap(_:)))
        doubleTap.numberOfTapsRequired = 2
        scroll.addGestureRecognizer(doubleTap)
        return scroll
    }

    func updateUIView(_ scroll: UIScrollView, context: Context) {
        context.coordinator.imageView?.image = image
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, UIScrollViewDelegate {
        var imageView: UIImageView?

        func viewForZooming(in scrollView: UIScrollView) -> UIView? { imageView }

        @objc func handleDoubleTap(_ gesture: UITapGestureRecognizer) {
            guard let scroll = gesture.view as? UIScrollView else { return }
            if scroll.zoomScale > scroll.minimumZoomScale {
                scroll.setZoomScale(scroll.minimumZoomScale, animated: true)
            } else {
                let point = gesture.location(in: imageView)
                let size = CGSize(width: scroll.bounds.width / 2.5,
                                  height: scroll.bounds.height / 2.5)
                scroll.zoom(to: CGRect(origin: CGPoint(x: point.x - size.width/2,
                                                       y: point.y - size.height/2),
                                       size: size), animated: true)
            }
        }
    }
}
```

One subtlety the web reader never had to solve: when a page is zoomed in, horizontal pan must scroll the zoomed image, and only flip pages at the edge. `UIScrollView` inside a paging container resolves this naturally (the inner scroll view wins while it has scrollable content), which is exactly why the wrapper beats reimplementing zoom with SwiftUI `MagnifyGesture` math.

Add manga support early: a right-to-left mode is just reversing the page order fed to the pager (and flipping the tap zones). CB8 tracks page indexes, not directions, so RTL is purely a client presentation concern — index `n` is index `n` either way, and progress stays compatible with the web UI.

### The page pipeline

In Phase 1, pages come from `GET /api/comics/:id/pages/:n`. The server natural-sorts archive entries (`naturalSort.ts`) and filters non-images (`imageFilter.ts`), so **page index `n` here equals page index `n` in the web UI** — progress is interoperable by construction.

A reader lives or dies on prefetch. The model: keep a window of decoded pages around the current index, fetch ahead in the reading direction, and evict behind:

```swift
@Observable @MainActor
final class ComicReaderModel {
    let comic: ComicRecord
    private let client: CB8Client
    private let pixelWidth: Int          // viewport width * displayScale
    private var pages: [Int: UIImage] = [:]   // decoded page cache
    private var inflight: [Int: Task<UIImage, Error>] = [:]
    private let window = 3               // prefetch radius

    var currentPage: Int {
        didSet { Task { await turned(to: currentPage) } }
    }

    init(comic: ComicRecord, client: CB8Client, pixelWidth: Int) {
        self.comic = comic
        self.client = client
        self.pixelWidth = pixelWidth
        // Resume where any client (including the web UI) left off.
        self.currentPage = comic.lastPage ?? 0
    }

    func image(for index: Int) async throws -> UIImage {
        if let cached = pages[index] { return cached }
        if let task = inflight[index] { return try await task.value }
        let task = Task { [client, pixelWidth, comic] in
            let url = await client.pageURL(comic: comic.id, page: index,
                                           width: pixelWidth)
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else {
                throw CB8Error.transport
            }
            return image
        }
        inflight[index] = task
        defer { inflight[index] = nil }
        let image = try await task.value
        pages[index] = image
        return image
    }

    private func turned(to index: Int) async {
        // Prefetch the window ahead; drop pages outside it (LRU in spirit —
        // CB8's shared/lru.ts plays this role for the web reader).
        for offset in 1...window {
            let ahead = index + offset
            guard ahead < comic.pageCount else { break }
            Task { try? await image(for: ahead) }
        }
        pages = pages.filter { abs($0.key - index) <= window + 1 }

        // Persist progress — fire-and-forget, the same PUT the web UI sends.
        try? await client.saveProgress(comic: comic.id, page: index)
    }
}
```

Three deliberate choices to note:

- **`?width=` at device-pixel size.** A 13"-iPad-resolution scan can be a 4000-pixel-wide PNG; decoding those wholesale is how reader apps blow their memory budget and get jetsam-killed. Asking the server for `viewportWidth × scale` pixels offloads the downsample, and the server caches the result for a day for every client at that width. When zoomed past ~2×, request the full-resolution URL for the current page only.
- **Progress writes on every turn, unthrottled.** That's what the web client does, the payload is tiny, and it makes "put the phone down, continue on the desktop" seamless. If you must coalesce (cellular politeness), debounce to ~2s but always flush on `scenePhase` going `.background` — an unflushed final page is a user-visible bug across devices.
- **Decode off the main thread.** `UIImage(data:)` defers decode to first render by default, which stutters page turns. Force pre-decode in the fetch task with `image.preparingForDisplay()` (`byPreparingForDisplay()` async variant) so the pager only ever touches ready-to-blit images.

### Reader chrome

Tap center toggles chrome (title bar, page slider, settings); tap left/right edges page backward/forward — same zones as CB8's touch UI. Build the slider on `comic.pageCount` and bind it to `currentPage`; add `.persistentSystemOverlays(.hidden)` and `.statusBarHidden` for immersion, and support hardware keyboards (arrow keys / space) with `.onKeyPress` — CB8's desktop reader has keyboard nav, and iPad users with keyboards expect parity.

```quiz
Q: Why wrap a `UIScrollView` for per-page zoom instead of hand-rolling pinch-zoom with SwiftUI's `MagnifyGesture`?
- [ ] SwiftUI can't display images
- [x] SwiftUI has no first-class pinch-zoom scroll container, and a `UIScrollView` nested in the pager naturally resolves the zoomed-pan-vs-page-flip conflict (the inner scroll wins while it has scrollable content) — gesture math you'd otherwise re-derive
- [ ] MagnifyGesture is deprecated
- [ ] UIScrollView renders faster
> The genuinely hard part is gesture arbitration: when zoomed, horizontal drags must pan the image and only flip pages at the edge. A `UIScrollView` inside a `TabView`/`UIPageViewController` pager handles that for free — the inner scroll consumes the drag while it has room, the pager takes over at the boundary. Reimplementing it with `MagnifyGesture` re-solves a problem UIKit already solved, which is why the wrapper is the standard, boring, correct answer.

Q: Why does the reader request pages at `?width=viewportWidth × scale` rather than full resolution?
- [ ] To reduce server disk usage
- [x] A high-res scan can be a 4000px-wide image; decoding those wholesale blows the memory budget and gets the app jetsam-killed — asking the server for device-pixel width offloads the downsample (cached per width), with full-res requested only when zoomed past ~2×
- [ ] Smaller images are required by App Review
- [ ] The server can't serve full resolution
> Reader apps die on memory: decoding a 4000px PNG per page exhausts the budget fast. Requesting `viewportWidth × displayScale` pixels makes the server downsample (and cache the result for every client at that width), so the client only decodes what it can display. Only when the user zooms past roughly 2× do you fetch the full-resolution URL for the current page. This downsample-at-the-source discipline is core to a native image pipeline.

Q: Why force pre-decode with `image.preparingForDisplay()` in the fetch task instead of letting `UIImage(data:)` decode lazily?
- [ ] To compress the image further
- [x] `UIImage(data:)` defers decode to first render by default, which stutters the page turn at exactly the wrong moment — pre-decoding off the main thread means the pager only ever blits ready images
- [ ] It's required for caching
- [ ] preparingForDisplay rotates the image
> Lazy decode-on-render moves the expensive decode onto the main thread the instant a page becomes visible, causing a visible hitch during the turn. Forcing the decode in the background fetch task (via the async `byPreparingForDisplay()`) means by the time the pager shows the page it's already a ready-to-blit bitmap, keeping turns smooth. Decode-off-the-main-thread is one of the three deliberate reader-pipeline choices.
```

---

## Part 7 — EPUB and PDF

CB8 treats books differently from comics: the server streams the whole file (`GET /api/comics/:id/file`) and the *client* renders it — `epubjs` for EPUB, `pdfjs-dist` for PDF in the web renderer. Progress for books is a string `location` (`lastLocation`), not a page index: an EPUB CFI or a position token, saved through the same progress endpoint.

That architecture transfers directly: the iOS app downloads the file (cache it — Part 10 makes this the offline story too) and renders natively.

### PDF: a free upgrade

`pdfjs-dist` exists because browsers lack a PDF API. iOS doesn't: **PDFKit** is a system framework with rendering, thumbnails, search, and text selection built in.

```swift
struct PDFReader: UIViewRepresentable {
    let document: PDFDocument
    let record: ComicRecord
    let onLocationChange: (String) -> Void

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.document = document
        view.autoScales = true
        view.displayMode = .singlePage
        view.displayDirection = .horizontal
        view.usePageViewController(true)   // page-curl style turns

        if let location = record.lastLocation,
           let pageIndex = Int(location),
           let page = document.page(at: pageIndex) {
            view.go(to: page)
        }

        NotificationCenter.default.addObserver(
            forName: .PDFViewPageChanged, object: view, queue: .main
        ) { [weak view] _ in
            guard let view, let page = view.currentPage,
                  let index = view.document?.index(for: page) else { return }
            onLocationChange(String(index))
        }
        return view
    }

    func updateUIView(_ view: PDFView, context: Context) {}
}
```

Store the page index as the `location` string. One compatibility note: agree with yourself on what the web client writes there (pdf.js page numbers are 1-based; `PDFDocument.index(for:)` is 0-based) and normalize in one place, or cross-device resume will be off by one — the classic symptom of exactly this bug.

### EPUB: two honest options

**Option A — Readium Swift Toolkit (recommended).** The open-source standard for native EPUB on iOS: parsing, pagination, themes, font scaling, CFI-style locators. Its `Locator` type serializes to JSON — store that serialization in `location` via the same `PUT progress`. Mapping CB8's EPUB features: theme toggle → Readium theme settings (port the palette constants from `src/shared/epubTheme.ts` so dark/sepia match the web exactly); adjustable font size → Readium font settings; Google Fonts → bundle the fonts you care about instead (runtime font fetching is a webview trick; licensed font files in the bundle are the native equivalent).

The trade-off is honest: Readium is a substantial dependency with its own architecture (publication server, navigator view controllers), and its locator format won't match epub.js CFIs — **cross-client EPUB resume needs a translation**, or accept that book positions are per-client while comic positions stay shared. Comics are CB8's center of gravity (it began as a manga reader), so shipping with per-client book resume is a defensible cut.

**Option B — WKWebView + epub.js.** Reuse CB8's exact rendering: a local HTML page bundling `epub.js`, loading the book over the `/file` endpoint or from a local copy, with a `WKScriptMessageHandler` bridge reporting CFI changes to Swift, which forwards them to `saveProgress(location:)`. You inherit the web reader's behavior — including byte-identical CFIs, so resume interoperates with the web UI perfectly. You also inherit webview text rendering, webview memory behavior, and a JS bridge to maintain. Pick B if cross-device EPUB resume is non-negotiable; pick A if native reading feel wins. (B is also a useful stepping stone: ship it first, swap in Readium later behind the same `location` contract — with the CFI translation as the migration cost.)

### MOBI

CB8 lists `.mobi` support; no maintained native Swift MOBI renderer exists. The pragmatic iOS answer: treat MOBI as download-only in v1 (open via the share sheet into Books or another handler), and if it matters later, convert server-side — adding an EPUB conversion path to the server's ingest pipeline would benefit the web client too, since `epubjs` doesn't render MOBI either (CB8 handles it with a separate path). Don't burn Phase 1 time here.

---

## Part 8 — Going Standalone: The On-Device Library

Phase 2 makes the app whole: a library that lives on the device, no server required — the role CB8's Electron build plays on the desktop. This part ports `src/main/`'s storage and scanning; Part 9 ports archive access.

### Getting files in: the iOS reality

CB8's desktop scanner (`fileScanner.ts`) walks arbitrary folders. iOS has no arbitrary folders — the sandbox changes the shape of "scanning":

- **The app's Documents directory** is yours. Set `UIFileSharingEnabled` and `LSSupportsOpeningDocumentsInPlace` in Info.plist and it appears in the Files app ("On My iPhone/iPad → CB8"), so users can drop a folder of CBZs in via Files, USB, or AirDrop.
- **`UIDocumentPickerViewController`** (`.fileImporter` in SwiftUI) imports files or grants access to external folders — including folders on iCloud Drive, on a USB drive, or *on an SMB share*, which for the NAS-owning CB8 audience is a killer feature: the same share the Docker server scans can be browsed by the phone.
- **Security-scoped bookmarks** are how folder access persists across launches. This is the iOS analog of CB8 persisting scan paths in its database.

```swift
struct ImportedFolder: Codable {
    let bookmark: Data
    let displayName: String
}

func persistFolderAccess(_ url: URL) throws -> ImportedFolder {
    // Must be called while access is granted (inside the picker callback).
    let bookmark = try url.bookmarkData(
        options: .minimalBookmark,
        includingResourceValuesForKeys: nil,
        relativeTo: nil)
    return ImportedFolder(bookmark: bookmark, displayName: url.lastPathComponent)
}

func withFolderAccess<T>(_ folder: ImportedFolder,
                         _ body: (URL) throws -> T) throws -> T {
    var stale = false
    let url = try URL(resolvingBookmarkData: folder.bookmark,
                      bookmarkDataIsStale: &stale)
    guard url.startAccessingSecurityScopedResource() else {
        throw LibraryError.accessDenied(folder.displayName)
    }
    defer { url.stopAccessingSecurityScopedResource() }
    return try body(url)
}
```

Decide the import policy per source: files added to Documents are *owned* (index in place); external folders are *referenced* (index via bookmark, like CB8 referencing files on disk without moving them — its README is emphatic that removal only deletes the DB row, never the file; keep that promise).

```quiz
Q: CB8's desktop scanner walks arbitrary folders, but iOS has no arbitrary filesystem. How does "scanning" change shape on iOS?
- [ ] You can't read any files on iOS
- [x] You work within the sandbox: the app's Documents directory (exposed via Files with the right Info.plist keys), `UIDocumentPickerViewController` to import or grant access to external folders (iCloud, USB, SMB), and security-scoped bookmarks to persist that access across launches
- [ ] iOS requires uploading files to a server first
- [ ] Only photos are accessible
> The sandbox replaces "walk any path" with explicit, user-granted access. Files dropped into the app's Documents (with `UIFileSharingEnabled`/`LSSupportsOpeningDocumentsInPlace`) are directly readable; the document picker grants access to outside folders — including an SMB share, a killer feature for the NAS-owning audience whose Docker server scans the same share. Security-scoped bookmarks are the persistence mechanism, the iOS analog of CB8 storing scan paths in its DB.

Q: Why does the on-device GRDB schema drop the `users`/`session`/`account`/`verification` tables from CB8's server schema?
- [ ] GRDB doesn't support those table types
- [x] Those are better-auth's multi-user web tables — meaningless on a single-user device — so per-user progress collapses into the comic row itself, which CB8 already maintains for the desktop case
- [ ] To save disk space
- [ ] iOS forbids storing user accounts
> The server schema carries auth and multi-user machinery because it serves many users over the web; a personal on-device library has exactly one user, so the auth complex is dead weight. Progress that the server keys per-user folds back into the comic record directly — and conveniently CB8's desktop/Electron case already works this way, so the simplification mirrors existing code rather than inventing something new.

Q: When the user removes a *referenced* external comic from the on-device library, what should happen to the file?
- [ ] Delete the file from the external folder
- [x] Only delete the database row, never the file — CB8's README is emphatic that referenced files are indexed in place and removal touches only the index; keeping that promise matters for trust
- [ ] Move the file into Documents first
- [ ] Ask the server to delete it
> Owned files (copied into Documents) versus referenced files (accessed via security-scoped bookmark) have different removal semantics, and for referenced files the rule is index-only: the app never owns or destroys data sitting in the user's iCloud/USB/SMB folder. Deleting just the DB row mirrors CB8's documented desktop behavior and preserves user trust — surprising users by deleting their source files is a cardinal sin for a library app.
```

### The GRDB schema: a deliberate subset

CB8's `db/schema/create.ts` defines the full server schema. The on-device port takes the library tables and **drops the entire auth complex** — `users`, `session`, `account`, `verification` are better-auth's tables for multi-user web access, meaningless on a single-user device. Per-user progress tables collapse into the comic row itself (which CB8 also maintains for the desktop case).

```swift
import GRDB

struct LocalComic: Codable, FetchableRecord, MutablePersistableRecord {
    static let databaseTableName = "comics"

    var id: Int64?
    var bookmarkData: Data?      // replaces file_path for external files
    var relativePath: String?    // for files owned in Documents
    var title: String
    var pageCount: Int
    var fileSize: Int64
    var dateAdded: Date
    var lastPage: Int?
    var lastLocation: String?
    var lastRead: Date?
    var mediaType: String        // 'comic' | 'book'
    var seriesName: String?
    var volumeNumber: Double?    // REAL in CB8's schema — keep it; "vol 1.5" exists
    var chapterNumber: Double?
    var completed: Bool

    mutating func didInsert(_ inserted: InsertionSuccess) {
        id = inserted.rowID
    }
}

func makeDatabase(at path: String) throws -> DatabasePool {
    var config = Configuration()
    config.prepareDatabase { db in
        try db.execute(sql: "PRAGMA journal_mode = WAL")
    }
    let pool = try DatabasePool(path: path, configuration: config)

    var migrator = DatabaseMigrator()
    migrator.registerMigration("v1") { db in
        try db.create(table: "comics") { t in
            t.autoIncrementedPrimaryKey("id")
            t.column("bookmarkData", .blob)
            t.column("relativePath", .text)        // unique within Documents
            t.column("title", .text).notNull()
            t.column("pageCount", .integer).notNull()
            t.column("fileSize", .integer).notNull()
            t.column("dateAdded", .datetime).notNull()
            t.column("lastPage", .integer)
            t.column("lastLocation", .text)
            t.column("lastRead", .datetime)
            t.column("mediaType", .text).notNull().defaults(to: "comic")
            t.column("seriesName", .text)
            t.column("volumeNumber", .double)
            t.column("chapterNumber", .double)
            t.column("completed", .boolean).notNull().defaults(to: false)
        }
        try db.create(table: "tags") { t in
            t.autoIncrementedPrimaryKey("id")
            t.column("name", .text).notNull().unique()
        }
        try db.create(table: "comicTags") { t in
            t.belongsTo("comic", onDelete: .cascade).notNull()
            t.belongsTo("tag", onDelete: .cascade).notNull()
            t.primaryKey(["comicId", "tagId"])
        }
        try db.create(table: "bookmarks") { t in
            t.autoIncrementedPrimaryKey("id")
            t.belongsTo("comic", onDelete: .cascade).notNull()
            t.column("page", .integer).notNull()
            t.column("note", .text)
        }
    }
    try migrator.migrate(pool)
    return pool
}
```

Two departures from CB8's schema, both deliberate. **No `cover_thumbnail BLOB`:** CB8 stores covers in the row; on iOS, store thumbnail JPEGs as files in `Library/Caches/Thumbnails/<id>.jpg` instead — Caches is purgeable by the system under storage pressure, which is exactly right for regenerable data, and it keeps rows small for fast grid queries. **No `file_path`:** sandbox paths aren't stable identity; the bookmark/relative-path pair is. Use CB8's migration discipline though — its `migrations.ts` tracks `schema_version` and is at v6; GRDB's `DatabaseMigrator` is the same idea with registration order as the version.

GRDB's `ValueObservation` replaces the IPC change notifications the Electron renderer gets: the library grid observes the query and re-renders on any DB write — scanning updates the UI live, like CB8's `ScanProgress` events.

### Scanning and thumbnails

The scanner walks granted folders, filters by CB8's extension list (`.cbz/.cbr/.epub/.pdf/.mobi`), and indexes anything new or changed — `fileScanner.ts`, translated to `FileManager.enumerator` inside `withFolderAccess`. Port `seriesParser.ts` alongside it: parsing series/volume/chapter out of filenames is regex work that transfers nearly line-for-line, and its vitest file (`seriesParser.test.ts`) comes along as the spec.

Thumbnails replace `sharp` with ImageIO's downsampling — which decodes *at* the target size rather than decoding full-size then shrinking, the difference between a scan that hums and one that gets the app jetsam-killed:

```swift
import ImageIO

func makeThumbnail(from imageData: Data, maxPixel: CGFloat = 480) -> CGImage? {
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceShouldCacheImmediately: true,
        kCGImageSourceThumbnailMaxPixelSize: maxPixel,
    ]
    guard let source = CGImageSourceCreateWithData(imageData as CFData, nil) else {
        return nil
    }
    return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
}
```

Cover *selection* (which archive entry becomes the thumbnail) is `coverSelection.ts` — port it, don't improvise, or local and server libraries will show different covers for the same file. EPUB covers come from the OPF manifest (Readium exposes this; or port `epubCoverExtractor.ts`'s logic over ZIPFoundation, since an EPUB is a ZIP); PDF covers are one PDFKit call: `document.page(at: 0)?.thumbnail(of: size, for: .mediaBox)` — that's the whole of `pdfCoverExtractor.ts` on iOS.

Run scans as a cooperative async task updating a `ScanProgress`-shaped observable (`discovered` / `processed` / `currentFile` — same fields as CB8's type, your progress UI will thank you). Don't reach for `BGProcessingTask` first: scans triggered by an explicit import can run in the foreground with a progress bar, which is both simpler and more legible to the user. Background refresh of external folders is a later nicety, and security-scoped resources plus background task time limits make it genuinely fiddly.

---

## Part 9 — Archives and the Shared-Logic Ports

This part replaces `archiveLoader.ts` + node-7z, and rewrites the `src/shared/` utilities the reader depends on. The contract to preserve, from `ArchiveHandle` in `src/shared/types.ts`: an archive opens to a list of image entries, natural-sorted, with `pageCount` and random access to any page's bytes.

### CBZ: ZIPFoundation

A CBZ is a ZIP of images. ZIPFoundation reads the central directory without unpacking, and extracts single entries to memory — random access, exactly what page-jumping needs:

```swift
import ZIPFoundation

struct ComicArchive {
    let url: URL
    private let archive: Archive
    /// Sorted, filtered image entries — index n IS page n, the same
    /// invariant the server's ArchiveLoader maintains.
    let pages: [Entry]

    init(url: URL) throws {
        self.url = url
        self.archive = try Archive(url: url, accessMode: .read)
        self.pages = archive
            .filter { $0.type == .file && isImageFile($0.path) }
            .sorted { naturalCompare($0.path, $1.path) < 0 }
    }

    var pageCount: Int { pages.count }

    func pageData(at index: Int) throws -> Data {
        var data = Data()
        data.reserveCapacity(Int(pages[index].uncompressedSize))
        _ = try archive.extract(pages[index], bufferSize: 64 << 10) { chunk in
            data.append(chunk)
        }
        return data
    }
}
```

Keep open `ComicArchive` handles in a small LRU keyed by comic id — the same pattern as the server's `archiveCache.ts`, and the same reason: reopening the ZIP central directory on every page turn is wasted work. Port `src/shared/lru.ts` for this; it's a dozen lines and its test file keeps you honest.

### CBR: the honest options

CBR is RAR, and RAR is encumbered: the reference unrar source ships under a license forbidding use in RAR-creation tools (extraction is fine) and is not OSI-open-source. The options:

1. **libarchive** — reads RAR4 and (since 3.4) most RAR5. BSD-licensed, C API, ships in many places but *not* as an iOS-usable system library, so you vendor it (SPM wrappers exist, or build it as an xcframework). Fails on some solid/encrypted archives.
2. **UnrarKit** — Objective-C wrapper over the official unrar library. Best compatibility (it *is* RAR's own extractor); the unrar license rides along — acceptable for App Store distribution, but read it and note it in your acknowledgements screen.
3. **Convert at the edge.** Detect CBR at import and repack to CBZ (extract → re-zip with ZIPFoundation). Storage cost during conversion, but afterward your reader has exactly one archive path. For *server* libraries this is moot — the server's node-7z handles CBR and the phone only ever sees decoded images over `/pages/:n`. Phase 1 gets CBR support for free; only local imports need this decision.

Recommendation: UnrarKit for owned local files (compatibility beats purity for a reader app), and lean on the server path otherwise. Whatever you choose, route both formats through the `ComicArchive` protocol so the reader is format-blind, as `archiveLoader.ts` is.

```quiz
Q: Why extract individual ZIP entries to memory and keep `ComicArchive` handles in a small LRU, rather than unpacking the whole CBZ?
- [ ] iOS forbids writing temp files
- [x] A reader needs random access to any page's bytes, so reading the central directory and extracting single entries on demand fits page-jumping; the LRU avoids re-reading the ZIP central directory on every page turn — mirroring the server's archiveCache.ts
- [ ] Full extraction is impossible in Swift
- [ ] It's required for thumbnails
> Page-jumping wants O(1) access to entry `n`, which ZIPFoundation gives by reading the central directory and extracting just that entry — no need to unpack megabytes of unused pages. But reopening and re-parsing the central directory on every turn is wasted work, so an LRU of open archive handles keyed by comic id (a direct port of CB8's `archiveCache.ts`) keeps the hot archives ready. Same problem, same solution as the server.

Q: Phase 1 (server client) gets CBR support "for free" while Phase 2 (local imports) needs a real decision. Why the asymmetry?
- [ ] CBR is only valid on servers
- [x] In Phase 1 the server's node-7z extracts CBR and the phone only ever receives decoded images over `/pages/:n`, so RAR never touches the device; only local on-device imports must solve RAR extraction (libarchive, UnrarKit, or convert-to-CBZ at import)
- [ ] Phase 2 drops CBR support
- [ ] App Review bans CBR
> The server already decodes every format and serves plain page images, so a Phase 1 client is format-agnostic — CBR is the server's problem. Standalone mode has no server, so the device must extract RAR itself, where the encumbered unrar license and partial libarchive support force a real choice (the guide recommends UnrarKit for owned files). Routing both formats through one `ComicArchive` protocol keeps the reader format-blind either way.

Q: Why is porting `naturalSort.ts` called a "spec-fidelity exercise" where an "almost right" port is a real bug?
- [ ] It's the slowest function to run
- [x] It decides page order, so any deviation (e.g. not sorting numeric chunks as integers) shows page 10 between pages 1 and 2 — and the order must match the server's so shared progress indexes line up, which is why its test file comes along as the spec
- [ ] Swift can't do string comparison
- [ ] It affects thumbnail quality
> Natural sort governs the canonical page sequence, and subtle rule differences (integer-compare numeric chunks, numeric-before-non-numeric, the "01" vs "1" fall-through) produce visibly wrong ordering. Worse, if the client's order diverges from the server's, page index `n` no longer means the same page, breaking cross-client progress. Porting the behavior exactly — bringing the original's test file as the spec — is what keeps both invariants intact.
```

### Porting `naturalSort.ts` — the spec-fidelity exercise

This function decides page order; an "almost right" port shows users page 10 after page 1 and before page 2. CB8's implementation: split into digit/non-digit chunks; numeric chunks compare as integers; numeric sorts before non-numeric at the same position; non-numeric compares case-insensitively; ties fall through; shorter wins. The Swift port, side by side with the original's structure:

```swift
/// Port of src/shared/naturalSort.ts — keep behavior identical, including
/// the "numeric chunks sort before non-numeric" rule and the equal-number
/// fall-through ("01" vs "1").
func naturalCompare(_ a: String, _ b: String) -> Int {
    func chunks(_ s: String) -> [Substring] {
        var result: [Substring] = []
        var index = s.startIndex
        while index < s.endIndex {
            let isDigit = s[index].isNumber
            var end = index
            while end < s.endIndex, s[end].isNumber == isDigit {
                end = s.index(after: end)
            }
            result.append(s[index..<end])
            index = end
        }
        return result
    }

    let ca = chunks(a), cb = chunks(b)
    for (x, y) in zip(ca, cb) {
        let xNum = x.first?.isNumber == true
        let yNum = y.first?.isNumber == true
        if xNum && yNum {
            let dx = Int(x) ?? 0, dy = Int(y) ?? 0
            if dx != dy { return dx < dy ? -1 : 1 }
            // numerically equal ("01" vs "1") — fall through
        } else if xNum != yNum {
            return xNum ? -1 : 1          // numbers before text
        } else {
            let cmp = x.lowercased().compare(y.lowercased())
            if cmp != .orderedSame { return cmp == .orderedAscending ? -1 : 1 }
        }
    }
    return ca.count - cb.count            // shorter first on full tie
}
```

One fidelity caveat worth a comment in your code: the TypeScript original uses `localeCompare` for text chunks; the port uses plain `compare`. For ASCII filenames (the overwhelming case for scan sets) they agree; for non-ASCII titles they can disagree with the server's ordering. If your library is full of Japanese filenames and the same archive must page identically on web and iOS, match semantics with `compare(_:options:range:locale:)` against the same locale — and add the test case.

`imageFilter.ts` is a one-liner to port — same extension set, and note it includes `jxl` and `avif`, both of which iOS 17+ decodes natively, so don't drop them:

```swift
/// Port of src/shared/imageFilter.ts.
private let imageExtensions: Set<Substring> =
    ["jpg", "jpeg", "png", "webp", "gif", "bmp", "jxl", "avif"]

func isImageFile(_ filename: String) -> Bool {
    guard let ext = filename.split(separator: ".").last else { return false }
    return imageExtensions.contains(Substring(ext.lowercased()))
}
```

`scaleFit.ts` mostly dissolves — `contentMode: .fit` and `AVMakeRect(aspectRatio:insideRect:)` do this math natively — but port it anyway if you write custom layout for two-page spreads, where you'll need the explicit computation, and the degenerate-input guard (zero/negative dimensions → zero) has a test asserting it.

---

## Part 10 — Progress Sync and Offline

With both modes built, the app has two libraries: server (Phase 1) and local (Phase 2). The remaining glue is offline reading for server content, and a clear-eyed progress story.

### Offline downloads

`GET /api/comics/:id/file` streams the original file — it exists for client-side book rendering, and it doubles as the download endpoint. Offline is then: download → store under `Library/Application Support/Offline/<serverID>/<comicID>.<ext>` (not Caches — user-requested downloads shouldn't evaporate; flag them with `isExcludedFromBackup`, they're re-downloadable) → open through the Part 8/9 local pipeline → keep the record's identity tied to the server copy.

Use a background `URLSessionConfiguration.background` session so multi-hundred-MB archives survive app suspension and continue over Wi-Fi; the delegate-based completion writes the file and inserts a row in a `downloads` table mapping `(serverURL, remoteID) → localPath`. The reader checks that table first: if a local copy exists, pages come from `ComicArchive`; otherwise from `/pages/:n`. Same `ComicRecord`, two data sources behind one protocol — the iOS edition of CB8 serving the same UI from Electron or Docker.

### Progress: one writer rule

Reading position is the one piece of state both sides mutate. Keep the rules simple and explicit:

- **Server comics, online:** the server is the source of truth. Write-through on every page turn (Part 6), read `lastPage` on open. No local persistence beyond the in-memory model.
- **Server comics, offline:** queue progress writes locally (a `pendingProgress` table: comic id, page, location, timestamp). On reconnect, replay in timestamp order — `PUT progress` is idempotent per value, and **last-write-wins is correct here**, because "furthest device read to" is genuinely the latest event, not a conflict to merge. Don't build vector clocks for a comic reader.
- **Local comics:** GRDB row is the only truth. No sync target exists.

The single trap: replaying a *stale* offline queue after you've read further on another device would yank position backward. Cheap guard — when replaying, fetch the record first and skip queued writes older than the server's `lastRead`. That's the entire conflict policy, and it matches what users mean by "sync my place."

### What not to build

Resist syncing the *libraries* themselves (server rows mirrored into GRDB wholesale, two-way). CB8's server is already the multi-device coordination point — that's its job in the Docker deployment. The phone is a client plus a private local shelf. The moment both sides own the same record you're building a distributed system, and Part 10 of a reader-app guide is the wrong place to be building one.

---

## Part 11 — Testing: Porting the Vitest Suite

CB8 ships tests where they pay: the pure logic (`naturalSort.test.ts`, `imageFilter.test.ts`, `scaleFit.test.ts`, `coverSelection.test.ts`, `lru.test.ts`, `seriesParser.test.ts`, plus property tests via fast-check). Since Part 9 ported those modules as specifications, the tests are the conformance suite — port them first, then the modules, TDD by transcription.

Vitest and Swift Testing are close enough that conversion is mechanical:

```typescript
// naturalSort.test.ts (CB8)
it('sorts page2 before page10', () => {
  expect(naturalCompare('page2.jpg', 'page10.jpg')).toBeLessThan(0);
});
```

```swift
import Testing

@Suite("NaturalSort — ported from src/shared/naturalSort.test.ts")
struct NaturalSortTests {
    @Test("sorts page2 before page10")
    func numericChunks() {
        #expect(naturalCompare("page2.jpg", "page10.jpg") < 0)
    }

    @Test("numbers sort before text at the same position")
    func numbersBeforeText() {
        #expect(naturalCompare("2.jpg", "cover.jpg") < 0)
    }

    @Test(arguments: [
        (["page1.jpg", "page10.jpg", "page2.jpg"],
         ["page1.jpg", "page2.jpg", "page10.jpg"]),
        (["ch1/p1.png", "ch1/p10.png", "ch1/p2.png"],
         ["ch1/p1.png", "ch1/p2.png", "ch1/p10.png"]),
    ])
    func ordersLikeTheServer(input: [String], expected: [String]) {
        #expect(input.sorted { naturalCompare($0, $1) < 0 } == expected)
    }
}
```

Parameterized `@Test(arguments:)` covers most of what fast-check was doing in spirit; if you want real property testing, generate random filename sets in a test and assert the invariants (totality, antisymmetry, transitivity on a sample, and "integer-aware ordering matches numeric comparison for pure-number names").

Beyond the ports:

- **API client tests** against a fixture server: spin up a tiny local HTTP server in tests (or stub `URLProtocol`) replaying captured CB8 responses — record real JSON from a dev server once, commit the fixtures. This catches the model-drift class of bug (a field renamed in `mapping.ts`) at test time instead of decode-crash time. When CB8's API changes upstream, refreshing fixtures *is* the compatibility audit.
- **Archive tests** with tiny committed fixtures: a 4-page CBZ built in-repo (have the test create it with ZIPFoundation), including a non-image entry to prove filtering, and misordered names (`p1, p10, p2`) to prove sorting end-to-end through `ComicArchive`.
- **Snapshot the reader math, not the pixels.** Progress writes, prefetch windows, and page-index handling are plain logic — test `ComicReaderModel` with a stubbed client and assert "opening at lastPage 41 requests pages 41–44," no UI involved. (Design note: that's why the model takes a client and width as init parameters.)

`pnpm test` ↔ `xcodebuild test` parity matters for one reason: when upstream CB8 changes `src/shared/`, the diff tells you which Swift file and which test file to update. Keep the "ported from" comment headers — they're the cross-reference.

---

## Part 12 — Distribution and App Review

The mechanics (signing, TestFlight, App Store Connect) are covered in the [iOS Development guide](IOS_DEVELOPMENT_STUDY_GUIDE.md); this part is the CB8-specific review surface.

- **Guideline 4.2 (minimum functionality) is fully defused by going native** — Parts 4–9 are unambiguously an app, not a wrapped site. This was a real factor in the Part 2 decision, not a formality: the wrapper variant carries genuine rejection risk; the native app carries none on this axis.
- **User-generated / user-provided content.** A reader for the user's own files is not a content service, but reviewers sometimes test with whatever's lying around. Make first-run state self-explanatory (empty library with clear import affordances), and make the server-connection screen obviously *bring-your-own-server* — apps that look like clients for a content service get asked "where does the content come from?" Have the answer in your review notes: "displays files the user owns; connects only to servers the user operates."
- **Demo account for review.** If the server-client mode is prominent, App Review will want to try it. Run a small CB8 instance (their Docker image makes this trivial) with innocuous public-domain content, and put credentials in the review notes. Don't make a reviewer set up Docker.
- **ATS exceptions** (Part 4): `NSAllowsLocalNetworking` is uncontroversial. Broad `NSAllowsArbitraryLoads` invites questions — if you support arbitrary HTTP URLs, scope the exception and explain it in review notes ("self-hosted media servers on user LANs commonly lack TLS").
- **Local network privacy.** Talking to a LAN server triggers the local-network permission prompt (iOS 14+); set `NSLocalNetworkUsageDescription` to something honest ("CB8 connects to your own media server on your network"). If you later add Bonjour discovery of CB8 servers — a nice touch — declare the service type in `NSBonjourServices`.
- **Licenses ship with the app.** ZIPFoundation (MIT), GRDB (MIT), Readium (BSD) are easy; UnrarKit bundles the unrar license with its no-RAR-creation clause — include all of them in an acknowledgements screen. CB8 itself is MIT-licensed, so deriving the iOS app from it (including porting its `shared/` logic) requires only preserving the copyright notice — do that in the acknowledgements too.
- **Encryption export compliance:** HTTPS-only counts as exempt; declare `ITSAppUsesNonExemptEncryption = NO` and move on.

A note on expectations: CB8's desktop releases ship via GitHub Releases — build, upload, done. iOS adds a review cycle (typically a day, occasionally a frustrating loop) and an annual developer fee. TestFlight is the pressure valve: up to 10,000 external testers with a lighter review, which for a self-hosted-community app may be a perfectly good "release channel" while the App Store listing matures. Sideloading via AltStore/EU alternative marketplaces exists but reaches a sliver of the audience.

---

## Appendix — The WKWebView / Capacitor Shortcut

Part 2 ruled this out as the destination; here's the recipe anyway, because as a weekend proof-of-concept — or a stopgap while Phase 1 is in progress — it's genuinely useful, and building it teaches you the API surface.

**Bare WKWebView (an afternoon):** an app with one screen — a server URL field (persisted), and a full-screen `WKWebView` pointed at it. CB8's web UI already handles touch, auth, and responsive layout, so what you get is exactly the LAN-browser experience, packaged.

```swift
struct ServerWebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        // Session cookie persists in WKWebsiteDataStore.default()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}
}
```

Details that separate "works" from "feels broken": handle the offline/unreachable state with a native retry screen (`webView(_:didFailProvisionalNavigation:)`) instead of WebKit's error page; respect safe areas *except* in the reader (CB8's reader goes immersive — let the web content underlap and the chrome handle insets); and disable the pinch-zoom of the *page itself* (viewport is already correctly set by the SPA) so the reader's own pinch handling wins.

**Capacitor (a weekend):** `npm i @capacitor/core @capacitor/ios` in the CB8 repo, point Capacitor's `webDir` at `dist/web`, and the SPA ships inside the app bundle, served from `capacitor://localhost` — with the SPA configured (one small upstream patch) to read a server base URL from preferences instead of assuming same-origin. You gain an app icon, splash screen, plugin access (haptics on page turn, keep-awake while reading), and offline shell loading. You don't gain: on-device libraries, native reader feel, or distance from guideline 4.2. CORS note: once the SPA is not same-origin with the API, the server's `@fastify/cors` config and the session cookie's `SameSite` behavior both need attention upstream — the cookie that "just worked" same-origin now needs `credentials: 'include'` on fetches and a CORS policy that allows it.

If the wrapper is ever the thing you ship, pair it with at least one undeniably native capability (offline downloads through the share sheet, a native library tab) — both for review safety and because that's the gravitational path toward the real app this guide builds.

---

## Closing: the porting checklist

The condensed sequence, with the CB8 source of truth for each step:

1. **Read the API routes** (`src/main/webServer/routes/`) — they are the contract. *(Part 4)*
2. **Ship the server client**: login → grid → reader → progress. Usable app, zero CB8 changes. *(Parts 4–6)*
3. **Native PDF, chosen-trade-off EPUB.** *(Part 7)*
4. **Port `src/shared/` with its tests** — naturalSort, imageFilter, LRU, coverSelection, seriesParser. *(Parts 9, 11)*
5. **Local library**: document picker + bookmarks, GRDB subset of `db/schema/create.ts`, ImageIO thumbnails. *(Part 8)*
6. **In-process archives**: ZIPFoundation CBZ; decide CBR (UnrarKit / libarchive / convert). *(Part 9)*
7. **Offline + progress replay** with the stale-write guard. *(Part 10)*
8. **Review prep**: demo server, ATS scoping, local-network string, licenses. *(Part 12)*

The through-line: CB8's decision to put an HTTP API between its GUI and its engine — made so a desktop app could also be a Docker container — is what makes the iOS app a two-phase project instead of a rewrite-from-zero. The best time to make an Electron app portable to mobile is when you architect it; the second-best time is never needed if you did it the first way.

---

## Where to Go Next

- **Do Apple's [SwiftUI tutorials](https://developer.apple.com/tutorials/swiftui)** if SwiftUI is new — they're genuinely good, and Parts 4–6 of this guide assume the fluency they build. The [Swift guide](SWIFT_STUDY_GUIDE.md) in this repo covers the language itself.
- **Read the platform docs that gate this port:** [GRDB](https://github.com/groue/GRDB.swift) (the SQLite layer), [PDFKit](https://developer.apple.com/documentation/pdfkit) and [WKWebView](https://developer.apple.com/documentation/webkit/wkwebview) (the two readers), [URLSession background downloads](https://developer.apple.com/documentation/foundation/url_loading_system/downloading_files_in_the_background), and the [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) before you build anything reviewers will question.
- **Read the [CB8 source](https://github.com/s4njee/CB8) with this guide open** — `src/shared/` and the server routes define the port; the guide only maps them.
- **Ship the Phase 1 server client first** — login → grid → reader → progress against a real CB8 server proves every architectural seam with the least code; the local library lands behind the same interfaces in Phase 2.
- **Sibling guides in this repo:** the [CB8 Android guide](CB8_ANDROID_STUDY_GUIDE.md) (the same port, other platform — the shared-logic decisions should be made jointly), [iOS Development](IOS_DEVELOPMENT_STUDY_GUIDE.md) (the platform guide this one builds on), [Electron](ELECTRON_STUDY_GUIDE.md) (the architecture being ported), and [SQLite](SQLITE_STUDY_GUIDE.md) (what GRDB wraps).

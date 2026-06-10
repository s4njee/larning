# CB8 on Android

A practical, depth-first guide to bringing [CB8](https://github.com/s4njee/CB8) — a comic and book reader built as an Electron app with an embedded web server and a React web GUI — to Android phones and tablets. This is the sibling of the [CB8 on iOS guide](CB8_IOS_STUDY_GUIDE.md): same source codebase, same two-phase strategy (native client for CB8 servers first, on-device library second), deliberately parallel part structure — but nearly every platform decision lands differently, because Android's sandbox, review process, and ecosystem are different in ways that matter for exactly this kind of port. Where the reasoning is identical to iOS, this guide says so and moves on; where Android changes the answer, it slows down.

Assumes you can read TypeScript (CB8's language) and have basic Kotlin exposure. The [iOS sibling guide](CB8_IOS_STUDY_GUIDE.md) Part 1 contains the full anatomy of the CB8 codebase; Part 1 here recaps it briefly and then focuses on the Android delta.

Primary references: the [CB8 repository](https://github.com/s4njee/CB8), [Jetpack Compose](https://developer.android.com/develop/ui/compose), [Room](https://developer.android.com/training/data-storage/room), the [Storage Access Framework](https://developer.android.com/guide/topics/providers/document-provider), the [Readium Kotlin Toolkit](https://github.com/readium/kotlin-toolkit), [Coil](https://coil-kt.github.io/coil/), and the [Google Play policy center](https://play.google/developer-content-policy/).

---

## Table of Contents

1. [Part 1 — Same Codebase, Different Rules: The Android Delta](#part-1--same-codebase-different-rules-the-android-delta)
2. [Part 2 — Choosing a Porting Strategy (the Android Version)](#part-2--choosing-a-porting-strategy-the-android-version)
3. [Part 3 — Project Setup and the Dependency Map](#part-3--project-setup-and-the-dependency-map)
4. [Part 4 — The Kotlin API Client](#part-4--the-kotlin-api-client)
5. [Part 5 — The Library UI](#part-5--the-library-ui)
6. [Part 6 — The Comic Reader](#part-6--the-comic-reader)
7. [Part 7 — EPUB and PDF](#part-7--epub-and-pdf)
8. [Part 8 — Going Standalone: The On-Device Library](#part-8--going-standalone-the-on-device-library)
9. [Part 9 — Archives and the Shared-Logic Ports](#part-9--archives-and-the-shared-logic-ports)
10. [Part 10 — Progress Sync and Offline](#part-10--progress-sync-and-offline)
11. [Part 11 — Testing: Porting the Vitest Suite](#part-11--testing-porting-the-vitest-suite)
12. [Part 12 — Distribution: Play, F-Droid, and the Sideload Channel](#part-12--distribution-play-f-droid-and-the-sideload-channel)
13. [Appendix — WebView Wrappers and the On-Device Node Experiment](#appendix--webview-wrappers-and-the-on-device-node-experiment)

---

## Part 1 — Same Codebase, Different Rules: The Android Delta

### Thirty-second recap of what CB8 is

CB8 runs three ways from one codebase — Electron desktop app, Docker container, plain Node standalone — and all three host the same embedded Fastify HTTP server, which serves the compiled React SPA and a JSON API under `/api/*`. Library state lives in SQLite (`better-sqlite3`); CBZ/CBR pages are extracted by spawning a 7-Zip executable (`node-7z`); EPUB renders client-side with `epubjs` and PDF with `pdfjs-dist`; auth is better-auth with signed session cookies; and `src/shared/` holds small, pure, vitest-covered logic modules (`naturalSort`, `imageFilter`, `scaleFit`, `coverSelection`, `lru`) that act as portable specifications. The deep tour — module map, endpoint inventory, what-survives-the-port table — is [Part 1 of the iOS guide](CB8_IOS_STUDY_GUIDE.md#part-1--reading-the-cb8-codebase-what-youre-actually-porting); everything there about *CB8 itself* applies verbatim, because the codebase doesn't care which phone you hold.

What changes is the platform's rulebook. Five rules that drove the iOS port flip or soften on Android:

### The delta table

| Constraint | iOS | Android | Consequence for the port |
| --- | --- | --- | --- |
| Spawning processes | Forbidden — `node-7z`'s design is dead on arrival | **Allowed** — binaries shipped in the APK's native-library dir are executable (API 29+ only blocks exec from *writable* app storage) | Bundling a 7-Zip binary is *possible*; Part 9 weighs whether it's *wise* |
| JIT compilation | Forbidden outside WebKit | **Allowed** — writable+executable pages are fine | Node-on-device (nodejs-mobile) runs at full speed; the Appendix gives it an honest hearing instead of a flat no |
| Filesystem reach | Sandbox + security-scoped bookmarks | Sandbox + **Storage Access Framework** (persistable tree grants); broad "All files access" exists but is Play-restricted | Scanning a NAS-synced folder works, but SAF traversal performance is a real engineering topic (Part 8) |
| Background work | Tightly budgeted (`BGProcessingTask` roulette) | **WorkManager** — long scans and bulk downloads are first-class citizens | Library scans and offline syncs get dramatically simpler (Parts 8, 10) |
| Store review | Guideline 4.2 looms over wrappers; review gates every build | Play review is lighter; **and the store is optional** — direct APK and F-Droid are real channels | Distribution strategy actually changes shape (Part 12), not just paperwork |

Two deltas cut the other way — Android is *harder* here:

- **Session cookies are not free.** iOS's `URLSession` persists and replays cookies automatically; OkHttp's default `CookieJar` is a no-op, and the JDK `CookieManager` is in-memory only. CB8's better-auth session cookie needs a small persistent cookie store you write yourself (Part 4).
- **PDF is not free.** iOS has PDFKit, a complete reader widget in the OS. Android's `PdfRenderer` rasterizes pages to bitmaps and does nothing else — no text selection, no search, no links. Closing the gap means Jetpack's new `androidx.pdf`, a Pdfium binding, or accepting bitmap-only rendering (Part 7).

And one delta is a wash that surprises people: **device fragmentation matters less than feared for this app.** A reader's hard problems — image memory, archive I/O, gesture feel — are the same on every device; what fragmentation actually costs you here is testing low-RAM behavior (Part 6's bitmap budget) and minding API-level gates on image codecs (Part 9).

### What this means structurally

The two-phase plan survives unchanged, because it was derived from CB8's architecture, not from iOS: **Phase 1**, a native Kotlin client speaking the existing `/api` to a CB8 server the user already runs (the Docker/standalone deployments exist precisely to serve remote clients); **Phase 2**, an on-device library with local scanning, indexing, and in-process archive reading. The endpoint table, the `WebComicRecord` wire shape, the progress-write semantics, the thumbnail cache-buster contract — all established in iOS guide Parts 4–6 — are the same contract here, and this guide references rather than re-derives them.

---

## Part 2 — Choosing a Porting Strategy (the Android Version)

Same four candidate strategies as iOS, three of them landing differently.

### Option 0 revisited: run the Node backend on the device

On iOS this was a trap with four independent fatal wounds. On Android, two of the four heal:

- **JIT is legal**, so nodejs-mobile runs V8 at full speed rather than in a crippled interpreter mode.
- **Process spawning is legal**, so `node-7z` could genuinely shell out to a 7-Zip binary shipped in `jniLibs` (the `lib*.so` trick: name the executable like a shared library, and `applicationInfo.nativeLibraryDir` provides an exec-permitted path — the same mechanism Termux-adjacent apps and bundled-ffmpeg apps use).

What doesn't heal: native Node addons (`better-sqlite3`, `sharp`) still need cross-compiling against nodejs-mobile's headers for four ABIs, with every upstream bump repeating the ceremony; the app becomes a ~40MB-heavier WebView-plus-server sandwich; Android's process-death model (the OS kills your process freely and restores activities later) is hostile to a stateful in-process server; and battery review on Play flags long-running local servers. It graduates from "impossible" to "a fascinating weekend that you will not ship." The Appendix walks through it because on Android it's at least *instructive*; the recommendation is unchanged.

### Option 1: WebView wrapper / Capacitor / TWA

Materially more attractive than on iOS:

- **Policy risk is lower.** Play has no 4.2-style hostility to wrappers; its minimum-functionality and spam policies target low-effort website rebundles, and a self-hosted-server client with a settings UI and native niceties clears that bar in practice. Thousands of WebView-shell apps live on Play.
- **The platform embraces the pattern.** Trusted Web Activities exist specifically to ship a (HTTPS, public) web app as an Android app. TWA doesn't fit CB8 — it requires a public origin with digital asset links, and CB8 servers are private LAN hosts — but plain WebView and Capacitor work the same as on iOS.
- The *product* objections survive intact: no on-device library, webview reader feel, no offline story. They're the reason this is still a stopgap, not the destination.

### Option 2: React Native / Flutter

The same calculus as iOS, with one Android-specific addendum: if the *real* goal is "CB8 on both mobile platforms with one team," the cross-platform conversation is worth having *before* building either native app, because having shipped a Swift app first is the worst time to adopt Flutter. The counterweights also repeat: the reader still wants platform-grade gesture/image work, the archive and SQLite layers are native regardless, and the UI rewrite happens in any case since shadcn/Tailwind components don't transfer. For a personal project shipping sequentially, per-platform native remains the recommendation; the closing section names the middle path (Kotlin Multiplatform for the non-UI core) if both ports become real.

### Option 3 (recommended): native Kotlin + Jetpack Compose, two phases

The same shape as the iOS plan: Phase 1 is a Compose client for existing CB8 servers — login, library grid, reader, progress — requiring zero upstream changes; Phase 2 adds the on-device library via SAF, Room, and in-process archive readers. Compose is assumed throughout (this is a new app in 2026; the View system earns no place here), minimum SDK 26 (covers effectively the whole fleet while keeping `java.time` and adaptive icons unconditional), target SDK current per Play's annual requirement.

### Strategy decision table (Android edition)

| | WebView / Capacitor | RN / Flutter | On-device Node | Native Kotlin + Compose |
| --- | --- | --- | --- | --- |
| UI reuse from CB8 | ~100% | ~0% | ~100% | 0% |
| Offline / local library | No | With native modules | Theoretically | First-class |
| Reader feel | Webview-grade | Good with effort | Webview-grade | Native |
| Play policy risk | Low (unlike iOS) | Low | Battery/process flags | Low |
| Maintenance tail | Low | Toolchain-sized | Severe (addon cross-compiles) | Normal |
| Verdict | Legitimate stopgap | Only if going cross-platform first | Don't ship it | **Build this** |

---

## Part 3 — Project Setup and the Dependency Map

### Creating the project

Android Studio → New Project → Empty Activity (Compose). Kotlin DSL build scripts, version catalog (`libs.versions.toml`), `minSdk 26`. Single-module is fine to start; if you want structure that mirrors CB8's separation the way the iOS guide's target layout did:

```
app/src/main/java/com/example/cb8/
  api/            # Part 4 — server client (CB8's webServer, consumed)
  library/        # Part 5 — browse UI (CB8's renderer/pages)
  reader/         # Parts 6–7 — comic/EPUB/PDF readers
  locallibrary/   # Part 8 — Room store, SAF scanner, importer (CB8's src/main)
  archives/       # Part 9 — CBZ/CBR access (CB8's archiveLoader)
  shared/         # Part 9 — naturalSort, imageFilter, lru ports (mirror src/shared names)
app/src/test/     # Part 11 — ported vitest suites (JVM, no emulator)
```

Keeping `shared/` file names parallel to CB8's `src/shared/` (`NaturalSort.kt` ↔ `naturalSort.ts`) preserves the same upstream-diffing benefit the iOS guide established.

### The dependency map

The same `package.json` inventory as the iOS guide's Part 3 table, with the Android column filled in:

| CB8 dependency | Role in CB8 | Android replacement | Notes |
| --- | --- | --- | --- |
| `electron` + Forge | Shell, packaging | — (Gradle, APK/AAB) | Does not port |
| `fastify` + plugins | Embedded HTTP server | — (consumed remotely in Phase 1; unnecessary in Phase 2) | See Appendix for the contrarian path |
| `better-auth`, `bcryptjs` | Sessions, hashing | OkHttp + a small persistent `CookieJar`; credentials in `EncryptedSharedPreferences`/Keystore | Hashing stays server-side; cookie persistence is on you (Part 4) |
| `better-sqlite3` | Library index | **Room** (SQLDelight is the fine alternative) | Same SQLite underneath; Room adds compile-checked queries, migrations, Flow observation |
| `node-7z` + 7-Zip binary, `yauzl` | CBZ/CBR extraction | `java.util.zip.ZipFile` for CBZ; `junrar` / libarchive-NDK for CBR | Part 9 — including the RAR5 problem and the bundled-7z temptation |
| `sharp`, `@napi-rs/canvas` | Thumbnails, resize | `BitmapFactory` with `inSampleSize` (+ Coil for the UI layer) | Subsampled decode = ImageIO downsampling's equivalent |
| `@jsquash/jxl` | JPEG XL decode | No platform decoder — needs libjxl via JNI, or skip | AVIF *is* platform-decoded on API 31+; JXL is the gap (Part 9) |
| `pdfjs-dist` | PDF rendering | `PdfRenderer` / `androidx.pdf` / Pdfium binding | Part 7 — the one place Android is behind iOS |
| `epubjs` | EPUB rendering | [Readium Kotlin Toolkit](https://github.com/readium/kotlin-toolkit), or WebView + epub.js | Same trade-off as iOS, same CFI-compatibility caveat |
| `react`, `react-router-dom` | UI, navigation | Jetpack Compose, Navigation-Compose | Pages map 1:1 to destinations |
| `zustand` | Client state | `ViewModel` + `StateFlow` (or plain `mutableStateOf` holders) | Same role |
| `@tanstack/react-query` | Server cache, pagination | **Paging 3** for the grid; plain suspend calls + small caches elsewhere | CB8's offset/limit API is exactly Paging 3's home turf (Part 5) |
| Tailwind/shadcn/radix, `lucide-react`, `sonner` | Components, icons, toasts | Material 3 Compose, `Icons.*`, `SnackbarHost` | — |
| `vitest`, `fast-check` | Tests | JUnit 5 / kotest (+ kotest property testing — a genuine fast-check equivalent) | Part 11 |

Gradle additions for Phase 1: `retrofit` + `kotlinx-serialization` converter (or Ktor client if you prefer — either is fine; the examples use Retrofit/OkHttp because its interceptor/cookie ecosystem is deeper), `coil-compose`, `androidx.paging:paging-compose`, `androidx.navigation:navigation-compose`. Phase 2 adds `room-runtime`/`room-ktx` (+ ksp compiler), `androidx.work:work-runtime-ktx`, `androidx.documentfile:documentfile`, and your chosen RAR dependency.

---

## Part 4 — The Kotlin API Client

The contract is the one transcribed in [iOS guide Part 4](CB8_IOS_STUDY_GUIDE.md#part-4--the-swift-api-client): the endpoint table compiled from `src/main/webServer/routes/`, the `WebComicRecord` shape from `mapping.ts`, the `?width=` server-side resize with day-long cache headers, and the progress auto-complete rule that clients must *not* duplicate. None of that changes per platform. What changes is the plumbing.

### Models

`kotlinx.serialization` mirrors of `mapping.ts` and `src/shared/types.ts`:

```kotlin
@Serializable
enum class MediaType { @SerialName("comic") COMIC, @SerialName("book") BOOK }

/** Mirrors WebComicRecord in src/main/webServer/mapping.ts. */
@Serializable
data class ComicRecord(
    val id: Int,
    val title: String,
    val pageCount: Int,
    val fileSize: Long,
    val dateAdded: String,
    val tags: List<String>,
    val lastPage: Int? = null,
    val lastLocation: String? = null,   // EPUB CFI / PDF position for books
    val lastRead: String? = null,
    val mediaType: MediaType,
    val thumbnailUrl: String,           // relative: /api/comics/7/thumbnail?v=...
    val fileExt: String,                // "cbz" | "cbr" | "epub" | "pdf" | "mobi"
    val favorited: Boolean? = null,
)

/** Mirrors QueryResult in src/shared/types.ts. */
@Serializable
data class ComicQueryResult(val records: List<ComicRecord>, val totalCount: Int)
```

Configure `Json { ignoreUnknownKeys = true }` — upstream CB8 adding a field to `mapping.ts` must not crash deployed clients (the Swift `JSONDecoder` ignores unknowns by default; kotlinx throws by default — a classic cross-platform drift bug, caught here instead of in production).

### The Retrofit surface

```kotlin
interface CB8Api {
    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @GET("api/auth/session")
    suspend fun session(): SessionResponse

    @GET("api/comics")
    suspend fun comics(@QueryMap query: Map<String, String>): ComicQueryResult

    @GET("api/comics/{id}")
    suspend fun comic(@Path("id") id: Int): ComicRecord

    @PUT("api/comics/{id}/progress")
    suspend fun saveProgress(@Path("id") id: Int, @Body body: ProgressUpdate): OkResponse

    @GET("api/continue-reading")
    suspend fun continueReading(@Query("limit") limit: Int = 20): List<ComicRecord>
}

@Serializable
data class LoginRequest(val username: String = "admin", val password: String)

@Serializable
data class ProgressUpdate(
    val page: Int? = null,
    val location: String? = null,
    // Deliberately no `completed`: the server auto-completes on the final
    // page (routes/progress.ts) — don't duplicate that rule client-side.
)
```

The `LibraryQuery` type from the iOS guide ports as a data class with a `toQueryMap()` that emits the same parameter names (`search`, `tag`, `sortBy`, `sortOrder`, `offset`, `limit`, `mediaType`, `fileExt`, `readStatus`, `favorites`) — keep `limit = 50` to match the server default and the web client's behavior.

### The part iOS got for free: cookie persistence

CB8's better-auth session rides a signed cookie (prefix `cb8`, 30-day sliding window). OkHttp will neither store nor replay it unless you give it a `CookieJar`, and the stock options are in-memory. A reader app whose login evaporates on process death is broken, so write the small persistent jar once:

```kotlin
/**
 * Persistent CookieJar for the CB8 session cookie. better-auth issues a
 * signed session token cookie (30-day sliding expiry, refreshed ~daily by
 * the server) — losing it across process death logs the user out.
 */
class PersistentCookieJar(context: Context) : CookieJar {
    private val prefs = context.getSharedPreferences("cb8_cookies", Context.MODE_PRIVATE)
    private val cache = ConcurrentHashMap<String, Cookie>()

    init {
        prefs.all.forEach { (_, v) ->
            (v as? String)?.let { serialized ->
                deserialize(serialized)?.takeIf { it.expiresAt > System.currentTimeMillis() }
                    ?.let { cache[key(it)] = it }
            }
        }
    }

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        for (cookie in cookies) {
            cache[key(cookie)] = cookie
            prefs.edit().putString(key(cookie), serialize(cookie)).apply()
        }
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> =
        cache.values.filter { it.matches(url) && it.expiresAt > System.currentTimeMillis() }

    fun clear() { cache.clear(); prefs.edit().clear().apply() }

    private fun key(c: Cookie) = "${c.domain}|${c.path}|${c.name}"
    // serialize/deserialize: name, value, domain, path, expiresAt, flags —
    // a pipe-joined string or a small @Serializable; ~15 lines either way.
}
```

Wire it in once and the auth story collapses to the iOS shape — login sets the cookie, every later call replays it, `401` means "session lapsed, re-login from Keystore-protected credentials":

```kotlin
val cookieJar = PersistentCookieJar(context)
val client = OkHttpClient.Builder()
    .cookieJar(cookieJar)
    .build()

val retrofit = Retrofit.Builder()
    .baseUrl(serverUrl)        // e.g. http://192.168.1.20:8008/
    .client(client)
    .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build()
```

Store the password for silent re-login in `EncryptedSharedPreferences` (Keystore-backed), keyed by server URL — the Keychain advice from the iOS guide, translated. Treat `401` as a state, not an error: an `Authenticator` or a central interceptor that funnels to the login screen, with `GET /api/auth/session` on cold start deciding the first screen.

### Cleartext HTTP on the LAN

Self-hosted CB8 is typically `http://` on a LAN, and Android blocks cleartext by default since API 28 — the ATS story with different XML. Scope the exception instead of flipping the global `usesCleartextTraffic` switch:

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <!-- User-entered self-hosted servers: permit cleartext only for
         private-range hosts the user explicitly configured. -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">192.168.1.20</domain>
    </domain-config>
</network-security-config>
```

One wrinkle iOS doesn't have: `domain-config` entries are static XML, but CB8 server addresses are user-entered at runtime. The honest options are (a) permit cleartext for the app while documenting why (`base-config cleartextTrafficPermitted="true"` — defensible for a self-hosted-only client, and Play does not reject it the way App Review interrogates `NSAllowsArbitraryLoads`), or (b) keep the default and require HTTPS for non-RFC1918 hosts in your own URL validation, permitting cleartext only when the resolved host is private-range. Option (b) is the better product: it nudges remote access toward the reverse-proxy setups CB8's deployment docs already describe.

---

## Part 5 — The Library UI

CB8's renderer pages map onto a bottom-bar Compose app the same way they mapped onto a `TabView`: Library (grid + search + filters), Home (continue-reading / recently-read shelves from the purpose-built endpoints), Organize (tags/folders/series), Settings. Navigation-Compose destinations stand in for react-router routes.

### Paging 3: the react-query replacement that's actually better here

The iOS guide hand-rolled offset pagination in an `@Observable` model. Android has a first-class library for exactly CB8's API shape — `GET /api/comics` with `offset`/`limit`/`totalCount` is a textbook `PagingSource`:

```kotlin
class ComicsPagingSource(
    private val api: CB8Api,
    private val query: LibraryQuery,
) : PagingSource<Int, ComicRecord>() {

    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, ComicRecord> =
        try {
            val offset = params.key ?: 0
            val result = api.comics(
                query.copy(offset = offset, limit = params.loadSize).toQueryMap())
            LoadResult.Page(
                data = result.records,
                prevKey = if (offset == 0) null else (offset - params.loadSize).coerceAtLeast(0),
                nextKey = (offset + result.records.size)
                    .takeIf { it < result.totalCount && result.records.isNotEmpty() },
            )
        } catch (e: Exception) {
            LoadResult.Error(e)
        }

    override fun getRefreshKey(state: PagingState<Int, ComicRecord>) =
        state.anchorPosition?.let { (it - state.config.pageSize / 2).coerceAtLeast(0) }
}

class LibraryViewModel(private val api: CB8Api) : ViewModel() {
    val query = MutableStateFlow(LibraryQuery())

    val comics: Flow<PagingData<ComicRecord>> = query
        .debounce(250)          // search-as-you-type without hammering the server
        .flatMapLatest { q ->
            Pager(PagingConfig(pageSize = 50)) {   // matches the server default
                ComicsPagingSource(api, q)
            }.flow
        }
        .cachedIn(viewModelScope)
}
```

`flatMapLatest` over the query flow gives you what react-query's key invalidation gave the web client: change a filter, the old pager is cancelled, a fresh one starts at offset 0.

### The grid and thumbnails

```kotlin
@Composable
fun LibraryGrid(viewModel: LibraryViewModel, onOpen: (ComicRecord) -> Unit) {
    val comics = viewModel.comics.collectAsLazyPagingItems()

    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 110.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(horizontal = 16.dp),
    ) {
        items(count = comics.itemCount, key = comics.itemKey { it.id }) { index ->
            comics[index]?.let { comic -> CoverCell(comic, onClick = { onOpen(comic) }) }
        }
    }
}

@Composable
fun CoverCell(comic: ComicRecord, onClick: () -> Unit) {
    Column(Modifier.clickable(onClick = onClick)) {
        Box {
            AsyncImage(
                model = serverUrl + comic.thumbnailUrl,   // ?v= cache-buster intact
                contentDescription = comic.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .aspectRatio(2f / 3f)
                    .clip(RoundedCornerShape(8.dp)),
            )
            comic.lastPage?.let { last ->
                if (comic.pageCount > 0) LinearProgressIndicator(
                    progress = { (last + 1f) / comic.pageCount },
                    modifier = Modifier.align(Alignment.BottomStart).fillMaxWidth(),
                )
            }
        }
        Text(comic.title, style = MaterialTheme.typography.bodySmall, maxLines = 2)
    }
}
```

Coil honors the thumbnail contract from `mapping.ts` for free: it keys its memory/disk caches by full URL, so the `?v=<dateAdded>` cache-buster does the invalidation exactly as designed, and its OkHttp-backed disk cache respects the server's cache headers. Give the shared `ImageLoader` a sized disk cache (`diskCache { maxSizeBytes(512L * 1024 * 1024) }`) and pass it the same OkHttp client from Part 4 — **this matters**: the thumbnail endpoint sits behind the same session auth, so Coil's requests need the cookie jar.

Filters are the same `FilterPreset` mapping as iOS (read status / extension / tag / sort, persisted as small `@Serializable`s in DataStore). Shelves are `GET /api/continue-reading` and `/api/recently-read`, rendered as horizontal `LazyRow`s on Home.

---

## Part 6 — The Comic Reader

Same interaction contract as the iOS guide Part 6 — page-at-a-time, pinch/pan/zoom, tap zones, progress on every turn, RTL as pure presentation — with Compose mechanics and one Android-specific discipline (bitmap memory on low-RAM devices).

### Pager + zoom: don't hand-roll the gesture arbitration

Compose's `HorizontalPager` is the paging container. The hard part — pinch-zoom *inside* a pager, where a zoomed-in pan must scroll the image and only flip pages at the edge — is the same gesture-arbitration problem `UIScrollView` solved on iOS. In Compose, the well-trodden answer is [Telephoto](https://saket.github.io/telephoto/)'s `ZoomableAsyncImage` (built on Coil), which implements exactly this pager-aware behavior plus double-tap-to-zoom:

```kotlin
@Composable
fun ComicReader(viewModel: ReaderViewModel) {
    val state = rememberPagerState(
        initialPage = viewModel.startPage,        // comic.lastPage ?? 0 — resume
        pageCount = { viewModel.comic.pageCount },
    )

    LaunchedEffect(state.settledPage) {
        viewModel.onPageSettled(state.settledPage) // progress write + prefetch
    }

    HorizontalPager(
        state = state,
        reverseLayout = viewModel.rightToLeft,     // manga mode = one boolean
        beyondViewportPageCount = 1,               // keep neighbors composed
    ) { page ->
        ZoomableAsyncImage(
            model = viewModel.pageRequest(page),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
        )
    }
}
```

`reverseLayout` is the entire RTL feature — the iOS guide's observation that CB8 tracks page indexes, not directions, pays off identically here: index `n` is index `n`, progress stays interoperable with the web UI.

### The page pipeline

Pages come from `GET /api/comics/:id/pages/:n` with `?width=` at device-pixel size — the same two reasons as iOS (don't decode 4000px scans; hit the server's per-width resize cache, which serves `Cache-Control: max-age=86400`):

```kotlin
class ReaderViewModel(
    val comic: ComicRecord,
    private val api: CB8Api,
    private val imageLoader: ImageLoader,
    private val serverUrl: String,
    displayMetrics: DisplayMetrics,
) : ViewModel() {
    private val pixelWidth = displayMetrics.widthPixels
    val startPage = comic.lastPage ?: 0
    val rightToLeft = false   // user setting in real code

    fun pageUrl(page: Int) =
        "$serverUrl/api/comics/${comic.id}/pages/$page?width=$pixelWidth"

    fun pageRequest(page: Int) = ImageRequest.Builder(appContext)
        .data(pageUrl(page))
        .build()

    fun onPageSettled(page: Int) {
        // Prefetch the window ahead — Coil dedupes in-flight requests,
        // so this is the whole prefetcher (CB8's shared/lru.ts role is
        // played by Coil's memory cache + the pager's viewport retention).
        viewModelScope.launch {
            for (ahead in (page + 1)..minOf(page + 3, comic.pageCount - 1)) {
                imageLoader.enqueue(
                    ImageRequest.Builder(appContext).data(pageUrl(ahead)).build())
            }
        }
        // Progress write-through on every turn — the same PUT the web UI
        // sends; the server owns the auto-complete rule.
        viewModelScope.launch {
            runCatching { api.saveProgress(comic.id, ProgressUpdate(page = page)) }
        }
    }
}
```

The iOS guide's three pipeline disciplines carry over with Android spellings:

- **Memory budget.** Android's spread of 3GB phones to 16GB tablets means the bitmap budget must be conservative *by default*: cap Coil's memory cache (`memoryCache { maxSizePercent(0.25) }`), let `?width=` keep decoded sizes screen-bounded, and request full resolution only for the currently-zoomed page. `ComponentCallbacks2.onTrimMemory` is the jetsam warning iOS never gives you — clear the memory cache when it fires.
- **Flush progress on backgrounding.** The unthrottled write-through usually suffices; if you debounce for cellular politeness, flush in `onStop` via a lifecycle observer — an unflushed final page breaks "continue on the desktop," the bug class the iOS guide flagged.
- **Decode off the main thread** is free — Coil decodes on workers — but *uploads* of huge bitmaps can still jank the first frame; `crossfade(false)` in the reader avoids paying an animation on every turn.

Reader chrome: tap-zone arbitration (center toggles chrome, edges page) via a `pointerInput` overlay that checks tap x-position; immersive mode with `WindowInsetsControllerCompat.hideSystemBars()`; a `Slider` bound to the pager with `animateScrollToPage`; hardware keys (arrows/space — and **volume keys**, an Android comic-reader tradition worth honoring) via `onKeyEvent`. Keep the screen on while reading: `FLAG_KEEP_SCREEN_ON` scoped to the reader destination only.

---

## Part 7 — EPUB and PDF

The architecture transfers from CB8 unchanged, as it did on iOS: books are fetched whole (`GET /api/comics/:id/file`), rendered client-side, and progress is a string `location` through the same progress endpoint.

### EPUB: Readium has a Kotlin toolkit too

The Readium project's [kotlin-toolkit](https://github.com/readium/kotlin-toolkit) is the Android twin of the Swift toolkit the iOS guide recommended — same architecture (publication parsing, navigator fragment, locators, theming). The decision and its caveat are identical: Readium's `Locator` JSON won't match epub.js CFIs, so **cross-client EPUB resume needs translation or a per-client-positions truce**; comics (page indexes) interoperate regardless. If byte-identical CFI compatibility with the web UI is non-negotiable, the WebView + epub.js option exists on Android exactly as Option B did on iOS — a bundled HTML page, a `@JavascriptInterface` bridge instead of `WKScriptMessageHandler`, the same inherited webview trade-offs.

Port the theme palette from `src/shared/epubTheme.ts` into Readium's theme settings so dark/sepia match the web client, and map font-size adjustment onto Readium preferences. The Google Fonts integration becomes bundled fonts, same as iOS.

### PDF: the one regression relative to iOS

PDFKit gave iOS a complete reader widget. Android's options, honestly ranked:

1. **`androidx.pdf`** (Jetpack's PDF library, building on the modernized platform renderer): an embeddable viewer fragment with search/selection on recent APIs. It is the designated future and the right default *if* its API-level floor and maturity fit your audience when you build — check its current release status; it has been moving from alpha toward stable through 2025–2026.
2. **Pdfium via a binding** (the engine Chrome uses; bindings like `pdfium-android` wrap it): full rendering fidelity, render-to-bitmap API, no built-in chrome — you wrap pages in the same Telephoto zoomable pager as comics, which for *comic-style* PDFs (scanned volumes — most of what a CB8 library holds) is actually the best reading experience of the three.
3. **`PdfRenderer`** (platform, API 21+): zero dependencies, renders pages to bitmaps, nothing else. Fine for a v1 whose PDFs are scanned comics; insufficient for text PDFs the moment users want search.

The pragmatic call for CB8's audience: route PDFs through the comic-reader pager rendering via Pdfium or `PdfRenderer` (treating each page as an image — `?width=`-style downsampling by rendering into a right-sized bitmap), and store the 0-based page index as the `location` string. The iOS guide's off-by-one warning applies verbatim: pdf.js positions are 1-based, `PdfRenderer`/Pdfium are 0-based — normalize in one place or cross-device resume drifts.

### MOBI

Same verdict as iOS: no maintained native renderer, treat as download-and-hand-off in v1 (`Intent.ACTION_VIEW` to whatever handles it), and if it ever matters, solve it server-side with a conversion path that benefits every client.

---

## Part 8 — Going Standalone: The On-Device Library

Phase 2: the local library that makes the app whole without a server. The Room schema decisions mirror the iOS guide's GRDB ones (same deliberate subset of `db/schema/create.ts`, same reasons); folder access and background work are where Android diverges, mostly favorably.

### Getting files in: SAF instead of bookmarks

Android's equivalent of the iOS document picker + security-scoped bookmark is the Storage Access Framework with persistable URI grants:

```kotlin
// Launching the tree picker
val pickFolder = registerForActivityResult(
    ActivityResultContracts.OpenDocumentTree()
) { uri: Uri? ->
    uri?.let {
        // The Android analog of a security-scoped bookmark: persist the
        // grant, then store the Uri string in Room (CB8 persists scan
        // paths in its DB the same way).
        contentResolver.takePersistableUriPermission(
            it, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        viewModel.addLibraryFolder(it)
    }
}
```

Three Android-specific realities to design around:

- **SAF traversal is slow** — `DocumentFile.listFiles()` does a content-provider round trip per directory, and naive recursion over a 5,000-file library takes minutes. Use `DocumentsContract.buildChildDocumentsUriUsingTree` with a projection of just `DOCUMENT_ID`, `DISPLAY_NAME`, `MIME_TYPE`, `SIZE`, `LAST_MODIFIED` and query each directory in one cursor pass. This is the difference between a scan that feels indexed and one that feels broken; it's the Android counterpart of the iOS guide's ImageIO-downsampling "hum vs. jetsam" point.
- **App-private storage needs no permissions at all** — files imported into `filesDir`/`getExternalFilesDir` are simply yours. Offer "import a copy" (owned) vs "index in place" (SAF reference), the same owned/referenced split as iOS, and keep CB8's README promise: removing a library item deletes the row, never the file.
- **"All files access" (`MANAGE_EXTERNAL_STORAGE`) is the tempting wrong answer.** It would make scanning trivial and Play restricts it to app categories CB8 doesn't fit; a file-manager-style permission declaration will bounce. SAF is the supported path; spend the effort on making it fast rather than on the appeal process. (For the F-Droid/sideload build flavor, this constraint relaxes — Part 12.)

### The Room schema

Same subset logic as the iOS port — library tables yes, better-auth tables no, per-user progress collapsed into the comic row:

```kotlin
@Entity(tableName = "comics",
        indices = [Index("treeUri", "documentId", unique = true)])
data class LocalComic(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val treeUri: String?,        // SAF tree the file came from (null = owned copy)
    val documentId: String?,     // stable within the tree — replaces file_path
    val relativePath: String?,   // for owned copies under filesDir
    val title: String,
    val pageCount: Int,
    val fileSize: Long,
    val dateAdded: Long,         // epoch millis; Room has no datetime affinity games
    val lastPage: Int? = null,
    val lastLocation: String? = null,
    val lastRead: Long? = null,
    val mediaType: String,       // 'comic' | 'book'
    val seriesName: String? = null,
    val volumeNumber: Double? = null,  // REAL in CB8's schema — "vol 1.5" exists
    val chapterNumber: Double? = null,
    val completed: Boolean = false,
)

@Dao
interface ComicDao {
    // The Flow return is the IPC-change-notification replacement, same as
    // GRDB's ValueObservation on iOS: scans write rows, the grid recomposes.
    @Query("""SELECT * FROM comics
              WHERE (:search IS NULL OR title LIKE '%' || :search || '%')
              ORDER BY dateAdded DESC LIMIT :limit OFFSET :offset""")
    fun page(search: String?, limit: Int, offset: Int): Flow<List<LocalComic>>

    @Query("SELECT COUNT(*) FROM comics")
    fun count(): Flow<Int>

    @Upsert suspend fun upsert(comic: LocalComic): Long
}
```

Tags, comic-tag join, and bookmarks tables port from the schema the same way the iOS guide's GRDB migration did. The two iOS departures repeat for the same reasons: thumbnails as files in `cacheDir/thumbnails/<id>.jpg` (purgeable, regenerable) instead of CB8's `cover_thumbnail BLOB`; identity as `(treeUri, documentId)` instead of `file_path`. Room's `Migration` list is the `migrations.ts` discipline (CB8 is at schema v6; start your version counting on day one). Also expose the local library through a `PagingSource` from Room (`@Query` returning `PagingSource<Int, LocalComic>`) so Part 5's grid is data-source-blind.

### Scanning with WorkManager

Here Android simply wins: a library scan is a `CoroutineWorker`, and the OS will run it to completion, in the background, with a progress notification — no `BGProcessingTask` lottery:

```kotlin
class ScanWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val folders = db.folderDao().all()
        var processed = 0
        for (folder in folders) {
            scanTree(folder.treeUri.toUri()) { file ->     // cursor-based walk
                if (file.name.hasComicExtension()) {        // .cbz/.cbr/.epub/.pdf/.mobi
                    indexFile(file)                         // parse, count pages, thumbnail
                    processed++
                    setProgress(workDataOf("processed" to processed,
                                           "currentFile" to file.name))
                }
            }
        }
        return Result.success()
    }
}
```

`setProgress` feeds a `ScanProgress`-shaped UI state (`discovered`/`processed`/`currentFile` — keep CB8's field names from `types.ts`). Run import-triggered scans as expedited work for immediacy; schedule periodic re-scans of referenced folders with `PeriodicWorkRequest` — which is CB8's `folderScheduler.ts` (auto-rescan interval) reborn with OS backing. Port `seriesParser.ts` alongside the scanner, as on iOS; it's regex work with a test file.

Thumbnails: `BitmapFactory.Options` two-pass decode — bounds first, then `inSampleSize` to land near 480px — is the `sharp`-replacement; compress to JPEG ~80 into the cache dir. PDF covers render page 0 via `PdfRenderer` into a right-sized bitmap (the whole of `pdfCoverExtractor.ts`); EPUB covers come from Readium's publication metadata or an OPF parse over the zip (an EPUB is a zip). Cover *selection* for archives is `coverSelection.ts` — port, don't improvise, or local covers diverge from server covers for the same file.

---

## Part 9 — Archives and the Shared-Logic Ports

Replacing `archiveLoader.ts` + node-7z. The contract from `src/shared/types.ts` stands: an archive opens to natural-sorted, image-filtered entries with random page access.

### CBZ: the JDK already ships it

No dependency needed — `java.util.zip.ZipFile` reads the central directory and gives random per-entry access:

```kotlin
class ComicArchive private constructor(
    private val zip: ZipFile,
    /** Sorted, filtered image entries — index n IS page n, the same
     *  invariant the server's ArchiveLoader maintains. */
    val pages: List<ZipEntry>,
) : Closeable {

    companion object {
        fun open(file: File): ComicArchive {
            val zip = ZipFile(file)
            val pages = zip.entries().asSequence()
                .filter { !it.isDirectory && isImageFile(it.name) }
                .sortedWith { a, b -> naturalCompare(a.name, b.name) }
                .toList()
            return ComicArchive(zip, pages)
        }
    }

    val pageCount get() = pages.size

    fun pageData(index: Int): ByteArray =
        zip.getInputStream(pages[index]).use { it.readBytes() }

    override fun close() = zip.close()
}
```

One SAF wrinkle: `ZipFile` wants a `File`, but SAF hands you a `Uri`. For *owned* copies you have a real path; for *referenced* files, get a file descriptor (`contentResolver.openFileDescriptor(uri, "r")`) and use a zip reader that accepts FDs/channels (Apache Commons Compress's `ZipFile` takes a `SeekableByteChannel`), or fall back to copying into the cache dir on first open for files on providers that can't seek. Keep open archives in a small LRU keyed by comic id — `archiveCache.ts`'s pattern, ported via your `lru.ts` port.

### CBR: more options than iOS, same conclusion shape

- **junrar** (pure Java/Kotlin, Apache-licensed): zero NDK, handles RAR4 — **but not RAR5**, and RAR5 has been WinRAR's default since 2013, so modern CBRs will fail. Fine as a first tier, not a solution.
- **libarchive via NDK**: reads RAR4 and most RAR5, BSD-licensed (F-Droid-friendly), but you own the JNI wrapper and per-ABI builds.
- **The bundled-7z move (Android-only option):** ship `7zz` per-ABI in `jniLibs` as `lib7zz.so`, exec it from `nativeLibraryDir` with output to your cache dir. This is the closest possible port of CB8's actual architecture — it *is* node-7z's design, legally re-homed — and it genuinely works. Costs: ~6MB across ABIs, process-spawn latency per archive open (mitigate by extracting whole archives once into cache rather than per page), and the 7-Zip RAR codec's licensing rider (7-Zip is LGPL but its RAR extraction code carries the unrar license clause — same acknowledgement obligations as UnrarKit on iOS, and a problem for an F-Droid flavor).
- **Convert at the edge**: detect CBR on import, repack to CBZ. Same trade as iOS; strongest in combination ("junrar for RAR4; offer convert-via-libarchive for RAR5").

Recommendation: libarchive via a maintained binding if you want one path that handles both RAR generations in-process; junrar + convert-on-import if you want to stay NDK-free. Reserve the bundled-7z trick for the sideload flavor where APK size and licensing review matter less. As on iOS, hide the choice behind the `ComicArchive` interface so the reader stays format-blind — and remember Phase 1 sidesteps all of this: server libraries deliver decoded images over `/pages/:n`, CBR included.

### Image format coverage

CB8's `imageFilter.ts` set is `jpg jpeg png webp gif bmp jxl avif`. Android platform decoding: JPEG/PNG/WebP/GIF/BMP always; **AVIF from API 31**; **JPEG XL not at all** (as of current API levels). Coil + a libjxl-JNI decoder plugs the JXL gap if your library actually contains JXL pages (CB8 bundles `@jsquash/jxl` for the same reason — the web platform lacks JXL too, which is a hint about how often this matters: it does, for some manga archives). Keep the extension in the filter either way — a page you can't decode should surface as a broken-page error, not silently vanish from the page count, or page indexes drift from the server's and progress interop breaks. That invariant — **filter by the shared extension list, not by what the device can decode** — is exactly the kind of subtle contract the shared-spec porting discipline exists to protect.

### Porting `naturalSort.ts`

Same spec, same fidelity stakes as the iOS port (an "almost right" comparator misorders pages 2/10). Kotlin port:

```kotlin
/**
 * Port of src/shared/naturalSort.ts — behavior-identical, including
 * numeric-before-text at the same position and the "01" vs "1"
 * equal-number fall-through.
 */
fun naturalCompare(a: String, b: String): Int {
    fun chunks(s: String): List<String> {
        val out = ArrayList<String>()
        var i = 0
        while (i < s.length) {
            val digit = s[i].isDigit()
            var j = i
            while (j < s.length && s[j].isDigit() == digit) j++
            out.add(s.substring(i, j))
            i = j
        }
        return out
    }

    val ca = chunks(a); val cb = chunks(b)
    for (i in 0 until minOf(ca.size, cb.size)) {
        val x = ca[i]; val y = cb[i]
        val xNum = x[0].isDigit(); val yNum = y[0].isDigit()
        when {
            xNum && yNum -> {
                val dx = x.toBigIntegerOrNull() ?: BigInteger.ZERO
                val dy = y.toBigIntegerOrNull() ?: BigInteger.ZERO
                val cmp = dx.compareTo(dy)
                if (cmp != 0) return cmp
                // numerically equal ("01" vs "1") — fall through
            }
            xNum != yNum -> return if (xNum) -1 else 1   // numbers before text
            else -> {
                val cmp = x.lowercase().compareTo(y.lowercase())
                if (cmp != 0) return cmp
            }
        }
    }
    return ca.size - cb.size   // shorter first on full tie
}
```

(`BigInteger` sidesteps overflow on absurd digit runs — the TS original's `parseInt` saturates differently, but both agree on every filename that fits in a `Long`; add the pathological case to the tests if you care.) The locale caveat from the iOS guide applies identically: the original's `localeCompare` vs. this port's plain lowercase comparison agree on ASCII and can diverge on non-ASCII titles — if web/Android page-order parity on Japanese filenames matters, use `Collator` pinned to the same locale and add the test.

`imageFilter.ts` is the same one-liner (`setOf("jpg","jpeg","png","webp","gif","bmp","jxl","avif")` against the lowercased final extension), and `lru.ts` ports to a `LinkedHashMap` with `accessOrder = true` and a size-bounded `removeEldestEntry` — a dozen lines, kept honest by its ported test file.

---

## Part 10 — Progress Sync and Offline

The policy layer is platform-independent and the iOS guide's Part 10 stands word-for-word: server is truth while online (write-through per page turn); offline writes queue locally and replay last-write-wins on reconnect, guarded against stale replays by skipping queued writes older than the server's `lastRead`; local comics have no sync target; and **do not** mirror whole libraries bidirectionally — the server is already the multi-device coordinator, and a reader app should not accidentally become a distributed system.

The Android mechanics are pleasantly boring:

- **Downloads** (`GET /api/comics/:id/file`) run as WorkManager jobs with a foreground-service notification for big files — survives process death, retries with backoff, constrainable to unmetered networks (`Constraints.Builder().setRequiredNetworkType(NetworkType.UNMETERED)` for an "only on Wi-Fi" setting, which a comics app should ship — archives are hundreds of MB and users have caps). Store under `getExternalFilesDir("offline/<serverId>/")`: app-scoped (auto-cleaned on uninstall), user-visible via USB, no permissions. A `downloads` Room table maps `(serverUrl, remoteId) → localPath`; the reader checks it first and serves pages from `ComicArchive` or `/pages/:n` behind one interface — the same two-sources-one-protocol shape as iOS, which is itself the same shape as CB8 serving identical UIs from Electron and Docker.
- **The progress replay queue** is a `pendingProgress` table plus a network-constrained worker with `ExistingWorkPolicy.APPEND`. WorkManager's persistence means the queue drains even if the user doesn't reopen the app — a small real win over the iOS version, where replay waits for a launch.

---

## Part 11 — Testing: Porting the Vitest Suite

The strategy is the iOS guide's Part 11 with better ergonomics: the `shared/` ports and their transcribed tests run as **plain JVM unit tests** — no emulator, no Robolectric, milliseconds per suite — because the ports are pure Kotlin with no Android imports (keep them that way; it's also what makes them KMP-extractable later).

```kotlin
// Ported from src/shared/naturalSort.test.ts
class NaturalSortTest {
    @Test fun `sorts page2 before page10`() {
        assertTrue(naturalCompare("page2.jpg", "page10.jpg") < 0)
    }

    @Test fun `numbers sort before text at the same position`() {
        assertTrue(naturalCompare("2.jpg", "cover.jpg") < 0)
    }

    @ParameterizedTest
    @MethodSource("orderingCases")
    fun `orders like the server`(input: List<String>, expected: List<String>) {
        assertEquals(expected, input.sortedWith(::naturalCompare))
    }

    companion object {
        @JvmStatic fun orderingCases() = listOf(
            arguments(listOf("page1.jpg", "page10.jpg", "page2.jpg"),
                      listOf("page1.jpg", "page2.jpg", "page10.jpg")),
            arguments(listOf("ch1/p1.png", "ch1/p10.png", "ch1/p2.png"),
                      listOf("ch1/p1.png", "ch1/p2.png", "ch1/p10.png")),
        )
    }
}
```

Where CB8 uses fast-check, Android has a *real* equivalent: kotest's property testing. Generate filename lists and assert the comparator's contract (totality, antisymmetry, transitivity, integer-aware ordering) — a closer port of the fast-check suites than the iOS guide's parameterized approximation.

Beyond the ports, the same three layers as iOS, translated: **API client tests** against OkHttp's `MockWebServer` (made by the OkHttp team; enqueue captured CB8 JSON fixtures, assert models decode — refreshing fixtures *is* the upstream-compatibility audit, and `ignoreUnknownKeys` gets exercised here); **archive tests** with fixtures the test builds itself (`ZipOutputStream` a 4-page CBZ with a non-image entry and misordered names, prove filtering and ordering end-to-end through `ComicArchive`); **reader-logic tests** on `ReaderViewModel` with a fake api (opening at `lastPage = 41` requests pages 41–44; progress PUTs fire per settled page) — plain coroutine tests with `runTest`, no UI. Room DAO tests and any Compose UI tests run instrumented, but notice the design pressure: everything this guide put in `shared/` and the view models stays JVM-testable, which is the same "test the math, not the pixels" line the iOS guide drew.

---

## Part 12 — Distribution: Play, F-Droid, and the Sideload Channel

On iOS, distribution was a compliance chapter. On Android it's a *strategy* chapter, because CB8's audience — people who run Docker containers on NASes — overlaps heavily with people who install APKs from GitHub Releases, which CB8 already publishes for desktop.

**Google Play** is the mainstream channel: app signing by Google, AAB upload, the Data Safety form (truthful answers are easy — the app talks only to user-configured servers; declare what you store locally), and a review that is faster and less adversarial than Apple's for this category. The iOS guide's review-prep list translates thinner: no demo-server requirement in practice (but having one ready never hurts), cleartext policy documented in the listing notes if you went with option (a) from Part 4, and the unrar/7-Zip license acknowledged in-app if you ship that codec.

**Direct APK via GitHub Releases** is the channel that matches CB8's existing release culture 1:1 — the desktop app ships there; the Android APK can ride the same release pipeline (a `gradle assembleRelease` job next to the Forge makers in CI, signed with a keystore in repo secrets). Users get it with one toggle ("install unknown apps"); you owe them an update path — at minimum a "check GitHub releases" tap, or wire in a self-updater library. This channel has no content police and no codec-license anxiety; it's where the bundled-7z flavor can live.

**F-Droid** fits the project's self-hosted ethos and its MIT license, with one sharp constraint: builds must be reproducible from FOSS sources, which disqualifies the unrar-licensed RAR codec paths. The clean answer is build flavors — `fdroid` (libarchive-only CBR, no proprietary bits) and `full` (everything) — declared once in Gradle and diverging only in the `archives/` dependency set. Decide this *before* the RAR choice in Part 9 hardens, because retrofitting flavor separation around a license is miserable.

Mechanical notes that round out the release: `minifyEnabled` with R8 plus keep-rules for kotlinx-serialization models; per-ABI splits if you ship NDK bits (libarchive/Pdfium) to keep the APK lean; and a `network_security_config` audit before each release — the debug-build cleartext allowances must not leak into release.

---

## Appendix — WebView Wrappers and the On-Device Node Experiment

### The WebView wrapper (the shippable stopgap)

Same role as the iOS appendix: a weekend proof, or a stopgap while Phase 1 bakes — and on Android, a lower-risk one to actually publish.

```kotlin
@Composable
fun ServerWebView(url: String) {
    AndroidView(factory = { ctx ->
        WebView(ctx).apply {
            settings.javaScriptEnabled = true          // the SPA requires it
            settings.domStorageEnabled = true           // zustand persists here
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(
                    view: WebView, request: WebResourceRequest, error: WebResourceError
                ) { /* swap in a native retry screen — not WebView's error page */ }
            }
            loadUrl(url)
        }
    })
}
```

The session cookie persists in the WebView's own cookie store (`CookieManager.getInstance()` — flush on pause), so login survives restarts with no work. The polish list from the iOS appendix applies: native unreachable-server screen, insets that let the reader go immersive, and don't double-handle pinch (the SPA owns zoom). Capacitor works identically to the iOS description — bundle `dist/web`, point it at a configurable server URL, inherit the CORS/`SameSite` homework upstream — and on Android it additionally clears Play review with little drama.

### The on-device Node experiment (the instructive dead end)

Because Android removes iOS's hard blockers, it's worth being precise about why this still loses. The recipe that *works*: nodejs-mobile as the runtime (full V8, JIT intact); CB8's `standalone.mjs` bundle as the payload; `7zz` shipped per-ABI in `jniLibs` as `lib7zz.so` with `CB8_SEVENZIP_PATH` pointed at `nativeLibraryDir` (CB8's own env-var escape hatch, doing exactly its job); `better-sqlite3` and `sharp` cross-compiled per ABI — this step is days, not hours, and recurs on every upstream bump; the server bound to `127.0.0.1:8008` inside the app's network namespace; a WebView on top. You will see the real CB8 web UI served by the real CB8 server from your pocket, scanning a folder of CBZs. It is a deeply satisfying demo.

Then the model breaks down: Android kills the process under memory pressure and restores your Activity *without* the server (every screen needs a "wait for backend" state); a foreground service keeps it alive at the cost of a permanent notification and battery-usage flags; scans that WorkManager would run politely now contend with the foreground app for the process's resources; and the maintenance tail — four-ABI native-addon builds against a community Node fork — is the kind of debt that ends hobby ports. The experiment's real value is what it proves: every piece of CB8 that *can* run on Android this way is a piece whose native replacement (Room, ZipFile, BitmapFactory) is *smaller* than the scaffolding needed to avoid replacing it.

---

## Closing: one codebase, three platforms, two ports

The condensed sequence mirrors the iOS checklist — read the routes; ship the server client (login → grid → reader → progress); pick the PDF/EPUB trade-offs; port `src/shared/` with its tests; build the SAF + Room local library; choose the CBR path with distribution flavors in mind; wire WorkManager downloads and the stale-guarded progress replay; then pick channels (Play and GitHub Releases, F-Droid if the flavors are clean).

If both this port and the iOS one become real, the duplication you'll feel first is exactly the code this guide and its sibling kept platform-free: the API models, the query types, the progress policy, the `shared/` ports and their tests. That set has a name — a **Kotlin Multiplatform core** consumed by the Compose app directly and by the SwiftUI app as a framework — and the migration is mechanical *because* both guides kept those layers free of platform imports. Whether that consolidation is worth it for two hobby clients is a judgment call; that it remains *available* is a direct payoff of porting CB8's `src/shared/` discipline instead of just its features. CB8 made its GUI portable by putting HTTP between the interface and the engine; the mobile ports stay maintainable by the same move, one layer down.

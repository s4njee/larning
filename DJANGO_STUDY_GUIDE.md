# Django Mastery Study Guide

A comprehensive, job-focused guide to mastering Django. Each section builds on the previous one. Practice by building real features, not toy examples.

---

## Phase 1: Core Foundations

### 1.1 Project Structure & Configuration

- **`settings.py` architecture**: Split into `base.py`, `development.py`, `production.py`, `testing.py` using a settings package
  - Put shared defaults in `base.py`, then import from it in environment-specific modules so dev, test, and prod can diverge without duplicating everything.
  - Keep environment-specific concerns isolated: debug toolbar, console email backend, and SQLite belong in development settings; hardened security, real caches, and production databases belong in production settings.
  - Switch between settings modules with `DJANGO_SETTINGS_MODULE` or `--settings`; this is what makes a settings package practical in real deployments and CI.
  - Learn the startup flow: Django imports one settings module, then builds app registry, middleware, templates, and database connections from it.
  - References: [Django settings](https://docs.djangoproject.com/en/stable/topics/settings/), [The `django-admin` utility and `DJANGO_SETTINGS_MODULE`](https://docs.djangoproject.com/en/stable/topics/settings/#designating-the-settings)
- **Environment variables**: Use `django-environ` or `python-decouple` to keep secrets out of code
  - Treat secrets and deploy-specific values as external configuration: `SECRET_KEY`, database credentials, cache URLs, allowed hosts, email credentials, and third-party API keys should not be committed to the repo.
  - Use helper libraries to parse booleans, lists, and database URLs safely, but still understand the final Django setting each value feeds into.
  - Give safe local defaults only where appropriate; production-only values should usually fail fast if missing instead of silently falling back to insecure defaults.
  - Pair this with `.env.example` files so teammates know what must be defined without exposing real secrets.
  - References: [Deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/), [`SECRET_KEY` guidance](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/#secret-key), [`django-environ` docs](https://django-environ.readthedocs.io/), [`python-decouple` package](https://pypi.org/project/python-decouple/)
- **`ALLOWED_HOSTS`**, **`DEBUG`**, **`SECRET_KEY`** — understand what each controls and the security implications
  - `DEBUG` controls detailed error pages and extra debugging behavior; it is useful locally but dangerous in production because it can expose settings, code paths, and runtime details.
  - `ALLOWED_HOSTS` is the host-header allowlist Django checks for incoming requests; when `DEBUG=False`, a bad value here can either block legitimate traffic or leave host validation too loose.
  - `SECRET_KEY` underpins Django signing and security-sensitive features such as session data, CSRF-related signing, and password reset tokens, so it must be random, private, and not shared across environments.
  - Know the operational rule: production means `DEBUG=False`, a correctly scoped `ALLOWED_HOSTS`, and a secret loaded from the environment or another private source.
  - Run `python manage.py check --deploy --settings=...` before deploys to catch obvious configuration mistakes early.
  - References: [`DEBUG`](https://docs.djangoproject.com/en/stable/ref/settings/#debug), [`ALLOWED_HOSTS`](https://docs.djangoproject.com/en/stable/ref/settings/#allowed-hosts), [`SECRET_KEY`](https://docs.djangoproject.com/en/stable/ref/settings/#secret-key), [Deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- **`INSTALLED_APPS` ordering** — why it matters (template resolution, signal loading, admin autodiscovery)
  - Template lookup can depend on app order when `APP_DIRS=True` or the app-directories loader is used; if two apps ship the same template path, Django uses the first match it finds.
  - This is why overriding admin templates requires your app to appear before `django.contrib.admin` in `INSTALLED_APPS`.
  - App initialization also happens as Django populates the app registry, and signal registration is commonly done in `AppConfig.ready()`, so you should understand app loading rather than treating `INSTALLED_APPS` as a random list.
  - Keep the list intentional and readable: a common convention is Django contrib apps first, third-party apps next, local apps last, with deliberate exceptions only when you need template overrides or similar behavior.
  - References: [Applications and `AppConfig.ready()`](https://docs.djangoproject.com/en/stable/ref/applications/#django.apps.AppConfig.ready), [Template loading from app directories](https://docs.djangoproject.com/en/stable/ref/templates/api/#django.template.loaders.app_directories.Loader), [Signals](https://docs.djangoproject.com/en/stable/topics/signals/)
- **`manage.py` vs `django-admin`** — when to use each
  - `manage.py` is the project-local entry point Django creates for you; it sets up your project’s default settings module automatically, so it is the normal choice for everyday work inside one codebase.
  - `django-admin` is the global administrative command; it is more useful when you are outside a specific project, generating a new project, or explicitly choosing a settings module with `--settings`.
  - In practice, most examples work with either one, but `manage.py` is safer for project-specific tasks because it already knows which settings to load.
  - Also recognize `python -m django` as an equivalent command style that can be handy in some environments.
  - References: [`django-admin` and `manage.py`](https://docs.djangoproject.com/en/stable/ref/django-admin/)
- **`ASGI` vs `WSGI`** — what they are, when you need ASGI
  - `WSGI` is the traditional Python web-server interface and is still a solid default for standard synchronous Django apps.
  - `ASGI` is the newer async-capable interface and is required when you need long-lived connections such as WebSockets, or when you want Django’s async request stack to run without a sync adapter in front of it.
  - Django creates both `wsgi.py` and `asgi.py` in new projects; the file alone does not change behavior, the deployment server you choose does.
  - Use ASGI servers such as Uvicorn, Daphne, or Hypercorn when you need async features; otherwise a WSGI deployment is often simpler and entirely acceptable.
  - References: [How to deploy with WSGI](https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/), [How to deploy with ASGI](https://docs.djangoproject.com/en/stable/howto/deployment/asgi/), [How to deploy Django](https://docs.djangoproject.com/en/stable/howto/deployment/)

**Practice**: Set up a project with split settings, environment variable configuration, and a `.env` file. Deploy it to a staging server where `DEBUG=False`.

---

### 1.2 URL Routing

- **`path()` vs `re_path()`** — use `path()` by default, `re_path()` only when you need regex
  - `path()` is the normal choice because it is easier to read, easier to maintain, and covers most application routes through built-in converters like `int`, `slug`, and `uuid`.
  - `re_path()` is for cases where you genuinely need regular expressions, such as legacy URL compatibility or a pattern that cannot be expressed cleanly with path converters.
  - Prefer the simplest pattern that communicates intent; if a route can be written with `path()`, using regex usually adds complexity without value.
  - Be able to read both styles because many existing Django codebases still contain older regex-based URLconfs.
  - References: [URL dispatcher](https://docs.djangoproject.com/en/stable/topics/http/urls/), [`path()`](https://docs.djangoproject.com/en/stable/ref/urls/#django.urls.path), [`re_path()`](https://docs.djangoproject.com/en/stable/ref/urls/#django.urls.re_path)
- **URL namespacing**: `app_name` in URLconfs, `namespace` in `include()`
  - Namespacing prevents collisions when different apps use the same route names, such as multiple apps each having a `detail` or `list` view.
  - Set `app_name` inside an app’s URLconf so its named URLs can live in an application namespace like `blog:post_detail`.
  - Use `namespace=` in `include()` when you need instance namespaces, which matters when you mount the same URLconf more than once.
  - This is what makes `reverse()` and `{% url %}` reliable in larger projects instead of depending on globally unique names by convention alone.
  - References: [URL namespaces](https://docs.djangoproject.com/en/stable/topics/http/urls/#url-namespaces), [`include()`](https://docs.djangoproject.com/en/stable/ref/urls/#django.urls.include)
- **`reverse()` and `reverse_lazy()`** — always use named URLs, never hardcode paths
  - `reverse()` resolves a URL name into a path at runtime and should be your default when you need a URL in Python code.
  - `reverse_lazy()` delays resolution until the value is actually needed, which is important in places that load at import time, such as class attributes in CBVs, decorators, and some settings-like module code.
  - Hardcoded paths create fragile coupling; renaming a route should require changing one URL pattern, not hunting string literals across views, templates, redirects, and tests.
  - Make URL names part of your public internal API: views redirect to names, templates link with `{% url %}`, and tests assert against reversed URLs.
  - References: [`reverse()`](https://docs.djangoproject.com/en/stable/ref/urlresolvers/#reverse), [`reverse_lazy()`](https://docs.djangoproject.com/en/stable/ref/urlresolvers/#reverse-lazy), [Naming URL patterns](https://docs.djangoproject.com/en/stable/topics/http/urls/#naming-url-patterns)
- **URL converters**: `<int:pk>`, `<slug:slug>`, `<uuid:uuid>`, custom converters
  - Converters validate and parse path segments before your view runs, which keeps URL patterns expressive and removes repetitive parsing logic from view code.
  - Use built-in converters for common cases: integer primary keys, slugs for readable URLs, and UUIDs when identifiers should not be sequential.
  - Custom converters are useful when your domain has a specific identifier format that should be enforced at the routing layer.
  - Understand that converters shape both matching and reversing: the pattern affects which requests reach the view and what values `reverse()` can generate.
  - References: [Path converters](https://docs.djangoproject.com/en/stable/topics/http/urls/#path-converters), [`register_converter()`](https://docs.djangoproject.com/en/stable/ref/urls/#django.urls.register_converter)
- **Nested includes**: Organize URLs per app, include them in the root URLconf
  - Large projects stay maintainable when each app owns its own URLconf and the root `urls.py` assembles them with `include()`.
  - This keeps routing changes local to the app that owns the feature instead of turning the project URLconf into a giant flat file.
  - Nested includes also support clean prefixes such as `blog/`, `albums/`, or `api/v1/`, which makes route ownership easier to understand.
  - Learn the request flow: Django starts at the root URLconf, follows includes recursively, and stops at the first matching final pattern.
  - References: [Including other URLconfs](https://docs.djangoproject.com/en/stable/topics/http/urls/#including-other-urlconfs), [`include()`](https://docs.djangoproject.com/en/stable/ref/urls/#django.urls.include)
- **Trailing slash convention** and `APPEND_SLASH` setting
  - Django projects often follow a consistent trailing-slash style, and consistency matters more than the specific choice because it affects links, redirects, SEO behavior, and API expectations.
  - `APPEND_SLASH=True` works with `CommonMiddleware` to redirect slashless requests to a slash-ending URL when no matching pattern is found and a slash-appended version does match.
  - This behavior is convenient for classic server-rendered sites, but you should understand the redirect cost and be deliberate when designing APIs, where slash conventions are often stricter.
  - Pick a convention early, keep it consistent across your URLconfs, and know how middleware affects requests that nearly match.
  - References: [`APPEND_SLASH`](https://docs.djangoproject.com/en/stable/ref/settings/#append-slash), [`CommonMiddleware`](https://docs.djangoproject.com/en/stable/ref/middleware/#django.middleware.common.CommonMiddleware), [URL dispatcher](https://docs.djangoproject.com/en/stable/topics/http/urls/)

**Practice**: Build a multi-app project where every URL is named, namespaced, and reversible. Write a test that verifies every named URL resolves correctly.

---

### 1.3 Models & the ORM

#### Schema Design
- **Field types**: `CharField`, `TextField`, `IntegerField`, `DecimalField`, `DateTimeField`, `JSONField`, `UUIDField`, `FileField`, `ImageField`
  - Choose field types based on domain semantics, not just storage shape. `DecimalField` is for money, `UUIDField` is for opaque identifiers, and `DateTimeField` implies timezone decisions.
  - Understand the database behavior behind each field, especially precision, indexing support, nullability, and whether the field maps cleanly across database backends.
  - File-oriented fields add storage concerns, not just schema concerns. They imply upload handling, storage backends, media serving, and cleanup policies.
  - References: [Model field reference](https://docs.djangoproject.com/en/stable/ref/models/fields/), [Model field types](https://docs.djangoproject.com/en/stable/topics/db/models/)
- **Field options**: `null`, `blank`, `default`, `choices`, `unique`, `db_index`, `validators`, `help_text`
  - Field options define both database constraints and form/admin behavior, so a single option can affect migrations, validation, and UI rendering.
  - Treat `unique`, `db_index`, and constraints as part of schema design, not convenience flags. They change data guarantees and query performance.
  - `validators`, `choices`, and `help_text` improve correctness close to the model layer and make forms/admin interfaces more self-documenting.
  - References: [Field options](https://docs.djangoproject.com/en/stable/ref/models/fields/#field-options), [Validators](https://docs.djangoproject.com/en/stable/ref/validators/)
- **`null=True` vs `blank=True`** — `null` is database-level, `blank` is validation-level. For string fields, prefer `blank=True` with `default=""` over `null=True`
  - `null` decides whether the database stores `NULL`; `blank` decides whether Django validation allows an empty value.
  - For string fields, mixing empty string and `NULL` often creates two “empty” states that complicate filters, uniqueness rules, and application logic.
  - Make the distinction explicit in your head: forms care about `blank`, the database cares about `null`, and the cleanest model design minimizes ambiguous states.
  - References: [`null`](https://docs.djangoproject.com/en/stable/ref/models/fields/#null), [`blank`](https://docs.djangoproject.com/en/stable/ref/models/fields/#blank)
- **Primary keys**: Default auto-incrementing `id` vs `UUIDField(primary_key=True)` — tradeoffs for each
  - Auto-incrementing integer keys are compact, fast to index, and easy to debug, which is why they remain a strong default.
  - UUIDs are useful when you want non-sequential identifiers, easier data merging across systems, or less guessable public IDs.
  - The tradeoff is operational: UUIDs are larger, noisier in URLs and logs, and can affect index locality depending on generation strategy.
  - References: [Automatic primary key fields](https://docs.djangoproject.com/en/stable/topics/db/models/#automatic-primary-key-fields), [`UUIDField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#uuidfield)
- **Abstract base classes** vs **multi-table inheritance** vs **proxy models**
  - Abstract: shared fields, no extra table, use this 90% of the time
  - Multi-table: separate tables with implicit `OneToOneField`, rarely what you want
  - Proxy: same table, different Python behavior (different default manager, different methods)
  - Use abstract base classes when multiple models share data and behavior but should stay separate database entities.
  - Multi-table inheritance is usually expensive and surprising because every query can involve joins you did not intend.
  - Proxy models are useful when you need alternate admin behavior, query defaults, or model methods without changing the underlying schema.
  - References: [Model inheritance](https://docs.djangoproject.com/en/stable/topics/db/models/#model-inheritance), [Proxy models](https://docs.djangoproject.com/en/stable/topics/db/models/#proxy-models)
- **`Meta` options**: `ordering`, `unique_together` / `UniqueConstraint`, `indexes`, `verbose_name`, `db_table`, `constraints`
  - `Meta` is where model-level policy lives: default sort order, database naming, integrity rules, and indexing strategy.
  - Prefer modern `UniqueConstraint` and explicit `constraints` over older `unique_together` patterns for clarity and flexibility.
  - Treat indexes and constraints as first-class design decisions. They encode assumptions about query patterns and data invariants.
  - References: [Model `Meta` options](https://docs.djangoproject.com/en/stable/ref/models/options/), [Constraints reference](https://docs.djangoproject.com/en/stable/ref/models/constraints/), [Indexes reference](https://docs.djangoproject.com/en/stable/ref/models/indexes/)

#### Relationships
- **`ForeignKey`**: `on_delete` options (`CASCADE`, `PROTECT`, `SET_NULL`, `SET_DEFAULT`, `DO_NOTHING`). Understand when to use each
  - A `ForeignKey` defines ownership or reference semantics, so `on_delete` is a business rule, not just a technical detail.
  - `CASCADE` is appropriate when child rows have no meaning without the parent; `PROTECT` is appropriate when history or accounting records must survive.
  - Choose deletion behavior intentionally because it affects admin usability, data retention, and operational safety.
  - References: [`ForeignKey`](https://docs.djangoproject.com/en/stable/ref/models/fields/#foreignkey), [`on_delete`](https://docs.djangoproject.com/en/stable/ref/models/fields/#django.db.models.ForeignKey.on_delete)
- **`ManyToManyField`**: With and without `through` models for extra data on the relationship
  - Use a plain `ManyToManyField` when the relationship is just membership. Use a `through` model when the relationship itself has attributes like role, ordering, timestamps, or status.
  - `through` models often turn an initially simple design into a more explicit and more useful domain model.
  - Be comfortable querying both sides of the relationship and understanding the intermediate table Django creates or uses.
  - References: [`ManyToManyField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#manytomanyfield), [Extra fields on many-to-many relationships](https://docs.djangoproject.com/en/stable/topics/db/models/#extra-fields-on-many-to-many-relationships)
- **`OneToOneField`**: Profile pattern, extending the User model
  - A `OneToOneField` is effectively a unique foreign key and is often used to split optional or domain-specific data away from a core model.
  - The classic example is a user profile, but for authentication-heavy apps, a custom user model is usually the better starting point.
  - Use one-to-one relationships when two records truly have a one-to-one lifecycle, not just because the fields feel logically grouped.
  - References: [`OneToOneField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#onetoonfield), [Customizing authentication](https://docs.djangoproject.com/en/stable/topics/auth/customizing/)
- **`related_name`**: Always set it explicitly. `related_name="+"` to disable reverse relation
  - Explicit reverse names make your API readable and stable, especially in larger codebases where implicit names become hard to remember.
  - Good reverse names communicate cardinality and meaning, such as `posts`, `comments`, or `memberships`, instead of whatever Django inferred.
  - Disable the reverse relation only when you are sure the reverse access path would be confusing or unused.
  - References: [`related_name`](https://docs.djangoproject.com/en/stable/ref/models/fields/#django.db.models.ForeignKey.related_name)
- **Self-referential relationships**: Tree structures, follower/following patterns
  - Self-relations model graphs inside a single table, which is useful for hierarchies, recommendations, and social relationships.
  - Decide whether the relation is directional and whether cycles are allowed; those are domain rules Django will not decide for you.
  - Tree-like data often needs more than a foreign key once depth, ordering, and subtree queries matter, so watch complexity early.
  - References: [Recursive relationships](https://docs.djangoproject.com/en/stable/ref/models/fields/#foreignkey), [Model relationships](https://docs.djangoproject.com/en/stable/topics/db/examples/many_to_one/)

#### QuerySet API (Deep Dive)
- **Lazy evaluation**: QuerySets don't hit the database until iterated, sliced, or evaluated
  - A `QuerySet` is a description of a query until evaluation happens, which is why you can chain operations cheaply.
  - Learn the common evaluation triggers: iteration, `list()`, `len()`, `bool()`, slicing with step, and serialization.
  - This matters for performance because the same-looking code can issue one query or many depending on when evaluation occurs.
  - References: [QuerySets are lazy](https://docs.djangoproject.com/en/stable/topics/db/queries/#querysets-are-lazy)
- **Chaining**: `.filter()`, `.exclude()`, `.order_by()`, `.distinct()`
  - QuerySet methods return new querysets, which makes filtering composable and keeps query logic readable.
  - Chaining is most powerful when you keep filters small and domain-specific, then combine them rather than writing giant one-off queries.
  - Be aware that ordering and distinctness interact differently across database backends and can affect query plans.
  - References: [Making queries](https://docs.djangoproject.com/en/stable/topics/db/queries/), [QuerySet API reference](https://docs.djangoproject.com/en/stable/ref/models/querysets/)
- **Lookups**: `__exact`, `__iexact`, `__contains`, `__icontains`, `__in`, `__gt`, `__gte`, `__lt`, `__lte`, `__startswith`, `__endswith`, `__range`, `__isnull`, `__date`, `__year`
  - Lookups are Django’s vocabulary for translating Python expressions into SQL predicates.
  - Mastering common lookups makes most application queries straightforward without dropping to raw SQL.
  - Also learn backend-specific behavior around case sensitivity, collations, and date extraction so you know when a lookup is convenient versus expensive.
  - References: [Field lookups](https://docs.djangoproject.com/en/stable/topics/db/queries/#field-lookups), [Lookup reference](https://docs.djangoproject.com/en/stable/ref/models/querysets/)
- **Spanning relationships**: `comment__post__author__username="sanjee"` — understand the JOINs this generates
  - Double-underscore traversal lets you filter across relationships declaratively, but every traversal can translate into joins.
  - You should be able to reason about which tables are involved and whether the query will multiply rows or require `distinct()`.
  - Complex traversal is powerful, but if you cannot explain the SQL shape, you are likely to miss performance or correctness issues.
  - References: [Lookups spanning relationships](https://docs.djangoproject.com/en/stable/topics/db/queries/#lookups-that-span-relationships)
- **`Q` objects**: Complex queries with `|` (OR), `&` (AND), `~` (NOT)
  - `Q` objects let you express boolean logic that would be awkward or impossible with keyword arguments alone.
  - Use them when the query structure itself is dynamic, such as building optional filters from user input.
  - They are also the foundation for readable search code and reusable query composition.
  - References: [Complex lookups with `Q`](https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects)
- **`F` expressions**: Reference model fields in queries. `Entry.objects.filter(rating__gt=F('number_of_comments'))`. Use for atomic updates: `Entry.objects.update(views=F('views') + 1)`
  - `F` expressions shift work into the database and avoid race conditions that happen when you read, modify, and save in Python.
  - They are especially important for counters, comparisons between columns, and expression-based updates.
  - Think of `F` as a way to ask the database to compute against existing row values safely.
  - References: [`F()` expressions](https://docs.djangoproject.com/en/stable/ref/models/expressions/#f-expressions)
- **`Subquery` and `OuterRef`**: Correlated subqueries for complex filtering
  - These tools let you express “for each row, compare against another query” patterns without leaving the ORM.
  - They are useful when joins would overcomplicate the query or when you need a scalar value from a related filtered subset.
  - Use them deliberately; they are powerful but harder to read than ordinary queryset filters.
  - References: [`Subquery` expressions](https://docs.djangoproject.com/en/stable/ref/models/expressions/#subquery-expressions), [`OuterRef`](https://docs.djangoproject.com/en/stable/ref/models/expressions/#outerref)
- **Aggregation**: `aggregate()` for whole-queryset stats, `annotate()` for per-row stats. Functions: `Count`, `Sum`, `Avg`, `Max`, `Min`, `StdDev`, `Variance`
  - `aggregate()` collapses a queryset into summary values, while `annotate()` adds computed values to each row in the result set.
  - Aggregations are where grouping semantics start to matter, so you need to understand how joins can change counts and sums.
  - This is a common place to accidentally double-count rows, so inspect SQL and test edge cases.
  - References: [Aggregation](https://docs.djangoproject.com/en/stable/topics/db/aggregation/)
- **`values()` and `values_list()`**: Return dicts/tuples instead of model instances. Use for performance when you don't need the full object
  - These methods reduce object construction overhead and make intent explicit when you only need specific columns.
  - They also change the shape of the result, which can affect downstream code and how annotations or distinctness behave.
  - Use them as an optimization when you have measured that model instances are unnecessary.
  - References: [`values()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#values), [`values_list()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#values-list)
- **`select_related()`**: Follows ForeignKey/OneToOne with a SQL JOIN. Use when you know you'll access the related object
  - `select_related()` reduces query count by joining single-valued relationships into the base query.
  - It is ideal when you will definitely touch the related object for every row and the join does not explode the result set.
  - The key skill is knowing when fewer queries are better and when a giant joined query becomes counterproductive.
  - References: [`select_related()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related)
- **`prefetch_related()`**: Separate query + Python-side join. Use for ManyToMany and reverse ForeignKey
  - `prefetch_related()` solves N+1 problems for multi-valued relationships by issuing additional focused queries and stitching the results together in Python.
  - It is the right tool for many-to-many and reverse foreign key access patterns that `select_related()` cannot handle.
  - Know that prefetching trades query count for memory, so it still needs judgment.
  - References: [`prefetch_related()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related)
- **`Prefetch` objects**: Custom querysets for prefetched data. Control filtering and ordering of prefetched results
  - `Prefetch` lets you control exactly what related rows are fetched and where they are stored on the model instances.
  - This is useful when the default related manager would load too much data or the wrong ordering.
  - It is one of the cleanest ways to prepare view-specific object graphs without contaminating model defaults.
  - References: [`Prefetch` objects](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-objects)
- **`only()` and `defer()`**: Load only specific fields. Use `only()` when you need few fields, `defer()` when you need most fields minus a few heavy ones
  - These methods are surgical optimizations for large tables or heavyweight fields, not default coding style.
  - Deferred fields trigger extra queries when accessed later, so they help only when you truly avoid touching those columns.
  - Use them after measuring, not as premature micro-optimizations.
  - References: [`only()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#only), [`defer()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#defer)
- **`exists()` and `count()`**: More efficient than `len(queryset)` or `bool(queryset)`
  - `exists()` answers “is there at least one row?” and `count()` asks the database for a count directly.
  - They communicate intent more clearly than forcing queryset evaluation and then inspecting Python objects.
  - In performance-sensitive paths, this distinction matters because you avoid loading whole rows unnecessarily.
  - References: [`exists()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#exists), [`count()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#count)
- **`bulk_create()`, `bulk_update()`**: Batch operations. Understand `batch_size` parameter and limitations (no signals, no custom `save()`)
  - Bulk operations are for throughput, not lifecycle hooks. They bypass parts of the model layer you may rely on elsewhere.
  - Use them for imports, backfills, and scheduled maintenance work where performance matters more than per-row behavior.
  - Always check the documented caveats before assuming they behave like repeated `save()` calls.
  - References: [`bulk_create()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#bulk-create), [`bulk_update()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#bulk-update)
- **`get_or_create()`, `update_or_create()`**: Atomic operations with race condition considerations
  - These APIs are convenient wrappers around common existence checks, but they are only as safe as the database constraints backing them.
  - Without uniqueness guarantees, race conditions can still produce duplicates or inconsistent assumptions.
  - Use them together with proper unique constraints, not instead of them.
  - References: [`get_or_create()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#get-or-create), [`update_or_create()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#update-or-create)
- **`iterator()`**: Memory-efficient iteration over large querysets
  - `iterator()` streams rows without caching them all in the queryset result cache, which is useful for large exports and backfills.
  - It reduces memory pressure but changes how repeated access behaves, so use it when you truly need one-pass processing.
  - Pair it with batching and careful transaction management for long-running jobs.
  - References: [`iterator()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#iterator)
- **Raw SQL**: `raw()` for raw queries that return model instances, `connection.cursor()` for completely custom SQL. Last resort only
  - Raw SQL is appropriate when the ORM cannot express the query cleanly or when you need backend-specific features that matter.
  - The cost is readability, portability, and safety review; once you leave the ORM, you lose a lot of Django’s guardrails.
  - Always parameterize queries and document why the ORM was insufficient.
  - References: [Performing raw SQL queries](https://docs.djangoproject.com/en/stable/topics/db/sql/)

#### Custom Managers and QuerySets
- **Custom managers**: Override `get_queryset()` to filter by default (e.g., soft delete: `objects = ActiveManager()`, `all_objects = models.Manager()`)
  - Managers define the entry point into your model API, so changing the base queryset changes how the model behaves throughout the project.
  - This is useful for default visibility rules like “active only,” but dangerous if it hides data in places that expect full access.
  - Keep an escape hatch such as `all_objects` when default filtering would otherwise surprise admin code, scripts, or maintenance tasks.
  - References: [Managers](https://docs.djangoproject.com/en/stable/topics/db/managers/)
- **Custom QuerySet methods**: Chain custom filters. Use `as_manager()` to turn a QuerySet class into a manager
  - Custom queryset methods are ideal for reusable, chainable domain queries like `.published()`, `.visible_to(user)`, or `.recent()`.
  - They keep query logic close to the model layer without forcing evaluation or tying you to one entry path.
  - `as_manager()` is the bridge that lets you expose the same API from `Model.objects`.
  - References: [Custom `QuerySet` methods](https://docs.djangoproject.com/en/stable/topics/db/managers/#creating-a-manager-with-queryset-methods)
- **When to use each**: Manager for changing the base queryset, QuerySet methods for chainable filters
  - Use a manager when the default universe of rows should change; use queryset methods when you want explicit opt-in filters.
  - If a filter should always apply everywhere, a manager may fit. If callers should be able to compose it, prefer a queryset method.
  - Keeping this distinction clear prevents confusing APIs and hidden behavior.
  - References: [Managers](https://docs.djangoproject.com/en/stable/topics/db/managers/)

**Practice**: Build a blog with posts, comments, tags (M2M with through model), and categories. Write queries that use every feature above. Use `django-debug-toolbar` to inspect the SQL generated.

---

### 1.4 Migrations

- **`makemigrations`** vs **`migrate`** — always review generated migrations before running them
  - `makemigrations` writes migration files from model changes; `migrate` applies migration operations to the database.
  - Treat generated migrations as code that deserves review, especially around defaults, constraints, data loss, and table rewrites.
  - A correct model change with a bad migration plan can still cause downtime or corrupt assumptions in production.
  - References: [Migrations](https://docs.djangoproject.com/en/stable/topics/migrations/)
- **Migration dependencies** — how Django resolves migration order across apps
  - Django builds a dependency graph across apps so schema changes happen in a consistent order.
  - Cross-app foreign keys and data migrations are where dependency understanding becomes essential.
  - If you cannot explain why one migration depends on another, you will struggle to resolve merge conflicts and deployment issues.
  - References: [Migration files](https://docs.djangoproject.com/en/stable/topics/migrations/#migration-files)
- **`RunPython` and `RunSQL`** — data migrations for backfilling, transforming existing data
  - Use `RunPython` for Python-level data transformations that can rely on historical models from the migration state.
  - Use `RunSQL` when the database can do the job more efficiently or when you need backend-specific features.
  - Reversibility matters: if a migration cannot be reversed safely, that should be an explicit decision, not an accident.
  - References: [Data migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations), [Writing migrations](https://docs.djangoproject.com/en/stable/howto/writing-migrations/)
- **Squashing migrations**: `squashmigrations` to reduce migration count
  - Squashing replaces a long chain of historical migrations with a smaller equivalent set, which improves startup and onboarding ergonomics.
  - It is most useful once an app’s migration history has stabilized and old deployments no longer need every intermediate step.
  - Squashing is maintenance work; review the generated result carefully before committing it.
  - References: [Squashing migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#squashing-migrations)
- **Handling migration conflicts** in teams — `makemigrations --merge`
  - Teams often create parallel migration branches, and Django will flag these as conflicts that need a merge migration.
  - Resolve conflicts by understanding both schema histories, not just by mechanically generating a merge file.
  - The goal is a coherent graph that preserves both developers’ changes without accidental no-ops or duplicated operations.
  - References: [Version control and migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#version-control)
- **Zero-downtime migrations**: Adding nullable columns, backfilling, then adding constraints. Never rename a column in one step in production
  - Production-safe schema changes are usually multi-step operations: introduce new structure, backfill, deploy code that uses it, then tighten constraints.
  - Avoid one-step destructive changes that lock large tables or break older app versions during rolling deploys.
  - Think operationally: your database and app may not update at exactly the same moment.
  - References: [Writing migrations](https://docs.djangoproject.com/en/stable/howto/writing-migrations/)
- **Fake migrations**: `migrate --fake` and `migrate --fake-initial` — when and why
  - Fake migrations mark migration state without applying SQL, which is useful only when the database already matches the expected schema.
  - This is a recovery and alignment tool, not something to use casually.
  - Misusing fake migration commands can desynchronize Django’s migration history from reality and make later deployments dangerous.
  - References: [`migrate`](https://docs.djangoproject.com/en/stable/ref/django-admin/#migrate)
- **Custom migration operations**: Writing reversible operations with `state_operations` and `database_operations`
  - Custom operations let you separate Django’s idea of project state from the exact SQL applied to the database.
  - This matters when the schema change is more nuanced than the built-in operations can express cleanly.
  - Only reach for custom operations when you fully understand both migration state and runtime database effects.
  - References: [Writing your own migration operations](https://docs.djangoproject.com/en/stable/howto/writing-migrations/#writing-your-own)

**Practice**: Write a data migration that backfills a new field from existing data. Practice squashing migrations. Simulate a migration conflict and resolve it.

---

## Phase 2: Views, Templates, and Forms

### 2.1 Views

#### Function-Based Views (FBVs)
- **Request/response cycle**: `HttpRequest` object, `HttpResponse` and its subclasses
  - A view receives an `HttpRequest`, performs application logic, and returns an `HttpResponse` or raises an exception that Django turns into one.
  - Understand what is already attached to the request by middleware: user, session, messages, files, headers, and method metadata.
  - Most view bugs come from not being precise about inputs, side effects, and response shape.
  - References: [Writing views](https://docs.djangoproject.com/en/stable/topics/http/views/), [Request and response objects](https://docs.djangoproject.com/en/stable/ref/request-response/)
- **Decorators**: `@login_required`, `@permission_required`, `@require_http_methods`, `@csrf_exempt` (understand why you almost never use this)
  - Decorators are the simplest way to layer access control and HTTP constraints onto FBVs.
  - Use them to make view requirements obvious at the top of the function instead of burying checks deep in the body.
  - `@csrf_exempt` should be exceptional because it disables a major built-in protection; if you think you need it, pause and verify the request pattern first.
  - References: [View decorators](https://docs.djangoproject.com/en/stable/topics/http/decorators/), [Authentication decorators](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-login-required-decorator), [CSRF protection](https://docs.djangoproject.com/en/stable/ref/csrf/)
- **Returning responses**: `HttpResponse`, `JsonResponse`, `HttpResponseRedirect`, `Http404`, `StreamingHttpResponse`, `FileResponse`
  - Response classes communicate intent: HTML, JSON, redirect, file transfer, or streaming output each have different behavior and performance tradeoffs.
  - Raise `Http404` for missing resources instead of returning ad hoc error pages; it keeps behavior consistent with Django conventions.
  - Use specialized response classes when the transport behavior matters rather than overloading plain `HttpResponse`.
  - References: [Request and response objects](https://docs.djangoproject.com/en/stable/ref/request-response/), [Shortcuts](https://docs.djangoproject.com/en/stable/topics/http/shortcuts/)

#### Class-Based Views (CBVs)
- **Base views**: `View`, `TemplateView`, `RedirectView`
  - These are the foundation classes that teach the CBV pattern without much abstraction hiding the mechanics.
  - `View` gives you method dispatch, while `TemplateView` and `RedirectView` package common response behaviors.
  - Understanding these base classes makes the higher-level generics much easier to customize safely.
  - References: [Base generic views](https://docs.djangoproject.com/en/stable/ref/class-based-views/base/)
- **Display views**: `DetailView`, `ListView`
  - Display views solve the common read-only patterns of “one object” and “many objects” while keeping conventions around template naming and context.
  - They are productive when your data retrieval is conventional and your customizations fit into the documented hooks.
  - The core skill is knowing which default behaviors you are relying on so you can override them deliberately.
  - References: [Generic display views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-display/)
- **Editing views**: `FormView`, `CreateView`, `UpdateView`, `DeleteView`
  - Editing views package the common GET/POST form lifecycle, validation, and redirect flow for CRUD-style interfaces.
  - They save time when your form and persistence flow is standard, but they can become awkward if the business process is more complex than a simple submit-and-save.
  - Learn the form handling hooks rather than overriding entire methods prematurely.
  - References: [Generic editing views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/)
- **Date views**: `ArchiveIndexView`, `YearArchiveView`, `MonthArchiveView`, `DayArchiveView`
  - Date-based views are specialized generics that organize querysets around temporal archives.
  - They are less common in modern apps but still useful for blogs, publishing systems, and audit-heavy interfaces.
  - Knowing they exist is useful even if you do not use them often.
  - References: [Date-based generic views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-date-based/)
- **Mixins**: `LoginRequiredMixin`, `PermissionRequiredMixin`, `UserPassesTestMixin`
  - Mixins layer reusable behavior onto CBVs, especially for access control and preconditions.
  - They keep permission logic declarative, but only if you understand how inheritance order affects dispatch.
  - Prefer mixins when the rule is reusable across multiple views instead of hand-writing the same checks repeatedly.
  - References: [Access mixins](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-loginrequiredmixin-mixin)
- **Method resolution order (MRO)**: How mixins compose. Put mixins left of the base view class
  - Python’s method resolution order decides which override runs first, so class order is behavior, not style.
  - If you do not understand the MRO, mixin-heavy CBVs become hard to debug because the wrong parent method may be called.
  - This is why access-control mixins are typically placed to the left of the main generic view class.
  - References: [Class-based views intro](https://docs.djangoproject.com/en/stable/topics/class-based-views/intro/)
- **`get_queryset()`**, **`get_context_data()`**, **`get_object()`**, **`get_form_class()`**, **`get_success_url()`** — the key methods to override
  - These hooks are where most safe customization happens in generic views.
  - Override the narrowest hook that solves the problem instead of replacing `get()` or `post()` unless you truly need full control.
  - Good CBV design comes from respecting the framework’s extension points rather than fighting them.
  - References: [Generic display views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-display/), [Generic editing views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/)
- **`dispatch()`** — entry point for all CBVs. Override for pre-processing (e.g., permission checks)
  - `dispatch()` routes the request to `get()`, `post()`, and other HTTP method handlers after the view instance is prepared.
  - It is the right place for cross-method preconditions, but it is easy to overuse and make view flow harder to follow.
  - If a mixin or narrower hook exists, prefer that before overriding `dispatch()` directly.
  - References: [Base `View`](https://docs.djangoproject.com/en/stable/ref/class-based-views/base/#view)
- **When to use FBVs vs CBVs**: FBVs for simple/custom logic, CBVs for standard CRUD patterns
  - FBVs are often clearer when the flow is unusual, highly procedural, or easier to understand as one function.
  - CBVs shine when you can leverage conventions around object lookup, form processing, or list/detail rendering.
  - Choose the style that makes the behavior easiest to read and maintain, not the one that feels more “advanced.”
  - References: [Writing views](https://docs.djangoproject.com/en/stable/topics/http/views/), [Class-based views](https://docs.djangoproject.com/en/stable/topics/class-based-views/)

**Practice**: Build the same feature (a CRUD interface for articles) using both FBVs and CBVs. Compare the code.

---

### 2.2 Templates

- **Template inheritance**: `{% extends %}`, `{% block %}`, `{{ block.super }}`
  - Inheritance gives templates a stable layout skeleton so page-specific templates only define the parts that vary.
  - Use it to keep page structure centralized and reduce duplication across navigation, metadata, and shared layout components.
  - `block.super` is useful when a child template needs to augment rather than replace parent content.
  - References: [Template inheritance](https://docs.djangoproject.com/en/stable/topics/templates/#template-inheritance)
- **Template tags**: `{% if %}`, `{% for %}`, `{% include %}`, `{% url %}`, `{% with %}`, `{% csrf_token %}`, `{% static %}`
  - Built-in tags cover most presentation logic you should allow in templates: control flow, composition, URL generation, and asset linking.
  - Keep template logic simple and declarative; if the template starts to look like application code, move that logic into the view or a helper.
  - The most important habit is to generate URLs and static asset paths through tags rather than hardcoded strings.
  - References: [Built-in tags](https://docs.djangoproject.com/en/stable/ref/templates/builtins/)
- **Filters**: `|date`, `|default`, `|length`, `|truncatewords`, `|safe`, `|escapejs`, `|json_script`
  - Filters format or transform values for presentation and should stay focused on rendering concerns, not business logic.
  - Some filters are convenience-oriented, while others like `safe` and escaping-related filters carry security implications.
  - Learn which filters are presentation sugar and which ones meaningfully change trust boundaries.
  - References: [Built-in filters](https://docs.djangoproject.com/en/stable/ref/templates/builtins/)
- **Custom template tags and filters**: `simple_tag`, `inclusion_tag`, `filter` — when you need reusable template logic
  - Custom tags are justified when the presentation pattern is reused and does not belong in every view context separately.
  - Keep them narrow and presentation-focused; once they start querying extensively or encoding business rules, they become hard to reason about.
  - `inclusion_tag` is especially useful for reusable fragments that need their own mini-context.
  - References: [Custom template tags and filters](https://docs.djangoproject.com/en/stable/howto/custom-template-tags/)
- **`{% json_script %}`**: Safely pass data from Django to JavaScript without XSS
  - `json_script` is the safest built-in pattern for embedding server-side data into a page for later JavaScript consumption.
  - It avoids the common mistake of hand-rolling JSON into inline scripts and accidentally creating an XSS sink.
  - Prefer it over string concatenation whenever you need structured data on the client side.
  - References: [`json_script`](https://docs.djangoproject.com/en/stable/ref/templates/builtins/#json-script)
- **Template loading**: `APP_DIRS`, `DIRS`, and resolution order
  - Django searches template locations in a defined order, so directory configuration directly affects which template wins.
  - This matters for shared base templates, app-specific overrides, and admin customization.
  - Understand the loader chain so template selection never feels magical.
  - References: [Template settings and loaders](https://docs.djangoproject.com/en/stable/topics/templates/), [Template API](https://docs.djangoproject.com/en/stable/ref/templates/api/)
- **Auto-escaping**: Enabled by default. Understand `|safe`, `mark_safe()`, and when (rarely) to use them
  - Auto-escaping is one of Django’s main defenses against XSS and should be treated as the default trust model for templates.
  - `safe` and `mark_safe()` are trust overrides, not formatting helpers, and should be used only when content has been sanitized or is fully controlled.
  - Anytime you bypass escaping, you are taking direct responsibility for output safety.
  - References: [Automatic HTML escaping](https://docs.djangoproject.com/en/stable/topics/templates/#automatic-html-escaping), [`safe`](https://docs.djangoproject.com/en/stable/ref/templates/builtins/#safe)

---

### 2.3 Forms

#### Core Concepts
- **`Form` vs `ModelForm`** — use `ModelForm` when the form maps to a model, `Form` for everything else
  - `ModelForm` is productive when the form is mainly a projection of model fields plus validation, but it should not force every workflow into a model-shaped interface.
  - Plain `Form` is better for searches, multi-step flows, API-adjacent inputs, or any case where validation exists without a direct model save.
  - Choose based on workflow shape, not habit.
  - References: [Forms](https://docs.djangoproject.com/en/stable/topics/forms/), [ModelForms](https://docs.djangoproject.com/en/stable/topics/forms/modelforms/)
- **Field types and widgets**: Every field has a default widget. Override widgets in `Meta.widgets` or in `__init__`
  - Fields define validation and normalized Python values; widgets define how the input is rendered and parsed from HTML.
  - This distinction matters because UI customization and data validation are related but not the same concern.
  - Override widgets when the browser input should change, not when the underlying data type changes.
  - References: [Form fields](https://docs.djangoproject.com/en/stable/ref/forms/fields/), [Widgets](https://docs.djangoproject.com/en/stable/ref/forms/widgets/)
- **Validation pipeline**: `field.clean()` -> `form.clean_<fieldname>()` -> `form.clean()`
  - Validation flows from field-level normalization to field-specific form hooks to whole-form cross-field validation.
  - Knowing this order is what lets you put validation in the right place and avoid duplicated or conflicting checks.
  - Put single-field rules as close to the field as possible; reserve `form.clean()` for rules involving multiple inputs.
  - References: [Form and field validation](https://docs.djangoproject.com/en/stable/ref/forms/validation/)
- **`is_valid()`**, **`cleaned_data`**, **`errors`** — the validation cycle
  - Calling `is_valid()` runs the validation pipeline and populates both normalized data and structured error information.
  - `cleaned_data` is only trustworthy after successful validation; `errors` is the proper API for rendering feedback.
  - Understanding this lifecycle keeps form handling deterministic and prevents subtle misuse of partially cleaned inputs.
  - References: [Working with forms](https://docs.djangoproject.com/en/stable/topics/forms/)
- **`save(commit=False)`** — modify the object before saving (e.g., set the author to `request.user`)
  - `commit=False` is how you intercept `ModelForm` persistence when the form does not have all model data yet.
  - It is useful for request-derived fields, related object wiring, and controlled save ordering.
  - Remember that many-to-many data is deferred and may require `save_m2m()` after the instance is saved.
  - References: [The `save()` method](https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#the-save-method)

#### Advanced Forms
- **Formsets**: `formset_factory`, `modelformset_factory`, `inlineformset_factory`
  - Formsets are for managing multiple homogeneous forms in one request cycle, which is common in bulk editing and parent-child UIs.
  - The management form and indexing rules are essential to understand; if you do not understand them, debugging formset bugs is painful.
  - Inline formsets are especially useful when editing a parent object and its related children together.
  - References: [Formsets](https://docs.djangoproject.com/en/stable/topics/forms/formsets/), [Inline formsets](https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#inline-formsets)
- **Dynamic forms**: Modify fields in `__init__` based on user permissions, request data, etc.
  - Dynamic form configuration is often cleaner than creating many near-duplicate form classes for slight behavioral differences.
  - It is appropriate for per-user choices, contextual help, conditional requiredness, and restricted field querysets.
  - Keep the logic readable and deterministic; forms that mutate unpredictably are hard to test.
  - References: [Working with forms](https://docs.djangoproject.com/en/stable/topics/forms/)
- **Custom validation**: `clean_<field>()` for single-field validation, `clean()` for cross-field validation
  - Validation placement should mirror responsibility: field hooks for isolated rules, `clean()` for interactions between fields.
  - Good validation code explains domain rules clearly rather than scattering them between views, templates, and model saves.
  - This is one of the best places to keep user-facing input rules explicit and testable.
  - References: [Form validation](https://docs.djangoproject.com/en/stable/ref/forms/validation/)
- **File uploads**: `request.FILES`, `FileField`, `ImageField`, `enctype="multipart/form-data"`
  - File uploads add transport and storage concerns to normal form handling, including multipart encoding and temporary upload storage.
  - A valid form still needs correct template markup and request handling, or the file data will never arrive.
  - Treat file uploads as an end-to-end workflow: browser form, Django parser, validation, storage backend, and serving strategy.
  - References: [File uploads](https://docs.djangoproject.com/en/stable/topics/http/file-uploads/), [Uploaded files](https://docs.djangoproject.com/en/stable/ref/files/uploads/)
- **Form rendering**: `{{ form.as_p }}`, `{{ form.as_table }}`, manual rendering with `{{ field.label_tag }}` and `{{ field }}`
  - Django provides quick rendering helpers, but manual rendering usually gives you the control needed for production markup and accessibility.
  - Once forms become design-sensitive, you will usually want explicit control over labels, help text, errors, and ARIA attributes.
  - Learn the default helpers first, then graduate to manual rendering when the UI demands it.
  - References: [Rendering fields manually](https://docs.djangoproject.com/en/stable/topics/forms/#rendering-fields-manually)
- **Crispy Forms / Widget Tweaks**: Third-party libraries for better form rendering (common in production)
  - These libraries solve presentation problems that Django intentionally leaves mostly unopinionated.
  - Use them to improve rendering ergonomics, not to hide weak form structure or validation design.
  - Django does not provide first-party docs for these packages, so treat them as ecosystem tools layered on top of Django’s form system.

**Practice**: Build a multi-step form wizard. Build an inline formset for editing a parent object and its children on the same page.

---

## Phase 3: Authentication & Authorization

### 3.1 Built-in Auth System

- **User model**: `AbstractUser` (extend it) vs `AbstractBaseUser` (replace it). **Always use a custom user model from day one**, even if it's just `class User(AbstractUser): pass`
  - A custom user model early avoids one of Django’s most painful later refactors.
  - `AbstractUser` is the pragmatic default because you keep Django’s built-in behavior while preserving room for future customization.
  - Reach for `AbstractBaseUser` only when your authentication identity or account model truly differs from Django’s standard assumptions.
  - References: [Customizing authentication](https://docs.djangoproject.com/en/stable/topics/auth/customizing/)
- **`AUTH_USER_MODEL`** setting — set it before your first migration, it's painful to change later
  - This setting tells Django which model is the canonical user model across foreign keys, forms, and auth internals.
  - It must be set before initial migrations because user references become baked into migration history and app relationships.
  - Treat this as a project bootstrap decision, not a future cleanup task.
  - References: [`AUTH_USER_MODEL`](https://docs.djangoproject.com/en/stable/ref/settings/#auth-user-model), [Substituting a custom `User` model](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#substituting-a-custom-user-model)
- **`get_user_model()`** — always use this instead of importing User directly
  - Importing the concrete `User` model directly couples your code to Django’s default auth implementation.
  - `get_user_model()` keeps model references aligned with the configured auth model and avoids subtle breakage in reusable code.
  - The same principle applies to foreign keys: use `settings.AUTH_USER_MODEL`, not a direct import.
  - References: [`get_user_model()`](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#referencing-the-user-model)
- **Authentication backends**: How `AUTHENTICATION_BACKENDS` works, writing custom backends (LDAP, SSO, API token)
  - Authentication backends determine how credentials are checked and how users are loaded for permission checks.
  - Multiple backends can coexist, which is powerful but means you should understand backend ordering and how permissions are aggregated.
  - Custom backends are appropriate when integrating corporate identity, SSO, or non-password credentials.
  - References: [Authentication backends](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#writing-an-authentication-backend)
- **Password hashing**: `PBKDF2` by default, `argon2` or `bcrypt` for production. `PASSWORD_HASHERS` setting
  - Password storage is handled by pluggable hashers, and Django automatically upgrades stored hashes over time as users log in.
  - The main question is not “can Django hash passwords?” but “which hasher policy fits our security posture and runtime constraints?”
  - Learn how hasher ordering affects verification and migration.
  - References: [Password management](https://docs.djangoproject.com/en/stable/topics/auth/passwords/), [`PASSWORD_HASHERS`](https://docs.djangoproject.com/en/stable/ref/settings/#password-hashers)
- **Built-in views**: `LoginView`, `LogoutView`, `PasswordChangeView`, `PasswordResetView` — customize templates, redirect URLs
  - Django ships a full set of auth views for common account workflows, which is often enough for server-rendered apps.
  - Your job is usually to wire templates, emails, URLs, and redirect behavior rather than reinvent the flow from scratch.
  - Learn the defaults before replacing them; it is easier to customize proven flows than rebuild them correctly.
  - References: [Authentication views](https://docs.djangoproject.com/en/stable/topics/auth/default/#using-the-views)

### 3.2 Permissions & Authorization

- **Model-level permissions**: Default `add_`, `change_`, `delete_`, `view_` permissions. Custom permissions in `Meta.permissions`
  - Django creates standard CRUD-like model permissions automatically, which gives you a baseline authorization vocabulary.
  - Custom permissions let you encode domain actions such as `publish_post` or `approve_invoice` instead of overloading generic change rights.
  - Authorization becomes easier to reason about when permission names reflect real business actions.
  - References: [Permissions and authorization](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization), [Custom permissions](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#custom-permissions)
- **`has_perm()`**, **`has_perms()`** — check permissions in code
  - These APIs are the low-level permission checks you will use in views, templates, and services when access decisions are explicit.
  - They reflect the combined result of the user’s permissions, group permissions, and superuser status.
  - Use them close to the protected behavior so the authorization rule stays obvious.
  - References: [Permissions API](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization)
- **`@permission_required`** decorator, **`PermissionRequiredMixin`**
  - These abstractions make access requirements declarative for FBVs and CBVs.
  - They are preferable to ad hoc permission checks scattered through view bodies because they state the rule at the entry point.
  - When using CBVs, prefer the mixin over manual `dispatch()` checks if it covers the use case cleanly.
  - References: [The `permission_required` decorator](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-permission-required-decorator), [Access mixins](https://docs.djangoproject.com/en/stable/topics/auth/default/#redirecting-unauthorized-requests-in-class-based-views)
- **`@user_passes_test`** — custom permission checks
  - `user_passes_test` is the escape hatch for custom access rules that do not map neatly to a stored permission.
  - It is useful for role checks, account state checks, or other predicates that depend on current user attributes.
  - Use it carefully; once access rules get complex, dedicated permission functions or service-layer checks are often clearer.
  - References: [Limiting access to logged-in users that pass a test](https://docs.djangoproject.com/en/stable/topics/auth/default/#limiting-access-to-logged-in-users-that-pass-a-test)
- **Groups**: Assign permissions to groups, then users to groups
  - Groups are Django’s built-in role aggregation mechanism and are often enough for internal tools and many business apps.
  - They help you manage permissions operationally without assigning many individual permissions to each user.
  - Design groups around roles people actually understand, not arbitrary technical clusters.
  - References: [Groups](https://docs.djangoproject.com/en/stable/topics/auth/default/#groups)
- **Object-level permissions**: Django doesn't provide this out of the box. Use `django-guardian` or `django-rules`
  - Django’s built-in permission model is mostly model-level, so per-object authorization requires either explicit queryset filtering or third-party tooling.
  - Object-level permission packages are valuable when you need assignable per-record access rather than ownership-based filtering.
  - The important architectural question is whether object permissions are really needed or whether row filtering captures the actual rule.
  - References: [Permissions and authorization](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization), [`django-guardian` docs](https://django-guardian.readthedocs.io/en/stable/), [`rules` repository](https://github.com/dfunckt/django-rules)
- **Row-level security patterns**: Filter querysets based on user in `get_queryset()`
  - Most application-level authorization is really visibility filtering, not separate permission metadata.
  - Enforcing visibility in `get_queryset()` keeps list and detail access aligned with the same data-scope rule.
  - This pattern is critical in multi-tenant and role-scoped applications where “can access” usually means “belongs to this filtered subset.”
  - References: [Generic display views](https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-display/), [QuerySets](https://docs.djangoproject.com/en/stable/topics/db/queries/)

### 3.3 Sessions

- **Session backends**: Database, cache, file, signed cookies
  - Session backend choice affects durability, performance, and operational complexity.
  - Database-backed sessions are simple and reliable; cached or signed-cookie approaches trade persistence and storage location differently.
  - Pick the backend based on scaling and security needs, not default convenience alone.
  - References: [Sessions](https://docs.djangoproject.com/en/stable/topics/http/sessions/)
- **Session configuration**: `SESSION_ENGINE`, `SESSION_COOKIE_AGE`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`
  - Session settings determine how long sessions live, where they are stored, and how safely the browser transports the session cookie.
  - Production deployments should review cookie security settings explicitly rather than relying on defaults.
  - Session behavior is part of both user experience and security posture.
  - References: [Session settings](https://docs.djangoproject.com/en/stable/ref/settings/#sessions)
- **Accessing session data**: `request.session` as a dict-like object
  - `request.session` is the per-user server-side state store exposed to application code.
  - Use it for small, session-scoped data like carts, in-progress flows, or temporary UI state, not as a general database substitute.
  - Be disciplined about what goes into the session because hidden state is easy to accumulate and hard to reason about.
  - References: [Using sessions in views](https://docs.djangoproject.com/en/stable/topics/http/sessions/#using-sessions-in-views)

### 3.4 Third-Party Auth

- **`django-allauth`**: Social auth (Google, GitHub, etc.), email verification, account management. The go-to library for production auth
  - Use it when built-in auth views are not enough and you need registration, email confirmation, or social login flows.
  - It integrates with Django auth rather than replacing it, so strong Django auth fundamentals still matter.
  - Django does not provide first-party docs for this library; treat it as the ecosystem standard layered on top of the core auth system.
  - References: [`django-allauth` docs](https://docs.allauth.org/en/latest/)
- **JWT / Token auth**: `djangorestframework-simplejwt` for API authentication
  - JWT is an API authentication strategy, not a replacement for understanding sessions, cookies, and permission checks.
  - It is most appropriate for stateless API clients and frontend/backend separations where bearer tokens fit operationally.
  - Prefer it because your API needs it, not because it sounds modern.
  - References: [`Simple JWT` docs](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/)
- **OAuth2 provider**: `django-oauth-toolkit` if you need to be an OAuth provider
  - This is relevant only when your system itself issues OAuth tokens to other clients or services.
  - It adds protocol and lifecycle complexity, so do not adopt it unless you actually need delegated authorization flows.
  - Django itself does not ship an OAuth provider, so this lives squarely in the third-party ecosystem.
  - References: [`django-oauth-toolkit` docs](https://django-oauth-toolkit.readthedocs.io/en/latest/)

**Practice**: Build a full auth flow: custom user model, registration with email verification (using `django-allauth`), login, logout, password reset, profile editing. Add role-based access to different sections.

---

## Phase 4: Django REST Framework (DRF)

### 4.1 Serializers

- **`Serializer` vs `ModelSerializer`** — same distinction as `Form` vs `ModelForm`
  - `ModelSerializer` is productive when your API maps closely to model structure, but it should not dictate the API shape by default.
  - Plain `Serializer` is better when the contract is workflow-oriented, aggregated, or intentionally decoupled from persistence.
  - Choose based on API design, not just speed of scaffolding.
  - References: [DRF serializers](https://www.django-rest-framework.org/api-guide/serializers/)
- **Field types**: Mirror model fields but for API representation
  - Serializer fields define validation, coercion, and representation for external clients rather than database storage.
  - This distinction matters because API types are a public contract, not just an internal schema mirror.
  - Good serializer design is explicit about what the client can send and what the API will return.
  - References: [Serializer fields](https://www.django-rest-framework.org/api-guide/fields/)
- **Nested serializers**: Representing related objects. `depth` for quick nesting, explicit nested serializers for control
  - Nesting is useful for client convenience, but deeper nesting expands payload size and coupling between resources.
  - `depth` is fast for prototypes, while explicit nested serializers are the production-friendly approach because they make the contract deliberate.
  - Be intentional about whether the API should embed relationships or link to them.
  - References: [Nested relationships](https://www.django-rest-framework.org/api-guide/relations/)
- **`SerializerMethodField`**: Computed fields
  - This field type is for derived output that belongs in the API representation but is not a direct serializer field mapping.
  - It is convenient, but easy to abuse if the method triggers per-object queries or complex business logic.
  - Use it for presentation-level computed data, not hidden performance traps.
  - References: [`SerializerMethodField`](https://www.django-rest-framework.org/api-guide/fields/#serializermethodfield)
- **Validation**: `validate_<field>()`, `validate()`, field-level validators
  - DRF validation mirrors Django forms conceptually: single-field rules belong close to fields, cross-field rules belong in `validate()`.
  - Good serializer validation makes API errors precise and keeps invalid state from leaking into business logic.
  - Keep validation deterministic and client-facing, with clear error messages.
  - References: [Serializer validation](https://www.django-rest-framework.org/api-guide/serializers/#validation)
- **`to_representation()` / `to_internal_value()`**: Customize serialization/deserialization
  - These hooks give you full control over how Python objects become API payloads and vice versa.
  - They are powerful enough to reshape contracts, which means they should be used sparingly and documented clearly.
  - Reach for them when field-level configuration is not expressive enough.
  - References: [Custom serializers](https://www.django-rest-framework.org/api-guide/serializers/)
- **`create()` and `update()`**: Override for custom save behavior (writable nested serializers)
  - These methods control how validated data becomes persisted state.
  - Override them when persistence is more complex than `ModelSerializer` defaults, especially with nested writes or related object orchestration.
  - Keep them transaction-aware and explicit about side effects.
  - References: [Saving instances](https://www.django-rest-framework.org/api-guide/serializers/#saving-instances)
- **Read/write serializer split**: Different serializers for input vs output. Common production pattern
  - Many APIs benefit from separate serializers because write payloads and read representations often have different concerns.
  - This reduces conditional field behavior and keeps each serializer easier to reason about.
  - It is a practical pattern once your API moves beyond simple CRUD.
  - References: [DRF serializers](https://www.django-rest-framework.org/api-guide/serializers/)

### 4.2 Views & ViewSets

- **`APIView`**: Base class, explicit method handlers (`get`, `post`, `put`, `delete`)
  - `APIView` is the DRF equivalent of a low-abstraction CBV and is useful when request handling is custom but still benefits from DRF’s request parsing, authentication, and response handling.
  - It gives you more control than generics while preserving DRF conventions around exceptions and content negotiation.
  - Use it when the endpoint shape is custom enough that generic mixins would obscure rather than simplify behavior.
  - References: [APIView](https://www.django-rest-framework.org/api-guide/views/)
- **Generic views**: `ListAPIView`, `CreateAPIView`, `RetrieveAPIView`, `UpdateAPIView`, `DestroyAPIView`, `ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`
  - Generic views package common CRUD endpoint patterns similarly to Django’s generic CBVs.
  - They are most useful when the endpoint is conventional and the main differences are queryset, serializer, and permission choices.
  - Learn the mixin structure so you know where the behavior actually comes from.
  - References: [Generic views](https://www.django-rest-framework.org/api-guide/generic-views/)
- **ViewSets**: `ModelViewSet`, `ReadOnlyModelViewSet`. Map to URLs via `Router`
  - ViewSets centralize related actions for a resource, which keeps routing and controller logic compact for standard RESTful endpoints.
  - They work best when your API genuinely behaves like a resource collection, not when many custom actions dominate.
  - Routers reduce boilerplate, but you still need to understand which URLs and action names they generate.
  - References: [ViewSets](https://www.django-rest-framework.org/api-guide/viewsets/), [Routers](https://www.django-rest-framework.org/api-guide/routers/)
- **`@action` decorator**: Custom endpoints on viewsets (`@action(detail=True, methods=['post'])`)
  - `@action` is for non-standard resource operations that still belong conceptually with a viewset’s resource.
  - It is useful, but too many actions can signal that the resource boundary is muddled.
  - Keep custom actions explicit and limited so the API remains understandable.
  - References: [Marking extra actions for routing](https://www.django-rest-framework.org/api-guide/viewsets/#marking-extra-actions-for-routing)
- **`get_serializer_class()`**: Return different serializers based on action (list vs detail)
  - Different actions often deserve different payload shapes, especially when list endpoints need lightweight responses and detail endpoints need richer data.
  - This hook is the clean way to express that difference without stuffing conditional logic into one serializer.
  - Keep the action-to-serializer mapping simple and predictable.
  - References: [Generic views](https://www.django-rest-framework.org/api-guide/generic-views/)
- **`get_queryset()`**: Filter based on request user, query params
  - This is where endpoint-level data scoping usually belongs, especially for tenant filtering and ownership rules.
  - Use it to make visibility rules explicit and keep list/detail behavior aligned under the same resource scope.
  - Queryset filtering is part of authorization as much as it is part of querying.
  - References: [Filtering against query parameters](https://www.django-rest-framework.org/api-guide/filtering/), [Generic views](https://www.django-rest-framework.org/api-guide/generic-views/)
- **`perform_create()`, `perform_update()`**: Hook into save without overriding the full method
  - These hooks are the narrow extension points for injecting request-derived fields, side effects, or lightweight save-time logic.
  - They are preferable to overriding `create()` and `update()` when the HTTP flow itself does not need to change.
  - Use the narrowest hook that fits the requirement.
  - References: [Save and deletion hooks](https://www.django-rest-framework.org/api-guide/generic-views/)

### 4.3 Authentication & Permissions

- **Authentication classes**: `SessionAuthentication`, `TokenAuthentication`, `JWTAuthentication`
  - Authentication decides how DRF identifies the caller; it does not decide what the caller may do.
  - Session auth fits browser-based apps, while token or JWT schemes fit API clients and decoupled frontends.
  - Pick authentication based on client behavior and deployment model, not trendiness.
  - References: [Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- **Permission classes**: `IsAuthenticated`, `IsAdminUser`, `IsAuthenticatedOrReadOnly`, `AllowAny`
  - Permission classes are DRF’s view-level authorization layer and should be treated as part of the endpoint contract.
  - Compose them carefully so anonymous, read-only, and admin-only behaviors are obvious from the class definition.
  - A good permission policy is consistent across the API, not improvised per endpoint.
  - References: [Permissions](https://www.django-rest-framework.org/api-guide/permissions/)
- **Custom permissions**: Subclass `BasePermission`, implement `has_permission()` and `has_object_permission()`
  - Custom permissions are for rules that built-ins cannot express cleanly.
  - Separate view-level access from object-level access so the API can reject quickly and consistently at the right layer.
  - Keep permission classes readable; if you cannot explain the rule clearly, the code probably needs simplification.
  - References: [Custom permissions](https://www.django-rest-framework.org/api-guide/permissions/#custom-permissions)
- **Per-view vs global**: `DEFAULT_PERMISSION_CLASSES` in settings vs per-view `permission_classes`
  - Global defaults establish the API’s baseline security posture, while per-view settings express intentional exceptions.
  - This is safer than relying on every view author to remember to lock endpoints down manually.
  - Start restrictive globally, then loosen only where needed.
  - References: [Settings](https://www.django-rest-framework.org/api-guide/settings/), [Permissions](https://www.django-rest-framework.org/api-guide/permissions/)

### 4.4 Filtering, Pagination, and Throttling

- **`django-filter`**: `FilterSet`, `DjangoFilterBackend`. Declarative filtering from query params
  - `django-filter` turns ad hoc query-param parsing into a declarative API surface.
  - It is cleaner and safer than hand-written filtering logic scattered across `get_queryset()`.
  - This is one of the first DRF add-ons worth learning well.
  - References: [Filtering](https://www.django-rest-framework.org/api-guide/filtering/), [`django-filter` docs](https://django-filter.readthedocs.io/en/stable/)
- **`SearchFilter`**: Full-text search across specified fields
  - `SearchFilter` is useful for lightweight search behavior, especially in internal tools and simple APIs.
  - It is not a substitute for real search design when ranking, stemming, or large-scale performance matter.
  - Use it as a practical default, not a universal solution.
  - References: [SearchFilter](https://www.django-rest-framework.org/api-guide/filtering/#searchfilter)
- **`OrderingFilter`**: Dynamic ordering from query params
  - Ordering filters let clients choose sort order, which improves API flexibility without adding dedicated endpoints.
  - Always restrict allowed ordering fields so clients cannot accidentally trigger expensive or sensitive sorts.
  - Sorting is part of the API contract and should be documented explicitly.
  - References: [OrderingFilter](https://www.django-rest-framework.org/api-guide/filtering/#orderingfilter)
- **Pagination**: `PageNumberPagination`, `LimitOffsetPagination`, `CursorPagination` (best for real-time data)
  - Pagination strategy affects API ergonomics, stability under changing data, and client complexity.
  - Cursor pagination is particularly useful for feeds and large datasets where stable traversal matters more than arbitrary page jumps.
  - Pick one style deliberately and keep it consistent unless you have a strong reason not to.
  - References: [Pagination](https://www.django-rest-framework.org/api-guide/pagination/)
- **Throttling**: `AnonRateThrottle`, `UserRateThrottle`, `ScopedRateThrottle`. Configure rates in settings
  - Throttling is a fairness and abuse-control mechanism, not a strong security boundary.
  - Different throttle classes let you express different traffic budgets for anonymous users, authenticated users, and specific endpoint groups.
  - It should complement monitoring and rate-limiting strategy, not replace them.
  - References: [Throttling](https://www.django-rest-framework.org/api-guide/throttling/)

### 4.5 Versioning

- **URL path versioning**: `/api/v1/`, `/api/v2/`
  - Path versioning is explicit and easy for clients, logs, and routing to understand.
  - It tends to be the most operationally straightforward versioning scheme for internal and public APIs alike.
  - The main tradeoff is URL churn when versions change.
  - References: [Versioning](https://www.django-rest-framework.org/api-guide/versioning/)
- **Header versioning**: `Accept: application/json; version=1`
  - Header-based versioning keeps URLs stable and pushes version semantics into content negotiation.
  - It is powerful, but clients and debugging tools need to handle it consistently or it becomes opaque.
  - Use it when you intentionally want URLs to remain version-neutral.
  - References: [Versioning schemes](https://www.django-rest-framework.org/api-guide/versioning/)
- **Namespace versioning**: Separate URLconfs per version
  - Namespaced versioning keeps versioned route sets organized and makes parallel versions easier to maintain during transitions.
  - It works well when a newer version needs partial divergence rather than a complete rewrite.
  - Clear version boundaries matter more than clever deduplication.
  - References: [Versioning](https://www.django-rest-framework.org/api-guide/versioning/)
- **Strategy**: Version the API, not individual endpoints. Support N and N-1
  - Versioning strategy is mostly a product and operations decision expressed through routing and deprecation policy.
  - Supporting the current version and one prior version is a common compromise between client stability and maintenance burden.
  - Consistency beats cleverness: decide how compatibility works before clients depend on your API.
  - References: [Versioning](https://www.django-rest-framework.org/api-guide/versioning/)

### 4.6 Testing APIs

- **`APIClient`**: `.get()`, `.post()`, `.put()`, `.patch()`, `.delete()`
  - `APIClient` is the main test client for DRF endpoints and understands DRF request/response patterns better than Django’s plain client.
  - It lets you exercise authentication, content negotiation, and serialization behavior realistically.
  - Use it for endpoint-level tests where the HTTP contract matters.
  - References: [DRF testing](https://www.django-rest-framework.org/api-guide/testing/)
- **`force_authenticate()`**: Skip auth in tests
  - This helper is useful when the test is about endpoint behavior after authentication, not the auth mechanism itself.
  - It keeps tests focused and reduces setup noise for permission or business-logic cases.
  - Do not use it everywhere; keep some tests that exercise the real auth path too.
  - References: [Forcing authentication](https://www.django-rest-framework.org/api-guide/testing/#forcing-authentication)
- **Response assertions**: Status codes, response data structure, pagination format
  - API tests should verify both semantics and contract shape, not just that the endpoint returned 200.
  - Assert status codes, key fields, error formats, and pagination envelopes so clients can depend on consistent responses.
  - Treat the serialized response as a public interface.
  - References: [DRF testing](https://www.django-rest-framework.org/api-guide/testing/)
- **Schema validation**: Use `drf-spectacular` for OpenAPI schema generation and validation
  - Schema tooling helps keep implementation and API documentation aligned.
  - It is especially valuable once multiple clients or teams consume the API.
  - Django does not provide first-party schema generation for DRF, so this belongs to the DRF ecosystem rather than core Django docs.
  - References: [`drf-spectacular` docs](https://drf-spectacular.readthedocs.io/en/stable/)

**Practice**: Build a complete REST API for a task management system: users, projects, tasks, comments. Include authentication, permissions (users can only see their projects), filtering, pagination, and full test coverage.

---

## Phase 5: Production Essentials

### 5.1 Database Optimization

#### Query Optimization
- **`django-debug-toolbar`**: Install it immediately. Watch for N+1 queries
  - This is the fastest way to build intuition for what your views are actually doing at the SQL layer.
  - Use it during feature development, not only after performance problems appear.
  - Django does not ship it, but it complements the ORM documentation exceptionally well.
  - References: [`django-debug-toolbar` docs](https://django-debug-toolbar.readthedocs.io/)
- **N+1 problem**: Accessing related objects in a loop without `select_related`/`prefetch_related`
  - N+1 queries are a symptom of object traversal patterns that look innocent in Python but are expensive at the database boundary.
  - Train yourself to spot loops that touch related fields, especially in templates and serializers.
  - Fixing N+1 issues is one of the highest-leverage Django optimization skills.
  - References: [`select_related()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related), [`prefetch_related()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related)
- **`explain()`**: Call `.explain()` on a queryset to see the SQL execution plan
  - `explain()` helps you move from guessing about performance to inspecting the database’s actual execution strategy.
  - It is especially useful when a query “looks fine” in ORM code but behaves poorly with real data volume.
  - Learn to connect query plans back to indexes, joins, and ordering choices.
  - References: [`explain()`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#explain)
- **Indexing strategy**: Add `db_index=True` to fields you filter/order by frequently. Composite indexes via `Meta.indexes`
  - Indexes should reflect real query patterns, not speculative optimization.
  - Single-column indexes help common filters; composite indexes matter when fields are usually queried together or used with ordering.
  - Every index has a write and storage cost, so treat indexing as measured design work.
  - References: [Indexes reference](https://docs.djangoproject.com/en/stable/ref/models/indexes/), [Database optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- **`django-silk`**: Profiling middleware for production-like environments
  - Silk is useful when you need broader profiling than debug-toolbar-style local inspection.
  - It can help connect slow requests to SQL volume, Python time, and endpoint behavior.
  - Like other third-party profilers, it complements rather than replaces Django’s own optimization guidance.
  - References: [`django-silk` repository](https://github.com/jazzband/django-silk)

#### Connection Management
- **`CONN_MAX_AGE`**: Keep database connections alive between requests
  - Persistent connections reduce reconnect overhead and are often the easiest first production tuning knob.
  - The right value depends on traffic, infrastructure, and how your database handles idle connections.
  - Treat it as part of deployment tuning, not a magic performance switch.
  - References: [Persistent database connections](https://docs.djangoproject.com/en/stable/ref/databases/#persistent-connections)
- **Connection pooling**: Use `django-db-connection-pool` or PgBouncer for production
  - Connection pooling is usually an infrastructure concern rather than a Django application concern.
  - PgBouncer is the common answer because it manages connection pressure centrally and predictably.
  - Understand pooling especially when you scale workers horizontally.
  - References: [Databases](https://docs.djangoproject.com/en/stable/ref/databases/), [`django-db-connection-pool` package](https://pypi.org/project/django-db-connection-pool/), [PgBouncer docs](https://www.pgbouncer.org/)
- **Read replicas**: Route reads to replicas with `DATABASE_ROUTERS`
  - Django can route database operations through routers, which is the application-level tool for multi-database strategies.
  - Read replicas improve scale only if the consistency tradeoffs are acceptable for the feature.
  - Know which code paths can tolerate replica lag and which cannot.
  - References: [Multiple databases](https://docs.djangoproject.com/en/stable/topics/db/multi-db/)

#### Advanced Patterns
- **Database functions**: `Concat`, `Coalesce`, `Greatest`, `Least`, `Now`, `Cast`, `Length`, `Lower`, `Upper`, `Trim`
  - Database functions let you push formatting and computation into SQL while staying inside the ORM.
  - They are most useful when the database can compute values more efficiently than Python or when you need expression-based filtering.
  - Learn them gradually; a handful of functions covers a surprising amount of real work.
  - References: [Database functions](https://docs.djangoproject.com/en/stable/ref/models/database-functions/)
- **Window functions**: `Window`, `RowNumber`, `Rank`, `DenseRank`, `Lag`, `Lead`
  - Window functions are for analytics-style queries where each row needs context from neighboring rows or ranked groups.
  - They are advanced, but they let you solve real reporting problems without leaving Django’s ORM.
  - Use them when annotations and aggregates are not expressive enough.
  - References: [Window functions](https://docs.djangoproject.com/en/stable/ref/models/expressions/#window-expressions)
- **Expressions**: `Case`, `When`, `Value` for conditional annotations
  - Conditional expressions let query logic reflect domain rules such as status labels, priority buckets, and conditional counts.
  - They are a clean bridge between SQL CASE expressions and Django ORM annotations.
  - They are especially useful in reporting endpoints and admin summaries.
  - References: [Conditional expressions](https://docs.djangoproject.com/en/stable/ref/models/conditional-expressions/)
- **Full-text search (PostgreSQL)**: `SearchVector`, `SearchQuery`, `SearchRank`, `TrigramSimilarity`
  - PostgreSQL search support gives Django a strong middle ground before you need a dedicated search engine.
  - It is appropriate for many content-heavy apps when search quality matters but infrastructure should stay simple.
  - Search design still matters: ranking, stemming, indexing, and fallback behavior are all product decisions.
  - References: [PostgreSQL full-text search](https://docs.djangoproject.com/en/stable/ref/contrib/postgres/search/)

### 5.2 Caching

- **Cache backends**: Redis (`django-redis`), Memcached, database, file, local memory
  - Backend choice affects latency, operational complexity, and whether the cache can be shared across processes and hosts.
  - Local memory is fine for development, but production caching usually means a networked backend like Redis or Memcached.
  - Treat the backend as infrastructure that shapes what kinds of cache strategies are realistic.
  - References: [Django cache framework](https://docs.djangoproject.com/en/stable/topics/cache/), [`django-redis` repository](https://github.com/jazzband/django-redis)
- **Cache levels**:
  - **Per-site cache**: `UpdateCacheMiddleware` + `FetchFromCacheMiddleware`. Caches entire pages
  - **Per-view cache**: `@cache_page(60 * 15)` decorator
  - **Template fragment cache**: `{% cache 300 sidebar request.user.id %}`
  - **Low-level cache API**: `cache.get()`, `cache.set()`, `cache.delete()`, `cache.get_or_set()`
  - Django gives you multiple cache layers because the right unit of caching depends on what changes and how often.
  - Start with the narrowest useful cache scope; whole-site caching is powerful but rarely appropriate for personalized apps.
  - Low-level caching gives flexibility, but it also pushes invalidation responsibility onto your code.
  - References: [The per-site cache](https://docs.djangoproject.com/en/stable/topics/cache/#the-per-site-cache), [The per-view cache](https://docs.djangoproject.com/en/stable/topics/cache/#the-per-view-cache), [Template fragment caching](https://docs.djangoproject.com/en/stable/topics/cache/#template-fragment-caching), [Low-level cache API](https://docs.djangoproject.com/en/stable/topics/cache/#the-low-level-cache-api)
- **Cache key design**: Include user/permission context to avoid serving wrong data
  - Cache keys are part of your correctness model, not just a performance detail.
  - Any dimension that changes output meaningfully, such as user, language, tenant, or permissions, may need to be reflected in the key.
  - Bad key design causes subtle data leaks and stale-content bugs.
  - References: [Cache framework](https://docs.djangoproject.com/en/stable/topics/cache/)
- **Cache invalidation**: The hard problem. Strategies: time-based expiry, signal-based invalidation, versioned keys
  - Invalidation strategy determines whether the cache remains trustworthy as data changes.
  - Time-based expiry is simple but imprecise; event-driven invalidation is precise but operationally harder.
  - Versioned keys are often the cleanest compromise for derived content that changes in known ways.
  - References: [Cache framework](https://docs.djangoproject.com/en/stable/topics/cache/)
- **Session caching**: `SESSION_ENGINE = 'django.contrib.sessions.backends.cache'`
  - Caching sessions is a latency optimization with availability tradeoffs.
  - If the cache is volatile, session durability changes with it, which may or may not be acceptable.
  - Know whether you are optimizing reads, centralizing session storage, or both.
  - References: [Using cached sessions](https://docs.djangoproject.com/en/stable/topics/http/sessions/#using-cached-sessions)

### 5.3 Celery & Async Tasks

- **Setup**: Celery + Redis/RabbitMQ as broker
  - Task queues are for work that should not block the request/response cycle, such as email, exports, or long-running integrations.
  - Broker choice affects delivery guarantees, operational overhead, and ecosystem defaults.
  - Celery is not part of Django, but it is the most common queue pairing in Django deployments.
  - References: [Celery docs](https://docs.celeryq.dev/en/stable/)
- **Task definition**: `@shared_task` decorator
  - `@shared_task` decouples task declaration from a single Celery app instance and fits well in reusable Django apps.
  - Tasks should take simple, serializable inputs and re-fetch database state rather than carrying complex Python objects around.
  - Good task signatures are part of good distributed-system hygiene.
- **Calling tasks**: `.delay()`, `.apply_async()` with countdown/eta
  - `.delay()` is the simple enqueue path; `.apply_async()` is for scheduling, routing, or custom execution options.
  - Use the simple API until you genuinely need delivery timing or queue selection.
  - Treat asynchronous invocation as a different execution boundary, not just a function call with extra syntax.
- **Task patterns**:
  - **Fire and forget**: Send email, generate report
  - **Periodic tasks**: Celery Beat for cron-like scheduling
  - **Chords and chains**: Compose complex workflows
  - **Task retries**: `self.retry(exc=exc, countdown=60, max_retries=3)`
  - These patterns exist because background work has different orchestration needs than synchronous request code.
  - Retries and periodic scheduling are especially common and should be designed for idempotency from the start.
  - Complex workflows are useful, but often a sign you should simplify the business process before encoding it in task primitives.
- **Monitoring**: Flower for real-time Celery monitoring
  - Monitoring is necessary because async failures are otherwise easy to miss.
  - Queue depth, task age, retries, and worker failures all matter more than “did the code run locally.”
  - Treat task infrastructure as production infrastructure, not a black box.
  - References: [Flower docs](https://flower.readthedocs.io/)
- **Common pitfalls**: Don't pass model instances to tasks (pass PKs and re-fetch). Tasks can run out of order. Idempotency matters
  - Queue consumers may see stale data, duplicate deliveries, or reordered work, so task design must tolerate those realities.
  - Idempotency is a correctness requirement, not an optimization.
  - Async bugs are often data-consistency bugs disguised as infrastructure issues.
- **Django-Q2 / Huey**: Lighter alternatives to Celery for simpler needs
  - Smaller queues can be a better fit when your workload is limited and Celery’s ecosystem weight is unnecessary.
  - The real decision is about operational complexity versus features, not brand preference.
  - Pick the smallest tool that reliably matches the workload.
  - References: [`Django Q2` docs](https://django-q2.readthedocs.io/en/latest/), [Huey docs](https://huey.readthedocs.io/en/latest/)

### 5.4 Django's Async Support

- **Async views**: `async def my_view(request):` — supported since Django 4.1
  - Async views let Django handle coroutine-based request code directly under ASGI.
  - They are most helpful when request handling spends meaningful time waiting on external I/O rather than pure Python or database CPU work.
  - Async is a tool for specific workloads, not a universal speed upgrade.
  - References: [Asynchronous support](https://docs.djangoproject.com/en/stable/topics/async/)
- **`sync_to_async` / `async_to_sync`**: Bridge between sync and async code
  - These adapters let synchronous and asynchronous code interoperate, which is necessary because Django ecosystems often mix both styles.
  - They are useful, but frequent boundary crossing can erase the benefits of async and complicate reasoning.
  - Minimize crossings where you can.
  - References: [Async adapter functions](https://docs.djangoproject.com/en/stable/topics/async/#async-adapter-functions)
- **Async ORM**: `async for obj in MyModel.objects.all()`, `await MyModel.objects.aget(pk=1)` — growing support
  - Django’s async ORM support is evolving, so you should know what is available and what still falls back to synchronous work.
  - Use async ORM features where they simplify code, but do not assume the entire stack is uniformly async end-to-end.
  - Keep an eye on current docs because this is an area that changes over time.
  - References: [Asynchronous queries](https://docs.djangoproject.com/en/stable/topics/db/queries/#asynchronous-queries)
- **ASGI deployment**: Run under `uvicorn` or `daphne` for async support
  - Async code needs an ASGI deployment path to deliver the intended behavior.
  - Having an `asgi.py` file is not enough; the runtime server and surrounding stack must also support ASGI correctly.
  - Deployment architecture determines whether async features are actually available.
  - References: [How to deploy with ASGI](https://docs.djangoproject.com/en/stable/howto/deployment/asgi/)
- **When to use async**: WebSockets, long-polling, calling external APIs. The ORM is still mostly sync under the hood
  - Async is best when waiting dominates the request, such as websocket handling, streaming, or external API fan-out.
  - It is less compelling when the bottleneck is still synchronous database access or CPU-bound work.
  - Choose async because the workload benefits from concurrency, not because it sounds architecturally superior.
  - References: [Asynchronous support](https://docs.djangoproject.com/en/stable/topics/async/)

### 5.5 Security

- **CSRF protection**: How it works, `{% csrf_token %}`, `@csrf_exempt` dangers, CSRF with APIs (use token auth instead)
  - CSRF protection matters whenever a browser automatically includes credentials on cross-site requests.
  - Django’s CSRF system is strong by default for forms, but only if you keep the token flow intact and avoid unnecessary exemptions.
  - Learn the attack model, not just the template tag.
  - References: [CSRF protection](https://docs.djangoproject.com/en/stable/ref/csrf/)
- **XSS prevention**: Template auto-escaping, `|safe` dangers, `Content-Security-Policy` headers
  - XSS prevention in Django starts with auto-escaping and is reinforced by cautious output handling and browser policies.
  - Anytime you mark content safe, you are accepting responsibility for sanitization and context-appropriate encoding.
  - CSP is defense in depth, not a substitute for safe rendering.
  - References: [Security in Django](https://docs.djangoproject.com/en/stable/topics/security/), [Automatic HTML escaping](https://docs.djangoproject.com/en/stable/topics/templates/#automatic-html-escaping)
- **SQL injection**: The ORM protects you. Be careful with `raw()`, `extra()`, and `RawSQL()`
  - The ORM parameterizes queries for you in normal use, which is one of Django’s biggest security advantages.
  - Risk returns when you drop into raw SQL or interpolate untrusted values into query fragments.
  - Preserve the ORM’s safety guarantees whenever possible.
  - References: [SQL injection protection](https://docs.djangoproject.com/en/stable/topics/security/#sql-injection-protection), [Performing raw SQL queries](https://docs.djangoproject.com/en/stable/topics/db/sql/)
- **Clickjacking**: `X-Frame-Options` via `XFrameOptionsMiddleware`
  - Clickjacking protection controls whether your pages can be embedded in frames on other sites.
  - It matters especially for authenticated interfaces and admin surfaces.
  - This is simple to enable and rarely something you should skip.
  - References: [Clickjacking protection](https://docs.djangoproject.com/en/stable/ref/clickjacking/)
- **HTTPS**: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
  - HTTPS settings determine whether browsers consistently use secure transport and whether cookies stay off insecure channels.
  - HSTS is powerful and should be enabled deliberately once you control the deployment environment confidently.
  - Transport security is a deployment configuration topic with real application consequences.
  - References: [SecurityMiddleware](https://docs.djangoproject.com/en/stable/ref/middleware/#security-middleware), [Deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- **`django.middleware.security.SecurityMiddleware`**: Enable and configure all options
  - `SecurityMiddleware` centralizes several important browser-facing protections.
  - It is one of the core pieces of a production Django configuration and should be understood, not just left in place by habit.
  - Review its settings as part of every serious deployment.
  - References: [SecurityMiddleware](https://docs.djangoproject.com/en/stable/ref/middleware/#security-middleware)
- **Content Security Policy**: `django-csp` for CSP headers
  - CSP is usually managed through headers and is especially useful for modern frontends with stricter script policies.
  - Django does not ship CSP management directly, so third-party tooling fills that gap.
  - Treat CSP as part of a broader frontend trust model.
  - References: [How to use Django’s CSP support](https://docs.djangoproject.com/en/dev/howto/csp/), [CSP reference](https://docs.djangoproject.com/en/dev/ref/csp/), [`django-csp` docs](https://django-csp.readthedocs.io/)
- **Rate limiting**: `django-ratelimit` for view-level rate limiting
  - Rate limiting helps reduce abuse and accidental overload at the view layer.
  - It is helpful, but application-layer throttling should complement infrastructure controls, not replace them.
  - Choose rate limits based on actual endpoint sensitivity and traffic patterns.
  - References: [`django-ratelimit` docs](https://django-ratelimit.readthedocs.io/)
- **Security checklist**: Run `python manage.py check --deploy` before every production deploy
  - `check --deploy` is a lightweight safety net for catching obvious production misconfigurations.
  - It is not a penetration test, but it reliably catches settings mistakes that are easy to miss.
  - Make it part of your deploy muscle memory.
  - References: [Deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)

### 5.6 File Storage & Media

- **`MEDIA_ROOT` / `MEDIA_URL`**: Where uploaded files go
  - Media settings define the storage location and public URL base for user-uploaded content.
  - Keep media separate from static assets conceptually and operationally.
  - Uploaded files are runtime data, not build artifacts.
  - References: [Managing files](https://docs.djangoproject.com/en/stable/topics/files/)
- **Storage backends**: Local filesystem (dev), S3 (`django-storages` + `boto3`), GCS, Azure
  - Storage backend choice affects scalability, URL generation, permissions, and operational burden.
  - Local storage is fine for development; production often needs object storage or another shared system.
  - The backend is part of your deployment architecture, not just a code setting.
  - References: [File storage API](https://docs.djangoproject.com/en/stable/ref/files/storage/), [`django-storages` docs](https://django-storages.readthedocs.io/)
- **`DEFAULT_FILE_STORAGE`** setting (Django < 5.0) / `STORAGES` setting (Django 5.0+)
  - Django’s storage configuration evolved, so you should know which style your project version expects.
  - `STORAGES` is the modern, more explicit configuration model.
  - This is a version-sensitive area worth checking in the official docs when upgrading.
  - References: [`STORAGES`](https://docs.djangoproject.com/en/stable/ref/settings/#storages)
- **File upload handling**: `UploadedFile`, `InMemoryUploadedFile`, `TemporaryUploadedFile`
  - Django abstracts uploaded files through objects that reflect whether the file stayed in memory or spilled to disk.
  - Understanding these types matters when handling large uploads, streaming, and cleanup behavior.
  - File upload performance is partly about these lifecycle details.
  - References: [Uploaded files and upload handlers](https://docs.djangoproject.com/en/stable/ref/files/uploads/)
- **`FILE_UPLOAD_MAX_MEMORY_SIZE`**: Files larger than this are written to temp files
  - This setting controls when uploads stay in memory versus using temporary files.
  - It matters for resource usage, especially on small containers or upload-heavy systems.
  - Tuning it is part of capacity planning, not just convenience.
  - References: [`FILE_UPLOAD_MAX_MEMORY_SIZE`](https://docs.djangoproject.com/en/stable/ref/settings/#file-upload-max-memory-size)
- **Image processing**: `Pillow` for thumbnails, `django-imagekit` for on-the-fly processing
  - Image handling usually goes beyond upload storage into derivative generation, resizing, and format management.
  - Django relies on Pillow for image support, while higher-level image workflows often use third-party packages.
  - Treat image processing as a media pipeline concern.
  - References: [`ImageField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#imagefield), [`django-imagekit` docs](https://django-imagekit.readthedocs.io/en/latest/)
- **Serving in production**: Never serve media through Django. Use nginx, a CDN, or pre-signed S3 URLs
  - Django can serve media in development, but production media delivery should be delegated to infrastructure designed for files.
  - Offloading media improves performance, scalability, and security posture.
  - Keep application servers focused on application logic.
  - References: [How to deploy static files](https://docs.djangoproject.com/en/stable/howto/static-files/deployment/)

---

## Phase 6: Middleware, Signals, and Admin

### 6.1 Middleware

- **Request/response lifecycle**: Middleware order matters. Request goes top-down, response goes bottom-up
  - Middleware wraps request handling, so ordering determines which behaviors run before others and which responses get modified last.
  - Bugs in middleware stacks are often ordering bugs rather than code bugs.
  - Learn the flow well enough to reason about sessions, auth, CSRF, and custom instrumentation together.
  - References: [Middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/)
- **Writing custom middleware**: Class-based with `__init__` and `__call__`, or using `process_request`, `process_view`, `process_response`, `process_exception` hooks
  - Custom middleware is appropriate for cross-cutting concerns that apply broadly across requests.
  - Keep middleware narrow and request-oriented; if the behavior belongs to one view family, it probably is not middleware.
  - Understand hook timing before choosing where the logic lives.
  - References: [Writing your own middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/#writing-your-own-middleware)
- **Common custom middleware**: Request logging, timing, tenant identification, feature flags
  - These are good middleware candidates because they attach context or perform broad request-level behavior.
  - They are also easy to overuse, so push business logic back down into views or services when appropriate.
  - Middleware should make the request pipeline cleaner, not more magical.
- **Built-in middleware to know**: `SecurityMiddleware`, `SessionMiddleware`, `CommonMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`
  - These built-ins define much of Django’s default request behavior and are worth understanding individually.
  - Most application assumptions around users, sessions, redirects, and protection come from these layers.
  - If you know what each one contributes, debugging becomes much easier.
  - References: [Middleware reference](https://docs.djangoproject.com/en/stable/ref/middleware/)

### 6.2 Signals

- **Built-in signals**: `pre_save`, `post_save`, `pre_delete`, `post_delete`, `m2m_changed`, `request_started`, `request_finished`
  - Signals are framework hooks for events around model lifecycle and request lifecycle.
  - They are useful because they let behavior observe events without tightly coupling call sites.
  - They are also easy to abuse when core business logic becomes hidden behind side effects.
  - References: [Signals](https://docs.djangoproject.com/en/stable/topics/signals/), [Model signals](https://docs.djangoproject.com/en/stable/ref/signals/)
- **Connecting signals**: `@receiver` decorator, `Signal.connect()`
  - Signal registration should be explicit and easy to locate.
  - The decorator style is common because it keeps the handler definition and registration close together.
  - However you connect them, the import path and app loading sequence still matter.
  - References: [Listening to signals](https://docs.djangoproject.com/en/stable/topics/signals/#listening-to-signals)
- **`AppConfig.ready()`**: Where to import signal handlers
  - `ready()` is the standard place to ensure signal modules are imported once the app registry is prepared.
  - This avoids registration happening too early or not at all.
  - It is an app initialization concern, not a random import trick.
  - References: [`AppConfig.ready()`](https://docs.djangoproject.com/en/stable/ref/applications/#django.apps.AppConfig.ready)
- **When to use signals**: Decoupled side effects (audit logging, cache invalidation, sending notifications)
  - Signals are best for side effects that should happen because an event occurred, not because a caller remembered to trigger them.
  - Even then, keep the side effect lightweight or hand it off to background work.
  - Use signals for decoupling, not for hiding essential workflow rules.
  - References: [Signals](https://docs.djangoproject.com/en/stable/topics/signals/)
- **When NOT to use signals**: Business logic that should be explicit. Signals make debugging hard. Prefer explicit method calls or service layer functions
  - If a behavior is core to the business transaction, it is usually better expressed explicitly in the service or model method that owns the workflow.
  - Hidden control flow makes testing and debugging significantly harder.
  - A good default is to prefer explicit calls unless decoupling is clearly valuable.
- **Transaction awareness**: `post_save` fires before the transaction commits. Use `django.db.transaction.on_commit()` for side effects that need committed data
  - Transaction timing matters because side effects like emails or webhooks should not run for database work that later rolls back.
  - `on_commit()` is the right way to defer those actions until the write is durable.
  - This distinction is critical in reliable production systems.
  - References: [Database transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit)

### 6.3 Django Admin

- **`ModelAdmin` customization**: `list_display`, `list_filter`, `search_fields`, `list_editable`, `readonly_fields`, `fieldsets`, `ordering`, `list_per_page`
  - Admin configuration turns the built-in admin from a raw CRUD surface into a serious internal operations tool.
  - The most valuable customizations improve discoverability, filtering, and safe editing for staff users.
  - Think of admin as operator UX, not a developer afterthought.
  - References: [The Django admin site](https://docs.djangoproject.com/en/stable/ref/contrib/admin/), [ModelAdmin options](https://docs.djangoproject.com/en/stable/ref/contrib/admin/#modeladmin-options)
- **Inline models**: `TabularInline`, `StackedInline` for editing related objects
  - Inlines are useful when related data should be managed in the context of a parent object rather than on separate pages.
  - They are productive for moderate-sized related sets, but can become unwieldy for large or complex relationships.
  - Use them where they genuinely improve staff workflows.
  - References: [InlineModelAdmin objects](https://docs.djangoproject.com/en/stable/ref/contrib/admin/#inlinemodeladmin-objects)
- **Custom actions**: Bulk operations on selected objects
  - Admin actions are ideal for staff workflows like publishing, archiving, exporting, or reprocessing selected records.
  - Bulk actions should be safe, auditable, and clear about side effects.
  - Treat them like internal APIs with serious consequences.
  - References: [Admin actions](https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/)
- **`get_queryset()`**: Filter admin views per user. Override to add `select_related`/`prefetch_related`
  - Admin querysets can and should be tuned for both security and performance.
  - Filtering by staff role and optimizing related-object access is often necessary once the admin handles real data volume.
  - The admin is not exempt from application data-scope rules.
  - References: [ModelAdmin methods](https://docs.djangoproject.com/en/stable/ref/contrib/admin/#modeladmin-methods)
- **Custom admin views**: Add arbitrary views to the admin site
  - Custom admin views let you build staff dashboards, reports, or workflows without inventing a separate internal app shell.
  - They are valuable when the standard model CRUD interface is not enough.
  - Keep them clearly staff-oriented and permission-protected.
  - References: [The AdminSite class](https://docs.djangoproject.com/en/stable/ref/contrib/admin/#adminsite-objects)
- **Admin security**: It's a power tool, not a user-facing app. Restrict access. Use `django-admin-honeypot` to detect unauthorized access attempts
  - Admin access should be limited tightly because the interface is deliberately powerful.
  - Strong passwords, staff scoping, and secure deployment matter more here than cosmetic customization.
  - Third-party hardening tools help, but basic access control remains the first line of defense.
  - References: [Admin site](https://docs.djangoproject.com/en/stable/ref/contrib/admin/), [`django-admin-honeypot` docs](https://django-admin-honeypot.readthedocs.io/)
- **`django-unfold`** or **`django-jazzmin`**: Modern admin themes for better UX
  - Themes can improve staff usability, but they should follow functional customization, not replace it.
  - If the admin workflow is poor, styling alone will not fix it.
  - Django itself remains intentionally conservative about admin presentation.
  - References: [Unfold docs](https://unfoldadmin.com/docs/), [Jazzmin docs](https://django-jazzmin.readthedocs.io/)

**Practice**: Build a comprehensive admin for your blog/task manager. Include custom actions (publish/unpublish), inline editing, custom filters, and search.

---

## Phase 7: Testing

### 7.1 Testing Fundamentals

- **`TestCase` vs `TransactionTestCase`**: `TestCase` wraps each test in a transaction (faster). `TransactionTestCase` flushes the database (needed when testing transaction behavior)
  - Choose the base test class based on how much database realism the test needs.
  - `TestCase` is the default for speed and isolation; `TransactionTestCase` is for behavior that depends on real transaction boundaries.
  - Knowing the difference avoids misleading test results around commits and rollbacks.
  - References: [Testing tools](https://docs.djangoproject.com/en/stable/topics/testing/tools/)
- **`SimpleTestCase`**: No database access allowed. For testing utilities, template rendering, URL resolution
  - `SimpleTestCase` is for fast tests that do not need the database at all.
  - It helps you keep non-persistence tests lightweight and honest about their dependencies.
  - Use it when the code under test is pure request/response or helper logic.
  - References: [SimpleTestCase](https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase)
- **`LiveServerTestCase`**: Starts a real server for Selenium/browser tests
  - This class is for end-to-end browser-style tests where a real HTTP server matters.
  - It is slower than normal Django tests, so reserve it for flows where browser integration is the point.
  - Use it sparingly and intentionally.
  - References: [LiveServerTestCase](https://docs.djangoproject.com/en/stable/topics/testing/tools/#liveservertestcase)
- **`Client`**: `self.client.get()`, `.post()`, `.put()`, `.delete()`. Check `response.status_code`, `response.context`, `response.content`
  - The Django test client exercises views and middleware without needing a separate server process.
  - It is the default tool for integration-style app tests where the HTTP contract and rendered response both matter.
  - Learn what it does and does not simulate so your tests stay realistic.
  - References: [The test client](https://docs.djangoproject.com/en/stable/topics/testing/tools/#the-test-client)

### 7.2 Test Patterns

- **Fixtures vs factories**: Fixtures (`json`/`yaml` files) are brittle. Use `factory_boy` with `Faker` for dynamic test data
  - Factories usually produce more readable and maintainable tests because the data setup lives close to the scenario.
  - Fixtures can still help for stable reference datasets, but they often become opaque over time.
  - Optimize for test clarity, not just setup reuse.
  - References: [`factory_boy` docs](https://factoryboy.readthedocs.io/en/stable/)
- **`setUpTestData()`**: Class-level test data setup. Faster than `setUp()` for read-only data
  - This hook is a practical optimization for expensive shared test data.
  - Use it only for data that the tests will not mutate, or you will create confusing inter-test coupling.
  - It is one of the simplest ways to speed up Django test suites responsibly.
  - References: [TestCase data setup](https://docs.djangoproject.com/en/stable/topics/testing/tools/#testcase)
- **Mocking**: `unittest.mock.patch`, `patch.object`. Mock external services, not your own code
  - Mock external boundaries where determinism matters, but avoid mocking away the code you actually need confidence in.
  - Good mocks isolate network calls, queues, or time-sensitive dependencies while keeping your application logic real.
  - Over-mocking leads to brittle tests that only verify your test setup.
- **Testing signals**: Use `Signal.disconnect()` in tests when signals cause side effects
  - Signal-heavy code often needs explicit test control so unrelated side effects do not pollute assertions.
  - The better long-term fix is often making the important behavior more explicit and less signal-driven.
  - Use disconnection tactically, not as a blanket excuse for hidden control flow.
  - References: [Signals](https://docs.djangoproject.com/en/stable/topics/signals/)
- **Testing async code**: `async def test_*` methods with `IsolatedAsyncioTestCase`
  - Async tests require you to be clear about which layer is truly async and which remains synchronous underneath.
  - Use async-native testing only where it adds realism; otherwise simpler sync tests may still cover the behavior better.
  - This area often depends on both Django and Python test primitives.
- **Coverage**: `coverage run manage.py test` + `coverage report`. Aim for meaningful coverage, not 100%
  - Coverage metrics are useful as a signal for blind spots, not as a quality guarantee.
  - Optimize for tests that catch regressions in important logic and interfaces.
  - A smaller suite with strong assertions is better than a large suite with shallow checks.

### 7.3 What to Test

- **Models**: Validation, custom methods, managers, querysets, constraints
  - Model tests protect the data rules your application assumes everywhere else.
  - Focus on behavior that would be expensive or dangerous to discover only through higher-level view tests.
  - Querysets and constraints deserve explicit tests because they encode business meaning.
  - References: [Testing tools](https://docs.djangoproject.com/en/stable/topics/testing/tools/)
- **Views**: Status codes, template used, context data, redirects, permissions
  - View tests verify routing, permission behavior, and rendered context together.
  - They are especially valuable for catching regressions in entry-point behavior that model tests cannot see.
  - Test the contract, not just the happy path.
- **Forms**: Valid data, invalid data, edge cases, custom validation
  - Forms are where user input meets application rules, so they deserve direct tests.
  - Test both expected submissions and boundary conditions that should fail cleanly.
  - Form tests are often the cheapest place to prove validation correctness.
  - References: [Forms](https://docs.djangoproject.com/en/stable/topics/forms/)
- **API endpoints**: Request/response format, authentication, permissions, filtering, pagination
  - API tests should prove both behavior and client contract stability.
  - Include negative cases such as unauthorized access, invalid payloads, and empty datasets.
  - Your API consumers depend on these details remaining consistent.
- **Middleware**: Request/response modification
  - Middleware tests are warranted when middleware adds meaningful request context, blocks access, or modifies responses centrally.
  - Because middleware is cross-cutting, bugs can affect large portions of the app.
  - Keep tests focused on the specific cross-cutting rule.
  - References: [Middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/)
- **Integration tests**: Full request cycles through multiple components
  - Integration tests are where you verify that the pieces work together under realistic conditions.
  - They are slower and broader, so use them for workflows that matter rather than every code path.
  - A balanced suite uses unit, integration, and end-to-end tests intentionally.

### 7.4 Performance Testing

- **`assertNumQueries()`**: Assert exact number of database queries in a code block
  - This is one of Django’s best tools for preventing performance regressions in ORM-heavy code.
  - Use it around views, serializers, and helpers where query shape matters.
  - It turns query discipline into a testable contract.
  - References: [`assertNumQueries()`](https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TransactionTestCase.assertNumQueries)
- **`override_settings()`**: Test with different settings
  - `override_settings()` is the clean way to vary configuration-dependent behavior without polluting global state.
  - It is especially useful for cache, storage, email, and feature-flag-like settings behavior.
  - Use it to keep tests explicit about the environment assumptions they need.
  - References: [`override_settings`](https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.override_settings)
- **`RequestFactory`**: Create request objects without going through middleware (faster than `Client`)
  - `RequestFactory` is useful for testing view logic in isolation when middleware behavior is irrelevant.
  - It is faster and more targeted, but it also means you must provide request attributes middleware would usually attach.
  - Use it when you want focused view-unit tests rather than request-stack integration tests.
  - References: [The request factory](https://docs.djangoproject.com/en/stable/topics/testing/advanced/#the-request-factory)

**Practice**: Write tests for everything you've built so far. Use `factory_boy`. Aim for >80% meaningful coverage. Use `assertNumQueries` to catch N+1 queries.

---

## Phase 8: Advanced Patterns

### 8.1 Service Layer / Fat Models vs Thin Models

- **Fat models**: Business logic in model methods. Works for simple apps, gets messy at scale
  - Keeping logic on models can work well when behavior is tightly coupled to one aggregate and the workflow is simple.
  - It starts to break down when operations span many models, external services, or transaction boundaries.
  - The real issue is not “fat” versus “thin,” but clarity of ownership.
- **Service layer**: Business logic in standalone functions/classes. Models handle data, services handle operations
  - A service layer is useful when workflows are broader than one model and need orchestration, side effects, or transaction management.
  - It makes dependencies more explicit and often improves testability.
  - Django does not prescribe a service layer, so this is an architectural pattern you apply intentionally.
- **When to use each**: Services when logic involves multiple models, external calls, or complex orchestration
  - Choose the location of logic based on the workflow’s scope and side effects.
  - The goal is not purity; it is keeping business behavior obvious and maintainable.
  - If a model method starts coordinating too much, that is usually the signal to extract.
- **Example pattern**:
  - A service function usually owns the full workflow boundary: validation-adjacent coordination, transactions, external calls, and async follow-up work.
  ```python
  # services/order.py
  def place_order(user, cart_items):
      with transaction.atomic():
          order = Order.objects.create(user=user)
          for item in cart_items:
              OrderItem.objects.create(order=order, **item)
          PaymentService.charge(user, order.total)
          send_order_confirmation.delay(order.pk)
      return order
  ```
  - Notice what the example centralizes: transaction handling, multi-model writes, payment side effects, and async follow-up work.
  - That is exactly the kind of orchestration that becomes awkward when buried in a model’s `save()` method.
  - References: [Database transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/)

### 8.2 Multi-Tenancy

- **Shared database, shared schema**: Filter by `tenant_id` column. Simplest approach
  - This is the most common starting point because it keeps infrastructure simple and scales product development well.
  - Its success depends on disciplined queryset scoping and strong authorization boundaries.
  - Most bugs here are tenant-isolation bugs, not schema bugs.
- **Shared database, separate schemas**: PostgreSQL schemas per tenant. `django-tenants`
  - Schema-per-tenant adds stronger separation at the database level, but it raises migration and operational complexity.
  - It is useful when tenant isolation needs to be stronger than application-level filtering alone.
  - Choose it only if the isolation benefits justify the maintenance cost.
  - References: [`django-tenants` docs](https://django-tenants.readthedocs.io/)
- **Separate databases**: One database per tenant. Most isolated, most complex
  - Separate databases maximize isolation and customer-specific control, but they multiply operational burdens significantly.
  - This pattern fits high-isolation or enterprise demands more than typical SaaS defaults.
  - Provisioning, migrations, and observability all get harder.
- **Middleware-based tenant resolution**: Identify tenant from subdomain, header, or URL
  - Tenant resolution is the entry-point concern that determines the rest of the request’s data scope.
  - Middleware is a common fit because it attaches tenant context early for downstream layers to use.
  - Whatever strategy you choose, make it explicit and test it heavily.
  - References: [Middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/)

### 8.3 Soft Deletes

- **Pattern**: Add `deleted_at` field, override `delete()` to set it, custom manager that filters deleted objects
  - Soft delete preserves recoverability and history at the cost of making “active rows only” a permanent application concern.
  - The pattern is simple conceptually but has ripple effects across managers, uniqueness, admin behavior, and analytics.
  - Treat soft delete as a data-lifecycle strategy, not just a convenience hack.
- **`django-safedelete`**: Library that implements this pattern
  - A library can save time if soft delete semantics are central to the app and you want battle-tested defaults.
  - Still understand the underlying model-manager-queryset pattern before adopting one.
  - Third-party tooling should support your policy, not define it for you.
  - References: [`django-safedelete` docs](https://django-safedelete.readthedocs.io/)
- **Considerations**: Foreign key cascades, unique constraints, admin visibility
  - These are the hard parts: related-row visibility, restoring data safely, and ensuring uniqueness still behaves sensibly.
  - Soft delete complexity grows with relational depth, so decide early whether you really need it.
  - References: [Managers](https://docs.djangoproject.com/en/stable/topics/db/managers/), [Constraints reference](https://docs.djangoproject.com/en/stable/ref/models/constraints/)

### 8.4 Audit Logging

- **`django-auditlog`**: Automatic change tracking on models
  - Audit logging is about traceability, not convenience.
  - Automatic tools are useful when you need broad coverage across many models with consistent metadata.
  - Decide first what level of auditing the business or compliance context actually needs.
  - References: [`django-auditlog` docs](https://django-auditlog.readthedocs.io/en/latest/)
- **`django-simple-history`**: Stores a copy of the model on every save
  - History tables are useful when you need object snapshots and temporal reconstruction, not just event messages.
  - They come with storage and noise costs, so scope them deliberately.
  - Snapshot history and event logs solve related but different problems.
  - References: [`django-simple-history` docs](https://django-simple-history.readthedocs.io/en/stable/)
- **Custom approach**: Middleware that captures `request.user`, signals or `save()` override that logs changes
  - Custom audit designs let you capture exactly the metadata you care about, including actor and request context.
  - The tradeoff is maintenance and consistency across code paths.
  - If you build your own, be explicit about when logging happens and what counts as a change.
- **What to log**: Who changed what, when, and from what value to what value
  - Good audit logs answer accountability questions clearly and reconstruct change intent.
  - Avoid logging everything indiscriminately if it makes real investigations harder.
  - Audit usefulness depends on signal quality, not sheer volume.

### 8.5 Feature Flags

- **`django-waffle`**: Feature flags, switches, and samples
  - Feature flags let you separate deployment from release and reduce the risk of large changes.
  - They are especially useful for staged rollouts, internal previews, and operational kill switches.
  - Django itself does not include a full feature-flag framework, so this is ecosystem territory.
  - References: [`django-waffle` docs](https://waffle.readthedocs.io/en/latest/)
- **Patterns**: Flag per user, per group, per percentage. Gradual rollouts
  - Different targeting strategies support different rollout goals, from internal testing to production canaries.
  - Percentage rollouts are helpful only if monitoring is in place to tell you whether the rollout is healthy.
  - Flags should have clear ownership and removal plans.
- **Database-backed vs config-backed**: Tradeoffs of each
  - Database-backed flags are dynamic and operable; config-backed flags are simpler and often safer for coarse environment toggles.
  - The right choice depends on whether runtime changes matter.
  - Avoid turning flags into permanent architecture.

### 8.6 Webhooks

- **Receiving webhooks**: Dedicated views with signature verification, idempotency keys, async processing
  - Incoming webhooks are untrusted external events and should be treated as such.
  - Verify signatures, acknowledge quickly, and hand off slow processing to background tasks.
  - Idempotency is essential because webhook providers commonly retry deliveries.
- **Sending webhooks**: Celery tasks with retry logic, payload signing, delivery logging
  - Outgoing webhooks are integration products in their own right and need observability, retries, and authenticity guarantees.
  - Background delivery keeps your core transactions responsive and resilient to receiver downtime.
  - Delivery history is often necessary for support and debugging.
- **Patterns**: Event-driven architecture with webhook dispatching on model changes
  - Webhooks are one way to externalize domain events, but they should map to meaningful business events rather than arbitrary saves.
  - Event names, payload versions, and retry semantics all become external contracts.
  - Design webhook systems with the same care you apply to public APIs.

---

## Phase 9: Deployment & DevOps

### 9.1 WSGI/ASGI Servers

- **Gunicorn**: The standard WSGI server. Configure workers (`2 * CPU + 1`), worker class (`sync` vs `gevent` vs `uvicorn.workers.UvicornWorker`)
  - Gunicorn is a common process manager for synchronous Django deployments and many hybrid setups.
  - Worker count and worker class tuning should be driven by workload and memory profile, not copied blindly.
  - Understand what each worker model implies before tuning.
- **Uvicorn**: ASGI server for async Django. Use with Gunicorn as process manager
  - Uvicorn is the common ASGI runtime when you need async Django or websockets.
  - It can run standalone or under a process manager depending on your deployment style.
  - Pair server choice with the actual concurrency features your app uses.
- **Daphne**: Django Channels' ASGI server
  - Daphne is most relevant in Channels-based deployments.
  - If you are not using Channels or websocket-heavy features, Uvicorn is often the simpler default.
  - Server selection should follow the runtime needs of the app.
  - References: [How to deploy with WSGI](https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/), [How to deploy with ASGI](https://docs.djangoproject.com/en/stable/howto/deployment/asgi/)

### 9.2 Static Files

- **`collectstatic`**: Gathers static files from all apps into `STATIC_ROOT`
  - `collectstatic` is the build step that turns scattered static assets into a deployable static tree.
  - It is part of deployment, not request handling.
  - If static files are broken in production, this command is one of the first places to inspect.
  - References: [The staticfiles app](https://docs.djangoproject.com/en/stable/ref/contrib/staticfiles/), [Deploying static files](https://docs.djangoproject.com/en/stable/howto/static-files/deployment/)
- **`WhiteNoise`**: Serve static files directly from the WSGI app. Simple and effective
  - WhiteNoise is a pragmatic choice for many deployments that want simple static serving without a separate asset server.
  - It is especially popular on platforms where app and static delivery are colocated.
  - Django does not ship it, but it integrates closely with Django’s staticfiles system.
  - References: [WhiteNoise docs](https://whitenoise.readthedocs.io/)
- **CDN integration**: `STATIC_URL` pointing to a CDN, `ManifestStaticFilesStorage` for cache-busting with hashed filenames
  - CDN-backed static delivery improves latency and offloads traffic from app servers.
  - Hashed filenames are critical so aggressive caching remains safe after deploys.
  - Asset URL strategy is part of deployment design, not just template syntax.
  - References: [Staticfiles storage](https://docs.djangoproject.com/en/stable/ref/contrib/staticfiles/#storage-staticfilesstorage), [`STORAGES`](https://docs.djangoproject.com/en/stable/ref/settings/#storages)
- **`django-compressor`**: Compress and bundle CSS/JS
  - Compression and bundling are useful when Django still owns part of the frontend asset pipeline.
  - In modern setups, this may overlap with dedicated frontend build tools.
  - Use it where it fits the stack rather than by habit.
  - References: [`django-compressor` docs](https://django-compressor.readthedocs.io/)

### 9.3 Docker

- **Multi-stage Dockerfile**: Builder stage for dependencies, slim runtime image
  - Multi-stage builds keep runtime images smaller and reduce attack surface by separating build tooling from execution.
  - They also make dependency installation and system-package layering more deliberate.
  - Container structure affects startup time, image size, and deploy reliability.
- **`docker-compose`**: Django + PostgreSQL + Redis + Celery worker + Celery beat
  - Compose is useful for local environments where several cooperating services need to start together predictably.
  - It is mostly a developer-experience tool, not necessarily a production orchestration strategy.
  - Use it to make the local stack resemble reality where it matters.
- **Entrypoint script**: Run migrations, collect static files, start Gunicorn
  - Entrypoints often encode the boot-time contract of the container, including setup steps and process startup.
  - Be careful not to hide slow or risky production behavior in opaque shell scripts.
  - Startup scripts should stay deterministic and observable.
- **Health checks**: `/health/` endpoint that checks database connectivity
  - Health checks tell orchestration systems whether the app is alive and whether key dependencies are reachable.
  - Separate liveness from readiness when possible so restarts and rollout gating behave correctly.
  - A good health check is simple, fast, and intentional.

### 9.4 CI/CD

- **GitHub Actions / GitLab CI**: Run tests, linting, type checking on every push
  - CI should give fast, trustworthy feedback on correctness before code reaches production.
  - The most valuable baseline is tests plus static quality checks that the team consistently trusts.
  - A noisy or flaky CI pipeline loses its value quickly.
- **Pre-commit hooks**: `black`, `ruff`, `isort`, `mypy`
  - Pre-commit catches cheap issues before they even reach CI.
  - It works best when hooks are fast and aligned with what CI will enforce.
  - Use local automation to reduce review noise.
- **Deployment pipeline**: Test -> Build Docker image -> Push to registry -> Deploy
  - A deployment pipeline should turn a validated code state into a reproducible artifact and then roll it out predictably.
  - The artifact boundary is important because it avoids “works in CI, differs in production” drift.
  - Keep deployment steps explicit and auditable.
- **Database migrations in CI**: Run `migrate --check` to verify no pending migrations
  - Migration checks prevent a common class of deployment mistake where code and migration state drift apart.
  - This is a lightweight but valuable gate for Django projects.
  - Schema discipline belongs in automation, not just reviewer memory.
  - References: [`migrate`](https://docs.djangoproject.com/en/stable/ref/django-admin/#migrate)

### 9.5 Monitoring & Observability

- **Error tracking**: Sentry (`sentry-sdk[django]`). Captures exceptions with full context
  - Error tracking turns production failures into actionable events with request, user, and stack context.
  - It is one of the highest-leverage additions for operating Django apps in production.
  - Django integrates well with these tools, but they remain ecosystem tooling.
  - References: [Sentry Django docs](https://docs.sentry.io/platforms/python/guides/django/)
- **Application Performance Monitoring (APM)**: Sentry Performance, Datadog, New Relic
  - APM helps you understand latency distribution, endpoint hotspots, and dependency bottlenecks over time.
  - It matters once local profiling is no longer enough to explain production behavior.
  - Observability is about trend visibility, not just debugging one incident.
- **Logging**: Configure Django's `LOGGING` dict. Log to stdout in containers. Structured logging with `structlog`
  - Logging should be deliberate about audience and structure: operators need searchable, contextual logs, not random print-like output.
  - In containerized systems, stdout logging is typically the right transport choice.
  - Good logging complements metrics and tracing rather than duplicating them poorly.
  - References: [Logging](https://docs.djangoproject.com/en/stable/topics/logging/), [structlog docs](https://www.structlog.org/en/stable/)
- **Health checks**: `django-health-check` for database, cache, storage, Celery connectivity
  - Health-check tooling is useful when readiness depends on multiple infrastructure services.
  - Keep checks proportional to what orchestration or monitoring actually needs.
  - Overly expensive health checks can become their own failure mode.
  - References: [`django-health-check` docs](https://django-health-check.readthedocs.io/en/stable/)
- **Metrics**: Prometheus with `django-prometheus`. Track request duration, database query count, cache hit rate
  - Metrics are how you notice degradation before users report it.
  - Focus on a few high-signal measurements first: latency, error rate, saturation, and queue depth.
  - Metrics are operational feedback loops, not vanity dashboards.
  - References: [`django-prometheus` repository](https://github.com/django-commons/django-prometheus), [Prometheus docs](https://prometheus.io/docs/introduction/overview/)

### 9.6 Scaling

- **Horizontal scaling**: Multiple Gunicorn processes behind a load balancer
  - Horizontal scaling is usually the first scaling lever because stateless Django app processes are easy to multiply.
  - It only works cleanly if stateful concerns like sessions, cache, and media are already externalized appropriately.
  - App scaling and state management are inseparable design concerns.
- **Database scaling**: Read replicas, connection pooling (PgBouncer), partitioning
  - Database scale work is often more about query discipline and connection management than raw machine size.
  - Replicas, pooling, and partitioning each solve different problems and should not be treated as interchangeable.
  - Optimize query shape before reaching for architectural complexity.
- **Caching layers**: Redis for sessions + cache + Celery broker
  - Shared infrastructure components can serve multiple roles, but coupling roles onto one service also couples failure modes.
  - Be intentional about whether one Redis cluster should handle all responsibilities.
  - Scaling decisions should consider blast radius as well as convenience.
- **CDN**: Cloudflare, CloudFront for static/media files
  - CDNs remove a major class of traffic from the app and improve asset delivery globally.
  - They are especially valuable once static and media traffic dominates edge bandwidth.
  - Offloading delivery is often cheaper than scaling app servers.
- **Task queue scaling**: Multiple Celery workers, priority queues, separate queues for different task types
  - Queue scaling is about matching workers to workload characteristics, not just adding more consumers.
  - Separate queues help isolate urgent work from slow batch jobs.
  - This is usually necessary before queue-heavy apps feel reliably responsive.

---

## Phase 10: Real-World Ecosystem

### 10.1 Essential Third-Party Packages

| Package | Purpose |
|---|---|
| [`Django REST framework`](https://www.django-rest-framework.org/) | API development |
| [`drf-spectacular`](https://drf-spectacular.readthedocs.io/en/stable/) | OpenAPI/Swagger schema generation |
| [`django-filter`](https://django-filter.readthedocs.io/en/stable/) | Declarative queryset filtering |
| [`django-allauth`](https://docs.allauth.org/en/latest/) | Authentication, registration, social auth |
| [`django-cors-headers`](https://github.com/adamchainz/django-cors-headers) | CORS handling for API backends |
| [`django-environ`](https://django-environ.readthedocs.io/) | Environment variable parsing |
| [`django-extensions`](https://django-extensions.readthedocs.io/) | `shell_plus`, `show_urls`, `graph_models`, `runserver_plus` |
| [`django-debug-toolbar`](https://django-debug-toolbar.readthedocs.io/) | SQL query inspection, profiling |
| [`django-redis`](https://github.com/jazzband/django-redis) | Redis cache backend |
| [`django-storages`](https://django-storages.readthedocs.io/) | S3, GCS, Azure storage backends |
| [`django-celery-beat`](https://django-celery-beat.readthedocs.io/) | Database-backed periodic task scheduling |
| [`factory_boy`](https://factoryboy.readthedocs.io/en/stable/) | Test data factories |
| [`django-silk`](https://github.com/jazzband/django-silk) | Request/SQL profiling |
| [`django-import-export`](https://django-import-export.readthedocs.io/) | CSV/Excel import/export in admin |
| [`django-guardian`](https://django-guardian.readthedocs.io/en/stable/) | Object-level permissions |
| [`django-simple-history`](https://django-simple-history.readthedocs.io/en/stable/) | Model change history |
| [`django-health-check`](https://django-health-check.readthedocs.io/en/stable/) | Application health monitoring |
| [`WhiteNoise`](https://whitenoise.readthedocs.io/) | Static file serving |
| [`sentry-sdk`](https://docs.sentry.io/platforms/python/guides/django/) | Error tracking |
| [`djangorestframework-simplejwt`](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/) | JWT authentication for DRF |
| [`django-oauth-toolkit`](https://django-oauth-toolkit.readthedocs.io/en/latest/) | OAuth2 provider support |
| [`django-ratelimit`](https://django-ratelimit.readthedocs.io/) | View-level rate limiting |
| [`django-prometheus`](https://github.com/django-commons/django-prometheus) | Prometheus metrics export |
| [`django-waffle`](https://waffle.readthedocs.io/en/latest/) | Feature flags and gradual rollouts |
| [`django-tenants`](https://django-tenants.readthedocs.io/) | PostgreSQL schema-based multi-tenancy |
| [`django-auditlog`](https://django-auditlog.readthedocs.io/en/latest/) | Model change/event auditing |
| [`django-safedelete`](https://django-safedelete.readthedocs.io/) | Soft delete patterns |
| [`django-imagekit`](https://django-imagekit.readthedocs.io/en/latest/) | Image processing and derived images |
| [`django-admin-honeypot`](https://django-admin-honeypot.readthedocs.io/) | Fake admin endpoint / honeypot |
| [`django-unfold`](https://unfoldadmin.com/docs/) | Modern admin theme and extensions |
| [`django-jazzmin`](https://django-jazzmin.readthedocs.io/) | Modern admin theme |

- Use this list as a toolbox, not a checklist. Mature Django projects often need only a subset of these packages.
- Prefer adding packages that solve a real operational or product problem rather than importing ecosystem complexity by default.
- Before adopting any package, check maintenance status, compatibility with your Django version, and whether the feature already exists in core Django.
- References: [Django ecosystem landing point](https://docs.djangoproject.com/en/stable/), [The `django-admin` command reference](https://docs.djangoproject.com/en/stable/ref/django-admin/), [Celery docs](https://docs.celeryq.dev/en/stable/), [Channels docs](https://channels.readthedocs.io/)

### 10.2 Code Quality Tools

- **`ruff`**: Linter and formatter (replaces `flake8`, `isort`, `black`, `pyflakes`)
  - Consolidated tooling reduces configuration sprawl and speeds up local and CI checks.
  - The real goal is consistent, low-friction feedback, not tool minimalism for its own sake.
  - Pick a toolchain the team will actually keep enabled.
  - References: [Ruff docs](https://docs.astral.sh/ruff/)
- **`mypy` + `django-stubs`**: Static type checking for Django code
  - Type checking is especially valuable in larger Django codebases where dynamic patterns otherwise hide interface drift.
  - `django-stubs` improves the usefulness of typing in a framework that is otherwise highly dynamic.
  - Use typing where it clarifies contracts rather than mechanically annotating everything.
  - References: [mypy docs](https://mypy.readthedocs.io/en/stable/), [`django-stubs` repository](https://github.com/typeddjango/django-stubs)
- **`pre-commit`**: Git hooks for automated code quality checks
  - Pre-commit moves cheap quality checks as far left as possible.
  - It works best when it mirrors CI and stays fast enough that developers keep it enabled.
  - Local automation should reduce review noise, not add workflow friction.
  - References: [pre-commit docs](https://pre-commit.com/)
- **`djhtml`**: Django template indentation
  - Template formatting tools help keep large server-rendered templates readable and reviewable.
  - This matters more than it sounds once templates become complex and long-lived.
  - Formatting is not the goal; readability is.
  - References: [`djhtml` repository](https://github.com/rtts/djhtml)

### 10.3 Django Channels (WebSockets)

- **Consumers**: WebSocket handlers (analogous to views)
  - Consumers are the Channels abstraction for long-lived connection handling rather than one-shot HTTP requests.
  - They require a different mental model because connection lifecycle and message events matter more than a single response.
  - Learn them only if your product actually needs real-time behavior.
  - References: [Channels docs](https://channels.readthedocs.io/)
- **Channel layers**: Redis-backed pub/sub for real-time communication
  - Channel layers are how multiple processes coordinate real-time events across connections.
  - They are infrastructure as much as application code, so deployment reliability matters.
  - Redis is common because it fits the required messaging pattern well.
  - References: [Channels docs](https://channels.readthedocs.io/), [`channels_redis` repository](https://github.com/django/channels_redis)
- **Routing**: URL routing for WebSocket connections
  - Channels uses its own routing setup because websocket connection handling is not ordinary Django URL dispatch.
  - You still need the same discipline around organization and ownership of routes.
  - Routing clarity matters even more in real-time systems.
  - References: [Routing docs](https://channels.readthedocs.io/en/stable/topics/routing.html)
- **Use cases**: Chat, live notifications, real-time dashboards, collaborative editing
  - Real-time features justify their complexity only when latency and push delivery materially improve the product.
  - If polling is good enough, it is often cheaper operationally.
  - Choose websockets because the use case needs them.
- **Groups**: Broadcast messages to multiple connected clients
  - Groups are the main abstraction for fan-out in Channels-based applications.
  - They let you target rooms, tenants, or topic subscribers without tracking every socket manually.
  - Broadcast design is part of the domain model, not just transport plumbing.
  - References: [Channel layers and groups](https://channels.readthedocs.io/en/stable/topics/channel_layers.html)

---

## Capstone Projects

Build these to demonstrate job-ready Django skills:

### Project 1: SaaS Task Manager
- Multi-tenant architecture (shared DB, filtered by organization)
  - Implement tenant scoping in every queryset path and verify cross-organization isolation with explicit tests.
- Custom user model with roles (admin, member, viewer)
  - Model roles so both UI behavior and API permissions can be enforced from one coherent authorization strategy.
- REST API with DRF (CRUD for projects, tasks, comments)
  - Keep resource boundaries clear and make project-level ownership rules visible in `get_queryset()` and permissions.
- Real-time notifications via WebSockets
  - Use websocket events only for updates that genuinely benefit from push delivery, such as assignment changes or new comments.
- Celery tasks for email notifications and report generation
  - Make tasks idempotent and ensure notifications are triggered after successful commits, not before.
- Full test suite with factory_boy
  - Cover tenant isolation, role permissions, API behavior, and async side-effect boundaries, not just happy-path CRUD.
- Docker Compose setup with PostgreSQL and Redis
  - Keep the local stack close enough to production that auth, queues, and websockets behave realistically.
- CI/CD pipeline with GitHub Actions
  - Automate tests, linting, and image builds so the project demonstrates deployable engineering discipline.

This project is strong because it exercises tenant scoping, auth, async work, and API design in one realistic business domain. Focus on organization-level isolation and permission rules first; they shape every later feature. A good implementation demonstrates discipline across models, views, APIs, background tasks, and deployment.

### Project 2: E-Commerce Platform
- Product catalog with categories, variants, and inventory tracking
  - Design inventory so variant-level stock changes remain auditable and safe under concurrent order placement.
- Shopping cart with session-based storage (anonymous) and database storage (authenticated)
  - Plan how anonymous carts merge into authenticated carts so the user experience and persistence rules stay consistent.
- Order processing with state machine (pending -> paid -> shipped -> delivered)
  - Make state transitions explicit and protected so invalid transitions cannot happen accidentally.
- Payment integration (Stripe) with webhook handling
  - Treat webhooks as the source of truth for asynchronous payment updates and design for retries and duplicate delivery.
- Admin dashboard with custom actions and reports
  - Use the admin to support operational workflows such as fulfillment, refunds, and order investigation.
- Full-text search with PostgreSQL
  - Tune search ranking and indexing enough that product discovery feels intentional rather than bolted on.
- Caching strategy (product pages, cart, user sessions)
  - Cache carefully so performance improves without leaking personalized cart or pricing state across users.
- Audit logging for all order state changes
  - Capture who changed order state, when it changed, and what triggered the transition for support and compliance visibility.

This project is useful because it forces you to handle money-adjacent workflows, state transitions, and operational correctness. The hard parts are consistency and side effects: inventory, payments, retries, and webhook idempotency. Build it with explicit transaction boundaries and strong admin tooling.

### Project 3: Content Management System
- Rich content editor with media uploads to S3
  - Make media storage part of the publishing workflow rather than a disconnected upload mechanism.
- Draft/review/publish workflow with permissions
  - Model editorial states and role-based permissions so approval flow is explicit and testable.
- Versioned content with diff view
  - Preserve history in a way editors can actually inspect and compare, not just store passively.
- SEO optimization (sitemaps, meta tags, structured data)
  - Treat SEO output as part of the rendering contract and verify it on published pages, not just in templates.
- API for headless frontend consumption
  - Keep the content API stable and explicit so a separate frontend could consume it without depending on admin-oriented assumptions.
- Scheduled publishing with Celery Beat
  - Use scheduled tasks to move content between states safely and predictably at publish time.
- Performance optimization (caching, query optimization, CDN)
  - Optimize the high-traffic read path first: article detail pages, media delivery, and content listing queries.
- Monitoring with Sentry and structured logging
  - Capture rendering failures, publish-task issues, and storage problems with enough context to debug production incidents quickly.

This project tests content workflows, editorial permissions, and rendering performance rather than commerce or multi-tenancy. It is a good place to demonstrate polished admin/editor experience and careful publishing-state design. Strong implementations show both server-rendered Django competence and API-ready architecture.

---

## Study Methodology

1. **Read the Django docs first** — they are exceptionally well written. Use this guide as a roadmap, the official docs as the textbook
   - Read the primary docs before blog posts or tutorials when learning a feature deeply; Django’s docs are unusually strong.
   - Use this guide to choose the next topic, then use the official docs to learn the actual mechanics and edge cases.
2. **Build, don't just read** — every section above has a practice exercise. Do them
   - Reading creates recognition; building creates recall and judgment.
   - Turn each section into working code, tests, and at least one debugging session where you inspect what Django is doing underneath.
3. **Use `django-debug-toolbar` from day one** — understanding the SQL your code generates is the single biggest lever for writing production-quality Django
   - Django skill compounds when you stop treating the ORM as magic.
   - Inspect queries, count them, and learn to predict them before you run the page.
4. **Read Django's source code** — it's clean, well-documented Python. Read the ORM, the auth system, the admin. Understanding internals makes you a better user
   - Source reading is how you move from framework user to framework engineer.
   - Focus on subsystems you actively use so the code answers real questions you have encountered.
5. **Contribute to open source Django projects** — read how production apps are structured
   - Studying real projects teaches tradeoffs the official docs intentionally abstract away.
   - Reviewing mature apps will sharpen your instincts around settings layout, query discipline, test style, and deployment conventions.
6. **Write tests for everything** — testing is a non-negotiable skill for professional Django development
   - Tests are part of Django mastery because the framework makes integration-heavy systems easy to build and easy to regress.
   - Use tests to lock down behavior, performance assumptions, and permission boundaries as you learn.

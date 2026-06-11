# Django Study Guide

A depth-first guide to Django — the models, the ORM, the request cycle, the forms machinery, the admin, Django REST Framework, caching, async, and deployment — for engineers who know Python well and want to build production web applications without re-deriving twenty years of web-framework wisdom from scratch. It assumes fluency with Python (classes, decorators, context managers — the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md) covers the layer underneath), basic SQL (the [Postgres guide](POSTGRES.md) goes deep on the database Django most often sits on), and HTTP fundamentals. It does **not** assume you've ever run `django-admin startproject`.

The throughline is a single mental model: **Django is the framework that makes the 80% case trivial and the 20% case possible.** Authentication, admin interfaces, form validation, CSRF protection, database migrations, query building — the things every web application needs — are built in, integrated with each other, and secure by default. That's the 80%. The remaining 20% — custom query expressions, middleware, storage backends, authentication backends — is reachable because almost every default is a documented, overridable hook. The skill of a senior Django engineer is not memorizing APIs; it's knowing *which layer* of the framework owns a problem, accepting the framework's defaults until you have a measured reason not to, and knowing where the escape hatches are when you do. Fighting Django is the most common failure mode; the second most common is not knowing the ORM well enough to see the SQL your Python is generating.

Three more mental models recur throughout and are worth stating up front. First, **a request is a value passed through a pipeline**: server → middleware (top-down) → URL resolver → view → middleware again (bottom-up) → response. Almost every "why is Django doing this?" question is answered by locating the behavior in that pipeline (Part 2). Second, **a QuerySet is a description of a query, not its results** — a lazy, chainable, immutable query builder that only touches the database when something forces evaluation (Part 4). Third, **migrations are version control for your schema** — a linear-ish history of diffs, committed alongside the code that depends on them (Part 5).

How to use this guide: Parts 1–5 are the foundation (configuration, the pipeline, models, queries, migrations) and reward being read in order; Parts 6–10 cover the server-rendered application layer; Parts 11–17 are production concerns that can be read as needed. Code samples form one continuous example — a small publishing application — so later parts reuse models and functions defined earlier.

Primary references: the [official Django documentation](https://docs.djangoproject.com/en/stable/) (genuinely among the best documentation of any open-source project — read it *first*, not as a last resort), the [Django REST Framework docs](https://www.django-rest-framework.org/), *[Two Scoops of Django](https://www.feldroy.com/two-scoops-press)* (Audrey & Daniel Feldroy — the book of production conventions), Will Vincent's *[Django for Professionals](https://learndjango.com/books/)* and [learndjango.com](https://learndjango.com/), [Adam Johnson's blog](https://adamj.eu/tech/) (a Django technical-board member writing the best ongoing Django material on the internet), and the indispensable class-explorer sites [Classy Class-Based Views](https://ccbv.co.uk/) and [Classy DRF](https://www.cdrf.co/).

---

## Table of Contents

1. [Part 1 — The Shape of Django: Philosophy, Project Anatomy & Settings](#part-1--the-shape-of-django-philosophy-project-anatomy--settings)
2. [Part 2 — The Request/Response Cycle, URLs & Middleware](#part-2--the-requestresponse-cycle-urls--middleware)
3. [Part 3 — Models: Designing the Schema](#part-3--models-designing-the-schema)
4. [Part 4 — The ORM: QuerySets Are Descriptions, Not Results](#part-4--the-orm-querysets-are-descriptions-not-results)
5. [Part 5 — Migrations: Version Control for Your Schema](#part-5--migrations-version-control-for-your-schema)
6. [Part 6 — Views: Functions, Classes & the Honest Trade-off](#part-6--views-functions-classes--the-honest-trade-off)
7. [Part 7 — Templates](#part-7--templates)
8. [Part 8 — Forms & ModelForms](#part-8--forms--modelforms)
9. [Part 9 — Authentication, Authorization & the Custom User Model](#part-9--authentication-authorization--the-custom-user-model)
10. [Part 10 — The Admin](#part-10--the-admin)
11. [Part 11 — Django REST Framework (and Django Ninja)](#part-11--django-rest-framework-and-django-ninja)
12. [Part 12 — Caching & Performance](#part-12--caching--performance)
13. [Part 13 — Signals, Transactions & Where Business Logic Lives](#part-13--signals-transactions--where-business-logic-lives)
14. [Part 14 — Async Django, Celery & Background Work](#part-14--async-django-celery--background-work)
15. [Part 15 — Testing](#part-15--testing)
16. [Part 16 — Security](#part-16--security)
17. [Part 17 — Deployment & Operations](#part-17--deployment--operations)

---

## Part 1 — The Shape of Django: Philosophy, Project Anatomy & Settings

Django calls itself "the web framework for perfectionists with deadlines," and the tagline is more precise than it sounds. It is a **batteries-included, opinionated, full-stack** framework: ORM, migrations, templating, forms, auth, admin, caching, email, i18n, and security middleware ship in the box and — crucially — are designed to work *with each other*. A `ModelForm` knows how to validate against your model's constraints; the admin renders itself from your model definitions; the auth system's permission checks appear in views, templates, and the admin alike. This integration is the actual product. Flask or FastAPI give you a smaller, sharper core and make you assemble the rest; Django gives you the assembled thing and asks you to learn its conventions. Neither is wrong — but they fail differently. With Django you occasionally fight the framework; with micro-frameworks you occasionally discover you've spent six months hand-rolling a worse Django.

### When Django Is the Wrong Tool

Honesty up front, because choosing the right tool matters more than mastering the wrong one:

- **Heavy real-time workloads.** If the *core* of your product is WebSockets, live presence, or sub-second push to thousands of connections, Django's request/response heritage shows. Django Channels works (Part 14), but a Node/Go/Elixir service — or a separate real-time sidecar next to a Django app — is often the better architecture. Real-time as a *feature* (live notifications on a CRUD app) is fine; real-time as the *product* is a stretch.
- **A swarm of tiny microservices.** Django's value is its integrated breadth. A service that exposes three endpoints and owns one table pays Django's conceptual weight for nothing — FastAPI or Go is leaner there. (Conversely, "microservices" carved out of what should have been one Django monolith is a far more common and far more expensive mistake. A well-modularized Django monolith scales to enormous team sizes — Instagram runs on one.)
- **CPU-bound or ultra-low-latency services.** The bottleneck is Python itself (see the GIL discussion in the [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md)), not Django, but Django won't save you either.

For everything else — CRUD-heavy products, SaaS backends, internal tools, content sites, REST APIs with relational data — Django's 80% coverage is a genuine multi-year head start.

### Project Anatomy

`django-admin startproject config .` followed by `python manage.py startapp blog` gives you the two-level structure everything else builds on: a **project** (the settings/URL/WSGI shell, conventionally named `config` or after the site) containing multiple **apps** (Python packages owning a cohesive slice of domain: models, views, templates, tests). A mature layout looks like:

```text
myproject/
├── manage.py                  # project-local CLI: knows your settings module
├── config/
│   ├── settings/
│   │   ├── base.py            # shared defaults
│   │   ├── development.py     # DEBUG=True, SQLite or local Postgres, debug toolbar
│   │   ├── production.py      # hardened security, real cache, real DB
│   │   └── test.py            # fast hashers, in-memory email, throwaway DB
│   ├── urls.py                # root URLconf: includes each app's URLs
│   ├── wsgi.py                # entry point for WSGI servers (gunicorn)
│   └── asgi.py                # entry point for ASGI servers (uvicorn/daphne)
├── apps/
│   ├── accounts/              # custom user model lives here (Part 9 — do this FIRST)
│   ├── blog/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── migrations/
│   │   └── tests/
│   └── ...
└── templates/                 # project-level templates and overrides
```

Apps are the unit of modularity. The test for "should this be one app or two?" is whether you could describe each one in a sentence without the word "and." `manage.py` is the project-local command-line entry point (it sets `DJANGO_SETTINGS_MODULE` for you); `django-admin` is the same machinery without a default settings module, useful mainly for `startproject`. Docs: [applications](https://docs.djangoproject.com/en/stable/ref/applications/), [django-admin and manage.py](https://docs.djangoproject.com/en/stable/ref/django-admin/).

### Settings: One Module, Many Environments

Django configures itself from exactly one Python module, named by the `DJANGO_SETTINGS_MODULE` environment variable. At startup it imports that module, then builds everything — the app registry, the middleware stack, template engines, database connections — from what it finds there. The single-file `settings.py` that `startproject` generates does not survive contact with a second environment, which is why the **settings package** split above is the universal production convention (canonized in [Two Scoops of Django](https://www.feldroy.com/two-scoops-press)). Shared defaults live in `base.py`; each environment imports and overrides:

```python
# config/settings/base.py
from pathlib import Path
import environ

env = environ.Env()                      # django-environ: typed env-var parsing
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY")    # no default: crash loudly if missing
DEBUG = False                            # safe default; development.py flips it

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    # local
    "apps.accounts",
    "apps.blog",
]

DATABASES = {"default": env.db("DATABASE_URL")}   # postgres://user:pw@host/db
AUTH_USER_MODEL = "accounts.User"                 # Part 9: set before first migrate
```

```python
# config/settings/production.py
from .base import *  # noqa

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # e.g. ["example.com"]
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30           # raise once you trust your TLS setup
CACHES = {"default": env.cache("REDIS_URL")}
```

Secrets — `SECRET_KEY`, database credentials, API keys — come from the environment, never the repo; [django-environ](https://django-environ.readthedocs.io/) or [python-decouple](https://pypi.org/project/python-decouple/) handle the parsing, and a committed `.env.example` documents what must be set. Note the philosophy embedded in `SECRET_KEY = env("DJANGO_SECRET_KEY")` with no default: production-critical values should **fail fast at startup**, not silently fall back to something insecure.

```bash
# .env.example — committed; documents the contract without leaking values
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_SECRET_KEY=change-me
DATABASE_URL=postgres://postgres:postgres@localhost:5432/myproject
REDIS_URL=redis://localhost:6379/0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

Three settings deserve a paragraph each because they're the ones that cause incidents. **`DEBUG`** turns on the detailed error pages that show settings, stack traces, and local variables — invaluable locally, a data breach in production; it also disables several caching and security behaviors. Production is `DEBUG = False`, no exceptions. **`ALLOWED_HOSTS`** is the Host-header allowlist Django enforces when `DEBUG` is off; it exists to block [Host-header attacks](https://docs.djangoproject.com/en/stable/topics/security/#host-header-validation) (password-reset poisoning, cache poisoning). Set it to your real domains — `["*"]` re-opens the hole. **`SECRET_KEY`** signs sessions, password-reset tokens, and everything else built on `django.core.signing`; if it leaks, attackers can forge all of those, and rotating it invalidates every outstanding session and token. Before any deploy, run `python manage.py check --deploy` — it audits exactly these settings against the [deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/).

One ordering subtlety in `INSTALLED_APPS`: when two apps ship a template at the same path, the **first app listed wins** (with the standard app-directories loader), which is why overriding admin templates requires your app to precede `django.contrib.admin`. App loading is also when `AppConfig.ready()` runs — the sanctioned place to register signal handlers (Part 13). Docs: [settings topic guide](https://docs.djangoproject.com/en/stable/topics/settings/), [settings reference](https://docs.djangoproject.com/en/stable/ref/settings/).

A short tour of what actually happens at startup, because it explains several rules above: the server imports `wsgi.py`/`asgi.py`, which triggers `django.setup()` — the settings module is imported (once), the **app registry** populates by importing each `INSTALLED_APPS` entry's models and calling its `AppConfig.ready()`, middleware is instantiated from `MIDDLEWARE`, and the URLconf loads lazily on the first request. This is why `INSTALLED_APPS` order matters, why signal registration belongs in `ready()` (Part 13), and why import-time code that touches models before setup completes dies with the infamous `AppRegistryNotReady`.

### WSGI and ASGI

The generated `wsgi.py` and `asgi.py` are the two doorways into your application. **WSGI** is the classic synchronous Python web-server interface — one request, one worker thread/process, gunicorn's home turf. **ASGI** is its async-capable successor — coroutines, long-lived connections, WebSockets — served by uvicorn or daphne. The files themselves are inert; what matters is which server you point at which one (Part 17). The honest default in 2026: **WSGI remains the simpler, battle-hardened choice for a standard database-backed Django app**, and ASGI is what you deploy when you actually use async views or Channels (Part 14). Docs: [WSGI deployment](https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/), [ASGI deployment](https://docs.djangoproject.com/en/stable/howto/deployment/asgi/).

If you remember one thing from Part 1: **Django's value is integration — and its configuration is one Python module, selected by `DJANGO_SETTINGS_MODULE`, split into base + per-environment files, with secrets in the environment and `check --deploy` run before every release.**

---

## Part 2 — The Request/Response Cycle, URLs & Middleware

Everything Django does happens inside one pipeline, and internalizing it is the single highest-leverage piece of Django knowledge — it's the framework's equivalent of Linux's "everything is a file." When a request arrives:

```text
web server (gunicorn/uvicorn)
  → WSGI/ASGI handler builds an HttpRequest
    → middleware, top of MIDDLEWARE list downward   (request phase)
      → URL resolver matches a path → view
        → view returns an HttpResponse (or raises)
      ← middleware, bottom of the list upward       (response phase)
  ← handler serializes the HttpResponse
```

Each middleware is an onion layer wrapping everything below it. `SecurityMiddleware` sees the request first and the response last; the view sits at the center. **Order in the `MIDDLEWARE` setting is therefore behavior, not style**: `AuthenticationMiddleware` must follow `SessionMiddleware` because it reads the session to figure out who `request.user` is; `CsrfViewMiddleware` must run before any view that processes a POST. Most "why is `request.user` an AnonymousUser?" and "why is my header missing?" bugs are ordering bugs. Docs: [middleware topic guide](https://docs.djangoproject.com/en/stable/topics/http/middleware/), [middleware reference](https://docs.djangoproject.com/en/stable/ref/middleware/) (read the one-paragraph description of every default middleware once — it pays for itself forever).

The default stack, annotated — worth reading top-to-bottom once while picturing the onion:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",           # HTTPS redirect, HSTS, security headers
    "whitenoise.middleware.WhiteNoiseMiddleware",               # static files (Part 17), if used
    "django.contrib.sessions.middleware.SessionMiddleware",     # attaches request.session
    "django.middleware.common.CommonMiddleware",                # APPEND_SLASH and friends
    "django.middleware.csrf.CsrfViewMiddleware",                # token check on unsafe methods (Part 16)
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # request.user — needs sessions above it
    "django.contrib.messages.middleware.MessageMiddleware",     # one-shot flash messages
    "django.middleware.clickjacking.XFrameOptionsMiddleware",   # X-Frame-Options: DENY
]
```

### Writing Middleware

The modern style is a callable factory — a function (or class) that takes `get_response` and returns a callable that wraps it. Everything before the `get_response(request)` call runs on the way in; everything after runs on the way out:

```python
# apps/core/middleware.py
import time, logging

logger = logging.getLogger("request_timing")

def timing_middleware(get_response):
    def middleware(request):
        start = time.monotonic()
        response = get_response(request)          # everything below this layer
        duration_ms = (time.monotonic() - start) * 1000
        response["X-Request-Duration"] = f"{duration_ms:.1f}ms"
        logger.info("%s %s -> %d in %.1fms",
                    request.method, request.path, response.status_code, duration_ms)
        return response
    return middleware
```

Add `"apps.core.middleware.timing_middleware"` to `MIDDLEWARE` and every request is timed. Middleware is for **cross-cutting concerns** — timing, request IDs, tenant resolution from a subdomain, feature-flag context. If the behavior belongs to one view family rather than the whole site, it should be a decorator or mixin instead; middleware that contains business logic is a smell. The older hook style (`process_view`, `process_exception`, `process_template_response`) still exists for the cases where you need to intervene at those specific points — see [writing your own middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/#writing-your-own-middleware).

When a view raises instead of returning, the pipeline handles that too: `Http404` becomes the 404 response (your `404.html` once `DEBUG=False`), `PermissionDenied` a 403, `SuspiciousOperation` a 400, and anything else a logged 500 — reported to your error tracker (Part 17) and rendered as the debug page or your `500.html` depending on `DEBUG`. Middleware can intercept this path via the `process_exception` hook. The practical consequence: *raising the right exception is the error-handling strategy* in Django; you rarely construct error responses by hand.

### URL Routing

The URL resolver is the pipeline's switchboard. Django starts at `ROOT_URLCONF`, walks the `urlpatterns` list in order, descends into `include()`s, and dispatches to the first final match — first match wins, so order matters within a file. Each app owns its own `urls.py`; the root URLconf just assembles them:

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("blog/", include("apps.blog.urls")),
    path("api/v1/", include("apps.api.urls")),
]

# apps/blog/urls.py
from django.urls import path
from . import views

app_name = "blog"                                  # namespace for reverse()
urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path("<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
]
```

Three habits make routing scale. First, **use `path()` with converters** (`<int:pk>`, `<slug:slug>`, `<uuid:id>`) rather than `re_path()` regexes — converters validate and coerce the segment before your view ever runs, so `views.post_detail(request, pk)` receives an actual `int`. `re_path()` survives for genuinely irregular patterns and for reading older codebases. Second, **name every URL and namespace every app** (`app_name = "blog"`), then *never hardcode a path again*: Python code calls `reverse("blog:post_detail", kwargs={"slug": post.slug})` (or `post.get_absolute_url()`), templates use `{% url "blog:post_detail" post.slug %}`, and renaming a route becomes a one-line change. Use `reverse_lazy()` in places evaluated at import time — class attributes like `success_url` on CBVs — where the URLconf isn't loaded yet. Third, keep app URLconfs flat and boring; cleverness in routing is paid for at debugging time. Docs: [URL dispatcher](https://docs.djangoproject.com/en/stable/topics/http/urls/), [reverse()](https://docs.djangoproject.com/en/stable/ref/urlresolvers/#reverse).

A small operational note: `CommonMiddleware` with `APPEND_SLASH = True` (the default) redirects `/blog/my-post` to `/blog/my-post/` when only the slashed pattern exists — convenient for human-facing sites, but be deliberate about slash conventions for APIs, where a surprise 301 on a POST loses the request body in most clients.

### Request and Response Objects

One data-structure detail saves an occasional afternoon: `request.GET` and `request.POST` are `QueryDict`s — multi-valued mappings, because HTML allows repeated parameters (`?tag=a&tag=b`). `request.GET["tag"]` returns the *last* value; `request.GET.getlist("tag")` returns them all. Checkbox groups and multi-selects are the usual place this surfaces.

The `HttpRequest` your view receives has already been enriched by the pipeline: `request.user` (from `AuthenticationMiddleware`), `request.session` (from `SessionMiddleware`), `request.GET`/`request.POST` (parsed query string and form body), `request.FILES`, `request.headers` (a case-insensitive mapping — `request.headers["X-Request-Id"]`). Your job is to return an `HttpResponse` subclass that matches intent: `JsonResponse({"ok": True})` for JSON, `HttpResponseRedirect` (usually via the `redirect()` shortcut) after successful POSTs, `FileResponse` for files, `StreamingHttpResponse` for responses too large to buffer. Raising `Http404` anywhere in a view produces the standard 404 path, which is why the `get_object_or_404(Post, slug=slug)` shortcut is idiomatic rather than lazy. Docs: [request/response reference](https://docs.djangoproject.com/en/stable/ref/request-response/).

If you remember one thing from Part 2: **a request flows down the middleware list, through the URL resolver, into one view, and the response flows back up — middleware order is behavior, every URL has a name, and nothing about the pipeline is magic once you can recite it.**

---

## Part 3 — Models: Designing the Schema

A Django model is a Python class that *is* a database table: each attribute is a column, each instance is a row, and the class's `Meta` options carry table-level policy (ordering, indexes, constraints). This is the framework's center of gravity — the admin, forms, serializers, and migrations are all derived from model definitions — so time spent getting models right is repaid by every other layer. Here is a realistic pair of models exercising the decisions that matter:

```python
# apps/blog/models.py
from django.conf import settings
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    """Abstract base: shared columns, no table of its own."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Post(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,          # never a hardcoded User import (Part 9)
        on_delete=models.PROTECT,          # an author with posts cannot be deleted
        related_name="posts",
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    body = models.TextField()
    summary = models.CharField(max_length=500, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", through="PostTag", related_name="posts")

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),  # the listing query
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="draft") | models.Q(published_at__isnull=False),
                name="published_posts_have_published_at",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)


class PostTag(models.Model):
    """Explicit M2M through-table: the relationship itself carries data."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "tag"], name="unique_post_tag"),
        ]
```

Unpack the decisions, because each encodes a rule worth knowing.

Two small conventions in the example carry outsized weight. Every model defines `__str__`, because that string is what the admin, the shell, log lines, and `ModelChoiceField` dropdowns display — a model without it shows as `Post object (42)` everywhere, forever. And `get_absolute_url()` gives the model one canonical address: `redirect(post)` and `CreateView`'s default success URL both use it, templates link with `{{ post.get_absolute_url }}`, and the URL logic lives in exactly one place.

**Field choice is domain semantics, not storage shape.** `DecimalField(max_digits=10, decimal_places=2)` for money, never `FloatField` (floats accumulate rounding errors — the same IEEE-754 reality covered in every language guide in this repo). `SlugField`/`UUIDField` when identifiers appear in URLs. `JSONField` for genuinely schemaless payloads — and not as an excuse to avoid designing columns you'll later need to filter on. `DateTimeField` everywhere implies the `USE_TZ = True` default: Django stores UTC and converts at the edges; never store local times. Full menu: [model field reference](https://docs.djangoproject.com/en/stable/ref/models/fields/).

**`null` vs `blank` is the classic interview distinction because it's a real layering distinction.** `null=True` is database-level — may the column store SQL `NULL`? `blank=True` is validation-level — may a form/serializer leave it empty? `summary` above uses the canonical string-field pattern, `blank=True, default=""` *without* `null=True`: allowing both `NULL` and `""` gives you two indistinguishable "empty" states that quietly break filters and unique constraints. For non-string optional fields like `published_at`, `null=True, blank=True` together is correct.

**`on_delete` is a business rule wearing a keyword argument.** `CASCADE` ("delete my children with me") is right when child rows are meaningless without the parent — comments on a post. `PROTECT` is right when deletion must be blocked while references exist — you don't silently destroy a user's published work. `SET_NULL` (requires `null=True`) keeps the row but orphans the reference — "deleted user" attribution. Choosing by reflex instead of by domain is how production data disappears. Always set `related_name` explicitly: `user.posts.all()` reads like the domain; the auto-generated `post_set` does not.

**`ManyToManyField` with `through`** is what you reach for the moment the *relationship itself* has attributes — who added the tag, when, in what role. A plain M2M is just a hidden two-column join table; making it explicit upgrades it to a real domain object you can query and constrain. Docs: [extra fields on M2M](https://docs.djangoproject.com/en/stable/topics/db/models/#extra-fields-on-many-to-many-relationships).

**`Meta` is table-level policy.** Default `ordering` (use sparingly — it silently adds `ORDER BY` to every query, including ones feeding `GROUP BY`); `indexes` matching your actual query patterns (the composite `["status", "-published_at"]` index exists because the listing page filters on status and sorts by date — see the [Postgres guide](POSTGRES.md) for why column order in composite indexes matters); and `constraints` — prefer modern [`UniqueConstraint`](https://docs.djangoproject.com/en/stable/ref/models/constraints/)/`CheckConstraint` over the legacy `unique_together`, because constraints are named, support conditions (`condition=Q(...)` gives you partial unique indexes), and **enforce invariants in the database**, where they hold even against code that bypasses model validation.

**Primary keys: integers by default, UUIDs by decision.** Unless told otherwise, Django adds an auto-incrementing `BigAutoField` named `id`. Sequential integers are compact, join-friendly, and easy to eyeball in logs — keep them unless you have a reason not to. The reason that usually arrives: integer IDs in public URLs leak volume and invite enumeration (`/orders/10452/`). The pattern with the best trade-offs is a *second* identifier — `public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)` — used in URLs and APIs while the integer PK keeps doing the internal work. Making the UUID the actual primary key works too, at the cost of larger indexes and poor insert locality with random UUIDv4 (B-tree mechanics in the [Postgres guide](POSTGRES.md)); Django 5.2's composite primary keys cover the legacy-schema cases.

**Validation has a trapdoor.** Field `validators=[...]`, `choices` enforcement, and `unique` checks run during `full_clean()` — which forms and DRF serializers call, **but `save()` does not**. `Post.objects.create(...)` happily writes a value every validator would reject. The moral, restated: validators are UX; invariants that must *always* hold belong in database constraints. And one relationship shape not shown above: a model can reference itself — `models.ForeignKey("self", on_delete=models.CASCADE, null=True, related_name="replies")` is how threaded comments, org charts, and follower graphs are modeled; just decide explicitly whether cycles are legal, because Django won't decide for you.

**Model inheritance: one pattern to use, two to know.** *Abstract base classes* (`TimeStampedModel` above) copy fields into each child's table — no joins, no surprises; this is the 90% case. *Multi-table inheritance* (inheriting from a concrete model) creates a hidden `OneToOneField` and a join on every access — almost never what you want; prefer explicit one-to-ones. *Proxy models* reuse the same table with different Python behavior (a different default manager or admin presentation) — a niche but clean tool. Docs: [model inheritance](https://docs.djangoproject.com/en/stable/topics/db/models/#model-inheritance).

Two Django 5.x additions worth knowing: [`db_default`](https://docs.djangoproject.com/en/stable/ref/models/fields/#db-default) puts the default *in the database* (so non-Django writers get it too), and [`GeneratedField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#generatedfield) maps to SQL generated columns — both examples of Django steadily exposing more of the database instead of hiding it.

If you remember one thing from Part 3: **models are where domain rules become schema — `on_delete` is a business decision, constraints belong in the database, string fields use `blank=True, default=""` not `null=True`, and abstract base classes are the inheritance pattern you actually use.**

---

## Part 4 — The ORM: QuerySets Are Descriptions, Not Results

The most important sentence about the Django ORM: **a `QuerySet` is a lazy, immutable description of a query — not the query's results.** `Post.objects.filter(status="published")` touches no database. It builds a data structure describing *intent*. Each chained method returns a *new* QuerySet with a refined description, which is why chaining is free:

```python
qs = Post.objects.filter(status=Post.Status.PUBLISHED)   # no SQL yet
qs = qs.exclude(author__is_active=False)                  # still no SQL
qs = qs.order_by("-published_at")[:20]                    # STILL no SQL (slicing = LIMIT)
print(qs.query)                                           # inspect the SQL it WOULD run

for post in qs:                                           # ← evaluation: ONE query runs here
    print(post.title)
```

Evaluation happens when something needs actual rows: iteration, `list(qs)`, `len(qs)`, `bool(qs)`, `qs[0]`, serialization, template rendering. After the first evaluation the QuerySet caches its results, so iterating twice doesn't query twice — but two *separate* QuerySets built from the same expression are two queries. This lazy-builder model explains nearly every ORM performance story, including the most famous one. Docs: [QuerySets are lazy](https://docs.djangoproject.com/en/stable/topics/db/queries/#querysets-are-lazy), [QuerySet API reference](https://docs.djangoproject.com/en/stable/ref/models/querysets/).

Make a habit of *reading* the SQL while you learn, not just trusting the ORM. Three tools, in increasing weight: `str(qs.query)` prints the approximate SQL of any queryset; `connection.queries` (with `DEBUG=True`) lists every query the current process has run with timings — `from django.db import connection; connection.queries[-5:]` in `shell_plus` after exercising some code is a five-second audit; and [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) does the same per-page with tracebacks showing *which line* triggered each query. ORM fluency is really SQL fluency wearing Python syntax — the engineers who write fast Django are the ones who can predict the query before they run the code.

### The N+1 Story, Told Properly

Here is the bug every Django developer ships at least once. The view is innocent; the template is innocent; together they're a disaster:

```python
# view
posts = Post.objects.filter(status="published")[:50]      # 1 query

# template
# {% for post in posts %}
#   {{ post.title }} — by {{ post.author.username }}      ← 1 query PER POST
# {% endfor %}
```

The listing query fetched the posts' columns — including `author_id`, but not the author *rows*. Each `post.author` access finds no cached author, so the lazy ORM helpfully runs `SELECT ... FROM users WHERE id = %s`. Fifty posts: 1 + 50 = **51 queries**. The page works perfectly in development with 5 rows and falls over in production with 500. Nothing is broken; the ORM did exactly what each line asked. That's the trap: **the ORM makes related-object access look free, and it isn't.**

Two fixes, chosen by relationship cardinality:

```python
# ForeignKey / OneToOne (single-valued): JOIN it into the same query
posts = (Post.objects.filter(status="published")
         .select_related("author")[:50])                  # 1 query, with a JOIN

# ManyToMany / reverse FK (multi-valued): second query + in-Python stitch
posts = (Post.objects.filter(status="published")
         .select_related("author")
         .prefetch_related("tags")[:50])                  # 2 queries total
```

[`select_related`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related) follows single-valued relations with a SQL `JOIN` — one query, wider rows. It *can't* be used for many-valued relations, because joining them would multiply rows. [`prefetch_related`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related) handles those: it runs one extra query per relation (`SELECT ... WHERE post_id IN (...)`) and stitches the results onto the instances in Python — trading a constant number of queries for memory. When the default prefetch fetches too much, a [`Prefetch`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-objects) object scopes it: `prefetch_related(Prefetch("comments", queryset=Comment.objects.filter(is_approved=True), to_attr="approved_comments"))`.

The discipline that makes this stick: run [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) from day one and glance at the query count on every page you build, and pin the count in tests with `assertNumQueries` (Part 15). Senior Django engineers don't avoid N+1 by being careful; they avoid it by making query counts *visible and tested*.

### F and Q: Pushing Logic into the Database

[`F()` expressions](https://docs.djangoproject.com/en/stable/ref/models/expressions/#f-expressions) reference a column's value *inside the query*, which buys you two things. First, column-vs-column comparisons: `Post.objects.filter(updated_at__gt=F("published_at"))`. Second — the important one — **race-free updates**:

```python
# WRONG: read-modify-write. Two concurrent requests both read 41, both write 42.
post = Post.objects.get(pk=pk)
post.view_count += 1
post.save()

# RIGHT: the database does the arithmetic atomically.
Post.objects.filter(pk=pk).update(view_count=F("view_count") + 1)
# SQL: UPDATE blog_post SET view_count = view_count + 1 WHERE id = %s
```

[`Q()` objects](https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects) express boolean logic that keyword arguments can't — keyword filters can only AND:

```python
from django.db.models import Q

Post.objects.filter(
    Q(title__icontains=query) | Q(body__icontains=query),   # OR
    ~Q(author=request.user),                                  # NOT
    status="published",                                       # ANDed with the rest
)
```

Q objects also compose dynamically (`q |= Q(tag__name=t)` in a loop), which makes them the backbone of search and optional-filter code.

### Aggregation, Annotation, and the Rest of the Toolbox

[`aggregate()`](https://docs.djangoproject.com/en/stable/topics/db/aggregation/) collapses a queryset to summary values (`Post.objects.aggregate(total=Count("id"), latest=Max("published_at"))` returns a dict); **`annotate()`** adds a computed column to *each row* — `Author.objects.annotate(post_count=Count("posts")).order_by("-post_count")` is the idiomatic "authors by productivity" query. The classic pitfall: annotating with `Count` across *two* multi-valued joins multiplies rows through the join, inflating counts — fix with `Count("posts", distinct=True)`, and when an aggregation looks wrong, read the SQL (`str(qs.query)`) before guessing.

The rest of the toolbox, with the judgment attached: `values()`/`values_list()` return dicts/tuples instead of model instances — use when you need columns, not objects (`values_list("id", flat=True)` for ID lists). `exists()` and `count()` push the question to the database instead of fetching rows to answer it in Python — `if qs.exists():` not `if qs:` on large tables. `only()`/`defer()` load a subset of columns — a measured optimization for wide tables, with the trap that touching a deferred field costs an extra query per instance. `bulk_create()`/`bulk_update()` batch writes for imports and backfills — vastly faster, but they skip `save()` overrides and signals, which is fine *if you know that's what you're choosing*. `iterator(chunk_size=2000)` streams large result sets without materializing them. `get_or_create()`/`update_or_create()` are only race-safe when backed by a real unique constraint — they catch the `IntegrityError` and retry the get; without the constraint, concurrent calls happily create duplicates. [`Subquery`/`OuterRef`](https://docs.djangoproject.com/en/stable/ref/models/expressions/#subquery-expressions) express correlated subqueries ("each author's latest post title") without leaving the ORM. And when the ORM genuinely can't express it, [`raw()` and `connection.cursor()`](https://docs.djangoproject.com/en/stable/topics/db/sql/) exist — always parameterized, never string-formatted (Part 16).

### The Expression Library: Conditionals, Window Functions, and Search

Annotations get more interesting once you discover that almost any SQL expression has an ORM spelling. [Conditional expressions](https://docs.djangoproject.com/en/stable/ref/models/conditional-expressions/) (`Case`/`When`) compute per-row values from logic; [database functions](https://docs.djangoproject.com/en/stable/ref/models/database-functions/) (`Coalesce`, `Lower`, `Concat`, `TruncMonth`, …) push formatting and bucketing into SQL:

```python
from django.db.models import Case, Count, Value, When
from django.db.models.functions import TruncMonth

# Per-row conditional: label posts by age without fetching them into Python
Post.objects.annotate(
    freshness=Case(
        When(published_at__gte=week_ago, then=Value("new")),
        When(published_at__gte=month_ago, then=Value("recent")),
        default=Value("archive"),
    )
)

# Monthly publishing report: GROUP BY a computed value
(Post.objects.published()
 .annotate(month=TruncMonth("published_at"))
 .values("month")
 .annotate(count=Count("id"))
 .order_by("month"))
```

[Window functions](https://docs.djangoproject.com/en/stable/ref/models/expressions/#window-expressions) (`Window` with `Rank`, `RowNumber`, `Lag`, …) answer "each row in the context of its peers" questions — rank each author's posts by views without N queries or Python-side sorting. And on Postgres, `django.contrib.postgres` exposes [full-text search](https://docs.djangoproject.com/en/stable/ref/contrib/postgres/search/) — `SearchVector`/`SearchQuery`/`SearchRank` for ranked, stemmed search, `TrigramSimilarity` for fuzzy matching — real search capability that postpones the day you need a dedicated search engine by years, provided you add the matching GIN index. The meta-lesson: before exporting rows to Python for computation, check whether the [expressions reference](https://docs.djangoproject.com/en/stable/ref/models/expressions/) can say it in SQL — the database is better at set math than your for-loop will ever be.

### Custom Managers and QuerySets: A Domain Vocabulary

Query logic scattered across views rots. The fix is to give your model a chainable query vocabulary:

```python
class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Post.Status.PUBLISHED)

    def by(self, author):
        return self.filter(author=author)

    def with_related(self):
        return self.select_related("author").prefetch_related("tags")


class Post(TimeStampedModel):
    ...
    objects = PostQuerySet.as_manager()

# call sites now read like the domain:
Post.objects.published().by(user).with_related()
```

QuerySet methods (opt-in, chainable) are usually better than overriding a manager's `get_queryset()` (which changes the *default universe of rows* for everyone — powerful for soft-delete patterns, dangerous because it hides data from the admin and from future you; if you do it, keep an `all_objects = models.Manager()` escape hatch). Docs: [managers](https://docs.djangoproject.com/en/stable/topics/db/managers/).

If you remember one thing from Part 4: **QuerySets are lazy descriptions — so chain freely, but know your evaluation points; fix N+1 with `select_related` (single-valued, JOIN) and `prefetch_related` (multi-valued, second query); push arithmetic and logic into the database with `F`/`Q`; and keep django-debug-toolbar open while you build.**

---

## Part 5 — Migrations: Version Control for Your Schema

Migrations are git for your database schema. Every time models change, you generate a diff (`makemigrations`), commit it alongside the code that needs it, and apply it everywhere — laptop, CI, production — with `migrate`. The `django_migrations` table records which diffs each database has applied, exactly like a branch pointer. This framing explains everything else about the system: why migrations form a dependency graph (commits have parents), why parallel work creates conflicts (two commits from the same parent), and why you never edit an applied migration (never rewrite pushed history). Docs: [migrations topic guide](https://docs.djangoproject.com/en/stable/topics/migrations/).

The daily workflow:

```bash
# 1. Change models.py
# 2. Generate the diff — and READ it before applying:
python manage.py makemigrations blog
python manage.py sqlmigrate blog 0007        # show the actual SQL
# 3. Apply locally, run tests, commit migration WITH the code
python manage.py migrate
# CI guard — fails if models and migrations have drifted apart:
python manage.py makemigrations --check --dry-run
```

Treat generated migrations as code under review, because `makemigrations` is a competent assistant, not a DBA: it cheerfully generates operations that lock a 100M-row table, and it asks interactive questions (the "provide a one-off default" prompt) whose answers get baked into the file. The `--check` line belongs in every Django CI pipeline (the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md) covers the surrounding plumbing).

The generated files are worth reading once, slowly, because they reveal the machine: a migration is a Python module with `dependencies` (its parents in the graph) and `operations` (the diff):

```python
# blog/migrations/0007_post_summary.py — what makemigrations writes
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0006_alter_post_options"),   # parent within this app
        ("accounts", "0001_initial"),          # cross-app: Post FKs the user model
    ]
    operations = [
        migrations.AddField(
            model_name="post",
            name="summary",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
```

Operations serve double duty: each describes both the SQL to run *and* a change to Django's in-memory model state, which is how the framework can reconstruct what your models looked like at any point in history (the basis for the historical models below) without consulting your current `models.py`. Cross-app `dependencies` are also why Part 9's user-model decision is so sticky — every app's `0001_initial` ends up depending on it. `showmigrations` displays the graph and what's applied where.

### Data Migrations

Schema migrations change structure; **data migrations** change rows — backfilling a new column, splitting a field, fixing encoded values. They use `RunPython` with a critical idiom: `apps.get_model()`, which returns the **historical** version of the model as it existed at that point in migration history, not your current class (whose fields may not exist yet in this database):

```python
# blog/migrations/0008_backfill_summary.py
from django.db import migrations

def backfill_summaries(apps, schema_editor):
    Post = apps.get_model("blog", "Post")          # historical model — NOT from models.py
    for post in Post.objects.filter(summary="").iterator():
        post.summary = post.body[:497] + "..."
        post.save(update_fields=["summary"])

class Migration(migrations.Migration):
    dependencies = [("blog", "0007_post_summary")]
    operations = [
        migrations.RunPython(backfill_summaries, migrations.RunPython.noop),
    ]
```

The second argument (`noop`) makes the migration *reversible* — `migrate blog 0007` can walk back through it. Irreversible migrations should be a deliberate choice, not an accident of omission. For set-based transformations, prefer a single `.update()` or `RunSQL` over a Python loop — the database is faster than your for-loop by orders of magnitude. Docs: [data migrations](https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations), [writing migrations how-to](https://docs.djangoproject.com/en/stable/howto/writing-migrations/).

### Migrations in Teams and in Production

**Conflicts.** Two branches each add `blog/0007_*` from the same parent: Django detects the fork and refuses to run until you create a merge migration (`makemigrations --merge`) — or, often better, rebase and renumber one branch's migration so history stays linear. Either way, resolve by *understanding both changes*, not by mechanically accepting the merge.

**Zero-downtime changes.** During a rolling deploy, old code and new schema coexist — so every migration must be safe against the *previous* release. That forbids one-step renames and one-step `NOT NULL` additions. The production-safe pattern for adding a required column is **expand → backfill → contract**, across multiple releases:

1. Add the column nullable (or with `db_default`) — old code ignores it, nothing breaks.
2. Deploy code that writes it; backfill existing rows with a data migration.
3. Only then add the `NOT NULL` constraint, once nothing can produce a null.

Renames are the same dance with a copy step in the middle (add new column, dual-write, backfill, switch reads, drop old). On Postgres, also know which DDL takes aggressive locks — `ADD COLUMN ... DEFAULT` is cheap on modern Postgres, but adding an index should use `AddIndexConcurrently` from `django.contrib.postgres.operations` (see the [Advanced Postgres guide](ADVANCED_POSTGRES.md) for the locking details). Adam Johnson's writing on [safe migration patterns](https://adamj.eu/tech/) is the best ongoing reference here.

**Recovery tools, used sparingly.** `migrate --fake` records a migration as applied without running its SQL — strictly for when the database *already* matches (e.g., adopting migrations onto an existing schema with `--fake-initial`). `squashmigrations` collapses a long-stable history into fewer files for faster test-database setup. Both are sharp tools: misusing `--fake` desynchronizes Django's view of the schema from reality, which is the database equivalent of a corrupted git index.

A note on long-run hygiene: after a few years an app can accumulate hundreds of migrations, and every test run replays them to build the test database (`--keepdb` helps). `squashmigrations` collapses a stable stretch of history into fewer, optimized operations while keeping the graph valid for databases that already applied the originals — worthwhile maintenance once a year, reviewed like any other migration, with the original files deleted only after every deployment has moved past them.

If you remember one thing from Part 5: **migrations are committed schema diffs — review the generated SQL, keep data migrations reversible with historical models, and in production never make a change the previous release's code can't live with (expand → backfill → contract).**

---

## Part 6 — Views: Functions, Classes & the Honest Trade-off

A view is a callable that takes an `HttpRequest` (plus captured URL arguments) and returns an `HttpResponse`. That's the entire contract. Django offers two styles for writing them, and the FBV-vs-CBV debate has consumed more conference hallway time than any technical question deserves — so let's settle it with code and an honest ledger.

### Function-Based Views

```python
# apps/blog/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PostForm
from .models import Post


def post_detail(request, slug):
    post = get_object_or_404(Post.objects.published().with_related(), slug=slug)
    return render(request, "blog/post_detail.html", {"post": post})


@login_required
@require_http_methods(["GET", "POST"])
def post_create(request):
    form = PostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user          # request-derived data the form can't know
        post.save()
        return redirect(post)                # uses get_absolute_url(); Post/Redirect/Get
    return render(request, "blog/post_form.html", {"form": form})
```

Everything is on the page: the control flow reads top to bottom, decorators state preconditions at eye level (`@login_required`, `@require_http_methods`), and there is no hidden machinery. The `form.save(commit=False)` → set fields → `save()` sequence and the redirect-after-successful-POST pattern (preventing double submission on refresh) are the two idioms every Django form view contains. Docs: [writing views](https://docs.djangoproject.com/en/stable/topics/http/views/), [view decorators](https://docs.djangoproject.com/en/stable/topics/http/decorators/).

### Class-Based Views

The same pair, as CBVs:

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, DetailView, ListView


class PostListView(ListView):
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = 20

    def get_queryset(self):
        return Post.objects.published().with_related()


class PostDetailView(DetailView):
    context_object_name = "post"

    def get_queryset(self):
        # Drafts visible only to their author — queryset scoping IS authorization
        qs = Post.objects.with_related()
        if self.request.user.is_authenticated:
            return qs.filter(Q(status="published") | Q(author=self.request.user))
        return qs.published()


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)      # saves and redirects to get_absolute_url
```

CBVs work by **method dispatch over a template-method skeleton**: `as_view()` produces a function that instantiates the class per request; `dispatch()` routes by HTTP method to `get()`/`post()`; the generic views (`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`, `FormView`) fill those in with conventional flows full of override hooks. The craft is overriding the **narrowest hook that solves the problem**: `get_queryset()` for what rows are visible (note above: visibility filtering in `get_queryset()` is *the* row-level authorization pattern — list and detail automatically agree), `get_context_data()` for extra template variables, `form_valid()` for save-time behavior, `get_success_url()` for redirects. If you find yourself overriding `get()` or `post()` wholesale, the generic view is fighting you — write an FBV.

A free feature hiding in the `ListView` example deserves a callout: `paginate_by = 20` gives you full pagination — the view slices the queryset with SQL `LIMIT`/`OFFSET` (never loading the whole table), validates the `?page=` parameter, and exposes `page_obj` and `paginator` to the template:

```html
{% if page_obj.has_next %}
  <a href="?page={{ page_obj.next_page_number }}">Older posts</a>
{% endif %}
<span>Page {{ page_obj.number }} of {{ paginator.num_pages }}</span>
```

Hand-rolled pagination is one of the classic FBV time sinks that CBVs (or the underlying [`Paginator`](https://docs.djangoproject.com/en/stable/topics/pagination/) class, usable anywhere) simply delete.

Mixins compose behavior through Python's MRO, and **class order is behavior**: `LoginRequiredMixin` must sit *left* of the generic view so its `dispatch()` runs first. When you can't tell which of a CBV's eight ancestors implements the method you need, [ccbv.co.uk](https://ccbv.co.uk/) flattens every generic view into one page — attributes, methods, ancestors — and is the single best CBV resource in existence. Docs: [class-based views](https://docs.djangoproject.com/en/stable/topics/class-based-views/), [access mixins](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-loginrequiredmixin-mixin).

### The Honest Ledger

| | FBVs | CBVs |
|---|---|---|
| Readability | Everything visible in one function | Behavior spread across class + 5–8 ancestors |
| Standard CRUD | Repetitive boilerplate | `CreateView` et al. erase it |
| Unusual flows (wizards, multi-form pages, branching) | Natural — it's just code | Hook-fighting; overrides of overrides |
| Reuse | Helper functions, decorators | Mixins, inheritance |
| Debuggability | Stack traces map to your code | Traces wander through `django/views/generic/*` |
| Learning curve | Minutes | Real (MRO, dispatch, hook contracts) |

The pragmatic rule: **CBVs for conventional CRUD where the convention fits like a glove; FBVs for everything custom.** Both in one codebase is normal and correct. The failure modes are symmetric — FBV zealots hand-roll pagination and form flows that `ListView`/`CreateView` give for free; CBV zealots contort `FormView` into workflows that would be ten honest lines as a function. If you're overriding more than two or three hooks, the convention doesn't fit: write the function. (For completeness: DRF tilts this calculus toward classes — its ViewSet/Router machinery is genuinely load-bearing in a way Django's generic views are not; Part 11.)

One bridging tool worth knowing: function decorators apply to CBVs via [`method_decorator`](https://docs.djangoproject.com/en/stable/topics/class-based-views/intro/#decorating-the-class) — `@method_decorator(cache_page(300), name="get")` above the class, or on `dispatch` for all methods — which means the decorator ecosystem (Part 2's `cache_page`, rate limiters, `csrf_exempt` for the rare legitimate case) serves both view styles.

For intuition about what `as_view()` actually builds, the skeleton is small enough to hold in your head:

```python
# Conceptually, what View provides (simplified from django/views/generic/base.py):
class View:
    @classonlymethod
    def as_view(cls, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)        # fresh instance per request — no shared state
            self.setup(request, *args, **kwargs)
            return self.dispatch(request, *args, **kwargs)
        return view

    def dispatch(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        return handler(request, *args, **kwargs)
```

Per-request instantiation is the detail that surprises people: storing state on `self` is safe within a request and never shared across requests, and every mixin's power comes from splicing itself into that `dispatch` chain via the MRO.

If you remember one thing from Part 6: **a view is just request → response — use CBVs when your page matches their convention, FBVs when it doesn't, override the narrowest hook, and keep ccbv.co.uk open whenever a generic view surprises you.**

---

## Part 7 — Templates

The Django Template Language (DTL) is **deliberately underpowered**: no arbitrary expressions, no function calls with arguments, no Python. That's a feature with a name — it forces logic back into views and models where it can be tested, leaving templates as what they should be: a declarative description of presentation. (If you need more power, Jinja2 is a [supported engine](https://docs.djangoproject.com/en/stable/topics/templates/#support-for-template-engines) — but most teams never need it, and DTL's restraint ages well.)

The organizing idea is **inheritance**. One `base.html` defines the page skeleton as named blocks; every page template extends it and fills in only what differs:

```html
{# templates/base.html #}
<!doctype html>
<html lang="en">
<head>
  <title>{% block title %}My Site{% endblock %}</title>
</head>
<body>
  {% include "partials/nav.html" %}
  <main>{% block content %}{% endblock %}</main>
</body>
</html>

{# templates/blog/post_detail.html #}
{% extends "base.html" %}

{% block title %}{{ post.title }} — {{ block.super }}{% endblock %}

{% block content %}
  <h1>{{ post.title }}</h1>
  <p>By <a href="{% url 'blog:author_detail' post.author.username %}">{{ post.author.get_full_name }}</a>
     on {{ post.published_at|date:"j F Y" }}</p>
  {{ post.body|linebreaks }}

  {% for tag in post.tags.all %}      {# fine — Part 4's prefetch_related made this free #}
    <span class="tag">{{ tag.name }}</span>
  {% empty %}
    <span>No tags.</span>
  {% endfor %}
{% endblock %}
```

`{{ block.super }}` appends to rather than replaces the parent block; `{% include %}` composes reusable fragments; `{% url %}` keeps templates on the named-URL discipline from Part 2; filters like `|date` and `|linebreaks` handle formatting at the point of display. Note the comment on the `for` loop: templates are where N+1 bugs *manifest* — `post.tags.all` in a loop over posts is exactly the pattern that Part 4's `prefetch_related` exists to make safe. Template resolution order (project `DIRS` first, then each app's `templates/` in `INSTALLED_APPS` order) is what makes overriding third-party templates possible. Docs: [template language](https://docs.djangoproject.com/en/stable/ref/templates/language/), [built-in tags and filters](https://docs.djangoproject.com/en/stable/ref/templates/builtins/).

Asset references follow the same no-hardcoding discipline as URLs: `{% static "css/site.css" %}` (after `{% load static %}`) resolves through the staticfiles machinery, which is what lets Part 17's hashed filenames (`site.3f2a8b.css`) work — a hardcoded `/static/css/site.css` would bypass the manifest and break the moment far-future caching is enabled. Docs: [managing static files](https://docs.djangoproject.com/en/stable/howto/static-files/).

### Auto-escaping Is a Security Boundary

Every `{{ variable }}` is HTML-escaped by default — `<script>` renders as `&lt;script&gt;` — which is Django's primary XSS defense (Part 16). The overrides, `{{ value|safe }}` and `mark_safe()` in Python, are **trust declarations, not formatting helpers**: you are asserting this string cannot contain attacker-controlled markup. The bar for using them should be "this HTML was produced by a sanitizer I trust" (e.g., [bleach](https://bleach.readthedocs.io/)/nh3 over user markdown), never "the escaping looked ugly."

The companion trap is handing data to JavaScript. Never interpolate into a `<script>` block by hand; use [`json_script`](https://docs.djangoproject.com/en/stable/ref/templates/builtins/#json-script), which serializes safely into a `<script type="application/json">` element your JS reads with `JSON.parse`:

```html
{{ chart_data|json_script:"chart-data" }}
<script>
  const data = JSON.parse(document.getElementById("chart-data").textContent);
</script>
```

When presentation logic genuinely needs to be reusable, [custom template tags](https://docs.djangoproject.com/en/stable/howto/custom-template-tags/) are the sanctioned mechanism — `@register.simple_tag` for computed values, `@register.inclusion_tag` for rendering a fragment with its own mini-context (the classic "sidebar widget" pattern), `@register.filter` for new transformations. Keep them presentation-only; an inclusion tag that runs three queries is a hidden performance landmine. Worth knowing in the 5.x era: server-rendered Django plus [htmx](https://htmx.org/) has become a mainstream answer to "do we need a React frontend?" — templates returning fragments over the wire — and pairs unusually well with everything in this part.

```python
# apps/blog/templatetags/blog_extras.py
from django import template
from apps.blog.models import Post

register = template.Library()


@register.inclusion_tag("blog/partials/recent_posts.html")
def recent_posts(count=5):
    return {"posts": Post.objects.published()[:count]}
```

```html
{# any template, after {% load blog_extras %} #}
{% recent_posts 3 %}
```

The fragment template renders with its own mini-context — the reusable-widget pattern, kept honest by the warning above: this one runs a query per use, so cache the fragment (Part 12) if it appears on every page.

If you remember one thing from Part 7: **DTL is weak on purpose — inherit from a base skeleton, generate URLs with `{% url %}`, treat `|safe` as a security assertion, and pass data to JavaScript only through `json_script`.**

---

## Part 8 — Forms & ModelForms

Django forms are not about HTML — they're a **validation pipeline** that happens to know how to render itself. A `Form` defines typed fields; binding it to `request.POST` and calling `is_valid()` runs every field's coercion and validation; afterwards `form.cleaned_data` holds *typed Python values* (a real `datetime`, a real `Decimal`) and `form.errors` holds structured, per-field messages. This is the 80% case made trivial: parsing, coercion, validation, error display, and re-rendering with the user's input preserved — the tedious heart of every web app — in one object.

`ModelForm` derives the fields from a model and adds persistence; the validation hooks are where real applications live:

```python
# apps/blog/forms.py
from django import forms
from django.utils import timezone
from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "slug", "status", "body", "summary", "published_at"]
        # NEVER fields = "__all__": new model fields would silently become
        # user-editable — a mass-assignment vulnerability waiting to happen.
        widgets = {
            "body": forms.Textarea(attrs={"rows": 20}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_slug(self):                      # single-field rule
        slug = self.cleaned_data["slug"]
        if slug in {"admin", "api", "static"}:
            raise forms.ValidationError("That slug is reserved.")
        return slug

    def clean(self):                           # cross-field rules
        cleaned = super().clean()
        if (cleaned.get("status") == Post.Status.PUBLISHED
                and not cleaned.get("published_at")):
            cleaned["published_at"] = timezone.now()   # clean() may repair, not just reject
        return cleaned
```

The pipeline order is worth memorizing because it tells you where each rule belongs: each field's own `clean()` (type coercion + `validators`) → your `clean_<fieldname>()` methods (single-field domain rules) → `clean()` (rules spanning fields). For `ModelForm`s, model-level validation (field validators, `unique` checks) joins in via `_post_clean`. Fields are about *data* (what type, what rules); **widgets** are about *rendering* (what HTML input) — override widgets when the browser control should change, not the data type. Docs: [working with forms](https://docs.djangoproject.com/en/stable/topics/forms/), [form and field validation](https://docs.djangoproject.com/en/stable/ref/forms/validation/), [ModelForm](https://docs.djangoproject.com/en/stable/topics/forms/modelforms/).

The view-side idiom appeared in Part 6, with its one famous wrinkle: after `post = form.save(commit=False)` you must call `form.save_m2m()` once the instance is saved, because many-to-many rows can't exist until the instance has a primary key. Choose `ModelForm` when the form is a projection of one model; choose plain `Form` for search boxes, multi-model workflows, CSV-upload screens — anywhere "valid input" doesn't mean "one model instance." Forcing workflow forms into `ModelForm` is a common shape error.

**Rendering** starts free — `{{ form.as_div }}` (the modern default; `as_p` survives) — and production UIs graduate to manual rendering for control over markup and accessibility:

```html
<form method="post">
  {% csrf_token %}                 {# mandatory on every POST form — Part 16 #}
  {{ form.non_field_errors }}
  {% for field in form %}
    <div class="field {% if field.errors %}has-error{% endif %}">
      {{ field.label_tag }} {{ field }}
      {{ field.errors }}
      {% if field.help_text %}<small>{{ field.help_text }}</small>{% endif %}
    </div>
  {% endfor %}
  <button type="submit">Save</button>
</form>
```

Since Django 4.x, form rendering is itself template-based ([renderers](https://docs.djangoproject.com/en/stable/ref/forms/renderers/)), so you can restyle all forms project-wide by overriding one template — which has reduced (not eliminated) the historical need for [django-crispy-forms](https://django-crispy-forms.readthedocs.io/). For editing *many* homogeneous forms at once — a parent and its children on one page — [formsets](https://docs.djangoproject.com/en/stable/topics/forms/formsets/) and especially `inlineformset_factory` package the bookkeeping (per-row forms, a management form tracking counts, add/delete flags) that you'd otherwise hand-roll badly. File uploads add three requirements that must all be present or the file silently never arrives: `enctype="multipart/form-data"` on the `<form>`, `request.FILES` passed as the form's second argument, and a `FileField`/`ImageField` with storage configured (Part 17). Docs: [file uploads](https://docs.djangoproject.com/en/stable/topics/http/file-uploads/).

The inline-formset shape, because the docs' version is hard to picture until you've seen it small:

```python
from django.forms import inlineformset_factory

LinkFormSet = inlineformset_factory(
    Post, RelatedLink, fields=["title", "url"], extra=2, can_delete=True
)


def edit_links(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)
    formset = LinkFormSet(request.POST or None, instance=post)
    if request.method == "POST" and formset.is_valid():
        formset.save()                       # creates, updates, AND deletes children
        return redirect(post)
    return render(request, "blog/links_form.html", {"formset": formset})
```

In the template, `{{ formset.management_form }}` is mandatory — the hidden bookkeeping (how many forms, which rows are deletions) that makes the mechanism work, and forgetting it is the classic formset bug.

If you remember one thing from Part 8: **forms are a typed validation pipeline — enumerate `fields` explicitly (never `"__all__"`), put single-field rules in `clean_<field>()` and cross-field rules in `clean()`, and trust `cleaned_data` only after `is_valid()` returns True.**

---

## Part 9 — Authentication, Authorization & the Custom User Model

Django ships a complete authentication system — user model, password hashing with automatic algorithm upgrades, login/logout/password-reset views, sessions, permissions, groups — that has been hardened by two decades of production exposure. The first rule of using it is also the most counterintuitive: **before your first migration, replace the default user model, even if you change nothing.**

### The Custom User Model: Do It First, Here's Why

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Identical to Django's default user — for now. That's the point."""
    pass

# config/settings/base.py
AUTH_USER_MODEL = "accounts.User"
```

Why this ceremony for an empty subclass? Because `AUTH_USER_MODEL` gets **baked into migration history**: every `ForeignKey` to the user, every permission row, every table the auth app creates references the concrete user model that existed when migration `0001` ran. Once a production database has migrations built against `auth.User`, switching to a custom model means rewriting migration history against live data — a project the [official docs](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#changing-to-a-custom-user-model-mid-project) describe with visible reluctance and most teams describe with profanity. The empty subclass costs five minutes on day one and buys you the ability to add `phone_number`, switch to email login, or restructure identity *whenever the product asks*, with an ordinary migration. This is the single most repeated piece of advice in the Django community ([the docs say it](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project), Two Scoops says it, Will Vincent says it) precisely because the cost asymmetry is so extreme.

Two subclass options: **`AbstractUser`** keeps Django's full user (username, email, names, permissions flags) and is the right default; **`AbstractBaseUser`** keeps only password machinery and makes you define identity yourself — choose it only when your model genuinely diverges (e.g., email-only login with no username), and budget for also writing a manager and admin integration. Two referencing rules follow everywhere else in the codebase: model FKs point at `settings.AUTH_USER_MODEL` (a string, resolved late), and Python code calls `get_user_model()` — never `from django.contrib.auth.models import User`, which hard-couples you to the model you just replaced.

### Passwords, Login Flows, and Sessions

Password storage is a pluggable hasher list (`PASSWORD_HASHERS`); the default PBKDF2 is fine, and [argon2](https://docs.djangoproject.com/en/stable/topics/auth/passwords/#using-argon2-with-django) (`pip install django[argon2]`, put it first in the list) is the modern recommendation. Django transparently re-hashes a user's password to your preferred algorithm at their next login — algorithm migration with zero ceremony, a small masterpiece of framework design.

The built-in views cover the entire account lifecycle — `LoginView`, `LogoutView`, `PasswordChangeView`, the four-step `PasswordReset*` flow with signed, expiring tokens — wired in one line (`path("accounts/", include("django.contrib.auth.urls"))`) and customized by overriding their templates (`registration/login.html` etc.). Registration, email verification, and social login are deliberately *not* included; [django-allauth](https://docs.allauth.org/en/latest/) is the ecosystem's production answer and is built atop (not instead of) everything above. For the protocol-level view of OAuth/OIDC that allauth implements, see the [Auth guide](AUTH_STUDY_GUIDE.md).

Sessions are the substrate: `SessionMiddleware` gives each browser a random session key in a cookie, storing the data server-side (database by default; `cached_db` — cache reads with database durability — is the standard production upgrade). Login simply stores the user ID in the session; `AuthenticationMiddleware` reads it back into `request.user` lazily on each request. The cookie hardening flags (`SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE`) are Part 16's business. Docs: [sessions](https://docs.djangoproject.com/en/stable/topics/http/sessions/), [auth defaults](https://docs.djangoproject.com/en/stable/topics/auth/default/).

The session-related settings cluster worth setting consciously rather than inheriting:

```python
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"  # cache reads, DB durability
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14      # two weeks
SESSION_COOKIE_SECURE = True                 # HTTPS only (production settings)
SESSION_COOKIE_HTTPONLY = True               # default: JS cannot read it
SESSION_COOKIE_SAMESITE = "Lax"              # default: blunts cross-site sends
SESSION_EXPIRE_AT_BROWSER_CLOSE = False      # persistent login; True for banking-style apps
```

Use `request.session` as a small dict for flow state (carts, wizards, "just verified email") — it is not a database, and everything in it rides on a cookie-keyed server-side record that vanishes on logout (`logout()` flushes it, which is also your session-fixation defense, applied automatically by `login()`).

### Authentication Backends: How "Who Is This?" Stays Pluggable

`authenticate(request, **credentials)` walks the `AUTHENTICATION_BACKENDS` list, asking each backend in turn until one returns a user. The default `ModelBackend` checks username/password against the database; adding a backend is how LDAP, corporate SSO, or API-key auth joins the party *without* touching the rest of the system — sessions, `request.user`, and permission checks keep working unchanged:

```python
# apps/accounts/backends.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend


class ApiKeyBackend(BaseBackend):
    def authenticate(self, request, api_key=None):
        if api_key is None:
            return None                      # not my kind of credential — next backend
        try:
            return (ApiKey.objects.select_related("user")
                    .get(key=api_key, revoked_at__isnull=True).user)
        except ApiKey.DoesNotExist:
            return None

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id).first()
```

Backends also participate in permission checks (`user.has_perm` aggregates across all of them) — the seam django-guardian uses for its object-level permissions. Most projects never write one, but knowing the seam exists is the difference between "Django can't do our SSO" and a forty-line file. Docs: [authentication backends](https://docs.djangoproject.com/en/stable/topics/auth/customizing/#writing-an-authentication-backend).

### Authorization: Permissions, Groups, and the Pattern That Actually Scales

Django's permission system auto-creates four permissions per model (`add_post`, `change_post`, `delete_post`, `view_post`), lets you declare domain-specific ones in `Meta.permissions = [("publish_post", "Can publish posts")]`, and aggregates them through **groups** (assign permissions to a "Editors" group, users to the group — roles without writing a role system). Checks appear at every layer with the same vocabulary: `user.has_perm("blog.publish_post")` in code, `@permission_required("blog.publish_post")` on FBVs, `PermissionRequiredMixin` on CBVs, `{% if perms.blog.publish_post %}` in templates, and automatically throughout the admin.

The honest limitation: these are **model-level** permissions — "can this user change posts *at all*," not "*this* post." Per-object authorization in real applications is overwhelmingly done by **queryset scoping**, which you've already seen in Part 6:

```python
class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm

    def get_queryset(self):
        # Object-level authorization as a WHERE clause: a user who doesn't own
        # the post gets a 404 — the object effectively doesn't exist for them.
        return Post.objects.filter(author=self.request.user)
```

This pattern — *authorization is filtering* — is robust because list views, detail views, and edit views all derive from the same scoped queryset, so they can't disagree; it returns 404 rather than 403, leaking nothing about what exists; and it's enforced where the data is fetched, not in a check someone can forget. Reach for [django-guardian](https://django-guardian.readthedocs.io/en/stable/) (per-object permission rows) or [django-rules](https://github.com/dfunckt/django-rules) (predicate-based) only when access is genuinely *assignable* ("share this document with Bob") rather than derivable from relationships. Most apps never need them.

If you remember one thing from Part 9: **create a custom user model before your first migration — `class User(AbstractUser): pass` is enough — reference it via `settings.AUTH_USER_MODEL`/`get_user_model()`, and implement per-object authorization as queryset filtering, not scattered if-statements.**

---

## Part 10 — The Admin

The admin is Django's most famous battery: a production-grade CRUD interface generated from your model definitions, with auth, audit logging of admin actions, search, filtering, and inline editing included. It is also the most *misunderstood* battery, so start with what it's for: **the admin is an internal power tool for trusted staff, not a user-facing application.** Used that way it routinely replaces months of internal-tools development. Stretched into a customer UI it becomes a security liability and a framework fight.

The register-and-configure idiom turns the raw default into a real operations console:

```python
# apps/blog/admin.py
from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from .models import Post, PostTag


class PostTagInline(admin.TabularInline):
    model = PostTag
    extra = 0
    autocomplete_fields = ["tag"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "status", "published_at", "comment_count"]
    list_filter = ["status", ("published_at", admin.DateFieldListFilter)]
    search_fields = ["title", "body", "author__username"]
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ["title"]}
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["author"]          # don't render a 100k-user <select>
    inlines = [PostTagInline]
    actions = ["publish_selected"]

    def get_queryset(self, request):
        # The admin is NOT exempt from N+1: list_display touching relations
        # needs the same select_related/annotate discipline as any view.
        return (super().get_queryset(request)
                .select_related("author")
                .annotate(num_comments=Count("comments")))

    @admin.display(ordering="num_comments", description="Comments")
    def comment_count(self, obj):
        return obj.num_comments

    @admin.action(description="Publish selected posts")
    def publish_selected(self, request, queryset):
        updated = queryset.update(status=Post.Status.PUBLISHED,
                                  published_at=timezone.now())
        self.message_user(request, f"{updated} posts published.")
```

Each block earns its place. `list_display` + `list_filter` + `search_fields` are the highest-leverage three lines in Django — they turn "row browser" into "support tool that answers questions." Inlines edit children in the parent's context (the natural UI for through-models and line items). **Actions** are staff bulk operations — publish, archive, re-send, export — and deserve the same care as APIs: they run with the operator's full authority and no confirmation by default. The `get_queryset` override carries two lessons: the admin obeys the same ORM physics as everything else (the N+1 of Part 4 happens here constantly, via `list_display` columns and `__str__` methods that touch relations), and it's also the hook for *scoping* what staff can see. Django 5.x added [facet counts](https://docs.djangoproject.com/en/stable/ref/contrib/admin/#facets) to filters — small, but emblematic of the admin's steady polish. Docs: [admin reference](https://docs.djangoproject.com/en/stable/ref/contrib/admin/), [admin actions](https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/).

Site-level knobs round it out: `admin.site.site_header`/`site_title` brand the instance (a surprisingly effective trust signal for staff), `admin.site.unregister(Group)` prunes noise, and wholly custom staff pages can mount on the admin site itself via `AdminSite.get_urls()` — dashboards and reports that inherit the admin's auth and chrome without pretending to be model CRUD.

Operationally: serve the admin at a non-default path (every botnet on earth probes `/admin/`), require staff 2FA, keep `is_superuser` rare, and remember admin users bypass much of your application's authorization logic by design. Themes ([django-unfold](https://unfoldadmin.com/docs/), [django-jazzmin](https://django-jazzmin.readthedocs.io/)) restyle it; they don't change the trust model. The judgment call that matters: when staff workflows outgrow CRUD-on-models — multi-step processes, dashboards, approvals — build real (staff-only) views rather than bending the admin further. The admin's sweet spot is wide but it has edges, and respecting them is part of the 80/20 mental model.

If you remember one thing from Part 10: **the admin is a generated internal tool for trusted staff — configure `list_display`/filters/search/actions generously, fix its querysets like any other view's, lock it down operationally, and graduate to custom views when workflows outgrow CRUD.**

---

## Part 11 — Django REST Framework (and Django Ninja)

[Django REST Framework](https://www.django-rest-framework.org/) is the de facto standard for building APIs on Django — not part of Django itself, but so universal that job postings treat them as one word. Its architecture deliberately rhymes with Django's: **serializers** are forms for JSON (validation pipeline in, representation out), **generic views and viewsets** are CBVs for resources, **permission classes** are the auth mixins, **routers** are the URLconf. If Parts 4, 6, 8, and 9 made sense, DRF is mostly new vocabulary for ideas you already hold.

### Serializers: Forms for JSON

A serializer converts between model instances and primitive types (out: `to_representation`) and between untrusted payloads and validated Python (in: `to_internal_value` + the validation pipeline). `ModelSerializer` derives fields from a model exactly as `ModelForm` does — with the same rule about explicit field lists:

```python
# apps/api/serializers.py
from rest_framework import serializers
from apps.blog.models import Post


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username"]            # explicit; never "__all__"


class PostListSerializer(serializers.ModelSerializer):
    """Lightweight shape for list endpoints."""
    author = serializers.StringRelatedField()

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "author", "published_at"]


class PostDetailSerializer(serializers.ModelSerializer):
    """Rich shape for detail endpoints: nested author, computed field."""
    author = AuthorSerializer(read_only=True)
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "author", "status",
                  "body", "tag_names", "published_at"]
        read_only_fields = ["published_at"]

    def get_tag_names(self, obj):
        # Iterates the prefetched cache — NO query, IF the view prefetched tags.
        # Without that prefetch, this line is an N+1 across every serialized post.
        return [t.name for t in obj.tags.all()]

    def validate_slug(self, value):            # field rule — mirrors clean_<field>()
        if value in {"admin", "api"}:
            raise serializers.ValidationError("Reserved slug.")
        return value

    def validate(self, attrs):                 # cross-field rule — mirrors clean()
        if attrs.get("status") == Post.Status.PUBLISHED and not attrs.get("body"):
            raise serializers.ValidationError("Published posts need a body.")
        return attrs
```

Three production patterns are embedded here. **Read/write and list/detail splits**: list endpoints want small payloads, detail endpoints want rich ones, and write payloads rarely match either — separate serializer classes beat one class full of conditionals. **Nested serializers are read-only by default**: writable nesting requires you to override `create()`/`update()` and orchestrate the related writes yourself (inside a transaction), which is why flat write-shapes with ID references (`author_id`) are usually the saner API design. **`SerializerMethodField` is the N+1 vector of the API layer** — the comment in `get_tag_names` is the single most common DRF performance bug, and the fix lives in the *view's* queryset, not the serializer. Docs: [serializers](https://www.django-rest-framework.org/api-guide/serializers/), [serializer relations](https://www.django-rest-framework.org/api-guide/relations/).

### Views, ViewSets, and Routers

DRF offers a ladder of abstraction — `APIView` (explicit `get`/`post` handlers plus DRF's parsing/auth/negotiation), generic views (`ListCreateAPIView` and friends), and at the top **ViewSets**, which collapse a resource's whole CRUD surface into one class that a **Router** wires to URLs:

```python
# apps/api/views.py
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filterset_fields = ["status", "author__username"]   # django-filter
    search_fields = ["title", "body"]
    ordering_fields = ["published_at"]
    lookup_field = "slug"

    def get_queryset(self):
        # Visibility scoping AND N+1 prevention live here, feeding every action.
        qs = Post.objects.select_related("author").prefetch_related("tags")
        if self.action == "list":
            return qs.published()
        return qs

    def get_serializer_class(self):
        return (PostListSerializer if self.action == "list"
                else PostDetailSerializer)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)       # request-derived field

    @action(detail=True, methods=["post"])
    def publish(self, request, slug=None):
        post = self.get_object()                        # runs object permissions
        post.status = Post.Status.PUBLISHED
        post.save(update_fields=["status"])
        return Response({"status": "published"})

# apps/api/urls.py
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")
urlpatterns = router.urls    # list/create/retrieve/update/destroy + POST /posts/{slug}/publish/
```

The hooks mirror Part 6 exactly: `get_queryset()` for scope (and prefetching), `get_serializer_class()` for shape, `perform_create()` for save-time injection, `@action` for the operations that don't fit CRUD (`POST /posts/{slug}/publish/`). When you can't find which ancestor provides a method, [cdrf.co](https://www.cdrf.co/) is DRF's ccbv. Unlike plain Django — where FBVs and CBVs are genuine peers — DRF's class machinery (routers, schema generation, the browsable API) is load-bearing enough that viewsets are the clear default; drop down to `APIView` only for genuinely non-resource endpoints. Docs: [viewsets](https://www.django-rest-framework.org/api-guide/viewsets/), [routers](https://www.django-rest-framework.org/api-guide/routers/), [generic views](https://www.django-rest-framework.org/api-guide/generic-views/).

### AuthN, AuthZ, and the Request Plumbing

DRF separates *who is calling* (authentication classes) from *what they may do* (permission classes). `SessionAuthentication` serves browser clients (and the browsable API) with CSRF intact; token schemes serve programmatic clients — [djangorestframework-simplejwt](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/) is the standard JWT choice for SPA/mobile backends (short-lived access token + refresh token; see the [Auth guide](AUTH_STUDY_GUIDE.md) for why JWT revocation is the part everyone gets wrong). Set restrictive **global defaults** and loosen per-view, never the reverse:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "1000/min"},
}
```

An unpaginated list endpoint is an outage waiting for data growth, so pagination is non-optional: `PageNumberPagination` is friendliest, `CursorPagination` is the right answer for large or frequently-inserted tables (stable pages, no `OFFSET` cost — the same reasoning as keyset pagination in the [Postgres guide](POSTGRES.md)). [django-filter](https://django-filter.readthedocs.io/en/stable/) provides declarative query-param filtering; `OrderingFilter` needs an explicit `ordering_fields` allowlist (letting clients sort by arbitrary columns invites pathological queries). Throttling is fairness control, not security. Version from day one — URL-path versioning (`/api/v1/`) is the option clients, logs, and caches all understand — and generate an OpenAPI schema with [drf-spectacular](https://drf-spectacular.readthedocs.io/en/stable/), which turns your serializers and viewsets into docs and typed clients. Docs: [authentication](https://www.django-rest-framework.org/api-guide/authentication/), [permissions](https://www.django-rest-framework.org/api-guide/permissions/), [pagination](https://www.django-rest-framework.org/api-guide/pagination/), [versioning](https://www.django-rest-framework.org/api-guide/versioning/).

One piece of plumbing worth a sentence because it explains DRF's developer experience: **content negotiation**. Renderers turn the same `Response` data into JSON for clients or the *browsable API* — the HTML interface you get for free at every endpoint, with forms for POSTing — which is DRF's secret onboarding weapon; parsers do the reverse for request bodies. You'll rarely customize either, but knowing the layer exists demystifies "why does my API render HTML in a browser?"

### Testing the API

DRF's `APIClient` extends Django's test client with content negotiation and auth helpers; the assertions worth writing mirror what clients depend on — status codes, payload shape, and above all *who can do what*:

```python
from rest_framework.test import APITestCase


class PostAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = UserFactory()
        cls.post = PostFactory(author=cls.author, status="published")

    def test_anonymous_can_read_but_not_write(self):
        self.assertEqual(self.client.get("/api/v1/posts/").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/posts/", {}).status_code, 401)

    def test_non_author_cannot_edit(self):
        self.client.force_authenticate(UserFactory())   # skip the auth handshake
        resp = self.client.patch(
            f"/api/v1/posts/{self.post.slug}/", {"title": "hijacked"}
        )
        self.assertEqual(resp.status_code, 403)         # IsAuthorOrReadOnly holds
```

`force_authenticate` keeps permission tests focused on the rule under test (keep a couple of tests exercising the real JWT flow — but only a couple), and Part 15's `assertNumQueries` applies verbatim here: list endpoints with nested serializers are where query-count regressions breed. Docs: [DRF testing](https://www.django-rest-framework.org/api-guide/testing/).

### DRF vs Django Ninja

[Django Ninja](https://django-ninja.dev/) is the credible challenger: FastAPI's ergonomics (type hints + Pydantic schemas, async-native handlers, automatic OpenAPI) on Django's ORM and auth. The honest comparison:

| | DRF | Django Ninja |
|---|---|---|
| Validation | Serializers (runtime field classes) | Pydantic models (type hints, faster) |
| Style | Class-based: viewsets, routers, mixins | Function-based: decorated endpoints |
| Async | Bolted on, partial | Native |
| OpenAPI | Via drf-spectacular | Built in |
| Ecosystem | Enormous (filters, JWT, nested routers, a decade of answers) | Smaller, growing |
| Browsable API | Yes — underrated for development | Swagger UI |

Choose DRF for large resource-oriented APIs, teams that know it, and anything leaning on its ecosystem; choose Ninja for new, smaller, async-leaning APIs where Pydantic typing and speed matter and you'd rather write functions than configure viewsets. Both are good; the expensive mistake is hand-rolling `JsonResponse` views and rediscovering, endpoint by endpoint, why these frameworks exist.

If you remember one thing from Part 11: **DRF is Django's patterns re-expressed for APIs — serializers are forms, viewsets are CBVs with `get_queryset`/`get_serializer_class` as the hooks that matter, defaults lock the API down globally, and the N+1 bugs hide in serializers but get fixed in view querysets.**

---

## Part 12 — Caching & Performance

Django performance work follows a strict order of operations: **measure, fix the queries, add indexes, and only then cache.** Caching applied before query discipline just hides the problem until a cache miss reveals it at the worst moment. This part follows that order.

### See the Queries First

[django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) in development shows every query a page runs, its time, and its traceback — install it the same day you start a project. [django-silk](https://github.com/jazzband/django-silk) profiles request/SQL behavior in staging-like environments. In tests, `assertNumQueries` (Part 15) freezes your query counts so regressions fail CI instead of paging you. For a single suspicious query, `.explain()` on any queryset prints the database's execution plan — and the [Advanced Postgres guide](ADVANCED_POSTGRES.md) teaches you to read it. The high-leverage fixes are the ones from Part 4 (`select_related`/`prefetch_related`, `exists()`/`count()`, `values()` for column-only reads, bulk writes) plus indexes that match real access patterns: a composite index on `["status", "-published_at"]` because the listing page filters and sorts that way, not `db_index=True` sprinkled speculatively — every index taxes every write. Docs: [database optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/).

Connection management is the quiet third lever: `CONN_MAX_AGE = 60` (persistent connections) eliminates per-request reconnect overhead; Django 5.1+ ships a [native connection pool](https://docs.djangoproject.com/en/stable/ref/databases/#connection-pool) for psycopg, and at scale [PgBouncer](https://www.pgbouncer.org/) pools centrally so a hundred gunicorn workers don't hold a hundred idle Postgres connections.

### The Cache Framework: Four Granularities

Django's [cache framework](https://docs.djangoproject.com/en/stable/topics/cache/) is one API over pluggable backends — Redis (first-party backend since 4.0; the [Redis guide](REDIS_STUDY_GUIDE.md) covers the server side), Memcached, database, local memory (dev only — per-process, so it *lies* under multi-worker gunicorn). Four levels, narrowest first because that's the order to reach for them:

**Low-level API** — cache *expensive computations*, keyed precisely:

```python
from django.core.cache import cache

def trending_posts():
    return cache.get_or_set(
        "trending_posts:v2",                       # versioned key: bump to invalidate
        lambda: list(                               # list(): cache results, not a lazy queryset
            Post.objects.published()
            .annotate(score=Count("comments"))
            .order_by("-score")[:10]
        ),
        timeout=300,
    )
```

Two details carry the lesson: the `list()` call forces evaluation — caching a lazy QuerySet object would cache the *description*, not the rows (Part 4's model paying rent again) — and the `:v2` suffix is the **versioned-key** idiom, the cheapest sane invalidation strategy: deploy code that writes `:v3` and the old entries die of TTL instead of being hunted down.

**Template fragment caching** caches expensive page *regions* (`{% cache 300 sidebar request.user.pk %}` — note the user PK in the key; forgetting a personalization dimension serves one user's fragment to another, which is a data leak, not a perf bug). **Per-view caching** (`@cache_page(300)`) suits anonymous, identical-for-everyone pages. **Per-site caching** middleware is almost always wrong for anything with a logged-in user. The cardinal rule across all levels: **every dimension that changes the output must appear in the key** — user, tenant, language, version.

Invalidation is the famously hard part, so prefer strategies in this order: (1) short TTLs and tolerance for bounded staleness — most "real-time" requirements aren't; (2) versioned keys, as above; (3) explicit `cache.delete()` at the write site — `transaction.on_commit(lambda: cache.delete(f"post:{post.pk}"))`, deferred so a rolled-back write doesn't evict valid data (Part 13); (4) signal-driven invalidation, last, because it hides the cache dependency from readers of the write path. Session storage can ride the same Redis via `SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"` — cache-speed reads, database durability.

The low-level API also handles small coordination jobs that aren't strictly "caching" — counters and cheap rate limits ride the atomic `incr`:

```python
def is_rate_limited(user_id: int, limit: int = 60) -> bool:
    key = f"rl:{user_id}:{timezone.now():%Y%m%d%H%M}"   # per-minute window
    try:
        count = cache.incr(key)
    except ValueError:                                    # key didn't exist yet
        cache.set(key, 1, timeout=90)
        count = 1
    return count > limit
```

(For anything with real fairness or distributed-lock requirements, use Redis primitives directly — the [Redis guide](REDIS_STUDY_GUIDE.md) covers `SET NX EX` locks and sliding windows; this fixed-window sketch is the 80% version.)

Two operational cache behaviors to know before they know you. **Stampedes**: when a popular key expires, every concurrent request misses and recomputes at once — for genuinely expensive values, serve slightly-stale data while a single request refreshes (a short `cache.add()` lock is the minimal version). **`Vary` and per-view caching**: `@cache_page` keys on the URL, so a view whose output depends on a header must declare it (`@vary_on_headers("Accept-Language")`) or users will be served each other's variants — the every-dimension-in-the-key rule again, enforced at the HTTP layer.

A final honest note: Django's cache framework is also the wrong tool for some things — rate limiting and distributed locks want Redis primitives directly (`INCR`, `SET NX EX`), and HTTP-level caching (`ETag`, `Cache-Control`, CDN) handles anonymous traffic before it ever reaches Django (Part 17).

If you remember one thing from Part 12: **measure with debug-toolbar, fix N+1s and add real indexes before caching anything — then cache at the narrowest useful level, put every output-changing dimension in the key, and prefer TTLs and versioned keys over clever invalidation.**

---

## Part 13 — Signals, Transactions & Where Business Logic Lives

This part is about the architecture question every Django codebase eventually answers, well or badly: *when something happens — an order is placed, a post is published — where does the code that responds to it live?* Django offers signals, model methods, and plain functions; the trade-offs between them are sharper than the docs let on.

### Signals: What They Are and Why to Distrust Them

[Signals](https://docs.djangoproject.com/en/stable/topics/signals/) are in-process publish/subscribe: the framework (or you) sends a named event, and registered receivers run synchronously, in the same transaction, on the same request. The built-ins cover model lifecycle (`pre_save`/`post_save`, `pre_delete`/`post_delete`, `m2m_changed`) and request lifecycle. Mechanically:

```python
# apps/blog/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Post)
def invalidate_post_cache(sender, instance, created, **kwargs):
    cache.delete(f"post:{instance.slug}")

# apps/blog/apps.py — registration must happen at app load
class BlogConfig(AppConfig):
    name = "apps.blog"
    def ready(self):
        from . import signals  # noqa: F401  (import for side effect)
```

The `ready()` dance matters: a signals module nobody imports registers nothing, and the symptom is a handler that silently never fires.

Now the architecture critique, which the Django community has converged on hard: **signals make control flow invisible.** Reading `post.save()` tells you nothing about the cache invalidation, search-index update, and notification email that are about to happen; the only way to know is to grep for receivers. Debugging means stepping through dispatch machinery. Testing means remembering to disconnect things. And `post_save` doesn't even mean what people think — it fires *before the transaction commits*, so a receiver that sends an email celebrates writes that may yet roll back. The honest decision rule:

| Use signals when… | Use explicit calls when… |
|---|---|
| You *can't* edit the sending code (third-party app's models) | It's your code calling your code |
| The receiver is a genuinely incidental side effect (cache eviction, audit log) | The behavior is part of the business operation's definition |
| Many apps must react and coupling them is worse than indirection | One or two call sites exist |

Which is to say: signals are a tool for *framework extension points*, and a liability as an *application architecture*. For your own workflows, write the explicit version — a **service function** that states the whole operation in one place:

```python
# apps/blog/services.py
from django.db import transaction


def publish_post(*, post: Post, actor: User) -> Post:
    """The single place 'publishing' is defined."""
    if post.author != actor and not actor.has_perm("blog.publish_post"):
        raise PermissionDenied
    with transaction.atomic():
        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.save(update_fields=["status", "published_at"])
        SearchIndexEntry.objects.update_or_create(
            post=post, defaults={"text": post.body}
        )
        # Side effects with external reach wait for the COMMIT:
        transaction.on_commit(lambda: notify_subscribers.delay(post.pk))
        transaction.on_commit(lambda: cache.delete(f"post:{post.slug}"))
    return post
```

Views, admin actions, management commands, and API endpoints all call `publish_post()`; the workflow has one definition, greppable and testable. This "services layer" pattern (the [HackSoftware Django style guide](https://github.com/HackSoftware/Django-Styleguide) is its best-known articulation) and the "fat models" tradition (logic as model methods, fine while operations touch one model) are both reasonable; the line to hold is that **operations spanning multiple models, external services, or queued work deserve a named function**, not a `save()` override and three signal receivers.

Two pragmatic footnotes. The auth-event built-ins (`user_logged_in`, `user_login_failed`) are reasonable receivers for audit trails — framework events you genuinely can't intercept any other way. And in tests, signal side effects are a recurring source of mystery slowness and flakiness: design receivers to be cheap and idempotent, and when a test needs quiet, patch the receiver's *work*, not the dispatch machinery.

### Transactions: `atomic` and `on_commit`

Django runs in autocommit by default — each ORM write is its own transaction. [`transaction.atomic`](https://docs.djangoproject.com/en/stable/topics/db/transactions/) (context manager or decorator) makes a block all-or-nothing, and nests via savepoints. Many teams set `ATOMIC_REQUESTS = True` to wrap every request in a transaction — simple and safe-by-default, at the cost of longer-held connections and the occasional surprise around long-running views.

The interaction that produces real-world bugs is **side effects inside transactions**. The Celery task enqueued mid-transaction can start running *before the commit lands*, query for the row, and find nothing (or worse, the transaction rolls back and the email already went out). [`transaction.on_commit(callback)`](https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit) is the fix, as in `publish_post` above: callbacks run only after a successful commit, and never on rollback. The rule generalizes: **database writes go inside `atomic`; anything that escapes the database — emails, webhooks, task enqueues, cache eviction — goes in `on_commit`.** For read-modify-write races, you've already met `F()` (Part 4); the heavier tool is `select_for_update()`, which takes row locks inside `atomic` — correct for things like inventory decrements, with the usual locking caveats covered in the [Postgres guide](POSTGRES.md).

The lock-based pattern, since Part 4 promised it:

```python
def reserve_stock(*, sku: str, quantity: int) -> None:
    with transaction.atomic():
        item = (Inventory.objects
                .select_for_update()          # row lock until COMMIT
                .get(sku=sku))
        if item.available < quantity:
            raise OutOfStock(sku)
        item.available -= quantity
        item.save(update_fields=["available"])
```

The check-then-decrement is safe because concurrent calls queue on the row lock. Use it when the decision depends on the value being changed (the `F()` one-liner can't express "fail if insufficient"); keep locked sections short, and know your lock ordering if you ever lock multiple rows — deadlock pages are written in exactly this code.

If you remember one thing from Part 13: **business operations deserve one named, explicit function wrapping its writes in `atomic` and deferring its side effects with `on_commit` — reserve signals for code you don't own, and never trust `post_save` to mean "committed."**

---

## Part 14 — Async Django, Celery & Background Work

"Async Django" is really three separate questions wearing one name: *Can my views be coroutines?* (yes, with caveats), *Can Django hold WebSockets?* (yes, via Channels), and *Where does slow work go?* (a task queue, which has nothing to do with `async def` at all). Teams that conflate these adopt the wrong tool; this part keeps them apart.

### Async Views: What's Real and What Isn't

Since 4.1, Django supports `async def` views end-to-end under ASGI, and an async-capable middleware/ORM interface has grown release by release. The honest picture, which the [official async docs](https://docs.djangoproject.com/en/stable/topics/async/) themselves are upfront about:

```python
import asyncio
import httpx


async def dashboard(request):
    async with httpx.AsyncClient() as client:
        # Three slow upstream calls, overlapped — THE async win
        weather, stocks, news = await asyncio.gather(
            client.get(WEATHER_URL), client.get(STOCKS_URL), client.get(NEWS_URL),
        )
    # Async ORM interface: real API, but read the next paragraph
    user_count = await User.objects.acount()
    posts = [p async for p in Post.objects.published()[:10]]
    return JsonResponse({...})
```

The ORM exposes async methods — `aget`, `acreate`, `acount`, `afirst`, `async for` iteration, `asave` — but **the database layer underneath is still synchronous**: these methods currently wrap the blocking driver calls via `sync_to_async`, hopping to a thread rather than doing native async I/O ([the docs say so explicitly](https://docs.djangoproject.com/en/stable/topics/async/#queries-the-orm)). Two consequences. First, the genuine wins for async views are **external-I/O fan-out** (the `gather` above), long-polling/SSE-style streaming, and holding many slow connections cheaply — *not* faster database CRUD; a sync view under gunicorn will serve your ORM-bound endpoint just as well or better. Second, calling sync code from async context requires discipline: blocking inside a coroutine stalls the whole event loop (the failure mode dissected in the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md)), so Django will raise `SynchronousOnlyOperation` if you touch lazy ORM attributes in async context, and the bridges — [`sync_to_async` and `async_to_sync`](https://docs.djangoproject.com/en/stable/topics/async/#async-adapter-functions) from asgiref — each cost a context switch. A view that crosses the boundary five times has paid more than it gained.

The decision rule: **stay sync by default; go async per-view where waiting-on-the-network dominates; deploy under ASGI (uvicorn) when you do.** Django happily mixes sync and async views in one project, adapting whichever doesn't match the server — that per-view granularity is the pragmatic path, not a big-bang rewrite. For WebSockets, [Django Channels](https://channels.readthedocs.io/) extends ASGI Django with consumers (long-lived connection handlers), groups (fan-out), and a Redis channel layer — solid for real-time *features* on a Django app, while real-time-as-the-product remains the "when Django is wrong" case from Part 1.

A Channels consumer, to make "views for connections" concrete:

```python
# apps/notifications/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]            # auth via the ASGI middleware stack
        if not user.is_authenticated:
            await self.close()
            return
        self.group = f"user-{user.pk}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def notify(self, event):           # invoked via group_send(type="notify")
        await self.send_json(event["payload"])
```

Server-side code anywhere — a Celery task, a service function's `on_commit` hook — pushes with `async_to_sync(channel_layer.group_send)("user-42", {"type": "notify", "payload": {...}})`. Note what changed: connection lifecycle (connect/disconnect/reconnect) is now your problem, state lives on the consumer instance, and the Redis channel layer is load-bearing infrastructure. That's the complexity real-time features actually cost, which is why the decision table matters:

| Workload | Right tool |
|---|---|
| Slow work the response shouldn't wait for (email, PDFs, imports) | Task queue (Celery — below) |
| One request fanning out to several external APIs | Async view under ASGI |
| WebSockets / server push | Channels (or a dedicated real-time service — Part 1) |
| Ordinary DB-backed CRUD | Sync views under gunicorn — change nothing |
| "Our pages are slow" | Parts 4 and 12 (queries, indexes, caching) — not async |

### Celery: Where Slow Work Actually Goes

The most common "we need async" diagnosis is actually "this request does slow work that shouldn't block the response" — sending email, rendering a PDF, calling a flaky third-party API. The cure for that is not coroutines; it's a **task queue**: the view enqueues a job and returns immediately, a separate worker process executes it, a broker (Redis or RabbitMQ) carries the messages. [Celery](https://docs.celeryq.dev/en/stable/) is the Django ecosystem's default:

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
app = Celery("myproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# apps/blog/tasks.py
from celery import shared_task


@shared_task(bind=True, max_retries=3, retry_backoff=True, acks_late=True)
def notify_subscribers(self, post_id: int):
    try:
        post = Post.objects.get(pk=post_id)     # re-fetch: rows can change between
    except Post.DoesNotExist:                   # enqueue and execution
        return                                  # deleted meanwhile — fine, do nothing
    try:
        send_digest_email(post)
    except SMTPException as exc:
        raise self.retry(exc=exc)               # exponential backoff via retry_backoff

# call site — inside the service function from Part 13:
transaction.on_commit(lambda: notify_subscribers.delay(post.pk))
```

The signature encodes the three laws of queue hygiene. **Pass IDs, not objects**: arguments are serialized (JSON) and the worker may run seconds or hours later — a pickled model instance would be a stale snapshot; an ID forces a fresh read. **Design for at-least-once delivery**: brokers redeliver on worker death and `retry` re-runs on failure, so tasks must be *idempotent* — running twice must be safe (guard with natural keys, `update_or_create`, or a "processed" flag). **Enqueue on commit**, never inside the transaction — Part 13's race in the wild. Beyond fire-and-forget: [Celery Beat](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html) (with [django-celery-beat](https://django-celery-beat.readthedocs.io/) for DB-backed schedules) covers cron-style work; chains/chords compose workflows (sparingly — debugging a distributed graph is no one's hobby); [Flower](https://flower.readthedocs.io/) watches queue depth and failures, which *will* otherwise fail silently. For modest needs, [Django-Q2](https://django-q2.readthedocs.io/en/latest/) or [Huey](https://huey.readthedocs.io/en/latest/) deliver 80% of this with a fraction of the operational surface — the right call for many projects.

If you remember one thing from Part 14: **async views help when requests wait on external I/O (the ORM underneath is still sync-backed); slow work belongs in a task queue regardless — enqueued `on_commit`, passing IDs, written to survive running twice.**

---

## Part 15 — Testing

Django apps are integration-heavy by nature — a feature is a URL, a view, a form, a queryset, and a template agreeing with each other — and Django's test tooling is built for exactly that: spin up a real (throwaway) database, run real requests through the real middleware stack, and assert on what comes out. The payoff for learning it properly is that "integration test" stops meaning "slow and flaky" and starts meaning "the default."

### The Test Case Ladder

Four base classes, chosen by how much realism the test needs. `SimpleTestCase` forbids database access — for URL resolution, template logic, pure helpers; it stays honest by *failing* if code under test sneaks a query. **`TestCase` is the workhorse**: it wraps each test in a transaction rolled back afterwards (fast isolation) and adds `setUpTestData()` for building shared fixtures *once per class* instead of once per test — the single biggest suite speedup available. `TransactionTestCase` actually commits and flushes — needed only when testing transaction behavior itself (`on_commit` callbacks, `select_for_update`); note `TestCase.captureOnCommitCallbacks()` now covers the common `on_commit` case without the slow class. `LiveServerTestCase` boots a real HTTP server for browser/Playwright tests — a handful of these for critical journeys, no more. Docs: [testing tools](https://docs.djangoproject.com/en/stable/topics/testing/tools/). (Most production teams run all of this under [pytest-django](https://pytest-django.readthedocs.io/) for fixtures and better assertion output; the Django classes still do the heavy lifting underneath.)

### What Production-Grade Django Tests Look Like

```python
# apps/blog/tests/test_views.py
from django.test import TestCase
from django.urls import reverse

from .factories import PostFactory, UserFactory


class PostListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = UserFactory()
        cls.published = PostFactory.create_batch(3, status="published")
        cls.draft = PostFactory(status="draft", author=cls.author)

    def test_lists_only_published_posts(self):
        response = self.client.get(reverse("blog:post_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.draft, response.context["posts"])
        self.assertEqual(len(response.context["posts"]), 3)

    def test_query_count_is_constant(self):
        PostFactory.create_batch(20, status="published")
        with self.assertNumQueries(3):          # posts + prefetch + count(pagination)
            self.client.get(reverse("blog:post_list"))

    def test_draft_invisible_to_non_author(self):
        self.client.force_login(UserFactory())
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)   # scoped queryset = 404, Part 9
```

Three patterns to steal. **`assertNumQueries` turns Part 4's query discipline into a contract**: when someone's innocent template change reintroduces an N+1, CI fails with "expected 3 queries, got 24" instead of production failing at scale — this is the highest-value Django-specific assertion that almost nobody uses. **The test client runs the whole pipeline** — middleware, URL resolution, view, template — so `response.context` and status-code assertions test what users actually experience; use `RequestFactory` instead when you want to unit-test a view in isolation (faster, but *you* must supply `request.user` and friends since no middleware runs). **Authorization tests are non-negotiable**: every scoped queryset from Part 9 deserves a "wrong user gets 404" test, because authorization bugs are the ones that make the news.

**Factories over fixtures.** JSON fixture files rot — every schema change breaks them, and nobody can tell which of forty fields matters to a given test. [factory_boy](https://factoryboy.readthedocs.io/en/stable/) builds objects programmatically with defaults you override only where the test cares:

```python
# apps/blog/tests/factories.py
import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@example.com")


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "blog.Post"
    title = factory.Faker("sentence", nb_words=5)
    slug = factory.Sequence(lambda n: f"post-{n}")
    author = factory.SubFactory(UserFactory)
    body = factory.Faker("paragraph")
    status = "draft"
```

`PostFactory(status="published")` reads as its intent; relationships materialize via `SubFactory`. Mocking earns one paragraph of restraint: **mock the boundaries you don't own** — `unittest.mock.patch` for the Stripe client, `EMAIL_BACKEND` defaults to in-memory in tests (`django.core.mail.outbox`), Celery's `task_always_eager` runs tasks inline (with the caveat that eager mode skips serialization, so keep a few real-broker tests if task arguments are exotic) — and don't mock your own models or views, because then the test verifies your mocks. `override_settings` pins any configuration a test depends on. Speed matters because slow suites stop being run: `setUpTestData`, `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]` in test settings (password hashing is *designed* to be slow — Part 9 — which is exactly wrong for tests), and `manage.py test --parallel --keepdb`.

A note on testing the async code from Part 14: Django's test cases support `async def test_*` methods and the test client has an async twin (`self.async_client`), while Celery tasks are usually best tested by calling the task function *directly* as a unit (it's just a function) plus one or two `task_always_eager` integration tests of the enqueue path.

What to test, in priority order: **models and querysets** (custom managers, constraints — cheap tests protecting rules everything else assumes), **forms and serializers** (the validation pipeline: valid input, each rejection rule, the boundary cases), **views and endpoints** (status, context/payload, redirects, and always permissions), then a few **end-to-end journeys** for the flows that pay the bills. Run `coverage run -m pytest && coverage report` in CI as a blind-spot detector — but treat the percentage as a flashlight, not a goal; 75% with strong assertions beats assertion-free 95% every time.

If you remember one thing from Part 15: **`TestCase` + the test client + factories cover most of a Django app honestly — pin query counts with `assertNumQueries`, test that the wrong user gets a 404, and mock only the boundaries you don't own.**

---

## Part 16 — Security

Security is where Django's "secure by default" philosophy earns its keep: the famous web vulnerability classes are each met by a default-on protection, and most Django security incidents are someone *disabling* a protection, not a gap in the framework. The way to study this part is attack-first — know what each attack does, then what Django does about it, then which line of code would turn the protection off. The framework's own [security overview](https://docs.djangoproject.com/en/stable/topics/security/) is the canonical companion.

**SQL injection** — attacker-controlled input spliced into SQL. The ORM parameterizes everything: `Post.objects.filter(title=user_input)` sends the input as a bound parameter, never as SQL text. The protection survives `raw()` and `cursor.execute()` *only if you keep using parameters*:

```python
# SAFE — parameterized, even though it's raw SQL
Post.objects.raw("SELECT * FROM blog_post WHERE title = %s", [user_input])

# VULNERABLE — you just wrote the injection yourself
Post.objects.raw(f"SELECT * FROM blog_post WHERE title = '{user_input}'")
```

The grep-able rule: any f-string or `%`-format that builds SQL (or a queryset `.extra()` call) is a finding. Docs: [SQL injection protection](https://docs.djangoproject.com/en/stable/topics/security/#sql-injection-protection).

**XSS** — attacker-controlled content executing as script in another user's browser. Template auto-escaping (Part 7) is the default defense; the off-switches are `|safe`, `mark_safe()`, and hand-built HTML in Python. Audit those the way you'd audit `unsafe` blocks in Rust: each one is a claim that the content is trusted or sanitized, and the claim should be checkable. Pass data to JS via `json_script`, sanitize user-supplied rich text with a real sanitizer, and add a [Content-Security-Policy](https://docs.djangoproject.com/en/stable/howto/csp/) header (first-party support landed in Django 6.0; [django-csp](https://django-csp.readthedocs.io/) before that) as defense in depth.

**CSRF** — a malicious site causing a victim's browser to submit a state-changing request to yours, riding the session cookie the browser helpfully attaches. Django's `CsrfViewMiddleware` requires every unsafe-method request to carry a secret token (`{% csrf_token %}` in forms, `X-CSRFToken` header from JS) that a foreign page can't read. The protection is only as good as its coverage: `@csrf_exempt` is the off-switch, and the legitimate uses are rare and specific — a webhook endpoint authenticated by *signature verification* (Stripe, GitHub) doesn't need CSRF because it doesn't use cookies, but "the token was annoying from my SPA" is not a reason, it's an incident report with a future date. Token-authenticated API endpoints (JWT in a header) are inherently CSRF-immune — the attack only exists where browsers attach credentials automatically. Docs: [CSRF reference](https://docs.djangoproject.com/en/stable/ref/csrf/).

**Clickjacking** — your page in an invisible iframe over a decoy UI. `XFrameOptionsMiddleware` sends `X-Frame-Options: DENY` by default. Leave it on.

**Host-header attacks** — Part 1's `ALLOWED_HOSTS`, which is why `["*"]` in production is a real vulnerability, not a config shortcut.

**Transport security** is configuration, all of it living in `SecurityMiddleware` and the production settings file from Part 1: `SECURE_SSL_REDIRECT` (force HTTPS), `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` (cookies never travel plaintext), `SESSION_COOKIE_HTTPONLY` (JS can't read the session cookie — on by default), and HSTS (`SECURE_HSTS_SECONDS`, started small and raised, because HSTS misconfiguration locks browsers out of your domain for its full duration). Behind a proxy/load balancer that terminates TLS, set `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` or Django will think every request is insecure and redirect-loop.

The browser-facing result of all this configuration is a set of response headers worth recognizing on sight:

| Header | Set by | Defends against |
|---|---|---|
| `Strict-Transport-Security` | `SECURE_HSTS_SECONDS` | protocol-downgrade, cookie theft over HTTP |
| `X-Frame-Options: DENY` | `XFrameOptionsMiddleware` | clickjacking |
| `X-Content-Type-Options: nosniff` | `SecurityMiddleware` (default on) | MIME-sniffing attacks |
| `Referrer-Policy: same-origin` | `SecurityMiddleware` (default on) | URL leakage to third parties |
| `Content-Security-Policy` | CSP config / django-csp | XSS blast-radius reduction |
| `Set-Cookie: ...; Secure; HttpOnly; SameSite=Lax` | session/CSRF cookie settings | cookie theft, some CSRF |

A two-minute check of any deployment: open devtools, load a page, read the response headers against this table — or let [securityheaders.com](https://securityheaders.com/) do it.

Password policy is configuration too: [`AUTH_PASSWORD_VALIDATORS`](https://docs.djangoproject.com/en/stable/topics/auth/passwords/#password-validation) (minimum length, common-password list, similarity-to-username) enforces baseline strength at registration and password change — tune it rather than inventing your own complexity rules, and pair it with rate limiting on the login view rather than aggressive lockout policies that become their own denial-of-service vector.

Beyond the framework's automatic layer, three application-level habits round out the posture. **Mass assignment**: explicit `fields` lists in every form and serializer (Parts 8 and 11) — `"__all__"` is how `is_admin` becomes user-editable. **Authorization testing**: the wrong-user-gets-404 tests from Part 15, because the framework cannot know your access rules. **Secrets and dependencies**: keys in the environment (Part 1), `pip-audit`/Dependabot watching your requirements, and Django itself kept on a [supported version](https://www.djangoproject.com/download/#supported-versions) — LTS releases get three years of security patches, and the project's [security release process](https://docs.djangoproject.com/en/stable/internals/security/) is exemplary. Rate limiting ([django-ratelimit](https://django-ratelimit.readthedocs.io/), or DRF throttles) belongs on login and other abuse-prone endpoints. And the mechanical gate from Part 1, run in CI: `manage.py check --deploy`.

One more application-layer corner: **file uploads**. Validate size and content type server-side; never trust the client's filename for storage decisions; serve user uploads from a separate domain or with `Content-Disposition: attachment` where feasible (an uploaded HTML file served inline from your origin is stored XSS with extra steps); and remember `ImageField`'s Pillow check verifies the file *is* an image, not that it's harmless.

If you remember one thing from Part 16: **Django's defaults already defeat the classic attacks — your job is to not turn them off (`|safe`, `@csrf_exempt`, f-string SQL, `fields = "__all__"` are the off-switches), to configure the transport layer, and to test authorization yourself because the framework can't.**

---

## Part 17 — Deployment & Operations

`manage.py runserver` is a development convenience — single-threaded, unaudited, auto-reloading — and the first rule of Django deployment is that it never faces the internet. A production deployment is a small stack of cooperating pieces, each with one job:

```text
internet
  → reverse proxy / load balancer (nginx, Caddy, or your platform's edge)
      TLS termination, buffering, static/media files (or CDN)
    → application server: gunicorn (WSGI) or uvicorn (ASGI), several workers
      → Django
    → Postgres   ← CONN_MAX_AGE / PgBouncer
    → Redis      ← cache, sessions, Celery broker
    → Celery workers (+ Beat)   ← the same codebase, different process
```

### The Application Server

For the standard sync app, [gunicorn](https://gunicorn.org/) is the boring, correct choice — a pre-fork process manager running N copies of your WSGI app:

```bash
gunicorn config.wsgi:application \
  --workers 5 \                  # start near (2 × CPU cores) + 1, then tune on metrics
  --threads 2 \                  # modest thread count helps I/O-flavored sync apps
  --timeout 30 \                 # kill stuck workers; long work belongs in Celery (Part 14)
  --max-requests 1000 --max-requests-jitter 100 \   # recycle workers: leak amnesty
  --bind 0.0.0.0:8000
```

Each worker is a full process holding its own database connections — which is why worker count × instance count is what PgBouncer (Part 12) exists to absorb. The `(2 × CPU) + 1` formula is a starting point, not a law; memory per worker is usually the binding constraint. For async Django (Part 14), the equivalent is uvicorn — in production typically run *under* gunicorn as a worker class, getting uvicorn's event loop plus gunicorn's process supervision:

```bash
gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker --workers 4
```

Choose based on what you actually use: no async views and no Channels means WSGI/gunicorn, full stop. Docs: [WSGI deployment](https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/), [ASGI deployment](https://docs.djangoproject.com/en/stable/howto/deployment/asgi/).

### Static Files and Media: Two Problems, Not One

Conflating these causes a disproportionate share of deployment confusion, so: **static files** are your assets (CSS, JS, images you shipped) — versioned with the code, collected at build time; **media** is *user-uploaded content* — runtime data, like database rows with bytes. They need different answers.

Static files: each app and the project contribute files; `manage.py collectstatic` gathers them into `STATIC_ROOT` at build/deploy time; something efficient serves them. The modern default answer is [WhiteNoise](https://whitenoise.readthedocs.io/) — serve them from the Django process itself, with compression and far-future cache headers, no nginx config required:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # right after SecurityMiddleware
    ...
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

The `Manifest` part is the clever bit: files are renamed to `app.3f2a8b.css` (content hash), so browsers and CDNs can cache them *forever* — a new deploy produces new hashes, making cache invalidation automatic. "Isn't serving static from Python slow?" was true once; WhiteNoise + a CDN in front is the documented, benchmarked, perfectly standard answer for most apps. (`STORAGES` is the modern unified setting, replacing the old `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE` pair.) Docs: [staticfiles](https://docs.djangoproject.com/en/stable/ref/contrib/staticfiles/), [static deployment how-to](https://docs.djangoproject.com/en/stable/howto/static-files/deployment/).

Media: uploaded files can't live on an app server's disk once you have two app servers (or any ephemeral container). Production means object storage — S3/GCS/R2 via [django-storages](https://django-storages.readthedocs.io/) as the `"default"` storage backend — with downloads served by the bucket/CDN (pre-signed URLs for private content), never proxied through Django. Validate uploads (size, type) and never trust user filenames.

### Containers, Pipelines, and the Release Step

The standard shape (the [Docker guide](DOCKER_STUDY_GUIDE.md) covers the container fundamentals): a multi-stage Dockerfile — build stage installs dependencies and runs `collectstatic`; slim runtime stage runs gunicorn as a non-root user — with one image powering web, worker, and beat containers via different commands. Compose runs the local constellation (web + Postgres + Redis + worker). CI (the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md)) runs lint (ruff), types (mypy + [django-stubs](https://github.com/typeddjango/django-stubs)), tests, plus the two Django-specific gates from earlier parts: `makemigrations --check` (models and migrations agree) and `check --deploy`.

```yaml
# compose.yaml — the local constellation
services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000   # dev server IS right, locally
    volumes: [".:/app"]
    env_file: .env
    depends_on: [db, redis]
    ports: ["8000:8000"]
  worker:
    build: .
    command: celery -A config worker -l info
    env_file: .env
    depends_on: [db, redis]
  db:
    image: postgres:17
    environment: {POSTGRES_PASSWORD: postgres}
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7
volumes:
  pgdata:
```

Same image, different commands — web and worker stay in lockstep, and the dev/prod gap shrinks to settings and the server command.

The step that distinguishes teams that page from teams that sleep is **migrations in the release pipeline**: run `manage.py migrate` as a release-phase step *before* new code receives traffic — never at container startup (ten replicas racing to migrate), and always with Part 5's compatibility discipline, because old code serves traffic while the migration runs.

```dockerfile
# Dockerfile — the two-stage shape
FROM python:3.13-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings.production
RUN DJANGO_SECRET_KEY=build-placeholder python manage.py collectstatic --noinput
USER nobody
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

The `collectstatic`-at-build-time line is why WhiteNoise fits containers so well — the image is self-contained, no shared volume or separate static server required. (The placeholder secret key is an honest wart: `collectstatic` imports settings, settings demand a key, and the real one belongs only in the runtime environment.)

### Observability and Scaling

Logging: configure the `LOGGING` dict to send structured output to stdout (containers expect it; [structlog](https://www.structlog.org/en/stable/) for JSON), and ship exceptions to [Sentry](https://docs.sentry.io/platforms/python/guides/django/) — its Django integration captures the request, user, and SQL context around every error and is the single highest-value operational add-on. Metrics ([django-prometheus](https://github.com/django-commons/django-prometheus)) and tracing follow as you grow — the [Observability guide](OBSERVABILITY_STUDY_GUIDE.md) covers the discipline; the Django-specific golden signals are request latency/error rate, **DB connections and slow queries**, **cache hit rate**, and **Celery queue depth** (the one that silently builds for hours). A `/health/` endpoint that checks the database (and optionally cache/broker — [django-health-check](https://django-health-check.readthedocs.io/en/stable/)) gates load balancers and rollouts.

```python
# config/settings/production.py — structured lines to stdout; the platform ships them
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "pythonjsonlogger.json.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"level": "WARNING"},      # 4xx/5xx summaries
        "django.db.backends": {"level": "WARNING"},  # DEBUG here logs every query — dev only
    },
}
```

Scaling, in the order it actually happens: Django app processes are stateless (sessions in the DB/cache, media in object storage — everything above already arranged this), so the first move is simply **more instances behind the load balancer**. The database is where scaling gets real, and the levers are Part 12's in order — query discipline, indexes, caching, connection pooling — long before read replicas (`DATABASE_ROUTERS`, with replica-lag consistency caveats) or partitioning. A CDN absorbs static/media traffic. Celery scales by splitting queues (urgent vs. batch) before adding workers. None of this is Django-specific, which is the point: a well-built Django app is a stateless twelve-factor citizen, and ordinary infrastructure scaling applies.

Before first real traffic, walk this list — it compresses the whole part: `DEBUG=False` with real `ALLOWED_HOSTS`; secrets only in the environment; `check --deploy` clean; migrations run as a release step; `collectstatic` baked into the image; media on object storage; HTTPS and cookie flags on; Sentry wired; a health endpoint behind the load balancer; and a tested way to roll back — which, per Part 5, means your latest migrations are reversible or at least backward-compatible.

If you remember one thing from Part 17: **gunicorn (or uvicorn under it) runs the app, WhiteNoise + hashed filenames serve static files, object storage holds media, migrations run as a release step before traffic shifts — and Sentry plus a health check are the first two operational add-ons, not the last.**

---

## Where to Go From Here

**The ecosystem toolbox.** Mature Django projects assemble a familiar cast of third-party packages. Treat this as a menu, not a checklist — each earns its place by solving a problem you actually have:

| Package | Problem it solves | Covered in |
|---|---|---|
| [django-environ](https://django-environ.readthedocs.io/) | Typed env-var settings | Part 1 |
| [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/) | See your SQL while developing | Parts 4, 12 |
| [django-extensions](https://django-extensions.readthedocs.io/) | `shell_plus`, `show_urls`, model graphs | — |
| [django-allauth](https://docs.allauth.org/en/latest/) | Registration, email verification, social login | Part 9 |
| [DRF](https://www.django-rest-framework.org/) + [drf-spectacular](https://drf-spectacular.readthedocs.io/en/stable/) + [django-filter](https://django-filter.readthedocs.io/en/stable/) + [simplejwt](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/) | APIs: framework, OpenAPI, filtering, JWT | Part 11 |
| [django-cors-headers](https://github.com/adamchainz/django-cors-headers) | CORS for separate frontends | — |
| [django-storages](https://django-storages.readthedocs.io/) | S3/GCS/Azure media storage | Part 17 |
| [WhiteNoise](https://whitenoise.readthedocs.io/) | Static file serving | Part 17 |
| [Celery](https://docs.celeryq.dev/en/stable/) + [django-celery-beat](https://django-celery-beat.readthedocs.io/) + [Flower](https://flower.readthedocs.io/) | Background work, schedules, monitoring | Part 14 |
| [factory_boy](https://factoryboy.readthedocs.io/en/stable/) + [pytest-django](https://pytest-django.readthedocs.io/) | Test data and test runner | Part 15 |
| [sentry-sdk](https://docs.sentry.io/platforms/python/guides/django/) | Error tracking | Part 17 |
| [django-guardian](https://django-guardian.readthedocs.io/en/stable/) | Assignable per-object permissions | Part 9 |
| [django-simple-history](https://django-simple-history.readthedocs.io/en/stable/) / [django-auditlog](https://django-auditlog.readthedocs.io/en/latest/) | Model change history / audit trails | — |
| [django-waffle](https://waffle.readthedocs.io/en/latest/) | Feature flags and gradual rollouts | — |
| [django-tenants](https://django-tenants.readthedocs.io/) | Schema-per-tenant multi-tenancy | — |
| [django-import-export](https://django-import-export.readthedocs.io/) | CSV/Excel in the admin | Part 10 |

### Advanced Patterns in Brief

These recur in production codebases often enough to deserve orientation — though each is "just" a composition of parts you now know.

**Multi-tenancy.** The default answer is a `tenant` foreign key on every tenant-owned model plus Part 9's scoping discipline, with middleware resolving the tenant once per request:

```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        subdomain = request.get_host().split(".")[0]
        request.tenant = get_object_or_404(Organization, slug=subdomain)
        return self.get_response(request)
```

Every `get_queryset()` then filters by `self.request.tenant`, and Part 15's isolation tests are not optional — most multi-tenancy bugs are isolation bugs. Schema-per-tenant ([django-tenants](https://django-tenants.readthedocs.io/)) buys database-level separation at the cost of migrations-per-schema; choose it for compliance-grade isolation, not by default.

**Soft delete.** A `deleted_at` timestamp plus a default manager that hides the dead:

```python
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Document(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)
    objects = ActiveManager()          # default universe excludes deleted rows
    all_objects = models.Manager()     # the escape hatch — keep it, you'll need it

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
```

Part 4's warning applies in full: a filtering default manager hides rows from the admin and from future maintainers, and unique constraints now need `condition=Q(deleted_at__isnull=True)` so "deleted" values can be recreated. Decide early whether you truly need recoverability, or just an `is_archived` flag.

**Audit logging** — who changed what, when, from what to what: [django-simple-history](https://django-simple-history.readthedocs.io/en/stable/) for row snapshots, [django-auditlog](https://django-auditlog.readthedocs.io/en/latest/) for change events, or an explicit log write inside your Part 13 service functions — the same philosophy again: explicit beats magical, and an audit trail you can't explain in court wasn't worth collecting. **Feature flags** ([django-waffle](https://waffle.readthedocs.io/en/latest/)) separate deploy from release — per-user, per-group, or percentage rollouts, each flag with an owner and a removal date, because permanent flags are just configuration debt. **Webhooks**: *receive* with signature verification, a fast 2xx ack, Celery handoff, and idempotency keys (providers retry — Part 14's at-least-once world again); *send* from Celery with retries, payload signing, and a delivery log, because your webhooks are someone else's third-party integration.

**Build something real.** This guide's knowledge consolidates only under a project with teeth — reading creates recognition; building creates recall. Three projects that, between them, exercise every part:

1. **Multi-tenant SaaS task manager.** Custom user model from minute one (Part 9); organizations with role-based membership; *every* queryset org-scoped, with cross-tenant isolation proven by tests rather than asserted in comments (Parts 9, 15); a DRF API with JWT, filtering, and cursor pagination (Part 11); notification emails enqueued via `on_commit` (Parts 13–14); a Compose stack with Postgres and Redis (Part 17).
2. **E-commerce site.** Money as `DecimalField` and nothing else (Part 3); anonymous-session carts merging into account carts; an order state machine implemented as service functions with explicit, guarded transitions (Part 13); inventory decrements with `F()`/`select_for_update` proven safe under concurrent checkout (Parts 4, 13); Stripe webhooks with signature verification and idempotency (Part 16's trust model applied); admin actions for refunds and fulfillment (Part 10).
3. **Publishing platform.** Draft → review → publish with custom permissions (Part 9); scheduled publishing via Celery Beat (Part 14); fragment caching on the hot pages with deliberately chosen keys (Part 12); Postgres full-text search (Part 4); sitemaps via `django.contrib.sitemaps` and a real read-path optimization pass — the whole performance playbook end to end.

For each: debug-toolbar open while you build, `assertNumQueries` on every hot page before moving on, and deployed somewhere real with `DEBUG = False` — the last 10% of deployment is where half the learning lives.

**Read in this order**: the official [tutorial](https://docs.djangoproject.com/en/stable/intro/) if you skipped it (it's good), then topic guides as each part of this guide sends you there, then *Two Scoops* for conventions, then [Adam Johnson](https://adamj.eu/tech/) and the [Django News](https://django-news.com/) newsletter to stay current. And eventually: read Django's source. It is clear, conventional Python — the ORM, the auth system, a generic view traced through ccbv — and the moment the framework stops being magic is the moment you've mastered it.

### Epilogue: One Request, End to End

To bind the guide together, trace `POST /blog/my-post/comments/` from a logged-in browser through everything you've now studied. Gunicorn (Part 17) hands the bytes to Django's WSGI handler, which builds an `HttpRequest`. The middleware stack (Part 2) runs top-down: `SecurityMiddleware` confirms HTTPS; `SessionMiddleware` reads the session cookie and loads the session through `cached_db` (Parts 9, 12); `AuthenticationMiddleware` attaches a lazy `request.user`; `CsrfViewMiddleware` validates the token because this is a POST (Part 16). The URL resolver (Part 2) matches the namespaced pattern and calls the view with `slug="my-post"`. The view (Part 6) loads the post through a scoped, `select_related`-ed queryset (Parts 4, 9) — a stranger would have gotten a 404 right here — binds a `CommentForm` (Part 8), and `is_valid()` runs the validation pipeline. A service function (Part 13) wraps the insert in `transaction.atomic` and registers a notification task with `transaction.on_commit` — which Celery (Part 14) executes on a worker after the commit, re-fetching by ID, idempotently. The view returns a redirect (Post/Redirect/Get); the response climbs back up the middleware stack collecting security headers; gunicorn writes it to the socket. A test in CI (Part 15) asserts this whole path costs exactly four queries and that the wrong user gets a 404; Sentry (Part 17) is watching in case any of it throws. Every part of this guide is one clause of that paragraph — which is the real sense in which Django is a *framework*: the pieces were designed to compose into exactly this pipeline.

The 80% is trivial. The 20% is possible. Now you know which is which.

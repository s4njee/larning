# Authentication & Authorization (Identity)

A depth-first guide to identity, authentication, and authorization in modern applications and distributed systems — the applied "how do I actually do auth securely in my app?" guide. It assumes you can build a web service and have *used* login forms and API tokens, but not that you understand what a JWT actually is, why password reset is the most-exploited flow in your app, or how Google decides whether you can open a Doc. The approach is concept-first but relentlessly worked: nearly every idea here comes with code, because auth is a domain where the gap between "I understand it" and "I implemented it correctly" is exactly where breaches live.

This guide sits deliberately between two others in the repo. The [Cryptography Fundamentals guide](CRYPTO_FUNDAMENTALS.md) covers the *primitives* underneath everything here — hashing, signatures, key exchange, TLS — and you should reach for it whenever this guide says "signed" or "hashed" and you want to know how. The [Kubernetes Security guide](k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md) covers *cluster-level* identity (RBAC, ServiceAccounts, admission control). This guide covers the layer in between: **identity in your application** — who the user is, how they prove it, and what they're allowed to do. It also connects to the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) (the browser auth-header problem), the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md) (revocation as a consistency problem), and the [Networking Fundamentals guide](NETWORKING_FUNDAMENTALS.md) (TLS, cookies, CORS).

Primary references: the [OAuth 2.1 draft](https://oauth.net/2.1/), [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html), the [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), and [Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) cheat sheets, the [WebAuthn spec](https://www.w3.org/TR/webauthn-3/), and Google's [Zanzibar paper](https://research.google/pubs/pub48190/).

---

## Table of Contents

1. [Part 1 — The Mental Model: AuthN vs AuthZ, Sessions vs Tokens](#part-1--the-mental-model-authn-vs-authz-sessions-vs-tokens)
2. [Part 2 — Passwords & Credential Storage](#part-2--passwords--credential-storage)
3. [Part 3 — MFA & Account Lifecycle](#part-3--mfa--account-lifecycle)
4. [Part 4 — JWTs in Depth](#part-4--jwts-in-depth)
5. [Part 5 — OAuth 2.0 & OpenID Connect](#part-5--oauth-20--openid-connect)
6. [Part 6 — Token Lifecycle & Revocation](#part-6--token-lifecycle--revocation)
7. [Part 7 — Enterprise SSO: SAML & SCIM](#part-7--enterprise-sso-saml--scim)
8. [Part 8 — Authorization Models (RBAC, ABAC, ReBAC)](#part-8--authorization-models-rbac-abac-rebac)
9. [Part 9 — Service-to-Service Auth](#part-9--service-to-service-auth)
10. [Part 10 — Application Architecture & Patterns](#part-10--application-architecture--patterns)
11. [Part 11 — Passkeys, Pitfalls & a Walkthrough](#part-11--passkeys-pitfalls--a-walkthrough)

---

## Part 1 — The Mental Model: AuthN vs AuthZ, Sessions vs Tokens

Before any code, pin down the two words people conflate and the one architectural fork that shapes everything after it.

### The Two Questions

Every identity system answers two distinct questions, and keeping them separate is the foundation of reasoning clearly about auth:

- **Authentication (AuthN) — *Who are you?*** Proving identity. Passwords, passkeys, "log in with Google," a fingerprint. The output is a verified principal: "this request is from user 42."
- **Authorization (AuthZ) — *What are you allowed to do?*** Deciding whether a known principal may perform an action. "User 42 may read document 7 but not delete it." The output is a yes/no decision on a specific action against a specific resource.

They run in that order — authenticate first, then authorize — and they fail differently: an AuthN failure is `401 Unauthorized` ("I don't know who you are"), an AuthZ failure is `403 Forbidden` ("I know who you are, and the answer is no"). Mixing them up is the source of endless confused error handling; get the two status codes right and you've already clarified your own thinking. Parts 1–7 are mostly about AuthN; Parts 8–10 are mostly about AuthZ.

### The Credential Problem

HTTP is stateless: every request arrives with no memory of the last. So after a user authenticates *once*, the system must issue a **credential** the client presents on every subsequent request to re-prove identity without re-entering a password. The entire design space of "how do I stay logged in" is about what that credential is and how it's verified. There are two fundamental models, and the choice between them ripples through your whole architecture.

### Model A: Stateful Sessions

The traditional model — the server remembers, the client holds only a pointer:

1. User logs in with credentials.
2. Server creates a **session record** in a store (Redis, Postgres) keyed by a cryptographically random `session_id`.
3. Server returns the `session_id` in a `Set-Cookie` header.
4. Browser sends the cookie automatically on every subsequent request; the server looks up the `session_id` to find the user.

```python
import secrets, redis, json
r = redis.Redis()

def login(user_id: int, response):
    session_id = secrets.token_urlsafe(32)          # 256 bits of entropy — unguessable
    r.setex(f"session:{session_id}", 3600,           # 1-hour TTL, refreshed on use
            json.dumps({"user_id": user_id, "created": time.time()}))
    response.set_cookie("sid", session_id,
                        httponly=True, secure=True, samesite="Strict", max_age=3600)

def authenticate(request) -> int | None:
    sid = request.cookies.get("sid")
    if not sid: return None
    raw = r.get(f"session:{sid}")
    return json.loads(raw)["user_id"] if raw else None
```

| Pros | Cons |
|---|---|
| **Instant revocation** — delete the record, the user is logged out *now* | **Stateful** — every request hits the session store (cheap with Redis, but a dependency) |
| **Always fresh** — each request re-reads current roles/permissions | **Cross-domain friction** — cookies are domain-bound; sharing across `app.x.com` and `api.y.com` needs care |
| **Simple to reason about** — the server is the source of truth | Scaling requires a *shared* session store (not in-process memory) across instances |

### Model B: Stateless Tokens

The distributed model — the credential *contains* the identity, cryptographically signed, so no lookup is needed:

1. User logs in.
2. Server builds a **JWT** containing the user ID, roles, and expiry, and **signs** it (Part 4).
3. Client stores the token and sends it as `Authorization: Bearer <token>`.
4. Server **verifies the signature mathematically** — no database lookup.

| Pros | Cons |
|---|---|
| **Stateless** — verify by signature alone; ideal for microservices and edge compute | **Revocation is hard** — a signed token is valid until it expires (Part 6) |
| **Cross-domain** — send the header to any origin | **Staleness** — a role change doesn't take effect until the token expires |
| No shared session store needed | Larger per-request payload; secrets/keys must be managed |

### The Honest Default

The industry over-rotated to "JWTs everywhere" in the 2010s and has since walked it back. The pragmatic 2026 guidance:

- **For a normal web app where you control the frontend and backend → use stateful sessions** (or the hybrid below). They're simpler, instantly revocable, and the "statefulness" cost is a Redis call. Most apps that reached for JWTs never needed them.
- **For APIs consumed by third parties, mobile apps, microservices, or true cross-domain SPAs → use tokens** (OAuth2/OIDC, Parts 5–6), where statelessness genuinely pays off.
- **The common hybrid:** a short-lived stateless *access token* for fast API verification, plus a stateful, revocable *refresh token* (Part 6). You get fast reads and real revocation.

### Where to Store the Credential in a Browser: XSS vs CSRF

If the client is a browser, *where* the credential lives determines which attack you're exposed to — and you must pick your poison consciously:

- **`localStorage` / JS-readable:** vulnerable to **XSS** (any injected script reads it and exfiltrates it) but immune to **CSRF** (the browser doesn't auto-send it; your code attaches the header explicitly).
- **`HttpOnly` cookie:** immune to **XSS** (JS cannot read it) but exposed to **CSRF** (the browser auto-attaches it to *any* request to your domain, including ones a malicious site triggers).

**The best practice:** store the credential in an **`HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict`) cookie** when client and API share a registrable domain. `SameSite` is what neutralizes CSRF for free — the cookie isn't sent on cross-site requests — which is why cookies beat `localStorage` for most apps. Reserve the `Authorization` header for cases where cookies can't work (native mobile, genuinely cross-domain), and pair it with a strict **Content-Security-Policy** (see the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md) and the web-security literature) to shrink the XSS surface. Never put long-lived credentials in `localStorage` if you can avoid it.

If you remember one thing from Part 1: **separate AuthN ("who are you?", 401) from AuthZ ("may you?", 403); then choose your credential model deliberately — stateful sessions for most apps (simple, instantly revocable), stateless tokens when you genuinely need cross-domain or microservice statelessness — and in browsers prefer `HttpOnly; Secure; SameSite` cookies, because `SameSite` kills CSRF and `HttpOnly` kills XSS-theft.**

```quiz
Q: What's the core trade-off between stateful sessions and stateless JWTs?
- [ ] Sessions are insecure; JWTs are secure
- [x] Sessions allow instant revocation and always-fresh roles at the cost of a session-store lookup per request; JWTs verify by signature alone (stateless) but a signed token stays valid until it expires — revocation and staleness are hard
- [ ] JWTs are always faster and better
- [ ] Sessions can't scale at all
> A session is a server-side record, so deleting it logs the user out *now* and each request re-reads current permissions — but every request hits the store. A JWT carries signed identity, so verification needs no lookup (great for microservices/edge), but you can't un-sign it: a revoked-but-unexpired token still validates, and a role change doesn't apply until expiry. The 2026 default is sessions for normal apps; tokens where statelessness genuinely pays.

Q: In a browser, why do `HttpOnly; Secure; SameSite` cookies beat storing the credential in `localStorage`?
- [ ] localStorage is slower to read
- [x] `HttpOnly` blocks XSS theft (JS can't read the cookie) and `SameSite` neutralizes CSRF for free (the cookie isn't sent on cross-site requests); localStorage is XSS-readable, and the header approach you'd pair with it carries the XSS exposure
- [ ] Cookies can't be stolen
- [ ] localStorage doesn't work over HTTPS
> The storage location picks your poison: `localStorage` is immune to CSRF (your code attaches it explicitly) but exposed to XSS (any injected script exfiltrates it); an `HttpOnly` cookie is immune to XSS theft but would be CSRF-exposed — except `SameSite=Lax/Strict` stops the browser sending it cross-site, closing CSRF. So the cookie gets both protections when client and API share a registrable domain; reserve the `Authorization` header for native/cross-domain cases.

Q: A request to view another user's private data is rejected. Should it be a 401 or a 403, and why does the distinction matter?
- [ ] 401, because the user isn't logged in
- [x] 403 — the user is authenticated (AuthN succeeded, "who you are") but not authorized (AuthZ failed, "may you?"); conflating them leads to bugs like re-prompting login when the real issue is permissions
- [ ] 404, to hide everything
- [ ] Either; they're interchangeable
> 401 means "I don't know who you are — authenticate," while 403 means "I know who you are, and you may not." Keeping AuthN and AuthZ separate clarifies both the response codes and the code: a logged-in user hitting a forbidden resource needs a 403, not a login redirect. (Sometimes you deliberately return 404 instead of 403 to avoid leaking that a resource exists — a separate, intentional choice.)
```

---

## Part 2 — Passwords & Credential Storage

Most guides skip straight to sessions and tokens — but the front door of almost every system is still a password, and it's where the most catastrophic, most common breaches happen. Get this wrong and nothing else matters: an attacker who dumps your user table walks in the front door of every account. This part is the non-negotiable baseline.

### Never Store What You Can Verify

The cardinal rule: **you never store passwords — you store a one-way hash of them, and you verify by re-hashing.** When a user logs in, you hash the submitted password and compare it to the stored hash. If your database leaks, the attacker gets hashes, not passwords — and a *correctly* chosen hash makes reversing them economically infeasible.

The critical distinction the [Crypto guide](CRYPTO_FUNDAMENTALS.md) hammers: **a password hash is not a general-purpose hash.** SHA-256 is *wrong* for passwords — it's designed to be *fast*, and fast is exactly what you don't want, because fast means an attacker can try billions of guesses per second against a leaked hash. Password hashing wants to be **deliberately slow and memory-hard.**

### The Right Algorithms

Use a purpose-built password hash, in this order of preference (2026):

1. **[Argon2id](https://argon2-cffi.readthedocs.io/en/stable/)** — the winner of the [Password Hashing Competition](https://www.password-hashing.net/) and the current default recommendation. Memory-hard (resists GPU/ASIC cracking) and tunable along time, memory, and parallelism.
2. **scrypt** — also memory-hard; a solid choice where Argon2 isn't available.
3. **bcrypt** — older but still acceptable and battle-tested; note its ~72-byte input truncation. Ubiquitous library support.
4. **PBKDF2** — only when you need FIPS compliance; it's not memory-hard, so it's the weakest of the four.

Three properties every password hash must have, and which these algorithms provide for you:

- **Salt** — a unique random value per password, stored alongside the hash. It ensures two users with the same password get different hashes, defeating **rainbow tables** (precomputed hash lookups) and stopping an attacker from seeing which users share a password. Modern libraries generate and embed the salt automatically — *don't roll your own.*
- **Cost / work factor** — a tunable that makes hashing slow (e.g., bcrypt's rounds, Argon2's memory/time). Set it so a single hash takes ~100–250ms on your hardware; re-tune upward as hardware improves.
- **(Optional) Pepper** — a secret added to all passwords, stored *outside* the database (in a secrets manager / HSM). If only the DB leaks, the pepper is still missing. Defense-in-depth, not a substitute for salt.

### Worked Example

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()                 # sane defaults: Argon2id, salt auto-generated & embedded

# Registration: hash and store. The output string ENCODES the algorithm, params, salt, and hash.
def register(username: str, password: str):
    hashed = ph.hash(password)
    # e.g. "$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>"  ← all self-contained
    db.users.insert(username=username, password_hash=hashed)

# Login: verify by re-hashing (the library extracts the salt+params from the stored string).
def verify_login(username: str, password: str) -> bool:
    user = db.users.get(username=username)
    if not user:
        ph.hash(password)             # ← dummy hash anyway to equalize timing (see below)
        return False
    try:
        ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False
    # Opportunistic upgrade: if you've raised the cost since this hash was made, re-hash now.
    if ph.check_needs_rehash(user.password_hash):
        db.users.update(username, password_hash=ph.hash(password))
    return True
```

Two subtleties in that code worth their own callout:

- **Timing attacks / user enumeration.** Notice the dummy `ph.hash` when the user doesn't exist. If "no such user" returns instantly but "wrong password" takes 200ms, an attacker can *enumerate valid usernames* by timing. Always do equivalent work on both paths — and return the *same generic error* ("invalid username or password") regardless of which was wrong.
- **`check_needs_rehash`** lets you transparently upgrade the work factor (or migrate bcrypt→Argon2) on each successful login, without forcing a password reset on every user.

### Defending the Login Endpoint

Hashing protects you *after* a DB leak. You also have to protect the live login endpoint from online guessing:

- **Rate limiting** — cap attempts per IP *and* per account (an attacker rotating IPs against one account, or one IP spraying many accounts — **credential stuffing** — both need covering). Exponential backoff after failures.
- **Account lockout** — temporary lock after N failures. Beware: aggressive lockout becomes a *denial-of-service* vector (an attacker locks out a victim on purpose). Prefer rate-limiting + step-up challenges (CAPTCHA, MFA) over hard lockout.
- **Breached-password check** — reject passwords found in known breach corpora (the [Have I Been Pwned](https://haveibeenpwned.com/Passwords) k-anonymity API lets you check without sending the password). This is higher-value than most composition rules.
- **Drop the silly rules.** Modern guidance ([NIST SP 800-63B](https://pages.nist.gov/800-63-3/sp800-63b.html)) is: require *length* (≥8, ideally allow long passphrases up to 64+), screen against breach lists, and **stop** forcing periodic rotation and arbitrary character-class rules — they push users toward `Password1!` and predictable mutations.

```quiz
Q: Why is SHA-256 the wrong choice for hashing passwords, even though it's a strong cryptographic hash?
- [ ] SHA-256 is reversible
- [x] It's designed to be *fast*, so an attacker with a leaked hash can try billions of guesses per second; password hashing wants to be deliberately slow and memory-hard (Argon2id, scrypt, bcrypt)
- [ ] SHA-256 produces collisions easily
- [ ] SHA-256 has no salt
> A password hash is not a general-purpose hash. SHA-256's speed — a virtue for integrity checks — is exactly the liability here, because cracking a leaked hash is a guessing race and fast hashing lets the attacker guess faster. Purpose-built password hashes are intentionally slow and memory-hard (resisting GPU/ASIC cracking), tuned so one hash takes ~100–250ms. Argon2id is the 2026 default.

Q: What attack does a unique per-password salt defeat, and who should generate it?
- [ ] Brute force; you generate it manually
- [x] Rainbow tables (precomputed hash lookups) and seeing which users share a password — and the library generates and embeds the salt automatically; don't roll your own
- [ ] CSRF; the browser generates it
- [ ] Timing attacks; the database generates it
> A salt makes two identical passwords hash differently, so a precomputed rainbow table is useless and an attacker can't spot password reuse across accounts. Modern password-hash libraries generate a random salt per password and embed it (with the algorithm and parameters) in the output string, so verification re-extracts it — you store one self-contained string. Hand-rolling salt handling is a classic source of bugs.

Q: In the login path, why hash a dummy password even when the username doesn't exist?
- [ ] To log the failed attempt
- [x] To equalize response timing — if "no such user" returned instantly while a real user's check took ~150ms, attackers could enumerate valid usernames by timing; the dummy hash hides which accounts exist
- [ ] To rate-limit the attacker
- [ ] Argon2 requires it
> A timing difference between "user not found" (fast) and "user found, password checked" (slow) leaks account existence — user enumeration. Running an equivalent dummy hash on the missing-user branch makes both paths take roughly the same time, so an attacker can't distinguish valid from invalid usernames by latency. It's the same constant-time-comparison philosophy applied to the whole login flow.
```

If you remember one thing from Part 2: **store passwords as Argon2id (or bcrypt/scrypt) hashes — never a fast hash like SHA-256, never plaintext — let the library handle the per-password salt, tune the cost to ~100–250ms, equalize timing to prevent user enumeration, and defend the live endpoint with rate limiting and breached-password screening.**

---

## Part 3 — MFA & Account Lifecycle

A password is one factor. Real accounts need a second factor and a *lifecycle* — registration, verification, recovery — and the recovery flows are, paradoxically, the most attacked part of any auth system, because they're designed to bypass the password.

### Multi-Factor Authentication

The factors, classically: **something you know** (password), **something you have** (phone, security key), **something you are** (biometric). MFA requires two of different kinds, so stealing one isn't enough. The options, weakest to strongest:

- **SMS OTP — weak, but better than nothing.** Vulnerable to **SIM-swapping** (attacker ports the victim's number) and SS7 interception. NIST discourages it. Acceptable as a fallback, not as a primary second factor.
- **TOTP (Time-based One-Time Password) — the solid default.** The [RFC 6238](https://datatracker.ietf.org/doc/html/rfc6238) standard behind Google Authenticator, Authy, 1Password. Server and app share a secret at enrollment; both compute the same 6-digit code from `HMAC(secret, current_30s_window)`. No network needed, phishing-resistant only weakly (a fooled user can still type the code into a fake site).
- **Push notifications** — approve/deny on a trusted device. Good UX, but beware **MFA fatigue** attacks (spam the user with prompts until they tap "approve"). Mitigate with number-matching.
- **WebAuthn / Passkeys — the strongest, and *phishing-resistant by design*** (Part 11). The credential is cryptographically bound to your domain, so it simply won't produce a valid response on `paypa1.com`. This is the endgame; everything else is transitional.

TOTP is simple enough to show end to end:

```python
import pyotp, qrcode

# Enrollment: generate a secret, show it as a QR code for the user's authenticator app.
def enroll_totp(user) -> str:
    secret = pyotp.random_base32()
    db.users.update(user.id, totp_secret=secret, totp_enabled=False)   # not yet confirmed
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="MyApp")
    return uri                         # render as QR; user scans it into their app

# Confirm enrollment: user types a code to prove the secret synced before you ENABLE it.
def confirm_totp(user, code: str) -> bool:
    if pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):   # ±1 window for clock skew
        db.users.update(user.id, totp_enabled=True)
        return True
    return False

# Login second step:
def verify_totp(user, code: str) -> bool:
    return pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)
```

Two production essentials around MFA: **recovery codes** (one-time backup codes generated at enrollment, stored *hashed* like passwords, for when the device is lost) and **step-up authentication** (don't demand MFA for reading a profile, *do* demand it for changing a password or transferring money — re-challenge for sensitive actions even within an active session).

### The Account Lifecycle

Auth isn't just login — it's the whole arc of an identity, and each transition is a security boundary:

**Registration + email verification.** Never trust an email address until proven. Issue a signed, expiring, single-use token, email a link, and only mark the address verified when it's clicked:

```python
import secrets, hashlib, time

def start_verification(user):
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()    # store the HASH, not the token
    db.verifications.insert(user_id=user.id, token_hash=token_hash,
                            expires=time.time() + 86400, used=False)
    send_email(user.email, link=f"https://app.example.com/verify?token={raw}")

def complete_verification(raw_token: str) -> bool:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rec = db.verifications.get(token_hash=token_hash)
    if not rec or rec.used or rec.expires < time.time():
        return False
    db.verifications.mark_used(rec.id)            # single-use
    db.users.update(rec.user_id, email_verified=True)
    return True
```

Note the pattern that recurs for *every* emailed token (verification, password reset, magic links): **store the hash of the token, not the token itself, give it a short expiry, and make it single-use.** A leaked verifications/resets table should reveal nothing usable — same reasoning as password hashing.

**Password reset — the most-attacked flow in your app.** It's a deliberate authentication *bypass*, so it must be built with paranoia:

- Use the same hashed-token-via-email pattern, with a *short* expiry (15–60 min) and single use.
- **Don't leak account existence**: "If an account exists for that email, we've sent a link" — *always*, whether or not the email is registered.
- **Invalidate all existing sessions** on a successful reset (a reset often *means* the account was compromised — log the attacker out).
- **Don't auto-login** from the reset link, and require the new password to pass the same strength/breach checks as registration.
- Rate-limit reset requests (an attacker can use them to spam a victim, or as an enumeration oracle if you're careless about the response).

**Logout & session management.** "Log out" deletes the session record (trivial for stateful sessions; for tokens, see Part 6's revocation). "Log out everywhere" — invalidate *all* a user's sessions — is a feature users expect after a compromise; it's a one-liner with a session store (delete all `session:*` for the user) and a real engineering problem with stateless JWTs (Part 6). Also enforce **idle timeout** (logged out after inactivity) *and* **absolute timeout** (re-auth after N hours regardless of activity) for sensitive apps.

If you remember one thing from Part 3: **add a second factor (TOTP as the solid default, passkeys as the endgame, SMS only as fallback), and treat the account lifecycle — especially password reset — as a security-critical surface: every emailed token is hashed-at-rest, short-lived, and single-use; reset flows never leak account existence and always invalidate existing sessions.**

---

## Part 4 — JWTs in Depth

JSON Web Tokens are the workhorse credential of stateless auth, and they're misunderstood often enough to be dangerous. This part dissects what's actually in one, how verification works, and the choices that make the difference between a secure system and a forgeable one.

### Anatomy

A JWT is three Base64URL-encoded segments joined by dots — `header.payload.signature`:

```text
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9 . eyJzdWIiOiI0MiIsInJvbGUiOiJ1c2VyIiwiZXhwIjoxNzM... . <signature>
└──────────── header ────────────┘   └──────────── payload (claims) ──────────┘   └─ signature ─┘
```

- **Header** — `{"alg": "RS256", "typ": "JWT"}` — the signing algorithm and token type.
- **Payload** — the **claims**, a JSON object of statements about the subject. Standard registered claims ([RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519#section-4.1)) carry real security meaning:
  - `sub` — subject (the user ID)
  - `iss` — issuer (who minted the token)
  - `aud` — audience (who it's *for* — which API should accept it)
  - `exp` — expiration (Unix time; reject after this)
  - `iat` — issued-at; `nbf` — not-before
  - `jti` — unique token ID (used for revocation/blocklists, Part 6)
- **Signature** — the issuer signs `base64(header) + "." + base64(payload)` so any tampering is detectable.

**The single most important property to internalize: the payload is *signed, not encrypted*.** Anyone can Base64-decode and read it — paste any JWT into [jwt.io](https://jwt.io) and you'll see the claims in plaintext. So **never put secrets in a JWT payload.** The signature guarantees *integrity* (it hasn't been altered) and *authenticity* (it came from the issuer), not *confidentiality*. (If you genuinely need an encrypted token, that's JWE, a separate and rarer beast.)

### Signing: Symmetric vs Asymmetric

How the token is signed determines who can verify it — and this choice is architectural:

- **HS256 (symmetric, HMAC):** one shared secret both signs *and* verifies. Fine for a **monolith** where the same codebase mints and checks tokens. The danger: every service that needs to *verify* also holds the power to *forge*. If any holder leaks the secret, attackers mint arbitrary tokens.
- **RS256 / ES256 (asymmetric):** a **private key signs** (held only by the auth server) and a **public key verifies** (distributed freely to every API). A verifier can check tokens but *cannot forge* them. This is the standard for **distributed systems** and any third-party scenario — and it's how OIDC works (Part 5). The public keys are published at a **JWKS** ([JSON Web Key Set, RFC 7517](https://datatracker.ietf.org/doc/html/rfc7517)) endpoint that verifiers fetch and cache.

```python
import jwt   # PyJWT — pyjwt.readthedocs.io
from datetime import datetime, timedelta, timezone

# Mint (auth server, asymmetric — signs with the PRIVATE key):
def issue_access_token(user_id: int, role: str, private_key: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iss": "https://auth.example.com",
        "aud": "https://api.example.com",     # who may accept this token
        "iat": now,
        "exp": now + timedelta(minutes=15),    # short-lived (Part 6)
        "jti": secrets.token_hex(16),          # for revocation
    }
    return jwt.encode(claims, private_key, algorithm="RS256")

# Verify (any API — verifies with the PUBLIC key; CANNOT forge):
def verify_access_token(token: str, public_key: str) -> dict:
    return jwt.decode(
        token, public_key,
        algorithms=["RS256"],                  # ← hardcode the algorithm (see alg=none below)
        audience="https://api.example.com",    # ← verify aud or reject
        issuer="https://auth.example.com",     # ← verify iss or reject
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )   # raises on bad signature, expiry, wrong audience/issuer
```

### The Verification Checklist

A JWT library checks the signature, but *you* must insist on the rest. A "valid signature" alone is not a valid token. Always:

1. **Verify the signature** — obviously, with the right key.
2. **Pin the algorithm.** Pass an explicit `algorithms=[...]` allowlist. This defends against the infamous **`alg=none` attack** (a token with `{"alg":"none"}` and no signature — naive libraries once accepted it) and the **RS256→HS256 confusion attack** (an attacker re-signs with the *public* key as if it were an HMAC secret; if your verifier accepts `HS256` and you handed it the public key as the "secret," it validates). Pin to exactly the algorithm you expect.
3. **Check `exp`** — reject expired tokens (allow small clock skew, ~30–60s).
4. **Check `aud`** — reject tokens not minted for *your* API. This stops the **confused-deputy** problem: a token your auth server issued for App A must not be replayable against App B.
5. **Check `iss`** — reject tokens from issuers you don't trust.

If you remember one thing from Part 4: **a JWT is signed, not encrypted — readable by anyone, so never put secrets in it — and "the signature is valid" is not enough: pin the algorithm (kill `alg=none` and RS256→HS256 confusion), and verify `exp`, `aud`, and `iss` on every request. Use HS256 only inside a monolith; use RS256/JWKS the moment more than one service verifies.**

```quiz
Q: A JWT payload is "signed, not encrypted." What practical rule follows?
- [ ] Always encrypt the whole token
- [x] Never put secrets in the payload — anyone can Base64-decode and read the claims; the signature provides integrity and authenticity, not confidentiality
- [ ] The payload is safe because it's hashed
- [ ] Only the server can read the payload
> Paste any JWT into jwt.io and the claims are plaintext — the signature only proves the token wasn't altered and came from the issuer, not that the contents are hidden. So a JWT is fine for non-secret identity claims (user id, roles, expiry) but never for passwords, API keys, or PII you wouldn't expose. Encrypted tokens are JWE, a separate and rarer mechanism.

Q: Why must you pass an explicit `algorithms=["RS256"]` allowlist when verifying, rather than trusting the token's header?
- [ ] To speed up verification
- [x] To defeat the `alg=none` attack (an unsigned token naive libraries once accepted) and the RS256→HS256 confusion attack (an attacker re-signs with your *public* key treated as an HMAC secret); pinning the algorithm closes both
- [ ] RS256 is faster than HS256
- [ ] The header is encrypted
> Letting the token dictate its own verification algorithm is the root of two classic forgeries: `{"alg":"none"}` with no signature, and tricking an RS256 verifier into running HS256 with the *public* key as the shared secret (which the attacker also has). Hardcoding the expected algorithm means the verifier ignores the attacker-controlled header and only accepts what you intended. A valid signature under the *wrong* algorithm is still a forgery.

Q: When should you use HS256 versus RS256/ES256 for signing JWTs?
- [ ] HS256 for distributed systems; RS256 for monoliths
- [x] HS256 (one shared secret signs and verifies) only inside a monolith; RS256/ES256 (private key signs, public key verifies) the moment more than one service verifies — a verifier can check but not forge
- [ ] Always HS256; it's simpler
- [ ] They're interchangeable in all cases
> With HS256 the verify secret *is* the sign secret, so every service that checks tokens can also mint them — acceptable when one codebase does both, dangerous when distributed (any leak forges arbitrary tokens). Asymmetric signing keeps the private key on the auth server and distributes only the public key (via a JWKS endpoint), so APIs verify without the power to forge. That's the standard for distributed systems and OIDC.
```

## Part 5 — OAuth 2.0 & OpenID Connect

OAuth 2.0 and OIDC are the standards behind "Log in with Google," third-party API access, and most modern SSO. They're widely misunderstood because the two solve *different* problems and are constantly conflated — so start there.

### The Crucial Distinction

- **OAuth 2.0 is an *authorization* framework.** Its job: let a user grant a third-party app limited access to their resources *without sharing their password*. "Let this calendar app read my Google Calendar." The output is an **access token** scoped to certain permissions. OAuth says nothing, by itself, about *who the user is*.
- **OpenID Connect (OIDC) is an *authentication* layer built on top of OAuth 2.0.** It adds a standard way to learn the user's identity, via an **ID token**. "Log in with Google" is OIDC.

The historical mistake — using raw OAuth 2.0 for login by treating "I got an access token for their profile" as "they're authenticated" — leads to real vulnerabilities (the access token says nothing verifiable about *who* logged in or *which app* it was issued to). **If you want login, use OIDC, not bare OAuth.**

### The Four Roles

Memorize these; every flow is a conversation between them:

- **Resource Owner** — the user who owns the data.
- **Client** — the application requesting access (your web/mobile app).
- **Authorization Server** — verifies identity and issues tokens (Google, Auth0, Keycloak, Okta, Entra ID).
- **Resource Server** — the API holding the data, which accepts and validates the access tokens.

### The Authorization Code Flow with PKCE

This is *the* flow for essentially all modern apps — SPAs, mobile, and traditional web. It replaced the old Implicit Flow (now deprecated — it leaked tokens in URLs). **PKCE** ("pixie," [Proof Key for Code Exchange, RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)) is the addition that makes it safe for public clients that can't keep a secret.

```text
1. Client generates a random code_verifier, and code_challenge = SHA256(code_verifier).
2. Client redirects user to the Authorization Server, sending the code_challenge.
        ──►  https://auth.example.com/authorize?
                response_type=code&client_id=...&redirect_uri=...&
                scope=openid profile email&state=<csrf>&
                code_challenge=<hash>&code_challenge_method=S256
3. User logs in and consents.
4. Auth Server redirects back to the Client with a one-time authorization_code.
        ◄──  https://app.example.com/callback?code=<code>&state=<csrf>
5. Client makes a BACK-CHANNEL POST to the token endpoint, sending the code
   AND the original plaintext code_verifier.
        ──►  POST /token  { code, code_verifier, client_id, redirect_uri }
6. Auth Server computes SHA256(code_verifier); if it matches the code_challenge
   from step 2, it returns the tokens.
        ◄──  { access_token, id_token, refresh_token, expires_in }
```

**Why PKCE matters:** if an attacker intercepts the `authorization_code` in step 4 (e.g., a malicious app hijacking a mobile custom-URL-scheme redirect), they still can't exchange it for tokens in step 5 — they don't have the secret `code_verifier`, and the code alone is useless. PKCE binds the code to the client that started the flow. (The separate `state` parameter is a CSRF token for the redirect — always verify it on return.)

```python
import secrets, hashlib, base64

def start_oauth():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)               # CSRF protection for the redirect
    session["code_verifier"] = code_verifier        # stash for step 5
    session["oauth_state"] = state
    return redirect(
        f"{AUTH_SERVER}/authorize?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&scope=openid+profile+email"
        f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
    )

def oauth_callback(request):
    if request.args["state"] != session["oauth_state"]:   # verify CSRF state FIRST
        abort(400, "state mismatch")
    resp = httpx.post(f"{AUTH_SERVER}/token", data={
        "grant_type": "authorization_code",
        "code": request.args["code"],
        "code_verifier": session["code_verifier"],         # the PKCE proof
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    })
    tokens = resp.json()    # { access_token, id_token, refresh_token, ... }
    claims = verify_id_token(tokens["id_token"])           # OIDC: who logged in (Part 4)
    ...
```

### Access Token vs ID Token — Don't Mix Them Up

The two tokens have *different audiences and different jobs*, and confusing them is a classic bug:

| | **Access Token** (OAuth) | **ID Token** (OIDC) |
|---|---|---|
| Answers | *What may the bearer do?* (authorization) | *Who logged in?* (authentication) |
| For | the **Resource Server** (the API) | the **Client** application |
| Format | opaque string *or* JWT | **always** a JWT |
| Client should inspect it? | **No** — just forward it to the API | **Yes** — that's its whole purpose |
| Sent to an API as proof? | **Yes** | **Never** |

The two rules that fall out: **the client must not parse the access token** (treat it as opaque; only the API it's for should validate it), and **the ID token must never be sent to an API as an authorization credential** (it's proof of *login to the client*, not permission to *call the API*). Violating either is a recurring source of broken-auth bugs.

### Other Grant Types

The auth-code+PKCE flow covers user-facing apps. Two others you'll meet:

- **Client Credentials** — for **machine-to-machine** (no user involved): a service authenticates with its own client ID + secret to get an access token. This is the OAuth path for service-to-service auth (Part 9).
- **Device Authorization** ([RFC 8628](https://datatracker.ietf.org/doc/html/rfc8628)) — for input-constrained devices (a TV, a CLI): the device shows a code, you approve it on your phone. (You've done this with `gh auth login` or a streaming-box login.)

The **deprecated** ones to avoid: **Implicit** (tokens in the URL fragment — replaced by auth-code+PKCE) and **Resource Owner Password Credentials** (the app collects the user's password directly — defeats the entire point of OAuth; never use it).

```quiz
Q: What's the difference between OAuth 2.0 and OpenID Connect, and why does "log in with Google" need OIDC?
- [ ] They're the same standard
- [x] OAuth 2.0 *authorizes* (issues access tokens for resources, saying nothing verifiable about identity); OIDC adds an *authentication* layer with an ID token — using a bare OAuth access token as proof of login is a real vulnerability
- [ ] OAuth is newer and replaces OIDC
- [ ] OIDC is only for enterprises
> OAuth answers "what may this app access?" — an access token grants scoped permission but doesn't verifiably identify the user or which app it was issued to. OIDC layers identity on top with an ID token. The classic mistake is treating "I got an access token for their profile" as "they're authenticated," which an attacker can exploit. For login, use OIDC; for delegated API access, use OAuth.

Q: In the auth-code flow, how does PKCE protect a public client even if an attacker intercepts the authorization code?
- [ ] It encrypts the code
- [x] The client sends only `code_challenge = SHA256(code_verifier)` up front, then must present the secret `code_verifier` to redeem the code — an intercepted code is useless without the verifier, binding the code to the client that started the flow
- [ ] It shortens the code's lifetime to one second
- [ ] It signs the code with the client secret
> PKCE binds the authorization code to the originating client via a one-way challenge: the auth server only releases tokens to whoever can produce the `code_verifier` whose hash it saw earlier. A malicious app hijacking a mobile redirect grabs the code but not the verifier, so the back-channel token exchange fails. This is why public clients (SPAs, mobile) that can't keep a secret can still use the flow safely. The separate `state` parameter handles CSRF on the redirect.

Q: Why must the client never send an OIDC ID token to an API as an authorization credential?
- [ ] ID tokens are encrypted
- [x] The ID token proves *login to the client* and is meant for the client; the access token is what authorizes API calls. Sending the ID token to an API (or having the client parse the access token) confuses their distinct audiences and jobs
- [ ] ID tokens expire too quickly
- [ ] APIs can't read JWTs
> The two tokens have different audiences: the ID token answers "who logged in?" for the client, the access token answers "what may the bearer do?" for the resource server. The client should treat the access token as opaque (only forward it) and never present the ID token as API authorization — it carries no statement about API permissions. Mixing them is a recurring broken-auth bug.
```

If you remember one thing from Part 5: **OAuth 2.0 authorizes (access tokens for APIs); OIDC authenticates (ID tokens for your app) — use OIDC for login, not bare OAuth. The auth-code flow with PKCE is the one flow for user-facing apps; keep the access token opaque to the client and never send the ID token to an API.**

---

## Part 6 — Token Lifecycle & Revocation

Tokens are credentials, and a stolen credential is a breach. Their power comes from being self-validating; their danger is the same thing — a signed token is valid until it expires, whether or not you still want it to be. This part is about managing that tension: short lifetimes, refresh, rotation, and the genuinely hard problem of revocation.

### Short-Lived Access + Long-Lived Refresh

The standard pattern resolves the staleness/revocation problem of stateless tokens (Part 1) by splitting the credential in two:

- **Access token — short-lived (5–15 min).** Carried on every API request, verified by signature alone (fast, stateless). Its short life is the whole security argument: a stolen access token is useless within minutes, and a role change propagates within minutes.
- **Refresh token — long-lived (days–weeks), but revocable.** Never sent to resource servers — only to the auth server, to mint a *new* access token when the old one expires. It's stored server-side (or otherwise tracked), so it *can* be revoked. Treated as highly sensitive: `HttpOnly` cookie for web, Keychain/Keystore for mobile.

So you get the best of both models from Part 1: fast stateless verification on the hot path (access token), and real revocation on the cold path (refresh token).

### Refresh Token Rotation + Reuse Detection

The critical hardening for public clients (SPAs, mobile) where the refresh token can't be perfectly secured: **rotate on every use, and treat reuse as a breach.**

```text
1. Client presents refresh token RT1 to get a new access token.
2. Auth server issues a new access token AND a new refresh token RT2,
   then invalidates RT1.
3. Next refresh uses RT2 → issues RT3, invalidates RT2.  (the chain rotates)

   ── Reuse detection ──
4. If RT1 (already invalidated) is EVER presented again, the server concludes
   the token was stolen (either the attacker or the legitimate client is
   replaying an old token) and REVOKES THE ENTIRE TOKEN FAMILY — forcing a
   full re-login. The thief and the victim both get locked out; the victim
   logs back in, the thief can't.
```

This turns a stolen-and-replayed refresh token from a silent persistent compromise into a detectable, self-healing event. It's the single most valuable refresh-token feature; any serious auth server (and OAuth 2.1, per the [OAuth Security BCP, RFC 9700](https://datatracker.ietf.org/doc/html/rfc9700)) builds it in.

### Revoking a Stateless Access Token — The Hard Problem

Here's the question that exposes the cost of statelessness: *a user is banned, but they hold a valid, unexpired 15-minute JWT — how do you stop it?* By design, you can't *just* invalidate it; the API validates by signature and never asks a database. Your options, in increasing strength and cost:

1. **Wait it out.** Accept the ≤15-minute window. For many apps this is genuinely fine — that's *why* you keep access tokens short. The simplest correct answer.
2. **Tiered checks.** Validate by signature for cheap reads (`GET /profile`), but do a live DB/cache check for sensitive actions (`POST /transfer`). You pay the statefulness cost only where it matters.
3. **A revocation blocklist by `jti`.** Maintain a (small, fast) set of revoked token IDs — keyed by the `jti` claim (Part 4) — in Redis, checked on each request. It re-introduces a lookup, but the set is tiny (only *revoked, not-yet-expired* tokens) and you can expire entries at the token's own `exp`. This is the common production middle ground.
4. **Push-based invalidation (CAE).** The API subscribes to an event stream from the identity provider; when a user is revoked, it receives an invalidation event and updates a local blocklist. This is essentially the [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md)'s cache-invalidation problem — eventual consistency with a propagation delay you must bound.

Recognize the shape: **revocation is fundamentally a distributed-cache-invalidation problem.** A JWT is a cached copy of an authorization decision; revoking it means invalidating that cache everywhere it's trusted, which is exactly as hard as cache invalidation always is. Stateful sessions sidestep this entirely (delete the record) — which is, again, why they're the better default for apps that don't need statelessness.

```quiz
Q: Why split the credential into a short-lived access token and a long-lived refresh token?
- [ ] To reduce token size
- [x] The access token (5–15 min) gives fast stateless verification on every request and limits the damage of theft; the long-lived refresh token is revocable and only sent to the auth server — so you get stateless speed on the hot path and real revocation on the cold path
- [ ] Refresh tokens are faster to verify
- [ ] Access tokens can't be stolen
> This resolves the staleness/revocation weakness of pure JWTs. The access token is verified by signature alone (no lookup) but is useless within minutes if stolen and reflects role changes quickly; the refresh token lives server-side, is sent only to the auth server to mint new access tokens, and can be revoked. It's the hybrid that combines both Part 1 models.

Q: What does refresh-token rotation with reuse detection accomplish?
- [ ] It makes tokens never expire
- [x] Each refresh issues a new token and invalidates the old one; if an already-invalidated token is ever presented again, the server treats it as theft and revokes the entire token family — turning a silent stolen-token compromise into a detectable, self-healing event
- [ ] It rotates the signing key
- [ ] It encrypts the refresh token
> Rotation chains the refresh tokens (RT1→RT2→RT3), so a stolen-and-replayed old token surfaces as the impossible event of reusing an invalidated one. The server then locks out the whole family, forcing re-login: the victim logs back in, the thief is shut out. It's the single most valuable refresh-token feature and is baked into OAuth 2.1, especially for public clients that can't perfectly secure the token.

Q: A user is banned but holds a valid, unexpired 15-minute access token. Why is stopping it "fundamentally a cache-invalidation problem"?
- [ ] The token is stored in a CDN cache
- [x] A JWT is a cached copy of an authorization decision verified by signature with no DB lookup, so revoking it means invalidating that cached decision everywhere it's trusted — solved by waiting it out, a `jti` blocklist, tiered live checks, or push-based invalidation
- [ ] Caches are unrelated to tokens
- [ ] You just delete the token from the database
> The whole point of a stateless token is that the API trusts the signature without asking anyone, which is exactly why you can't un-issue it — the authorization decision is cached in the token itself, distributed to every verifier. Options trade cost for immediacy: accept the short window, check a small `jti` revocation set in Redis, do live checks only on sensitive actions, or push invalidation events. Stateful sessions sidestep this by just deleting the record.
```

If you remember one thing from Part 6: **pair a short-lived (5–15 min) stateless access token with a long-lived, revocable refresh token that rotates on every use and revokes the whole family on reuse — and accept that revoking an unexpired access token is a cache-invalidation problem, solved by keeping it short, checking a `jti` blocklist, or doing live checks on sensitive actions.**

---

## Part 7 — Enterprise SSO: SAML & SCIM

The moment you sell software to a company, they will demand **Single Sign-On** — their employees log in through the company's identity provider (Okta, Microsoft Entra ID, Google Workspace), not a password in your app. "SSO" is frequently a hard requirement in enterprise procurement, so it's worth understanding even though the protocols are crusty.

### SAML 2.0

The long-standing enterprise SSO standard ([OASIS SAML 2.0](https://docs.oasis-open.org/security/saml/v2.0/saml-core-2.0-os.pdf)). It's XML-based and uses XML Digital Signatures — which are *notoriously* complex and a historical source of signature-bypass vulnerabilities, so **use a vetted library; never hand-parse SAML.**

```text
SP-Initiated flow (your app = Service Provider, the customer's Okta = Identity Provider):

1. User hits your app (the SP) and needs to log in.
2. Your app builds a SAML AuthnRequest (XML), encodes it, and redirects the
   user's browser to the customer's IdP (Okta).
3. User authenticates at Okta (the IdP).
4. Okta POSTs a signed SAML Response (XML with Assertions about the user) to
   your app's ACS (Assertion Consumer Service) URL.
5. Your app verifies the XML signature against the IdP's public cert, reads the
   assertions (email, name, groups), and logs the user in.
```

The vocabulary you'll configure:

- **Entity ID** — a unique identifier for the SP or IdP.
- **ACS URL** — the endpoint on *your* app that receives the SAML Response.
- **Metadata XML** — a config document exchanged between SP and IdP carrying public certs and endpoint URLs (it automates setup).
- **Assertions** — the signed statements about the user (identity + attributes/groups).

### OIDC for SSO — The Modern Path

Increasingly, enterprises support **OIDC** (Part 5) for SSO instead of SAML, and you should prefer it for new integrations: JSON instead of XML, standard OAuth flows you already implement, far simpler and less error-prone. The mechanics are exactly the OIDC of Part 5, with the enterprise IdP as the authorization server. Offer both if you sell broadly (some large customers are still SAML-only), but reach for OIDC first.

### SCIM — The Provisioning Half Everyone Forgets

SSO handles **authentication** — but it doesn't answer: how does your app know a user *exists* before they first log in? How is access *revoked the instant* someone is fired? That's **provisioning**, and the standard is **SCIM** ([System for Cross-domain Identity Management, RFC 7644](https://datatracker.ietf.org/doc/html/rfc7644)) — a standardized REST API for syncing users and groups:

- The IdP (Okta) is the **client**; your app implements the **SCIM server** (`POST /scim/v2/Users`, `PATCH /scim/v2/Users/{id}`, `DELETE`, plus `/Groups`).
- HR adds an employee in Okta → Okta calls your SCIM API to **create** the account (often before the user ever logs in).
- HR deactivates them → Okta calls your API to **deprovision** — which is the security-critical half: **instant offboarding.** Without SCIM, a fired employee's access lingers until tokens/sessions expire, which is exactly the gap attackers and auditors care about.

If you remember one thing from Part 7: **enterprise SSO means delegating authentication to the customer's IdP — prefer OIDC over the crusty XML of SAML for new integrations (but support SAML where required, with a vetted library) — and don't forget SCIM, the provisioning API that creates accounts on hire and, critically, revokes them instantly on termination.**

---

## Part 8 — Authorization Models (RBAC, ABAC, ReBAC)

Authentication is settled by Part 7; the rest of the guide is authorization — *what an authenticated principal may do*. There are three dominant models, increasing in power and complexity, and choosing the right one for your app's shape is one of the higher-leverage design decisions you'll make.

### RBAC: Role-Based Access Control

Users get **roles**; roles carry **permissions**. Alice is an `Admin`; `Admin` has `delete_user`.

```python
ROLE_PERMISSIONS = {
    "admin":  {"user:read", "user:write", "user:delete", "billing:manage"},
    "editor": {"doc:read", "doc:write"},
    "viewer": {"doc:read"},
}
def can(user, permission: str) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(r, set()) for r in user.roles)
```

- **Pros:** simple, universally understood, easy to audit ("what can an editor do?" is a lookup).
- **Cons:** **role explosion** — real orgs grow roles like `US_East_Billing_Viewer_ReadOnly_Temp` as combinations multiply. And it's **coarse**: RBAC says "editors can edit documents," but struggles with "Alice can edit *document 1* but only view *document 2*" — per-resource access. When you find yourself encoding resource IDs into role names, you've outgrown RBAC.

RBAC is the right default for most apps. Reach further only when per-resource or relationship-driven access becomes central.

### ABAC: Attribute-Based Access Control

Decisions are computed from **attributes** of the user, the resource, and the environment, evaluated by a policy at request time:

```text
Allow  action=edit
  if   user.department == resource.department
  and  user.clearance >= resource.classification
  and  request.time.hour < 18
```

- **Pros:** extremely flexible and granular; expresses context-dependent rules RBAC can't.
- **Cons:** **hard to audit.** Because decisions are computed at runtime from dynamic state, answering "*list every document Alice can access*" is difficult — you'd have to evaluate the policy against every resource. **AWS IAM is the canonical ABAC system** (policies over principals, resources, conditions), and anyone who's debugged an IAM `Deny` knows both the power and the pain.

ABAC is often implemented with a policy engine — **[Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/)** with its Rego language, or **[Cedar](https://www.cedarpolicy.com/)** (AWS) — that you query for a decision, keeping policy out of your business logic (more in Part 10).

### ReBAC: Relationship-Based Access Control (Zanzibar)

The modern model for complex, hierarchical, multi-tenant apps — and the one behind Google Docs/Drive. Access is determined by **traversing a graph of relationships**, formalized in Google's **[Zanzibar](https://research.google/pubs/pub48190/)** paper and implemented by open-source **[SpiceDB](https://authzed.com/docs)** and **[OpenFGA](https://openfga.dev/docs/fga)**.

```text
Relationship tuples:  Object#Relation@Subject
    document:1   #owner   @user:alice
    folder:eng   #viewer  @group:engineering#member
    document:1   #parent  @folder:eng

Policy (schema):  "you may VIEW a document if you are its owner,
                   OR a viewer of its parent folder (transitively)."

Question: "can user:alice view document:1?" → traverse the graph → yes/no.
```

- **Pros:** naturally models ownership, sharing, inheritance, and groups; and it **solves the "list all documents Alice can view" problem** because the whole permission model is a queryable graph (traverse from Alice). This reverse-index capability is exactly what ABAC struggles with.
- **Cons:** new infrastructure (a dedicated authz service holding the relationship graph), and a learning curve. But it's the gold standard for Google-Docs-style sharing and complex B2B hierarchies.

### Multi-Tenant Authorization

In B2B SaaS, the same human is `admin` in Tenant A and `viewer` in Tenant B — so **roles are never global, they're per-tenant.** The rules that prevent cross-tenant data leaks (the worst class of SaaS bug):


---

## Part 9 — Service-to-Service Auth

Everything so far assumed a human at the other end. But in a microservice or distributed system, most authentication is **machine-to-machine** — service A calling service B, a job calling an API, a pod calling the database. There's no password, no browser, no consent screen. This part covers how services prove identity to each other, and it connects directly to the [Kubernetes Security guide](k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md) and [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md).

### The Spectrum, Weakest to Strongest

- **Shared API keys / static secrets.** The simplest: service B issues service A a long random key; A sends it on every request. Easy, but the key is a long-lived bearer credential — if it leaks (a logged header, a committed `.env`, a breached service), the attacker is indistinguishable from A until you rotate. Acceptable for low-stakes internal calls *if* you rotate regularly and scope tightly; avoid as your primary mechanism at scale.
- **OAuth Client Credentials grant** (Part 5). Service A authenticates to an auth server with its client ID/secret and receives a *short-lived* access token for service B. Better than static keys because the token expires (bounded blast radius) and is centrally issued and auditable. The standard for M2M when you already run an OAuth server.
- **mTLS (mutual TLS).** Both sides present X.509 certificates during the TLS handshake; each verifies the other's cert against a trusted CA. Identity *is* the certificate, authentication happens as part of establishing the connection, and traffic is encrypted in transit by definition. Strong — but you now own a **certificate lifecycle** (issuance, distribution, rotation, revocation), which is real operational weight, and exactly what service meshes automate.
- **Workload identity (SPIFFE/SPIRE).** The modern, platform-native answer: a workload's identity is derived from *what and where it is* (its Kubernetes ServiceAccount, namespace, node) rather than a secret it carries. **[SPIFFE](https://spiffe.io/docs/latest/spiffe-about/overview/)** defines a universal identity format (the SVID — SPIFFE Verifiable Identity Document, an X.509 cert or JWT); **[SPIRE](https://spiffe.io/docs/latest/spire-about/)** is the runtime that attests workloads and issues short-lived SVIDs automatically. No long-lived secret to leak, identity is cryptographically attested, and rotation is continuous and invisible.

### How the Mesh Makes This Disappear

The reason most teams don't hand-roll mTLS is the **service mesh** (Istio, Linkerd, Cilium — see the [Docker & Kubernetes Networking guide](k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md)). The mesh injects a sidecar proxy beside each service and **automatically establishes mTLS between every pair of sidecars** — issuing certs, rotating them, and enforcing identity-based policy ("service `frontend` may call `backend`, but not `payments`") — all without the application code knowing. Your service makes a plain HTTP call to `localhost`; the sidecar wraps it in authenticated, encrypted mTLS. This is the cleanest way to get strong service identity at scale: it's infrastructure, not application code.

### Cloud Workload Identity

In a managed cloud, the equivalent is **workload identity federation**: instead of stuffing AWS keys or a GCP service-account JSON into your pod (a long-lived secret to leak), the workload's *platform identity* (its Kubernetes ServiceAccount, bound via OIDC to a cloud IAM role) is exchanged for short-lived cloud credentials on demand. AWS IRSA / EKS Pod Identity, GKE Workload Identity, and Azure Workload Identity all implement this. The principle is identical to SPIFFE: **derive identity from the platform, mint short-lived credentials, store no long-lived secret.** It's also how CI gets cloud access without stored keys — the OIDC-to-cloud pattern in the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md).

If you remember one thing from Part 9: **machine-to-machine auth should avoid long-lived static secrets — prefer short-lived tokens (OAuth client credentials), mTLS for mutual cryptographic identity, and workload identity (SPIFFE/SPIRE or cloud workload-identity federation) where the platform attests *what* a workload is so there's no secret to leak — and let a service mesh automate the mTLS so it never touches your application code.**

---

## Part 10 — Application Architecture & Patterns

How do all these pieces assemble in a real system? This part is the architectural glue — where tokens get validated, how the edge talks to internal services, and the patterns that recur in every production deployment.

### Where to Validate: The API Gateway Pattern

In a microservice architecture, you do **not** want every internal service independently fetching JWKS, validating OAuth tokens, and handling external-identity nuance — that's duplicated, error-prone, and couples every service to your IdP. Instead, **terminate external auth at the edge** (an API gateway), and pass a simpler, trusted identity inward.

**The [Phantom Token pattern](https://curity.io/resources/learn/phantom-token-pattern/)** is the clean version of this (token introspection itself is [RFC 7662](https://datatracker.ietf.org/doc/html/rfc7662)):

```text
1. The browser/client holds an OPAQUE access token (a random string — reveals nothing,
   can't be inspected, easy to revoke).
2. Client -> API Gateway with the opaque token.
3. The Gateway introspects it (a cached lookup or RFC 7662 introspection call to the auth
   server) and exchanges it for a rich, signed JWT (user id, roles, tenant context).
4. The Gateway forwards the request inward, attaching the JWT.
5. Internal services just verify the JWT signature (fast, cached public key) and trust the claims.
```

The external world holds revocable opaque tokens; the internal world enjoys fast stateless JWT verification. The gateway is the single place that knows about the IdP, JWKS, introspection, and revocation — internal services stay simple. (It's also where you'd enforce coarse authz, rate limiting, and tenant routing.)

### The Trust Boundary

The principle underneath that pattern: **establish a trust boundary at the edge, and define what "trusted" means inside it.** Inside the boundary, services trust the gateway-minted JWT and don't re-authenticate the *user* on every hop — but in a zero-trust deployment they still authenticate *each other* (Part 9's mTLS) so a compromised internal service can't impersonate others. "Authenticate the user once at the edge; authenticate services on every hop" is the modern shape.

### The WebSockets Problem

A specific, common snag also covered from the protocol side in the [WebSockets guide](WEBSOCKETS_STUDY_GUIDE.md): the browser `WebSocket` API **cannot set custom headers** on the handshake, so you can't send `Authorization: Bearer <token>` the way you do for HTTP. Three options, in order of preference:

1. **Cookie-based** — if the WS endpoint shares the domain, the browser sends the auth cookie automatically on the handshake (the cleanest path, and another point for cookies over `localStorage`).
2. **Ticket pattern** — the client makes a normal authenticated `POST /ws-ticket`, gets a short-lived (~10s) single-use ticket, and connects to `wss://.../stream?ticket=...`. The server consumes the ticket to establish the session. Safe because the ticket is ephemeral and single-use.
3. **First-message auth** — open the socket unauthenticated, require `{"type":"auth","token":"..."}` as the first frame within a few seconds, and drop the connection otherwise.

**Avoid** putting a long-lived token directly in the URL query string (`?token=<jwt>`) — URLs land in access logs, proxy logs, and browser history, leaking the credential. The ticket pattern exists precisely to make the query-string approach safe by making the value worthless after one use.

If you remember one thing from Part 10: **terminate external auth at an API gateway (the Phantom Token pattern — opaque revocable tokens outside, fast signed JWTs inside) so internal services stay simple; define a clear trust boundary (authenticate the user once at the edge, services on every hop); and for WebSockets, use cookies or the single-use ticket pattern, never a long-lived token in the URL.**

---

## Part 11 — Passkeys, Pitfalls & a Walkthrough

The closing part: where authentication is heading (passwordless), the mistakes that recur across every system in this guide, and an end-to-end assembly of the pieces.

### Passkeys & WebAuthn — The Endgame

The future of authentication is **passwordless**, built on the **FIDO2 / WebAuthn** standards, and **passkeys** are its consumer form. They replace the shared secret (a password the server stores and an attacker can steal) with **public-key cryptography** where the server only ever holds a *public* key — useless to a thief.

```text
Registration:
1. The user's device generates a public/private key pair, scoped to YOUR domain.
2. The private key never leaves the device's secure hardware (Secure Enclave / TPM),
   or is synced encrypted via the platform keychain (iCloud Keychain, Google Password Manager).
3. The PUBLIC key is sent to your server and stored against the account.

Authentication:
1. Server sends a random challenge.
2. The device prompts for a local gesture — FaceID, TouchID, PIN — to unlock the private key.
3. The device signs the challenge with the private key.
4. Server verifies the signature with the stored public key.  -> logged in.
```

Why this is the endgame, not just an incremental improvement:

- **Phishing-resistant *by construction*.** The credential is cryptographically bound to your origin (the registrable domain). On `paypa1.com`, the browser simply won't offer or produce a valid assertion — the wrong-domain check is in the protocol, not in the user's vigilance. This defeats the entire category of credential phishing that MFA only partially addresses.
- **Nothing shared to steal.** The server stores public keys. A database breach yields nothing an attacker can authenticate with — contrast Part 2, where even hashed passwords are crackable given time.
- **No password reset to attack.** The most-exploited flow (Part 3) largely disappears; account recovery shifts to device/platform recovery and backup keys.
- **Excellent UX.** A biometric tap — no password to remember or type.

The practical 2026 posture: **offer passkeys as a first-class option** (browsers and platforms now broadly support them), keep a fallback (TOTP, or password+MFA) for users and devices that aren't ready, and treat passkeys as the direction the whole industry is converging on. A passkey is simultaneously a *factor* (something you have + something you are) and a complete login mechanism.

### Common Pitfalls

The recurring mistakes, each tied back to where this guide covered it:

1. **`alg=none` / algorithm confusion** (Part 4). Always pin the expected algorithm in JWT verification; never let the token's header choose. Defends against unsigned tokens and RS256->HS256 confusion.
2. **Confused deputy — unchecked `aud`** (Part 4). A token minted for App A replayed against App B. Always verify the audience claim is *your* service.
3. **Fast hashes for passwords** (Part 2). SHA-256/MD5 for passwords is a breach waiting to happen. Argon2id/bcrypt/scrypt only.
4. **Secrets in JWTs** (Part 4). The payload is signed, not encrypted — readable by anyone. Never put anything sensitive in it.
5. **Token in the URL** (Parts 10, 11). Query strings leak to logs, history, and the `Referer` header sent to third-party resources. Use headers, cookies, or single-use tickets.
6. **User enumeration via timing or messages** (Parts 2, 3). "No such user" vs "wrong password" — same generic error, same timing. Same for "email not found" on password reset.
7. **Password reset that doesn't invalidate sessions** (Part 3). A reset often *means* compromise — log everyone out.
8. **Cross-tenant data access / IDOR** (Part 8). Always scope queries by `tenant_id` *and* owner, never trust a resource ID alone.
9. **Long-lived, unrotated, broadly-scoped secrets** (Parts 6, 9). Short-lived and rotated beats long-lived and static, every time.
10. **`localStorage` for tokens with a weak CSP** (Part 1). Prefer `HttpOnly; Secure; SameSite` cookies; if you must use the header pattern, lock down XSS hard.

### End-to-End Walkthrough: A Multi-Tenant B2B SaaS

Tying the guide together — the auth architecture of a realistic product, each decision pointing back to its Part:

```text
SIGN-UP & LOGIN (Parts 1-4)
  - Consumers: email + password (Argon2id, breach-checked) -> email verification (hashed,
    single-use token) -> TOTP enrollment offered, passkeys offered as the preferred option.
  - Credential lives in an HttpOnly; Secure; SameSite=Lax cookie (client & app share a domain).
  - Sensitive actions (change password, billing) trigger step-up re-authentication.

ENTERPRISE CUSTOMERS (Part 7)
  - SSO via OIDC (SAML offered for those who require it) -> users log in through their own Okta.
  - SCIM provisions accounts on hire and -- critically -- deprovisions instantly on termination.

THE TOKEN ARCHITECTURE (Parts 5, 6, 10)
  - Auth handled by an OIDC provider (Keycloak/Auth0); Authorization Code + PKCE flow.
  - API gateway terminates external auth: opaque token outside -> introspect -> rich signed
    JWT (sub, per-tenant role, tenant_id) inside.  Access token 15 min; refresh token rotated.
  - Internal microservices verify the JWT signature via cached JWKS -- fast, stateless.

AUTHORIZATION (Part 8)
  - RBAC per tenant for coarse roles (admin/editor/viewer), resolved at the gateway from tenant_id.
  - ReBAC (OpenFGA) for the document-sharing feature, where "who can see this?" is a graph.
  - Every data query scoped:  WHERE id = ? AND tenant_id = ?  -- enforced in middleware.

SERVICE-TO-SERVICE (Part 9)
  - A service mesh provides automatic mTLS between all internal services -- no app-level secrets.
  - Cloud access via workload identity federation -- no stored cloud keys in any pod.

REVOCATION & LIFECYCLE (Parts 3, 6)
  - "Log out everywhere" deletes all refresh tokens for the user.
  - Refresh-token reuse -> revoke the whole family (breach signal).
  - Password reset / SCIM-deprovision -> immediately invalidate all sessions.
```

Notice that **every layer is defense-in-depth**: a stolen access token dies in 15 minutes; a stolen refresh token is detected on reuse; a phished password is stopped by MFA (or made impossible by passkeys); a compromised internal service can't impersonate others (mTLS); a leaked DB yields only public keys and uncrackable hashes. No single failure is catastrophic — which is the entire point of an auth architecture.

If you remember one thing from Part 11: **passkeys/WebAuthn are the phishing-resistant, nothing-to-steal endgame — adopt them as a first-class option now — and a real auth system is defense-in-depth: short-lived tokens, MFA, per-tenant scoping, mTLS between services, and the discipline that every one of the ten pitfalls above is closed.**

---

## Where to Go Next

- **Read the [OAuth 2.1 draft](https://oauth.net/2.1/) and the [OAuth Security BCP (RFC 9700)](https://datatracker.ietf.org/doc/html/rfc9700)** — together they are the consolidated, current statement of how OAuth should be done, with every deprecated flow and required mitigation in one place. [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html) is the companion for the identity layer.
- **Work through the OWASP cheat sheets** — [Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), and [Forgot Password](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html) — they are the practitioner's checklists this guide compresses.
- **Read the [Zanzibar paper](https://research.google/pubs/pub48190/)** while Part 8 is fresh — it's short, readable, and the [OpenFGA docs](https://openfga.dev/docs/fga) let you play with the model in an afternoon.
- **Build one flow end to end.** Stand up [Keycloak](https://www.keycloak.org/documentation) locally, implement the auth-code+PKCE flow against it by hand (no SDK), verify the ID token yourself with pinned algorithms, then add refresh rotation. Nothing exposes the gap between "I understand OAuth" and "I implemented it correctly" faster.
- **Adjacent guides in this repo:** [Cryptography Fundamentals](CRYPTO_FUNDAMENTALS.md) (the primitives under every signature here), [Kubernetes Security](k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md) (cluster identity), [Enterprise APIs](ENTERPRISE_API_STUDY_GUIDE.md) (where these tokens get used), and [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) (the browser-header problem in depth).

That's the guide. From here the highest-leverage next step is to audit one real system against Part 11's pitfall list and walkthrough: confirm passwords are Argon2id, JWT verification pins the algorithm and checks `aud`, password reset invalidates sessions, every query is tenant-scoped, and no long-lived secrets sit in environment variables. Auth is the domain where "I understand it" and "I implemented it correctly" are different skills — and the gap between them is exactly where the breaches are. For the cryptographic primitives underneath all of this, see the [Cryptography Fundamentals guide](CRYPTO_FUNDAMENTALS.md); for cluster identity, the [Kubernetes Security guide](k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md); for protocol-level WebSocket and TLS detail, the [WebSockets](WEBSOCKETS_STUDY_GUIDE.md) and [Networking Fundamentals](NETWORKING_FUNDAMENTALS.md) guides.

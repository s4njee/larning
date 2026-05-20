# Cryptography Fundamentals Study Guide

A depth-first guide to applied cryptography for working engineers. The goal is not to make you a cryptographer — it is to make you fluent enough to read a spec, choose the right primitive, use a library correctly, and recognize when something is dangerously wrong. Each phase builds on the previous. Phases 11–13 are applied: building auth in Node.js and Go, and recipes for the common applied tasks (webhook signing, envelope encryption, file encryption with `age`).

> **Do not roll your own crypto.** This guide exists so you can pick the right primitive and the right library — not write your own AES. The single most reliable security move you can make is to use a high-level, audited library and to keep its defaults.

---

## Phase 1: Foundations

### 1.1 What Cryptography Buys You

There are four properties to keep straight. Every system you build is a composition of these.

- **Confidentiality** — only the intended recipient can read the message. Provided by *encryption*.
- **Integrity** — the message was not altered in transit. Provided by *MACs* and *hashes-in-context*.
- **Authenticity** — the message came from who you think it did. Provided by *MACs* (shared key) or *digital signatures* (public key).
- **Non-repudiation** — the sender cannot plausibly deny they sent it. Provided by *digital signatures* only — MACs do not give you this, because both parties share the key.

A frequent confusion: encryption alone provides confidentiality but **not** integrity. An attacker can flip bits in CBC or CTR ciphertext to flip bits in the plaintext. This is why modern symmetric crypto uses *AEAD* (authenticated encryption with associated data), which bundles confidentiality + integrity into a single primitive. Use AEAD. Always.

### 1.2 Kerckhoffs's Principle

> A cryptosystem should be secure even if everything about the system, except the key, is public knowledge.

Security through obscurity does not count. If your scheme breaks when an attacker reads your code, your scheme is broken. This is why we use well-known, peer-reviewed algorithms (AES, ChaCha20, SHA-256, Ed25519) instead of bespoke ones.

### 1.3 Attacker Models

Cryptographic security is always defined against an adversary with specified powers. The two most common goals you'll encounter:

- **IND-CPA** (indistinguishability under chosen-plaintext attack) — the attacker can request encryptions of arbitrary plaintexts. They cannot tell apart two ciphertexts of their choice. *The minimum bar for encryption.* Pure CTR-mode AES satisfies this but provides no integrity.
- **IND-CCA2** (indistinguishability under adaptive chosen-ciphertext attack) — stronger: the attacker can also request *decryptions* of arbitrary ciphertexts (except the challenge). *This is what you want.* AEAD constructions like AES-GCM and ChaCha20-Poly1305 satisfy IND-CCA2.

For signatures, the analogous goal is **EUF-CMA** (existential unforgeability under chosen-message attack) — the attacker cannot produce a signature on any new message, even after seeing many valid signatures.

These acronyms appear constantly in papers and library docs. Knowing what they mean is half the battle.

### 1.4 Randomness

Almost every cryptographic operation needs unpredictable random bytes — for keys, nonces, IVs, salts, session tokens, OAuth `state`, everything. Using a bad source destroys the security of everything downstream.

- **CSPRNG** (cryptographically secure pseudorandom number generator) — what you must use. Sources:
  - Linux: `/dev/urandom` (modern kernels block until seeded, then never block). `getrandom(2)` is the modern syscall.
  - macOS: `/dev/urandom` is fine. `getentropy()` and `SecRandomCopyBytes` are first-class.
  - Node: `crypto.randomBytes(n)` (sync), `crypto.randomFillSync`. `crypto.randomUUID()` for v4 UUIDs.
  - Go: `crypto/rand.Read`. *Never* `math/rand` for anything security-related.
  - Python: `secrets` module. *Never* `random` for security.
- **Non-CSPRNG** — `Math.random()`, `rand()`, `math/rand`. These are deterministic given the seed and were designed for simulations and games. Using them for tokens, keys, or nonces is a vulnerability class on its own.
- **Seeding** — modern OS-level RNGs handle seeding for you. The historical Debian OpenSSL disaster (a one-line "fix" reduced entropy to 32768 possible keys for ~2 years, 2006–2008) is the cautionary tale for messing with this.

References: [RFC 4086 — Randomness Requirements](https://datatracker.ietf.org/doc/html/rfc4086), [Linux random number documentation](https://www.kernel.org/doc/html/latest/admin-guide/sysctl/kernel.html#random)

---

## Phase 2: Hashing

### 2.1 What a Cryptographic Hash Is

A hash function `H` maps an arbitrary-length input to a fixed-length output (the *digest*). Cryptographic hashes must satisfy three properties:

1. **Preimage resistance** — given `H(x)`, finding any `x'` with `H(x') = H(x)` is infeasible.
2. **Second-preimage resistance** — given `x` and `H(x)`, finding *another* `x' ≠ x` with `H(x') = H(x)` is infeasible.
3. **Collision resistance** — finding *any* pair `(x, x')` with `H(x) = H(x')` is infeasible.

Collision resistance is strictly stronger than second-preimage resistance, which is strictly stronger than preimage resistance. The output size bounds these by the *birthday bound*: a hash with `n`-bit output offers `~2^(n/2)` collision resistance and `~2^n` preimage resistance. SHA-256 → 128-bit collision, 256-bit preimage.

### 2.2 The Hash Function Landscape

- **MD5** — broken since 2004 (collisions trivially generated). Still used as a non-security checksum (e.g., S3 ETags). Never use for anything security-relevant.
- **SHA-1** — broken since 2017 ([SHAttered](https://shattered.io/)). Git still uses it (migrating to SHA-256). Avoid.
- **SHA-2 family** — SHA-256, SHA-384, SHA-512. The workhorse. Built on the Merkle–Damgård construction, which means they suffer from **length-extension attacks**: given `H(secret || message)` and the length of `secret`, an attacker can compute `H(secret || message || padding || extension)` *without knowing the secret*. This is why you never use raw SHA-256 as a MAC — use HMAC.
- **SHA-3 family** — SHA3-256, SHA3-512. Different construction (Keccak sponge), not vulnerable to length extension. Slower than SHA-2 in software on most CPUs. Use when you specifically want a Keccak-based hash.
- **BLAKE2 / BLAKE3** — modern, very fast, no length-extension issue. BLAKE3 is parallelizable and outperforms SHA-2 on every modern CPU. Use BLAKE3 for non-standardized integrity work where speed matters; use SHA-256 when you need interop with other systems.

For general-purpose use today: **SHA-256 by default** (interop), **BLAKE3 when speed matters**.

References: [NIST FIPS 180-4 (SHA-2)](https://csrc.nist.gov/publications/detail/fips/180/4/final), [BLAKE3 spec](https://github.com/BLAKE3-team/BLAKE3-specs)

### 2.3 HMAC

A hash takes data → digest. A **MAC** (message authentication code) takes a key + data → tag, where the tag can only be produced (and verified) by someone who knows the key.

**HMAC** is the standard construction: `HMAC(K, m) = H((K ⊕ opad) || H((K ⊕ ipad) || m))`. The clever nested structure makes it secure even when `H` itself has the length-extension weakness (so HMAC-SHA-256 is fine).

Use HMAC for:
- API request signing
- Webhook signature verification
- Session cookie integrity
- "Signed" URLs (e.g., S3 presigned URLs are HMAC-based)

**Always compare MAC tags in constant time** (`crypto.timingSafeEqual` in Node, `crypto/subtle.ConstantTimeCompare` in Go). A naïve `==` comparison leaks timing information that lets an attacker forge tags byte-by-byte.

### 2.4 Password Hashing

Password hashing is **not** general-purpose hashing. The goals are different:

- General hash: fast, deterministic, collision-resistant.
- Password hash: **deliberately slow**, **memory-hard** (resistant to GPU/ASIC attack), with a **salt** (so identical passwords don't produce identical hashes), and a **tunable work factor**.

The right algorithms, in order of preference:

- **Argon2id** (winner of the 2015 Password Hashing Competition) — the modern default. Tune `memory`, `iterations`, `parallelism` to your hardware budget. Target ~500ms–1s per hash on production hardware.
- **scrypt** — pre-Argon2, still respectable. Memory-hard. In Node's `crypto` module, in Go's `golang.org/x/crypto/scrypt`. Use when you can't ship an Argon2 dependency.
- **bcrypt** — the old default. Still fine if you can't move. **Hard 72-byte input limit** — passwords longer than 72 bytes are silently truncated. Pre-hash with SHA-256 + base64 if your users might have long passwords, then bcrypt that.
- **PBKDF2** — old. Acceptable for **legacy interop and FIPS compliance only**. Not memory-hard, so cheap to attack on GPUs.

**Never** use a plain hash (SHA-256, MD5) for passwords. A modern GPU computes billions of SHA-256s per second; a leaked database of SHA-256 password hashes is effectively plaintext.

**Salts** must be unique per password and at least 16 bytes from a CSPRNG. Salts go in the database alongside the hash; they are not secret. Their job is to prevent rainbow-table reuse across users and across databases.

**Peppers** are an *additional* secret value (the same for all users), stored outside the database (env var, KMS). They protect against database-only breaches. Useful but not a substitute for slow hashing.

References: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [Argon2 RFC 9106](https://datatracker.ietf.org/doc/html/rfc9106)

---

## Phase 3: Symmetric Encryption

### 3.1 Block Ciphers and AES

A **block cipher** transforms a fixed-size block of plaintext into a same-size block of ciphertext under a key. AES (Advanced Encryption Standard, FIPS 197) has a 128-bit block and supports 128/192/256-bit keys. It's the dominant block cipher.

A block cipher by itself only encrypts one block. To encrypt arbitrary data you wrap it in a **mode of operation**.

### 3.2 Modes of Operation

- **ECB** (Electronic Codebook) — each block encrypted independently. **Never use.** Identical plaintext blocks produce identical ciphertext blocks; the [ECB penguin](https://words.filippo.io/the-ecb-penguin/) shows the structure of your data through the ciphertext.
- **CBC** (Cipher Block Chaining) — each block XORed with the previous ciphertext block before encryption. Needs a unique IV per encryption. **Malleable**: bit-flips in ciphertext produce predictable bit-flips in plaintext. **Padding oracle attacks** (POODLE, Lucky13) made CBC notorious. Use only inside a Encrypt-then-MAC construction, and prefer AEAD.
- **CTR** (Counter) — turns the block cipher into a stream cipher by encrypting a counter and XORing with plaintext. **Nonce reuse is catastrophic**: encrypting two messages with the same `(key, nonce)` reveals the XOR of the two plaintexts. No integrity by itself.
- **GCM** (Galois/Counter Mode) — CTR + GHASH authentication. The standard AEAD mode. AES-GCM is the default in TLS 1.3. **Nonce reuse is still catastrophic** — same `(key, nonce)` reveals plaintext XOR *and* the authentication key. AES-GCM nonces are 96 bits; if generated randomly, birthday-bound after ~2³² encryptions per key.
- **GCM-SIV** (RFC 8452) — nonce-misuse-resistant variant. If you reuse a nonce, you only leak whether the plaintexts were identical, not their contents. Slower than GCM. Use when you can't guarantee nonce uniqueness.
- **XTS** — for disk encryption where ciphertext length must equal plaintext length. Not for general use.

### 3.3 ChaCha20-Poly1305

The other modern AEAD. A stream cipher (ChaCha20) + a MAC (Poly1305). Designed by Daniel J. Bernstein. Highlights:

- **No hardware acceleration required** — fast in pure software. On CPUs without AES-NI (older phones, embedded devices), it beats AES-GCM.
- **256-bit key**, **96-bit nonce** (or 192-bit in the `XChaCha20-Poly1305` variant, which makes random nonces safe).
- TLS 1.3 includes it as a peer to AES-GCM.

**XChaCha20-Poly1305** is what `libsodium`'s `crypto_secretbox` uses. If your nonces are random and you want zero footguns, this is the safest single primitive to reach for.

### 3.4 What to Actually Use

| Need                     | Use                                                  |
|--------------------------|------------------------------------------------------|
| New design, no constraints | XChaCha20-Poly1305 via libsodium                  |
| TLS-style interop        | AES-256-GCM                                         |
| Embedded, no AES-NI      | ChaCha20-Poly1305                                   |
| Can't guarantee unique nonces | AES-GCM-SIV or XChaCha20-Poly1305              |
| Disk encryption          | AES-XTS                                             |
| Anything else CBC/ECB    | Stop. Use AEAD.                                     |

References: [NIST SP 800-38D (GCM)](https://csrc.nist.gov/publications/detail/sp/800-38d/final), [RFC 8439 (ChaCha20-Poly1305)](https://datatracker.ietf.org/doc/html/rfc8439), [Latacora's Cryptographic Right Answers](https://latacora.singles/2018/04/03/cryptographic-right-answers.html)

---

## Phase 4: Asymmetric Encryption & The Math Behind It

### 4.1 Why Asymmetric Crypto Exists

Symmetric crypto requires both parties to share a secret key. That's a chicken-and-egg problem: how do you share the key over an insecure channel? **Public-key cryptography** solves this. Each party has a *key pair*: a public key (anyone can know) and a private key (only the owner knows). The public key can encrypt to the owner, or verify signatures from the owner.

Asymmetric ops are **orders of magnitude slower** than symmetric ones. So in practice, you don't encrypt bulk data with public-key crypto. You use it to either:
- Encrypt a fresh symmetric key (which then encrypts the data) — *hybrid encryption*.
- Do a key exchange (DH) that derives a shared symmetric key — *the modern approach*.
- Sign a hash of the data.

### 4.2 RSA

The first widely deployed public-key system. Security rests on the difficulty of factoring large integers (`n = p * q` where `p`, `q` are large primes).

**Key sizes**: 2048-bit is the practical minimum today; 3072-bit gives ~128-bit security; 4096-bit is overkill for almost everyone. RSA keys are expensive to generate (a 4096-bit key can take seconds on a modern laptop).

**Critical RSA pitfalls**:
- **Textbook RSA** (`c = m^e mod n`) is **broken** as an encryption scheme. It's deterministic, malleable, and leaks information. *Never use it directly.*
- **PKCS#1 v1.5 padding** for encryption is vulnerable to [Bleichenbacher attacks](https://en.wikipedia.org/wiki/Adaptive_chosen-ciphertext_attack) (1998, repeatedly rediscovered: ROBOT 2017, Marvin 2023). Don't use for new code.
- **OAEP padding** (RSA-OAEP) is the modern choice for encryption.
- For signatures: **PKCS#1 v1.5** is still widely used and acceptable; **PSS** is the more modern choice.

Honestly: for new designs, just don't use RSA. Use ECC.

### 4.3 Elliptic Curve Cryptography (ECC) in One Page

ECC operates on points of an elliptic curve over a finite field. The hard problem is the *elliptic curve discrete logarithm*: given points `P` and `Q = k·P`, find `k`. For well-chosen curves this is infeasible.

**Why ECC**:
- A 256-bit elliptic curve key offers ~128-bit security — equivalent to a 3072-bit RSA key. Smaller keys, faster operations, faster handshakes.
- Better forward secrecy story (ECDHE is the default in TLS 1.3).
- Smaller signatures.

**Curves worth knowing**:
- **P-256 / P-384 / P-521** (NIST curves) — standardized, broadly supported, FIPS-compliant. Use when you need interop.
- **Curve25519** (for ECDH, called **X25519**) and **Ed25519** (for signatures) — designed by Daniel J. Bernstein. Misuse-resistant, fast, no controversial parameter choices. Use these for anything new where interop allows.
- **secp256k1** — Bitcoin's curve. Don't use unless you're doing blockchain work.

References: [SafeCurves](https://safecurves.cr.yp.to/), [RFC 7748 (X25519)](https://datatracker.ietf.org/doc/html/rfc7748)

### 4.4 Hybrid Encryption

The standard pattern for "encrypt this data to a public key":

1. Generate a fresh symmetric key (the *data encryption key*).
2. Encrypt the data with that symmetric key using AEAD.
3. Encrypt the symmetric key with the recipient's public key.
4. Ship `(encrypted_data, encrypted_key)`.

This is what PGP does, what S/MIME does, and what every "encrypt a large blob to a public key" library does under the hood. **HPKE** (Hybrid Public Key Encryption, RFC 9180) is the modern standardized version — use it instead of rolling your own.

---

## Phase 5: Key Exchange & Key Derivation

### 5.1 Diffie–Hellman

Two parties can agree on a shared secret over a public channel, even with an eavesdropper, without ever transmitting the secret.

- Each party generates a key pair `(a, A=g^a)` and `(b, B=g^b)`.
- They exchange public values `A` and `B`.
- Both compute `s = A^b = B^a = g^(ab)`.

**ECDH** is the elliptic-curve version. **X25519** is the modern, misuse-resistant ECDH. This is the building block of TLS handshakes and Signal's Double Ratchet.

**Forward secrecy** (a.k.a. *perfect forward secrecy*, PFS): if you use a *fresh ephemeral* DH key pair for each session and discard it after, then even if the long-term private key leaks later, past session keys cannot be recovered. **TLS 1.3 mandates this** (all cipher suites use ephemeral ECDH).

### 5.2 Authenticated Key Exchange

Raw DH is vulnerable to man-in-the-middle: the attacker does DH with both parties separately. Real protocols **authenticate** the DH exchange — typically by signing the DH public value with a long-term key whose certificate is trusted (this is what TLS does), or via a pre-shared key, or via a PAKE.

### 5.3 Key Derivation Functions

The output of DH is a uniform-looking byte string but isn't directly suitable as a key — it's biased depending on the algebraic structure. You run it through a **KDF** to produce usable keys.

- **HKDF** (HMAC-based KDF, RFC 5869) — the standard. Two steps: *extract* (concentrates entropy) and *expand* (produces arbitrary-length output). Use this for deriving symmetric keys from a DH shared secret, or for deriving multiple keys from one master key.
- **PBKDF2** — old, for deriving keys from passwords. Use **Argon2id** instead for new code.

A common pattern with HKDF:

```
shared = X25519(my_priv, their_pub)
enc_key  = HKDF(shared, salt, info=b"enc-key",  len=32)
mac_key  = HKDF(shared, salt, info=b"mac-key",  len=32)
```

The `info` parameter provides **domain separation** — different contexts derive different keys even from the same source.

### 5.4 PAKEs

**Password-Authenticated Key Exchange** lets two parties derive a strong shared key from a weak shared password, *without* the password being recoverable by an eavesdropper or by an offline attacker.

- **SRP** (Secure Remote Password) — old, used by 1Password historically and Apple's iCloud KeyChain. Has known weaknesses; deprecated for new work.
- **OPAQUE** (RFC 9807, 2024) — the modern aPAKE. Server learns nothing about the password even during registration. Use this if you're designing authentication from first principles.

References: [RFC 5869 (HKDF)](https://datatracker.ietf.org/doc/html/rfc5869), [Cryptographic Doom Principle](https://moxie.org/2011/12/13/the-cryptographic-doom-principle.html)

---

## Phase 6: Digital Signatures

### 6.1 What a Signature Is (and Isn't)

A signature scheme has three operations: `keygen()`, `sign(privkey, message) → signature`, `verify(pubkey, message, signature) → bool`.

- Signatures provide **authenticity + integrity + non-repudiation**.
- Signatures do **not** provide confidentiality. They're typically computed *over a hash of the message*, then transmitted *alongside* the (possibly plaintext) message.
- A signature is **not** an encrypted hash. This is a common misconception spread by analogy with RSA-PKCS#1 v1.5, where the operation looks superficially like decryption with the public key. It's not. Other signature schemes (ECDSA, Ed25519) have no decryption-shaped operation at all.

### 6.2 The Schemes

- **RSA-PKCS#1 v1.5** — old, deterministic, still in use. Acceptable for verification of existing signatures. For new work, prefer PSS.
- **RSA-PSS** (RFC 8017) — RSA with probabilistic padding. Better security proof. The current right answer if you have to use RSA.
- **ECDSA** — elliptic-curve DSA. Standardized (FIPS 186), widely supported. **Catastrophic nonce-reuse footgun**: if two signatures use the same `k` (nonce), the private key can be recovered with a few lines of algebra. This is how the [Sony PS3 was hacked](https://www.bbc.com/news/technology-12116051) — they used a constant `k`. Deterministic ECDSA (RFC 6979) eliminates this by deriving `k` from the private key + message hash.
- **Ed25519** — EdDSA over Curve25519. **No nonce required at all** (it's derived deterministically inside the algorithm). Misuse-resistant. Fast. Small signatures (64 bytes). Use this for new work.

| Scheme    | Key size | Sig size | Use case                                 |
|-----------|----------|----------|------------------------------------------|
| RSA-PSS   | 256+ B   | 256+ B   | Legacy interop, FIPS compliance          |
| ECDSA-P256| 32 B     | ~70 B    | TLS, WebAuthn, anything that needs FIPS  |
| Ed25519   | 32 B     | 64 B     | Anything new                             |

### 6.3 What You Actually Sign

A subtle but critical point: **sign exactly what you mean**.

- Always sign a hash of the message, not the message itself (most libraries do this for you).
- If your message is structured (JSON, CBOR), use **canonical** encoding before signing. Otherwise an attacker can re-encode the same logical message into different bytes and produce a valid signature for both — leading to confusion attacks.
- Include **context / domain separation** in what you sign. Signing `"transfer:" || from || to || amount` prevents an attacker from replaying the signature in a different protocol context.

This is what RFC 8032 calls the "context string" for Ed25519ctx, and what TLS 1.3 calls the "context label" in its signature inputs.

---

## Phase 7: TLS

### 7.1 What TLS Actually Does

TLS provides authenticated, confidential channels between two parties over an unauthenticated network. The protocol does three things on every connection:

1. **Authenticate** the server (and optionally the client) via certificates.
2. **Establish** a shared symmetric key via an ephemeral key exchange.
3. **Encrypt + authenticate** all subsequent traffic with an AEAD cipher under that key.

### 7.2 TLS 1.2 vs. TLS 1.3

The differences are large enough that they're worth knowing.

| Aspect | TLS 1.2 | TLS 1.3 |
|--------|---------|---------|
| Handshake round-trips | 2 (full) | 1 (full), 0 (resumed) |
| Cipher suites | Dozens, many broken | 5, all AEAD |
| Key exchange | RSA, DHE, ECDHE | ECDHE only (forward secrecy mandatory) |
| Signature in handshake | Optional | Mandatory |
| Old crypto allowed | RC4, 3DES, CBC, SHA-1, RSA-PKCS#1 v1.5 | None of these |
| Server hello | Plaintext | Encrypted (mostly) |

**Disable TLS 1.0 and 1.1.** They're deprecated by RFC 8996 (2021). Disable TLS 1.2 if you can — but most production deployments still need it for client compatibility. Disable known-bad cipher suites: anything with CBC, anything with RSA key exchange (no forward secrecy), anything with SHA-1.

### 7.3 The Certificate Chain

A TLS server presents a chain of X.509 certificates ending at a trusted root. Each cert is signed by the next; the client validates the chain against its trust store.

- **Trust stores** — the OS, browser, or runtime ships a list of root CAs. Mozilla's CA list, the macOS keychain, `/etc/ssl/certs` on Linux, Node's `tls.rootCertificates`. *This is the foundation of public-CA TLS.*
- **Let's Encrypt** — free, automated, dominant for public-facing servers. Use a client like `certbot`, `caddy` (handles it automatically), or `acme.sh`.
- **OCSP / OCSP stapling** — online cert revocation checking. The server "staples" a fresh OCSP response into the TLS handshake so the client doesn't have to query the CA.
- **CT logs** (Certificate Transparency) — public append-only logs of every issued cert. Browsers require certs to be logged. This is how unauthorized cert issuance gets caught.
- **CAA records** — DNS records that tell CAs "only issue certs for my domain to these CAs." Set them.

### 7.4 mTLS

Mutual TLS: the *client* also presents a cert, authenticating to the server. Used heavily in zero-trust service-to-service architectures (Istio, Linkerd, modern bank back-ends).

Operational complexity is real: you need a private CA, you need to issue and rotate client certs, you need to handle revocation. Tools like [cert-manager](https://cert-manager.io/), [step-ca](https://smallstep.com/docs/step-ca/), or HashiCorp Vault's PKI engine manage this.

### 7.5 Certificate Pinning

The client refuses to trust *any* cert except a specific one (or one signed by a specific intermediate). Stops compromised CAs from issuing rogue certs for your domain.

- **Static pinning** in mobile apps is the classic case. Powerful, but **the wrong pin bricks your app** until users update.
- **HPKP** (HTTP Public Key Pinning) for browsers was deprecated and removed — the footguns outweighed the benefits.
- Modern replacement: **Expect-CT** header (also being phased out as CT is now mandatory), and just relying on CT + CAA records.

### 7.6 Common TLS Misconfigurations

- Self-signed certs in production.
- Expired certs (monitor via `cert-manager`, Prometheus blackbox-exporter, or a simple cron).
- Missing intermediate certs (the famous "works in browsers, breaks in curl/Go" symptom).
- Weak DH parameters (Logjam).
- Mixed-content pages.
- HSTS missing or with too-short max-age.
- Not redirecting HTTP → HTTPS.

Tools: [SSL Labs](https://www.ssllabs.com/ssltest/), [testssl.sh](https://testssl.sh/), [`openssl s_client -connect host:443`].

References: [RFC 8446 (TLS 1.3)](https://datatracker.ietf.org/doc/html/rfc8446), [BetterTLS](https://bettertls.com/), [Cloudflare's TLS 1.3 deep dive](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/)

---

## Phase 8: Tokens, Sessions, and Auth Crypto

### 8.1 The Two Models

Almost every web auth system is one of:

- **Server-side sessions**: the client holds an opaque random session ID; the server keeps the actual state (user ID, roles, expiry) in a session store (Redis, Postgres, memcached). Revocation is trivial — delete the row.
- **Stateless tokens** (typically JWT): the client holds a signed/encrypted token that *contains* the state. Server can verify with just a key. Revocation is hard — you have to maintain a deny-list.

Default to server-side sessions unless you have a specific reason to use stateless tokens (cross-service trust, scale-out without a shared store). Even then, prefer **short-lived access tokens + opaque refresh tokens**: the access token can be a JWT for stateless verification, but the refresh token is opaque and revocable.

### 8.2 JWT Pitfalls

JWTs are a footgun-rich format. Many of the well-known attacks come from how libraries handle the format, not from the underlying crypto.

- **`alg: none`** — historical attack. The token says it's unsigned; the library accepts it. Modern libraries reject this by default, but verify yours does.
- **Algorithm confusion** — server expects RS256 (asymmetric); attacker submits a JWT with `alg: HS256` and uses the server's public RSA key as the HMAC secret. The library happily verifies. **Mitigation**: pin the expected algorithm at verify time. Don't trust the `alg` header.
- **`kid` injection** — the `kid` (key ID) header points to a key. If your library reads `kid` as a file path or SQL parameter, it's an LFI/SQLi vector. Treat `kid` as an opaque key into a fixed map.
- **JWK header confusion** — some libraries trust the `jwk` field in the JWT header (an embedded public key). This lets an attacker provide *their own* key and have it accepted. Never use the `jwk` header for verification.
- **Long-lived JWTs are not revocable**. If you log out a user, the JWT they hold is still valid until expiry. Either keep JWTs short (5–15 minutes) and use refresh tokens, or maintain a revocation list, or use server-side sessions.
- **Don't put secrets in JWTs**. The payload is base64-encoded, not encrypted, by default. Use JWE if you need confidentiality (rare and complex; prefer not putting secrets in tokens at all).

### 8.3 Alternatives to JWT

- **PASETO** (Platform-Agnostic Security Tokens) — designed to fix JWT's problems. Algorithm pinned per version (`v4.local`, `v4.public`). No alg confusion possible. Worth strong consideration for new designs.
- **Branca** — similarly minimal. XChaCha20-Poly1305 by default. Even simpler than PASETO.
- **Opaque session tokens** — just a random 256-bit ID in a cookie, looked up server-side. Boring, secure, revocable. The right default for most apps.

### 8.4 SAML and the Signature Wrapping Disaster

SAML is XML-based federated SSO. The format is sufficiently complex that **XML signature wrapping** has been a recurring exploit class — the attacker reorganizes the XML so the signed element and the element-being-trusted are different. If you're consuming SAML, use a hardened library (`python3-saml`, `passport-saml`) and stay current with patches. SAML for new designs is mostly a "you have to interop with an enterprise IdP" choice. For new SSO, use OIDC.

### 8.5 OIDC

OpenID Connect is OAuth 2.0 + identity. The flow you want is almost always **Authorization Code with PKCE**.

- The **ID token** is a JWT containing user identity claims. Validate it: signature, issuer, audience, expiry, nonce.
- The **access token** authorizes API calls. Treat as opaque unless your provider says otherwise.
- The **refresh token** is long-lived, *single-use* (with rotation), and high-value. Store securely.
- **PKCE** (Proof Key for Code Exchange) — extension that protects against authorization code interception. Originally for mobile, now required for all clients in best-current-practice OAuth 2.1.

References: [RFC 8725 (JWT BCP)](https://datatracker.ietf.org/doc/html/rfc8725), [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1), [PASETO spec](https://github.com/paseto-standard/paseto-spec)

---

## Phase 9: Cryptographic Engineering

### 9.1 Constant-Time Code

Crypto code must execute in time independent of secret values. If comparison of a MAC takes longer when more bytes match, an attacker can binary-search the MAC byte by byte over the network. Real attacks have been demonstrated.

- Use `crypto.timingSafeEqual` (Node), `crypto/subtle.ConstantTimeCompare` (Go), `hmac.compare_digest` (Python), `sodium_memcmp` (libsodium).
- Never `==`, never `strcmp`, never `[a, b].every(...)`.
- Branch-free conditionals: instead of `if secret == 0`, libraries do `(secret | -secret) >> 63` and similar bit tricks. You won't write these — but you should recognize them in code review of crypto libraries.

### 9.2 Side Channels

Anything an attacker can measure that depends on secret values is a side channel:

- **Timing** — the most common, attackable over the network. Constant-time code fixes this for the algorithmic level. Hardware (cache, branch predictor) is harder.
- **Cache** — Spectre, Meltdown, and friends. Constant-time code at the algorithm level can still leak through CPU cache behavior. Mitigated mostly at the hardware/microcode level.
- **Power** — measuring power consumption recovers keys on smart cards. Relevant for embedded.
- **EM** — measuring electromagnetic emissions. Same.
- **Acoustic** — yes, this works ([microphone-based key extraction](https://www.cs.tau.ac.il/~tromer/acoustic/)). Mostly academic for now.

You will not defend against the last three. You will defend against timing, by using vetted libraries.

### 9.3 Picking a Library

The trustworthy options, by language:

- **C/C++**: [libsodium](https://doc.libsodium.org/), BoringSSL, OpenSSL (if you must — large, complex, historically footgun-rich).
- **Rust**: [`ring`](https://github.com/briansmith/ring), [`rustls`](https://github.com/rustls/rustls), [`age`](https://github.com/FiloSottile/age) (file enc), `RustCrypto` family.
- **Go**: `crypto/*` standard library, `golang.org/x/crypto`, `filippo.io/age`.
- **Node**: `crypto` standard library, [`@panva/jose`](https://github.com/panva/jose), `argon2`, `sodium-native`.
- **Python**: [`cryptography`](https://cryptography.io/) (the standard answer), `pynacl`, `argon2-cffi`.
- **JVM**: BouncyCastle, Google Tink.

What to avoid: PyCrypto (unmaintained), `crypto-js` (slow JS implementations of broken modes, often misused), anything labeled "experimental" or "novel" without active maintainership.

[Google Tink](https://developers.google.com/tink) deserves a special mention: it's a high-level library that exposes only the right primitives with only the right defaults, across many languages. If you're starting fresh with no interop constraints, it's a strong choice.

### 9.4 Key Management

The hardest part of applied crypto isn't the math. It's **where the keys live**.

- **Environment variables** — fine for low-stakes services. Visible to anyone with shell access; leaked in crash logs, in `/proc/<pid>/environ`, in process listings.
- **Secret managers** — AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault. Centralized storage, audit logs, rotation hooks. The right default for cloud.
- **KMS** (Key Management Service) — AWS KMS, GCP KMS, Azure Key Vault, Vault Transit. The *key never leaves the service*; you call the KMS to encrypt/decrypt with it. See "Envelope encryption" in Phase 13.
- **HSMs** (Hardware Security Modules) — keys live in tamper-resistant hardware. Used for root CAs, payment processors, signing keys for code-signing certificates. CloudHSM (AWS), Cloud HSM (GCP), or on-prem (YubiHSM, Thales, etc.).

### 9.5 Key Rotation

Every secret has a rotation story. If you can't rotate it, you have no recovery path when it leaks.

- Make every secret consumer support **at least two valid keys** (current + previous). Rotate by introducing a new key, signing/encrypting with the new one, leaving the old one accepted for the rotation window, then retiring it.
- Use **key IDs** in your tokens (`kid` in JWTs, version tags in encrypted blobs) so consumers know which key to use.
- For TLS certs: short-lived (90 days for Let's Encrypt) and automated. Yearly cert rotation done by hand is a reliable source of outages.
- For long-lived service keys: rotate yearly minimum, monthly if cheap.

### 9.6 Testing Your Crypto Code

- **Don't write golden-output tests with hardcoded ciphertexts** for non-deterministic primitives (AES-GCM, Ed25519). The output is supposed to vary. Test the *round-trip*: encrypt → decrypt = original.
- **Test failure paths**: bad MAC, truncated ciphertext, modified ciphertext, wrong key. They should *fail closed*.
- **Fuzz** with `cargo fuzz`, `go-fuzz`, `atheris`. Cryptographic code is great fuzz target — clear failure modes.
- **Misuse-resistant by construction** beats "well-tested" every time. The right primitive choice (e.g., XChaCha20-Poly1305) removes whole classes of test cases you'd otherwise need.

References: [Cryptopals Crypto Challenges](https://cryptopals.com/), [Real-World Crypto Slides](https://rwc.iacr.org/)

---

## Phase 10: Post-Quantum & the Modern Landscape

### 10.1 The Quantum Threat, Honestly

A sufficiently large quantum computer running **Shor's algorithm** breaks every public-key system in widespread use today: RSA, DH, ECDH, ECDSA, Ed25519. Symmetric algorithms (AES, ChaCha20, SHA-256) are mostly fine — **Grover's algorithm** halves the effective key size, so AES-256 still gives 128-bit security against a quantum adversary.

"Sufficiently large" is the key qualifier. As of 2026, the largest demonstrated quantum factorization is small enough that real RSA keys are nowhere near threatened. Estimates for cryptographically-relevant quantum computers range from 10 to 30+ years, with high uncertainty.

But: **harvest now, decrypt later**. An adversary with the patience to record encrypted traffic *today* can decrypt it whenever quantum capability arrives. For data that needs to stay confidential for decades (state secrets, long-lived health records), this is a real threat now.

### 10.2 NIST PQC Standards

NIST finalized the first batch of post-quantum standards in 2024:

- **ML-KEM** (Module-Lattice-Based Key Encapsulation Mechanism, FIPS 203) — formerly Kyber. The PQ replacement for ECDH key exchange.
- **ML-DSA** (Module-Lattice-Based Digital Signature Algorithm, FIPS 204) — formerly Dilithium. The PQ general-purpose signature.
- **SLH-DSA** (Stateless Hash-Based Digital Signature Algorithm, FIPS 205) — formerly SPHINCS+. Larger and slower than ML-DSA, but built on minimal assumptions (just hash function security), so it's the most conservative option. Good fit for root-of-trust signing where you sign rarely but need long-term confidence.

### 10.3 Hybrid Deployments

The industry consensus is to ship **hybrid** crypto during the transition: do *both* a classical (ECDH) and a post-quantum (ML-KEM) operation, and combine the results. If either holds, you're safe.

- Chrome and Cloudflare ship X25519+Kyber768 hybrid for TLS handshakes already (rolling out 2023–2024).
- SSH (OpenSSH 9.0+) supports `sntrup761x25519-sha512` as a hybrid KEX.
- Signal announced PQXDH in 2023, adding a Kyber-based PQ step to the Double Ratchet.

What this means for you, today: if you operate TLS at scale, evaluate hybrid KEX. For everything else, the classical primitives are still fine. Don't rip out Ed25519 in a panic.

References: [NIST PQC project](https://csrc.nist.gov/projects/post-quantum-cryptography), [Cloudflare's PQ deployment posts](https://blog.cloudflare.com/post-quantum-for-all/), [Signal's PQXDH](https://signal.org/docs/specifications/pqxdh/)

---

## Phase 11: Auth in Node.js, Done Right

This is where everything in Phases 1–9 lands in code. Most production breaches at the auth layer are not crypto-math failures — they're library misuse, sloppy session handling, or missing defenses. This section is prescriptive.

### 11.1 The Decision Tree

Before writing any auth code, ask: **do I need to?**

- **Use a managed identity provider** (Auth0, Okta, WorkOS, Clerk) if you're a B2B SaaS, if SSO is on the roadmap, or if losing a weekend to OIDC mechanics costs more than the subscription. Bonus: SOC 2 paperwork gets easier.
- **Use an auth library** ([Auth.js](https://authjs.dev/) (formerly NextAuth), [Lucia](https://lucia-auth.com/), [Better-Auth](https://better-auth.com/)) if you want self-hosted auth but not from-scratch. These libraries get sessions, OAuth, cookies, and CSRF mostly right by default.
- **Roll your own** only when you have specific requirements no library serves. Allocate triple the time you think it'll take.

When you do roll your own: keep the surface area small, use the well-trodden primitives below, and don't deviate.

### 11.2 Password Storage

Use **Argon2id**. Don't think about it.

```js
import argon2 from 'argon2';

// On registration / password change:
const hash = await argon2.hash(password, {
  type: argon2.argon2id,
  memoryCost: 2 ** 16,    // 64 MB. Tune to your hardware budget.
  timeCost: 3,
  parallelism: 1,
});
await db.users.update(userId, { passwordHash: hash });

// On login:
const valid = await argon2.verify(user.passwordHash, password);
if (!valid) { /* reject */ }
```

Notes:
- The `argon2` npm package is a binding to the reference C implementation. Use it, not the pure-JS port.
- The hash output is a self-describing string (`$argon2id$v=19$m=65536,t=3,p=1$...`). The parameters live in the hash — no separate columns needed.
- Tune parameters to target ~250–500ms per hash on your **production** hardware, then verify with a load test that your login endpoint isn't the bottleneck under traffic.
- If you can't ship Argon2 (Alpine container without build tools, etc.), `bcrypt` is still acceptable. Use `bcrypt` (native bindings), not `bcryptjs` (pure JS, ~10x slower so you get ~10x weaker work factor for the same latency budget).

### 11.3 Primitives from `node:crypto`

The standard library is mostly sufficient. The handful of functions you'll use:

```js
import {
  randomBytes,
  randomUUID,
  timingSafeEqual,
  createHmac,
  scrypt,
} from 'node:crypto';

// Generate session token / OAuth state / CSRF token:
const token = randomBytes(32).toString('base64url');

// Generate a UUID v4:
const id = randomUUID();

// Compare a presented token to a stored one — ALWAYS constant-time:
const presented = Buffer.from(req.body.token, 'utf8');
const expected = Buffer.from(storedToken, 'utf8');
if (presented.length !== expected.length) return reject();  // Length check is OK to do non-constant-time
if (!timingSafeEqual(presented, expected)) return reject();

// HMAC for signing things (webhook tokens, signed cookies):
const sig = createHmac('sha256', signingKey).update(payload).digest('hex');
```

**Never use `Math.random()`** for any token, ID, or salt. It's not a CSPRNG.

**Always pass Buffers of equal length to `timingSafeEqual`** — it throws on unequal lengths. Check length first as a non-secret operation.

### 11.4 Session Cookies

Default to **server-side sessions** keyed by a random ID in a cookie. Use Redis (or any KV store) for the session store.

```js
// express-session-style setup:
app.use(session({
  name: '__Host-sid',                // __Host- prefix locks the cookie to the exact origin
  secret: process.env.SESSION_SECRET, // 32+ random bytes from a CSPRNG
  resave: false,
  saveUninitialized: false,
  store: new RedisStore({ client: redis }),
  cookie: {
    httpOnly: true,                  // No JS access
    secure: true,                    // HTTPS only — required by __Host-
    sameSite: 'lax',                 // 'strict' if you have no cross-site flows
    path: '/',                       // Required by __Host-
    maxAge: 1000 * 60 * 60 * 24 * 7, // 7 days. Renew sliding-window on activity.
  },
}));
```

Cookie hardening reference:
- **`HttpOnly`** — blocks JS access. Mitigates XSS-based token theft. *Always set.*
- **`Secure`** — HTTPS only. *Always set in production.*
- **`SameSite=Lax`** — sent on top-level navigations only. Baseline CSRF defense. **`Strict`** blocks even legitimate cross-site navigations (e.g., link from email won't be logged in). `None` requires `Secure` and is for cross-site embeds (iframes, OAuth).
- **`__Host-` prefix** — browser enforces: must have `Secure`, must have `Path=/`, must not have `Domain` attribute. Strongest cookie-scoping you can get.
- **`__Secure-` prefix** — weaker version: just requires `Secure`. Use if you need `Domain=` for subdomain sharing.

**Rotate the session ID on privilege change** (login, role change). This prevents session fixation: an attacker who plants a cookie before login otherwise inherits the authenticated session.

### 11.5 CSRF in 2026

CSRF is significantly less scary than it used to be, because `SameSite=Lax` is the default in modern browsers. But the threat model has shifted, not vanished.

- **`SameSite=Lax`** is your baseline. Almost everything works correctly under it.
- **Server-rendered apps with form posts to the same origin** — `SameSite=Lax` is sufficient unless you have GET endpoints that mutate state (don't have those).
- **SPAs talking to APIs on the same origin** — also fine with `SameSite=Lax`. The fetch is same-site.
- **SPAs talking to APIs on a different subdomain or origin** — you need CORS configured (`Access-Control-Allow-Credentials: true`, explicit `Access-Control-Allow-Origin` — no `*` with credentials). And you should add an explicit token check (double-submit or session-bound).
- **Cross-origin POSTs from forms** — blocked by `SameSite=Lax`. If you need them (rare), use `SameSite=None` and a CSRF token.

The old `csurf` middleware is **deprecated and unmaintained**. Modern options:

- [`csrf-csrf`](https://www.npmjs.com/package/csrf-csrf) — double-submit cookie pattern. Works for SPA + API setups.
- Build your own minimal version: store a random 32-byte token in the session, send it in a custom header on writes, compare server-side with `timingSafeEqual`.

### 11.6 JWTs Done Right

If you must use JWTs, **use [`jose`](https://github.com/panva/jose)**, not `jsonwebtoken`. `jose` is misuse-resistant by default: you specify the algorithm at verify time, JWK selection is explicit, and the API forces you to handle errors.

```js
import { SignJWT, jwtVerify, createRemoteJWKSet } from 'jose';

// Issuing a token (signed by your service):
const key = await importPKCS8(process.env.PRIVATE_KEY, 'EdDSA');
const token = await new SignJWT({ sub: userId, role: 'user' })
  .setProtectedHeader({ alg: 'EdDSA', kid: 'k1' })
  .setIssuer('https://auth.example.com')
  .setAudience('https://api.example.com')
  .setIssuedAt()
  .setExpirationTime('15m')           // SHORT. 15 min, not 24 hours.
  .setJti(randomUUID())
  .sign(key);

// Verifying a token (e.g., from another service):
const JWKS = createRemoteJWKSet(new URL('https://auth.example.com/.well-known/jwks.json'));
const { payload } = await jwtVerify(token, JWKS, {
  algorithms: ['EdDSA'],              // Pin the algorithm. Critical.
  issuer: 'https://auth.example.com',
  audience: 'https://api.example.com',
});
```

The non-negotiables:
- **Pin `algorithms`** at verify. Without this, alg-confusion attacks are possible.
- **Validate `iss` and `aud`** at verify. Otherwise a token issued for one service is valid at another.
- **Short expiry** (5–15 min). Combined with refresh tokens for long sessions.
- **Refresh tokens are opaque random strings, server-side, single-use with rotation**. On every refresh, issue a new pair and invalidate the old refresh. Detect reuse (= "someone stole the refresh token") and force re-login.
- **JWKS caching with rotation**. `createRemoteJWKSet` caches and refreshes; you don't have to manage this.

Don't put secrets (passwords, PII) in JWT payloads. The payload is base64-encoded, not encrypted.

### 11.7 OIDC Clients

For "log in with Google/GitHub/etc." or for talking to corporate IdPs, use [`openid-client`](https://github.com/panva/openid-client) (same author as `jose`). It implements OIDC correctly, including PKCE.

```js
import * as client from 'openid-client';

// Discovery once at startup:
const config = await client.discovery(
  new URL('https://accounts.google.com'),
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
);

// On login start:
const codeVerifier = client.randomPKCECodeVerifier();
const codeChallenge = await client.calculatePKCECodeChallenge(codeVerifier);
const state = client.randomState();
req.session.oidc = { codeVerifier, state };

const authUrl = client.buildAuthorizationUrl(config, {
  redirect_uri: 'https://example.com/callback',
  scope: 'openid email profile',
  code_challenge: codeChallenge,
  code_challenge_method: 'S256',
  state,
});
res.redirect(authUrl.href);

// On callback:
const tokens = await client.authorizationCodeGrant(config, new URL(req.url), {
  pkceCodeVerifier: req.session.oidc.codeVerifier,
  expectedState: req.session.oidc.state,
});
const claims = tokens.claims();   // Validated ID token claims
```

**Always**: PKCE on every flow (including confidential clients — required in OAuth 2.1). Validate `state`. Validate `nonce` if you use the implicit/hybrid flows (you shouldn't — use code+PKCE). Validate the redirect URL against an exact-match allow-list.

### 11.8 MFA and Passkeys

**TOTP** (time-based one-time passwords, RFC 6238) is the workhorse second factor. Use [`otplib`](https://www.npmjs.com/package/otplib):

```js
import { authenticator } from 'otplib';

// On enrollment:
const secret = authenticator.generateSecret();
// Show QR code: otpauth://totp/Example:user@example.com?secret=...&issuer=Example
await db.users.update(userId, { totpSecret: encrypt(secret) });

// On login (after password):
const valid = authenticator.verify({ token: code, secret });
// Note: small window of acceptance (±1 step = ±30s) for clock skew.
```

Always issue **backup codes** at TOTP enrollment — single-use random strings, hashed in the database. Without them, lost-phone scenarios become permanent lockouts.

**Passkeys** (WebAuthn) are the modern direction — phishing-resistant, no shared secret, the credential is bound to the origin. Use [`@simplewebauthn/server`](https://github.com/MasterKale/SimpleWebAuthn):

```js
import {
  generateRegistrationOptions, verifyRegistrationResponse,
  generateAuthenticationOptions, verifyAuthenticationResponse,
} from '@simplewebauthn/server';

// Registration:
const options = await generateRegistrationOptions({
  rpName: 'Example',
  rpID: 'example.com',
  userName: user.email,
  userID: user.idBuffer,
  attestationType: 'none',     // 'none' unless you have a specific reason for attestation
});
// Send options to client, client calls navigator.credentials.create(), sends response back.
const verification = await verifyRegistrationResponse({
  response: clientResponse,
  expectedChallenge: options.challenge,  // Store challenge server-side, single-use
  expectedOrigin: 'https://example.com',
  expectedRPID: 'example.com',
});
if (verification.verified) {
  await db.credentials.insert({ userId, credential: verification.registrationInfo });
}
```

Passkeys are the right default for new auth designs in 2026, with passwords as a fallback for legacy accounts.

### 11.9 Rate Limiting & Brute-Force Defense

Every auth endpoint needs rate limiting, separate from your general API limits.

```js
import { rateLimit } from 'express-rate-limit';

const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,        // 15 minutes
  max: 10,                         // 10 attempts per IP
  standardHeaders: true,
  legacyHeaders: false,
  skipSuccessfulRequests: true,    // Don't count successes
});

app.post('/login', loginLimiter, loginHandler);
```

Important: rate-limit on **both** IP *and* target account. IP alone lets an attacker brute-force a known account from a botnet; account-only lets one IP try one password against millions of accounts (password spraying). Use a library like [`rate-limiter-flexible`](https://github.com/animir/node-rate-limiter-flexible) that supports composite keys.

For repeated failures on a single account, escalate: exponential backoff, captcha, then temporary lockout. Don't lock indefinitely — that's a DoS vector.

### 11.10 The Footguns Checklist

Things that will burn you, sorted by how common they are:

- **Storing tokens in `localStorage`** — accessible to any JS, including XSS-injected JS. Use `HttpOnly` cookies.
- **Leaking tokens in URLs** — query parameters end up in server logs, browser history, Referer headers. Tokens go in headers (`Authorization: Bearer ...`) or `HttpOnly` cookies.
- **`alg: none` or alg confusion** — solved by using `jose` and pinning algorithms.
- **Not rotating session IDs on login** — session fixation. Always rotate.
- **Not invalidating sessions on password change** — old sessions remain valid after a compromised password rotation. Invalidate all but the current.
- **Timing-leaky email enumeration** — `if (!user) return error('no user'); else if (!passwordValid) return error('bad password')` lets an attacker enumerate accounts. Always return the same response for unknown user vs. wrong password.
- **Signup/reset response leakage** — same problem. Always return "if an account exists, we sent an email" regardless of whether the account exists.
- **Open redirects on OAuth callbacks** — allow-list exact redirect URIs. No partial matching.
- **CSRF on logout** — yes, attackers can log victims out. Use POST + CSRF token for logout.
- **No expiry on password reset tokens** — set tight expiry (15–60 min) and make them single-use.
- **Long-lived refresh tokens without rotation/revocation** — a stolen refresh token = permanent account takeover.

### 11.11 Operational Concerns

- **Rotating signing keys** — issue with a new `kid`, serve both via JWKS, retire the old `kid` after the maximum token lifetime expires.
- **Secret storage** — `process.env` for low-stakes, KMS/Secrets Manager for serious. Never check into git, never log.
- **Audit logging** — log every auth event (login, logout, password change, role change, MFA enroll/disable, failed-login bursts). Include user ID, IP, user-agent, timestamp, outcome. Ship to an immutable store. Useful for compromise investigation and required by SOC 2.
- **Testing auth** — at minimum, automate happy-path login, MFA, password reset, logout. Add tests for every footgun you've ever burned on. Auth bugs are a category that benefits enormously from regression coverage.

References: [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OAuth 2.0 Security BCP (RFC 9700)](https://datatracker.ietf.org/doc/html/rfc9700)

---

## Phase 12: Auth in Go, Done Right

The same goals, in Go. The shape of the code is different because Go's standard library is much closer to crypto-complete than Node's, but the principles are identical.

### 12.1 Why Go Auth Looks Different

- Most of what you'd reach for a library for in Node is already in `crypto/*` and `golang.org/x/crypto/*`.
- Strong typing eliminates a class of "I passed a string where a buffer was expected" bugs.
- `crypto/subtle` is right there in the standard library — constant-time comparison is one import away.
- Errors are values, not exceptions — much easier to fail-closed correctly.

You'll still reach for libraries for OIDC (`go-oidc`), JWT (`lestrrat-go/jwx`), and high-level frameworks, but the surface is smaller.

### 12.2 Password Storage

Use **Argon2id** from `golang.org/x/crypto/argon2`. It returns raw bytes — you wrap them in your own encoding for storage.

```go
import (
    "crypto/rand"
    "crypto/subtle"
    "encoding/base64"
    "fmt"
    "strings"

    "golang.org/x/crypto/argon2"
)

type argonParams struct {
    memory, time uint32
    threads      uint8
    saltLen, keyLen uint32
}

var defaultParams = &argonParams{
    memory:  64 * 1024, // 64 MB
    time:    3,
    threads: 1,
    saltLen: 16,
    keyLen:  32,
}

func HashPassword(password string) (string, error) {
    salt := make([]byte, defaultParams.saltLen)
    if _, err := rand.Read(salt); err != nil {
        return "", err
    }
    hash := argon2.IDKey([]byte(password), salt,
        defaultParams.time, defaultParams.memory, defaultParams.threads, defaultParams.keyLen)
    return fmt.Sprintf("$argon2id$v=19$m=%d,t=%d,p=%d$%s$%s",
        defaultParams.memory, defaultParams.time, defaultParams.threads,
        base64.RawStdEncoding.EncodeToString(salt),
        base64.RawStdEncoding.EncodeToString(hash)), nil
}

func VerifyPassword(password, encoded string) (bool, error) {
    // Parse encoded format, extract params + salt + expected hash.
    // ... (omitted for brevity; matches the format above)
    computed := argon2.IDKey([]byte(password), salt, params.time, params.memory, params.threads, params.keyLen)
    // Constant-time comparison:
    return subtle.ConstantTimeCompare(computed, expected) == 1, nil
}
```

Alternatives:
- [`alexedwards/argon2id`](https://github.com/alexedwards/argon2id) — wraps the above with a sensible API. Use this rather than rolling your own format if you're starting fresh.
- `golang.org/x/crypto/bcrypt` — if Argon2 isn't available. Same 72-byte input limit caveat as in Node.

### 12.3 Primitives from the Standard Library

```go
import (
    "crypto/hmac"
    "crypto/rand"
    "crypto/sha256"
    "crypto/subtle"
    "encoding/base64"
)

// Generate a random token (32 bytes = 256 bits):
func NewToken() (string, error) {
    b := make([]byte, 32)
    if _, err := rand.Read(b); err != nil {
        return "", err
    }
    return base64.RawURLEncoding.EncodeToString(b), nil
}

// Constant-time comparison:
ok := subtle.ConstantTimeCompare([]byte(presented), []byte(expected)) == 1

// HMAC:
mac := hmac.New(sha256.New, signingKey)
mac.Write(payload)
sig := mac.Sum(nil)

// Verify HMAC (constant time):
if !hmac.Equal(sig, expectedSig) { /* reject */ }
```

**`crypto/rand`** is the CSPRNG. **`math/rand`** is for simulations — never for tokens, keys, salts. The compiler does not stop you from using the wrong one; code review must.

### 12.4 Session Cookies

The `net/http` standard library handles cookies natively. No third-party framework needed.

```go
http.SetCookie(w, &http.Cookie{
    Name:     "__Host-sid",
    Value:    sessionID,
    Path:     "/",
    HttpOnly: true,
    Secure:   true,
    SameSite: http.SameSiteLaxMode,
    MaxAge:   60 * 60 * 24 * 7, // 7 days
})
```

For the store: Redis via [`go-redis`](https://github.com/redis/go-redis), Postgres via `database/sql`, whatever fits the rest of your stack. Sessions are a `(id → user_id, expires_at, csrf_token, ...)` mapping.

Middleware pattern:

```go
func WithSession(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        cookie, err := r.Cookie("__Host-sid")
        if err != nil {
            next.ServeHTTP(w, r)  // No session — anonymous
            return
        }
        sess, err := store.Get(r.Context(), cookie.Value)
        if err != nil || sess.Expired() {
            // Clear the bad cookie, continue anonymous.
            http.SetCookie(w, &http.Cookie{Name: "__Host-sid", MaxAge: -1, Path: "/", Secure: true})
            next.ServeHTTP(w, r)
            return
        }
        ctx := context.WithValue(r.Context(), sessionKey, sess)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

Don't use `gorilla/sessions` for new code — it stores session data in the cookie itself by default (signed but not encrypted), which has the same revocation problem as JWTs. Server-side stores are the safer default.

### 12.5 CSRF

Same principles as Node. Tools:

- [`gorilla/csrf`](https://github.com/gorilla/csrf) — double-submit token middleware, mature and audited.
- [`justinas/nosurf`](https://github.com/justinas/nosurf) — alternative, same pattern.

Or build your own minimal version using `crypto/subtle.ConstantTimeCompare`. The pattern is:

1. On session creation, generate a 32-byte random CSRF token; store in the session.
2. Send the token to the client in a non-`HttpOnly` cookie or in the page HTML.
3. The client sends it back in a custom header on writes.
4. Server compares header against session-stored token in constant time.

`SameSite=Lax` covers most CSRF cases without a token, same as in Node. The token is for cross-site scenarios and defense in depth.

### 12.6 JWTs in Go

Two libraries dominate:

- [`golang-jwt/jwt/v5`](https://github.com/golang-jwt/jwt) — popular, simple API, has had algorithm-confusion CVEs in older versions. v5 is much better — use it.
- [`lestrrat-go/jwx`](https://github.com/lestrrat-go/jwx) — the Go equivalent of `jose`. More opinionated, harder to misuse. Recommended for new code.

Example with `jwx`:

```go
import (
    "github.com/lestrrat-go/jwx/v2/jwa"
    "github.com/lestrrat-go/jwx/v2/jwk"
    "github.com/lestrrat-go/jwx/v2/jwt"
)

// Signing:
tok, _ := jwt.NewBuilder().
    Issuer("https://auth.example.com").
    Audience([]string{"https://api.example.com"}).
    Subject(userID).
    IssuedAt(time.Now()).
    Expiration(time.Now().Add(15 * time.Minute)).
    JwtID(uuid.NewString()).
    Build()
signed, _ := jwt.Sign(tok, jwt.WithKey(jwa.EdDSA, privateKey))

// Verifying:
jwks, _ := jwk.NewCache(ctx)
jwks.Register("https://auth.example.com/.well-known/jwks.json")
parsed, err := jwt.Parse(token,
    jwt.WithKeySet(jwks.LookupKeySet("https://auth.example.com/.well-known/jwks.json")),
    jwt.WithIssuer("https://auth.example.com"),
    jwt.WithAudience("https://api.example.com"),
    jwt.WithValidate(true),
)
```

Same non-negotiables as Node: pin algorithm (via the `jwt.WithKey` / `jwt.WithKeySet` choice), validate `iss`/`aud`, short expiry, refresh tokens for long sessions.

### 12.7 OIDC

Use [`coreos/go-oidc`](https://github.com/coreos/go-oidc) (now maintained as `go-oidc/v3`). Wraps the OIDC discovery + ID token verification correctly.

```go
import (
    "github.com/coreos/go-oidc/v3/oidc"
    "golang.org/x/oauth2"
)

provider, _ := oidc.NewProvider(ctx, "https://accounts.google.com")
oauthConfig := &oauth2.Config{
    ClientID:     os.Getenv("GOOGLE_CLIENT_ID"),
    ClientSecret: os.Getenv("GOOGLE_CLIENT_SECRET"),
    Endpoint:     provider.Endpoint(),
    RedirectURL:  "https://example.com/callback",
    Scopes:       []string{oidc.ScopeOpenID, "email", "profile"},
}
verifier := provider.Verifier(&oidc.Config{ClientID: oauthConfig.ClientID})

// On login start: generate state + PKCE verifier; store in session.
codeVerifier := oauth2.GenerateVerifier()
state := generateState()
url := oauthConfig.AuthCodeURL(state, oauth2.S256ChallengeOption(codeVerifier))

// On callback:
oauth2Token, _ := oauthConfig.Exchange(ctx, code, oauth2.VerifierOption(codeVerifier))
rawIDToken, _ := oauth2Token.Extra("id_token").(string)
idToken, _ := verifier.Verify(ctx, rawIDToken)

var claims struct {
    Email         string `json:"email"`
    EmailVerified bool   `json:"email_verified"`
    Name          string `json:"name"`
}
_ = idToken.Claims(&claims)
```

Same rules: PKCE on every flow, validate state, exact-match redirect URI allow-list.

### 12.8 The Go-Specific Footguns

- **`math/rand` vs. `crypto/rand`** — easy to import the wrong one. `crypto/rand.Read` for security; never `math/rand`.
- **`time.Now()` for token expiry comparisons is fine, but `time.Since()` returns a duration that *can be negative* if clocks drift.** Be explicit about what "expired" means.
- **`subtle.ConstantTimeCompare` returns 1/0, not bool.** Easy to misread.
- **The old `dgrijalva/jwt-go` library is unmaintained** and had algorithm-confusion CVEs. Use the v5 fork or `jwx`.
- **`encoding/json` decodes into structs case-insensitively by default**. For security-sensitive parsing of, e.g., a JWT claim manually, prefer strict decoders or explicit field tags.
- **The standard `http` server doesn't enforce TLS** — you have to call `ListenAndServeTLS`. In production, terminate TLS at a reverse proxy (or use a Caddy-style server).

References: [Go's `crypto/*` packages](https://pkg.go.dev/crypto), [`golang.org/x/crypto`](https://pkg.go.dev/golang.org/x/crypto), [`go-oidc`](https://github.com/coreos/go-oidc)

---

## Phase 13: Practical Recipes

Short, prescriptive recipes for the applied crypto tasks that come up most often. Each pulls from primitives covered earlier.

### 13.1 Webhook Signing and Verification

Almost every webhook provider (Stripe, GitHub, Slack, Twilio) uses HMAC. The pattern, generically:

**Sender side** (provider):
```
timestamp = current_unix_seconds()
signature = HMAC-SHA256(secret, f"{timestamp}.{raw_body}")
send headers:
  X-Webhook-Timestamp: {timestamp}
  X-Webhook-Signature: {hex(signature)}
```

**Receiver side** (your service):
```js
// Node:
import { createHmac, timingSafeEqual } from 'node:crypto';

function verifyWebhook(rawBody, timestamp, signature, secret) {
  // 1. Reject ancient timestamps (replay protection):
  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (age > 300) return false;     // 5-minute tolerance

  // 2. Recompute the expected signature:
  const expected = createHmac('sha256', secret)
    .update(`${timestamp}.${rawBody}`)
    .digest();
  const provided = Buffer.from(signature, 'hex');

  // 3. Constant-time compare:
  if (expected.length !== provided.length) return false;
  return timingSafeEqual(expected, provided);
}
```

```go
// Go:
func VerifyWebhook(rawBody []byte, timestamp, signature, secret string) bool {
    ts, err := strconv.ParseInt(timestamp, 10, 64)
    if err != nil || math.Abs(float64(time.Now().Unix()-ts)) > 300 {
        return false
    }
    mac := hmac.New(sha256.New, []byte(secret))
    fmt.Fprintf(mac, "%s.", timestamp)
    mac.Write(rawBody)
    expected := mac.Sum(nil)
    provided, err := hex.DecodeString(signature)
    if err != nil {
        return false
    }
    return hmac.Equal(expected, provided)
}
```

The traps:

- **You must verify against the raw body**, before JSON parsing. Frameworks that auto-parse and re-serialize will change byte order, whitespace, etc., and your signature will not match. Capture the raw body in middleware before parsing.
- **Include the timestamp in what you sign**, and reject ancient timestamps. Without this, an attacker who captures a valid webhook can replay it forever.
- **Constant-time comparison**, always. `hmac.Equal` in Go does this; `timingSafeEqual` in Node does this.
- **Use the provider's library if they ship one** (`stripe.webhooks.constructEvent`, `github-webhook-handler`). They handle the edge cases.

### 13.2 Envelope Encryption with KMS

The standard pattern for encrypting data at rest in cloud environments. The actual encryption keys never leave the KMS; you just borrow short-lived *data encryption keys* (DEKs) from it.

The pattern:

1. Ask KMS to generate a **data key**. KMS returns *both* the plaintext DEK *and* an encrypted-by-KMS version of the same DEK.
2. Use the plaintext DEK to encrypt your data with AES-GCM (or your AEAD of choice).
3. **Throw away the plaintext DEK.** Store the encrypted DEK alongside the ciphertext.
4. To decrypt: ask KMS to decrypt the stored encrypted-DEK. KMS returns the plaintext DEK. Decrypt the data. Throw away the plaintext DEK again.

Why this is better than "just encrypt with KMS directly":
- KMS has request quotas. With envelope encryption, you only call KMS once per file (or per cache window), not on every byte.
- Large data: KMS can't directly encrypt more than 4 KB. DEKs let you encrypt arbitrary-sized blobs.
- You can cache the plaintext DEK in memory for a short window if performance matters, with bounded risk.

**AWS KMS example** (Node, with the `@aws-sdk/client-kms` package):

```js
import { KMSClient, GenerateDataKeyCommand, DecryptCommand } from '@aws-sdk/client-kms';
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';

const kms = new KMSClient({});

async function encryptBlob(plaintext, keyId) {
  // 1. Get a DEK from KMS:
  const { Plaintext: dek, CiphertextBlob: wrappedDek } = await kms.send(
    new GenerateDataKeyCommand({ KeyId: keyId, KeySpec: 'AES_256' })
  );

  // 2. Encrypt the data with AES-256-GCM:
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', Buffer.from(dek), iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const authTag = cipher.getAuthTag();

  // 3. Throw away the plaintext DEK (Node will GC it; for paranoia, zero the buffer).
  Buffer.from(dek).fill(0);

  // 4. Store: { wrappedDek, iv, authTag, ciphertext }
  return { wrappedDek, iv, authTag, ciphertext };
}

async function decryptBlob({ wrappedDek, iv, authTag, ciphertext }) {
  // 1. Ask KMS to unwrap the DEK:
  const { Plaintext: dek } = await kms.send(
    new DecryptCommand({ CiphertextBlob: wrappedDek })
  );

  // 2. Decrypt the data:
  const decipher = createDecipheriv('aes-256-gcm', Buffer.from(dek), iv);
  decipher.setAuthTag(authTag);
  const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]);

  // 3. Throw away the plaintext DEK.
  Buffer.from(dek).fill(0);

  return plaintext;
}
```

The traps:

- **IV reuse**: each encryption needs a fresh random IV. Don't be tempted to derive it.
- **`setAuthTag` before `decipher.update`** in Node. The auth tag is *checked* on `decipher.final()` — if the tag is wrong, `final()` throws. Handle that error properly; never ignore it.
- **Audit logs**: every KMS Decrypt call shows up in CloudTrail / Cloud Audit Logs. This is a feature — you have a forensic record of every data access. Don't filter it out.
- **Per-tenant keys**: in multi-tenant systems, give each tenant their own KMS key. Lets you "delete a tenant" cryptographically by deleting the key, even if their data is still in cold backups.
- **AWS Encryption SDK** ([`@aws-crypto/client-node`](https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/javascript.html)) does all of the above for you and handles caching correctly. Prefer it over hand-rolled envelope encryption.

The same pattern applies to GCP KMS, Azure Key Vault, and HashiCorp Vault Transit — the API calls differ but the structure is identical.

### 13.3 File and Secret Encryption with `age`

[`age`](https://github.com/FiloSottile/age) is a modern file encryption tool — think "what PGP would be if designed today." Single primitive (X25519 + ChaCha20-Poly1305), tiny CLI, no key servers, no configuration. Use it for:

- Encrypting backups before uploading to S3/GCS.
- Encrypting secrets-in-git via [`sops`](https://github.com/getsops/sops) (which uses `age` as one of its key backends).
- Securely sharing one-off files with teammates.
- Encrypting build artifacts at rest.

**Generating a key**:
```bash
age-keygen -o key.txt
# Output: a public key (age1...) and a private identity (AGE-SECRET-KEY-1...).
```

**Encrypting a file**:
```bash
# To a recipient's public key:
age -r age1qz...recipient_pubkey... -o secret.enc secret.txt

# To multiple recipients (each can decrypt independently):
age -r age1abc... -r age1def... -o team-secret.enc secret.txt

# Password-based (for storage you want to unlock with a passphrase):
age -p -o secret.enc secret.txt
```

**Decrypting**:
```bash
age -d -i key.txt -o secret.txt secret.enc
```

**SSH key support** — `age` can encrypt to an existing `ssh-ed25519` public key. Very useful for "send this to the recipient using only their existing GitHub SSH key":

```bash
# Fetch the recipient's SSH keys from GitHub:
curl https://github.com/alice.keys | grep ssh-ed25519 > alice.pub

# Encrypt to them:
age -R alice.pub -o for-alice.enc message.txt
```

**Programmatic use in Go**:
```go
import "filippo.io/age"

// Encrypt:
identity, _ := age.ParseX25519Identity("AGE-SECRET-KEY-1...")
recipient := identity.Recipient()
out, _ := os.Create("secret.enc")
w, _ := age.Encrypt(out, recipient)
io.WriteString(w, "hello world")
w.Close()

// Decrypt:
in, _ := os.Open("secret.enc")
r, _ := age.Decrypt(in, identity)
io.Copy(os.Stdout, r)
```

**`sops` + `age` for secrets-in-git**: `sops` encrypts only the *values* in YAML/JSON files, leaving keys plaintext. This means PRs show "the password changed" without revealing values, and diffs remain meaningful. Configure once via `.sops.yaml`, then `sops -e file.yaml > file.enc.yaml`. Pair with the [SOPS GitOps operator](https://github.com/getsops/sops) for cluster secrets.

The trap: `age` files are not authenticated to a specific sender (the recipient learns nothing about who encrypted). If you need authenticity, sign separately. For most use cases ("encrypt my own backups, decrypt them later") this doesn't matter.

References: [age spec](https://github.com/C2SP/C2SP/blob/main/age.md), [sops docs](https://github.com/getsops/sops)

---

## Phase 14: Post-Quantum & Modern Landscape

(See Phase 10 above for the full treatment — this is the same content, kept here as the natural ending phase. In a future revision this section may consolidate; for now the placement honors the "applied" phases between fundamentals and PQ.)

If you only remember three things about PQ:

1. **Symmetric crypto is mostly fine.** AES-256 against a quantum adversary gives 128-bit security via Grover.
2. **Public-key crypto needs to migrate.** RSA, DH, ECDSA, Ed25519 all break under Shor's algorithm on a sufficiently large quantum computer.
3. **Hybrid is shipping today.** Cloudflare, Chrome, OpenSSH, Signal already deploy hybrid (classical + PQ) protocols. The classical leg keeps you safe today; the PQ leg protects against "harvest now, decrypt later."

The standardized PQ algorithms to know: **ML-KEM** (key exchange, was Kyber), **ML-DSA** (signature, was Dilithium), **SLH-DSA** (conservative hash-based signature, was SPHINCS+).

---

## Mastery Checklist

You're solid on applied crypto when you can, without looking anything up:

- Pick the right primitive for confidentiality, integrity, authenticity, and non-repudiation independently.
- Explain why ECB is broken, why CBC is dangerous, and why AEAD is the right default.
- Recognize the nonce-reuse footgun in CTR-mode constructions (including GCM) and pick a misuse-resistant alternative (GCM-SIV, XChaCha20-Poly1305).
- Use HMAC correctly — including constant-time verification.
- Hash a password with Argon2id tuned to your hardware budget.
- Generate cryptographic randomness without reaching for `Math.random()`.
- Validate a JWT correctly — pinned algorithm, validated `iss`/`aud`/`exp`, JWKS rotation.
- Configure a session cookie with `__Host-`, `HttpOnly`, `Secure`, `SameSite=Lax`, and explain why each matters.
- Implement webhook signature verification with replay protection.
- Describe envelope encryption end-to-end and explain why it's better than directly calling KMS.
- Read a TLS handshake at the wire level and name each step.
- Identify SIDE channels (especially timing) and write constant-time code where it matters.
- Justify a key management strategy (KMS, secret manager, env var) for a given threat model.

---

## Recommended Reading Path

1. **[Cryptography Engineering](https://www.schneier.com/books/cryptography-engineering/)** (Ferguson, Schneier, Kohno) — the standard textbook. Read end to end. Slow read.
2. **[Real-World Cryptography](https://www.manning.com/books/real-world-cryptography)** (David Wong) — modern, practical, opinionated. Read after Cryptography Engineering as the application layer.
3. **[Serious Cryptography](https://nostarch.com/seriouscrypto)** (Jean-Philippe Aumasson) — concise, deeply opinionated, full of footgun warnings.
4. **[The Cryptopals Crypto Challenges](https://cryptopals.com/)** — hands-on. Implement each attack. This will teach you more about real-world crypto than any book.
5. **The IETF specs themselves** — RFC 8446 (TLS 1.3), RFC 9106 (Argon2), RFC 8439 (ChaCha20-Poly1305), RFC 8725 (JWT BCP), RFC 9700 (OAuth 2.0 Security BCP). The specs are surprisingly readable once you have the fundamentals.
6. **[Latacora's cryptographic right answers](https://latacora.singles/2018/04/03/cryptographic-right-answers.html)** — short, opinionated, current. Bookmark it.
7. **[Real World Crypto symposium talks](https://rwc.iacr.org/)** — the annual conference where industry crypto problems get aired. YouTube has most recent years.

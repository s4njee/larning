# Advanced Rust Study Guide

A depth-first guide to the Rust that senior work actually demands: **the type-system machinery, concurrency, async and the runtime model, unsafe/FFI, and production engineering**. It is the sequel to [Rust for Python Developers](RUST_FOR_PYTHON_DEVS.md) — this guide assumes you already own the fundamentals (ownership and borrowing, `Result`/`Option`, traits, enums, pattern matching, `cargo`) and goes after the parts that take Rust from "I can write a CLI" to "I can build a correct concurrent service and explain why it's correct."

The throughline: in Python you fight the GIL and in Go you fight the garbage collector, but in Rust **the compiler makes you prove your concurrency is sound before it runs**. Async, `Send`/`Sync`, `Pin`, lifetimes, and `unsafe` are all the same story — *encode the invariant in the type system so violations don't compile*. Each "hard" topic in this guide is that one move at a different layer, and once you see it, the language stops feeling like a pile of special cases. The corollary that shapes how you should read: when the compiler rejects your concurrent design, it is almost never being pedantic — it has found a bug that other languages would have let you ship.

Every section includes compilable code, embedded in the explanation rather than substituting for it. Primary references throughout: [The Rust Programming Language](https://doc.rust-lang.org/book/), the [Rustonomicon](https://doc.rust-lang.org/nomicon/) (unsafe), the [Async Book](https://rust-lang.github.io/async-book/), Mara Bos's [*Rust Atomics and Locks*](https://marabos.nl/atomics/) (free online, and the best book on Part 5's material), and the [Tokio tutorial](https://tokio.rs/tokio/tutorial).

---

## Table of Contents

1. [Part 1 — The Type System as a Proof Engine](#part-1--the-type-system-as-a-proof-engine)
2. [Part 2 — Lifetimes, Variance, and the Shape of Borrowing](#part-2--lifetimes-variance-and-the-shape-of-borrowing)
3. [Part 3 — Memory Layout and Smart Pointers](#part-3--memory-layout-and-smart-pointers)
4. [Part 4 — Threads, Send/Sync, and Data Parallelism](#part-4--threads-sendsync-and-data-parallelism)
5. [Part 5 — Atomics and the Memory Model](#part-5--atomics-and-the-memory-model)
6. [Part 6 — Async I: The Model](#part-6--async-i-the-model)
7. [Part 7 — Async II: Tokio in Production](#part-7--async-ii-tokio-in-production)
8. [Part 8 — Unsafe Rust](#part-8--unsafe-rust)
9. [Part 9 — FFI: Crossing the C Boundary](#part-9--ffi-crossing-the-c-boundary)
10. [Part 10 — Performance Engineering](#part-10--performance-engineering)
11. [Part 11 — Errors, Testing, and Verification](#part-11--errors-testing-and-verification)
12. [Part 12 — Macros](#part-12--macros)
13. [Part 13 — Production Service Patterns](#part-13--production-service-patterns)
14. [Capstone Projects](#capstone-projects)
15. [Study Methodology](#study-methodology)

---

## Part 1 — The Type System as a Proof Engine

Everything advanced in Rust routes through the trait system, so this is where the guide starts — not with a feature tour, but with the handful of mechanisms that decide how every API you write will compile, perform, and compose.

### 1.1 Static vs. dynamic dispatch: the decision underneath every API

Rust has exactly two ways to turn a trait call into machine code, and choosing between them is the most common design decision in the language. **Monomorphization** — the generics path — stamps out a specialized copy of your function for every concrete type it's used with, resolved entirely at compile time. **Dynamic dispatch** — the [`dyn Trait`](https://doc.rust-lang.org/book/ch17-02-trait-objects.html) path — compiles one copy that looks the method up in a vtable at run time.

```rust
trait Shape {
    fn area(&self) -> f64;
}

struct Circle { r: f64 }
impl Shape for Circle {
    fn area(&self) -> f64 { std::f64::consts::PI * self.r * self.r }
}

// Static dispatch: monomorphized per concrete S, fully inlinable, zero runtime cost.
fn total_area<S: Shape>(shapes: &[S]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}

// Dynamic dispatch: ONE compiled function, a vtable lookup per call — but it can
// hold a heterogeneous mix of shapes behind pointers.
fn total_area_dyn(shapes: &[Box<dyn Shape>]) -> f64 {
    shapes.iter().map(|s| s.area()).sum()
}
```

The mental model that makes the trade-off predictable: a generic function is a *template* the compiler stamps out; a `dyn` value is a **fat pointer** — two machine words, a data pointer plus a vtable pointer (Part 3 returns to fat pointers as a layout fact). From that, everything follows. Monomorphization gives the optimizer a concrete type to inline through — this is why iterator chains compile to tight loops — at the cost of compile time and binary size (every instantiation is more code, and a heavily-generic crate can bloat both badly enough that *de*-generifying internals behind a `dyn` boundary is a real optimization). Dynamic dispatch costs an indirect call and blocks inlining, but compiles once, erases the type (so a `Vec<Box<dyn Shape>>` can mix circles and squares), and keeps trait machinery out of your struct signatures — a field of type `Box<dyn Database>` doesn't force a generic parameter onto every type that contains it.

The practical defaults: **generics for hot paths and known-at-call-site types; `dyn` for heterogeneous collections, plugin-style seams, and keeping public APIs and compile times sane.** And one idiom worth knowing by name — the *hybrid*: take generics in the public signature for ergonomics, immediately convert to `dyn` internally to avoid monomorphizing your whole implementation per caller type (`fn run(f: impl FnMut() + 'static)` calling `run_dyn(Box::new(f))`). The standard library does this in `std::thread::spawn`'s internals; it's the professional compromise between the two costs.

Two pieces of fine print complete the picture. **Dyn-compatibility** (long called "object safety", [reference](https://doc.rust-lang.org/reference/items/traits.html#dyn-compatibility)): a trait is only usable as `dyn Trait` if its methods don't return `Self` by value and aren't generic — both would require knowing the concrete type, which is exactly what `dyn` erased. The error ("the trait cannot be made into an object") confuses everyone once; the standard fixes are splitting the offending methods into a separate trait, or the `where Self: Sized` escape hatch that removes a method from the `dyn` vtable. And **`impl Trait`** is two features wearing one syntax: in *argument* position it's sugar for a generic parameter; in *return* position it means "one concrete type I decline to name" — which is not dynamic dispatch but type inference, and is the only way to return closures and async blocks, whose types are unnameable compiler inventions.

### 1.2 Associated types vs. generic parameters: how many implementations?

The question that decides between `trait Iterator { type Item; }` and `trait From<T>` is always the same: **for a given implementing type, how many implementations should exist?** An associated type says *one* — a type iterates over one `Item` type, a future resolves to one `Output`; the relationship is a function from implementer to type, and users never have to annotate it. A generic parameter says *many* — `String` implements `From<&str>` *and* `From<char>` *and* `From<Cow<str>>`, and the compiler selects among them per call site.

Get this wrong and the pain is immediate: model `Iterator` with a generic parameter and every bound becomes `I: Iterator<u32>` with inference ambiguities everywhere ("which Iterator impl did you mean?"); model `From` with an associated type and a type could only ever convert from one source. The standard library's choices are a curriculum in themselves — read [`Add`](https://doc.rust-lang.org/std/ops/trait.Add.html) (generic in the right-hand side, associated in the output: you can add many types to a `Duration`, but `Duration + Duration` has exactly one result type) until the pattern is reflexive.

**Generic associated types (GATs)**, stable since 1.65, complete the system: an associated type that is itself generic over a lifetime or type. The canonical unlock is the **lending iterator** — an iterator whose items borrow from the iterator itself:

```rust
trait LendingIterator {
    type Item<'a> where Self: 'a;          // the GAT: Item borrows from &mut self
    fn next(&mut self) -> Option<Self::Item<'_>>;
}

// A windows-iterator over a slice that yields overlapping &[T] views — impossible
// to express with std Iterator (each item would need to borrow from the iterator,
// but Iterator::Item can't mention the &mut self lifetime).
struct Windows<'s, T> { slice: &'s [T], size: usize, pos: usize }

impl<'s, T> LendingIterator for Windows<'s, T> {
    type Item<'a> = &'a [T] where Self: 'a;
    fn next(&mut self) -> Option<&[T]> {
        let w = self.slice.get(self.pos..self.pos + self.size)?;
        self.pos += 1;
        Some(w)
    }
}
```

You won't write GATs weekly, but you will *read* them — they're load-bearing in async traits' desugaring and across the ecosystem's zero-copy parsing crates — and knowing the lending-iterator example by heart converts an opaque feature into one sentence: *GATs let an associated type depend on the lifetime of the borrow that produced it.* ([RFC 1598](https://rust-lang.github.io/rfcs/1598-generic_associated_types.html), [stabilization post](https://blog.rust-lang.org/2022/10/28/gats-stabilization.html).)

### 1.3 Coherence, the orphan rule, and the newtype escape

Rust enforces **coherence**: for any (type, trait) pair there is at most one implementation in the universe, so trait resolution never depends on which crates happen to be linked. The enforcement mechanism is the **orphan rule** — you may `impl Trait for Type` only if the trait or the type is local to your crate ([reference](https://doc.rust-lang.org/reference/items/implementations.html#orphan-rules)). This is why you cannot `impl serde::Serialize for chrono::DateTime` in your application: both halves are foreign, and if two crates did that with different behavior, the program's meaning would depend on link order.

The standard escape is the **newtype pattern**: wrap the foreign type in a local tuple struct and implement away. The wrapper is zero-cost (same layout, Part 3), and `Deref` or delegated methods recover ergonomics where appropriate:

```rust
struct Meters(f64);                       // local type — implement anything for it

impl std::fmt::Display for Meters {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} m", self.0)
    }
}
```

Newtypes earn a second, bigger job in serious codebases: **making invariants unrepresentable**. `UserId(u64)` and `OrderId(u64)` cannot be swapped at a call site even though both are u64s underneath; `Validated<Email>` can only be constructed by the validation function. This is the cheapest formal method in industry — the type system refusing to compile confused code — and the natural segue to its maximal form, the **typestate pattern**: encode a state machine's states as types so that invalid transitions are not runtime errors but missing methods (`Connection<Idle>` has `connect()`, only `Connection<Established>` has `send()`; the builder pattern that won't `build()` until required fields are set is the everyday instance). You don't need typestate often; you need to *recognize* it, because the best Rust APIs you'll consume (embedded HALs, protocol libraries) are built from it.

### 1.4 Const generics and compile-time evaluation

Types can be parameterized by *values*: `[T; N]` was always magic, and since 1.51 your own types can do it — `struct Matrix<const R: usize, const C: usize>([f32; R * C])`-style APIs where dimension mismatches are compile errors rather than runtime panics ([reference](https://doc.rust-lang.org/reference/items/generics.html#const-generics)). Combined with `const fn` — functions executable at compile time, an ever-growing subset of the language — you get lookup tables computed at build, sizes checked before run, and parsers that reject invalid static configuration during compilation. The discipline: const generics shine for *small, structural* values (sizes, flags); resist encoding business data into types — monomorphization multiplies code per distinct value, and the error messages multiply with it.

### 1.5 Closures: structs the compiler writes for you

A closure is an anonymous struct holding its captured variables as fields, plus an implementation of one of three traits — and *which* trait is determined by **how the body uses the captures**: [`Fn`](https://doc.rust-lang.org/std/ops/trait.Fn.html) (reads them: captures by `&`), `FnMut` (mutates them: by `&mut`), `FnOnce` (consumes them: by value). Every `Fn` is also `FnMut` is also `FnOnce` — calling through a shared borrow is strictly more permissive than consuming — so the API rule is to **bound with the weakest trait that works**: `FnOnce` if you call once, `FnMut` for a loop, `Fn` only if you genuinely call through a shared reference.

```rust
// `impl Fn` returns the closure by value; `move` makes it own `x` so it can outlive this frame.
fn make_adder(x: i32) -> impl Fn(i32) -> i32 {
    move |y| x + y
}

fn main() {
    let add5 = make_adder(5);
    assert_eq!(add5(10), 15);

    // FnMut: mutates captured state between calls.
    let mut count = 0;
    let mut tick = || { count += 1; count };
    assert_eq!((tick(), tick()), (1, 2));

    // FnOnce: moves a capture out — callable exactly once, enforced at compile time.
    let name = String::from("rust");
    let consume = move || name;
    let _owned: String = consume();    // a second call would not compile
}
```

Two details carry the rest of the guide. First, **`move` is the bridge to concurrency**: `thread::spawn` and `tokio::spawn` require the closure to own everything it touches, because the spawning stack frame may be gone before the closure runs — that's the `'static` bound made concrete (Part 2), and it's why spawn closures are almost always `move`. Second, **an `async` block is the same compiler trick** — a generated struct holding captured state, implementing `Future` instead of `Fn` — which is why every question you learn to ask about a closure (*what does it capture? by value or reference? is it `Send`?*) will be asked again, verbatim, about futures in Parts 6–7. Closures are the rehearsal; async is the performance.

```quiz
Q: Why do iterator chains compile to tight loops while a Vec of Box<dyn Shape> pays per call?
- [ ] Iterators are implemented in the compiler, not the library
- [x] Generics monomorphize — the optimizer sees concrete types and inlines through them; dyn dispatch is an indirect vtable call that blocks inlining
- [ ] Box adds a null check on every access
- [ ] Trait objects are reference-counted
> Monomorphization stamps out a specialized copy per concrete type (paying compile time and binary size); dyn compiles once and erases the type behind a fat pointer. Defaults: generics for hot paths, dyn for heterogeneous collections and API seams — and the hybrid (generic signature, dyn internals) when both costs bite.

Q: Iterator uses an associated type (type Item) but From uses a generic parameter (From<T>). What question decides between them?
- [ ] Which one compiles faster
- [x] How many implementations should exist per implementing type — associated type means exactly one; generic parameter means many, selected per call site
- [ ] Whether the trait needs to be dyn-compatible
- [ ] Whether the type is Sized
> A type iterates over one Item, so users never annotate it; String converts From<&str> and From<char> and more, so the parameter selects among impls. Get it backwards and you either lose flexibility or drown in inference ambiguity.

Q: You can't impl serde::Serialize for chrono::DateTime in your app crate. Why, and what's the escape?
- [ ] DateTime is #[non_exhaustive]; ask upstream for support
- [x] The orphan rule — both trait and type are foreign, and two crates doing this could give one program two conflicting impls; wrap DateTime in a local newtype and implement on that
- [ ] serde traits are sealed
- [ ] You can — it just needs unsafe
> Coherence guarantees at most one impl per (type, trait) pair in the universe, so resolution never depends on link order. The newtype is zero-cost (same layout) — and earns a second job making invariants unrepresentable (UserId(u64) vs OrderId(u64)).

Q: Why are closures passed to thread::spawn and tokio::spawn almost always `move` closures?
- [ ] move closures run faster
- [x] The spawned code may outlive the spawning stack frame, so the 'static bound demands the closure own its captures rather than borrow doomed locals
- [ ] Non-move closures can't implement FnOnce
- [ ] The runtime copies non-move captures anyway
> Borrowed captures would dangle once the spawning frame returns. move makes the closure self-sufficient — and the same capture analysis (what's captured? is it Send?) is exactly what you'll re-run on async blocks, which are the same compiler-generated-struct trick.
```

---

## Part 2 — Lifetimes, Variance, and the Shape of Borrowing

You know elision and `&'a T`. The advanced surface is small but load-bearing: `'static` as a bound, higher-ranked bounds, variance, and the one thing lifetimes *cannot* express — which is precisely the thing async needs (and Part 6's `Pin` exists to recover).

### 2.1 Lifetimes are proofs, not annotations

The reframe that dissolves most lifetime fights: lifetime parameters don't *do* anything — they are the vocabulary in which the compiler states its proof that no reference outlives its referent. When a signature won't compile, the compiler isn't asking for different annotations; it's telling you the ownership story your annotations claim is not the one your code enacts. The productive response is never "sprinkle `'static`"; it's to ask *who owns this data, and how long do I actually need to view it?* — and then make the signature say that. (Reference: [the Nomicon's lifetime chapters](https://doc.rust-lang.org/nomicon/lifetimes.html), which are written exactly in this proofs-first spirit.)

Modern borrow checking is **non-lexical** (NLL): a borrow ends at its *last use*, not at the closing brace. This is why most "fighting the borrow checker" folklore from pre-2018 posts no longer reproduces — and why, when you do hit a residual limitation (conditional returns of borrows from a match are the famous one, addressed by the in-progress Polonius work), the right move is a small restructure rather than a fight.

### 2.2 `'static`: the most misread bound in Rust

`T: 'static` does **not** mean "T lives forever." It means **"T contains no non-`'static` borrows"** — T is self-sufficient: either it owns all its data (a `String`, a `Vec<u8>`, an `Arc<Config>`) or any references inside it point at process-lifetime data (string literals). `thread::spawn` and `tokio::spawn` require it because a spawned task may run *arbitrarily later*, after the spawning frame's locals are gone; the bound is the compiler's way of saying "hand me something that doesn't dangle, however long I hold it." An owned `String` created two milliseconds ago satisfies `'static` perfectly. Misreading this bound as "must be a global" sends people to `Box::leak` and `lazy_static` contortions when the actual fix was a `.clone()` or an `Arc`.

### 2.3 Higher-ranked trait bounds: "for every lifetime"

Sometimes a bound must hold not for one lifetime the caller picks, but for *all of them*. That's a **higher-ranked trait bound** (HRTB), written `for<'a>` ([Nomicon](https://doc.rust-lang.org/nomicon/hrtb.html)):

```rust
// F must accept a borrow of ANY duration — including one created inside `apply`,
// which no single caller-chosen lifetime could name.
fn apply<F>(f: F)
where
    F: for<'a> Fn(&'a str) -> &'a str,
{
    let owned = String::from("hello world");
    println!("{}", f(&owned));      // `owned` lives only inside apply — and that's fine
}

fn main() {
    apply(|s| s.split(' ').next().unwrap());
}
```

You mostly *encounter* HRTBs rather than write them — closure bounds over references elide to them automatically, and serde's `Deserialize<'de>` machinery is built on them — but recognizing `for<'a>` in an error message converts a wall of text into one idea: *the function demands a callback that works for every lifetime, and yours only works for one.*

### 2.4 Variance: why `&mut` is stricter than `&`

Variance answers a question you've been benefiting from without asking: when is `Thing<'long>` usable where `Thing<'short>` is expected? For shared references, always — `&'long T` **coerces** to `&'short T` (covariance: shortening a view is harmless). For mutable references, the lifetime is still covariant but the *pointee type* is **invariant** — `&mut Vec<&'long str>` is *not* usable as `&mut Vec<&'short str>` — and the reason is an actual exploit: if it were allowed, the callee could *write* a short-lived reference into your long-lived vector, which you'd later read as long-lived. Dangling pointer, by type-system sleight of hand. (The [Nomicon's variance table](https://doc.rust-lang.org/nomicon/subtyping.html) is the reference; `Cell<T>` and friends are likewise invariant for the same writes-allowed reason.)

You need variance actively in two situations: deciphering the otherwise-mystifying class of errors where a `&mut` nested borrow "should obviously work" (it shouldn't — now you know the attack it prevents), and choosing `PhantomData` markers when building unsafe abstractions (Part 8), where *you* declare your raw-pointer type's variance and the soundness of client code rides on the choice.

### 2.5 The wall: self-reference, and why it matters more than it looks

One ownership shape is flatly inexpressible in safe Rust: **a struct holding a reference into itself**. The borrow checker has no vocabulary for "field b borrows from field a of the same value," and there's a hard mechanical reason beneath the syntactic one — Rust values are *movable by memcpy, always*; a move would copy the struct while its internal pointer kept aiming at the old address. Every workaround is really a redesign: store indices instead of references, split the owner and the view into separate structs, or use `Rc` to make the "self"-reference an ordinary shared owner.

File this limitation carefully rather than as trivia, because it is **the** reason async Rust has `Pin`: an `async fn`'s generated state machine routinely holds borrows across `.await` points — references into its own captured locals — making it exactly the self-referential struct safe Rust forbids. The language's solution was not to allow self-reference generally, but to make *not-moving* a checkable promise. That story is Part 6.2; the groundwork is laid here.

```quiz
Q: tokio::spawn requires T: 'static. What does that bound actually demand?
- [ ] T must be stored in a global or leaked
- [x] T contains no non-'static borrows — it's self-sufficient, owning its data or referencing only process-lifetime data; a freshly created String qualifies
- [ ] T must live for the entire program
- [ ] T must be Copy
> The most misread bound in Rust: it's about what T *contains*, not how long it lives. The task may run arbitrarily late, so it can't hold borrows of the spawning frame. The fix is a clone or an Arc — not Box::leak gymnastics.

Q: Why is `&mut Vec<&'long str>` NOT usable where `&mut Vec<&'short str>` is expected, when the same shortening is fine for shared references?
- [ ] Mutable references can't be coerced at all
- [x] Through &mut the callee could *write* a short-lived reference into your long-lived Vec, which you'd later read as long-lived — a dangling pointer by type-system sleight of hand
- [ ] Vec is invariant because it owns heap memory
- [ ] 'long and 'short must be declared covariant explicitly
> Shared references are covariant (shortening a read-only view is harmless); &mut's pointee is invariant because writes flow the other way. The "obviously fine" nested-borrow error is the compiler blocking a real exploit.

Q: Why does safe Rust flatly forbid a struct holding a reference into itself?
- [ ] The borrow checker limit is temporary and Polonius will allow it
- [x] Every Rust value must survive being moved by memcpy — a move would copy the struct while its internal pointer kept aiming at the old address
- [ ] Self-references create reference-count cycles
- [ ] It's allowed with #[repr(C)]
> There's no vocabulary for "field b borrows field a of the same value" because movability is unconditional. Workarounds are redesigns (indices, owner/view split, Rc). And this exact wall is why async needs Pin: futures hold borrows across .await — self-references — so immobility had to become a checkable promise.
```

---

## Part 3 — Memory Layout and Smart Pointers

Senior Rust work means knowing what your types *are* in memory — both because performance lives there (Part 10) and because unsafe code (Part 8) is downstream of layout facts.

### 3.1 What types look like

The compiler lays out a default (`repr(Rust)`) struct however it likes — typically sorting fields to minimize padding, which is why field order in source doesn't reliably predict layout and why FFI structs need `#[repr(C)]` (Part 9). The sizes worth knowing cold: references and `Box` are one machine word; **fat pointers** — `&[T]`, `&str`, `&dyn Trait`, and their `Box`ed forms — are two (pointer + length, or pointer + vtable); `Vec<T>` is three (pointer, length, capacity); `String` is a `Vec<u8>` with a UTF-8 invariant. [`std::mem::size_of`](https://doc.rust-lang.org/std/mem/fn.size_of.html) answers any dispute in one line, and disputes are worth having — a struct that's 40 bytes when it could be 24 is a cache-line tax on every collection that holds it.

Enums are where Rust's layout gets genuinely clever. A `Result<T, E>` is tag + payload — but the **niche optimization** routinely deletes the tag: `Option<&T>`, `Option<Box<T>>`, `Option<NonZeroU64>` are all *pointer-sized*, because the compiler smuggles the `None` case into the payload's forbidden value (null, zero). This is why "nullable pointer" in Rust costs exactly what it costs in C while being impossible to dereference unchecked — the zero-cost-abstraction promise, delivered by layout — and why [`NonZeroU64`](https://doc.rust-lang.org/std/num/struct.NonZeroU64.html) and friends exist: they *donate a niche* to every `Option` that wraps them.

### 3.2 The ownership toolbox, completed

The decision table you must know reflexively:

| Type | Owners | Threads | Mutation through `&` | Cost |
|---|---|---|---|---|
| `Box<T>` | one | — | no | allocation |
| `Rc<T>` | many | **single-threaded** | no | non-atomic refcount |
| `Arc<T>` | many | thread-safe | no | atomic refcount |
| `Cell<T>` | (wrapper) | single-threaded | yes — by *copy/swap* only | zero |
| `RefCell<T>` | (wrapper) | single-threaded | yes — borrow rules checked **at runtime**, panics on violation | flag check |
| `Mutex<T>` / `RwLock<T>` | (wrapper) | thread-safe | yes — by blocking | lock |
| `OnceLock<T>` / `LazyLock<T>` | (wrapper) | thread-safe | write-once / lazy-init | one-time sync |

([`std::cell`](https://doc.rust-lang.org/std/cell/) · [`Rc`](https://doc.rust-lang.org/std/rc/struct.Rc.html) · [`std::sync`](https://doc.rust-lang.org/std/sync/).)

Three additions to the table everyone learns late and wishes they'd learned early:

**`Weak<T>`** ([docs](https://doc.rust-lang.org/std/rc/struct.Weak.html)) — the non-owning companion to `Rc`/`Arc`, and the answer to the question reference counting always raises: cycles. Two `Rc`s pointing at each other never hit refcount zero — a leak with no error message. The pattern: ownership edges are strong, *back*-edges are weak (a tree's children are `Rc`, the parent pointer is `Weak`; `upgrade()` returns `Option<Rc<T>>` because the parent may be gone). If your design has `Rc`s in both directions and no `Weak`, you have written a leak.

**`OnceLock` and `LazyLock`** ([docs](https://doc.rust-lang.org/std/sync/struct.LazyLock.html)) — the modern, std-only answer to "global initialized once" (configuration, compiled regexes, connection pools), retiring the `lazy_static!`/`once_cell` crates for new code: `static CONFIG: LazyLock<Config> = LazyLock::new(load_config);` is thread-safe, lazy, and lock-free after initialization.

**`Cow<'a, T>`** ([docs](https://doc.rust-lang.org/std/borrow/enum.Cow.html)) — clone-on-write: an enum of `Borrowed(&'a T)` / `Owned(T)` that lets a function return a borrow when no modification was needed and an owned value when it was (the canonical example: a sanitizer that returns the input string untouched 99% of the time, allocating only for the 1% that needed escaping). `Cow` in a signature is a precision instrument: it documents "I allocate only when I must."

### 3.3 Interior mutability: moving the check, not breaking the rule

`Rc<RefCell<T>>` (single-threaded shared mutability — graphs, observer lists) and `Arc<Mutex<T>>` (the cross-thread version) are the two canonical compositions, and the composition is the lesson: **`Arc` and `Mutex` are orthogonal**. `Arc` gives shared *ownership*; `Mutex` gives safe *mutation*; you combine them because thread-shared mutable state needs both — but plenty of designs want only one (an `Arc<Config>` of read-only settings needs no lock; a `Mutex<Cache>` owned by one struct needs no `Arc`).

```rust
use std::sync::{Arc, Mutex};
use std::thread;

let counter = Arc::new(Mutex::new(0u64));
let mut handles = vec![];

for _ in 0..10 {
    let counter = Arc::clone(&counter);          // bumps the refcount, not the data
    handles.push(thread::spawn(move || {
        let mut n = counter.lock().unwrap();     // guard unlocks on drop (RAII)
        *n += 1;
    }));
}
for h in handles { h.join().unwrap(); }
assert_eq!(*counter.lock().unwrap(), 10);
```

Interior mutability does not repeal "shared XOR mutable" — it **relocates the check**. `RefCell` enforces the borrow rules at runtime (and a violation is a *panic*, which is the trade you accepted); `Mutex` enforces them by making violators wait; `Cell` enforces them by never handing out a reference at all (you can only copy values in and out, which is also why it's zero-cost). Two production notes that separate journeyman from senior usage: a `Mutex` poisoned by a panicking thread returns `Err` from `lock()` forever after — decide a policy (`.unwrap()` to propagate the panic is usually right; `.lock().unwrap_or_else(|e| e.into_inner())` to shrug is sometimes right) instead of discovering the question in production; and `RefCell` in a struct is a design smell *exactly when* the struct is also `Send`-adjacent — it's the single most common reason a type mysteriously stops being `Sync` (Part 4 explains why).

```quiz
Q: Why is Option<Box<T>> exactly pointer-sized, with no separate tag?
- [ ] The compiler stores the tag in a thread-local table
- [x] The niche optimization — Box can never be null, so None is encoded as the forbidden zero value inside the payload itself
- [ ] Option is special-cased to one bit
- [ ] It isn't — Option always adds a word
> Enums smuggle their discriminant into payload values the payload type forbids (null for pointers, zero for NonZeroU64). That's how Rust's "nullable pointer" costs exactly what C's does while being impossible to dereference unchecked — the zero-cost promise delivered by layout.

Q: Two Rc values point at each other. What happens, and what's the fix?
- [ ] The cycle collector frees them eventually
- [x] Neither refcount ever reaches zero — a silent leak; make the back-edge a Weak, whose upgrade() returns Option because the target may be gone
- [ ] The program panics on drop
- [ ] Rc forbids cyclic assignment at compile time
> Reference counting has no cycle detection — Rust has no tracing GC to save you. The pattern: ownership edges strong, back-edges weak (children Rc, parent Weak). Rc in both directions with no Weak is a leak you've already written.

Q: What's the actual difference between Cell, RefCell, and Mutex for mutating through a shared reference?
- [ ] They're interchangeable; only performance differs
- [x] All relocate the "shared XOR mutable" check: Cell only copies values in/out (zero-cost), RefCell checks borrow rules at runtime and panics on violation, Mutex makes violators wait
- [ ] Only Mutex actually allows mutation
- [ ] RefCell is the thread-safe version of Cell
> Interior mutability never repeals the aliasing rule — it moves enforcement from compile time to a different mechanism. The choice is which failure mode you accept: impossibility (Cell), panic (RefCell), or blocking (Mutex) — and only Mutex's check works across threads.

Q: When does Cow<'a, str> earn its place in a signature?
- [x] When a function usually returns its input unchanged but occasionally must allocate a modified copy — it documents "I allocate only when I must"
- [ ] When the string must be shared across threads
- [ ] As a faster general replacement for String
- [ ] When the caller needs interior mutability
> Clone-on-write is Borrowed(&'a T) | Owned(T): a sanitizer returns the borrow for the 99% of clean inputs and allocates only for the 1% needing escapes. It's a precision instrument for conditional ownership, not a default string type.
```

---

## Part 4 — Threads, Send/Sync, and Data Parallelism

### 4.1 `Send` and `Sync`: the whole safety claim in two traits

Rust's "fearless concurrency" is not a slogan; it is two **auto traits** plus the borrow checker. [`Send`](https://doc.rust-lang.org/nomicon/send-and-sync.html) means *safe to move to another thread*; `Sync` means *safe to share by reference across threads* (`T: Sync` ⟺ `&T: Send`). The compiler derives both **structurally**: a type is `Send`/`Sync` iff all its fields are. No annotations, no registry — your design either composes from thread-safe parts or it doesn't, and the answer is computed, not declared.

This is the mechanism that turns data races into *type errors*. `Rc<T>` is deliberately not `Send` — its refcount is non-atomic, so moving one across threads would race the count itself — and the moment you try, the compiler stops you and (in so many words) tells you to use `Arc`. A `RefCell<T>` is `Send` but not `Sync` — its runtime borrow flag isn't atomic either — which is why it's fine inside one task and rejected the moment a reference would cross threads, with `Mutex` as the prescribed upgrade. Read those rejections as **design feedback with a fix attached**: a struct that "suddenly isn't `Send`" has a stray `Rc`, a raw pointer, or a `RefCell` where a `Mutex` belongs, and the error message names the field.

The two traits are also *contagious in the useful direction*: they flow through your whole composition automatically (an `Arc<Mutex<HashMap<K, V>>>` is `Send + Sync` because every layer is), and the rare cases where you implement them *by hand* — wrapping a raw pointer you know to be thread-safe — are `unsafe impl`s precisely because you're asserting what the compiler can't verify (Part 8.4).

### 4.2 Threads that borrow: `thread::scope`

The classic friction — `thread::spawn` needs `'static`, so threads can't borrow locals — has a stable, ergonomic answer since 1.63: [**scoped threads**](https://doc.rust-lang.org/std/thread/fn.scope.html). The scope guarantees every spawned thread joins before the scope returns, which is exactly the proof the borrow checker needs to allow borrows of the enclosing frame:

```rust
use std::thread;

let mut data = vec![1, 2, 3];

thread::scope(|s| {
    s.spawn(|| println!("read borrow: {:?}", &data));   // borrows local data directly
    s.spawn(|| println!("len = {}", data.len()));       // multiple shared borrows: fine
});                                                      // ← all scoped threads joined HERE

data.push(4);                                            // borrows ended; mutation OK again
```

This is the same "structure guarantees lifetime" move you'll meet again in async structured concurrency (Part 7), and it should be your default for fork-join work on borrowed data — reaching for `Arc` to share something that a scope could simply borrow is a tell that the tool ordering is off.

### 4.3 Channels vs. shared state

Rust supports both coordination styles and is opinionated about neither, but the design pressure is real: **channels move ownership, so there is nothing to lock and no lock order to get wrong**. A pipeline of stages connected by channels cannot deadlock the way two mutexes acquired in different orders can — the hardest classical concurrency bug class is structurally absent.

```rust
use std::sync::mpsc;
use std::thread;

let (tx, rx) = mpsc::channel();

for id in 0..3 {
    let tx = tx.clone();                    // multiple producers
    thread::spawn(move || {
        tx.send(format!("hello from {id}")).unwrap();   // send = transfer ownership
    });
}
drop(tx);                                   // last sender gone ⇒ the iterator below ends

for msg in rx {                             // blocks until a message or all senders dropped
    println!("{msg}");
}
```

The honest decision rule: **channels when the work decomposes into a flow of owned messages** (pipelines, work queues, event streams — most services); **shared state (`Arc<Mutex>`) when many workers genuinely converge on one structure** (a cache, a connection pool, a metrics registry). And a practical upgrade note: the std [`mpsc`](https://doc.rust-lang.org/std/sync/mpsc/) channel is fine, but the ecosystem standard is [`crossbeam-channel`](https://docs.rs/crossbeam-channel/) — faster, multi-consumer, and with a `select!` over multiple channels that std lacks; for bounded async channels see Part 7.

### 4.4 Data parallelism: Rayon

Whole category, one crate: when the problem is "do this CPU-bound thing to a million items," the answer is not hand-rolled threads or async — it's [**Rayon**](https://docs.rs/rayon/), the work-stealing data-parallelism library. Its headline API is almost insultingly small: change `.iter()` to `.par_iter()` and the iterator chain runs across all cores, with Rayon's scheduler splitting the work adaptively and the type system (those same `Send`/`Sync` bounds) guaranteeing the closure is race-free:

```rust
use rayon::prelude::*;

let total: u64 = (0..10_000_000u64)
    .into_par_iter()
    .map(|n| expensive_hash(n))
    .sum();                                  // all cores, no unsafe, no locks
```

What makes this safe where the equivalent OpenMP pragma is a prayer: the closure must be `Send + Sync`-compatible, captured borrows are checked, and any attempt to mutate shared state without synchronization simply doesn't compile. The mental sorting that should become reflex — and that Part 7 will sharpen from the other side: **Rayon for CPU-bound parallelism, async for I/O-bound concurrency.** They compose (a Tokio service handing image-resize work to a Rayon pool via `spawn_blocking`), but using either for the other's job produces the two classic performance bug reports: "async made my number crunching slower" and "my web server has 10,000 threads."

```quiz
Q: Why is Rc<T> deliberately not Send?
- [ ] Rc is too slow to be worth sharing
- [x] Its refcount is non-atomic — moving an Rc across threads would race the count itself; the compiler stops you and the fix is Arc
- [ ] Rc contains a raw pointer
- [ ] Send requires the Copy trait
> Send/Sync are derived structurally — a type is thread-safe iff its fields are — so the compiler computes the answer and the error names the offending field. "Suddenly not Send" almost always means a stray Rc, RefCell (→ Mutex), or raw pointer.

Q: What does thread::scope provide that thread::spawn can't?
- [x] Spawned threads may borrow the enclosing frame's locals, because the scope guarantees every thread joins before it returns
- [ ] Threads that run at higher priority
- [ ] Automatic panic recovery
- [ ] More than 1,024 concurrent threads
> spawn demands 'static because the thread may outlive the spawner. scope turns "all threads join here" into a structural guarantee the borrow checker can use — so fork-join work on borrowed data needs no Arc at all. Reaching for Arc where a scope would do is a tool-ordering tell.

Q: Why do channel-based pipelines structurally avoid the classic deadlock?
- [ ] Channels detect deadlocks at runtime and panic
- [x] Sending moves ownership — there's nothing to lock, so there's no lock order to invert
- [ ] Channels are faster than mutexes
- [ ] The runtime serializes all channel operations
> Two mutexes acquired in different orders is the textbook deadlock; a flow of owned messages has no shared state to contend over. Decision rule: channels when work decomposes into messages; Arc<Mutex> when many workers genuinely converge on one structure.

Q: A million CPU-bound items need processing. Threads, async, or Rayon?
- [ ] tokio::spawn per item — tasks are cheap
- [x] Rayon's par_iter — work-stealing data parallelism across cores, with Send/Sync making the closure provably race-free
- [ ] One thread per item
- [ ] async with buffer_unordered
> Rayon for CPU-bound parallelism, async for I/O-bound concurrency — using either for the other's job yields "async made my math slower" or "my server has 10,000 threads." They compose via spawn_blocking when a service needs both.
```

---

## Part 5 — Atomics and the Memory Model

The lowest level of the concurrency stack: lock-free primitives and the memory-ordering model that governs them. The essential reference for this entire part is Mara Bos's [*Rust Atomics and Locks*](https://marabos.nl/atomics/) — free online, and the rare book that makes orderings genuinely click.

### 5.1 The uncomfortable truth orderings encode

Modern hardware does not present memory as one coherent array that all cores see identically. Stores buffer, caches negotiate, compilers reorder — and *single-threaded* code never notices, because every reordering preserves single-threaded meaning. The moment two threads communicate through memory, "what happened before what" becomes a question with no default answer, and the [`Ordering`](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html) you pass to every atomic operation is how you buy exactly as much ordering as you need:

- **`Relaxed`** — the operation is atomic (no torn reads, no lost updates), and *nothing else*: no ordering relationship with any other memory access. Correct for self-contained values — counters, statistics, IDs.
- **`Acquire` / `Release`** — the handshake. A `Release` store publishes; an `Acquire` load that sees that store *also sees everything the storing thread did before it*. This pair is how every lock, channel, and `Arc` actually works underneath.
- **`SeqCst`** — acquire/release plus one single global order over all `SeqCst` operations. The safe-by-default choice, the slowest, and — the expert consensus — usually a sign the author didn't identify which weaker guarantee they needed. Use it when you genuinely need a total order (rare), not as a talisman.

The acquire/release handshake deserves the canonical demonstration, because once you can narrate this example you understand every lock you'll ever use:

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;

static READY: AtomicBool = AtomicBool::new(false);
static mut DATA: u64 = 0;                    // the payload being published

fn main() {
    thread::spawn(|| {
        unsafe { DATA = 42 };                 // (1) write the data...
        READY.store(true, Ordering::Release); // (2) ...then publish the flag.
    });

    while !READY.load(Ordering::Acquire) {}  // (3) spin until the flag is seen
    println!("{}", unsafe { DATA });         // (4) GUARANTEED to print 42
}
```

The `Release`/`Acquire` pair is what makes step (4) sound: it forbids the hardware and compiler from reordering (1) after (2), or (4) before (3). Make both orderings `Relaxed` and this program is **undefined behavior** — the reader can legally observe `READY == true` while seeing the *old* `DATA`, because you never asked for the data write to be ordered with the flag. Every "works on my machine, corrupts on the ARM server" story at this level is a missing or mismatched half of this handshake — x86's strong hardware ordering masks the bug; weaker architectures execute the freedom you accidentally granted.

### 5.2 Compare-and-swap: the lock-free building block

A `Relaxed` counter is the easy case:

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;

let hits = Arc::new(AtomicUsize::new(0));
let mut handles = vec![];
for _ in 0..10 {
    let hits = Arc::clone(&hits);
    handles.push(thread::spawn(move || {
        hits.fetch_add(1, Ordering::Relaxed);   // one atomic instruction, no lock
    }));
}
for h in handles { h.join().unwrap(); }
assert_eq!(hits.load(Ordering::Relaxed), 10);
```

Anything cleverer than `fetch_add` is built from the **compare-and-swap loop**: read the current value, compute the desired one, attempt to install it *conditional on nobody having changed it*, and retry on failure with the fresh value:

```rust
use std::sync::atomic::{AtomicUsize, Ordering};

// Lock-free "store the max seen so far."
fn store_max(slot: &AtomicUsize, candidate: usize) {
    let mut current = slot.load(Ordering::Relaxed);
    while candidate > current {
        match slot.compare_exchange_weak(
            current, candidate, Ordering::Release, Ordering::Relaxed,
        ) {
            Ok(_) => break,                  // we won the race
            Err(actual) => current = actual, // lost it; retry against the new value
        }
    }
}
```

(`compare_exchange_weak` may fail spuriously on some architectures in exchange for being cheaper in a loop — in a retry loop you were handling failure anyway, so prefer it there.)

### 5.3 Where the honest line sits

Atomics are the right tool for **counters, flags, sequence numbers, and the occasional published pointer** ([`arc-swap`](https://docs.rs/arc-swap/) packages the read-mostly-config case properly). Full lock-free *data structures* are a different sport: the ABA problem (the value you compare against was changed and changed *back* — your CAS succeeds, your invariant doesn't), memory reclamation (when may a removed node be freed, given lock-free readers may still hold it — the problem epoch-based schemes in [`crossbeam-epoch`](https://docs.rs/crossbeam-epoch/) exist to solve), and orderings interacting across multiple locations. The senior move is almost always a vetted crate — [`crossbeam`](https://docs.rs/crossbeam/)'s queues and deques, `arc-swap`, a sharded counter — and a `Mutex` for everything that profiling hasn't proven hot. An uncontended `Mutex` lock is ~20 nanoseconds; the bar for "the lock is the bottleneck" is higher than intuition suggests, and Part 10's tools tell you whether you've cleared it. When you *do* write lock-free code, Part 11's `loom` is how you test it against every legal interleaving rather than the ones your laptop happened to schedule.

```quiz
Q: In the publish-a-flag example, why must the writer use Release and the reader Acquire — what goes wrong with Relaxed on both?
- [ ] Relaxed loads can tear the value
- [x] Nothing orders the DATA write with the flag: the reader can legally see READY == true while reading the *old* DATA — undefined behavior that x86's strong ordering masks and ARM executes
- [ ] Relaxed is only valid for integers under 64 bits
- [ ] The spin loop would never terminate
> Acquire/Release is the handshake: a Release store publishes everything the thread did before it to any Acquire load that sees it — it's how every lock and channel works underneath. Relaxed buys atomicity only; "works on my machine, corrupts on the ARM server" is a missing half of this pair.

Q: When is Ordering::Relaxed actually correct?
- [x] For self-contained values like counters and statistics, where you need atomicity but no ordering relationship with other memory
- [ ] Never — it exists only for benchmarks
- [ ] Whenever performance matters more than correctness
- [ ] Only inside Mutex-protected regions
> fetch_add(1, Relaxed) on a hit counter is exactly right: no torn updates, no lost increments, and nobody infers other memory state from the count. The moment a value *publishes* other data, you need the Release/Acquire handshake.

Q: Why prefer compare_exchange_weak inside a retry loop?
- [ ] It's stronger than compare_exchange
- [x] It may fail spuriously on some architectures in exchange for being cheaper — and the loop was already handling failure, so spurious failures cost nothing
- [ ] It cannot suffer from the ABA problem
- [ ] It doesn't require an Ordering argument
> The CAS loop (read, compute, install-if-unchanged, retry) is the building block of everything cleverer than fetch_add. weak maps better to LL/SC architectures like ARM; reserve the strong version for one-shot, non-looping attempts.

Q: Profiling hasn't shown a lock to be hot, but you're tempted to go lock-free anyway. What does the guide say?
- [ ] Lock-free is always worth it for future-proofing
- [x] An uncontended Mutex lock is ~20 ns — the bar for "the lock is the bottleneck" is high; use vetted crates (crossbeam, arc-swap) when proven, and loom-test anything hand-written
- [ ] Rewrite with SeqCst everywhere to be safe
- [ ] Spin-locks are a good middle ground
> Lock-free data structures bring ABA, memory reclamation, and multi-location ordering — a different sport. SeqCst-as-talisman usually signals unidentified requirements; the senior move is a Mutex until the profiler objects, and loom when you do cross the line.
```

---

## Part 6 — Async I: The Model

Async Rust earns its reputation in this part and loses it in the next: the *model* is small and rigorous; the *ecosystem reality* is conventions layered on it. Learn the model first and the conventions become predictable.

### 6.1 Futures are state machines, and they are lazy

`async`/`await` is sugar over one small trait ([`Future`](https://doc.rust-lang.org/std/future/trait.Future.html)). An `async fn` compiles into an anonymous struct — a **state machine** whose states are "between which `.await`s am I," holding whatever locals are alive across each await — and `await`ing it advances the machine. Two consequences define everything downstream.

**Futures do nothing until polled.** `async fn` desugars to `fn(...) -> impl Future<Output = ...>`: calling it constructs the state machine and returns instantly; the body has not begun. Python's coroutines behave similarly, but Rust's laziness is total — no executor sees your future until you `.await` it or `spawn` it, which is why "I called the async function and nothing happened" is the first async bug everyone files against themselves.

**The contract is `poll`, `Pending`, and the `Waker`.** An executor drives a future by calling `poll`; the future either completes (`Ready(value)`) or — having arranged for the [`Waker`](https://doc.rust-lang.org/std/task/struct.Waker.html) in the `Context` to be invoked when progress becomes possible — parks itself (`Pending`). The waker is the entire notification system: I/O readiness, timer expiry, a channel receiving a message — all of them end in "call the waker, so the executor re-polls the task."

```rust
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

// The whole async model in miniature: yield once (Pending + wake), then complete.
struct YieldNow(bool);

impl Future for YieldNow {
    type Output = ();
    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if self.0 {
            Poll::Ready(())
        } else {
            self.0 = true;
            cx.waker().wake_by_ref();     // "poll me again" — omit this and we hang forever
            Poll::Pending
        }
    }
}
```

From the contract, the scheduling model: **cooperative**. A task runs from one `poll` until it returns — it yields *only* at `.await` points that come up `Pending`. A blocking syscall or a long CPU loop inside async code never yields, and on a runtime multiplexing thousands of tasks over a handful of threads, one such task starves the rest. This is the async cardinal sin, and Part 7 gives it the full treatment because production incident reports give it one monthly.

The last structural fact: **Rust ships no runtime.** The language defines `Future` and the awaiting machinery; *executors* (Tokio, and alternatives like [smol](https://docs.rs/smol/)) supply the scheduler, timers, and I/O reactor. Python bundles `asyncio`; Rust unbundles deliberately — embedded targets run futures on bare-metal executors with no OS, while servers run work-stealing thread pools, all against one trait. The cost of that generality is the next section.

### 6.2 `Pin`: the self-reference problem, solved by promise

Part 2.5 established the wall: safe Rust forbids self-referential structs because every value must survive being moved by `memcpy`. Now watch async run straight into it — *any borrow held across an `.await` is a self-reference*:

```rust
async fn example() {
    let data = vec![1u8, 2, 3];
    let view = &data[1..];              // borrows data...
    something().await;                  // ...and is alive ACROSS this await
    println!("{view:?}");
}
```

Both `data` and `view` must be stored in the state machine while it's suspended — making it a struct containing a pointer into itself. Move that struct after polling begins and `view` dangles. The language's answer is not to forbid such futures (they're the *common case*) but to make immobility a typed promise: [`Pin<P>`](https://doc.rust-lang.org/std/pin/) wraps a pointer and guarantees the pointee **will never move again**. Executors only ever poll through `Pin<&mut F>`, so by the time a future can possibly become self-referential, the type system has already extracted the no-move promise.

What keeps `Pin` from infecting all your code is its escape valve: [`Unpin`](https://doc.rust-lang.org/std/marker/trait.Unpin.html), an auto trait marking types that *don't care* about moving — which is almost every type you'll ever write (`i32`, `String`, your structs). For `Unpin` types, `Pin` is a transparent no-op. The only types that are `!Unpin` in practice are the compiler-generated futures themselves and deliberately self-referential unsafe constructions. So the working rules are short: you'll *consume* `Pin` (the `pin!` macro to poll a future in place; `Box::pin` to heap-pin one you need to store or send), and you'll *produce* pinned access only when writing future combinators — where [`pin-project`](https://docs.rs/pin-project/) generates the safe field-projection boilerplate, distinguishing structurally-pinned fields from movable ones:

```rust
use pin_project::pin_project;
use std::time::Instant;

#[pin_project]
struct Timed<F> {
    #[pin] future: F,    // structurally pinned: pinning Timed pins this field
    started: Instant,    // ordinary field: freely movable even when Timed is pinned
}
```

Why `Pin` feels alien is worth saying out loud: it solves a problem most languages never surface. In a GC'd language objects never move (or the GC fixes pointers up), so self-reference is free; in C you simply promise not to move things, unverified. Rust is the language that makes the promise *checkable* — `Pin` is ownership-thinking applied to *location*, the same invariants-in-types move as everything else in this guide.

### 6.3 Reading async signatures like a professional

Assemble Parts 1, 2, and 6, and async type errors become legible. An `async` block is a compiler-generated struct capturing its environment (closure rules, 1.5). It is `Send` iff everything held across its awaits is `Send` (auto-trait structural rule, 4.1) — *held across awaits*, not merely used: a non-`Send` value created and dropped between awaits is fine. It satisfies `'static` iff it captures no borrows (2.2) — hence `move` blocks and cloned `Arc`s before a `spawn`. The notorious error — *"future cannot be sent between threads safely"* with three screens of types — is the compiler walking that structural derivation and showing you the path; the actionable line is the one naming **which value** is `!Send` and **which await** it lives across. The fix is almost always one of three: scope the value to end before the await, replace it with a `Send` equivalent (`Rc` → `Arc`, `RefCell` → `Mutex`), or — when the task genuinely needn't move threads — run it on a `LocalSet` (Part 7.6).

```quiz
Q: You call an async fn and nothing happens. Why?
- [x] Futures are lazy — calling the fn only constructs the state machine; nothing runs until it's awaited or spawned onto an executor
- [ ] The runtime queues it behind existing tasks
- [ ] async fns require #[tokio::main] to be callable
- [ ] The future panicked silently
> async fn desugars to fn(...) -> impl Future: the body hasn't begun. This is the first async bug everyone files against themselves — and it's total laziness, stronger than Python's coroutines: no executor sees the future until you hand it over.

Q: What turns an async fn into the self-referential struct safe Rust forbids — and how does Pin resolve it?
- [ ] Recursion; Pin allocates each frame on the heap
- [x] Any borrow held across an .await becomes a pointer into the future's own state; Pin makes "this value will never move again" a typed promise, extracted before polling begins
- [ ] Captured Rc values; Pin makes them atomic
- [ ] Nothing — async structs are always movable
> The state machine stores both the data and the borrow of it while suspended. Rather than forbid such futures (they're the common case), Rust made immobility checkable: executors only poll through Pin<&mut F>. Unpin opts nearly every ordinary type out, which is why you mostly just use pin! or Box::pin.

Q: The compiler says "future cannot be sent between threads safely." What's the actionable information?
- [ ] The runtime needs more worker threads
- [x] The line naming which !Send value lives across which .await — fix by scoping it to end before the await, swapping it for a Send equivalent, or running on a LocalSet
- [ ] The future is too large to move
- [ ] You must add Send to your trait bounds
> A future is Send iff everything held *across* its awaits is Send — created-and-dropped between awaits is fine. The three screens of types are the structural derivation; the fix is one of three moves (scope it, Rc→Arc / RefCell→Mutex, or LocalSet).
```

---

## Part 7 — Async II: Tokio in Production

[Tokio](https://tokio.rs/) is the de-facto runtime: a multi-threaded, work-stealing **executor**, an I/O **reactor** wired to `epoll`/`kqueue`/IOCP via [`mio`](https://docs.rs/mio/), and a hierarchical timer wheel — plus the [`tokio::sync`](https://docs.rs/tokio/latest/tokio/sync/) toolbox and the ecosystem standard position. This part is the working knowledge: what the runtime actually does, and the five disciplines that separate services that stay up from services that mysteriously stall.

### 7.1 The runtime's anatomy, briefly but honestly

`#[tokio::main]` builds a runtime (one worker thread per core by default) and blocks on your async `main`. `tokio::spawn` hands a future to the scheduler as a **task** — the async analog of a green thread, ~hundreds of bytes of overhead rather than a thread's megabytes, which is the entire reason async exists: a thread-per-connection server tops out where an async one is warming up. Each worker runs tasks from its local queue and **steals** from siblings when idle, so load balances without your involvement; the reactor thread(s) sleep in `epoll_wait`, translating OS readiness events into waker calls (Part 6.1's contract, operationalized); expired timers do the same. Two scheduler facts with operational consequences: spawned tasks require **`Send + 'static`** (any worker may run the task, at any time — Part 6.3's checklist), and Tokio implements **cooperative budgeting** (a task that keeps polling ready resources is forced to yield every ~128 operations, so a hot connection can't monopolize a worker — but this only helps between `.await`s; it cannot rescue you from blocking, which is the next section).

```rust
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    // Two tasks run concurrently on the runtime; the sleeps OVERLAP.
    let a = tokio::spawn(async { sleep(Duration::from_millis(50)).await; 1 });
    let b = tokio::spawn(async { sleep(Duration::from_millis(30)).await; 2 });

    let total = a.await.unwrap() + b.await.unwrap();   // ~50ms total, not 80
    println!("{total}");
}
```

### 7.2 Discipline #1: never block the executor

The cardinal rule, with its reasons now visible: workers are few and tasks are many, so a worker thread parked in a blocking syscall or grinding a CPU loop removes 1/Nth of your entire service's capacity until it returns. The symptoms are characteristic — latency cliffs under load, timers firing late, health checks timing out while CPU sits idle — and the offending call is usually innocent-looking: `std::fs` anything, a synchronous database client, `reqwest::blocking`, a CPU-heavy serde of a 50 MB payload, even a surprisingly contended `std::sync::Mutex`.

The prescribed escape hatches, in order: [`tokio::task::spawn_blocking`](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) ships the closure to a dedicated, elastic blocking pool (default cap 512 threads) and returns a future for its result — correct for file I/O, sync clients, and *bounded* CPU bursts; **Rayon** (Part 4.4) for sustained data-parallel compute, bridged back via a oneshot channel; and `block_in_place` as the narrow expert tool (it converts the *current* worker to a blocking thread, stealing its queue first — fewer copies, more sharp edges). For finding violations rather than guessing: `tokio-console` (7.7) flags tasks with pathological poll times, and a `current_thread` test runtime makes blocking hangs reproduce deterministically.

```rust
// Blocking work belongs on the blocking pool, not the async workers.
let contents = tokio::task::spawn_blocking(|| std::fs::read("big.bin"))
    .await
    .expect("blocking task panicked")?;
```

### 7.3 Discipline #2: cancellation is everywhere, design for it

The combinators first, because they're where cancellation enters. [`join!`](https://docs.rs/tokio/latest/tokio/macro.join.html) runs futures concurrently and waits for **all**; [`select!`](https://docs.rs/tokio/latest/tokio/macro.select.html) races them and takes the **first** — *dropping the losers*. And in async Rust, **drop means cancel**: a dropped future simply never gets polled again, evaporating at whatever `.await` it last parked on.

```rust
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    let work = async { sleep(Duration::from_secs(5)).await; "done" };

    tokio::select! {
        res = work => println!("finished: {res}"),
        _ = sleep(Duration::from_secs(1)) => println!("timed out"),  // wins; `work` is DROPPED
    }
}
```

This design is why timeouts in Rust are one line ([`tokio::time::timeout`](https://docs.rs/tokio/latest/tokio/time/fn.timeout.html) is just this pattern packaged) and also why **cancellation safety** is a first-class engineering property with no equivalent in most languages. A future cancelled between "removed the message from the internal buffer" and "returned it to the caller" has *lost the message* — and `select!` in a loop creates exactly that window every iteration. The Tokio docs mark each API's cancel-safety: `mpsc::Receiver::recv` is cancel-safe (a message is either delivered or still queued — nothing is lost by dropping the future mid-wait); `tokio::io::AsyncReadExt::read_exact` is *not* (partially read bytes are gone). The working rules: in every `select!` arm, ask "if this future is dropped *right now*, what state is half-mutated?"; prefer cancel-safe primitives in select loops; and for must-complete sequences, either spawn them as their own task (spawned tasks aren't cancelled by a `select!` — only their `JoinHandle` is) or guard cleanup in a `Drop` impl. Treat every `.await` in cancellable code as a possible last line of the function, because it is.

### 7.4 Discipline #3: structured concurrency over loose spawns

`spawn` is cheap, and unbounded spawning is how services die slowly: every "fire and forget" task is memory, scheduler pressure, and — worse — an untracked failure domain whose panics vanish into a `JoinHandle` nobody awaits. The structured tools: [`JoinSet`](https://docs.rs/tokio/latest/tokio/task/struct.JoinSet.html) owns a dynamic group of tasks, yields results as they complete, and **aborts all members when dropped** (the async sibling of `thread::scope`'s guarantee):

```rust
use tokio::task::JoinSet;

#[tokio::main]
async fn main() {
    let mut set = JoinSet::new();
    for i in 0..5 {
        set.spawn(async move { i * i });
    }
    let mut sum = 0;
    while let Some(res) = set.join_next().await {
        sum += res.expect("task panicked");     // completion order, not spawn order
    }
    println!("{sum}");                          // 30
}
```

— while a [`Semaphore`](https://docs.rs/tokio/latest/tokio/sync/struct.Semaphore.html) caps concurrency ("at most 64 in-flight upstream calls": acquire a permit before, drop it after), and `FuturesUnordered`/[`StreamExt::buffer_unordered`](https://docs.rs/futures/latest/futures/stream/trait.StreamExt.html#method.buffer_unordered) handle the "N-at-a-time over a big list" shape *within* one task. The decision smell to internalize: if you can't answer "who awaits this task, and what happens when it fails?", the spawn is unstructured and will eventually page someone.

### 7.5 Channels, locks, and the one footgun everyone fires

[`tokio::sync`](https://docs.rs/tokio/latest/tokio/sync/) gives you the async-aware coordination set, and channel selection is a vocabulary question: **`mpsc`** (bounded work queues — the default), **`oneshot`** (single request/response handoff, the reply-envelope of actor-ish designs), **`watch`** (latest-value broadcast — config reloads, shutdown signals), **`broadcast`** (fan-out to many subscribers, with lagging receivers handled by ring-buffer eviction). All the useful ones are *bounded*, which is Part 13's backpressure story showing up early: a bounded channel makes a slow consumer slow the producers down — the truthful behavior — where an unbounded one converts the same situation into an OOM kill an hour later.

The footgun: **holding a `std::sync::Mutex` guard across an `.await`**.

```rust
use std::sync::Mutex;

// ❌ The guard lives across the await: the future is no longer Send (compile error
// when spawned) — and conceptually you'd be holding a blocking lock while suspended
// for an unbounded time, inviting deadlock.
async fn bad(state: &Mutex<Vec<u8>>, client: &Client) {
    let mut g = state.lock().unwrap();
    g.push(1);
    client.fetch().await;
    g.push(2);
}

// ✅ Scope the guard so it drops before the await; re-acquire after.
async fn good(state: &Mutex<Vec<u8>>, client: &Client) {
    { state.lock().unwrap().push(1); }
    client.fetch().await;
    { state.lock().unwrap().push(2); }
}
```

The compiler usually catches this (the guard is `!Send`, so the spawned future is too — Part 6.3's derivation working in your favor), and the *fix hierarchy* matters: first, restructure so the lock isn't held across the await (almost always possible, fastest); second, [`tokio::sync::Mutex`](https://docs.rs/tokio/latest/tokio/sync/struct.Mutex.html) — whose guard *is* designed to be held across awaits — accepting that it's slower and that long hold times now block tasks instead of threads; third, reconsider whether the shared state should be a channel-owned actor instead. The underlying principle: **a lock assumes a bounded critical section; an await is unbounded**. Designs that minimize their overlap are the designs that don't deadlock at 4 a.m.

### 7.6 The rest of the working surface

**Streams** — async iterators ([`tokio-stream`](https://docs.rs/tokio-stream/), the `futures` crate's [`StreamExt`](https://docs.rs/futures/latest/futures/stream/trait.StreamExt.html)) — `while let Some(x) = stream.next().await` plus combinators, with `buffer_unordered` as the workhorse for bounded concurrent fan-out over a stream of jobs. **Async traits**: native `async fn` in traits landed in 1.75; the remaining seam is dyn-compatibility and the `Send` bound on returned futures, which is why public interfaces still often use [`#[async_trait]`](https://docs.rs/async-trait/) or explicit `-> impl Future + Send` ([the 1.75 announcement](https://blog.rust-lang.org/2023/12/21/async-fn-rpit-in-traits.html) explains the trade space). **`!Send` work**: [`LocalSet`](https://docs.rs/tokio/latest/tokio/task/struct.LocalSet.html) runs tasks pinned to one thread, the sanctioned home for `Rc`-laden code; and `flavor = "current_thread"` builds a single-threaded runtime outright — the right choice for CLIs and tests more often than people expect. **Async drop doesn't exist**: `Drop` is synchronous, so "async cleanup on the way out" needs an explicit `shutdown().await` method or a drop-spawned task — design resource teardown with that limitation in front of you, not as a surprise.

### 7.7 Seeing into the runtime

When "it's slow" arrives without a stack trace: [`tokio-console`](https://github.com/tokio-rs/console) is the async profiler — live per-task poll counts, poll durations, and wake patterns that make a blocking task or a busy-loop waker glow on the screen; the [`tracing`](https://docs.rs/tracing/) crate (Part 13) gives you structured, span-scoped causality through async boundaries where thread-based loggers produce confetti; and runtime metrics ([`Handle::metrics`](https://docs.rs/tokio/latest/tokio/runtime/struct.Handle.html#method.metrics)) expose queue depths and blocking-pool counts to your dashboards. Instrument before you have the incident; the async runtime is exactly the part of your system that a conventional profiler sees worst.

```quiz
Q: A Tokio service shows latency cliffs and late timers while CPU sits idle. What's the likely class of bug?
- [ ] Too few tokio worker threads configured
- [x] Something is blocking a worker — std::fs, a sync client, or heavy compute parked on the async pool; ship it to spawn_blocking (or Rayon for sustained compute)
- [ ] The channel buffers are too small
- [ ] GC pauses in the allocator
> Workers are few and tasks are many: one blocked worker removes 1/Nth of total capacity, and cooperative budgeting can't rescue code that never reaches an .await. tokio-console makes the pathological poll times glow.

Q: In a select! loop, what does "cancellation safety" ask of each arm's future?
- [x] If this future is dropped right now — at any await — is any state left half-mutated or any message lost? Losers of select! are dropped, and drop means cancel
- [ ] Whether the future catches panics
- [ ] Whether it completes within a deadline
- [ ] Whether it's Send + 'static
> An async Rust future evaporates at whatever await it last parked on. recv() is cancel-safe (the message stays queued); read_exact is not (partial bytes are gone). Treat every .await in cancellable code as a possible last line of the function.

Q: Why does the guide insist on bounded channels by default?
- [ ] Unbounded channels are slower per message
- [x] A bounded channel makes a slow consumer slow its producers — honest backpressure — where an unbounded one converts the same situation into an OOM kill hours later, far from the cause
- [ ] Bounded channels preserve message ordering
- [ ] tokio deprecated unbounded channels
> Every queue is a policy decision. Backpressure makes load tell the truth at the point of origin; unbounded buffering defers the failure and detaches it from its cause — the worst possible debugging gift.

Q: Holding a std::sync::Mutex guard across an .await is the canonical async footgun. What's the fix hierarchy?
- [ ] Switch to a spin lock
- [x] First restructure so the guard drops before the await; second, tokio::sync::Mutex if the lock genuinely must span it; third, reconsider — maybe a channel-owned actor
- [ ] Always use tokio::sync::Mutex everywhere
- [ ] Wrap the lock in catch_unwind
> A lock assumes a bounded critical section; an await is unbounded. The compiler usually catches it (the guard is !Send) — and the principle generalizes: minimize the overlap between held locks and suspension points, or meet the deadlock at 4 a.m.
```

---

## Part 8 — Unsafe Rust

### 8.1 The contract: five powers, zero exemptions

The `unsafe` keyword unlocks exactly **five** operations ([the book](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html), [Rustonomicon](https://doc.rust-lang.org/nomicon/)): dereference a raw pointer, call an `unsafe` function, implement an `unsafe` trait, access or modify a `static mut`, and access a `union` field. That's the entire list — and just as important is what `unsafe` does **not** do: it does not disable the borrow checker, the type system, lifetimes, or any other check. Inside an `unsafe` block, every safe-Rust rule still applies; you've merely been *permitted to also do five things the compiler cannot verify*. The keyword's real meaning is a transfer of proof obligation: "the compiler can't show this is sound, so *I* am vouching for it" — and if you vouch wrongly, the result is **undefined behavior**, the one outcome safe Rust exists to abolish.

```rust
let mut x = 42;
let ptr = &mut x as *mut i32;     // creating a raw pointer is SAFE — it's inert
unsafe {
    *ptr += 1;                    // dereferencing asserts: valid, aligned, not aliased
}
assert_eq!(x, 43);
```

Be concrete about what UB means, because "it crashes" undersells it: UB licenses the *optimizer* to assume the violating execution never happens, and to transform your program under that assumption. Symptoms range from nothing (today, this compiler) to wrong values, vanished checks, and security holes that appear only at `-O2` on the release build. The principal sins: dereferencing dangling or unaligned pointers, **violating aliasing** (constructing two live `&mut` to one location, or mutating behind a live `&` — the rules safe Rust enforces remain *facts* unsafe code must respect, not suggestions it may waive), reading uninitialized memory, producing invalid values (a `bool` of 3, a bad enum tag — this is why [`transmute`](https://doc.rust-lang.org/std/mem/fn.transmute.html) is the most dangerous function in the language), and data races (Part 5's model still governs).

### 8.2 The discipline: safe abstractions over audited cores

Production `unsafe` has one legitimate shape: **a small unsafe core wrapped in an API that safe code cannot misuse**. The classic teaching example is `split_at_mut` — two disjoint `&mut` views into one slice, which the borrow checker can't verify (it doesn't reason about ranges) but you can prove:

```rust
use std::slice;

fn split_at_mut(v: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    let len = v.len();
    let ptr = v.as_mut_ptr();
    assert!(mid <= len);                 // ← the runtime check that makes the proof total
    unsafe {
        // SAFETY: [0, mid) and [mid, len) are disjoint ranges of one valid
        // allocation, so the two &mut never alias; lengths are in bounds by
        // the assert above.
        (
            slice::from_raw_parts_mut(ptr, mid),
            slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

Read the shape, not just the code: the *signature* is fully safe (no caller, however adversarial, can cause UB through it); the `assert!` closes the one hole; the `// SAFETY:` comment states the invariant being relied on — a convention enforced by `#[deny(clippy::undocumented_unsafe_blocks)]` in serious codebases, and the right habit from day one. If you cannot write the SAFETY comment, you are not ready to write the block. Two more tools belong in the same toolbox: [`MaybeUninit<T>`](https://doc.rust-lang.org/std/mem/union.MaybeUninit.html) is the sanctioned way to work with uninitialized memory (building a buffer before initializing it — the old `mem::uninitialized` is UB-on-arrival and deprecated for it), and [`PhantomData`](https://doc.rust-lang.org/std/marker/struct.PhantomData.html) is how a raw-pointer-holding type *declares* its ownership and variance to the compiler so that drop-checking and Part 2.4's variance come out right.

### 8.3 Miri: the UB detector you must run

You no longer have to *wonder* whether your unsafe code is sound on the cases you exercise: [**Miri**](https://github.com/rust-lang/miri) (`cargo +nightly miri test`) interprets your program against Rust's experimental-but-enforced aliasing models (Stacked Borrows / Tree Borrows) and reports UB *as an error with a trace* — dangling dereferences, aliasing violations, invalid values, leaks. It's slow (an interpreter) and can't see FFI, but the policy writes itself: **any crate containing `unsafe` runs its tests under Miri in CI.** The ecosystem's serious unsafe code (the standard library included) is developed this way; matching that bar is table stakes, not extra credit.

### 8.4 `unsafe impl Send`/`Sync`: vouching at the type level

Implementing the Part 4 marker traits by hand is the type-level version of the same contract — you're asserting a thread-safety property the structural derivation couldn't see (typical case: a struct holding a raw pointer into a C library you know to be thread-safe). The assertion is load-bearing for every downstream user, so it earns the same SAFETY-comment treatment, plus an honest check of *both* claims separately: `Send` (may the value move threads? — not if the C library uses thread-local state) and `Sync` (may two threads call through `&self` concurrently? — not unless the C side is internally synchronized). Wrong answers here are the worst kind of unsoundness: invisible locally, and they convert your users' safe code into data races.

```quiz
Q: What does the unsafe keyword actually disable?
- [ ] The borrow checker, inside the block
- [x] Nothing — it permits five extra operations (raw-pointer deref, unsafe fn calls, unsafe trait impls, static mut access, union fields) while every safe-Rust rule still applies
- [ ] Lifetime checking and the type system
- [ ] Bounds checks on slices
> unsafe is a transfer of proof obligation, not an off switch: "the compiler can't verify this, so I vouch for it." Vouch wrongly and you get UB — which licenses the optimizer to assume the violation never happens and transform your program accordingly.

Q: What makes split_at_mut the model of legitimate production unsafe?
- [x] A fully safe signature no caller can cause UB through, a runtime assert closing the one hole, and a SAFETY comment stating the invariant relied on
- [ ] It avoids unsafe entirely by cloning the slice
- [ ] It's only compiled in release mode
- [ ] It uses transmute, the approved primitive
> The shape is the lesson: small audited core, safe abstraction over it, the proof written down. If you can't write the SAFETY comment, you aren't ready to write the block — and clippy::undocumented_unsafe_blocks can enforce the habit.

Q: What's the policy the guide derives about Miri?
- [ ] Run it once before each major release
- [x] Any crate containing unsafe runs its tests under Miri in CI — it interprets your code against the aliasing models and reports UB as an error with a trace
- [ ] Use it only when debugging a crash
- [ ] Miri replaces the need for SAFETY comments
> Miri turns "I wonder if this is sound" into a test failure with a trace, for the cases you exercise. It's slow and can't see FFI, but the standard library itself is developed under it — matching that bar is table stakes for unsafe code.

Q: Why is a wrong `unsafe impl Send` worse than most unsafe bugs?
- [ ] It fails to compile downstream
- [x] It's invisible locally and converts *users'* safe code into data races — the assertion is load-bearing for everyone downstream
- [ ] It only affects performance
- [ ] The compiler inserts runtime checks to catch it
> Hand-implementing the marker traits asserts what structural derivation couldn't see. Check both claims separately: Send (thread-local state on the C side says no) and Sync (concurrent &self calls need internal synchronization) — and write the SAFETY comment.
```

---

## Part 9 — FFI: Crossing the C Boundary

The C ABI is Rust's interop lingua franca — to C itself, and through it to Python, Node, Java, and every language with a C FFI. Rust's guarantees genuinely stop at this line, so professional FFI is about making the line thin, explicit, and immediately re-wrapped in safety.

### 9.1 The mechanics in both directions

Calling C ([Nomicon: FFI](https://doc.rust-lang.org/nomicon/ffi.html)): declare the foreign signatures in an `extern "C"` block; every call is `unsafe` because the compiler cannot check the other side's contract.

```rust
extern "C" {
    fn abs(input: i32) -> i32;     // from libc
}

fn main() {
    let n = unsafe { abs(-5) };    // SAFETY: abs is total for all i32 except i32::MIN — handle it
    println!("{n}");
}
```

Being called *from* C: export with `#[no_mangle] pub extern "C"`, and give every shared struct `#[repr(C)]` — without it, Rust's field-reordering layout freedom (Part 3.1) makes the struct's bytes mean different things on each side:

```rust
#[no_mangle]
pub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }

#[repr(C)]
pub struct Point { pub x: f64, pub y: f64 }   // C-stable layout: declared order, C padding rules
```

Don't hand-write declarations at scale: [`bindgen`](https://rust-lang.github.io/rust-bindgen/) generates Rust `extern` blocks from C headers (typically in a `build.rs`, with the system library located via [`pkg-config`](https://docs.rs/pkg-config/) and linked via `cargo:rustc-link-lib` directives), and [`cbindgen`](https://github.com/mozilla/cbindgen) generates C headers from your Rust exports. The ecosystem convention worth following: a raw `-sys` crate containing only the generated bindings and link logic, and a safe wrapper crate on top — so consumers, including future-you, never touch the unsafe surface directly.

### 9.2 The three hazards that account for most FFI bugs

**Ownership across the line.** Every pointer crossing the boundary needs an agreed answer to "who frees this, with which allocator?" — Rust memory must be freed by Rust (export a `free_foo` function; the pattern is `Box::into_raw` to hand ownership out and `Box::from_raw` to take it back), C memory by C, and strings get the dedicated [`CString`/`CStr`](https://doc.rust-lang.org/std/ffi/) pair (NUL-terminated, no interior NULs — `CString::into_raw`/`from_raw` for the owned handoff). Mixing allocators "works" right up until it corrupts a heap on a platform where the allocators differ.

**Unwinding.** A Rust panic unwinding into C frames is undefined behavior. Every exported function must contain panics — wrap fallible bodies in [`std::panic::catch_unwind`](https://doc.rust-lang.org/std/panic/fn.catch_unwind.html) and convert to an error code; the modern `extern "C-unwind"` ABI ([RFC 2945](https://rust-lang.github.io/rfcs/2945-c-unwind-abi.html)) exists for the narrower case of deliberately propagating unwinds through C++-style frames, not as an excuse to skip the catch.

**Validity of incoming data.** Every pointer from C is a claim, not a fact: null-check, respect alignment, and treat lengths as untrusted. The wrapper layer's job is converting C's "trust me" into Rust types that *can't* lie — `Option<&T>` instead of a nullable pointer (they're layout-identical, Part 3.1's niche optimization at work), slices built with explicit, checked lengths.

For specific high-level targets, skip raw C glue entirely: [PyO3](https://pyo3.rs/) (Python), [napi-rs](https://napi.rs/) (Node), [UniFFI](https://mozilla.github.io/uniffi-rs/) (mobile) generate the boundary with the hazards above already handled — the same thin-unsafe-core principle, industrialized.

```quiz
Q: Why does every struct shared with C need #[repr(C)]?
- [x] Default Rust layout may reorder fields to minimize padding — without repr(C), the struct's bytes mean different things on each side of the boundary
- [ ] C compilers reject Rust's field names otherwise
- [ ] repr(C) enables the niche optimization
- [ ] It's only needed for structs containing pointers
> repr(Rust) gives the compiler layout freedom; repr(C) pins declared order and C padding rules. The same fact from Part 3 — source order doesn't predict layout — becomes a correctness requirement the moment bytes cross the ABI.

Q: Rust allocates a struct and hands the pointer to C. Who frees it, and how?
- [ ] C calls free() on it — that's what the C ABI means
- [x] Rust must — export a free function built on Box::from_raw, because memory must be freed by the allocator that allocated it
- [ ] Either side; modern allocators are compatible
- [ ] Nobody — FFI pointers are static by convention
> Box::into_raw hands ownership out; Box::from_raw takes it back for Rust's allocator to free. Mixing allocators "works" until it corrupts a heap on a platform where they differ — same story for strings via CString::into_raw/from_raw.

Q: What must every Rust function exported to C do about panics?
- [ ] Nothing — panics become C error codes automatically
- [x] Contain them — a panic unwinding into C frames is undefined behavior; wrap fallible bodies in catch_unwind and return an error code
- [ ] Compile with panic = "unwind"
- [ ] Re-export them as C++ exceptions
> Unwinding across an extern "C" boundary is UB, full stop. catch_unwind at every export converts panics into error codes; the "C-unwind" ABI exists for deliberately propagating unwinds through C++-style frames, not as an excuse to skip the catch.
```

---

## Part 10 — Performance Engineering

### 10.1 What "zero-cost" actually promises

The promise — iterators, closures, generics, `async`, `Option`/`Result` compile to what you'd have written by hand — is real and load-bearing: a `.iter().filter().map().sum()` chain monomorphizes and inlines into the same loop as the manual version, with no allocation and no indirection. What the promise does *not* cover is the costs you explicitly order: `Box<dyn Trait>` buys flexibility with a vtable call and an allocation; `Arc::clone` is an atomic RMW (cheap, but contended atomics ping-pong cache lines — don't clone in the hot loop, clone once outside it); `.collect()`, `format!`, and `Vec` growth allocate; async's state machines have a *size* (a future holding a 16 KB buffer across an await is a 16 KB struct — `Box::pin` the big ones, or restructure so the buffer doesn't span the await). "Zero-cost abstraction" means zero *overhead versus equivalent hand-written code*, never zero cost in absolute terms; senior Rust performance work is mostly noticing which costs you ordered without meaning to.

The practical allocation discipline, in descending payoff order: **reuse buffers** across iterations (`Vec::clear` keeps capacity; the `String` you pass back in beats the one you allocate fresh); **pre-size** with `with_capacity` when the length is knowable; **borrow instead of owning** in APIs (`&str` over `String` parameters; return `Cow` when mutation is conditional — Part 3.2); and for the structures profiling actually indicts, the specialized crates: [`smallvec`](https://docs.rs/smallvec/) (inline storage below a threshold — wins when most instances are small, *measure* because the branch isn't free), [`bytes`](https://docs.rs/bytes/) (reference-counted byte buffers for network code, making "slice this packet without copying" safe and cheap).

### 10.2 The knobs outside your code

Release-profile settings in `Cargo.toml` that move real numbers ([profiles reference](https://doc.rust-lang.org/cargo/reference/profiles.html)): `lto = "thin"` (cross-crate inlining at link time — frequently several percent for almost-free build-time cost; `"fat"` squeezes a bit more for a lot slower links), `codegen-units = 1` (stops parallel codegen from fragmenting optimization regions — slower builds, faster code), `panic = "abort"` where unwinding isn't needed (smaller, slightly faster, but no `catch_unwind` — mind Part 9.2). Beyond rustc: `-C target-cpu=native` for machines you control (vectorization unlocked by newer ISAs), **PGO** ([rustc book](https://doc.rust-lang.org/rustc/profile-guided-optimization.html)) for the dedicated (profile a representative run, recompile against it — low single-digit percent for real pipelines), and the **allocator swap**: the system allocator is replaceable in two lines (`#[global_allocator]`) with [jemalloc](https://docs.rs/tikv-jemallocator/) or [mimalloc](https://docs.rs/mimalloc/), and for allocation-heavy multithreaded services this is routinely a 5–20% throughput win — the highest return-on-effort optimization in this part. Measure on *your* workload; allocators trade memory footprint for speed differently.

### 10.3 Measurement, or it didn't happen

The toolchain: [`criterion`](https://docs.rs/criterion/) for microbenchmarks (statistically sound, regression-detecting; [`divan`](https://docs.rs/divan/) is the lighter modern alternative), [`cargo flamegraph`](https://github.com/flamegraph-rs/flamegraph) for where wall-time goes, [`dhat`](https://docs.rs/dhat/) for where *allocations* come from (the flamegraph of the other resource), `perf stat` for IPC and cache misses when you're optimizing seriously, and `cargo build --timings` when the thing that's slow is the build itself (monomorphization bloat shows up here — Part 1.1's hybrid trick is the cure). The two rules that prevent self-deception: **always `--release`** (debug builds are 10–100× slower and differently shaped — every conclusion drawn from one is noise), and **benchmark the realistic case** (criterion's micro-numbers on hot loops are honest; your service's p99 is governed by allocator behavior, cache pressure, and contention that micros don't see — close the loop with the flamegraph under production-shaped load).

```quiz
Q: What does "zero-cost abstraction" actually promise about an iterator chain?
- [ ] It performs no work at runtime
- [x] Zero overhead versus the equivalent hand-written loop — it monomorphizes and inlines to the same code, but costs you explicitly order (Box<dyn>, Arc::clone, collect) are still real
- [ ] It never allocates under any circumstances
- [ ] It compiles faster than the manual loop
> The promise is relative, not absolute: filter/map/sum becomes the tight loop you'd have written. Senior performance work is noticing the costs you ordered without meaning to — a vtable here, an atomic clone in a hot loop there, a 16 KB buffer held across an await making a 16 KB future.

Q: Which single change is called the highest return-on-effort optimization in this part?
- [ ] Rewriting hot paths with SIMD intrinsics
- [x] Swapping the global allocator for jemalloc or mimalloc — two lines, routinely 5–20% throughput for allocation-heavy multithreaded services
- [ ] panic = "abort" in the release profile
- [ ] Sprinkling #[inline(always)]
> #[global_allocator] is a two-line experiment with a real payoff profile. lto = "thin" and codegen-units = 1 are the other cheap knobs; PGO and target-cpu=native follow for the dedicated. Measure on your workload — allocators trade footprint for speed differently.

Q: Why is benchmarking a debug build self-deception?
- [x] Debug builds are 10–100× slower and *differently shaped* — bottlenecks move, so every conclusion is noise; always measure --release
- [ ] Debug builds disable atomics
- [ ] Debug symbols inflate cache pressure slightly
- [ ] It's fine if you scale the numbers by a constant
> Without optimization, iterators don't inline and bounds checks don't lift — the profile points at different code than production runs. The companion rule: micro-numbers are honest about hot loops, but p99 is governed by allocator, cache, and contention effects only a production-shaped flamegraph sees.
```

---

## Part 11 — Errors, Testing, and Verification

### 11.1 The two-crate error convention

The ecosystem settled the error-handling question into one sentence: **[`thiserror`](https://docs.rs/thiserror/) for libraries, [`anyhow`](https://docs.rs/anyhow/) for applications.** A library's errors are part of its contract — callers match on them — so they're precise enums with derived `Display`/`From`:

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum StoreError {
    #[error("item not found: {0}")]
    NotFound(String),
    #[error("backing store unavailable")]
    Io(#[from] std::io::Error),     // generates From<io::Error>, so `?` converts automatically
}

fn load(path: &str) -> Result<String, StoreError> {
    Ok(std::fs::read_to_string(path)?)   // io::Error → StoreError via #[from]
}
```

An application mostly *propagates* — what it needs is ergonomics and a readable causal trail, which is `anyhow`'s type-erased `Result` plus `.context()`:

```rust
use anyhow::{Context, Result};

fn start() -> Result<()> {
    let raw = std::fs::read_to_string("config.toml")
        .context("reading config.toml")?;
    let port: u16 = raw.trim().parse()
        .context("config must contain a port number")?;
    println!("listening on :{port}");
    Ok(())
}
```

The composed pattern — **typed at the boundaries, opaque in the middle** — is mainstream for a reason: the `?` operator with `#[from]` conversions makes the library side nearly ceremony-free, while `context` strings give operators error messages that read like a story instead of a type name. Two design notes that separate good error enums from noisy ones: model errors by *what the caller can do about them* (retryable vs. fatal vs. caller-bug), not by which function threw; and don't `#[from]` two sources of the same underlying type into one variant — you lose the distinction the enum exists to make.

### 11.2 Testing, the Rust-shaped parts

The basics are built in (`#[test]`, `cargo test`, integration tests in `tests/`, and **doctests** — examples in doc comments that compile and run, keeping documentation honest by construction). The advanced surface is what differs from other languages:

**Async tests** run under [`#[tokio::test]`](https://docs.rs/tokio/latest/tokio/attr.test.html), and the headline feature is **paused time**: `#[tokio::test(start_paused = true)]` makes timers virtual — `sleep(Duration::from_secs(3600))` advances instantly to the next timer rather than waiting — so timeout logic, retry backoff, and heartbeat code get *fast, deterministic* tests instead of flaky sleeps. This single feature removes the classic excuse for not testing time-dependent behavior.

**Concurrency tests** have a real answer: [`loom`](https://docs.rs/loom/) runs your lock-free or intricate-locking code under a model checker that explores *every legal interleaving and memory-model outcome* the orderings permit — the Part 5 bugs your laptop's scheduler would exhibit once a quarter become deterministic test failures. The cost is structure (loom shims `std::sync` types; the code under test imports them conditionally) and it's mandatory exactly where it's mandatory: any hand-written atomics deserve a loom test or they're untested by definition.

**Property-based testing** with [`proptest`](https://docs.rs/proptest/) (generate inputs, assert invariants, auto-shrink failures to minimal cases) covers the input space unit tests can't; **fuzzing** with [`cargo-fuzz`](https://rust-fuzz.github.io/book/) does the adversarial version against parsers and decoders — and the pairing with Rust is special: in C, a fuzzer finds crashes; in Rust, anything the fuzzer finds in safe code is by definition a logic bug or a panic, and anything it finds in `unsafe` is a soundness bug you absolutely wanted to know about. **Miri** (Part 8.3) completes the verification ladder for unsafe code.

### 11.3 The static layer

[Clippy](https://doc.rust-lang.org/clippy/) is not optional equipment: `cargo clippy -- -D warnings` in CI, with the lint groups tuned per project (the `pedantic` group has real signal for libraries; `undocumented_unsafe_blocks` should be `deny` anywhere Part 8 applies). `cargo fmt --check` ends formatting discussions. [`cargo-audit`](https://docs.rs/cargo-audit/)/[`cargo-deny`](https://embarkstudios.github.io/cargo-deny/) gate known-vulnerable and license-incompatible dependencies. The principle uniting this part with the rest of the guide: Rust's culture pushes *every* property it can — memory safety, thread safety, API misuse, even style — to the earliest checkable moment. Your test suite is for the properties that remain.

```quiz
Q: Why "thiserror for libraries, anyhow for applications"?
- [x] A library's errors are part of its contract — precise enums callers can match on; an application mostly propagates, needing ergonomics and a context trail more than types
- [ ] anyhow is faster at runtime
- [ ] thiserror doesn't work in binaries
- [ ] They're interchangeable; the split is historical
> Typed at the boundaries, opaque in the middle: #[from] makes the library side ceremony-free with ?, while .context() strings give operators errors that read like a story. Design note: model error variants by what the caller can *do* (retry? fatal? caller-bug?), not by which function threw.

Q: What does #[tokio::test(start_paused = true)] change?
- [ ] Tests run on a single thread
- [x] Timers become virtual — a one-hour sleep advances instantly to the next timer, so timeout/retry/backoff logic gets fast, deterministic tests
- [ ] Panics are converted to test failures
- [ ] All I/O is mocked automatically
> Paused time removes the classic excuse for not testing time-dependent behavior: no real sleeps, no flakiness. Retry backoff that would take minutes of wall clock runs in milliseconds, deterministically.

Q: When is loom mandatory rather than nice-to-have?
- [x] Any hand-written atomics — loom explores every legal interleaving and memory-model outcome, turning once-a-quarter heisenbugs into deterministic failures; without it the code is untested by definition
- [ ] Any use of tokio::spawn
- [ ] Code using Mutex or RwLock from std
- [ ] All async code
> Your laptop's scheduler exercises a handful of interleavings; the memory model permits vastly more. loom shims std::sync and model-checks the space. The verification ladder: clippy everywhere, Miri on unsafe, loom on atomics, proptest/fuzzing on parsers.

Q: What makes fuzzing Rust different from fuzzing C?
- [ ] Rust fuzzers run faster
- [x] In safe Rust, anything the fuzzer finds is a logic bug or panic, not memory corruption — and a crash in unsafe code is a soundness bug you urgently wanted to know about
- [ ] Rust code can't be fuzzed without FFI shims
- [ ] cargo-fuzz only finds UTF-8 issues
> In C a fuzzer hunts memory corruption; Rust's type system already abolished that class in safe code, so findings classify cleanly. Parsers and decoders are the natural targets — pair with proptest for invariant-style coverage.
```

---

## Part 12 — Macros

Macros are the part of advanced Rust most people use daily (`#[derive(...)]`, `println!`, `#[tokio::main]`) and write rarely — the right ratio. This part is sized accordingly: enough to write declarative macros confidently, read procedural ones, and know when each is the wrong tool.

### 12.1 Declarative macros: `macro_rules!`

A [`macro_rules!`](https://doc.rust-lang.org/book/ch20-05-macros.html) macro is pattern-matching over *token trees*: each rule matches a syntax shape (with typed fragments — `$x:expr`, `$name:ident`, `$t:ty`) and expands to code, with `$( ... )*` repetition handling variadic shapes — the reason `vec![1, 2, 3]` can exist in a language with no variadic functions:

```rust
// A tiny DSL: build a HashMap from key => value pairs.
macro_rules! map {
    ( $( $k:expr => $v:expr ),* $(,)? ) => {{      // $(,)? permits a trailing comma
        let mut m = std::collections::HashMap::new();
        $( m.insert($k, $v); )*                     // expand once per matched pair
        m
    }};
}

let scores = map! { "ada" => 95, "grace" => 97 };
```

Two properties make these safer than C's text macros: they're **hygienic** (identifiers introduced inside the macro can't capture or collide with the caller's variables) and they operate on parsed tokens, not strings. The legitimate uses are *removing structural duplication that functions and generics can't* — implementing a trait for many primitive types, table-driven test cases, small DSLs. The misuse is reaching for a macro where a function or generic would do: macros don't typecheck until expansion, produce worse errors, and resist refactoring tools. Exhaust the type system first; that's not a platitude, it's the order that keeps codebases readable. ([The Little Book of Rust Macros](https://veykril.github.io/tlborm/) is the standard deep reference.)

### 12.2 Procedural macros: how the magic you depend on works

Proc macros are *compiler plugins*: functions from `TokenStream` to `TokenStream`, living in a dedicated crate, in three flavors — **derive** (`#[derive(Serialize)]` — by far the most important: serde, thiserror, clap all live here), **attribute** (`#[tokio::main]`, rewriting the item they adorn), and **function-like** (`sqlx::query!`, which famously checks your SQL against a live database *at compile time*). The universal implementation stack is [`syn`](https://docs.rs/syn/) (parse the tokens into a syntax tree) + [`quote`](https://docs.rs/quote/) (template the output tokens), and the shape is always the same: parse the input item, walk its fields/variants, generate an impl.

You should be able to *read* a derive macro before you ever write one — pick `thiserror`'s source over a lunch break; it's a few hundred lines and demystifies the whole genre. Write one when, and only when, you find yourself maintaining the same impl by hand across many types: the cost side of the ledger (a separate crate, `syn`'s compile-time weight, opaque error spans unless you work at them, and tooling that can't see through you) is real, which is why the ecosystem's pattern is a few excellent proc-macro crates used by everyone rather than proc macros sprinkled through application code.

```quiz
Q: What makes macro_rules! macros safer than C preprocessor macros?
- [x] They're hygienic (introduced identifiers can't capture the caller's variables) and operate on parsed token trees, not text
- [ ] They're expanded at runtime where errors can be caught
- [ ] They can only expand to expressions
- [ ] They require unsafe blocks to define
> Hygiene plus typed fragments ($x:expr, $name:ident) means no C-style "evaluated the argument twice" or accidental variable capture. The $( ... )* repetition is also why vec![1, 2, 3] can exist in a language without variadic functions.

Q: When does the guide say to reach for a macro at all?
- [ ] Whenever a function would need more than three arguments
- [x] Only for structural duplication that functions and generics can't remove — trait impls over many primitive types, table-driven tests, small DSLs; exhaust the type system first
- [ ] To inline hot code paths
- [ ] To avoid writing documentation
> Macros don't typecheck until expansion, produce worse errors, and resist refactoring tools. "Exhaust the type system first" is an ordering, not a platitude — it's what keeps codebases readable.

Q: How does a derive macro like #[derive(Serialize)] actually work?
- [ ] The compiler has serde's logic built in
- [x] It's a compiler plugin — a function from TokenStream to TokenStream that parses the type with syn, walks its fields, and generates an impl with quote
- [ ] It generates code at runtime via reflection
- [ ] It modifies the struct's memory layout
> All three proc-macro flavors (derive, attribute like #[tokio::main], function-like like sqlx::query!) share the syn + quote stack and the same shape: parse, walk, generate. Reading thiserror's few hundred lines demystifies the genre.
```

---

## Part 13 — Production Service Patterns

The last mile: the patterns that keep a correct async service *operable*. The throughline is **bounding things** — bounded queues, bounded concurrency, bounded lifetimes, bounded shutdown time. The type system bought you correctness; ceilings buy you survivability.

### 13.1 Graceful shutdown

A production service drains instead of dropping: stop accepting new work, let in-flight work finish (with a deadline), then exit. The standard machinery is [`CancellationToken`](https://docs.rs/tokio-util/latest/tokio_util/sync/struct.CancellationToken.html) (clonable, hierarchical — cancel a parent, every child token fires) wired into each long-lived task's `select!`:

```rust
use tokio_util::sync::CancellationToken;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    let token = CancellationToken::new();
    let worker_token = token.clone();

    let worker = tokio::spawn(async move {
        loop {
            tokio::select! {
                _ = worker_token.cancelled() => break,          // shutdown requested
                _ = sleep(Duration::from_millis(100)) => { /* one unit of work */ }
            }
        }
        // post-loop: flush buffers, ack in-flight items — the DRAIN step
    });

    tokio::signal::ctrl_c().await.unwrap();
    token.cancel();                           // ask everyone to stop at their next await
    worker.await.unwrap();                    // and wait for the drain (add a timeout in prod)
}
```

Note how Part 7's themes pay off: the shutdown branch is a `select!` arm, so the loop body must be cancellation-safe; the drain step after the loop is the must-complete work that lives *outside* the cancellable region; and the final `await` with a deadline (wrap it in `tokio::time::timeout`) is the ceiling that turns a stuck task into a logged forced-exit instead of a hung deploy.

### 13.2 Backpressure: make load tell the truth

Every queue in the system is a policy decision. **Bounded channels** (`mpsc::channel(capacity)`) make a slow consumer slow its producers — latency rises, throughput honestly saturates, and the system *signals* its limit; an unbounded channel converts the identical situation into unbounded memory growth and an OOM kill, hours later, far from the cause. The same principle at each tier: cap in-flight requests with a `Semaphore` (return 429/503 when full — load shedding is backpressure at the edge), cap connection pools, and put deadlines on everything that waits (`timeout` around every upstream call — an unbounded await is an unbounded queue of one). When the system is saturated, these ceilings are what make it degrade *predictably* — the difference between "p99 doubled" and "the service fell over."

### 13.3 Observability

[`tracing`](https://docs.rs/tracing/) is the standard: structured events inside **spans** that follow causality across `.await`s and `spawn`s (the `#[instrument]` attribute macro gives a function a span with its arguments as fields for one line of code), with subscribers fanning out to JSON logs, OpenTelemetry, or the console. Add `tokio-console` (Part 7.7) in staging for runtime-level visibility, and a metrics facade ([`metrics`](https://docs.rs/metrics/) or OpenTelemetry) for the dashboards. The async-specific discipline: never log-and-drop a `JoinHandle`'s error — task panics that vanish silently are the async equivalent of an empty `catch` block, and wiring `JoinSet` results into error logs is what makes 3 a.m. debuggable.

```quiz
Q: In the graceful-shutdown pattern, why does the drain step live *after* the select! loop rather than inside it?
- [x] Inside the loop it's in the cancellable region — the drain is must-complete work, so it runs after the cancellation branch breaks out, with a timeout as the ceiling
- [ ] select! arms can't contain I/O
- [ ] The CancellationToken can't fire twice
- [ ] Rust's Drop handles draining automatically
> The loop body must be cancellation-safe because shutdown is a select! arm; the flush/ack work that must finish lives outside the cancellable region. The final await gets a timeout so a stuck task becomes a logged forced-exit, not a hung deploy — and async Drop doesn't exist, so teardown is explicit.

Q: What does CancellationToken add over a plain watch channel for shutdown?
- [ ] It forcibly kills tasks that ignore it
- [x] It's clonable and hierarchical — cancelling a parent fires every child token, so a task tree shuts down as a tree
- [ ] It bypasses cancellation safety concerns
- [ ] It works without an async runtime
> Tokens compose with task structure: each long-lived task selects on its token, and one cancel() at the root reaches the whole hierarchy. Tasks still stop only at their next await — cooperative cancellation, like everything async.

Q: Why is dropping a JoinHandle without checking its result an operational bug?
- [ ] It leaks the task's memory permanently
- [x] A panic in that task vanishes silently — the async equivalent of an empty catch block; wire JoinSet results into error logs
- [ ] It cancels the task immediately
- [ ] It blocks the worker thread
> Detached tasks are untracked failure domains. The structured-concurrency smell test from Part 7 applies: if you can't answer "who awaits this task and what happens when it fails?", the spawn will eventually page someone — with no log line to start from.
```

---

## Capstone Projects

Build these to turn the concepts into instincts. Each forces a different hard part to be correct, and each names the parts it exercises.

**Project 1: Concurrent TCP chat server** — Tokio, `tokio::net::TcpListener`, a `broadcast` channel, `select!`, graceful shutdown. Accept many clients; fan each message out to all others; shut down cleanly on Ctrl-C, *draining* in-flight messages. Each connection is a task `select!`-ing between socket readability and the broadcast — which makes every Part 7 discipline load-bearing at once: cancellation safety in the select loop, `Send + 'static` bounds on the per-connection task, lagging-receiver policy on the broadcast channel, and a shutdown that proves your drain logic instead of asserting it.

**Project 2: Bounded job processor** — bounded `mpsc`, a fixed worker pool, `Semaphore` concurrency caps, `CancellationToken`, and `criterion` benchmarks of throughput under saturation. This is Part 13 made concrete: when the queue is full, producers must *feel* it; when shutdown fires, in-flight jobs finish and queued jobs drain to a deadline. Extend it with per-job timeouts and retry-with-backoff to meet cancellation safety again from the other side.

**Project 3: Safe wrapper over a C library** — `bindgen`, a `-sys` crate, `CString`/`CStr`, `catch_unwind` at every export, and a safe API that makes misuse unrepresentable. Bind a small real library (compression or hashing); the deliverable that matters is the *boundary design*: raw unsafe surface in one module, SAFETY comments on every block, Miri on the test suite, and a public API through which no sequence of safe calls can reach UB. This is Parts 8–9 as a single discipline.

**Project 4: Lock-free metrics registry** — sharded `AtomicU64` counters, `Ordering` choices you can justify in comments, a `loom` test of the interesting interleavings, and a `criterion` comparison against `Mutex<HashMap>` under 1, 4, and 16 threads of contention. The goal is calibration, not just code: discover empirically where the lock actually loses (it's later than you think), and exit with the Part 5 honest line — atomics for counters and flags, locks for everything unproven — written in your own benchmark numbers.

---

## Study Methodology

1. **Walk the ladder in order**: type system → lifetimes/layout → threads → atomics → async → unsafe/FFI. Async builds on `Send`/`Sync` and closures; `Pin` builds on the self-reference wall; FFI builds on layout and unsafe. Skipping ahead is why async feels like magic — the foundations *are* the explanation.
2. **Read compiler errors as design feedback.** "Not `Send`," "does not live long enough," "cannot be made into an object" — each is a true statement about your ownership story with a fix attached. Treat them as questions about the design, not syntax puzzles to appease.
3. **Pick one runtime and learn it deeply.** Tokio: its scheduler, `spawn_blocking`, cancellation behavior, and `tokio-console` — before touching alternatives. Runtime knowledge compounds; runtime tourism doesn't.
4. **Make verification a habit, scaled to the risk**: clippy everywhere; `--release` for every benchmark; Miri on any crate with `unsafe`; `loom` on any hand-written atomics; proptest/fuzzing on any parser. The tools exist so that "I think it's correct" can be upgraded sentence by sentence to "it's checked."
5. **Confine `unsafe` and prove it.** Every block gets a `// SAFETY:` comment stating the invariant it relies on. If you can't write the comment, you can't write the block.
6. **Default to ownership-moving designs**: channels before shared locks, scoped threads before `Arc`, structured task groups before loose spawns. Add shared mutable state when a profiler — not a hunch — justifies it.
7. **Bound everything in production**: queues, concurrency, timeouts, shutdown. Correctness comes from the type system; staying up comes from ceilings.

The point of the sequence, one last time: Rust's "hard" topics are one idea wearing different costumes — **encode the invariant in the type system so violations don't compile**, and where the type system can't reach (memory orderings, unsafe contracts, cancellation windows), *name the invariant explicitly and test it with the tool built for exactly that gap*. Once you see `Send`, `Pin`, lifetimes, `unsafe`, and even `loom` as that same move at different layers, the language stops feeling like a pile of special cases and starts feeling like one design, applied relentlessly.

---

## Additional Reference Links

- **Core & official**: [The Rust Programming Language](https://doc.rust-lang.org/book/) · [The Rustonomicon](https://doc.rust-lang.org/nomicon/) · [The Async Book](https://rust-lang.github.io/async-book/) · [Rust Reference](https://doc.rust-lang.org/reference/) · [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) · [std docs](https://doc.rust-lang.org/std/)
- **Concurrency & async**: [*Rust Atomics and Locks*](https://marabos.nl/atomics/) (Mara Bos, free online) · [Tokio tutorial](https://tokio.rs/tokio/tutorial) · [Tokio docs](https://docs.rs/tokio/) · [`std::sync`](https://doc.rust-lang.org/std/sync/) / [`std::sync::atomic`](https://doc.rust-lang.org/std/sync/atomic/) · [`std::pin`](https://doc.rust-lang.org/std/pin/) · [`pin-project`](https://docs.rs/pin-project/) · [`rayon`](https://docs.rs/rayon/) · [`crossbeam`](https://docs.rs/crossbeam/) · [tokio-console](https://github.com/tokio-rs/console) · [`loom`](https://docs.rs/loom/)
- **Errors, testing, verification**: [`thiserror`](https://docs.rs/thiserror/) · [`anyhow`](https://docs.rs/anyhow/) · [Miri](https://github.com/rust-lang/miri) · [`proptest`](https://docs.rs/proptest/) · [cargo-fuzz / Rust Fuzz Book](https://rust-fuzz.github.io/book/) · [Clippy lint list](https://rust-lang.github.io/rust-clippy/master/)
- **FFI & macros**: [Nomicon FFI chapter](https://doc.rust-lang.org/nomicon/ffi.html) · [`bindgen`](https://rust-lang.github.io/rust-bindgen/) · [`cbindgen`](https://github.com/mozilla/cbindgen) · [PyO3](https://pyo3.rs/) · [The Little Book of Rust Macros](https://veykril.github.io/tlborm/) · [`syn`](https://docs.rs/syn/) / [`quote`](https://docs.rs/quote/)
- **Performance**: [The Rust Performance Book](https://nnethercote.github.io/perf-book/) (Nethercote — read it cover to cover) · [`criterion`](https://docs.rs/criterion/) · [cargo-flamegraph](https://github.com/flamegraph-rs/flamegraph) · [`dhat`](https://docs.rs/dhat/)
- **Deepen further**: [Jon Gjengset — *Rust for Rustaceans* and the "Crust of Rust" series](https://www.youtube.com/c/JonGjengset) · [This Week in Rust](https://this-week-in-rust.org/) for tracking the language's motion

Use the references as a map, not a substitute for the compiler. The fastest way to learn advanced Rust remains: write code that doesn't compile, read what the compiler says, fix the *design* it's pointing at — then confirm your mental model against the docs above.

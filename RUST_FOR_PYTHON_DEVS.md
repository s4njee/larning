# Rust for Python Developers

A study guide that skips the basics and focuses on what actually trips up Python developers learning Rust. Covers ownership, borrowing, lifetimes, concurrency, and the mental shifts required.

---

## Table of Contents

1. [The Mental Shift: Why Rust Feels Hard](#1-the-mental-shift-why-rust-feels-hard)
2. [Ownership & Move Semantics](#2-ownership--move-semantics)
3. [Borrowing & References](#3-borrowing--references)
4. [Lifetimes](#4-lifetimes)
5. [Enums, Pattern Matching & Option/Result](#5-enums-pattern-matching--optionresult)
6. [Error Handling](#6-error-handling)
7. [Structs, Traits & Polymorphism](#7-structs-traits--polymorphism)
8. [Generics & Trait Bounds](#8-generics--trait-bounds)
9. [Closures & Iterators](#9-closures--iterators)
10. [Concurrency & Parallelism](#10-concurrency--parallelism)
11. [Async/Await](#11-asyncawait)
12. [Smart Pointers & Interior Mutability](#12-smart-pointers--interior-mutability)
13. [Modules, Crates & Visibility](#13-modules-crates--visibility)
14. [Testing](#14-testing)
15. [Strings (Yes, They Deserve Their Own Section)](#15-strings-yes-they-deserve-their-own-section)
16. [Common Pitfalls for Python Developers](#16-common-pitfalls-for-python-developers)

---

## 1. The Mental Shift: Why Rust Feels Hard

Official docs: [The Rust Book: Variables and Mutability](https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html), [The Rust Book: Understanding Ownership](https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html)

### What Rust Does Differently

Python manages memory for you with reference counting and garbage collection. You never think about when objects are freed. Rust has **no garbage collector** -- instead, the compiler enforces strict rules about who owns data, who can borrow it, and when it's freed.

| | Python | Rust |
|---|---|---|
| Memory management | GC + reference counting | Ownership system (compile-time) |
| Null | `None` on any variable | No null -- use `Option<T>` |
| Exceptions | `try/except` | No exceptions -- use `Result<T, E>` |
| Mutability | Everything mutable by default | Everything **immutable** by default |
| Type system | Dynamic, optional hints | Static, strict, inferred |
| Runtime cost | Interpreter overhead | Zero-cost abstractions |
| Data races | GIL hides most (but not all) | **Impossible** at compile time |

### The Compiler Is Your Pair Programmer

In Python, bugs show up at runtime. In Rust, the compiler catches entire categories of bugs before the code runs:
- Use-after-free
- Double-free
- Data races
- Null pointer dereferences
- Buffer overflows

The tradeoff: **you'll fight the compiler**. This is normal. The compiler errors are detailed and usually tell you exactly how to fix the problem. Read them carefully.

### Immutable by Default

```rust
let x = 5;       // immutable
// x = 6;        // compile error!

let mut y = 5;   // mutable -- must opt in
y = 6;           // fine
```

```python
x = 5
x = 6  # always fine -- Python has no concept of immutable bindings
```

---

## 2. Ownership & Move Semantics

Official docs: [The Rust Book: What Is Ownership?](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html), [`Copy`](https://doc.rust-lang.org/std/marker/trait.Copy.html), [`Clone`](https://doc.rust-lang.org/std/clone/trait.Clone.html)

### The Three Rules of Ownership

1. Each value in Rust has exactly **one owner**
2. When the owner goes out of scope, the value is **dropped** (freed)
3. Ownership can be **transferred** (moved), but then the original variable is invalid

### Move Semantics (The Python Brain-Breaker)

```rust
let s1 = String::from("hello");
let s2 = s1;        // s1 is MOVED to s2

// println!("{}", s1);  // compile error: s1 is no longer valid
println!("{}", s2);     // fine
```

```python
s1 = "hello"
s2 = s1       # both s1 and s2 point to the same object
print(s1)     # fine -- Python uses reference counting
print(s2)     # fine
```

In Python, assignment creates another reference. In Rust, assignment **transfers ownership** -- the original variable is dead.

### Copy vs Move

Some types are cheap to copy and implement the `Copy` trait. These are copied instead of moved:

```rust
let x = 42;     // i32 implements Copy
let y = x;      // x is COPIED, not moved
println!("{x}"); // fine -- x is still valid

let s1 = String::from("hello");  // String does NOT implement Copy
let s2 = s1;                      // MOVED
// println!("{s1}");              // error
```

| Copy types (stack-only) | Move types (heap data) |
|---|---|
| `i32`, `f64`, `bool`, `char` | `String`, `Vec<T>`, `HashMap` |
| Tuples of Copy types | `Box<T>`, any struct with heap data |
| Arrays of Copy types | Most custom structs (unless you derive Copy) |

### Clone -- Explicit Deep Copy

```rust
let s1 = String::from("hello");
let s2 = s1.clone();   // explicit deep copy
println!("{s1}");       // fine -- s1 was cloned, not moved
```

Python's equivalent is `copy.deepcopy()`, but in Python you rarely need it because the GC handles everything.

### Ownership and Functions

```rust
fn takes_ownership(s: String) {
    println!("{s}");
}   // s is dropped here

fn main() {
    let s = String::from("hello");
    takes_ownership(s);
    // println!("{s}");  // error: s was moved into the function
}
```

```python
def takes_value(s):
    print(s)

s = "hello"
takes_value(s)
print(s)  # fine -- Python doesn't transfer ownership
```

To "give back" ownership, return the value:

```rust
fn takes_and_gives_back(s: String) -> String {
    println!("{s}");
    s  // return ownership to the caller
}
```

But this gets tedious -- which is why **borrowing** exists.

---

## 3. Borrowing & References

Official docs: [The Rust Book: References and Borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html), [The Rust Book: Slices](https://doc.rust-lang.org/book/ch04-03-slices.html)

### References Let You Use Data Without Taking Ownership

```rust
fn calculate_length(s: &String) -> usize {  // borrows s
    s.len()
}   // s goes out of scope, but since it doesn't own the String, nothing is dropped

fn main() {
    let s = String::from("hello");
    let len = calculate_length(&s);  // lend s
    println!("{s} has length {len}"); // s is still valid
}
```

### The Borrowing Rules

1. You can have **either** (not both at the same time):
   - Any number of **immutable references** (`&T`)
   - Exactly **one mutable reference** (`&mut T`)
2. References must always be **valid** (no dangling references)

```rust
let mut s = String::from("hello");

let r1 = &s;      // immutable borrow -- fine
let r2 = &s;      // another immutable borrow -- fine
// let r3 = &mut s;  // ERROR: can't borrow mutably while immutable borrows exist

println!("{r1} {r2}");
// r1 and r2 are no longer used after this point (NLL - Non-Lexical Lifetimes)

let r3 = &mut s;  // fine now -- r1 and r2 are done
r3.push_str(" world");
```

### Why This Rule Exists

This prevents data races **at compile time**:
- Multiple readers OR one writer, never both
- No iterator invalidation
- No concurrent mutation bugs

Python "solves" this with the GIL (for threads) or just lets you shoot yourself in the foot (mutating a list while iterating it).

### Mutable References

```rust
fn append_world(s: &mut String) {
    s.push_str(" world");
}

fn main() {
    let mut s = String::from("hello");
    append_world(&mut s);
    println!("{s}");  // "hello world"
}
```

### Slices -- Borrowing Parts of Data

```rust
let s = String::from("hello world");
let hello: &str = &s[0..5];   // string slice -- borrows part of s
let world: &str = &s[6..11];

let nums = vec![1, 2, 3, 4, 5];
let mid: &[i32] = &nums[1..4];  // [2, 3, 4] -- slice of the vector
```

Slices are **borrowed views** -- they don't own data. This is like Python's `memoryview`, but enforced at compile time.

---

## 4. Lifetimes

Official docs: [The Rust Book: Validating References with Lifetimes](https://doc.rust-lang.org/book/ch10-03-lifetime-syntax.html), [The Rust Reference: Lifetime elision](https://doc.rust-lang.org/reference/lifetime-elision.html)

This is the section that tends to look the most mysterious to Python developers, mostly because the syntax makes it seem like lifetimes are a special advanced type system. In practice, lifetimes are just Rust's way of describing relationships between borrows: which reference depends on which piece of data staying alive.

The important mindset shift is that a lifetime is usually not "how long an object lives" in a wall-clock sense. It is a compile-time proof that one reference cannot outlast the value it points at. Once that clicks, the annotations stop feeling like magic punctuation and start reading like contracts.

### What Are Lifetimes?

Lifetimes are the compiler's way of ensuring references don't outlive the data they point to. Most of the time, the compiler infers them automatically. You only write them explicitly when the compiler can't figure it out.

### The Dangling Reference Problem

```rust
// This won't compile:
fn dangling() -> &String {
    let s = String::from("hello");
    &s  // ERROR: s is dropped when function returns, reference would dangle
}
```

Python never has this problem because the GC keeps objects alive as long as any reference exists.

### Explicit Lifetime Annotations

```rust
// "The returned reference lives as long as both input references are valid"
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```

Read `'a` as "lifetime a". This tells the compiler: the returned reference is valid for as long as **both** `x` and `y` are valid.

More precisely, the returned reference is valid for the shorter of the two input lifetimes. That is why `longest` is safe: the compiler knows the result cannot outlive either input, so any caller must keep both borrowed values alive long enough.

```rust
fn main() {
    let string1 = String::from("long string");
    let result;
    {
        let string2 = String::from("xyz");
        result = longest(&string1, &string2);
        println!("{result}");  // fine -- both strings alive
    }
    // println!("{result}");  // ERROR: string2 is dropped, result might reference it
}
```

### Lifetime Elision Rules

The compiler automatically infers lifetimes in common cases. You usually only need explicit lifetimes when:

1. A function returns a reference and has multiple reference parameters
2. A struct stores references

```rust
// Compiler infers this:
fn first_word(s: &str) -> &str { /* ... */ }
// As if you wrote:
fn first_word<'a>(s: &'a str) -> &'a str { /* ... */ }
```

### Lifetimes in Structs

If a struct holds a reference, it needs a lifetime annotation:

```rust
struct Excerpt<'a> {
    text: &'a str,  // this struct borrows a string
}

fn main() {
    let novel = String::from("Call me Ishmael. Some years ago...");
    let first_sentence = &novel[..16];
    let excerpt = Excerpt { text: first_sentence };
    // excerpt can't outlive novel
}
```

### `'static` Lifetime

```rust
// 'static means the reference lives for the entire program
let s: &'static str = "I'm a string literal";  // embedded in the binary
```

Beginners often overuse `'static` because it sounds like "the easy lifetime." Usually it is not what you want. In most code, if the compiler asks for a lifetime, the fix is to own the data with `String`, `Vec<T>`, or `Arc<T>`, not to force everything toward `'static`.

---

## 5. Enums, Pattern Matching & Option/Result

Official docs: [The Rust Book: Enums and Pattern Matching](https://doc.rust-lang.org/book/ch06-00-enums.html), [The Rust Book: `match` Control Flow](https://doc.rust-lang.org/book/ch06-02-match.html), [`Option`](https://doc.rust-lang.org/std/option/enum.Option.html), [`Result`](https://doc.rust-lang.org/std/result/enum.Result.html)

### Enums Are Not Python Enums

Rust enums can hold **data in each variant** -- they're closer to tagged unions or algebraic data types.

```rust
enum Shape {
    Circle(f64),                    // holds radius
    Rectangle(f64, f64),            // holds width, height
    Triangle { a: f64, b: f64, c: f64 },  // named fields
    Point,                          // no data
}
```

```python
# Python enums are just named constants
from enum import Enum

class Shape(Enum):
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    # Can't hold per-variant data
```

### Pattern Matching with `match`

```rust
fn area(shape: &Shape) -> f64 {
    match shape {
        Shape::Circle(r) => std::f64::consts::PI * r * r,
        Shape::Rectangle(w, h) => w * h,
        Shape::Triangle { a, b, c } => {
            let s = (a + b + c) / 2.0;
            (s * (s - a) * (s - b) * (s - c)).sqrt()
        }
        Shape::Point => 0.0,
    }
}
```

`match` is **exhaustive** -- you must handle every variant or use a wildcard `_`. The compiler enforces this.

```python
# Python 3.10+ structural pattern matching
match shape:
    case Circle(r):
        return math.pi * r ** 2
    case _:
        return 0
    # But it's not exhaustive -- missing cases just fall through
```

### `Option<T>` -- Rust's Replacement for `None`

There is no `null`/`None` that any variable can hold. Instead, "might be absent" is explicit:

```rust
enum Option<T> {
    Some(T),    // has a value
    None,       // no value
}

fn find_user(id: u64) -> Option<User> {
    if id == 1 {
        Some(User { name: "Alice".into() })
    } else {
        None
    }
}

// You MUST handle both cases
match find_user(42) {
    Some(user) => println!("Found: {}", user.name),
    None => println!("User not found"),
}
```

```python
# Python: None can appear anywhere, crashes are at runtime
def find_user(id: int) -> User | None:
    ...

user = find_user(42)
print(user.name)  # AttributeError at runtime if None
```

### Common `Option` Methods

```rust
let x: Option<i32> = Some(42);

x.unwrap();              // 42 -- panics if None (like Python's crash)
x.unwrap_or(0);          // 42, or 0 if None
x.unwrap_or_default();   // uses the type's default value if None
x.map(|v| v * 2);        // Some(84)
x.and_then(|v| if v > 0 { Some(v) } else { None });
x.is_some();             // true
x.is_none();             // false

// if let -- handle only the Some case
if let Some(value) = x {
    println!("Got {value}");
}
```

### `Result<T, E>` -- Rust's Replacement for Exceptions

`Option<T>` answers "is there a value?" while `Result<T, E>` answers "did the operation succeed?" That split is one of Rust's best design choices because it forces APIs to distinguish ordinary absence from an actual failure condition.

```rust
enum Result<T, E> {
    Ok(T),     // success
    Err(E),    // failure
}

fn parse_number(s: &str) -> Result<i32, std::num::ParseIntError> {
    s.parse::<i32>()
}

match parse_number("42") {
    Ok(n) => println!("Parsed: {n}"),
    Err(e) => println!("Failed: {e}"),
}
```

---

## 6. Error Handling

Official docs: [The Rust Book: Error Handling](https://doc.rust-lang.org/book/ch09-00-error-handling.html), [`Result`](https://doc.rust-lang.org/std/result/enum.Result.html)

Rust error handling gets much easier once you separate library concerns from application concerns. Libraries should preserve structure so callers can inspect failures. Applications often just need good context and a clean error chain for logs or CLI output.

### No Exceptions, No try/except

Rust uses `Result<T, E>` for all recoverable errors. The compiler forces you to handle them.

```rust
use std::fs;
use std::io;

fn read_config(path: &str) -> Result<String, io::Error> {
    let content = fs::read_to_string(path)?;  // ? propagates errors
    Ok(content)
}
```

```python
def read_config(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except OSError as e:
        raise RuntimeError(f"reading config: {e}") from e
```

### The `?` Operator -- Rust's Error Propagation

The `?` operator is the single most important thing to learn. It replaces hundreds of lines of match statements:

```rust
// Without ?
fn read_username() -> Result<String, io::Error> {
    let file_result = fs::read_to_string("username.txt");
    let username = match file_result {
        Ok(content) => content,
        Err(e) => return Err(e),
    };
    Ok(username.trim().to_string())
}

// With ? (identical behavior)
fn read_username() -> Result<String, io::Error> {
    let username = fs::read_to_string("username.txt")?;
    Ok(username.trim().to_string())
}

// Chained
fn read_username() -> Result<String, io::Error> {
    Ok(fs::read_to_string("username.txt")?.trim().to_string())
}
```

`?` does: if `Err`, return the error immediately from the function. If `Ok`, unwrap the value and continue.

This is why Rust error-handling code often reads linearly even without exceptions. Instead of building nested control flow, you keep the happy path visible and let `?` short-circuit failure paths in a type-safe way.

### Custom Error Types

```rust
use thiserror::Error;  // popular crate

#[derive(Error, Debug)]
enum AppError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Parse error: {0}")]
    Parse(#[from] serde_json::Error),

    #[error("User {id} not found")]
    NotFound { id: u64 },
}

fn load_user(id: u64) -> Result<User, AppError> {
    let data = fs::read_to_string("users.json")?;  // io::Error auto-converts
    let users: Vec<User> = serde_json::from_str(&data)?;  // also auto-converts
    users.into_iter()
        .find(|u| u.id == id)
        .ok_or(AppError::NotFound { id })
}
```

### `anyhow` for Application Code

```rust
use anyhow::{Context, Result};

fn main() -> Result<()> {
    let config = fs::read_to_string("config.toml")
        .context("Failed to read config file")?;

    let port: u16 = config.parse()
        .context("Invalid port number")?;

    Ok(())
}
```

Use `thiserror` for libraries (structured errors), `anyhow` for applications (convenient error chaining).

That distinction matters. If you are publishing a library, callers may want to `match` on specific failures. If you are writing a binary, preserving every intermediate error type is often more work than value, and `anyhow` keeps the code readable.

### When to `unwrap()` and `expect()`

```rust
// unwrap -- panics with generic message if Err/None
let value = some_result.unwrap();

// expect -- panics with YOUR message
let value = some_result.expect("database should be reachable");

// Only use these when:
// 1. You're prototyping
// 2. You can prove it won't fail
// 3. Failure means a bug in your code (not a runtime condition)
```

---

## 7. Structs, Traits & Polymorphism

Official docs: [The Rust Book: Using Structs to Structure Related Data](https://doc.rust-lang.org/book/ch05-00-structs.html), [The Rust Book: Traits](https://doc.rust-lang.org/book/ch10-02-traits.html), [The Rust Book: Trait Objects](https://doc.rust-lang.org/book/ch18-02-trait-objects.html), [`std::ops::Add`](https://doc.rust-lang.org/std/ops/trait.Add.html)

### Structs (Not Classes)

```rust
struct User {
    name: String,
    email: String,
    age: u32,
}

impl User {
    // Associated function (like __init__ / classmethod)
    fn new(name: &str, email: &str, age: u32) -> Self {
        Self {
            name: name.to_string(),
            email: email.to_string(),
            age,
        }
    }

    // Method (takes &self, &mut self, or self)
    fn greet(&self) -> String {
        format!("Hi, I'm {}", self.name)
    }

    fn set_email(&mut self, email: &str) {
        self.email = email.to_string();
    }
}
```

```python
class User:
    def __init__(self, name: str, email: str, age: int):
        self.name = name
        self.email = email
        self.age = age

    def greet(self) -> str:
        return f"Hi, I'm {self.name}"
```

### Traits -- Rust's Interfaces

Traits define shared behavior. They're like Python's ABCs or Go's interfaces, but explicit.

They are also more central than Python interfaces usually are. Traits power generic constraints, operator overloading, formatting, iteration, conversion, async behavior, and much of the standard library's design. Once you understand traits, a lot of Rust APIs stop feeling arbitrary.

```rust
trait Drawable {
    fn draw(&self);

    // Default implementation (like a mixin)
    fn description(&self) -> String {
        String::from("a drawable object")
    }
}

struct Circle {
    radius: f64,
}

impl Drawable for Circle {
    fn draw(&self) {
        println!("Drawing circle with radius {}", self.radius);
    }
    // description() uses the default
}
```

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self): ...

    def description(self) -> str:  # default implementation
        return "a drawable object"

class Circle(Drawable):
    def __init__(self, radius: float):
        self.radius = radius

    def draw(self):
        print(f"Drawing circle with radius {self.radius}")
```

### No Inheritance -- Composition Instead

Like Go, Rust has no class inheritance. You compose behavior through:

1. **Trait implementation** -- a type can implement many traits
2. **Struct composition** -- embed structs inside other structs
3. **Trait objects** -- dynamic dispatch when needed

### Trait Objects (Dynamic Dispatch)

Most Rust code prefers static dispatch through generics because it is fast and keeps types concrete. Trait objects are the escape hatch when you need heterogenous collections, plugin-style behavior, or runtime polymorphism.

```rust
// Static dispatch (monomorphization) -- fast, but one concrete type
fn draw_it(item: &impl Drawable) {
    item.draw();
}

// Dynamic dispatch (trait object) -- multiple types at runtime
fn draw_all(items: &[&dyn Drawable]) {
    for item in items {
        item.draw();
    }
}

// Box<dyn Trait> for owned trait objects
fn create_shape(kind: &str) -> Box<dyn Drawable> {
    match kind {
        "circle" => Box::new(Circle { radius: 5.0 }),
        "square" => Box::new(Square { side: 3.0 }),
        _ => panic!("unknown shape"),
    }
}
```

```python
# Python: dynamic dispatch is the default
def draw_all(items: list[Drawable]):
    for item in items:
        item.draw()  # always dynamic dispatch
```

The tradeoff is worth being explicit about: `impl Trait` usually gives better performance and better compiler visibility, while `dyn Trait` buys flexibility at the cost of an indirection and some lost compile-time specialization.

### Deriving Common Traits

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct Point {
    x: i32,
    y: i32,
}

// Debug     -> like __repr__     -> {:?} formatting
// Clone     -> like copy.deepcopy -> .clone()
// PartialEq -> like __eq__       -> == operator
// Hash      -> like __hash__     -> usable as HashMap key
```

### Operator Overloading via Traits

```rust
use std::ops::Add;

#[derive(Debug, Clone, Copy)]
struct Vec2 {
    x: f64,
    y: f64,
}

impl Add for Vec2 {
    type Output = Vec2;

    fn add(self, other: Vec2) -> Vec2 {
        Vec2 {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
}

let a = Vec2 { x: 1.0, y: 2.0 };
let b = Vec2 { x: 3.0, y: 4.0 };
let c = a + b;  // Vec2 { x: 4.0, y: 6.0 }
```

---

## 8. Generics & Trait Bounds

Official docs: [The Rust Book: Generic Types, Traits, and Lifetimes](https://doc.rust-lang.org/book/ch10-00-generics.html), [The Rust Book: Traits](https://doc.rust-lang.org/book/ch10-02-traits.html)

### Generic Functions

```rust
fn largest<T: PartialOrd>(list: &[T]) -> &T {
    let mut max = &list[0];
    for item in &list[1..] {
        if item > max {
            max = item;
        }
    }
    max
}

largest(&[1, 5, 3]);         // works with i32
largest(&[1.5, 0.2, 3.8]);   // works with f64
```

### Trait Bounds

Trait bounds constrain what a generic type can do:

```rust
// Single bound
fn print_it<T: Display>(item: T) {
    println!("{item}");
}

// Multiple bounds
fn compare_and_print<T: Display + PartialOrd>(a: T, b: T) {
    if a > b { println!("{a}") } else { println!("{b}") }
}

// where clause (cleaner for complex bounds)
fn process<T, U>(t: T, u: U) -> String
where
    T: Display + Clone,
    U: Debug + Into<String>,
{
    format!("{t} and {:?}", u)
}
```

This is the Rust version of saying "generic, but not unconstrained." Python developers often reach for `TypeVar` bounds mostly for documentation and static tooling. In Rust, the bound is part of what makes the code legal in the first place.

### Compared to Python

```python
# Python generics are for type checkers only -- no runtime enforcement
from typing import TypeVar

T = TypeVar('T', bound=Comparable)

def largest(items: list[T]) -> T:
    return max(items)  # works... but no compile-time guarantee
```

Rust generics are **monomorphized** -- the compiler generates specialized code for each concrete type used. Zero runtime cost.

That is why Rust generics usually feel closer to templates in C++ than to Python's type hints. You get strong static guarantees and optimized concrete code, but compile times and binary size can grow when a generic API is instantiated many different ways.

### Generic Structs

```rust
struct Cache<K, V> {
    data: HashMap<K, V>,
}

impl<K: Eq + Hash, V> Cache<K, V> {
    fn new() -> Self {
        Cache { data: HashMap::new() }
    }

    fn get(&self, key: &K) -> Option<&V> {
        self.data.get(key)
    }

    fn set(&mut self, key: K, value: V) {
        self.data.insert(key, value);
    }
}
```

---

## 9. Closures & Iterators

Official docs: [The Rust Book: Closures](https://doc.rust-lang.org/book/ch13-01-closures.html), [The Rust Book: Iterators](https://doc.rust-lang.org/book/ch13-02-iterators.html)

### Closures

```rust
let add = |a, b| a + b;       // type inferred
let add: fn(i32, i32) -> i32 = |a, b| a + b;  // explicit

let mut count = 0;
let mut increment = || {       // captures count by mutable reference
    count += 1;
    count
};
increment();  // 1
increment();  // 2
```

### Closure Capture Modes

This is where Rust closures differ from Python -- they interact with the ownership system:

| Trait | Captures by | Python equivalent |
|---|---|---|
| `Fn` | Immutable reference (`&T`) | Normal closure |
| `FnMut` | Mutable reference (`&mut T`) | Closure that mutates outer variable |
| `FnOnce` | Ownership (move) | No direct equivalent |

```rust
// Fn -- borrows immutably
let name = String::from("Alice");
let greet = || println!("Hello, {name}");
greet();
greet();           // can call multiple times
println!("{name}"); // name still accessible

// FnOnce -- takes ownership
let name = String::from("Alice");
let consume = move || println!("Consumed: {name}");
consume();
// println!("{name}");  // error: name was moved into closure
```

### Iterators -- Rust's List Comprehensions

Python has list comprehensions. Rust has **iterator chains** -- they're lazy and zero-cost.

```python
# Python
result = [x ** 2 for x in range(10) if x % 2 == 0]
```

```rust
// Rust
let result: Vec<i32> = (0..10)
    .filter(|x| x % 2 == 0)
    .map(|x| x * x)
    .collect();
```

### Common Iterator Methods

```rust
let nums = vec![1, 2, 3, 4, 5];

nums.iter().map(|x| x * 2);              // [2, 4, 6, 8, 10]
nums.iter().filter(|&&x| x > 3);          // [4, 5]
nums.iter().fold(0, |acc, x| acc + x);    // 15 (like reduce)
nums.iter().any(|&x| x > 4);              // true
nums.iter().all(|&x| x > 0);             // true
nums.iter().find(|&&x| x == 3);           // Some(&3)
nums.iter().position(|&x| x == 3);        // Some(2)
nums.iter().enumerate();                   // [(0,1), (1,2), ...]
nums.iter().zip(other.iter());             // pairs
nums.iter().take(3);                       // first 3
nums.iter().skip(2);                       // skip first 2
nums.iter().flatten();                     // flatten nested iterators
nums.iter().chain(other.iter());           // concatenate
nums.iter().sum::<i32>();                  // 15
nums.iter().min();                         // Some(1)
nums.iter().max();                         // Some(5)
nums.iter().count();                       // 5
nums.iter().collect::<Vec<_>>();           // back to Vec
nums.iter().collect::<HashSet<_>>();       // to HashSet
```

The subtle part is that almost all of these are lazy until you hit a consuming operation like `collect`, `sum`, `find`, or `count`. If you come from Python's eager list comprehensions, it is easy to assume work already happened when you only built an iterator pipeline.

### Three Types of Iteration

```rust
let v = vec![String::from("a"), String::from("b")];

// Borrow (most common)
for s in &v { }          // s is &String, v still usable after

// Mutable borrow
for s in &mut v { }      // s is &mut String, can modify in place

// Take ownership (consumes the vec)
for s in v { }           // s is String, v is gone after this loop
```

---

## 10. Concurrency & Parallelism

Official docs: [The Rust Book: Fearless Concurrency](https://doc.rust-lang.org/book/ch16-00-concurrency.html), [The Rust Book: Threads](https://doc.rust-lang.org/book/ch16-01-threads.html), [The Rust Book: Message Passing](https://doc.rust-lang.org/book/ch16-02-message-passing.html), [The Rust Book: Shared-State Concurrency](https://doc.rust-lang.org/book/ch16-03-shared-state.html)

### Rust's Concurrency Promise

**"Fearless concurrency"** -- the ownership system prevents data races at compile time.

| | Python | Rust |
|---|---|---|
| Threads | OS threads, but GIL limits parallelism | OS threads, true parallelism |
| Data race prevention | GIL (partially), locks (manually) | **Compile-time enforcement** |
| Shared state | Just share it (GIL protects somewhat) | Must use `Arc<Mutex<T>>` or channels |
| Message passing | `queue.Queue` | Channels (`std::sync::mpsc`) |
| Async | `asyncio` (single-threaded event loop) | `async`/`await` (multi-threaded runtimes) |

### Threads

```rust
use std::thread;

let handle = thread::spawn(|| {
    println!("Hello from a thread!");
    42
});

let result = handle.join().unwrap();  // 42
```

### Move Closures for Threads

Threads can outlive the function that spawned them, so data must be **moved** in:

```rust
let name = String::from("Alice");

let handle = thread::spawn(move || {
    // name is MOVED into this thread -- the main thread can't use it anymore
    println!("Hello, {name}!");
});

// println!("{name}");  // error: name was moved
handle.join().unwrap();
```

### Channels (Message Passing)

```rust
use std::sync::mpsc;  // multiple producer, single consumer

let (tx, rx) = mpsc::channel();

thread::spawn(move || {
    tx.send("hello from thread").unwrap();
    tx.send("another message").unwrap();
});

// Receive
println!("{}", rx.recv().unwrap());  // blocks until message available

// Iterate over received messages
for msg in rx {
    println!("{msg}");
}
```

That `for msg in rx` loop ends only when all senders are dropped. This is a common beginner gotcha: if you keep an extra `tx` alive somewhere, the receiver may wait forever because the channel is still considered open.

```python
import queue
import threading

q = queue.Queue()

def worker():
    q.put("hello from thread")

threading.Thread(target=worker).start()
print(q.get())
```

### Shared State with `Arc<Mutex<T>>`

```rust
use std::sync::{Arc, Mutex};

let counter = Arc::new(Mutex::new(0));  // Arc = atomic reference count
let mut handles = vec![];

for _ in 0..10 {
    let counter = Arc::clone(&counter);  // clone the Arc (not the data)
    let handle = thread::spawn(move || {
        let mut num = counter.lock().unwrap();  // acquire lock
        *num += 1;
        // lock automatically released when num goes out of scope
    });
    handles.push(handle);
}

for handle in handles {
    handle.join().unwrap();
}

println!("Result: {}", *counter.lock().unwrap());  // 10
```

```python
import threading

counter = 0
lock = threading.Lock()

def increment():
    global counter
    with lock:
        counter += 1

threads = [threading.Thread(target=increment) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
print(counter)  # 10
```

Key difference: Rust **won't compile** if you try to share data across threads without proper synchronization. Python will happily let you create race conditions.

### `Send` and `Sync` Traits

The compiler uses two marker traits to enforce thread safety:

| Trait | Meaning | Example |
|---|---|---|
| `Send` | Ownership can be transferred across threads | Most types |
| `Sync` | Can be referenced from multiple threads | Types where `&T` is `Send` |

`Rc<T>` is **not** `Send` -- use `Arc<T>` for multi-threaded reference counting. The compiler will refuse to let you send an `Rc` to another thread.

---

## 11. Async/Await

Official docs: [Async Book](https://rust-lang.github.io/async-book/), [`Future`](https://doc.rust-lang.org/std/future/trait.Future.html)

### Rust Async vs Python Async

Rust async usually feels lower-level than Python async because the language gives you the syntax, but not the runtime. You choose an executor such as `tokio`, and that executor decides how tasks are scheduled, what timers and networking primitives exist, and what spawning APIs are available.

| | Python asyncio | Rust async |
|---|---|---|
| Runtime | Built-in (`asyncio`) | External crate (`tokio`, `async-std`) |
| Threading | Single-threaded event loop | Multi-threaded by default (tokio) |
| Colored functions | Yes (`async def` infects callers) | Yes (`async fn` infects callers) |
| Futures | Eager (start immediately) | **Lazy** (do nothing until `.await`ed) |

### Basic Async

```rust
// Cargo.toml: tokio = { version = "1", features = ["full"] }

use tokio;

async fn fetch_data(url: &str) -> Result<String, reqwest::Error> {
    let body = reqwest::get(url).await?.text().await?;
    Ok(body)
}

#[tokio::main]
async fn main() {
    let result = fetch_data("https://example.com").await;
    match result {
        Ok(body) => println!("Got {} bytes", body.len()),
        Err(e) => eprintln!("Error: {e}"),
    }
}
```

```python
import asyncio
import aiohttp

async def fetch_data(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.text()

asyncio.run(fetch_data("https://example.com"))
```

### Futures Are Lazy

```rust
async fn do_work() -> i32 {
    println!("Working...");
    42
}

// This does NOTHING -- the future is not polled
let future = do_work();

// This actually executes it
let result = future.await;
```

In Python, `asyncio.create_task()` starts execution eagerly. In Rust, futures don't execute until driven by `.await` or an executor.

That laziness is powerful, but it also means "creating a future" and "running a task" are separate actions. A lot of early Rust async bugs come from constructing work and forgetting to actually await or spawn it.

### Concurrent Execution

```rust
use tokio;

async fn task_a() -> String { /* ... */ }
async fn task_b() -> i32 { /* ... */ }

// Run concurrently (like asyncio.gather)
let (a, b) = tokio::join!(task_a(), task_b());

// Race (like asyncio.wait FIRST_COMPLETED)
tokio::select! {
    val = task_a() => println!("A finished first: {val}"),
    val = task_b() => println!("B finished first: {val}"),
}
```

### Spawning Tasks

```rust
// Spawn a task (like asyncio.create_task)
let handle = tokio::spawn(async {
    expensive_computation().await
});

let result = handle.await.unwrap();
```

### Streams (Async Iterators)

```rust
use tokio_stream::StreamExt;

let mut stream = tokio_stream::iter(vec![1, 2, 3]);

while let Some(value) = stream.next().await {
    println!("{value}");
}
```

```python
async for value in async_iterable:
    print(value)
```

Streams are not built into the language the way Python's async iterators are. They are a trait-based ecosystem pattern, which is flexible but means you will often need helper crates and extension traits to get ergonomic stream combinators.

---

## 12. Smart Pointers & Interior Mutability

Official docs: [The Rust Book: Smart Pointers](https://doc.rust-lang.org/book/ch15-00-smart-pointers.html), [The Rust Book: `Rc<T>`](https://doc.rust-lang.org/book/ch15-04-rc.html), [The Rust Book: Interior Mutability](https://doc.rust-lang.org/book/ch15-05-interior-mutability.html), [`Arc`](https://doc.rust-lang.org/std/sync/struct.Arc.html), [`Mutex`](https://doc.rust-lang.org/std/sync/struct.Mutex.html)

Most of the time, plain ownership and borrowing are enough. Smart pointers show up when the basic model is too strict for the shape of your data: recursive trees, shared ownership graphs, GUI state, caches, or thread-safe shared mutation.

For Python developers, this section helps explain how Rust replaces the "everything is a heap object with references" model with several precise tools, each optimized for a different ownership problem.

### `Box<T>` -- Heap Allocation

```rust
// Allocate on the heap (like Python does for everything)
let boxed = Box::new(42);
println!("{boxed}");  // auto-derefs

// Required for recursive types
enum List {
    Cons(i32, Box<List>),
    Nil,
}
```

### `Rc<T>` -- Reference Counting (Single Thread)

Like Python's reference counting, but explicit:

```rust
use std::rc::Rc;

let a = Rc::new(String::from("shared"));
let b = Rc::clone(&a);  // increment ref count
let c = Rc::clone(&a);  // increment ref count

println!("ref count: {}", Rc::strong_count(&a));  // 3
// All three point to the same data
// Dropped when count reaches 0
```

### `Arc<T>` -- Atomic Reference Counting (Thread-Safe)

```rust
use std::sync::Arc;

let shared = Arc::new(vec![1, 2, 3]);
let clone = Arc::clone(&shared);

thread::spawn(move || {
    println!("{:?}", clone);  // safe to use in another thread
});
```

| | `Rc<T>` | `Arc<T>` |
|---|---|---|
| Thread-safe | No | Yes |
| Overhead | Lower | Slightly higher (atomic operations) |
| Use when | Single-threaded shared ownership | Multi-threaded shared ownership |

### Interior Mutability -- `RefCell<T>` and `Mutex<T>`

Sometimes you need to mutate data behind an immutable reference. Rust calls this "interior mutability" -- it moves borrow checking to **runtime**.

That sounds like cheating, and in a sense it is: `RefCell<T>` and `Mutex<T>` are controlled escape hatches. They are useful specifically because most of Rust stays statically checked; when you reach for interior mutability, you should know what invariant the compiler can no longer enforce for you.

```rust
use std::cell::RefCell;

let data = RefCell::new(vec![1, 2, 3]);

// Borrow checking happens at RUNTIME
{
    let mut v = data.borrow_mut();  // panics if already borrowed
    v.push(4);
}

let v = data.borrow();  // immutable borrow
println!("{:?}", *v);
```

### Common Smart Pointer Combinations

| Pattern | Use Case |
|---|---|
| `Box<T>` | Single owner, heap allocation |
| `Rc<T>` | Multiple owners, single thread |
| `Arc<T>` | Multiple owners, multi-threaded |
| `Rc<RefCell<T>>` | Multiple owners + mutation, single thread |
| `Arc<Mutex<T>>` | Multiple owners + mutation, multi-threaded |
| `Arc<RwLock<T>>` | Multiple owners + read-heavy mutation, multi-threaded |

---

## 13. Modules, Crates & Visibility

Official docs: [The Rust Book: Packages, Crates, and Modules](https://doc.rust-lang.org/book/ch07-00-managing-growing-projects-with-packages-crates-and-modules.html), [The Rust Book: Defining Modules](https://doc.rust-lang.org/book/ch07-02-defining-modules-to-control-scope-and-privacy.html), [The Rust Reference: Visibility and Privacy](https://doc.rust-lang.org/reference/visibility-and-privacy.html), [The Cargo Book](https://doc.rust-lang.org/cargo/)

Rust's module system often feels more mechanical than Python's import system, but it is also much less ambiguous. Visibility, file layout, and crate boundaries are explicit enough that large projects stay easier to reason about once you learn the rules.

### Terminology

| Rust | Python Equivalent |
|---|---|
| Crate | Package (installable unit) |
| Module | Module (a `.py` file or `__init__.py` directory) |
| `Cargo.toml` | `pyproject.toml` / `requirements.txt` |
| `Cargo.lock` | `pip freeze` / lock file |
| crates.io | PyPI |
| `cargo` | `pip` + `pytest` + `build` combined |

### Module System

```
my_project/
├── Cargo.toml
├── src/
│   ├── main.rs          # binary entry point
│   ├── lib.rs           # library root
│   ├── models/
│   │   ├── mod.rs       # like __init__.py
│   │   ├── user.rs
│   │   └── post.rs
│   └── utils.rs
```

```rust
// src/lib.rs
pub mod models;   // declares the models module
mod utils;        // private module

// src/models/mod.rs
pub mod user;
pub mod post;

// src/models/user.rs
pub struct User {
    pub name: String,     // pub = public field
    email: String,        // private field (default)
}
```

The key thing to notice is that files do not become public just because they exist. You expose modules and items deliberately with `mod` and `pub`, which keeps package boundaries tighter than the usual Python convention of "everything is importable unless we politely say otherwise."

### Visibility

```rust
pub struct Foo {       // public struct
    pub x: i32,        // public field
    y: i32,            // private field (crate-only)
}

pub fn public_fn() {}  // accessible to external crates
fn private_fn() {}     // only within this module

pub(crate) fn crate_fn() {}   // accessible anywhere in this crate
pub(super) fn parent_fn() {}  // accessible in parent module
```

| Rust | Python |
|---|---|
| `pub` | No prefix (public by convention) |
| No prefix (private) | `_single_underscore` (convention only) |
| `pub(crate)` | No direct equivalent |

### Cargo Commands

```bash
cargo new my_project     # create new project
cargo build              # compile
cargo build --release    # optimized build
cargo run                # build and run
cargo test               # run tests
cargo check              # type-check without building (fast)
cargo clippy             # linter (like pylint/ruff)
cargo fmt                # formatter (like black)
cargo doc --open         # generate and view docs
cargo add serde          # add dependency (like pip install)
```

In practice, `cargo check`, `cargo fmt`, `cargo clippy`, and `cargo test` become your default inner loop. One reason Rust projects feel consistent across teams is that these workflows are standardized instead of being assembled ad hoc from third-party tools.

---

## 14. Testing

Official docs: [The Rust Book: Writing Automated Tests](https://doc.rust-lang.org/book/ch11-00-testing.html), [The Rust Book: How to Write Tests](https://doc.rust-lang.org/book/ch11-01-writing-tests.html), [The Cargo Book](https://doc.rust-lang.org/cargo/)

Rust testing is intentionally boring in a good way. The language and toolchain assume tests live alongside the code or in a standard `tests/` directory, and `cargo test` knows how to run all of it without extra framework setup.

### Built-in Testing

```rust
// In the same file as the code being tested
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_addition() {
        assert_eq!(add(2, 3), 5);
    }

    #[test]
    fn test_greeting() {
        let result = greet("Alice");
        assert!(result.contains("Alice"));
    }

    #[test]
    #[should_panic(expected = "division by zero")]
    fn test_divide_by_zero() {
        divide(1, 0);
    }

    #[test]
    fn test_result() -> Result<(), String> {
        let result = parse_number("42")?;
        assert_eq!(result, 42);
        Ok(())
    }
}
```

Unit tests in the same file can access private items through `use super::*`, which makes it practical to test internal helpers without turning your crate's public API into a test seam.

### Assertion Macros

```rust
assert!(condition);                        // like Python's assert
assert_eq!(left, right);                   // like assert left == right
assert_ne!(left, right);                   // like assert left != right
assert_eq!(a, b, "custom message: {}", x); // with message
```

### Integration Tests

```
my_project/
├── src/
│   └── lib.rs
├── tests/              # integration tests directory
│   ├── api_tests.rs    # each file is a separate test binary
│   └── db_tests.rs
```

```rust
// tests/api_tests.rs
use my_project::api;  // imports from your library crate

#[test]
fn test_api_endpoint() {
    let response = api::handle_request("/users");
    assert_eq!(response.status, 200);
}
```

Integration tests compile as separate crates, so they only see your public API. That makes them a good fit for higher-level behavior checks, similar to testing your Python package from the outside instead of reaching into implementation details.

### Running Tests

```bash
cargo test                          # all tests
cargo test test_name                # specific test
cargo test -- --nocapture           # show println output
cargo test --test api_tests         # specific integration test file
cargo test -- --ignored             # run ignored tests
```

---

## 15. Strings (Yes, They Deserve Their Own Section)

Official docs: [The Rust Book: Storing UTF-8 Encoded Text with Strings](https://doc.rust-lang.org/book/ch08-02-strings.html), [`String`](https://doc.rust-lang.org/std/string/struct.String.html), [`str`](https://doc.rust-lang.org/std/primitive.str.html)

Python lets you mostly ignore the difference between owned text, borrowed text, bytes, Unicode scalar values, and display width until edge cases appear. Rust makes those distinctions explicit, which is painful at first but prevents a lot of vague "string-ish" APIs.

If Rust strings feel awkward, it is usually because the language is forcing you to answer a question Python let you postpone: do you own this text, are you borrowing it, or are you operating on encoded bytes?

### Why Strings Are Hard in Rust

Python strings are simple: `str` is an immutable sequence of Unicode characters. Rust has **two** main string types, and the distinction matters.

| | `String` | `&str` |
|---|---|---|
| Ownership | Owned, heap-allocated | Borrowed reference (slice) |
| Mutability | Growable, modifiable | Immutable view |
| Analogy | `list` (owned, growable) | A slice/view into a string |
| Created by | `String::from("hi")`, `.to_string()` | String literals `"hi"`, slicing |
| Use in structs | Yes (owns its data) | Needs lifetime annotations |
| As function param | Prefer `&str` (accepts both) | Most common parameter type |

```rust
let owned: String = String::from("hello");     // heap-allocated, owned
let borrowed: &str = "hello";                  // points to binary data, borrowed
let slice: &str = &owned[0..3];                // "hel" -- borrows from owned

// Converting between them
let s: String = borrowed.to_string();          // &str -> String
let s: String = String::from(borrowed);        // &str -> String
let b: &str = &owned;                          // String -> &str (auto deref)
```

### Strings Are UTF-8 (Not Indexable by Character)

```rust
let s = String::from("hello");
// let c = s[0];  // ERROR: Rust strings are UTF-8 bytes, not chars

// You must be explicit about what you want:
let bytes = s.as_bytes();         // &[u8]
let chars: Vec<char> = s.chars().collect();  // Unicode scalar values
let c = &s[0..1];                 // byte slice (panics if not on char boundary)
```

```python
s = "hello"
c = s[0]  # 'h' -- simple indexing
```

### Common String Operations

```rust
// Concatenation
let s = String::from("hello") + " " + "world";  // String + &str
let s = format!("{} {}", "hello", "world");       // preferred

// Formatting (like f-strings)
let name = "Alice";
let age = 30;
let msg = format!("Hi, I'm {name} and I'm {age} years old");

// Methods
s.len();                    // byte length (not char count!)
s.chars().count();          // character count
s.contains("ello");         // true
s.starts_with("hel");       // true
s.replace("hello", "Hi");   // "Hi world"
s.trim();                   // strip whitespace
s.split_whitespace();       // iterator over words
s.to_uppercase();           // "HELLO WORLD"
s.is_empty();               // false

// Building strings
let mut s = String::new();
s.push('h');               // single char
s.push_str("ello");        // string slice
```

Notice how often these APIs separate bytes, chars, slices, and owned strings. That is the recurring theme of Rust text handling: the language wants you to be precise about what unit you are manipulating.

### When to Use Which

```rust
// Function parameters: accept &str (works with both String and &str)
fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

greet("Alice");                           // &str literal
greet(&String::from("Alice"));            // &String auto-derefs to &str

// Struct fields: use String (owns the data)
struct User {
    name: String,  // not &str (would need lifetime)
}
```

---

## 16. Common Pitfalls for Python Developers

Official docs: [The Rust Book: Understanding Ownership](https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html), [The Rust Book: References and Borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html), [The Rust Book: Error Handling](https://doc.rust-lang.org/book/ch09-00-error-handling.html), [The Rust Book: Strings](https://doc.rust-lang.org/book/ch08-02-strings.html)

### 1. Fighting the Borrow Checker

The most common frustration. You'll try to do something that feels natural in Python and the compiler will reject it.

```rust
// This won't compile:
let mut v = vec![1, 2, 3];
let first = &v[0];     // immutable borrow
v.push(4);              // mutable borrow -- ERROR: can't borrow mutably
println!("{first}");    // immutable borrow still in use

// Fix: restructure so borrows don't overlap
let mut v = vec![1, 2, 3];
let first = v[0];       // COPY the value (i32 is Copy)
v.push(4);
println!("{first}");
```

### 2. Expecting Everything to Be a Reference

```python
# Python: everything is a reference, sharing is free
users = [user1, user2]  # both user1 and list share the same objects
```

```rust
// Rust: you must choose ownership
let users = vec![user1, user2];  // user1 and user2 are MOVED into vec
// user1 is now invalid!

// If you need shared access, clone or use references
let users = vec![user1.clone(), user2.clone()];  // explicit
```

### 3. String Confusion

```rust
// This is &str (a borrowed string slice)
let s = "hello";

// This is String (an owned, heap-allocated string)
let s = String::from("hello");

// You'll see lots of .to_string(), .as_str(), &, format!()
// until it becomes natural
```

### 4. No Exceptions Means Lots of `?` and `match`

```rust
// Every fallible operation returns Result -- you must handle it
let file = File::open("data.txt")?;
let content = read_to_string(&file)?;
let parsed: Config = serde_json::from_str(&content)?;
```

### 5. Forgetting `mut`

```rust
let v = vec![1, 2, 3];
// v.push(4);  // ERROR: v is not mutable

let mut v = vec![1, 2, 3];
v.push(4);     // fine
```

### 6. Confusing `iter()`, `into_iter()`, `iter_mut()`

```rust
let v = vec![1, 2, 3];

v.iter()        // yields &i32 (borrows, v still usable)
v.iter_mut()    // yields &mut i32 (mutable borrows)
v.into_iter()   // yields i32 (consumes v -- v is gone)

// for x in &v     == v.iter()
// for x in &mut v == v.iter_mut()
// for x in v      == v.into_iter()
```

### 7. Trying to Store References in Structs

```rust
// Instinct from Python: "I'll just store a reference"
struct Cache {
    data: &Vec<u8>,  // ERROR: missing lifetime
}

// Fix 1: Own the data
struct Cache {
    data: Vec<u8>,
}

// Fix 2: Use lifetime (only when borrowing is truly needed)
struct Cache<'a> {
    data: &'a Vec<u8>,
}
```

**Rule of thumb:** When in doubt, own the data. Use `String` not `&str`, `Vec<T>` not `&[T]` in structs.

### 8. The Turbofish `::<>`

```rust
// Sometimes Rust can't infer types -- you need the turbofish
let numbers: Vec<i32> = "1 2 3".split(' ')
    .map(|s| s.parse::<i32>().unwrap())  // ::<i32> is the turbofish
    .collect();

// Or annotate the variable type instead
let numbers: Vec<i32> = "1 2 3".split(' ')
    .map(|s| s.parse().unwrap())
    .collect();
```

---

## Quick Reference Cheat Sheet

Official docs: [The Rust Book](https://doc.rust-lang.org/book/), [Standard Library](https://doc.rust-lang.org/std/), [Rust Reference](https://doc.rust-lang.org/reference/)

| Python | Rust |
|--------|------|
| `class Foo` | `struct Foo` + `impl Foo` |
| `self.method()` | `self.method()` (receiver is `&self` / `&mut self`) |
| `try/except` | `Result<T, E>` + `?` operator |
| `with open() as f` | `let f = File::open()?;` (no context managers, use RAII) |
| `None` | `Option::None` |
| `isinstance(x, Foo)` | `match` / `if let` / `x.downcast_ref::<Foo>()` |
| `list` | `Vec<T>` |
| `dict` | `HashMap<K, V>` |
| `set` | `HashSet<T>` |
| `tuple` | `(T1, T2, T3)` (heterogeneous, fixed-size) |
| `f"Hello {name}"` | `format!("Hello {name}")` |
| `print()` | `println!()` |
| `lambda x: x + 1` | `\|x\| x + 1` |
| `map(f, list)` | `iter.map(f)` |
| `filter(f, list)` | `iter.filter(f)` |
| `sum(list)` | `iter.sum()` |
| `[x*2 for x in lst]` | `lst.iter().map(\|x\| x*2).collect()` |
| `threading.Thread` | `std::thread::spawn` |
| `threading.Lock` | `std::sync::Mutex` |
| `asyncio.gather` | `tokio::join!` |
| `pip install` | `cargo add` |
| `pytest` | `cargo test` (built-in) |
| `black` | `cargo fmt` |
| `ruff` / `pylint` | `cargo clippy` |
| `copy.deepcopy(x)` | `x.clone()` |
| `type()` | Compile-time types; runtime via `TypeId` |

---

## Essential Crates (The "Standard Library" Everyone Uses)

Official docs: [The Cargo Book](https://doc.rust-lang.org/cargo/), [The Rust Book](https://doc.rust-lang.org/book/)

These are not literally part of the standard library. They are the crates you will see so often that they function like default infrastructure across much of the ecosystem. Knowing them early makes real-world Rust code much less intimidating.

| Crate | Purpose | Python Equivalent |
|---|---|---|
| `serde` + `serde_json` | Serialization/deserialization | `json` / `dataclasses` |
| `tokio` | Async runtime | `asyncio` |
| `reqwest` | HTTP client | `requests` / `aiohttp` |
| `clap` | CLI argument parsing | `argparse` / `click` |
| `anyhow` | Easy error handling (apps) | N/A |
| `thiserror` | Custom error types (libs) | Custom exception classes |
| `tracing` | Structured logging | `logging` |
| `rayon` | Data parallelism | `multiprocessing.Pool` |
| `regex` | Regular expressions | `re` |
| `chrono` | Date/time | `datetime` |
| `rand` | Random numbers | `random` |
| `itertools` | Extra iterator methods | `itertools` |
| `sqlx` | Async SQL | `asyncpg` / `SQLAlchemy` |
| `axum` / `actix-web` | Web frameworks | `FastAPI` / `Flask` |

# Swift

A depth-first guide to the Swift programming language in 2026 — not a tour, but a treatment of how the language actually works under the hood and how to use it idiomatically. Covers the type system, memory management (ARC), protocols and generics, collections and strings, error handling, closures and functional patterns, concurrency (actors, async/await, Sendable), macros, result builders, ownership and noncopyable types, and the Swift 6.x language evolution. The iOS Development guide is the companion for building apps with SwiftUI; this guide is about Swift itself.

Assumes programming experience. No prior Swift knowledge required.

Primary references: [The Swift Programming Language](https://docs.swift.org/swift-book/), the [Swift Evolution proposals](https://github.com/swiftlang/swift-evolution/tree/main/proposals), the [Swift source code](https://github.com/swiftlang/swift), and the [Swift blog](https://www.swift.org/blog/).

---

## Table of Contents

1. [Part 1 — The Type System](#part-1--the-type-system)
2. [Part 2 — Memory Management: ARC](#part-2--memory-management-arc)
3. [Part 3 — Optionals](#part-3--optionals)
4. [Part 4 — Closures](#part-4--closures)
5. [Part 5 — Enums and Pattern Matching](#part-5--enums-and-pattern-matching)
6. [Part 6 — Protocols](#part-6--protocols)
7. [Part 7 — Generics](#part-7--generics)
8. [Part 8 — Collections](#part-8--collections)
9. [Part 9 — Strings and Unicode](#part-9--strings-and-unicode)
10. [Part 10 — Error Handling](#part-10--error-handling)
11. [Part 11 — Concurrency](#part-11--concurrency)
12. [Part 12 — Macros](#part-12--macros)
13. [Part 13 — Result Builders](#part-13--result-builders)
14. [Part 14 — Property Wrappers](#part-14--property-wrappers)
15. [Part 15 — Ownership and Noncopyable Types](#part-15--ownership-and-noncopyable-types)
16. [Part 16 — Swift 6.x: The Language in 2026](#part-16--swift-6x-the-language-in-2026)

---

## Part 1 — The Type System

### Value Types vs. Reference Types

This is the most important distinction in Swift. It affects correctness, performance, thread safety, and architecture.

**Value types** (structs, enums, tuples) are **copied** on assignment. Each variable owns an independent copy:

```swift
struct Point {
    var x: Double
    var y: Double
}

var a = Point(x: 1, y: 2)
var b = a        // b is an independent copy
b.x = 99        // a.x is still 1
```

**Reference types** (classes) are **shared**. Variables hold a pointer to the same heap-allocated object:

```swift
class Account {
    var balance: Double
    init(balance: Double) { self.balance = balance }
}

let a = Account(balance: 100)
let b = a        // b points to the same object
b.balance = 0    // a.balance is also 0 — same object
```

**Where they live:**
- Value types live on the **stack** (unless captured by a closure or boxed into a protocol existential, in which case the compiler may promote them to the heap).
- Reference types always live on the **heap**, and variables hold a pointer.

**The rule:** prefer structs. Use classes only when you need identity (the object itself matters, not just its value), when you need inheritance, or when you need reference semantics for shared mutable state (and if you need that in concurrent code, use an actor instead).

The reason Swift pushes value types this hard — and why this is "the most important distinction" rather than a stylistic preference — is that value semantics *eliminates an entire category of bugs by construction*. With reference types, passing an object to a function hands over a shared pointer, so the function (or anything it stores the pointer in) can mutate *your* object behind your back — the spooky-action-at-a-distance that produces "why did this value change? I never touched it" debugging sessions. With value types, passing a struct passes a *copy*, so the callee physically cannot affect your copy no matter what it does; the value you hold is yours alone. This is also the foundation of Swift's compile-time concurrency safety (Part 11): the hardest problem in concurrent programming is shared mutable state racing between threads, and a value type *has no sharing to race* — two tasks each get their own copy — which is precisely why Swift 6's strict concurrency checking can prove a value type is safe to send across task boundaries (it's `Sendable`) while a class holding mutable state is not. So "prefer structs" is not aesthetics; it is choosing the type discipline that makes both ordinary code easier to reason about and concurrent code provably safe, which is why the actor (Part 11) exists as the *one* sanctioned way to have shared mutable state when you genuinely need it.

### Mutability

Swift separates mutability at the binding level (`let` vs `var`) and at the type level (mutating methods):

```swift
let immutable = Point(x: 1, y: 2)
// immutable.x = 5    // compile error — let binding

var mutable = Point(x: 1, y: 2)
mutable.x = 5    // fine — var binding

// for classes, let means the reference can't change — the object can
let account = Account(balance: 100)
account.balance = 200    // fine — the object is mutable
// account = Account(balance: 0)    // error — can't reassign the reference
```

Structs that modify their own properties must mark methods as `mutating`:

```swift
struct Counter {
    var count = 0
    
    mutating func increment() {
        count += 1
    }
}

var counter = Counter()
counter.increment()    // fine

let fixedCounter = Counter()
// fixedCounter.increment()    // error — can't call mutating method on let
```

### Structs

```swift
struct User {
    let id: UUID             // immutable after init
    var name: String
    var email: String
    
    // memberwise initializer is auto-generated:
    // User(id:name:email:)
    
    // custom init
    init(name: String, email: String) {
        self.id = UUID()
        self.name = name
        self.email = email
    }
    
    // computed property
    var displayName: String {
        name.isEmpty ? email : name
    }
    
    // static property
    static let anonymous = User(name: "Anonymous", email: "")
}
```

Key struct behaviors:
- Auto-generated **memberwise initializer** (lost if you write a custom `init` — put custom inits in an extension to keep both).
- No inheritance (use protocols for shared behavior).
- Conforms to `Sendable` automatically if all stored properties are `Sendable`.
- Copy-on-write is NOT automatic for custom structs — only for standard library types like `Array`, `String`, `Dictionary`. Your struct is copied on every assignment (though the compiler optimizes away many copies in practice).

### Classes

```swift
class Vehicle {
    let vin: String
    var mileage: Double
    
    init(vin: String, mileage: Double = 0) {
        self.vin = vin
        self.mileage = mileage
    }
    
    deinit {
        print("Vehicle \(vin) deallocated")    // called when ref count hits 0
    }
    
    func drive(miles: Double) {
        mileage += miles
    }
}

class ElectricVehicle: Vehicle {
    var batteryLevel: Double
    
    init(vin: String, batteryLevel: Double) {
        self.batteryLevel = batteryLevel
        super.init(vin: vin)    // must call super after initializing own properties
    }
    
    override func drive(miles: Double) {
        super.drive(miles: miles)
        batteryLevel -= miles * 0.3
    }
}
```

Key class behaviors:
- **Reference counting** (ARC) manages lifetime — see Part 2.
- **Inheritance** — single class inheritance, unlimited protocol conformance.
- `deinit` runs when the object is deallocated.
- `final` prevents subclassing and enables static dispatch (faster method calls).

### Type Casting

```swift
let vehicle: Vehicle = ElectricVehicle(vin: "123", batteryLevel: 100)

// conditional cast
if let ev = vehicle as? ElectricVehicle {
    print("Battery: \(ev.batteryLevel)")
}

// forced cast (crashes if wrong type — avoid)
let ev = vehicle as! ElectricVehicle

// type check
if vehicle is ElectricVehicle {
    print("It's electric")
}
```

### Type Aliases and Nested Types

```swift
typealias Completion<T> = (Result<T, Error>) -> Void
typealias UserID = String

struct APIClient {
    // nested types — scope types inside their parent
    enum Endpoint {
        case users
        case posts(userId: UserID)
        
        var path: String {
            switch self {
            case .users: return "/users"
            case .posts(let id): return "/users/\(id)/posts"
            }
        }
    }
}

// used as APIClient.Endpoint.users
```

---

## Part 2 — Memory Management: ARC

Swift's memory management is one of its defining choices, and understanding *why* it picked **Automatic Reference Counting (ARC)** over garbage collection explains both what Swift is good at and the one discipline it demands of you. A garbage-collected language (Java, Go, C#) runs a separate collector that periodically traces the object graph to find and free unreachable memory — convenient, because the programmer never thinks about it, but at the cost of unpredictable *pauses* when the collector runs and *non-deterministic* timing for when an object's cleanup happens. Swift, designed for systems and UI work where a frame budget is 16 milliseconds and a GC pause is a visible stutter, made the opposite trade: ARC tracks each object's reference count and frees it *the instant* the count hits zero, with the compiler inserting the `retain`/`release` calls at compile time. The payoffs are exactly what a responsive app needs — **no GC pauses**, **deterministic deallocation** (an object's `deinit` runs at a precise, knowable moment, so you can rely on it to close a file or release a resource, the way C++ RAII does), and a smaller, more predictable memory footprint.

That determinism is not free, and the bill is the one thing this whole section is about: because ARC simply counts references and frees at zero, it **cannot detect cycles** — two objects pointing at each other keep each other's count above zero forever, and they leak. A tracing garbage collector would notice they're unreachable and collect them; ARC can't, because it never traces. So the discipline ARC demands of the programmer is breaking those cycles by hand with `weak` and `unowned` references (below) — which is the trade Swift made explicit: you get deterministic, pause-free memory in exchange for owning the cycle problem yourself. The compiler inserts `retain` and `release`; the runtime deallocates at zero; and the programmer's job is to make sure the graph can *reach* zero.

### How ARC Works

Every class instance has a reference count stored in its header on the heap:

```swift
class Dog {
    let name: String
    init(name: String) { self.name = name }
    deinit { print("\(name) deallocated") }
}

var a: Dog? = Dog(name: "Rex")    // ref count = 1
var b = a                         // ref count = 2
a = nil                           // ref count = 1
b = nil                           // ref count = 0 → deinit → "Rex deallocated"
```

This works perfectly for trees and acyclic object graphs. The problem is **retain cycles**.

### Retain Cycles

A retain cycle occurs when two objects hold strong references to each other. Their reference counts never reach zero, and they leak:

```swift
class Person {
    let name: String
    var pet: Dog?
    init(name: String) { self.name = name }
    deinit { print("\(name) deallocated") }
}

class Dog {
    let name: String
    var owner: Person?    // STRONG reference — creates cycle
    init(name: String) { self.name = name }
    deinit { print("\(name) deallocated") }
}

var alice: Person? = Person(name: "Alice")
var rex: Dog? = Dog(name: "Rex")

alice?.pet = rex       // Person → Dog (strong)
rex?.owner = alice     // Dog → Person (strong) — CYCLE

alice = nil    // Person ref count: 1 (Dog still holds it)
rex = nil      // Dog ref count: 1 (Person still holds it)
// neither deinit runs — both leaked
```

### Breaking Cycles: weak and unowned

**`weak`** — the safe choice. Automatically set to `nil` when the referenced object is deallocated. Always optional:

```swift
class Dog {
    let name: String
    weak var owner: Person?    // weak — does NOT increment ref count
    init(name: String) { self.name = name }
}

// Now when alice = nil, Person's ref count reaches 0
// Person deallocates, Dog.owner becomes nil
// Then rex = nil, Dog deallocates
```

**`unowned`** — for when the referenced object is guaranteed to outlive the holder. Non-optional. **Crashes if accessed after the object is deallocated:**

```swift
class CreditCard {
    let number: String
    unowned let holder: Person    // holder always outlives the card
    
    init(number: String, holder: Person) {
        self.number = number
        self.holder = holder
    }
}
```

**Decision:** default to `weak`. Use `unowned` only when you can prove the lifetime relationship makes dangling access impossible.

### Closures and Retain Cycles

Closures capture references to objects they use. If an object holds a closure that captures `self`, you get a cycle:

```swift
class ViewModel {
    var name = "Alice"
    var onUpdate: (() -> Void)?
    
    func setup() {
        // BAD — closure captures self strongly, self holds closure
        onUpdate = {
            print(self.name)    // retains self
        }
    }
    
    // GOOD — capture list breaks the cycle
    func setupCorrectly() {
        onUpdate = { [weak self] in
            guard let self else { return }
            print(self.name)
        }
    }
}
```

**Capture lists** — `[weak self]`, `[unowned self]`, or capture specific values:

```swift
let id = user.id
onUpdate = { [id] in    // captures the VALUE of id, not a reference to user
    print(id)
}
```

### Detecting Leaks

- **Xcode Memory Graph Debugger:** Debug → Debug Memory Graph. Shows all live objects and their references. Look for cycles.
- **Instruments → Leaks:** Profile your app and the Leaks instrument flags objects that are unreachable but not deallocated.
- **Instruments → Allocations:** Track allocation patterns and identify objects that grow without bound.
- **`deinit` logging:** Temporary `print` statements in `deinit` to verify objects are being released.

---

## Part 3 — Optionals

Optionals are implemented as an enum with two cases:

```swift
enum Optional<Wrapped> {
    case none          // nil
    case some(Wrapped) // has a value
}
```

`String?` is syntactic sugar for `Optional<String>`.

### Unwrapping Patterns

```swift
let name: String? = fetchName()

// 1. if let — bind if non-nil
if let name {    // Swift 5.7+ shorthand (same as: if let name = name)
    print(name)  // name is String here
}

// 2. guard let — early return if nil
func greet(_ name: String?) {
    guard let name else {
        print("No name")
        return
    }
    // name is String for the rest of the function
    print("Hello, \(name)")
}

// 3. nil-coalescing — provide a default
let displayName = name ?? "Anonymous"    // String, not String?

// 4. optional chaining — propagate nil
let count = name?.count           // Int? — nil if name is nil
let upper = name?.uppercased()    // String?

// chained multiple levels deep
let firstChar = user?.address?.city?.first    // Character?

// 5. map and flatMap — transform without unwrapping
let greeting = name.map { "Hello, \($0)" }    // String?
let parsed = optionalString.flatMap { Int($0) }    // Int? (avoids Int??)

// 6. switch
switch name {
case .some(let value):
    print(value)
case .none:
    print("nil")
}

// 7. force unwrap — AVOID in production
let unsafeName = name!    // crashes at runtime if nil
```

### Implicitly Unwrapped Optionals

`String!` — an optional that's automatically force-unwrapped on access. Used only for values that are guaranteed to be set before use but can't be set during init:

```swift
// only real use case: Interface Builder outlets (UIKit legacy)
@IBOutlet weak var label: UILabel!

// and some Apple framework delegation patterns
// NEVER use in your own APIs
```

### Optional Chaining with Assignment

```swift
struct Settings {
    var theme: Theme?
}

var settings: Settings? = Settings()
settings?.theme = .dark    // sets if settings is non-nil, no-op if nil
```

---

## Part 4 — Closures

Closures are self-contained blocks of functionality. They can capture and store references to variables and constants from the surrounding context.

### Syntax

```swift
// full syntax
let add: (Int, Int) -> Int = { (a: Int, b: Int) -> Int in
    return a + b
}

// type inference removes parameter types and return type
let add: (Int, Int) -> Int = { a, b in
    return a + b
}

// implicit return for single-expression closures
let add: (Int, Int) -> Int = { a, b in a + b }

// shorthand argument names
let add: (Int, Int) -> Int = { $0 + $1 }

// trailing closure syntax — when the last parameter is a closure
let sorted = names.sorted { $0 < $1 }

// multiple trailing closures
Button {
    save()
} label: {
    Label("Save", systemImage: "square.and.arrow.down")
}
```

### Capture Semantics

Closures capture variables **by reference** (for reference types) and **by value** (for value types, but they capture the variable itself, not a snapshot):

```swift
var counter = 0
let increment = { counter += 1 }    // captures the variable 'counter'
increment()
increment()
print(counter)    // 2 — the closure mutated the original variable

// capture list — capture a snapshot of the value
var x = 10
let snapshot = { [x] in print(x) }
x = 99
snapshot()    // prints 10 — captured the value at creation time
```

### Escaping vs. Non-Escaping

By default, closure parameters are **non-escaping** — they can't outlive the function call. If you need to store the closure (for callbacks, async work), mark it `@escaping`:

```swift
// non-escaping (default) — closure runs before the function returns
func apply(_ transform: (Int) -> Int, to value: Int) -> Int {
    transform(value)
}

// escaping — closure is stored or called after the function returns
class Downloader {
    var completionHandlers: [() -> Void] = []
    
    func download(completion: @escaping () -> Void) {
        completionHandlers.append(completion)    // stored — must be @escaping
    }
}
```

**Why it matters:** non-escaping closures don't need to worry about retain cycles (they can't outlive `self`). Escaping closures can create retain cycles — use `[weak self]`.

### @Sendable Closures

In Swift 6, closures that cross concurrency boundaries must be `@Sendable` — they can't capture mutable state:

```swift
func onBackground(_ work: @Sendable @escaping () -> Void) {
    Task.detached { work() }
}

var count = 0
onBackground {
    // count += 1    // ERROR in Swift 6: capturing mutable var in @Sendable closure
}
```

### Higher-Order Functions

Swift's standard library provides functional-style operations on sequences:

```swift
let numbers = [1, 2, 3, 4, 5]

// map — transform each element
let doubled = numbers.map { $0 * 2 }             // [2, 4, 6, 8, 10]

// filter — keep elements matching a predicate
let evens = numbers.filter { $0.isMultiple(of: 2) }  // [2, 4]

// reduce — combine all elements into a single value
let sum = numbers.reduce(0, +)                    // 15

// compactMap — map + remove nils
let parsed = ["1", "two", "3"].compactMap { Int($0) }  // [1, 3]

// flatMap — map + flatten nested arrays
let nested = [[1, 2], [3, 4]]
let flat = nested.flatMap { $0 }                  // [1, 2, 3, 4]

// chaining
let result = users
    .filter { $0.isActive }
    .sorted { $0.name < $1.name }
    .map { $0.email }

// lazy — defer computation until needed (avoids intermediate arrays)
let firstActive = users.lazy
    .filter { $0.isActive }
    .map { $0.name }
    .first    // only processes elements until it finds the first match
```

### KeyPath Expressions

KeyPaths are type-safe references to properties. They can replace simple closures:

```swift
struct User {
    let name: String
    let age: Int
}

let users = [User(name: "Alice", age: 30), User(name: "Bob", age: 25)]

// closure syntax
let names = users.map { $0.name }

// keypath syntax (equivalent)
let names = users.map(\.name)

// sorting with keypath
let sorted = users.sorted(by: \.age)

// writable keypaths
struct Settings {
    var volume: Int = 50
}
var s = Settings()
let path = \Settings.volume
s[keyPath: path] = 75    // sets volume to 75
```

---

## Part 5 — Enums and Pattern Matching

Swift enums are algebraic data types — each case can carry different associated values. This makes them the right tool for modeling state machines, errors, API responses, and any type with a fixed set of variants.

### Basics

```swift
enum Direction {
    case north, south, east, west
}

let heading: Direction = .north    // type inferred from context
```

### Associated Values

Each case can carry different data:

```swift
enum Media {
    case image(url: URL, width: Int, height: Int)
    case video(url: URL, duration: TimeInterval)
    case text(String)
    case audio(url: URL, sampleRate: Int)
}

let content: Media = .image(url: imageURL, width: 1920, height: 1080)
```

### Raw Values

For simple mappings to primitive types:

```swift
enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case delete = "DELETE"
}

let method = HTTPMethod.get
print(method.rawValue)    // "GET"

// init from raw value (returns optional)
let parsed = HTTPMethod(rawValue: "POST")    // .post

// integer raw values auto-increment
enum Priority: Int {
    case low = 1
    case medium     // 2
    case high       // 3
}
```

### Pattern Matching

`switch` must be exhaustive — every possible case must be handled:

```swift
func describe(_ media: Media) -> String {
    switch media {
    case .image(_, let w, let h):
        return "\(w)×\(h) image"
    case .video(_, let duration) where duration > 3600:
        return "long video (\(Int(duration / 60)) min)"
    case .video(_, let duration):
        return "\(Int(duration))s video"
    case .text(let content) where content.isEmpty:
        return "empty text"
    case .text:
        return "text"
    case .audio:
        return "audio"
    }
}
```

Pattern matching works in `if case`, `guard case`, and `for case`:

```swift
// if case — match a single pattern
if case .image(let url, _, _) = content {
    loadImage(from: url)
}

// guard case — early return if no match
guard case .video(let url, _) = content else {
    return
}
playVideo(url)

// for case — filter and extract from a collection
let items: [Media] = [...]
for case .image(let url, _, _) in items {
    prefetchImage(url)    // only processes .image cases
}
```

### Recursive Enums

Use `indirect` for enums that reference themselves:

```swift
indirect enum ArithExpr {
    case number(Double)
    case add(ArithExpr, ArithExpr)
    case multiply(ArithExpr, ArithExpr)
}

func evaluate(_ expr: ArithExpr) -> Double {
    switch expr {
    case .number(let value):
        return value
    case .add(let lhs, let rhs):
        return evaluate(lhs) + evaluate(rhs)
    case .multiply(let lhs, let rhs):
        return evaluate(lhs) * evaluate(rhs)
    }
}

let expr = ArithExpr.add(.number(2), .multiply(.number(3), .number(4)))
print(evaluate(expr))    // 14.0
```

### CaseIterable

Auto-generate a collection of all cases:

```swift
enum Theme: String, CaseIterable {
    case light, dark, system
}

for theme in Theme.allCases {
    print(theme.rawValue)
}
```

### Enum Without Cases — The Namespace Pattern

An enum with no cases cannot be instantiated. Use it as a namespace:

```swift
enum API {
    static let baseURL = URL(string: "https://api.example.com")!
    static let timeout: TimeInterval = 30
}

// API() — compile error, can't instantiate
```

---

## Part 6 — Protocols

Protocols define a contract — a set of requirements — that conforming types must satisfy. Unlike class inheritance, any type (struct, enum, class, actor) can conform to any number of protocols.

### Definition and Conformance

```swift
protocol Describable {
    var summary: String { get }
    func describe() -> String
}

// property requirements specify get-only or get+set
protocol Configurable {
    var isEnabled: Bool { get set }    // must be read-write
    var name: String { get }          // must be at least readable
}

struct User: Describable {
    let name: String
    
    var summary: String { name }
    
    func describe() -> String {
        "User: \(name)"
    }
}
```

### Protocol Extensions — Default Implementations

Protocol extensions provide default behavior. Conforming types can override them:

```swift
extension Describable {
    func describe() -> String {
        "Description: \(summary)"    // default implementation
    }
}

// User can choose to use the default or provide its own
```

**Static vs. dynamic dispatch:** methods declared in the protocol itself use **dynamic dispatch** (the correct implementation is called even through a protocol type). Methods declared only in the extension (not in the protocol) use **static dispatch** (the extension's implementation is always called, regardless of the concrete type):

```swift
protocol Animal {
    func sound() -> String           // protocol requirement — dynamic dispatch
}

extension Animal {
    func sound() -> String { "..." } // default for sound()
    func description() -> String {   // NOT in protocol — static dispatch
        "An animal that says \(sound())"
    }
}

struct Dog: Animal {
    func sound() -> String { "Woof" }
    func description() -> String { "A dog" }
}

let dog = Dog()
dog.sound()         // "Woof" — Dog's implementation
dog.description()   // "A dog" — Dog's implementation

let animal: any Animal = Dog()
animal.sound()       // "Woof" — dynamic dispatch finds Dog's implementation
animal.description() // "An animal that says Woof" — STATIC dispatch uses extension
```

This is a common source of bugs. **Rule:** if you want polymorphic behavior, declare the method in the protocol, not just the extension.

### Protocol Composition

Combine multiple protocols as a single requirement:

```swift
func save(_ item: any Codable & Identifiable) { /* ... */ }

// or with a typealias
typealias Persistable = Codable & Identifiable & Hashable
```

### Associated Types

Protocols with associated types are generic protocols — the conforming type fills in the placeholder:

```swift
protocol Repository {
    associatedtype Item: Identifiable
    
    func fetchAll() async throws -> [Item]
    func fetch(id: Item.ID) async throws -> Item
    func save(_ item: Item) async throws
}

struct UserRepository: Repository {
    typealias Item = User    // compiler infers this from the method signatures
    
    func fetchAll() async throws -> [User] { /* ... */ }
    func fetch(id: String) async throws -> User { /* ... */ }
    func save(_ user: User) async throws { /* ... */ }
}
```

### `some` vs. `any` — Opaque and Existential Types

These are two different ways to use a protocol as a type:

**`some Protocol`** — opaque type. The compiler knows the concrete type; the caller doesn't. Static dispatch, no heap allocation overhead:

```swift
func makeAnimal() -> some Animal {
    Dog()    // compiler knows this returns Dog
}
// caller sees 'some Animal' — can't know it's Dog
// but the compiler uses static dispatch (fast)
```

**`any Protocol`** — existential type. Runtime polymorphism. Can hold any conforming type. Dynamic dispatch, potential heap allocation:

```swift
func processAnimals(_ animals: [any Animal]) {
    for animal in animals {
        print(animal.sound())    // dynamic dispatch
    }
}

let mixed: [any Animal] = [Dog(), Cat(), Fish()]    // heterogeneous
```

**Rule of thumb:** use `some` by default (generics). Use `any` when you need a heterogeneous collection or runtime flexibility.

### Common Standard Library Protocols

| Protocol | What it provides | Typical use |
|---|---|---|
| `Equatable` | `==` operator | Comparing values |
| `Hashable` | Hash value | Dictionary keys, Set members |
| `Comparable` | `<`, `>` operators | Sorting |
| `Codable` | JSON/Plist encoding/decoding | Serialization |
| `Identifiable` | `id` property | SwiftUI lists, diffing |
| `CustomStringConvertible` | `description` property | String interpolation |
| `Sendable` | Safe to pass across concurrency boundaries | Actors, async/await |
| `Error` | Can be thrown | Error handling |
| `Sequence` / `Collection` | Iteration / indexed access | Custom collections |

Most of these can be auto-synthesized by the compiler:

```swift
struct User: Identifiable, Codable, Hashable {
    let id: UUID
    var name: String
    var email: String
    // Codable, Hashable, Equatable are auto-synthesized
}
```

---

## Part 7 — Generics

Generics let you write flexible, reusable code that works with any type, subject to constraints.

### Generic Functions

```swift
func swapped<T>(_ a: T, _ b: T) -> (T, T) {
    (b, a)
}

let result = swapped(1, 2)    // (2, 1)
let names = swapped("Alice", "Bob")    // ("Bob", "Alice")
```

### Generic Types

```swift
struct Stack<Element> {
    private var items: [Element] = []
    
    var isEmpty: Bool { items.isEmpty }
    var count: Int { items.count }
    
    mutating func push(_ item: Element) {
        items.append(item)
    }
    
    mutating func pop() -> Element? {
        items.popLast()
    }
    
    func peek() -> Element? {
        items.last
    }
}

var intStack = Stack<Int>()
intStack.push(1)
intStack.push(2)
print(intStack.pop())    // Optional(2)
```

### Constraints

```swift
// single constraint
func largest<T: Comparable>(_ a: T, _ b: T) -> T {
    a > b ? a : b
}

// multiple constraints
func findDuplicate<T: Hashable & Comparable>(in array: [T]) -> T? {
    var seen = Set<T>()
    for item in array {
        if seen.contains(item) { return item }
        seen.insert(item)
    }
    return nil
}

// where clause for complex constraints
func merge<S1: Sequence, S2: Sequence>(
    _ a: S1, _ b: S2
) -> [S1.Element] where S1.Element == S2.Element, S1.Element: Hashable {
    Array(Set(Array(a) + Array(b)))
}
```

### Constrained Extensions

Add functionality to a generic type only when its type parameters meet certain constraints:

```swift
extension Stack where Element: Equatable {
    func contains(_ item: Element) -> Bool {
        items.contains(item)
    }
}

extension Stack where Element: Numeric {
    func sum() -> Element {
        items.reduce(0, +)
    }
}

extension Array where Element: StringProtocol {
    func joinedWithComma() -> String {
        joined(separator: ", ")
    }
}
```

### Phantom Types

Use generic parameters that appear in the type signature but not in stored properties — for compile-time enforcement of constraints:

```swift
struct Identifier<Entity>: Hashable {
    let rawValue: String
}

struct User {
    let id: Identifier<User>
    let name: String
}

struct Post {
    let id: Identifier<Post>
    let title: String
}

func fetchUser(id: Identifier<User>) async throws -> User { /* ... */ }

let userId = Identifier<User>(rawValue: "123")
let postId = Identifier<Post>(rawValue: "456")

// fetchUser(id: postId)    // compile error — wrong phantom type
```

---

## Part 8 — Collections

### Array

```swift
var numbers = [1, 2, 3, 4, 5]

// access
numbers[0]           // 1
numbers.first        // Optional(1)
numbers.last         // Optional(5)

// mutating
numbers.append(6)
numbers.insert(0, at: 0)
numbers.remove(at: 3)
numbers.removeAll { $0.isMultiple(of: 2) }

// transforming
let doubled = numbers.map { $0 * 2 }
let evens = numbers.filter { $0 % 2 == 0 }
let sum = numbers.reduce(0, +)

// slicing — returns ArraySlice, not Array
let firstThree = numbers.prefix(3)         // ArraySlice<Int>
let tail = numbers.dropFirst()

// checking
numbers.contains(3)           // true
numbers.allSatisfy { $0 > 0 } // true
numbers.isEmpty                // false

// sorting
numbers.sort()                     // in-place
let sorted = numbers.sorted()     // returns new array
let custom = users.sorted { $0.name < $1.name }
let byKey = users.sorted(using: KeyPathComparator(\.age))
```

### Dictionary

```swift
var scores: [String: Int] = [
    "Alice": 95,
    "Bob": 87,
]

// access — always returns optional
scores["Alice"]        // Optional(95)
scores["Charlie"]      // nil

// default value
scores["Charlie", default: 0]    // 0 — does NOT insert

// mutation
scores["Charlie"] = 72           // insert
scores["Alice"] = nil            // remove
scores.removeValue(forKey: "Bob")

// merge
scores.merge(["Dave": 91, "Alice": 100]) { _, new in new }

// iteration (order is NOT guaranteed)
for (name, score) in scores {
    print("\(name): \(score)")
}

// transform
let passing = scores.filter { $0.value >= 90 }
let names = scores.map { $0.key }
let grouped = users.reduce(into: [:]) { dict, user in
    dict[user.department, default: []].append(user)
}
```

### Set

```swift
var tags: Set<String> = ["swift", "ios", "xcode"]

tags.insert("swiftui")
tags.remove("xcode")
tags.contains("swift")    // true

// set operations
let a: Set = [1, 2, 3, 4]
let b: Set = [3, 4, 5, 6]

a.union(b)            // {1, 2, 3, 4, 5, 6}
a.intersection(b)     // {3, 4}
a.subtracting(b)      // {1, 2}
a.symmetricDifference(b)  // {1, 2, 5, 6}
a.isSubset(of: b)     // false
```

### Copy-on-Write

`Array`, `Dictionary`, `Set`, and `String` use **copy-on-write** internally. When you assign to a new variable, the underlying storage is shared — the actual copy only happens when one of the copies is mutated:

```swift
var a = [1, 2, 3]
var b = a            // no copy yet — shared storage

b.append(4)          // NOW the storage is copied for b
// a and b are independent: a = [1,2,3], b = [1,2,3,4]
```

This gives you value semantics (safe, no shared mutable state) with reference-type performance (copies are deferred until needed). Custom structs do NOT get this automatically — you must implement it manually using `isKnownUniquelyReferenced`.

### Sequence and Collection Protocols

To create a custom collection, conform to `Sequence` (for iteration) or `Collection` (for indexed access):

```swift
// minimal Sequence conformance
struct Countdown: Sequence {
    let start: Int
    
    func makeIterator() -> CountdownIterator {
        CountdownIterator(current: start)
    }
}

struct CountdownIterator: IteratorProtocol {
    var current: Int
    
    mutating func next() -> Int? {
        guard current > 0 else { return nil }
        defer { current -= 1 }
        return current
    }
}

for n in Countdown(start: 5) {
    print(n)    // 5, 4, 3, 2, 1
}
```

---

## Part 9 — Strings and Unicode

Swift strings are correct-by-default for Unicode — but this means they behave differently from strings in most other languages.

### String is Not an Array

You cannot index a Swift String with integers:

```swift
let text = "Hello"
// text[0]    // compile error — no integer subscript
text[text.startIndex]                     // "H"
text[text.index(text.startIndex, offsetBy: 1)]    // "e"
```

**Why:** Swift strings are composed of **extended grapheme clusters** — the character as a human perceives it. A single "character" can be multiple Unicode scalars:

```swift
let flag = "🇺🇸"
flag.count              // 1 — one grapheme cluster
flag.unicodeScalars.count    // 2 — U+1F1FA U+1F1F8

let accent = "é"
accent.count            // 1
accent.unicodeScalars.count  // could be 1 (U+00E9) or 2 (e + combining accent)

let family = "👨‍👩‍👧‍👦"
family.count            // 1 — one grapheme cluster
family.unicodeScalars.count  // 7 — four emoji joined by ZWJ characters
```

Because grapheme clusters have variable width, `String.count` is O(n) — it must walk the entire string to count characters. This is why integer subscripting isn't provided: `text[5]` would also be O(n), which would be misleadingly expensive.

### String Views

Access the underlying representation via views:

```swift
let text = "Hello, 世界!"

text.count                        // 9 characters (grapheme clusters)
text.utf8.count                   // 15 bytes
text.utf16.count                  // 11 code units
text.unicodeScalars.count         // 9 scalar values

// iterate over specific views
for scalar in text.unicodeScalars {
    print(scalar, scalar.value)
}

for byte in text.utf8 {
    print(byte)
}
```

### Substring

Slicing a string produces a `Substring`, which shares storage with the original string (zero-copy):

```swift
let greeting = "Hello, World!"
let hello = greeting.prefix(5)    // Substring — shares memory with greeting

// convert to String when you want an independent copy
let independent = String(hello)

// Substring is useful for parsing — no copies until you need to store the result
func firstName(of fullName: String) -> String {
    let first = fullName.prefix(while: { $0 != " " })    // Substring
    return String(first)    // copy only when returning
}
```

### String Interpolation

```swift
let name = "Alice"
let age = 30
let message = "Name: \(name), Age: \(age)"

// custom formatting
let price = 19.99
let formatted = "Price: \(price, format: .currency(code: "USD"))"

// multiline strings
let json = """
    {
        "name": "\(name)",
        "age": \(age)
    }
    """
```

### Common String Operations

```swift
let text = "  Hello, Swift!  "

// trimming
text.trimmingCharacters(in: .whitespaces)    // "Hello, Swift!"

// case
text.lowercased()
text.uppercased()

// searching
text.contains("Swift")           // true
text.hasPrefix("  Hello")        // true
text.hasSuffix("!  ")            // true
text.range(of: "Swift")          // Range<String.Index>?

// splitting
"a,b,c".split(separator: ",")   // ["a", "b", "c"] — [Substring]

// replacing
text.replacing("Swift", with: "World")    // "  Hello, World!  "

// regex (Swift 5.7+)
let digits = text.matches(of: /\d+/)
if let match = text.firstMatch(of: /Hello, (\w+)!/) {
    print(match.1)    // "Swift"
}
```

---

## Part 10 — Error Handling

### Throwing Functions

```swift
enum ValidationError: Error, LocalizedError {
    case empty
    case tooShort(minimum: Int)
    case invalidFormat(reason: String)
    
    var errorDescription: String? {
        switch self {
        case .empty: return "Value cannot be empty"
        case .tooShort(let min): return "Must be at least \(min) characters"
        case .invalidFormat(let reason): return "Invalid format: \(reason)"
        }
    }
}

func validateEmail(_ email: String) throws {
    guard !email.isEmpty else { throw ValidationError.empty }
    guard email.count >= 5 else { throw ValidationError.tooShort(minimum: 5) }
    guard email.contains("@") else {
        throw ValidationError.invalidFormat(reason: "missing @")
    }
}
```

### Typed Throws (Swift 6+)

Declare the exact error type a function can throw:

```swift
func validatePassword(_ password: String) throws(ValidationError) {
    guard !password.isEmpty else { throw .empty }
    guard password.count >= 8 else { throw .tooShort(minimum: 8) }
}

// caller gets typed error without casting
do {
    try validatePassword(input)
} catch .empty {
    showError("Password required")
} catch .tooShort(let min) {
    showError("Need at least \(min) characters")
} catch .invalidFormat(let reason) {
    showError(reason)
}
// no catch-all needed — compiler knows all cases are handled
```

### do-catch

```swift
do {
    try validateEmail(input)
    try validatePassword(input)
    createAccount()
} catch let error as ValidationError {
    showValidationError(error)
} catch {
    // generic catch — 'error' is any Error
    showGenericError(error)
}
```

### try? and try!

```swift
// try? — convert to optional (nil on error)
let isValid = try? validateEmail(input)    // Void? — nil if it threw

let user = try? loadUser()    // User? — nil if any error occurred

// try! — force (crashes on error — avoid in production)
let config = try! loadConfig()    // crashes if loadConfig throws
```

### Result Type

For when you need to store, pass, or transform errors as values:

```swift
func fetchUser(id: String) -> Result<User, NetworkError> {
    // ...
}

// using Result
switch fetchUser(id: "123") {
case .success(let user):
    display(user)
case .failure(let error):
    handleError(error)
}

// Result interop with throwing
let result = Result { try riskyOperation() }
let value = try result.get()    // throws if failure

// transform
let name = result.map { $0.name }    // Result<String, Error>
```

### rethrows

A function that only throws if its closure parameter throws:

```swift
func perform<T>(_ body: () throws -> T) rethrows -> T {
    try body()
}

// non-throwing closure — perform doesn't throw
let x = perform { 42 }

// throwing closure — perform throws
let y = try perform { try riskyOperation() }
```

---

## Part 11 — Concurrency

Swift's concurrency model is built on three pillars: **async/await** (structured asynchronous code), **actors** (thread-safe shared state), and **Sendable** (compile-time data-race prevention). Swift 6 enforces strict concurrency checking — data races are caught at compile time.

### async/await

```swift
// async function — can suspend
func fetchUser(id: String) async throws -> User {
    let url = URL(string: "https://api.example.com/users/\(id)")!
    let (data, _) = try await URLSession.shared.data(from: url)
    return try JSONDecoder().decode(User.self, from: data)
}

// calling async functions
func loadProfile() async {
    do {
        let user = try await fetchUser(id: "123")
        print(user.name)
    } catch {
        print("Failed: \(error)")
    }
}

// bridging from synchronous to async
func startLoading() {
    Task {
        await loadProfile()
    }
}
```

### Structured Concurrency

**async let** — run a fixed number of tasks in parallel:

```swift
func loadDashboard() async throws -> Dashboard {
    async let user = fetchUser()
    async let posts = fetchPosts()
    async let notifications = fetchNotifications()
    
    return try await Dashboard(
        user: user,
        posts: posts,
        notifications: notifications
    )
    // all three run concurrently; we await all three at the end
}
```

**TaskGroup** — run a dynamic number of tasks:

```swift
func fetchAllUsers(ids: [String]) async throws -> [User] {
    try await withThrowingTaskGroup(of: User.self) { group in
        for id in ids {
            group.addTask {
                try await fetchUser(id: id)
            }
        }
        
        var users: [User] = []
        for try await user in group {
            users.append(user)
        }
        return users
    }
}
```

### Task

An unstructured task that runs independently:

```swift
// inherits actor context
Task {
    await doSomething()
}

// explicitly off the current actor
Task.detached {
    await doSomethingInBackground()
}

// with priority
Task(priority: .background) {
    await lowPriorityWork()
}
```

### Task Cancellation

Cancellation is cooperative — your code must check for it:

```swift
func processItems(_ items: [Item]) async throws {
    for item in items {
        try Task.checkCancellation()    // throws CancellationError
        await process(item)
    }
}

// or check without throwing
func processItems(_ items: [Item]) async {
    for item in items {
        guard !Task.isCancelled else { return }
        await process(item)
    }
}
```

### Actors

An actor is a reference type that serializes access to its mutable state:

```swift
actor BankAccount {
    let id: String
    private(set) var balance: Double
    
    init(id: String, balance: Double) {
        self.id = id
        self.balance = balance
    }
    
    func deposit(_ amount: Double) {
        balance += amount
    }
    
    func withdraw(_ amount: Double) throws {
        guard balance >= amount else {
            throw BankError.insufficientFunds
        }
        balance -= amount
    }
}

// accessing actor properties requires await
let account = BankAccount(id: "1", balance: 1000)
let balance = await account.balance         // read requires await
try await account.withdraw(500)              // method call requires await

// non-isolated properties can be accessed synchronously
let id = account.id    // 'let' properties are safe — no await needed
```

### @MainActor

Guarantees code runs on the main thread (UI thread):

```swift
@MainActor
class ViewModel {
    var items: [Item] = []
    var isLoading = false
    
    func load() async {
        isLoading = true
        defer { isLoading = false }
        items = try? await fetchItems() ?? []
    }
}

// individual functions or properties
@MainActor
func updateUI() {
    // guaranteed main thread
}
```

### Sendable

`Sendable` marks types that can safely cross concurrency boundaries. The compiler enforces this in Swift 6:

```swift
// value types with Sendable properties are implicitly Sendable
struct Point: Sendable {    // implicitly Sendable (all properties are Sendable)
    var x: Double
    var y: Double
}

// classes must be final with immutable properties
final class Config: Sendable {
    let apiKey: String
    let baseURL: URL
    init(apiKey: String, baseURL: URL) {
        self.apiKey = apiKey
        self.baseURL = baseURL
    }
}

// actors are implicitly Sendable

// @unchecked Sendable — you guarantee thread safety manually
final class AtomicCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var _value = 0
    
    var value: Int {
        lock.lock()
        defer { lock.unlock() }
        return _value
    }
    
    func increment() {
        lock.lock()
        defer { lock.unlock() }
        _value += 1
    }
}
```

### AsyncSequence and AsyncStream

```swift
// consuming an async sequence
func processLines(from url: URL) async throws {
    for try await line in url.lines {
        print(line)
    }
}

// creating a custom async stream
func temperatureUpdates() -> AsyncStream<Double> {
    AsyncStream { continuation in
        let monitor = TemperatureMonitor()
        monitor.onUpdate = { temp in
            continuation.yield(temp)
        }
        monitor.onComplete = {
            continuation.finish()
        }
        
        continuation.onTermination = { _ in
            monitor.stop()
        }
        
        monitor.start()
    }
}

// consuming
for await temp in temperatureUpdates() {
    print("Temperature: \(temp)")
}
```

---

## Part 12 — Macros

Swift macros (introduced in Swift 5.9) are compile-time code generation. The macro runs during compilation and produces Swift code that replaces or augments the macro invocation. You can inspect the expanded code in Xcode (right-click → Expand Macro).

### Freestanding Macros

Appear standalone using `#` syntax:

```swift
// expression macro — produces a value
let (result, code) = #stringify(2 + 3)
// expands to: (2 + 3, "2 + 3") — both the value and the source code

// declaration macro — produces new declarations
#warning("This is incomplete")    // compiler warning
```

### Attached Macros

Attached to declarations using `@` syntax. They add or modify code on the declaration:

```swift
// @Observable — the most common macro you'll use
@Observable    // attached(member, memberAttribute, conformance)
class UserSettings {
    var theme: Theme = .system
    var fontSize: Int = 16
    var notifications: Bool = true
}

// expands to (simplified):
// - Adds ObservationTracking conformance
// - Wraps each stored property with observation access tracking
// - Generates _$observationRegistrar and access/withMutation methods
```

### Macro Roles

| Role | What it does | Example |
|---|---|---|
| `@freestanding(expression)` | Produces a value | `#stringify`, `#Predicate` |
| `@freestanding(declaration)` | Creates new declarations | `#warning` |
| `@attached(peer)` | Adds sibling declarations | async overloads |
| `@attached(member)` | Adds members to a type | `@Observable` adding registrar |
| `@attached(memberAttribute)` | Adds attributes to members | `@Observable` adding tracking |
| `@attached(accessor)` | Adds get/set accessors | property wrappers via macros |
| `@attached(conformance)` | Adds protocol conformance | `@Observable` adding Observable |
| `@attached(extension)` | Adds extension methods/conformances | auto-conformance macros |

### Writing a Macro

Macros are implemented as Swift packages using the `SwiftSyntax` library:

```swift
// 1. declare the macro (in your library)
@freestanding(expression)
public macro stringify<T>(_ value: T) -> (T, String) =
    #externalMacro(module: "MyMacroPlugin", type: "StringifyMacro")

// 2. implement the macro (in a compiler plugin target)
import SwiftSyntax
import SwiftSyntaxMacros

public struct StringifyMacro: ExpressionMacro {
    public static func expansion(
        of node: some FreestandingMacroExpansionSyntax,
        in context: some MacroExpansionContext
    ) throws -> ExprSyntax {
        guard let argument = node.arguments.first?.expression else {
            throw MacroError.missingArgument
        }
        return "(\(argument), \(literal: argument.description))"
    }
}

// 3. test the macro
import MacroTesting

@Test func testStringify() {
    assertMacroExpansion(
        #"#stringify(2 + 3)"#,
        expandedSource: #"(2 + 3, "2 + 3")"#,
        macros: ["stringify": StringifyMacro.self]
    )
}
```

**Key points:**
- Macros are **additive** — they can only add code, never remove or modify existing code.
- They run at **compile time** — no runtime overhead.
- Always use **Expand Macro** in Xcode to inspect what a macro generates.
- Macros you'll encounter most: `@Observable`, `@Model` (SwiftData), `#Preview`, `#Predicate`, `@Entry`.

---

## Part 13 — Result Builders

Result builders power SwiftUI's declarative syntax. They're a general-purpose feature for building DSLs (domain-specific languages) in Swift.

### How SwiftUI's ViewBuilder Works

When you write:

```swift
VStack {
    Text("Hello")
    Text("World")
}
```

The `VStack` initializer takes a `@ViewBuilder` closure. The `@ViewBuilder` result builder transforms the closure body: each statement becomes a component, and the builder combines them into a single view (a `TupleView<(Text, Text)>`).

### Building Your Own

```swift
@resultBuilder
struct HTMLBuilder {
    // combine multiple statements into one result
    static func buildBlock(_ components: String...) -> String {
        components.joined(separator: "\n")
    }
    
    // enable if statements (without else)
    static func buildOptional(_ component: String?) -> String {
        component ?? ""
    }
    
    // enable if-else — first branch
    static func buildEither(first component: String) -> String {
        component
    }
    
    // enable if-else — second branch
    static func buildEither(second component: String) -> String {
        component
    }
    
    // enable for-in loops
    static func buildArray(_ components: [String]) -> String {
        components.joined(separator: "\n")
    }
}
```

```swift
func html(@HTMLBuilder content: () -> String) -> String {
    "<html>\n\(content())\n</html>"
}

func div(@HTMLBuilder content: () -> String) -> String {
    "<div>\(content())</div>"
}

func p(_ text: String) -> String { "<p>\(text)</p>" }
func h1(_ text: String) -> String { "<h1>\(text)</h1>" }

// usage — reads like a DSL
let page = html {
    h1("Welcome")
    div {
        p("Hello, World!")
        if showSubtitle {
            p("Subtitle")
        }
        for item in items {
            p(item.title)
        }
    }
}
```

### Builder Methods Reference

| Method | Enables | Example |
|---|---|---|
| `buildBlock` | Multiple statements | `Text("A"); Text("B")` |
| `buildOptional` | `if` without `else` | `if condition { ... }` |
| `buildEither(first/second)` | `if-else` | `if x { A } else { B }` |
| `buildArray` | `for-in` loops | `for item in list { ... }` |
| `buildExpression` | Transform individual expressions | Type coercion |
| `buildLimitedAvailability` | `#available` checks | `if #available(iOS 17, *) { ... }` |
| `buildFinalResult` | Transform the final output | Post-processing |

---

## Part 14 — Property Wrappers

Property wrappers encapsulate reusable getter/setter/storage logic behind an `@Attribute` syntax.

### Anatomy

```swift
@propertyWrapper
struct Clamped<Value: Comparable> {
    var wrappedValue: Value {
        didSet {
            wrappedValue = min(max(wrappedValue, range.lowerBound), range.upperBound)
        }
    }
    
    let range: ClosedRange<Value>
    
    init(wrappedValue: Value, _ range: ClosedRange<Value>) {
        self.range = range
        self.wrappedValue = min(max(wrappedValue, range.lowerBound), range.upperBound)
    }
}

struct AudioSettings {
    @Clamped(0...100) var volume: Int = 50
    @Clamped(20...20000) var frequency: Int = 440
}

var audio = AudioSettings()
audio.volume = 150     // clamped to 100
audio.frequency = 10   // clamped to 20
```

### Projected Value ($)

Property wrappers can expose additional functionality via the projected value (`$`):

```swift
@propertyWrapper
struct Validated<Value> {
    var wrappedValue: Value
    var projectedValue: Bool    // accessed via $property
    
    init(wrappedValue: Value, validator: @escaping (Value) -> Bool) {
        self.wrappedValue = wrappedValue
        self.projectedValue = validator(wrappedValue)
        self.validator = validator
    }
    
    private let validator: (Value) -> Bool
    
    mutating func validate() {
        projectedValue = validator(wrappedValue)
    }
}

// SwiftUI uses this pattern extensively:
// @State var name = ""
// $name → Binding<String> (the projected value)
```

### Common Property Wrappers

| Wrapper | Source | Purpose |
|---|---|---|
| `@State` | SwiftUI | View-local state |
| `@Binding` | SwiftUI | Read-write access to parent's state |
| `@Environment` | SwiftUI | Injected values from view tree |
| `@AppStorage` | SwiftUI | UserDefaults-backed state |
| `@Published` | Combine | Observable property (legacy, replaced by `@Observable`) |
| `@Observable` | Observation | Type-level observation (it's a macro, not a property wrapper) |
| `@Model` | SwiftData | Persistable model |
| `@Query` | SwiftData | Auto-updating fetch |

---

## Part 15 — Ownership and Noncopyable Types

Swift 5.9+ introduced ownership annotations and noncopyable types — bringing Rust-style move semantics to Swift for scenarios where copies are dangerous or expensive.

### Noncopyable Types (~Copyable)

By default, every type in Swift conforms to an implicit `Copyable` protocol. Suppress it with `~Copyable` to create a type that can only be moved:

```swift
struct FileHandle: ~Copyable {
    private let fd: Int32
    
    init(path: String) throws {
        fd = open(path, O_RDONLY)
        guard fd >= 0 else { throw IOError.openFailed }
    }
    
    deinit {
        close(fd)    // guaranteed cleanup — exactly once
    }
    
    consuming func takeOwnership() -> Int32 {
        let result = fd
        discard self    // prevent deinit from closing fd
        return result
    }
}

var handle = try FileHandle(path: "/tmp/data")
let handle2 = handle    // MOVE — handle is now consumed
// handle.read()       // compile error — handle has been consumed
```

**Why it matters:**
- **Resource safety:** a file handle, database connection, or hardware lock should never be duplicated.
- **Guaranteed cleanup:** `deinit` runs exactly once, when the unique owner goes out of scope.
- **Compile-time enforcement:** the compiler ensures no accidental copies or use-after-move.

### Borrowing and Consuming

Explicit ownership annotations for function parameters:

```swift
struct LargeBuffer: ~Copyable {
    var data: [UInt8]
    
    // borrowing — temporary read-only access, caller keeps ownership
    borrowing func checksum() -> UInt32 {
        var hash: UInt32 = 0
        for byte in data { hash = hash &+ UInt32(byte) }
        return hash
    }
    
    // consuming — takes ownership, caller can no longer use the value
    consuming func encrypt(key: [UInt8]) -> LargeBuffer {
        // transforms and returns a new buffer
        // self is consumed — caller's copy is gone
        var encrypted = data
        // ... encryption logic ...
        return LargeBuffer(data: encrypted)
    }
    
    // mutating — exclusive mutable access (existing concept)
    mutating func append(_ bytes: [UInt8]) {
        data.append(contentsOf: bytes)
    }
}
```

These annotations also work on regular (`Copyable`) types as **performance hints** — they tell the compiler it can avoid retain/release overhead:

```swift
// on regular types, these are optimization hints
func process(borrowing buffer: [UInt8]) {
    // buffer is borrowed — no copy, no retain
}

func consume(consuming buffer: [UInt8]) {
    // buffer is moved — no retain on entry, no release on exit
    // but caller can no longer use their copy
}
```

### When to Use

- **Noncopyable types:** file handles, locks, unique hardware resources, "move-only" tokens.
- **Borrowing/consuming on regular types:** hot-path performance optimization in libraries. Most application code doesn't need these annotations — the compiler already optimizes well.

---

## Part 16 — Swift 6.x: The Language in 2026

### Swift Version Timeline

| Version | Release | Headline Feature |
|---|---|---|
| **Swift 5.9** | Sep 2023 | Macros, noncopyable types |
| **Swift 5.10** | Mar 2024 | Complete concurrency checking (opt-in) |
| **Swift 6.0** | Sep 2024 | Strict concurrency (data-race safety at compile time) |
| **Swift 6.1** | Mar 2025 | Nonisolated refinements, TaskGroup inference, SwiftPM traits |
| **Swift 6.2** | Sep 2025 | Approachable concurrency, InlineArray, Span |
| **Swift 6.3** | Mar 2026 | `@c` interop attribute, Android SDK, embedded improvements |

### Strict Concurrency (Swift 6.0)

The headline feature of Swift 6. The compiler guarantees your code is free of data races at compile time. New projects have it enabled by default. Existing projects migrate with build settings:

```
// in Package.swift
.target(name: "MyTarget", swiftSettings: [
    .swiftLanguageMode(.v6)
])

// or incrementally
.swiftSetting(.enableExperimentalFeature("StrictConcurrency"))
```

### Approachable Concurrency (Swift 6.2)

Responding to community feedback that strict concurrency was too aggressive, Swift 6.2 introduced pragmatic defaults:

- **Default main-actor isolation:** new projects default to `@MainActor` for app-level code, making single-threaded apps simple.
- **`@concurrent` attribute:** opt into concurrent execution explicitly.
- **Caller-context async:** async functions can inherit the caller's isolation, reducing unnecessary actor hops.

```swift
// Swift 6.2: this function runs in the caller's context by default
func fetchData() async throws -> Data {
    // runs on MainActor if called from MainActor
    // runs on an actor if called from an actor
    // no surprise thread switches
}

// opt into concurrent execution
@concurrent
func processInBackground() async {
    // explicitly runs off the main actor
}
```

### InlineArray (Swift 6.2)

Fixed-size arrays with inline storage (no heap allocation):

```swift
let rgb: InlineArray<3, UInt8> = [255, 128, 0]

// useful for performance-critical code where the size is known at compile time
// and you want to avoid heap allocation
```

### Span (Swift 6.2)

A safe view into contiguous memory, replacing many uses of `UnsafeBufferPointer`:

```swift
func process(_ data: Span<UInt8>) {
    for byte in data {
        // safe, bounds-checked access
    }
}
```

### @c Attribute (Swift 6.3)

Expose Swift functions to C code without manual header management:

```swift
@c func handleCallback(value: Int32) -> Int32 {
    return value * 2
}
// generates a C-callable function — no bridging header needed
```

### Embedded Swift

A subset of Swift for resource-constrained environments (microcontrollers, firmware, kernels). No runtime, no reflection, no existentials — but full type safety, generics, and value types:

```swift
// embedded Swift — no heap allocation, no runtime
@_extern(c, "led_on")
func ledOn()

@_extern(c, "delay_ms")
func delay(ms: UInt32)

@main
struct Blinker {
    static func main() {
        while true {
            ledOn()
            delay(ms: 500)
            ledOff()
            delay(ms: 500)
        }
    }
}
```

### Swift on Non-Apple Platforms

Swift is officially supported on:

| Platform | Status in 2026 |
|---|---|
| **macOS, iOS, watchOS, tvOS, visionOS** | First-class |
| **Linux** | First-class (server-side Swift, Vapor framework) |
| **Windows** | Supported (community-driven, improving rapidly) |
| **Android** | Official SDK as of Swift 6.3 |
| **WebAssembly** | Community-supported (SwiftWasm) |
| **Embedded** | Experimental → practical |

---

## Quick Reference

### Type Decision Tree

```
Need identity or inheritance?
  Yes → class (or actor for concurrent access)
  No → struct

Need to cross concurrency boundaries?
  Yes → must be Sendable (struct with Sendable fields, or actor)
  No → any type works

Need a fixed set of variants?
  Yes → enum (with associated values if needed)
  No → struct or class

Need to prevent copies?
  Yes → ~Copyable struct
  No → regular struct
```

### Memory Management Cheat Sheet

| Situation | Use |
|---|---|
| Default reference | `strong` (implicit) |
| Delegate or parent reference | `weak` |
| Reference guaranteed to outlive holder | `unowned` |
| Closure capturing `self` (escaping) | `[weak self]` |
| Closure capturing `self` (non-escaping) | No annotation needed |

### Concurrency Cheat Sheet

| Need | Use |
|---|---|
| Run async code | `async/await` |
| Fixed parallelism | `async let` |
| Dynamic parallelism | `TaskGroup` |
| Thread-safe shared state | `actor` |
| UI thread guarantee | `@MainActor` |
| Cross-boundary safety | `Sendable` |
| Callback → async bridge | `withCheckedContinuation` |
| Async iteration | `AsyncSequence` / `AsyncStream` |

---

That's the guide. Swift in 2026 is a language with two faces: a high-level, safe, expressive language for app development (protocols, generics, closures, result builders, macros — all the abstraction power you want), and an increasingly capable systems language (ownership, noncopyable types, inline arrays, embedded Swift, C interop) that's expanding beyond the Apple ecosystem. The type system enforces more invariants at compile time than almost any mainstream language — optionals for null safety, Sendable for thread safety, exhaustive switches for enum coverage, typed throws for error handling — and the 6.x evolution is steadily closing the remaining gaps.

---

## Where to Go Next

- **Read [*The Swift Programming Language*](https://docs.swift.org/swift-book/)** (TSPL) cover to cover — it's free, current, and the canonical statement of everything in Parts 1–8; this guide is the map, TSPL is the territory.
- **Read the [Swift Evolution proposals](https://github.com/swiftlang/swift-evolution/tree/main/proposals)** for the features that surprised you — each proposal documents the *why* behind a feature (motivation, alternatives considered) better than any tutorial; the concurrency proposals (SE-0296, SE-0306, SE-0414) are required reading for Part 9's mental model.
- **Follow the [Swift.org blog](https://www.swift.org/blog/)** and the [migration guide to Swift 6 data-race safety](https://www.swift.org/migration/documentation/migrationguide/) — the strict-concurrency transition is the live edge of the language.
- **Build something with the strictness on.** Start a project with Swift 6 language mode, make it compile warning-free with complete concurrency checking, and let the compiler teach you `Sendable` and actor isolation through real errors.
- **Adjacent guides in this repo:** [iOS Development](IOS_DEVELOPMENT_STUDY_GUIDE.md) (the platform this language usually targets), [CB8 iOS](CB8_IOS_STUDY_GUIDE.md) (a worked porting project), and [Advanced Rust](ADVANCED_RUST_STUDY_GUIDE.md) (the language Swift's ownership features are converging toward — the comparison sharpens both).

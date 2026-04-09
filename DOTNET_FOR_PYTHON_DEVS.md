# .NET for Python Developers

A study guide that skips the basics and focuses on what actually trips up Python developers learning modern, cross-platform .NET. This guide targets **.NET 10** and **C# 14** as of **April 9, 2026**, and intentionally avoids legacy Windows-only `.NET Framework` advice unless the distinction matters.

---

## Table of Contents

1. [What Modern .NET Means](#1-what-modern-net-means)
2. [Type System, Compilation & Nullability](#2-type-system-compilation--nullability)
3. [Classes, Records, Structs & Properties](#3-classes-records-structs--properties)
4. [Interfaces, Delegates & Pattern Matching](#4-interfaces-delegates--pattern-matching)
5. [Generics, Collections & LINQ](#5-generics-collections--linq)
6. [Exceptions, `using` & Resource Cleanup](#6-exceptions-using--resource-cleanup)
7. [Async/Await, `Task` & Cancellation](#7-asyncawait-task--cancellation)
8. [Concurrency & Parallelism](#8-concurrency--parallelism)
9. [Dependency Injection, Configuration, Logging & the Generic Host](#9-dependency-injection-configuration-logging--the-generic-host)
10. [Projects, `csproj`, NuGet & CLI Workflow](#10-projects-csproj-nuget--cli-workflow)
11. [ASP.NET Core for Python Web Developers](#11-aspnet-core-for-python-web-developers)
12. [Serialization, HTTP & Data Access](#12-serialization-http--data-access)
13. [Testing, Analyzers & Tooling](#13-testing-analyzers--tooling)
14. [Common Pitfalls for Python Developers](#14-common-pitfalls-for-python-developers)
15. [Quick Reference Cheat Sheet](#15-quick-reference-cheat-sheet)
16. [Essential First-Party Libraries & Tools](#16-essential-first-party-libraries--tools)

---

## 1. What Modern .NET Means

Official docs: [Introduction to .NET](https://learn.microsoft.com/en-us/dotnet/core/introduction), [What's new in .NET 10](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-10/overview), [What's new in C# 14](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-14)

If you have been away from the Microsoft ecosystem for a while, the first important reset is terminology. When people say ".NET" today, they usually mean the **modern, unified, cross-platform** platform that runs on macOS, Linux, and Windows. That is the line you want to learn.

The old split mattered:
- **.NET Framework**: the older Windows-focused runtime and app model family
- **.NET**: the modern cross-platform runtime, SDK, libraries, and app stacks

### The One-Sentence Mental Model

Python is a language plus an interpreter plus a packaging ecosystem.  
Modern .NET is a **platform** that includes:
- a runtime
- an SDK and CLI
- base libraries
- app frameworks like ASP.NET Core
- languages, with **C#** as the dominant one

### .NET vs .NET Framework

| | Modern .NET | .NET Framework |
|---|---|---|
| Cross-platform | Yes | No, effectively Windows-only |
| Primary CLI | `dotnet` | Visual Studio / Windows tooling |
| Web stack | ASP.NET Core | Old ASP.NET / IIS-centric stack |
| Project format | SDK-style `csproj` | Older project system |
| What you should learn now | Yes | Usually no, unless maintaining legacy code |

### Why Python Developers Usually Like Modern .NET Once It Clicks

The modern stack has a few qualities that land well with Python developers:
- The CLI is excellent and consistent across platforms.
- The standard library and first-party framework story are much more integrated than Python's ecosystem.
- Tooling around building, testing, publishing, logging, configuration, and dependency injection is built into the platform instead of being assembled ad hoc.
- C# gives you static guarantees without forcing you into the extremely strict ownership model that Rust does.

### What Is Actually "Latest" Right Now

As of **April 9, 2026**:
- **.NET 10** is the latest stable .NET release and is an **LTS** release.
- **C# 14** is the latest stable C# language release and is supported on .NET 10.

That matters because a lot of blog posts still talk about:
- `.NET Core`
- `.NET 5/6/7/8/9`
- `.NET Framework`
- ASP.NET examples that predate the current hosting model

Those are not all wrong, but they are not the best baseline to learn from now.

### The Python Comparison

| Concept | Python | Modern .NET |
|---|---|---|
| Language | Python | Usually C# |
| Runtime | CPython | CLR / CoreCLR |
| Package manager | `pip` | NuGet |
| Project runner | `python app.py` | `dotnet run` |
| Web framework | Flask / FastAPI / Django | ASP.NET Core |
| Virtual env / version pinning | `venv`, `pyenv`, `uv` | SDK install + `global.json` |
| Batteries included | Some core libs, many third-party packages | Very large first-party platform |

---

## 2. Type System, Compilation & Nullability

Official docs: [Introduction to C#](https://learn.microsoft.com/en-us/dotnet/csharp/tour-of-csharp/), [Nullable reference types](https://learn.microsoft.com/en-us/dotnet/csharp/nullable-references), [C# language reference](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/)

This is the first real mental shift. Python lets you stay flexible until runtime. C# asks you to make your intent explicit earlier, and in return the compiler catches a lot of mistakes before the program ever runs.

### Static Typing Is Part of the Design, Not Just Documentation

```python
def add(a, b):
    return a + b

add(1, 2)
add("a", "b")
```

```csharp
int Add(int a, int b)
{
    return a + b;
}

Add(1, 2);
// Add("a", "b"); // compile error
```

In Python, the function contract is partly social.  
In C#, the function contract is part of the code the compiler enforces.

### `var` Does Not Mean Dynamic Typing

Python developers often see `var` and assume it behaves like Python's loose binding model. It does not.

```csharp
var name = "Ada";   // inferred as string
// name = 42;       // compile error
```

`var` means "the compiler can infer the type from the right-hand side." It does **not** mean the variable can later hold anything.

If you actually want dynamic runtime behavior, C# has `dynamic`:

```csharp
dynamic value = "hello";
Console.WriteLine(value.ToUpper());
// Console.WriteLine(value.DoesNotExist()); // runtime failure, not compile-time failure
```

Use `dynamic` sparingly. In modern .NET code, it is an escape hatch, not the default style.

### Compilation Model

C# code is compiled before it runs. In very simplified terms:
1. C# source is compiled into IL (intermediate language)
2. the runtime loads that code
3. the runtime JIT-compiles hot paths for the target machine

This is why .NET code often feels more "finished" earlier in the dev loop:
- compiler errors are stronger
- IDE refactoring is stronger
- runtime surprises from type mismatches are fewer

### Nullability Is Explicit Now

Python has `None`, but the type system does not enforce where it can appear unless you add tooling on top. Modern C# has **nullable reference types**, which are a huge deal.

```csharp
string name = "Ada";
string? maybeName = null;

Console.WriteLine(name.Length);
// Console.WriteLine(maybeName.Length); // warning: possible null dereference

if (maybeName is not null)
{
    Console.WriteLine(maybeName.Length); // safe
}
```

Key idea:
- `string` means "should not be null"
- `string?` means "may be null"

This is one of the best examples of C# being stricter than Python without being painful once you accept the workflow.

### Nullable Warnings Are About Intent

Nullable reference types are mainly a **compiler analysis system**. That means:
- you can still write bad code
- but the compiler now points at suspicious null flows
- good teams take those warnings seriously

If you ignore nullable warnings, you throw away one of the best safety features in modern C#.

### Python vs C# Null Story

| | Python | C# |
|---|---|---|
| Null-ish value | `None` | `null` |
| Type-level nullability | Usually external tooling only | Built into the compiler flow analysis |
| Common failure | `AttributeError` / `TypeError` at runtime | compiler warning before runtime, then possible `NullReferenceException` if ignored |

### The Real Mindset Shift

Python encourages "let the object flow through and see what happens."  
C# encourages "make the legal shapes explicit and let the compiler defend the boundaries."

That sounds restrictive at first. In practice it makes large codebases much easier to refactor safely.

---

## 3. Classes, Records, Structs & Properties

Official docs: [Records (C# reference)](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/record), [Types overview](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/), [Properties](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/properties)

Python developers often start by looking for the class story. In C#, object modeling is familiar on the surface but important details differ:
- value types vs reference types matter
- properties are more important than fields
- records are often a better fit than traditional classes for data-heavy code

### Classes Are the Default Reference Type

```csharp
public sealed class User
{
    public string Name { get; }
    public string Email { get; private set; }

    public User(string name, string email)
    {
        Name = name;
        Email = email;
    }

    public void ChangeEmail(string email)
    {
        Email = email;
    }
}
```

```python
class User:
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email

    def change_email(self, email: str) -> None:
        self.email = email
```

So far this feels normal. The deeper difference is how much C# uses the type system to shape what can happen.

### Properties Matter More Than Public Fields

In Python, `obj.name` is usually just an attribute access and can later grow into a property.  
In C#, public API surface is usually modeled with **properties**, not public fields.

```csharp
public string Name { get; init; }
public string Email { get; private set; }
```

Why?
- validation hooks
- clear read/write intent
- serialization support
- framework conventions

### Records Are the Closest Thing to Python `dataclass`

If you are modeling data, modern C# often wants a `record`, not a classic mutable class.

```csharp
public record UserDto(string Name, string Email);

var a = new UserDto("Ada", "ada@example.com");
var b = new UserDto("Ada", "ada@example.com");

Console.WriteLine(a == b); // True - value equality

var updated = a with { Email = "new@example.com" };
```

Python comparison:

```python
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class UserDto:
    name: str
    email: str

a = UserDto("Ada", "ada@example.com")
b = UserDto("Ada", "ada@example.com")
print(a == b)  # True

updated = replace(a, email="new@example.com")
```

Use records when:
- the type is mostly about data
- value equality makes sense
- immutability or near-immutability is useful
- you want concise DTO-style modeling

### `struct` Changes Copy Semantics

This is a classic Python-developer footgun. A `struct` is a **value type**. Assigning it copies the value.

```csharp
public struct Point
{
    public int X { get; set; }
    public int Y { get; set; }
}

var p1 = new Point { X = 1, Y = 2 };
var p2 = p1;   // copy
p2.X = 99;

Console.WriteLine(p1.X); // 1
Console.WriteLine(p2.X); // 99
```

In Python, assignment usually just gives you another reference to the same object.  
In C#, whether you copied or aliased something depends on the type category.

### Reference Types vs Value Types

| Category | Examples | Assignment behavior |
|---|---|---|
| Value types | `int`, `bool`, `DateTime`, `struct`, `record struct` | copied by value |
| Reference types | `string`, arrays, `List<T>`, `class`, `record class` | copies the reference |

Do not reduce this to "stack vs heap." That explanation is usually too simplistic and leads beginners into bad reasoning. The important part for day-to-day coding is **copy semantics** and **mutability**.

### Immutable-by-Convention Is Common

Modern C# code often leans toward:
- constructor initialization
- `init` properties
- records
- `readonly` fields where appropriate

That style often feels cleaner to Python developers coming from `dataclass(frozen=True)` or Pydantic-style DTOs than old-school mutable enterprise Java patterns.

### `required` Is Useful for API Modeling

```csharp
public sealed class CreateUserRequest
{
    public required string Name { get; init; }
    public required string Email { get; init; }
}
```

This is helpful when you want object initializers but still want the compiler to enforce required members.

### When to Reach for What

| Use | Best fit |
|---|---|
| Rich domain object with behavior and lifecycle | `class` |
| DTO / API payload / immutable-ish data carrier | `record` |
| Tiny value object where copying is intended | `struct` or `record struct` |

As a beginner, default to:
- `class` for service-like objects and behavior-heavy models
- `record` for request/response/data models
- avoid `struct` until you truly need value semantics

---

## 4. Interfaces, Delegates & Pattern Matching

Official docs: [Interfaces](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/interfaces), [Events](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/events/), [Pattern matching overview](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/functional/pattern-matching)

Python developers often bring in two instincts:
- duck typing is enough
- callbacks are just functions

C# supports both flexibility and indirection, but in more explicit forms.

### Interfaces Are Contracts, Not Suggestions

```csharp
public interface INotifier
{
    Task SendAsync(string message, CancellationToken cancellationToken = default);
}

public sealed class EmailNotifier : INotifier
{
    public Task SendAsync(string message, CancellationToken cancellationToken = default)
    {
        Console.WriteLine($"Email: {message}");
        return Task.CompletedTask;
    }
}
```

Unlike Python duck typing, interface compatibility is checked at compile time.

That gives you:
- stronger DI integration
- safer refactoring
- clearer API boundaries

### Why So Many .NET Interfaces Start With `I`

This is just naming convention:
- `IEnumerable<T>`
- `ILogger<T>`
- `IDisposable`
- `IHostedService`

At first it looks noisy. After a while it becomes a useful visual signal.

### Delegates Are Typed Function Signatures

In Python, functions are first-class and callbacks are easy. C# also supports passing behavior around, but usually through delegates like `Func<>`, `Action<>`, or custom delegate types.

```csharp
Func<int, int, int> add = (a, b) => a + b;
Action<string> log = message => Console.WriteLine(message);

Console.WriteLine(add(2, 3));
log("hello");
```

The common built-in delegate families:
- `Action<T1, ...>`: returns `void`
- `Func<T1, ..., TResult>`: returns a value
- `Predicate<T>`: returns `bool`

This is closer to "type-checked higher-order functions" than to Python's unconstrained callback style.

### Events Exist, but You Use Them Less in Web Backends

Events are publisher/subscriber mechanisms built on delegates.

```csharp
public class TimerService
{
    public event EventHandler? Tick;

    public void RaiseTick()
    {
        Tick?.Invoke(this, EventArgs.Empty);
    }
}
```

You will see events more in:
- desktop UI code
- framework internals
- libraries that expose notifications

You will see them less in typical ASP.NET Core backend code, where DI, middleware, channels, queues, and hosted services are more common.

### Pattern Matching Is One of the Best Parts of Modern C#

This is the area many Python developers genuinely enjoy once they start using it.

```csharp
static string Describe(object? value) => value switch
{
    null => "null",
    int n when n < 0 => "negative int",
    int n => $"int {n}",
    string { Length: 0 } => "empty string",
    string s => $"string {s}",
    UserDto(var name, _) => $"user {name}",
    _ => "something else"
};
```

Python comparison:

```python
def describe(value):
    match value:
        case None:
            return "null"
        case int() as n if n < 0:
            return "negative int"
        case int() as n:
            return f"int {n}"
        case "":
            return "empty string"
        case str() as s:
            return f"string {s}"
        case _:
            return "something else"
```

Modern C# pattern matching is not as "everything is dynamically inspectable" as Python, but it is powerful, readable, and increasingly central to idiomatic code.

### `is` in C# Is More Than Type Checking

```csharp
if (value is string s)
{
    Console.WriteLine(s.Length);
}
```

That is both:
- a type check
- a safe cast
- a local variable declaration

### Practical Advice

Prefer:
- interfaces for service boundaries
- delegates for small callback-shaped dependencies
- pattern matching for branching on type and shape

Avoid:
- giant inheritance trees
- overusing events in backend code when simpler control flow would work

---

## 5. Generics, Collections & LINQ

Official docs: [Generics in .NET](https://learn.microsoft.com/en-us/dotnet/standard/generics/), [LINQ overview](https://learn.microsoft.com/en-us/dotnet/standard/linq/), [Commonly used collection types](https://learn.microsoft.com/en-us/dotnet/standard/collections/selecting-a-collection-class)

This section is where .NET starts to feel really productive. The collection story is strong, the generic story is real, and LINQ gives you expressive data manipulation without a pile of helper libraries.

### Generics Are Real Runtime Types, Not Just Hints

Python type hints mostly help editors, static checkers, and humans.  
C# generics are part of the actual compiled type system.

```csharp
List<string> names = new() { "Ada", "Grace", "Linus" };
// names.Add(123); // compile error
```

### Common Collections You Will Use Constantly

| Python | C# |
|---|---|
| `list` | `List<T>` |
| `tuple` | `(T1, T2)` or custom type |
| `dict` | `Dictionary<TKey, TValue>` |
| `set` | `HashSet<T>` |
| immutable tuple-ish data object | `record` |

Examples:

```csharp
var numbers = new List<int> { 1, 2, 3 };
var scores = new Dictionary<string, int>
{
    ["Ada"] = 100,
    ["Grace"] = 98
};
var tags = new HashSet<string> { "dotnet", "csharp" };
```

### Arrays Are Fixed-Size

```csharp
int[] numbers = { 1, 2, 3 };
numbers[0] = 42;
// numbers.Add(4); // no Add - arrays are fixed-size
```

If you want Python-list-like resizing behavior, use `List<T>`.

### LINQ Is the Query and Transformation Layer

LINQ is one of the signatures of .NET. It gives you composable query operations like:
- `Where`
- `Select`
- `OrderBy`
- `GroupBy`
- `Any`
- `All`
- `First`
- `Single`
- `Count`

```csharp
var activeNames = users
    .Where(u => u.IsActive)
    .OrderBy(u => u.Name)
    .Select(u => u.Name)
    .ToList();
```

Python comparison:

```python
active_names = [
    user.name
    for user in sorted(users, key=lambda u: u.name)
    if user.is_active
]
```

### Method Syntax vs Query Syntax

LINQ has two syntaxes. Most modern code prefers method syntax, but you should be able to read both.

```csharp
var result = users
    .Where(u => u.IsActive)
    .Select(u => u.Name);
```

```csharp
var result =
    from u in users
    where u.IsActive
    select u.Name;
```

### `IEnumerable<T>` Is Closer to a Generator Pipeline Than a List

This matters a lot.

```csharp
IEnumerable<int> query = numbers.Where(n => n % 2 == 0);
```

That line usually does **not** run the query immediately. It builds a deferred pipeline. Execution happens when you enumerate it:
- `foreach`
- `ToList()`
- `ToArray()`
- `Count()`
- `First()`

This is one of the most common sources of confusion for Python developers. A LINQ pipeline often behaves more like a lazy generator chain than a realized list.

### Materialization Matters

```csharp
var query = users.Where(u => u.IsActive); // deferred
var list = query.ToList();                // materialized now
```

Use `ToList()` or `ToArray()` when:
- you want a snapshot
- you will iterate multiple times
- the source is expensive or stateful

### `First`, `Single`, and Friends

These methods look similar but communicate different intent:
- `First()` -> at least one item must exist
- `FirstOrDefault()` -> first item or default
- `Single()` -> exactly one item must exist
- `SingleOrDefault()` -> zero or one item

`Single()` is much stricter and throws if there is more than one match.

### Projection Is Natural in C#

```csharp
var summaries = users.Select(u => new UserSummary(u.Id, u.Name)).ToList();
```

Projection into anonymous or record types is common and pleasant.

### Beware `IQueryable<T>`

`IQueryable<T>` looks like LINQ but often means "this expression will be translated into something else," usually SQL through Entity Framework Core.

That has consequences:
- not every .NET method can be translated
- what looks like in-memory code may become a database query
- materialization boundaries matter even more

Rule of thumb:
- `IEnumerable<T>` -> in-memory sequence / deferred enumeration
- `IQueryable<T>` -> query provider expression tree, often remote execution

### The Python Comparison That Helps Most

| Concept | Python | C# |
|---|---|---|
| dynamic container | `list` | `List<T>` |
| hash map | `dict` | `Dictionary<TKey, TValue>` |
| lazy pipeline | generators / `itertools` | `IEnumerable<T>` + LINQ |
| list comprehension | list comprehension | `Where` + `Select` |
| runtime type parameter hints | `list[str]` | `List<string>` with compiler enforcement |

---

## 6. Exceptions, `using` & Resource Cleanup

Official docs: [Exceptions and exception handling](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/exceptions/), [`using` statement](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/using), [Dispose pattern](https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose)

This is an area where C# is more familiar to Python developers than Go or Rust are. .NET uses exceptions heavily. The catch is that it also has a strong distinction between:
- garbage collection for memory
- explicit disposal for external resources

### Exceptions Are the Normal Failure Mechanism

```csharp
try
{
    var text = File.ReadAllText("config.json");
}
catch (FileNotFoundException ex)
{
    Console.WriteLine(ex.Message);
}
catch (UnauthorizedAccessException ex)
{
    Console.WriteLine(ex.Message);
}
```

That feels much more like Python than Go's error returns or Rust's `Result`.

### Catch Specific Exceptions, Not Just `Exception`

Python beginners often write:

```python
try:
    ...
except Exception:
    ...
```

In C#, the equivalent broad catch exists, but good code still prefers specific exception handling when possible.

Use broad `catch (Exception)` only when you are:
- logging and rethrowing at a boundary
- converting unknown failures into a safe top-level response
- protecting app-level execution from crashing without context

### Garbage Collection Does Not Mean "No Cleanup Needed"

Python developers sometimes assume "managed language with GC" means resources clean themselves up quickly enough. Not necessarily.

Memory is GC-managed. External resources are different:
- files
- sockets
- HTTP responses
- database connections
- streams

Those often implement `IDisposable`, which means you should dispose them deterministically.

### `using` Is the `with` of C#

```csharp
using var reader = File.OpenText("data.txt");
string content = reader.ReadToEnd();
```

Or with a block:

```csharp
using (var reader = File.OpenText("data.txt"))
{
    string content = reader.ReadToEnd();
}
```

Python comparison:

```python
with open("data.txt") as f:
    content = f.read()
```

The mental model is very close:
- acquire resource
- do work
- guarantee cleanup

### `await using` Exists for Async Disposal

Some resources need asynchronous cleanup.

```csharp
await using var stream = File.OpenRead("data.json");
```

This is the async counterpart to `using`.

### Common Exception Patterns

#### Validate and throw early

```csharp
public static int Divide(int a, int b)
{
    if (b == 0)
    {
        throw new ArgumentException("b cannot be zero.", nameof(b));
    }

    return a / b;
}
```

#### Preserve context when rethrowing

```csharp
catch (JsonException ex)
{
    throw new InvalidOperationException("Config file was invalid JSON.", ex);
}
```

#### Do not lose the stack trace

If you want to rethrow the same exception, use:

```csharp
throw;
```

not:

```csharp
throw ex; // resets the stack trace
```

### The Python Mindset Adjustment

Python developers are used to thinking:
- GC handles memory
- `with` handles resources
- exceptions handle errors

That is actually pretty close to .NET, with one important addition:
- disposal is a first-class part of API design in .NET

If a type implements `IDisposable` or `IAsyncDisposable`, treat that as meaningful and intentional.

---

## 7. Async/Await, `Task` & Cancellation

Official docs: [Asynchronous programming with async and await](https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/), [`Task` class](https://learn.microsoft.com/en-us/dotnet/fundamentals/runtime-libraries/system-threading-tasks-task), [`CancellationToken`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.cancellationtoken?view=net-10.0)

This is one of the areas where Python and C# feel similar on the surface and different in practice.

### `Task` Is the Core Async Abstraction

Think of:
- `Task` as "an async operation that yields no value"
- `Task<T>` as "an async operation that yields a value"

```csharp
async Task<string> FetchTextAsync(HttpClient client, string url, CancellationToken cancellationToken)
{
    using var response = await client.GetAsync(url, cancellationToken);
    response.EnsureSuccessStatusCode();
    return await response.Content.ReadAsStringAsync(cancellationToken);
}
```

Python comparison:

```python
async def fetch_text(session, url: str) -> str:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()
```

### `async`/`await` Feels Familiar, but the Runtime Model Is Different

The syntax similarity can trick Python developers into assuming the whole ecosystem behaves like `asyncio`. It does not.

Important differences:
- `Task` does not automatically imply a dedicated OS thread
- async is primarily about **non-blocking I/O**, not background CPU work
- the runtime and libraries integrate deeply with the thread pool and synchronization primitives

### `Task.WhenAll` Is Your `asyncio.gather`

```csharp
var pages = await Task.WhenAll(
    urls.Select(url => FetchTextAsync(client, url, cancellationToken)));
```

This is one of the most common and useful async patterns in .NET.

### `Task.WhenAny` Exists Too

```csharp
Task<string> a = FetchTextAsync(client, urlA, cancellationToken);
Task<string> b = FetchTextAsync(client, urlB, cancellationToken);

Task<string> winner = await Task.WhenAny(a, b);
string firstResult = await winner;
```

### Async All the Way Down

This rule is just as real in .NET as it is in Python. If you start mixing async code with synchronous blocking carelessly, you will create pain.

Avoid:
- `.Result`
- `.Wait()`
- blocking threads while waiting for async work

Prefer:
- `await`
- async method chains
- async-aware APIs end to end

### Cancellation Is Explicit and Important

Python developers are often used to task cancellation being more runtime-driven. In .NET, cancellation is usually cooperative through `CancellationToken`.

```csharp
async Task WorkAsync(CancellationToken cancellationToken)
{
    while (!cancellationToken.IsCancellationRequested)
    {
        await Task.Delay(500, cancellationToken);
        Console.WriteLine("working...");
    }
}
```

If an API accepts a `CancellationToken`, pass one when you have it. This is especially important in:
- ASP.NET Core request handling
- background services
- long-running jobs
- HTTP and database calls

### Async Streams Exist

If you know Python `async for`, C# has a very similar feature:

```csharp
async IAsyncEnumerable<int> CountAsync([System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken = default)
{
    for (int i = 0; i < 3; i++)
    {
        await Task.Delay(100, cancellationToken);
        yield return i;
    }
}

await foreach (var item in CountAsync(cancellationToken))
{
    Console.WriteLine(item);
}
```

### What Async Is Not

Do not use `async` because:
- it looks modern
- you want CPU-bound work to become magically parallel
- you want to "just run stuff in the background"

Use async when:
- the underlying work is I/O-bound
- the API is naturally asynchronous
- you want scalable request concurrency without blocking threads

### Python Comparison

| Python | C# |
|---|---|
| `async def` | `async Task` / `async Task<T>` |
| `await` | `await` |
| `asyncio.gather` | `Task.WhenAll` |
| task cancellation | cancellation through runtime/task APIs | usually cooperative via `CancellationToken` |
| `async for` | `await foreach` over `IAsyncEnumerable<T>` |

---

## 8. Concurrency & Parallelism

Official docs: [Task Parallel Library](https://learn.microsoft.com/en-us/dotnet/standard/parallel-programming/task-parallel-library-tpl), [Data parallelism](https://learn.microsoft.com/en-us/dotnet/standard/parallel-programming/data-parallelism-task-parallel-library), [Thread-safe collections](https://learn.microsoft.com/en-us/dotnet/standard/collections/thread-safe/)

Python developers often mix together three different ideas:
- async concurrency
- multithreading
- parallel CPU execution

Modern .NET makes clearer distinctions.

### Async Is Not the Same as Parallelism

Use async when you are mostly waiting on I/O.  
Use parallelism when you want multiple cores doing CPU work.

That distinction is much more meaningful in .NET than it often feels in Python, because the GIL changes Python's threading tradeoffs.

### `Task.Run` Is the Escape Hatch, Not the Default Architecture

```csharp
var result = await Task.Run(() => ExpensiveCpuBoundWork());
```

This is fine when you explicitly want to offload CPU-bound work. It is **not** how you design normal ASP.NET Core request handlers or service architecture.

### `Parallel.ForEachAsync` Is Great for Independent Work

```csharp
await Parallel.ForEachAsync(urls, cancellationToken, async (url, ct) =>
{
    string body = await FetchTextAsync(client, url, ct);
    Console.WriteLine($"{url}: {body.Length}");
});
```

This is often much cleaner than manually wiring up a pile of tasks.

### `lock` Is the Basic Shared-State Primitive

```csharp
private readonly object _gate = new();
private int _count;

public void Increment()
{
    lock (_gate)
    {
        _count++;
    }
}
```

Python comparison:

```python
lock = threading.Lock()

with lock:
    count += 1
```

### `SemaphoreSlim` Is Useful for Concurrency Limits

```csharp
var gate = new SemaphoreSlim(5);

await gate.WaitAsync(cancellationToken);
try
{
    await DoWorkAsync(cancellationToken);
}
finally
{
    gate.Release();
}
```

This is a good tool for:
- limiting outbound HTTP concurrency
- protecting scarce resources
- implementing backpressure

### Concurrent Collections Exist

For shared concurrent state, .NET has built-in structures like:
- `ConcurrentDictionary<TKey, TValue>`
- `ConcurrentQueue<T>`
- `ConcurrentBag<T>`

Use them when you truly need shared concurrent mutation. Otherwise, simpler patterns like immutable snapshots or message passing are often easier to reason about.

### The Python Comparison That Matters

| Scenario | Python instinct | Better .NET question |
|---|---|---|
| I/O-bound concurrency | `asyncio` | async/await + `Task` |
| CPU-bound work | `multiprocessing` because of GIL | TPL / threads / parallel loops are often enough |
| simple locking | `threading.Lock` | `lock` / `SemaphoreSlim` |

### The Design Advice

Prefer this order of thinking:
1. Can I keep this single-threaded and simple?
2. If I need concurrency, is it I/O-bound? Use async.
3. If I need parallel CPU work, use parallel constructs.
4. If I need shared mutable state, use the smallest synchronization primitive possible.

That order will keep your code much cleaner.

---

## 9. Dependency Injection, Configuration, Logging & the Generic Host

Official docs: [.NET dependency injection](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/overview), [.NET Generic Host](https://learn.microsoft.com/en-us/dotnet/core/extensions/generic-host), [Configuration in .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/configuration), [Logging in .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/logging)

This is one of the biggest ecosystem differences from Python. In Python, these concerns are often library-by-library choices. In modern .NET, they are part of the platform's default application model.

### The Generic Host Is the App Shell

The Generic Host is the standard way to wire up:
- dependency injection
- configuration
- logging
- application lifetime
- hosted/background services

That makes .NET apps feel more "pre-integrated" than Python apps.

### Minimal Host Setup

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

HostApplicationBuilder builder = Host.CreateApplicationBuilder(args);

builder.Services.AddSingleton<IClock, SystemClock>();
builder.Services.AddHostedService<Worker>();

using IHost host = builder.Build();
await host.RunAsync();
```

This is not just for worker services. The same broad model shows up across:
- console apps
- background services
- ASP.NET Core apps

### Dependency Injection Is Built In

```csharp
public interface IClock
{
    DateTimeOffset UtcNow { get; }
}

public sealed class SystemClock : IClock
{
    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
}

public sealed class Greeter(IClock clock)
{
    public string Greet() => $"UTC now is {clock.UtcNow:O}";
}
```

Registration:

```csharp
builder.Services.AddSingleton<IClock, SystemClock>();
builder.Services.AddTransient<Greeter>();
```

Python developers often start by manually instantiating everything. That works in tiny apps, but idiomatic .NET expects you to lean into the container for app composition.

### Service Lifetimes Matter

| Lifetime | Meaning | Typical use |
|---|---|---|
| `Singleton` | one instance for the app lifetime | stateless services, caches, shared clients |
| `Scoped` | one instance per scope, commonly per web request | request-oriented services, EF Core `DbContext` |
| `Transient` | new instance each resolution | lightweight, stateless helpers |

Getting these wrong can cause subtle bugs, especially in ASP.NET Core.

### Constructor Injection Is the Default

```csharp
public sealed class UserService(ILogger<UserService> logger, IClock clock)
{
    public void PrintTime()
    {
        logger.LogInformation("UTC now is {UtcNow}", clock.UtcNow);
    }
}
```

You will see this style everywhere. Once you accept it, .NET code becomes much more readable.

### Configuration Is Layered

Configuration sources often include:
- `appsettings.json`
- `appsettings.Development.json`
- environment variables
- command-line args
- secret stores in real environments

Sample `appsettings.json`:

```json
{
  "Greeting": {
    "Prefix": "Hello"
  }
}
```

Options class:

```csharp
public sealed class GreetingOptions
{
    public string Prefix { get; set; } = "Hello";
}
```

Registration:

```csharp
builder.Services.Configure<GreetingOptions>(
    builder.Configuration.GetSection("Greeting"));
```

This is a stronger, more structured alternative to sprinkling `os.environ` and ad hoc config dictionaries around the codebase.

### Logging Is Structured by Default

```csharp
logger.LogInformation("Processed user {UserId} in {DurationMs}ms", userId, durationMs);
```

This is better than string interpolation for logs because the placeholders are structured fields, not just text.

Bad:

```csharp
logger.LogInformation($"Processed user {userId} in {durationMs}ms");
```

Good:

```csharp
logger.LogInformation("Processed user {UserId} in {DurationMs}ms", userId, durationMs);
```

### Why Python Developers Sometimes Resist This at First

It can feel like ceremony:
- interfaces
- DI registration
- host builder
- options classes

But the upside is huge in medium and large codebases:
- testability
- consistency
- discoverability
- refactorability

Once you stop fighting the host/container model, modern .NET starts feeling very well engineered.

---

## 10. Projects, `csproj`, NuGet & CLI Workflow

Official docs: [.NET CLI overview](https://learn.microsoft.com/en-us/dotnet/core/tools/), [.NET project SDKs](https://learn.microsoft.com/en-us/dotnet/core/project-sdk/overview), [`global.json` overview](https://learn.microsoft.com/en-us/dotnet/core/tools/global-json), [NuGet docs](https://learn.microsoft.com/en-us/nuget/)

The CLI and project system are one of modern .NET's best qualities. If you like clean command-line workflows, this part is very satisfying.

### SDK-Style Projects Are the Default

A modern console app project file looks like this:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

This is much smaller and saner than older Microsoft project files.

### Common SDKs

| SDK | Use |
|---|---|
| `Microsoft.NET.Sdk` | console apps, libraries |
| `Microsoft.NET.Sdk.Web` | ASP.NET Core apps |
| `Microsoft.NET.Sdk.Worker` | background workers / hosted services |

### Core CLI Commands

```bash
dotnet new console -n HelloDotnet
dotnet build
dotnet run
dotnet test
dotnet publish -c Release
dotnet add package Microsoft.Extensions.Hosting
dotnet add reference ../MyLib/MyLib.csproj
```

These commands are the daily workflow. You do not need an IDE to be productive.

### Solutions Are Common, but Not Mandatory

```bash
dotnet new sln -n MyApp
dotnet sln add src/MyApp/MyApp.csproj
dotnet sln add tests/MyApp.Tests/MyApp.Tests.csproj
```

Think of a solution as:
- a workspace-level grouping
- especially useful for multi-project repos
- not the same thing as the project itself

### A Typical Repo Shape

```text
MyApp.sln
global.json
src/
  MyApp/
    MyApp.csproj
tests/
  MyApp.Tests/
    MyApp.Tests.csproj
```

### NuGet Is the Package Ecosystem

Python:
- `pip install requests`
- `requirements.txt`

.NET:
- `dotnet add package Some.Package`
- `PackageReference` entries in `csproj`

Example:

```xml
<ItemGroup>
  <PackageReference Include="Microsoft.Extensions.Hosting" Version="10.0.0" />
</ItemGroup>
```

Version numbers live in the project file unless you use centralized package management in larger repos.

### `global.json` Pins the SDK

If you want reproducible team builds, pin the SDK version:

```json
{
  "sdk": {
    "version": "10.0.102"
  }
}
```

This is not exactly the same as Python virtual environments, but it serves a related purpose: keeping toolchain expectations aligned.

### Publishing Is First-Class

`.NET` has strong built-in publishing support for:
- self-contained deployments
- framework-dependent deployments
- trimming
- NativeAOT in suitable scenarios
- container-friendly output

That is a much tighter story than many Python packaging/deployment setups.

### The Important Python Comparison

| Python | .NET |
|---|---|
| `pip install` | `dotnet add package` |
| `requirements.txt` / `pyproject.toml` | `csproj` |
| `python -m pytest` | `dotnet test` |
| `python app.py` | `dotnet run` |
| version pinning with toolchain managers | `global.json` |

---

## 11. ASP.NET Core for Python Web Developers

Official docs: [ASP.NET Core fundamentals](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/), [Minimal APIs](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis), [Background tasks with hosted services](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/host/hosted-services?view=aspnetcore-10.0)

If you come from Flask or FastAPI, ASP.NET Core is the part of .NET that will matter most for web development. It is modern, fast, cross-platform, and deeply integrated with the host/DI/config/logging model you saw above.

### The Smallest Useful Mental Model

An ASP.NET Core app usually has:
- a host
- a DI container
- configuration
- logging
- middleware
- endpoints

### Minimal API Example

```csharp
var builder = WebApplication.CreateBuilder(args);

var todos = new List<Todo>
{
    new(1, "Learn C#", false),
    new(2, "Build an API", true)
};

var app = builder.Build();

app.MapGet("/todos", () => todos);

app.MapGet("/todos/{id:int}", (int id) =>
{
    var todo = todos.FirstOrDefault(t => t.Id == id);
    return todo is null ? Results.NotFound() : Results.Ok(todo);
});

app.MapPost("/todos", (CreateTodo request) =>
{
    var todo = new Todo(todos.Count + 1, request.Title, false);
    todos.Add(todo);
    return Results.Created($"/todos/{todo.Id}", todo);
});

app.Run();

public record Todo(int Id, string Title, bool IsDone);
public record CreateTodo(string Title);
```

That should feel pleasantly straightforward.

### FastAPI / Flask Comparison

| Python | ASP.NET Core |
|---|---|
| route decorators | `MapGet`, `MapPost`, controllers, endpoint mapping |
| dependency injection via framework helpers | DI built into the platform |
| request handler function | endpoint delegate / controller action |
| middleware | middleware |
| Pydantic-style DTOs | request/response records/classes |

### Middleware Is the Request Pipeline

This is a core ASP.NET Core concept. Each middleware can:
- inspect the request
- do work before the next component
- call the next component
- do work after the next component
- short-circuit the request

This is conceptually similar to Python web middleware stacks, but ASP.NET Core makes it very central and explicit.

### Dependency Injection Shows Up Everywhere

You can inject services into:
- constructors
- minimal API handlers
- controllers
- hosted services

That is much more standardized than in Python frameworks.

### Serialization Is Built In

JSON serialization defaults to `System.Text.Json`, so returning objects from endpoints is easy and first-party.

### Background Work: Do It the .NET Way

A major Python-to-.NET mistake is starting fire-and-forget work from a request and assuming that is a robust background-job strategy.

For long-running background work, prefer:
- hosted services
- queues
- dedicated workers
- external job systems where appropriate

Do **not** casually sprinkle `Task.Run()` inside request handlers and call it architecture.

### Hosted Services Are the Built-In Background Story

ASP.NET Core and the Generic Host support background services through `IHostedService` / `BackgroundService`.

That is the right baseline for:
- timed jobs
- queue consumers
- background pollers
- process-local workers

### Why Python Developers Often End Up Liking ASP.NET Core

ASP.NET Core feels strongly designed:
- less framework magic than you might expect
- excellent performance
- first-party cohesion
- strong typing without burying the web layer in ceremony

If you enjoy FastAPI because it is structured but productive, ASP.NET Core usually lands well.

---

## 12. Serialization, HTTP & Data Access

Official docs: [System.Text.Json overview](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/overview), [HttpClient guidelines](https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient-guidelines), [EF Core overview](https://learn.microsoft.com/en-us/ef/core/)

This is the section where day-to-day app work becomes more concrete.

### JSON: `System.Text.Json` Is the Default

```csharp
using System.Text.Json;

var user = new UserDto("Ada", "ada@example.com");
string json = JsonSerializer.Serialize(user);
UserDto? roundTrip = JsonSerializer.Deserialize<UserDto>(json);
```

You do not need a third-party JSON library for normal work. The first-party serializer is the standard default in modern .NET.

### `HttpClient` Is the Standard HTTP Client

```csharp
using var client = new HttpClient();
string body = await client.GetStringAsync("https://example.com");
```

But in real applications, especially ASP.NET Core, you often want `IHttpClientFactory` rather than sprinkling raw `new HttpClient()` everywhere.

Why?
- handler lifetime management
- configuration
- resilience patterns
- better testability

### DTOs Are Usually Classes or Records

For API payloads and JSON models, records are often great:

```csharp
public record WeatherResponse(string City, decimal TemperatureC);
```

### EF Core Is the Default ORM Story

If you know SQLAlchemy, EF Core is the closest official equivalent in the .NET world.

Key pieces:
- `DbContext` -> unit-of-work/session-like abstraction
- `DbSet<T>` -> typed collection/query root
- LINQ -> query language
- migrations -> schema evolution

Conceptual comparison:

| Python | .NET |
|---|---|
| SQLAlchemy session | `DbContext` |
| ORM model | entity class |
| query builder / ORM query | LINQ over `DbSet<T>` |
| Alembic | EF Core migrations |

### Remember the `IQueryable<T>` Trap

With EF Core, this matters a lot:

```csharp
var query = db.Users.Where(u => u.IsActive); // not executed yet
var users = await query.ToListAsync(cancellationToken); // executed here
```

That query may become SQL. The expression tree matters. Materialization matters. Client-side vs server-side execution matters.

### Async Database Calls Are Normal

```csharp
var users = await db.Users
    .Where(u => u.IsActive)
    .OrderBy(u => u.Name)
    .ToListAsync(cancellationToken);
```

Use async database APIs in server applications. That is the normal scalable path.

### `DbContext` Lifetime Matters

In web apps, `DbContext` is commonly scoped per request. Do not treat it like a process-wide singleton.

### The Big Picture

The platform story here is very coherent:
- HTTP -> `HttpClient`
- JSON -> `System.Text.Json`
- web APIs -> ASP.NET Core
- data access -> EF Core or lower-level libraries as needed

You can go a long way using mostly first-party components.

---

## 13. Testing, Analyzers & Tooling

Official docs: [Unit testing C# with xUnit](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-csharp-with-xunit), [.NET testing overview](https://learn.microsoft.com/en-us/dotnet/core/testing/), [`dotnet format`](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-format)

This is another place where modern .NET feels mature out of the box.

### `dotnet test` Is the Standard Entry Point

```bash
dotnet test
```

That command builds the solution/project and runs tests. Simple, predictable, first-party.

### xUnit Is a Very Common Default

```csharp
public sealed class Calculator
{
    public int Add(int a, int b) => a + b;
}

public class CalculatorTests
{
    [Theory]
    [InlineData(2, 3, 5)]
    [InlineData(-1, 1, 0)]
    public void Add_ReturnsExpectedSum(int a, int b, int expected)
    {
        var calc = new Calculator();

        int actual = calc.Add(a, b);

        Assert.Equal(expected, actual);
    }
}
```

If you know `pytest.parametrize`, xUnit's `[Theory]` + `[InlineData]` will feel familiar.

### Test Project Setup

Typical commands:

```bash
dotnet new xunit -o MyApp.Tests
dotnet add MyApp.Tests/MyApp.Tests.csproj reference MyApp/MyApp.csproj
dotnet test
```

### AAA Is the Usual Style

Arrange, Act, Assert.

The syntax differs from Python testing, but the core testing habits are the same:
- isolate behavior
- prefer small tests
- make setup obvious
- assert on one concept at a time

### Analyzers Matter

Modern .NET ships with useful analyzers and compiler warnings. Good teams treat them as a real part of code quality, not background noise.

Commonly enforced through:
- nullable warnings
- style analyzers
- code-quality analyzers
- "warnings as errors" in CI for important categories

### Formatting Is Built In

```bash
dotnet format
```

You also usually configure style via:
- `.editorconfig`
- project settings
- analyzer rules

This gives a much more unified tooling story than many Python repos where formatting, linting, and type checking are separate ecosystems with separate conventions.

### Tooling You Will Use Constantly

```bash
dotnet build
dotnet test
dotnet format
dotnet run
dotnet publish
```

That small command set gets you very far.

### Python Comparison

| Python | .NET |
|---|---|
| `pytest` | `dotnet test` + xUnit / NUnit / MSTest |
| `ruff format` / `black` | `dotnet format` |
| `ruff` / `flake8` / `pylint` | compiler warnings + analyzers |
| `mypy` / `pyright` | C# compiler + nullable analysis |

---

## 14. Common Pitfalls for Python Developers

Official docs: [Nullable reference types](https://learn.microsoft.com/en-us/dotnet/csharp/nullable-references), [LINQ overview](https://learn.microsoft.com/en-us/dotnet/standard/linq/), [Asynchronous programming](https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/)

### 1. Assuming `var` Means Dynamic Typing

```csharp
var x = 5;   // x is int
// x = "hello"; // compile error
```

`var` is just local type inference.

### 2. Ignoring Nullable Warnings

If the compiler says a value might be null, treat that as useful information, not busywork. Many teams effectively use nullable warnings as bug detectors.

### 3. Forgetting That `struct` Values Copy

```csharp
Point a = new() { X = 1 };
Point b = a;
b.X = 5;

Console.WriteLine(a.X); // still 1
```

This is a major mental mismatch if you are used to Python object references.

### 4. Thinking LINQ Executes Immediately

```csharp
var query = users.Where(u => u.IsActive); // deferred
```

Nothing may happen until enumeration.

### 5. Calling `.Result` or `.Wait()` on Async Work

This is the .NET equivalent of fighting the async model. Prefer `await`.

### 6. Using `Task.Run()` as a Background Job Architecture

`Task.Run()` is not your job queue, scheduler, or worker system. Use hosted services or a proper external job mechanism when needed.

### 7. Treating `IDisposable` as Optional

If a type is disposable, that usually matters. Use `using` / `await using`.

### 8. Expecting Duck Typing

C# wants explicit contracts. That is usually:
- interfaces
- base types
- generic constraints

### 9. Assuming All Equality Works Like Python Value Equality

Equality depends on the type:
- records have value equality by default
- classes often default to reference equality unless customized
- strings compare by value

Know which model you are in.

### 10. Overusing Mutable Shared State

Because .NET has strong concurrency tools, it is easy to write thread-safe complexity you never needed. Prefer simple ownership and clear data flow first.

### 11. Not Passing `CancellationToken`

In Python you can sometimes get away with less explicit cancellation design. In .NET, `CancellationToken` is a core part of cooperative shutdown and request cancellation.

### 12. Fighting the Platform Defaults

You can build a Python-style hand-rolled app with:
- manual object construction
- ad hoc config
- random logging conventions
- no host

But modern .NET is at its best when you use the platform's integrated defaults.

---

## 15. Quick Reference Cheat Sheet

Official docs: [Introduction to .NET](https://learn.microsoft.com/en-us/dotnet/core/introduction), [C# language reference](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/), [.NET CLI](https://learn.microsoft.com/en-us/dotnet/core/tools/)

This is a translation layer, not a perfect one-to-one mapping. Many of these pairings are "close enough to orient you" rather than "exact same semantics."

| Python | .NET / C# |
|---|---|
| `class Foo:` | `class Foo { }` |
| `@dataclass` | `record` |
| `dict` | `Dictionary<TKey, TValue>` |
| `list` | `List<T>` |
| `set` | `HashSet<T>` |
| `None` | `null` |
| `str | None` | `string?` |
| type hints | real compile-time type system |
| duck typing | interfaces / generic constraints |
| `with open(...) as f:` | `using var f = ...;` |
| `try/except` | `try/catch` |
| `async def` | `async Task` / `async Task<T>` |
| `asyncio.gather(...)` | `Task.WhenAll(...)` |
| `async for` | `await foreach` |
| `threading.Lock` | `lock` / `Monitor` |
| `asyncio.Semaphore` | `SemaphoreSlim` |
| `requests` / `httpx` | `HttpClient` |
| `json` / Pydantic serialization | `System.Text.Json` |
| SQLAlchemy | Entity Framework Core |
| Flask / FastAPI | ASP.NET Core |
| `pip install` | `dotnet add package` |
| `pytest` | `dotnet test` |
| `black` / `ruff format` | `dotnet format` |
| `venv` + toolchain pinning | SDK install + `global.json` |
| `python script.py` | `dotnet run` |

---

## 16. Essential First-Party Libraries & Tools

Official docs: [Introduction to .NET](https://learn.microsoft.com/en-us/dotnet/core/introduction), [System.Text.Json overview](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/overview), [.NET Generic Host](https://learn.microsoft.com/en-us/dotnet/core/extensions/generic-host), [ASP.NET Core fundamentals](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/)

These are the things you will see so often that they function like default infrastructure across much of the ecosystem.

| Library / Tool | Purpose | Python Equivalent |
|---|---|---|
| `dotnet` CLI | create, build, test, run, publish apps | `python`, `pip`, `pytest`, packaging commands spread across tools |
| `System.Collections.Generic` | core generic collections | built-in containers |
| LINQ | querying and transforming sequences | comprehensions + `itertools` + helper funcs |
| `System.Text.Json` | JSON serialization/deserialization | `json`, Pydantic serialization |
| `HttpClient` | HTTP client | `requests`, `httpx`, `aiohttp` |
| `Microsoft.Extensions.Logging` | structured logging | `logging`, `structlog` |
| `Microsoft.Extensions.Configuration` | layered app config | `os.environ` + config libs |
| built-in DI container | service registration and resolution | framework-specific DI helpers |
| Generic Host | app lifetime, DI, config, logging, background services | no direct default equivalent |
| ASP.NET Core | web framework | Flask / FastAPI / Django |
| `BackgroundService` / `IHostedService` | background workers | ad hoc workers, Celery-like local loops, custom async tasks |
| EF Core | ORM / data access platform | SQLAlchemy |
| `dotnet test` | test runner entry point | `pytest` |
| `dotnet format` | formatter | `black`, `ruff format` |

### Suggested Learning Order

If you want the shortest path from Python to productive .NET:

1. Learn modern C# syntax and nullability.
2. Learn classes, records, interfaces, and generics.
3. Learn collections plus LINQ.
4. Learn async/await plus `Task` and cancellation.
5. Learn the host + DI + configuration + logging model.
6. Learn ASP.NET Core if you care about web apps.
7. Learn EF Core if you need relational data access.

### Final Advice

The biggest mistake Python developers make in .NET is trying to force Python ergonomics onto a platform that is optimized around different strengths.

The biggest opportunity is the same thing:
- let the compiler help you
- lean into the platform defaults
- use records, LINQ, async/await, DI, and the host model as intended

Once that mental shift happens, modern .NET feels less like "Microsoft Java" and more like a very cohesive, productive, cross-platform application platform with unusually strong tooling.

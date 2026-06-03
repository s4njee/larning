# Advanced Python Study Guide

A depth-first guide to the parts of Python that sit below everyday application code — the runtime, the object model, the type system, the packaging machinery, and the performance levers — for engineers who already write Python professionally and want to write it *well*. It assumes fluency with the language basics (classes, iterators, decorators, context managers, comprehensions, `*args`/`**kwargs`) and comfort with a debugger. It does **not** assume you've read CPython source, understood the GIL, or profiled a hot loop.

The throughline is **performance with understanding**: not "use this magic trick," but "here's how CPython actually works, and here's why this approach is fast." Every optimization in the guide is motivated by a model of what the interpreter is doing, so you can reason about new situations instead of cargo-culting benchmarks. The closing recipe chapter is the payoff — worked, profiled, production-grade patterns for making Python fast without rewriting it in another language.

This guide has two siblings that go deeper on concurrency specifically: the [Python Concurrency guide](PYTHON_CONCURRENCY.md) (which model to pick: threads, processes, or async) and the [Asyncio & aiohttp guide](ASYNCIO_STUDY_GUIDE.md) (the event loop, aiohttp, and async performance). This guide covers the *language and runtime* layer underneath both of them.

Primary references: the [CPython source](https://github.com/python/cpython) (the final authority), the [Python Language Reference](https://docs.python.org/3/reference/), the [Data Model](https://docs.python.org/3/reference/datamodel.html) chapter (the most important page in the docs), Brett Cannon's [blog](https://snarky.ca/) on Python internals, and the [`dis`](https://docs.python.org/3/library/dis.html) module for seeing what the interpreter actually executes.

---

## Table of Contents

1. [Part 1 — The CPython Runtime Model](#part-1--the-cpython-runtime-model)
2. [Part 2 — The Object Model & Data Model](#part-2--the-object-model--data-model)
3. [Part 3 — Descriptors, Properties & Slots](#part-3--descriptors-properties--slots)
4. [Part 4 — Metaclasses & Class Machinery](#part-4--metaclasses--class-machinery)
5. [Part 5 — Iterators, Generators & Lazy Evaluation](#part-5--iterators-generators--lazy-evaluation)
6. [Part 6 — The Type System](#part-6--the-type-system)
7. [Part 7 — Modern Packaging & Tooling](#part-7--modern-packaging--tooling)
8. [Part 8 — Profiling & Measurement](#part-8--profiling--measurement)
9. [Part 9 — Performance Levers](#part-9--performance-levers)
10. [Part 10 — High-Performance Recipes](#part-10--high-performance-recipes)

---

## Part 1 — The CPython Runtime Model

Before any optimization, get the model right. Almost every "Python is slow" complaint — and almost every "I tried to speed it up and it got worse" story — traces back to a misunderstanding of what CPython actually does when it runs your code. This part is the floor everything else stands on.

### CPython Is the Language

"Python" is a language spec; **CPython** is its dominant implementation — the one from python.org, the one in your distro, the one running your production services. When this guide says "Python does X," it means "CPython does X." Alternative implementations (PyPy, GraalPy, Cython, Mypyc) exist and matter (Part 9), but you must understand CPython first because it's what you're almost certainly running.

### Everything Is an Object, Everything Is Heap-Allocated

In CPython, **every value** — an integer, a string, a function, a class, `None`, the number `42` — is a C struct (`PyObject`) living on the heap. A Python variable is a **pointer** (a reference) to one of these structs, not the value itself. When you write `x = 42`, the integer `42` is a heap object and `x` is a pointer to it. When you write `x = y`, you copy the *pointer*, not the integer.

This is why:

- **Assignment is cheap** — it's a pointer copy, regardless of the object's size.
- **`is` vs `==`** makes sense — `is` compares pointer identity (same object), `==` compares value (calls `__eq__`).
- **Everything has overhead** — even a bare `int` in CPython carries ~28 bytes of per-object overhead (refcount, type pointer, the actual value). A Python `list` of a million ints is a million heap-allocated `PyObject`s plus a million-pointer array — *not* a contiguous array of machine integers. This overhead is exactly what NumPy and `array.array` exist to eliminate (Part 9).

### Reference Counting + Generational GC

CPython uses **reference counting** as its primary memory-management strategy: every `PyObject` has a `ob_refcnt` field. When you bind a name, pass an argument, or append to a list, the refcount increments. When a name goes out of scope or is rebound, it decrements. When it hits zero, the object is freed **immediately** — no waiting for a garbage-collection pause.

Reference counting is *deterministic*: you know exactly when objects die. That's why `with open(...)` and context managers aren't strictly necessary for file handles in CPython (the refcount drops to zero at the end of the block and the file closes instantly) — but they *are* necessary for portability, because other implementations (PyPy) don't refcount and may delay finalization arbitrarily. **Always use context managers for resources.** They're correct everywhere.

Refcounting can't handle **cycles** (A references B, B references A, both unreachable). For those, CPython runs a **generational garbage collector** (`gc` module) that periodically walks objects to find unreachable cycles. You almost never need to think about it, but two things are worth knowing: (1) the cycle GC only runs periodically, so cyclic garbage lingers briefly; (2) you can `gc.disable()` it during latency-sensitive windows and call `gc.collect()` manually afterward — a niche but real optimization for request-serving code that creates temporary cyclic structures.

### The GIL — What It Does and Doesn't Do

The **Global Interpreter Lock** is a mutex that ensures **only one thread executes Python bytecode at a time** within a single process. It exists because CPython's reference counting (above) is not thread-safe — without the GIL, two threads incrementing and decrementing refcounts concurrently would corrupt memory.

What the GIL **means for you**:

- **CPU-bound multithreading does not parallelize.** Ten threads doing math contend on the GIL and run *sequentially* — or worse, with the overhead of context-switching. For CPU parallelism, use **`multiprocessing`** or **`ProcessPoolExecutor`**, which spawn separate processes each with their own GIL (see the [Python Concurrency guide](PYTHON_CONCURRENCY.md)).
- **I/O-bound multithreading works fine.** The GIL is released during blocking I/O (network, disk, `time.sleep`), so threads waiting on I/O overlap genuinely. For I/O concurrency, threading works — and `asyncio` is often better (see the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md)).
- **C extensions can release the GIL.** NumPy, pandas, scikit-learn, and other C-backed libraries release the GIL during their heavy computations, so multithreaded code that calls them *does* parallelize on the C side. This is why "use NumPy" is a real performance answer (Part 9).

**The free-threaded build (PEP 703, Python 3.13+).** CPython now ships an *experimental* build without the GIL (`python3.13t`), enabling true thread-level parallelism for CPU-bound Python. It uses per-object locks, biased reference counting, and deferred refcounting instead of the GIL. As of 2026 it's maturing rapidly — more C extensions support it each release — but it's still opt-in and carries a ~5–10% single-threaded overhead on the non-free-threaded path. Know it exists, watch its progress, and test your workload before betting on it.

### Bytecode and the Evaluation Loop

When you `import` a module, CPython compiles it to **bytecode** — a sequence of low-level instructions for the **CPython virtual machine** (the "evaluation loop," `ceval.c`). Bytecode lives in `.pyc` files (the `__pycache__` directory) and is cached across runs. You can inspect it:

```python
import dis

def add(a, b):
    return a + b

dis.dis(add)
#   0 RESUME            0
#   2 LOAD_FAST         0 (a)
#   4 LOAD_FAST         1 (b)
#   6 BINARY_OP         0 (+)
#  10 RETURN_VALUE
```

Each bytecode instruction is dispatched through the eval loop — a giant C `switch` statement. This is the interpreter overhead: each `LOAD_FAST`, `BINARY_OP`, and `RETURN_VALUE` is a C-level dispatch, a pointer dereference, and (for `BINARY_OP`) a dynamic type lookup and method call. A tight loop in Python executing millions of these dispatches per second is spending most of its time in interpreter machinery, not in the actual addition — which is why moving hot loops into C, NumPy, or a JIT (Part 9) gives 10–100× speedups.

**The specializing adaptive interpreter (3.11+).** Since Python 3.11, CPython includes a *specializing interpreter* that watches bytecode as it runs and, when it sees a pattern repeat (e.g., `BINARY_OP` always gets two `int`s), **replaces the generic instruction with a specialized fast path** (`BINARY_OP_ADD_INT`) that skips the type-lookup overhead. This is a *runtime* JIT-like optimization, transparent to you, and is a big reason Python 3.11–3.13 are significantly faster than 3.10 on the same code. The practical takeaway: **upgrade to the latest CPython** before reaching for exotic optimizations — you may get a 10–40% speedup for free.

**The JIT compiler (3.13+).** CPython 3.13 introduced an experimental **copy-and-patch JIT** that compiles specialized bytecode into native machine code. It's off by default (build with `--enable-experimental-jit`), yields modest speedups on microbenchmarks, and is an investment in future performance. By 3.14+ it's becoming more impactful. Like the free-threaded build, know it's coming — it changes the "Python can't be fast" calculus over the next few years.

### Small-Integer and String Interning

A performance detail that explains otherwise-baffling `is` behavior and that matters for hashing. CPython **interns** (caches and reuses) small integers in the range `[-5, 256]` — they're singletons, pre-allocated at startup. So `a = 256; b = 256; a is b` is `True`, but `a = 257; b = 257; a is b` is `False` (two separate heap objects). **Never use `is` to compare values; use `==`.** `is` is for identity checks against singletons (`None`, `True`, `False`) and nothing else.

Similarly, string literals that look like identifiers are **interned** automatically, and you can force it with `sys.intern()`. Interned strings compare by pointer (`is`), which is O(1) instead of O(n) — this is how `dict` lookups and attribute access are fast: they compare interned key strings by pointer first, falling back to `==` only on collision.

If you remember one thing from Part 1: **CPython is a reference-counted, bytecode-interpreted runtime where every value is a heap object, the GIL serializes CPU-bound threads, and the interpreter's dispatch overhead is *the* bottleneck for tight loops.** Every performance lever in this guide — NumPy, C extensions, `__slots__`, generators, the JIT — is a strategy for reducing either the object overhead or the dispatch overhead, or both.

---

## Part 2 — The Object Model & Data Model

Part 1 said everything is a `PyObject`. This part is about **how Python decides what operations mean** — addition, attribute access, iteration, hashing, truthiness, calling — all of it. The system is called the **data model** (sometimes "dunder methods" or "the magic method protocol"), and it's the single most important page in the Python docs. Understanding it lets you make your own objects behave like built-ins, explains why built-in operations are fast, and is the foundation of descriptors (Part 3), metaclasses (Part 4), and the type system (Part 6).

### The Protocol Pattern

Python doesn't use interfaces or abstract base classes to define behavior (though `abc` exists). It uses **protocols**: if an object has a `__len__` method, it supports `len()`; if it has `__iter__` and `__next__`, it's iterable; if it has `__getitem__`, it's subscriptable. The interpreter checks for the presence of the method at call time. This is *duck typing made precise*.

The data model is the catalog of these protocols. Here are the ones that matter most, grouped by what they let you do:

### Representation and Identity

| Method | Triggered by | Notes |
|---|---|---|
| `__repr__(self)` | `repr(obj)`, the REPL, debuggers | unambiguous, ideally `eval()`-able |
| `__str__(self)` | `str(obj)`, `print()`, f-strings | human-friendly; falls back to `__repr__` |
| `__hash__(self)` | `hash()`, `dict` keys, `set` membership | must be consistent with `__eq__`: `a == b` ⟹ `hash(a) == hash(b)` |
| `__eq__(self, other)` | `==` | defining `__eq__` makes the object unhashable by default unless you also define `__hash__` |
| `__bool__(self)` | `if obj:`, `bool()` | falls back to `__len__` (truthy if non-empty) |

The `__hash__`/`__eq__` contract is load-bearing: violate it (two equal objects with different hashes) and `dict` and `set` silently break — lookups miss, duplicates appear. **If your object is mutable, don't make it hashable.** This is why `list` and `dict` aren't hashable but `tuple` and `frozenset` are.

### Attribute Access

| Method | Triggered by | Notes |
|---|---|---|
| `__getattr__(self, name)` | attribute lookup, **only when normal lookup fails** | the "fallback" hook |
| `__getattribute__(self, name)` | **every** attribute access | the "total intercept" — rare, tricky |
| `__setattr__(self, name, value)` | `obj.attr = val` | |
| `__delattr__(self, name)` | `del obj.attr` | |
| `__dir__(self)` | `dir(obj)` | |

The resolution order for `obj.attr` in Python — the full **attribute lookup chain** — is:

1. **Data descriptors** on the *type* (class and its MRO) — e.g. `property`, `__slots__` descriptors. (Part 3.)
2. The instance's `__dict__` (the per-object attribute dictionary).
3. **Non-data descriptors** on the type — e.g. regular methods, `classmethod`, `staticmethod`.
4. `__getattr__` (the fallback hook, if defined).

This order is *why* a `property` (a data descriptor) overrides an instance attribute of the same name, and why `__slots__` removes the instance `__dict__` entirely (Part 3). Understanding this chain is what makes descriptor-based metaprogramming predictable instead of magical.

### Container and Sequence Protocols

| Method | Triggered by | Notes |
|---|---|---|
| `__len__(self)` | `len()`, truthiness fallback | |
| `__getitem__(self, key)` | `obj[key]`, also enables iteration if no `__iter__` | |
| `__setitem__` / `__delitem__` | `obj[key] = val` / `del obj[key]` | |
| `__contains__(self, item)` | `in` operator | falls back to `__iter__` |
| `__iter__(self)` | `for x in obj`, `iter()` | returns an iterator (Part 5) |
| `__reversed__(self)` | `reversed()` | |
| `__missing__(self, key)` | `dict` subclass — called when key is absent | the hook `defaultdict` uses |

A class with `__getitem__` is subscriptable *and* iterable (Python will call `__getitem__(0)`, `__getitem__(1)`, … until `IndexError`). Defining `__iter__` is preferred and more explicit.

### Numeric and Comparison Protocols

| Method | Triggered by | Notes |
|---|---|---|
| `__add__` / `__radd__` / `__iadd__` | `+` / reflected / `+=` | the `r` variants are tried when the *left* operand doesn't know how |
| `__mul__`, `__sub__`, `__truediv__`, `__floordiv__`, `__mod__`, `__pow__` | the obvious operators | each has `__r*__` and `__i*__` |
| `__neg__`, `__abs__`, `__invert__` | `-obj`, `abs()`, `~obj` | |
| `__lt__`, `__le__`, `__gt__`, `__ge__` | `<`, `<=`, `>`, `>=` | `@functools.total_ordering` derives all four from `__eq__` + one |
| `__int__`, `__float__`, `__index__` | `int()`, `float()`, slicing/`bin()`/`hex()` | `__index__` is specifically for integer-like types used in slicing |

The **reflected** (`__radd__`) mechanism: `a + b` first tries `a.__add__(b)`. If that returns `NotImplemented`, Python tries `b.__radd__(a)`. This is how `1 + MyVector()` works even though `int` doesn't know about your type — your `__radd__` gets the call.

### The Callable Protocol

| Method | Triggered by |
|---|---|
| `__call__(self, ...)` | `obj()` — calling the object like a function |

Any object with `__call__` is callable. This is how functors, stateful callbacks, and decorator classes work. It's also how *classes themselves* are callable — `MyClass()` calls `type.__call__`, which calls `MyClass.__new__` then `MyClass.__init__` (Part 4).

### Context Managers

| Method | Triggered by |
|---|---|
| `__enter__(self)` | `with obj as x:` — returns `x` |
| `__exit__(self, exc_type, exc_val, exc_tb)` | exiting the `with` block (even on exception) |

The beauty is that `__exit__` is called **regardless** of how the block exits — normal completion, exception, or `return`. Return `True` from `__exit__` to suppress the exception. `contextlib.contextmanager` lets you write the same thing as a generator (Part 5).

### `__init_subclass__` and `__class_getitem__` — Modern Hooks

Two newer hooks that often replace metaclasses (Part 4) for simpler use cases:

- **`__init_subclass__(cls, **kwargs)`** (3.6+): called on the *parent* class whenever a *child* is defined. Use it for registration, validation, or injecting behavior into subclasses without a metaclass.
- **`__class_getitem__(cls, item)`** (3.7+): makes a class subscriptable as a type (`MyClass[int]`). This is how `list[int]`, `dict[str, Any]` work at runtime — `__class_getitem__` returns a `GenericAlias`.

```python
class Plugin:
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, /, name: str, **kwargs):
        super().__init_subclass__(**kwargs)
        Plugin._registry[name] = cls    # auto-register every subclass

class JSONPlugin(Plugin, name="json"):   # registered automatically
    ...
class XMLPlugin(Plugin, name="xml"):
    ...

Plugin._registry  # {"json": JSONPlugin, "xml": XMLPlugin}
```

If you remember one thing from Part 2: **Python dispatches operators, attribute access, iteration, and calling through dunder methods defined in the data model, and the attribute lookup chain (data descriptor → instance dict → non-data descriptor → `__getattr__`) is the resolution order you must know to predict what any attribute access does.**

---

## Part 3 — Descriptors, Properties & Slots

Descriptors are the *implementation mechanism* behind `property`, `classmethod`, `staticmethod`, `__slots__`, and method binding itself. Understanding them is understanding how Python's attribute lookup *actually works* — Part 2's chain, made concrete.

### What a Descriptor Is

A descriptor is any object that defines one or more of:

- `__get__(self, obj, objtype=None)` — called when the descriptor is *read* from an instance or class.
- `__set__(self, obj, value)` — called when the descriptor is *assigned to*.
- `__delete__(self, obj)` — called when the descriptor is `del`eted from.

A descriptor that defines only `__get__` is a **non-data descriptor**; one that defines `__set__` (or `__delete__`) is a **data descriptor**. The distinction matters because of the lookup order from Part 2: **data descriptors win over the instance `__dict__`**, while non-data descriptors lose to it.

### `property` Is a Descriptor

`property` is just a class that implements the descriptor protocol:

```python
class property:
    def __init__(self, fget=None, fset=None, fdel=None, doc=None): ...
    def __get__(self, obj, objtype=None):
        if obj is None: return self     # accessed on the class, return the descriptor itself
        return self.fget(obj)           # accessed on an instance, call the getter
    def __set__(self, obj, value):
        self.fset(obj, value)           # call the setter
```

That's it. `@property` is syntactic sugar for creating a data-descriptor instance on the class. Because it defines `__set__`, it's a data descriptor — which is *why* `obj.x = val` calls the setter even if `obj.__dict__["x"]` exists: data descriptors outrank the instance dict.

### Functions Are Descriptors: How Methods Work

Here's the detail that trips people up until they see it. A regular function defines `__get__`:

```python
class Foo:
    def greet(self):
        return "hello"

# Foo.__dict__["greet"] is the raw function object.
# Foo.greet  →  calls function.__get__(None, Foo)  →  returns the function itself
# Foo().greet  →  calls function.__get__(instance, Foo)  →  returns a "bound method"
#   which, when called, passes the instance as the first argument (self).
```

That's *all* method binding is — the function's `__get__` wrapping itself with the instance. `classmethod` and `staticmethod` are *different* descriptors with different `__get__` implementations: `classmethod.__get__` binds the *class* as the first argument, `staticmethod.__get__` returns the raw function unchanged.

### Building a Reusable Descriptor

The classic use case: validated attributes without repeating `property` boilerplate on every field.

```python
class Positive:
    """A descriptor that enforces positive values."""
    def __set_name__(self, owner, name):
        self.storage_name = f"_{name}"      # e.g. "_width"

    def __get__(self, obj, objtype=None):
        if obj is None: return self
        return getattr(obj, self.storage_name, None)

    def __set__(self, obj, value):
        if value <= 0:
            raise ValueError(f"{self.storage_name[1:]} must be positive, got {value}")
        setattr(obj, self.storage_name, value)

class Rectangle:
    width = Positive()      # descriptor instance on the class
    height = Positive()

    def __init__(self, w, h):
        self.width = w      # goes through Positive.__set__
        self.height = h

r = Rectangle(3, 4)
r.width = -1               # ValueError: width must be positive, got -1
```

`__set_name__` (3.6+) is called automatically when the descriptor is assigned to a class attribute, giving it the name it was assigned to — no need to pass the name manually.

### `__slots__`: Trading Flexibility for Memory and Speed

By default, every instance has a `__dict__` — a hash table that stores its attributes. For a class with three attributes, that's a hash table per instance, which costs ~100+ bytes of overhead per object. For millions of small objects, that's real memory.

`__slots__` replaces the `__dict__` with a fixed-size array of pointers — one per declared attribute, stored directly in the object struct:

```python
class Point:
    __slots__ = ("x", "y")   # no __dict__, just these two

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
p.z = 3   # AttributeError: 'Point' object has no attribute 'z'
```

The effects:

| | `__dict__` (default) | `__slots__` |
|---|---|---|
| **Memory per instance** | ~170 bytes (3 attrs + dict overhead) | ~72 bytes (3 attrs, no dict) |
| **Attribute access speed** | dict lookup (~60 ns) | direct offset lookup (~40 ns) |
| **Can add arbitrary attrs** | yes | **no** — only declared slots |
| **Can weakref** | yes | only if `__weakref__` is in slots |
| **Inheritance** | just works | must declare slots in every subclass or child gets a `__dict__` anyway |

**Use `__slots__` when you create millions of instances of a small data class** and memory or lookup speed matters — sensor readings, graph nodes, ORM row objects. Don't use it casually; the flexibility loss (no arbitrary attributes, inheritance footguns) is real. (And in many of those cases, a `@dataclass(slots=True)` — 3.10+ — is the right tool.) Under the hood, each slot is a **data descriptor** on the class that reads/writes a fixed offset in the instance struct — the same descriptor protocol from above, used by the language itself.

If you remember one thing from Part 3: **descriptors are the mechanism behind `property`, methods, `classmethod`, `staticmethod`, and `__slots__` — they intercept attribute access at the class level, and data descriptors outrank the instance `__dict__` while non-data descriptors yield to it.**

---

## Part 4 — Metaclasses & Class Machinery

A metaclass is **the class of a class**. Just as an object is an instance of a class, a class is an instance of its metaclass. The default metaclass is `type` — `type` *is* the thing that creates classes. Metaclasses let you customize *class creation itself*: validate class definitions, auto-register subclasses, inject methods, enforce interfaces, or transform the class body. They are the most powerful (and most overused) metaprogramming tool in the language.

### How Class Creation Works

When Python encounters a `class` statement:

```python
class Foo(Base, metaclass=Meta):
    x = 1
    def method(self): ...
```

it does, roughly:

1. **Determine the metaclass** — the `metaclass=` keyword, or inherited from the base, or `type` by default.
2. **Prepare the namespace** — call `Meta.__prepare__(name, bases, **kwargs)` to get the dict-like object the class body will execute in. (The default is a plain `dict`; returning an `OrderedDict` was how pre-3.7 code preserved definition order.)
3. **Execute the class body** — run the code in that namespace. After this, the namespace holds `{"x": 1, "method": <function>}`.
4. **Call the metaclass** — `Meta(name, bases, namespace, **kwargs)`, which calls `Meta.__new__` to create the class object and `Meta.__init__` to initialize it.

So `type("Foo", (Base,), {"x": 1})` creates the exact same class as the `class Foo(Base): x = 1` statement. `type` is callable because classes are objects, and creating a class is just calling its metaclass.

### A Practical Metaclass

```python
class ValidatedMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # Enforce: every concrete class must define a 'validate' method
        if bases and "validate" not in namespace:
            raise TypeError(f"{name} must implement validate()")
        return cls

class BaseModel(metaclass=ValidatedMeta):
    def validate(self): ...

class User(BaseModel):
    def validate(self): ...   # fine

class Order(BaseModel):       # TypeError: Order must implement validate()
    pass
```

### When *Not* to Use a Metaclass

Metaclasses are powerful and confusing. In modern Python, you almost always have a simpler alternative:

| You want to… | Use |
|---|---|
| Auto-register subclasses | `__init_subclass__` (Part 2) |
| Validate fields, add `__repr__`/`__eq__`/`__hash__` | `@dataclass` |
| Enforce an interface | `abc.ABC` / `@abstractmethod` |
| Customize attribute access | descriptors (Part 3) |
| Transform the class body | a class decorator |
| All of the above plus control over class *creation* | a metaclass |

The rule of thumb: **reach for the simplest tool that solves the problem.** `__init_subclass__` handles 80% of what people historically used metaclasses for. Metaclasses are for frameworks and ORMs (Django's `Model`, SQLAlchemy's `DeclarativeMeta`), not application code.

### `dataclasses` — The 80% Solution

`@dataclass` (3.7+) auto-generates `__init__`, `__repr__`, `__eq__`, and optionally `__hash__`, `__lt__`, `__slots__`, `__match_args__` (for structural pattern matching) — all from a list of annotated fields:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
    label: str = ""
    tags: list[str] = field(default_factory=list)

p = Point(1.0, 2.0, label="origin")
# repr:  Point(x=1.0, y=2.0, label='origin', tags=[])
# frozen: p.x = 3.0  →  FrozenInstanceError
# slots:  ~40% less memory per instance
# hashable (frozen=True): usable as dict key or set member
```

`frozen=True` makes it immutable (and hashable); `slots=True` (3.10+) adds `__slots__` automatically. For performance-critical data carriers, **`@dataclass(slots=True)`** is the default choice — you get `__slots__` without maintaining them by hand.

For cases where you want even more (validation, serialization, aliasing), **Pydantic v2** and **attrs** are the ecosystem answers — both are descriptor-and-metaclass-based under the hood but present a clean decorator API.

### The MRO and `super()`

Python's **Method Resolution Order** (MRO) is computed by the C3 linearization algorithm: it produces a deterministic, consistent order for looking up methods through the inheritance chain, even with multiple inheritance (diamonds). Call `ClassName.__mro__` to see it.

`super()` follows the MRO, not the direct parent — which is *why* cooperative multiple inheritance works and why `super().__init__()` in a diamond calls each class's `__init__` exactly once, in MRO order. **Always use `super()` instead of hardcoding parent calls** unless you have an explicit reason not to.

If you remember one thing from Part 4: **a class is an instance of its metaclass (default: `type`), and class creation is a callable chain you can hook into — but `__init_subclass__`, `@dataclass`, and class decorators handle most real-world needs without the complexity of a metaclass.**

---

## Part 5 — Iterators, Generators & Lazy Evaluation

Lazy evaluation — producing values only when asked for them, one at a time — is Python's most important performance habit for data that doesn't fit in memory or doesn't need to. Generators are the tool; the iterator protocol is the mechanism; and `itertools` is the standard library of ready-made lazy pipelines. This part is about writing code that processes a 50 GB file in constant memory.

### The Iterator Protocol

An **iterable** is anything with `__iter__()` that returns an **iterator**. An iterator has `__next__()` (returns the next value, raises `StopIteration` when done) and `__iter__()` (returns itself). `for x in obj:` is syntactic sugar for:

```python
_iter = iter(obj)            # calls obj.__iter__()
while True:
    try:
        x = next(_iter)      # calls _iter.__next__()
    except StopIteration:
        break
```

Lists, dicts, files, range objects — all iterables. The distinction matters: a *list* is iterable (you can loop over it), but it holds all items in memory. An *iterator* (or generator) produces items one at a time and discards them.

### Generators: Iterators Without the Boilerplate

A **generator function** uses `yield` instead of `return`. Calling it returns a **generator object** (an iterator) that pauses at each `yield` and resumes on `next()`:

```python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fib = fibonacci()
[next(fib) for _ in range(8)]   # [0, 1, 1, 2, 3, 5, 8, 13]
```

This generates an infinite sequence in **constant memory** — each value is computed and yielded on demand, never stored.

**Generator expressions** are the inline form — a comprehension with `()` instead of `[]`:

```python
total = sum(x * x for x in range(10_000_000))   # no list created; constant memory
# vs.
total = sum([x * x for x in range(10_000_000)])  # builds a 10M-element list first
```

Always prefer generator expressions when you're feeding the result into a single consumer (`sum`, `max`, `min`, `any`, `all`, `"".join`, a `for` loop) — the memory savings are free and significant.

### `yield from` — Delegating and Composing Generators

`yield from iterable` delegates to a sub-iterator, yielding each of its values:

```python
def flatten(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)   # recursive delegation
        else:
            yield item

list(flatten([1, [2, [3, 4]], 5]))   # [1, 2, 3, 4, 5]
```

Without `yield from` you'd write a `for` loop with `yield` — `yield from` is shorter, faster (C-level delegation), and passes `send()`/`throw()`/`close()` through to the sub-generator.

### `itertools` — The Standard Library of Lazy Pipelines

`itertools` is the module for composing lazy operations. Every function returns an iterator, so they chain with zero intermediate lists:

```python
from itertools import islice, chain, groupby, batched, count, takewhile

# Take the first 5 Fibonacci numbers
list(islice(fibonacci(), 5))                    # [0, 1, 1, 2, 3]

# Chain multiple iterables lazily
for x in chain(range(3), "abc", [10, 20]):      # 0, 1, 2, 'a', 'b', 'c', 10, 20
    ...

# Process in batches of 100 (3.12+)
for batch in batched(huge_iterable, 100):
    process_batch(batch)

# Group consecutive items by a key
data = [("a", 1), ("a", 2), ("b", 3)]
for key, group in groupby(data, key=lambda x: x[0]):
    print(key, list(group))                     # a [(a,1),(a,2)]  b [(b,3)]
```

Key combinators: `chain` (concatenate), `islice` (slice an iterator), `takewhile`/`dropwhile` (filter by predicate), `groupby` (consecutive groups — *not* SQL GROUP BY; data must be pre-sorted), `batched` (3.12+, fixed-size chunks), `starmap` (map unpacking tuples), `product`/`permutations`/`combinations` (combinatorics), and `accumulate` (running totals/reductions).

The **more-itertools** third-party package adds hundreds more: `chunked`, `flatten`, `peekable`, `windowed`, `unique_everseen`, `first`, `one`.

### Processing Large Files in Constant Memory

The pattern that makes Python handle data bigger than RAM:

```python
import csv

def parse_large_csv(path):
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)                  # skip header
        for row in reader:            # file iterator: one line at a time, constant memory
            yield transform(row)      # yield transformed row lazily

# Compose a pipeline — nothing runs until consumed
pipeline = (
    row
    for row in parse_large_csv("huge.csv")
    if row["status"] == "active"
)

# Consume in batches
from itertools import batched
for batch in batched(pipeline, 1000):
    db.insert_many(batch)             # only 1000 rows in memory at a time
```

No intermediate list is ever built. Each row flows through the pipeline one at a time. This is the power of lazy evaluation: **the pipeline's memory usage is O(batch_size), not O(file_size).**

If you remember one thing from Part 5: **generators and `itertools` let you process arbitrarily large data in constant memory — prefer generator expressions over list comprehensions when feeding a single consumer, and build lazy pipelines that never materialize the full dataset.**

---

## Part 6 — The Type System

Python's type system is **gradual**: you can add types incrementally to an untyped codebase, and typed and untyped code coexist. Types are checked by external tools (**mypy**, **pyright**, **pytype**) — the runtime ignores them almost entirely (the `typing` module is mostly for the checker's benefit). The practical value is catching bugs before they run, making IDE autocompletion precise, and documenting intent in a way that's machine-verified.

### The Basics, Quickly

```python
# Variable annotations (3.6+)
name: str = "hello"
count: int = 0
items: list[str] = []                  # generic built-in types (3.9+)
mapping: dict[str, list[int]] = {}

# Function signatures
def greet(name: str, loud: bool = False) -> str:
    return name.upper() if loud else name

# None return
def log(msg: str) -> None: ...

# Optional (nullable)
from typing import Optional
def find(key: str) -> Optional[str]:   # same as str | None (3.10+)
    ...

# Union
def process(data: str | bytes) -> None: ...
```

Since Python 3.10+, prefer `X | Y` over `Union[X, Y]` and `X | None` over `Optional[X]` — cleaner, built-in syntax.

### Generics

Make a function or class work with *any* type while preserving the relationship:

```python
from typing import TypeVar
T = TypeVar("T")

def first(items: list[T]) -> T:     # "returns the same type that's in the list"
    return items[0]

# 3.12+ syntax — no separate TypeVar declaration:
def first[T](items: list[T]) -> T:
    return items[0]
```

For classes:

```python
# 3.12+
class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> None:
        self._items.append(item)
    def pop(self) -> T:
        return self._items.pop()

s: Stack[int] = Stack()
s.push(1)       # ok
s.push("x")     # type error
```

### Protocols (Structural Subtyping)

`Protocol` (3.8+) is the typed version of duck typing — a class matches a protocol if it has the right methods, *without* inheriting from it:

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str: ...

class Button:
    def render(self) -> str:
        return "<button>Click</button>"

def display(widget: Renderable) -> None:   # Button matches — it has render() -> str
    print(widget.render())

display(Button())   # ✓ — structural match, no inheritance required
```

This is the idiomatic way to type APIs that accept "anything with method X" — no base class needed, pure structural compatibility. Use `Protocol` over `ABC` when you don't control the implementing classes.

### `TypedDict`, `Literal`, `TypeGuard`, and Other Power Tools

| Type | Use case |
|---|---|
| `TypedDict` | type a dictionary with known string keys and per-key types — common for JSON/API payloads |
| `Literal["a", "b"]` | restrict a value to specific literals |
| `TypeGuard` / `TypeIs` | tell the checker that a function narrows a type (a custom type guard) |
| `@overload` | declare multiple signatures for a function that returns different types based on input types |
| `Never` (3.11+) | a function that never returns (always raises) |
| `Self` (3.11+) | the return type is the current class (for fluent/builder APIs) |
| `ParamSpec` / `Concatenate` | type decorators that preserve the wrapped function's signature |
| `TypeVarTuple` (3.11+) | variadic generics — type-safe `*args` |
| `@dataclass_transform` (3.11+) | tell the checker that your decorator/metaclass creates dataclass-like classes |

### Practical Type-Checking Setup

```bash
# Install and run mypy (the most common checker):
pip install mypy
mypy src/

# Or pyright (faster, Microsoft, the engine behind Pylance in VS Code):
pip install pyright
pyright src/
```

In `pyproject.toml`:

```toml
[tool.mypy]
strict = true                    # maximum checking — enable this for new projects
warn_return_any = true
disallow_untyped_defs = true

[tool.pyright]
typeCheckingMode = "strict"
```

**Start with `strict` on new code** and relax selectively with `# type: ignore[code]` or `cast()`. For legacy codebases, add types incrementally — the gradual system is designed for this.

If you remember one thing from Part 6: **Python's type system is gradual and checked by external tools (mypy/pyright), not the runtime — use `Protocol` for structural typing, generics to preserve type relationships, and strict mode on new code to catch bugs before they run.**

---

## Part 7 — Modern Packaging & Tooling

Python's packaging ecosystem has historically been confusing. By 2026 it has converged on a clear set of standards and a standout tool. This part is the "just tell me what to use" guide.

### `uv` — The Tool That Replaced the Toolchain

**[uv](https://docs.astral.sh/uv/)** (Astral, the company behind Ruff) is a Rust-based tool that replaces `pip`, `pip-tools`, `virtualenv`, `pyenv`, `pipx`, and most of `poetry`/`pdm` in a single binary. It's **10–100× faster** than `pip` for resolution and installation, and it has become the default recommendation:

```bash
# Install uv (standalone, no Python required):
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a project with a managed virtual environment:
uv init myproject && cd myproject
uv add requests httpx                     # add dependencies (updates pyproject.toml)
uv add --dev pytest mypy ruff             # dev dependencies
uv run python main.py                     # run in the managed venv
uv run pytest                             # run tests in the managed venv

# Lock and sync (reproducible installs):
uv lock                                   # generate/update uv.lock
uv sync                                   # install exactly what's in the lockfile

# Install and manage Python versions:
uv python install 3.12 3.13               # download and manage Pythons
uv python pin 3.13                        # pin the project to 3.13

# Run one-off tools without installing (replaces pipx):
uv tool run ruff check .
uvx ruff check .                          # shorthand
```

`uv` reads and writes **`pyproject.toml`** (PEP 621), the standard project metadata file that replaced `setup.py`, `setup.cfg`, and `requirements.txt` as the source of truth. It generates a **`uv.lock`** file for reproducible installs (like `package-lock.json` or `Cargo.lock`).

### `pyproject.toml` — The One File

```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest", "mypy", "ruff"]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

This replaces `setup.py`, `setup.cfg`, `requirements.txt`, `requirements-dev.txt`, `.flake8`, `mypy.ini`, and `pytest.ini` — all in one file, all standardized (PEP 621).

### Ruff — Linting and Formatting

**[Ruff](https://docs.astral.sh/ruff/)** replaces `flake8`, `isort`, `black`, `pyflakes`, `pycodestyle`, `pydocstyle`, and dozens of other linters/formatters — written in Rust, runs in milliseconds:

```bash
ruff check .              # lint (replaces flake8 + isort + dozens of plugins)
ruff check --fix .        # auto-fix what it can
ruff format .             # format (replaces black)
```

### The Modern Python Toolchain, Summarized

| Job | 2020 tool(s) | 2026 tool |
|---|---|---|
| Install packages | `pip` | **`uv add`** / `uv pip install` |
| Virtual environments | `virtualenv` / `venv` | **`uv`** (manages them automatically) |
| Lock dependencies | `pip-tools` / `poetry lock` | **`uv lock`** |
| Manage Python versions | `pyenv` | **`uv python`** |
| Run one-off tools | `pipx` | **`uvx`** |
| Project metadata | `setup.py` / `setup.cfg` | **`pyproject.toml`** |
| Lint | `flake8` + `isort` + plugins | **`ruff check`** |
| Format | `black` | **`ruff format`** |
| Type-check | `mypy` | **`mypy`** or **`pyright`** |

If you remember one thing from Part 7: **use `uv` for everything (dependencies, venvs, Python versions, running tools), `pyproject.toml` as the single config file, and `ruff` for linting and formatting — the Python tooling story has converged and it's fast.**

---

## Part 8 — Profiling & Measurement

The cardinal rule of performance work: **measure before you optimize.** Intuition about where code spends its time is almost always wrong — doubly so in Python, where the interpreter's overhead and the call into C extensions make hot spots unintuitive. This part is about finding the bottleneck *before* you reach for the levers of Part 9.

### Time It: `timeit`

For microbenchmarks — "is approach A faster than approach B for this one expression":

```python
import timeit

# From the REPL or script:
timeit.timeit('"-".join(str(i) for i in range(100))', number=10_000)
timeit.timeit('"-".join(map(str, range(100)))', number=10_000)

# Or the CLI:
# python -m timeit '"-".join(str(i) for i in range(100))'
```

`timeit` automatically disables GC, runs multiple loops, and reports the best time. For comparing alternatives, always benchmark both on the *same machine, same data, same Python version*.

### Profile It: `cProfile` + Visualization

When you need to know *where* a program spends its time:

```bash
python -m cProfile -o profile.out myscript.py
# Then visualize:
pip install snakeviz
snakeviz profile.out        # opens a browser-based flame graph
```

Or inline:

```python
import cProfile, pstats

with cProfile.Profile() as pr:
    expensive_function()

stats = pstats.Stats(pr)
stats.sort_stats("cumulative")
stats.print_stats(20)         # top 20 by cumulative time
```

Read the output columns: **`tottime`** is time spent *in* that function (excluding callees) — that's where the function itself is slow; **`cumtime`** is total time including callees — that's the end-to-end cost. Sort by `tottime` to find the hot loop; sort by `cumtime` to find the expensive call chain.

### Line-Level Profiling

`cProfile` is per-function. When you've found the slow function and need to know *which line*, use **`line_profiler`**:

```bash
pip install line_profiler
```

```python
# Decorate the function you want to profile:
@profile                          # line_profiler recognizes this decorator
def process(data):
    parsed = parse(data)          # Line 2:  12.3s
    validated = validate(parsed)  # Line 3:   0.1s
    result = compute(validated)   # Line 4:  45.2s  ← the real bottleneck
    return result
```

```bash
kernprof -lv myscript.py
```

### Memory Profiling

When memory is the concern (leaks, bloat, OOM):

- **`tracemalloc`** (stdlib) — tracks memory allocations by call site:

```python
import tracemalloc
tracemalloc.start()

# ... run code ...

snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics("lineno")[:10]:
    print(stat)
```

- **`memory_profiler`** — line-by-line memory usage, the memory counterpart to `line_profiler`.
- **`sys.getsizeof(obj)`** — size of *one* object (shallow, doesn't count referenced objects). For deep size, use `pympler.asizeof`.
- **`objgraph`** — visualizes object reference graphs; indispensable for finding memory leaks (cycles, caches that grow unbounded).

### Benchmark Discipline

A handful of rules that prevent misleading results:

1. **Profile with production-like data.** A function that's fast on 100 items may be O(n²) and catastrophic on 100,000.
2. **Warm up.** The first call may include import, JIT warmup (3.13+), or cache population. Run a few warmup iterations before measuring.
3. **Measure the right thing.** Wall time (`time.perf_counter`) for end-to-end latency; CPU time (`time.process_time`) for compute work; allocations (`tracemalloc`) for memory.
4. **Establish a baseline before changing anything.** You need a "before" number to know if the "after" is actually better.

If you remember one thing from Part 8: **`cProfile` + `snakeviz` to find the hot function, `line_profiler` to find the hot line, and `timeit` to compare alternatives — always measure, because intuition about Python performance is almost always wrong.**

---

## Part 9 — Performance Levers

Now the levers, in order of **effort vs. impact** — easiest and highest-return first, exotic last. Each one is motivated by a specific bottleneck from Part 1's runtime model: either reducing **object overhead** (fewer heap allocations, tighter memory layout) or reducing **interpreter dispatch** (fewer bytecode operations, or replacing them with C or machine code).

### Lever 1: Use the Right Data Structure

The single highest-return, lowest-effort optimization. Python's built-in data structures are implemented in C and are *fast* — but only if you're using the right one:

| Need | Reach for | Not | Why |
|---|---|---|---|
| Membership test (`x in col`) | `set` — O(1) | `list` — O(n) | A `set` is a hash table; a `list` is a linear scan |
| Lookup by key | `dict` — O(1) | list of tuples — O(n) | |
| FIFO queue (append/pop both ends) | `collections.deque` — O(1) | `list.pop(0)` — O(n) | `list.pop(0)` shifts every element |
| Sorted access, priority | `heapq` — O(log n) push/pop | sorting after every insert — O(n log n) | |
| Counting | `collections.Counter` | manual dict += 1 | Counter is cleaner and often faster |
| Ordered unique set | `dict.fromkeys(items)` (3.7+ dicts are ordered) | manual dedup | |
| Named fields | `@dataclass(slots=True)` or `NamedTuple` | regular class (memory) or plain tuple (readability) | |

The classic performance murder: checking `if item in large_list` inside a loop. Replacing the `list` with a `set` turns an O(n²) algorithm into O(n). Always **profile first** (Part 8), but this is where the fix usually lives.

### Lever 2: Move the Loop into C

Python's per-iteration overhead (Part 1's bytecode dispatch) means a tight `for` loop doing simple work spends most of its time in the interpreter, not in the work. The fix: **replace the Python loop with a single call to a C-implemented function** that does the loop internally:

```python
# Slow — Python loop, one bytecode dispatch per element:
total = 0
for x in data:
    total += x

# Fast — one call into C, loop runs in C:
total = sum(data)
```

Built-in functions and methods that loop in C: `sum`, `min`, `max`, `any`, `all`, `sorted`, `"".join`, `map`, `filter`, `str.translate`, `bytes.decode`, `list.sort`, and — most importantly — the entire NumPy/pandas/polars API. This is the fundamental reason "use NumPy" is a real performance answer: **NumPy replaces a million Python-level loop iterations with a single C call that operates on a contiguous array of machine-native values.**

### Lever 3: NumPy and Vectorization

NumPy arrays (`ndarray`) are **contiguous, typed, fixed-size arrays of machine values** — not arrays of `PyObject` pointers. An array of a million `float64`s is 8 MB of contiguous memory (1M × 8 bytes), not the ~28 MB of a million Python `float` objects plus a million-pointer list. Operations on them run in C, at SIMD speed, with the GIL released:

```python
import numpy as np

# Python loop: ~500 ms for 10M elements
result = [x ** 2 + 2 * x + 1 for x in range(10_000_000)]

# NumPy vectorized: ~30 ms — 15× faster, less memory
a = np.arange(10_000_000)
result = a ** 2 + 2 * a + 1         # entire computation in C, no Python loop
```

The principle is **vectorization**: express the operation as a whole-array transformation, not an element-at-a-time loop. If your computation fits this pattern (and numerical/data work almost always does), NumPy is the answer *before* reaching for threading, multiprocessing, or Cython.

**Pandas** and **Polars** sit on top of this idea for tabular data. Polars in particular is worth calling out — it's a Rust-backed dataframe library that auto-parallelizes, uses lazy evaluation, and is often 5–10× faster than pandas for the same query.

### Lever 4: Caching and Memoization

If you compute the same result repeatedly, **cache it**:

```python
from functools import lru_cache, cache

@cache                     # unbounded cache (3.9+); use @lru_cache(maxsize=N) to bound
def expensive(n: int) -> int:
    # ... slow computation ...
    return result

# Classic use: recursive algorithms that revisit subproblems
@cache
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)
fib(100)  # instant — each subproblem computed once
```

For more control (TTL, size limits, async, distributed): `cachetools` (in-process), Redis (networked — see the [Redis guide](REDIS_STUDY_GUIDE.md)).

### Lever 5: `__slots__`, `struct`, and Memory Layout

When you have millions of small objects, per-object overhead dominates (Part 1). `__slots__` (Part 3) eliminates the per-instance `__dict__` — roughly halving memory per object. `@dataclass(slots=True)` is the ergonomic way.

For even denser packing, the **`struct`** module packs values into flat byte buffers with no per-value object overhead:

```python
import struct
# Pack a million (x, y, z) float triples into a single bytes object:
fmt = "fff"
buffer = b"".join(struct.pack(fmt, x, y, z) for x, y, z in points)
# 12 bytes per point vs. ~200+ bytes for a Python tuple of three floats
```

And `array.array` sits between `list` and NumPy — a typed C array of scalars without NumPy's dependency:

```python
from array import array
a = array("d", range(1_000_000))   # 8 MB (8 bytes × 1M), not ~28 MB for a list of floats
```

### Lever 6: String Performance

Strings are immutable, so concatenation in a loop creates a new string (and copies all previous characters) each time — classic O(n²):

```python
# O(n²) — each += copies the entire string so far:
s = ""
for word in words:
    s += word + " "

# O(n) — join allocates once:
s = " ".join(words)
```

**Always use `"".join(iterable)` for building strings from parts.** For formatted output, f-strings are faster than `%` formatting and `.format()`. For character-level transformations, `str.translate()` with `str.maketrans()` runs in C and is dramatically faster than a Python loop.

### Lever 7: Concurrency and Parallelism

Covered in depth by the sibling guides — here's the one-paragraph summary as a performance lever:

- **I/O-bound** (network, disk): use `asyncio` (thousands of concurrent connections, single thread — [Asyncio guide](ASYNCIO_STUDY_GUIDE.md)) or `ThreadPoolExecutor` (simpler for a few parallel calls — [Concurrency guide](PYTHON_CONCURRENCY.md)).
- **CPU-bound**: use `ProcessPoolExecutor` or `multiprocessing` to bypass the GIL with separate processes, or call a GIL-releasing C extension (NumPy, etc.). The free-threaded build (Part 1) may eventually make CPU threading viable.
- **Both**: `asyncio` with `loop.run_in_executor()` for the CPU-heavy parts.

### Lever 8: C Extensions, Cython, and Compilation

When pure-Python hot loops can't be vectorized, you compile them:

| Tool | What it does | Effort | Speedup |
|---|---|---|---|
| **Cython** | compiles Python-like code (`.pyx`) to C extension modules; optional static types give bigger speedups | medium | 10–100× for typed code |
| **Mypyc** | compiles type-annotated Python directly to C extensions — your existing code, no new syntax | low–medium | 2–5× typical |
| **cffi / ctypes** | call existing C/Rust shared libraries from Python | low | depends on library |
| **PyO3 / maturin** | write Python extensions in **Rust** | medium–high | near-C speed with safety |
| **Numba** | JIT-compiles numerical Python (NumPy-heavy code) to machine code via LLVM, with a decorator | low | 10–100× for numerical loops |
| **PyPy** | alternative Python interpreter with a tracing JIT — run your existing code 2–10× faster | zero (just switch interpreters) | 2–10× |

The decision tree: **try PyPy first** (zero effort) → then **Numba** for numerical code (one decorator) → then **Mypyc** (existing typed code) → then **Cython** or **PyO3/Rust** for the truly hot path.

### Lever 9: Algorithm and Architecture

The lever that dwarfs all others but isn't Python-specific: **use a better algorithm.** An O(n log n) sort beats an O(n²) sort by a million× at n=10⁶, regardless of language. No amount of Cython or NumPy saves an O(n³) when an O(n log n) exists.

Beyond algorithms: sometimes the right answer is **not running the computation at all** — caching the result (Lever 4), precomputing at build time, or moving the hot path to a service written in a compiled language. Python is the glue; let it be glue, and let the hot inner loop be C, Rust, or a database query.

If you remember one thing from Part 9: **the performance levers in order of effort-to-impact are: right data structure → move the loop into C (`sum`/`map`/joins) → NumPy vectorization → caching → `__slots__` and memory layout → string joins → concurrency → compiled extensions → better algorithm.** Profile first, and pick the cheapest lever that solves the measured bottleneck.

---

## Part 10 — High-Performance Recipes

The payoff. Each recipe is a complete, worked pattern for a common performance problem — profiled, explained, and ready to adapt. They're ordered from "you'll use this Tuesday" to "you'll use this when the stakes are high."

### Recipe 1: Replace a Membership-Test Loop with a Set

The most common Python performance fix in the wild:

```python
# BEFORE — O(n × m): for each item, linear scan of the blocklist
blocklist = load_blocklist()                  # returns a list of 50,000 entries
results = [x for x in stream if x not in blocklist]   # each `in` is O(50,000)

# AFTER — O(n + m): build the set once (O(m)), then O(1) per lookup
blocklist = set(load_blocklist())             # one-time O(m) cost
results = [x for x in stream if x not in blocklist]   # each `in` is O(1)
```

If `stream` has 1M items and `blocklist` has 50K, the before version does 50 *billion* comparisons; the after version does 1 million hash lookups. The fix is one word: `set(...)`.

### Recipe 2: Batch Database Inserts

Inserting rows one at a time in a loop is the database equivalent of string concatenation — each insert is a network round-trip:

```python
# SLOW — 10,000 round-trips:
for row in rows:
    cursor.execute("INSERT INTO t (a, b) VALUES (%s, %s)", row)

# FAST — 1 round-trip:
from psycopg.rows import dict_row  # psycopg 3
cursor.executemany("INSERT INTO t (a, b) VALUES (%s, %s)", rows)

# FASTEST — COPY protocol (bulk load, bypasses SQL parser):
with cursor.copy("COPY t (a, b) FROM STDIN") as copy:
    for row in rows:
        copy.write_row(row)
```

`executemany` batches into fewer round-trips; `COPY` (Postgres) or `LOAD DATA` (MySQL) is a streaming binary protocol — 10–100× faster for bulk loads. See the [Postgres guide](POSTGRES.md) and the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md) (which covers `asyncpg` + `COPY` in an async pipeline).

### Recipe 3: Process a Large File Without Loading It

```python
import csv
from itertools import batched

def active_users(path: str):
    """Yield active users from a multi-GB CSV, constant memory."""
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:                         # lazy — one row at a time
            if row["status"] == "active":
                yield row["email"]

# Consume lazily in batches:
for batch in batched(active_users("users.csv"), 500):
    send_emails(batch)                             # 500 at a time, never all at once
```

Peak memory: ~500 rows × row size, regardless of file size. The `open()` file object, `csv.reader`, and the generator are all lazy.

### Recipe 4: Vectorize a Numerical Computation with NumPy

```python
import numpy as np

# BEFORE — pure Python, ~12 seconds for 10M points:
def distances_slow(points, origin):
    return [((p[0]-origin[0])**2 + (p[1]-origin[1])**2) ** 0.5 for p in points]

# AFTER — NumPy vectorized, ~0.08 seconds (150× faster):
def distances_fast(points: np.ndarray, origin: np.ndarray) -> np.ndarray:
    return np.sqrt(np.sum((points - origin) ** 2, axis=1))

points = np.random.rand(10_000_000, 2)
origin = np.array([0.5, 0.5])
result = distances_fast(points, origin)
```

The entire computation — subtraction, squaring, summing, square root — runs in C on contiguous memory with SIMD instructions. No Python loop, no per-element object allocation.

### Recipe 5: JIT a Hot Loop with Numba

When you can't vectorize cleanly (the loop body has branches, state, or complex logic):

```python
from numba import njit
import numpy as np

@njit                              # compiles to machine code on first call
def mandelbrot(c_real, c_imag, max_iter):
    """Count iterations for a single point."""
    z_real, z_imag = 0.0, 0.0
    for i in range(max_iter):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        if z_real_sq + z_imag_sq > 4.0:
            return i
        z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
    return max_iter

@njit(parallel=True)               # auto-parallelize the outer loop
def render(width, height, max_iter):
    result = np.zeros((height, width), dtype=np.int32)
    for j in numba.prange(height):  # parallel range
        for i in range(width):
            result[j, i] = mandelbrot(
                -2.0 + 3.0 * i / width,
                -1.0 + 2.0 * j / height,
                max_iter,
            )
    return result

image = render(4000, 3000, 256)    # first call compiles; subsequent calls are fast
```

Pure Python: minutes. Numba: seconds — comparable to C. The `@njit` decorator compiles the function to LLVM machine code, and `parallel=True` + `prange` auto-parallelizes across CPU cores. The constraint: Numba works on a subset of Python (mostly NumPy arrays and scalar math); general Python objects and third-party library calls aren't supported inside `@njit`.

### Recipe 6: Concurrent HTTP Fetches with `asyncio`

When you need to call 500 APIs and the bottleneck is waiting for responses:

```python
import asyncio
import httpx

async def fetch(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

async def fetch_all(urls: list[str], max_concurrent: int = 50) -> list[dict]:
    semaphore = asyncio.Semaphore(max_concurrent)    # don't open 500 connections at once
    async with httpx.AsyncClient() as client:
        async def bounded_fetch(url):
            async with semaphore:
                return await fetch(client, url)
        return await asyncio.gather(*(bounded_fetch(u) for u in urls))

results = asyncio.run(fetch_all(urls))
```

Synchronous: 500 × ~200ms = 100 seconds (sequential). Async with 50 concurrency: ~2 seconds (50 in-flight at a time, overlapping waits). The semaphore is critical — without it you'd open 500 connections simultaneously and likely get rate-limited or OOM. Full treatment in the [Asyncio guide](ASYNCIO_STUDY_GUIDE.md).

### Recipe 7: CPU Parallelism with `ProcessPoolExecutor`

When the work is CPU-bound and you need all your cores:

```python
from concurrent.futures import ProcessPoolExecutor
import math

def is_prime(n: int) -> bool:
    if n < 2: return False
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

candidates = range(10_000_000, 10_100_000)

# Single process: ~30 seconds
# primes = [n for n in candidates if is_prime(n)]

# 8 processes on 8 cores: ~4 seconds
with ProcessPoolExecutor() as pool:
    results = pool.map(is_prime, candidates, chunksize=1000)
    primes = [n for n, prime in zip(candidates, results) if prime]
```

`chunksize` matters: the default sends one item per IPC message; `chunksize=1000` batches them, cutting the per-item serialization overhead. See the [Concurrency guide](PYTHON_CONCURRENCY.md) for the full treatment.

### Recipe 8: Reduce Object Memory with `__slots__`

When you're holding millions of instances:

```python
from dataclasses import dataclass
import sys

@dataclass
class PointDict:
    x: float
    y: float
    z: float

@dataclass(slots=True)
class PointSlots:
    x: float
    y: float
    z: float

d = PointDict(1.0, 2.0, 3.0)
s = PointSlots(1.0, 2.0, 3.0)

sys.getsizeof(d) + sys.getsizeof(d.__dict__)   # ~200 bytes
sys.getsizeof(s)                                 # ~72 bytes — 2.8× less

# At 10M instances: ~1.9 GB vs ~690 MB — the difference between OOM and fine.
```

### Recipe 9: Fast String Building and Transformation

```python
words = ["hello"] * 1_000_000

# SLOW — O(n²) quadratic concatenation:
s = ""
for w in words:
    s += w + " "

# FAST — O(n), single allocation:
s = " ".join(words)

# Character transformation — 10× faster than a Python loop:
table = str.maketrans("aeiou", "AEIOU")
result = "hello world".translate(table)   # "hEllO wOrld"
```

### Recipe 10: Precompute and Intern for Lookup-Heavy Code

When you're doing millions of dictionary lookups with the same string keys:

```python
import sys

# Intern the keys so dict lookups compare by pointer (O(1)) not content (O(n)):
KEY = sys.intern("frequently_used_key")

# Precompute a lookup table instead of repeated conditional logic:
# SLOW:
def category(code):
    if code == "A": return "alpha"
    if code == "B": return "beta"
    # ... 50 more branches
    return "unknown"

# FAST:
CATEGORY_MAP = {"A": "alpha", "B": "beta", ...}   # dict lookup — O(1), branch-free
def category(code):
    return CATEGORY_MAP.get(code, "unknown")
```

### The Decision Tree

When a program is too slow, work through this:

```text
1. Profile it (Part 8) — find the actual bottleneck
   │
2. Wrong data structure? (set instead of list, deque instead of list.pop(0))
   │ yes → fix it, re-profile
   │ no ↓
3. Python loop over simple operations? (sum, join, map, built-in)
   │ yes → replace with C built-in, re-profile
   │ no ↓
4. Numerical computation? (arrays, matrices, math)
   │ yes → NumPy / Polars vectorization, re-profile
   │ no ↓
5. Repeated computation? (same inputs, same result)
   │ yes → @cache / @lru_cache, re-profile
   │ no ↓
6. I/O-bound? (network, disk, database)
   │ yes → asyncio / ThreadPoolExecutor (→ sibling guides)
   │ no ↓
7. CPU-bound, parallelizable?
   │ yes → ProcessPoolExecutor / multiprocessing
   │ no ↓
8. Hot loop, can't vectorize?
   │ yes → Numba @njit / Cython / PyO3 (Rust) / try PyPy
   │ no ↓
9. Wrong algorithm?
   │ yes → rethink the approach (O(n²) → O(n log n))
   │ no ↓
10. Accept it, or move the hot path out of Python.
```

If you remember one thing from Part 10: **profile first, then pick the cheapest lever that fixes the measured bottleneck — right data structure beats micro-optimization, vectorization beats compiled extensions, and the best optimization is often the one that avoids the work entirely.**

---

That's the guide. From here the highest-leverage next step is the one that sticks: take a piece of code you've written that's slower than you'd like, run `cProfile` + `snakeviz` on it, find the hot spot, and apply the cheapest lever from Part 9's list. The pattern — measure, identify the bottleneck class, apply the matching lever, re-measure — is a skill that compounds for the rest of your career, and it works in every language. Python just makes the levers especially visible because the interpreter overhead gives you so many concrete places to push.

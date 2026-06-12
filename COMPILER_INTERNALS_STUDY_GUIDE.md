# Compiler and Language Internals

A textbook-level study guide to what compilers, interpreters, and language runtimes actually do — for engineers who use languages daily and want to understand the machine beneath them. Every language is a leaky abstraction over what its compiler produces, and the leaks are where senior work happens: why this code deoptimizes in V8, why TypeScript accepts that unsound assignment, why Rust's borrow checker rejects a program you know is fine, why `-O2` deleted your null check, why the build spends four minutes in the linker. This guide covers the full pipeline — lexing, parsing, semantic analysis, type systems and inference, intermediate representations and SSA, optimization, code generation, linking, bytecode interpreters, JIT compilation, and garbage collection — and then tours the real systems (CPython, tsc, rustc, V8, HotSpot, LLVM) so the theory attaches to the tools you actually run.

The method follows this repo's [Distributed Algorithms](DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md) and [Database Internals](DATABASE_INTERNALS_STUDY_GUIDE.md) guides: precise mechanisms, worked examples you can run, claims you can verify against real tools, and exercises closing every chapter. A miniature language — **Calc**, an expression-and-statements toy — is built incrementally in plain Python across Chapters 2–4, 7, and 11, because thirty lines of working lexer teach more than three pages about lexing. Total lab code is a few hundred lines; type it, don't copy it.

Primary references: Bob Nystrom, [*Crafting Interpreters*](https://craftinginterpreters.com/) (free online; the best first book on this material, full stop); Cooper & Torczon, *Engineering a Compiler* (the modern textbook); the [LLVM Kaleidoscope tutorial](https://llvm.org/docs/tutorial/); Cornell's [CS 6120 self-guided course](https://www.cs.cornell.edu/courses/cs6120/2020fa/self-guided/) (optimization and SSA, with implementation homework); the [V8 blog](https://v8.dev/blog) and [rustc dev guide](https://rustc-dev-guide.rust-lang.org/) for the production systems.

---

## Table of Contents

1. [Chapter 1 — The Shape of a Language Implementation](#chapter-1--the-shape-of-a-language-implementation)
2. [Chapter 2 — Lexing](#chapter-2--lexing)
3. [Chapter 3 — Parsing](#chapter-3--parsing)
4. [Chapter 4 — ASTs, Names, and Semantic Analysis](#chapter-4--asts-names-and-semantic-analysis)
5. [Chapter 5 — Type Systems I: Checking](#chapter-5--type-systems-i-checking)
6. [Chapter 6 — Type Systems II: Inference, Ownership, and the Fancy End](#chapter-6--type-systems-ii-inference-ownership-and-the-fancy-end)
7. [Chapter 7 — Intermediate Representations and SSA](#chapter-7--intermediate-representations-and-ssa)
8. [Chapter 8 — Optimization](#chapter-8--optimization)
9. [Chapter 9 — Code Generation](#chapter-9--code-generation)
10. [Chapter 10 — Linking and Loading](#chapter-10--linking-and-loading)
11. [Chapter 11 — Interpreters and Bytecode VMs](#chapter-11--interpreters-and-bytecode-vms)
12. [Chapter 12 — JIT Compilation](#chapter-12--jit-compilation)
13. [Chapter 13 — Garbage Collection and Memory Runtimes](#chapter-13--garbage-collection-and-memory-runtimes)
14. [Chapter 14 — The Real Compilers, Toured](#chapter-14--the-real-compilers-toured)
15. [Chapter 15 — Where to Go Next](#chapter-15--where-to-go-next)

---

## Chapter 1 — The Shape of a Language Implementation

### 1.1 The pipeline

Every language implementation — gcc, CPython, V8, tsc — is a variation on one pipeline, and fixing it in mind gives every later chapter an address:

```
source text
  │  lexer        → tokens                      (Ch. 2)
  │  parser       → syntax tree                 (Ch. 3)
  │  analysis     → resolved, typed tree        (Ch. 4–6)   ← the "frontend" ends here
  │  lowering     → intermediate representation (Ch. 7)
  │  optimizer    → better IR                   (Ch. 8)     ← the "middle end"
  │  codegen      → machine code / bytecode     (Ch. 9, 11)
  │  link/load    → a runnable program          (Ch. 10)    ← the "backend" ends here
  └─ runtime      → GC, JIT, dispatch           (Ch. 11–13) ← runs alongside your program
```

The frontend knows everything about the language and nothing about the machine; the backend knows everything about the machine and nothing about the language; the IR in the middle is the treaty between them. This separation is not just pedagogy — it is the actual industrial structure: LLVM is a middle-and-back-end that a dozen frontends (C, C++, Rust, Swift, Zig, Julia) share, which is why "write a frontend, get world-class optimization free" has shaped two decades of language design.

### 1.2 The execution spectrum

"Compiled vs. interpreted" is a property of *implementations*, not languages, and it's a spectrum, not a binary:

- **Ahead-of-time (AOT) native**: the whole pipeline runs before execution; the artifact is machine code. gcc/clang for C/C++, rustc, Go.
- **Bytecode interpreter**: the frontend runs ahead of time (or at import time), producing **bytecode** — instructions for a virtual machine, not a CPU — which an interpreter loop executes. CPython, Lua, the JVM and CLR *before* their JITs kick in.
- **JIT-compiled**: starts interpreting, *watches the program run*, and compiles the hot parts to machine code using what it observed — types, branch frequencies, call targets. V8, HotSpot, .NET, PyPy, LuaJIT. The defining trade: optimization decisions made with runtime knowledge AOT can never have, paid for with warmup time and the machinery to *undo* wrong guesses (deoptimization, Ch. 12).
- **Transpilers** compile to another high-level language (tsc emits JavaScript; the interesting part of tsc is therefore not codegen — it has almost none — but the type checker, Ch. 5/14).

Where each real system sits, for orientation: **rustc** is AOT through LLVM; **CPython** is a bytecode interpreter (with a young, optional JIT — Ch. 12); **V8** is a four-tier JIT; **HotSpot** interprets JVM bytecode then tier-compiles; **Go** is AOT with its own (non-LLVM) backend tuned for compile speed. None of these choices is "modern vs. legacy"; each is a deliberate position on the trade triangle of *startup time, peak speed, and implementation complexity*.

### 1.3 How to study an implementation (the tools used throughout)

Like databases, language implementations are honest if you know where to look:

```bash
# CPython: every frontend stage is importable
python -c "import tokenize,io; [print(t) for t in tokenize.generate_tokens(io.StringIO('x+=1').readline)]"
python -c "import ast; print(ast.dump(ast.parse('x = 1 + 2*y'), indent=2))"
python -c "import dis; dis.dis(compile('x = 1 + 2*y','','exec'))"

# C/C++/Rust: watch the middle and back ends
clang -O2 -S -emit-llvm f.c -o -      # LLVM IR after optimization
rustc --emit=llvm-ir -O f.rs          # same, from Rust
cargo rustc -- --emit=mir             # rustc's own mid-level IR

# The single most useful tool in this guide:
#   https://godbolt.org  (Compiler Explorer) — source on the left,
#   any compiler's assembly/IR on the right, diffable across flags.

# V8: watch the JIT think
node --trace-opt --trace-deopt app.js
node --allow-natives-syntax -e 'function f(o){return o.x}; /* %DebugPrint(obj) shows hidden classes */'
```

A standing instruction: when any chapter makes a claim about what a compiler does, take a five-line example to Compiler Explorer or `dis` and watch it happen. The difference between knowing *about* compilers and knowing compilers is exactly this habit.

### Exercises 1

1. Classify these on the execution spectrum, with one sentence of evidence each: Java, Ruby (CRuby), Ruby (TruffleRuby), C#, Bash, TypeScript, Julia, Go, PHP 8.
2. For one small function, collect the artifacts of every pipeline stage CPython exposes: tokens, AST, bytecode (`tokenize`, `ast`, `dis`). Label each with its pipeline stage.
3. On Compiler Explorer, compile `int f(int x){return x*2;}` with gcc at `-O0` and `-O2`. The multiply becomes what instruction, and which chapter of this guide owns that transformation?
4. Make the startup-vs-peak trade concrete: time `python -c pass`, `node -e ''`, and a hello-world Go binary. Explain each number's relationship to its position on the spectrum.

---

## Chapter 2 — Lexing

### 2.1 The job: characters → tokens

The lexer (scanner, tokenizer) turns a character stream into a **token** stream — the smallest units that carry meaning: identifiers, keywords, literals, operators, punctuation. Its theoretical home is **regular languages**: token shapes are describable by regular expressions, recognizable by finite automata, which is why lexing needs no lookahead beyond a character or two and runs in linear time. The practical consequence of the theory: a lexer can be a single loop with a `switch` on the current character, and in production compilers it usually is (generated lexers exist — `flex`, `logos` — but hand-written dominates among major compilers because lexing is easy and error messages matter).

The one universal rule worth naming: **maximal munch** — at each point, consume the longest token that matches. `>=` is one token, not `>` then `=`; `forty` is an identifier, not the keyword `for` followed by `ty`. Keywords are the standard subtlety: lex them *as identifiers*, then check against a keyword table — trying to match keywords first is how you make `format` lex as `for`+`mat`.

### 2.2 The lab: a lexer in 40 lines

Calc's tokens: numbers, identifiers, keywords (`let`, `if`, `else`, `while`, `print`), operators, punctuation.

```python
import re
from collections import namedtuple

Token = namedtuple("Token", "kind value line")

KEYWORDS = {"let", "if", "else", "while", "print", "fn", "return", "true", "false"}
TOKEN_RE = re.compile(r"""
    (?P<NUMBER>  \d+(\.\d+)? )
  | (?P<IDENT>   [A-Za-z_]\w* )
  | (?P<OP>      ==|!=|<=|>=|[+\-*/<>=(){},;] )
  | (?P<NEWLINE> \n )
  | (?P<SKIP>    [ \t]+ | \#[^\n]* )
  | (?P<ERROR>   . )
""", re.VERBOSE)

def lex(src):
    line = 1
    for m in TOKEN_RE.finditer(src):
        kind, text = m.lastgroup, m.group()
        if kind == "NEWLINE": line += 1
        elif kind == "SKIP":  continue
        elif kind == "ERROR": raise SyntaxError(f"line {line}: unexpected {text!r}")
        elif kind == "IDENT" and text in KEYWORDS:
            yield Token(text.upper(), text, line)         # keyword
        else:
            yield Token(kind, text, line)
    yield Token("EOF", "", line)
```

Note what even this toy must decide: comments and whitespace are *consumed here* and never reach the parser (most languages; significant-whitespace languages are next), the regex alternation order implements maximal munch for operators (`==` before `=`), and every token carries a **source position** — the thing that makes error messages possible, and the bookkeeping that real lexers spend half their code on (column tracking, tab policy, multi-byte characters).

### 2.3 Where real lexers earn their pay

**Significant indentation** (Python): the lexer *synthesizes tokens that aren't in the text*. CPython's tokenizer maintains a stack of indentation levels and emits `INDENT`/`DEDENT` tokens as the level changes — so by the time the parser runs, Python's block structure looks exactly like curly braces. Run the `tokenize` one-liner from Ch. 1 on an indented snippet and watch them appear; "this language has no braces" is false at the token level. **Lexer hacks**: some grammars are not context-free at the token level — C's `T * x;` (multiplication or pointer declaration? depends on whether `T` names a type) forces the lexer/parser to consult the symbol table, a famous wart that newer languages design away. **Raw/nested constructs**: string interpolation (`"hello ${name}"`) makes the lexer re-entrant — modern lexers handle a stack of modes. **Unicode**: identifier rules (UAX #31), normalization, and the security corner (homoglyph identifiers) are why "just `\w+`" doesn't survive contact with production.

### Exercises 2

1. Extend the lab lexer: string literals with escapes, and `**` (power) — placing it correctly relative to `*` in the alternation. Add a test where wrong ordering would mis-lex.
2. Run CPython's `tokenize` on a function with nested indentation; map every `INDENT`/`DEDENT` to the brace it would be in C. What does the tokenizer do with a blank line inside a block, and why must it?
3. Demonstrate maximal munch ambiguity: in C++, `>>` inside nested templates (`vector<vector<int>>`) was famously two tokens until C++11. Explain the original problem and what the fix traded.
4. Write the three-line pathological case for a backtracking regex lexer (catastrophic backtracking) and explain why production lexers are written as single-pass automata instead.

---

## Chapter 3 — Parsing

### 3.1 Grammars, and the tree hiding in flat text

A **context-free grammar** assigns structure to token sequences. The grammar for Calc's expressions, written to encode precedence and associativity directly:

```
expr     → equality
equality → comparison ( ("==" | "!=") comparison )*
comparison → term ( ("<" | ">" | "<=" | ">=") term )*
term     → factor ( ("+" | "-") factor )*        # lower precedence binds looser
factor   → unary ( ("*" | "/") unary )*
unary    → "-" unary | primary
primary  → NUMBER | IDENT | "(" expr ")" | IDENT "(" args ")"
```

Read the shape: each precedence level is a rule that consumes the *next tighter* level and then loops on its own operators. That layering is the entire trick for expression grammars — `1 + 2 * 3` parses as `1 + (2*3)` because `term` can only see `*`-products as atoms, never raw additions.

Distinguish two trees now, permanently: the **parse tree** (concrete syntax tree) mirrors the grammar exactly — every rule application is a node, parentheses and semicolons included; the **AST** (abstract syntax tree) keeps only meaning — `(1 + 2)` and `1 + 2` produce identical ASTs, and a `BinaryOp(+, 1, 2)` node doesn't record which grammar rules built it. Parsers *use* the grammar but *emit* the AST; tools that need the original text exactly (formatters like Prettier and rustfmt, refactoring engines) use CSTs or "lossless" syntax trees with trivia attached — a real design axis in modern compiler architecture (Roslyn, rust-analyzer, swift-syntax all chose lossless).

### 3.2 Recursive descent: the technique that won

A **recursive-descent parser** is the grammar transcribed into functions — one per rule, each consuming tokens and returning a tree. It is the technique used by the production compilers you use daily (clang, rustc, tsc, V8's parser, Go), having beaten the parser generators of the textbooks (yacc/bison) on the grounds that matter industrially: error messages, error *recovery*, and freedom to handle the grammar's ugly corners by just writing code. The lab parser, with the expression levels collapsed into one **precedence-climbing (Pratt)** loop — the standard trick for operator expressions that turns seven near-identical functions into a table:

```python
class Parser:
    PREC = {"==":1, "!=":1, "<":2, ">":2, "<=":2, ">=":2,
            "+":3, "-":3, "*":4, "/":4}

    def __init__(self, tokens):
        self.toks = list(tokens); self.i = 0

    def peek(self):  return self.toks[self.i]
    def next(self):  t = self.toks[self.i]; self.i += 1; return t
    def expect(self, kind):
        t = self.next()
        if t.kind != kind:
            raise SyntaxError(f"line {t.line}: expected {kind}, got {t.value!r}")
        return t

    # --- expressions: Pratt loop ---
    def expr(self, min_prec=0):
        left = self.atom()
        while self.peek().kind == "OP" and self.PREC.get(self.peek().value, -1) >= min_prec:
            op = self.next().value
            right = self.expr(self.PREC[op] + 1)      # +1 ⇒ left-associative
            left = ("binop", op, left, right)
        return left

    def atom(self):
        t = self.next()
        if t.kind == "NUMBER": return ("num", float(t.value))
        if t.kind == "IDENT":
            if self.peek().value == "(":              # call
                self.next(); args = []
                while self.peek().value != ")":
                    args.append(self.expr())
                    if self.peek().value == ",": self.next()
                self.expect("OP")                     # ')'
                return ("call", t.value, args)
            return ("var", t.value)
        if t.value == "(":
            e = self.expr(); self.expect("OP"); return e
        if t.value == "-": return ("neg", self.expr(5))
        raise SyntaxError(f"line {t.line}: unexpected {t.value!r}")

    # --- statements: plain recursive descent ---
    def statement(self):
        k = self.peek().kind
        if k == "LET":
            self.next(); name = self.expect("IDENT").value
            self.expect("OP")                          # '='
            return ("let", name, self.expr_semi())
        if k == "PRINT":
            self.next(); return ("print", self.expr_semi())
        if k == "WHILE":
            self.next(); cond = self.expr()
            return ("while", cond, self.block())
        return ("expr", self.expr_semi())

    def expr_semi(self):
        e = self.expr(); self.expect("OP"); return e   # ';'

    def block(self):
        self.expect("OP")                              # '{'
        stmts = []
        while self.peek().value != "}": stmts.append(self.statement())
        self.next()
        return stmts
```

Forty lines of mechanism worth internalizing: the parser is **predictive** (it decides what to parse from the next token, never backtracking — which is what makes it linear-time and its errors precise); **left recursion** is handled by the loop (a grammar rule `term → term "+" factor` would recurse infinitely as a function — the loop *is* the standard transformation); and the Pratt `min_prec` parameter is the entire precedence mechanism — trace `1 + 2 * 3` and then `1 * 2 + 3` by hand once and operator parsing is demystified for life.

### 3.3 The landscape beyond, honestly

**LR/LALR** (yacc, bison): table-driven bottom-up parsing; accepts more grammars than LL, mathematically elegant, and largely abandoned for primary industrial frontends because shift/reduce conflict messages are miserable to debug and error recovery is hard to customize — its modern niche is languages with genuinely gnarly grammars and places where grammar-as-specification matters. **PEG** (parsing expression grammars): ordered choice instead of ambiguity, packrat memoization for linear time — *CPython switched to a PEG parser in 3.9* ([PEP 617](https://peps.python.org/pep-0617/)) precisely to escape LL(1) restrictions that had warped Python's grammar evolution (match statements and parenthesized context managers arrived on the new parser's flexibility). **GLR/Earley**: all CFGs, ambiguity tolerated — the natural-language and many-language-tooling end (tree-sitter, the incremental GLR-ish parser inside your editor's syntax features, is the one you use daily). **Hand-rolled wins anyway** for compilers because of one requirement the textbooks underweight: **error recovery**. An IDE parser cannot stop at the first error — it must produce a *best-effort tree for broken code* (the file is broken almost continuously while you type) so completion and navigation keep working; techniques are synchronization tokens (skip to the next `;` or `}`), error nodes in the tree, and never panicking. tsc is the extreme: it produces an AST for *anything*, reserving all judgment for the checker.

### Exercises 3

1. Trace the Pratt parser on `1 - 2 - 3` and on `2 * 3 + 4 < 20` — write the call tree and the resulting AST. Then change `+1` to `+0` in the recursive call and show what `1 - 2 - 3` becomes (right associativity), and which real operator (exponentiation) wants exactly that.
2. Add `if/else` to the lab parser, then construct the **dangling else** ambiguity (`if a if b print 1; else print 2;` in a braceless grammar). Which parse does your code produce, and what grammar rule or convention resolves it in C?
3. Run `ast.dump` on `(((1)))+2` and `1+2` — confirm parse-tree vs. AST in one experiment. Then find what Python's AST *does* preserve that surprises you (hint: `ast.parse('f(x,)')`).
4. Break the lab parser's input mid-statement and improve its behavior: implement panic-mode recovery (skip to the next `;`), and make it report *three* errors in a three-error file instead of dying on the first.
5. Read [PEP 617](https://peps.python.org/pep-0617/)'s motivation section. Which concrete Python syntax was blocked by the old LL(1) parser, and what does the PEG parser trade for the flexibility (hint: memory, and what the `|` operator means)?

```quiz
Q: Why is the frontend/backend split with an IR "treaty" in the middle an industrial structure, not just pedagogy?
- [x] LLVM is a shared middle-and-back-end that a dozen frontends (C, C++, Rust, Swift, Zig, Julia) target — so "write a frontend, get world-class optimization free" shaped two decades of language design
- [ ] It makes compilers easier to document
- [ ] The IR runs faster than machine code
- [ ] It's required by the C standard
> The frontend knows the language and nothing about the machine; the backend the reverse. That clean separation is why new languages bootstrap on LLVM instead of writing optimizers from scratch.

Q: What does the lexer rule "maximal munch" decide?
- [x] At each point, consume the longest token that matches — so `>=` is one token not two, and `forty` is an identifier not `for`+`ty`
- [ ] It strips all whitespace before parsing
- [ ] It matches keywords before identifiers
- [ ] It enables backtracking on ambiguity
> Keywords are the subtlety: lex them *as identifiers* then check a keyword table, or `format` lexes as `for`+`mat`. Maximal munch plus the keyword-table check is most of a real lexer's tokenizing logic.

Q: In the expression grammar, why does `1 + 2 * 3` parse as `1 + (2*3)`?
- [x] Each precedence level consumes the next *tighter* level as its atom and loops on its own operators — so `term` (the +/- level) can only see `*`-products as atoms, never raw additions
- [ ] The lexer reorders by precedence
- [ ] Multiplication tokens sort first
- [ ] A separate precedence pass rewrites the tree
> The layering is the entire trick for expression grammars. In the Pratt-parser version, the same effect comes from the `min_prec` parameter — `+1` in the recursive call makes operators left-associative.

Q: Why did production compilers (clang, rustc, tsc, V8) choose hand-written recursive descent over LR/LALR parser generators?
- [x] Error messages, error *recovery*, and freedom to handle ugly grammar corners by just writing code — an IDE parser must produce a best-effort tree for continuously-broken code, which shift/reduce tables make miserable
- [ ] Recursive descent parses more grammars
- [ ] Generated parsers are slower at runtime
- [ ] LR parsers can't handle precedence
> The textbooks favor LR for accepting more grammars; industry favors recursive descent because error recovery is the requirement they underweight. tsc is the extreme — it builds an AST for *anything* and defers all judgment to the checker.
```

---

## Chapter 4 — ASTs, Names, and Semantic Analysis

### 4.1 The tree as the program

After parsing, the AST *is* the program for every subsequent phase — so its design is consequential engineering, not bookkeeping. The recurring decisions: **node representation** (Calc's tagged tuples scale to a point; real compilers use typed node classes or, increasingly, *flat arrays with index-based references* — rustc and many modern compilers arena-allocate nodes for cache locality and trivially serializable trees); **the visitor question** (how does code walk a tree with thirty node kinds without thirty hand-written traversals? — OO compilers use visitor classes, functional ones pattern-match, and either way the *structural* traversal is written once and specialized); and **what hangs off nodes** (source spans always; later phases attach types, resolved symbols, and constant values — the AST accretes annotations as it moves down the pipeline, until many compilers re-emit it as a new, lower tree: Ch. 7's lowering).

### 4.2 Name resolution: from text to meaning

`x` is three characters; *which* `x` is a semantic question, and answering it is **name resolution** — binding every identifier use to its declaration. The data structure is the **symbol table**: a stack of **scopes**, pushed at each block/function, each mapping names to symbol records (kind, type slot, declaration site). Resolution walks the AST: declarations insert; uses look up through the scope stack, innermost outward — which *is* lexical scoping, implemented:

```python
class Scopes:
    def __init__(self): self.stack = [{}]
    def push(self): self.stack.append({})
    def pop(self):  self.stack.pop()
    def declare(self, name, info):
        if name in self.stack[-1]: raise NameError(f"duplicate {name}")
        self.stack[-1][name] = info
    def resolve(self, name):
        for scope in reversed(self.stack):
            if name in scope: return scope[name]
        raise NameError(f"undefined {name}")
```

The interesting cases are exactly the ones that complicate this picture. **Forward references**: can a function call another defined later in the file? Most languages say yes for top-level items — which forces resolution to be *two-pass* (collect all declarations, then resolve bodies), the simplest instance of a pattern that recurs throughout semantic analysis. **Shadowing policy** is a language design choice surfaced here (Rust permits it enthusiastically; Java forbids same-scope shadowing). **Hoisting** is JavaScript's infamous answer (`var` declarations are resolved as if moved to function top — a pure name-resolution rule that generations of developers learned as folklore). And **closures** make resolution generate *runtime structure*: when an inner function captures `x` from an enclosing scope, the resolver must classify `x` as a *captured* variable — which tells the backend that `x` can't live on the stack (the frame dies; the closure survives) and must be boxed into a heap cell shared between closure and origin. CPython exposes every bit of this: the `symtable` module shows each variable classified as local/global/**cell**/**free**, and `LOAD_FAST` vs. `LOAD_DEREF` in `dis` output is the classification, executed.

### 4.3 The rest of "semantic analysis"

Name resolution headlines a family of judgment passes between parse and codegen, all sharing its shape (walk the tree, maintain context, record or reject): definite-assignment analysis (Java/C# proving every variable is written before read; TypeScript's `strictPropertyInitialization`), reachability and dead-code checks (`unreachable code` warnings; Rust's "this match is non-exhaustive" — which is type-system-adjacent and Chapter 5's business), `const`-ness and purity checks, and control-flow legality (`break` outside a loop, `return` outside a function). They are unglamorous and they are most of a production frontend by line count — type checking gets the textbooks' attention, but the long tail of "is this program *well-formed*" lives here.

### Exercises 4

1. Implement resolution for Calc: a pass that walks the AST with `Scopes`, rejects use-before-declaration, and annotates each `("var", x)` node with a (scope-depth, slot) pair. Then add blocks and prove shadowing works.
2. Use CPython's `symtable` on a function containing a closure: classify every variable (local/free/cell/global) and match each against `dis` output's `LOAD_FAST`/`LOAD_DEREF`/`LOAD_GLOBAL`.
3. Explain, mechanically, why this JavaScript prints `3 3 3` — and what `let`'s per-iteration binding changes in name-resolution terms:
   `for (var i=0;i<3;i++) setTimeout(()=>console.log(i));`
4. Write the two-pass top-level resolver: make `fn even(n) { ... odd(n-1) ... } fn odd(n) { ... even(n-1) ... }` resolve in Calc. What goes wrong with one pass, and on which call?

---

## Chapter 5 — Type Systems I: Checking

### 5.1 What a type system is for

A type system is a **conservative, compile-time proof procedure**: it assigns types to expressions by rule, and accepts a program only if the rules compose. "Conservative" is load-bearing — by Rice's theorem, any non-trivial property of program behavior is undecidable in general, so a sound type checker must reject *some* programs that would have run fine. Every type system you'll ever use sits somewhere on the axis defined by that fact: reject more good programs (simple, restrictive) versus work harder to accept them (sophisticated, complex) versus accept some bad ones (unsound, pragmatic). Naming the axis turns type-system debates from aesthetics into engineering.

Two vocabulary pairs that get conflated and shouldn't: **static vs. dynamic** is *when* types are checked (compile time vs. runtime — Python is strongly *and* dynamically typed); **strong vs. weak** is roughly *how much implicit conversion* blurs the types (C will reinterpret nearly anything; Python won't add a string to an int). And **gradual typing** (TypeScript, Python's hints, Sorbet) is the engineered middle: static checking where annotations exist, dynamic escape hatches (`any`) where they don't, with the known cost that an `any` is a hole the static guarantees drain out through — `any` infects what it touches, which is why `unknown` (the sound "I don't know yet": you must narrow before use) exists and is almost always what you meant.

### 5.2 Nominal vs. structural: what is a type's identity?

**Nominal** typing (Java, C#, Rust's structs): a type is its *name*; two classes with identical members are unrelated unless declared so (`implements`, inheritance). **Structural** typing (TypeScript, Go's interfaces, OCaml objects): a type is its *shape*; anything with the right members conforms, no declaration needed.

```typescript
interface Point { x: number; y: number }
class Vec { constructor(public x: number, public y: number) {} }
const p: Point = new Vec(1, 2);          // ✓ TypeScript: right shape, conforms
```

```java
interface Point { double x(); double y(); }
class Vec { double x(){...} double y(){...} }   // does NOT implement Point
Point p = new Vec();                      // ✗ Java: no declared relationship
```

Neither is "better"; they encode different theories of compatibility. Structural matches how JavaScript code actually flows (objects shaped by data, not declarations) — which is *why* TypeScript chose it; it had to type-check a world that already existed. Nominal gives intent and privacy (two structurally-identical types — `Meters` and `Feet` — *should* be incompatible; in structural systems you simulate nominality with branded types, a trick worth knowing: `type Meters = number & { __brand: "m" }`). Go's interfaces are the interesting hybrid: structural conformance (no `implements`), checked statically — duck typing with a proof.

### 5.3 Soundness, and TypeScript's deliberate unsoundness

A type system is **sound** if well-typed programs cannot exhibit type errors at runtime ("well-typed programs don't go wrong"). TypeScript is — by explicit, documented [design choice](https://www.typescriptlang.org/docs/handbook/type-compatibility.html) — *unsound* in enumerated places, trading guarantees for usability over the existing JavaScript ecosystem. Know the big three, because each is a lesson in type-system mechanics:

- **Method bivariance / `--strictFunctionTypes` history**: function parameter types should be checked **contravariantly** (a function accepting `Animal` can stand in where one accepting `Dog` is needed — it handles *more*; not vice versa). TypeScript historically checked parameters *bivariantly* (either direction OK) because real-world callback patterns (DOM event handlers) demanded it; strict mode fixed standalone function types, while *method* parameters remain bivariant to keep `Array<Dog>` assignable to `Array<Animal>`.
- **Mutable covariant arrays**: `Dog[]` is assignable to `Animal[]`, after which `animals.push(new Cat())` plants a cat in your dog list with no error — the exact unsoundness Java chose at gunpoint (pre-generics arrays) and checks at *runtime* (`ArrayStoreException`); TypeScript doesn't even check. The principled rule — covariant reads, contravariant writes, invariant read-write — is the same variance logic as the [Advanced Rust guide](ADVANCED_RUST_STUDY_GUIDE.md)'s `&` vs. `&mut`, and recognizing it as *one* principle across languages is a genuine senior-engineer unlock.
- **`any`, assertions (`as`), and declaration files**: trust-me constructs whose claims are never verified — the FFI boundary of the type system.

The deep takeaway is not "TypeScript is sloppy" — it's that **soundness is a dial, and tsc's designers set it deliberately**: a sound TypeScript would have rejected too much working JavaScript to be adopted, and an adopted-but-unsound checker catches more real bugs than a sound-but-unused one. Type-system design is product design.

### 5.4 The checker, mechanically

Checking is a bottom-up tree walk with an environment: literals have known types; variables look up their declared/inferred type (Ch. 4's symbol table grows a type column); each operator/call node has a rule (`+ : (number, number) → number`; call: argument types must be assignable to parameter types, result is the return type); statements check their parts (an `if` condition must be `bool` — or "truthy," a *language* decision the checker merely enforces). **Subtyping** turns the equality checks into an *assignability* relation (is `T` usable where `U` is expected?) with variance governing how type constructors compose, and **flow-sensitive narrowing** — TypeScript's signature move — threads control flow through the types: after `if (typeof x === "string")`, `x`'s type *in that branch* is narrowed; discriminated unions plus exhaustiveness checking (`never` as the type of the impossible) turn the checker into a state-machine verifier. That last family — making illegal states unrepresentable and letting the checker prove you handled every case — is the highest-leverage daily payoff of understanding this chapter.

### Exercises 5

1. Write the 60-line type checker for Calc (types: `num`, `bool`, `str`): annotate `let` with inferred types from initializers, check operators and `if`/`while` conditions, and produce errors with source lines. (The structure mirrors the resolver from Ex. 4.1 — that's the point.)
2. Demonstrate both classic unsoundnesses in real TypeScript: the covariant-array cat-among-dogs, and a method-bivariance accept that `--strictFunctionTypes` would reject for standalone functions. Predict the runtime behavior of each, then run them.
3. Implement branded types: make `Meters`/`Feet` (both `number`) mutually unassignable in TypeScript, with a constructor function each. What does this simulate, in §5.2's vocabulary?
4. Derive the variance table from first principles: for `Producer<T>` (only returns T), `Consumer<T>` (only accepts T), and `Cell<T>` (both), argue which direction of assignability is safe — then check your answers against C#'s `out`/`in` annotations or Kotlin's declaration-site variance.
5. Build a discriminated union state machine in TypeScript (`{state:"idle"} | {state:"loading", started:number} | ...`) with an exhaustive `switch` and a `never` default. Add a state and watch the checker find every unhandled site — then write one sentence on why this is Ch. 4's reachability analysis wearing type clothes.

---

## Chapter 6 — Type Systems II: Inference, Ownership, and the Fancy End

### 6.1 Hindley–Milner: types the programmer never wrote

ML-family languages (OCaml, Haskell, F#, and — locally — Rust) infer types so completely that annotations are optional. The engine is **Hindley–Milner inference** via **unification** (Algorithm W), and it is simpler than its reputation: walk the tree, assign every unknown a fresh **type variable**, record the **equations** each construct implies, and solve them by unification — the same "make these two terms syntactically equal by substituting variables" procedure as Prolog.

Worked, on `fn twice(f, x) = f(f(x))`:

```
assign:   f : α        x : β        result of twice : γ
inner f(x):    f must be a function from typeof(x):        α = β → δ      (fresh δ)
outer f( … ):  f must be a function from typeof(f(x)):     α = δ → ε      (fresh ε)
unify the two views of α:   β → δ  =  δ → ε    ⇒   β = δ,  δ = ε
so:  α = δ → δ,   x : δ,   result γ = δ
twice : (δ → δ, δ) → δ          — i.e. ∀T. ((T→T), T) → T
```

No annotation anywhere, and the result is the *most general* type — HM's celebrated property: principal types, inferred in near-linear time in practice. Two refinements complete the classical picture: the **occurs check** (refuse to unify `α` with `α → β` — otherwise you'd build an infinite type; this is the error behind ML's famously cryptic "occurs check" messages) and **let-generalization** (variables bound by `let` are *generalized* to polymorphic schemes — `let id = fn x => x` gets `∀T. T→T` and can be used at two different types in the next line; lambda parameters are not generalized, which is the precise technical line between "polymorphic definition" and "monomorphic use").

Why doesn't every language do this? Because HM's magic depends on the *absence* of features mainstream languages want: **subtyping wrecks unification** (equations become inequalities; principal types vanish), and overloading, implicit conversion, and inheritance each poke holes. Hence the industry's working compromise, **local/bidirectional inference** (Rust within function bodies, TypeScript, Java's `var`, C++'s `auto`): infer *inside* functions from how values are used, but require **annotations at function boundaries**. That requirement isn't a limitation to apologize for — boundary annotations are machine-checked documentation, error-message firewalls (inference failures stay local), and what makes separate compilation and stable APIs tractable. Rust's choice — full HM-style inference inside bodies, mandatory signatures at item boundaries — is the modern consensus position, arrived at from both directions.

### 6.2 Rust's ownership as a type system

The borrow checker is not an ad-hoc lint bolted onto a normal type system — it is a **substructural type system**, the academic lineage (linear logic, affine types) shipped industrially, and seeing it that way explains "why these exact rules."

In a classical type system, a variable's type permits unlimited use. A **substructural** system restricts the *structural rules* — how many times and in what order assumptions may be used. **Affine** types allow *at most one* use: after you use (move) a value, it's gone from the static environment. That is precisely Rust's move semantics — `let b = a;` doesn't copy the binding's permissions, it *transfers* them, and a later use of `a` is not a runtime hazard but a type error ("value used after move"). References refine the discipline with the shared-XOR-mutable rule, and **lifetimes** make the temporal half checkable: each reference's type carries a *region* — an approximation of the span of code it may live through — and the checker verifies that no reference's region outlives its referent's. Use-after-free becomes ill-*typed*, not just ill-behaved: the same "make the invariant a type" move this guide keeps meeting (and the [Advanced Rust guide](ADVANCED_RUST_STUDY_GUIDE.md) develops from the user's side).

Mechanically, modern borrow checking (**non-lexical lifetimes**) runs not on the AST but on the **MIR** — rustc's mid-level IR (Ch. 7/14), a control-flow graph — computing the live range of each borrow as the set of CFG points it must remain valid through, then checking for conflicting access within ranges. Borrow-check errors are *dataflow analysis results*, which is why they speak in terms of points and paths ("borrow later used here") and why the move from lexical scopes to CFG liveness (NLL, 2018) eliminated whole classes of false rejections: the analysis got a finer notion of "where the borrow is actually alive."

### 6.3 The frontier, briefly and honestly

**Generics implementation** is a type-system decision with Ch. 8–10 consequences: monomorphization (Rust/C++ — specialize per instantiation: fast code, slow compiles, big binaries) versus erasure (Java/TS — one compiled artifact, types gone at runtime) versus dictionary passing (Haskell/Swift/Go — runtime descriptors threaded through; Swift's "witness tables" and Go's "GC shape stenciling" are engineering midpoints). **Dependent types** (Idris, Agda, Lean) move values into types (`Vector n Int` — length in the type; out-of-bounds is ill-typed), at the price of type checking becoming theorem proving; their industrial shadow is **refinement types** (Liquid Haskell, F*) and, more diffusely, the way TypeScript's literal types + narrowing already track *values* flowing through types. **Effect systems** (Koka, OCaml 5's effects, and Java's checked exceptions as the awkward ancestor) type *what a function does* (IO, throws, async) — async/await coloring is an effect system that grew without the theory. None of these are daily tools; all of them are where the daily tools' next features come from.

### Exercises 6

1. Run the unification algorithm by hand on `fn compose(f, g) = fn x => f(g(x))` — fresh variables, equations, solved form. Check your answer against any ML/Haskell REPL (`:t (.)`).
2. Trigger the occurs check in OCaml or Haskell with `fn f => f f`. Write out the failing equation. Why does this *particular* program have no HM type, and what feature (rank-n types) would accept a variant of it?
3. Demonstrate let-polymorphism's edge: in OCaml, `let id = fun x -> x in (id 1, id "a")` works but `(fun id -> (id 1, id "a")) (fun x -> x)` doesn't. Map each to §6.1's generalization rule.
4. Write the three smallest Rust programs that each violate exactly one rule: use-after-move, two `&mut`, borrow outliving owner. For each, identify what the affine/region analysis computed, using the compiler's own error text as evidence.
5. Monomorphization vs. erasure, empirically: compile a Rust generic used at three types and find the three symbols (`nm` or `cargo asm`); then check Java's single erased method via `javap -c`. One sentence each: who pays, and when?

---

## Chapter 7 — Intermediate Representations and SSA

### 7.1 Why IRs exist

The AST is the wrong data structure for optimization: it's shaped like *source* (nested, named, syntactic) when optimizers need *flow* (what computes what, what reaches where). So compilers **lower** the tree into an IR built around explicit, atomic operations and explicit control flow. The classic shape is **three-address code** organized into **basic blocks** (straight-line instruction runs with one entry and one exit) connected by jumps into a **control-flow graph (CFG)**:

```
// while (i < n) { sum = sum + i; i = i + 1; }   lowers to:
bb0:  jump bb1
bb1:  t0 = i < n
      branch t0 → bb2, bb3
bb2:  sum = sum + i
      i   = i + 1
      jump bb1
bb3:  ...
```

Real compilers run a *tower* of IRs, each lowering discarding source detail and exposing machine detail: rustc goes AST → **HIR** (desugared source: `for` loops become `loop`+`match` on iterators) → **MIR** (the CFG above; where borrow checking and Rust-specific optimization run) → **LLVM IR** → machine code. The design rule of thumb: each analysis runs at the *highest* level that still expresses what it needs — borrow checking needs Rust's reference semantics (MIR), vectorization needs machine-ish operations (LLVM IR), and "unused variable" warnings need the AST.

### 7.2 SSA: the representation that made modern optimization

**Static Single Assignment** form adds one constraint: **every variable is assigned exactly once**; re-assignments become new numbered versions (`i1`, `i2`, …). Where control flow merges, a **φ (phi) node** selects the version by incoming edge:

```
bb1:  i1 = φ(i0 from bb0, i2 from bb2)        // loop header merges entry + back edge
      sum1 = φ(sum0 from bb0, sum2 from bb2)
      t0 = i1 < n
      branch t0 → bb2, bb3
bb2:  sum2 = sum1 + i1
      i2 = i1 + 1
      jump bb1
```

Why this bookkeeping transformed the field: in SSA, **def-use chains are the representation itself**. "Who computes the value `sum2` uses?" — exactly one place, by construction; no reaching-definitions dataflow needed. Constant propagation becomes "if `x1 = 5`, substitute 5 at `x1`'s uses"; dead-code elimination becomes "no uses → delete"; value numbering becomes hash-consing. A generation of optimizations that each required bespoke iterative dataflow analyses collapsed into near-graph-rewrites — which is why **every serious optimizer is SSA-based** (LLVM, GCC's GIMPLE, V8's TurboFan/Turboshaft, HotSpot's C2, Go's SSA backend, Cranelift). Constructing SSA efficiently (placing φs only where needed, at **dominance frontiers**) is the one classical algorithm here; you should know it exists and what dominance means (block A dominates B if every path to B passes A — the CFG's "happens-before"), and let [Cytron et al.] stay a citation.

### 7.3 Reading LLVM IR

LLVM IR is the lingua franca and worth being able to read — typed, SSA, with explicit memory:

```llvm
define i64 @sumto(i64 %n) {
entry:
  br label %loop
loop:
  %i   = phi i64 [ 0, %entry ], [ %i2, %loop ]      ; SSA versions + φ
  %sum = phi i64 [ 0, %entry ], [ %sum2, %loop ]
  %sum2 = add i64 %sum, %i
  %i2   = add i64 %i, 1
  %done = icmp eq i64 %i2, %n
  br i1 %done, label %exit, label %loop
exit:
  ret i64 %sum2
}
```

The reading keys: `%locals` are SSA values (registers without limit — Ch. 9's register allocator maps them to the real eight-to-thirty-one); memory is *explicit* (`alloca` stack slots, `load`/`store` — and the **mem2reg** pass's whole job is promoting memory back into SSA values, which is why `-O0` output is full of loads/stores and `-O1` output isn't); types are everywhere; and undefined behavior has first-class citizens (`undef`, `poison`) — Ch. 8 explains why the optimizer *wants* UB representable. Generate your own with `clang -emit-llvm` or `rustc --emit=llvm-ir` and diff `-O0` against `-O2` once; it permanently changes what "the compiler optimized it" means to you.

### Exercises 7

1. Lower by hand: `if (a > b) { m = a; } else { m = b; } return m * 2;` — first to a CFG of three-address code, then to SSA with the φ placed correctly. Verify against `clang -O1 -emit-llvm` for the equivalent C.
2. Why does a loop need φs at its *header* and not in its body? Construct the smallest loop where a φ in the wrong block gives a wrong answer.
3. Compile a five-line function at `-O0` and run just mem2reg (`opt -passes=mem2reg f.ll -S`). Count `alloca`/`load`/`store` before and after; describe what the pass proved about each promoted variable.
4. Dump rustc's MIR for a function with a `for` loop (`cargo rustc -- --emit=mir` or the Rust Playground's MIR button). Find: the desugared iterator protocol, the CFG blocks, and one `StorageLive`/`StorageDead` pair — what is the *latter* bookkeeping for (hint: Ch. 6.2)?

```quiz
Q: Why is the AST the wrong data structure for optimization?
- [x] It's shaped like source (nested, named, syntactic) while optimizers need flow (what computes what, what reaches where) — so compilers lower it into an IR of atomic operations in basic blocks connected by a control-flow graph
- [ ] It's too small to hold optimization metadata
- [ ] ASTs can't represent loops
- [ ] It loses type information
> Real compilers run a tower of IRs (rustc: AST → HIR → MIR → LLVM IR), each lowering exposing more machine detail. The rule: run each analysis at the highest level that still expresses what it needs.

Q: What does Static Single Assignment (SSA) form give optimizers "for free"?
- [x] Def-use chains *are* the representation — every variable is assigned once, so "who computes this value?" has exactly one answer, collapsing constant propagation, DCE, and value numbering into near-graph-rewrites
- [ ] Faster register allocation
- [ ] Automatic parallelization
- [ ] Type checking
> Before SSA, each optimization needed bespoke iterative dataflow analysis. SSA is why every serious optimizer (LLVM, GCC GIMPLE, TurboFan, HotSpot C2, Go's backend) is SSA-based. φ-nodes select the right version where control flow merges.

Q: At `-O0` LLVM IR is full of `alloca`/`load`/`store`; at `-O1` they're gone. What happened?
- [x] The mem2reg pass promoted memory back into SSA values — proving each stack variable could live in a register instead of memory
- [ ] The optimizer inlined the loads
- [ ] -O1 disables memory safety checks
- [ ] The linker removed them
> mem2reg is the gateway: most optimizations operate on SSA values, not memory traffic. That's why diffing -O0 against -O2 LLVM IR permanently changes what "the compiler optimized it" means.
```

---

## Chapter 8 — Optimization

### 8.1 The contract: as-if, and UB as license

An optimizer may do anything that preserves the program's **observable behavior** (the "as-if" rule) — and the definition of "observable" is where languages diverge consequentially. In C, C++, and Rust, **undefined behavior is not observable behavior**: an execution containing UB has *no* defined semantics, so the optimizer may assume UB never happens and transform accordingly. This is not compiler-writer malice; it is the mechanism by which UB *buys performance*. The canonical example: signed overflow is UB in C, therefore `for (int i = 0; i <= n; i++)` lets the compiler assume `i` never wraps, therefore the trip count is computable, therefore the loop can be unrolled/vectorized — the same loop with `unsigned i` (defined wraparound) genuinely optimizes worse. The infamous corollaries follow from the same logic: a null check *after* a dereference is deleted (the dereference "proved" non-null — UB otherwise), and `if (x + 1 > x)` folds to `true` for signed `x`. Once you see optimizations as *theorems derived from the language's axioms*, "the compiler broke my code" reliably decodes to "my code asserted an axiom I didn't mean" — and `-fsanitize=undefined` is the tool that finds the assertion.

### 8.2 The catalog, as IR transformations

Each classic optimization is a small rewrite on Ch. 7's SSA, shown here in before/after spirit:

- **Constant folding & propagation**: compute at compile time (`x = 3*4` → `x = 12`), substitute known constants through def-use chains, cascading (folding exposes more folding). With branches: **sparse conditional constant propagation** folds `if (false)` arms away entirely.
- **Dead code elimination (DCE)**: no uses → delete; unreachable blocks → delete. Mostly valuable as the *janitor* for other passes — inlining and folding leave corpses, DCE sweeps.
- **Common subexpression elimination / GVN**: same operands + same operation = same value; compute once. In SSA this is value numbering — hash `add(%a,%b)` and reuse. The reason you don't hand-hoist `a[i]*b[i]` repeats.
- **Inlining** — *the* enabling optimization: replace a call with the callee's body. Its direct win (call overhead) is minor; its real product is **context** — after inlining, constants flow into the body, branches on arguments fold, the abstraction tax of small functions drops to zero (this is why "many small functions" is free in optimized builds, and why C++/Rust iterator chains compile to loops: each closure inlines into the loop skeleton, then folding/DCE dissolve the scaffolding — "zero-cost abstraction" *is* inlining plus cleanup). The cost is code growth, hence heuristics (size budgets, call-site hotness) and the attribute escape hatches (`#[inline]`, `__attribute__((always_inline))`).
- **Loop optimizations**: **LICM** (loop-invariant code motion — hoist computations that don't change per iteration, including bounds-check components); **unrolling** (replicate the body to amortize branch overhead and expose ILP); **vectorization** (rewrite element-at-a-time loops into SIMD lanes — the highest-payoff and most fragile transformation: one may-alias pointer or cross-iteration dependence and the vectorizer declines; `-Rpass=loop-vectorize` / `-Rpass-missed` makes clang *tell you why*, a criminally underused flag); strength reduction (multiply-by-index → running add).
- **Scalar replacement / SROA and escape analysis**: prove an aggregate or allocation never escapes, then dissolve it into SSA values entirely — the pass that makes "allocate a small struct per iteration" free in Rust/C++ and (as escape analysis) lets JVMs stack-allocate objects.

Two systemic truths complete the picture. **Phase ordering**: passes enable each other (inline → fold → DCE → now another inline is attractive…), there is no optimal order, and real pipelines (`opt -O2` is literally a list of ~100 passes) are tuned by benchmark archaeology. And **alias analysis is the silent gatekeeper**: nearly every reordering needs "do these pointers overlap?", the answer is usually "maybe," and "maybe" kills the transformation — this is why Fortran beat C at numerics for decades (no aliasing by rule), why `restrict` and Rust's `&mut`-noalias guarantee matter materially, and why so many "the compiler should obviously…" complaints end at a may-alias edge.

### 8.3 Beyond single-module: LTO and PGO

Inlining stops at what the compiler can see, and separate compilation traditionally blinds it at file boundaries — **link-time optimization** (`-flto`) defers optimization until the whole program is visible (cross-module inlining, dead-global elimination), for link-time cost. **Profile-guided optimization** closes the other gap — the compiler's guesses about hotness: run an instrumented build on representative input, recompile with real branch/call frequencies; typical single-digit-to-teens percent on branchy server code, and the same data JITs get *for free* by construction — which is the bridge to Chapter 12: a JIT is a compiler whose PGO run is the program's own execution, continuously.

### Exercises 8

1. On Compiler Explorer: write a C function summing `0..n` with `int i` vs. `unsigned i` at `-O2` and diff the assembly. Find the transformation the UB enabled. Then add `-fwrapv` and watch it disappear.
2. Demonstrate inlining-as-enabler: a `square(x)` helper called as `square(3) + square(k)` — show at `-O2` that one call became a constant and the other became a multiply, with no `call` anywhere. Then `__attribute__((noinline))` it and count what returns.
3. Get the vectorizer to talk: a float-array loop with `-O3 -Rpass=loop-vectorize`, then break it three ways (potential aliasing via two pointer params; a cross-iteration dependency; an early-exit branch) and read `-Rpass-missed`'s explanation for each.
4. Write the multiply-shift strength-reduction table empirically: compile `x*2`, `x*7`, `x*9`, `x/2` (signed!), `x%8` at `-O2` and explain each emitted sequence — the signed-division one is subtler than it looks.
5. Run a small CPU-bound program under PGO (clang: `-fprofile-instr-generate` → run → `-fprofile-instr-use`) and measure. Then write one sentence on why V8 doesn't need this flag.

```quiz
Q: `for (int i = 0; i <= n; i++)` vectorizes better than the same loop with `unsigned i`. Why?
- [x] Signed overflow is UB in C, so the compiler may assume `i` never wraps, making the trip count computable; unsigned wraparound is *defined*, so it must emit code correct for the wrap case
- [ ] Signed integers are faster on x86
- [ ] The vectorizer rejects unsigned types
- [ ] Unsigned loops can't be unrolled
> Optimizations are theorems derived from the language's axioms. UB *buys* performance by letting the optimizer assume it never happens — and "the compiler broke my code" decodes to "my code asserted an axiom I didn't mean." -fsanitize=undefined finds it.

Q: Why is inlining called "the enabling optimization" when call overhead is minor?
- [x] Its real product is context — after inlining, constants flow into the callee, branches on arguments fold, and the abstraction tax of small functions drops to zero; "zero-cost abstraction" IS inlining plus folding/DCE cleanup
- [ ] It eliminates the stack frame
- [ ] It's the only optimization that touches loops
- [ ] It reduces binary size
> This is why "many small functions" is free in optimized builds and why C++/Rust iterator chains compile to loops — each closure inlines into the loop skeleton, then folding/DCE dissolve the scaffolding. The cost is code growth, hence size-budget heuristics.

Q: A loop the vectorizer "should obviously" optimize declines silently. What's the most common silent gatekeeper?
- [x] Alias analysis — nearly every reordering needs "do these pointers overlap?", the answer is usually "maybe," and "maybe" kills the transformation; restrict and Rust's &mut-noalias exist to answer it
- [ ] The optimization level is too low
- [ ] The loop has too many iterations
- [ ] Floating-point is disabled
> This is why Fortran beat C at numerics for decades (no aliasing by rule). -Rpass-missed makes clang explain *why* it declined — a criminally underused flag. Phase ordering is the other systemic truth: passes enable each other with no optimal order.
```

---

## Chapter 9 — Code Generation

### 9.1 From infinite registers to sixteen

The backend's three jobs, in order: **instruction selection** (map IR operations to machine instructions — mostly pattern-matching over the IR DAG, where the interesting wins are fused patterns: multiply-add → `lea` or FMA, compare-and-branch fusion), **instruction scheduling** (order operations to keep the CPU's pipelines fed — less critical on modern out-of-order cores, still alive for in-order and GPU targets), and the star of the chapter, **register allocation**: the IR has unlimited SSA values; the machine has ~16 general-purpose registers; map the former onto the latter, **spilling** the overflow to stack slots.

The classical formulation is elegant: build an **interference graph** (one node per live range; an edge where two ranges are simultaneously live), and **color it with k colors** (k = number of registers) — adjacent nodes get different colors, colors are registers, and if the graph won't k-color, pick a node to spill and retry (Chaitin's algorithm). Graph coloring is NP-complete in general, but the heuristics are excellent and this is what AOT compilers' top tiers descend from. The pragmatic alternative — **linear scan** — sorts live ranges by start point and greedily assigns, in near-linear time, at a few-percent code-quality cost: which is exactly the trade a JIT wants, and why baseline/mid-tier JIT compilers (and Cranelift, and LLVM's `-O0`) allocate this way while `-O2` does the expensive thing. The visible artifact of allocation pressure in any disassembly: spill/reload pairs (`mov [rsp+24], rax` … `mov rax, [rsp+24]`) — when a hot loop is full of them, the function has more live values than the machine has names, and the *source-level* fix is usually reducing simultaneously-live temporaries.

### 9.2 Calling conventions: the ABI as treaty

A **calling convention** is the contract that lets separately-compiled functions interoperate: where arguments go (System V x86-64: first six integer args in `rdi rsi rdx rcx r8 r9`, floats in `xmm0–7`, the rest on the stack; returns in `rax`), who saves which registers (**caller-saved** registers may be clobbered by any call — the caller stashes them if it cares; **callee-saved** must be restored — the callee stashes them if it uses them; allocation interacts with this constantly), and how stack frames are laid out (return address, saved frame pointer, locals, alignment rules). This treaty is most of what "ABI" means, it is per-OS-per-architecture (Windows x64 differs from System V), and it is why FFI (the [Advanced Rust guide](ADVANCED_RUST_STUDY_GUIDE.md)'s Part 9) is a *binary* discipline, not just a header-file one. Two downstream facts worth wiring in: **tail calls** (a call in return position can reuse the frame — `jmp` instead of `call`; guaranteed in Scheme, opportunistic in LLVM, famously absent from CPython by design) and **the frame walk** (how debuggers and unwinders climb the stack — and why omitting frame pointers for one extra register made profilers' lives miserable for a decade until `-fno-omit-frame-pointer` came back into fashion).

### Exercises 9

1. Read a real frame: compile a recursive factorial at `-O0`, disassemble, and annotate every prologue/epilogue instruction (push, mov, sub) with its §9.2 role. Then at `-O2` — what happened to the frame, and which optimization did it (hint: it's also in Ch. 8)?
2. Force spills: write a function with ~20 simultaneously-live `int` temporaries, compile at `-O2`, and find the spill slots. Reduce liveness (restructure into phases) and watch them disappear.
3. From a Compiler Explorer disassembly of `f(a,b,c,d,e,f,g)` on x86-64 Linux, label each argument's location, and explain which registers the callee saved and why those.
4. Demonstrate tail-call optimization: a tail-recursive sum in C at `-O2` becomes a loop (find the `jmp`); the non-tail version doesn't. Then explain in two sentences why CPython refuses this on principle (tracebacks).

---

## Chapter 10 — Linking and Loading

### 10.1 The last compiler nobody studies

Compilation of each source file ends in an **object file**: machine code and data in named **sections** (`.text`, `.data`, `.rodata`, `.bss`), a **symbol table** (names this file defines and names it needs), and **relocations** — "patch this placeholder with the final address of symbol X when you know it." The **linker** merges sections, resolves every undefined symbol to exactly one definition, applies relocations, and emits the executable. That's the whole job, and it's where a distinct class of errors lives: `undefined reference` (you declared but never linked the definition — a *linker* error, which is why the compiler happily produced your `.o`), duplicate symbols and C++'s **ODR** violations (two definitions that differ — UB at link granularity, the classic source of "works in debug, crashes in release" when headers drift), and the archaeology of **name mangling** (C++/Rust encode types and modules into symbol names — `_ZN3foo3barEi`; `c++filt`/`rustfilt` decode them; `extern "C"` exists precisely to *not* mangle, which is why it's the FFI handshake).

Two link-time behaviors explain chronic build mysteries. **Static archive semantics**: linking against `.a` archives pulls in only the members that resolve currently-undefined symbols, *in command-line order* — the ancient "it works if I list the libraries twice / in the other order" bug. **Why C++ template-heavy objects are huge**: every TU instantiates the templates it uses (Ch. 6's monomorphization), so twenty `.o` files each contain `std::vector<int>`'s methods; the linker deduplicates (weak/COMDAT symbols) but compile time and object size already paid — the mechanism behind both C++ build-time pain and the `-ffunction-sections -Wl,--gc-sections` diet (and LTO, Ch. 8.3, which moves the dedup-and-optimize into the link).

### 10.2 Dynamic linking and loading

Dynamic libraries (`.so`/`.dylib`/`.dll`) defer resolution to **load time**: the executable records dependencies (`ldd` lists them), the **dynamic loader** (`ld.so` — itself the interpreter named in the ELF header, `PT_INTERP`) maps them and resolves symbols at startup. Cross-library calls indirect through the **PLT/GOT** (procedure linkage table / global offset table): the first call through a PLT entry triggers lazy resolution, then the GOT slot caches the real address — one extra indirect jump per cross-library call forever after, which is the measurable cost of dynamic linking (and what `-fno-plt`, `LD_BIND_NOW`, and protected visibility tune). The same machinery enables the ecosystem's tricks: `LD_PRELOAD` interposition (your malloc wrapper wins symbol resolution), ASLR (everything is position-independent code anyway), `dlopen` plugins, and the versioned-symbol dance behind "glibc version `GLIBC_2.34` not found." Static-vs-dynamic is therefore a real trade, not a fashion: static (Go's default, Rust mostly) buys deployment simplicity and LTO reach at the price of binary size and library-update-requires-rebuild; dynamic buys shared memory pages and centralized security updates at the price of startup work, version skew, and the dependency archaeology this section equips you to do.

### Exercises 10

1. Produce and read the artifacts: compile two C files separately, run `nm` on each `.o` (find `U` vs `T` symbols), `objdump -r` for the relocations, link, and confirm the relocation got patched (`objdump -d` the final binary).
2. Manufacture each classic error: an undefined reference; a duplicate symbol; an ODR violation that *links fine* (two TUs, same inline function name, different bodies) — and explain why the third is the dangerous one.
3. Trace lazy binding live: a program calling `puts`, `objdump -d` the PLT stub, then run under `LD_DEBUG=bindings` and find the moment of resolution. Re-run with `LD_BIND_NOW=1`.
4. Use `LD_PRELOAD` to interpose `malloc` with a counting wrapper on a real program. Explain, in symbol-resolution terms, why your definition won.
5. Measure the template tax: a C++ file using `std::map<std::string,int>` — compile, and count the instantiated symbols in the object (`nm -C | grep std::map`). Add a second TU using the same map; verify the duplication, then watch the final binary contain one copy.

---

## Chapter 11 — Interpreters and Bytecode VMs

### 11.1 Two interpreter architectures

A **tree-walking interpreter** executes the AST directly — `eval(node)` recursing over children. It's the natural first implementation (Crafting Interpreters' first half; Ruby pre-1.9; many template engines and DSLs today) and the slowest: every operation pays pointer-chasing through heap-allocated nodes, dynamic dispatch on node type, and re-traversal of structure that never changes. The standard upgrade compiles the AST once into **bytecode** — a linear array of instructions for a virtual machine — and runs a tight dispatch loop over it. Linearization is most of the win: instruction fetch becomes array indexing with hot, contiguous, cache-friendly code, and the structure-walking cost is paid once at compile time.

The lab VM, completing Calc — a **stack machine** (operands push/pop on an evaluation stack; the alternative, register VMs like Lua's, trades fewer-but-fatter instructions):

```python
# Compiler: AST → (code, consts);  ops: PUSH,LOAD,STORE,ADD,MUL,LT,JMP,JF,PRINT
def compile_expr(node, code, consts):
    tag = node[0]
    if tag == "num":
        consts.append(node[1]); code += [("PUSH", len(consts)-1)]
    elif tag == "var":   code += [("LOAD", node[1])]
    elif tag == "binop":
        compile_expr(node[2], code, consts); compile_expr(node[3], code, consts)
        code += [({"+":"ADD","*":"MUL","<":"LT"}[node[1]], None)]

def run(code, consts):
    stack, env, pc = [], {}, 0
    while pc < len(code):
        op, arg = code[pc]; pc += 1
        if   op == "PUSH":  stack.append(consts[arg])
        elif op == "LOAD":  stack.append(env[arg])
        elif op == "STORE": env[arg] = stack.pop()
        elif op == "ADD":   b, a = stack.pop(), stack.pop(); stack.append(a + b)
        elif op == "MUL":   b, a = stack.pop(), stack.pop(); stack.append(a * b)
        elif op == "LT":    b, a = stack.pop(), stack.pop(); stack.append(a < b)
        elif op == "JF":    pc = arg if not stack.pop() else pc
        elif op == "JMP":   pc = arg
        elif op == "PRINT": print(stack.pop())
```

This *is* CPython's architecture in miniature: `compile()` produces a code object (bytecode + constants + names), `ceval.c` runs the dispatch loop, and `dis.dis` shows you instructions that map one-to-one onto this toy's (`LOAD_FAST`, `BINARY_OP`, `POP_JUMP_IF_FALSE`). Run `dis` next to the lab VM once and the mapping locks in.

### 11.2 Why interpretation is slow, and the pre-JIT remedies

The dispatch loop's costs, in order: **dispatch overhead** (one indirect branch per VM instruction — historically hard for branch predictors; the classic remedy is *computed gotos / threaded code*, giving each opcode its own jump and the predictor per-opcode history — CPython uses it where the compiler allows, for double-digit-percent wins), **operand boxing** (every Calc/Python value is a heap object with a type tag — `a + b` on boxed floats is allocate-check-unbox-add-rebox; mainstream VMs shrink this with *tagged pointers* and *NaN-boxing*, packing small ints/floats into the pointer word itself), and **generic operations** (`BINARY_OP` must ask "what types?" every single time, though the answer is the same at this site for the millionth consecutive run).

That last observation — *per-site type stability* — is the seam where modern CPython mines its speed without a full JIT: the **specializing adaptive interpreter** ([PEP 659](https://peps.python.org/pep-0659/), Python 3.11's headline ~25%) rewrites hot bytecode in place to specialized variants (`BINARY_OP` → `BINARY_OP_ADD_FLOAT`; `LOAD_ATTR` → a version that caches the attribute's location) with cheap inline guards that fall back when the assumption breaks. Run `dis.dis(f, adaptive=True)` after calling `f` in a loop and watch the instructions have *changed* — the interpreter is observing your program and editing itself, which is precisely the JIT idea (Ch. 12) stopping one step short of machine code.

### Exercises 11

1. Finish the lab: compile `while` (backpatch the `JF`/`JMP` targets) and run a loop summing 0..99. Then implement the same program as a tree-walker and benchmark the two on 10⁷ iterations.
2. Mirror it in CPython: `dis` the equivalent Python loop and produce a two-column table matching every CPython opcode to your VM's.
3. Demonstrate specialization: a function adding floats in a loop; `dis.dis(f, adaptive=True)` before and after 1,000 calls. Then call it once with strings and dis again — find the de-specialization.
4. Measure dispatch: add a `NOP`-padding option to the lab VM (every real op emits one NOP after it) and benchmark — you've isolated dispatch overhead from work. Estimate the per-instruction cost in ns.
5. Why can't `env` be a Python dict in a *fast* VM? Sketch the slot-numbering fix (Ch. 4's resolver output) and implement `LOAD_SLOT n` — measure the win even in this toy.

---

## Chapter 12 — JIT Compilation

The chapter the topics sketch promised would change how you write hot loops. A JIT is a compiler whose profile data is the program's own execution: it watches, specializes for what it saw, and — the part that makes it an engineering discipline rather than a trick — *undoes* its bets when they go bad.

### 12.1 The tiered architecture

Modern VMs are **tiered**, because startup and peak speed want opposite compilers. **V8**'s ladder: **Ignition** (bytecode interpreter — also the profiler: it records, per call site and per operation, what types and targets it actually sees) → **Sparkplug** (baseline compiler: mechanical bytecode→machine-code transliteration, no IR, no optimization — exists purely because even dumb machine code beats dispatch overhead ~5×) → **Maglev** (mid-tier: SSA, the cheap high-value optimizations) → **TurboFan** (the optimizing tier: full SSA optimization fed by the recorded **type feedback**, emitting code specialized to observed reality). **HotSpot** runs the same play with different names (interpreter → C1 with profiling → C2/Graal), with method-entry and loop-back-edge counters deciding promotion, and **on-stack replacement (OSR)** handling the awkward case of a hot *loop* inside a once-called method — swapping to compiled code *mid-loop*, reconstructing the interpreter's state into the compiled frame's layout.

The economics: each tier costs more to compile into and runs faster; the VM spends compile time only where running time concentrates. The numbers that make it intuitive — a function may run thousands of times in Ignition before Sparkplug touches it, and only the top sliver of hot code ever earns TurboFan — most code in a real app runs *forever* in the cheap tiers, and that's the correct allocation.

### 12.2 Hidden classes and inline caches: the heart of dynamic-language speed

The problem: in JavaScript (and Python and Ruby), `obj.x` is semantically a hash lookup — objects are dictionaries. Hash lookups per property access would cap the language at interpreter speed forever. The solution — descending from Smalltalk and the Self project, the research lineage V8 industrialized — has two halves:

**Hidden classes (V8: *maps*; the literature: *shapes*).** Although the language says "dictionary," real programs create objects in stereotyped ways. So the VM secretly maintains *classes* for them: an empty `{}` gets shape S0; adding `x` transitions to S1 ("has x at slot 0"); adding `y` to S2 ("x at 0, y at 1"). Every object created by the same constructor path marches through the same transition chain and ends at the same shape, holding its properties in *fixed slots* like a C struct. Property names map to offsets *in the shape*, once — not in each object, per access.

**Inline caches (ICs).** Each property-access *site* remembers the shapes it has seen and the offset each implies. The first execution of `return p.x` does the slow lookup, then caches "(shape S2 → slot 0)" *at that site*. Every later execution checks the incoming object's shape against the cache — one compare — and loads the slot directly: dictionary semantics at struct prices. Sites are **monomorphic** (one shape seen — the fast path: TurboFan will inline the access as compare-and-load), **polymorphic** (a few shapes — a small linear dispatch), or **megamorphic** (many shapes — the site gives up and does hash lookups forever).

Now the performance folklore decodes into mechanism, which was the sketch's promise:

- *"Initialize all properties in the constructor, in the same order"* — objects built identically share a shape; conditional or variably-ordered property addition forks the transition chain, and downstream sites go polymorphic.
- *"Don't add properties after construction / don't `delete`"* — late addition transitions shapes (and `delete` typically demotes the object to actual-dictionary mode, the worst case).
- *"`obj[key] = value` with dynamic keys in a hot loop is slow"* — dynamic keys defeat the entire mechanism: no per-site stable shape+offset to cache. A `Map` is the honest data structure for that access pattern, and now you know *why*.
- *"Keep arrays packed and same-typed"* — arrays have element-kind shapes too (packed small-int → packed double → generic, a one-way ratchet per array); writing `1.5` into an int array, or punching a hole, permanently de-specializes its element accesses.

CPython's 3.11+ specializing interpreter (Ch. 11.2) is this same idea — per-site caches keyed on observed types — implemented inside an interpreter; the concept is universal across dynamic-language VMs.

### 12.3 Speculation and deoptimization: the license to cheat

Type feedback makes TurboFan/C2 *speculative* compilers: "this site has only ever seen two Smis; compile an integer add and **guard** it." The guard is the crucial half — a cheap runtime check (shape compare, small-int tag check) that, on failure, triggers **deoptimization**: throw away the optimized frame, *reconstruct the interpreter's state* (every live variable mapped back to bytecode-level locations — the bookkeeping that makes speculation safe is most of its implementation cost), and resume in the interpreter, updating the feedback so the next compile is less naive. Speculation is why JITs beat AOT on dynamic languages (an AOT compiler must emit code correct for *all* inputs; a JIT emits code correct for *observed* inputs plus an escape hatch) — and deopt churn is the failure mode: a site that keeps deopting and recompiling ("deopt loops") runs slower than never optimizing. `node --trace-deopt` names the function, the reason (`wrong map`, `not a Smi`), and the bailout site; reading its output on your own hot function is the single most instructive half hour in this chapter. The same architecture explains HotSpot's famous behaviors: aggressive inlining through megamorphic-looking call sites *because* class-hierarchy analysis says only one implementation is loaded — with an **uncommon trap** deopt if a new class ever loads and falsifies the assumption. The JVM speculates on the *world*, not just on values.

### 12.4 The wider JIT landscape

**Method JITs** (V8, HotSpot, .NET RyuJIT) compile function-at-a-time, as above. **Tracing JITs** (LuaJIT, PyPy) record a *hot loop's actual executed path* — across function boundaries — into a linear trace, optimize that straight line ruthlessly (no merge points = perfect knowledge), and guard every place the trace could diverge: spectacular on tight loops, fragile on branchy code (trace explosion). **Meta-tracing** (PyPy/RPython, GraalVM's partial evaluation) generates the JIT *from the interpreter* — write a Python interpreter, get a Python JIT — which is how PyPy stays compatible with a moving language. And **CPython's own JIT** (3.13+, experimental): a **copy-and-patch** design — precompiled machine-code templates per micro-op, stitched and patched at runtime — chosen explicitly for low engineering cost and maintainability over peak performance; modest gains so far, architecturally significant as the end of "Python will never have a JIT." The honest cross-cutting trade: JITs buy peak speed with warmup, memory (bytecode + profiles + multiple compiled copies), and complexity; AOT buys predictability and instant start. Hence the hybrid era: AOT for serverless cold starts (GraalVM native-image), JIT for long-running servers, and profile-guided AOT (Ch. 8.3) as the meeting point.

### Exercises 12

1. Watch the ladder: run a hot numeric function under `node --trace-opt` and identify each tier promotion. Add `%OptimizeFunctionOnNextCall` (with `--allow-natives-syntax`) to force it, and `%GetOptimizationStatus` to interrogate it.
2. Cause and read a deopt: optimize a two-Smi add loop, then pass `0.5`, then a string, under `--trace-deopt`. For each, write down the guard that failed in §12.3's vocabulary.
3. Demonstrate shape discipline empirically: benchmark summing `.x` over a million objects — (a) all constructed identically, (b) half constructed with properties in swapped order, (c) keys assigned dynamically. Explain the three numbers with monomorphic/polymorphic/megamorphic.
4. Demonstrate the array-kind ratchet: fill an array with ints, benchmark a sum; write one `1.5` into it; re-benchmark. Find the V8 element-kind documentation that names what happened.
5. Compare the philosophies in one experiment: the same numeric loop in CPython 3.13 (`PYTHON_JIT=1` if available), PyPy, and Node. Relate the three results to method-vs-tracing-vs-copy-and-patch and to warmup.

```quiz
Q: Why are modern VMs tiered (V8: Ignition → Sparkplug → Maglev → TurboFan)?
- [x] Startup and peak speed want opposite compilers — cheap tiers run immediately and profile; only the hot sliver of code earns the expensive optimizing tier, so compile time is spent only where running time concentrates
- [ ] Each tier targets a different CPU
- [ ] Older tiers exist for backward compatibility
- [ ] More tiers always means faster code
> Most code in a real app runs forever in the cheap tiers, which is the correct allocation. A function may run thousands of times in the interpreter before the baseline compiler touches it.

Q: How do hidden classes + inline caches turn `obj.x` from a hash lookup into struct-speed access?
- [x] The VM gives objects built the same way a shared *shape* with properties in fixed slots; each access site caches "(shape → offset)" so later executions are one shape-compare plus a direct slot load
- [ ] It precomputes every possible property at startup
- [ ] It converts objects to arrays
- [ ] It caches the value, not the offset
> "Initialize all properties in the constructor, same order" makes objects share a shape (monomorphic sites — fast). Conditional/reordered property addition forks the transition chain; dynamic keys defeat the mechanism entirely (use a Map).

Q: What makes a JIT's speculation safe, and what's the failure mode?
- [x] Each speculative assumption is protected by a cheap guard that, on failure, triggers deoptimization — reconstructing interpreter state and resuming; the failure mode is deopt loops, where a site keeps deopting and recompiling slower than never optimizing
- [ ] Speculation never fails if types are consistent
- [ ] Guards are checked only at compile time
- [ ] Deoptimization restarts the whole program
> Speculation is why JITs beat AOT on dynamic languages: AOT must be correct for all inputs, a JIT for *observed* inputs plus an escape hatch. node --trace-deopt names the function, reason, and site — the most instructive half hour in the chapter.

Q: HotSpot aggressively inlines through a call site with only one loaded implementation, then adds an "uncommon trap." What is it speculating on?
- [x] The *world* — class-hierarchy analysis says only one implementation is loaded, so it inlines; if a new class ever loads and falsifies the assumption, the uncommon trap deoptimizes
- [ ] The argument values
- [ ] The available registers
- [ ] The garbage collector's state
> The JVM speculates on the world's shape, not just on values — a strictly more powerful (and more fragile) bet than value speculation. It's why JVM peak performance is famously good and famously warmup-dependent.
```

---

## Chapter 13 — Garbage Collection and Memory Runtimes

### 13.1 The problem and the two classical answers

A runtime must reclaim unreachable memory. **Reference counting** (CPython, Swift/ARC, Rust's `Rc`) frees at the instant the last reference drops — deterministic, incremental by nature, and broken by **cycles** (two objects referencing each other never hit zero; CPython runs a separate generational *cycle collector* on top of refcounting for exactly this, and Swift answers with `weak`/`unowned` — the same strong-edges-vs-back-edges discipline as the [Advanced Rust guide](ADVANCED_RUST_STUDY_GUIDE.md)'s `Weak`). Its hidden costs are write traffic (every pointer assignment mutates two counts — cache-line pings; this, plus the GIL story, is why CPython's counts were a multicore problem and why 3.12+ *immortal objects* and biased counting exist). **Tracing** (everything else): start from **roots** (stacks, registers, globals), walk the object graph, and everything unreached is garbage — collecting cycles for free, deferring all cost to collection time.

The tracing family tree, by what they do with survivors: **mark-sweep** (mark reachable, sweep the rest onto free lists — no moving, fragments over time), **mark-compact** (slide survivors together — defragments, costs a second pass and pointer fixups), **copying/semispace** (copy survivors to a fresh space — allocation becomes pointer-bump, cost proportional to *live* data only, at 2× space). The performance-defining empirical fact is the **generational hypothesis**: most objects die young. So real collectors split the heap: a small **nursery** collected often with a copying collector (cheap — most of it is dead, and you only touch survivors), and a **tenured** space for objects that survive promotion, collected rarely with mark-sweep/compact. The price of the split is the **write barrier**: an old object pointing at a young one would be invisible to a nursery-only trace, so *every pointer store* runs a tiny check recording old→young edges (card tables, remembered sets) — a few percent on all mutator writes, buying order-of-magnitude cheaper collections. Barriers are the reason "GC overhead" exists even between pauses, and the hook on which all concurrent collection hangs.

### 13.2 The modern problem: pauses, and the concurrent answers

Stop-the-world collection scales pauses with heap size — unacceptable at multi-GB heaps and millisecond SLOs — so modern collectors run **concurrently with the mutator**, which immediately raises the correctness problem: the graph mutates *while being traced*. The classical framework is **tri-color marking** (white = unvisited, gray = found-not-scanned, black = scanned): collection is complete when no gray remains, and the invariant that must hold is *no black→white pointer without a gray protector* — which a mutator can violate in one assignment. Write barriers again, now as invariant-keepers: snapshot-at-the-beginning or incremental-update barriers intercept the dangerous stores. Production geography: **V8/Orinoco** (parallel nursery scavenging, concurrent marking, incremental everything — browser frame budgets drove it), **HotSpot G1** (region-based, pause-target-driven, the default), **ZGC/Shenandoah** (the low-latency end: concurrent *relocation* via colored pointers/forwarding, pauses in the ~millisecond range nearly independent of heap size — trading throughput via load barriers on reads), and **Go's GC** (concurrent mark-sweep, non-moving, tuned monomaniacally for low pause at the cost of throughput and compaction — a *values-first language* needs less from its GC, which is the next point).

### 13.3 GC pressure is a language-design and program-design variable

The collector you need depends on the garbage you make. Languages with **value types** (Go structs, C#/Java's incoming value classes, Rust's everything-by-default) let data live in stacks, arrays, and registers — no header, no trace, no barrier; JVM-style "everything is a heap object" maximizes allocation rate and pointer density, then asks heroic collectors to cope (and **escape analysis** — Ch. 8's SROA at the JIT level — to quietly un-heap what it can prove local). The program-level corollaries you can act on this week: allocation *rate* drives GC cost more than heap *size* (the per-request `[]byte` in the hot path is a nursery tax — pools and buffer reuse attack exactly this); object *pointer density* drives trace cost (a `[]struct` traces as one slab; a `[]*struct` is a pointer chase per element — the same struct-of-arrays instinct as cache optimization, because the GC is just another graph walker); and **finalizers are not destructors** (they run late, maybe never, on a GC thread — resource cleanup belongs to deterministic constructs: `defer`, `with`, `try-with-resources`, RAII).

### Exercises 13

1. Demonstrate CPython's two-tier reality: create a reference cycle with `__del__`-free objects, show refcounting alone leaks it (`gc.disable()`, `gc.get_count()`), then `gc.collect()` it. Then give it `__del__` and read what changed in `gc.garbage` semantics across Python versions.
2. Observe generational behavior in V8 or the JVM: allocate short-lived objects in a loop under `node --trace-gc` (or `-Xlog:gc`) and identify nursery collections vs. major ones; then retain everything in a global list and watch promotion change the log's shape.
3. Write the write-barrier cost experiment in Go: sum over `[]T` vs `[]*T` (same data) with GC forced (`runtime.GC()` between runs, `GODEBUG=gctrace=1`). Attribute the difference between mutator and GC time.
4. Trigger and fix allocation-rate pressure: a Go or Java hot loop allocating a buffer per iteration vs. a reused/pooled buffer — compare GC logs, not just latency. Which §13.3 lever did you pull?
5. Explain, in tri-color terms, the exact race a concurrent collector without write barriers loses: give the three-object, two-step interleaving where a live object is freed.

```quiz
Q: Reference counting frees deterministically. What's its defining weakness and how do refcounting languages cope?
- [x] Cycles — two objects referencing each other never hit zero; CPython runs a separate generational cycle collector on top, Swift uses weak/unowned (strong edges vs back edges)
- [ ] It's slower than tracing for all workloads
- [ ] It can't free large objects
- [ ] It requires stop-the-world pauses
> Refcounting also has hidden write traffic (every pointer assignment mutates two counts — cache-line pings), which plus the GIL is why CPython's counts were a multicore problem (hence immortal objects, biased counting). Tracing collects cycles for free by deferring cost to collection time.

Q: What empirical fact justifies generational garbage collection, and what does the split cost?
- [x] The generational hypothesis — most objects die young — so a small nursery is collected often and cheaply (only survivors are touched); the price is the write barrier on every pointer store, recording old→young edges
- [ ] Old objects are larger, so they're collected separately
- [ ] It eliminates fragmentation entirely
- [ ] The split removes the need for roots
> Write barriers are why "GC overhead" exists even between pauses — a few percent on all mutator writes, buying order-of-magnitude cheaper collections. They're also the hook on which all concurrent collection hangs (tri-color invariant keeping).

Q: How is GC pressure a program-design variable you can act on this week?
- [x] Allocation *rate* drives GC cost more than heap *size* (per-request buffers are a nursery tax — pool them), and pointer *density* drives trace cost (a []struct traces as one slab; a []*struct is a pointer-chase per element)
- [ ] Only the runtime author can affect GC cost
- [ ] Bigger heaps always mean slower GC
- [ ] Finalizers reliably free resources promptly
> The struct-of-arrays instinct helps the GC for the same reason it helps cache — the collector is just another graph walker. And finalizers are not destructors: they run late, maybe never; deterministic cleanup belongs to defer/with/RAII.

Q: Why does a value-types language (Go, Rust) need less from its garbage collector than "everything is a heap object" (classic JVM)?
- [x] Value types let data live in stacks, arrays, and registers — no header, no trace, no barrier — so allocation rate and pointer density drop, where JVM-style heaps maximize both and ask heroic collectors (plus escape analysis) to cope
- [ ] Value types are reference counted
- [ ] They don't need a GC at all
- [ ] Their objects are smaller
> Go's GC is tuned monomaniacally for low pause at the cost of throughput and compaction precisely because a values-first language makes less garbage. Escape analysis (the JIT's SROA) quietly un-heaps what it can prove local.
```

---

## Chapter 14 — The Real Compilers, Toured

Theory attached to the four systems you most likely touch, each chosen because it embodies one architectural thesis.

### 14.1 CPython: the transparent interpreter

The full pipeline, every stage importable (Ch. 1.3): PEG parser (Ch. 3) → AST (`ast`) → symbol tables (`symtable`, Ch. 4) → bytecode compiler with small peephole optimizations (`dis`, Ch. 11) → the `ceval.c` dispatch loop with adaptive specialization (Ch. 11.2) → refcounting + cycle GC (Ch. 13.1), with the experimental copy-and-patch JIT (Ch. 12.4) and free-threading both arriving via the same modernization push. The thesis CPython embodies: **simplicity and introspectability as product features** — the implementation is readable C, every stage is exposed to Python code, and the C-API's stability constraints (refcounts in the ABI!) are the honest reason "just add a JIT/remove the GIL" took thirty years — the lesson being that an implementation's *compatibility surface*, not its algorithms, is usually what petrifies it.

### 14.2 tsc: a checker wearing a compiler costume

TypeScript's compiler is architecturally upside-down by this guide's pipeline: scanner → parser (never rejects — error-tolerant trees for the IDE, Ch. 3.3) → **binder** (Ch. 4's resolution) → **checker** (the overwhelming bulk: structural subtyping, narrowing, inference — Ch. 5) → emitter that mostly *erases* (types vanish; downleveling old targets is the only real codegen). There is no IR, no optimizer, no SSA — JavaScript engines own performance; tsc owns *judgment*. Two architectural facts worth knowing: the checker is substantially **lazy** (types computed on demand, cached — why `--noEmit` type-checking dominates build time and why the **language service** can answer hover/completion queries on a dirty file in milliseconds), and the same codebase *is* the IDE backend (tsserver) — tsc is the clearest industrial proof that a "compiler" can be primarily an analysis engine, and that error-tolerance (Ch. 3) is a first-class architectural requirement, not polish.

### 14.3 rustc: the tower of IRs, queried

rustc is the guide's Ch. 6–8 made flesh: AST → **HIR** (desugared; type inference and trait resolution here) → **THIR/MIR** (the CFG where **borrow checking** runs as dataflow — Ch. 6.2 — along with Rust-aware optimization and monomorphization) → LLVM IR → machine code. Its two distinctive theses: **put each analysis on the right IR** (the borrow checker needed a CFG, so they built MIR — most languages never give their mid-level semantics a first-class representation), and the **query system** — the compiler is structured not as sequential passes but as memoized queries (`type_of(def_id)`, `borrowck(def_id)`) with automatic dependency tracking, which is what makes **incremental compilation** sound (a change re-executes only invalidated queries) and what rust-analyzer shares conceptually. The cost ledger is honest too: monomorphization + LLVM at `-O2` + the query graph's bookkeeping = the compile times Rust is famous for; the [rustc dev guide](https://rustc-dev-guide.rust-lang.org/) documents all of it with unusual candor.

### 14.4 LLVM and the contrast case, Go

**LLVM** is the thesis "a shared, typed, SSA middle-end is a public good": frontends (clang, rustc, swiftc, Zig…) buy decades of optimization and every backend for the price of emitting IR — the reason new AOT languages are viable as small projects at all. The costs that come with the purchase: compile time (the pass pipeline is heavy), a C-centric semantic bias that other languages must encode around (UB flavors, aliasing models), and a moving API. **Go** is the deliberate counter-position: a from-scratch compiler with its own SSA backend, modest optimization, and a fanatical compile-speed/simplicity budget — because Go's designers priced developer iteration time above the last 10–20% of runtime performance, and *the build experience itself was a language goal*. Put side by side, rustc-on-LLVM and Go are the cleanest demonstration that compiler architecture is product strategy: the same textbook chapters, weighted by different values, produce visibly different tools.

### Exercises 14

1. For one ten-line function, collect the artifact at every rustc stage: `--emit=hir,mir,llvm-ir,asm` (Playground or cargo). Annotate where inference, borrow checking, monomorphization, and vectorization each happened.
2. Use tsserver like the IDE does: open a TypeScript file with a deliberate type error mid-function and confirm (in any editor) that completion still works *below* the error. Name the two Ch. 3/14.2 design decisions that made that possible.
3. Demonstrate rustc's incrementality: `touch` vs. meaningful-edit a leaf function in a medium crate with `CARGO_INCREMENTAL=1` and compare rebuild times; explain in query terms.
4. Read one real pass: pick LLVM's `InstCombine` description (or one rule in its source) and write the before/after IR for one peephole it performs. Cite the Ch. 8 category it belongs to.

---

## Chapter 15 — Where to Go Next

**The build-one path** (the highest-value path): finish what the lab started — [*Crafting Interpreters*](https://craftinginterpreters.com/) end to end (tree-walker in Java, bytecode VM with GC in C; the second half is the best VM-internals text ever written at any price), then Thorsten Ball's [*Writing an Interpreter/Compiler in Go*](https://interpreterbook.com/) for a second reps-building pass, then the [LLVM Kaleidoscope tutorial](https://llvm.org/docs/tutorial/) to bolt a real backend onto your own frontend.

**The optimize-one path**: Cornell [CS 6120](https://www.cs.cornell.edu/courses/cs6120/2020fa/self-guided/) (build passes over a teaching IR — SSA, DCE, LICM, with autograded homework), then the *SSA Book* ([free draft](https://pfalcon.github.io/ssabook/latest/book-full.pdf)) when you want the theory load-bearing, with Cooper & Torczon as the reference shelf (the Dragon Book is historically important and pedagogically obsolete for self-study — parsing-heavy in exactly the proportion modern practice isn't).

**The runtime path**: Mara Bos-grade sources for VMs are blogs and talks — the [V8 blog](https://v8.dev/blog) (shapes/ICs/Maglev/Orinoco posts are chapter-quality), JVM internals via [Aleksey Shipilëv's writings](https://shipilev.net/) (JMM, GC, benchmarking methodology), *The Garbage Collection Handbook* (Jones et al.) as the GC bible, and PyPy/GraalVM papers for the meta end.

**The professional path**: read production compiler code guided by its own docs — the [rustc dev guide](https://rustc-dev-guide.rust-lang.org/) is the gold standard of compiler-internals documentation; tsc's [architecture wiki](https://github.com/microsoft/TypeScript/wiki/Architectural-Overview) and CPython's [internals docs](https://devguide.python.org/internals/) follow. And keep the habit this guide tried to install: **Compiler Explorer open in a tab, `dis`/`--emit` one keystroke away, every performance claim taken to the tool**. The single sentence to retain: a language is a UI over a pipeline of representations, and once you can name the representation a behavior lives in — token, tree, type, IR, machine code, runtime — you can predict it, measure it, and when necessary, defeat it.

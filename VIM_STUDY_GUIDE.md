# Vim Study Guide

A practical, depth-first guide to Vim for engineers who want to edit text at the speed of thought. It assumes you've used a normal editor (VS Code, an IDE, Notepad) but have never gotten past the "how do I even quit this thing" stage of Vim — or that you've used it for years by muscle memory without ever learning the *system* underneath. The approach is deliberately not a command list. Vim's commands number in the thousands, and memorizing them flat is hopeless and pointless. Instead this guide teaches Vim as what it actually is: **a small language for editing, where a handful of verbs and nouns compose into a near-infinite vocabulary of edits you never explicitly learned.** Get the grammar and the rest falls out.

The throughline is the question in the title: *why is this faster than a traditional editor?* The answer has three parts, and every chapter reinforces them — your hands never leave the home row, you express editing **intent** ("change inside the quotes") instead of **mechanism** (mouse-select the text, delete, retype), and repetitive edits collapse into a single keystroke through repeat, registers, and macros. Once those click, going back to click-and-drag feels like typing with mittens on.

The single best first step is not this guide — it's running **`vimtutor`** from your terminal (30 minutes, ships with Vim). Then come back here for the depth. Other references worth keeping open: Vim's own peerless built-in docs via `:help` (mirrored at [vimhelp.org](https://vimhelp.org/)), Drew Neil's [*Practical Vim*](https://pragprog.com/titles/dnvim2/practical-vim-second-edition/) (the best book on the subject), and the [Neovim docs](https://neovim.io/doc/) if you go the modern-fork route. This guide covers Vim, with Neovim differences flagged where they matter; ~95% applies identically to both. Where Vim shows up in your daily tools — the default Git commit editor, `git mergetool` — the [Git guide](GIT_STUDY_GUIDE.md) is a useful companion.

---

## Table of Contents

1. [Part 1 — Why Modal Editing](#part-1--why-modal-editing)
2. [Part 2 — The Modes in Depth](#part-2--the-modes-in-depth)
3. [Part 3 — The Grammar of Editing](#part-3--the-grammar-of-editing)
4. [Part 4 — Motions](#part-4--motions)
5. [Part 5 — Text Objects](#part-5--text-objects)
6. [Part 6 — Changing Text & Registers](#part-6--changing-text--registers)
7. [Part 7 — Search & Substitute](#part-7--search--substitute)
8. [Part 8 — Macros](#part-8--macros)
9. [Part 9 — Files Windows & Ex Power](#part-9--files-windows--ex-power)
10. [Part 10 — Configuration & Speed Recipes](#part-10--configuration--speed-recipes)

A note on notation: keystrokes are shown in `code font`. `<Esc>`, `<CR>` (Enter/Return), and `<C-a>` (Control-a) follow Vim's own help convention. In before/after examples, `█` marks the cursor position. "Type `ciw`" means press those three keys in Normal mode, in sequence — not all at once.

---

## Part 1 — Why Modal Editing

Before any keystroke, get the model right. Almost everything that frustrates beginners — "it beeped at me," "my text got replaced," "I'm trapped" — comes from one root misunderstanding: treating Vim like a normal editor that has weird shortcuts, instead of a fundamentally different machine that happens to also edit text.

### The Problem Modal Editing Solves

In a traditional editor, every key on the keyboard has one job: **insert that character.** Press `d` and you get a "d" in your document. So every *command* — copy, delete a word, jump to the end of the line — has to be expressed some other way: a modifier chord (`Ctrl`, `Alt`, `Cmd`), a menu, or the mouse. Two consequences follow, and both cost you speed:

1. **Your hands leave the home row constantly** — reaching for arrow keys, `Home`/`End`, `Page Up`, or the mouse. Every reach is a few hundred milliseconds and a break in flow.
2. **Editing is mechanical, not intentional.** To change the text inside a pair of quotes you *aim the mouse, click before the first character, drag carefully to the last, release, delete, then type.* That's five physical operations to express one idea.

Here's the insight Vim is built on: **when you're working with existing code, you spend far more time navigating and restructuring it than typing brand-new characters.** So Vim inverts the default. Most of the time the keyboard is a *command surface* — every key manipulates text — and when you actually want to insert characters, you switch into a mode for that. The cost is that you must always know which mode you're in. The payoff is everything else in this guide.

### Vim Is a Language, Not a List of Shortcuts

This is the most important idea in the guide, so it gets said plainly: **Vim commands compose like words in a sentence.** There are **verbs** (operators: delete, change, yank) and **nouns** (motions and text objects: a word, the inside of parentheses, to the end of the line). You combine them:

- `d` (delete) + `w` (a word) → `dw` — "delete word"
- `c` (change) + `i(` (inside parentheses) → `ci(` — "change inside parens"
- `y` (yank) + `$` (to end of line) → `y$` — "copy to end of line"

You learn perhaps **thirty primitives** and get **thousands of combinations** — most of which you never explicitly studied. The first time you need to "delete inside a quoted string," you *derive* `di"` from `d` + `i"` without anyone teaching you that specific command, because the grammar is consistent. A traditional editor gives you a flat, unrelated list — `Ctrl+Shift+K` deletes a line, and there's no logic connecting it to anything else, so you memorize each one in isolation and forget the rare ones. Vim's combinatorial grammar is *why* it scales to thousands of edits without thousands of memorizations. **Spend your learning effort on the grammar (Part 3), and the rest composes itself.**

### The Modes, and the Map Between Them

Vim has a handful of modes. You'll live in the first two; the rest are specialized.

- **Normal mode** — the home base, and the mode Vim starts in. Every key is a command: move, delete, change, paste, search. Counterintuitively, *this* is where you spend most of your time, with your fingers resting and ready. New users flee it; experts return to it after every small edit.
- **Insert mode** — what a traditional editor is always in. Keys insert characters. You enter it deliberately, do a focused burst of typing, and leave immediately.
- **Visual mode** — select a region (by character, line, or block), *then* act on it. The "I want to see exactly what I'm affecting" mode.
- **Command-line mode** — entered with `:` (Ex commands like `:w`, `:s`), `/` or `?` (search). For file operations, search-and-replace, and bulk edits across ranges.
- **Replace mode** — typing overwrites existing characters instead of inserting. Niche.
- **Operator-pending mode** — a brief, almost invisible mode you're in *between* pressing an operator and its motion (the moment after `d`, waiting for the `w`). You don't think of it as a mode, but it's the conceptual engine behind the whole grammar.

```text
                 i a o I A O s c ...
        ┌────────────────────────────────►┌──────────────┐
        │                                  │  INSERT mode  │
        │              <Esc>               │ (type text)   │
        │   ◄──────────────────────────────└──────────────┘
 ┌──────┴───────┐  v V <C-v>   ┌──────────────┐
 │  NORMAL mode │ ───────────► │  VISUAL mode  │
 │ (commands —  │  ◄────────── │ (select then  │
 │  home base)  │    <Esc>     │   operate)    │
 └──────┬───────┘              └──────────────┘
        │  :  /  ?      ┌────────────────────┐
        │ ────────────► │  COMMAND-LINE mode │
        │  ◄─────────── │ (:w :s /search ... )│
        │   <CR>/<Esc>  └────────────────────┘
        ▼
   (everything returns to Normal — when in doubt, press <Esc>)
```

The golden rule for survival: **when you're lost, press `<Esc>` (or `<C-[>`) until you're back in Normal mode**, then think. Everything radiates from Normal.

### Why It's Actually Faster

Four compounding reasons, each developed later in the guide:

1. **Zero travel.** Commands are letter keys, so your hands never leave the home row — no arrow keys, no `Home`/`End`, no mouse. Navigation that costs a hand-reach elsewhere costs a finger-twitch here.
2. **Intent over mechanism.** "Change what's inside these quotes" is a single thought and a single command, `ci"`. You don't tell Vim *how* to select the text; you tell it *what you mean*. The editor does the aiming.
3. **Effortless repetition.** The `.` command repeats your last change; counts like `3dd` multiply a command; registers store snippets; macros record and replay whole sequences. Repetitive edits that are a tedious slog in a traditional editor collapse to one or two keystrokes (Parts 6–8).
4. **It's everywhere.** Vim is on every server you'll SSH into, it's the default editor for Git, and every serious IDE and editor has a high-quality Vim mode (Part 10). Learn it once; the skill follows you to every environment for the rest of your career.

### Surviving Your First Session

Enough to not feel trapped, so you can practice the rest:

| You want to… | Press |
|---|---|
| Start typing text | `i` (insert before cursor) |
| Stop typing, return to commands | `<Esc>` |
| Undo / redo | `u` / `<C-r>` |
| Save | `:w<CR>` |
| Save and quit | `:wq<CR>` or `ZZ` |
| Quit, discarding changes | `:q!<CR>` |
| Open the built-in tutorial | run `vimtutor` in your shell |

Set your expectations honestly: for the **first few days you will be slower** than your old editor — that's the tax, and it's real. Within a week you're functional; within a month you're faster than you were before; and from there the advantage compounds for years because the skill never stops deepening. The people who quit do so in the first three days. Don't.

If you remember one thing from Part 1: **Vim is a language for editing, not a set of shortcuts.** Learn the grammar and you stop memorizing commands — you start *speaking* edits.

---

## Part 2 — The Modes in Depth

Part 1 mapped the modes; this part lives in each one. The recurring theme: **you enter the specialized modes deliberately and return to Normal quickly.** Time spent in Normal mode is time spent ready to act.

### Normal Mode: Home Base

Normal mode is where Vim starts and where you should return after every edit. Here, the alphabet is a command set. You don't need it all at once, but notice the *shape* — single keys do a lot:

- Move: `h j k l` (left, down, up, right), `w`/`b` (word forward/back), `0`/`$` (line start/end), `gg`/`G` (file top/bottom). Full treatment in Part 4.
- Edit: `x` (delete char), `d`/`c`/`y` (delete/change/yank — operators, Part 3), `p` (paste), `r` (replace one char), `u` (undo).
- Enter other modes: `i a o` (insert), `v V <C-v>` (visual), `:` `/` (command-line), `R` (replace).

The mindset shift that separates beginners from the fluent: **the resting state of your hands is Normal mode, not Insert mode.** A fluent user makes an edit, hits `<Esc>`, and sits in Normal mode reading and navigating — dipping into Insert only for the actual keystrokes of new text. Beginners do the opposite: they live in Insert mode and treat Vim like Notepad with extra steps, forfeiting the entire benefit.

### Insert Mode: Get In, Type, Get Out

Insert mode is ordinary typing. The art is in *how you enter it*, because choosing the right entry command saves a navigation step. There are eight common doors, and picking the right one is a real speed habit:

| Command | Enters insert… | Use when |
|---|---|---|
| `i` | before the cursor | the default "insert here" |
| `a` | after the cursor (append) | adding to the right of the current char |
| `I` | at first non-blank of line | prepend to a line of code |
| `A` | at end of line | the most-used one — append to a line |
| `o` | on a new line below | adding a new line of code |
| `O` | on a new line above | inserting a line above |
| `gi` | where you last left insert mode | resume editing where you were |
| `s` / `S` | deleting char / whole line first | replace-and-retype (these are `cl` / `cc`) |

The difference between `i` and `A`, or `o` versus pressing `<Esc>`-then-arrow-down-then-typing, is the difference between one keystroke and four. **Leaving** insert mode is `<Esc>` — or `<C-[>`, which many remap to a home-row key (`jk`, Caps Lock) because reaching for the far-away `<Esc>` is the one ergonomic wart in the design. While in insert mode you also get a few power keys without leaving: `<C-w>` deletes the previous word, `<C-u>` deletes to the start of the line, `<C-r>{reg}` inserts a register (Part 6), and `<C-n>`/`<C-p>` autocomplete words from the file (Part 10).

The discipline: **don't navigate in insert mode** with arrow keys. Hit `<Esc>`, move with a real motion, re-enter. It feels pedantic for a day and becomes invisible after that.

### Visual Mode: Select, Then Operate

Visual mode reverses Vim's usual order. Normally you say verb-then-noun (`d` then `w`); in Visual you select the noun first (watching it highlight), then press the verb. It exists for the cases where you can't easily express the target as a motion, or you just want to *see* the selection before acting. Three flavors:

- **`v` — charwise:** select character by character. `vee` selects two words; press `d` to delete the selection or `c` to change it.
- **`V` — linewise:** select whole lines. `Vjj` selects three lines; `>` indents them, `d` deletes them.
- **`<C-v>` — blockwise:** select a rectangular column block. This is the one with no equivalent in most editors and a genuine superpower — covered with examples in Part 10 (insert text on 50 lines at once, edit a column of a table).

Inside Visual mode: `o` jumps the cursor to the *other* end of the selection (extend the side you got wrong without restarting), `gv` reselects your last visual selection, and any operator (`d c y > < u U ~ =`) acts on the highlighted region. A subtle but huge one: after selecting lines with `V`, pressing `:` pre-fills the command line with the range `:'<,'>` so your next Ex command applies exactly to the selection (Part 7).

When *should* you use Visual mode versus a plain operator+motion? Use an operator when you can name the target (`ci(`, `d}`) — it's faster and **repeatable with `.`**. Reach for Visual when the boundary is irregular, when you want to confirm visually, or for blockwise edits. Over-reliance on Visual mode for things that have a clean text object is a common intermediate plateau.

### Command-Line Mode: The Ex Heritage

Pressing `:` drops to the command line, where Vim's older line-editor ancestor (`ex`) lives. This is where file operations and bulk transformations happen: `:w` (write), `:q` (quit), `:e file` (edit a file), `:s` (substitute), `:g` (global). These commands take **ranges** — `:10,20d` deletes lines 10–20, `:%s/…/…/g` substitutes across the whole file — which makes them devastatingly efficient for sweeping edits (Parts 7 and 9). `/` and `?` are technically command-line mode too, for forward and backward search. A quality-of-life trick: `q:` opens the **command-line window**, a normal buffer of your command history you can edit and re-run with `<CR>` — Vim editing its own command line.

### Replace and the Invisible Operator-Pending Mode

Two to round out the set:

- **Replace mode (`R`)** overtypes: each character you type replaces the one under the cursor, like the old `Insert` key. Niche — handy for fixed-width tables or ASCII art. `r{char}` replaces just a single character without entering a mode at all.
- **Operator-pending mode** is the one you never named but use constantly. The instant you press an operator like `d`, Vim enters operator-pending mode and *waits* for a motion or text object to tell it the extent. Press `w` and it completes as `dw`. This tiny waiting state is the hinge of the entire grammar — it's why `d` + any noun works, including text objects (`diw`), counts (`d3w`), and even searches (`d/foo<CR>` deletes up to the next "foo"). Understanding that operators open a "now name the target" prompt is understanding Vim.

(Neovim and modern Vim also have a **Terminal mode** for the built-in `:terminal`, and there's a rarely-used **Select mode** that mimics traditional select-and-replace for snippet plugins. Neither is worth dwelling on now.)

If you remember one thing from Part 2: **enter the specialized modes on purpose and leave them fast.** Your home is Normal mode; Insert is a quick errand, not a place to live.

---

## Part 3 — The Grammar of Editing

This is the heart of the guide. Parts 4–8 are vocabulary; this part is the grammar that makes the vocabulary explode into fluency. If Part 1 convinced you Vim is a language, this is the sentence structure.

### The Sentence: Operator + Motion

Most Vim edits follow one pattern:

```text
[count] operator [count] motion-or-text-object
```

An **operator** (verb) says *what to do*; a **motion or text object** (noun) says *to what*. The operator acts on exactly the text the motion would cover. So:

- `d` + `w` = `dw` — delete from cursor to the start of the next word.
- `c` + `$` = `c$` — change from cursor to end of line (delete it and enter insert mode).
- `y` + `}` = `y}` — yank from cursor to the next blank line.
- `>` + `G` = `>G` — indent from this line to the end of the file.

This is composition, and it's *predictable*: any operator pairs with any motion. You don't memorize `dw`, `cw`, `yw`, `d$`, `c$`, `y$` as six separate commands — you learn three operators and a handful of motions and get all the combinations free. That's the leverage.

### The Verbs (Operators)

The operators you'll use constantly:

| Operator | Action |
|---|---|
| `d` | **delete** (and copy into a register) |
| `c` | **change** — delete, then enter Insert mode |
| `y` | **yank** (copy) |
| `>` / `<` | **indent** right / left |
| `=` | **auto-indent** (reformat indentation) |
| `gu` / `gU` / `g~` | lowercase / uppercase / toggle case |
| `gq` / `gw` | **format** (re-wrap) lines to text width |
| `!` | **filter** through an external shell command |

`p`/`P` (put/paste), `x` (delete char), `r` (replace char), and `~` (toggle case) aren't operators in the formal sense — they don't take a motion — but they're core editing verbs you'll lean on (Part 6).

### The Nouns: Motions vs. Text Objects

There are two kinds of noun, and the distinction matters:

- **Motions** describe *movement* — they cover the text *between* where the cursor is and where the motion lands. `w`, `$`, `}`, `G`, `/foo<CR>`. They're directional and depend on cursor position. (Part 4.)
- **Text objects** describe *structure* — a complete syntactic unit regardless of where in it the cursor sits: a word (`iw`), the inside of quotes (`i"`), a parenthesized group (`a(`), an HTML tag's contents (`it`). They come in **inner** (`i`) and **around** (`a`) variants. (Part 5.)

The practical difference: a motion like `dw` deletes *from the cursor* forward, so the result depends on where you started. A text object like `diw` deletes *the whole word* the cursor is anywhere inside — position-independent. Text objects are what make Vim feel like it reads your mind, and they're the single biggest "faster than a traditional editor" lever, which is why they get their own chapter.

### Counts Multiply

A **count** before a command repeats the motion or operator. It can go before the operator, before the motion, or both (the two multiply):

- `3w` — move forward 3 words.
- `2dd` — delete 2 lines.
- `d3w` — delete 3 words.
- `3d2w` — delete 6 words (3 × 2).
- `5j` — down 5 lines; `10G` or `:10` — go to line 10.

Counts turn "do this a few times" into a single command, no repetition needed.

### Doubling an Operator Goes Linewise

A useful special case: **type an operator twice and it acts on the whole current line.** This is how you operate on lines without a motion:

- `dd` — delete the current line.
- `cc` — change the current line (clear it, keep indent, enter Insert).
- `yy` — yank the current line.
- `>>` — indent the current line.
- `guu` / `gUU` — lower/uppercase the line.

With a count: `3dd` deletes three lines, `2yy` yanks two. (`d` doubled is `dd`; the second `d` stands in for "the line" as the motion.)

### Reading Compositions Fluently

Put it together and you can read any of these at a glance — and, more importantly, *write the one you need* by composing parts you already know:

```text
ci(    change inside parentheses        — rewrite a function's arguments
da"    delete a double-quoted string    — including the quotes
yi{    yank inside braces               — copy a block's body
>ap    indent a paragraph
gUiw   uppercase the current word
d2j    delete this line and the 2 below (3 lines, linewise)
c/end  change everything up to the next "end"
=i{    reindent the contents of a block
gqip   re-wrap the current paragraph to text width
!ip sort   filter the paragraph through the `sort` shell command
```

None of these needed to be memorized individually. Each is just *verb + noun*. When you hit a new editing situation, the question is never "what's the command for this?" — it's "what's the verb, what's the noun?" and you assemble it.

If you remember one thing from Part 3: **edits are sentences — `operator + motion/text-object`, optionally multiplied by a count.** Learn the verbs and nouns separately, and every combination is yours without ever studying it.

## Part 4 — Motions

Motions move the cursor — and because any operator can take a motion (Part 3), **every motion you learn doubles as a way to delete, change, or yank.** Learn `}` to jump a paragraph and you've also learned `d}`, `c}`, `y}` for free. This part is about getting anywhere — in a line, a screen, or a file — without arrow keys or the mouse. The skill to build is **precision targeting**: reach your destination in as few keystrokes as possible, ideally one motion rather than a burst of repeated ones.

### Character and Word Motions

`h j k l` move left/down/up/right. They're on the home row so your fingers never move, but **mashing `l` ten times to cross a line is a beginner tell** — there's almost always a one-keystroke motion that gets you there. Use `hjkl` for tiny adjustments only.

Word motions are the workhorses of intra-line movement:

| Motion | Moves to |
|---|---|
| `w` / `W` | start of next word / WORD |
| `e` / `E` | end of next word / WORD |
| `b` / `B` | start of previous word / WORD |
| `ge` / `gE` | end of previous word / WORD |

The lowercase/uppercase distinction is **word vs. WORD**, and it's worth internalizing: a **word** is a run of letters/digits/underscores *or* a run of punctuation; a **WORD** is anything between whitespace. On the text `foo.bar_baz()`:

```text
foo.bar_baz()
│  ││      ││
w stops at: foo → . → bar_baz → ()      (punctuation breaks words)
W stops at: foo.bar_baz()                (one WORD — only whitespace breaks it)
```

So `dw` on `foo.bar` deletes just `foo`, while `dW` on `foo.bar baz` deletes `foo.bar`. Reach for WORD motions when you want to skip over punctuation-heavy tokens like file paths or `snake.case.chains` in one jump.

### Line-Internal Motions

| Motion | Moves to |
|---|---|
| `0` | first column (very start of line) |
| `^` | first non-blank character |
| `$` | end of line |
| `g_` | last non-blank character |
| `{n}\|` | column `n` |

`^` and `$` are the ones you'll wear out — start and end of the meaningful content. `d^`, `d$` (or its alias `D`), `c$` (alias `C`) follow directly.

### Find and Till: The Fastest Way Across a Line

This family is the secret to one-keystroke intra-line jumps, and beginners chronically underuse it:

| Motion | Moves to |
|---|---|
| `f{char}` | next `{char}` (cursor lands **on** it) |
| `F{char}` | previous `{char}` |
| `t{char}` | just **before** the next `{char}` (till) |
| `T{char}` | just after the previous `{char}` |
| `;` | repeat the last `f`/`t`/`F`/`T` |
| `,` | repeat it in the opposite direction |

To jump to the next comma, press `f,`. Need the one after? `;`. Combined with operators this is razor-sharp: on `hello(world, again)` with the cursor at the start, `df,` deletes up to **and including** the comma (`f` is *inclusive*), leaving ` again)`; `dt,` deletes up to but **not** including it. That inclusive/exclusive difference (next section) is exactly the `f` vs `t` choice.

### Moving Around the Screen and File

| Motion | Moves to |
|---|---|
| `gg` / `G` | first / last line of file |
| `{n}G` or `:{n}<CR>` | line `n` |
| `H` / `M` / `L` | **H**igh / **M**iddle / **L**ow line of the visible screen |
| `<C-d>` / `<C-u>` | down / up half a screen |
| `<C-f>` / `<C-b>` | forward / back a full screen |
| `zz` / `zt` / `zb` | scroll so the cursor line is centered / top / bottom |

`zz` deserves a callout: after jumping somewhere, `zz` recenters the view around your cursor so you can see context — a constant companion to search and `G`.

### Structural Motions

These jump by code/prose structure:

| Motion | Moves to |
|---|---|
| `}` / `{` | next / previous blank line (paragraph) |
| `)` / `(` | next / previous sentence |
| `%` | the matching bracket of the pair under/after the cursor — `()`, `[]`, `{}` |
| `[{` / `]}` | the unmatched enclosing `{` / `}` |
| `[(` / `])` | the unmatched enclosing `(` / `)` |
| `[[` / `]]` | previous / next section or function (language-dependent) |

`%` is indispensable for code: park on a `{` and `%` leaps to its closing `}` (and back). `d%` from an opening bracket deletes the whole bracketed span.

### Search as a Motion

Search isn't just navigation — it's a motion, so it composes with operators:

- `/pattern<CR>` jumps to the next match; `?pattern<CR>` searches backward.
- `n` / `N` repeat the search forward / backward.
- `*` / `#` search for the **exact word under the cursor**, forward / backward (a fantastic "find other uses of this variable" key); `g*` / `g#` do the same but match partial words too.
- As a motion: `d/foo<CR>` deletes everything from the cursor up to the next "foo"; `c/end<CR>` changes up to "end". You can even add an offset: `/foo/e` lands on the *end* of the match.

Search is often the *fastest* long-range motion: rather than count lines, `/uniqueword<CR>` teleports you straight there.

### Marks and Jumps: Teleporting Back

Vim remembers where you've been:

- **Marks:** `m{a-z}` drops a named mark at the cursor. `` `a `` jumps to that exact spot; `'a` jumps to the start of that line. So `ma`, wander off, `` `a `` to snap back. Uppercase marks (`mA`) work *across files*.
- **Automatic marks:** `` `. `` jumps to your last edit, `` `^ `` to where you last left insert mode, and `` `` `` (two backticks) jumps back to where you were *before* the last jump — toggle between two spots by pressing it repeatedly.
- **The jump list:** `<C-o>` goes **back** to your previous location (across searches, `G`, file switches), `<C-i>` goes **forward** again — like a browser's back/forward buttons for your cursor.
- **The change list:** `g;` / `g,` cycle through the places you recently changed.

For navigating a real codebase, `*` to find a symbol, `<C-o>` to retrace, and marks for "I'll be right back" are how you move without ever touching a scrollbar.

### Inclusive vs. Exclusive (and the `cw` Surprise)

A detail that explains otherwise-baffling results. Motions are either **inclusive** (the operator includes the character the motion lands on) or **exclusive** (it doesn't):

- **Inclusive:** `f` `t` `e` `$` `%` — e.g. `df.` includes the period.
- **Exclusive:** `w` `b` `0` `/` — e.g. `dw` stops *before* the next word's first character.

The famous wrinkle: **`cw` behaves like `ce`.** Logically `dw` deletes the word *and* the trailing space (it's a movement to the next word). But when *changing*, you almost never want to delete the space too, so Vim special-cases `cw` to act like `ce` — change to the end of the word, leaving the space. Don't fight it; it's the behavior you actually want. (For the position-independent "change the whole word from anywhere," prefer the text object `ciw` — next part.)

If you remember one thing from Part 4: **prefer one precise motion over many repeated ones** — `f`, `/`, `}`, `%`, and `{n}G` get you there in a keystroke, and each one instantly becomes a delete/change/yank when you put an operator in front of it.

---

## Part 5 — Text Objects

If motions are how you *move*, text objects are how you *grab structure* — and they are the single feature that makes experienced Vim users look like they're cheating. A text object selects a complete syntactic unit — a word, a quoted string, a parenthesized group, an HTML tag's contents — **no matter where inside it the cursor sits.** That position-independence is the whole point, and it's what a traditional editor's mouse-select can never match for speed.

### Inner vs. Around

Every text object comes in two forms:

- **`i` — inner:** the content *only*. `i"` is the text between the quotes, not the quotes.
- **`a` — around (a.k.a. "a"):** the content *plus* its delimiters (and, for words and paragraphs, the trailing whitespace). `a"` includes the quotes.

Mnemonic: **`i`nner** = inside, **`a`round** = all of it. You combine these with any operator: `ci"` (change inside quotes), `da(` (delete the parens and everything in them), `yi{` (yank a block's body), `vi"` (visually select inside quotes).

### The Catalog

| Text object | Selects |
|---|---|
| `iw` / `aw` | a word / a word + surrounding whitespace |
| `iW` / `aW` | a WORD / a WORD + whitespace |
| `i"` `i'` `` i` `` | inside the quotes (and `a"` etc. to include them) |
| `i(` `i)` `ib` | inside parentheses (`ab` = "a block" = `a(`) |
| `i{` `i}` `iB` | inside braces (`aB` = `a{`) |
| `i[` `i]` | inside square brackets |
| `i<` `i>` | inside angle brackets |
| `it` / `at` | inside an HTML/XML tag / the whole tag element |
| `ip` / `ap` | a paragraph / paragraph + trailing blank line |
| `is` / `as` | a sentence |

`ib`/`ab` (brackets/block) and `iB`/`aB` (Braces) are the same as `i(`/`a(` and `i{`/`a{` — shorter to type once they're in your fingers.

### Why This Is the Speed Lever

Here's the comparison that sells it. Say you have `const name = "old value";` and want to replace the string. In a traditional editor: aim the mouse, click just after the opening quote, drag to just before the closing quote (don't overshoot!), release, delete, type. In Vim, with the cursor **anywhere on that line**:

```text
const name = "old valu█e";
Type:  ci"
const name = "█";          (string contents gone, now in Insert mode — just type)
```

`ci"` is three keys, position-independent, and it doesn't matter how long the string is or where your cursor landed — Vim finds the quotes and operates between them. A few more that turn multi-step mouse operations into reflexes:

```text
Rewrite a function's arguments:
    foo(a, b█, c)        →  ci(  →  foo(█)              type new args

Delete an entire HTML element's contents, keep the tags:
    <p>hello █world</p>  →  cit  →  <p>█</p>            type new content

Delete the whole element including tags:
    <p>hello █world</p>  →  dat  →  █

Copy a whole block body to paste elsewhere:
    if (x) {             →  yi{  (cursor anywhere in the braces)
        do█Thing();
    }

Delete a paragraph and the blank line after it:
    ...some par█agraph... →  dap

Uppercase a word from anywhere in it:
    let my█Var = 1;      →  gUiw  →  let MYVAR... (well, gUiW for the whole token)
```

The mental motion is always the same: identify the **structure** you want (a string, a block, a tag, a paragraph), pick **inner or around**, and put a **verb** in front. You're describing *what* you mean and letting Vim do the selecting.

### Text Objects + Repeat + Search = Lightweight Refactoring

Text objects shine when combined with the `.` repeat (Part 6) and search (Part 7). To change every call `format(x)` to `render(x)`: search `/format(<CR>`, then `cwrender<Esc>` (or `ciwrender<Esc>`), then `n` to the next match and `.` to repeat the change — `n . n . n .` walks through the file applying the same edit. No find-and-replace dialog, full control over which ones you touch.

### Beyond the Built-ins

Two extensions worth knowing now (full plugin treatment in Part 10), because they *are* text-object thinking:

- **vim-surround** adds operations on the *delimiters* themselves: `cs"'` changes surrounding `"` to `'`, `ds(` deletes surrounding parentheses, and `ysiw"` wraps the current word in quotes. It treats "the surroundings" as something you can change, delete, and add — a natural extension of `i`/`a`.
- **Treesitter text objects** (Neovim) add *semantic* objects that understand your language's syntax tree: `if`/`af` for inner/around a **function**, `ic`/`ac` for a **class**, `ia`/`aa` for an **argument**. `cif` changes a whole function body; `daa` deletes an argument *and* its trailing comma. This is text objects graduating from "matching brackets" to "actual code structure."

If you remember one thing from Part 5: **stop selecting text and start naming structure.** `ci"`, `dap`, `cit`, `yi{` — describe the unit and the operation, and Vim finds the boundaries for you. This is the habit that makes editing feel telepathic.

---

## Part 6 — Changing Text & Registers

Parts 4–5 gave you nouns. This part is the verbs in daily practice — deleting, changing, copying, pasting — plus the two features that multiply them: **the `.` command** (repeat anything) and **registers** (where copied and deleted text actually goes). Master these and routine editing stops feeling like work.

### The Everyday Edit Verbs

Beyond the operators of Part 3, a set of single-key shortcuts handles the most common edits. Many are just an operator+motion fused into one key — knowing the expansion helps them stick:

| Key | Equivalent | Does |
|---|---|---|
| `x` / `X` | `dl` / `dh` | delete char under / before cursor |
| `D` | `d$` | delete to end of line |
| `C` | `c$` | change to end of line |
| `s` | `cl` | delete char, enter Insert ("substitute") |
| `S` | `cc` | clear line, enter Insert |
| `Y` | `yy`\* | yank line (\*Neovim defaults `Y` to `y$`) |
| `r{char}` | — | replace one character, no mode change |
| `~` | — | toggle case of the character, move right |
| `J` / `gJ` | — | join next line up (with / without a space) |

`J` is a small delight: it pulls the following line onto the current one with a single space, fixing up whitespace — `3J` joins three lines. `gJ` joins without adding the space.

### Put (Paste) and the Swap Tricks

`p` puts the last delete/yank **after** the cursor; `P` puts it **before**. The behavior depends on how the text was captured:

- **Charwise** (`yw`, `x`): inserted inline at the cursor.
- **Linewise** (`yy`, `dd`): inserted on a **new line** below (`p`) or above (`P`) — it never jams a line into the middle of another.

This linewise behavior powers two classic micro-edits:

```text
Swap two characters (cursor on first):   xp      teh → the
Swap two lines (cursor on first):        ddp
Duplicate the current line:              yyp
```

`{count}p` pastes multiple copies (`3p` pastes three times).

### Numbers: Increment and Decrement

`<C-a>` increments the number under or after the cursor; `<C-x>` decrements it. `10<C-a>` adds ten. Vim finds the next number on the line if the cursor isn't on one, and understands hex/binary too. The showstopper is the **visual-block version**: select a column and `g<C-a>` turns it into an *ascending sequence* — covered as a recipe in Part 10, it's how you number a list 1, 2, 3… in one command.

### The Dot Command: Repeat Anything

`.` repeats your **last change** — the most powerful single key in Vim, and the one that quietly does the most work. A "change" is any text modification: `dd`, `ciwfoo<Esc>`, `x`, `A;<Esc>`. After making one, `.` does it again at the new cursor position.

The **dot-repeat workflow** is a habit worth building deliberately: *make a small, self-contained change, move to the next spot, press `.`*. For example, to add a semicolon to the end of several lines:

```text
A;<Esc>     append a semicolon to this line, leave Insert
j           down to the next line
.           repeat "append a semicolon"  (one keystroke!)
j .  j .    keep going
```

Because `.` re-runs the *entire* change including the typed text, pairing it with a repeatable motion (`n` for searches, `;` for `f`/`t`, `j` for lines) lets you apply an edit across many locations while eyeballing each one. It's "find and replace" with a human in the loop, and it's faster to *start* than opening a replace dialog. (Well-written plugins like vim-surround even make *their* operations dot-repeatable.)

### Registers: Where Copied Text Lives

Every delete and yank goes into a **register** — a named clipboard. Vim has many, and understanding a few saves you from the #1 paste frustration.

- **The unnamed register `""`** holds the most recent delete or yank. Plain `p` pastes from it.
- **The yank register `"0`** holds *only the last yank* — crucially, **deletes don't touch it.** This solves the classic trap below.
- **The numbered ring `"1`–`"9`** holds recent *deletes*: `"1` is the newest, shifting down as you delete more. You can replay a series of deletes with `"1p` then `.` `.` (each `.` advances to the next numbered register — a neat trick).
- **Named registers `"a`–`"z`** are yours to assign explicitly. Prefix any yank/delete/paste with `"{letter}`: `"ayy` yanks the line into register `a`; `"ap` pastes it back. Use the **uppercase** name to **append**: `"Ayy` adds another line to register `a` — great for collecting scattered lines into one place.
- **The black hole `"_`** discards: `"_dd` deletes a line *without* overwriting the unnamed register.
- **The system clipboard `"+`** bridges to the OS: `"+y` copies to the system clipboard, `"+p` pastes from it. (On X11, `"*` is the primary selection.) Set `clipboard=unnamedplus` to make plain `y`/`p` use the OS clipboard by default.
- **Read-only registers:** `"%` (current filename), `".` (last inserted text), `":` (last command), `"/` (last search). And the **expression register `"=`** inserts computed values: in Insert mode, `<C-r>=2*21<CR>` types `42`.

`:registers` (or `:reg`) shows them all. To paste a register while in Insert mode without leaving it, `<C-r>{reg}` — e.g. `<C-r>0` inserts your last yank mid-type.

**The trap everyone hits, and the fix.** You yank a word (`yiw`), then delete some junk (`diw`), then paste (`p`) — and Vim pastes the *junk*, because the delete overwrote the unnamed register. Three fixes: (1) paste from the yank register, `"0p`, which the delete didn't touch; (2) delete into the black hole, `"_diw`, so your yank survives; or (3) in Visual mode, select and `p` over the target — though note that itself swaps text into the unnamed register.

### Undo, Redo, and Time Travel

- `u` undoes; `<C-r>` redoes. `U` undoes *all* recent changes on one line (and is itself undoable).
- Vim's undo is a **tree**, not a line — if you undo and then make a new change, the old branch isn't lost. `g-` and `g+` move backward and forward through *every* state in time order, and `:earlier 10m` / `:later 5m` jump by elapsed time (also `:earlier 50` by change count). You can recover work you thought a redo had buried.
- Enable **persistent undo** (`set undofile`) and the undo history survives closing and reopening the file — undo across sessions.

If you remember one thing from Part 6: **`.` is your repeat button and `"0`/`"_` keep your clipboard from betraying you.** Make changes small and repeatable so `.` can do the rest, and reach for the yank or black-hole register the moment a delete would clobber something you wanted to paste.

## Part 7 — Search & Substitute

Motions move you to one place; this part is about acting on **many** places at once. Search finds, `:substitute` rewrites, and the `:global` command — Vim's most powerful and least-known feature — runs any command on every line that matches a pattern. Together they turn "edit all the X's to Y" from a chore into a one-liner, and they're where Vim decisively out-paces a point-and-click editor.

### Search, Properly

`/pattern<CR>` searches forward, `?pattern<CR>` backward, `n`/`N` repeat forward/back, and `*`/`#` jump to the exact word under the cursor (Part 4). A few things that make search far more pleasant:

- **`incsearch`** (set it — default in Neovim) jumps to matches *as you type* the pattern.
- **`hlsearch`** highlights all matches; `:noh<CR>` clears the highlight when you're done.
- **`ignorecase` + `smartcase`** together is the magic combination: searches are case-insensitive *unless* you type a capital letter, in which case they become case-sensitive. `/error` matches anything; `/Error` matches only the capitalized form.

### Regex and "Very Magic" Mode

Vim's default regex dialect requires backslashes before many metacharacters (`\(`, `\+`, `\|`), which is noisy. Prefix a pattern with **`\v`** ("very magic") and the syntax becomes conventional, like most other regex engines:

```text
Default:   /\(foo\|bar\)\+
Very magic: /\v(foo|bar)+
```

Use `\v` whenever a pattern has groups or alternation. Other handy atoms: `\c`/`\C` force case-insensitive/sensitive for one search; `\<` and `\>` match word boundaries; and `\zs`/`\ze` set where the *match* starts/ends independent of what you required around it (so `/foo\zsbar` finds "bar" but only when preceded by "foo", leaving the cursor on "bar").

### Substitute: Search-and-Replace with Ranges

The `:substitute` command (`:s`) is find-and-replace, and its power is in the **range** prefix and the **flags** suffix:

```text
:[range]s/pattern/replacement/[flags]
```

The range says *which lines*, and this is the part worth memorizing cold:

| Range | Means |
|---|---|
| (none) | current line only |
| `%` | the whole file |
| `10,20` | lines 10–20 |
| `.,+5` | current line and the next 5 |
| `'<,'>` | the visual selection (auto-filled after you select with `V`) |
| `/start/,/end/` | from the next "start" line to the next "end" line |

The flags change behavior: **`g`** replaces *all* occurrences on each line (not just the first), **`c`** asks for **confirmation** on each (`y`/`n`/`a`/`q`), and **`i`** forces case-insensitive. So the canonical "replace everywhere, asking me each time":

```text
:%s/oldName/newName/gc
```

In the replacement you can reference capture groups (`\1`, `\2` — use `\v` in the pattern to write `(...)` cleanly), the whole match (`&`), and case switches (`\u` uppercases the next char, `\U` until `\E`). Swap two comma-separated fields:

```text
:%s/\v(\w+), (\w+)/\2 \1/        Doe, Jane  →  Jane Doe
```

The `\=` form lets the replacement be an *expression* — e.g. `:%s/\d\+/\=submatch(0)+1/` increments every number in the file. And two repeat shortcuts: `&` re-runs the last `:s` on the current line, and pressing `g&` re-runs it across the whole file with the same flags.

A small but constant time-saver: an **empty pattern reuses your last search.** Search for something with `/`, eyeball the matches, then `:%s//replacement/g` substitutes that same pattern without retyping it.

### The Global Command: Vim's Power Tool

`:global` (`:g`) is the feature that, once learned, you reach for weekly. It runs an Ex command on **every line matching a pattern**:

```text
:[range]g/pattern/command
```

The defaults are devastating in the good way:

```text
:g/TODO/d              delete every line containing "TODO"
:g/^\s*$/d             delete every blank line
:g/error/t$            copy every line containing "error" to the end of the file
:g/^/m0                reverse the file (move every line to the top, in turn)
```

`:v` (or `:g!`) is the inverse — run the command on every line that **doesn't** match:

```text
:v/keep/d              delete every line that does NOT contain "keep"
```

The real power comes from combining `:g` with **`:normal`**, which runs *Normal-mode keystrokes* on each matched line. This is "do this edit on every line like X" in one command:

```text
:g/console/normal A  // debug          append a comment to every line with "console"
:g/^function/normal O/** doc */         add a doc line above every function
:g/;$/normal $x                          remove the trailing semicolon from lines ending in ;
```

`:g/pattern/normal {keys}` is, in effect, a one-shot macro applied to every matching line at once — frequently simpler than recording an actual macro (Part 8).

### The `cgn` Trick: Multi-Cursor, the Vim Way

A standout workflow that fuses search, change, and `.`-repeat. `gn` is a special motion that selects the **next match of the last search**, so `cgn` changes it. The pattern:

```text
*           search for the word under the cursor
cgn         change this match — type the replacement, <Esc>
n           (optional) skip a match you want to keep
.           repeat: jump to next match AND change it, in one keystroke
```

Now `.` `.` `.` walks through the file replacing each occurrence, and because you can press `n` to *skip* any match, you get find-and-replace with per-instance control — Vim's idiomatic answer to multiple cursors, and it's dot-repeatable so it costs one keystroke per edit.

If you remember one thing from Part 7: **`:%s` for blanket replacements, `:g/pat/normal …` for "run this edit on every matching line," and `*`-then-`cgn`-then-`.` for replace-with-review.** These three collapse the bulk-editing tasks that take minutes of clicking into seconds.

---

## Part 8 — Macros

A macro records a sequence of keystrokes and replays it on demand. Where `.` repeats your last *change*, a macro repeats an entire *workflow* — move, edit, move, edit — making it the tool for transforming a list of similar lines, reshaping data, or any repetitive multi-step edit. If you've ever done the same five edits on twenty lines by hand, a macro does the remaining nineteen for free.

### Record, Replay, Repeat

The interface is three keys:

- **`q{register}`** starts recording into a named register (e.g. `qa` records into `a`). Vim shows `recording @a`.
- Perform your edits normally — every keystroke is captured.
- **`q`** again stops recording.
- **`@{register}`** plays it back (`@a`). **`@@`** repeats the *last* macro played.
- **`{count}@{register}`** plays it many times: `20@a` runs macro `a` twenty times.

Because a macro is just keystrokes stored in a register, `"ap` *pastes* it as text and `:reg a` shows it — which is how you edit a macro that's almost right (next section).

### The Macro Mindset: Make Each Step Robust

The difference between a macro that works and one that corrupts your file is **discipline about position and repeatability**. Two rules:

1. **Start from a predictable position and end ready for the next iteration.** Begin each macro by normalizing the cursor (`0` to go to column zero, or `^`), and end by moving to the start of the *next* item (`j` for the next line). Then `{count}@a` flows cleanly down the file.
2. **Use structural motions, not counted ones.** Inside a macro, prefer `f,`, `ci"`, `$`, `/pattern<CR>` over "right three times" — so the macro adapts to lines of different lengths instead of breaking on the first one that doesn't match your assumptions.

Here's a complete example. You have a list of names to turn into a SQL `VALUES` list:

```text
Start:                    After  qa  ...edits...  q  on line 1, then 5@a:
alice                     ('alice'),
bob                       ('bob'),
carol                     ('carol'),
dave                      ('dave'),
```

Record it (`qa`), then on the first line type: `I('<Esc>` (prepend `('`), `A'),<Esc>` (append `'),`), `j` (next line), `q` (stop). One iteration done and cursor is on line 2. Now `3@a` finishes the rest. Read the recorded macro as a sentence: *go to line start, insert `('`, go to line end, append `'),`, move down.* Each step is position-independent, so it works regardless of name length.

### Counts, Recursion, and Fixing a Macro

- **Run to the end of the file** by giving a big count — `99@a` — and letting it stop when it runs out of lines (a macro errors and halts when a motion fails, e.g. `j` on the last line, which conveniently ends the run).
- **Recursive macros** call themselves: record the edits, and as the last step play the same register (`@a`) *before* you stop recording. Now `@a` runs until it fails on its own — no count needed. (Clear the register first with `qaq` so the recursion starts clean.)
- **Edit a misbehaving macro** by pasting it into the buffer (`"ap`), fixing the keystrokes as plain text, then yanking it back into the register (`0"ay$`). A macro is just text, so you debug it like text.

### Macro or `:g`? Choosing

Both apply an edit repeatedly, and they overlap:

- Reach for **`:g/pattern/normal {keys}`** (Part 7) when the edit applies to lines *matching a pattern* and each edit is self-contained — it's a one-liner with no recording.
- Reach for a **macro** when the transformation spans multiple lines per iteration, needs to navigate unpredictably, or you want to *watch* it run a few times with `@a` before committing with `{count}@a`.

If you remember one thing from Part 8: **a macro is a recorded sentence of edits — make each one start from a known spot, use structural motions, and end on the next item**, then let `{count}@a` apply it across the whole file while you do something else.

---

## Part 9 — Files Windows & Ex Power

So far, one file. Real work means many — jumping between source and test, grepping across a project, applying an edit to every file at once. This part covers Vim's models for holding multiple files (**buffers**, **windows**, **tabs** — routinely confused) and the Ex-command machinery (ranges, `:normal`, `:argdo`) that operates across them. Getting the buffer/window/tab model right removes most of the friction newcomers feel with multi-file editing.

### Buffers, Windows, Tabs — The Model People Get Wrong

The mental model, stated once and clearly:

- A **buffer** is a file loaded into memory. Open ten files and you have ten buffers, whether or not you can see them. *Buffers are your open files.*
- A **window** is a viewport onto a buffer. Splitting the screen gives you multiple windows, possibly showing different buffers (or the same one in two places). *Windows are panes.*
- A **tab** (tabpage) is a *layout of windows*. Crucially — and contrary to every other editor — **a Vim tab is not "an open file."** It's a saved arrangement of splits. You might keep all your files as buffers and use *one* tab, or use tabs to hold different *window layouts* for different tasks.

The big unlock: you don't need a visible window or tab per file. You keep many **buffers** open and *switch* which one the current window shows.

### Working with Buffers

| Command | Does |
|---|---|
| `:e {file}` | open a file (into a buffer) |
| `:ls` or `:buffers` | list open buffers |
| `:b {n}` / `:b {name}` | switch to buffer by number or name-fragment |
| `:bn` / `:bp` | next / previous buffer |
| `:bd` | delete (close) a buffer |
| `<C-^>` | toggle between the current and **alternate** (last) buffer |

`<C-^>` is the unsung hero — instant toggle between the two files you're bouncing between (source ↔ test). For switching among many, `:b str<Tab>` completes on a fragment of the filename, so `:b mod<CR>` jumps to `models.py`. Set **`hidden`** (default in Neovim) so you can switch away from a modified buffer without saving — without it, Vim nags you to save first.

### Windows (Splits)

Split the screen to see two places at once. Window commands hang off the `<C-w>` prefix:

| Command | Does |
|---|---|
| `:sp` / `<C-w>s` | split horizontally (same buffer) |
| `:vs` / `<C-w>v` | split vertically |
| `<C-w>h/j/k/l` | move focus left/down/up/right |
| `<C-w>w` | cycle to the next window |
| `<C-w>q` / `<C-w>c` | close the window |
| `<C-w>=` | equalize all window sizes |
| `<C-w>_` / `<C-w>\|` | maximize height / width |
| `<C-w>o` | close all windows *except* the current one |

`:vs {file}` opens another file in a vertical split. Most users remap the focus moves to plain `<C-h/j/k/l>` (Part 10) since hopping between splits is constant.

### Tabs

Use tabs for *task layouts*, not files: `:tabnew` (or `:tabe {file}`) opens a tab, `gt`/`gT` cycle forward/back, `{n}gt` jumps to tab `n`, and `:tabclose` closes one. If you're coming from VS Code and instinctively want "a tab per file," resist it — use buffers for that and you'll be working with the grain of the tool.

### Ex Ranges and Line Addressing

Part 7 used ranges with `:s` and `:g`; they apply to *most* Ex commands and compose from these address atoms:

| Address | Line |
|---|---|
| `.` | current line |
| `$` | last line |
| `{n}` | line `n` |
| `'a` | the line with mark `a` |
| `'<` / `'>` | start / end of the last visual selection |
| `/pat/` / `?pat?` | next / previous line matching `pat` |
| `+{n}` / `-{n}` | relative to the line before it |

Combine an address pair with a command: `:1,$` is the whole file (same as `:%`), `:.,+10>` indents the next eleven lines, `:'a,'bd` deletes from mark `a` to mark `b`.

### Commands That Move and Transform Lines

| Command | Does |
|---|---|
| `:{range}m {addr}` | **move** lines to after `{addr}` (`:m0` = to top, `:m$` = to bottom) |
| `:{range}t {addr}` or `:co` | **copy** lines to after `{addr}` (`:t.` duplicates the line) |
| `:{range}normal {keys}` | run Normal-mode keystrokes on each line in range |
| `:r {file}` | read a file's contents in below the cursor |
| `:r !{cmd}` | read the **output of a shell command** into the buffer |
| `:{range}!{cmd}` | filter the range *through* a shell command |
| `:{range}w {file}` | write just those lines to a file |

That filter line is a sleeper feature: `:%!sort` pipes the whole file through `sort` and replaces it with the result; `:'<,'>!python -m json.tool` pretty-prints the selected JSON; `:.!date` inserts today's date. Any Unix tool becomes a Vim command. (The operator form `!ip sort` from Part 3 does the same on a text object.)

### Editing Across Many Files at Once

To apply one change to a whole set of files, load them into the **argument list** and use `:argdo`:

```text
:args src/**/*.js              populate the arglist (** recurses)
:argdo %s/oldAPI/newAPI/ge | update     run the substitute in every file, then save
```

The `e` flag ignores "pattern not found" errors so one fileless-of-matches doesn't halt the run; `| update` writes each changed file. `:bufdo` does the same across all open buffers, `:windo` across visible windows, and `:tabdo` across tabs. This is project-wide refactoring without leaving the editor — and combined with `:g` and `:normal`, almost any bulk transformation is expressible.

### Finding Files, Grepping, and the Quickfix Loop

Finding a file by name is `:find {file}`, which searches along your `path` option — and the one-time setup that makes it powerful is `set path+=**`, after which `:find Model<Tab>` fuzzy-finds any file under the project by name fragment, no plugin required. The built-in file explorer is `:Explore` (`:Ex`), and most people eventually add a fuzzy finder (fzf or Neovim's Telescope, Part 10) for instant file and content search. But the feature worth understanding deeply here is not file-finding — it's the **quickfix list**, because it is the structure that turns "search the whole project" into "edit the whole project," and it is the single biggest reason Vim handles large refactors gracefully.

The quickfix list is a list of *locations* — file, line, column — that Vim can navigate through and act on as a unit. The canonical way to fill it is `:grep {pattern}`, which runs an external search (configure `grepprg=rg\ --vimgrep` to use ripgrep) across the entire project and dumps every match into the quickfix list as a navigable set of jump targets. From there a small, fixed loop handles everything: `:copen` opens the quickfix window so you can see every match across every file at once; `<CR>` on any entry jumps straight to that location; and `:cnext`/`:cprev` walk through the matches in order, each one loading the right buffer and placing the cursor exactly on the match. This is already a complete "find every usage and visit each one" workflow, but the multiplier is `:cdo` and `:cfdo`, which run an Ex command on *every entry* (or every file) in the quickfix list — so `:cdo s/oldName/newName/ | update` performs a project-wide, search-result-scoped substitution and saves each touched file, applying your edit to exactly the locations the grep found and nowhere else. The mental model to take away is that **a search produces a list, and the list is something you can edit through** — grep populates the quickfix list, you review it, and then `:cdo` (for scripted changes) or `:cnext`-plus-`.` (for reviewed ones) applies the transformation across the whole project from inside the editor, no separate find-and-replace tool involved. This loop — `:grep` → `:copen` → review → `:cdo` or step-and-`.` — is how experienced Vim users do project-wide refactors, and it composes with everything from Parts 6–8 because each entry is just a cursor position your normal editing commands operate on.

If you remember one thing from Part 9: **buffers are your files, windows are panes, tabs are layouts** — keep many buffers and switch with `<C-^>` and `:b`, and use `:argdo`/`:bufdo` with `:s`, `:g`, and `:normal` to edit across all of them at once.

## Part 10 — Configuration & Speed Recipes

You now have the language. This part makes Vim *yours* — a sane config, the ecosystem worth knowing, and the fact that the skill follows you into every other editor — and then pays off the title with a cookbook of edits that are dramatically faster than their click-and-drag equivalents. It closes with an honest account of when *not* to go all-in, and the fastest path to actually learning this.

### A Sane Starting Config

Vim reads `~/.vimrc`; Neovim reads `~/.config/nvim/init.lua` (or `init.vim` for Vimscript). Out of the box, Vim is deliberately minimal. A handful of options make it pleasant without changing its nature:

```vim
" ~/.vimrc — a sane starting point
set nocompatible            " behave like Vim, not vi (already default in Neovim)
syntax on                   " syntax highlighting
filetype plugin indent on   " filetype-aware plugins and indentation

set number relativenumber   " absolute number on the cursor line, relative elsewhere
set hidden                  " switch away from a modified buffer without saving
set incsearch hlsearch      " jump to matches as you type; highlight them
set ignorecase smartcase    " case-insensitive search unless the query has a capital
set expandtab shiftwidth=4 softtabstop=4   " indent with 4 spaces
set undofile                " persistent undo, survives closing the file
set scrolloff=5             " keep 5 lines of context above/below the cursor
set clipboard=unnamedplus   " let y/p use the system clipboard

let mapleader = " "         " use the spacebar as <leader>

inoremap jk <Esc>           " leave insert mode without reaching for Esc
nnoremap <leader>w :w<CR>   " <space>w to save
nnoremap <leader><space> :nohlsearch<CR>   " clear search highlight
nnoremap <C-h> <C-w>h       " move between splits with Ctrl+h/j/k/l
nnoremap <C-j> <C-w>j
nnoremap <C-k> <C-w>k
nnoremap <C-l> <C-w>l
```

Two notes that matter. **`relativenumber`** isn't cosmetic — it shows the *exact count* to any visible line, so when you see `7` beside a line you want, you press `7j` to get there. It turns counted motions from guesswork into reading-a-number. And always use the **`noremap`** family (`nnoremap`, `inoremap`, `vnoremap`) for mappings: the `nore` means "non-recursive," so your mapping won't break if one of the keys it uses is itself remapped. The `<leader>` key is a personal namespace — a prefix (here the spacebar) for your own commands that won't collide with built-ins.

### Vim or Neovim?

**Neovim** is a modern fork of Vim, and for a newcomer in 2026 it's usually the better default. What it adds: configuration in **Lua** (a real programming language, not Vimscript), a **built-in Language Server Protocol client** (so go-to-definition, rename, and diagnostics work like an IDE), **Treesitter** (syntax-aware highlighting and the semantic text objects from Part 5), first-class async, and saner defaults so your config starts smaller. Starter distributions — **kickstart.nvim** (a single well-commented file), **LazyVim**, **NvChad** — give you an IDE-grade setup in minutes.

**Vim** remains everywhere by default: it (or its tiny cousin `vi`) is preinstalled on essentially every server and container you'll SSH into, where Neovim may not be. The practical stance: learn the *language* in this guide — it's identical in both — use Neovim as your daily driver if you want the IDE features, and rest easy that your skills work unchanged when you land on a bare server with only `vim`.

### Plugins Worth Knowing (and Restraint)

You can be extremely productive with **zero plugins** — everything in Parts 1–9 is built in. Add plugins deliberately, for capabilities you actually miss, not to "rice" your setup. A plugin manager (**vim-plug** for Vim, **lazy.nvim** for Neovim) handles installation. The high-leverage few:

| Plugin | Gives you |
|---|---|
| **vim-surround** | operate on delimiters: `ysiw"` wrap a word in quotes, `cs"'`, `ds(` (Part 5) |
| **vim-commentary** | `gcc` to toggle a comment line, `gc{motion}` for a range (`gcip`) |
| **vim-repeat** | makes plugin commands (like surround) `.`-repeatable |
| **fzf** / **Telescope** | fuzzy "open any file / search any text" in a few keystrokes |
| **nvim-treesitter** | accurate highlighting + semantic text objects (`if`, `ac`, `ia`) |
| **LSP** (built-in / nvim-lspconfig) + completion | IDE features: go-to-def, rename, diagnostics, autocomplete |
| **vim-fugitive** | Git from inside Vim (`:Git blame`, staging, diffs) — pairs with the [Git guide](GIT_STUDY_GUIDE.md) |
| **which-key** | a popup that shows what your `<leader>` keys do — great while learning |

### Vim Everywhere

The deepest reason to invest: **the skill is portable to almost every tool you already use.** Vim keybindings exist as first-class modes far beyond Vim itself:

- **VS Code** — the *VSCodeVim* extension (modal editing with VS Code's IDE features underneath).
- **JetBrains IDEs** (IntelliJ, PyCharm, …) — *IdeaVim*.
- **Your shell** — `set -o vi` in Bash (readline) or `bindkey -v` in Zsh gives you modal command-line editing; press `<Esc>` and navigate your command with `b`, `e`, `ciw`.
- **Browsers** — *Vimium* / *Tridactyl* for keyboard-driven browsing.
- **Pagers and more** — `less`, `man`, and many REPLs use vi-style navigation, and Git already drops you into Vim for commit messages and interactive rebases.

Learn the grammar once; speak it in your editor, your terminal, your IDE, and your browser.

### The Speed Cookbook

The payoff. Each of these is a task that's slow and fiddly in a point-and-click editor and a reflex in Vim. Cursor position is `█`.

**Rewrite what's inside a delimiter** — the everyday win:

```text
foo(a, b█, c)     →  ci(  →  foo(█)        type new arguments
color: "re█d";    →  ci"  →  color: "█";   type new value
<h1>Titl█e</h1>   →  cit  →  <h1>█</h1>     type new heading
```

**Rename a symbol with per-instance review** (Vim's multi-cursor):

```text
*           on the symbol, search for it
cgn newName <Esc>      change this occurrence
n           skip one you want to keep (optional)
.           change the next occurrence — repeat . across the file
```

**Append/transform every matching line** with `:g` + `:normal`:

```text
:g/console\.log/normal A   // TODO remove     comment every debug log
:g/^import/normal $a;                          add a semicolon to every import
:g/^\s*$/d                                     delete all blank lines
:v/ERROR/d                                     keep only lines containing ERROR
```

**Filter through any shell tool** — Vim borrows the entire Unix toolbox:

```text
:%!sort -u                  sort the file and remove duplicate lines
:'<,'>!python -m json.tool  pretty-print the selected JSON
:%!column -t                align columns into a table
:.!date                     replace the current line with today's date
```

**Edit a column on many lines at once** with visual block (`<C-v>`):

```text
Prepend "- " to a list:        <C-v> select down the first column, I- <Esc>
Append ";" to many lines:       <C-v> select down, $, A; <Esc>
Delete a vertical slice:        <C-v> select the block, d
```

**Generate a numbered sequence** — select a column of zeros, then:

```text
0  0  0  0     →   <C-v> select the column   →   g<C-a>   →   1  2  3  4
```

**Reformat and reindent**:

```text
gg=G        re-indent the entire file
=i{         re-indent the contents of the current block
gqip        re-wrap the current paragraph to text width
guu / gUU   lower / upper-case the whole line
```

**Wrap, comment, and surround** (with the small plugins above):

```text
ysiw"       surround the word in double quotes      (vim-surround)
yss)        surround the whole line in parentheses
cs"'        change surrounding " to '
gcc         toggle a comment on this line           (vim-commentary)
gcap        comment out the whole paragraph
```

**Swap and move**:

```text
ddp         swap this line with the one below
xp          swap two characters
:m+1        move this line down one     (:m-2 moves it up one)
:%s/\v(\w+),(\w+)/\2,\1/   swap two comma-separated columns file-wide
```

The thread through all of these: you name the **structure** and the **operation**, and Vim does the mechanical selecting and repeating. That's the entire speed story in one sentence.

### When *Not* to Go All-In

An honest accounting, in the spirit of the rest of this repo:

- **The learning curve is real.** You will be slower for days. If you're on a tight deadline this week, learn Vim *next* week.
- **Heavily visual / mouse-native tasks** — dragging UI in a design tool, some notebook workflows — aren't where modal editing shines. Use the right tool.
- **You don't have to choose.** The highest-return move for most people isn't "abandon your IDE for terminal Vim" — it's enabling **Vim mode inside** VS Code or your JetBrains IDE, keeping the debugger, refactoring, and ecosystem while getting modal editing for the 90% of time you're moving and reshaping text. Best of both, none of the loss.
- **Don't rabbit-hole on config.** It's easy to spend a month tweaking `init.lua` instead of editing text. Start from a good base (kickstart.nvim or the snippet above), then change things only when something annoys you in real work.

On ergonomics, there's a genuine upside: modal editing replaces repetitive modifier-chording (the `Ctrl`/`Cmd`-everything that strains pinkies) with home-row letter commands, which many people find easier on the hands — provided you remap the far-away `<Esc>` to something reachable (`jk`, or Caps Lock).

### How to Actually Learn It

A concrete path that works:

1. **Day 1:** run `vimtutor` end to end (30 minutes). It's interactive and covers the survival basics hands-on.
2. **Week 1:** use Vim (or Vim mode in your IDE) for *real* editing, accepting the slowdown. Force the habits: stay out of insert mode, navigate with `w`/`b`/`f`/`/` instead of arrows. Some people disable the arrow keys to break the reflex.
3. **Weeks 2–3:** learn the part that pays the most — **text objects and operators** (Parts 3 and 5). `ci"`, `dap`, `ciw`, `ct,`. This is where Vim starts to feel fast.
4. **Week 4 and on:** add one tool at a time — the `.` workflow, then `:s` and `:g`, then macros, then a couple of plugins. Dip into `:help {topic}` whenever you wonder "can Vim do X?" (it can, and the docs are excellent).

The internalization order that mirrors this guide: **modes → motions → operators + text objects → search & substitute → `.` and registers → macros → config.** Don't rush to macros and plugins; the operators-and-text-objects layer is 80% of the daily speed.

If you remember one thing from Part 10: **configure lightly, lean on Vim mode everywhere you already work, and spend your practice on text objects and the `.` command** — that's where editing-at-the-speed-of-thought actually comes from.

---

## Where to Go Next

- **Run `vimtutor` today** if you somehow still haven't — 30 minutes, ships with Vim, and it's the best first hour of Vim instruction ever written.
- **Read Drew Neil's [*Practical Vim*](https://pragprog.com/titles/dnvim2/practical-vim-second-edition/)** — organized as 121 tips, it's the book-length version of this guide's grammar-first approach, and his [Vimcasts](http://vimcasts.org/) screencasts are free.
- **Learn to read `:help`** (mirrored at [vimhelp.org](https://vimhelp.org/)) — Vim's built-in docs are excellent once you know `:help text-objects`, `:help motion.txt`, and `Ctrl-]` to follow tags. Answering your own Vim questions is a skill that compounds forever.
- **If you go Neovim:** the [Neovim docs](https://neovim.io/doc/) and `:help lua-guide` for Lua configuration; [kickstart.nvim](https://github.com/nvim-lua/kickstart.nvim) is the best-documented starting config — a single annotated file, not a framework.
- **Drill, don't read.** Two weeks of real editing in Vim beats any further study; add one new motion or text object per day and force yourself to use it.
- **Adjacent guide in this repo:** the [Git guide](GIT_STUDY_GUIDE.md) — commit messages, `git mergetool`, and interactive rebase are where Vim shows up in your daily tools whether you chose it or not.

That's the guide. From here the highest-leverage next step isn't reading more — it's the two-week commitment: run `vimtutor` today, then do your real editing in Vim (or Vim mode) even though it's slower at first, and drill text objects until `ci"`, `dap`, and `cit` are reflexes. Past that hump, the grammar keeps compounding for the rest of your career, and every other editor starts to feel like typing with mittens on.


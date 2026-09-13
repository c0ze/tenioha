# Tenioha — proposed Japanese core

Design following the [2026-09-13 investigation](RESEARCH.md). **M0, M1, M2, and
the 0.4 closure, 0.5 nested-pattern, 0.6 compact-boundary, and 0.7 explicit-alias extensions are
implemented in Python**; [LANGUAGE.md](LANGUAGE.md) documents the runnable
dialect. The later surface-syntax extensions below remain proposals. See
[HANDOFF.md](../HANDOFF.md) for current progress and the next agent's starting point.

## 1. Preserve the idea, redesign the grammar

Keep Kip's typed argument roles, predicate-final calls, functional values,
and separation of pure computations from effects. Represent Japanese particles
directly rather than translating them into Kip's Turkish `Case` enum.

Separate a **value type** from a **parameter role**. An integer does not
permanently become an “accusative integer” when used with `を`. The particle
labels that occurrence of an argument. Another occurrence of the same variable
may supply `から` in another call.

Start with these separate internal concepts:

```text
Parameter = (local name, primary particle, alternate particles, value type)
Signature = (function identity, parameters, result type, effect)
Argument  = (expression, particle, source span)
Call      = (function identity, arguments, source span)
Effect    = Pure | IO
```

`Pure | IO` is an initial distinction, not a complete effect system. The checked
core records the resolved function and parameter bindings so the interpreter
does not repeat surface-level argument matching.

## 2. Call syntax

Use parenthesized, predicate-final calls with explicit lexical boundaries:

```text
(5 から 3 を 引く)
(3 を 5 から 引く)
((5 から 3 を 引く) に 4 を 足す)
(「こんにちは」 を 表示する)
```

The first two produce `2`; the nested expression produces `6`. `表示する`
performs I/O and returns `単位`, the unit type.

An initial expression grammar can be this small:

```ebnf
expression = integer | string | boolean | identifier | call ;
call       = "(" , { argument } , identifier , ")" ;
argument   = expression , particle ;
particle   = "が" | "を" | "に" | "で" | "から" | "へ" | "と" | "まで" ;
```

The lexer supplies distinct identifier and particle tokens. A zero-argument
call is `(読む)`; bare `読む` is a name reference. Delimiters make nested
calls explicit. M0/M1 call heads name a function; M2 adds explicit function
references and indirect application with `適用`.

This is Lisp-inspired expression structure with the predicate at the end.
It does not yet imply macros, quotation, or code-as-data semantics. The EBNF
above is the original M0 call subset. The current grammar, including M1
declarations, bindings, blocks, and conditionals, is in [LANGUAGE.md](LANGUAGE.md).

## 3. Argument matching

These signatures are **notation for this document**, not declaration syntax:

```text
引く       (元: 整数 から, 量: 整数 を)       -> 整数   ! Pure
足す       (元: 整数 に,   量: 整数 を)       -> 整数   ! Pure
表示する   (内容: 文字列 を)                 -> 単位   ! IO
読む       ()                               -> 文字列 ! IO
```

For the first implementation:

1. Resolve one function by name. Do not add overloading yet.
2. Reject duplicate particles in its declaration.
3. Reject missing, unexpected, or duplicate particles in a call.
4. Bind each argument to the parameter with that exact particle.
5. Check each argument's value type and require a pure argument expression.
6. Check the call's effect against its surrounding context.
7. Emit a resolved call with arguments in the signature's canonical order.

There is no missing-particle fallback, inferred `が`, implicit conversion, or
global `に`/`へ` alias. Since 0.7, explicit choices such as `に|へ` map to one
parameter identity; supplying both counts as supplying that parameter twice.
Choice sets must be disjoint across a signature, even with different value types.

### Repeated particles are a real limitation

Natural Japanese can use `に` for both a destination and a time. A unique-label
rule therefore accepts a controlled subset of Japanese, not all Japanese.
Two `に` arguments cannot be assigned arbitrary roles from the particle alone.

For v0, reject such signatures; use separate operations or a record argument
when records exist. Do not quietly fall back to positional matching. Later
options include explicit role names or matching `(particle, type)` when there
is exactly one complete assignment. Type-based matching must reject ambiguity,
especially with generics and overlapping types. This is deliberately stricter
than Kip's occurrence-order handling of repeated cases.

## 4. Japanese-specific choices

| Form | Proposed treatment | Reason |
|---|---|---|
| `が` | Explicit parameter label | Common subject marking; no automatically supplied subject |
| `を` | Explicit parameter label | Often an object, but the signature determines its meaning |
| `に` | Explicit parameter label | Can describe a target, recipient, time, and other relations |
| `で` | Explicit parameter label | Can describe a means or an action's location |
| `から`, `まで` | Separate labels | Useful for source/boundary operations; endpoint inclusion belongs to each API |
| `へ` | Separate label | No automatic substitution for `に` |
| `と` | Explicit label in the core | Coordination and quotation require separate grammar later |
| `は` | Explicit immutable binding in M1 | Not an alias for `が`; no ambient topic variable |
| `の` | Reserved for a later genitive/projection design | `利用者 の 名前 の 長さ` needs explicit association rules |
| `て` | Consider later as sequencing syntax | Verb conjugation and value binding must be specified first |
| `なら` | M1 conditional separator; M2 match-arm separator | Pure conditions/subjects and equally typed branches; exhaustive constructors for matching |

These are language-design choices, not a claim that Japanese particles each
have one meaning. The [TUFS materials](RESEARCH.md#sources) help distinguish
topic, case, and connective functions.

### Word boundaries and IME input

- Require whitespace between word tokens initially, including the particle
  after a bare identifier: `たから を` contains the single identifier `たから`.
  Never split it into `た` and `から` by suffix matching.
- Parentheses delimit calls. Accept `「…」` strings; define backslash escapes
  for a literal backslash, a closing `」`, newline, and tab. Strings and
  comments are never particle-tokenized.
- Specify Unicode identifier rules and compare names in NFC. Preserve original
  source offsets for diagnostics. Kanji, kana, and different spellings are not
  automatically equivalent identifiers.
- Accept U+3000 fullwidth space as whitespace. Initially use ASCII parentheses,
  minus signs, and digits; diagnose unsupported fullwidth equivalents. Later,
  an explicit punctuation mapping can improve IME ergonomics without applying
  NFKC to the entire program or modifying string contents.
- Permit kana identifiers and invented names. A dictionary should not decide
  whether a programmer is allowed to name a value.
- The 0.6 compact reader accepts unambiguous boundaries such as `5から`,
  `「文字列」を`, or `(式)を`. Bare identifier words remain whole: `値を`
  is one name, and `5から3を引く` is not accepted. See the implementation
  decision below for the exact scope.

These restrictions allow an initial implementation without an external
morphology engine. Supporting `書く` / `書いて` / `書きます` automatically
is a separate feature. Version 0.7 adds explicitly declared alternate names;
it does not infer arbitrary stems by deleting a suffix.

## 5. Effects and politeness

Dictionary forms can name either pure functions or I/O procedures. The
declaration and checked body determine the effect. `表示する` remains effectful
even though it is not polite; a declared polite alias has the same type and
effect as its canonical function.

Do not use honorific or humble speech to grant permissions. If capabilities
are added, represent them as actual values/permissions checked by the runtime
and type system. Register can be an optional presentation or style convention.
It is not, by itself, evidence of purity, public visibility, or authority.

### Sequencing before reordering

Reject I/O calls nested inside argument expressions, including zero-argument
`(読む)`. Bind their results in an explicitly ordered procedure first. This
M1 example is executable:

```text
手続き あいさつ -> 単位 {
    名前 は (読む)。
    文 は (「こんにちは、」 と 名前 を 連結する)。
    (文 を 表示する)
}
(あいさつ)
```

Here `連結する` takes a `文字列` with `と` followed by a `文字列` with `を`,
concatenates in that parameter order, and is pure. The sequence executes top
to bottom; bindings are lexical and immutable. Adding `を` to a name does not
bind it, and there is no implicit “previous result”.

Canonical parameter order is also the evaluation order for pure arguments.
Reordering their written positions preserves bindings and uses that same
canonical evaluation order. This matters even for pure code that diverges or
raises an arithmetic error. Explicit effects remain in statement order.

## 6. Implementation milestones

Build a fresh Japanese frontend and small core; do not fork Kip and replace
Turkish strings. Its morphology and elaboration are closely coupled.

M0 uses a Python reference interpreter with no third-party dependencies. This
makes it straightforward to change the grammar and check its behavior. A later
browser or native runtime can use the same examples and conformance tests;
no port is selected yet.

### M0 — executable particle-call experiment (implemented)

The interpreter implements tokenization, source spans, the expression grammar,
`整数`, `文字列`, `真偽値`, and `単位`; fixed builtin signatures; strict
particle/type matching; and an explicit effect context for top-level commands.
Pure expressions are accepted there, but nested effectful arguments are
rejected. Entire files are checked before execution. The CLI supports files,
inline evaluation, checking without execution, and a pure context.

The current reader also defines line comments, optional top-level `。`, string
escapes, NFC names, and explicit limits; see [LANGUAGE.md](LANGUAGE.md).

### M1 — a usable functional language (implemented)

M1 implements declarations with named parameters and return types, immutable
lexical bindings, explicit I/O sequences, direct/mutual recursion, and a lazy
conditional. User-defined pure functions and IO procedures are checked against
their declared return type and effect. Every body is checked before top-level
execution, including uncalled functions. Source signatures are hoisted to
support forward calls; values remain sequential and lexical.

Selected explicit `関数`/`手続き` declarations, `名前 は 式` bindings, and
`もし 条件 なら { … } そうでなければ { … }`. The comparison with explanatory
Japanese is recorded in [DECISIONS.md](DECISIONS.md).

The evaluator uses an explicit stack with at most 1024 active user calls.
Functions do not capture top-level or caller values; pass those as parameters.
Definitions are file-scoped, and values/functions have separate namespaces.
M1 did not include closures or tail-call optimization. The 0.4 extension below
adds anonymous closures while retaining the named-function scope rules.

### M2 — Kip-like expressiveness (implemented, 0.3.0)

M2 implements nominal algebraic types with particle-labelled constructors,
explicit generic parameters and type arguments, and exhaustive flat constructor
matching. Generic bodies are checked against abstract type parameters, even
when unused. Match subjects are pure; branches retain lexical scope, effects,
and lazy evaluation.

Function values carry ordered particle/type pairs, a result type, and an effect.
`参照` obtains a named function/procedure/constructor and `適用` invokes a
function value. Its callee evaluates first and must be pure; arguments retain
canonical evaluation order. IO cannot be passed as a pure function type.
Closures and anonymous functions are not part of this milestone.

Aliased, relative file imports expose a module's own type and function
declarations. Imported files contain declarations only. The entire import graph
is loaded and checked before entry statements execute, with cycle detection
and nominal type identity shared across aliases of the same canonical path.
The minimal source library provides generic lists (length/map/left-fold) and
optional values (default/map). See [LANGUAGE.md](LANGUAGE.md) for syntax.

### 0.4 — lexical closures (implemented)

Anonymous `関数`/`手続き` expressions omit the declaration name and return a
function value. They retain only the free lexical values used by their checked
body, including values needed by nested closures. Capture snapshots are immutable;
parameters and local bindings follow existing shadowing rules. Captures survive
factory returns and are independent across factory calls.

Closure creation is pure and delays the body. Each body is checked eagerly under
its declared result type and effect; calling a procedure closure remains IO.
Generic factories can return closures using their enclosing type parameters.
The existing explicit evaluator stack and call limit cover closure calls too.
Named declarations remain file-scoped and keep their original no-capture rules.

### 0.5 — nested patterns and ordered arms (implemented)

Constructor fields can recursively contain patterns. Bare names bind whole
values and `_` discards them, including at the root. Arms run in source order;
repeated outer constructors and partial overlaps are allowed when each arm
covers new cases. All bindings across a pattern must be unique except `_`.

The checker verifies particle roles and generic/nominal types at every level,
then uses constructor-matrix coverage to detect missing combinations and arms
covered by earlier arms. Missing-case errors include an uncovered pattern.
Coverage preserves correlations between fields; it does not merely collect
constructors appearing in each field independently. Analysis and runtime
matching use explicit work stacks, with a 50,000-state coverage limit per match.

Every body remains eagerly checked. The subject executes once, and failed arms
leave no bindings behind. The selected arm's nested bindings can be captured by
closures. Literal patterns, guards, primitive matching, and proofs that recursive
types have no finite values remain outside this extension.

### 0.6 — compact particle boundaries (implemented)

An ASCII integer may have one complete particle word attached, including after
a minus sign or leading zeros. Closing string quotes, parentheses, braces,
generic delimiters, and function-type brackets already supply word boundaries;
allow particles to touch them in values, patterns, parameters, and types.

Read identifier words in full, preserving names such as `たから` and `値を`.
The reader does not split particle prefixes from longer numeric suffixes such
as `5から引く` or `5から3を`. It retains original spans while normalizing
particle spelling to NFC. All existing semantic checks and spaced notation
remain in force. Unrestricted unspaced Japanese is still a separate proposal.

### 0.7 — explicit names and particle choices (implemented)

`別名 新名 は 対象` adds an explicit spelling for a named function, procedure,
or constructor, including a builtin or qualified import. Resolve forward aliases
and chains before checking bodies; reject unknown targets, cycles, and collisions.
Retain the target's runtime key, generic parameters, and complete signature.
Aliases are exported under their new name and may explicitly re-export imported
functions. They do not add a body, constructor coverage case, or type alias.

Parameters may declare disjoint choice sets, such as `(元:整数)に|へ`. Resolve
either label to the same slot and reject supplying both. The same rules apply
to closures, constructors, and patterns. Function types preserve choice sets;
normalize choice order within each slot while preserving parameter slot order.
Types must match exactly, without implicit narrowing, widening, or effect changes.

`別名` is a new keyword; programs that used it as an identifier must rename it.
Explicit declarations provide alternate spellings without a morphology engine,
global particle equivalence, or implicit politeness/effect rules.

### Later extensions

Explore broader controlled Japanese syntax, `の` projections, and `て` chains.

Porting, a JS backend, editor support, caching, macros, and game embedding come
after core semantics. A future untrusted-program runner still needs appropriate
isolation and resource limits; avoiding morphology does not remove that need.

## 7. Acceptance cases for the first interpreter

M0 cases are covered by `tests/test_language.py` and `tests/test_cli.py`.
M1's `tests/test_functions.py` additionally verifies source declarations,
normalized parameter/binding names, procedure ordering, effect propagation,
scope/shadowing, branch laziness/types, return types, and direct/mutual recursion.
M2 adds `tests/test_types.py`, `tests/test_function_values.py`, and
`tests/test_modules.py` for constructors/generics, exhaustive matches,
function signatures/effects, and module identity/loading/diagnostics.
The 0.4 `tests/test_closures.py` adds lexical capture, lifetime, generic factory,
shadowing, delayed execution, and closure type/effect tests.
The 0.5 `tests/test_patterns.py` covers nested patterns, ordered overlaps,
missing combinations, unreachable arms, aliases, and captured bindings. An
independent finite-domain oracle checks 729 three-arm pattern combinations.
The 0.6 `tests/test_compact.py` checks lexical boundaries, all particle labels,
argument permutations, Unicode spans, numeric limits, and compact forms across
types, patterns, closures, and modules. CLI cases verify output and diagnostics.
The 0.7 `tests/test_aliases.py` checks choice sets and argument permutations,
duplicate roles, type equality/substitution, effects, canonical failure order,
aliases and forward chains, constructor identity/coverage, imported re-exports,
and validation before I/O. CLI cases cover the example, check counts, and spans.

| Case | Expected result |
|---|---|
| `(5 から 3 を 引く)` and its argument permutation | Both evaluate to `2` |
| `(3 から 5 を 引く)` | `-2`; roles matter for a noncommutative operation |
| `((5 から 3 を 引く) に 4 を 足す)` | `6` |
| `(3 に 5 に 足す)` | Duplicate `に` and missing `を`, with spans |
| `(5 から 引く)` | Missing `を` |
| `(5 から 3 を 1 で 引く)` | Unexpected `で` |
| `(「五」 から 3 を 引く)` | `から` expects `整数`, received `文字列` |
| A signature declaring `に` twice | Declaration error, even if its types differ |
| A `は` argument where `が` is declared | Reject reserved/wrong particle; no implicit substitution |
| `(「こんにちは」 を 表示する)` in an effectful command context | Prints the text and returns unit |
| The same call in a pure checker context (`--pure`) | Effect error |
| `((読む) を 表示する)` | Nested effect error before any input is read |
| `たから` and `たから を` in lexer tests | Preserve the identifier; the latter adds a separate label |
| `「は、が、を、から」` | One unchanged string token |
| A valid string containing an escaped closing quote | One string containing the literal quote |
| Missing `)` or an unterminated `「` string | Precise syntax error |
| NFC-equivalent function name spellings | Same lookup; original source spans preserved |
| ASCII versus fullwidth spaces | Same token boundaries |
| Fullwidth digits in the initial reader | Clear unsupported-token error |

Four-parameter permutations are tested for host builtins, source functions,
constructors, and indirect calls. M2 tests preserve those bindings and effects
through function values and verify generic substitutions, exhaustive matches,
module cycles, and errors in unused imported bodies before program I/O.

# Tenioha 0.6 — the runnable language

This describes M0/M1/M2, the 0.4 closure extension, 0.5 nested patterns, and
0.6 compact particle boundaries.
The larger [design](DESIGN.md) also contains future features. Literal patterns,
guards, and unrestricted unspaced Japanese are not implemented yet. See [the handoff](../HANDOFF.md)
for milestone progress and [decisions](DECISIONS.md) for the syntax rationale.

## Running programs

From the project directory, using Python 3.11+:

```sh
python -m tenioha examples/hello.ten
python -m tenioha examples/factorial.ten
python -m tenioha examples/greeting.ten < examples/greeting.in
python -m tenioha examples/lists.ten
python -m tenioha examples/options.ten
python -m tenioha examples/closures.ten
python -m tenioha examples/closure_greeting.ten < examples/closure_greeting.in
python -m tenioha examples/nested_patterns.ten
python -m tenioha examples/compact.ten
python -m tenioha --eval '(3 を 5 から 引く)'
python -m tenioha --eval '(真 を 否定する)'
python -m tenioha --check examples/arithmetic.ten
python -m tenioha --pure --eval '((5 から 3 を 引く) に 4 を 足す)'
```

Files are UTF-8, with an optional initial BOM; `.ten` is the conventional
extension. File mode displays only explicit program output. `--eval` executes
its source, then prints each non-unit result; it does not echo the unit returned
by `表示する`. Strings print as text, booleans as `真`/`偽`, and integers as
decimal numbers. Use `--eval '(読む)'` to read and echo one input line.
Algebraic values display their constructor and particle-labelled fields, with
quoted strings inside them. Named function values display `参照` and their
function name. Closures display `関数 {…}` or `手続き {…}` without their captures.
These displays omit module aliases and type arguments and are not a
source serialization format.

`--check` checks without executing any statement and reports entry statement,
named function definition, and (when present) algebraic type counts. Anonymous
closure bodies are checked but do not add to the named definition count. Definition/type
counts include imported modules, counting each file once. `--pure` requires pure top-level execution, including when
combined with `--check`; unused procedure definitions are allowed under their
declared IO context. Every function body is checked, even if uncalled. The
interpreter checks an entire input and its import graph before running its first statement.
Syntax, role, type, and effect errors
therefore prevent all program I/O. Runtime failures, such as division by zero,
stop execution at that point and do not undo earlier output.

Exit codes: `0` success, `1` language/file/runtime error, `2` CLI usage error,
and `130` keyboard interruption. Diagnostics include a code, file, line, column,
and source underline. Diagnostic prose is currently English; Japanese names
and types are preserved.

## Reader

- Integers use ASCII digits and an optional ASCII minus: `5`, `-3`, `0005`.
  Leading zeros are decimal. Floats are not supported. Integer literals may
  have at most 4096 digits; calculated integers can exceed that size.
- Strings use `「…」` and preserve their contents without normalization.
  They may span lines. Escapes are `\\` (backslash), `\」` (closing quote),
  `\n` (newline), and `\t` (tab). Other escapes are errors.
- Boolean literals are `真` and `偽`. Unit has no literal; `(何もしない)`
  returns unit.
- A name is a Python-style Unicode identifier, compared using **NFC**, with
  no kana/kanji transliteration or compatibility normalization. An entire
  word is read before checking whether it is a particle: `たから` and
  `文字列にする` each remain one name. No dictionary is used.
- Whitespace, including U+3000 fullwidth space, separates words. Integers may
  attach one complete particle word, as in `5から`. Closing delimiters also
  separate words, allowing `「猫」を` and `(式)に`. Identifier words, including
  boolean and bare type names, still need separation from their particles.
- Parentheses, braces, colons, the return arrow `->`, generic delimiters `< >`,
  function type brackets `[ ]`, commas, and qualification dots are ASCII.
  Other fullwidth punctuation/numeral equivalents are
  not rewritten. Japanese punctuation and fullwidth numerals remain valid
  inside strings.
- `;` begins a comment through the end of the line, except inside a string.
- Newlines are whitespace. `。` may terminate a statement at file or block
  scope; it is optional and is not a separator inside a call.
- Calls, blocks, conditionals, matches, patterns, closures, and type expressions have a nesting
  limit of 128 levels. An import chain may contain at most 128 files, including
  the entry file.
  Runtime recursion has a separate limit of 1024 active user function calls.
  Exceeding either limit produces a language diagnostic.
- Match coverage checking permits at most 50,000 analyzed states per match.
  Exceeding it produces `E_MATCH_COMPLEXITY`; split the match into smaller matches.

## Compact particle boundaries

Spaced and compact notation can be mixed in one program. This prints `2` and
`前後`:

```text
(((5から 3を 引く)を 文字列にする)を 表示する)。
((「前」と「後」を 連結する)を 表示する)。
```

An ASCII integer may attach exactly one complete particle word, including after
a minus sign or leading zeros: `-0005から` is the integer `-5` followed by
`から`. Particle comparison uses NFC, with original numeric and particle spans
retained for diagnostics. The 4096-digit integer limit is unchanged. Numeric
prefixes, floats, fullwidth numbers, and numeric words such as `5から3を` or
`5から引く` remain errors. Reserved syntax words such as `は` and `なら`
cannot attach to integers and retain their existing grammatical roles.

Closing `」`, `)`, `}`, `>`, and `]` delimit a value or type, so a following
particle need not have whitespace. This applies consistently to argument
expressions, constructor patterns, parameter declarations, and function types:
`(値:整数)を`, `((値 を 有り)を 有り)`, `一覧<整数>を`, and
`関数[整数 を->整数]で` all have clear boundaries. Imports may similarly use
`取込「module.ten」と 別名`.

Every identifier word is still read in full. `値を`, `たから`, `真を`, and
`整数を` are single names; write `値 を`, `真 を`, and `整数 を` when a
particle is intended. A particle and a following identifier or number also
need separation: `「猫」を表示する` and `5から3を引く` are not split into a
call. A delimiter can provide that separation, as in `「前」と「後」を`.
Use whitespace or delimiters, without guessing boundaries from known names.

This extension changes only reading: exact particles, argument evaluation
order, types, effects, and matching rules are the same. For example,
`((読む)を 表示する)` is still rejected for nested I/O. Strings and comments
are unchanged, and automatic verb conjugation or particle aliases are not added.
See [compact.ten](../examples/compact.ten) for modules, closures, and nested
patterns using the shorter notation.

## Expressions and calls

```ebnf
program    = { (declaration | statement) , [ "。" ] } ;
statement  = binding | expression ;
binding    = identifier , "は" , expression ;
expression = integer | string | boolean | qualified_name | call | block | conditional | match | reference | closure ;
qualified_name = identifier , { "." , identifier } ;
call       = "(" , { argument } , (qualified_name , [ type_arguments ] | "適用" , expression) , ")" ;
argument   = expression , particle ;
particle   = "が" | "を" | "に" | "で" | "から" | "へ" | "と" | "まで" ;
block      = "{" , { statement , [ "。" ] } , "}" ;
conditional = "もし" , expression , "なら" , block , "そうでなければ" , block ;
declaration = function_declaration | type_declaration | import ;
function_declaration = ("関数" | "手続き") , identifier , [ type_parameters ] , { parameter } , "->" , type , block ;
parameter  = "(" , identifier , ":" , type , ")" , particle ;
type       = qualified_name , [ type_arguments ] | function_type ;
type_parameters = "<" , identifier , { "," , identifier } , ">" ;
type_arguments = "<" , type , { "," , type } , ">" ;
function_type = ("関数" | "手続き") , "[" , [ function_parameter , { "," , function_parameter } ] , "->" , type , "]" ;
function_parameter = type , particle ;
type_declaration = "型" , identifier , [ type_parameters ] , "{" , { constructor , [ "。" ] } , "}" ;
constructor = identifier , { parameter } ;
match      = "場合" , expression , "{" , { arm , [ "。" ] } , "}" ;
arm        = pattern , "なら" , block ;
pattern    = identifier | "(" , { pattern , particle } , qualified_name , ")" ;
reference  = "参照" , qualified_name , [ type_arguments ] ;
closure    = ("関数" | "手続き") , { parameter } , "->" , type , block ;
import     = "取込" , string , "と" , identifier ;
```

Calls put the function last. Nested calls require their own parentheses:

```text
(5 から 3 を 引く)
(3 を 5 から 引く)
((5 から 3 を 引く) に 4 を 足す)
```

These return `2`, `2`, and `6`. A bare name reads a bound value. Use `(読む)`
to invoke a zero-argument function and `参照 読む` to obtain its function value;
`読む` alone remains an error.

`は` introduces bindings and `なら` separates a condition from its branches.
`の` and `て` remain reserved. These words do not act as argument labels.
Particle matching is exact; `へ` does not stand in for
`に`. Signatures cannot repeat a label, even with different value types.

## Functions and procedures

```text
関数 差 (元: 整数) から (量: 整数) を -> 整数 {
    (元 から 量 を 引く)
}

手続き 挨拶 -> 単位 {
    名前 は (読む)。
    文 は (「こんにちは、」 と 名前 を 連結する)。
    (文 を 表示する)
}
```

`関数` declares a pure function and `手続き` an IO procedure. Both declare
named, typed particle parameters and a return type. A zero-argument declaration
goes directly from the name to `->`; do not write an empty parameter group.
The body's last statement supplies the result. An empty block or a final
binding returns `単位`. The body must match the declared result type.

Named declarations are file-scoped; nested named declarations and duplicate function names
(including builtin and constructor replacements) are rejected. All signatures are registered
before bodies are checked, so calls may precede their declarations and functions
may recurse directly or mutually. Value bindings are not hoisted.

Named file-scoped functions see parameters, local values, and file-scoped function names. They
do not capture top-level values or caller-local values; pass those explicitly
as parameters. Value and function names use separate namespaces. A value named
`引く` does not replace the function selected by a call ending in `引く`.

## Bindings and blocks

```text
値 は 1。
内側 は {
    値 は (値 に 1 を 足す)。
    値
}。
```

After this code, `値` is `1` and `内側` is `2`. `は` binds a value once in the
current scope. Its type is inferred from the initializer; no conversion or
mutation occurs. The binding becomes visible after its initializer completes.
A nested block may shadow an outer name and use the outer value in that
initializer. Bindings do not escape their blocks or branches.

Rebinding within the same scope is an error, including rebinding a parameter
in its function's outermost block. Nested blocks can shadow parameters. A block
evaluates statements in order and returns its last result; earlier results are
discarded. A binding itself returns unit, so it is not echoed by `--eval`.

## Conditionals and recursion

```text
関数 階乗 (数: 整数) を -> 整数 {
    もし (数 と 0 が 等しい) なら {
        1
    } そうでなければ {
        (数 に ((数 から 1 を 引く) を 階乗) を 掛ける)
    }
}
```

`(6 を 階乗)` returns `720`. This example expects nonnegative input; negative
input never reaches its base case and eventually hits the call-depth limit.

Conditions must be pure and have type `真偽値`. Both branches are mandatory
and must return the same type. Both are checked statically, but only the
selected branch executes. A failing computation in an unselected branch is
not evaluated. Branches inherit the surrounding effect context and have their
own lexical scopes.

The evaluator uses an explicit stack instead of Python recursion, with at most
1024 active user calls. There is no tail-call optimization in this version.

## Algebraic types and explicit generics

```text
型 一覧<T> {
    空。
    節 (頭: T) を (尾: 一覧<T>) に
}

関数 長さ<T> (値: 一覧<T>) を -> 整数 {
    場合 値 {
        (空) なら { 0 }
        (_ を 残り に 節) なら { ((残り を 長さ<T>) に 1 を 足す) }
    }
}

値 は (1 を (2 を (空<整数>) に 節<整数>) に 節<整数>)。
(値 を 長さ<整数>)
```

The final expression returns `2`. `型` introduces a nominal algebraic type with
one or more constructors. Constructor fields use named, typed particle
parameters; construction is a pure call with the same exact-label checks and
canonical evaluation order as a function. Constructors share the function
namespace and cannot replace another constructor, function, or builtin.
Types have a separate namespace. Type and function declarations are hoisted,
including mutually recursive types.

Declare generic parameters after a type or function name: `<T>` or `<T, U>`.
Supply all type arguments explicitly in types, calls, and references, including
nullary constructors such as `(空<整数>)`. There is no generic argument
inference, partially specialized function value, or implicit conversion.
Type parameters must be unique and cannot shadow visible type names.

Generic function bodies are checked once against abstract type parameters,
even if unused. A parameter of type `T` cannot be passed to integer addition:
the body must work for every possible `T`. The generic runtime shares the
checked body; it does not expand a new body for each type instantiation.
Function types and instantiated algebraic types can themselves be type arguments.
Two different type declarations remain different even when their fields match.

## Exhaustive nested constructor matching

`場合` evaluates a pure algebraic subject once and tries arms in source order.
The first matching arm runs. Every arm is checked before execution, all arms
must return the same type, and only the selected body executes. Arm effects
inherit the surrounding context.

A constructor pattern uses the same predicate-last structure and exact field
particles as a constructor call. A field can itself contain a constructor
pattern, a binding name, or `_`:

```text
型 選択<T> { 無し。有り (値: T) を }

関数 内側 (入力: 選択<選択<整数>>) から -> 整数 {
    場合 入力 {
        (無し) なら { 0 }
        ((無し) を 有り) なら { 1 }
        ((値 を 有り) を 有り) なら { 値 }
    }
}

(((7 を 有り<整数>) を 有り<選択<整数>>) から 内側)
```

The last expression returns `7`. Repeating an outer constructor is allowed when
its nested patterns cover new cases. Particles can be reordered at every level;
all fields must still appear exactly once. Constructor patterns omit type
arguments, which follow from the subject and its field types. Foreign constructors,
wrong particles, and constructors used against primitive/function/abstract fields
are errors. Generic and nominal module types retain their existing checks.

`_` matches any value at its position and discards it. A bare name matches and
binds the whole value at that position, including at the root: `残り なら { … }`.
A bare constructor spelling is also a binding; write `(無し)` to match that
constructor, rather than `無し`. Qualified constructor names need parentheses.

Non-wildcard binding names must be unique across the entire pattern after NFC
normalization, including different nesting levels. `_` may repeat. Bindings are
local to an arm, may shadow outer values, and cannot be rebound in the arm's
outermost block. A failed arm contributes no bindings to later arms. Closures
returned from an arm may retain its nested or whole-value bindings.

Coverage checking considers constructor combinations, including relationships
between fields. For a pair of two-colour values, arms matching `(赤, 赤)` and
`(青, 青)` leave `(赤, 青)` and `(青, 赤)` uncovered even though both colours
appear in both columns. `E_MATCH_EXHAUSTIVE` reports one uncovered pattern shape;
`_` within that diagnostic leaves a field unrestricted.

Overlapping arms are allowed if each can match something not covered by earlier
arms. A nested special case followed by a broader pattern is useful; reversing
that order makes the special case unreachable. A later arm can also be covered
by several earlier arms together. Completely covered arms produce `E_PATTERN`
with an unreachable-pattern diagnostic. A final `_` or binding can cover the
remaining cases, but is itself rejected if earlier arms are already exhaustive.

Subjects still require algebraic data, even when the only arm is `_`. Literal
patterns, guards, alternatives within a single pattern, and primitive matching
remain future work; use `もし` to inspect bound primitive values. The checker
uses declared constructor structure and does not prove that a recursive type
has no finite values. Such declarations still require structural coverage.

See [nested_patterns.ten](../examples/nested_patterns.ten) for optional lists,
ordered fallbacks, and a closure capturing a nested list element.

## Function values

```text
関数 計算 (操作: 関数[整数 から, 整数 を -> 整数]) で -> 整数 {
    (3 を 10 から 適用 操作)
}

差 は 参照 引く。
(差 で 計算)
```

The final expression returns `7`. `参照 名前` obtains a named function,
procedure, or constructor as a value without invoking it. Generic references
need explicit arguments, such as `参照 長さ<整数>`. Bare function names remain
errors. Values and function names continue to use separate namespaces.

An indirect call puts `適用` and a function-valued expression at the end:
`(5 から 3 を 適用 差)`. The callee must be pure and is evaluated first;
arguments then evaluate in the function type's canonical parameter order.
A callee may come from a binding, function result, conditional, match, or closure
expression. Nested named function declarations remain unsupported.

Function types declare ordered particle/type pairs, a result, and an effect:
`関数[整数 から, 整数 を -> 整数]` or `手続き[文字列 を -> 単位]`.
A zero-argument function type is `関数[-> 整数]`. Parameter names are not part
of a function type. Particle order is part of it, because changing that order
could change which argument failure happens first. Repeated particles are errors.
Types must match exactly; no parameter variance or effect coercion is provided.

Creating a procedure reference is pure; applying it remains IO. A pure function
may return a procedure reference, but cannot invoke one. Passing an IO reference
where a pure function type is required is rejected. If a procedure returns a
function value, bind that result before using it as a callee.

## Anonymous functions and lexical closures

```text
関数 加算器 (増分: 整数) で -> 関数[整数 を -> 整数] {
    関数 (値: 整数) を -> 整数 { (値 に 増分 を 足す) }
}

一増やす は (1 で 加算器)。
十増やす は (10 で 加算器)。
(5 を 適用 一増やす)
(5 を 適用 十増やす)
```

The last two expressions return `6` and `15`. A `関数` or `手続き` expression
without a name creates an anonymous function value, called a closure. Parameters
and the result type remain explicit. A zero-argument closure goes directly to
`->`, as in `関数 -> 整数 { 7 }`.

Apply a closure with `適用`, just like any function value. A bound closure name
already denotes its value; `参照` is for named file-scoped functions, procedures,
and constructors. Closures can be passed directly as arguments or callees,
returned, stored in algebraic data, and nested inside other closures.

A closure retains the immutable outer values its body uses, from the lexical
scope where it was created. These values survive the surrounding function or
block. Later shadowing and the caller's local variables cannot change them.
Nested closures retain values needed by their own nested closures too. Unused
outer values are not retained. Each invocation starts with fresh local bindings.

Parameters may shadow outer values. A local binding may shadow a captured name,
and its initializer still sees the outer value. Rebinding a parameter or local
in the same scope remains an error. Pattern bindings can be captured by a closure
returned from a match arm. A closure cannot capture a binding introduced later,
including its own initializer's binding; recursive local bindings are not added.
Named file-scoped functions still only see their parameters and locals. A closure
inside one can capture those values, not unrelated top-level or caller values.

Creation is pure and does not execute the body. Every closure body is checked
before program execution, even if its value is unused or its containing branch
is not selected. The body is checked under its own declared pure/IO context:

```text
名前 は (読む)。
挨拶 は 手続き -> 単位 {
    ((「こんにちは、」 と 名前 を 連結する) を 表示する)
}。
(適用 挨拶)。
(適用 挨拶)。
```

This reads once and prints twice. Creating `挨拶` performs no I/O. Invoking it
requires an IO context, even if a procedure body happens to be pure. A pure
function may construct and return a procedure closure. A pure closure cannot
invoke captured IO function values; ordinary function-type effect checks apply.
`--pure` permits creating a procedure closure, and `--check` checks its body
without reading input or printing its output.

Closures inherit type parameters from an enclosing generic function. For example,
`関数 保存<T> (値: T) を -> 関数[-> T] { 関数 -> T { 値 } }` is valid.
Closures cannot declare fresh generic parameters or infer parameter/result types.
Use a named generic factory when specialization is needed.

Closure invocations share the explicit evaluator stack and the 1024-active-call
limit with named functions. Tail-call optimization and nested named declarations
remain future work. Imported modules may define factories returning closures;
an anonymous expression at module top level is still rejected as an initializer.
See [closures.ten](../examples/closures.ten) and
[closure_greeting.ten](../examples/closure_greeting.ten) for runnable examples.

## Modules and the small library

Save this program in the `examples` directory:

```text
取込 「../lib/list.ten」 と 列。

値 は (1 を (2 を (列.空<整数>) に 列.節<整数>) に 列.節<整数>)。
(((値 を 列.長さ<整数>) を 文字列にする) を 表示する)。
```

`取込 「relative/path.ten」 と 別名` imports a file relative to the importing
file's directory, independently of the process's working directory. Access its
own types, constructors, and functions through `別名.名前`. Imports are
hoisted. No global module search path, package installation, or absolute import
path is used. An import through another module is not automatically re-exported.

Imported files contain only type declarations, function/procedure declarations,
and imports. Top-level value bindings and expressions are rejected, so importing
a module performs no program I/O. Every imported body is checked, even if unused.
Modules may declare IO procedures; their effects are checked at call sites.
The entry file retains normal ordered top-level execution.

A canonical file path identifies a module. Repeated imports and different
aliases of the same file share its definitions and nominal types. Identically
named types from different files remain distinct. Cycles, unreadable/invalid
files, duplicate aliases, and excessive import depth produce source diagnostics.
`--check` reads module source files but never executes program statements.
`--eval` has no file location and rejects imports. For embedding, provide a
concrete `filename` to `compile_source` or `run` to resolve relative imports.

The source library is intentionally small:

| File | Type and constructors | Functions |
|---|---|---|
| [list.ten](../lib/list.ten) | `一覧<T>`, `空`, `節` | `長さ<T>`, `写す<T, U>` (map), `畳む<T, U>` (left fold) |
| [option.ten](../lib/option.ten) | `選択<T>`, `無し`, `有り` | `取り出す<T>` (value or default), `写す<T, U>` (map) |

List map and fold accept pure function values. As ordinary recursive functions,
they retain the 1024-active-call limit. See [lists.ten](../examples/lists.ten)
and [options.ten](../examples/options.ten) for complete programs with output.

## Builtins

The parameter column below describes a signature; it is not source syntax for
declaring a function. Parameter order here is the canonical evaluation order.

| Function | Parameters in canonical order | Result | Effect / behavior |
|---|---|---|---|
| `引く` | `元: 整数 から`, `量: 整数 を` | `整数` | Pure; 元 − 量 |
| `足す` | `元: 整数 に`, `量: 整数 を` | `整数` | Pure; addition |
| `掛ける` | `元: 整数 に`, `量: 整数 を` | `整数` | Pure; multiplication |
| `割る` | `元: 整数 を`, `除数: 整数 で` | `整数` | Pure; integer quotient rounded toward negative infinity; zero divisor is an error |
| `等しい` | `左: 整数 と`, `右: 整数 が` | `真偽値` | Pure; integer equality |
| `否定する` | `値: 真偽値 を` | `真偽値` | Pure; boolean negation |
| `連結する` | `前: 文字列 と`, `後: 文字列 を` | `文字列` | Pure; 前 followed by 後 |
| `文字列にする` | `値: 整数 を` | `文字列` | Pure; decimal conversion |
| `何もしない` | none | `単位` | Pure; unit value |
| `表示する` | `内容: 文字列 を` | `単位` | IO; write text and a newline, then flush |
| `読む` | none | `文字列` | IO; read one line without its line ending; EOF is an error |

There is no overloading or implicit conversion. For example, `真` is not an
integer, and `表示する` requires a string. Display an integer explicitly:

```text
(((5 から 3 を 引く) を 文字列にする) を 表示する)。
```

The checker binds arguments by particle and stores them in canonical parameter
order. Pure arguments evaluate in that order, regardless of their written
positions. Their exception order is therefore stable under permutation too.

## Effects

Top-level statements and procedure bodies execute in source order and may perform I/O. Every call
argument must be pure, including arguments of an I/O function. This is rejected
before it reads anything:

```text
((読む) を 表示する)
```

Bind effectful results before supplying them as arguments:

```text
名前 は (読む)。
(名前 を 表示する)。
```

A procedure may return a value, but calling it remains IO even if its body
happens to be pure. Pure functions cannot call procedures. IO hidden inside
an argument block or conditional branch is also rejected. A condition itself
must be pure; bind an IO result first if it will determine a branch.

Plain or polite spellings do not alter effects. Function names are matched
exactly after NFC normalization; there is no automatic conjugation.

## Python embedding and tests

```python
from tenioha import compile_source, execute, run

assert run("(3 を 5 から 引く)") == [2]
program = compile_source("(5 から 3 を 引く)", allow_io=False)
assert execute(program) == [2]
```

`run` and `execute` accept `stdin` and `stdout` text streams. `compile_source`
performs no program I/O, although imports read source files. The test suite uses in-memory streams to verify that
invalid programs do not read or print, and subprocesses to verify CLI behavior.
Executing a compiled program starts with fresh top-level bindings and closure
captures each time.
The result list has one value per top-level statement (bindings return `None`);
declarations contribute no result entry. `Program.definitions` contains checked
function bodies across the import graph, `Program.types` contains nominal type
definitions, and `Program.expressions` retains the entry statement list.

```sh
python -m unittest discover -s tests -v
```

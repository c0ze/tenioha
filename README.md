# てにをは / Tenioha

*English · [日本語](README.ja.md)*

Tenioha is an experimental functional language in which Japanese particles are
checked parts of a function signature. A call binds each argument by its
particle rather than by its position, so arguments may be reordered as long as
the particles are distinct. The implementation is a Python reference
interpreter with no third-party dependencies.

> *てにをは* (tenioha) is the traditional Japanese term for the grammatical
> particles, named after て・に・を・は themselves. Idiomatically it refers to
> whether a sentence's grammar holds together: 「てにをはが合わない」 is said
> of someone whose particles are wrong.

## Status

Version 0.7.1. The interpreter covers typed particle calls, user-defined
functions and procedures, immutable bindings, recursion, lazy conditionals,
checked I/O, algebraic data types, explicit generics, exhaustive nested
constructor matching, function values, and modules. Generic list and option
libraries are included. Anonymous functions and procedures capture immutable
lexical values. Matches take ordered arms and wildcard fallbacks; missing and
unreachable cases are rejected before execution. Particles may touch integers
and closing delimiters, while identifier words keep explicit boundaries.
Explicit alternate names and per-parameter particle choices preserve the same
types, effects, and canonical argument order.

Version 0.7.1 fixes crashes on deeply nested generic types and makes source
handling consistent across files and embedding. CR and CRLF inside file string
literals now retain their original characters; earlier file decoding translated
them to LF. Comments and diagnostic locations follow the documented
line-ending rules, and every input path accepts exactly one initial BOM.

- [Milestone progress and agent handoff](HANDOFF.md)
- [Project introduction and browser playground](https://c0ze.github.io/tenioha/)
- [Playground development and deployment](docs/PLAYGROUND.md)
- [Current language and builtins](docs/LANGUAGE.md)
- [Recorded language decisions](docs/DECISIONS.md)
- [Claude, Kimi, and Grok audit and fixes](docs/AUDIT-0.7.md)
- [Investigation of Kip and Japanese prior art](docs/RESEARCH.md)
- [Proposed Japanese core and implementation milestones](docs/DESIGN.md)

---

## The idea

In most languages an argument's meaning follows from its position:

```python
subtract(5, 3)   # the minuend is not marked; the reader has to remember
```

Tenioha uses particles to identify argument roles instead:

```text
(5 から 3 を 引く)
(3 を 5 から 引く)
```

Both calls mean "subtract 3 from 5" and return `2`. `から` marks the starting
value and `を` the amount subtracted. The signature checks the particle and the
ordinary value type, such as `整数` (integer).

Arguments with distinct particle labels can move without changing their
parameter bindings. Missing, repeated, and incorrect labels are compile errors.
Arguments must be pure expressions; I/O belongs in explicit sequences. These
restrictions are what make the reordering rule precise.

The whole file is checked before any expression executes. For example,
`(3 に 5 に 足す)` reports a duplicate `に` and a missing `を`, with a source
location. A nested `(読む)` is rejected before input is read; bind its result
with `名前 は (読む)` in a procedure or at file scope, then use `名前` as a pure
argument.

## Running the interpreter

Python 3.11+; no packages or installation required. Tested with Python 3.11.15
and 3.14.7.

```sh
git clone https://github.com/c0ze/tenioha.git
cd tenioha
python -m tenioha --eval '(5 から 3 を 引く)'
python -m tenioha examples/hello.ten
python -m tenioha examples/arithmetic.ten
python -m tenioha examples/factorial.ten
python -m tenioha examples/fibonacci.ten
python -m tenioha examples/fizzbuzz.ten
python -m tenioha examples/primes.ten
python -m tenioha examples/gcd.ten
python -m tenioha examples/collatz.ten
python -m tenioha examples/times_table.ten
python -m tenioha examples/power.ten
python -m tenioha examples/binary.ten
python -m tenioha examples/palindrome.ten
python -m tenioha examples/sort.ten
python -m tenioha examples/greeting.ten < examples/greeting.in
python -m tenioha examples/lists.ten
python -m tenioha examples/options.ten
python -m tenioha examples/closures.ten
python -m tenioha examples/closure_greeting.ten < examples/closure_greeting.in
python -m tenioha examples/nested_patterns.ten
python -m tenioha examples/compact.ten
python -m tenioha examples/aliases.ten
python -m tenioha --check examples/factorial.ten
```

The first command prints `2`, and factorial prints `720`. The greeting example
reads `Ada` from its input fixture. The list example prints `3` and `12` after
mapping and folding a generic list. `--check` checks a whole file, including
uncalled function bodies and imported modules, without executing program I/O.
`--pure` requires pure top-level statements. File execution prints only explicit
`表示する` output, while `--eval` also prints non-unit expression results.

Run the tests with:

```sh
python -m unittest discover -s tests -v
```

## A first program

```text
; Convert the integer result explicitly before displaying it.
(((5 から 3 を 引く) を 文字列にする) を 表示する)。
```

Source is UTF-8 in a `.ten` file. `;` starts a line comment and `。` is an
optional statement terminator. Nested calls need parentheses. Particles may
touch numbers and closing delimiters:

```text
(((5から 3を 引く)を 文字列にする)を 表示する)。
```

This also prints `2`. Identifier words keep their spaces: `値 を` is a name plus
a particle, while `値を` is a single name. Fully joined `5から3を引く` is not
supported.

Functions declare particle parameters and a return type:

```text
関数 差 (元: 整数) から (量: 整数) を -> 整数 {
    (元 から 量 を 引く)
}

答え は (3 を 5 から 差)。
((答え を 文字列にする) を 表示する)。
```

Alternate names and particle choices are declared explicitly:

```text
関数 加える (元:整数)に|へ (量:整数)を -> 整数 {
    (元 に 量 を 足す)
}
別名 加えます は 加える。
(((5へ 3を 加えます)を 文字列にする)を 表示する)。
```

This prints `8`. `に|へ` accepts either particle for one parameter; supplying
both is an error. The choices remain part of the type through function values,
closures, and imports. `別名` declares a spelling without automatic conjugation
or any change of effect. See [aliases.ten](examples/aliases.ten) for further
cases.

Algebraic types declare constructors under the same particle rules as
functions:

```text
型 選択<T> { 無し。有り (値: T) を }

値 は (42 を 有り<整数>)。
答え は 場合 値 {
    (無し) なら { 0 }
    (数 を 有り) なら { 数 }
}。
((答え を 文字列にする) を 表示する)。
```

Matches must cover every constructor combination. `参照 引く` produces a
function value, and `(5 から 3 を 適用 参照 引く)` applies it and returns `2`.
Function types preserve particle order and effects. The
[language guide](docs/LANGUAGE.md) covers generic functions, matching, and
relative module imports.

Omitting the function name creates a closure. Each result below retains the
increment from its own factory call:

```text
関数 加算器 (増分: 整数) で -> 関数[整数 を -> 整数] {
    関数 (値: 整数) を -> 整数 { (値 に 増分 を 足す) }
}

十増やす は (10 で 加算器)。
(((5 を 適用 十増やす) を 文字列にする) を 表示する)。
```

This prints `15`. Creating a closure delays its body, but the entire body is
still checked before program I/O. Anonymous `手続き` values retain their IO
effect.

Patterns can unpack several constructor levels at once. The first matching arm
runs, and `_` handles the remaining cases:

```text
型 選択<T> { 無し。有り (値: T) を }
値 は ((42 を 有り<整数>) を 有り<選択<整数>>)。
答え は 場合 値 {
    ((数 を 有り) を 有り) なら { 数 }
    _ なら { 0 }
}。
((答え を 文字列にする) を 表示する)。
```

This prints `42`. A non-exhaustive match reports an uncovered pattern, and an
arm completely covered by earlier arms is rejected as unreachable.

## Familiar algorithms

These standalone examples use the existing language, with expected output in
each matching `.out` file. The playground includes all 23 repository examples.

| Example | Technique | Default output |
|---|---|---|
| [Fibonacci](examples/fibonacci.ten) | Linear accumulator recursion | First 12 numbers, `0` through `89` |
| [FizzBuzz](examples/fizzbuzz.ten) | Pure decisions and ordered printing | 1 through 30, with Fizz/Buzz/FizzBuzz substitutions |
| [Prime numbers](examples/primes.ten) | A typed predicate and trial division | Primes between 2 and 50 |
| [Greatest common divisor](examples/gcd.ten) | Euclid's algorithm | `21` and `6` |
| [Collatz](examples/collatz.ten) | Even/odd branching and a recursive sequence | The sequence from 7 to 1 |
| [Multiplication table](examples/times_table.ten) | Nested recursion building each row as text | The 9x9 table (九九) |
| [Exponentiation](examples/power.ten) | Squaring, one call per bit of the exponent | `1024`, `243`, and `1` |
| [Binary representation](examples/binary.ten) | Recursion on the quotient, concatenating digits | `0`, `5`, `10`, and `255` in base 2 |
| [Palindromic numbers](examples/palindrome.ten) | Digit reversal with an accumulator | Four numbers with their reversals |
| [Insertion sort](examples/sort.ten) | Library lists, a fold, and floor-division comparison | `5 3 9 1 4`, then sorted |

Use the input ranges described in each file. These are small teaching programs,
and the interpreter's 1024-active-call limit still applies. The final call in
each file can be changed locally or in the
[browser playground](https://c0ze.github.io/tenioha/#example=fibonacci).

To build and serve the website locally, run `python scripts/serve_site.py` and
open `http://127.0.0.1:8765`. The site build uses Python's standard library;
browser tests use Playwright. See [PLAYGROUND.md](docs/PLAYGROUND.md) for setup
and checks.

---

## Prior art, and credit

**[Kip](https://github.com/kip-dili/kip)**, by Joomy Korkut, is the direct
inspiration: a Turkish language in which grammatical case and verb form take
part in static checking. Its implementation is MIT licensed. The local research
checkout is `../kip`, and the inspected revision is recorded in the research
notes.

**[なでしこ / Nadesiko](https://nadesi.com/)** already supports Japanese
particle arguments, argument reordering, and polite syntax. Tenioha cannot
claim those ideas as new. Its focus is a small functional core with strict
particle signatures, ordinary static types, and checked effects.

Japanese needs its own design rather than a translation of Kip's case names:

- `は` marks topic and must not silently substitute for `が`.
- A particle's role depends on the predicate; `に`, `で`, and `と` are not
  universal type categories.
- Explicit word boundaries avoid the need for a morphological analyser.
  Unrestricted Japanese text and automatic verb conjugation would require more
  machinery.
- Politeness is a possible surface feature. Purity, effects, and permissions
  should have explicit semantics independent of register.

## Scope and limitations

The question under test is whether Japanese argument roles make typed
functional programs readable and teachable. The syntax is meant to follow from
actual examples and reader feedback; the author lives in Japan and speaks the
language.

The current implementation has no type inference, no `の` projections, no `て`
chaining, no unrestricted unspaced Japanese, and no conjugation engine. A
repeated `に` within one signature is rejected rather than disambiguated by
type. The evaluator caps at 1024 active calls. This is a reference interpreter
rather than a compiler, and no claim of research novelty is made here: that
would require a literature review that has not been done.

One intended application is the hard mode of a programming game,
`~/projects/games/commit/commit+++`.

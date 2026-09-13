# てにをは / Tenioha

A programming language where **Japanese particles are checked parts of function signatures**.

> *てにをは* (tenioha) is the traditional Japanese term for the grammatical
> particles — named after て・に・を・は themselves. Idiomatically it means
> whether a sentence's grammar holds together: *「てにをはが合わない」* is
> what you say when someone's particles are wrong.

Status: **0.7.0 is implemented:** a Python reference interpreter with
typed particle calls, user-defined functions/procedures, immutable bindings,
recursion, lazy conditionals, checked I/O, algebraic data types, explicit generics,
exhaustive nested constructor matching, function values, and modules. Generic list and
option libraries are included. Anonymous functions and procedures capture immutable
lexical values. Matches support ordered arms and wildcard fallbacks, with missing
and unreachable cases rejected before execution. Particles can touch integers
and closing delimiters; identifier words keep explicit boundaries. Explicit
alternate function names and parameter-specific particle choices preserve
the same types, effects, and canonical argument order.

- [Milestone progress and agent handoff](HANDOFF.md)
- [Current language and builtins](docs/LANGUAGE.md)
- [Recorded language decisions](docs/DECISIONS.md)
- [Investigation of Kip and Japanese prior art](docs/RESEARCH.md)
- [Proposed Japanese core and implementation milestones](docs/DESIGN.md)

---

## Run it

Python 3.11+; no packages or installation required. Tested with Python 3.14.7.

```sh
git clone https://github.com/c0ze/tenioha.git
cd tenioha
python -m tenioha --eval '(5 から 3 を 引く)'
python -m tenioha examples/hello.ten
python -m tenioha examples/arithmetic.ten
python -m tenioha examples/factorial.ten
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

The first command prints `2`; factorial prints `720`. The greeting example
reads `Ada` from its input fixture. `--check` checks the whole file, including
uncalled function bodies and imported modules, without executing program I/O.
The list example prints `3` and `12` after mapping and folding a generic list.
`--pure` requires pure
top-level statements. File execution prints only explicit `表示する`
output; `--eval` also prints non-unit expression results.

Run the tests with:

```sh
python -m unittest discover -s tests -v
```

## A first program

```text
; Convert the integer result explicitly before displaying it.
(((5 から 3 を 引く) を 文字列にする) を 表示する)。
```

Save UTF-8 source as a `.ten` file. `;` starts a line comment and `。` is an
optional statement terminator. Nested calls need parentheses. Particles can
touch numbers and closing delimiters:

```text
(((5から 3を 引く)を 文字列にする)を 表示する)。
```

This also prints `2`. Keep spaces between identifier words: `値 を` uses a
particle, while `値を` is one name. Fully joined `5から3を引く` is not supported.

Functions declare particle parameters and their return type:

```text
関数 差 (元: 整数) から (量: 整数) を -> 整数 {
    (元 から 量 を 引く)
}

答え は (3 を 5 から 差)。
((答え を 文字列にする) を 表示する)。
```

Declare alternate names and particle choices explicitly:

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
or any effect change. See [aliases.ten](examples/aliases.ten) for more examples.

Algebraic types declare constructors with the same particle rules as functions:

```text
型 選択<T> { 無し。有り (値: T) を }

値 は (42 を 有り<整数>)。
答え は 場合 値 {
    (無し) なら { 0 }
    (数 を 有り) なら { 数 }
}。
((答え を 文字列にする) を 表示する)。
```

Matches must cover every constructor combination. `参照 引く` produces a function value;
`(5 から 3 を 適用 参照 引く)` applies it and returns `2`. Function types
preserve particle order and effects. See [the language guide](docs/LANGUAGE.md)
for generic functions, matching, and relative module imports.

Omit the function name to create a closure. Each result below retains the
increment from its own factory call:

```text
関数 加算器 (増分: 整数) で -> 関数[整数 を -> 整数] {
    関数 (値: 整数) を -> 整数 { (値 に 増分 を 足す) }
}

十増やす は (10 で 加算器)。
(((5 を 適用 十増やす) を 文字列にする) を 表示する)。
```

This prints `15`. Creating a closure delays its body; the entire body is still
checked before program I/O. Anonymous `手続き` values retain their IO effect.

Patterns can unpack several constructor levels at once. The first matching arm
runs, and `_` handles any remaining cases:

```text
型 選択<T> { 無し。有り (値: T) を }
値 は ((42 を 有り<整数>) を 有り<選択<整数>>)。
答え は 場合 値 {
    ((数 を 有り) を 有り) なら { 数 }
    _ なら { 0 }
}。
((答え を 文字列にする) を 表示する)。
```

This prints `42`. A non-exhaustive match reports an uncovered pattern; an arm
completely covered by earlier arms is rejected as unreachable.

## The idea

In most languages an argument's meaning comes from its **position**:

```python
subtract(5, 3)   # which one is the minuend? you have to remember
```

Tenioha uses **particles** to identify argument roles:

```
(5 から 3 を 引く)
(3 を 5 から 引く)
```

Both calls mean “subtract 3 from 5” and return `2`. Here `から` marks
the starting value and `を` the amount subtracted. The signature checks both
the particle and the ordinary value type, such as `整数` (integer).

Arguments with distinct particle labels can move without changing their
parameter bindings. Missing, repeated, or incorrect labels are compile
errors. Arguments must be pure expressions; I/O belongs in explicit sequences.
These restrictions make the reordering rule precise.

The whole file is checked before any expression executes. For example,
`(3 に 5 に 足す)` reports duplicate `に` and missing `を`, with a source
location. A nested `(読む)` is rejected before input is read. Bind its result
with `名前 は (読む)` in a procedure or at file scope, then use `名前` as a
pure argument.

---

## Prior art, and credit

**[Kip](https://github.com/kip-dili/kip)**, by Joomy Korkut, is the direct
inspiration: a Turkish language with grammatical case and verb form involved
in static checking. Its implementation is MIT licensed. The local research
checkout is `../kip`; the inspected revision is recorded in the research notes.

**[なでしこ / Nadesiko](https://nadesi.com/)** already supports Japanese
particle arguments, argument reordering, and polite syntax. Tenioha cannot
claim those ideas as new. Its proposed focus is a small functional core with
strict particle signatures, ordinary static types, and checked effects.

Japanese needs its own design rather than a translation of Kip's case names:

- `は` marks topic and must not silently substitute for `が`.
- A particle's role depends on the predicate; `に`, `で`, and `と` are not
  universal type categories.
- Explicit word boundaries can avoid a morphological analyser. Unrestricted
  Japanese text and automatic verb conjugation require more machinery.
- Politeness is a possible surface feature. Purity, effects, and permissions
  should have explicit semantics independent of register.

---

## Why build it

To explore whether Japanese argument roles make typed functional programs
readable and teachable. The person starting it lives in Japan and speaks the
language; actual examples and reader feedback should drive the syntax.

One possible application is the hard mode of a programming game:
`~/projects/games/commit/commit+++`.

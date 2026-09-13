## Tenioha 0.7.0 — independent audit report

Model: Claude Opus 5 (1M context), `claude-opus-5[1m]`.
Baseline `40c2e08`, read-only. I made no repository changes; the `HANDOFF.md` modification present in the working tree is the orchestrator's own audit-tracking paragraph (it predates my first read).

### Bottom line

**No correctness, type-soundness, effect-isolation, or security-boundary defects found.** Everything the docs promise that I could test, held. The three findings below are minor (one diagnostic-quality inconsistency, one cosmetic display inconsistency, one doc nit) plus one unreachable-from-CLI robustness nit.

---

## Probes run

| Probe | Result |
|---|---|
| `python -m unittest discover -s tests` on Python 3.14.3 | 305 pass |
| Same suite on Python 3.11.15 (the documented floor; HANDOFF says only 3.14.7 was verified) | **305 pass** — closes a stated verification gap |
| All 13 `examples/*.ten` run + byte-compare against `.out` fixtures + `--check` | 13/13 match, all check clean |
| ~20 README/`LANGUAGE.md` snippets re-executed verbatim (incl. deliberate-error examples) | all produce the documented result |
| Limits: expression nesting 100/120/127/128/130; import chains 127 vs 130 files; 4096 vs 4097-digit literals; 1024 call depth; 20 000 top-level statements; 500 000-char string; 256-arm match | all give `E_DEPTH`/`E_IMPORT_DEPTH`/`E_INTEGER`/`E_CALL_DEPTH` diagnostics, no `RecursionError`, no traceback; limits match the documented numbers exactly |
| Match-coverage fuzz vs. independent brute-force oracle: 4 000 random arm sets over a 2-field/2-ctor pair, + 5 000 over a 3-ctor pair and a nested wrapper type, depth 3 | **0 mismatches** on both exhaustiveness and unreachability |
| Token-level parser fuzz, 60 000 random token strings | 0 non-`Diagnostic` exceptions |
| Template semantic fuzz, 30 000 generated programs (closures, matches, aliases, generics, blocks, conditionals) | 0 crashes |
| **Differential fuzz vs. a hand-written Python reference model**, 20 000 programs — particle→slot mapping under argument permutation, canonical evaluation order (incl. which `割る` raises first), closure capture/shadowing, block scoping, match binding, alias call sites | **0 mismatches**, 606 of them exercising division-by-zero ordering |
| Effects-before-IO sweep: 19 distinct error classes (tokenize, parse, duplicate type/function, alias cycle/unknown, bad particle choice, unknown type, return type, pure-context IO, coverage, unreachable arm, closure body, nested IO, missing/cyclic import, module body, type args, depth), each preceded by `表示する` + `読む` | **no output written, stdin position 0 in every case** |
| Type-soundness probes: phantom type parameters, generic substitution through function-typed constructor fields, type-variable escape via closures, choice-set exactness, nominal identity across modules and constructor aliases | all correctly rejected/accepted |
| Module probes: diamond imports, alias re-export chains, matching a value whose type is not importable, `E_MATCH_EXHAUSTIVE` label selection when only an alias is visible | correct; diagnostics pick a *visible* qualified label |
| CLI: `--check --pure`, `--pure --check <file>`, `--eval`+`--check`, usage/exit codes, NUL-byte filename | as documented (exit 2 usage, 1 error, `--pure` rejects top-level IO under `--check`) |
| Stress cases bounded with `RLIMIT_AS` 2–3 GB, `RLIMIT_CPU` 25–60 s, subprocess timeouts | no OOM, no runaway; worst wall time 0.7 s |

---

## Findings

### F1 — `別名` in a nested scope reports a generic `E_SYNTAX` instead of `E_DEFINITION` (Low, confirmed)

**File:** `tenioha/syntax.py:593` (and the test that pins it: `tests/test_aliases.py:184`)

**Repro**
```sh
python -m tenioha --eval '{ 別名 甲 は 足す }'
python -m tenioha --eval '関数 f -> 整数 { 別名 甲 は 足す。 1 }'
```

**Observed**
```
<eval>:1:3: E_SYNTAX: Expected a value or a parenthesized call.
```
**Expected** (by analogy with every other file-scope-only construct):
```
E_DEFINITION: Declarations and imports are only allowed at file scope.
```
`型`, `取込`, and named `関数`/`手続き` all produce `E_DEFINITION` in exactly the same position.

**Root cause:** 0.7 added `別名` to `KEYWORDS` (`syntax.py:12`) but not to the keyword set at `syntax.py:593`:
```python
if token.kind == "KEYWORD" and token.value in {"関数", "手続き", "型", "取込"}:
    raise Diagnostic("E_DEFINITION", "Declarations and imports are only allowed at file scope.", token.span)
```
So `別名` falls through to the catch-all `E_SYNTAX` at the end of `expression()`.

**Fix:** add `"別名"` to that set, and update `tests/test_aliases.py:184` from `"E_SYNTAX"` to `"E_DEFINITION"`. `HANDOFF.md`'s "Known limits" already says aliases "cannot be declared inside a block", so the message should say so.

Related, lower-value, and *not* 0.7-specific: `関数 別名 -> 整数 { 1 }` reports `E_SYNTAX: Expected -> before the closure return type` because any keyword after `関数` routes to the closure path. Behaviour is correct (`別名` is reserved, as documented in the compatibility note); only the wording is confusing. I would not change this without a broader "keyword used as a name" diagnostic.

---

### F2 — An aliased constructor prints under the alias spelling, so identical values display differently (Low, confirmed, cosmetic)

**File:** `tenioha/core.py:171` (`format_value` uses `item.constructor.name`); origin `tenioha/core.py:605` (`Compiler.aliases` does `replace(signature, name=declaration.name.name, identity=signature.key)`).

**Repro**
```sh
python -m tenioha --eval '型 箱<T> { 包む (値:T)を|に } 別名 包みます は 包む。 (7に 包みます<整数>) (7を 包む<整数>)'
```

**Observed**
```
(7 を 包みます)
(7 を 包む)
```
**Expected:** both are the same constructor of the same nominal type — `docs/LANGUAGE.md` states "a constructor alias is the same constructor for nominal typing and exhaustiveness checking" — so a reader can reasonably expect one canonical rendering.

**Root cause:** an alias is a `Constructor` whose `identity`/`key` is the target's but whose `name` is the alias. `DataValue` stores whichever `Signature` the call site resolved, and `format_value` renders `.name`. Semantics are unaffected: `_bind_pattern` (`core.py:646`) compares `.key`, so matching, exhaustiveness, and nominal identity are all correct — this is display only.

Note the asymmetry that makes this worth mentioning: `Checker.match` deliberately builds a canonical `labels` map (`core.py:418-421`, first-registered name wins) so `E_MATCH_EXHAUSTIVE` *does* render canonically. Value display does not use that mechanism.

**Fix (optional):** render `DataValue` via the same canonical-label lookup, or store the defining `Constructor` (resolve `identity` back through `Program.types`) rather than the alias signature. `docs/LANGUAGE.md` does say displays "are not a source serialization format", so leaving it and documenting the alias behaviour explicitly is also defensible.

---

### F3 — `docs/LANGUAGE.md:274` alias example has an arity trap (Info / doc nit)

```
Alias a whole generic declaration, then supply type arguments at its calls or
references: `別名 写します は 写す` followed by `参照 写します<整数>`.
```
The only `写す` in the project is `lib/list.ten`'s `写す<T, U>` (and `lib/option.ten`'s, also two-parameter), both also listed in the library table of the same document. A reader who wires the example to either gets `E_TYPE_ARGUMENTS: 写します expects 2 explicit type argument(s), received 1`. The paragraph is schematic (it never declares `写す`), so this is ambiguity rather than an error — but using a one-parameter name, or `参照 写します<整数, 文字列>`, would remove the trap.

---

### F4 — Uncaught `ValueError` for an entry filename containing NUL (Info; not reachable through the CLI)

**File:** `tenioha/__main__.py:30`, `except (OSError, UnicodeError)` at `:44`.

**Repro** (embedding only — `execve` cannot carry a NUL in argv, so no shell can trigger this):
```python
from tenioha.__main__ import main; main(['a\x00b.ten'])
# ValueError: embedded null byte  -> Python traceback
```
`Compiler.load` already catches `ValueError`/`RuntimeError` for *import* paths (`core.py:519`); the entry-file read does not. One-line fix: add `ValueError` to the `__main__` except tuple. Low value — include only if you want the "no traceback ever" property to hold for the embedding entry point too.

---

## Explicitly checked and found correct (no finding)

Recording these so the same ground isn't re-covered:

- **Alias resolution** — forward targets, chains (1 500 links, iterative), self- and mutual cycles, unknown targets, collisions with builtins/constructors/functions/other aliases, qualified import targets, explicit re-export, NFC normalization, and `Signature.key` preservation across modules. `Compiler.aliases` (`core.py:588-610`) cannot `IndexError` on `path[-1]`: a name already registered by an earlier chain exits the `while` with `path == []` but also skips both raise sites.
- **Particle choices** — `FunctionType.__post_init__` sorts choices for canonical form; this never reorders *parameter slots*, so argument ordering and runtime `zip(function.parameters, actual)` stay aligned. Choice sets are compared exactly; `に|へ` ≡ `へ|に`; substitution preserves `aliases`.
- **Generic substitution** — `TypeVariable` owners are namespaced (`function:<key>` / `type:<identity>`), so same-named parameters in different declarations and modules cannot alias. Bodies are checked once parametrically; runtime bodies are shared (no expansion). Phantom parameters and function-typed fields substitute correctly.
- **Closure lifetime** — `capture_names` (`core.py:268-297`) correctly models sequential bindings, arm bindings, transitive nested-closure captures, and shadowing; I could not construct a `KeyError` at `scope[name]` in `_evaluate`.
- **Evaluation order** — callee first, then arguments in canonical slot order; verified by both stack analysis and 606 differential division-by-zero orderings.
- **Effects** — arguments, conditions, and match subjects are always checked with `allow_io=False`; the IO gate sits on every call; `--pure` bounds only top-level execution while procedure bodies keep their declared context, exactly as documented.
- **Coverage engine** (`patterns.py`) — matches an independent oracle on 9 000 random arm sets; the `default`/`branch`/`wrap` memoization always populates `memo[state]`, so no `KeyError`; the 50 000-state budget fires as `E_MATCH_COMPLEXITY` before any IO. Runtime `E_MATCH` ("No match arm accepts this value") appears unreachable.
- **Module loading** — dependency-before-importer ordering, `loaded`/`active` cycle handling, canonical-path identity with repeated aliases, diamond imports, rejection of absolute/empty paths and of imports under `<eval>`, and `E_IMPORT_CYCLE`/`E_IMPORT_DEPTH` spans (never `None`, since the root can reach neither).
- **Reader** — integer+particle splitting (signed, leading zeros, 4096-digit cap, chunked parse independent of `PYTHONINTMAXSTRDIGITS`), identifier words never split, `5から3を引く`/`値を` rejected as documented, string escapes, CRLF, comments, NFC with original spans.
- **Recursion budget** — every deep walk (`format_value`, `_bind_pattern`, `capture_names`, `Coverage.*`, `_evaluate`) is iterative; the remaining Python-recursive paths (`Checker.check`, `TypeEnvironment.resolve`, `substitute`, `Compiler.load`) are each bounded by `MAX_NESTING`/`MAX_IMPORT_DEPTH` and do not stack with one another, leaving ample headroom under the default 1 000-frame limit.

I did not flag the documented absences (no sandbox, arbitrary-precision integers, fixed recursion limits, no inference, unimplemented roadmap features) as defects, per the brief.

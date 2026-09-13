# Tenioha 0.7.0 independent audit

**Reviewer:** Grok 4.6
**Tree:** `/home/arda/projects/tenioha` at `40c2e08` (`audit/multi-model-0.7`)
**Baseline:** `python -m unittest discover -s tests` → **305 passed** (Python 3.14.3)

No in-language semantic bugs showed up in coverage oracles, matching, effects-before-IO, alias identity, call/import/match budgets, or CLI `--check`. The confirmed issues are diagnostic/comment-boundary problems.

---

## Confirmed findings

### 1. Low — indirect-call argument diagnostics disagree with direct calls

**Where:** `tenioha/typesys.py:54-71` (`FunctionType` sorts each slot’s particles and rewrites the primary label); `tenioha/core.py:349-368` (`roles()` reports `missing` using `p.particle`); `tenioha/core.py:461-466` (適用 builds `Parameter`s from that sorted `FunctionType` and passes `expression.head.name` `"適用"`).

**Repro:**
```text
関数 受ける (値:整数)へ|に -> 整数 { 値 }
(受ける)
(適用 参照 受ける)
```

**Observed:**
```text
<input>:1:31: E_ARGUMENTS: 受ける: missing: へ.
<input>:1:31: E_ARGUMENTS: 適用: missing: に.
```
(`1を` instead of a valid label is the same split: `missing: へ; unexpected: を` vs `適用: missing: に; unexpected: を`.)

**Expected:** The same missing slot, with the same label set (and a name that is not the keyword `適用`). Both `へ` and `に` are valid; evaluation order is already correct (slot order, not written order / sort order).

**Root cause:** Direct calls use `Signature.parameters` (declared first particle). 適用 uses `FunctionType.parameters` after `__post_init__` replaces the primary particle with `sorted(choices)[0]` (`に` < `へ`). `roles()` then prints that primary, and the call head is always `適用`.

**Fix:** Keep declared (or fully listed) choice sets for diagnostics. For example report `missing: へ|に` from `p.choices` (sorted for stability), and pass a display name other than the `適用` keyword. Do not use the sorted primary as the only missing label. Type equality can keep using the sorted form.

---

### 2. Low — `;` comments only end at LF, so a Unicode line separator after `;` comments out the rest of the line

**Where:** `tenioha/syntax.py:95-98`

**Repro:**
```sh
python -m tenioha --eval $';x\u2028(3 を 5 から 引く)'
```
Same with a file containing `; skip` + U+2028 + a `表示する` statement: `Path.read_text` keeps U+2028 (unlike `\r` / `\r\n`, which universal newlines map to `\n`).

**Observed:** exit 0, empty stdout (comment runs to EOF or the next `\n`, so the call never runs).

**Expected:** U+2028 (and U+2029 / U+0085) behave as line breaks: the comment ends, the following call runs and prints `2`. Docs say “`;` begins a comment through the end of the line” and “newlines are whitespace.” Outside comments, those characters already count as `isspace()` separators.

**Root cause:** Comment skipping uses `text.find("\n", pos)` only. Tokenizer whitespace is `str.isspace()`, which includes Unicode line separators, but comments and `Span.line` do not.

**Fix:** End comments (and count lines) on the same set of line breaks, at least `\n`, `\r` (when not part of `\r\n`), U+2028, U+2029, and U+0085.

---

## Unverified concerns / optional design notes (not bugs in the language)

- **`DataValue` / `FunctionValue` Python `==` follows surface `Signature.name` (and builtin aliases also set `identity` from `None` to the original name).** `(7を 包む)` and `(7を 包みます)` share `constructor.key` and match as the same constructor, but `run(...) == run(...)` is `False` and `format_value` differs. In-language matching is fine; tests already compare `.key`. Optional: `name: field(compare=False)` on `Signature`, and/or compare data by `key` + fields. Document that hosts should not use `==` on algebraic results.
- **`compile_source(..., functions=)` replaces the whole builtin table** (tests that need both do `{**BUILTINS, extra}`). `run()` does not accept `functions`. LANGUAGE.md embedding section omits this. Document replace-vs-merge.
- **Zero-arg `FunctionType.value` is `関数[ -> 整数]`** (space before `->`). Source `関数[-> 整数]` still parses; it only shows up in `E_TYPE` text.
- **`filename` is the entry module’s identity, not just a directory base.** `run('取込 「lib.ten」 と L。(L.一)', filename=str(lib_path))` is `E_IMPORT_CYCLE` because that path is already the entry. Tests use a distinct entry path; worth a sentence in the embedding docs.

---

## What was checked (no further confirmed defects)

| Area | Result |
|---|---|
| Nested / correlated coverage | Independent oracles: 1156 three-colour 2-field sequences; 729 two-colour 3-field 2-arm sequences; 125 option-of-colour 3-arm sequences; targeted 3-field 3-arm “any-red” hole reports `(青,青,青)`; mixed-arity enum; mutual `A`/`B` types; incomplete recursive lists. No false exhaustive / false unreachable / runtime `E_MATCH`. |
| Coverage termination / budget | Incomplete binary tree, 80-ctor enum, 6-field 3-colour product: all finished in ≪1s with `E_MATCH_EXHAUSTIVE` (not a hang, not a silent pass). |
| Call / import / nesting limits | User recursion: 1023 OK, 1024 `E_CALL_DEPTH`. Closures/`適用` of named functions count. Constructors do not bypass the user-call cap. Import-chain depth still diagnosed. |
| Effects before IO | Nested `(読む)` in arguments and `適用` callees rejected with streams untouched. `--check` of alias IO does not read stdin. Unused match-arm IO is checked and not executed. |
| Aliases / choices | Direct and `適用` accept both labels; canonical exception order follows **slot** order, not written order. Constructor aliases share `.key` and coverage. 1500-link alias chains already in the suite. |
| Embedding | Missing on-disk entry filename still resolves relative imports; default `<input>` rejects imports; `--eval` import is `E_IMPORT`. |
| CLI | `--pure --check` rejects top-level IO; 4096-digit literals still work with `PYTHONINTMAXSTRDIGITS=640`. |

---

## Probes run

- Full suite: `python -m unittest discover -s tests` (305 OK).
- `/tmp/tenioha_audit_probes.py`, `probes2.py`, `probes3.py`: coverage oracles, mutual/recursive patterns, particle-choice eval order, `適用` vs direct diagnostics, tab caret vs column, FunctionType display, `functions=` replacement, `run(functions=)`, IO re-execute, call-depth off-by-one, match-complexity timing, parser junk, `--eval` import / `--check` alias IO, CR/CRLF/U+2028/NEL comments, embedding filename = import path, mixed-arity match, BOM `--eval`, unused procedure/`--pure`, closure capturing aliased builtin.
- CLI subprocesses with 10–20s timeouts; no unbounded stress loops.

No repository files, git state, or dependencies were changed.

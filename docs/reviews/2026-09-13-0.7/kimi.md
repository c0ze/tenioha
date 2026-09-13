All probes complete. The codebase held up well across ~120 adversarial probes. Here is my independent audit report.

---

# Independent Audit — Tenioha 0.7.0 (baseline 40c2e08)

**Scope:** full project (not just the 0.7 diff). Read README.md, docs/LANGUAGE.md, HANDOFF.md, docs/DECISIONS.md, docs/DESIGN.md, all six `tenioha/*.py` modules, `lib/*.ten`, and the test suite listing. **Baseline reproduced:** `python -m unittest discover -s tests` → 305 passed, 0 failures (Python 3.14.7). All 13 examples match their `.out` fixtures (including both `.in` greeting fixtures). No repository files were modified; all probes ran in `/tmp/tenioha_probe`.

**Probes run:** reader/Unicode/compact boundaries (22), nesting limits for calls/blocks/conditionals/types/patterns/function-types incl. mixed-depth stress (18), effects-before-IO and evaluation order (11), closures/captures (9), aliases and particle choices (11), pattern coverage (23), modules/imports (18), `読む` line-ending semantics (10), CLI exit codes/flags/stderr rendering (17), coverage-complexity stress up to 400 diagonal arms (fast, no hang), call-depth limit at 1023/1024/1025, 4096/4097-digit literals, 2^1000 display, 900-deep value formatting, diamond/symlink/self/cyclic imports, import depth 128 vs 129, plus ~20 misc semantic checks.

## Confirmed bugs (both minor)

### 1. `別名` in nested contexts yields `E_SYNTAX` instead of `E_DEFINITION` — LOW

- **Location:** `tenioha/syntax.py:593`
- **Repro:** `python -m tenioha --eval '{ 別名 x は 引く。1 }'`
- **Observed:** `E_SYNTAX: Expected a value or a parenthesized call.` — same for `別名` inside function bodies, conditionals, and match arms.
- **Expected:** consistency with every other declaration keyword — `{ 型 箱 { 包む }。1 }` yields `E_DEFINITION: Declarations and imports are only allowed at file scope.`
- **Root cause:** `Parser.expression()` checks `token.value in {"関数", "手続き", "型", "取込"}` for the file-scope-only diagnostic; `"別名"` was never added to that set when it became a keyword in 0.7.
- **Suggested fix:** add `"別名"` to the set at `syntax.py:593`. Still rejected before any I/O either way; this is a diagnostic-code/message quality issue only.

### 2. `compile_source`/`run` reject a leading BOM that file-based entry accepts — LOW

- **Location:** `tenioha/core.py:625` (`compile_source` passes `text` straight through); file paths use `utf-8-sig` at `tenioha/__main__.py:23` and `tenioha/core.py:519`.
- **Repro:** `python -c "import tenioha; tenioha.run('﻿(3 を 5 から 引く)')"` → `E_TOKEN: Invalid token '\ufeff'` at 1:1.
- **Observed vs expected:** LANGUAGE.md promises "Files are UTF-8, with an optional initial BOM", and CLI/imported files honor that; an embedder who reads a file with plain `utf-8` and passes the string to `compile_source`/`run` gets a confusing token error on the same document.
- **Root cause:** tokenizer (`syntax.py:83`) treats U+FEFF as a word character; no BOM strip on the embedding path.
- **Suggested fix:** strip one leading `"\ufeff"` in `compile_source` (or document that the API expects BOM-less text). Consistency argues for stripping.

## Unverified concerns / informational

3. **Depth budget not accumulated for closure parameter types** — `Parser.parameters()` (`syntax.py:415-426`) calls `self.type_expression()` with default `depth=0`; `closure(depth)` (`syntax.py:474`) doesn't thread its depth in. A closure nested 126 blocks deep can contain a parameter type nested 127 deep (~253 total nesting) without `E_DEPTH`. I stress-tested the worst combinations (126 blocks + 127-deep function types, 126 blocks + 126-deep generic types): no `RecursionError`, comfortable margin under Python's 1000-frame limit. LANGUAGE.md's "nesting limit of 128 levels" reads as a uniform bound, so this is a spec-uniformity gap with no crash attached. Fix (optional): pass `depth` into `parameters()` and on to `type_expression(depth)`.

4. **`repr()` on deep `DataValue` recurses** — dataclass-generated `__repr__` on a 900-deep list value raises `RecursionError`. The interpreter itself never reprs values (CLI/`--eval` uses the iterative `format_value`, verified safe at 900+ depth), so this only bites an embedder who prints `execute()` results. Optional: `field(repr=False)` on `fields` or a depth-capped `__repr__` on `DataValue` (`core.py:24-27`).

5. **`読む` strips a lone trailing `\r` that is not part of a line ending** — `_read` (`core.py:215`) does `removesuffix("\n").removesuffix("\r")`, so input `"abc\r"` (no newline, e.g. classic-Mac ending) returns `"abc"`. Verified CRLF, LF, blank-line-vs-EOF, inner `\r` preservation all correct; this is a defensible reading of "without its line ending" but does delete a content byte in the corner case. Worth a doc word at most.

6. **Portability: case-variant import paths on case-insensitive filesystems** — module identity is `str(Path(filename).resolve())` (`core.py:500`), which resolves symlinks (verified: symlinked import shares nominal identity) but not case. On macOS/Windows, importing the same file as 「util.ten」 and 「Util.ten」 would produce two module identities with nominally distinct same-named types. Cannot verify on this case-sensitive Linux system; suggest `os.path.normcase` on the key or a documented note.

## Areas explicitly verified clean (no findings)

- **Reader/compact boundaries:** all 8 particles attach to integers (incl. `-0005から`), NFD particles normalize with separate spans, identifier words never split (`5から3を引く`, `5は`, `5なら`, fullwidth digits all correctly rejected), float/dot rejection, escapes, 4096-digit limit at both boundaries.
- **Nesting:** 127/128 accepted, 129/300/500 rejected with `E_DEPTH` (never `RecursionError`) for calls, blocks, conditionals, matches, patterns, type arguments, function types.
- **Effects-before-IO:** nested `読む` in arguments/blocks/conditions, errors in later statements and uncalled bodies — all prevent any program output/input; runtime failures correctly don't undo earlier output (documented).
- **Evaluation order:** canonical parameter order confirmed stable under written permutation via division-by-zero span; `適用` callee evaluates first; unselected branches/arms never execute.
- **Aliases/choices:** chains (1500-link), cycles (span on cycle-closing target), unknown targets, builtin/procedure/constructor aliases, constructor alias = same coverage case, choice-set exact type equality, `へ|に` ≡ `に|へ`, duplicate-label detection, re-exports, hoisting.
- **Patterns/coverage:** correlated pairs (`(赤,青)` reported missing), unreachable arms (incl. alias arms), cross-level NFC duplicate bindings, foreign constructors, empty match, missing-case rendering; 400-arm diagonal match checks in 0.08s.
- **Modules:** relative resolution independent of CWD, diamond sharing, cycle/self-import/depth (128 ok, 129 `E_IMPORT_DEPTH`), module-body rejection, BOM in imported files, nominal type distinction across files.
- **CLI:** exit codes 0/1/2, `--check` (passes with runtime errors present, counts correct, no execution), `--pure` (rejects top-level IO, allows unused 手続き), `--eval` (unit not echoed, import rejected), missing file/invalid UTF-8 → clean exit 1, tab/wide-char caret alignment correct.
- **Docs:** README, LANGUAGE.md, DECISIONS.md, DESIGN.md, HANDOFF.md all match the implementation; grammar in LANGUAGE.md matches the parser; no stale claims found.

No security boundary promised by the docs was found violated; documented non-goals (no sandboxing, no inference, recursion/digit limits) were not counted as findings. Model/version: not disclosed by this runtime, so not reported.

**Bottom line:** two confirmed low-severity bugs (`E_DEFINITION` inconsistency for nested `別名`, BOM handling on the embedding API), four informational concerns. Nothing blocks the 0.7.0 baseline.

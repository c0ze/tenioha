# Tenioha 0.7.1 — bounded final closeout

## **PASS** — land `65867a8`

No blocking findings. All accepted audit findings are resolved at the inspected implementation, and the final correction (`94f5b09..65867a8`) is independently verified.

---

## What was inspected

- **Implementation commit inspected: `65867a8`** ("Preserve source bytes through decoding and reject duplicate BOMs"), branch `audit/multi-model-0.7`, baseline `40c2e08`.
- Implementation diff `40c2e08..65867a8` restricted to code/tests: `tenioha/{__init__,__main__,core,syntax,typesys}.py`, `tests/{test_aliases,test_cli,test_deep_types,test_source_input}.py` — 9 files, +387/−32.
- Final correction `94f5b09..65867a8` code surface: `tenioha/core.py` (new `read_source`, import path), `tenioha/__main__.py` (entry path), `tests/test_source_input.py` (+56), plus docs.
- `git status --porcelain -- tenioha tests examples lib` is **empty**: the working tree changes are documentation/review files only, so the tested implementation is exactly `65867a8`.
- Read `docs/AUDIT-0.7.md` (current on-disk version), my own `claude.md`, `claude-depth-followup.md`, `claude-final.md`, and `codex-round-1.md` (the trigger for the final correction). I did not rely on the other reviewers' round-2 conclusions.

## Runtimes actually used

| Invocation | Version | Executable |
|---|---|---|
| `python` | 3.14.3 | `/home/arda/.local/share/mise/installs/python/3.14.3/bin/python` (via shim `/home/arda/.local/share/mise/shims/python`) |
| `python3.11` | 3.11.15 | `/home/arda/.local/bin/python3.11` → `/home/arda/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3.11` |

**Runtime discrepancy to record:** `docs/AUDIT-0.7.md:77` and `README.md` state "3.11.15 and 3.14.7". Python 3.14.7 is **not installed on this machine**; the only 3.14 available is 3.14.3. I verified on 3.11.15 and 3.14.3. Non-blocking, but the doc should say 3.14.3 unless the 3.14.7 run is re-done elsewhere.

---

## Checks actually run

**Test suites at `65867a8`** — `322 passed` on 3.11.15 and `322 passed` on 3.14.3 (run twice, start and end of session; identical).

**A1 — composed generic type operations** (both interpreters, identical results):

| Case | Result |
|---|---|
| 110-level generic instantiated with a 110-level type argument, compared inside 125 nested blocks | **compiles**, checked result type depth **220** (confirming composed depth exceeds the 128 source-nesting limit) |
| Same shape with a type error | **`E_TYPE`**, no `RecursionError`, no traceback |
| Same, preceded by `表示する` + `読む` | `E_TYPE` with `stdout=''` and `stdin` position `0` — effects-before-I/O intact |

**Codex's round-1 regression** — his exact reproduction, `printf '\357\273\277\357\273\2771' | python3.11 -m tenioha --check /dev/stdin`, now exits 1 with `/dev/stdin:1:2: E_TOKEN`. Single-BOM control exits 0. `--eval` with the same double-BOM text produces the identical code and `1:2` location. **File and string input paths are back in parity.**

**Shared file reading / single BOM** — entry file vs. import, both interpreters:

| Source prefix | Import path | Entry path |
|---|---|---|
| no BOM | accepted | accepted |
| one BOM | accepted | accepted |
| two BOMs | `E_TOKEN@1:2` in `lib.ten` (the importing module's own path) | `E_TOKEN@1:2` |

**Literal line endings** — for all six documented breaks (LF, CRLF, CR, U+0085, U+2028, U+2029), a string literal round-trips byte-identically through the entry file (verified at the byte level on stdout, e.g. CRLF emits `b'\xe5\x89\x8d\r\n\xe5\xbe\x8c\n'`), through an imported module, and through the embedding API — all three agree.

**`read_source` error paths** — NUL in path, missing file, directory, and invalid UTF-8 all return CLI exit 1 with a `tenioha:` message and **no traceback**; an invalid-UTF-8 import becomes `E_IMPORT`.

**Guard quality of the final correction** — the four new `test_source_input.py` tests run against the pre-correction implementation (`94f5b09`) **fail 4/4** (5 with subtests): `test_double_bom_entry_file_is_rejected`, `test_import_reader_accepts_exactly_one_bom_and_preserves_spans`, `test_file_and_import_strings_preserve_literal_line_endings` (CR and CRLF), `test_import_diagnostics_keep_original_crlf_text_and_bom_offsets`. They are real regressions, not tautologies.

**Remaining accepted findings re-confirmed at HEAD** — A2 `E_DEFINITION` for `別名` in block / function body / conditional arm; A4 `missing: に|へ` identically for direct and indirect calls; A6 corrected generic alias example executed against `lib/list.ten` (returns `'1'`); A7 NUL entry filename → rc 1, no traceback.

**Examples** — all 13 match their `.out` fixtures and pass `--check` on both interpreters.

Per the brief I did not repeat the broad fuzz campaigns from my earlier reports (79,800 type-equality pairs vs. a recursive oracle, 20,000-program differential semantics, 5,000-case match-coverage oracle, 40,000-input reader fuzz); `tenioha/typesys.py` and `tenioha/syntax.py` are byte-identical between `94f5b09` and `65867a8`, so those results carry forward unchanged.

---

## Non-blocking notes

1. **Documentation handoff (orchestrator already on it).** `HANDOFF.md:123` still reads "Latest verification: **305 tests passed** on Python 3.14.7" — that is the stale 0.7.0 paragraph, now superseded by 322. `HANDOFF.md:31,48` and `docs/AUDIT-0.7.md:92` still say round 2 is in progress. Note that `docs/AUDIT-0.7.md:6`'s "305 tests" is **correct** as written — it describes the untouched baseline and should not be changed.
2. **3.14.7 vs 3.14.3** in `README.md` and `docs/AUDIT-0.7.md:77`, as above.
3. Carried forward from my prior report, unchanged and still optional: VT/FF/U+001C–U+001E do not end comments (deliberate closed set at `docs/LANGUAGE.md:83-85`); `test_composed_generic_types_compare_inside_deep_blocks` only reproduces the old failure on 3.11-era frame accounting (the 600-level test is the version-independent guard); trailing whitespace exists only in verbatim-retained reviewer files.
4. **Release-note item, not a defect:** `read_source`'s `newline=""` means CR/CRLF inside string literals in a file are now preserved verbatim rather than translated to LF. I confirmed this at the byte level. It is the intended A5/Kimi correction and matches "strings preserve their contents without normalization", but it is the most user-visible semantic change for anyone editing on Windows and deserves a line in the release notes.

No documented non-goals were reopened.

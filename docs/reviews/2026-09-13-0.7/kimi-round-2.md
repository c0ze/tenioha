All verification complete. Final report:

---

# Final Review Round 2 — `94f5b09..65867a8` (read_source / double-BOM / literal newlines)

**Verdict: PASS.** The double-BOM regression Codex caught is fixed correctly, literal CR/CRLF preservation now holds across all input paths, and no regressions were found.

## What the diff does

`tenioha/core.py:625-628` adds `read_source(path)`, which opens with `encoding="utf-8"` and `newline=""` — no BOM stripping, no universal-newline translation — and routes both entry-file reads (`__main__.py:23`) and import reads (`core.py:519`) through it. BOM handling is now centralized in the tokenizer's single-BOM skip (`syntax.py:93-94`), so files, imports, `--eval`, and embedding share one rule. `grep` confirms no `utf-8-sig`/`read_text` remains in `tenioha/`.

## Checks actually run

- **Suites:** 322 tests pass on Python 3.14.3 and 3.11.15 (both executed here).
- **BOM matrix (0/1/2/3 BOMs × embed, `--eval`, entry file, import):** exactly one initial BOM accepted on all four paths; two or more rejected with `E_TOKEN` at `1:2`, attributed to the correct source file (entry span for entry errors, library span for import errors) and before any program I/O.
- **Codex's exact round-1 repro** (`printf '\357\273\277\357\273\2771' | python3.11 -m tenioha --check /dev/stdin`): now fails with `E_TOKEN` at 1:2 on both interpreters (previously accepted). Single BOM via `/dev/stdin`, `--eval`, file, and import still accepted; BOM-only file remains a valid empty program.
- **Line-ending matrix:** all six boundary forms (LF, CRLF, CR, U+0085, U+2028, U+2029) inside string literals are preserved byte-exactly through embed, `--eval`, entry file, and imported functions, on both interpreters — including a string containing all six forms and BOM-prefixed files. A CLI file run emits the exact original bytes plus the display newline.
- **Error paths:** invalid-UTF-8 entry → `tenioha:` exit 1 without traceback; NUL filename → exit 1 (A7 path intact); directory entry → exit 1; invalid-UTF-8 import → `E_IMPORT` with the importer's span. These work unchanged with the `newline=""` open mode.
- **Diagnostic alignment:** a BOM'd entry file's error reports `1:7` with the caret under the offending particle — identical to the embedding expectation from round 1; a BOM'd importing file renders its own span correctly.
- **Regression sweep:** 20-case diagnostic-render diff vs baseline `40c2e08` → 0 differences; all 13 examples still match `.out` fixtures; baseline probe batches (reader 22, semantics 29) re-run with identical outcomes.
- **Docs:** AUDIT-0.7.md and HANDOFF.md updates match the code (double-BOM disposition, newline-preservation note, 322-test count); LANGUAGE.md's new sentence ("Entry files and imports use the same reader and preserve literal CR/CRLF characters without newline translation") is accurate — this also records the behavioral correction I flagged as a doc note in round 1.

No reproducible issues found in the bounded diff; no new suggestions. Model/version: not disclosed by this runtime, so not reported.

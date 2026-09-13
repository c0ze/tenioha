# PASS

`65867a8` fixes the round-1 double-BOM split and file-literal newline rewrite. Entry files and imports now decode like embedding/`--eval`: UTF-8, no `utf-8-sig`, `newline=""`, and **only** `tokenize` drops a single leading BOM.

## Corrections

**Double BOM.** `read_source` (`tenioha/core.py:625-628`) leaves `\ufeff` in the decoded text. A second BOM is `E_TOKEN` at column 2 on embedding, `--eval`, `--check --eval`, CLI files (run and `--check`), and imports, with no program output. One BOM still works on all four channels; token offsets stay on the original text (`span.start == 1`).

**Literal newlines.** File/import strings keep LF/CRLF/CR/U+0085/U+2028/U+2029. Import diagnostics keep the raw source, including a leading BOM and CRLF (`test_import_diagnostics_keep_original_crlf_text_and_bom_offsets`). CLI `--eval` and file stdout match those bytes (verified with `capture_output` in binary mode; `subprocess` `text=True` was translating `\r` in the probe, not in the interpreter).

No remaining `utf-8-sig` on production read paths.

## Checks

- `git diff 94f5b09..65867a8` for `core.py`, `__main__.py`, `tests/test_source_input.py`, LANGUAGE.md
- `python -m unittest discover -s tests` → **322 OK** (3.14.3)
- `python3.11 -m unittest discover -s tests` → **322 OK** (3.11.15)
- `tests.test_source_input` on 3.11
- Probes: 0/1/2 BOMs on embedding, `--eval`, CLI files, imports; `read_source` keeps one and two BOMs; Codex-style `\xef\xbb\xbf\xef\xbb\xbf1 --check`; all six line endings in strings on all four channels; import diagnostic text/line for BOM+CRLF

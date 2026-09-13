# PASS

Land **0.7.1** at **`65867a8`** (`audit/multi-model-0.7`). No blocking findings. Documented non-goals were not reopened.

Inspected implementation: `65867a8a80e4ab784cad94f2318368db4a6e6365`
Baseline: `40c2e08`. Final correction: `94f5b09..65867a8`.

## Accepted findings

| ID | Closeout |
|---|---|
| **A1** composed generics | Iterative eq/hash/text/substitute. `作る`/`取得` of 110-deep `箱` inside 125 blocks runs on 3.11 with no `RecursionError`. Identity, owners, slot order, exact choice sets, and effects still hold. |
| **A3/A5 file reading** | `read_source` (`core.py:625-628`) is `encoding="utf-8", newline=""` for CLI files and imports. Only `tokenize` drops one leading BOM. Two BOMs are `E_TOKEN` at column 2 on embedding, `--eval`, files/`--check`, and imports, with no program IO. File/import string CRLF is preserved in raw stdout/values. |
| **A2, A4, A6, A7** | Unchanged from the earlier pass (`E_DEFINITION` for nested `別名`; missing roles `に\|へ` on direct and `適用`). |

`utf-8-sig` is gone from production reads. The double-BOM split from round 1 is gone.

## Runtimes

- `python` → Python 3.14.3, `/home/arda/.local/share/mise/installs/python/3.14.3/bin/python`
- `python3.11` → Python 3.11.15, `/home/arda/.local/bin/python3.11`

## Checks

- `git rev-parse HEAD` = `65867a8`; `git diff 94f5b09..65867a8` for `core.py`, `__main__.py`, `test_source_input.py`
- `python -m unittest discover -s tests` → **322 OK**
- `python3.11 -m unittest discover -s tests` → **322 OK**
- `tests.test_deep_types` + `tests.test_source_input` on both
- 3.11 probes: 110-deep types in 125 blocks; type-contract asserts; 1 vs 2 BOMs on four channels; `read_source` keeps two BOMs; file/import CRLF literals in binary stdout / returned strings

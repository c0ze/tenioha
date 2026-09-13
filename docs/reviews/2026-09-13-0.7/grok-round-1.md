# PASS

0.7.1 on `audit/multi-model-0.7` (`94f5b09`) fixes the accepted findings without breaking the type or reader contracts. No blocking regression.

## Accepted findings (this review)

| ID | Status |
|---|---|
| **A4** (Grok) missing `へ\|に` | **Fixed.** Direct and 適用 both report `missing: に\|へ.` `適用` stays the call-site label, as documented. |
| **A5** (Grok) comment/line boundaries | **Fixed.** LF/CRLF/CR/U+0085/U+2028/U+2029 all end comments and advance `Span.line`; CRLF counts once; string contents unchanged. |
| DataValue `==` / `適用` as name / `functions=` replace / entry `filename` identity / nullary `関数[ -> …]` space | **Not reopened.** Dispositions in `docs/AUDIT-0.7.md` match the code and LANGUAGE.md. |

A1 (composed-type stack), A2 (`別名` → `E_DEFINITION`), A3 (one initial BOM), A6 (generic alias example), A7 (NUL filename) are in place and behave as described.

## Type-system contract (main risk)

Iterative `_type_equal` / `_type_hash` / `_type_text` / `substitute` in `tenioha/typesys.py` preserve:

- **Nominal identity** — `DataType.name` is display-only; different `identity` values are unequal
- **Generic owners** — `TypeVariable("T", "a")` ≠ `TypeVariable("T", "b")`; substitute follows owner
- **Exact choice sets** — `に` ≠ `に\|へ`; `に\|へ` == `へ\|に` (and same hash)
- **Slot order** — `(に, を)` ≠ `(を, に)`
- **Effects** — `関数` ≠ `手続き`

`tests/test_deep_types.py` (600-level + 110/125 composed source) passed on **Python 3.11.15 and 3.14.3**. Extra 400-deep eq/hash/text/substitute probes did not `RecursionError`.

## Checks performed

- `git diff 40c2e08..HEAD` (code, tests, LANGUAGE/DECISIONS/AUDIT)
- `python -m unittest discover -s tests` → **318 OK** (3.14.3)
- `python3.11 -m unittest discover -s tests` → **318 OK** (3.11.15)
- Targeted 3.11: `test_deep_types`, `test_source_input`, `test_aliases`
- Probes: A4/A5/A2/A3; type identity/owners/slots/choices/effects; 400-deep iterative ops; type error still before IO
- Examples: `aliases.ten`, `nested_patterns.ten`, `compact.ten`, `lists.ten` match fixtures

## Non-blocking notes (not FAIL)

- `HANDOFF.md` / `docs/AUDIT-0.7.md` still say final review is in progress; that is the placeholder the user said would be replaced after reviews.
- `docs/reviews/2026-09-13-0.7/grok.md` has trailing whitespace (`git diff --check`); original report text, not runtime.
- `except ValueError` in `tenioha/__main__.py:37` is broader than NUL paths; it matches A7 and does not change language diagnostics.

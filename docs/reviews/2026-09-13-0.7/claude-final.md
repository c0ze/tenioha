# Final review — Tenioha 0.7.1 audit fixes (`40c2e08..HEAD`)

## **PASS** — no blocking findings

Reviewed through `65867a8` (the tree gained `65867a8` and two untracked round-1 review files while I was reviewing; all results below were re-run against that final state).

---

## Verification of my accepted findings

| ID | Status | Evidence |
|---|---|---|
| **A1** composed-type `RecursionError` | **Fixed** | `PYTHONPATH=. python3.11 /tmp/tenioha-audit-YEdpGq/deep_types.py` → `(値 を 適用 操作) OK` / `(値 に 1 を 足す) E_TYPE`. Valid source compiles, invalid source diagnoses, no traceback. |
| **A2** `別名` file-scope diagnostic | **Fixed** | `E_DEFINITION` now in block, function body, conditional arm, match arm, and call-argument positions (I checked all five; the tests cover three). |
| **A4** missing-role choice sets | **Fixed** | Direct and indirect both report `missing: に|へ`; single-choice slots unchanged (`missing: を`). |
| **A6** generic alias doc example | **Fixed and executed** — `別名 写します は 列.写す` + `参照 写します<整数, 文字列>` runs correctly against `lib/list.ten`. |
| **A7** NUL entry filename | **Fixed** | `main(['bad\0name.ten'])` → rc 1, `tenioha: embedded null byte`, no traceback. |
| **A3/A5** (not mine; verified anyway) | **Fixed** | One initial BOM accepted on every path; two rejected at `1:2` in entry *and* import; all six line-break forms end comments and advance diagnostic lines. |

`docs/AUDIT-0.7.md` dispositions of my F2 (alias display) and F4 are reasonable and are now stated as contract in `docs/LANGUAGE.md:39-40` and the embedding section — not silently dropped.

---

## Main risk area: the iterative type operations

This was the part worth real scrutiny. It holds up.

**Differential fuzz against a recursive reference implementation** (`_type_equal`, `_type_hash`, `_type_text`, `substitute` vs. hand-written recursive equivalents of the 0.7.0 semantics): 6,000 randomly generated types — mixed `DataType`/`FunctionType`/`TypeVariable`/`ValueType`, varying display names, shared subtrees, multi-particle choice groups, both effects — plus **79,800 pairwise equality comparisons**. **0 mismatches**, and `hash(a) == hash(b)` for every equal pair.

**22 targeted invariant assertions**, all passing:

- *Nominal identity*: same `identity` + different display name → equal **and** same hash; same name + different `identity` → unequal. (`name` correctly stays out of both `__eq__` and `__hash__`, matching the old `field(compare=False)`.)
- *Generic variable owners*: `TypeVariable("T","f:a") != TypeVariable("T","f:b")`, including 600 levels deep inside a structure.
- *Exact choice sets*: `に|へ == へ|に`, `に|へ != に`, `に|へ != に|で`.
- *Slot order*: `[整数 から, 整数 を] != [整数 を, 整数 から]`; slot types compared positionally.
- *Effects*: `関数[...]` ≠ `手続き[...]`.
- Cross-kind and foreign-object comparisons return `False`/`True` correctly via the `NotImplemented` path; deep `dict`/`set` membership works.

**Mechanism checks.** `DataType.__eq__/__hash__` and `FunctionType.__eq__/__hash__` are the hand-written ones (`__qualname__` confirms the `@dataclass` generator did not overwrite them — `_set_new_attribute` skips `__eq__`, and an explicit `__hash__` suppresses `_hash_add`). The `id()`-keyed memo tables in `_type_equal`/`_type_hash`/`substitute` are safe: every keyed object is reachable from a root that stays alive for the walk (in `_type_equal` the roots are rebound, but the caller's `self`/`other` keep them alive), and type structures are acyclic, so the two-phase `(False, …)/(True, …)` protocol always resolves children before parents. `_type_text` reproduces the old rendering exactly, **including** the leading space in the nullary `関数[ -> 整数]` form — no incidental formatting drift.

**Guard quality.** `tests/test_deep_types.py` genuinely guards: run against the 0.7.0 `tenioha/` it fails **4/4 on 3.11** and **1/4 on 3.14** (the 600-level pure-`typesys` case is version-independent).

---

## Regression checks

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **322 pass on 3.11.15 and on 3.14.3** |
| Match-coverage vs. brute-force oracle, 5,000 random arm sets | 0 mismatches |
| Differential semantics fuzz, 20,000 programs (particle→slot mapping under permutation, canonical evaluation order incl. division-by-zero ordering, closures/captures, shadowing, blocks, matches, aliases) | 0 mismatches |
| Reader/checker fuzz, 40,000 inputs seeded with BOM/CR/CRLF/NEL/LS/PS/VT/FF | 0 uncaught host exceptions; all 38,994 diagnostics rendered without crashing |
| Effects-before-IO sweep, 17 error classes incl. the new deep-type `E_TYPE` | no stdout written, stdin position 0 in every case |
| `Span.line`/`Span.column` old vs. new formulas, 300 random LF sources × every offset | identical — no location regression |
| All 13 examples vs. `.out` fixtures + `--check` | 13/13 match |
| Compile performance vs. `40c2e08` (generic-heavy program; `compact.ten` ×20) | 0.021s vs 0.021s; 0.070s vs 0.071s — no measurable cost |
| New decoding (`read_source`, `newline=""`) end-to-end: LF/CRLF/CR/LS files, BOM, double BOM, entry + import, byte-level stdout | all correct; double BOM rejected at `1:2` with the *module's own* path |
| `git diff --check` on `tenioha/ tests/ README.md HANDOFF.md docs/{LANGUAGE,DECISIONS,AUDIT-0.7}.md` | clean |

---

## One behavior change worth release-note prominence (not a defect)

`read_source` (`tenioha/core.py:626-629`) opens with `newline=""`, so **CR and CRLF inside string literals in a file are now preserved verbatim** instead of being translated to LF by `read_text`. I confirmed at byte level: a CRLF-saved source printing a multi-line 「…」 emits `b'a\r\nb\n'`, where 0.7.0 emitted `b'a\nb\n'`.

This is correct per `docs/LANGUAGE.md` ("Strings … preserve their contents without normalization" / "These characters inside strings retain their original contents") and is the intended A5 correction — but it is the single most user-visible semantic change in the diff for anyone editing on Windows, so it deserves a line in the release notes rather than only the decisions log.

---

## Optional (design ideas, not bugs — no action required)

1. **VT/FF/FS/GS/RS still do not end a comment.** `; ignored` + `U+000B`/`U+000C`/`U+001C`–`U+001E` still swallows the next statement (`run("; ignored\x0c7") == []`). This is pre-existing, unchanged by the diff, and consistent with the now-closed enumeration at `docs/LANGUAGE.md:83-85`. Worth knowing that Unicode UAX#14 classes VT and FF as *mandatory* breaks and Python's `str.isspace()`/`splitlines()` include all five — so `LINE_BREAK` is a deliberate subset. Either adding VT/FF or noting the exclusion would close the last gap in A5's class.
2. **`test_composed_generic_types_compare_inside_deep_blocks`** (110 type levels / 125 blocks) only fails against old code on 3.11-era frame accounting; on 3.14 it passes either way. The 600-level test carries the version-independent guarantee, so coverage is adequate — but pinning `sys.setrecursionlimit` inside the composed test would make it guard on every interpreter, matching the depth-based robustness of its sibling.
3. **BOM'd files now report column +1 on line 1** (offsets preserved by design; `_display_width` skips `\ufeff` so the caret is correctly aligned). Only the numeric column differs from what an editor shows on that one line — flagging it as intended, not broken.
4. **Trailing whitespace in `docs/reviews/2026-09-13-0.7/grok.md:3-4`** — verbatim-retained third-party text, correctly excluded from scope. If `HANDOFF.md` re-asserts "`git diff --check` passed", scope that claim to code/authored docs.
5. I could verify only **Python 3.14.3** locally; the `3.14.7` figure in `README.md:32` and `docs/AUDIT-0.7.md` is unverifiable in this environment (3.11.15 matched exactly).

No reopened non-goals: sandboxing, arbitrary precision, recursion/nesting limits, absence of inference, and the deferred roadmap items are untouched.

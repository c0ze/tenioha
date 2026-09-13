All verification complete. Closeout report:

---

# Tenioha 0.7.1 Audit — Final Closeout (bounded)

**Verdict: PASS — the implementation is ready to land.** No blocking findings remain.

**Commit inspected:** `65867a8` ("Preserve source bytes through decoding and reject duplicate BOMs") on `audit/multi-model-0.7`, i.e. implementation HEAD; full implementation diff `40c2e08..65867a8` with the final correction `94f5b09..65867a8`. Working tree carries only documentation changes (AUDIT-0.7.md wording, whitespace normalization in review reports, untracked round reports) — no implementation drift since my round-2 review.

**Runtimes actually used** (recorded fresh):
- `python` → `/home/arda/.local/share/mise/shims/python` → **Python 3.14.3**
- `python3.11` → `/home/arda/.local/bin/python3.11` → **Python 3.11.15**

## Checks actually run (all fresh, independent reproductions from my own /tmp scratch)

1. **Test suites:** 322 tests pass on both interpreters (`python -m unittest discover -s tests` → OK 322; same under `python3.11`).
2. **A1 composed generic types:** baseline `40c2e08` (extracted via `git archive` to /tmp) raises `RecursionError` on python3.11 for the 110+110-level composed type inside 125 nested blocks; HEAD `65867a8` compiles it on both 3.11.15 and 3.14.3 (result type depth 220). The iterative type equality/hash/render/substitute preserve nominal identity, generic owners, choice sets, slot order, and effects (verified by contract probes in my earlier rounds and the suite's 600-level cases).
3. **Final correction — shared file reading/single BOM:** BOM matrix 0/1/2/3 across embedding, `--eval`, entry file, and imports — exactly one initial BOM accepted on every path; two or more rejected with `E_TOKEN` at 1:2 attributed to the correct source file, before any I/O. Codex's exact round-1 reproduction (`printf` double-BOM piped to `python3.11 -m tenioha --check /dev/stdin`) exits 1 with `E_TOKEN`. `read_source` (`core.py:625`) is the sole file-decoding path; no `utf-8-sig`/`read_text` remains in `tenioha/`.
4. **Final correction — literal line endings:** all six boundary forms (LF, CRLF, CR, U+0085, U+2028, U+2029) inside string literals are preserved byte-exactly through embed, `--eval`, entry files, and imported functions, on both interpreters, including a string containing all six forms.
5. **Fixtures and spot checks:** all 13 examples match their `.out` fixtures; nested `別名` → `E_DEFINITION` (A2); direct and indirect missing-role diagnostics both report `に|へ` (A4); `main(['bad\0name.ten'])` → exit 1, clean `tenioha:` message, no traceback (A7); `--version` reports `Tenioha 0.7.1`.

## Notes

- Documented non-goals (constructor-alias display/host equality, `適用` label, closure annotation depth budget, deep host `repr`, lone-CR `読む`, case-insensitive filesystem identity, builtin-mapping replacement, nullary function-type display space) remain accepted dispositions; not reopened.
- HANDOFF.md/AUDIT-0.7.md still contain the obsolete 305-test/review-in-progress paragraphs in the committed text; the orchestrator is finalizing those to the verified 322-test, review-complete status separately. That is documentation bookkeeping, not an implementation concern.
- Model/version: not disclosed by this runtime; not guessed.

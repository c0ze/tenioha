FAIL: independently confirmed the double-BOM regression against the baseline; no other actionable regressions found. On Python 3.11.15 and 3.14.3, 287 tests passed per interpreter; 31 encountered unavailable temporary-directory errors under the read-only sandbox. Additional checks passed: 1,000 type rendering/substitution/hash cases, 20,000 equality comparisons, deep structural invariants and shared-DAG probes, compilation of all 13 examples, and the corrected documentation alias example.

Review comment:

- [P2] Strip the initial BOM in only one input layer — /home/arda/projects/tenioha/tenioha/syntax.py:93-94
  For files beginning with two BOMs, `__main__.py:23` and `core.py:519` already remove one through `utf-8-sig`; this new skip removes the second. Consequently, file input now accepts source that embedding and `--eval` reject with `E_TOKEN`, violating the documented one-BOM limit. Minimal reproduction: `printf '\357\273\277\357\273\2771' | python3.11 -m tenioha --check /dev/stdin` incorrectly succeeds. The baseline rejects this input. Centralize BOM handling in the reader and cover double-BOM entry files and imports.

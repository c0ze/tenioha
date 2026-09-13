All checks complete. Final report:

---

# Feature Review — `feature/examples-playground` @ `7535edf` (diff `8d83495..7535edf`)

**Verdict: PASS — no release blockers.**

The interpreter is untouched (no `tenioha/*.py` or `lib/*.ten` in the diff); the branch adds 5 algorithm examples, the static introduction, the Pyodide playground, build/serve tooling, tests, and the Pages workflow, as documented.

## Checks actually run

- **Native suites:** 334 tests pass on both interpreters available here — `python` = `/home/arda/.local/share/mise/shims/python` (3.14.3) and `python3.11` = `/home/arda/.local/bin/python3.11` (3.11.15). (HANDOFF cites 3.14.7; this machine's shim is 3.14.3 — no behavioral difference observed.) `git diff --check` clean.
- **New examples:** fibonacci, fizzbuzz, primes, gcd, collatz all run and match their `.out` fixtures; catalog descriptions match actual program semantics (the nonnegative-input guidance is honest — violating it hits the documented call/time limits).
- **Build artifact:** `scripts/build_site.py` → `dist/` contains exactly the 5 named assets + `examples.json` (18 entries, source/expected/input read byte-exact via `read_source`) + `runtime.json` (real `tenioha/*.py`, `lib/*.ten`, `runner.py`, version 0.7.1) + `.nojekyll`. No `{{VERSION}}` placeholder left; no audit/dev files. Catalog-id validation blocks path traversal; destination guard blocks overwriting the repo.
- **`/tenioha/` prefix:** served `dist/` through a `/tenioha/` path prefix — all assets (index, CSS, JS, worker, favicon, both JSON bundles) resolve with correct MIME types (`text/javascript` for module/worker scripts). All references are relative (`./…`, `import.meta.url`, `self.location`), confirming the no-origin-root claim.
- **Security:** no `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`/`eval` anywhere in site code; program output, diagnostics, and catalog text go through `textContent` only; source is passed to Python as a function argument (verified in `worker.js`/`runner.py`), never interpolated. `serve_site.py` binds 127.0.0.1 only.
- **Adapter probes (native `site/runner.py`):** source/input limits enforced exactly at 100,000/20,000 and rejected at +1; output capped at exactly 64,000 on both the `表示する` path and the non-unit echo path with the documented message; static errors produce no output while runtime errors preserve earlier output; check mode never executes; NUL-in-string and astral characters round-trip.
- **CDN/pins:** Pyodide v0.29.3 assets (`pyodide.js`, `pyodide.asm.js`, `pyodide.asm.wasm`, `python_stdlib.zip`) all return 200 on jsDelivr; Google Fonts reachable. All six GitHub Actions are pinned by SHA — I verified each pinned SHA equals the current tag commit for its labeled major version (`git ls-remote`: checkout=v4, setup-python=v5, setup-node=v4, configure-pages=v5, upload-pages-artifact=v4, deploy-pages=v4).
- **CI/Pages:** workflow YAML parses; test matrix 3.11/3.14, Chromium job with fresh server, deploy gated to `refs/heads/master` non-PR with `pages: write`/`id-token`; `.nojekyll` present; `package-lock.json` v3 pins Playwright 1.63.0 with integrity hashes; PLAYGROUND.md correctly requires the GitHub Actions publishing source.
- **Accessibility/Japanese input:** skip link, `.sr-only` defined, `:focus-visible` outlines (orange, ≥3:1), `role="status"`/`aria-live` on runtime status, `lang="ja"` on Japanese fragments, real buttons/labels/select, reduced-motion media query plus JS scroll guard, and the Ctrl/Cmd+Enter handler checks `event.isComposing` so IME composition is not hijacked. Contrast: ink/paper ≈11:1, muted ≈4.8:1, green ≈5.5:1.
- **Claim consistency:** "18 examples" (catalog=18, browser test expects 18), "eight Chromium tests" (7+1 in the spec), 334 native tests, 10s/60s timeouts and 64k/100k/20k caps match the code, greeting prefill `Ada\n` matches `.in` fixtures, reset/download/hash behaviors match PLAYGROUND.md, hero swap demo preserves the `= 2` result per language semantics.

## Non-blocking observations (optional improvements)

1. **Low — cap unit mismatch:** the textareas' `maxlength` and the JS pre-check count UTF-16 code units, while `runner.py` counts Python code points. For astral-heavy source/input the client rejects earlier than the documented 100,000/20,000 character limits. The runner enforces the same documented numbers independently, so this fails safe; counting code points client-side would give exact parity.
2. **Info — check-output format:** the playground's Check always prints `, N type(s)` and adds "No program code was executed.", differing slightly from CLI `--check` (which omits the type count when zero). Documented playground behavior, not a parity bug.
3. **Info — serve port conflict:** `serve_site.py` hardcodes 8765 and exits with a raw traceback on `EADDRINUSE` (observed only because root's parallel test server already holds the port; the Playwright config reuses existing servers correctly). Cosmetic for manual local use.

Model/version: not disclosed by this runtime, so not reported.

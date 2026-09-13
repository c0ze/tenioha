# Feature review — examples & browser playground (`8d83495..7535edf`)

## **PASS** — no release blockers

The 30-file diff is well-built: the playground runs the *actual* interpreter sources rather than a reimplementation, output and diagnostics are text-only, external actions are SHA-pinned, and the browser suite covers the real runtime. Everything below is optional.

**Runtimes used:** `python` 3.14.3 (`/home/arda/.local/share/mise/installs/python/3.14.3/bin/python`), `python3.11` 3.11.15 (`/home/arda/.local/bin/python3.11` → uv cpython-3.11.15). HANDOFF/README claim 3.14.7; only 3.14.3 is installed here, same as during the 0.7.1 audit.

**Disclosure:** I ran the documented `python scripts/build_site.py`, which rewrites the gitignored `dist/`. No tracked file changed. The `HANDOFF.md` modification in the working tree is the orchestrator's own concurrent review-tracking edit, not mine.

---

## Checks actually run

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **334 pass** on 3.14.3 and on 3.11.15 |
| All 18 examples vs `.out` fixtures + `--check` | 18/18 match, all check clean |
| New fixtures verified by content | fibonacci 12 lines `0…89`; fizzbuzz 30; primes 15 (exactly the primes ≤ 50); gcd `21`,`6`; collatz 17 (`7…1`) — all match README/HANDOFF/catalog prose |
| `scripts/build_site.py` end-to-end | 168 KB `dist/`, `.nojekyll` present, `{{VERSION}}` fully substituted (`v0.7.1` ×2), 18 examples, `greeting`/`closure_greeting` carry `.in` input, `runtime.json` bundles the 5 real `tenioha/*.py` + both `lib/*.ten` + `runner.py` |
| Asset paths under `/tenioha/` | **zero** absolute `/`-rooted refs in built `index.html`/`styles.css`/`playground.js`/`worker.js`; worker resolves `./runtime.json` from `self.location.href`; `new URL("./worker.js", import.meta.url)` — all project-prefix safe |
| **Worker FS layout reproduced natively** (mirrored `<root>/{lib,examples}` and ran with `filename=<root>/examples/playground.ten`) | `lists`, `options`, `compact` all resolve `取込 「../lib/…」` and match fixtures — the `/playground/…` path convention is correct |
| `LimitedOutput` boundary (63 999 / 64 000 / 64 001 chars, plus a straddling two-write case) | exactly 64 000 kept, `ok:false`, partial output preserved, no negative-slice bug |
| Pinned versions resolve | `https://cdn.jsdelivr.net/pyodide/v0.29.3/full/{pyodide.js,pyodide.asm.wasm}` → **HTTP 200**; `@playwright/test` 1.63.0 present in `package-lock.json` (v3, 3/3 packages have integrity hashes) |
| Injection surface | no `innerHTML`/`insertAdjacentHTML`/`document.write`/`eval`/`new Function` in `site/`; no inline `on*=` handlers; source/input passed as **function arguments** to Python, never interpolated |
| External origins | only `cdn.jsdelivr.net`, `fonts.googleapis.com`, `fonts.gstatic.com` (+ github.com / nadesi.com links) — all disclosed in `docs/PLAYGROUND.md:26-29` |
| Palette contrast (WCAG) | ink/paper 11.33, ink/surface 12.59, muted/paper 4.92, green/paper 5.59, white-on-green 6.27, white-on-orange 4.89 — all AA. Dark console: footer 7.19, placeholder 5.70. `--orange` at 4.36 on paper is used **only** inside `aria-hidden="true"` decorative art, so it never applies to meaningful text |
| A11y primitives | skip link, `:focus-visible` outlines on every interactive role, `sr-only`, `@media (prefers-reduced-motion)`, `role="status" aria-live="polite"` on runtime status, `aria-live` on the swap demo, `aria-labelledby` per section, `<noscript>` notice, font stacks degrade without Google Fonts |
| Japanese input | `!event.isComposing` guard on the Ctrl/⌘+Enter handler (`playground.js:158-167`) — IME commit does not trigger a run; no Tab interception, so tab-out works; `lang="ja"` used consistently on prose Japanese |
| Browser-worker correctness | classic worker (no `{type:"module"}`), so `importScripts` is valid; `ready` is reset on failure so a failed load retries; `terminate()` kills a runaway worker and discards partial output; 10 s execution / 60 s load timers are armed and cleared correctly |
| CI workflow | all 5 external actions SHA-pinned with version comments; `permissions: contents: read` at top, elevated only in `deploy`; Python 3.11 + 3.14 matrix; deploy gated on `master` and `needs: [test, browser]`; `npm ci` with lockfile |
| Cross-CWD test invocation | fails from a foreign CWD — **pre-existing** (baseline `8d83495` fails the same way); the documented invocation is from the repo root |

I did not re-run the 0.7.1 language audit.

---

## Findings (all optional — none block release)

### O1 · Low · No Content-Security-Policy
`site/index.html` (head, lines 3-21) ships no CSP, and GitHub Pages cannot set headers. The worker executes code fetched from `cdn.jsdelivr.net` via `importScripts` (`site/worker.js:128`), where SRI is not available, and styles come from `fonts.googleapis.com`.
**Impact:** a CDN compromise would run arbitrary code in the page origin. Bounded: no credentials, no storage, no server.
**Fix:** add `<meta http-equiv="Content-Security-Policy">` pinning `default-src 'self'`, `script-src 'self' https://cdn.jsdelivr.net`, `worker-src 'self'`, `connect-src 'self' https://cdn.jsdelivr.net`, `style-src 'self' https://fonts.googleapis.com`, `font-src https://fonts.gstatic.com`. Verify against the Playwright suite, since a wrong `worker-src`/`connect-src` would break Pyodide. The tradeoff is already honestly disclosed in `docs/PLAYGROUND.md:26-29`.

### O2 · Low · Build destination guard misses subdirectories
`scripts/build_site.py:17` rejects `ROOT` and its ancestors but not descendants, and line 20 then `shutil.rmtree`s the destination.
**Repro:** `python -c "import sys;sys.path.insert(0,'.');from scripts.build_site import build,ROOT;build(ROOT/'tenioha')"` → deletes the interpreter package (I verified the guard returns `False` for that path; I did **not** execute the destructive call).
**Impact:** developer footgun only — no CI step or documented command passes a repo subdirectory.
**Fix:** also reject when `ROOT in destination.resolve().parents`, or require `destination.name == "dist"`.

### O3 · Low · Playground `Check` text diverges from the CLI
`site/runner.py:100-101` always emits the type clause; `tenioha/__main__.py:33` omits it when there are no types.
**Repro:** playground Check on `(5から 3を 引く)` → `OK: 1 statement(s), 0 definition(s), 0 type(s) checked.`; `python -m tenioha --check --eval '(5から 3を 引く)'` → `OK: 1 statement(s), 0 definition(s) checked.`
**Impact:** cosmetic. `index.html:137-139` ("The same interpreter powers the command line and this playground") remains true — the interpreter is identical; only the adapter's summary line differs.
**Fix:** mirror the CLI's conditional in `runner.py`.

### O4 · Low · Focus is lost when a run starts
`site/playground.js:17-25` sets `disabled` on `#run`/`#check` and reveals `#stop`. A keyboard or screen-reader user who activated **Run** has focus on a now-disabled element, so focus falls to `<body>` and Stop must be reached by tabbing from the top.
**Impact:** minor keyboard-a11y friction during the 10 s window. Ctrl+Enter is unaffected — the textareas use `readOnly` (not `disabled`), which deliberately preserves focus.
**Fix:** `$("stop").focus()` when it becomes visible, or use `aria-disabled` with a guarded handler instead of `disabled`.

### O5 · Info · Three Japanese strings in UI chrome lack `lang="ja"`
`site/index.html:181` (`<span>for 読む calls</span>`), `:184` (sr-only label "Standard input, one line per 読む call"), `:188` (`placeholder="One line per 読む call…"`). The rest of the page marks Japanese carefully.
**Impact:** screen readers may pronounce 読む with an English voice.
**Fix:** wrap each occurrence in `<span lang="ja">`.

### O6 · Info · Hard-coded example count in two places
`tests/browser/playground.spec.mjs:34` asserts `toHaveLength(18)` and `docs/PLAYGROUND.md:10` says "18 examples". `tests/test_playground.py:62-63` already enforces catalog↔`examples/` parity, so the literal adds a maintenance step without new coverage.
**Fix (optional):** assert the browser catalog length against the fetched list, or accept the two-line edit when adding an example.

### O7 · Info · Unhashed asset filenames
`index.html`, `styles.css`, `playground.js`, `worker.js` deploy under fixed names; only `examples.json`/`runtime.json` use `cache: "no-cache"`. After a redeploy, a browser could briefly pair cached JS with fresh JSON (Pages default `max-age=600`).
**Impact:** negligible for this site. Noting only.

---

## Notable strengths worth keeping

- **No second implementation.** `build_site.py:32-36` reads `examples/*.ten` and `.out` directly; `test_playground.py:66-69` asserts byte equality and re-runs every example through the adapter against its fixture. `docs/PLAYGROUND.md:47-49` claims this and it holds.
- **`read_source` reuse** (`build_site.py:23,33,38`) means the site pipeline inherits the 0.7.1 BOM and literal-line-ending guarantees instead of re-deriving them.
- **Error-path discipline:** static errors yield empty output, runtime errors preserve prior output, output limit keeps its partial buffer — verified natively and asserted in both test layers.
- **`primes`/`gcd`/`collatz`/`fizzbuzz`/`fibonacci` are checked against independent oracles** over 0–100 ranges in `tests/test_algorithms.py`, not just their fixtures.
- **Browser suite covers the real risk surface:** all 18 examples through actual Pyodide (which is what exercises the `/playground` virtual-FS import layout), Stop, the 10 s timeout, the 64 000-char cap, HTML-like output rendered as text, `#example=` deep links, download, four viewport widths with an overflow assertion, and recovery from an aborted `runtime.json`.
- **Worker choice is correct:** classic worker so `importScripts` is legal; module script on the page for top-level `await` + `import.meta.url`.

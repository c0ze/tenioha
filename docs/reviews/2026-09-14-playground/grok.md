# PASS

No release blockers. Inspected **`7535edf`** (`feature/examples-playground`, `8d83495..7535edf`). The playground is a documented disposable in-browser runner with time/output caps, not a general sandbox.

## Blockers

None.

## Non-blocking (optional)

**Low — mobile example label and download name** (`site/styles.css:1112-1132`, `site/index.html:150,158`). Below 760px the `EXAMPLE` `<label>` is `display: none` (may drop the select’s explicit name), and `#download` is shown as CSS `Save .ten` while the accessible name stays `Download .ten` (WCAG 2.5.3). Prefer `.sr-only` for the label and the same visible/accessible download string.

**Low — diagnostic filename** (`site/runner.py:27`). Errors show `/playground/examples/playground.ten`. Harmless; it is the virtual path used for `../lib/` imports.

## What holds

- **Correctness:** 18 catalog examples match fixtures; algorithm oracles (Fibonacci, FizzBuzz, primes, gcd including `(0,0)`, Collatz steps) match independent results. Check skips I/O; runtime errors keep prior output; HTML-like output is `textContent`.
- **Security:** Source/input are function arguments, not interpolated. Worker is same-origin and terminated on Stop/timeout. No host-file mounts; output is not HTML.
- **Japanese input:** Ctrl/Cmd+Enter ignores `isComposing`; Tab is not captured.
- **`/tenioha/` assets:** Site files use `./…` and `new URL(..., import.meta.url)` / `self.location.href`. GitHub `…/tenioha/` links are repo URLs, not origin-root assets.
- **CI/Pages:** Python 3.11/3.14 unit tests, Chromium, deploy from `master` only, actions pinned by commit, `path: dist`, `.nojekyll`.
- **Claims:** 18 examples, Pyodide 0.29.3, 10s/64k limits, `--eval`-style echoing — match code and tests.

## Checks

- Native: **334 OK** on Python 3.14.3 (`/home/arda/.local/share/mise/installs/python/3.14.3/bin/python`) and 3.11.15 (`/home/arda/.local/bin/python3.11`)
- `python scripts/build_site.py` into `/tmp/tenioha-pg-dist`: 18 examples, interpreter + `lib/*.ten` + `runner.py`, version substituted, relative CSS/JS
- Playwright 1.63: **8 passed (34.2s)** against existing `http://127.0.0.1:8765/` (`PLAYGROUND_URL`; this environment has `CI=true` so the config would not reuse a busy port without that URL)

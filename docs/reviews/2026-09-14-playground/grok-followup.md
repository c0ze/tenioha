# PASS

Retains the earlier **PASS** at `7535edf`. Follow-up **`5b2726d`** (`7535edf..5b2726d`) does not introduce a regression. No unresolved concrete finding in this diff.

Inspected commit: `5b2726d55b8ec9ad2d90f91b582e6cc6d0c07dc54` — wait, I should use the hash from git: `5b2726d55b8ec9ad2d90f91b582e6cc6d0f7dc54`.

The seven-file change matches the stated dispositions:

- **Focus:** Run/Check move focus to Stop; `finish()` restores only if Stop is still focused, so editor-origin runs and mid-run tab-away are not stolen. Timeout/Stop go through the same path.
- **Mobile names:** EXAMPLE is clipped/visually hidden (not `display:none`); download no longer injects `Save .ten`. Playwright asserts both names at 360–1440.
- **Build guard:** rejects repo descendants other than top-level `dist/` before `rmtree`/`mkdir`; the mock test covers `ROOT`, parent, `tenioha`, `site`, `tests`, `.git`.
- **Japanese / limits:** `lang="ja"` on 読む; placeholder is English; UTF-16 vs code-point caps are documented accurately.

Targeted check: `tests.test_playground` build-rejection and bundle tests, **OK** (Python 3.14.3). Did not re-run the full native or Chromium suites.

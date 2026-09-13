All checks complete. Final report:

---

# Bounded Follow-up Review — `7535edf..5b2726d` (playground focus + build guard)

**Verdict: PASS (retained).** No new regression and no unresolved concrete finding in the seven-file diff.

## What was checked

**`site/playground.js` (focus management):** Traced every flow. Button-origin runs (Run/Check) move focus to Stop after it becomes visible and restore focus to the initiating button on completion — only when focus is still on Stop, so a user who tabs elsewhere mid-run is not hijacked. Editor-origin runs (Ctrl+Enter) never move focus, preserving IME/editor context. `terminate()` (Stop click, timeout, failure) shares `finish()`'s restore logic; stale-worker messages remain guarded by instance/id checks; `controls(true)` unhides Stop before `.focus()`. In browsers that don't focus buttons on mouse click (e.g. Safari), the logic degrades gracefully to "no focus change" rather than error. The new browser test's assertions (Stop focused after Enter on Run, focus returned after stopping, Check refocused after check, synthetic `isComposing` keydown ignored, editor focus preserved, Tab leaves the editor) match the implementation line by line.

**`site/index.html`:** 読む fragments in the summary and sr-only label are wrapped in `lang="ja"`; the placeholder is now plain English ("One line per input call…") since placeholders can't carry markup — consistent with the duplicate-label cleanup.

**`site/styles.css`:** both changes are scoped to the `@media (max-width: 760px)` block (desktop untouched). `.example-control label` uses the standard visually-hidden pattern instead of `display: none`, restoring the select's accessible name ("EXAMPLE", asserted by the new test); the `#download { font-size: 0 }` + `::before { content: "Save .ten" }` override is removed, eliminating the duplicated accessible name — rebuilt `dist/styles.css` contains zero "Save .ten" occurrences and the test asserts accessible name "Download .ten".

**`scripts/build_site.py`:** the destination guard now resolves the path and rejects the repo, its parents, and any repo descendant except exactly `dist/` — verified empirically: ROOT, parent, `tenioha/`, `site/`, `docs/`, `.git/`, `scripts/`, and `dist/../site` (resolves into repo) all raise `ValueError` with the targets still intact afterward; default `dist/`, outside, and nested-outside destinations build 18 examples successfully. The new native test patches `rmtree`/`mkdir` to prove rejection precedes any mutation.

**`docs/PLAYGROUND.md`:** the UTF-16-code-unit vs Unicode-code-point distinction is documented accurately ("most Japanese characters count as one, while emoji and some rare kanji count as two") — this closes my earlier informational observation about cap-unit mismatch; no code change needed.

**Suites:** 335 native tests pass on both `/home/arda/.local/share/mise/shims/python` (3.14.3) and `/home/arda/.local/bin/python3.11` (3.11.15), matching root's count (334 + 1 new guard test). Root's 9 real Chromium tests were not rerun here per instructions; their assertions were verified against the code instead. Working tree remains docs-only (`HANDOFF.md` bookkeeping, uncommitted `docs/reviews/`).

No release blockers; earlier PASS stands.

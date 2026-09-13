# Follow-up review — `7535edf..5b2726d`

## **PASS** — no regression, no unresolved finding. Earlier PASS retained.

All four fixes are correct and none of them introduces a new problem. No blocking or non-blocking finding remains open from my report.

### Per-fix verification

**O2 — build destination guard (`scripts/build_site.py:16-21`).** Correct, and I exercised it independently rather than trusting the new test. 11 destinations plus a relative-traversal form, all behaving as intended: `ROOT`, `ROOT.parent`, `tenioha/`, `.git/`, `site/`, `examples/`, `dist/sub`, a non-existent subdir, and `../home/.../tenioha/tenioha` from another CWD all raise `ValueError`; `ROOT/dist`, `/tmp/…`, and a **sibling-prefix path** (`tenioha-sibling`) are allowed — so there is no string-prefix bug, and the default build path still works. Every repo subdirectory was intact afterwards. The guard is evaluated before `rmtree`/`mkdir`, and the new `test_build_rejects_source_directories_before_any_mutation` proves that properly by patching both mutators to raise; it passes in isolation.

**O4 — focus management (`site/playground.js:16,56-61,128-133`).** The state machine is sound on every path I traced:
- Capturing `restoreFocus` *before* `controls(false)` is the key detail — it reads `activeElement` while Stop is still visible, then restores after Stop is hidden, so focus is never stranded on a hidden button.
- Focus is only restored when Stop actually holds focus, so a user who tabbed away mid-run is not interrupted.
- Editor-origin runs (Ctrl/⌘+Enter) set `buttonTriggered = false`, never move focus, and leave the textarea focused (`readOnly`, not `disabled`) — the "preserve editor focus" claim holds.
- `terminate()` routes through `finish()`, so the Stop-click, 10 s timeout, 60 s load timeout, `onerror`, and the `postMessage` catch all restore identically. `focusAfterRun` is cleared at the end of every `finish()`, so no stale reference survives a run.
- Safari (which does not focus buttons on mouse click) degrades to the previous behaviour rather than misbehaving.
- `.stop` (`styles.css:663`) sets only colors, so the `hidden` attribute remains the sole visibility control and the element is focusable once shown.

**Mobile accessible names (`styles.css:1111-1120`, `index.html:181-187`).** The `#download` `font-size:0` + `::before` pair is fully removed (no leftovers anywhere in the file), so the button's name is just its real text. `.example-control label` now uses the visually-hidden clip pattern instead of `display:none`, keeping "EXAMPLE" in the accessibility tree; it matches the existing `.sr-only` utility (`styles.css:881`). I parsed the HTML: all three `for=` targets resolve to real ids and the label text is intact. The slightly wider Download label cannot cause document overflow — `.playground` is `overflow: hidden` — and root's four-width Chromium assertions cover the rendering.

**Japanese marking + docs.** Parser-verified: 読む is wrapped in `lang="ja"` in both the visible summary and the sr-only label, and the placeholder was reworded to be Japanese-free — the right call, since `placeholder` cannot carry `lang`. The `docs/PLAYGROUND.md:58-60` UTF-16-vs-code-point note is accurate for both the JS and Python limit checks.

**New browser test** is a genuine guard, not a tautology: it covers keyboard Run → Stop → return, Check → return, an `isComposing: true` keydown *not* starting a run (a real Japanese-IME regression guard), editor focus preserved after Ctrl+Enter, and Tab still escaping the textarea.

### Checks actually run

335 native tests pass on `python` 3.14.3 (`/home/arda/.local/share/mise/installs/python/3.14.3/bin/python`) and `python3.11` 3.11.15 (`/home/arda/.local/bin/python3.11`) — matching root's count; the new guard test in isolation; the independent 12-case build-destination matrix above; HTML parsed for label/`id` associations, `lang` context and tag balance; CSS inspected for leftovers, `.sr-only` consistency, `.stop` visibility and toolbar layout; `node --check` on `playground.js` (as a module) and `worker.js`. I did not repeat the full audit or the browser suite.

### Notes (not findings)

- Four Japanese strings remain unmarked — `ことば → code` and the demo legend `から = from` / `を = object` / `引く = subtract` (`index.html`, sheet decoration and glossary). I confirmed these are byte-identical at `7535edf`, so they are pre-existing, not a regression, and each already carries its English gloss inline.
- Disclosure: the guard matrix included the legitimate `ROOT/dist` case, which rebuilt the gitignored `dist/`. Scratch dirs `/tmp/tfx_out` and `tenioha-sibling` were removed and are confirmed gone. No tracked file changed by me; `git status` shows only root's own `HANDOFF.md` edit and the untracked `docs/reviews/2026-09-14-playground/`.

# Examples and playground review

Reviewed feature: `8d83495..7535edf`, adding five algorithms and a static browser
playground without changing the 0.7.1 interpreter. The original language audit
was already complete and was not repeated.

Claude, Kimi, and Grok independently returned **PASS**, with no release blockers.
Their original reports are preserved below (only trailing whitespace normalized):

- [Claude](claude.md)
- [Kimi](kimi.md)
- [Grok](grok.md)

All three also returned **PASS** for the fixes in
`7535edf..5b2726d55b8ec9ad2d90f91b582e6cc6d0f7dc54`:
[Claude follow-up](claude-followup.md), [Kimi follow-up](kimi-followup.md),
[Grok follow-up](grok-followup.md). No implementation findings remain unresolved.

## Findings and decisions

- **Keyboard focus (Claude O4): fixed.** Reproduced in Chromium: activating Run
  from the keyboard moved focus to the document body. Run/Check now focus Stop
  while busy and return focus to the initiating button when it finishes or is
  stopped. Running from the editor preserves editor focus. Focus is not stolen
  back if the user moves to another control. A browser regression covers the
  transitions, Japanese composition guard, and Tab navigation.
- **Mobile labels (Grok): fixed.** Chromium already retained the hidden EXAMPLE
  label's accessible name; it now uses visually hidden styling for consistency.
  The download button had the duplicate accessible name “Save .ten Download
  .ten” because CSS generated different text. Both desktop and mobile now show
  “Download .ten”; responsive tests assert both controls' accessible names.
- **Build destination (Claude O2): fixed.** The build helper rejects repository
  descendants other than the intended top-level `dist/`, as well as the root
  and its ancestors. A test verifies rejection before any file removal/creation;
  it mocks those operations so a future regression cannot damage the checkout.
- **Japanese UI fragments (Claude O5): fixed.** The input label and summary mark
  読む with `lang="ja"`; the placeholder uses an English description.
- **Text length units (Kimi): documented.** The browser caps UTF-16 code units,
  while the adapter independently checks Unicode code points. This can reject
  astral characters earlier and does not weaken either limit.
- **CSP (Claude O1): optional future hardening.** A policy allowing jsDelivr would
  not prevent compromise of the explicitly allowed runtime. A useful policy
  requires separate worker/WebAssembly compatibility work. External origins and
  local execution are already disclosed; no sandbox claim is made.
- **Check summary wording and virtual diagnostic filename:** retained. The
  adapter intentionally describes checking without execution, and its virtual
  path is what supports bundled relative imports. Neither changes semantics.
- **Serve-port errors, explicit catalog count, asset cache filenames:** retained
  as optional tooling improvements. The configured local port and example count
  are explicit; no offline or instantaneous cache-update guarantee is made.

## Verification

The orchestrator reran 335 native tests successfully on Python 3.11.15 and
3.14.7 after the fixes. Reviewers additionally ran their provider environments'
Python 3.14.3; those reports describe their environments, not the orchestrator's
interpreter. There are six distinct pinned GitHub Actions (Claude's report says
five); all six commit IDs were verified against the official repositories.

The existing Playwright workflow was used because no Browser-plugin skill was
available in this session. Before fixes, all eight real Chromium tests passed,
including all 18 examples, input, errors, Stop, time/output limits, downloads,
responsive widths and failed-runtime recovery. After the fixes, all **nine**
Chromium tests passed, including the new keyboard-focus regression and mobile
accessible-name assertions. Desktop and mobile screenshots were inspected, with
no page or console errors; the wider mobile download label was checked visually.
Local browser verification used Node 20.20.2 with Playwright 1.63.0 and its pinned
Chromium 153 binary; the publication workflow uses Node 22.

The [GitHub Actions publication](https://github.com/c0ze/tenioha/actions/runs/34777327550)
passed both Python jobs, the browser suite, and deployment. All nine browser tests
then passed against [the public site](https://c0ze.github.io/tenioha/) in 33.7
seconds on 2026-09-14. A separate fresh-page Fibonacci run produced the expected
sequence and no page/console errors; its full-page screenshot was inspected.
Milestone status is recorded in [HANDOFF.md](../../../HANDOFF.md).

# Tenioha 0.7 audit

Date: 2026-09-13. Baseline: `40c2e08` (0.7.0). Fix version: **0.7.1**.
The user requested independent Claude, Kimi, and Grok reviews and necessary fixes.
All three completed read-only full-project reviews through local tincan agents.
The untouched baseline passed 305 tests on Python 3.14.7 and 3.11.15; there were
no open GitHub issues at the start of the audit.

The original reports are retained verbatim. Their probe counts and model/version
claims are reviewer-reported; the verified results below are the orchestrator's
own checks. In particular, the original blanket claim that type recursion had
enough stack headroom was disproved and corrected in the follow-up.

- [Claude original report](reviews/2026-09-13-0.7/claude.md)
- [Kimi original report](reviews/2026-09-13-0.7/kimi.md)
- [Grok original report](reviews/2026-09-13-0.7/grok.md)
- [Claude verification of the composed-type failure](reviews/2026-09-13-0.7/claude-depth-followup.md)

## Accepted findings and fixes

Locations below refer to the audited baseline. All listed failures were
reproduced locally before their fixes.

| ID | Severity | Finding and trigger | Source | Fix |
|---|---|---|---|---|
| A1 | Medium | `typesys.py:43,74` and generated type equality: composing two 110-level generic types, then comparing them or formatting a type error inside 125 nested blocks raises `RecursionError` on Python 3.11. Every written annotation and expression remains within its limit. | Orchestrator; independently confirmed by Claude | Iterative type equality, consistent hashing, formatting, and substitution. Valid source compiles; invalid source reports `E_TYPE` before I/O. |
| A2 | Low | `syntax.py:593`: `{ 別名 甲 は 足す }` reports a generic expression error instead of explaining the file-scope restriction. | Claude, Kimi | Include `別名` in the `E_DEFINITION` diagnostic; cover blocks, functions, and conditional arms. |
| A3 | Low | `syntax.py:83`: `run('\ufeff(3 を 5 から 引く)')` rejects the same initial BOM accepted in a file. | Kimi | Skip one initial BOM only in the reader, preserving original spans and literal string content. File decoding leaves the BOM intact; double-BOM entries/imports are rejected. |
| A4 | Low | `core.py:349-368`: a missing `へ\|に` parameter reports only `へ` in a direct call but only `に` in an indirect call. | Grok | List the full sorted choice set for each missing slot; both forms now report `に\|へ`. |
| A5 | Low | `syntax.py:95-98`: `; ignored` followed by CR or U+2028 silently consumes the next statement on string-input paths; diagnostic lines use a different boundary rule from whitespace. File decoding also rewrites literal CR/CRLF characters. | Grok; Kimi final review; locally confirmed | Share LF/CRLF/CR/U+0085/U+2028/U+2029 boundaries between comments and source locations. Decode files without newline translation; count CRLF once and retain original offsets/string contents. |
| A6 | Documentation | `LANGUAGE.md:274`: a schematic `写す` alias example supplies one type argument although both library functions use two. | Claude | Use a qualified list-library target and `参照 写します<整数, 文字列>`. |
| A7 | Info | `__main__.py:23,37`: calling `main(['bad\0name.ten'])` directly from Python leaks `ValueError`. OS process arguments cannot contain NUL. | Claude | Convert the invalid entry filename into the normal CLI error return without a traceback. |

The composed-type regression is the most material result: source nesting alone
does not bound inferred type structure, and type operations share the host stack
with expression checking. The fix keeps the existing type contract, including
nominal identity, generic-variable ownership, effects, parameter slot order,
and unordered choices within each slot. It does not raise Python's recursion limit.

Source-input compatibility: Unicode NEL, line separator, and paragraph separator
now end comments and advance diagnostic lines. Previously they only separated
tokens outside comments. CR and CRLF have the same meaning in embedded strings
as in files. Only one BOM at the start of source is skipped.

## Findings not treated as behavioral bugs

- **Constructor alias display and host equality** (Claude F2, Grok notes): an alias
  may appear in value output, and Python dataclass equality may distinguish its
  signature. In-language nominal typing, coverage, and matching already use the
  canonical constructor key. No canonical display or host value-equality contract
  was promised; the guide now states this explicitly. Changing those APIs would
  be a separate design decision.
- **Indirect diagnostic name** (Grok A1): keep `適用` as the call-site label.
  Its callee can be a closure, conditional, factory result, or runtime function
  value; a single statically known function name is not always available. The
  misleading particle omission is fixed independently.
- **Separate closure annotation depth** (Kimi note 3): documented explicitly.
  Source annotations and composed semantic types need distinct treatment; the
  actual composed-type crash is fixed by A1.
- **Deep Python dataclass repr** (Kimi note 4): the interpreter already uses
  iterative `format_value`. The embedding guide now directs callers to it;
  recursive host repr is not the language display API.
- **Lone trailing CR from `読む`** (Kimi note 5): accepted as a line ending,
  consistent with reading a line without its ending. Other whitespace remains
  preserved. No change needed.
- **Case-insensitive filesystem identity** (Kimi note 6): unverified on this Linux
  filesystem. A blanket `normcase` change is not a portable file-identity fix
  (case behavior belongs to the filesystem). Windows/macOS filesystem testing
  remains an open portability check, not a confirmed regression here.
- **Builtin mapping replacement and entry filename meaning** (Grok notes): both
  behaviors are intentional and now documented in the embedding section.
- **Space in a nullary function-type display** (Grok note): harmless formatting;
  accepted source and type identity are unaffected.

## Verification and review status

- 322 tests pass on Python 3.11.15 and Python 3.14.7 after the implementation fixes.
- New tests cover the composed-type failures, 600-level type operations, generic
  owner/effect/choice preservation, BOM positions, six line-ending forms, mixed
  lines, comment termination, alias diagnostics, and entry-path errors.
- Baseline probes also covered 10,000 deterministic malformed token streams and
  four expression nesting shapes, with no uncaught host exceptions.
- All 13 examples match their output fixtures and pass `--check` on both versions.
  The 23 README/guide text snippets and corrected inline alias example also pass.
- 5,000 generated type comparisons/substitutions agree with an independent
  recursive oracle, including ignored display names and equal-object hashes.
- Review round 1 caught a double-BOM regression: `utf-8-sig` decoding and the new
  reader each removed one BOM. [Codex's report](reviews/2026-09-13-0.7/codex-round-1.md)
  is retained. The correction centralizes BOM handling in the reader, adds
  double-BOM entry/import tests, and preserves file string line endings noted
  by Kimi. Round 2 reviews these corrections before landing.

The interpreter remains a reference implementation with the limits documented in
[LANGUAGE.md](LANGUAGE.md). This review did not establish an untrusted-code
sandbox or test operating systems other than Linux.

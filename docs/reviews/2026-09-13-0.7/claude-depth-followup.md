## Verified: the orchestrator is right and my audit statement was wrong

```
$ PYTHONPATH=. python3.11 /tmp/tenioha-audit-YEdpGq/deep_types.py
(値 を 適用 操作) UNCAUGHT RecursionError
(値 に 1 を 足す) UNCAUGHT RecursionError
```
Python 3.11.15, repo cwd, baseline `40c2e08` (working tree differs only in `HANDOFF.md` + untracked `docs/reviews/`). Valid source does not compile; invalid source does not produce `E_TYPE`. Through the CLI it is worse than an exception — a raw Python traceback on stderr, exit 1:

```
$ PYTHONPATH=. python3.11 -m tenioha --check <that program>
  File "<string>", line 4, in __eq__
  [Previous line repeated 151 more times]
RecursionError: maximum recursion depth exceeded in comparison
```

My report's claim — *"the remaining Python-recursive paths … are each bounded by `MAX_NESTING`/`MAX_IMPORT_DEPTH` and do not stack with one another"* — is wrong on both halves for the type paths. (The `Compiler.load` half of that claim does hold: loading completes before `declare`/`check`, so import depth genuinely does not stack.)

### Root cause

Two independent recursion budgets **add**, and one of them is **not** bounded by `MAX_NESTING`:

1. **Expression/block nesting** — `Checker.check` → `block` → `statements` (`core.py:443/330/325`) costs ~3 Python frames per source level, up to the documented 128. The counterexample's 125 nested blocks contribute 376 frames.
2. **Type-structure recursion** — the checked `DataType` is ~220 levels deep even though every *written* type is ≤128. `instantiate`/`substitute` compose a 110-deep declared type with a 110-deep type argument; the parser's `depth()` limit constrains written syntax only. My audit assumed structural depth ≤ `MAX_NESTING`. It isn't.

Two distinct innermost frames, one per arm:

| Arm | Expected | Innermost frame | Frames |
|---|---|---|---|
| `(値 を 適用 操作)` (valid) | compiles | `<string>:4 __eq__` — dataclass-generated `DataType.__eq__`, 155 deep | 534 |
| `(値 に 1 を 足す)` (invalid) | `E_TYPE` | `typesys.py:43` — `DataType.value`, 207 × (property + genexpr) | 793 |

The second is the sting: the type checker correctly *detects* the error, then blows the stack **rendering the type name into the message** at `core.py:473`.

Four operations recurse over type structure; I confirmed all four raise `RecursionError` in isolation at structural depth 500 (fine at 200):

- `DataType.value` (`typesys.py:42-44`), `FunctionType.value` (`typesys.py:74-78`)
- `DataType.__eq__` and `DataType.__hash__` (dataclass-generated over `arguments`)
- `substitute` (`typesys.py:140-148`) — not what failed here, but the same defect class

Measured thresholds on 3.11.15 (t = written box depth, b = nested blocks; `t=127` → `E_DEPTH` first):

| | b=0 | b=20 | b=60 | b=100 | b=125 |
|---|---|---|---|---|---|
| valid, t=90 | OK | OK | OK | **REC `__eq__`** | **REC** |
| valid, t=110 | OK | OK | **REC `__eq__`** | **REC** | **REC** |
| invalid, t=110 | E_TYPE | E_TYPE | E_TYPE | E_TYPE | **REC `.value`** |

Neither knob alone suffices — they compose. That is the whole finding.

### Severity: **Medium**

- Real toolchain failure on the documented minimum interpreter: valid program rejected, invalid program's diagnostic lost, uncaught Python exception + traceback. Contradicts `docs/LANGUAGE.md` ("Exceeding either limit produces a language diagnostic"), README "Python 3.11+", and the repo-wide no-traceback property that `tests/test_cli.py` asserts in several places.
- **Version-sensitive, but not version-specific.** Does not reproduce on 3.14.3 (same `recursionlimit` 1000, but 3.12+ frames are far cheaper against it) — `t=120/b=125` still returns `OK`/`E_TYPE`. However, running the *identical valid program* on 3.14.3 through the documented `compile_source` embedding API from inside a 500-frame host stack **does** raise `RecursionError`. Tenioha does not own the stack budget, so "3.14 is fine" is headroom, not immunity.
- Not High: requires a deliberately pathological program (~90-110 nested generic applications *and* ~60-125 nested blocks); no incorrect acceptance or rejection (no type-soundness hole — equality either completes correctly or raises); no I/O leak, since the failure is inside `compile_source`, before execution.

### Assessment of the proposed fix

**Right direction, and sufficient for this failure — but scope it to four sites, not two, and pin the regression test's recursion limit.**

- **Iterative `value` rendering** (`DataType.value`, `FunctionType.value`): straightforward and idiomatic here — `core.format_value` and `patterns.Coverage.render` already use explicit stacks for exactly this reason, with comments saying so. Low risk.
- **Iterative equality**: the riskiest piece. It means hand-writing `__eq__` on both frozen dataclasses and walking `arguments` / `parameters` / `result_type` / `effect` / `aliases` with a work stack. This is load-bearing for *every* type decision in the language, and `DataType.name` must stay excluded (today `field(compare=False)`; two `DataType`s differing only in `name` must remain equal — relied on when one file is imported under two aliases). Worth doing, worth reviewing carefully, and worth re-running the match-coverage and differential fuzzes afterward.
- **Hash consistency is forced, not optional**: defining `__eq__` on a frozen dataclass sets `__hash__ = None` unless you also define it. The generated hash is recursive too (verified), so it needs the same treatment. Cheapest sound option is a structural hash cached via `object.__setattr__` in `__post_init__`, folded from children's already-cached hashes — O(arity) per node, no stack needed, and it must exclude `name` to match equality. Note this path is currently *latent*: I found no live site that hashes a deep `DataType`, so it is a consistency requirement rather than a second bug.
- **Add `substitute` to the scope.** It is not what failed here, but it recurses over the same unbounded structure on the hot path of every generic instantiation, and is the next thing someone will hit. `TypeEnvironment.resolve` is lower priority — it walks *written* syntax, so `depth()` genuinely bounds it.
- **What the fix leaves standing**: the `Checker.check`/`block`/`statements` half still costs ~3 frames per source level. Removing the type term drops 414 of 793 frames in the render case and 155 of 534 in the equality case, so the reported program clears with a wide margin — but the documented 128-level limits become *empirically* safe rather than *independently* safe. Proportionate response: take the iterative type ops and add a pinned regression test; making expression checking iterative too is a larger change I would not bundle here.
- **Do not reach for `sys.setrecursionlimit`** — it trades a catchable `RecursionError` for a possible C-stack segfault, and the embedding scenario above shows Tenioha cannot assume the available stack.

**Regression test (currently missing).** `tests/test_types.py` has `test_type_nesting_limit_is_a_diagnostic`, but only for *written* depth; nothing covers substituted depth. Add both arms of the counterexample asserting `OK` / `E_TYPE` — and run them under a pinned low `sys.setrecursionlimit` (e.g. 400, restored in `addCleanup`). Without pinning, the test passes vacuously on 3.14 today and guards nothing.

# Tenioha — milestone progress and agent handoff

Updated: 2026-09-14. Repository: `/home/arda/projects/tenioha`.

## Current task

Continue building a Japanese programming language inspired by Kip. The user
requested this persistent progress file so another agent can resume. Update it
when a milestone, decision, verification result, or remaining task changes.
Do not infer that a planned item is implemented.

The user asked to resume the interrupted M1 checkpoint, then to continue.
M1 and M2 are complete. Subsequent continuations added anonymous functions and
lexical closures (0.4.0), then nested constructor patterns and ordered match
arms (0.5.0). The user then requested a public repository under `c0ze` and
continued development. The repository is published; compact particle boundaries
were implemented as version 0.6.0 at `6383f17`.

The user resumed from that checkpoint and asked to continue. This continuation
implements **0.7.0 explicit aliases**, after reproducing the clean 262-test
baseline. Alternate function spellings and per-parameter particle choices are
complete. Final verification is recorded below; no 0.7 work remains outstanding.

The user requested independent Claude, Kimi, and Grok audits and fixes for
confirmed findings, then asked to resume after the prior agent reached quota.
The **0.7.1 audit is complete**, prepared on `audit/multi-model-0.7` from
`40c2e08`. Implementation commit `65867a8` passes 322 tests on Python 3.11.15 and
3.14.7, freshly verified on 2026-09-14. Final review round 1 caught double-BOM
handling and literal newline translation; both are corrected with entry/import
regressions. Claude, Kimi, and Grok each returned **PASS** in the resumed bounded
closeout review of that implementation. No blocking findings or unfinished 0.7.1
implementation work remain; no new feature work is in progress.
Original reports, follow-ups, and finding dispositions are in
[the audit record](docs/AUDIT-0.7.md). Review transport files remain in
`/tmp/tenioha-audit-YEdpGq`, `/tmp/tenioha-closeout-hc1fqpb8`, and local `.tincan/`
(excluded from git). Do not repeat the original full-project review.

Current task: add Fibonacci, FizzBuzz, primes, and related teaching examples,
plus a GitHub Pages introduction and working browser playground. Implementation
is on `feature/examples-playground`, based on `8d83495`. Five new standalone
examples bring the catalog to 18. The site runs the unchanged 0.7.1 interpreter
through pinned Pyodide 0.29.3 in a disposable worker. Native tests pass 334 cases
on Python 3.11.15 and 3.14.7; eight real Chromium tests cover the full catalog,
errors, I/O, cancellation, limits, responsive layout, and load-failure recovery.
Claude/Kimi/Grok review and Pages publication are the remaining steps. See
[PLAYGROUND.md](docs/PLAYGROUND.md) for building, serving, tests, and deployment.

## Milestones

| Milestone | Status | Scope |
|---|---|---|
| Research | Complete | Kip source investigation, Japanese adaptations, Nadesiko prior art |
| M0 | Complete | Python interpreter; typed particle calls, literals, checked I/O, CLI |
| M1 | Complete (0.2.0) | Functions/procedures, immutable lexical bindings, recursion, lazy conditionals, ordered I/O |
| M2 | Complete (0.3.0) | Algebraic data types, explicit generics, exhaustive constructor matching, function values, modules, list/option library |
| Closures | Complete (0.4.0) | Anonymous functions/procedures with immutable lexical captures |
| Nested patterns | Complete (0.5.0) | Recursive constructor patterns, ordered arms, exhaustiveness and unreachable-case checking |
| Compact boundaries | Complete (0.6.0) | Adjacent particles after integers and closing delimiters, preserving whole identifier words |
| Explicit aliases | Complete (0.7.0) | `別名 新名 は 対象`; per-parameter particle choices such as `に|へ`, retained in function types |
| Multi-model audit | Complete (0.7.1) | Composed-type stack safety, consistent source input, clearer diagnostics, Claude/Kimi/Grok closeout passes and recorded dispositions |
| Examples and playground | Implemented; review and publication in progress | Five algorithms, 18-example browser catalog, project introduction, worker runtime, and Pages workflow |
| Later | Not started | Broader Japanese syntax, richer patterns/inference, tooling/backends, embedding |

## Current implementation

- Python standard library only; run from the repository with `python -m tenioha`.
- `syntax.py` tokenizes and parses, retaining original spans while normalizing
  names to NFC. M2 adds type syntax, constructor patterns, explicit function
  references/application, and qualified import names. Anonymous `関数`/`手続き`
  expressions use the same signature syntax with the name omitted. Patterns
  recursively contain constructors, binding names, or wildcards.
- ASCII integers may attach one complete particle word, including signed and
  leading-zero forms. Closing delimiters can touch following particles in
  values, patterns, parameters, and types. The reader preserves original spans
  and never splits identifier words or guesses particle prefixes in longer
  numeric words. Both spaced and compact forms use the same checker/evaluator.
- `typesys.py` defines primitive/nominal/function types, rigid generic variables,
  signature substitution, and type resolution. Generic arguments are explicit;
  body checking is parametric and runtime bodies are shared. Equality, hashing,
  formatting, and substitution use explicit stacks because generic composition
  can create types deeper than any written annotation.
- `core.py` loads the import graph, hoists types/signatures, checks bodies and
  statements, and evaluates with an explicit stack. It retains the existing
  host builtin API (`Builtin`, `Parameter`, `ValueType`, `Effect`).
- Entry files and imports share `read_source`, which decodes UTF-8 without
  newline translation or BOM removal. The tokenizer skips exactly one initial
  BOM while preserving offsets. Comments and diagnostic locations share six
  line-break forms: LF, CRLF, CR, NEL, line separator, and paragraph separator.
  Characters inside strings retain their exact contents.
- `patterns.py` checks constructor coverage using interned shapes, memoized
  matrix specialization, and an explicit work stack. It preserves correlations
  between fields and produces an uncovered pattern for missing-case errors.
- Every body, including unused imported functions, is checked before entry-file
  program I/O. Imports read source files during compilation; imported modules
  contain declarations only. Entry-file statements execute in source order.
- Parameters may declare particle choices, for example `(元:整数)に|へ`.
  Choices must be disjoint across a signature. Calls and patterns supply one
  accepted label per slot; supplying two alternatives for the same slot is a
  duplicate argument. There is no global particle equivalence.
- All arguments are pure and evaluate in canonical parameter order. Indirect
  callees must also be pure and evaluate before arguments. Alternate labels
  resolve to the same slot before evaluation.
- Function types preserve canonical parameter order, complete particle choice
  sets, value types, result type, and effect. Choice order within a slot is
  normalized; slot order remains significant. Creating an IO reference is pure;
  calling it is still IO. `FunctionType.aliases` and `Parameter.aliases` retain
  alternatives through generic substitution and indirect calls.
- `別名 新名 は 対象` declares a file-scoped alternate function, procedure,
  or constructor name. `Compiler.aliases` resolves chains iteratively after
  hoisting real signatures. `Signature.key` retains the original runtime body
  or builtin identity, including across modules. Aliases add no executable
  statements, runtime wrappers, or duplicate bodies. Unknown targets, cycles,
  and collisions are checked even when unused.
- Alias targets may be qualified imports. An alias is exported under its new
  name, allowing explicit function/constructor re-exports. It preserves all
  generic parameters, types, and effects. Constructor aliases retain nominal
  identity and the same match coverage case. No type aliases are implemented.
- Closures retain only the free values used by their bodies, including values
  needed by nested closures. Capture snapshots are immutable and survive factory
  returns. Each invocation receives fresh locals. `capture_names` walks checked
  code with sequential binding and pattern scope rules; runtime `FunctionValue`
  stores the checked closure body and captured values.
- Closure creation is pure and delays execution; bodies are checked eagerly
  under their own declared type/effect. Generic factories may return closures
  using enclosing type parameters. `適用` invokes named values and closures alike.
- Match subjects are pure algebraic values evaluated once. Arms run in source
  order; the first matching body executes. All arms are checked and equally
  typed. Every constructor combination must be covered; wholly covered later
  arms are rejected as unreachable. Repeated outer constructors and partial
  overlaps are allowed. Fields match by declared particle choices at every level.
- `_` and bare binding names match any value, including the whole subject.
  Constructor spellings need parentheses to act as constructor patterns.
  Non-wildcard bindings are unique across a pattern after NFC normalization.
  Arm bindings are lexical and can be captured by closures; failed patterns
  discard any bindings collected while matching. Runtime matching is iterative.
- Imports use relative paths and aliases. Canonical file paths identify modules
  and nominal types; repeated aliases share definitions. Cycles are rejected.
- `lib/list.ten` supplies generic length/map/left-fold. `lib/option.ten` supplies
  optional values, defaults, and map. These are ordinary Tenioha source modules.

## Verification

Latest verification: **334 tests passed on Python 3.11.15 and 3.14.7** on
2026-09-14. This includes the 322-test audited baseline and 12 algorithm/adapter/
site-build tests. **Eight Chromium browser tests pass**, including every bundled
example through the real Pyodide runtime. `git diff --check` passed.

M1's resumed baseline was **91 passing tests** on Python 3.14.7. M2 adds tests
in `test_types.py`, `test_function_values.py`, `test_modules.py`, and the CLI
suite. Run the full suite with:

```sh
python -m unittest discover -s tests -v
```

Coverage includes all 24 permutations of four constructor/indirect-call
parameters, generic substitution and rigid body checking, nominal identity,
exhaustiveness, lexical pattern scope, lazy branches, function effects,
canonical exception order, cyclic/duplicate/invalid imports, and checking
unused imported bodies before I/O. Deep list construction/traversal/formatting
and polymorphic/indirect recursion exercise the explicit evaluator stack.
The closure suite adds capture lifetime, snapshot/shadowing behavior, nested
captures, conditional and pattern scope, generic factories, captured functions
and data, delayed execution, and 1,000 chained closure calls. The nested-pattern
suite adds ordered overlap, correlated exhaustiveness, unreachable unions,
exact particles at every level, scope/capture behavior, import aliases,
single subject evaluation, and checking before I/O. An independent finite-value
oracle verifies all 729 three-arm sequences for a pair of two-colour values.
Deep/wide patterns, recursive data, and the coverage budget exercise resource
limits. CLI tests verify examples and source diagnostics before output.
The compact-reader suite adds all eight labels, signed/large integers, NFC
particle spans, identifier boundaries, delimiter adjacency across the grammar,
and unchanged types/effects, evaluation order, modules, and captures.
The alias suite adds every particle as a choice, argument permutations, duplicate
slots, exact choice-set type equality, generic substitutions, closures, and host
builtins. It covers alternate names, forward targets and 1,500-link chains,
constructor patterns/coverage, explicit module re-exports, canonical exception
order, IO effects, and early diagnostics. CLI checks cover alias output, original
source spans, `--check` counts without duplicate bodies, and no execution during
checking. Alias-cycle diagnostics point to the target that closes the cycle.
The audit regressions cover 600-level type operations, generic composition
inside nested blocks, type errors before I/O, one initial BOM across input
paths, double-BOM rejection, literal newline preservation, six source line
boundaries, original diagnostic offsets, and invalid entry filenames.

All eighteen example files ran with their expected `.out` fixtures and passed
`--check`, including both greeting input fixtures. Selected examples:

| Example | Output |
|---|---|
| `lists.ten` | `3`, `12` on separate lines after generic map and fold |
| `options.ten` | `42`, `7` on separate lines after map/default selection |
| `closures.ten` | `6`, `15`, `36` after independent increment factories and list map/fold |
| `closure_greeting.ten` | `こんにちは、Ada` twice after one input read |
| `nested_patterns.ten` | `未設定`, `空`, `一つ`, `複数`, `7` after optional-list matching and a closure capturing the first element |
| `compact.ten` | `てにをは、少し短く。`, `2`, `2`, `36`, `11` using compact particles, closures, list operations, and nested patterns |
| `aliases.ten` | `8`, `8`, `7`, `11` using alternate names, particle choices, indirect calls, constructor matching, and a closure |
| `fibonacci.ten` | First 12 Fibonacci numbers, `0` through `89`, using linear accumulator recursion |
| `fizzbuzz.ten` | FizzBuzz for 1 through 30 |
| `primes.ten` | Primes between 2 and 50 using trial division |
| `gcd.ten` | `21` and `6` using Euclid's algorithm |
| `collatz.ten` | The Collatz sequence starting at 7 and ending at 1 |

Twenty-three README/language-guide snippets were verified, including the deliberate
nested-I/O error example, plus the corrected inline generic alias example.
Python 3.11+ is the intended baseline; verification covers Python 3.11.15 and
3.14.7 on Linux. Reviewers' reports used Python 3.14.3; their recorded
versions and probe counts are separate from the orchestrator's fresh checks.

## Known limits

- No nested named declarations, recursive local bindings, or tail-call optimization.
  Named file-scoped functions receive parameters/locals and do not capture
  top-level or caller values. Anonymous closures capture their defining lexical
  values. Value and function namespaces remain separate.
- At most 1024 user calls may be active. Source/type nesting and import chains
  have limits of 128 (the import count includes the entry file).
- Generic calls/references/types require all type arguments. No generic
  inference, partial specialization, constraints, or higher-rank polymorphism.
  Closures cannot declare fresh generic parameters or infer parameter/result
  annotations; they may use type parameters from an enclosing generic function.
- No literal patterns, guards, alternatives within a single pattern, or
  primitive match subjects. Use conditionals to inspect bound primitive values.
  Coverage follows declared constructor structure and does not prove that
  recursive types have no finite values. Each match has a 50,000-state analysis
  budget; exceeding it produces `E_MATCH_COMPLEXITY` before program I/O.
- Function types match exactly, including particle choice sets, parameter order,
  and effects. No
  overloading, implicit conversions, variance, or effect subtyping.
- Aliases target whole named declarations, not generic specializations, type
  names, or lexical function values. They cannot be declared inside a block.
  `別名` is a new keyword in 0.7: rename older identifiers with that spelling.
- Imported files have no top-level values/initializers, private declarations,
  implicit re-exports, or package search path. `--eval` cannot import; embedding
  can supply a concrete source filename for relative import resolution.
- No unrestricted unspaced Japanese or automatic conjugation. Alternate
  spellings, including polite ones, require explicit alias declarations.
  `5から` and `「猫」を` work, but `値を` remains one name. Keep boundaries
  between words; `5から3を引く` is rejected rather than segmented.
- Algebraic/function displays omit type arguments and module aliases; they are
  human-readable values, not a source serialization format. Anonymous closures
  display `関数 {…}` or `手続き {…}` without exposing captured values.

## Useful context

- [Current language guide](docs/LANGUAGE.md)
- [Design and roadmap](docs/DESIGN.md)
- [Recorded decisions](docs/DECISIONS.md), including M2 grammar, closures, nested patterns, compact boundaries, and explicit aliases
- [Research and pinned sources](docs/RESEARCH.md)
- Kip checkout: `/home/arda/projects/kip`, inspected revision
  `eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2`. It was not changed or executed.
- Public repository: [c0ze/tenioha](https://github.com/c0ze/tenioha), default
  branch `master`. The 0.7.0 release is `40c2e08`; implementation corrections
  through `65867a8` implement 0.7.1. Use `git log -1` and `git status -sb` to inspect
  the actual checkout and remote tracking state.
  The user authorized publication and continued development.
- No repository `AGENTS.md` was found. No third-party packages are required.

## Resume commands

```sh
cd /home/arda/projects/tenioha
git status --short
python -m unittest discover -s tests -v
python -m tenioha examples/factorial.ten
python -m tenioha examples/greeting.ten < examples/greeting.in
python -m tenioha examples/lists.ten
python -m tenioha examples/options.ten
python -m tenioha examples/closures.ten
python -m tenioha examples/closure_greeting.ten < examples/closure_greeting.in
python -m tenioha examples/nested_patterns.ten
python -m tenioha examples/compact.ten
python -m tenioha examples/aliases.ten
python -m tenioha examples/fibonacci.ten
python -m tenioha examples/fizzbuzz.ten
python -m tenioha examples/primes.ten
python scripts/serve_site.py
python -m tenioha --check examples/lists.ten
```

## Next work (not started)

The browser playground is a fresh-program editor, not a persistent REPL. Do not
repeat completed alias or playground work. A possible later milestone is an
interactive REPL to make the language easier
to explore. Before implementing it, specify multiline input, persistent bindings
and declarations, error recovery, relative imports, and when checking permits
IO. Acceptance should include defining a function across multiple lines, reusing
it in later inputs, recovering from an error, and quitting on EOF. This is a
recommendation, not an approved syntax design or started implementation.

Other roadmap candidates include `の` projections, `て` sequencing, and richer
patterns (literals or guards). Tooling/backends and game embedding remain separate
work. Select one bounded milestone and record semantics and acceptance examples
before implementation.

Preserve whole-program checking before I/O, canonical argument evaluation order,
NFC names with original spans, nominal module/type identity, immutable lexical
captures, ordered/exhaustive matching, and all existing regressions. No external blocker.

# Tenioha — milestone progress and agent handoff

Updated: 2026-09-13. Repository: `/home/arda/projects/tenioha`.

## Current task

Continue building a Japanese programming language inspired by Kip. The user
requested this persistent progress file so another agent can resume. Update it
when a milestone, decision, verification result, or remaining task changes.
Do not infer that a planned item is implemented.

The user asked to resume the interrupted M1 checkpoint, then to continue.
M1 and M2 are complete. Subsequent continuations added anonymous functions and
lexical closures (0.4.0), then nested constructor patterns and ordered match
arms as version **0.5.0**. Final verification is recorded below.

## Milestones

| Milestone | Status | Scope |
|---|---|---|
| Research | Complete | Kip source investigation, Japanese adaptations, Nadesiko prior art |
| M0 | Complete | Python interpreter; typed particle calls, literals, checked I/O, CLI |
| M1 | Complete (0.2.0) | Functions/procedures, immutable lexical bindings, recursion, lazy conditionals, ordered I/O |
| M2 | Complete (0.3.0) | Algebraic data types, explicit generics, exhaustive constructor matching, function values, modules, list/option library |
| Closures | Complete (0.4.0) | Anonymous functions/procedures with immutable lexical captures |
| Nested patterns | Complete (0.5.0) | Recursive constructor patterns, ordered arms, exhaustiveness and unreachable-case checking |
| Later | Not started | Compact Japanese syntax, richer patterns/inference, tooling/backends, embedding |

## Current implementation

- Python standard library only; run from the repository with `python -m tenioha`.
- `syntax.py` tokenizes and parses, retaining original spans while normalizing
  names to NFC. M2 adds type syntax, constructor patterns, explicit function
  references/application, and qualified import names. Anonymous `関数`/`手続き`
  expressions use the same signature syntax with the name omitted. Patterns
  recursively contain constructors, binding names, or wildcards.
- `typesys.py` defines primitive/nominal/function types, rigid generic variables,
  signature substitution, and type resolution. Generic arguments are explicit;
  body checking is parametric and runtime bodies are shared.
- `core.py` loads the import graph, hoists types/signatures, checks bodies and
  statements, and evaluates with an explicit stack. It retains the existing
  host builtin API (`Builtin`, `Parameter`, `ValueType`, `Effect`).
- `patterns.py` checks constructor coverage using interned shapes, memoized
  matrix specialization, and an explicit work stack. It preserves correlations
  between fields and produces an uncovered pattern for missing-case errors.
- Every body, including unused imported functions, is checked before entry-file
  program I/O. Imports read source files during compilation; imported modules
  contain declarations only. Entry-file statements execute in source order.
- Calls and constructors require unique exact particle labels. All arguments
  are pure and evaluate in canonical parameter order. Indirect callees must
  also be pure and evaluate before arguments.
- Function types preserve canonical particle order, value types, result type,
  and effect. Creating an IO reference is pure; calling it is still IO.
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
  overlaps are allowed. Fields match by exact particle at every nesting level.
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

Latest verification: **234 tests passed** on Python 3.14.7 on 2026-09-13,
including the 193-test closure baseline, 38 nested-pattern tests, and 3 new CLI
tests. `git diff --check` also passed.

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

All eleven example files ran with their expected `.out` fixtures and passed
`--check`, including both greeting input fixtures. Selected examples:

| Example | Output |
|---|---|
| `lists.ten` | `3`, `12` on separate lines after generic map and fold |
| `options.ten` | `42`, `7` on separate lines after map/default selection |
| `closures.ten` | `6`, `15`, `36` after independent increment factories and list map/fold |
| `closure_greeting.ten` | `こんにちは、Ada` twice after one input read |
| `nested_patterns.ten` | `未設定`, `空`, `一つ`, `複数`, `7` after optional-list matching and a closure capturing the first element |

Eighteen README/language-guide snippets were verified, including the deliberate
nested-I/O error example. All 32 local documentation links resolve. Python 3.11+ is the
intended baseline; runtime verification used Python 3.14.7 only.

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
- Function types match exactly, including parameter order and effects. No
  overloading, implicit conversions, variance, or effect subtyping.
- Imported files have no top-level values/initializers, private declarations,
  implicit re-exports, or package search path. `--eval` cannot import; embedding
  can supply a concrete source filename for relative import resolution.
- No compact Japanese syntax, automatic conjugation, or inflected aliases yet.
- Algebraic/function displays omit type arguments and module aliases; they are
  human-readable values, not a source serialization format. Anonymous closures
  display `関数 {…}` or `手続き {…}` without exposing captured values.

## Useful context

- [Current language guide](docs/LANGUAGE.md)
- [Design and roadmap](docs/DESIGN.md)
- [Recorded decisions](docs/DECISIONS.md), including M2 grammar, closures, and nested patterns
- [Research and pinned sources](docs/RESEARCH.md)
- Kip checkout: `/home/arda/projects/kip`, inspected revision
  `eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2`. It was not changed or executed.
- The user authorized creating a public `c0ze/tenioha` GitHub repository and
  pushing the implementation, then continuing development. Publication of the
  verified 0.5.0 checkpoint is the current step.
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
python -m tenioha --check examples/lists.ten
```

## Next work (not started)

The M0–M2 roadmap, closures, and nested-pattern extension are complete. Before
extending the surface language, select one later feature and record its exact
semantics and acceptance examples.
Candidates from the roadmap include declared particle/inflection aliases,
constrained compact Japanese, `の` projections, and `て` sequencing. Richer
patterns (literals or guards), tooling/backends, and game embedding are separate work.

Preserve whole-program checking before I/O, canonical argument evaluation order,
NFC names with original spans, nominal module/type identity, immutable lexical
captures, ordered/exhaustive matching, and all existing regressions. No external blocker.

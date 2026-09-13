# Language decisions

## 2026-09-13: M1 declarations and scope

Selected an explicit structured declaration for the reference language:

```text
関数 差 (元: 整数) から (量: 整数) を -> 整数 {
    (元 から 量 を 引く)
}
```

`関数` declares a pure function; `手続き` declares an IO procedure. These
keywords express effects explicitly rather than tying them to register.
Calls remain predicate-last. The final statement supplies a block's result;
an empty block or a final binding returns unit.

### Structured versus explanatory Japanese

The initial sketch proposed `〜とは…である`. We compared the same operations
using a structured signature and an explanatory Japanese wrapper. The latter
forms below are design sketches, not accepted syntax:

| Program | Selected structured header | Explanatory sketch |
|---|---|---|
| Greeting | `手続き 挨拶 -> 単位 { … }` | `挨拶 とは 単位 を 返す 手続き である { … }` |
| Factorial | `関数 階乗 (数: 整数) を -> 整数 { … }` | `階乗 とは (数: 整数) を 受け取り 整数 を 返す 関数 である { … }` |
| List length (M1 sketch) | `関数 長さ (値: 一覧<整数>) を -> 整数 { … }` | `長さ とは (値: 一覧<整数>) を 受け取り 整数 を 返す 関数 である { … }` |

Each pair has the same intended body: greeting binds an input then prints it;
factorial branches at zero and recurses; list length would match empty/nonempty
constructors and recurse. At this M1 decision, neither list header was executable.
M2 subsequently selected generic type notation and matching; see the decision below.

For this iteration, the explanatory forms repeat signature information through
additional words without resolving parameter, result, or scope ambiguity.
The structured form provides clear parser boundaries and diagnostic locations.
Keep an optional explanatory reader as a future experiment; do not implement
multiple equivalent definition grammars before the core is established.

### Binding and branching

`名前 は 式` introduces an immutable value in the current scope. It does not
make `は` an alias for `が` in calls, infer a topic, or mutate an existing value.
Nested blocks may shadow an outer value; their initializer sees the previous
outer binding. Repeating a name in the same scope is an error, including
rebinding a parameter in its function's outermost body.

```text
もし (数 と 0 が 等しい) なら {
    1
} そうでなければ {
    (数 に ((数 から 1 を 引く) を 階乗) を 掛ける)
}
```

Require a pure boolean condition, both branches, and equal branch types.
Check both branches statically; execute only the selected one. Branches are
ordinary lexical blocks and inherit the surrounding effect context.

### Function visibility and effects

- Hoist file-scoped function signatures, enabling forward calls and mutual
  recursion. Check all declared bodies before executing any top-level statement.
- Value bindings are sequential, not hoisted. Functions receive parameters and
  create locals; they do not capture top-level values or caller environments.
  Pass external values as explicit arguments. Anonymous closures were deferred
  to the 0.4 decision below; these named-function rules still apply.
- Value and function namespaces are separate, as in a Lisp with separate
  function lookup. A value named `引く` does not change the target of `(… 引く)`.
- Declarations are file-scoped only. No nested definitions or overloading yet.
- A procedure may return a value. Bind its result before using it as an argument.
  Any procedure call is IO even if the procedure's body happens to be pure.
- `--pure` restricts top-level execution. Uncalled procedure definitions are
  allowed and checked under their declared IO context; pure functions can never
  call them, even indirectly through another declared procedure.
- Use an explicit evaluator stack with a limit of 1024 active user calls.
  No tail-call optimization yet. Source nesting remains limited to 128 levels.

## 2026-09-13: M2 types, matching, function values, and modules

M2 selects these additions to the structured core:

- Algebraic declarations use `型 一覧<T> { 空。節 (頭: T) を (尾: 一覧<T>) に }`.
  Constructors are pure functions with particle-labelled fields; nominal type
  identities prevent unrelated declarations with the same shape from mixing.
  Hoist type names before resolving fields to allow recursive data.
- Type arguments are explicit at every generic call, reference, and type use.
  Check generic bodies against rigid type variables, including uncalled bodies.
  This keeps error locations predictable without introducing inference,
  constraints, or higher-rank polymorphism in the first generic implementation.
  The earlier `一覧<整数>` sketch is now selected syntax.
- Matching uses `場合 値 { (空) なら { … } (頭 を 尾 に 節) なら { … } }`.
  Require one flat arm per constructor, exact field particles, unique bindings
  except `_`, and equal branch result types. The subject is pure; arm effects
  inherit their context. Nested matches express recursive destructuring without
  needing a nested-pattern coverage algorithm yet.
- Keep the separate value/function namespaces. `参照 名前<型>` explicitly
  obtains a function value; `(引数 を 適用 値)` invokes it. Functions can be
  passed, stored, and returned, including in generic data, without adding
  closures or ambiguous bare-name lookup. References can target constructors.
- Function types use `関数[整数 から, 整数 を -> 整数]` and
  `手続き[文字列 を -> 単位]`. Equality includes canonical parameter order,
  particle labels, value types, result type, and effect; local parameter names
  are irrelevant. Keeping order prevents coercion from changing exception
  order. Do not add effect subtyping or parameter variance yet.
- Evaluate an indirect callee first, then pure arguments in canonical type
  order. Creating an IO function reference is pure; invoking it remains IO.
  Type arguments have no runtime operations; generic bodies are shared rather
  than recursively expanded for each instantiation.
- Modules use `取込 「relative/path.ten」 と 別名` and `別名.名前` lookup.
  Resolve paths relative to the importing file; canonical paths identify modules
  and nominal types. Cache repeated imports, reject cycles, and keep source
  spans from each file. Imported files contain declarations only; all their
  bodies are checked before any entry-file execution. All own declarations are
  exported; imports are not automatically re-exported. (`別名` here is the M2
  placeholder for a module name; 0.7 reserves that word as a keyword.) There is no package
  search path or module initialization order to infer.
- The minimal library provides generic list length/map/left-fold and optional
  values/defaults/map in `lib/list.ten` and `lib/option.ten`. Keep these ordinary
  Tenioha source programs so they exercise the language and its call-depth limit.

The executable grammar and examples are in [LANGUAGE.md](LANGUAGE.md).
At the M2 boundary, anonymous functions and closures were deferred; the 0.4
decision below implements them. The 0.5 decision further extends constructor
patterns, and 0.6 adds constrained compact particle boundaries. Literal patterns,
generic inference, module constants, and unrestricted unspaced Japanese remain
future work.

## 2026-09-13: 0.4 anonymous functions and lexical closures

The next extension makes existing function values usable as capturing callbacks.
Use the existing `関数`/`手続き` signature and body syntax without a name:
`関数 (値: 整数) を -> 整数 { (値 に 増分 を 足す) }`. This is an expression;
a keyword followed by a name remains a file-scoped declaration. No new keyword,
implicit binding, or second calling convention is needed: invoke with `適用`.

Capture only the free values referenced by the checked body. A nested closure's
capture requirements count as uses in its enclosing closure. Sequential locals,
parameter shadowing, and match-arm bindings determine whether each name is free.
Capture values when the expression executes, in an immutable snapshot. Keep the
checked body with the value so it remains callable after its factory returns;
start each invocation with a fresh environment containing captures and parameters.

The body is delayed at runtime but checked eagerly under its own declared effect
and result type. Constructing an IO closure is pure; applying it is IO. This lets
pure factories build effectful callbacks while preserving the existing prohibition
on IO in pure argument/callee contexts. A captured value that came from earlier
IO is an ordinary immutable value; capturing it does not repeat that operation.

Closures inherit their enclosing generic type parameters and require explicit
parameter/result annotations. Defer fresh anonymous generic parameters, local
recursive bindings, and nested named declarations. Preserve the named-function
namespace and module lookup rules, and use the existing explicit evaluation stack
and 1024-active-call limit for both named and anonymous invocations.

Acceptance examples are independent increment factories used with generic list
map and a procedure factory that reads a name once, then returns a greeting that
can be invoked repeatedly. Both are executable in `examples/`.

## 2026-09-13: 0.5 nested constructor patterns and coverage

Allow a constructor field pattern to contain another constructor pattern, with
exact particle roles at every level. This preserves predicate-last syntax and
supports forms such as `((値 を 有り) を 有り)`. Pattern type arguments are
inferred from the already checked subject/field type; no generic call inference
or primitive/literal pattern syntax is added.

Select source-order, first-match semantics. Repeated outer constructors and
partially overlapping patterns are useful for nested cases. Bare names and `_`
can also serve as whole-subject fallbacks. Bindings remain unique across an entire
pattern after NFC normalization, except repeated `_`. A failed arm must not leak
partial bindings, and closures may retain bindings from the selected arm.

Check whether each arm adds any values beyond earlier arms, then apply the same
coverage question to a wildcard to find missing cases. This is the usefulness
approach described in the [Rust Compiler Development Guide](https://rustc-dev-guide.rust-lang.org/pat-exhaustive-checking.html).
Our constructor-only implementation specializes pattern rows by constructor and
keeps field combinations together. Unreachable arms are errors, and missing-case
diagnostics display an uncovered pattern shape. No Rust code was copied.

After type checking, coverage needs constructor identity/arity and pattern shape,
not binding names or concrete generic arguments. Intern shapes as integer IDs
and use memoized, explicit work stacks, avoiding recursive expansion of nominal
type definitions. Cap each match at 50,000 analyzed coverage states and report
`E_MATCH_COMPLEXITY` if exceeded; splitting a large match is the supported remedy.
Runtime matching also uses a work stack and never evaluates code while testing
patterns. The subject evaluates once; only the first matching body's code runs.

Do not attempt a separate proof that recursive declarations have no finite
values. Coverage remains conservative over declared constructor structure.
Literal patterns, guards, alternatives within patterns, and primitive subjects
are future work. The acceptance program classifies absent/empty/single/multiple
lists inside an option and returns a closure holding a nested list element.

## 2026-09-13: 0.6 compact particle boundaries

Accept compact forms only where the reader can identify a boundary without a
dictionary, name lookup, or guessing a particle prefix. This is the constrained
reader proposed in the original design:

- An ASCII integer, including a minus sign or leading zeros, may be immediately
  followed by exactly one complete particle word: `5から`, `-3を`, or `7が`
  (the last particle normalizes to `が`). Preserve separate original spans for
  the number and particle. The existing 4096-digit limit still applies.
- A closing string quote, parenthesis, brace, generic delimiter, or function-type
  bracket already separates words. Allow its following particle to touch it in
  calls, constructor patterns, parameter declarations, and function types.
  Examples include `「猫」を`, `(式)に`, `(値:整数)を`, and `一覧<整数>を`.
- Continue reading every identifier word in full before classifying it. `値を`,
  `たから`, and `真を` are single names. Bare names, boolean literals, and bare
  type names therefore still need separation from their particles. A particle
  and a following name or number also need separation: `5から引く`, `5から3を`,
  and `「猫」を表示する` are not split into calls. Delimiters can supply that
  separation, as in `「前」と「後」を 連結する`.

Apply this as a reader extension, with no alternate mode or source rewriting.
Spaced programs retain their behavior. Particle roles, canonical argument order,
static types/effects, module identity, pattern coverage, and lexical captures
are unchanged. Strings and comments retain their exact contents. Continue to
reject unsupported numeric forms, fullwidth syntax, and reserved words used as
particles. Automatic conjugation, particle aliases, and unrestricted unspaced
Japanese remain separate proposals.

The acceptance program compares compact argument permutations, matches nested
constructors, and uses a capturing closure with a generic library operation.

## 2026-09-13: 0.7 explicit names and particle choices

Add two explicit, orthogonal declarations without a morphology dependency:

```text
関数 加える (元:整数)に|へ (量:整数)を -> 整数 { (元 に 量 を 足す) }
別名 加えます は 加える。
(5へ 3を 加えます)
```

Particle choices belong to a single parameter. Resolve each accepted label to
that slot before checking completeness, duplication, types, or evaluation order.
Supplying both `に` and `へ` above is a duplicate argument, not a second role.
All labels in a signature must be distinct, including alternatives within a
group and across groups. Do not use value types to disambiguate repeated labels.
The eight existing particles remain the only choices; there is no global
equivalence of Japanese particles and no change to the builtin signatures.

Use the same choice syntax for functions, procedures, closures, constructors,
and structural function types: `関数[整数 に|へ, 整数 を -> 整数]`. Each slot
retains its complete accepted set through references, generic substitution,
imports, and indirect application. Choice order within a slot is immaterial;
parameter slot order remains significant for types and argument evaluation.
Require exact sets rather than introducing subtyping or coercions. Calls and
constructor patterns supply exactly one label per slot, without `|` syntax.

An alternate name targets a whole named declaration, including a builtin or
qualified imported function. Preserve the canonical implementation/body key,
generic parameter identities, result type, and effect; do not add a wrapper.
Specialize generics at calls and references, never at an alias declaration.
Constructor aliases preserve nominal identity and represent the same coverage
case. The matcher can use either spelling and any declared particle choice.

Aliases share the function namespace and are file-scoped declarations. Hoist
them after real signatures, resolve forward chains iteratively, and reject
unknown targets, cycles, and duplicate names before all program execution.
Check unused imported aliases too. Export aliases under their own names;
an alias of an imported function is an explicit re-export. Imports remain
non-transitive, and type aliases and aliases of lexical values are not added.

Reserve `別名` as a keyword. This requires renaming identifiers with that exact
spelling in older source. Polite spellings have to be declared explicitly and
retain the target's effect; there is no automatic conjugation or suffix stripping.

Acceptance cases cover alternate spellings in direct and indirect calls, both
particle choices under permutations, duplicate aliases, generic factories and
closures, same-constructor matching, explicit module re-exports, unchanged IO
checks, and canonical argument failure order. `examples/aliases.ten` prints
`8`, `8`, `7`, and `11` using these features together.

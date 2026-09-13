# Kip investigation and implications for Tenioha

Investigated on **2026-09-13**. Observed source behavior is separate from the
proposed [Tenioha design](DESIGN.md).

This investigation predates the M0 interpreter. See [LANGUAGE.md](LANGUAGE.md)
for Tenioha's current runnable features; the Kip execution boundary below
still applies to the upstream investigation.

## Scope and reproducibility

Tenioha initially contained only a README and a design sketch. Kip was cloned
from `https://github.com/kip-dili/kip.git` into `/home/arda/projects/kip`, beside
`/home/arda/projects/tenioha`.

Inspected revision: **`eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2`**.
The checkout was left unmodified. Implementation links below pin that revision.

Read the official website/tutorial, AST, relevant parser and checker paths,
argument evaluation, standard-library declarations, morphology interface, test
instructions, and selected success/failure fixtures. Also reviewed Nadesiko's
official documentation and TUFS Japanese grammar materials.

**Execution boundary:** Kip was not built or executed. This machine has no
`kip`, GHC, Cabal, Stack, or Wasmtime installed. The GitHub latest-release API
returned 404, so no release binary was obtained. Node is installed, but Kip's
JS backend still needs the compiler to generate JS. Native and WASM builds
require additional toolchains. Fixture outputs below are checked-in upstream
expectations, not results from a local test run.

## What Kip implements

Kip combines predicate-final syntax with morphology-aware name resolution,
typed grammatical roles, algebraic data, polymorphism, pattern matching, and
grammatical distinctions between pure and effectful definitions. The source
uses Haskell, Megaparsec, and a C interface to Foma/TRmorph.

| Layer | Evidence in the pinned checkout | Implication for Tenioha |
|---|---|---|
| Syntax tree | [AST.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/AST.hs) | Ordinary value types coexist with case/span annotations; expressions include calls, binding, sequencing, matching. |
| Parser | [Parser.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/Parser.hs) | Morphology, scope, known arities, and syntax interact. Japanese needs a new frontend. |
| Morphology | [Language/Foma.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Language/Foma.hs), [C interface](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/c/morphology.c) | Analyses and generated forms cross an FFI boundary; caches and fallback rules support resolution. |
| Checking | [TypeCheck.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/TypeCheck.hs) | Checks names, roles, value types, and effects; rewrites calls into signature order. |
| Runtime | [Eval.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/Eval.hs) | Evaluates checked calls and sequences; includes resolved-call dispatch and tail-call machinery. |
| Modules | [Runner.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/Runner.hs) | Coordinates parsing, checking, imports, evaluation, diagnostics, and caches. |
| JS backend | [Codegen/JS.hs](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/src/Kip/Codegen/JS.hs) | A useful later architecture, not necessary for a syntax experiment. |

### Roles supplement ordinary types

`Case` contains `Nom`, `Acc`, `Dat`, `Loc`, `Abl`, `Gen`, `Ins`, `Cond`, and
`P3s`. This implementation category includes conditional and possessive
information; it is not a ready-made inventory of Japanese particles. `Ty`
separately includes integers, floats, characters, strings, named types, type
variables, applications, and function arrows.

`Ann = (Case, Span)` annotates expressions and types. `Arg` holds a parameter
identifier and type. The original Tenioha question “particle on value or
parameter?” was a false either/or: declarations and supplied arguments both
need role information, without changing the underlying value permanently.

### Argument reordering has limits

The integer subtraction declaration distinguishes its inputs with `Ins` and
`Gen`. The upstream fixture
[tam-sayı-fark-sırası](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/tests/succeed/tam-sayı-fark-sırası.kip)
permutes those inputs; its `.out` expects `2` twice.

In contrast,
[aynı-hal-ardışık-fark](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/tests/succeed/aynı-hal-ardışık-fark.kip)
declares two integer parameters with the **same case**. Its two reversed calls
have expected outputs `2` and `-2`. Repeated cases retain occurrence order;
they are not freely interchangeable.

There is a source-reading trap: the header of `TypeCheck.hs` describes the
unique-case helper `reorderByCases`, which rejects duplicates. The main
exact-signature path in `tcExp1With` instead calls `reorderByCasesNomFallback`
from `AST.hs` (line 238). That helper consumes the first remaining exact-case
occurrence and, when needed, a nominative fallback. The call checker applies
additional compatibility rules, including flexible cases for some bound
variables and applications.

Consequently, “any incorrect case always fails” and “all arguments can always
be permuted” are both too strong as implementation descriptions. Tenioha can
start with stricter rules instead of inheriting Turkish disambiguation fallbacks.

### Pure arguments make reordering manageable

In `tcExp1With`, the call branch checks each argument with `tcExp1With False`
(`TypeCheck.hs`, line 511). This prohibits evaluating an effectful expression
as an ordinary argument, even in an effectful caller. The checker canonicalizes
argument order; `Eval.hs` evaluates that list in order with `mapM`.

Kip marks effectful definitions using the infinitive form, permits imperative
invocation, and supplies explicit binding/sequencing constructs. The fixture
[etki-yazmak](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/tests/succeed/etki-yazmak.kip)
binds an effectful result before printing it. The corresponding fail fixture
attempts to use that call as an argument. Another fail fixture,
`etki-bağlamı-yazmak`, rejects an effectful body in a pure definition.

Preserve this behavior: **explicitly sequence effects, then freely arrange
pure arguments with distinct roles**. Japanese register need not encode it.

### Library and tests

The library declares typed primitives in Kip and implements derived functions
in Kip itself. `lib/temel/tam-sayı.kip` demonstrates arithmetic signatures;
`lib/temel/liste.kip` has recursive and generic list operations;
`lib/temel/etki.kip` declares input, output, file, environment, and random effects.

The inspected corpus contains 104 success `.kip` programs and 49 failure `.kip`
programs. The [test instructions](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/tests/README.md)
describe output/error expectations, stdin fixtures, and interpreter/JS parity
testing. That behavioral fixture structure is useful to imitate early.

## Japanese adaptations

TUFS describes `は` among topic/focus particles and explains how it interacts
with case marking. Treating `は` and `が` as interchangeable discards
information. It also documents particles attaching to other particles, so
forms such as `には` need a deliberate grammar rather than naïve splitting.

Japanese source generally lacks spaces between words. Even when the desired
particle spelling is fixed, recognizing it inside arbitrary identifiers is
not automatic: `たから` can be an identifier containing `から`. Explicit
token boundaries can avoid a morphological analyser; unrestricted segmentation
and productive inflection are a different commitment.

Our design inference is to make role labels local to each signature. Reserve
topic, genitive chains, and connective syntax for separate rules. Require
unambiguous grouping and word boundaries before attempting compact text.

## Existing Japanese prior art: Nadesiko

Nadesiko's [function documentation](https://nadesi.com/v3/doc/index.php?文法/関数)
already demonstrates subtraction with particle-marked inputs in either order.
Its [word-order documentation](https://nadesi.com/v3/doc/index.php?文法/語順)
distinguishes Japanese-order calls from C-style calls and describes where
particle-based reordering does and does not apply.

Its [segmentation documentation](https://nadesi.com/v3/doc/index.php?文法/単語の区切り)
describes particles and Japanese punctuation as boundaries. Its
[politeness documentation](https://nadesi.com/v3/doc/index.php?文法/敬語)
supports polite requests and an observable courtesy counter.

Neither Japanese particle arguments nor polite surface forms are new by
themselves. Tenioha's proposed focus is a small functional core, strict
role/type contracts, and checked effects. Establishing research novelty
would require a broader literature review; this investigation does not claim it.

## Recommendation

Build a new frontend and small typed interpreter, informed by Kip's architecture
and tested against the Japanese cases in [DESIGN.md](DESIGN.md). Do not
transplant Turkish inflection, case fallbacks, or grammatical effect markers.
Start with exact labels, ordinary types, pure arguments, explicit effect
sequences, and a deterministic reader.

Politeness can remain an experiment, but honorific register does not itself
specify computational effects or enforce permissions. Demonstrate useful
Japanese programs before expanding this axis.

## Sources

- [Kip official site](https://kip-dili.github.io/) and
  [English tutorial](https://github.com/kip-dili/kip/wiki/Tutorial).
- [Pinned Kip repository](https://github.com/kip-dili/kip/tree/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2).
  Exact implementation links appear beside the findings above.
- [Kip license](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/LICENSE)
  credits Joomy Korkut; the separately attributed
  [TRmorph license](https://github.com/kip-dili/kip/blob/eed6b0ed5ea397f226ed0f7d52ff8d56410ae4d2/vendor/TRmorph-LICENSE)
  credits Çağrı Çöltekin. Both contain MIT terms. No upstream implementation
  code or morphology assets were copied into Tenioha.
- [TUFS Japanese grammar: topic/focus particles](https://www.coelang.tufs.ac.jp/mt/ja/gmod/courses/c02/lesson28/step1/explanation/095.html).
- Nadesiko's official manuals linked above were retrieved directly from the
  site when the search tool could not fetch those query URLs.

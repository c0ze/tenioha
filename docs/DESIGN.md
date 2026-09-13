# Tenioha — design sketch

Nothing here is decided. This is the thinking so far, written down so a
future session starts from something rather than nothing.

---

## 1. Particles as argument roles

The core mapping, against Kip's case list:

| Role | Kip (Turkish case) | Tenioha (particle) | Reads as |
|---|---|---|---|
| subject | nominative (bare) | が / は | the thing acting |
| object | accusative `-i` | を | the thing acted on |
| target | dative `-e` | に | to / onto |
| location | locative `-de` | で | at / in / using |
| source | ablative `-den` | から | from |
| possession | genitive `-in` | の | of |
| instrument | instrumental `-le` | と / で | with |

Because the particle carries the role, **argument order is free**:

```
3を 5に 足す。
5に 3を 足す。      ; same call
```

And a wrong particle is a compile error, not a bug:

```
3に 5に 足す。      ; error: 足す takes を and に, got two に
```

That is the whole value proposition. Positional arguments are a convention
we tolerate; particles are a convention a billion people already know.

## 2. Syntax sketch

Definition uses 〜とは…である, the ordinary Japanese way to define a term:

```
あいさつとは、
    名前を 読んで、
    「こんにちは、」と 名前を 連結して 書く ことである。

あいさつする。
```

Conditionals fall out of 〜なら:

```
否定とは、
    真なら 偽、
    偽なら 真 である。
```

Signatures might read as ordinary Japanese too:

```
足し算とは、数を 数に 足して 数である。
```

Open: whether definitions end in である (declarative) or こと (nominalised),
and whether the trailing 。is required. Both are aesthetic until there is a
parser to argue with.

## 3. The politeness axis — the genuinely novel part

Japanese marks *register* independently of meaning. The same operation is
書く / 書きます / お書きになる / 書かせていただく depending on who is
speaking to whom about whom.

No mainstream type system has an axis like this, and it is sitting there
unused. Candidates for what it could encode:

- **Effects.** Plain form = pure, polite form = performs I/O. This is the
  closest analogue to what Kip does with mood, and the most obvious.
- **Capability / privilege.** 尊敬語 for operations that require elevated
  rights, 謙譲語 for operations that yield them. Grammatically, honorifics
  already encode *who is permitted what* — which is what a capability system
  is.
- **Visibility.** Plain = module-private, polite = exported. "You speak
  politely to strangers" is a startlingly good mnemonic for a public API.

The capability reading is the most interesting and the least explored. It is
also the one that would make Tenioha a research contribution rather than a
port.

## 4. Implementation — first real decision

Not chosen. The trade-offs as they stand:

- **Python** — fastest to a working prototype, best for exploring syntax
  before committing. Weakest as a shipped artefact.
- **Rust** — best if this ever wants to be embedded, fast, or trusted.
  Slowest to iterate on grammar.
- **TypeScript** — best if the first audience is a web playground, which for
  an experimental language is a real argument: people try what they can try
  without installing.

Recommendation: **prototype in Python, port once the grammar stops moving.**
Language design is iteration on syntax, and the prototype is disposable.

Whatever the choice: no external morphological analyser. Japanese particles
are invariant tokens, so the tokeniser stays self-contained, and the language
keeps the property that there is nothing to sandbox.

## 5. Open questions

1. Does the particle bind to the **value** or to the **parameter**? Kip binds
   to the parameter. Binding to the value would allow genuinely free-floating
   arguments but makes inference much harder.
2. What happens with **は vs が**? Japanese distinguishes topic from subject;
   most type systems have no equivalent. Ignoring it is easiest. Using it —
   topic as an implicit/ambient parameter — is more interesting.
3. **Vocabulary.** Are keywords real Japanese words (足す, 読む, 書く) or
   invented? Real words make it readable and make error messages natural;
   they also make the parser's job harder and collide with user identifiers.
4. Does it write **vertically**? Almost certainly not. Worth asking once.
5. Is there an **English mode** — same semantics, particles as `-to`, `-from`,
   `-with` suffixes? That would make the idea legible to people who cannot
   read Japanese, at the cost of the thing that makes it beautiful.

## 6. Explicitly out of scope for now

Performance, a standard library, tooling, packaging. This is a question about
grammar. It earns those things only if the grammar turns out to be good.

# てにをは / Tenioha

A programming language where **Japanese particles are the type system**.

> *てにをは* (tenioha) is the traditional Japanese term for the grammatical
> particles — named after て・に・を・は themselves. Idiomatically it means
> whether a sentence's grammar holds together: *「てにをはが合わない」* is
> what you say when someone's particles are wrong.

Status: **concept only.** No implementation, no decisions locked. See
[docs/DESIGN.md](docs/DESIGN.md).

---

## The idea

In most languages an argument's meaning comes from its **position**:

```python
subtract(5, 3)   # which one is the minuend? you have to remember
```

In Japanese it comes from its **particle**, and position is free:

```
5から 3を 引く      "from 5, subtract 3"
3を 5から 引く      identical meaning
```

`から` marks the source and `を` marks the object, wherever they appear. That
is already a type system — it just isn't being used as one.

Tenioha makes the particle part of the signature. A function declares which
particles it takes, arguments can be written in any order, and a wrong
particle is a **type error**, not a runtime surprise.

---

## Prior art, and credit

This is Japanese applied to an idea that belongs to
**[kip](https://github.com/kip-dili/kip)** — a Turkish language (MIT, by a
Turkish PhD student) in which grammatical *case* is part of the type system.
Kip is the original insight. Tenioha asks whether it ports, and it does,
because Turkish case suffixes and Japanese particles do the same grammatical
job.

Two things Japanese brings that Turkish does not:

1. **No morphological analyser.** Kip needs TRmorph to resolve Turkish
   suffixes through vowel harmony (`-i/-ı/-u/-ü`). Japanese particles are
   separate, invariant tokens. A plain tokeniser is enough — which means the
   whole implementation can be self-contained, with no external language
   dependency.

2. **Politeness as a second axis.** Turkish has mood; Japanese has mood *and*
   register (plain / 丁寧 / 尊敬 / 謙譲). That is an entire orthogonal
   dimension of grammar with no equivalent in most type systems. Whether it
   should carry effects, capabilities, or visibility is the most interesting
   open question in the project.

---

## Why build it

Honest answer: because nobody has, the mapping is unusually clean, and the
person starting it lives in Japan and speaks the language.

Less honest answer: it might be the hard mode of a game about programming.
See `~/projects/games/commit/commit+++`.

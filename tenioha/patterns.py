"""Checked patterns and constructor-matrix coverage, without runtime evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .syntax import Diagnostic, Span
from .typesys import Constructor, DataDefinition


MAX_COVERAGE_STATES = 50_000


@dataclass(frozen=True)
class CheckedPattern:
    constructor: Constructor | None = None
    fields: tuple[CheckedPattern, ...] = ()
    binding: str | None = None


class Coverage:
    """Find a pattern not covered by earlier rows, preserving field correlations.

    Patterns are interned as integer IDs: zero is wildcard. Checking uses an
    explicit work stack and ignores binding names and generic type arguments;
    those have already been checked. Constructor identity determines its family.
    """

    def __init__(self, definitions: Mapping[str, DataDefinition], span: Span):
        self.span = span
        self.constructors = {c.key: c for definition in definitions.values() for c in definition.constructors}
        self.families = {definition.identity: tuple(c.key for c in definition.constructors) for definition in definitions.values()}
        self.nodes = [(None, ())]
        self.interned = {(None, ()): 0}
        self.memo = {}
        self.states = 0

    def node(self, constructor: str, fields: tuple[int, ...]) -> int:
        key = (constructor, fields)
        if key not in self.interned:
            self.interned[key] = len(self.nodes)
            self.nodes.append(key)
        return self.interned[key]

    def shape(self, pattern: CheckedPattern) -> int:
        results, pending = [], [(False, pattern)]
        while pending:
            finish, current = pending.pop()
            if current.constructor is None:
                results.append(0)
            elif finish:
                count = len(current.fields)
                fields = tuple(results[-count:]) if count else ()
                if count:
                    del results[-count:]
                results.append(self.node(current.constructor.key, fields))
            else:
                pending.append((True, current))
                pending.extend((False, child) for child in reversed(current.fields))
        return results.pop()

    def specialize(self, matrix, constructor: str):
        arity = len(self.constructors[constructor].parameters)
        rows = []
        for row in matrix:
            head, fields = self.nodes[row[0]]
            if row[0] == 0:
                rows.append((0,) * arity + row[1:])
            elif head == constructor:
                rows.append(fields + row[1:])
        return tuple(dict.fromkeys(rows))

    def witness(self, matrix: tuple[tuple[int, ...], ...], vector: tuple[int, ...]) -> tuple[int, ...] | None:
        """Return a shape covered by vector but not matrix, or None if covered."""
        root = (matrix, vector)
        pending = [("solve", root)]
        while pending:
            operation, *arguments = pending.pop()
            if operation == "solve":
                state, = arguments
                if state in self.memo:
                    continue
                self.states += 1
                if self.states > MAX_COVERAGE_STATES:
                    raise Diagnostic("E_MATCH_COMPLEXITY", f"Match coverage exceeds {MAX_COVERAGE_STATES} analysis states; split the match into smaller matches.", self.span)
                rows, candidate = state
                if not rows:
                    self.memo[state] = candidate
                    continue
                if not candidate or any(all(field == 0 for field in row) for row in rows):
                    self.memo[state] = None
                    continue
                constructor, fields = self.nodes[candidate[0]]
                if constructor is not None:
                    child = (self.specialize(rows, constructor), fields + candidate[1:])
                    pending.append(("wrap", state, child, constructor))
                    pending.append(("solve", child))
                    continue
                heads = {self.nodes[row[0]][0] for row in rows if row[0] != 0}
                family = self.families[self.constructors[next(iter(heads))].result_type.identity] if heads else ()
                if family and heads == set(family):
                    # Try one constructor at a time and stop at the first witness.
                    pending.append(("branch", state, family, 0, None))
                else:
                    default = tuple(dict.fromkeys(row[1:] for row in rows if row[0] == 0))
                    child = (default, candidate[1:])
                    missing = next((c for c in family if c not in heads), None)
                    first = self.node(missing, (0,) * len(self.constructors[missing].parameters)) if missing else 0
                    pending.append(("default", state, child, first))
                    pending.append(("solve", child))
            elif operation == "wrap":
                state, child, constructor = arguments
                witness = self.memo[child]
                if witness is None:
                    self.memo[state] = None
                else:
                    count = len(self.constructors[constructor].parameters)
                    self.memo[state] = (self.node(constructor, witness[:count]),) + witness[count:]
            elif operation == "default":
                state, child, first = arguments
                witness = self.memo[child]
                self.memo[state] = None if witness is None else (first,) + witness
            elif operation == "branch":
                state, family, index, previous = arguments
                if previous is not None and self.memo[previous] is not None:
                    constructor = family[index - 1]
                    count = len(self.constructors[constructor].parameters)
                    witness = self.memo[previous]
                    self.memo[state] = (self.node(constructor, witness[:count]),) + witness[count:]
                elif index == len(family):
                    self.memo[state] = None
                else:
                    constructor = family[index]
                    rows, candidate = state
                    count = len(self.constructors[constructor].parameters)
                    child = (self.specialize(rows, constructor), (0,) * count + candidate[1:])
                    pending.append(("branch", state, family, index + 1, child))
                    pending.append(("solve", child))
        return self.memo[root]

    def render(self, shape: int, labels: Mapping[str, str]) -> str:
        pieces, pending = [], [(False, shape)]
        while pending:
            literal, item = pending.pop()
            if literal:
                pieces.append(item)
            elif item == 0:
                pieces.append("_")
            else:
                constructor, fields = self.nodes[item]
                signature = self.constructors[constructor]
                pieces.append("(")
                pending.append((True, labels.get(constructor, signature.name) + ")"))
                for parameter, child in reversed(tuple(zip(signature.parameters, fields))):
                    pending.append((True, " " + parameter.particle + " "))
                    pending.append((False, child))
        return "".join(pieces)

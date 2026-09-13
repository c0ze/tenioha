"""Structural function types and nominal, explicitly instantiated algebraic types."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping
import unicodedata

from .syntax import KEYWORDS, PARTICLES, RESERVED, Diagnostic, Name, Span, TypeExpression


class ValueType(Enum):
    INTEGER = "整数"
    STRING = "文字列"
    BOOLEAN = "真偽値"
    UNIT = "単位"


class Effect(Enum):
    PURE = "Pure"
    IO = "IO"


@dataclass(frozen=True)
class TypeVariable:
    name: str
    owner: str

    @property
    def value(self) -> str:
        return self.name


@dataclass(frozen=True)
class DataType:
    identity: str
    arguments: tuple[Type, ...]
    name: str = field(compare=False)

    @property
    def value(self) -> str:
        return _type_text(self)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return _type_equal(self, other)

    def __hash__(self) -> int:
        return _type_hash(self)


@dataclass(frozen=True)
class FunctionType:
    parameters: tuple[tuple[str, Type], ...]
    result_type: Type
    effect: Effect
    aliases: tuple[tuple[str, ...], ...] = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        aliases = self.aliases or ((),) * len(self.parameters)
        if len(aliases) != len(self.parameters):
            raise ValueError("Particle choices must correspond to function parameters.")
        parameters, normalized, seen = [], [], set()
        for (particle, kind), alternatives in zip(self.parameters, aliases):
            choices = (particle, *alternatives)
            if any(p not in PARTICLES for p in choices):
                raise ValueError("A function type contains an unsupported particle.")
            if len(set(choices)) != len(choices) or seen.intersection(choices):
                raise ValueError("A function type cannot repeat a particle across its parameter choices.")
            seen.update(choices)
            # Choice order is immaterial; parameter order still determines evaluation.
            ordered = tuple(sorted(choices))
            parameters.append((ordered[0], kind))
            normalized.append(ordered[1:])
        object.__setattr__(self, "parameters", tuple(parameters))
        object.__setattr__(self, "aliases", tuple(normalized))

    @property
    def value(self) -> str:
        return _type_text(self)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return _type_equal(self, other)

    def __hash__(self) -> int:
        return _type_hash(self)


Type = ValueType | TypeVariable | DataType | FunctionType


def _type_equal(left: Type, right: Type) -> bool:
    # Generic substitution can compose types deeper than any source annotation.
    # Do not add Python recursion to the checker's surrounding expression stack.
    pending, seen = [(left, right)], set()
    while pending:
        left, right = pending.pop()
        pair = (id(left), id(right))
        if left is right or pair in seen:
            continue
        if type(left) is not type(right):
            return False
        seen.add(pair)
        if isinstance(left, DataType):
            if left.identity != right.identity or len(left.arguments) != len(right.arguments):
                return False
            pending.extend(zip(left.arguments, right.arguments))
        elif isinstance(left, FunctionType):
            if (left.effect is not right.effect or left.aliases != right.aliases
                    or tuple(p for p, _ in left.parameters) != tuple(p for p, _ in right.parameters)):
                return False
            pending.append((left.result_type, right.result_type))
            pending.extend((a, b) for (_, a), (_, b) in zip(left.parameters, right.parameters))
        elif left != right:
            return False
    return True


def _type_hash(kind: Type) -> int:
    hashes, pending = {}, [(False, kind)]
    while pending:
        finish, current = pending.pop()
        key = id(current)
        if key in hashes:
            continue
        if isinstance(current, DataType):
            children = current.arguments
            if finish:
                hashes[key] = hash((type(current), current.identity, tuple(hashes[id(t)] for t in children)))
        elif isinstance(current, FunctionType):
            children = tuple(t for _, t in current.parameters) + (current.result_type,)
            if finish:
                parameters = tuple((p, hashes[id(t)]) for p, t in current.parameters)
                hashes[key] = hash((type(current), parameters, hashes[id(current.result_type)], current.effect, current.aliases))
        else:
            hashes[key] = hash(current)
            continue
        if not finish:
            pending.append((True, current))
            pending.extend((False, child) for child in reversed(children))
    return hashes[id(kind)]


def _type_text(kind: Type) -> str:
    pieces, pending = [], [kind]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            pieces.append(current)
        elif isinstance(current, DataType):
            pieces.append(current.name)
            if current.arguments:
                pieces.append("<")
                pending.append(">")
                for index in range(len(current.arguments) - 1, -1, -1):
                    pending.append(current.arguments[index])
                    if index:
                        pending.append(", ")
        elif isinstance(current, FunctionType):
            pieces.append("関数[" if current.effect is Effect.PURE else "手続き[")
            pending.extend(("]", current.result_type, " -> "))
            for index in range(len(current.parameters) - 1, -1, -1):
                particle, parameter_type = current.parameters[index]
                pending.append(" " + "|".join((particle, *current.aliases[index])))
                pending.append(parameter_type)
                if index:
                    pending.append(", ")
        else:
            pieces.append(current.value)
    return "".join(pieces)


@dataclass(frozen=True)
class Parameter:
    name: str
    particle: str
    value_type: Type
    aliases: tuple[str, ...] = field(default=(), kw_only=True)

    @property
    def choices(self) -> tuple[str, ...]:
        return (self.particle, *self.aliases)


@dataclass(frozen=True)
class Signature:
    name: str
    parameters: tuple[Parameter, ...]
    result_type: Type
    effect: Effect
    type_parameters: tuple[TypeVariable, ...] = field(default=(), kw_only=True)
    identity: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", unicodedata.normalize("NFC", self.name))
        if not self.name.isidentifier() or self.name in PARTICLES | RESERVED | KEYWORDS | {"真", "偽"}:
            raise ValueError(f"Invalid function name: {self.name}")
        particles = [label for p in self.parameters for label in p.choices]
        if len(set(particles)) != len(particles):
            raise ValueError(f"{self.name}: duplicate particle in signature")
        if any(p not in PARTICLES for p in particles):
            raise ValueError(f"{self.name}: unsupported particle in signature")
        if len({p.name for p in self.parameters}) != len(self.parameters):
            raise ValueError(f"{self.name}: duplicate parameter name")

    @property
    def key(self) -> str:
        return self.name if self.identity is None else self.identity

    @property
    def value_type(self) -> FunctionType:
        return FunctionType(tuple((p.particle, p.value_type) for p in self.parameters), self.result_type, self.effect,
                            aliases=tuple(p.aliases for p in self.parameters))


@dataclass(frozen=True)
class Constructor(Signature):
    pass


@dataclass
class DataDefinition:
    name: str
    identity: str
    type_parameters: tuple[TypeVariable, ...]
    constructors: tuple[Constructor, ...] = ()


def substitute(kind: Type, substitutions: Mapping[TypeVariable, Type]) -> Type:
    resolved, pending = {}, [(False, kind)]
    while pending:
        finish, current = pending.pop()
        key = id(current)
        if key in resolved:
            continue
        if isinstance(current, TypeVariable):
            resolved[key] = substitutions.get(current, current)
            continue
        if isinstance(current, DataType):
            children = current.arguments
            if finish:
                resolved[key] = replace(current, arguments=tuple(resolved[id(t)] for t in children))
        elif isinstance(current, FunctionType):
            children = tuple(t for _, t in current.parameters) + (current.result_type,)
            if finish:
                resolved[key] = FunctionType(tuple((p, resolved[id(t)]) for p, t in current.parameters),
                                            resolved[id(current.result_type)], current.effect, aliases=current.aliases)
        else:
            resolved[key] = current
            continue
        if not finish:
            pending.append((True, current))
            pending.extend((False, child) for child in reversed(children))
    return resolved[id(kind)]


def instantiate(signature: Signature, arguments: tuple[Type, ...], span: Span) -> Signature:
    if len(arguments) != len(signature.type_parameters):
        raise Diagnostic("E_TYPE_ARGUMENTS", f"{signature.name} expects {len(signature.type_parameters)} explicit type argument(s), received {len(arguments)}.", span)
    substitutions = dict(zip(signature.type_parameters, arguments))
    return replace(signature, parameters=tuple(replace(p, value_type=substitute(p.value_type, substitutions)) for p in signature.parameters),
                   result_type=substitute(signature.result_type, substitutions), type_parameters=())


def type_parameters(names: tuple[Name, ...], owner: str, types: Mapping[str, DataDefinition]) -> tuple[TypeVariable, ...]:
    seen = set()
    for name in names:
        if name.name in seen or name.name in types or name.name in {t.value for t in ValueType}:
            raise Diagnostic("E_TYPE_PARAMETER", f"Duplicate or shadowing type parameter {name.name!r}.", name.span)
        seen.add(name.name)
    return tuple(TypeVariable(name.name, owner) for name in names)


class TypeEnvironment:
    def __init__(self, types: Mapping[str, DataDefinition]):
        self.types = types

    def resolve(self, node: TypeExpression, variables: Mapping[str, TypeVariable] | None = None) -> Type:
        variables = {} if variables is None else variables
        if node.name is None:
            aliases = node.particle_aliases or ((),) * len(node.parameters)
            particles = [p for (particle, _), alternatives in zip(node.parameters, aliases)
                         for p in (particle, *alternatives)]
            if len(set(particles)) != len(particles):
                raise Diagnostic("E_PARAMETER", "A function type cannot repeat a particle across its parameter choices.", node.span)
            return FunctionType(tuple((p, self.resolve(t, variables)) for p, t in node.parameters),
                                self.resolve(node.result, variables), Effect.IO if node.effectful else Effect.PURE, aliases=aliases)
        name = node.name.name
        if name in variables:
            kind = variables[name]
        elif name in {t.value for t in ValueType}:
            kind = ValueType(name)
        elif name in self.types:
            definition = self.types[name]
            if len(node.arguments) != len(definition.type_parameters):
                raise Diagnostic("E_TYPE_ARGUMENTS", f"{name} expects {len(definition.type_parameters)} type argument(s), received {len(node.arguments)}.", node.span)
            return DataType(definition.identity, tuple(self.resolve(t, variables) for t in node.arguments), name)
        else:
            raise Diagnostic("E_TYPE_NAME", f"Unknown type {name!r}.", node.span)
        if node.arguments:
            raise Diagnostic("E_TYPE_ARGUMENTS", f"{name} does not accept type arguments.", node.span)
        return kind

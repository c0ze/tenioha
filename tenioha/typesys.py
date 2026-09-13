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
        arguments = "<" + ", ".join(t.value for t in self.arguments) + ">" if self.arguments else ""
        return self.name + arguments


@dataclass(frozen=True)
class FunctionType:
    parameters: tuple[tuple[str, Type], ...]
    result_type: Type
    effect: Effect

    @property
    def value(self) -> str:
        keyword = "関数" if self.effect is Effect.PURE else "手続き"
        parameters = ", ".join(f"{kind.value} {particle}" for particle, kind in self.parameters)
        return f"{keyword}[{parameters} -> {self.result_type.value}]"


Type = ValueType | TypeVariable | DataType | FunctionType


@dataclass(frozen=True)
class Parameter:
    name: str
    particle: str
    value_type: Type


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
        particles = [p.particle for p in self.parameters]
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
        return FunctionType(tuple((p.particle, p.value_type) for p in self.parameters), self.result_type, self.effect)


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
    if isinstance(kind, TypeVariable):
        return substitutions.get(kind, kind)
    if isinstance(kind, DataType):
        return replace(kind, arguments=tuple(substitute(t, substitutions) for t in kind.arguments))
    if isinstance(kind, FunctionType):
        return FunctionType(tuple((p, substitute(t, substitutions)) for p, t in kind.parameters),
                            substitute(kind.result_type, substitutions), kind.effect)
    return kind


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
            particles = [particle for particle, _ in node.parameters]
            if len(set(particles)) != len(particles):
                raise Diagnostic("E_PARAMETER", "A function type cannot repeat a particle.", node.span)
            return FunctionType(tuple((p, self.resolve(t, variables)) for p, t in node.parameters),
                                self.resolve(node.result, variables), Effect.IO if node.effectful else Effect.PURE)
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

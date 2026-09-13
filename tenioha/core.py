"""Static particle/type/effect checking and evaluation of resolved calls."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Callable, Mapping, TextIO

from .patterns import CheckedPattern, Coverage
from .syntax import (AliasDeclaration, Binding, Block, Closure, Conditional, Diagnostic, Expression,
                     FunctionDeclaration, FunctionReference, Import, Literal, Match,
                     Name, Source, Span, Statement, TypeDeclaration, parse)
from .typesys import (Constructor, DataDefinition, DataType, Effect, FunctionType,
                      Parameter, Signature, Type, TypeEnvironment, TypeVariable,
                      ValueType, instantiate, type_parameters)


MAX_CALL_DEPTH = 1024
MAX_IMPORT_DEPTH = 128


@dataclass(frozen=True)
class DataValue:
    constructor: Constructor
    fields: tuple[Value, ...]


@dataclass(frozen=True)
class FunctionValue:
    signature: Signature
    definition: CheckedFunction | None = field(default=None, repr=False)
    captures: Mapping[str, Value] = field(default_factory=lambda: MappingProxyType({}), repr=False)


Value = int | str | bool | None | DataValue | FunctionValue


@dataclass(frozen=True)
class IOContext:
    stdin: TextIO
    stdout: TextIO


@dataclass(frozen=True)
class Builtin(Signature):
    implementation: Callable[[tuple[Value, ...], IOContext], Value]


@dataclass(frozen=True)
class CheckedLiteral:
    value: Value
    value_type: Type
    span: Span


@dataclass(frozen=True)
class CheckedReference:
    function: Signature
    span: Span

    @property
    def value_type(self) -> FunctionType:
        return self.function.value_type


@dataclass(frozen=True)
class CheckedCall:
    function: Signature | FunctionType
    arguments: tuple[CheckedExpression, ...]
    span: Span
    head_span: Span
    callee: CheckedExpression | None = None

    @property
    def value_type(self) -> Type:
        return self.function.result_type


@dataclass(frozen=True)
class CheckedVariable:
    name: str
    value_type: Type
    span: Span


@dataclass(frozen=True)
class CheckedBinding:
    name: str
    value: CheckedExpression
    span: Span
    value_type: Type = ValueType.UNIT


@dataclass(frozen=True)
class CheckedBlock:
    statements: tuple[CheckedStatement, ...]
    value_type: Type
    span: Span


@dataclass(frozen=True)
class CheckedConditional:
    condition: CheckedExpression
    consequent: CheckedBlock
    alternative: CheckedBlock
    span: Span

    @property
    def value_type(self) -> Type:
        return self.consequent.value_type


@dataclass(frozen=True)
class CheckedArm:
    pattern: CheckedPattern
    names: tuple[str, ...]
    body: CheckedBlock


@dataclass(frozen=True)
class CheckedMatch:
    subject: CheckedExpression
    arms: tuple[CheckedArm, ...]
    value_type: Type
    span: Span


@dataclass(frozen=True)
class CheckedClosure:
    function: CheckedFunction
    captures: tuple[str, ...]
    span: Span

    @property
    def value_type(self) -> FunctionType:
        return self.function.signature.value_type


CheckedExpression = (CheckedLiteral | CheckedCall | CheckedVariable | CheckedBlock |
                     CheckedConditional | CheckedReference | CheckedMatch | CheckedClosure)
CheckedStatement = CheckedExpression | CheckedBinding


@dataclass(frozen=True)
class CheckedFunction:
    signature: Signature
    body: CheckedBlock


@dataclass(frozen=True)
class Program:
    expressions: tuple[CheckedStatement, ...]
    definitions: Mapping[str, CheckedFunction] = field(default_factory=dict)
    types: Mapping[str, DataDefinition] = field(default_factory=dict)


def integer_text(value: int) -> str:
    """Decimal output without depending on Python's int/string digit limit."""
    if value == 0:
        return "0"
    sign, remaining = ("-" if value < 0 else ""), abs(value)
    chunks = []
    while remaining:
        remaining, chunk = divmod(remaining, 1_000_000_000)
        chunks.append(chunk)
    return sign + str(chunks[-1]) + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))


def format_value(value: Value) -> str:
    if isinstance(value, DataValue):
        # Values can be deeper than either the source or Python recursion limit.
        pieces, tasks = [], [(False, value)]
        while tasks:
            literal, item = tasks.pop()
            if literal:
                pieces.append(item)
            elif isinstance(item, DataValue):
                pieces.append("(")
                tasks.append((True, item.constructor.name + ")"))
                for parameter, child in reversed(tuple(zip(item.constructor.parameters, item.fields))):
                    tasks.append((True, " " + parameter.particle + " "))
                    tasks.append((False, child))
            elif isinstance(item, str):
                escaped = item.replace("\\", "\\\\").replace("」", "\\」").replace("\n", "\\n").replace("\t", "\\t")
                pieces.append("「" + escaped + "」")
            else:
                pieces.append(format_value(item))
        return "".join(pieces)
    if isinstance(value, FunctionValue):
        if value.definition is not None:
            keyword = "関数" if value.signature.effect is Effect.PURE else "手続き"
            return keyword + " {…}"
        return f"参照 {value.signature.name}"
    if value is None:
        return "単位"
    if type(value) is bool:
        return "真" if value else "偽"
    if type(value) is int:
        return integer_text(value)
    return value


def _display(args: tuple[Value, ...], context: IOContext) -> None:
    context.stdout.write(args[0] + "\n")
    context.stdout.flush()


def _read(args: tuple[Value, ...], context: IOContext) -> str:
    line = context.stdin.readline()
    if line == "":
        raise EOFError("No input remains for 読む.")
    # Preserve other trailing whitespace and distinguish a blank line from EOF.
    return line.removesuffix("\n").removesuffix("\r")


def _builtins() -> dict[str, Builtin]:
    integer, string = ValueType.INTEGER, ValueType.STRING
    boolean, unit = ValueType.BOOLEAN, ValueType.UNIT

    def parameter(name: str, particle: str, kind: ValueType = integer) -> Parameter:
        return Parameter(name, particle, kind)

    functions = (
        Builtin("引く", (parameter("元", "から"), parameter("量", "を")), integer,
                Effect.PURE, lambda a, io: a[0] - a[1]),
        Builtin("足す", (parameter("元", "に"), parameter("量", "を")), integer,
                Effect.PURE, lambda a, io: a[0] + a[1]),
        Builtin("掛ける", (parameter("元", "に"), parameter("量", "を")), integer,
                Effect.PURE, lambda a, io: a[0] * a[1]),
        Builtin("割る", (parameter("元", "を"), parameter("除数", "で")), integer,
                Effect.PURE, lambda a, io: a[0] // a[1]),
        Builtin("等しい", (parameter("左", "と"), parameter("右", "が")), boolean,
                Effect.PURE, lambda a, io: a[0] == a[1]),
        Builtin("否定する", (parameter("値", "を", boolean),), boolean,
                Effect.PURE, lambda a, io: not a[0]),
        Builtin("連結する", (parameter("前", "と", string), parameter("後", "を", string)),
                string, Effect.PURE, lambda a, io: a[0] + a[1]),
        Builtin("文字列にする", (parameter("値", "を"),), string,
                Effect.PURE, lambda a, io: integer_text(a[0])),
        Builtin("何もしない", (), unit, Effect.PURE, lambda a, io: None),
        Builtin("表示する", (parameter("内容", "を", string),), unit, Effect.IO, _display),
        Builtin("読む", (), string, Effect.IO, _read),
    )
    return {function.name: function for function in functions}


BUILTINS = _builtins()


def resolve_parameters(declarations, environment: TypeEnvironment, variables: Mapping[str, TypeVariable]) -> tuple[Parameter, ...]:
    names, particles, parameters = set(), set(), []
    for parameter in declarations:
        if parameter.name.name in names:
            raise Diagnostic("E_PARAMETER", f"Duplicate parameter name {parameter.name.name!r}.", parameter.name.span)
        for label, span in ((parameter.particle, parameter.particle_span), *parameter.aliases):
            if label in particles:
                raise Diagnostic("E_PARAMETER", f"Duplicate parameter particle {label!r}.", span)
            particles.add(label)
        names.add(parameter.name.name)
        parameters.append(Parameter(parameter.name.name, parameter.particle, environment.resolve(parameter.type_name, variables),
                                    aliases=tuple(label for label, _ in parameter.aliases)))
    return tuple(parameters)


def capture_names(body: CheckedBlock, parameters: frozenset[str]) -> tuple[str, ...]:
    """Find free values, respecting sequential bindings and nested closure captures."""
    captures, pending = set(), [(body, parameters)]
    while pending:
        node, bound = pending.pop()
        if isinstance(node, CheckedVariable):
            if node.name not in bound:
                captures.add(node.name)
        elif isinstance(node, CheckedClosure):
            # The outer closure must retain values needed to construct this one.
            captures.update(name for name in node.captures if name not in bound)
        elif isinstance(node, CheckedBlock):
            local = bound
            for statement in node.statements:
                if isinstance(statement, CheckedBinding):
                    pending.append((statement.value, local))
                    local = local | {statement.name}
                else:
                    pending.append((statement, local))
        elif isinstance(node, CheckedConditional):
            pending.extend((child, bound) for child in (node.condition, node.consequent, node.alternative))
        elif isinstance(node, CheckedMatch):
            pending.append((node.subject, bound))
            for arm in node.arms:
                pending.append((arm.body, bound | {name for name in arm.names if name is not None}))
        elif isinstance(node, CheckedCall):
            pending.extend((argument, bound) for argument in node.arguments)
            if node.callee is not None:
                pending.append((node.callee, bound))
    return tuple(sorted(captures))


class Checker:
    def __init__(self, functions: Mapping[str, Signature], types: TypeEnvironment,
                 data_definitions: Mapping[str, DataDefinition],
                 type_variables: Mapping[str, TypeVariable] | None = None):
        self.functions, self.types, self.data_definitions = functions, types, data_definitions
        self.type_variables = {} if type_variables is None else type_variables

    def resolve_function(self, name: Name, arguments) -> Signature:
        function = self.functions.get(name.name)
        if function is None:
            raise Diagnostic("E_FUNCTION", f"Unknown function {name.name!r}.", name.span)
        return instantiate(function, tuple(self.types.resolve(t, self.type_variables) for t in arguments), name.span)

    def statements(self, statements: tuple[Statement, ...], *, allow_io: bool,
                   variables: dict[str, Type], declared: set[str]) -> tuple[CheckedStatement, ...]:
        checked = []
        for statement in statements:
            if isinstance(statement, Binding):
                name = statement.name.name
                if name in declared:
                    raise Diagnostic("E_BINDING", f"{name!r} is already bound in this scope; bindings are immutable.", statement.name.span)
                value = self.check(statement.value, allow_io=allow_io, variables=variables)
                variables[name] = value.value_type
                declared.add(name)
                checked.append(CheckedBinding(name, value, statement.span))
            else:
                checked.append(self.check(statement, allow_io=allow_io, variables=variables))
        return tuple(checked)

    def block(self, block: Block, *, allow_io: bool, variables: Mapping[str, Type],
              declared: set[str] | None = None) -> CheckedBlock:
        statements = self.statements(block.statements, allow_io=allow_io, variables=dict(variables),
                                     declared=set() if declared is None else set(declared))
        result_type = statements[-1].value_type if statements else ValueType.UNIT
        return CheckedBlock(statements, result_type, block.span)

    def closure(self, expression: Closure, variables: Mapping[str, Type]) -> CheckedClosure:
        parameters = resolve_parameters(expression.parameters, self.types, self.type_variables)
        result_type = self.types.resolve(expression.return_type, self.type_variables)
        signature = Signature("_無名", parameters, result_type, Effect.IO if expression.effectful else Effect.PURE)
        parameter_types = {p.name: p.value_type for p in parameters}
        scope = {**variables, **parameter_types}
        # Construction is pure; the delayed body has its own declared effect.
        body = self.block(expression.body, allow_io=expression.effectful,
                          variables=scope, declared=set(parameter_types))
        if body.value_type != result_type:
            raise Diagnostic("E_RETURN", f"Closure declares {result_type.value} but its body returns {body.value_type.value}.", body.span)
        return CheckedClosure(CheckedFunction(signature, body), capture_names(body, frozenset(parameter_types)), expression.span)

    @staticmethod
    def roles(name: str, parameters: tuple[Parameter, ...], supplied: list[tuple[str, Span]], head: Span) -> dict[str, str]:
        seen, duplicates = set(), []
        canonical = {label: p.particle for p in parameters for label in p.choices}
        for particle, span in supplied:
            role = canonical.get(particle, particle)
            if role in seen:
                duplicates.append((particle, span))
            seen.add(role)
        missing = [p.particle for p in parameters if p.particle not in seen]
        unexpected = [(p, span) for p, span in supplied if p not in canonical]
        if duplicates or missing or unexpected:
            details = []
            if duplicates:
                details.append("duplicate: " + ", ".join(p for p, _ in duplicates))
            if missing:
                details.append("missing: " + ", ".join(missing))
            if unexpected:
                details.append("unexpected: " + ", ".join(p for p, _ in unexpected))
            span = (duplicates or unexpected)[0][1] if duplicates or unexpected else head
            raise Diagnostic("E_ARGUMENTS", f"{name}: {'; '.join(details)}.", span)
        return canonical

    def pattern(self, pattern, kind: Type, bindings: dict[str, Type]) -> CheckedPattern:
        if isinstance(pattern, Name):
            if pattern.name == "_":
                return CheckedPattern()
            if pattern.name in bindings:
                raise Diagnostic("E_PATTERN", f"Duplicate pattern binding {pattern.name!r}.", pattern.span)
            bindings[pattern.name] = kind
            return CheckedPattern(binding=pattern.name)
        if not isinstance(kind, DataType):
            raise Diagnostic("E_PATTERN", f"A constructor pattern requires algebraic data, received {kind.value}.", pattern.span)
        constructor = self.functions.get(pattern.constructor.name)
        if not isinstance(constructor, Constructor) or constructor.result_type.identity != kind.identity:
            raise Diagnostic("E_PATTERN", f"{pattern.constructor.name} is not a constructor of {kind.value}.", pattern.constructor.span)
        constructor = instantiate(constructor, kind.arguments, pattern.constructor.span)
        roles = self.roles(pattern.constructor.name, constructor.parameters,
                           [(particle, span) for _, particle, span in pattern.arguments], pattern.constructor.span)
        parameters = {p.particle: p for p in constructor.parameters}
        fields = {roles[particle]: self.pattern(child, parameters[roles[particle]].value_type, bindings)
                  for child, particle, _ in pattern.arguments}
        return CheckedPattern(constructor, tuple(fields[p.particle] for p in constructor.parameters))

    def match(self, expression: Match, *, allow_io: bool, variables: Mapping[str, Type]) -> CheckedMatch:
        subject = self.check(expression.subject, allow_io=False, variables=variables)
        kind = subject.value_type
        if not isinstance(kind, DataType):
            raise Diagnostic("E_MATCH_TYPE", "場合 requires an algebraic data value.", subject.span)
        definition = self.data_definitions[kind.identity]
        coverage = Coverage(self.data_definitions, expression.span)
        arms, matrix, result_type = [], (), None
        for arm in expression.arms:
            bindings = {}
            pattern = self.pattern(arm.pattern, kind, bindings)
            shape = coverage.shape(pattern)
            if coverage.witness(matrix, (shape,)) is None:
                raise Diagnostic("E_PATTERN", "Unreachable pattern: previous arms cover every matching value.", arm.pattern.span)
            matrix += ((shape,),)
            body = self.block(arm.body, allow_io=allow_io, variables={**variables, **bindings}, declared=set(bindings))
            if result_type is not None and result_type != body.value_type:
                raise Diagnostic("E_BRANCH_TYPE", f"Match arms return different types: {result_type.value} and {body.value_type.value}.", body.span)
            result_type = body.value_type
            arms.append(CheckedArm(pattern, tuple(bindings), body))
        missing = coverage.witness(matrix, (0,))
        if missing is not None:
            shape = missing[0]
            if shape == 0:
                first = definition.constructors[0]
                shape = coverage.node(first.key, (0,) * len(first.parameters))
            labels = {}
            for name, function in self.functions.items():
                labels.setdefault(function.key, name)
            raise Diagnostic("E_MATCH_EXHAUSTIVE", "Missing constructor case: " + coverage.render(shape, labels) + ".", expression.span)
        return CheckedMatch(subject, tuple(arms), result_type, expression.span)

    def check(self, expression: Expression, *, allow_io: bool,
              variables: Mapping[str, Type] | None = None) -> CheckedExpression:
        variables = {} if variables is None else variables
        if isinstance(expression, Literal):
            kind = {int: ValueType.INTEGER, str: ValueType.STRING, bool: ValueType.BOOLEAN}[type(expression.value)]
            return CheckedLiteral(expression.value, kind, expression.span)
        if isinstance(expression, Name):
            if expression.type_arguments:
                raise Diagnostic("E_NAME", "Type arguments on a value require a function call or 参照.", expression.span)
            if expression.name in variables:
                return CheckedVariable(expression.name, variables[expression.name], expression.span)
            if expression.name in self.functions:
                raise Diagnostic("E_NAME", f"{expression.name} is a function; call it with parentheses or use 参照 to obtain its value.", expression.span)
            raise Diagnostic("E_NAME", f"Unknown value {expression.name!r} in this lexical scope.", expression.span)
        if isinstance(expression, FunctionReference):
            return CheckedReference(self.resolve_function(expression.name, expression.type_arguments), expression.span)
        if isinstance(expression, Closure):
            return self.closure(expression, variables)
        if isinstance(expression, Block):
            return self.block(expression, allow_io=allow_io, variables=variables)
        if isinstance(expression, Match):
            return self.match(expression, allow_io=allow_io, variables=variables)
        if isinstance(expression, Conditional):
            condition = self.check(expression.condition, allow_io=False, variables=variables)
            if condition.value_type != ValueType.BOOLEAN:
                raise Diagnostic("E_CONDITION", f"もし expects 真偽値, received {condition.value_type.value}.", condition.span)
            consequent = self.block(expression.consequent, allow_io=allow_io, variables=variables)
            alternative = self.block(expression.alternative, allow_io=allow_io, variables=variables)
            if consequent.value_type != alternative.value_type:
                raise Diagnostic("E_BRANCH_TYPE", f"Conditional branches return different types: {consequent.value_type.value} and {alternative.value_type.value}.", alternative.span)
            return CheckedConditional(condition, consequent, alternative, expression.span)
        callee = None
        if expression.callee is not None:
            callee = self.check(expression.callee, allow_io=False, variables=variables)
            function = callee.value_type
            if not isinstance(function, FunctionType):
                raise Diagnostic("E_CALLABLE", f"適用 requires a function value, received {function.value}.", callee.span)
            parameters = tuple(Parameter(str(index), p, t, aliases=function.aliases[index])
                               for index, (p, t) in enumerate(function.parameters))
        else:
            function = self.resolve_function(expression.head, expression.type_arguments)
            parameters = function.parameters
        self.roles(expression.head.name, parameters, [(a.particle, a.span) for a in expression.arguments], expression.head.span)
        checked, by_particle = {}, {label: p for p in parameters for label in p.choices}
        # Diagnose arguments in source order; evaluate in canonical type order.
        for argument in expression.arguments:
            value = self.check(argument.expression, allow_io=False, variables=variables)
            parameter = by_particle[argument.particle]
            if value.value_type != parameter.value_type:
                raise Diagnostic("E_TYPE", f"{expression.head.name}: {argument.particle} expects {parameter.value_type.value}, received {value.value_type.value}.", argument.expression.span)
            checked[parameter.particle] = value
        if function.effect is Effect.IO and not allow_io:
            raise Diagnostic("E_EFFECT", f"{expression.head.name} performs IO. Arguments and pure contexts cannot perform IO.", expression.head.span)
        return CheckedCall(function, tuple(checked[p.particle] for p in parameters), expression.span, expression.head.span, callee)


@dataclass
class Module:
    filename: str
    items: tuple
    prefix: str
    imports: dict[str, Module] = field(default_factory=dict)
    types: dict[str, DataDefinition] = field(default_factory=dict)
    functions: dict[str, Signature] = field(default_factory=dict)
    exports: dict[str, Signature] = field(default_factory=dict)
    exported_types: dict[str, DataDefinition] = field(default_factory=dict)


class Compiler:
    def __init__(self, functions: Mapping[str, Builtin] | None):
        self.builtins = dict(BUILTINS if functions is None else functions)
        self.modules, self.loaded, self.active = [], {}, set()
        self.definitions, self.data_definitions = {}, {}

    def load(self, text: str, filename: str, *, root: bool = False, import_span: Span | None = None) -> Module:
        synthetic = filename.startswith("<") and filename.endswith(">")
        key = filename if synthetic else str(Path(filename).resolve())
        if key in self.active:
            raise Diagnostic("E_IMPORT_CYCLE", f"Cyclic module import of {filename}.", import_span)
        if key in self.loaded:
            return self.loaded[key]
        if len(self.active) >= MAX_IMPORT_DEPTH:
            raise Diagnostic("E_IMPORT_DEPTH", f"At most {MAX_IMPORT_DEPTH} modules may nest in an import chain.", import_span)
        self.active.add(key)
        module = Module(filename, parse(Source(text, filename)), "" if root else key + "::")
        for item in module.items:
            if isinstance(item, Import):
                if item.alias.name in module.imports:
                    raise Diagnostic("E_IMPORT", f"Duplicate module alias {item.alias.name!r}.", item.alias.span)
                if synthetic:
                    raise Diagnostic("E_IMPORT", "Imports need a source filename to resolve relative paths.", item.span)
                if not item.path or Path(item.path).is_absolute():
                    raise Diagnostic("E_IMPORT", "Module paths must be nonempty and relative to the importing file.", item.span)
                try:
                    path = (Path(key).parent / item.path).resolve()
                    imported_text = path.read_text(encoding="utf-8-sig")
                except (OSError, UnicodeError, ValueError, RuntimeError) as error:
                    raise Diagnostic("E_IMPORT", f"Cannot import {item.path!r}: {error}", item.span) from None
                module.imports[item.alias.name] = self.load(imported_text, str(path), import_span=item.span)
            elif not root and not isinstance(item, (FunctionDeclaration, TypeDeclaration, AliasDeclaration)):
                raise Diagnostic("E_MODULE_BODY", "Imported modules contain declarations only; put execution in the entry file.", item.span)
        self.active.remove(key)
        self.loaded[key] = module
        self.modules.append(module)  # dependencies precede their importers
        return module

    @staticmethod
    def register(module: Module, name: Name, signature: Signature) -> None:
        if name.name in module.functions:
            raise Diagnostic("E_DUPLICATE_FUNCTION", f"Function or constructor {name.name!r} is already defined.", name.span)
        module.functions[name.name] = signature
        module.exports[name.name] = signature

    def declare(self, module: Module) -> None:
        module.functions.update(self.builtins)
        for alias, imported in module.imports.items():
            module.functions.update((alias + "." + name, signature) for name, signature in imported.exports.items())
            module.types.update((alias + "." + name, kind) for name, kind in imported.exported_types.items())
        declarations = [item for item in module.items if isinstance(item, TypeDeclaration)]
        # Register every nominal type before resolving recursive constructor fields.
        for declaration in declarations:
            name = declaration.name.name
            if name in module.types or name in {t.value for t in ValueType}:
                raise Diagnostic("E_DUPLICATE_TYPE", f"Type {name!r} is already defined.", declaration.name.span)
            if not declaration.constructors:
                raise Diagnostic("E_TYPE_DECL", "A type needs at least one constructor.", declaration.span)
            definition = DataDefinition(name, module.prefix + name, ())
            module.types[name] = definition
            module.exported_types[name] = definition
            self.data_definitions[definition.identity] = definition
        for declaration in declarations:
            definition = module.types[declaration.name.name]
            definition.type_parameters = type_parameters(declaration.type_parameters, "type:" + definition.identity, module.types)
        environment = TypeEnvironment(module.types)
        for declaration in declarations:
            definition = module.types[declaration.name.name]
            variables = {v.name: v for v in definition.type_parameters}
            result_type = DataType(definition.identity, definition.type_parameters, definition.name)
            constructors = []
            for constructor in declaration.constructors:
                signature = Constructor(constructor.name.name, resolve_parameters(constructor.parameters, environment, variables),
                                        result_type, Effect.PURE, type_parameters=definition.type_parameters,
                                        identity=module.prefix + constructor.name.name)
                self.register(module, constructor.name, signature)
                constructors.append(signature)
            definition.constructors = tuple(constructors)
        for declaration in module.items:
            if not isinstance(declaration, FunctionDeclaration):
                continue
            name, key = declaration.name.name, module.prefix + declaration.name.name
            generics = type_parameters(declaration.type_parameters, "function:" + key, module.types)
            variables = {v.name: v for v in generics}
            signature = Signature(name, resolve_parameters(declaration.parameters, environment, variables),
                                  environment.resolve(declaration.return_type, variables),
                                  Effect.IO if declaration.effectful else Effect.PURE,
                                  type_parameters=generics, identity=key)
            self.register(module, declaration.name, signature)

        self.aliases(module)

    def aliases(self, module: Module) -> None:
        pending = {}
        for declaration in module.items:
            if not isinstance(declaration, AliasDeclaration):
                continue
            if declaration.name.name in module.functions or declaration.name.name in pending:
                raise Diagnostic("E_DUPLICATE_FUNCTION", f"Function or alias {declaration.name.name!r} is already defined.", declaration.name.span)
            pending[declaration.name.name] = declaration
        # Follow forward aliases iteratively; aliases keep the target's runtime key.
        for name in pending:
            path, seen, target = [], set(), name
            while target not in module.functions and target in pending:
                if target in seen:
                    raise Diagnostic("E_ALIAS_CYCLE", f"Alias cycle involving {target!r}.", path[-1].target.span)
                seen.add(target)
                declaration = pending[target]
                path.append(declaration)
                target = declaration.target.name
            if target not in module.functions:
                raise Diagnostic("E_ALIAS", f"Unknown function, procedure, or constructor {target!r}.", path[-1].target.span)
            signature = module.functions[target]
            for declaration in reversed(path):
                signature = replace(signature, name=declaration.name.name, identity=signature.key)
                self.register(module, declaration.name, signature)

    def check(self, module: Module) -> None:
        environment = TypeEnvironment(module.types)
        for declaration in module.items:
            if not isinstance(declaration, FunctionDeclaration):
                continue
            signature = module.functions[declaration.name.name]
            checker = Checker(module.functions, environment, self.data_definitions,
                              {v.name: v for v in signature.type_parameters})
            parameters = {p.name: p.value_type for p in signature.parameters}
            body = checker.block(declaration.body, allow_io=signature.effect is Effect.IO,
                                 variables=parameters, declared=set(parameters))
            if body.value_type != signature.result_type:
                raise Diagnostic("E_RETURN", f"{signature.name} declares {signature.result_type.value} but its body returns {body.value_type.value}.", body.span)
            self.definitions[signature.key] = CheckedFunction(signature, body)


def compile_source(text: str, *, filename: str = "<input>", allow_io: bool = True,
                   functions: Mapping[str, Builtin] | None = None) -> Program:
    """Load declarations and check the entire import graph before program I/O."""
    compiler = Compiler(functions)
    root = compiler.load(text, str(filename), root=True)
    for module in compiler.modules:
        compiler.declare(module)
    for module in compiler.modules:
        compiler.check(module)
    checker = Checker(root.functions, TypeEnvironment(root.types), compiler.data_definitions)
    statements = tuple(item for item in root.items if not isinstance(item, (FunctionDeclaration, TypeDeclaration, Import, AliasDeclaration)))
    return Program(checker.statements(statements, allow_io=allow_io, variables={}, declared=set()),
                   compiler.definitions, compiler.data_definitions)


def _bind_pattern(pattern: CheckedPattern, value: Value) -> dict[str, Value] | None:
    """Try one arm without executing code or leaking bindings from a failed arm."""
    bindings, pending = {}, [(pattern, value)]
    while pending:
        pattern, value = pending.pop()
        if pattern.constructor is None:
            if pattern.binding is not None:
                bindings[pattern.binding] = value
        elif not isinstance(value, DataValue) or value.constructor.key != pattern.constructor.key:
            return None
        else:
            pending.extend(reversed(tuple(zip(pattern.fields, value.fields))))
    return bindings


def _evaluate(expression: CheckedStatement, context: IOContext,
              variables: dict[str, Value], definitions: Mapping[str, CheckedFunction]) -> Value:
    """Explicit evaluation stack: language recursion never consumes Python frames."""
    tasks = [("evaluate", expression, variables)]
    values = []
    call_depth = 0
    while tasks:
        operation, *arguments = tasks.pop()
        if operation == "evaluate":
            node, scope = arguments
            if isinstance(node, CheckedLiteral):
                values.append(node.value)
            elif isinstance(node, CheckedReference):
                values.append(FunctionValue(node.function))
            elif isinstance(node, CheckedClosure):
                captures = MappingProxyType({name: scope[name] for name in node.captures})
                values.append(FunctionValue(node.function.signature, node.function, captures))
            elif isinstance(node, CheckedVariable):
                values.append(scope[node.name])
            elif isinstance(node, CheckedBinding):
                tasks.append(("bind", node.name, scope))
                tasks.append(("evaluate", node.value, scope))
            elif isinstance(node, CheckedBlock):
                local_scope = dict(scope)
                if not node.statements:
                    values.append(None)
                for index in range(len(node.statements) - 1, -1, -1):
                    if index != len(node.statements) - 1:
                        tasks.append(("discard",))
                    tasks.append(("evaluate", node.statements[index], local_scope))
            elif isinstance(node, CheckedConditional):
                tasks.append(("choose", node, scope))
                tasks.append(("evaluate", node.condition, scope))
            elif isinstance(node, CheckedMatch):
                tasks.append(("match", node, scope))
                tasks.append(("evaluate", node.subject, scope))
            else:
                tasks.append(("apply", node))
                for argument in reversed(node.arguments):
                    tasks.append(("evaluate", argument, scope))
                if node.callee is not None:
                    tasks.append(("evaluate", node.callee, scope))
        elif operation == "bind":
            name, scope = arguments
            scope[name] = values.pop()
            values.append(None)
        elif operation == "discard":
            values.pop()
        elif operation == "choose":
            node, scope = arguments
            branch = node.consequent if values.pop() else node.alternative
            tasks.append(("evaluate", branch, scope))
        elif operation == "match":
            node, scope = arguments
            value = values.pop()
            for arm in node.arms:
                bindings = _bind_pattern(arm.pattern, value)
                if bindings is not None:
                    tasks.append(("evaluate", arm.body, {**scope, **bindings}))
                    break
            else:
                raise Diagnostic("E_MATCH", "No match arm accepts this value.", node.span)
        elif operation == "return":
            call_depth -= 1
        elif operation == "apply":
            node, = arguments
            count = len(node.arguments)
            actual = tuple(values[-count:]) if count else ()
            if count:
                del values[-count:]
            function_value = values.pop() if node.callee is not None else None
            function = function_value.signature if function_value is not None else node.function
            if isinstance(function, Constructor):
                values.append(DataValue(function, actual))
            elif isinstance(function, Builtin):
                try:
                    values.append(function.implementation(actual, context))
                except ZeroDivisionError:
                    raise Diagnostic("E_ZERO_DIVISION", "Cannot divide by zero.", node.head_span) from None
                except (EOFError, OSError, UnicodeError) as error:
                    raise Diagnostic("E_IO", str(error), node.head_span) from None
            else:
                if call_depth >= MAX_CALL_DEPTH:
                    raise Diagnostic("E_CALL_DEPTH", f"At most {MAX_CALL_DEPTH} user function calls may be active at once.", node.head_span)
                call_depth += 1
                scope = dict(function_value.captures) if function_value is not None else {}
                scope.update((p.name, value) for p, value in zip(function.parameters, actual))
                definition = function_value.definition if function_value is not None else None
                if definition is None:
                    definition = definitions[function.key]
                tasks.append(("return",))
                tasks.append(("evaluate", definition.body, scope))
    return values.pop()


def execute(program: Program, *, stdin: TextIO | None = None,
            stdout: TextIO | None = None) -> list[Value]:
    context = IOContext(sys.stdin if stdin is None else stdin, sys.stdout if stdout is None else stdout)
    variables = {}
    return [_evaluate(expression, context, variables, program.definitions) for expression in program.expressions]


def run(text: str, *, filename: str = "<input>", allow_io: bool = True,
        stdin: TextIO | None = None, stdout: TextIO | None = None) -> list[Value]:
    return execute(compile_source(text, filename=filename, allow_io=allow_io), stdin=stdin, stdout=stdout)

"""The source reader: unambiguous boundaries, Japanese strings, predicate-last calls."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property
import re
import unicodedata


PARTICLES = frozenset({"が", "を", "に", "で", "から", "へ", "と", "まで"})
RESERVED = frozenset({"は", "の", "て", "なら"})
KEYWORDS = frozenset({"関数", "手続き", "もし", "そうでなければ", "型", "場合", "参照", "適用", "取込", "別名"})
MAX_NESTING = 128
LINE_BREAK = re.compile(r"\r\n|[\n\r\u0085\u2028\u2029]")


@dataclass(frozen=True)
class Source:
    text: str
    name: str = "<input>"

    @cached_property
    def line_starts(self) -> tuple[int, ...]:
        return (0, *(match.end() for match in LINE_BREAK.finditer(self.text)))


@dataclass(frozen=True)
class Span:
    source: Source
    start: int
    end: int

    @property
    def line(self) -> int:
        return bisect_right(self.source.line_starts, self.start)

    @property
    def column(self) -> int:
        return self.start - self.source.line_starts[self.line - 1] + 1


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if char == "\ufeff":
            continue
        if char == "\t":
            width += 4 - width % 4
        elif not unicodedata.combining(char):
            width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


class Diagnostic(Exception):
    def __init__(self, code: str, message: str, span: Span):
        super().__init__(message)
        self.code, self.message, self.span = code, message, span

    def render(self) -> str:
        text, start, end = self.span.source.text, self.span.start, self.span.end
        line_start = self.span.source.line_starts[self.span.line - 1]
        line_break = LINE_BREAK.search(text, line_start)
        line_end = line_break.start() if line_break else len(text)
        prefix = text[line_start:start]
        width = max(1, _display_width(text[line_start:min(end, line_end)])
                    - _display_width(prefix))
        # Expand tabs using display columns, including wide Japanese characters.
        displayed, column = [], 0
        for char in text[line_start:line_end]:
            if char == "\t":
                padding = 4 - column % 4
                displayed.append(" " * padding)
                column += padding
            else:
                displayed.append(char)
                column += _display_width(char)
        location = f"{self.span.source.name}:{self.span.line}:{self.span.column}"
        return (f"{location}: {self.code}: {self.message}\n"
                f"  {''.join(displayed)}\n  {' ' * _display_width(prefix)}{'^' * width}")


@dataclass(frozen=True)
class Token:
    kind: str
    value: str | int | bool
    span: Span


def tokenize(source: Source) -> tuple[Token, ...]:
    text, tokens = source.text, []
    # Accept one initial BOM without changing the offsets in the original source.
    pos = 1 if text.startswith("\ufeff") else 0
    punctuation = {"(": "OPEN", ")": "CLOSE", "。": "STOP", "{": "BLOCK_OPEN",
                   "}": "BLOCK_CLOSE", ":": "COLON", "<": "TYPE_OPEN", ">": "TYPE_CLOSE",
                   "[": "SQUARE_OPEN", "]": "SQUARE_CLOSE", ",": "COMMA", ".": "DOT", "|": "ALTERNATIVE"}
    boundaries = frozenset("()。「」;{}:<>[],.|")
    escapes = {"\\": "\\", "」": "」", "n": "\n", "t": "\t"}
    while pos < len(text):
        char = text[pos]
        if char.isspace():
            pos += 1
            continue
        if char == ";":
            newline = LINE_BREAK.search(text, pos)
            pos = len(text) if newline is None else newline.end()
            continue
        start = pos
        if text.startswith("->", pos):
            pos += 2
            tokens.append(Token("ARROW", "->", Span(source, start, pos)))
            continue
        if char in punctuation:
            if char == "." and tokens and tokens[-1].kind == "INTEGER" and tokens[-1].span.end == pos:
                raise Diagnostic("E_TOKEN", "Floating-point literals are not supported.", Span(source, tokens[-1].span.start, pos + 1))
            pos += 1
            tokens.append(Token(punctuation[char], char, Span(source, start, pos)))
            continue
        if char == "「":
            pos += 1
            value = []
            while pos < len(text) and text[pos] != "」":
                if text[pos] == "\\":
                    escape_start = pos
                    pos += 1
                    if pos >= len(text):
                        break
                    if text[pos] not in escapes:
                        raise Diagnostic("E_ESCAPE", "Unknown string escape; use \\\\, \\」, \\n, or \\t.",
                                         Span(source, escape_start, pos + 1))
                    value.append(escapes[text[pos]])
                else:
                    value.append(text[pos])
                pos += 1
            if pos >= len(text):
                raise Diagnostic("E_STRING", "Unterminated string; expected 」.",
                                 Span(source, start, start + 1))
            pos += 1
            tokens.append(Token("STRING", "".join(value), Span(source, start, pos)))
            continue
        if char == "」":
            raise Diagnostic("E_STRING", "Unexpected closing quote 」.", Span(source, pos, pos + 1))
        while (pos < len(text) and not text[pos].isspace() and text[pos] not in boundaries
               and not text.startswith("->", pos)):
            pos += 1
        word = text[start:pos]
        span = Span(source, start, pos)
        normalized = unicodedata.normalize("NFC", word)
        number = re.match(r"-?[0-9]+", word)
        suffix = unicodedata.normalize("NFC", word[number.end():]) if number else ""
        # Only split an integer followed by a complete particle word. Never
        # split identifier words or guess a particle prefix in 5から引く.
        if number and (not suffix or suffix in PARTICLES):
            integer = number.group()
            integer_end = start + number.end()
            integer_span = Span(source, start, integer_end)
            # A documented reader limit, independent of Python's int conversion setting.
            if len(integer.lstrip("-")) > 4096:
                raise Diagnostic("E_INTEGER", "Integer literals may contain at most 4096 digits.", integer_span)
            digits = integer.lstrip("-")
            value = 0
            for offset in range(0, len(digits), 9):
                chunk = digits[offset:offset + 9]
                value = value * 10 ** len(chunk) + int(chunk)
            tokens.append(Token("INTEGER", -value if integer.startswith("-") else value, integer_span))
            if suffix:
                tokens.append(Token("PARTICLE", suffix, Span(source, integer_end, pos)))
        elif normalized in {"真", "偽"}:
            tokens.append(Token("BOOLEAN", normalized == "真", span))
        elif normalized in PARTICLES:
            tokens.append(Token("PARTICLE", normalized, span))
        elif normalized in RESERVED:
            tokens.append(Token("RESERVED", normalized, span))
        elif normalized in KEYWORDS:
            tokens.append(Token("KEYWORD", normalized, span))
        elif normalized.isidentifier():
            tokens.append(Token("NAME", normalized, span))
        else:
            raise Diagnostic("E_TOKEN",
                             f"Invalid token {word!r}. Use ASCII numbers/parentheses and separate identifier words; an integer may attach one complete particle.",
                             span)
    tokens.append(Token("END", "", Span(source, len(text), len(text))))
    return tuple(tokens)


@dataclass(frozen=True)
class Literal:
    value: int | str | bool
    span: Span


@dataclass(frozen=True)
class Name:
    name: str
    span: Span
    type_arguments: tuple[TypeExpression, ...] = ()


@dataclass(frozen=True)
class TypeExpression:
    name: Name | None
    arguments: tuple[TypeExpression, ...]
    parameters: tuple[tuple[str, TypeExpression], ...]
    result: TypeExpression | None
    effectful: bool
    span: Span
    particle_aliases: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class FunctionReference:
    name: Name
    type_arguments: tuple[TypeExpression, ...]
    span: Span


@dataclass(frozen=True)
class Argument:
    expression: Expression
    particle: str
    span: Span


@dataclass(frozen=True)
class Call:
    head: Name
    arguments: tuple[Argument, ...]
    span: Span
    type_arguments: tuple[TypeExpression, ...] = ()
    callee: Expression | None = None


@dataclass(frozen=True)
class Binding:
    name: Name
    value: Expression
    span: Span


@dataclass(frozen=True)
class Block:
    statements: tuple[Statement, ...]
    span: Span


@dataclass(frozen=True)
class Conditional:
    condition: Expression
    consequent: Block
    alternative: Block
    span: Span


@dataclass(frozen=True)
class ParameterDeclaration:
    name: Name
    type_name: TypeExpression
    particle: str
    particle_span: Span
    aliases: tuple[tuple[str, Span], ...] = ()


@dataclass(frozen=True)
class FunctionDeclaration:
    name: Name
    parameters: tuple[ParameterDeclaration, ...]
    return_type: TypeExpression
    body: Block
    effectful: bool
    span: Span
    type_parameters: tuple[Name, ...] = ()


@dataclass(frozen=True)
class Closure:
    parameters: tuple[ParameterDeclaration, ...]
    return_type: TypeExpression
    body: Block
    effectful: bool
    span: Span


@dataclass(frozen=True)
class ConstructorDeclaration:
    name: Name
    parameters: tuple[ParameterDeclaration, ...]


@dataclass(frozen=True)
class TypeDeclaration:
    name: Name
    type_parameters: tuple[Name, ...]
    constructors: tuple[ConstructorDeclaration, ...]
    span: Span


@dataclass(frozen=True)
class ConstructorPattern:
    constructor: Name
    arguments: tuple[tuple[Pattern, str, Span], ...]
    span: Span


Pattern = Name | ConstructorPattern


@dataclass(frozen=True)
class MatchArm:
    pattern: Pattern
    body: Block


@dataclass(frozen=True)
class Match:
    subject: Expression
    arms: tuple[MatchArm, ...]
    span: Span


@dataclass(frozen=True)
class Import:
    path: str
    alias: Name
    span: Span


@dataclass(frozen=True)
class AliasDeclaration:
    name: Name
    target: Name
    span: Span


Expression = Literal | Name | Call | Block | Conditional | Match | FunctionReference | Closure
Statement = Expression | Binding
TopLevel = Statement | FunctionDeclaration | TypeDeclaration | Import | AliasDeclaration


class Parser:
    def __init__(self, source: Source):
        self.tokens = tokenize(source)
        self.pos = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def expect(self, kind: str, description: str, value: str | None = None) -> Token:
        token = self.current
        if token.kind != kind or (value is not None and token.value != value):
            raise Diagnostic("E_SYNTAX", f"Expected {description}.", token.span)
        self.pos += 1
        return token

    def depth(self, depth: int) -> None:
        if depth >= MAX_NESTING:
            raise Diagnostic("E_DEPTH", f"Expressions and types may nest at most {MAX_NESTING} levels.", self.current.span)

    def name(self, description: str, *, qualified: bool = False) -> Name:
        token = self.expect("NAME", description)
        name, end = str(token.value), token.span.end
        while qualified and self.current.kind == "DOT":
            self.pos += 1
            part = self.expect("NAME", "a name after .")
            name += "." + str(part.value)
            end = part.span.end
        return Name(name, Span(token.span.source, token.span.start, end))

    def type_parameters(self) -> tuple[Name, ...]:
        if self.current.kind != "TYPE_OPEN":
            return ()
        self.pos += 1
        names = [self.name("a type parameter")]
        while self.current.kind == "COMMA":
            self.pos += 1
            names.append(self.name("a type parameter after ,"))
        self.expect("TYPE_CLOSE", "> after type parameters")
        return tuple(names)

    def type_arguments(self, depth: int = 0) -> tuple[TypeExpression, ...]:
        if self.current.kind != "TYPE_OPEN":
            return ()
        self.depth(depth)
        self.pos += 1
        types = [self.type_expression(depth + 1)]
        while self.current.kind == "COMMA":
            self.pos += 1
            types.append(self.type_expression(depth + 1))
        self.expect("TYPE_CLOSE", "> after type arguments")
        return tuple(types)

    def type_expression(self, depth: int = 0) -> TypeExpression:
        self.depth(depth)
        token = self.current
        if token.kind == "KEYWORD" and token.value in {"関数", "手続き"}:
            self.pos += 1
            self.expect("SQUARE_OPEN", "[ after a function type keyword")
            parameters, aliases = [], []
            while self.current.kind != "ARROW":
                kind = self.type_expression(depth + 1)
                particle, alternatives = self.particle_choices()
                parameters.append((str(particle.value), kind))
                aliases.append(tuple(str(t.value) for t in alternatives))
                if self.current.kind != "ARROW":
                    self.expect("COMMA", ", between function type parameters")
            self.pos += 1
            result = self.type_expression(depth + 1)
            close = self.expect("SQUARE_CLOSE", "] after the function result type")
            return TypeExpression(None, (), tuple(parameters), result, token.value == "手続き",
                                  Span(token.span.source, token.span.start, close.span.end), tuple(aliases))
        name = self.name("a type name", qualified=True)
        arguments = self.type_arguments(depth)
        end = self.tokens[self.pos - 1].span.end
        return TypeExpression(name, arguments, (), None, False, Span(name.span.source, name.span.start, end))

    def particle_choices(self) -> tuple[Token, tuple[Token, ...]]:
        first = self.expect("PARTICLE", "a parameter particle (は is not an argument label)")
        alternatives = []
        while self.current.kind == "ALTERNATIVE":
            self.pos += 1
            alternatives.append(self.expect("PARTICLE", "a particle after |"))
        return first, tuple(alternatives)

    def parameters(self) -> tuple[ParameterDeclaration, ...]:
        parameters = []
        while self.current.kind == "OPEN":
            self.pos += 1
            parameter_name = self.name("a parameter name")
            self.expect("COLON", ": before the parameter type")
            type_name = self.type_expression()
            self.expect("CLOSE", ") after the parameter type")
            particle, alternatives = self.particle_choices()
            parameters.append(ParameterDeclaration(parameter_name, type_name, str(particle.value), particle.span,
                                                   tuple((str(t.value), t.span) for t in alternatives)))
        return tuple(parameters)

    def program(self) -> tuple[TopLevel, ...]:
        statements = []
        while self.current.kind != "END":
            keyword = self.current.value if self.current.kind == "KEYWORD" else None
            if keyword in {"関数", "手続き"} and self.tokens[self.pos + 1].kind == "NAME":
                statements.append(self.declaration())
            elif keyword == "型":
                statements.append(self.type_declaration())
            elif keyword == "別名":
                opening = self.current
                self.pos += 1
                name = self.name("an alternate function name")
                self.expect("RESERVED", "は before the alias target", "は")
                target = self.name("a function, procedure, or constructor name", qualified=True)
                if self.current.kind == "TYPE_OPEN":
                    raise Diagnostic("E_ALIAS", "Aliases name whole generic functions; specialize at the call or reference.", self.current.span)
                statements.append(AliasDeclaration(name, target, Span(opening.span.source, opening.span.start, target.span.end)))
            elif keyword == "取込":
                opening = self.current
                self.pos += 1
                path = self.expect("STRING", "a relative module path in 「…」")
                self.expect("PARTICLE", "と before the module alias", "と")
                alias = self.name("a module alias")
                statements.append(Import(str(path.value), alias, Span(opening.span.source, opening.span.start, alias.span.end)))
            else:
                statements.append(self.statement())
            if self.current.kind == "STOP":
                self.pos += 1
        return tuple(statements)

    def declaration(self) -> FunctionDeclaration:
        keyword = self.current
        self.pos += 1
        name = self.name("a function name after 関数/手続き")
        type_parameters = self.type_parameters()
        parameters = self.parameters()
        self.expect("ARROW", "-> before the return type")
        return_type = self.type_expression()
        body = self.block(0)
        return FunctionDeclaration(name, parameters, return_type, body, keyword.value == "手続き",
                                   Span(keyword.span.source, keyword.span.start, body.span.end), type_parameters)

    def closure(self, depth: int) -> Closure:
        self.depth(depth)
        keyword = self.current
        self.pos += 1
        parameters = self.parameters()
        self.expect("ARROW", "-> before the closure return type")
        return_type = self.type_expression()
        body = self.block(depth + 1)
        return Closure(parameters, return_type, body, keyword.value == "手続き",
                       Span(keyword.span.source, keyword.span.start, body.span.end))

    def type_declaration(self) -> TypeDeclaration:
        opening = self.current
        self.pos += 1
        name = self.name("a name after 型")
        type_parameters = self.type_parameters()
        self.expect("BLOCK_OPEN", "{ before constructors")
        constructors = []
        while self.current.kind != "BLOCK_CLOSE":
            if self.current.kind == "END":
                raise Diagnostic("E_BLOCK", "Unclosed type declaration; expected }.", opening.span)
            constructor = self.name("a constructor name")
            constructors.append(ConstructorDeclaration(constructor, self.parameters()))
            if self.current.kind == "STOP":
                self.pos += 1
        closing = self.current
        self.pos += 1
        return TypeDeclaration(name, type_parameters, tuple(constructors), Span(opening.span.source, opening.span.start, closing.span.end))

    def statement(self, depth: int = 0) -> Statement:
        if (self.current.kind == "NAME" and self.tokens[self.pos + 1].kind == "RESERVED"
                and self.tokens[self.pos + 1].value == "は"):
            name = self.name("a binding name")
            self.pos += 1
            value = self.expression(depth)
            return Binding(name, value, Span(name.span.source, name.span.start, value.span.end))
        return self.expression(depth)

    def block(self, depth: int) -> Block:
        self.depth(depth)
        opening = self.expect("BLOCK_OPEN", "{ to begin a block")
        statements = []
        while self.current.kind != "BLOCK_CLOSE":
            if self.current.kind == "END":
                raise Diagnostic("E_BLOCK", "Unclosed block; expected }.", opening.span)
            statements.append(self.statement(depth + 1))
            if self.current.kind == "STOP":
                self.pos += 1
        closing = self.current
        self.pos += 1
        return Block(tuple(statements), Span(opening.span.source, opening.span.start, closing.span.end))

    def match(self, depth: int) -> Match:
        self.depth(depth)
        opening = self.current
        self.pos += 1
        subject = self.expression(depth + 1)
        self.expect("BLOCK_OPEN", "{ before match arms")
        arms = []
        while self.current.kind != "BLOCK_CLOSE":
            pattern = self.pattern(depth + 1)
            self.expect("RESERVED", "なら after the constructor pattern", "なら")
            arms.append(MatchArm(pattern, self.block(depth + 1)))
            if self.current.kind == "STOP":
                self.pos += 1
        closing = self.current
        self.pos += 1
        return Match(subject, tuple(arms), Span(opening.span.source, opening.span.start, closing.span.end))

    def pattern(self, depth: int) -> Pattern:
        if self.current.kind == "NAME":
            name = self.name("a pattern binding", qualified=True)
            if "." in name.name:
                raise Diagnostic("E_PATTERN", "Pattern bindings must be unqualified; put constructors in parentheses.", name.span)
            return name
        self.depth(depth)
        opening = self.expect("OPEN", "a binding, _, or parenthesized constructor pattern")
        arguments = []
        while True:
            if self.current.kind == "NAME":
                name = self.name("a pattern binding or constructor", qualified=True)
                if self.current.kind == "CLOSE":
                    closing = self.current
                    self.pos += 1
                    return ConstructorPattern(name, tuple(arguments), Span(opening.span.source, opening.span.start, closing.span.end))
                if "." in name.name:
                    raise Diagnostic("E_PATTERN", "Pattern bindings must be unqualified names.", name.span)
                child = name
            else:
                child = self.pattern(depth + 1)
            particle = self.expect("PARTICLE", "a particle after the field pattern")
            arguments.append((child, str(particle.value), particle.span))

    def expression(self, depth: int = 0) -> Expression:
        token = self.current
        if token.kind in {"INTEGER", "STRING", "BOOLEAN"}:
            self.pos += 1
            return Literal(token.value, token.span)
        if token.kind == "NAME":
            name = self.name("a name", qualified=True)
            type_arguments = self.type_arguments(depth)
            return Name(name.name, Span(name.span.source, name.span.start, self.tokens[self.pos - 1].span.end), type_arguments)
        if token.kind == "BLOCK_OPEN":
            return self.block(depth)
        if token.kind == "KEYWORD" and token.value == "参照":
            self.pos += 1
            name = self.name("a function name after 参照", qualified=True)
            types = self.type_arguments(depth)
            return FunctionReference(name, types, Span(token.span.source, token.span.start, self.tokens[self.pos - 1].span.end))
        if token.kind == "KEYWORD" and token.value == "場合":
            return self.match(depth)
        if token.kind == "KEYWORD" and token.value == "もし":
            self.depth(depth)
            self.pos += 1
            condition = self.expression(depth + 1)
            self.expect("RESERVED", "なら after the condition", "なら")
            consequent = self.block(depth + 1)
            self.expect("KEYWORD", "そうでなければ and an alternative branch", "そうでなければ")
            alternative = self.block(depth + 1)
            return Conditional(condition, consequent, alternative, Span(token.span.source, token.span.start, alternative.span.end))
        if (token.kind == "KEYWORD" and token.value in {"関数", "手続き"}
                and self.tokens[self.pos + 1].kind != "NAME"):
            return self.closure(depth)
        if token.kind == "KEYWORD" and token.value in {"関数", "手続き", "型", "取込", "別名"}:
            raise Diagnostic("E_DEFINITION", "Declarations and imports are only allowed at file scope.", token.span)
        if token.kind == "RESERVED":
            raise Diagnostic("E_RESERVED", f"{token.value} is a syntax word, not a value or argument label.", token.span)
        if token.kind != "OPEN":
            raise Diagnostic("E_SYNTAX", "Expected a value or a parenthesized call.", token.span)
        self.depth(depth)
        self.pos += 1
        arguments = []
        while True:
            if self.current.kind == "END":
                raise Diagnostic("E_PAREN", "Unclosed call; expected a function name and ).", token.span)
            if self.current.kind == "CLOSE":
                raise Diagnostic("E_HEAD", "A call must end with its function name.", self.current.span)
            if self.current.kind == "KEYWORD" and self.current.value == "適用":
                head = Name("適用", self.current.span)
                self.pos += 1
                callee = self.expression(depth + 1)
                close = self.expect("CLOSE", ") after the function value")
                return Call(head, tuple(arguments), Span(token.span.source, token.span.start, close.span.end), callee=callee)
            expression = self.expression(depth + 1)
            if isinstance(expression, Name) and self.current.kind == "CLOSE":
                end = self.current.span.end
                self.pos += 1
                return Call(expression, tuple(arguments), Span(token.span.source, token.span.start, end), expression.type_arguments)
            particle = self.current
            if particle.kind == "RESERVED":
                raise Diagnostic("E_RESERVED", f"{particle.value} is reserved; it cannot substitute for an argument particle.", particle.span)
            if particle.kind == "END":
                raise Diagnostic("E_PAREN", "Unclosed call; expected ).", token.span)
            if particle.kind != "PARTICLE":
                raise Diagnostic("E_PARTICLE", "Expected an argument particle after this value; put the function name last.", particle.span)
            self.pos += 1
            arguments.append(Argument(expression, str(particle.value), particle.span))


def parse(source: Source) -> tuple[TopLevel, ...]:
    return Parser(source).program()

from dataclasses import replace
import io
from itertools import permutations
from pathlib import Path
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import BUILTINS, Builtin, Effect, Parameter, ValueType, format_value
from tenioha.syntax import MAX_NESTING, Source, tokenize


class LanguageTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_subtraction_permutations_and_role_changes(self):
        self.assertEqual(run("(5 から 3 を 引く) (3 を 5 から 引く) (3 から 5 を 引く)"), [2, 2, -2])

    def test_nested_calls(self):
        self.assertEqual(run("((5 から 3 を 引く) に 4 を 足す)"), [6])

    def test_every_two_argument_builtin_permutation(self):
        cases = [
            ("引く", ["11 から", "4 を"], 7),
            ("足す", ["11 に", "4 を"], 15),
            ("掛ける", ["11 に", "4 を"], 44),
            ("割る", ["11 を", "4 で"], 2),
            ("等しい", ["11 と", "4 が"], False),
            ("連結する", ["「先」 と", "「後」 を"], "先後"),
        ]
        for name, args, expected in cases:
            for ordering in permutations(args):
                with self.subTest(name=name, ordering=ordering):
                    self.assertEqual(run(f"({' '.join(ordering)} {name})"), [expected])

    def test_four_argument_permutations_preserve_roles(self):
        function = Builtin("組み立てる", tuple(Parameter(p, p, ValueType.INTEGER) for p in ("から", "を", "に", "で")),
                           ValueType.INTEGER, Effect.PURE,
                           lambda a, ctx: a[0] * 1000 + a[1] * 100 + a[2] * 10 + a[3])
        for ordering in permutations(["1 から", "2 を", "3 に", "4 で"]):
            with self.subTest(ordering=ordering):
                program = compile_source(f"({' '.join(ordering)} 組み立てる)", functions={function.name: function})
                self.assertEqual(execute(program), [1234])

    def test_boolean_literals_and_functions(self):
        results = run("真 偽 (真 を 否定する) (5 と 5 が 等しい)")
        self.assertEqual(results, [True, False, False, True])
        self.assertTrue(all(type(value) is bool for value in results))

    def test_bool_is_not_an_integer(self):
        for source in ["(真 から 3 を 引く)", "(1 を 否定する)", "(偽 を 文字列にする)"]:
            with self.subTest(source=source):
                self.error(source, "E_TYPE")

    def test_conversion_and_unit(self):
        self.assertEqual(run("(-123 を 文字列にする) (何もしない)"), ["-123", None])
        self.assertEqual([format_value(v) for v in [True, False, None, -12, "猫"]], ["真", "偽", "単位", "-12", "猫"])

    def test_integer_division_floors_negative_results(self):
        self.assertEqual(run("(-7 を 3 で 割る) (7 を -3 で 割る)"), [-3, -3])

    def test_duplicate_and_missing_particle_reported_together(self):
        error = self.error("(3 に 5 に 足す)", "E_ARGUMENTS")
        self.assertIn("duplicate: に", error.message)
        self.assertIn("missing: を", error.message)
        self.assertEqual(error.span.start, 7)

    def test_missing_unexpected_and_wrong_particles(self):
        cases = [("(5 から 引く)", "missing: を"),
                 ("(5 から 3 を 1 で 引く)", "unexpected: で"),
                 ("(5 へ 3 を 足す)", "missing: に")]
        for source, message in cases:
            with self.subTest(source=source):
                self.assertIn(message, self.error(source, "E_ARGUMENTS").message)

    def test_wrong_value_type(self):
        error = self.error("(「五」 から 3 を 引く)", "E_TYPE")
        self.assertIn("から expects 整数, received 文字列", error.message)
        self.assertEqual(error.span.start, 1)

    def test_signature_rejects_repeated_particles_even_with_distinct_types(self):
        with self.assertRaisesRegex(ValueError, "duplicate particle"):
            replace(BUILTINS["足す"], parameters=(Parameter("時", "に", ValueType.INTEGER),
                                               Parameter("場所", "に", ValueType.STRING)))

    def test_signature_rejects_reserved_particle_and_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, "unsupported particle"):
            replace(BUILTINS["足す"], parameters=(Parameter("元", "は", ValueType.INTEGER),))
        with self.assertRaisesRegex(ValueError, "duplicate parameter name"):
            replace(BUILTINS["足す"], parameters=(Parameter("元", "に", ValueType.INTEGER),
                                               Parameter("元", "を", ValueType.INTEGER)))

    def test_topic_does_not_substitute_for_subject(self):
        self.error("(5 と 5 は 等しい)", "E_RESERVED")

    def test_display_and_source_order(self):
        output = io.StringIO()
        self.assertEqual(run("(「一」 を 表示する)。(「二」 を 表示する)。", stdout=output), [None, None])
        self.assertEqual(output.getvalue(), "一\n二\n")

    def test_pure_context_rejects_io(self):
        for source in ["(「猫」 を 表示する)", "(読む)"]:
            with self.subTest(source=source):
                self.error(source, "E_EFFECT", allow_io=False)

    def test_nested_io_rejected_before_reading_or_printing(self):
        source, output = io.StringIO("unused\n"), io.StringIO()
        self.error("((読む) を 表示する)", "E_EFFECT", stdin=source, stdout=output)
        self.assertEqual(source.tell(), 0)
        self.assertEqual(output.getvalue(), "")

    def test_late_static_errors_prevent_earlier_io(self):
        for bad in ["(5 に 引く)", "(真 を 文字列にする)", "(未知)", "("]:
            with self.subTest(bad=bad):
                output, source = io.StringIO(), io.StringIO("unused\n")
                with self.assertRaises(Diagnostic):
                    run(f"(「printed too early」 を 表示する) (読む) {bad}", stdout=output, stdin=source)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(source.tell(), 0)

    def test_compile_does_not_execute_io(self):
        # EOF stdin would fail if compilation accidentally evaluated this call.
        program = compile_source("(読む)")
        self.assertEqual(execute(program, stdin=io.StringIO("ready\n")), ["ready"])

    def test_read_preserves_spaces_and_distinguishes_blank_from_eof(self):
        self.assertEqual(run("(読む) (読む)", stdin=io.StringIO("  猫  \r\n\n")), ["  猫  ", ""])
        self.error("(読む)", "E_IO", stdin=io.StringIO(""))

    def test_io_failure_is_a_source_diagnostic(self):
        class BrokenOutput(io.StringIO):
            def write(self, text):
                raise OSError("output unavailable")
        error = self.error("(「猫」 を 表示する)", "E_IO", stdout=BrokenOutput())
        self.assertIn("output unavailable", error.message)

    def test_division_by_zero_and_canonical_evaluation_order(self):
        # The から argument is evaluated first, even when authored second.
        source = "((1 を 0 で 割る) を (2 を 0 で 割る) から 引く)"
        error = self.error(source, "E_ZERO_DIVISION")
        self.assertEqual(error.span.start, source.rfind("割る"))
        reversed_source = "((2 を 0 で 割る) から (1 を 0 で 割る) を 引く)"
        self.assertEqual(self.error(reversed_source, "E_ZERO_DIVISION").span.start, reversed_source.find("割る"))

    def test_strings_are_not_tokenized_or_normalized(self):
        text = "は、が、を、から；(猫)。か\u3099"
        self.assertEqual(run(f"「{text}」"), [text])

    def test_string_escapes_and_multiline_string(self):
        self.assertEqual(run(r"「猫\」\n\t\\犬」"), ["猫」\n\t\\犬"])
        self.assertEqual(run("「一\n二」"), ["一\n二"])

    def test_invalid_and_unclosed_strings(self):
        for source, code in [("「猫", "E_STRING"), ("「猫\\", "E_STRING"), (r"「\q」", "E_ESCAPE"), ("」", "E_STRING")]:
            with self.subTest(source=source):
                self.error(source, code)

    def test_names_containing_particles_are_not_split(self):
        tokens = tokenize(Source("たから を 文字列にする"))
        self.assertEqual([(t.kind, t.value) for t in tokens[:-1]],
                         [("NAME", "たから"), ("PARTICLE", "を"), ("NAME", "文字列にする")])

    def test_nfc_names_resolve_but_spans_preserve_original_offsets(self):
        function = replace(BUILTINS["何もしない"], name="がく")
        text = "(か\u3099く)"
        program = compile_source(text, functions={function.name: function})
        self.assertEqual(execute(program), [None])
        self.assertEqual(program.expressions[0].head_span.end, 4)
        self.assertEqual(program.expressions[0].head_span.source.text, text)

    def test_unknown_name_and_noninvoked_function(self):
        self.error("たから", "E_NAME")
        self.assertIn("parentheses", self.error("読む", "E_NAME").message)
        self.error("(ありません)", "E_FUNCTION")

    def test_fullwidth_space_and_line_comments(self):
        self.assertEqual(run("; ignored ( は\n(5　から\n 3　を　引く)。 ; result\n"), [2])

    def test_unsupported_fullwidth_syntax(self):
        for source in ["１２", "（5 から 3 を 引く）", "－5", "3.14"]:
            with self.subTest(source=source):
                self.error(source, "E_TOKEN")

    def test_missing_word_boundaries(self):
        self.error("(5から 3 を 引く)", "E_TOKEN")
        self.error("(「猫」を 表示する)", "E_SPACE")
        self.error("((5 から 3 を 引く)に 4 を 足す)", "E_SPACE")

    def test_unbalanced_or_malformed_calls(self):
        for source, code in [("(5 から 3 を 引く", "E_PAREN"), ("(5 から", "E_PAREN"),
                             ("()", "E_HEAD"), ("(5 から)", "E_HEAD"), ("(5 3 引く)", "E_PARTICLE"),
                             (")", "E_SYNTAX"), ("。", "E_SYNTAX")]:
            with self.subTest(source=source):
                self.error(source, code)

    def test_source_location_and_japanese_caret_width(self):
        error = self.error("; line one\n(「猫」 から 3 を 引く)", "E_TYPE", filename="例.ten")
        self.assertEqual((error.span.line, error.span.column), (2, 2))
        self.assertIn("例.ten:2:2: E_TYPE", error.render())
        self.assertEqual(error.render().splitlines()[-1], "   ^^^^^^")

    def test_empty_program(self):
        self.assertEqual(run(" ; just a comment\n"), [])

    def test_diagnostic_tabs_account_for_wide_characters(self):
        error = self.error("(「猫」\tから 3 を 引く)", "E_TYPE")
        self.assertEqual(error.render().splitlines()[1], "  (「猫」 から 3 を 引く)")
        self.assertEqual(error.render().splitlines()[2], "   ^^^^^^")

    def test_nesting_limit_is_a_diagnostic(self):
        def nested(depth):
            return "(" * depth + "0" + " に 1 を 足す)" * depth
        self.assertEqual(run(nested(MAX_NESTING)), [MAX_NESTING])
        self.error(nested(MAX_NESTING + 1), "E_DEPTH")

    def test_large_integers_and_literal_limit(self):
        digits = "9" * 4096
        self.assertEqual(format_value(run(digits)[0]), digits)
        self.assertEqual(run("-0005 0000 -0"), [-5, 0, 0])
        self.error("1" * 4097, "E_INTEGER")

    def test_example_programs(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        paths = sorted(examples.glob("*.ten"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(example=path.name):
                output = io.StringIO()
                input_path = path.with_suffix(".in")
                source = io.StringIO(input_path.read_text() if input_path.exists() else "")
                run(path.read_text(), filename=str(path), stdin=source, stdout=output)
                self.assertEqual(output.getvalue(), path.with_suffix(".out").read_text())


if __name__ == "__main__":
    unittest.main()

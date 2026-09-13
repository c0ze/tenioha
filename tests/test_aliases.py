import io
from itertools import permutations, product
from pathlib import Path
import tempfile
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import BUILTINS, Builtin, Effect, Parameter, ValueType
from tenioha.syntax import PARTICLES


DIFFERENCE = "関数 差 (元:整数)から|で (量:整数)を|に -> 整数 { (元 から 量 を 引く) }"


class AliasTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_alternate_particles_and_all_argument_permutations(self):
        for source, amount in product(("から", "で"), ("を", "に")):
            for args in permutations((f"9{source}", f"2{amount}")):
                with self.subTest(args=args):
                    self.assertEqual(run(DIFFERENCE + f"({' '.join(args)} 差)"), [7])

    def test_aliases_are_local_to_the_signature(self):
        self.error(DIFFERENCE + "(9で 2に 引く)", "E_ARGUMENTS")

    def test_every_particle_can_be_a_choice(self):
        choices = " | ".join(sorted(PARTICLES))
        declaration = f"関数 複写 (値:整数){choices} -> 整数 {{ 値 }}"
        for particle in sorted(PARTICLES):
            with self.subTest(particle=particle):
                self.assertEqual(run(declaration + f"(7{particle} 複写) (8{particle} 適用 参照 複写)"), [7, 8])

    def test_host_builtins_support_choices_and_name_aliases(self):
        function = Builtin("差", (Parameter("元", "で", ValueType.INTEGER, aliases=("から",)),
                                  Parameter("量", "を", ValueType.INTEGER, aliases=("に",))),
                           ValueType.INTEGER, Effect.PURE, lambda args, ctx: args[0] - args[1])
        source = "別名 差です は 差。(2に 9から 差です)(2を 9で 適用 参照 差です)"
        self.assertEqual(execute(compile_source(source, functions={function.name: function})), [7, 7])

    def test_supplying_two_labels_for_one_slot_is_duplicate(self):
        for call in ["(9から 8で 2を 差)", "(9で 8から 2に 差)"]:
            with self.subTest(call=call):
                error = self.error(DIFFERENCE + call, "E_ARGUMENTS")
                self.assertIn("duplicate:", error.message)
                self.assertNotIn("missing:", error.message)

    def test_missing_and_wrong_alias_arguments(self):
        error = self.error(DIFFERENCE + "(2に 差)", "E_ARGUMENTS")
        self.assertIn("missing: から", error.message)
        error = self.error(DIFFERENCE + "(「九」で 2を 差)", "E_TYPE")
        self.assertIn("で expects 整数", error.message)

    def test_repeated_choices_and_overlapping_parameters_are_rejected(self):
        for signature in ["(元:整数)に|に", "(元:整数)に|へ (量:文字列)へ",
                          "(元:整数)に (量:整数)を|に"]:
            with self.subTest(signature=signature):
                self.error(f"関数 悪い {signature} -> 整数 {{ 1 }}", "E_PARAMETER")

    def test_choice_syntax_is_for_signatures_not_call_arguments(self):
        self.error(DIFFERENCE + "(9から|で 2を 差)", "E_SYNTAX")
        for signature in ["(元:整数)に|は", "(元:整数)に||へ", "(元:整数)に|"]:
            with self.subTest(signature=signature):
                self.error(f"関数 悪い {signature} -> 整数 {{ 1 }}", "E_SYNTAX")

    def test_particle_spans_keep_original_nfc_spelling(self):
        source = "関数 悪い (元:整数)と|か\u3099 (量:整数)が -> 整数 { 1 }"
        error = self.error(source, "E_PARAMETER")
        self.assertEqual(source[error.span.start:error.span.end], "が")
        self.assertEqual(run("関数 値 (元:整数)と|か\u3099 -> 整数 { 元 } (7か\u3099 値)"), [7])

    def test_indirect_calls_retain_choices(self):
        self.assertEqual(run(DIFFERENCE + "操作 は 参照 差。(2に 9で 適用 操作)"), [None, 7])
        self.error(DIFFERENCE + "(9から 8で 2を 適用 参照 差)", "E_ARGUMENTS")

    def test_function_type_compares_choice_sets_not_choice_order(self):
        self.assertEqual(run("""
            関数 増加 (元:整数)へ|に -> 整数 { (元 に 1 を 足す) }
            関数 使用 (操作:関数[整数 に|へ -> 整数])で -> 整数 { (4へ 適用 操作) }
            (参照 増加 で 使用)
        """), [5])

    def test_function_type_choice_contract_is_exact(self):
        for actual, expected in [("に|へ", "に"), ("に", "に|へ")]:
            with self.subTest(actual=actual, expected=expected):
                self.error(f"""
                    関数 値 (元:整数){actual} -> 整数 {{ 元 }}
                    関数 使用 (操作:関数[整数 {expected} -> 整数])で -> 整数 {{ 1 }}
                    (参照 値 で 使用)
                """, "E_TYPE")

    def test_function_parameter_order_is_still_part_of_type(self):
        self.error(DIFFERENCE + """
            関数 使用 (操作:関数[整数 を|に, 整数 で|から -> 整数])で -> 整数 { 1 }
            (参照 差 で 使用)
        """, "E_TYPE")

    def test_bad_function_type_choices_are_rejected(self):
        for parameters in ["整数 に|に", "整数 に|へ, 文字列 へ", "整数 を, 整数 に|を"]:
            with self.subTest(parameters=parameters):
                self.error(f"関数 悪い (操作:関数[{parameters} -> 整数])で -> 整数 {{ 1 }}", "E_PARAMETER")

    def test_generic_function_types_preserve_choices_during_substitution(self):
        self.assertEqual(run("""
            関数 使用<T> (値:T)を (操作:関数[T に|へ -> T])で -> T { (値 へ 適用 操作) }
            関数 複写<T> (値:T)へ|に -> T { 値 }
            (「猫」を 参照 複写<文字列> で 使用<文字列>)
        """), ["猫"])

    def test_closure_parameter_choices_and_captures(self):
        self.assertEqual(run("""
            関数 工場 (増分:整数)で -> 関数[整数 に|へ -> 整数] {
                関数 (値:整数)へ|に -> 整数 { (値 に 増分 を 足す) }
            }
            操作 は (5で 工場)。
            (2へ 適用 操作) (3に 適用 操作)
        """), [None, 7, 8])

    def test_aliases_do_not_change_canonical_exception_order(self):
        for head in ["差", "差です", "適用 参照 差です"]:
            source = DIFFERENCE + "別名 差です は 差。" + f"((1を 0で 割る)に (2を 0で 割る)で {head})"
            with self.subTest(head=head):
                self.assertEqual(self.error(source, "E_ZERO_DIVISION").span.start, source.rfind("割る"))

    def test_builtin_alternate_spelling(self):
        self.assertEqual(run("別名 足します は 足す。(2に 3を 足します)"), [5])
        value, = run("別名 足します は 足す。参照 足します")
        self.assertEqual(value.signature.key, BUILTINS["足す"].key)
        self.assertEqual(value.signature.value_type, BUILTINS["足す"].value_type)

    def test_aliases_can_precede_targets_and_calls(self):
        self.assertEqual(run("(9で 2に 差です) 別名 差です は 別の差。別名 別の差 は 差。" + DIFFERENCE), [7])

    def test_generic_name_alias_is_not_a_specialization(self):
        declaration = "関数 複写<T> (値:T)を|と -> T { 値 } 別名 複写します は 複写。"
        self.assertEqual(run(declaration + "(7と 複写します<整数>) (「猫」を 適用 参照 複写します<文字列>)"), [7, "猫"])
        self.error(declaration + "(7を 複写します)", "E_TYPE_ARGUMENTS")
        self.error("関数 複写<T> (値:T)を -> T { 値 } 別名 整数用 は 複写<整数>", "E_ALIAS")

    def test_alias_declaration_does_not_execute_or_create_a_body(self):
        program = compile_source("別名 読みます は 読む。別名 一です は 一。関数 一 -> 整数 { 1 }")
        self.assertEqual(execute(program, stdin=io.StringIO("")), [])
        self.assertEqual(len(program.definitions), 1)

    def test_procedure_alias_effects_and_input(self):
        declaration = "別名 読みます は 読む。"
        self.assertEqual(run(declaration + "(読みます)", stdin=io.StringIO("猫\n")), ["猫"])
        self.error(declaration + "((読みます)を 表示する)", "E_EFFECT")
        self.error(declaration + "(適用 参照 読みます)", "E_EFFECT", allow_io=False)
        self.assertEqual(len(run(declaration + "参照 読みます", allow_io=False)), 1)

    def test_procedure_choices_do_not_make_a_pure_reference(self):
        self.error("""
            手続き 受ける (値:文字列)を|と -> 単位 { (値 を 表示する) }
            別名 受けます は 受ける。
            関数 使用 (操作:関数[文字列 を|と -> 単位])で -> 単位 {}
            (参照 受けます で 使用)
        """, "E_TYPE")

    def test_alias_cycles_missing_targets_and_collisions(self):
        cases = [("別名 自分 は 自分", "E_ALIAS_CYCLE"),
                 ("別名 甲 は 乙。別名 乙 は 甲", "E_ALIAS_CYCLE"),
                 ("別名 新名 は 不明", "E_ALIAS"),
                 ("別名 足す は 引く", "E_DUPLICATE_FUNCTION"),
                 ("別名 新名 は 足す。別名 新名 は 引く", "E_DUPLICATE_FUNCTION"),
                 ("別名 新名 は 足す。関数 新名 -> 整数 { 1 }", "E_DUPLICATE_FUNCTION")]
        for source, code in cases:
            with self.subTest(source=source):
                self.error(source, code)

    def test_name_alias_normalization(self):
        self.assertEqual(run("別名 か\u3099く は 何もしない。(がく)"), [None])
        self.error("別名 がく は 足す。別名 か\u3099く は 引く", "E_DUPLICATE_FUNCTION")

    def test_aliases_do_not_resolve_value_bindings_or_types(self):
        self.error("値 は 関数 -> 整数 { 1 }。別名 新名 は 値", "E_ALIAS")
        self.error("型 箱 { 空 } 別名 新名 は 箱", "E_ALIAS")

    def test_name_aliases_are_file_scoped(self):
        for source in ["{ 別名 新名 は 足す }", "関数 甲 -> 整数 { 別名 新名 は 足す。1 }",
                       "もし 真 なら { 別名 新名 は 足す } そうでなければ {}"]:
            with self.subTest(source=source):
                self.error(source, "E_DEFINITION")

    def test_direct_and_indirect_missing_roles_list_the_same_choices(self):
        declaration = "関数 受ける (値:整数)へ|に -> 整数 { 値 }"
        for head in ["受ける", "適用 参照 受ける"]:
            with self.subTest(head=head):
                error = self.error(declaration + f"({head})", "E_ARGUMENTS")
                self.assertEqual(error.message.split(": ", 1)[1], "missing: に|へ.")

    def test_long_alias_chains_use_no_python_recursion(self):
        source = "\n".join(f"別名 名前{i} は 名前{i+1}。" for i in range(1500))
        source += "別名 名前1500 は 何もしない。(名前0)"
        self.assertEqual(run(source), [None])

    def test_constructor_names_and_particle_aliases_preserve_matching(self):
        self.assertEqual(run("""
            型 箱<T> { 包む (値:T)を|に }
            別名 包みます は 包む。
            値 は (7に 包みます<整数>)。
            場合 値 { (中 を 包む) なら { 中 } }
            場合 値 { (中 に 包みます) なら { 中 } }
        """), [None, 7, 7])

    def test_nested_patterns_use_aliases_at_each_level(self):
        self.assertEqual(run("""
            型 箱<T> { 包む (値:T)を|に }
            別名 包みます は 包む。
            場合 ((7に 包みます<整数>)を 包む<箱<整数>>) {
                ((中 を 包む)に 包みます) なら { 中 }
            }
        """), [7])

    def test_alias_pattern_is_not_an_additional_constructor(self):
        self.error("""
            型 箱 { 包む (値:整数)を|に }
            別名 包みます は 包む。
            場合 (7に 包む) {
                (中 を 包む) なら { 中 }
                (中 に 包みます) なら { 中 }
            }
        """, "E_PATTERN")

    def test_constructor_alias_reference_retains_particle_contract(self):
        self.assertEqual(run("""
            型 箱<T> { 包む (値:T)を|に }
            別名 包みます は 包む。
            関数 作成<T> (値:T)から (操作:関数[T に|を -> 箱<T>])で -> 箱<T> { (値 に 適用 操作) }
            場合 (7から 参照 包みます<整数> で 作成<整数>) { (中 を 包む) なら { 中 } }
        """), [7])

    def test_duplicate_particle_choices_in_a_pattern(self):
        self.error("型 箱 { 包む (値:整数)を|に } 場合 (7に 包む) { (中 を 別 に 包む) なら { 中 } }", "E_ARGUMENTS")

    def test_alias_constructor_cannot_cross_nominal_types(self):
        self.error("型 甲 { 一 } 型 乙 { 二 } 別名 別 は 二。場合 (一) { (別) なら { 0 } }", "E_PATTERN")

    def test_bad_aliases_and_signatures_fail_before_program_io(self):
        for bad in ["別名 新名 は 不明", "別名 甲 は 乙。別名 乙 は 甲",
                    "関数 悪い (値:整数)に|に -> 整数 { 1 }"]:
            with self.subTest(bad=bad):
                source, output = io.StringIO("unused\n"), io.StringIO()
                with self.assertRaises(Diagnostic):
                    run("(「early」を 表示する) (読む) " + bad, stdin=source, stdout=output)
                self.assertEqual((source.tell(), output.getvalue()), (0, ""))


class AliasModuleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.entry = self.directory / "main.ten"

    def write(self, name, source):
        (self.directory / name).write_text(source, encoding="utf-8")

    def evaluate(self, text, **options):
        return run(text, filename=str(self.entry), **options)

    def test_imported_aliases_and_explicit_reexports(self):
        self.write("base.ten", DIFFERENCE + "別名 差です は 差。")
        self.write("adapter.ten", "取込 「base.ten」 と 元。別名 減らす は 元.差です。")
        self.assertEqual(self.evaluate("""
            取込 「adapter.ten」 と 外。
            別名 減らします は 外.減らす。
            (9で 2に 減らします) (9から 2を 適用 参照 外.減らす)
        """), [7, 7])

    def test_alias_uses_the_targets_own_module_definitions(self):
        self.write("base.ten", "関数 内 -> 整数 { 7 } 関数 呼ぶ -> 整数 { (内) }")
        self.assertEqual(self.evaluate("取込 「base.ten」 と 元。関数 内 -> 整数 { 99 } 別名 呼びます は 元.呼ぶ。(呼びます)"), [7])

    def test_exported_constructor_alias_preserves_nominal_identity(self):
        self.write("base.ten", "型 箱<T> { 包む (値:T)を|に }")
        self.write("adapter.ten", "取込 「base.ten」 と 元。別名 包みます は 元.包む。")
        self.assertEqual(self.evaluate("""
            取込 「base.ten」 と 元。取込 「adapter.ten」 と 外。
            関数 使用 (値:元.箱<整数>)を -> 整数 { 場合 値 { (中 に 外.包みます) なら { 中 } } }
            ((7を 外.包みます<整数>)を 使用)
        """), [7])

    def test_imported_aliases_are_not_implicit_reexports(self):
        self.write("base.ten", "別名 一 は 何もしない")
        self.write("adapter.ten", "取込 「base.ten」 と 元")
        with self.assertRaises(Diagnostic) as caught:
            self.evaluate("取込 「adapter.ten」 と 外。(外.一)")
        self.assertEqual(caught.exception.code, "E_FUNCTION")

    def test_imported_bad_alias_is_checked_before_io(self):
        self.write("bad.ten", "別名 甲 は 乙。別名 乙 は 甲")
        output = io.StringIO()
        with self.assertRaises(Diagnostic) as caught:
            self.evaluate("(「early」を 表示する) 取込 「bad.ten」 と 悪い", stdout=output)
        self.assertEqual(caught.exception.code, "E_ALIAS_CYCLE")
        self.assertEqual(caught.exception.span.source.name, str(self.directory / "bad.ten"))
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

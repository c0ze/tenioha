import io
from itertools import permutations
import math
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import MAX_CALL_DEPTH


FACTORIAL = """
関数 階乗 (数: 整数) を -> 整数 {
    もし (数 と 0 が 等しい) なら {
        1
    } そうでなければ {
        (数 に ((数 から 1 を 引く) を 階乗) を 掛ける)
    }
}
"""


class FunctionTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_source_functions_preserve_noncommutative_particle_order(self):
        declaration = "関数 差 (元: 整数) から (量: 整数) を -> 整数 { (元 から 量 を 引く) }"
        self.assertEqual(run(declaration + "(10 から 3 を 差) (3 を 10 から 差) (3 から 10 を 差)"), [7, 7, -7])

    def test_four_source_parameter_permutations(self):
        declaration = """関数 桁 (千: 整数) から (百: 整数) を (十: 整数) に (一: 整数) で -> 整数 {
            上 は ((千 に 1000 を 掛ける) に (百 に 100 を 掛ける) を 足す)。
            下 は ((十 に 10 を 掛ける) に 一 を 足す)。
            (上 に 下 を 足す)
        }"""
        for args in permutations(["1 から", "2 を", "3 に", "4 で"]):
            with self.subTest(args=args):
                self.assertEqual(run(declaration + f"({' '.join(args)} 桁)"), [1234])

    def test_all_primitive_types_in_source_signatures(self):
        self.assertEqual(run("""
            関数 文 (値: 文字列) を -> 文字列 { 値 }
            関数 判定 (値: 真偽値) を -> 真偽値 { 値 }
            関数 空 (値: 単位) を -> 単位 { 値 }
            (「猫」 を 文) (真 を 判定) ((何もしない) を 空)
        """), ["猫", True, None])

    def test_function_argument_types_are_checked(self):
        self.error("関数 文 (値: 文字列) を -> 文字列 { 値 } (1 を 文)", "E_TYPE")

    def test_recursion_and_independent_frames(self):
        self.assertEqual(run(FACTORIAL + "(0 を 階乗) (6 を 階乗) (4 を 階乗)"), [1, 720, 24])

    def test_deep_recursion_does_not_use_python_call_stack(self):
        self.assertEqual(run(FACTORIAL + "(1000 を 階乗)"), [math.factorial(1000)])

    def test_unbounded_recursion_reports_language_limit(self):
        error = self.error("関数 再帰 -> 整数 { (再帰) } (再帰)", "E_CALL_DEPTH")
        self.assertIn(str(MAX_CALL_DEPTH), error.message)
        self.assertIn("再帰", error.render())

    def test_forward_and_mutually_recursive_calls(self):
        self.assertEqual(run("""
            (1000 を 偶数) (13 を 偶数) (13 を 奇数)
            関数 偶数 (数: 整数) を -> 真偽値 {
                もし (数 と 0 が 等しい) なら { 真 }
                そうでなければ { ((数 から 1 を 引く) を 奇数) }
            }
            関数 奇数 (数: 整数) を -> 真偽値 {
                もし (数 と 0 が 等しい) なら { 偽 }
                そうでなければ { ((数 から 1 を 引く) を 偶数) }
            }
        """), [True, False, True])

    def test_conditionals_evaluate_only_selected_branch(self):
        self.assertEqual(run("""
            もし 真 なら { 8 } そうでなければ { (1 を 0 で 割る) }
            もし 偽 なら { (1 を 0 で 割る) } そうでなければ { 9 }
        """), [8, 9])

    def test_conditionals_can_supply_pure_arguments(self):
        self.assertEqual(run("(もし 真 なら { 5 } そうでなければ { 8 } から 3 を 引く)"), [2])

    def test_unselected_branch_still_typechecks(self):
        self.error("もし 真 なら { 1 } そうでなければ { (真 から 3 を 引く) }", "E_TYPE")
        self.error("もし 真 なら { 1 } そうでなければ { 不明 }", "E_NAME")

    def test_condition_and_branch_types(self):
        self.error("もし 1 なら { 2 } そうでなければ { 3 }", "E_CONDITION")
        self.error("もし 真 なら { 1 } そうでなければ { 「猫」 }", "E_BRANCH_TYPE")

    def test_selected_io_branch_only(self):
        output = io.StringIO()
        self.assertEqual(run("もし 偽 なら { (「wrong」 を 表示する) } そうでなければ { (「right」 を 表示する) }", stdout=output), [None])
        self.assertEqual(output.getvalue(), "right\n")

    def test_condition_must_be_pure(self):
        self.error("""
            手続き 判定 -> 真偽値 { 真 }
            もし (判定) なら { 1 } そうでなければ { 2 }
        """, "E_EFFECT")

    def test_top_level_bindings_and_block_results(self):
        self.assertEqual(run("元 は 5。量 は 3。(元 から 量 を 引く) {} { 内 は 1 }"),
                         [None, None, 2, None, None])

    def test_nested_shadowing_initializes_from_outer_value(self):
        self.assertEqual(run("値 は 1。{ 値 は (値 に 1 を 足す)。値 } 値"), [None, 2, 1])

    def test_block_and_branch_bindings_do_not_escape(self):
        for source in ["{ 内 は 1 } 内", "もし 真 なら { 内 は 1 } そうでなければ {} 内"]:
            with self.subTest(source=source):
                self.error(source, "E_NAME")

    def test_binding_is_not_visible_in_its_own_initializer(self):
        self.error("値 は (値 に 1 を 足す)", "E_NAME")
        self.error("{ 値 } 値 は 1", "E_NAME")

    def test_rebinding_same_scope_is_an_error(self):
        self.error("値 は 1。値 は 2", "E_BINDING")
        self.error("関数 増加 (値: 整数) を -> 整数 { 値 は 3。値 }", "E_BINDING")

    def test_parameter_can_be_shadowed_in_nested_block(self):
        self.assertEqual(run("""
            関数 増加 (値: 整数) を -> 整数 { { 値 は (値 に 1 を 足す)。値 } }
            (4 を 増加)
        """), [5])

    def test_value_and_function_names_are_separate(self):
        self.assertEqual(run("引く は 7。(引く から 3 を 引く)"), [None, 4])

    def test_functions_do_not_capture_top_level_or_caller_values(self):
        for source in ["値 は 7。関数 取得 -> 整数 { 値 } (取得)",
                       "関数 取得 -> 整数 { 値 } 関数 呼出 (値: 整数) を -> 整数 { (取得) }"]:
            with self.subTest(source=source):
                self.error(source, "E_NAME")

    def test_procedure_reads_binds_then_prints_in_order(self):
        source, output = io.StringIO("Ada\nLinus\n"), io.StringIO()
        values = run("""
            手続き 挨拶 -> 単位 {
                名前 は (読む)。
                文 は (「こんにちは、」 と 名前 を 連結する)。
                (文 を 表示する)
            }
            (挨拶) (挨拶)
        """, stdin=source, stdout=output)
        self.assertEqual(values, [None, None])
        self.assertEqual(output.getvalue(), "こんにちは、Ada\nこんにちは、Linus\n")
        self.assertEqual(source.read(), "")

    def test_procedure_can_return_a_bound_value(self):
        source, output = io.StringIO("Ada\n"), io.StringIO()
        self.assertEqual(run("""
            手続き 入力 -> 文字列 { (読む) }
            名前 は (入力)。
            (名前 を 表示する)
            名前
        """, stdin=source, stdout=output), [None, None, "Ada"])
        self.assertEqual(output.getvalue(), "Ada\n")

    def test_pure_function_cannot_call_io_directly_or_transitively(self):
        for source in ["関数 悪い -> 文字列 { (読む) }",
                       "手続き 入力 -> 文字列 { (読む) } 関数 悪い -> 文字列 { (入力) }"]:
            with self.subTest(source=source):
                self.error(source, "E_EFFECT")

    def test_procedure_annotation_is_effectful_even_with_pure_body(self):
        self.error("手続き 一 -> 整数 { 1 } ((一) に 2 を 足す)", "E_EFFECT")

    def test_io_in_argument_block_is_rejected_before_input(self):
        source = io.StringIO("unused\n")
        self.error("({ 名前 は (読む)。名前 } を 表示する)", "E_EFFECT", stdin=source)
        self.assertEqual(source.tell(), 0)

    def test_pure_mode_permits_procedure_definitions_but_not_execution(self):
        definition = "手続き 入力 -> 文字列 { (読む) }"
        self.assertEqual(run(definition, allow_io=False), [])
        self.error(definition + "(入力)", "E_EFFECT", allow_io=False)
        self.error("名前 は (読む)", "E_EFFECT", allow_io=False)

    def test_entire_file_and_all_bodies_checked_before_io(self):
        bad_bodies = ["関数 未使用 -> 整数 { 「bad return」 }",
                      "関数 未使用 -> 文字列 { (読む) }",
                      "関数 未使用 -> 整数 { 不明 }",
                      "関数 未使用 -> 整数 {}",
                      "値 は 1。値 は 2"]
        for bad in bad_bodies:
            with self.subTest(bad=bad):
                source, output = io.StringIO("unused\n"), io.StringIO()
                with self.assertRaises(Diagnostic):
                    run("(「too early」 を 表示する) 名前 は (読む)。" + bad, stdin=source, stdout=output)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(source.tell(), 0)

    def test_return_type_and_last_binding_unit(self):
        self.error("関数 悪い -> 整数 { 「猫」 }", "E_RETURN")
        self.error("関数 悪い -> 整数 { 値 は 1 }", "E_RETURN")
        self.assertEqual(run("関数 空 -> 単位 {} (空)"), [None])

    def test_duplicate_function_and_builtin_names(self):
        self.error("関数 同名 -> 整数 { 1 } 関数 同名 -> 整数 { 2 }", "E_DUPLICATE_FUNCTION")
        self.error("関数 引く -> 整数 { 1 }", "E_DUPLICATE_FUNCTION")

    def test_duplicate_source_parameters_and_unknown_types(self):
        cases = [
            ("関数 差 (元: 整数) を (量: 文字列) を -> 整数 { 1 }", "E_PARAMETER"),
            ("関数 差 (元: 整数) から (元: 整数) を -> 整数 { 1 }", "E_PARAMETER"),
            ("関数 差 (元: 実数) を -> 整数 { 1 }", "E_TYPE_NAME"),
            ("関数 差 -> 実数 { 1 }", "E_TYPE_NAME"),
        ]
        for source, code in cases:
            with self.subTest(source=source):
                self.error(source, code)

    def test_nfc_source_bindings_and_declarations(self):
        self.assertEqual(run("か\u3099く は 1。がく"), [None, 1])
        self.assertEqual(run("関数 か\u3099く (か\u3099た: 整数) を -> 整数 { がた } (5 を がく)"), [5])
        self.error("か\u3099く は 1。がく は 2", "E_BINDING")
        self.error("関数 がく -> 整数 { 1 } 関数 か\u3099く -> 整数 { 2 }", "E_DUPLICATE_FUNCTION")

    def test_normalization_does_not_allow_binding_a_particle_name(self):
        self.error("か\u3099 は 1", "E_SYNTAX")

    def test_nfc_parameter_collision(self):
        self.error("関数 差 (がく: 整数) から (か\u3099く: 整数) を -> 整数 { 1 }", "E_PARAMETER")

    def test_nested_declarations_are_not_supported(self):
        self.error("{ 関数 内 -> 整数 { 1 } }", "E_DEFINITION")

    def test_malformed_new_syntax_has_diagnostics(self):
        for source, code in [
            ("{", "E_BLOCK"), ("関数 名 -> 整数 { 1", "E_BLOCK"),
            ("もし 真 なら { 1 }", "E_SYNTAX"),
            ("もし 真 { 1 } そうでなければ { 2 }", "E_SYNTAX"),
            ("関数 名 (数 整数) を -> 整数 { 数 }", "E_SYNTAX"),
            ("関数 名 (数: 整数)を -> 整数 { 数 }", "E_SPACE"),
            ("関数 名 (数: 整数) は -> 整数 { 数 }", "E_SYNTAX"),
            ("関数 名 -> 整数 1", "E_SYNTAX"), ("値 は", "E_SYNTAX"),
        ]:
            with self.subTest(source=source):
                self.error(source, code)

    def test_reexecuting_a_compiled_program_uses_fresh_bindings(self):
        program = compile_source("値 は 1。{ 値 は 2。値 } 値")
        self.assertEqual(execute(program), [None, 2, 1])
        self.assertEqual(execute(program), [None, 2, 1])


if __name__ == "__main__":
    unittest.main()

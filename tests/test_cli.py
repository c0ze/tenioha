import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def cli(self, *args, input="", env=None):
        return subprocess.run([sys.executable, "-m", "tenioha", *args], cwd=ROOT,
                              input=input, capture_output=True, text=True, timeout=10, env=env)

    def test_eval(self):
        result = self.cli("--eval", "(3 を 5 から 引く)")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "2\n", ""))

    def test_output_does_not_print_unit(self):
        result = self.cli("--eval", "(「こんにちは」 を 表示する)")
        self.assertEqual((result.returncode, result.stdout), (0, "こんにちは\n"))

    def test_check_never_reads_or_prints_program_output(self):
        result = self.cli("--check", "--eval", "(読む) (「should not print」 を 表示する)")
        self.assertEqual((result.returncode, result.stdout), (0, "OK: 2 statement(s), 0 definition(s) checked.\n"))

    def test_error_exit_and_diagnostic(self):
        result = self.cli("--eval", "(3 に 5 に 足す)")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("<eval>:1:8: E_ARGUMENTS", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_pure_flag(self):
        result = self.cli("--pure", "--eval", "(読む)")
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_EFFECT", result.stderr)

    def test_read_and_eof(self):
        result = self.cli("--eval", "(読む)", input="猫\n")
        self.assertEqual((result.returncode, result.stdout), (0, "猫\n"))
        result = self.cli("--eval", "(読む)")
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_IO", result.stderr)

    def test_example_file(self):
        result = self.cli("examples/arithmetic.ten")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, (ROOT / "examples/arithmetic.out").read_text())

    def test_file_read_errors(self):
        result = self.cli("examples/missing-file.ten")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.ten"
            path.write_bytes(b"\xff")
            result = self.cli(str(path))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_utf8_bom_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.ten"
            path.write_text("(「猫」 を 表示する)", encoding="utf-8-sig")
            result = self.cli(str(path))
            self.assertEqual((result.returncode, result.stdout), (0, "猫\n"))

    def test_usage_errors_and_version(self):
        for args in [(), ("examples/arithmetic.ten", "--eval", "1")]:
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)
        self.assertEqual(self.cli("--version").stdout, "Tenioha 0.7.0\n")

    def test_algebraic_values_function_values_and_check_counts(self):
        result = self.cli("--eval", "型 箱<T> { 包む (値: T) を } (7 を 包む<整数>) 参照 引く")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "(7 を 包む)\n参照 引く\n", ""))
        result = self.cli("--check", "examples/lists.ten")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "OK: 6 statement(s), 4 definition(s), 1 type(s) checked.\n", ""))

    def test_closure_values_do_not_execute_their_bodies(self):
        source = "手続き -> 文字列 { (読む) }"
        result = self.cli("--pure", "--eval", source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "手続き {…}\n", ""))
        result = self.cli("--check", "--eval", source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "OK: 1 statement(s), 0 definition(s) checked.\n", ""))

    def test_closure_examples(self):
        for name in ["closures", "closure_greeting"]:
            with self.subTest(name=name):
                path = ROOT / "examples" / f"{name}.ten"
                fixture = path.with_suffix(".in")
                result = self.cli(str(path), input=fixture.read_text() if fixture.exists() else "")
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, path.with_suffix(".out").read_text(), ""))
                check = self.cli("--check", str(path))
                self.assertEqual(check.returncode, 0, check.stderr)

    def test_closure_error_has_original_source_location(self):
        result = self.cli("--eval", "元 は 0。\n操作 は 関数 -> 整数 { (1 を 元 で 割る) }。\n(適用 操作)")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("<eval>:2:", result.stderr)
        self.assertIn("E_ZERO_DIVISION", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_nested_pattern_example(self):
        path = ROOT / "examples" / "nested_patterns.ten"
        result = self.cli(str(path))
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, path.with_suffix(".out").read_text(), ""))
        check = self.cli("--check", str(path))
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_compact_example_and_pure_eval(self):
        path = ROOT / "examples" / "compact.ten"
        result = self.cli(str(path))
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, path.with_suffix(".out").read_text(), ""))
        check = self.cli("--check", str(path))
        self.assertEqual(check.returncode, 0, check.stderr)
        result = self.cli("--pure", "--eval", "(5から 3を 引く)")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "2\n", ""))

    def test_compact_error_has_original_span_before_output(self):
        result = self.cli("--eval", '(「early」を 表示する)。\n(3に 5に 足す)')
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("<eval>:2:6: E_ARGUMENTS", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        result = self.cli("--eval", '(「early」を 表示する)(5から3を引く)')
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("E_TOKEN", result.stderr)

    def test_alias_example_and_check_counts(self):
        path = ROOT / "examples" / "aliases.ten"
        result = self.cli(str(path))
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, path.with_suffix(".out").read_text(), ""))
        check = self.cli("--check", str(path))
        self.assertEqual((check.returncode, check.stdout, check.stderr),
                         (0, "OK: 8 statement(s), 1 definition(s), 1 type(s) checked.\n", ""))

    def test_alias_check_does_not_invoke_procedures(self):
        source = '別名 読みます は 読む。別名 表示します は 表示する。(読みます)(「early」を 表示します)'
        result = self.cli("--check", "--eval", source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "OK: 2 statement(s), 0 definition(s) checked.\n", ""))

    def test_alias_errors_have_original_spans_before_output(self):
        sources = [('別名 新名 は 不明', "<eval>:2:9: E_ALIAS"),
                   ('別名 甲 は 乙。別名 乙 は 甲', "<eval>:2:17: E_ALIAS_CYCLE"),
                   ('関数 受ける (値:整数)に|へ -> 整数 { 値 } (1に 2へ 受ける)', "E_ARGUMENTS: 受ける: duplicate: へ")]
        for source, diagnostic in sources:
            with self.subTest(source=source):
                result = self.cli("--eval", '(「early」を 表示する)。\n' + source)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn(diagnostic, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_compact_large_integer_is_independent_of_python_conversion_limit(self):
        digits = "8" * 1000
        result = self.cli("--eval", f"({digits}を 文字列にする)",
                          env={**os.environ, "PYTHONINTMAXSTRDIGITS": "640"})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, digits + "\n", ""))

    def test_missing_nested_case_is_reported_before_output(self):
        source = '''(「early」 を 表示する)
            型 色 { 赤。青 } 型 対 { 組 (左: 色) を (右: 色) に }
            関数 不正 (値: 対) を -> 整数 {
                場合 値 { ((赤) を (赤) に 組) なら { 1 } ((青) を (青) に 組) なら { 2 } }
            }'''
        result = self.cli("--eval", source)
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("E_MATCH_EXHAUSTIVE", result.stderr)
        self.assertIn("((赤) を (青) に 組)", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unreachable_pattern_is_rejected_before_output(self):
        source = '(「early」 を 表示する) 型 色 { 赤。青 } 場合 (赤) { _ なら { 0 } (赤) なら { 1 } }'
        result = self.cli("--eval", source)
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("E_PATTERN: Unreachable", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_recursive_function_file(self):
        result = self.cli("examples/factorial.ten")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "720\n", ""))

    def test_procedure_file_and_check_without_input(self):
        result = self.cli("examples/greeting.ten", input="Ada\n")
        self.assertEqual((result.returncode, result.stdout), (0, "こんにちは、Ada\n"))
        result = self.cli("--check", "examples/greeting.ten")
        self.assertEqual((result.returncode, result.stdout), (0, "OK: 1 statement(s), 1 definition(s) checked.\n"))

    def test_declarations_do_not_print_results(self):
        result = self.cli("--eval", "関数 一 -> 整数 { 1 }")
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_runtime_recursion_error_has_no_python_traceback(self):
        result = self.cli("--eval", "関数 再帰 -> 整数 { (再帰) } (再帰)")
        self.assertEqual(result.returncode, 1)
        self.assertIn("E_CALL_DEPTH", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_python_integer_conversion_setting_does_not_change_language(self):
        digits = "8" * 1000
        result = self.cli("--eval", f"({digits} を 文字列にする)",
                          env={**os.environ, "PYTHONINTMAXSTRDIGITS": "640"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, digits + "\n")


if __name__ == "__main__":
    unittest.main()

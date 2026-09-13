import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import MAX_IMPORT_DEPTH


ROOT = Path(__file__).resolve().parents[1]


class ModuleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.entry = self.directory / 'main.ten'

    def write(self, name, source):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return path

    def evaluate(self, source, **options):
        return run(source, filename=str(self.entry), **options)

    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            self.evaluate(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_aliased_import_and_forward_use(self):
        self.write('math.ten', '関数 差 (元: 整数) から (量: 整数) を -> 整数 { (元 から 量 を 引く) }')
        self.assertEqual(self.evaluate('(3 を 10 から 数.差) 取込 「math.ten」 と 数'), [7])
        self.error('取込 「math.ten」 と 数。(3 を 10 から 差)', 'E_FUNCTION')

    def test_module_relative_paths_and_internal_function_resolution(self):
        self.write('nested/inner.ten', '関数 値 -> 整数 { 5 }')
        self.write('nested/outer.ten', '取込 「inner.ten」 と 内。関数 値 -> 整数 { ((内.値) に 1 を 足す) }')
        self.assertEqual(self.evaluate('取込 「nested/outer.ten」 と 外。関数 値 -> 整数 { 9 } (外.値) (値)'), [6, 9])
        self.error('取込 「nested/outer.ten」 と 外。(外.内.値)', 'E_FUNCTION')

    def test_imported_generic_types_and_constructor_patterns(self):
        self.write('box.ten', '型 箱<T> { 包む (値: T) を }')
        self.assertEqual(self.evaluate('''
        取込 「box.ten」 と 箱群。
        関数 取得 (値: 箱群.箱<整数>) から -> 整数 {
            場合 値 { (数 を 箱群.包む) なら { 数 } }
        }
        ((7 を 箱群.包む<整数>) から 取得)
        '''), [7])

    def test_types_from_different_modules_are_nominal(self):
        text = '型 箱 { 包む (値: 整数) を }'
        self.write('a.ten', text)
        self.write('b.ten', text)
        self.error('''
        取込 「a.ten」 と A。取込 「b.ten」 と B。
        関数 使用 (値: A.箱) を -> A.箱 { 値 }
        ((7 を B.包む) を 使用)
        ''', 'E_TYPE')
        self.error('取込 「a.ten」 と A。取込 「b.ten」 と B。場合 (7 を A.包む) { (値 を B.包む) なら { 値 } }', 'E_PATTERN')

    def test_same_module_aliases_share_type_identity(self):
        self.write('box.ten', '型 箱 { 包む (値: 整数) を }')
        self.assertEqual(self.evaluate('''
        取込 「box.ten」 と A。取込 「./box.ten」 と B。
        関数 使用 (値: A.箱) を -> 整数 { 場合 値 { (数 を B.包む) なら { 数 } } }
        ((7 を B.包む) を 使用)
        '''), [7])
        self.error('取込 「box.ten」 と A。取込 「box.ten」 と B。場合 (7 を A.包む) { (値 を A.包む) なら { 値 } (値 を B.包む) なら { 値 } }', 'E_PATTERN')

    def test_diamond_import_loads_one_definition(self):
        self.write('common.ten', '関数 値 -> 整数 { 7 }')
        self.write('left.ten', '取込 「common.ten」 と 共。関数 左 -> 整数 { (共.値) }')
        self.write('right.ten', '取込 「common.ten」 と 共。関数 右 -> 整数 { (共.値) }')
        program = compile_source('取込 「left.ten」 と L。取込 「right.ten」 と R。(L.左) (R.右)', filename=str(self.entry))
        self.assertEqual(execute(program), [7, 7])
        self.assertEqual(len(program.definitions), 3)

    def test_imported_function_value_uses_its_defining_module(self):
        self.write('a.ten', '関数 値 -> 整数 { 7 } 関数 取得 -> 関数[-> 整数] { 参照 値 }')
        self.assertEqual(self.evaluate('取込 「a.ten」 と A。関数 値 -> 整数 { 9 } 操作 は (A.取得)。(適用 操作)'), [None, 7])

    def test_module_initializers_are_rejected_before_any_program_io(self):
        for statement in ['(「bad」 を 表示する)', '値 は 7', '1', '(読む)']:
            with self.subTest(statement=statement):
                self.write('bad.ten', statement)
                stdin, stdout = io.StringIO('unused\n'), io.StringIO()
                self.error('(「early」 を 表示する) (読む) 取込 「bad.ten」 と 悪い', 'E_MODULE_BODY', stdin=stdin, stdout=stdout)
                self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_uncalled_imported_body_is_checked_before_io(self):
        self.write('bad.ten', '関数 未使用 -> 整数 { 「bad」 }')
        stdout = io.StringIO()
        error = self.error('(「early」 を 表示する) 取込 「bad.ten」 と 悪い', 'E_RETURN', stdout=stdout)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(error.span.source.name, str(self.directory / 'bad.ten'))

    def test_import_cycles_are_diagnostics(self):
        self.write('a.ten', '取込 「b.ten」 と B')
        self.write('b.ten', '取込 「a.ten」 と A')
        self.error('取込 「a.ten」 と A', 'E_IMPORT_CYCLE')
        self.write('main.ten', '取込 「main.ten」 と 自分')
        self.error(self.entry.read_text(), 'E_IMPORT_CYCLE')

    def test_missing_invalid_and_absolute_paths(self):
        self.error('取込 「missing.ten」 と 無し', 'E_IMPORT')
        self.error('取込 「」 と 無し', 'E_IMPORT')
        self.error('取込 「/tmp/tenioha-absolute.ten」 と 無し', 'E_IMPORT')
        self.error('取込 「bad\x00.ten」 と 無し', 'E_IMPORT')
        self.write('invalid.ten', '関数')
        self.error('取込 「invalid.ten」 と 無し', 'E_SYNTAX')
        (self.directory / 'invalid.ten').write_bytes(b'\xff')
        self.error('取込 「invalid.ten」 と 無し', 'E_IMPORT')

    def test_imports_require_a_filename_for_embedding(self):
        with self.assertRaises(Diagnostic) as caught:
            compile_source('取込 「math.ten」 と 数')
        self.assertEqual(caught.exception.code, 'E_IMPORT')

    def test_alias_normalization_and_duplicates(self):
        self.write('a.ten', '関数 がく -> 整数 { 7 }')
        self.assertEqual(self.evaluate('取込 「a.ten」 と か\u3099た。(がた.か\u3099く)'), [7])
        self.error('取込 「a.ten」 と がた。取込 「a.ten」 と か\u3099た', 'E_IMPORT')

    def test_imported_procedures_preserve_pure_context(self):
        self.write('io.ten', '手続き 入力 -> 文字列 { (読む) }')
        self.assertEqual(self.evaluate('取込 「io.ten」 と 入出力', allow_io=False), [])
        self.error('取込 「io.ten」 と 入出力。(入出力.入力)', 'E_EFFECT', allow_io=False)
        self.error('取込 「io.ten」 と 入出力。((適用 参照 入出力.入力) を 表示する)', 'E_EFFECT')

    def test_import_depth_has_language_diagnostic(self):
        for index in range(MAX_IMPORT_DEPTH):
            self.write(f'{index}.ten', f'取込 「{index + 1}.ten」 と 次' if index < MAX_IMPORT_DEPTH - 1 else '')
        self.error('取込 「0.ten」 と 始', 'E_IMPORT_DEPTH')

    def test_utf8_bom_imports(self):
        self.write('bom.ten', '\ufeff関数 一 -> 整数 { 1 }')
        self.assertEqual(self.evaluate('取込 「bom.ten」 と B。(B.一)'), [1])

    def test_cli_imports_and_check_from_another_directory(self):
        self.write('io.ten', '手続き 入力 -> 文字列 { (読む) }')
        self.write('main.ten', '取込 「io.ten」 と 入出力。値 は (入出力.入力)。(値 を 表示する)')
        command = [sys.executable, '-m', 'tenioha', str(self.entry)]
        result = subprocess.run(command, cwd=ROOT, input='Ada\n', text=True, capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'Ada\n', ''))
        result = subprocess.run(command + ['--check'], cwd=ROOT, input='', text=True, capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'OK: 2 statement(s), 1 definition(s) checked.\n', ''))

    def test_cli_module_error_has_source_and_no_traceback(self):
        self.write('bad.ten', '関数 未使用 -> 整数 { 「bad」 }')
        self.write('main.ten', '(「early」 を 表示する) 取込 「bad.ten」 と B')
        result = subprocess.run([sys.executable, '-m', 'tenioha', str(self.entry)], cwd=ROOT,
                                input='', text=True, capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('bad.ten:1:', result.stderr)
        self.assertIn('E_RETURN', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_standard_library_examples(self):
        for name in ['lists', 'options']:
            path = ROOT / 'examples' / f'{name}.ten'
            output = io.StringIO()
            run(path.read_text(), filename=str(path), stdout=output)
            self.assertEqual(output.getvalue(), path.with_suffix('.out').read_text())


if __name__ == '__main__':
    unittest.main()

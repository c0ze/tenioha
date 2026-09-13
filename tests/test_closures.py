import io
from itertools import permutations
from pathlib import Path
import tempfile
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import FunctionValue, format_value
from tenioha.syntax import MAX_NESTING


class ClosureTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_anonymous_function_is_a_value_and_can_be_applied_inline(self):
        value, = run('関数 (値: 整数) を -> 整数 { (値 に 1 を 足す) }')
        self.assertIsInstance(value, FunctionValue)
        self.assertEqual(format_value(value), '関数 {…}')
        self.assertEqual(run('(4 を 適用 関数 (値: 整数) を -> 整数 { (値 に 1 を 足す) })'), [5])
        self.assertEqual(run('(適用 関数 -> 単位 {})'), [None])

    def test_captures_top_level_value_and_ignores_caller_shadowing(self):
        self.assertEqual(run('''
            元 は 10。
            差 は 関数 (量: 整数) を -> 整数 { (元 から 量 を 引く) }。
            { 元 は 20。(3 を 適用 差) }
            (4 を 適用 差)
        '''), [None, None, 7, 6])

    def test_factory_closures_have_independent_lifetimes(self):
        self.assertEqual(run('''
            関数 加算器 (増分: 整数) で -> 関数[整数 を -> 整数] {
                関数 (値: 整数) を -> 整数 { (値 に 増分 を 足す) }
            }
            一増やす は (1 で 加算器)。十増やす は (10 で 加算器)。
            (5 を 適用 一増やす) (5 を 適用 十増やす) (6 を 適用 一増やす)
        '''), [None, None, 6, 15, 7])

    def test_later_shadowing_does_not_change_an_existing_capture(self):
        self.assertEqual(run('''
            値 は 1。
            取得 は {
                内 は 関数 -> 整数 { 値 }。
                値 は 2。
                内
            }。
            (適用 取得)
        '''), [None, None, 1])

    def test_nested_closures_capture_transitively(self):
        self.assertEqual(run('''
            外 は 10。
            工場 は 関数 (左: 整数) を -> 関数[整数 に -> 関数[-> 整数]] {
                関数 (右: 整数) に -> 関数[-> 整数] {
                    関数 -> 整数 { ((左 に 右 を 足す) に 外 を 足す) }
                }
            }。
            内 は (2 を 適用 工場)。結果 は (3 に 適用 内)。
            (適用 結果)
        '''), [None, None, None, None, 15])

    def test_parameters_shadow_outer_values_and_locals_shadow_captures(self):
        self.assertEqual(run('''
            値 は 9。
            一 は 関数 (値: 整数) を -> 整数 { 値 }。
            二 は 関数 -> 整数 { 値 は (値 に 1 を 足す)。値 }。
            (3 を 適用 一) (適用 二) (適用 二) 値
        '''), [None, None, None, 3, 10, 10, 9])
        self.error('関数 (値: 整数) を -> 整数 { 値 は 2。値 }', 'E_BINDING')

    def test_capture_set_excludes_unused_values_and_local_bindings(self):
        value = run('''
            使用 は 2。未使用 は 99。
            関数 (引数: 整数) を -> 整数 {
                内 は (引数 に 使用 を 足す)。
                { 未使用 は 0。未使用 }
                内
            }
        ''')[-1]
        self.assertEqual(dict(value.captures), {'使用': 2})
        with self.assertRaises(TypeError):
            value.captures['使用'] = 3

    def test_nested_capture_sets_account_for_local_shadowing(self):
        value = run('''
            外 は 2。使用 は 10。未使用 は 99。
            関数 -> 関数[-> 整数] {
                使用 は 3。
                関数 -> 整数 { (使用 に 外 を 足す) }
            }
        ''')[-1]
        self.assertEqual(dict(value.captures), {'外': 2})

    def test_generic_factory_can_capture_abstract_values(self):
        self.assertEqual(run('''
            関数 保存<T> (値: T) を -> 関数[-> T] { 関数 -> T { 値 } }
            数 は (7 を 保存<整数>)。文 は (「猫」 を 保存<文字列>)。
            (適用 数) (適用 文)
        '''), [None, None, 7, '猫'])
        self.error('関数 悪い<T> (値: T) を -> 関数[-> 整数] { 関数 -> 整数 { 値 } }', 'E_RETURN')

    def test_generic_closure_parameters_use_enclosing_type_variables(self):
        self.assertEqual(run('''
            関数 恒等<T> (値: T) を -> T { 値 }
            関数 操作<T> -> 関数[T を -> T] { 関数 (値: T) を -> T { (値 を 恒等<T>) } }
            (7 を 適用 (操作<整数>))
        '''), [7])

    def test_closures_can_capture_and_apply_other_functions(self):
        self.assertEqual(run('''
            操作 は 参照 引く。
            差 は 関数 (値: 整数) を -> 整数 { (値 から 3 を 適用 操作) }。
            (10 を 適用 差)
        '''), [None, None, 7])

    def test_named_function_namespace_is_not_captured_as_a_value(self):
        value = run('引く は 99。関数 -> 整数 { (5 から 3 を 引く) }')[-1]
        self.assertEqual(dict(value.captures), {})
        self.assertEqual(run('引く は 99。(適用 関数 -> 整数 { (5 から 3 を 引く) })'), [None, 2])

    def test_closure_returned_from_match_keeps_pattern_binding(self):
        self.assertEqual(run('''
            型 箱 { 包む (値: 整数) を }
            取得 は 場合 (7 を 包む) { (値 を 包む) なら { 関数 -> 整数 { 値 } } }。
            (適用 取得)
        '''), [None, 7])

    def test_condition_and_branch_captures_respect_lexical_bindings(self):
        source = '''
            選択 は 真。値 は 5。
            操作 は 関数 -> 整数 {
                もし 選択 なら { 値 は (値 に 1 を 足す)。値 }
                そうでなければ { 値 }
            }。
        '''
        value = run(source + '操作')[-1]
        self.assertEqual(dict(value.captures), {'選択': True, '値': 5})
        self.assertEqual(run(source + '{ 選択 は 偽。値 は 99。(適用 操作) }'), [None, None, None, 6])

    def test_closures_and_named_references_share_function_types(self):
        self.assertEqual(run('''
            関数 一 -> 整数 { 1 }
            関数 選ぶ (条件: 真偽値) で -> 関数[-> 整数] {
                もし 条件 なら { 関数 -> 整数 { 2 } }
                そうでなければ { 参照 一 }
            }
            (適用 (真 で 選ぶ)) (適用 (偽 で 選ぶ))
        '''), [2, 1])

    def test_match_inside_closure_does_not_capture_pattern_bindings(self):
        value = run('''
            型 箱 { 包む (値: 整数) を }
            値 は 99。外 は 2。
            関数 (入力: 箱) を -> 整数 { 場合 入力 { (値 を 包む) なら { (値 に 外 を 足す) } } }
        ''')[-1]
        self.assertEqual(dict(value.captures), {'外': 2})

    def test_closures_inside_data_and_data_inside_closures(self):
        self.assertEqual(run('''
            型 箱<T> { 包む (値: T) を }
            値 は (7 を 包む<整数>)。
            操作 は 関数 -> 整数 { 場合 値 { (数 を 包む) なら { 数 } } }。
            場合 (操作 を 包む<関数[-> 整数]>) { (取得 を 包む) なら { (適用 取得) } }
        '''), [None, None, 7])

    def test_all_particle_permutations_preserve_captures_and_roles(self):
        source = '''基準 は 10000。操作 は 関数 (千: 整数) から (百: 整数) を (十: 整数) に (一: 整数) で -> 整数 {
            (基準 に ((千 に 1000 を 掛ける) に ((百 に 100 を 掛ける) に ((十 に 10 を 掛ける) に 一 を 足す) を 足す) を 足す) を 足す)
        }。'''
        for arguments in permutations(['1 から', '2 を', '3 に', '4 で']):
            with self.subTest(arguments=arguments):
                self.assertEqual(run(source + f"({' '.join(arguments)} 適用 操作)"), [None, None, 11234])

    def test_closure_type_preserves_particle_order(self):
        self.error('''
            関数 使用 (操作: 関数[整数 から, 整数 を -> 整数]) で -> 単位 {}
            (関数 (量: 整数) を (元: 整数) から -> 整数 { (元 から 量 を 引く) } で 使用)
        ''', 'E_TYPE')
        self.error('(真 を 適用 関数 (値: 整数) を -> 整数 { 値 })', 'E_TYPE')
        self.error('(1 に 適用 関数 (値: 整数) を -> 整数 { 値 })', 'E_ARGUMENTS')

    def test_closure_body_is_delayed_and_creation_is_pure(self):
        value, = run('関数 -> 整数 { (1 を 0 で 割る) }', allow_io=False)
        self.assertIsInstance(value, FunctionValue)
        stdin, stdout = io.StringIO('unused\n'), io.StringIO()
        value, = run('手続き -> 文字列 { (「later」 を 表示する) (読む) }', allow_io=False, stdin=stdin, stdout=stdout)
        self.assertEqual(format_value(value), '手続き {…}')
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_procedure_closure_captures_bound_input_and_sequences_output(self):
        stdout = io.StringIO()
        self.assertEqual(run('''
            名前 は (読む)。
            挨拶 は 手続き -> 単位 { ((「こんにちは、」 と 名前 を 連結する) を 表示する) }。
            (適用 挨拶) (適用 挨拶)
        ''', stdin=io.StringIO('Ada\n'), stdout=stdout), [None, None, None, None])
        self.assertEqual(stdout.getvalue(), 'こんにちは、Ada\nこんにちは、Ada\n')

    def test_pure_factory_can_return_procedure_closure(self):
        stdout = io.StringIO()
        self.assertEqual(run('''
            関数 出力器 (文: 文字列) を -> 手続き[-> 単位] {
                手続き -> 単位 { (文 を 表示する) }
            }
            操作 は (「猫」 を 出力器)。(適用 操作)
        ''', stdout=stdout), [None, None])
        self.assertEqual(stdout.getvalue(), '猫\n')

    def test_closures_cannot_hide_io(self):
        for source, code in [
            ('関数 -> 文字列 { (読む) }', 'E_EFFECT'),
            ('読む値 は 参照 読む。関数 -> 文字列 { (適用 読む値) }', 'E_EFFECT'),
            ('((適用 手続き -> 文字列 { (読む) }) を 表示する)', 'E_EFFECT'),
            ('関数 使用 (操作: 関数[-> 整数]) で -> 単位 {} (手続き -> 整数 { 1 } で 使用)', 'E_TYPE'),
            ('関数 -> 関数[-> 整数] { 手続き -> 整数 { 1 } }', 'E_RETURN'),
        ]:
            with self.subTest(source=source):
                self.error(source, code)
        self.error('(適用 手続き -> 整数 { 1 })', 'E_EFFECT', allow_io=False)

    def test_unused_and_unselected_closures_are_checked_before_io(self):
        for suffix in ['関数 -> 整数 { 「bad」 }',
                       '操作 は 関数 -> 文字列 { (読む) }',
                       'もし 真 なら { 関数 -> 整数 { 1 } } そうでなければ { 関数 -> 整数 { 不明 } }']:
            stdin, stdout = io.StringIO('unused\n'), io.StringIO()
            with self.assertRaises(Diagnostic):
                run('(「early」 を 表示する) (読む) ' + suffix, stdin=stdin, stdout=stdout)
            self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_later_and_self_bindings_are_not_visible(self):
        self.error('操作 は 関数 -> 整数 { 値 }。値 は 3', 'E_NAME')
        self.error('操作 は 関数 -> 整数 { (適用 操作) }', 'E_NAME')
        self.error('関数 工場 -> 関数[-> 整数] { 関数 -> 整数 { 外 } } 外 は 3', 'E_NAME')

    def test_invalid_closure_signatures_are_diagnosed(self):
        for source, code in [
            ('関数 (値: 整数) を (別: 整数) を -> 整数 { 値 }', 'E_PARAMETER'),
            ('関数 (値: 整数) を (値: 整数) に -> 整数 { 値 }', 'E_PARAMETER'),
            ('関数 (がく: 整数) を (か\u3099く: 整数) に -> 整数 { がく }', 'E_PARAMETER'),
            ('関数 (値: 不明) を -> 単位 {}', 'E_TYPE_NAME'),
            ('関数 -> 不明 {}', 'E_TYPE_NAME'),
            ('関数 -> 整数 {}', 'E_RETURN'),
            ('関数 -> 整数 { 値 は 1 }', 'E_RETURN'),
        ]:
            with self.subTest(source=source):
                self.error(source, code)

    def test_nfc_capture_names_resolve(self):
        self.assertEqual(run('か\u3099く は 7。取得 は 関数 -> 整数 { がく }。(適用 取得)'), [None, None, 7])

    def test_closure_factory_keeps_module_function_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'factory.ten').write_text('''
                関数 補正 (値: 整数) を -> 整数 { (値 に 2 を 足す) }
                関数 作る (値: 整数) を -> 関数[-> 整数] { 関数 -> 整数 { (値 を 補正) } }
            ''')
            source = '''
                取込 「factory.ten」 と 工場。
                関数 補正 (値: 整数) を -> 整数 { 99 }
                値 は 100。操作 は (7 を 工場.作る)。(適用 操作)
            '''
            self.assertEqual(run(source, filename=str(root / 'main.ten')), [None, None, 9])
            (root / 'factory.ten').write_text('関数 -> 整数 { 1 }')
            self.error(source, 'E_MODULE_BODY', filename=str(root / 'main.ten'))

    def test_reexecuting_compiled_program_refreshes_captures(self):
        program = compile_source('文 は (読む)。操作 は 関数 -> 文字列 { 文 }。(適用 操作)')
        self.assertEqual(execute(program, stdin=io.StringIO('one\n')), [None, None, 'one'])
        self.assertEqual(execute(program, stdin=io.StringIO('two\n')), [None, None, 'two'])

    def test_closure_calls_share_the_explicit_stack_and_call_limit(self):
        source = '''
            関数 作る (数: 整数) を -> 関数[-> 整数] {
                もし (数 と 0 が 等しい) なら { 関数 -> 整数 { 0 } }
                そうでなければ {
                    前 は ((数 から 1 を 引く) を 作る)。
                    関数 -> 整数 { ((適用 前) に 1 を 足す) }
                }
            }
        '''
        self.assertEqual(run(source + '操作 は (1000 を 作る)。(適用 操作)'), [None, 1000])
        self.error('''
            関数 再帰 -> 整数 { (適用 関数 -> 整数 { (再帰) }) } (再帰)
        ''', 'E_CALL_DEPTH')

    def test_closure_nesting_is_bounded(self):
        source = '関数 -> 単位 { ' * MAX_NESTING + '(何もしない)' + ' }' * MAX_NESTING
        self.error(source, 'E_DEPTH')

    def test_malformed_closures_have_source_diagnostics(self):
        for source in ['関数 (値 整数) を -> 整数 { 値 }', '関数 (値: 整数) -> 整数 { 値 }',
                       '関数 -> 整数 {', '関数 (値: 整数) を { 値 }', '関数<T> -> T {}']:
            with self.subTest(source=source):
                with self.assertRaises(Diagnostic):
                    compile_source(source)


if __name__ == '__main__':
    unittest.main()

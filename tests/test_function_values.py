import io
from itertools import permutations
import unittest

from tenioha import Diagnostic, run
from tenioha.core import FunctionValue


class FunctionValueTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_explicit_builtin_reference_and_application(self):
        self.assertEqual(run('差 は 参照 引く。(5 から 3 を 適用 差) (3 を 5 から 適用 差)'), [None, 2, 2])
        self.assertEqual(run('(5 から 3 を 適用 参照 引く)'), [2])
        self.assertEqual(run('(適用 参照 何もしない)'), [None])

    def test_user_function_reference_and_separate_namespaces(self):
        self.assertEqual(run('''
            関数 増やす (値: 整数) を -> 整数 { (値 に 1 を 足す) }
            足す は 参照 増やす。
            (4 を 適用 足す) (4 に 3 を 足す)
        '''), [None, 5, 7])

    def test_forward_reference(self):
        self.assertEqual(run('値 は 参照 一。(適用 値) 関数 一 -> 整数 { 1 }'), [None, 1])

    def test_function_parameters_and_returned_values(self):
        source = '''
        関数 選ぶ (条件: 真偽値) で -> 関数[整数 から, 整数 を -> 整数] {
            もし 条件 なら { 参照 引く } そうでなければ { 参照 差 }
        }
        関数 差 (元: 整数) から (量: 整数) を -> 整数 { (元 から 量 を 引く) }
        関数 計算 (操作: 関数[整数 から, 整数 を -> 整数]) で -> 整数 {
            (3 を 10 から 適用 操作)
        }
        ((真 で 選ぶ) で 計算) (3 を 10 から 適用 (偽 で 選ぶ))
        '''
        self.assertEqual(run(source), [7, 7])

    def test_generic_function_references_are_specialized(self):
        source = '''
        関数 恒等<T> (値: T) を -> T { 値 }
        数 は 参照 恒等<整数>。文 は 参照 恒等<文字列>。
        (7 を 適用 数) (「猫」 を 適用 文)
        '''
        self.assertEqual(run(source), [None, None, 7, '猫'])
        self.error(source + '(真 を 適用 数)', 'E_TYPE')
        self.error('関数 恒等<T> (値: T) を -> T { 値 } 参照 恒等', 'E_TYPE_ARGUMENTS')

    def test_generic_function_value_as_type_argument(self):
        self.assertEqual(run('''
        関数 恒等<T> (値: T) を -> T { 値 }
        差 は (参照 引く を 恒等<関数[整数 から, 整数 を -> 整数]>)。
        (9 から 2 を 適用 差)
        '''), [None, 7])

    def test_generic_function_can_return_specialized_reference(self):
        self.assertEqual(run('''
        関数 恒等<T> (値: T) を -> T { 値 }
        関数 取得<T> -> 関数[T を -> T] { 参照 恒等<T> }
        操作 は (取得<整数>)。(7 を 適用 操作)
        '''), [None, 7])

    def test_constructors_can_be_function_values(self):
        self.assertEqual(run('''
        型 箱<T> { 包む (値: T) を }
        作る は 参照 包む<整数>。
        場合 (8 を 適用 作る) { (値 を 包む) なら { 値 } }
        '''), [None, 8])

    def test_indirect_four_parameter_permutations(self):
        declaration = '''関数 桁 (千: 整数) から (百: 整数) を (十: 整数) に (一: 整数) で -> 整数 {
            ((千 に 1000 を 掛ける) に ((百 に 100 を 掛ける) に ((十 に 10 を 掛ける) に 一 を 足す) を 足す) を 足す)
        } 操作 は 参照 桁。'''
        for arguments in permutations(['1 から', '2 を', '3 に', '4 で']):
            with self.subTest(arguments=arguments):
                self.assertEqual(run(declaration + f"({' '.join(arguments)} 適用 操作)"), [None, 1234])

    def test_particle_order_is_part_of_function_type(self):
        declaration = '関数 使用 (操作: 関数[整数 を, 整数 から -> 整数]) で -> 整数 { (3 を 5 から 適用 操作) }'
        self.error(declaration + '(参照 引く で 使用)', 'E_TYPE')
        self.error('関数 使用 (操作: 関数[整数 に, 整数 を -> 整数]) で -> 単位 {} (参照 引く で 使用)', 'E_TYPE')
        self.error('関数 使用 (操作: 関数[整数 を, 整数 を -> 整数]) で -> 単位 {}', 'E_PARAMETER')

    def test_indirect_calls_preserve_canonical_exception_order(self):
        for arguments in ['(1 を 0 で 割る) から (2 を 0 で 割る) を', '(2 を 0 で 割る) を (1 を 0 で 割る) から']:
            source = f'({arguments} 適用 参照 引く)'
            error = self.error(source, 'E_ZERO_DIVISION')
            self.assertEqual(error.span.start, source.index('割る', source.index('(1 を')))

    def test_callee_evaluates_before_arguments(self):
        source = '''関数 取得 -> 関数[整数 から, 整数 を -> 整数] {
            (1 を 0 で 割る) 参照 引く
        }
        ((2 を 0 で 割る) から 3 を 適用 (取得))'''
        error = self.error(source, 'E_ZERO_DIVISION')
        self.assertEqual(error.span.start, source.index('割る'))

    def test_referencing_io_is_pure_but_calling_it_is_io(self):
        stdin, stdout = io.StringIO('unused\n'), io.StringIO()
        values = run('参照 読む 参照 表示する', allow_io=False, stdin=stdin, stdout=stdout)
        self.assertTrue(all(isinstance(value, FunctionValue) for value in values))
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))
        self.error('(適用 参照 読む)', 'E_EFFECT', allow_io=False)
        self.error('((適用 参照 読む) を 表示する)', 'E_EFFECT')

    def test_higher_order_procedure_sequences_io(self):
        stdout = io.StringIO()
        values = run('''
        手続き 二回 (出力: 手続き[文字列 を -> 単位]) で -> 単位 {
            (「一」 を 適用 出力)。
            (「二」 を 適用 出力)
        }
        (参照 表示する で 二回)
        ''', stdout=stdout)
        self.assertEqual((values, stdout.getvalue()), ([None], '一\n二\n'))

    def test_io_cannot_be_hidden_by_function_types(self):
        self.error('関数 使用 (操作: 関数[-> 文字列]) で -> 文字列 { (適用 操作) } (参照 読む で 使用)', 'E_TYPE')
        self.error('関数 悪い (操作: 手続き[-> 文字列]) で -> 文字列 { (適用 操作) }', 'E_EFFECT')
        self.error('関数 悪い -> 関数[-> 文字列] { 参照 読む }', 'E_RETURN')
        self.error('もし 真 なら { 参照 何もしない } そうでなければ { 参照 表示する }', 'E_BRANCH_TYPE')

    def test_procedure_returning_a_function_must_be_bound_first(self):
        declaration = '手続き 取得 -> 関数[整数 から, 整数 を -> 整数] { 参照 引く }'
        self.error(declaration + '(5 から 3 を 適用 (取得))', 'E_EFFECT')
        self.assertEqual(run(declaration + '操作 は (取得)。(5 から 3 を 適用 操作)'), [None, 2])

    def test_data_containing_io_reference_preserves_effect(self):
        self.error('''
        型 箱<T> { 包む (値: T) を }
        関数 悪い (値: 箱<手続き[-> 文字列]>) を -> 文字列 {
            場合 値 { (操作 を 包む) なら { (適用 操作) } }
        }
        ''', 'E_EFFECT')

    def test_nonfunction_values_and_unknown_references_are_rejected(self):
        self.error('(1 を 適用 3)', 'E_CALLABLE')
        self.error('参照 不明', 'E_FUNCTION')
        self.error('値 は 1。参照 値', 'E_FUNCTION')
        self.error('(3 に 5 に 適用 参照 引く)', 'E_ARGUMENTS')

    def test_indirect_recursion_retains_call_limit(self):
        self.error('関数 再帰 -> 整数 { (適用 参照 再帰) } (再帰)', 'E_CALL_DEPTH')

    def test_polymorphic_recursion_does_not_expand_runtime_types(self):
        self.error('型 箱<T> { 包む (値: T) を } 関数 再帰<T> -> 単位 { (再帰<箱<T>>) } (再帰<整数>)', 'E_CALL_DEPTH')

    def test_invalid_higher_order_body_prevents_earlier_io(self):
        stdout = io.StringIO()
        self.error('(「early」 を 表示する) 関数 不正 -> 整数 { (適用 参照 読む) }', 'E_EFFECT', stdout=stdout)
        self.assertEqual(stdout.getvalue(), '')


if __name__ == '__main__':
    unittest.main()

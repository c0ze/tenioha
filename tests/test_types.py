import io
from itertools import permutations
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import DataValue, format_value
from tenioha.syntax import MAX_NESTING


LIST = '''
型 一覧<T> { 空。節 (頭: T) を (尾: 一覧<T>) に }
関数 長さ<T> (値: 一覧<T>) を -> 整数 {
    場合 値 {
        (空) なら { 0 }
        (_ を 残り に 節) なら { ((残り を 長さ<T>) に 1 を 足す) }
    }
}
'''
OPTION = '型 選択<T> { 無し。有り (値: T) を }'


class TypeTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_nullary_and_parameterized_constructors(self):
        values = run('型 色 { 赤。青 } (赤) (青)')
        self.assertTrue(all(isinstance(value, DataValue) for value in values))
        self.assertEqual([format_value(value) for value in values], ['(赤)', '(青)'])
        self.assertEqual(format_value(run(OPTION + '(「猫」 を 有り<文字列>)')[0]), '(「猫」 を 有り)')

    def test_recursive_generic_list(self):
        self.assertEqual(run(LIST + '((1 を (2 を (空<整数>) に 節<整数>) に 節<整数>) を 長さ<整数>)'), [2])
        self.assertEqual(run(LIST + '((「猫」 を (空<文字列>) に 節<文字列>) を 長さ<文字列>)'), [1])

    def test_constructor_and_match_parameter_permutations(self):
        declaration = '型 数組 { 組 (千: 整数) から (百: 整数) を (十: 整数) に (一: 整数) で }'
        pattern = '場合 値 { (D で B を A から C に 組) なら { ((A に 1000 を 掛ける) に ((B に 100 を 掛ける) に ((C に 10 を 掛ける) に D を 足す) を 足す) を 足す) } }'
        for arguments in permutations(['1 から', '2 を', '3 に', '4 で']):
            with self.subTest(arguments=arguments):
                self.assertEqual(run(declaration + f"値 は ({' '.join(arguments)} 組)。" + pattern), [None, 1234])

    def test_nominal_types_are_distinct(self):
        self.error('型 A { 甲 } 型 B { 乙 } 関数 受ける (値: A) を -> A { 値 } ((乙) を 受ける)', 'E_TYPE')
        self.error(OPTION + 'もし 真 なら { (無し<整数>) } そうでなければ { (無し<文字列>) }', 'E_BRANCH_TYPE')

    def test_nested_generic_type_substitution(self):
        source = OPTION + '''
        関数 包む<T> (値: T) を -> 選択<T> { (値 を 有り<T>) }
        値 は ((7 を 包む<整数>) を 包む<選択<整数>>)。
        場合 値 {
            (無し) なら { 0 }
            (内 を 有り) なら {
                場合 内 { (無し) なら { 1 } (数 を 有り) なら { 数 } }
            }
        }
        '''
        self.assertEqual(run(source), [None, 7])

    def test_multiple_type_parameters(self):
        source = '''型 対<A, B> { 組 (左: A) を (右: B) と }
        関数 右<A, B> (値: 対<A, B>) から -> B {
            場合 値 { (_ を 結果 と 組) なら { 結果 } }
        }
        ((7 を 「猫」 と 組<整数, 文字列>) から 右<整数, 文字列>)'''
        self.assertEqual(run(source), ['猫'])

    def test_generic_body_is_checked_for_all_types(self):
        self.error('関数 悪い<T> (値: T) を -> 整数 { (値 に 1 を 足す) }', 'E_TYPE')
        self.error('関数 悪い<T> -> T { 1 }', 'E_RETURN')
        self.error('関数 恒等<T> (値: T) を -> T { 値 } (「猫」 を 恒等<整数>)', 'E_TYPE')

    def test_missing_extra_and_unknown_type_arguments(self):
        for suffix, code in [
            ('(無し)', 'E_TYPE_ARGUMENTS'), ('(無し<整数, 文字列>)', 'E_TYPE_ARGUMENTS'),
            ('(無し<不明>)', 'E_TYPE_NAME'), ('(何もしない<整数>)', 'E_TYPE_ARGUMENTS'),
            ('関数 悪い (値: 選択) を -> 単位 {}', 'E_TYPE_ARGUMENTS'),
            ('関数 悪い (値: 整数<文字列>) を -> 単位 {}', 'E_TYPE_ARGUMENTS'),
            ('関数 悪い<T> (値: T<整数>) を -> 単位 {}', 'E_TYPE_ARGUMENTS'),
        ]:
            with self.subTest(suffix=suffix):
                self.error(OPTION + suffix, code)

    def test_duplicate_and_shadowing_type_parameters(self):
        for source in ['型 組<T, T> { 作る }', '関数 同じ<T, T> -> 単位 {}',
                       '型 組<整数> { 作る }', '型 T { 作る } 関数 同じ<T> -> 単位 {}']:
            self.error(source, 'E_TYPE_PARAMETER')
        self.error('型 組<がく, か\u3099く> { 作る }', 'E_TYPE_PARAMETER')

    def test_forward_and_mutually_recursive_types(self):
        source = '''
        関数 測る (値: A) を -> 整数 {
            場合 値 { (終) なら { 0 } (内 を 次) なら { 場合 内 { (残 を 戻る) なら { ((残 を 測る) に 1 を 足す) } } } }
        }
        型 A { 終。次 (値: B) を }
        型 B { 戻る (値: A) を }
        ((((終) を 戻る) を 次) を 測る)
        '''
        self.assertEqual(run(source), [1])

    def test_invalid_type_and_constructor_declarations(self):
        for source, code in [
            ('型 空型 {}', 'E_TYPE_DECL'), ('型 整数 { 作る }', 'E_DUPLICATE_TYPE'),
            ('型 同じ { 甲 } 型 同じ { 乙 }', 'E_DUPLICATE_TYPE'),
            ('型 A { 組 } 型 B { 組 }', 'E_DUPLICATE_FUNCTION'),
            ('型 A { 足す }', 'E_DUPLICATE_FUNCTION'),
            ('型 A { 組 } 関数 組 -> 単位 {}', 'E_DUPLICATE_FUNCTION'),
            ('型 A { 組 (値: 不明) を }', 'E_TYPE_NAME'),
            ('型 A { 組 (値: 整数) を (別: 整数) を }', 'E_PARAMETER'),
            ('型 A { 組 (値: 整数) を (値: 整数) に }', 'E_PARAMETER'),
            ('{ 型 A { 組 } }', 'E_DEFINITION'),
        ]:
            with self.subTest(source=source):
                self.error(source, code)

    def test_match_requires_all_constructors(self):
        for arms in ['', '(無し) なら { 0 }', '(値 を 有り) なら { 値 }']:
            error = self.error(OPTION + '場合 (無し<整数>) { ' + arms + ' }', 'E_MATCH_EXHAUSTIVE')
            self.assertIn('Missing constructor', error.message)

    def test_match_rejects_duplicate_and_foreign_constructors(self):
        self.error(OPTION + '場合 (無し<整数>) { (無し) なら { 0 } (無し) なら { 1 } }', 'E_PATTERN')
        self.error(OPTION + '型 別 { 外 } 場合 (無し<整数>) { (外) なら { 0 } }', 'E_PATTERN')
        self.error(OPTION + '場合 (無し<整数>) { (何もしない) なら { 0 } }', 'E_PATTERN')
        self.error(OPTION + '場合 (無し<整数>) { (不明) なら { 0 } }', 'E_PATTERN')

    def test_match_field_roles_are_checked(self):
        for bindings in ['', '値 に', '値 を 別 を', '値 を 別 で']:
            self.error(OPTION + f'場合 (無し<整数>) {{ (無し) なら {{ 0 }} ({bindings} 有り) なら {{ 1 }} }}', 'E_ARGUMENTS')

    def test_pattern_names_are_unique_and_wildcards_do_not_bind(self):
        source = '型 対 { 組 (左: 整数) を (右: 整数) に } 場合 (1 を 2 に 組) '
        self.error(source + '{ (値 を 値 に 組) なら { 値 } }', 'E_PATTERN')
        self.assertEqual(run(source + '{ (_ を _ に 組) なら { 3 } }'), [3])
        self.error(source + '{ (_ を _ に 組) なら { _ } }', 'E_NAME')

    def test_pattern_bindings_shadow_and_stay_local(self):
        source = OPTION + '値 は 9。場合 (3 を 有り<整数>) { (無し) なら { 0 } (値 を 有り) なら { 値 } } 値'
        self.assertEqual(run(source), [None, 3, 9])
        self.error(OPTION + '場合 (3 を 有り<整数>) { (無し) なら { 0 } (値 を 有り) なら { 値 } } 値', 'E_NAME')
        self.error(OPTION + '場合 (3 を 有り<整数>) { (無し) なら { 0 } (値 を 有り) なら { 値 は 4。値 } }', 'E_BINDING')

    def test_match_subject_must_be_pure_algebraic_value(self):
        self.error('場合 1 {}', 'E_MATCH_TYPE')
        self.error(OPTION + '手続き 入力 -> 選択<整数> { (無し<整数>) } 場合 (入力) {}', 'E_EFFECT')

    def test_match_arms_are_lazy_and_statically_checked(self):
        self.assertEqual(run(OPTION + '場合 (無し<整数>) { (無し) なら { 3 } (値 を 有り) なら { (1 を 0 で 割る) } }'), [3])
        self.error(OPTION + '場合 (無し<整数>) { (無し) なら { 3 } (値 を 有り) なら { 「猫」 } }', 'E_BRANCH_TYPE')
        self.error(OPTION + '場合 (無し<整数>) { (無し) なら { 3 } (値 を 有り) なら { 不明 } }', 'E_NAME')

    def test_match_and_constructor_effects(self):
        output = io.StringIO()
        source = OPTION + '場合 (無し<整数>) { (無し) なら { (「ok」 を 表示する) } (_ を 有り) なら { (「bad」 を 表示する) } }'
        self.assertEqual(run(source, stdout=output), [None])
        self.assertEqual(output.getvalue(), 'ok\n')
        self.error(source, 'E_EFFECT', allow_io=False)
        self.error(OPTION + '((読む) を 有り<文字列>)', 'E_EFFECT')

    def test_invalid_uncalled_generic_body_prevents_io(self):
        stdin, stdout = io.StringIO('unused\n'), io.StringIO()
        self.error('(「early」 を 表示する) (読む) ' + OPTION + '''
            関数 不完全<T> (値: 選択<T>) を -> 整数 { 場合 値 { (無し) なら { 0 } } }
        ''', 'E_MATCH_EXHAUSTIVE', stdin=stdin, stdout=stdout)
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_deep_list_evaluation_and_formatting_use_explicit_stacks(self):
        source = LIST + '''
        関数 作る (数: 整数) を -> 一覧<整数> {
            もし (数 と 0 が 等しい) なら { (空<整数>) }
            そうでなければ { (数 を ((数 から 1 を 引く) を 作る) に 節<整数>) }
        }
        値 は (1000 を 作る)。
        (値 を 長さ<整数>) 値
        '''
        values = run(source)
        self.assertEqual(values[1], 1000)
        rendered = format_value(values[2])
        self.assertEqual(rendered.count(' に 節)'), 1000)
        self.assertTrue(rendered.startswith('(1000 を (999 を '))

    def test_data_format_escapes_nested_strings(self):
        value = run(OPTION + '(「a\\n\\」\\\\」 を 有り<文字列>)')[0]
        self.assertEqual(format_value(value), '(「a\\n\\」\\\\」 を 有り)')

    def test_type_and_constructor_names_use_nfc(self):
        self.assertEqual(run('型 か\u3099た { か\u3099く } 関数 文 (値: がた) を -> 整数 { 場合 値 { (がく) なら { 7 } } } ((がく) を 文)'), [7])
        self.error('型 がた { 作る } 型 か\u3099た { 別 }', 'E_DUPLICATE_TYPE')

    def test_type_nesting_limit_is_a_diagnostic(self):
        source = '関数 深い (値: ' + '選択<' * MAX_NESTING + '整数' + '>' * MAX_NESTING + ') を -> 単位 {}'
        self.error(OPTION + source, 'E_DEPTH')

    def test_malformed_m2_syntax_has_language_diagnostics(self):
        for source in ['型 A {', '型 A<T,> { 作る }', '型 A { 作る (値 整数) を }',
                       '型 A { 作る } 場合 (作る) {', '場合 1 { (名前)', '関数 名 -> 関数[整数 -> 整数] {}',
                       '関数 名<> -> 単位 {}', '参照', '(適用)', '(1 を 適用 参照)', '取込 「x」']:
            with self.subTest(source=source):
                with self.assertRaises(Diagnostic):
                    compile_source(source)

    def test_compiled_generic_program_is_reusable(self):
        program = compile_source(LIST + '値 は (1 を (空<整数>) に 節<整数>)。(値 を 長さ<整数>)')
        self.assertEqual(execute(program), [None, 1])
        self.assertEqual(execute(program), [None, 1])


if __name__ == '__main__':
    unittest.main()

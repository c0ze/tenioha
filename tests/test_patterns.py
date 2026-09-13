import io
from itertools import permutations, product
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import BUILTINS, Builtin, Effect, ValueType
from tenioha.syntax import MAX_NESTING


OPTION = '型 選択<T> { 無し。有り (値: T) を }'
LIST = '型 一覧<T> { 空。節 (頭: T) を (尾: 一覧<T>) に }'
PAIR = '型 色 { 赤。青 } 型 対 { 組 (左: 色) を (右: 色) に }'


class PatternTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code, caught.exception.render())
        return caught.exception

    def test_nested_option_patterns_and_generic_field_binding(self):
        source = OPTION + '''
            関数 取得<T> (入力: 選択<選択<T>>) から (既定値: T) を -> T {
                場合 入力 {
                    (無し) なら { 既定値 }
                    ((無し) を 有り) なら { 既定値 }
                    ((値 を 有り) を 有り) なら { 値 }
                }
            }
            ((無し<選択<整数>>) から 3 を 取得<整数>)
            (((無し<整数>) を 有り<選択<整数>>) から 4 を 取得<整数>)
            (((7 を 有り<整数>) を 有り<選択<整数>>) から 5 を 取得<整数>)
        '''
        self.assertEqual(run(source), [3, 4, 7])

    def test_root_wildcard_and_binding_fallbacks(self):
        self.assertEqual(run(OPTION + '''
            場合 (7 を 有り<整数>) { _ なら { 1 } }
            場合 (7 を 有り<整数>) {
                (無し) なら { 0 }
                残り なら { 場合 残り { (無し) なら { 2 } (値 を 有り) なら { 値 } } }
            }
        '''), [1, 7])
        self.error(OPTION + '場合 (無し<整数>) { _ なら { _ } }', 'E_NAME')

    def test_bare_names_are_bindings_including_constructor_spellings(self):
        self.assertEqual(run(OPTION + '場合 (7 を 有り<整数>) { 無し なら { 場合 無し { (無し) なら { 0 } (値 を 有り) なら { 値 } } } }'), [7])

    def test_first_matching_arm_wins_when_patterns_overlap(self):
        source = PAIR + '''
            関数 選ぶ (値: 対) を -> 整数 {
                場合 値 {
                    ((赤) を _ に 組) なら { 1 }
                    (_ を (青) に 組) なら { 2 }
                    (_ を _ に 組) なら { 3 }
                }
            }
            (((赤) を (青) に 組) を 選ぶ)
            (((青) を (青) に 組) を 選ぶ)
            (((青) を (赤) に 組) を 選ぶ)
        '''
        self.assertEqual(run(source), [1, 2, 3])

    def test_exhaustiveness_tracks_combinations_not_individual_fields(self):
        error = self.error(PAIR + '''
            関数 不完全 (値: 対) を -> 整数 {
                場合 値 {
                    ((赤) を (赤) に 組) なら { 1 }
                    ((青) を (青) に 組) なら { 2 }
                }
            }
        ''', 'E_MATCH_EXHAUSTIVE')
        self.assertIn('((赤) を (青) に 組)', error.message)

    def test_missing_nested_constructor_is_reported(self):
        error = self.error(OPTION + '''
            関数 不完全 (値: 選択<選択<整数>>) を -> 整数 {
                場合 値 { (無し) なら { 0 } ((無し) を 有り) なら { 1 } }
            }
        ''', 'E_MATCH_EXHAUSTIVE')
        self.assertIn('((_ を 有り) を 有り)', error.message)

    def test_complete_nested_split_accepts_repeated_outer_constructor(self):
        self.assertEqual(run(PAIR + '''
            場合 ((青) を (赤) に 組) {
                ((赤) を (赤) に 組) なら { 1 }
                ((赤) を (青) に 組) なら { 2 }
                ((青) を (赤) に 組) なら { 3 }
                ((青) を (青) に 組) なら { 4 }
            }
        '''), [3])

    def test_fallback_after_complete_split_is_unreachable(self):
        error = self.error(PAIR + '''
            場合 ((赤) を (赤) に 組) {
                ((赤) を _ に 組) なら { 1 }
                ((青) を _ に 組) なら { 2 }
                _ なら { 3 }
            }
        ''', 'E_PATTERN')
        self.assertIn('Unreachable', error.message)

    def test_union_of_earlier_arms_can_cover_a_later_pattern(self):
        self.error(PAIR + '''
            場合 ((赤) を (赤) に 組) {
                (_ を (赤) に 組) なら { 1 }
                (_ を (青) に 組) なら { 2 }
                ((赤) を _ に 組) なら { 3 }
            }
        ''', 'E_PATTERN')

    def test_general_pattern_before_specific_one_is_unreachable(self):
        for first in ['_', '全体', '(_ を _ に 組)']:
            self.error(PAIR + f'場合 ((赤) を (赤) に 組) {{ {first} なら {{ 1 }} ((赤) を (青) に 組) なら {{ 2 }} }}', 'E_PATTERN')

    def test_bindings_do_not_make_identical_shapes_distinct(self):
        self.error(OPTION + '場合 (無し<整数>) { (値 を 有り) なら { 値 } (別 を 有り) なら { 別 } (無し) なら { 0 } }', 'E_PATTERN')

    def test_nested_particle_permutations_preserve_bindings(self):
        declaration = '型 桁型 { 桁 (千: 整数) から (百: 整数) を (十: 整数) に (一: 整数) で } 型 箱 { 包む (中: 桁型) を }'
        for fields in permutations(['A から', 'B を', 'C に', 'D で']):
            source = declaration + f'''場合 ((1 から 2 を 3 に 4 で 桁) を 包む) {{
                (({' '.join(fields)} 桁) を 包む) なら {{
                    ((A に 1000 を 掛ける) に ((B に 100 を 掛ける) に ((C に 10 を 掛ける) に D を 足す) を 足す) を 足す)
                }}
            }}'''
            with self.subTest(fields=fields):
                self.assertEqual(run(source), [1234])

    def test_particle_reordering_does_not_make_pattern_reachable(self):
        self.error(PAIR + '''
            場合 ((赤) を (青) に 組) {
                ((赤) を (青) に 組) なら { 1 }
                ((青) に (赤) を 組) なら { 2 }
                _ なら { 3 }
            }
        ''', 'E_PATTERN')

    def test_duplicate_bindings_across_pattern_levels_are_rejected(self):
        self.error(OPTION + '型 対 { 組 (左: 整数) を (右: 選択<整数>) に } 場合 (1 を (2 を 有り<整数>) に 組) { (値 を (値 を 有り) に 組) なら { 値 } _ なら { 0 } }', 'E_PATTERN')
        self.error(OPTION + '型 対 { 組 (左: 整数) を (右: 選択<整数>) に } 場合 (1 を (2 を 有り<整数>) に 組) { (がく を (か\u3099く を 有り) に 組) なら { がく } _ なら { 0 } }', 'E_PATTERN')

    def test_nested_wildcards_repeat_without_binding(self):
        self.assertEqual(run(OPTION + '型 対 { 組 (左: 整数) を (右: 選択<整数>) に } 場合 (1 を (2 を 有り<整数>) に 組) { (_ を (_ を 有り) に 組) なら { 7 } _ なら { 0 } }'), [7])

    def test_nested_bindings_shadow_and_stay_in_their_arm(self):
        source = OPTION + '''値 は 9。
            場合 ((7 を 有り<整数>) を 有り<選択<整数>>) {
                ((値 を 有り) を 有り) なら { 値 }
                _ なら { 0 }
            } 値'''
        self.assertEqual(run(source), [None, 7, 9])
        self.error(OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ((内 を 有り) を 有り) なら { 内 } _ なら { 0 } } 内', 'E_NAME')
        self.error(OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ((内 を 有り) を 有り) なら { 内 は 8。内 } _ なら { 0 } }', 'E_BINDING')

    def test_failed_arm_does_not_leak_partial_bindings(self):
        source = OPTION + '''型 対 { 組 (左: 整数) を (右: 選択<整数>) に }
            値 は 9。
            場合 (1 を (無し<整数>) に 組) {
                (値 を (_ を 有り) に 組) なら { 値 }
                _ なら { 値 }
            }
        '''
        self.assertEqual(run(source), [None, 9])

    def test_closures_retain_nested_and_root_bindings(self):
        self.assertEqual(run(OPTION + '''
            取得 は 場合 ((7 を 有り<整数>) を 有り<選択<整数>>) {
                ((値 を 有り) を 有り) なら { 関数 -> 整数 { 値 } }
                _ なら { 関数 -> 整数 { 0 } }
            }。
            (適用 取得)
            別 は 場合 (3 を 有り<整数>) {
                全体 なら { 関数 -> 整数 { 場合 全体 { (無し) なら { 0 } (値 を 有り) なら { 値 } } } }
            }。
            (適用 別)
        '''), [None, 7, None, 3])

    def test_nested_pattern_bindings_are_not_closure_captures(self):
        value = run(OPTION + '''値 は 9。外 は 2。
            関数 (入力: 選択<選択<整数>>) を -> 整数 {
                場合 入力 { ((値 を 有り) を 有り) なら { (値 に 外 を 足す) } _ なら { 外 } }
            }
        ''')[-1]
        self.assertEqual(dict(value.captures), {'外': 2})

    def test_constructor_patterns_reject_primitive_and_abstract_fields(self):
        self.error(OPTION + '場合 (7 を 有り<整数>) { ((無し) を 有り) なら { 0 } _ なら { 1 } }', 'E_PATTERN')
        self.error(OPTION + '関数 不正<T> (値: 選択<T>) を -> 整数 { 場合 値 { ((無し) を 有り) なら { 0 } _ なら { 1 } } }', 'E_PATTERN')
        self.error(OPTION + '場合 (参照 読む を 有り<手続き[-> 文字列]>) { ((無し) を 有り) なら { 0 } _ なら { 1 } }', 'E_PATTERN')

    def test_inner_particle_errors_keep_original_span(self):
        for fields in ['', '値 に', '値 を 別 を']:
            source = OPTION + f'場合 ((7 を 有り<整数>) を 有り<選択<整数>>) {{ (({fields} 有り) を 有り) なら {{ 0 }} _ なら {{ 1 }} }}'
            self.error(source, 'E_ARGUMENTS')
        self.error(OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ((値 を 有り)を 有り) なら { 0 } _ なら { 1 } }', 'E_SPACE')

    def test_nested_patterns_remain_nominal(self):
        self.error(OPTION + '型 別 { 外 } 場合 ((無し<整数>) を 有り<選択<整数>>) { ((外) を 有り) なら { 0 } _ なら { 1 } }', 'E_PATTERN')

    def test_nfc_constructor_names_work_at_every_level(self):
        self.assertEqual(run('型 がた { がく } 型 箱 { 包む (値: がた) を } 場合 ((がく) を 包む) { ((か\u3099く) を 包む) なら { 7 } }'), [7])

    def test_only_selected_body_runs(self):
        stdout = io.StringIO()
        source = OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ((値 を 有り) を 有り) なら { (「ok」 を 表示する) } _ なら { (1 を 0 で 割る) (「bad」 を 表示する) } }'
        self.assertEqual(run(source, stdout=stdout), [None])
        self.assertEqual(stdout.getvalue(), 'ok\n')
        self.error(source, 'E_EFFECT', allow_io=False)
        self.error(OPTION + '手続き 入力 -> 選択<整数> { (無し<整数>) } 場合 (入力) { _ なら { 0 } }', 'E_EFFECT')

    def test_subject_is_evaluated_once_across_failed_arms(self):
        calls = []
        marker = Builtin('印', (), ValueType.UNIT, Effect.PURE, lambda args, context: calls.append('subject'))
        source = OPTION + '''場合 { (印) ((7 を 有り<整数>) を 有り<選択<整数>>) } {
            (無し) なら { 0 }
            ((無し) を 有り) なら { 1 }
            ((値 を 有り) を 有り) なら { 値 }
        }'''
        program = compile_source(source, functions={**BUILTINS, marker.name: marker})
        self.assertEqual(calls, [])
        self.assertEqual(execute(program), [7])
        self.assertEqual(calls, ['subject'])

    def test_all_arm_types_and_effects_are_checked_before_io(self):
        for suffix, code in [
            ('((値 を 有り) を 有り) なら { 値 } _ なら { 「bad」 }', 'E_BRANCH_TYPE'),
            ('((値 を 有り) を 有り) なら { 値 } _ なら { 不明 }', 'E_NAME'),
        ]:
            stdout = io.StringIO()
            self.error('(「early」 を 表示する)' + OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ' + suffix + ' }', code, stdout=stdout)
            self.assertEqual(stdout.getvalue(), '')

    def test_uncalled_incomplete_or_unreachable_match_prevents_io(self):
        for arms, code in [('((無し) を 有り) なら { 1 }', 'E_MATCH_EXHAUSTIVE'),
                           ('_ なら { 1 } (無し) なら { 2 }', 'E_PATTERN')]:
            stdin, stdout = io.StringIO('unused\n'), io.StringIO()
            self.error('(「early」 を 表示する) (読む)' + OPTION + '関数 不正 (値: 選択<選択<整数>>) を -> 整数 { 場合 値 { ' + arms + ' } }', code, stdin=stdin, stdout=stdout)
            self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_imported_patterns_share_identity_across_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'types.ten').write_text(OPTION)
            prefix = '取込 「types.ten」 と A。取込 「./types.ten」 と B。'
            source = prefix + '場合 ((7 を A.有り<整数>) を A.有り<A.選択<整数>>) { ((値 を B.有り) を A.有り) なら { 値 } _ なら { 0 } }'
            self.assertEqual(run(source, filename=str(root / 'main.ten')), [7])
            self.error(prefix + '場合 ((7 を A.有り<整数>) を A.有り<A.選択<整数>>) { ((値 を B.有り) を A.有り) なら { 値 } ((別 を A.有り) を B.有り) なら { 別 } _ なら { 0 } }', 'E_PATTERN', filename=str(root / 'main.ten'))

    def test_missing_pattern_diagnostic_uses_visible_module_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'types.ten').write_text(OPTION)
            error = self.error('取込 「types.ten」 と A。関数 不正 (値: A.選択<A.選択<整数>>) を -> 整数 { 場合 値 { (A.無し) なら { 0 } ((A.無し) を A.有り) なら { 1 } } }', 'E_MATCH_EXHAUSTIVE', filename=str(root / 'main.ten'))
            self.assertIn('((_ を A.有り) を A.有り)', error.message)

    def test_recursive_list_patterns_are_exhaustive_without_unfolding_type(self):
        source = LIST + '''
            関数 分類<T> (値: 一覧<T>) を -> 整数 {
                場合 値 {
                    (空) なら { 0 }
                    (_ を (空) に 節) なら { 1 }
                    (_ を (_ を _ に 節) に 節) なら { 2 }
                }
            }
            ((空<整数>) を 分類<整数>)
            ((1 を (空<整数>) に 節<整数>) を 分類<整数>)
            ((1 を (2 を (空<整数>) に 節<整数>) に 節<整数>) を 分類<整数>)
        '''
        self.assertEqual(run(source), [0, 1, 2])

    def test_recursive_types_without_base_constructor_remain_conservative(self):
        self.assertEqual(run('型 再帰型 { 次 (値: 再帰型) を } 関数 検査 (値: 再帰型) を -> 整数 { 場合 値 { ((残り を 次) を 次) なら { 0 } } }'), [])
        self.error('型 再帰型 { 次 (値: 再帰型) を } 関数 検査 (値: 再帰型) を -> 整数 { 場合 値 {} }', 'E_MATCH_EXHAUSTIVE')

    def test_matrix_analysis_matches_exhaustive_finite_domain_oracle(self):
        # Independent oracle: enumerate actual values, never compiler pattern IR.
        values = tuple(product(['赤', '青'], repeat=2))
        patterns = tuple(product(['赤', '青', '_'], repeat=2))
        for choices in product(patterns, repeat=3):
            covered, expected_error = set(), None
            for pattern in choices:
                matches = {value for value in values if all(p == '_' or p == v for p, v in zip(pattern, value))}
                if not matches - covered:
                    expected_error = 'E_PATTERN'
                    break
                covered.update(matches)
            if expected_error is None and len(covered) != len(values):
                expected_error = 'E_MATCH_EXHAUSTIVE'
            def field(name):
                return '_' if name == '_' else f'({name})'
            arms = ' '.join(f'({field(left)} を {field(right)} に 組) なら {{ {index} }}' for index, (left, right) in enumerate(choices))
            source = PAIR + '関数 分類 (値: 対) を -> 整数 { 場合 値 { ' + arms + ' } } '
            source += ' '.join(f'((({left}) を ({right}) に 組) を 分類)' for left, right in values)
            with self.subTest(patterns=choices):
                if expected_error:
                    self.error(source, expected_error)
                else:
                    expected = [next(i for i, pattern in enumerate(choices) if all(p == '_' or p == v for p, v in zip(pattern, value))) for value in values]
                    self.assertEqual(run(source), expected)

    def test_wide_deep_patterns_do_not_depend_on_python_recursion(self):
        depth = 115
        declaration = '型 木 { 枝 (A: 木) が (B: 木) を (C: 木) に (D: 木) で (E: 木) から (F: 木) へ (G: 木) と (H: 木) まで }'
        pattern = '_'
        for _ in range(depth):
            pattern = f'({pattern} が _ を _ に _ で _ から _ へ _ と _ まで 枝)'
        # Hundreds of pending fields exercise the iterative coverage work stack.
        self.assertEqual(run(declaration + '関数 検査 (値: 木) を -> 整数 { 場合 値 { ' + pattern + ' なら { 0 } } }'), [])

    def test_deep_runtime_pattern_retains_the_remaining_list(self):
        pattern = '残り'
        for _ in range(100):
            pattern = f'(_ を {pattern} に 節)'
        source = LIST + '''
            関数 作る (数: 整数) を -> 一覧<整数> {
                もし (数 と 0 が 等しい) なら { (空<整数>) }
                そうでなければ { (数 を ((数 から 1 を 引く) を 作る) に 節<整数>) }
            }
        ''' + '場合 (1000 を 作る) { ' + pattern + ' なら { 場合 残り { (数 を _ に 節) なら { 数 } (空) なら { 0 } } } _ なら { 0 } }'
        self.assertEqual(run(source), [900])

    def test_pattern_nesting_limit_has_language_diagnostic(self):
        pattern = '(' * MAX_NESTING + '_' + ' を 有り)' * MAX_NESTING
        self.error(OPTION + '場合 (無し<整数>) { ' + pattern + ' なら { 0 } _ なら { 1 } }', 'E_DEPTH')

    def test_complexity_limit_prevents_io(self):
        stdin, stdout = io.StringIO('unused\n'), io.StringIO()
        with patch('tenioha.patterns.MAX_COVERAGE_STATES', 1):
            self.error('(「early」 を 表示する) (読む)' + OPTION + '場合 (無し<整数>) { _ なら { 0 } }', 'E_MATCH_COMPLEXITY', stdin=stdin, stdout=stdout)
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))

    def test_new_matching_program_can_be_reexecuted(self):
        program = compile_source(OPTION + '場合 ((7 を 有り<整数>) を 有り<選択<整数>>) { ((値 を 有り) を 有り) なら { 値 } _ なら { 0 } }')
        self.assertEqual(execute(program), [7])
        self.assertEqual(execute(program), [7])

    def test_malformed_nested_patterns_are_diagnostics(self):
        for pattern in ['((無し) 有り)', '((無し) を)', '((無し) を 有り<整数>)', '()', 'A.名前', '(0 を 有り)', '(真 を 有り)', '(値 は 有り)']:
            with self.subTest(pattern=pattern):
                with self.assertRaises(Diagnostic):
                    compile_source(OPTION + '場合 (無し<整数>) { ' + pattern + ' なら { 0 } }')


if __name__ == '__main__':
    unittest.main()

import io
from itertools import permutations
from pathlib import Path
import tempfile
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.core import format_value
from tenioha.syntax import MAX_NESTING, PARTICLES, Source, tokenize


class CompactReaderTests(unittest.TestCase):
    def error(self, source, code, **options):
        with self.assertRaises(Diagnostic) as caught:
            run(source, **options)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_all_integer_particles_and_signed_decimal_forms(self):
        for particle in PARTICLES:
            for digits, value in [('7', 7), ('-7', -7), ('0007', 7), ('-0007', -7), ('-0', 0)]:
                with self.subTest(particle=particle, digits=digits):
                    source = f'関数 保つ (値:整数){particle} -> 整数 {{ 値 }} ({digits}{particle} 保つ)'
                    self.assertEqual(run(source), [value])

    def test_integer_and_normalized_particle_keep_separate_original_spans(self):
        text = '; comment\n(-0007か\u3099)'
        tokens = tokenize(Source(text, 'compact.ten'))
        number, particle = tokens[1:3]
        self.assertEqual((number.kind, number.value, particle.kind, particle.value),
                         ('INTEGER', -7, 'PARTICLE', 'が'))
        self.assertEqual(text[number.span.start:number.span.end], '-0007')
        self.assertEqual(text[particle.span.start:particle.span.end], 'か\u3099')
        self.assertEqual(number.span.end, particle.span.start)
        self.assertEqual((particle.span.line, particle.span.column), (2, 7))

    def test_large_compact_integer_and_digit_limit(self):
        digits = '9' * 4096
        self.assertEqual(run(f'({digits}を 文字列にする)'), [digits])
        self.assertEqual(format_value(run(f'(-{digits}に 0を 足す)')[0]), '-' + digits)
        source = '(' + '9' * 4097 + 'か\u3099 保つ)'
        error = self.error(source, 'E_INTEGER')
        self.assertEqual(source[error.span.start:error.span.end], '9' * 4097)

    def test_invalid_numeric_forms_and_nonparticle_suffixes_remain_errors(self):
        for word in ['5から引く', '5から3を', '5からから', '5は', '5なら', '5の',
                     '5e2', '5_0', '0x10', '+5を', '--5を', '-５を', '５を', '5.0', '5.0を']:
            with self.subTest(word=word):
                self.error(word, 'E_TOKEN')

    def test_identifier_words_are_never_split(self):
        words = ['値を', 'たから', '真を', '偽が', 'を表示する', 'から3', 'x5から', '関数名', '整数を']
        tokens = tokenize(Source(' '.join(words)))
        self.assertEqual([(t.kind, t.value) for t in tokens[:-1]], [('NAME', word) for word in words])
        self.assertEqual(run('値を は 7。真を は 9。(値を から 真を を 引く)'), [None, None, -2])
        self.assertEqual(run('(真 を 否定する)'), [False])
        self.error('(真を 否定する)', 'E_PARTICLE')

    def test_particle_needs_a_boundary_before_a_following_word(self):
        self.error('(5から3を引く)', 'E_TOKEN')
        self.error('(「猫」を表示する)', 'E_PARTICLE')
        self.error('((読む)を表示する)', 'E_PARTICLE')

    def test_strings_and_comments_are_unchanged(self):
        text = '5から3を引く;「 はか\u3099 ( )'
        self.assertEqual(run(f'「{text}」'), [text])
        self.assertEqual(run('(5から; 「ignored」\n3を 引く)'), [2])
        self.assertEqual(run(r'(「猫\」\n」と「犬」を 連結する)'), ['猫」\n犬'])

    def test_spaced_and_compact_forms_have_the_same_tokens(self):
        for spaced, compact in [
            ('(5 から 3 を 引く)', '(5から 3を 引く)'),
            ('(「前」 と 「後」 を 連結する)', '(「前」と「後」を 連結する)'),
            ('((5 から 3 を 引く) に 4 を 足す)', '((5から 3を 引く)に 4を 足す)'),
            ('関数 保つ (値: 整数) を -> 整数 { 値 }', '関数 保つ(値:整数)を->整数{値}'),
            ('関数[一覧<整数> を -> 整数]', '関数[一覧<整数>を->整数]'),
        ]:
            with self.subTest(compact=compact):
                signature = lambda source: [(t.kind, t.value) for t in tokenize(Source(source))]
                self.assertEqual(signature(spaced), signature(compact))

    def test_argument_permutations_preserve_noncommutative_roles(self):
        self.assertEqual(run('(5から 3を 引く)(3を 5から 引く)(3から 5を 引く)'), [2, 2, -2])
        source = '関数 組む (千:整数)から (百:整数)を (十:整数)に (一:整数)で -> 整数 { (((千 に 1000を 掛ける)に (百 に 100を 掛ける)を 足す)に ((十 に 10を 掛ける)に 一 を 足す)を 足す) } '
        for ordering in permutations(['1から', '2を', '3に', '4で']):
            self.assertEqual(run(source + f'({" ".join(ordering)} 組む)'), [1234])

    def test_adjacent_delimited_arguments_and_nested_calls(self):
        self.assertEqual(run('(「前」と「後」を 連結する)'), ['前後'])
        self.assertEqual(run('((5から 3を 引く)に(9から 5を 引く)を 足す)'), [6])
        self.assertEqual(run('(5から{3}を 引く)'), [2])

    def test_block_conditional_and_match_results_accept_adjacent_particles(self):
        self.assertEqual(run('({5}から 3を 引く)'), [2])
        self.assertEqual(run('(もし 真 なら{5}そうでなければ{9}から 3を 引く)'), [2])
        self.assertEqual(run('型 色{赤。青}(場合 (赤){(赤)なら{5}(青)なら{9}}から 3を 引く)'), [2])

    def test_compact_constructor_fields_and_nested_patterns(self):
        source = '''型 選択<T>{無し。有り(値:T)を}
            場合 ((7を 有り<整数>)を 有り<選択<整数>>){
                ((値 を 有り)を 有り)なら{値}
                _ なら{0}
            }'''
        self.assertEqual(run(source), [7])

    def test_generic_function_reference_and_delimited_function_types(self):
        source = '''関数 保つ<T>(値:T)を->T{値}
            関数 呼ぶ(操作:関数[整数 を->整数])で->整数{(7を 適用 操作)}
            (参照 保つ<整数>で 呼ぶ)'''
        self.assertEqual(run(source), [7])
        source = '''関数 二重(外:関数[関数[整数 を->整数]で->整数])を->整数{
                (関数(値:整数)を->整数{値}で 適用 外)
            }
            (関数(内:関数[整数 を->整数])で->整数{(9を 適用 内)}を 二重)'''
        self.assertEqual(run(source), [9])

    def test_generic_data_in_compact_function_type(self):
        source = '''型 箱<T>{包む(値:T)を}
            関数 呼ぶ(操作:関数[箱<整数>を->整数])で->整数{((7を 包む<整数>)を 適用 操作)}
            (関数(箱値:箱<整数>)を->整数{場合 箱値{(値 を 包む)なら{値}}}で 呼ぶ)'''
        self.assertEqual(run(source), [7])

    def test_closure_capture_and_indirect_application(self):
        source = '''関数 加算器(増分:整数)で->関数[整数 を->整数]{
                関数(値:整数)を->整数{(値 に 増分 を 足す)}
            }
            操作 は (10で 加算器)。{増分 は 100。(5を 適用 操作)}'''
        self.assertEqual(run(source), [None, 15])

    def test_compact_modules_and_qualified_generic_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'helper.ten').write_text('関数 保つ<T>(値:T)を->T{値}', encoding='utf-8')
            source = '取込「helper.ten」と 助。(7を 適用 参照 助.保つ<整数>)'
            self.assertEqual(run(source, filename=str(root / 'main.ten')), [7])

    def test_effect_errors_prevent_earlier_output_and_input(self):
        stdin, stdout = io.StringIO('Ada\n'), io.StringIO()
        source = '(「early」を 表示する)((読む)を 表示する)'
        self.error(source, 'E_EFFECT', stdin=stdin, stdout=stdout)
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ''))
        self.error('(「猫」を 表示する)', 'E_EFFECT', allow_io=False)

    def test_compact_procedure_has_ordered_io(self):
        stdin, stdout = io.StringIO('Ada\n'), io.StringIO()
        source = '手続き 挨拶->単位{名前 は (読む)。((「こんにちは、」と 名前 を 連結する)を 表示する)}(挨拶)'
        self.assertEqual(run(source, stdin=stdin, stdout=stdout), [None])
        self.assertEqual(stdout.getvalue(), 'こんにちは、Ada\n')
        self.assertEqual(stdin.read(), '')

    def test_original_type_and_particle_error_locations(self):
        source = '; header\n(「猫」から 3を 引く)'
        error = self.error(source, 'E_TYPE', filename='compact.ten')
        self.assertEqual((error.span.line, error.span.column), (2, 2))
        self.assertEqual(error.render().splitlines()[-1], '   ^^^^^^')
        source = '(3に 5に 足す)'
        self.assertEqual(self.error(source, 'E_ARGUMENTS').span.start, source.rindex('に'))
        source = '(3か\u3099 5が 等しい)'
        error = self.error(source, 'E_ARGUMENTS')
        self.assertEqual(error.span.start, source.index('が'))
        self.assertIn('duplicate: が', error.message)

    def test_wrong_compact_particle_has_no_implicit_alias(self):
        self.error('(1へ 2を 足す)', 'E_ARGUMENTS')
        self.error('(「猫」は 表示する)', 'E_RESERVED')
        self.error('関数 保つ(値:整数)は->整数{値}', 'E_SYNTAX')

    def test_runtime_exception_order_is_still_canonical(self):
        for source in ['((1を 0で 割る)から(2を 0で 割る)を 引く)',
                       '((2を 0で 割る)を(1を 0で 割る)から 引く)']:
            error = self.error(source, 'E_ZERO_DIVISION')
            self.assertEqual(error.span.start, source.index('割る', source.index('(1を')))

    def test_nfc_names_and_particle_spans(self):
        source = '関数 か\u3099く(値:整数)か\u3099->整数{値}(7か\u3099 がく)'
        self.assertEqual(run(source), [7])
        source = '(3と 3か\u3099 等しい)'
        self.assertEqual(run(source), [True])

    def test_fullwidth_whitespace_is_supported_but_not_punctuation(self):
        self.assertEqual(run('(5から　3を　引く)'), [2])
        for source in ['（5から 3を 引く）', '－5を', '１２から', '｛5｝から']:
            with self.subTest(source=source):
                self.error(source, 'E_TOKEN')

    def test_compact_nesting_retains_depth_limit(self):
        source = '(' * MAX_NESTING + '0' + 'に 1を 足す)' * MAX_NESTING
        self.assertEqual(run(source), [MAX_NESTING])
        self.error('(' + source + 'に 1を 足す)', 'E_DEPTH')

    def test_compiled_compact_program_can_be_reused(self):
        program = compile_source('値 は 5。(値 から 3を 引く)')
        self.assertEqual(execute(program), [None, 2])
        self.assertEqual(execute(program), [None, 2])


if __name__ == '__main__':
    unittest.main()

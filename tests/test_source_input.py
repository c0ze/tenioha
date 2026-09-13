import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tenioha import Diagnostic, run
from tenioha.__main__ import main
from tenioha.syntax import Source, tokenize


LINE_ENDINGS = ("\n", "\r\n", "\r", "\u0085", "\u2028", "\u2029")
ROOT = Path(__file__).resolve().parents[1]


class SourceInputTests(unittest.TestCase):
    def test_initial_bom_in_embedding_preserves_token_offsets(self):
        source = Source("\ufeff(3 を 5 から 引く)")
        self.assertEqual(run(source.text), [2])
        self.assertEqual(tokenize(source)[0].span.start, 1)
        self.assertEqual(run("\ufeff"), [])
        for text in ["\ufeff\ufeff1", "1 \ufeff"]:
            with self.subTest(text=text), self.assertRaises(Diagnostic) as caught:
                run(text)
            self.assertEqual(caught.exception.code, "E_TOKEN")

    def test_comments_end_on_each_supported_line_break(self):
        for ending in LINE_ENDINGS:
            with self.subTest(ending=repr(ending)):
                self.assertEqual(run('; ignored' + ending + '(3 を 5 から 引く)'), [2])
                self.assertEqual(run('; ignored' + ending + '; also ignored' + ending + '7'), [7])
        self.assertEqual(run('; fullwidth space\u3000(3 を 5 から 引く)'), [])

    def test_line_breaks_and_bom_inside_strings_are_unchanged(self):
        content = "\ufeff;" + "".join(LINE_ENDINGS)
        self.assertEqual(run("「" + content + "」"), [content])

    def test_diagnostic_locations_use_the_same_line_breaks_as_comments(self):
        for ending in LINE_ENDINGS:
            with self.subTest(ending=repr(ending)):
                source = '; ignored' + ending + '(3に 5に 足す)'
                with self.assertRaises(Diagnostic) as caught:
                    run(source)
                error = caught.exception
                self.assertEqual((error.code, error.span.line, error.span.column), ("E_ARGUMENTS", 2, 6))
                self.assertEqual(source[error.span.start:error.span.end], "に")
                self.assertEqual(error.render().splitlines()[1:], ['  (3に 5に 足す)', '        ^^'])

    def test_mixed_line_breaks_count_crlf_once_and_track_eof(self):
        source = '; first\r\n; second\u2028; third\r; fourth\n'
        end = tokenize(Source(source))[-1].span
        self.assertEqual((end.line, end.column), (5, 1))
        with self.assertRaises(Diagnostic) as caught:
            run(source + '(')
        self.assertEqual((caught.exception.span.line, caught.exception.span.column), (5, 1))

    def test_bom_diagnostic_keeps_original_column_and_visible_caret(self):
        with self.assertRaises(Diagnostic) as caught:
            run('\ufeff(3に 5に 足す)')
        error = caught.exception
        self.assertEqual((error.span.line, error.span.column), (1, 7))
        self.assertEqual(error.render().splitlines()[-1], '        ^^')

    def test_cli_eval_and_file_agree_on_unicode_line_breaks_and_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.ten'
            for ending in LINE_ENDINGS:
                with self.subTest(ending=repr(ending)):
                    source = '\ufeff; ignored' + ending + '(「猫」を 表示する)'
                    path.write_bytes(source.encode('utf-8'))
                    for args in [('--eval', source), (str(path),)]:
                        result = subprocess.run([sys.executable, '-m', 'tenioha', *args], cwd=ROOT,
                                                text=True, capture_output=True, timeout=10)
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '猫\n', ''))

    def test_entry_filename_error_is_reported_without_traceback(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(['bad\0name.ten'])
        self.assertEqual(code, 1)
        self.assertIn('tenioha:', stderr.getvalue())
        self.assertNotIn('Traceback', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_site import ROOT, build

spec = importlib.util.spec_from_file_location("playground_runner", ROOT / "site/runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PlaygroundTests(unittest.TestCase):
    def run_source(self, source, input_text="", check_only=False, filename="playground.ten"):
        return json.loads(runner.run_playground(source, input_text, check_only, filename))

    def test_run_echoes_values_and_reads_supplied_input(self):
        result = self.run_source('名前 は (読む)。(名前 を 表示する)(5から 3を 引く)', 'Ada\n')
        self.assertEqual(result, {"ok": True, "output": "Ada\n2\n", "error": ""})

    def test_check_never_executes_io_or_runtime_failures(self):
        result = self.run_source('(読む)(「unseen」を 表示する)(1を 0で 割る)', check_only=True)
        self.assertTrue(result["ok"])
        self.assertIn("No program code was executed", result["output"])
        self.assertNotIn("unseen", result["output"])

    def test_static_errors_prevent_output_but_runtime_errors_preserve_it(self):
        static = self.run_source('(「early」を 表示する)(3に 5に 足す)')
        self.assertFalse(static["ok"])
        self.assertEqual(static["output"], "")
        self.assertIn("E_ARGUMENTS", static["error"])
        runtime = self.run_source('(「early」を 表示する)(1を 0で 割る)')
        self.assertFalse(runtime["ok"])
        self.assertEqual(runtime["output"], "early\n")
        self.assertIn("E_ZERO_DIVISION", runtime["error"])

    def test_missing_input_and_fresh_bindings(self):
        self.assertIn("E_IO", self.run_source('(読む)')["error"])
        self.assertTrue(self.run_source('値 は 3。')["ok"])
        self.assertIn("E_NAME", self.run_source('値')["error"])

    def test_output_and_input_limits(self):
        result = self.run_source('(「' + 'x' * runner.MAX_OUTPUT + '」を 表示する)')
        self.assertFalse(result["ok"])
        self.assertEqual(result["output"], 'x' * runner.MAX_OUTPUT)
        self.assertIn("64,000", result["error"])
        self.assertFalse(self.run_source(' ' * (runner.MAX_SOURCE + 1))["ok"])
        self.assertFalse(self.run_source('', 'x' * (runner.MAX_INPUT + 1))["ok"])

    def test_program_is_data_not_host_python(self):
        result = self.run_source('__import__(「os」)')
        self.assertFalse(result["ok"])
        literal = '「<script>alert(1)</script>」'
        self.assertEqual(self.run_source(literal)["output"], '<script>alert(1)</script>\n')

    def test_build_bundles_actual_sources_and_every_example(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dist"
            count = build(target)
            catalog = json.loads((target / "examples.json").read_text())
            self.assertEqual(count, len(list((ROOT / "examples").glob("*.ten"))))
            self.assertEqual({item["id"] for item in catalog}, {path.stem for path in (ROOT / "examples").glob("*.ten")})
            for item in catalog:
                path = ROOT / "examples" / f'{item["id"]}.ten'
                self.assertEqual(item["source"], path.read_bytes().decode("utf-8"))
                result = self.run_source(item["source"], item["input"], filename=str(path))
                self.assertTrue(result["ok"], result["error"])
                self.assertEqual(result["output"], item["expected"])
            runtime = json.loads((target / "runtime.json").read_text())
            self.assertEqual(runtime["files"]["tenioha/core.py"], (ROOT / "tenioha/core.py").read_text())
            self.assertEqual(runtime["files"]["runner.py"], (ROOT / "site/runner.py").read_text())
            self.assertIn("lib/list.ten", runtime["files"])
            self.assertIn("lib/option.ten", runtime["files"])
            self.assertNotIn("{{VERSION}}", (target / "index.html").read_text())
            self.assertFalse((target / "HANDOFF.md").exists())
            self.assertFalse((target / ".tincan").exists())


if __name__ == "__main__":
    unittest.main()

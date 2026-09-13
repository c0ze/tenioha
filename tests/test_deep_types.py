import io
import unittest

from tenioha import Diagnostic, compile_source, execute, run
from tenioha.typesys import DataType, Effect, FunctionType, TypeVariable, ValueType, substitute


def boxes(depth, leaf="T"):
    return "箱<" * depth + leaf + ">" * depth


def composed_types():
    return f"""
        型 箱<T> {{ 空 }}
        関数 作る<T> -> {boxes(110)} {{ (空<{boxes(109)}>) }}
        関数 複写<T> (値:T)を -> T {{ 値 }}
        関数 取得<T> -> 関数[{boxes(110)} を -> {boxes(110)}] {{ 参照 複写<{boxes(110)}> }}
        値 は (作る<{boxes(110, '整数')}>)。
        操作 は (取得<{boxes(110, '整数')}>)。
    """


class DeepTypeTests(unittest.TestCase):
    def test_substitution_of_deep_types_preserves_choices_effects_and_variable_owners(self):
        variable = TypeVariable("T", "factory")
        other = TypeVariable("T", "unrelated")
        kind = variable
        for _ in range(600):
            kind = DataType("box", (kind,), "箱")
        function = FunctionType((("へ", kind), ("を", other)), kind, Effect.IO, aliases=(("に",), ()))
        result = substitute(function, {variable: ValueType.INTEGER})
        self.assertEqual(result.result_type.value, boxes(600, "整数"))
        self.assertEqual(result.parameters[0][1], result.result_type)
        self.assertEqual(result.parameters[1][1], other)
        self.assertEqual((result.aliases, result.effect), ((("へ",), ()), Effect.IO))

    def test_composed_generic_types_compare_inside_deep_blocks(self):
        program = compile_source(composed_types() + "{" * 125 + "(値 を 適用 操作)" + "}" * 125)
        self.assertEqual(program.expressions[-1].value_type.value, boxes(220, "整数"))
        self.assertEqual(len(execute(program)), 3)

    def test_deep_type_error_remains_a_diagnostic_before_io(self):
        source = '(「early」を 表示する)(読む)' + composed_types()
        source += "{" * 125 + "(値 に 1 を 足す)" + "}" * 125
        stdin, stdout = io.StringIO("unused\n"), io.StringIO()
        with self.assertRaises(Diagnostic) as caught:
            run(source, stdin=stdin, stdout=stdout)
        self.assertEqual(caught.exception.code, "E_TYPE")
        self.assertIn(boxes(220, "整数"), caught.exception.message)
        self.assertEqual((stdin.tell(), stdout.getvalue()), (0, ""))

    def test_structural_type_equality_hashing_and_display_are_iterative(self):
        left = right = ValueType.INTEGER
        different = ValueType.STRING
        display = "整数"
        for depth in range(600):
            if depth % 2:
                left = FunctionType((("に", ValueType.INTEGER),), left, Effect.PURE, aliases=(("へ",),))
                right = FunctionType((("へ", ValueType.INTEGER),), right, Effect.PURE, aliases=(("に",),))
                different = FunctionType((("に", ValueType.INTEGER),), different, Effect.PURE, aliases=(("へ",),))
                display = f"関数[整数 に|へ -> {display}]"
            else:
                left = DataType("box", (left,), "箱")
                right = DataType("box", (right,), "別の表示名")
                different = DataType("box", (different,), "箱")
                display = f"箱<{display}>"
        self.assertEqual(left, right)
        self.assertNotEqual(left, different)
        self.assertEqual(hash(left), hash(right))
        self.assertEqual(len({left, right, different}), 2)
        self.assertEqual(left.value, display)


if __name__ == "__main__":
    unittest.main()

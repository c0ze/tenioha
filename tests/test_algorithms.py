import io
import math
import random
from pathlib import Path
import unittest

from tenioha import run

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def evaluate(name, calls):
    path = EXAMPLES / f"{name}.ten"
    source = path.read_text(encoding="utf-8")
    # The filename resolves an example's relative imports, as the CLI does.
    return run(source + "\n" + "\n".join(calls), filename=str(path), stdout=io.StringIO())[-len(calls):]


class AlgorithmTests(unittest.TestCase):
    def test_fibonacci_including_zero_and_larger_index(self):
        indices = [0, 1, 2, 10, 20, 30]
        self.assertEqual(evaluate("fibonacci", [f"({n}を フィボナッチ)" for n in indices]),
                         [0, 1, 1, 55, 6765, 832040])

    def test_fizzbuzz_each_branch_and_range(self):
        expected = ["FizzBuzz" if n % 15 == 0 else "Fizz" if n % 3 == 0 else
                    "Buzz" if n % 5 == 0 else str(n) for n in range(1, 101)]
        self.assertEqual(evaluate("fizzbuzz", [f"({n}を 判定)" for n in range(1, 101)]), expected)

    def test_primes_against_independent_small_domain(self):
        expected = [n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1)) for n in range(101)]
        self.assertEqual(evaluate("primes", [f"({n}を 素数か)" for n in range(101)]), expected)

    def test_gcd_including_zero_and_reversed_arguments(self):
        pairs = [(0, 0), (0, 12), (12, 0), (18, 48), (48, 18), (1071, 462), (17, 31), (100, 100)]
        self.assertEqual(evaluate("gcd", [f"({a}と {b}で 最大公約数)" for a, b in pairs]),
                         [math.gcd(a, b) for a, b in pairs])

    def test_collatz_step_for_even_and_odd_positive_numbers(self):
        self.assertEqual(evaluate("collatz", [f"({n}を 次の数)" for n in range(1, 51)]),
                         [n // 2 if n % 2 == 0 else 3 * n + 1 for n in range(1, 51)])

    def test_power_including_zero_exponent_and_zero_base(self):
        cases = [(base, exponent) for base in (0, 1, 2, 3, 5, 7, 10) for exponent in range(13)]
        self.assertEqual(evaluate("power", [f"({b}を {e}で べき乗)" for b, e in cases]),
                         [b ** e for b, e in cases])

    def test_binary_matches_python_formatting_including_zero(self):
        numbers = list(range(130)) + [255, 256, 1023, 4096]
        self.assertEqual(evaluate("binary", [f"({n}を 二進)" for n in numbers]),
                         [format(n, "b") for n in numbers])

    def test_reversed_digits_and_palindrome_agree_with_string_reversal(self):
        numbers = list(range(200)) + [90, 1111, 12321, 12345, 1002001]
        reversed_digits = [int(str(n)[::-1]) for n in numbers]
        self.assertEqual(evaluate("palindrome", [f"({n}を 逆順)" for n in numbers]), reversed_digits)
        self.assertEqual(evaluate("palindrome", [f"({n}を 回文か)" for n in numbers]),
                         [n == r for n, r in zip(numbers, reversed_digits)])

    def test_times_table_rows_hold_every_product(self):
        self.assertEqual(evaluate("times_table", [f"({d}に 2を ({d}を 文字列にする)で 行)" for d in range(1, 10)]),
                         [" ".join(str(d * c) for c in range(1, 10)) for d in range(1, 10)])

    def test_less_than_holds_across_nonnegative_pairs(self):
        pairs = [(left, right) for left in range(25) for right in range(25)]
        self.assertEqual(evaluate("sort", [f"({a} が {b} で 未満)" for a, b in pairs]),
                         [a < b for a, b in pairs])

    def test_insertion_sort_orders_random_lists_including_duplicates(self):
        def literal(values):
            source = "(列.空<整数>)"
            for value in reversed(values):
                source = f"({value} を {source} に 列.節<整数>)"
            return source

        generator = random.Random(7)
        lists = [[]] + [[generator.randrange(60) for _ in range(generator.randrange(1, 9))] for _ in range(40)]
        self.assertEqual(evaluate("sort", [f"(({literal(values)} を 整列) を 連ねる)" for values in lists]),
                         [" ".join(str(v) for v in sorted(values)) if values else "空" for values in lists])


if __name__ == "__main__":
    unittest.main()

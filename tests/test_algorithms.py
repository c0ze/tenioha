import io
import math
from pathlib import Path
import unittest

from tenioha import run

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def evaluate(name, calls):
    source = (EXAMPLES / f"{name}.ten").read_text(encoding="utf-8")
    return run(source + "\n" + "\n".join(calls), stdout=io.StringIO())[-len(calls):]


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


if __name__ == "__main__":
    unittest.main()

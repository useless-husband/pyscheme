"""examples/*.scm 全部跑完,輸出必須和 tests/expected/*.txt 完全一致 (透過真正的命令列執行)。"""
import subprocess
import sys
import unittest

from tests.helpers import ROOT

EXAMPLES = sorted((ROOT / "examples").glob("*.scm"))


class ExampleTests(unittest.TestCase):
    def test_all_examples_exist(self):
        names = {p.stem for p in EXAMPLES}
        self.assertEqual(names, {"fizzbuzz", "factorial", "queens", "stream-primes",
                                 "generator", "metacircular"})

    def test_outputs(self):
        for p in EXAMPLES:
            with self.subTest(example=p.name):
                r = subprocess.run([sys.executable, "-m", "pyscheme", str(p)],
                                   capture_output=True, text=True, cwd=ROOT, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr)
                expected = (ROOT / "tests" / "expected" / f"{p.stem}.txt").read_text(encoding="utf-8")
                self.assertEqual(r.stdout, expected)

    def test_key_facts(self):
        out = {p.stem: (ROOT / "tests" / "expected" / f"{p.stem}.txt").read_text(encoding="utf-8")
               for p in EXAMPLES}
        self.assertIn("FizzBuzz", out["fizzbuzz"])
        self.assertIn("93326215443944152681699238856266700490715968264381621468592963895217599993"
                      "229915608941463976156518286253697920827223758251185210916864000000000000000000000000",
                      out["factorial"])
        self.assertIn("92 種解", out["queens"])
        self.assertIn("541", out["stream-primes"])
        self.assertIn("(fib 15)  =>  610", out["metacircular"])


if __name__ == "__main__":
    unittest.main()

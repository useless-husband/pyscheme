import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT


def cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "pyscheme", *args], input=stdin,
                          capture_output=True, text=True, cwd=ROOT, timeout=60)


class CliTests(unittest.TestCase):
    def test_eval_flag(self):
        r = cli("-e", "(* 6 7)")
        self.assertEqual((r.returncode, r.stdout), (0, "42\n"))

    def test_run_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hello.scm"
            p.write_text('(display "你好, Scheme")\n(newline)\n', encoding="utf-8")
            r = cli(str(p))
        self.assertEqual((r.returncode, r.stdout), (0, "你好, Scheme\n"))

    def test_file_error_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.scm"
            p.write_text('(display "before")\n(car 5)\n', encoding="utf-8")
            r = cli(str(p))
        self.assertEqual(r.returncode, 1)
        self.assertIn("before", r.stdout)
        self.assertIn("expected pair", r.stderr)

    def test_missing_file(self):
        r = cli("/nonexistent/file.scm")
        self.assertEqual(r.returncode, 2)
        self.assertIn("無法讀取", r.stderr)

    def test_stdin_repl(self):
        r = cli(stdin="(define (sq x) (* x x))\n(sq 12)\n(sq\n 3)\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "144\n9\n")

    def test_exit_code_from_scheme(self):
        self.assertEqual(cli("-e", "(exit 7)").returncode, 7)

    def test_version(self):
        r = cli("--version")
        self.assertIn("pyscheme", r.stdout)

    def test_interactive_after_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "defs.scm"
            p.write_text("(define answer 42)\n", encoding="utf-8")
            r = cli("-i", str(p), stdin="answer\n")
        self.assertEqual(r.stdout, "42\n")


if __name__ == "__main__":
    unittest.main()

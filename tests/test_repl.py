import io
import unittest

from pyscheme.repl import Repl


def session(lines):
    it = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    out, err = io.StringIO(), io.StringIO()
    code = Repl(input_fn=fake_input, out=out, err=err, interactive=False).run()
    return code, out.getvalue(), err.getvalue()


class ReplTests(unittest.TestCase):
    def test_prints_values(self):
        _, out, _ = session(["(+ 1 2)", '"hi"', "'(a . b)"])
        self.assertEqual(out, '3\n"hi"\n(a . b)\n')

    def test_define_prints_nothing(self):
        _, out, _ = session(["(define x 1)", "x"])
        self.assertEqual(out, "1\n")

    def test_multiline(self):
        _, out, err = session(["(define (fact n)", "  (if (= n 0)", "      1", "      (* n (fact (- n 1)))))",
                               "(fact 5)"])
        self.assertEqual(out, "120\n")
        self.assertEqual(err, "")

    def test_multiline_string(self):
        _, out, _ = session(['(display "a', 'b")'])
        self.assertEqual(out, "a\nb\n")

    def test_error_does_not_end_repl(self):
        _, out, err = session(["(car 5)", "undefined", "(+ 1 1)"])
        self.assertEqual(out, "2\n")
        self.assertIn("expected pair", err)
        self.assertIn("unbound variable: undefined", err)

    def test_read_error_recovers(self):
        _, out, err = session(["(+ 1 2))", "(+ 3 4)"])
        self.assertIn("line 1", err)
        self.assertIn("7", out)

    def test_state_survives_error(self):
        _, out, _ = session(["(define x 10)", "(error \"boom\")", "x"])
        self.assertEqual(out, "10\n")

    def test_help_and_quit(self):
        code, out, _ = session([",help", "(display 1)", ",quit", "(display 2)"])
        self.assertIn(",load", out)
        self.assertIn("1", out)
        self.assertNotIn("2", out.replace(",load", ""))
        self.assertEqual(code, 0)

    def test_unknown_command(self):
        _, _, err = session([",bogus"])
        self.assertIn("不認得的指令", err)

    def test_expand_command(self):
        _, out, _ = session(["(define-syntax inc! (syntax-rules () ((_ v) (set! v (+ v 1)))))",
                             ",expand (inc! n)"])
        self.assertEqual(out.strip(), "(set! n (+ n 1))")

    def test_env_and_reset(self):
        _, out, _ = session(["(define zzz 1)", ",env", ",reset", ",env"])
        self.assertIn("zzz", out)
        self.assertIn("還沒有自己定義", out)

    def test_exit_code(self):
        code, _, _ = session(["(exit 4)"])
        self.assertEqual(code, 4)

    def test_output_then_value_on_new_line(self):
        _, out, _ = session(['(begin (display "x") 5)'])
        self.assertEqual(out, "x\n5\n")

    def test_load_command(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".scm", delete=False) as f:
            f.write("(define loaded 99)")
        try:
            _, out, _ = session([f",load {f.name}", "loaded"])
            self.assertIn("99", out)
        finally:
            os.unlink(f.name)

    def test_time_command(self):
        _, out, _ = session([",time (+ 1 2)"])
        self.assertIn("3", out)
        self.assertIn("秒", out)


if __name__ == "__main__":
    unittest.main()

import unittest

from pyscheme import Interpreter, SchemeError
from pyscheme.errors import SchemeExit
from tests.helpers import run, value


class InterpreterTests(unittest.TestCase):
    def test_million_tail_calls(self):
        self.assertEqual(value("(define (loop n) (if (= n 0) 'done (loop (- n 1)))) (loop 1000000)"),
                         "done")

    def test_million_iterations_do_and_named_let(self):
        self.assertEqual(value("(do ((i 0 (+ i 1))) ((= i 1000000) i))"), "1000000")
        self.assertEqual(value("(let lp ((i 0) (s 0)) (if (= i 1000000) s (lp (+ i 1) (+ s 1))))"),
                         "1000000")

    def test_mutual_tail_recursion(self):
        src = """(define (ev? n) (if (= n 0) #t (od? (- n 1))))
                 (define (od? n) (if (= n 0) #f (ev? (- n 1))))
                 (ev? 1000001)"""
        self.assertEqual(value(src), "#f")

    def test_deep_non_tail_recursion(self):
        self.assertEqual(value("(define (f n) (if (= n 0) 0 (+ 1 (f (- n 1))))) (f 200000)"), "200000")

    def test_python_stack_not_used(self):
        import sys
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            self.assertEqual(value("(define (f n) (if (= n 0) 0 (+ 1 (f (- n 1))))) (f 20000)"),
                             "20000")
        finally:
            sys.setrecursionlimit(old)

    def test_depth_limit(self):
        it = Interpreter()
        it.max_depth = 5000
        with self.assertRaises(SchemeError) as cm:
            it.run_string("(define (f n) (+ 1 (f n))) (f 0)")
        self.assertIn("recursion depth exceeded", str(cm.exception))
        self.assertIn("遞迴太深", str(cm.exception))
        # 撞到上限後直譯器仍然可用
        self.assertEqual(run("(+ 1 2)", it)[0], "3")

    def test_uncaught_raise_and_error_object(self):
        with self.assertRaises(SchemeError) as cm:
            Interpreter().run_string("(raise 'oops)")
        self.assertEqual(str(cm.exception.payload), "oops")
        with self.assertRaises(SchemeError) as cm:
            Interpreter().run_string('(error "Something bad:" 42 "s")')
        self.assertEqual(str(cm.exception), 'Something bad: 42 "s"')

    def test_error_messages_bilingual(self):
        cases = [("(car 5)", "expected pair", "序對"),
                 ("undefined-thing", "unbound variable: undefined-thing", "未定義的變數"),
                 ("((lambda (x) x))", "expects 1 argument", "需要 1 個參數"),
                 ("(+ 'a 1)", "expected number", "數字"),
                 ("(1 2)", "not a procedure", "不是程序")]
        for src, en, zh in cases:
            with self.subTest(src=src):
                with self.assertRaises(SchemeError) as cm:
                    Interpreter().run_string(src)
                self.assertIn(en, str(cm.exception))
                self.assertIn(zh, str(cm.exception))

    def test_syntax_errors_at_analysis(self):
        for src in ("(if)", "(let ((1 2)) 3)", "(lambda (1) 1)", "(define)", "(quote)"):
            with self.subTest(src=src):
                with self.assertRaises(SchemeError):
                    Interpreter().run_string(src)

    def test_exit(self):
        with self.assertRaises(SchemeExit) as cm:
            Interpreter().run_string("(exit 3)")
        self.assertEqual(cm.exception.code, 3)

    def test_state_persists_between_calls(self):
        it = Interpreter()
        it.run_string("(define x 5)")
        self.assertEqual(run("(* x 2)", it)[0], "10")

    def test_fresh_interpreters_are_isolated(self):
        Interpreter().run_string("(define leaked 1)")
        with self.assertRaises(SchemeError):
            Interpreter().run_string("leaked")

    def test_macroexpand_1(self):
        from pyscheme.reader import read_one
        from pyscheme.printer import to_string
        it = Interpreter()
        it.run_string("(define-syntax inc! (syntax-rules () ((_ v) (set! v (+ v 1)))))")
        out = it.analyzer.macroexpand_1(read_one("(inc! x)"))
        self.assertEqual(to_string(out, True), "(set! x (+ x 1))")

    def test_output_order_with_side_effects(self):
        self.assertEqual(run('(display 1) (display "-") (display (+ 1 1))')[1], "1-2")

    def test_big_list_gc(self):
        # 一百萬個元素的串列建立後釋放,不能因為遞迴釋放而當掉
        self.assertEqual(value("(length (iota 1000000))"), "1000000")

    def test_apply_with_primitive_and_closure(self):
        self.assertEqual(value("(apply max '(3 9 2))"), "9")
        self.assertEqual(value("(apply (lambda (a . r) (list a r)) 1 2 '(3))"), "(1 (2 3))")

    def test_shadowed_special_form(self):
        self.assertEqual(value("(define (f when) (+ when 1)) (f 1)"), "2")


if __name__ == "__main__":
    unittest.main()

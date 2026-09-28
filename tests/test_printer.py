import unittest

from tests.helpers import run, value


class PrinterTests(unittest.TestCase):
    def test_write_vs_display(self):
        self.assertEqual(value('"a\\"b"'), '"a\\"b"')
        self.assertEqual(run('(display "hi") (write "hi") (write #\\a) (display #\\a)')[1], 'hi"hi"#\\aa')

    def test_numbers(self):
        self.assertEqual(value("1/3"), "1/3")
        self.assertEqual(value("(/ 1.0 4)"), "0.25")
        self.assertEqual(value("(/ 1. 0)"), "+inf.0")
        self.assertEqual(value("(- (/ 1. 0))"), "-inf.0")
        self.assertEqual(value("(expt 2 100)"), str(2 ** 100))

    def test_structures(self):
        self.assertEqual(value("'(1 (2 . 3) #(4 5) \"s\")"), '(1 (2 . 3) #(4 5) "s")')
        self.assertEqual(value("''a"), "'a")
        self.assertEqual(value("car"), "#<primitive car>")
        self.assertEqual(value("(define (f) 1) f"), "#<procedure f>")
        self.assertEqual(value("(lambda () 1)"), "#<procedure>")
        self.assertEqual(value("(delay 1)"), "#<promise>")

    def test_record(self):
        src = "(define-record-type point (mk x y) point? (x px) (y py)) (mk 1 \"a\")"
        self.assertEqual(value(src), '#<point x=1 y="a">')

    def test_booleans_empty(self):
        self.assertEqual(value("(list #t #f '())"), "(#t #f ())")


if __name__ == "__main__":
    unittest.main()

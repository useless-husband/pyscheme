import unittest
from fractions import Fraction

from pyscheme.datatypes import NIL, Pair, char, sym
from pyscheme.errors import IncompleteInput, ReadError
from pyscheme.printer import to_string
from pyscheme.reader import Reader, read_all, read_one


class ReaderTests(unittest.TestCase):
    def test_atoms(self):
        self.assertEqual(read_one("42"), 42)
        self.assertEqual(read_one("-7"), -7)
        self.assertEqual(read_one("3.25"), 3.25)
        self.assertEqual(read_one("1e3"), 1000.0)
        self.assertEqual(read_one("3/6"), Fraction(1, 2))
        self.assertEqual(read_one("4/2"), 2)
        self.assertIs(read_one("#t"), True)
        self.assertIs(read_one("#false"), False)
        self.assertIs(read_one("foo"), sym("foo"))
        self.assertIs(read_one("+"), sym("+"))
        self.assertIs(read_one("-"), sym("-"))
        self.assertIs(read_one("..."), sym("..."))
        self.assertIs(read_one("1+"), sym("1+"))

    def test_strings_and_chars(self):
        self.assertEqual(read_one(r'"a\nb\t\"q\"\\"'), 'a\nb\t"q"\\')
        self.assertEqual(read_one(r'"\x41;"'), "A")
        self.assertIs(read_one(r"#\a"), char("a"))
        self.assertIs(read_one(r"#\space"), char(" "))
        self.assertIs(read_one(r"#\newline"), char("\n"))
        self.assertIs(read_one(r"#\("), char("("))
        self.assertIs(read_one(r"#\x41"), char("A"))

    def test_lists(self):
        self.assertEqual(to_string(read_one("(1 (2 3) . 4)"), True), "(1 (2 3) . 4)")
        self.assertIs(read_one("()"), NIL)
        self.assertEqual(to_string(read_one("'x"), True), "'x")
        self.assertEqual(to_string(read_one("`(a ,b ,@c)"), True), "`(a ,b ,@c)")
        self.assertEqual(read_one("#(1 2)"), [1, 2])

    def test_comments(self):
        self.assertEqual(read_all("1 ; comment\n 2 #| block #| nested |# |# 3 #;(skip) 4"),
                         [1, 2, 3, 4])

    def test_multiple(self):
        self.assertEqual(len(read_all("(a) (b) c")), 3)

    def test_error_positions(self):
        with self.assertRaises(ReadError) as cm:
            read_all("(a b)\n  )")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 3))
        self.assertIn("line 2, column 3", str(cm.exception))
        with self.assertRaises(ReadError) as cm:
            read_all("(a\n b]")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 3))
        with self.assertRaises(ReadError) as cm:
            read_all('\n\n  "ok" "bad\\q"')
        self.assertEqual(cm.exception.line, 3)

    def test_incomplete(self):
        for src in ("(a b", '"abc', "#| never closed", "'", "(a . "):
            with self.subTest(src=src):
                with self.assertRaises(IncompleteInput):
                    read_all(src)

    def test_incomplete_reports_open_paren_position(self):
        with self.assertRaises(IncompleteInput) as cm:
            read_all("(define x\n  (foo")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 3))

    def test_bad_syntax(self):
        for src in ("( . 1)", "#zzz", "#\\bogus"):
            with self.subTest(src=src):
                with self.assertRaises(ReadError):
                    read_all(src)

    def test_reader_class_eof(self):
        r = Reader("  ; only comment\n")
        from pyscheme.reader import EOF
        self.assertIs(r.read(), EOF)


if __name__ == "__main__":
    unittest.main()

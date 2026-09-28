"""Reader:把文字變成 Scheme 資料 (datum)。

手寫的遞迴下降剖析器。遇到錯誤會回報行號與欄位;
如果只是「輸入還沒結束」則丟 IncompleteInput,REPL 靠它判斷要不要繼續讀下一行。
"""
import re
from fractions import Fraction

from .datatypes import NIL, Pair, char, py_to_list, sym
from .errors import IncompleteInput, ReadError, bi

EOF = object()
DELIMS = set(" \t\n\r\f()[]\";")
QUOTE, QUASI = sym("quote"), sym("quasiquote")
UNQ, UNQS = sym("unquote"), sym("unquote-splicing")
CHAR_NAMES = {"space": " ", "newline": "\n", "tab": "\t", "return": "\r",
              "null": "\0", "nul": "\0", "delete": "\x7f", "escape": "\x1b",
              "altmode": "\x1b", "backspace": "\b", "alarm": "\a", "linefeed": "\n"}
STR_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "a": "\a",
           "0": "\0", "b": "\b"}
FLOAT_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
FRAC_RE = re.compile(r"^[+-]?\d+/\d+$")
INT_RE = re.compile(r"^[+-]?\d+$")


def parse_number(tok, radix=10):
    """把 token 轉成數字;不是數字回傳 None。"""
    if radix != 10:
        try:
            return int(tok, radix)
        except ValueError:
            return None
    if INT_RE.match(tok):
        return int(tok)
    if FLOAT_RE.match(tok):
        return float(tok)
    if FRAC_RE.match(tok):
        n, d = tok.split("/")
        if int(d) == 0:
            return None
        f = Fraction(int(n), int(d))
        return f.numerator if f.denominator == 1 else f
    if tok in ("+inf.0", "-inf.0"):
        return float(tok[:-2])
    if tok in ("+nan.0", "-nan.0"):
        return float("nan")
    return None


class Reader:
    def __init__(self, text):
        self.s = text
        self.i = 0
        self.n = len(text)

    # ---- 錯誤與位置 ----
    def linecol(self, pos):
        line = self.s.count("\n", 0, pos) + 1
        col = pos - (self.s.rfind("\n", 0, pos) + 1) + 1
        return line, col

    def error(self, msg, pos=None, incomplete=False):
        line, col = self.linecol(self.i if pos is None else pos)
        raise (IncompleteInput if incomplete else ReadError)(msg, line, col)

    # ---- 空白與註解 ----
    def skip_ws(self):
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in " \t\n\r\f":
                self.i += 1
            elif c == ";":
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif c == "#" and s.startswith("#|", self.i):
                start, depth = self.i, 1
                self.i += 2
                while depth:
                    a, b = s.find("|#", self.i), s.find("#|", self.i)
                    if a < 0:
                        self.error(bi("unterminated block comment #|",
                                      "區塊註解 #| 沒有結尾 |#"), start, True)
                    if 0 <= b < a:
                        depth += 1
                        self.i = b + 2
                    else:
                        depth -= 1
                        self.i = a + 2
            elif c == "#" and s.startswith("#;", self.i):
                self.i += 2
                self.datum()
            else:
                break

    # ---- 對外介面 ----
    def read(self):
        self.skip_ws()
        if self.i >= self.n:
            return EOF
        return self.datum()

    def read_all(self):
        out = []
        while True:
            d = self.read()
            if d is EOF:
                return out
            out.append(d)

    # ---- 內部 ----
    def datum(self):
        self.skip_ws()
        s = self.s
        if self.i >= self.n:
            self.error(bi("unexpected end of input", "輸入意外結束"), incomplete=True)
        c = s[self.i]
        start = self.i
        if c in "([":
            self.i += 1
            return self.read_list(c, start)
        if c in ")]":
            self.error(bi("unexpected close parenthesis", "多出來的右括號"))
        if c == "'":
            self.i += 1
            return py_to_list([QUOTE, self.datum()])
        if c == "`":
            self.i += 1
            return py_to_list([QUASI, self.datum()])
        if c == ",":
            if s.startswith(",@", self.i):
                self.i += 2
                return py_to_list([UNQS, self.datum()])
            self.i += 1
            return py_to_list([UNQ, self.datum()])
        if c == '"':
            return self.read_string()
        if c == "#":
            return self.read_hash()
        return self.read_atom()

    def read_list(self, open_ch, start):
        close = ")" if open_ch == "(" else "]"
        items, tail = [], NIL
        while True:
            self.skip_ws()
            if self.i >= self.n:
                self.error(bi("missing close parenthesis for the one opened here",
                              "這個左括號沒有對應的右括號"), start, True)
            c = self.s[self.i]
            if c in ")]":
                if c != close:
                    self.error(bi(f"mismatched parenthesis: expected '{close}'",
                                  f"括號種類不符:應為 '{close}'"))
                self.i += 1
                return py_to_list(items, tail)
            if c == "." and (self.i + 1 >= self.n or self.s[self.i + 1] in DELIMS):
                if not items:
                    self.error(bi("dot at the start of a list", "串列開頭不能是 ."))
                self.i += 1
                tail = self.datum()
                self.skip_ws()
                if self.i >= self.n:
                    self.error(bi("missing close parenthesis", "缺少右括號"), start, True)
                if self.s[self.i] != close:
                    self.error(bi("expected ')' after dotted tail", "點對 (.) 之後只能有一個元素"))
                self.i += 1
                return py_to_list(items, tail)
            items.append(self.datum())

    def read_string(self):
        s = self.s
        start = self.i
        self.i += 1
        buf = []
        while True:
            if self.i >= self.n:
                self.error(bi("unterminated string", "字串沒有結尾的引號"), start, True)
            c = s[self.i]
            if c == '"':
                self.i += 1
                return "".join(buf)
            if c == "\\":
                self.i += 1
                if self.i >= self.n:
                    self.error(bi("unterminated string", "字串沒有結尾的引號"), start, True)
                e = s[self.i]
                if e in STR_ESC:
                    buf.append(STR_ESC[e])
                elif e == "x":
                    j = s.find(";", self.i)
                    try:
                        buf.append(chr(int(s[self.i + 1:j], 16)))
                    except ValueError:
                        self.error(bi("bad \\x escape in string", "字串中的 \\x 跳脫格式錯誤"))
                    self.i = j
                elif e == "\n":  # 行尾反斜線:吃掉換行與下一行的縮排
                    while self.i + 1 < self.n and s[self.i + 1] in " \t":
                        self.i += 1
                else:
                    self.error(bi(f"unknown escape \\{e} in string", f"字串中不認得的跳脫字元 \\{e}"))
                self.i += 1
            else:
                buf.append(c)
                self.i += 1

    def token(self):
        s, j = self.s, self.i
        while j < self.n and s[j] not in DELIMS:
            j += 1
        tok = s[self.i:j]
        self.i = j
        return tok

    def read_hash(self):
        s = self.s
        start = self.i
        nxt = s[self.i + 1] if self.i + 1 < self.n else ""
        if nxt == "(":
            self.i += 2
            lst = self.read_list("(", start)
            out = []
            while lst.__class__ is Pair:
                out.append(lst.car)
                lst = lst.cdr
            return out
        if nxt == "\\":
            self.i += 2
            if self.i >= self.n:
                self.error(bi("incomplete character literal", "字元 #\\ 不完整"), start, True)
            first = s[self.i]
            self.i += 1
            j = self.i
            while j < self.n and s[j] not in DELIMS:
                j += 1
            rest = s[self.i:j]
            self.i = j
            if not rest:
                return char(first)
            name = first + rest
            if name in CHAR_NAMES:
                return char(CHAR_NAMES[name])
            if first == "x" and re.fullmatch(r"[0-9a-fA-F]+", rest):
                return char(chr(int(rest, 16)))
            self.error(bi(f"unknown character name #\\{name}", f"不認得的字元名稱 #\\{name}"), start)
        tok = self.token()
        if tok in ("#t", "#true"):
            return True
        if tok in ("#f", "#false"):
            return False
        radix = {"x": 16, "b": 2, "o": 8, "d": 10}.get(tok[1:2].lower())
        if radix and len(tok) > 2:
            n = parse_number(tok[2:], radix)
            if n is not None:
                return n
        self.error(bi(f"bad syntax {tok}", f"不合法的語法 {tok}"), start)

    def read_atom(self):
        start = self.i
        tok = self.token()
        if not tok:
            self.error(bi("unexpected character", "無法辨識的字元"))
        n = parse_number(tok)
        if n is not None:
            return n
        return sym(tok)


def read_all(text):
    return Reader(text).read_all()


def read_one(text):
    d = Reader(text).read()
    if d is EOF:
        raise IncompleteInput("empty input", 1, 1)
    return d

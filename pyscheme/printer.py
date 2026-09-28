"""把 Scheme 值轉成文字。display 與 write 的差別在字串和字元。"""
import math
from fractions import Fraction

from .datatypes import (NIL, UNSPEC, Char, Closure, Continuation, HashTable,
                        Pair, Primitive, Promise, Record, RecordType,
                        SpecialPrim, Symbol, Env)

CHAR_NAMES = {" ": "space", "\n": "newline", "\t": "tab", "\r": "return",
              "\0": "null", "\x7f": "delete", "\x1b": "escape"}
STR_ESC = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}
QUOTES = {"quote": "'", "quasiquote": "`", "unquote": ",", "unquote-splicing": ",@"}


def fmt_float(x):
    if x != x:
        return "+nan.0"
    if x in (math.inf, -math.inf):
        return "+inf.0" if x > 0 else "-inf.0"
    return repr(x)


def to_string(x, write=False):
    out = []
    _p(x, write, out)
    return "".join(out)


def _p(x, write, out):
    c = x.__class__
    if c is bool:
        out.append("#t" if x else "#f")
    elif c is int:
        out.append(str(x))
    elif c is float:
        out.append(fmt_float(x))
    elif c is Fraction:
        out.append(f"{x.numerator}/{x.denominator}")
    elif c is str:
        if write:
            out.append('"' + "".join(STR_ESC.get(ch, ch) for ch in x) + '"')
        else:
            out.append(x)
    elif c is Symbol:
        out.append(x.name)
    elif c is Char:
        if write:
            out.append("#\\" + CHAR_NAMES.get(x.ch, x.ch))
        else:
            out.append(x.ch)
    elif x is NIL:
        out.append("()")
    elif c is Pair:
        _pair(x, write, out)
    elif c is list:
        out.append("#(")
        for i, e in enumerate(x):
            if i:
                out.append(" ")
            _p(e, write, out)
        out.append(")")
    elif x is UNSPEC:
        pass
    elif c is Closure:
        out.append(f"#<procedure {x.name.name}>" if x.name else "#<procedure>")
    elif c in (Primitive, SpecialPrim):
        out.append(f"#<primitive {x.name}>")
    elif c is Continuation:
        out.append("#<continuation>")
    elif c is Promise:
        out.append("#<promise>")
    elif c is Record:
        out.append("#<" + x.rtype.name)
        for f, v in zip(x.rtype.fields, x.values):
            out.append(f" {f.name}=")
            _p(v, True, out)
        out.append(">")
    elif c is RecordType:
        out.append(f"#<record-type {x.name}>")
    elif c is HashTable:
        out.append("#<hash-table>")
    elif c is Env:
        out.append("#<environment>")
    else:
        out.append(f"#<{c.__name__}>")


def _pair(x, write, out):
    if x.car.__class__ is Symbol and x.car.name in QUOTES \
            and x.cdr.__class__ is Pair and x.cdr.cdr is NIL:
        out.append(QUOTES[x.car.name])
        _p(x.cdr.car, write, out)
        return
    out.append("(")
    first = True
    while x.__class__ is Pair:
        if not first:
            out.append(" ")
        first = False
        _p(x.car, write, out)
        x = x.cdr
    if x is not NIL:
        out.append(" . ")
        _p(x, write, out)
    out.append(")")

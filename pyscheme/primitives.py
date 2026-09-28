"""用 Python 實作的內建程序。

用 @prim("名稱", ...) 註冊。pure=True 代表沒有副作用 (也不會呼叫 Scheme 程序),
直譯器可以在快速路徑裡直接呼叫它們。
"""
import math
import random as _random
import sys
import time
from fractions import Fraction

from .datatypes import (NIL, NUMT, UNSPEC, Char, HashTable, Pair, Primitive,
                        Record, RecordType, Symbol, char, list_to_py, py_to_list,
                        sym, is_list)
from .errors import SchemeError, SchemeExit, bi
from .printer import fmt_float, to_string
from .reader import parse_number

PRIMS = {}
_gensym_counter = [0]


def prim(*names, pure=False):
    def deco(fn):
        for n in names:
            PRIMS[n] = Primitive(n, fn, pure)
        return fn
    return deco


# ---------------------------------------------------------------- 錯誤輔助
def terr(name, en, zh, got):
    g = to_string(got, True)
    return SchemeError(bi(f"{name}: expected {en}, got {g}", f"{name}: 需要{zh},卻收到 {g}"))


def need_num(name, x):
    if x.__class__ not in NUMT:
        raise terr(name, "number", "數字(number)", x)
    return x


def need_int(name, x):
    if x.__class__ is int:
        return x
    if x.__class__ is float and x.is_integer():
        return x
    raise terr(name, "integer", "整數(integer)", x)


def need_index(name, x):
    if x.__class__ is not int:
        raise terr(name, "exact integer index", "整數索引", x)
    return x


def need_str(name, x):
    if x.__class__ is not str:
        raise terr(name, "string", "字串(string)", x)
    return x


def need_pair(name, x):
    if x.__class__ is not Pair:
        raise terr(name, "pair", "序對(pair)", x)
    return x


def need_vec(name, x):
    if x.__class__ is not list:
        raise terr(name, "vector", "向量(vector)", x)
    return x


def need_char(name, x):
    if x.__class__ is not Char:
        raise terr(name, "character", "字元(char)", x)
    return x


def norm(r):
    if r.__class__ is Fraction and r.denominator == 1:
        return int(r)
    return r


# ---------------------------------------------------------------- 數字
@prim("+", pure=True)
def add(*a):
    r = 0
    for x in a:
        if x.__class__ not in NUMT:
            raise terr("+", "number", "數字(number)", x)
        r += x
    return norm(r) if r.__class__ is Fraction else r


@prim("*", pure=True)
def mul(*a):
    r = 1
    for x in a:
        if x.__class__ not in NUMT:
            raise terr("*", "number", "數字(number)", x)
        r *= x
    return norm(r) if r.__class__ is Fraction else r


@prim("-", pure=True)
def sub(x, *rest):
    need_num("-", x)
    if not rest:
        return -x
    r = x
    for y in rest:
        if y.__class__ not in NUMT:
            raise terr("-", "number", "數字(number)", y)
        r -= y
    return norm(r) if r.__class__ is Fraction else r


def _div2(a, b):
    if b == 0:
        if b.__class__ is float or a.__class__ is float:
            if a == 0 or a != a:
                return math.nan
            neg = (a < 0) != (math.copysign(1.0, b) < 0)
            return -math.inf if neg else math.inf
        raise SchemeError(bi("/: division by zero", "/: 除以零"))
    if a.__class__ is float or b.__class__ is float:
        return a / b
    if a.__class__ is int and b.__class__ is int:
        if a % b == 0:
            return a // b
        return Fraction(a, b)
    return norm(Fraction(a) / Fraction(b))


@prim("/", pure=True)
def div(x, *rest):
    need_num("/", x)
    if not rest:
        return _div2(1, x)
    r = x
    for y in rest:
        need_num("/", y)
        r = _div2(r, y)
    return r


def _cmp(name, op):
    def f(*a):
        for x in a:
            if x.__class__ not in NUMT:
                raise terr(name, "number", "數字(number)", x)
        for i in range(len(a) - 1):
            if not op(a[i], a[i + 1]):
                return False
        return True
    PRIMS[name] = Primitive(name, f, True)


import operator as _op
for _n, _o in (("=", _op.eq), ("<", _op.lt), (">", _op.gt), ("<=", _op.le), (">=", _op.ge)):
    _cmp(_n, _o)


@prim("quotient", "truncate-quotient", pure=True)
def quotient(a, b):
    need_int("quotient", a)
    need_int("quotient", b)
    if b == 0:
        raise SchemeError(bi("quotient: division by zero", "quotient: 除以零"))
    if a.__class__ is int and b.__class__ is int:
        q = abs(a) // abs(b)
        return q if (a < 0) == (b < 0) else -q
    return float(math.trunc(a / b))


@prim("remainder", "truncate-remainder", pure=True)
def remainder(a, b):
    need_int("remainder", a)
    need_int("remainder", b)
    if b == 0:
        raise SchemeError(bi("remainder: division by zero", "remainder: 除以零"))
    if a.__class__ is int and b.__class__ is int:
        r = abs(a) % abs(b)
        return -r if a < 0 else r
    return math.fmod(a, b)


@prim("modulo", "floor-remainder", pure=True)
def modulo(a, b):
    need_int("modulo", a)
    need_int("modulo", b)
    if b == 0:
        raise SchemeError(bi("modulo: division by zero", "modulo: 除以零"))
    return a % b


@prim("floor/", pure=True)
def floor_div(a, b):
    return py_to_list([a // b, modulo(a, b)])


@prim("abs", "magnitude", pure=True)
def p_abs(x):
    return abs(need_num("abs", x))


@prim("min", pure=True)
def p_min(x, *rest):
    return _minmax("min", min, x, rest)


@prim("max", pure=True)
def p_max(x, *rest):
    return _minmax("max", max, x, rest)


def _minmax(name, fn, x, rest):
    need_num(name, x)
    inexact = x.__class__ is float
    for y in rest:
        need_num(name, y)
        inexact = inexact or y.__class__ is float
    r = fn((x,) + rest)
    return float(r) if inexact else r


@prim("gcd", pure=True)
def p_gcd(*a):
    r = 0
    for x in a:
        r = math.gcd(r, need_int("gcd", x))
    return r


@prim("lcm", pure=True)
def p_lcm(*a):
    r = 1
    for x in a:
        r = math.lcm(r, need_int("lcm", x))
    return r


@prim("1+", pure=True)
def inc(x):
    return add(x, 1)


@prim("-1+", "1-", pure=True)
def dec(x):
    return sub(x, 1)


@prim("square", pure=True)
def square(x):
    return mul(x, x)


@prim("cube", pure=True)
def cube(x):
    return mul(x, x, x)


@prim("expt", pure=True)
def expt(b, e):
    need_num("expt", b)
    need_num("expt", e)
    if e.__class__ is int:
        if e >= 0:
            return b ** e
        if b == 0:
            raise SchemeError(bi("expt: division by zero", "expt: 除以零"))
        return norm(Fraction(b) ** e) if b.__class__ is not float else b ** e
    if e.__class__ is Fraction and e.denominator != 1:
        e = float(e)
    r = float(b) ** float(e)
    if isinstance(r, complex):
        raise SchemeError(bi("expt: result is not a real number", "expt: 結果不是實數"))
    return r


@prim("sqrt", pure=True)
def p_sqrt(x):
    need_num("sqrt", x)
    if x < 0:
        raise SchemeError(bi("sqrt: negative argument (complex numbers are not supported)",
                             "sqrt: 參數為負數(不支援複數)"))
    if x.__class__ is int:
        r = math.isqrt(x)
        return r if r * r == x else math.sqrt(x)
    if x.__class__ is Fraction:
        n, d = math.isqrt(x.numerator), math.isqrt(x.denominator)
        if n * n == x.numerator and d * d == x.denominator:
            return Fraction(n, d)
    return math.sqrt(x)


@prim("exact-integer-sqrt", pure=True)
def exact_isqrt(n):
    r = math.isqrt(need_index("exact-integer-sqrt", n))
    return py_to_list([r, n - r * r])


def _float_fn(name, fn):
    def f(x):
        need_num(name, x)
        try:
            return fn(x)
        except ValueError:
            raise SchemeError(bi(f"{name}: argument out of domain", f"{name}: 參數超出定義域"))
    PRIMS[name] = Primitive(name, f, True)


for _n, _f in (("sin", math.sin), ("cos", math.cos), ("tan", math.tan),
               ("asin", math.asin), ("acos", math.acos)):
    _float_fn(_n, _f)


@prim("exp", pure=True)
def p_exp(x):
    return 1 if x == 0 and x.__class__ is int else math.exp(need_num("exp", x))


@prim("log", pure=True)
def p_log(x, base=None):
    need_num("log", x)
    if x == 0 or x < 0:
        raise SchemeError(bi("log: argument out of domain", "log: 參數超出定義域"))
    if x == 1 and x.__class__ is int and base is None:
        return 0
    return math.log(x) if base is None else math.log(x) / math.log(need_num("log", base))


@prim("atan", pure=True)
def p_atan(y, x=None):
    need_num("atan", y)
    return math.atan(y) if x is None else math.atan2(y, need_num("atan", x))


@prim("number?", "complex?", "real?", pure=True)
def is_number(x):
    return x.__class__ in NUMT


@prim("integer?", pure=True)
def is_integer(x):
    return x.__class__ is int or (x.__class__ is float and x.is_integer())


@prim("rational?", pure=True)
def is_rational(x):
    return x.__class__ in (int, Fraction) or (x.__class__ is float and math.isfinite(x))


@prim("exact?", pure=True)
def is_exact(x):
    return need_num("exact?", x).__class__ is not float


@prim("inexact?", pure=True)
def is_inexact(x):
    return need_num("inexact?", x).__class__ is float


@prim("exact-integer?", pure=True)
def is_exact_integer(x):
    return x.__class__ is int


@prim("exact-rational?", pure=True)
def is_exact_rational(x):
    return x.__class__ in (int, Fraction)


@prim("nan?", pure=True)
def is_nan(x):
    return need_num("nan?", x) != x


@prim("zero?", pure=True)
def is_zero(x):
    return need_num("zero?", x) == 0


@prim("positive?", pure=True)
def is_positive(x):
    return need_num("positive?", x) > 0


@prim("negative?", pure=True)
def is_negative(x):
    return need_num("negative?", x) < 0


@prim("odd?", pure=True)
def is_odd(x):
    return need_int("odd?", x) % 2 == 1


@prim("even?", pure=True)
def is_even(x):
    return need_int("even?", x) % 2 == 0


@prim("exact->inexact", "inexact", "exact->inexact", pure=True)
def to_inexact(x):
    return float(need_num("exact->inexact", x))


@prim("inexact->exact", "exact", pure=True)
def to_exact(x):
    need_num("inexact->exact", x)
    if x.__class__ is float:
        if not math.isfinite(x):
            raise terr("inexact->exact", "finite number", "有限的數字", x)
        return int(x) if x.is_integer() else norm(Fraction(x))
    return x


def _rounder(name, fn):
    def f(x):
        need_num(name, x)
        if x.__class__ is int:
            return x
        if x.__class__ is float:
            return float(fn(x)) if math.isfinite(x) else x
        return fn(x)
    PRIMS[name] = Primitive(name, f, True)


_rounder("floor", math.floor)
_rounder("ceiling", math.ceil)
_rounder("truncate", math.trunc)
_rounder("round", round)


@prim("numerator", pure=True)
def numerator(x):
    return Fraction(to_exact(x)).numerator


@prim("denominator", pure=True)
def denominator(x):
    return Fraction(to_exact(x)).denominator


@prim("number->string", pure=True)
def number_to_string(x, radix=10):
    need_num("number->string", x)
    if radix != 10 and x.__class__ is int:
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        n, out = abs(x), []
        while True:
            n, d = divmod(n, radix)
            out.append(digits[d])
            if n == 0:
                break
        return ("-" if x < 0 else "") + "".join(reversed(out))
    return to_string(x)


@prim("string->number", pure=True)
def string_to_number(s, radix=10):
    n = parse_number(need_str("string->number", s), radix)
    return False if n is None else n


@prim("bitwise-and", pure=True)
def bit_and(*a):
    r = -1
    for x in a:
        r &= need_index("bitwise-and", x)
    return r


@prim("bitwise-or", pure=True)
def bit_or(*a):
    r = 0
    for x in a:
        r |= need_index("bitwise-or", x)
    return r


@prim("bitwise-xor", pure=True)
def bit_xor(*a):
    r = 0
    for x in a:
        r ^= need_index("bitwise-xor", x)
    return r


@prim("arithmetic-shift", pure=True)
def arith_shift(x, n):
    need_index("arithmetic-shift", x)
    return x << n if need_index("arithmetic-shift", n) >= 0 else x >> -n


@prim("random")
def p_random(n):
    if n.__class__ is int and n > 0:
        return _random.randrange(n)
    if n.__class__ is float and n > 0:
        return _random.random() * n
    raise terr("random", "positive number", "正數", n)


# ---------------------------------------------------------------- 相等與型別述詞
def eqv(a, b):
    ca, cb = a.__class__, b.__class__
    if ca in NUMT and cb in NUMT:
        return ca is cb and a == b
    if ca is bool or cb is bool:
        return a is b
    if ca is str and cb is str:
        return a is b or (a == "" and b == "")
    return a is b


def equal(a, b):
    while True:
        ca = a.__class__
        if ca is Pair:
            if b.__class__ is not Pair:
                return False
            if not equal(a.car, b.car):
                return False
            a, b = a.cdr, b.cdr
            continue
        if ca is list:
            return b.__class__ is list and len(a) == len(b) and \
                all(equal(x, y) for x, y in zip(a, b))
        if ca is str:
            return b.__class__ is str and a == b
        return eqv(a, b)


@prim("eq?", pure=True)
def is_eq(a, b):
    return eqv(a, b)


@prim("eqv?", pure=True)
def is_eqv(a, b):
    return eqv(a, b)


@prim("equal?", pure=True)
def is_equal(a, b):
    return equal(a, b)


@prim("not", pure=True)
def p_not(x):
    return x is False


@prim("boolean?", pure=True)
def is_boolean(x):
    return x.__class__ is bool


@prim("symbol?", pure=True)
def is_symbol(x):
    return x.__class__ is Symbol


@prim("string?", pure=True)
def is_string(x):
    return x.__class__ is str


@prim("char?", pure=True)
def is_char(x):
    return x.__class__ is Char


@prim("vector?", pure=True)
def is_vector(x):
    return x.__class__ is list


@prim("pair?", pure=True)
def is_pair(x):
    return x.__class__ is Pair


@prim("null?", pure=True)
def is_null(x):
    return x is NIL


@prim("list?", pure=True)
def p_is_list(x):
    return is_list(x)


@prim("procedure?", pure=True)
def is_procedure(x):
    from .datatypes import Closure, Continuation, SpecialPrim
    return x.__class__ in (Closure, Primitive, SpecialPrim, Continuation)


@prim("boolean=?", pure=True)
def boolean_eq(a, b):
    return a is b


@prim("default-object?", pure=True)
def default_object(x):
    return x is UNSPEC


# ---------------------------------------------------------------- 序對與串列
@prim("cons", pure=True)
def cons(a, b):
    return Pair(a, b)


@prim("car", pure=True)
def car(x):
    if x.__class__ is not Pair:
        raise terr("car", "pair", "序對(pair)", x)
    return x.car


@prim("cdr", pure=True)
def cdr(x):
    if x.__class__ is not Pair:
        raise terr("cdr", "pair", "序對(pair)", x)
    return x.cdr


def _make_cxr(path):
    name = "c" + path + "r"

    def f(x):
        orig = x
        for step in reversed(path):
            if x.__class__ is not Pair:
                raise terr(name, "a suitable pair structure", "足夠深的序對結構", orig)
            x = x.car if step == "a" else x.cdr
        return x
    PRIMS[name] = Primitive(name, f, True)


for _p in ("aa", "ad", "da", "dd", "aaa", "aad", "ada", "add", "daa", "dad", "dda",
           "ddd", "addd", "dddd"):
    _make_cxr(_p)


@prim("set-car!")
def set_car(p, v):
    need_pair("set-car!", p).car = v
    return UNSPEC


@prim("set-cdr!")
def set_cdr(p, v):
    need_pair("set-cdr!", p).cdr = v
    return UNSPEC


@prim("list", pure=True)
def p_list(*a):
    return py_to_list(a)


@prim("cons*", "list*", pure=True)
def cons_star(*a):
    return py_to_list(a[:-1], a[-1])


@prim("make-list", pure=True)
def make_list(n, fill=UNSPEC):
    return py_to_list([fill] * need_index("make-list", n))


@prim("length", pure=True)
def length(x):
    n = 0
    p = x
    while p.__class__ is Pair:
        n += 1
        p = p.cdr
    if p is not NIL:
        raise terr("length", "proper list", "正規串列(list)", x)
    return n


@prim("append", pure=True)
def append(*lists):
    if not lists:
        return NIL
    result = lists[-1]
    for lst in reversed(lists[:-1]):
        result = py_to_list(list_to_py(lst, "append"), result)
    return result


@prim("reverse", pure=True)
def reverse(x):
    r = NIL
    p = x
    while p.__class__ is Pair:
        r = Pair(p.car, r)
        p = p.cdr
    if p is not NIL:
        raise terr("reverse", "proper list", "正規串列(list)", x)
    return r


@prim("list-tail", pure=True)
def list_tail(x, k):
    need_index("list-tail", k)
    p = x
    for _ in range(k):
        if p.__class__ is not Pair:
            raise SchemeError(bi("list-tail: index out of range", "list-tail: 索引超出範圍"))
        p = p.cdr
    return p


@prim("list-head", pure=True)
def list_head(x, k):
    need_index("list-head", k)
    out, p = [], x
    for _ in range(k):
        if p.__class__ is not Pair:
            raise SchemeError(bi("list-head: index out of range", "list-head: 索引超出範圍"))
        out.append(p.car)
        p = p.cdr
    return py_to_list(out)


@prim("list-ref", pure=True)
def list_ref(x, k):
    need_index("list-ref", k)
    p = x
    for _ in range(k):
        if p.__class__ is not Pair:
            raise SchemeError(bi("list-ref: index out of range", "list-ref: 索引超出範圍"))
        p = p.cdr
    if p.__class__ is not Pair:
        raise SchemeError(bi("list-ref: index out of range", "list-ref: 索引超出範圍"))
    return p.car


@prim("list-copy", pure=True)
def list_copy(x):
    return py_to_list(list_to_py(x, "list-copy"))


@prim("last-pair", pure=True)
def last_pair(x):
    need_pair("last-pair", x)
    while x.cdr.__class__ is Pair:
        x = x.cdr
    return x


@prim("iota", pure=True)
def iota(n, start=0, step=1):
    need_index("iota", n)
    return py_to_list([add(start, mul(i, step)) for i in range(n)])


def _mem(name, test):
    def f(x, lst):
        p = lst
        while p.__class__ is Pair:
            if test(x, p.car):
                return p
            p = p.cdr
        return False
    PRIMS[name] = Primitive(name, f, True)


def _ass(name, test):
    def f(x, lst):
        p = lst
        while p.__class__ is Pair:
            e = p.car
            if e.__class__ is not Pair:
                raise terr(name, "association list (list of pairs)", "關聯串列(元素須為序對)", lst)
            if test(x, e.car):
                return e
            p = p.cdr
        return False
    PRIMS[name] = Primitive(name, f, True)


_mem("memq", eqv)
_mem("memv", eqv)
_mem("member", equal)
_ass("assq", eqv)
_ass("assv", eqv)
_ass("assoc", equal)


# ---------------------------------------------------------------- 符號
@prim("symbol->string", pure=True)
def symbol_to_string(s):
    if s.__class__ is not Symbol:
        raise terr("symbol->string", "symbol", "符號(symbol)", s)
    return s.name


@prim("string->symbol", "intern", pure=True)
def string_to_symbol(s):
    return sym(need_str("string->symbol", s))


@prim("symbol-append", pure=True)
def symbol_append(*a):
    return sym("".join(x.name for x in a))


@prim("gensym", "generate-uninterned-symbol")
def gensym(prefix="g"):
    _gensym_counter[0] += 1
    return Symbol(f"{prefix if prefix.__class__ is str else 'g'}{_gensym_counter[0]}")


# ---------------------------------------------------------------- 字元
@prim("char->integer", pure=True)
def char_to_integer(c):
    return ord(need_char("char->integer", c).ch)


@prim("integer->char", pure=True)
def integer_to_char(n):
    return char(chr(need_index("integer->char", n)))


@prim("char-upcase", pure=True)
def char_upcase(c):
    return char(need_char("char-upcase", c).ch.upper())


@prim("char-downcase", pure=True)
def char_downcase(c):
    return char(need_char("char-downcase", c).ch.lower())


@prim("char-alphabetic?", pure=True)
def char_alpha(c):
    return need_char("char-alphabetic?", c).ch.isalpha()


@prim("char-numeric?", pure=True)
def char_numeric(c):
    return need_char("char-numeric?", c).ch.isdigit()


@prim("char-whitespace?", pure=True)
def char_space(c):
    return need_char("char-whitespace?", c).ch.isspace()


@prim("char-upper-case?", pure=True)
def char_upper(c):
    return need_char("char-upper-case?", c).ch.isupper()


@prim("char-lower-case?", pure=True)
def char_lower(c):
    return need_char("char-lower-case?", c).ch.islower()


@prim("char->digit", pure=True)
def char_to_digit(c, radix=10):
    try:
        return int(need_char("char->digit", c).ch, radix)
    except ValueError:
        return False


@prim("digit->char", pure=True)
def digit_to_char(d, radix=10):
    return char("0123456789abcdefghijklmnopqrstuvwxyz"[d]) if 0 <= d < radix else False


def _char_cmp(name, op, fold=False):
    def f(*a):
        vals = [need_char(name, c).ch for c in a]
        if fold:
            vals = [v.lower() for v in vals]
        return all(op(vals[i], vals[i + 1]) for i in range(len(vals) - 1))
    PRIMS[name] = Primitive(name, f, True)


def _str_cmp(name, op, fold=False):
    def f(*a):
        vals = [need_str(name, s) for s in a]
        if fold:
            vals = [v.lower() for v in vals]
        return all(op(vals[i], vals[i + 1]) for i in range(len(vals) - 1))
    PRIMS[name] = Primitive(name, f, True)


for _n, _o in (("=?", _op.eq), ("<?", _op.lt), (">?", _op.gt), ("<=?", _op.le), (">=?", _op.ge)):
    _char_cmp("char" + _n, _o)
    _char_cmp("char-ci" + _n, _o, True)
    _str_cmp("string" + _n, _o)
    _str_cmp("string-ci" + _n, _o, True)


# ---------------------------------------------------------------- 字串
@prim("string-length", pure=True)
def string_length(s):
    return len(need_str("string-length", s))


@prim("string-ref", pure=True)
def string_ref(s, k):
    need_str("string-ref", s)
    if need_index("string-ref", k) < 0 or k >= len(s):
        raise SchemeError(bi(f"string-ref: index {k} out of range", f"string-ref: 索引 {k} 超出範圍"))
    return char(s[k])


@prim("substring", pure=True)
def substring(s, start, end=None):
    need_str("substring", s)
    end = len(s) if end is None else end
    need_index("substring", start)
    need_index("substring", end)
    if not 0 <= start <= end <= len(s):
        raise SchemeError(bi(f"substring: range {start}..{end} out of bounds for length {len(s)}",
                             f"substring: 範圍 {start}..{end} 超出長度 {len(s)}"))
    return s[start:end]


@prim("string-append", pure=True)
def string_append(*a):
    for s in a:
        need_str("string-append", s)
    return "".join(a)


@prim("string", pure=True)
def p_string(*a):
    return "".join(x.ch if x.__class__ is Char else to_string(x) for x in a)


@prim("make-string", pure=True)
def make_string(n, c=None):
    return (c.ch if c else " ") * need_index("make-string", n)


@prim("string-copy", pure=True)
def string_copy(s, start=0, end=None):
    return substring(s, start, end)


@prim("string-null?", pure=True)
def string_null(s):
    return need_str("string-null?", s) == ""


@prim("string-upcase", pure=True)
def string_upcase(s):
    return need_str("string-upcase", s).upper()


@prim("string-downcase", pure=True)
def string_downcase(s):
    return need_str("string-downcase", s).lower()


@prim("string-reverse", pure=True)
def string_reverse(s):
    return need_str("string-reverse", s)[::-1]


@prim("string->list", pure=True)
def string_to_list(s, start=0, end=None):
    return py_to_list([char(c) for c in substring(s, start, end)])


@prim("list->string", pure=True)
def list_to_string(lst):
    return "".join(need_char("list->string", c).ch for c in list_to_py(lst, "list->string"))


@prim("string->vector", pure=True)
def string_to_vector(s):
    return [char(c) for c in need_str("string->vector", s)]


@prim("string-index", pure=True)
def string_index(s, c):
    i = need_str("string-index", s).find(need_char("string-index", c).ch)
    return False if i < 0 else i


@prim("string-contains", "string-search-forward", pure=True)
def string_contains(s, pat, start=0):
    if s.__class__ is str and pat.__class__ is int:  # MIT 參數順序 (pattern string start)
        s, pat = pat, s
    i = need_str("string-contains", s).find(need_str("string-contains", pat), start)
    return False if i < 0 else i


@prim("string-prefix?", pure=True)
def string_prefix(p, s):
    return need_str("string-prefix?", s).startswith(need_str("string-prefix?", p))


@prim("string-suffix?", pure=True)
def string_suffix(p, s):
    return need_str("string-suffix?", s).endswith(need_str("string-suffix?", p))


@prim("string-trim", pure=True)
def string_trim(s):
    return need_str("string-trim", s).strip()


@prim("string-pad-left", pure=True)
def string_pad_left(s, n, c=None):
    need_str("string-pad-left", s)
    fill = c.ch if c else " "
    return s[-n:] if len(s) >= n else fill * (n - len(s)) + s


@prim("string-pad-right", pure=True)
def string_pad_right(s, n, c=None):
    need_str("string-pad-right", s)
    fill = c.ch if c else " "
    return s[:n] if len(s) >= n else s + fill * (n - len(s))


@prim("string-join", pure=True)
def string_join(lst, delim=" "):
    items = list_to_py(lst, "string-join")
    for s in items:
        need_str("string-join", s)
    return need_str("string-join", delim).join(items)


@prim("string-split", pure=True)
def string_split(s, delim=None):
    need_str("string-split", s)
    d = " " if delim is None else (delim.ch if delim.__class__ is Char else need_str("string-split", delim))
    return py_to_list(s.split(d))


# ---------------------------------------------------------------- 向量
@prim("vector", pure=True)
def vector(*a):
    return list(a)


@prim("make-vector", pure=True)
def make_vector(n, fill=False):
    if need_index("make-vector", n) < 0:
        raise terr("make-vector", "non-negative integer", "非負整數", n)
    return [fill] * n


@prim("vector-length", pure=True)
def vector_length(v):
    return len(need_vec("vector-length", v))


def _vidx(name, v, k):
    need_vec(name, v)
    if need_index(name, k) < 0 or k >= len(v):
        raise SchemeError(bi(f"{name}: index {k} out of range (length {len(v)})",
                             f"{name}: 索引 {k} 超出範圍(長度 {len(v)})"))


@prim("vector-ref", pure=True)
def vector_ref(v, k):
    _vidx("vector-ref", v, k)
    return v[k]


@prim("vector-set!")
def vector_set(v, k, x):
    _vidx("vector-set!", v, k)
    v[k] = x
    return UNSPEC


@prim("vector->list", pure=True)
def vector_to_list(v, start=0, end=None):
    need_vec("vector->list", v)
    return py_to_list(v[start:end])


@prim("list->vector", pure=True)
def list_to_vector(lst):
    return list_to_py(lst, "list->vector")


@prim("vector-fill!")
def vector_fill(v, x):
    need_vec("vector-fill!", v)
    for i in range(len(v)):
        v[i] = x
    return UNSPEC


@prim("vector-copy", "subvector", pure=True)
def vector_copy(v, start=0, end=None):
    need_vec("vector-copy", v)
    return v[start:end]


@prim("vector-append", pure=True)
def vector_append(*vs):
    out = []
    for v in vs:
        out.extend(need_vec("vector-append", v))
    return out


@prim("vector-grow", pure=True)
def vector_grow(v, n):
    return need_vec("vector-grow", v) + [False] * (n - len(v))


# ---------------------------------------------------------------- 雜湊表
def hkey(x):
    c = x.__class__
    if c is Pair:
        items = []
        while x.__class__ is Pair:
            items.append(hkey(x.car))
            x = x.cdr
        return ("pair", tuple(items), hkey(x))
    if c is list:
        return ("vec", tuple(hkey(e) for e in x))
    if c in (int, float, Fraction, str, bool):
        return (c.__name__, x)
    return x


@prim("make-hash-table", "make-equal-hash-table", "make-strong-eqv-hash-table",
      "make-string-hash-table", "make-eqv-hash-table")
def make_hash_table(*_):
    return HashTable()


def need_ht(name, t):
    if t.__class__ is not HashTable:
        raise terr(name, "hash table", "雜湊表", t)
    return t


@prim("hash-table?", pure=True)
def is_hash_table(x):
    return x.__class__ is HashTable


@prim("hash-table-set!")
def ht_set(t, k, v):
    need_ht("hash-table-set!", t).d[hkey(k)] = (k, v)
    return UNSPEC


@prim("hash-table-ref/default", "hash-table-ref-default")
def ht_ref_default(t, k, default):
    e = need_ht("hash-table-ref/default", t).d.get(hkey(k))
    return default if e is None else e[1]


@prim("hash-table-contains?", "hash-table-exists?")
def ht_contains(t, k):
    return hkey(k) in need_ht("hash-table-contains?", t).d


@prim("hash-table-delete!", "hash-table-remove!")
def ht_delete(t, k):
    need_ht("hash-table-delete!", t).d.pop(hkey(k), None)
    return UNSPEC


@prim("hash-table-count", "hash-table-size")
def ht_count(t):
    return len(need_ht("hash-table-count", t).d)


@prim("hash-table-keys")
def ht_keys(t):
    return py_to_list([e[0] for e in need_ht("hash-table-keys", t).d.values()])


@prim("hash-table-values")
def ht_values(t):
    return py_to_list([e[1] for e in need_ht("hash-table-values", t).d.values()])


@prim("hash-table->alist")
def ht_alist(t):
    return py_to_list([Pair(*e) for e in need_ht("hash-table->alist", t).d.values()])


@prim("hash-table-clear!")
def ht_clear(t):
    need_ht("hash-table-clear!", t).d.clear()
    return UNSPEC


# ---------------------------------------------------------------- 輸出與雜項
def _out(s):
    sys.stdout.write(s)


@prim("display")
def display(x, port=None):
    _out(to_string(x, False))
    return UNSPEC


@prim("write", "pp")
def write(x, port=None):
    _out(to_string(x, True))
    return UNSPEC


@prim("write-string")
def write_string(x, port=None):
    _out(need_str("write-string", x))
    return UNSPEC


@prim("write-char")
def write_char(x, port=None):
    _out(need_char("write-char", x).ch)
    return UNSPEC


@prim("newline")
def newline(port=None):
    _out("\n")
    return UNSPEC


@prim("write-line")
def write_line(x, port=None):
    _out(to_string(x, True) + "\n")
    return UNSPEC


@prim("fresh-line")
def fresh_line(port=None):
    return UNSPEC


@prim("runtime", "real-time")
def runtime():
    return time.time()


@prim("current-time")
def current_time():
    return int(time.time())


@prim("exit", "%exit")
def p_exit(code=0):
    raise SchemeExit(0 if code is True or code is UNSPEC else (1 if code is False else code))


def format_error(msg, irritants):
    parts = [msg if msg.__class__ is str else to_string(msg, True)]
    parts += [to_string(x, True) for x in irritants]
    return " ".join(parts)


@prim("error")
def p_error(msg="error", *irritants):
    raise SchemeError(format_error(msg, irritants))


@prim("raise")
def p_raise(obj):
    raise SchemeError("uncaught raise: " + to_string(obj, True) + " / 未被處理的 raise", obj)


@prim("assert")
def p_assert(x, *msg):
    if x is False:
        raise SchemeError(bi("assertion failed", "斷言失敗") +
                          ("" if not msg else ": " + " ".join(to_string(m) for m in msg)))
    return UNSPEC


@prim("void")
def void(*_):
    return UNSPEC


@prim("record?", pure=True)
def is_record(x):
    return x.__class__ is Record


@prim("record-type-name", pure=True)
def record_type_name(x):
    return sym(x.name if x.__class__ is RecordType else x.rtype.name)


@prim("promise?", pure=True)
def is_promise(x):
    from .datatypes import Promise
    return x.__class__ is Promise

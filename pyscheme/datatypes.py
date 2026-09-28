"""Scheme 的資料表示法。

  Scheme          Python
  --------------  ------------------------------------
  整數/浮點/分數  int / float / fractions.Fraction
  #t #f           True / False   (只有 #f 是假值)
  字串            str
  符號            Symbol (有 intern,所以可以用 is 比較)
  字元            Char (同樣 intern)
  '()             NIL (唯一的空串列物件)
  序對            Pair(car, cdr)
  向量            Python list
"""
from fractions import Fraction

from .errors import SchemeError, bi


class Symbol:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


_symtab = {}


def sym(name):
    """取得 (或建立) 已 intern 的符號。"""
    s = _symtab.get(name)
    if s is None:
        s = _symtab[name] = Symbol(name)
    return s


class Nil:
    __slots__ = ()

    def __repr__(self):
        return "()"


NIL = Nil()


class Unspecified:
    __slots__ = ()

    def __repr__(self):
        return "#<unspecified>"


UNSPEC = Unspecified()


class Pair:
    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr


class Char:
    __slots__ = ("ch",)

    def __init__(self, ch):
        self.ch = ch


_chartab = {}


def char(c):
    x = _chartab.get(c)
    if x is None:
        x = _chartab[c] = Char(c)
    return x


class Env:
    """環境:一個 dict 加上指向外層環境的指標。"""

    __slots__ = ("vars", "parent")

    def __init__(self, vars, parent):
        self.vars = vars
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def lookup(self, name):
        env = self
        while env is not None:
            v = env.vars
            if name in v:
                return v[name]
            env = env.parent
        raise SchemeError(bi(f"unbound variable: {name.name}",
                             f"未定義的變數: {name.name}"))

    def set(self, name, value):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise SchemeError(bi(f"set!: unbound variable: {name.name}",
                             f"set!: 未定義的變數: {name.name}"))


class Closure:
    __slots__ = ("params", "rest", "body", "env", "name")

    def __init__(self, params, rest, body, env, name):
        self.params = params
        self.rest = rest
        self.body = body
        self.env = env
        self.name = name


class Primitive:
    """用 Python 寫的內建程序。pure=True 表示沒有副作用,可以在快速路徑內直接呼叫。"""

    __slots__ = ("name", "fn", "pure", "min", "max")

    def __init__(self, name, fn, pure=False, min=None, max=None):
        self.name = name
        self.fn = fn
        self.pure = pure
        if min is None:
            co = fn.__code__
            n = co.co_argcount
            nd = len(fn.__defaults__ or ())
            min = n - nd
            max = (1 << 30) if co.co_flags & 4 else n
        self.min = min
        self.max = max


class SpecialPrim:
    """需要直接操作直譯器狀態的程序 (apply、call/cc、dynamic-wind ...)。"""

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class Continuation:
    __slots__ = ("k", "winds")

    def __init__(self, k, winds):
        self.k = k
        self.winds = winds


class Promise:
    __slots__ = ("done", "value", "node", "env")

    def __init__(self, node, env):
        self.done = False
        self.value = None
        self.node = node
        self.env = env


class RecordType:
    __slots__ = ("name", "fields")

    def __init__(self, name, fields):
        self.name = name
        self.fields = fields


class Record:
    __slots__ = ("rtype", "values")

    def __init__(self, rtype, values):
        self.rtype = rtype
        self.values = values


class HashTable:
    __slots__ = ("d",)

    def __init__(self):
        self.d = {}


NUMT = frozenset((int, float, Fraction))


def is_num(x):
    return x.__class__ in NUMT


def py_to_list(items, tail=NIL):
    r = tail
    for x in reversed(items):
        r = Pair(x, r)
    return r


def list_to_py(x, who="list"):
    """Scheme 的正規串列轉成 Python list;不是正規串列就丟錯。"""
    out = []
    p = x
    while p.__class__ is Pair:
        out.append(p.car)
        p = p.cdr
    if p is not NIL:
        from .printer import to_string
        raise SchemeError(bi(f"{who}: expected proper list, got {to_string(x, True)}",
                             f"{who}: 需要正規串列(list),卻收到 {to_string(x, True)}"))
    return out


def is_list(x):
    while x.__class__ is Pair:
        x = x.cdr
    return x is NIL

"""AST 節點。Analyzer 把 S-expression 轉成這些節點,machine 再執行它們。

leaf  節點 (Const/Ref/Lambda/Delay):可以直接用 ev(env) 求值,不需要堆疊框架。
cand  節點:App 的運算元全是 leaf 或 cand 時為 True,machine 會先嘗試「不推框架」的
      快速求值;遇到不是純內建程序時丟 Bail,退回一般路徑。
"""
from .datatypes import Closure, Primitive, Promise
from .errors import SchemeError, bi


class Bail(Exception):
    """快速求值失敗,請改走完整的 CEK 路徑。"""


class Node:
    __slots__ = ()
    leaf = False
    cand = False


class Const(Node):
    __slots__ = ("value",)
    leaf = True
    cand = True

    def __init__(self, value):
        self.value = value

    def ev(self, env):
        return self.value


class Ref(Node):
    __slots__ = ("name",)
    leaf = True
    cand = True

    def __init__(self, name):
        self.name = name

    def ev(self, env):
        name = self.name
        while env is not None:
            v = env.vars
            if name in v:
                return v[name]
            env = env.parent
        raise SchemeError(bi(f"unbound variable: {name.name}",
                             f"未定義的變數: {name.name}"))


class LambdaNode(Node):
    __slots__ = ("params", "rest", "body", "name")
    leaf = True
    cand = True

    def __init__(self, params, rest, body, name=None):
        self.params = params
        self.rest = rest
        self.body = body
        self.name = name

    def ev(self, env):
        return Closure(self.params, self.rest, self.body, env, self.name)


class Delay(Node):
    __slots__ = ("body",)
    leaf = True
    cand = True

    def __init__(self, body):
        self.body = body

    def ev(self, env):
        return Promise(self.body, env)


class If(Node):
    __slots__ = ("test", "conseq", "alt")

    def __init__(self, test, conseq, alt):
        self.test = test
        self.conseq = conseq
        self.alt = alt


class Seq(Node):
    __slots__ = ("nodes",)

    def __init__(self, nodes):
        self.nodes = nodes


class Define(Node):
    __slots__ = ("name", "expr")

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class SetBang(Node):
    __slots__ = ("name", "expr")

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class Or(Node):
    __slots__ = ("nodes",)

    def __init__(self, nodes):
        self.nodes = nodes


class App(Node):
    __slots__ = ("fn", "args", "parts", "cand")

    def __init__(self, fn, args):
        self.fn = fn
        self.args = args
        self.parts = [fn] + args
        self.cand = fn.leaf and all(a.cand for a in args)

    def ev(self, env):
        f = self.fn.ev(env)
        if f.__class__ is Primitive and f.pure:
            args = [a.ev(env) for a in self.args]
            n = len(args)
            if n < f.min or n > f.max:
                raise arity_error(f, n)
            try:
                return f.fn(*args)
            except (TypeError, ValueError, ZeroDivisionError, OverflowError,
                    IndexError, KeyError, AttributeError) as e:
                raise prim_error(f, e)
        raise Bail


def arity_error(f, n):
    if f.max >= 1 << 30:
        need = f"at least {f.min}"
        zh = f"至少 {f.min}"
    elif f.min == f.max:
        need = str(f.min)
        zh = str(f.min)
    else:
        need = f"{f.min} to {f.max}"
        zh = f"{f.min} 到 {f.max}"
    return SchemeError(bi(f"{f.name} expects {need} argument(s), got {n}",
                          f"{f.name} 需要 {zh} 個參數,卻收到 {n} 個"))


def prim_error(f, e):
    return SchemeError(bi(f"{f.name}: invalid arguments ({e})",
                          f"{f.name}: 參數不合法 ({e})"))

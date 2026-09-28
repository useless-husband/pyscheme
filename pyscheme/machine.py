"""CEK 機器:Control (要算什麼) / Environment (環境) / Kontinuation (接下來要做什麼)。

整個直譯器是一個 while 迴圈,沒有任何 Python 遞迴:
  * 「接下來要做什麼」存在堆積 (heap) 上的 Frame 鏈結串列,不是 Python 呼叫堆疊,
    所以非尾遞迴再深也不會 RecursionError (上限由 max_depth 控制,避免吃光記憶體)。
  * 尾呼叫不推新的 Frame,所以迴圈跑一百萬次也只用固定空間。
  * Frame 鏈是不可變的,所以 call/cc 只要記住目前的 k 指標就是完整的 continuation,
    可以重複進入 (generator 就是這樣做的)。
"""
from pathlib import Path

from .analyzer import Analyzer
from .datatypes import (NIL, UNSPEC, Closure, Continuation, Env, Pair, Primitive,
                        Promise, SpecialPrim, py_to_list, sym, list_to_py)
from .errors import SchemeError, bi
from .nodes import (App, Bail, Const, Define, If, Or, Seq, SetBang, arity_error,
                    prim_error)
from .primitives import PRIMS
from .printer import to_string
from .reader import Reader

EVAL, RET, APPLY, ARGS = 0, 1, 2, 3
(K_HALT, K_ARG, K_IF, K_SEQ, K_DEF, K_SET, K_OR, K_FORCE, K_DW1, K_DW2, K_DW3,
 K_WINDSEQ, K_CATCH, K_TOP) = range(14)

PRIM_ERRORS = (TypeError, ValueError, ZeroDivisionError, OverflowError, IndexError,
               KeyError, AttributeError)


class Frame:
    __slots__ = ("tag", "a", "b", "c", "next", "depth")

    def __init__(self, tag, a, b, c, nxt):
        self.tag = tag
        self.a = a
        self.b = b
        self.c = c
        self.next = nxt
        self.depth = nxt.depth + 1


class HaltFrame(Frame):
    __slots__ = ()

    def __init__(self):
        self.tag = K_HALT
        self.a = self.b = self.c = self.next = None
        self.depth = 0


HALT = HaltFrame()
SPECIALS = ("apply", "call-with-current-continuation", "call/cc", "dynamic-wind", "force",
            "eval", "catch-error", "call-with-escape-continuation")
DEFAULT_MAX_DEPTH = 400_000


def unwind_plan(cur, target):
    """從 dynamic-wind 狀態 cur 走到 target 需要呼叫的 thunk 清單:[(thunk, 呼叫時的 winds)]。"""
    steps, entries = [], []
    a, b = cur, target
    da = a[3] if a else 0
    db = b[3] if b else 0
    while da > db:
        steps.append((a[1], a[2]))
        a, da = a[2], da - 1
    while db > da:
        entries.append(b)
        b, db = b[2], db - 1
    while a is not b:
        steps.append((a[1], a[2]))
        a = a[2]
        entries.append(b)
        b = b[2]
    for w in reversed(entries):
        steps.append((w[0], w[2]))
    return steps


class Interpreter:
    def __init__(self, load_prelude=True):
        self.analyzer = Analyzer()
        self.max_depth = DEFAULT_MAX_DEPTH
        self.global_env = Env({}, None)
        v = self.global_env.vars
        for name, p in PRIMS.items():
            v[sym(name)] = p
        for name in SPECIALS:
            v[sym(name)] = SpecialPrim(name)
        v[sym("interaction-environment")] = Primitive("interaction-environment",
                                                      lambda: self.global_env, True)
        v[sym("system-global-environment")] = self.global_env
        v[sym("user-initial-environment")] = self.global_env
        self.prelude_names = set()
        if load_prelude:
            self.load_prelude()
            self.prelude_names = {s.name for s in self.global_env.vars}

    # ------------------------------------------------------------ 對外介面
    def load_prelude(self):
        text = (Path(__file__).with_name("prelude.scm")).read_text(encoding="utf-8")
        self.run_string(text)

    def run_string(self, text):
        """依序求值 text 內所有運算式,回傳最後一個值。

        整段程式共用一條 continuation 鏈 (K_TOP 框架),所以 call/cc 抓到的
        continuation 包含「檔案接下來的其他運算式」,就像在 Scheme 檔案裡該有的樣子。
        """
        forms = Reader(text).read_all()
        return self.execute(None, self.global_env, forms)

    def eval_datum(self, datum):
        node = self.analyzer.analyze(datum)
        return self.execute(node, self.global_env)

    def run_file(self, path):
        return self.run_string(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------ 核心迴圈
    def bind_slow(self, f, args):
        n, m = len(f.params), len(args)
        name = f.name.name if f.name else None
        if f.rest is None and m != n or m < n:
            label = f"procedure '{name}'" if name else "anonymous procedure"
            zh = f"程序 '{name}'" if name else "匿名程序"
            if f.rest is None:
                raise SchemeError(bi(f"{label} expects {n} argument(s), got {m}",
                                     f"{zh} 需要 {n} 個參數,卻收到 {m} 個"))
            raise SchemeError(bi(f"{label} expects at least {n} argument(s), got {m}",
                                 f"{zh} 至少需要 {n} 個參數,卻收到 {m} 個"))
        d = dict(zip(f.params, args))
        if f.rest is not None:
            d[f.rest] = py_to_list(args[n:])
        return Env(d, f.env)

    def execute(self, node, env, forms=None):
        k = HALT
        winds = None  # dynamic-wind 狀態:(before, after, parent, depth) 或 None
        mode = EVAL
        val = None
        f = args = vals = None
        i = 0
        max_depth = self.max_depth
        if forms is not None:
            k = Frame(K_TOP, forms, None, 0, HALT)
            val = UNSPEC
            mode = RET
        while True:
            try:
                while True:
                    if mode == EVAL:
                        t = node.__class__
                        if t is App:
                            if node.cand:
                                f = node.fn.ev(env)
                                try:
                                    args = [a.ev(env) for a in node.args]
                                except Bail:
                                    vals = []
                                    i = 0
                                    mode = ARGS
                                    continue
                                mode = APPLY
                            else:
                                vals = []
                                i = 0
                                mode = ARGS
                        elif t is If:
                            test = node.test
                            if test.cand:
                                try:
                                    node = node.alt if test.ev(env) is False else node.conseq
                                    continue
                                except Bail:
                                    pass
                            k = Frame(K_IF, node, env, None, k)
                            node = test
                        elif node.leaf:
                            val = node.ev(env)
                            mode = RET
                        elif t is Seq:
                            k = Frame(K_SEQ, node, env, 1, k)
                            node = node.nodes[0]
                        elif t is Define:
                            x = node.expr
                            if x.leaf:
                                env.vars[node.name] = val = x.ev(env)
                                val = UNSPEC
                                mode = RET
                            else:
                                k = Frame(K_DEF, node, env, None, k)
                                node = x
                        elif t is SetBang:
                            x = node.expr
                            if x.leaf:
                                env.set(node.name, x.ev(env))
                                val = UNSPEC
                                mode = RET
                            else:
                                k = Frame(K_SET, node, env, None, k)
                                node = x
                        elif t is Or:
                            k = Frame(K_OR, node, env, 1, k)
                            node = node.nodes[0]
                        else:
                            raise SchemeError(f"internal error: unknown node {t.__name__}")

                    elif mode == ARGS:
                        parts = node.parts
                        n = len(parts)
                        while i < n:
                            p = parts[i]
                            if p.leaf:
                                vals.append(p.ev(env))
                                i += 1
                            else:
                                k = Frame(K_ARG, node, env, (vals, i), k)
                                node = p
                                mode = EVAL
                                break
                        else:
                            f = vals[0]
                            args = vals[1:]
                            mode = APPLY

                    elif mode == APPLY:
                        c = f.__class__
                        if c is Closure:
                            params = f.params
                            if f.rest is None and len(args) == len(params):
                                env = Env(dict(zip(params, args)), f.env)
                            else:
                                env = self.bind_slow(f, args)
                            if k.depth > max_depth:
                                raise SchemeError(bi(
                                    f"recursion depth exceeded (more than {max_depth} pending calls)",
                                    f"遞迴太深(等待中的呼叫超過 {max_depth} 層)"))
                            node = f.body
                            mode = EVAL
                        elif c is Primitive:
                            n = len(args)
                            if n < f.min or n > f.max:
                                raise arity_error(f, n)
                            try:
                                val = f.fn(*args)
                            except PRIM_ERRORS as e:
                                raise prim_error(f, e)
                            mode = RET
                        elif c is Continuation:
                            val = args[0] if len(args) == 1 else UNSPEC
                            if f.winds is winds:
                                k = f.k
                                mode = RET
                            else:
                                steps = unwind_plan(winds, f.winds)
                                final = (RET, f.k, val, f.winds)
                                k = Frame(K_WINDSEQ, steps, final, 0, k)
                                mode = RET
                        elif c is SpecialPrim:
                            name = f.name
                            if name == "apply":
                                if not args:
                                    raise SchemeError(bi("apply expects at least 1 argument, got 0",
                                                         "apply 至少需要 1 個參數,卻收到 0 個"))
                                f = args[0]
                                if len(args) == 1:
                                    args = []
                                else:
                                    args = list(args[1:-1]) + list_to_py(args[-1], "apply")
                            elif name in ("call/cc", "call-with-current-continuation",
                                          "call-with-escape-continuation"):
                                if len(args) != 1:
                                    raise SchemeError(bi(f"{name} expects 1 argument, got {len(args)}",
                                                         f"{name} 需要 1 個參數,卻收到 {len(args)} 個"))
                                f, args = args[0], [Continuation(k, winds)]
                            elif name == "dynamic-wind":
                                if len(args) != 3:
                                    raise SchemeError(bi(f"dynamic-wind expects 3 arguments, got {len(args)}",
                                                         f"dynamic-wind 需要 3 個參數,卻收到 {len(args)} 個"))
                                k = Frame(K_DW1, tuple(args), None, None, k)
                                f, args = args[0], []
                            elif name == "force":
                                p = args[0] if len(args) == 1 else None
                                if p.__class__ is not Promise:
                                    val = p if len(args) == 1 else UNSPEC
                                    mode = RET
                                elif p.done:
                                    val = p.value
                                    mode = RET
                                else:
                                    k = Frame(K_FORCE, p, None, None, k)
                                    node, env = p.node, p.env
                                    mode = EVAL
                            elif name == "eval":
                                if not args:
                                    raise SchemeError(bi("eval expects 1 or 2 arguments, got 0",
                                                         "eval 需要 1 或 2 個參數,卻收到 0 個"))
                                node = self.analyzer.analyze(args[0])
                                env = self.global_env
                                mode = EVAL
                            elif name == "catch-error":
                                if len(args) != 2:
                                    raise SchemeError(bi(f"catch-error expects 2 arguments, got {len(args)}",
                                                         f"catch-error 需要 2 個參數,卻收到 {len(args)} 個"))
                                k = Frame(K_CATCH, args[1], winds, None, k)
                                f, args = args[0], []
                        else:
                            raise SchemeError(bi(f"not a procedure: {to_string(f, True)}",
                                                 f"不是程序,不能呼叫: {to_string(f, True)}"))

                    else:  # RET
                        fr = k
                        tag = fr.tag
                        k = fr.next
                        if tag == K_ARG:
                            node = fr.a
                            env = fr.b
                            vals = fr.c[0] + [val]
                            i = fr.c[1] + 1
                            mode = ARGS
                        elif tag == K_IF:
                            nd = fr.a
                            env = fr.b
                            node = nd.alt if val is False else nd.conseq
                            mode = EVAL
                        elif tag == K_SEQ:
                            sq = fr.a
                            nodes = sq.nodes
                            j = fr.c
                            env = fr.b
                            if j == len(nodes) - 1:
                                node = nodes[j]
                            else:
                                k = Frame(K_SEQ, sq, env, j + 1, k)
                                node = nodes[j]
                            mode = EVAL
                        elif tag == K_HALT:
                            return val
                        elif tag == K_DEF:
                            fr.b.vars[fr.a.name] = val
                            val = UNSPEC
                        elif tag == K_SET:
                            fr.b.set(fr.a.name, val)
                            val = UNSPEC
                        elif tag == K_OR:
                            if val is False:
                                nodes = fr.a.nodes
                                j = fr.c
                                env = fr.b
                                if j == len(nodes) - 1:
                                    node = nodes[j]
                                else:
                                    k = Frame(K_OR, fr.a, env, j + 1, k)
                                    node = nodes[j]
                                mode = EVAL
                        elif tag == K_FORCE:
                            p = fr.a
                            if not p.done:
                                p.done = True
                                p.value = val
                                p.node = p.env = None
                            val = p.value
                        elif tag == K_DW1:
                            before, thunk, after = fr.a
                            winds = (before, after, winds, (winds[3] if winds else 0) + 1)
                            k = Frame(K_DW2, after, None, None, k)
                            f, args = thunk, []
                            mode = APPLY
                        elif tag == K_DW2:
                            winds = winds[2]
                            k = Frame(K_DW3, val, None, None, k)
                            f, args = fr.a, []
                            mode = APPLY
                        elif tag == K_DW3:
                            val = fr.a
                        elif tag == K_WINDSEQ:
                            steps, final, j = fr.a, fr.b, fr.c
                            if j < len(steps):
                                thunk, w = steps[j]
                                winds = w
                                k = Frame(K_WINDSEQ, steps, final, j + 1, k)
                                f, args = thunk, []
                                mode = APPLY
                            else:
                                m, k, payload, winds = final
                                if m == RET:
                                    val = payload
                                else:
                                    f, args = payload
                                mode = m
                        elif tag == K_TOP:
                            j = fr.c
                            if j < len(fr.a):
                                node = self.analyzer.analyze(fr.a[j])
                                env = self.global_env
                                k = Frame(K_TOP, fr.a, None, j + 1, k)
                                mode = EVAL
                        elif tag == K_CATCH:
                            pass  # thunk 正常結束:值原封不動往外傳
                        else:
                            raise SchemeError(f"internal error: bad frame {tag}")
            except SchemeError as e:
                err = e
            except RecursionError:
                err = SchemeError(bi("recursion too deep in a builtin (e.g. printing or comparing "
                                     "a deeply nested structure)",
                                     "內建程序遇到太深的巢狀結構"))
            # ---- 錯誤處理:找最近的 catch-error 框架 ----
            fr = k
            while fr is not None and fr.tag != K_CATCH:
                fr = fr.next
            if fr is None:
                raise err
            handler, target = fr.a, fr.b
            steps = unwind_plan(winds, target)
            final = (APPLY, fr.next, (handler, [err.payload]), target)
            k = Frame(K_WINDSEQ, steps, final, 0, k)
            mode = RET

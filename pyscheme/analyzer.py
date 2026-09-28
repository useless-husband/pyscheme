"""Analyzer:S-expression -> AST 節點,同時負責巨集展開與語法糖 (let/cond/do ...)。

scope 是「目前被局部變數遮蔽的名稱」集合:若 (if ...) 的 if 被使用者當成變數綁定,
就不再視為特殊形式。
"""
from .datatypes import NIL, UNSPEC, Pair, Record, RecordType, Symbol, py_to_list, sym, Primitive
from .errors import SchemeError, bi
from .nodes import (App, Const, Define, Delay, If, LambdaNode, Or, Ref, Seq,
                    SetBang)
from .primitives import PRIMS
from .printer import to_string
from .syntax_rules import ELLIPSIS, Macro

S = sym
ELSE, ARROW = S("else"), S("=>")
DEFINE, BEGIN, LAMBDA = S("define"), S("begin"), S("lambda")
DEFINE_SYNTAX, DEFINE_RECORD = S("define-syntax"), S("define-record-type")
UNQUOTE, UNQUOTE_SPLICING, QUASIQUOTE = S("unquote"), S("unquote-splicing"), S("quasiquote")
QUOTE = S("quote")
EMPTY = frozenset()


def bad(form, what=None):
    text = to_string(form, True)
    return SchemeError(bi(f"bad syntax: {text}", f"語法錯誤: {text}"))


def items(form, whole=None):
    """Scheme 串列 -> Python list,不是正規串列就報語法錯誤。"""
    out = []
    while form.__class__ is Pair:
        out.append(form.car)
        form = form.cdr
    if form is not NIL:
        raise bad(whole if whole is not None else form)
    return out


def prim_call(name, *args):
    return App(Const(PRIMS[name]), list(args))


def seq(nodes):
    return nodes[0] if len(nodes) == 1 else Seq(nodes)


def named_loop(name, lam, inits):
    """((letrec ((name lam)) name) init ...),init 在外層環境求值。"""
    maker = LambdaNode([], None, Seq([Define(name, lam), Ref(name)]))
    return App(App(maker, []), inits)


class Analyzer:
    def __init__(self):
        self.macros = {}
        self.special = {
            S("quote"): self.a_quote, S("quasiquote"): self.a_quasiquote,
            S("lambda"): self.a_lambda, S("define"): self.a_define,
            S("set!"): self.a_set, S("if"): self.a_if, S("cond"): self.a_cond,
            S("case"): self.a_case, S("and"): self.a_and, S("or"): self.a_or,
            S("when"): self.a_when, S("unless"): self.a_unless, S("let"): self.a_let,
            S("let*"): self.a_let_star, S("letrec"): self.a_letrec,
            S("letrec*"): self.a_letrec, S("do"): self.a_do, S("begin"): self.a_begin,
            S("delay"): self.a_delay, S("make-promise-lazy"): self.a_delay,
            S("cons-stream"): self.a_cons_stream,
            S("define-record-type"): self.a_record, S("define-syntax"): self.a_define_syntax,
            S("named-lambda"): self.a_named_lambda,
        }

    # ------------------------------------------------------------ 入口
    def analyze(self, x, scope=EMPTY):
        c = x.__class__
        if c is Symbol:
            return Ref(x)
        if c is Pair:
            head = x.car
            if head.__class__ is Symbol and head not in scope:
                m = self.macros.get(head)
                if m is not None:
                    return self.analyze(m.expand(x), scope)
                sf = self.special.get(head)
                if sf is not None:
                    return sf(x, scope)
            fn = self.analyze(head, scope)
            return App(fn, [self.analyze(a, scope) for a in items(x.cdr, x)])
        if x is NIL:
            raise SchemeError(bi("combination must not be empty: ()", "運算式不可為空: ()"))
        return Const(x)

    def macroexpand_1(self, x):
        if x.__class__ is Pair and x.car.__class__ is Symbol:
            m = self.macros.get(x.car)
            if m is not None:
                return m.expand(x)
        return x

    # ------------------------------------------------------------ 本體 (含內部 define)
    def expand_body(self, forms, scope):
        """展開巨集頭、攤平 begin、收集內部 define 的名稱。"""
        queue = list(forms)
        out, names = [], []
        while queue:
            f = queue.pop(0)
            if f.__class__ is Pair and f.car.__class__ is Symbol and f.car not in scope:
                h = f.car
                if h in self.macros:
                    queue.insert(0, self.macros[h].expand(f))
                    continue
                if h is BEGIN:
                    queue[0:0] = items(f.cdr, f)
                    continue
                if h is DEFINE_SYNTAX:
                    self.a_define_syntax(f, scope)
                    continue
                if h is DEFINE:
                    t = f.cdr.car if f.cdr.__class__ is Pair else None
                    while t.__class__ is Pair:
                        t = t.car
                    if t.__class__ is Symbol:
                        names.append(t)
                elif h is DEFINE_RECORD:
                    names.extend(self.record_names(f))
            out.append(f)
        return out, names

    def body(self, forms, scope, whole=None):
        forms, names = self.expand_body(forms, scope)
        scope = scope | frozenset(names)
        nodes = [self.analyze(f, scope) for f in forms]
        if not nodes:
            raise bad(whole if whole is not None else NIL)
        return seq(nodes)

    # ------------------------------------------------------------ 基本形式
    def a_quote(self, x, scope):
        a = items(x)
        if len(a) != 2:
            raise bad(x)
        return Const(a[1])

    def a_if(self, x, scope):
        a = items(x)
        if len(a) not in (3, 4):
            raise bad(x)
        alt = self.analyze(a[3], scope) if len(a) == 4 else Const(UNSPEC)
        return If(self.analyze(a[1], scope), self.analyze(a[2], scope), alt)

    def a_set(self, x, scope):
        a = items(x)
        if len(a) != 3 or a[1].__class__ is not Symbol:
            raise bad(x)
        return SetBang(a[1], self.analyze(a[2], scope))

    def a_begin(self, x, scope):
        a = items(x)[1:]
        if not a:
            return Const(UNSPEC)
        return seq([self.analyze(f, scope) for f in a])

    def parse_params(self, params, whole):
        names, rest = [], None
        while params.__class__ is Pair:
            if params.car.__class__ is not Symbol:
                raise bad(whole)
            names.append(params.car)
            params = params.cdr
        if params is not NIL:
            if params.__class__ is not Symbol:
                raise bad(whole)
            rest = params
        return names, rest

    def make_lambda(self, params, body, scope, name, whole):
        names, rest = self.parse_params(params, whole)
        inner = scope | frozenset(names + ([rest] if rest else []))
        return LambdaNode(names, rest, self.body(items(body, whole), inner, whole), name)

    def a_lambda(self, x, scope):
        if x.cdr.__class__ is not Pair:
            raise bad(x)
        return self.make_lambda(x.cdr.car, x.cdr.cdr, scope, None, x)

    def a_named_lambda(self, x, scope):
        spec = x.cdr.car
        return self.make_lambda(spec.cdr, x.cdr.cdr, scope, spec.car, x)

    def a_define(self, x, scope):
        if x.cdr.__class__ is not Pair:
            raise bad(x)
        target = x.cdr.car
        if target.__class__ is Pair:
            name, params, body = target.car, target.cdr, x.cdr.cdr
            if name.__class__ is Pair:  # 柯里化 (define ((f a) b) ...)
                inner = Pair(LAMBDA, Pair(params, body))
                return self.a_define(py_to_list([DEFINE, name, inner]), scope)
            if name.__class__ is not Symbol:
                raise bad(x)
            expr = self.make_lambda(params, body, scope, name, x)
        elif target.__class__ is Symbol:
            rest = items(x.cdr.cdr, x)
            if len(rest) > 1:
                raise bad(x)
            expr = self.analyze(rest[0], scope) if rest else Const(UNSPEC)
            name = target
            if expr.__class__ is LambdaNode and expr.name is None:
                expr.name = name
        else:
            raise bad(x)
        if not scope:
            self.macros.pop(name, None)
        return Define(name, expr)

    def a_define_syntax(self, x, scope):
        a = items(x)
        if len(a) != 3 or a[1].__class__ is not Symbol:
            raise bad(x)
        spec = a[2]
        if spec.__class__ is not Pair or spec.car is not S("syntax-rules"):
            raise SchemeError(bi("define-syntax: only syntax-rules is supported",
                                 "define-syntax: 只支援 syntax-rules"))
        rest = spec.cdr
        ellipsis = ELLIPSIS
        if rest.car.__class__ is Symbol:
            ellipsis = rest.car
            rest = rest.cdr
        literals = items(rest.car, x)
        rules = []
        for r in items(rest.cdr, x):
            parts = items(r, x)
            if len(parts) != 2 or parts[0].__class__ is not Pair:
                raise bad(x)
            rules.append((parts[0], parts[1]))
        self.macros[a[1]] = Macro(a[1], literals, rules, ellipsis)
        return Const(UNSPEC)

    # ------------------------------------------------------------ 條件類
    def clause_body(self, forms, scope, whole):
        nodes = [self.analyze(f, scope) for f in items(forms, whole)]
        return seq(nodes)

    def a_cond(self, x, scope):
        return self.cond_rec(items(x)[1:], scope, x)

    def cond_rec(self, clauses, scope, whole):
        if not clauses:
            return Const(UNSPEC)
        clause, rest = clauses[0], clauses[1:]
        if clause.__class__ is not Pair:
            raise bad(whole)
        if clause.car is ELSE and ELSE not in scope:
            if clause.cdr is NIL:
                raise bad(whole)
            return self.clause_body(clause.cdr, scope, whole)
        test = self.analyze(clause.car, scope)
        if clause.cdr is NIL:
            return Or([test, self.cond_rec(rest, scope, whole)])
        if clause.cdr.car is ARROW:
            tmp = Symbol("cond-tmp")
            fn = self.analyze(clause.cdr.cdr.car, scope)
            body = If(Ref(tmp), App(fn, [Ref(tmp)]), self.cond_rec(rest, scope, whole))
            return App(LambdaNode([tmp], None, body), [test])
        return If(test, self.clause_body(clause.cdr, scope, whole),
                  self.cond_rec(rest, scope, whole))

    def a_case(self, x, scope):
        a = items(x)
        if len(a) < 2:
            raise bad(x)
        tmp = Symbol("case-key")
        key = self.analyze(a[1], scope)

        def rec(clauses):
            if not clauses:
                return Const(UNSPEC)
            cl = clauses[0]
            if cl.__class__ is not Pair:
                raise bad(x)
            if cl.car is ELSE:
                body = cl.cdr
                if body.__class__ is Pair and body.car is ARROW:
                    return App(self.analyze(body.cdr.car, scope), [Ref(tmp)])
                return self.clause_body(body, scope, x)
            test = prim_call("memv", Ref(tmp), Const(cl.car))
            body = cl.cdr
            if body.__class__ is Pair and body.car is ARROW:
                then = App(self.analyze(body.cdr.car, scope), [Ref(tmp)])
            else:
                then = self.clause_body(body, scope, x)
            return If(test, then, rec(clauses[1:]))
        return App(LambdaNode([tmp], None, rec(a[2:])), [key])

    def a_and(self, x, scope):
        a = items(x)[1:]
        if not a:
            return Const(True)
        nodes = [self.analyze(f, scope) for f in a]

        def rec(i):
            if i == len(nodes) - 1:
                return nodes[i]
            return If(nodes[i], rec(i + 1), Const(False))
        return rec(0)

    def a_or(self, x, scope):
        a = items(x)[1:]
        if not a:
            return Const(False)
        nodes = [self.analyze(f, scope) for f in a]
        return nodes[0] if len(nodes) == 1 else Or(nodes)

    def a_when(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        return If(self.analyze(a[1], scope),
                  seq([self.analyze(f, scope) for f in a[2:]]), Const(UNSPEC))

    def a_unless(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        return If(self.analyze(a[1], scope), Const(UNSPEC),
                  seq([self.analyze(f, scope) for f in a[2:]]))

    # ------------------------------------------------------------ let 家族
    def bindings(self, bs, whole):
        names, inits = [], []
        for b in items(bs, whole):
            if b.__class__ is Symbol:
                names.append(b)
                inits.append(None)
                continue
            parts = items(b, whole)
            if not parts or len(parts) > 2 or parts[0].__class__ is not Symbol:
                raise bad(whole)
            names.append(parts[0])
            inits.append(parts[1] if len(parts) == 2 else None)
        return names, inits

    def init_node(self, init, scope):
        return Const(UNSPEC) if init is None else self.analyze(init, scope)

    def a_let(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        if a[1].__class__ is Symbol:  # named let
            name = a[1]
            if len(a) < 4:
                raise bad(x)
            names, inits = self.bindings(a[2], x)
            init_nodes = [self.init_node(i, scope) for i in inits]
            inner = scope | frozenset(names) | {name}
            lam = LambdaNode(names, None, self.body(a[3:], inner, x), name)
            return named_loop(name, lam, init_nodes)
        names, inits = self.bindings(a[1], x)
        init_nodes = [self.init_node(i, scope) for i in inits]
        lam = LambdaNode(names, None, self.body(a[2:], scope | frozenset(names), x))
        return App(lam, init_nodes)

    def a_let_star(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        names, inits = self.bindings(a[1], x)

        def rec(i, sc):
            if i == len(names):
                return App(LambdaNode([], None, self.body(a[2:], sc, x)), [])
            init = self.init_node(inits[i], sc)
            return App(LambdaNode([names[i]], None, rec(i + 1, sc | {names[i]})), [init])
        return rec(0, scope)

    def a_letrec(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        names, inits = self.bindings(a[1], x)
        inner = scope | frozenset(names)
        defs = []
        for n, i in zip(names, inits):
            node = self.init_node(i, inner)
            if node.__class__ is LambdaNode and node.name is None:
                node.name = n
            defs.append(Define(n, node))
        body = self.body(a[2:], inner, x)
        return App(LambdaNode([], None, Seq(defs + [body])), [])

    def a_do(self, x, scope):
        a = items(x)
        if len(a) < 3:
            raise bad(x)
        specs = []
        for b in items(a[1], x):
            p = items(b, x)
            if len(p) not in (2, 3) or p[0].__class__ is not Symbol:
                raise bad(x)
            specs.append(p)
        names = [p[0] for p in specs]
        exit_clause = items(a[2], x)
        if not exit_clause:
            raise bad(x)
        loop = Symbol("do-loop")
        inner = scope | frozenset(names) | {loop}
        inits = [self.analyze(p[1], scope) for p in specs]
        steps = [self.analyze(p[2] if len(p) == 3 else p[0], inner) for p in specs]
        test = self.analyze(exit_clause[0], inner)
        res = seq([self.analyze(f, inner) for f in exit_clause[1:]]) \
            if len(exit_clause) > 1 else Const(UNSPEC)
        recur = App(Ref(loop), steps)
        body_nodes = [self.analyze(f, inner) for f in a[3:]]
        loop_body = If(test, res, seq(body_nodes + [recur]))
        lam = LambdaNode(names, None, loop_body, loop)
        return named_loop(loop, lam, inits)

    # ------------------------------------------------------------ delay / stream
    def a_delay(self, x, scope):
        a = items(x)
        if len(a) != 2:
            raise bad(x)
        return Delay(self.analyze(a[1], scope))

    def a_cons_stream(self, x, scope):
        a = items(x)
        if len(a) != 3:
            raise bad(x)
        return prim_call("cons", self.analyze(a[1], scope), Delay(self.analyze(a[2], scope)))

    # ------------------------------------------------------------ quasiquote
    def a_quasiquote(self, x, scope):
        a = items(x)
        if len(a) != 2:
            raise bad(x)
        return self.qq(a[1], 1, scope)

    def has_unquote(self, x):
        while x.__class__ is Pair:
            if x.car is UNQUOTE or x.car is UNQUOTE_SPLICING:
                return True
            if self.has_unquote(x.car):
                return True
            x = x.cdr
        if x.__class__ is list:
            return any(self.has_unquote(e) for e in x)
        return False

    def qq(self, x, depth, scope):
        if not self.has_unquote(x):
            return Const(x)
        if x.__class__ is list:
            return prim_call("list->vector", self.qq(py_to_list(x), depth, scope))
        head = x.car
        if head is UNQUOTE:
            if depth == 1:
                return self.analyze(x.cdr.car, scope)
            return prim_call("list", Const(UNQUOTE), self.qq(x.cdr.car, depth - 1, scope))
        if head is QUASIQUOTE:
            return prim_call("list", Const(QUASIQUOTE), self.qq(x.cdr.car, depth + 1, scope))
        if head.__class__ is Pair and head.car is UNQUOTE_SPLICING:
            if depth == 1:
                return prim_call("append", self.analyze(head.cdr.car, scope),
                                 self.qq(x.cdr, depth, scope))
            inner = prim_call("list", Const(UNQUOTE_SPLICING),
                              self.qq(head.cdr.car, depth - 1, scope))
            return prim_call("cons", inner, self.qq(x.cdr, depth, scope))
        return prim_call("cons", self.qq(head, depth, scope), self.qq(x.cdr, depth, scope))

    # ------------------------------------------------------------ define-record-type
    def record_names(self, f):
        a = items(f)
        names = []
        if len(a) < 4:
            return names
        if a[1].__class__ is Symbol:
            names.append(a[1])
        ctor = a[2]
        if ctor.__class__ is Pair:
            names.append(ctor.car)
        elif ctor.__class__ is Symbol:
            names.append(ctor)
        if a[3].__class__ is Symbol:
            names.append(a[3])
        for spec in a[4:]:
            if spec.__class__ is Pair:
                names.extend(s for s in items(spec.cdr) if s.__class__ is Symbol)
        return names

    def a_record(self, x, scope):
        a = items(x)
        if len(a) < 4:
            raise bad(x)
        tname = a[1].car if a[1].__class__ is Pair else a[1]
        if tname.__class__ is not Symbol:
            raise bad(x)
        fspecs = [items(s, x) if s.__class__ is Pair else [s] for s in a[4:]]
        fields = [s[0] for s in fspecs]
        pretty = tname.name
        if pretty.startswith("<") and pretty.endswith(">"):
            pretty = pretty[1:-1]
        rt = RecordType(pretty, fields)
        defs = [Define(tname, Const(rt))]
        ctor = a[2]
        if ctor is not False:
            if ctor.__class__ is Pair:
                cname, cfields = ctor.car, items(ctor.cdr, x)
            else:
                cname, cfields = ctor, fields
            idxs = []
            for cf in cfields:
                if cf not in fields:
                    raise bad(x)
                idxs.append(fields.index(cf))
            n_fields = len(fields)

            def make(*args, idxs=idxs, n=n_fields):
                vals = [False] * n
                for i, v in zip(idxs, args):
                    vals[i] = v
                return Record(rt, vals)
            defs.append(Define(cname, Const(Primitive(cname.name, make, False, len(idxs), len(idxs)))))
        if a[3].__class__ is Symbol:
            pname = a[3]
            defs.append(Define(pname, Const(Primitive(
                pname.name, lambda v: v.__class__ is Record and v.rtype is rt, True, 1, 1))))
        for spec in fspecs:
            idx = fields.index(spec[0])
            if len(spec) > 1:
                defs.append(Define(spec[1], Const(self.accessor(spec[1], rt, idx))))
            if len(spec) > 2:
                defs.append(Define(spec[2], Const(self.modifier(spec[2], rt, idx))))
        return Seq(defs + [Const(tname)])

    def accessor(self, name, rt, idx):
        def get(r):
            if r.__class__ is not Record or r.rtype is not rt:
                raise SchemeError(bi(f"{name.name}: expected a {rt.name} record, got {to_string(r, True)}",
                                     f"{name.name}: 需要 {rt.name} 記錄,卻收到 {to_string(r, True)}"))
            return r.values[idx]
        return Primitive(name.name, get, True, 1, 1)

    def modifier(self, name, rt, idx):
        def put(r, v):
            if r.__class__ is not Record or r.rtype is not rt:
                raise SchemeError(bi(f"{name.name}: expected a {rt.name} record, got {to_string(r, True)}",
                                     f"{name.name}: 需要 {rt.name} 記錄,卻收到 {to_string(r, True)}"))
            r.values[idx] = v
            return UNSPEC
        return Primitive(name.name, put, False, 2, 2)

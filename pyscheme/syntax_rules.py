"""syntax-rules 巨集:模式比對 + 樣板展開。

注意:這裡「沒有」做完整的衛生 (hygiene)。樣板裡引入的符號會原樣放進展開結果,
所以樣板裡自己用的暫存變數名稱可能與使用者的變數撞名 (詳見 README)。
"""
from .datatypes import NIL, Pair, Symbol, py_to_list, sym
from .errors import SchemeError, bi
from .printer import to_string

ELLIPSIS = sym("...")
UNDERSCORE = sym("_")


class Multi(list):
    """代表 `...` 比對到的一串結果 (與 Scheme 向量區分,所以另開一個類別)。"""


class Macro:
    def __init__(self, name, literals, rules, ellipsis=ELLIPSIS):
        self.name = name
        self.literals = set(literals)
        self.rules = rules  # [(pattern, template)]
        self.ellipsis = ellipsis

    def expand(self, form):
        for pattern, template in self.rules:
            binds = {}
            # 模式的第一個元素是巨集關鍵字本身,不參與比對
            if self.match(pattern.cdr, form.cdr, binds):
                return self.instantiate(template, binds)
        raise SchemeError(bi(f"no matching syntax rule for macro '{self.name.name}': "
                             f"{to_string(form, True)}",
                             f"巨集 '{self.name.name}' 沒有符合的語法規則: {to_string(form, True)}"))

    # ---------- 比對 ----------
    def match(self, pat, form, binds):
        c = pat.__class__
        if c is Symbol:
            if pat in self.literals:
                return form is pat
            if pat is not UNDERSCORE:
                binds[pat] = form
            return True
        if c is Pair:
            if pat.cdr.__class__ is Pair and pat.cdr.car is self.ellipsis:
                after = pat.cdr.cdr
                min_after = 0
                p = after
                while p.__class__ is Pair:
                    min_after += 1
                    p = p.cdr
                items, f = [], form
                while f.__class__ is Pair:
                    items.append(f.car)
                    f = f.cdr
                n_rep = len(items) - min_after
                if n_rep < 0:
                    return False
                matches = []
                for item in items[:n_rep]:
                    b = {}
                    if not self.match(pat.car, item, b):
                        return False
                    matches.append(b)
                for v in self.pattern_vars(pat.car):
                    binds[v] = Multi(m[v] for m in matches)
                return self.match(after, py_to_list(items[n_rep:], f), binds)
            if form.__class__ is not Pair:
                return False
            return self.match(pat.car, form.car, binds) and \
                self.match(pat.cdr, form.cdr, binds)
        if pat is NIL:
            return form is NIL
        if c is list:
            return form.__class__ is list and \
                self.match(py_to_list(pat), py_to_list(form), binds)
        from .primitives import equal
        return equal(pat, form)

    def pattern_vars(self, pat):
        c = pat.__class__
        if c is Symbol:
            if pat in self.literals or pat is self.ellipsis or pat is UNDERSCORE:
                return []
            return [pat]
        if c is Pair:
            return self.pattern_vars(pat.car) + self.pattern_vars(pat.cdr)
        if c is list:
            return [v for x in pat for v in self.pattern_vars(x)]
        return []

    # ---------- 展開 ----------
    def instantiate(self, t, binds):
        c = t.__class__
        if c is Symbol:
            if t in binds:
                v = binds[t]
                if v.__class__ is Multi:
                    raise SchemeError(bi(f"pattern variable '{t.name}' used without ...",
                                         f"樣板變數 '{t.name}' 使用時少了 ..."))
                return v
            return t
        if c is Pair:
            if t.car is self.ellipsis and t.cdr.__class__ is Pair:  # (... ...) 跳脫
                return self.escape(t.cdr.car)
            if t.cdr.__class__ is Pair and t.cdr.car is self.ellipsis:
                depth, rest = 1, t.cdr.cdr
                while rest.__class__ is Pair and rest.car is self.ellipsis:
                    depth += 1
                    rest = rest.cdr
                results = self.expand_ellipsis(t.car, binds, depth)
                return py_to_list(results, self.instantiate(rest, binds))
            return Pair(self.instantiate(t.car, binds), self.instantiate(t.cdr, binds))
        if c is list:
            out = self.instantiate(py_to_list(t), binds)
            res = []
            while out.__class__ is Pair:
                res.append(out.car)
                out = out.cdr
            return res
        return t

    def escape(self, t):
        return t

    def expand_ellipsis(self, sub, binds, depth):
        vs = [v for v in self.template_vars(sub)
              if v in binds and binds[v].__class__ is Multi]
        if not vs:
            raise SchemeError(bi("no ... variable in template before '...'",
                                 "樣板中 '...' 前面沒有可重複的樣板變數"))
        n = max(len(binds[v]) for v in vs)
        if any(len(binds[v]) != n for v in vs):
            raise SchemeError(bi("ellipsis variables have different lengths",
                                 "同一個 ... 內的樣板變數長度不一致"))
        out = []
        for i in range(n):
            b = dict(binds)
            for v in vs:
                b[v] = binds[v][i]
            if depth > 1:
                out.extend(self.expand_ellipsis(sub, b, depth - 1))
            else:
                out.append(self.instantiate(sub, b))
        return out

    def template_vars(self, t):
        c = t.__class__
        if c is Symbol:
            return [t]
        if c is Pair:
            return self.template_vars(t.car) + self.template_vars(t.cdr)
        if c is list:
            return [v for x in t for v in self.template_vars(x)]
        return []

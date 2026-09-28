import contextlib
import io
from pathlib import Path

from pyscheme import Interpreter
from pyscheme.datatypes import sym
from pyscheme.printer import to_string

ROOT = Path(__file__).resolve().parent.parent
SCHEME_DIR = ROOT / "tests" / "scheme"


def run(src, interp=None):
    """執行一段 Scheme,回傳 (最後一個值的 write 字串, 標準輸出)。"""
    interp = interp or Interpreter()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        val = interp.run_string(src)
    return to_string(val, True), buf.getvalue()


def value(src):
    return run(src)[0]


def counters(interp):
    v = interp.global_env.vars
    return v[sym("*pass*")], v[sym("*fail*")]

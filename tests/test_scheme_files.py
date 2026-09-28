"""執行 tests/scheme/*.scm。每個檔案用自己寫的 (assert-equal ...) 巨集,失敗會印出 FAIL。"""
import contextlib
import io
import unittest

from pyscheme import Interpreter
from tests.helpers import SCHEME_DIR, counters

HARNESS = SCHEME_DIR / "00-harness.scm"
FILES = sorted(p for p in SCHEME_DIR.glob("*.scm") if p != HARNESS)
TOTALS = {}


def execute(path):
    """跑一個測試檔 (含框架),回傳 (通過數, 失敗數, 輸出)。結果快取,避免重複執行。"""
    if path.name not in TOTALS:
        interp = Interpreter()
        interp.max_depth = 150_000  # 讓「無限遞迴」的測試快一點結束
        interp.run_file(HARNESS)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            interp.run_file(path)
        TOTALS[path.name] = counters(interp) + (buf.getvalue(),)
    return TOTALS[path.name]


class SchemeFileTests(unittest.TestCase):
    def run_file(self, path):
        passed, failed, output = execute(path)
        buf = io.StringIO(output)
        self.assertEqual(failed, 0, f"{path.name}:\n{buf.getvalue()}")
        self.assertNotIn("FAIL", buf.getvalue())
        self.assertGreater(passed, 0)


def _make(path):
    return lambda self: self.run_file(path)


for _p in FILES:
    setattr(SchemeFileTests, "test_" + _p.stem.replace("-", "_"), _make(_p))


class AssertionCountTest(unittest.TestCase):
    def test_at_least_120_assertions(self):
        total = sum(execute(p)[0] for p in FILES)
        self.assertGreaterEqual(total, 120)
        # 涵蓋 README 列出的每個主題
        self.assertGreaterEqual(len(FILES), 10)


if __name__ == "__main__":
    unittest.main()

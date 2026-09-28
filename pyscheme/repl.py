"""REPL 與命令列入口。"""
import argparse
import sys
import time

from . import __version__
from .datatypes import UNSPEC
from .errors import IncompleteInput, ReadError, SchemeError, SchemeExit
from .machine import Interpreter
from .printer import to_string
from .reader import EOF, Reader

HELP = """\
指令 (commands):
  ,help            顯示這段說明
  ,quit  ,q        離開 (也可以按 Ctrl-D 或輸入 (exit))
  ,load 檔名       載入並執行一個 .scm 檔
  ,env             列出你自己定義的名稱
  ,expand 運算式   把巨集展開一層並印出結果
  ,time 運算式     執行並顯示花費時間
  ,reset           清除所有定義,重新開始
括號沒配完時會自動換行繼續輸入 (提示符號變成 "... ")。
"""


def _setup_readline():
    try:
        import readline
    except ImportError:
        return None
    return readline


class _Tracker:
    """包住輸出串流,記住最後寫出的字元,好讓結果另起一行。"""

    def __init__(self, stream):
        self.stream = stream
        self.last = "\n"

    def write(self, text):
        if text:
            self.last = text[-1]
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()


class Repl:
    def __init__(self, interp=None, input_fn=input, out=None, err=None, interactive=True):
        self.interp = interp or Interpreter()
        self.input_fn = input_fn
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        self.tracker = None
        self.interactive = interactive
        self.prompt = "pyscheme> " if interactive else ""
        self.cont_prompt = "...       " if interactive else ""

    def say(self, text):
        self.out.write(text + "\n")
        self.out.flush()

    def report(self, e):
        self.out.flush()
        self.err.write(f"錯誤 (error): {e}\n")
        self.err.flush()

    def print_value(self, v):
        if self.tracker is not None and self.tracker.last != "\n":
            self.out.write("\n")
        if v is not UNSPEC:
            self.say(to_string(v, True))

    def eval_text(self, text):
        """求值 text 裡所有運算式並印出結果。錯誤只印訊息,不往外丟。"""
        old = sys.stdout
        self.tracker = sys.stdout = _Tracker(self.out)
        try:
            reader = Reader(text)
            while True:
                d = reader.read()
                if d is EOF:
                    break
                self.print_value(self.interp.eval_datum(d))
        except SchemeExit:
            raise
        except SchemeError as e:
            self.report(e)
        except KeyboardInterrupt:
            self.report("中斷 (interrupted)")
        finally:
            sys.stdout = old

    def command(self, line):
        """處理 ,xxx 指令。回傳 False 代表要離開。"""
        parts = line[1:].strip().split(None, 1)
        cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""
        if cmd in ("q", "quit", "exit"):
            return False
        if cmd in ("h", "help", "?"):
            self.out.write(HELP)
        elif cmd == "load":
            try:
                self.interp.run_file(arg.strip())
                self.say(f"已載入 {arg.strip()}")
            except (OSError, SchemeError) as e:
                self.report(e)
        elif cmd == "env":
            from .primitives import PRIMS
            names = sorted(s.name for s, v in self.interp.global_env.vars.items()
                           if s.name not in PRIMS and s.name not in self.interp.prelude_names)
            self.say(" ".join(names) if names else "(還沒有自己定義的名稱)")
        elif cmd == "expand":
            try:
                form = Reader(arg).read()
                if form is EOF:
                    raise ReadError("empty", 1, 1)
                self.say(to_string(self.interp.analyzer.macroexpand_1(form), True))
            except SchemeError as e:
                self.report(e)
        elif cmd == "time":
            t0 = time.perf_counter()
            self.eval_text(arg)
            self.say(f";; {time.perf_counter() - t0:.3f} 秒")
        elif cmd == "reset":
            self.interp = Interpreter()
            self.say("已重置。")
        else:
            self.report(f"不認得的指令 ,{cmd}(輸入 ,help 看說明)")
        return True

    def run(self):
        if self.interactive:
            self.say(f"pyscheme {__version__} -- 輸入 ,help 看說明,Ctrl-D 離開")
        buf = ""
        while True:
            try:
                line = self.input_fn(self.cont_prompt if buf else self.prompt)
            except EOFError:
                if self.interactive:
                    self.say("")
                return 0
            except KeyboardInterrupt:
                buf = ""
                self.say("")
                continue
            if not buf and line.strip().startswith(","):
                try:
                    if not self.command(line.strip()):
                        return 0
                except SchemeExit as e:
                    return e.code
                continue
            buf = buf + line + "\n"
            try:
                Reader(buf).read_all()
            except IncompleteInput:
                continue
            except ReadError as e:
                self.report(e)
                buf = ""
                continue
            text, buf = buf, ""
            try:
                self.eval_text(text)
            except SchemeExit as e:
                return e.code


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pyscheme", description="pyscheme: 用 Python 從零實作的 Scheme 直譯器")
    ap.add_argument("file", nargs="?", help="要執行的 .scm 檔 (省略則進入 REPL)")
    ap.add_argument("-e", "--eval", metavar="EXPR", help="求值一段程式並印出結果")
    ap.add_argument("-i", "--interactive", action="store_true", help="執行檔案後進入 REPL")
    ap.add_argument("--version", action="version", version=f"pyscheme {__version__}")
    ns = ap.parse_args(argv)
    interp = Interpreter()
    try:
        if ns.eval is not None:
            v = interp.run_string(ns.eval)
            if v is not UNSPEC:
                print(to_string(v, True))
            return 0
        if ns.file:
            try:
                interp.run_file(ns.file)
            except OSError as e:
                print(f"pyscheme: 無法讀取檔案 {ns.file}: {e.strerror}", file=sys.stderr)
                return 2
            except SchemeError as e:
                sys.stdout.flush()
                print(f"錯誤 (error): {e}", file=sys.stderr)
                return 1
            if not ns.interactive:
                return 0
    except SchemeExit as e:
        return e.code
    except SchemeError as e:
        print(f"錯誤 (error): {e}", file=sys.stderr)
        return 1
    tty = sys.stdin.isatty()
    if tty:
        rl = _setup_readline()
        if rl:
            import atexit
            import os
            hist = os.path.join(os.path.expanduser("~"), ".pyscheme_history")
            try:
                rl.read_history_file(hist)
            except OSError:
                pass
            rl.set_history_length(1000)
            atexit.register(lambda: _save_history(rl, hist))
    return Repl(interp, interactive=tty).run()


def _save_history(rl, path):
    try:
        rl.write_history_file(path)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())

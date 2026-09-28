"""錯誤型別。所有「Scheme 程式本身的錯誤」都是 SchemeError。"""


def bi(en, zh):
    """雙語訊息:英文 / 中文。"""
    return f"{en} / {zh}"


class SchemeError(Exception):
    """執行期錯誤。payload 是 raise 出去的物件(error 則是訊息字串)。"""

    def __init__(self, message, payload=None):
        super().__init__(message)
        self.message = message
        self.payload = message if payload is None else payload


class ReadError(SchemeError):
    """Reader 的語法錯誤,附行號與欄位(從 1 開始)。"""

    def __init__(self, message, line, col):
        super().__init__(f"line {line}, column {col}: {message}")
        self.line = line
        self.col = col


class IncompleteInput(ReadError):
    """輸入還沒結束(括號或字串沒關)。REPL 看到它就會繼續等下一行。"""


class SchemeExit(Exception):
    """呼叫 (exit) 時丟出,由 CLI 接住。"""

    def __init__(self, code=0):
        super().__init__(code)
        self.code = code

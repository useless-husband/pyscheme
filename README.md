# pyscheme
A Scheme interpreter written from scratch in pure Python: CEK machine, proper tail calls, full call/cc, syntax-rules macros.

pyscheme 是一個用 Python 標準函式庫從零寫成的 Scheme 直譯器,附帶一份給初學者看的「直譯器是怎麼運作的」說明。它不依賴任何第三方套件,全部程式碼加起來三千多行,可以從頭讀到尾。

我寫它的目的是搞懂直譯器的內部:Reader、AST、環境、尾呼叫、call/cc、巨集。所以程式碼裡的註解和這份 README 都盡量寫得白話。它不是要和 Guile、Racket 比速度。

## 功能

- **Reader**:整數、浮點、分數 (`1/3`)、字串 (含跳脫字元)、字元 `#\a`、布林、符號、串列、點對 `(a . b)`、向量 `#(1 2)`、`'` `` ` `` `,` `,@` 簡寫、`;` 行註解、`#| |#` 巢狀區塊註解、`#;` 資料註解。語法錯誤會回報行號與欄位。
- **核心形式**:`define` (含 `(define (f x) ...)`、柯里化、內部 define)、`lambda` (含 rest 參數)、`if`、`cond` (含 `else`、`=>`)、`case`、`and`、`or`、`when`、`unless`、`let`、`let*`、`letrec`、named `let`、`do`、`begin`、`set!`、`quote`、巢狀 `quasiquote`、`delay` / `force`、`cons-stream`、`define-record-type`。
- **巨集**:`define-syntax` + `syntax-rules`,支援 `...`、巢狀 `...`、literals、遞迴巨集。**沒有做完整的衛生 (hygiene)**,限制見下文。
- **正確的尾呼叫**:`(loop 1000000)` 只用固定空間。非尾遞迴很深 (十萬層以上) 也不會 `RecursionError`,因為直譯器根本沒有用 Python 的呼叫堆疊。
- **完整的 `call/cc`**:不只是逃逸,continuation 可以被存起來、重新進入多次 (所以能寫 generator)。另有 `dynamic-wind`,以及 `catch-error` 做錯誤處理。
- **約 300 個內建程序**:數字 (大整數、分數、`expt` `sqrt` `exact->inexact` ...)、串列 (`map` `filter` `fold-left` `fold-right` `reduce` `assoc` `sort` ...)、字串、字元、向量、雜湊表、`display` `write` `newline`、`error`、`eq?` `eqv?` `equal?`,還有串流 (`stream-map` `stream-filter` ...)。一部分是用 Scheme 寫的 ([`pyscheme/prelude.scm`](pyscheme/prelude.scm))。
- **REPL**:括號沒配完就繼續等下一行、方向鍵與歷史 (readline 可用時)、錯誤不會讓 REPL 結束、`,help` 等指令。也可以 `pyscheme file.scm` 執行檔案。
- **雙語錯誤訊息**:例如 `unbound variable: foo / 未定義的變數: foo`。

## 安裝與執行

需要 Python 3.10 以上 (在 3.10 到 3.13 測試過)。不需要安裝任何其他東西。

### 方法一:直接從 GitHub 安裝成指令 (推薦)

用 [pipx](https://pipx.pypa.io/) 或 [uv](https://docs.astral.sh/uv/) 都可以,兩個擇一:

```bash
pipx install git+https://github.com/useless-husband/pyscheme
```

```bash
uv tool install git+https://github.com/useless-husband/pyscheme
```

裝好之後,開一個新的終端機視窗,輸入:

```bash
pyscheme
```

就會進入 REPL。

### 方法二:下載原始碼直接跑 (不用安裝)

```bash
git clone https://github.com/useless-husband/pyscheme
cd pyscheme
python3 -m pyscheme
```

### 執行檔案與其他用法

```bash
pyscheme examples/fizzbuzz.scm        # 執行檔案
pyscheme -e '(+ 1 2 3)'               # 算一個運算式,印出 6
pyscheme -i examples/factorial.scm    # 先執行檔案,再進入 REPL (可以繼續用檔案裡的定義)
pyscheme --version
```

(如果用方法二,把上面的 `pyscheme` 換成 `python3 -m pyscheme`。)

## 使用範例

### REPL

```text
$ pyscheme
pyscheme 1.0.0 -- 輸入 ,help 看說明,Ctrl-D 離開
pyscheme> (define (square x) (* x x))
pyscheme> (square 12)
144
pyscheme> (map square (list 1 2 3 4))
(1 4 9 16)
pyscheme> (define (fact n)
...         (if (= n 0)
...             1
...             (* n (fact (- n 1)))))
pyscheme> (fact 30)
265252859812191058636308480000000
pyscheme> `(1 ,(+ 1 1) ,@(list 3 4))
(1 2 3 4)
pyscheme> (/ 1 3)
1/3
pyscheme> (exact->inexact 1/3)
0.3333333333333333
pyscheme> (car 5)
錯誤 (error): car: expected pair, got 5 / car: 需要序對(pair),卻收到 5
pyscheme> (square 1 2)
錯誤 (error): procedure 'square' expects 1 argument(s), got 2 / 程序 'square' 需要 1 個參數,卻收到 2 個
pyscheme> (foo)
錯誤 (error): unbound variable: foo / 未定義的變數: foo
pyscheme> ,quit
```

REPL 指令 (都以逗號開頭):

| 指令 | 作用 |
| --- | --- |
| `,help` | 顯示說明 |
| `,quit` / `,q` | 離開 (也可以按 Ctrl-D 或輸入 `(exit)`) |
| `,load 檔名` | 載入並執行一個 `.scm` 檔 |
| `,env` | 列出你自己定義的名稱 |
| `,expand 運算式` | 把巨集展開一層並印出來 |
| `,time 運算式` | 執行並顯示花費時間 |
| `,reset` | 清除所有定義 |

### 尾呼叫與深遞迴

```scheme
(define (loop n) (if (= n 0) 'done (loop (- n 1))))
(loop 1000000)                     ; => done,不會 RecursionError

(define (count n) (if (= n 0) 0 (+ 1 (count (- n 1)))))
(count 100000)                     ; => 100000,非尾遞迴也可以
```

非尾遞迴的深度上限預設是 40 萬層 (避免無限遞迴吃光記憶體),超過會得到一般的錯誤訊息:
`recursion depth exceeded ... / 遞迴太深 ...`,REPL 不會結束。

### call/cc:generator

```scheme
(define (make-generator lst)
  (define return #f)
  (define resume #f)
  (define (start)
    (for-each (lambda (x)
                (call/cc (lambda (next) (set! resume next) (return x))))
              lst)
    (return 'done))
  (lambda ()
    (call/cc (lambda (r)
               (set! return r)
               (if resume (resume #f) (start))))))

(define g (make-generator '(apple banana cherry)))
(g) (g) (g) (g)     ; 依序得到 apple banana cherry done
```

### 巨集

```scheme
(define-syntax while
  (syntax-rules ()
    ((_ cond body ...) (let lp () (when cond body ... (lp))))))

(define i 0)
(while (< i 3) (display i) (set! i (+ i 1)))    ; 印出 012
```

### 錯誤處理

`catch-error` 接受一個 thunk 和一個處理函式;`error` 丟出的東西會以字串 (訊息加上 irritants) 傳給處理函式,`raise` 丟出的物件則原樣傳入:

```scheme
(catch-error
  (lambda () (error "boom:" 42))
  (lambda (msg) (display "caught: ") (display msg) (newline)))
; caught: boom: 42
```

### examples/ 資料夾

| 檔案 | 內容 |
| --- | --- |
| [`fizzbuzz.scm`](examples/fizzbuzz.scm) | FizzBuzz |
| [`factorial.scm`](examples/factorial.scm) | 階乘、大數、精確分數 |
| [`queens.scm`](examples/queens.scm) | 八皇后 (92 種解) 並印出棋盤 |
| [`stream-primes.scm`](examples/stream-primes.scm) | 用無限串列做質數篩、費氏數列 |
| [`generator.scm`](examples/generator.scm) | 用 `call/cc` 做 generator 與 same-fringe |
| [`metacircular.scm`](examples/metacircular.scm) | 用 Scheme 寫的小型 Scheme 直譯器 (SICP 第四章精簡版) |

例如 `pyscheme examples/queens.scm` 的輸出開頭:

```text
8 皇后共有 92 種解
第一個解:(4 2 7 3 6 8 5 1)
. . . Q . . . .
. Q . . . . . .
. . . . . . Q .
...
```

## 專案結構

```text
pyscheme/
├── pyscheme/
│   ├── reader.py        # 文字 -> Scheme 資料 (含行號欄位的錯誤)
│   ├── datatypes.py     # Symbol、Pair、Env、Closure ... 資料表示法
│   ├── analyzer.py      # S-expression -> AST 節點;巨集展開;let/cond/do 等語法糖
│   ├── syntax_rules.py  # syntax-rules 的比對與展開
│   ├── nodes.py         # AST 節點類別
│   ├── machine.py       # CEK 機器:整個直譯器的主迴圈
│   ├── primitives.py    # 用 Python 寫的內建程序
│   ├── prelude.scm      # 用 Scheme 寫的內建程序 (map、sort、串流 ...)
│   ├── printer.py       # display / write
│   ├── repl.py          # REPL 與命令列
│   └── errors.py
├── examples/            # 六個範例程式
├── tests/
│   ├── scheme/*.scm     # 用 (assert-equal ...) 巨集寫的 Scheme 測試
│   ├── expected/        # examples 的預期輸出
│   └── test_*.py        # unittest
├── .github/workflows/ci.yml
└── pyproject.toml
```

## 如何跑測試

不需要安裝任何東西,在專案根目錄:

```bash
python3 -m unittest discover -s tests -t . -v
```

測試分兩層:

1. `tests/scheme/*.scm`:用 Scheme 自己寫的測試,共 11 個檔案、約 440 個斷言,涵蓋 Reader、核心形式、quasiquote、巨集、尾呼叫 (一百萬次迴圈、十萬層深遞迴)、call/cc 與 dynamic-wind、數字、串列、字串、串流、錯誤訊息。斷言是用兩個自己寫的 `syntax-rules` 巨集 (見 [`tests/scheme/00-harness.scm`](tests/scheme/00-harness.scm)):

   ```scheme
   (assert-equal '(1 4 9) (map (lambda (x) (* x x)) '(1 2 3)))
   (assert-error "unbound variable" (undefined-function 1))
   ```

2. `tests/test_*.py`:Python `unittest`,測 Reader 的錯誤位置、印出格式、REPL (多行輸入、錯誤後繼續)、命令列 (結束碼、stdin)、所有 examples 的輸出是否與 `tests/expected/` 完全一致。

整套約 20 到 30 秒 (一百萬次迴圈的測試佔了大部分)。

## 直譯器是怎麼運作的

這一章給第一次看直譯器原始碼的人。整個流程可以濃縮成一條線:

```text
  原始碼文字  ──Reader──▶  S-expression 資料  ──Analyzer──▶  AST 節點  ──Machine──▶  結果
 "(+ 1 (* 2 3))"          (+ 1 (* 2 3))                     App(+, ...)              7
```

### 1. Reader:文字變成資料 (`reader.py`)

Scheme 有一個很漂亮的性質:程式本身就是資料。`(+ 1 (* 2 3))` 既是一段程式,也是一個含三個元素的串列 (符號 `+`、數字 `1`、另一個串列)。

Reader 一個字元一個字元往下讀,遇到 `(` 就一直讀到對應的 `)`,把裡面的東西收成串列。串列用 `Pair(car, cdr)` 一節一節串起來,`(1 2 3)` 在記憶體裡長這樣:

```text
 Pair ─▶ Pair ─▶ Pair ─▶ NIL
 car=1   car=2   car=3
```

Reader 也負責:數字判斷 (整數 / 浮點 / 分數)、字串跳脫、`'x` 展開成 `(quote x)`、略過註解。括號沒關時它會丟 `IncompleteInput`,REPL 就是靠這個判斷「要不要再等下一行」;真的有語法錯誤時則丟 `ReadError`,訊息帶行號與欄位。

### 2. Analyzer:資料變成 AST (`analyzer.py`, `nodes.py`)

如果每次執行都重新檢查「這個串列的第一個元素是不是 `if`」,會又慢又亂。所以求值之前先做一次分析,把 S-expression 轉成 AST 節點:`Const`、`Ref` (變數參照)、`If`、`LambdaNode`、`App` (函式呼叫)、`Seq`、`Define`、`SetBang`、`Or`、`Delay`。

`let`、`cond`、`case`、`do`、`and`、`when`、named `let`、`quasiquote` 這些「語法糖」在這一步全部被改寫成上面那幾種基本節點,例如:

```scheme
(let ((x 1) (y 2)) (+ x y))
;; 分析後等於
((lambda (x y) (+ x y)) 1 2)
```

所以真正執行的機器只需要認得十來種節點。巨集展開也發生在這一步 (見下文)。

### 3. 環境模型 (`datatypes.py` 的 `Env`)

變數的值放在「環境」裡。環境就是一個 dict 加上指向外層環境的指標:

```scheme
(define x 10)                  ; 全域環境:{x: 10, ...}
(define (f y)
  (let ((z 3))
    (+ x y z)))
(f 1)
```

呼叫 `(f 1)` 時:

```text
 let 的環境    {z: 3}
      │ parent
 f 的環境      {y: 1}
      │ parent
 全域環境      {x: 10, f: <procedure>, + : <primitive>, ...}
```

查 `x` 時先找 `{z: 3}`,沒有就往外找 `{y: 1}`,最後在全域環境找到。這就是「詞法作用域」。`lambda` 建立的 Closure 會記住「它在哪個環境被建立」,所以之後不管在哪裡被呼叫,查變數都從那個環境往外找。這就是 closure 能記住 `make-counter` 裡的計數器的原因。

### 4. Machine:CEK 機器與尾呼叫 (`machine.py`)

最直覺的寫法是遞迴:`eval(if 節點)` 呼叫 `eval(條件)`,`eval(函式呼叫)` 呼叫 `eval(每個引數)`。但這樣 Scheme 每深一層,Python 就深一層,幾千層就 `RecursionError`,尾呼叫也做不到。

pyscheme 的做法是把「接下來要做什麼」明確寫成資料。狀態有三個部分 (CEK 的由來):

- **C**ontrol:現在要算的節點 (或剛算出來的值)
- **E**nvironment:現在的環境
- **K**ontinuation:算完之後要接著做的事,是一串 `Frame` 組成的鏈結串列

主迴圈只是一個 `while True`,在「求值 / 回傳值 / 套用函式」三種模式間切換。以 `(+ 1 (f 2))` 為例:

```text
 要算 (+ 1 (f 2)),先算引數:
   K: [等 (f 2) 的值,之後湊齊 + 的引數] → HALT
   C: (f 2)
 (f 2) 是 closure 呼叫 → 進入 f 的本體,K 不變地多了一格等待:
   K: [等 (f 2) 的值...] → HALT          ← Frame 存在 heap,不是 Python 堆疊
 f 算出 5 → 從 K 拿出最上面一格 → 繼續湊 + 的引數 → 算出 6
```

**尾呼叫**就變得很自然。如果函式呼叫出現在「尾端位置」(算完它之後沒有別的事要做),機器就**不推新的 Frame**,直接把 C 換成被呼叫函式的本體:

```text
 (define (loop n) (if (= n 0) 'done (loop (- n 1))))

 非尾呼叫  (+ 1 (loop ...))         尾呼叫  (loop (- n 1))
 K: [等值] → [等值] → [等值] → ...   K: HALT   K: HALT   K: HALT ...
 每呼叫一次,鏈就長一格               每呼叫一次,K 完全不變
```

所以 `(loop 1000000)` 只用固定的空間。反過來,非尾遞迴每一層多一個 Frame,但 Frame 在 heap 上,十萬層也只是十萬個小物件 (預設上限 40 萬層,避免無限遞迴把記憶體吃光)。

> 這種做法和 trampoline (蹦床) 是同一個想法的兩種寫法:trampoline 是「函式不直接呼叫下一步,而是回傳『下一步要做什麼』,由外層迴圈反覆執行」;CEK 機器則是把整個直譯器都寫成那個外層迴圈。CEK 的額外好處是 continuation 就是資料,所以 `call/cc` 幾乎是免費的。

**call/cc** 因此很簡單:`(call/cc f)` 就是把當下的 K 指標包成一個 Continuation 物件,傳給 `f`。K 這條鏈是不可變的 (Frame 建好之後不再修改),所以那個指標永遠有效。呼叫這個 continuation,就是把機器的 K 換回去。因為可以重複換回去,所以能重新進入,generator 就是這樣做出來的。`dynamic-wind` 則在機器裡另外維護一條「進入了哪些 before/after 區段」的串列,跳出或跳入時依序執行對應的 thunk。

另外還有兩個小優化,不影響語意:一是 `Const` / `Ref` / `lambda` 這種一步就能算完的節點直接求值,不推 Frame;二是引數全是簡單運算的呼叫 (例如 `(= n 0)`、`(- n 1)`) 會先嘗試一次「不推 Frame」的快速求值。

### 5. 巨集展開流程 (`syntax_rules.py`)

`define-syntax` + `syntax-rules` 是「在分析階段,把一段程式碼改寫成另一段程式碼」。以 `swap!` 為例:

```scheme
(define-syntax swap!
  (syntax-rules ()
    ((_ a b) (let ((tmp a)) (set! a b) (set! b tmp)))))

(swap! x y)
```

展開分三步:

```text
 1. 找到巨集:Analyzer 看到 (swap! x y),第一個符號 swap! 是已註冊的巨集
 2. 比對模式:  (_ a b)   對   (swap! x y)     →  a = x,  b = y
 3. 套進樣板:  (let ((tmp a)) (set! a b) (set! b tmp))
                → (let ((tmp x)) (set! x y) (set! y tmp))
 4. 把結果再丟回 Analyzer,繼續分析 (結果裡還有巨集也會繼續展開)
```

`...` (省略號) 表示「前面那個模式可以重複零次以上」。比對時,`x ...` 的每個變數會收集成一串;展開時樣板裡的 `x ...` 再逐項展開。例如 `((_ (a b) ...) (list (cons a b) ...))` 用在 `(m (1 2) (3 4))` 得到 `(list (cons 1 2) (cons 3 4))`。在 REPL 裡可以用 `,expand` 看展開一層的結果:

```text
pyscheme> (define-syntax inc! (syntax-rules () ((_ v) (set! v (+ v 1)))))
pyscheme> ,expand (inc! n)
(set! n (+ n 1))
```

## 已知限制 (請先看這裡)

### 巨集不是衛生 (hygienic) 的

pyscheme 的 `syntax-rules` 只做單純的樣板替換,沒有幫樣板裡引入的變數改名。所以樣板裡自己用的暫存變數,可能和使用者程式裡的同名變數撞在一起:

```scheme
(define-syntax bad-swap!
  (syntax-rules ()
    ((_ a b) (let ((tmp a)) (set! a b) (set! b tmp)))))

(define tmp 1)
(define other 2)
(bad-swap! tmp other)
(list tmp other)      ; 得到 (1 2),沒有交換!真正衛生的實作會得到 (2 1)
```

原因:展開後變成 `(let ((tmp tmp)) (set! tmp other) (set! other tmp))`,巨集自己的 `tmp` 蓋住了使用者的 `tmp`。

解法是自己在樣板裡用不太可能撞名的名字,例如 `%tmp` (`tests/scheme/` 裡的 `assert-equal` 就是這樣寫的):

```scheme
(define-syntax swap!
  (syntax-rules ()
    ((_ a b) (let ((%tmp a)) (set! a b) (set! b %tmp)))))
```

反方向也有類似問題:樣板裡用到的 `if`、`let` 等名字,如果使用者剛好把它們綁成區域變數,展開結果會用到使用者的版本。另外,`define-syntax` 定義的巨集是全域的,寫在函式內部也一樣會影響之後的程式 (沒有 `let-syntax` 那樣的區域範圍)。

### 其他限制

- 只支援 `syntax-rules`,沒有 `er-macro-transformer` 之類的。
- 沒有複數、沒有 `values` / `call-with-values`、沒有 `guard` / `with-exception-handler` (錯誤處理請用 `catch-error`)、沒有 `parameterize`、沒有 port (`display` 永遠寫到標準輸出)。`sqrt` 遇到負數會報錯而不是回傳複數。
- 字串是 Python 的 `str`,不可變:沒有 `string-set!`。
- `force` 不是完全符合 R7RS 的 `delay-force` 迭代版本。
- 錯誤訊息只有錯誤原因,沒有 Scheme 層的呼叫堆疊追蹤,也沒有原始碼行號 (只有 Reader 的語法錯誤有)。
- 效能約為一百萬次迴圈 1 到 2 秒。夠寫作業和玩 SICP,不適合跑重運算。
- 比較大的資料結構 (成千上萬層巢狀的串列) 在 `equal?` 或印出時會用到 Python 遞迴,超過限制會得到「內建程序遇到太深的巢狀結構」錯誤。長串列 (只是很長,不是很深) 沒有問題。
- 語意上以 R7RS 為參考,但不是完整實作,某些角落 (例如求值順序、`eq?` 對數字與字串的判斷) 與其他實作可能不同。引數是由左到右求值。

## 授權

[MIT License](LICENSE),Copyright (c) 2026 useless-husband。

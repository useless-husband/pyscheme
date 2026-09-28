(define-syntax swap!
  (syntax-rules ()
    ((_ a b) (let ((%tmp a)) (set! a b) (set! b %tmp)))))
(define p 1) (define q 2)
(swap! p q)
(assert-equal '(2 1) (list p q))

(define-syntax my-or
  (syntax-rules ()
    ((_) #f)
    ((_ e) e)
    ((_ e r ...) (let ((%t e)) (if %t %t (my-or r ...))))))
(assert-equal #f (my-or))
(assert-equal 3 (my-or #f #f 3))
(assert-equal 1 (my-or 1 (car '())))

(define-syntax while
  (syntax-rules ()
    ((_ cond body ...) (let lp () (when cond body ... (lp))))))
(define i 0) (define total 0)
(while (< i 5) (set! total (+ total i)) (set! i (+ i 1)))
(assert-equal 10 total)

(define-syntax for
  (syntax-rules (in from to)
    ((_ x in lst body ...) (for-each (lambda (x) body ...) lst))
    ((_ x from a to b body ...) (do ((x a (+ x 1))) ((> x b)) body ...))))
(define acc '())
(for y in '(1 2 3) (set! acc (cons (* y y) acc)))
(assert-equal '(9 4 1) acc)
(set! acc 0)
(for k from 1 to 4 (set! acc (+ acc k)))
(assert-equal 10 acc)

(define-syntax my-let*
  (syntax-rules ()
    ((_ () body ...) (let () body ...))
    ((_ ((n v) rest ...) body ...) (let ((n v)) (my-let* (rest ...) body ...)))))
(assert-equal 5 (my-let* ((a 1) (b (+ a 1)) (c (+ a b 2))) c))

(define-syntax my-cond
  (syntax-rules (else)
    ((_ (else e ...)) (begin e ...))
    ((_ (c e ...) clause ...) (if c (begin e ...) (my-cond clause ...)))))
(assert-equal 'b (my-cond (#f 'a) ((= 1 1) 'b) (else 'c)))
(assert-equal 'c (my-cond (#f 'a) (#f 'b) (else 'c)))

(define-syntax my-list-of-pairs
  (syntax-rules ()
    ((_ (a b) ...) (list (cons a b) ...))))
(assert-equal '((1 . 2) (3 . 4)) (my-list-of-pairs (1 2) (3 4)))

(define-syntax flat
  (syntax-rules ()
    ((_ (a ...) ...) '(a ... ...))))
(assert-equal '(1 2 3 4 5) (flat (1 2) (3) (4 5)))

(define-syntax tail-pat
  (syntax-rules ()
    ((_ a ... z) '(z a ...))))
(assert-equal '(4 1 2 3) (tail-pat 1 2 3 4))

(define-syntax unless2
  (syntax-rules () ((_ c body ...) (if c #f (begin body ...)))))
(assert-equal 'ok (unless2 #f 'ok))

;;; 巨集可以定義在函式裡的內部 define 之前使用
(define (use-in-body)
  (define-syntax double (syntax-rules () ((_ x) (* 2 x))))
  (double 21))
(assert-equal 42 (use-in-body))

;;; 遞迴巨集
(define-syntax count-args
  (syntax-rules ()
    ((_) 0)
    ((_ x rest ...) (+ 1 (count-args rest ...)))))
(assert-equal 4 (count-args a b c d))

;;; 巨集產生 define
(define-syntax def-getter
  (syntax-rules () ((_ name val) (define (name) val))))
(def-getter get-five 5)
(assert-equal 5 (get-five))
(assert-error "no matching syntax rule" (eval '(swap! 1)))

;;; 已知限制:沒有完整衛生。樣板裡的 tmp 會吃掉使用者的 tmp。
(define-syntax bad-swap!
  (syntax-rules () ((_ a b) (let ((tmp a)) (set! a b) (set! b tmp)))))
(define tmp 1) (define other 2)
(bad-swap! tmp other)
(assert-equal '(1 2) (list tmp other))   ; 交換失敗了 (真正衛生的巨集會得到 (2 1))

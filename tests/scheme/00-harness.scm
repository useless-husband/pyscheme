;;; 測試用的小框架:兩個自己寫的 syntax-rules 巨集。
;;; (assert-equal 期望值 運算式)          期望值與結果用 equal? 比較
;;; (assert-error "訊息片段" 運算式)      運算式必須丟出錯誤,且訊息含該片段

(define *pass* 0)
(define *fail* 0)

(define (%record-ok) (set! *pass* (+ *pass* 1)))
(define (%record-fail what got want)
  (set! *fail* (+ *fail* 1))
  (display "FAIL: ") (write what)
  (display "\n  got:      ") (write got)
  (display "\n  expected: ") (write want)
  (newline))

(define-syntax assert-equal
  (syntax-rules ()
    ((_ want expr)
     (let ((%got expr) (%want want))
       (if (equal? %got %want)
           (%record-ok)
           (%record-fail 'expr %got %want))))))

(define-syntax assert-error
  (syntax-rules ()
    ((_ part expr)
     (let ((%r (catch-error (lambda () expr 'no-error) (lambda (m) m))))
       (if (and (string? %r) (string-contains %r part))
           (%record-ok)
           (%record-fail 'expr %r part))))))

(define-syntax assert-true
  (syntax-rules () ((_ expr) (assert-equal #t (if expr #t #f)))))

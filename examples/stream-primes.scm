;;; 用串流 (stream) 做無限的質數篩 (Sieve of Eratosthenes)
;;; cons-stream 的第二個參數不會馬上求值,要用到時才算。

(define (integers-from n)
  (cons-stream n (integers-from (+ n 1))))

(define (sieve s)
  (cons-stream
   (stream-car s)
   (sieve (stream-filter
           (lambda (x) (not (= 0 (remainder x (stream-car s)))))
           (stream-cdr s)))))

(define primes (sieve (integers-from 2)))

(display "前 20 個質數:")
(display (stream-head primes 20))
(newline)
(display "第 100 個質數:")
(display (stream-ref primes 99))
(newline)

;;; 費氏數列也可以用串流「自己定義自己」
(define (add-streams a b) (stream-map + a b))
(define fibs
  (cons-stream 0 (cons-stream 1 (add-streams fibs (stream-cdr fibs)))))
(display "前 15 個費氏數:")
(display (stream-head fibs 15))
(newline)
(display "fib(100) = ")
(display (stream-ref fibs 100))
(newline)

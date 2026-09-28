;;; FizzBuzz:印出 1 到 20
(define (fizzbuzz n)
  (cond ((= 0 (modulo n 15)) "FizzBuzz")
        ((= 0 (modulo n 3)) "Fizz")
        ((= 0 (modulo n 5)) "Buzz")
        (else n)))

(do ((i 1 (+ i 1)))
    ((> i 20))
  (display (fizzbuzz i))
  (newline))

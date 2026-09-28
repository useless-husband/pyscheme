;;; 階乘與大數:Scheme 的整數沒有位數上限
(define (fact n)
  (if (= n 0)
      1
      (* n (fact (- n 1)))))

(display "20!  = ") (display (fact 20)) (newline)
(display "30!  = ") (display (fact 30)) (newline)
(display "100! = ") (display (fact 100)) (newline)

;;; 尾遞迴版本:累加器,不會增加堆疊
(define (fact-iter n)
  (let loop ((i n) (acc 1))
    (if (= i 0) acc (loop (- i 1) (* acc i)))))

(display "2^200 = ") (display (expt 2 200)) (newline)
(display "1000! 有幾位數:")
(display (string-length (number->string (fact-iter 1000))))
(newline)

;;; 分數也是精確的
(display "1/3 + 1/6 = ") (display (+ 1/3 1/6)) (newline)
(define (harmonic n)
  (if (= n 0) 0 (+ (/ 1 n) (harmonic (- n 1)))))
(display "H(10) = ") (display (harmonic 10)) (newline)

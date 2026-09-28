;;; 八皇后:找出所有放法
;;; 一個解用串列表示,第 i 個元素是第 i 列皇后所在的欄。

(define (safe? col placed)
  ;; placed 是已放好的皇后 (最近放的在最前面)
  (let loop ((rest placed) (dist 1))
    (cond ((null? rest) #t)
          ((or (= (car rest) col)
               (= (abs (- (car rest) col)) dist))
           #f)
          (else (loop (cdr rest) (+ dist 1))))))

(define (queens board-size)
  (define (place k placed)
    (if (= k 0)
        (list placed)
        (append-map
         (lambda (col)
           (if (safe? col placed)
               (place (- k 1) (cons col placed))
               '()))
         (iota board-size 1))))
  (place board-size '()))

(define (show-board solution n)
  (for-each
   (lambda (col)
     (do ((c 1 (+ c 1))) ((> c n))
       (display (if (= c col) "Q " ". ")))
     (newline))
   solution))

(define solutions (queens 8))
(display "8 皇后共有 ") (display (length solutions)) (display " 種解") (newline)
(display "第一個解:") (display (car solutions)) (newline)
(show-board (car solutions) 8)
(display "6 皇后共有 ") (display (length (queens 6))) (display " 種解") (newline)

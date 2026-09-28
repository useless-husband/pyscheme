;;; 用 call/cc 做 generator:每次呼叫吐出下一個元素。
;;; 這裡的 continuation 會被「重新進入」,不只是逃逸。

(define (make-generator lst)
  (define return #f)   ; 目前呼叫者的 continuation
  (define resume #f)   ; 上次中斷的地方
  (define (start)
    (for-each
     (lambda (x)
       (call/cc (lambda (next)
                  (set! resume next)
                  (return x))))
     lst)
    (return 'done))
  (lambda ()
    (call/cc (lambda (r)
               (set! return r)
               (if resume (resume #f) (start))))))

(define g (make-generator '(apple banana cherry)))
(display (g)) (newline)
(display (g)) (newline)
(display (g)) (newline)
(display (g)) (newline)

;;; 樹的葉子 generator:比較兩棵樹的葉子序列是否相同 (same-fringe)
(define (tree-walk tree yield)
  (cond ((null? tree) 'skip)
        ((pair? tree) (tree-walk (car tree) yield) (tree-walk (cdr tree) yield))
        (else (yield tree))))

(define (tree->generator tree)
  (define return #f)
  (define resume #f)
  (lambda ()
    (call/cc
     (lambda (r)
       (set! return r)
       (if resume
           (resume #f)
           (begin
             (tree-walk tree
                        (lambda (leaf)
                          (call/cc (lambda (next)
                                     (set! resume next)
                                     (return leaf)))))
             (return '*end*)))))))

(define (same-fringe? t1 t2)
  (let ((g1 (tree->generator t1)) (g2 (tree->generator t2)))
    (let loop ()
      (let ((a (g1)) (b (g2)))
        (cond ((not (eqv? a b)) #f)
              ((eq? a '*end*) #t)
              (else (loop)))))))

(display (same-fringe? '(1 (2 3) 4) '((1 2) (3 (4)))))
(newline)
(display (same-fringe? '(1 (2 3) 4) '(1 2 (4 3))))
(newline)

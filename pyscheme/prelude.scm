;;; prelude.scm -- 用 Scheme 自己寫的標準函式庫。
;;; 高階函式 (map、filter ...) 寫在這裡而不是 Python,
;;; 這樣它們呼叫的 lambda 也走同一台機器:尾呼叫、call/cc 都能正常運作。

(define (%check-list who l)
  (if (not (list? l))
      (error (string-append who ": expected proper list, got") l)))

(define (%map1 f l)
  (let loop ((l l) (acc '()))
    (cond ((pair? l) (loop (cdr l) (cons (f (car l)) acc)))
          ((null? l) (reverse acc))
          (else (error "map: expected proper list, got" l)))))

(define (%cars ls) (%map1 car ls))
(define (%cdrs ls) (%map1 cdr ls))
(define (%any-null? ls)
  (cond ((null? ls) #f) ((null? (car ls)) #t) (else (%any-null? (cdr ls)))))

(define (map f l . rest)
  (if (null? rest)
      (%map1 f l)
      (let loop ((ls (cons l rest)) (acc '()))
        (if (%any-null? ls)
            (reverse acc)
            (loop (%cdrs ls) (cons (apply f (%cars ls)) acc))))))

(define (for-each f l . rest)
  (if (null? rest)
      (let loop ((l l))
        (cond ((pair? l) (f (car l)) (loop (cdr l)))
              ((null? l) #t)
              (else (error "for-each: expected proper list, got" l))))
      (let loop ((ls (cons l rest)))
        (if (%any-null? ls)
            #t
            (begin (apply f (%cars ls)) (loop (%cdrs ls)))))))

(define (append-map f . ls) (apply append (apply map f ls)))

(define (filter pred l)
  (%check-list "filter" l)
  (let loop ((l l) (acc '()))
    (cond ((null? l) (reverse acc))
          ((pred (car l)) (loop (cdr l) (cons (car l) acc)))
          (else (loop (cdr l) acc)))))

(define (remove pred l) (filter (lambda (x) (not (pred x))) l))

(define (partition pred l)
  (cons (filter pred l) (remove pred l)))

(define (fold-left f init l)
  (%check-list "fold-left" l)
  (let loop ((acc init) (l l))
    (if (null? l) acc (loop (f acc (car l)) (cdr l)))))

(define (fold-right f init l)
  (%check-list "fold-right" l)
  (let loop ((l (reverse l)) (acc init))
    (if (null? l) acc (loop (cdr l) (f (car l) acc)))))

(define (fold f init l)
  (%check-list "fold" l)
  (let loop ((acc init) (l l))
    (if (null? l) acc (loop (f (car l) acc) (cdr l)))))

(define (reduce f init l)
  (%check-list "reduce" l)
  (if (null? l)
      init
      (let loop ((acc (car l)) (l (cdr l)))
        (if (null? l) acc (loop (f (car l) acc) (cdr l))))))

(define reduce-left reduce)

(define (delete x l) (filter (lambda (y) (not (equal? x y))) l))

(define (delete-duplicates l)
  (let loop ((l l) (acc '()))
    (cond ((null? l) (reverse acc))
          ((member (car l) acc) (loop (cdr l) acc))
          (else (loop (cdr l) (cons (car l) acc))))))

(define (find pred l)
  (cond ((null? l) #f) ((pred (car l)) (car l)) (else (find pred (cdr l)))))

(define (find-tail pred l)
  (cond ((null? l) #f) ((pred (car l)) l) (else (find-tail pred (cdr l)))))

(define (list-index pred l)
  (let loop ((l l) (i 0))
    (cond ((null? l) #f) ((pred (car l)) i) (else (loop (cdr l) (+ i 1))))))

(define (any pred l)
  (cond ((null? l) #f) ((null? (cdr l)) (pred (car l)))
        ((pred (car l)) => (lambda (x) x))
        (else (any pred (cdr l)))))

(define (every pred l)
  (cond ((null? l) #t) ((null? (cdr l)) (pred (car l)))
        ((pred (car l)) (every pred (cdr l)))
        (else #f)))

(define (count pred l)
  (let loop ((l l) (n 0))
    (cond ((null? l) n) ((pred (car l)) (loop (cdr l) (+ n 1))) (else (loop (cdr l) n)))))

(define (list-tabulate n f)
  (let loop ((i (- n 1)) (acc '()))
    (if (< i 0) acc (loop (- i 1) (cons (f i) acc)))))

(define make-initialized-list list-tabulate)

(define (first l) (car l))
(define (second l) (cadr l))
(define (third l) (caddr l))
(define (last l) (car (last-pair l)))

(define (%merge less? a b)
  (let loop ((a a) (b b) (acc '()))
    (cond ((null? a) (append (reverse acc) b))
          ((null? b) (append (reverse acc) a))
          ((less? (car b) (car a)) (loop a (cdr b) (cons (car b) acc)))
          (else (loop (cdr a) b (cons (car a) acc))))))

(define (%sort-list l less?)
  (let ((n (length l)))
    (if (< n 2)
        l
        (let ((half (quotient n 2)))
          (%merge less?
                  (%sort-list (list-head l half) less?)
                  (%sort-list (list-tail l half) less?))))))

(define (sort seq less?)
  (if (vector? seq)
      (list->vector (%sort-list (vector->list seq) less?))
      (begin (%check-list "sort" seq) (%sort-list seq less?))))

(define list-sort (lambda (less? l) (sort l less?)))

(define (vector-map f v . rest)
  (list->vector (apply map f (vector->list v) (map vector->list rest))))

(define (vector-for-each f v . rest)
  (apply for-each f (vector->list v) (map vector->list rest)))

(define (string-for-each f s) (for-each f (string->list s)))
(define (string-map f s) (list->string (map f (string->list s))))
(define (string-count s pred) (count pred (string->list s)))

(define (char-ascii? c) (< (char->integer c) 128))

;;; 雜湊表中需要呼叫 Scheme 程序的部分
(define (hash-table-ref table key . fail)
  (let ((v (hash-table-ref/default table key %hash-missing)))
    (if (eq? v %hash-missing)
        (if (pair? fail) ((car fail)) (error "hash-table-ref: key not found:" key))
        v)))
(define %hash-missing (list 'missing))
(define (hash-table-update! table key proc . fail)
  (hash-table-set! table key (proc (apply hash-table-ref table key fail))))
(define (hash-table-update!/default table key proc default)
  (hash-table-set! table key (proc (hash-table-ref/default table key default))))
(define (hash-table-walk table proc)
  (for-each (lambda (p) (proc (car p) (cdr p))) (hash-table->alist table)))

;;; 串流 (SICP 風格,cons-stream 是特殊形式)
(define the-empty-stream '())
(define stream-nil '())
(define (stream-pair? s) (and (pair? s) (promise? (cdr s))))
(define (stream-null? s) (null? s))
(define empty-stream? stream-null?)
(define (stream-car s) (car s))
(define (stream-cdr s) (force (cdr s)))
(define (stream-first s) (stream-car s))
(define (stream-rest s) (stream-cdr s))

(define (stream-head s n)
  (if (= n 0) '() (cons (stream-car s) (stream-head (stream-cdr s) (- n 1)))))
(define (stream-tail s n)
  (if (= n 0) s (stream-tail (stream-cdr s) (- n 1))))
(define (stream-ref s n)
  (if (= n 0) (stream-car s) (stream-ref (stream-cdr s) (- n 1))))
(define (stream->list s . opt)
  (let loop ((s s) (n (if (pair? opt) (car opt) -1)) (acc '()))
    (if (or (null? s) (= n 0))
        (reverse acc)
        (loop (stream-cdr s) (- n 1) (cons (stream-car s) acc)))))
(define (stream-map f s . rest)
  (if (null? rest)
      (if (null? s)
          '()
          (cons-stream (f (stream-car s)) (stream-map f (stream-cdr s))))
      (let ((ss (cons s rest)))
        (if (%any-null? ss)
            '()
            (cons-stream (apply f (map stream-car ss))
                         (apply stream-map f (map stream-cdr ss)))))))
(define (stream-filter pred s)
  (cond ((null? s) '())
        ((pred (stream-car s))
         (cons-stream (stream-car s) (stream-filter pred (stream-cdr s))))
        (else (stream-filter pred (stream-cdr s)))))
(define (stream-for-each f s)
  (if (null? s) #t (begin (f (stream-car s)) (stream-for-each f (stream-cdr s)))))
(define (list->stream l)
  (if (null? l) '() (cons-stream (car l) (list->stream (cdr l)))))
(define (make-promise v) (delay v))

DROP TABLE IF EXISTS t1;

CREATE TABLE t1 (
    id INT,
    num INT,
    INDEX idx_num (num)
);

INSERT INTO t1 VALUES
(1, 123),
(2, 456),
(3, 789);

-- implicit cast
EXPLAIN SELECT * FROM t1 WHERE num = '123';

-- correct
EXPLAIN SELECT * FROM t1 WHERE num = 123;
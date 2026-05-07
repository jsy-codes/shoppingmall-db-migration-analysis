DROP TABLE IF EXISTS t23;

CREATE TABLE t23 (
    id INT,
    name VARCHAR(50)
);

-- ❌ Oracle style (문제)
INSERT INTO t23 VALUES (my_seq.NEXTVAL, 'Alice');

-- ✅ MySQL style (개선)
INSERT INTO t23 (name) VALUES ('Bob');
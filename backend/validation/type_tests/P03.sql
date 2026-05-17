DROP TABLE IF EXISTS t3;

CREATE TABLE t3 (
    id INT
);

INSERT INTO t3 VALUES
(1),(2),(3),(4),(5),(6);

-- Oracle style (should fail)
SELECT * FROM t3 WHERE ROWNUM <= 3;

-- MySQL style
SELECT * FROM t3 LIMIT 3;
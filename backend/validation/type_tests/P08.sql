DROP TABLE IF EXISTS t8;

CREATE TABLE t8 (
    name VARCHAR(20)
);

INSERT INTO t8 VALUES
('kim'),
('lee'),
('park');

CREATE INDEX idx_name ON t8(name);

EXPLAIN SELECT * FROM t8 WHERE name = 'kim';

EXPLAIN SELECT * FROM t8 WHERE UPPER(name) = 'KIM';
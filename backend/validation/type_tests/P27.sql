DROP TABLE IF EXISTS t27;

CREATE TABLE t27 (
    name VARCHAR(50)
);

INSERT INTO t27 VALUES ('Alice'), ('bob'), ('CHARLIE');

-- ❌ Oracle
SELECT * FROM t27 WHERE REGEXP_LIKE(name, '^a', 'i');

-- ✅ MySQL
SELECT * FROM t27 WHERE name REGEXP '^a';
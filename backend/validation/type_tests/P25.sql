DROP TABLE IF EXISTS t25;

-- ❌ Oracle NUMBER
CREATE TABLE t25 (
    price NUMBER(10,2),
    count NUMBER
);

-- ✅ MySQL 변환
CREATE TABLE t25_new (
    price DECIMAL(10,2),
    count INT
);
-- P25.sql에 추가
INSERT INTO t25_new VALUES (29900.50, 100);
INSERT INTO t25_new VALUES (5500.00, 250);


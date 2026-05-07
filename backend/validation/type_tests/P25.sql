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
DROP TABLE IF EXISTS t30;

-- ❌ Oracle Unicode 타입
CREATE TABLE t30 (
    name NVARCHAR2(50),
    code NCHAR(10)
);

-- ✅ MySQL charset 명시
CREATE TABLE t30_new (
    name VARCHAR(50) CHARACTER SET utf8mb4,
    code CHAR(10) CHARACTER SET utf8mb4
);
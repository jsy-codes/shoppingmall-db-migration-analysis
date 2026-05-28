-- ============================================================
-- badQuery 설계 초안 — 공개 DB (Grocery Oracle + DS3) 기반
-- 생성일시: 2026-05-26 23:43:39
-- 대상 테이블: DS3(CUSTOMERS, ORDERS, PRODUCTS, ORDERLINES 등)
--              Grocery Oracle(jta_* 테이블)
-- 탐지 기반 패턴: P01, P02, P04, P05, P06, P07, P09, P10, P13, P15, P20, P21, P22, P23, P25
-- ============================================================

-- 🚨 [P01] Implicit Type Cast (MEDIUM): CUSTOMERS customerid(NUMBER)에 문자열 비교
SELECT * FROM CUSTOMERS WHERE customerid = '12345';

-- 🚨 [P01] Implicit Type Cast (MEDIUM): ORDERS customerid VARCHAR 비교
SELECT * FROM ORDERS WHERE customerid = 100;

-- 🚨 [P02] Function on Indexed Column (HIGH): CUSTOMERS email UPPER 인덱스 우회
SELECT * FROM CUSTOMERS WHERE UPPER(email) LIKE '%@GMAIL.COM%';

-- 🚨 [P02] Function on Indexed Column (HIGH): PRODUCTS title LOWER 인덱스 우회
SELECT * FROM PRODUCTS WHERE LOWER(title) = 'inception';

-- 🚨 [P04] NVL Function (LOW): ORDERS netamount NVL null 치환
SELECT orderid, NVL(netamount, 0) FROM ORDERS WHERE customerid = 500;

-- 🚨 [P04] NVL Function (LOW): INVENTORY quan_in_stock NVL
SELECT prod_id, NVL(quan_in_stock, 0) FROM INVENTORY WHERE sales > 100;

-- 🚨 [P05] DATE vs DATETIME (MEDIUM): ORDERS orderdate DATE 비교
SELECT * FROM ORDERS WHERE DATE(orderdate) = '2024-01-15';

-- 🚨 [P05] DATE vs DATETIME (MEDIUM): ORDERS CAST AS DATE 시간 손실
SELECT * FROM ORDERS WHERE CAST(orderdate AS DATE) BETWEEN '2024-01-01' AND '2024-03-31';

-- 🚨 [P06] VARCHAR2 Usage (LOW): CUSTOMERS 임시 테이블 VARCHAR2
CREATE TEMPORARY TABLE temp_vip (cust_id VARCHAR2(20), grade VARCHAR2(10));

-- 🚨 [P09] JOIN Without Index (HIGH): CUSTOMERS-ORDERS 비인덱스 컬럼 JOIN
SELECT c.firstname, o.totalamount FROM CUSTOMERS c JOIN ORDERS o ON c.country = o.orderdate;

-- 🚨 [P09] JOIN Without Index (HIGH): PRODUCTS-ORDERLINES LIKE JOIN
SELECT p.title, ol.quantity FROM PRODUCTS p JOIN ORDERLINES ol ON p.title LIKE CONCAT('%', ol.prod_id, '%');

-- 🚨 [P10] Nested Subquery (MEDIUM): 3중 중첩 IN (CUST_HIST → ORDERS → CUSTOMERS)
SELECT * FROM CUSTOMERS WHERE customerid IN (
    SELECT customerid FROM ORDERS WHERE orderid IN (
        SELECT orderid FROM ORDERLINES WHERE prod_id IN (
            SELECT prod_id FROM PRODUCTS WHERE category = 'DVD'
        )
    )
);

-- 🚨 [P10] Nested Subquery (MEDIUM): 상관 서브쿼리 (고객별 총 주문액)
SELECT c.firstname, (SELECT SUM(o.totalamount) FROM ORDERS o WHERE o.customerid = c.customerid) FROM CUSTOMERS c;

-- 🚨 [P13] START WITH Hierarchy (MEDIUM): Grocery 카테고리 계층 START WITH
SELECT * FROM jta_categories START WITH parent_id IS NULL CONNECT BY PRIOR cat_id = parent_id;

-- 🚨 [P15] SYSDATE Usage (LOW): ORDERS 최근 30일 SYSDATE 비교
SELECT * FROM ORDERS WHERE orderdate >= SYSDATE - 30;

-- 🚨 [P15] SYSDATE Usage (LOW): CUSTOMERS 등록일 SYSDATE 비교
SELECT * FROM CUSTOMERS WHERE creditcardexpiration > SYSDATE;

-- 🚨 [P20] TO_CHAR Date Formatting (MEDIUM): ORDERS 월별 집계 TO_CHAR
SELECT TO_CHAR(orderdate, 'YYYY-MM'), COUNT(*), SUM(totalamount) FROM ORDERS GROUP BY TO_CHAR(orderdate, 'YYYY-MM');

-- 🚨 [P20] TO_CHAR Date Formatting (MEDIUM): PRODUCTS 가격 TO_CHAR 포맷
SELECT title, TO_CHAR(price, '999,990.00') FROM PRODUCTS WHERE special = 1;

-- 🚨 [P21] TO_DATE Parsing (MEDIUM): ORDERS TO_DATE 날짜 파싱
SELECT * FROM ORDERS WHERE orderdate >= TO_DATE('2024-01-01', 'YYYY-MM-DD');

-- 🚨 [P22] TRUNC Date Function (MEDIUM): ORDERS 월별 집계 TRUNC
SELECT TRUNC(orderdate, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(orderdate, 'MM');

-- 🚨 [P23] SEQUENCE NEXTVAL/CURRVAL (HIGH): ORDERS 시퀀스 채번 INSERT
INSERT INTO ORDERS (orderid, orderdate, customerid) VALUES (order_seq.NEXTVAL, SYSDATE, 100);

-- 🚨 [P25] NUMBER Type Declaration (LOW): 임시 주문 테이블 NUMBER 타입
CREATE TABLE temp_orders (order_id NUMBER, amount NUMBER(12,2), status VARCHAR2(20));

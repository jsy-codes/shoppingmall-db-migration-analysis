-- ============================================================
-- Oracle Pattern Fixture SQL
-- 목적:
--   시나리오 A에서 미탐지 패턴(P03,P12,P14,P17,P19,P24~P30)을
--   강제로 포함시켜 탐지 검증용으로 사용
-- ============================================================


---------------------------------------------------------------
-- P03 : ROWNUM Pagination
---------------------------------------------------------------
SELECT *
FROM (
    SELECT p.*, ROWNUM rn
    FROM jta_products p
    WHERE ROWNUM <= 20
)
WHERE rn > 10;


---------------------------------------------------------------
-- P12 : CONNECT BY Hierarchy
---------------------------------------------------------------
SELECT category_id,
       parent_category_id
FROM jta_categories
CONNECT BY PRIOR category_id = parent_category_id;


---------------------------------------------------------------
-- P14 : Oracle Outer Join (+)
---------------------------------------------------------------
SELECT p.product_id,
       c.category_name
FROM jta_products p,
     jta_categories c
WHERE p.category_id = c.category_id(+);


---------------------------------------------------------------
-- P17 : MERGE INTO Statement
---------------------------------------------------------------
MERGE INTO jta_products tgt
USING jta_products_stage src
ON (tgt.product_id = src.product_id)
WHEN MATCHED THEN
    UPDATE SET tgt.price = src.price
WHEN NOT MATCHED THEN
    INSERT (product_id, price)
    VALUES (src.product_id, src.price);


---------------------------------------------------------------
-- P19 : DUAL Table Dependency
---------------------------------------------------------------
SELECT SYSDATE
FROM DUAL;


---------------------------------------------------------------
-- P24 : LISTAGG Aggregation
---------------------------------------------------------------
SELECT category_id,
       LISTAGG(product_name, ',')
           WITHIN GROUP (ORDER BY product_name)
FROM jta_products
GROUP BY category_id;


---------------------------------------------------------------
-- P26 : CONNECT BY NOCYCLE
---------------------------------------------------------------
SELECT category_id,
       parent_category_id
FROM jta_categories
START WITH parent_category_id IS NULL
CONNECT BY NOCYCLE
       PRIOR category_id = parent_category_id;


---------------------------------------------------------------
-- P27 : REGEXP_LIKE Function
---------------------------------------------------------------
SELECT *
FROM jta_customers
WHERE REGEXP_LIKE(
    email,
    '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
);


---------------------------------------------------------------
-- P28 : PIVOT Operator
---------------------------------------------------------------
SELECT *
FROM (
    SELECT category_id,
           status,
           amount
    FROM jta_sales
)
PIVOT (
    SUM(amount)
    FOR status IN (
        'ACTIVE'   AS active_amt,
        'INACTIVE' AS inactive_amt
    )
);


---------------------------------------------------------------
-- P29 : WM_CONCAT Aggregation
---------------------------------------------------------------
SELECT category_id,
       WM_CONCAT(product_name)
FROM jta_products
GROUP BY category_id;


---------------------------------------------------------------
-- P30 : NCHAR / NVARCHAR2 Type
---------------------------------------------------------------
CREATE TABLE jta_unicode_test (
    id            NUMBER,
    name_nchar    NCHAR(50),
    desc_nvarchar NVARCHAR2(200)
);
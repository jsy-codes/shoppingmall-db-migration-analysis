-- ============================================================
-- Oracle → MySQL 마이그레이션 안티패턴 검증용 쿼리셋 (58종)
-- 대상 스키마: bucketstore_dummy
-- 테이블: MEMBERS, CATEGORIES, PRODUCTS, COUPONS,
--         ORDERS, ORDER_ITEMS, PAYMENTS
-- 패턴 범위: P01~P30 전체
-- ============================================================

-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 1 : 인덱스 무력화 (성능 저하)
-- ▌P01 Implicit Type Cast / P02 Function on Indexed Column
-- ▌P05 DATE vs DATETIME / P07 CHAR Padding / P08 Function Based Index
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P01] Implicit Type Cast (MEDIUM)
-- 암묵적 형변환 → 인덱스 무력화
-- ──────────────────────────────────────────────

-- Q01. ORDERS.member_id(VARCHAR FK)에 숫자 비교 → 형변환 발생
-- [수정] phone 컬럼 없음 → member_id(VARCHAR)와 숫자 비교로 변경
SELECT id, member_id FROM ORDERS WHERE member_id = 10050;

-- Q02. PAYMENTS.id에 산술 연산(+0) → 인덱스 완전 배제
-- [수정] receipt_id 없음 → id 사용
SELECT * FROM PAYMENTS WHERE id + 0 = 100;

-- Q03. MEMBERS.id(VARCHAR PK)를 숫자 범위 비교 → 형변환 발생
-- [수정] zip_code 없음 → id(VARCHAR)와 숫자 범위 비교로 변경
SELECT * FROM MEMBERS WHERE id > 10000 AND id < 20000;


-- ──────────────────────────────────────────────
-- [P02] Function on Indexed Column (HIGH)
-- 인덱스 컬럼에 함수 적용 → 인덱스 무력화
-- ──────────────────────────────────────────────

-- Q04. MEMBERS.email에 UPPER + 양방향 와일드카드 (최악의 성능)
SELECT id, email FROM MEMBERS WHERE UPPER(email) LIKE '%@GMAIL.COM%';

-- Q05. PRODUCTS.product_name 앞 3자리 SUBSTR 검색 → Range Scan 불가
-- [수정] product_code 없음 → product_name 사용
SELECT * FROM PRODUCTS WHERE SUBSTR(product_name, 1, 3) = 'MAC';

-- Q06. MEMBERS.name 공백 제거 후 검색 → 풀스캔
SELECT * FROM MEMBERS WHERE REPLACE(name, ' ', '') = '이동훈';


-- ──────────────────────────────────────────────
-- [P05] DATE vs DATETIME (MEDIUM)
-- 날짜 함수로 인덱스 컬럼 가공 → Range Scan 포기
-- ──────────────────────────────────────────────

-- Q13. ORDERS.created_at을 DATE()로 감싸서 풀스캔 유도
SELECT * FROM ORDERS WHERE DATE(created_at) = '2025-05-08';

-- Q14. PAYMENTS.payment_date를 CAST로 형변환 후 비교
-- [수정] approved_at 없음 → payment_date 사용
SELECT * FROM PAYMENTS WHERE CAST(payment_date AS DATE) = '2025-05-01';

-- Q15. ORDERS.created_at에 산술 연산 → 인덱스 무력화
SELECT * FROM ORDERS WHERE created_at + 1 >= '2025-05-09';


-- ──────────────────────────────────────────────
-- [P07] CHAR Padding (LOW)
-- 공백 트림 처리 → 인덱스 무력화
-- ──────────────────────────────────────────────

-- Q17. ORDERS.status에 TRIM 적용 → 풀스캔
SELECT * FROM ORDERS WHERE TRIM(status) = 'COMPLETE';

-- Q18. PAYMENTS.payment_method Oracle || 연산자로 결합 후 비교
-- [수정] p.status 없음 → payment_method 사용
SELECT * FROM PAYMENTS WHERE payment_method || ' ' = 'CARD ';


-- ──────────────────────────────────────────────
-- [P08] Function Based Index (HIGH)
-- Oracle 함수 기반 인덱스 → MySQL 구문 오류
-- ──────────────────────────────────────────────

-- Q19. MEMBERS.email 소문자 함수 기반 인덱스 생성 시도
CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email));

-- Q20. PRODUCTS.product_name 대문자 함수 기반 인덱스 생성 시도
-- [수정] category_name 없음 → product_name 사용
CREATE INDEX idx_prod_name_upper ON PRODUCTS(UPPER(product_name));


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 2 : 페이징 / 집계 함수 비호환
-- ▌P03 ROWNUM / P04 NVL / P11 DECODE
-- ▌P24 LISTAGG / P29 WM_CONCAT
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P03] ROWNUM Pagination (HIGH)
-- MySQL 미지원 페이징 → 실행 실패
-- ──────────────────────────────────────────────

-- Q07. 조건절과 결합된 ROWNUM
SELECT * FROM ORDERS WHERE status = 'PENDING' AND ROWNUM <= 100;

-- Q08. ORDER BY 수행 전 ROWNUM이 먼저 적용되는 논리적 오류
SELECT id, total_amount FROM ORDERS WHERE ROWNUM <= 10 ORDER BY total_amount DESC;

-- Q09. 서브쿼리 내 ROWNUM BETWEEN 페이징 실패
SELECT * FROM (SELECT id, created_at FROM ORDERS ORDER BY created_at DESC) WHERE ROWNUM BETWEEN 11 AND 20;


-- ──────────────────────────────────────────────
-- [P04] NVL Function (LOW)
-- MySQL 미지원 → 실행 실패 및 인덱스 우회
-- ──────────────────────────────────────────────

-- Q10. ORDERS.member_id에 NVL → 인덱스 무력화 + 풀스캔
SELECT * FROM ORDERS WHERE NVL(member_id, '0') = '10050';

-- Q11. COUPONS.discount_amount에 NVL 후 산술 연산
SELECT id FROM COUPONS WHERE NVL(discount_amount, 0) + 1000 > 5000;

-- Q12. PRODUCTS 정렬 시 NVL → Filesort 부하
-- [수정] updated_at 없음 → stock_quantity 사용
SELECT * FROM PRODUCTS ORDER BY NVL(stock_quantity, 0) DESC;


-- ──────────────────────────────────────────────
-- [P11] DECODE Function (MEDIUM)
-- Oracle 전용 분기 함수 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q27. 집계 + GROUP BY 모두 DECODE 사용
SELECT DECODE(status, 'COMPLETE', 1, 0) AS is_done, COUNT(*)
FROM ORDERS GROUP BY DECODE(status, 'COMPLETE', 1, 0);

-- Q28. WHERE절 DECODE → 인덱스 우회
SELECT * FROM PAYMENTS WHERE DECODE(payment_method, 'CARD', 1, 0) = 1;


-- ──────────────────────────────────────────────
-- [P24] LISTAGG Aggregation (HIGH)
-- Oracle 전용 문자열 집계 → MySQL 실행 실패
-- ──────────────────────────────────────────────

-- Q52. Oracle LISTAGG 집계 함수 사용
SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM CATEGORIES;


-- ──────────────────────────────────────────────
-- [P29] WM_CONCAT Aggregation (HIGH)
-- Oracle deprecated 집계 함수 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q57. WM_CONCAT 문자열 집계
SELECT WM_CONCAT(product_name) FROM PRODUCTS;


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 3 : 계층 쿼리 비호환
-- ▌P12 CONNECT BY / P13 START WITH / P26 CONNECT BY NOCYCLE
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P12] CONNECT BY Hierarchy (HIGH)
-- Oracle 재귀 쿼리 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q29. 카테고리 무한 루프 위험 계층 조회
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id;

-- Q30. 레벨 제한 계층 조회
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id AND LEVEL <= 3;


-- ──────────────────────────────────────────────
-- [P13] START WITH Hierarchy (MEDIUM)
-- Oracle 계층 시작 조건 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q31. 최상위 카테고리부터 시작하는 계층 조회 (P12+P13 복합)
SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id;


-- ──────────────────────────────────────────────
-- [P26] CONNECT BY NOCYCLE (HIGH)
-- 순환 참조 탐지 계층 쿼리 → MySQL 직접 대응 없음
-- ──────────────────────────────────────────────

-- Q54. NOCYCLE 순환 방지 계층 조회 (P12+P26 복합)
SELECT id, parent_id FROM CATEGORIES CONNECT BY NOCYCLE PRIOR id = parent_id;


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 4 : 조인 성능 저하
-- ▌P09 JOIN Without Index / P14 Oracle Outer Join (+)
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P09] JOIN Without Index (HIGH)
-- 인덱스 없는 컬럼 조인 → 카테시안 곱 수준 성능 저하
-- ──────────────────────────────────────────────

-- Q21. MEMBERS.status ↔ ORDERS.status 비인덱스 컬럼 조인
-- [수정] address/shipping_address 없음 → status 컬럼 조인으로 변경
SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status;

-- Q22. PRODUCTS.product_name LIKE로 CATEGORIES.name 포함 조인
-- [수정] description/category_name 없음 → product_name, CATEGORIES.name 사용
SELECT p.product_name, c.name
FROM PRODUCTS p JOIN CATEGORIES c ON p.product_name LIKE CONCAT('%', c.name, '%');

-- Q23. DATE() 함수 씌워 조인 (P05+P09 복합)
-- [수정] approved_at 없음 → payment_date 사용
SELECT o.id, p.id FROM ORDERS o
JOIN PAYMENTS p ON DATE(o.created_at) = DATE(p.payment_date) AND o.id = p.order_id;


-- ──────────────────────────────────────────────
-- [P14] Oracle Outer Join (+) (HIGH)
-- 레거시 조인 문법 → MySQL 실행 실패
-- ──────────────────────────────────────────────

-- Q32. WHERE절 (+) 1:N 아우터 조인
SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+);

-- Q33. 다중 테이블 아우터 조인 + 추가 조건
-- [수정] p.status 없음 → p.payment_method 사용
SELECT o.id, p.id FROM ORDERS o, PAYMENTS p
WHERE o.id = p.order_id (+) AND p.payment_method (+) = 'CARD';

-- Q34. 카테고리-상품 아우터 조인 + 가격 조건
SELECT c.name, p.product_name FROM CATEGORIES c, PRODUCTS p
WHERE c.id (+) = p.category_id AND p.price > 10000;


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 5 : 서브쿼리 성능 저하
-- ▌P10 Nested Subquery
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P10] Nested Subquery (MEDIUM)
-- DEPENDENT SUBQUERY → 옵티마이저 한계 도달
-- ──────────────────────────────────────────────

-- Q24. 3중 중첩 IN 절 → 풀스캔 유발
SELECT * FROM PRODUCTS WHERE id IN (
  SELECT product_id FROM ORDER_ITEMS WHERE order_id IN (
    SELECT id FROM ORDERS WHERE member_id IN (
      SELECT id FROM MEMBERS WHERE status = 'INACTIVE'
    )
  )
);

-- Q25. SELECT절 상관 서브쿼리 + ROWNUM (P03+P10 복합)
SELECT m.name, (
  SELECT MAX(total_amount) FROM ORDERS o WHERE o.member_id = m.id AND ROWNUM = 1
) FROM MEMBERS m;

-- Q26. 중첩 EXISTS → 복잡한 상태 체크로 옵티마이저 포기
SELECT id FROM ORDERS o WHERE EXISTS (
  SELECT 1 FROM PAYMENTS p WHERE p.order_id = o.id AND EXISTS (
    SELECT 1 FROM COUPONS c WHERE c.member_id = o.member_id
  )
);


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 6 : 날짜 / 시간 함수 비호환
-- ▌P15 SYSDATE / P16 SYSTIMESTAMP
-- ▌P20 TO_CHAR / P21 TO_DATE / P22 TRUNC
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P15] SYSDATE Usage (LOW)
-- MySQL NOW()와의 호환성 문제
-- ──────────────────────────────────────────────

-- Q35. COUPONS.valid_until에 SYSDATE 날짜 연산
SELECT * FROM COUPONS WHERE valid_until >= SYSDATE - 7;

-- Q36. SYSDATE + TO_CHAR 혼용 (P15+P20 복합)
SELECT * FROM ORDERS WHERE TO_CHAR(SYSDATE, 'YYYYMMDD') = TO_CHAR(created_at, 'YYYYMMDD');


-- ──────────────────────────────────────────────
-- [P16] SYSTIMESTAMP Usage (MEDIUM)
-- 밀리초 정밀도 문제 → DATETIME 손실
-- ──────────────────────────────────────────────

-- Q37. PAYMENTS.payment_date에 SYSTIMESTAMP 업데이트
-- [수정] approved_at 없음 → payment_date 사용
UPDATE PAYMENTS SET payment_date = SYSTIMESTAMP WHERE payment_method = 'CARD';

-- Q38. ORDERS.created_at과 INTERVAL 연산 혼용
SELECT * FROM ORDERS WHERE created_at > SYSTIMESTAMP - INTERVAL '1' DAY;


-- ──────────────────────────────────────────────
-- [P20] TO_CHAR Date Formatting (MEDIUM)
-- Oracle 포맷 함수 → MySQL DATE_FORMAT과 불일치
-- ──────────────────────────────────────────────

-- Q44. 일별 매출 집계 — 조건절+GROUP BY 모두 TO_CHAR (풀스캔)
SELECT TO_CHAR(created_at, 'YYYYMMDD'), SUM(total_amount)
FROM ORDERS
WHERE TO_CHAR(created_at, 'YYYYMMDD') LIKE '202505%'
GROUP BY TO_CHAR(created_at, 'YYYYMMDD');

-- Q45. PAYMENTS.payment_date 시분초 포맷 정렬
-- [수정] approved_at → payment_date
SELECT * FROM PAYMENTS ORDER BY TO_CHAR(payment_date, 'YYYY-MM-DD HH24:MI:SS') DESC;

-- Q46. PRODUCTS.price 숫자 포맷으로 변환해 비교
SELECT * FROM PRODUCTS WHERE TO_CHAR(price, '999,999') = '10,000';


-- ──────────────────────────────────────────────
-- [P21] TO_DATE Parsing (MEDIUM)
-- Oracle TO_DATE → MySQL STR_TO_DATE와 불일치
-- ──────────────────────────────────────────────

-- Q47. PAYMENTS.payment_date에 TO_DATE 시간 포맷 비교
-- [수정] approved_at → payment_date
SELECT * FROM PAYMENTS
WHERE payment_date >= TO_DATE('2025-05-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS');

-- Q48. ORDERS.created_at BETWEEN TO_DATE 연속 사용
SELECT * FROM ORDERS
WHERE created_at BETWEEN TO_DATE('20250101', 'YYYYMMDD') AND TO_DATE('20251231', 'YYYYMMDD');


-- ──────────────────────────────────────────────
-- [P22] TRUNC Date Function (MEDIUM)
-- 날짜 절삭 → 인덱스 무력화
-- ──────────────────────────────────────────────

-- Q49. ORDERS 월별 집계 TRUNC → 풀스캔
SELECT TRUNC(created_at, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at, 'MM');

-- Q50. PAYMENTS.payment_date TRUNC + SYSDATE (P22+P15 복합)
-- [수정] approved_at → payment_date
SELECT * FROM PAYMENTS WHERE TRUNC(payment_date) = TRUNC(SYSDATE - 1);


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 7 : Oracle 전용 타입 / DDL 비호환
-- ▌P06 VARCHAR2 / P25 NUMBER / P30 NCHAR·NVARCHAR2
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P06] VARCHAR2 Usage (LOW)
-- Oracle 전용 문자열 타입 → MySQL 실행 실패
-- ──────────────────────────────────────────────

-- Q16. 임시 테이블 생성 시 VARCHAR2 사용
CREATE TEMPORARY TABLE temp_vip_users (user_id VARCHAR2(50), grade VARCHAR2(10));


-- ──────────────────────────────────────────────
-- [P25] NUMBER Type Declaration (LOW)
-- Oracle NUMBER 타입 → MySQL 명시적 매핑 필요
-- ──────────────────────────────────────────────

-- Q53. Oracle NUMBER 타입으로 테이블 생성
CREATE TABLE t25 (
    price NUMBER(10,2),
    count NUMBER
);


-- ──────────────────────────────────────────────
-- [P30] NCHAR / NVARCHAR2 Type (LOW)
-- Oracle Unicode 전용 타입 → MySQL charset으로 대체 필요
-- ──────────────────────────────────────────────

-- Q58. Oracle NVARCHAR2/NCHAR 타입 선언
CREATE TABLE t30 (
    name NVARCHAR2(50),
    code NCHAR(10)
);


-- ══════════════════════════════════════════════════════════
-- ▌CATEGORY 8 : Oracle 전용 구문 / 연산자 비호환
-- ▌P17 MERGE INTO / P18 MINUS / P19 DUAL
-- ▌P23 SEQUENCE / P27 REGEXP_LIKE / P28 PIVOT
-- ══════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────
-- [P17] MERGE INTO Statement (HIGH)
-- Oracle 전용 UPSERT → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q39. 재고 차감 MERGE INTO (WHEN MATCHED) + DUAL (P17+P19 복합)
-- [수정] stock → stock_quantity
MERGE INTO PRODUCTS p
USING (SELECT 50 AS id, 10 AS qty FROM DUAL) d
ON (p.id = d.id)
WHEN MATCHED THEN UPDATE SET p.stock_quantity = p.stock_quantity - d.qty;

-- Q40. 회원 상태 MERGE INTO (WHEN NOT MATCHED) + DUAL (P17+P19 복합)
-- [수정] MEMBERS.id는 VARCHAR(50) → 문자열 리터럴 사용
MERGE INTO MEMBERS m
USING (SELECT 'USR10050' AS id, 'ACTIVE' AS status FROM DUAL) d
ON (m.id = d.id)
WHEN NOT MATCHED THEN INSERT (id, name, email, status)
VALUES (d.id, 'Unknown', 'unknown@test.com', d.status);


-- ──────────────────────────────────────────────
-- [P18] MINUS Set Operator (MEDIUM)
-- Oracle 차집합 → MySQL EXCEPT 미지원
-- ──────────────────────────────────────────────

-- Q41. 주문 이력 없는 회원 도출 (MINUS)
SELECT id FROM MEMBERS
MINUS
SELECT member_id FROM ORDERS WHERE created_at > '2024-01-01';

-- Q42. 팔리지 않은 상품 도출 (MINUS)
SELECT id FROM PRODUCTS
MINUS
SELECT product_id FROM ORDER_ITEMS;


-- ──────────────────────────────────────────────
-- [P19] DUAL Table Dependency (LOW)
-- Oracle 시스템 테이블 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q43. 시퀀스 NEXTVAL FROM DUAL (AUTO_INCREMENT와 충돌)
SELECT member_seq.NEXTVAL FROM DUAL;


-- ──────────────────────────────────────────────
-- [P23] SEQUENCE NEXTVAL / CURRVAL (HIGH)
-- Oracle 시퀀스 채번 → MySQL AUTO_INCREMENT와 충돌
-- ──────────────────────────────────────────────

-- Q51. Oracle SEQUENCE.NEXTVAL INSERT
INSERT INTO ORDERS (id, member_id, status, total_amount)
VALUES (my_seq.NEXTVAL, 'USR001', 'PENDING', 15000);

-- Q51-B. CURRVAL 참조
SELECT my_seq.CURRVAL FROM DUAL;


-- ──────────────────────────────────────────────
-- [P27] REGEXP_LIKE Function (MEDIUM)
-- Oracle 전용 정규식 함수 → MySQL REGEXP와 동작 차이
-- ──────────────────────────────────────────────

-- Q55. REGEXP_LIKE 대소문자 무시 플래그 사용
SELECT * FROM MEMBERS WHERE REGEXP_LIKE(name, '^kim', 'i');


-- ──────────────────────────────────────────────
-- [P28] PIVOT / UNPIVOT Operator (HIGH)
-- Oracle 전용 피벗 연산자 → MySQL 미지원
-- ──────────────────────────────────────────────

-- Q56. Oracle PIVOT으로 연도별 매출 집계
SELECT * FROM (
    SELECT member_id, status, total_amount FROM ORDERS
)
PIVOT (
    SUM(total_amount)
    FOR status IN ('PENDING', 'COMPLETE', 'CANCEL')
);
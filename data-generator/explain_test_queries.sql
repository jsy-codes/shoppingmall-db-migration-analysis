-- ============================================================
-- EXPLAIN 실험용 테스트 쿼리 10종
-- 대상 DB: bucketstore_dummy (ORDERS 100만건 기준)
-- 목적: 안티패턴 적용 전/후 실행계획 및 성능 차이 측정
-- 실행법: MySQL에서 각 쿼리 앞에 EXPLAIN 붙여서 실행
--         ex) EXPLAIN SELECT * FROM ORDERS WHERE ...
-- ============================================================

-- ══════════════════════════════════════════════════════════
-- EQ01. 인덱스 컬럼에 함수 적용 (P02 — Function on Indexed Column)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: UPPER() 씌워서 인덱스 무력화 → 풀스캔
EXPLAIN SELECT id, email
FROM MEMBERS
WHERE UPPER(email) = 'USER10001@TESTMAIL.COM';

-- ✅ 개선: 함수 제거 → 인덱스 사용
EXPLAIN SELECT id, email
FROM MEMBERS
WHERE email = 'user10001@testmail.com';


-- ══════════════════════════════════════════════════════════
-- EQ02. ROWNUM 페이징 vs LIMIT (P03 — ROWNUM Pagination)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: ROWNUM (MySQL에서 실행 실패 — 실행계획만 확인)
-- EXPLAIN SELECT * FROM ORDERS WHERE ROWNUM <= 10;

-- ✅ 개선: LIMIT 사용 → 인덱스 Range Scan
EXPLAIN SELECT *
FROM ORDERS
ORDER BY created_at DESC
LIMIT 10;


-- ══════════════════════════════════════════════════════════
-- EQ03. DATE() 함수로 인덱스 무력화 (P05 — DATE vs DATETIME)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: DATE() 함수 씌워서 풀스캔
EXPLAIN SELECT *
FROM ORDERS
WHERE DATE(created_at) = '2025-01-01';

-- ✅ 개선: BETWEEN으로 범위 조건 → 인덱스 Range Scan
EXPLAIN SELECT *
FROM ORDERS
WHERE created_at >= '2025-01-01 00:00:00'
  AND created_at <  '2025-01-02 00:00:00';


-- ══════════════════════════════════════════════════════════
-- EQ04. 암묵적 형변환 (P01 — Implicit Type Cast)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: VARCHAR 컬럼에 숫자 비교 → 형변환 발생, 인덱스 무력화
EXPLAIN SELECT *
FROM ORDERS
WHERE member_id = 10001;

-- ✅ 개선: 문자열 리터럴로 비교 → 인덱스 사용
EXPLAIN SELECT *
FROM ORDERS
WHERE member_id = '10001';


-- ══════════════════════════════════════════════════════════
-- EQ05. 인덱스 없는 컬럼 JOIN (P09 — JOIN Without Index)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: status 컬럼(인덱스 없음) 기준 조인 → 풀스캔 조인
EXPLAIN SELECT m.name, o.total_amount
FROM MEMBERS m
JOIN ORDERS o ON m.status = o.status
LIMIT 100;

-- ✅ 개선: PK/FK 기준 조인 → 인덱스 사용
EXPLAIN SELECT m.name, o.total_amount
FROM MEMBERS m
JOIN ORDERS o ON m.id = o.member_id
LIMIT 100;


-- ══════════════════════════════════════════════════════════
-- EQ06. 3중 중첩 서브쿼리 (P10 — Nested Subquery)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: 3중 중첩 IN → DEPENDENT SUBQUERY, 풀스캔
EXPLAIN SELECT *
FROM PRODUCTS
WHERE id IN (
    SELECT product_id FROM ORDER_ITEMS
    WHERE order_id IN (
        SELECT id FROM ORDERS
        WHERE member_id IN (
            SELECT id FROM MEMBERS WHERE status = 'INACTIVE'
        )
    )
);

-- ✅ 개선: JOIN으로 변환 → 인덱스 활용
EXPLAIN SELECT DISTINCT p.*
FROM PRODUCTS p
JOIN ORDER_ITEMS oi ON p.id = oi.product_id
JOIN ORDERS o       ON oi.order_id = o.id
JOIN MEMBERS m      ON o.member_id = m.id
WHERE m.status = 'INACTIVE';


-- ══════════════════════════════════════════════════════════
-- EQ07. TO_CHAR 날짜 포맷 (P20 — TO_CHAR Date Formatting)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: TO_CHAR로 인덱스 컬럼 가공 → 풀스캔 + 함수 미지원
-- EXPLAIN SELECT TO_CHAR(created_at, 'YYYYMMDD'), SUM(total_amount)
-- FROM ORDERS
-- WHERE TO_CHAR(created_at, 'YYYYMMDD') LIKE '202501%'
-- GROUP BY TO_CHAR(created_at, 'YYYYMMDD');

-- ✅ 개선: DATE_FORMAT + 범위 조건 → 인덱스 Range Scan
EXPLAIN SELECT DATE_FORMAT(created_at, '%Y%m%d') AS day, SUM(total_amount)
FROM ORDERS
WHERE created_at >= '2025-01-01'
  AND created_at <  '2025-02-01'
GROUP BY DATE_FORMAT(created_at, '%Y%m%d');


-- ══════════════════════════════════════════════════════════
-- EQ08. 대량 집계 — 인덱스 유무에 따른 차이
-- (P02 응용 — Function on Indexed Column)
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: 집계 시 status 컬럼에 함수 적용
EXPLAIN SELECT TRIM(status) AS status, COUNT(*), SUM(total_amount)
FROM ORDERS
GROUP BY TRIM(status);

-- ✅ 개선: 함수 제거 → 인덱스 있을 경우 활용 가능
EXPLAIN SELECT status, COUNT(*), SUM(total_amount)
FROM ORDERS
GROUP BY status;


-- ══════════════════════════════════════════════════════════
-- EQ09. 페이징 — OFFSET 방식 vs 커서 방식
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: 대량 OFFSET → 앞 페이지를 모두 읽고 버림 (풀스캔에 가까움)
EXPLAIN SELECT *
FROM ORDERS
ORDER BY created_at DESC
LIMIT 10 OFFSET 999990;

-- ✅ 개선: 커서 기반 페이징 → 인덱스 Range Scan
EXPLAIN SELECT *
FROM ORDERS
WHERE created_at < '2024-01-01 00:00:00'
ORDER BY created_at DESC
LIMIT 10;


-- ══════════════════════════════════════════════════════════
-- EQ10. 다중 테이블 집계 — 전체 파이프라인 성능 측정
-- ══════════════════════════════════════════════════════════

-- ❌ 안티패턴: 서브쿼리 + 함수 조합 → 전체 풀스캔
EXPLAIN SELECT m.id, m.name,
    (SELECT COUNT(*) FROM ORDERS o WHERE o.member_id = m.id) AS order_count,
    (SELECT SUM(total_amount) FROM ORDERS o WHERE o.member_id = m.id) AS total_spent
FROM MEMBERS m
WHERE m.status = 'ACTIVE'
LIMIT 100;

-- ✅ 개선: GROUP BY JOIN → 인덱스 활용 집계
EXPLAIN SELECT m.id, m.name,
    COUNT(o.id) AS order_count,
    SUM(o.total_amount) AS total_spent
FROM MEMBERS m
LEFT JOIN ORDERS o ON m.id = o.member_id
WHERE m.status = 'ACTIVE'
GROUP BY m.id, m.name
LIMIT 100;

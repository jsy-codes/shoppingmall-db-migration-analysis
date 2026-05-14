# EXPLAIN 테스트용 Oracle/MySQL 쿼리 쌍 5종
> D(김채운) EXPLAIN 파서 개발용 | 작성: 정성윤

---

## Case 1 — Implicit Cast (P01)
> 기대 신호: key=NULL, type=ALL

-- Oracle (문제)
SELECT * FROM orders WHERE customer_id = '1001';
-- customer_id가 INT인데 문자열로 비교 → 인덱스 무력화

-- MySQL EXPLAIN 확인
EXPLAIN SELECT * FROM orders WHERE customer_id = '1001';

-- 개선
EXPLAIN SELECT * FROM orders WHERE customer_id = 1001;

---

## Case 2 — Function on Indexed Column (P02)
> 기대 신호: type=ALL, key=NULL

-- Oracle (문제)
SELECT * FROM members WHERE UPPER(email) = 'TEST@TEST.COM';

-- MySQL EXPLAIN 확인
EXPLAIN SELECT * FROM members WHERE UPPER(email) = 'TEST@TEST.COM';

-- 개선
EXPLAIN SELECT * FROM members WHERE email = 'test@test.com';

---

## Case 3 — JOIN Without Index (P09)
> 기대 신호: rows 급증, type=ALL

-- Oracle (문제)
SELECT o.id, m.name
FROM orders o, members m
WHERE o.customer_id = m.id;

-- MySQL EXPLAIN 확인
EXPLAIN SELECT o.id, m.name
FROM orders o
JOIN members m ON o.customer_id = m.id;

-- 개선 (인덱스 추가 후 재확인)
CREATE INDEX idx_orders_customer ON orders(customer_id);
EXPLAIN SELECT o.id, m.name
FROM orders o
JOIN members m ON o.customer_id = m.id;

---

## Case 4 — Nested Subquery (P10)
> 기대 신호: DEPENDENT SUBQUERY, rows 급증

-- Oracle (문제)
SELECT * FROM orders
WHERE customer_id IN (
    SELECT id FROM members
    WHERE id IN (SELECT member_id FROM t3)
);

-- MySQL EXPLAIN 확인
EXPLAIN SELECT * FROM orders
WHERE customer_id IN (
    SELECT id FROM members
    WHERE id IN (SELECT member_id FROM t3)
);

-- 개선 (CTE)
EXPLAIN WITH base AS (SELECT member_id FROM t3)
SELECT o.* FROM orders o
JOIN members m ON o.customer_id = m.id
JOIN base b ON m.id = b.member_id;

---

## Case 5 — TRUNC Date Function (P22)
> 기대 신호: type=ALL (날짜 함수로 인덱스 무력화)

-- Oracle (문제)
SELECT * FROM orders WHERE TRUNC(order_date) = '2024-01-01';

-- MySQL EXPLAIN 확인
EXPLAIN SELECT * FROM orders
WHERE DATE(order_date) = '2024-01-01';

-- 개선 (범위 조건으로 인덱스 활용)
EXPLAIN SELECT * FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date < '2024-01-02';

---

## D 파서 추출 대상 필드
| 필드 | 의미 | 위험 신호 |
|------|------|----------|
| type | 접근 방식 | ALL = 풀스캔 |
| key | 사용된 인덱스 | NULL = 인덱스 미사용 |
| rows | 탐색 예상 행 수 | 급증 = 위험 |
| filtered | 조건 필터 비율 | 낮을수록 비효율 |
| Extra | 추가 정보 | Using temporary, Using filesort 주의 |
-- ==========================================
-- Oracle -> MySQL 마이그레이션 위험 패턴 쿼리 50선
-- 목적: AI 진단기 문법 에러 테스트 및 성능 예측 모델 부하 테스트용
-- ==========================================

-- [P01] Implicit Type Cast (MEDIUM) : 문자열-숫자 암묵적 형변환으로 인덱스 무력화
-- Q01. MEMBERS 테이블의 문자열 id를 숫자로 조회
SELECT * FROM MEMBERS WHERE id = 10500;
-- Q02. ORDERS 테이블의 문자열 member_id를 숫자로 조건 검색
SELECT id, total_amount FROM ORDERS WHERE member_id = 200;
-- Q03. PRODUCTS 테이블의 category_id를 문자열이 아닌 숫자로 비교
SELECT product_name FROM PRODUCTS WHERE category_id = 5;

-- [P02] Function on Indexed Column (HIGH) : 함수 적용으로 인덱스 탐색 우회
-- Q04. 회원 이름 검색 시 UPPER 함수 사용
SELECT id, name FROM MEMBERS WHERE UPPER(name) = 'KIM';
-- Q05. 이메일 검색 시 LOWER 함수 사용
SELECT id, email FROM MEMBERS WHERE LOWER(email) = 'test@example.com';
-- Q06. 상품명 검색 시 SUBSTR(문자열 자르기) 함수 사용
SELECT * FROM PRODUCTS WHERE SUBSTR(product_name, 1, 3) = 'MAC';

-- [P03] ROWNUM Pagination (HIGH) : MySQL 미지원 Oracle ROWNUM 페이징
-- Q07. 최근 주문 10건 조회 시도
SELECT * FROM ORDERS WHERE ROWNUM <= 10 ORDER BY created_at DESC;
-- Q08. 금액이 높은 결제 내역 5건 조회 시도
SELECT * FROM PAYMENTS WHERE ROWNUM <= 5 ORDER BY amount DESC;

-- [P04] NVL Function (LOW) : MySQL IFNULL 대신 NVL 사용 에러
-- Q09. 쿠폰 할인액이 null일 경우 0으로 치환 시도
SELECT id, NVL(discount_amount, 0) FROM COUPONS;
-- Q10. 상품 설명이 없을 경우 기본 텍스트 치환 시도
SELECT product_name, NVL(description, '설명 없음') FROM PRODUCTS;

-- [P05] DATE vs DATETIME (MEDIUM) : 시간 정보 손실/불일치 정합성 이슈
-- Q11. 오라클 방식의 DATE 타입 캐스팅 (주문일 기준)
SELECT * FROM ORDERS WHERE created_at = CAST('2025-01-01' AS DATE);
-- Q12. 결제 완료일 기준 DATE 타입 비교
SELECT id FROM PAYMENTS WHERE approved_at = CAST('2025-02-15' AS DATE);

-- [P06] VARCHAR2 Usage (LOW) : MySQL에 없는 VARCHAR2 타입 사용
-- Q13. 임시 테이블 생성 시 VARCHAR2 명시
CREATE TEMPORARY TABLE temp_users (user_id VARCHAR2(50));
-- Q14. 형변환 시 VARCHAR2 사용
SELECT CAST(name AS VARCHAR2(100)) FROM MEMBERS;

-- [P07] CHAR Padding (LOW) : 공백 패딩으로 인한 비교 결과 왜곡
-- Q15. CHAR 타입 상태값에 대한 후행 공백 미처리 비교 (주문)
SELECT * FROM ORDERS WHERE CAST(status AS CHAR(10)) = 'COMPLETED ';
-- Q16. CHAR 타입 결제수단 공백 비교
SELECT * FROM PAYMENTS WHERE CAST(payment_method AS CHAR(10)) = 'CARD      ';

-- [P08] Function Based Index (HIGH) : MySQL 미지원 함수 기반 인덱스 생성
-- Q17. 회원 이메일 소문자 변환 인덱스 생성
CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email));
-- Q18. 상품 카테고리 대문자 변환 인덱스 생성
CREATE INDEX idx_products_cat_upper ON PRODUCTS(UPPER(category_name));

-- [P09] JOIN Without Index (HIGH) : 조인 키 인덱스 부재로 인한 풀스캔/대량 탐색
-- Q19. 회원 주소와 배송지가 같은 데이터 조인 (텍스트 컬럼 조인 부하)
SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.address = o.shipping_address;
-- Q20. 상품 설명과 주문 비고란이 일치하는 데이터 조인
SELECT p.product_name FROM PRODUCTS p JOIN ORDER_ITEMS oi ON p.description = oi.remarks;
-- Q21. 결제 영수증 번호와 주문 번호 텍스트 매칭 조인
SELECT py.id, o.id FROM PAYMENTS py JOIN ORDERS o ON py.receipt_id = o.order_number;

-- [P10] Nested Subquery (MEDIUM) : 깊은 중첩 서브쿼리로 인한 최적화 저하
-- Q22. 특정 결제 금액 이상의 주문을 한 회원 조회 (3중첩)
SELECT * FROM MEMBERS WHERE id IN (
    SELECT member_id FROM ORDERS WHERE id IN (
        SELECT order_id FROM PAYMENTS WHERE amount > 100000
    )
);
-- Q23. 특정 카테고리의 상품이 포함된 주문 건 조회 (3중첩)
SELECT * FROM ORDERS WHERE id IN (
    SELECT order_id FROM ORDER_ITEMS WHERE product_id IN (
        SELECT id FROM PRODUCTS WHERE category_id = 2
    )
);
-- Q24. 미사용 쿠폰을 가진 회원의 주문 조회 (3중첩)
SELECT * FROM ORDERS WHERE member_id IN (
    SELECT id FROM MEMBERS WHERE id IN (
        SELECT member_id FROM COUPONS WHERE status = 'UNUSED'
    )
);

-- [P11] DECODE Function (MEDIUM) : 오라클 DECODE 분기 함수 사용
-- Q25. 주문 상태값 한글 변환 시도
SELECT id, DECODE(status, 'PENDING', '대기', 'COMPLETE', '완료', '기타') FROM ORDERS;
-- Q26. 결제 수단 한글 변환 시도
SELECT id, DECODE(payment_method, 'CARD', '신용카드', 'CASH', '현금', '기타') FROM PAYMENTS;

-- [P12] CONNECT BY Hierarchy (HIGH) : 재귀 CTE로 변환이 필요한 계층 쿼리
-- Q27. 카테고리 계층 구조 조회
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id;
-- Q28. 회원 추천인(다단계) 계층 조회
SELECT * FROM MEMBERS CONNECT BY PRIOR id = referrer_id;

-- [P13] START WITH Hierarchy (MEDIUM) : 계층 시작조건 문법 오류 유발
-- Q29. 카테고리 최상위 노드 지정 조회
SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id;
-- Q30. 특정 회원을 시작점으로 하는 하위 추천인 조회
SELECT * FROM MEMBERS START WITH id = 100 CONNECT BY PRIOR id = referrer_id;

-- [P14] Oracle Outer Join (+) (HIGH) : 레거시 오라클 조인 문법 미지원 에러
-- Q31. 주문이 없는 회원까지 모두 조회 (아우터 조인)
SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+);
-- Q32. 결제 내역이 없는 주문까지 모두 조회
SELECT o.id, p.amount FROM ORDERS o, PAYMENTS p WHERE o.id = p.order_id (+);

-- [P15] SYSDATE Usage (LOW) : MySQL NOW() 대신 SYSDATE 사용
-- Q33. 어제부터 오늘까지 들어온 주문 조회
SELECT * FROM ORDERS WHERE created_at >= SYSDATE - 1;
-- Q34. 오늘 만료되는 쿠폰 조회
SELECT * FROM COUPONS WHERE valid_until = SYSDATE;

-- [P16] SYSTIMESTAMP Usage (MEDIUM) : 타임스탬프 정밀도 차이 유발
-- Q35. 주문 수정 일자에 오라클 타임스탬프 기록 시도
UPDATE ORDERS SET updated_at = SYSTIMESTAMP WHERE id = 1;
-- Q36. 결제 승인 일자 기록 시도
UPDATE PAYMENTS SET approved_at = SYSTIMESTAMP WHERE status = 'APPROVED';

-- [P17] MERGE INTO Statement (HIGH) : MySQL ON DUPLICATE KEY UPDATE 변환 누락
-- Q37. 회원 정보 Upsert 시도
MERGE INTO MEMBERS m USING (SELECT 100 AS id, 'NEW' AS status FROM DUAL) d ON (m.id = d.id) 
WHEN MATCHED THEN UPDATE SET status = d.status;
-- Q38. 상품 재고 Upsert 시도
MERGE INTO PRODUCTS p USING (SELECT 50 AS id, 999 AS stock FROM DUAL) d ON (p.id = d.id)
WHEN MATCHED THEN UPDATE SET stock = d.stock;

-- [P18] MINUS Set Operator (MEDIUM) : MySQL 미지원 집합 연산자
-- Q39. 한 번도 주문하지 않은 회원 조회
SELECT id FROM MEMBERS MINUS SELECT member_id FROM ORDERS;
-- Q40. 한 번도 팔리지 않은 상품 조회
SELECT id FROM PRODUCTS MINUS SELECT product_id FROM ORDER_ITEMS;
-- Q41. 등록된 상품이 없는 빈 카테고리 조회
SELECT id FROM CATEGORIES MINUS SELECT category_id FROM PRODUCTS;

-- [P19] DUAL Table Dependency (LOW) : 불필요한 DUAL 테이블 의존
-- Q42. 단순 수식 연산 결과 조회
SELECT 100 * 200 FROM DUAL;
-- Q43. 오라클 방식 현재 날짜 단일 조회
SELECT SYSDATE FROM DUAL;

-- [P20] TO_CHAR Date Formatting (MEDIUM) : 날짜 포맷 토큰 차이로 인한 파싱 실패
-- Q44. 가입일을 YYYY-MM-DD 포맷의 문자열로 변환 시도
SELECT TO_CHAR(created_at, 'YYYY-MM-DD') FROM MEMBERS;
-- Q45. 주문 업데이트 일자를 YYYY/MM 포맷으로 조회
SELECT TO_CHAR(updated_at, 'YYYY/MM') FROM ORDERS;
-- Q46. 결제 승인 일자를 MM-DD-YYYY 포맷으로 조회
SELECT TO_CHAR(approved_at, 'MM-DD-YYYY') FROM PAYMENTS;

-- [P21] TO_DATE Parsing (MEDIUM) : 날짜 파싱 함수 차이로 인한 값 오류
-- Q47. 문자열을 오라클 방식으로 날짜 파싱하여 검색 (주문)
SELECT * FROM ORDERS WHERE created_at = TO_DATE('2025/01/01', 'YYYY/MM/DD');
-- Q48. 쿠폰 유효기간을 오라클 방식으로 파싱하여 비교
SELECT * FROM COUPONS WHERE valid_until > TO_DATE('2025-12-31 23:59:59', 'YYYY-MM-DD HH24:MI:SS');

-- [P22] TRUNC Date Function (MEDIUM) : 집계 기준 불일치를 유발하는 날짜 절삭 함수
-- Q49. 일자별 주문 건수 집계 시도
SELECT TRUNC(created_at), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at);
-- Q50. 월별 결제 금액 합계 집계 시도 (TRUNC 사용)
SELECT TRUNC(approved_at, 'MM'), SUM(amount) FROM PAYMENTS GROUP BY TRUNC(approved_at, 'MM');
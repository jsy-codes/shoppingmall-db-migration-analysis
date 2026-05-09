-- 🚨 [P01] Implicit Type Cast (MEDIUM) : 좌변 암묵적 형변환 (인덱스 무력화)
-- Q01. VARCHAR 인덱스 컬럼에 숫자형 데이터 대입
SELECT id, name FROM MEMBERS WHERE phone = 01012345678;
-- Q02. 문자열 결제번호를 숫자 연산 처리하여 풀스캔 유도
SELECT * FROM PAYMENTS WHERE receipt_id + 0 = 20240508001;
-- Q03. 우편번호를 숫자 크기 비교로 조회
SELECT * FROM MEMBERS WHERE zip_code > 48000 AND zip_code < 49000;

-- 🚨 [P02] Function on Indexed Column (HIGH) : 좌변 함수 씌우기 (인덱스 무력화)
-- Q04. 이메일 도메인 검색 시 좌변 함수 + 양방향 와일드카드 결합 (최악의 성능)
SELECT id, email FROM MEMBERS WHERE UPPER(email) LIKE '%@GMAIL.COM%';
-- Q05. 상품 코드의 앞 3자리 검색을 위해 SUBSTR 사용 (Range Scan 불가)
SELECT * FROM PRODUCTS WHERE SUBSTR(product_code, 1, 3) = 'MAC';
-- Q06. 이름에 포함된 공백을 제거하고 검색 (풀스캔)
SELECT * FROM MEMBERS WHERE REPLACE(name, ' ', '') = '이동훈';

-- 🚨 [P03] ROWNUM Pagination (HIGH) : MySQL 미지원 페이징 (실행 실패)
-- Q07. 인덱스를 타지 않는 조건과 결합된 ROWNUM
SELECT * FROM ORDERS WHERE status = 'PENDING' AND ROWNUM <= 100;
-- Q08. ORDER BY 수행 전 ROWNUM이 먼저 잘리는 논리적 오류 유발
SELECT id, total_amount FROM ORDERS WHERE ROWNUM <= 10 ORDER BY total_amount DESC;
-- Q09. 서브쿼리 내에서의 ROWNUM BETWEEN 사용 (페이징 실패)
SELECT * FROM (SELECT id, created_at FROM ORDERS ORDER BY created_at DESC) WHERE ROWNUM BETWEEN 11 AND 20;

-- 🚨 [P04] NVL Function (LOW) : MySQL 미지원 널 처리 (실행 실패 및 인덱스 우회)
-- Q10. 인덱스가 걸려있을 member_id에 NVL을 씌워 100만 건 풀스캔 유도
SELECT * FROM ORDERS WHERE NVL(member_id, 0) = 10050;
-- Q11. 쿠폰 할인 금액 계산 시 좌변 가공
SELECT id FROM COUPONS WHERE NVL(discount_amount, 0) + 1000 > 5000;
-- Q12. 정렬 시 NVL을 사용하여 소트 부하(Filesort) 발생 유도
SELECT * FROM PRODUCTS ORDER BY NVL(updated_at, created_at) DESC;

-- 🚨 [P05] DATE vs DATETIME (MEDIUM) : 날짜 절삭으로 인한 Range Scan 포기
-- Q13. 날짜 인덱스 컬럼을 DATE()로 감싸서 풀스캔 유도
SELECT * FROM ORDERS WHERE DATE(created_at) = '2025-05-08';
-- Q14. 결제 승인일자를 강제 CAST 형변환하여 비교
SELECT * FROM PAYMENTS WHERE CAST(approved_at AS DATE) = '2025-05-01';
-- Q15. 날짜 컬럼에 산술 연산을 수행하여 인덱스 무력화
SELECT * FROM ORDERS WHERE created_at + 1 >= '2025-05-09';

-- 🚨 [P06] VARCHAR2 Usage (LOW) : Oracle 전용 타입 사용
-- Q16. 임시 테이블 생성 시 Oracle VARCHAR2 명시
CREATE TEMPORARY TABLE temp_vip_users (user_id VARCHAR2(50), grade VARCHAR2(10));

-- 🚨 [P07] CHAR Padding (LOW) : 공백 트림으로 인한 인덱스 무력화
-- Q17. CHAR 타입 상태값 비교 시 좌변 TRIM 사용 (풀스캔 유도)
SELECT * FROM ORDERS WHERE TRIM(status) = 'COMPLETE';
-- Q18. 결제 수단 텍스트 강제 결합 후 비교
SELECT * FROM PAYMENTS WHERE payment_method || ' ' = 'CARD ';

-- 🚨 [P08] Function Based Index (HIGH) : Oracle 함수 기반 인덱스 생성 시도
-- Q19. MySQL에서 지원하지 않는 구문으로 이메일 소문자 인덱스 생성
CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email));
-- Q20. 카테고리 이름 대문자 기반 인덱스 생성 시도
CREATE INDEX idx_prod_cat_upper ON PRODUCTS(UPPER(category_name));

-- 🚨 [P09] JOIN Without Index (HIGH) : 카테시안 곱 수준의 치명적 조인 성능 저하
-- Q21. 텍스트 컬럼(주소)을 조인 키로 사용하여 해시/네스티드 루프 조인 유발
SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.address = o.shipping_address;
-- Q22. LIKE를 조인 조건으로 사용하여 인덱스 완전 배제
SELECT p.product_name, c.category_name FROM PRODUCTS p JOIN CATEGORIES c ON p.description LIKE CONCAT('%', c.category_name, '%');
-- Q23. 조인 키 양쪽에 함수를 씌워 Full Table Scan 조인 발생
SELECT o.id, p.id FROM ORDERS o JOIN PAYMENTS p ON DATE(o.created_at) = DATE(p.approved_at) AND o.member_id = p.member_id;

-- 🚨 [P10] Nested Subquery (MEDIUM) : DEPENDENT SUBQUERY 유발로 옵티마이저 한계 도달
-- Q24. IN 절이 3중첩되어 풀스캔을 선택하게 만듦
SELECT * FROM PRODUCTS WHERE id IN (SELECT product_id FROM ORDER_ITEMS WHERE order_id IN (SELECT id FROM ORDERS WHERE member_id IN (SELECT id FROM MEMBERS WHERE status = 'INACTIVE')));
-- Q25. SELECT 절 내부의 상관 서브쿼리 (매 건마다 100만 건 스캔)
SELECT m.name, (SELECT MAX(total_amount) FROM ORDERS o WHERE o.member_id = m.id AND ROWNUM = 1) FROM MEMBERS m;
-- Q26. EXISTS가 중첩된 복잡한 권한/상태 체크 쿼리
SELECT id FROM ORDERS o WHERE EXISTS (SELECT 1 FROM PAYMENTS p WHERE p.order_id = o.id AND EXISTS (SELECT 1 FROM COUPONS c WHERE c.member_id = o.member_id));

-- 🚨 [P11] DECODE Function (MEDIUM) : Oracle 전용 분기 함수
-- Q27. 집계 함수 내에서 DECODE 사용
SELECT DECODE(status, 'COMPLETE', 1, 0) AS is_done, COUNT(*) FROM ORDERS GROUP BY DECODE(status, 'COMPLETE', 1, 0);
-- Q28. WHERE 절 조건에 DECODE 적용 (인덱스 우회)
SELECT * FROM PAYMENTS WHERE DECODE(payment_method, 'CARD', 1, 0) = 1;

-- 🚨 [P12] CONNECT BY Hierarchy (HIGH) : Oracle 재귀 쿼리
-- Q29. 카테고리 무한 루프 위험이 있는 계층 조회
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id;
-- Q30. 레벨 제한이 걸린 추천인 다단계 조회
SELECT * FROM MEMBERS CONNECT BY PRIOR referrer_id = id AND LEVEL <= 3;

-- 🚨 [P13] START WITH Hierarchy (MEDIUM) : 계층 시작 조건
-- Q31. 최상위 카테고리부터 시작하는 계층 조회
SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id;

-- 🚨 [P14] Oracle Outer Join (+) (HIGH) : 레거시 조인 문법 에러
-- Q32. WHERE 절에서의 (+) 1:N 아우터 조인
SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+);
-- Q33. 다중 테이블 아우터 조인 및 추가 조건 결합
SELECT o.id, p.id FROM ORDERS o, PAYMENTS p WHERE o.id = p.order_id (+) AND p.status (+) = 'COMPLETED';
-- Q34. 상품과 카테고리의 텍스트 기반 아우터 조인
SELECT c.category_name, p.product_name FROM CATEGORIES c, PRODUCTS p WHERE c.id (+) = p.category_id AND p.price > 10000;

-- 🚨 [P15] SYSDATE Usage (LOW) : MySQL NOW() 와의 호환성
-- Q35. 날짜 연산에 SYSDATE 직접 사용
SELECT * FROM COUPONS WHERE valid_until >= SYSDATE - 7;
-- Q36. SYSDATE를 문자열로 포맷팅하여 비교
SELECT * FROM ORDERS WHERE TO_CHAR(SYSDATE, 'YYYYMMDD') = TO_CHAR(created_at, 'YYYYMMDD');

-- 🚨 [P16] SYSTIMESTAMP Usage (MEDIUM) : 정밀도 문제
-- Q37. 밀리초 업데이트 시도
UPDATE PAYMENTS SET approved_at = SYSTIMESTAMP WHERE status = 'PENDING';
-- Q38. 타임스탬프와 INTERVAL 연산 혼용
SELECT * FROM ORDERS WHERE created_at > SYSTIMESTAMP - INTERVAL '1' DAY;

-- 🚨 [P17] MERGE INTO Statement (HIGH) : Oracle 전용 UPSERT
-- Q39. 재고 차감 비즈니스 로직 MERGE INTO (MATCHED)
MERGE INTO PRODUCTS p USING (SELECT 50 AS id, 10 AS qty FROM DUAL) d ON (p.id = d.id) WHEN MATCHED THEN UPDATE SET stock = stock - d.qty;
-- Q40. 회원 상태 업데이트 MERGE INTO (NOT MATCHED)
MERGE INTO MEMBERS m USING (SELECT 10050 AS id, 'ACTIVE' AS status FROM DUAL) d ON (m.id = d.id) WHEN NOT MATCHED THEN INSERT (id, status) VALUES (d.id, d.status);

-- 🚨 [P18] MINUS Set Operator (MEDIUM) : 차집합 에러
-- Q41. 대량의 데이터 셋에서 MINUS 연산 (주문 이력이 없는 회원)
SELECT id FROM MEMBERS MINUS SELECT member_id FROM ORDERS WHERE created_at > '2024-01-01';
-- Q42. 팔리지 않은 상품을 MINUS로 도출
SELECT id FROM PRODUCTS MINUS SELECT product_id FROM ORDER_ITEMS;

-- 🚨 [P19] DUAL Table Dependency (LOW) : 불필요한 시스템 테이블 호출
-- Q43. 시퀀스 넥스트발 추출 시도 (MySQL AUTO_INCREMENT와 충돌)
SELECT member_seq.NEXTVAL FROM DUAL;

-- 🚨 [P20] TO_CHAR Date Formatting (MEDIUM) : 포맷팅 에러 및 인덱스 우회
-- Q44. 일별 매출 집계를 위해 조건절과 GROUP BY 모두에 TO_CHAR 사용 (100만건 풀스캔)
SELECT TO_CHAR(created_at, 'YYYYMMDD'), SUM(total_amount) FROM ORDERS WHERE TO_CHAR(created_at, 'YYYYMMDD') LIKE '202505%' GROUP BY TO_CHAR(created_at, 'YYYYMMDD');
-- Q45. 시분초 포맷으로 정렬
SELECT * FROM PAYMENTS ORDER BY TO_CHAR(approved_at, 'YYYY-MM-DD HH24:MI:SS') DESC;
-- Q46. 숫자 컬럼을 문자 포맷으로 변환하여 비교
SELECT * FROM PRODUCTS WHERE TO_CHAR(price, '999,999') = '10,000';

-- 🚨 [P21] TO_DATE Parsing (MEDIUM) : 파싱 함수 차이
-- Q47. 시간 포맷까지 명시한 TO_DATE 검색
SELECT * FROM PAYMENTS WHERE approved_at >= TO_DATE('2025-05-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS');
-- Q48. BETWEEN 구문 내에서 TO_DATE 연속 사용
SELECT * FROM ORDERS WHERE created_at BETWEEN TO_DATE('20250101', 'YYYYMMDD') AND TO_DATE('20251231', 'YYYYMMDD');

-- 🚨 [P22] TRUNC Date Function (MEDIUM) : 날짜 절삭 인덱스 무력화
-- Q49. 월별 집계를 위한 TRUNC 절삭 (풀스캔 유발)
SELECT TRUNC(created_at, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at, 'MM');
-- Q50. 특정 일자에 발생한 로그 조회 (인덱스 우회)
SELECT * FROM PAYMENTS WHERE TRUNC(approved_at) = TRUNC(SYSDATE - 1);
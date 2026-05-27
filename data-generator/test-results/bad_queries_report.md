# 시나리오 C — bad_queries.sql MySQL 에러 검증 리포트
> 생성: 2026-05-26 23:38:39
> 대상: bucketstore_dummy (MySQL 8.0)

## 요약
- 전체: 50건
- 성공(OK/OK_SLOW/OK_WRONG): 13건
- 에러(ERROR): 37건
- **에러율: 74.0%**

## 실패 유형별 분류

| 실패 유형 | 건수 | 의미 |
|-----------|------|------|
| SYNTAX_ERROR | 15 | MySQL이 아예 인식 못 하는 Oracle 전용 문법 |
| FUNCTION_NOT_FOUND | 13 | MySQL에 없는 Oracle 전용 함수 |
| UNKNOWN_ERROR | 9 | 분류되지 않은 기타 오류 |

## 전체 실행 결과

| 번호 | 패턴 | 결과 | 실패 유형 | 수정 방향 | 설명 |
|------|------|------|-----------|-----------|------|
| Q01 | P01 | ✅ OK | - | 정상 실행 | MEMBERS 테이블의 문자열 id를 숫자로 조회 |
| Q02 | P01 | ✅ OK | - | 정상 실행 | ORDERS 테이블의 문자열 member_id를 숫자로 |
| Q03 | P02 | ✅ OK | - | 정상 실행 | PRODUCTS 테이블의 category_id를 문자열 |
| Q04 | P02 | ✅ OK_SLOW | - | 인덱스 컬럼에 함수 적용 — 성능 저하 (P02) | 회원 이름 검색 시 UPPER 함수 사용 |
| Q05 | P02 | ✅ OK_SLOW | - | 인덱스 컬럼에 함수 적용 — 성능 저하 (P02) | 이메일 검색 시 LOWER 함수 사용 |
| Q06 | P03 | ✅ OK_SLOW | - | 인덱스 컬럼에 함수 적용 — 성능 저하 (P02) | 상품명 검색 시 SUBSTR(문자열 자르기) 함수 사용 |
| Q07 | P03 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | 최근 주문 10건 조회 시도 |
| Q08 | P04 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | 금액이 높은 결제 내역 5건 조회 시도 |
| Q09 | P04 | ❌ ERROR | FUNCTION_NOT_FOUND | NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환 | 쿠폰 할인액이 null일 경우 0으로 치환 시도 |
| Q10 | P05 | ❌ ERROR | FUNCTION_NOT_FOUND | NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환 | 상품 설명이 없을 경우 기본 텍스트 치환 시도 |
| Q11 | P05 | ✅ OK_SLOW | - | CAST AS DATE 실행됨 — 시간 정보 손실 가능 (P05) | 오라클 방식의 DATE 타입 캐스팅 (주문일 기준) |
| Q12 | P06 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 결제 완료일 기준 DATE 타입 비교 |
| Q13 | P06 | ❌ ERROR | SYNTAX_ERROR | VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요 | 임시 테이블 생성 시 VARCHAR2 명시 |
| Q14 | P07 | ❌ ERROR | SYNTAX_ERROR | VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요 | 형변환 시 VARCHAR2 사용 |
| Q15 | P07 | ✅ OK_SLOW | - | CAST 형변환 실행됨 — 인덱스 우회 가능 (P07) | CHAR 타입 상태값에 대한 후행 공백 미처리 비교 ( |
| Q16 | P08 | ✅ OK_SLOW | - | CAST 형변환 실행됨 — 인덱스 우회 가능 (P07) | CHAR 타입 결제수단 공백 비교 |
| Q17 | P08 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 회원 이메일 소문자 변환 인덱스 생성 |
| Q18 | P09 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 상품 카테고리 대문자 변환 인덱스 생성 |
| Q19 | P09 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 회원 주소와 배송지가 같은 데이터 조인 (텍스트 컬럼  |
| Q20 | P09 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 상품 설명과 주문 비고란이 일치하는 데이터 조인 |
| Q21 | P10 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 결제 영수증 번호와 주문 번호 텍스트 매칭 조인 |
| Q22 | P10 | ✅ OK | - | 정상 실행 | 특정 결제 금액 이상의 주문을 한 회원 조회 (3중첩) |
| Q23 | P10 | ✅ OK | - | 정상 실행 | 특정 카테고리의 상품이 포함된 주문 건 조회 (3중첩) |
| Q24 | P11 | ✅ OK | - | 정상 실행 | 미사용 쿠폰을 가진 회원의 주문 조회 (3중첩) |
| Q25 | P11 | ❌ ERROR | FUNCTION_NOT_FOUND | DECODE 함수 미지원 — CASE WHEN으로 변환 | 주문 상태값 한글 변환 시도 |
| Q26 | P12 | ❌ ERROR | FUNCTION_NOT_FOUND | DECODE 함수 미지원 — CASE WHEN으로 변환 | 결제 수단 한글 변환 시도 |
| Q27 | P12 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 카테고리 계층 구조 조회 |
| Q28 | P13 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 회원 추천인(다단계) 계층 조회 |
| Q29 | P13 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 카테고리 최상위 노드 지정 조회 |
| Q30 | P14 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 특정 회원을 시작점으로 하는 하위 추천인 조회 |
| Q31 | P14 | ❌ ERROR | SYNTAX_ERROR | Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 | 주문이 없는 회원까지 모두 조회 (아우터 조인) |
| Q32 | P15 | ❌ ERROR | SYNTAX_ERROR | Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 | 결제 내역이 없는 주문까지 모두 조회 |
| Q33 | P15 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 어제부터 오늘까지 들어온 주문 조회 |
| Q34 | P16 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 오늘 만료되는 쿠폰 조회 |
| Q35 | P16 | ❌ ERROR | FUNCTION_NOT_FOUND | SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIM | 주문 수정 일자에 오라클 타임스탬프 기록 시도 |
| Q36 | P17 | ❌ ERROR | FUNCTION_NOT_FOUND | SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIM | 결제 승인 일자 기록 시도 |
| Q37 | P17 | ❌ ERROR | SYNTAX_ERROR | MERGE INTO 미지원 — INSERT ON DUPLICATE KEY | 회원 정보 Upsert 시도 |
| Q38 | P18 | ❌ ERROR | SYNTAX_ERROR | MERGE INTO 미지원 — INSERT ON DUPLICATE KEY | 상품 재고 Upsert 시도 |
| Q39 | P18 | ❌ ERROR | SYNTAX_ERROR | MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인 | 한 번도 주문하지 않은 회원 조회 |
| Q40 | P18 | ❌ ERROR | SYNTAX_ERROR | MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인 | 한 번도 팔리지 않은 상품 조회 |
| Q41 | P19 | ❌ ERROR | SYNTAX_ERROR | MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인 | 등록된 상품이 없는 빈 카테고리 조회 |
| Q42 | P19 | ✅ OK_COMPAT | - | DUAL은 MySQL에서 실행 가능 (P19) | 단순 수식 연산 결과 조회 |
| Q43 | P20 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | 오라클 방식 현재 날짜 단일 조회 |
| Q44 | P20 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | 가입일을 YYYY-MM-DD 포맷의 문자열로 변환 시도 |
| Q45 | P20 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | 주문 업데이트 일자를 YYYY/MM 포맷으로 조회 |
| Q46 | P21 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | 결제 승인 일자를 MM-DD-YYYY 포맷으로 조회 |
| Q47 | P21 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_DATE 함수 미지원 — STR_TO_DATE로 변환 | 문자열을 오라클 방식으로 날짜 파싱하여 검색 (주문) |
| Q48 | P22 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_DATE 함수 미지원 — STR_TO_DATE로 변환 | 쿠폰 유효기간을 오라클 방식으로 파싱하여 비교 |
| Q49 | P22 | ❌ ERROR | FUNCTION_NOT_FOUND | TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변 | 일자별 주문 건수 집계 시도 |
| Q50 | P22 | ❌ ERROR | FUNCTION_NOT_FOUND | TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변 | 월별 결제 금액 합계 집계 시도 (TRUNC 사용) |

## 에러 항목 상세 — C(이현종) Claude 프롬프트 반영용

아래 항목들은 Claude API 프롬프트의 `[이관 규칙 가이드라인]`에
실제 에러 메시지와 수정 방향을 보강해야 합니다.

### Q07 — P03 (SYNTAX_ERROR)
- **설명**: 최근 주문 10건 조회 시도
- **에러**: `Unknown column 'ROWNUM' in 'where clause'`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT * FROM ORDERS WHERE ROWNUM <= 10 ORDER BY created_at DESC
```

### Q08 — P04 (SYNTAX_ERROR)
- **설명**: 금액이 높은 결제 내역 5건 조회 시도
- **에러**: `Unknown column 'ROWNUM' in 'where clause'`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT * FROM PAYMENTS WHERE ROWNUM <= 5 ORDER BY amount DESC
```

### Q09 — P04 (FUNCTION_NOT_FOUND)
- **설명**: 쿠폰 할인액이 null일 경우 0으로 치환 시도
- **에러**: `FUNCTION bucketstore_dummy.NVL does not exist`
- **수정 방향**: NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환
```sql
SELECT id, NVL(discount_amount, 0) FROM COUPONS
```

### Q10 — P05 (FUNCTION_NOT_FOUND)
- **설명**: 상품 설명이 없을 경우 기본 텍스트 치환 시도
- **에러**: `FUNCTION bucketstore_dummy.NVL does not exist`
- **수정 방향**: NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환
```sql
SELECT product_name, NVL(description, '설명 없음') FROM PRODUCTS
```

### Q12 — P06 (UNKNOWN_ERROR)
- **설명**: 결제 완료일 기준 DATE 타입 비교
- **에러**: `Unknown column 'approved_at' in 'where clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT id FROM PAYMENTS WHERE approved_at = CAST('2025-02-15' AS DATE)
```

### Q13 — P06 (SYNTAX_ERROR)
- **설명**: 임시 테이블 생성 시 VARCHAR2 명시
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요
```sql
CREATE TEMPORARY TABLE temp_users (user_id VARCHAR2(50))
```

### Q14 — P07 (SYNTAX_ERROR)
- **설명**: 형변환 시 VARCHAR2 사용
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요
```sql
SELECT CAST(name AS VARCHAR2(100)) FROM MEMBERS
```

### Q17 — P08 (UNKNOWN_ERROR)
- **설명**: 회원 이메일 소문자 변환 인덱스 생성
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email))
```

### Q18 — P09 (UNKNOWN_ERROR)
- **설명**: 상품 카테고리 대문자 변환 인덱스 생성
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
CREATE INDEX idx_products_cat_upper ON PRODUCTS(UPPER(category_name))
```

### Q19 — P09 (UNKNOWN_ERROR)
- **설명**: 회원 주소와 배송지가 같은 데이터 조인 (텍스트 컬럼 조인 부하)
- **에러**: `Unknown column 'm.address' in 'on clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.address = o.shipping_address
```

### Q20 — P09 (UNKNOWN_ERROR)
- **설명**: 상품 설명과 주문 비고란이 일치하는 데이터 조인
- **에러**: `Unknown column 'p.description' in 'on clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT p.product_name FROM PRODUCTS p JOIN ORDER_ITEMS oi ON p.description = oi.remarks
```

### Q21 — P10 (UNKNOWN_ERROR)
- **설명**: 결제 영수증 번호와 주문 번호 텍스트 매칭 조인
- **에러**: `Unknown column 'py.receipt_id' in 'on clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT py.id, o.id FROM PAYMENTS py JOIN ORDERS o ON py.receipt_id = o.order_number
```

### Q25 — P11 (FUNCTION_NOT_FOUND)
- **설명**: 주문 상태값 한글 변환 시도
- **에러**: `FUNCTION bucketstore_dummy.DECODE does not exist`
- **수정 방향**: DECODE 함수 미지원 — CASE WHEN으로 변환
```sql
SELECT id, DECODE(status, 'PENDING', '대기', 'COMPLETE', '완료', '기타') FROM ORDERS
```

### Q26 — P12 (FUNCTION_NOT_FOUND)
- **설명**: 결제 수단 한글 변환 시도
- **에러**: `FUNCTION bucketstore_dummy.DECODE does not exist`
- **수정 방향**: DECODE 함수 미지원 — CASE WHEN으로 변환
```sql
SELECT id, DECODE(payment_method, 'CARD', '신용카드', 'CASH', '현금', '기타') FROM PAYMENTS
```

### Q27 — P12 (SYNTAX_ERROR)
- **설명**: 카테고리 계층 구조 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id
```

### Q28 — P13 (SYNTAX_ERROR)
- **설명**: 회원 추천인(다단계) 계층 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM MEMBERS CONNECT BY PRIOR id = referrer_id
```

### Q29 — P13 (SYNTAX_ERROR)
- **설명**: 카테고리 최상위 노드 지정 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id
```

### Q30 — P14 (SYNTAX_ERROR)
- **설명**: 특정 회원을 시작점으로 하는 하위 추천인 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM MEMBERS START WITH id = 100 CONNECT BY PRIOR id = referrer_id
```

### Q31 — P14 (SYNTAX_ERROR)
- **설명**: 주문이 없는 회원까지 모두 조회 (아우터 조인)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환
```sql
SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+)
```

### Q32 — P15 (SYNTAX_ERROR)
- **설명**: 결제 내역이 없는 주문까지 모두 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환
```sql
SELECT o.id, p.amount FROM ORDERS o, PAYMENTS p WHERE o.id = p.order_id (+)
```

### Q33 — P15 (UNKNOWN_ERROR)
- **설명**: 어제부터 오늘까지 들어온 주문 조회
- **에러**: `Unknown column 'SYSDATE' in 'where clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT * FROM ORDERS WHERE created_at >= SYSDATE - 1
```

### Q34 — P16 (UNKNOWN_ERROR)
- **설명**: 오늘 만료되는 쿠폰 조회
- **에러**: `Unknown column 'SYSDATE' in 'where clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT * FROM COUPONS WHERE valid_until = SYSDATE
```

### Q35 — P16 (FUNCTION_NOT_FOUND)
- **설명**: 주문 수정 일자에 오라클 타임스탬프 기록 시도
- **에러**: `Unknown column 'updated_at' in 'field list'`
- **수정 방향**: SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIMESTAMP(6)으로 변환
```sql
UPDATE ORDERS SET updated_at = SYSTIMESTAMP WHERE id = 1
```

### Q36 — P17 (FUNCTION_NOT_FOUND)
- **설명**: 결제 승인 일자 기록 시도
- **에러**: `Unknown column 'status' in 'where clause'`
- **수정 방향**: SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIMESTAMP(6)으로 변환
```sql
UPDATE PAYMENTS SET approved_at = SYSTIMESTAMP WHERE status = 'APPROVED'
```

### Q37 — P17 (SYNTAX_ERROR)
- **설명**: 회원 정보 Upsert 시도
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MERGE INTO 미지원 — INSERT ON DUPLICATE KEY UPDATE로 변환
```sql
MERGE INTO MEMBERS m USING (SELECT 100 AS id, 'NEW' AS status FROM DUAL) d ON (m.id = d.id) WHEN MATCHED THEN UPDATE SET status = d.status
```

### Q38 — P18 (SYNTAX_ERROR)
- **설명**: 상품 재고 Upsert 시도
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MERGE INTO 미지원 — INSERT ON DUPLICATE KEY UPDATE로 변환
```sql
MERGE INTO PRODUCTS p USING (SELECT 50 AS id, 999 AS stock FROM DUAL) d ON (p.id = d.id) WHEN MATCHED THEN UPDATE SET stock = d.stock
```

### Q39 — P18 (SYNTAX_ERROR)
- **설명**: 한 번도 주문하지 않은 회원 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환
```sql
SELECT id FROM MEMBERS MINUS SELECT member_id FROM ORDERS
```

### Q40 — P18 (SYNTAX_ERROR)
- **설명**: 한 번도 팔리지 않은 상품 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환
```sql
SELECT id FROM PRODUCTS MINUS SELECT product_id FROM ORDER_ITEMS
```

### Q41 — P19 (SYNTAX_ERROR)
- **설명**: 등록된 상품이 없는 빈 카테고리 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환
```sql
SELECT id FROM CATEGORIES MINUS SELECT category_id FROM PRODUCTS
```

### Q43 — P20 (UNKNOWN_ERROR)
- **설명**: 오라클 방식 현재 날짜 단일 조회
- **에러**: `Unknown column 'SYSDATE' in 'field list'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT SYSDATE FROM DUAL
```

### Q44 — P20 (FUNCTION_NOT_FOUND)
- **설명**: 가입일을 YYYY-MM-DD 포맷의 문자열로 변환 시도
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT TO_CHAR(created_at, 'YYYY-MM-DD') FROM MEMBERS
```

### Q45 — P20 (FUNCTION_NOT_FOUND)
- **설명**: 주문 업데이트 일자를 YYYY/MM 포맷으로 조회
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT TO_CHAR(updated_at, 'YYYY/MM') FROM ORDERS
```

### Q46 — P21 (FUNCTION_NOT_FOUND)
- **설명**: 결제 승인 일자를 MM-DD-YYYY 포맷으로 조회
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT TO_CHAR(approved_at, 'MM-DD-YYYY') FROM PAYMENTS
```

### Q47 — P21 (FUNCTION_NOT_FOUND)
- **설명**: 문자열을 오라클 방식으로 날짜 파싱하여 검색 (주문)
- **에러**: `FUNCTION bucketstore_dummy.TO_DATE does not exist`
- **수정 방향**: TO_DATE 함수 미지원 — STR_TO_DATE로 변환
```sql
SELECT * FROM ORDERS WHERE created_at = TO_DATE('2025/01/01', 'YYYY/MM/DD')
```

### Q48 — P22 (FUNCTION_NOT_FOUND)
- **설명**: 쿠폰 유효기간을 오라클 방식으로 파싱하여 비교
- **에러**: `FUNCTION bucketstore_dummy.TO_DATE does not exist`
- **수정 방향**: TO_DATE 함수 미지원 — STR_TO_DATE로 변환
```sql
SELECT * FROM COUPONS WHERE valid_until > TO_DATE('2025-12-31 23:59:59', 'YYYY-MM-DD HH24:MI:SS')
```

### Q49 — P22 (FUNCTION_NOT_FOUND)
- **설명**: 일자별 주문 건수 집계 시도
- **에러**: `FUNCTION bucketstore_dummy.TRUNC does not exist`
- **수정 방향**: TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변환
```sql
SELECT TRUNC(created_at), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at)
```

### Q50 — P22 (FUNCTION_NOT_FOUND)
- **설명**: 월별 결제 금액 합계 집계 시도 (TRUNC 사용)
- **에러**: `FUNCTION bucketstore_dummy.TRUNC does not exist`
- **수정 방향**: TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변환
```sql
SELECT TRUNC(approved_at, 'MM'), SUM(amount) FROM PAYMENTS GROUP BY TRUNC(approved_at, 'MM')
```

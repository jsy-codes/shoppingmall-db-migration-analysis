# 시나리오 C — bad_queries.sql MySQL 에러 검증 리포트
> 생성: 2026-06-01 19:19:37
> 대상: bucketstore_dummy (MySQL 8.0)

## 요약
- 전체: 58건
- 성공(OK/OK_SLOW/OK_WRONG): 17건
- 에러(ERROR): 41건
- **에러율: 70.7%**

## 실패 유형별 분류

| 실패 유형 | 건수 | 의미 |
|-----------|------|------|
| SYNTAX_ERROR | 20 | MySQL이 아예 인식 못 하는 Oracle 전용 문법 |
| FUNCTION_NOT_FOUND | 18 | MySQL에 없는 Oracle 전용 함수 |
| UNKNOWN_ERROR | 3 | 분류되지 않은 기타 오류 |

## 전체 실행 결과

| 번호 | 패턴 | 결과 | 실패 유형 | 수정 방향 | 설명 |
|------|------|------|-----------|-----------|------|
| Q01 | P01 | ✅ OK | - | 정상 실행 | ORDERS.member_id(VARCHAR FK)에  |
| Q02 | P01 | ✅ OK | - | 정상 실행 | PAYMENTS.id에 산술 연산(+0) → 인덱스 완 |
| Q03 | P02 | ✅ OK | - | 정상 실행 | MEMBERS.id(VARCHAR PK)를 숫자 범위  |
| Q04 | P02 | ✅ OK_SLOW | - | 인덱스 컬럼에 함수 적용 — 성능 저하 (P02) | MEMBERS.email에 UPPER + 양방향 와일드 |
| Q05 | P02 | ✅ OK_SLOW | - | 인덱스 컬럼에 함수 적용 — 성능 저하 (P02) | PRODUCTS.product_name 앞 3자리 SU |
| Q06 | P05 | ✅ OK | - | 정상 실행 | MEMBERS.name 공백 제거 후 검색 → 풀스캔 |
| Q13 | P05 | ✅ OK | - | 정상 실행 | ORDERS.created_at을 DATE()로 감싸서 |
| Q14 | P05 | ✅ OK_SLOW | - | CAST AS DATE 실행됨 — 시간 정보 손실 가능 (P05) | PAYMENTS.payment_date를 CAST로 형 |
| Q15 | P07 | ✅ OK | - | 정상 실행 | ORDERS.created_at에 산술 연산 → 인덱스 |
| Q17 | P07 | ✅ OK | - | 정상 실행 | ORDERS.status에 TRIM 적용 → 풀스캔 |
| Q18 | P08 | ✅ OK | - | 정상 실행 | PAYMENTS.payment_method Oracle |
| Q19 | P08 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | MEMBERS.email 소문자 함수 기반 인덱스 생성 |
| Q20 | P03 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | PRODUCTS.product_name 대문자 함수 기 |
| Q07 | P03 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | 조건절과 결합된 ROWNUM |
| Q08 | P03 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | ORDER BY 수행 전 ROWNUM이 먼저 적용되는  |
| Q09 | P04 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | 서브쿼리 내 ROWNUM BETWEEN 페이징 실패 |
| Q10 | P04 | ❌ ERROR | FUNCTION_NOT_FOUND | NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환 | ORDERS.member_id에 NVL → 인덱스 무력 |
| Q11 | P04 | ❌ ERROR | FUNCTION_NOT_FOUND | NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환 | COUPONS.discount_amount에 NVL 후 |
| Q12 | P11 | ❌ ERROR | FUNCTION_NOT_FOUND | NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환 | PRODUCTS 정렬 시 NVL → Filesort 부 |
| Q27 | P11 | ❌ ERROR | FUNCTION_NOT_FOUND | DECODE 함수 미지원 — CASE WHEN으로 변환 | 집계 + GROUP BY 모두 DECODE 사용 |
| Q28 | P24 | ❌ ERROR | FUNCTION_NOT_FOUND | DECODE 함수 미지원 — CASE WHEN으로 변환 | WHERE절 DECODE → 인덱스 우회 |
| Q52 | P29 | ❌ ERROR | FUNCTION_NOT_FOUND | Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필 | Oracle LISTAGG 집계 함수 사용 |
| Q57 | P12 | ❌ ERROR | FUNCTION_NOT_FOUND | Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필 | WM_CONCAT 문자열 집계 |
| Q29 | P12 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 카테고리 무한 루프 위험 계층 조회 |
| Q30 | P13 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 레벨 제한 계층 조회 |
| Q31 | P26 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | 최상위 카테고리부터 시작하는 계층 조회 (P12+P13 |
| Q54 | P09 | ❌ ERROR | SYNTAX_ERROR | 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요 | NOCYCLE 순환 방지 계층 조회 (P12+P26 복 |
| Q21 | P09 | ✅ OK | - | 정상 실행 | MEMBERS.status ↔ ORDERS.status |
| Q22 | P09 | ✅ OK | - | 정상 실행 | PRODUCTS.product_name LIKE로 CA |
| Q23 | P14 | ✅ OK | - | 정상 실행 | DATE() 함수 씌워 조인 (P05+P09 복합) |
| Q32 | P14 | ❌ ERROR | SYNTAX_ERROR | Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 | WHERE절 (+) 1:N 아우터 조인 |
| Q33 | P14 | ❌ ERROR | SYNTAX_ERROR | Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 | 다중 테이블 아우터 조인 + 추가 조건 |
| Q34 | P10 | ❌ ERROR | SYNTAX_ERROR | Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 | 카테고리-상품 아우터 조인 + 가격 조건 |
| Q24 | P10 | ✅ OK | - | 정상 실행 | 3중 중첩 IN 절 → 풀스캔 유발 |
| Q25 | P10 | ❌ ERROR | SYNTAX_ERROR | ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요 | SELECT절 상관 서브쿼리 + ROWNUM (P03+ |
| Q26 | P15 | ✅ OK | - | 정상 실행 | 중첩 EXISTS → 복잡한 상태 체크로 옵티마이저 포 |
| Q35 | P15 | ❌ ERROR | UNKNOWN_ERROR | 에러 원인 수동 확인 필요 | COUPONS.valid_until에 SYSDATE 날 |
| Q36 | P16 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | SYSDATE + TO_CHAR 혼용 (P15+P20  |
| Q37 | P16 | ❌ ERROR | FUNCTION_NOT_FOUND | SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIM | PAYMENTS.payment_date에 SYSTIME |
| Q38 | P20 | ❌ ERROR | FUNCTION_NOT_FOUND | SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIM | ORDERS.created_at과 INTERVAL 연산 |
| Q44 | P20 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | 일별 매출 집계 — 조건절+GROUP BY 모두 TO_ |
| Q45 | P20 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | PAYMENTS.payment_date 시분초 포맷 정 |
| Q46 | P21 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환 | PRODUCTS.price 숫자 포맷으로 변환해 비교 |
| Q47 | P21 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_DATE 함수 미지원 — STR_TO_DATE로 변환 | PAYMENTS.payment_date에 TO_DATE |
| Q48 | P22 | ❌ ERROR | FUNCTION_NOT_FOUND | TO_DATE 함수 미지원 — STR_TO_DATE로 변환 | ORDERS.created_at BETWEEN TO_D |
| Q49 | P22 | ❌ ERROR | FUNCTION_NOT_FOUND | TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변 | ORDERS 월별 집계 TRUNC → 풀스캔 |
| Q50 | P06 | ❌ ERROR | FUNCTION_NOT_FOUND | TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변 | PAYMENTS.payment_date TRUNC +  |
| Q16 | P25 | ❌ ERROR | SYNTAX_ERROR | VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요 | 임시 테이블 생성 시 VARCHAR2 사용 |
| Q53 | P30 | ❌ ERROR | SYNTAX_ERROR | Oracle NUMBER 타입 미지원 — INT/DECIMAL로 변환 필 | Oracle NUMBER 타입으로 테이블 생성 |
| Q58 | P17 | ❌ ERROR | SYNTAX_ERROR | VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요 | Oracle NVARCHAR2/NCHAR 타입 선언 |
| Q39 | P17 | ❌ ERROR | SYNTAX_ERROR | MERGE INTO 미지원 — INSERT ON DUPLICATE KEY | 재고 차감 MERGE INTO (WHEN MATCHED |
| Q40 | P18 | ❌ ERROR | SYNTAX_ERROR | MERGE INTO 미지원 — INSERT ON DUPLICATE KEY | 회원 상태 MERGE INTO (WHEN NOT MAT |
| Q41 | P18 | ❌ ERROR | SYNTAX_ERROR | MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인 | 주문 이력 없는 회원 도출 (MINUS) |
| Q42 | P19 | ❌ ERROR | SYNTAX_ERROR | MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인 | 팔리지 않은 상품 도출 (MINUS) |
| Q43 | P23 | ❌ ERROR | SYNTAX_ERROR | Oracle SEQUENCE 문법 미지원 — AUTO_INCREMENT로 | 시퀀스 NEXTVAL FROM DUAL (AUTO_IN |
| Q51 | P27 | ❌ ERROR | SYNTAX_ERROR | Oracle SEQUENCE 문법 미지원 — AUTO_INCREMENT로 | Oracle SEQUENCE.NEXTVAL INSERT |
| Q55 | P28 | ✅ OK_WRONG | - | REGEXP_LIKE 실행되나 플래그 동작이 Oracle과 다름 — RE | REGEXP_LIKE 대소문자 무시 플래그 사용 |
| Q56 | P28 | ❌ ERROR | FUNCTION_NOT_FOUND | Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필 | Oracle PIVOT으로 연도별 매출 집계 |

## 에러 항목 상세 — C(이현종) Claude 프롬프트 반영용

아래 항목들은 Claude API 프롬프트의 `[이관 규칙 가이드라인]`에
실제 에러 메시지와 수정 방향을 보강해야 합니다.

### Q19 — P08 (UNKNOWN_ERROR)
- **설명**: MEMBERS.email 소문자 함수 기반 인덱스 생성 시도
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email))
```

### Q20 — P03 (UNKNOWN_ERROR)
- **설명**: PRODUCTS.product_name 대문자 함수 기반 인덱스 생성 시도
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
CREATE INDEX idx_prod_name_upper ON PRODUCTS(UPPER(product_name))
```

### Q07 — P03 (SYNTAX_ERROR)
- **설명**: 조건절과 결합된 ROWNUM
- **에러**: `Unknown column 'ROWNUM' in 'where clause'`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT * FROM ORDERS WHERE status = 'PENDING' AND ROWNUM <= 100
```

### Q08 — P03 (SYNTAX_ERROR)
- **설명**: ORDER BY 수행 전 ROWNUM이 먼저 적용되는 논리적 오류
- **에러**: `Unknown column 'ROWNUM' in 'where clause'`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT id, total_amount FROM ORDERS WHERE ROWNUM <= 10 ORDER BY total_amount DESC
```

### Q09 — P04 (SYNTAX_ERROR)
- **설명**: 서브쿼리 내 ROWNUM BETWEEN 페이징 실패
- **에러**: `Every derived table must have its own alias`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT * FROM (SELECT id, created_at FROM ORDERS ORDER BY created_at DESC) WHERE ROWNUM BETWEEN 11 AND 20
```

### Q10 — P04 (FUNCTION_NOT_FOUND)
- **설명**: ORDERS.member_id에 NVL → 인덱스 무력화 + 풀스캔
- **에러**: `FUNCTION bucketstore_dummy.NVL does not exist`
- **수정 방향**: NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환
```sql
SELECT * FROM ORDERS WHERE NVL(member_id, '0') = '10050'
```

### Q11 — P04 (FUNCTION_NOT_FOUND)
- **설명**: COUPONS.discount_amount에 NVL 후 산술 연산
- **에러**: `FUNCTION bucketstore_dummy.NVL does not exist`
- **수정 방향**: NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환
```sql
SELECT id FROM COUPONS WHERE NVL(discount_amount, 0) + 1000 > 5000
```

### Q12 — P11 (FUNCTION_NOT_FOUND)
- **설명**: PRODUCTS 정렬 시 NVL → Filesort 부하
- **에러**: `FUNCTION bucketstore_dummy.NVL does not exist`
- **수정 방향**: NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환
```sql
SELECT * FROM PRODUCTS ORDER BY NVL(stock_quantity, 0) DESC
```

### Q27 — P11 (FUNCTION_NOT_FOUND)
- **설명**: 집계 + GROUP BY 모두 DECODE 사용
- **에러**: `FUNCTION bucketstore_dummy.DECODE does not exist`
- **수정 방향**: DECODE 함수 미지원 — CASE WHEN으로 변환
```sql
SELECT DECODE(status, 'COMPLETE', 1, 0) AS is_done, COUNT(*) FROM ORDERS GROUP BY DECODE(status, 'COMPLETE', 1, 0)
```

### Q28 — P24 (FUNCTION_NOT_FOUND)
- **설명**: WHERE절 DECODE → 인덱스 우회
- **에러**: `FUNCTION bucketstore_dummy.DECODE does not exist`
- **수정 방향**: DECODE 함수 미지원 — CASE WHEN으로 변환
```sql
SELECT * FROM PAYMENTS WHERE DECODE(payment_method, 'CARD', 1, 0) = 1
```

### Q52 — P29 (FUNCTION_NOT_FOUND)
- **설명**: Oracle LISTAGG 집계 함수 사용
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필요
```sql
SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM CATEGORIES
```

### Q57 — P12 (FUNCTION_NOT_FOUND)
- **설명**: WM_CONCAT 문자열 집계
- **에러**: `FUNCTION bucketstore_dummy.WM_CONCAT does not exist`
- **수정 방향**: Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필요
```sql
SELECT WM_CONCAT(product_name) FROM PRODUCTS
```

### Q29 — P12 (SYNTAX_ERROR)
- **설명**: 카테고리 무한 루프 위험 계층 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id
```

### Q30 — P13 (SYNTAX_ERROR)
- **설명**: 레벨 제한 계층 조회
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id AND LEVEL <= 3
```

### Q31 — P26 (SYNTAX_ERROR)
- **설명**: 최상위 카테고리부터 시작하는 계층 조회 (P12+P13 복합)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id
```

### Q54 — P09 (SYNTAX_ERROR)
- **설명**: NOCYCLE 순환 방지 계층 조회 (P12+P26 복합)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: 계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요
```sql
SELECT id, parent_id FROM CATEGORIES CONNECT BY NOCYCLE PRIOR id = parent_id
```

### Q32 — P14 (SYNTAX_ERROR)
- **설명**: WHERE절 (+) 1:N 아우터 조인
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환
```sql
SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+)
```

### Q33 — P14 (SYNTAX_ERROR)
- **설명**: 다중 테이블 아우터 조인 + 추가 조건
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환
```sql
SELECT o.id, p.id FROM ORDERS o, PAYMENTS p WHERE o.id = p.order_id (+) AND p.payment_method (+) = 'CARD'
```

### Q34 — P10 (SYNTAX_ERROR)
- **설명**: 카테고리-상품 아우터 조인 + 가격 조건
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환
```sql
SELECT c.name, p.product_name FROM CATEGORIES c, PRODUCTS p WHERE c.id (+) = p.category_id AND p.price > 10000
```

### Q25 — P10 (SYNTAX_ERROR)
- **설명**: SELECT절 상관 서브쿼리 + ROWNUM (P03+P10 복합)
- **에러**: `Unknown column 'ROWNUM' in 'where clause'`
- **수정 방향**: ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요
```sql
SELECT m.name, ( SELECT MAX(total_amount) FROM ORDERS o WHERE o.member_id = m.id AND ROWNUM = 1 ) FROM MEMBERS m
```

### Q35 — P15 (UNKNOWN_ERROR)
- **설명**: COUPONS.valid_until에 SYSDATE 날짜 연산
- **에러**: `Unknown column 'SYSDATE' in 'where clause'`
- **수정 방향**: 에러 원인 수동 확인 필요
```sql
SELECT * FROM COUPONS WHERE valid_until >= SYSDATE - 7
```

### Q36 — P16 (FUNCTION_NOT_FOUND)
- **설명**: SYSDATE + TO_CHAR 혼용 (P15+P20 복합)
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT * FROM ORDERS WHERE TO_CHAR(SYSDATE, 'YYYYMMDD') = TO_CHAR(created_at, 'YYYYMMDD')
```

### Q37 — P16 (FUNCTION_NOT_FOUND)
- **설명**: PAYMENTS.payment_date에 SYSTIMESTAMP 업데이트
- **에러**: `Unknown column 'SYSTIMESTAMP' in 'field list'`
- **수정 방향**: SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIMESTAMP(6)으로 변환
```sql
UPDATE PAYMENTS SET payment_date = SYSTIMESTAMP WHERE payment_method = 'CARD'
```

### Q38 — P20 (FUNCTION_NOT_FOUND)
- **설명**: ORDERS.created_at과 INTERVAL 연산 혼용
- **에러**: `Unknown column 'SYSTIMESTAMP' in 'where clause'`
- **수정 방향**: SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIMESTAMP(6)으로 변환
```sql
SELECT * FROM ORDERS WHERE created_at > SYSTIMESTAMP - INTERVAL '1' DAY
```

### Q44 — P20 (FUNCTION_NOT_FOUND)
- **설명**: 일별 매출 집계 — 조건절+GROUP BY 모두 TO_CHAR (풀스캔)
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT TO_CHAR(created_at, 'YYYYMMDD'), SUM(total_amount) FROM ORDERS WHERE TO_CHAR(created_at, 'YYYYMMDD') LIKE '202505%' GROUP BY TO_CHAR(created_at, 'YYYYMMDD')
```

### Q45 — P20 (FUNCTION_NOT_FOUND)
- **설명**: PAYMENTS.payment_date 시분초 포맷 정렬
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT * FROM PAYMENTS ORDER BY TO_CHAR(payment_date, 'YYYY-MM-DD HH24:MI:SS') DESC
```

### Q46 — P21 (FUNCTION_NOT_FOUND)
- **설명**: PRODUCTS.price 숫자 포맷으로 변환해 비교
- **에러**: `FUNCTION bucketstore_dummy.TO_CHAR does not exist`
- **수정 방향**: TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환
```sql
SELECT * FROM PRODUCTS WHERE TO_CHAR(price, '999,999') = '10,000'
```

### Q47 — P21 (FUNCTION_NOT_FOUND)
- **설명**: PAYMENTS.payment_date에 TO_DATE 시간 포맷 비교
- **에러**: `FUNCTION bucketstore_dummy.TO_DATE does not exist`
- **수정 방향**: TO_DATE 함수 미지원 — STR_TO_DATE로 변환
```sql
SELECT * FROM PAYMENTS WHERE payment_date >= TO_DATE('2025-05-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS')
```

### Q48 — P22 (FUNCTION_NOT_FOUND)
- **설명**: ORDERS.created_at BETWEEN TO_DATE 연속 사용
- **에러**: `FUNCTION bucketstore_dummy.TO_DATE does not exist`
- **수정 방향**: TO_DATE 함수 미지원 — STR_TO_DATE로 변환
```sql
SELECT * FROM ORDERS WHERE created_at BETWEEN TO_DATE('20250101', 'YYYYMMDD') AND TO_DATE('20251231', 'YYYYMMDD')
```

### Q49 — P22 (FUNCTION_NOT_FOUND)
- **설명**: ORDERS 월별 집계 TRUNC → 풀스캔
- **에러**: `FUNCTION bucketstore_dummy.TRUNC does not exist`
- **수정 방향**: TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변환
```sql
SELECT TRUNC(created_at, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at, 'MM')
```

### Q50 — P06 (FUNCTION_NOT_FOUND)
- **설명**: PAYMENTS.payment_date TRUNC + SYSDATE (P22+P15 복합)
- **에러**: `FUNCTION bucketstore_dummy.TRUNC does not exist`
- **수정 방향**: TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변환
```sql
SELECT * FROM PAYMENTS WHERE TRUNC(payment_date) = TRUNC(SYSDATE - 1)
```

### Q16 — P25 (SYNTAX_ERROR)
- **설명**: 임시 테이블 생성 시 VARCHAR2 사용
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요
```sql
CREATE TEMPORARY TABLE temp_vip_users (user_id VARCHAR2(50), grade VARCHAR2(10))
```

### Q53 — P30 (SYNTAX_ERROR)
- **설명**: Oracle NUMBER 타입으로 테이블 생성
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle NUMBER 타입 미지원 — INT/DECIMAL로 변환 필요
```sql
CREATE TABLE t25 ( price NUMBER(10,2), count NUMBER )
```

### Q58 — P17 (SYNTAX_ERROR)
- **설명**: Oracle NVARCHAR2/NCHAR 타입 선언
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요
```sql
CREATE TABLE t30 ( name NVARCHAR2(50), code NCHAR(10) )
```

### Q39 — P17 (SYNTAX_ERROR)
- **설명**: 재고 차감 MERGE INTO (WHEN MATCHED) + DUAL (P17+P19 복합)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MERGE INTO 미지원 — INSERT ON DUPLICATE KEY UPDATE로 변환
```sql
MERGE INTO PRODUCTS p USING (SELECT 50 AS id, 10 AS qty FROM DUAL) d ON (p.id = d.id) WHEN MATCHED THEN UPDATE SET p.stock_quantity = p.stock_quantity - d.qty
```

### Q40 — P18 (SYNTAX_ERROR)
- **설명**: 회원 상태 MERGE INTO (WHEN NOT MATCHED) + DUAL (P17+P19 복합)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MERGE INTO 미지원 — INSERT ON DUPLICATE KEY UPDATE로 변환
```sql
MERGE INTO MEMBERS m USING (SELECT 'USR10050' AS id, 'ACTIVE' AS status FROM DUAL) d ON (m.id = d.id) WHEN NOT MATCHED THEN INSERT (id, name, email, status) VALUES (d.id, 'Unknown', 'unknown@test.com'
```

### Q41 — P18 (SYNTAX_ERROR)
- **설명**: 주문 이력 없는 회원 도출 (MINUS)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환
```sql
SELECT id FROM MEMBERS MINUS SELECT member_id FROM ORDERS WHERE created_at > '2024-01-01'
```

### Q42 — P19 (SYNTAX_ERROR)
- **설명**: 팔리지 않은 상품 도출 (MINUS)
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환
```sql
SELECT id FROM PRODUCTS MINUS SELECT product_id FROM ORDER_ITEMS
```

### Q43 — P23 (SYNTAX_ERROR)
- **설명**: 시퀀스 NEXTVAL FROM DUAL (AUTO_INCREMENT와 충돌)
- **에러**: `Unknown table 'member_seq' in field list`
- **수정 방향**: Oracle SEQUENCE 문법 미지원 — AUTO_INCREMENT로 변환 필요
```sql
SELECT member_seq.NEXTVAL FROM DUAL
```

### Q51 — P27 (SYNTAX_ERROR)
- **설명**: Oracle SEQUENCE.NEXTVAL INSERT
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle SEQUENCE 문법 미지원 — AUTO_INCREMENT로 변환 필요
```sql
INSERT INTO ORDERS (id, member_id, status, total_amount) VALUES (my_seq.NEXTVAL, 'USR001', 'PENDING', 15000); SELECT my_seq.CURRVAL FROM DUAL
```

### Q56 — P28 (FUNCTION_NOT_FOUND)
- **설명**: Oracle PIVOT으로 연도별 매출 집계
- **에러**: `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version`
- **수정 방향**: Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필요
```sql
SELECT * FROM ( SELECT member_id, status, total_amount FROM ORDERS ) PIVOT ( SUM(total_amount) FOR status IN ('PENDING', 'COMPLETE', 'CANCEL') )
```

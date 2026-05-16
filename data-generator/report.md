# 시뮬레이터 탐지 검증 리포트
> 생성일시: 2026-05-16 02:14:49

## 요약
- 전체: 58건
- 정상 탐지: 50건
- 미탐지: 8건
- API 오류: 0건
- **탐지율: 86.2%**

## 전체 결과

| 쿼리 | 예상 패턴 | 실제 탐지 | 결과 | 비고 |
|------|-----------|-----------|------|------|
| Q01 | ['P01'] | [] | ❌ 미탐지: ['P01'] | VARCHAR FK에 숫자 비교 → 암묵적 형변환 |
| Q02 | ['P01'] | [] | ❌ 미탐지: ['P01'] | id에 +0 산술 연산 → 인덱스 배제 |
| Q03 | ['P01'] | [] | ❌ 미탐지: ['P01'] | VARCHAR PK를 숫자 범위 비교 |
| Q04 | ['P02'] | ['P02'] | ✅ 정상 | UPPER + 양방향 와일드카드 |
| Q05 | ['P02'] | [] | ❌ 미탐지: ['P02'] | SUBSTR로 인덱스 무력화 |
| Q06 | ['P02'] | [] | ❌ 미탐지: ['P02'] | REPLACE로 인덱스 무력화 |
| Q07 | ['P03'] | ['P03'] | ✅ 정상 | 조건절 + ROWNUM |
| Q08 | ['P03'] | ['P03'] | ✅ 정상 | ROWNUM + ORDER BY 논리 오류 |
| Q09 | ['P03'] | ['P03', 'P10'] | ✅ 정상 | 서브쿼리 내 ROWNUM BETWEEN |
| Q10 | ['P04'] | ['P04'] | ✅ 정상 | NVL로 인덱스 무력화 |
| Q11 | ['P04'] | ['P04'] | ✅ 정상 | NVL + 산술 연산 |
| Q12 | ['P04'] | ['P04'] | ✅ 정상 | ORDER BY NVL → Filesort |
| Q13 | ['P05'] | ['P05'] | ✅ 정상 | DATE() 함수로 인덱스 무력화 |
| Q14 | ['P05'] | ['P05'] | ✅ 정상 | CAST(... AS DATE) 형변환 |
| Q15 | ['P05'] | [] | ❌ 미탐지: ['P05'] | 날짜 컬럼 산술 연산 |
| Q16 | ['P06'] | ['P06'] | ✅ 정상 | Oracle 전용 타입 VARCHAR2 |
| Q17 | ['P07'] | [] | ❌ 미탐지: ['P07'] | TRIM으로 인덱스 무력화 |
| Q18 | ['P07'] | [] | ❌ 미탐지: ['P07'] | Oracle || 연산자 + 공백 비교 |
| Q19 | ['P08'] | ['P08', 'P02'] | ✅ 정상 | 함수 기반 인덱스 생성 |
| Q20 | ['P08'] | ['P08', 'P02'] | ✅ 정상 | 함수 기반 인덱스 생성 |
| Q21 | ['P09'] | ['P09'] | ✅ 정상 | 비인덱스 컬럼 JOIN |
| Q22 | ['P09'] | ['P09'] | ✅ 정상 | LIKE 조인 조건 |
| Q23 | ['P09', 'P05'] | ['P09', 'P05'] | ✅ 정상 | DATE() 함수 JOIN (P05+P09 복합) |
| Q24 | ['P10'] | ['P10'] | ✅ 정상 | 3중 중첩 IN |
| Q25 | ['P10', 'P03'] | ['P03', 'P10'] | ✅ 정상 | 상관 서브쿼리 + ROWNUM (P03+P10 복합) |
| Q26 | ['P10'] | ['P10'] | ✅ 정상 | 중첩 EXISTS |
| Q27 | ['P11'] | ['P11'] | ✅ 정상 | DECODE + GROUP BY |
| Q28 | ['P11'] | ['P11'] | ✅ 정상 | WHERE절 DECODE |
| Q29 | ['P12'] | ['P12'] | ✅ 정상 | CONNECT BY 계층 조회 |
| Q30 | ['P12'] | ['P12'] | ✅ 정상 | CONNECT BY + LEVEL 제한 |
| Q31 | ['P13', 'P12'] | ['P12', 'P13'] | ✅ 정상 | START WITH + CONNECT BY (P12+P13 복합) |
| Q32 | ['P14'] | ['P14'] | ✅ 정상 | Oracle (+) 아우터 조인 |
| Q33 | ['P14'] | ['P14'] | ✅ 정상 | (+) 다중 조건 |
| Q34 | ['P14'] | ['P14'] | ✅ 정상 | (+) 조인 + 가격 조건 |
| Q35 | ['P15'] | ['P15'] | ✅ 정상 | SYSDATE 날짜 연산 |
| Q36 | ['P15', 'P20'] | ['P20', 'P15'] | ✅ 정상 | SYSDATE + TO_CHAR (P15+P20 복합) |
| Q37 | ['P16'] | ['P16'] | ✅ 정상 | SYSTIMESTAMP UPDATE |
| Q38 | ['P16'] | ['P16'] | ✅ 정상 | SYSTIMESTAMP + INTERVAL |
| Q39 | ['P17', 'P19'] | ['P19', 'P17'] | ✅ 정상 | MERGE INTO + DUAL (P17+P19 복합) |
| Q40 | ['P17', 'P19'] | ['P19', 'P17'] | ✅ 정상 | MERGE INTO NOT MATCHED + DUAL (P17+P19 복합) |
| Q41 | ['P18'] | ['P18', 'P10'] | ✅ 정상 | MINUS 차집합 |
| Q42 | ['P18'] | ['P18', 'P10'] | ✅ 정상 | MINUS 차집합 |
| Q43 | ['P19'] | ['P19', 'P23'] | ✅ 정상 | NEXTVAL FROM DUAL |
| Q44 | ['P20'] | ['P20'] | ✅ 정상 | TO_CHAR 조건절 + GROUP BY |
| Q45 | ['P20'] | ['P20'] | ✅ 정상 | TO_CHAR ORDER BY |
| Q46 | ['P20'] | ['P20'] | ✅ 정상 | TO_CHAR 숫자 포맷 |
| Q47 | ['P21'] | ['P21'] | ✅ 정상 | TO_DATE 시간 포맷 |
| Q48 | ['P21'] | ['P21'] | ✅ 정상 | BETWEEN TO_DATE ... TO_DATE |
| Q49 | ['P22'] | ['P22'] | ✅ 정상 | TRUNC 월별 집계 |
| Q50 | ['P22', 'P15'] | ['P22', 'P15'] | ✅ 정상 | TRUNC + SYSDATE (P22+P15 복합) |
| Q51 | ['P23'] | ['P23'] | ✅ 정상 | Oracle SEQUENCE.NEXTVAL 사용 |
| Q52 | ['P24'] | ['P24'] | ✅ 정상 | Oracle LISTAGG 집계 함수 |
| Q53 | ['P25'] | ['P25'] | ✅ 정상 | Oracle NUMBER 타입 선언 |
| Q54 | ['P26', 'P12'] | ['P26', 'P12'] | ✅ 정상 | CONNECT BY NOCYCLE (P12+P26 복합) |
| Q55 | ['P27'] | ['P27'] | ✅ 정상 | Oracle REGEXP_LIKE 함수 |
| Q56 | ['P28'] | ['P28'] | ✅ 정상 | Oracle PIVOT 연산자 |
| Q57 | ['P29'] | ['P29'] | ✅ 정상 | Oracle WM_CONCAT (deprecated) |
| Q58 | ['P30'] | ['P30'] | ✅ 정상 | Oracle NVARCHAR2/NCHAR 타입 |

## 미탐지 패턴 상세 — 시뮬레이터 담당자 전달용

### Q01 — 미탐지: ['P01']
- 비고: VARCHAR FK에 숫자 비교 → 암묵적 형변환
- SQL:
```sql
SELECT id, member_id FROM ORDERS WHERE member_id = 10050;
```

### Q02 — 미탐지: ['P01']
- 비고: id에 +0 산술 연산 → 인덱스 배제
- SQL:
```sql
SELECT * FROM PAYMENTS WHERE id + 0 = 100;
```

### Q03 — 미탐지: ['P01']
- 비고: VARCHAR PK를 숫자 범위 비교
- SQL:
```sql
SELECT * FROM MEMBERS WHERE id > 10000 AND id < 20000;
```

### Q05 — 미탐지: ['P02']
- 비고: SUBSTR로 인덱스 무력화
- SQL:
```sql
SELECT * FROM PRODUCTS WHERE SUBSTR(product_name, 1, 3) = 'MAC';
```

### Q06 — 미탐지: ['P02']
- 비고: REPLACE로 인덱스 무력화
- SQL:
```sql
SELECT * FROM MEMBERS WHERE REPLACE(name, ' ', '') = '이동훈';
```

### Q15 — 미탐지: ['P05']
- 비고: 날짜 컬럼 산술 연산
- SQL:
```sql
SELECT * FROM ORDERS WHERE created_at + 1 >= '2025-05-09';
```

### Q17 — 미탐지: ['P07']
- 비고: TRIM으로 인덱스 무력화
- SQL:
```sql
SELECT * FROM ORDERS WHERE TRIM(status) = 'COMPLETE';
```

### Q18 — 미탐지: ['P07']
- 비고: Oracle || 연산자 + 공백 비교
- SQL:
```sql
SELECT * FROM PAYMENTS WHERE payment_method || ' ' = 'CARD ';
```

[시뮬레이터 미탐지 패턴 보고 - 최종]

전체 58건 테스트 결과 8건 미탐지 (탐지율 86.2%)
첨부: report_v2.md

미탐지 원인 요약:

P01 (Q01~Q03): 따옴표 없는 숫자 비교, 산술연산(+0),
  부등호 범위 비교 패턴 regex 없음

P02 (Q05, Q06): UPPER/LOWER만 탐지됨.
  SUBSTR(), REPLACE() 패턴 추가 필요

P05 (Q15): 날짜 컬럼 산술연산(+1) 패턴 없음

P07 (Q17, Q18): TRIM(), || 연산자 regex 자체 없음
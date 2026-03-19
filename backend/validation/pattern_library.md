## P01 Implicit Type Cast

Oracle Pattern:

```
WHERE member_id = '123'
```

MySQL Result:
Implicit type conversion may occur, causing index not to be used.

Risk:
MEDIUM

Reason:
String to numeric casting can disable index usage.

Fix:

```
WHERE member_id = 123
```

---

## P02 Function on Indexed Column

Oracle Pattern:

```
WHERE UPPER(name) = 'KIM'
```

MySQL Result:
Index not used, full table scan occurs.

Risk:
HIGH

Reason:
Applying a function on indexed column prevents index usage.

Fix:

```
WHERE name = 'KIM'
```

or create proper index / generated column

---

## P03 ROWNUM Pagination

Oracle Pattern:

```
WHERE ROWNUM <= 10
```

MySQL Result:
Query returns all rows if LIMIT not applied.

Risk:
HIGH

Reason:
Oracle ROWNUM is not compatible with MySQL LIMIT.

Fix:

```
LIMIT 10
```

---

## P04 NVL vs IFNULL

Oracle Pattern:

```
NVL(col, 0)
```

MySQL Result:
Function not supported.

Risk:
LOW

Reason:
MySQL uses IFNULL instead of NVL.

Fix:

```
IFNULL(col, 0)
```

---

## P05 DATE vs DATETIME Difference

Oracle Pattern:
DATE

MySQL Result:
DATETIME or TIMESTAMP required.

Risk:
MEDIUM

Reason:
Oracle DATE includes time, MySQL DATE does not.

Fix:
Use DATETIME or TIMESTAMP in MySQL.

---

## P06 VARCHAR2 vs VARCHAR Difference

Oracle Pattern:
VARCHAR2

MySQL Result:
VARCHAR

Risk:
LOW

Reason:
Different length / padding / comparison behavior.

Fix:
Check column length and charset explicitly.

---

## P07 CHAR Padding Issue

Oracle Pattern:
CHAR(10)

MySQL Result:
Trailing spaces may affect comparison.

Risk:
LOW

Reason:
CHAR type pads with spaces.

Fix:
Use VARCHAR or TRIM()

---

## P08 Function-Based Index Loss

Oracle Pattern:

```
CREATE INDEX idx ON t(UPPER(name))
```

MySQL Result:
Function-based index not supported directly.

Risk:
HIGH

Reason:
MySQL requires generated column for function index.

Fix:
Use generated column + index.

---

## P09 JOIN Without Index

Oracle Pattern:
JOIN without index

MySQL Result:
Full scan / slow join

Risk:
HIGH

Reason:
MySQL optimizer depends heavily on index.

Fix:
Add index on join column.

---

## P10 Nested Subquery Performance Issue

Oracle Pattern:
Nested subquery

MySQL Result:
Slow execution

Risk:
MEDIUM

Reason:
Optimizer behavior differs between Oracle and MySQL.

Fix:
Rewrite using JOIN.

```
```
# Oracle→MySQL Migration Failure Pattern Library (v2)

정합성 검증 시뮬레이터용 패턴 카탈로그입니다.  
현재 규칙 수: **22개 (P01~P22)**.

| ID | Pattern | Severity | Failure Type | 핵심 이슈 | 기본 대응 |
|---|---|---|---|---|---|
| P01 | Implicit Type Cast | MEDIUM | TYPE_MISMATCH_INDEX_BYPASS | 문자열-숫자 비교로 인덱스 무력화 | CAST 명시/타입 정렬 |
| P02 | Function on Indexed Column | HIGH | FUNCTION_INDEX_BYPASS | UPPER/LOWER로 인덱스 미사용 | 생성컬럼+인덱스 |
| P03 | ROWNUM Pagination | HIGH | PAGINATION_MIGRATION_ERROR | Oracle 전용 페이징 | LIMIT/OFFSET 변환 |
| P04 | NVL Function | LOW | FUNCTION_COMPATIBILITY | NVL 미지원 | IFNULL/COALESCE |
| P05 | DATE vs DATETIME | MEDIUM | TEMPORAL_TYPE_MISMATCH | DATE 시간 의미 차이 | DATETIME/TIMESTAMP 검토 |
| P06 | VARCHAR2 Usage | LOW | STRING_TYPE_COMPATIBILITY | VARCHAR2 타입 차이 | VARCHAR 명시 매핑 |
| P07 | CHAR Padding | LOW | CHAR_PADDING_COMPARISON | trailing space 비교 이슈 | VARCHAR/TRIM |
| P08 | Function Based Index | HIGH | FUNCTION_BASED_INDEX_LOSS | 함수기반 인덱스 이관 누락 | generated column |
| P09 | JOIN Without Index | HIGH | JOIN_FULL_SCAN | 조인 키 인덱스 부재 | 조인키 인덱스 추가 |
| P10 | Nested Subquery | MEDIUM | NESTED_QUERY_DEGRADATION | 중첩 서브쿼리 최적화 저하 | JOIN/CTE 재작성 |
| P11 | DECODE Function | MEDIUM | FUNCTION_COMPATIBILITY | DECODE 미지원 | CASE WHEN |
| P12 | CONNECT BY Hierarchy | HIGH | HIERARCHY_QUERY_MIGRATION | 계층 쿼리 문법 차이 | WITH RECURSIVE |
| P13 | START WITH Hierarchy | MEDIUM | HIERARCHY_QUERY_MIGRATION | 계층 시작점 문법 | recursive CTE base case |
| P14 | Oracle Outer Join (+) | HIGH | JOIN_SYNTAX_INCOMPATIBILITY | (+) 문법 미지원 | LEFT/RIGHT JOIN |
| P15 | SYSDATE Usage | LOW | FUNCTION_COMPATIBILITY | 날짜함수 동작 차이 | NOW()/CURRENT_TIMESTAMP |
| P16 | SYSTIMESTAMP Usage | MEDIUM | TIMESTAMP_PRECISION_COMPATIBILITY | 정밀도/타임존 차이 | precision 포함 매핑 |
| P17 | MERGE INTO Statement | HIGH | UPSERT_SYNTAX_MIGRATION | MERGE 문법 이식 불가 | ON DUPLICATE KEY UPDATE |
| P18 | MINUS Set Operator | MEDIUM | SET_OPERATOR_INCOMPATIBILITY | MINUS 미지원 | NOT EXISTS/ANTI JOIN |
| P19 | DUAL Table Dependency | LOW | SYSTEM_TABLE_DEPENDENCY | DUAL 의존성 | 불필요시 제거 |
| P20 | TO_CHAR Date Formatting | MEDIUM | DATE_FORMAT_FUNCTION_MIGRATION | 포맷 토큰 차이 | DATE_FORMAT 매핑 |
| P21 | TO_DATE Parsing | MEDIUM | DATE_PARSE_FUNCTION_MIGRATION | 파싱 포맷 차이 | STR_TO_DATE 매핑 |
| P22 | TRUNC Date Function | MEDIUM | DATE_TRUNCATION_MIGRATION | 날짜 절삭 의미 차이 | DATE()/DATE_FORMAT |

## 운영 원칙

1. 규칙 추가 시 `pattern_rules.json`과 본 문서를 동시에 갱신한다.
2. severity는 정합성 위험 기준(LOW/MEDIUM/HIGH)으로 유지한다.
3. 수치 기반 RiskScore는 본 카탈로그에서 다루지 않고 예측 모델 파트에서 관리한다.


## 정량 신호 예시

- Full Scan 여부: `EXPLAIN type=ALL`, `key=NULL`
- 탐색량 급증: `EXPLAIN rows` 급증
- 호환성 오류: 실행 시 syntax/function error
- 정합성 차이: 변환 전/후 row count 또는 집계 결과 불일치
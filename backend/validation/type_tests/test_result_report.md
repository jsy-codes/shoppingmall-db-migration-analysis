# Oracle → MySQL 패턴 정합성 통합 리포트
> 생성: 2026-05-29 17:02

## 검증 3축 기준
| 축 | 의미 |
|---|---|
| ① 탐지 | consistency_simulator가 패턴을 잡아냈는가 (result.json) |
| ② 실행 | MySQL에서 syntax/function 에러 없이 실행되는가 (result.csv) |
| ③ 결과 | 변환 전후 SELECT 결과 row가 일치하는가 (result_compare.csv) |

## 패턴별 정합성 결과

| ID | 패턴명 | 위험도 | 등급 | ① 탐지 | ② 실행 | ③ 결과 일치 | 비고 |
|---|---|---|---|---|---|---|---|
| P01 | Implicit Type Cast | MEDIUM | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ✅ 일치 | 전체 9건 일치 |
| P02 | Function on Indexed Column | HIGH | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ✅ 일치 | 전체 9건 일치 |
| P03 | ROWNUM Pagination | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1054 (42S22): Unknown column 'ROWNUM' in 'where clause' |
| P04 | NVL Function | LOW | 🟢 AUTO | ✅ 탐지 | ❌ 에러 | ❌ 실행불가 | ['1305 (42000): FUNCTION type_test.NVL does not exist'] |
| P05 | DATE vs DATETIME | MEDIUM | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ✅ 일치 | 전체 8건 일치 |
| P06 | VARCHAR2 Usage | LOW | 🟡 VERIFY | ⚠️ 미탐지 | ❌ 에러 | ⚪ 미실행 | 1406 (22001): Data too long for column 'name' at row 1 |
| P07 | CHAR Padding | LOW | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ⚪ 미실행 | 공백 패딩 비교 동작이 Oracle/MySQL 간 미묘하게 다름 — TRIM 적용 후 검증 |
| P08 | Function Based Index | HIGH | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ⚪ 미실행 | 쿼리 결과는 동일하나 인덱스 미적용으로 성능 저하 — generated column 대체 필요 |
| P09 | JOIN Without Index | HIGH | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ⚪ 미실행 | 결과 동일하나 조인 키 인덱스 누락 시 성능 급격히 저하 |
| P10 | Nested Subquery | MEDIUM | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ✅ 일치 | 전체 8건 일치 |
| P11 | DECODE Function | MEDIUM | 🟢 AUTO | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | CASE WHEN으로 1:1 구조 치환 가능, NULL 처리 동작 동일 |
| P12 | CONNECT BY Hierarchy | HIGH | 🔴 MANUAL | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | WITH RECURSIVE로 전면 재작성 필요 — 변환 후 row count 및 계층 순서 검증 필수 |
| P13 | START WITH Hierarchy | MEDIUM | 🔴 MANUAL | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | 재귀 CTE base case로 변환 — 시작 조건 누락 시 결과 전혀 달라짐 |
| P14 | Oracle Outer Join (+) | HIGH | 🔴 MANUAL | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | MySQL에서 즉시 syntax error — LEFT/RIGHT JOIN으로 재작성 후 결과 검증 필수 |
| P15 | SYSDATE Usage | LOW | 🟢 AUTO | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | NOW()로 단순 치환 가능 — 시간대 설정이 동일한 경우 결과 동일 |
| P16 | SYSTIMESTAMP Usage | MEDIUM | 🟡 VERIFY | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | 밀리초 정밀도 및 타임존 처리 방식 차이 — CURRENT_TIMESTAMP(6) 등 명시적 정밀도 지정 필 |
| P17 | MERGE INTO Statement | HIGH | 🔴 MANUAL | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | INSERT ... ON DUPLICATE KEY UPDATE로 전면 재작성 — 다중 조건 MERGE는 로직 |
| P18 | MINUS Set Operator | MEDIUM | 🔴 MANUAL | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | NOT EXISTS 또는 LEFT JOIN anti-join으로 재작성 — 변환 후 row count 반드시 |
| P19 | DUAL Table Dependency | LOW | 🟢 AUTO | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | FROM DUAL 제거 후 SELECT 표현식만으로 동일 결과 — 단순 치환 가능 |
| P20 | TO_CHAR Date Formatting | MEDIUM | 🟡 VERIFY | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | DATE_FORMAT으로 대체 가능하나 포맷 토큰(YYYY→%Y 등) 매핑 후 출력값 비교 필수 |
| P21 | TO_DATE Parsing | MEDIUM | 🟡 VERIFY | ⚪ 미실행 | ⚪ 미실행 | ⚪ 미실행 | STR_TO_DATE로 대체 시 포맷 토큰 매핑 필요 — 파싱 결과 날짜값 비교 필수 |
| P22 | TRUNC Date Function | MEDIUM | 🟡 VERIFY | ⚪ 미실행 | ⚪ 미실행 | ✅ 일치 | 전체 8건 일치 |
| P23 | SEQUENCE NEXTVAL/CURRVAL | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1054 (42S22): Unknown column 'my_seq.NEXTVAL' in 'field list' |
| P24 | LISTAGG Aggregation | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1064 (42000): You have an error in your SQL syntax; check the manual t |
| P25 | NUMBER Type Declaration | LOW | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1064 (42000): You have an error in your SQL syntax; check the manual t |
| P26 | CONNECT BY NOCYCLE | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1064 (42000): You have an error in your SQL syntax; check the manual t |
| P27 | REGEXP_LIKE Function | MEDIUM | 🟡 VERIFY | ✅ 탐지 | ✅ OK | ⚪ 미실행 | REGEXP으로 대체 가능하나 대소문자 구분 플래그 차이로 결과 건수 불일치 가능 — 검증 필요 |
| P28 | PIVOT/UNPIVOT Operator | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1064 (42000): You have an error in your SQL syntax; check the manual t |
| P29 | WM_CONCAT Aggregation | HIGH | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | ['1305 (42000): FUNCTION type_test.WM_CONCAT does not exist'] |
| P30 | NCHAR/NVARCHAR2 Type | LOW | 🔴 MANUAL | ✅ 탐지 | ❌ 에러 | ⚪ 미실행 | 1064 (42000): You have an error in your SQL syntax; check the manual t |

---

## 요약 통계

### 정합성 등급 분포
- 🟢 AUTO  (자동 변환, 결과 보장): 4건
- 🟡 VERIFY (변환 후 검증 필요):    13건
- 🔴 MANUAL (수동 재작성 필요):     13건

### 실행 호환성 (② 실행)
- ✅ OK       : 8건
- ❌ 에러      : 10건  ← Oracle 전용 구문 확인
- ⚪ 미실행    : 12건

### 결과 정합성 (③ 결과)
- ✅ 일치      : 5건
- ⚠️ 불일치    : 0건  ← 변환 로직 재검토 필요
- ⚪ 미실행    : 25건

---

## 등급별 조치 가이드

| 등급 | 의미 | 조치 |
|---|---|---|
| 🟢 AUTO   | 1:1 치환 가능, 결과 동일 보장 | 변환 스크립트 자동 적용 가능 |
| 🟡 VERIFY | 변환 패턴 존재하나 결과 검증 필요 | 변환 후 SELECT 결과 비교 실행 |
| 🔴 MANUAL | 직접 대응 구문 없음, 수동 재작성 | DBA/개발자 리뷰 후 재작성 |

> consistency_check.csv — 테이블 Row Count / Checksum 검증 완료
> result_compare.csv   — 변환 전후 SELECT 결과 row 비교 완료
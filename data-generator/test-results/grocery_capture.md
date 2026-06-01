# 시나리오 A — Grocery Market Oracle 패턴 탐지 결과 캡처
> 생성: 2026-06-01 19:15:51

## 기준 비교

| 항목 | 중간평가 기준 (JTA_Packages.sql) | 현재 (전체 3파일) |
|------|----------------------------------|------------------|
| 분석 구문 수 | 470개 | 682개 |
| 패턴 탐지 건수 | 131건 | 401건 |
| 실패 유형 종류 | 11종 | 23종 |

## 파일별 탐지 현황

| 파일 | 구문 수 | 탐지 건수 |
|------|---------|---------|
| JTA_Create_Database.sql | 272 | 232 |
| JTA_Packages.sql | 196 | 85 |
| JTA_Test_Code.sql | 203 | 67 |
| oracle_pattern_fixtures.sql | 11 | 17 |

## 패턴별 탐지 횟수

| 패턴 ID | 패턴명 | 위험도 | 탐지 횟수 |
|---------|--------|--------|---------|
| P01 | Implicit Type Cast | MEDIUM | 13건 |
| P03 | ROWNUM Pagination | HIGH | 1건 |
| P04 | NVL Function | MEDIUM | 4건 |
| P05 | DATE vs DATETIME | MEDIUM | 35건 |
| P06 | VARCHAR2 Usage | MEDIUM | 32건 |
| P07 | CHAR Padding | MEDIUM | 2건 |
| P09 | JOIN Without Index | HIGH | 8건 |
| P10 | Nested Subquery | MEDIUM | 6건 |
| P12 | CONNECT BY Hierarchy | HIGH | 2건 |
| P13 | START WITH Hierarchy | MEDIUM | 25건 |
| P14 | Oracle Outer Join (+) | HIGH | 1건 |
| P15 | SYSDATE Usage | MEDIUM | 13건 |
| P17 | MERGE INTO Statement | HIGH | 1건 |
| P19 | DUAL Table Dependency | MEDIUM | 1건 |
| P20 | TO_CHAR Date Formatting | MEDIUM | 10건 |
| P21 | TO_DATE Parsing | MEDIUM | 77건 |
| P22 | TRUNC Date Function | MEDIUM | 7건 |
| P23 | SEQUENCE NEXTVAL/CURRVAL | HIGH | 80건 |
| P24 | LISTAGG Aggregation | HIGH | 1건 |
| P25 | NUMBER Type Declaration | MEDIUM | 77건 |
| P26 | CONNECT BY NOCYCLE | HIGH | 1건 |
| P27 | REGEXP_LIKE Function | MEDIUM | 1건 |
| P28 | PIVOT/UNPIVOT Operator | HIGH | 1건 |
| P29 | WM_CONCAT Aggregation | HIGH | 1건 |
| P30 | NCHAR/NVARCHAR2 Type | MEDIUM | 1건 |

## 체크리스트

- ✅ P03 — ROWNUM Pagination (1건)
- ✅ P12 — CONNECT BY Hierarchy (2건)
- ✅ P14 — Oracle Outer Join (+) (1건)
- ✅ P17 — MERGE INTO Statement (1건)
- ✅ P19 — DUAL Table Dependency (1건)

### 신규 패턴 P23~P30
- ✅ P23 — SEQUENCE NEXTVAL/CURRVAL (80건)
- ✅ P24 — LISTAGG Aggregation (1건)
- ✅ P25 — NUMBER Type Declaration (77건)
- ✅ P26 — CONNECT BY NOCYCLE (1건)
- ✅ P27 — REGEXP_LIKE Function (1건)
- ✅ P28 — PIVOT/UNPIVOT Operator (1건)
- ✅ P29 — WM_CONCAT Aggregation (1건)
- ✅ P30 — NCHAR/NVARCHAR2 Type (1건)
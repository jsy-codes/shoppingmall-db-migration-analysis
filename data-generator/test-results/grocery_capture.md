# 시나리오 A — Grocery Market Oracle 패턴 탐지 결과 캡처
> 생성: 2026-05-26 23:43:39

## 기준 비교

| 항목 | 중간평가 기준 (JTA_Packages.sql) | 현재 (전체 3파일) |
|------|----------------------------------|------------------|
| 분석 구문 수 | 470개 | 946개 |
| 패턴 탐지 건수 | 131건 | 439건 |
| 실패 유형 종류 | 11종 | 14종 |

## 파일별 탐지 현황

| 파일 | 구문 수 | 탐지 건수 |
|------|---------|---------|
| JTA_Create_Database.sql | 272 | 232 |
| JTA_Packages.sql | 470 | 137 |
| JTA_Test_Code.sql | 204 | 70 |

## 패턴별 탐지 횟수

| 패턴 ID | 패턴명 | 위험도 | 탐지 횟수 |
|---------|--------|--------|---------|
| P01 | Implicit Type Cast | MEDIUM | 17건 |
| P02 | Function on Indexed Column | HIGH | 1건 |
| P04 | NVL Function | LOW | 8건 |
| P05 | DATE vs DATETIME | MEDIUM | 46건 |
| P06 | VARCHAR2 Usage | LOW | 36건 |
| P07 | CHAR Padding | LOW | 2건 |
| P09 | JOIN Without Index | HIGH | 15건 |
| P10 | Nested Subquery | MEDIUM | 6건 |
| P13 | START WITH Hierarchy | MEDIUM | 25건 |
| P15 | SYSDATE Usage | LOW | 18건 |
| P20 | TO_CHAR Date Formatting | MEDIUM | 12건 |
| P21 | TO_DATE Parsing | MEDIUM | 77건 |
| P22 | TRUNC Date Function | MEDIUM | 8건 |
| P23 | SEQUENCE NEXTVAL/CURRVAL | HIGH | 83건 |
| P25 | NUMBER Type Declaration | LOW | 85건 |

## 체크리스트

- ❌ P03 — ROWNUM Pagination (미탐지)
- ❌ P12 — CONNECT BY Hierarchy (미탐지)
- ❌ P14 — Oracle Outer Join (+) (미탐지)
- ❌ P17 — MERGE INTO Statement (미탐지)
- ❌ P19 — DUAL Table Dependency (미탐지)

### 신규 패턴 P23~P30
- ✅ P23 — SEQUENCE NEXTVAL/CURRVAL (83건)
- ⚠ P24 — LISTAGG Aggregation (미탐지)
- ✅ P25 — NUMBER Type Declaration (85건)
- ⚠ P26 — CONNECT BY NOCYCLE (미탐지)
- ⚠ P27 — REGEXP_LIKE Function (미탐지)
- ⚠ P28 — PIVOT/UNPIVOT Operator (미탐지)
- ⚠ P29 — WM_CONCAT Aggregation (미탐지)
- ⚠ P30 — NCHAR/NVARCHAR2 Type (미탐지)

> ⚠ 미탐지 패턴 ['P24', 'P26', 'P27', 'P28', 'P29', 'P30']
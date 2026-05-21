# P23~P30 패턴 탐지 단위 테스트 결과
> 생성: 2026-05-21 14:15
> **판정 기준**: Oracle 전용 구문이 MySQL에서 에러를 내면 '탐지 성공'

| ID | 패턴명 | 위험도 | MySQL 실행 결과 | 판정 | 증거 (에러 메시지 요약) |
|---|---|---|---|---|---|
| P01 | Implicit Type Cast | MEDIUM | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P02 | Function on Indexed Column | HIGH | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P03 | ROWNUM Pagination | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1054 (42S22): Unknown column 'ROWNUM' in 'where clause'` |
| P04 | NVL Function | LOW | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `['1305 (42000): FUNCTION type_test.NVL does not exist']` |
| P05 | DATE vs DATETIME | MEDIUM | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P06 | VARCHAR2 Usage | LOW | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1406 (22001): Data too long for column 'name' at row 1` |
| P07 | CHAR Padding | LOW | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P08 | Function Based Index | HIGH | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P09 | JOIN Without Index | HIGH | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P10 | Nested Subquery | MEDIUM | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P23 | SEQUENCE NEXTVAL/CURRVAL | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1054 (42S22): Unknown column 'my_seq.NEXTVAL' in 'field list'` |
| P24 | LISTAGG Aggregation | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1064 (42000): You have an error in your SQL syntax; check the manual that corres` |
| P25 | NUMBER Type Declaration | LOW | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1064 (42000): You have an error in your SQL syntax; check the manual that corres` |
| P26 | CONNECT BY NOCYCLE | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1064 (42000): You have an error in your SQL syntax; check the manual that corres` |
| P27 | REGEXP_LIKE Function | MEDIUM | OK | ✅ 구문 통과 (성능·정합성 이슈) | `런타임 성능 저하 / 데이터 불일치 유형` |
| P28 | PIVOT/UNPIVOT Operator | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1064 (42000): You have an error in your SQL syntax; check the manual that corres` |
| P29 | WM_CONCAT Aggregation | HIGH | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `['1305 (42000): FUNCTION type_test.WM_CONCAT does not exist']` |
| P30 | NCHAR/NVARCHAR2 Type | LOW | 에러 | ✅ 탐지 성공 (Oracle 전용 구문) | `1064 (42000): You have an error in your SQL syntax; check the manual that corres` |

## 요약
- 전체 실행: 18건
- 에러 발생 (Oracle 전용 구문 확인): 10건
- 구문 통과 (성능·정합성 이슈): 8건

> consistency_check.csv 로 정합성(Row Count / Checksum)도 별도 검증 완료
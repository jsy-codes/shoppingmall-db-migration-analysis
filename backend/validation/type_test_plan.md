# Type Conversion Test Plan

목적

Oracle → MySQL 마이그레이션 시 발생하는
데이터 타입 변환 오차를 검증한다.


## 테스트 항목

| ID | Oracle | MySQL | 테스트 | 예상 문제 |
|----|--------|--------|--------|----------|
| T01 | NUMBER | INT | 큰 값 | overflow |
| T02 | NUMBER(10,4) | DECIMAL | 소수 | 반올림 |
| T03 | DATE | DATETIME | 시간 | 차이 |
| T04 | VARCHAR2 | VARCHAR | 공백 | trim |
| T05 | CHAR | CHAR | padding | 비교 |
| T06 | CLOB | TEXT | 길이 | trunc |
| T07 | NUMBER | VARCHAR | cast | index |
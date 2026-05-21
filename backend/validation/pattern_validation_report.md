# Oracle→MySQL 패턴 검증 및 실측 결과 보고서

## 1. 개요

본 문서는 Oracle→MySQL 이관 과정에서 발생 가능한 SQL 패턴 기반 위험 요소를 탐지하고,
실제 EXPLAIN 및 실행시간 측정을 통해 검증한 결과를 정리한다.

총 30개의 이관 실패 패턴(P01~P30)을 정의하였으며,
정규식(regex) 및 heuristic 기반 탐지 규칙을 pattern_rules.json에 구현하였다.

또한 핵심 성능 패턴(P01, P02, P09, P10, P22)에 대해
MySQL EXPLAIN FORMAT=JSON 기반 실측 실험을 수행하였다.

---

# 2. 패턴 분류 현황

| 구분           | 개수 |
| ------------ | -- |
| 전체 패턴        | 30 |
| Regex 기반     | 24 |
| Heuristic 기반 | 6  |
| 성능 위험 패턴     | 8  |
| 문법 비호환 패턴    | 14 |
| 정합성 위험 패턴    | 8  |

---

# 3. 신규 패턴(P23~P30) 단위 테스트 결과

| 패턴                     | 결과    |
| ---------------------- | ----- |
| P23 SEQUENCE NEXTVAL   | 탐지 성공 |
| P24 LISTAGG            | 탐지 성공 |
| P25 NUMBER 타입          | 탐지 성공 |
| P26 CONNECT BY NOCYCLE | 탐지 성공 |
| P27 REGEXP_LIKE        | 탐지 성공 |
| P28 PIVOT/UNPIVOT      | 탐지 성공 |
| P29 WM_CONCAT          | 탐지 성공 |
| P30 NCHAR/NVARCHAR2    | 탐지 성공 |

Oracle 전용 구문이 MySQL에서 syntax error를 발생시키는 것을 기준으로 검증하였다.

---

# 4. EXPLAIN 기반 실측 결과

## P01 — Implicit Type Cast

* before_ms: 33.75ms
* after_ms: 0.54ms
* full_scan_ratio: 1.0 → 0.0
* no_index_flag: True → False

타입 암묵 변환 제거 후 인덱스 사용이 정상화되었음을 확인하였다.

---

## P02 — Function on Indexed Column

* before_ms: 8.53ms
* after_ms: 0.46ms
* type=ALL 발생 확인

UPPER(email) 사용 시 인덱스 우회가 발생하였다.

---

## P22 — DATE Function on DATETIME

* before_ms: 19.19ms
* after_ms: 0.31ms
* rows_ratio: 99936 → 1

DATE(created_at) 함수 제거 후 인덱스 Range Scan이 정상 동작하였다.

---

# 5. 보완 필요 패턴

## P09 — JOIN Without Index

실험 대상 테이블에 기존 인덱스가 존재하여
before/after 차이가 명확히 나타나지 않았다.

향후 별도 실험용 테이블 기반 재측정이 필요하다.

## P10 — Nested Subquery

실행은 성공했으나 before EXPLAIN JSON 파싱 결과가 비어 있었다.

explain_parser의 nested query 처리 보완이 필요하다.

---

# 6. 정합성 검증 결과

consistency_check.csv 기준:

* 전체 대상 테이블 checksum 검증 완료
* Row Count 불일치 없음
* 데이터 손실 없음

---

# 7. 결론

30개 Oracle→MySQL 이관 실패 패턴 카탈로그를 구축하였다.

또한 EXPLAIN 기반 실측 실험을 통해
핵심 성능 패턴(P01/P02/P22)의 인덱스 우회 및 Full Scan 현상을 검증하였다.

향후 explain_parser 보완 및 Grid Search 안정화를 통해
예측 정확도를 추가 개선할 예정이다.

# Migration Pattern Experiment Result

## 목적

Oracle → MySQL 이관 시 발생할 수 있는 데이터 정합성 문제와
쿼리 호환성 오류를 확인하기 위해 10가지 패턴을 실험하였다.

실험 환경

- MySQL 8
- Python mysql-connector
- 자동 실행 스크립트 사용

---

## 결과 요약

| Pattern | Result | 의미 |
|---------|--------|--------|
| P01 Implicit Cast | OK | 자동 형변환 발생 가능 |
| P02 Function on Index | OK | index 사용 제한 가능 |
| P03 ROWNUM | ERROR | MySQL에서 지원 안됨 |
| P04 NVL | ERROR | 함수 미지원 |
| P05 DATE | OK | 타입 차이 존재 |
| P06 VARCHAR | ERROR | 길이 초과 |
| P07 CHAR | OK | padding 영향 가능 |
| P08 Function Index | OK | index 사용 제한 |
| P09 Join Index | OK | index 없으면 느림 |
| P10 Subquery | OK | optimizer 차이 가능 |

---

## 상세 분석

### P01 Implicit Type Cast

숫자 컬럼을 문자열과 비교 시
MySQL에서 implicit cast 발생 가능

성능 저하 위험 있음


### P02 Function on Indexed Column

컬럼에 함수 적용 시
index 사용 안됨


### P03 ROWNUM

Oracle 문법

ROWNUM

MySQL 미지원

LIMIT 사용 필요


### P04 NVL

Oracle NVL

MySQL IFNULL 사용해야 함


### P05 DATE

Oracle DATE = datetime

MySQL DATE = date only

정합성 문제 가능


### P06 VARCHAR

길이 초과 시 insert 실패

이관 시 데이터 손실 가능


### P07 CHAR

padding 발생

비교 오류 가능


### P08 Function Index

Oracle 지원

MySQL 직접 지원 안함

generated column 필요


### P09 Join

index 없으면 full scan


### P10 Subquery

optimizer 차이 존재


---

## 결론

Oracle → MySQL 이관 시

- 함수 호환성 문제
- 타입 차이 문제
- 인덱스 사용 문제
- 문자열 길이 문제
- 문법 차이

등의 패턴이 존재하며

이를 pattern library 로 정리하였다.
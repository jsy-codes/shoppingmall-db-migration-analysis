# LLM 일관성 비교 실험 리포트
생성일시: 2026-06-04 16:28

## 실험 개요
- 테스트 SQL: 8종 (Oracle 이관 핵심 위험 패턴)
- 반복 횟수: 5회 (동일 SQL, 동일 조건)
- Claude vanilla: 시스템 프롬프트 없음, temperature 기본값(1.0)
- 우리 시스템: pattern_rules.json 기반 결정론적 탐지 + Claude API

---

## 결과 요약

| 패턴 | 예상 | Claude vanilla 분포 | vanilla 일관성 | 우리 시스템 분포 | 우리 일관성 |
|------|------|---------------------|--------------|----------------|-----------|
| P03 ROWNUM Pagination | HIGH | {HIGH: 4, MEDIUM: 1} | 🟡 80% | {HIGH: 5} | ✅ 100% |
| P04 NVL Function | MEDIUM | {MEDIUM: 5} | ✅ 100% | {MEDIUM: 5} | ✅ 100% |
| P12 CONNECT BY Hierarchy | HIGH | {HIGH: 5} | ✅ 100% | {HIGH: 5} | ✅ 100% |
| P14 Oracle Outer Join (+) | HIGH | {HIGH: 1, MEDIUM: 4} | 🟡 80% | {HIGH: 5} | ✅ 100% |
| P23 SEQUENCE NEXTVAL | HIGH | {HIGH: 5} | ✅ 100% | {HIGH: 5} | ✅ 100% |
| P17 MERGE INTO Statement | HIGH | {MEDIUM: 4, HIGH: 1} | 🟡 80% | {HIGH: 5} | ✅ 100% |
| P24 LISTAGG Aggregation | HIGH | {HIGH: 4, MEDIUM: 1} | 🟡 80% | {HIGH: 5} | ✅ 100% |
| P02 Function on Indexed Column | HIGH | {LOW: 2, MEDIUM: 3} | 🔴 60% | {HIGH: 5} | ✅ 100% |

## 핵심 수치

- **Claude vanilla 평균 일관성: 85.0%**
- **우리 시스템 평균 일관성: 100.0%**
- **일관성 차이: +15.0%p (우리 시스템 우위)**

---

## 패턴별 상세

### P03 — ROWNUM Pagination
**왜 어려운가**: ROWNUM은 Oracle 전용 — MySQL에서 즉시 syntax error
**vanilla 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'MEDIUM']  →  일관성 80%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 90.0~90.0점

### P04 — NVL Function
**왜 어려운가**: NVL은 Oracle 전용 — MySQL에서 function not found 에러
**vanilla 5회**: ['MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM']  →  일관성 100%
**우리 시스템 5회**: ['MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM']  →  일관성 100%  점수: 60.0~60.0점

### P12 — CONNECT BY Hierarchy
**왜 어려운가**: CONNECT BY는 Oracle 계층 쿼리 전용 — MySQL에서 syntax error, WITH RECURSIVE 재작성 필요
**vanilla 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 100.0~100.0점

### P14 — Oracle Outer Join (+)
**왜 어려운가**: (+) 조인 문법은 Oracle 전용 — MySQL에서 즉시 syntax error
**vanilla 5회**: ['HIGH', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM']  →  일관성 80%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 90.0~90.0점

### P23 — SEQUENCE NEXTVAL
**왜 어려운가**: SEQUENCE.NEXTVAL은 Oracle 전용 — MySQL AUTO_INCREMENT로 전면 재작성 필요
**vanilla 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 90.0~90.0점

### P17 — MERGE INTO Statement
**왜 어려운가**: MERGE INTO는 Oracle 전용 — MySQL에서 INSERT ... ON DUPLICATE KEY UPDATE로 재작성 필요
**vanilla 5회**: ['MEDIUM', 'MEDIUM', 'HIGH', 'MEDIUM', 'MEDIUM']  →  일관성 80%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 100.0~100.0점

### P24 — LISTAGG Aggregation
**왜 어려운가**: LISTAGG는 Oracle 전용 — MySQL GROUP_CONCAT으로 재작성 필요
**vanilla 5회**: ['HIGH', 'MEDIUM', 'HIGH', 'HIGH', 'HIGH']  →  일관성 80%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 90.0~90.0점

### P02 — Function on Indexed Column
**왜 어려운가**: UPPER()로 인덱스 무력화 — 성능 저하 패턴, 범용 LLM이 HIGH로 판단 안 할 수 있음
**vanilla 5회**: ['LOW', 'MEDIUM', 'LOW', 'MEDIUM', 'MEDIUM']  →  일관성 60%
**우리 시스템 5회**: ['HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH']  →  일관성 100%  점수: 85.0~85.0점

---

## 발표 핵심 메시지

> **같은 Claude API를 쓰더라도, 시스템 프롬프트와 결정론적 탐지 엔진이 없으면
> 동일 SQL에 대해 매번 다른 위험도를 판단합니다.**
>
> 우리 시스템은 pattern_rules.json 기반 탐지 → 위험도 점수 → Claude 해석의
> 3단계 파이프라인으로, LLM이 수치를 만드는 게 아니라 실측 기반 수치를 해석합니다.
> 동일 SQL → 동일 패턴 ID → 동일 점수가 보장되는 것이 핵심 차이입니다.
# 정합성 검증 시뮬레이터 완성 가이드

## 목표

정합성 검증 시뮬레이터는 **RiskScore를 수치 계산하지 않는다.**

- 담당: Oracle->MySQL **호환성/정합성 실패 패턴 탐지**
- 비담당: 위험도 수치화(RiskScore), 예측 정확도 모델링 (김채운 파트)

---

## 완료 기준 (Done Definition)

1. 패턴 규칙집이 20개 이상이다. (`P01`~`P22`)  
2. SQL 입력 시 패턴 ID, 실패유형(failure_type), 권고안을 JSON으로 반환한다.  
3. statement 단위 + 전체 summary를 모두 제공한다.  
4. FastAPI/LLM 프롬프트에서 바로 재사용 가능한 구조를 유지한다.

---

## 실행 방법

```bash P+{패턴 번호}
python backend\validation\consistency_simulator.py --sql-file backend\validation\type_tests\P02.sql --rules backend\validation\pattern_rules.json --output backend\validation\type_tests\P02_result.json
```


---

## 출력 스키마 (핵심)

- `summary.total_pattern_count`
- `summary.max_severity`
- `summary.severity_counts`
- `summary.failure_types`
- `details[].pattern_ids`
- `details[].failure_types`
- `details[].recommendations`
- `details[].matched_patterns[].impact` (왜 느려지는지/깨지는지)
- `details[].matched_patterns[].quant_signal` (가능한 정량 신호)

> 주의: `risk_score`는 intentionally excluded

---

## 3단계 로드맵

### Step A (지금)
- 패턴 20개+ 확장
- 오탐/미탐 케이스 수집

### Step B
- FastAPI `/validate` 연결
- SQL 입력 -> failure_type 반환

### Step C
- AI 진단 System Prompt에 pattern_rules.json 주입
- 실패유형별 권고 쿼리/DDL 템플릿 연결

---

## 발표용 한 줄

> "우리는 Oracle→MySQL 이관 실패 패턴 22종을 구축했고, 정합성 시뮬레이터가 실패 유형과 수정 권고를 즉시 반환합니다."

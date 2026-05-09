RiskModel v2 설계 문서 (초안)

1. 개요
현재의 위험도 모델(v1)은 하드코딩된 규칙에 의존하여 오차율이 존재함. 이를 개선하기 위해 RiskModel v2에서는 MySQL 8.0의 `EXPLAIN FORMAT=JSON` 실행 계획 데이터를 직접 파싱하여 정량적 위험 신호(`quant_signal`)를 모델에 주입함.

2. 핵심 변경 사항: `quant_signal` 필드 추가
위험도 계산 로직에 실제 쿼리 실행 계획의 정량적 데이터를 반영하기 위해 새로운 필드를 추가함.

필드명: `quant_signal` (데이터 타입: Dictionary)
추출 파라미터 (EXPLAIN JSON 기반):
   `is_full_scan` (boolean): `access_type == "ALL"` 여부
   `no_index_flag` (boolean): `key == NULL` 여부
   `rows_examined` (integer): 풀 스캔 시 검사해야 할 예상 행 수

3. 향후 보정 계획 (Grid Search 연동)
v2 모델의 점수 정확도를 높이기 위해, 실측 오차 데이터를 기반으로 아래 범위 내에서 최적의 파라미터를 탐색함.
DECAY_RATE: [0.1, 0.2, 0.3, 0.4]
BONUS: [1 ~ 15]

4. 기대 효과 (차별성)
단순한 텍스트 기반 LLM 추론을 넘어서, **실제 DB 엔진이 내뱉는 실행 계획 데이터를 파싱(parsing)하여 수학적 근거(실측치)를 마련함. 이를 통해 사전 예측의 전문성을 대폭 강화하고 오차율을 3.0% 이하로 낮춤.
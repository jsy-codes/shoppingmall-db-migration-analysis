# 실측 Harness 안정화 리포트
> 생성일시: 2026-05-18 03:42:28
> 반복 횟수: 6회 (1회차 워밍업 제외 → 5회 평균)
> 편차 허용 기준: ±5.0%
> 이상값 처리: IQR 자동 제거 | 5.0ms 미만: 측정 한계
> 패턴 메타데이터: pattern_rules.json (30개 패턴 로드)

## 요약
- 전체: 10건
- 안정: 4건
- 불안정: 6건

## 전체 측정 결과

| 패턴 | 패턴명 | 위험도 | 실패유형 | 안티패턴(ms) | 편차 | 개선(ms) | 편차 | 개선율 | 결과 |
|------|--------|--------|----------|-------------|------|---------|------|--------|------|
| P01 | P01 — Implicit Type Cast | MEDIUM | TYPE_MISMATCH_INDEX_BYPASS | 158.4 | ±19.4% | 12.1 | ±80.1% | +92.3% | ❌ 불안정 |
| P02 | P02 — Function on Indexed Column | HIGH | FUNCTION_INDEX_BYPASS | 3.1 | ±0.0% | 1.1 | ±0.0% | +64.1% | ✅ 안정 |
| P03 | P03 — ROWNUM Pagination | HIGH | PAGINATION_MIGRATION_ERROR | N/A | - | 1.2 | ±0.0% | - | ✅ 안정 |
| P05 | P05 — DATE vs DATETIME | MEDIUM | TEMPORAL_TYPE_MISMATCH | 134.5 | ±7.4% | 1.5 | ±0.0% | +98.9% | ❌ 불안정 |
| P09 | P09 — JOIN Without Index | HIGH | JOIN_FULL_SCAN | 14.2 | ±10.4% | 2.0 | ±0.0% | +86.1% | ❌ 불안정 |
| P10 | P10 — Nested Subquery | MEDIUM | NESTED_QUERY_DEGRADATION | 4368.7 | ±25.6% | 4294.8 | ±9.9% | +1.7% | ❌ 불안정 |
| P20 | P20 — TO_CHAR Date Formatting | MEDIUM | DATE_FORMAT_FUNCTION_MIGRATION | N/A | - | 2.0 | ±0.0% | - | ✅ 안정 |
| P02 | P02 응용 — GROUP BY 집계 | HIGH | FUNCTION_INDEX_BYPASS | 717.4 | ±106.8% | 3067.7 | ±40.3% | -327.6% | ❌ 불안정 |
| P03 | P03 응용 — 대량 OFFSET 페이징 | HIGH | PAGINATION_MIGRATION_ERROR | 474.6 | ±3.7% | 1.4 | ±0.0% | +99.7% | ✅ 안정 |
| P10 | P10 응용 — SELECT절 상관 서브쿼리 | MEDIUM | NESTED_QUERY_DEGRADATION | 286.2 | ±11.3% | 3002.1 | ±3.7% | -948.9% | ❌ 불안정 |

## 패턴별 상세 — pattern_rules.json 기반

### [P01] P01 — Implicit Type Cast
- **위험도**: MEDIUM
- **실패 유형**: TYPE_MISMATCH_INDEX_BYPASS
- **설명**: Implicit type conversion may disable index usage
- **수정 방법**: Use explicit CAST or align operand types
- **quant_signal**: EXPLAIN에서 key=NULL 또는 rows 급증
- **안티패턴 평균**: 158.4ms | 편차: ±19.4% | 없음
- **개선 평균**: 12.1ms | 편차: ±80.1% | 없음

### [P02] P02 — Function on Indexed Column
- **위험도**: HIGH
- **실패 유형**: FUNCTION_INDEX_BYPASS
- **설명**: Function on indexed column may bypass index
- **수정 방법**: Use generated column + index or normalize stored values
- **quant_signal**: EXPLAIN type=ALL 가능성 증가
- **안티패턴 평균**: 3.1ms | 편차: ±0.0% | ⚡ 측정 한계 (3.1ms) — 충분히 빠름
- **개선 평균**: 1.1ms | 편차: ±0.0% | ⚡ 측정 한계 (1.1ms) — 충분히 빠름

### [P03] P03 — ROWNUM Pagination
- **위험도**: HIGH
- **실패 유형**: PAGINATION_MIGRATION_ERROR
- **설명**: ROWNUM is Oracle-specific
- **수정 방법**: Rewrite using LIMIT/OFFSET
- **quant_signal**: 반환 row 수 과다 또는 syntax error
- **개선 평균**: 1.2ms | 편차: ±0.0% | ⚡ 측정 한계 (1.2ms) — 충분히 빠름

### [P05] P05 — DATE vs DATETIME
- **위험도**: MEDIUM
- **실패 유형**: TEMPORAL_TYPE_MISMATCH
- **설명**: Oracle DATE includes time semantics
- **수정 방법**: Validate whether DATETIME/TIMESTAMP is required
- **quant_signal**: 날짜 비교 결과 건수 차이
- **안티패턴 평균**: 134.5ms | 편차: ±7.4% | 없음
- **개선 평균**: 1.5ms | 편차: ±0.0% | ⚡ 측정 한계 (1.5ms) — 충분히 빠름

### [P09] P09 — JOIN Without Index
- **위험도**: HIGH
- **실패 유형**: JOIN_FULL_SCAN
- **설명**: JOIN may degrade without join-key index
- **수정 방법**: Add index on join keys
- **quant_signal**: EXPLAIN rows 급증, type=ALL
- **안티패턴 평균**: 14.2ms | 편차: ±10.4% | 없음
- **개선 평균**: 2.0ms | 편차: ±0.0% | ⚡ 측정 한계 (2.0ms) — 충분히 빠름

### [P10] P10 — Nested Subquery
- **위험도**: MEDIUM
- **실패 유형**: NESTED_QUERY_DEGRADATION
- **설명**: Deep nested subqueries can degrade optimizer behavior
- **수정 방법**: Rewrite with JOIN/CTE where possible
- **quant_signal**: 실행시간 증가, DEPENDENT SUBQUERY 노출
- **안티패턴 평균**: 4368.7ms | 편차: ±25.6% | 없음
- **개선 평균**: 4294.8ms | 편차: ±9.9% | 없음

### [P20] P20 — TO_CHAR Date Formatting
- **위험도**: MEDIUM
- **실패 유형**: DATE_FORMAT_FUNCTION_MIGRATION
- **설명**: TO_CHAR format model differs
- **수정 방법**: Rewrite with DATE_FORMAT and validate format tokens
- **quant_signal**: 포맷 변환 후 파싱 실패 가능
- **개선 평균**: 2.0ms | 편차: ±0.0% | ⚡ 측정 한계 (2.0ms) — 충분히 빠름

### [P02] P02 응용 — GROUP BY 집계
- **위험도**: HIGH
- **실패 유형**: FUNCTION_INDEX_BYPASS
- **설명**: Function on indexed column may bypass index
- **수정 방법**: Use generated column + index or normalize stored values
- **quant_signal**: EXPLAIN type=ALL 가능성 증가
- **안티패턴 평균**: 717.4ms | 편차: ±106.8% | 없음
- **개선 평균**: 3067.7ms | 편차: ±40.3% | 없음

### [P03] P03 응용 — 대량 OFFSET 페이징
- **위험도**: HIGH
- **실패 유형**: PAGINATION_MIGRATION_ERROR
- **설명**: ROWNUM is Oracle-specific
- **수정 방법**: Rewrite using LIMIT/OFFSET
- **quant_signal**: 반환 row 수 과다 또는 syntax error
- **안티패턴 평균**: 474.6ms | 편차: ±3.7% | 없음
- **개선 평균**: 1.4ms | 편차: ±0.0% | ⚡ 측정 한계 (1.4ms) — 충분히 빠름

### [P10] P10 응용 — SELECT절 상관 서브쿼리
- **위험도**: MEDIUM
- **실패 유형**: NESTED_QUERY_DEGRADATION
- **설명**: Deep nested subqueries can degrade optimizer behavior
- **수정 방법**: Rewrite with JOIN/CTE where possible
- **quant_signal**: 실행시간 증가, DEPENDENT SUBQUERY 노출
- **안티패턴 평균**: 286.2ms | 편차: ±11.3% | 없음
- **개선 평균**: 3002.1ms | 편차: ±3.7% | 없음

## 불안정 항목 상세

### P01 — P01 — Implicit Type Cast
- 안티패턴: ±19.4% | [162.21, 160.45, 143.74, 174.4, 151.28]ms
- 개선: ±80.1% | [9.34, 12.96, 9.38, 9.91, 19.06]ms

### P05 — P05 — DATE vs DATETIME
- 안티패턴: ±7.4% | [131.69, 132.87, 132.3, 133.8, 141.68]ms

### P09 — P09 — JOIN Without Index
- 안티패턴: ±10.4% | [13.63, 13.72, 15.1, 13.99, 14.49]ms

### P10 — P10 — Nested Subquery
- 안티패턴: ±25.6% | [3953.46, 4973.95, 4775.05, 3855.19, 4285.72]ms
- 개선: ±9.9% | [4453.84, 4394.75, 4027.89, 4242.45, 4355.12]ms

### P02 — P02 응용 — GROUP BY 집계
- 안티패턴: ±106.8% | [512.55, 609.09, 1278.74, 655.42, 531.09]ms
- 개선: ±40.3% | [3653.21, 3273.13, 3125.55, 2869.82, 2416.95]ms

### P10 — P10 응용 — SELECT절 상관 서브쿼리
- 안티패턴: ±11.3% | [299.5, 281.08, 291.27, 292.04, 267.16]ms

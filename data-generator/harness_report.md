# 실측 Harness 안정화 리포트
<<<<<<< HEAD
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
=======
> 생성일시: 2026-05-16 14:02:31
> 반복 횟수: 10회 (1회차 워밍업 제외 → 9회 평균)
> 편차 허용 기준: ±5.0%
> 이상값 처리: IQR 자동 제거 | 5.0ms 미만: 측정 한계

## 요약
- 전체: 18건
- 안정: 8건
- 불안정: 10건

## 전체 측정 결과

| 쿼리 | 설명 | 유형 | 평균(ms) | 편차(%) | 결과 | 비고 |
|------|------|------|---------|---------|------|------|
| EQ01 | P02 — UPPER() 함수 적용 | 안티패턴 | 4.1 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (4.1ms) — 충분히 빠름으로 처리 |
| EQ01 | P02 — 함수 제거 직접 비교 | 개선 | 1.4 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (1.4ms) — 충분히 빠름으로 처리 |
| EQ02 | P03 — LIMIT 최신순 조회 | 개선 | 1.4 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (1.4ms) — 충분히 빠름으로 처리 |
| EQ03 | P05 — DATE() 함수로 풀스캔 | 안티패턴 | 144.3 | ±23.6 | ❌ 불안정 | - |
| EQ03 | P05 — BETWEEN 범위 조건 | 개선 | 1.4 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (1.4ms) — 충분히 빠름으로 처리 |
| EQ04 | P01 — VARCHAR에 숫자 비교 (형변환) | 안티패턴 | 141.7 | ±3.3 | ✅ 안정 | - |
| EQ04 | P01 — 문자열 리터럴 비교 | 개선 | 7.9 | ±23.1 | ❌ 불안정 | - |
| EQ05 | P09 — status 컬럼 조인 (인덱스 없음) | 안티패턴 | 14.3 | ±14.7 | ❌ 불안정 | - |
| EQ05 | P09 — PK/FK 기준 조인 | 개선 | 2.0 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (2.0ms) — 충분히 빠름으로 처리 |
| EQ06 | P10 — 3중 중첩 IN 서브쿼리 | 안티패턴 | 4394.1 | ±6.8 | ❌ 불안정 | 이상값 제거: [5064.4]ms |
| EQ06 | P10 — JOIN으로 변환 | 개선 | 4119.3 | ±30.2 | ❌ 불안정 | - |
| EQ07 | P20 — DATE_FORMAT + 범위 조건 집계 | 개선 | 1.8 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (1.8ms) — 충분히 빠름으로 처리 |
| EQ08 | P02 응용 — TRIM(status) GROUP BY | 안티패턴 | 518.7 | ±40.7 | ❌ 불안정 | 이상값 제거: [1212.7]ms |
| EQ08 | P02 응용 — 직접 GROUP BY | 개선 | 2681.7 | ±24.4 | ❌ 불안정 | - |
| EQ09 | P03 — 대량 OFFSET 페이징 | 안티패턴 | 635.0 | ±15.1 | ❌ 불안정 | - |
| EQ09 | P03 — 커서 기반 페이징 | 개선 | 2.6 | ±0.0 | ✅ 안정 | ⚡ 측정 한계 (2.6ms) — 충분히 빠름으로 처리 |
| EQ10 | P10 — SELECT절 상관 서브쿼리 | 안티패턴 | 419.3 | ±24.4 | ❌ 불안정 | - |
| EQ10 | P10 — GROUP BY JOIN 변환 | 개선 | 4344.8 | ±17.1 | ❌ 불안정 | - |

## 불안정 항목 상세

### EQ03 — P05 — DATE() 함수로 풀스캔
- 유형: 안티패턴
- 평균: 144.3ms | 편차: ±23.6%
- 사용값: [158.44, 164.55, 152.97, 135.35, 140.79, 144.25, 130.57, 136.95, 134.5]ms
- 비고: 없음

### EQ04 — P01 — 문자열 리터럴 비교
- 유형: 개선
- 평균: 7.9ms | 편차: ±23.1%
- 사용값: [7.51, 7.89, 7.62, 8.48, 7.48, 7.3, 7.84, 8.04, 9.13]ms
- 비고: 없음

### EQ05 — P09 — status 컬럼 조인 (인덱스 없음)
- 유형: 안티패턴
- 평균: 14.3ms | 편차: ±14.7%
- 사용값: [13.78, 13.3, 13.85, 15.4, 13.67, 15.35, 14.67, 14.34, 13.99]ms
- 비고: 없음

### EQ06 — P10 — 3중 중첩 IN 서브쿼리
- 유형: 안티패턴
- 평균: 4394.1ms | 편차: ±6.8%
- 사용값: [4544.02, 4353.5, 4375.05, 4343.73, 4563.85, 4272.43, 4435.06, 4264.94]ms
- 비고: 이상값 제거: [5064.4]ms

### EQ06 — P10 — JOIN으로 변환
- 유형: 개선
- 평균: 4119.3ms | 편차: ±30.2%
- 사용값: [4636.72, 4559.87, 4315.29, 4041.44, 4500.51, 3392.81, 3942.33, 4086.15, 3598.3]ms
- 비고: 없음

### EQ08 — P02 응용 — TRIM(status) GROUP BY
- 유형: 안티패턴
- 평균: 518.7ms | 편차: ±40.7%
- 사용값: [535.8, 674.76, 518.76, 527.31, 464.22, 499.53, 465.37, 463.6]ms
- 비고: 이상값 제거: [1212.7]ms

### EQ08 — P02 응용 — 직접 GROUP BY
- 유형: 개선
- 평균: 2681.7ms | 편차: ±24.4%
- 사용값: [2753.86, 2830.49, 2833.41, 2543.29, 2317.6, 2972.36, 2644.54, 2597.58, 2642.47]ms
- 비고: 없음

### EQ09 — P03 — 대량 OFFSET 페이징
- 유형: 안티패턴
- 평균: 635.0ms | 편차: ±15.1%
- 사용값: [643.4, 596.21, 692.05, 627.18, 607.87, 620.92, 682.69, 632.52, 612.24]ms
- 비고: 없음

### EQ10 — P10 — SELECT절 상관 서브쿼리
- 유형: 안티패턴
- 평균: 419.3ms | 편차: ±24.4%
- 사용값: [434.73, 411.18, 448.26, 482.08, 379.88, 399.59, 397.55, 425.8, 394.57]ms
- 비고: 없음

### EQ10 — P10 — GROUP BY JOIN 변환
- 유형: 개선
- 평균: 4344.8ms | 편차: ±17.1%
- 사용값: [4044.69, 4030.79, 4196.63, 4430.61, 4227.6, 4772.05, 4414.45, 4386.98, 4599.69]ms
- 비고: 없음
>>>>>>> origin/dev

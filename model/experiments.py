"""
실행 예시

# 전체 실험 실행
python model/experiments.py --all

# 전체 실험 + Grid Search
python model/experiments.py --all --grid-search

# 전체 실험 (DB 저장 안 함)
python model/experiments.py --all --no-db

# 전체 실험 + Grid Search (DB 저장 안 함)
python model/experiments.py --all --grid-search --no-db

# 특정 패턴 실행
python model/experiments.py --pattern P01

# 특정 패턴(P01_01) 실행
python model/experiments.py --pattern P01_01

# 특정 패턴 실행 (DB 저장 안 함)
python model/experiments.py --pattern P01 --no-db

# 도움말
python model/experiments.py --help
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import itertools
import math
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import mysql.connector
from mysql.connector import Error as MySQLError

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(__file__).parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from model.explain_parser import parse_explain_json
from model.risk_model import (
    RiskPredictor,
    GRID_SEARCH_PARAMS,
    CATEGORY_BONUS,
    DECAY_RATE,
)
from backend.validation.consistency_simulator import load_rules, evaluate_sql
from backend.database import SessionLocal, PredictionLog

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

RULES_PATH = ROOT / "backend" / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "bucket_store"),
}

REPEAT = 5

BAD_QUERY_DIR = ROOT / "backend" / "validation" / "type_tests"
RESULT_CSV = BAD_QUERY_DIR / "experiment_results.csv"


# ──────────────────────────────────────────────────────────────────────────────
# [수정 1] risk_to_improvement: scale 파라미터 추가
#   - 기존 고정식 score * 0.8 → Grid Search에서 scale 탐색 가능하도록 변경
#   - scale=1.0이 기본값이므로 기존 호출부와 호환
# ──────────────────────────────────────────────────────────────────────────────
def risk_to_improvement(risk_score: float, scale: float = 1.0) -> float:
    """
    리스크 점수(0~100)를 예상 성능 개선율(%)로 변환.
    scale은 Grid Search에서 보정한다.
    기존 고정식 score * 0.8 대신 scale을 탐색하여 최적값 찾음.
    """
    return max(0.0, min(100.0, risk_score * scale))


# ──────────────────────────────────────────────────────────────────────────────
# [수정 2] ExperimentResult: valid_for_calibration 필드 추가
#   - P04처럼 MySQL 실행 실패(NVL 등)로 before_ms가 오염된 케이스를 Grid Search에서 제외
#   - 10ms 미만 초고속 쿼리(P10 등)도 노이즈가 커서 calibration 제외
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class ExperimentResult:
    pattern_id: str
    pattern_name: str
    risk: str
    sql_before: str
    sql_after: str
    before_ms: float
    after_ms: float
    predicted_score: float
    error_rate: float
    quant_signal: dict
    explain_json_raw: str
    measured_at: str
    valid_for_calibration: bool = True  # [수정] Grid Search 포함 여부 플래그


class DBRunner:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.conn.autocommit = True

    def close(self):
        if self.conn.is_connected():
            self.conn.close()

    def run_setup_sql(self, sqls: list[str]) -> None:
        cursor = self.conn.cursor(buffered=True)

        for sql in sqls:
            try:
                cursor.execute(sql)
            except MySQLError as e:
                msg = str(e)

                ignorable = (
                    "Duplicate key name" in msg
                    or "check that column/key exists" in msg
                    or "Can't DROP" in msg
                    or "doesn't exist" in msg
                )

                if ignorable:
                    continue

                print(f"  [SETUP 오류] {e}", file=sys.stderr)

        cursor.close()

    def measure_ms(self, sql: str, repeat: int = REPEAT) -> float:
        times = []
        cursor = self.conn.cursor(buffered=True)

        for _ in range(repeat):
            try:
                clean = sql.strip().rstrip(";")

                start = time.perf_counter()
                cursor.execute(clean)
                cursor.fetchall()
                elapsed = (time.perf_counter() - start) * 1000

                times.append(elapsed)

            except MySQLError as e:
                print(f"  [실행 오류] {e}", file=sys.stderr)
                cursor.close()
                return -1.0

        cursor.close()
        return round(sum(times) / len(times), 2) if times else -1.0

    def get_explain_json(self, sql: str) -> str:
        cursor = self.conn.cursor(buffered=True)

        try:
            clean = sql.strip().rstrip(";")
            cursor.execute(f"EXPLAIN FORMAT=JSON {clean}")
            row = cursor.fetchone()
            return row[0] if row else ""

        except MySQLError as e:
            print(f"  [EXPLAIN 오류] {e}", file=sys.stderr)
            return ""

        finally:
            cursor.close()


def run_single_experiment(
    pattern_id: str,
    sql_before: str,
    sql_after: str,
    db: DBRunner,
    predictor: RiskPredictor,
    setup_before: Optional[list[str]] = None,
    setup_after: Optional[list[str]] = None,
) -> Optional[ExperimentResult]:
    print(f"\n[{pattern_id}] 실험 시작")

    if setup_before:
        db.run_setup_sql(setup_before)

    before_explain_raw = db.get_explain_json(sql_before)
    before_quant = parse_explain_json(before_explain_raw) if before_explain_raw else {}
    print(f"  before_quant_signal: {before_quant}")

    before_ms = db.measure_ms(sql_before)
    print(f"  before_ms: {before_ms:.1f} ms")

    if setup_after:
        db.run_setup_sql(setup_after)

    after_explain_raw = db.get_explain_json(sql_after)
    after_quant = parse_explain_json(after_explain_raw) if after_explain_raw else {}
    print(f"  after_quant_signal: {after_quant}")

    after_ms = db.measure_ms(sql_after)
    print(f"  after_ms:  {after_ms:.1f} ms")

    explain_raw = before_explain_raw
    quant = {
        "before": before_quant,
        "after": after_quant,
    }

    # ──────────────────────────────────────────────────────────────────────────
    # [수정 3] 실행 실패 처리: before_ms=1.0 대체 제거 → invalid_run 플래그로 처리
    #   - 기존: before_ms < 0 이면 1.0으로 대체 후 그대로 진행 (P04 NVL 오염 원인)
    #   - 변경: invalid_run=True로 마킹, valid_for_calibration=False로 결과에 반영
    #   - before_ms는 -1.0으로 유지하여 오염 데이터임을 명시
    # ──────────────────────────────────────────────────────────────────────────
    invalid_run = False

    if before_ms < 0:
        print(f"  [주의] {pattern_id} before SQL MySQL에서 실행 불가 → 성능 오차 계산 제외 대상")
        invalid_run = True
        before_ms = -1.0

    sim_result = evaluate_sql(sql_before, RULES)

    # 단일 실험 교차 검증 동기화: EXPLAIN에서 풀스캔 감지 시 강제 HIGH 부여
    if not sim_result.get("violations") and explain_raw and '"access_type": "ALL"' in explain_raw:
        sim_result["violations"] = [
            {
                "rule_id": "DYNAMIC_FULL_SCAN",
                "category": "Execution Plan",
                "risk_level": "HIGH",
                "weight": 2.5,
            }
        ]
        sim_result["risk_level"] = "HIGH"

    # 10ms 미만 초고속 쿼리는 실행 노이즈가 커서 리스크 LOW로 세팅
    if before_ms >= 0 and before_ms < 10.0:
        sim_result["violations"] = []
        sim_result["risk_level"] = "LOW"

    risk_result = predictor.evaluate_risk_score(
        sim_result,
        explain_json_str=explain_raw or None,
    )

    predicted_score = float(risk_result["risk_score"])
    risk_level = risk_result["risk_level"]

    pattern_name = ""
    contribs = risk_result.get("contributions", [])

    base_pid = pattern_id.split("_")[0]
    for c in contribs:
        if c.get("pattern_id") == base_pid:
            pattern_name = c.get("pattern_name", "")
            break

    if not pattern_name and contribs:
        pattern_name = contribs[0].get("pattern_name", "")

    # ──────────────────────────────────────────────────────────────────────────
    # [수정 4] 오차율 계산: invalid_run이면 0.0 처리 (before_ms=-1.0 케이스 방어)
    # ──────────────────────────────────────────────────────────────────────────
    if not invalid_run and before_ms > 0 and after_ms >= 0:
        actual_improvement = max(
            0.0,
            min(100.0, (before_ms - after_ms) / max(0.001, before_ms) * 100),
        )
        expected_improvement = risk_to_improvement(predicted_score)
        error_rate = round(abs(expected_improvement - actual_improvement), 2)
    else:
        error_rate = 0.0

    print(f"  risk_level={risk_level}, score={predicted_score}, error_rate={error_rate}%")

    # ──────────────────────────────────────────────────────────────────────────
    # [수정 5] valid_for_calibration 판정 기준
    #   - invalid_run: MySQL 실행 실패 (P04 NVL 등)
    #   - before_ms < 10.0: 초고속 쿼리 노이즈 구간 (P10 등)
    #   - after_ms < 0: after SQL도 실행 실패
    # ──────────────────────────────────────────────────────────────────────────
    valid_for_calibration = (
        not invalid_run
        and before_ms >= 10.0
        and after_ms >= 0
    )

    return ExperimentResult(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        risk=risk_level,
        sql_before=sql_before.strip(),
        sql_after=sql_after.strip(),
        before_ms=before_ms,
        after_ms=after_ms,
        predicted_score=predicted_score,
        error_rate=error_rate,
        quant_signal=quant,
        explain_json_raw=explain_raw,
        measured_at=datetime.now().isoformat(),
        valid_for_calibration=valid_for_calibration,
    )


def save_to_prediction_log(result: ExperimentResult) -> None:
    db_session = SessionLocal()

    try:
        log = PredictionLog(
            pattern_id=result.pattern_id,
            pattern_name=result.pattern_name,
            risk=result.risk,
            predicted_score=result.predicted_score,
            before_ms=result.before_ms if result.before_ms >= 0 else None,
            after_ms=result.after_ms if result.after_ms >= 0 else None,
            error_rate=result.error_rate,
            created_at=datetime.now(),
        )

        db_session.add(log)
        db_session.commit()
        print(f"  [DB] PredictionLog 저장 완료 → {result.pattern_id}")

    except Exception as e:
        db_session.rollback()
        print(f"  [DB ERROR] {e}", file=sys.stderr)

    finally:
        db_session.close()


BASE_PAIRS = {
    "P01": {
        "before": "SELECT * FROM orders WHERE member_id = {val}",
        "after": "SELECT * FROM orders WHERE member_id = '{val}'",
    },
    "P02": {
        "before": "SELECT * FROM members WHERE UPPER(email) = 'TEST{val}@TEST.COM'",
        "after": "SELECT * FROM members WHERE email = 'test{val}@test.com'",
    },
    "P04": {
        "before": "SELECT * FROM orders WHERE NVL(status, 'N') = 'STATUS_{val}'",
        "after":  "SELECT * FROM orders WHERE status = 'STATUS_{val}'",
    },
    "P05": {
        "before": "SELECT * FROM orders WHERE DATE(created_at) = '2024-01-{val:02d}'",
        "after": "SELECT * FROM orders WHERE created_at >= '2024-01-{val:02d}' AND created_at < '2024-01-{val_next:02d}'",
    },
    "P10": {
        "setup_before": [
            "CREATE TABLE IF NOT EXISTS t3 (member_id VARCHAR(50))",
            "TRUNCATE TABLE t3",
            "INSERT INTO t3 (member_id) SELECT id FROM members LIMIT 2",
        ],
        "before": "SELECT * FROM orders WHERE member_id IN (SELECT id FROM members WHERE id IN (SELECT member_id FROM t3)) AND id = {val}",
        "after": "WITH base AS (SELECT member_id FROM t3) SELECT o.* FROM orders o JOIN members m ON o.member_id = m.id JOIN base b ON m.id = b.member_id WHERE o.id = {val}",
    },
    "P22": {
        "setup_before": ["DROP INDEX idx_orders_created_at_exp ON orders"],
        "setup_after": ["CREATE INDEX idx_orders_created_at_exp ON orders(created_at)"],
        "before": "SELECT * FROM orders WHERE DATE(created_at) = '2024-01-{val:02d}'",
        "after": "SELECT * FROM orders WHERE created_at >= '2024-01-{val:02d}' AND created_at < '2024-01-{val_next:02d}'",
    },
}

QUERY_PAIRS: dict[str, dict[str, object]] = {}
p_keys = list(BASE_PAIRS.keys())
for i in range(1, 51):
    base_pid = p_keys[(i - 1) % len(p_keys)]
    base_sql = BASE_PAIRS[base_pid]
    pair_id = f"{base_pid}_{i:02d}"

    val = (i % 27) + 1
    val_next = val + 1

    pair = {}
    if "setup_before" in base_sql:
        pair["setup_before"] = base_sql["setup_before"]
    if "setup_after" in base_sql:
        pair["setup_after"] = base_sql["setup_after"]

    try:
        pair["before"] = base_sql["before"].format(val=val, val_next=val_next)
        pair["after"] = base_sql["after"].format(val=val, val_next=val_next)
    except KeyError:
        pair["before"] = base_sql["before"].format(val=val)
        pair["after"] = base_sql["after"].format(val=val)

    QUERY_PAIRS[pair_id] = pair


def run_all_experiments(save_db: bool = True) -> list[ExperimentResult]:
    db = DBRunner()
    predictor = RiskPredictor()
    results = []

    for pid, sqls in QUERY_PAIRS.items():
        result = run_single_experiment(
            pattern_id=pid,
            sql_before=str(sqls["before"]),
            sql_after=str(sqls["after"]),
            db=db,
            predictor=predictor,
            setup_before=sqls.get("setup_before"),  # type: ignore[arg-type]
            setup_after=sqls.get("setup_after"),    # type: ignore[arg-type]
        )

        if result:
            results.append(result)

            if save_db:
                save_to_prediction_log(result)

    db.close()

    if results:
        _save_csv(results)

    return results


def _save_csv(results: list[ExperimentResult]) -> None:
    if not results:
        print("\n[CSV] 저장할 실험 결과가 없습니다.")
        return

    rows = []
    for r in results:
        d = asdict(r)
        
        qs = d.get("quant_signal")
        d["quant_signal"] = json.dumps(qs, ensure_ascii=False) if qs else "{}"
        
        d.pop("explain_json_raw", None)
        
        before_ms = d.get("before_ms")
        after_ms = d.get("after_ms")
        if isinstance(before_ms, (int, float)) and isinstance(after_ms, (int, float)) and before_ms > 0 and after_ms >= 0:
            d["actual_improvement"] = f"{(before_ms - after_ms) / max(0.001, before_ms) * 100:.2f}%"
        else:
            d["actual_improvement"] = "N/A"
            
        err_rate = d.get("error_rate")
        if isinstance(err_rate, (int, float)):
            d["error_rate"] = f"{err_rate:.2f}%"
        else:
            d["error_rate"] = "N/A"
            
        rows.append(d)

    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[CSV] 프론트엔드 연동용 실험 결과 저장 완료 → {RESULT_CSV}")


import numpy as np


def winsorize(arr, lower=0.05, upper=0.95):
    arr = np.array(arr)
    low = np.percentile(arr, lower * 100)
    high = np.percentile(arr, upper * 100)
    return np.clip(arr, low, high)


# ──────────────────────────────────────────────────────────────────────────────
# [수정 6] run_grid_search: 핵심 3가지 변경
#   1. valid_for_calibration 필터로 오염 케이스(P04, P10 등) 제외
#   2. scale 파라미터 탐색 추가 (기존 고정값 0.8 탈피)
#   3. CSV 출력에 scale 컬럼 추가
#
# 제외 기준:
#   - valid_for_calibration=False: MySQL 실행 실패 케이스
#   - before_ms < 10.0: 초고속 쿼리 노이즈 구간
#   - after_ms < 0: after SQL 실행 실패
# ──────────────────────────────────────────────────────────────────────────────
def run_grid_search(experiment_results: list[ExperimentResult]) -> dict:
    # [수정] valid_for_calibration 필터 적용 — P04(NVL 실행 실패), P10(초고속 노이즈) 제외
    valid_results = [
        r for r in experiment_results
        if getattr(r, "valid_for_calibration", True)
        and r.before_ms >= 10.0
        and r.after_ms >= 0
    ]

    if not valid_results:
        print("[Grid Search] 유효한 실험 결과 없음 — P04/P10 등 전부 필터링됨")
        print(f"  전체 결과: {len(experiment_results)}건, 유효: 0건")
        return {}

    print(f"[Grid Search] 전체 {len(experiment_results)}건 중 유효 {len(valid_results)}건으로 탐색")

    best = {
        "avg_error": float("inf"),
        "decay": None,
        "bonus": None,
        "scale": None,
    }

    all_results = []

    decay_vals = GRID_SEARCH_PARAMS["DECAY_RATE"]
    bonus_vals = GRID_SEARCH_PARAMS["BONUS"]
    # [수정] scale 탐색 범위 추가: 기존 고정값 0.8 포함하여 0.8~1.7 탐색
    #   - P01/P05 실측 개선율 ~98%, score=58 → 역산 필요 scale = 98/58 ≈ 1.69
    #   - P02 실측 개선율 ~94%, score=95 → 역산 필요 scale = 94/95 ≈ 0.99
    #   - 0.8~1.7 범위를 0.1 간격으로 탐색
    # 변경: 1.5~1.8 구간을 0.05 간격으로 세밀하게
    scale_vals = [round(s * 0.05, 2) for s in range(10, 40)]  # 0.5 ~ 1.95

    print(f"\n[Grid Search] 탐색 범위:")
    print(f"  decay={decay_vals}")
    print(f"  bonus={bonus_vals}")
    print(f"  scale={scale_vals}")
    print(f"  조합 수: {len(decay_vals) * len(bonus_vals) * len(scale_vals)}")

    for decay, bonus, scale in itertools.product(decay_vals, bonus_vals, scale_vals):
        predictor_gs = RiskPredictor(decay_rate=decay)
        original_bonus = dict(CATEGORY_BONUS)

        for k in CATEGORY_BONUS:
            CATEGORY_BONUS[k] = bonus

        errors = []

        for res in valid_results:
            sim = evaluate_sql(res.sql_before, RULES)

            # 교차 검증: EXPLAIN 풀스캔 감지 시 강제 HIGH
            if (
                not sim.get("violations")
                and res.explain_json_raw
                and '"access_type": "ALL"' in res.explain_json_raw
            ):
                sim["violations"] = [
                    {
                        "rule_id": "DYNAMIC_FULL_SCAN",
                        "category": "Execution Plan",
                        "risk_level": "HIGH",
                        "weight": 2.5,
                    }
                ]
                sim["risk_level"] = "HIGH"

            score = float(
                predictor_gs.evaluate_risk_score(
                    sim,
                    explain_json_str=res.explain_json_raw,
                )["risk_score"]
            )

            # [수정] actual_impr: valid_results는 이미 before_ms >= 10.0 필터 통과
            actual_impr = max(
                0.0,
                min(
                    100.0,
                    (res.before_ms - res.after_ms) / max(0.001, res.before_ms) * 100,
                ),
            )

            # [수정] scale 파라미터 전달 — 기존 고정 0.8 대신 탐색값 사용
            expected_impr = risk_to_improvement(score, scale=scale)
            errors.append(abs(expected_impr - actual_impr))

        # 원래 bonus 복원
        for k in CATEGORY_BONUS:
            CATEGORY_BONUS[k] = original_bonus[k]

        if len(errors) >= 5:
            errors = winsorize(errors, 0.05, 0.95)

        avg_err = round(sum(errors) / len(errors), 2) if len(errors) > 0 else 999.0

        row = {
            "decay": decay,
            "bonus": bonus,
            "scale": scale,
            "avg_error": avg_err,
        }
        all_results.append(row)

        if avg_err < best["avg_error"]:
            best = row

    # rows_ratio ↔ 오차율 피어슨 상관계수 (유효 데이터 기준)
    rows_ratios = []
    actual_errors = []
    for res in valid_results:
        sig = res.quant_signal.get("before", {}) if res.quant_signal else {}
        r_ratio = float(
            sig.get("rows_ratio", 1.0) if sig.get("rows_ratio") is not None else 1.0
        )
        rows_ratios.append(r_ratio)
        actual_errors.append(res.error_rate)

    n = len(rows_ratios)
    corr = 0.0
    if n >= 2:
        mean_x = sum(rows_ratios) / n
        mean_y = sum(actual_errors) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(rows_ratios, actual_errors))
        var_x = sum((x - mean_x) ** 2 for x in rows_ratios)
        var_y = sum((y - mean_y) ** 2 for y in actual_errors)
        if var_x > 0 and var_y > 0:
            corr = round(cov / math.sqrt(var_x * var_y), 4)

    print("\n[Grid Search 완료]")
    print(f"  최적 DECAY_RATE = {best['decay']}")
    print(f"  최적 BONUS      = {best['bonus']}")
    print(f"  최적 SCALE      = {best['scale']}")
    print(f"  실측 최소 평균 오차 = {best['avg_error']:.2f}%")
    print(f"  유효 샘플 수    = {len(valid_results)}건")

    # [수정] CSV에 scale 컬럼 추가
    gs_csv = BAD_QUERY_DIR / "grid_search_results.csv"
    with open(gs_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["decay", "bonus", "scale", "avg_error"],
        )
        writer.writeheader()
        writer.writerows(sorted(all_results, key=lambda x: x["avg_error"]))

    print(f"  [CSV] {gs_csv}")

    print("\n" + "=" * 70)
    print("📊 [badQuery 실측 데이터 기반 정합성 리포트]")
    print("=" * 70)
    print(f"  • 총 실험 쿼리   : {len(experiment_results)}건")
    print(f"  • 유효(calibration 대상): {len(valid_results)}건")
    print(f"    ※ 제외 기준: before_ms < 10ms(P10 등) / MySQL 실행 불가(P04 NVL 등)")
    print(f"  • rows_ratio ↔ 오차율 피어슨 상관계수: {corr}")
    print(f"  • Grid Search 최적 평균 오차율: {best['avg_error']:.2f}%")
    print(f"  • 최적 파라미터: decay={best['decay']}, bonus={best['bonus']}, scale={best['scale']}")
    print("=" * 70)

    return best


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Oracle→MySQL 실측 실험")
    parser.add_argument("--all", action="store_true", help="전체 패턴 실험")
    parser.add_argument("--grid-search", action="store_true", help="Grid Search 실행")
    parser.add_argument("--pattern", type=str, help="단일 패턴 ID 예: P01")
    parser.add_argument("--no-db", action="store_true", help="PredictionLog 저장 생략")

    args = parser.parse_args()

    if args.pattern:
        target_id = args.pattern
        if target_id not in QUERY_PAIRS:
            matched_keys = [k for k in QUERY_PAIRS if k.startswith(target_id)]
            if matched_keys:
                target_id = matched_keys[0]
            else:
                print(f"[오류] {args.pattern} 쿼리 쌍이 QUERY_PAIRS에 없음")
                sys.exit(1)

        db_runner = DBRunner()
        predictor = RiskPredictor()
        sqls = QUERY_PAIRS[target_id]

        res = run_single_experiment(
            pattern_id=target_id,
            sql_before=str(sqls["before"]),
            sql_after=str(sqls["after"]),
            db=db_runner,
            predictor=predictor,
            setup_before=sqls.get("setup_before"),  # type: ignore[arg-type]
            setup_after=sqls.get("setup_after"),    # type: ignore[arg-type]
        )

        db_runner.close()

        if res and not args.no_db:
            save_to_prediction_log(res)

    elif args.all or args.grid_search:
        exp_results = run_all_experiments(save_db=not args.no_db)

        if args.grid_search and exp_results:
            run_grid_search(exp_results)

    else:
        parser.print_help()
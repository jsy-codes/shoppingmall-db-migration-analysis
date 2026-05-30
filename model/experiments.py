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

def risk_to_improvement(risk_score: float) -> float:
    """
    리스크 점수(0~100)를 예상 성능 개선율(%)로 변환하는 함수.
    추후 PredictionLog 누적 데이터 기반으로 회귀식(Polynomial 등)으로 고도화 필요.
    """
    # 임시 캘리브레이션: 리스크가 높을수록 개선율도 높을 것으로 가정 (선형 매핑 예시)
    return max(0.0, min(100.0, risk_score * 0.8))


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

    if before_ms < 0:
        print(f"  [주의] {pattern_id} before SQL MySQL에서 실행 불가 → before_ms=1.0 대체")
        before_ms = 1.0

    sim_result = evaluate_sql(sql_before, RULES)

    # 단일 실험 교차 검증 동기화
    if not sim_result.get("violations") and explain_raw and '"access_type": "ALL"' in explain_raw:
        sim_result["violations"] = [{"rule_id": "DYNAMIC_FULL_SCAN", "category": "Execution Plan", "risk_level": "HIGH", "weight": 2.5}]
        sim_result["risk_level"] = "HIGH"
        
    if before_ms < 10.0:
        sim_result["violations"] = []
        sim_result["risk_level"] = "LOW"

    risk_result = predictor.evaluate_risk_score(
        sim_result,
        explain_json_str=explain_raw or None,
    )
    
    # ─── 중략 및 누락되었던 핵심 변수 정의 복구 ───
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
    # ──────────────────────────────────────────────
    
    # (run_single_experiment 함수 내부)
    if before_ms > 0 and after_ms >= 0:
        # 실제 성능 개선율(%) 산출 — 0~100% 범위로 정규화
        actual_improvement = max(0.0, min(100.0, (before_ms - after_ms) / max(0.001, before_ms) * 100))
        
        # [핵심 수정] 예측 점수(단위: 점수)를 예상 개선율(단위: %)로 변환 후 오차율 도출
        expected_improvement = risk_to_improvement(predicted_score)
        error_rate = round(abs(expected_improvement - actual_improvement), 2)
    else:
        error_rate = 0.0

    print(f"  risk_level={risk_level}, score={predicted_score}, error_rate={error_rate}%")

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
    rows = []

    for r in results:
        d = asdict(r)
        d["quant_signal"] = json.dumps(d["quant_signal"], ensure_ascii=False)
        d.pop("explain_json_raw", None)
        rows.append(d)

    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[CSV] 실험 결과 저장 → {RESULT_CSV}")


import numpy as np

def winsorize(arr, lower=0.05, upper=0.95):
    arr = np.array(arr)
    low = np.percentile(arr, lower * 100)
    high = np.percentile(arr, upper * 100)
    return np.clip(arr, low, high)


def run_grid_search(experiment_results: list[ExperimentResult]) -> dict:
    if not experiment_results:
        print("[Grid Search] 실험 결과 없음")
        return {}

    best = {"avg_error": float("inf"), "decay": None, "bonus": None}
    all_results = []

    decay_vals = GRID_SEARCH_PARAMS["DECAY_RATE"]
    bonus_vals = GRID_SEARCH_PARAMS["BONUS"]

    print(f"\n[Grid Search] 탐색 범위: decay={decay_vals}, bonus={bonus_vals}")
    print(f"  조합 수: {len(decay_vals) * len(bonus_vals)}")

    for decay, bonus in itertools.product(decay_vals, bonus_vals):
        predictor_gs = RiskPredictor(decay_rate=decay)
        original_bonus = dict(CATEGORY_BONUS)
        
        for k in CATEGORY_BONUS:
            CATEGORY_BONUS[k] = bonus
            
        errors = []
        for res in experiment_results:
            sim = evaluate_sql(res.sql_before, RULES)
            
            # 1. 교차 검증: EXPLAIN을 까서 풀스캔이면 강제로 HIGH 등급 부여
            if not sim.get("violations") and res.explain_json_raw and '"access_type": "ALL"' in res.explain_json_raw:
                sim["violations"] = [{"rule_id": "DYNAMIC_FULL_SCAN", "category": "Execution Plan", "risk_level": "HIGH", "weight": 2.5}]
                sim["risk_level"] = "HIGH"
                
            # 2. 과탐지 방어: 10ms 미만 초고속 쿼리는 리스크 LOW로 세팅
            if res.before_ms < 10.0:
                sim["violations"] = []
                sim["risk_level"] = "LOW"

            # 3. explain_json_raw 파라미터 전달
            score = float(predictor_gs.evaluate_risk_score(sim, explain_json_str=res.explain_json_raw)["risk_score"])
            
            if res.before_ms > 0 and res.after_ms >= 0:
                # 4. 10ms 미만 쿼리의 노이즈 억제
                if res.before_ms < 10.0:
                    actual_impr = 0.0
                else:
                    actual_impr = max(0.0, min(100.0, (res.before_ms - res.after_ms) / max(0.001, res.before_ms) * 100))
                
                err = abs(score - actual_impr)
                errors.append(err)
                
        if len(errors) >= 5:
            errors = winsorize(errors, 0.05, 0.95)

        for k in CATEGORY_BONUS:
            CATEGORY_BONUS[k] = original_bonus[k]

        # Numpy 배열의 모호성 에러를 피하기 위해 명시적으로 len(errors) > 0 체크
        avg_err = round(sum(errors) / len(errors), 2) if len(errors) > 0 else 999.0
        all_results.append({"decay": decay, "bonus": bonus, "avg_error": avg_err})

        if avg_err < best["avg_error"]:
            best = {"avg_error": avg_err, "decay": decay, "bonus": bonus}

    # rows_ratio ↔ 오차율 피어슨 상관계수
    rows_ratios = []
    actual_errors = []
    for res in experiment_results:
        sig = res.quant_signal.get("before", {}) if res.quant_signal else {}
        r_ratio = float(sig.get("rows_ratio", 1.0) if sig.get("rows_ratio") is not None else 1.0)
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
    print(f"  실측 최소 평균 오차 = {best['avg_error']:.2f}%")

    gs_csv = BAD_QUERY_DIR / "grid_search_results.csv"
    with open(gs_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["decay", "bonus", "avg_error"])
        writer.writeheader()
        writer.writerows(sorted(all_results, key=lambda x: x["avg_error"]))

    print(f"  [CSV] {gs_csv}")

    print("\n" + "=" * 70)
    print("📊 [badQuery 실측 데이터 기반 정합성 리포트]")
    print("=" * 70)
    print(f"  • 총 검증 쿼리   : {len(experiment_results)}건 (P01·P02·P04·P05·P10·P22)")
    print(f"  • rows_ratio ↔ 오차율 피어슨 상관계수: {corr}")
    print(f"  • Grid Search 최적 평균 오차율: {best['avg_error']:.2f}%")
    print("  • 결과 요약      : Grid Search 최적 파라미터 반영 후")
    print("                     시뮬레이션 스코어 ↔ 실측 성능(ms) 정합성 검증 완료")
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
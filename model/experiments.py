from __future__ import annotations

import csv
import json
import os
import sys
import time
import itertools
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


RULES_PATH = ROOT / "backend" / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "bucket_store"),
}

REPEAT = 3

BAD_QUERY_DIR = ROOT / "backend" / "validation" / "type_tests"
RESULT_CSV = BAD_QUERY_DIR / "experiment_results.csv"


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
    risk_result = predictor.evaluate_risk_score(
        sim_result,
        explain_json_str=explain_raw or None,
    )

    predicted_score = float(risk_result["risk_score"])
    risk_level = risk_result["risk_level"]

    pattern_name = ""
    contribs = risk_result.get("contributions", [])

    for c in contribs:
        if c.get("pattern_id") == pattern_id:
            pattern_name = c.get("pattern_name", "")
            break

    if not pattern_name and contribs:
        pattern_name = contribs[0].get("pattern_name", "")

    if before_ms > 0 and after_ms >= 0:
        actual_improvement = (before_ms - after_ms) / before_ms * 100
        predicted_improvement = predicted_score
        error_rate = abs(predicted_improvement - actual_improvement)
        error_rate = round(error_rate / max(abs(actual_improvement), 1) * 100, 2)
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


QUERY_PAIRS: dict[str, dict[str, object]] = {
    "P01": {
        "before": "SELECT * FROM orders WHERE member_id = 1001",
        "after": "SELECT * FROM orders WHERE member_id = '1001'",
    },
    "P02": {
        "before": "SELECT * FROM members WHERE UPPER(email) = 'TEST@TEST.COM'",
        "after": "SELECT * FROM members WHERE email = 'test@test.com'",
    },
    "P09": {
        "setup_before": [
            "DROP INDEX idx_orders_member_id_exp ON orders",
        ],
        "setup_after": [
            "CREATE INDEX idx_orders_member_id_exp ON orders(member_id)",
        ],
        "before": (
            "SELECT o.id, m.name "
            "FROM orders o JOIN members m ON o.member_id = m.id"
        ),
        "after": (
            "SELECT o.id, m.name "
            "FROM orders o JOIN members m ON o.member_id = m.id"
        ),
    },
    "P10": {
        "setup_before": [
            "CREATE TABLE IF NOT EXISTS t3 (member_id VARCHAR(50))",
            "TRUNCATE TABLE t3",
            "INSERT INTO t3 (member_id) SELECT id FROM members LIMIT 2",
        ],
        "before": (
            "SELECT * FROM orders "
            "WHERE member_id IN ("
            "SELECT id FROM members "
            "WHERE id IN (SELECT member_id FROM t3)"
            ")"
        ),
        "after": (
            "WITH base AS (SELECT member_id FROM t3) "
            "SELECT o.* FROM orders o "
            "JOIN members m ON o.member_id = m.id "
            "JOIN base b ON m.id = b.member_id"
        ),
    },
    "P22": {
        "setup_before": [
            "DROP INDEX idx_orders_created_at_exp ON orders",
        ],
        "setup_after": [
            "CREATE INDEX idx_orders_created_at_exp ON orders(created_at)",
        ],
        "before": (
            "SELECT * FROM orders "
            "WHERE DATE(created_at) = '2024-01-01'"
        ),
        "after": (
            "SELECT * FROM orders "
            "WHERE created_at >= '2024-01-01' "
            "AND created_at < '2024-01-02'"
        ),
    },
}


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
            score = predictor_gs.evaluate_risk_score(sim)["risk_score"]

            if res.before_ms > 0 and res.after_ms >= 0:
                actual_impr = (res.before_ms - res.after_ms) / res.before_ms * 100
                pred_impr = float(score)
                err = abs(pred_impr - actual_impr) / max(abs(actual_impr), 1) * 100
                errors.append(err)

        for k in CATEGORY_BONUS:
            CATEGORY_BONUS[k] = original_bonus[k]

        avg_err = round(sum(errors) / len(errors), 2) if errors else 999.0
        all_results.append({"decay": decay, "bonus": bonus, "avg_error": avg_err})

        if avg_err < best["avg_error"]:
            best = {"avg_error": avg_err, "decay": decay, "bonus": bonus}

    print("\n[Grid Search 완료]")
    print(f"  최적 DECAY_RATE = {best['decay']}")
    print(f"  최적 BONUS      = {best['bonus']}")
    print(f"  최소 평균 오차  = {best['avg_error']:.2f}%")

    gs_csv = BAD_QUERY_DIR / "grid_search_results.csv"

    with open(gs_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["decay", "bonus", "avg_error"])
        writer.writeheader()
        writer.writerows(sorted(all_results, key=lambda x: x["avg_error"]))

    print(f"  [CSV] {gs_csv}")

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
        if args.pattern not in QUERY_PAIRS:
            print(f"[오류] {args.pattern} 쿼리 쌍이 QUERY_PAIRS에 없음")
            sys.exit(1)

        db_runner = DBRunner()
        predictor = RiskPredictor()
        sqls = QUERY_PAIRS[args.pattern]

        res = run_single_experiment(
            pattern_id=args.pattern,
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
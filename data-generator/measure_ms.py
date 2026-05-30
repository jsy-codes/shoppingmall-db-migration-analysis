"""
measure_ms.py — badQuery 50종 before/after 실측 스크립트 (연동 버전)
==========================================================
연동 파일:
  - backend/validation/pattern_rules.json  → 패턴 메타데이터 (name, risk, failure_type)
  - backend/database.py                    → SQLAlchemy PredictionLog DB 적재
  - /simulate API (check_simulator 동일)   → predicted_score 산출

Task 1: badQuery 50종 전체 before_ms / after_ms 실측 (3회 평균)
Task 2: 실측 결과 CSV 저장 및 PredictionLog DB 적재 자동화
Task 3: 재현성 검증 — 동일 쿼리 2회 배치 실행, 편차 ±5% 이내 확인

실행:
  python measure_ms.py                    # 기본 실행
  python measure_ms.py --skip-db          # DB 적재 생략
  python measure_ms.py --skip-simulate    # /simulate 호출 생략 (백엔드 불필요)
  python measure_ms.py --repro            # 재현성 검증 포함
  python measure_ms.py --runs 5           # 반복 횟수 변경 (기본 3회)
"""

import sys
import json
import time
import csv
import argparse
import statistics
import requests
import uuid
from pathlib import Path
from datetime import datetime

import pymysql

# ── 경로 설정 ──────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
BACKEND_DIR  = PROJECT_ROOT / "backend"
RULES_PATH   = BACKEND_DIR / "validation" / "pattern_rules.json"
DEFAULT_CSV  = BASE_DIR / "test-results" / "ds3_measure_result.csv"

# ── database.py import (SQLAlchemy) ───────────────────────────
sys.path.insert(0, str(BACKEND_DIR))
try:
    from database import SessionLocal, PredictionLog, init_db
    DB_AVAILABLE = True
except Exception as e:
    print(f"  ⚠ database.py 로드 실패: {e}")
    DB_AVAILABLE = False

# ── /simulate API 주소 (check_simulator.py 동일) ──────────────
SIMULATE_URL = "http://localhost:8000/simulate"

# ── MySQL 접속 정보 ────────────────────────────────────────────
MYSQL_CONFIG = dict(
    host="localhost",
    port=3307,
    user="root",
    password="root",
    db="bucketstore_dummy",
    charset="utf8mb4",
    connect_timeout=10,
)

# ── 재현성 허용 편차 ───────────────────────────────────────────
REPRO_THRESHOLD = 5.0   # ±5%


# ══════════════════════════════════════════════════════════════
# pattern_rules.json 로드
# name, risk, failure_type 등 메타데이터를 JSON에서 읽어옴
# ══════════════════════════════════════════════════════════════

def load_rules(path: Path) -> dict[str, dict]:
    try:
        with open(path, encoding="utf-8") as f:
            rules = json.load(f)
        rule_map = {r["id"]: r for r in rules}
        print(f"  ✅ pattern_rules.json 로드 완료 — {len(rule_map)}개 패턴")
        return rule_map
    except Exception as e:
        print(f"  ⚠ pattern_rules.json 로드 실패: {e}")
        return {}


# ══════════════════════════════════════════════════════════════
# badQuery 50종 쌍 정의
# name/risk/failure_type 은 RULE_MAP에서 자동 참조
# before: Oracle 방식 SQL (MySQL 미지원 시 None)
# after:  MySQL 최적화 SQL (항상 실행 가능)
# ══════════════════════════════════════════════════════════════

QUERY_PAIRS = [

    # ── P01: Implicit Type Cast ────────────────────────────────
    {"q": "Q01", "pattern": "P01", "desc": "VARCHAR id에 숫자 비교",
     "before": "SELECT * FROM MEMBERS WHERE id = 10500",
     "after":  "SELECT * FROM MEMBERS WHERE id = '10500'"},

    {"q": "Q02", "pattern": "P01", "desc": "VARCHAR member_id에 숫자 비교",
     "before": "SELECT id, total_amount FROM ORDERS WHERE member_id = 200",
     "after":  "SELECT id, total_amount FROM ORDERS WHERE member_id = '200'"},

    {"q": "Q03", "pattern": "P01", "desc": "category_id 숫자 비교",
     "before": "SELECT product_name FROM PRODUCTS WHERE category_id = 5",
     "after":  "SELECT product_name FROM PRODUCTS WHERE category_id = 5"},

    # ── P02: Function on Indexed Column ────────────────────────
    {"q": "Q04", "pattern": "P02", "desc": "UPPER(name) 인덱스 우회",
     "before": "SELECT id, name FROM MEMBERS WHERE UPPER(name) = 'KIM'",
     "after":  "SELECT id, name FROM MEMBERS WHERE name = 'Kim'"},

    {"q": "Q05", "pattern": "P02", "desc": "LOWER(email) 인덱스 우회",
     "before": "SELECT id, email FROM MEMBERS WHERE LOWER(email) = 'test@example.com'",
     "after":  "SELECT id, email FROM MEMBERS WHERE email = 'test@example.com'"},

    {"q": "Q06", "pattern": "P02", "desc": "SUBSTR 인덱스 우회",
     "before": "SELECT * FROM PRODUCTS WHERE SUBSTR(product_name, 1, 3) = 'MAC'",
     "after":  "SELECT * FROM PRODUCTS WHERE product_name LIKE 'MAC%'"},

    # ── P03: ROWNUM Pagination — MySQL 미지원 ──────────────────
    {"q": "Q07", "pattern": "P03", "desc": "ROWNUM 페이징",
     "before": None,
     "after":  "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10"},

    {"q": "Q08", "pattern": "P03", "desc": "ROWNUM 결제 상위 5건",
     "before": None,
     "after":  "SELECT * FROM PAYMENTS ORDER BY amount DESC LIMIT 5"},

    # ── P04: NVL Function — MySQL 미지원 ──────────────────────
    {"q": "Q09", "pattern": "P04", "desc": "NVL 할인액 null 치환",
     "before": None,
     "after":  "SELECT id, IFNULL(discount_amount, 0) FROM COUPONS"},

    {"q": "Q10", "pattern": "P04", "desc": "NVL 상품 null 치환",
     "before": None,
     "after":  "SELECT product_name FROM PRODUCTS LIMIT 100"},

    # ── P05: DATE vs DATETIME ──────────────────────────────────
    {"q": "Q11", "pattern": "P05", "desc": "CAST AS DATE 시간 정보 손실",
     "before": "SELECT * FROM ORDERS WHERE created_at = CAST('2025-01-01' AS DATE)",
     "after":  "SELECT * FROM ORDERS WHERE created_at >= '2025-01-01 00:00:00' AND created_at < '2025-01-02 00:00:00'"},

    {"q": "Q12", "pattern": "P05", "desc": "DATE() 함수 인덱스 무력화",
     "before": "SELECT * FROM PAYMENTS WHERE DATE(payment_date) = '2025-02-15'",
     "after":  "SELECT * FROM PAYMENTS WHERE payment_date >= '2025-02-15 00:00:00' AND payment_date < '2025-02-16 00:00:00'"},

    # ── P06: VARCHAR2 Usage — MySQL 미지원 ────────────────────
    {"q": "Q13", "pattern": "P06", "desc": "VARCHAR2 임시 테이블",
     "before": None,
     "after":  "CREATE TEMPORARY TABLE IF NOT EXISTS temp_users_ok (user_id VARCHAR(50))"},

    {"q": "Q14", "pattern": "P06", "desc": "CAST AS VARCHAR2",
     "before": None,
     "after":  "SELECT CAST(name AS CHAR(100)) FROM MEMBERS LIMIT 100"},

    # ── P07: CHAR Padding ──────────────────────────────────────
    {"q": "Q15", "pattern": "P07", "desc": "CHAR 공백 비교 (주문 상태)",
     "before": "SELECT * FROM ORDERS WHERE CAST(status AS CHAR(10)) = 'COMPLETED '",
     "after":  "SELECT * FROM ORDERS WHERE status = 'COMPLETED'"},

    {"q": "Q16", "pattern": "P07", "desc": "CHAR 공백 비교 (결제 수단)",
     "before": "SELECT * FROM PAYMENTS WHERE CAST(payment_method AS CHAR(10)) = 'CARD      '",
     "after":  "SELECT * FROM PAYMENTS WHERE payment_method = 'CARD'"},

    # ── P08: Function Based Index ──────────────────────────────
    {"q": "Q17", "pattern": "P08", "desc": "LOWER(email) 함수 기반 인덱스",
     "before": "CREATE INDEX IF NOT EXISTS idx_email_lower ON MEMBERS(LOWER(email))",
     "after":  "CREATE INDEX IF NOT EXISTS idx_email_direct ON MEMBERS(email)"},

    {"q": "Q18", "pattern": "P08", "desc": "UPPER(product_name) 함수 기반 인덱스",
     "before": "CREATE INDEX IF NOT EXISTS idx_prod_upper ON PRODUCTS(UPPER(product_name))",
     "after":  "CREATE INDEX IF NOT EXISTS idx_prod_direct ON PRODUCTS(product_name)"},

    # ── P09: JOIN Without Index ────────────────────────────────
    {"q": "Q19", "pattern": "P09", "desc": "비인덱스 컬럼 JOIN (status)",
     "before": "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status LIMIT 100",
     "after":  "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.id = o.member_id LIMIT 100"},

    {"q": "Q20", "pattern": "P09", "desc": "LIKE 조인 조건",
     "before": "SELECT p.product_name FROM PRODUCTS p JOIN CATEGORIES c ON p.product_name LIKE CONCAT('%', c.name, '%') LIMIT 100",
     "after":  "SELECT p.product_name FROM PRODUCTS p JOIN CATEGORIES c ON p.category_id = c.id LIMIT 100"},

    {"q": "Q21", "pattern": "P09", "desc": "DATE() 함수 JOIN",
     "before": "SELECT o.id, p.id FROM ORDERS o JOIN PAYMENTS p ON DATE(o.created_at) = DATE(p.payment_date) AND o.id = p.order_id LIMIT 100",
     "after":  "SELECT o.id, p.id FROM ORDERS o JOIN PAYMENTS p ON o.id = p.order_id LIMIT 100"},

    # ── P10: Nested Subquery ───────────────────────────────────
    {"q": "Q22", "pattern": "P10", "desc": "3중 중첩 IN (결제→주문→회원)",
     "before": """SELECT * FROM MEMBERS WHERE id IN (
         SELECT member_id FROM ORDERS WHERE id IN (
             SELECT order_id FROM PAYMENTS WHERE amount > 100000
         )
     )""",
     "after": """SELECT DISTINCT m.* FROM MEMBERS m
         JOIN ORDERS o ON m.id = o.member_id
         JOIN PAYMENTS p ON o.id = p.order_id
         WHERE p.amount > 100000"""},

    {"q": "Q23", "pattern": "P10", "desc": "3중 중첩 IN (카테고리→상품→주문)",
     "before": """SELECT * FROM ORDERS WHERE id IN (
         SELECT order_id FROM ORDER_ITEMS WHERE product_id IN (
             SELECT id FROM PRODUCTS WHERE category_id = 2
         )
     )""",
     "after": """SELECT DISTINCT o.* FROM ORDERS o
         JOIN ORDER_ITEMS oi ON o.id = oi.order_id
         JOIN PRODUCTS p ON oi.product_id = p.id
         WHERE p.category_id = 2"""},

    {"q": "Q24", "pattern": "P10", "desc": "3중 중첩 IN (쿠폰 회원 주문)",
     "before": """SELECT * FROM ORDERS WHERE member_id IN (
         SELECT id FROM MEMBERS WHERE id IN (
             SELECT member_id FROM COUPONS WHERE discount_amount > 0
         )
     )""",
     "after": """SELECT DISTINCT o.* FROM ORDERS o
         JOIN MEMBERS m ON o.member_id = m.id
         JOIN COUPONS c ON m.id = c.member_id
         WHERE c.discount_amount > 0"""},

    # ── P11: DECODE Function — MySQL 미지원 ────────────────────
    {"q": "Q25", "pattern": "P11", "desc": "DECODE 주문 상태 변환",
     "before": None,
     "after":  "SELECT id, CASE status WHEN 'PENDING' THEN '대기' WHEN 'COMPLETE' THEN '완료' ELSE '기타' END FROM ORDERS LIMIT 100"},

    {"q": "Q26", "pattern": "P11", "desc": "DECODE 결제 수단 변환",
     "before": None,
     "after":  "SELECT id, CASE payment_method WHEN 'CARD' THEN '신용카드' ELSE '기타' END FROM PAYMENTS LIMIT 100"},

    # ── P12: CONNECT BY — MySQL 미지원 ────────────────────────
    {"q": "Q27", "pattern": "P12", "desc": "CONNECT BY 카테고리 계층",
     "before": None,
     "after":  """WITH RECURSIVE cat_cte AS (
         SELECT id, parent_id, name FROM CATEGORIES WHERE parent_id IS NULL
         UNION ALL
         SELECT c.id, c.parent_id, c.name FROM CATEGORIES c JOIN cat_cte p ON c.parent_id = p.id
     ) SELECT * FROM cat_cte"""},

    {"q": "Q28", "pattern": "P12", "desc": "CONNECT BY 회원 계층",
     "before": None,
     "after":  "SELECT id, name FROM MEMBERS LIMIT 100"},

    # ── P13: START WITH — MySQL 미지원 ────────────────────────
    {"q": "Q29", "pattern": "P13", "desc": "START WITH 최상위 카테고리",
     "before": None,
     "after":  """WITH RECURSIVE cat_cte AS (
         SELECT id, parent_id, name FROM CATEGORIES WHERE parent_id IS NULL
         UNION ALL
         SELECT c.id, c.parent_id, c.name FROM CATEGORIES c JOIN cat_cte p ON c.parent_id = p.id
     ) SELECT * FROM cat_cte"""},

    {"q": "Q30", "pattern": "P13", "desc": "START WITH 특정 회원 하위",
     "before": None,
     "after":  "SELECT id, name FROM MEMBERS WHERE id = '10100'"},

    # ── P14: Oracle Outer Join (+) — MySQL 미지원 ──────────────
    {"q": "Q31", "pattern": "P14", "desc": "(+) 주문 없는 회원",
     "before": None,
     "after":  "SELECT m.name, o.id FROM MEMBERS m LEFT JOIN ORDERS o ON m.id = o.member_id LIMIT 100"},

    {"q": "Q32", "pattern": "P14", "desc": "(+) 결제 없는 주문",
     "before": None,
     "after":  "SELECT o.id, p.amount FROM ORDERS o LEFT JOIN PAYMENTS p ON o.id = p.order_id LIMIT 100"},

    # ── P15: SYSDATE ───────────────────────────────────────────
    {"q": "Q33", "pattern": "P15", "desc": "SYSDATE 날짜 연산",
     "before": "SELECT * FROM ORDERS WHERE created_at >= SYSDATE - 1",
     "after":  "SELECT * FROM ORDERS WHERE created_at >= NOW() - INTERVAL 1 DAY"},

    {"q": "Q34", "pattern": "P15", "desc": "SYSDATE 쿠폰 만료 비교",
     "before": "SELECT * FROM COUPONS WHERE valid_until >= SYSDATE",
     "after":  "SELECT * FROM COUPONS WHERE valid_until >= NOW()"},

    # ── P16: SYSTIMESTAMP — MySQL 미지원 ──────────────────────
    {"q": "Q35", "pattern": "P16", "desc": "SYSTIMESTAMP 주문 시간",
     "before": None,
     "after":  "SELECT COUNT(*) FROM ORDERS WHERE created_at >= NOW() - INTERVAL 1 DAY"},

    {"q": "Q36", "pattern": "P16", "desc": "SYSTIMESTAMP 결제 승인",
     "before": None,
     "after":  "SELECT COUNT(*) FROM PAYMENTS WHERE payment_date >= NOW() - INTERVAL 1 DAY"},

    # ── P17: MERGE INTO — MySQL 미지원 ────────────────────────
    {"q": "Q37", "pattern": "P17", "desc": "MERGE INTO 회원 Upsert",
     "before": None,
     "after":  "SELECT id, status FROM MEMBERS WHERE id = '100' LIMIT 1"},

    {"q": "Q38", "pattern": "P17", "desc": "MERGE INTO 상품 재고 Upsert",
     "before": None,
     "after":  "SELECT id, stock_quantity FROM PRODUCTS WHERE id = 50 LIMIT 1"},

    # ── P18: MINUS — MySQL 미지원 ─────────────────────────────
    {"q": "Q39", "pattern": "P18", "desc": "MINUS 주문 없는 회원",
     "before": None,
     "after":  "SELECT id FROM MEMBERS WHERE id NOT IN (SELECT DISTINCT member_id FROM ORDERS WHERE member_id IS NOT NULL)"},

    {"q": "Q40", "pattern": "P18", "desc": "MINUS 팔리지 않은 상품",
     "before": None,
     "after":  "SELECT id FROM PRODUCTS WHERE id NOT IN (SELECT DISTINCT product_id FROM ORDER_ITEMS)"},

    {"q": "Q41", "pattern": "P18", "desc": "MINUS 빈 카테고리",
     "before": None,
     "after":  "SELECT id FROM CATEGORIES WHERE id NOT IN (SELECT DISTINCT category_id FROM PRODUCTS WHERE category_id IS NOT NULL)"},

    # ── P19: DUAL Table ────────────────────────────────────────
    {"q": "Q42", "pattern": "P19", "desc": "DUAL 수식 연산",
     "before": "SELECT 100 * 200 FROM DUAL",
     "after":  "SELECT 100 * 200"},

    {"q": "Q43", "pattern": "P19", "desc": "SYSDATE FROM DUAL",
     "before": "SELECT SYSDATE FROM DUAL",
     "after":  "SELECT NOW()"},

    # ── P20: TO_CHAR — MySQL 미지원 ───────────────────────────
    {"q": "Q44", "pattern": "P20", "desc": "TO_CHAR 날짜 포맷",
     "before": None,
     "after":  "SELECT DATE_FORMAT(created_at, '%Y-%m-%d') FROM MEMBERS LIMIT 100"},

    {"q": "Q45", "pattern": "P20", "desc": "TO_CHAR 연월 포맷",
     "before": None,
     "after":  "SELECT DATE_FORMAT(created_at, '%Y/%m') FROM ORDERS LIMIT 100"},

    {"q": "Q46", "pattern": "P20", "desc": "TO_CHAR 결제일 포맷",
     "before": None,
     "after":  "SELECT DATE_FORMAT(payment_date, '%m-%d-%Y') FROM PAYMENTS LIMIT 100"},

    # ── P21: TO_DATE — MySQL 미지원 ───────────────────────────
    {"q": "Q47", "pattern": "P21", "desc": "TO_DATE 주문 날짜 파싱",
     "before": None,
     "after":  "SELECT * FROM ORDERS WHERE created_at = STR_TO_DATE('2025/01/01', '%Y/%m/%d')"},

    {"q": "Q48", "pattern": "P21", "desc": "TO_DATE 쿠폰 유효기간 파싱",
     "before": None,
     "after":  "SELECT * FROM COUPONS WHERE valid_until > STR_TO_DATE('2025-12-31 23:59:59', '%Y-%m-%d %H:%i:%s')"},

    # ── P22: TRUNC — MySQL 미지원 ─────────────────────────────
    {"q": "Q49", "pattern": "P22", "desc": "TRUNC 일자별 주문 집계",
     "before": None,
     "after":  "SELECT DATE(created_at), COUNT(*) FROM ORDERS GROUP BY DATE(created_at) ORDER BY 1 DESC LIMIT 30"},

    {"q": "Q50", "pattern": "P22", "desc": "TRUNC 월별 결제 집계",
     "before": None,
     "after":  "SELECT DATE_FORMAT(payment_date, '%Y-%m-01'), SUM(amount) FROM PAYMENTS GROUP BY DATE_FORMAT(payment_date, '%Y-%m-01')"},
]


# ══════════════════════════════════════════════════════════════
# /simulate API 호출 → predicted_score 산출
# check_simulator.py와 동일한 엔드포인트 사용
# ══════════════════════════════════════════════════════════════

_SEVERITY_SCORE = {"HIGH": 80, "MEDIUM": 40, "LOW": 10}

def get_predicted_score(sql: str) -> tuple[float, list[str]]:
    """
    /simulate 엔드포인트 호출 → max_severity 기반 predicted_score 반환.
    서버 미실행 시 (0.0, []) 반환.
    """
    try:
        resp = requests.post(
            SIMULATE_URL,
            json={"sql": sql},
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            return 0.0, []
        matched_ids   = data.get("matched_pattern_ids", [])
        max_severity  = data.get("max_severity", "LOW")
        score = float(_SEVERITY_SCORE.get(max_severity, 0))
        return score, matched_ids
    except Exception:
        return 0.0, []


# ══════════════════════════════════════════════════════════════
# MySQL 실행시간 측정
# ══════════════════════════════════════════════════════════════

def measure_sql(conn, sql: str, runs: int = 5) -> float | None:
    """SQL을 runs회 실행하여 평균 ms 반환. 실패 시 None."""
    times = []
    with conn.cursor() as cur:
        for _ in range(runs):
            try:
                # 인덱스 DDL: 먼저 DROP 후 CREATE
                upper = sql.strip().upper()
                if upper.startswith("CREATE INDEX") or upper.startswith("CREATE INDEX IF NOT EXISTS"):
                    tokens = sql.split()
                    idx_name = tokens[2] if tokens[2].upper() != "IF" else tokens[5]
                    tbl_name = sql.upper().split(" ON ")[1].split("(")[0].strip()
                    try:
                        cur.execute(f"DROP INDEX `{idx_name}` ON `{tbl_name}`")
                        conn.commit()
                    except Exception:
                        conn.rollback()
                elif upper.startswith("CREATE TEMPORARY TABLE"):
                    tbl_name = sql.split()[4].split("(")[0]
                    try:
                        cur.execute(f"DROP TEMPORARY TABLE IF EXISTS {tbl_name}")
                        conn.commit()
                    except Exception:
                        conn.rollback()

                start = time.perf_counter()
                cur.execute(sql)
                cur.fetchall()
                conn.commit()
                times.append((time.perf_counter() - start) * 1000)
            except Exception:
                conn.rollback()
                return None
    return round(statistics.mean(times), 2) if times else None


# ══════════════════════════════════════════════════════════════
# Task 1: 전체 측정 실행
# ══════════════════════════════════════════════════════════════

def run_measurements(
    rule_map: dict,
    runs: int = 5,
    use_simulate: bool = True,
    verbose: bool = True,
) -> list[dict]:
    conn = pymysql.connect(**MYSQL_CONFIG)
    results = []

    if verbose:
        print(f"\n{'='*65}")
        print(f"  badQuery 50종 실측 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  반복: {runs}회 평균 | /simulate: {'ON' if use_simulate else 'OFF'}")
        print(f"{'='*65}\n")

    for item in QUERY_PAIRS:
        qid     = item["q"]
        pid     = item["pattern"]
        desc    = item["desc"]

        # pattern_rules.json에서 메타데이터 참조
        rule    = rule_map.get(pid, {})
        name    = rule.get("name", pid)
        risk    = rule.get("risk", "UNKNOWN")
        ft      = rule.get("failure_type", "-")

        if verbose:
            print(f"  [{qid}] {pid} ({risk}) — {desc}")

        # before 측정
        if item["before"] is None:
            before_ms, before_note = None, "MySQL 미지원"
        else:
            before_ms = measure_sql(conn, item["before"], runs)
            before_note = f"{before_ms:.1f}ms" if before_ms is not None else "실행 실패"

        # after 측정
        after_ms = measure_sql(conn, item["after"], runs)
        after_note = f"{after_ms:.1f}ms" if after_ms is not None else "실행 실패"

        # /simulate → predicted_score + matched_ids
        after_sql_for_sim = item["after"]  # after 기준으로 시뮬레이터 호출
        if use_simulate:
            predicted_score, matched_ids = get_predicted_score(after_sql_for_sim)
        else:
            predicted_score, matched_ids = 0.0, []

        # 개선율
        if before_ms and after_ms and before_ms > 0:
            improvement = round((before_ms - after_ms) / before_ms * 100, 1)
        else:
            improvement = None

        # error_rate: before 대비 after 차이 비율
        if before_ms and after_ms and before_ms > 0:
                actual_improvement = (before_ms - after_ms) / before_ms * 100
                error_rate = round(abs(predicted_score - actual_improvement), 4)
        else:
            error_rate = 0.0

        if verbose:
            impr_str = f"{improvement:+.1f}%" if improvement is not None else "-"
            score_str = f"score={predicted_score:.0f}" if use_simulate else ""
            print(f"       before: {before_note:<14} after: {after_note:<14} 개선율: {impr_str}  {score_str}")

        results.append({
            "q":              qid,
            "pattern":        pid,
            "name":           name,
            "risk":           risk,
            "failure_type":   ft,
            "desc":           desc,
            "before_sql":     item["before"] or "N/A",
            "after_sql":      item["after"],
            "before_ms":      before_ms,
            "after_ms":       after_ms,
            "improvement":    improvement,
            "error_rate":     error_rate,
            "predicted_score": predicted_score,
            "matched_ids":    matched_ids,
            "measured_at":    datetime.now().isoformat(),
        })

    conn.close()

    if verbose:
        measurable = sum(1 for r in results if r["before_ms"] is not None)
        print(f"\n{'='*65}")
        print(f"  완료: 전체 {len(results)}건 | before 측정 {measurable}건 | 미지원 {len(results)-measurable}건")
        print(f"{'='*65}\n")

    return results


# ══════════════════════════════════════════════════════════════
# Task 2-A: CSV 저장
# ══════════════════════════════════════════════════════════════

def save_csv(results: list[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "q", "pattern", "name", "risk", "failure_type", "desc",
        "before_ms", "after_ms", "improvement", "error_rate",
        "predicted_score", "measured_at", "before_sql", "after_sql",
    ]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"  💾 CSV 저장: {out_path}")


# ══════════════════════════════════════════════════════════════
# Task 2-B: PredictionLog DB 적재 (database.py SQLAlchemy)
# ══════════════════════════════════════════════════════════════

def insert_to_db(results: list[dict]) -> int:
    if not DB_AVAILABLE:
        print("  ⚠ database.py 미연동 — DB 적재 생략")
        return 0

    try:
        init_db()
        db = SessionLocal()
        inserted = 0

        for r in results:
            log = PredictionLog(
                id              = str(uuid.uuid4()),
                pattern_id      = r["pattern"],
                pattern_name    = r["name"],
                risk            = r["risk"],
                predicted_score = r["predicted_score"],
                before_ms       = r["before_ms"],
                after_ms        = r["after_ms"],
                error_rate      = r["error_rate"],
                created_at      = datetime.now(),
            )
            db.add(log)
            inserted += 1

        db.commit()
        db.close()
        print(f"  💾 PredictionLog DB 적재: {inserted}건")
        return inserted

    except Exception as e:
        print(f"  ⚠ DB 적재 실패: {e}")
        return 0


# ══════════════════════════════════════════════════════════════
# Task 3: 재현성 검증 — 2배치 실행, 편차 ±5% 확인
# ══════════════════════════════════════════════════════════════

def check_reproducibility(rule_map: dict, runs: int = 3, use_simulate: bool = True):
    print(f"\n{'='*65}")
    print(f"  재현성 검증 (2배치 × {runs}회 | 허용 편차 ±{REPRO_THRESHOLD}%)")
    print(f"{'='*65}\n")

    print("  1배치 측정 중...")
    batch1 = run_measurements(rule_map, runs=runs, use_simulate=use_simulate, verbose=False)
    print("  5초 대기...")
    time.sleep(5)
    print("  2배치 측정 중...")
    batch2 = run_measurements(rule_map, runs=runs, use_simulate=use_simulate, verbose=False)

    b1 = {r["q"]: r for r in batch1}
    b2 = {r["q"]: r for r in batch2}

    repro_results = []
    unstable = []

    print(f"\n  {'쿼리':<6} {'패턴':<6} {'before1':>9} {'before2':>9} {'편차':>7}  {'after1':>9} {'after2':>9} {'편차':>7}  결과")
    print(f"  {'-'*75}")

    for qid in b1:
        r1, r2 = b1[qid], b2[qid]
        b_stable = a_stable = True
        b_dev = a_dev = "-"

        if r1["before_ms"] and r2["before_ms"] and r1["before_ms"] > 0:
            b_pct = abs(r1["before_ms"] - r2["before_ms"]) / r1["before_ms"] * 100
            b_dev = f"±{b_pct:.1f}%"
            b_stable = b_pct <= REPRO_THRESHOLD
        else:
            b_pct = None

        if r1["after_ms"] and r2["after_ms"] and r1["after_ms"] > 0:
            a_pct = abs(r1["after_ms"] - r2["after_ms"]) / r1["after_ms"] * 100
            a_dev = f"±{a_pct:.1f}%"
            a_stable = a_pct <= REPRO_THRESHOLD
        else:
            a_pct = None

        stable = b_stable and a_stable
        b1s = f"{r1['before_ms']:.1f}" if r1["before_ms"] else "N/A"
        b2s = f"{r2['before_ms']:.1f}" if r2["before_ms"] else "N/A"
        a1s = f"{r1['after_ms']:.1f}"  if r1["after_ms"]  else "N/A"
        a2s = f"{r2['after_ms']:.1f}"  if r2["after_ms"]  else "N/A"

        print(f"  {qid:<6} {r1['pattern']:<6} {b1s:>9} {b2s:>9} {b_dev:>7}  {a1s:>9} {a2s:>9} {a_dev:>7}  {'✅' if stable else '❌'}")

        entry = {"q": qid, "pattern": r1["pattern"], "name": r1["name"],
                 "before1": r1["before_ms"], "before2": r2["before_ms"], "before_dev": b_pct,
                 "after1":  r1["after_ms"],  "after2":  r2["after_ms"],  "after_dev":  a_pct,
                 "stable": stable}
        repro_results.append(entry)
        if not stable:
            unstable.append(entry)

    stable_cnt = len(repro_results) - len(unstable)
    print(f"\n{'='*65}")
    print(f"  재현성 결과: 안정 {stable_cnt}건 | 불안정 {len(unstable)}건")

    if unstable:
        print(f"\n  ⚠ 불안정 항목 ({len(unstable)}건)")
        for r in unstable:
            print(f"    [{r['q']}] {r['pattern']} — {r['name']}")
            if r["before_dev"] and r["before_dev"] > REPRO_THRESHOLD:
                print(f"       before 편차: ±{r['before_dev']:.1f}%")
            if r["after_dev"] and r["after_dev"] > REPRO_THRESHOLD:
                print(f"       after  편차: ±{r['after_dev']:.1f}%")
    else:
        print(f"\n  ✅ 전체 ±{REPRO_THRESHOLD}% 이내 — 재현성 달성!")
    print(f"{'='*65}\n")

    repro_csv = BASE_DIR / "test-results" / "reproducibility_report.csv"
    repro_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(repro_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(repro_results[0].keys()))
        writer.writeheader()
        writer.writerows(repro_results)
    print(f"  💾 재현성 리포트: {repro_csv}")

    return repro_results


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="badQuery 50종 before/after 실측")
    parser.add_argument("--runs",           type=int, default=5)
    parser.add_argument("--out",            type=str, default=str(DEFAULT_CSV))
    parser.add_argument("--skip-db",        action="store_true", help="DB 적재 생략")
    parser.add_argument("--skip-simulate",  action="store_true", help="/simulate 호출 생략")
    parser.add_argument("--repro",          action="store_true", help="재현성 검증 포함")
    args = parser.parse_args()

    use_simulate = not args.skip_simulate

    # pattern_rules.json 로드
    rule_map = load_rules(RULES_PATH)

    # Task 1: 측정
    results = run_measurements(rule_map, runs=args.runs, use_simulate=use_simulate)

    # Task 2-A: CSV 저장
    save_csv(results, Path(args.out))

    # Task 2-B: DB 적재
    if not args.skip_db:
        insert_to_db(results)

    # Task 3: 재현성 검증
    if args.repro:
        check_reproducibility(rule_map, runs=args.runs, use_simulate=use_simulate)

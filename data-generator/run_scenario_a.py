"""
run_scenario_a.py — 시나리오 A: Grocery Market Oracle SQL 패턴 탐지 검증
=========================================================================

입력 파일 (이미 포함됨):
  public-DB/grocery-oracle/
    ├── JTA_Create_Database.sql
    ├── JTA_Packages.sql       ← 중간평가 기준 131건 탐지
    └── JTA_Test_Code.sql

결과물:
  test-results/grocery_pattern_result.csv    → 구문별 상세
  test-results/grocery_pattern_summary.csv   → 패턴별 집계
  test-results/grocery_capture.md            → 탐지 결과 캡처
  test-results/bad_queries_draft_public_db.sql → badQuery 초안 20종+

실행:
  python run_scenario_a.py
  python run_scenario_a.py --files JTA_Packages.sql   # 단독 파일
  python run_scenario_a.py --skip-docker              # Docker 확인 생략
"""

import sys
import csv
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── 경로 설정 ──────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
BACKEND_DIR  = PROJECT_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "validation"))

RULES_PATH   = BACKEND_DIR / "validation" / "pattern_rules.json"
GROCERY_DIR  = BASE_DIR / "public-DB" / "grocery-oracle"
OUT_DIR      = BASE_DIR / "test-results"

DEFAULT_FILES = [
    "JTA_Create_Database.sql",
    "JTA_Packages.sql",
    "JTA_Test_Code.sql",
    "oracle_pattern_fixtures.sql",
]

# 중간평가 기준 수치 (JTA_Packages.sql 단독 기준)
BASELINE_STMTS    = 470
BASELINE_PATTERNS = 131
BASELINE_FTYPES   = 11

# 시나리오 A 체크리스트
MUST_DETECT  = ["P03", "P12", "P14", "P17", "P19"]
NEW_PATTERNS = ["P23", "P24", "P25", "P26", "P27", "P28", "P29", "P30"]

# DS3 MySQL 테이블 정보 (badQuery 초안 생성용)
DS3_TABLES = {
    "CUSTOMERS":  ["customerid", "firstname", "lastname", "email", "creditcard",
                   "creditcardexpiration", "username", "age", "income", "country"],
    "ORDERS":     ["orderid", "orderdate", "customerid", "netamount", "tax", "totalamount"],
    "ORDERLINES": ["orderlineid", "orderid", "prod_id", "quantity", "orderdate"],
    "PRODUCTS":   ["prod_id", "category", "title", "actor", "price", "special"],
    "INVENTORY":  ["prod_id", "quan_in_stock", "sales"],
    "CUST_HIST":  ["customerid", "orderid", "prod_id"],
}


# ══════════════════════════════════════════════════════════════
# 1. 탐지 실행
# ══════════════════════════════════════════════════════════════

def run_detection(file_names: list[str], rules, rule_map: dict) -> dict:
    from consistency_simulator import evaluate_sql

    all_detail_rows = []
    pattern_hits    = defaultdict(int)
    failure_set     = set()
    detected_pids   = set()
    total_stmts     = 0
    total_hits      = 0
    file_summary    = []

    for fname in file_names:
        fpath = GROCERY_DIR / fname
        if not fpath.exists():
            print(f"  ⚠  파일 없음: {fpath}")
            continue

        sql_text = fpath.read_text(encoding="utf-8", errors="replace")
        result   = evaluate_sql(sql_text, rules)
        stmts    = result["summary"]["statement_count"]
        hits     = result["summary"]["total_pattern_count"]
        total_stmts += stmts
        total_hits  += hits
        failure_set.update(result["summary"]["failure_types"])

        file_summary.append({"file": fname, "stmts": stmts, "hits": hits})
        print(f"  ✅ {fname}: {stmts}개 구문 / {hits}건 탐지")

        for detail in result["details"]:
            if detail["pattern_count"] == 0:
                continue
            for pid in detail["pattern_ids"]:
                pattern_hits[pid] += 1
                detected_pids.add(pid)
                if pid in rule_map:
                    failure_set.add(rule_map[pid].failure_type)
            all_detail_rows.append({
                "file":          fname,
                "statement":     detail["statement"][:120].replace("\n", " "),
                "pattern_ids":   ", ".join(detail["pattern_ids"]),
                "pattern_count": detail["pattern_count"],
                "max_severity":  detail["max_severity"],
                "failure_types": ", ".join(detail["failure_types"]),
            })

    return {
        "detail_rows":   all_detail_rows,
        "pattern_hits":  pattern_hits,
        "failure_set":   failure_set,
        "detected_pids": detected_pids,
        "total_stmts":   total_stmts,
        "total_hits":    total_hits,
        "file_summary":  file_summary,
    }


# ══════════════════════════════════════════════════════════════
# 2. DS3 Docker 컨테이너 세팅 확인
# ══════════════════════════════════════════════════════════════

def check_ds3_docker():
    print(f"\n  [DS3 Docker 컨테이너 세팅 확인]")
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        containers = {l.split("\t")[0]: l for l in lines if l}

        targets = {
            "migration-test-db": "bucket_store (3306)",
            "dvdstore-mysql":    "DS3 MySQL (3307)",
            "oracle-testbed":    "Oracle Free (1521)",
        }

        all_ok = True
        for name, desc in targets.items():
            if name in containers:
                status = containers[name].split("\t")[1] if "\t" in containers[name] else "?"
                print(f"  ✅ {name} ({desc}): {status}")
            else:
                print(f"  ❌ {name} ({desc}): 미실행")
                all_ok = False

        if not all_ok:
            print(f"\n  → docker-compose up -d 로 컨테이너를 실행하세요.")
        return all_ok

    except Exception as e:
        print(f"  ⚠  Docker 확인 실패: {e}")
        print(f"  → Docker Desktop이 실행 중인지 확인하세요.")
        return False


# ══════════════════════════════════════════════════════════════
# 3. badQuery 초안 20종+ 생성
#    Grocery Oracle + DS3 탐지 패턴 기반, DS3 테이블 사용
# ══════════════════════════════════════════════════════════════

BAD_QUERY_TEMPLATES = [
    # P01 — Implicit Type Cast (DS3 CUSTOMERS)
    ("P01", "CUSTOMERS customerid(NUMBER)에 문자열 비교",
     "SELECT * FROM CUSTOMERS WHERE customerid = '12345'"),
    ("P01", "ORDERS customerid VARCHAR 비교",
     "SELECT * FROM ORDERS WHERE customerid = 100"),

    # P02 — Function on Indexed Column
    ("P02", "CUSTOMERS email UPPER 인덱스 우회",
     "SELECT * FROM CUSTOMERS WHERE UPPER(email) LIKE '%@GMAIL.COM%'"),
    ("P02", "PRODUCTS title LOWER 인덱스 우회",
     "SELECT * FROM PRODUCTS WHERE LOWER(title) = 'inception'"),

    # P04 — NVL Function
    ("P04", "ORDERS netamount NVL null 치환",
     "SELECT orderid, NVL(netamount, 0) FROM ORDERS WHERE customerid = 500"),
    ("P04", "INVENTORY quan_in_stock NVL",
     "SELECT prod_id, NVL(quan_in_stock, 0) FROM INVENTORY WHERE sales > 100"),

    # P05 — DATE vs DATETIME
    ("P05", "ORDERS orderdate DATE 비교",
     "SELECT * FROM ORDERS WHERE DATE(orderdate) = '2024-01-15'"),
    ("P05", "ORDERS CAST AS DATE 시간 손실",
     "SELECT * FROM ORDERS WHERE CAST(orderdate AS DATE) BETWEEN '2024-01-01' AND '2024-03-31'"),

    # P06 — VARCHAR2
    ("P06", "CUSTOMERS 임시 테이블 VARCHAR2",
     "CREATE TEMPORARY TABLE temp_vip (cust_id VARCHAR2(20), grade VARCHAR2(10))"),

    # P09 — JOIN Without Index
    ("P09", "CUSTOMERS-ORDERS 비인덱스 컬럼 JOIN",
     "SELECT c.firstname, o.totalamount FROM CUSTOMERS c JOIN ORDERS o ON c.country = o.orderdate"),
    ("P09", "PRODUCTS-ORDERLINES LIKE JOIN",
     "SELECT p.title, ol.quantity FROM PRODUCTS p JOIN ORDERLINES ol ON p.title LIKE CONCAT('%', ol.prod_id, '%')"),

    # P10 — Nested Subquery
    ("P10", "3중 중첩 IN (CUST_HIST → ORDERS → CUSTOMERS)",
     """SELECT * FROM CUSTOMERS WHERE customerid IN (
    SELECT customerid FROM ORDERS WHERE orderid IN (
        SELECT orderid FROM ORDERLINES WHERE prod_id IN (
            SELECT prod_id FROM PRODUCTS WHERE category = 'DVD'
        )
    )
)"""),
    ("P10", "상관 서브쿼리 (고객별 총 주문액)",
     "SELECT c.firstname, (SELECT SUM(o.totalamount) FROM ORDERS o WHERE o.customerid = c.customerid) FROM CUSTOMERS c"),

    # P13 — START WITH Hierarchy (Grocery CATEGORIES 구조)
    ("P13", "Grocery 카테고리 계층 START WITH",
     "SELECT * FROM jta_categories START WITH parent_id IS NULL CONNECT BY PRIOR cat_id = parent_id"),

    # P15 — SYSDATE
    ("P15", "ORDERS 최근 30일 SYSDATE 비교",
     "SELECT * FROM ORDERS WHERE orderdate >= SYSDATE - 30"),
    ("P15", "CUSTOMERS 등록일 SYSDATE 비교",
     "SELECT * FROM CUSTOMERS WHERE creditcardexpiration > SYSDATE"),

    # P20 — TO_CHAR
    ("P20", "ORDERS 월별 집계 TO_CHAR",
     "SELECT TO_CHAR(orderdate, 'YYYY-MM'), COUNT(*), SUM(totalamount) FROM ORDERS GROUP BY TO_CHAR(orderdate, 'YYYY-MM')"),
    ("P20", "PRODUCTS 가격 TO_CHAR 포맷",
     "SELECT title, TO_CHAR(price, '999,990.00') FROM PRODUCTS WHERE special = 1"),

    # P21 — TO_DATE
    ("P21", "ORDERS TO_DATE 날짜 파싱",
     "SELECT * FROM ORDERS WHERE orderdate >= TO_DATE('2024-01-01', 'YYYY-MM-DD')"),

    # P22 — TRUNC
    ("P22", "ORDERS 월별 집계 TRUNC",
     "SELECT TRUNC(orderdate, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(orderdate, 'MM')"),

    # P23 — SEQUENCE NEXTVAL (Grocery에서 실제 탐지됨)
    ("P23", "ORDERS 시퀀스 채번 INSERT",
     "INSERT INTO ORDERS (orderid, orderdate, customerid) VALUES (order_seq.NEXTVAL, SYSDATE, 100)"),

    # P25 — NUMBER Type (Grocery에서 실제 탐지됨)
    ("P25", "임시 주문 테이블 NUMBER 타입",
     "CREATE TABLE temp_orders (order_id NUMBER, amount NUMBER(12,2), status VARCHAR2(20))"),
]


def generate_bad_queries_draft(
    pattern_hits: dict, rule_map: dict, out_path: Path
) -> int:
    lines = [
        "-- ============================================================",
        "-- badQuery 설계 초안 — 공개 DB (Grocery Oracle + DS3) 기반",
        f"-- 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-- 대상 테이블: DS3(CUSTOMERS, ORDERS, PRODUCTS, ORDERLINES 등)",
        "--              Grocery Oracle(jta_* 테이블)",
        "-- 탐지 기반 패턴: " + ", ".join(sorted(pattern_hits.keys())),
        "-- ============================================================",
        "",
    ]

    count = 0
    for pid, desc, sql in BAD_QUERY_TEMPLATES:
        rule  = rule_map.get(pid)
        risk  = rule.risk if rule else "UNKNOWN"
        lines += [
            f"-- 🚨 [{pid}] {rule.name if rule else pid} ({risk}): {desc}",
            sql.strip() + ";",
            "",
        ]
        count += 1

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return count

# ══════════════════════════════════════════════════════════════
# 5. 탐지 결과 캡처 (발표용 마크다운)
# ══════════════════════════════════════════════════════════════

def save_capture(
    pattern_hits: dict, failure_set: set, rule_map: dict,
    total_stmts: int, total_hits: int,
    file_summary: list, undetected_new: list, out_path: Path
):
    lines = [
        "# 시나리오 A — Grocery Market Oracle 패턴 탐지 결과 캡처",
        f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 기준 비교",
        "",
        f"| 항목 | 중간평가 기준 (JTA_Packages.sql) | 현재 (전체 3파일) |",
        f"|------|----------------------------------|------------------|",
        f"| 분석 구문 수 | {BASELINE_STMTS}개 | {total_stmts}개 |",
        f"| 패턴 탐지 건수 | {BASELINE_PATTERNS}건 | {total_hits}건 |",
        f"| 실패 유형 종류 | {BASELINE_FTYPES}종 | {len(failure_set)}종 |",
        "",
        "## 파일별 탐지 현황",
        "",
        "| 파일 | 구문 수 | 탐지 건수 |",
        "|------|---------|---------|",
    ]
    for s in file_summary:
        lines.append(f"| {s['file']} | {s['stmts']} | {s['hits']} |")

    lines += [
        "",
        "## 패턴별 탐지 횟수",
        "",
        "| 패턴 ID | 패턴명 | 위험도 | 탐지 횟수 |",
        "|---------|--------|--------|---------|",
    ]
    for pid in sorted(pattern_hits.keys()):
        rule = rule_map.get(pid)
        lines.append(
            f"| {pid} | {rule.name if rule else '-'} | {rule.risk if rule else '-'} | {pattern_hits[pid]}건 |"
        )

    lines += [
        "",
        "## 체크리스트",
        "",
    ]
    for pid in MUST_DETECT:
        rule   = rule_map.get(pid)
        status = "✅" if pid in pattern_hits else "❌"
        count  = f"({pattern_hits[pid]}건)" if pid in pattern_hits else "(미탐지)"
        lines.append(f"- {status} {pid} — {rule.name if rule else pid} {count}")

    lines += ["", "### 신규 패턴 P23~P30"]
    for pid in NEW_PATTERNS:
        rule   = rule_map.get(pid)
        status = "✅" if pid in pattern_hits else "⚠"
        count  = f"({pattern_hits[pid]}건)" if pid in pattern_hits else "(미탐지)"
        lines.append(f"- {status} {pid} — {rule.name if rule else pid} {count}")

    if undetected_new:
        lines += ["", f"> ⚠ 미탐지 패턴 {undetected_new}"]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ══════════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════════

def main(file_names: list[str], skip_docker: bool = False):
    print(f"\n{'='*65}")
    print(f"  시나리오 A — Grocery Market Oracle SQL 패턴 탐지 검증")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    # ── 룰 로드 ───────────────────────────────────────────────
    try:
        from consistency_simulator import load_rules
        rules    = load_rules(RULES_PATH)
        rule_map = {r.id: r for r in rules}
        print(f"  ✅ pattern_rules.json 로드 — {len(rules)}개 패턴\n")
    except Exception as e:
        print(f"  ❌ 룰 로드 실패: {e}")
        return

    # ── 탐지 실행 ─────────────────────────────────────────────
    r = run_detection(file_names, rules, rule_map)

    # ── 결과 요약 출력 ────────────────────────────────────────
    total_hits = r["total_hits"]
    print(f"\n  {'='*55}")
    print(f"  탐지 결과 요약")
    print(f"  총 구문:        {r['total_stmts']}개  (중간평가 기준: {BASELINE_STMTS}개)")
    print(f"  총 탐지 건수:   {total_hits}건  (중간평가 기준: {BASELINE_PATTERNS}건)")
    print(f"  실패 유형 종류: {len(r['failure_set'])}종  (중간평가 기준: {BASELINE_FTYPES}종)")
    print(f"  고유 패턴 종류: {len(r['detected_pids'])}개")
    print(f"  {'='*55}\n")

    print(f"  {'패턴ID':<8} {'패턴명':<32} {'위험도':<8} {'탐지 횟수':>8}")
    print(f"  {'-'*60}")
    for pid in sorted(r["pattern_hits"].keys()):
        rule = rule_map.get(pid)
        print(f"  {pid:<8} {rule.name if rule else '-':<32} {rule.risk if rule else '-':<8} {r['pattern_hits'][pid]:>8}건")

    # 체크리스트
    print(f"\n  [필수 패턴 체크리스트]")
    for pid in MUST_DETECT:
        rule   = rule_map.get(pid)
        status = "✅ 탐지됨" if pid in r["detected_pids"] else "❌ 미탐지"
        count  = f"({r['pattern_hits'][pid]}건)" if pid in r["detected_pids"] else ""
        print(f"  {status} {pid} — {rule.name if rule else pid} {count}")

    print(f"\n  [신규 패턴 P23~P30]")
    undetected_new = []
    for pid in NEW_PATTERNS:
        rule = rule_map.get(pid)
        if pid in r["detected_pids"]:
            print(f"  ✅ {pid} — {rule.name if rule else pid} ({r['pattern_hits'][pid]}건)")
        else:
            print(f"  ⚠  {pid} — {rule.name if rule else pid} (미탐지 → B 전달 필요)")
            undetected_new.append(pid)

    if undetected_new:
        print(f"\n  📋 {undetected_new}")

    # ── DS3 Docker 확인 ───────────────────────────────────────
    if not skip_docker:
        check_ds3_docker()

    # ── CSV 저장 ──────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    detail_csv = OUT_DIR / "grocery_pattern_result.csv"
    with open(detail_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file", "pattern_ids", "pattern_count",
            "max_severity", "failure_types", "statement",
        ])
        writer.writeheader()
        writer.writerows(r["detail_rows"])

    summary_csv = OUT_DIR / "grocery_pattern_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pattern_id", "pattern_name", "risk", "failure_type", "detected_count",
        ])
        writer.writeheader()
        for pid in sorted(r["pattern_hits"].keys()):
            rule = rule_map.get(pid)
            writer.writerow({
                "pattern_id":     pid,
                "pattern_name":   rule.name if rule else "-",
                "risk":           rule.risk if rule else "-",
                "failure_type":   rule.failure_type if rule else "-",
                "detected_count": r["pattern_hits"][pid],
            })

    # ── 탐지 결과 캡처 ────────────────────────────────────────
    capture_md = OUT_DIR / "grocery_capture.md"
    save_capture(
        r["pattern_hits"], r["failure_set"], rule_map,
        r["total_stmts"], total_hits,
        r["file_summary"], undetected_new, capture_md,
    )

    # ── badQuery 초안 생성 ────────────────────────────────────
    draft_sql = OUT_DIR / "bad_queries_draft_public_db.sql"
    count = generate_bad_queries_draft(r["pattern_hits"], rule_map, draft_sql)

    # ── 완료 요약 ─────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  저장 완료")
    print(f"  📄 {detail_csv.name:<40} 구문별 상세")
    print(f"  📄 {summary_csv.name:<40} 패턴별 집계")
    print(f"  📄 {capture_md.name:<40} 탐지 결과 캡처")
    print(f"  📄 {draft_sql.name:<40} badQuery 초안 {count}종")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grocery Oracle 패턴 탐지")
    parser.add_argument(
        "--files", nargs="+", default=DEFAULT_FILES,
        help="분석할 SQL 파일명 (public-DB/grocery-oracle/ 기준)"
    )
    parser.add_argument(
        "--skip-docker", action="store_true",
        help="DS3 Docker 컨테이너 확인 생략"
    )
    args = parser.parse_args()
    main(args.files, skip_docker=args.skip_docker)

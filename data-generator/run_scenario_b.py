"""
run_scenario_b.py — 시나리오 B: DS3 데이터 Oracle vs MySQL 실행시간 실측
=========================================================================
목적:
  1. DS3 MySQL 컨테이너 세팅 확인 + 데이터 적재 검증
  2. 동일 쿼리를 Oracle(before_ms)과 MySQL(after_ms)에서 실행해 시간 비교
  3. 결과를 ds3_measure_result.csv 저장 → Grid Search 입력값

DS3 컨테이너 구성:
  dvdstore-mysql  (port 3308, db=DS3)  → after_ms 실측
  oracle-testbed  (port 1521)          → before_ms 실측 (없으면 None)
  migration-test-db (port 3307)        → bucketstore_dummy fallback

실행:
  python run_scenario_b.py               # 기본 실행
  python run_scenario_b.py --setup       # DS3 MySQL 데이터 적재 포함
  python run_scenario_b.py --skip-oracle # Oracle 측정 생략
  python run_scenario_b.py --use-bucket  # bucketstore_dummy로 측정
"""

import sys
import csv
import time
import argparse
import subprocess
import statistics
from pathlib import Path
from datetime import datetime

import pymysql

# ── 경로 설정 ──────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
BACKEND_DIR  = PROJECT_ROOT / "backend"
OUT_DIR      = BASE_DIR / "test-results"
DS3_DIR      = BASE_DIR / "public-DB" / "dvdstore"
DATA_DIR     = DS3_DIR / "data_files"

sys.path.insert(0, str(BACKEND_DIR))

# ── DB 접속 정보 ───────────────────────────────────────────────
DS3_MYSQL_CONFIG = dict(
    host="localhost", port=3308,
    user="root", password="root",
    db="DS3", charset="utf8mb4", connect_timeout=5,
    local_infile=True,   
)
BUCKET_MYSQL_CONFIG = dict(
    host="localhost", port=3307,
    user="root", password="root",
    db="bucketstore_dummy", charset="utf8mb4", connect_timeout=5,
)
ORACLE_DSN = "system/root@localhost:1521/FREEPDB1"

# ── 반복 횟수 / 허용 편차 ──────────────────────────────────────
REPEAT    = 5
THRESHOLD = 5.0  # ±5%

# ── 목표 적재 건수 ─────────────────────────────────────────────
TARGET_ORDERS = 1_000_000


# ══════════════════════════════════════════════════════════════
# DS3 쿼리 쌍 정의 (Oracle before / MySQL after)
# 테이블: DS3 → CUSTOMERS, ORDERS, PRODUCTS, ORDERLINES, INVENTORY
#         bucketstore_dummy → MEMBERS, ORDERS, PRODUCTS, ORDER_ITEMS, PAYMENTS
# ══════════════════════════════════════════════════════════════

DS3_QUERY_PAIRS = [
    {
        "pattern": "P02", "risk": "HIGH",
        "desc": "UPPER(email) 인덱스 우회",
        "oracle": "SELECT * FROM CUSTOMERS WHERE UPPER(email) LIKE '%@GMAIL.COM%'",
        "mysql":  "SELECT * FROM CUSTOMERS WHERE email LIKE '%@gmail.com%'",
    },
    {
    "pattern": "P03", "risk": "HIGH",
    "desc": "ROWNUM 페이징",
    "oracle": "SELECT * FROM ORDERS WHERE ROWNUM <= 10",  # ← 추가
    "mysql":  "SELECT * FROM ORDERS ORDER BY orderdate DESC LIMIT 10",
    },
    {
    "pattern": "P04", "risk": "LOW",
    "desc": "NVL 함수 null 치환",
    "oracle": "SELECT orderid, NVL(netamount, 0) FROM ORDERS WHERE customerid = 500",  # ← 추가
    "mysql":  "SELECT orderid, IFNULL(netamount, 0) FROM ORDERS WHERE customerid = 500",
    },
    {
    "pattern": "P05", "risk": "MEDIUM",
    "desc": "DATE() 함수로 인덱스 무력화",
    "oracle": "SELECT * FROM ORDERS WHERE orderdate >= SYSDATE - 30",
    "mysql":  "SELECT * FROM ORDERS WHERE orderdate >= DATE(NOW() - INTERVAL 30 DAY)",
    },
    {
    "pattern": "P09", "risk": "HIGH",
    "desc": "비인덱스 컬럼 JOIN",
    "oracle": "SELECT c.firstname, o.totalamount FROM CUSTOMERS c JOIN ORDERS o ON c.country = TO_CHAR(o.orderdate, 'YYYY-MM-DD') AND ROWNUM <= 100",
    "mysql":  "SELECT c.firstname, o.totalamount FROM CUSTOMERS c JOIN ORDERS o ON c.customerid = o.customerid LIMIT 100",
    },
    {
        "pattern": "P10", "risk": "MEDIUM",
        "desc": "3중 중첩 서브쿼리",
        "oracle": """SELECT * FROM CUSTOMERS WHERE customerid IN (
    SELECT customerid FROM ORDERS WHERE orderid IN (
        SELECT orderid FROM ORDERLINES WHERE prod_id IN (
            SELECT prod_id FROM PRODUCTS WHERE category = 4
        )
    )
)""",
        "mysql": """SELECT DISTINCT c.* FROM CUSTOMERS c
    JOIN ORDERS o ON c.customerid = o.customerid
    JOIN ORDERLINES ol ON o.orderid = ol.orderid
    JOIN PRODUCTS p ON ol.prod_id = p.prod_id
    WHERE p.category = 4""",
    },
    {
        "pattern": "P15", "risk": "LOW",
        "desc": "SYSDATE 날짜 연산",
        "oracle": "SELECT * FROM ORDERS WHERE orderdate >= SYSDATE - 365",
        "mysql":  "SELECT * FROM ORDERS WHERE orderdate >= NOW() - INTERVAL 365 DAY",
    },
    {
    "pattern": "P20", "risk": "MEDIUM",
    "desc": "TO_CHAR 월별 집계",
    "oracle": "SELECT TO_CHAR(orderdate, 'YYYY-MM'), COUNT(*), SUM(totalamount) FROM ORDERS GROUP BY TO_CHAR(orderdate, 'YYYY-MM')",  # ← 추가
    "mysql":  "SELECT DATE_FORMAT(orderdate, '%Y-%m'), COUNT(*), SUM(totalamount) FROM ORDERS GROUP BY DATE_FORMAT(orderdate, '%Y-%m')",
    },
    {
    "pattern": "P21", "risk": "MEDIUM",
    "desc": "TO_DATE 날짜 파싱",
    "oracle": "SELECT * FROM ORDERS WHERE orderdate >= TO_DATE('2013-01-01', 'YYYY-MM-DD')",  # ← 추가
    "mysql":  "SELECT * FROM ORDERS WHERE orderdate >= STR_TO_DATE('2013-01-01', '%Y-%m-%d')",
    },
    {
    "pattern": "P22", "risk": "MEDIUM",
    "desc": "TRUNC 날짜 절삭",
    "oracle": "SELECT TRUNC(orderdate, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(orderdate, 'MM')",  # ← 추가
    "mysql":  "SELECT DATE_FORMAT(orderdate, '%Y-%m-01'), COUNT(*) FROM ORDERS GROUP BY DATE_FORMAT(orderdate, '%Y-%m-01')",
    },
]

BUCKET_QUERY_PAIRS = [
    {
        "pattern": "P02", "risk": "HIGH",
        "desc": "UPPER(email) 인덱스 우회",
        "oracle": "SELECT * FROM MEMBERS WHERE UPPER(email) LIKE '%@GMAIL.COM%'",
        "mysql":  "SELECT * FROM MEMBERS WHERE email LIKE '%@gmail.com%'",
    },
    {
        "pattern": "P03", "risk": "HIGH",
        "desc": "ROWNUM 페이징",
        "oracle": None,
        "mysql":  "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10",
    },
    {
        "pattern": "P04", "risk": "LOW",
        "desc": "NVL null 치환",
        "oracle": None,
        "mysql":  "SELECT id, IFNULL(discount_amount, 0) FROM COUPONS LIMIT 100",
    },
    {
        "pattern": "P05", "risk": "MEDIUM",
        "desc": "DATE() 인덱스 무력화",
        "oracle": "SELECT * FROM ORDERS WHERE TRUNC(created_at) = TRUNC(SYSDATE - 30)",
        "mysql":  "SELECT * FROM ORDERS WHERE created_at >= DATE(NOW() - INTERVAL 30 DAY)",
    },
    {
        "pattern": "P09", "risk": "HIGH",
        "desc": "비인덱스 컬럼 JOIN",
        "oracle": "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status",
        "mysql":  "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.id = o.member_id LIMIT 100",
    },
    {
        "pattern": "P10", "risk": "MEDIUM",
        "desc": "3중 중첩 서브쿼리",
        "oracle": """SELECT * FROM MEMBERS WHERE id IN (
    SELECT member_id FROM ORDERS WHERE id IN (
        SELECT order_id FROM ORDER_ITEMS WHERE product_id IN (
            SELECT id FROM PRODUCTS WHERE category_id = 2
        )
    )
)""",
        "mysql": """SELECT DISTINCT m.* FROM MEMBERS m
    JOIN ORDERS o ON m.id = o.member_id
    JOIN ORDER_ITEMS oi ON o.id = oi.order_id
    JOIN PRODUCTS p ON oi.product_id = p.id
    WHERE p.category_id = 2""",
    },
    {
        "pattern": "P15", "risk": "LOW",
        "desc": "SYSDATE 날짜 연산",
        "oracle": "SELECT * FROM ORDERS WHERE created_at >= SYSDATE - 365",
        "mysql":  "SELECT * FROM ORDERS WHERE created_at >= NOW() - INTERVAL 365 DAY",
    },
    {
        "pattern": "P20", "risk": "MEDIUM",
        "desc": "TO_CHAR 월별 집계",
        "oracle": None,
        "mysql":  "SELECT DATE_FORMAT(created_at, '%Y-%m'), COUNT(*), SUM(total_amount) FROM ORDERS GROUP BY DATE_FORMAT(created_at, '%Y-%m')",
    },
    {
        "pattern": "P21", "risk": "MEDIUM",
        "desc": "TO_DATE 날짜 파싱",
        "oracle": None,
        "mysql":  "SELECT * FROM ORDERS WHERE created_at >= STR_TO_DATE('2024-01-01', '%Y-%m-%d')",
    },
    {
        "pattern": "P22", "risk": "MEDIUM",
        "desc": "TRUNC 날짜 절삭",
        "oracle": None,
        "mysql":  "SELECT DATE_FORMAT(created_at, '%Y-%m-01'), COUNT(*) FROM ORDERS GROUP BY DATE_FORMAT(created_at, '%Y-%m-01')",
    },
]


# ══════════════════════════════════════════════════════════════
# 1. 컨테이너 상태 확인
# ══════════════════════════════════════════════════════════════

def check_containers() -> dict:
    print(f"\n  [컨테이너 상태 확인]")
    status = {"ds3_mysql": False, "bucket_mysql": False, "oracle": False}
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        running = result.stdout.strip().split("\n")
        status["ds3_mysql"]    = "dvdstore-mysql" in running
        status["bucket_mysql"] = "migration-test-db" in running
        status["oracle"]       = "oracle-testbed" in running
    except Exception:
        pass

    icons = {True: "✅", False: "❌"}
    print(f"  {icons[status['ds3_mysql']]}  dvdstore-mysql   (DS3, port 3308)")
    print(f"  {icons[status['bucket_mysql']]}  migration-test-db (bucketstore_dummy, port 3307)")
    print(f"  {icons[status['oracle']]}  oracle-testbed   (Oracle Free, port 1521)")

    if not status["ds3_mysql"]:
        print(f"""
  → DS3 MySQL 컨테이너가 없습니다. docker-compose.yml에 아래를 추가하세요:

  mysql-dvdstore:
    image: mysql:8.0
    container_name: dvdstore-mysql
    ports:
      - "3308:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: DS3
      TZ: Asia/Seoul
    command:
      - --default-authentication-plugin=mysql_native_password
      - --local-infile=1
""")
    return status


# ══════════════════════════════════════════════════════════════
# 2. MySQL 연결 (DS3 → fallback: bucketstore_dummy)
# ══════════════════════════════════════════════════════════════

def get_mysql_conn(use_bucket: bool = False):
    if use_bucket:
        conn = pymysql.connect(**BUCKET_MYSQL_CONFIG)
        return conn, "bucketstore_dummy", BUCKET_QUERY_PAIRS

    try:
        conn = pymysql.connect(**DS3_MYSQL_CONFIG)
        return conn, "DS3", DS3_QUERY_PAIRS
    except Exception:
        print(f"  ⚠  dvdstore-mysql 연결 실패 → bucketstore_dummy로 fallback")
        conn = pymysql.connect(**BUCKET_MYSQL_CONFIG)
        return conn, "bucketstore_dummy (fallback)", BUCKET_QUERY_PAIRS


# ══════════════════════════════════════════════════════════════
# 3. DS3 데이터 적재 (--setup 옵션)
# ══════════════════════════════════════════════════════════════

def setup_ds3_data(conn):
    """DS3 MySQL에 CSV 데이터 적재 및 스키마 생성"""
    print(f"\n  [DS3 MySQL 데이터 적재]")
    cur = conn.cursor()

    # 스키마 생성
    schema_sqls = [
        """CREATE TABLE IF NOT EXISTS CUSTOMERS (
            customerid INT PRIMARY KEY, firstname VARCHAR(50), lastname VARCHAR(50),
            address1 VARCHAR(100), city VARCHAR(50), state CHAR(2), zip VARCHAR(10),
            country VARCHAR(50), phone VARCHAR(20), email VARCHAR(100),
            creditcardtype INT, creditcard VARCHAR(20), creditcardexpiration VARCHAR(10),
            username VARCHAR(50), password VARCHAR(50), age SMALLINT,
            income INT, gender CHAR(1)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS PRODUCTS (
            prod_id INT PRIMARY KEY, category SMALLINT, title VARCHAR(100),
            actor VARCHAR(50), price DECIMAL(12,2), special SMALLINT,
            common_prod_id INT
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS INVENTORY (
            prod_id INT PRIMARY KEY, quan_in_stock INT, sales INT
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS ORDERS (
            orderid INT PRIMARY KEY, orderdate DATETIME, customerid INT,
            netamount DECIMAL(12,2), tax DECIMAL(12,2), totalamount DECIMAL(12,2),
            INDEX idx_orders_customerid (customerid),
            INDEX idx_orders_orderdate (orderdate)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS ORDERLINES (
            orderlineid INT PRIMARY KEY, orderid INT, prod_id INT,
            quantity SMALLINT, orderdate DATETIME,
            INDEX idx_ol_orderid (orderid)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS CUST_HIST (
            customerid INT, orderid INT, prod_id INT,
            INDEX idx_ch_customerid (customerid)
        ) ENGINE=InnoDB""",
    ]

    for sql in schema_sqls:
        try:
            cur.execute(sql)
        except Exception as e:
            print(f"  ⚠  스키마 생성: {e}")
    conn.commit()
    print(f"  ✅ 스키마 생성 완료")

    # CSV 적재
    cur.execute("SET GLOBAL local_infile = 1")
    load_targets = [
        ("CUSTOMERS",  DATA_DIR / "cust" / "row_cust.csv"),
        ("CUSTOMERS",  DATA_DIR / "cust" / "us_cust.csv"),
        ("PRODUCTS",   DATA_DIR / "prod" / "prod.csv"),
        ("INVENTORY",  DATA_DIR / "prod" / "inv.csv"),
    ]
    for month in ["jan","feb","mar","apr","may","jun",
                  "jul","aug","sep","oct","nov","dec"]:
        load_targets.append(("ORDERS",     DATA_DIR / "orders" / f"{month}_orders.csv"))
        load_targets.append(("ORDERLINES", DATA_DIR / "orders" / f"{month}_orderlines.csv"))
        load_targets.append(("CUST_HIST",  DATA_DIR / "orders" / f"{month}_cust_hist.csv"))

    for table, csv_path in load_targets:
        if not csv_path.exists():
            continue
        path_str = str(csv_path).replace("\\", "/")
        try:
            cur.execute(f"""
                LOAD DATA LOCAL INFILE '{path_str}'
                INTO TABLE {table}
                FIELDS TERMINATED BY ','
                OPTIONALLY ENCLOSED BY '"'
            """)
            conn.commit()
            print(f"  ✅ {table} ← {csv_path.name}")
        except Exception as e:
            print(f"  ⚠  {table} 적재 실패: {e}")


# ══════════════════════════════════════════════════════════════
# 4. 데이터 적재 현황 확인 (100만건 목표)
# ══════════════════════════════════════════════════════════════

def verify_data(conn, db_name: str) -> dict:
    print(f"\n  [데이터 적재 현황 — {db_name}]")
    tables = (
        ["CUSTOMERS", "ORDERS", "PRODUCTS", "ORDERLINES", "INVENTORY"]
        if "DS3" in db_name
        else ["MEMBERS", "ORDERS", "PRODUCTS", "ORDER_ITEMS", "PAYMENTS"]
    )
    counts = {}
    cur = conn.cursor()
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            counts[t] = cnt
        except Exception:
            counts[t] = None

    order_tbl = "ORDERS"
    total_orders = counts.get(order_tbl, 0) or 0

    for t, cnt in counts.items():
        val = f"{cnt:,}" if cnt is not None else "테이블 없음"
        goal = " ← 목표 100만건" if t == order_tbl else ""
        ok = "✅" if (cnt or 0) > 0 else "❌"
        print(f"  {ok} {t:<15}: {val}{goal}")

    if total_orders >= TARGET_ORDERS:
        print(f"\n  ✅ ORDERS {total_orders:,}건 — 100만건 목표 달성!")
    else:
        print(f"\n  ⚠  ORDERS {total_orders:,}건 — 목표 {TARGET_ORDERS:,}건 미달")
        print(f"     generate_dummy.py 실행 또는 DS3 large 데이터셋 적재 필요")

    return counts


# ══════════════════════════════════════════════════════════════
# 5. 실행시간 측정
# ══════════════════════════════════════════════════════════════

def measure_mysql_query(conn, sql: str, runs: int = REPEAT) -> float | None:
    times = []
    with conn.cursor() as cur:
        for _ in range(runs):
            try:
                start = time.perf_counter()
                cur.execute(sql)
                cur.fetchall()
                times.append((time.perf_counter() - start) * 1000)
            except Exception:
                return None
    return round(statistics.mean(times), 2) if times else None


def measure_oracle_query(sql: str, runs: int = REPEAT) -> float | None:
    try:
        import oracledb
    except ImportError:
        return None

    try:
        conn  = oracledb.connect(user="system", password="root",
                                 dsn="localhost:1521/FREEPDB1")
        times = []
        for _ in range(runs):
            try:
                cur   = conn.cursor()          # ← 매번 새 커서 생성
                start = time.perf_counter()
                cur.execute(sql)
                cur.fetchall()
                times.append((time.perf_counter() - start) * 1000)
                cur.close()                    # ← 매번 커서 닫기
            except Exception as e:
                print(f"       Oracle 쿼리 실패: {e}")
                try:
                    cur.close()
                except Exception:
                    pass
        conn.close()
        return round(statistics.mean(times), 2) if times else None
    except Exception as e:
        print(f"       Oracle 연결 실패: {e}")
        return None

# ══════════════════════════════════════════════════════════════
# 6. 전체 측정 실행
# ══════════════════════════════════════════════════════════════

def run_measurement(
    mysql_conn, query_pairs: list, db_name: str,
    skip_oracle: bool = False,
) -> list[dict]:
    print(f"\n  [before/after 실행시간 측정 — {REPEAT}회 평균]")

    oracle_available = False
    if not skip_oracle:
        try:
            import oracledb
            test = oracledb.connect(user="system", password="root",
                            dsn="localhost:1521/FREEPDB1")
            test.close()
            oracle_available = True
            print(f"  ✅ Oracle 연결 성공 — before_ms 실측 가능")
        except ImportError:
            print(f"  ⚠  cx_Oracle 미설치 → pip install cx_Oracle 후 Oracle 측정 가능")
        except Exception:
            print(f"  ⚠  Oracle 컨테이너 미실행 → before_ms = None")

    print(f"\n  {'패턴':<6} {'설명':<25} {'before_ms':>10} {'after_ms':>10} {'개선율':>8}")
    print(f"  {'-'*65}")

    results = []
    for q in query_pairs:
        # before (Oracle)
        if q["oracle"] and oracle_available and not skip_oracle:
            before_ms = measure_oracle_query(q["oracle"])
        else:
            before_ms = None

        # after (MySQL)
        after_ms = measure_mysql_query(mysql_conn, q["mysql"])

        # 개선율
        if before_ms and after_ms and before_ms > 0:
            improvement = round((before_ms - after_ms) / before_ms * 100, 1)
            impr_str = f"{improvement:+.1f}%"
        else:
            improvement = None
            impr_str = "-"

        b_str = f"{before_ms:.1f}" if before_ms else "N/A"
        a_str = f"{after_ms:.1f}"  if after_ms  else "ERR"
        print(f"  {q['pattern']:<6} {q['desc']:<25} {b_str:>10} {a_str:>10} {impr_str:>8}")

        # error_rate
        if before_ms and after_ms and before_ms > 0:
            error_rate = round(abs(before_ms - after_ms) / before_ms, 4)
        else:
            error_rate = 0.0

        results.append({
            "pattern":     q["pattern"],
            "risk":        q["risk"],
            "desc":        q["desc"],
            "oracle_sql":  q["oracle"] or "N/A",
            "mysql_sql":   q["mysql"],
            "before_ms":   before_ms,
            "after_ms":    after_ms,
            "improvement": improvement,
            "error_rate":  error_rate,
            "db_source":   db_name,
            "measured_at": datetime.now().isoformat(),
        })

    return results


# ══════════════════════════════════════════════════════════════
# 7. 결과 저장
# ══════════════════════════════════════════════════════════════

def save_results(results: list[dict]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "ds3_measure_result.csv"

    fields = [
        "pattern", "risk", "desc",
        "before_ms", "after_ms", "improvement", "error_rate",
        "db_source", "measured_at", "oracle_sql", "mysql_sql",
    ]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # 요약 출력
    measured = [r for r in results if r["after_ms"]]
    both     = [r for r in results if r["before_ms"] and r["after_ms"]]
    print(f"\n  {'='*55}")
    print(f"  측정 완료")
    print(f"  after_ms 측정 성공: {len(measured)}/{len(results)}건")
    print(f"  before+after 모두:  {len(both)}/{len(results)}건")
    if both:
        avg_impr = sum(r["improvement"] for r in both if r["improvement"]) / len(both)
        print(f"  평균 개선율:         {avg_impr:+.1f}%")
    print(f"  {'='*55}")
    print(f"\n  💾 {out_path}")
    print(f"  →Grid Search 입력값으로 활용")


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════

def main(setup: bool, skip_oracle: bool, use_bucket: bool):
    print(f"\n{'='*65}")
    print(f"  시나리오 B — DS3 Oracle vs MySQL 실행시간 실측")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  반복: {REPEAT}회 평균 | Oracle: {'생략' if skip_oracle else '시도'}")
    print(f"{'='*65}")

    # ── 컨테이너 상태 확인 ────────────────────────────────────
    check_containers()

    # ── MySQL 연결 ────────────────────────────────────────────
    try:
        mysql_conn, db_name, query_pairs = get_mysql_conn(use_bucket)
        print(f"\n  ✅ MySQL 연결 성공: {db_name}")
    except Exception as e:
        print(f"\n  ❌ MySQL 연결 실패: {e}")
        print(f"  docker-compose up -d 로 컨테이너를 실행하세요.")
        return

    # ── DS3 데이터 적재 (--setup) ─────────────────────────────
    if setup and "DS3" in db_name:
        setup_ds3_data(mysql_conn)

    # ── 데이터 현황 확인 ──────────────────────────────────────
    verify_data(mysql_conn, db_name)

    # ── 실행시간 측정 ─────────────────────────────────────────
    results = run_measurement(mysql_conn, query_pairs, db_name, skip_oracle)
    mysql_conn.close()

    # ── 결과 저장 ─────────────────────────────────────────────
    save_results(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시나리오 B — DS3 실행시간 실측")
    parser.add_argument("--setup",        action="store_true", help="DS3 MySQL 데이터 적재")
    parser.add_argument("--skip-oracle",  action="store_true", help="Oracle 측정 생략")
    parser.add_argument("--use-bucket",   action="store_true", help="bucketstore_dummy 사용")
    args = parser.parse_args()
    main(args.setup, args.skip_oracle, args.use_bucket)

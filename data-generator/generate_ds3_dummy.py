"""
generate_ds3_dummy.py — DS3 MySQL 100만건 더미 데이터 생성기
============================================================
적재 대상 (dvdstore-mysql, port 3308, db=DS3):
  - CUSTOMERS   20,000건 (기존 유지 — 재생성 생략 가능)
  - PRODUCTS    10,000건 (기존 유지 — 재생성 생략 가능)
  - INVENTORY   10,000건 (기존 유지 — 재생성 생략 가능)
  - ORDERS   1,000,000건  ← 핵심 (DS3 기본 12K → 100만건으로 확장)
  - ORDERLINES 약 2,900,000건 (ORDERS당 평균 2.9건)
  - CUST_HIST 1,000,000건 (ORDERS와 1:1)

실행 전 조건:
  - dvdstore-mysql 컨테이너 실행 중 (docker ps 확인)
  - DS3 기본 데이터 적재 완료 (python run_scenario_b.py --setup --skip-oracle)
  - pip install pymysql

실행:
  python generate_ds3_dummy.py              # ORDERS만 100만건 추가
  python generate_ds3_dummy.py --full       # CUSTOMERS/PRODUCTS 포함 전체 재생성
  python generate_ds3_dummy.py --count 500000  # 목표 건수 지정 (기본 1,000,000)
"""

import argparse
import random
import pymysql
from datetime import datetime, timedelta

# ── DB 접속 (DS3 MySQL, port 3308) ─────────────────────────────
DS3_CONFIG = dict(
    host='localhost',
    port=3308,
    user='root',
    password='root',
    db='DS3',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    local_infile=True,
)

# ── 생성 파라미터 ──────────────────────────────────────────────
CUSTOMER_COUNT  = 20_000
PRODUCT_COUNT   = 10_000
TARGET_ORDERS   = 1_000_000
BATCH_SIZE      = 10_000

# DS3 샘플 데이터 (실제 DS3와 동일한 패턴)
COUNTRIES   = ['US', 'UK', 'Germany', 'France', 'Japan', 'Korea', 'Canada', 'Australia']
CATEGORIES  = list(range(1, 17))   # DS3 category 1~16


def get_conn():
    return pymysql.connect(**DS3_CONFIG)


# ══════════════════════════════════════════════════════════════
# 1. 현재 데이터 현황 확인
# ══════════════════════════════════════════════════════════════

def check_current(conn) -> dict:
    print(f"\n  [현재 DS3 데이터 현황]")
    cur = conn.cursor()
    counts = {}
    for t in ['CUSTOMERS', 'PRODUCTS', 'INVENTORY', 'ORDERS', 'ORDERLINES', 'CUST_HIST']:
        try:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
            counts[t] = cur.fetchone()['cnt']
        except Exception:
            counts[t] = 0
        print(f"  {'✅' if counts[t] > 0 else '❌'} {t:<15}: {counts[t]:>12,}건")
    return counts


# ══════════════════════════════════════════════════════════════
# 2. CUSTOMERS 재생성 (--full 옵션)
# ══════════════════════════════════════════════════════════════

def insert_customers(conn, count=CUSTOMER_COUNT):
    print(f"\n  CUSTOMERS {count:,}건 생성 중...")
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE CUSTOMERS")
    conn.commit()

    sql = """INSERT INTO CUSTOMERS
        (customerid, firstname, lastname, address1, city, state, zip,
         country, phone, email, creditcardtype, creditcard,
         creditcardexpiration, username, password, age, income, gender)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    first_names = ['James','John','Robert','Michael','William','David','Mary','Patricia','Jennifer','Linda']
    last_names  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Wilson','Moore']
    states      = ['CA','NY','TX','FL','IL','PA','OH','GA','NC','MI']

    data = []
    for i in range(1, count + 1):
        data.append((
            i,
            random.choice(first_names),
            random.choice(last_names),
            f"{random.randint(100,9999)} Main St",
            f"City{random.randint(1,100)}",
            random.choice(states),
            f"{random.randint(10000,99999)}",
            random.choice(COUNTRIES),
            f"{random.randint(100,999)}-{random.randint(1000,9999)}",
            f"user{i:06d}@dell.com",
            random.randint(1, 5),
            f"{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
            f"{random.randint(2024,2029)}/{random.randint(1,12):02d}",
            f"user{i:06d}",
            "password",
            random.randint(18, 75),
            random.choice([30000, 50000, 70000, 100000, 150000]),
            random.choice(['M', 'F']),
        ))
        if len(data) == BATCH_SIZE:
            cur.executemany(sql, data)
            conn.commit()
            data = []

    if data:
        cur.executemany(sql, data)
        conn.commit()
    print(f"  ✅ CUSTOMERS {count:,}건 완료")
    return list(range(1, count + 1))


# ══════════════════════════════════════════════════════════════
# 3. PRODUCTS + INVENTORY 재생성 (--full 옵션)
# ══════════════════════════════════════════════════════════════

def insert_products(conn, count=PRODUCT_COUNT):
    print(f"\n  PRODUCTS + INVENTORY {count:,}건 생성 중...")
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE INVENTORY")
    cur.execute("TRUNCATE TABLE PRODUCTS")
    conn.commit()

    titles  = ['Action','Comedy','Drama','Horror','Sci-Fi','Romance','Thriller','Documentary']
    actors  = ['Actor A','Actor B','Actor C','Actor D','Actor E']

    prod_sql = """INSERT INTO PRODUCTS
        (prod_id, category, title, actor, price, special, common_prod_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s)"""
    inv_sql  = "INSERT INTO INVENTORY (prod_id, quan_in_stock, sales) VALUES (%s,%s,%s)"

    prod_data = []
    inv_data  = []
    for i in range(1, count + 1):
        prod_data.append((
            i,
            random.choice(CATEGORIES),
            f"{random.choice(titles)} {i:05d}",
            random.choice(actors),
            round(random.uniform(5.0, 50.0), 2),
            random.randint(0, 1),
            random.randint(1, count),
        ))
        inv_data.append((i, random.randint(0, 1000), random.randint(0, 5000)))

        if len(prod_data) == BATCH_SIZE:
            cur.executemany(prod_sql, prod_data)
            cur.executemany(inv_sql, inv_data)
            conn.commit()
            prod_data = []
            inv_data  = []

    if prod_data:
        cur.executemany(prod_sql, prod_data)
        cur.executemany(inv_sql, inv_data)
        conn.commit()
    print(f"  ✅ PRODUCTS + INVENTORY {count:,}건 완료")
    return list(range(1, count + 1))


# ══════════════════════════════════════════════════════════════
# 4. ORDERS 100만건 생성 (핵심)
# ══════════════════════════════════════════════════════════════

def insert_orders(conn, customer_ids, target=TARGET_ORDERS):
    print(f"\n  ORDERS {target:,}건 생성 중... (5~10분 소요 예상)")
    cur = conn.cursor()

    # 기존 데이터 확인
    cur.execute("SELECT MAX(orderid) as max_id, COUNT(*) as cnt FROM ORDERS")
    row = cur.fetchone()
    existing = row['cnt'] or 0
    start_id = (row['max_id'] or 0) + 1

    need = target - existing
    if need <= 0:
        print(f"  ✅ 이미 {existing:,}건 존재 — 추가 생성 불필요")
        cur.execute("SELECT orderid FROM ORDERS ORDER BY orderid")
        return [r['orderid'] for r in cur.fetchall()]

    print(f"  기존 {existing:,}건 + 추가 {need:,}건 = 목표 {target:,}건")

    sql = """INSERT INTO ORDERS
        (orderid, orderdate, customerid, netamount, tax, totalamount)
        VALUES (%s,%s,%s,%s,%s,%s)"""

    # 상위 5% 헤비바이어 (쿼리 성능 차이 극대화)
    heavy = customer_ids[:max(1, len(customer_ids) // 20)]
    normal = customer_ids[max(1, len(customer_ids) // 20):]

    base_date = datetime(2013, 1, 1)
    date_range = (datetime.now() - base_date).days

    data = []
    inserted = 0
    for i in range(need):
        oid = start_id + i
        cid = random.choice(heavy) if random.random() < 0.5 else random.choice(normal)
        net = round(random.uniform(10.0, 300.0), 2)
        tax = round(net * 0.08, 2)
        odate = base_date + timedelta(days=random.randint(0, date_range))
        data.append((oid, odate, cid, net, tax, round(net + tax, 2)))

        if len(data) == BATCH_SIZE:
            cur.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []
            pct = (existing + inserted) / target * 100
            print(f"  - {existing + inserted:>10,}건 ({pct:.1f}%)")

    if data:
        cur.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    total = existing + inserted
    print(f"  ✅ ORDERS {total:,}건 완료")

    cur.execute("SELECT orderid FROM ORDERS ORDER BY orderid")
    return [r['orderid'] for r in cur.fetchall()]


# ══════════════════════════════════════════════════════════════
# 5. ORDERLINES 생성
# ══════════════════════════════════════════════════════════════

def insert_orderlines(conn, order_ids, product_ids):
    print(f"\n  ORDERLINES 생성 중... (~{len(order_ids)*3//1000}K건 예상, 5~10분 소요)")
    cur = conn.cursor()

    # 기존 건수 확인
    cur.execute("SELECT COUNT(*) as cnt FROM ORDERLINES")
    existing = cur.fetchone()['cnt']

    # 기존에 없는 order_id만 처리
    cur.execute("SELECT DISTINCT orderid FROM ORDERLINES")
    done_ids = {r['orderid'] for r in cur.fetchall()}
    pending  = [oid for oid in order_ids if oid not in done_ids]

    if not pending:
        print(f"  ✅ 이미 {existing:,}건 존재 — 추가 생성 불필요")
        return

    print(f"  추가 처리 대상: {len(pending):,}건 주문")

    sql = """INSERT INTO ORDERLINES
         (orderlineid, orderid, prod_id, quantity, orderdate)
         VALUES (%s,%s,%s,%s,%s)"""

    base_date  = datetime(2013, 1, 1)
    date_range = (datetime.now() - base_date).days

    data = []
    inserted = 0
    ol_id = existing + 1  
    for oid in pending:
        n = random.randint(1, 5)
        odate = base_date + timedelta(days=random.randint(0, date_range))
        for _ in range(n):
            data.append((ol_id, oid, random.choice(product_ids), random.randint(1, 5), odate))
            ol_id += 1

        if len(data) >= BATCH_SIZE:
            cur.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []
            if inserted % 100_000 == 0:
                print(f"  - ORDERLINES {existing + inserted:>10,}건")

    if data:
        cur.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    print(f"  ✅ ORDERLINES {existing + inserted:,}건 완료")


# ══════════════════════════════════════════════════════════════
# 6. CUST_HIST 생성
# ══════════════════════════════════════════════════════════════

def insert_cust_hist(conn, order_ids, customer_ids, product_ids):
    print(f"\n  CUST_HIST {len(order_ids):,}건 생성 중...")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as cnt FROM CUST_HIST")
    existing = cur.fetchone()['cnt']
    if existing >= len(order_ids):
        print(f"  ✅ 이미 {existing:,}건 존재 — 추가 생성 불필요")
        return

    cur.execute("SELECT DISTINCT orderid FROM CUST_HIST")
    done_ids = {r['orderid'] for r in cur.fetchall()}
    pending  = [oid for oid in order_ids if oid not in done_ids]

    sql = "INSERT INTO CUST_HIST (customerid, orderid, prod_id) VALUES (%s,%s,%s)"
    data = []
    inserted = 0
    for oid in pending:
        data.append((random.choice(customer_ids), oid, random.choice(product_ids)))
        if len(data) == BATCH_SIZE:
            cur.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []

    if data:
        cur.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    print(f"  ✅ CUST_HIST {existing + inserted:,}건 완료")


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DS3 MySQL 더미 데이터 생성기")
    parser.add_argument("--full",  action="store_true",
                        help="CUSTOMERS/PRODUCTS 포함 전체 재생성")
    parser.add_argument("--count", type=int, default=TARGET_ORDERS,
                        help=f"ORDERS 목표 건수 (기본 {TARGET_ORDERS:,})")
    args = parser.parse_args()

    target = args.count

    print(f"\n{'='*60}")
    print(f"  DS3 더미 데이터 생성 시작 — {datetime.now().strftime('%H:%M:%S')}")
    print(f"  대상: dvdstore-mysql (port 3308, db=DS3)")
    print(f"  목표: ORDERS {target:,}건")
    print(f"{'='*60}")

    conn = get_conn()

    try:
        # 현황 확인
        counts = check_current(conn)

        # CUSTOMERS
        if args.full or counts['CUSTOMERS'] == 0:
            customer_ids = insert_customers(conn, CUSTOMER_COUNT)
        else:
            cur = conn.cursor()
            cur.execute("SELECT customerid FROM CUSTOMERS ORDER BY customerid")
            customer_ids = [r['customerid'] for r in cur.fetchall()]
            print(f"\n  CUSTOMERS {len(customer_ids):,}건 기존 데이터 사용")

        # PRODUCTS
        if args.full or counts['PRODUCTS'] == 0:
            product_ids = insert_products(conn, PRODUCT_COUNT)
        else:
            cur = conn.cursor()
            cur.execute("SELECT prod_id FROM PRODUCTS ORDER BY prod_id")
            product_ids = [r['prod_id'] for r in cur.fetchall()]
            print(f"  PRODUCTS  {len(product_ids):,}건 기존 데이터 사용")

        # ORDERS 100만건
        order_ids = insert_orders(conn, customer_ids, target)

        # ORDERLINES
        insert_orderlines(conn, order_ids, product_ids)

        # CUST_HIST
        insert_cust_hist(conn, order_ids, customer_ids, product_ids)

    finally:
        conn.close()

    # 최종 확인
    conn = get_conn()
    print(f"\n{'='*60}")
    print(f"  ✅ DS3 더미 데이터 생성 완료 — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    cur = conn.cursor()
    for t in ['CUSTOMERS','PRODUCTS','INVENTORY','ORDERS','ORDERLINES','CUST_HIST']:
        try:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
            cnt = cur.fetchone()['cnt']
            goal = " ✅ 목표 달성!" if t == 'ORDERS' and cnt >= target else ""
            print(f"  {t:<15}: {cnt:>12,}건{goal}")
        except Exception:
            print(f"  {t:<15}: 조회 실패")
    conn.close()

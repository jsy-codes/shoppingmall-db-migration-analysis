"""
setup_oracle_ds3.py — Oracle Free 컨테이너에 DS3 데이터 적재
=============================================================
실행:
  python setup_oracle_ds3.py
"""

import csv
import oracledb
from pathlib import Path

DATA_DIR = Path(__file__).parent / "public-DB" / "dvdstore" / "data_files"
ORACLE_DSN = "localhost:1521/FREEPDB1"

print("\n  Oracle DS3 데이터 적재 시작\n")

conn = oracledb.connect(user="system", password="root", dsn=ORACLE_DSN)
cur  = conn.cursor()

# ── 기존 데이터 초기화 ─────────────────────────────────────
for tbl in ["CUST_HIST", "ORDERLINES", "ORDERS", "INVENTORY", "PRODUCTS", "CUSTOMERS"]:
    try:
        cur.execute(f"TRUNCATE TABLE {tbl}")
        print(f"  TRUNCATE {tbl}")
    except Exception as e:
        print(f"  ⚠  TRUNCATE {tbl} 실패: {e}")
conn.commit()

# ── CUSTOMERS ──────────────────────────────────────────────
rows = []
for fname in ["row_cust.csv", "us_cust.csv"]:
    fpath = DATA_DIR / "cust" / fname
    if not fpath.exists():
        continue
    with open(fpath, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for r in reader:
            if r and len(r) >= 20:
                rows.append(r[:20])

if rows:
    # CSV 컬럼 순서: 0=customerid, 1=firstname, 2=lastname, 3=address1,
    # 4=address2(skip), 5=city, 6=state, 7=zip, 8=country,
    # 9=creditcardtype, 10=email, 11=phone, 12=unknown(skip),
    # 13=creditcard, 14=creditcardexpiration, 15=username,
    # 16=password, 17=age, 18=income, 19=gender
    mapped = [
        (r[0],r[1],r[2],r[3],r[5],r[6],r[7],r[8],
         r[11],r[10],r[9],r[13],r[14],r[15],r[16],r[17],r[18],r[19])
        for r in rows
    ]
    cur.executemany(
        """INSERT INTO CUSTOMERS
           (customerid,firstname,lastname,address1,city,state,zip,country,
            phone,email,creditcardtype,creditcard,creditcardexpiration,
            username,password,age,income,gender)
           VALUES(:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18)""",
        mapped
    )
    conn.commit()
    print(f"  ✅ CUSTOMERS: {len(rows)}건")

# ── PRODUCTS ───────────────────────────────────────────────
rows = []
fpath = DATA_DIR / "prod" / "prod.csv"
if fpath.exists():
    with open(fpath, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for r in reader:
            if r and len(r) >= 7:
                rows.append(r[:7])
if rows:
    cur.executemany(
        """INSERT INTO PRODUCTS
           (prod_id,category,title,actor,price,special,common_prod_id)
           VALUES(:1,:2,:3,:4,:5,:6,:7)""",
        rows
    )
    conn.commit()
    print(f"  ✅ PRODUCTS: {len(rows)}건")

# ── INVENTORY ──────────────────────────────────────────────
rows = []
fpath = DATA_DIR / "prod" / "inv.csv"
if fpath.exists():
    with open(fpath, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for r in reader:
            if r and len(r) >= 3:
                rows.append(r[:3])
if rows:
    cur.executemany(
        "INSERT INTO INVENTORY (prod_id,quan_in_stock,sales) VALUES(:1,:2,:3)",
        rows
    )
    conn.commit()
    print(f"  ✅ INVENTORY: {len(rows)}건")

# ── ORDERS (12개월) ────────────────────────────────────────
months = ["jan","feb","mar","apr","may","jun",
          "jul","aug","sep","oct","nov","dec"]
total_orders = 0
for month in months:
    fpath = DATA_DIR / "orders" / f"{month}_orders.csv"
    if not fpath.exists():
        continue
    rows = []
    with open(fpath, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for r in reader:
            if r and len(r) >= 6:
                rows.append(r[:6])
    if rows:
        cur.executemany(
            """INSERT INTO ORDERS
               (orderid,orderdate,customerid,netamount,tax,totalamount)
               VALUES(:1,TO_DATE(:2,'YYYY-MM-DD'),:3,:4,:5,:6)""",
            rows
        )
        conn.commit()
        total_orders += len(rows)
print(f"  ✅ ORDERS: {total_orders}건")

# ── ORDERLINES (12개월) ────────────────────────────────────
total_ol = 0
for month in months:
    fpath = DATA_DIR / "orders" / f"{month}_orderlines.csv"
    if not fpath.exists():
        continue
    rows = []
    with open(fpath, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for r in reader:
            if r and len(r) >= 5:
                rows.append(r[:5])
    if rows:
        try:
            cur.executemany(
                """INSERT INTO ORDERLINES
                   (orderlineid,orderid,prod_id,quantity,orderdate)
                   VALUES(:1,:2,:3,:4,TO_DATE(:5,'YYYY-MM-DD'))""",
                rows
            )
            conn.commit()
            total_ol += len(rows)
        except Exception as e:
            conn.rollback()
            print(f"  ⚠  ORDERLINES {month} 실패: {e}")
print(f"  ✅ ORDERLINES: {total_ol}건")

conn.close()

print(f"\n  ✅ Oracle DS3 데이터 적재 완료\n")

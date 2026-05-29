import mysql.connector
import csv
import json
import os
# check_consistency.py

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 체크섬용 (패턴 테스트 테이블: type_test)
conn_type = mysql.connector.connect(
    host="localhost", user="root", password="1234", database="type_test"
)
cursor = conn_type.cursor(buffered=True)

# ── 변환 전후 비교용 (실제 서비스 테이블: bucket_store)
conn_store = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", "1234"),
    database=os.getenv("MYSQL_DATABASE", "bucket_store"),
)
cursor_store = conn_store.cursor(buffered=True)

# ── 1. 테이블 Row Count + Checksum (type_test) ─────────────────
tables = [
    "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t10",
    "t23", "t24", "t25_new", "t27", "t29", "t30_new",
    "tree", "sales", "a", "b"
]

checksum_results = []
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        cursor.execute(f"CHECKSUM TABLE {table}")
        checksum = cursor.fetchone()[1]
        checksum_results.append([table, row_count, checksum, "OK"])
        print(f"[CHECKSUM] {table}: rows={row_count}, checksum={checksum}")
    except Exception as e:
        checksum_results.append([table, "-", "-", str(e)])
        print(f"[CHECKSUM] {table}: ERROR - {e}")

out_checksum = os.path.join(BASE_DIR, "consistency_check.csv")
with open(out_checksum, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["table", "row_count", "checksum", "status"])
    writer.writerows(checksum_results)

# ── 2. SQL 변환 전후 결과 비교 (bucket_store) ──────────────────
experiment_csv = os.path.join(BASE_DIR, "experiment_results.csv")
compare_results = []

def safe_execute(cur, sql):
    try:
        clean = sql.strip()
        if clean.upper().startswith("EXPLAIN"):
            clean = clean[7:].strip()
        cur.execute(clean)
        rows = cur.fetchall()
        return rows, None
    except Exception as e:
        return None, str(e)

def rows_match(before_rows, after_rows):
    if before_rows is None or after_rows is None:
        return False
    try:
        norm_before = sorted([tuple(str(v) for v in r) for r in before_rows])
        norm_after  = sorted([tuple(str(v) for v in r) for r in after_rows])
        return norm_before == norm_after
    except Exception:
        return False

if os.path.exists(experiment_csv):
    with open(experiment_csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        print(f"[DEBUG] CSV 헤더: {reader.fieldnames}")
        for row in reader:
            pid        = row["pattern_id"].split("_")[0]
            sql_before = row["sql_before"]
            sql_after  = row["sql_after"]

            before_rows, before_err = safe_execute(cursor_store, sql_before)
            after_rows,  after_err  = safe_execute(cursor_store, sql_after)

            match = rows_match(before_rows, after_rows)

            before_count = len(before_rows) if before_rows is not None else "-"
            after_count  = len(after_rows)  if after_rows  is not None else "-"

            status = "MATCH" if match else ("ERROR" if (before_err or after_err) else "MISMATCH")

            compare_results.append({
                "pattern_id":   pid,
                "pattern_name": row["pattern_name"],
                "risk":         row["risk"],
                "before_rows":  before_count,
                "after_rows":   after_count,
                "result_match": status,
                "before_error": before_err or "",
                "after_error":  after_err  or "",
            })

            print(f"[COMPARE] {pid}: before={before_count}rows, after={after_count}rows → {status}")
else:
    print(f"[WARN] experiment_results.csv 없음: {experiment_csv}")

out_compare = os.path.join(BASE_DIR, "result_compare.csv")
if compare_results:
    with open(out_compare, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=compare_results[0].keys())
        writer.writeheader()
        writer.writerows(compare_results)
    print(f"\n[DONE] 결과 비교 → {out_compare}")

print(f"[DONE] 체크섬 → {out_checksum}")

conn_type.close()
conn_store.close()
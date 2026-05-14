import mysql.connector
import csv
import os

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="type_test"
)
cursor = conn.cursor(buffered=True)

BASE_DIR = os.path.dirname(__file__)

# type_test에 실제 존재하는 테이블
tables = [
    "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t10",
    "t23", "t24", "t25_new", "t27", "t29", "t30_new",
    "tree", "sales", "a", "b"
]

results = []

for table in tables:
    try:
        # Row Count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]

        # Checksum
        cursor.execute(f"CHECKSUM TABLE {table}")
        checksum = cursor.fetchone()[1]

        results.append([table, row_count, checksum, "OK"])
        print(f"{table}: rows={row_count}, checksum={checksum}")

    except Exception as e:
        results.append([table, "-", "-", str(e)])
        print(f"{table}: ERROR - {e}")

out = os.path.join(BASE_DIR, "consistency_check.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["table", "row_count", "checksum", "status"])
    writer.writerows(results)

print("\nDONE →", out)
import mysql.connector
import os
import csv

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="type_test"
)

# ✅ 여기 수정
cursor = conn.cursor(buffered=True)

BASE_DIR = os.path.dirname(__file__)

sql_files = [
    "P01.sql", "P02.sql", "P03.sql", "P04.sql", "P05.sql",
    "P06.sql", "P07.sql", "P08.sql", "P09.sql", "P10.sql",
    # 2주차 추가
    "P23.sql", "P24.sql", "P25.sql", "P26.sql",
    "P27.sql", "P28.sql", "P29.sql", "P30.sql",
]

results = []


def run_sql_file(filename):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    queries = sql_script.split(";")
    errors = []

    for q in queries:
        q = q.strip()
        if not q:
            continue
        try:
            cursor.execute(q)
        except Exception as e:
            errors.append(str(e))

    conn.commit()  # ← 추가
    return errors if errors else "OK"


for file in sql_files:

    print("RUN:", file)

    result = run_sql_file(file)

    results.append([file, result])


csv_path = os.path.join(BASE_DIR, "result.csv")

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["file", "result"])
    writer.writerows(results)

print("DONE")
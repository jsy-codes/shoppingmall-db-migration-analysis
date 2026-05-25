import mysql.connector

# 🚨 비밀번호만 형님의 찐 로컬 비번(예: 0827, 1234 등)으로 바꾸십쇼!
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "0827", 
    "database": "bucket_store"
}

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print("🚀 더미 데이터 5만 건 주입 시작! (약 3~5초 소요)")

    # 1. members 데이터 1,000명 장전
    members = [(i, f"user{i}", f"test{i}@test.com") for i in range(1, 1001)]
    cursor.executemany("INSERT IGNORE INTO members (id, name, email) VALUES (%s, %s, %s)", members)

    # 2. orders 데이터 5만 건 장전
    orders = [(i, (i%1000)+1, f"STATUS_{(i%20)+1}", f"2024-01-{(i%28)+1:02d} 12:00:00") for i in range(1, 50001)]
    cursor.executemany("INSERT IGNORE INTO orders (id, member_id, status, created_at) VALUES (%s, %s, %s, %s)", orders)

    conn.commit()
    print("✅ 데이터 주입 완벽하게 끝났습니다! 이제 experiments.py 돌리십쇼!")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
finally:
    if 'cursor' in locals(): cursor.close()
    if 'conn' in locals(): conn.close()
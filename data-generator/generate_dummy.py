import pymysql
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('ko_KR')

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1234', 
    db='bucket_store',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

def insert_members(count=10000):
    print("MEMBERS 데이터 삽입 중...")
    sql = "INSERT INTO MEMBERS (id, name, email, status, created_at) VALUES (%s, %s, %s, %s, %s)"
    data = []
    for i in range(1, count + 1):
        member_id = str(10000 + i) 
        name = fake.name()
        email = fake.unique.email()
        status = random.choice(['ACTIVE', 'INACTIVE', 'SLEEP'])
        created_at = fake.date_time_between(start_date='-2y', end_date='now')
        data.append((member_id, name, email, status, created_at))
    
    cursor.executemany(sql, data)
    conn.commit()
    return [d[0] for d in data] 

def insert_orders(member_ids, count=100000):
    print(f"ORDERS 데이터 {count}건 삽입 중... (시간이 조금 걸릴 수 있습니다)")
    sql = "INSERT INTO ORDERS (member_id, status, total_amount, created_at) VALUES (%s, %s, %s, %s)"
    data = []
    
    heavy_buyers = member_ids[:int(len(member_ids)*0.05)]
    normal_buyers = member_ids[int(len(member_ids)*0.05):]

    for _ in range(count):
        if random.random() < 0.5:
            m_id = random.choice(heavy_buyers)
        else:
            m_id = random.choice(normal_buyers)
            
        status = random.choice(['PENDING', 'COMPLETE', 'CANCELLED', 'REFUNDED'])
        total_amount = round(random.uniform(10000, 500000), 4) 
        created_at = fake.date_time_between(start_date='-1y', end_date='now')
        
        data.append((m_id, status, total_amount, created_at))
        
        if len(data) == 10000:
            cursor.executemany(sql, data)
            conn.commit()
            data = []
            print("  - 10,000건 적재 완료...")

    if data:
        cursor.executemany(sql, data)
        conn.commit()

try:
    member_ids = insert_members(10000) 
    
    # TODO: CATEGORIES, PRODUCTS 삽입 로직은 유사한 패턴으로 추가 작성
    
    insert_orders(member_ids, 100000) 
    
    print("✅ 모든 더미 데이터 적재가 완료되었습니다!")

except Exception as e:
    print(f"오류 발생: {e}")
finally:
    cursor.close()
    conn.close()
"""
Oracle -> MySQL 마이그레이션 EXPLAIN 실험용 더미 데이터 생성기
============================================================
적재 대상:
  - MEMBERS      10,000건
  - CATEGORIES      100건 (대/중/소 3단계 계층)
  - PRODUCTS      5,000건
  - COUPONS      20,000건
  - ORDERS    1,000,000건  ← EXPLAIN 실험 핵심
  - ORDER_ITEMS 2,000,000건 (ORDERS당 평균 2건)
  - PAYMENTS    1,000,000건

실행 전 조건:
  - Docker MySQL 컨테이너가 실행 중이어야 함 (docker ps 확인)
  - pip install pymysql faker

실행:
  python generate_dummy.py
"""

import pymysql
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('ko_KR')

# ── DB 접속 정보 ──────────────────────────────────────────────
conn = pymysql.connect(
    host='localhost',
    port=3307,               # docker-compose에서 3307로 변경했으므로
    user='root',
    password='root',         # docker-compose MYSQL_ROOT_PASSWORD
    db='bucketstore_dummy',  # docker-compose MYSQL_DATABASE
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

# ── 외래키 제약 임시 해제 (적재 순서 유연하게) ────────────────
cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
conn.commit()


# ──────────────────────────────────────────────────────────────
# 1. CATEGORIES (100건 — 대/중/소 3단계 계층)
# ──────────────────────────────────────────────────────────────
def insert_categories():
    print("CATEGORIES 데이터 삽입 중...")
    cursor.execute("DELETE FROM CATEGORIES")
    conn.commit()

    top_categories = ["전자제품", "의류", "식품", "스포츠", "도서", "뷰티", "가구", "완구", "자동차용품", "반려동물"]
    mid_map = {
        "전자제품": ["스마트폰", "노트북", "태블릿", "카메라", "TV"],
        "의류":    ["남성의류", "여성의류", "아동의류", "속옷", "아웃도어"],
        "식품":    ["신선식품", "가공식품", "음료", "과자", "건강식품"],
        "스포츠":  ["헬스용품", "구기종목", "수영", "자전거", "등산"],
        "도서":    ["소설", "자기계발", "IT기술서", "만화", "어린이책"],
        "뷰티":    ["스킨케어", "메이크업", "헤어케어", "향수", "바디케어"],
        "가구":    ["침실가구", "거실가구", "주방가구", "수납", "조명"],
        "완구":    ["블록", "인형", "보드게임", "RC카", "교육완구"],
        "자동차용품": ["카오디오", "내비게이션", "세차용품", "안전용품", "타이어용품"],
        "반려동물": ["개용품", "고양이용품", "사료", "간식", "미용용품"],
    }

    category_ids = []
    cat_id = 1

    for top in top_categories:
        cursor.execute(
            "INSERT INTO CATEGORIES (id, parent_id, name) VALUES (%s, %s, %s)",
            (cat_id, None, top)
        )
        top_id = cat_id
        cat_id += 1

        for mid in mid_map[top]:
            cursor.execute(
                "INSERT INTO CATEGORIES (id, parent_id, name) VALUES (%s, %s, %s)",
                (cat_id, top_id, mid)
            )
            category_ids.append(cat_id)
            cat_id += 1

    conn.commit()
    print(f"  → CATEGORIES {cat_id - 1}건 완료")
    return category_ids


# ──────────────────────────────────────────────────────────────
# 2. MEMBERS (10,000건)
# ──────────────────────────────────────────────────────────────
def insert_members(count=10000):
    print(f"MEMBERS 데이터 {count}건 삽입 중...")
    cursor.execute("DELETE FROM MEMBERS")
    conn.commit()

    sql = "INSERT INTO MEMBERS (id, name, email, status, created_at) VALUES (%s, %s, %s, %s, %s)"
    data = []
    for i in range(1, count + 1):
        member_id = str(10000 + i)
        name = fake.name()
        email = f"user{10000 + i}@testmail.com"   # unique.email()은 100만건 생성시 느려서 패턴으로 대체
        status = random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'INACTIVE', 'SLEEP'])  # ACTIVE 비중 높게
        created_at = fake.date_time_between(start_date='-2y', end_date='now')
        data.append((member_id, name, email, status, created_at))

        if len(data) == 1000:
            cursor.executemany(sql, data)
            conn.commit()
            data = []

    if data:
        cursor.executemany(sql, data)
        conn.commit()

    print(f"  → MEMBERS {count}건 완료")
    return [str(10000 + i) for i in range(1, count + 1)]


# ──────────────────────────────────────────────────────────────
# 3. PRODUCTS (5,000건)
# ──────────────────────────────────────────────────────────────
def insert_products(category_ids, count=5000):
    print(f"PRODUCTS 데이터 {count}건 삽입 중...")
    cursor.execute("DELETE FROM PRODUCTS")
    conn.commit()

    sql = "INSERT INTO PRODUCTS (category_id, product_name, price, stock_quantity) VALUES (%s, %s, %s, %s)"
    data = []
    product_ids = []

    for i in range(1, count + 1):
        category_id = random.choice(category_ids)
        product_name = f"{fake.word()} {fake.word()} {random.randint(100, 999)}호"
        price = round(random.uniform(1000, 500000), 4)
        stock_quantity = random.randint(0, 1000)
        data.append((category_id, product_name, price, stock_quantity))

        if len(data) == 1000:
            cursor.executemany(sql, data)
            conn.commit()
            # 방금 적재된 product id 수집
            cursor.execute("SELECT id FROM PRODUCTS ORDER BY id DESC LIMIT %s", (len(data),))
            rows = cursor.fetchall()
            product_ids.extend([r['id'] for r in rows])
            data = []

    if data:
        cursor.executemany(sql, data)
        conn.commit()

    # 전체 product id 재조회 (순서 보장)
    cursor.execute("SELECT id FROM PRODUCTS ORDER BY id")
    product_ids = [r['id'] for r in cursor.fetchall()]

    print(f"  → PRODUCTS {count}건 완료")
    return product_ids


# ──────────────────────────────────────────────────────────────
# 4. COUPONS (20,000건)
# ──────────────────────────────────────────────────────────────
def insert_coupons(member_ids, count=20000):
    print(f"COUPONS 데이터 {count}건 삽입 중...")
    cursor.execute("DELETE FROM COUPONS")
    conn.commit()

    sql = "INSERT INTO COUPONS (member_id, coupon_code, discount_amount, valid_until) VALUES (%s, %s, %s, %s)"
    data = []

    for i in range(1, count + 1):
        member_id = random.choice(member_ids)
        coupon_code = f"CPN{i:08d}"
        discount_amount = round(random.choice([1000, 2000, 3000, 5000, 10000, 0]), 4)
        valid_until = fake.date_time_between(start_date='-6m', end_date='+6m')
        data.append((member_id, coupon_code, discount_amount, valid_until))

        if len(data) == 1000:
            cursor.executemany(sql, data)
            conn.commit()
            data = []

    if data:
        cursor.executemany(sql, data)
        conn.commit()

    print(f"  → COUPONS {count}건 완료")


# ──────────────────────────────────────────────────────────────
# 5. ORDERS (1,000,000건) ← EXPLAIN 실험 핵심
# ──────────────────────────────────────────────────────────────
def insert_orders(member_ids, count=1000000):
    print(f"ORDERS 데이터 {count:,}건 삽입 중... (5~10분 소요 예상)")
    cursor.execute("DELETE FROM ORDERS")
    conn.commit()

    sql = "INSERT INTO ORDERS (member_id, status, total_amount, created_at) VALUES (%s, %s, %s, %s)"
    data = []

    # 상위 5% 헤비바이어 패턴 (쿼리 성능 차이를 극대화하기 위해)
    heavy_buyers = member_ids[:int(len(member_ids) * 0.05)]
    normal_buyers = member_ids[int(len(member_ids) * 0.05):]

    inserted = 0
    for _ in range(count):
        if random.random() < 0.5:
            m_id = random.choice(heavy_buyers)
        else:
            m_id = random.choice(normal_buyers)

        status = random.choice(['PENDING', 'COMPLETE', 'COMPLETE', 'COMPLETE', 'CANCELLED', 'REFUNDED'])
        total_amount = round(random.uniform(10000, 500000), 4)
        created_at = fake.date_time_between(start_date='-1y', end_date='now')
        data.append((m_id, status, total_amount, created_at))

        if len(data) == 10000:
            cursor.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []
            print(f"  - {inserted:>10,}건 적재 완료...")

    if data:
        cursor.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    print(f"  → ORDERS {inserted:,}건 완료")

    # 전체 order id 반환
    cursor.execute("SELECT id FROM ORDERS ORDER BY id")
    return [r['id'] for r in cursor.fetchall()]


# ──────────────────────────────────────────────────────────────
# 6. ORDER_ITEMS (ORDERS당 평균 2건 = 약 200만건)
# ──────────────────────────────────────────────────────────────
def insert_order_items(order_ids, product_ids, avg_items=2):
    total = len(order_ids) * avg_items
    print(f"ORDER_ITEMS 데이터 약 {total:,}건 삽입 중... (5~10분 소요 예상)")
    cursor.execute("DELETE FROM ORDER_ITEMS")
    conn.commit()

    sql = "INSERT INTO ORDER_ITEMS (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)"
    data = []
    inserted = 0

    for order_id in order_ids:
        item_count = random.randint(1, 3)
        for _ in range(item_count):
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 5)
            unit_price = round(random.uniform(1000, 300000), 4)
            data.append((order_id, product_id, quantity, unit_price))

        if len(data) >= 10000:
            cursor.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []
            print(f"  - {inserted:>10,}건 적재 완료...")

    if data:
        cursor.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    print(f"  → ORDER_ITEMS {inserted:,}건 완료")


# ──────────────────────────────────────────────────────────────
# 7. PAYMENTS (ORDERS와 1:1)
# ──────────────────────────────────────────────────────────────
def insert_payments(order_ids):
    total = len(order_ids)
    print(f"PAYMENTS 데이터 {total:,}건 삽입 중... (5~10분 소요 예상)")
    cursor.execute("DELETE FROM PAYMENTS")
    conn.commit()

    sql = "INSERT INTO PAYMENTS (order_id, payment_method, amount, payment_date) VALUES (%s, %s, %s, %s)"
    data = []
    inserted = 0

    for order_id in order_ids:
        payment_method = random.choice(['CARD', 'CARD', 'CARD', 'BANK', 'KAKAO', 'NAVER'])
        amount = round(random.uniform(10000, 500000), 4)
        payment_date = fake.date_time_between(start_date='-1y', end_date='now')
        data.append((order_id, payment_method, amount, payment_date))

        if len(data) == 10000:
            cursor.executemany(sql, data)
            conn.commit()
            inserted += len(data)
            data = []
            print(f"  - {inserted:>10,}건 적재 완료...")

    if data:
        cursor.executemany(sql, data)
        conn.commit()
        inserted += len(data)

    print(f"  → PAYMENTS {inserted:,}건 완료")


# ──────────────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────────────
try:
    start = datetime.now()
    print(f"\n{'='*55}")
    print(f"  더미 데이터 생성 시작 — {start.strftime('%H:%M:%S')}")
    print(f"{'='*55}\n")

    category_ids = insert_categories()
    member_ids   = insert_members(10000)
    product_ids  = insert_products(category_ids, 5000)
    insert_coupons(member_ids, 20000)
    order_ids    = insert_orders(member_ids, 1000000)
    insert_order_items(order_ids, product_ids)
    insert_payments(order_ids)

    # 외래키 제약 복원
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()

    end = datetime.now()
    elapsed = end - start
    print(f"\n{'='*55}")
    print(f"  ✅ 모든 더미 데이터 적재 완료!")
    print(f"  소요 시간: {elapsed}")
    print(f"{'='*55}\n")

    # 적재 결과 요약
    for table in ['MEMBERS', 'CATEGORIES', 'PRODUCTS', 'COUPONS', 'ORDERS', 'ORDER_ITEMS', 'PAYMENTS']:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        result = cursor.fetchone()
        print(f"  {table:<15} {result['cnt']:>12,}건")

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

finally:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()
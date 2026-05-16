"""
Oracle -> MySQL 마이그레이션 시뮬레이터 탐지 검증 스크립트
=====================================================
용도: bad_queries 50종을 /diagnose API에 전송하여
      예상 패턴 ID와 실제 탐지 결과를 비교하고
      미탐지 항목을 리포트로 출력한다.

실행 전 조건:
  - 백엔드 서버가 http://localhost:8000 에서 실행 중이어야 함
  - pip install requests 되어 있어야 함

실행:
  python check_simulator.py
  python check_simulator.py --out report.md   # 결과를 파일로 저장
"""

import requests
import json
import argparse
from datetime import datetime

API_URL = "http://localhost:8000/simulate"

# ── 50개 쿼리 + 예상 패턴 정의 ─────────────────────────────────
QUERIES = [
    # (쿼리ID, SQL, 예상패턴ID 목록, 비고)
    ("Q01", "SELECT id, member_id FROM ORDERS WHERE member_id = 10050;",
     ["P01"], "VARCHAR FK에 숫자 비교 → 암묵적 형변환"),

    ("Q02", "SELECT * FROM PAYMENTS WHERE id + 0 = 100;",
     ["P01"], "id에 +0 산술 연산 → 인덱스 배제"),

    ("Q03", "SELECT * FROM MEMBERS WHERE id > 10000 AND id < 20000;",
     ["P01"], "VARCHAR PK를 숫자 범위 비교"),

    ("Q04", "SELECT id, email FROM MEMBERS WHERE UPPER(email) LIKE '%@GMAIL.COM%';",
     ["P02"], "UPPER + 양방향 와일드카드"),

    ("Q05", "SELECT * FROM PRODUCTS WHERE SUBSTR(product_name, 1, 3) = 'MAC';",
     ["P02"], "SUBSTR로 인덱스 무력화"),

    ("Q06", "SELECT * FROM MEMBERS WHERE REPLACE(name, ' ', '') = '이동훈';",
     ["P02"], "REPLACE로 인덱스 무력화"),

    ("Q07", "SELECT * FROM ORDERS WHERE status = 'PENDING' AND ROWNUM <= 100;",
     ["P03"], "조건절 + ROWNUM"),

    ("Q08", "SELECT id, total_amount FROM ORDERS WHERE ROWNUM <= 10 ORDER BY total_amount DESC;",
     ["P03"], "ROWNUM + ORDER BY 논리 오류"),

    ("Q09", "SELECT * FROM (SELECT id, created_at FROM ORDERS ORDER BY created_at DESC) WHERE ROWNUM BETWEEN 11 AND 20;",
     ["P03"], "서브쿼리 내 ROWNUM BETWEEN"),

    ("Q10", "SELECT * FROM ORDERS WHERE NVL(member_id, '0') = '10050';",
     ["P04"], "NVL로 인덱스 무력화"),

    ("Q11", "SELECT id FROM COUPONS WHERE NVL(discount_amount, 0) + 1000 > 5000;",
     ["P04"], "NVL + 산술 연산"),

    ("Q12", "SELECT * FROM PRODUCTS ORDER BY NVL(stock_quantity, 0) DESC;",
     ["P04"], "ORDER BY NVL → Filesort"),

    ("Q13", "SELECT * FROM ORDERS WHERE DATE(created_at) = '2025-05-08';",
     ["P05"], "DATE() 함수로 인덱스 무력화"),

    ("Q14", "SELECT * FROM PAYMENTS WHERE CAST(payment_date AS DATE) = '2025-05-01';",
     ["P05"], "CAST(... AS DATE) 형변환"),

    ("Q15", "SELECT * FROM ORDERS WHERE created_at + 1 >= '2025-05-09';",
     ["P05"], "날짜 컬럼 산술 연산"),

    ("Q16", "CREATE TEMPORARY TABLE temp_vip_users (user_id VARCHAR2(50), grade VARCHAR2(10));",
     ["P06"], "Oracle 전용 타입 VARCHAR2"),

    ("Q17", "SELECT * FROM ORDERS WHERE TRIM(status) = 'COMPLETE';",
     ["P07"], "TRIM으로 인덱스 무력화"),

    ("Q18", "SELECT * FROM PAYMENTS WHERE payment_method || ' ' = 'CARD ';",
     ["P07"], "Oracle || 연산자 + 공백 비교"),

    ("Q19", "CREATE INDEX idx_members_email_lower ON MEMBERS(LOWER(email));",
     ["P08"], "함수 기반 인덱스 생성"),

    ("Q20", "CREATE INDEX idx_prod_name_upper ON PRODUCTS(UPPER(product_name));",
     ["P08"], "함수 기반 인덱스 생성"),

    ("Q21", "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status;",
     ["P09"], "비인덱스 컬럼 JOIN"),

    ("Q22", "SELECT p.product_name, c.name FROM PRODUCTS p JOIN CATEGORIES c ON p.product_name LIKE CONCAT('%', c.name, '%');",
     ["P09"], "LIKE 조인 조건"),

    ("Q23", "SELECT o.id, p.id FROM ORDERS o JOIN PAYMENTS p ON DATE(o.created_at) = DATE(p.payment_date) AND o.id = p.order_id;",
     ["P09", "P05"], "DATE() 함수 JOIN (P05+P09 복합)"),

    ("Q24", """SELECT * FROM PRODUCTS WHERE id IN (
  SELECT product_id FROM ORDER_ITEMS WHERE order_id IN (
    SELECT id FROM ORDERS WHERE member_id IN (
      SELECT id FROM MEMBERS WHERE status = 'INACTIVE'
    )
  )
);""",
     ["P10"], "3중 중첩 IN"),

    ("Q25", """SELECT m.name, (
  SELECT MAX(total_amount) FROM ORDERS o WHERE o.member_id = m.id AND ROWNUM = 1
) FROM MEMBERS m;""",
     ["P10", "P03"], "상관 서브쿼리 + ROWNUM (P03+P10 복합)"),

    ("Q26", """SELECT id FROM ORDERS o WHERE EXISTS (
  SELECT 1 FROM PAYMENTS p WHERE p.order_id = o.id AND EXISTS (
    SELECT 1 FROM COUPONS c WHERE c.member_id = o.member_id
  )
);""",
     ["P10"], "중첩 EXISTS"),

    ("Q27", "SELECT DECODE(status, 'COMPLETE', 1, 0) AS is_done, COUNT(*) FROM ORDERS GROUP BY DECODE(status, 'COMPLETE', 1, 0);",
     ["P11"], "DECODE + GROUP BY"),

    ("Q28", "SELECT * FROM PAYMENTS WHERE DECODE(payment_method, 'CARD', 1, 0) = 1;",
     ["P11"], "WHERE절 DECODE"),

    ("Q29", "SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id;",
     ["P12"], "CONNECT BY 계층 조회"),

    ("Q30", "SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id AND LEVEL <= 3;",
     ["P12"], "CONNECT BY + LEVEL 제한"),

    ("Q31", "SELECT * FROM CATEGORIES START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id;",
     ["P13", "P12"], "START WITH + CONNECT BY (P12+P13 복합)"),

    ("Q32", "SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+);",
     ["P14"], "Oracle (+) 아우터 조인"),

    ("Q33", "SELECT o.id, p.id FROM ORDERS o, PAYMENTS p WHERE o.id = p.order_id (+) AND p.payment_method (+) = 'CARD';",
     ["P14"], "(+) 다중 조건"),

    ("Q34", "SELECT c.name, p.product_name FROM CATEGORIES c, PRODUCTS p WHERE c.id (+) = p.category_id AND p.price > 10000;",
     ["P14"], "(+) 조인 + 가격 조건"),

    ("Q35", "SELECT * FROM COUPONS WHERE valid_until >= SYSDATE - 7;",
     ["P15"], "SYSDATE 날짜 연산"),

    ("Q36", "SELECT * FROM ORDERS WHERE TO_CHAR(SYSDATE, 'YYYYMMDD') = TO_CHAR(created_at, 'YYYYMMDD');",
     ["P15", "P20"], "SYSDATE + TO_CHAR (P15+P20 복합)"),

    ("Q37", "UPDATE PAYMENTS SET payment_date = SYSTIMESTAMP WHERE payment_method = 'CARD';",
     ["P16"], "SYSTIMESTAMP UPDATE"),

    ("Q38", "SELECT * FROM ORDERS WHERE created_at > SYSTIMESTAMP - INTERVAL '1' DAY;",
     ["P16"], "SYSTIMESTAMP + INTERVAL"),

    ("Q39", """MERGE INTO PRODUCTS p
USING (SELECT 50 AS id, 10 AS qty FROM DUAL) d
ON (p.id = d.id)
WHEN MATCHED THEN UPDATE SET p.stock_quantity = p.stock_quantity - d.qty;""",
     ["P17", "P19"], "MERGE INTO + DUAL (P17+P19 복합)"),

    ("Q40", """MERGE INTO MEMBERS m
USING (SELECT 'USR10050' AS id, 'ACTIVE' AS status FROM DUAL) d
ON (m.id = d.id)
WHEN NOT MATCHED THEN INSERT (id, name, email, status)
VALUES (d.id, 'Unknown', 'unknown@test.com', d.status);""",
     ["P17", "P19"], "MERGE INTO NOT MATCHED + DUAL (P17+P19 복합)"),

    ("Q41", "SELECT id FROM MEMBERS MINUS SELECT member_id FROM ORDERS WHERE created_at > '2024-01-01';",
     ["P18"], "MINUS 차집합"),

    ("Q42", "SELECT id FROM PRODUCTS MINUS SELECT product_id FROM ORDER_ITEMS;",
     ["P18"], "MINUS 차집합"),

    ("Q43", "SELECT member_seq.NEXTVAL FROM DUAL;",
     ["P19"], "NEXTVAL FROM DUAL"),

    ("Q44", """SELECT TO_CHAR(created_at, 'YYYYMMDD'), SUM(total_amount)
FROM ORDERS
WHERE TO_CHAR(created_at, 'YYYYMMDD') LIKE '202505%'
GROUP BY TO_CHAR(created_at, 'YYYYMMDD');""",
     ["P20"], "TO_CHAR 조건절 + GROUP BY"),

    ("Q45", "SELECT * FROM PAYMENTS ORDER BY TO_CHAR(payment_date, 'YYYY-MM-DD HH24:MI:SS') DESC;",
     ["P20"], "TO_CHAR ORDER BY"),

    ("Q46", "SELECT * FROM PRODUCTS WHERE TO_CHAR(price, '999,999') = '10,000';",
     ["P20"], "TO_CHAR 숫자 포맷"),

    ("Q47", "SELECT * FROM PAYMENTS WHERE payment_date >= TO_DATE('2025-05-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS');",
     ["P21"], "TO_DATE 시간 포맷"),

    ("Q48", "SELECT * FROM ORDERS WHERE created_at BETWEEN TO_DATE('20250101', 'YYYYMMDD') AND TO_DATE('20251231', 'YYYYMMDD');",
     ["P21"], "BETWEEN TO_DATE ... TO_DATE"),

    ("Q49", "SELECT TRUNC(created_at, 'MM'), COUNT(*) FROM ORDERS GROUP BY TRUNC(created_at, 'MM');",
     ["P22"], "TRUNC 월별 집계"),

    ("Q50", "SELECT * FROM PAYMENTS WHERE TRUNC(payment_date) = TRUNC(SYSDATE - 1);",
     ["P22", "P15"], "TRUNC + SYSDATE (P22+P15 복합)"),

    # ── P23~P30 신규 패턴 (type_tests 추가분) ─────────────────────
    ("Q51", "INSERT INTO t23 VALUES (my_seq.NEXTVAL, 'Alice');",
     ["P23"], "Oracle SEQUENCE.NEXTVAL 사용"),

    ("Q52", "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM t24;",
     ["P24"], "Oracle LISTAGG 집계 함수"),

    ("Q53", """CREATE TABLE t25 (
    price NUMBER(10,2),
    count NUMBER
);""",
     ["P25"], "Oracle NUMBER 타입 선언"),

    ("Q54", """SELECT id, parent_id
FROM tree
CONNECT BY NOCYCLE PRIOR id = parent_id;""",
     ["P26", "P12"], "CONNECT BY NOCYCLE (P12+P26 복합)"),

    ("Q55", "SELECT * FROM t27 WHERE REGEXP_LIKE(name, '^a', 'i');",
     ["P27"], "Oracle REGEXP_LIKE 함수"),

    ("Q56", """SELECT * FROM sales
PIVOT (
    SUM(amount)
    FOR year IN (2023, 2024)
);""",
     ["P28"], "Oracle PIVOT 연산자"),

    ("Q57", "SELECT WM_CONCAT(name) FROM t29;",
     ["P29"], "Oracle WM_CONCAT (deprecated)"),

    ("Q58", """CREATE TABLE t30 (
    name NVARCHAR2(50),
    code NCHAR(10)
);""",
     ["P30"], "Oracle NVARCHAR2/NCHAR 타입"),
]


def run_check(out_path=None):
    print(f"\n{'='*65}")
    print(f"  시뮬레이터 탐지 검증 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  대상 API : {API_URL}")
    print(f"{'='*65}\n")

    results = []
    ok_count = 0
    fail_count = 0
    error_count = 0

    header = f"{'쿼리':<5}  {'예상 패턴':<18}  {'실제 탐지':<25}  {'결과'}"
    print(header)
    print("-" * 70)

    for qid, sql, expected, note in QUERIES:
        try:
            resp = requests.post(API_URL, json={"sql": sql}, timeout=30)
            data = resp.json()

            if "error" in data:
                status = "⚠ API 오류"
                actual = []
                error_count += 1
            else:
                actual = data.get("matched_pattern_ids", [])
                missed = [p for p in expected if p not in actual]
                if not missed:
                    status = "✅ 정상"
                    ok_count += 1
                else:
                    status = f"❌ 미탐지: {missed}"
                    fail_count += 1

        except requests.exceptions.ConnectionError:
            status = "🔴 서버 연결 실패"
            actual = []
            error_count += 1
        except Exception as e:
            status = f"⚠ 예외: {e}"
            actual = []
            error_count += 1

        exp_str = str(expected)
        act_str = str(actual) if actual else "[]"
        print(f"{qid:<5}  {exp_str:<18}  {act_str:<25}  {status}")

        results.append({
            "id": qid,
            "sql": sql,
            "expected": expected,
            "actual": actual,
            "note": note,
            "status": status,
        })

    # ── 요약 ────────────────────────────────────────────────────
    total = len(QUERIES)
    print(f"\n{'='*65}")
    print(f"  검증 결과 요약")
    print(f"  전체: {total}건  |  정상: {ok_count}건  |  미탐지: {fail_count}건  |  오류: {error_count}건")
    print(f"  탐지율: {ok_count/total*100:.1f}%")
    print(f"{'='*65}")

    # ── 미탐지 목록 상세 출력 ────────────────────────────────────
    missed_list = [r for r in results if "미탐지" in r["status"]]
    if missed_list:
        print(f"\n📋 미탐지 패턴 상세 ({len(missed_list)}건) — 시뮬레이터 담당자 보고용\n")
        for r in missed_list:
            missed_patterns = [p for p in r["expected"] if p not in r["actual"]]
            print(f"  {r['id']} | 미탐지 패턴: {missed_patterns} | {r['note']}")
            print(f"       SQL: {r['sql'][:80].strip()}{'...' if len(r['sql']) > 80 else ''}\n")
    else:
        print("\n✅ 미탐지 패턴 없음 — 모든 쿼리 정상 탐지")

    # ── 파일 저장 ────────────────────────────────────────────────
    if out_path:
        _save_report(results, ok_count, fail_count, error_count, out_path)
        print(f"\n💾 리포트 저장 완료: {out_path}")

    return results


def _save_report(results, ok_count, fail_count, error_count, path):
    total = len(results)
    lines = [
        "# 시뮬레이터 탐지 검증 리포트",
        f"> 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 요약",
        f"- 전체: {total}건",
        f"- 정상 탐지: {ok_count}건",
        f"- 미탐지: {fail_count}건",
        f"- API 오류: {error_count}건",
        f"- **탐지율: {ok_count/total*100:.1f}%**",
        "",
        "## 전체 결과",
        "",
        "| 쿼리 | 예상 패턴 | 실제 탐지 | 결과 | 비고 |",
        "|------|-----------|-----------|------|------|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['expected']} | {r['actual']} | {r['status']} | {r['note']} |"
        )

    missed_list = [r for r in results if "미탐지" in r["status"]]
    if missed_list:
        lines += [
            "",
            "## 미탐지 패턴 상세 — 시뮬레이터 담당자 전달용",
            "",
        ]
        for r in missed_list:
            missed_patterns = [p for p in r["expected"] if p not in r["actual"]]
            lines += [
                f"### {r['id']} — 미탐지: {missed_patterns}",
                f"- 비고: {r['note']}",
                f"- SQL:",
                f"```sql",
                r["sql"].strip(),
                f"```",
                "",
            ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시뮬레이터 탐지 검증")
    parser.add_argument("--out", help="결과를 저장할 마크다운 파일 경로 (선택)")
    args = parser.parse_args()
    run_check(out_path=args.out)
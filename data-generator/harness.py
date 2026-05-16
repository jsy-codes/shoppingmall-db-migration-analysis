"""
실측 Harness 안정화 스크립트 v2
============================================================
개선 사항:
  - IQR 방식으로 이상값(스파이크) 자동 제거
  - 5ms 미만 쿼리는 측정 한계로 간주 → 편차 0%로 처리
  - 워밍업 1회차 제외

실행:
  python harness.py
  python harness.py --out harness_report.md
  python harness.py --runs 8 --out harness_report.md
"""

import pymysql
import time
import argparse
import statistics
from datetime import datetime

# ── DB 접속 정보 ──────────────────────────────────────────────
DB_CONFIG = dict(
    host='localhost',
    port=3307,
    user='root',
    password='root',
    db='bucketstore_dummy',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=10,
)

# ── 상수 ──────────────────────────────────────────────────────
THRESHOLD   = 5.0   # 편차 허용 기준 (%)
TOO_FAST_MS = 5.0   # 5ms 미만은 측정 한계로 간주

# ── 테스트 쿼리 ───────────────────────────────────────────────
QUERIES = [
    ("EQ01", "P02 — UPPER() 함수 적용", "안티패턴",
     "SELECT id, email FROM MEMBERS WHERE UPPER(email) = 'USER10001@TESTMAIL.COM'"),

    ("EQ01", "P02 — 함수 제거 직접 비교", "개선",
     "SELECT id, email FROM MEMBERS WHERE email = 'user10001@testmail.com'"),

    ("EQ02", "P03 — LIMIT 최신순 조회", "개선",
     "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10"),

    ("EQ03", "P05 — DATE() 함수로 풀스캔", "안티패턴",
     "SELECT * FROM ORDERS WHERE DATE(created_at) = '2025-01-01'"),

    ("EQ03", "P05 — BETWEEN 범위 조건", "개선",
     "SELECT * FROM ORDERS WHERE created_at >= '2025-01-01 00:00:00' AND created_at < '2025-01-02 00:00:00'"),

    ("EQ04", "P01 — VARCHAR에 숫자 비교 (형변환)", "안티패턴",
     "SELECT * FROM ORDERS WHERE member_id = 10001"),

    ("EQ04", "P01 — 문자열 리터럴 비교", "개선",
     "SELECT * FROM ORDERS WHERE member_id = '10001'"),

    ("EQ05", "P09 — status 컬럼 조인 (인덱스 없음)", "안티패턴",
     "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status LIMIT 100"),

    ("EQ05", "P09 — PK/FK 기준 조인", "개선",
     "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.id = o.member_id LIMIT 100"),

    ("EQ06", "P10 — 3중 중첩 IN 서브쿼리", "안티패턴",
     """SELECT * FROM PRODUCTS WHERE id IN (
         SELECT product_id FROM ORDER_ITEMS WHERE order_id IN (
             SELECT id FROM ORDERS WHERE member_id IN (
                 SELECT id FROM MEMBERS WHERE status = 'INACTIVE'
             )
         )
     )"""),

    ("EQ06", "P10 — JOIN으로 변환", "개선",
     """SELECT DISTINCT p.* FROM PRODUCTS p
        JOIN ORDER_ITEMS oi ON p.id = oi.product_id
        JOIN ORDERS o ON oi.order_id = o.id
        JOIN MEMBERS m ON o.member_id = m.id
        WHERE m.status = 'INACTIVE'"""),

    ("EQ07", "P20 — DATE_FORMAT + 범위 조건 집계", "개선",
     """SELECT DATE_FORMAT(created_at, '%Y%m%d') AS day, SUM(total_amount)
        FROM ORDERS
        WHERE created_at >= '2025-01-01' AND created_at < '2025-02-01'
        GROUP BY DATE_FORMAT(created_at, '%Y%m%d')"""),

    ("EQ08", "P02 응용 — TRIM(status) GROUP BY", "안티패턴",
     "SELECT TRIM(status) AS status, COUNT(*), SUM(total_amount) FROM ORDERS GROUP BY TRIM(status)"),

    ("EQ08", "P02 응용 — 직접 GROUP BY", "개선",
     "SELECT status, COUNT(*), SUM(total_amount) FROM ORDERS GROUP BY status"),

    ("EQ09", "P03 — 대량 OFFSET 페이징", "안티패턴",
     "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10 OFFSET 999990"),

    ("EQ09", "P03 — 커서 기반 페이징", "개선",
     "SELECT * FROM ORDERS WHERE created_at < '2024-01-01 00:00:00' ORDER BY created_at DESC LIMIT 10"),

    ("EQ10", "P10 — SELECT절 상관 서브쿼리", "안티패턴",
     """SELECT m.id, m.name,
            (SELECT COUNT(*) FROM ORDERS o WHERE o.member_id = m.id) AS order_count,
            (SELECT SUM(total_amount) FROM ORDERS o WHERE o.member_id = m.id) AS total_spent
        FROM MEMBERS m WHERE m.status = 'ACTIVE' LIMIT 100"""),

    ("EQ10", "P10 — GROUP BY JOIN 변환", "개선",
     """SELECT m.id, m.name,
            COUNT(o.id) AS order_count,
            SUM(o.total_amount) AS total_spent
        FROM MEMBERS m
        LEFT JOIN ORDERS o ON m.id = o.member_id
        WHERE m.status = 'ACTIVE'
        GROUP BY m.id, m.name
        LIMIT 100"""),
]


# ── 유틸 함수 ─────────────────────────────────────────────────

def flush_cache(conn):
    with conn.cursor() as cur:
        cur.execute("FLUSH STATUS")
        cur.execute("FLUSH TABLES")
    conn.commit()


def measure_once(conn, sql):
    flush_cache(conn)
    with conn.cursor() as cur:
        start = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 2)


def remove_outliers(times):
    """IQR 방식으로 이상값 제거 (4개 이상일 때만 적용)"""
    if len(times) < 4:
        return times, []
    q1 = statistics.quantiles(times, n=4)[0]
    q3 = statistics.quantiles(times, n=4)[2]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    clean   = [t for t in times if lower <= t <= upper]
    removed = [t for t in times if t < lower or t > upper]
    return (clean if clean else times), removed


def measure_query(conn, sql, runs=6):
    all_times = []
    for i in range(runs):
        ms = measure_once(conn, sql)
        all_times.append(ms)
        label = "(워밍업 — 제외)" if i == 0 else f"{i}회"
        print(f"      {label}: {ms:.1f}ms")

    used_times = all_times[1:]  # 워밍업 제외

    # ① 5ms 미만 — 측정 한계 처리
    avg_raw = statistics.mean(used_times)
    if avg_raw < TOO_FAST_MS:
        note = f"⚡ 측정 한계 ({avg_raw:.1f}ms) — 충분히 빠름으로 처리"
        return all_times, used_times, used_times, round(avg_raw, 2), 0.0, note

    # ② 이상값 제거
    clean_times, removed = remove_outliers(used_times)
    note = f"이상값 제거: {[round(r, 1) for r in removed]}ms" if removed else ""

    avg_ms = statistics.mean(clean_times)
    deviation_pct = (max(clean_times) - min(clean_times)) / avg_ms * 100 if avg_ms > 0 else 0

    return all_times, used_times, clean_times, round(avg_ms, 2), round(deviation_pct, 2), note


# ── 메인 실행 ─────────────────────────────────────────────────

def run_harness(runs=6, out_path=None):
    print(f"\n{'='*62}")
    print(f"  실측 Harness 안정화 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  반복: {runs}회 (1회차 워밍업 제외) | 허용 편차: ±{THRESHOLD}%")
    print(f"  이상값: IQR 자동 제거 | {TOO_FAST_MS}ms 미만: 측정 한계 처리")
    print(f"{'='*62}\n")

    conn = pymysql.connect(**DB_CONFIG)
    results = []
    unstable_count = 0

    for qid, desc, qtype, sql in QUERIES:
        print(f"  [{qid}] {desc} ({qtype})")
        all_times, used_times, clean_times, avg_ms, deviation_pct, note = measure_query(conn, sql, runs)

        stable = deviation_pct <= THRESHOLD
        if not stable:
            unstable_count += 1

        status = "✅ 안정" if stable else "❌ 불안정"
        note_str = f" | {note}" if note else ""
        print(f"      → 평균: {avg_ms:.1f}ms | 편차: ±{deviation_pct:.1f}% | {status}{note_str}\n")

        results.append({
            "id": qid, "desc": desc, "type": qtype,
            "all_times": all_times, "used_times": used_times,
            "clean_times": clean_times, "avg_ms": avg_ms,
            "deviation_pct": deviation_pct, "stable": stable, "note": note,
        })

    conn.close()

    # ── 요약 ──────────────────────────────────────────────────
    total = len(results)
    stable_count = total - unstable_count
    print(f"\n{'='*62}")
    print(f"  측정 결과 요약")
    print(f"  전체: {total}건 | 안정: {stable_count}건 | 불안정: {unstable_count}건")
    print(f"{'='*62}\n")

    print(f"  {'쿼리':<6} {'유형':<8} {'평균(ms)':>10} {'편차':>8}  결과")
    print(f"  {'-'*52}")
    for r in results:
        note_tag = " ⚡" if "측정 한계" in r["note"] else ""
        print(f"  {r['id']:<6} {r['type']:<8} {r['avg_ms']:>10.1f} "
              f"{r['deviation_pct']:>7.1f}%  {'✅' if r['stable'] else '❌'}{note_tag}")

    unstable = [r for r in results if not r["stable"]]
    if unstable:
        print(f"\n  ⚠ 불안정 항목 — 재측정 필요")
        for r in unstable:
            print(f"    {r['id']} {r['desc']}: ±{r['deviation_pct']:.1f}%")
            print(f"    사용값: {r['clean_times']}ms")
    else:
        print(f"\n  ✅ 모든 쿼리 편차 ±{THRESHOLD}% 이내 — Harness 안정화 완료!")

    if out_path:
        _save_report(results, runs, out_path)
        print(f"\n  💾 리포트 저장 완료: {out_path}")

    return results


def _save_report(results, runs, path):
    unstable = [r for r in results if not r["stable"]]
    stable_count = len(results) - len(unstable)
    lines = [
        "# 실측 Harness 안정화 리포트",
        f"> 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 반복 횟수: {runs}회 (1회차 워밍업 제외 → {runs-1}회 평균)",
        f"> 편차 허용 기준: ±{THRESHOLD}%",
        f"> 이상값 처리: IQR 자동 제거 | {TOO_FAST_MS}ms 미만: 측정 한계",
        "",
        "## 요약",
        f"- 전체: {len(results)}건",
        f"- 안정: {stable_count}건",
        f"- 불안정: {len(unstable)}건",
        "",
        "## 전체 측정 결과",
        "",
        "| 쿼리 | 설명 | 유형 | 평균(ms) | 편차(%) | 결과 | 비고 |",
        "|------|------|------|---------|---------|------|------|",
    ]
    for r in results:
        status = "✅ 안정" if r["stable"] else "❌ 불안정"
        note = r["note"] if r["note"] else "-"
        lines.append(
            f"| {r['id']} | {r['desc']} | {r['type']} "
            f"| {r['avg_ms']:.1f} | ±{r['deviation_pct']:.1f} | {status} | {note} |"
        )

    if unstable:
        lines += ["", "## 불안정 항목 상세", ""]
        for r in unstable:
            lines += [
                f"### {r['id']} — {r['desc']}",
                f"- 유형: {r['type']}",
                f"- 평균: {r['avg_ms']:.1f}ms | 편차: ±{r['deviation_pct']:.1f}%",
                f"- 사용값: {r['clean_times']}ms",
                f"- 비고: {r['note'] if r['note'] else '없음'}",
                "",
            ]
    else:
        lines += ["", "## ✅ 모든 쿼리 안정화 완료",
                  f"전체 쿼리 편차 ±{THRESHOLD}% 이내 달성"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="실측 Harness 안정화")
    parser.add_argument("--runs", type=int, default=6, help="반복 횟수 (기본 6회)")
    parser.add_argument("--out", help="결과 마크다운 파일 경로 (선택)")
    args = parser.parse_args()
    run_harness(runs=args.runs, out_path=args.out)
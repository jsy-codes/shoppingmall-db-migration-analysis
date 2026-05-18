"""
<<<<<<< HEAD
실측 Harness 안정화 스크립트 v3
============================================================
변경 사항 (v3):
  - pattern_rules.json을 직접 로드하여 패턴 메타데이터 사용
    (id, name, risk, failure_type, description, fix 자동 반영)
  - 테스트 쿼리(SQL)만 QUERY_MAP에 패턴 ID별로 정의
  - JSON에 패턴이 추가되면 QUERY_MAP에 쿼리만 추가하면 됨
  - IQR 이상값 자동 제거
=======
실측 Harness 안정화 스크립트 v2
============================================================
개선 사항:
  - IQR 방식으로 이상값(스파이크) 자동 제거
>>>>>>> origin/dev
  - 5ms 미만 쿼리는 측정 한계로 간주 → 편차 0%로 처리
  - 워밍업 1회차 제외

실행:
  python harness.py
  python harness.py --out harness_report.md
  python harness.py --runs 8 --out harness_report.md
<<<<<<< HEAD
  python harness.py --rules ../../backend/validation/pattern_rules.json
=======
>>>>>>> origin/dev
"""

import pymysql
import time
<<<<<<< HEAD
import json
import argparse
import statistics
from pathlib import Path
=======
import argparse
import statistics
>>>>>>> origin/dev
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

<<<<<<< HEAD
# ── 기본 pattern_rules.json 경로 ──────────────────────────────
DEFAULT_RULES_PATH = Path(__file__).parent.parent / "backend" / "validation" / "pattern_rules.json"


# ══════════════════════════════════════════════════════════════
# 패턴 ID별 테스트 쿼리 정의
# SQL만 여기에 정의 — 메타데이터(이름, 위험도 등)는 JSON에서 로드
#
# 구조:
#   "패턴ID": {
#       "anti": "안티패턴 SQL (Oracle 방식)",
#       "fix":  "개선 SQL (MySQL 방식)",
#   }
#
# anti/fix 중 하나만 있어도 됨 (단방향 측정)
# ══════════════════════════════════════════════════════════════
QUERY_MAP: dict[str, dict] = {
    "P01": {
        "anti": "SELECT * FROM ORDERS WHERE member_id = 10001",
        "fix":  "SELECT * FROM ORDERS WHERE member_id = '10001'",
    },
    "P02": {
        "anti": "SELECT id, email FROM MEMBERS WHERE UPPER(email) = 'USER10001@TESTMAIL.COM'",
        "fix":  "SELECT id, email FROM MEMBERS WHERE email = 'user10001@testmail.com'",
    },
    "P03": {
        # ROWNUM은 MySQL에서 실행 불가 → fix만 측정
        "fix":  "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10",
    },
    "P05": {
        "anti": "SELECT * FROM ORDERS WHERE DATE(created_at) = '2025-01-01'",
        "fix":  "SELECT * FROM ORDERS WHERE created_at >= '2025-01-01 00:00:00' AND created_at < '2025-01-02 00:00:00'",
    },
    "P09": {
        "anti": "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.status = o.status LIMIT 100",
        "fix":  "SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.id = o.member_id LIMIT 100",
    },
    "P10": {
        "anti": """SELECT * FROM PRODUCTS WHERE id IN (
            SELECT product_id FROM ORDER_ITEMS WHERE order_id IN (
                SELECT id FROM ORDERS WHERE member_id IN (
                    SELECT id FROM MEMBERS WHERE status = 'INACTIVE'
                )
            )
        )""",
        "fix": """SELECT DISTINCT p.* FROM PRODUCTS p
            JOIN ORDER_ITEMS oi ON p.id = oi.product_id
            JOIN ORDERS o ON oi.order_id = o.id
            JOIN MEMBERS m ON o.member_id = m.id
            WHERE m.status = 'INACTIVE'""",
    },
    "P20": {
        # TO_CHAR는 MySQL 미지원 → fix만 측정
        "fix": """SELECT DATE_FORMAT(created_at, '%Y%m%d') AS day, SUM(total_amount)
            FROM ORDERS
            WHERE created_at >= '2025-01-01' AND created_at < '2025-02-01'
            GROUP BY DATE_FORMAT(created_at, '%Y%m%d')""",
    },
    "P02_GROUP": {   # P02 응용 — GROUP BY
        "anti": "SELECT TRIM(status) AS status, COUNT(*), SUM(total_amount) FROM ORDERS GROUP BY TRIM(status)",
        "fix":  "SELECT status, COUNT(*), SUM(total_amount) FROM ORDERS GROUP BY status",
        "_pattern_id": "P02",  # JSON 메타데이터는 P02 사용
        "_label": "P02 응용 — GROUP BY 집계",
    },
    "P03_OFFSET": {  # P03 응용 — 대량 OFFSET
        "anti": "SELECT * FROM ORDERS ORDER BY created_at DESC LIMIT 10 OFFSET 999990",
        "fix":  "SELECT * FROM ORDERS WHERE created_at < '2024-01-01 00:00:00' ORDER BY created_at DESC LIMIT 10",
        "_pattern_id": "P03",
        "_label": "P03 응용 — 대량 OFFSET 페이징",
    },
    "P10_CORR": {    # P10 응용 — 상관 서브쿼리
        "anti": """SELECT m.id, m.name,
            (SELECT COUNT(*) FROM ORDERS o WHERE o.member_id = m.id) AS order_count,
            (SELECT SUM(total_amount) FROM ORDERS o WHERE o.member_id = m.id) AS total_spent
            FROM MEMBERS m WHERE m.status = 'ACTIVE' LIMIT 100""",
        "fix": """SELECT m.id, m.name,
            COUNT(o.id) AS order_count,
            SUM(o.total_amount) AS total_spent
            FROM MEMBERS m
            LEFT JOIN ORDERS o ON m.id = o.member_id
            WHERE m.status = 'ACTIVE'
            GROUP BY m.id, m.name
            LIMIT 100""",
        "_pattern_id": "P10",
        "_label": "P10 응용 — SELECT절 상관 서브쿼리",
    },
}


# ── 패턴 메타데이터 로드 ──────────────────────────────────────

def load_rules(rules_path: Path) -> dict[str, dict]:
    """
    pattern_rules.json을 로드하여 {패턴ID: 메타데이터} 딕셔너리로 반환.
    """
    try:
        with open(rules_path, encoding="utf-8") as f:
            rules = json.load(f)
        return {r["id"]: r for r in rules}
    except FileNotFoundError:
        print(f"  ⚠ pattern_rules.json을 찾을 수 없습니다: {rules_path}")
        print(f"  --rules 옵션으로 경로를 직접 지정하세요.")
        return {}
    except Exception as e:
        print(f"  ⚠ pattern_rules.json 로드 실패: {e}")
        return {}


def get_pattern_meta(key: str, rules: dict[str, dict]) -> dict:
    """
    QUERY_MAP 키에 대응하는 pattern_rules.json 메타데이터 반환.
    _pattern_id가 있으면 그걸 사용, 없으면 key 자체를 패턴 ID로 사용.
    """
    entry    = QUERY_MAP[key]
    pid      = entry.get("_pattern_id", key)   # 응용 케이스는 _pattern_id 참조
    label    = entry.get("_label", None)
    meta     = rules.get(pid, {})
    return {
        "pattern_id":   pid,
        "label":        label or f"{pid} — {meta.get('name', pid)}",
        "risk":         meta.get("risk", "UNKNOWN"),
        "failure_type": meta.get("failure_type", "-"),
        "description":  meta.get("description", "-"),
        "fix":          meta.get("fix", "-"),
        "quant_signal": meta.get("quant_signal", "-"),
    }


# ── 측정 유틸 ─────────────────────────────────────────────────
=======
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
>>>>>>> origin/dev

def flush_cache(conn):
    with conn.cursor() as cur:
        cur.execute("FLUSH STATUS")
        cur.execute("FLUSH TABLES")
    conn.commit()


<<<<<<< HEAD
def measure_once(conn, sql: str) -> float:
=======
def measure_once(conn, sql):
>>>>>>> origin/dev
    flush_cache(conn)
    with conn.cursor() as cur:
        start = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 2)


<<<<<<< HEAD
def remove_outliers(times: list[float]) -> tuple[list[float], list[float]]:
=======
def remove_outliers(times):
>>>>>>> origin/dev
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


<<<<<<< HEAD
def measure_query(conn, sql: str, runs: int = 6) -> dict:
    """
    runs회 실행 후 1회차(워밍업) 제외 + 이상값 제거 후 평균/편차 반환.
    """
=======
def measure_query(conn, sql, runs=6):
>>>>>>> origin/dev
    all_times = []
    for i in range(runs):
        ms = measure_once(conn, sql)
        all_times.append(ms)
        label = "(워밍업 — 제외)" if i == 0 else f"{i}회"
        print(f"      {label}: {ms:.1f}ms")

<<<<<<< HEAD
    used_times = all_times[1:]
    avg_raw = statistics.mean(used_times)

    # 5ms 미만 — 측정 한계
    if avg_raw < TOO_FAST_MS:
        return {
            "all_times":   all_times,
            "used_times":  used_times,
            "clean_times": used_times,
            "avg_ms":      round(avg_raw, 2),
            "deviation":   0.0,
            "note":        f"⚡ 측정 한계 ({avg_raw:.1f}ms) — 충분히 빠름",
        }

    clean_times, removed = remove_outliers(used_times)
    avg_ms    = statistics.mean(clean_times)
    deviation = (max(clean_times) - min(clean_times)) / avg_ms * 100 if avg_ms > 0 else 0
    note      = f"이상값 제거: {[round(r, 1) for r in removed]}ms" if removed else ""

    return {
        "all_times":   all_times,
        "used_times":  used_times,
        "clean_times": clean_times,
        "avg_ms":      round(avg_ms, 2),
        "deviation":   round(deviation, 2),
        "note":        note,
    }
=======
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
>>>>>>> origin/dev


# ── 메인 실행 ─────────────────────────────────────────────────

<<<<<<< HEAD
def run_harness(runs: int = 6, out_path: str | None = None, rules_path: Path = DEFAULT_RULES_PATH):
    print(f"\n{'='*65}")
    print(f"  실측 Harness 안정화 v3 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  반복: {runs}회 (1회차 워밍업 제외) | 허용 편차: ±{THRESHOLD}%")
    print(f"  이상값: IQR 자동 제거 | {TOO_FAST_MS}ms 미만: 측정 한계 처리")
    print(f"  패턴 메타데이터: {rules_path}")
    print(f"{'='*65}\n")

    # pattern_rules.json 로드
    rules = load_rules(rules_path)
    if rules:
        print(f"  ✅ pattern_rules.json 로드 완료 — {len(rules)}개 패턴\n")
    else:
        print(f"  ⚠ 패턴 메타데이터 없이 진행합니다.\n")

    conn    = pymysql.connect(**DB_CONFIG)
    results = []
    unstable_count = 0

    for key, entry in QUERY_MAP.items():
        meta = get_pattern_meta(key, rules)
        print(f"  [{meta['pattern_id']}] {meta['label']}")
        if rules:
            print(f"       위험도: {meta['risk']} | 실패유형: {meta['failure_type']}")

        # 안티패턴 측정
        anti_result = None
        if "anti" in entry:
            print(f"    ❌ 안티패턴:")
            anti_result = measure_query(conn, entry["anti"], runs)
            stable_anti = anti_result["deviation"] <= THRESHOLD
            print(f"       → 평균: {anti_result['avg_ms']:.1f}ms | "
                  f"편차: ±{anti_result['deviation']:.1f}% | "
                  f"{'✅ 안정' if stable_anti else '❌ 불안정'}"
                  f"{' | ' + anti_result['note'] if anti_result['note'] else ''}")
        else:
            print(f"    ❌ 안티패턴: MySQL 미지원으로 측정 생략")

        # 개선 쿼리 측정
        fix_result = None
        if "fix" in entry:
            print(f"    ✅ 개선:")
            fix_result = measure_query(conn, entry["fix"], runs)
            stable_fix = fix_result["deviation"] <= THRESHOLD
            print(f"       → 평균: {fix_result['avg_ms']:.1f}ms | "
                  f"편차: ±{fix_result['deviation']:.1f}% | "
                  f"{'✅ 안정' if stable_fix else '❌ 불안정'}"
                  f"{' | ' + fix_result['note'] if fix_result['note'] else ''}")

        # 개선 효과 출력
        if anti_result and fix_result:
            if anti_result["avg_ms"] > 0:
                improvement = (anti_result["avg_ms"] - fix_result["avg_ms"]) / anti_result["avg_ms"] * 100
                print(f"       → 성능 개선: {improvement:+.1f}%")

        # 안정 여부 판단
        anti_stable = anti_result["deviation"] <= THRESHOLD if anti_result else True
        fix_stable  = fix_result["deviation"] <= THRESHOLD if fix_result else True
        overall_stable = anti_stable and fix_stable
        if not overall_stable:
            unstable_count += 1

        results.append({
            "key":     key,
            "meta":    meta,
            "anti":    anti_result,
            "fix":     fix_result,
            "stable":  overall_stable,
        })
        print()
=======
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
>>>>>>> origin/dev

    conn.close()

    # ── 요약 ──────────────────────────────────────────────────
    total = len(results)
    stable_count = total - unstable_count
<<<<<<< HEAD
    print(f"\n{'='*65}")
    print(f"  측정 결과 요약")
    print(f"  전체: {total}건 | 안정: {stable_count}건 | 불안정: {unstable_count}건")
    print(f"{'='*65}\n")

    header = f"  {'패턴':<8} {'위험도':<8} {'안티패턴(ms)':>12} {'개선(ms)':>10} {'개선율':>8}  결과"
    print(header)
    print(f"  {'-'*60}")
    for r in results:
        pid   = r["meta"]["pattern_id"]
        risk  = r["meta"]["risk"]
        a_ms  = f"{r['anti']['avg_ms']:.1f}" if r["anti"] else "N/A"
        f_ms  = f"{r['fix']['avg_ms']:.1f}"  if r["fix"]  else "N/A"
        impr  = "-"
        if r["anti"] and r["fix"] and r["anti"]["avg_ms"] > 0:
            pct  = (r["anti"]["avg_ms"] - r["fix"]["avg_ms"]) / r["anti"]["avg_ms"] * 100
            impr = f"{pct:+.1f}%"
        tag   = "✅" if r["stable"] else "❌"
        print(f"  {pid:<8} {risk:<8} {a_ms:>12} {f_ms:>10} {impr:>8}  {tag}")

    # 불안정 항목
    unstable_list = [r for r in results if not r["stable"]]
    if unstable_list:
        print(f"\n  ⚠ 불안정 항목 ({len(unstable_list)}건)")
        for r in unstable_list:
            print(f"    [{r['meta']['pattern_id']}] {r['meta']['label']}")
            if r["anti"] and r["anti"]["deviation"] > THRESHOLD:
                print(f"       안티패턴: ±{r['anti']['deviation']:.1f}% — {r['anti']['clean_times']}ms")
            if r["fix"] and r["fix"]["deviation"] > THRESHOLD:
                print(f"       개선:     ±{r['fix']['deviation']:.1f}% — {r['fix']['clean_times']}ms")
=======
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
>>>>>>> origin/dev
    else:
        print(f"\n  ✅ 모든 쿼리 편차 ±{THRESHOLD}% 이내 — Harness 안정화 완료!")

    if out_path:
<<<<<<< HEAD
        _save_report(results, runs, rules, out_path)
=======
        _save_report(results, runs, out_path)
>>>>>>> origin/dev
        print(f"\n  💾 리포트 저장 완료: {out_path}")

    return results


<<<<<<< HEAD
def _save_report(results: list, runs: int, rules: dict, path: str):
    unstable  = [r for r in results if not r["stable"]]
=======
def _save_report(results, runs, path):
    unstable = [r for r in results if not r["stable"]]
    stable_count = len(results) - len(unstable)
>>>>>>> origin/dev
    lines = [
        "# 실측 Harness 안정화 리포트",
        f"> 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 반복 횟수: {runs}회 (1회차 워밍업 제외 → {runs-1}회 평균)",
        f"> 편차 허용 기준: ±{THRESHOLD}%",
        f"> 이상값 처리: IQR 자동 제거 | {TOO_FAST_MS}ms 미만: 측정 한계",
<<<<<<< HEAD
        f"> 패턴 메타데이터: pattern_rules.json ({len(rules)}개 패턴 로드)",
        "",
        "## 요약",
        f"- 전체: {len(results)}건",
        f"- 안정: {len(results) - len(unstable)}건",
=======
        "",
        "## 요약",
        f"- 전체: {len(results)}건",
        f"- 안정: {stable_count}건",
>>>>>>> origin/dev
        f"- 불안정: {len(unstable)}건",
        "",
        "## 전체 측정 결과",
        "",
<<<<<<< HEAD
        "| 패턴 | 패턴명 | 위험도 | 실패유형 | 안티패턴(ms) | 편차 | 개선(ms) | 편차 | 개선율 | 결과 |",
        "|------|--------|--------|----------|-------------|------|---------|------|--------|------|",
    ]

    for r in results:
        m      = r["meta"]
        a      = r["anti"]
        f      = r["fix"]
        a_ms   = f"{a['avg_ms']:.1f}" if a else "N/A"
        a_dev  = f"±{a['deviation']:.1f}%" if a else "-"
        f_ms   = f"{f['avg_ms']:.1f}" if f else "N/A"
        f_dev  = f"±{f['deviation']:.1f}%" if f else "-"
        impr   = "-"
        if a and f and a["avg_ms"] > 0:
            pct  = (a["avg_ms"] - f["avg_ms"]) / a["avg_ms"] * 100
            impr = f"{pct:+.1f}%"
        status = "✅ 안정" if r["stable"] else "❌ 불안정"
        lines.append(
            f"| {m['pattern_id']} | {m['label']} | {m['risk']} | {m['failure_type']} "
            f"| {a_ms} | {a_dev} | {f_ms} | {f_dev} | {impr} | {status} |"
        )

    # 패턴별 상세 (JSON 메타데이터 포함)
    lines += ["", "## 패턴별 상세 — pattern_rules.json 기반", ""]
    for r in results:
        m = r["meta"]
        lines += [
            f"### [{m['pattern_id']}] {m['label']}",
            f"- **위험도**: {m['risk']}",
            f"- **실패 유형**: {m['failure_type']}",
            f"- **설명**: {m['description']}",
            f"- **수정 방법**: {m['fix']}",
            f"- **quant_signal**: {m['quant_signal']}",
        ]
        if r["anti"]:
            a = r["anti"]
            lines.append(f"- **안티패턴 평균**: {a['avg_ms']:.1f}ms | 편차: ±{a['deviation']:.1f}% | {a['note'] or '없음'}")
        if r["fix"]:
            f_ = r["fix"]
            lines.append(f"- **개선 평균**: {f_['avg_ms']:.1f}ms | 편차: ±{f_['deviation']:.1f}% | {f_['note'] or '없음'}")
        lines.append("")

    if unstable:
        lines += ["## 불안정 항목 상세", ""]
        for r in unstable:
            m = r["meta"]
            lines += [f"### {m['pattern_id']} — {m['label']}"]
            if r["anti"] and r["anti"]["deviation"] > THRESHOLD:
                lines.append(f"- 안티패턴: ±{r['anti']['deviation']:.1f}% | {r['anti']['clean_times']}ms")
            if r["fix"] and r["fix"]["deviation"] > THRESHOLD:
                lines.append(f"- 개선: ±{r['fix']['deviation']:.1f}% | {r['fix']['clean_times']}ms")
            lines.append("")

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="실측 Harness 안정화 v3")
    parser.add_argument("--runs",  type=int, default=6,  help="반복 횟수 (기본 6회)")
    parser.add_argument("--out",   type=str, default=None, help="결과 마크다운 파일 경로")
    parser.add_argument("--rules", type=str, default=str(DEFAULT_RULES_PATH),
                        help=f"pattern_rules.json 경로 (기본: {DEFAULT_RULES_PATH})")
    args = parser.parse_args()
    run_harness(
        runs       = args.runs,
        out_path   = args.out,
        rules_path = Path(args.rules),
    )
=======
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
>>>>>>> origin/dev

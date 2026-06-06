"""
run_scenario_c.py — 시나리오 C: bad_queries.sql MySQL 실행 에러 검증
=========================================================================
목적: bad_queries.sql 50개 쿼리를 MySQL에 직접 실행하여
      실제 에러 발생 여부, 에러 코드, 에러 메시지를 기록하고
      결과를 C(이현종)에게 전달한다.

결과물:
  test-results/bad_queries_result.csv    → 전체 실행 결과
  test-results/bad_queries_report.md    → 요약 리포트

실행:
  python run_scenario_c.py
  python run_scenario_c.py --input data-generator/bad_queries.sql
"""

import sys
import re
import csv
import argparse
import pymysql
from pathlib import Path
from datetime import datetime

# ── 경로 설정 ──────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
OUT_DIR     = BASE_DIR / "test-results"
DEFAULT_SQL = BASE_DIR / "bad_queries_fixed.sql"

# ── MySQL 접속 (bucketstore_dummy) ─────────────────────────────
MYSQL_CONFIG = dict(
    host="localhost", port=3307,
    user="root", password="root",
    db="bucketstore_dummy",
    charset="utf8mb4", connect_timeout=10,
)

# ── 실패 유형 분류 기준 (에러 메시지 키워드 → failure_type) ─────
FAILURE_PATTERNS = [
    (r"ROWNUM",                     "SYNTAX_ERROR",       "ROWNUM은 MySQL 미지원 — LIMIT으로 변환 필요"),
    (r"CONNECT BY|START WITH",      "SYNTAX_ERROR",       "계층 쿼리 미지원 — WITH RECURSIVE로 변환 필요"),
    (r"MERGE INTO",                 "SYNTAX_ERROR",       "MERGE INTO 미지원 — INSERT ON DUPLICATE KEY UPDATE로 변환"),
    (r"MINUS",                      "SYNTAX_ERROR",       "MINUS 미지원 — NOT EXISTS 또는 LEFT JOIN 안티조인으로 변환"),
    (r"VARCHAR2",                   "SYNTAX_ERROR",       "VARCHAR2 타입 미지원 — VARCHAR으로 변환 필요"),
    (r"\(\+\)",                     "SYNTAX_ERROR",       "Oracle (+) 조인 문법 미지원 — LEFT/RIGHT JOIN으로 변환"),
    (r"NVL",                        "FUNCTION_NOT_FOUND", "NVL 함수 미지원 — IFNULL 또는 COALESCE로 변환"),
    (r"DECODE",                     "FUNCTION_NOT_FOUND", "DECODE 함수 미지원 — CASE WHEN으로 변환"),
    (r"TO_CHAR",                    "FUNCTION_NOT_FOUND", "TO_CHAR 함수 미지원 — DATE_FORMAT으로 변환"),
    (r"TO_DATE",                    "FUNCTION_NOT_FOUND", "TO_DATE 함수 미지원 — STR_TO_DATE로 변환"),
    (r"TRUNC",                      "FUNCTION_NOT_FOUND", "TRUNC 함수 미지원 — DATE() 또는 DATE_FORMAT으로 변환"),
    (r"SYSTIMESTAMP",               "FUNCTION_NOT_FOUND", "SYSTIMESTAMP 미지원 — NOW(6) 또는 CURRENT_TIMESTAMP(6)으로 변환"),
    (r"Unknown column",             "COLUMN_NOT_FOUND",   "존재하지 않는 컬럼 참조 — 스키마 불일치 수정 필요"),
    (r"Table .* doesn't exist",     "TABLE_NOT_FOUND",    "존재하지 않는 테이블 참조"),
    (r"Incorrect integer value",    "TYPE_MISMATCH",      "타입 불일치 — 암묵적 형변환 오류"),
    (r"LISTAGG|WM_CONCAT|PIVOT|REGEXP_LIKE",     "FUNCTION_NOT_FOUND", "Oracle 전용 함수/연산자 미지원 — MySQL 대체 함수로 변환 필요"),
    (r"NEXTVAL|CURRVAL",     "SYNTAX_ERROR", "Oracle SEQUENCE 문법 미지원 — AUTO_INCREMENT로 변환 필요"),
    (r"NUMBER\s*\(",  "SYNTAX_ERROR", "Oracle NUMBER 타입 미지원 — INT/DECIMAL로 변환 필요"),
    (r"NVARCHAR2|NCHAR",   "SYNTAX_ERROR", "Oracle 유니코드 타입 미지원 — VARCHAR + utf8mb4로 변환 필요"),
    (r"1305",   "FUNCTION_NOT_FOUND", "MySQL에 없는 함수 호출"),
]


def classify_failure(sql: str, error_msg: str) -> tuple[str, str]:
    """에러 메시지와 SQL로 failure_type과 수정 방법 분류"""
    sql_upper = sql.upper()
    err_upper = error_msg.upper()

    for pattern, ftype, fix in FAILURE_PATTERNS:
        if re.search(pattern, sql_upper) or re.search(pattern, err_upper):
            return ftype, fix

    return "UNKNOWN_ERROR", "에러 원인 수동 확인 필요"


def classify_ok(sql: str) -> tuple[str, str]:
    """실행 성공했지만 성능/정합성 이슈가 있는 경우 분류"""
    sql_upper = sql.upper()

    if re.search(r"\bUPPER\s*\(|\bLOWER\s*\(|\bSUBSTR\s*\(", sql_upper):
        return "OK_SLOW", "인덱스 컬럼에 함수 적용 — 성능 저하 (P02)"
    if re.search(r"\bSYSDATE\b", sql_upper):
        return "OK_WRONG", "SYSDATE 실행되나 의미가 다름 — NOW()로 변환 권장 (P15)"
    if re.search(r"\bFROM\s+DUAL\b", sql_upper):
        return "OK_COMPAT", "DUAL은 MySQL에서 실행 가능 (P19)"
    if re.search(r"\bCAST\s*\(.*AS\s+CHAR", sql_upper):
        return "OK_SLOW", "CAST 형변환 실행됨 — 인덱스 우회 가능 (P07)"
    if re.search(r"\bCAST\s*\(.*AS\s+DATE", sql_upper):
        return "OK_SLOW", "CAST AS DATE 실행됨 — 시간 정보 손실 가능 (P05)"
    if re.search(r"\bREGEXP_LIKE\s*\(", sql_upper):
        return "OK_WRONG", "REGEXP_LIKE 실행되나 플래그 동작이 Oracle과 다름 — REGEXP로 변환 권장 (P27)"

    return "OK", "정상 실행"


# ══════════════════════════════════════════════════════════════
# SQL 파일 파싱 — 쿼리 번호·패턴·SQL 추출
# ══════════════════════════════════════════════════════════════

def detect_pattern_from_sql(sql: str, current_pattern: str) -> str:
    sql_upper = sql.upper()
    if "LISTAGG" in sql_upper:
        return "P24"
    if "NOCYCLE" in sql_upper:
        return "P26"
    if "REGEXP_LIKE" in sql_upper:
        return "P27"
    if "PIVOT" in sql_upper:
        return "P28"
    if "WM_CONCAT" in sql_upper:
        return "P29"
    if "NVARCHAR2" in sql_upper or "NCHAR" in sql_upper:
        return "P30"
    return current_pattern

def parse_bad_queries(sql_path: Path) -> list[dict]:
    """
    bad_queries.sql에서 Q번호, 패턴, 설명, SQL을 파싱.
    """
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    queries = []
    current_qnum    = None
    current_pattern = None
    current_desc    = None
    current_sql     = []

    pattern_re = re.compile(r"--\s*\[(P\d+)\]")
    qnum_re    = re.compile(r"--\s*(Q\d+)[.\s]+(.+)")

    for line in lines:
        stripped = line.strip()

        # 패턴 ID 감지 ([P01] ...)
        m_p = pattern_re.search(stripped)
        if m_p and stripped.startswith("--"):
            current_pattern = m_p.group(1)
            continue

        # 쿼리 번호 감지 (-- Q01. ...)
        m_q = qnum_re.match(stripped)
        if m_q:
            # 이전 쿼리 저장
            if current_qnum and current_sql:
                sql_text = " ".join(current_sql).strip().rstrip(";")
                queries.append({
                    "qnum":    current_qnum,
                    "pattern": detect_pattern_from_sql(sql_text, current_pattern or "?"),
                    "desc":    current_desc or "",
                    "sql":     sql_text,
                })
                current_sql = []

            current_qnum = m_q.group(1)
            current_desc = m_q.group(2).strip()
            continue

        # SQL 라인 수집 (주석 제외)
        if not stripped.startswith("--") and stripped:
            current_sql.append(stripped)
    
    # 마지막 쿼리 저장
    if current_qnum and current_sql:
        sql_text = " ".join(current_sql).strip().rstrip(";")
        queries.append({
            "qnum":    current_qnum,
            "pattern": detect_pattern_from_sql(sql_text, current_pattern or "?"),
            "desc":    current_desc or "",
            "sql":     sql_text,
        })

    return queries


# ══════════════════════════════════════════════════════════════
# 쿼리 실행 및 결과 분류
# ══════════════════════════════════════════════════════════════

def run_query(conn, sql: str) -> tuple[bool, str, str]:
    """
    MySQL에 쿼리 실행 후 (성공여부, 에러코드, 에러메시지) 반환.
    DDL은 롤백 처리.
    """
    sql_upper = sql.strip().upper()
    is_ddl    = any(sql_upper.startswith(k) for k in
                    ["CREATE", "DROP", "ALTER", "MERGE", "TRUNCATE"])

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if not is_ddl:
                cur.fetchall()
            conn.commit()

            # DDL 성공 시 롤백 (인덱스/테이블 생성 원상복구)
            if is_ddl:
                try:
                    if "CREATE TEMPORARY TABLE" in sql_upper:
                        tbl = re.search(r"CREATE\s+TEMPORARY\s+TABLE\s+(\w+)", sql, re.I)
                        if tbl:
                            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS {tbl.group(1)}")
                    elif "CREATE INDEX" in sql_upper:
                        idx = re.search(r"CREATE\s+INDEX\s+(\w+)", sql, re.I)
                        tbl = re.search(r"\bON\s+(\w+)\s*\(", sql, re.I)
                        if idx and tbl:
                            cur.execute(f"DROP INDEX {idx.group(1)} ON {tbl.group(1)}")
                    conn.commit()
                except Exception:
                    conn.rollback()

        return True, "", ""

    except pymysql.err.ProgrammingError as e:
        conn.rollback()
        return False, f"ER_{e.args[0]}", str(e.args[1])
    except pymysql.err.OperationalError as e:
        conn.rollback()
        return False, f"ER_{e.args[0]}", str(e.args[1])
    except Exception as e:
        conn.rollback()
        return False, "UNKNOWN", str(e)


# ══════════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════════

def run_scenario_c(sql_path: Path):
    print(f"\n{'='*65}")
    print(f"  시나리오 C — bad_queries.sql MySQL 에러 검증")
    print(f"  입력: {sql_path.name}")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    # ── SQL 파일 파싱 ──────────────────────────────────────────
    if not sql_path.exists():
        print(f"  ❌ 파일 없음: {sql_path}")
        return

    queries = parse_bad_queries(sql_path)
    print(f"  ✅ {len(queries)}개 쿼리 파싱 완료\n")

    # ── MySQL 연결 ────────────────────────────────────────────
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        print(f"  ✅ MySQL 연결 성공 (bucketstore_dummy)\n")
    except Exception as e:
        print(f"  ❌ MySQL 연결 실패: {e}")
        return

    # ── 실행 및 결과 수집 ─────────────────────────────────────
    results = []
    ok_count  = 0
    err_count = 0

    print(f"  {'번호':<6} {'패턴':<6} {'결과':<8} {'실패 유형':<22} 설명")
    print(f"  {'-'*75}")

    for q in queries:
        success, err_code, err_msg = run_query(conn, q["sql"])

        if success:
            result_type, note = classify_ok(q["sql"])
            failure_type = "-"
            fix_hint     = note
            ok_count += 1
            icon = "✅"
        else:
            result_type  = "ERROR"
            failure_type, fix_hint = classify_failure(q["sql"], err_msg)
            err_count += 1
            icon = "❌"

        short_err = err_msg[:60] + "..." if len(err_msg) > 60 else err_msg
        print(f"  {q['qnum']:<6} {q['pattern']:<6} {icon} {result_type:<8} {failure_type:<22} {q['desc'][:30]}")

        results.append({
            "qnum":         q["qnum"],
            "pattern":      q["pattern"],
            "desc":         q["desc"],
            "result":       result_type,
            "failure_type": failure_type,
            "error_code":   err_code,
            "error_msg":    err_msg,
            "fix_hint":     fix_hint,
            "sql":          q["sql"][:200],
        })

    conn.close()

    # ── 결과 요약 ─────────────────────────────────────────────
    total = len(results)
    print(f"\n  {'='*55}")
    print(f"  실행 결과 요약")
    print(f"  전체: {total}건 | 성공(OK): {ok_count}건 | 에러(ERROR): {err_count}건")
    print(f"  에러율: {err_count/total*100:.1f}%")

    # 실패 유형별 집계
    from collections import Counter
    ft_counts = Counter(r["failure_type"] for r in results if r["result"] == "ERROR")
    print(f"\n  [실패 유형별 분류]")
    for ft, cnt in ft_counts.most_common():
        print(f"  {ft:<25}: {cnt}건")

    # ── CSV 저장 ──────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "bad_queries_result.csv"
    fields = [
        "qnum", "pattern", "desc", "result",
        "failure_type", "error_code", "error_msg", "fix_hint", "sql",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  💾 결과 CSV: {csv_path}")

    report_path = OUT_DIR / "bad_queries_report.md"
    _save_report(results, ok_count, err_count, ft_counts, report_path)
    print(f"  💾 전달 리포트: {report_path}")
    print(f"\n  ✅ 시나리오 C 완료\n")


def _save_report(results, ok_count, err_count, ft_counts, path: Path):
    total      = len(results)
    error_rows = [r for r in results if r["result"] == "ERROR"]

    lines = [
        "# 시나리오 C — bad_queries.sql MySQL 에러 검증 리포트",
        f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 대상: bucketstore_dummy (MySQL 8.0)",
        "",
        "## 요약",
        f"- 전체: {total}건",
        f"- 성공(OK/OK_SLOW/OK_WRONG): {ok_count}건",
        f"- 에러(ERROR): {err_count}건",
        f"- **에러율: {err_count/total*100:.1f}%**",
        "",
        "## 실패 유형별 분류",
        "",
        "| 실패 유형 | 건수 | 의미 |",
        "|-----------|------|------|",
    ]
    ft_desc = {
        "SYNTAX_ERROR":       "MySQL이 아예 인식 못 하는 Oracle 전용 문법",
        "FUNCTION_NOT_FOUND": "MySQL에 없는 Oracle 전용 함수",
        "COLUMN_NOT_FOUND":   "스키마에 없는 컬럼 참조",
        "TABLE_NOT_FOUND":    "스키마에 없는 테이블 참조",
        "TYPE_MISMATCH":      "타입 불일치로 인한 암묵적 변환 오류",
        "UNKNOWN_ERROR":      "분류되지 않은 기타 오류",
    }
    for ft, cnt in ft_counts.most_common():
        desc = ft_desc.get(ft, "-")
        lines.append(f"| {ft} | {cnt} | {desc} |")

    lines += [
        "",
        "## 전체 실행 결과",
        "",
        "| 번호 | 패턴 | 결과 | 실패 유형 | 수정 방향 | 설명 |",
        "|------|------|------|-----------|-----------|------|",
    ]
    for r in results:
        icon = "✅" if r["result"] != "ERROR" else "❌"
        lines.append(
            f"| {r['qnum']} | {r['pattern']} | {icon} {r['result']} "
            f"| {r['failure_type']} | {r['fix_hint'][:40]} | {r['desc'][:30]} |"
        )

    lines += [
        "",
        "## 에러 항목 상세 — C(이현종) Claude 프롬프트 반영용",
        "",
        "아래 항목들은 Claude API 프롬프트의 `[이관 규칙 가이드라인]`에",
        "실제 에러 메시지와 수정 방향을 보강해야 합니다.",
        "",
    ]
    for r in error_rows:
        lines += [
            f"### {r['qnum']} — {r['pattern']} ({r['failure_type']})",
            f"- **설명**: {r['desc']}",
            f"- **에러**: `{r['error_msg'][:100]}`",
            f"- **수정 방향**: {r['fix_hint']}",
            f"```sql",
            r["sql"][:200],
            "```",
            "",
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시나리오 C — bad_queries MySQL 에러 검증")
    parser.add_argument(
        "--input", default=str(DEFAULT_SQL),
        help="bad_queries.sql 경로 (기본: data-generator/bad_queries.sql)"
    )
    args = parser.parse_args()
    run_scenario_c(Path(args.input))

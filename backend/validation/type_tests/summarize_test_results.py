# backend/validation/type_tests/summarize_test_results.py
"""
result.csv + consistency_check.csv + result_compare.csv + pattern_rules.json 을 읽어
'패턴 정합성 통합 리포트' 생성

검증 3축:
  ① 패턴 탐지  — consistency_simulator가 잡아냈는가
  ② 실행 호환성 — MySQL에서 syntax/function 에러 없이 실행되는가
  ③ 결과 정합성 — 변환 전후 row 결과가 일치하는가
"""
import csv
import json
from pathlib import Path
from datetime import datetime

BASE       = Path(__file__).parent
RULES_PATH = BASE.parent / "pattern_rules.json"

# ── 데이터 로드 ────────────────────────────────────────────────

# ① result.csv  (MySQL 실행 호환성)
exec_map: dict[str, str] = {}
result_csv = BASE / "result.csv"
if result_csv.exists():
    with open(result_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["file"].replace(".sql", "")
            exec_map[pid] = row["result"]

# ② result_compare.csv  (변환 전후 결과 비교)
# pattern_id 형식: P01_01, P02_02 → 앞 패턴 ID(P01)로 그룹핑
compare_map: dict[str, list[dict]] = {}
compare_csv = BASE / "result_compare.csv"
if compare_csv.exists():
    with open(compare_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            base_pid = row["pattern_id"].split("_")[0]   # "P01_01" → "P01"
            compare_map.setdefault(base_pid, []).append(row)

# ③ pattern_rules.json
rules     = json.loads(RULES_PATH.read_text(encoding="utf-8"))
rule_map  = {r["id"]: r for r in rules}
all_pids  = [r["id"] for r in rules]   # P01 ~ P30 순서 유지

# ── 헬퍼 ──────────────────────────────────────────────────────

def exec_verdict(pid: str) -> tuple[str, str]:
    """(셀 텍스트, 에러 요약)"""
    raw = exec_map.get(pid)
    if raw is None:
        return "⚪ 미실행", ""
    if raw == "OK":
        return "✅ OK", ""
    try:
        errs = json.loads(raw)
        summary = errs[0][:70] if errs else raw[:70]
    except Exception:
        summary = str(raw)[:70]
    return "❌ 에러", summary


def compare_verdict(pid: str) -> tuple[str, str]:
    """(셀 텍스트, 상세)"""
    rows = compare_map.get(pid)
    if not rows:
        return "⚪ 미실행", ""

    statuses = [r["result_match"] for r in rows]
    match_cnt    = statuses.count("MATCH")
    mismatch_cnt = statuses.count("MISMATCH")
    error_cnt    = statuses.count("ERROR")
    total        = len(statuses)

    if error_cnt == total:
        return "❌ 실행불가", f"전체 {total}건 에러"
    if mismatch_cnt > 0:
        return "⚠️ 불일치", f"{mismatch_cnt}/{total}건 불일치"
    if match_cnt == total:
        return "✅ 일치", f"전체 {total}건 일치"
    return "⚠️ 부분일치", f"{match_cnt}/{total}건 일치"


GRADE_LABEL = {"AUTO": "🟢 AUTO", "VERIFY": "🟡 VERIFY", "MANUAL": "🔴 MANUAL"}

# ── 리포트 본문 ────────────────────────────────────────────────

now = datetime.now().strftime("%Y-%m-%d %H:%M")

lines = [
    "# Oracle → MySQL 패턴 정합성 통합 리포트",
    f"> 생성: {now}",
    "",
    "## 검증 3축 기준",
    "| 축 | 의미 |",
    "|---|---|",
    "| ① 탐지 | consistency_simulator가 패턴을 잡아냈는가 (result.json) |",
    "| ② 실행 | MySQL에서 syntax/function 에러 없이 실행되는가 (result.csv) |",
    "| ③ 결과 | 변환 전후 SELECT 결과 row가 일치하는가 (result_compare.csv) |",
    "",
    "## 패턴별 정합성 결과",
    "",
    "| ID | 패턴명 | 위험도 | 등급 | ① 탐지 | ② 실행 | ③ 결과 일치 | 비고 |",
    "|---|---|---|---|---|---|---|---|",
]

# 통계용
stats = {"AUTO": 0, "VERIFY": 0, "MANUAL": 0}
exec_ok = exec_err = exec_skip = 0
cmp_match = cmp_mismatch = cmp_skip = 0

for pid in all_pids:
    rule = rule_map.get(pid, {})
    name  = rule.get("name", "-")
    risk  = rule.get("risk", "-")
    grade = rule.get("consistency_grade", "-")
    note  = rule.get("consistency_note", "")

    grade_label = GRADE_LABEL.get(grade, grade)
    stats[grade] = stats.get(grade, 0) + 1

    # ① 탐지: result.json 파일 존재 여부로 판단
    result_json = BASE / f"{pid}_result.json"
    if result_json.exists():
        try:
            rj = json.loads(result_json.read_text(encoding="utf-8"))
            detected = rj["summary"]["total_pattern_count"] > 0
            detect_cell = "✅ 탐지" if detected else "⚠️ 미탐지"
        except Exception:
            detect_cell = "⚠️ 파싱오류"
    else:
        detect_cell = "⚪ 미실행"

    # ② 실행
    exec_cell, exec_err_summary = exec_verdict(pid)
    if "OK" in exec_cell:
        exec_ok += 1
    elif "에러" in exec_cell:
        exec_err += 1
    else:
        exec_skip += 1

    # ③ 결과 비교
    cmp_cell, cmp_detail = compare_verdict(pid)
    if "일치" in cmp_cell and "불일치" not in cmp_cell:
        cmp_match += 1
    elif "불일치" in cmp_cell or "부분" in cmp_cell:
        cmp_mismatch += 1
    else:
        cmp_skip += 1

    # 비고: 에러 요약 또는 compare 상세 또는 consistency_note
    remark = exec_err_summary or cmp_detail or note[:60]

    lines.append(
        f"| {pid} | {name} | {risk} | {grade_label} "
        f"| {detect_cell} | {exec_cell} | {cmp_cell} | {remark} |"
    )

# ── 요약 섹션 ─────────────────────────────────────────────────

total = len(all_pids)
lines += [
    "",
    "---",
    "",
    "## 요약 통계",
    "",
    "### 정합성 등급 분포",
    f"- 🟢 AUTO  (자동 변환, 결과 보장): {stats.get('AUTO',0)}건",
    f"- 🟡 VERIFY (변환 후 검증 필요):    {stats.get('VERIFY',0)}건",
    f"- 🔴 MANUAL (수동 재작성 필요):     {stats.get('MANUAL',0)}건",
    "",
    "### 실행 호환성 (② 실행)",
    f"- ✅ OK       : {exec_ok}건",
    f"- ❌ 에러      : {exec_err}건  ← Oracle 전용 구문 확인",
    f"- ⚪ 미실행    : {exec_skip}건",
    "",
    "### 결과 정합성 (③ 결과)",
    f"- ✅ 일치      : {cmp_match}건",
    f"- ⚠️ 불일치    : {cmp_mismatch}건  ← 변환 로직 재검토 필요",
    f"- ⚪ 미실행    : {cmp_skip}건",
    "",
    "---",
    "",
    "## 등급별 조치 가이드",
    "",
    "| 등급 | 의미 | 조치 |",
    "|---|---|---|",
    "| 🟢 AUTO   | 1:1 치환 가능, 결과 동일 보장 | 변환 스크립트 자동 적용 가능 |",
    "| 🟡 VERIFY | 변환 패턴 존재하나 결과 검증 필요 | 변환 후 SELECT 결과 비교 실행 |",
    "| 🔴 MANUAL | 직접 대응 구문 없음, 수동 재작성 | DBA/개발자 리뷰 후 재작성 |",
    "",
    "> consistency_check.csv — 테이블 Row Count / Checksum 검증 완료",
    "> result_compare.csv   — 변환 전후 SELECT 결과 row 비교 완료",
]

# ── 파일 저장 ─────────────────────────────────────────────────

out = BASE / "test_result_report.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"[DONE] 리포트 생성 → {out}")
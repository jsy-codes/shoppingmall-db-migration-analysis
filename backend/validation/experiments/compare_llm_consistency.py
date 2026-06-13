"""
LLM 일관성 비교 실험: Claude vanilla vs 우리 시스템(/diagnose)
=============================================================

목적:
  동일한 Oracle SQL을 5회 반복 호출했을 때
  - Claude vanilla (시스템 프롬프트 없음): 위험도 판단이 얼마나 흔들리는가
  - 우리 시스템(/diagnose): 항상 동일한 패턴 ID + 점수가 나오는가

핵심 메시지:
  같은 Claude API를 쓰더라도, 시스템 프롬프트와 결정론적 탐지 엔진이 없으면
  동일 SQL에 대해 매번 다른 위험도를 판단한다.

실행 방법:
  pip install anthropic requests

  # Claude vanilla만 테스트 (우리 서버 없어도 됨)
  python compare_llm_consistency.py --api-key YOUR_ANTHROPIC_KEY --vanilla-only --save

  # 전체 비교 (우리 서버 실행 중일 때)
  python compare_llm_consistency.py --api-key YOUR_ANTHROPIC_KEY --save

결과물:
  consistency_report.md  — 발표용 마크다운 리포트
  consistency_raw.csv    — 원시 데이터
"""

import argparse
import csv
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
import anthropic


# ══════════════════════════════════════════════════════════════
# 1. 테스트 SQL 목록
#    선택 기준: MySQL에서 즉시 에러 or 성능 저하가 명확한 이관 핵심 패턴
# ══════════════════════════════════════════════════════════════

TEST_CASES = [
    {
        "id": "P03",
        "pattern_name": "ROWNUM Pagination",
        "expected_risk": "HIGH",
        "sql": "SELECT * FROM orders WHERE ROWNUM <= 10 AND status = 'COMPLETE' ORDER BY created_at DESC",
        "why_hard": "ROWNUM은 Oracle 전용 — MySQL에서 즉시 syntax error",
    },
    {
        "id": "P04",
        "pattern_name": "NVL Function",
        "expected_risk": "MEDIUM",
        "sql": "SELECT order_id, NVL(discount_amount, 0) AS discount FROM orders WHERE NVL(status, 'N') = 'COMPLETE'",
        "why_hard": "NVL은 Oracle 전용 — MySQL에서 function not found 에러",
    },
    {
        "id": "P12",
        "pattern_name": "CONNECT BY Hierarchy",
        "expected_risk": "HIGH",
        "sql": "SELECT employee_id, manager_id, LEVEL FROM employees START WITH manager_id IS NULL CONNECT BY PRIOR employee_id = manager_id",
        "why_hard": "CONNECT BY는 Oracle 계층 쿼리 전용 — MySQL에서 syntax error, WITH RECURSIVE 재작성 필요",
    },
    {
        "id": "P14",
        "pattern_name": "Oracle Outer Join (+)",
        "expected_risk": "HIGH",
        "sql": "SELECT o.order_id, m.name FROM orders o, members m WHERE o.member_id = m.id(+) AND o.status = 'COMPLETE'",
        "why_hard": "(+) 조인 문법은 Oracle 전용 — MySQL에서 즉시 syntax error",
    },
    {
        "id": "P23",
        "pattern_name": "SEQUENCE NEXTVAL",
        "expected_risk": "HIGH",
        "sql": "INSERT INTO orders (order_id, member_id, status) VALUES (order_seq.NEXTVAL, 1001, 'PENDING')",
        "why_hard": "SEQUENCE.NEXTVAL은 Oracle 전용 — MySQL AUTO_INCREMENT로 전면 재작성 필요",
    },
    {
        "id": "P17",
        "pattern_name": "MERGE INTO Statement",
        "expected_risk": "HIGH",
        "sql": "MERGE INTO members m USING (SELECT 1001 AS id, 'hong@test.com' AS email FROM DUAL) src ON (m.id = src.id) WHEN MATCHED THEN UPDATE SET m.email = src.email WHEN NOT MATCHED THEN INSERT (id, email) VALUES (src.id, src.email)",
        "why_hard": "MERGE INTO는 Oracle 전용 — MySQL에서 INSERT ... ON DUPLICATE KEY UPDATE로 재작성 필요",
    },
    {
        "id": "P24",
        "pattern_name": "LISTAGG Aggregation",
        "expected_risk": "HIGH",
        "sql": "SELECT department_id, LISTAGG(employee_name, ', ') WITHIN GROUP (ORDER BY hire_date) AS names FROM employees GROUP BY department_id",
        "why_hard": "LISTAGG는 Oracle 전용 — MySQL GROUP_CONCAT으로 재작성 필요",
    },
    {
        "id": "P02",
        "pattern_name": "Function on Indexed Column",
        "expected_risk": "HIGH",
        "sql": "SELECT member_id, email FROM members WHERE UPPER(email) = 'HONG@TEST.COM' AND status = 'ACTIVE'",
        "why_hard": "UPPER()로 인덱스 무력화 — 성능 저하 패턴, 범용 LLM이 HIGH로 판단 안 할 수 있음",
    },
]


# ══════════════════════════════════════════════════════════════
# 2. Claude vanilla 호출 (시스템 프롬프트 없이 — 범용 LLM 재현)
# ══════════════════════════════════════════════════════════════

VANILLA_PROMPT = """다음 SQL을 Oracle에서 MySQL로 이관할 때 위험도를 평가해주세요.

위험도는 반드시 HIGH/MEDIUM/LOW중 하나만 답변 첫 줄에 작성하고,
그 다음 줄에 이유를 간단히 설명해주세요.

SQL:
{sql}"""


def call_vanilla_claude(sql: str, client: anthropic.Anthropic, retry: int = 3) -> dict:
    """Claude API — 시스템 프롬프트 없이 순수 호출 (범용 LLM 재현)"""
    for attempt in range(retry):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",  # 팀에서 이미 쓰는 모델
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": VANILLA_PROMPT.format(sql=sql),
                }],
                # temperature 기본값(1.0) 사용 → 확률적 응답 재현
            )
            raw_text = message.content[0].text.strip()

            # 위험도 파싱 — 앞 3줄에서 HIGH/MEDIUM/LOW 추출
            risk_level = "UNKNOWN"
            for line in raw_text.split("\n")[:3]:
                upper = line.upper()
                if "HIGH" in upper:
                    risk_level = "HIGH"
                    break
                elif "MEDIUM" in upper or "MODERATE" in upper:
                    risk_level = "MEDIUM"
                    break
                elif "LOW" in upper:
                    risk_level = "LOW"
                    break

            return {"risk_level": risk_level, "raw_text": raw_text[:300], "error": None}

        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2)
            else:
                return {"risk_level": "ERROR", "raw_text": "", "error": str(e)}

    return {"risk_level": "ERROR", "raw_text": "", "error": "max retry"}


# ══════════════════════════════════════════════════════════════
# 3. 우리 시스템 /diagnose 호출
# ══════════════════════════════════════════════════════════════

def call_our_system(sql: str, base_url: str = "http://localhost:8000") -> dict:
    try:
        resp = requests.post(f"{base_url}/diagnose", json={"sql": sql}, timeout=30)
        # HTTP 에러 상세 출력
        if resp.status_code != 200:
            print(f"    [HTTP {resp.status_code}] {resp.text[:300]}")
            return {"risk_level": "ERROR", "risk_score": 0, "matched_pattern_ids": [],
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        # 서버가 error 키를 반환한 경우
        if "error" in data:
            print(f"    [서버 에러] {data['error']}")
        return {
            "risk_level": data.get("risk_level", "UNKNOWN"),
            "risk_score": data.get("risk_score", 0),
            "matched_pattern_ids": data.get("matched_pattern_ids", []),
            "error": None,
        }
    except requests.exceptions.ConnectionError:
        print(f"    [연결 실패] {base_url} 에 연결할 수 없음 — 서버 실행 중인지 확인")
        return {"risk_level": "ERROR", "risk_score": 0, "matched_pattern_ids": [], "error": "ConnectionError"}
    except Exception as e:
        print(f"    [예외] {type(e).__name__}: {e}")
        return {"risk_level": "ERROR", "risk_score": 0, "matched_pattern_ids": [], "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 4. 일관성 지표 계산
# ══════════════════════════════════════════════════════════════

def calc_consistency(responses: list) -> dict:
    valid = [r for r in responses if r not in ("ERROR", "UNKNOWN")]
    if not valid:
        return {"consistency_rate": 0.0, "dominant": "N/A", "distribution": {}}
    counter = Counter(valid)
    dominant, count = counter.most_common(1)[0]
    return {
        "consistency_rate": round(count / len(valid), 2),
        "dominant": dominant,
        "distribution": dict(counter),
    }

def consistency_emoji(rate: float) -> str:
    if rate >= 1.0:   return "✅"
    elif rate >= 0.8: return "🟡"
    else:             return "🔴"


# ══════════════════════════════════════════════════════════════
# 5. 실험 실행
# ══════════════════════════════════════════════════════════════

def run_experiment(api_key: str, repeat: int = 5, vanilla_only: bool = False,
                   our_system_url: str = "http://localhost:8000", delay: float = 1.0) -> list:

    client = anthropic.Anthropic(api_key=api_key)
    all_results = []

    for case in TEST_CASES:
        print(f"\n{'='*60}")
        print(f"[{case['id']}] {case['pattern_name']}  (예상: {case['expected_risk']})")

        result = {
            "pattern_id":    case["id"],
            "pattern_name":  case["pattern_name"],
            "expected_risk": case["expected_risk"],
            "why_hard":      case["why_hard"],
            "sql":           case["sql"],
            "vanilla_responses": [],
            "our_responses":     [],
        }

        # ── Claude vanilla 반복 호출 ──────────────────────
        print(f"  [Claude vanilla] {repeat}회 호출 중...")
        for i in range(repeat):
            resp = call_vanilla_claude(case["sql"], client)
            result["vanilla_responses"].append(resp["risk_level"])
            print(f"    {i+1}회: {resp['risk_level']}")
            time.sleep(delay)

        result["vanilla_consistency"] = calc_consistency(result["vanilla_responses"])
        vc = result["vanilla_consistency"]
        print(f"  → 일관성: {vc['consistency_rate']*100:.0f}%  분포: {vc['distribution']}")

        # ── 우리 시스템 반복 호출 ──────────────────────────
        if not vanilla_only:
            print(f"  [우리 시스템] {repeat}회 호출 중...")
            our_scores = []
            our_pattern_ids_list = []

            for i in range(repeat):
                resp = call_our_system(case["sql"], our_system_url)
                result["our_responses"].append(resp["risk_level"])
                our_scores.append(resp["risk_score"])
                our_pattern_ids_list.append(resp["matched_pattern_ids"])
                print(f"    {i+1}회: {resp['risk_level']}  score={resp['risk_score']}  patterns={resp['matched_pattern_ids']}")

            result["our_consistency"]    = calc_consistency(result["our_responses"])
            result["our_scores"]         = our_scores
            result["our_pattern_ids"]    = our_pattern_ids_list
            oc = result["our_consistency"]
            print(f"  → 일관성: {oc['consistency_rate']*100:.0f}%  분포: {oc['distribution']}")
        else:
            result["our_consistency"] = None

        all_results.append(result)

    return all_results


# ══════════════════════════════════════════════════════════════
# 6. 리포트 생성
# ══════════════════════════════════════════════════════════════

def generate_report(results: list, repeat: int = 5) -> str:
    lines = []
    lines.append("# LLM 일관성 비교 실험 리포트")
    lines.append(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## 실험 개요")
    lines.append(f"- 테스트 SQL: {len(results)}종 (Oracle 이관 핵심 위험 패턴)")
    lines.append(f"- 반복 횟수: {repeat}회 (동일 SQL, 동일 조건)")
    lines.append("- Claude vanilla: 시스템 프롬프트 없음, temperature 기본값(1.0)")
    lines.append("- 우리 시스템: pattern_rules.json 기반 결정론적 탐지 + Claude API")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 요약 테이블 ──────────────────────────────────────────
    has_our = any(r.get("our_consistency") for r in results)
    lines.append("## 결과 요약")
    lines.append("")

    if has_our:
        lines.append("| 패턴 | 예상 | Claude vanilla 분포 | vanilla 일관성 | 우리 시스템 분포 | 우리 일관성 |")
        lines.append("|------|------|---------------------|--------------|----------------|-----------|")
    else:
        lines.append("| 패턴 | 예상 | Claude vanilla 분포 | vanilla 일관성 |")
        lines.append("|------|------|---------------------|--------------|")

    vanilla_rates, our_rates = [], []

    for r in results:
        vc = r["vanilla_consistency"]
        v_rate = vc["consistency_rate"]
        vanilla_rates.append(v_rate)
        v_dist = str(vc["distribution"]).replace("'", "")
        v_emoji = consistency_emoji(v_rate)

        if has_our and r.get("our_consistency"):
            oc = r["our_consistency"]
            o_rate = oc["consistency_rate"]
            our_rates.append(o_rate)
            o_dist = str(oc["distribution"]).replace("'", "")
            o_emoji = consistency_emoji(o_rate)
            lines.append(f"| {r['pattern_id']} {r['pattern_name']} | {r['expected_risk']} "
                         f"| {v_dist} | {v_emoji} {v_rate*100:.0f}% "
                         f"| {o_dist} | {o_emoji} {o_rate*100:.0f}% |")
        else:
            lines.append(f"| {r['pattern_id']} {r['pattern_name']} | {r['expected_risk']} "
                         f"| {v_dist} | {v_emoji} {v_rate*100:.0f}% |")

    lines.append("")

    # ── 핵심 수치 ──────────────────────────────────────────
    avg_vanilla = sum(vanilla_rates) / len(vanilla_rates) if vanilla_rates else 0
    lines.append("## 핵심 수치")
    lines.append("")
    lines.append(f"- **Claude vanilla 평균 일관성: {avg_vanilla*100:.1f}%**")
    if our_rates:
        avg_our = sum(our_rates) / len(our_rates)
        lines.append(f"- **우리 시스템 평균 일관성: {avg_our*100:.1f}%**")
        lines.append(f"- **일관성 차이: +{(avg_our - avg_vanilla)*100:.1f}%p (우리 시스템 우위)**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 패턴별 상세 ──────────────────────────────────────────
    lines.append("## 패턴별 상세")
    lines.append("")
    for r in results:
        vc = r["vanilla_consistency"]
        lines.append(f"### {r['pattern_id']} — {r['pattern_name']}")
        lines.append(f"**왜 어려운가**: {r['why_hard']}")
        lines.append(f"**vanilla 5회**: {r['vanilla_responses']}  →  일관성 {vc['consistency_rate']*100:.0f}%")
        if r.get("our_consistency"):
            oc = r["our_consistency"]
            scores = r.get("our_scores", [])
            score_range = f"{min(scores)}~{max(scores)}점" if scores else "N/A"
            lines.append(f"**우리 시스템 5회**: {r['our_responses']}  →  일관성 {oc['consistency_rate']*100:.0f}%  점수: {score_range}")
        lines.append("")

    # ── 발표 핵심 메시지 ─────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 발표 핵심 메시지")
    lines.append("")
    lines.append("> **같은 Claude API를 쓰더라도, 시스템 프롬프트와 결정론적 탐지 엔진이 없으면")
    lines.append("> 동일 SQL에 대해 매번 다른 위험도를 판단합니다.**")
    lines.append(">")
    lines.append("> 우리 시스템은 pattern_rules.json 기반 탐지 → 위험도 점수 → Claude 해석의")
    lines.append("> 3단계 파이프라인으로, LLM이 수치를 만드는 게 아니라 실측 기반 수치를 해석합니다.")
    lines.append("> 동일 SQL → 동일 패턴 ID → 동일 점수가 보장되는 것이 핵심 차이입니다.")

    return "\n".join(lines)


def save_csv(results: list, path: Path) -> None:
    rows = []
    for r in results:
        for i, v_resp in enumerate(r["vanilla_responses"]):
            rows.append({
                "pattern_id":              r["pattern_id"],
                "pattern_name":            r["pattern_name"],
                "expected_risk":           r["expected_risk"],
                "trial":                   i + 1,
                "vanilla_response":        v_resp,
                "our_response":            r["our_responses"][i] if i < len(r["our_responses"]) else "",
                "vanilla_consistency_rate": r["vanilla_consistency"]["consistency_rate"],
            })
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"[CSV] 저장 → {path}")


# ══════════════════════════════════════════════════════════════
# 7. 진입점
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM 일관성 비교 실험 (Claude vanilla vs 우리 시스템)")
    parser.add_argument("--api-key",      required=True,              help="Anthropic API 키")
    parser.add_argument("--repeat",       type=int,   default=5,      help="반복 횟수 (기본 5)")
    parser.add_argument("--vanilla-only", action="store_true",        help="우리 서버 없이 vanilla만 테스트")
    parser.add_argument("--our-url",      default="http://localhost:8000", help="우리 시스템 URL")
    parser.add_argument("--save",         action="store_true",        help="결과 파일 저장")
    parser.add_argument("--delay",        type=float, default=1.0,    help="API 호출 간격(초)")
    args = parser.parse_args()

    print("=" * 60)
    print("LLM 일관성 비교 실험 시작")
    print(f"  테스트 케이스: {len(TEST_CASES)}종")
    print(f"  반복 횟수: {args.repeat}회")
    print(f"  vanilla only: {args.vanilla_only}")
    print("=" * 60)

    results = run_experiment(
        api_key=args.api_key,
        repeat=args.repeat,
        vanilla_only=args.vanilla_only,
        our_system_url=args.our_url,
        delay=args.delay,
    )

    if not results:
        print("[오류] 실험 결과 없음")
        exit(1)

    report = generate_report(results, repeat=args.repeat)
    print("\n" + "=" * 60)
    print(report)

    if args.save:
        out_dir = Path(__file__).parent
        report_path = out_dir / "consistency_report.md"
        csv_path    = out_dir / "consistency_raw.csv"
        report_path.write_text(report, encoding="utf-8")
        print(f"\n[MD] 리포트 저장 → {report_path}")
        save_csv(results, csv_path)
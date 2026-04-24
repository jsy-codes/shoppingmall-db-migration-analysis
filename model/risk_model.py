"""
Oracle → MySQL 마이그레이션 위험도 점수 계산 모델
=======================================================

[설계 원칙]
  시뮬레이터(consistency_simulator.py)가 탐지한 패턴을 입력으로 받아 점수화.
  SQL 직접 분석(독자 regex) 없음 → 탐지 결과와 항상 일치.

[점수 구성 — 두 축]

  축 1 ─ severity floor
    "이 등급 패턴이 하나만 탐지돼도 이 점수를 보장"
    값이 등급 임계값과 동일하게 설계 → HIGH 1개 탐지 = 즉시 HIGH 등급 진입

      severity │ floor │ 등급 임계값
      ─────────┼───────┼────────────
      HIGH     │  80   │  ≥ 80
      MEDIUM   │  40   │  ≥ 40
      LOW      │  10   │  < 40

  축 2 ─ failure_type category bonus
    패턴이 운영 환경에서 어떤 유형의 실패를 유발하는지에 따라 차등 추가.
    22개 패턴의 failure_type을 4개 카테고리로 분류:

      QUERY_FAILURE   : 즉시 실행 실패 (구문 오류, 페이징 실패)       +10
      DATA_INTEGRITY  : 실행은 되나 결과가 틀림 (silent fail, 치명적)  +8
      PERFORMANCE     : 인덱스 무력화·풀스캔 등 성능 저하              +5
      COMPATIBILITY   : 단순 함수/타입 호환 변환                       +2

    → 같은 HIGH라도 P03(ROWNUM, QUERY_FAILURE)=90점 vs P09(JOIN Scan, PERFORMANCE)=85점

[집계 공식]
  1. 각 패턴: contribution = (floor + bonus)
  2. 동일 severity가 복수일 때 감쇠 적용: contribution × decay^n  (decay=0.25, n=중복 순서)
     → MEDIUM 패턴이 아무리 많아도 합산 한도 ≈ 71점 < HIGH 임계값(80) 보장
  3. 서로 다른 카테고리 복수 탐지 시 조합 보너스 추가 (2종+3 / 3종+6 / 4종+10)
  4. clamp(0, 100)

[반환값 호환성]
  기존 코드(query: str 입력)의 리턴 키를 유지하면서 신규 필드 추가:
    risk_score        (기존 동일)
    risk_level        (기존 동일 — "HIGH"/"MEDIUM"/"LOW" 통일, "MED" 없음)
    detected_patterns (기존 동일 형식: 문자열 리스트)
    contributions     (신규 — app.py 차트 데이터용)
    score_breakdown   (신규 — 발표·디버그용 점수 내역)

[수정 이력]
  v1: SQL 직접 분석 4-패턴 하드코딩 (원본)
  v2: sim_result 입력 + severity/임계값 역전 버그 수정
  v3: failure_type 카테고리 도입, 감쇠·조합 보너스 체계화
  v4: 리턴값 호환성 정비, MED 정규화 완전 적용 (현재)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import json


# ══════════════════════════════════════════════════════════════════════════════
# 1. Severity 정규화
#    pattern_rules.json 이 "MED" 를 쓸 수 있으므로 내부에서 "MEDIUM" 으로 통일.
#    외부 반환값은 "HIGH" / "MEDIUM" / "LOW" 만 사용.
# ══════════════════════════════════════════════════════════════════════════════

_SEVERITY_ALIAS: dict[str, str] = {
    "HIGH":   "HIGH",
    "MED":    "MEDIUM",
    "MEDIUM": "MEDIUM",
    "LOW":    "LOW",
}

def _norm_sev(raw: str) -> str:
    return _SEVERITY_ALIAS.get(raw.strip().upper(), "LOW")


# ══════════════════════════════════════════════════════════════════════════════
# 2. 축 1 — severity floor
#    floor 값 = 해당 등급 임계값과 동일하게 설계.
#    이 규칙 하나로 "HIGH 패턴 1개 → HIGH 등급 보장"이 구조적으로 성립.
# ══════════════════════════════════════════════════════════════════════════════

SEVERITY_FLOOR: dict[str, int] = {
    "HIGH":   80,
    "MEDIUM": 40,
    "LOW":    10,
}

THRESHOLD_HIGH = 80   # SEVERITY_FLOOR["HIGH"] 와 항상 동일해야 함
THRESHOLD_MED  = 40   # SEVERITY_FLOOR["MEDIUM"] 와 항상 동일해야 함


# ══════════════════════════════════════════════════════════════════════════════
# 3. 축 2 — failure_type → category → bonus
#    pattern_rules.json 의 22개 failure_type 을 4개 카테고리로 매핑.
#    분류 기준: 운영 환경에서의 치명도
#      QUERY_FAILURE  — 즉시 실행 실패, 가장 명확하게 드러남
#      DATA_INTEGRITY — 실행은 되지만 결과가 틀림 (발견 어렵고 파급 큼)
#      PERFORMANCE    — 성능 저하, 측정/최적화 여지 있음
#      COMPATIBILITY  — 단순 변환, 대응 방법 명확
# ══════════════════════════════════════════════════════════════════════════════

_FAILURE_CATEGORY: dict[str, str] = {
    "PAGINATION_MIGRATION_ERROR":      "QUERY_FAILURE",
    "HIERARCHY_QUERY_MIGRATION":       "QUERY_FAILURE",
    "JOIN_SYNTAX_INCOMPATIBILITY":     "QUERY_FAILURE",
    "UPSERT_SYNTAX_MIGRATION":         "QUERY_FAILURE",

    "TYPE_MISMATCH_INDEX_BYPASS":      "DATA_INTEGRITY",
    "TEMPORAL_TYPE_MISMATCH":          "DATA_INTEGRITY",
    "CHAR_PADDING_COMPARISON":         "DATA_INTEGRITY",
    "SET_OPERATOR_INCOMPATIBILITY":    "DATA_INTEGRITY",
    "DATE_FORMAT_FUNCTION_MIGRATION":  "DATA_INTEGRITY",
    "DATE_PARSE_FUNCTION_MIGRATION":   "DATA_INTEGRITY",
    "DATE_TRUNCATION_MIGRATION":       "DATA_INTEGRITY",
    "TIMESTAMP_PRECISION_COMPATIBILITY": "DATA_INTEGRITY",

    "FUNCTION_INDEX_BYPASS":           "PERFORMANCE",
    "FUNCTION_BASED_INDEX_LOSS":       "PERFORMANCE",
    "JOIN_FULL_SCAN":                  "PERFORMANCE",
    "NESTED_QUERY_DEGRADATION":        "PERFORMANCE",

    "FUNCTION_COMPATIBILITY":          "COMPATIBILITY",
    "STRING_TYPE_COMPATIBILITY":       "COMPATIBILITY",
    "SYSTEM_TABLE_DEPENDENCY":         "COMPATIBILITY",
}

CATEGORY_BONUS: dict[str, int] = {
    "QUERY_FAILURE":  10,
    "DATA_INTEGRITY":  8,
    "PERFORMANCE":     5,
    "COMPATIBILITY":   2,
}

def _category(failure_type: str) -> str:
    return _FAILURE_CATEGORY.get(failure_type.strip(), "COMPATIBILITY")

def _bonus(failure_type: str) -> int:
    return CATEGORY_BONUS[_category(failure_type)]


# ══════════════════════════════════════════════════════════════════════════════
# 4. 집계 파라미터
# ══════════════════════════════════════════════════════════════════════════════

# 동일 severity 패턴 반복 시 감쇠율.
# MEDIUM 패턴 무한 누적 합산 상한 = 48 / (1 - 0.25) = 64 < THRESHOLD_HIGH(80)
# → MEDIUM만으로는 구조적으로 HIGH 등급 불가 보장.
DECAY_RATE = 0.25

# 서로 다른 failure_type 카테고리가 복수 감지될 때 추가 보너스.
# "즉시 실패 + 데이터 불일치 동시 발생"은 단순 합산보다 위험.
MULTI_CATEGORY_BONUS: dict[int, int] = {2: 3, 3: 6, 4: 10}


# ══════════════════════════════════════════════════════════════════════════════
# 5. 데이터 클래스
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PatternContribution:
    pattern_id:     str
    pattern_name:   str
    severity:       str
    failure_type:   str
    category:       str
    floor:          int
    bonus:          int
    applied_score:  float   # 감쇠 적용 후 실제 기여 점수


@dataclass
class RiskResult:
    risk_score:           int
    risk_level:           str
    max_severity:         str
    base_score:           float
    multi_category_bonus: int
    unique_categories:    list[str]
    contributions:        list[PatternContribution] = field(default_factory=list)
    note:                 Optional[str] = None

    def to_dict(self) -> dict:
        """
        기존 코드와 호환되는 키 구조로 반환.
        detected_patterns: 기존 형식(문자열 리스트) 유지.
        """
        detected_patterns = [
            f"[{c.severity}][{c.category}] {c.pattern_name} — {c.failure_type}"
            for c in self.contributions
        ]
        return {
            # ── 기존 호환 키 (app.py, 프론트엔드에서 그대로 사용 가능) ──────
            "risk_score":        self.risk_score,
            "risk_level":        self.risk_level,
            "detected_patterns": detected_patterns,

            # ── 신규 키 (app.py 차트 데이터·디버그용) ──────────────────────
            "contributions": [
                {
                    "pattern_id":    c.pattern_id,
                    "pattern_name":  c.pattern_name,
                    "severity":      c.severity,
                    "failure_type":  c.failure_type,
                    "category":      c.category,
                    "floor":         c.floor,
                    "bonus":         c.bonus,
                    "applied_score": round(c.applied_score, 1),
                }
                for c in self.contributions
            ],
            "score_breakdown": {
                "base_score":           round(self.base_score, 1),
                "multi_category_bonus": self.multi_category_bonus,
                "unique_categories":    self.unique_categories,
                "max_severity":         self.max_severity,
            },
            "note": self.note,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 6. RiskPredictor
# ══════════════════════════════════════════════════════════════════════════════

class RiskPredictor:
    """
    Oracle → MySQL 위험도 점수 계산기.

    [사용법]
        sim_result = evaluate_sql(sql, RULES)        # consistency_simulator
        result     = predictor.evaluate_risk_score(sim_result)

        result["risk_score"]        # 0~100 정수
        result["risk_level"]        # "HIGH" / "MEDIUM" / "LOW"
        result["detected_patterns"] # 문자열 리스트 (기존 형식 호환)
        result["contributions"]     # 패턴별 점수 기여 내역
        result["score_breakdown"]   # 집계 내역 (발표·디버그용)

    Parameters
    ----------
    decay_rate : float
        동일 severity 패턴 반복 감쇠율 (기본 0.25).
        낮출수록 추가 패턴 영향이 작아짐.
    """

    def __init__(self, decay_rate: float = DECAY_RATE):
        self.decay = decay_rate

    def evaluate_risk_score(self, sim_result: dict) -> dict:
        """
        consistency_simulator.evaluate_sql() 반환값을 입력으로 받는다.

        Parameters
        ----------
        sim_result : dict
            {
              "summary": {"max_severity": str, "severity_counts": dict, ...},
              "details": [{"matched_patterns": [...], ...}, ...]
            }

        Returns
        -------
        dict  — RiskResult.to_dict() 참고
        """
        return self._compute(sim_result).to_dict()

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _compute(self, sim_result: dict) -> RiskResult:
        summary      = sim_result.get("summary", {})
        details      = sim_result.get("details", [])
        max_severity = _norm_sev(summary.get("max_severity", "LOW"))

        patterns = self._collect(details)

        if not patterns:
            return RiskResult(
                risk_score=0, risk_level="LOW", max_severity=max_severity,
                base_score=0.0, multi_category_bonus=0, unique_categories=[],
                note="탐지된 위험 패턴 없음 — 이관 위험도 낮음",
            )

        contributions, base = self._aggregate(patterns)
        cats     = sorted({c.category for c in contributions})
        cat_b    = MULTI_CATEGORY_BONUS.get(len(cats), 0)
        score    = min(100, max(0, round(base + cat_b)))
        level    = self._level(score)

        return RiskResult(
            risk_score           = score,
            risk_level           = level,
            max_severity         = max_severity,
            base_score           = base,
            multi_category_bonus = cat_b,
            unique_categories    = cats,
            contributions        = contributions,
        )

    def _collect(self, details: list[dict]) -> list[dict]:
        """
        모든 statement 의 matched_patterns 를 수집.
        · 중복 pattern_id 제거 (첫 등장 유지)
        · severity 정규화
        · (floor + bonus) 기준 내림차순 정렬 → 높은 점수부터 감쇠 적용
        """
        seen: set[str] = set()
        out:  list[dict] = []
        for detail in details:
            for p in detail.get("matched_patterns", []):
                pid = p.get("id", "")
                if pid in seen:
                    continue
                seen.add(pid)
                p2 = dict(p)
                p2["severity"] = _norm_sev(p.get("severity", "LOW"))
                out.append(p2)

        out.sort(
            key=lambda p: (
                SEVERITY_FLOOR.get(p["severity"], 10)
                + _bonus(p.get("failure_type", ""))
            ),
            reverse=True,
        )
        return out

    def _aggregate(
        self, patterns: list[dict]
    ) -> tuple[list[PatternContribution], float]:
        """
        severity별 독립 감쇠 카운터로 기여도 합산.

        n번째(0-indexed) 동일 severity 패턴의 기여도:
            (floor + bonus) × decay^n

        severity가 다르면 카운터 독립 → HIGH 감쇠가 MEDIUM에 영향 없음.
        """
        sev_count: dict[str, int] = {}
        contribs:  list[PatternContribution] = []
        total = 0.0

        for p in patterns:
            sev   = p["severity"]
            ft    = p.get("failure_type", "")
            fl    = SEVERITY_FLOOR.get(sev, 10)
            bns   = _bonus(ft)
            base  = fl + bns
            n     = sev_count.get(sev, 0)
            applied = base * (self.decay ** n)
            sev_count[sev] = n + 1
            total += applied

            contribs.append(PatternContribution(
                pattern_id   = p.get("id", ""),
                pattern_name = p.get("name", ""),
                severity     = sev,
                failure_type = ft,
                category     = _category(ft),
                floor        = fl,
                bonus        = bns,
                applied_score = applied,
            ))

        return contribs, total

    @staticmethod
    def _level(score: int) -> str:
        if score >= THRESHOLD_HIGH:
            return "HIGH"
        if score >= THRESHOLD_MED:
            return "MEDIUM"
        return "LOW"


# ══════════════════════════════════════════════════════════════════════════════
# 7. 단독 검증
# ══════════════════════════════════════════════════════════════════════════════

def _mock(patterns: list[dict], max_sev: str = "HIGH") -> dict:
    return {
        "summary": {"max_severity": max_sev},
        "details": [{"matched_patterns": patterns}],
    }


if __name__ == "__main__":
    predictor = RiskPredictor()

    # pattern_rules.json 의 실제 패턴 데이터로 케이스 구성
    CASES = [
        ("HIGH 1개 — QUERY_FAILURE   (P03 ROWNUM)",
         _mock([{"id":"P03","name":"ROWNUM Pagination",    "severity":"HIGH",  "failure_type":"PAGINATION_MIGRATION_ERROR"}])),
        ("HIGH 1개 — PERFORMANCE     (P09 JOIN Scan)",
         _mock([{"id":"P09","name":"JOIN Without Index",   "severity":"HIGH",  "failure_type":"JOIN_FULL_SCAN"}])),
        ("HIGH 2개 — 같은 카테고리   (P03+P14)",
         _mock([{"id":"P03","name":"ROWNUM Pagination",    "severity":"HIGH",  "failure_type":"PAGINATION_MIGRATION_ERROR"},
                {"id":"P14","name":"Oracle Outer Join (+)","severity":"HIGH",  "failure_type":"JOIN_SYNTAX_INCOMPATIBILITY"}])),
        ("MEDIUM 1개 — DATA_INTEGRITY (P01 Implicit Cast)",
         _mock([{"id":"P01","name":"Implicit Type Cast",   "severity":"MEDIUM","failure_type":"TYPE_MISMATCH_INDEX_BYPASS"}], "MEDIUM")),
        ("MEDIUM 5개 — HIGH 임계값 미달 확인",
         _mock([{"id":"P01","name":"Implicit Type Cast",   "severity":"MEDIUM","failure_type":"TYPE_MISMATCH_INDEX_BYPASS"},
                {"id":"P05","name":"DATE vs DATETIME",     "severity":"MEDIUM","failure_type":"TEMPORAL_TYPE_MISMATCH"},
                {"id":"P10","name":"Nested Subquery",      "severity":"MEDIUM","failure_type":"NESTED_QUERY_DEGRADATION"},
                {"id":"P11","name":"DECODE Function",      "severity":"MED",   "failure_type":"FUNCTION_COMPATIBILITY"},  # "MED" 정규화 테스트
                {"id":"P13","name":"START WITH Hierarchy", "severity":"MEDIUM","failure_type":"HIERARCHY_QUERY_MIGRATION"}], "MEDIUM")),
        ("LOW 1개 — COMPATIBILITY    (P04 NVL)",
         _mock([{"id":"P04","name":"NVL Function",         "severity":"LOW",   "failure_type":"FUNCTION_COMPATIBILITY"}], "LOW")),
        ("복합 — HIGH+MEDIUM+LOW+4카테고리 (최대 복합)",
         _mock([{"id":"P03","name":"ROWNUM Pagination",    "severity":"HIGH",  "failure_type":"PAGINATION_MIGRATION_ERROR"},
                {"id":"P01","name":"Implicit Type Cast",   "severity":"MEDIUM","failure_type":"TYPE_MISMATCH_INDEX_BYPASS"},
                {"id":"P09","name":"JOIN Without Index",   "severity":"HIGH",  "failure_type":"JOIN_FULL_SCAN"},
                {"id":"P04","name":"NVL Function",         "severity":"LOW",   "failure_type":"FUNCTION_COMPATIBILITY"}])),
    ]

    HEADER = f"{'케이스':<48} {'score':>5}  {'level':<8}  {'categories'}"
    SEP    = "─" * 80
    print(f"\n{SEP}\n{HEADER}\n{SEP}")
    for desc, mock in CASES:
        r    = predictor.evaluate_risk_score(mock)
        cats = r["score_breakdown"]["unique_categories"]
        print(f"{desc:<48} {r['risk_score']:>5}점  {r['risk_level']:<8}  {cats}")
        for c in r["contributions"]:
            decay_note = f"(×{DECAY_RATE}^{list(r['contributions']).index(c)})" if list(r['contributions']).index(c) > 0 else ""
            print(f"   {c['pattern_id']:<4} {c['severity']:<7} {c['category']:<16} "
                  f"floor={c['floor']:2}+bonus={c['bonus']:2}={c['floor']+c['bonus']:2} "
                  f"→ applied={c['applied_score']:5.1f} {decay_note}")
        bd = r["score_breakdown"]
        if bd["multi_category_bonus"]:
            print(f"   ↳ 다중 카테고리 보너스 (+{bd['multi_category_bonus']}): {bd['unique_categories']}")
        print()
    print(SEP)
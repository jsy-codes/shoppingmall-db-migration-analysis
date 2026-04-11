from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import json
import re
import sys
from pathlib import Path

import anthropic
import os

# [팀원 모듈 임포트] 
# 규칙 기반 시뮬레이터 / 위험도 계산 모델
# 주의: backend/validation/__init__.py 파일이 있어야함
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))
from model.risk_model import RiskPredictor
from backend.validation.consistency_simulator import load_rules, evaluate_sql
# 객체 생성
predictor = RiskPredictor()

# 시뮬레이터 규칙 로드
# RULES_PATH = Path("validation/pattern_rules.json")

BASE_DIR = Path(__file__).parent
RULES_PATH = BASE_DIR / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)
# 수정 후: 객체(Rule)를 딕셔너리로 변환하여 JSON화
try:
    # RULES가 리스트 안에 객체들이 들어있는 형태라면:
    rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in RULES]
    RULES_STR = json.dumps(rules_data, ensure_ascii=False)
except Exception as e:
    # 만약 위 방법이 안 된다면 시뮬레이터 파일 자체를 직접 읽는 방법
    with open(RULES_PATH, 'r', encoding='utf-8') as f:
        RULES_STR = f.read()

app = FastAPI()

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key는 반드시 보안 준수
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class QueryRequest(BaseModel):
    sql: str
def adjust_score_by_level(score: int, level: str) -> int:
    if level == "HIGH":
        return max(score, 70)
    elif level == "MEDIUM":
        return max(score, 40)
    else:
        return max(score, 20)
# [엔드포인트 1] 진단 기능 (AI 쿼리 진단 API)   
@app.post("/diagnose")
async def diagnose(req: QueryRequest):
    # 1. [Simulator] 규칙 기반 선행 분석
    sim_result = evaluate_sql(req.sql, RULES)
    
    # 2. 결과 가공: 매칭된 ID 목록과 최고 위험도 추출
    matched_ids = list(set(
        p["id"] for detail in sim_result["details"] 
        for p in detail["matched_patterns"]
    ))
    max_severity = sim_result["summary"]["max_severity"]
    severity_counts = sim_result["summary"]["severity_counts"]

    # 3. [Risk Model] 정량적 위험 점수 계산 (시뮬레이터 결과 연동!)
    risk_analysis = predictor.evaluate_risk_score(req.sql, sim_result)
    risk_score = risk_analysis["risk_score"]


    risk_score = adjust_score_by_level(risk_score, max_severity)
    #risk_level = risk_analysis["risk_level"] # "HIGH", "MED", "LOW"
    

    # 4. [AI 엔진] Claude에게 전달할 시스템 프롬프트 설정
    system_prompt = f"""

    당신은 Oracle에서 MySQL로의 이관 전문가입니다. 
    제공된 [이관 규칙 가이드라인]를 바탕으로 [사전 분석 결과]에 명시된 패턴을 중점적으로 사용자의 SQL을 분석하여 최적의 솔루션을 제공하세요.

    [이관 규칙 가이드라인]
    {RULES_STR}
    
    [분석 및 생성 원칙]
    1. 스크립트 보존: 사용자가 입력한 모든 SQL 문장(INSERT 등)을 생략 없이 전체 보존하여 변환하세요.
    2. 기술적 차이 명시: `reason` 항목에는 "Oracle은 [A] 방식을 쓰지만, MySQL은 [B] 방식으로 동작하므로 [C] 문제가 발생함"과 같이 아키텍처적 차이를 구체적으로 설명하세요.
    3. 실행 즉시성: `recommended_ddl`에 제공되는 코드는 사용자가 복사하여 MySQL Workbench에서 즉시 실행했을 때, 테이블 생성부터 데이터 삽입, 조회까지 에러 없이 한 번에 성공해야 합니다.
    4. 대표 규칙 선정: [사전 분석 결과]의 `matched_ids` 중 가장 위험도가 높거나(HIGH > MEDIUM > LOW) 핵심적인 패턴 ID 하나를 선택하여 `rule_id`에 할당하세요.

    [응답 지침]
    1. 언어: 반드시 한국어로 응답할 것.
    2. 형식: JSON 외의 서문이나 맺음말 등 어떠한 텍스트도 출력하지 말 것.
    3. 성능 개선: `estimated_improvement`에는 예상되는 실행 시간 단축이나 자원 소모 감소량을 수치(%)로 포함하세요.
    
    반드시 아래 JSON 형식으로만 응답하세요:
    {{
        "reason": "상세 원인 설명",
        "recommended_ddl": "MySQL용 전체 수정 스크립트",
        "estimated_improvement": "예상 성능 향상치(%)와 근거",
        "rule_id": "가장 핵심적인 패턴 ID (예: P03)"
    }}
    """

    # 5. Claude 호출: 시뮬레이터가 찾은 '이미 확정된 패턴'을 컨텍스트로 전달
    user_context = f"""
    [사전 분석 결과]
    - 감지된 패턴 ID: {matched_ids}
    - 최고 위험 등급: {max_severity}

    [대상 SQL]
    {req.sql}

    위 분석 결과를 참고하여 상세 설명과 수정된 DDL을 작성하세요.
    """

    performance_data = []
    for detail in sim_result["details"]:
        for pattern in detail["matched_patterns"]:
            # 실제 측정값이 없으므로, 패턴별 '기본 영향도'를 기준으로 before/after 시뮬레이션
            base_ms = 100 # 기준 시간
            # 위험도가 HIGH면 개선 폭을 크게(80%), LOW면 작게(20%) 설정하는 식의 로직
            improvement_rate = 0.8 if pattern["severity"] == "HIGH" else 0.4
            
            performance_data.append({
                "pattern": pattern["id"],
                "label": pattern["name"],
                "before": base_ms,
                "after": int(base_ms * (1 - improvement_rate)),
                "improvement": improvement_rate * 100
            })
    risk_score_data = []
    for rule in RULES: # pattern_rules.json의 모든 규칙
        # 이번에 탐지된 패턴 ID 목록(matched_ids)에 포함되어 있다면
        if rule.id in matched_ids:
            if risk_score < 20:
                # 시뮬레이터 결과에서 해당 패턴의 severity를 찾아 가중치 부여
                current_score = 80 if max_severity == "HIGH" else 50
            else:
                current_score = risk_score
        else:
            # 탐지 안 된 패턴은 낮은 기본 점수 부여
            current_score = 10 
            
        risk_score_data.append({
            "id": rule.id,
            "name": rule.name,
            "score": current_score
        })

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001", # 모델명 확인 필요
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_context}]
        )
        
        # AI 응답 파싱
        raw_text = message.content[0].text
        ai_json = json.loads(re.search(r'(\{.*\})', raw_text, re.DOTALL).group(1))

        # 6. [최종 통합 결과] 모든 팀원의 산출물을 하나로 합쳐 반환
        return {
            "rule_id": ai_json.get("rule_id", matched_ids[0] if matched_ids else "P00"), # AI가 뽑은 대표 ID
            "risk_level": max_severity,              # 시뮬레이터 결과
            "risk_score": risk_score,                # 리스크 스코어
            "matched_pattern_ids": matched_ids,      # 감지된 패턴 목록
            "reason": ai_json["reason"],             # Claude: 논리적 이유
            "recommended_ddl": ai_json["recommended_ddl"], # Claude: 수정 쿼리
            "estimated_improvement": ai_json["estimated_improvement"], # Claude: 기대 효과
            "simulator_detail": sim_result["details"], # 프론트엔드 상세 표시용
            "performance_data": performance_data,
            "risk_score_data": risk_score_data
        }
    
    except Exception as e:
        return {"error": str(e)}

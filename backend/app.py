from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import json
import re
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# 이관 실패 문제 패턴 정리된 규칙 파일 로드 함수
def load_rules_once():
    file_path = "validation/pattern_rules.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

GLOBAL_RULES = load_rules_once()
RULES_STR = json.dumps(GLOBAL_RULES, ensure_ascii=False, indent=2)

class QueryRequest(BaseModel):
    sql: str

# [엔드포인트 1] 진단 기능 (AI 쿼리 진단 API)
@app.post("/diagnose")
async def diagnose(req: QueryRequest):
    system_prompt = f"""
    당신은 Oracle에서 MySQL로의 이관 전문가입니다. 
    다음 제공된 [이관 규칙 가이드라인]을 바탕으로 입력된 SQL을 분석하세요.

    [이관 규칙 가이드라인]
    {RULES_STR}

    [분석 프로세스]
    1. SQL 구문 분석: 입력된 쿼리에서 Oracle 전용 함수나 구문(ROWNUM, NVL, TO_DATE 등)이 있는지 식별합니다.
    2. 규칙 매칭: 가이드라인의 'pattern'과 일치하는 요소를 찾아 'id(P01~P21)'를 할당합니다.
    3. 위험도 산정: 가이드라인의 'risk' 등급을 따르되, 실행 불가능한 구문은 반드시 'HIGH'로 분류하세요.
    4. 해결책 생성: 가이드라인의 'fix' 내용을 바탕으로 MySQL 8.0에서 동작하는 최적의 SQL을 작성하세요.

    [응답 지침]
    1. 반드시 한국어로 응답할 것.
    2. JSON 외에 어떠한 설명도 덧붙이지 말 것.
    3. recommended_ddl에는 수정된 SQL문뿐만 아니라, 필요시 CREATE INDEX 등의 DDL도 포함하세요.
    4. recommended_ddl은 바로 복사해서 실행 가능한 형태여야 함.
    5. estimated_improvement에는 예상 성능 향상 수치(%)와 기술적 이유를 포함하세요.

    반드시 아래 JSON 형식으로만 응답하세요:
    {{
      "risk_level": "HIGH/MEDIUM/LOW",
      "rule_id": "매칭된 규칙 ID (예: P01)",
      "reason": "위험 원인 (가이드라인의 reason 참고)",
      "recommended_ddl": "MySQL용 수정 쿼리 또는 DDL (가이드라인의 fix 참고)",
      "estimated_improvement": "예상 개선 효과"
    }}
    """
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": req.sql}]
        )  
        raw_text = message.content[0].text

        match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        return {"error": "JSON 응답을 찾을 수 없습니다.", "raw": raw_text}
    
    except Exception as e:
        return {"error": str(e)}

# # [엔드포인트 2] 변환 기능 (자동 쿼리 변환 API)
# @app.post('/convert')
# async def convert(req: QueryRequest):
#     # 진단 없이 순수하게 MySQL 문법으로만 변환하도록 별도 요청
#     system_prompt = "너는 SQL 변환기야. 입력된 Oracle SQL을 오직 MySQL 표준 문법으로 변환하여 SQL 문장만 출력해."
#     try:
#         message = client.messages.create(
#             model="claude-haiku-4-5-20251001", # 비용 효율적인 하이쿠 모델 권장
#             max_tokens=500,
#             system=system_prompt,
#             messages=[{"role": "user", "content": req.sql}]
#         )
#         return {"converted_sql": message.content[0].text.strip()}
#     except Exception as e:
#         return {"error": str(e)}

# @app.post('/convert')
# async def convert(req: QueryRequest):
#     # 별도로 AI를 호출하지 않고, 이미 검증된 diagnose 로직의 결과값만 활용
#     diag_result = await diagnose(req)
#     if "error" in diag_result:
#         return diag_result
#     return {"converted_sql": diag_result.get('recommended_ddl')}
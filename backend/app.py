from fastapi import FastAPI
from pydantic import BaseModel
import anthropic
import json
import re
import os

app = FastAPI()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# 1. 정리된 규칙 파일 로드 함수
def load_rules():
    file_path = "validation/pattern_rules.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

class QueryRequest(BaseModel):
    sql: str

@app.post("/diagnose")
async def diagnose(req: QueryRequest):
    # 파일에서 규칙을 읽어와 프롬프트에 동적으로 삽입
    rules_data = load_rules()
    rules_str = json.dumps(rules_data, ensure_ascii=False, indent=2)

    system_prompt = f"""
    당신은 Oracle에서 MySQL로의 이관 전문가입니다. 
    다음 제공된 [이관 규칙 가이드라인]을 엄격히 준수하여 분석하세요.

    [이관 규칙 가이드라인]
    {rules_str}

    [응답 지침]
    1. 모든 답변은 한국어로 작성하세요.
    2. rule_id는 반드시 가이드라인에 정의된 ID(P01~P10)를 정확히 사용하세요.
    3. recommended_ddl에는 수정된 SQL문뿐만 아니라, 필요시 CREATE INDEX 등의 DDL도 포함하세요.
    4. estimated_improvement에는 예상 성능 향상 수치(%)와 기술적 이유를 포함하세요.

    반드시 아래 JSON 형식으로만 응답하세요:
    {{
      "risk_level": "HIGH/MEDIUM/LOW",
      "rule_id": "매칭된 규칙 ID (예: P01)",
      "reason": "위험 원인 (가이드라인의 description 참고)",
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
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {{"error": "파싱 실패", "raw": raw_text}}

    except Exception as e:
        return {{"error": str(e)}}
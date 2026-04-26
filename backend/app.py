from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from pathlib import Path
import json
import re
import sys
import uuid
import anthropic
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

from sqlalchemy import text
from sqlalchemy import desc

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI()

secret_key = os.getenv("SESSION_SECRET_KEY")
if not secret_key:
    raise ValueError("SESSION_SECRET_KEY가 설정되지 않았습니다!")
app.add_middleware(SessionMiddleware, secret_key=secret_key, same_site="none", https_only=True)

anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    raise ValueError("ANTHROPIC_API_KEY가 .env 파일에 없습니다.")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://shoppingmall-ui.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from database import init_db, SessionLocal, DiagnoseLog
from model.risk_model import RiskPredictor
from backend.validation.consistency_simulator import load_rules, evaluate_sql

predictor = RiskPredictor()

RULES_PATH = BASE_DIR / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)
try:
    rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in RULES]
    RULES_STR = json.dumps(rules_data, ensure_ascii=False)
except Exception as e:
    with open(RULES_PATH, 'r', encoding='utf-8') as f:
        RULES_STR = f.read()

class QueryRequest(BaseModel):
    sql: str

class SessionRequest(BaseModel):
    query_sql: str
    results: list

# ─── JWT로 유저 확인 ───────────────────────────────────────────
def get_user_id(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    print(f"[AUTH] header: '{auth[:60]}'")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # PyJWT 버전에 따라 decode 방식이 다를 수 있어서 둘 다 시도
        for verify in [True, False]:
            try:
                payload = jwt.decode(
                    token,
                    secret_key,
                    algorithms=["HS256"],
                    options={"verify_exp": verify}
                )
                email = payload.get("email")
                if email:
                    print(f"[AUTH] JWT OK → {email}")
                    return email
            except Exception as e:
                print(f"[AUTH] JWT decode error (verify={verify}): {e}")
    anon_id = request.session.get('anon_id')
    if not anon_id:
        anon_id = f"anon_{uuid.uuid4().hex[:12]}"
        request.session['anon_id'] = anon_id
    print(f"[AUTH] fallback anon → {anon_id}")
    return anon_id

def adjust_score_by_level(score: int, level: str) -> int:
    if level == "HIGH":
        return max(score, 70)
    elif level == "MEDIUM":
        return max(score, 40)
    else:
        return max(score, 20)

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── 로그인 관련 ───────────────────────────────────────────────
@app.get("/login")
async def login(request: Request):
    redirect_uri = "https://shoppingmall-db-migration-analysis.onrender.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    email = user_info['email']

    # JWT 발급
    jwt_token = jwt.encode(
        {"email": email, "exp": datetime.utcnow() + timedelta(days=7)},
        secret_key,
        algorithm="HS256"
    )

    return RedirectResponse(
        url=f"https://shoppingmall-ui.onrender.com?token={jwt_token}"
    )

# ─── DB 관련 ───────────────────────────────────────────────────
@app.get("/db-test")
async def test_db():
    try:
        db = SessionLocal()
        test_log = DiagnoseLog(
            user_email="test@gmail.com",
            query_sql="SELECT * FROM oracle_table;",
            ai_response={"reason": "테스트 데이터입니다.", "recommended_ddl": "CREATE TABLE mysql_table (id INT);", "estimated_improvement": "50%"}
        )
        db.add(test_log)
        db.commit()
        saved_data = db.query(DiagnoseLog).filter(DiagnoseLog.user_email == "test@gmail.com").first()
        db.close()
        return {"message": "DB 연결 및 데이터 저장 성공!", "saved_id": saved_data.id, "saved_email": saved_data.user_email}
    except Exception as e:
        return {"error": str(e)}

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}

@app.delete("/history/{log_id}")
async def delete_history(log_id: str, request: Request):
    user_email = get_user_id(request)
    db = SessionLocal()
    try:
        log = db.query(DiagnoseLog).filter(
            DiagnoseLog.id == log_id,
            DiagnoseLog.user_email == user_email
        ).first()
        if not log:
            return {"ok": False}
        db.delete(log)
        db.commit()
        return {"ok": True}
    finally:
        db.close()

@app.get("/history")
async def get_history(request: Request, limit: int = 20, offset: int = 0):
    user_email = get_user_id(request)
    db = SessionLocal()
    history = db.query(DiagnoseLog)\
                .filter(DiagnoseLog.user_email == user_email)\
                .order_by(desc(DiagnoseLog.created_at))\
                .offset(offset)\
                .limit(limit)\
                .all()
    db.close()
    return history

@app.get("/db-check")
def db_check():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}

@app.get("/me")
async def me(request: Request):
    user_id = get_user_id(request)
    email = user_id if "@" in user_id else None
    return {"email": email}

# ─── AI 진단 관련 ──────────────────────────────────────────────
@app.post("/diagnose")
async def diagnose(req: QueryRequest, request: Request):
    user_email = get_user_id(request)

    sim_result = evaluate_sql(req.sql, RULES)
    matched_ids = list(set(
        p["id"] for detail in sim_result["details"]
        for p in detail["matched_patterns"]
    ))
    max_severity = sim_result["summary"]["max_severity"]

    risk_analysis = predictor.evaluate_risk_score(sim_result)
    risk_score = risk_analysis["risk_score"]
    risk_score = adjust_score_by_level(risk_score, max_severity)
    risk_level = risk_analysis["risk_level"]

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
            base_ms = 100
            improvement_rate = 0.8 if pattern["severity"] == "HIGH" else 0.4
            performance_data.append({
                "pattern": pattern["id"],
                "label": pattern["name"],
                "before": base_ms,
                "after": int(base_ms * (1 - improvement_rate)),
                "improvement": improvement_rate * 100
            })

    risk_score_data = []
    for rule in RULES:
        if rule.id in matched_ids:
            current_score = (80 if max_severity == "HIGH" else 50) if risk_score < 20 else risk_score
        else:
            current_score = 10
        risk_score_data.append({"id": rule.id, "name": rule.name, "score": current_score})

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_context}]
        )
        raw_text = message.content[0].text
        ai_json = json.loads(re.search(r'(\{.*\})', raw_text, re.DOTALL).group(1))

        final_result = {
            "rule_id": ai_json.get("rule_id", matched_ids[0] if matched_ids else "P00"),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "matched_pattern_ids": matched_ids,
            "reason": ai_json["reason"],
            "recommended_ddl": ai_json["recommended_ddl"],
            "estimated_improvement": ai_json["estimated_improvement"],
            "simulator_detail": sim_result["details"],
            "performance_data": performance_data,
            "risk_score_data": risk_score_data
        }
        return final_result

    except Exception as e:
        return {"error": str(e)}

@app.post("/session")
async def save_session(body: SessionRequest, request: Request):
    user_email = get_user_id(request)
    print(f"[SESSION] user_email: {user_email}")
    db = SessionLocal()
    try:
        new_log = DiagnoseLog(
            user_email=user_email,
            query_sql=body.query_sql,
            ai_response=body.results
        )
        db.add(new_log)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
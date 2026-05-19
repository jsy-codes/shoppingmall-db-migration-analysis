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

from sqlalchemy import text, desc

# env_path = Path(__file__).parent.parent / ".env"
load_dotenv()

app = FastAPI()

secret_key = os.getenv("SESSION_SECRET_KEY")
if not secret_key:
    raise ValueError("SESSION_SECRET_KEY가 설정되지 않았습니다!")
app.add_middleware(SessionMiddleware, secret_key=secret_key, same_site="lax", https_only=False) # local : https_only=False

anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    raise ValueError("ANTHROPIC_API_KEY가 .env 파일에 없습니다.")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
# http://localhost:5173 , http://localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
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

from database import init_db, SessionLocal, DiagnoseLog, PredictionLog

from backend.validation.consistency_simulator import load_rules, evaluate_sql

# risk_model.py 안의 RiskPredictor 클래스 객체 생성
from model.risk_model import RiskPredictor
predictor = RiskPredictor()

RULES_PATH = BASE_DIR / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)
# try:
#     rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in RULES]
#     RULES_STR = json.dumps(rules_data, ensure_ascii=False)
# except Exception as e:
#     with open(RULES_PATH, 'r', encoding='utf-8') as f:
#         RULES_STR = f.read()

rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in RULES]
RULES_STR = json.dumps(rules_data, ensure_ascii=False) 

class QueryRequest(BaseModel):
    sql: str

class SessionRequest(BaseModel):
    query_sql: str
    results: list

# ─── JWT로 유저 확인 ───────────────────────────────────────────
def get_user_id(request: Request) -> str:
    # 1. JWT 토큰 확인 (로그인 유저)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            email = payload.get("email")
            if email:
                print(f"[AUTH] JWT OK → {email}")
                return email
        except Exception as e:
            print(f"[AUTH] JWT error: {e}")

    # 2. 비로그인: 프론트 localStorage의 anon_id 사용
    anon_id = request.headers.get("X-Anon-Id")
    if anon_id:
        print(f"[AUTH] anon → {anon_id}")
        return anon_id

    # 3. 아무것도 없으면 임시 anon (히스토리 저장 안 됨)
    fallback = f"anon_{uuid.uuid4().hex[:12]}"
    print(f"[AUTH] fallback → {fallback}")
    return fallback



# ─── 로그인 관련 ───────────────────────────────────────────────
@app.get("/login")
async def login(request: Request):
    redirect_uri = "http://localhost:8000/auth/callback"
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
        url=f"http://localhost:5173?token={jwt_token}"
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}

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

@app.get("/me")
async def me(request: Request):
    user_id = get_user_id(request)
    email = user_id if "@" in user_id else None
    return {"email": email}

# ─── DB 관련 ───────────────────────────────────────────────────
init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

@app.get("/logs")
async def get_logs():

    db = SessionLocal()

    try:
        # 일단 간단하게 불러오는 형식으로 구현함
        logs = db.query(PredictionLog)\
            .order_by(PredictionLog.created_at.desc())\
            .limit(100)\
            .all()

        return [
            {
                "pattern_id": log.pattern_id,
                "pattern_name": log.pattern_name,
                "risk": log.risk,
                "predicted_score": log.predicted_score,
                "before_ms": log.before_ms,
                "after_ms": log.after_ms,
                "error_rate": log.error_rate,
                "created_at": log.created_at
            }
            for log in logs
        ]

    finally:
        db.close()

#@app.post("/stats") 3주차 까지
#async def ():

# ─── AI 진단 관련 ──────────────────────────────────────────────
@app.post("/diagnose")
async def diagnose(req: QueryRequest, request: Request):
    #user_email = get_user_id(request)

    # consistency_simulator가 탐지한 패턴 결과
    sim_result = evaluate_sql(req.sql, RULES)

    pattern_map = {}
    for detail in sim_result["details"]:
        for pattern in detail["matched_patterns"]:
            pattern_map[pattern["id"]] = pattern

    matched_ids = list(pattern_map.keys())
    # matched_ids = list(set(
    #     p["id"] for detail in sim_result["details"]
    #     for p in detail["matched_patterns"]
    # ))
    
    max_severity = sim_result["summary"]["max_severity"]

    # matched_rules = [
    #     r for r in RULES
    #     if r.id in matched_ids
    # ]
    matched_rules = [
        r for r in RULES
        if r.id in pattern_map
    ]
    RULES_STR = "\n".join([
        f"{r.id} | {r.name} | {r.description}"
        for r in matched_rules
    ])

    main_pattern_id = matched_ids[0] if matched_ids else "P00"
    
    try:
        input_patterns = []
        for pid in matched_ids:
            if pid in pattern_map:
                p_info = pattern_map[pid]
                input_patterns.append({
                    "pattern_id": pid,
                    "name": p_info.get("name", ""),
                    "severity": p_info.get("severity", "LOW"),
                    "failure_type": p_info.get("failure_type", "COMPATIBILITY")
                })
        
        risk_analysis = predictor.evaluate_risk_score(input_patterns)
        
        risk_score = risk_analysis.get("risk_score", 15)
        risk_level = risk_analysis.get("risk_level", "LOW")
        
    except Exception as e:
        print(f"Risk model error: {e}")
        risk_analysis = {"contributions": []}
        risk_score = 15
        risk_level = "LOW"
        risk_analysis["contributions"] = [{"pattern_id": "P05", "applied_score": 48}]
    

    # EXPLAIN 분석 결과 (현재는 placeholder)
    explain_signal = {
        "full_scan_ratio": 0.75,
        "no_index_flag": 1,
        "rows_ratio": 3.2
    }
    
    # system_prompt = f"""
    # 당신은 Oracle에서 MySQL로의 이관 전문가입니다. 
    # 제공된 [이관 규칙 가이드라인]를 바탕으로 [사전 분석 결과]에 명시된 패턴을 중점적으로 사용자의 SQL을 분석하여 최적의 솔루션을 제공하세요.

    # [이관 규칙 가이드라인]
    # {RULES_STR}
    
    # [분석 및 생성 원칙]
    # 1. 스크립트 보존: 사용자가 입력한 모든 SQL 문장(INSERT 등)을 생략 없이 전체 보존하여 변환하세요.
    # 2. 기술적 차이 명시: `reason` 항목에는 "Oracle은 [A] 방식을 쓰지만, MySQL은 [B] 방식으로 동작하므로 [C] 문제가 발생함"과 같이 아키텍처적 차이를 구체적으로 설명하세요.
    # 3. 실행 즉시성: `recommended_ddl`에 제공되는 코드는 사용자가 복사하여 MySQL Workbench에서 즉시 실행했을 때, 테이블 생성부터 데이터 삽입, 조회까지 에러 없이 한 번에 성공해야 합니다.
    # 4. 대표 규칙 선정: [사전 분석 결과]의 `matched_ids` 중 가장 위험도가 높거나(HIGH > MEDIUM > LOW) 핵심적인 패턴 ID 하나를 선택하여 `rule_id`에 할당하세요.

    # [응답 지침]
    # 1. 언어: 반드시 한국어로 응답할 것.
    # 2. 형식: JSON 외의 서문이나 맺음말 등 어떠한 텍스트도 출력하지 말 것.
    # 3. 성능 개선: `estimated_improvement`에는 예상되는 실행 시간 단축이나 자원 소모 감소량을 수치(%)로 포함하세요.
    
    # 반드시 아래 JSON 형식으로만 응답하세요:
    # {{
    #     "reason": "상세 원인 설명",
    #     "recommended_ddl": "MySQL용 전체 수정 스크립트",
    #     "estimated_improvement": "예상 성능 향상치(%)와 근거",
    #     "rule_id": "가장 핵심적인 패턴 ID (예: P03)"
    # }}
    # """

    system_prompt = f"""
    당신은 Oracle→MySQL 이관 전문가입니다.

    [탐지 규칙]
    {RULES_STR}

    [EXPLAIN]
    full_scan={explain_signal['full_scan_ratio']}
    no_index={explain_signal['no_index_flag']}
    rows_ratio={explain_signal['rows_ratio']}

    [지침]
    - 입력 SQL 전체 유지
    - MySQL 호환 형태로 변환
    - Oracle/MySQL 차이를 기술적으로 설명
    - recommended_ddl은 즉시 실행 가능해야 함
    - matched_ids 중 핵심 패턴 하나를 rule_id로 선택
    - 반드시 한국어 JSON만 출력

    응답 형식:
    {{
        "reason": "상세 원인 설명",
        "recommended_ddl": "MySQL용 전체 수정 스크립트",
        "estimated_improvement": "예상 성능 향상치(%)와 근거",
        "rule_id": "가장 핵심적인 패턴 ID (예: P03)"
    }}
    """

    #위 분석 결과를 참고하여 상세 설명과 수정된 DDL을 작성하세요.
    user_context = f"""
    [사전 분석 결과]
    - 감지된 패턴 ID: {matched_ids}
    - 최고 위험 등급: {max_severity}

    [대상 SQL]
    {req.sql}
    """
    
    performance_data = []
    db_perf = SessionLocal()
    try:
        for pattern_id, pattern in pattern_map.items():

            logs = db_perf.query(PredictionLog).filter(
                PredictionLog.pattern_id == pattern_id
            ).all()

            valid_logs = [
                log for log in logs
                if log.before_ms is not None and log.after_ms is not None
            ]

            # 과거 데이터가 있으면 평균 사용
            if valid_logs:
                avg_before = sum(log.before_ms for log in valid_logs) / len(valid_logs)
                avg_after = sum(log.after_ms for log in valid_logs) / len(valid_logs)
            # 없으면 fallback
            else:
                avg_before = 100.0
                if pattern["severity"] == "HIGH":
                    avg_after = 20.0
                elif pattern["severity"] == "MEDIUM":
                    avg_after = 50.0
                else:
                    avg_after = 70.0

            improvement = (
                (avg_before - avg_after) / avg_before
            ) * 100

            performance_data.append({
                "pattern": pattern_id,
                "label": pattern["name"],
                "before": round(avg_before, 1),
                "after": round(avg_after, 1),
                "improvement": round(improvement, 1)
            })
    finally:
        db_perf.close()

    #
    risk_score_data = []
    contrib_map = {}
    for c in risk_analysis.get("contributions", []):
        pid = c.get("pattern_id", "")
        score_val = c.get("applied_score", c.get("bonus", 0))
        try:
            contrib_map[pid] = round(float(score_val))
        except:
            contrib_map[pid] = 0
    for rule in RULES:
        current_score = contrib_map.get(rule.id, 0)

        risk_score_data.append({
            "id": rule.id,
            "name": rule.name,
            "score": current_score
        })
    
    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_context}]
        )

        raw_text = message.content[0].text
        
        match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if not match:
            return {"error": "Claude JSON parsing failed"}
        ai_json = json.loads(match.group(1))
        #ai_json = json.loads(re.search(r'(\{.*\})', raw_text, re.DOTALL).group(1))

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
            "risk_score_data": risk_score_data,
            "explain_signal": explain_signal
        }

        # 토큰 사용량 확인
        usage = message.usage
        print(f"DEBUG: [TOKEN USAGE] Input: {usage.input_tokens}, Output: {usage.output_tokens}")

        # PredictionLog DB 저장부분
        db_log = SessionLocal()
        try:
            for perf in performance_data:
                matched_pattern = pattern_map.get(perf["pattern"])

                new_pred = PredictionLog(
                    # 패턴 id (V)
                    pattern_id=perf["pattern"],
                     # 패턴 이름 ( ? )
                    pattern_name=perf["label"],
                     # HIGH / MEDIUM / LOW (V)
                    risk=matched_pattern["severity"] if matched_pattern else "LOW",
                    # just 리스크 점수? (V?)
                    predicted_score=float(risk_score),
                    # 이관 전 실행시간 ( )
                    before_ms=None,
                    #before_ms=float(execution_result["before_ms"]),
                    # 이관(변환) 후 실행시간 ( )
                    after_ms=None,
                    # after_ms=float(execution_result["after_ms"]),
                    # 오차율 ( )
                    error_rate=0.0,
                    # 기록 시각 (V)
                    created_at=datetime.now()
                )
                db_log.add(new_pred)
            db_log.commit()
            print(f"DEBUG: PredictionLog 저장 완료 ({final_result['rule_id']})")
        except Exception as db_err:
            db_log.rollback()
            print(f"DEBUG: PredictionLog 저장 중 에러 -> {db_err}")
        finally:
            db_log.close()

        return final_result
    except Exception as e:
        return {"error": str(e)}
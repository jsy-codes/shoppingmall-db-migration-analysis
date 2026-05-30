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

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:   
    sys.path.append(str(BASE_DIR))

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

class QueryRequest(BaseModel):
    sql: str

class SessionRequest(BaseModel):
    query_sql: str
    results: list

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

# JWT로 유저 확인
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
from database import init_db, SessionLocal, DiagnoseLog, PredictionLog
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

#@app.post("/stats") 3주차 까지?
#async def ():

# ─── consistency_simulator.py ───────────────────────────────────────────────────
from backend.validation.consistency_simulator import load_rules, evaluate_sql

RULES_PATH = BASE_DIR / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)

rules_data = [r.__dict__ if hasattr(r, '__dict__') else r for r in RULES]
RULES_STR = json.dumps(rules_data, ensure_ascii=False) 

# ─── risk_model.py ───────────────────────────────────────────────────
from model.risk_model import RiskPredictor
predictor = RiskPredictor()

# ─── experiments.py ───────────────────────────────────────────────────
from model.experiments import DBRunner

def compare_sql_time(original_sql: str, converted_sql: str):
    db = DBRunner()

    try:
        before_ms = db.measure_ms(original_sql)
        after_ms = db.measure_ms(converted_sql)

        improvement_rate = None

        if before_ms > 0 and after_ms >= 0:
            improvement_rate = round(
                (before_ms - after_ms) / before_ms * 100,
                2
            )

        return {
            "original_sql_ms": before_ms,
            "converted_sql_ms": after_ms,
            "improvement_rate": improvement_rate,
        }

    finally:
        db.close()

# ─── explain_parser.py ───────────────────────────────────────────────────
# MySQL 8.0 사용하는 가정시 사용 가능
from model.explain_parser import parse_explain_json
def get_explain_signal_from_mysql(sql: str) -> dict:
    db = DBRunner()

    try:
        explain_json = db.get_explain_json(sql)
        if not explain_json:
            print(f"[EXPLAIN LOG] DB 결과가 비어있습니다. 입력된 SQL에 오타가 있거나 테이블이 없는 것 같습니다 -> SQL: {sql[:50]}...")
            return {
                "full_scan_ratio": 0.0,
                "no_index_flag": 0,
                "rows_ratio": 1.0
            }
        
        parsed = parse_explain_json(explain_json)
    
        explain_signal = {
            "full_scan_ratio": parsed.get("full_scan_ratio", 0.0),
            "no_index_flag": 1 if parsed.get("no_index_flag", False) else 0,
            "rows_ratio": parsed.get("rows_ratio", 1.0)
        }
        return explain_signal
    
    # 현재 SQLite 환경이거나 문법이 맞지 않아 에러(Exception)가 발생하면 이 블록으로 들어옵니다.
    except Exception as e:
        print(f"[EXPLAIN LOG] 현재 환경(SQLite 등) 문제로 고정된 시뮬레이션용 가상 값을 반환합니다. (에러내용: {e})")
        explain_signal = {
            "full_scan_ratio": 0.0,
            "no_index_flag": 0,
            "rows_ratio": 1.0
        }
        return explain_signal
    
    finally:
        db.close()


# ─── AI 진단 관련 ──────────────────────────────────────────────
@app.post("/diagnose")
async def diagnose(req: QueryRequest, request: Request):
    # consistency_simulator가 탐지한 패턴 결과
    sim_result = evaluate_sql(req.sql, RULES)

    pattern_map = {}
    for detail in sim_result["details"]:
        for pattern in detail["matched_patterns"]:
            pattern_map[pattern["id"]] = pattern

    matched_ids = list(pattern_map.keys())
    
    max_severity = sim_result["summary"]["max_severity"]

    matched_rules = [
        r for r in RULES
        if r.id in pattern_map
    ]
    RULES_STR = "\n".join([
        f"{r.id} | {r.name} | {r.description}"
        for r in matched_rules
    ])

    risk_analysis = predictor.evaluate_risk_score(sim_result)
    risk_score = risk_analysis["risk_score"]
    risk_level = risk_analysis["risk_level"]

    # [EXPLAIN]
    # full_scan={explain_signal['full_scan_ratio']}
    # no_index={explain_signal['no_index_flag']}
    # rows_ratio={explain_signal['rows_ratio']}

    system_prompt = f"""
    당신은 Oracle→MySQL 이관 전문가입니다.

    [탐지 규칙]
    {RULES_STR}

    [지침]
    - 입력 SQL 전체 유지
    - MySQL 호환 형태로 변환
    - Oracle/MySQL 차이를 기술적으로 설명
    - recommended_ddl은 즉시 실행 가능해야 함
    - "converted_sql"에는 반드시 실행 가능한 SELECT SQL만 작성
    - matched_ids 중 핵심 패턴 하나를 rule_id로 선택
    - JSON 외 텍스트 작성 금지
    - 반드시 한국어 JSON만 출력

    응답 형식:
    {{
        "reason": "상세 원인 설명",
        "recommended_ddl": "MySQL용 전체 수정 스크립트",
        "converted_sql": "변환된 MySQL SELECT SQL만 작성",
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

    risk_score_data = []
    contrib_map = {
        c["pattern_id"]: round(c["applied_score"])
        for c in risk_analysis["contributions"]
    }
    for rule in RULES:
        current_score = contrib_map.get(rule.id, 0)

        risk_score_data.append({
            "id": rule.id,
            "name": rule.name,
            "score": current_score
        })
    
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_context}]
        )

        raw_text = message.content[0].text
        
        match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if not match:
            return {"error": "Claude JSON parsing failed"}
        ai_json = json.loads(match.group(1))

        # 실행시간 측정
        print("DEBUG: [EXPERIMENT] 원본 SQL 및 변환 DDL 실행 시간 측정 시작...")
        try:
            execution_result = compare_sql_time(
                req.sql,
                ai_json.get("converted_sql", "")
            )
        except Exception as e:
            print(f"[EXPERIMENT ERROR] 실행시간 측정 실패: {e}")

            execution_result = {
                "original_sql_ms": None,
                "converted_sql_ms": None,
                "improvement_rate": None,
            }
        print(f"DEBUG: [EXPERIMENT RESULT] -> {execution_result}")

        # EXPLAIN 분석 결과
        try:
            explain_signal = get_explain_signal_from_mysql(
                ai_json.get("converted_sql", "")
            )
        except Exception as e:
            print(f"[EXPERIMENT ERROR] EXPLAIN 분석 실패: {e}")
            explain_signal = {
                "full_scan_ratio": 0.0,
                "no_index_flag": 0,
                "rows_ratio": 1.0
            }

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
                    #before_ms=None,
                    before_ms=float(execution_result["original_sql_ms"]),
                    # 이관(변환) 후 실행시간 ( )
                    #after_ms=None,
                    after_ms=float(execution_result["converted_sql_ms"]),
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
    

#     # ── app.py 에 추가할 consistency 관련 코드 ────────────────────
# # 위치: RULES = load_rules(RULES_PATH) 바로 아래에 붙여넣기

# # consistency_grade 맵 사전 로딩 (pattern_rules.json에서 읽음)
# CONSISTENCY_MAP: dict[str, dict] = {
#     r["id"]: {
#         "grade": r.get("consistency_grade", "VERIFY"),
#         "note":  r.get("consistency_note", ""),
#     }
#     for r in rules_data  # rules_data는 기존에 있는 변수 그대로 사용
# }

# GRADE_LABEL = {
#     "AUTO":   "🟢 AUTO — 자동 변환, 결과 동일 보장",
#     "VERIFY": "🟡 VERIFY — 변환 후 결과 검증 필요",
#     "MANUAL": "🔴 MANUAL — 수동 재작성 필요",
# }

# # ── /diagnose 엔드포인트 final_result 딕셔너리에 아래 블록 추가 ──
# # final_result = { ... } 안에 "consistency" 키를 추가하면 됨:
# #
# #   "consistency": build_consistency(matched_ids),
# #
# # 아래 함수를 @app.post("/diagnose") 위에 정의해두세요.

# def build_consistency(matched_ids: list[str]) -> dict:
#     """
#     탐지된 패턴 ID 목록으로 정합성 등급 및 조치 가이드를 생성.
#     가장 엄격한 등급(MANUAL > VERIFY > AUTO)을 대표 등급으로 사용.
#     """
#     RANK = {"AUTO": 1, "VERIFY": 2, "MANUAL": 3}

#     details = []
#     worst_grade = "AUTO"

#     for pid in matched_ids:
#         info  = CONSISTENCY_MAP.get(pid, {"grade": "VERIFY", "note": ""})
#         grade = info["grade"]
#         note  = info["note"]

#         details.append({
#             "pattern_id":    pid,
#             "grade":         grade,
#             "grade_label":   GRADE_LABEL.get(grade, grade),
#             "note":          note,
#         })

#         if RANK.get(grade, 2) > RANK.get(worst_grade, 1):
#             worst_grade = grade

#     action_guide = {
#         "AUTO":   "변환 스크립트를 자동 적용할 수 있습니다. 별도 검증 불필요.",
#         "VERIFY": "변환 후 SELECT 결과를 원본과 비교하여 row 수·값 일치 여부를 확인하세요.",
#         "MANUAL": "자동 변환이 불가능합니다. DBA 또는 개발자가 직접 재작성해야 합니다.",
#     }

#     return {
#         "overall_grade":  worst_grade,
#         "grade_label":    GRADE_LABEL.get(worst_grade, worst_grade),
#         "action":         action_guide.get(worst_grade, ""),
#         "pattern_detail": details,
#     }


# # ── 실제 final_result 수정 예시 (기존 코드에서 final_result 딕셔너리를 찾아 아래처럼 수정) ──
# #
# # final_result = {
# #     "rule_id": ...,
# #     "risk_level": ...,
# #     "risk_score": ...,
# #     "matched_pattern_ids": matched_ids,
# #     "reason": ...,
# #     "recommended_ddl": ...,
# #     "estimated_improvement": ...,
# #     "simulator_detail": ...,
# #     "performance_data": ...,
# #     "risk_score_data": ...,
# #     "explain_signal": ...,
# #     "consistency": build_consistency(matched_ids),   # ← 이 줄만 추가
# # }
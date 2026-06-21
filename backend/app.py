from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Any
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

app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    same_site="lax",
    https_only=False,  # local : https_only=False
)

anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    raise ValueError("ANTHROPIC_API_KEY가 .env 파일에 없습니다.")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://shoppingmall-ui.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


class QueryRequest(BaseModel):
    sql: str


class SessionRequest(BaseModel):
    query_sql: str
    results: list


# ─── 로그인 관련 ───────────────────────────────────────────────
@app.get("/login")
async def login(request: Request):
    redirect_uri = "https://shoppingmall-ui.onrender.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")
    email = user_info["email"]

    jwt_token = jwt.encode(
        {"email": email, "exp": datetime.utcnow() + timedelta(days=7)},
        secret_key,
        algorithm="HS256",
    )

    return RedirectResponse(url=f"https://shoppingmall-ui.onrender.com?token={jwt_token}")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


def get_user_id(request: Request) -> str:
    """JWT 또는 anon_id 기반 사용자 식별."""
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

    anon_id = request.headers.get("X-Anon-Id")
    if anon_id:
        print(f"[AUTH] anon → {anon_id}")
        return anon_id

    fallback = f"anon_{uuid.uuid4().hex[:12]}"
    print(f"[AUTH] fallback → {fallback}")
    return fallback


# ─── DB 관련 ───────────────────────────────────────────────────
from database import init_db, SessionLocal, DiagnoseLog, PredictionLog

init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/session")
async def save_session(body: SessionRequest, request: Request):
    user_email = get_user_id(request)
    print(f"[SESSION] user_email: {user_email}")

    db = SessionLocal()
    try:
        new_log = DiagnoseLog(
            user_email=user_email,
            query_sql=body.query_sql,
            ai_response=body.results,
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


@app.delete("/history/{log_id}")
async def delete_history(log_id: str, request: Request):
    user_email = get_user_id(request)

    db = SessionLocal()
    try:
        log = (
            db.query(DiagnoseLog)
            .filter(DiagnoseLog.id == log_id, DiagnoseLog.user_email == user_email)
            .first()
        )

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
    history = (
        db.query(DiagnoseLog)
        .filter(DiagnoseLog.user_email == user_email)
        .order_by(desc(DiagnoseLog.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
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
    finally:
        db.close()


@app.get("/logs")
async def get_logs():
    db = SessionLocal()

    try:
        logs = (
            db.query(PredictionLog)
            .order_by(PredictionLog.created_at.desc())
            .limit(100)
            .all()
        )

        return [
            {
                "pattern_id": log.pattern_id,
                "pattern_name": log.pattern_name,
                "risk": log.risk,
                "predicted_score": log.predicted_score,
                "before_ms": log.before_ms,
                "after_ms": log.after_ms,
                "error_rate": log.error_rate,
                "created_at": log.created_at,
            }
            for log in logs
        ]

    finally:
        db.close()


# ─── consistency_simulator.py ───────────────────────────────────
from backend.validation.consistency_simulator import load_rules, evaluate_sql

RULES_PATH = BASE_DIR / "validation" / "pattern_rules.json"
RULES = load_rules(RULES_PATH)

rules_data = [r.__dict__ if hasattr(r, "__dict__") else r for r in RULES]
RULES_JSON_STR = json.dumps(rules_data, ensure_ascii=False)


RULE_BY_ID: dict[str, dict[str, Any]] = {
    r.get("id"): r
    for r in rules_data
    if isinstance(r, dict) and r.get("id")
}

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "MED": 2, "HIGH": 3}

APP_FORCE_MIN_SCORE_BY_PATTERN_ID = {
    "P04": 60,  # NVL: 자동 치환 가능하지만 MySQL에서는 즉시 실행 실패
    "P11": 60,  # DECODE
    "P23": 80,  # SEQUENCE
    "P24": 80,  # LISTAGG
    "P29": 80,  # WM_CONCAT
}


def _normalize_severity(value: Any) -> str:
    raw = str(value or "LOW").strip().upper()
    if raw == "MED":
        return "MEDIUM"
    if raw in {"HIGH", "MEDIUM", "LOW"}:
        return raw
    return "LOW"


def normalize_sim_result_for_risk(sim_result: dict) -> dict:
    """
    consistency_simulator 결과를 risk_model 입력용으로 정규화한다.

    필요한 이유:
    - pattern_rules.json은 등급 키가 risk임
    - simulator 결과는 버전에 따라 severity/risk/risk_level 중 하나만 가질 수 있음
    - 이 정규화가 없으면 HIGH 패턴이 LOW처럼 계산되어 95점 → 35점처럼 떨어질 수 있음
    """
    normalized = json.loads(json.dumps(sim_result, ensure_ascii=False))

    worst = "LOW"

    for detail in normalized.get("details", []):
        for pattern in detail.get("matched_patterns", []):
            pid = pattern.get("id")
            rule = RULE_BY_ID.get(pid, {})

            severity = _normalize_severity(
                pattern.get("severity")
                or pattern.get("risk")
                or pattern.get("risk_level")
                or rule.get("risk")
                or rule.get("severity")
                or "LOW"
            )

            pattern["severity"] = severity
            pattern["risk"] = severity

            if not pattern.get("name") and rule.get("name"):
                pattern["name"] = rule["name"]

            if not pattern.get("failure_type") and rule.get("failure_type"):
                pattern["failure_type"] = rule["failure_type"]

            if not pattern.get("description") and rule.get("description"):
                pattern["description"] = rule["description"]

            if SEVERITY_RANK.get(severity, 1) > SEVERITY_RANK.get(worst, 1):
                worst = severity

    normalized.setdefault("summary", {})
    normalized["summary"]["max_severity"] = worst
    return normalized


# ─── risk_model.py ──────────────────────────────────────────────
from model.risk_model import RiskPredictor

# experiments.py --all --grid-search 결과를 .env로도 덮어쓸 수 있게 구성
BEST_DECAY_RATE = float(os.getenv("BEST_DECAY_RATE", "0.1"))

BEST_SCALE = float(os.getenv("BEST_SCALE", "1.7"))



predictor = RiskPredictor(decay_rate=BEST_DECAY_RATE)


# ─── experiments.py ─────────────────────────────────────────────
from model.experiments import DBRunner


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def predict_improvement_from_risk(risk_score: float, scale: float = BEST_SCALE) -> float:
    """
    Grid Search 보정값 기반 예상 개선율.
    Claude의 est_im_percent가 아니라 서버 모델의 기준값으로 사용한다.
    """
    return round(clamp(float(risk_score) * scale), 2)


def calculate_actual_improvement(before_ms: float | None, after_ms: float | None) -> float | None:
    if before_ms is None or after_ms is None:
        return None
    if before_ms <= 0 or after_ms < 0:
        return None

    return round(clamp((before_ms - after_ms) / max(0.001, before_ms) * 100.0), 2)


def calculate_improvement_gap(
    predicted_improvement: float,
    actual_improvement: float | None,
) -> float | None:
    if actual_improvement is None:
        return None

    return round(abs(predicted_improvement - actual_improvement), 2)


def compare_sql_time(original_sql: str, converted_sql: str):
    db = DBRunner()

    try:
        before_ms = db.measure_ms(original_sql)
        after_ms = db.measure_ms(converted_sql)

        improvement_rate = calculate_actual_improvement(before_ms, after_ms)

        return {
            "original_sql_ms": before_ms,
            "converted_sql_ms": after_ms,
            "improvement_rate": improvement_rate,
        }

    finally:
        db.close()


# ─── explain_parser.py ──────────────────────────────────────────
from model.explain_parser import parse_explain_json


def empty_explain_signal(error: str | None = None) -> dict[str, Any]:
    return {
        "full_scan_ratio": 0.0,
        "no_index_flag": 0,
        "rows_ratio": 1.0,
        "filtered_min": 100.0,
        "extra_flags": [],
        "table_count": 0,
        "full_scan_count": 0,
        "explain_error": error,
    }


def get_explain_json_from_mysql(sql: str) -> str:
    """
    MySQL EXPLAIN FORMAT=JSON 원문 반환.
    실패하면 빈 문자열 반환.
    """
    if not sql or not sql.strip():
        return ""

    db = DBRunner()

    try:
        return db.get_explain_json(sql)
    except Exception as e:
        print(f"[EXPLAIN LOG] EXPLAIN 실행 실패: {e}")
        return ""
    finally:
        db.close()


def get_explain_signal_from_mysql(sql: str) -> dict[str, Any]:
    """
    SQL의 EXPLAIN FORMAT=JSON을 실행하고 quant_signal을 반환.
    실패 시 프론트가 깨지지 않도록 기본값 반환.
    """
    explain_json = get_explain_json_from_mysql(sql)

    if not explain_json:
        print(
            "[EXPLAIN LOG] DB 결과가 비어있습니다. "
            f"입력 SQL에 오타가 있거나 테이블이 없을 수 있습니다 -> SQL: {sql[:80]}..."
        )
        return empty_explain_signal("EXPLAIN_EMPTY_OR_FAILED")

    parsed = parse_explain_json(explain_json)

    if not parsed:
        return empty_explain_signal("PARSE_EMPTY_OR_FAILED")

    return {
        "full_scan_ratio": parsed.get("full_scan_ratio", 0.0),
        "no_index_flag": 1 if parsed.get("no_index_flag", False) else 0,
        "rows_ratio": parsed.get("rows_ratio", 1.0),
        "filtered_min": parsed.get("filtered_min", 100.0),
        "extra_flags": parsed.get("extra_flags", []),
        "table_count": parsed.get("table_count", 0),
        "full_scan_count": parsed.get("full_scan_count", 0),
        "explain_error": None,
    }


def build_explain_prompt_block(
    before_signal: dict[str, Any],
    model_predicted_improvement: float,
) -> str:
    """
    Claude system_prompt에 넣을 before EXPLAIN + 모델 예측 기준.
    after SQL은 Claude가 converted_sql을 만든 뒤에야 알 수 있으므로
    최종 응답에 별도로 포함한다.
    """
    return f"""
[EXPLAIN 실행 계획 신호 - before SQL]
full_scan_ratio={before_signal.get("full_scan_ratio", 0.0)}
no_index_flag={before_signal.get("no_index_flag", 0)}
rows_ratio={before_signal.get("rows_ratio", 1.0)}
filtered_min={before_signal.get("filtered_min", 100.0)}
table_count={before_signal.get("table_count", 0)}
full_scan_count={before_signal.get("full_scan_count", 0)}
extra_flags={before_signal.get("extra_flags", [])}

[모델 기반 예상 개선율]
model_predicted_improvement={model_predicted_improvement}%

est_im_percent 산출 기준:
- est_im_percent는 위 model_predicted_improvement 값을 우선 사용한다.
- full_scan_ratio=1.0 + rows_ratio>10000이면 성능 개선 가능성이 높다고 설명한다.
- full_scan_ratio=1.0 + rows_ratio<1000이면 개선 가능성이 있으나 데이터 규모가 작을 수 있다고 설명한다.
- full_scan_ratio=0이면 성능 개선보다는 호환성/정합성 개선 중심으로 설명한다.
- 숫자를 임의로 크게 바꾸지 말고 model_predicted_improvement와 크게 벗어나지 않게 한다.
""".strip()


def build_performance_fallback(pattern: dict[str, Any], risk_score: float) -> tuple[float, float, float]:
    """
    과거 PredictionLog가 없을 때 사용하는 fallback.
    기존 HIGH/MEDIUM/LOW 하드코딩 대신 risk_score * BEST_SCALE을 사용.
    """
    avg_before = 100.0
    predicted_improvement = predict_improvement_from_risk(risk_score)
    avg_after = round(avg_before * (1.0 - predicted_improvement / 100.0), 1)
    return avg_before, avg_after, predicted_improvement


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ─── AI 진단 관련 ──────────────────────────────────────────────
@app.post("/diagnose")
async def diagnose(req: QueryRequest, request: Request):
    # 1. consistency_simulator가 탐지한 패턴 결과
    raw_sim_result = evaluate_sql(req.sql, RULES)
    sim_result = normalize_sim_result_for_risk(raw_sim_result)

    pattern_map: dict[str, dict[str, Any]] = {}
    for detail in sim_result.get("details", []):
        for pattern in detail.get("matched_patterns", []):
            pattern_map[pattern["id"]] = pattern

    matched_ids = list(pattern_map.keys())
    max_severity = sim_result.get("summary", {}).get("max_severity", "LOW")

    matched_rules = [r for r in RULES if r.id in pattern_map]
    matched_rules_str = "\n".join(
        [f"{r.id} | {r.name} | {r.description}" for r in matched_rules]
    )

    # 2. before SQL EXPLAIN을 먼저 계산하고 RiskPredictor에 전달
    before_explain_json = get_explain_json_from_mysql(req.sql)
    before_explain_signal = (
        get_explain_signal_from_mysql(req.sql)
        if before_explain_json
        else empty_explain_signal("EXPLAIN_EMPTY_OR_FAILED")
    )

    risk_analysis = predictor.evaluate_risk_score(
        sim_result,
        explain_json_str=before_explain_json or None,
    )
    risk_score = float(risk_analysis.get("risk_score", 0.0))
    risk_level = risk_analysis.get("risk_level", "LOW")

    # 3. Grid Search scale 기반 모델 예측 개선율
    model_predicted_improvement = predict_improvement_from_risk(risk_score)

    explain_prompt_block = build_explain_prompt_block(
        before_signal=before_explain_signal,
        model_predicted_improvement=model_predicted_improvement,
    )

    system_prompt = f"""
당신은 Oracle→MySQL 이관 전문가입니다.

[탐지 규칙]
{matched_rules_str}

{explain_prompt_block}

[지침]
- 입력 SQL 전체 유지
- MySQL 호환 형태로 변환
- Oracle/MySQL 차이를 기술적으로 설명
- recommended_ddl은 즉시 실행 가능해야 함
- "converted_sql"에는 반드시 실행 가능한 SELECT SQL만 작성
- matched_ids 중 핵심 패턴 하나를 rule_id로 선택
- est_im_percent는 모델 기반 예상 개선율 값을 우선 반영
- JSON 외 텍스트 작성 금지
- 반드시 한국어 JSON만 출력

응답 형식:
{{
    "reason": "상세 원인 설명",
    "recommended_ddl": "MySQL용 전체 수정 스크립트",
    "converted_sql": "변환된 MySQL SELECT SQL만 작성",
    "est_im_percent": "숫자만 반환",
    "estimated_improvement": "예상 성능 향상률(%포함)와 근거",
    "rule_id": "가장 핵심적인 패턴 ID (예: P03)"
}}
"""

    user_context = f"""
[사전 분석 결과]
- 감지된 패턴 ID: {matched_ids}
- 최고 위험 등급: {max_severity}
- 모델 위험 점수: {risk_score}
- 모델 예상 개선율: {model_predicted_improvement}%

[대상 SQL]
{req.sql}
"""

    # 4. 과거 PredictionLog 기반 performance_data 구성
    performance_data = []
    db_perf = SessionLocal()

    try:
        for pattern_id, pattern in pattern_map.items():
            logs = (
                db_perf.query(PredictionLog)
                .filter(PredictionLog.pattern_id == pattern_id)
                .all()
            )

            valid_logs = [
                log
                for log in logs
                if log.before_ms is not None and log.after_ms is not None
            ]

            if valid_logs:
                avg_before = sum(log.before_ms for log in valid_logs) / len(valid_logs)
                avg_after = sum(log.after_ms for log in valid_logs) / len(valid_logs)

                improvement = calculate_actual_improvement(avg_before, avg_after)
                if improvement is None:
                    improvement = model_predicted_improvement
            else:
                avg_before, avg_after, improvement = build_performance_fallback(
                    pattern,
                    risk_score,
                )

            performance_data.append(
                {
                    "pattern": pattern_id,
                    "label": pattern["name"],
                    "before": round(avg_before, 1),
                    "after": round(avg_after, 1),
                    "improvement": round(improvement, 1),
                }
            )

    finally:
        db_perf.close()

    # 5. 위험 점수 차트 데이터
    risk_score_data = []
    contrib_map = {}
    for c in risk_analysis.get("contributions", []):
        pid = c["pattern_id"]
        raw_score = round(c["applied_score"] + c.get("quant_bonus", 0))
        contrib_map[pid] = max(
            raw_score,
            APP_FORCE_MIN_SCORE_BY_PATTERN_ID.get(pid, 0),
        )

    for rule in RULES:
        risk_score_data.append(
            {
                "id": rule.id,
                "name": rule.name,
                "score": contrib_map.get(rule.id, 0),
            }
        )

    try:
        # 6. Claude 호출
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_context}],
        )

        raw_text = message.content[0].text

        match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if not match:
            return {"error": "Claude JSON parsing failed", "raw": raw_text}

        ai_json = json.loads(match.group(1))
        converted_sql = ai_json.get("converted_sql", "")

        # 7. 실행시간 측정
        print("DEBUG: [EXPERIMENT] 원본 SQL 및 변환 SQL 실행 시간 측정 시작...")

        try:
            execution_result = compare_sql_time(req.sql, converted_sql)

            actual_improvement = execution_result.get("improvement_rate")
            improvement_gap = calculate_improvement_gap(
                model_predicted_improvement,
                actual_improvement,
            )

        except Exception as e:
            print(f"[EXPERIMENT ERROR] 실행시간 측정 실패: {e}")

            execution_result = {
                "original_sql_ms": None,
                "converted_sql_ms": None,
                "improvement_rate": None,
            }
            actual_improvement = None
            improvement_gap = None

        print(f"DEBUG: [EXPERIMENT RESULT] -> {execution_result}")

        # 8. after SQL EXPLAIN 분석
        try:
            after_explain_signal = get_explain_signal_from_mysql(converted_sql)
        except Exception as e:
            print(f"[EXPERIMENT ERROR] after EXPLAIN 분석 실패: {e}")
            after_explain_signal = empty_explain_signal("AFTER_EXPLAIN_FAILED")

        # 9. 최종 응답 구성
        final_result = {
            "rule_id": ai_json.get("rule_id", matched_ids[0] if matched_ids else "P00"),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "matched_pattern_ids": matched_ids,
            "reason": ai_json.get("reason", ""),
            "recommended_ddl": ai_json.get("recommended_ddl", ""),
            "converted_sql": converted_sql,

            # Claude 응답값은 남기되, 실제 기준값은 model_predicted_improvement
            "claude_est_im_percent": ai_json.get("est_im_percent"),
            "est_im_percent": model_predicted_improvement,
            "estimated_improvement": ai_json.get(
                "estimated_improvement",
                f"모델 기준 예상 성능 향상률은 약 {model_predicted_improvement}%입니다.",
            ),
            "model_predicted_improvement": model_predicted_improvement,
            "actual_improvement": actual_improvement,
            "improvement_gap": improvement_gap,

            "execution_result": execution_result,
            "simulator_detail": sim_result.get("details", []),
            "performance_data": performance_data,
            "risk_score_data": risk_score_data,

            # 기존 호환 키
            "explain_signal": after_explain_signal,

            # 신규 연결 키
            "quant_signal": {
                "before": before_explain_signal,
                "after": after_explain_signal,
            },
            "risk_analysis": risk_analysis,
            "grid_search_params": {
                "decay": BEST_DECAY_RATE,
                "scale": BEST_SCALE,
            },
        }

        usage = message.usage
        print(
            f"DEBUG: [TOKEN USAGE] Input: {usage.input_tokens}, "
            f"Output: {usage.output_tokens}"
        )

        # 10. PredictionLog 저장
        db_log = SessionLocal()

        try:
            before_ms = safe_float(execution_result.get("original_sql_ms"))
            after_ms = safe_float(execution_result.get("converted_sql_ms"))

            for perf in performance_data:
                matched_pattern = pattern_map.get(perf["pattern"])

                new_pred = PredictionLog(
                    pattern_id=perf["pattern"],
                    pattern_name=perf["label"],
                    risk=matched_pattern.get("severity", "LOW") if matched_pattern else "LOW",
                    predicted_score=float(risk_score),
                    before_ms=before_ms,
                    after_ms=after_ms,
                    error_rate=improvement_gap,
                    created_at=datetime.now(),
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


# ─── consistency 관련 옵션 코드 ───────────────────────────────
# pattern_rules.json에 consistency_grade / consistency_note가 있을 때 사용 가능

CONSISTENCY_MAP: dict[str, dict] = {
    r.get("id"): {
        "grade": r.get("consistency_grade", "VERIFY"),
        "note": r.get("consistency_note", ""),
    }
    for r in rules_data
    if isinstance(r, dict) and r.get("id")
}

GRADE_LABEL = {
    "AUTO": "🟢 AUTO — 자동 변환, 결과 동일 보장",
    "VERIFY": "🟡 VERIFY — 변환 후 결과 검증 필요",
    "MANUAL": "🔴 MANUAL — 수동 재작성 필요",
}


def build_consistency(matched_ids: list[str]) -> dict:
    """
    탐지된 패턴 ID 목록으로 정합성 등급 및 조치 가이드를 생성.
    가장 엄격한 등급(MANUAL > VERIFY > AUTO)을 대표 등급으로 사용.
    """
    rank = {"AUTO": 1, "VERIFY": 2, "MANUAL": 3}

    details = []
    worst_grade = "AUTO"

    for pid in matched_ids:
        info = CONSISTENCY_MAP.get(pid, {"grade": "VERIFY", "note": ""})
        grade = info["grade"]
        note = info["note"]

        details.append(
            {
                "pattern_id": pid,
                "grade": grade,
                "grade_label": GRADE_LABEL.get(grade, grade),
                "note": note,
            }
        )

        if rank.get(grade, 2) > rank.get(worst_grade, 1):
            worst_grade = grade

    action_guide = {
        "AUTO": "변환 스크립트를 자동 적용할 수 있습니다. 별도 검증 불필요.",
        "VERIFY": "변환 후 SELECT 결과를 원본과 비교하여 row 수·값 일치 여부를 확인하세요.",
        "MANUAL": "자동 변환이 불가능합니다. DBA 또는 개발자가 직접 재작성해야 합니다.",
    }

    return {
        "overall_grade": worst_grade,
        "grade_label": GRADE_LABEL.get(worst_grade, worst_grade),
        "action": action_guide.get(worst_grade, ""),
        "pattern_detail": details,
    }

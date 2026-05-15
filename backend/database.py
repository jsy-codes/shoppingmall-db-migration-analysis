from sqlalchemy import Column, String, Text, DateTime, JSON, Float, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
from pathlib import Path
import os

# 📌 DB 파일 위치 (backend/history.db)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "history.db"

# 📌 환경변수 읽기
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# 📌 Render postgres 대응
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg2://"
    )

# 📌 ❗ 핵심: fallback (로컬용 SQLite)
if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# 📌 엔진 생성 (sqlite 대응 포함)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 📌 테이블 정의
class DiagnoseLog(Base):
    __tablename__ = "diagnose_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, index=True)
    query_sql = Column(Text)
    ai_response = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)

class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_id = Column(String, index=True)     # 예: P04
    pattern_name = Column(String)   # 추가예정
    risk = Column(String)           # HIGH / MEDIUM / LOW
    predicted_score = Column(Float)             # 리스크 점수?
    before_ms = Column(Float, nullable=True)    # 이관 전 실행시간
    after_ms = Column(Float, nullable=True)     # 이관(변환) 후 실행시간
    error_rate = Column(Float, nullable=True)   # 오차율
    created_at = Column(DateTime, default=datetime.now) # 기록 시각

# 📌 테이블 생성
def init_db():
    Base.metadata.create_all(bind=engine)
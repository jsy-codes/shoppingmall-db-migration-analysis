from sqlalchemy import Column, String, Text, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
#import os
from pathlib import Path
from datetime import datetime

# 1. 현재 database.py 파일이 있는 위치(backend 폴더)를 찾습니다.
BASE_DIR = Path(__file__).resolve().parent
# 2. backend 폴더 안에 history.db가 위치하도록 절대 경로를 만듭니다.
DB_PATH = BASE_DIR / "history.db"

# DB 연결 설정
#SQLALCHEMY_DATABASE_URL = "sqlite:///./history.db"

# 윈도우 환경에서 경로 인식을 확실하게 하기 위해 as_posix() 사용
# sqlite:/// (슬래시 3개) + 절대경로
import os

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# SQL라이트용 엔진 생성 (create_client가 아니라 create_engine입니다)
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 테이블(모델) 정의
class DiagnoseLog(Base):
    """개별 진단 내역 (한 번의 질문과 답변)"""
    __tablename__ = "diagnose_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, index=True)  # 이제 여기에 직접 이메일을 저장합니다.
    query_sql = Column(Text)    # 사용자가 입력한 오리지널 SQL
    ai_response = Column(JSON)  # AI가 준 결과 JSON 전체
    created_at = Column(DateTime, default=datetime.now)

# 테이블 생성 함수
def init_db():
    Base.metadata.create_all(bind=engine)
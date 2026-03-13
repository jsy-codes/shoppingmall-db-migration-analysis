# shoppingmall-db-migration-analysis
Legacy shopping mall database analysis and performance tuning project
shoppingmall-db-migration-analysis/
├─ backend/           
│   ├─ app.py          # FastAPI 백엔드 메인
│   ├─ models.py       # DB 모델 정의
│   ├─ validation/     # 정성윤: 데이터 정합성 검증, 이관 실패 패턴
│   │   └─ pattern_rules.json
│   └─ utils/          # 유틸리티 함수
├─ frontend/          # 김남규: React + Tailwind 대시보드
│   ├─ src/
│   │   ├─ App.js
│   │   ├─ components/
│   │   └─ pages/
│   └─ public/
├─ model/             # 김채운: 위험도 예측 모델
│   ├─ risk_model.py
│   └─ experiments/
├─ data-generator/    # 이동훈: 더미 데이터 생성 스크립트
│   └─ generate_dummy.py
├─ docs/              # 프로젝트 문서 / ERD / 발표자료
└─ .gitkeep           # 빈 폴더 commit용

# branch 구조
main        최종 배포용(실행 가능 ver)
dev         통합 개발 브랜치
dev/jsy     각자 feature 작업 브랜치 dev아래 만들고, dev PR


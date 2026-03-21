# 기존 마이그레이션 도구의 한계

기존 도구는

- 문법 변환
- 데이터 복사

까지만 지원하며

성능 저하 원인 분석은 개발자의 수동 판단에 의존한다.

문제점

슬로우 쿼리 분석은

EXPLAIN 결과 해석  
인덱스 구조 이해  
DB 엔진 특성 이해  

가 동시에 필요하여 자동화가 어렵다.

해결 방법

LLM 기반 분석기를 이용하여

- 쿼리 패턴 인식
- 실패 패턴 매칭
- 최적화 규칙 적용

을 자동화한다.

# shoppingmall-db-migration-analysis project structure 구조 예시
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
jsy         각자 feature 작업 브랜치 만들고, dev PR  


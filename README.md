# 🛒 레거시 DB 쇼핑몰 마이그레이션 예비 분석 및 성능 튜닝 파이프라인

## 📖 프로젝트 배경 및 개요
기존 데이터베이스 마이그레이션 도구들은 주로 '문법 변환'과 '데이터 복사'까지만 지원하며, 이관 후 발생하는 성능 저하의 원인 분석은 온전히 개발자의 수동 판단에 의존해 왔습니다. 
특히 슬로우 쿼리 분석은 `EXPLAIN` 결과 해석, 인덱스 구조 이해, DB 엔진 특성 파악이 동시에 필요하여 자동화가 매우 어려웠습니다.

본 프로젝트는 이러한 한계를 극복하고자 LLM 기반 분석기와 규칙 기반 시뮬레이터를 결합하여, 쿼리 패턴 인식부터 실패 패턴 매칭, 최적화 규칙 적용(DDL 추천)까지 전 과정을 자동화하는 파이프라인입니다.

## 👥 팀원 및 역할
본 프로젝트는 5인의 모듈화된 협업으로 진행됩니다.
* 이동훈 (PM / Data): 프로젝트 총괄, 10만 건 더미 데이터 적재 및 공통 테스트 쿼리셋(`bad_queries.sql`) 구축
* 정성윤 (Team Leader / Simulator): `pattern_rules.json` 기반 데이터 정합성 검증 및 이관 실패 패턴 매칭 로직 구현
* 이현종 (Backend / AI): FastAPI 기반 백엔드 통합 및 Claude API 프롬프트 엔지니어링 (최적화 규칙 적용 자동화)
* 김채운 (Risk Model): 시스템 위험도 점수(Risk Score, 0~100점) 산출 및 예측 알고리즘 개발
* 김남규 (Frontend): React + Tailwind 기반 진단 결과 시각화(RiskBadge, DdlBlock 등) 대시보드 UI 개발

## 🏗 통합 아키텍처 및 워크플로우
이 시스템은 단순한 AI 호출이 아닌, '규칙 기반 검증'과 'AI의 유연성'이 결합된 하이브리드 파이프라인으로 동작합니다. 

1. 사전 패턴 매칭 (Simulator): 입력된 SQL을 `simulator`에 통과시켜 빠르고 확실하게 안티패턴(P01~P21)을 감지합니다.
2. 위험도 계산 (Risk Model): 시뮬레이터가 반환한 `severity_counts`(위험도별 빈도)를 바탕으로 `risk_model`이 Risk Score를 산출합니다.
3. AI 기반 DDL 및 설명 생성 (Claude API): 감지된 패턴 ID와 최고 위험도 정보를 Claude의 프롬프트 컨텍스트로 주입하여, 해당 SQL의 문제 원인 파악 및 최적화된 MySQL DDL을 자동 생성합니다.
4. 최종 JSON 응답 반환: 위 3가지 모듈의 결과를 하나로 통합하여 프론트엔드 대시보드에 시각화합니다.

## 🗂 프로젝트 폴더 구조
```text
shoppingmall-db-migration-analysis/
├─ .vscode/
│  └─ settings.json
├─ backend/                 # 백엔드 서버 및 검증 파이프라인
│  ├─ app.py                # FastAPI 메인 (시뮬레이터+위험도 모델+AI 통합 지점)
│  └─ validation/           # 정성윤: 정합성 검증 및 실패 패턴 탐지 모듈
│     ├─ type_tests/        # P01~P10 패턴별 단위 테스트 쿼리 및 결과
│     ├─ __init__.py        
│     ├─ consistency_simulator.py # 규칙 기반 안티패턴 탐지 핵심 로직
│     ├─ pattern_rules.json       # 20여 종의 이관 실패 패턴(정규식) 룰셋
│     ├─ pattern_library.md       # 패턴 라이브러리 상세 명세 문서
│     ├─ run_all_tests.py         # 전체 패턴 단위 테스트 일괄 실행 스크립트
│     ├─ simulator_competiton_plan.md # 시뮬레이터 고도화 계획 문서
│     └─ type_test_plan.md        # 테스트 시나리오 계획 문서
├─ data-generator/          # 이동훈: 데이터 및 테스트 셋
│  ├─ bad_queries.sql       # 팀 공통 AI 정확도 검증용 50개 악성 쿼리셋
│  └─ generate_dummy.py     # 성능 테스트용 10만 건 더미 데이터 생성기
├─ docs/                    # 프로젝트 주요 문서
│  ├─ integration_test_scenario.md # 통합 API 테스트 시나리오 10종
│  └─ model.sql
├─ front/                   # 김남규: React + Vite 대시보드 UI
│  ├─ public/               # 정적 애셋 (favicon 등)
│  └─ src/
│     ├─ api/
│     │  └─ diagnose.js     # 백엔드 POST /diagnose API 연동
│     ├─ assets/            # UI 이미지 및 아이콘
│     └─ data/
│        ├─ mock_diagnose_result.json # API 장애 대비 오프라인 데모용 Mock 데이터
│        └─ pattern_rules.json        # 프론트엔드 매핑용 룰셋 사본
├─ model/                   # 김채운: 위험도 예측 모델
│  └─ risk_model.py         # 시뮬레이터 결과를 바탕으로 0~100점 점수 산출
├─ .gitignore
├─ LICENSE
├─ README.md                # 프로젝트 메인 소개서
├─ result.csv               # 데이터 추출 결과물
└─ run.py                   # 프로젝트 전체 실행 스크립트
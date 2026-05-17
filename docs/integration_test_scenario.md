# 🧪 쇼핑몰 DB 마이그레이션 통합 테스트 시나리오 (Top 10)

## 📌 테스트 목적
본 문서는 사용자가 프론트엔드에 암시적 형변환(P01), ROWNUM(P03) 등 대표적인 오라클 악성 쿼리를 입력했을 때, 전체 통합 파이프라인이 정상 작동하는지 검증하기 위한 데모 시연 및 최종 채점표입니다. [cite_start]백엔드의 규칙 기반 시뮬레이터(정성윤)가 위험 패턴과 등급을 감지하고, 위험도 예측 모델(김채운)이 점수를 산출하며, 최종적으로 AI(이현종)가 원인 분석과 함께 최적화된 MySQL DDL을 생성하여 UI(김남규)에 올바르게 표출하는지를 종합적으로 확인합니다 [cite: 3, 31-49].

---

1. [P02] Function on Indexed Column (성능 저하 - HIGH)
상황 설명: 회원 이름 검색 시 `UPPER()` 함수를 사용하여 인덱스를 무효화시킨 상황.
입력 SQL (`bad_queries.sql` Q04):
 
 SELECT id, name FROM MEMBERS WHERE UPPER(name) = 'KIM';
 
 기대 결과 (Expected Output):


-매칭 패턴 ID (Simulator): ["P02"] 


-Risk Level (Simulator): HIGH 


-Risk Score (Risk Model): 40점 이상 (HIGH 가중치 반영) 


-AI 진단/수정 (Claude): 인덱스 컬럼에 함수를 사용하여 Full Scan이 발생함을 지적하고, 생성 컬럼(Generated Column) 기반의 인덱스 추가 DDL 또는 튜닝 쿼리 제시.

2. [P03] ROWNUM Pagination (문법 에러 - HIGH)
상황 설명: MySQL에서 지원하지 않는 오라클 전용 페이징 문법 사용.

입력 SQL (bad_queries.sql Q07):

SELECT * FROM ORDERS WHERE ROWNUM <= 10 ORDER BY created_at DESC;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P03"]

-Risk Level: HIGH

-Risk Score: 40점 이상

-AI 진단/수정: ROWNUM은 MySQL에서 미지원함을 설명하고, LIMIT 10을 활용한 올바른 쿼리로 변환하여 제공.

3. [P01] Implicit Type Cast (성능 저하 - MEDIUM)
상황 설명: 문자열 타입인 id 컬럼을 숫자형으로 검색하여 암시적 형변환 발생.

입력 SQL (bad_queries.sql Q01):

SELECT * FROM MEMBERS WHERE id = 10500;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P01"]

-Risk Level: MEDIUM

-Risk Score: 20점 내외 (MEDIUM 가중치 반영)

-AI 진단/수정: 타입 불일치로 인한 인덱스 무력화를 경고하고, WHERE id = '10500'과 같이 타입을 맞춘 쿼리 제시.

4. [P09] JOIN Without Index (성능 폭발 - HIGH)
상황 설명: 인덱스가 없는 텍스트 컬럼(주소)을 조인 키로 사용하여 대량 풀 스캔 유발.

입력 SQL (bad_queries.sql Q19):

SELECT m.name, o.total_amount FROM MEMBERS m JOIN ORDERS o ON m.address = o.shipping_address;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P09"]

-Risk Level: HIGH

-Risk Score: 40점 이상

-AI 진단/수정: 조인 키에 인덱스가 없어 치명적인 병목이 발생함을 설명하고, 조인 대상 컬럼에 대한 CREATE INDEX 문법 생성.

5. [P14] Oracle Outer Join (+) (문법 에러 - HIGH)
상황 설명: 레거시 오라클의 (+) 아우터 조인 기호를 사용한 문법 에러.

입력 SQL (bad_queries.sql Q31):

SELECT m.name, o.id FROM MEMBERS m, ORDERS o WHERE m.id = o.member_id (+);

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P14"]

-Risk Level: HIGH

-Risk Score: 40점 이상

-AI 진단/수정: (+) 문법 지원 불가를 명시하고, LEFT OUTER JOIN 표준 ANSI SQL 문법으로 재작성하여 반환.

6. [P17] MERGE INTO Statement (문법 에러 - HIGH)
상황 설명: MySQL에서 지원하지 않는 MERGE INTO (Upsert) 구문 사용.

입력 SQL (bad_queries.sql Q37):

MERGE INTO MEMBERS m USING (SELECT 100 AS id, 'NEW' AS status FROM DUAL) d ON (m.id = d.id) 
WHEN MATCHED THEN UPDATE SET status = d.status;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P17"]

-Risk Level: HIGH

-Risk Score: 40점 이상

-AI 진단/수정: MERGE INTO 대신, MySQL 전용 INSERT ... ON DUPLICATE KEY UPDATE 구문으로 완벽히 변환하여 제공.

7. [P11] DECODE Function (문법 에러 - MEDIUM)
상황 설명: 오라클 전용 분기 함수인 DECODE를 사용.

입력 SQL (bad_queries.sql Q25):

SELECT id, DECODE(status, 'PENDING', '대기', 'COMPLETE', '완료', '기타') FROM ORDERS;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P11"]

-Risk Level: MEDIUM

-Risk Score: 20점 내외

-AI 진단/수정: CASE WHEN ... THEN ... END 표준 구문으로 치환하여 응답.

8. [P12] CONNECT BY Hierarchy (문법 에러 - HIGH)
상황 설명: 오라클 전용 계층형 쿼리 문법 사용.

입력 SQL (bad_queries.sql Q27):

SELECT * FROM CATEGORIES CONNECT BY PRIOR id = parent_id;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P12"]

-Risk Level: HIGH

-Risk Score: 40점 이상

-AI 진단/수정: MySQL 8.0 이상에서 지원하는 WITH RECURSIVE (재귀 CTE) 구문으로 구조를 완전히 재작성하여 제공.

9. [P04] NVL Function (문법 에러 - LOW)
상황 설명: 널(Null) 치환 시 MySQL의 IFNULL 대신 오라클의 NVL 사용.

입력 SQL (bad_queries.sql Q09):

SELECT id, NVL(discount_amount, 0) FROM COUPONS;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P04"]

-Risk Level: LOW

-Risk Score: 5점 내외

-AI 진단/수정: 단순 함수 비호환 문제임을 알리고, IFNULL(discount_amount, 0) 또는 COALESCE로 변환.

10. [복합 패턴 감지] P03 + P15 (다중 에러 - HIGH)
상황 설명: 여러 위험 패턴이 하나의 쿼리에 섞여 있는 복합 상황 검증.

입력 SQL (조합 생성):

SELECT * FROM ORDERS WHERE created_at >= SYSDATE - 1 AND ROWNUM <= 5;

기대 결과 (Expected Output):

-매칭 패턴 ID: ["P03", "P15"] (2개 동시 감지)

-Risk Level: HIGH (가장 높은 등급 기준)

-Risk Score: 45점 이상 (HIGH + LOW 합산 반영) 

-AI 진단/수정: ROWNUM은 LIMIT로, SYSDATE는 NOW()로 변환해야 함을 복합적으로 설명하고 통합 수정 쿼리 제시.
import re

class RiskPredictor:
    # 핵심: sim_result 파라미터를 추가해서 시뮬레이터와 독립적으로 노는 문제를 해결
    def evaluate_risk_score(self, query: str, sim_result: dict = None) -> dict:
        total_score = 0
        detected_patterns = []

        # 1. 시뮬레이터 결과 흡수 로직 (점수 30점 정체 해결)
        if sim_result and "details" in sim_result:
            for detail in sim_result.get("details", []):
                for pattern in detail.get("matched_patterns", []):
                    severity = pattern.get("severity", "LOW")
                    pattern_name = pattern.get("name", "Unknown Pattern")
                    
                    # 시뮬레이터가 판별한 레벨에 맞춰 다이나믹하게 점수 누적
                    if severity == "HIGH":
                        total_score += 40
                    elif severity == "MEDIUM":
                        total_score += 20
                    else:
                        total_score += 10
                        
                    detected_patterns.append(f"[{severity}] {pattern_name}")

        # 2. 시뮬레이터 결과가 없거나 점수가 0일 때 방어 로직
        if total_score == 0:
            query_upper = query.upper()
            if re.search(r'\b(UPPER|LOWER|NVL|TO_CHAR|TO_DATE)\s*\(', query_upper):
                total_score += 40
                detected_patterns.append("[HIGH] Function-Based Filter")
            if query_upper.count(' JOIN ') >= 4:
                total_score += 30
                detected_patterns.append("[MEDIUM] Complex Join")
            if re.search(r'=\s*\d+(?!\s*\')', query_upper) and "'" not in query_upper:
                total_score += 35
                detected_patterns.append("[HIGH] Implicit Type Cast")
            if 'ROWNUM' in query_upper:
                total_score += 35
                detected_patterns.append("[MEDIUM] ROWNUM Paging")

        # 3. 점수 상한 및 등급 정리
        total_score = min(total_score, 100) # 최대 100점
        detected_patterns = list(set(detected_patterns)) # 중복 패턴명 제거

        risk_level = "LOW"
        if total_score >= 60:
            risk_level = "HIGH"
        elif total_score >= 30:
            risk_level = "MEDIUM"

        return {
            "query": query,
            "risk_score": total_score,
            "risk_level": risk_level,
            "detected_patterns": detected_patterns
        }
    
    # --- 여기서부터 파일 맨 밑에 추가로 복붙 ---
if __name__ == "__main__":
    predictor = RiskPredictor()
    
    # 가짜 시뮬레이터 결과 (HIGH 1개, MEDIUM 1개 세팅)
    mock_sim_result = {
        "details": [
            {
                "matched_patterns": [
                    {"name": "Test High Pattern", "severity": "HIGH"},
                    {"name": "Test Medium Pattern", "severity": "MEDIUM"}
                ]
            }
        ]
    }
    
    print("\n [테스트 1] 시뮬레이터 결과가 들어왔을 때 (40 + 20 = 60점, HIGH 등급 예상)")
    result1 = predictor.evaluate_risk_score("SELECT * FROM dual", mock_sim_result)
    print(result1)
    
    print("\n [테스트 2] 시뮬레이터 결과 없이 혼자 돌 때 (ROWNUM 감지 -> 35점, MEDIUM 등급 예상)")
    result2 = predictor.evaluate_risk_score("SELECT * FROM orders WHERE ROWNUM <= 10")
    print(result2)
    print("\n")

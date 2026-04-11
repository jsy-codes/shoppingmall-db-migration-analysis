import re

class RiskPredictor:
    # sim_result(시뮬레이터 결과)를 추가 파라미터로 받도록 변경 (기본값 None으로 기존 연동 파괴 방지)
    def evaluate_risk_score(self, query: str, sim_result: dict = None) -> dict:
        total_score = 0
        detected_patterns = []

        # [핵심] 시뮬레이터와 연동된 진짜 평가 로직
        if sim_result and "details" in sim_result:
            for detail in sim_result["details"]:
                for pattern in detail.get("matched_patterns", []):
                    severity = pattern.get("severity", "LOW")
                    pattern_name = pattern.get("name", "Unknown Pattern")
                    
                    # 시뮬레이터가 잡은 등급에 따라 다이나믹하게 점수 부여
                    if severity == "HIGH":
                        total_score += 40
                    elif severity == "MEDIUM":
                        total_score += 20
                    else:
                        total_score += 10
                        
                    detected_patterns.append(f"[{severity}] {pattern_name}")

        # 시뮬레이터 결과가 안 넘어왔을 때를 대비한 비상용 로직
        else:
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

        # 최대 점수 100점 제한
        total_score = min(total_score, 100)

        # 등급 산정
        risk_level = "LOW"
        if total_score >= 60:
            risk_level = "HIGH"
        elif total_score >= 30:
            risk_level = "MEDIUM"

        return {
            "query": query,
            "risk_score": total_score,
            "risk_level": risk_level,
            "detected_patterns": list(set(detected_patterns)) # 중복 패턴 제거
        }

if __name__ == "__main__":
    # 테스트 생략
    pass

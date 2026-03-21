import re

class RiskPredictor:
    def __init__(self):
        # AI 모델과 통합하기 쉽게 점수(수치적 로직)를 딕셔너리로 세팅
        self.risk_metrics = {
            'PATTERN_A_FUNC_INDEX': 30,  # 함수 기반 필터 (Full Scan 위험)
            'PATTERN_B_COMPLEX_JOIN': 40, # 다중 조인 복잡도 (성능 저하 위험)
        }

    def evaluate_risk_score(self, query: str) -> dict:
        query_upper = query.upper()
        total_score = 0
        detected_patterns = []

        # 지표 1: 함수 기반 필터 (UPPER, LOWER 등)
        if re.search(r'\b(UPPER|LOWER|NVL|IFNULL|TO_CHAR|TO_DATE)\s*\(', query_upper):
            total_score += self.risk_metrics['PATTERN_A_FUNC_INDEX']
            detected_patterns.append("Pattern A: Function-Based Filter (Full Scan 위험)")

        # 지표 2: 다중 조인 복잡도 (5-Way 이상 -> JOIN 키워드 4개 이상)
        if query_upper.count(' JOIN ') >= 4:
            total_score += self.risk_metrics['PATTERN_B_COMPLEX_JOIN']
            detected_patterns.append("Pattern B: Complex Join (성능 저하 위험)")

        # 점수 통합 (최대 100점 제한)
        final_score = min(total_score, 100)

        # JSON 형태로 리턴
        return {
            "risk_score": final_score,
            "detected_patterns": detected_patterns
        }

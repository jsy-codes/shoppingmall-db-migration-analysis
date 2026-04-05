import re
import json

class RiskPredictor:
    def __init__(self):
        # 4가지 위험 지표 가중치 정의 (총합 100점)
        self.risk_metrics = {
            'PATTERN_A_FUNC_INDEX': 40,  # 함수 기반 필터 (Function-Based Index 미지원)
            'PATTERN_B_COMPLEX_JOIN': 30, # 복잡한 조인 (5-Way 이상)
            'PATTERN_C_IMPLICIT_CAST': 35, # 묵시적 형변환 (타입 불일치)
            'PATTERN_D_ROWNUM': 35        # ROWNUM 기반 페이징
        }

    def evaluate_risk_score(self, query: str) -> dict:
        query_upper = query.upper()
        total_score = 0
        detected_patterns = []

        # 지표 1: 함수 기반 필터
        if re.search(r'\b(UPPER|LOWER|NVL|TO_CHAR|TO_DATE)\s*\(', query_upper):
            total_score += self.risk_metrics['PATTERN_A_FUNC_INDEX']
            detected_patterns.append("Pattern A: Function-Based Filter (Full Scan 위험)")

        # 지표 2: 다중 조인 복잡도 (5-Way 이상)
        if query_upper.count(' JOIN ') >= 4:
            total_score += self.risk_metrics['PATTERN_B_COMPLEX_JOIN']
            detected_patterns.append("Pattern B: Complex Join (성능 저하 위험)")

        # 지표 3: 묵시적 형변환 의심 (문자열 컬럼에 숫자 비교 등)
        if re.search(r'=\s*\d+(?!\s*\')', query_upper) and "'" not in query_upper:
            total_score += self.risk_metrics['PATTERN_C_IMPLICIT_CAST']
            detected_patterns.append("Pattern C: Implicit Type Cast (인덱스 무효화 위험)")

        # 지표 4: ROWNUM 페이징
        if 'ROWNUM' in query_upper:
            total_score += self.risk_metrics['PATTERN_D_ROWNUM']
            detected_patterns.append("Pattern D: ROWNUM Paging (전체 스캔 위험)")

        # 위험도 등급 산정
        risk_level = "LOW"
        if total_score >= 60:
            risk_level = "HIGH"
        elif total_score >= 30:
            risk_level = "MED"

        return {
            "query": query,
            "risk_score": total_score,
            "risk_level": risk_level,
            "detected_patterns": detected_patterns
        }

if __name__ == "__main__":
    predictor = RiskPredictor()
    test_query = "SELECT * FROM orders WHERE UPPER(status) = 'DONE' AND ROWNUM <= 10"
    print(json.dumps(predictor.evaluate_risk_score(test_query), indent=2, ensure_ascii=False))
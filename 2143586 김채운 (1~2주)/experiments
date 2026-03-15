import time
import pymysql
import json

class PerformanceExperiment:
    def __init__(self, db_config):
        self.conn = pymysql.connect(
            host=db_config.get('host', 'localhost'),
            user=db_config.get('user', 'root'),
            password=db_config.get('password', ''),
            db=db_config.get('db', 'shoppingmall'),
            cursorclass=pymysql.cursors.DictCursor
        )

    def extract_metrics(self, query: str):
        metrics = {"execution_time": 0.0, "rows_examined": 0, "access_type": "UNKNOWN"}
        
        try:
            with self.conn.cursor() as cursor:
                # 1. EXPLAIN으로 스캔 행 수 및 접근 타입 파싱
                cursor.execute(f"EXPLAIN FORMAT=JSON {query}")
                explain_data = json.loads(cursor.fetchone()['EXPLAIN'])
                
                table_info = explain_data.get('query_block', {}).get('table', {})
                if not table_info and 'nested_loop' in explain_data.get('query_block', {}):
                     table_info = explain_data['query_block']['nested_loop'][0].get('table', {})
                     
                metrics['access_type'] = table_info.get('access_type', 'UNKNOWN')
                metrics['rows_examined'] = table_info.get('rows_examined_per_scan', 0)

                # 2. 쿼리 실제 실행 시간 측정
                start_time = time.time()
                cursor.execute(query)
                cursor.fetchall()
                metrics['execution_time'] = round(time.time() - start_time, 4)
                
        except Exception as e:
            pass # 실험 중단 방지
            
        return metrics

    def run_shadow_test(self, pattern_id: str, bad_query: str, good_query: str):
        print(f"\n[실험 진행] {pattern_id}")
        
        bad_metrics = self.extract_metrics(bad_query)
        print(f" - [위험 버전] 소요시간: {bad_metrics['execution_time']}s | 스캔방식: {bad_metrics['access_type']} | 스캔행수: {bad_metrics['rows_examined']}")
        
        good_metrics = self.extract_metrics(good_query)
        print(f" - [안전 버전] 소요시간: {good_metrics['execution_time']}s | 스캔방식: {good_metrics['access_type']} | 스캔행수: {good_metrics['rows_examined']}")

    def execute_all_experiments(self):
        # Pattern A 실험
        self.run_shadow_test(
            pattern_id="Pattern A (Function-Based Filter)",
            bad_query="SELECT * FROM users WHERE UPPER(name) = 'KIM'",
            good_query="SELECT * FROM users WHERE name = 'KIM'"
        )
        
        # Pattern D 실험
        self.run_shadow_test(
            pattern_id="Pattern D (ROWNUM Paging Missing)",
            bad_query="SELECT * FROM orders /* ROWNUM 누락 가정한 쿼리 */",
            good_query="SELECT * FROM orders LIMIT 10"
        )

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    config = {'host': 'localhost', 'user': 'root', 'password': 'password', 'db': 'shoppingmall'}
    try:
        experiment = PerformanceExperiment(config)
        experiment.execute_all_experiments()
        experiment.close()
    except Exception as e:
        print("DB 연결 오류. config 정보를 실제 DB 환경에 맞게 수정 후 실행하세요.")
from pathlib import Path
from consistency_simulator import load_rules, evaluate_sql
import json

BASE = Path(__file__).parent
RULES = load_rules(BASE / "pattern_rules.json")

test_files = list((BASE / "type_tests").glob("P*.sql"))

for sql_path in test_files:
    name = sql_path.stem  # P11_positive
    
    out_path = sql_path.with_name(f"{name}_result.json")
    
    sql = sql_path.read_text(encoding="utf-8")
    result = evaluate_sql(sql, RULES)
    
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"{name} done")
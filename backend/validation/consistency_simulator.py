#  #.!/usr/bin/env python3
"""Oracle -> MySQL 정합성 검증 시뮬레이터.

주의: 이 모듈은 "정합성/호환성 패턴 탐지" 전용이다.
RiskScore 계산은 별도 예측 모델(김채운 파트)에서 수행한다.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


@dataclass
class Rule:
    id: str
    name: str
    risk: str
    type: str
    description: str
    fix: str
    failure_type: str
    impact: str
    quant_signal: str
    pattern: str | None = None
    heuristic: str | None = None


def load_rules(path: Path) -> list[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Rule(**item) for item in data]


def normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().upper()


def split_statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip()]


def _is_implicit_cast(sql: str) -> bool:
    return bool(re.search(r"\b[A-Z_][A-Z0-9_]*\s*=\s*'\d+'", sql))


def _is_join_without_index(sql: str) -> bool:
    if " JOIN " not in sql:
        return False
    has_index_hint = " USE INDEX" in sql or " FORCE INDEX" in sql
    mentions_index_ddl = "CREATE INDEX" in sql
    return not (has_index_hint or mentions_index_ddl)


def _is_nested_subquery(sql: str) -> bool:
    return sql.count("SELECT") >= 2


def match_heuristic(sql: str, name: str | None) -> bool:
    if name == "implicit_cast":
        return _is_implicit_cast(sql)
    if name == "join_without_index":
        return _is_join_without_index(sql)
    if name == "nested_subquery":
        return _is_nested_subquery(sql)
    return False


def match_rule(sql: str, rule: Rule) -> bool:
    if rule.type == "regex":
        return bool(rule.pattern and re.search(rule.pattern, sql))
    if rule.type == "heuristic":
        return match_heuristic(sql, rule.heuristic)
    return False


def highest_severity(risks: list[str]) -> str:
    if not risks:
        return "LOW"
    return max(risks, key=lambda r: SEVERITY_RANK.get(r, 1))


def evaluate_statement(statement: str, rules: list[Rule]) -> dict:
    normalized = normalize_sql(statement)
    matched = [rule for rule in rules if match_rule(normalized, rule)]

    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for rule in matched:
        severity_counts[rule.risk] = severity_counts.get(rule.risk, 0) + 1

    return {
        "statement": statement,
        "pattern_count": len(matched),
        "pattern_ids": [rule.id for rule in matched],
        "failure_types": sorted({rule.failure_type for rule in matched}),
        "severity_counts": severity_counts,
        "max_severity": highest_severity([rule.risk for rule in matched]),
        "matched_patterns": [
            {
                "id": rule.id,
                "name": rule.name,
                "severity": rule.risk,
                "failure_type": rule.failure_type,
                "description": rule.description,
                "impact": rule.impact,
                "quant_signal": rule.quant_signal,
            }
            for rule in matched
        ],
        "recommendations": sorted({rule.fix for rule in matched}),
    }


def evaluate_sql(sql: str, rules: list[Rule]) -> dict:
    statements = split_statements(sql)
    details = [evaluate_statement(stmt, rules) for stmt in statements]

    total_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    all_failure_types: set[str] = set()
    for item in details:
        for key in total_severity:
            total_severity[key] += item["severity_counts"].get(key, 0)
        all_failure_types.update(item["failure_types"])

    return {
        "summary": {
            "statement_count": len(details),
            "total_pattern_count": sum(item["pattern_count"] for item in details),
            "max_severity": highest_severity([item["max_severity"] for item in details]),
            "severity_counts": total_severity,
            "failure_types": sorted(all_failure_types),
            "note": "RiskScore is intentionally excluded. Use prediction model for scoring.",
        },
        "details": details,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정합성 검증 시뮬레이터")
    parser.add_argument("--rules", default="backend/validation/pattern_rules.json", help="패턴 규칙 JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sql", help="직접 SQL 문자열")
    group.add_argument("--sql-file", help="SQL 파일 경로")
    parser.add_argument("--output", help="결과 JSON 저장 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules = load_rules(Path(args.rules))
    sql_text = args.sql if args.sql else Path(args.sql_file).read_text(encoding="utf-8")
    report = evaluate_sql(sql_text, rules)

    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    print(report_json)

    if args.output:
        Path(args.output).write_text(report_json, encoding="utf-8")


if __name__ == "__main__":
    main()

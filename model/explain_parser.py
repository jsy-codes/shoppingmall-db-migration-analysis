# model/explain_parser.py
from __future__ import annotations

import json
import sys


def _extract_tables(query_block: dict) -> list[dict]:
    """
    MySQL EXPLAIN FORMAT=JSON 의 query_block 에서 모든 table 노드를 재귀적으로 수집.
    """
    tables: list[dict] = []

    if not isinstance(query_block, dict):
        return tables

    if "table" in query_block:
        table = query_block["table"]
        tables.append(table)

        for sub in table.get("attached_subqueries", []):
            tables.extend(_extract_tables(sub.get("query_block", {})))

    if "nested_loop" in query_block:
        for node in query_block["nested_loop"]:
            tables.extend(_extract_tables(node))

    return tables


def parse_explain_json(json_string: str) -> dict:
    """
    MySQL 8.0 EXPLAIN FORMAT=JSON 결과를 파싱해 quant_signal 반환.
    파싱 실패 또는 빈 입력이면 빈 dict 반환.
    """
    if not json_string or not json_string.strip():
        return {}

    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"[explain_parser] JSON 파싱 실패: {e}", file=sys.stderr)
        return {}

    query_block = data.get("query_block", {})
    tables = _extract_tables(query_block)

    if not tables:
        return {}

    danger_extras = {"Using temporary", "Using filesort", "Using join buffer"}

    full_scan_count = 0
    no_index = False
    total_rows = 0.0
    filtered_vals: list[float] = []
    extra_flags: set[str] = set()

    for table in tables:
        if table.get("access_type") == "ALL":
            full_scan_count += 1

        if table.get("key") is None:
            no_index = True

        total_rows += float(table.get("rows_examined_per_scan", 0) or 0)

        raw_filtered = table.get("filtered")
        if raw_filtered is not None:
            try:
                filtered_vals.append(float(raw_filtered))
            except (ValueError, TypeError):
                pass

        extra_raw = table.get("Extra", "")
        if isinstance(extra_raw, str):
            for flag in danger_extras:
                if flag in extra_raw:
                    extra_flags.add(flag)

    table_count = len(tables)

    return {
        "full_scan_ratio": round(full_scan_count / table_count, 3),
        "no_index_flag": no_index,
        "rows_ratio": total_rows,
        "filtered_min": min(filtered_vals) if filtered_vals else 100.0,
        "extra_flags": sorted(extra_flags),
        "table_count": table_count,
        "full_scan_count": full_scan_count,
    }
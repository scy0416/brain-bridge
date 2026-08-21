"""
logs/app.jsonl 을 읽어 단계별 지연시간 통계를 내고,
knowledge_graph_tool의 raw_result_count vs formatted_item_count 불일치(=포맷팅 단계 누락)를 찾아낸다.

사용법:
    python scripts/analyze_logs.py
    python scripts/analyze_logs.py --log-path logs/app.jsonl --request-id abcd1234ef56
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def load_records(log_path: str) -> List[dict]:
    records = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 로그가 깨진 줄은 건너뜀
    return records


def print_latency_stats(records: List[dict]) -> None:
    stage_durations: Dict[str, List[float]] = defaultdict(list)
    for rec in records:
        if rec.get("event") == "end" and "duration_sec" in rec:
            stage_durations[rec["stage"]].append(rec["duration_sec"])

    if not stage_durations:
        print("기록된 stage가 없습니다. log_stage()가 실제로 호출되고 있는지 확인하세요.")
        return

    print(f"{'STAGE':30s} {'N':>4s} {'median':>8s} {'p95':>8s} {'max':>8s}")
    print("-" * 62)
    for stage, durations in sorted(stage_durations.items(), key=lambda kv: -max(kv[1])):
        durations = sorted(durations)
        median = statistics.median(durations)
        p95_idx = min(int(len(durations) * 0.95), len(durations) - 1)
        p95 = durations[p95_idx]
        print(f"{stage:30s} {len(durations):4d} {median:7.2f}s {p95:7.2f}s {max(durations):7.2f}s")


def find_kg_mismatches(records: List[dict]) -> None:
    """kg_db_execution의 raw_result_count와 kg_formatting의 formatted_item_count를
    request_id 기준으로 매칭해서, 개수가 안 맞는 케이스를 출력한다."""
    by_request: Dict[str, dict] = defaultdict(dict)
    for rec in records:
        if rec.get("event") != "end":
            continue
        rid = rec.get("request_id")
        if rec.get("stage") == "kg_db_execution":
            by_request[rid]["raw_result_count"] = rec.get("raw_result_count")
            by_request[rid]["cypher_query"] = rec.get("cypher_query")
        elif rec.get("stage") == "kg_formatting":
            by_request[rid]["formatted_item_count"] = rec.get("formatted_item_count")

    mismatches = []
    for rid, data in by_request.items():
        raw = data.get("raw_result_count")
        fmt = data.get("formatted_item_count")
        if raw is not None and fmt is not None and raw != fmt:
            mismatches.append((rid, raw, fmt, data.get("cypher_query")))

    print("\n=== knowledge_graph 개수 불일치 케이스 ===")
    if not mismatches:
        print("없음 (raw_result_count == formatted_item_count 전부 일치)")
        return
    for rid, raw, fmt, query in mismatches:
        print(f"- request_id={rid}: DB 결과 {raw}건 -> 최종 출력 {fmt}건")
        print(f"  cypher: {query}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", default="logs/app.jsonl")
    args = parser.parse_args()

    if not Path(args.log_path).exists():
        print(f"로그 파일을 찾을 수 없습니다: {args.log_path}")
        return

    records = load_records(args.log_path)
    print_latency_stats(records)
    find_kg_mismatches(records)


if __name__ == "__main__":
    main()
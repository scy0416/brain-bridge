"""
scripts/load_graph_edges.py

data/graph/edges.json 을 읽어, orig_id로 두 정점을 매칭해서 Apache AGE 그래프
(companyx_graph)에 간선으로 적재한다.

사용법:
    docker compose run --rm app python scripts/load_graph_edges.py
    docker compose run --rm app python scripts/load_graph_edges.py --fresh   # 기존 간선 전체 삭제 후 재적재

주의: --fresh는 간선만 삭제한다 (정점은 그대로 유지). 정점까지 초기화하려면
      load_graph_nodes.py --fresh를 먼저 실행할 것.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph.age_client import age_session, get_connection, run_cypher, to_cypher_map

EDGES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "graph", "edges.json")

# edges.json의 relation 값은 이미 AGE의 UPPER_SNAKE_CASE 컨벤션과 일치하므로 변환 불필요
EXPECTED_COUNTS = {
    "BELONGS_TO": 45,
    "HEAD_IS": 6,
    "USES": 61,
    "MANAGES_ACCOUNT": 63,
    "HAS_PROJECT": 40,
    "LEADS": 40,
    "REPORTED_ISSUE": 99,
}


def reset_edges(conn):
    """--fresh 옵션: 그래프의 모든 간선만 삭제한다 (정점은 유지)."""
    print("==> 기존 간선 전체 삭제")
    run_cypher(conn, "MATCH ()-[r]->() DELETE r", return_cols="")
    conn.commit()


def load_edges(conn, edges: list) -> dict:
    counts = {}
    skipped = []

    for edge in edges:
        relation = edge["relation"]
        if relation not in EXPECTED_COUNTS:
            raise ValueError(f"알 수 없는 관계 타입: {relation}")

        source_id = edge["source"]
        target_id = edge["target"]
        props = edge.get("properties", {})
        rel_props = f" {to_cypher_map(props)}" if props else ""

        result = run_cypher(
            conn,
            f"""
            MATCH (a {{orig_id: "{source_id}"}}), (b {{orig_id: "{target_id}"}})
            CREATE (a)-[r:{relation}{rel_props}]->(b)
            RETURN r
            """,
            return_cols="r agtype",
        )
        conn.commit()

        if not result:
            # source/target 정점을 못 찾은 경우 (정점이 아직 적재 안 됐거나 orig_id 불일치)
            skipped.append((source_id, target_id, relation))
            continue

        counts[relation] = counts.get(relation, 0) + 1

    if skipped:
        print(f"\n⚠️  {len(skipped)}개 간선이 정점을 찾지 못해 스킵되었습니다:")
        for source_id, target_id, relation in skipped[:10]:
            print(f"    {source_id} -[{relation}]-> {target_id}")
        if len(skipped) > 10:
            print(f"    ... 외 {len(skipped) - 10}건")

    return counts


def count_existing_edges(conn) -> dict:
    counts = {}
    for relation in EXPECTED_COUNTS:
        result = run_cypher(
            conn,
            f"MATCH ()-[r:{relation}]->() RETURN count(r)",
            return_cols="cnt agtype",
        )
        counts[relation] = result[0][0]
    return counts


def already_loaded(conn) -> bool:
    return count_existing_edges(conn) == EXPECTED_COUNTS


def verify_counts(conn, counts: dict) -> bool:
    print("\n==> 관계별 개수 검증")
    all_ok = True
    for relation, expected in EXPECTED_COUNTS.items():
        actual = counts.get(relation, 0)
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_ok = False
        print(f"    {relation:16s} 기대={expected:3d}  실제={actual:3d}  [{status}]")

    print("\n==> DB 재조회로 이중 확인")
    db_counts = count_existing_edges(conn)
    for relation, db_count in db_counts.items():
        print(f"    {relation:16s} DB 조회 결과={db_count}")

    return all_ok


def main():
    fresh = "--fresh" in sys.argv

    with open(EDGES_PATH, encoding="utf-8") as f:
        edges = json.load(f)
    print(f"==> edges.json 로드: 총 {len(edges)}개 간선")

    conn = get_connection()

    if fresh:
        reset_edges(conn)
    elif already_loaded(conn):
        print("==> 이미 기대값만큼 적재되어 있습니다 — 재적재를 건너뜁니다. (강제 재적재: --fresh)")
        counts = count_existing_edges(conn)
        all_ok = verify_counts(conn, counts)
        conn.close()
        print("\n✅ 간선 데이터가 이미 최신 상태입니다." if all_ok else "\n⚠️  기대값과 다릅니다.")
        sys.exit(0 if all_ok else 1)

    counts = load_edges(conn, edges)
    print(f"\n==> 적재 완료: {counts}")

    all_ok = verify_counts(conn, counts)
    conn.close()

    if all_ok:
        print("\n✅ 간선 적재 및 검증 완료 — 기대값과 일치")
    else:
        print("\n⚠️  일부 관계의 개수가 기대값과 다릅니다. 위 로그를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
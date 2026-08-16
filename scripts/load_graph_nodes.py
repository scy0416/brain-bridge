"""
scripts/load_graph_nodes.py

data/graph/nodes.json 을 읽어 Apache AGE 그래프(companyx_graph)에 정점으로 적재한다.

사용법:
    docker compose run --rm app python scripts/load_graph_nodes.py
    docker compose run --rm app python scripts/load_graph_nodes.py --fresh   # 그래프 초기화 후 재적재
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph.age_client import (
    GRAPH_NAME,
    age_session,
    create_graph_if_not_exists,
    get_connection,
    run_cypher,
    to_cypher_map,
)

NODES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "graph", "nodes.json")

# 정점 레이블 매핑표 (nodes.json의 type → AGE 레이블)
TYPE_TO_LABEL = {
    "client": "Client",
    "product": "Product",
    "employee": "Employee",
    "project": "Project",
    "department": "Department",
}

EXPECTED_COUNTS = {
    "Client": 30,
    "Product": 12,
    "Employee": 45,
    "Project": 40,
    "Department": 6,
}


def reset_graph(conn):
    """--fresh 옵션: 그래프를 삭제하고 새로 생성한다."""
    print(f"==> 그래프 초기화: {GRAPH_NAME} 삭제 후 재생성")
    with age_session(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ag_catalog.ag_graph WHERE name = %s;", (GRAPH_NAME,))
            (exists_count,) = cur.fetchone()
            if exists_count > 0:
                cur.execute("SELECT drop_graph(%s, true);", (GRAPH_NAME,))
        conn.commit()
    create_graph_if_not_exists(conn)


def load_nodes(conn, nodes: list) -> dict:
    counts = {}
    for node in nodes:
        node_type = node["type"]
        if node_type not in TYPE_TO_LABEL:
            raise ValueError(f"알 수 없는 노드 타입: {node_type} (id={node['id']})")

        label = TYPE_TO_LABEL[node_type]
        vertex_props = {
            "orig_id": node["id"],
            "name": node["name"],
            **node.get("properties", {}),
        }
        cypher_map = to_cypher_map(vertex_props)

        run_cypher(
            conn,
            f"CREATE (n:{label} {cypher_map}) RETURN n",
            return_cols="n agtype",
        )
        conn.commit()
        counts[label] = counts.get(label, 0) + 1

    return counts


def verify_counts(conn, counts: dict):
    print("\n==> 타입별 개수 검증")
    all_ok = True
    for label, expected in EXPECTED_COUNTS.items():
        actual = counts.get(label, 0)
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_ok = False
        print(f"    {label:12s} 기대={expected:3d}  실제={actual:3d}  [{status}]")

    # DB에 실제로 반영됐는지도 그래프 쿼리로 재확인
    print("\n==> DB 재조회로 이중 확인")
    for label in EXPECTED_COUNTS:
        result = run_cypher(
            conn,
            f"MATCH (n:{label}) RETURN count(n)",
            return_cols="cnt agtype",
        )
        db_count = result[0][0]
        print(f"    {label:12s} DB 조회 결과={db_count}")

    return all_ok


def count_existing_vertices(conn) -> dict:
    """그래프에 이미 적재된 레이블별 정점 수를 조회한다."""
    counts = {}
    for label in EXPECTED_COUNTS:
        result = run_cypher(
            conn,
            f"MATCH (n:{label}) RETURN count(n)",
            return_cols="cnt agtype",
        )
        counts[label] = result[0][0]
    return counts


def already_loaded(conn) -> bool:
    """레이블별 정점 수가 기대값과 전부 일치하면 이미 적재된 것으로 간주한다."""
    existing = count_existing_vertices(conn)
    return existing == EXPECTED_COUNTS


def main():
    fresh = "--fresh" in sys.argv

    with open(NODES_PATH, encoding="utf-8") as f:
        nodes = json.load(f)
    print(f"==> nodes.json 로드: 총 {len(nodes)}개 노드")

    conn = get_connection()

    if fresh:
        reset_graph(conn)
    else:
        create_graph_if_not_exists(conn)
        if already_loaded(conn):
            print("==> 이미 기대값만큼 적재되어 있습니다 — 재적재를 건너뜁니다. (강제 재적재: --fresh)")
            counts = count_existing_vertices(conn)
            verify_counts(conn, counts)
            conn.close()
            print("\n✅ 정점 데이터가 이미 최신 상태입니다.")
            return

    counts = load_nodes(conn, nodes)
    print(f"\n==> 적재 완료: {counts}")

    all_ok = verify_counts(conn, counts)

    conn.close()

    if all_ok:
        print("\n✅ 정점 적재 및 검증 완료 — 기대값과 일치")
    else:
        print("\n⚠️  일부 타입의 개수가 기대값과 다릅니다. 위 로그를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
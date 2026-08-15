"""
scripts/verify_cypher_helper.py

src/graph/age_client.py의 run_cypher() 헬퍼가 실제로 동작하는지
더미 데이터로 검증하는 스크립트.

실행:
    docker compose exec -T <api 또는 별도 python 환경> python scripts/verify_cypher_helper.py
    (혹은 로컬에 psycopg2가 설치되어 있고 POSTGRES_PORT가 호스트에 노출돼 있다면
     POSTGRES_HOST=localhost 로 바꿔서 로컬에서 바로 실행 가능)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph.age_client import create_graph_if_not_exists, get_connection, run_cypher

TEST_GRAPH = "verify_helper_graph"


def main():
    conn = get_connection()

    print(f"==> [1/5] 테스트 그래프 생성: {TEST_GRAPH}")
    create_graph_if_not_exists(conn, graph_name=TEST_GRAPH)

    print("==> [2/5] 정점 생성 (속성 포함)")
    result = run_cypher(
        conn,
        "CREATE (n:Client {orig_id: 'test_client_1', name: 'Test Client', region: '서울'}) RETURN n",
        return_cols="n agtype",
        graph_name=TEST_GRAPH,
    )
    conn.commit()
    print("    결과:", result)
    assert len(result) == 1, "정점 생성 결과가 1개가 아닙니다"
    assert result[0][0]["properties"]["name"] == "Test Client"

    print("==> [3/5] 정점 두 번째 생성 + 관계(속성 포함) 생성")
    result = run_cypher(
        conn,
        """
        CREATE (p:Product {orig_id: 'test_product_1', name: 'Test Product'})
        WITH p
        MATCH (c:Client {orig_id: 'test_client_1'})
        CREATE (c)-[r:USES {amount: 1000, status: 'active'}]->(p)
        RETURN r
        """,
        return_cols="r agtype",
        graph_name=TEST_GRAPH,
    )
    conn.commit()
    print("    결과:", result)
    assert result[0][0]["label"] == "USES"
    assert result[0][0]["properties"]["amount"] == 1000

    print("==> [4/5] MATCH로 조회 (1-hop 순회)")
    result = run_cypher(
        conn,
        """
        MATCH (c:Client {orig_id: 'test_client_1'})-[:USES]->(p:Product)
        RETURN p
        """,
        return_cols="p agtype",
        graph_name=TEST_GRAPH,
    )
    print("    결과:", result)
    assert len(result) == 1
    assert result[0][0]["properties"]["orig_id"] == "test_product_1"

    print("==> [5/5] 정형 테이블(SELECT)과 그래프 쿼리를 한 트랜잭션에서 함께 실행")
    with conn.cursor() as cur:
        cur.execute("BEGIN;")
        cur.execute("SELECT count(*) FROM clients;")
        (client_count,) = cur.fetchone()
        cur.execute("COMMIT;")
    graph_result = run_cypher(
        conn,
        "MATCH (n:Client) RETURN count(n)",
        return_cols="cnt agtype",
        graph_name=TEST_GRAPH,
    )
    print(f"    정형 테이블 clients 행 수: {client_count}")
    print(f"    그래프 Client 정점 수: {graph_result[0][0]}")

    print("\n==> 정리: 테스트 그래프 삭제")
    with conn.cursor() as cur:
        cur.execute("LOAD 'age';")
        cur.execute('SET search_path = ag_catalog, "$user", public;')
        cur.execute("SELECT drop_graph(%s, true);", (TEST_GRAPH,))
    conn.commit()

    conn.close()
    print("\n✅ Cypher 헬퍼 검증 완료 — 모든 단계 통과")


if __name__ == "__main__":
    main()
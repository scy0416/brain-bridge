#!/bin/bash
set -e

echo "==> [사전 점검] Cypher 헬퍼 동작 검증"
python scripts/verify_cypher_helper.py

echo ""
echo "==> [1/2] nodes.json 정점 적재"
python scripts/load_graph_nodes.py

echo ""
echo "==> [2/2] edges.json 간선 적재"
python scripts/load_graph_edges.py
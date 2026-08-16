#!/bin/bash
set -e

echo "==> [사전 점검] Cypher 헬퍼 동작 검증"
python scripts/verify_cypher_helper.py

echo ""
echo "==> [본 작업] nodes.json 정점 적재"
python scripts/load_graph_nodes.py
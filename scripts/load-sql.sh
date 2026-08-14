#!/bin/bash
set -e

# scripts/load-sql.sh
#
# db/01-init-extensions.sql, db/schema/02-schema.sql, db/schema/03-data.sql는
# PostgreSQL 컨테이너의 docker-entrypoint-initdb.d/ 메커니즘을 통해 최초 기동 시
# 자동으로 적용됩니다 (빈 볼륨일 때만 실행됨).
#
# 이 스크립트는 그 결과를 검증하고, 필요하면 --fresh 옵션으로 클린 재기동까지 수행합니다.
#
# 사용법:
#   ./scripts/load-sql.sh            # 현재 상태 검증만 수행
#   ./scripts/load-sql.sh --fresh    # 볼륨 삭제 후 처음부터 재기동 + 검증

if [ ! -f .env ]; then
  echo "오류: .env 파일이 없습니다. 'cp .env.example .env' 후 다시 실행하세요."
  exit 1
fi
source .env

FRESH=false
if [[ "$1" == "--fresh" ]]; then
  FRESH=true
fi

if [ "$FRESH" = true ]; then
  echo "==> 기존 볼륨 삭제 후 클린 재기동 (docker-entrypoint-initdb.d 재실행)"
  docker compose down -v
  docker compose up postgres -d --build

  echo "==> PostgreSQL 준비 대기 중..."
  until docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    sleep 1
  done
fi

PSQL="docker compose exec -T postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}"

echo ""
echo "==> [1/5] 확장 설치 확인 (age, vector, plpgsql)"
$PSQL -c "\dx"

echo ""
echo "==> [2/5] 테이블 목록 확인 (9개 테이블 존재해야 함)"
$PSQL -c "\dt"

echo ""
echo "==> [3/5] document_chunks 임베딩 차원 확인 (vector(1024)이어야 함)"
$PSQL -c "\d document_chunks"

echo ""
echo "==> [4/5] 테이블별 행 수 확인"
echo "    기대값: departments=6, employees=45, clients=30, products=12,"
echo "           contracts=65, projects=40, sales=500, support_tickets=120,"
echo "           document_chunks=0 (임베딩 파이프라인에서 별도 적재 예정)"
$PSQL -c "
SELECT 'departments' AS table_name, count(*) FROM departments
UNION ALL SELECT 'employees', count(*) FROM employees
UNION ALL SELECT 'clients', count(*) FROM clients
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'contracts', count(*) FROM contracts
UNION ALL SELECT 'projects', count(*) FROM projects
UNION ALL SELECT 'sales', count(*) FROM sales
UNION ALL SELECT 'support_tickets', count(*) FROM support_tickets
UNION ALL SELECT 'document_chunks', count(*) FROM document_chunks
ORDER BY table_name;
"

echo ""
echo "==> [5/5] FK 조인 동작 확인"
echo "---- employees x departments ----"
$PSQL -c "
SELECT e.name AS employee_name, e.position, d.name AS department_name
FROM employees e
JOIN departments d ON e.dept_id = d.id
LIMIT 5;
"

echo "---- sales x clients x products ----"
$PSQL -c "
SELECT c.name AS client_name, p.name AS product_name, s.amount, s.region
FROM sales s
JOIN clients c ON s.client_id = c.id
JOIN products p ON s.product_id = p.id
LIMIT 5;
"

echo ""
echo "==> 완료: 정형 데이터 적재 및 검증이 끝났습니다."
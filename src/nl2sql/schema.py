"""
src/nl2sql/schema.py

정형 데이터 8개 테이블의 스키마를 LLM 프롬프트에 삽입 가능한 텍스트로 정리한다.
(document_chunks는 벡터 검색 전용 테이블이라 NL2SQL 스키마 컨텍스트에서 제외)
"""

SCHEMA_TEXT = """\
## 테이블: departments (부서, 6행)
- id (PK, 정수)
- name (부서명, 문자열. 예: "경영지원팀", "클라우드사업부", "보안솔루션팀", "데이터플랫폼팀", "기술지원팀")
- head_id (부서장 직원 id, employees.id 참조, 정수)
- created_at (생성일시, timestamp)

## 테이블: employees (직원, 45행)
- id (PK, 정수)
- name (직원 이름, 문자열)
- email (이메일, 문자열)
- position (직급, 문자열. 예: "부장", "이사", "사원")
- dept_id (소속 부서 id, departments.id 참조, 정수)
- hire_date (입사일, date. 형식 'YYYY-MM-DD')
- salary (연봉, 정수. 단위 원)
- is_active (재직 여부, boolean: true/false)
- created_at (생성일시, timestamp)

## 테이블: clients (고객사, 30행)
- id (PK, 정수)
- name (고객사명, 문자열. 예: "Client-A")
- industry (업종, 문자열. 예: "제조업", "금융", "의료/바이오", "유통/물류", "에너지", "공공기관", "미디어")
- region (지역, 문자열. 예: "서울", "경기", "인천", "대전", "제주")
- company_size (기업 규모, 문자열. 정확히 다음 두 값 중 하나: "startup", "mid")
- contact_name (담당자 이름, 문자열)
- contact_email (담당자 이메일, 문자열)
- registered_at (고객사 등록일, date. 형식 'YYYY-MM-DD')
- is_active (거래 활성 여부, boolean: true/false)
- created_at (생성일시, timestamp)

## 테이블: products (제품/솔루션, 12행)
- id (PK, 정수)
- name (제품명, 문자열. 예: "Product-C1")
- category (카테고리, 문자열. 정확히 다음 값들 중 하나: "cloud", "security", "data", "consulting")
- description (제품 설명, 문자열)
- price_monthly (월 구독료, 정수. 단위 원)
- version (버전, 문자열)
- release_date (출시일, date. 형식 'YYYY-MM-DD')
- status (제품 상태, 문자열. 예: "active")
- created_at (생성일시, timestamp)

## 테이블: contracts (계약, 65행)
- id (PK, 정수)
- client_id (고객사 id, clients.id 참조, 정수)
- product_id (제품 id, products.id 참조, 정수)
- manager_id (담당 직원 id, employees.id 참조, 정수)
- contract_type (계약 유형, 문자열)
- amount (계약 금액, 정수. 단위 원)
- start_date (계약 시작일, date. 형식 'YYYY-MM-DD')
- end_date (계약 종료일, date, NULL 가능)
- status (계약 상태, 문자열. 예: "active")
- created_at (생성일시, timestamp)

## 테이블: projects (프로젝트, 40행)
- id (PK, 정수)
- name (프로젝트명, 문자열)
- client_id (고객사 id, clients.id 참조, 정수)
- manager_id (담당 직원 id, employees.id 참조, 정수)
- contract_id (연관 계약 id, contracts.id 참조, 정수, NULL 가능)
- status (진행 상태, 문자열. 정확히 다음 값들 중 하나: "in_progress", "completed")
- start_date (시작일, date. 형식 'YYYY-MM-DD')
- end_date (종료일, date, NULL 가능)
- budget (예산, 정수. 단위 원)
- description (프로젝트 설명, 문자열)
- created_at (생성일시, timestamp)

## 테이블: sales (매출, 500행)
- id (PK, 정수)
- contract_id (계약 id, contracts.id 참조, 정수)
- client_id (고객사 id, clients.id 참조, 정수)
- product_id (제품 id, products.id 참조, 정수)
- amount (매출액, 정수. 단위 원)
- sale_date (매출 발생일, date. 형식 'YYYY-MM-DD')
- quarter (분기, 문자열. 형식 "YYYY-Q1"~"YYYY-Q4", 예: "2025-Q3")
- category (제품 카테고리, 문자열. products.category와 동일한 값 범위: "cloud", "security", "data", "consulting")
- region (매출 발생 지역, 문자열. clients.region과 동일한 값 범위)
- created_at (생성일시, timestamp)

## 테이블: support_tickets (기술 지원 티켓, 120행)
- id (PK, 정수)
- client_id (고객사 id, clients.id 참조, 정수)
- product_id (제품 id, products.id 참조, 정수)
- assignee_id (담당 직원 id, employees.id 참조, 정수, NULL 가능)
- title (티켓 제목, 문자열)
- description (상세 내용, 문자열)
- priority (우선순위, 문자열. 정확히 다음 값들 중 하나: "critical", "high", "medium", "low")
- status (처리 상태, 문자열. 정확히 다음 값들 중 하나: "open", "in_progress", "resolved", "closed".
  "미해결"/"아직 해결 안 됨"을 의미하는 질문은 status IN ('open', 'in_progress')로 필터링할 것 —
  status != 'resolved' 는 'closed'까지 포함시키는 실수이므로 사용하지 말 것)
- created_at (티켓 생성일시, timestamp)
- resolved_at (해결일시, timestamp, NULL 가능)
"""

FK_SUMMARY = """\
## 외래키(FK) 관계 요약

- departments.head_id → employees.id (부서의 부서장 — 딱 1명. "부서 직원 전체"를 조회할 때는 이 FK가 아니라 employees.dept_id를 써야 함!)
- employees.dept_id → departments.id (직원의 소속 부서 — "부서 소속 직원 목록/평균" 등은 반드시 이 방향으로 조인)
- contracts.client_id → clients.id (계약의 고객사)
- contracts.product_id → products.id (계약의 제품)
- contracts.manager_id → employees.id (계약 담당 직원)
- projects.client_id → clients.id (프로젝트의 고객사)
- projects.manager_id → employees.id (프로젝트 담당 직원)
- projects.contract_id → contracts.id (프로젝트와 연관된 계약, NULL 가능)
- sales.contract_id → contracts.id (매출이 발생한 계약)
- sales.client_id → clients.id (매출의 고객사)
- sales.product_id → products.id (매출의 제품)
- support_tickets.client_id → clients.id (티켓을 등록한 고객사)
- support_tickets.product_id → products.id (티켓 대상 제품)
- support_tickets.assignee_id → employees.id (티켓 담당 직원, NULL 가능)

## 자주 쓰이는 조인 경로

- 직원의 소속 부서: employees JOIN departments ON employees.dept_id = departments.id
- 매출 상세(고객사/제품명 포함): sales JOIN clients ON sales.client_id = clients.id
                                  JOIN products ON sales.product_id = products.id
- 계약 상세(고객사/제품/담당자 포함): contracts JOIN clients ON contracts.client_id = clients.id
                                     JOIN products ON contracts.product_id = products.id
                                     JOIN employees ON contracts.manager_id = employees.id
- 프로젝트 상세(고객사/담당자 포함): projects JOIN clients ON projects.client_id = clients.id
                                    JOIN employees ON projects.manager_id = employees.id
- 티켓 상세(고객사/제품/담당자 포함): support_tickets JOIN clients ON support_tickets.client_id = clients.id
                                     JOIN products ON support_tickets.product_id = products.id
                                     JOIN employees ON support_tickets.assignee_id = employees.id
- 부서장 조회: departments JOIN employees ON departments.head_id = employees.id
"""
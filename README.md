# Brain Bridge

MCP(Model Context Protocol) 기반 지능형 데이터 플랫폼 — 2026년 오픈소스 개발자대회 [리원에이스 지정과제](https://liwonace.co.kr/blog/9) 출품작

사용자의 자연어 질문을 받아, 로컬에서 구동되는 소형 LLM 에이전트가 스스로 적절한 도구(정형 데이터 조회, 문서 검색, 지식 그래프 탐색)를 선택하고 PostgreSQL 데이터베이스를 조회하여 답변을 생성하는 end-to-end 시스템입니다. 모든 컴포넌트는 외부 API 호출 없이 로컬 환경에서 완결적으로 동작합니다.

## 아키텍처

```
[Open WebUI] ── HTTP(OpenAI 호환) ──▶ [FastAPI 어댑터]
                                            │
                                            ▼
                                 ┌───────────────────────────────────────┐
                                 │            LangGraph 그래프              │
                                 │                                        │
                                 │   Base Agent (게이트 노드)                │  ← Gemma 4 E4B
                                 │   "데이터 조회가 필요한 질문인가?"           │     (Ollama, 로컬 실행)
                                 │        │                               │
                                 │        ├── 질문 (조회 필요) ──────┐        │
                                 │        │                       ▼        │
                                 │        │              Router Agent      │  ← 도구 필요 판단 시에만 호출
                                 │        │              (bind_tools,      │     (비용이 큰 경로이므로
                                 │        │               tool_call 생성)   │      Base Agent가 먼저 걸러냄)
                                 │        │                       │        │
                                 │        │                       ▼        │
                                 │        │              Tool 실행 노드      │  ← MCP tools/call
                                 │        │              (ToolNode)        │
                                 │        │                       │        │
                                 │        ├── 비질문 (잡담/메타) ──┤        │
                                 │        │  (도구 호출 없이 직행)  │        │
                                 │        ▼                       ▼        │
                                 │              Answer Agent                │  ← Gemma 4 E4B
                                 │   (도구 결과 有: RAG 방식 답변 생성 /       │     (동일 인스턴스, 프롬프트만 교체)
                                 │    도구 결과 無: 대화형 답변 생성)          │
                                 └───────────────────────────────────────┘
                                            │
                                            ▼ (Router Agent 경로에서만)
                                 ┌─────────────────────┐
                                 │     MCP 서버          │  (공식 MCP Python SDK,
                                 │  - nl2sql_tool        │   MCPServer 클래스)
                                 │  - vector_search_tool │
                                 │  - knowledge_graph_tool│
                                 └─────────────────────┘
                                            │
                                            ▼
                                 ┌─────────────────────┐
                                 │   PostgreSQL          │
                                 │  - 정형 데이터 (8개 테이블)│
                                 │  - pgvector (문서 임베딩) │
                                 │  - Apache AGE (지식 그래프)│
                                 └─────────────────────┘
```

**Base Agent가 먼저 질문/비질문 여부를 판단해 불필요한 도구 호출 비용을 막습니다.** 데이터 조회가 필요 없는 인사말·잡담·메타 질문은 Router Agent/MCP 도구 단계를 거치지 않고 Answer Agent가 곧바로 대화형으로 응답하고, 실제 데이터 조회가 필요한 질문만 Router Agent로 넘어가 도구 선택(네이티브 function-calling)과 MCP 도구 실행을 거칩니다. 두 경로 모두 최종적으로 Answer Agent에서 응답을 생성한다는 점은 동일합니다.

규칙 기반 분류기(키워드/패턴 매칭)가 Router Agent에게 참고용 힌트를 제공하지만, 최종 도구 선택은 Router Agent가 MCP 도구 설명을 바탕으로 자율적으로 결정합니다.

## 주요 구성 요소

| 구성 요소 | 선택 | 비고 |
|---|---|---|
| LLM | Gemma 4 E4B | Ollama 로컬 실행, Apache-2.0, function-calling 네이티브 지원 |
| 임베딩 모델 | BGE-M3 | Ollama 로컬 실행, MIT, 1024차원, 한국어 검색 성능 우수 |
| 벡터 검색 | pgvector | PostgreSQL 확장 |
| 지식 그래프 | Apache AGE | PostgreSQL 확장 (별도 그래프 DB 서비스 없이 단일 DB로 통합) |
| MCP 서버 | 공식 MCP Python SDK (`MCPServer`) | 舊 FastMCP |
| 에이전트 오케스트레이션 | LangGraph | Base Agent(질문/비질문 게이트) → Router Agent → Answer Agent로 이어지는 멀티 에이전트 구조 |
| 실행 인터페이스 | Open WebUI | FastAPI 어댑터를 통해 OpenAI 호환 API로 연동 |

## 데이터셋

`data/` 디렉토리에 [companyx-dataset-v1.0.zip](https://liwonace.co.kr/blog/9)(가상 IT 솔루션 기업 "Company-X"의 운영 데이터) 원본을 포함하고 있습니다. 대회 측으로부터 데이터셋 원본을 공개 저장소에 포함해도 좋다는 서면(이메일) 확인을 받았습니다.

```
data/
├── companyx-dataset-v1.0.zip   # 원본 보존
├── README.md                    # 데이터셋 자체 설명 (원본)
├── sql/                          # 정형 데이터 (DDL + INSERT)
├── documents/                    # 비정형 문서 40건
├── graph/                        # 지식 그래프 노드/관계
└── questions.json                # 예시 질문 30개
```

> 실제 적재에 사용하는 스키마는 `db/schema/01-schema.sql`에 별도로 관리합니다 — BGE-M3(1024차원)에 맞춰 `document_chunks.embedding` 차원을 원본의 `vector(768)`에서 `vector(1024)`로 수정했습니다. 원본(`data/sql/01-schema.sql`)은 수정하지 않고 그대로 보존합니다.

## 사전 요구사항

- **Docker Engine 20.10 이상** (`docker --version`으로 확인)
- **Docker Compose v2** — `docker compose`(하이픈 없는 서브커맨드) 형태로 동작하는 버전이어야 합니다. `docker compose version`으로 확인하세요. 이 프로젝트의 `docker-compose.yml`은 최신 Compose Specification을 따르며 `version:` 필드를 명시하지 않습니다 — 구버전 `docker-compose`(v1, 하이픈 포함) 사용 시 정상 동작하지 않을 수 있습니다.
- **메모리 최소 8GB, 권장 12GB 이상** — Gemma 4 E4B(4.5B) + BGE-M3 + PostgreSQL(pgvector/AGE)을 동시에 구동합니다. Windows에서 Docker Desktop(WSL2 백엔드) 사용 시, 기본 WSL2 메모리 할당(호스트 RAM의 50%)이 부족할 수 있으니 `%USERPROFILE%\.wslconfig`에서 별도로 늘려주는 것을 권장합니다:
  ```ini
  [wsl2]
  memory=12GB
  ```
  적용 후 `wsl --shutdown` 실행 및 Docker Desktop 재시작이 필요합니다.
- **여유 디스크 공간 약 10GB** (모델 다운로드 포함)

## 설치 및 실행

### 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 전체 스택 기동 (PostgreSQL, Ollama, MCP 서버, Open WebUI)
docker compose up -d --build

# 3. 데이터 적재 (정형 데이터 + 그래프 + 문서 임베딩)
./scripts/setup-data.sh

# 4. Open WebUI 접속
# http://localhost:3000
```

모델(Gemma 4 E4B, BGE-M3) 다운로드는 `ollama-init` 서비스가 `docker compose up` 시 자동으로 처리합니다 — 별도 스크립트를 수동 실행할 필요는 없습니다 (최초 실행 시 다운로드로 인해 몇 분 정도 소요될 수 있습니다).

### 인프라 기동 절차 (단계별 상세)

전체를 한 번에 띄우기보다 컴포넌트별로 순서대로 검증하고 싶다면 아래 순서를 따르세요.

**1. PostgreSQL 기동 및 확장 확인**
```bash
docker compose up postgres -d --build
docker compose logs postgres
```
로그에 `database system is ready to accept connections`가 보이면 정상입니다. 확장 설치 여부는 다음으로 확인합니다.
```bash
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dx"
```
`age`, `vector`, `plpgsql` 세 항목이 모두 나열되어야 합니다.

**2. Ollama 기동 및 모델 확인**
```bash
docker compose up ollama ollama-init -d --build
docker compose logs -f ollama-init
```
`ollama-init`은 모델 pull이 끝나면 자동 종료(`Exited (0)`)됩니다.
```bash
docker compose ps
docker compose exec ollama ollama list
```
`gemma4:e4b`, `bge-m3`가 목록에 있어야 합니다.

**3. 전체 스택 기동**
```bash
docker compose up -d --build
docker compose ps
```
모든 서비스가 `Up`(또는 `ollama-init`은 `Exited (0)`) 상태인지 확인합니다.

**4. 클린 재현 테스트 (권장)**
심사·재현 목적으로 처음부터 다시 기동해도 동일하게 동작하는지 확인합니다.
```bash
docker compose down -v
docker compose up -d --build
```

### 트러블슈팅

- **`docker compose up` 시 메모리 부족으로 컨테이너가 강제 종료(`signal: killed`)되는 경우**: 위 [사전 요구사항](#사전-요구사항)의 메모리 설정(`.wslconfig` 등)을 확인하세요.
- **`.env`/`.sh` 파일을 Windows 에디터로 수정한 뒤 `$'\r': command not found` 등의 오류가 발생하는 경우**: 파일이 CRLF 줄바꿈으로 저장되어 발생하는 문제입니다. `sed -i 's/\r$//' <파일명>` 또는 `dos2unix <파일명>`으로 LF로 변환하세요.
- **Ollama 응답이 몇 분씩 지연되는 경우**: 최초 요청 시 모델을 메모리에 로드하는 데 다소 시간이 걸릴 수 있습니다(수 분 소요 가능). 이후 요청부터는 `OLLAMA_KEEP_ALIVE=-1` 설정에 따라 모델이 계속 상주하여 빨라집니다.
- **Apache AGE 관련 쿼리(`cypher()` 등)가 "function does not exist" 또는 "relation does not exist" 오류를 내는 경우**: AGE는 PostgreSQL 확장 특성상 **세션(커넥션)마다** 아래 두 줄을 먼저 실행해야 `ag_catalog` 스키마와 `cypher()` 함수가 인식됩니다.
  ```sql
  LOAD 'age';
  SET search_path = ag_catalog, "$user", public;
  ```
  - `psql -f file.sql` 또는 `< file.sql`처럼 **한 세션 안에서 여러 쿼리를 순차 실행**하는 경우, 파일 맨 위에 한 번만 넣으면 이후 쿼리에 모두 적용됩니다.
  - 반면 매번 새로운 접속(새 커넥션)으로 나눠서 쿼리를 실행하면, 접속할 때마다 이 두 줄을 다시 실행해야 합니다 — 이 설정은 세션에 종속되며 DB에 영구 저장되지 않습니다.
  - 애플리케이션 코드(Python 등)에서 커넥션 풀을 사용할 경우, **매 커넥션 획득 시 위 두 줄을 초기화 쿼리로 실행**하도록 구현해야 합니다 (예: `psycopg2`/`asyncpg`의 커넥션 생성 콜백에 포함).
  - `create_graph()`를 이미 실행한 그래프에 다시 실행하면 `graph "..." already exists` 오류가 납니다 — 정상적인 안내이며, 필요 시 `SELECT drop_graph('<그래프명>', true);`로 초기화 후 재실행하세요.

## 프로젝트 구조

```
.
├── data/               # 원본 데이터셋 (증빙 보존용)
├── db/
│   └── schema/         # 실제 적재용 수정 스키마
├── scripts/             # 셋업/로더 스크립트
├── src/
│   ├── tools/            # nl2sql / vector_search / knowledge_graph 도구
│   ├── router/           # 규칙 기반 분류기 + Router Agent
│   ├── agent/            # LangGraph 그래프 정의 (Base/Router/Answer Agent)
│   └── api/              # FastAPI OpenAI 호환 어댑터
├── docker-compose.yml
├── .env.example
├── LICENSE
├── THIRD_PARTY_LICENSES.md
└── README.md
```

## 라이선스

이 프로젝트의 소스코드는 [MIT License](./LICENSE) 하에 배포됩니다.

사용된 모든 서드파티 라이브러리 및 AI 모델의 라이선스는 [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)에서 확인할 수 있습니다.

## AI 모델 활용 내역

본 프로젝트는 로컬 오픈웨이트 모델(Gemma 4 E4B, BGE-M3)만을 사용하며 외부 API 호출 없이 동작합니다. 개발 과정에서 Claude(Anthropic)를 코드 작성 및 설계 논의 보조 도구로 활용했습니다. 자세한 내용은 대회 지정 서식의 AI 모델 활용 내역서를 참고해 주세요.

## 대회 정보

- 대회명: 2026년 오픈소스 개발자대회
- 지정과제: [MCP 기반 지능형 데이터 플랫폼 클러스터](https://liwonace.co.kr/blog/9) (리원에이스)
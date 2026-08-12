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

- Docker
- Docker Compose
- 여유 디스크 공간 약 10GB (모델 다운로드 포함)

## 설치 및 실행

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 전체 스택 기동 (PostgreSQL, Ollama, MCP 서버, Open WebUI)
docker compose up -d

# 3. 필요 모델 자동 다운로드 (최초 1회, 없으면 자동 실행)
./scripts/pull-models.sh

# 4. 데이터 적재 (정형 데이터 + 그래프 + 문서 임베딩)
./scripts/setup-data.sh

# 5. Open WebUI 접속
# http://localhost:3000
```

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
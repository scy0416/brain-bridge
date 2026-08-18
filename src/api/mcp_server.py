"""
src/api/mcp_server.py

공식 MCP Python SDK(MCPServer, 舊 FastMCP)에 3개 도구를 등록한다.
- nl2sql_tool: 정형 데이터(8개 테이블) 자연어 질의
- vector_search_tool: 비정형 문서(40건) 벡터 유사도 검색
- knowledge_graph_tool: 지식 그래프(정점 133/관계 354) 관계 탐색

이 세 도구를 Router Agent가 bind_tools로 인식해서 자율적으로 선택·호출하게 된다
(Phase 12). 도구 설명(docstring)이 그 판단의 핵심 근거이므로, 각 도구의
역할과 사용 시점을 서로 명확히 구분되도록 작성했다.
"""

import os
import sys

# src/api/mcp_server.py에서 src/ 하위 패키지(tools, graph, nl2sql, documents)를
# import하려면 src/ 자체가 경로에 있어야 한다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import MCPServer

from tools.knowledge_graph_tool import knowledge_graph_tool as _knowledge_graph_tool
from tools.nl2sql_tool import nl2sql_tool as _nl2sql_tool
from tools.vector_search_tool import vector_search_tool as _vector_search_tool

# 별도 컨테이너("mcp-server" 서비스)로 상시 구동되며, 다른 컨테이너("app")가
# 네트워크(Streamable HTTP)로 접속한다. 같은 프로세스 안에서 부르는 게 아니다.
MCP_HOST = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_SERVER_PORT", "8100"))

mcp = MCPServer("brain-bridge")


@mcp.tool()
def nl2sql_tool(question: str) -> dict:
    """
    회사의 정형(테이블) 데이터베이스에 대한 질문에 답한다.
    매출, 계약, 고객사 정보, 직원/부서 정보, 제품 목록, 기술 지원 티켓처럼
    "숫자로 집계하거나(합계/평균/개수/순위), 조건으로 필터링해야 하는" 질문에 사용한다.
    예: "서울 지역 매출 상위 5개 고객사", "현재 활성 계약 수", "평균 연봉이 가장 높은 부서".
    자연어 질문을 SQL로 변환해서 실행하고 결과를 반환한다.
    """
    return _nl2sql_tool(question)


@mcp.tool()
def vector_search_tool(question: str, k: int = 3) -> dict:
    """
    회사의 비정형 문서(장애보고서/기술문서/회의록/제안서)에서 질문과 의미적으로
    관련된 내용을 검색한다. "방법", "정책", "이슈가 있었나", "논의된 내용" 처럼
    문서 안의 서술형 정보를 찾아야 하는 질문에 사용한다.
    예: "Product-C1 설치 방법", "백업 정책", "SSL 인증서 관련 장애가 있었나".
    :param k: 반환할 관련 문서 조각 개수 (기본 3)
    """
    return _vector_search_tool(question, k=k)


@mcp.tool()
def knowledge_graph_tool(question: str) -> dict:
    """
    회사 조직/고객/제품 간의 "관계"를 묻는 질문에 답한다. 고객사-제품 사용 관계,
    직원-부서 소속, 직원-고객사 담당, 직원-프로젝트 리드, 부서장, 기술 지원 이슈
    제기 관계처럼 "누가 무엇을 사용/담당/소속/이끄는지"를 묻는 질문에 사용한다.
    예: "Client-A가 사용 중인 제품", "클라우드사업부 소속 직원", "경영지원팀 팀장",
    "이슈가 가장 많은 제품", "가장 많은 고객을 담당하는 직원".
    """
    return _knowledge_graph_tool(question)


if __name__ == "__main__":
    # 별도 "mcp-server" 컨테이너로 상시 구동되며, 네트워크(HTTP)로 접속받는다.
    print(f"MCP 서버 시작: http://{MCP_HOST}:{MCP_PORT}/mcp (Streamable HTTP)")
    mcp.run(transport="streamable-http", host=MCP_HOST, port=MCP_PORT)
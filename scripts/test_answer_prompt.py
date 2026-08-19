"""
scripts/test_answer_prompt.py

format_tool_results()/build_answer_messages()가 MCP 응답 형태를
올바르게 파싱해서 프롬프트 텍스트로 정리하는지 확인한다.
실제 LLM 호출 없이, 가짜 MCP 결과 객체로 결정론적으로 검증한다.

사용법:
    docker compose run --rm app python scripts/test_answer_prompt.py
"""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.answer_prompt import build_answer_messages, format_tool_results


def make_fake_mcp_result(payload: dict):
    """MCP CallToolResult를 흉내낸 가짜 객체 (content=[TextContent(text=JSON문자열)])."""
    text_block = SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(content=[text_block])


def test_empty_tool_results():
    result = format_tool_results([])
    print("빈 tool_results:", result)
    assert "조회된 데이터 없음" in result


def test_success_result():
    payload = {"success": True, "sql": "SELECT COUNT(*) ...", "row_count": 1, "rows": [{"count": 46}]}
    tool_results = [{"tool": "nl2sql_tool", "args": {}, "success": True, "result": make_fake_mcp_result(payload)}]
    text = format_tool_results(tool_results)
    print("\n정상 결과 포맷:\n", text)
    assert "nl2sql_tool" in text
    assert "46" in text


def test_failed_call():
    tool_results = [{"tool": "vector_search_tool", "args": {}, "success": False, "error": "타임아웃"}]
    text = format_tool_results(tool_results)
    print("\n실패 결과 포맷:\n", text)
    assert "실행 실패" in text
    assert "타임아웃" in text


def test_multiple_results():
    payload1 = {"success": True, "row_count": 2, "rows": [{"name": "Client-Q"}]}
    payload2 = {"success": True, "count": 1, "results": [{"name": "Product-S1"}]}
    tool_results = [
        {"tool": "nl2sql_tool", "args": {}, "success": True, "result": make_fake_mcp_result(payload1)},
        {"tool": "knowledge_graph_tool", "args": {}, "success": True, "result": make_fake_mcp_result(payload2)},
    ]
    text = format_tool_results(tool_results)
    print("\n복수 결과 포맷:\n", text)
    assert "nl2sql_tool" in text and "knowledge_graph_tool" in text


def test_build_answer_messages():
    payload = {"success": True, "row_count": 0, "rows": [], "note": "조건에 맞는 데이터가 없습니다."}
    tool_results = [{"tool": "nl2sql_tool", "args": {}, "success": True, "result": make_fake_mcp_result(payload)}]
    messages = build_answer_messages("2030년에 등록된 고객사는?", tool_results)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "2030년에 등록된 고객사는?" in messages[1]["content"]
    assert "데이터가 없습니다" in messages[1]["content"]
    print("\nmessages 구성 확인 완료")


def main():
    test_empty_tool_results()
    test_success_result()
    test_failed_call()
    test_multiple_results()
    test_build_answer_messages()
    print("\n✅ Answer 프롬프트 포맷팅 로직 전부 통과")


if __name__ == "__main__":
    main()
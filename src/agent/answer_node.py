"""
src/agent/answer_node.py

Answer Agent를 LangGraph 노드 함수로 구현. Router Agent와 같은 Ollama
인스턴스(ollama_client.call_chat, 환경변수 LLM_MODEL 기준 — 특정 모델에
종속되지 않음)를 재사용하되, 프롬프트만 answer_prompt.py의 것으로 교체한다.
이 노드는 도구를 호출하지 않고, 오직 자연어 답변 생성만 담당한다.
"""

from agent.answer_prompt import build_answer_messages
from agent.state import GraphState
from router.ollama_client import call_chat

FALLBACK_ANSWER = "죄송합니다, 답변을 생성하지 못했습니다. 다시 질문해 주세요."


def answer_agent_node(state: GraphState) -> dict:
    """
    LangGraph 노드: 원본 질문과 tool_results(있으면 RAG, 없으면 대화형)를
    바탕으로 최종 자연어 답변을 생성한다. 이 노드는 도구를 호출하지 않는다
    (tools 파라미터 없이 순수 텍스트 생성만 수행).

    :param state: GraphState (question 필수, tool_results는 없어도 됨)
    :return: state에 병합될 부분 딕셔너리 {"final_answer": str}
    """
    question = state["question"]
    tool_results = state.get("tool_results", [])

    messages = build_answer_messages(question, tool_results)

    message = call_chat(messages, tools=None, think=False)
    final_answer = (message.get("content") or "").strip()

    if not final_answer:
        final_answer = FALLBACK_ANSWER

    return {"final_answer": final_answer}
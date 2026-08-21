"""
src/agent/answer_node.py

Answer Agent를 LangGraph 노드 함수로 구현. Router Agent와 같은 Ollama
인스턴스를 재사용하되, 프롬프트만 answer_prompt.py의 것으로 교체한다.
이 노드는 도구를 호출하지 않고, 오직 자연어 답변 생성만 담당한다.

멀티턴 지원: state["messages"](대화 히스토리 전체)를 build_answer_messages에
넘긴다. Base/Router Agent는 여전히 question만 사용한다.

스트리밍 지원: router/ollama_client.call_chat(동기, 완성된 응답 한 번에
반환) 대신 stream_chat(비동기, 토큰 조각을 순차적으로 yield)을 사용한다.
토큰이 도착할 때마다 dispatch_custom_event("token", ...)으로 발행한다.

이 변경은 기존 호출 경로와 완전히 호환된다:
  - graph.ainvoke()로 실행되는 경우(run_agent, 기존 테스트 스크립트들):
    dispatch_custom_event는 구독자가 없으면 그냥 아무 일도 하지 않으므로
    영향이 없고, 노드는 기존과 동일하게 {"final_answer": str}를 반환한다.
  - graph.astream_events()로 실행되는 경우(신규 SSE 스트리밍 엔드포인트):
    "token" 커스텀 이벤트를 구독해 토큰 단위로 실시간 전달할 수 있다.
"""

from langchain_core.callbacks.manager import dispatch_custom_event

from agent.answer_prompt import build_answer_messages
from agent.state import GraphState
from router.ollama_client import stream_chat
from utils.logging_config import log_stage

FALLBACK_ANSWER = "죄송합니다, 답변을 생성하지 못했습니다. 다시 질문해 주세요."


async def answer_agent_node(state: GraphState) -> dict:
    """
    LangGraph 노드: 대화 히스토리 전체와 tool_results(있으면 RAG, 없으면
    대화형)를 바탕으로 최종 자연어 답변을 생성한다. 이 노드는 도구를
    호출하지 않는다.

    router_agent_node/tool_execution_node와 마찬가지로 비동기 노드다
    (stream_chat이 async generator이므로 async for로 순회해야 함) -
    graph.py의 "그래프 전체는 반드시 ainvoke/astream_events로 실행"
    주석과 일치한다 (기존에도 동기/비동기가 섞여 있었으므로 그래프
    실행 방식에는 변화가 없다).

    :param state: GraphState (messages 필수, tool_results는 없어도 됨)
    :return: state에 병합될 부분 딕셔너리 {"final_answer": str}
    """
    request_id = state["request_id"]
    messages = state.get("messages") or [{"role": "user", "content": state.get("question", "")}]
    tool_results = state.get("tool_results", [])

    answer_messages = build_answer_messages(messages, tool_results)

    with log_stage(
        "answer_agent", request_id, tool_results_count=len(tool_results)
    ) as log_result:
        chunks = []
        async for token in stream_chat(
            answer_messages, think=False, request_id=request_id, stage_hint="answer"
        ):
            chunks.append(token)
            dispatch_custom_event("token", {"content": token})

        final_answer = "".join(chunks).strip()

        if not final_answer:
            final_answer = FALLBACK_ANSWER

        log_result["final_answer_length"] = len(final_answer)

    return {"final_answer": final_answer}
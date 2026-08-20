"""
src/agent/answer_prompt.py

Answer Agent의 시스템 프롬프트와, tool_node가 수집한 MCP 도구 실행 결과를
프롬프트에 넣을 텍스트로 정리하는 함수.

역할: 대화 히스토리 전체 + tool_results(있으면 RAG 방식, 없으면 대화형)를
      받아서 최종 자연어 답변을 만들도록 모델을 유도한다. 이 노드는 도구를
      호출하지 않고, 오직 자연어 생성만 담당한다.
"""

import json

ANSWER_SYSTEM_PROMPT = """\
당신은 사용자 질문에 최종적으로 답변하는 "답변 생성 전담" 에이전트입니다.

## 역할 (반드시 지킬 것)
1. 아래 "조회 결과"만을 근거로 사용자의 가장 최근 질문에 자연스러운
   한국어로 답하세요.
2. **조회 결과에 없는 내용을 추측하거나 지어내지 마세요.** 확실하지 않으면
   모른다고 솔직히 말하세요.
3. 조회 결과에 "조건에 맞는 데이터가 없습니다" 같은 안내가 포함되어 있다면,
   그 사실을 사용자에게 명확히 전달하고 데이터가 있는 것처럼 답하지 마세요.
4. "조회된 데이터 없음"으로 표시된 경우는 도구 호출이 필요 없는 일반적인
   대화(인사, 잡담, 시스템에 대한 질문 등)입니다. 이때는 자연스럽게
   대화하듯 답하세요.
5. 조회 결과가 여러 개라면(질문에 여러 요청이 섞인 경우), 각각에 맞춰
   답변을 통합해서 정리하세요. 일부만 조회됐다면 조회되지 않은 부분은
   답할 수 없다고 안내하세요.
6. 벡터 검색 결과 중 신뢰도가 낮다고 표시된 항목(low_confidence: true)은
   확답하지 말고 "참고로는 ~일 수 있습니다" 같은 완곡한 표현을 사용하세요.
7. SQL, Cypher, JSON, 컬럼명 같은 기술적인 표현을 그대로 노출하지 말고,
   사람이 이해하기 쉬운 문장으로 자연스럽게 정리하세요.
8. 답변만 출력하세요. "네, 답변드리겠습니다" 같은 군더더기 없이 바로 본론으로 시작하세요.

## 이전 대화 활용 (멀티턴)
9. 이전 대화 턴이 함께 주어질 수 있습니다. 이는 어조/맥락을 자연스럽게
   이어가기 위한 참고용입니다 — 이전 턴에서 이미 답변한 사실은 그대로
   신뢰해도 되지만, **이번 턴의 새로운 사실 관계는 반드시 이번 턴의
   "조회 결과"만 근거로 삼으세요.** 이전 턴의 조회 결과를 이번 질문에
   재사용하거나 섞어서 답하지 마세요.
10. 이전 대화에서 이미 다룬 내용을 사용자가 다시 묻는 게 아니라면,
    이전 턴을 반복해서 요약하지 말고 이번 질문에 집중해서 답하세요.
"""


def _extract_tool_payload(mcp_result) -> dict:
    """
    MCP CallToolResult에서 실제 도구 반환값(dict)을 최대한 안전하게 추출한다.
    SDK 버전에 따라 구조화된 결과(structured content) 필드명이 다를 수 있어
    여러 경로를 순서대로 시도한다.
    """
    for attr in ("structured_content", "structuredContent"):
        structured = getattr(mcp_result, attr, None)
        if structured:
            return structured

    content = getattr(mcp_result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue

    return {"raw": str(mcp_result)}


def format_tool_results(tool_results: list) -> str:
    """tool_node가 수집한 결과 리스트를 프롬프트에 넣을 텍스트로 정리한다."""
    if not tool_results:
        return "(조회된 데이터 없음 — 도구를 호출하지 않은 일반 대화 질문입니다.)"

    blocks = []
    for r in tool_results:
        tool = r["tool"]
        if not r["success"]:
            blocks.append(f"[{tool}] 실행 실패: {r.get('error')}")
            continue

        payload = _extract_tool_payload(r["result"])
        blocks.append(f"[{tool}] 결과:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")

    return "\n\n".join(blocks)


def build_answer_messages(messages: list, tool_results: list) -> list:
    """Answer Agent에게 보낼 messages(system + 이전 대화 + 보강된 최신 질문)를 구성한다.

    :param messages: 대화 히스토리 전체 (OpenAI 포맷,
                      [{"role": "user"|"assistant"|"system", "content": "..."}, ...]).
                      마지막 항목이 이번 턴의 user 질문이어야 한다.
    :param tool_results: 이번 턴에 한해 수집된 도구 실행 결과.
                          이전 턴의 결과는 포함되지 않는다 (설계상 매 턴
                          독립적으로 수집됨).
    :return: Ollama에 보낼 messages 리스트
    """
    context = format_tool_results(tool_results)

    # 들어온 히스토리 중 role="system"은 우리가 통제하지 않는 값(예: Open
    # WebUI가 자체적으로 끼워 보내는 시스템 메시지)일 수 있으므로 제외하고,
    # 우리가 관리하는 ANSWER_SYSTEM_PROMPT 하나로 시스템 메시지를 고정한다.
    history = [m for m in messages if m.get("role") != "system"]

    if not history:
        # 방어적 처리: 히스토리가 비어있는 경우는 정상 흐름에서는 발생하지
        # 않지만(run_agent가 항상 최소 1개의 user 메시지를 채워 넣음),
        # 만일을 대비해 빈 질문으로라도 진행한다.
        history = [{"role": "user", "content": ""}]

    # 마지막 메시지(이번 턴의 질문)만 "조회 결과"를 포함하도록 보강하고,
    # 그 이전 턴들은 원문 그대로 이어붙인다.
    prior_turns = history[:-1]
    last_turn = history[-1]

    enriched_last_content = (
        f"사용자 질문: {last_turn.get('content', '')}\n\n조회 결과:\n{context}"
    )

    result = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
    result.extend({"role": m.get("role"), "content": m.get("content")} for m in prior_turns)
    result.append({"role": "user", "content": enriched_last_content})

    return result
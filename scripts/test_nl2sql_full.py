"""
scripts/test_nl2sql_full.py

data/questions.json의 nl2sql 타입 질문 10개 전체를 파이프라인
(생성→파싱→검증→실행→포맷)으로 돌려서 결과를 확인한다.

각 단계에서 발생 가능한 예외를 개별적으로 잡아서, 하나가 실패해도
나머지 9개는 계속 진행하고 마지막에 요약을 보여준다.

사용법:
    docker compose run --rm app python scripts/test_nl2sql_full.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.execute import SQLExecutionError, execute_query
from nl2sql.format import format_query_result
from nl2sql.generate import SQLGenerationError, generate_sql
from nl2sql.parse import SQLParseError, extract_sql
from nl2sql.safety import SQLSafetyError, validate_select_only

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")


def run_one(question: str) -> dict:
    """파이프라인 전체를 실행하고, 어느 단계에서든 실패하면 실패 정보를 담아 반환한다."""
    try:
        raw = generate_sql(question)
    except SQLGenerationError as e:
        return {"stage": "generate", "error": str(e)}

    try:
        sql = extract_sql(raw)
    except SQLParseError as e:
        return {"stage": "parse", "error": str(e), "raw": raw}

    if sql == "NO_QUERY":
        return {"stage": "no_query", "sql": sql}

    try:
        validated = validate_select_only(sql)
    except SQLSafetyError as e:
        return {"stage": "safety", "error": str(e), "sql": sql}

    try:
        columns, rows = execute_query(validated)
    except SQLExecutionError as e:
        return {"stage": "execute", "error": str(e), "sql": validated}

    formatted = format_query_result(columns, rows)
    return {"stage": "success", "sql": validated, "result": formatted}


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        all_questions = json.load(f)

    nl2sql_questions = [q for q in all_questions if q["tool"] == "nl2sql"]
    print(f"==> nl2sql 타입 질문 {len(nl2sql_questions)}개 테스트\n")

    success_count = 0
    failures = []

    for i, q in enumerate(nl2sql_questions, start=1):
        question = q["q"]
        hint = q["hint"]

        print(f"[{i}/{len(nl2sql_questions)}] 질문: {question}")
        print(f"       힌트: {hint}")

        outcome = run_one(question)

        if outcome["stage"] == "success":
            success_count += 1
            r = outcome["result"]
            print(f"       SQL: {outcome['sql']}")
            if r["is_empty"]:
                print("       결과: (0행) — 데이터 없음")
            else:
                preview = r["rows"][:3]
                more = f" 외 {r['row_count'] - 3}건" if r["row_count"] > 3 else ""
                print(f"       결과 ({r['row_count']}행): {preview}{more}")
        else:
            failures.append((question, hint, outcome))
            print(f"       ⚠️  실패 (단계: {outcome['stage']}): {outcome.get('error', outcome)}")

        print()

    print("=" * 70)
    print(f"결과: {success_count}/{len(nl2sql_questions)}개 파이프라인 성공 (SQL 실행까지 도달)")
    print("(주의: '성공'은 SQL이 에러 없이 실행됐다는 뜻이며, 힌트와 의미적으로")
    print(" 일치하는지는 위 출력을 보고 수작업으로 판정해야 합니다.)")

    if failures:
        print(f"\n실패한 {len(failures)}건 — few-shot/스키마 설명 보강이 필요한 후보:")
        for question, hint, outcome in failures:
            print(f"  - [{outcome['stage']}] {question} (힌트: {hint})")
            print(f"    사유: {outcome.get('error', outcome)}")


if __name__ == "__main__":
    main()
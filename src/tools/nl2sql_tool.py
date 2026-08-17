"""
src/tools/nl2sql_tool.py

질문(자연어 문자열)을 받아 SQL 생성→파싱→안전 검증→실행→결과 포맷까지
전체 파이프라인을 수행하는 최종 도구 함수. Phase 11에서 MCPServer에
그대로 등록될 인터페이스.
"""

from nl2sql.execute import SQLExecutionError, execute_query
from nl2sql.format import format_query_result
from nl2sql.generate import SQLGenerationError, generate_sql
from nl2sql.parse import NO_QUERY_MARKER, SQLParseError, extract_sql
from nl2sql.safety import SQLSafetyError, validate_select_only


def nl2sql_tool(question: str) -> dict:
    """
    자연어 질문을 SQL로 변환해서 정형 데이터베이스(8개 테이블)를 조회한다.

    :param question: 사용자의 자연어 질문
    :return: {
        "question": 원본 질문,
        "success": 파이프라인이 끝까지 정상 처리됐는지 여부,
        "sql": 실행된 SQL (실패 시 None 또는 실패 직전까지 확보된 SQL),
        "columns": 컬럼명 리스트 (실패 시 빈 리스트),
        "rows": 결과 레코드 리스트 (실패 시 빈 리스트),
        "row_count": 전체 결과 행 수,
        "is_empty": 결과가 0행인지 여부,
        "note": Answer Agent에게 전달할 안내 문구
                (빈 결과 안내, 답할 수 없음 안내, 실패 사유 등)
    }
    """
    # 1. SQL 생성
    try:
        raw = generate_sql(question)
    except SQLGenerationError as e:
        return _error_result(question, "SQL 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.", str(e))

    # 2. 파싱
    try:
        sql = extract_sql(raw)
    except SQLParseError as e:
        return _error_result(
            question, "질문을 SQL로 변환하지 못했습니다.", str(e)
        )

    # 2-1. 모델이 "이 질문엔 답할 수 없다"고 판단한 경우
    if sql == NO_QUERY_MARKER:
        return {
            "question": question,
            "success": True,
            "sql": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "is_empty": True,
            "note": "이 질문은 현재 데이터베이스 스키마로는 답변할 수 없는 내용입니다.",
        }

    # 3. 안전 검증
    try:
        validated_sql = validate_select_only(sql)
    except SQLSafetyError as e:
        return _error_result(
            question,
            "생성된 쿼리가 안전 기준을 통과하지 못해 실행할 수 없습니다.",
            str(e),
            sql=sql,
        )

    # 4. 실행
    try:
        columns, rows = execute_query(validated_sql)
    except SQLExecutionError as e:
        return _error_result(
            question, "쿼리 실행 중 오류가 발생했습니다.", str(e), sql=validated_sql
        )

    # 5. 결과 포맷
    formatted = format_query_result(columns, rows)

    return {
        "question": question,
        "success": True,
        "sql": validated_sql,
        "columns": formatted["columns"],
        "rows": formatted["rows"],
        "row_count": formatted["row_count"],
        "is_empty": formatted["is_empty"],
        "note": formatted.get("note"),
    }


def _error_result(question: str, note: str, error_detail: str, sql: str = None) -> dict:
    """실패 케이스를 일관된 형식으로 감싼다."""
    return {
        "question": question,
        "success": False,
        "sql": sql,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "is_empty": True,
        "note": f"{note} (상세: {error_detail})",
    }
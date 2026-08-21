"""
공통 구조화 로깅 유틸.

- 모든 단계 시작/종료를 JSON Lines(logs/app.jsonl)로 기록한다.
- request_id로 하나의 질문이 거친 모든 단계를 grep/조인할 수 있다.
- scripts/analyze_logs.py 가 이 파일 형식(event/stage/duration_sec)을 그대로 읽는다.
"""

import json
import logging
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

LOG_DIR = Path("/app/logs")  # docker-compose에서 app/mcp-server 양쪽에 동일 경로로 마운트
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _setup_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))  # 한 줄 = JSON 1개
        logger.addHandler(file_handler)

        # docker compose logs 로도 실시간으로 보이게 콘솔에도 남김
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

        logger.propagate = False
    return logger


app_logger = _setup_logger("brain_bridge", "app.jsonl")


def new_request_id() -> str:
    """FastAPI 어댑터 진입 시점에 1회 발급해서 GraphState에 담아 전 노드로 흘려보낸다."""
    return uuid.uuid4().hex[:12]


@contextmanager
def log_stage(stage: str, request_id: str, **extra: Any):
    """
    사용 예:
        with log_stage("kg_db_execution", request_id, cypher_query=q) as result:
            raw = await execute_cypher(q)
            result["raw_result_count"] = len(raw)

    - 진입 시 event="start" 레코드 1줄
    - 종료 시 event="end" 레코드 1줄 (duration_sec, status, result 딕셔너리 내용 포함)
    - 예외 발생 시 status="error"로 기록하고 그대로 재전파(raise)한다.
    """
    start = time.time()
    _write({"request_id": request_id, "stage": stage, "event": "start", "ts": start, **extra})

    result_holder: Dict[str, Any] = {}
    status = "success"
    try:
        yield result_holder
    except Exception as e:
        status = "error"
        result_holder["error"] = str(e)
        raise
    finally:
        end = time.time()
        record = {
            "request_id": request_id,
            "stage": stage,
            "event": "end",
            "status": status,
            "duration_sec": round(end - start, 3),
            **result_holder,
        }
        _write(record)


def _write(record: Dict[str, Any]) -> None:
    app_logger.info(json.dumps(record, ensure_ascii=False))
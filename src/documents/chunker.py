"""
src/documents/chunker.py

마크다운 문서를 헤더(##, ###) 기준으로 섹션 단위 청크로 분리한다.

관찰된 문서 구조 (4개 타입 실제 확인):
- incident_report / meeting_note: "# 제목" → "## 섹션" 구조
- technical_doc: "## 설치 절차" 아래에 "### 1단계" 식으로 한 단계 더 중첩되는 경우 있음
- proposal: "# 제목" → "## N. 섹션명" 구조 (h3 없음)

그래서 h2와 h3를 둘 다 청크 경계로 삼되, h3가 있는 경우 상위 h2 제목을
breadcrumb(title_path)에 포함시켜 맥락을 보존한다.
"""

import re
from dataclasses import dataclass
from typing import List

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)

MAX_CHARS = 800  # 상한: 이보다 길면 문단 단위로 추가 분할
MIN_CHARS = 10  # 하한: 이보다 짧으면 직전 청크에 병합


@dataclass
class Chunk:
    title_path: str  # 예: "장애 보고서 > 기본 정보" 또는 "설치 가이드 > 설치 절차 > 1단계: 의존성 설치"
    content: str


def _split_if_too_long(text: str, max_chars: int) -> List[str]:
    """MAX_CHARS를 넘는 본문은 문단(빈 줄 기준) 단위로 추가 분할한다."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts, buf = [], ""
    for para in paragraphs:
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) > max_chars and buf:
            parts.append(buf)
            buf = para
        else:
            buf = candidate
    if buf:
        parts.append(buf)
    return parts


def chunk_markdown(text: str) -> List[Chunk]:
    """
    마크다운 텍스트를 h1(문서 제목) + h2/h3(섹션) 기준으로 청크 리스트로 분리한다.
    h1은 청크로 만들지 않고 title_path의 접두어로만 사용한다.
    """
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        stripped = text.strip()
        return [Chunk(title_path="", content=stripped)] if stripped else []

    doc_title = ""
    h2_title = ""
    raw_chunks: List[Chunk] = []

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if level == 1:
            doc_title = title
            continue

        if level == 2:
            h2_title = title
            path = " > ".join(p for p in [doc_title, h2_title] if p)
        else:  # level == 3
            path = " > ".join(p for p in [doc_title, h2_title, title] if p)

        if not body:
            # 하위 헤더(h3)가 실제 내용을 담고 있는 빈 상위 섹션(h2)은 건너뜀
            continue

        for part in _split_if_too_long(body, MAX_CHARS):
            raw_chunks.append(Chunk(title_path=path, content=part))

    # 하한(MIN_CHARS) 미만인 너무 짧은 청크는 직전 청크에 병합
    merged: List[Chunk] = []
    for c in raw_chunks:
        if merged and len(c.content) < MIN_CHARS:
            prev = merged[-1]
            merged[-1] = Chunk(title_path=prev.title_path, content=f"{prev.content}\n{c.content}")
        else:
            merged.append(c)

    return merged
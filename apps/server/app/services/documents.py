"""Document ingestion helpers: extract text, clean, chunk, detect sections."""
from __future__ import annotations

import io
import re
from typing import List

from pypdf import PdfReader

from ..config import settings


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return clean_text("\n\n".join(parts))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # de-hyphenate words split across line breaks
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> List[str]:
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    if not text:
        return []

    paragraphs = re.split(r"\n\n+", text)
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > chunk_size:
                words = para.split(" ")
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= chunk_size:
                        current = f"{current} {word}" if current else word
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = word
            else:
                current = para
    if current:
        chunks.append(current.strip())

    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append(f"{tail}\n\n{chunks[i]}")
        return overlapped
    return chunks


def detect_section(text: str, chunk_index: int, total_chunks: int) -> str:
    head = text.lower()[:500]
    if chunk_index == 0:
        return "opening"
    for marker, section in [
        ("introduction", "introduction"),
        ("background", "background"),
        ("related work", "related_work"),
        ("method", "methods"),
        ("approach", "methods"),
        ("experiment", "results"),
        ("evaluation", "results"),
        ("results", "results"),
        ("conclusion", "conclusion"),
        ("discussion", "conclusion"),
        ("reference", "references"),
    ]:
        if marker in head:
            return section
    ratio = chunk_index / max(total_chunks, 1)
    if ratio < 0.2:
        return "introduction"
    if ratio < 0.6:
        return "body"
    if ratio < 0.85:
        return "results"
    return "conclusion"

"""Graph-QA endpoint — ask natural-language questions about a bucket's graph."""
from __future__ import annotations

from fastapi import APIRouter

from ..agents import graph_qa
from ..schemas import QARequest, QAResponse

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("", response_model=QAResponse)
def ask(body: QARequest):
    result = graph_qa.answer_question(body.bucket_id, body.question)
    return QAResponse(
        question=result["question"],
        answer=result["answer"],
        context=result.get("context", []),
    )

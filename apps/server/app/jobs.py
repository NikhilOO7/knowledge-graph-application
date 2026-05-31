"""Simple in-process background job runner for document processing.

For production this would be a Redis/BullMQ-style queue with separate workers;
here a thread pool keeps the pipeline off the request thread while remaining
dependency-free. Job status is mirrored onto the document row in Postgres so
the UI can poll either the job or the document.
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from .db.postgres import DocumentRow, get_session
from .pipeline.graph import run_pipeline

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(job_id: str, document_id: str) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "document_id": document_id,
            "bucket_id": None,
            "bucket_action": None,
            "error": None,
            "stats": {},
        }


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _set_doc_status(document_id: str, status: str, progress: int, error: str | None = None,
                    bucket_id: str | None = None) -> None:
    session = get_session()
    try:
        doc = session.get(DocumentRow, document_id)
        if doc:
            doc.processing_status = status
            doc.processing_progress = progress
            if error is not None:
                doc.processing_error = error
            if bucket_id:
                doc.bucket_id = bucket_id
            session.commit()
    finally:
        session.close()


def enqueue(job_id: str, document_id: str, forced_bucket_id: Optional[str]) -> None:
    create_job(job_id, document_id)
    _executor.submit(_run, job_id, document_id, forced_bucket_id)


def _run(job_id: str, document_id: str, forced_bucket_id: Optional[str]) -> None:
    def progress(stage: str, percent: int) -> None:
        _update(job_id, status="processing", stage=stage, progress=percent)
        _set_doc_status(document_id, stage, percent)

    _update(job_id, status="processing", stage="starting", progress=1)
    try:
        final = run_pipeline(document_id, forced_bucket_id, progress)
        if final.get("error"):
            raise RuntimeError(final["error"])
        _update(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            bucket_id=final.get("bucket_id"),
            bucket_action=final.get("bucket_action"),
            stats=final.get("stats", {}),
        )
        _set_doc_status(document_id, "completed", 100, bucket_id=final.get("bucket_id"))
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _update(job_id, status="failed", stage="failed", error=str(exc))
        _set_doc_status(document_id, "failed", 0, error=str(exc))

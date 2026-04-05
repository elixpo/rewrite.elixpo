"""Job polling and report download endpoints."""

import os
import tempfile
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas import JobResponse, JobStatus
from app.api.jobs import get_job
from app.detection.ensemble import detect_heuristic_only
from app.document.structure import Document
from app.document.report import generate_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/job/{job_id}", response_model=JobResponse)
def poll_job(job_id: str):
    """Poll job status and progress."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired")

    return JobResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0),
        paragraphs=job.get("paragraphs", []),
        result=job.get("result"),
        error=job.get("error"),
    )


@router.get("/report/{job_id}/pdf")
def download_report(job_id: str):
    """Generate and download a PDF report for a completed job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired")

    if job["status"] != JobStatus.completed:
        raise HTTPException(409, f"Job is {job['status'].value}, not completed")

    result = job.get("result")
    if not result or "rewritten" not in result:
        raise HTTPException(500, "Job result missing rewritten text")

    rewritten_text = result["rewritten"]
    doc = Document.from_text(rewritten_text)

    # Score each paragraph for the report
    seg_scores = []
    for para in doc.paragraphs:
        if len(para.text.strip()) < 30:
            seg_scores.append({"score": 0, "verdict": "Too short", "text": para.text})
        else:
            r = detect_heuristic_only(para.text)
            seg_scores.append({"score": r["score"], "verdict": r["verdict"], "text": para.text})

    overall = detect_heuristic_only(rewritten_text)

    # Generate PDF to temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()

    try:
        generate_report(
            document=doc,
            segment_scores=seg_scores,
            overall_score=overall["score"],
            overall_verdict=overall["verdict"],
            features=overall.get("features", {}),
            output_path=tmp.name,
        )
        return FileResponse(
            tmp.name,
            media_type="application/pdf",
            filename=f"rewrite_report_{job_id}.pdf",
        )
    except Exception as e:
        os.unlink(tmp.name)
        raise HTTPException(500, f"Report generation failed: {e}")

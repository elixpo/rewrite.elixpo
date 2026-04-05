"""Paraphrase endpoints — returns job ID for async polling."""

import os
import tempfile
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.api.schemas import (
    ParaphraseTextRequest,
    ParaphraseResponse,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    Domain,
    Intensity,
)
from app.api.jobs import create_job, update_job, run_in_background
from app.detection.ensemble import detect_heuristic_only
from app.detection.segment import segment_by_paragraphs
from app.paraphrase.prompts import build_messages, build_detection_feedback
from app.paraphrase.postprocess import postprocess, normalize_length, global_postprocess
from app.core.llm import chat
from app.core.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["paraphrase"])


def _run_paraphrase(job_id: str, text: str, intensity: str, domain: str):
    """Background task: paraphrase all flagged paragraphs."""
    threshold = 20
    max_attempts = 5
    model = DEFAULT_MODEL

    paragraphs = segment_by_paragraphs(text)
    if not paragraphs:
        return {"rewritten": text, "original_score": 0, "final_score": 0, "paragraphs": []}

    # Score each paragraph
    scores = []
    para_progress = []
    for i, para in enumerate(paragraphs):
        if len(para.strip()) < 30:
            scores.append({"score": 0, "verdict": "Too short", "features": {}})
        else:
            scores.append(detect_heuristic_only(para))
        para_progress.append({
            "index": i,
            "original_score": round(scores[i]["score"], 1),
            "current_score": None,
            "status": "pending",
        })

    update_job(job_id, paragraphs=para_progress)

    flagged = [(i, scores[i]) for i in range(len(paragraphs)) if scores[i]["score"] > threshold]
    total_steps = len(flagged)
    if total_steps == 0:
        overall = detect_heuristic_only(text)
        return {
            "rewritten": text,
            "original_score": round(overall["score"], 1),
            "final_score": round(overall["score"], 1),
            "paragraphs": para_progress,
        }

    rewritten_paragraphs = list(paragraphs)
    temp_schedule = [0.6, 0.7, 0.8, 0.85, 0.9]
    intensity_schedule = ["aggressive"] * 5

    for step, (para_idx, score_info) in enumerate(flagged):
        para_text = paragraphs[para_idx]
        original_score = score_info["score"]

        # Update progress
        para_progress[para_idx]["status"] = "rewriting"
        progress_pct = (step / total_steps) * 100
        update_job(job_id, paragraphs=para_progress, progress=progress_pct)

        # Build context
        context_parts = []
        if para_idx > 0:
            context_parts.append(f"[Previous]: {paragraphs[para_idx - 1][:200]}")
        if para_idx < len(paragraphs) - 1:
            context_parts.append(f"[Next]: {paragraphs[para_idx + 1][:200]}")
        context = "\n".join(context_parts)

        best_text = para_text
        best_score = original_score

        for attempt in range(max_attempts):
            attempt_intensity = intensity_schedule[min(attempt, len(intensity_schedule) - 1)]
            temp = temp_schedule[min(attempt, len(temp_schedule) - 1)]

            try:
                # Detection feedback
                source = best_text if attempt > 0 else para_text
                fb_result = detect_heuristic_only(source)
                feedback = build_detection_feedback(source, fb_result["features"])

                messages = build_messages(
                    para_text, intensity=attempt_intensity,
                    domain=domain, context=context,
                    feedback=feedback,
                )
                rewritten = chat(messages=messages, model=model, temperature=temp, seed=-1)
                rewritten = postprocess(rewritten)
                rewritten = normalize_length(rewritten, para_text)

                new_result = detect_heuristic_only(rewritten)
                new_score = new_result["score"]

                if new_score < best_score:
                    best_text = rewritten
                    best_score = new_score

                if best_score <= threshold:
                    break
            except Exception as e:
                logger.warning("Paraphrase attempt %d failed for para %d: %s", attempt, para_idx, e)
                break

        rewritten_paragraphs[para_idx] = best_text
        para_progress[para_idx]["current_score"] = round(best_score, 1)
        para_progress[para_idx]["status"] = "done"
        update_job(job_id, paragraphs=para_progress)

    # Global post-processing
    rewritten_paragraphs = global_postprocess(rewritten_paragraphs, paragraphs)

    final_text = "\n\n".join(rewritten_paragraphs)
    overall_before = detect_heuristic_only(text)
    overall_after = detect_heuristic_only(final_text)

    # Fill in scores for unflagged paragraphs
    for i in range(len(para_progress)):
        if para_progress[i]["status"] == "pending":
            para_progress[i]["current_score"] = para_progress[i]["original_score"]
            para_progress[i]["status"] = "done"

    return {
        "rewritten": final_text,
        "original_score": round(overall_before["score"], 1),
        "final_score": round(overall_after["score"], 1),
        "paragraphs": para_progress,
    }


@router.post("/paraphrase", response_model=ParaphraseResponse)
def paraphrase_text(req: ParaphraseTextRequest):
    """Start a paraphrase job. Returns job_id for polling via GET /api/job/{id}."""
    text = req.text.strip()
    job_id = create_job()
    run_in_background(_run_paraphrase, job_id, text, req.intensity.value, req.domain.value)
    return ParaphraseResponse(job_id=job_id)


@router.post("/paraphrase/file", response_model=ParaphraseResponse)
async def paraphrase_file(
    file: UploadFile = File(...),
    intensity: Intensity = Form(Intensity.aggressive),
    domain: Domain = Form(Domain.general),
):
    """Start a paraphrase job from an uploaded file."""
    if not file.filename:
        raise HTTPException(400, "Filename required")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type '{ext}'")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max: {MAX_FILE_SIZE // 1024 // 1024} MB")

    # Parse the file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from app.document.parser import parse_file
        doc = parse_file(tmp_path)
        text = doc.text
    finally:
        os.unlink(tmp_path)

    if len(text.strip()) < 50:
        raise HTTPException(422, "Extracted text too short (< 50 characters)")

    job_id = create_job()
    run_in_background(_run_paraphrase, job_id, text[:100_000], intensity.value, domain.value)
    return ParaphraseResponse(job_id=job_id)

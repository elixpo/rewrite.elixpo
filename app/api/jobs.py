"""Background job runner for long-running tasks (paraphrase, full pipeline)."""

import logging
import threading
import time
import uuid

from app.api.schemas import JobStatus

logger = logging.getLogger(__name__)

# In-memory job store — upgrade to Redis for multi-worker deployments
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

# Job TTL: auto-cleanup completed jobs after 1 hour
JOB_TTL = 3600


def create_job() -> str:
    """Create a new pending job and return its ID."""
    job_id = uuid.uuid4().hex[:16]
    with _lock:
        _jobs[job_id] = {
            "status": JobStatus.pending,
            "progress": 0,
            "paragraphs": [],
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    return job_id


def get_job(job_id: str) -> dict | None:
    """Get job state. Returns None if not found or expired."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        # Check TTL for completed/failed jobs
        if job["status"] in (JobStatus.completed, JobStatus.failed):
            if time.time() - job["created_at"] > JOB_TTL:
                del _jobs[job_id]
                return None
        return dict(job)


def update_job(job_id: str, **kwargs):
    """Update job fields."""
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def run_in_background(fn, job_id: str, *args, **kwargs):
    """Run a function in a background thread, updating job status on completion/failure."""

    def _wrapper():
        update_job(job_id, status=JobStatus.running)
        try:
            result = fn(job_id, *args, **kwargs)
            update_job(job_id, status=JobStatus.completed, result=result, progress=100)
        except Exception as e:
            logger.exception("Job %s failed: %s", job_id, e)
            update_job(job_id, status=JobStatus.failed, error=str(e))

    thread = threading.Thread(target=_wrapper, daemon=True)
    thread.start()
    return thread


def cleanup_expired():
    """Remove expired jobs. Call periodically."""
    now = time.time()
    with _lock:
        expired = [
            jid for jid, job in _jobs.items()
            if job["status"] in (JobStatus.completed, JobStatus.failed)
            and now - job["created_at"] > JOB_TTL
        ]
        for jid in expired:
            del _jobs[jid]
    return len(expired)

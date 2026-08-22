"""Development-compatible durable worker entry point for Synth Now.

The FastAPI app uses BackgroundTasks in local tests. This module provides a separate worker process
for container deployments: it polls the database for queued audio jobs and uses a conditional state
transition to avoid duplicate processing. Replace polling with a durable queue adapter when traffic
or latency warrants it; the worker must retain the same state and safety boundary.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

from prometheus_client import start_http_server
from sqlalchemy import func, select, update

from app.audio_worker import process_audio_job
from app.db import AudioAnalysisJob, SessionLocal
from app.metrics import AUDIO_JOB_QUEUE_DEPTH

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("synthnow.worker")
POLL_INTERVAL_SECONDS = float(os.getenv("SYNTH_NOW_WORKER_POLL_INTERVAL_SECONDS", "1.0"))
WORKER_METRICS_PORT = int(os.getenv("SYNTH_NOW_WORKER_METRICS_PORT", "9100"))


def refresh_audio_queue_depth() -> int:
    db = SessionLocal()
    try:
        depth = int(db.scalar(select(func.count()).select_from(AudioAnalysisJob).where(AudioAnalysisJob.status == "queued")) or 0)
        AUDIO_JOB_QUEUE_DEPTH.set(depth)
        return depth
    finally:
        db.close()


def claim_one_queued_audio_job() -> str | None:
    """Claims one queued job by conditional update; returns no job when the queue is empty."""
    db = SessionLocal()
    try:
        candidate = db.scalar(
            select(AudioAnalysisJob.id)
            .where(AudioAnalysisJob.status == "queued")
            .order_by(AudioAnalysisJob.created_at.asc())
            .limit(1)
        )
        if candidate is None:
            return None
        claimed = db.execute(
            update(AudioAnalysisJob)
            .where(AudioAnalysisJob.id == candidate, AudioAnalysisJob.status == "queued")
            .values(status="running")
        )
        db.commit()
        return candidate if claimed.rowcount == 1 else None
    finally:
        db.close()


def run_forever() -> None:
    # Internal-only metrics endpoint. Expose it through a ClusterIP service and scrape via a
    # monitoring namespace; do not add it to public ingress.
    start_http_server(WORKER_METRICS_PORT)
    log.info("Synth Now worker started", extra={"poll_interval_seconds": POLL_INTERVAL_SECONDS, "metrics_port": WORKER_METRICS_PORT})
    while True:
        refresh_audio_queue_depth()
        job_id = claim_one_queued_audio_job()
        if not job_id:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            log.info("Processing audio job", extra={"job_id": job_id})
            process_audio_job(job_id)
        except Exception:
            log.exception("Audio job failed", extra={"job_id": job_id})


if __name__ == "__main__":
    run_forever()

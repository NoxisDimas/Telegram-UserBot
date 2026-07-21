"""
Redis queue consumer — blocking pop loop with retry and DLQ.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session
from app.core.redis import pop_from_queue, push_to_queue
from app.models.job import Job, JobStatus
from app.workers.tasks import dispatch_task

logger = logging.getLogger(__name__)

QUEUE_NAME = "job_queue"
DLQ_NAME = "job_dlq"


async def consume_loop() -> None:
    """Main consumer loop — blocks on BRPOP and dispatches tasks.

    Implements:
    - Exponential backoff on retries
    - Dead-letter queue for permanent failures
    - Job status tracking in PostgreSQL
    """
    settings = get_settings()
    logger.info(
        "Worker consumer started (concurrency=%d, max_retries=%d)",
        settings.WORKER_CONCURRENCY, settings.MAX_RETRIES,
    )

    while True:
        try:
            payload = await pop_from_queue(QUEUE_NAME, timeout=5)
            if payload is None:
                continue

            job_id = payload.get("job_id")
            job_type = payload.get("job_type", "unknown")
            job_data = payload.get("data", {})
            retries = payload.get("retries", 0)

            logger.info(
                "Processing job %s (type=%s, retry=%d)",
                job_id, job_type, retries,
            )

            # Update job status in DB
            if job_id:
                await _update_job_status(job_id, JobStatus.PROCESSING)

            try:
                await dispatch_task(job_type, job_data)

                # Mark as completed
                if job_id:
                    await _update_job_status(job_id, JobStatus.COMPLETED)
                logger.info("Job %s completed.", job_id)

            except Exception as exc:
                logger.error("Job %s failed: %s", job_id, exc)

                if retries < settings.MAX_RETRIES:
                    # Retry with exponential backoff
                    delay = settings.RETRY_BASE_DELAY * (2 ** retries)
                    logger.info(
                        "Retrying job %s in %.1fs (attempt %d/%d)",
                        job_id, delay, retries + 1, settings.MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)

                    payload["retries"] = retries + 1
                    await push_to_queue(QUEUE_NAME, payload)

                    if job_id:
                        await _update_job_status(
                            job_id, JobStatus.FAILED,
                            error=str(exc),
                            retries=retries + 1,
                        )
                else:
                    # Move to DLQ
                    logger.error(
                        "Job %s moved to DLQ after %d retries.",
                        job_id, retries,
                    )
                    await push_to_queue(DLQ_NAME, payload)

                    if job_id:
                        await _update_job_status(
                            job_id, JobStatus.DEAD, error=str(exc),
                        )

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled.")
            break
        except Exception as exc:
            logger.error("Consumer loop error: %s", exc)
            await asyncio.sleep(5)


async def _update_job_status(
    job_id: str,
    status: JobStatus,
    error: str | None = None,
    retries: int | None = None,
) -> None:
    """Update a job's status in the database."""
    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, TypeError):
        return

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Job).where(Job.job_id == job_uuid)
            )
            job = result.scalar_one_or_none()
            if job is None:
                return

            job.status = status
            if error is not None:
                job.error = error
            if retries is not None:
                job.retries = retries
            session.add(job)
    except Exception as exc:
        logger.error("Failed to update job %s status: %s", job_id, exc)


async def enqueue_job(
    job_type: str,
    data: dict,
    max_retries: int | None = None,
) -> str:
    """Create a job in the database and push to the Redis queue.

    Returns the job_id (UUID string).
    """
    settings = get_settings()
    _max_retries = max_retries if max_retries is not None else settings.MAX_RETRIES

    job = Job(
        job_type=job_type,
        payload=data,
        status=JobStatus.PENDING,
        max_retries=_max_retries,
    )

    async with get_session() as session:
        session.add(job)
        await session.flush()
        job_id = str(job.job_id)

    # Push to Redis
    await push_to_queue(QUEUE_NAME, {
        "job_id": job_id,
        "job_type": job_type,
        "data": data,
        "retries": 0,
    })

    logger.info("Enqueued job %s (type=%s)", job_id, job_type)
    return job_id

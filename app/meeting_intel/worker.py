"""Background worker.

Polls the database for queued meetings, claims one atomically and runs the
processing pipeline.  Multiple worker replicas are safe to run concurrently
(Postgres ``FOR UPDATE SKIP LOCKED``).  Also runs a periodic retention sweep
that deletes source audio older than ``AUDIO_RETENTION_DAYS``.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import get_settings
from .db import init_db, session_scope
from .engine.pipeline import process_meeting
from .models import Meeting, MeetingStatus

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("meeting_intel.worker")

_running = True


def _stop(signum, frame):  # noqa: ANN001
    global _running
    logger.info("Received signal %s, shutting down after current job...", signum)
    _running = False


def claim_next_meeting() -> str | None:
    """Atomically claim the oldest queued meeting; return its id or None."""
    with session_scope() as session:
        stmt = (
            select(Meeting)
            .where(Meeting.status == MeetingStatus.QUEUED.value)
            .order_by(Meeting.created_at.asc())
            .limit(1)
        )
        if session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        meeting = session.execute(stmt).scalars().first()
        if meeting is None:
            return None
        meeting.status = MeetingStatus.PROCESSING.value
        meeting.progress = "queued"
        return meeting.id


def retention_sweep() -> int:
    """Delete source audio older than the retention window. Returns count."""
    settings = get_settings()
    if settings.audio_retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audio_retention_days)
    removed = 0
    with session_scope() as session:
        stmt = select(Meeting).where(
            Meeting.audio_path.is_not(None), Meeting.created_at < cutoff
        )
        for meeting in session.execute(stmt).scalars():
            path = meeting.audio_path
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    removed += 1
                meeting.audio_path = None
            except OSError as exc:
                logger.warning("Could not delete %s: %s", path, exc)
    if removed:
        logger.info("Retention sweep removed %d audio file(s)", removed)
    return removed


def run() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info("Worker started. Whisper=%s Ollama=%s", settings.whisper_model, settings.ollama_model)
    last_sweep = 0.0
    sweep_interval = 3600.0  # hourly

    while _running:
        try:
            meeting_id = claim_next_meeting()
            if meeting_id:
                logger.info("Processing meeting %s", meeting_id)
                process_meeting(meeting_id, settings)
            else:
                time.sleep(settings.worker_poll_interval_seconds)

            now = time.monotonic()
            if now - last_sweep > sweep_interval:
                retention_sweep()
                last_sweep = now
        except Exception:  # never let the loop die
            logger.exception("Worker loop error; continuing")
            time.sleep(settings.worker_poll_interval_seconds)

    logger.info("Worker stopped.")


if __name__ == "__main__":
    run()

"""Watch-folder ingestion.

Any recording dropped into ``WATCH_FOLDER_PATH`` is registered as a new meeting
and queued for processing.  This is how Jitsi/Jibri (or any recorder) feeds the
platform today: point Jibri's finalize step at this folder.  See
docs/JITSI-INTEGRATION.md.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

from .config import get_settings
from .db import init_db, session_scope
from .models import Meeting, MeetingStatus

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("meeting_intel.ingest")

_running = True


def _is_stable(path: Path, wait: float = 2.0) -> bool:
    """Heuristic: file size unchanged over ``wait`` seconds -> done writing."""
    try:
        size1 = path.stat().st_size
        time.sleep(wait)
        return path.stat().st_size == size1 and size1 > 0
    except OSError:
        return False


def ingest_file(path: Path, source: str = "watch") -> str | None:
    """Register a recording file as a queued meeting. Returns meeting id."""
    settings = get_settings()
    ext = path.suffix.lower()
    if ext not in settings.allowed_audio_extensions:
        logger.info("Ignoring non-audio file: %s", path.name)
        return None

    settings.ensure_dirs()
    with session_scope() as session:
        meeting = Meeting(title=path.stem, source=source, status=MeetingStatus.QUEUED.value)
        session.add(meeting)
        session.flush()
        meeting_id = meeting.id
        dest = settings.audio_dir / f"{meeting_id}{ext}"
        shutil.move(str(path), str(dest))
        meeting.audio_path = str(dest)
    logger.info("Ingested %s as meeting %s", path.name, meeting_id)
    return meeting_id


def run() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    folder = Path(settings.watch_folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    logger.info("Watching folder: %s", folder)

    seen: set[str] = set()
    while _running:
        try:
            for entry in sorted(folder.iterdir()):
                if not entry.is_file() or entry.name.startswith("."):
                    continue
                if entry.name in seen:
                    continue
                if _is_stable(entry):
                    if ingest_file(entry):
                        seen.discard(entry.name)
                    else:
                        seen.add(entry.name)  # skip unsupported next time
        except Exception:
            logger.exception("Ingest loop error; continuing")
        time.sleep(settings.watch_folder_poll_seconds)


if __name__ == "__main__":
    run()

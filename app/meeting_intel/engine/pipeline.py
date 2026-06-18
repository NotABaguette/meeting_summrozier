"""End-to-end processing: audio file -> transcript + summary."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import Settings, get_settings
from . import diarize as diarize_mod
from . import merge, summarize, transcribe

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str], None]


@dataclass
class PipelineResult:
    segments: list[dict] = field(default_factory=list)
    transcript_text: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    language: str | None = None
    duration: float | None = None
    speakers: list[str] = field(default_factory=list)


def run_pipeline(
    audio_path: str,
    settings: Settings | None = None,
    progress: ProgressCb | None = None,
) -> PipelineResult:
    """Run the full local pipeline on an audio file and return the result."""
    settings = settings or get_settings()

    def report(stage: str) -> None:
        logger.info("[pipeline] %s", stage)
        if progress:
            progress(stage)

    report("transcribing")
    tr = transcribe.transcribe(audio_path, settings)
    segments = tr.segments

    if settings.diarization_enabled and segments:
        report("diarizing")
        turns = diarize_mod.diarize(audio_path, settings)
        if turns:
            segments = merge.assign_speakers(segments, turns)

    transcript_text = merge.build_transcript_text(segments)
    speakers = merge.list_speakers(segments)

    report("summarizing")
    summary: dict[str, Any] = {}
    if transcript_text.strip():
        try:
            summary = summarize.Summarizer(settings).summarize(transcript_text, speakers or None)
        except Exception as exc:
            logger.exception("Summarization failed: %s", exc)
            summary = {
                "executive_summary": (
                    "Transcription succeeded but summarization failed: "
                    f"{exc}. The full transcript is available."
                ),
                "key_points": [],
                "decisions": [],
                "action_items": [],
                "topics": [],
                "next_steps": [],
                "journal": [],
                "participants": speakers,
            }
    report("done")

    return PipelineResult(
        segments=segments,
        transcript_text=transcript_text,
        summary=summary,
        language=tr.language,
        duration=tr.duration,
        speakers=speakers,
    )


def process_meeting(meeting_id: str, settings: Settings | None = None) -> None:
    """Load a meeting from the DB, process it, and persist the results."""
    from ..db import session_scope
    from ..models import Meeting, MeetingStatus

    settings = settings or get_settings()

    with session_scope() as session:
        meeting = session.get(Meeting, meeting_id)
        if meeting is None:
            logger.error("Meeting %s not found", meeting_id)
            return
        if not meeting.audio_path:
            meeting.status = MeetingStatus.FAILED.value
            meeting.error = "No audio file associated with this meeting."
            return
        meeting.status = MeetingStatus.PROCESSING.value
        meeting.attempts += 1
        meeting.error = None
        audio_path = meeting.audio_path

    def progress(stage: str) -> None:
        with session_scope() as s:
            m = s.get(Meeting, meeting_id)
            if m:
                m.progress = stage

    try:
        result = run_pipeline(audio_path, settings, progress=progress)
    except Exception as exc:
        logger.exception("Pipeline failed for meeting %s", meeting_id)
        with session_scope() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting:
                meeting.status = MeetingStatus.FAILED.value
                meeting.error = str(exc)
                meeting.progress = None
        return

    with session_scope() as session:
        meeting = session.get(Meeting, meeting_id)
        if meeting is None:
            return
        meeting.segments = result.segments
        meeting.transcript_text = result.transcript_text
        meeting.summary = result.summary
        meeting.language = result.language
        meeting.duration_seconds = result.duration
        if result.summary.get("title") and (
            not meeting.title or meeting.title in ("Untitled meeting", "")
        ):
            meeting.title = result.summary["title"]
        meeting.status = MeetingStatus.COMPLETED.value
        meeting.progress = "done"

"""End-to-end pipeline test with the heavy model calls mocked out."""

from meeting_intel.engine.transcribe import TranscriptionResult


class _FakeSummarizer:
    def __init__(self, settings=None):
        pass

    def summarize(self, transcript, participants=None):
        return {
            "title": "Generated Title",
            "executive_summary": "It worked.",
            "key_points": ["kp"],
            "decisions": [],
            "action_items": [],
            "topics": [],
            "next_steps": [],
            "journal": [],
            "participants": participants or [],
        }


def _fake_transcribe(audio_path, settings=None):
    return TranscriptionResult(
        segments=[
            {"start": 0.0, "end": 2.0, "text": "سلام", "speaker": None},
            {"start": 2.0, "end": 4.0, "text": "خداحافظ", "speaker": None},
        ],
        language="fa",
        duration=4.0,
    )


def test_process_meeting_success(monkeypatch, tmp_path):
    monkeypatch.setattr("meeting_intel.engine.transcribe.transcribe", _fake_transcribe)
    monkeypatch.setattr("meeting_intel.engine.summarize.Summarizer", _FakeSummarizer)

    from meeting_intel.db import session_scope
    from meeting_intel.engine.pipeline import process_meeting
    from meeting_intel.models import Meeting, MeetingStatus

    audio = tmp_path / "m.wav"
    audio.write_bytes(b"fake")

    with session_scope() as s:
        m = Meeting(title="Untitled meeting", audio_path=str(audio))
        s.add(m)
        s.flush()
        mid = m.id

    process_meeting(mid)

    with session_scope() as s:
        m = s.get(Meeting, mid)
        assert m.status == MeetingStatus.COMPLETED.value
        assert m.language == "fa"
        assert m.duration_seconds == 4.0
        assert "سلام" in m.transcript_text
        assert m.summary["executive_summary"] == "It worked."
        # Title auto-filled from summary because it was "Untitled meeting".
        assert m.title == "Generated Title"


def test_process_meeting_handles_failure(monkeypatch, tmp_path):
    def boom(audio_path, settings=None):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("meeting_intel.engine.transcribe.transcribe", boom)

    from meeting_intel.db import session_scope
    from meeting_intel.engine.pipeline import process_meeting
    from meeting_intel.models import Meeting, MeetingStatus

    audio = tmp_path / "m.wav"
    audio.write_bytes(b"fake")
    with session_scope() as s:
        m = Meeting(title="X", audio_path=str(audio))
        s.add(m)
        s.flush()
        mid = m.id

    process_meeting(mid)

    with session_scope() as s:
        m = s.get(Meeting, mid)
        assert m.status == MeetingStatus.FAILED.value
        assert "model exploded" in m.error

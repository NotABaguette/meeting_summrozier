from meeting_intel.engine import artifacts

SUMMARY = {
    "title": "Weekly Sync",
    "executive_summary": "We discussed the roadmap.",
    "key_points": ["Point A", "Point B"],
    "decisions": ["Ship on Friday"],
    "action_items": [
        {"owner": "Ali", "task": "Prepare deck", "due": "Tomorrow"},
        {"owner": None, "task": "Email client", "due": None},
    ],
    "topics": ["Roadmap"],
    "next_steps": ["Follow up"],
    "journal": [{"heading": "Intro", "details": "Greetings and agenda."}],
    "participants": ["Speaker 1", "Speaker 2"],
}

MEETING = {
    "title": "Weekly Sync",
    "source": "upload",
    "duration_seconds": 125.0,
    "created_at": "2026-06-18T10:00:00",
}


def test_render_minutes_contains_all_sections():
    md = artifacts.render_minutes_markdown(MEETING, SUMMARY)
    for heading in [
        "# Weekly Sync",
        "## Executive summary",
        "## Key points",
        "## Decisions",
        "## Action items",
        "## Topics discussed",
        "## Next steps",
        "## Meeting journal",
    ]:
        assert heading in md
    assert "Prepare deck" in md
    assert "Ali" in md
    assert "no data left your network" in md.lower()


def test_render_action_items_table():
    table = artifacts.render_action_items(SUMMARY["action_items"])
    assert "| Owner | Action | Due |" in table
    assert "| Ali | Prepare deck | Tomorrow |" in table
    # Missing owner/due fall back to em dash.
    assert "| — | Email client | — |" in table


def test_render_action_items_empty():
    assert "None" in artifacts.render_action_items([])


def test_render_minutes_handles_empty_summary():
    md = artifacts.render_minutes_markdown(MEETING, {})
    assert "## Executive summary" in md
    assert "_Not available._" in md or "Not available" in md


def test_render_transcript_markdown():
    segments = [
        {"start": 0, "end": 2, "speaker": "Speaker 1", "text": "hello"},
        {"start": 2, "end": 4, "speaker": "Speaker 2", "text": "hi"},
    ]
    md = artifacts.render_transcript_markdown(MEETING, segments)
    assert "**[00:00:00] Speaker 1:** hello" in md
    assert "Speaker 2" in md


def test_render_transcript_markdown_empty():
    md = artifacts.render_transcript_markdown(MEETING, [])
    assert "No speech detected" in md

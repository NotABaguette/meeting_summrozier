"""Render stored results into downloadable Markdown documents.

Pure functions -> easy to unit test and reuse from the API/CLI.
"""

from __future__ import annotations

from typing import Any

from .merge import build_transcript_text, format_timestamp, group_segments


def _bullets(items: list[Any]) -> str:
    lines = []
    for item in items or []:
        text = str(item).strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if lines else "_None recorded._"


def render_action_items(action_items: list[dict]) -> str:
    if not action_items:
        return "_None recorded._"
    rows = ["| Owner | Action | Due |", "| --- | --- | --- |"]
    for item in action_items:
        owner = (item.get("owner") or "—") if isinstance(item, dict) else "—"
        task = (item.get("task") or "") if isinstance(item, dict) else str(item)
        due = (item.get("due") or "—") if isinstance(item, dict) else "—"
        rows.append(f"| {owner} | {task} | {due} |")
    return "\n".join(rows)


def render_journal(journal: list[dict]) -> str:
    if not journal:
        return "_No journal generated._"
    parts = []
    for entry in journal:
        if isinstance(entry, dict):
            heading = entry.get("heading") or entry.get("title") or "Section"
            details = entry.get("details") or entry.get("summary") or ""
            parts.append(f"### {heading}\n\n{details}".rstrip())
        else:
            parts.append(f"- {entry}")
    return "\n\n".join(parts)


def render_minutes_markdown(meeting: dict, summary: dict) -> str:
    """Render the human-facing 'meeting minutes / journal' document."""
    summary = summary or {}
    title = summary.get("title") or meeting.get("title") or "Meeting"
    duration = meeting.get("duration_seconds")
    duration_str = format_timestamp(duration) if duration else "unknown"
    participants = summary.get("participants") or []

    sections = [
        f"# {title}",
        "",
        f"- **Date:** {meeting.get('created_at', 'unknown')}",
        f"- **Duration:** {duration_str}",
        f"- **Source:** {meeting.get('source', 'unknown')}",
        f"- **Participants/Speakers:** {', '.join(participants) if participants else 'unknown'}",
        "",
        "## Executive summary",
        "",
        summary.get("executive_summary") or "_Not available._",
        "",
        "## Key points",
        "",
        _bullets(summary.get("key_points")),
        "",
        "## Decisions",
        "",
        _bullets(summary.get("decisions")),
        "",
        "## Action items",
        "",
        render_action_items(summary.get("action_items") or []),
        "",
        "## Topics discussed",
        "",
        _bullets(summary.get("topics")),
        "",
        "## Next steps",
        "",
        _bullets(summary.get("next_steps")),
        "",
        "## Meeting journal",
        "",
        render_journal(summary.get("journal") or []),
        "",
        "---",
        "_Generated locally by the self-hosted Meeting Intelligence platform. "
        "No data left your network._",
    ]
    return "\n".join(sections).strip() + "\n"


def render_transcript_markdown(meeting: dict, segments: list[dict]) -> str:
    """Render a readable transcript document with timestamps and speakers."""
    title = meeting.get("title") or "Meeting"
    header = [f"# Transcript — {title}", "", f"_Source: {meeting.get('source', 'unknown')}_", ""]
    blocks = group_segments(segments or [])
    body = []
    for block in blocks:
        ts = format_timestamp(block.get("start"))
        speaker = block.get("speaker")
        if speaker:
            body.append(f"**[{ts}] {speaker}:** {block['text']}")
        else:
            body.append(f"**[{ts}]** {block['text']}")
        body.append("")
    if not body:
        body = ["_No speech detected._"]
    return "\n".join(header + body).strip() + "\n"


def plain_transcript(segments: list[dict]) -> str:
    """Convenience wrapper for the plain-text transcript."""
    return build_transcript_text(segments or [])

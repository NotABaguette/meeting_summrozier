"""Pure helpers to turn raw ASR + diarization output into a clean transcript.

These functions have no model dependencies, so they are fully unit-tested.
"""

from __future__ import annotations

from typing import Any

Segment = dict[str, Any]
Turn = dict[str, Any]


def format_timestamp(seconds: float | None) -> str:
    """Format seconds as HH:MM:SS (clamped at 0)."""
    if seconds is None or seconds < 0:
        seconds = 0
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Length of the overlap between two intervals (0 if disjoint)."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(segments: list[Segment], turns: list[Turn]) -> list[Segment]:
    """Attach a ``speaker`` label to each ASR segment.

    Each segment is assigned the diarization turn it overlaps the most.  If a
    segment overlaps nothing (e.g. diarization missed it), it inherits the
    speaker of the nearest turn by midpoint distance.  Returns new dicts.
    """
    if not turns:
        return [dict(seg) for seg in segments]

    result: list[Segment] = []
    for seg in segments:
        s_start = float(seg.get("start", 0.0))
        s_end = float(seg.get("end", s_start))

        best_speaker = None
        best_overlap = 0.0
        for turn in turns:
            ov = _overlap(s_start, s_end, float(turn["start"]), float(turn["end"]))
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = turn["speaker"]

        if best_speaker is None:
            # Fall back to the nearest turn by midpoint distance.
            seg_mid = (s_start + s_end) / 2
            best_speaker = min(
                turns,
                key=lambda t: abs(((float(t["start"]) + float(t["end"])) / 2) - seg_mid),
            )["speaker"]

        new_seg = dict(seg)
        new_seg["speaker"] = best_speaker
        result.append(new_seg)
    return result


def group_segments(segments: list[Segment]) -> list[Segment]:
    """Merge consecutive segments from the same speaker into readable blocks."""
    blocks: list[Segment] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = seg.get("speaker")
        if blocks and blocks[-1].get("speaker") == speaker:
            prev = blocks[-1]
            prev["end"] = seg.get("end", prev.get("end"))
            prev["text"] = (prev["text"] + " " + text).strip()
        else:
            blocks.append(
                {
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "speaker": speaker,
                    "text": text,
                }
            )
    return blocks


def build_transcript_text(segments: list[Segment]) -> str:
    """Render a plain-text transcript: ``[HH:MM:SS] Speaker: text`` per line."""
    lines: list[str] = []
    for block in group_segments(segments):
        ts = format_timestamp(block.get("start"))
        speaker = block.get("speaker")
        prefix = f"[{ts}] {speaker}: " if speaker else f"[{ts}] "
        lines.append(prefix + block["text"])
    return "\n".join(lines)


def list_speakers(segments: list[Segment]) -> list[str]:
    """Return the distinct speaker labels in first-appearance order."""
    seen: list[str] = []
    for seg in segments:
        sp = seg.get("speaker")
        if sp and sp not in seen:
            seen.append(sp)
    return seen

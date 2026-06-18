"""Pure helper logic for the Jitsi bot (no I/O) — unit tested."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


def normalize_room_url(server_base: str, room: str) -> str:
    """Build the full meeting URL from a server base + room name or full URL."""
    room = (room or "").strip()
    if room.startswith("http://") or room.startswith("https://"):
        return room
    base = (server_base or "").rstrip("/")
    return f"{base}/{room.lstrip('/')}"


def safe_room_name(room: str) -> str:
    """Extract a filesystem-safe room name from a URL or raw name."""
    name = (room or "meeting").strip()
    # Strip scheme/host if a URL was given.
    name = re.sub(r"^https?://[^/]+/", "", name)
    name = name.split("?")[0].split("#")[0].strip("/")
    name = name.split("/")[-1] or "meeting"
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name[:80] or "meeting"


def output_filename(room: str, when: datetime) -> str:
    """Recording filename, e.g. ``standup-20260618-101500.ogg``."""
    return f"{safe_room_name(room)}-{when:%Y%m%d-%H%M%S}.ogg"


@dataclass(frozen=True)
class StopPolicy:
    # Hard cap so a forgotten bot never records forever.
    max_seconds: int = 4 * 3600
    # Leave once everyone else has left for this long.
    leave_after_alone_seconds: int = 30
    # If nobody ever joins within this window, give up.
    join_grace_seconds: int = 300


def decide_stop(
    remote_count: int,
    seconds_alone: float,
    elapsed: float,
    ever_had_participants: bool,
    policy: StopPolicy,
) -> tuple[bool, str]:
    """Decide whether the bot should stop recording, and why.

    Returns ``(should_stop, reason)``.
    """
    if elapsed >= policy.max_seconds:
        return True, "max_duration"
    if not ever_had_participants:
        if elapsed >= policy.join_grace_seconds:
            return True, "nobody_joined"
        return False, ""
    if remote_count <= 0 and seconds_alone >= policy.leave_after_alone_seconds:
        return True, "everyone_left"
    return False, ""

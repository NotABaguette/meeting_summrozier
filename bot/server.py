"""Control API for the Jitsi bot.

POST /join {"room": "..."} makes the bot join that meeting, record it, and submit
it to the platform automatically. This is what a Jitsi moderator button (or the
platform, or a simple curl) calls.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import suppress

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_bot_settings
from .recorder import record_meeting

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("jitsi_bot.server")

app = FastAPI(title="Jitsi Meeting Bot")

_origins = os.environ.get("BOT_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session registry. A meeting bot is ephemeral by nature.
_SESSIONS: dict[str, dict] = {}


class JoinRequest(BaseModel):
    room: str
    max_minutes: int | None = None


async def _run(session_id: str, room: str) -> None:
    settings = get_bot_settings()
    sess = _SESSIONS[session_id]
    stop_event: asyncio.Event = sess["stop_event"]

    def on_status(state: str, extra: dict) -> None:
        sess["state"] = state
        sess["detail"] = extra

    try:
        result = await record_meeting(room, settings, stop_event, on_status)
        sess["state"] = "completed"
        sess["result"] = result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bot session %s failed", session_id)
        sess["state"] = "failed"
        sess["error"] = str(exc)


@app.post("/join")
async def join(req: JoinRequest):
    if not req.room.strip():
        raise HTTPException(status_code=400, detail="room is required")
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = {
        "id": session_id,
        "room": req.room,
        "state": "starting",
        "stop_event": asyncio.Event(),
        "result": None,
        "error": None,
        "detail": {},
    }
    asyncio.create_task(_run(session_id, req.room))
    logger.info("Started bot session %s for room %s", session_id, req.room)
    return {"session_id": session_id, "state": "starting"}


def _public(sess: dict) -> dict:
    return {k: v for k, v in sess.items() if k != "stop_event"}


@app.get("/sessions")
async def sessions():
    return [_public(s) for s in _SESSIONS.values()]


@app.get("/sessions/{session_id}")
async def session(session_id: str):
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="unknown session")
    return _public(sess)


@app.post("/sessions/{session_id}/stop")
async def stop(session_id: str):
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="unknown session")
    with suppress(Exception):
        sess["stop_event"].set()
    return {"session_id": session_id, "state": "stopping"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "active": sum(1 for s in _SESSIONS.values() if s["state"] not in ("completed", "failed"))}

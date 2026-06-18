"""FastAPI application: JSON API + server-rendered web UI."""

from __future__ import annotations

import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from .. import __version__
from ..config import get_settings
from ..db import init_db, session_scope
from ..engine.artifacts import (
    plain_transcript,
    render_minutes_markdown,
    render_transcript_markdown,
)
from ..models import Meeting, MeetingStatus

logger = logging.getLogger("meeting_intel.api")

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    logger.info("API started (v%s)", __version__)
    yield


app = FastAPI(title="Self-hosted Meeting Intelligence", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Allow the optional "button in your existing Jitsi" page (which lives on the
# Jitsi origin) to call /api/jitsi/join. Scoped to your Jitsi origin only.
_cors_origins = [get_settings().jitsi_server_url] if get_settings().jitsi_server_url else []
if _cors_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_meeting_or_404(session, meeting_id: str) -> Meeting:
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in get_settings().allowed_audio_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: "
            + ", ".join(get_settings().allowed_audio_extensions),
        )
    return ext


# --------------------------------------------------------------------------- #
# Web UI
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with session_scope() as session:
        meetings = (
            session.execute(select(Meeting).order_by(Meeting.created_at.desc()).limit(200))
            .scalars()
            .all()
        )
        rows = [m.to_dict(include_results=False) for m in meetings]
    return templates.TemplateResponse(
        request, "index.html", {"meetings": rows, "settings": get_settings()}
    )


@app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
def meeting_page(request: Request, meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        data = meeting.to_dict()
    return templates.TemplateResponse(
        request, "detail.html", {"m": data, "settings": get_settings()}
    )


# --------------------------------------------------------------------------- #
# Jitsi: host a meeting with a built-in "Record & Summarize" button
# --------------------------------------------------------------------------- #
class JitsiJoinRequest(BaseModel):
    room: str


def _jitsi_room_url(settings, room: str) -> str:
    room = (room or "").strip()
    if room.startswith("http://") or room.startswith("https://"):
        return room
    base = settings.jitsi_server_url.rstrip("/")
    return f"{base}/{room}" if base else room


@app.get("/meet", response_class=HTMLResponse)
def meet_launcher(request: Request):
    return templates.TemplateResponse(
        request, "meet_launcher.html", {"settings": get_settings()}
    )


@app.get("/meet/{room}", response_class=HTMLResponse)
def meet_room(request: Request, room: str):
    settings = get_settings()
    if not settings.jitsi_enabled:
        raise HTTPException(
            status_code=503,
            detail="Jitsi is not configured. Set JITSI_SERVER_URL to enable hosted meetings.",
        )
    return templates.TemplateResponse(
        request,
        "meet.html",
        {
            "settings": settings,
            "room": room,
            "jitsi_domain": settings.jitsi_domain,
            "button_label": settings.jitsi_button_label,
        },
    )


@app.post("/api/jitsi/join")
def jitsi_join(req: JitsiJoinRequest):
    """Called by the in-meeting button. Tells the bot to join + record."""
    settings = get_settings()
    room_url = _jitsi_room_url(settings, req.room)
    if not room_url:
        raise HTTPException(status_code=400, detail="room is required")
    import httpx

    try:
        resp = httpx.post(f"{settings.bot_base_url}/join", json={"room": room_url}, timeout=15)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the recording bot. Is the 'jitsi' profile running? ({exc})",
        )
    return resp.json()


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
_ALLOWED_SOURCES = {"upload", "jitsi", "meet", "voip", "watch"}


@app.post("/api/meetings")
async def create_meeting(
    file: UploadFile,
    title: str = Form(default=""),
    source: str = Form(default="upload"),
):
    settings = get_settings()
    settings.ensure_dirs()
    ext = _validate_extension(file.filename or "audio")
    source = source if source in _ALLOWED_SOURCES else "upload"

    with session_scope() as session:
        meeting = Meeting(
            title=(title.strip() or Path(file.filename or "Untitled meeting").stem),
            source=source,
            status=MeetingStatus.QUEUED.value,
        )
        session.add(meeting)
        session.flush()  # assign id without committing -> worker can't see it yet
        meeting_id = meeting.id
        dest = settings.audio_dir / f"{meeting_id}{ext}"
        try:
            with open(dest, "wb") as out:
                shutil.copyfileobj(file.file, out, length=1024 * 1024)
        finally:
            await file.close()
        meeting.audio_path = str(dest)
        status = meeting.status
    return {"id": meeting_id, "status": status}


@app.get("/api/meetings")
def list_meetings():
    with session_scope() as session:
        meetings = (
            session.execute(select(Meeting).order_by(Meeting.created_at.desc()).limit(500))
            .scalars()
            .all()
        )
        return [m.to_dict(include_results=False) for m in meetings]


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        return meeting.to_dict()


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        if meeting.audio_path and os.path.exists(meeting.audio_path):
            try:
                os.remove(meeting.audio_path)
            except OSError as exc:
                logger.warning("Could not delete audio: %s", exc)
        session.delete(meeting)
    return {"deleted": meeting_id}


@app.get("/api/meetings/{meeting_id}/transcript.md", response_class=PlainTextResponse)
def download_transcript_md(meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        md = render_transcript_markdown(meeting.to_dict(), meeting.segments or [])
    return _as_download(md, f"transcript-{meeting_id}.md", "text/markdown")


@app.get("/api/meetings/{meeting_id}/transcript.txt", response_class=PlainTextResponse)
def download_transcript_txt(meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        txt = meeting.transcript_text or plain_transcript(meeting.segments or [])
    return _as_download(txt, f"transcript-{meeting_id}.txt", "text/plain")


@app.get("/api/meetings/{meeting_id}/minutes.md", response_class=PlainTextResponse)
def download_minutes_md(meeting_id: str):
    with session_scope() as session:
        meeting = _get_meeting_or_404(session, meeting_id)
        md = render_minutes_markdown(meeting.to_dict(), meeting.summary or {})
    return _as_download(md, f"minutes-{meeting_id}.md", "text/markdown")


def _as_download(content: str, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/healthz")
def healthz():
    settings = get_settings()
    db_ok = False
    ollama_ok = False
    details: dict = {}
    try:
        with session_scope() as session:
            session.execute(select(Meeting).limit(1))
            db_ok = True
    except Exception as exc:
        details["database_error"] = str(exc)
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except Exception as exc:
        details["ollama_error"] = str(exc)
    status = "ok" if (db_ok and ollama_ok) else "degraded"
    return {"status": status, "database": db_ok, "ollama": ollama_ok, "details": details}

"""Headless Jitsi join + audio recording.

Strategy (robust + version-stable): a headless Chromium joins the conference and
plays all audio into a PulseAudio virtual sink; ``ffmpeg`` records that sink's
monitor to an Opus file. This captures the full mixed meeting audio regardless
of Jitsi's internal APIs. Speaker labels are then added by the platform's
optional diarization step.

This module performs real I/O (browser, ffmpeg) and is meant to run inside the
bot container. Heavy deps (Playwright) are imported lazily so the control
server and unit tests don't require them.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .config import BotSettings
from .helpers import decide_stop, normalize_room_url, output_filename

logger = logging.getLogger("jitsi_bot.recorder")

# JS that returns the number of OTHER participants in the call.
_COUNT_JS = """
() => {
  try {
    if (window.APP && APP.conference) {
      const c = APP.conference;
      if (typeof c.membersCount === 'number') return Math.max(0, c.membersCount - 1);
      if (typeof c.listMembers === 'function') return c.listMembers().length;
      if (c._room && typeof c._room.getParticipantCount === 'function')
        return Math.max(0, c._room.getParticipantCount() - 1);
    }
  } catch (e) {}
  // DOM fallback: count remote video tiles.
  const sel = '.remote-videos .videocontainer, .filmstrip .remote-videos > span, span.remotevideocontainer';
  return document.querySelectorAll(sel).length;
}
"""


def build_join_url(settings: BotSettings, room: str) -> str:
    """Full URL with config overrides to auto-join muted, no prejoin page."""
    url = normalize_room_url(settings.jitsi_server_url, room)
    if settings.jwt:
        url += ("&" if "?" in url else "?") + f"jwt={quote(settings.jwt)}"
    name = quote(f'"{settings.display_name}"')
    overrides = (
        "config.prejoinPageEnabled=false"
        "&config.prejoinConfig.enabled=false"
        "&config.startWithAudioMuted=true"
        "&config.startWithVideoMuted=true"
        "&config.disableInitialGUM=true"
        f"&userInfo.displayName={name}"
    )
    return f"{url}#{overrides}"


async def _start_ffmpeg(source: str, outfile: Path) -> asyncio.subprocess.Process:
    outfile.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
        "-f", "pulse", "-i", source,
        "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k",
        str(outfile),
    ]
    logger.info("Recording with: %s", " ".join(cmd))
    return await asyncio.create_subprocess_exec(*cmd)


async def _stop_ffmpeg(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.terminate()  # ffmpeg flushes and finalizes on SIGTERM
        await asyncio.wait_for(proc.wait(), timeout=15)
    except (asyncio.TimeoutError, ProcessLookupError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


async def _submit(settings: BotSettings, outfile: Path, room: str) -> str:
    """Hand the recording to the platform. Returns a description of where."""
    if settings.submit_mode == "folder":
        dest = Path(settings.output_dir) / outfile.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(outfile), str(dest))
        return f"folder:{dest}"

    # Default: upload to the platform API.
    import httpx  # lazy

    title = f"Jitsi — {room}"
    async with httpx.AsyncClient(timeout=300) as client:
        with open(outfile, "rb") as fh:
            files = {"file": (outfile.name, fh, "audio/ogg")}
            data = {"title": title, "source": "jitsi"}
            resp = await client.post(
                f"{settings.platform_api_url}/api/meetings", files=files, data=data
            )
    resp.raise_for_status()
    outfile.unlink(missing_ok=True)
    return f"api:{resp.json().get('id')}"


async def record_meeting(
    room: str,
    settings: BotSettings,
    stop_event: asyncio.Event | None = None,
    on_status=None,
) -> dict:
    """Join ``room``, record until the meeting ends, and submit the audio."""
    from playwright.async_api import async_playwright  # lazy import

    stop_event = stop_event or asyncio.Event()
    policy = settings.stop_policy()
    started = datetime.now()
    outfile = Path(settings.work_dir) / output_filename(room, started)
    join_url = build_join_url(settings, room)

    def status(state: str, **extra):
        logger.info("[%s] %s %s", room, state, extra or "")
        if on_status:
            on_status(state, extra)

    status("starting", url=join_url.split("#")[0])
    ffmpeg = await _start_ffmpeg(settings.audio_source, outfile)

    ever_had = False
    alone_since: float | None = None
    reason = "unknown"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=settings.headless,
            args=[
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-gpu",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(permissions=["microphone", "camera"])
        page = await context.new_page()
        try:
            await page.goto(join_url, wait_until="domcontentloaded", timeout=60000)
            status("joined")
            while True:
                elapsed = (datetime.now() - started).total_seconds()
                try:
                    remote = int(await page.evaluate(_COUNT_JS))
                except Exception:
                    remote = 0
                if remote > 0:
                    ever_had = True
                    alone_since = None
                elif alone_since is None:
                    alone_since = elapsed
                seconds_alone = 0.0 if alone_since is None else elapsed - alone_since

                if stop_event.is_set():
                    reason = "api_stop"
                    break
                stop, why = decide_stop(remote, seconds_alone, elapsed, ever_had, policy)
                if stop:
                    reason = why
                    break
                await asyncio.sleep(settings.poll_seconds)
        finally:
            status("leaving", reason=reason)
            await _stop_ffmpeg(ffmpeg)
            try:
                await context.close()
                await browser.close()
            except Exception:
                pass

    where = await _submit(settings, outfile, room)
    status("submitted", where=where, reason=reason)
    return {"room": room, "reason": reason, "submitted": where, "duration_seconds": (datetime.now() - started).total_seconds()}

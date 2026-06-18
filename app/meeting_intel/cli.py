"""Command-line interface for headless processing and diagnostics.

Examples
--------
    python -m meeting_intel.cli process meeting.wav --out ./out
    python -m meeting_intel.cli health
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import get_settings
from .engine.artifacts import render_minutes_markdown, render_transcript_markdown
from .engine.pipeline import run_pipeline


def cmd_process(args: argparse.Namespace) -> int:
    settings = get_settings()
    audio = Path(args.file)
    if not audio.exists():
        print(f"File not found: {audio}", file=sys.stderr)
        return 2

    print(f"Processing {audio} ...", file=sys.stderr)
    result = run_pipeline(str(audio), settings, progress=lambda s: print(f"  -> {s}", file=sys.stderr))

    meeting_meta = {
        "title": args.title or audio.stem,
        "source": "cli",
        "duration_seconds": result.duration,
        "created_at": "",
    }
    transcript_md = render_transcript_markdown(meeting_meta, result.segments)
    minutes_md = render_minutes_markdown(meeting_meta, result.summary)

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "transcript.md").write_text(transcript_md, encoding="utf-8")
        (out / "minutes.md").write_text(minutes_md, encoding="utf-8")
        (out / "result.json").write_text(
            json.dumps(
                {
                    "language": result.language,
                    "duration": result.duration,
                    "speakers": result.speakers,
                    "segments": result.segments,
                    "summary": result.summary,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Wrote transcript.md, minutes.md, result.json to {out}", file=sys.stderr)
    else:
        print("\n===== MINUTES =====\n")
        print(minutes_md)
        print("\n===== TRANSCRIPT =====\n")
        print(transcript_md)
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    settings = get_settings()
    print(f"Whisper model : {settings.whisper_model} ({settings.whisper_device})")
    print(f"Ollama model  : {settings.ollama_model} @ {settings.ollama_base_url}")
    print(f"Diarization   : {'on' if settings.diarization_enabled else 'off'}")
    ok = True
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=4)
        print(f"Ollama reachable: {r.status_code == 200}")
        ok = ok and r.status_code == 200
    except Exception as exc:
        print(f"Ollama reachable: False ({exc})")
        ok = False
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meeting_intel", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_proc = sub.add_parser("process", help="Transcribe + summarize an audio file")
    p_proc.add_argument("file", help="Path to an audio/video file")
    p_proc.add_argument("--out", help="Output directory (writes .md/.json files)")
    p_proc.add_argument("--title", help="Meeting title")
    p_proc.set_defaults(func=cmd_process)

    p_health = sub.add_parser("health", help="Show config and check Ollama")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Optional speaker diarization with pyannote.audio.

Diarization answers "who spoke when" for single-stream recordings.  It is
optional because it needs PyTorch plus a gated HuggingFace model.  When the
meeting source already provides per-speaker audio (e.g. a future Jitsi
per-participant bot), diarization is unnecessary.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_PIPELINE_CACHE: dict[str, Any] = {}


def is_available() -> bool:
    """True if pyannote.audio is importable."""
    try:
        import pyannote.audio  # noqa: F401

        return True
    except Exception:
        return False


def _get_pipeline(settings: Settings):
    key = settings.diarization_model
    if key not in _PIPELINE_CACHE:
        from pyannote.audio import Pipeline  # lazy import

        logger.info("Loading diarization pipeline '%s'", settings.diarization_model)
        pipeline = Pipeline.from_pretrained(
            settings.diarization_model,
            use_auth_token=settings.huggingface_token,
        )
        # Move to GPU if available.
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))
        except Exception:
            pass
        _PIPELINE_CACHE[key] = pipeline
    return _PIPELINE_CACHE[key]


def diarize(audio_path: str, settings: Settings | None = None) -> list[dict]:
    """Return a list of speaker turns: ``{"start", "end", "speaker"}``.

    Returns an empty list (no labels) if diarization is disabled or unavailable
    so the caller can degrade gracefully to a label-free transcript.
    """
    settings = settings or get_settings()
    if not settings.diarization_enabled:
        return []
    if not is_available():
        logger.warning(
            "Diarization enabled but pyannote.audio is not installed; "
            "install requirements-diarization.txt. Continuing without speakers."
        )
        return []

    try:
        pipeline = _get_pipeline(settings)
        kwargs: dict[str, Any] = {}
        if settings.diarization_min_speakers is not None:
            kwargs["min_speakers"] = settings.diarization_min_speakers
        if settings.diarization_max_speakers is not None:
            kwargs["max_speakers"] = settings.diarization_max_speakers

        annotation = pipeline(audio_path, **kwargs)
        turns: list[dict] = []
        for segment, _, label in annotation.itertracks(yield_label=True):
            turns.append(
                {"start": float(segment.start), "end": float(segment.end), "speaker": str(label)}
            )
        turns.sort(key=lambda t: t["start"])
        return _relabel(turns)
    except Exception as exc:  # diarization must never crash the pipeline
        logger.exception("Diarization failed; continuing without speakers: %s", exc)
        return []


def _relabel(turns: list[dict]) -> list[dict]:
    """Rename raw labels (SPEAKER_00...) to friendly 'Speaker 1...' in order."""
    mapping: dict[str, str] = {}
    for turn in turns:
        raw = turn["speaker"]
        if raw not in mapping:
            mapping[raw] = f"Speaker {len(mapping) + 1}"
        turn["speaker"] = mapping[raw]
    return turns

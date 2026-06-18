"""Speech-to-text using faster-whisper (CTranslate2).

Runs efficiently on CPU with int8 quantization, or on a small GPU.  The model
is loaded once per process and cached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {}


@dataclass
class TranscriptionResult:
    segments: list[dict] = field(default_factory=list)
    language: str | None = None
    duration: float | None = None


def _resolve_device_and_compute(settings: Settings) -> tuple[str, str]:
    device = settings.whisper_device
    compute = settings.whisper_compute_type

    if device == "auto":
        try:
            import torch  # type: ignore

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    if compute == "auto":
        compute = "int8" if device == "cpu" else "int8_float16"

    return device, compute


def get_model(settings: Settings | None = None):
    """Return a cached faster-whisper model instance."""
    settings = settings or get_settings()
    device, compute = _resolve_device_and_compute(settings)
    cache_key = f"{settings.whisper_model}:{device}:{compute}"
    if cache_key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel  # lazy import

        logger.info(
            "Loading Whisper model '%s' on %s (%s)",
            settings.whisper_model, device, compute,
        )
        _MODEL_CACHE[cache_key] = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute,
            download_root=str(settings.model_cache_dir),
        )
    return _MODEL_CACHE[cache_key]


def transcribe(audio_path: str, settings: Settings | None = None) -> TranscriptionResult:
    """Transcribe an audio file into timestamped segments."""
    settings = settings or get_settings()
    model = get_model(settings)

    segments_iter, info = model.transcribe(
        audio_path,
        language=settings.whisper_language,
        beam_size=settings.whisper_beam_size,
        vad_filter=settings.whisper_vad_filter,
        word_timestamps=False,
    )

    segments: list[dict] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text,
                "speaker": None,
            }
        )

    return TranscriptionResult(
        segments=segments,
        language=getattr(info, "language", None),
        duration=getattr(info, "duration", None),
    )

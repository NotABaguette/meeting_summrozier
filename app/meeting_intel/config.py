"""Central configuration.

Every setting can be overridden with an environment variable (or a ``.env``
file).  Defaults are tuned for a CPU-only / small-GPU (2-6 GB VRAM) on-prem
deployment so the platform runs out of the box without any tuning.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- General ---------------------------------------------------------
    app_name: str = "Meeting Intelligence (self-hosted)"
    environment: str = "production"

    # ----- Storage ---------------------------------------------------------
    # Where uploaded audio and rendered artifacts live (a mounted volume).
    data_dir: Path = Path("/data")
    # Database connection.  Postgres in production, SQLite works for local dev.
    database_url: str = "postgresql+psycopg://meeting:meeting@db:5432/meeting"

    # Auto-delete the source audio file this many days after processing.
    # 0 disables auto-deletion.  Transcripts/summaries are kept regardless.
    audio_retention_days: int = 0

    # ----- Speech-to-text (faster-whisper) --------------------------------
    # tiny | base | small | medium | large-v3 | large-v3-turbo ...
    # NOTE on Persian/Farsi: smaller models are weak on Persian.
    #   large-v3-turbo (default): same encoder as large-v3 but ~6x faster
    #     decoding; strong Persian; fits a small GPU; OK on CPU for batch.
    #   large-v3: best general Persian accuracy (slower, more memory).
    #   small: fastest / lowest resource (noticeably weaker Persian).
    #   Best-in-class Persian: a fine-tune like vhdm/whisper-large-fa-v1
    #     converted to CTranslate2 (see docs/MODELS.md), then set this to its path.
    whisper_model: str = "large-v3-turbo"
    # cpu | cuda | auto
    whisper_device: str = "auto"
    # int8 (CPU) | int8_float16 (small GPU) | float16 (GPU) | auto
    whisper_compute_type: str = "auto"
    # Language of the meetings. "fa" = Persian/Farsi. Set to None to auto-detect
    # (auto-detect is less reliable; pin it if you know the language).
    whisper_language: str | None = "fa"
    whisper_beam_size: int = 5
    # Voice-activity detection trims silence -> faster, fewer hallucinations.
    whisper_vad_filter: bool = True
    # Directory used to cache downloaded model weights (mount a volume here for
    # fully air-gapped re-runs).
    model_cache_dir: Path = Path("/models")

    # ----- Speaker diarization (optional, pyannote.audio) -----------------
    # OFF by default because it needs PyTorch + a gated HuggingFace model.
    # When OFF you still get a full timestamped transcript, just without
    # per-speaker labels.  See docs/JITSI-INTEGRATION.md for the per-speaker
    # story.  Turn ON for "who said what" on single-stream recordings.
    diarization_enabled: bool = False
    # community-1 is pyannote's current best open self-hostable model
    # (more accurate than 3.1). Falls back fine to "pyannote/speaker-diarization-3.1".
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    # HuggingFace token, only needed the first time to download the gated model.
    huggingface_token: str | None = None
    # Optional hints to improve diarization accuracy.
    diarization_min_speakers: int | None = None
    diarization_max_speakers: int | None = None

    # ----- Summarization (local LLM via Ollama) ---------------------------
    ollama_base_url: str = "http://ollama:11434"
    # Default: Gemma 4 E2B with Quantization-Aware Training (int4). ~4.3 GB, so
    # it fits the whole "CPU or 2-6 GB GPU" range and stays fast, while QAT keeps
    # quality close to the full-precision model. 140+ languages incl. Persian,
    # 128K context (long meetings summarize in one pass), commercial Gemma terms.
    # Quality upgrades (one env var):
    #   gemma4:e4b-it-qat  (~6.1 GB, better Persian; ~8 GB GPU or CPU/RAM)
    #   gemma4:12b-it-qat  (best quality; needs more RAM/GPU)
    #   qwen2.5:7b-instruct (alt), partai/dorna-llama3 (Persian-specialized)
    #   qwen3.5:4b is an option but its "thinking mode" complicates strict JSON.
    #   aya-expanse:8b is great for Persian BUT CC-BY-NC (non-commercial).
    # NOTE: requires a recent Ollama (Gemma 4 support, mid-2026+).
    ollama_model: str = "gemma4:e2b-it-qat"
    ollama_timeout_seconds: int = 900
    ollama_num_ctx: int = 8192
    ollama_temperature: float = 0.2
    # Auto-pull the model from the local Ollama registry if missing.
    ollama_auto_pull: bool = True
    # Language for the generated minutes/summary.
    # "auto"  -> write in the same language as the meeting (Persian in -> Persian out)
    # "fa"    -> always Persian, "en" -> always English, etc.
    summary_language: str = "auto"
    # Transcript chunk size (characters) for map-reduce summarization of long
    # meetings.  Kept conservative so it fits small-context models.
    summary_max_chunk_chars: int = 12000

    # ----- Worker / ingestion ---------------------------------------------
    worker_poll_interval_seconds: float = 3.0
    # Watch-folder ingestion (e.g. Jitsi/Jibri drops recordings here).
    watch_folder_enabled: bool = False
    watch_folder_path: Path = Path("/data/incoming")
    watch_folder_poll_seconds: float = 10.0

    # ----- Jitsi (in-meeting "Record & Summarize" button) -----------------
    # Your Jitsi server base URL, e.g. https://meet.yourcompany.com
    # When set, the platform hosts meetings with a built-in record button.
    jitsi_server_url: str = ""
    # Internal URL the platform uses to reach the bot (never exposed to browsers).
    bot_base_url: str = "http://jitsi-bot:8090"
    # Text shown on the in-meeting button.
    jitsi_button_label: str = "🤖 Record & Summarize"

    @property
    def jitsi_domain(self) -> str:
        """Host portion of jitsi_server_url (what external_api.js needs)."""
        url = self.jitsi_server_url.strip()
        if not url:
            return ""
        url = url.split("://", 1)[-1]
        return url.split("/", 1)[0]

    @property
    def jitsi_enabled(self) -> bool:
        return bool(self.jitsi_domain)

    # ----- Uploads ---------------------------------------------------------
    max_upload_mb: int = 2048
    allowed_audio_extensions: tuple[str, ...] = (
        ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".opus", ".flac", ".webm", ".mkv",
    )

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.audio_dir, self.artifacts_dir, self.model_cache_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

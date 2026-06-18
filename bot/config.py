"""Bot configuration (env-driven)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from .helpers import StopPolicy


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOT_", env_file=".env", extra="ignore")

    # Your Jitsi server, e.g. https://meet.yourcompany.com
    jitsi_server_url: str = "https://meet.example.com"
    # Display name the bot shows in the meeting.
    display_name: str = "Meeting Summarizer"
    # Optional JWT for authenticated Jitsi deployments.
    jwt: str | None = None

    # Where to send the finished recording:
    #   "api"    -> upload to the platform API (recommended; no shared volume)
    #   "folder" -> drop into a watch folder the ingester reads
    submit_mode: str = "api"
    platform_api_url: str = "http://api:8000"
    output_dir: str = "/data/incoming"
    work_dir: str = "/tmp/recordings"

    # Headless Chromium + audio capture.
    headless: bool = True
    # PulseAudio monitor source that Chromium's audio is routed to.
    audio_source: str = "jitsi_sink.monitor"

    # Stop policy.
    max_minutes: int = 240
    leave_after_alone_seconds: int = 30
    join_grace_seconds: int = 300
    poll_seconds: float = 5.0

    # Control server port.
    port: int = 8090

    def stop_policy(self) -> StopPolicy:
        return StopPolicy(
            max_seconds=self.max_minutes * 60,
            leave_after_alone_seconds=self.leave_after_alone_seconds,
            join_grace_seconds=self.join_grace_seconds,
        )


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()

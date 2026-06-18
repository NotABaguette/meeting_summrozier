"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MeetingSummary(BaseModel):
    id: str
    title: str
    source: str
    status: str
    duration_seconds: float | None = None
    language: str | None = None
    error: str | None = None
    progress: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MeetingDetail(MeetingSummary):
    segments: list[dict[str, Any]] | None = None
    transcript_text: str | None = None
    summary: dict[str, Any] | None = None


class CreateMeetingResponse(BaseModel):
    id: str
    status: str


class HealthResponse(BaseModel):
    status: str
    database: bool
    ollama: bool
    details: dict[str, Any] = {}

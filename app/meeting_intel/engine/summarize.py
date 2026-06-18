"""Generate meeting summaries with a local LLM served by Ollama.

For long meetings we use a map-reduce strategy: the transcript is split into
chunks, each chunk is condensed into notes, then the notes are combined into a
single structured summary.  This keeps everything within the context window of
the small models that fit on CPU / a 2-6 GB GPU.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

# Keys the rest of the system relies on.  parse_summary() guarantees them.
_LIST_KEYS = ("key_points", "decisions", "topics", "next_steps", "participants")

# Friendly names for common language codes (extend as needed).
_LANG_NAMES = {
    "fa": "Persian (Farsi)",
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "tr": "Turkish",
    "ru": "Russian",
}


def _lang_instruction(language: str | None) -> str:
    """Return an instruction telling the model which language to write in."""
    if not language or language == "auto":
        return (
            "Write ALL output in the SAME language as the transcript "
            "(for example, if the meeting is in Persian, write the minutes in Persian)."
        )
    name = _LANG_NAMES.get(language.lower(), language)
    return f"Write ALL output in {name}, regardless of the transcript's language."

_JSON_SCHEMA_HINT = """Return ONLY a JSON object with exactly these fields:
{
  "title": "a short descriptive meeting title",
  "executive_summary": "2-4 sentence overview of the meeting",
  "key_points": ["the most important points discussed"],
  "decisions": ["concrete decisions that were made"],
  "action_items": [{"owner": "person or null", "task": "what to do", "due": "deadline or null"}],
  "topics": ["topics/agenda items covered"],
  "next_steps": ["agreed follow-ups"],
  "journal": [{"heading": "section title", "details": "a paragraph describing that part of the meeting"}],
  "participants": ["speaker names or labels if identifiable"]
}
Do not invent information that is not supported by the transcript. Use empty
arrays or null when something is not present."""


# --------------------------------------------------------------------------- #
# Pure helpers (no network) — unit tested
# --------------------------------------------------------------------------- #
def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks no larger than ``max_chars``, on line boundaries."""
    text = text or ""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        # A single oversized line is hard-split.
        if len(line) > max_chars:
            if current:
                chunks.append("".join(current))
                current, size = [], 0
            for i in range(0, len(line), max_chars):
                chunks.append(line[i : i + max_chars])
            continue
        if size + len(line) > max_chars and current:
            chunks.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        chunks.append("".join(current))
    return [c for c in chunks if c.strip()]


def build_single_prompt(
    transcript: str, participants: list[str] | None = None, language: str | None = "auto"
) -> str:
    who = f"\nKnown speakers: {', '.join(participants)}." if participants else ""
    return (
        "You are a meticulous meeting-minutes assistant. Analyse the meeting "
        f"transcript below and produce structured minutes.{who}\n"
        f"{_lang_instruction(language)}\n\n"
        f"{_JSON_SCHEMA_HINT}\n\n"
        "TRANSCRIPT:\n"
        f"{transcript}\n"
    )


def build_map_prompt(chunk: str, language: str | None = "auto") -> str:
    return (
        "Below is PART of a longer meeting transcript. Write concise notes "
        "capturing the key points, any decisions, action items (with owners), "
        "and topics in this part. Use short bullet points. Do not add a "
        f"conclusion.\n{_lang_instruction(language)}\n\nTRANSCRIPT PART:\n"
        f"{chunk}\n"
    )


def build_reduce_prompt(
    notes: str, participants: list[str] | None = None, language: str | None = "auto"
) -> str:
    who = f"\nKnown speakers: {', '.join(participants)}." if participants else ""
    return (
        "You are a meticulous meeting-minutes assistant. Below are ordered "
        "notes taken from consecutive parts of a single meeting. Consolidate "
        f"them into one coherent set of structured minutes.{who}\n"
        f"{_lang_instruction(language)}\n\n"
        f"{_JSON_SCHEMA_HINT}\n\n"
        "NOTES:\n"
        f"{notes}\n"
    )


def _extract_json(raw: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from model output."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Find the outermost {...} block.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                # e.g. {"point": "..."} -> take first string value
                vals = [str(v) for v in item.values() if v]
                if vals:
                    out.append(" ".join(vals))
            elif item is not None and str(item).strip():
                out.append(str(item).strip())
        return out
    return [str(value)]


def _normalize_action_items(value: Any) -> list[dict]:
    items: list[dict] = []
    if not value:
        return items
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                items.append(
                    {
                        "owner": (item.get("owner") or None),
                        "task": str(item.get("task") or item.get("action") or "").strip(),
                        "due": (item.get("due") or item.get("deadline") or None),
                    }
                )
            elif str(item).strip():
                items.append({"owner": None, "task": str(item).strip(), "due": None})
    return [i for i in items if i["task"]]


def _normalize_journal(value: Any) -> list[dict]:
    out: list[dict] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                heading = entry.get("heading") or entry.get("title") or "Section"
                details = entry.get("details") or entry.get("summary") or ""
                out.append({"heading": str(heading), "details": str(details)})
            elif str(entry).strip():
                out.append({"heading": "Section", "details": str(entry).strip()})
    elif isinstance(value, str) and value.strip():
        out.append({"heading": "Summary", "details": value.strip()})
    return out


def parse_summary(raw: str) -> dict[str, Any]:
    """Parse model output into the canonical summary dict with safe defaults."""
    data = _extract_json(raw)
    summary: dict[str, Any] = {
        "title": str(data.get("title") or "").strip() or None,
        "executive_summary": str(data.get("executive_summary") or "").strip(),
        "action_items": _normalize_action_items(data.get("action_items")),
        "journal": _normalize_journal(data.get("journal")),
    }
    for key in _LIST_KEYS:
        summary[key] = _as_str_list(data.get(key))

    # If the model produced nothing usable, surface the raw text so the user
    # still gets *something* instead of a blank page.
    if not summary["executive_summary"] and not data:
        summary["executive_summary"] = (raw or "").strip()[:2000]
    return summary


# --------------------------------------------------------------------------- #
# Ollama client
# --------------------------------------------------------------------------- #
class OllamaError(RuntimeError):
    pass


class Summarizer:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.ollama_base_url,
            timeout=self.settings.ollama_timeout_seconds,
        )

    def ensure_model(self) -> None:
        """Pull the configured model from the local Ollama registry if absent."""
        if not self.settings.ollama_auto_pull:
            return
        model = self.settings.ollama_model
        with self._client() as client:
            try:
                tags = client.get("/api/tags").json()
                names = {m.get("name", "") for m in tags.get("models", [])}
                # Ollama lists e.g. "qwen2.5:3b-instruct"; also accept ":latest".
                if model in names or f"{model}:latest" in names or any(
                    n.split(":")[0] == model.split(":")[0] and model in n for n in names
                ):
                    return
            except Exception as exc:
                logger.warning("Could not list Ollama models: %s", exc)

            logger.info("Pulling Ollama model '%s' (one-time, local registry)...", model)
            resp = client.post("/api/pull", json={"name": model, "stream": False})
            if resp.status_code != 200:
                raise OllamaError(f"Failed to pull model '{model}': {resp.text}")

    def generate(self, prompt: str, *, json_format: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings.ollama_temperature,
                "num_ctx": self.settings.ollama_num_ctx,
            },
        }
        if json_format:
            payload["format"] = "json"
        with self._client() as client:
            resp = client.post("/api/generate", json=payload)
            if resp.status_code != 200:
                raise OllamaError(f"Ollama generate failed: {resp.status_code} {resp.text}")
            return resp.json().get("response", "")

    def summarize(self, transcript: str, participants: list[str] | None = None) -> dict[str, Any]:
        """Produce a structured summary, using map-reduce for long transcripts."""
        self.ensure_model()
        transcript = transcript or ""
        lang = self.settings.summary_language
        chunks = chunk_text(transcript, self.settings.summary_max_chunk_chars)

        if len(chunks) <= 1:
            raw = self.generate(
                build_single_prompt(transcript, participants, lang), json_format=True
            )
            return parse_summary(raw)

        logger.info("Long transcript: summarizing in %d chunks (map-reduce)", len(chunks))
        partial_notes = []
        for i, chunk in enumerate(chunks, 1):
            note = self.generate(build_map_prompt(chunk, lang))
            partial_notes.append(f"--- Part {i} ---\n{note.strip()}")
        combined = "\n\n".join(partial_notes)

        # If the combined notes are still huge, recurse on the notes.
        if len(combined) > self.settings.summary_max_chunk_chars * 2:
            combined = "\n\n".join(
                self.generate(build_map_prompt(c, lang)).strip()
                for c in chunk_text(combined, self.settings.summary_max_chunk_chars)
            )

        raw = self.generate(build_reduce_prompt(combined, participants, lang), json_format=True)
        return parse_summary(raw)

# Roadmap

Status of the platform and what's planned. Phase 1 is implemented and runnable
today.

## ✅ Phase 1 — Core platform (done)

- Local transcription (faster-whisper, Persian-tuned defaults, CPU/small-GPU)
- Optional speaker diarization (pyannote community-1)
- Local LLM summaries via Ollama (Gemma 4 QAT default): executive summary,
  key points, decisions, action items, topics, next steps, meeting journal
- Output language follows the meeting (Persian in → Persian out), configurable
- Web UI (upload, live status, results, RTL rendering, downloads)
- JSON API + CLI
- **Ingestion:** browser upload and watch-folder (Jibri, VoIP, Meet recordings)
- **Automatic Jitsi auto-join bot** (beta): joins a room on demand (moderator
  button or API), records, and submits — no manual upload
- Postgres-backed job queue, horizontally scalable workers
- Fully offline / air-gappable; privacy & retention controls
- Docker Compose one-command deploy; unit-tested core

## 🛠️ Phase 2 — Jitsi bot upgrades

- Per-participant audio capture (via `lib-jitsi-meet`) → exact speaker
  attribution without diarization
- Auto-join via Jitsi/Prosody events (bot joins the instant a meeting starts) and
  calendar integration
- Live/near-real-time processing and captions while the meeting runs
- Harden the headless capture across Jitsi versions / auth modes

## 🛠️ Phase 3 — Google Meet bot

- Headless-browser bot that joins a Meet call and captures audio
- Speaker attribution via diarization (Meet doesn't expose per-speaker tracks)

## 🛠️ Phase 4 — VoIP deep integration

- Asterisk (AMI/ARI) and FreeSWITCH (ESL) connectors
- Per-channel recording → clean per-speaker transcripts automatically
- Map channels/extensions to participant names

## 🛠️ Phase 5 — Collaboration & intelligence

- User accounts, roles & permissions (RBAC), multi-team isolation
- Speaker **enrollment/naming** (recognize "Ali", "Sara" across meetings)
- **Search** across all meetings; tags; folders
- **Ask questions** about past meetings (local RAG over transcripts)
- Live captions during the meeting
- Delivery integrations: email / internal chat (Mattermost, Rocket.Chat) — all
  self-hosted
- Export to PDF / DOCX; templated minutes

## Ideas / nice-to-have

- Real-time translation (Persian ↔ English) using local models
- Sentiment / talk-time analytics per speaker
- Redaction of sensitive terms before storage
- Webhooks on "meeting processed"

> Have a priority? The connector interface (see
> [ARCHITECTURE.md](ARCHITECTURE.md#extending-with-new-sources)) makes it
> straightforward to add sources without touching the engine.

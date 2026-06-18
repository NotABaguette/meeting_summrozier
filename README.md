# 🗣️ Meeting Intelligence — Self-Hosted, Private, Offline

Transcribe your meetings (who said what, with timestamps) and automatically
generate **full transcripts, executive summaries, bullet points, decisions,
action items, and a meeting journal** — all using AI models that run **entirely
on your own servers**.

> **Privacy first.** No meeting audio, transcript, or summary ever leaves your
> network. The only outbound traffic is a **one-time model download** during
> setup — and that can be eliminated for a fully air-gapped install
> (see [docs/SECURITY-PRIVACY.md](docs/SECURITY-PRIVACY.md)).

Built for **Persian/Farsi meetings** by default (configurable to any language),
and tuned to run on **CPU or a small 2–6 GB GPU**.

---

## What it does

1. You give it a meeting recording (upload in the browser, or auto-ingest from a
   watch folder that Jitsi/Jibri, a VoIP recorder, etc. drop files into).
2. It **transcribes** the audio locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
3. It optionally labels **speakers** ("who said what").
4. A **local LLM** (via [Ollama](https://ollama.com)) writes the summary,
   bullet points, decisions, action items, and meeting journal — **in Persian**
   (or whatever language you choose).
5. You read it in a clean web UI and download Markdown files.

---

## Quick start (3 commands)

You need a Linux server with **Docker** + **Docker Compose**. Nothing else.

```bash
git clone <this-repo> && cd meeting_summrozier
cp .env.example .env        # optional — defaults work out of the box
docker compose up -d        # builds everything and downloads the models
```

Then open **http://localhost:8080**, upload a recording, and wait for it to
finish (status updates live). First run downloads the AI models (a few GB), so
give it a few minutes; after that everything is local and fast.

> Prefer make? `make up`, `make logs`, `make ps`, `make down`. Run `make help`.

---

## Default models (and why)

These were chosen for **Persian quality on small/cheap hardware** with
**commercial-friendly licenses**. All are swappable with one line in `.env`.
See [docs/MODELS.md](docs/MODELS.md) for the full rationale, benchmarks, and how
to get **best-in-class Persian** accuracy.

| Job | Default | Why | Lighter / Heavier |
| --- | --- | --- | --- |
| Speech-to-text | `large-v3-turbo` | ~6× faster than large-v3, strong Persian, fits a small GPU | `small` (faster) · `large-v3` (best Persian) |
| Summarization LLM | `gemma4:e2b-it-qat` | Newest Gemma 4 QAT (int4, ~4.3 GB), 140+ languages incl. Persian, 128K context, commercial license | `gemma4:e4b-it-qat` / `gemma4:12b-it-qat` (better) |
| Speaker labels | off (optional) | `pyannote community-1` when enabled | — |

---

## Connecting your meeting platforms

| Platform | How it works | Status |
| --- | --- | --- |
| **Jitsi** (self-hosted) | **Fully automatic:** an auto-join bot joins the room (triggered by a moderator button or an API call), records, and submits it — no manual capture/upload. The native Jibri Record button is also supported. | ✅ Automatic (bot) |
| **Google Meet** | Save the Meet recording → drop in the watch folder (auto-processed). Live bot on [roadmap](docs/ROADMAP.md). | ✅ Recording |
| **VoIP** (Asterisk/FreeSWITCH) | Per-channel call recording → watch folder (per-channel = clean speaker separation). | ✅ Recording |

### Automatic Jitsi (no uploads) — point it at a meeting or add a button

```bash
# 1) Set JITSI_SERVER_URL in .env, then start the bot:
docker compose --profile jitsi up -d --build

# 2) Tell it to join a meeting (or wire this to a Jitsi moderator button):
curl -X POST http://localhost:8090/join \
  -H 'content-type: application/json' \
  -d '{"room": "https://meet.yourcompany.com/WeeklySync"}'
```
The bot joins, records, leaves when everyone's gone, and the summary appears in
the UI automatically. Full setup incl. the **"🤖 Summarize meeting" moderator
button**: [docs/JITSI-INTEGRATION.md](docs/JITSI-INTEGRATION.md).

### Watch folder (for Jibri / VoIP / Meet recordings)

```bash
make watch          # or: docker compose --profile watch up -d
```
Drop any recording into `./recordings` and it's processed automatically.

---

## Usage without the UI (CLI)

```bash
# Process a file and print the minutes + transcript
docker compose run --rm worker python -m meeting_intel.cli process /data/audio/yourfile.wav --out /data/out

# Check configuration and that Ollama is reachable
docker compose run --rm worker python -m meeting_intel.cli health
```

There is also a JSON API (`POST /api/meetings`, `GET /api/meetings/{id}`, …) —
see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Configuration

Everything is configured via `.env` (see `.env.example` for the full list). The
most useful knobs:

| Variable | Default | Meaning |
| --- | --- | --- |
| `WHISPER_MODEL` | `large-v3-turbo` | Transcription model |
| `WHISPER_LANGUAGE` | `fa` | Meeting language (`fa` = Persian; blank = auto) |
| `OLLAMA_MODEL` | `gemma4:e2b-it-qat` | Summarization model |
| `SUMMARY_LANGUAGE` | `auto` | Language of the minutes (`auto` = same as meeting) |
| `WHISPER_DEVICE` | `auto` | `cpu` or `cuda` |
| `DIARIZATION_ENABLED` | `false` | Turn on speaker labels (needs extra setup) |
| `AUDIO_RETENTION_DAYS` | `0` | Auto-delete source audio after N days (0 = keep) |

---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how it's built, data flow, API
- [docs/SECURITY-PRIVACY.md](docs/SECURITY-PRIVACY.md) — privacy model, air-gapping, hardening
- [docs/MODELS.md](docs/MODELS.md) — model choices, Persian tuning, swapping models
- [docs/JITSI-INTEGRATION.md](docs/JITSI-INTEGRATION.md) — wiring up Jitsi/Jibri
- [docs/ROADMAP.md](docs/ROADMAP.md) — what's next (live bots, speaker naming, search)

---

## Hardware notes

- **CPU-only** works. `large-v3-turbo` transcription runs slower than real time
  on a 4-core CPU but is fine for batch processing after a meeting. Drop to
  `small` if you need it faster.
- **A small GPU (2–6 GB)** makes transcription near-real-time and speeds up the
  LLM. Uncomment the GPU block in `docker-compose.yml`.
- RAM: 8 GB minimum, 16 GB comfortable.

## Tests

```bash
make test     # or: cd app && pip install -r requirements-dev.txt && pytest
```

## License

This project's code is provided as-is for your internal use. Note that the AI
**models** you download have their own licenses — the defaults are chosen to be
commercial-friendly; see [docs/MODELS.md](docs/MODELS.md).

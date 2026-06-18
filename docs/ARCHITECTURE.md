# Architecture

Everything runs as containers on your own host(s). No managed/cloud services.

```
                              ┌──────────────────────────────────────────────┐
   Meeting recording          │                  YOUR SERVER                  │
   ───────────────────        │                                              │
   • Browser upload  ─────────┼──►  API  (FastAPI + web UI, port 8080)        │
   • Watch folder    ─────────┼──►  Ingest  ──┐                               │
     (Jitsi/Jibri,            │               │  creates "queued" meeting     │
      VoIP, Meet rec.)        │               ▼                               │
                              │           Postgres  ◄── metadata, transcripts,│
                              │               ▲          summaries (JSON)     │
                              │               │                               │
                              │            Worker  ── claims queued jobs ──┐   │
                              │               │                            │   │
                              │   ┌───────────┴───────────┐                │   │
                              │   ▼           ▼           ▼                ▼   │
                              │ faster-    pyannote     Ollama         /data    │
                              │ whisper   (optional)   (local LLM)   audio +    │
                              │ (ASR)     diarization  gemma4 QAT    artifacts  │
                              └──────────────────────────────────────────────┘
   Outbound: only a one-time model download at setup. Then fully offline.
```

## Components

| Service | Image / entrypoint | Role |
| --- | --- | --- |
| `api` | `uvicorn meeting_intel.api.main:app` | Web UI + JSON API. Accepts uploads, shows results, serves downloads. |
| `worker` | `python -m meeting_intel.worker` | Pulls queued meetings and runs the pipeline. Scale to N replicas. |
| `ingest` | `python -m meeting_intel.ingest` | (optional) Watches a folder and registers dropped recordings. |
| `db` | `postgres:16` | Meetings, transcripts (JSON), summaries (JSON), status. |
| `ollama` | `ollama/ollama` | Serves the local summarization LLM. |
| `model-init` | one-shot | Pulls the LLM into Ollama on first start. |

## The engine (`meeting_intel/engine/`)

| Module | Responsibility |
| --- | --- |
| `transcribe.py` | faster-whisper wrapper → timestamped segments. Model cached per process. |
| `diarize.py` | Optional pyannote diarization → speaker turns. Degrades gracefully if off/unavailable. |
| `merge.py` | Pure logic: assign speakers to segments, group, render plain transcript. |
| `summarize.py` | Ollama client + prompts. Map-reduce for long meetings. Strict JSON parsing with fallbacks. |
| `artifacts.py` | Render Markdown (minutes + transcript) from stored data. |
| `pipeline.py` | Orchestrates transcribe → diarize → merge → summarize and persists results. |

The pure modules (`merge`, `artifacts`, and the prompt/parse helpers in
`summarize`) are covered by unit tests in `app/tests/`.

## Job lifecycle

```
queued ──(worker claims)──► processing ──► completed
                                  └────────► failed (error stored, retry-able)
```

Workers claim jobs atomically with `SELECT ... FOR UPDATE SKIP LOCKED` on
Postgres, so you can run multiple worker replicas safely:

```bash
docker compose up -d --scale worker=3
```

`progress` is updated through stages (`transcribing` → `diarizing` →
`summarizing` → `done`) and shown live in the UI.

## Storage layout (the `appdata` volume, mounted at `/data`)

```
/data
├── audio/        # source recordings, named <meeting_id>.<ext>
├── artifacts/    # (reserved for exported files)
└── incoming/     # watch-folder drop zone (when the ingester is enabled)
```

Model weights live in the separate `models` volume (`/models`) so re-runs are
offline and images stay small.

## HTTP API

| Method & path | Purpose |
| --- | --- |
| `POST /api/meetings` | Upload audio (`file`, optional `title`). Returns `{id, status}`. |
| `GET /api/meetings` | List meetings. |
| `GET /api/meetings/{id}` | Full detail incl. segments + summary. |
| `DELETE /api/meetings/{id}` | Delete meeting and its audio. |
| `GET /api/meetings/{id}/minutes.md` | Download minutes (Markdown). |
| `GET /api/meetings/{id}/transcript.md` / `.txt` | Download transcript. |
| `GET /healthz` | Liveness + DB/Ollama reachability. |

## Why this design

- **Postgres-as-queue** keeps the moving parts minimal (no Redis/Celery) while
  remaining safe for concurrent workers — ideal for a team with no ops staff.
- **Lazy model imports** mean the API container starts instantly and only the
  worker loads the heavy ML libraries.
- **JSON columns** make results portable and the DB schema stable as we add
  summary fields.
- **Connector-agnostic engine**: any source that produces an audio file (upload,
  watch folder, future live bots) feeds the same pipeline.

## Extending with new sources

A "connector" only needs to land an audio file and create a `Meeting` row with
`status="queued"` (see `meeting_intel/ingest.py::ingest_file` for the reference
implementation). The worker does the rest. Live, per-participant bots (Jitsi,
Meet) are planned — see [ROADMAP.md](ROADMAP.md).

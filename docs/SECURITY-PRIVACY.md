# Security & Privacy

This platform is designed so that **your meeting content never leaves your
network**. This document explains exactly what runs where, the only outbound
traffic that exists, how to make it **fully air-gapped**, and a hardening
checklist.

## What data exists, and where

| Data | Stored in | Leaves your network? |
| --- | --- | --- |
| Source audio | `appdata` volume → `/data/audio` | **No** |
| Transcript (text + segments) | Postgres (`db` volume) | **No** |
| Summary / minutes | Postgres | **No** |
| Model weights | `models` / `ollama` volumes | Downloaded once at setup (see below) |

There is **no telemetry, no analytics, no external API**. The AI models
(transcription and summarization) run inside your own containers.

## The only outbound traffic: one-time model download

On first start, two downloads happen **once**:

1. The **LLM** is pulled by Ollama from the Ollama registry
   (`registry.ollama.ai`).
2. The **Whisper** weights are downloaded by faster-whisper from
   **huggingface.co** on the first transcription.

After that, weights are cached in the `models`/`ollama` volumes and the system
works with **no internet at all**.

## Fully air-gapped install

If you cannot allow any outbound traffic, pre-stage the models on a connected
machine and copy them in:

1. **LLM** — on a machine with internet and Ollama:
   ```bash
   ollama pull gemma4:e2b-it-qat
   # copy the ~/.ollama directory into the server's `ollama` volume
   ```
   …or, on the server with temporary access: `make pull-model`, then cut
   internet.
2. **Whisper** — pre-download the CTranslate2 weights (e.g. with
   `huggingface-cli download Systran/faster-whisper-large-v3-turbo`) into the
   `models` volume, or convert a model as in [MODELS.md](MODELS.md).
3. Optionally make the backend network internal so containers physically cannot
   reach the internet. Add an override file `docker-compose.airgap.yml`:
   ```yaml
   networks:
     default:
       internal: true   # no egress for any service on this network
   ```
   Run with: `docker compose -f docker-compose.yml -f docker-compose.airgap.yml up -d`
   (publish the API port via a separate non-internal network or a reverse proxy).

> Verify zero egress: `docker compose exec worker curl -m 5 https://huggingface.co`
> should **fail** once air-gapped.

## Network isolation

- Only the **API** port (default `8080`) is published to the host. Postgres and
  Ollama are reachable only on the internal Docker network.
- Put the API behind your **reverse proxy** (nginx/Traefik/Caddy) with **TLS**
  and **authentication** (see below). Do not expose `8080` to the internet
  directly.

## Authentication

The app ships without built-in auth (it's meant to live on your internal
network / behind your SSO proxy). For access control, front it with:

- An authenticating reverse proxy (OAuth2-Proxy, Authelia, Authentik, or your
  existing SSO), **or**
- Network restrictions (VPN / internal-only).

Built-in user accounts & RBAC are on the [roadmap](ROADMAP.md).

## Data retention & deletion

- `AUDIO_RETENTION_DAYS` auto-deletes **source audio** after N days (a worker
  sweep runs hourly). `0` = keep. Transcripts/summaries are always kept.
- Any meeting (and its audio) can be deleted from the UI or
  `DELETE /api/meetings/{id}`.
- To wipe everything: `make clean` (removes all volumes — **irreversible**).

## Hardening checklist

- [ ] Change `POSTGRES_PASSWORD` in `.env`.
- [ ] Terminate TLS at a reverse proxy; don't expose port 8080 publicly.
- [ ] Require authentication (SSO/VPN) in front of the UI.
- [ ] Restrict who can reach the host (firewall / security groups).
- [ ] Enable disk encryption on the volume host (audio + DB at rest).
- [ ] Back up the `pgdata` volume (transcripts/summaries) regularly.
- [ ] Set an appropriate `AUDIO_RETENTION_DAYS` for your policy.
- [ ] Keep base images updated (`docker compose pull && docker compose up -d`).
- [ ] For multi-tenant/compliance needs, wait for RBAC (roadmap) or isolate per
      team with separate deployments.

## Threat model (brief)

- **Protects against:** data exfiltration to third-party AI services (there are
  none); accidental cloud storage of recordings.
- **You are responsible for:** host security, access control in front of the UI,
  encryption at rest, and backups. The platform gives you the controls; your
  environment enforces them.

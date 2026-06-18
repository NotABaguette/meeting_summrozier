# Jitsi integration — fully automatic, no manual upload

You self-host Jitsi, so the platform can capture meetings **automatically**.
There are two zero-touch options; **use Option 1** for the "point it at a
meeting / moderator button" experience you want.

| Option | What the user does | Speaker labels | Setup |
| --- | --- | --- | --- |
| **1. Auto-join bot** (recommended) | Click a button / nothing | via diarization | Run one container |
| **2. Native Record button** (Jibri) | Press Jitsi's Record | via diarization | Requires Jibri |

> **Per-participant accuracy:** both options capture *mixed* audio, so "who said
> what" comes from the optional diarization step (enable it — see
> [MODELS.md](MODELS.md)). A future bot upgrade captures each participant's audio
> separately for perfect attribution (see [ROADMAP.md](ROADMAP.md)).

---

## Option 1 — Auto-join recording bot ✅

A headless bot **joins the meeting, records it, and submits it for processing
automatically.** When everyone leaves (or a max duration is hit), it leaves and
the summary appears in the platform UI a few minutes later. No human captures or
uploads anything.

### 1. Enable it

In `.env` set your Jitsi server:
```env
JITSI_SERVER_URL=https://meet.yourcompany.com
# JITSI_JWT=...        # only if your Jitsi requires auth
```
Start the bot (it talks to the platform internally):
```bash
docker compose --profile jitsi up -d --build
```

### 2. Use it — just press a button (no curl)

The platform hosts your meetings with the official Jitsi UI **plus a built-in
button**. Nobody captures or uploads anything.

1. In the platform's top bar click **"＋ Start meeting"** (or open / share
   `http://your-platform:8080/meet/RoomName`).
2. The Jitsi call opens with a **"🤖 Record & Summarize"** button in the toolbar.
3. Press it once. A confirmation appears; the bot joins, records, and submits the
   meeting automatically. The summary shows up under **Meetings** afterwards.

That's the whole flow. How it works under the hood: the button calls the
platform (same origin, `POST /api/jitsi/join`), and the platform tells the
internal bot to join — so the bot is never exposed and there's no CORS or curl.

### Optional: put the button in your *existing* Jitsi UI

If you'd rather keep using your current Jitsi (not the platform-hosted page), add
the button via `config.js` and forward its click to the platform:
```js
// config.js on your Jitsi server
config.customToolbarButtons = [
  { id: 'summarize', text: '🤖 Record & Summarize',
    icon: 'data:image/svg+xml;base64,PHN2Zy8+' }
];
```
```js
// small script injected into your Jitsi deployment
APP.API.addListener?.('customButtonPressed', ({ id }) => {
  if (id !== 'summarize') return;
  fetch('http://your-platform:8080/api/jitsi/join', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ room: location.href })
  });
});
```

### Optional: automation (calendar bots, etc.)

For unattended/scheduled recording you can call the platform endpoint directly
(server-to-server) — no user needed:
```
POST http://your-platform:8080/api/jitsi/join   {"room": "RoomName"}
```

### How it stops automatically
- Leaves once **everyone else has left** (default 30s grace).
- Leaves if **nobody joins** within 5 minutes.
- Hard cap of **`BOT_MAX_MINUTES`** (default 240) so a forgotten bot never runs
  forever.

### Notes
- **Lobby / membersOnly:** allow the bot in, or give it a JWT (`JITSI_JWT`).
- **The bot is a silent listener** (mic & camera off). It shows up with the name
  from `BOT_DISPLAY_NAME` so participants know it's recording.
- **Speaker labels:** enable diarization (`DIARIZATION_ENABLED=true`) to get
  "who said what" from the mixed recording.

---

## Option 2 — Native Jitsi Record button (Jibri)

If you already run [Jibri](https://github.com/jitsi/jibri), the moderator's
built-in **Record** button is the trigger — no extra bot. Hook Jibri's finalize
step to hand the recording to the platform.

1. Start the watch-folder ingester: `make watch`
2. Set Jibri's finalize script (`jibri.conf`):
   ```hocon
   recording { finalize-script = "/opt/jitsi/finalize_recording.sh" }
   ```
3. `finalize_recording.sh` copies the recording into the platform:
   ```bash
   #!/bin/bash
   RECORDINGS_DIR="$1"                                   # passed by Jibri
   DEST="/path/to/meeting_summrozier/recordings"         # same host
   # or scp to the platform host: user@host:/path/.../recordings
   for f in "$RECORDINGS_DIR"/*.mp4; do cp "$f" "$DEST/"; done
   ```
4. Done — the file is auto-transcribed and summarized.

---

## Troubleshooting (bot)

| Symptom | Fix |
| --- | --- |
| Bot can't join | Check `JITSI_SERVER_URL`; allow guests or set `JITSI_JWT`; check lobby. |
| Empty/silent recording | Confirm the bot container has PulseAudio running (it starts automatically); check `docker compose logs jitsi-bot`. |
| Button does nothing | Ensure the `jitsi` profile is running (`docker compose --profile jitsi ps`) and check `docker compose logs jitsi-bot`. |
| "Could not reach the recording bot" | Start the bot: `docker compose --profile jitsi up -d`. |
| No speaker names | Enable diarization (see [MODELS.md](MODELS.md)). |

> The bot uses headless Chromium + PulseAudio + ffmpeg. It's new — validate it
> against your specific Jitsi deployment, and fall back to Option 2 (Jibri) if
> your Jitsi has unusual auth/lobby requirements.

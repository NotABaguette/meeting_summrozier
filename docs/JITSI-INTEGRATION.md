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

### 2. Trigger it — three ways

**(a) Point it at a meeting (API / script):**
```bash
curl -X POST http://localhost:8090/join \
  -H 'content-type: application/json' \
  -d '{"room": "https://meet.yourcompany.com/WeeklySync"}'
```
The bot joins, records, and submits. Check progress in the platform UI.

**(b) Moderator button inside Jitsi (External API embed) — recommended:**
If you open meetings through your own page using Jitsi's
[External API](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-iframe),
add a custom toolbar button that calls the bot. Minimal working example:

```html
<script src="https://meet.yourcompany.com/external_api.js"></script>
<div id="meet" style="height:100vh"></div>
<script>
  const DOMAIN = "meet.yourcompany.com";
  const BOT_URL = "http://localhost:8090";   // where the bot is reachable
  const roomName = "WeeklySync";
  const ICON = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTEyIDNhOSA5IDAgMTAwIDE4IDkgOSAwIDAwMC0xOHptMCAyYTcgNyAwIDExMCAxNCA3IDcgMCAwMTAtMTR6Ii8+PC9zdmc+";

  const api = new JitsiMeetExternalAPI(DOMAIN, {
    roomName,
    parentNode: document.querySelector("#meet"),
    configOverwrite: {
      customToolbarButtons: [
        { id: "summarize", text: "🤖 Summarize meeting", icon: ICON }
      ]
    }
  });

  api.addListener("customButtonPressed", ({ id }) => {
    if (id !== "summarize") return;
    fetch(BOT_URL + "/join", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ room: `https://${DOMAIN}/${roomName}` })
    }).then(() => alert("✅ The meeting will be transcribed and summarized."));
  });
</script>
```

**(c) Moderator button in a standalone Jitsi deployment:**
If you run the standard Jitsi web UI, add the button in your `config.js` and a
small listener (e.g. via a custom `<script>` in your deployment's
`base.html`/`title.html`):
```js
// config.js
config.customToolbarButtons = [
  { id: 'summarize', text: '🤖 Summarize meeting',
    icon: 'data:image/svg+xml;base64,PHN2Zy8+' }
];
```
```js
// custom injected script
window.addEventListener('message', (e) => {
  // Jitsi emits the custom button event; forward it to the bot.
  if (e?.data?.name === 'customButtonPressed' && e.data.id === 'summarize') {
    fetch('http://localhost:8090/join', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ room: location.href })
    });
  }
});
```

### How it stops automatically
- Leaves once **everyone else has left** (default 30s grace).
- Leaves if **nobody joins** within 5 minutes.
- Hard cap of **`BOT_MAX_MINUTES`** (default 240) so a forgotten bot never runs
  forever.
- You can stop it manually: `POST http://localhost:8090/sessions/{id}/stop`.

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
| Button does nothing | Verify `BOT_URL` is reachable from the browser and `BOT_ALLOWED_ORIGINS` allows your Jitsi origin (CORS). |
| No speaker names | Enable diarization (see [MODELS.md](MODELS.md)). |

> The bot uses headless Chromium + PulseAudio + ffmpeg. It's new — validate it
> against your specific Jitsi deployment, and fall back to Option 2 (Jibri) if
> your Jitsi has unusual auth/lobby requirements.

#!/bin/bash
# Start a PulseAudio virtual sink so headless Chromium has somewhere to play
# audio, then run the control server. ffmpeg records the sink's monitor.
set -e

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp}

# Start PulseAudio (per-user daemon; fine inside a container).
pulseaudio -D --exit-idle-time=-1 --disable-shm=true 2>/dev/null || true
sleep 1

# Create the virtual sink the recorder reads from (jitsi_sink.monitor).
pactl load-module module-null-sink sink_name=jitsi_sink \
      sink_properties=device.description=jitsi_sink 2>/dev/null || true
pactl set-default-sink jitsi_sink 2>/dev/null || true

echo "PulseAudio ready. Starting Jitsi bot control server on :${BOT_PORT:-8090}"
exec uvicorn bot.server:app --host 0.0.0.0 --port "${BOT_PORT:-8090}"

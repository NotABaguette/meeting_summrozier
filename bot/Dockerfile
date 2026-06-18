FROM python:3.11-slim

# Audio capture stack: PulseAudio (virtual sink) + ffmpeg (recorder).
RUN apt-get update && apt-get install -y --no-install-recommends \
        pulseaudio pulseaudio-utils ffmpeg dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    XDG_RUNTIME_DIR=/tmp

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt
# Install the Chromium browser + its system dependencies.
RUN playwright install --with-deps chromium

COPY . ./bot
COPY entrypoint.sh /srv/entrypoint.sh
RUN chmod +x /srv/entrypoint.sh

EXPOSE 8090
ENTRYPOINT ["/srv/entrypoint.sh"]

FROM python:3.11-slim

# ffmpeg: robust audio/video decoding. libgomp1: required by CTranslate2.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models \
    HUGGINGFACE_HUB_CACHE=/models

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml .
COPY meeting_intel ./meeting_intel

EXPOSE 8000

# Default command runs the API; the worker overrides this in docker-compose.
CMD ["uvicorn", "meeting_intel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Models — choices, Persian tuning, and how to swap

All models run locally. Defaults are picked for **Persian/Farsi quality on
CPU or a small 2–6 GB GPU**, with **commercial-friendly licenses**. Every choice
is one line in `.env`.

## Speech-to-text (faster-whisper)

| Model | Persian quality | Speed / size | When to use |
| --- | --- | --- | --- |
| **`large-v3-turbo`** (default) | Very good | ~6× faster decode than large-v3; small-GPU friendly | **Best default** for Persian on small hardware |
| `large-v3` | Best (general) | Slower, more memory | You have a GPU and want max accuracy |
| `medium` | OK | Moderate | Middle ground |
| `small` | Weak on Persian | Fastest, lowest RAM | CPU-only and you need speed |

> For **non-English** audio, `large-v3` / `large-v3-turbo` clearly beat the
> smaller models. `turbo` shares large-v3's encoder but uses a much smaller
> decoder, so it's far faster at near-identical accuracy — the best fit for your
> constraints.

Change it:
```env
WHISPER_MODEL=large-v3      # or small, medium, large-v3-turbo
WHISPER_LANGUAGE=fa         # pin Persian; blank to auto-detect
```

### Best-in-class Persian (optional): use a Persian fine-tuned Whisper

Models like [`vhdm/whisper-large-fa-v1`](https://huggingface.co/vhdm/whisper-large-fa-v1)
(built on the large-v3-turbo backbone with curated Persian data) can beat the
generic models on Persian. To use one with faster-whisper, convert it to
CTranslate2 once, then point `WHISPER_MODEL` at the local folder:

```bash
pip install ctranslate2 transformers[torch]
ct2-transformers-converter \
  --model vhdm/whisper-large-fa-v1 \
  --output_dir /models/whisper-fa --quantization int8
# then in .env:
#   WHISPER_MODEL=/models/whisper-fa
```

## Summarization LLM (Ollama)

| Model | Persian | Footprint | License | Notes |
| --- | --- | --- | --- | --- |
| **`gemma4:e2b-it-qat`** (default) | Good | **~4.3 GB** | Gemma (commercial OK) | Newest **QAT int4**; 140+ langs; 128K context; fits CPU / 2–6 GB GPU |
| `gemma4:e4b-it-qat` | Better | ~6.1 GB | Gemma | Recommended upgrade if you have ~8 GB GPU or CPU+RAM |
| `gemma4:12b-it-qat` | Best (of these) | larger | Gemma | If you have the RAM/GPU |
| `qwen2.5:7b-instruct` | Good | ~4.7 GB | Apache-2.0 | Solid alternative, no "thinking mode" quirks |
| `partai/dorna-llama3` | Persian-specialized | ~4.7 GB | Llama 3 (commercial OK) | Fine-tuned on Persian |
| `qwen3.5:4b` | Good | ~2.5 GB | Apache-2.0 | 256K context, but "thinking mode" can interfere with strict JSON |
| `aya-expanse:8b` | Excellent | ~5 GB | **CC-BY-NC** ⚠️ | Great Persian, but **non-commercial** — avoid for business use |

> **Why QAT?** Quantization-Aware Training keeps int4 quality close to the
> full-precision model while cutting memory ~70% — ideal for on-device/small-GPU.

Change it:
```env
OLLAMA_MODEL=gemma4:e4b-it-qat
SUMMARY_LANGUAGE=auto      # auto = write minutes in the meeting's language (Persian)
                           # or set fa / en to force a language
```
After changing, pull it: `make pull-model OLLAMA_MODEL=gemma4:e4b-it-qat`
(or it auto-pulls on the next meeting).

> Requires a **recent Ollama** (Gemma 4 support, mid-2026+). The
> `ollama/ollama:latest` image used here is fine.

## Speaker diarization (optional) — "who said what"

Off by default (it needs PyTorch + a gated model). When enabled we use
`pyannote/speaker-diarization-community-1` (more accurate than 3.1).

To enable on single-stream recordings:
1. Build the diarization-capable image (adds PyTorch): see
   `app/requirements-diarization.txt`.
2. Get a free [HuggingFace token](https://huggingface.co/settings/tokens) and
   accept the model terms (one-time, online).
3. Set in `.env`:
   ```env
   DIARIZATION_ENABLED=true
   HUGGINGFACE_TOKEN=hf_xxx
   ```

> **Tip:** For Jitsi/VoIP you can get *perfect* speaker separation without
> diarization by capturing **per-participant / per-channel** audio. See
> [JITSI-INTEGRATION.md](JITSI-INTEGRATION.md) and [ROADMAP.md](ROADMAP.md).

## Hardware sizing

| Setup | Transcription speed | LLM | Recommended models |
| --- | --- | --- | --- |
| 4-core CPU, 16 GB RAM | ~0.3–0.8× real time | works (slower) | `large-v3-turbo` + `gemma4:e2b-it-qat` |
| 2–4 GB GPU | near real time | fast | `large-v3-turbo` + `gemma4:e2b-it-qat` |
| 6–8 GB GPU | real time | fast | `large-v3` + `gemma4:e4b-it-qat` |

## Sources / further reading

- faster-whisper — https://github.com/SYSTRAN/faster-whisper
- Whisper turbo vs large-v3 for non-English — https://modal.com/blog/choosing-whisper-variants
- Persian Whisper fine-tune — https://huggingface.co/vhdm/whisper-large-fa-v1
- Gemma 4 QAT on Ollama — https://ollama.com/library/gemma4/tags ·
  https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
- Qwen on Ollama — https://ollama.com/library/qwen3
- Aya Expanse (note: CC-BY-NC) — https://ollama.com/library/aya-expanse
- pyannote diarization — https://github.com/pyannote/pyannote-audio
- Persian LLM benchmarking — https://arxiv.org/html/2510.12807v1

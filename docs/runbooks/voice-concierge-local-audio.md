# Runbook — Voice concierge local audio

This runbook covers the local-first audio runtime behind the voice concierge prototype:
whisper.cpp STT, Silero VAD, and Chatterbox multilingual TTS. It is not a cloud
deployment dependency and must not be installed as part of the base backend image.

## Runtime boundary

- **Pro/Mini only**: real runtime and deep doctor checks belong on `Nuzantara` or `Mini-Pro2`.
- **Air-M5**: static/unit-test surface only. Do not install or pull heavy audio runtimes on Air.
- **No cloud fallback**: local audio providers use `LOCAL_ONLY_PROVIDER_POLICY` and must not send
  voice, transcripts, or synthesis text to third-party endpoints.
- **Model choice**: production readiness requires Whisper `large-v3-turbo`. Smaller Whisper
  models are benchmark/dev-only.

## Overlay install

Run on Pro or Mini after the normal backend environment is healthy:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
python -m pip install --require-virtualenv --no-deps -r requirements-local-audio.txt
```

Do not drop `--no-deps`. `requirements-local-audio.txt` is intentionally an overlay because
`chatterbox-tts` declares strict transitive pins that should not rewrite the deployable backend
dependency graph.

## Environment

Set these in the local Pro/Mini backend `.env` or shell:

```bash
VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED=true
VOICE_CONCIERGE_LOCAL_AUDIO=true
VOICE_CONCIERGE_WHISPER_BINARY=/opt/homebrew/bin/whisper-cli
VOICE_CONCIERGE_WHISPER_MODEL=/Users/nuzantara/models/whisper/ggml-large-v3-turbo.bin
VOICE_CONCIERGE_WHISPER_TIMEOUT_SECONDS=30
VOICE_CONCIERGE_AUDIO_MAX_BYTES=10485760
VOICE_CONCIERGE_TTS_MAX_CHARS=1200
VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES=10485760
VOICE_CONCIERGE_SILERO_MODULE=silero_vad
VOICE_CONCIERGE_SILERO_SAMPLING_RATE=16000
VOICE_CONCIERGE_SILERO_THRESHOLD=0.5
VOICE_CONCIERGE_SILERO_TIMEOUT_SECONDS=15
VOICE_CONCIERGE_CHATTERBOX_MODULE=chatterbox
VOICE_CONCIERGE_CHATTERBOX_MODEL_PATH=/Users/nuzantara/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/<snapshot-id>
VOICE_CONCIERGE_CHATTERBOX_T3_MODEL=v3
VOICE_CONCIERGE_CHATTERBOX_LANGUAGE=en
VOICE_CONCIERGE_CHATTERBOX_TIMEOUT_SECONDS=60
VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7880/healthz
VOICE_CONCIERGE_LIVEKIT_WORKER_TIMEOUT_SECONDS=3
DO_NOT_TRACK=1
HF_DATASETS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

`VOICE_CONCIERGE_CHATTERBOX_MODEL_PATH` may be omitted if the local HuggingFace cache already
contains a complete `ResembleAI/chatterbox` snapshot.

For the Next.js audio bridge, set `VOICE_CONCIERGE_BACKEND_API_KEY` in `apps/mouth/.env.local`.
That key must be a dedicated voice bridge secret and must also be present in the backend `API_KEYS`
allowlist. The frontend intentionally does not fall back to broad `API_KEYS`.

## Doctor

Static mode validates config, filesystem, import specs, local-only policy, checkpoint presence,
caps, and offline guard env. It does not instantiate Silero or Chatterbox models:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/local_audio_doctor.py --mode static --json
```

Deep mode is gated to Pro/Mini and exercises the local runtime:

- Whisper runs a small local `whisper-cli` smoke check against the configured model.
- Silero validates the runtime import path.
- Chatterbox loads the local multilingual model snapshot.
- LiveKit worker health must return HTTP 2xx from
  `VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL`.

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/local_audio_doctor.py --mode deep --json
```

From Air-M5, route real checks over SSH:

```bash
ssh pro 'cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python scripts/local_audio_doctor.py --mode static --json'
```

Deep checks on Air-M5 should fail closed. That is expected and protects the thin-client boundary.

## Expected failures

- `local_audio_enabled: fail`: set one of the local audio flags to `true`.
- `whisper_model: fail`: install or point `VOICE_CONCIERGE_WHISPER_MODEL` at the local model file.
- `whisper_model_quality: fail`: the configured model is not `large-v3-turbo`.
- `chatterbox_checkpoint: fail`: local checkpoint files are incomplete or the cache is missing.
- `silero_import: fail`: the overlay runtime is not installed in the active venv.
- `offline_env: warn`: set the offline guard env before runtime verification.
- `livekit_agent: warn`: static mode is missing
  `VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL`.
- `livekit_agent: fail`: deep mode could not reach a healthy LiveKit worker, the health URL is
  missing/invalid, the timeout is invalid, or the worker returned non-2xx.

If deep mode returns local audio warm-check results plus `livekit_agent: fail`, use the provider
results to fix Whisper/Silero/Chatterbox and then start or repair the LiveKit worker health
endpoint before treating the report as production-green.

## Promotion rule

The lab UI can remain available for experiments, but production voice should not be considered
ready unless:

1. Static doctor is green on Pro/Mini.
2. Deep doctor is green on the intended runtime host, including a passing LiveKit worker health
   check.
3. The route still fails closed when local audio is disabled.
4. No voice/transcript path falls back to cloud providers for client data.

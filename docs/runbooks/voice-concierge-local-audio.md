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

Install the LiveKit worker runtime separately. The doctor only talks to the worker through its
loopback health endpoint, so this can live in a dedicated local venv instead of the deployable
backend image:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
python3 -m venv .venv-livekit-worker
source .venv-livekit-worker/bin/activate
python -m pip install -r requirements-livekit-worker.txt
```

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
VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7889/healthz
VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_TIMEOUT_SECONDS=2
VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL=http://127.0.0.1:7888/
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=replace-me-local-livekit-api-key
LIVEKIT_API_SECRET=replace-me-local-livekit-api-secret
VOICE_CONCIERGE_LIVEKIT_AGENT_NAME=voice-concierge-local
VOICE_CONCIERGE_CHATTERBOX_MODULE=chatterbox
VOICE_CONCIERGE_CHATTERBOX_MODEL_PATH=/Users/nuzantara/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/<snapshot-id>
VOICE_CONCIERGE_CHATTERBOX_T3_MODEL=v3
VOICE_CONCIERGE_CHATTERBOX_LANGUAGE=en
VOICE_CONCIERGE_CHATTERBOX_TIMEOUT_SECONDS=60
VOICE_CONCIERGE_PKUSEG_CACHE_DIR=/Users/nuzantara/.pkuseg
DO_NOT_TRACK=1
HF_DATASETS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

`VOICE_CONCIERGE_CHATTERBOX_MODEL_PATH` may be omitted if the local HuggingFace cache already
contains a complete `ResembleAI/chatterbox` snapshot.

Before deep verification, run the local bootstrap guard on Pro/Mini. It does not download model
assets. It only verifies the `~/.pkuseg` asset cache and confirms that the installed Chatterbox
runtime can select the v3 multilingual T3 checkpoint:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/bootstrap_local_audio_runtime.py --json
```

If Chatterbox is the legacy `0.1.7` layout, apply the local v3 selector patch after the runtime
assets have already been provisioned:

```bash
PYTHONPATH=. python scripts/bootstrap_local_audio_runtime.py --apply --json
```

If `spacy-pkuseg` has been staged in a separate local directory, copy it into the runtime cache
without network access:

```bash
PYTHONPATH=. python scripts/bootstrap_local_audio_runtime.py \
  --pkuseg-source-dir /path/to/provisioned/.pkuseg \
  --json
```

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
- LiveKit worker health calls the configured loopback URL with proxy env disabled.

Set the LiveKit health URL only to a same-host endpoint:

```bash
export VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7889/healthz
export VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_TIMEOUT_SECONDS=2
```

The doctor rejects non-loopback hosts, credentials, query strings, and fragments in this URL.

Start the local worker with a JSON health sidecar plus the native LiveKit Agents health server.
The doctor points at the sidecar `/healthz`, which returns `200` only when the LiveKit server is
reachable and the native worker metadata matches the expected local agent. LiveKit's native
`GET /` returns text `OK`; it is useful for debugging but is not sufficient for production
promotion because it can be `200` during connection retries.

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv-livekit-worker/bin/activate
export VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7889/healthz
export VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL=http://127.0.0.1:7888/
export LIVEKIT_URL=ws://127.0.0.1:7880
export LIVEKIT_API_KEY=replace-me-local-livekit-api-key
export LIVEKIT_API_SECRET=replace-me-local-livekit-api-secret
export DO_NOT_TRACK=1
export HF_DATASETS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
python scripts/local_livekit_voice_worker.py start
```

In another shell on the same host:

```bash
curl -fsS http://127.0.0.1:7889/healthz
curl -fsS http://127.0.0.1:7888/
curl -fsS http://127.0.0.1:7888/worker
```

From Air-M5, remember that `127.0.0.1` is the Air itself. To inspect a Pro worker in the browser,
open an SSH tunnel first:

```bash
ssh -N -L 7889:127.0.0.1:7889 pro
```

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

## LiveKit audio E2E smoke

The deep doctor proves provider readiness and worker health. The E2E smoke below proves a real
local LiveKit room path: publish input audio, run local VAD/STT/TTS, publish the TTS WAV back into
the same room, and optionally play the TTS output on the local speaker.

Install the LiveKit SDK into the verification venv if it is not already present:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
python -m pip install --require-virtualenv -r requirements-livekit-worker.txt
```

For a true microphone and speaker check, run from a local Pro/Mini GUI session with microphone
permission available to the terminal app:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/local_livekit_audio_e2e.py \
  --mic-seconds 4 \
  --play-output \
  --json
```

If the terminal does not have microphone access yet, macOS TCC will block recording. Grant the
terminal app microphone permission and rerun. Over SSH, use a local WAV fixture instead; that is
useful for CI-style smoke but does not satisfy the hardware microphone check:

```bash
PYTHONPATH=. python scripts/local_livekit_audio_e2e.py \
  --input-wav /path/to/local/input.wav \
  --json
```

`--synthetic-input` is only a transport smoke because the tone is not a meaningful speech sample.
Use it to validate LiveKit publication and TTS output when no microphone or fixture is available.

## LaunchAgent persistence

To keep the local LiveKit server and worker alive after reboot on Pro/Mini, create the local env
file first:

```bash
mkdir -p ~/.config/nuzantara
cat > ~/.config/nuzantara/local-livekit.env <<'EOF'
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=replace-me-local-livekit-api-key
LIVEKIT_API_SECRET=replace-me-local-livekit-api-secret
VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7889/healthz
VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL=http://127.0.0.1:7888/
VOICE_CONCIERGE_LIVEKIT_AGENT_NAME=voice-concierge-local
VOICE_CONCIERGE_LIVEKIT_BIND=127.0.0.1
DO_NOT_TRACK=1
HF_DATASETS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
EOF
```

Then install or reload the two per-user agents:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
bash deploy/launchd/install_local_livekit_audio.sh
launchctl list | grep com.nuzantara.local-livekit
curl -fsS http://127.0.0.1:7889/healthz
```

After reboot, rerun the curl health check and the deep doctor before treating the machine as H24
voice-ready.

## Expected failures

- `local_audio_enabled: fail`: set one of the local audio flags to `true`.
- `whisper_model: fail`: install or point `VOICE_CONCIERGE_WHISPER_MODEL` at the local model file.
- `whisper_model_quality: fail`: the configured model is not `large-v3-turbo`.
- `chatterbox_checkpoint: fail`: local checkpoint files are incomplete or the cache is missing.
- `chatterbox_pkuseg_asset: fail`: `~/.pkuseg` is incomplete; run the bootstrap script after
  provisioning the local `spacy-pkuseg` asset.
- `silero_import: fail`: the overlay runtime is not installed in the active venv.
- `offline_env: warn`: set the offline guard env before runtime verification.
- `livekit_agent: warn`: static mode is reminding you to configure the local worker health URL.
- `livekit_agent: fail`: the health URL is missing, unsafe, unreachable, returns non-2xx, or does
  not report a healthy worker.

If deep mode returns local audio warm-check results plus `livekit_agent: fail`, use the provider
results to fix Whisper/Silero/Chatterbox, then start or fix the LiveKit worker before treating the
overall report as production-green.

## Promotion rule

The lab UI can remain available for experiments, but production voice should not be considered
ready unless:

1. Static doctor is green on Pro/Mini.
2. Deep doctor is green on the intended runtime host, including a passing LiveKit worker health
   check.
3. The route still fails closed when local audio is disabled.
4. No voice/transcript path falls back to cloud providers for client data.

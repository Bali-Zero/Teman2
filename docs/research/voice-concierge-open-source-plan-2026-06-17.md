# Voice Concierge Open Source Plan

Date: 2026-06-17  
Scope: production-grade, local-first voice concierge for Nuzantara/Bali Zero  
Status: planning artifact; no runtime changes

## Decision

Build the production voice concierge as a local-first audio pipeline with replaceable components:

```
browser/WebRTC or websocket
  -> VAD / turn detection
  -> local STT on Pro/Mini
  -> PII boundary and intent router
  -> Nuzantara tools / LLM layer
  -> local TTS
  -> streamed audio reply
```

The recommended production target is:

| Layer | Primary choice | Why |
| --- | --- | --- |
| Realtime orchestration | LiveKit Agents for production, Pipecat for local MVP/challenger | LiveKit is stronger for WebRTC, rooms, future SIP/phone. Pipecat is faster to prototype and easier to run as a Python pipeline. |
| STT | whisper.cpp `large-v3-turbo` first; MLX Whisper as Apple Silicon challenger | whisper.cpp is already installed on Pro and has server/streaming binaries. MLX may win latency on Apple Silicon. |
| VAD / turn detection | Silero VAD | Mature, small, local, permissive license. |
| TTS | Chatterbox first for premium voice; Kokoro/Piper as latency fallback | Chatterbox is already aligned with WR3 local TTS doctrine. Kokoro/Piper are simpler low-latency fallbacks. |
| Diarization | Defer | 1:1 concierge does not need it; add WhisperX/pyannote only for meetings/calls. |
| Wake word | Defer; openWakeWord later | Not needed for push-to-talk/browser concierge. |

## Cleanup Decision

Do not install every high-quality voice package discovered in research. The selected production path is intentionally narrow:

| Status | Software / path | Decision |
| --- | --- | --- |
| Keep | `whisper.cpp` on Pro/Mini | Primary local STT path; reuse installed binary first. |
| Keep | Chatterbox local TTS | Premium local TTS path; aligned with WR3 local voice doctrine. |
| Keep | Silero VAD | Turn detection / barge-in layer. |
| Keep | LiveKit Agents + Pipecat | LiveKit is the production orchestration target; Pipecat is the local MVP/challenger harness. |
| Lab only | Browser Web Speech API | Useful for the current browser demo, not a production STT/TTS path. |
| Retired | `/api/voice/elevenlabs/kbli-audit` | Legacy vendor webhook; now fails closed with HTTP 410. |
| Legacy only | `AudioService` Pollinations/OpenAI audio path | Keep existing contracts until the local adapter replaces them; do not wire into the new concierge. |
| Benchmark only | Kokoro, Piper, MLX Whisper | Evaluate only if Chatterbox/whisper.cpp miss latency or quality targets. |
| Do not install now | CosyVoice, F5-TTS, FunASR/SenseVoice, sherpa-onnx, WhisperX, openWakeWord | Research/challenger options; not part of the first production build. |

## Grounding

### Current repo state

- The local voice concierge prototype exists in `apps/mouth/src/app/(workspace)/intelligence/voice-concierge/` and `apps/mouth/src/app/api/lab/voice-concierge/`.
- The existing backend audio service is still cloud-oriented: `Pollinations.ai` TTS first, OpenAI fallback, OpenAI Whisper for STT.
- Existing frontend SDK methods already call `/api/audio/transcribe` and `/api/audio/speech`; reuse those contracts rather than inventing a parallel client API.
- Existing security audit already flags `/api/audio/` as cost/resource sensitive and requiring strict auth/rate limiting.
- WR3 already encodes a local audio doctrine: Chatterbox local TTS, banned cloud TTS vendors, and explicit local-sovereignty lint.

### Pro local state

Verified on `nuzantara@Nuzantara`:

- `openai-whisper 20250625_4` is installed at `/opt/homebrew/bin/whisper`.
- `whisper.cpp 1.8.4` is installed with `whisper-cli`, `whisper-server`, `whisper-stream`.
- `whisper.cpp` loads Metal/BLAS backend on Pro.
- No standard local whisper.cpp model files were found in the usual cache/share paths during this pass.

## Reuse-First Matrix

Metadata collected via GitHub API on 2026-06-17.

| Component | Repo | License | Stars | Action |
| --- | --- | ---: | ---: | --- |
| Realtime voice production | `livekit/agents` | Apache-2.0 | 11010 | Install/library integration; inspect examples and deployment model. |
| Local voice pipeline MVP | `pipecat-ai/pipecat` | BSD-2-Clause | 12857 | Install/library integration; inspect local/audio and LiveKit transport patterns. |
| Local STT on Mac | `ggml-org/whisper.cpp` | MIT | 50787 | Reuse installed binary first; no vendoring needed. |
| VAD | `snakers4/silero-vad` | MIT | 9343 | Install/library integration or consume via wrapper. |
| Premium TTS | `resemble-ai/chatterbox` | MIT | 25095 | Pilot as premium voice path; verify Mac/MPS performance. |
| Lightweight TTS | `hexgrad/kokoro` | Apache-2.0 | 7510 | Benchmark as low-latency fallback. |
| Multilingual TTS | `FunAudioLLM/CosyVoice` | Apache-2.0 | 21687 | Research lane only; likely heavier. |
| Zero-shot TTS | `SWivid/F5-TTS` | MIT | 14768 | Research lane only; likely too slow for realtime MVP. |
| Multilingual ASR | `modelscope/FunASR` | MIT | 18183 | Benchmark SenseVoice/FunASR as challenger. |
| SenseVoice model code | `FunAudioLLM/SenseVoice` | NOASSERTION in GitHub API | 8592 | Do not copy until license is manually verified. Pattern/research only. |
| Faster Whisper | `SYSTRAN/faster-whisper` | MIT | 23676 | Good Linux/CTranslate2 option; lower priority on Apple Silicon. |
| Apple MLX examples | `ml-explore/mlx-examples` | MIT | 8741 | Inspect Whisper example; use as Apple Silicon challenger. |
| Unified offline speech toolkit | `k2-fsa/sherpa-onnx` | Apache-2.0 | 13028 | Red-team/challenger path for STT+VAD+TTS in one toolkit. |
| Word timestamps/diarization | `m-bain/whisperX` | BSD-2-Clause | 22525 | Defer until meeting/call workflows. |
| Wake word | `dscripka/openWakeWord` | Apache-2.0 | 2401 | Defer until always-on mode. |

Classification:

- `[INSTALLA-LIB]`: LiveKit Agents, Pipecat, Silero VAD, Chatterbox.
- `[USA-BINARIO]`: whisper.cpp on Pro.
- `[STUDIA-PATTERN-RISCRIVI]`: SenseVoice until license/model terms are manually verified.
- `[BENCHMARK-ONLY]`: Kokoro, Piper, MLX Whisper.
- `[DEFER]`: WhisperX/diarization, wake word, full SIP, CosyVoice, F5-TTS, FunASR/SenseVoice, sherpa-onnx, openWakeWord.

## Multi-LLM Panel

Roles used:

- Codex orchestrator: final decision and Nuzantara constraints.
- Gemini (`agy`): breadth scout; argued for Pipecat + MLX Whisper + Kokoro because it is lighter for an Apple Silicon MVP.
- Codex CLI (`gpt-5.5`): repo reviewer; found existing `AudioService`, frontend audio SDK, and cloud-oriented audio path that should be replaced rather than duplicated.
- DeepSeek V4 Pro: red-team; argued for a more conservative Pipecat + sherpa-onnx + Piper stack to reduce realtime complexity.

Panel synthesis:

- Everyone agrees the browser Web Speech API is not a production path.
- The split is orchestration-heavy vs MVP-light:
  - LiveKit first is better if production WebRTC/phone is the near-term target.
  - Pipecat first is better if we want the fastest local pipeline and benchmark harness.
- TTS is the main quality/latency risk:
  - Chatterbox is the premium path and aligns with WR3.
  - Kokoro/Piper are fallback paths if Chatterbox misses realtime latency.
- STT should be benchmarked, not chosen by reputation:
  - whisper.cpp is the fastest path because it is already installed.
  - MLX Whisper may beat it on Apple Silicon.
  - FunASR/SenseVoice and sherpa-onnx are challengers, not first integration.

## Implementation Plan

### Phase 0: Safety and benchmark harness

Goal: measure before architecture lock-in.

Tasks:

1. Create `apps/backend-rag/backend/app/services/local_audio/` with thin wrappers only.
2. Add a benchmark script that accepts fixed audio fixtures and measures:
   - STT word error rate by manual expected transcript.
   - time to first partial transcript.
   - total transcription time.
   - TTS time to first audio.
   - total TTS render time.
   - memory/CPU/GPU pressure where measurable.
3. Build a 30-sample local fixture set:
   - Italian owner/operator voice.
   - English client voice.
   - Indonesian operational phrases.
   - noisy office/Bali environment.
   - domain terms: PT PMA, KITAS, NPWP, KBLI, leasehold, nominee, tax residency.
4. Add PII fixture rules using fake placeholders only.

Acceptance:

- No real client PII in fixtures.
- Benchmark command runs on Pro.
- Metrics exported as JSON.

### Phase 1: Local STT adapter

Goal: replace cloud STT for concierge path.

Primary:

- Use `whisper.cpp` on Pro with `large-v3-turbo` if latency allows; test smaller quantized models as fallback.
- Expose a local FastAPI provider behind the existing audio contracts.

Challengers:

- MLX Whisper.
- FunASR/SenseVoice.
- sherpa-onnx.

Acceptance:

- Concierge can transcribe browser audio without OpenAI/Pollinations.
- PII guard runs before text enters any cloud LLM path.
- Average local STT latency target: under 1.0x realtime for short utterances.

### Phase 2: VAD and barge-in

Goal: make conversation usable, not push-to-record.

Primary:

- Integrate Silero VAD in the backend audio pipeline.

Acceptance:

- Detect speech start/stop on fixture audio.
- Barge-in can cancel TTS playback and pending LLM generation.
- False barge-in rate acceptable in noisy sample set.

### Phase 3: Local TTS adapter

Goal: stop using cloud TTS for concierge responses.

Primary:

- Chatterbox local TTS, reusing WR3 doctrine and config where possible.

Fallbacks:

- Kokoro for latency.
- Piper for robustness/low compute.

Acceptance:

- First-audio latency target: under 1.2s for short replies.
- Audio is understandable in English/Italian; Indonesian pronunciation manually rated.
- Provider is swappable with one config value.

### Phase 4: Orchestration decision

Goal: decide LiveKit-first vs Pipecat-first with data.

Path A: Pipecat-first

- Best for local MVP and faster integration.
- Use if websocket browser pipeline is enough for next 30 days.

Path B: LiveKit-first

- Best for production concierge, WebRTC, future SIP/phone.
- Use if browser realtime and phone are the next target.

Decision gate:

- If TTFA and barge-in are stable in Pipecat within 2 implementation days, ship Pipecat MVP and wrap with LiveKit later.
- If browser/WebRTC session reliability dominates the work, move directly to LiveKit Agents.

### Phase 5: Production hardening

Required before production exposure:

- Auth on all audio routes.
- Strict per-user and per-IP rate limits.
- Max audio duration and max text length.
- Local-only mode for STT/TTS by default.
- Audit log with redacted transcript metadata, not raw transcript.
- No raw audio persistence unless explicitly enabled for debugging.
- Feature flag: `VOICE_CONCIERGE_PRODUCTION_ENABLED`.
- Canary release only to internal users first.

## Recommended First Sprint

1. Add local provider interfaces:
   - `LocalSTTProvider`
   - `LocalTTSProvider`
   - `TurnDetector`
2. Add `WhisperCppSTTProvider` using installed Pro binary.
3. Add benchmark fixtures and JSON metrics.
4. Add `ChatterboxTTSProvider` stub plus runtime check; if not installed, return clear unavailable status.
5. Wire the lab route to use local STT/TTS only when `VOICE_CONCIERGE_LOCAL_AUDIO=true`.
6. Keep Gemini text concierge as a separate non-PII router; do not mix raw audio with Gemini.

## Kill Criteria

Stop or pivot if:

- Time-to-first-audio stays above 1.5s after sentence chunking and model fallback.
- STT misses domain terms at a rate that makes lead intake unsafe.
- Chatterbox cannot run reliably on Pro/Mini without thermal or memory issues.
- Auth/rate-limit cannot be enforced on every audio entrypoint.
- Any candidate has unclear or incompatible licensing for production use.

## Sources

- LiveKit Agents: https://github.com/livekit/agents
- Pipecat: https://github.com/pipecat-ai/pipecat
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- Silero VAD: https://github.com/snakers4/silero-vad
- Chatterbox: https://github.com/resemble-ai/chatterbox
- Kokoro: https://github.com/hexgrad/kokoro
- CosyVoice: https://github.com/FunAudioLLM/CosyVoice
- F5-TTS: https://github.com/SWivid/F5-TTS
- FunASR: https://github.com/modelscope/FunASR
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- MLX examples Whisper: https://github.com/ml-explore/mlx-examples
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
- WhisperX: https://github.com/m-bain/whisperX
- openWakeWord: https://github.com/dscripka/openWakeWord

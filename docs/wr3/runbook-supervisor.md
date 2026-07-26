---
name: wr3-supervisor-runbook
description: Runbook for scripts/wr3_supervisor.py (S7.5). Step-by-step operational procedures for starting/stopping/recovering the WR3 episode pipeline.
status: PLACEHOLDER (S7.5 implements supervisor; this runbook expands then)
---

# WR3 Supervisor Runbook

> **Status: PLACEHOLDER.** `scripts/wr3_supervisor.py` does not exist yet — implementation lands at S7.5. This runbook is seeded with operational structure so it can be expanded inline with implementation.

## Start

```bash
# (S7.5 will implement)
cd ~/nuzantara
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=apps/backend-rag/backend python scripts/wr3_supervisor.py
```

Expected stdout:

```
[wr3-supervisor] Loaded router from docs/wr3/contracts/_router.yaml (6 channels)
[wr3-supervisor] Loaded precedence from docs/wr3/symbiosis-precedence.md
[wr3-supervisor] Connected to PG (LISTEN on 6 channels)
[wr3-supervisor] Outbox replay on reconnect: 0 unconsumed events
[wr3-supervisor] Ready.
```

## Stop

`Ctrl+C` or `kill -SIGTERM <pid>`. Supervisor flushes outbox state on shutdown.

## Recover from stuck episode

1. Identify episode slug: `ls apps/war-room/output/episode/`
2. Check current state via manifest: `cat apps/war-room/output/episode/<slug>/episode_manifest.json | jq .stage`
3. Manual retry: `python scripts/wr3_supervisor.py --retry <slug> --from-stage <stage>`

## Telegram P0 channel

Failures emit to chat_id 1125336968 (Zero) via `~/scripts/telegram-notify.sh`.
Includes: episode slug, agent, failure reason, retry attempt count.

## Cron LaunchAgents

S7.5 will install:

- `com.balizero.wr3.supervisor.plist` (KeepAlive=true, RunAtLoad=true)
- `com.balizero.wr3.reflexion.weekly.plist` (Sun 02:30 WITA)
- `com.balizero.wr3.yt-metrics.weekly.plist` (Mon 06:00 WITA)
- `com.balizero.wr3.editorial-bench.monthly.plist` (1st Mon 07:00 WITA)

## Audio architecture

> **Decision 2026-05-22 (Antonello, verbatim):**
> _"usiamo audio nativo, chatterbox come fallback. facciamo tante prove per la
> voce. /Users/nuzantara/Desktop/logo/pilot-A-veo-zantara-lipsync.mp4 in questo
> video e' perfetta. perche se abbiamo poi tanto audio, potremo clonare la voce
> e perfino l'avatar"._
>
> Override of the agy+DeepSeek panel (2/2 NEEDS_FIX on Veo audio): empirical
> pilot beats LLM redteam. Empirica > LLM.

### Primary path — Veo audio nativo

`wr3-clip-renderer` requests `audio=native` on every Flow API submit (env
`WR3_VEO_AUDIO=native|off`, default `native`). Each `clips/<n>.mp4` carries an
embedded AAC stereo 48 kHz audio track (VO + ambient).

`wr3-audio-asset-producer` Step 0 probes `clips/` for embedded audio via
`ffprobe -select_streams a`. If present (the normal case), it runs:

```bash
python scripts/wr3_veo_audio_extract.py \
  --episode-dir apps/war-room/output/episode/<slug> \
  --episode-id <slug>
```

The script extracts per-clip audio, concatenates to `audio/vo.wav`, measures
LUFS into `audio/lufs_report.json`, applies a corrective `ffmpeg loudnorm` pass
if the overall LUFS is outside `[-15, -13]`, and copies the final `vo.wav` to
`~/Desktop/Zantara-Voice-Corpus/<episode_id>.wav` (voice corpus accumulator).

Exit codes:

- `0` — Veo audio OK, corpus updated, continue to music + license.
- `75` (`EX_TEMPFAIL`) — overall LUFS catastrophic (`>±5` from `-14`) → cascade
  to Chatterbox fallback.
- `70` (`EX_SOFTWARE`) — audio missing/corrupt on at least one clip → cascade
  to Chatterbox fallback.

### Fallback path — Chatterbox local Emma seed

When the Veo extract returns `70` or `75`, the producer cascades to
`scripts/wr3_chatterbox_runner.py --mode=fallback` (Emma seed=42 cfg=0.30
temperature=0.70 exaggeration=0.32). The fallback writes the same outputs (
`vo.wav` + voice-corpus copy tagged `source=chatterbox` in the manifest) and
emits the same `wr3_episode_assembly_ready` channel. If Chatterbox ALSO crashes
the producer emits `degrade_loud` (music + subtitles only).

### Voice corpus accumulator

`~/Desktop/Zantara-Voice-Corpus/<episode_id>.wav` — one file per episode,
PCM s16le 48 kHz stereo, LUFS -14 ±1. At ~50 wav we run a custom Chatterbox
training run to replace the Emma seed with a Zantara-trained model. At ~100 wav
we look at avatar lipsync (Wav2Lip / SadTalker) — out-of-scope for WR3 v0,
candidate for WR4. README lives next to the wavs (`~/Desktop/Zantara-Voice-Corpus/README.md`).

### Symbiosis Law 6 posture

Veo audio nativo is byproduct of an EXISTING cloud touchpoint (Flow API for
clip-renderer). No new vendor surface added. Cartesia and ElevenLabs remain
BANNED. Chatterbox is the only local TTS fallback. Lint
`scripts/lint/wr3_lint_cloud_dependency.py` is unchanged — it still rejects
new TTS vendor references.

## Companion mode (WR2 → WR3 handoff)

When the WR2 carousel pipeline successfully publishes an episode (Canva apply + Drive staged + Telegram P0), the WR2 supervisor emits a `wr2_episode_published` PG NOTIFY event (migration `186_wr2_published_channel.sql`). The WR3 supervisor consumes this channel and routes it to `wr3-design-architect` under the **`companion_from_carousel`** mode — declared in `docs/wr3/contracts/modes/companion-mode.yaml`.

### Three sub-modes

| Sub-mode              | Activation                                                               | Output                                      | Duration                     | Clips   | Cost ceiling                        | Critic lanes                             |
| --------------------- | ------------------------------------------------------------------------ | ------------------------------------------- | ---------------------------- | ------- | ----------------------------------- | ---------------------------------------- |
| `episode`             | **automatic** (every publish, unless `companion_skip=true` in WR2 brief) | IG Reel / TikTok / Shorts, EN + ID cuts     | 60s default, 60–150s allowed | 8–19×8s | 80 cr @60s … 190 cr (~$0.475) @150s | Full 4-lane                              |
| `story_15s`           | opt-in via WR2 brief `companion_story=true` (Antonello `--story`)        | IG Story 9:16                               | 15s (16s trimmed)            | 2×8s    | 20 cr Flow Pro (~$0.05)             | Lane 1 (Identity) + Lane 3 (Brand voice) |
| `comment_interactive` | opt-in via WR2 brief `companion_engage=true` (Antonello `--engage`)      | text-only (IG comment + DM reply templates) | 0s                           | 0       | $0.05 (Sonnet text-only)            | Lane 3 only + manual review              |

Opt-in sub-modes are additive: `--story` and `--engage` ride alongside the automatic `episode`, one companion event emitted per sub-mode.

**Changed 2026-07-26 (Zero's ruling).** WR3 is now _preordained_: "la wr3 è prestabilita e crea il video del carosello della wr2 (in due versioni uguali ma una in inglese con sottotitoli inglese e una indonesiana con sottotitoli indonesiano)", bounded to "massimo 150 secondi e minimo 60 secondi". The old `reel_60s` sub-mode is what `episode` grew out of — renamed and promoted from opt-in to automatic; `story_15s` was demoted from default to a flag. `companion_expand` is gone: a stale one in a WR2 brief is ignored, not fatal.

`[60,150]` is not a companion-mode invention — it is WR3's native envelope, declared identically in `brief-interpreter` (out-of-range = `hard_fail`), `shot-director` (60s→8 clips … 150s→19), `script-editor` and the `pre-render-gatekeeper` credit ceilings. Because companion mode sets `skip_brief_interpreter: true`, it never passes the agent that enforces that range — which is the only reason a 15-second default could exist here at all. `wr3_companion_dispatcher._assert_duration_envelope` now enforces it on the automatic path, so skipping the validator no longer means skipping the validation. `story_15s` sits outside the envelope deliberately and stays exempt: it is a human's explicit choice.

### Cost economy

Companion mode REUSES the WR2 brief verbatim:

- `primary_claim_ids` are inherited transitively (already vetted by the WR2 fact-checker — re-verification is wasteful).
- `brief-interpreter` is **SKIPPED entirely** — no NB query, no NB source_ids ever enter the room (Law 2: NB UUIDs never leak across pipelines).
- `domain` and `audience_segment` are inherited verbatim.

Net effect per companion: ~$0.20 for a 60s `episode` (~$0.475 at the 150s ceiling) against ~$0.45 of brief cost avoided on top of the render — the inheritance saves brief-interpreter's ~$0.30 NB query on every episode. The opt-in `story_15s` still lands at ~$0.05, and additionally skips critic Lane 2/4 (~$0.10); the automatic `episode` runs the full 4-lane critic, because it ships without a human in the loop.

**Empty `primary_claim_ids` skips the companion entirely** (changed 2026-07-26, was: fall back to `story_15s`). WR2 carries claim ids in 0 of 23 briefs on disk today, so the old fallback would have fired on _every_ episode and quietly reinstated the very format the ruling replaced. An episode with no inherited claims would have to be either ungrounded or re-query NotebookLM (Law 2 forbids the latter here). Skipping spends nothing and keeps the gap visible instead of degrading past it.

### Output isolation

Companion artifacts land in a separate root to avoid colliding with the standard WR3 episode tree:

```
apps/war-room/output/companion/<wr2_slug>-<sub_mode>/
  ├─ brief.json         (translated by wr3_companion_dispatcher.py)
  ├─ script.json        (script-editor, voice_register from sub-mode)
  ├─ shot-pack.json     (shot-director, single-shot for story_15s)
  ├─ clips/*.mp4
  ├─ audio/vo.wav
  ├─ master.mp4
  └─ critic-report.json (masked per sub-mode critic_lane_mask)
```

### Dispatch flow

```
WR2 supervisor                       PG eventbus                        WR3 supervisor
──────────────                       ──────────                         ──────────────
publish carousel
   │
   ▼
publish_wr2_episode_published_event(payload)
                           ──pg_notify──►
                                                                        listen wr2_episode_published
                                                                                │
                                                                                ▼
                                                                  wr3_companion_dispatcher.dispatch_companion()
                                                                                │
                                                                  resolve sub_modes from WR2 brief flags
                                                                                │
                                                                  per sub-mode: build WR3 brief.json (no NB query)
                                                                                │
                                                                  publish_wr3_event('wr3_episode_brief_requested', wr3_brief)
                                                                                │
                                                                  → standard WR3 pipeline (skip brief-interpreter)
```

### Manual replay (backfill)

```bash
# Translate-only (no emit):
python scripts/wr3_companion_dispatcher.py --wr2-slug <slug> --dry-run

# With full payload from a JSON file:
python scripts/wr3_companion_dispatcher.py --wr2-slug <slug> --payload-json /tmp/payload.json
```

### TODO — WR2 supervisor emitter

`scripts/wr2_supervisor.py` does **NOT yet** emit `wr2_episode_published`. The WR2 side of this handoff must add a call to the SQL helper after the existing Canva-apply + Drive-staged + Telegram-P0 sequence:

```python
await conn.execute(
    "SELECT publish_wr2_episode_published_event($1::jsonb)",
    json.dumps({
        "slug": slug,
        "slides_count": slides_count,
        "hero_image_path": hero_path,
        "primary_claim_ids": claim_ids,
        "domain": domain,
        "audience_segment": audience_segment,
        "brief_path": brief_path,
        "slides_path": slides_path,
    }),
)
```

Until this is wired, companion mode can only be triggered manually via the dispatcher CLI.

## See also

- `research/wr3/06-architecture-skeleton.md` — full architecture
- `docs/wr3/contracts/_schema.yaml` — contract meta-schema
- `docs/wr3/contracts/_router.yaml` — channel → agent map
- `docs/wr3/symbiosis-precedence.md` — inter-law conflict resolution
- `~/Desktop/Zantara-Voice-Corpus/README.md` — voice corpus accumulator
- `scripts/wr3_veo_audio_extract.py` — Veo audio extractor (primary path)
- `scripts/wr3_chatterbox_runner.py` — Chatterbox runner (fallback path)

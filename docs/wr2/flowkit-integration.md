# WR2 Image Generator — FlowKit Integration

> **Status**: Shipped Sprint 1.6 W3, 2026-05-03. FlowKit is the **secondary
> backend**, opt-in via `WR2_IMAGE_BACKEND=auto` (the new default). The
> existing Playwright path is preserved as fallback and remains the
> production behavior whenever FlowKit is unreachable.

## Why FlowKit

The empirical POC on 2026-05-03 (Antonello's Ultra account, see memory
`discovery_flowkit_poc_test_2026_05_03.md`) verified that FlowKit gives a
direct HTTP path to the same `GEM_PIX_2` (Nano Banana Pro) model that the
Playwright path drives via the Gemini web UI. Concrete numbers:

| Path | Latency / image | Credit cost | Setup overhead |
|---|---|---|---|
| Playwright (existing) | 30-90 s | 0 (web UI quota) | persistent Chrome profile, hover-reveal selectors |
| FlowKit (new) | 5-15 s | **0** (FREE for `PAYGATE_TIER_TWO`) | local agent on `:8100` + Chrome extension |

Same model, same image quality, **5-10× faster**, same $0 marginal cost.
The slow path is preserved because FlowKit's bearer token expires every
~45 min (extension auto-refreshes on Flow tab activity, but if the tab
sits idle the next call returns `NO_FLOW_KEY` until refresh).

## Architecture

```mermaid
flowchart LR
    DB[(Postgres<br/>war_room_drafts)] --> WR2[wr2_image_generator.py]
    WR2 -->|probe once per draft| Probe{FlowKit<br/>is_available?}
    Probe -->|yes| FK[FlowKit<br/>:8100]
    Probe -->|no| PW[Playwright<br/>Gemini web UI]
    FK -->|fails| PW
    FK --> Tigris[Tigris S3<br/>nuzantara-warroom-images]
    PW --> Tigris
    Tigris --> WR2
    WR2 -->|status=drafts_imaged| DB
```

The dispatch is per-slide but the FlowKit availability probe is **once per
draft** — we don't re-probe between slides because (a) it's wasteful and
(b) we want consistent backend choice within a single dispatch carousel.

## Env-var matrix

| Env var | Default | Purpose |
|---|---|---|
| `WR2_IMAGE_BACKEND` | `auto` | `auto` = FlowKit first, fall back to Playwright. `flowkit` = FlowKit only, raise `BackendUnavailableError` if down. `playwright` = legacy Playwright only. |
| `WR2_FLOWKIT_BASE_URL` | `http://127.0.0.1:8100` | FlowKit local agent endpoint. |
| `WR2_FLOWKIT_TIMEOUT_S` | `60` | HTTP timeout for individual FlowKit calls. |
| `WR2_FLOWKIT_MATERIAL` | `realistic` | FlowKit project material/style preset. `realistic` matches the WR2 brand bar (editorial photo aesthetic). |
| `WR2_FLOWKIT_LANGUAGE` | `en` | Project language hint. |

The existing Playwright vars (`WR2_GEMINI_PROFILE_DIR`, `WR2_IMAGE_TIMEOUT_PER_SLIDE`,
`WR2_IMAGE_MAX_RETRIES`, `WR2_IMAGE_VLM_VALIDATION` etc.) are unchanged
and still apply to the Playwright path. **`WR2_IMAGE_VLM_VALIDATION`
applies to BOTH backends** — Nano Banana Pro can also produce off-prompt
outputs and the WR2 brand bar is the same regardless of producer.

## Trigger conditions for fallback

The `auto` backend falls back to Playwright on ANY of:

1. FlowKit local agent (`:8100`) not reachable (TCP connection refused, timeout).
2. `/health` returns `extension_connected: false` (Chrome extension not loaded
   or service worker idle).
3. `/api/flow/credits` returns `NO_FLOW_KEY` (bearer token expired or
   never captured) — surfaced as HTTP 401 OR 200+detail-envelope.
4. `/api/flow/generate-image` returns 5xx, malformed JSON, or
   `detail: "MODEL_ACCESS_DENIED"` (region-blocked / model not in tier).
5. Signed CDN download fails (URL expired past 30-min TTL, or Tigris
   network issue between Pro and the CDN).
6. Local read of the downloaded PNG produces zero bytes.
7. VLM alignment validation rejects the FlowKit output (off-prompt
   stock-style content) — same threshold as Playwright (`WR2_IMAGE_MIN_ALIGN_SCORE=0.5`).

In `flowkit`-only mode the same conditions instead surface as an error in
the per-slide tuple (`(slide_number, None, error_msg)`) — there is no
Playwright fallback. The draft is marked `image_failed` if every slide
errors.

## Operational runbook

### Start FlowKit on Pro (manual, one-time per session)

```bash
# 1. Boot the local agent (assumes setup per the skill doc)
cd /tmp/flowkit-poc/flowkit
source venv/bin/activate
python -m agent.main &  # listens on :8100 (HTTP) + :9222 (extension WS)

# 2. Open the Flow tab and pin the extension (one-time per Chrome restart)
open "https://labs.google/fx/tools/flow"
# → Click the FlowKit extension icon (puzzle 🧩 → pin → click)

# 3. Verify
curl -s http://127.0.0.1:8100/health \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('connected:',d['extension_connected'])"
# connected: True

curl -s http://127.0.0.1:8100/api/flow/credits | python3 -m json.tool | head -10
# Should NOT be {"detail":"NO_FLOW_KEY"}
```

If `connected: false` after 30 s, refresh the Flow tab and click the
extension icon again — the WebSocket bridge re-establishes within ~5 s.

### Verify the WR2 cron picks up FlowKit

```bash
# Run wr2_image_generator.py manually with a known draft in 'drafts' status:
cd ~/Desktop/nuzantara
DATABASE_URL=postgresql://localhost/nuzantara_local \
  WR2_IMAGE_BACKEND=auto \
  apps/backend-rag/.venv/bin/python scripts/wr2_image_generator.py --draft-id <UUID>

# Look for these log lines:
#   FlowKit available — using as primary backend (PAYGATE_TIER_TWO)
#   [slide N] generating via FlowKit (Nano Banana Pro)
#   [slide N] FlowKit ok (8.3s, 1234567 bytes)
#   [slide N] uploading to Tigris
#   [slide N] uploaded → https://...
```

If FlowKit is down you should see instead:

```
FlowKit unavailable — using Playwright backend
[slide N] generating image (overall 1, primary attempt 1/3)
```

### Failure modes (none of which require operator action)

| Symptom | What's happening | Action |
|---|---|---|
| `FlowKit /health unreachable` (DEBUG-level log) | Local agent not running. | None — auto path falls back to Playwright. Restart agent next time you boot Chrome. |
| `FlowKit token not captured (NO_FLOW_KEY)` | Bearer expired (>45 min idle on Flow tab). | None — auto fallback. To restore primary: refresh `labs.google/fx/tools/flow` and click extension icon. |
| `FlowKit generate-image status=403 ... MODEL_ACCESS_DENIED` | Region block on the requested model (Veo 3 from Bali, etc.). | None — auto fallback. Image gen via `GEM_PIX_2` is NOT region-blocked, so this should not fire for hero images. |
| `flowkit VLM rejected (score=0.4 < 0.5)` | FlowKit output didn't match prompt (off-brand) | None — auto path falls back to Playwright; flowkit-only path returns error and slide is marked failed. |

## What does NOT change

This integration is purely additive:

- The Playwright path (`_gen_one_image`, `_gen_one_image_raw`,
  `_build_prompt_variants`) is **byte-identical** to before.
- The launchd plist (`infra/launchagents/com.balizero.wr2.image-generator.plist`)
  is **unchanged** — no new env var is set there, so production cron
  defaults to `WR2_IMAGE_BACKEND=auto` and silently uses Playwright until
  FlowKit is set up on Pro.
- DB schema, status transitions (`drafts/drafts_checked` →
  `drafts_imaged`/`image_failed`), `slides_json` shape, Tigris bucket and
  key naming convention are all unchanged.
- VLM alignment validation, retry loop, prompt variant fallback all apply
  to the Playwright path identically.

The only observable behavior difference when FlowKit IS available:
hero-slide generation drops from ~30-90s/image to ~5-15s/image, and the
`council_debate_json` `image_generated_at` timestamp closes on the draft
~3-7 minutes earlier on a 4-hero carousel.

## Anthropic SDK compliance

FlowKit's `agent/services/video_reviewer.py` has a lazy-import path that
uses the Anthropic SDK if `ANTHROPIC_API_KEY` is set. The Bali Zero setup
procedure (per the skill doc) **strips `anthropic` from
`requirements.txt`** during install, and we never call the video reviewer
from this integration — we only use `/api/flow/generate-image` and
`/api/flow/credits`. Defense in depth: even if a future FlowKit patch adds
`import anthropic` at module top, pip install will fail on the missing
package, which is the desired outcome under Golden Rule #13.

The reference implementation in `scripts/wr2_flowkit_client.py` uses only
`httpx` — no Anthropic SDK, no LLM calls.

## References

- Skill: `~/.claude/skills/nuzantara-flowkit-flow-generation.md`
- Memory: `discovery_flowkit_poc_test_2026_05_03.md`
- POC repo: `github.com/crisng95/flowkit` (MIT, OSS)
- Existing pipeline: [`wr2_image_generator.py`](../../scripts/wr2_image_generator.py)
- Sibling docs: [`docs/wr2/SUPERVISOR.md`](SUPERVISOR.md)

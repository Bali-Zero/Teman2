# WR3 anchor start-image i2v fix — design

**Date**: 2026-05-30
**Branch**: `agent/nuzantara/wr3/anchor-i2v-fix`
**Author**: Claude Opus 4.8 (orchestrated by Antonello)
**Status**: design approved → TDD implementation

## Problem

WR3 video episodes that require Zantara's face (identity token `A007`) fail the
ArcFace identity gate (`scripts/wr3_arcface_verify.py`, cosine threshold 0.6,
hard-fail 0.55). Empirically measured on episode `content-creator-3-roads-2026-05-29`:

| metric | value |
|---|---|
| overall cosine avg | 0.119 |
| overall cosine min | 0.000 |
| clips passed | 0 / 18 |

**Root cause** (verified `scripts/wr3_flowkit_client.py:509-516`): when a shot has no
`start_image_media_id`, `submit_clip` calls `_generate_start_image(prompt)`, which
POSTs `/api/flow/generate-image` with **only a text prompt** ("Zantara, woman ~35,
mediterranean features, ..."). Veo's i2v then starts from a generic woman, not the
A007 anchor face. Cosine ~0.2 follows.

## Empirical proof of fix (2026-05-30, FlowKit `127.0.0.1:8100`, TIER1P5)

Uploaded `research/marketing/zantara-visual-dataset/v1/ingredients/zantara-face-anchor-v1.png`
via `POST /api/flow/upload-image` → `media_id`, used it as `start_image_media_id` for
shot 1's prompt, polled `/api/flow/media/<id>` (6× transient 500 then READY ~48s),
ran ArcFace on the resulting clip:

| metric | text-prompt (old) | anchor start-image (new) |
|---|---|---|
| cosine avg | 0.119 | **0.912** |
| cosine min | 0.000 | **0.894** |
| faces found | 7/18 at zero | **8/8** |
| identity gate | FAIL | **PASS** |

The anchor holds identity across the full 8s clip — i2v drift is not a problem.

## Why i2v, not r2v

r2v (`/api/flow/generate-video-refs`, `reference_media_ids`) was the first choice
(conditions the whole clip on the reference, not just frame 1) but is **inaccessible
on this account**, verified empirically:

- `veo_3_1_r2v_fast_landscape_ultra_relaxed` (the TIER1P5 mapped model) → `500 INTERNAL` ×3 (not transient)
- `veo_3_1_r2v_fast_portrait` (base TIER_ONE model, via hot-reload PATCH) → `403 PUBLIC_ERROR_MODEL_ACCESS_DENIED`
- landscape aspect with ultra model → `500 INTERNAL`

i2v `_ultra` is the only working video path on TIER1P5 (per memory 3871 + verified today).

## Design

Three isolated changes. Default behavior unchanged when no anchor is configured
(b-roll / faceless episodes keep the text-prompt path → no regression).

### 1. `scripts/wr3_flowkit_client.py`

**1a. New uploader** (next to `_generate_start_image`):

```python
async def _upload_image_asset(
    ctx: EpisodeContext, *, image_path: Path, timeout_s: int = 60,
) -> str:
    """POST /api/flow/upload-image — returns media_id for a LOCAL image file.

    Used to inject the Zantara anchor as the i2v start image so the rendered
    clip preserves the A007 identity (verified cosine 0.91 vs 0.12 text-prompt).
    """
```

POSTs `{file_path: str(image_path), project_id: ctx.project_id, file_name: image_path.name}`,
returns `resp["media_id"]`. Raises `FlowkitError` on missing `media_id` / non-200.

**1b. `EpisodeContext`** gains:
- field `anchor_image_path: str | None = None` (persisted in `to_dict`/`from_dict`)
- field `anchor_media_id: str | None = None` (runtime cache, NOT persisted — media_ids
  are project-scoped and re-uploaded per run; cheap, 0cr)

**1c. `submit_clip` step 2b** becomes:

```python
if request.start_image_media_id:
    start_image_id = request.start_image_media_id
elif episode_context.anchor_image_path:
    # upload once per episode, cache on ctx
    if not episode_context.anchor_media_id:
        episode_context.anchor_media_id = await _upload_image_asset(
            episode_context, image_path=Path(episode_context.anchor_image_path),
        )
    start_image_id = episode_context.anchor_media_id
else:
    img_prompt = request.image_prompt or request.positive_prompt
    start_image_id = await _generate_start_image(episode_context, prompt=img_prompt, timeout_s=90)
```

Precedence: explicit per-shot `start_image_media_id` > episode anchor > text-prompt.

### 2. `render_shot_pack` — read anchor from shot-pack root

After loading `shot_pack`, if `episode_context.anchor_image_path` is unset and the
shot-pack declares `anchor_image_path` at root, set it on the context before the loop:

```python
if episode_context.anchor_image_path is None:
    ap = shot_pack.get("anchor_image_path")
    if ap:
        episode_context.anchor_image_path = ap
```

### 3. `~/.claude/agents/wr3-shot-director.md` — emit anchor in shot-pack

For episodes whose identity tokens include `A007`, the shot-director writes
`"anchor_image_path": "<abs path to zantara-face-anchor-v1.png>"` at the root of
shot-pack.json. (Agent-definition doc edit, not Python.)

## Out of scope

- The `models.json` r2v TIER1P5 portrait→landscape mapping bug (r2v unused; do not touch).
- Re-rendering the 18 C5a clips (separate step after this lands).
- The `render_shot_pack` schema mismatch (`shot["index"]`/`positive_prompt` vs real
  shot-pack `shot_id`/`prompt_positive`) — pre-existing, the real renderer is the
  clip-renderer agent dispatcher, not this function. Not introduced or fixed here.

## Test plan (TDD)

`scripts/tests/test_wr3_anchor_start_image.py`:

1. `test_anchor_uploaded_and_used_as_start_image` — ctx has `anchor_image_path`,
   `start_image_media_id` None → `_upload_image_asset` called once, its media_id
   becomes the `_generate_video` `start_image_media_id`, `_generate_start_image` NOT called.
2. `test_anchor_uploaded_once_across_shots` — 3 shots, upload happens exactly once
   (cached on ctx.anchor_media_id).
3. `test_explicit_start_image_wins_over_anchor` — per-shot `start_image_media_id` set
   → anchor NOT uploaded, explicit id used.
4. `test_no_anchor_falls_back_to_text_prompt` — no anchor, no explicit id →
   `_generate_start_image` called (current behavior preserved, no regression).
5. `test_render_shot_pack_reads_anchor_from_root` — shot-pack with root
   `anchor_image_path` → ctx.anchor_image_path populated.
6. `test_upload_image_asset_raises_on_no_media_id` — gateway returns no media_id → FlowkitError.

All async via `pytest.mark.asyncio`, mock `_http_post_json` / sub-helpers (no real FlowKit, 0cr).

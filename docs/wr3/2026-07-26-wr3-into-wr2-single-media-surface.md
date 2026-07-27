# WR3 into WR2 — one media surface, two language cuts

> **Status:** DESIGN **signed off** — Zero ruled all four open questions on 2026-07-26 (§6). Ready to build.
> **Mandate (Zero, 2026-07-26):** _"wr3 dobbiamo farla entrare nella app wr2 e quindi creare un
> unico luogo di sviluppo media. Riguardo la produzione come wr2, la wr3 è prestabilita e crea il
> video del carosello della wr2 (in due versioni uguali ma una in inglese con sottotitoli inglese e
> una indonesiana con sottotitoli indonesiano)."_
> Style reference named by Zero: `C5a-FINAL-gfx.mp4`. Zantara character already built on Flow.

---

## 1. Why this is being written now (the finding that forced it)

WR3 has produced **zero episodes in 57 days** (last: `2026-05-29`). The cause is not a broken
organ — every organ works. Verified on 2026-07-26:

- the supervisor is **healthy**: holds `TCP 127.0.0.1:59789->127.0.0.1:15432 (ESTABLISHED)`,
  **15s of CPU across 2 days** (asleep in its event loop), reconnect counter frozen at 285
  (`285 → 285` over 60 observed seconds), both logs silent since 2026-07-25 13:27. The 2.3 MB of
  `heartbeat timed out` errors is **history, not a live signal**;
- the Postgres path is clean: 12/12 heartbeats at **38 ms**, survives **60 s idle** (10/20/35/60 s
  all tested) — so neither proxy flap nor idle-kill;
- FlowKit is authenticated and reports **12 410 credits** (9 910 subscription + 2 500 top-up),
  `SERVICE_TIER_ADVANCED`.

**The defect is that nothing can start an episode.** The ignition chain closes on itself:

| link                                                                      | who emits it                                                           | reality                        |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------ |
| `wr3_episode_brief_requested`                                             | only `wr3_companion_dispatcher.py`                                     | fires only from the link below |
| `wr2_episode_published`                                                   | **nobody** — no repo file emits it outside tests/supervisor/dispatcher | dead end                       |
| `companion_expand` / `companion_engage` / `companion_skip` in a WR2 brief | **never set by any carousel**                                          | dead end                       |

Eight specialist agents, supervisor, contracts, outbox, gatekeeper and the Veo integration are all
built, and **the nerve that should fire them is connected at neither end**. This is
"esiste ≠ armato" raised one floor: not a dead organ, an unwired one.

It also means WR3 was _already_ designed as a companion to WR2 — Zero's mandate does not bend the
architecture, it **finishes** it.

## 2. The decision

**WR3 stops being a separate lane and becomes the video output of the WR2 app.** One media surface,
one pipeline, one place to develop. A carousel is no longer "a carousel that might also get a
video": it is a **media item** that renders to slides _and_ video.

Production is **preordained, not opt-in** — the `companion_expand` flag disappears rather than
being set. Every published WR2 carousel yields video. Two cuts, identical in edit, differing only
in language:

- **EN** — English VO, English subtitles
- **ID** — Indonesian VO, Indonesian subtitles

Same shots, same timing, same graphics, same music. Only the voice track and the subtitle text
change, so both cuts share one render of the visual layer.

## 3. Style system — extracted from the reference, not invented

Measured from `C5a-FINAL-gfx.mp4` (`ffprobe` + frame extraction, 2026-07-26):

**Container** — 1080×1920 (9:16), **24 fps**, h264, AAC stereo 48 kHz, 6.1 Mbps, **163 s**.
Note: 163 s is **above the agreed 150 s ceiling** (§6.1) — the reference is the LOOK to match, not a length to copy.

**Subject** — Zantara: medium shot (waist-up), centred, walking or standing, talking to camera.
Cream V-neck blouse, camel high-waisted trousers, tan leather crossbody bag, gold hoops.
Backgrounds are real Bali exteriors (shopfronts + motorbikes, palm, temple gate, market, sunset
street) with one studio/behind-the-scenes beat (softbox + camera on tripod).

**Graphics layer** (the reference ships a `C5a-CLEAN-nogfx.mp4` twin — the gfx are a separable
overlay, which is exactly how we should build it):

1. **Chapter label**, top-left: `| THE HOOK`, `| THE C5A`, `| ROAD 1/3`, `| THE 3 QUESTIONS`,
   `| GET HELP` — amber, small caps, letter-spaced, preceded by a vertical bar.
2. **Logo badge**, top-right: circular near-black disc, `BALI ZERO` wordmark, B in amber.
3. **Subtitle block**, lower third: dark translucent rounded panel, white **ALL-CAPS** bold sans,
   centred — with **key terms set in amber inside the white text** (`FEELS HARMLESS`,
   `2 JUNE 2025`, `$60K /YEAR`, `KBLI 59112`, `WHO PAYS`, `BALIZERO0`). This selective amber
   emphasis is the signature move of the format and must survive translation (§6).
4. **Info card**, optional, under the subtitle: darker panel, title line + small grey sub-line
   (`E33G — REMOTE WORKER KITAS` / `Income from abroad only`). Used to pin a term.
5. **Progress bar**, bottom edge: horizontal rule split amber (elapsed) / dark (remaining).
6. **Centre title beat**: large white caps + oversized amber numerals (`DECIDE YOUR ROAD` / `1 · 2`)
   for enumeration moments.

**Palette** — amber/gold + white + near-black translucent panels. Consistent with the Bali Zero
brand cortex; the graphics layer must read tokens from it rather than hardcoding hexes.

**Assets already on disk** (`~/Desktop/nuzantara-archive/pro-archive-20260627/zantara avatar/`):
face anchor, close-up, front-neutral, 3-view turnaround, outfit-F face/body refs, bust/face
per-shot refs, `Zantara-Voice-Corpus/`, and gfx mockups A/B/C + COMPARE.

## 4. What the merge actually changes

- **Ignition**: the WR2 publish step becomes the single trigger. No `companion_expand` flag, no
  second app to remember. Publishing a carousel _is_ requesting the video.
- **Brief reuse stays**: `wr3_companion_dispatcher` already inherits `claim_ids` verbatim from the
  WR2 brief and **skips brief-interpreter entirely** (Law 2 — NB source_ids are never re-queried).
  That contract is preserved; the merge does not widen the NB surface.
- **One review queue**: slides and video land in the same human-review surface, so a carousel is
  approved once as a media item.
- **The supervisor's role shrinks** to what it already does well: listen, dispatch, ACK. It does
  not need to change to make this work — it has been waiting for exactly this event.

## 5. Build order (each step independently provable)

1. **Emit `wr2_episode_published`** at the WR2 publish step, carrying the carousel slug.
   _Proof:_ the supervisor's stdout log shows its first-ever dispatch line.
   **BUILT, DELIBERATELY UNARMED** (PR #3166, 2026-07-26). `wr2_ig_publish.py` emits the event
   after `_mark_queue_published`, so it only ever fires for a carousel that is fully published and
   fully recorded — but behind `WR2_WR3_HANDOFF_ENABLED`, default OFF. The firebreak is not
   timidity: the WR3 supervisor runs `WR3_DRY_RUN=false` and dispatches through `claude --print`,
   so the first emitted event is real Veo spend, not a smoke test. The proof line above is
   therefore also the proof-of-armed in the PENDING-ARMS ledger.
2. **Drop the opt-in**: companion runs for every published carousel; keep `companion_skip` as the
   only escape hatch. _Proof:_ a published carousel with no flags produces a WR3 brief.
   **CONTRACT DONE** (2026-07-26): `episode` is the automatic sub-mode at 60–150 s in two cuts,
   `story_15s` is demoted behind `--story`, `companion_expand` is gone, and the dispatcher enforces
   the duration envelope itself (`_assert_duration_envelope`) because this path skips the agent
   that used to enforce it. Proven in dry-run, not yet on a live publish — which is blocked on the
   same thing step 1 is: **`primary_claim_ids` is empty in 23 of 23 WR2 briefs on disk**, and an
   episode with no inherited claims is now skipped outright rather than downgraded. Making WR2
   emit claim ids is the remaining arming condition for both steps.
3. **Two-cut render**: one visual render, two audio+subtitle tracks (EN/ID).
   _Proof:_ two MP4s, byte-different audio, identical video stream hash.
4. **Graphics layer as an overlay pass**, parameterised from brand tokens, mirroring the
   clean/gfx split the reference already demonstrates. _Proof:_ the same clean render with the
   overlay disabled and enabled.
5. **Canary**: BKPM 5/2025 paid-up capital → 2.5 mld (Zero's pick). Facts already verified, so a
   bad result indicts the pipeline, not the grounding. Budget: 8–19 clips inside the 60–150 s contract ⇒ ~80–190 credits of 12 410. **EN cut first**; the ID cut waits on an Indonesian voice corpus (§6.2).

## 6. Decided (Zero, 2026-07-26)

1. **Length — flexible, hard bounds `60 s ≤ duration ≤ 150 s`.** Not a target: a **contract**, and
   the gatekeeper enforces it before any credit is spent. Consequences that follow from the number,
   not from taste:
   - the style reference itself (**163 s**) is **over the cap** — it is the look to match, not a
     length to copy;
   - at ~8 s per clip, the envelope is **8–19 clips**, i.e. **~80–190 credits per episode** and
     **~65–150 episodes** inside the current 12 410;
   - the VO budget follows at ~3 words/s: **~180–450 words**. A carousel too thin to reach 60 s of
     honest narration must not be padded to clear the floor — it should not become an episode.
     Reaching the floor is a **quality gate**, not a formatting step.
2. **Indonesian voice — a real ID voice-over, not subtitles over English.** So the ID cut is a
   genuine second render of the audio, and the Zantara voice corpus (today English-only,
   `zantara-avatar-flow/Zantara-Voice-Corpus/`) needs an Indonesian counterpart before the first ID
   episode. **This is now the critical path for the ID cut** — the visual layer renders once and is
   shared, but the ID audio cannot be derived from the EN one. Sub-decision left to the build:
   whether the ID voice comes from Veo's native audio for the same character or from the local
   Chatterbox fallback; both are already wired in `wr3-audio-asset-producer`, and the choice is
   empirical (identity + LUFS + transcript match), not architectural.
3. **Amber emphasis — authored per language** (default taken, not overridden). The storyboarder
   picks the emphasised terms **for each language independently**; never translate the English
   selection. A regulatory number keeps its emphasis in both cuts, but the surrounding words that
   carry the sentence's weight differ between English and Indonesian.
4. **Merge target — the existing WR2 surface.** No new app directory. Anything that reads like
   "a new place for media" is out of scope by construction: the whole point is to stop having two.

---

_Grounding note: every measurement in §1 and §3 was executed on 2026-07-26 (ffprobe, frame
extraction, live process inspection, asyncpg probes) rather than recalled. Three earlier diagnoses
of the WR3 stall — proxy flap, shared-connection contention, idle-kill — were each retracted after
measurement; they are recorded in memory `discovery_subscription_audit_paid_capacity_unarmed_2026_07_25`
so the next session does not re-derive them._

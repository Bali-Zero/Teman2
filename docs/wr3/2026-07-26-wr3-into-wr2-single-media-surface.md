# WR3 into WR2 — one media surface, two language cuts

> **Status:** DESIGN, awaiting Zero's sign-off on the open decisions in §6.
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
Note: 163 s is far longer than the current WR3 contract (60–90 s VO, 8 s clips) — see §6.

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
2. **Drop the opt-in**: companion runs for every published carousel; keep `companion_skip` as the
   only escape hatch. _Proof:_ a published carousel with no flags produces a WR3 brief.
3. **Two-cut render**: one visual render, two audio+subtitle tracks (EN/ID).
   _Proof:_ two MP4s, byte-different audio, identical video stream hash.
4. **Graphics layer as an overlay pass**, parameterised from brand tokens, mirroring the
   clean/gfx split the reference already demonstrates. _Proof:_ the same clean render with the
   overlay disabled and enabled.
5. **Canary**: BKPM 5/2025 paid-up capital → 2.5 mld (Zero's pick). Facts already verified, so a
   bad result indicts the pipeline, not the grounding. Budget ≈ 70 credits of 12 410.

## 6. Open — Zero decides

1. **Length.** The reference is **163 s**; the WR3 contract targets 60–90 s. Do we raise the
   contract to reference length, or cut the carousel down to 60–90 s? This drives credit burn
   (~10 cr per 8 s clip) and the platform targets.
2. **Indonesian voice.** The Zantara voice corpus is English. The ID cut needs either a rendered
   Indonesian VO for the same character, or ID subtitles over the EN VO. Not the same product.
3. **Amber emphasis across languages.** The signature move highlights _specific terms_. Term
   selection must be authored per language, not machine-translated from the English pick, or the
   emphasis lands on the wrong word.
4. **Where "the WR2 app" is.** Confirm the merge target is the WR2 skill/pipeline surface rather
   than a new app directory, so we do not create a third place.

---

_Grounding note: every measurement in §1 and §3 was executed on 2026-07-26 (ffprobe, frame
extraction, live process inspection, asyncpg probes) rather than recalled. Three earlier diagnoses
of the WR3 stall — proxy flap, shared-connection contention, idle-kill — were each retracted after
measurement; they are recorded in memory `discovery_subscription_audit_paid_capacity_unarmed_2026_07_25`
so the next session does not re-derive them._

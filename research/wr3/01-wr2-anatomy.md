---
date: 2026-05-18
domain: wr3-design
client_case: WR3 Video Production Room — Step 1 anatomy WR2 predecessor + agent-craft patterns NB-AGENTS + 4-LLM panel synthesis
sources: 4-LLM panel (Gemini 3.1 Pro + Codex GPT-5.5 + NB-AGENTS query + my own codebase reading) + WR2 source files
status: draft pending Antonello decision gate
---

# WR3 Step 1 — Anatomy WR2 + Agent-craft Pattern Library

**Date**: 2026-05-18 00:15 WITA · **Author**: WR3 design phase, Step 1 of 6 · **Step process**: my draft → NB-AGENTS query → 4-LLM panel → synthesis (this doc) → Antonello decision gate

## TL;DR — what we learned about WR2 + what to carry into WR3

WR2 is a **centralized-orchestrator + N stateless workers** pattern (1+4+supporting), governed by 3 hard contracts (fan-out / NB ground-truth / no silent placeholder reuse), with cost-discipline via consolidated audit script, memory growth via Reflexion + Voyager skill library, and explicit failure-mode + human-in-loop publisher handoff. WR3 inherits the topology but mutates 6 of 10 dimensions because video introduces **temporal continuity + audio + identity drift + render cost asymmetry** that carousel doesn't.

## Part A — WR2 anatomy (verbatim codebase reading 2026-05-18)

### A.1 Topology

- **1 orchestrator**: `wr2-design-architect` (Opus 4.7, 416 lines, `~/.claude/agents/wr2-design-architect.md`)
- **4 sub-agent specialists** (all stateless workers, Sonnet 4.6 except critic):
  - `wr2-brief-interpreter` (Sonnet 4.6, 147 lines) — topic → structured brief JSON via NB query
  - `wr2-storyboarder` (Sonnet 4.6, 263 lines) — brief → 8-10 slide narrative spec JSON
  - `wr2-layout-composer` (Sonnet 4.6, 161 lines) — slide-spec + brief → render-ready HTML
  - `wr2-critic` (Opus 4.7 vision, 344 lines) — rendered PNG + slides + brief → 4-rubric scores + binary verdict
- **4 supporting agents** (NOT in main pipeline, asynchronous): `wr2-external-bench`, `wr2-ig-metrics-analyst`, `wr2-image-prompt-author` (between storyboarder + composer for hero image prompt enrichment), plus `wr2-design-architect-resources/` (4 reference files: architecture-patterns + brand-bali-zero + brand-external-audit + deep-research)
- **1 skill**: `bali-zero-brand` — cortex with `constitution.md` (Articles 1-11), `tokens.json` (palette closed namespace), `voice/forbidden-phrases.md`, `voice/on-tone-examples.md`, `voice/off-tone-examples.md`, `layouts/*.md` (6 layout families), `past/` (64 carousels reference + metadata.json)

**Key pattern**: orchestrator is **Opus 4.7** (judgment-heavy: sequencing + retry decisions + handoff), workers downgraded to **Sonnet 4.6** because structured I/O has predictable schemas (~25% cost of Opus, identical output quality). Critic stays Opus 4.7 with vision (rubric scoring + verbal feedback).

### A.2 The 3 hard contracts (enforced by Step 0 prologue + final-audit)

1. **Contract A — Fan-out (mandatory)**: orchestrator MUST invoke 4 specialists via `Agent` tool. Inline replacement of their work = pipeline FAIL. Empirical evidence (test-3, 2026-05-09): 9-slide pipeline with **0 Agent calls, 0 NB queries, 0 codex imagegen** = silent placeholder reuse from prior test. Counted via turn-history Agent invocations; if <4 → abort `STATUS: fanout_violated`.

2. **Contract B — NB query (ground-truth)**: brief-interpreter MUST issue ≥1 NB query before storyboard. Brief emits `nb_sources_consulted ≥1` + `nb_query_log ≥1 verbatim string`. Empty = `STATUS: ground_truth_missing`. User's research report is INPUT, not substitute — even with curated report, query NB to verify citations.

3. **Contract C — Imagegen no-silent-reuse**: layout-composer MUST generate fresh hero image via Codex `$imagegen` per `is_hero_image: true` slide, UNLESS explicit `image_strategy: "anchor_reuse"` + matching anchor file + sha256 verification. Each decision logged in `slides.json` as `image_source: "anchor:<file>"` or `"imagegen:<codex_session>"`. Silent `cp ../prior-test/placeholder.jpg .` forbidden.

### A.3 Cost discipline — `_audit-checklist.sh`

Test-5 cost **$10.07 / 29min because orchestrator made 107 Bash + 50 Read = 165 tool calls** for verifications that fit ONE bash script. Solution: consolidated audit script with 5 modes invoked exactly 4 times per pipeline:

| Mode           | When                    | Replaces                                                                                                          |
| -------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `preflight`    | Step 0                  | ~12 separate Bash probes (subagent presence + brand cortex + domain anchor sha + codex version + slug uniqueness) |
| `setup-outdir` | between Step 1-2        | ~5 cp/mkdir calls (output dir + logo + \_base.css + hammurabi-stele)                                              |
| `hero-sha`     | after Step 4            | 5 shasum calls + sliding logic (Article 5.10 verification)                                                        |
| `render-check` | after Playwright render | sips loop (PNG dimensions check)                                                                                  |
| `final-audit`  | before READY emission   | Step 0 self-audit (counts Agent calls, NB queries, imagegen sessions, placeholder reuse)                          |

Output: structured KEY=value lines, parseable via `grep '^KEY='`. Exit 0 = PASS.

### A.4 Memory growth — Reflexion + Voyager

- **Reflexion weekly cron** (`com.balizero.wr2.reflexion.weekly.plist`, Sunday 02:30 WITA): reads last 7 days of episodes + designer-override diffs (Damar's final published vs orchestrator draft), generates ≤10 verbal lessons, appends to:
  - `~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md` (voice-related)
  - `~/.claude/skills/bali-zero-brand/layouts/_proposed/` (layout-related)
  - `~/.claude/skills/bali-zero-brand/constitution.md` (recurring violation needs hard rule)

- **Voyager curriculum**: weekly inspect last 30 carousels. If topic-type underrepresented (e.g. "0 tax carousels last 14 days"), generate 1 exploratory variant for next cycle, tag `exploration:true`.

- **Skill graduation**: `_proposed/` skill → `/layouts` after **3 successful uses** (critic ≥ threshold + Antonello approval). Unused 60 days → `_archived/`.

### A.5 Centralized state + anti-pattern enforcement

- **No peer-to-peer between subagents** — Google's **17.2× error-amplification** finding. Workers stateless read shared files. Communicate via orchestrator only (orchestrator writes intermediate state to `apps/war-room/output/carousel/<slug>/`).
- **Dual brief propagation (R3a)**: brief.json travels verbatim with every subagent call (storyboarder + layout-composer). Previous bug: orchestrator's prose synthesis lost voice_register + bilingual_lexicon + taboo_check → S6 mappazza + bilingual untranslated terms.
- **Vision pre-pass (R3b)**: before invoking expensive Opus critic, run Haiku 4.5 binary vision check on every hero PNG ("does image semantically match brief topic+hook? PASS/FAIL"). Catches hallucination snowballing (arXiv 2509.21789) at $0.20 per slide.

### A.6 Hard rules constitution (cannot override without Antonello approval)

14 articles: aspect ratio 1080×1350 portrait, palette closed token namespace (antracite + black + white + yellow + red, NEVER green/blue/purple), logo `3 ALI ZERO` bottom every slide, single bold geometric sans-serif UPPERCASE, editorial 35mm photo style with teal-amber, regulatory citations verbatim (`PP 18/2021` NOT "the 2021 regulation"), bilingual lexicon never translated (KITAS/PT PMA/KBLI/SHGB), body 25-50 words/slide, closing statement-bomb single-line NO CTA hard-sell, forbidden phrases list closed, anti-cliché images (no palms/beaches/sunsets/handshakes), spell-check verbatim, slide count 7-10 hero 4-6, no hallucinated brand attributes (always token names not hex).

Added 2026-05-15 (post-incident):

- **Rule 15 — Renderer canonicity**: NEVER write `/tmp/wr2_*_LOCAL.py` patch copies (false-PASS incident /tmp shadowing 8h)
- **Rule 16 — Hero declaration must match layout**: `is_hero_image: true` only on cover-photo/photo-headline-yellow-sub/stat-card-hero
- **Rule 17 — Quote verification**: every direct quote traceable to research file with attribution; qa-dialogue ONLY when question also verbatim from source (v3 2026-05-15 invented "DG Imigrasi, will the BVK scheme be revoked?" — journalistic falsification)

### A.7 PG channels + state model

- **PG channels active**: `war_room_event`, `wr2_status_change` (migrations 138, 164, 170 — outbox-durable per Symbiosis Law 4)
- **State table**: `war_room_drafts` (status FSM: pending → drafts_imaged_checked → rendering → ready)
- **Migrations**: 138 (notify), 161 (supervisor heartbeat), 164 (status_change outbox), 170 (draft_lease columns for canva_renderer_v2)

### A.8 Failure mode + publisher handoff

- **Max 2 retry rounds**: critic verdict → composer fix → critic re-review. After 2, write `STATUS: needs_human_edit` + POST `http://localhost:8765/api/flag-needs-human-edit` → Damar queue UI yellow pill. Never infinite-loop, never claim success on flagged carousel.
- **Publisher handoff = `canva_pending.json`** single-slot pattern: `apps/war-room/output/canva/canva_pending.json` overwrite. Schema includes `template_design_id`, `folder_id`, `operations[]` (replace_text + upload-asset-from-url), hero_slide_indices, slides_count. Consumed by `/canva-apply` skill or 5-min supervisor cron.
- **Conflict resolution**: existing `canva_pending.json` with `status: pending` → append `.queued.<timestamp>.json` suffix instead of overwriting.
- **Human-in-loop on IG publish**: Damar publishes manually. Orchestrator output stops at Canva via `wr2-canva-apply` skill.

### A.9 Cicatrici (lessons learned)

5 key cicatrici with concrete prevention patches:

1. **test-3 fan-out bypass (2026-05-09)** → Contract A enforcement counts Agent calls in turn history
2. **test-5 cost overrun 165 tool calls (2026-05-10)** → `_audit-checklist.sh` consolidation
3. **KEP71 imagegen hang 25+ min (2026-05-12)** → 300s watchdog hard wall-clock cap on every `codex exec $imagegen` invocation
4. **False-PASS /tmp shadowing 8h (2026-05-15)** → "Errare è umano, allucinare è diabolico" anti-pattern; renderer canonicity Rule 15; never `/tmp/wr2_*_LOCAL.py` patches
5. **v3 invented quote falsification (2026-05-15)** → Rule 17 quote verification with attribution traceability

## Part B — Convergent verdicts (3-LLM panel + NB-AGENTS bipolar)

### Convergence 4/4 panel members on these findings:

1. **WR2 1+4 topology DOES NOT replicate 1:1 to WR3**. Video introduces dimensions (temporal continuity + audio + identity drift + render cost asymmetry) absent in carousel. Granularity must adapt.

2. **Orchestrator + critic stay Opus 4.7, workers go Sonnet 4.6** — worker downgrade pattern proven, transfers directly to WR3.

3. **3 hard contracts evolve** but stay rigid:
   - Fan-out: MANDATORY for video too (anti-temptation to assemble ffmpeg inline)
   - NB ground-truth: MANDATORY for any regulatory/factual video claim
   - "No silent placeholder reuse" expands to **clip + audio + music** (not just image)

4. **Reflexion + Voyager apply** but require additional video-specific libraries:
   - `shot-cliche-library` (banned/saturated patterns)
   - `clip-pathology-library` (face drift / lip mismatch / hand artifacts / subtitle collision / mushy B-roll)
   - `prompt-yield-ledger` (prompt × model tier × credits × retries × usable yes/no)
   - `retention-lessons` (hook/pacing evidence from publish metrics)
   - **Save what almost worked but was scrapped, not only what worked** — Codex emphasis

5. **`canva_pending.json` is IG-carousel-only**. WR3 needs **manifest + staging directory pattern**:
   - `staging/<episode_id>/master.mp4`
   - `reel_9x16.mp4`, `shorts_9x16.mp4`
   - `thumbnail.jpg`, `caption.md`, `sources.md`, `manifest.json`, `qc_report.json`
   - Damar queue UI with preview video player
   - REJECT carries timestamp ("0:14 face artifact") → orchestrator **partial-patches** that clip, doesn't regenerate entire video

6. **Bootstrap problem (5 vs 64 past)** must be solved with hybrid strategy:
   - 5 Bali Zero episodes = house seed (NOT statistical truth)
   - 20-30 external reference clips (NYT/Pudding/Bloomberg) = rubric anchor (NOT copy target)
   - 20 known-bad clips = critic training gold (failure dataset)
   - **Pairwise scoring** ("A beats B because...") > 1-10 score
   - First 10 WR3 episodes = pilot with MANDATORY human labels
   - **Strict Template Mode**: deviate max 10% from Golden Episodes until episodes_produced ≥ 20

### Per-panel unique insights

**Gemini 3.1 Pro unique** — strongest on operational mechanics:

- **Timeline EDL pattern** (Edit Decision List): replace WR2's "canvas JSON" with structured timeline that tracks duration, VO seconds, shot count, audio level mix, subtitle density
- **Pre-render critic gate**: critique TEXTUAL prompts BEFORE expensive Veo render, not after (cost asymmetry)
- **Identity gate as deterministic tool call**: ArcFace local script, NEVER ask LLM to "look at face and judge similarity"
- **Subtitle safe-zone Y=1400px** to avoid Instagram/TikTok UI overlap
- **5 Golden Episodes** virtual ground truth as system-prompt input

**Codex GPT-5.5 unique** — strongest on production engineering:

- **1+6 not 1+4**: minimum serious WR3 = orchestrator + brief-verifier + script-editor + shot-director + flow-producer + post-assembler + critic. Below 6 → "agenti onnivori" hide errors
- **Post-assembler deterministic-first**: ffmpeg/libass/audio mix as Python/Bash, LLM only for diagnostics, never for ffmpeg parameter generation
- **8 PG channels not 3**: add `wr3_status_change` + `wr3_clip_failed` + `wr3_qc_failed` + `wr3_human_action_required` + `wr3_publish_ready` (state in table, channels are notifications via outbox)
- **Cost discipline**: NEVER hardcode `3500 cr` or `10 cr/clip` in constitution (volatile); audit reads balance from FlowKit live
- **Codex correction**: Google Flow Pro now lists **1000 monthly credits** (not 3500) — verify per-account/region/snapshot
- **Pairwise critic scoring** instead of 1-10 (avoids absolute scale drift)

**NB-AGENTS bipolar unique** — strongest on agent-craft authority:

- **Frontmatter rigor (plugin-dev bundle)**: `name` kebab-case; `description` includes when-to-invoke conditions + 2-4 concrete examples in third person; tool restrictions implement **least privilege** (post-assembler gets ONLY Bash+Read, NOT WebFetch/Edit); model `sonnet` for drafting, `opus` for synthesis
- **Voyager skill library applied**: script parametrici FFmpeg (pan/zoom + cut timings + Veo scene descriptions) saved as **executable code modules** retrievable by topic/archetype
- **Cross-LLM bipolar verifier** as critic when corpus < 20: Opus + Gemini Pro panel validates metadata + script generated, replaces lack of past visual reference
- **Anti-pattern enforcement explicit**: vision pre-pass (Haiku 4.5) MANDATORY before render to block hallucination snowballing
- **References numerate verbatim** to 11 source documents in NB (Reflexion paper + Voyager paper + WR2 architect spec + cicatrici lessons + brand assets) — true ground-truth not hallucinated

## Part C — What to extract for Step 2 (decomposition verbi atomici)

The convergent findings let us write the verb-list more precisely. **Patterns to carry forward**:

1. **Topology baseline**: 1 orchestrator (Opus) + 5-7 sub-agents (mostly Sonnet, critic Opus, post-assembler deterministic-first hybrid). Definitive number decided in Step 3 after verb list.

2. **3 contracts mutate to 4-5**:
   - Contract A (fan-out) → unchanged
   - Contract B (NB ground-truth) → unchanged
   - Contract C (no-silent-reuse) → expand to clip+audio+music
   - **NEW Contract D**: pre-render textual critic gate (cost discipline)
   - **NEW Contract E**: identity gate deterministic tool call (ArcFace + VLM combo)

3. **Memory libraries: 4-5 instead of 2**:
   - shot-cliche-library
   - clip-pathology-library
   - prompt-yield-ledger
   - retention-lessons (post-publish)
   - **scrapped-but-close-library** (Codex insight — save the "almost worked")

4. **Bootstrap = Golden Few-Shot Strict Template Mode**:
   - 5 Bali Zero ad-hoc episodes + 20-30 external refs + 20 known-bad
   - Pairwise scoring instead of absolute 1-10
   - Strict Template Mode → free creative mode at episode_count ≥ 20

5. **Skill `bali-zero-brand` extension**:
   - New subfolder `surfaces/video-editorial/`
   - Contains: video-constitution.md + Zantara character bible A007 anchor + Chatterbox Emma seed lock + shot archetypes + audio mix targets (VO LUFS, music ducking) + subtitle .ass template + duration bands per format
   - Cross-surface inherits: palette, forbidden phrases, voice Bali Zero, citations discipline

6. **Manifest schema (replaces canva_pending.json)**:

   ```json
   {
     "episode_id": "...",
     "topic": "...",
     "stage": "pending|rendering|qc|ready_for_review|approved|published",
     "files": {
       "master_mp4": "staging/.../master.mp4",
       "reel_9x16": "...",
       "thumbnail": "...",
       "captions": { "ig": "...", "yt_shorts": "..." },
       "sources": "sources.md",
       "qc_report": "qc_report.json"
     },
     "clips": [
       {
         "clip_id": "...",
         "prompt_hash": "...",
         "model": "veo_3_1_fast",
         "credits": 10,
         "ms_start": 0,
         "ms_duration": 8000,
         "checksum": "..."
       }
     ],
     "audio": { "vo_lufs": -14, "music_lufs": -24, "duck_target_lufs": -28 },
     "identity_gate": { "arcface_score": 0.87, "vlm_pass": true },
     "publish_targets": ["ig_reel", "yt_shorts"],
     "approval_required": "antonello"
   }
   ```

7. **PG channels minimal-but-complete**:
   - `wr3_episode_status_change` (FSM transitions)
   - `wr3_clip_generated` (success)
   - `wr3_clip_failed` (Veo policy/timeout/quota)
   - `wr3_qc_failed` (critic verdict reject)
   - `wr3_human_action_required` (max retries hit / approval gate)
   - `wr3_publish_ready` (Damar UI flag)

8. **`_video-audit.sh` modes** (consolidated like WR2):
   - preflight (ffmpeg + ffprobe + libass + fonts + FlowKit + ingredients + A007 + Chatterbox config)
   - setup-outdir (episode dir + manifest + logs + temp + final exports)
   - source-check (NB + sources + citations)
   - clip-check (duration + fps + resolution + codec + nonzero audio + prompt/model/cost logged)
   - identity-check (ArcFace + VLM + face detect)
   - render-check (final mp4 probe + subtitles visible + safe-area sample frames)
   - audio-check (LUFS + true peak + VO/music ratio)
   - final-audit (budget + retry count + human gate + publish manifest)

## Part D — Open questions Step 1 didn't fully resolve (forward to Step 2-6)

1. **Number of sub-agents (5/6/7)**: Gemini says 5, Codex says 6 minimum, NB-AGENTS replicates WR2's 4 mapped to video. Step 2 (verb decomposition) will determine.

2. **Hedra vs no-Hedra**: 4-LLM verdict precedente bocciava Hedra. Spike Veo+MuseTalk fal.ai mostrato MuseTalk inferiore. Veo nativo wins. **Lock-in**: Veo 3.1 Fast Tier_ONE Pro plan, Chatterbox Emma off-camera, ffmpeg post-prod.

3. **Mini-Pro2 role**: NB-AGENTS query timed out earlier connectivity-side; Codex flag Mini unreachable. Mini batch role (overnight long renders) needs SSH verification before Step 5 Symbiosis Laws section.

4. **Critic baseline 5 episodi**: Step 3 (agent roster) will define exactly which agent owns bootstrap responsibility (likely shot-director loads strict template + critic loads pairwise rubric).

5. **DeepSeek 4-LLM panel completion**: Step 1 dossier closes with 3-LLM convergent (Gemini + Codex + NB-AGENTS). DeepSeek as 4th member not yet delivered — will add as addendum if/when it arrives. Pattern emerged is solid without it.

## Decision gate (Antonello)

**Per the locked process**: this dossier is the Step 1 output. Decisions to take before Step 2:

- **A. Accept Step 1 findings as-is** → proceed Step 2 (Decomposizione verbi atomici)
- **B. Iterate Step 1** with specific corrections (which?)
- **C. Pivot direction** based on something Step 1 surfaced

Step 2 will produce: `02-verbi-atomici.md` — exhaustive list of all video-production verbs (parse → render → assemble → publish), classified as **Agent (LLM judgment)** vs **Tool call (deterministic)**, then mapped to sub-agents in Step 3.

## Sources

- `~/.claude/agents/wr2-design-architect.md` (416 lines, verbatim read)
- `~/.claude/agents/wr2-brief-interpreter.md` (147 lines, verbatim head)
- `~/.claude/agents/wr2-storyboarder.md`, `wr2-layout-composer.md`, `wr2-critic.md` (frontmatter + key sections)
- `~/.claude/skills/bali-zero-brand/SKILL.md` + `constitution.md` (Article structure)
- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_nb_agents.md`
- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/agent-mesh-v1-live.md`
- `/tmp/wr3-step1/gemini.txt` (8.6KB)
- `/tmp/wr3-step1/codex.txt` (148KB)
- `/tmp/wr3-step1/nb-agents.txt` (49KB, 11 NB sources, 38 citations to Reflexion + Voyager + WR2 architect + cicatrici)
- WR2 cicatrici from `.claude/rules/cicatrix-scars.md` + memory `lessons_*` files

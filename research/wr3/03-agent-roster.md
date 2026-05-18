---
date: 2026-05-18
domain: wr3-design
step: 3
title: Agent Roster Mapping — verb → sub-agent
panel: Gemini 3.1 Pro + Codex GPT-5.5 + NB-AGENTS
deepseek: killed by user 2026-05-18 ("uccidi deepseek vai con 3")
my_draft_roster_size: 7 pipeline + 4 supporting = 11
panel_recommended_roster_size: 9 pipeline + 4 supporting = 13
verdict: roster expanded — 3-LLM convergent on 2 critical splits
---

# WR3 Step 3 — Agent Roster Mapping

## Convergenze 3/3 (panel UNANIMOUS)

| #   | Decisione                                                                                                          | Rationale                                                                                                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | **wr3-veo-producer DEVE essere SPLIT** in `wr3-clip-renderer` (Phase 5+6) + `wr3-audio-asset-producer` (Phase 7+8) | Failure domains diversi: render fallisce su safety filter / cost / identity drift; audio fallisce su pronuncia / LUFS / license / Content ID. Retry loop devono essere isolati. Single-responsibility violato a 26-28 verbi cross-modal. |
| C2  | **Phase 4 → `wr3-pre-render-gatekeeper` standalone**                                                               | Self-review trap: shot-director scrive prompt Veo (`3.4a-d`), non può anche approvarli (`4.2 review_shot_list_against_cliche`). Separation of creator/approver è inviolabile pre-spend.                                                  |
| C3  | **`wr3-reflexion-synth` resta cron weekly standalone** (NON nell'orchestrator)                                     | Mirror esatto WR2 pattern. Orchestrator deve restare lean per real-time. Reflexion legge episodi sett. + diffs human-override, sintetizza ≤10 lezioni Markdown.                                                                          |
| C4  | **Skill graduation = Antonello human-veto**                                                                        | No auto-merge. `_proposed/<name>.md` → 3 successful uses (critic ≥ threshold) → Antonello reviewa diff git → commit to main. Voyager propone, Antonello firma.                                                                           |
| C5  | **Least-privilege tool restrictions** per ogni agente                                                              | Read-only agents (brief, critic) no Write/Edit/Agent. Execution agents (clip-renderer, post-assembler) no WebFetch. Tutti no recursive Agent calls eccetto orchestrator.                                                                 |

## Divergenze 2-contro-1 (risolte)

| #   | Punto                   | Gemini                       | Codex                             | NB-AGENTS         | Decisione                                                                                                            |
| --- | ----------------------- | ---------------------------- | --------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------- |
| D1  | wr3-critic split?       | Single + multi-pass          | Single + internal lanes           | Split 3 paralleli | **Single con internal lanes** (2/3 contro split — coordination overhead 3 critic > beneficio)                        |
| D2  | wr3-shot-director model | Opus                         | Opus per prompt-critical          | (non specifica)   | **Opus** (largest hallucination surface)                                                                             |
| D3  | legal_claim_gate owner  | Orchestrator                 | brief-interpreter                 | (non specifica)   | **brief-interpreter** (è già grounding reviewer con NB access)                                                       |
| D4  | wr3-post-assembler LLM? | Sonnet per edge cases ffmpeg | Pure Python + LLM solo diagnostic | (non specifica)   | **Hybrid: Python-first, Sonnet solo per `9.3b resolve_audio_video_mismatch` + `10.3 generate_caption_per_platform`** |

## Roster finale — 9 pipeline + 4 supporting = 13

### Pipeline (9 — hot path produzione)

| #   | Agent                         | Phases                                                                                  | Verbs                                                  | Model                                                        | Color  | Tools                                                                                   |
| --- | ----------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------ | ------ | --------------------------------------------------------------------------------------- |
| 1   | **wr3-design-architect**      | Orchestrator + 2.5.1 script_freeze + 2.5.5 budget_reserve + 4.4 route_fix_to_specialist | ~12 routing                                            | Opus                                                         | blue   | Read, Write, Bash, Glob, Grep, Agent, Skill                                             |
| 2   | **wr3-brief-interpreter**     | Phase 1 (Research) + 2.5.2 legal_claim_gate                                             | ~14                                                    | Sonnet                                                       | pink   | Read, Glob, Grep, Bash, WebFetch — **NO Write/Edit/Agent**                              |
| 3   | **wr3-script-editor**         | Phase 2 (Scripting)                                                                     | ~10                                                    | Sonnet                                                       | purple | Read, Write, Bash, Glob, Grep — **NO WebFetch/Agent**                                   |
| 4   | **wr3-shot-director**         | Phase 3 (Cinematography)                                                                | ~12                                                    | **Opus**                                                     | orange | Read, Write, Bash, Glob, Grep, Skill — **NO WebFetch/Agent**                            |
| 5   | **wr3-pre-render-gatekeeper** | Phase 4 (Pre-render gate)                                                               | ~6                                                     | Sonnet                                                       | yellow | Read, Write, Bash, Glob, Grep — **NO Agent**                                            |
| 6   | **wr3-clip-renderer**         | Phase 5 (Veo render) + Phase 6 (Identity gate)                                          | ~13                                                    | Sonnet (Opus per `5.6 fallback_select` + `6.3 vlm_holistic`) | red    | Read, Write, Bash, Glob — **NO WebFetch/Agent**                                         |
| 7   | **wr3-audio-asset-producer**  | Phase 7 (Voice TTS) + Phase 8 (Music/B-roll)                                            | ~13                                                    | Sonnet                                                       | cyan   | Read, Write, Bash, Glob (+ WebFetch solo se license check non API-based) — **NO Agent** |
| 8   | **wr3-post-assembler**        | Phase 9 (Assembly) + 10 (Variants) + 12 (Manifest)                                      | ~19 (15 Tool + 4 Hybrid)                               | Python-first + Sonnet diagnostic                             | green  | Read, Write, Bash, Glob — **NO WebFetch/Agent**                                         |
| 9   | **wr3-critic**                | Phase 11 (Critic final)                                                                 | ~12 (Haiku VLM pre-pass + Opus per voice/legal/cliche) | Opus                                                         | red    | Read, Write, Bash, Glob, Grep — **NO Agent**                                            |

**Total pipeline verbs:** ~111 mappati (3 over-count = verbi che attraversano 2 agent come `2.5.1` orchestrator+script-editor → counted once orchestrator)

### Supporting (4 — async/cron)

| #   | Agent                      | Phase                                           | Cadence                                     | Model                              | Color | Tools                                                 |
| --- | -------------------------- | ----------------------------------------------- | ------------------------------------------- | ---------------------------------- | ----- | ----------------------------------------------------- |
| 10  | **wr3-reflexion-synth**    | Phase 13.2 (Reflexion) + 13.5 (Voyager propose) | Sun 02:30 WITA cron                         | Sonnet                             | gray  | Read, Write, Bash, Glob — **NO Agent**                |
| 11  | **wr3-yt-metrics-analyst** | Phase 13.1 (YT metrics ingest)                  | Mon 06:00 WITA cron post-Reflexion          | Gemini 3.1 Pro free OAuth (1M ctx) | gray  | Read, Write, Bash, Glob, Grep — **NO Agent**          |
| 12  | **wr3-editorial-bench**    | External benchmark NYT/Bloomberg/Pudding        | Monthly 1st Mon 07:00 WITA cron             | Gemini ingestion + Opus synthesis  | gray  | Read, Write, Bash, WebFetch, WebSearch — **NO Agent** |
| 13  | **wr3-b-roll-curator**     | Phase 5.7 fallback + 8.5 stock search           | On-demand from clip-renderer/audio-producer | Sonnet                             | gray  | Read, Bash, WebFetch — **NO Agent/Write**             |

## Frontmatter discipline (WHEN-TO-INVOKE — plugin-dev compliant)

Pattern WR2 (`wr2-design-architect.md`): description in **3rd person**, inizia **"MUST BE USED..."** o **"Use IMMEDIATELY when..."**, 2-4 esempi concreti `<example>` blocks.

### Esempi draft frontmatter per ogni agent

```yaml
# 1. wr3-design-architect
name: wr3-design-architect
description: "MUST BE USED for every Bali Zero WR3 video episode. Use IMMEDIATELY when user says 'produce WR3 episode for [topic]', 'run video room', 'retry failed episode'. Orchestrator-only: fans out to 8 specialist subagents, NEVER writes script/shot-list/render-config inline. Reads brand cortex + Step 2 verb taxonomy, enforces 3 contracts (fan-out, NB ground-truth, no-silent-asset-reuse), runs critic gate, emits Drive handoff. Grows via Voyager skill library + Reflexion weekly synthesis."
tools: Read, Write, Bash, Glob, Grep, Agent, Skill
model: opus
color: blue

# 2. wr3-brief-interpreter
name: wr3-brief-interpreter
description: "MUST BE USED by wr3-design-architect at Step 1 of every episode run. Use IMMEDIATELY when orchestrator passes topic. Queries NotebookLM Bali Zero NBs for ground-truth, returns structured brief JSON (key facts, key numbers, audience segment, regulatory citations verbatim, taboo notes, tone register, claim_ids for legal_claim_gate). Also owns Phase 2.5.2 legal_claim_gate as independent grounding reviewer AFTER wr3-script-editor writes — verifies every claim against NB before script_freeze."
tools: Read, Glob, Grep, Bash, WebFetch
model: sonnet
color: pink

# 3. wr3-script-editor
name: wr3-script-editor
description: "MUST BE USED by wr3-design-architect at Step 2 after brief-interpreter returns brief JSON. Use IMMEDIATELY when brief JSON exists. Writes 60-90s VO script with claim_ids embedded, pacing markers, beat-sheet structure (Hook/Frame/Discovery/Closing arc). Outputs script.json — does NOT freeze (orchestrator owns 2.5.1 script_freeze). Re-write loop if legal_claim_gate fails."
tools: Read, Write, Bash, Glob, Grep
model: sonnet
color: purple

# 4. wr3-shot-director
name: wr3-shot-director
description: "MUST BE USED by wr3-design-architect at Step 3 after script_freeze passes 2.5.1. Use IMMEDIATELY after script is frozen. Drafts shot-list with camera grammar, then writes Veo 3.1 prompt pack (positive + negative + identity tokens A007 anchor + transition map). LARGEST hallucination surface — uses Opus. Does NOT approve own prompts — output passes to wr3-pre-render-gatekeeper at Phase 4."
tools: Read, Write, Bash, Glob, Grep, Skill
model: opus
color: orange

# 5. wr3-pre-render-gatekeeper
name: wr3-pre-render-gatekeeper
description: "MUST BE USED by wr3-design-architect at Phase 4 BEFORE any Veo credit spend. Use IMMEDIATELY after wr3-shot-director returns prompt pack. Reviews shot-list against cliche library, runs cost circuit breaker (4.3), safety pre-check, optional human-review gate. Returns PASS/FAIL/REROLL verdict. If FAIL: orchestrator routes back to shot-director. Independent reviewer — NEVER the same agent that wrote prompts."
tools: Read, Write, Bash, Glob, Grep
model: sonnet
color: yellow

# 6. wr3-clip-renderer
name: wr3-clip-renderer
description: "MUST BE USED by wr3-design-architect at Phase 5 ONLY after pre-render-gatekeeper returns PASS. Use IMMEDIATELY after gatekeeper PASS. Submits Veo 3.1 Fast Tier_ONE jobs (`veo_3_1_i2v_s_fast_portrait`, 10cr/clip 720x1280 9:16 8s), watchdog timeout, fallback selection (Opus escalation), ingest MP4s. Also owns Phase 6 Identity Gate (ArcFace cosine + VLM holistic check). NO WebFetch — operates on local file system + FlowKit gateway only."
tools: Read, Write, Bash, Glob
model: sonnet
color: red

# 7. wr3-audio-asset-producer
name: wr3-audio-asset-producer
description: "MUST BE USED by wr3-design-architect at Phase 7+8 IN PARALLEL with clip-renderer. Use IMMEDIATELY after script_freeze. Generates Emma VO via Chatterbox (seed=42 cfg=0.30 temp=0.70 exag=0.32), compares transcript to script, normalizes LUFS to -14, sources music (license-verified), drafts attribution. If Veo fails specific shot, dispatches wr3-b-roll-curator for stock fallback (8.5)."
tools: Read, Write, Bash, Glob
model: sonnet
color: cyan

# 8. wr3-post-assembler
name: wr3-post-assembler
description: "MUST BE USED by wr3-design-architect when ALL assets (clips + VO + music + b-roll) are ready. Use IMMEDIATELY after clip-renderer AND audio-asset-producer both return success. Concatenates video tracks via ffmpeg, assembles master, renders subtitles (libass evermeet static ffmpeg /tmp/ffmpeg-full/ffmpeg), exports 9:16 variant matrix (TikTok 60s / IG Reels / YT Shorts / FB), generates per-platform captions+sources via Sonnet diagnostic, builds episode_manifest with 18 fields (episode_id, brief_hash, claim_ids, asset_hashes, ...)."
tools: Read, Write, Bash, Glob
model: sonnet  # Python-first, Sonnet only for 9.3b resolve_audio_video_mismatch + 10.3 caption_per_platform
color: green

# 9. wr3-critic
name: wr3-critic
description: "MUST BE USED by wr3-design-architect at Phase 11 as MANDATORY quality gate. Use IMMEDIATELY after post-assembler returns master MP4. Reviews 4 rubrics: (1) Identity (ArcFace cosine + frame-sample), (2) Audio sync (VO/video drift, LUFS, transcript match), (3) Brand voice + cliche pattern, (4) Legal/regulatory verbatim + cost-disclosure. Internal multi-pass: Haiku VLM pre-pass for cheap checks (11.3/11.4/11.8/11.10/11.11), Opus for nuanced (11.5/11.6/11.7/11.9). Returns binary PASS/FAIL per rubric + retry feedback. NO Agent tool — cannot recurse."
tools: Read, Write, Bash, Glob, Grep
model: opus
color: red  # same as clip-renderer — distinct context (Phase 11 vs Phase 5/6)
```

## Tool restrictions summary (least-privilege matrix)

| Agent                 | Read | Write | Bash | Glob | Grep | WebFetch | Agent | Skill |
| --------------------- | ---- | ----- | ---- | ---- | ---- | -------- | ----- | ----- |
| design-architect      | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ✅    | ✅    |
| brief-interpreter     | ✅   | ❌    | ✅   | ✅   | ✅   | ✅       | ❌    | ❌    |
| script-editor         | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ❌    | ❌    |
| shot-director         | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ❌    | ✅    |
| pre-render-gatekeeper | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ❌    | ❌    |
| clip-renderer         | ✅   | ✅    | ✅   | ✅   | ❌   | ❌       | ❌    | ❌    |
| audio-asset-producer  | ✅   | ✅    | ✅   | ✅   | ❌   | ⚠️       | ❌    | ❌    |
| post-assembler        | ✅   | ✅    | ✅   | ✅   | ❌   | ❌       | ❌    | ❌    |
| critic                | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ❌    | ❌    |
| reflexion-synth       | ✅   | ✅    | ✅   | ✅   | ❌   | ❌       | ❌    | ❌    |
| yt-metrics-analyst    | ✅   | ✅    | ✅   | ✅   | ✅   | ❌       | ❌    | ❌    |
| editorial-bench       | ✅   | ✅    | ✅   | ❌   | ❌   | ✅       | ❌    | ❌    |
| b-roll-curator        | ✅   | ❌    | ✅   | ❌   | ❌   | ✅       | ❌    | ❌    |

⚠️ audio-asset-producer WebFetch solo se license check non risolvibile via manifest API.

## Hard rules ereditate da WR2 (cf. Step 1)

1. **No peer-to-peer**: sub-agent NON parlano fra loro, solo via orchestrator (Google 17.2× error amplification finding).
2. **NB ground-truth verbatim**: brief-interpreter è SOLE source of NB queries; altri agent leggono SOLO da brief.json.
3. **No silent asset reuse**: ogni clip MP4 deve avere sha256 unico nel manifest (Article 5.10 WR2 equivalent).
4. **Critic gate binding**: orchestrator NON pubblica se critic FAIL su qualunque rubrica.
5. **Human-in-loop su pubblicazione**: orchestrator output stops at Drive staging. Damar (o tu) pubblica manualmente IG/TikTok/YT.
6. **Cost zero paid API**: solo Claude OAuth (Opus/Sonnet/Haiku), Gemini free, DeepSeek API ($0.01/q OK), NotebookLM free. NEVER ANTHROPIC_API_KEY.
7. **No emoji** in user-facing output.

## Open questions per Antonello (decision gate)

1. **Critic split rationale**: NB-AGENTS ha proposto 3 critic paralleli (sync + brand + identity). Tu accetti single con internal lanes (2 vs 1 voto) o vuoi forzare split?
2. **Roster expansion 11 → 13**: panel ha aggiunto wr3-pre-render-gatekeeper (giustificato, no self-review) e split veo-producer (giustificato, retry loop isolation). Confermi 13 actors o vuoi compress?
3. **wr3-editorial-bench cadenza**: monthly (NYT/Bloomberg long-form research) o weekly? WR2 fa monthly — replicare?
4. **Identity gate threshold ArcFace cosine**: parto da 0.6 come placeholder Step 2. Calibrazione empirica al primo Manifesto pilot (Step 7)?
5. **Phase 12 manifest 18 fields ownership**: post-assembler scrive, ma chi LEGGE? yt-metrics-analyst per metrics correlation? Critic per audit? Reflexion-synth per pattern detection? — penso "tutti read-only, post-assembler sole writer".

## Next step (Step 4 — Lifecycle per agente)

Per ogni agente disegnare:

- **Nasce** (frontmatter + system prompt iniziale + skill cortex)
- **Impara** (Reflexion feedback loop verbal lessons + Voyager skill proposals)
- **Produce** (verb cluster + I/O contract)
- **Misura** (metrics: latency, cost, critic score, retry rate)
- **Migliora** (skill graduation via 3 successful uses + Antonello approval)
- **Muore** (sunset: 60 days unused → `_archived/`, broken skill → quarantine)

Trigger: confirm Step 3 roster decisions (A/B/C/D)?

## Sources

| Panel          | LLM                                                        | Bytes                       | Quality                                          | Convergent                   |
| -------------- | ---------------------------------------------------------- | --------------------------- | ------------------------------------------------ | ---------------------------- |
| Gemini 3.1 Pro | gemini-3.1-pro-preview                                     | 8443                        | terse, ranked, decision-oriented                 | YES on 8/10                  |
| Codex GPT-5.5  | gpt-5.5 xhigh                                              | 4938 (1.1MB inc. exec logs) | thorough, verb-cited, citation-heavy             | YES on 9/10                  |
| NB-AGENTS      | NotebookLM RAG (UUID 6d449787-04e3-430e-acbe-d6fc38d379a9) | 21091                       | ground-truth WR2 verbatim + plugin-dev citations | YES on 5/10 (where it spoke) |
| DeepSeek       | KILLED by user 2026-05-18                                  | —                           | —                                                | —                            |

## NB sources consulted by NB-AGENTS

- `d0adf453-1edb-4966-8a1c-a545718a4f2f` (wr2-design-architect.md + Reflexion architecture)
- `d3ccdc37-f3b2-4163-8e2c-c11bba281169` (plugin-dev agent-creation reference)
- `41511dc3-8e29-456d-bc5d-01747901dc58` (Claude Agent SDK least-privilege example)
- `7e015fa6-1820-4ef4-8c3d-9365b4dc9a69` (Anthropic code-review parallel agents pattern)
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc` (Skill graduation rules)

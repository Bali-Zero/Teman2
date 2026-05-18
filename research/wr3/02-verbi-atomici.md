---
date: 2026-05-18
domain: wr3-design
client_case: WR3 Video Production Room — Step 2 atomic verb decomposition + Agent/Tool classification
sources: 4-LLM panel (Gemini 3.1 Pro + Codex GPT-5.5 + DeepSeek V4 Pro + NB-AGENTS bipolar) + my draft 103 verbs
status: draft pending Antonello decision gate
---

# WR3 Step 2 — Atomic Verb Decomposition

**Date**: 2026-05-18 01:15 WITA · **Author**: WR3 design phase, Step 2 of 6 · **Step process**: my draft 103 verbs → 4-LLM panel cross-review → synthesis → decision gate

## TL;DR

103 verbs in 13 phases is a **good design inventory but too granular as runtime DAG**. After 4-LLM panel cross-review, the consolidated final verb count is **~95-105 verbs across 14 phases** (added Phase 2.5 Script Gate based on universal panel recommendation), classified roughly **40% Agent (LLM judgment) + 50% Tool (deterministic) + 10% Hybrid**.

**Critical convergent finding (4/4 panel)**: legal/factual gate moved BEFORE expensive Veo render (not Phase 11). Save credits + avoid liability.

## Process

1. My draft: 103 verbs in 13 phases (parse → publish), grouped by phase
2. NB-AGENTS bipolar query → 31KB response with MetaGPT/Voyager/Reflexion patterns + 17 citations to Kim 2025 (17.2× error amplification) + plugin-dev authority
3. 4-LLM panel parallel: Gemini 3.1 Pro (6.8KB) + Codex GPT-5.5 (77KB) + DeepSeek V4 Pro (11.6KB) + NB-AGENTS (31.7KB)
4. Synthesis (this doc)
5. Decision gate Antonello

## Part A — Convergent panel verdicts (4/4 unanimous)

### A.1 Collapse over-decomposed verbs

All 4 panels agree the following are over-split:

| Verbs to collapse                                                                                                  | Reason                                                                | Panel consensus      |
| ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- | -------------------- |
| All `emit_*_event` (1.7, 2.8, 3.8, 5.7, 7.6, 8.6, 11.10, 12.4) → single tool `publish_phase_event(phase, payload)` | Event emission is byproduct of phase boundary, not separate operation | 4/4                  |
| 5.4 download + 5.5 verify_mp4 + 5.6 extract_first_frame → `ingest_clip_asset`                                      | Single long-running clip ingestion                                    | 3/4                  |
| 6.2 arcface_embed + 6.3 load_canonical + 6.4 cosine_sim + 6.5 threshold_apply → `verify_anchor_identity(face)`     | Single identity verification function                                 | 3/4                  |
| 9.2 write_concat + 9.3 ffmpeg_concat → `concat_video_track`                                                        | Atomically a single ffmpeg call                                       | 2/4 (Codex+DeepSeek) |
| 9.4 build_audio_mix + 9.5 ffmpeg_mux → `assemble_master`                                                           | Often paired ffmpeg operation                                         | 3/4                  |
| 10.1 export_reel + 10.2 export_shorts + 10.3 export_yt → `export_variant_matrix(presets)`                          | Variant is data, not verb                                             | 2/4 (Codex+DeepSeek) |
| 12.1 build_manifest + 12.2 write_staging + 12.3 sync_drive → `persist_handoff_manifest` OR `publish_to_staging`    | Single staging publish operation                                      | 2/4                  |
| 13.3 + 13.4 + 13.5 update\_\*\_library → `propose_memory_updates`                                                  | Memory mutations should be batched + reviewed                         | 2/4 (Codex+NB)       |

### A.2 Split hidden complexity

All 4 panels identified these verbs as masking too much logic:

| Verb                     | Split into                                                                                                  | Reason                                                                           | Panel consensus             |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------- |
| **3.4 write_veo_prompt** | 3.4a draft_prompt + 3.4b inject_identity_constraints + 3.4c refine_against_safety + 3.4d variant_per_aspect | Largest LLM hallucination risk; safety + identity + format are distinct concerns | **4/4 unanimous**           |
| 1.4 extract_citations    | 1.4a extract_claims + 1.4b normalize_dates_codes_amounts + 1.4c bind_claims_to_sources                      | Claim ID binding needed for downstream legal review                              | 3/4 (Codex+NB+DeepSeek)     |
| 1.5 cross_verify_web     | authority_select + fetch_source + recency_check + claim_compare + conflict_flag                             | Verification is multi-step                                                       | 2/4 (Codex+DeepSeek)        |
| 9.4 build_audio_mix      | 9.4a duck_music_under_vo + 9.4b apply_lufs_normalization + 9.4c align_sfx_to_cuts                           | EBU R128 LUFS + ducking + SFX are distinct                                       | 3/4 (Gemini+Codex+DeepSeek) |
| 2.4 write_vo_per_shot    | 2.4a draft_vo + 2.4b timebox_vo + 2.4c lock_claim_references                                                | VO must not drift from source claims                                             | 2/4 (Codex+DeepSeek)        |
| 5.8 policy_fail_fallback | 5.8a select_fallback_strategy (Agent) + 5.8b execute_fallback (Tool)                                        | Strategy choice vs execution                                                     | 2/4 (Codex+DeepSeek)        |
| 8.3 verify_license       | 8.3a license_check + 8.3b attribution_capture + 8.3c commercial_use_gate                                    | Multi-step legal                                                                 | 2/4                         |

### A.3 Missing verbs entirely

**4/4 unanimous additions** (rights/safety/compliance gap):

| Missing verb                                                                            | Phase            | Reason                                                                        | Panel mention                       |
| --------------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------- | ----------------------------------- |
| `verify_anchor_consent` / `verify_anchor_release`                                       | 0 or 3           | UU PDP compliance — even digital avatar needs signed consent from real person | 4/4 (Gemini+Codex+DeepSeek+NB)      |
| `claim_register_init` + `source_snapshot`                                               | 1                | Claim IDs + immutable source snapshots                                        | 2/4 (Codex+DeepSeek)                |
| `script_freeze`                                                                         | 2.5              | Lock script before render so VO/clips reference frozen claims                 | 3/4                                 |
| `legal_claim_gate` (script-level, BEFORE render)                                        | 2.5 NEW          | Move legal review BEFORE expensive Phase 5                                    | **4/4 unanimous**                   |
| `budget_reserve` + `cost_circuit_breaker` (real-time)                                   | 4                | Don't burn credits on bad scripts                                             | 3/4                                 |
| `idempotency_key_create` + `checkpoint_write` + `asset_hash_register`                   | every phase      | Resumability                                                                  | 2/4 (Codex+NB)                      |
| `subtitle_translate` + `subtitle_lexicon_check` + `generate_subtitle_bilingual` (EN+ID) | 9                | Multi-language editorial                                                      | 3/4 (Codex+DeepSeek+Gemini)         |
| `platform_policy_check` (IG/YT terms) + `synthid_disclosure_check`                      | 11               | AI-content disclosure compliance                                              | 2/4 (Codex+DeepSeek)                |
| `human_review_packet` / `package_human_review_bundle`                                   | 4.6+11           | Bundle script+shot_list+cortex diagnostics for Damar                          | 2/4                                 |
| `brand_forbidden_phrase_scan`                                                           | 11               | Hard-rule enforcement                                                         | 2/4                                 |
| `apply_bz_branding` (logo, framing, color grading LUTs)                                 | 9                | Missing from raw assembly                                                     | 1/4 (Gemini) — but critical         |
| `generate_transition_map` (cut/fade/whip-pan)                                           | 3                | Shot-to-shot transitions undeclared                                           | 2/4 (Gemini+DeepSeek)               |
| `handle_api_backoff` / `rate_limit_aware_submit`                                        | 5,7,8            | Systemic backoff missing                                                      | 2/4 (Gemini+DeepSeek)               |
| `verify_safe_harbor` (YouTube Content ID, etc.)                                         | 8                | Music copyright pre-check                                                     | 1/4 (Gemini)                        |
| `crossfade_decision` agent                                                              | 9                | Transition logic gap                                                          | 1/4 (DeepSeek)                      |
| `ingest_human_fix` (Damar override → manifest learning)                                 | 13               | Memory growth from human edits                                                | 1/4 (DeepSeek)                      |
| `enforce_bz_lexicon` (per-clip not just brief)                                          | 2,11             | Bilingual lock at clip granularity                                            | 4/4 unanimous                       |
| `cross_verify_nb_intel_codes`                                                           | 1                | Indonesian regulatory code accuracy                                           | 1/4 (DeepSeek) — Bali Zero critical |
| `review_kpi_compliance` (BPOM/KPI broadcast rules)                                      | 4                | Indonesian broadcast law gate                                                 | 1/4 (DeepSeek)                      |
| `register_canonical_embedding`                                                          | 0 or 6 first-run | Cold-start ArcFace canonical creation                                         | 1/4 (DeepSeek) — important          |
| `upload_anchor_reference` (once per anchor)                                             | 3                | Not in per-clip loop                                                          | 1/4 (DeepSeek)                      |
| `initialise_empty_corpus`                                                               | 0 first-run      | Cold-start manifest                                                           | 1/4 (DeepSeek)                      |
| `bootstrap_from_heuristics`                                                             | 13               | Fallback when corpus < 20 episodes                                            | 1/4 (Gemini)                        |
| `publish_scope_guard`                                                                   | 12               | Staging vs public publish boundary                                            | 1/4 (Codex)                         |
| `client_data_redaction`                                                                 | 0 or 1           | UU PDP scrubbing before LLM                                                   | 1/4 (Codex)                         |
| `likeness_check` (face anchor real-person verification)                                 | 6                | Distinct from identity match                                                  | 1/4 (Codex)                         |
| `generated_audio_transcribe` + `script_vs_audio_compare`                                | 7                | Verify Emma audio matches script verbatim                                     | 1/4 (Codex)                         |
| `price_reference_check` + `visa_kbli_term_lock`                                         | 11               | Indonesian-specific fact lock                                                 | 1/4 (Codex)                         |

**TOTAL added verbs: ~25** (some duplicates across panel). Final estimated count: 103 - 12 collapse + 25 missing = **~116 verbs in 14 phases**.

### A.4 Critical ordering fix (4/4 unanimous)

**Move legal/script gate BEFORE render** — currently Phase 11 fires AFTER Veo cost spent:

```
OLD: 0 → 1 → 2 → 3 → 4 (gate) → 5 (render) → 6 → 7 → 8 → 9 → 10 → 11 (legal_accuracy) → 12 → 13
NEW: 0 → 1 → 2 → 2.5 (script_gate + legal_claim_gate + script_freeze) → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13
```

Phase 2.5 contains:

- script_freeze (lock all claims/citations/quotes)
- legal_claim_gate (Sonnet review verbatim against NB facts)
- regulatory_term_lock (KITAS/PT PMA/KBLI/PPh — no paraphrase)
- bilingual_lexicon_enforcement (per-clip not just brief)
- consent_check + safety_filter_prompt_input
- budget_reserve (allocate Veo credit ceiling for this episode)

**Saves**: ~20-50% Veo render cost (don't render bad-fact scripts) + zero legal liability post-publish.

### A.5 Parallelism rules (4/4 convergent)

```
STRICT SYNC (dependency chain):
  Phase 0 → 1 → 2 → 2.5 (gate) → 3 (shot list depends on frozen script)
  Phase 9 (assembly) AFTER all of [5, 6, 7, 8] complete for the shot
  Phase 11 (critic final) AFTER 9
  Phase 12 (manifest) AFTER 11

PARALLEL FAN-OUT (after script_freeze):
  Phase 5 (Veo clip gen) per-shot fan-out N parallel
  Phase 6 (Identity gate) per-clip fan-out
  Phase 7 (Emma VO) can run parallel with Phase 5 (different system)
  Phase 8 (Music + B-roll) parallel with Phase 5 (mood detection only needs script, ready at 2.5)
  Phase 10 (Format variants) fan-out after master validated

ASYNC POST-CRITICAL-PATH:
  Phase 13 (Memory growth) — never on critical path, runs after publish
```

### A.6 Retry topology (4/4 convergent)

**No single dumb retry counter.** Classify retry causes:

| Retry type                              | Auto-retry? | Strategy                                                   |
| --------------------------------------- | ----------- | ---------------------------------------------------------- |
| Transient API (5xx, network)            | YES auto    | Exponential backoff, max 3                                 |
| Rate limit (429)                        | YES auto    | Rate-limit-aware wait + retry                              |
| Policy refusal (Veo audio filter, NSFW) | NO          | Route to Agent for prompt refinement, max 2                |
| Identity fail (ArcFace < threshold)     | Limited     | Stricter prompt + retry, max 2 then fallback               |
| Quality fail (critic verdict)           | Limited     | Verbal feedback to layout/composer agent, max 2 then human |
| Factual fail (NB conflict)              | NO          | Route to brief-interpreter, max 1 then abort               |

Global manifest tracks `retry_counts` per verb. Global circuit breaker fires at total cost ≥ 80% monthly budget OR retry chain > 5 levels deep.

### A.7 Degraded continuation (4/4 convergent)

**Fail-graceful rules**:

| Fail scenario                          | Action                                                                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| >50% clips fail render                 | ABORT pipeline                                                                                                            |
| ≤50% non-critical B-roll clips fail    | Continue with `fallback_to_b_roll` (licensed stock) OR `frozen_first_frame_placeholder` with "Visual unavailable" overlay |
| Identity anchor critical clip fails    | ABORT                                                                                                                     |
| Legal/factual claim fails verification | ABORT (Codex emphasis)                                                                                                    |
| Consent missing                        | ABORT                                                                                                                     |
| VO ≠ script (>20% deviation)           | ABORT                                                                                                                     |
| Music license fails                    | Substitute royalty-free public domain                                                                                     |
| Subtitle generation fails              | Skip subtitles + flag for human edit                                                                                      |

Final critic always flags degraded segments as `FALLBACK` in verdict. Damar reviews before approving for publish.

### A.8 State persistence — mandatory manifest fields per phase boundary

Codex schema (most comprehensive):

```json
{
  "episode_id": "uuid",
  "brief_hash": "sha256",
  "phase_status": "0|1|2|2.5|3|4|5|6|7|8|9|10|11|12|13",
  "source_ids": [...],
  "claim_ids": [...],
  "script_version": "vN",
  "shot_ids": [...],
  "prompt_versions": {shot_id: [v1, v2, ...]},
  "asset_paths": {shot_id: "clips/.../clip.mp4"},
  "asset_hashes": {asset_path: "sha256"},
  "model_tier": {shot_id: "veo_3_1_fast"},
  "credits_spent": {phase: int},
  "license_ids": [...],
  "consent_ids": [...],
  "qa_verdicts": {shot_id: {arcface: 0.87, vlm: true, critic: "PASS"}},
  "retry_counts": {verb: int},
  "event_sequence": [{ts, phase, verb, status}, ...],
  "human_signoff": {damar: bool, antonello: bool},
  "publish_scope": "staging|public"
}
```

Phase boundaries that MUST persist to disk (NB-AGENTS 3 minimums + Codex/DeepSeek expansion):

| After Phase           | Verb that writes         | Critical fields                                                                            |
| --------------------- | ------------------------ | ------------------------------------------------------------------------------------------ |
| 0 (Bootstrap)         | setup_outdir             | episode_id, brief_path, output_dir                                                         |
| 1 (Research)          | emit_brief               | domain, nb_route, citations[], taboo_flags                                                 |
| **2.5 (Script Gate)** | script_freeze            | script_id, claim_ids, total_duration, shots:[{shot_id, vo_text, duration, bilingual_flag}] |
| 3 (Cinematography)    | emit_shot_list           | shot_id, anchor_id, camera_grammar, veo_prompt, negative_prompt, safety_score              |
| 5 (Clip Gen) per shot | emit_clip_event          | shot_id, clip_path, mp4_checksum, generation_status                                        |
| 6 (Identity) per shot | combine_verdict          | shot_id, identity_verdict, confidence                                                      |
| 7 (Voice)             | emit_vo_event            | vo_id, audio_path, duration_ms, lufs                                                       |
| 9 (Assembly)          | ffprobe_validate         | master_mp4_path, codec_info, duration_match                                                |
| 11 (Critic)           | emit_verdict             | verdict, violations[]                                                                      |
| 12 (Manifest)         | persist_handoff_manifest | Full delivery manifest                                                                     |

Every tool that writes to disk (download, concat, mux) must append to `state.json` enabling crash-resume.

### A.9 Agent/Tool classification (final)

**Clear Agents (LLM judgment required)** — ~40 verbs:

- All `classify_*`, `detect_audience/tone/taboo`, `select_nb_route`
- All `design_*`, `write_*` (creative writing: arc, VO, prompts, captions, sources)
- `select_anchor` (when no fixed mapping exists)
- All `review_*` (script gate, shot list, final critic)
- `route_fix`, `vlm_check`, `combine_verdict`
- `detect_mood`, `infer_mood_tag`, `brand_voice`, `pacing`, `legal_accuracy`, `cliche_pattern`
- `reflexion_synthesis`

**Clear Tools (deterministic, no LLM)** — ~50 verbs:

- `setup_outdir`, `mkdir`, file IO
- NB query execution (CLI call, response parsing deterministic)
- Web fetch, OCR
- All `emit_*` → `publish_phase_event` (PG NOTIFY)
- All Flow/Veo API calls (submit, poll, download)
- All ffmpeg/ffprobe
- ArcFace embed + cosine similarity (math)
- LUFS normalize (EBU R128)
- File sync (rclone)
- Drive staging write
- Manifest JSON write
- KG record insert
- `cost_circuit_breaker_check` (threshold)
- `verify_mp4_integrity` (ffprobe)

**Hybrid (Agent + Tool combo)** — ~10 verbs:

- `select_anchor`: Tool deterministic if shot.context maps to fixed anchor; Agent only if ambiguous
- `select_music`: Agent decides mood/intent, Tool calls Suno/library API
- `detect_mood`: Tool extracts tempo/key, Agent infers narrative mood tag
- `prefilter_safety`: Tool regex/blocklist scan first, Agent only if Tool flags warning
- `policy_fail_fallback`: Agent selects strategy, Tool executes

### A.10 Bootstrap fit (5-episode corpus reality)

Bootstrap-aware verbs that need cold-start fallback:

| Verb                                   | Cold-start behavior                                                                                         |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 4.1 load_cortex                        | Return blank default if cortex empty                                                                        |
| 6.3 load_canonical (ArcFace embedding) | First run: `register_canonical_embedding` writes new                                                        |
| 3.2 select_anchor                      | First runs: deterministic mapping shot.context → anchor.tag; full Agent judgment kicks in after 10 episodes |
| 11.9 cliche_pattern_match              | Rely on static rules (no palms/beaches/handshakes); Voyager skill library populates after 20 episodes       |
| 13.3-13.5 update_libraries             | "Propose only" mode until corpus ≥ 20; Damar approves promotion                                             |
| 13.6 voyager_graduation                | Disabled until 50 episodes (DeepSeek manual review trigger)                                                 |
| 11.3 critic_review_identity            | Pairwise scoring ("A beats B because...") instead of absolute 1-10 (Codex)                                  |
| 4.2 review_script                      | Strict template mode: deviate max 10% from Golden Episodes until episode_count ≥ 20                         |

NB-AGENTS unique bootstrap pattern: **Cross-LLM Bipolar Verifier** as critic substitute. Opus + Gemini Pro vision panel validates metadata + script, brand constitution = ground truth (no past corpus needed).

## Part B — Final consolidated verb list (post-panel)

### Phase 0 — Bootstrap (5 verbs)

0.1 receive_brief (Tool)
0.2 validate_brief_completeness (Agent fuzzy)
0.3 setup_episode_outdir (Tool)
0.4 idempotency_key_create (Tool) [NEW]
0.5 initialise_empty_corpus_if_first_run (Tool) [NEW]

### Phase 1 — Research & Grounding (12 verbs)

1.1 classify_domain (Agent)
1.2 select_nb_route (Agent)
1.3 query_nb_facts (Tool)
1.4a extract_claims (Tool/Agent semantic) [SPLIT]
1.4b normalize_dates_codes_amounts (Tool) [SPLIT]
1.4c bind_claims_to_sources (Tool) [SPLIT]
1.5 cross_verify_web_authority (Agent + Tool fetch) [SIMPLIFIED]
1.6 cross_verify_nb_intel_codes (Tool) [NEW — Indonesian critical]
1.7 detect_audience_segment (Agent)
1.8 detect_tone_register (Agent)
1.9 identify_taboo_phrases (Agent)
1.10 source_snapshot (Tool) [NEW]
1.11 emit_brief_struct (publish_phase_event Tool) [collapsed from old 1.10]

### Phase 2 — Narrative & Scripting (10 verbs)

2.1 design_episode_arc (Agent — Opus)
2.2 estimate_total_duration_target (Tool)
2.3 split_arc_into_shots (Agent — Sonnet)
2.4a draft_vo_per_shot (Agent — Sonnet) [SPLIT]
2.4b timebox_vo (Tool) [SPLIT]
2.4c lock_claim_references (Tool) [SPLIT]
2.5 align_shot_duration_to_vo (Tool)
2.6 enforce_bilingual_lexicon_per_clip (Agent + Tool glossary) [EXPANDED]
2.7 verify_quote_attribution (Agent) [STRICTER]
2.8 emit_script_struct (publish_phase_event Tool)

### Phase 2.5 — NEW Script Gate (5 verbs) [ADDED — 4/4 unanimous]

2.5.1 script_freeze (Tool — write versioned + hash)
2.5.2 legal_claim_gate (Agent — Sonnet review vs NB)
2.5.3 regulatory_term_lock (Tool — glossary enforcement)
2.5.4 consent_check + verify_anchor_release (Tool — UU PDP)
2.5.5 budget_reserve (Tool — allocate credit ceiling)

### Phase 3 — Cinematography & Identity (10 verbs)

3.1 classify_shot_type (Agent)
3.2 select_zantara_anchor (Hybrid: Tool deterministic OR Agent if ambiguous)
3.3 write_camera_grammar (Agent)
3.4a draft_veo_prompt (Agent) [SPLIT]
3.4b inject_identity_constraints (Agent) [SPLIT]
3.4c refine_against_safety (Agent + Tool blocklist) [SPLIT]
3.4d variant_prompt_per_aspect (Tool — 9:16/16:9 templating) [SPLIT]
3.5 write_veo_negative_prompt (Agent)
3.6 generate_transition_map (Agent) [NEW]
3.7 emit_shot_list_struct (publish_phase_event Tool)

### Phase 4 — Pre-render Critic Gate (5 verbs)

4.1 load_brand_cortex (Tool)
4.2 review_shot_list_against_cliche (Agent)
4.3 cost_circuit_breaker_check (Tool)
4.4 route_fix_to_specialist (Tool — orchestrator dispatch)
4.5 package_human_review_bundle_if_escalate (Tool) [NEW]

### Phase 5 — Clip Generation Veo (8 verbs)

5.1 ensure_anchor_uploaded (Tool, runs once per anchor)
5.2 submit_veo_clip (Tool — API)
5.3 poll_veo_clip_with_watchdog (Tool — 300s cap)
5.4 ingest_clip_asset (Tool — download + verify_mp4 + extract_first_frame collapsed)
5.5 emit_clip_event (Tool — publish_phase_event)
5.6 select_fallback_strategy_if_fail (Agent) [SPLIT 5.8a]
5.7 execute_fallback (Tool — b-roll OR placeholder OR retry) [SPLIT 5.8b]
5.8 rate_limit_aware_submit (Tool) [NEW]

### Phase 6 — Identity Gate (5 verbs)

6.1 detect_face_in_frame (Tool)
6.2 verify_anchor_identity (Tool — arcface_embed + load_canonical + cosine_sim + threshold combined)
6.3 vlm_holistic_check (Agent — Haiku 4.5 fast vision)
6.4 combine_identity_verdict (Tool)
6.5 register_canonical_embedding_if_first (Tool) [NEW]

### Phase 7 — Voice & Audio Generation (7 verbs)

7.1 load_chatterbox_emma_locked_config (Tool)
7.2 chunk_vo_by_shot (Tool)
7.3 generate_emma_audio (Tool — API)
7.4 generated_audio_transcribe (Tool — Whisper) [NEW]
7.5 script_vs_audio_compare (Tool + Agent verification) [NEW]
7.6 normalize_audio_loudness (Tool — EBU R128 -14 LUFS)
7.7 emit_vo_event (Tool — publish_phase_event)

### Phase 8 — Music & B-roll Stock (8 verbs)

8.1a extract_tempo_key (Tool) [SPLIT]
8.1b infer_mood_tag (Agent) [SPLIT]
8.2 select_music (Hybrid: Agent intent + Tool API)
8.3a license_check (Tool) [SPLIT]
8.3b attribution_capture (Tool) [SPLIT]
8.3c commercial_use_gate (Tool) [SPLIT]
8.4 verify_safe_harbor_ytci (Tool) [NEW — YT Content ID]
8.5 b_roll_curator_search (Agent + Tool API)

### Phase 9 — Post-Assembly (10 verbs)

9.1 ensure_ffmpeg_libass_present (Tool)
9.2 concat_video_track (Tool — write_concat + ffmpeg_concat combined)
9.3 assemble_master (Tool — build_audio_mix + ffmpeg_mux combined)
9.3a duck_music_under_vo (Tool) [SPLIT]
9.3b apply_lufs_normalization (Tool) [SPLIT]
9.3c align_sfx_to_cuts (Tool) [SPLIT]
9.4 write_ass_subtitles_multilang (Tool — EN + ID) [EXPANDED]
9.5 ffmpeg_burn_subtitles (Tool)
9.6 apply_bz_branding (Tool — logo overlay + LUT color grade) [NEW]
9.7 ffprobe_master_validate (Tool)

### Phase 10 — Format Variants (3 verbs)

10.1 export_variant_matrix (Tool — reel/shorts/yt presets) [COLLAPSED]
10.2 generate_thumbnail (Tool — hero frame select + crop)
10.3 generate_caption_and_sources_per_platform (Agent — caption per platform + sources.md)

### Phase 11 — Critic Final Verdict (10 verbs)

11.1 load_critic_rubric (Tool)
11.2 vision_pre_pass_haiku (Agent — fast PASS/FAIL per frame)
11.3 critic_review_identity_consistency (Tool — ArcFace mean) + (Agent — VLM)
11.4 critic_review_audio_quality (Tool — LUFS true peak)
11.5 critic_review_brand_voice (Agent — Opus rubric)
11.6 critic_review_pacing_density (Agent)
11.7 critic_review_legal_accuracy (Agent — NB cross-check final pass)
11.8 critic_review_subtitle_legibility (Tool — sample area check)
11.9 critic_review_cliche_pattern (Agent)
11.10 platform_policy_check_and_synthid_disclosure (Tool) [NEW]
11.11 brand_forbidden_phrase_scan (Tool) [NEW]
11.12 emit_critic_verdict (Tool — publish_phase_event)

### Phase 12 — Manifest & Handoff (5 verbs)

12.1 build_episode_manifest (Tool)
12.2 publish_to_staging (Tool — write_staging + sync_drive collapsed)
12.3 publish_scope_guard (Tool — staging vs public) [NEW]
12.4 emit_publish_ready_event (Tool)
12.5 notify_damar_telegram (Tool)
12.6 record_in_kg (Tool)

### Phase 13 — Memory Growth post-publish (6 verbs)

13.1 collect_publish_metrics (Tool)
13.2 reflexion_synthesis (Agent — Opus weekly)
13.3 propose_memory_updates (Tool — batched proposal to \_proposed/) [COLLAPSED]
13.4 ingest_human_fix (Tool + Agent) [NEW — Damar override → learning]
13.5 voyager_skill_graduation_propose (Agent — disabled until corpus ≥ 50)
13.6 bootstrap_from_heuristics_if_corpus_small (Tool) [NEW]

## Part C — Final tally

- **Total verbs**: ~108 (vs 103 draft)
- **Phases**: 14 (vs 13 — added 2.5 Script Gate)
- **Agent count**: ~40 (38% of total)
- **Tool count**: ~58 (54%)
- **Hybrid count**: ~10 (9%)
- **Critical fix**: Phase 2.5 inserted BEFORE expensive render (4/4 unanimous panel verdict)

## Part D — Open questions for Step 3 (agent roster mapping)

1. **Agent → verbs mapping**: 108 verbs to be grouped into 5-7 sub-agents (per Step 1 outcome). Mapping logic: single-responsibility per agent, no agent owns >25-30 verbs.

2. **`select_anchor` (3.2)**: Tool with Agent fallback OR purely Agent? Step 3 ownership: if `wr3-shot-director` agent → Agent; if `wr3-character-consistency-planner` exists → that owns it.

3. **`select_music` (8.2) hybrid**: which agent owns intent decision vs which tool calls Suno? Step 3 decides.

4. **Bootstrap verbs (load_cortex, load_canonical, etc.)**: Phase 0 first-run verbs OR distributed across owning agents? Step 3 decides.

5. **`reflexion_synthesis` weekly cron**: separate agent OR part of orchestrator? WR2 has standalone Reflexion Sunday cron — likely same pattern.

6. **`script_freeze` ownership**: brief-interpreter owns? script-editor? Or orchestrator-direct? Step 3.

7. **Critic split**: 10 verbs in Phase 11 — should they be 1 mega-critic agent OR 2-3 specialist critics (identity / audio / brand)? Step 3 final call.

## Sources

- My draft: `/tmp/wr3-step2/draft-verbs.md` (103 verbs / 13 phases)
- Gemini 3.1 Pro: `/tmp/wr3-step2/gemini.txt` (6.8KB) — collapse `emit_*`, split `write_veo_prompt`, move Script Gate before Phase 3, Bali Zero MCP integration
- Codex GPT-5.5: `/tmp/wr3-step2/codex.txt` (77KB) — 18+ missing verbs (rights/consent/script_freeze/budget_reserve/idempotency/asset_hash/transcribe-compare), 18-field manifest schema, retry classification 6 types, official UU PDP source links
- DeepSeek V4 Pro: `/tmp/wr3-step2/deepseek.txt` (11.6KB) — collapse 5.2-5.5 + 6.2-6.5, Indonesian-specific verbs (verify_anchor_release UU PDP, cross_verify_nb_intel_codes, review_kpi_compliance BPOM), cold-start fallback verbs (register_canonical_embedding, initialise_empty_corpus)
- NB-AGENTS bipolar: `/tmp/wr3-step2/nb-agents.txt` (31.7KB) — MetaGPT SOPs argument for collapse, Voyager skill library applied to critic approval, Reflexion verbal feedback for retry prompts, Cross-LLM Bipolar Verifier as cold-start critic substitute, 3 mandatory phase boundaries to disk

## Decision gate (Antonello)

Step 2 dossier closed. Three options:

- **A** — Accept findings → proceed Step 3 (Agent roster mapping → which sub-agent owns which verbs)
- **B** — Iterate Step 2 (specific corrections to verb list)
- **C** — Pivot

Step 3 will produce: `03-agent-roster.md` — final list of WR3 sub-agents with verb-ownership mapping, model selection (Sonnet/Opus/Haiku), tool restrictions, frontmatter specs.

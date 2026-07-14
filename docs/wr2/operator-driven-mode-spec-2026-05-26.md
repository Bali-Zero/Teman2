---
date: 2026-05-26
domain: wr2
status: spec-draft
authors: Claude Opus 4.7 (CLI session) + 4-LLM panel (Gemini 3.1 Pro + Codex GPT-5.5 + DeepSeek V4 Pro)
panel_synthesis: research/operations/2026-05-26-wr2-canva-ig-4llm-panel-synthesis.md
trigger_case: C5A Visa Kunjungan Konten Kreator pilot 2026-05-26
priority: P1
---

# WR2 `operator_driven` Mode — Formal Contract Spec

> **HISTORICAL SNAPSHOT (2026-05-26, spec-draft).** This is a proposal, not a shipped procedure:
> `scripts/wr2_operator_apply.py` (the entry point this spec proposes) was never built and does not
> exist on disk. Some of the underlying intent partially landed elsewhere (see
> `apps/backend-rag/backend/app/routers/asset_upload.py`), but this document should not be read as
> "how WR2 operator-driven mode works today" — it wasn't re-verified against disk in the 2026-07-14
> pass. It also predates the Canva-lane retirement (PR #2396, 2026-07-13) that this spec's "Canva
> apply" stage refers to. Current ground truth: `docs/wr2/SUPERVISOR.md` +
> `research/operations/2026-07-14-wr2-deep-audit.md`.

## Problem statement

The WR2 production pipeline (`wr2-design-architect` orchestrator → 5 specialist subagents → critic gate → Canva apply → IG publisher) assumes an **autonomous chain**: brief from intel-stream → narrative auto-generated → render → publish.

For **regulatory editorial carouseli** (Bali Zero domain: visa, KBLI, tax, compliance) the autonomous chain is **insufficient** because:

1. **Regulatory verbatim accuracy** demands NB query + verify-gate against ground-truth source — beyond what `wr2-brief-interpreter` alone produces
2. **Editorial judgment** (which slides matter, which order, what hook) requires operator semantic intervention
3. **Bilingual ID+EN nuance** (e.g. when to keep "Data Belum Tersedia" verbatim, when to translate) demands operator domain knowledge
4. **Slide count flexibility**: autonomous chain caps at 4-10 per `wr2-storyboarder` contract; some regulatory cases need 9-14

The C5A pilot 2026-05-26 was driven manually by Claude Opus in Claude Code CLI session, bypassing `wr2-storyboarder` and `wr2-critic`. The bypass **worked editorially** (NB-2 verify-gate caught 6 errors from a parallel session, content shipped is regulatory-accurate) but produced **technical debt**: no canonical JSON conforming to WR2 schema, no machine-readable critic verdict, hero asset upload deferred manually, etc.

The 4-LLM panel (synthesis: `research/operations/2026-05-26-wr2-canva-ig-4llm-panel-synthesis.md`) converged 4/4 on:

> **The bypass is acceptable IF AND ONLY IF it produces contracts equivalent to the autonomous chain.** Without those contracts, operator-driven mode is a smell that drifts brand/quality silently.

This spec formalizes those contracts.

---

## Contract overview

`WR2_OPERATOR_MODE=true` is a first-class WR2 execution mode in which:

1. **The operator** (human-in-CLI Claude) supplies the narrative arc (slide sequence, headings, body) — bypassing `wr2-storyboarder`
2. **`wr2-critic` is ALWAYS invoked** on the final deliverable — NEVER bypassed
3. **Required artifacts** are produced equivalent to autonomous chain output
4. **Hard structural gates** (regulatory verify-gate, IG cap, sha256 hero uniqueness) are enforced

The mode is OPT-IN per carousel. Default WR2 mode remains `autonomous`.

---

## Required artifact bundle (session directory)

Every `operator_driven` carousel MUST produce, in `~/.claude/skills/bali-zero-brand/_carousels-by-session/<slug>/`:

| Artifact                            | Format        | Required      | Validator                                                      |
| ----------------------------------- | ------------- | ------------- | -------------------------------------------------------------- |
| `brief.json`                        | JSON          | YES           | Schema same as autonomous chain `wr2-brief-interpreter` output |
| `slides-v<N>-post-verify-gate.json` | JSON          | YES           | Canonical slide schema (below)                                 |
| `VERIFY-GATE.md`                    | Markdown      | YES           | Claim-per-claim NB ground truth verification                   |
| `CRITIC-GATE.md` or `.json`         | Markdown/JSON | YES           | `wr2-critic` 4-rubric verdict per slide                        |
| `slides/01.html` ... `NN.html`      | HTML          | YES           | Brand cortex layout family conformance                         |
| `slides/01.png` ... `NN.png`        | PNG 1080×1350 | YES           | Playwright render product                                      |
| `slides/*-hero.jpg`                 | JPG           | If hero       | sha256 distinct + sha256 ≠ anchor                              |
| `canva_pending_<slug>.json`         | JSON          | YES           | Schema v2.2+ (this commit)                                     |
| `_render.py`                        | Python        | YES           | Reproducibility                                                |
| `_archive-*/`                       | Dir           | If iterations | Audit trail of dropped/superseded artifacts                    |

---

## Canonical slide JSON schema (operator_driven slides-vN.json)

```json
{
  "session_id": "<slug>",
  "carousel_id": "<slug>",
  "carousel_title": "string",
  "version": "v1|v2|v3...",
  "supersedes": ["v_old", ...],
  "supersedes_errors": ["v2 had 11 slides — IG max 10..." ],
  "slide_count": 10,
  "hero_count": 5,
  "format": "1080x1350-portrait-4-5",
  "domain": "visa|kbli|tax|property|compliance",
  "regulatory_source_anchor": {
    "nb_uuid": "cff93ab0-...",
    "nb_name": "NB-2 Immigration & Visa",
    "primary_sources": ["Kepmen M.IP-08.GR.01.01/2025", "..."]
  },
  "slides": [
    {
      "n": 1,
      "index": 1,
      "layout_family": "cover-photo",
      "is_hero_image": true,
      "image_strategy": "editorial-photo|metaphor|anchor-reuse",
      "image_style": "...",
      "heading": "string",
      "subheading_or_eyebrow": "string",
      "body": "string",
      "supporting_line": "string",
      "yellow_accent": ["word1", "word2"],
      "regulatory_citation_verbatim": "...",
      "verbatim_id": "<unique_claim_id_for_audit>",
      "bilingual_terms_used": ["Kepmen", "Permenkumham", "C5A"],
      "anchor_check_hits": ["..."],
      "rationale": "...",
      "image_prompt_hint": "...",
      "voice_register": "editoriale-quieto|allarme|consulenziale",
      "supporting_words": ["..."]
    }
  ]
}
```

**Required validation**:

- `slide_count == len(slides)` consistent
- `hero_count == sum(is_hero_image)` consistent
- `n == index` (1-based, sequential, no gaps)
- All `is_hero_image: true` slides have unique sha256 hero file (Article 5.10.3) AND sha256 ≠ anchor (Article 5.10.1)
- Every `regulatory_citation_verbatim` must have matching entry in VERIFY-GATE.md

---

## VERIFY-GATE.md required structure

Each regulatory claim in slides JSON MUST appear in VERIFY-GATE.md as:

```markdown
## Claim: <slide.heading> — <verbatim_id>

**Slide**: n=N  
**Citation**: <regulatory_citation_verbatim>  
**Source**: <NB-X source name or external URL>  
**Verification method**: NB query | WebFetch | mcp**notebooklm-mcp**notebook_query  
**Verdict**: PASS | FAIL | PARTIAL  
**Evidence**:

> Verbatim NB output / URL excerpt

**Notes**: <correction if PARTIAL/FAIL>
```

A missing or FAIL claim = HARD STOP. Operator must correct slide BEFORE proceeding to render.

---

## CRITIC-GATE structure (markdown OR machine-readable JSON)

`wr2-critic` rubric MUST evaluate operator_driven carousel against same 4 rubrics as autonomous chain:

1. **Brand voice register** (PASS/FAIL per slide)
2. **Article 5.10 hero uniqueness** (sha256 pairwise + sha256 ≠ anchor)
3. **Article 6.2 bilingual assist** (first-occurrence ID terms have EN gloss UNLESS in always-untranslated list)
4. **Article 6.3 bullet-promise** (heading announces N items ⇒ body delivers N items, no paragraph mush)

CRITIC-GATE.json (preferred for machine consumption):

```json
{
  "carousel_id": "<slug>",
  "verdict": "PASS|FAIL|PASS_WITH_NOTES",
  "rubric_scores": {
    "brand_voice": { "verdict": "PASS", "notes": "..." },
    "hero_uniqueness": {
      "verdict": "PASS",
      "sha_pairs_checked": 10,
      "anchor_distinct": true
    },
    "bilingual_assist": {
      "verdict": "PASS_WITH_NOTES",
      "notes": [
        "s8 'Permenkumham' first occurrence missing EN gloss — operator chose to keep ID-only per always-untranslated list"
      ]
    },
    "bullet_promise": {
      "verdict": "PASS",
      "notes": "All bullet-headed slides deliver promised N items"
    }
  },
  "anti_monotone_check": { "verdict": "PASS", "image_styles_distinct": 5 },
  "operator_override_acknowledged": true,
  "human_judgment_zones": [
    "s8 bilingual gloss omission",
    "11→10 slide drop per IG cap"
  ]
}
```

---

## Schema adapter (operator JSON → WR2 canonical fields)

Existing `pending_builder.py` (`apps/backend-rag/backend/services/canva_renderer/pending_builder.py`) expects fields different from operator_driven slides JSON. To bridge:

| Operator slides JSON field                         | WR2 canonical field   | Adapter                                        |
| -------------------------------------------------- | --------------------- | ---------------------------------------------- |
| `n`                                                | `slide_number`        | direct map                                     |
| `heading`                                          | `headline`            | direct map                                     |
| `subheading_or_eyebrow`                            | `subhead`             | direct map                                     |
| `body`                                             | `body`                | direct map (with concat of `supporting_line`)  |
| `layout_family`                                    | `slide_type`          | direct map                                     |
| `is_hero_image`                                    | `is_hero_image`       | direct map                                     |
| `image_strategy + image_style + image_prompt_hint` | `image_prompt`        | concat                                         |
| `image_url` (computed)                             | `image_url`           | from hero JPG path → Tigris URL via P1.2 proxy |
| `regulatory_citation_verbatim`                     | `source_refs`         | array wrap                                     |
| `verbatim_id`                                      | `regulatory_claim_id` | new field, required for audit                  |

Adapter implementation: new file `apps/backend-rag/backend/services/canva_renderer/operator_mode_adapter.py` (P1 follow-up).

---

## IG carousel max-10 enforcement

**HARD GATE** in operator_driven mode: `slide_count > 10 → REJECT`.

Exception: `slides_dropped: N` and `slides_dropped_reason` documenting strategy (drop / merge / split into part 1+2). The reason MUST be machine-checkable (regex match for "split", "merge", "drop slide").

Reference: `apps/backend-rag/backend/services/publisher/ig_publisher.py:106`.

---

## Asset hosting contract

In operator_driven mode, hero JPG hosting follows priority order:

1. **Backend proxy** (`POST /api/assets/upload` per P1.2) — preferred when wired
2. **Cloudflared tunnel + `mcp__claude_ai_Canva__upload_asset_from_url`** — tactical bridge when proxy missing
3. **Tigris content-addressed manual upload** — escape hatch ONLY if backend offline AND tunnel blocked
4. **NEVER**: Pro-side Tigris creds in `~/.nuzantara-secrets.env` (rejected 4/4 panel)

---

## Canva apply contract

Operator_driven mode uses **copy-first edit-transaction**, NOT PDF→import (production flow autonomous chain is being refactored separately in P1.3):

```python
copy = mcp__claude_ai_Canva__copy_design(template_id, page_numbers=[1..N])
hero_asset_ids = [mcp__claude_ai_Canva__upload_asset_from_url(url, name) for url in hero_urls]
txn = mcp__claude_ai_Canva__start_editing_transaction(copy.design_id)
mcp__claude_ai_Canva__perform_editing_operations(txn, [replace_text...] + [update_fill...])
preview = [mcp__claude_ai_Canva__get_design_thumbnail(txn, page) for page in 1..N]
# HUMAN GATE: visual approval required
mcp__claude_ai_Canva__commit_editing_transaction(txn)
final_png = mcp__claude_ai_Canva__export_design(copy.design_id, format=png)
```

Master template `template_id` is **NEVER mutated**. Always copy first.

---

## IG publisher contract

Operator_driven mode produces `DraftPayload` (after P1.4 extension):

```json
{
  "draft_id": "<slug>",
  "platform": "instagram",
  "slides": [<10 PNG URLs from copy-export step>],
  "cover_image_url": "<slide 1 PNG URL>",
  "main_caption": "<hook + bullets + CTA, ≤2200 chars>",
  "alt_text_per_slide": ["<accessibility text per slide>", ...],
  "first_comment": "<sources + caveats verbatim>",
  "hashtags": ["#C5A", "#VisaIndonesia", ...],
  "approval_state": "pending|approved|rejected",
  "approval_actor": null | "<email>",
  "approval_timestamp": null | "<ISO8601>",
  "scheduled_publish_at": null | "<ISO8601>"
}
```

`media_publish` is invoked ONLY if `approval_state == approved` AND (optional) `scheduled_publish_at <= now()`.

**Regulatory editorial NEVER auto-publishes.** Convergence 4/4 panel.

---

## Workflow invocation

```bash
# In Claude Code CLI session:
WR2_OPERATOR_MODE=true wr2-apply-carousel <session-dir>

# Or equivalent direct MCP cycle:
python scripts/wr2_operator_apply.py \
  --session-dir ~/.claude/skills/bali-zero-brand/_carousels-by-session/<slug>/ \
  --canva-pending apps/war-room/output/canva/canva_pending_<slug>.json
```

Steps performed by `wr2_operator_apply.py` (P1 follow-up implementation):

1. Read session dir → validate required artifacts (table above)
2. Run JSON schema validators
3. Run sha256 hero uniqueness check
4. Run IG cap check (≤10 OR documented exception)
5. Run wr2-critic gate (4 rubrics)
6. If hero upload pending → host via priority chain (proxy > tunnel)
7. Execute canva_pending.json apply_workflow (copy_design → upload → edit txn → preview → commit)
8. Generate DraftPayload (caption / alt-text / first-comment per slide via wr2-storyboarder fragment OR operator override)
9. Park draft in `apps/war-room/output/drafts/<slug>.json` with `approval_state: pending`
10. Emit Telegram alert to operator with Canva edit URL + approval action items

---

## Migration plan

| Phase                    | Action                                                                                                         | Owner                |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- | -------------------- |
| **P0 (done 2026-05-26)** | Spec drafted (this doc), C5A pilot ships under spec contracts manually                                         | This session         |
| **P1.1**                 | Schema adapter `operator_mode_adapter.py` + JSON validators                                                    | Claude Code CLI      |
| **P1.2**                 | Backend `POST /api/assets/upload` proxy endpoint Tigris                                                        | Claude Code CLI      |
| **P1.3**                 | `orchestrator.py` refactor: drop PDF→import, add copy-first edit-transaction                                   | Claude Code CLI      |
| **P1.4**                 | `DraftPayload` extend caption/alt-text/first-comment                                                           | Claude Code CLI      |
| **P1.5**                 | IG cap canonical schema validation                                                                             | Claude Code CLI      |
| **P2**                   | `wr2-critic.md` agent update for operator_driven mode invocation                                               | Subagent maintenance |
| **P2**                   | Cron `wr2_canva_pdf_apply.py` deprecated; replaced by `wr2_operator_apply.py` (or its autonomous-mode sibling) | Refactor wave        |

---

## Open questions for Antonello

1. **`wr2_operator_apply.py` location**: `scripts/` (local cron) vs `apps/backend-rag/.../wr2/operator_apply.py` (backend service)?
2. **Approval gate UI**: Telegram bot button vs `kita.balizero.com/wr2-approve` route?
3. **Carousel split-into-parts** (alternative to drop): when content NATURALLY > 10 slides, prefer split (Part 1/Part 2) over drop. Need policy: which carouseli are eligible for split?
4. **Backward-compat** with existing 64 past carouseli in `past/`: do we backfill canonical JSON for old carouseli, or grandfather them out of the schema validator?

---

## References

- Brand cortex: `~/.claude/skills/bali-zero-brand/constitution.md` (Articles 1-7)
- Subagent contracts: `~/.claude/agents/wr2-*.md`
- WR2 pipeline architecture: `docs/wr2/pipeline-architecture-2026-05-10.md`
- Canonical bypass prevention: `docs/wr2/canonical-bypass-prevention-2026-05-15.md`
- 4-LLM panel synthesis: `research/operations/2026-05-26-wr2-canva-ig-4llm-panel-synthesis.md`
- Pilot artifacts: `~/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/`
- IG publisher: `apps/backend-rag/backend/services/publisher/ig_publisher.py`
- Cicatrix scars (failure modes referenced): `.claude/rules/cicatrix-scars.md` W47/W49/W50/W51 (deploy-path family), 2026-05-10 (template coupling), 2026-05-15 (canonical bypass)

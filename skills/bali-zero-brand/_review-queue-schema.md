# Human-in-loop review queue schema

> Addresses Codex FLAW MEDIUM "human-in-loop under-specified". Damar publishes manually but without a queue schema, "ignored" cannot be distinguished from "approved".

## Storage location

`~/nuzantara/apps/war-room/output/queue/human-review-queue.json`

Single JSON array. Append-only by orchestrator. Modified in-place by Damar's tooling (or by Antonello if Damar unavailable).

## Schema

```json
[
  {
    "id": "carousel_2026-05-08T11:00:00Z_kep71-spt-extension",
    "run_id": 42,
    "topic_slug": "kep71-spt-extension",
    "drafted_at": "2026-05-08T11:00:00Z",
    "carousel_path": "~/nuzantara/apps/war-room/output/carousel/kep71-spt-extension/",
    "canva_design_id": "DAHJxxxxxx",
    "canva_design_url": "https://www.canva.com/design/DAHJxxxxxx/edit",
    "critic_overall_verdict": "legibility_soft_fail",
    "critic_summary": "rubric 4 image-fit slide 5: AI-art fingerprints suspected (extra finger). Other slides pass.",
    "agent_recommendation": "regenerate slide 5 hero image OR keep + manual photo swap",
    "state": "drafted",
    "state_history": [
      {
        "state": "drafted",
        "at": "2026-05-08T11:00:00Z",
        "by": "wr2-design-architect"
      }
    ],
    "damar_action": null,
    "damar_action_at": null,
    "damar_notes": null,
    "instagram_post_url": null,
    "instagram_published_at": null,
    "designer_override_diff": null,
    "engagement_metrics": null
  }
]
```

> **`critic_overall_verdict` vocabulary (WR2 deep audit 2026-07-14, §5a finding
> #2):** this doc's worked example above predates the current field values and
> is otherwise Canva-era (`canva_design_id`, `damar_action` — fields the live
> Python-cron render path, `scripts/wr2_html_render_apply.py`, does not write;
> full doc refresh is a separate tracked item, out of this fix's scope). The
> verdict values `legibility_only_pass` / `legibility_soft_fail` mean the
> per-slide **legibility** loop (readable/hierarchy/balanced) converged or
> didn't — they are NOT a constitution-critic verdict. The 4-rubric brand
> constitution critic (citations verbatim, no-emoji, bullet-promise, Art 7
> phrase-ban, Art 2.3 palette-ratio) is the `wr2-critic` subagent, run only on
> the interactive `wr2-design-architect` orchestration path — it never touches
> a draft produced by the Python cron path. Before this rename the cron path
> wrote a bare `"pass"`/`"soft_fail"`, indistinguishable from a real
> constitution-critic pass to every downstream consumer (the review app, the
> IG-metrics analyst, reflexion synthesis). Other observed values on this
> field: `"external"` (hand-imported, never critic-gated — see
> `wr2_carousel_import.py`) and `null`/omitted (this pipeline never touched
> the field at all).

## State machine

```
drafted → drafted_needs_human_edit → reviewed → published_with_edits  (orchestrator-flagged path)
drafted → reviewed → published        (happy path)
drafted → reviewed → rejected         (Damar refuses to publish)
drafted → reviewed → published_with_edits  (Damar edited then published)
drafted → ignored                      (no action 14 days → auto-archive)
drafted → withdrawn                    (Antonello pulls the carousel before review)
```

### State definitions

- **drafted**: agent produced carousel, queued for Damar. Initial state.
- **drafted_needs_human_edit**: orchestrator exhausted retry budget (2 critic rounds failed). Visible to Damar as a yellow-bordered row with "needs human edit" pill. Damar opens, reviews critic report (`needs_human_edit_critic_report`), edits manually in Canva, then transitions to `reviewed`. Set by `POST /api/flag-needs-human-edit` from `wr2-design-architect`. Required fields: `needs_human_edit_reason`, `needs_human_edit_retry_count`, `needs_human_edit_critic_report`, `needs_human_edit_flagged_at`.
- **reviewed**: Damar opened the Canva design and made a decision (any of next 4 transitions).
- **published**: Damar posted the carousel verbatim to Instagram. Most common case.
- **published_with_edits**: Damar made changes in Canva before publishing. The `designer_override_diff` MUST be filled — this is the gold-standard learning signal.
- **rejected**: Damar refused publication. `damar_notes` field MUST contain the reason.
- **ignored**: 14 days elapsed without review. Auto-transitioned by daily cron. NOT a learning signal — could mean "Damar busy" or "topic stale" or "carousel bad". Don't optimize against ignored.
- **withdrawn**: Antonello pulled before Damar acted. Reason in `damar_notes` (overloaded with `withdrawn_reason` semantics).

## Required fields per state transition

### drafted → reviewed

- `damar_action_at` set
- `state_history` appended with `by: "damar"`

### reviewed → published

- `instagram_post_url` set
- `instagram_published_at` set
- `designer_override_diff` MUST be `null` or empty (no edits = identity diff)

### reviewed → published_with_edits

- `instagram_post_url` set
- `instagram_published_at` set
- `designer_override_diff` MUST be filled with structured JSON:
  ```json
  {
    "slides_modified": [3, 5],
    "modifications": [
      {
        "slide": 3,
        "field": "body",
        "before": "...",
        "after": "...",
        "reason": "regulatory citation was wrong"
      },
      {
        "slide": 5,
        "field": "image",
        "before_url": "...",
        "after_url": "...",
        "reason": "AI fingerprints"
      }
    ]
  }
  ```

### reviewed → rejected

- `damar_notes` MUST contain reason — at minimum a tag from this closed list:
  - `factually-wrong`
  - `tone-off`
  - `image-bad`
  - `topic-stale`
  - `legal-risk`
  - `client-conflict`
  - `other` (then free text)

## Voyager curriculum signal extraction

Weekly cron reads queue + carousel_runs join, extracts:

- **Published count by domain/register/layout** → "underrepresented" detection
- **Override diffs** → Reflexion lessons (most valuable signal)
- **Rejection reasons** → constitution amendment proposals (categorized)
- **Ignored count** → operational health alert (Damar pipeline stalled if >5 ignored simultaneously)

## What NOT to do (per Codex FLAW + Gemini FLAW review)

- **Do NOT auto-publish** under any circumstance. OB-1 owner-binding 2026-05-07.
- **Do NOT prompt Damar** via DM/email/Telegram automatically. Pull-based: Damar opens queue UI when ready.
- **Do NOT optimize against `ignored` state**. Ignored is noise, not signal.
- **Do NOT publish IG metrics ingestion to public webhook**. Damar pastes URL → engagement scraper runs locally on Pro 24h after publish.

## Damar-side tooling (TBD — sessione 3)

- Local web UI (Next.js or static HTML) reads queue.json, shows next-up Canva design with one-click "Open in Canva" + state-transition buttons.
- Backend writes queue updates to JSON + triggers SQLite sync.
- Optional: Telegram bot `/queue` command shows count of `drafted` items.

## Gold metric

`(published / drafted) × time_to_review_avg` — the "Damar throughput". Tracking this answers: is the agent producing usable output? Is Damar engaged?

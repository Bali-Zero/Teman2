# Canonical anchor image — decision (sessione 3)

> Open question from sessione 2 (`_image-consistency.md` §"Open question"): per-topic-domain
> anchor PNG (visa-anchor.png, tax-anchor.png, etc.) for cross-carousel consistency, OR
> per-carousel slide-1 anchor (in-carousel only)?

## Decision: **HYBRID — domain anchors as STARTING reference, slide-1 as IN-CAROUSEL anchor**

Approved 2026-05-08 in sessione 3.

## Rationale

- **Pure per-carousel anchor (slide-1 only)**: each carousel internally consistent but cross-carousel drift remains. Visa carousel from Monday looks unrelated to visa carousel from Friday. Brand recognition weakens.
- **Pure domain anchor**: every visa carousel re-uses the same template image lighting/grading. Cross-carousel consistency strong but per-carousel artistic variation lost. Becomes stamp factory.
- **Hybrid (chosen)**: 5 domain anchor reference PNGs, ONE per domain, hand-curated by Antonello. At carousel start, the domain anchor seeds the *style* of slide 1 (lighting, grading, mood). Slide 1 then becomes the in-carousel anchor for slides 2..N. Best of both: cross-carousel mood family + per-carousel artistic variation.

## Domain anchor catalog

Path: `~/.claude/skills/bali-zero-brand/anchors/`

| File | Domain | Style brief |
|---|---|---|
| `visa-anchor.png` | visa | Editorial photography of immigration office paperwork, single overhead lamp, dark wood desk, blurred bureaucrat hand. Chiaroscuro Villeneuve reference. Teal-amber. ARRI Alexa Mini LF. |
| `tax-anchor.png` | tax | Stack of documents on dark surface, calculator, single fluorescent light from side, motion blur on hand stamping. Chiaroscuro. Hasselblad X2D. |
| `property-anchor.png` | property | Construction site at dusk, scaffolding silhouette, distant security light, perimeter fence. Storm clouds. Teal-amber heavy. RED V-Raptor. |
| `hr-anchor.png` | hr | Empty conference room after meeting, single lamp, scattered papers, abandoned coffee cups. Cinematic stillness. ARRI Alexa Mini LF. |
| `regulatory-anchor.png` | regulatory | Stamp closeup on folded document, blurred official seal in background, harsh side-light. High contrast. Leica M11. |

## Workflow

### Carousel start

1. Brief-interpreter assigns `domain` field.
2. Orchestrator selects `anchors/<domain>-anchor.png`.
3. Slide 1 image generation prompt:
   ```
   Match style and grading of reference image (lighting, color, atmosphere).
   Subject for THIS specific cover slide: <slide-1-specific-subject>.
   Same chiaroscuro, same teal-amber grading, same camera anchor.
   ```
   With `--reference-image anchors/<domain>-anchor.png` (Codex CLI flag).
4. Slide 1 generated PNG becomes the **in-carousel reference**.
5. Slides 2..N use slide-1.png as `--reference-image` (per `_image-consistency.md` Layer 2).

### Anchor curation (Antonello, manual)

- Initial: Antonello curates 5 PNGs from past WR2 best-of, one per domain.
- Quarterly review: Antonello replaces anchor PNG if a better in-the-wild example emerges.
- Anchor PNGs are 1080×1350 (full-bleed), no text, pure photography — they encode style, not content.
- Anchors are NOT used as carousel cover slides themselves; they are reference-only.

## Failure mode

- If `anchors/<domain>-anchor.png` missing at carousel start: orchestrator falls back to pure slide-1 anchor (no domain seeding) and logs warning.
- If domain has no anchor (new domain added without anchor curation): same fallback, log warning.

## Open backlog

- **Multi-anchor per domain**: 2-3 anchors per domain (e.g., visa-formal-anchor.png + visa-fieldwork-anchor.png) for tonal variation. Defer until 50+ carousels published and tonal needs surface empirically.
- **Anchor versioning**: when Antonello swaps an anchor, archive old version with date in `anchors/_archive/`. Keep last 3 versions per domain.
- **CLIP embedding cache**: pre-compute CLIP embeddings for each anchor for the CLIP-similarity quality gate (sessione 2 deferred). Cache in `anchors/_embeddings.json`.

## Constitutional impact

Add to constitution Article 5 (Imagery), new sub-article 5.6:

> 5.6 **Anchor reference cascade**: every hero image generation MUST start from the domain
> anchor (`anchors/<domain>-anchor.png`) as style reference. Slide 1 inherits domain anchor
> style; slides 2..N inherit slide-1 style. This guarantees both cross-carousel domain mood
> consistency and per-carousel internal consistency. Missing domain anchor falls back to
> pure slide-1 anchor with logged warning.

(Will be merged in next constitutional amendment commit.)

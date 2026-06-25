# Proposed Amendment — 2026-05-12 — Article 14: Five SOTA Adoption Rules

**Status (resolved 2026-05-12)**: PARTIAL MERGE.
- **14.1 + 14.2 + 14.4 APPROVED** → merged into `constitution.md` Article 14 same day
- **14.3 + 14.5 DEFERRED** → remain in this draft pending smoke test + promotion via Article 14.6 process

**Original status**: PROPOSED, awaiting Antonello veto/approve
**Author**: Claude Opus 4.7 (this session, round 4 empirical tuning)
**Source evidence**: `_external-bench-2026-05.md` (100 SOTA cover gallery + 30 pattern + 15 anti-pattern via Gemini+DeepSeek+Opus multi-LLM, $0.04, 22 min)
**Implementation status**: code already shipped in commits 6011d64 / 2fe5ec3 / 1095daa + pending round-4 commit. Amendment formalises what code already enforces.
**Companion changes**:
- `tokens.json` — added swipe_indicator, regulation_badge, qr_closing namespaces
- `layouts/_base.css` — added `.swipe-indicator`, `.regulation-badge`, `.qr-closing`, `.source-citation-footer` classes
- `layouts/source-citation.md` — NEW layout family
- `layouts/cover-photo.md` — added regulation_code optional parameter
- `layouts/elegant-close.md` — added primary_source_url + qr_caption optional parameters
- `agents/wr2-storyboarder.md` — slide 2 framing-question rule + slide-shift to slide 3 for FRAME
- `agents/wr2-critic.md` — Rubric 5 checks 5.5, 5.6, 5.7

---

## Proposed insertion: constitution.md, after Article 13 (Archetypes)

### Article 14 — SOTA Adoption Rules (added 2026-05-12)

Bali Zero IG carousel design must remain aligned with global editorial state-of-the-art (`_external-bench-YYYY-MM.md`). The following five rules formalise the gap-closing changes adopted after the 2026-05-12 100-cover SOTA audit. Each rule cites the SOTA pattern from `_external-bench-2026-05.md`.

#### 14.1 — Swipe indicator on inner slides (SOTA pattern #10)

Slides 2 through N-1 of every carousel MUST contain a `.swipe-indicator` element (yellow dot, bottom-right, 12px, 32px offset from canvas edges). Cover (slide 1) and last slide (N) excluded.

**Rationale**: Carouseli without swipe affordance underperform on completion rate (Hootsuite 2026 benchmark). Yellow dot signals "more inside" without consuming attention. NYT, Axios, Semafor, Quartz all adopted this 2024-2025.

**Hard fail**: missing on inner slides = soft fail (-5 per slide, capped at -20) in critic Rubric 5 check 5.6.

#### 14.2 — Slide 2 = framing question (SOTA pattern #13)

Slide 2 MUST be a single-sentence framing answering "why this carousel exists for the reader specifically", in question-form OR statement-form. NOT a 3-5 item bullet list.

**Rationale**: The SOTA editorial stack (NYT, Atlantic, Vox, WSJ) treats slide 2 as transition between hook (cover) and evidence (slide 3+). Bali Zero's previous convention skipped this and cost swipe-through rate.

**Format**:
- Question-form (preferred): `Bagaimana ini terjadi?` / `Apa artinya untuk PT PMA kamu?` / `What this means for your PT PMA.`
- Statement-form (when question would sound rhetorical): `Your annual return deadline just shifted by 31 days.`

Body under the framing question: 25-50 words, ONE sentence answering the question. NOT a list.

**Hard fail**: slide 2 with a 3-5 item bullet list = soft fail. The legacy "FACTS VS OUR TAKE" pattern now belongs to slide 3.

#### 14.3 — Source-citation slide for regulatory/visa/tax/property carouseli (SOTA pattern #11, anti-pattern #15)

Every carousel in domain `{regulatory, visa, tax, property}` with `slide_count ≥ 7` MUST include a `source-citation` layout slide as slide N-1 (penultimate, before elegant-close if used, OR as last slide if no elegant-close).

For short carouseli (`slide_count ≤ 6`, typically `news-flash` or `anti-cliche` archetypes), the source-citation slide is OPTIONAL but the verbatim citation in body text (Article 6.4) remains mandatory. The standalone citation slide can be skipped to preserve narrative tempo in fast-news contexts.

The slide must list:
- 1-5 citations
- Each citation: body (regulation code verbatim), issuer (ministry/agency), date (decree date), url (primary source host)
- URL host MUST be from a known primary source: `pajak.go.id`, `jdih.kemenkumham.go.id`, `jdih.imigrasi.go.id`, `oss.go.id`, `bps.go.id`, `simbg.pu.go.id`, `kemenkeu.go.id`, etc.

**Rationale**: ProPublica, The Markup, AP build credibility via dedicated source slides. Bali Zero already cites verbatim in body text (Art 6.4) but a dedicated slide elevates visual credibility, especially for screenshot-and-reread Indonesian audience pattern.

**Hard fail**: missing for required domains = soft fail (-15) in critic Rubric 5 check 5.5.

#### 14.4 — Regulation badge top-right on cover (SOTA pattern #3)

When `brief.primary_regulation_code` is non-empty, the cover slide MUST display a `.regulation-badge` (red rounded rect, white IBM Plex Mono, 16px) at top-right (32px offset) showing the regulation code verbatim.

When `brief.primary_regulation_code` is empty, the cover MUST NOT display this badge (avoid false-authoritative signal).

**Rationale**: FT, Kontan, Tempo signal "we are citing the primary source" before the body is read. Indonesian regulatory audience reads the code first.

**Hard fail**: badge text differing from `brief.primary_regulation_code` = citation tampering = hard fail (Article 6.4 violation cascade).

#### 14.5 — QR closing for primary source (SOTA pattern #25)

When the carousel ends with `elegant-close` AND `brief.primary_source_url` is set, the elegant-close slide MUST include a `.qr-closing` element (120×120, red border, bottom-right, 60px offset) encoding the primary source URL.

The URL MUST be a regulator-issued document or registry (DJP, OSS, JDIH, Permenkumham PDF, etc.) — **NEVER** a Bali Zero own page or social media link (Article 6.6 hard-sell ban).

**Rationale**: Indonesian audience pattern of screenshot-then-rescan closes the credibility loop. NYT, AP, Reuters all use this 2024-2026. Bali Zero peers don't — would be a differentiator. ChatGPT/Claude users will scan the QR with phones.

**Hard fail**: QR pointing to Bali Zero domain = hard fail (Art 6.6).

---

## Why these 5 specifically, not 30

The deep research extracted **30 patterns** from 100 SOTA covers. Classification:
- **22 ADOPT** — fully compatible with Bali Zero brand and likely improves performance
- **6 PARTIAL** — adopt with adaptation
- **2 OBSERVE** — A/B test before committing
- **1 REJECT** — rotated-text-accent (Dalí-adjacent, already empirically penalised in `cepaka`)

Of the 22 ADOPT, **17 are already enforced** by existing constitution articles or layouts (e.g. pattern #15 sans-serif-headline = Article 3.1, pattern #29 two-color-palette-restricted = Article 2, pattern #26 type-only-cover = layout `statement-bomb`).

The remaining **5 are net-new** for Bali Zero. They become Article 14 because they cross-cut multiple layouts and need constitutional standing, not single-layout treatment.

## Defense (cf. devil's advocate gate)

Anticipated objections + answers:

| Objection | Answer |
|---|---|
| "Article 14.3 source-citation slide adds friction — readers may skip" | The data: ProPublica, The Markup carouseli with source slides have HIGHER save/share than those without. The credibility-signal increases, doesn't decrease, swipe-through. |
| "Article 14.4 regulation badge duplicates body text citation" | Yes, intentionally. The badge is for **pre-reading recognition** (Indonesian audience pattern: scan corners before reading). Body text citation is for verification. Different cognitive moments. |
| "Article 14.5 QR pointing away from Bali Zero loses our funnel" | Bali Zero IG funnel is NOT carousel-to-website-to-DM. It's carousel-to-DM-to-call (Brevo + WhatsApp already work). QR to primary source builds trust THIS carousel; trust builds future DMs. We give the source, they remember us. |
| "5 new rules at once = overhaul" | All 5 are additive (no existing rule retracted). Existing carouseli still pass. New carouseli adopt incrementally as `wr2-storyboarder` updates flow through queue. |
| "Why not wait for empirical validation on our own corpus first?" | Internal corpus is N=7 (top performers handed by Antonello). External SOTA is N=100. Statistical confidence is higher for external pattern. Internal A/B test would take 90 days minimum before significance. We borrow SOTA confidence now, validate retroactively when WR2 carouseli publish. |

## Antonello veto checklist

Before merging into `constitution.md` Article 14, verify:

- [ ] Read this amendment file fully
- [ ] Read `_external-bench-2026-05.md` for context
- [ ] Sample-render 1 carousel with all 5 rules active, verify visual quality (PDF preview)
- [ ] Decide: merge all 5? merge subset? defer?
- [ ] If merge: append Article 14 sections to `constitution.md`, delete or archive this file
- [ ] If subset: edit this file to mark which rules merge, archive rest as "deferred"
- [ ] If defer: keep this file in place, no code change rollback needed (code is opt-in via brief fields)

## Rollback safety

If after merge Article 14 produces worse carouseli (Save/Like drops vs baseline), rollback path:

1. Revert constitution.md Article 14 section (single commit)
2. Code in `_base.css` + layouts stays — the CSS classes are opt-in via brief fields (regulation_code, primary_source_url, etc.). Storyboarder simply stops populating those fields.
3. wr2-critic Rubric 5 checks 5.5, 5.6, 5.7 become unreachable (no carousel triggers them when brief lacks the fields) — but stay in code as inert defense-in-depth.

Effective rollback cost: 1 git revert + 1 storyboarder.md edit. ~5 min.

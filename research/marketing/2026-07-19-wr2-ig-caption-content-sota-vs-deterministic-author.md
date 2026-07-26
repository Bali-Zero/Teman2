---
date: 2026-07-19
domain: marketing
client_case: none — WR2 growth loop SPRINT R
adversarial_review: codex
sources:
  - scripts/wr2_ig_caption.py (the deterministic caption author under evaluation — build_caption: hook=_first_slide_heading→_restrain, body=_build_body hook_angle[:3 sentences], SOFT_CTA "DM us / link in bio", DISCLAIMER, _build_hashtags 8-15)
  - scripts/wr2_ig_publish_remote.py:116,122 (M5 operator publish path: build_caption(slug) is the LIVE default caption; --caption-file overrides) + scripts/wr2_ig_publish.py:125,450 (server-side path: _PLACEHOLDER_CAPTION when no --caption-file)
  - apps/wr2-control-app/docs/superpowers/specs/2026-07-11-instagram-caption-editor-design.md (the delivery mechanism — surfaces build_caption's output as an operator-editable default; §Out-of-scope EXPLICITLY excludes "Changing the caption-writing style or hashtag policy" = this R's exact territory)
  - ~/.claude/skills/bali-zero-brand/_external-bench-2026-06.md (NEGATIVE source — its 7 "caption" mentions are all the slide translucent-caption-PILL CSS device, NOT the IG post caption; post-caption content strategy is UN-benched)
  - https://carouselli.com/blog/instagram-carousel-best-practices (2026 carousel best practices — caption EXTENDS not summarizes; first 125 chars; saves-oriented CTA)
  - https://later.com/blog/ultimate-guide-to-using-instagram-hashtags/ (2026 5-hashtag guidance) + https://www.phable.io/phable-labs/instagram-hashtags-keywords-discovery (Mosseri: hashtags don't significantly improve reach, keywords stronger)
  - https://later.com/blog/how-instagram-algorithm-works/ + https://buffer.com/resources/instagram-algorithms/ (2026 ranking signals: DM-sends + saves + watch-time; sends weighted most for non-follower reach)
  - research/marketing/2026-07-18-wr2-cover-headline-char-budget-for-thumbnail-legibility.md (sibling R — the cover-copy length budget; the caption hook is a DIFFERENT surface)
---

# WR2 IG caption: the deterministic author encodes a ~2023 playbook; 2025-26 SOTA + facts-honesty have moved past it

**Frontier question (SPRINT R).** WR2 already generates the Instagram post caption — `build_caption`
in `scripts/wr2_ig_caption.py`, a pure/deterministic, LLM-free, LAW-2-safe author, surfaced to the
operator as an editable default by the 2026-07-11 caption-editor spec (Legge 5 preserved). **Is that
caption's CONTENT state-of-the-art for the 2025-26 Instagram algorithm, and is it facts-honest by
construction?** The editor spec that ships it explicitly put "caption-writing style or hashtag policy"
**out of scope**, the external benches only cover the slide caption-*pill* (a CSS legibility scrim),
and no prior capture touches post-caption content — so the author's editorial fitness has never been
evaluated. This R evaluates it and recommends one concrete evolution.

## GROUND — what `build_caption` actually produces (verified on disk this turn)

A fixed 5-part template, deterministic (same JSON → same caption):
1. **Hook line** = `_restrain(_first_slide_heading(slides))` — **derived from** the cover / slide-1
   heading (restrained: emoji-stripped, `" / "`-collapsed, mostly-uppercase sentence-cased). Not
   byte-verbatim, but editorially it still **restates the cover** — same words, softened case.
2. **Body** = `_build_body(brief)` — `candidates[0]` split into its **first ≤3 retained sentences**
   (`Source:`/`Sumber:` sentences dropped, emoji stripped). `candidates[0]` = `hook_angle` when a
   non-empty one exists, **else** the first `key_facts`/`key_numbers` entry (so `key_facts` IS a body
   fallback, not hashtag-only — corrected per R1).
3. **Soft CTA** = a constant: `"Questions about your case? DM us or tap the link in bio."`
4. **Disclaimer** = a constant: `"Informational, not legal advice."`
5. **Hashtags** = `_build_hashtags` — 3 broad + a domain bucket + keyword-scanned niche tags,
   **floored at 8, capped at 15.**

## The 2025-26 SOTA gaps (sourced)

1. **The caption must EXTEND the carousel, never restate it — but the hook line restates the cover.**
   "If your caption restates what the slides already cover, you waste the space… add context that did
   not fit in the slides" (carouselli 2026). `build_caption`'s first line is the **restrained cover
   heading** (same words, softened case — R1: not byte-verbatim, but editorially a restatement) — it
   spends the single highest-value real estate (the pre-"…more" 125 chars) repeating what the reader is
   already looking at.
2. **Keywords in the first sentence drive reach; hashtags no longer do — but the opening carries no
   keyword discipline.** Instagram's Mosseri has stated hashtags don't significantly improve reach and
   keyword-rich captions are the stronger discovery signal (phable/Later 2026). `build_caption` runs a
   keyword scan, but ONLY to pick hashtags — the caption's opening line is not keyword-shaped for
   in-app/Explore/Google search.
3. **The Dec-2025 hashtag guidance is ~5, relevance over volume — the author emits 8-15.** Multiple
   2026 practitioner sources (Later, DiveMedia) report Instagram moved to a small-N hashtag regime
   (~5, "classification signal not traffic source"); some report a hard 5-cap. `build_caption`'s
   floor-8/cap-15 is the retired 2023 volume playbook. (Source-quality caveat: these are practitioner
   blogs citing Mosseri, not an Instagram Help-Center number — so "reduce to ~5" is the defensible,
   risk-averse SOTA-aligned move, not a claim of a specific enforced ceiling.)
4. **Saves and DM-sends are the top ranking signals; the CTA optimizes for neither.** 2026 algorithm
   write-ups (Later, Buffer) converge on watch-time + likes-per-reach + **DM-sends** (weighted most for
   *non-follower* reach) + **saves** (educational content's strongest signal). `build_caption`'s only
   CTA — "DM us or tap the link in bio" — steers to a business lead, not to the save/send actions the
   algorithm rewards. Educational regulatory carousels are exactly the "reference/framework/comparison"
   content that earns saves and "send-to-a-friend-who's-moving-to-Bali" sends — untapped.

## The facts-honesty gap (internal, load-bearing — the founding-scar axis applied to captions)

`_build_body` uses `candidates[0]` truncated to its **first 3 retained sentences** — and `candidates[0]`
is `hook_angle` when a non-empty one exists (the common case), else the first `key_facts` entry. So the
omission is **conditional** (corrected per R1, not categorical): a load-bearing legal caveat is dropped
when it lives **beyond the third sentence of `hook_angle`, OR only in `key_facts` while a non-empty
`hook_angle` wins** (the body never concatenates `key_facts` onto a present `hook_angle`). It is a real
**structural omission risk**, not a guaranteed drop on every deck.
Concrete, live example: the PMK 37/2025 deck's own publish note requires the caption to carry
*"Dikecualikan bukan berarti bebas pajak"* ("exempted ≠ tax-free") — a caveat without which the
simplified claim is misleading. The caption is the **highest-reach surface** (what most non-followers
read first, and now the discovery-ranked one), so an un-caveated simplification there is the founding
2026-07-16 "facts-first" scar re-materialized on the surface that reaches the most people. Today this
is caught only if the operator hand-notices it in the editor — not by construction.

## Recommendation (ONE, actionable) — evolve `wr2_ig_caption.py`, keep it deterministic-first + operator-gated

Re-author `build_caption`'s content policy (delivery is already solved — the editor surfaces it as an
approved-by-operator default). Prioritized, each independently testable:

- **(e) Facts-honesty caveat-preservation (HARD, do FIRST — gates the rest).** Do NOT phrase-match
  `"not-X / bukan berarti"` to decide what a caveat is — that is exactly a superscar-#3 substring guard
  (misses paraphrase, over-matches). **R1 CADE fix:** add an explicit upstream editorial field
  `caption_required_caveats: string[]` (set by the brief/storyboarder when it authors a simplified
  claim); `build_caption` preserves every listed caveat **verbatim** and **fails closed** (raises) if the
  field is present-and-non-empty but a caveat text is absent from the assembled caption. Phrase-matching
  may only be a soft QA *warning*, never the gate.
- **(a) Hook line = EXTEND, not restate.** Open with a distinct tension/"so-what" line derived from
  `hook_angle`/`key_numbers` — not the restrained slide-1 heading. Guilt test: caption first line ≢
  cover heading (case-normalized).
- **(b) Keyword-in-first-125-chars.** Reuse the domain/keyword the hashtag scanner already extracts to
  seed the opening sentence (e.g. "KITAS", "PMK 37", "leasehold") within the pre-"…more" window —
  deterministic, no LAW-2/purity impact.
- **(c) Hashtags → ~5, relevance-ranked.** Drop the floor-8/cap-15 to a keyword-relevant ~5 and **just
  drop the overflow** (relevance-rank, keep the top ~5). **R1 CADE:** do NOT "move overflow to a first
  comment" — neither publisher has any first-comment capability (no arg, no Graph comments call), so that
  was a phantom. A first-comment channel would be a *separately scoped* publisher feature (needs the
  published post-ID + a Graph `POST /{ig-media-id}/comments` call + failure policy + operator gate) — out
  of scope for the caption author.
- **(d) Saves/sends-oriented CTA** for educational decks: "Save this for your next renewal / Send it to
  someone moving to Bali" alongside (not replacing) the DM-lead line — matched to the two signals that
  most drive non-follower reach. Deterministic static string; no LAW-2/purity impact.

**Atteso:** captions aligned with the 2025-26 ranking reality (keyword-SEO + saves/sends) AND
facts-honest by construction — replacing the restate-the-cover + 8-15-hashtag ~2023 template — while
staying deterministic + LAW-2-safe + operator-approved (Legge 5 untouched). **Next SPRINT B:** implement
(e)+(a)+(b)+(c)+(d) in `wr2_ig_caption.py`, all deterministic (generator≠grader cross-family red-team on
the caveat-preservation gate + a guilt/innocence corpus: a deck with `caption_required_caveats` whose
text is missing from the body → FAILS closed; a deck with no required caveats → unchanged; a caveat in a
present `hook_angle`'s 4th sentence → surfaced). Prove-live via `wr2_ig_publish_remote.py --print-caption`.
**R1 constraint:** `build_caption` MUST stay pure/deterministic — if a richer LLM-drafted hook is ever
wanted, it is a **separate opt-in pre-authoring step** fed only approved public editorial fields, whose
output is then passed *through* the deterministic caveat gate + operator approval; it never runs inside
`build_caption`.

## Anti-twin note (so the next session doesn't re-walk this)

The caption-EDITOR (UI/delivery) is spec'd + planned (2026-07-11) and explicitly out-of-scopes caption
STYLE + hashtag policy — this R is that excluded content half, complementary not overlapping. The bench
"caption" device is the slide translucent-PILL (CSS scrim), a different object. The cover-headline
char-budget R (#2759) is the COVER copy length; the caption hook is a separate surface. No existing
capture addresses IG post-caption content. The single new artifact here: a sourced SOTA-gap audit of
`build_caption` + a facts-honesty structural risk in `_build_body`, both feeding one next B.

## Adversarial review

Reviewed by Codex `gpt-5.6-terra` (medium effort — `sol` at high effort timed out twice at the 590s
harness cap, so a faster same-family codex seat was used; cross-family generator≠grader preserved, author
did not grade). The draft was **corrected**, and two sub-recommendations were **CADE'd** — both were fixed
in place above:

- **On-disk claims A–D:** hook is derived-then-restrained, **not byte-verbatim** (STANDS-WITH-CORRECTION —
  wording softened, argument holds: restrained restatement is still restatement). `key_facts` **is a body
  fallback** when `hook_angle` is absent, not hashtag-only (STANDS-WITH-CORRECTION — GROUND + facts-gap
  reworded). Hashtags floor-8/cap-15 + the exact "DM us" CTA constant + `build_caption` being the LIVE
  default on the **remote/M5** path (server-side uses the placeholder) all **STAND**.
- **Facts-honesty gap — STANDS-WITH-CORRECTION:** real but narrower — reframed as a *conditional structural
  omission risk* (caveat only in later `hook_angle` sentences, or only in `key_facts` while a non-empty
  `hook_angle` wins), not a categorical `key_facts` exclusion.
- **(c) "move overflow hashtags to a first comment" — CADE (phantom capability):** neither publisher has
  any first-comment support. Rewritten to "drop the overflow, keep top ~5"; a first-comment channel is
  noted as a separately scoped publisher/Graph feature, out of scope.
- **(e) "match `bukan berarti` to preserve caveats" — CADE (superscar-#3 substring guard):** string
  detection ≠ deterministic knowledge of load-bearing status (misses paraphrase, over-matches). Rewritten
  to require an explicit upstream `caption_required_caveats: string[]` field, preserved verbatim + fail-
  closed; phrase-matching demoted to a soft QA warning.
- **(b)/(d)/optional-LLM — STANDS-WITH-CORRECTION:** deterministic keyword insertion + static CTA are LAW-2
  and purity safe; an LLM hook would break `build_caption`'s pure-function contract if invoked inside it —
  so it is explicitly scoped as a separate opt-in pre-authoring step feeding the deterministic caveat gate.

**Net:** generator≠grader caught a phantom capability (first-comment) and a scar-#3 fragile guard
(phrase-matched caveats) that the naive recommendation would have shipped as the next B — the corrected
recommendation is stronger (explicit caveat field + fail-closed) and buildable.

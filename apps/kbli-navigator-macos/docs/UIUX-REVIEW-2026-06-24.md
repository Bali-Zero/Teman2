# KBLI Navigator — UI/UX Review Report (Day + Night)

**Date:** 2026-06-24 · **Subject:** variant D "Registry Dossier", code 55203 · **Panel:** 4 LLM
(Gemini 3.1 Pro High [vision], DeepSeek V4 Pro [IA/contrast-math], Codex GPT-5.5 [vision], Claude Opus 4.8 [vision]).

Each reviewer saw the actual rendered Day+Night screens (6 bands) — except DeepSeek (text-only, reviewed
IA + token math). Findings below are **ranked by cross-panel agreement** (the strongest signal): a fix
flagged independently by 3-4 reviewers is near-certain to be real.

---

## ⭐ CONSENSUS P1 — flagged by ALL or 3/4 (fix these first)

### C1. Verdict still reads as a contradiction · **4/4**

"In Bali: closed to PT PMA" + "National: open · 100%" + the ledger's "Foreign Ownership: 100% Open"
compete. On a 2-second scan the eye keeps the green/open data, not the blocker.
**Fix (synthesised):** promote the Bali answer to a **full-width verdict banner under the title**
("Bali operating answer: a PT PMA cannot register this code"). Demote the national fact to a
subordinate reference line/ghost-chip. Move "medium conf." OUT of the main pill into metadata below.

### C2. Periwinkle leaks outside Zantara (constraint violation) · **2/4 explicit (DeepSeek+Codex), real**

The "Renumbered 55193→55203" pill (and some rails) use the periwinkle/blue family, but the locked rule
is **periwinkle = Zantara only**. This dilutes the footer's unique signal.
**Fix:** introduce a separate "statutory blue" token for renumber/national/reference; keep periwinkle
strictly in the Zantara chat.

### C3. Night-mode contrast failures (WCAG) · **3/4 (Gemini+DeepSeek+Codex), with numbers**

DeepSeek computed: night coral `#E8746A`+white ≈ **2.9:1**, accent callouts (terracotta/orange)+white ≈
**2.2–2.3:1** — both below the 4.5:1 minimum. Gemini: risk pill dark-green-on-dark-green ≈ invisible; ID
right-column text vanishes; "Open 100%" labels illegible on `#4C5158`.
**Fix:** (a) callouts → keep colored fill but set **text to ink** (`#F2F3F5` night / `#3A352F` day), not
white; (b) darken night coral toward `#C85A5A`; (c) pills → bright saturated text on a 15-20% wash of the
same hue; (d) lift night secondary-text +10-15% and hairlines to 14-16% white in dense tables.

### C4. Bali Intelligence buried too low · **4/4**

The gold-tier reality-check (oversupply, real costs, common mistakes) is the highest-value investor
content but sits BELOW reference drawers + related codes. Owner moved it down deliberately — so the panel
agrees: **keep the full block low, but surface a compressed 3-line "Bali reality check" right after the
Licensing warning** (teaser high, deep-read low). Best of both.

### C5. "Wall of plates" monotony · **4/4**

License + PP28 + authority + TKA + complementary + related all share the rounded-rect + rail + mono-label
motif → scan landmarks blur into a "tax form".
**Fix:** restrict the full LedgerPlate to authoritative LEGAL blocks only; make Related Codes + Bali Intel
visually distinct (lighter container, fewer separators); widen macro-block spacing (28→34); add a tiny
contextual icon to the Authority plate title as a differentiator.

---

## P2 — flagged by 2-3 reviewers (high value)

### C6. Collapsibles aren't discoverable · **3/4**

PP28 / TKA / Complementary drawers look like static ledger headers; the chevron is decoupled at the far
right edge. **Fix:** make the whole header row tappable, move chevron to sit next to the title, rotate on
open, and add payload-preview copy ("Show 12 positions" / "Guest Relation Mgr, Hotel Mgr, +10").

### C7. Roadmap contradicts the warning · **1/4 (Codex) — but objectively correct, promoted**

After "national procedure does NOT apply to a PT PMA in Bali", the roadmap's **step 1 is "PT PMA
incorporation"** — it recommends the path it just invalidated. **Fix:** relabel the roadmap per scenario
("Non-PMA / MSME Bali registration path") OR show the PT-PMA path as a disabled/blocked branch for codes
where Bali closes it. _(High-impact correctness bug; only Codex caught it — worth fixing.)_

### C8. Bali-Intel bullets are false affordances · **2/4 (Gemini+Opus)**

The "Real costs"/"Common mistakes" bullets are wrapped in rounded plate-like chips — same shape as
tappable elements. **Fix:** drop the per-bullet chip wrappers; render as a plain bulleted list inside the
single gold-tier plate (3pt amber indent rail).

### C9. PP28 segmented "Mikro" uses system-blue · **2/4 (Gemini+DeepSeek)**

The active segment's default system blue doesn't map to any Night token and clashes with anthracite.
**Fix:** active segment → orange `#F2954A` (night) / terracotta (day).

### C10. TKA EN↔ID tracking gap · **1/4 (Gemini)**

~400pt of whitespace between left EN title and right-aligned ID title breaks the eye's column link.
**Fix:** dotted leader line, or cap the row max-width to ~500pt.

---

## P3 — polish (1 reviewer each, low-risk)

- **C11. Related-card status dots uninformative** (Opus): all 6 show identical "Open 100%" → either show
  each code's own Bali verdict, or label the dot "National".
- **C12. Night card-depth subtle** (DeepSeek+Codex): bg `#3C4047` vs card `#4C5158` close → add a 6%-white
  top edge-highlight or 12% inner stroke (no heavy shadow).
- **C13. Orange overused in Night** (Codex+Opus): code + rails + TKA codes + gold-intel all orange →
  reserve orange for the main code + attention states; secondary codes neutral mono.
- **C14. Roadmap whitespace inefficient** (Codex): tighten vertical gaps 20-25%; durations → muted not faint.
- **C15. Read-Full-Guide weak nav signal** (DeepSeek+Codex): add a left rail + trailing arrow.
- **C16. Day muted text too faint in dense legal areas** (Codex): raise muted contrast on legal-basis
  captions + PB UMKU chips.

---

## Recommended implementation order (max UI/UX gain per edit)

1. **C1 verdict banner** + **C7 roadmap relabel** — the two correctness/clarity bugs (a user could make a
   wrong legal decision). Highest impact.
2. **C3 night contrast** + **C2 periwinkle token split** — accessibility + constraint compliance (token-level,
   touches Theme.swift, cheap, fixes many call-sites at once).
3. **C6 collapsible affordance** + **C8 false-affordance chips** — interaction clarity.
4. **C5 wall-of-plates** + **C4 Bali-intel teaser** — rhythm + IA.
5. P3 polish pass (C9-C16).

> Panel note: 4/4 convergence on C1, C4, C5 means these are not stylistic opinions — they are structural.
> The owner's locked constraints (photo plate, no pricing, periwinkle=Zantara, LedgerPlate signature,
> native fonts, hairlines) were respected by all reviewers; C2 actually _enforces_ one of them.

# Proposed Amendment — 2026-07-16 — Accessibility Discipline (17 rules + hooks)

## ⛔ Constitutional conflicts — PENDING ZERO (added post red-team, 2026-07-16)

Codex gpt-5.6-sol xhigh red-team review of the branch carrying this amendment found the "proposed"
framing below does not match what actually landed in the live prompt blocks: `wr2-storyboarder.md`
and `wr2-brief-interpreter.md` already carried parts of this ruleset, and four of the 17 rules
directly contradict a currently-enforced constitutional gate or cron validator. Until Antonello/Zero
reconciles each one, **rules 1, 5, 12, and 17 are NOT active** in the live agent prompts — the
trimmed prompt blocks in both agent files now say so explicitly, and only the six
constitution-compatible sub-rules stay live (audience-register-follows-real-audience,
stakes-before-mechanism, one-anchor-metaphor, ≤2 tone registers, close-on-reader-action,
cover-subhead-essential-fact). The four blocked conflicts, verbatim:

1. **Rule 1 (gloss-before-code) vs. constitution Article 6.1.2.** Rule 1 asks every regulation
   code/acronym to get a same-slide plain-English gloss on first mention. Article 6.1.2's
   always-untranslated bucket (`KITAS`, `KBLI`, `NPWP`, etc.) is glossed **verbatim, NO gloss** —
   glossing those terms is a **hard fail**, not a style choice. Rule 1 was still marked
   "awaiting Zero's nod" in this very file, yet the live storyboarder prompt applied it anyway
   before this fix — a doctrine-drift bug, not just a documentation inconsistency.
2. **Rule 12 (length polarization: 4-5 or 8-12, banning 6-7) vs. three existing slide-count
   contracts.** Constitution Article 1.2 mandates **7-10** slides. `wr2_draft_generator.py`'s
   normalizer accepts **6-11**. The archetype liveness-tier routing explicitly assigns
   breaking→6-7, developing→7-8, evergreen→9-10 slides — ranges Rule 12 would ban outright.
   Rule 12 conflicts with all three, not just one.
3. **Rule 5 (ban `qa-dialogue` for regulatory-explainer) vs. constitution Article 13.1.** Article
   13.1's archetype table explicitly lists `qa-dialogue` in the `regulatory-explainer` layout pool
   (and in `anti-cliche` and `comparison` too). Rule 5 says "never" for the same archetype
   Article 13 says "yes."
4. **Rule 17 (ban categorical cover subheads) vs. `wr2_draft_generator.py` rule 9 and
   `cover-photo.md`.** Both currently prescribe categorical tag examples ("VISA UPDATE",
   "IMMIGRATION", **"TAX ALERT"**) as the correct subhead pattern — the exact pattern Rule 17
   calls out to kill.

Fix path: reconcile constitution Article 1.2/6.1.2/13.1, the cron validator's slide-count range,
and `cover-photo.md`'s subhead examples in one atomic change alongside whichever of rules 1/5/12/17
Zero approves — never activate a rule number here piecemeal against a contradicting live gate.

---

**Status**: PROPOSED, awaiting Antonello/Zero veto/approve on Rule 1 specifically (see flag below);
Rules 2-17 are additive clarifications of existing constitution intent and can merge on the normal
Article 11 amendment path once smoke-tested on a live carousel. **Rules 1, 5, 12, 17 additionally
blocked by the constitutional conflicts above — see that section, not just the Rule 1 flag.**

**Author**: research-accessibility (this session, 2026-07-16), synthesized by the Fable orchestrator.
**Trigger**: Zero's mandate item (C) — _"the '1 August' carousel is still too hermetic for the general
public — beauty and simplicity of communication, inspired by the best."_ The August 1 PMK 37/2025
marketplace-withholding carousel (`draft_id a80130df`) is the live probe for this ruleset (Front C2,
tracked separately).

**Companion changes** (session-executable, tracked in this PR/handoff):

- `skills/bali-zero-brand/layouts/evidence-carved.md` — take_label variety section (separate front,
  already shipped this session — unrelated to accessibility but same PR).
- `agents/wr2-storyboarder.md`, `agents/wr2-brief-interpreter.md` — "Accessibility discipline"
  prompt block (audience-register-follows-real-audience rule + pointer to this file), now TRIMMED
  (2026-07-16 red-team fix) to only the six constitution-compatible sub-rules listed above. **Update
  (2026-07-16, post red-team)**: the earlier "BLOCKED — HOME-only, host_boundary refuses the write"
  note here was stale by the time of the red-team review — these agent defs were vendored into repo
  `.claude/agents/` (project-level precedence over the HOME copies) earlier this session specifically
  to route around that block, and both files' accessibility blocks are live in the repo-tracked
  copies today, trimmed per the conflicts above.

---

## ⚠️ Header flag — Rule 1 needs Zero's nod before constitution hardening

**Rule 1 (gloss-before-code) is additive, not destructive, but sits close to an existing habit**:
constitution.md Article 6.1.2 establishes a "verbatim, NO gloss" convention for the
always-untranslated bucket (KITAS, PT PMA, KBLI, NPWP, etc. — cite bare, the audience already knows
them), and Article 6.4 mandates regulation codes (`PMK 37/2025`, `KEP-71/PJ/2026`) be cited
**verbatim, never paraphrased**. Rule 1 does not ask to paraphrase or drop the code — 6.4's
verbatim requirement stays fully intact — it asks for a plain-English gloss to sit ALONGSIDE the
code on first mention. That's additive on its face, but it softens the "cite it and move on"
instinct that 6.1.2 trains for the always-untranslated bucket, which is why this amendment proposes
it as a SKILL-level prompt rule for now (storyboarder/brief-interpreter guidance) rather than
hardening it straight into the constitution's Article 6 — Zero's explicit nod is requested before
that promotion.

**Empirical grounding** (this session's engagement-data review, N as noted per finding):

- announcement-only regulatory carouseli: Save/Like −46%, Share/Like −35% (N=13)
- qa-dialogue format on regulatory topics: −66% Save/Like (worst-performing format measured)
- tax carouseli pairing a citation with a concrete consequence: +78% Save/Like
- evidence-carved layout family (facts-then-stance structure): +22% Save/Like

The pattern across all four: readers save and forward content that tells them **what changes for
them**, not content that announces a rule and stops. That is the throughline for all 17 rules below.

---

## The 17 rules

Each rule: one-sentence statement, then a before → after pair grounded in the domain already in
front of this session (PMK 37/2025 marketplace withholding, KEP-71 SPT extension) so the examples
are load-bearing, not generic.

### 1 — Gloss-before-code

Never state a bare regulation code or acronym without a same-slide plain-English gloss immediately
attached to it (see header flag above — additive to Article 6.4's verbatim requirement, not a
replacement for it).

> **Before**: "PMK 37/2025 applies from 1 August 2026."
> **After**: "A new finance-ministry rule (PMK 37/2025) — the one that turns marketplaces into tax
> collectors — applies from 1 August 2026."

### 2 — Name-the-reader

State explicitly, in the reader's own words, who this slide is talking to — never a taxonomy label
from the internal brief.

> **Before**: framing pitched at "founder" register on a carousel actually read by everyday
> marketplace sellers.
> **After**: "If you sell on Tokopedia, Shopee, Lazada, or Blibli — this is about your payout, not
> your company."

### 3 — Stakes-before-mechanism

State what changes for the reader BEFORE explaining how or why the mechanism works.

> **Before**: "PPh 22 is withheld under Article 22 of the Income Tax Law by parties appointed as
> collectors, including specified marketplaces from 1 August 2026."
> **After**: "Starting 1 August, 0.5% comes out of your marketplace payout before it reaches you.
> Here's the rule that does it: PPh 22 (Article 22 income tax), collected by the marketplace itself."

### 4 — Analogy-before-mechanism

Introduce one plain-language analogy before the formal explanation.

> **Before**: "Marketplaces become withholding agents under PMK 37/2025."
> **After**: "Think of it like a toll booth on your payout: the marketplace now stops 0.5% before it
> reaches your bank account. Formally: PMK 37/2025 makes marketplaces PPh 22 withholding agents."

### 5 — Kill qa-dialogue for regulatory

Never use the `qa-dialogue` layout family for regulatory-explainer carouseli — measured −66%
Save/Like, the worst-performing format tested on this content class.

> **Before**: "Q: What is PPh 22? A: PPh 22 is an income tax withheld at source under Article 22..."
> **After** (same content, direct-statement layout instead): "PPh 22 is the income tax now taken
> from your payout automatically — no filing needed on your side to trigger it."

### 6 — Acronym-chain needs a connecting clause

When multiple codes/acronyms appear together, connect them with one clause explaining how they
relate — never list them bare in sequence.

> **Before**: "SKB, bukti pemungutan, SPT Tahunan, NPWP/NIK, PPN/PPnBM all apply."
> **After**: "You may need an exemption letter (SKB) to avoid this. If it's withheld anyway, you get
> a receipt (bukti pemungutan) to claim back on your annual return (SPT Tahunan), filed under your
> tax ID (NPWP/NIK)."

### 7 — Smart-friend test

Before shipping, read the slide aloud as if explaining it to a smart friend outside the industry —
if you'd naturally add a clarifying phrase out loud, the slide is missing it on the page.

> Operationalized as the acceptance gate for the other 16 rules: a slide that fails the smart-friend
> test is the slide that needs rules 1/3/4/6 applied to it, in that order.

### 8 — Concrete consequence, never a category label

State the actual, concrete effect on the reader — never just the name of the category it falls
under.

> **Before**: "Tax compliance implications apply."
> **After**: "You'll see 0.5% less in your payout starting 1 August."

### 9 — One anchor metaphor per carousel

Pick exactly one central metaphor and return to it across the carousel — never introduce a second,
competing metaphor mid-run.

> Candidate anchor for the August 1 carousel: **"same tax, new cashier — it comes out before the
> money reaches you."** Every slide that needs a metaphor reuses this one; it does not reach for a
> second image (no toll booth AND a different metaphor in the same carousel — pick one).

### 10 — Process-step-map for procedures

Any carousel describing a multi-step process (apply for X, claim Y back) renders it as an explicit
numbered step map — never buried inside a paragraph.

> **Before**: "To claim it back you first need to file your SKB then wait for approval then submit
> at year-end alongside your SPT."
> **After**: "1. Apply for SKB (exemption letter). 2. Wait for approval. 3. File it with your SPT
> Tahunan at year-end."

### 11 — Annotate the number

Every number cited gets an annotation of what it means in practice — never a bare figure.

> **Before**: "0.5%."
> **After**: "0.5% — about 5,000 IDR for every 1,000,000 IDR you sell."

### 12 — Length polarization: 4-5 vs 8-12, never the flat middle

Pick either a tight 4-5 slide carousel (breaking/simple story) or a full 8-12 slide carousel
(complex/evergreen story). The flat 6-7 middle tests worst on both completion rate and depth —
neither short enough to be a quick hit nor long enough to actually explain the mechanism.

### 13 — Bullet-promise = what changes for YOU

When a heading promises a count of items, each bullet is phrased as a concrete change for the
reader — never an abstract fact about the rule.

> **Before**: "THREE NEW RULES: Article 22 applies; withholding is automatic; exemptions require
> SKB."
> **After**: "THREE THINGS THAT CHANGE FOR YOU: Your payout drops by 0.5%, automatically. You don't
> file anything to trigger it. You CAN get it back — but only if you apply for an SKB first."

### 14 — Close on the reader's next action

The closing slide states one concrete, doable action the reader can take right now — never a vague
summary of what was just explained.

> **Before**: "This is an important change for online sellers to understand."
> **After**: "Check your next payout for the 0.5% deduction. If you qualify for exemption, apply for
> your SKB before your next sale."

### 15 — Sentence-complexity cap (~FK8), even in uppercase

Even in uppercase editorial voice, keep sentence complexity around Flesch-Kincaid grade 8: short
clauses, one idea per sentence, no nested subordinate clauses.

> **Before**: "Marketplaces designated as withholding agents pursuant to PMK 37/2025, which was
> signed to implement Article 22 of the Income Tax Law as amended, must withhold PPh 22 at the point
> of payout disbursement to registered sellers."
> **After**: "PMK 37/2025 makes marketplaces the tax collector. They withhold PPh 22. It happens the
> moment they pay you."

### 16 — Data slides get a plain source note

Every slide citing a number or data point carries a plain-English footer naming where the number
came from — not just a bare citation code.

> **Before**: footer reads `PMK 37/2025 Ps. 4`.
> **After**: footer reads `PMK 37/2025 Ps. 4 — the finance ministry regulation, Article 4`.

### 17 — Audience-first lede on cover subhead

The cover subhead carries the single fact that matters most to THIS reader first — never a generic
category tag.

> **Before**: subhead `TAX UPDATE`.
> **After**: subhead `YOUR PAYOUT, MINUS 0.5%`.

---

## Hook formulas (5)

Real statutory urgency only — these frame an ACTUAL deadline/consequence already established in the
brief; they are never a manufactured-urgency device. Hype stays banned (constitution Article 6.6/6.7
untouched).

1. **Clock-Consequence** — pair a specific date/deadline with its concrete consequence. _"From 1
   August, this happens to your payout."_
2. **The Reversal** — state the old rule, then the new rule that replaces it. _"It used to work like
   X. Now it's Y."_
3. **Silent-Majority-Affected** — name how many/most people this quietly affects, not just the rule
   itself. _"Almost every online seller — most don't know yet."_
4. **Countdown-to-Real-Consequence** — frame the remaining time before a REAL consequence lands, not
   a manufactured one.
5. **Already-Late** — for retroactive or already-in-force rules, frame that the clock has already
   started, not that it's about to.

---

## Engagement-data preamble (cited above, reproduced here for the record)

- Announcement-only regulatory carouseli: Save/Like −46%, Share/Like −35% (N=13).
- Qa-dialogue format on regulatory topics: −66% Save/Like — the single worst-performing format
  measured on this content class.
- Tax carouseli pairing a citation with a concrete consequence: +78% Save/Like.
- Evidence-carved layout family (facts, then a subordinated stance): +22% Save/Like.

Read together: the audience saves and forwards content that tells them what changes for them, in
their own words, at their own reading level — not content that announces a rule and stops. Rules
1-17 above are that principle applied slide-by-slide.

## Antonello/Zero veto checklist

- [ ] Read this amendment file fully.
- [ ] Decide on Rule 1 specifically (header flag above) — approve as skill-level guidance only, OR
      approve for eventual Article 6 constitution hardening, OR reject.
- [ ] Rules 2-17: no single rule retracts an existing constitution article — they are additive
      clarifications. Default posture: approve for skill-level guidance (storyboarder/
      brief-interpreter prompt patch) without a constitution edit.
- [ ] Sample-render the August 1 rewrite (Front C2, separate handoff) applying this ruleset, verify
      it reads as simpler without losing regulatory accuracy.
- [ ] If approved: this file stays as the doctrine reference (agents point to it); no constitution
      edit needed unless Rule 1 is explicitly promoted.

## Rollback safety

This amendment is skill-level guidance only (storyboarder/brief-interpreter prompt text), not a
constitution or code change — rollback is deleting the "Accessibility discipline" prompt block from
the two agent files and this file stays as archived doctrine. No renderer/composer behavior depends
on it (unlike the take_label variety gate shipped alongside this in the same session, which IS
code-enforced and tracked separately).

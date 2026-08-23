---
adversarial_review: kimi-k3
---

# D12 active-stay-permit exclusion — BALI_ZERO_POLICY source, drafted 2026-08-23

E5 increment 8 (targets seq-14, chaining off seq-13's SIGNED payload). This rule ships LIVE, not
dormant — PR #4695 (merged 2026-08-23) closed the interview-side gap the
`.claude/skills/modus/PENDING-ARMS.md` "v2-d12, D12 rework mandate" row tracked; see "Live from
activation, not dormant" below. Author: v2-d12.

**UPDATED 2026-08-24 (Kimi refuter finding F7): the line above originally said seq-13's SIGNED
payload was "not yet available as of this draft" — stale as of this correction.** Seq-13 signed,
activated, and went LIVE in production at `2026-08-23T16:27:06.707408Z`
(`rulepack-prod-013.signed.json`, `payload_sha256 b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8`,
independently re-verified against `origin/main`). D12's `product_version_id`
(`63f64a7e-2bff-5a48-8c3b-7ad5349e8c91`) is confirmed unchanged in seq-13's real source file — the
pin below survives. **Do NOT fold this rule into seq-14 yet regardless of seq-13's availability**:
a separate, independently-confirmed defect (offshore applicants can never reach the questions this
rule's fact depends on — PR #4727, in progress) blocks the fold until fixed. **UPDATED 2026-08-24:
Zero has now ruled on both KITAP-widening (RESOLVED — see "What is VERIFIED" below, the rule's
breadth is correct as drafted) and renewal-pending (RULED, verbatim quote and implementation
status tracked in PENDING-ARMS — as of this update, the derivation change per that ruling has NOT
yet landed in `fact_registry.py`, so `_derive_has_active_stay_permit` still resolves an
expired-but-renewal-filed applicant to `False`, a now-confirmed wrong answer). Both offshore
reachability (PR #4727) and the renewal-pending derivation change block the fold — do not fold
D12 until both land, in addition to the pre-existing seq-13 dependency already satisfied above.**
Seq-13 being ready removes one blocker, not
all of them.

## What is VERIFIED

The ruling exists and its text is fixed by two independent, already-committed artifacts on
`origin/main`, both dated 2026-08-23:

1. `apps/backend-rag/backend/services/visa_engine/fact_registry.py`,
   `_derive_has_active_stay_permit`'s docstring, verbatim: "Owner ruling (2026-08-23): an
   applicant WITH an active KITAS is excluded from D12."
2. `.claude/skills/modus/PENDING-ARMS.md`, the row opened by v1-facts on the same date, which
   attributes the ruling to Zero in the original Italian: **"chi ha kitas attivo va escluso da
   D12"** — sourced there to a "D12 rework mandate" dispatch.

Both artifacts agree on content (an applicant who currently holds an active **KITAS** — the
verbatim word in both quotes above — does not qualify for D12) and on date. Neither is a
regulatory citation — this is recorded as a **business/eligibility policy decision**
(`SourceAuthorityType.BALI_ZERO_POLICY`,
`apps/backend-rag/backend/services/visa_engine/enums.py:409`), not a `PRIMARY_LAW`/
`IMPLEMENTING_REGULATION`/`OFFICIAL_PORTAL` fact. No Ditjen Imigrasi page or statute is cited for
it anywhere in the codebase as of this draft, and this document does not manufacture one.

**UPDATED 2026-08-24 (F3 CLOSED — Zero ruled, the rule's KITAP breadth is VERIFIED, not
interpretive).** A prior revision of this document flagged the rule's breadth beyond
"kitas attivo" (it also fires on KITAP-class E-shaped codes) as an unconfirmed inference and
surfaced it to Zero as an open question (team-lead, 2026-08-24). Zero ruled on it directly, in
Italian, verbatim:

> "non si possono mai avere due visa contemporaneamente"

This is not a KITAS-specific clarification — it is a general principle (you can never hold two
visas at the same time), so it grounds the rule's condition exactly as drafted: any applicant
whose `derived.has_active_stay_permit` resolves `True` — KITAS, KITAP, or any other class the
`^E\d+[A-Z]?$` shape catches — already holds an active stay permit and is excluded from D12 under
this SAME general principle, not a separate, narrower extrapolation of the 2026-08-23 wording.
**This ruling is now the third artifact grounding the rule, alongside the two above** — cite it,
not the earlier KITAS-only quote, whenever this rule's breadth needs justifying. Same authority
class as the other two (`BALI_ZERO_POLICY`, business/eligibility decision, no regulatory
citation implied or manufactured).

## What is NOT independently verified here (interpretive only, not cited doctrine)

The evident rationale — D12 is a *pre-investment exploration* instrument (survey/feasibility
scouting ahead of incorporation, per `research/visa/doctrine-factory/cards/D12.md` §3.1-3.2), so
an applicant who already holds an active residence permit is presumably already in the country on
a different, more substantive legal basis and does not need a pre-investment visit product — is
this author's own inference from the ruling and the D12 doctrine card. It is written here so a
future reader can tell it apart from the three VERIFIED sources above; it is not itself a claim
with a `claim_id`, and D12.md (dated 2026-08-17, six days before this ruling) makes no such
statement. If Zero's actual rationale differs, that difference does not change the ruling's
substance, only this document's explanatory paragraph.

**Separately, NOT settled by the above and still an open question surfaced to Zero (team-lead,
2026-08-24): whether "you can never hold two visas at the same time" implies an active-permit
exclusion should exist on OTHER products too, not only D12.** D12 is one of ~38 products; Zero was
asked specifically about D12's rule and answered about D12's rule. Reading a pack-wide sweep out
of one general-principle sentence, without a separate ruling naming which other products it
applies to, would repeat the exact class of error this document was corrected for once already
(extrapolating a ruling past its literal scope) — just in the opposite direction (widening past
what was asked, rather than narrowing). This document takes no position on that question and no
other product's rule is touched by this fold.

## First use of `BALI_ZERO_POLICY` in this pack

`SourceAuthorityType.BALI_ZERO_POLICY` and `SourceAuthorityType.PRICING_CATALOG` are declared in
`enums.py` and the JSON Schema but — confirmed by a full scan of every `rulepack-prod-*.source.json`
file's `source_records` array through sequence 12 — neither has ever been instantiated. This is the
first `BALI_ZERO_POLICY` source_record this pack will carry.

That matters for one specific, previously-documented failure mode: `content_sha256` on an
`OFFICIAL_PORTAL` source is **unverifiable by construction** when the underlying page embeds a
per-request CSRF token (two fetches of the same live page hash differently — measured directly on
this pack's own portal sources). A `BALI_ZERO_POLICY` source pointing at a repo-tracked file does
not have that problem to the same degree: this file's bytes are fixed the moment it is committed,
so `content_sha256` (`hashlib.sha256` over the file's own raw bytes — see
`test_draft_source_record_content_sha256_matches_the_actual_policy_doc`) is reproducible by any
future verifier who reads the same commit. The companion `SourceRecord` JSON in this directory
therefore points its `canonical_url` at this file's own repo path rather than at any external URL.

**CORRECTED 2026-08-24 (Kimi refuter finding F6) — two overstatements in the paragraph above,
now removed.** (i) "exactly the git blob's SHA-256" was false: a git blob id hashes the
`"blob <len>\0"` framing plus the content (and, in any case, this repo's git objects are SHA-1,
not SHA-256) — what the test actually computes is `sha256` over the file's raw bytes, which is a
real and useful guarantee, just not the one that sentence named. (ii) "reproducible forever" only
holds while the file never changes. This file was revised multiple times on its first day and is
explicitly the living home for this rule's ongoing documentation — the next edit invalidates the
hash. With `freshness_policy: null` and `safety_critical: false` on the source_record, nothing in
the pack itself detects that staleness; the ONE thing that will is
`test_draft_source_record_content_sha256_matches_the_actual_policy_doc` going red — for what will
look like an unrelated documentation typo fix, not a content-integrity failure. That is a virtue
(a stale hash cannot silently ship) but also a maintenance cost worth naming rather than leaving
implicit.

## The rule this source backs

`hf.d12-active-stay-permit-excluded` (drafted, not yet folded — see the companion JSON in this
directory): HARD_FILTER, EXCLUDE on `derived.has_active_stay_permit == true`,
`on_unknown: NEEDS_INPUT` (never silently admit an applicant whose current-status code is
undisclosed — matches the sibling `hf.d12-onshore-conversion-excluded`'s own on_unknown choice and
the fact's own derivation docstring, which is explicit that guessing `False` on an UNKNOWN input
would wrongly ADMIT).

## Boundary choice: a permit expiring on `effective_at`'s date is still active that day — RULED, 2026-08-23

**UPDATE 2026-08-23 (same day, later): this question is now settled by an actual authority, not
merely by internal consistency.** Zero ruled directly on the permit-validity axis, verbatim in
Italian: **"si valido fino alle 10pm del giorno. si consiglia di recarsi all'immigrazione
aeroportuale nel primo pomeriggio del giorno della scadenza al massimo"** — a permit stated as
valid "until DD-MM-YYYY" is valid through that date, specifically until 22:00, with practical
guidance to complete any airport-immigration business by early afternoon of the expiry day at the
latest. This closes the "one question this document does NOT resolve" the paragraph below
originally flagged — see `.claude/skills/modus/PENDING-ARMS.md`'s 2026-08-23 "v2-d12, Zero's ruling
on the permit-validity axis" row for the full closure record, including a gap this ruling itself
introduces (below).

**Original text, preserved as the reasoning that held before the ruling landed**: `derived.has_active_stay_permit` (`fact_registry.py`'s
`_derive_has_active_stay_permit`, authored in #4650 — not by this rule) computes
`expiry_date >= reference_date`, an inclusive comparison, and its own docstring states the
rationale explicitly: it "mirrors `_derive_age_years`'s own reference-date comparison" — an
existing, pre-dating engine-wide convention for date-boundary inclusivity, not a choice made for
D12 specifically. This rule and its tests inherit that convention by consuming the derived fact;
they do not introduce or re-derive it. Zero's ruling text on the KITAS-exclusion policy itself
("chi ha kitas attivo va escluso da D12") does not speak to day-granularity at all, so before
today's second ruling the convention was neither "from the ruling" nor this author's own reading —
it was an existing engine primitive, pinned here by test rather than asserted anew. **That gap is
now closed**: `expiry_date >= reference_date` is confirmed correct by the ruling quoted above, not
merely internally consistent with `_derive_age_years`.

**One thing the new ruling settles and one it does not.** Settled: the DATE the permit's stated
expiry falls on counts as active — no change needed anywhere in this draft. NOT settled: Zero's
ruling names a TIME (22:00); `_derive_has_active_stay_permit` compares DATES only, with no
time-of-day component. Between 22:00 and midnight on the expiry date, a real permit is technically
expired while this engine still reports it active — a two-hour window, once, per permit. This is
judged immaterial for D12 today: this rule (and the engine generally) makes eligibility decisions,
not same-day time-of-day ones, and Zero's own operational guidance below means no legitimate
interaction with the permit should be happening in that window anyway. It would stop being
immaterial only if a future rule or engine surface started deciding on time-of-day rather than
date — flagged here so that future work does not have to rediscover the gap from scratch.

## Operational guidance (not engineered) — Zero, 2026-08-23

The second half of the same ruling is practical client-facing advice, not a fact about this
codebase, and is captured here verbatim so it is not lost — it is deliberately NOT turned into a
rule, a fact path, or engine output, because the tool has no surface for advice like this today:

> "si consiglia di recarsi all'immigrazione aeroportuale nel primo pomeriggio del giorno della
> scadenza al massimo" — recommendation: go to airport immigration in the early afternoon of the
> expiry day at the latest.

This is real, field-tested guidance from an agency that handles these permits daily, worth
preserving for whoever eventually builds a client-facing guidance/next-steps surface for D12 or any
other stay-permit-adjacent product — it has no home in the RulePack or the fact registry, so this
document is where it lives until one exists.

## Live from activation, not dormant — #4695 merged 2026-08-23

**UPDATE 2026-08-23 (same day, third pass): #4695 has MERGED.** Merge commit
`88faa0e0450a4986730829b8d2990229b11bf216`, `2026-08-23T14:56:27Z`. `v1-facts`'s
interview extension ("wake `derived.has_active_stay_permit`'s dormant positive
path") is on `origin/main`: a two-step gate — `holds_stay_permit` ("do you
currently hold a limited or permanent stay permit (KITAS/KITAP)?"), and on
yes, `stay_permit_code`, a 29-code E-series selector transcribed from the
applicant's own permit card — wired to `immigration.current_status_code`,
the exact fact this rule's condition keys on through `derived.has_active_stay_permit`.

**This rule is therefore LIVE, not dormant, from the moment its own fold
(seq-14, still pending seq-13's signature) activates.** It will exclude a
real applicant on the first request that matches, not merely be correct-but-
unreachable. The fold's PR body must say this plainly — a rule described as
dormant invites a lighter review; this one has an applicant on the other
side of it from day one.

**Verified, not assumed, before writing this**: all 29 codes the selector
offers (`E23, E23U, E23V, E28A, E28B, E28C, E28D, E28F, E30, E30A, E30B,
E30E, E30F, E31A, E31B, E31C, E31D, E31E, E31F, E31G, E31H, E31J, E33, E33A,
E33B, E33C, E33E, E33F, E33G`) match `_STAY_PERMIT_STATUS_CODE_SHAPE`
(`^E\d+[A-Z]?$`, `fact_registry.py:99`) — checked programmatically against
the compiled pattern itself, 29/29, zero mismatches. A selector offering a
code the derivation cannot parse would fail safe (UNKNOWN -> `NEEDS_INPUT`
via this rule's `on_unknown`) but would be silently useless for a precisely-
transcribed answer; that risk is closed.

**The former dormancy tripwire went GREEN through #4695's merge, and here is
exactly why — recorded so the mistake in its own design isn't repeated.**
`test_declared_dormancy_no_interview_status_code_is_e_series_shaped` was a
backend-only Python test that hardcoded a snapshot of the OLD 8 non-E
interview codes and asserted none of them activates the permit fact. #4695
touched only `apps/mouth` frontend files (`fact-mapper.ts`, `flow.ts`,
`tree.ts`, `i18n.ts`, `flow.test.ts`) — zero backend files — so there was
never a mechanism by which a Python test could observe that diff landing.
The docstring's original "a future red here means the extension landed"
framing assumed a cross-language observability the test never had; that was
a flaw in the tripwire's own design, not a defect in #4695 or in the fact
wiring.

**First replacement attempt, corrected after a further review round.** The
first successor read `rulepack-prod-007.source.json`'s 29 E-prefix product
codes and claimed to prove "reachability end-to-end for the full catalogue
the interview can actually send." That claim repeated the ORIGINAL
tripwire's exact mistake, only with a JSON-sourced list standing in for a
hardcoded one — reading a file is not the same as observing the frontend,
and this test still cannot see `fact-mapper.ts`. **Final replacement**,
`test_e_series_shape_activates_permit_fact_visit_class_shape_does_not`,
scopes its claim to what a backend test can actually prove: the
DERIVATION's shape rule — codes matching `^E\d+[A-Z]?$` activate the permit
fact and the 8 old visit-class codes do not — using real product codes from
the same catalogue as representative E-shaped examples, never as a claim
about what the interview currently offers. The docstring says explicitly
that interview↔derivation agreement is UNVERIFIED by any automated check
today; see the PENDING-ARMS row "v2-d12, interview-catalogue cross-boundary
sync unverified" for the real cure (a shared generated artifact or a
frontend-side test — not a pytest parsing TypeScript). Mutation-checked:
flipping the rule's condition value turns this test red along with the
others, confirming it has real bite.
**Near-miss found during pre-fold due diligence (2026-08-24): `safety_critical`
almost got "corrected" to match a sibling, which would have broken production.**
Re-checking this rule's draft against the live seq-13 source file before folding
it into seq-14 turned up that the sibling `hf.d12-onshore-conversion-excluded`
carries `safety_critical: true`, contradicting an earlier version of this rule's
`_note`, which claimed `safety_critical: false` "matches the sibling D12
HARD_FILTER." That claim was false — worth stopping on, because the two rules
are NOT interchangeable on this field. `safety_critical` is read pack-wide by
`evaluate_path._apply_safety_critical_source_hold`: for every active rule with
`safety_critical=true`, it demands every one of that rule's `source_refs` pass
`_source_is_authoritative_and_applicable` (authority_type in
`{PRIMARY_LAW, IMPLEMENTING_REGULATION, OFFICIAL_PORTAL, OFFICIAL_CIRCULAR}` AND
a `canonical_url` on the pinned government-host allowlist) — any failure forces
`HUMAN_REVIEW_REQUIRED` on every otherwise-conclusive decision in the entire
pack, not just this product. This source_record's `authority_type` is
`BALI_ZERO_POLICY` (not in that set) and its `canonical_url` is a repo-relative
path (no scheme at all) — it fails on two independent grounds, plus a third via
`freshness_policy: null` (`_evaluate_source_freshness` returns
`FRESHNESS_POLICY_NOT_DEFINED`). Flipping this rule to `safety_critical: true`
to mirror the sibling would therefore have triggered a pack-wide
`HUMAN_REVIEW_REQUIRED` override the moment it activated in a signed pack — a
silent, system-wide production outage disguised as a routine convention match.
`safety_critical: false` is correct, but for this reason, not the one the
earlier note gave; the note itself has been corrected in the source JSON. This
was caught by re-deriving the claim from the actual mechanism
(`evaluate_path.py`) rather than trusting a plausible-sounding note, and cross-
checked against the already-passing `test_safety_source_hold_applies_when_safety_rules_are_in_force`
in `test_evaluate_endpoint.py`, which proves the pack-wide HRR-override
mechanism generically. No code change was needed — the draft's value was
already right — only the reasoning attached to it.

## Pack-level design gap (Kimi refuter finding F5, 2026-08-24) — recorded, not fixed here

`BALI_ZERO_POLICY` is the right authority type for this source — typing a business ruling as
`OFFICIAL_PORTAL` to buy the safety hold's coverage would be fabrication, not honesty. But pressed
from the other side: `_apply_safety_critical_source_hold` polices source *provenance class*
(authority type + official-host URL + freshness policy), never rule *effect class* (whether the
rule can EXCLUDE a real applicant). The one authority type that can never pass that check —
`BALI_ZERO_POLICY`, by construction, since it is not in `_PRIMARY_AUTHORITY_TYPES` and typically
has no external URL to pin — is exactly the type this rule uses to carry a LIVE, day-one,
applicant-facing EXCLUDE. That EXCLUDE is therefore permanently exempt from every staleness/
authority check the pack's safety machinery has, and its one source is self-attested (`verified_by`
is the same agent that wrote the cited file). `safety_critical: false` is the correct value for
THIS rule (see the near-miss note above — `true` would be a pack-wide outage, not extra safety),
but that correctness is a workaround, not a solution: **the pack has no compensating control for
policy-backed exclusion rules in general** — no owner-sign-off artifact, no policy-source
freshness semantics, nothing that lets a future `BALI_ZERO_POLICY` rule opt INTO oversight instead
of being structurally unable to. Recorded here as a design gap for whoever next adds a
policy-backed rule to this engine; not a blocker for this one, and not fixed in this PR.

## Adversarial review

**Real run** (not simulated): `kimi -p "<D12 rule + source + test-suite artifacts + refutation
instructions>" -m kimi-code/k3` (kimi version 0.38.0, session
`session_f35a8e40-2b91-45e7-aa0f-4c3f8bfd7f8f`), run against `origin/main` before this rule's own
reachability fix existed. Full transcript is session-local (this session's scratchpad,
`d12_kimi_verdict.txt`), not committed to the repo — see BRIDGING.md's Adversarial review section
for the same disclosure pattern on a sibling card. Verdict, verbatim:

> VERDICT: DO-NOT-SHIP — on `origin/main` every status question sits behind the
> `in_indonesia === "yes"` branch, so every offshore applicant — D12's entire market, including
> the unlapsed-KITAS holder the ruling names — resolves `has_active_stay_permit` to UNKNOWN and
> lands in a NEEDS_INPUT the finished interview can never answer.

**F1 (P0, blocks ship) — the finding that drove PR #4727.** The rule's required fact was
unreachable for D12's entire target population: `flow.ts::computeNextNode` sent every offshore
applicant (`in_indonesia === "no"`) straight to `overstay_days`, never asking
`permit_expiry`/`holds_stay_permit`/`stay_permit_code`/`current_status_code` at all — the exact
questions this rule's derived fact depends on. D12 is a pre-investment *visit* product; its
applicants are offshore by definition. Result: 100% of D12's market resolved
`has_active_stay_permit` to UNKNOWN, hit `on_unknown: NEEDS_INPUT`, and the interview had already
ended — a dead end wearing a safety costume, not fail-closed protection. **Cured in #4727 (merged
2026-08-23T19:20:36Z)**: offshore applicants now gate on `holds_stay_permit` first, expanding into
the full chain only on "yes" — see that PR and this repo's `flow.ts` for the resulting shape.

**F4 (P1) — the finding that drove this PR's own F4 rescoping.** The derivation's docstring and
its own test asserted the owner had "explicitly ruled" that a holder of an expired permit "CAN
apply" — a claim neither supplied ruling text actually made. The concrete applicant this hid: a
renewal-in-process holder (printed KITAS expired, renewal filed and paid, legally present,
possibly on `ITK_PERALIHAN`) — admitted to D12 despite holding a live residence basis. Directly
prompted Zero's clarifying rulings ("chi ha un kitas scaduto e il pagamento del rinnovo..." /
"esatto il rinno si considera depositato se ce stato pagamento", recorded in
`decision_no_two_visas_at_once_and_renewal_stays_on_the_extended_visa_2026_08_23.md`) and this
PR's `immigration.renewal_paid` fact plus the derivation rework above.

Other findings (F2 test/draft decoupling, F3 KITAP-scope attribution, F5 safety-machinery design
gap, F6 `content_sha256` framing, F7 stale precondition language, F8 `freshness_policy`
verification depth) were P1/P2, already dispositioned in this doc's own sections above (see "What
is VERIFIED" and "Pack-level design gap") — not repeated here to avoid duplicating recorded
doctrine.


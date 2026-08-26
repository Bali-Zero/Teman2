# NAGA → P04 canonical-type adapter mapping

Basis: `packages/research-os-core/research_os/schemas/claim.schema.json` and
`evidence.schema.json`, read in full this session (both are `additionalProperties: false` at
every object level — extra fields are rejected, not ignored, so every mapping below either lands
on a real field or explicitly goes to `extensions`). Cross-checked against
`object_successor_edge.schema.json`, `approval_receipt.schema.json`, and
`operational_receipt.schema.json` (all read this session; `required` arrays and enum `$defs`
verified, not paraphrased from the spec doc).

Per `contract-pass-001.md §7`, Cohort B **may** treat these 25 models/schemas as build-ready, and
**may not** rely on D6 (contract registry), D7 (deterministic hashing), D8-second-half
(dual-write/read plan), D10 (atomic multi-object repository), D11 (atomic classification-change
primitive), or D3-as-registry (only a pairwise diff checker exists). Every design choice below
that depends on one of those absent primitives is called out explicitly — this is not a full
adapter spec, it is the mapping plus the list of what the mapping cannot assume.

## 0. The single largest structural gap — mutable rows vs. immutable content-addressed objects

`naga_claims` is a mutable Postgres row: `claim_status`, `expires_at`, `quality_score` are all
updated in place over the row's life (migration 081's own `ADD COLUMN` + backfill `UPDATE`
pattern is the proof — see `01-naga-baseline-inventory.md §1`). P04's `Claim` schema has no
`UPDATE` concept at all: every object carries `object_hash` (required, `^[0-9a-f]{64}$`) and a
`ClaimRef` (the only way to point at a claim) is `{claim_id, object_hash}` — a **specific
revision**, not "whatever the row currently says." Supersession is modeled by writing a **new**
Claim object whose `supersedes_claim_ref` points at the old `ClaimRef`, never by mutating the old
one. This is the packet's own instruction, verbatim: "Canonical versions store immutable
`recorded_at`; effective system-time intervals are derived from append-only successor edges and
never closed by mutating a prior object."

Consequence for design: the canonical NAGA store cannot be "the same `naga_claims` table with new
columns." It must be a **new, additive object stream** that an adapter *reads from* NAGA's
existing mutable rows at defined checkpoints (session completion, quality re-score, expiry sweep,
dedup resolution) and writes as new immutable `Claim`/`Evidence` objects — exactly what the
packet's Implementation sequence step 3 already says ("Add strict canonical adapters and
additive storage") and step 7 ("Dual-write and shadow-read a bounded public, non-PII domain").
This bundle's migration design notes (`03-migration-design-notes.md`) follow that shape.

## 1. `naga_claims` row → canonical `Claim` object

| NAGA field | Canonical `Claim` field | Mapping | Gap / note |
|---|---|---|---|
| `id` (UUID) | `claim_id` | direct copy, first revision | A NAGA claim's `id` never changes across its lifecycle (it's a row PK), so it can serve as `claim_id`, but see G1 below — NAGA has no revision concept, so "first revision" must be defined by the adapter, not discovered in NAGA. |
| — (none) | `claim_family_id` | **new field, no NAGA source** | P04 requires a stable family id spanning all revisions/supersessions of "the same claim." NAGA's `claim_key` (sha256 of first 200 chars of claim_text, lowercased) is the closest analogue but is a **content hash of the text**, not an identity — two claims with materially different-but-similarly-worded text would collide; two revisions of one claim whose wording is corrected across a supersession would **not** share a `claim_key`. Recommend `claim_family_id` be a **new UUID minted at first canonical write**, persisted back into NAGA (e.g. a new nullable column) rather than derived from `claim_key`. This needs a decision, flagged in `07-open-questions-and-corrections.md`. |
| `claim_text` | `statement.object_ref_or_value` (as a string) + `statement.predicate` | **not a direct copy** — P04's `statement` is a structured subject/predicate/object triple (`ExactObjectRef` subject, dotted-lowercase `predicate`, and object as ref-or-scalar), not a natural-language sentence. `claim_text` alone cannot populate `statement` without a real atomization step. | **G-STATEMENT (blocking).** The packet's own deliverable #3 calls automated atomization "an evaluated candidate, not a prerequisite," and the packet explicitly lists as an adversarial case "the same sentence contains two atomic claims." NAGA today extracts one `ClaimRecord` per sentence-ish unit with no subject/predicate/object decomposition at all. Until atomization exists (human/rule-assisted, per the packet's mandated safe incumbent), the adapter cannot honestly populate `statement.subject_ref`/`predicate` — proposal: store the raw `claim_text` in `extensions["naga.raw_text"]` (schema-legal: `extensions` accepts arbitrary payload under a versioned key) and populate `statement` only for the golden-set claims where a human/rule pass produced the triple by hand, leaving the rest **out of canonical storage** until atomization ships. This is the direct implementation of packet §"Automated extraction... Failure of the extractor must never defer the ledger's atomic or temporal semantics" — the atomic/temporal ledger exists now, for the subset that has a real statement; it does not fake statements for the rest. |
| `category` (15-value enum, `core/claims/models.py`) | no direct field | `category` is a claim-*type* taxonomy; P04's closest analogue is the `predicate` namespace. Proposal (not binding): map each of the 15 `CLAIM_CATEGORIES` to a `predicate` prefix, e.g. `FEE_CHANGE` → `naga.fee_change.*`, `ELIGIBILITY_RULE` → `naga.eligibility_rule.*`. This still requires the statement triple to exist (see G-STATEMENT above) — `category` cannot populate `predicate` without a subject/object too. |
| `domain` (`VARCHAR(20)`, e.g. `"visa"`) | `scope.domain` (pattern `^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)*$`) | direct copy after lowercasing (NAGA values observed in code are already lowercase: `"visa"`, `"immigration"`, `"general"`) | none — clean mapping. |
| `jurisdiction` | `scope.jurisdiction` (nullable free string) | direct copy | NAGA's `jurisdiction` is `VARCHAR(50)` with no enum/CHECK — same looseness on both sides, no gap. |
| — (none) | `scope.audience` | **new field, no NAGA source** | NAGA has no audience concept per claim. Leave `null` (schema allows it). |
| `valid_as_of` (single `DATE`) | `time.valid_from` (nullable datetime) | `valid_as_of` → `valid_from` at `00:00:00Z` of that date | **G1 (bitemporal, blocking for the packet's exit threshold).** NAGA has no `valid_to` at all — a claim is either not-yet-expired (checked against `expires_at`, a *different*, storage-lifecycle field) or expired. P04 wants a real **valid-time interval**. `valid_as_of`→`valid_from` is directionally right but the adapter cannot invent a `valid_to` NAGA never captured; it must be left `null` (open interval) unless/until a source explicitly states an end date. Do not conflate `expires_at` (NAGA's *system*-side "stop trusting this" clock, see G1b) with `valid_to` (the *fact's own* validity end) — they answer different questions and the packet is explicit that valid-time and system-time "are distinct and mandatory." |
| `expires_at` (`DATE`) | *not `time.valid_to`* — closer to a system-side abstention/review-trigger signal, has **no direct P04 field** | Recommend: do not map to any `Claim` field directly. Model `expires_at` as an adapter-side scheduling signal that triggers re-review / a new `ObjectSuccessorEdge` with `reason_code = "naga.system_expiry"` when it lapses — i.e. it drives a *process*, not a *field*. | **G1b.** Conflating this with `time.valid_to` was the single easiest wrong shortcut available here — flagging it explicitly so no implementer takes it. |
| — (none) | `time.recorded_at` (required) | **new field** | Set to the wall-clock time the *adapter* wrote the canonical object — never copied from `naga_claims.created_at` (that is when the NAGA row was created, which is a legitimate `recorded_at` for the **first** canonical revision only; any later canonical revision produced by re-review must get its own, later `recorded_at`, per the "immutable `recorded_at`" rule). |
| `verification_level` (`VERIFIED/PROVISIONAL/LOW` derived from score thresholds `0.75`/`0.55`) | `confidence.score` region, **not a stored field** | `confidence.score` = `confidence` (float, direct copy); `confidence.method` = a fixed lowercase-dotted string identifying the scoring function, e.g. `"naga.claim_scorer.v1"` (schema requires `method`, pattern-constrained — cannot leave blank) | `verification_level` itself is **derivable** from `confidence.score` using the same thresholds NAGA already has (`VerificationLevel.VERIFIED=0.75`, `PROVISIONAL=0.55`) — do not store it as a separate canonical field (schema forbids unknown top-level keys); recompute at read time if a UI needs the label. |
| `confidence` (float) | `confidence.score` | direct copy | none. |
| `review_status` (`'auto_extracted'` hardcoded at write, `VARCHAR(20)`) | `review.state` (enum: `unreviewed / machine_checked / human_approved / human_rejected / superseded`) | **G3 (vocabulary mismatch, needs a decision).** `'auto_extracted'` does not appear in P04's enum. Two readings are both defensible and give different downstream behavior: (a) map to `unreviewed` — a machine extracted it but no verification step ran; (b) map to `machine_checked` — `claim_scorer.py` *did* run a scoring pass, which is itself a form of machine check. NAGA's own quality-scoring is exactly what `claim_scorer.py` does, so reading (b) is more accurate to what actually happened — but the packet's exit threshold "zero unsupported critical claims eligible for public use" argues for the **conservative** reading (a), since `machine_checked` in a downstream consumer's mind plausibly means "safe to show," which NAGA's current pipeline does not guarantee (see §2, `_collect_credibility_scores`'s circularity note in the baseline doc). **Recommendation: `unreviewed`, until a human reviewer is demonstrably in the loop for the claim class in question — decision flagged, not made, in `07-open-questions-and-corrections.md`.** |
| `claim_status` (`active/expired/duplicate/conflicting/superseded`, migration 081) | `status` (`ClaimStatus` enum: `supported/contradicted/inconclusive/superseded/expired`) | **G4 (blocking — different axes, not a vocabulary swap).** This is the packet's own baseline question ("where `claim`... carr[ies] inconsistent meanings") answered concretely: NAGA's `claim_status` is a **lifecycle** flag (is this row still the one to look at?), while P04's `status` is an **evidentiary verdict** (what does the evidence say about this proposition?). `active` cannot map to `supported` — a claim can be `active` in NAGA (not yet expired/duplicated/superseded) while its evidence is thin (`verification_level = LOW`), and mapping `active → supported` unconditionally would put unsupported claims into a field a downstream reader will treat as a support verdict, directly violating the packet's exit threshold. `expired` and `superseded` map cleanly (same word, and NAGA's meaning is a strict subset of P04's — a NAGA-expired claim is always at least P04-expired). `duplicate` has no P04 analogue at all — P04 has no "this object is a duplicate of that one" status; the packet's own dedup handling (deliverable "Evidence independence model that distinguishes original, syndicated...") suggests duplicates should not become separate `Claim` objects in the canonical store in the first place (dedup happens *before* canonical write, not as a status *of* a canonical write) — recommend `duplicate_of_id` rows never reach the canonical store at all; only the canonical (deduplicated) claim does. `conflicting` is the hardest: NAGA models it as a **whole-claim** status, but P04 models contradiction as a **per-evidence-item stance** (`EvidenceStance.contradicts`, attached to one `ClaimEvidenceRef`, not to the whole claim) — a claim can have both supporting and contradicting evidence simultaneously in P04's shape, which is strictly more expressive. Recommend deriving P04 `status` from the *aggregate* of a claim's `evidence_refs[].stance` (some contradicts present → `contradicted`; all support, high confidence → `supported`; mixed/thin → `inconclusive`) rather than trusting NAGA's `conflicting` flag directly. **This derivation function is itself new work this bundle does not spec in full — flagged as an open question.** |
| `cross_ref_count` (int) | not a `Claim` field | Recommend: `len(evidence_refs)` on the canonical object supersedes this — do not carry `cross_ref_count` forward as a separate stored number; it becomes derivable. |
| `topic_tags` (`TEXT[]`) | no direct field | Candidate for `extensions["naga.topic_tags"]`. |
| `resolution_hint` (free text) | no direct field | Candidate for `extensions["naga.resolution_hint"]`. |
| — | `classification.risk_class` / `classification.sensitivity` | **new, no NAGA source** | NAGA has no risk/sensitivity classification per claim today. Must be assigned by the adapter, likely from `domain` (e.g. `visa`/`immigration` claims default `sensitivity: internal` unless proven `public`) — needs an explicit policy, not a default guess, before any claim leaves the `internal` sensitivity class. This gates the packet's Non-goal "Do not send sensitive source content to an external model" and the shadow-canary requirement to dual-write only "a bounded public, non-PII domain first." |
| — | `retention.retention_class` / `legal_hold` | **new, no NAGA source** | Needs a policy decision, likely tied to the 5-year conversation-retention floor already established elsewhere in this repo's doctrine (`decision_conversation_retention_five_years_never_delete`), but claims are not conversations — this needs its own ruling, not an inherited one. Flagged, not decided. |
| — | `lineage.{run_id, extractor, input_claim_refs}` | `run_id` ← `naga_sessions.id`; `extractor` ← a fixed string identifying the extraction pipeline version (e.g. `"naga.orchestrator.v1"`); `input_claim_refs` ← `[]` for a first-generation claim, populated for claims produced by re-processing an existing canonical claim (e.g. atomization splitting one wide claim into two narrow ones) | Clean mapping once `extractor` naming convention is fixed by whoever owns P06 build. |

## 2. `naga_sources` + `naga_claim_evidence` → canonical `Evidence` object

| NAGA field(s) | Canonical `Evidence` field | Mapping / gap |
|---|---|---|
| `naga_sources.url` | `document_id` | direct copy (a URL is a legitimate document identifier) — but see G5: no version concept. |
| — (none) | `document_version_id` | **G5 (blocking).** `naga_sources` has no notion that the *same URL* fetched twice (a regulation page edited in place) is two different document versions. `content_hash` (sha256 of the **URL string**, not the page body — read the migration: `hashlib.sha256(url.encode())`, confirmed in `01-naga-baseline-inventory.md` §2 point 2 is about dedup keying, but the **hash input is the URL, not fetched content**) cannot serve as `document_content_hash` either, for the same reason. This is a real, separate defect from the bitemporal one: **NAGA currently has no way to detect that a source page changed between two fetches**, which directly undermines the packet's adversarial case "a later correction predates Nuzantara's discovery" — that case requires knowing a document *version* changed. Recommend: canonical adapter must fetch-and-hash the actual response body (not the URL) to populate `document_content_hash`, and mint a new `document_version_id` whenever that hash changes for a given `document_id`. This is new work, not a mapping. |
| `naga_claim_evidence.source_span_hint` (freeform `TEXT`) | `source_span` (`{locator, start?, end?, page?, section?, quote_hash}` — `locator` and `quote_hash` **required**) | **G2 (blocking for exit threshold "100% source-span coverage for critical claims").** A hint string is not a locator+quote-hash. The canonical adapter cannot synthesize a valid `quote_hash` (sha256 of an exact quoted span) from a hint alone — it needs the actual quoted text. Recommend: for the golden set and any claim promoted to canonical storage, the human/rule-assisted atomization pass (same one needed for G-STATEMENT) must also capture the exact quoted span and its hash; claims lacking this stay out of canonical storage, exactly mirroring the G-STATEMENT resolution. |
| `naga_sources.credibility_score` | no direct field | Closest P04 concept is `source_tier` (a lowercase-dotted string, not a float) — recommend a discrete tiering function bucketing `credibility_score` into tiers (e.g. `naga.tier.high/medium/low`), not a direct copy; P04 deliberately does not carry a raw float credibility score on `Evidence`. |
| `naga_claim_evidence.relation` (`"supports"` hardcoded in `persist.py`, the only value observed being written) | `stance` (`EvidenceStance`: `supports/contradicts/contextualizes/inconclusive`) | Direct enum-name match for the one value NAGA's write path currently produces (`"supports"`). **But note: `persist.py` never writes any other value** — the `relation` column's `VARCHAR(20)` suggests the schema anticipated more, and `naga_claim_transitions.transition_type` may carry contradiction info instead (unverified — flagged in baseline §7). Until that's confirmed, assume NAGA today can only honestly populate `stance="supports"`; do not synthesize `contradicts`/`contextualizes` values NAGA never actually determined. |
| — (none) | `source_event_ref` (required `EventRef` → an `IntelEvent`) | **G6 (blocking, cross-packet).** P04's `Evidence.source_event_ref` is **required** and points at an `IntelEvent` — a P05 (Intel Lake) concept. NAGA sources are not, today, `IntelEvent`s. Per the packet's own text: "Intel Lake source/event identity from Packet 05 when available; use adapters until then." **This bundle cannot resolve G6** — it depends on P05's own (parallel, sibling-lane B1) preparation output, which this lane does not have visibility into beyond the shared P04 contract. Recommend: the adapter mints a placeholder `IntelEvent`-shaped wrapper per NAGA source *only if* P05's real adapter is not yet available, clearly tagged so it can be swapped for a real `IntelEvent` reference without a second migration. Flagged as a cross-lane dependency in `07-open-questions-and-corrections.md`, not solved here. |
| `naga_sources.fetched_at` | `times.observed_at` (required) | direct copy. |
| — | `times.published_at` | **new, no NAGA source** — NAGA does not capture the *document's own* publish date separately from when NAGA fetched it. This is exactly the packet's adversarial case "effective dates distinct from publication dates" — NAGA cannot express the distinction today at the source level. New extraction work needed (parse a publish date off the page/PDF), not an adapter mapping. |
| — | `provenance.{extractor, extractor_version, run_id, extraction_input_hash}` | Same shape as `Claim.lineage` — `run_id` ← `naga_sessions.id`, rest are fixed pipeline-identity strings + a hash of the extraction input. |
| — (none, no distinction in NAGA) | Evidence-independence classification (original vs. syndicated vs. translated vs. derived) | **G4 (deliverable #4, currently unimplemented anywhere in NAGA).** Not a P04 schema field by that name — this is a NAGA-side analytical layer the packet asks for on top of Evidence objects (likely via `extensions` + a dedicated dedup/independence service, not a base schema field). This is genuinely new design, not a mapping — see `04-golden-set-and-adversarial-plan.md` for the "five websites repeat one original story" adversarial case, which is the concrete test of whatever gets built here. |

## 3. Transitions and invalidation — reusing `ObjectSuccessorEdge` and `OperationalReceipt`

`naga_claim_transitions` (append-only by construction, many-to-many, `transition_type` +
`reason` + `detected_by`) is structurally close to P04's `ObjectSuccessorEdge`
(`{object_successor_edge_id, object_kind, family_id, predecessor_ref, successor_ref, reason_code,
recorded_at, producer, lineage, retention, object_hash}` — required fields verified by reading
the schema this session). Recommend the canonical NAGA supersession/contradiction record **reuse
`ObjectSuccessorEdge` directly** rather than inventing a NAGA-specific transition schema — this
follows the packet's own instruction to extend NAGA's foundations, not build a third system, and
it is one of the 25 models Cohort B may build against per `contract-pass-001.md §7`.

**Caveat, explicit per the contract-pass boundary:** `ObjectSuccessorEdge` being *available* is
not the same as an *atomic write* of "claim revision + successor edge + downstream invalidation"
being available — D10 (atomic multi-object repository) and D11 (atomic classification-change
primitive) are both **absent**, and the packet is explicit that D11 in particular "matters to you
specifically" because contradiction/supersession/invalidation are exactly the shapes that want
one. The design must therefore assume these three writes happen as **separate, individually
committed steps**, and be built so that a crash between steps is safe — i.e. idempotent replay
(the packet's own required test: "invalidation idempotency and replay tests") is not a nice-to-
have here, it is the *only* consistency mechanism available given D10/D11's absence. Concretely:
the successor edge must be derivable/re-creatable from the new claim's own
`supersedes_claim_ref` field (belt and suspenders — the edge is a redundant, queryable index over
information the claim object already carries), so a missing or duplicate edge write is a
performance/query problem, never a correctness problem.

For **downstream invalidation events** (packet deliverable #7: "Invalidation events when evidence
is withdrawn, a claim expires, is contradicted, or is superseded") and the dependency index
(deliverable #6: claims → DecisionPackets, ContentObjects, drafts, alerts, pending actions), the
`OperationalReceipt` "queue-only" profile (per `contract-pass-001.md §7`, explicitly listed as
available to Cohort B) is the better fit than `ApprovalReceipt` — see G7 immediately below for
why `ApprovalReceipt` does not work here at all.

## 4. G7 — `ApprovalReceipt.subject.kind` has no member for a claim (verified, not assumed)

Read `approval_receipt.schema.json` in full this session. `ApprovalSubject.kind` is a **closed**
enum (`ApprovalSubjectKind`, `additionalProperties: false` on the containing object, and the kind
field itself is a JSON Schema `enum` — not a pattern-matched open string like
`ExactObjectRef.object_kind` is elsewhere in the same package):

```
"decision_packet", "topic_lock", "creative_lock", "media_script_lock",
"media_shot_lock", "content_revision", "action_intent"
```

There is no `claim` (or anything NAGA-shaped) in this list. The packet's deliverable #8 — "Human
review queue for critical/ambiguous claims" — is exactly the kind of workflow `ApprovalReceipt`
exists to record (`decision: select/approve/reject/request_changes/request_evidence/defer`), and
routing a claim-review decision through it would be the natural design. **It cannot be done
without a contract change**, because the enum is closed and this lane has no authority (and no
mandate) to widen a P04 contract type. This is directly analogous to — and independently confirms
the pattern behind — the sibling H1/P04 lane's own finding (surfaced in this session's fleet
messages, re-derived here from the schema itself, not copied from that message) that
`media_script_lock`/`media_shot_lock`/`content_revision` are `ApprovalSubjectKind` members with no
defining section in the spec: **this enum is under-specified from more than one direction at
once** (some listed members lack a home object; NAGA's whole domain — claims — has no listed
member at all). Recommend: P06 build routes claim review through `OperationalReceipt` (open
`subject_refs`, not a closed kind enum — `required` array confirmed this session includes
`subject_refs` as a list, not a closed-vocabulary singular `subject`) instead of waiting on a
`ApprovalReceipt` contract widening that is out of this packet's authority to request. Flagged as
an open question for the Conductor in `07-open-questions-and-corrections.md`, not resolved here.

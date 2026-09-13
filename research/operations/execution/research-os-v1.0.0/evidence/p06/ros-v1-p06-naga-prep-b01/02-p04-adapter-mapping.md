---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# NAGA → P04 canonical-type adapter mapping

Basis: `packages/research-os-core/research_os/schemas/claim.schema.json` and
`evidence.schema.json`, read in full this session (both are `additionalProperties: false` at
every object level — extra fields are rejected, not ignored, so every mapping below either lands
on a real field or explicitly goes to `extensions`). **CORRECTED 2026-08-26 (adversarial
review): this completeness claim is FALSE for §2 (Evidence). Four fields in
`evidence.schema.json`'s required sets appear nowhere in the mapping — `evidence_family_id`
(required, and exactly the identity-minting gap this bundle correctly flags for
`claim_family_id` on the Claim side), `review_state` (required), `classification.rights`
(required on Evidence's classification, unlike Claim's), and `times.recorded_at` (required
alongside `observed_at`; §2 maps only `fetched_at → observed_at`).** A build lane following §2
as written would emit schema-invalid Evidence objects on day one. Closing these four —
especially the family-identity one — is a precondition for the P06 build, not a detail. Cross-checked against
`object_successor_edge.schema.json`, `approval_receipt.schema.json`, and
`operational_receipt.schema.json` (all read this session; `required` arrays and enum `$defs`
verified, not paraphrased from the spec doc).

**FURTHER CORRECTED 2026-09-11 (R1, `research/operations/2026-09-10-fable-max-sessions/R-research-os.md`
D4/§5a).** The paragraph above undercounted its own finding. Re-measured against the schema's
full recursive required set — `_required_paths()` walked over `evidence.schema.json`'s `$defs`,
exactly as `apps/backend-rag/backend/tests/unit/research_os/test_naga_evidence_mapping_preconditions.py`
does it — §2 as it stood on 2026-08-26 named none of **fifteen** required paths, not four: the
four above (`evidence_family_id`, `review_state`, `classification.rights`, `times.recorded_at`)
were a strict subset of that fifteen; the rest were `contract_version`, `tenant`, `object_hash`,
`evidence_id`, `classification.risk_class`, `classification.sensitivity`, `retention`,
`retention.retention_class`, `retention.legal_hold`, `source_event_ref.event_id`, and
`source_event_ref.object_hash`. **R1 closed this gap on 2026-09-11**: §2 below now names all
32/32 required paths, each with either its NAGA mapping or an explicit exclusion naming a D4
reason, and a new §2b reports D4's three admission counts separately, never collapsed into one
number. This does not delete the history above — the four-field undercount happened, and is left
visible on purpose, per this repo's habit of superseding in place rather than erasing.

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
| — (none) | `claim_family_id` | **new field, no NAGA source** | P04 requires a stable family id spanning all revisions/supersessions of "the same claim." NAGA's `claim_key` (sha256 of first 200 chars of claim_text, lowercased) is the closest analogue but is a **content hash of the text**, not an identity — two claims with materially different-but-similarly-worded text would collide; two revisions of one claim whose wording is corrected across a supersession would **not** share a `claim_key`. Recommend `claim_family_id` be a **new UUID minted at first canonical write**, ~~persisted back into NAGA (e.g. a new nullable column)~~ rather than derived from `claim_key`. **SUPERSEDED 2026-09-11 (R1, D4, `research/operations/2026-09-10-fable-max-sessions/R-research-os.md` §0):** the struck-through clause is FALSE as a design choice — the stable family identity lives in the ADMISSION MANIFEST (`research_os_naga_admission`, D5) and is NEVER written back into legacy NAGA. This needs a decision, flagged in `07-open-questions-and-corrections.md`. |
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
| `naga_claim_evidence.id` (`SERIAL` int) | `evidence_id` (required, `format: uuid`) | **New gap, not named until R1 (2026-09-11).** Unlike `naga_claims.id` (UUID, direct copy to `claim_id` in §1), `naga_claim_evidence.id` is a Postgres `SERIAL` — a type mismatch with the schema's `uuid` format makes a direct copy impossible. Recommend: the adapter mints a **new UUID** at first canonical write (deterministic, e.g. `uuid5` over a fixed namespace plus the legacy serial, so replay is idempotent — mirrors D5's admission-manifest idempotency requirement), and preserves the legacy serial under `extensions["naga.legacy_evidence_serial_id"]` for cross-reference and debugging. "First revision" is defined by the adapter, exactly as for `claim_id` in §1. |
| — (none) | `evidence_family_id` (required, pattern `^[a-z][a-z0-9]*[._-][a-z0-9](?:[a-z0-9_-]\|\.[a-z0-9])*$` — a **dotted-lowercase namespaced string, NOT a UUID**, unlike Claim's `claim_family_id`) | **New gap, not named until R1.** The identity-minting problem is the same one §1's `claim_family_id` row describes — NAGA has no stable cross-revision identity for a piece of evidence — but the target shape differs: a value like `naga.evidence.<slug-or-hash-suffix>` satisfies the pattern; a raw UUID does not. **D4** (`research/operations/2026-09-10-fable-max-sessions/R-research-os.md` §0): minted at first canonical write, persisted in the ADMISSION MANIFEST (`research_os_naga_admission`, D5), never written back into legacy NAGA — same rule as `claim_family_id` above. |
| — (fixed) | `contract_version` (required, `const: "research-os/v1.0.0"`) | Fixed constant — every canonical object carries the same value regardless of source. No NAGA field maps to it and none is needed; nothing to decide. |
| — (fixed) | `tenant` (required, `const: "bali-zero"`) | Fixed constant, same treatment as `contract_version`. No gap. |
| — (computed) | `object_hash` (required, `^[0-9a-f]{64}$`) | Computed by the write path over the canonical payload via `research_os.hashing.object_hash` (RFC 8785 canonicalization + sha256) — never sourced from NAGA, never hand-typed. Recomputed and verified on every read (`Evidence.validate_evidence`'s hash comparison, guarded by `test_a_corrupted_object_hash_is_refused`). Infrastructure, not an adapter-mapping choice. |
| — (none, G6 continued) | `source_event_ref.event_id`, `source_event_ref.object_hash` (both required on the `EventRef` `source_event_ref` already discussed above under G6) | **New gap, not named until R1.** G6 above proposes a placeholder `IntelEvent`-shaped wrapper per NAGA source until P05's real adapter exists; these are that placeholder's own two required sub-fields — `event_id` a minted UUID, `object_hash` computed over the placeholder's payload the same way as any other canonical object. Until the placeholder is actually built (it is NOT built by this bundle — G6 remains unresolved), a legacy NAGA source has no real value for either sub-field, so admission of any legacy record EXCLUDES with reason `intel_event_identity_missing` (D4 order #5) rather than leaving `source_event_ref` half-populated with an invented identity. |
| — (none) | `times.recorded_at` (required alongside `times.observed_at`) | One of the four fields the 2026-08-26 correction named. Mirrors `Claim.time.recorded_at` in §1 exactly: set to the wall-clock instant the *adapter* writes the canonical Evidence object — **never** copied from `naga_claim_evidence.created_at` (that is when the NAGA row was created, a legitimate `recorded_at` only for the evidence's first canonical revision; a later canonical revision, e.g. produced when a review pass supplies a real span, gets its own later `recorded_at`, per the immutable-`recorded_at` rule `CONTRACTS.md:88`/`:266`). |
| — (none) | `classification.risk_class`, `classification.sensitivity` | **New gap, not named until R1.** Same shape as §1's Claim `classification.risk_class`/`classification.sensitivity` row: NAGA has no risk/sensitivity classification per source or per claim-evidence link today. Must be assigned by the adapter from `domain`/`source_type` (e.g. official `.go.id` regulatory text defaults `sensitivity: internal` unless proven `public`) — needs an explicit policy, not a default guess (open question §4 in `07-open-questions-and-corrections.md`, unchanged by this PR). A legacy record for which no policy value can be honestly assigned is EXCLUDED with reason `classification_missing` (D4 order #8) rather than defaulted. |
| — (none) | `classification.rights` (required on `EvidenceClassification`, minLength 1 — **the asymmetry `test_evidence_classification_requires_rights_where_claim_does_not` pins**: `Claim.classification` has no `rights` field at all) | One of the four fields the 2026-08-26 correction named. NAGA captures no usage-rights/licensing metadata for a source at any point in its pipeline — this is not a vocabulary gap like `review_status`, it is a dimension NAGA never asked about. For the curated seed cohort (§5c) rights is set explicitly from the document's own public status (e.g. `"public_domain_government_publication"` for an Indonesian government regulation page); for a legacy record with no rights determination on file, admission EXCLUDES with reason `rights_missing` (D4 order #6) — never a silent default. |
| — (none) | `review_state` (required, top-level — **not nested under a `review` object the way Claim's `review.state` is**; same five-value `ReviewState` enum) | One of the four fields the 2026-08-26 correction named. NAGA has no evidence-level review workflow at all (§1's `review_status` gap is a claim-level field, on a different table). For evidence produced by a human/rule-assisted canonical write (the golden-set/seed path, §5c) the adapter may honestly set `unreviewed` — it truly has not been reviewed, mirroring the conservative reading recommended for Claim's `review_status` in §1. For a legacy record admitted with no review signal at all, defaulting is not allowed (D4's ordering rule: "nothing is ever defaulted silently") — admission EXCLUDES with reason `review_state_missing` (D4 order #9). |
| — (none) | `retention` (required top-level object), `retention.retention_class`, `retention.legal_hold` | **New gap, not named until R1.** Same shape as §1's Claim `retention.retention_class`/`legal_hold` row and the same open question (§5 in `07-open-questions-and-corrections.md`, still not inherited from the unrelated 5-year conversation-retention doctrine — claims and evidence are a different object class with different legal grounding). A legacy record with no retention policy assigned is EXCLUDED with reason `retention_missing` (D4 order #7). |

## 2b. Three counts, reported separately (D4)

Per D4 (`research/operations/2026-09-10-fable-max-sessions/R-research-os.md` §0, and R1-build-spec
§3), admission over a legacy NAGA cohort reports **three different counts**, never collapsed into
one, and a test asserts they are pairwise different so collapsing any two is a red:

1. **`documented_mapping_coverage`** — how many of the 32 required canonical Evidence paths §2
   above *documents* (with either a real mapping or a named exclusion reason). After this PR:
   **32/32.** This is a property of this DOCUMENT, not of any legacy record.
2. **`available_source_information`** — of those 32 documented paths, how many a given legacy
   NAGA record actually carries *any* source information toward, even indirectly. §2's own rows
   show this splits into three groups that behave very differently:
   - **adapter-computed, always present, never "source information" at all** — `contract_version`,
     `tenant`, `object_hash` (3 paths, fixed constants or computed hashes, no NAGA dependency);
   - **genuinely NAGA-sourced today** — `document_id`, `times.observed_at`, `stance`,
     `source_tier` (via `credibility_score`), `source_span` in part (a hint string exists, but see
     G2 — it is not yet a real `locator`+`quote_hash`) (roughly 4-5 paths, and G2/G5 already flag
     that even these are imperfect);
   - **NAGA never asked the question** — `source_event_ref.*` (no `IntelEvent` concept, G6),
     `classification.rights`, `classification.risk_class`/`sensitivity` (no policy exists),
     `review_state` (no evidence-level review workflow), `retention.*` (no policy exists),
     `evidence_family_id`/`evidence_id` (identity-minting gaps) — this group is why the D4
     admission predicate (build-spec §3, rules 5-9) fires on effectively every legacy NAGA record
     today, regardless of how well any individual field maps.
   The exact count for a given cohort is a property of that cohort's rows, not of this document —
   this section states the RULE, not a fixed number.
3. **`admissible_records`** — of the legacy cohort, how many records pass every ordered D4
   predicate (build-spec §3, rules 1-10) and are actually written as canonical objects.

**These three numbers differ on the mixed set, and that is the point.** `documented_mapping_coverage`
is a ceiling that does not move once this document is complete (32/32, permanently, until the
schema itself changes). `available_source_information` is typically far smaller than 32 for any
real legacy NAGA record, because the "NAGA never asked the question" group above has no answer at
all, independent of data quality. `admissible_records` is smaller still, because a record can carry
partial source information for a required path (e.g. a `source_span_hint` string) without that
information being STRUCTURALLY sufficient to satisfy the predicate (e.g. rule 4,
`exact_span_missing`, fires on a hint string precisely because it lacks `locator`/`quote_hash`).

**A dry-run over legacy-shaped records that admits zero is a valid, honestly reported outcome, not
a failure.** Given the "NAGA never asked the question" group above, a dry-run over `naga_sources`
+ `naga_claim_evidence` rows as they exist today — URL-hashed `content_hash`, hint-string spans, no
`IntelEvent` identity, no rights/review/retention policy — is expected to admit **0** records, with
every exclusion reason named per record. This is the honest baseline the seed cohort (§5c) is built
to clear instead.

## 3. Transitions and invalidation — reusing `ObjectSuccessorEdge` and `OperationalReceipt`

`naga_claim_transitions` (append-only by construction, many-to-many, `transition_type` +
`reason` + `detected_by`) is structurally close to P04's `ObjectSuccessorEdge`
(`{object_successor_edge_id, object_kind, family_id, predecessor_ref, successor_ref, reason_code,
recorded_at, producer, lineage, retention, object_hash}` — required fields verified by reading
the schema this session). Recommend the canonical NAGA supersession/contradiction record **reuse
`ObjectSuccessorEdge` directly** rather than inventing a NAGA-specific transition schema — this
follows the packet's own instruction to extend NAGA's foundations, not build a third system, and
it is one of the 25 models Cohort B may build against per `contract-pass-001.md §7`.

~~**Caveat, explicit per the contract-pass boundary:** `ObjectSuccessorEdge` being *available* is
not the same as an *atomic write* of "claim revision + successor edge + downstream invalidation"
being available — D10 (atomic multi-object repository) and D11 (atomic classification-change
primitive) are both **absent**, and the packet is explicit that D11 in particular "matters to you
specifically" because contradiction/supersession/invalidation are exactly the shapes that want
one. The design must therefore assume these three writes happen as **separate, individually
committed steps**, and be built so that a crash between steps is safe~~ — **SUPERSEDED 2026-09-11
(R1, D3/D5, `research/operations/2026-09-10-fable-max-sessions/R-research-os.md` §0):** the
struck-through "cannot be atomic" premise is FALSE. A successor claim and its `ObjectSuccessorEdge`
commit **atomically, in one transaction** (`CONTRACTS.md:142`, `:267`: "a successor object and its
edge commit atomically... the predecessor is never updated"). D10/D11 remain absent and are not
needed for this: what they would have added is a *third*, coupled write — mutating the predecessor
in place — and that write does not happen at all (RULING B1, §07 above); it never needed atomicity
with the other two because it was never a write. The two writes that DO happen (successor + edge)
are one transaction, not two "separate, individually committed steps" as this paragraph originally
claimed — i.e. a crash between steps is safe not because idempotent replay papers over a partial
write, but because there is no window in which one exists without the other. **The idempotent-replay
reasoning below stays — it is still true and still required, independent of which premise motivated
it:** replay must still resolve to the same bundle rather than create a second branch, and the edge
must still be derivable/re-creatable from the claim's own `supersedes_claim_ref` field as a
redundant, queryable index. Only the "cannot be atomic" premise is superseded; the belt-and-suspenders
edge-reconstruction discipline is not.

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


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `bb6d9ceb9`):
the generator was dead before the refuter was dispatched.

**Verdict: DEFECTIVE.** The bundle is unusually honest about what it did not do, and its two
load-bearing corrections (migration numbering, the G7 `ApprovalSubjectKind` gap) check out
independently. But its fixture set was internally inconsistent in exactly the D11 area the review
was aimed at, and its central baseline claim rested on one search pattern. Every finding was
re-verified against disk by the gating session before acceptance — the refuter is not trusted
either (superscar #6). That re-verification made finding 1 **worse** than reported.

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | "`persist.py` is the only writer" came from an `INSERT INTO naga_` grep, blind to UPDATE by construction | TRUE, **and worse** | **FIXED** — four UPDATE writers named (`dedup.py:144`, `claim_scorer.py:202`, `expiry.py:58`, `:174`). The gating session also found the cited INSERT grep is *itself* wrong: `dedup.py:155` and `expiry.py:154` insert into `naga_claim_transitions`, one of the same 5 tables, and `persist.py` never writes it. Five writers across three files, not one |
| 2 | "`quality_score` written once" contradicted by two post-insertion UPDATEs | TRUE | **FIXED** — written *first*, not once |
| 3 | §2 point 5's open mystery ("what moves a claim out of `active`") is answered in a file it listed but never searched | TRUE | **FIXED** — `expiry.py:58` / `dedup.py:144`. The `review_status` half STANDS: nothing moves a claim out of `auto_extracted`, so the human-review gate has no exit path in code |
| 4 | Supersession requires two coupled writes on an immutable content-hashed object; D10/D11 forbidden by §7 | TRUE (`object_hash` required, `claim.schema.json:618`) | **NOT FIXED — RAISED AS BLOCKING** (`07` §B1). Patching it means choosing an answer this bundle has no authority to choose |
| 5 | `bitemporal/01` and `supersession/01` encode contradictory predecessor conventions; `bitemporal/01` trips the test matrix's own "FALSE if" | TRUE | **NOT FIXED — RAISED AS BLOCKING** (`07` §B2). Picking a convention IS answering §B1; both left visible |
| 6 | `bitemporal/03` uses `supersedes_claim_ref` for calendared succession, not correction | TRUE | **RAISED** (`07` §B3) |
| 7 | `invalidation/01` withdraws evidence `...e7` and asserts it affects claim `...0030` — a citation that exists nowhere in the fixture set | TRUE | **FIXED** — trigger now withdraws `...e2`, which `0030` genuinely cites. A PASS on the original data would have proven nothing |
| 8 | "one or more per adversarial category" false — case 6 (sanitization boundary) had no fixture | TRUE (14 files, 8 dirs, no sanitization) | **FIXED** — fixture added; 15 files. This was the one category where a missing negative control costs most |
| 9 | Evidence adapter mapping is four required fields short: `evidence_family_id`, `review_state`, `classification.rights`, `times.recorded_at` | TRUE (0 grep hits each; all four in the schema's required sets) | **FIXED** — §2's completeness claim corrected; closing them is a build precondition |
| 10 | "Fixtures validate directly against the schemas" — they would fail today (extraneous `note`, most required fields absent, `additionalProperties: false` throughout) | TRUE | **FIXED** — restated as behaviour specs; the old hedge covered "we did not run it", not "it would fail" |
| 11 | "100% invented, not real-data-renamed" overstated — real PMA capital figures embedded | TRUE | **RAISED** (`07` §B4) — transparent, no PII, but a synthetic-stamped file now carries an unverified real figure |
| 12 | G5 attributes a URL hash to "the migration" (it is `persist.py:102`), and omits the `[:16]` / `[:32]` truncations | TRUE, low severity | **ACCEPTED AS LIMIT** — substance (hash of URL, not content) is correct |

**Not a finding** (refuter checked, found sound): migration numbering — `273` is WhatsApp-broker,
head is 287, 282 absent, symbolic name correct; the G7 `ApprovalSubjectKind` closed-enum gap;
`ObjectSuccessorEdge` and `OperationalReceipt` required-field claims; the abstention fixture's
`reasoning.py` attribution (re-exported from `reasoning_utils.py`); and implementation-readiness,
which is disclaimed consistently throughout.

**Bottom line:** usable as an inventory and a gap list. **Not** to be handed to a build lane until
§B1 and §B2 in `07-open-questions-and-corrections.md` are ruled on.

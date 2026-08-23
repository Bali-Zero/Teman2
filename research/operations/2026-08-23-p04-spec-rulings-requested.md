---
title: P04 frozen-contract spec — open questions requesting a Conductor ruling
spec: research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md (read at origin/main, commit 22a5e796a03cb7a3e796d4577064f27ab44f6dc9, 1039 lines)
generated: 2026-08-23
scope: P04 D1 (canonical contract core — 25 kinds). D2=migration 270, D3=adapters/dual-write, D4=contract PASS / compatibility-matrix sign-off (per Work Packet 04 exit criteria)
method: every claim below was verified against the spec snapshot with line numbers, and cross-checked against the actual implementation (origin/main + the four open, unmerged P04-D1 PRs: #4610 evidence-spine, #4621 operator-decisions, #4643 content, #4653 outcome-event) and against `.claude/skills/modus/PENDING-ARMS.md`. Nothing here is asserted from memory of a prior turn.
date: 2026-08-23
domain: operations
adversarial_review: exempt-session-capture
---

# P04 frozen-contract spec — items requesting a Conductor ruling

**9 candidates reviewed. 8 survive verification, 1 dropped as factually wrong.** Two of the eight
(§5, §9 below) turn out to already be logged in `PENDING-ARMS.md` with a fuller, corrected repro
than the candidate note had — I quote the ledger version, not the candidate's, where they diverge.
Three more (§2, §4, §7) are not yet in the ledger but are already flagged as open questions inside
the implementer's own module docstring on an unmerged PR — I cite those too, because they show the
exact fork in the road the Conductor is being asked to pick a branch of.

---

## 1. `approval_subject_kind` admits three object kinds the spec never defines — REAL, not yet ledgered

**Spec text**, §3 closed-enum table, line 64:

> `approval_subject_kind` | `decision_packet`, `topic_lock`, `creative_lock`, `media_script_lock`, `media_shot_lock`, `content_revision`, `action_intent`

**§8's own preamble**, line 314:

> They are immutable proposals or selections; every approval remains a separate `ApprovalReceipt` bound to the exact object hash.

Verified independently (not just re-asserting the candidate note): `media_script_lock`,
`media_shot_lock`, and `content_revision` each appear in the spec **exactly three times** — the
enum row above (line 64), the `subject.kind` inline union on `ApprovalReceipt` (line 642), and the
allowed-pairs sentence in §13.5 (line 720). Grepped the full 1039-line file for each string; no
other hits. Cross-checked against the section-header list (all 25 numbered `##`/`###` object
sections) — there is no `MediaScriptLock`, `MediaShotLock`, or `ContentRevision` section, and no
prose anywhere describing what such an object would contain. `decision_packet` (§7), `topic_lock`
(§8.1), `creative_lock` (§8.2), and `action_intent` (§13.2) — the other four members of the same
enum — all have a defining section. These three don't.

**Why reading alone can't resolve it**: §8's invariant requires binding "the exact object hash of
its subject" for *every* approval, with no carve-out for these three kinds. There is no other spec
passage (§9 ContentObject, §10 MediaManifest, the WR3 work packet) that names these as aliases of
an already-defined object. The gap is structural, not something a wider reading window closes — I
re-read §9, §10, and §13 in full looking for a "this is really a `ContentObject` revision" mapping
and found none.

**Already implemented one way in code**: `approval_receipt.py` (origin/main, merged), lines 45–51,
transcribes the closed decision-table verbatim and accepts all three kinds as valid
`ApprovalSubjectKind` enum members with no comment flagging the gap — the implementer took the enum
at face value and moved on. So today, `ApprovalReceipt.subject.kind = media_script_lock` validates
structurally (UUID + object_id + a syntactically-valid sha256), with nothing to check that hash
*means* anything, because no object schema exists to compute it against.

**Candidate answers and what breaks under each**:
- **(a) These are placeholders for kinds a later work packet defines** (most likely: `media_script_lock`/`media_shot_lock` read as WR3 script/shot approval gates — Work Packet 11 territory; `content_revision` reads as a narrower approval than the whole-`ContentObject` revision approval §9 already implies exists via `supersedes_content_object_ref`). Under this reading, P04 D1 should leave the enum as-is and Packets 02/10/11 are on notice that they must define these object shapes before ever issuing such an approval — anything issuing one before that section exists is out of spec.
- **(b) The enum is wrong and should be trimmed to kinds §3–§20 actually define**, deferring the addition of `media_script_lock`/`media_shot_lock`/`content_revision` to a versioned freeze-change when their owning packet is ready. Under this reading, any code (like the current `approval_receipt.py`) that already accepts them today is validating against a stale closed set and needs a follow-up PR the moment the enum shrinks.
- Either way, **someone has to decide before Packet 11 (WR3 Video Foundry) or Packet 10 (WR2 Creative Foundry) tries to issue a script-lock/shot-lock approval**, because right now that approval would validate with no way to verify its subject actually exists.

**Blast radius**: does not block D1/D2/D3/D4 of the canonical core itself (ApprovalReceipt already
validates and is merged). Blocks **future kinds** — specifically Packet 11 (media script/shot
locks) and Packet 02/10 (content-revision-level approval) the moment either needs to issue one. It
*should* also surface in D4's compatibility-matrix sign-off ("independent reviewer signs the
semantic compatibility matrix") since an incomplete kind vocabulary is exactly what that review is
for.

---

## 2. `payload_ref`'s union shape has no discriminator in the spec — REAL, already resolved-with-caveat in code

**Spec text**, §4 `IntelEvent`, line 191:

> `payload_ref: durable reference or validated inline public payload`

That is the entire specification of the field — prose, not a tagged union, not even a hint of a
type-tag field name. Nothing elsewhere in the spec (not §2's canonical-representation rules, not
any other `*_ref` field) establishes a discriminator convention for a field that can be *either* a
reference *or* an inline value.

**Why reading alone can't resolve it**: a validator (or a second-language producer) reading only
the spec cannot construct a JSON Schema for this field, because "durable reference" and "validated
inline public payload" are never given field-level shapes, and there is no declared tag to tell the
two apart on the wire.

**Already implemented one way in code**: `intel_event.py` on the open, unmerged PR #4610
(`agent/nuzantara/backend-rag/ros-v1-p04-d1-evidence-spine`), lines 20–23:

> `payload_ref`'s two shapes ("durable reference" vs "validated inline public payload") are not given field-level detail in section 4; the concrete `DurablePayloadReference`/`InlinePublicPayload` layout below is this packet's canonical choice, discriminated on `ref_type`.

The implementer invented a `ref_type` discriminator field, a `DurablePayloadReference` shape
constrained to `https://`/`s3://` URIs (added in a later adversarial-review pass, per lines 27–44
of the same file — an earlier draft accepted `data:`/`blob:` URIs, which are the payload wearing a
reference's label), and an `InlinePublicPayload` shape whose `content_hash` is verified against the
actual embedded bytes. This is a real, defensible design — but it is an **implementer-invented
wire shape for a field the frozen spec leaves untyped**, exactly the class of decision §21's own
closing rule says should "raise a versioned freeze-change proposal" rather than ship silently.

**Candidate answers and what breaks under each**:
- **(a) Ratify the PR's `ref_type` discriminator (or a Conductor-specified equivalent) as the
  canonical wire shape**, folding it into CONTRACTS.md via a minor (additive-detail) or major
  (if the discriminator name changes) version bump. Every future producer of an `IntelEvent` now
  has one shape to target.
- **(b) Leave the field spec-untyped and let each producer choose its own shape**, accepting that
  cross-implementation compatibility for `payload_ref` is not guaranteed by the contract — which
  contradicts §2's stated purpose (canonical objects must hash identically across implementations)
  the moment two producers pick different shapes for the same logical reference.
- (a) is clearly the sane default; the ruling that's actually needed is narrower: **does the
  `ref_type` name and the `https/s3`-only constraint on `DurablePayloadReference.uri` become the
  frozen wire shape, or does the Conductor want a different discriminator/scheme allowlist?**
  Shipping D1 with this un-ratified is shipping an unratified schema extension inside a document
  whose header says "frozen semantic contract."

**Blast radius**: blocks **D1 exit / D4 contract PASS** for the `IntelEvent` kind specifically —
this is live, in-flight code on an open D1 PR right now, not a future-kind hypothetical.

---

## 3. `arguments_ref` is typed as a bare, unconstrained string — REAL, already live on `main`

**Spec text**, §8.3 `RequestedActionSpec`, line 381, and §13.2 `ActionIntent`, line 620 (identical
wording in both):

> `arguments_ref: protected or public durable reference`

Prose, same pattern as item 2 — no field-level shape, no discriminator for "protected" vs "public."

**Why reading alone can't resolve it**: same reasoning as item 2, but with a materially different
urgency, because —

**Already implemented one way in code, and already merged**: `action_intent.py` on `origin/main`
(merged, not a draft), line 69:

```
arguments_ref: str = Field(min_length=1)
```

No structure, no protected/public discriminator, no scheme constraint — a bare non-empty string.
The exact same typing appears on PR #4621's `requested_action_spec.py` line 75. Unlike item 2, this
field is not being decided right now — it is already shipped, on the object every downstream
consumer (Packet 12, the kita Action Inbox) will read to find "where are this action's arguments."
A bare string means every producer and every consumer must independently agree on a convention
(is it a URI? a DB row locator? a JSON pointer into another store?) with the contract enforcing
nothing beyond "non-empty."

**Why this is a sufficiency question, not just a shape question** (per the candidate's own framing
— "is it sufficient for an exact reference?"): §2 states `input_revision_hash` "binds a decision to
the exact revision it reviewed. References to mutable files or URLs are insufficient without a
content or revision hash." `arguments_ref` sits right next to `arguments_hash: sha256` in both
objects (lines 382–383, 621–622) — so the *hash* half of the exact-reference pair is covered. But
`arguments_ref` itself, as a bare string with no required scheme, can legally be a plain mutable
URL, which is exactly the shape §2 calls insufficient for anything that isn't paired with a hash —
here it is paired with one, so this may already be fine by construction. The open question is
whether "bare string + separate hash" is the Conductor's intended sufficiency bar for *every*
future consumer, or whether `arguments_ref` itself needs a minimum shape (e.g. a scheme allowlist,
mirroring what item 2's `DurablePayloadReference.uri` fix just did for `payload_ref`) so a producer
can't hand back e.g. `"see attached"`.

**Candidate answers and what breaks under each**:
- **(a) Bare string is fine as shipped** — `arguments_hash` already carries the exactness
  guarantee, and `arguments_ref` is deliberately opaque so any storage backend can be named without
  a contract-level scheme registry. Nothing changes; Packet 12 must independently document a
  convention (or accept ref+hash as sufficient without dereferencing ref at all in some flows).
- **(b) `arguments_ref` needs the same discriminated/constrained shape item 2 just gave
  `payload_ref`** ("protected" vs "public" as an explicit tag, plus a scheme allowlist). This is a
  **breaking wire change** to two already-defined kinds (`RequestedActionSpec`, `ActionIntent`) —
  under §1 rule 10 it would need at minimum a minor version if additive-with-default, or a major
  version if the field becomes a structured object replacing a string.
- Because (b) is a breaking change to fields already shipped and already hashed into existing
  fixtures, **the longer this stays unruled, the more expensive the fix** — every day more code and
  more fixtures get written against the untyped-string shape.

**Blast radius**: **D3 (adapters/dual-write)** — every legacy-to-canonical adapter mapping an
existing action's argument location into this field has to pick a convention now, with nothing in
the contract to check it against. Also affects **D4** for the two already-merged kinds
(`ActionIntent`, and `RequestedActionSpec` once #4621 lands), and the future Packet 12 runtime that
has to dereference this field to actually execute anything.

---

## 4. §16 `OutcomeEvent.subject_refs` has no `revocation_receipt_ref`, though §3.2 requires an `OutcomeEvent` for revocation propagation — REAL, already flagged in an open PR's docstring

**Spec text**, §3.2 `RevocationReceipt` invariants, line 173:

> Every downstream effect—withdrawal, cache purge, reindex, notification, reroute, or other propagation—requires its own `ActionItem`/`ActionIntent`, unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, typed terminal `OperationalReceipt`, **and `OutcomeEvent`**. Missing confirmation remains a blocking gap; revocation never silently implies that propagation succeeded.

**Spec text**, §16 `OutcomeEvent`, lines 829–839 (`subject_refs` block, verbatim field list):

> `decision_packet_ref?`, `content_object_ref?`, `artifact_revision_ref?`, `verification_receipt_ref?`, `action_intent_ref?`, `execution_attempt_ref?`, `operational_receipt_ref?`, `claim_refs`, `campaign_ref?`, `workflow_run_ref?`

No `revocation_receipt_ref` field among them. §13.5's registry (line 716) does name a receipt type
for exactly this case — `revocation.propagation` — so an `OutcomeEvent` reporting that outcome
*can* bind `operational_receipt_ref` to the `OperationalReceipt`, and that receipt's own generic
`subject_refs: [{object_kind, object_id, object_hash}]` (line 696) *could* carry the
`RevocationReceipt` reference one hop away. But `OutcomeEvent` itself has no direct field for it.

**Why reading alone can't resolve it**: it is genuinely ambiguous whether the two-hop path
(`OutcomeEvent.operational_receipt_ref` → `OperationalReceipt.subject_refs`) is the *intended*
binding, or whether §16's field list is simply incomplete relative to §3.2's own stated
requirement. I widened the read to check whether `subject_refs` was meant as an exhaustive mirror
of all 25 canonical kinds — it is not: `artifact_revision_ref` and `campaign_ref` also reference
object shapes (`{artifact_revision_id, artifact_sha256}` and `{campaign_id, revision?,
object_hash}`) that, like item 1's three subject kinds, have **no defining section anywhere in
this spec** ("ArtifactRevision" and "Campaign" are not among the 25 numbered objects). That's not
this candidate's question, but it means §16's field list is not a reliable "what subjects exist"
inventory to reason from — it already contains two other undefined-kind references, which weakens
any argument that `revocation_receipt_ref`'s absence is *necessarily* deliberate curation rather
than an omission from the same pattern as items 1 and 4.

**Already implemented one way in code**: `outcome_event.py` on open PR #4653
(`agent/nuzantara/backend-rag/ros-v1-p04-d1-outcome-event`), lines 3–23, states this almost
verbatim as a **known, explicitly unresolved gap**:

> KNOWN GAP against section 3.2 (RevocationReceipt, already on main) — reported, not silently resolved: [...] This model encodes section 16's `subject_refs` exactly as written (no invented `revocation_receipt_ref` field) rather than quietly patching the gap; Packet 04 needs to rule whether this is an intentional indirection (the `OperationalReceipt`'s own `subject_refs` already binds the revocation, per section 13.5) or a missing field on this object.

The implementer deliberately did **not** invent a field to paper over this — they left it open and
wrote the ruling request directly into the module docstring.

**Candidate answers and what breaks under each**:
- **(a) The two-hop indirection is intentional** — `OutcomeEvent` never needs a direct
  `revocation_receipt_ref` because `operational_receipt_ref` + `OperationalReceipt.subject_refs`
  already closes the loop. Nothing changes in the schema; any query that needs "which
  `OutcomeEvent`s report on this `RevocationReceipt`" must join through `OperationalReceipt`.
- **(b) `revocation_receipt_ref?` is a missing field** and should be added to §16's `subject_refs`
  block as a minor (additive-optional) version change, giving direct queryability without the
  join and matching the treatment every *other* first-class subject kind gets.
- Under (a), any consumer or dashboard built assuming a direct reference will be wrong and need a
  join it didn't know it needed. Under (b), every already-written `OutcomeEvent` fixture and any
  code built against the current field list needs a (backward-compatible, since additive-optional)
  update once the field lands.

**Blast radius**: blocks **D1 exit / D4 contract PASS** for `OutcomeEvent` (open PR #4653, live
right now) and, more concretely, blocks **any actual revocation-propagation flow** from having a
spec-clean way to report its outcome — §3.2 already requires this reporting to exist for every
revocation's downstream effects.

---

## 5. §13.5's "closure" has no registered `OperationalReceipt` type, unlike its six siblings — REAL, already ledgered, already caused a live bug

**Spec text**, §13.5 shared invariants, line 725:

> A queue-only triage, assignment, snooze, rejection, split, merge-duplicate, evidence-request, **or closure** atomically appends the next `ActionItem` revision, its `ObjectSuccessorEdge`, and the registered typed `OperationalReceipt`.

**Spec text**, same section, line 716 (the v1 registry):

> The v1 registry includes at least `execution.result`, `team.acknowledgment`, `team.partial`, `team.completion`, `team.blocked`, `team.cancelled`, `team.superseded`, `routing.assignment`, `queue.triage`, `queue.rejected`, `queue.snoozed`, `queue.split`, `queue.merge_duplicate`, `queue.evidence_requested`, and `revocation.propagation`.

Cross-checked every operation named in line 725's list against line 716's registry: triage →
`queue.triage`, assignment → `routing.assignment`, snooze → `queue.snoozed`, rejection →
`queue.rejected`, split → `queue.split`, merge-duplicate → `queue.merge_duplicate`,
evidence-request → `queue.evidence_requested`. **All six of the other operations have a matching
registered type. "Closure" does not** — there is no `queue.closed`, `queue.closure`, or
`queue.completion`-for-ActionItem entry anywhere in the registry (note `team.completion` exists but
is a different vocabulary — the `team.*` family, not the `queue.*` family this ActionItem-closure
sentence groups with).

**Why reading alone can't resolve it**: the registry is explicitly open ("includes at least" —
domain packets may register more via Packet 04 compatibility review, per line 716's closing
sentence), so this isn't a closed-enum violation the way item 1 is. But §13.5's own sentence
(line 725) requires closure to produce "the registered typed `OperationalReceipt`" in the same
breath as the six operations that *do* have one — and closing an `ActionItem` (every finished item
eventually closes; `ActionItem.close_reason?` at line 600 already anticipates it) is not a rare
edge case that can comfortably wait for a future compatibility-review PR. Nothing in the frozen
text tells an implementer what string to use today.

**Already implemented one way in code, and this is the most consequential finding in this
document**: `.claude/skills/modus/PENDING-ARMS.md`, row opened 2026-08-23 (Pro, P04-D1 metrics
ship), and `operational_receipt.py` (`origin/main`, merged) lines 84–100, document a **live bug**
this exact gap caused:

> `queue.closed` (unregistered; no v1 receipt_type exists for ActionItem closure — see the module docstring's second invariant and the open freeze-change question this leaves for the Conductor) sailed an `execution_attempt_ref` straight through, because it was not one of the 7 named entries.

The original guard was a **blocklist** of the seven registered queue-only types, forbidding them
from carrying an `execution_attempt_ref`. Because `queue.closed` isn't a registered type at all, it
wasn't on the blocklist, so a receipt claiming `receipt_type=queue.closed` could smuggle an
`execution_attempt_ref` straight through the guard — exactly the "no `ExecutionAttempt` carried"
invariant §13.5 states for closure. Caught by an independent cross-family refuter (Kimi K3) plus
reproduction, and fixed defensively by inverting the guard to an **allow-list** (only
`execution.result` may carry an `execution_attempt_ref`; everything else, named or not, is
rejected). The defensive fix closes the security-relevant hole, but the underlying spec gap — no
registered vocabulary word for the single most common ActionItem operation — is unresolved and is
explicitly logged as "the open freeze-change question this leaves for the Conductor."

**Candidate answers and what breaks under each**:
- **(a) Register `queue.closed`** (or a Conductor-chosen equivalent name) in a minor version bump
  to the v1 registry, closing the gap the same way the other six operations are closed. Cheapest,
  most consistent fix; matches the pattern every sibling operation already has.
- **(b) Leave it to be registered later via the Packet 04 compatibility-review path** the registry
  already provides for domain-specific extensions — treating "closure" as not urgent enough to
  freeze now. Given the bug this already caused and given closure is universal (not domain-
  specific), this reading is hard to square with treating the other six operations as needing
  day-one registration.
- Either way, the allow-list fix already shipped is safe under **both** answers — it doesn't
  need to be revisited regardless of which way this is ruled. What's still open is only the
  registry entry itself, and any code that constructs a real closure receipt today has to invent a
  string with nothing in the contract to validate it against.

**Blast radius**: blocks **D1 exit / D4 contract PASS** for `OperationalReceipt` (`ActionItem`
closure is a day-one operation, not a future kind) and directly affects **D3** — any adapter that
needs to record a legacy system's "this item is done" event into the canonical chain has no
registered vocabulary word to write. This is my nomination for **most urgent** item in this
document — see the closing section below.

---

## 6. ~~`verify_action_intent_matches_action_item` mutual fixed point~~ — DROPPED, the candidate is wrong

**Candidate's claim**: "do §13.1 and §13.2 each require a reference to the other in a way that
cannot be satisfied at creation time?"

**This does not survive.** §13.1 `ActionItem.current_intent_ref` (line 599) is written with a `?` —
**optional**:

> `current_intent_ref?: {action_intent_id, object_hash}`

§13.2 `ActionIntent.action_item_ref` (line 616) is **not** optional — every `ActionIntent` must
name its exact `ActionItem` hash. That asymmetry is exactly what breaks the apparent cycle: an
`ActionItem` revision can be created first, with `current_intent_ref` absent (legally, since it's
optional), giving it a fixed `object_hash`; the `ActionIntent` is then created referencing that
already-fixed hash. No circular hash dependency exists at creation.

§13.5's own shared invariants (line 723) spell out the second half explicitly:

> Assignment, decision readiness, **intent linkage**, closure, or SLA change appends a new revision in the same `action_item_family_id` [...]

"Intent linkage" is named as one of the reasons an `ActionItem` gets a **new revision** — i.e., the
spec itself anticipates a two-step sequence (item rev-1 without the link, then item rev-2 that adds
`current_intent_ref` pointing at the now-existing intent), not a single atomic pair where both
objects must simultaneously embed each other's hash. §8.3's "atomically materializes one
`ActionItem` and one `ActionIntent`" (line 404) describes the *initial pair* (item rev-1 + intent),
not a requirement that rev-1 already carry the link.

**Confirmed against the actual implementation** (`action_intent.py`, `origin/main`, merged,
lines 96–135, function `verify_action_intent_matches_action_item`): the check treats
`item.current_intent_ref is not None` as a **conditional** branch (lines 129–134) — "when present
it must name and pin this exact intent" — exactly matching the optional-then-linked-by-successor-
revision reading above, with no comment anywhere suggesting the implementer saw a fixed-point
problem. `action_item.py`'s own docstring (lines 1–12) independently states the same
"intent linkage... appends a new revision" resolution without prompting.

**Verdict**: not stale, not merely already-resolved-in-code — **wrong on the spec text itself**.
The mutual-reference concern doesn't exist because one of the two references is optional and the
spec explicitly names "intent linkage" as its own successor-revision event. No ruling needed here;
raising it as a ruling request would ask the Conductor to adjudicate a non-problem.

---

## 7. §11 `StoryCluster` — is `translation`/`update` independent corroboration or not? — REAL, already an open freeze-change question in an unmerged PR

**Note on the candidate's wording**: the literal word "attestation" does not appear anywhere in
CONTRACTS.md (checked: zero hits). The real question, once traced to spec text, is about
`independent_source_groups` counting, not a missing "attestation field" in the sense of a
verifier-signed statement. I'm reframing to what the spec actually says; the underlying concern
survives.

**Spec text**, §11 `StoryCluster`, purpose line 493:

> preserve one evolving story without mistaking syndication for corroboration.

**Spec text**, member shape, lines 503–507:

> `relationship: exact | near | syndicated | translation | update | same_event`

**Spec text**, invariant, line 529:

> Independent corroboration counts distinct `source_group_id` values, not member count.

The purpose clause names exactly one relationship value — `syndicated` — as the thing that must
not be mistaken for corroboration. It says nothing about `translation` or `update`. Both are
republications of the same underlying story (a translated version, or an updated version of the
same article) rather than an independently-sourced confirmation — which is arguably closer in kind
to `syndicated` than to `exact`/`near`/`same_event`, but the spec never says so explicitly either
way.

**Why reading alone can't resolve it**: the purpose clause and the invariant together tell you
*that* `independent_source_groups` must exclude non-independent republication, but the only named
example is `syndicated`. Whether `translation` and `update` count as independent sources (inflating
the corroboration count) or as republication (excluded, like `syndicated`) is not decidable from
the text — both readings are defensible, and picking either without a ruling is an implementer
narrowing a frozen contract in one direction or the other.

**Already implemented one way in code, with the tension explicitly flagged**: `story_cluster.py` on
open PR #4610, lines 47–63:

> `members[].relationship` carries five other values (`exact`, `near`, `translation`, `update`, `same_event`); of these, `translation` and `update` are counted as independent attestation DELIBERATELY, not by oversight. A translated or updated republish is not the mechanical, no-new-verification reproduction the purpose clause names — `syndicated` alone denotes that [...] Whether corroboration-inflation risk nonetheless argues for excluding `translation`/`update` too is a live freeze-change question this module does not answer here; per section 21's closing rule [...] it stays open pending that proposal rather than being resolved unilaterally in code.

The implementer chose the narrowest reading of the purpose clause (only `syndicated` is excluded,
because that's the only word actually named) and explicitly declined to extrapolate further,
citing §21's own rule against unilateral narrowing.

**Candidate answers and what breaks under each**:
- **(a) Ratify the current reading** — only `syndicated` is excluded from
  `independent_source_groups`; `translation` and `update` count as independent. Risk: a story that
  gets translated into three languages by the same original outlet, or updated three times, could
  inflate the corroboration count to 3 or more distinct `source_group_id`s without any genuinely
  independent confirmation ever existing — precisely the failure mode the purpose clause exists to
  prevent, just reached through a side door the clause didn't name.
- **(b) Extend the exclusion to `translation` and `update`** as well, on the theory that neither
  represents new verification of the underlying claim. Risk: a genuinely independent outlet that
  happens to publish an updated follow-up on a story (new reporting, not a republish) would be
  wrongly excluded from counting as independent corroboration — the relationship taxonomy doesn't
  distinguish "updated because new facts emerged" from "updated the same facts, cosmetic edit."
- Neither answer is free of a failure mode; that's exactly why this is a ruling request and not a
  bug fix.

**Blast radius**: blocks **D1 exit / D4 contract PASS** for `StoryCluster` (open PR #4610, live
right now) and has direct downstream consequences for Packet 06 (NAGA claim ledger) and Packet 05
(Intel Lake), both of which consume corroboration-count signal from this object.

---

## 8. `ContentObject` model accepts a wire document its own generated schema rejects (null-semantics divergence on `supersedes_content_object_ref`) — REAL, already ledgered with a precise repro

**Spec text** (module docstring, `hashing.py`, `origin/main`, merged, lines 3–5 — quoting the
governing rule, since CONTRACTS.md itself doesn't restate JCS mechanics):

> `research-os/v1.0.0` uses presence-preserving null semantics (option b): an absent Pydantic field is omitted, while a field explicitly set to `None` is serialized as JSON `null`. Mapping inputs already preserve that distinction.

This is a real wire-contract rule this package's own hashing module states as binding, derived from
§2's canonicalization rules (RFC 8785 JCS, lines 26–35) — §2 itself doesn't spell out the
absent-vs-null distinction in so many words, but `object_hash()` (`hashing.py` lines 66–77) is
built on it: it calls `model_dump(mode="json", exclude_unset=True)`, meaning a field's presence in
the hashed document depends on whether it was set, not on its value.

**The divergence** (verified directly against PR #4643's `content_object.py`, lines 201–220 for the
schema and line 257 for the model check):

- **Schema** (`model_config.json_schema_extra`, an `allOf`/`if`/`then` block): for `revision == 1`,
  `"then": {"not": {"required": ["supersedes_content_object_ref"]}}`. JSON Schema `required` tests
  **key presence only**, regardless of value — so a document with
  `"supersedes_content_object_ref": null` present as a key **fails** this constraint (the key *is*
  present, so `not: {required: [...]}` is violated), and the schema rejects it.
- **Model** (`validate_content_object`, line 257): `if self.revision == 1 and
  self.supersedes_content_object_ref is not None:` — this tests the **deserialized value**. A JSON
  `null` deserializes to Python `None`, so `is not None` is `False`, and the check never fires —
  the model **accepts** it.

So a revision-1 `ContentObject` carrying `"supersedes_content_object_ref": null` explicitly is
**rejected by the schema and accepted by the model** — the two validation paths disagree on the
same document. The absent-key case and the present-with-real-value case agree on both sides; only
the present-with-explicit-null case diverges.

**Why reading alone can't resolve it**: this isn't a case of one side simply being buggy in an
obvious way — the schema is *correctly* implementing JSON Schema's presence-only semantics for
`required`, and the model is *correctly* implementing a value-based check that happens to treat
`None` as "as good as absent." Both are locally coherent; they just encode different rules for the
same field. `hashing.py`'s own stated rule (presence-preserving: absent ≠ explicit-null) sides with
the schema's stricter reading — an explicit `null` is a different, present value, not nothing — but
that rule lives in a different file from the one with the bug, and nothing forces the two to be
checked against each other.

**Already implemented one way in code, and already ledgered**: `.claude/skills/modus/PENDING-ARMS.md`,
row opened 2026-08-23, states the resolved direction of the asymmetry precisely: "the model's
`is not None` check collapses the distinction the contract says must be preserved, treating an
explicit `null` as if it were absent — so at revision 1 the model wrongly ACCEPTS a document the
contract, by its own stated rule, says is invalid." The same row explicitly frames the two remedies
as a **choice**, not a "which side is fussier" question (matching how the team-lead candidate note
insisted this be framed):

**Candidate answers and what breaks under each**:
- **(a) Tighten the model** — change `validate_content_object`'s check from `is not None` to a
  presence check (e.g., checking `"supersedes_content_object_ref" in
  self.model_fields_set`), so an explicit `null` at revision 1 is rejected identically by both
  schema and model. This matches `hashing.py`'s documented rule as-is; no wire-contract text
  changes. Cost: a code change plus a new negative fixture (`invalid_revision_one_explicit_null_
  supersedes_ref` or similar) to lock the behavior in.
- **(b) Formally amend `hashing.py`'s documented rule** to carve out an exception for this field
  (or for optional reference fields generally): explicit-null and absent should NOT be
  distinguished for `supersedes_content_object_ref` at revision 1. Cost: this weakens a
  general wire-contract statement that's true for every *other* optional field on every other
  kind in the spec — the exception would need to be scoped precisely enough not to quietly loosen
  hashing behavior anywhere else, and the schema's `allOf`/`if`/`then` block would then be the one
  that's "wrong" and needs relaxing to accept the null form.
- (a) is the lower-risk fix (it tightens one model to match an already-stated general rule); (b)
  changes a rule the package treats as load-bearing for every kind's hash identity. But the
  decision is the Conductor's, not mine to presume.

**Blast radius**: blocks **D1 exit / D4 contract PASS** for `ContentObject` (open PR #4643, live
right now). Narrow in surface (one field, one kind, one specific wire shape — explicit null at
revision 1) but the *pattern* (model checks value where schema checks presence) is worth watching
for on every other `supersedes_*_ref`-shaped optional field across the other 24 kinds; I did not
have scope in this task to re-audit all of them and did not do so.

---

## 9. The extension jail's reserved-name set is incomplete relative to CONTRACTS.md's own nested field names — REAL, but the candidate's stated *mechanism* is wrong; corrected version already ledgered

**Correction to the candidate's framing, checked directly against the code**: the claim as written
says "`V1_RESERVED_EXTENSION_FIELD_NAMES` ... is a flat set of TOP-LEVEL names, so a core field
name nested inside `extensions.<ns>.payload` is accepted [i.e. not caught]." I read
`validate_extensions()` (`primitives.py`, `origin/main`, merged, lines 453–474) directly: it walks
the extension **payload's own tree** recursively —

```python
pending: list[Any] = [extension.payload]
while pending:
    value = pending.pop()
    if isinstance(value, dict):
        shadowed.update(V1_RESERVED_EXTENSION_FIELD_NAMES.intersection(value))
        pending.extend(value.values())
    elif isinstance(value, (list, tuple)):
        pending.extend(value)
```

— checking every nested dict's keys against the reserved set at **every depth** of the payload,
not just the top level. The function's own docstring says so: "Enforce namespaces and recursively
jail the frozen core vocabulary." So a payload nesting a reserved name **anywhere** in its own
structure is already caught — the candidate's stated failure mode (nesting inside the payload lets
a reserved name slip through) does not reproduce against this code.

**What actually reproduces, verified against the real reserved-name set** (extracted the full
251-member `frozenset` literal from `primitives.py` lines 89–342 and checked membership directly):
common words that appear **only nested inside one of CONTRACTS.md's own kind definitions** — never
as a bare top-level field of any of the 25 kinds — are **missing from the reserved set entirely**,
regardless of where they'd appear in an extension payload. Confirmed absent from the 251-member
set: `count`, `name`, `size`, `type`, `kind`, `role`, `threshold` — all of which appear nested in
the spec (e.g. `MetricResult.sample.subgroups[].name`/`size`, `.exclusions[].count`,
`RiskReclassificationReceipt.remediation.type`, `MetricProfile.guardrails[].threshold`, line 916,
963–966, 1001). The set-building process evidently walked only each kind's own top-level field
names, not the field names of every sub-object nested within a kind — so those nested-only names
were never added to the set at all, and a payload using one of them (at *any* depth, including the
payload's own top level) is never caught, because the string simply isn't a member.

**Already ledgered with a precise, cross-checked repro**: `.claude/skills/modus/PENDING-ARMS.md`,
row opened 2026-08-23 (Pro, P04-D1 metrics ship, ledger carryover):

> Reproduced end-to-end against `MetricResult` (fixture `valid_minimal.json`, hash recomputed post-mutation): `extensions.<ns>.payload = {"aggregation_level": "per-clip"}` is ACCEPTED although `aggregation_level` is a REQUIRED field of `MetricResult.classification` [...] Positive control: `metric_profile_ref` (a name that IS in the 251-name set) nested the same way IS correctly rejected — `validate_extensions()` [...] does walk the payload recursively, it just intersects every dict's keys against one FLAT, top-level-only **set** [not a flat top-level-only *walk*]. DO NOT just extend that list: re-derived every model field name across all 9 kinds not already reserved = 51, of which about half are bare common English words [...] jailing those rejects legitimate extension payloads wholesale (superscar #3, over-match on a bare token). A NAME-only jail cannot distinguish `MetricResult.classification.aggregation_level` from an unrelated extension's own same-named field — the real fix is PATH-aware, not a longer list.

This confirms and sharpens the candidate's ultimate ask (is the fix path-aware) while correcting the
mechanism: the bug is **set incompleteness** (nested-only spec field names were never captured),
not **walk shallowness** (the walk already recurses). The candidate's proposed cure-that's-wrong
("adding the nested names would jail ~23 bare common words") is exactly what the ledger row
independently derived and rejected for the same reason (superscar #3, over-match on a bare token).

**Candidate answers and what breaks under each** (unchanged from the candidate's own framing, now
grounded in the corrected mechanism):
- **(a) Make the jail path-aware** — track not just "is this name reserved" but "is this name
  reserved *at the path where a real core object would have it*" (e.g. only flag
  `aggregation_level` when it appears at a payload path that structurally mirrors
  `classification.aggregation_level`). Correct but non-trivial: requires encoding each reserved
  name's structural context, not just its string.
- **(b) Extend the flat set to include every nested-only field name too**, accepting the
  over-jailing the ledger row measured (~half of 51 additional names are common English words that
  would then reject legitimate, unrelated extension payloads using them at any depth).
- **(c) Leave the set as-is** (accept the false-negative gap for nested-only names), on the theory
  that the top-level-only set already covers every name most likely to be *deliberately* smuggled
  (the ones that are also a kind's own top-level identity), and the nested-only misses are lower
  risk. This is implicitly what's shipped today.
- The ledger row already rules out (b) empirically. The real ruling needed is **(a) vs (c)** — does
  P04 D1 ship a path-aware jail now, or does it explicitly declare the nested-name gap an accepted
  residual risk and move on.

**Blast radius**: does not block D1/D2/D3 mechanically (the guard degrades to under-catching, not
to crashing or over-rejecting anything currently shipped) but **is a live extension-boundary
violation** — §2 line 46's "an extension cannot change a core field's meaning [...] until promoted
through the freeze-change protocol" is silently violable today for any nested-only field name.
Relevant to **D4 contract PASS** sign-off, since the compatibility matrix should record this as a
known limitation rather than the reviewer discovering it unannounced.

---

## Summary for the Conductor

| # | Item | Verdict | Blast radius | Already ledgered? |
|---|---|---|---|---|
| 1 | `approval_subject_kind` undefined kinds | REAL | future kinds (Packet 02/10/11) + D4 matrix | No — fresh finding |
| 2 | `payload_ref` union, no discriminator | REAL | D1/D4 (`IntelEvent`, PR #4610) | No — flagged in PR docstring only |
| 3 | `arguments_ref` bare `str` | REAL | D3 + D4 (already merged) | No — flagged nowhere until now |
| 4 | `OutcomeEvent` missing `revocation_receipt_ref` | REAL | D1/D4 (PR #4653) + live revocation flows | No — flagged in PR docstring only |
| 5 | `queue.closed` unregistered receipt type | REAL, **already caused a bug** | D1/D4/D3, universal operation | **Yes** — PENDING-ARMS 2026-08-23 |
| 6 | mutual fixed point, ActionItem/ActionIntent | **WRONG — DROPPED** | n/a | n/a |
| 7 | StoryCluster translation/update corroboration | REAL (reframed from "attestation") | D1/D4 (PR #4610) + Packets 05/06 | No — flagged in PR docstring only |
| 8 | ContentObject null-semantics divergence | REAL | D1/D4 (PR #4643) | **Yes** — PENDING-ARMS 2026-08-23 |
| 9 | Extension jail reserved-set incompleteness | REAL (mechanism corrected) | D4 matrix, live boundary gap | **Yes** — PENDING-ARMS 2026-08-23 |

**Most urgent: item 5 (§13.5 closure registry gap).** Reasons, in order: (1) it is the only item
that has already caused a real, independently-reproduced security-relevant bug (a receipt could
smuggle an `ExecutionAttempt` reference past a blocklist that didn't know `queue.closed` existed) —
this isn't a hypothetical risk, it happened; (2) "closure" is not an edge case or a future-kind
concern like items 1, 2, 4, 7 — every `ActionItem` that ever finishes closes, so this is hit on
essentially every queue lifecycle, immediately, including by Packet 12 (kita Action Inbox), the
packet this whole chain exists to feed; (3) the defensive code fix (allow-list instead of
blocklist) is safe under either ruling answer, so ruling this does not require re-opening already-
shipped code — it only requires picking a registry string, which is the cheapest possible fix once
decided. Item 3 (`arguments_ref`) is the runner-up: it is the only *other* item already live on
merged `main`, and unlike item 5 its cost grows the longer it's left unruled (more fixtures and
adapters get written against the untyped-string shape every day it stays open).

**On the one dropped item**: item 6 is not stale, it's incorrect as stated — §13.1's
`current_intent_ref` is optional and §13.5 explicitly names "intent linkage" as its own successor-
revision event, so there is no unsatisfiable mutual reference at creation time. I'd rather flag this
plainly than let a non-problem take up a ruling slot.

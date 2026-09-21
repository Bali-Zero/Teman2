"""The `intel_items` -> D4 admission bridge -- an ADAPTER, not a second engine.

WHY THIS MODULE EXISTS. `research_os_objects` (migration 279) has zero rows in production. The
admission engine that would fill it (`naga_admission.admit`) is complete but was only ever wired
to `naga_claims`, a legacy table that carries none of the four things `admit()` requires --
`raw_payload->>'verbatim_excerpt'`, `raw_payload->>'citation'`, `canonical_url`, `published_at`
-- so every `naga_claims` row is excluded on rule 1 by construction
(`naga_admission`'s own module docstring; `naga_backfill.py`'s "ON TODAY'S LEGACY CORPUS THE
EXPECTED DRY-RUN RESULT IS ZERO ADMITTED"). `intel_items`, produced by `regulatory_watcher`, DOES
carry all four (measured live, 66 of 1,922 rows). This module maps THAT shape into the
`(record, source_snapshot)` pair `admit()` already consumes -- migration 279's own words: "Work
Packet 04 owns this table; domain packets build adapters/projections on top, never a parallel
core." `admit()` itself is untouched; this module only supplies its two inputs.

THE ONE DESIGN DECISION THAT SHAPES EVERYTHING BELOW: the canonical document IS the cited
excerpt. `document_content_hash = sha256(verbatim_excerpt)` and `source_snapshot["body"] =
verbatim_excerpt` -- never a hash of, or a body fetched from, `canonical_url` itself. This is
required for `admit()` to stay deterministic (D4, same input -> same decision, every run) without
this module performing its own network I/O (a live re-fetch of a government URL could change
between two runs of the same admission report, which would make the report non-diffable). The
consequence, named honestly and not left for a future reader to discover the hard way:

- `_span_is_exact` becomes TAUTOLOGICAL here. The "quoted span" and the "document body" are the
  SAME string by construction (`quoted_text = verbatim_excerpt = body`), so the locator this
  module mints always resolves and the hash always matches -- the rule is exercised (still
  computed, still capable of raising `exact_span_missing` if a future edit to this module ever
  breaks the identity), but for THIS record shape it can never be the rule that excludes a row.
  It verifies the excerpt against itself, not against an independently fetched document.
- `_source_version_resolves` is likewise satisfied by construction: this module always registers
  exactly the `document_version_id` it puts on the record, pointing at exactly this
  `document_content_hash`. It is not a vacuous check in general (a hand-built or corrupted
  `source_snapshot` could still fail it), but for every record THIS module produces it always
  holds.
- `_intel_event_identity_resolves` keeps real discriminating power, but not the one its own
  docstring describes ("the resolved event must be the event FOR THIS DOCUMENT"): since this
  module always mints the `IntelEvent` itself, `source.uri` and `record.document_id` are the same
  string by construction, so the CROSS-DOCUMENT binding check can never fire here either. What
  DOES still fire, and fires on real data (see below): `payload_ref` (a `DurablePayloadReference`)
  requires an `https://`/`s3://` URI with a host, and roughly two-thirds of `intel_items.
  canonical_url` values measured live are NOT a URL at all -- `regulatory_watcher` stores a
  human-readable source label there (`"DDTC News | https://..."`, `"nb: NB-INTEL-Tax"`), not a
  bare URI. Those rows fail `intel_event.schema.json` validation and are excluded by NAME
  (`intel_event_identity_missing`), which is the correct, non-defaulting D4 behaviour for a
  malformed identity -- it is a data-quality finding about `canonical_url`, not a bug in this
  bridge, and not something this module papers over with a laxer payload_ref shape.

A reader of a future admission report must not mistake either bullet's "always holds" for "this
input was independently verified" -- it was not; it is definitionally true given how this module
builds its inputs. The one rule that is NOT weakened by this construction, and remains the real
signal on real data, is `_statement_is_from_source`: the claimed `citation` must occur in the
excerpt as a whole, delimited token. `regulatory_watcher`'s `citation` and `verbatim_excerpt`
fields are produced independently (one summarizes a regulation number, the other quotes body
text) and roughly 40 of today's 66 fully-sourced rows do NOT contain their own citation verbatim
-- this module does not paraphrase, normalize or fuzzy-match the citation into the excerpt to
make that number look better; a citation that legitimately is not a literal substring is
correctly `statement_not_from_source`.

WHAT `--dry-run` DOES. `bridge()` itself never opens a database connection, never fetches a URL,
never writes anywhere -- it is a pure function over one already-fetched `intel_items` row.
`main()`/`--dry-run` is read-only (`SET default_transaction_read_only = on`, mirroring
`naga_backfill.py`'s own connection pattern) and prints the `summarize()` tally plus a
`manifest_hash`/`source_snapshot_hash` pair -- counts, named reasons and hashes, never a
`verbatim_excerpt`, `citation` or `canonical_url` value.

WHAT `--apply` DOES, AND WHY IT EXISTS NOW. The owner authorized the DML on 2026-09-21, scoped to
the `regulatory_watcher` cohort (`COHORT`), capped at `ADMITTED_ROW_CAP` (66) admitted rows,
touching only `research_os_objects` and `research_os_naga_admission` -- nothing else. `--apply
--manifest <64-hex>` recomputes the ENTIRE pipeline fresh in this process (`_compute`) and
refuses (`SourceSnapshotDrifted`, imported from `naga_backfill` rather than re-derived -- same
drift contract, same manifest shape) if the recomputed `manifest_hash` disagrees with the one the
caller names. It refuses again, by name, if the recomputed admitted count exceeds
`ADMITTED_ROW_CAP` (`AdmittedCohortExceedsCap`) -- a refusal, never a truncation to the first 66;
exceeding the cap means this is no longer the cohort the owner authorized. Both refusals write
zero rows. When neither refusal fires, every `Admitted` decision becomes exactly TWO
`research_os_objects` rows -- one `evidence`-kind (`_build_evidence_write`) and one `claim`-kind
(`_build_claim_write`) that cites it by real `(evidence_id, object_hash)` in its own
`evidence_refs`, never an empty tuple -- plus one `research_os_naga_admission` row, written
through `naga_persistence.write_objects`/`record_admissions` exactly as `naga_backfill.py` does;
this module issues no INSERT of its own. NEITHER payload is a re-shuffle of `bridge()`'s own
admission-input `record` (that shape exists ONLY to satisfy `admit()`'s rules, whose
`statement.subject_ref` is a bare `canonical_url` string -- sufficient for `admit()`'s
truthiness-only check, not for `ExactObjectRef`'s shape): both are independently built to satisfy
`research_os.models.claim.Claim`/`research_os.models.evidence.Evidence`, the frozen,
`extra="forbid"` pydantic contracts those object kinds promise, and BOTH are checked against
those exact models (`_validate_canonical_schema`, `CanonicalSchemaInvalid` on failure, BEFORE
either write reaches `naga_persistence` -- see that exception's own docstring for why a
`claim` row that is not a `Claim` is a worse defect than a missing write authorization).
`naga_persistence.validate_object` does not perform this check (D5 treats the jsonb payload as
opaque); this module adds it because nothing else in the write path will. All three rows -- both
objects and the admission row -- are written inside ONE transaction (mirroring
`naga_backfill._execute_apply`'s own comment: each nested call opens its own asyncpg SAVEPOINT,
so a failure recording admission rolls back whatever objects were already inserted). Idempotent
by construction: `claim_id`/`evidence_id` are `uuid5` of the item's own `canonical_url`, every
instant embedded in either payload is a real column value (`intel_items.first_seen_at`, the
synthetic `IntelEvent`'s own `times.observed_at`) rather than the wall clock, and NEITHER
payload carries the `manifest` at all: `lineage.run_id`/`provenance.run_id` are both `uuid5` of
the item's own `canonical_url` -- so a second `--apply` recomputes byte-identical payloads even
after the cohort has moved, `write_objects`' `ON CONFLICT (object_id) DO NOTHING` inserts zero
new object rows, and `record_admissions`' `ON CONFLICT (run_id, legacy_claim_id) DO NOTHING`
inserts zero new admission rows -- the report says so by name, not by silence. WHICH EXECUTION
wrote a row is recorded once, on the admission row (`AdmissionRow.run_id=manifest`), the one
place a per-run value can live without entering an object's canonical identity. PR #7004 was
BLOCKED for the opposite arrangement (`Claim.lineage.run_id = uuid5(manifest)`): a manifest
hashes the WHOLE cohort, so one new `intel_items` row gave the same `claim_id` a different
`object_hash`, and `regulatory_watcher` is a daily cron -- the idempotency window was ~24h. Six
green tests missed it because all six ran on a single manifest. `Excluded`/`Rejected` outcomes are never written to either table (same choice
`naga_backfill.py` makes for its own cohort) -- an admitted cohort of `ADMITTED_ROW_CAP` writes at
most `2 * ADMITTED_ROW_CAP` object rows plus `ADMITTED_ROW_CAP` admission rows in one run.

THE COHORT IS A FILTER, NOT A LABEL (PR #7007 gate, condition C1). The owner's authorization is
scoped to `COHORT`, and until that gate `COHORT` was only a string inside the manifest:
`_load_intel_items` read every `intel_items` row of every producer (1,922 on 2026-09-21, 128 of
them `is_probe_sandbox`), and the first `--apply` stayed inside the cohort only because every row
with an admissible shape happened to be `source_domain='regulatory-watcher'` (66/66, measured
read-only) -- a property of the data, not of the query. Now the query states it:
`_COHORT_SOURCE_DOMAIN[COHORT]` is the `source_domain` bound into `_load_intel_items`' `WHERE
source_domain = $1 AND NOT is_probe_sandbox`, so the name the manifest carries and the rows it
binds are one declaration. The filter changes the MANIFEST, never a payload: `items_read`,
`rejected_by_bridge` and `source_snapshot_hash` now cover only the cohort's rows, so a manifest
taken before the filter is refused as `SourceSnapshotDrifted` and the dry-run must be re-taken.
No payload reads anything the filter touches, so the 8 claim + 8 evidence objects the first
`--apply` wrote are recomputed byte-identical: a new `--apply` reports them `already_present`
and adds only their admission rows under the new `run_id` (the new manifest).

SOURCE TIER, SOURCE TYPE AND RIGHTS ARE DERIVED FROM THE HOST, NEVER FIXED FOR THE COHORT.
`Evidence.source_tier` exists to record EVIDENTIARY WEIGHT, so it may not be a constant: PR #7004
was BLOCKED for stamping `research_os.source_tier.government_gazette` on every admitted row while
all eight real candidates came from `news.ddtc.co.id` -- a PRIVATE Indonesian tax consultancy's
newsletter, with zero government hosts among them. `regulatory_watcher` watches government
sources AND the press that reports on them, and the admitted subset is by construction the rows
whose `canonical_url` is a bare URI, which is exactly where the press dominates. So
`_is_government_host` decides per row, from that row's own `canonical_url`: a government host
(label-bounded `.go.id`/`.gov.id`/`.gov` -- `evilgo.id` is not one) earns
`source_tier=...government_gazette`, `IntelEvent.source.source_type=government.gazette` and
`rights=public-domain`; EVERYTHING else, including a `canonical_url` that does not parse as a URL
at all, gets `...secondary_reporting`, `secondary.reporting` and `rights=publisher-copyright`.
The official tier is earned by positive proof from the host; the absence of a counter-proof never
earns it. The statute a press article quotes is public-domain -- the article quoting it is not.

WHAT REMAINS FIXED POLICY, NAMED AND NOT DEFAULTED SILENTLY. `intel_items` carries no
`risk_class`, `sensitivity`, `retention_class` or review state -- there is no per-row signal to
defer to. Rather than have `admit()`'s rules 6-9 exclude every row uniformly on a column this
source will never populate, this module assigns one named policy for the whole cohort on those
four: every row here is text already published on the open web, government or press alike, so
`risk_class=green / sensitivity=public / retention_class=public_record / review.state=unreviewed`.
That is a STATED assumption about this ONE source, not a general default `admit()` applies -- a
future adapter for a different `intel_items` producer (a confidential client-facing source, say)
must supply its own policy, not inherit this one.

WHY `retention_class` IGNORES THE HOST WHILE `rights` FOLLOWS IT (PR #7007 gate, C2). The frozen
contract gives the four `retention_class` values no semantics -- only the vocabulary
(`CONTRACTS.md` §3 `retention`, `research_os.primitives.Retention`) -- so this is a READING,
stated to be challenged. The contract's primitive table defines `retention` as "Policy, expiry,
legal hold, and rights expiry": the lifecycle of the object WE store. `classification.rights` is
what the PUBLISHER permits anyone to do with its text. They part here because of what the stored
object holds: per the Evidence invariant ("Short excerpts are stored only where rights and privacy
policy permit; otherwise retain locator and hash", `CONTRACTS.md` §5), neither payload carries
the publisher's text -- the evidence holds `source_span.{locator,start,end,quote_hash}` and
`document_content_hash`, the claim holds the `citation` -- so what we retain is our own record
that a public document said something, the same kind of record whether the host is a ministry or
a newsletter; the copyright attaches to the excerpt, which stays in `intel_items.raw_payload` and
never enters `research_os_objects`. Where a publisher's terms could bound OUR retention, the
contract's slot is `retention.rights_expires_at`, not `retention_class`; no `intel_items` row
carries such a term, so it stays unset. The value is also no longer free to revisit in place:
the rows already written carry `public_record` inside their `object_hash` (next section).

THE PAYLOAD CONSTANTS ARE A FROZEN IDENTITY (PR #7007 gate, C3). `evidence_id`/`claim_id` are
`uuid5` of `canonical_url` alone, but `object_hash` covers the whole payload: six `intel_items`
columns (`canonical_url`, `published_at`, `raw_payload.verbatim_excerpt`, `raw_payload.citation`,
`jurisdiction`, `first_seen_at`) plus every module constant a builder writes into either payload,
directly or through the synthetic `IntelEvent`'s own `object_hash` (which the evidence cites in
`source_event_ref`). Rows derived from them exist on an append-only table since the first
`--apply` (2026-09-21), so each of them is now part of those rows' identity: edit one and the next
`--apply` recomputes a different `object_hash` for an `object_id` already stored,
`naga_persistence._insert_object` raises `NagaWriteRejected("object_id_hash_collision")`, and the
ONE transaction rolls back the whole batch -- every new item is wedged with it, not just the
changed one. What enters the hash, read from the builders:

- both payloads: `_CONTRACT_VERSION`, `_TENANT`, `_EXTRACTOR`, `_RUN_NAMESPACE`,
  `_FAMILY_NAMESPACE`, `_CLASSIFICATION`, `_RETENTION`, `_REVIEW`, `_EVIDENCE_STANCE`,
  `_EVIDENCE_NAMESPACE` (the claim cites the evidence by id);
- evidence: `_EXTRACTOR_VERSION`, `_LOCATOR`, `_VERSION_NAMESPACE`, `_EVENT_NAMESPACE`,
  `_SOURCE_TIER_*`, `_RIGHTS_*`, and `_GOVERNMENT_HOST_SUFFIXES`, which picks within each pair;
- claim: `_CLAIM_NAMESPACE`, `_PREDICATE`, `_CLAIM_DOMAIN`, `_CLAIM_STATUS`, `_CONFIDENCE_METHOD`
  and the literal `score=1.0` -- plus the evidence's own `object_hash` (`statement.subject_ref`,
  `evidence_refs`), so whatever moves the evidence hash moves the claim's;
- through the IntelEvent hash: `_EVENT_CLASSIFICATION`, `_EVENT_RETENTION`, `_PIPELINE_NAMESPACE`,
  `_SOURCE_TYPE_*`, and `_build_intel_event`'s literals (`event_type`, `producer`,
  `payload_ref.ref_type`);
- the derivation code itself: `_to_rfc3339`, `_is_government_host`, `_sha256`, and
  `research_os.hashing.object_hash`'s canonicalisation.

`_CLAIM_NAMESPACE` alone fails differently: it re-mints `claim_id`, so nothing collides and every
claim is written a second time under a new id -- no better. `test_intel_evidence_bridge.py` pins
both hashes for a fixed item per host branch; an intended change needs a succession strategy
(`supersedes_evidence_ref`/`supersedes_claim_ref` plus an `ObjectSuccessorEdge`, `CONTRACTS.md`
§3.1), not a new expected value.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NoReturn
from urllib.parse import urlsplit

import asyncpg
from pydantic import ValidationError as _PydanticValidationError

# This import puts `packages/research-os-core` on `sys.path`, so it MUST precede every
# `research_os.*` import below. `# isort: split` is what holds the order against the
# formatter -- the same guard `naga_persistence.py` uses for the same reason. Without it
# the sorter hoists `research_os.hashing` above the bootstrap and `python -m` on this
# module dies with ModuleNotFoundError, a failure no test in this package can observe
# because conftest.py performs the same insert at collection time.
from backend.services.research_os import _core_path as _core_path

# isort: split

from research_os.hashing import object_hash as _object_hash
from research_os.models.claim import Claim
from research_os.models.evidence import Evidence

from backend.services.research_os.naga_admission import (
    AdmissionDecision,
    Admitted,
    admit,
    summarize,
)
from backend.services.research_os.naga_backfill import (
    SourceSnapshotDrifted,
    compute_manifest,
    compute_source_snapshot_hash,
)
from backend.services.research_os.naga_persistence import (
    AdmissionRow,
    ObjectWrite,
    record_admissions,
    validate_object,
    write_objects,
)

__all__ = [
    "ADMITTED_ROW_CAP",
    "COHORT",
    "DEFAULT_DSN_ENV",
    "REJECTION_REASONS",
    "AdmittedCohortExceedsCap",
    "ApplyReport",
    "BridgeResult",
    "CanonicalSchemaInvalid",
    "Mapped",
    "Rejected",
    "SourceSnapshotDrifted",
    "bridge",
    "main",
    "run_apply",
]

logger = logging.getLogger(__name__)

#: Name of the env var the DSN is read from, unless `--dsn-env` overrides it. Never printed,
#: logged or echoed -- mirrors `naga_backfill.DEFAULT_DSN_ENV`'s own contract.
DEFAULT_DSN_ENV = "INTEL_EVIDENCE_BRIDGE_DSN"

#: The ordered vocabulary for a mapping-level refusal -- BEFORE `admit()` ever runs. Distinct
#: from `naga_admission.EXCLUSION_REASONS`: those name why an admission RULE refused a
#: well-formed `(record, source_snapshot)` pair; these name why this module could not BUILD that
#: pair at all (an `intel_items` row missing one of the four fields `admit()` needs). Checked in
#: this order -- a row missing more than one field reports the first.
REJECTION_REASONS: tuple[str, ...] = (
    "canonical_url_missing",
    "published_at_missing",
    "verbatim_excerpt_missing",
    "citation_missing",
)

#: Fixed uuid5 namespaces, one per minted identity, so two different identities derived from the
#: same `canonical_url` never collide with each other. Arbitrary but FROZEN: changing any one of
#: these re-mints every id it produces and breaks determinism across runs.
_EVENT_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e1")
_VERSION_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e2")
_PIPELINE_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e3")
_FAMILY_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e4")
#: The `research_os_objects` identity minted for the `claim`-kind object `--apply` writes -- a
#: FIFTH namespace, never reused for an event/version/pipeline/family id above.
_CLAIM_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e5")

#: The one production cohort this module's `--apply` is authorized against (Zero, 2026-09-21) --
#: `intel_items` has exactly one producer (`regulatory_watcher`), so this is a fixed constant,
#: never a `--cohort` flag: there is no second cohort this bridge could be pointed at today.
COHORT = "regulatory_watcher"

#: What `COHORT` MEANS in `intel_items`: the `source_domain` `regulatory_watcher` writes there
#: (measured live, 2026-09-21). `_load_intel_items` binds exactly this value, so the name in the
#: manifest and the rows the manifest covers cannot drift apart -- see the module docstring's
#: "THE COHORT IS A FILTER" section. One entry, because there is one cohort.
_COHORT_SOURCE_DOMAIN: Mapping[str, str] = {COHORT: "regulatory-watcher"}

#: Owner-authorized cap (Zero, 2026-09-21) on admitted rows a single `--apply` run may write --
#: a REFUSAL past this line, never a truncation to the first `ADMITTED_ROW_CAP` rows. Measured
#: live at 8 admitted out of 1,922 `intel_items` rows the day this was authorized; the cap is
#: the owner's authorization boundary, not a capacity estimate.
ADMITTED_ROW_CAP = 66

_MANIFEST_RE = re.compile(r"^[0-9a-f]{64}$")

#: The one span this module ever registers per record -- a name, not data, so it stays constant.
_LOCATOR = "verbatim_excerpt"

#: The statement triple's predicate -- see the module docstring's design-decision note. Truthy,
#: fixed, and not sourced from `intel_items` (there is no column that would supply it).
_PREDICATE = "research_os.intel_evidence_bridge.cites"

_CONTRACT_VERSION = "research-os/v1.0.0"
_TENANT = "bali-zero"

#: The COHORT-WIDE half of the policy -- see the module docstring's "WHAT REMAINS FIXED POLICY"
#: section. Copied (never mutated in place) into every record this module produces. `rights` is
#: deliberately NOT here: it tracks the host (`_rights_for`), because a private publisher's
#: article is not public-domain just because the statute it quotes is.
_CLASSIFICATION: Mapping[str, str] = {"risk_class": "green", "sensitivity": "public"}
#: `legal_hold` is required on `research_os.primitives.Retention` (no default) -- always `False`
#: for this source, same "public, already-published" reasoning as the rest of this policy. Why
#: `retention_class` does not split per host the way `rights` does, and why it is frozen now:
#: the module docstring's `retention_class` and "FROZEN IDENTITY" sections.
_RETENTION: Mapping[str, Any] = {"retention_class": "public_record", "legal_hold": False}
_REVIEW: Mapping[str, str] = {"state": "unreviewed"}

#: The IntelEvent's OWN classification/retention -- schema-constrained enums
#: (`intel_event.schema.json`), distinct fields from the record's `_CLASSIFICATION`/`_RETENTION`
#: above even though the values happen to agree for this source.
_EVENT_CLASSIFICATION: Mapping[str, str] = {"risk_class": "green", "sensitivity": "public"}
_EVENT_RETENTION: Mapping[str, Any] = {"retention_class": "public_record", "legal_hold": False}

#: `research_os.models.claim.Claim`/`research_os.models.evidence.Evidence` -- both frozen,
#: `extra="forbid"` -- are the two canonical shapes `--apply` writes. Fixed, named policy for
#: fields those two models require but neither `intel_items` nor `admit()`'s own record shape
#: supplies (see `_build_evidence_write`/`_build_claim_write`, and the module docstring's
#: "WHAT --apply DOES" section for why each one is honest rather than invented):
_CLAIM_DOMAIN = "regulatory"  #: `ClaimScope.domain` -- this source is Indonesian regulatory text.
_CLAIM_STATUS = "supported"  #: `ClaimStatus` -- `admit()` already proved the statement is
#: evidence-backed (`_statement_is_from_source`); "supported" names exactly that, nothing more.
_EVIDENCE_STANCE = "supports"  #: `EvidenceStance` -- same proof, the evidence SUPPORTS the claim.
#: `Evidence.source_tier` (`RegisteredName`) and the synthetic `IntelEvent`'s
#: `source.source_type` (`Identifier`), PAIRED: both answer "what kind of source is this", and no
#: row may be a gazette in one field and a newsletter in the other. Chosen per row by
#: `_source_tier_for`/`_source_type_for` from the host -- see the module docstring's "SOURCE TIER,
#: SOURCE TYPE AND RIGHTS" section. These are this module's own namespace, distinct from
#: `naga.tier.*` (which buckets a NAGA `credibility_score`, an input `intel_items` does not have).
_SOURCE_TIER_GOVERNMENT = "research_os.source_tier.government_gazette"
_SOURCE_TIER_SECONDARY = "research_os.source_tier.secondary_reporting"
_SOURCE_TYPE_GOVERNMENT = "government.gazette"
_SOURCE_TYPE_SECONDARY = "secondary.reporting"
#: `classification.rights` -- same host split, same reason (`admit()`'s rule 6 only requires the
#: field to be PRESENT, so both values pass admission; the value is about reuse, not admissibility).
_RIGHTS_GOVERNMENT = "public-domain"
_RIGHTS_SECONDARY = "publisher-copyright"
_EXTRACTOR = "research_os.intel_evidence_bridge"  #: `Identifier` -- this module, naming itself.
_EXTRACTOR_VERSION = "1.0.0"
#: `ClaimConfidence.method` -- NOT a truth/veracity estimate. `score=1.0` below measures
#: EXTRACTION FIDELITY: `admit()`'s `_value_is_anchored_in_span` already proved the claimed
#: value is a literal, delimited token of the cited span, mechanically, before this row could
#: ever be `Admitted` -- so the score is not a guess about whether the underlying regulatory
#: fact is true, only a statement that the extraction is exactly what the source says, verified
#: deterministically rather than estimated. The name says this so a future reader never mistakes
#: it for a veracity judgment.
_CONFIDENCE_METHOD = "research_os.intel_evidence_bridge.span_anchored_admission"

#: Sixth/seventh uuid5 namespaces (see the five above) -- `_EVIDENCE_NAMESPACE` mints the
#: `evidence_id` `--apply` writes per admitted item; `_RUN_NAMESPACE` mints BOTH run ids
#: (`Evidence.provenance.run_id` and `Claim.lineage.run_id`) from the item's own `canonical_url`.
#: Neither is therefore an EXECUTION identity -- it is a per-document extraction identity, stable
#: for as long as the document is, and that is the point: every value inside a payload enters its
#: `object_hash`, so a per-run value there (the manifest, a wall clock) would give the same
#: `claim_id` a different hash on the next run and destroy the idempotency `--apply` promises.
#: WHICH run wrote the row lives on the admission row instead (`AdmissionRow.run_id`).
_EVIDENCE_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e6")
_RUN_NAMESPACE = uuid.UUID("8f2c1a00-0000-4000-8000-0000000000e7")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: Government host suffixes, matched on the PARSED host's own dot-delimited labels. A substring
#: or bare-`endswith` test on the URL string is the guard-over-match this repo keeps re-learning:
#: `evilgo.id` and `https://news.example.com/go.id/x` are not government hosts.
_GOVERNMENT_HOST_SUFFIXES: tuple[str, ...] = ("go.id", "gov.id", "gov")


def _is_government_host(canonical_url: str) -> bool:
    """True ONLY when this row's own `canonical_url` parses to a government host.

    Unparseable input, a hostless string (`intel_items.canonical_url` is often
    `"DDTC News | https://..."`), or any non-government host all return False: the official tier
    is earned by positive proof, never by the absence of a counter-proof.
    """

    try:
        host = (urlsplit(canonical_url).hostname or "").strip().lower().rstrip(".")
    except ValueError:  # a malformed URL (an invalid IPv6 literal, say) is not a proof of anything
        return False
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in _GOVERNMENT_HOST_SUFFIXES)


def _source_tier_for(canonical_url: str) -> str:
    return _SOURCE_TIER_GOVERNMENT if _is_government_host(canonical_url) else _SOURCE_TIER_SECONDARY


def _source_type_for(canonical_url: str) -> str:
    return _SOURCE_TYPE_GOVERNMENT if _is_government_host(canonical_url) else _SOURCE_TYPE_SECONDARY


def _rights_for(canonical_url: str) -> str:
    return _RIGHTS_GOVERNMENT if _is_government_host(canonical_url) else _RIGHTS_SECONDARY


def _classification_for(canonical_url: str) -> dict[str, str]:
    """The cohort-wide `_CLASSIFICATION` plus the one field that tracks this row's own host."""

    return {**_CLASSIFICATION, "rights": _rights_for(canonical_url)}


@dataclass(frozen=True)
class Mapped:
    """`intel_item` carried everything `admit()` needs; here is the input it needs, built."""

    intel_item_id: str
    record: Mapping[str, Any]
    source_snapshot: Mapping[str, Any]


@dataclass(frozen=True)
class Rejected:
    """`intel_item` is missing a field this bridge cannot build `admit()`'s input without.

    Never a bare `None`/`False` -- same NAMED-reason contract `naga_admission.Excluded` uses.
    This is a MAPPING failure, not an admission decision: a row rejected here never reaches
    `admit()` at all, and its reason is never one of `naga_admission.EXCLUSION_REASONS`.
    """

    intel_item_id: str
    reason: str


BridgeResult = Mapped | Rejected


class AdmittedCohortExceedsCap(Exception):
    """`--apply`'s recomputed admitted count exceeds `ADMITTED_ROW_CAP`. Zero writes.

    Named the same way `SourceSnapshotDrifted` (imported from `naga_backfill`) is: the exact
    numbers involved, never a bare message -- a caller catching this can log `admitted`/`cap`
    without re-parsing a string.
    """

    def __init__(self, *, admitted: int, cap: int) -> None:
        self.admitted = admitted
        self.cap = cap
        super().__init__(f"admitted cohort exceeds cap: admitted={admitted} cap={cap}")


class CanonicalSchemaInvalid(Exception):
    """A payload `--apply` built for `object_kind` does not validate against the canonical model
    that name promises (`Claim`/`Evidence`, `research_os.models.*`). Zero writes.

    `naga_persistence.validate_object` never runs this check -- it recomputes `object_hash` and
    checks the write-path instant grammar, nothing about the payload's OWN declared shape (D5
    treats `research_os_objects.payload` as opaque jsonb by design). Writing an object whose
    `object_kind` names a contract it does not satisfy is a worse defect than a missing DML
    authorization: a `claim` row that is not a `Claim` lies about what it is to every future
    reader, forever, on an append-only table. So THIS module gates on it before either the
    `claim` or the `evidence` write ever reaches `naga_persistence` -- named by field path, from
    pydantic's own error locations, never a bare traceback.
    """

    def __init__(self, *, object_kind: str, object_id: str, errors: tuple[str, ...]) -> None:
        self.object_kind = object_kind
        self.object_id = object_id
        self.errors = errors
        super().__init__(
            f"canonical schema invalid: object_kind={object_kind} object_id={object_id} "
            f"errors={errors}"
        )


_CANONICAL_MODELS: Mapping[str, type] = {"claim": Claim, "evidence": Evidence}


def _validate_canonical_schema(write: ObjectWrite) -> None:
    """`Claim.model_validate`/`Evidence.model_validate` on `write.payload`, keyed by
    `write.object_kind` -- see `CanonicalSchemaInvalid`'s docstring for why this exists
    alongside, not instead of, `naga_persistence.validate_object`."""

    model = _CANONICAL_MODELS.get(write.object_kind)
    if model is None:
        return
    try:
        model.model_validate(write.payload)
    except _PydanticValidationError as exc:
        field_paths = tuple(
            ".".join(str(part) for part in error["loc"]) or "<root>" for error in exc.errors()
        )
        raise CanonicalSchemaInvalid(
            object_kind=write.object_kind, object_id=write.object_id, errors=field_paths
        ) from exc


def _raw_payload(intel_item: Mapping[str, Any]) -> Mapping[str, Any]:
    """`raw_payload` arrives as a `dict` when the caller's connection pool has a jsonb codec
    registered, and as a JSON `str` over a bare `asyncpg` connection with no such codec (this
    module's own `--dry-run` path, which opens a plain `asyncpg.connect`) -- both are accepted."""

    payload = intel_item.get("raw_payload")
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str) and payload:
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return {}
        return decoded if isinstance(decoded, Mapping) else {}
    return {}


def _to_rfc3339(value: Any) -> str | None:
    """A deterministic RFC3339 string ending in `Z`/`+00:00` (`intel_event.schema.json`'s
    `IntelEventTimes` pattern) -- never the wall clock, so `bridge()` stays pure."""

    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        # PARSE, never concatenate. `timestamptz` rendered as text by PostgreSQL ends in `+00`
        # -- neither `Z` nor `+00:00` -- and appending `Z` to it produced the malformed
        # `2026-09-17 10:30:00+00Z`, which this module then hashed into an `IntelEvent` that no
        # longer validated. The admission verdict became a function of the DB driver: the same
        # instant admitted as a `datetime` and was excluded as a string. Routing both forms
        # through the branch above is what makes the verdict driver-independent.
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            # Not an instant at all. A named refusal upstream (`published_at_missing`) beats a
            # fabricated timestamp that only fails later, inside the schema validator.
            return None
        return _to_rfc3339(parsed)
    return None


def _anchor(value: str, quoted_text: str) -> dict[str, int]:
    """Offsets of `value` inside `quoted_text`, IF it occurs there as a literal substring.

    When it does not, this still returns a well-formed, in-bounds `{start, end}` pair rather
    than `None` -- `admit()` requires `value_span` to be present to even evaluate the anchor, and
    a record with a citation that is genuinely not in its own excerpt must reach `admit()` and be
    excluded there (`statement_not_from_source`, via `_value_is_anchored_in_span`'s slice
    inequality), not be silently dropped by this module before `admit()` ever sees it.
    """

    index = quoted_text.find(value)
    if index >= 0:
        return {"start": index, "end": index + len(value)}
    end = max(1, min(len(value), len(quoted_text)))
    return {"start": 0, "end": end}


def _build_intel_event(
    *,
    event_id: str,
    canonical_url: str,
    document_content_hash: str,
    published_at: str,
    pipeline_run_id: str,
) -> dict[str, Any]:
    """A synthetic `IntelEvent`, minted by THIS bridge -- there is no upstream `IntelEvent`
    producer for `intel_items` yet (P05, deferred). Built the same way
    `test_naga_admission.py`'s own fixture builds one: assemble the dict, then compute
    `object_hash` over it (never hand-typed, never carried from anywhere else)."""

    node: dict[str, Any] = {
        "event_id": event_id,
        "contract_version": _CONTRACT_VERSION,
        "tenant": _TENANT,
        "event_type": "intel.regulatory_excerpt.observed",
        "producer": {
            "name": "research_os.intel_evidence_bridge",
            "version": "1.0.0",
            "machine_class": "bridge-synthetic",
        },
        "source": {"uri": canonical_url, "source_type": _source_type_for(canonical_url)},
        "times": {"observed_at": published_at, "ingested_at": published_at},
        "identity": {"content_hash": document_content_hash, "idempotency_key": canonical_url},
        "classification": dict(_EVENT_CLASSIFICATION),
        "lineage": {"pipeline_run_id": pipeline_run_id, "input_event_refs": []},
        "payload_ref": {
            "ref_type": "reference",
            "uri": canonical_url,
            "content_hash": document_content_hash,
        },
        "retention": dict(_EVENT_RETENTION),
        "object_hash": "0" * 64,
    }
    node["object_hash"] = _object_hash(node)
    return node


def bridge(intel_item: Mapping[str, Any]) -> BridgeResult:
    """Map one `intel_items` row into `admit()`'s `(record, source_snapshot)` input, or refuse
    by name. Pure: no I/O, no clock, no randomness -- the same `intel_item` always produces
    byte-identical output (`json.dumps(..., sort_keys=True)`-comparable), which is what makes an
    admission report over this bridge diffable run over run, same as D4 requires of `admit()`
    itself.
    """

    item_id = str(intel_item.get("id") or "")

    canonical_url = intel_item.get("canonical_url")
    if not isinstance(canonical_url, str) or not canonical_url:
        return Rejected(intel_item_id=item_id, reason="canonical_url_missing")

    published_at = _to_rfc3339(intel_item.get("published_at"))
    if not published_at:
        return Rejected(intel_item_id=item_id, reason="published_at_missing")

    raw_payload = _raw_payload(intel_item)
    verbatim_excerpt = raw_payload.get("verbatim_excerpt")
    if not isinstance(verbatim_excerpt, str) or not verbatim_excerpt:
        return Rejected(intel_item_id=item_id, reason="verbatim_excerpt_missing")

    citation = raw_payload.get("citation")
    if not isinstance(citation, str) or not citation:
        return Rejected(intel_item_id=item_id, reason="citation_missing")

    document_content_hash = _sha256(verbatim_excerpt)
    document_version_id = str(
        uuid.uuid5(_VERSION_NAMESPACE, f"{canonical_url}:{document_content_hash}")
    )
    event_id = str(uuid.uuid5(_EVENT_NAMESPACE, canonical_url))
    pipeline_run_id = str(uuid.uuid5(_PIPELINE_NAMESPACE, canonical_url))
    family_id = str(uuid.uuid5(_FAMILY_NAMESPACE, canonical_url))

    intel_event = _build_intel_event(
        event_id=event_id,
        canonical_url=canonical_url,
        document_content_hash=document_content_hash,
        published_at=published_at,
        pipeline_run_id=pipeline_run_id,
    )

    record: dict[str, Any] = {
        "id": item_id,
        "document_id": canonical_url,
        "document_version_id": document_version_id,
        "document_content_hash": document_content_hash,
        "source_span": {
            "locator": _LOCATOR,
            "quoted_text": verbatim_excerpt,
            "quote_hash": _sha256(verbatim_excerpt),
        },
        "statement": {
            "subject_ref": canonical_url,
            "predicate": _PREDICATE,
            "object_ref_or_value": citation,
            "value_span": _anchor(citation, verbatim_excerpt),
            "derived_from_span": True,
        },
        "source_event_ref": {"event_id": event_id},
        "classification": _classification_for(canonical_url),
        "retention": dict(_RETENTION),
        "review": dict(_REVIEW),
        "manifest_family_id": family_id,
    }

    source_snapshot: dict[str, Any] = {
        "body": verbatim_excerpt,
        "intel_events": {event_id: intel_event},
        "document_versions": {
            document_version_id: {"document_id": canonical_url, "content_hash": document_content_hash}
        },
        "locators": {_LOCATOR: {"start": 0, "end": len(verbatim_excerpt)}},
    }

    return Mapped(intel_item_id=item_id, record=record, source_snapshot=source_snapshot)


def _require_instant(value: Any, *, column: str, item_id: str) -> str:
    """Like `_to_rfc3339`, but for a column the schema declares `NOT NULL` -- a `None` result
    here is not a named `Rejected` reason (there is no admission-mapping vocabulary entry for
    it, because a `NOT NULL` column cannot legitimately be absent); it is a schema-contract
    violation this module refuses to paper over with a fabricated instant.
    """

    parsed = _to_rfc3339(value)
    if parsed is None:
        raise ValueError(f"intel_items.{column} is not a parseable instant for item {item_id}")
    return parsed


def _build_evidence_write(mapped: Mapped, *, item: Mapping[str, Any]) -> ObjectWrite:
    """The addressable source unit the Claim below cites as its own `evidence_refs` entry --
    `research_os.models.evidence.Evidence`, section 5 of frozen CONTRACTS.md: "an addressable
    source unit supporting or contradicting a claim." Every field not covered by a module-level
    fixed policy (see the constants above) comes from `mapped.record`/`item`, never invented:
    `document_id`/`document_version_id`/`document_content_hash`/`source_span.{locator,
    quote_hash}` are `bridge()`'s own admission-judged values, byte-identical to what `admit()`
    evaluated; `source_event_ref` adds the intel_event's OWN `object_hash` (`bridge()`'s record
    only carries `event_id`, sufficient for `admit()`'s rules but not for `EventRef`'s exact-
    reference contract); `times.recorded_at` is `intel_items.first_seen_at` -- when
    `regulatory_watcher` itself first recorded this item, the honest answer to "when was this
    evidence recorded", never the wall clock (this must stay deterministic for
    `--apply`-run-twice idempotency: a wall-clock value would give the same `evidence_id` a
    different `object_hash` on replay, which `write_objects` correctly reports as a hash
    collision rather than accepting)."""

    canonical_url = str(mapped.record["document_id"])
    item_id = str(item.get("id") or mapped.intel_item_id)
    evidence_id = str(uuid.uuid5(_EVIDENCE_NAMESPACE, canonical_url))
    source_span = mapped.record["source_span"]
    quoted_text = source_span["quoted_text"]
    event_id = mapped.record["source_event_ref"]["event_id"]
    intel_event = mapped.source_snapshot["intel_events"][event_id]
    recorded_at = _require_instant(item.get("first_seen_at"), column="first_seen_at", item_id=item_id)

    payload: dict[str, Any] = {
        "evidence_id": evidence_id,
        "evidence_family_id": f"{_EXTRACTOR}.evidence_family.{mapped.record['manifest_family_id']}",
        "contract_version": _CONTRACT_VERSION,
        "tenant": _TENANT,
        "source_event_ref": {"event_id": event_id, "object_hash": intel_event["object_hash"]},
        "document_id": canonical_url,
        "document_version_id": mapped.record["document_version_id"],
        "document_content_hash": mapped.record["document_content_hash"],
        "source_span": {
            "locator": source_span["locator"],
            "start": 0,
            "end": len(quoted_text),
            "quote_hash": source_span["quote_hash"],
        },
        "source_tier": _source_tier_for(canonical_url),
        "stance": _EVIDENCE_STANCE,
        "times": {
            "observed_at": intel_event["times"]["observed_at"],
            "valid_from": intel_event["times"]["observed_at"],
            "recorded_at": recorded_at,
        },
        "provenance": {
            "extractor": _EXTRACTOR,
            "extractor_version": _EXTRACTOR_VERSION,
            "run_id": str(uuid.uuid5(_RUN_NAMESPACE, canonical_url)),
            "extraction_input_hash": mapped.record["document_content_hash"],
        },
        "classification": _classification_for(canonical_url),
        "review_state": mapped.record["review"]["state"],
        "retention": dict(_RETENTION),
        "object_hash": "0" * 64,
    }
    payload["object_hash"] = _object_hash(payload)

    return ObjectWrite(object_kind="evidence", object_id=evidence_id, payload=payload)


def _build_claim_write(
    mapped: Mapped, *, item: Mapping[str, Any], evidence_write: ObjectWrite
) -> ObjectWrite:
    """`research_os.models.claim.Claim` -- section 6 of frozen CONTRACTS.md. Built from
    `mapped.record` plus the evidence object above, never from a bare re-shuffle of the
    admission-input record `admit()` judged (that record's `statement.subject_ref` is a plain
    `canonical_url` string, sufficient for `admit()`'s truthiness-only check on `subject_ref`
    but not `ExactObjectRef`'s shape): here `subject_ref` names the `evidence` object THIS
    `--apply` run is also writing, by its own real, freshly-computed `object_hash` -- "the
    evidence this claim's statement is drawn from", not a dangling reference to something never
    persisted. `claim_family_id` reuses `admit()`'s OWN `manifest_family_id` (the same seed,
    `canonical_url`, under a namespace distinct from `claim_id`'s) rather than minting a second,
    competing family concept. `scope.jurisdiction` is `intel_items.jurisdiction` WHEN the column
    is actually populated -- never a constant standing in for missing data; `scope.domain` is
    the one honest constant this source-wide policy can state (see `_CLAIM_DOMAIN`).
    `time.valid_from`/`confidence`/`status` -- see the module-level constants' own docstrings for
    why each value is the one `admit()`'s own verification already proved, not a fabrication.
    `lineage.run_id` is `uuid5(_RUN_NAMESPACE, canonical_url)` -- the SAME derivation the evidence
    above uses, and deliberately NOT the caller's `manifest`: this builder no longer receives it,
    so the defect cannot be reintroduced by an edit inside this function. A manifest hashes the
    whole cohort, so binding it here put a value that moves for reasons EXTERNAL to the object
    inside the object's own `object_hash` (PR #7004, BLOCK). The execution that wrote the row is
    recorded on the admission row instead (`AdmissionRow.run_id=manifest`), which is what that
    column is for.
    """

    canonical_url = str(mapped.record["document_id"])
    item_id = str(item.get("id") or mapped.intel_item_id)
    claim_id = str(uuid.uuid5(_CLAIM_NAMESPACE, canonical_url))
    claim_family_id = str(mapped.record["manifest_family_id"])
    recorded_at = _require_instant(item.get("first_seen_at"), column="first_seen_at", item_id=item_id)

    event_id = mapped.record["source_event_ref"]["event_id"]
    intel_event = mapped.source_snapshot["intel_events"][event_id]
    valid_from = intel_event["times"]["observed_at"]

    scope: dict[str, Any] = {"domain": _CLAIM_DOMAIN}
    jurisdiction = item.get("jurisdiction")
    if jurisdiction:
        scope["jurisdiction"] = jurisdiction

    payload: dict[str, Any] = {
        "claim_id": claim_id,
        "claim_family_id": claim_family_id,
        "contract_version": _CONTRACT_VERSION,
        "tenant": _TENANT,
        "statement": {
            "subject_ref": {
                "object_kind": evidence_write.object_kind,
                "object_id": evidence_write.object_id,
                "object_hash": evidence_write.payload["object_hash"],
            },
            "predicate": mapped.record["statement"]["predicate"],
            "object_ref_or_value": mapped.record["statement"]["object_ref_or_value"],
        },
        "scope": scope,
        "time": {"recorded_at": recorded_at, "valid_from": valid_from},
        "status": _CLAIM_STATUS,
        "evidence_refs": [
            {
                "evidence_id": evidence_write.object_id,
                "object_hash": evidence_write.payload["object_hash"],
                "stance": _EVIDENCE_STANCE,
            }
        ],
        "confidence": {"score": 1.0, "method": _CONFIDENCE_METHOD},
        "classification": {
            "risk_class": _CLASSIFICATION["risk_class"],
            "sensitivity": _CLASSIFICATION["sensitivity"],
        },
        "review": dict(mapped.record["review"]),
        "lineage": {
            "run_id": str(uuid.uuid5(_RUN_NAMESPACE, canonical_url)),
            "extractor": _EXTRACTOR,
            "input_claim_refs": [],
        },
        "retention": dict(_RETENTION),
        "object_hash": "0" * 64,
    }
    payload["object_hash"] = _object_hash(payload)

    return ObjectWrite(object_kind="claim", object_id=claim_id, payload=payload)


# ------------------------------------------------------------------------------------------
# Dry-run CLI -- read-only, reports only counts and named reasons.
# ------------------------------------------------------------------------------------------


async def _load_intel_items(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """`COHORT`'s rows only -- `source_domain = _COHORT_SOURCE_DOMAIN[COHORT]`, and never an
    `is_probe_sandbox` row (migration 187: "queries SHOULD include `WHERE NOT
    is_probe_sandbox`") -- so the authorization's scope is enforced by the read, not inferred
    from the data's current shape. Explicit column list, ordered by `id` (never `SELECT *`) --
    the four columns `admit()` needs, plus `id`, plus the two columns ONLY the `--apply` write
    path reads (`jurisdiction` for `Claim.scope.jurisdiction`, `first_seen_at` for
    `time.recorded_at`/`times.recorded_at`) -- nothing else this module has no use for. Both
    extra columns also widen `compute_source_snapshot_hash`'s own per-row hash (it hashes every
    column this SELECT returns), which is correct: a row whose `jurisdiction`/`first_seen_at`
    changed would write a different `Claim`/`Evidence`, so the manifest must bind to it too."""

    records = await conn.fetch(
        "SELECT id, canonical_url, published_at, raw_payload, jurisdiction, first_seen_at "
        "FROM intel_items WHERE source_domain = $1 AND NOT is_probe_sandbox ORDER BY id",
        _COHORT_SOURCE_DOMAIN[COHORT],
    )
    return [dict(record) for record in records]


@dataclass(frozen=True)
class DryRunReport:
    """Counts, named reasons and the manifest -- never a field value from any `intel_items` row."""

    items_read: int
    rejected_by_bridge: Mapping[str, int]
    admitted: int
    excluded_by_reason: Mapping[str, int]
    manifest_hash: str
    source_snapshot_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": "dry-run",
            "items_read": self.items_read,
            "rejected_by_bridge": dict(self.rejected_by_bridge),
            "admitted": self.admitted,
            "excluded_by_reason": dict(self.excluded_by_reason),
            "manifest_hash": self.manifest_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
        }


@dataclass(frozen=True)
class ApplyReport:
    """What `--apply` actually did -- counts per table, never a field value from any row."""

    items_read: int
    rejected_by_bridge: Mapping[str, int]
    admitted: int
    excluded_by_reason: Mapping[str, int]
    manifest_hash: str
    source_snapshot_hash: str
    objects_inserted: int
    objects_already_present: int
    admissions_inserted: int
    written: tuple[tuple[str, str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": "apply",
            "items_read": self.items_read,
            "rejected_by_bridge": dict(self.rejected_by_bridge),
            "admitted": self.admitted,
            "excluded_by_reason": dict(self.excluded_by_reason),
            "manifest_hash": self.manifest_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
            "objects_inserted": self.objects_inserted,
            "objects_already_present": self.objects_already_present,
            "admissions_inserted": self.admissions_inserted,
            "written": [
                {"object_kind": object_kind, "object_id": object_id, "object_hash": object_hash}
                for object_kind, object_id, object_hash in self.written
            ],
        }


def render_report(report: DryRunReport | ApplyReport, *, as_json: bool = False) -> str:
    data = report.as_dict()
    if as_json:
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [
        f"mode: {data['mode']}",
        f"manifest_hash: {data['manifest_hash']}",
        f"source_snapshot_hash: {data['source_snapshot_hash']}",
        f"items_read: {data['items_read']}",
        "rejected_by_bridge:",
    ]
    for reason in sorted(data["rejected_by_bridge"]):
        lines.append(f"  {reason}: {data['rejected_by_bridge'][reason]}")
    lines.append(f"admitted: {data['admitted']}")
    lines.append("excluded_by_reason:")
    for reason in sorted(data["excluded_by_reason"]):
        lines.append(f"  {reason}: {data['excluded_by_reason'][reason]}")
    if "written" in data:
        lines.append(f"objects_inserted: {data['objects_inserted']}")
        lines.append(f"objects_already_present: {data['objects_already_present']}")
        lines.append(f"admissions_inserted: {data['admissions_inserted']}")
        lines.append("written:")
        for entry in data["written"]:
            lines.append(f"  {entry['object_kind']} {entry['object_id']}: {entry['object_hash']}")
    return "\n".join(lines)


@dataclass(frozen=True)
class _Computed:
    """The one pipeline's full output -- `run_dry_run`/`run_apply` both project from this, and
    `run_apply` recomputes it fresh (never reuses a caller-supplied one) so a manifest agreement
    always reflects THIS call's own read, never a cached prior one."""

    intel_items: list[Mapping[str, Any]]
    rejected_by_bridge: Mapping[str, int]
    #: `(bridge result, admission decision, RAW intel_items row)` -- the raw row travels
    #: alongside because `--apply`'s writers need `jurisdiction`/`first_seen_at`, columns
    #: `bridge()`'s own `Mapped.record` never carries (they play no role in `admit()`'s rules).
    mapped_admitted: tuple[tuple[Mapped, Admitted, Mapping[str, Any]], ...]
    excluded_by_reason: Mapping[str, int]
    admitted: int
    source_snapshot_hash: str
    manifest_hash: str


def _compute_sync(intel_items: Sequence[Mapping[str, Any]]) -> _Computed:
    """Bridge every row, `admit()` every `Mapped` result, tally with `summarize()` (reused, not
    reimplemented), and bind EVERY row's fate -- `rejected_by_bridge`, `excluded`, `admitted`
    alike -- into one manifest via `naga_backfill.compute_manifest`/`compute_source_snapshot_hash`
    (also reused): a row that changes anywhere in this cohort, admitted or not, changes the
    manifest, which is what makes `--apply`'s drift check meaningful over the WHOLE cohort read,
    not just the admitted slice.
    """

    rejected_by_bridge: dict[str, int] = {}
    decisions: list[AdmissionDecision] = []
    mapped_by_item_id: dict[str, tuple[Mapped, Mapping[str, Any]]] = {}
    manifest_decisions: list[tuple[str, str, str | None]] = []

    for item in intel_items:
        item_id = str(item.get("id") or "")
        result = bridge(item)
        if isinstance(result, Rejected):
            rejected_by_bridge[result.reason] = rejected_by_bridge.get(result.reason, 0) + 1
            manifest_decisions.append((item_id, "rejected_by_bridge", result.reason))
            continue
        decision = admit(result.record, source_snapshot=result.source_snapshot)
        decisions.append(decision)
        if isinstance(decision, Admitted):
            mapped_by_item_id[decision.legacy_claim_id] = (result, item)
            manifest_decisions.append((item_id, "admitted", decision.family_id))
        else:
            manifest_decisions.append((item_id, "excluded", decision.reason))

    summary = summarize(decisions)
    mapped_admitted_list: list[tuple[Mapped, Admitted, Mapping[str, Any]]] = []
    for decision in decisions:
        if isinstance(decision, Admitted):
            mapped_result, raw_item = mapped_by_item_id[decision.legacy_claim_id]
            mapped_admitted_list.append((mapped_result, decision, raw_item))
    mapped_admitted = tuple(mapped_admitted_list)

    source_snapshot_hash = compute_source_snapshot_hash(intel_items)
    _, manifest_hash = compute_manifest(
        cohort=COHORT, source_snapshot_hash=source_snapshot_hash, decisions=manifest_decisions
    )

    return _Computed(
        intel_items=list(intel_items),
        rejected_by_bridge=rejected_by_bridge,
        mapped_admitted=mapped_admitted,
        excluded_by_reason=dict(summary.excluded_by_reason),
        admitted=summary.admitted,
        source_snapshot_hash=source_snapshot_hash,
        manifest_hash=manifest_hash,
    )


def run_dry_run_sync(intel_items: list[Mapping[str, Any]]) -> DryRunReport:
    """The pure tally step, split out from the DB read so tests can drive it without a
    connection."""

    computed = _compute_sync(intel_items)
    return DryRunReport(
        items_read=len(computed.intel_items),
        rejected_by_bridge=computed.rejected_by_bridge,
        admitted=computed.admitted,
        excluded_by_reason=computed.excluded_by_reason,
        manifest_hash=computed.manifest_hash,
        source_snapshot_hash=computed.source_snapshot_hash,
    )


async def run_dry_run(conn: asyncpg.Connection) -> DryRunReport:
    intel_items = await _load_intel_items(conn)
    return run_dry_run_sync(intel_items)


async def _compute(conn: asyncpg.Connection) -> _Computed:
    """`run_apply`'s own fresh read -- never the caller's `--dry-run` result -- so a manifest
    agreement proves THIS instant's data, not a stale one."""

    intel_items = await _load_intel_items(conn)
    return _compute_sync(intel_items)


# ------------------------------------------------------------------------------------------
# Apply -- writes through `naga_persistence` only, one transaction, capped and manifest-gated.
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _ApplyOutcome:
    objects_inserted: int
    objects_already_present: int
    admissions_inserted: int
    written: tuple[tuple[str, str, str], ...]


async def _execute_apply(
    conn: asyncpg.Connection,
    *,
    writes: Sequence[ObjectWrite],
    admission_rows: Sequence[AdmissionRow],
) -> _ApplyOutcome:
    """ONE transaction for the whole batch -- `write_objects`/`record_admissions` each nest
    their own via an asyncpg SAVEPOINT (the same pattern `naga_backfill._execute_apply` uses and
    describes), so a failure recording the second table rolls back whatever the first already
    inserted. Zero writes, zero I/O, when `writes` is empty -- a cohort with nothing admitted is
    a valid, silent no-op.
    """

    inserted_ids: tuple[str, ...] = ()
    already_present_ids: tuple[str, ...] = ()
    admissions_inserted = 0
    if writes:
        async with conn.transaction():
            write_result = await write_objects(conn, writes)
            inserted_ids = write_result.inserted_ids
            already_present_ids = write_result.already_present_ids
            admissions_inserted = await record_admissions(conn, admission_rows)

    written = tuple(
        (write.object_kind, write.object_id, str(write.payload["object_hash"]))
        for write in writes
        if write.object_id in inserted_ids
    )
    return _ApplyOutcome(
        objects_inserted=len(inserted_ids),
        objects_already_present=len(already_present_ids),
        admissions_inserted=admissions_inserted,
        written=written,
    )


async def run_apply(conn: asyncpg.Connection, *, manifest: str) -> ApplyReport:
    """Recomputes the dry-run pipeline fresh; refuses (zero writes) on manifest disagreement
    (`SourceSnapshotDrifted`) or on an admitted count past `ADMITTED_ROW_CAP`
    (`AdmittedCohortExceedsCap`) -- checked, and raised, BEFORE any `ObjectWrite` is built."""

    computed = await _compute(conn)
    if computed.manifest_hash != manifest:
        raise SourceSnapshotDrifted(given=manifest, computed=computed.manifest_hash)
    if computed.admitted > ADMITTED_ROW_CAP:
        raise AdmittedCohortExceedsCap(admitted=computed.admitted, cap=ADMITTED_ROW_CAP)

    writes: list[ObjectWrite] = []
    admission_rows: list[AdmissionRow] = []
    for mapped, decision, item in computed.mapped_admitted:
        evidence_write = _build_evidence_write(mapped, item=item)
        validate_object(evidence_write)
        _validate_canonical_schema(evidence_write)

        claim_write = _build_claim_write(mapped, item=item, evidence_write=evidence_write)
        validate_object(claim_write)
        _validate_canonical_schema(claim_write)

        writes.append(evidence_write)
        writes.append(claim_write)
        admission_rows.append(
            AdmissionRow(
                run_id=manifest,
                legacy_claim_id=decision.legacy_claim_id,
                family_id=decision.family_id,
                claim_object_id=claim_write.object_id,
                claim_object_hash=str(claim_write.payload["object_hash"]),
                evidence_object_ids=(evidence_write.object_id,),
                evidence_object_hashes=(str(evidence_write.payload["object_hash"]),),
                source_snapshot_hash=computed.source_snapshot_hash,
                decision="admitted",
                reason=None,
            )
        )

    outcome = await _execute_apply(conn, writes=writes, admission_rows=admission_rows)
    return ApplyReport(
        items_read=len(computed.intel_items),
        rejected_by_bridge=computed.rejected_by_bridge,
        admitted=computed.admitted,
        excluded_by_reason=computed.excluded_by_reason,
        manifest_hash=manifest,
        source_snapshot_hash=computed.source_snapshot_hash,
        objects_inserted=outcome.objects_inserted,
        objects_already_present=outcome.objects_already_present,
        admissions_inserted=outcome.admissions_inserted,
        written=outcome.written,
    )


def _require_dsn(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        _refuse(f"refused: environment variable {env_name} is not set")
    return value


def _refuse(message: str, *, code: int = 2) -> NoReturn:
    print(message)  # noqa: T201 -- the refusal message IS this CLI's diagnostic output
    raise SystemExit(code)


async def _dry_run_main(dsn: str) -> DryRunReport:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET default_transaction_read_only = on")
        return await run_dry_run(conn)
    finally:
        await conn.close()


async def _apply_main(dsn: str, *, manifest: str) -> ApplyReport:
    """No `SET default_transaction_read_only` here -- unlike `_dry_run_main`, this path writes,
    exactly as `naga_backfill._apply_main` does for its own cohort."""

    conn = await asyncpg.connect(dsn)
    try:
        return await run_apply(conn, manifest=manifest)
    finally:
        await conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.services.research_os.intel_evidence_bridge",
        description=(
            "Bridge intel_items into admit()'s input. Dry-run by default (read-only). "
            "--apply --manifest <64-hex> writes the admitted cohort (regulatory_watcher only, "
            f"capped at {ADMITTED_ROW_CAP} admitted rows) through naga_persistence, and only "
            "if the recomputed manifest still agrees."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="read-only (default mode)")
    parser.add_argument("--apply", action="store_true", help="write; requires --manifest")
    parser.add_argument("--manifest", help="64-hex manifest hash from a prior --dry-run")
    parser.add_argument(
        "--dsn-env",
        default=DEFAULT_DSN_ENV,
        help=f"name of the env var carrying the DSN (default {DEFAULT_DSN_ENV})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.dry_run and args.apply:
        _refuse("refused: --dry-run and --apply are mutually exclusive")
    if args.apply:
        if not args.manifest:
            _refuse("refused: --apply requires --manifest <64-hex>")
        if _MANIFEST_RE.fullmatch(args.manifest) is None:
            _refuse("refused: --manifest must be 64 lowercase hex characters")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _validate_args(args)
    dsn = _require_dsn(args.dsn_env)

    if args.apply:
        try:
            report: DryRunReport | ApplyReport = asyncio.run(
                _apply_main(dsn, manifest=args.manifest)
            )
        except SourceSnapshotDrifted as exc:
            logger.warning("apply refused: source snapshot drifted (given=%s)", exc.given)
            _refuse("refused: source_snapshot_drifted", code=3)
        except AdmittedCohortExceedsCap as exc:
            logger.warning(
                "apply refused: admitted cohort exceeds cap (admitted=%d cap=%d)",
                exc.admitted,
                exc.cap,
            )
            _refuse(
                f"refused: admitted_cohort_exceeds_cap admitted={exc.admitted} cap={exc.cap}",
                code=4,
            )
        except CanonicalSchemaInvalid as exc:
            logger.warning(
                "apply refused: canonical schema invalid (object_kind=%s object_id=%s errors=%s)",
                exc.object_kind,
                exc.object_id,
                exc.errors,
            )
            _refuse(
                f"refused: canonical_schema_invalid object_kind={exc.object_kind} "
                f"object_id={exc.object_id} errors={exc.errors}",
                code=5,
            )
    else:
        report = asyncio.run(_dry_run_main(dsn))

    print(render_report(report, as_json=args.json))  # noqa: T201 -- the report IS this CLI's output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

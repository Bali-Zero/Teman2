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

WHAT THIS MODULE DOES NOT DO. It never opens a database connection, never fetches a URL, never
writes anywhere; `bridge()` is a pure function over one already-fetched `intel_items` row.
`main()`/`--dry-run` is read-only (`SET default_transaction_read_only = on`, mirroring
`naga_backfill.py`'s own connection pattern) and prints ONLY the `summarize()` tally -- counts and
named reasons, never a `verbatim_excerpt`, `citation` or `canonical_url` value. There is no
`--apply` in this module, on purpose: writing admitted objects into `research_os_objects` needs
the owner's explicit authorization for the DML, which this PR does not have.

CLASSIFICATION/RETENTION/REVIEW ARE FIXED POLICY DEFAULTS, NOT DEFAULTED SILENTLY.
`intel_items` carries no `risk_class`, `sensitivity`, `rights`, `retention_class` or review
state -- there is no per-row signal to defer to. Rather than have `admit()`'s rules 6-9 exclude
every row uniformly on a column this source will never populate, this module assigns one fixed,
named policy for this entire source: Indonesian government regulatory gazette text, already
public by the nature of `regulatory_watcher`'s own sourcing (public statute/circular text), is
`risk_class=green / sensitivity=public / rights=public-domain / retention_class=public_record /
review.state=unreviewed`. This is a STATED assumption about this ONE source, not a general
default `admit()` applies -- a future adapter for a different `intel_items` producer (a
confidential client-facing source, say) must supply its own policy, not inherit this one.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NoReturn

import asyncpg

# This import puts `packages/research-os-core` on `sys.path`, so it MUST precede every
# `research_os.*` import below. `# isort: split` is what holds the order against the
# formatter -- the same guard `naga_persistence.py` uses for the same reason. Without it
# the sorter hoists `research_os.hashing` above the bootstrap and `python -m` on this
# module dies with ModuleNotFoundError, a failure no test in this package can observe
# because conftest.py performs the same insert at collection time.
from backend.services.research_os import _core_path as _core_path

# isort: split

from research_os.hashing import object_hash as _object_hash

from backend.services.research_os.naga_admission import admit, summarize

__all__ = [
    "DEFAULT_DSN_ENV",
    "REJECTION_REASONS",
    "BridgeResult",
    "Mapped",
    "Rejected",
    "bridge",
    "main",
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

#: The one span this module ever registers per record -- a name, not data, so it stays constant.
_LOCATOR = "verbatim_excerpt"

#: The statement triple's predicate -- see the module docstring's design-decision note. Truthy,
#: fixed, and not sourced from `intel_items` (there is no column that would supply it).
_PREDICATE = "research_os.intel_evidence_bridge.cites"

_CONTRACT_VERSION = "research-os/v1.0.0"
_TENANT = "bali-zero"

#: The one fixed policy this module applies -- see the module docstring's "CLASSIFICATION/..."
#: section. Copied (never mutated in place) into every record this module produces.
_CLASSIFICATION: Mapping[str, str] = {
    "risk_class": "green",
    "sensitivity": "public",
    "rights": "public-domain",
}
_RETENTION: Mapping[str, str] = {"retention_class": "public_record"}
_REVIEW: Mapping[str, str] = {"state": "unreviewed"}

#: The IntelEvent's OWN classification/retention -- schema-constrained enums
#: (`intel_event.schema.json`), distinct fields from the record's `_CLASSIFICATION`/`_RETENTION`
#: above even though the values happen to agree for this source.
_EVENT_CLASSIFICATION: Mapping[str, str] = {"risk_class": "green", "sensitivity": "public"}
_EVENT_RETENTION: Mapping[str, Any] = {"retention_class": "public_record", "legal_hold": False}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        "source": {"uri": canonical_url, "source_type": "government.gazette"},
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
        "classification": dict(_CLASSIFICATION),
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


# ------------------------------------------------------------------------------------------
# Dry-run CLI -- read-only, reports only counts and named reasons.
# ------------------------------------------------------------------------------------------


async def _load_intel_items(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Explicit column list, ordered by `id` (never `SELECT *`) -- the four columns `admit()`
    needs plus `id`, and nothing else this module has no use for."""

    records = await conn.fetch(
        "SELECT id, canonical_url, published_at, raw_payload FROM intel_items ORDER BY id"
    )
    return [dict(record) for record in records]


@dataclass(frozen=True)
class DryRunReport:
    """Counts and named reasons only -- never a field value from any `intel_items` row."""

    items_read: int
    rejected_by_bridge: Mapping[str, int]
    admitted: int
    excluded_by_reason: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "items_read": self.items_read,
            "rejected_by_bridge": dict(self.rejected_by_bridge),
            "admitted": self.admitted,
            "excluded_by_reason": dict(self.excluded_by_reason),
        }


def render_report(report: DryRunReport, *, as_json: bool = False) -> str:
    data = report.as_dict()
    if as_json:
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [
        f"items_read: {data['items_read']}",
        "rejected_by_bridge:",
    ]
    for reason in sorted(data["rejected_by_bridge"]):
        lines.append(f"  {reason}: {data['rejected_by_bridge'][reason]}")
    lines.append(f"admitted: {data['admitted']}")
    lines.append("excluded_by_reason:")
    for reason in sorted(data["excluded_by_reason"]):
        lines.append(f"  {reason}: {data['excluded_by_reason'][reason]}")
    return "\n".join(lines)


def run_dry_run_sync(intel_items: list[Mapping[str, Any]]) -> DryRunReport:
    """The pure tally step, split out from the DB read so tests can drive it without a
    connection: bridge every row, then `admit()` every `Mapped` result, then `summarize()`."""

    rejected_by_bridge: dict[str, int] = {}
    decisions = []
    for item in intel_items:
        result = bridge(item)
        if isinstance(result, Rejected):
            rejected_by_bridge[result.reason] = rejected_by_bridge.get(result.reason, 0) + 1
            continue
        decisions.append(admit(result.record, source_snapshot=result.source_snapshot))

    summary = summarize(decisions)
    return DryRunReport(
        items_read=len(intel_items),
        rejected_by_bridge=rejected_by_bridge,
        admitted=summary.admitted,
        excluded_by_reason=dict(summary.excluded_by_reason),
    )


async def run_dry_run(conn: asyncpg.Connection) -> DryRunReport:
    intel_items = await _load_intel_items(conn)
    return run_dry_run_sync(intel_items)


def _require_dsn(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        _refuse(f"refused: environment variable {env_name} is not set")
    return value


def _refuse(message: str) -> NoReturn:
    print(message)  # noqa: T201 -- the refusal message IS this CLI's diagnostic output
    raise SystemExit(2)


async def _dry_run_main(dsn: str) -> DryRunReport:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET default_transaction_read_only = on")
        return await run_dry_run(conn)
    finally:
        await conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.services.research_os.intel_evidence_bridge",
        description=(
            "Read-only dry-run: bridge every fully-sourced intel_items row into admit()'s "
            "input and report the tally. No --apply -- this module never writes."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="read-only (the only mode)")
    parser.add_argument(
        "--dsn-env",
        default=DEFAULT_DSN_ENV,
        help=f"name of the env var carrying the DSN (default {DEFAULT_DSN_ENV})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    dsn = _require_dsn(args.dsn_env)
    report = asyncio.run(_dry_run_main(dsn))
    print(render_report(report, as_json=args.json))  # noqa: T201 -- the report IS this CLI's output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""fold_pack_seq13_source.py — the seq-13 JOIN: combine the RULES-ONLY half
(``rulepack-prod-013.rules-only.json``, ``fold_pack_seq13_rules.py``) with
the source-freshness half (an 18-record ``verified_at``/``verified_by``
re-attestation of the OFFICIAL_PORTAL ``source_records``, the seq-12
pattern applied to seq-13) into the actual, signable
``rulepack-prod-013.source.json``.

**The freshness half's input contract is the EDIT-PAIR shape** — the same
schema seq-12's own ``source-restamp-edits.json`` uses: each restamp
carries ``source_record_id``, ``source_key`` (cross-checked against
seq-12's actual record, not just trusted — an id/key mismatch aborts),
``field`` (must read exactly ``"verified_at+verified_by"`` — this fold
refuses to consume an edit-pair claiming to touch anything else),
``current_verified_at``/``current_verified_by``, and
``new_verified_at``/``new_verified_by`` — 7 fields, verified against the
real ``inc5``/``inc7`` files on disk, not assumed from a routing message
(the first draft of this contract assumed 5). Not a full-record blob.
Settled 2026-08-23 (team-lead, after a same-day architecture fork — see
the "seq-14" note below): the edit-pair shape is
strictly better for a joiner, not merely consistent with family
convention — it lets this fold assert the declared PRIOR against seq-12's
ACTUAL bytes before mutating (a real ledger-drift gate), where a
full-record blob only asks to be trusted for what it claims to contain.
It also makes "content_sha256 never touched" true BY CONSTRUCTION rather
than by comparison: the edit-pair schema has no slot for content fields
at all, so there is nothing for a freshness input to smuggle even if it
tried — this fold's own field-scoped mutation (`verified_at`/
`verified_by` only, nothing else ever assigned) is the second, redundant
half of that guarantee.

**A same-day architecture fork, caught before it shipped.** Mid-build, the
freshness lane's worktree independently produced an uncommitted
``fold_pack_seq14.py`` that chained directly off seq-12 (same signed
hash), skipping seq-13 entirely — freshness-only, with NO rules-only
fixes (no E31C nationality-gap close, no D12 removal). Two children of one
parent, one signed active pack: had it shipped, the fixes would have
silently lost with nothing going red. The team-lead ruled it out
(traced to a routing-message race on their end, not a decision anyone
made) — **seq-13 combined is the path, seq-14 is stopped.** Left here
because the failure mode is worth knowing: a freshness-only re-attestation
convenience fold is easy to reach for and easy to get structurally wrong
when a rules-fix lane is mid-flight on the same parent.

Two lanes, two disjoint concerns, one join. Neither half's own fold owns
identity (``sequence``/``version``/``rule_pack_id``/
``previous_payload_sha256``/``created_at``/``created_by``) — both leave it
at seq-12's own values by design (see each fold's module docstring). This
module is where identity is actually assigned and where the chain anchors
to seq-12's SIGNED payload hash.

**Complement-of-the-rules-fold's guard.** ``fold_pack_seq13_rules.py``'s
own ``_assert_untouched`` holds ``products``/``source_records`` (and every
top-level key outside its declared rule edits) to whole-collection
equality with seq-12 — the rules-only lane owns neither. This module
enforces the complement: ``rules`` comes ONLY from the rules-only half
(taken wholesale, cross-checked that the rules-only payload's own
non-``rules`` content is untouched from seq-12 — i.e. the rules lane kept
its promise), and ``source_records`` comes ONLY from the freshness half
(the restamp applied to seq-12's own source_records, entity-derived as
the OFFICIAL_PORTAL set — never a frozen id list, the seq-12 pattern).
Every other top-level key must equal seq-12 canonically. If either half
smuggled a change outside its own lane, this fold aborts rather than
silently carrying it forward.

**On the freshness half's identical-timestamp shape — and the trend behind
it.** All 18 restamps in the freshness input currently carry the SAME
``verified_at`` value — a disclosed pass-level proxy timestamp (see that
file's own ``verified_at_caveat``), not 18 independently observed
per-source fetch times (none were logged). This fold does **not** reject
that shape: a script cannot manufacture 18 honest independent timestamps
out of one that were never captured, and inventing artificial jitter
would be *less* honest, not more.

But "seq-12 did the same thing" — this module's own first-draft framing,
corrected by the team-lead reading the actual bytes rather than trusting
that claim — is the wrong reference point. ``source-restamp-edits.json``
(seq-12's own restamp ledger) shows a DESCENDING staircase, not a stable
convention: the batch seq-12 itself replaced (inherited from seq-10/
seq-11) carried **7 distinct, second-precision values** — real per-fetch
times (``2026-08-18T21:41:23Z`` through ``2026-08-19T04:31:03Z``, verified
by reading the file directly). seq-12's own fold then rounded that down to
**2** (4 records at ``06:14:00Z``, 14 at ``06:15:00Z``). This freshness
input proposes **1**. Each restamp has been coarser than the last, and
nothing in this fold family has ever noticed, because every gate asserts
*advance*, never *resolution*. "What good looks like" is seq-10's 7
distinct values, not seq-12's 2 — citing seq-12 as the bar would enshrine
one step of degradation as acceptable practice.

What this fold DOES enforce mechanically, per record: the new
``verified_at`` strictly advances past the value it replaces (a real
ledger-drift guard, checked against the freshness file's own declared
prior value AND cross-checked against seq-12's actual bytes), and is not
later than this pack's own ``created_at`` (no fabricated future
attestation). Those are real teeth; distinctness-across-records is not,
and a guard that pretended otherwise would be worse engineering than
naming the gap plainly. So the shape is FLAGGED, never rejected and never
silently absorbed: a non-fatal note on stderr, mechanically testable,
that reports the actual three-point resolution trend (this pass vs. the
batch it replaces vs. the batch seq-12 itself replaced, the last read
best-effort from ``source-restamp-edits.json`` — informational only,
never a hard dependency of this fold; its absence degrades the note, not
the join).

**``content_sha256`` is never touched, never recomputed, never
"verified" here.** Ditjen pages embed a per-request CSRF token, so two
fetches of unchanged content hash differently — there is no
canonical-extraction script in this repo. Verification of those 18
sources is by verbatim quotation (the QW-5 report), not by hash
recomputation. Two independent guarantees, not one: the edit-pair input
schema has no field for content at all (nothing to smuggle even if the
freshness lane tried), AND this fold's own final byte-invariance sweep
(``_assert_untouched``) asserts every restamped record rides through
byte-identical from seq-12 outside ``verified_at``/``verified_by`` — the
same "did anything besides the declared field change" guard every
sibling fold in this family runs, now redundant-by-design rather than
the sole line of defense.

Every input is read from disk at run time. The chain hash is read LIVE
from ``rulepack-prod-012.signed.json`` and asserted against the expected
anchor; the seq-12 source bytes are additionally re-hashed (RFC 8785 JCS)
and must equal that same value — a source/signed mismatch aborts the
fold. Deterministic: fixed timestamps, no ``datetime.now()`` — re-running
is byte-identical. Both input halves are read from disk at fixed paths;
either being absent raises a clear ``FoldPackError``, never an unhandled
crash — the rules-only half ships in PR #4660 (not yet merged as of this
module's authoring) and the freshness half's exact commit path was still
being coordinated directly with its lane as of this module's authoring
(see ``_FRESHNESS_INPUT``'s own comment).

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq13_source
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.models import RulePackPayload

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[2]  # apps/backend-rag/backend
_REPO_ROOT = _THIS_FILE.parents[5]

_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ12_SOURCE = _PACKS_DIR / "rulepack-prod-012.source.json"
_SEQ12_SIGNED = _PACKS_DIR / "rulepack-prod-012.signed.json"
_SEQ13_RULES_ONLY = _PACKS_DIR / "rulepack-prod-013.rules-only.json"
_SEQ13_SOURCE_OUT = _PACKS_DIR / "rulepack-prod-013.source.json"

# Where the s13-fresh lane's re-attestation lands: the edit-pair shape
# (see module docstring), same schema and same directory convention as
# seq-12's own inc5-pack-edits/source-restamp-edits.json, one increment
# later. Matches what is staged (uncommitted) in that lane's own worktree
# at the time this fold was authored — coordinated directly with that
# lane per the team-lead's instruction (this is a two-lane integration
# detail, not something adjudicated from outside). If the committed path
# ends up different, this is the one constant to repoint.
_FRESHNESS_INPUT = (
    _REPO_ROOT
    / "research"
    / "visa"
    / "doctrine-factory"
    / "e5"
    / "inc7-pack-edits"
    / "source-restamp-edits.json"
)

# Informational only, never a hard dependency: seq-12's OWN restamp ledger,
# read purely to report the resolution-trend NOTE (see module docstring).
# Its absence degrades the note (that segment is simply omitted), never the
# join — this path is deliberately not run through `_load_json`'s
# raise-on-missing behavior.
_SEQ12_RESTAMP_HISTORY = (
    _REPO_ROOT
    / "research"
    / "visa"
    / "doctrine-factory"
    / "e5"
    / "inc5-pack-edits"
    / "source-restamp-edits.json"
)

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-13 identity (the uuid5 anchor is verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ13_SEQUENCE = 13
_SEQ13_VERSION = "2026.8.23"
_SEQ13_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/13"
)
_EXPECTED_SEQ13_RULE_PACK_ID = uuid.UUID("79b62b85-829e-59f8-a058-c38c065b8cb5")

# The signed seq-12 payload hash this pack must chain to. Read LIVE from the
# signed file at run time AND asserted equal to this anchor AND equal to the
# recomputed canonical hash of the seq-12 SOURCE bytes — three independent
# derivations of one value, any mismatch aborts. Same anchor
# fold_pack_seq13_rules.py chains against (both halves fold off the same
# seq-12 baseline).
_EXPECTED_SEQ12_PAYLOAD_SHA256 = (
    "ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"
)

# Fixed (not datetime.now()) so re-running this script is byte-identical,
# and so the freshness half's "not in the future" guard has a fixed
# reference rather than depending on wall-clock at run time.
#
# 2026-08-23, corrected: the original value here (20:00:00Z) was picked
# when this module was first written, at ~10:29 UTC that day — already
# ~9.5h in the future at write-time, with no comment justifying the choice.
# It was carried unchanged through every later revision (the NOTE-trend
# fix, the edit-pair schema adopt, the post-merge rebase re-run) because
# it's a hardcoded literal, not a computed value — the two-consecutive-run
# determinism proof this fold reports cannot see this class of defect,
# since a hardcoded wrong value is exactly as deterministic as a hardcoded
# right one. Caught by a reviewer comparing this field to real measured
# UTC, not by anything in this module. Fixed to the most recently-elapsed
# round hour as of actually finalizing this pack (13:54:25Z measured,
# 13:00:00Z chosen so it is unambiguously in the past by the time this
# commits) — matching seq-12's own convention (a nominal round-hour stamp,
# not a measured instant) without repeating the "guessed forward" mistake.
_SEQ13_CREATED_AT = "2026-08-23T13:00:00Z"
_SEQ13_CREATED_BY = "agent.air-m5.backend-rag.visa-seq13-source-join.fold-2026-08-23"

# Drift tripwire on the restamp batch size — same convention as seq-12's
# fold: a different count means this fold was authored against a different
# world and must abort, not adapt.
_EXPECTED_RESTAMP_COUNT = 18
_PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)
_RESTAMP_FIELDS = frozenset({"verified_at", "verified_by"})
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path, *, what: str) -> Any:
    if not path.exists():
        raise FoldPackError(
            f"{what} not found at {path} — this join cannot run without it. "
            "Merge/land that lane's artifact first, then re-run this fold."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _historical_restamp_distinct_count(record_ids: set[str]) -> int | None:
    """Best-effort, informational only: how many distinct ``verified_at``
    values the batch seq-12 ITSELF replaced (``source-restamp-edits.json``'s
    own ``current_verified_at`` — inherited from seq-10/seq-11) carried,
    restricted to ``record_ids``. Returns ``None`` on anything short of a
    clean read (missing file, unexpected shape, empty overlap) — this feeds
    the resolution-trend NOTE only, never a guard, and must never become a
    third hard dependency of this fold."""

    try:
        if not _SEQ12_RESTAMP_HISTORY.exists():
            return None
        data = json.loads(_SEQ12_RESTAMP_HISTORY.read_text(encoding="utf-8"))
        values = {
            e["current_verified_at"]
            for e in data["restamps"]
            if e.get("source_record_id") in record_ids
        }
        return len(values) if values else None
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _parse_utc(value: str) -> datetime:
    try:
        return datetime.strptime(value, _UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise FoldPackError(f"timestamp {value!r} is not the fixed UTC shape {_UTC_FORMAT!r}") from exc


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ13_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ13_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-13 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ13_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ13_RULE_PACK_ID} — do not hand-adjust either side"
        )
    return computed


def _chain_hash(seq12_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ12_SIGNED, what="rulepack-prod-012.signed.json")
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ12_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ12_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ12_PAYLOAD_SHA256!r} — the signed seq-12 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-12 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


def _apply_identity(payload: dict[str, Any], seq12_source: dict[str, Any]) -> None:
    payload["sequence"] = _SEQ13_SEQUENCE
    payload["version"] = _SEQ13_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = _chain_hash(seq12_source)
    payload["created_at"] = _SEQ13_CREATED_AT
    payload["created_by"] = _SEQ13_CREATED_BY
    # rollback_of_payload_sha256 stays null; top-level valid_period untouched
    # (not in _IDENTITY_KEYS, so the byte-invariance sweep asserts it equals
    # seq-12's).


# ---------------------------------------------------------------------------
# Rules half — taken wholesale, cross-checked that it kept its own promise
# ---------------------------------------------------------------------------


def _apply_rules(payload: dict[str, Any], seq12_source: dict[str, Any]) -> dict[str, Any]:
    rules_only = _load_json(_SEQ13_RULES_ONLY, what="rulepack-prod-013.rules-only.json")

    # The rules-only fold's own docstring promises it changes NOTHING but
    # `rules` — identity stays at seq-12's own values, products and
    # source_records are untouched. Verify that promise was kept before
    # trusting its `rules` at all: a rules-only artifact that silently
    # smuggled a product or source_record edit must abort here, not ride
    # into the combined pack disguised as "the rules half".
    for key in _IDENTITY_KEYS:
        if rules_only.get(key) != seq12_source.get(key):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's {key!r} = "
                f"{rules_only.get(key)!r} differs from seq-12's {seq12_source.get(key)!r} "
                "— the rules-only fold declares no identity change; this artifact "
                "does not match its own contract"
            )
    for key in ("products", "source_records"):
        if _canon(rules_only.get(key)) != _canon(seq12_source.get(key)):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's {key!r} drifted from seq-12 — "
                "the rules-only lane owns neither products nor source_records; "
                "this join refuses to inherit a change outside that lane's own "
                "declared territory"
            )
    for key in set(seq12_source) | set(rules_only):
        if key in _IDENTITY_KEYS or key in ("rules", "products", "source_records"):
            continue
        if _canon(rules_only.get(key)) != _canon(seq12_source.get(key)):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's top-level key {key!r} drifted "
                "from seq-12 outside its declared rules-only edit"
            )

    payload["rules"] = copy.deepcopy(rules_only["rules"])
    return rules_only


# ---------------------------------------------------------------------------
# Freshness half — 18-record OFFICIAL_PORTAL restamp, entity-derived
# ---------------------------------------------------------------------------


#: The only top-level keys the edit-pair freshness input may carry. A
#: whitelist, not a blacklist: any key outside this set — including,
#: but not limited to, a "rules"/"products" fragment that would smuggle
#: a change outside the freshness lane's territory — aborts the fold.
_FRESHNESS_INPUT_ALLOWED_KEYS = frozenset({"_comment", "restamps"})

#: The exact fields one restamp edit in the edit-pair shape carries —
#: verified against the REAL inc5/inc7 files on disk (not assumed from a
#: routing message): 7 fields, not 5. ``source_key``/``field`` are
#: descriptive metadata this fold cross-checks (entity consistency /
#: scope), not merely tolerated passthrough. Extra or missing keys abort
#: — a whitelist so a future accidental field (e.g. a stray
#: content_sha256) is caught by construction, not by remembering to check
#: for it.
_RESTAMP_EDIT_FIELDS = frozenset(
    {
        "source_record_id",
        "source_key",
        "field",
        "current_verified_at",
        "current_verified_by",
        "new_verified_at",
        "new_verified_by",
    }
)
_RESTAMP_EDIT_EXPECTED_FIELD_VALUE = "verified_at+verified_by"


def _apply_freshness(payload: dict[str, Any], seq12_source: dict[str, Any]) -> set[str]:
    freshness = _load_json(_FRESHNESS_INPUT, what="seq-13 freshness restamp JSON")

    extra_keys = set(freshness) - _FRESHNESS_INPUT_ALLOWED_KEYS
    if extra_keys:
        raise FoldPackError(
            f"the freshness input declares unexpected top-level key(s) {sorted(extra_keys)} "
            f"— only {sorted(_FRESHNESS_INPUT_ALLOWED_KEYS)} are allowed in the edit-pair "
            "shape; refusing to consume a change outside the freshness lane's territory"
        )

    records = freshness.get("restamps")
    if records is None:
        raise FoldPackError("freshness input is missing 'restamps'")
    if len(records) != _EXPECTED_RESTAMP_COUNT:
        raise FoldPackError(
            f"expected exactly {_EXPECTED_RESTAMP_COUNT} restamps, freshness input "
            f"carries {len(records)}"
        )

    for edit in records:
        extra = set(edit) - _RESTAMP_EDIT_FIELDS
        missing = _RESTAMP_EDIT_FIELDS - set(edit)
        if extra or missing:
            raise FoldPackError(
                f"restamp edit {edit.get('source_record_id')!r} has "
                f"{'unexpected field(s) ' + str(sorted(extra)) if extra else ''}"
                f"{' and ' if extra and missing else ''}"
                f"{'missing field(s) ' + str(sorted(missing)) if missing else ''} "
                f"— must carry exactly {sorted(_RESTAMP_EDIT_FIELDS)}"
            )

    payload_records_by_id = {r["source_record_id"]: r for r in payload["source_records"]}

    # Entity check, not a frozen id list — the restamped set must be exactly
    # the set of OFFICIAL_PORTAL records already in the payload (seq-12's,
    # untouched at this point). The seq-12 pattern, one generation later.
    portal_ids = {
        sid
        for sid, r in payload_records_by_id.items()
        if r.get("authority_type") == _PORTAL_AUTHORITY_TYPE
    }
    restamp_ids = {r["source_record_id"] for r in records}
    if len(restamp_ids) != len(records):
        raise FoldPackError("freshness input names a duplicate source_record_id")
    if restamp_ids != portal_ids:
        missing_ids = sorted(portal_ids - restamp_ids)
        extra_ids = sorted(restamp_ids - portal_ids)
        raise FoldPackError(
            "freshness restamp set is not exactly the OFFICIAL_PORTAL set — "
            f"portal records not restamped: {missing_ids}; "
            f"restamps naming non-portal/unknown records: {extra_ids}"
        )

    created_at_dt = _parse_utc(_SEQ13_CREATED_AT)
    new_stamps: list[str] = []
    replaced_stamps: list[str] = []

    for edit in records:
        sid = edit["source_record_id"]
        baseline = payload_records_by_id.get(sid)
        if baseline is None:
            raise FoldPackError(f"freshness restamp names unknown source_record_id {sid!r}")

        if edit["field"] != _RESTAMP_EDIT_EXPECTED_FIELD_VALUE:
            raise FoldPackError(
                f"restamp edit {sid!r} declares field={edit['field']!r}, expected "
                f"{_RESTAMP_EDIT_EXPECTED_FIELD_VALUE!r} — this fold only ever restamps "
                "verified_at+verified_by; any other declared field is out of scope"
            )
        if edit["source_key"] != baseline.get("source_key"):
            raise FoldPackError(
                f"restamp edit {sid!r} declares source_key={edit['source_key']!r}, but "
                f"seq-12's actual record {sid!r} has source_key={baseline.get('source_key')!r} "
                "— id/key mismatch, refusing to apply against the wrong record"
            )

        current_verified_at = edit["current_verified_at"]
        current_verified_by = edit["current_verified_by"]

        # Ledger-drift guard: the edit-pair's declared "current" value must
        # match seq-12's ACTUAL bytes — this is the exact strengthening the
        # edit-pair shape buys over a full-record blob (team-lead, on
        # adopting this contract): a claim about what is being replaced,
        # checked against reality, not merely trusted.
        if baseline.get("verified_at") != current_verified_at or baseline.get("verified_by") != current_verified_by:
            raise FoldPackError(
                f"source_record {sid!r}: seq-12's actual verified_at/verified_by "
                f"({baseline.get('verified_at')!r}, {baseline.get('verified_by')!r}) does not "
                f"match the freshness input's declared current value ({current_verified_at!r}, "
                f"{current_verified_by!r}) — ledger drift, refusing to apply blind"
            )

        new_verified_at = edit["new_verified_at"]
        new_verified_by = edit["new_verified_by"]

        new_dt = _parse_utc(new_verified_at)
        current_dt = _parse_utc(current_verified_at)
        if not new_dt > current_dt:
            raise FoldPackError(
                f"source_record {sid!r}: new verified_at {new_verified_at!r} does not "
                f"advance past the current {current_verified_at!r} — a re-stamp that moves "
                "time backward or holds it still is not an attestation"
            )
        if new_dt > created_at_dt:
            raise FoldPackError(
                f"source_record {sid!r}: new verified_at {new_verified_at!r} is after "
                f"this pack's own created_at {_SEQ13_CREATED_AT!r} — a re-stamp cannot "
                "attest to a fetch that (per this pack's own clock) hasn't happened yet"
            )

        # content_sha256 and every other field are untouched BY
        # CONSTRUCTION here — the edit-pair schema has no slot for them,
        # and only these two fields are ever assigned onto `baseline`.
        # No comparison is needed; there is nothing for the input to have
        # smuggled. `_assert_untouched` below re-derives the same
        # guarantee independently from the final payload, for defense in
        # depth against a bug in THIS function.
        baseline["verified_at"] = new_verified_at
        baseline["verified_by"] = new_verified_by
        new_stamps.append(new_verified_at)
        replaced_stamps.append(current_verified_at)

    # FLAGGED, not rejected — see module docstring for the reasoning. A
    # batch of identical-to-the-second stamps is a disclosed pass-level
    # proxy, not per-source observation; the per-record guards above
    # (advance + not-future + ledger-drift) are the actual evidentiary
    # teeth, not timestamp cardinality. But this fold family's resolution
    # has been getting COARSER, not holding steady — report the trend, not
    # just the current number, so a reader sees the coarsening rather than
    # mistaking a prior degradation for an established convention.
    current_distinct = len(set(new_stamps))
    if current_distinct < len(new_stamps):
        replaced_distinct = len(set(replaced_stamps))
        historical_distinct = _historical_restamp_distinct_count(restamp_ids)

        trend = [f"{current_distinct} now"]
        trend.append(f"{replaced_distinct} in the batch this replaces (seq-12's own restamp)")
        if historical_distinct is not None:
            trend.append(
                f"{historical_distinct} in the batch seq-12 itself replaced "
                "(inherited from seq-10/seq-11, real second-precision per-fetch times)"
            )

        print(
            f"NOTE: {len(new_stamps)} freshness restamps carry only {current_distinct} "
            "distinct verified_at value(s) — a disclosed pass-level proxy timestamp, "
            "not independently observed per-source fetch times. Flagged, not rejected: "
            "a script cannot manufacture per-source fetch times that were never "
            "captured. But this is a DESCENDING resolution trend, not a stable "
            f"convention — distinct-verified_at-count, newest first: {' <- '.join(trend)}. "
            "What good looks like is the oldest figure in that chain, not the most "
            "recent one. Evidentiary backing for each source is the QW-5 "
            "verbatim-quote report, not timestamp cardinality — but the coarsening "
            "itself is worth naming, not just excusing.",
            file=sys.stderr,
        )

    return restamp_ids


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-12
# ---------------------------------------------------------------------------


def _assert_untouched(
    payload: dict[str, Any], seq12: dict[str, Any], restamped_ids: set[str]
) -> None:
    for key in set(seq12) | set(payload):
        if key in _IDENTITY_KEYS or key in ("rules", "source_records"):
            continue
        if _canon(payload.get(key)) != _canon(seq12.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-12 — this join "
                "declares no edit there"
            )

    seq12_records = {r["source_record_id"]: r for r in seq12["source_records"]}
    new_records = {r["source_record_id"]: r for r in payload["source_records"]}
    if set(new_records) != set(seq12_records):
        raise FoldPackError(
            "source_record set (by source_record_id) drifted from seq-12 — this "
            "join declares no record add/remove/drop"
        )
    for sid, record in new_records.items():
        baseline = seq12_records[sid]
        if sid in restamped_ids:
            b = {k: v for k, v in baseline.items() if k not in _RESTAMP_FIELDS}
            c = {k: v for k, v in record.items() if k not in _RESTAMP_FIELDS}
            if _canon(b) != _canon(c):
                raise FoldPackError(
                    f"source_record {sid!r} changed beyond verified_at/verified_by "
                    "— content_sha256 and every other field must ride through "
                    "untouched on a pure re-stamp"
                )
        elif _canon(record) != _canon(baseline):
            raise FoldPackError(
                f"source_record {sid!r} drifted from seq-12 outside the declared "
                "restamp set"
            )


# ---------------------------------------------------------------------------
# Write (atomic + prettier — fold_pack.py's Codex-finding-7 shape)
# ---------------------------------------------------------------------------


def _write_pack(payload: dict[str, Any], out_path: Path) -> None:
    if not _PRETTIER_BIN.exists():
        raise FoldPackError(
            f"prettier binary not found at {_PRETTIER_BIN} — run `npm install` at repo root"
        )

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{out_path.stem}.tmp.", suffix=out_path.suffix, dir=str(out_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        result = subprocess.run(
            [str(_PRETTIER_BIN), "--write", str(tmp_path)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise FoldPackError(
                f"prettier --write {tmp_path} failed (rc={result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
        tmp_path.replace(out_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def assemble_payload() -> dict[str, Any]:
    seq12_original = _load_json(_SEQ12_SOURCE, what="rulepack-prod-012.source.json")
    payload = copy.deepcopy(seq12_original)

    _apply_identity(payload, seq12_original)
    _apply_rules(payload, seq12_original)
    restamped_ids = _apply_freshness(payload, seq12_original)
    _assert_untouched(payload, seq12_original, restamped_ids)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-13 payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ13_SOURCE_OUT)
    print(
        f"wrote {_SEQ13_SOURCE_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Visa Freshness Sentinel — alerts Telegram BEFORE an active Visa Oracle
RulePack's OFFICIAL_PORTAL source stamps cross their freshness_policy
window (7-day for the live seq-11+ portal sources), so production never
silently trips DECISIVE_SOURCE_STALE (which folds every decision into
HUMAN_REVIEW abstain — "the oracle goes mute").

This is the structural half of an owner ruling: the weekly re-attestation
lane RE-STAMPS sources; this sentinel guarantees a missed week cannot pass
silently (superscar family #2, "esiste != armato" — built-but-unarmed and
armed-but-blind are the same failure).

Freshness semantics mirrored EXACTLY from the engine, so the sentinel and
the engine never disagree about the instant staleness begins:
    apps/backend-rag/backend/services/visa_engine/evaluate_path.py:551-598
    (`_evaluate_source_freshness`) — INCLUSIVE boundary: CURRENT through
    exactly verified_at + max_age_seconds, STALE strictly after. Whole-second
    age math (no float rounding). See `_is_current()` below.

ACTIVE-pack truth is a Postgres bitemporal join, NOT the filesystem:
    apps/backend-rag/backend/services/visa_engine/repository.py:185-253
    (`VisaEngineRepository.load_active_rule_pack`) — the activation whose
    legal_period contains effective_at AND system_period contains
    observed_at. `_fetch_active_pack_from_db()` replicates that SELECT
    read-only (never writes, never verifies signatures — that is the
    service layer's job, not this sentinel's).

FALLBACK (declared proxy, cicatrix W106b — "the checkout is a proxy of
what the repo says, and mentions it must NAME itself as a proxy, not
silently pass as truth"): if the DB is unreachable, `_fetch_active_pack_from_repository()`
MAY fall back to the highest-sequence signed PRODUCTION pack on disk,
mimicking (without its cryptography/pydantic dependencies — this script
runs under cron's bare python3, stdlib only):
    apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py:274-296
    (`select_highest_repository_pack`)
Every verdict built from that fallback is labelled "repository highest-
signed pack (proxy), not proven active" in both `Verdict.reason` and the
Telegram alert text. Never silently presented as the DB truth.

DB unreachable is its own outcome, CANNOT_VERIFY (digest tier, never p0) —
never a false "approaching stale" and never a silent green. Offline is a
natural state (SYMBIOSIS Law 6); a sentinel that cries stale when the truth
is cannot-check burns trust exactly like the drive-token watchdog's old
day-ladder did (`scripts/drive_token_watchdog.py`'s module docstring).

Telegram: ONLY via the gateway `scripts/tg_notify.py`, exact house pattern
of `scripts/drive_token_watchdog.py::_send_telegram` (subprocess + verdict
read via `scripts/tg_gateway_verdict.extract_gateway_verdict`). This file
must NEVER contain the literal Telegram API domain string — see
`scripts/lint_tg_direct_senders.py`.

Usage:
    python3 scripts/visa_freshness_sentinel.py                 # full run
    python3 scripts/visa_freshness_sentinel.py --dry-run        # verdict JSON only, no Telegram
    python3 scripts/visa_freshness_sentinel.py --now 2026-08-27T00:00:00Z  # TEST-ONLY clock override

Exit codes:
    0 — OK, APPROACHING, or NO_PORTAL_RECORDS (alert delivered as designed)
    1 — STALE found (at least one OFFICIAL_PORTAL source past its boundary)
    2 — CANNOT_VERIFY (neither the DB nor the repository fallback answered)
A gateway failure NEVER raises — it is logged and swallowed, matching the
house contract that `tg_notify.py` itself never fails its caller.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tg_gateway_verdict import extract_gateway_verdict  # noqa: E402

logger = logging.getLogger("visa_freshness_sentinel")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Wire vocabulary — apps/backend-rag/backend/services/visa_engine/enums.py
PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"
ENVIRONMENT = "PRODUCTION"
JURISDICTION = "ID"
DECISION_DOMAIN = "IMMIGRATION_VISA"
FRESHNESS_POLICY_KIND = "MAX_AGE_SINCE_VERIFIED_AT"

DEFAULT_WARN_SECONDS = 48 * 3600  # 48h Telegram warning window (spec)

PACKS_DIR = (
    PROJECT_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
PG_SH = PROJECT_ROOT / "scripts" / "pg.sh"
TG_NOTIFY = PROJECT_ROOT / "scripts" / "tg_notify.py"

# Outcomes
OUTCOME_OK = "OK"
OUTCOME_ANOMALY = "ANOMALY"
OUTCOME_APPROACHING = "APPROACHING"
OUTCOME_STALE = "STALE"
OUTCOME_NO_PORTAL_RECORDS = "NO_PORTAL_RECORDS"
OUTCOME_CANNOT_VERIFY = "CANNOT_VERIFY"

# The single read-only SELECT this sentinel is allowed to run — a byte-for-byte
# mirror of repository.py::load_active_rule_pack's WHERE clause (see module
# docstring), except it asks the DB for `now()` on BOTH bitemporal clocks
# (this sentinel asks "what is active RIGHT NOW", never a historical instant)
# and projects only what freshness classification needs, never protected/
# signature columns.
_ACTIVE_PACK_SQL = (
    "SELECT jsonb_build_object("
    "'sequence', (p.payload->>'sequence')::bigint, "
    "'version', p.payload->>'version', "
    "'source_records', p.payload->'source_records'"
    ")::text "
    "FROM visa_ruleset_activations a "
    "JOIN visa_rule_packs p ON p.id = a.rule_pack_id "
    f"WHERE a.environment = '{ENVIRONMENT}' "
    f"  AND a.jurisdiction = '{JURISDICTION}' "
    f"  AND a.decision_domain = '{DECISION_DOMAIN}' "
    "  AND a.legal_period @> now() "
    "  AND a.system_period @> now() "
    "ORDER BY a.created_at DESC "
    "LIMIT 1;"
)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse_utc(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (with or without a trailing 'Z') to an
    aware UTC datetime. Returns None (never raises) on anything unparseable —
    an unparseable timestamp is a fact the caller must report, not a crash."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_current(verified_at: datetime, max_age_seconds: int, now: datetime) -> bool:
    """Mirror `evaluate_path._evaluate_source_freshness`'s inclusive boundary
    EXACTLY (evaluate_path.py:582-587): CURRENT through exactly
    verified_at + max_age_seconds inclusive, STALE strictly after. Whole-
    second age math (no float rounding) — the semantic anchor this whole
    sentinel exists to never disagree with.
    """
    age = now - verified_at
    age_whole_seconds = age.days * 86_400 + age.seconds
    return age_whole_seconds < max_age_seconds or (
        age_whole_seconds == max_age_seconds and age.microseconds == 0
    )


# ---------------------------------------------------------------------------
# Verdict data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFinding:
    """One OFFICIAL_PORTAL source record that is STALE or APPROACHING."""

    source_record_id: str
    title: str
    verified_at: datetime
    max_age_seconds: int
    boundary: datetime  # verified_at + max_age_seconds

    @property
    def short_id(self) -> str:
        return self.source_record_id[:8]

    def to_json(self) -> dict[str, Any]:
        return {
            "source_record_id": self.source_record_id,
            "short_id": self.short_id,
            "title": self.title,
            "verified_at": self.verified_at.isoformat(),
            "max_age_seconds": self.max_age_seconds,
            "boundary": self.boundary.isoformat(),
        }


@dataclass(frozen=True)
class SourceAnomaly:
    """A portal source the sentinel could not classify as CURRENT/STALE at
    all — mirrors the engine's UNKNOWN posture (never silently CURRENT)."""

    source_record_id: str
    title: str
    reason_code: str
    detail: str = ""

    @property
    def short_id(self) -> str:
        return self.source_record_id[:8]

    def to_json(self) -> dict[str, Any]:
        return {
            "source_record_id": self.source_record_id,
            "short_id": self.short_id,
            "title": self.title,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Verdict:
    outcome: str
    now: datetime
    warn_seconds: int
    portal_total: int = 0
    stale: tuple[SourceFinding, ...] = ()
    approaching: tuple[SourceFinding, ...] = ()
    policy_missing: tuple[SourceAnomaly, ...] = ()
    future_verified: tuple[SourceAnomaly, ...] = ()
    pack_sequence: int | None = None
    pack_version: str | None = None
    pack_source: str = "unknown"  # "database" | "repository-fallback" | "unknown"
    reason: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "now": self.now.isoformat(),
            "warn_seconds": self.warn_seconds,
            "portal_total": self.portal_total,
            "stale": [f.to_json() for f in self.stale],
            "approaching": [f.to_json() for f in self.approaching],
            "policy_missing": [a.to_json() for a in self.policy_missing],
            "future_verified": [a.to_json() for a in self.future_verified],
            "pack_sequence": self.pack_sequence,
            "pack_version": self.pack_version,
            "pack_source": self.pack_source,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Pure classification core — no I/O, fully unit-testable
# ---------------------------------------------------------------------------


def classify_freshness(
    source_records: list[dict[str, Any]],
    now: datetime,
    warn_seconds: int = DEFAULT_WARN_SECONDS,
) -> Verdict:
    """Classify an active pack's OFFICIAL_PORTAL sources against `now`.

    Outcomes:
      STALE              any portal record already past its inclusive
                          boundary (CRITICAL, p0)
      APPROACHING         any portal record within `warn_seconds` of its
                          boundary, none yet stale (p0)
      OK                  none within the window
      NO_PORTAL_RECORDS   zero OFFICIAL_PORTAL records were scanned — a
                          blind-scan FAILURE state (cicatrix W84: "zero
                          traversed != clean"), never reported as OK

    A record lacking `freshness_policy`, or with an unparseable/missing
    `verified_at`, is reported in `policy_missing` (the engine treats these
    as UNKNOWN, never implicitly CURRENT — evaluate_path.py:573-580). A
    record whose `verified_at` is in the future is reported in
    `future_verified` (mirrors `SOURCE_VERIFIED_AT_IN_FUTURE`,
    evaluate_path.py:565-572) and is NEVER counted as STALE.
    """
    if now.tzinfo is None:
        raise ValueError("classify_freshness: `now` must be timezone-aware (UTC)")

    portal_records = [
        r for r in source_records if r.get("authority_type") == PORTAL_AUTHORITY_TYPE
    ]
    portal_total = len(portal_records)

    if portal_total == 0:
        return Verdict(
            outcome=OUTCOME_NO_PORTAL_RECORDS,
            now=now,
            warn_seconds=warn_seconds,
            portal_total=0,
            reason=(
                "zero OFFICIAL_PORTAL source_records in the active pack — "
                "blind-scan failure state, never read as clean (cicatrix W84)"
            ),
        )

    stale: list[SourceFinding] = []
    approaching: list[SourceFinding] = []
    policy_missing: list[SourceAnomaly] = []
    future_verified: list[SourceAnomaly] = []

    for record in portal_records:
        record_id = str(record.get("source_record_id", "?"))
        title = str(record.get("title", "?"))

        verified_at = _parse_utc(record.get("verified_at"))
        if verified_at is None:
            policy_missing.append(
                SourceAnomaly(
                    record_id,
                    title,
                    "VERIFIED_AT_UNREADABLE",
                    f"raw={record.get('verified_at')!r}",
                )
            )
            continue

        # Future-verified check FIRST, mirroring evaluate_path.py's own
        # ordering (:565 checks `verified_at > evaluated_at` before it ever
        # looks at the policy).
        if verified_at > now:
            future_verified.append(
                SourceAnomaly(
                    record_id, title, "SOURCE_VERIFIED_AT_IN_FUTURE",
                    f"verified_at={verified_at.isoformat()} now={now.isoformat()}",
                )
            )
            continue

        policy = record.get("freshness_policy")
        if not isinstance(policy, dict) or policy.get("kind") != FRESHNESS_POLICY_KIND:
            policy_missing.append(
                SourceAnomaly(record_id, title, "FRESHNESS_POLICY_NOT_DEFINED")
            )
            continue

        max_age_seconds = policy.get("max_age_seconds")
        if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 1:
            policy_missing.append(
                SourceAnomaly(
                    record_id, title, "FRESHNESS_POLICY_MALFORMED",
                    f"max_age_seconds={max_age_seconds!r}",
                )
            )
            continue

        boundary = verified_at + timedelta(seconds=max_age_seconds)

        if _is_current(verified_at, max_age_seconds, now):
            remaining = boundary - now
            if remaining <= timedelta(seconds=warn_seconds):
                approaching.append(
                    SourceFinding(record_id, title, verified_at, max_age_seconds, boundary)
                )
        else:
            stale.append(
                SourceFinding(record_id, title, verified_at, max_age_seconds, boundary)
            )

    if stale:
        outcome = OUTCOME_STALE
    elif approaching:
        outcome = OUTCOME_APPROACHING
    elif policy_missing or future_verified:
        # An anomaly must never resolve to OK. Both of these branches `continue`
        # above — a record with no readable freshness_policy, or a verified_at in
        # the future, enters NEITHER `stale` NOR `approaching` — so before this
        # clause existed the outcome fell through to OK and `send_alert`'s
        # `if outcome == OUTCOME_OK: return None` dropped the finding before
        # `format_alert_text` (which has always printed these counts) was ever
        # called. A pack that lost its freshness_policy on every portal record
        # therefore reported OK and sent nothing, while the engine treated those
        # same records as UNKNOWN. Cicatrix #2 (green silence) crossed with #3's
        # under-match twin: the alarm watched two of the four ways a pack can be
        # unfit to decide. Ranked below APPROACHING because a live deadline is
        # the more urgent fact when both are true; the anomalies are still
        # printed in that alert's body either way.
        outcome = OUTCOME_ANOMALY
    else:
        outcome = OUTCOME_OK

    return Verdict(
        outcome=outcome,
        now=now,
        warn_seconds=warn_seconds,
        portal_total=portal_total,
        stale=tuple(stale),
        approaching=tuple(approaching),
        policy_missing=tuple(policy_missing),
        future_verified=tuple(future_verified),
    )


# ---------------------------------------------------------------------------
# Active pack acquisition — DB primary, repository fallback (declared proxy)
# ---------------------------------------------------------------------------


def _resolve_database_url() -> str | None:
    return os.environ.get("VISA_SENTINEL_DATABASE_URL", "").strip() or None


def _fetch_active_pack_from_db() -> tuple[dict[str, Any] | None, str | None]:
    """Query the ACTIVE pack's payload from Postgres (read-only).

    Returns `(payload, failure_reason)` — exactly one of the two is non-None.
    `VISA_SENTINEL_DATABASE_URL` overrides the connection; otherwise this
    shells out to `scripts/pg.sh` (the one-true-way, cicatrix W87) rather than
    reimplementing its Keychain/proxy dance — this script never embeds or
    reads a credential itself.
    """
    dsn = _resolve_database_url()
    if dsn:
        cmd = ["psql", dsn, "-t", "-A", "-c", _ACTIVE_PACK_SQL]
    elif PG_SH.is_file():
        cmd = [str(PG_SH), "-t", "-A", "-c", _ACTIVE_PACK_SQL]
    else:
        return None, (
            f"no DB access path: VISA_SENTINEL_DATABASE_URL unset and "
            f"{PG_SH} not found"
        )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as exc:  # noqa: BLE001 — the reason is reported, never guessed (W106)
        return None, f"{type(exc).__name__}: {exc}"

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().replace("\n", " ")[:200]
        return None, f"query failed (exit {proc.returncode}): {detail or '(no output)'}"

    output = proc.stdout.strip()
    if not output:
        return None, (
            "no ACTIVE pack row matched the bitemporal join "
            "(legal_period/system_period @> now())"
        )

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return None, f"unparseable payload from DB: {exc}"

    return payload, None


def _fetch_active_pack_from_repository() -> tuple[dict[str, Any] | None, str | None]:
    """FALLBACK (declared proxy, cicatrix W106b): the highest-sequence signed
    PRODUCTION pack on disk. Mirrors
    `gold_replay_driver.py::select_highest_repository_pack`'s selection rule
    WITHOUT its cryptography/pydantic dependencies — this script is stdlib
    only (cron's bare python3). Never signature-verified here; the caller
    MUST label this state as a proxy, never as proven-active.
    """
    if not PACKS_DIR.is_dir():
        return None, f"packs dir not found: {PACKS_DIR}"

    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in sorted(PACKS_DIR.glob("*.signed.json")):
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skipping unreadable pack %s: %s", path.name, exc)
            continue
        payload = raw.get("payload")
        if not isinstance(payload, dict) or payload.get("environment") != ENVIRONMENT:
            continue
        sequence = payload.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            continue
        candidates.append((sequence, path, payload))

    if not candidates:
        return None, f"no signed PRODUCTION packs found in {PACKS_DIR}"

    highest_sequence = max(seq for seq, _, _ in candidates)
    highest = [c for c in candidates if c[0] == highest_sequence]
    if len(highest) != 1:
        paths = ", ".join(str(p) for _, p, _ in highest)
        return None, (
            f"multiple signed PRODUCTION packs share highest sequence "
            f"{highest_sequence}: {paths}"
        )

    _, path, payload = highest[0]
    return {
        "sequence": payload.get("sequence"),
        "version": payload.get("version"),
        "source_records": payload.get("source_records", []),
        "_repository_path": path.name,
    }, None


def _resolve_pack() -> tuple[dict[str, Any] | None, str, str | None]:
    """Returns `(payload, source, failure_reason)`.

    `source` is `"database"` or `"repository-fallback"` on success, or
    `"unknown"` when both paths failed (caller emits CANNOT_VERIFY).
    """
    payload, db_error = _fetch_active_pack_from_db()
    if payload is not None:
        return payload, "database", None

    payload, repo_error = _fetch_active_pack_from_repository()
    if payload is not None:
        logger.warning(
            "DB unreachable (%s) — falling back to repository highest-signed "
            "pack (proxy, not proven active)", db_error,
        )
        return payload, "repository-fallback", None

    return None, "unknown", f"DB: {db_error}; repository fallback: {repo_error}"


def build_verdict(now: datetime, warn_seconds: int = DEFAULT_WARN_SECONDS) -> Verdict:
    """Acquire the active pack and classify it. Never raises on I/O failure —
    that becomes CANNOT_VERIFY, never a crash and never a silent green."""
    payload, source, failure = _resolve_pack()
    if payload is None:
        return Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            now=now,
            warn_seconds=warn_seconds,
            pack_source="unknown",
            reason=failure or "no pack available from any source",
        )

    source_records = payload.get("source_records") or []
    verdict = classify_freshness(source_records, now, warn_seconds)

    reason = verdict.reason
    if source == "repository-fallback":
        proxy_note = "repository highest-signed pack (proxy), not proven active"
        reason = f"{reason} — {proxy_note}" if reason else proxy_note

    return dataclasses.replace(
        verdict,
        pack_sequence=payload.get("sequence"),
        pack_version=payload.get("version"),
        pack_source=source,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Alert text + dedup key
# ---------------------------------------------------------------------------


def urgency_buckets(warn_seconds: int) -> tuple[int, ...]:
    """Hour-wide urgency buckets, DERIVED from the warning window: W, W/2, W/4, W/8.

    Derived rather than hardcoded on purpose. A literal ``(48, 24, 12, 6)`` is
    correct only while ``warn_seconds`` is 48h: raise the window to 72h and the
    72→48h span collapses into a single key, re-opening the very gap the bucket
    exists to close. Duplicates are dropped (a tiny window can fold levels
    together) and the sequence stays strictly descending.
    """
    hours = max(1, warn_seconds // 3600)
    out: list[int] = []
    for divisor in (1, 2, 4, 8):
        bucket = max(1, hours // divisor)
        if bucket not in out:
            out.append(bucket)
    return tuple(out)


def approaching_bucket(verdict: Verdict) -> int:
    """The TIGHTEST urgency bucket the nearest boundary still sits inside.

    An APPROACHING verdict carrying no findings is incoherent, but it must not
    raise here: this runs inside the alert path, and the house contract is that a
    formatting fault never costs the alert (`send_alert` swallows gateway errors
    for the same reason). Degrade to the widest bucket — a stable key that still
    sends — rather than crashing on an empty ``min()``.
    """
    buckets = urgency_buckets(verdict.warn_seconds)
    if not verdict.approaching:
        return buckets[0]
    remaining_h = min(
        (f.boundary - verdict.now).total_seconds() / 3600 for f in verdict.approaching
    )
    tightest = buckets[-1]
    for bucket in buckets:
        if remaining_h <= bucket:
            tightest = bucket
    return tightest


def dedup_key(verdict: Verdict) -> str:
    """Per-CONDITION, stable dedup key (never a raw measurement — W104/#2).

    APPROACHING is the one outcome whose key also carries URGENCY, because it is
    the one outcome with a deadline running against it. The gateway's mute ladder
    climbs 6h → 24h → 72h → 168h per surviving repeat, while the warning window
    is only 48h: at streak 3 the silence (72h) outlasts the entire window, so a
    warning could be muted straight through the boundary it exists to announce.
    Crossing into a tighter bucket mints a brand-new key at streak 0, which sends
    immediately; inside one bucket the ladder still does its anti-spam job.

    A bucket can be skipped entirely if launchd runs late — the guarantee is
    "every bucket ENTERED fires", not "every bucket fires", which is the one that
    matters. This deliberately reintroduces a moving producer key, which the
    gateway's own docstring names as an anti-pattern; it is justified here by the
    deadline and must not be copied to a consumer without one.
    """
    seq = verdict.pack_sequence if verdict.pack_sequence is not None else "unknown"
    # An anomaly that appears while the pack is ALREADY stale or approaching does
    # not get its own outcome — it rides along in the alert body. Without this
    # suffix it would also not get its own key, so if the stale/approaching key
    # were already muted by the ladder, the new information would be swallowed
    # and nobody would learn the pack had also become un-ageable. Adding the
    # marker mints a fresh key at the moment anomalies first appear alongside a
    # deadline condition. (Found by the cross-family refuter on this diff.)
    anomalous = ":anom" if (verdict.policy_missing or verdict.future_verified) else ""
    if verdict.outcome == OUTCOME_STALE:
        return f"visa-freshness:stale:{seq}{anomalous}"
    if verdict.outcome == OUTCOME_APPROACHING:
        return f"visa-freshness:approaching:{seq}:t{approaching_bucket(verdict)}{anomalous}"
    if verdict.outcome == OUTCOME_ANOMALY:
        return f"visa-freshness:anomaly:{seq}"
    if verdict.outcome == OUTCOME_NO_PORTAL_RECORDS:
        return f"visa-freshness:no-portal-records:{seq}"
    return "visa-freshness:cannot-verify"


def format_alert_text(verdict: Verdict) -> str:
    lines: list[str] = []
    header = f"Visa Oracle freshness sentinel — pack seq={verdict.pack_sequence} version={verdict.pack_version}"
    if verdict.pack_source == "repository-fallback":
        header += " [repository highest-signed pack (proxy), not proven active]"
    lines.append(header)

    if verdict.outcome == OUTCOME_STALE:
        lines.append(
            f"STALE: {len(verdict.stale)} OFFICIAL_PORTAL source(s) past their "
            "freshness boundary."
        )
        for f in sorted(verdict.stale, key=lambda x: x.boundary)[:10]:
            lines.append(f"  - {f.short_id} \"{f.title[:60]}\" boundary={f.boundary.isoformat()}")

    if verdict.outcome == OUTCOME_APPROACHING:
        warn_h = verdict.warn_seconds / 3600
        lines.append(
            f"APPROACHING: {len(verdict.approaching)} OFFICIAL_PORTAL source(s) "
            f"within {warn_h:.0f}h of going stale."
        )
        for f in sorted(verdict.approaching, key=lambda x: x.boundary)[:10]:
            hrs = (f.boundary - verdict.now).total_seconds() / 3600
            lines.append(
                f"  - {f.short_id} \"{f.title[:60]}\" boundary={f.boundary.isoformat()} "
                f"({hrs:.1f}h remaining)"
            )

    all_findings = list(verdict.stale) + list(verdict.approaching)
    if all_findings:
        earliest = min(all_findings, key=lambda f: f.boundary)
        hrs = (earliest.boundary - verdict.now).total_seconds() / 3600
        lines.append(f"Earliest boundary: {earliest.boundary.isoformat()} ({hrs:.1f}h from now)")
        lines.append("Action: run the weekly re-attestation lane (fold_pack_seqNN restamp).")

    if verdict.outcome == OUTCOME_ANOMALY:
        lines.append(
            "ANOMALY: no source is stale or approaching, but "
            f"{len(verdict.policy_missing) + len(verdict.future_verified)} "
            "OFFICIAL_PORTAL source(s) cannot be aged at all — the engine treats "
            "those as UNKNOWN. Action: inspect the pack's freshness_policy; a "
            "forward pack is the only way to correct a signed artifact."
        )

    if verdict.outcome == OUTCOME_NO_PORTAL_RECORDS:
        lines.append(f"NO_PORTAL_RECORDS: {verdict.reason}")

    if verdict.outcome == OUTCOME_CANNOT_VERIFY:
        lines.append(f"CANNOT_VERIFY: {verdict.reason}")

    if verdict.policy_missing:
        lines.append(
            f"{len(verdict.policy_missing)} portal source(s) missing/unreadable "
            "freshness_policy (engine treats as UNKNOWN)."
        )

    if verdict.future_verified:
        lines.append(
            f"{len(verdict.future_verified)} portal source(s) have verified_at "
            "in the future (anomaly)."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram gateway — fire-and-forget, exact house pattern
# ---------------------------------------------------------------------------


def _send(
    verdict: Verdict, gateway_path: Path, key: str | None = None
) -> tuple[str | None, str]:
    """One gateway call. Returns (gateway verdict, failure class). The class is
    "" when the gateway answered; otherwise a reason that carries no secret."""
    # ANOMALY is p0, not digest: a portal record the engine cannot age is a record
    # the engine treats as UNKNOWN, which is a decision-integrity fact, not a
    # housekeeping note.
    tier = (
        "p0"
        if verdict.outcome in (OUTCOME_STALE, OUTCOME_APPROACHING, OUTCOME_ANOMALY)
        else "digest"
    )
    text = format_alert_text(verdict)
    key = key or dedup_key(verdict)

    if not gateway_path.is_file():
        logger.warning("tg_notify.py not found at %s — alert NOT sent: %s", gateway_path, key)
        return None, "gateway-missing"

    try:
        proc = subprocess.run(
            [
                sys.executable, str(gateway_path),
                "--tier", tier,
                "--source", "visa-freshness-sentinel",
                "--dedup-key", key,
                "--", text,
            ],
            capture_output=True, text=True, timeout=30,
        )
        gateway_verdict = extract_gateway_verdict(proc.stderr)
        logger.info(
            "tg_notify: %s (rc=%s, tier=%s, key=%s)",
            gateway_verdict or "NO VERDICT", proc.returncode, tier, key,
        )
        return gateway_verdict, "" if gateway_verdict else "no-verdict"
    except Exception as exc:  # noqa: BLE001 — gateway failure must NEVER crash the sentinel
        logger.warning("tg_notify invocation failed: %s", type(exc).__name__)
        return None, "gateway-exception"


def send_alert(
    verdict: Verdict, gateway_path: Path = TG_NOTIFY, key: str | None = None
) -> str | None:
    """Route the verdict through `scripts/tg_notify.py`. Returns the gateway's
    machine-readable verdict string, or None when nothing was sent (OK, or
    the gateway could not be reached). NEVER raises — a gateway failure must
    not crash the sentinel (house contract, `drive_token_watchdog.py`)."""
    if verdict.outcome == OUTCOME_OK:
        return None
    return _send(verdict, gateway_path, key)[0]


# ---------------------------------------------------------------------------
# Persistent-condition re-alert (W141)
#
# The gateway's mute ladder (6h/24h/72h/168h) is built for FLAPPING conditions.
# A STALE pack is a standing outage: one lost first send plus a 168h mute is
# six days of silence. For STALE, and APPROACHING within a week of the
# boundary, this sentinel owns the schedule: every send goes out under a
# fresh gateway key (so the ladder never mutes it) and the sentinel's own
# state decides when the next one is due. A send that was not delivered does
# not move that schedule.
# ---------------------------------------------------------------------------

# Invariant: gap between two deliveries <= REALERT_MAX_GAP_S while the condition persists.
# A run can only land on a tick, so the worst gap is gate + one tick + drift:
#   REALERT_GATE_S + CADENCE_S + DRIFT_SLACK_S == REALERT_MAX_GAP_S.
CADENCE_S = 6 * 3600  # StartInterval of infra/launchagents/com.nuzantara.visa-freshness-sentinel.plist
REALERT_MAX_GAP_S = 24 * 3600
DRIFT_SLACK_S = 30 * 60
REALERT_GATE_S = REALERT_MAX_GAP_S - CADENCE_S - DRIFT_SLACK_S
CLOCK_SKEW_S = 300
BOARD_REPROBE_S = 7 * 86400
APPROACHING_PERSIST_S = 7 * 86400
ESCALATION_JOB = "visa-freshness-sentinel:persistent"
ESCALATION_JOB_PREFIX = "visa-freshness"


def _state_path() -> Path:
    override = os.environ.get("VISA_FRESHNESS_STATE")
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "nuzantara" / "visa_freshness_sentinel.json"


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True))
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("state not saved (%s): the next run re-alerts early", type(exc).__name__)


def is_persistent(verdict: Verdict) -> bool:
    if verdict.outcome == OUTCOME_STALE:
        return True
    if verdict.outcome == OUTCOME_APPROACHING and verdict.approaching:
        left = min((f.boundary - verdict.now).total_seconds() for f in verdict.approaching)
        return left <= APPROACHING_PERSIST_S
    return False


def _condition(verdict: Verdict) -> str:
    return f"{verdict.outcome}:{verdict.pack_sequence}"


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def sanitize_state(
    state: dict[str, Any], now_ts: float, *, log: bool = True
) -> tuple[dict[str, Any], list[str]]:
    """Validate every field; an invalid one is treated as ABSENT (so the next
    decision is a send), never trusted. A corrupt file must not silence STALE."""
    clean: dict[str, Any] = {}
    reset: list[str] = []
    horizon = now_ts + CLOCK_SKEW_S
    checks = {
        "condition": lambda v: isinstance(v, str),
        "route": lambda v: v == "board",
        "delivered_streak": lambda v: isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**6,
        "undelivered_attempts": lambda v: isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**6,
        "board_count": lambda v: isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 10**6,
        "telegram_last_delivered_ts": lambda v: _is_num(v) and v <= horizon,
        "board_last_ts": lambda v: _is_num(v) and v <= horizon,
        "cond_start_ts": lambda v: _is_num(v) and v <= horizon,
        "route_ts": lambda v: _is_num(v) and v <= horizon,
    }
    # `next_due_ts` is deliberately NOT a stored field any more: it is derived from
    # `telegram_last_delivered_ts` on every load, so a corrupt or stale stored value
    # (null, NaN, a day ahead) can never hold an alert back.
    for field, ok in checks.items():
        if field not in state:
            continue
        if ok(state[field]):
            clean[field] = state[field]
        else:
            reset.append(field)
            if log:
                logger.warning("state-reset: %s", field)
    return clean, reset


def _next_due(state: dict[str, Any]) -> float:
    """When the Telegram channel is next due: last delivery + the gate, else now."""
    last = state.get("telegram_last_delivered_ts")
    return last + REALERT_GATE_S if last is not None else 0.0


def decide_alert(verdict: Verdict, state: dict[str, Any], now_ts: float) -> dict[str, Any]:
    """Pure: what this run would do on the TELEGRAM channel, and why.

    Two channels, two clocks. Telegram: only a `sent` verdict advances
    `telegram_last_delivered_ts`. Board: the sentinel's own HIGH row, refreshed on its
    own clock (`board_last_ts`) and resolved on OK."""
    state, _ = sanitize_state(state, now_ts, log=False)
    dedup_state = {
        "condition": state.get("condition"),
        "delivered_streak": state.get("delivered_streak", 0),
        "undelivered_attempts": state.get("undelivered_attempts", 0),
        "telegram_last_delivered_ts": state.get("telegram_last_delivered_ts"),
        "next_due_ts": _next_due(state) if "telegram_last_delivered_ts" in state else None,
        "board_last_ts": state.get("board_last_ts"),
        "route": state.get("route"),
    }
    if verdict.outcome == OUTCOME_OK:
        return {"would_send": False, "reason": "ok-resets-ladder", "dedup_state": dedup_state}
    if not is_persistent(verdict):
        return {"would_send": None, "reason": "gateway-ladder", "dedup_state": dedup_state}
    if state.get("condition") != _condition(verdict):
        return {"would_send": True, "reason": "new-condition", "dedup_state": dedup_state}
    if now_ts >= _next_due(state):
        why = "retry-undelivered" if "telegram_last_delivered_ts" not in state else "realert-due"
        return {"would_send": True, "reason": why, "dedup_state": dedup_state}
    return {"would_send": False, "reason": "not-due-yet", "dedup_state": dedup_state}


def _escalation_open(verdict: Verdict, now_ts: float, count: int, force: bool) -> bool:
    """Write or refresh the ONE HIGH board row (same job; readers collapse to the latest).
    Returns True when a row was appended."""
    try:
        from scripts.sentinel_lib import escalations as esc

        summary = format_alert_text(verdict).replace("\n", " | ")[:400]
        if (
            not force
            and esc.is_job_open(ESCALATION_JOB)
            and _last_escalated(esc) == verdict.outcome
        ):
            return False
        esc.write_escalation({
            "job": ESCALATION_JOB,
            "type": "visa_freshness_persistent",
            "priority": "HIGH",
            "outcome": verdict.outcome,
            "last_seen_ts": now_ts,
            "attempts": count,
            "error_summary": summary,
            "detail": "Visa Oracle answers HUMAN_REVIEW_REQUIRED while portal stamps are stale; "
            "cure is the re-attestation ceremony (docs/runbooks/visa-engine-key-ceremony.md).",
            "context": "visa-freshness-sentinel",
        })
        return True
    except Exception as exc:  # noqa: BLE001 — the board must never crash the sentinel
        logger.warning("escalation row not written: %s", type(exc).__name__)
        return False


def _last_escalated(esc: Any) -> str | None:
    rows = [e for e in esc.read_all_escalations() if e.get("job") == ESCALATION_JOB]
    return rows[0].get("outcome") if rows else None


def _is_own_job(job: str) -> bool:
    """The sentinel's HIGH row (exact) or a gateway-routed `visa-freshness:*` job
    (strict `family:` prefix) — never a sibling like `visa-freshness-other-organ`."""
    return job == ESCALATION_JOB or job.startswith(f"{ESCALATION_JOB_PREFIX}:")


def _escalation_resolve() -> None:
    """Close the sentinel's HIGH row AND every gateway-routed row it spawned."""
    try:
        from scripts.sentinel_lib import escalations as esc

        jobs = {
            e.get("job") for e in esc.read_all_escalations()
            if _is_own_job(str(e.get("job", "")))
        }
        for job in sorted(j for j in jobs if j):
            if esc.is_job_open(job):
                esc.mark_resolved(job)
    except Exception as exc:  # noqa: BLE001
        logger.warning("escalation not resolved: %s", type(exc).__name__)


def run_alert_cycle(
    verdict: Verdict,
    *,
    dry_run: bool,
    now_ts: float,
    state_path: Path | None = None,
    gateway_path: Path = TG_NOTIFY,
) -> dict[str, Any]:
    """Decide, send, record. In dry-run only the decision is computed.

    Fail LOUD: an unexpected exception still attempts the send. An exception path
    that returns silently is the W141 shape."""
    try:
        return _run_alert_cycle(verdict, dry_run, now_ts, state_path, gateway_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("alert cycle failed (%s): sending anyway", type(exc).__name__)
        decision: dict[str, Any] = {"would_send": True, "reason": "internal-error-fallback-send"}
        if not dry_run and verdict.outcome != OUTCOME_OK:
            decision["gateway_verdict"] = _send(verdict, gateway_path)[0]
        return decision


def _run_alert_cycle(
    verdict: Verdict, dry_run: bool, now_ts: float, state_path: Path | None, gateway_path: Path
) -> dict[str, Any]:
    path = state_path or _state_path()
    state, _ = sanitize_state(load_state(path), now_ts)
    decision = decide_alert(verdict, state, now_ts)
    if dry_run:
        return decision

    if verdict.outcome == OUTCOME_OK:
        if state or path.exists():
            save_state(path, {})
        _escalation_resolve()
        return decision

    if decision["would_send"] is None:
        send_alert(verdict, gateway_path)  # non-persistent: the gateway ladder decides
        return decision

    cond = _condition(verdict)
    if state.get("condition") != cond:
        state = {"condition": cond, "delivered_streak": 0, "cond_start_ts": now_ts}
    cond_start = state.setdefault("cond_start_ts", now_ts)

    # BOARD channel: the sentinel's own row, on its own clock. It never depends on Telegram.
    board_due = now_ts >= state.get("board_last_ts", 0) + REALERT_GATE_S
    if _escalation_open(verdict, now_ts, state.get("board_count", 0) + 1, force=board_due):
        state.update(board_last_ts=now_ts, board_count=state.get("board_count", 0) + 1)

    if not decision["would_send"]:
        save_state(path, state)
        return decision

    # TELEGRAM channel: only a `sent` verdict advances its clock.
    attempts = state.get("undelivered_attempts", 0)
    # Once the gateway has answered `spooled` (board routing) keep ONE stable key so the
    # gateway holds one job, not one per attempt; re-probe weekly in case routing changed.
    on_board = state.get("route") == "board"
    probe = on_board and now_ts - state.get("route_ts", 0) >= BOARD_REPROBE_S
    key = dedup_key(verdict)
    if not on_board or probe:
        # condition start + delivery count + attempt: two deliveries inside one UTC day, or a
        # condition that ended and restarted the same day, must not share a key, or the
        # gateway ladder mutes the second.
        key = f"{key}:s{int(cond_start)}:n{state.get('delivered_streak', 0)}:a{attempts}"
    gateway_verdict, failure = _send(verdict, gateway_path, key)
    decision["gateway_verdict"] = gateway_verdict
    if gateway_verdict == "sent":
        state.update(
            delivered_streak=state.get("delivered_streak", 0) + 1,
            undelivered_attempts=0,
            telegram_last_delivered_ts=now_ts,
        )
        state.pop("route", None)
        state.pop("route_ts", None)
        decision.update(delivered=True, delivered_via="telegram")
    else:
        reason = failure or str(gateway_verdict)
        logger.warning("undelivered: reason=%s key=%s", reason, key)
        decision.update(delivered=False, undelivered_reason=reason)
        state["undelivered_attempts"] = attempts + 1
        if gateway_verdict == "spooled":
            # A board delivery: feeds the board clock, never the Telegram one.
            state.update(route="board", route_ts=now_ts if (not on_board or probe) else state.get("route_ts", now_ts))
            state.update(board_last_ts=now_ts, board_count=state.get("board_count", 0) + 1)
            decision["board_delivery"] = True
    save_state(path, state)
    return decision


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Alert BEFORE the active Visa Oracle RulePack's OFFICIAL_PORTAL "
        "sources cross their freshness_policy window."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print verdict JSON, never send Telegram.")
    parser.add_argument(
        "--now", default=None,
        help="ISO-8601 UTC instant override — TEST-ONLY, never for cron.",
    )
    parser.add_argument("--warn-seconds", type=int, default=DEFAULT_WARN_SECONDS)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[visa-freshness-sentinel] %(message)s",
    )

    if args.now:
        now = _parse_utc(args.now)
        if now is None:
            parser.error(f"--now: unparseable ISO-8601 instant: {args.now!r}")
    else:
        now = datetime.now(timezone.utc)

    verdict = build_verdict(now, args.warn_seconds)
    decision = run_alert_cycle(
        verdict, dry_run=args.dry_run, now_ts=now.timestamp()
    )
    out = verdict.to_json()
    out["alert_decision"] = decision
    print(json.dumps(out, indent=2))
    if not args.dry_run:
        if verdict.outcome != OUTCOME_OK:
            logger.info("alert decision: %s", decision.get("reason"))
        else:
            logger.info("OK — %d OFFICIAL_PORTAL source(s) within policy", verdict.portal_total)

    if verdict.outcome == OUTCOME_CANNOT_VERIFY:
        return 2
    if verdict.outcome == OUTCOME_STALE:
        return 1
    if verdict.outcome == OUTCOME_ANOMALY:
        # NOT 0. `pro-visa-freshness-sentinel.sh` writes `heartbeat "ok"` on any
        # zero exit, so an ANOMALY returning 0 would show as `ok` on the sidecar
        # — the one surface anyone actually reads — and the repair above would be
        # swallowed one layer down, exactly the way APPROACHING already is
        # (PENDING-ARMS 2026-08-30, defect 2, still open and NOT fixed here:
        # APPROACHING fires for 48h before every boundary, so making IT non-zero
        # needs the wrapper's exit-code map changed too, and that wrapper is a
        # HOME-fork declared pair that must be synced to Pro in the same gesture).
        # 3 is safe to ship alone: the wrapper's else-branch writes
        # `heartbeat "error" "rc=3"`, which is visible and true, and an
        # un-ageable pack is a rare defect state rather than a recurring phase,
        # so it cannot become a standing false red. Recovery is driven by
        # SILENCE (`severity_on_silence: warning`), not by a fresh error
        # heartbeat, so this does not put the healer in a kickstart loop.
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

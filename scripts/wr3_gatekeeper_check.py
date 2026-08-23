#!/usr/bin/env python3
"""WR3 pre-render-gatekeeper deterministic check matrix.
Faithful execution of ~/.claude/agents/wr3-pre-render-gatekeeper.md "Hard rules".
Writes gate-verdict.json. Step 4 spend gate (Law 7 hard halt).

Cost-gate rework 2026-08-23 (P03 "cost truth"): the cost circuit breaker was
previously decorative — see wr3_credit_ledger.py's module docstring for the
5 measured defects (frozen/hand-seeded quota file with nothing writing it;
uncaught crash + NO verdict file when that file is absent; the per-clip cost
this gate PROJECTS silently disagreed with what the real spend call site
projects, 10 here vs 20 there; a daily-ceiling check that computed its
condition and then `pass`ed; a `hard_ceiling` emitted into the verdict and
never compared against anything). This file now:
  - derives the per-clip cost from the same SSOT the real spend call site
    uses (wr3_credit_ledger.CLIP_COST_CR), so the two projections can no
    longer drift from EACH OTHER. NOTE this does not mean 20 is the
    verified true cost — see wr3_credit_ledger.py's module docstring:
    20 is an unverified 2026-05-20 observation on some paygate tier, and
    the live gateway mostly syncs a DIFFERENT tier than the one this repo
    requests. `WR3_FLOWKIT_CLIP_COST` is the escape hatch for that unknown;
  - fails CLOSED on a missing/invalid/stale quota snapshot — never crashes,
    always writes gate-verdict.json;
  - arms the daily-ceiling check against the ledger's OWN today's spend,
    not the quota file's frozen daily_spent_cr;
  - actually compares projected_cr against hard_ceiling;
  - short-circuits to a free PASS under WR3_ZERO_SPEND (nothing is spent,
    so nothing should be able to fail a cost gate).
"""
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# The file has no sys.path setup today — the siblings below live next to
# this script, not on the default import path when invoked from elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wr3_credit_ledger import (  # noqa: E402
    CLIP_COST_CR,
    _parse_ts,
    _resolve_ledger_path,
    read_integrity,
    read_records,
)
from wr3_spend_authority import zero_spend_enabled  # noqa: E402

EP = Path(sys.argv[1])
shot_pack = json.loads((EP / "shot-pack.json").read_text())
brief = json.loads((EP / "brief.json").read_text())

shots = shot_pack["shots"]
n = len(shots)
target_dur = shot_pack.get("total_duration_s", brief.get("target_duration_s", 145.4))


_LEDGER_UNREADABLE = -1


def _ledger_unreachable_reason(ledger_path: Path) -> str | None:
    """None when the ledger's ABSENCE can be believed; otherwise why it cannot.

    `Path.exists()` answers False both for a file that is not there and for one
    it cannot reach because an ancestor directory is unreadable — measured, not
    assumed. To a spend gate those two answers mean opposite things: absent is
    "0 spent today"; unreachable is "UNKNOWN spent today". Only the first is
    safe to spend against, and every reader downstream here — `read_integrity`,
    the malformed scan, `read_records` — collapses both into the same
    clean-looking zero without raising anything. No OSError handler can see
    this case, which is why it needs a check of its own.

    Walking up to the first ancestor that answers at all is what makes it
    correct: if `~/.cache` is unreadable then `~/.cache/wr3` reports "does not
    exist", and a check that stopped at the immediate parent would believe it.

    `os.access` is a pre-check, not the belt — it can disagree with the kernel
    under ACLs or on a network filesystem. The OSError handlers at the call
    sites remain the actual guarantee; this covers only what they cannot.
    """
    probe = ledger_path.parent
    while not os.access(probe, os.F_OK):
        if probe.parent == probe:
            return None
        probe = probe.parent
    if not os.access(probe, os.R_OK | os.X_OK):
        return f"ledger directory {probe} is not readable (permissions?)"
    return None

# The daily ceiling is a BUSINESS quantity, so its day must be the business's
# day — and it must not depend on the process environment. The obvious spelling,
# `datetime.now(timezone.utc).astimezone().tzinfo`, honours $TZ: under TZ=UTC
# (the default in most cron, launchd and container contexts) it silently reverts
# to UTC-date bucketing, which UNDER-counts spend — the direction that burns
# credits — and the one test written to catch that skips itself under exactly
# that condition, so the failure is invisible.
#
# A NAMED ZONE, resolved explicitly, never inherited:
#   * `ZoneInfo` + `timedelta(days=1)` does wall-clock arithmetic — measured, it
#     spans 25 hours across a fall-back day — so the window is DST-correct. A
#     fixed offset would not be.
#   * `/usr/share/zoneinfo` is present on every image this repo builds on
#     (python:3.11-slim, python:3.12-slim) and on alpine — measured, not assumed.
#     The PyPI `tzdata` package is deliberately NOT added: `wr3_credit_ledger.py`
#     documents a stdlib-only invariant, and `zoneinfo` is stdlib.
#   * If the zone cannot be resolved anyway (an exotic stripped base), this does
#     NOT refuse. Refusing would turn a missing tz database into a gate that
#     blocks every episode. It falls back to fixed UTC+8 — exact for this
#     business, one distinct offset across 1990-2030, verified — and records the
#     fallback so the degradation is visible instead of silent.
#
# What this does NOT protect against: a syntactically valid but WRONG zone
# (`WR3_BUSINESS_TZ=UTC`) resolves fine and no validation can reject it. The
# resolved zone stamped into gate-verdict.json is the mitigation for that.
_DEFAULT_BUSINESS_TZ = "Asia/Makassar"
_FALLBACK_BUSINESS_UTC_OFFSET_H = 8


def _business_tz() -> tuple[Any, str]:
    """(tzinfo, label) for the business day. Never reads $TZ."""
    name = os.environ.get("WR3_BUSINESS_TZ", "").strip() or _DEFAULT_BUSINESS_TZ
    try:
        return ZoneInfo(name), name
    except Exception:
        return (
            timezone(timedelta(hours=_FALLBACK_BUSINESS_UTC_OFFSET_H)),
            f"UTC+{_FALLBACK_BUSINESS_UTC_OFFSET_H} (fallback: zone {name!r} unresolvable)",
        )


def _scan_ledger_for_malformed_lines(ledger_path: Path) -> int:
    """Count non-blank ledger lines that are not a valid JSON object.

    `read_records()` already skips these — logged at WARNING, never fatal,
    which is the correct behaviour for a `report`. It is the WRONG behaviour
    for a spend gate: a ledger corrupted mid-write must not silently read as
    "0 spent today". This is a deliberate, SEPARATE check from
    `read_integrity()` below — `read_integrity()` only summarizes
    `record_spend()`'s write-failure sidecar (validation rejections / IO
    write failures at append time); it has no visibility into a ledger file
    that is corrupted by some other means (hand-edit, crash mid-line,
    concurrent writer). Both are checked because they catch different
    failure modes.
    """
    bad = 0
    try:
        # `exists()` is INSIDE the guard because it can itself raise: on Python
        # 3.9/3.11 it propagates PermissionError, while on 3.14 it answers False
        # — measured. Like the read_records handler, reaching it now needs a
        # TOCTOU window, since the caller short-circuits on an unreadable
        # directory before getting here; the `open()` below is the part this
        # try/except actually earns, and mutation-checked as a real gate.
        if not ledger_path.exists():
            return 0
        fh = ledger_path.open("r", encoding="utf-8")
    except OSError:
        # UNREADABLE is a different finding from MALFORMED and must not be
        # folded into the same count: a permissions fault and a corrupt line
        # need different cures. The sentinel keeps them distinct, and keeps
        # this function from killing the gate before any verdict is written.
        return _LEDGER_UNREADABLE
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(obj, dict):
                bad += 1
    return bad


# --- Cost check ---
# SSOT — wr3_credit_ledger.CLIP_COST_CR (2026-08-23 fix). Was a hardcoded
# 10 here that silently disagreed with wr3_flowkit_client.py's own
# projection of 20cr/clip. Collapsing to one number fixes that
# disagreement between the two files — it does NOT mean 20 is a verified
# true cost. See wr3_credit_ledger.py's module docstring: 20 traces to a
# single 2026-05-20 observation on some Flow paygate tier, and the live
# gateway account predominantly syncs a DIFFERENT tier than the one this
# client requests, so the true per-clip cost for the tier in use is
# UNMEASURED. `WR3_FLOWKIT_CLIP_COST` overrides this — treat it as the
# escape hatch for an unknown number, not a tuning knob.
CR_PER_CLIP = CLIP_COST_CR

# expected_cr / hard_ceiling are hardcoded for the ONE 150s-tier episode
# length (19 shots / 190cr expected / 209cr ceiling) this gate was written
# for. That is a REAL, separate defect (any other episode length gets a
# wrong envelope) — it is OUT OF SCOPE for this cost-truth fix (P03) and is
# left as-is. Do not read this as "fine" — see the module docstring above.
expected_cr = 190
hard_ceiling = 209

cost_fail = False
cost_reasons = []
cost_mode = "real"
business_tz_label = None
projected_cr = n * CR_PER_CLIP
balance = None
daily_ceiling_cr = None
quota_as_of = None
spent_today_cr = None

if zero_spend_enabled():
    # B1 — zero-spend short circuit, checked FIRST and before the quota file
    # is touched at all. Under WR3_ZERO_SPEND the renderer produces local
    # ffmpeg placeholders and provably spends 0 credits — a cost FAIL here
    # would block a pipeline that cannot cost anything, and the whole point
    # of zero-spend mode is that gatekeeper/audio/assembler/critic run
    # end-to-end at 0 credits.
    cost_mode = "placeholder"
    projected_cr = 0
else:
    # B2 — quota snapshot: fail CLOSED, never crash, never trust a stale
    # number. `Path("")` is truthy (it's PosixPath('.')), so branch on the
    # raw env string being non-empty, not on the Path.
    quota_env = os.environ.get("WR3_FLOW_QUOTA", "")
    quota_path = (
        Path(quota_env) if quota_env else Path.home() / ".cache" / "wr3" / "flow-quota.json"
    )
    max_age_h = float(os.environ.get("WR3_FLOW_QUOTA_MAX_AGE_H", "24"))

    quota = None
    refusal = None
    try:
        raw_quota_text = quota_path.read_text()
    except OSError as e:
        refusal = (
            f"quota snapshot unreadable/missing at {quota_path} ({e}) — "
            "nothing in this repo writes this file, so a missing balance "
            "silently disables the cost breaker; refusing to spend"
        )
    else:
        try:
            quota = json.loads(raw_quota_text)
        except json.JSONDecodeError as e:
            refusal = f"quota snapshot at {quota_path} is not valid JSON: {e}"

    if refusal is None:
        required = ("balance_remaining_cr", "daily_ceiling_cr", "as_of")
        missing = [k for k in required if k not in quota]
        if missing:
            refusal = f"quota snapshot at {quota_path} is missing required field(s): {missing}"

    if refusal is None:
        as_of_raw = quota.get("as_of")
        as_of_dt = _parse_ts(as_of_raw)
        if as_of_dt is None:
            refusal = f"quota snapshot's as_of={as_of_raw!r} is unparseable"
        else:
            age_h = (datetime.now(timezone.utc) - as_of_dt).total_seconds() / 3600.0
            if age_h > max_age_h:
                refusal = (
                    f"quota snapshot at {quota_path} is STALE: as_of={as_of_raw} "
                    f"is {age_h:.1f}h old (max {max_age_h}h) — nothing in this "
                    "repo writes this file, so a stale balance silently "
                    "disables the cost breaker; refusing to spend"
                )

    if refusal is not None:
        cost_fail = True
        cost_reasons.append(refusal)
    else:
        balance = quota["balance_remaining_cr"]
        daily_ceiling_cr = quota["daily_ceiling_cr"]
        quota_as_of = quota.get("as_of")

        # B4 — arm the daily-ceiling check off the LEDGER's real today's
        # spend, not the quota file's frozen daily_spent_cr. A degraded
        # ledger (either kind of corruption) must not silently read as "0
        # spent today" — that is ALSO a refusal.
        ledger_path_for_gate = _resolve_ledger_path(None)
        unreachable = _ledger_unreachable_reason(ledger_path_for_gate)
        if unreachable is not None:
            # Nothing below can be believed — and on some interpreters nothing
            # below even raises. MEASURED on this repo's own interpreters, with
            # the ledger's directory unreadable:
            #
            #   Python 3.9 / 3.11 (what CI pins) -> Path.exists() RAISES
            #     PermissionError; the gate dies without writing a verdict.
            #   Python 3.14 (what `#!/usr/bin/env python3` resolves to on the
            #     Pro and M5 render hosts) -> Path.exists() returns False;
            #     integrity reads "ok", the scan reads 0, read_records() reads
            #     [], and the gate PASSES with "0 spent today".
            #
            # So the SILENT failure is the one that happens on the machine that
            # actually spends credits, while the interpreter CI runs would have
            # shown a crash instead: a defect that cannot reproduce where it is
            # tested. That asymmetry is why this is a positive `os.access`
            # probe and not one more exception handler.
            integrity = {"status": "unreadable", "failure_count": 0, "since": None}
            malformed_lines = _LEDGER_UNREADABLE
        else:
            try:
                integrity = read_integrity()
            except OSError as e:
                # read_integrity() opens the failures sidecar with no handler of
                # its own, and it runs FIRST — so an unreadable sidecar killed
                # the gate before either guard below could fire, and before any
                # verdict was written. Handled at the call site, like the
                # read_records guard, because report/backfill also call it.
                integrity = {"status": "unreadable", "failure_count": 0, "since": None}
                unreachable = f"ledger failures sidecar unreadable ({e})"
            malformed_lines = _scan_ledger_for_malformed_lines(ledger_path_for_gate)
        if unreachable is not None or malformed_lines == _LEDGER_UNREADABLE:
            cost_fail = True
            detail = unreachable or f"ledger unreadable at {ledger_path_for_gate}"
            cost_reasons.append(
                f"cannot certify today's spend total — {detail} — refusing to "
                "spend rather than silently reading 0 spent today"
            )
        elif integrity["status"] != "ok" or malformed_lines:
            cost_fail = True
            parts = []
            if integrity["status"] != "ok":
                parts.append(
                    f"credit ledger integrity DEGRADED "
                    f"({integrity['failure_count']} write failure(s) since "
                    f"{integrity['since']})"
                )
            if malformed_lines:
                parts.append(f"{malformed_lines} malformed ledger line(s)")
            cost_reasons.append(
                "cannot certify today's spend total — " + "; ".join(parts) +
                " — refusing to spend rather than silently reading 0 spent today"
            )
        else:
            # "Today" is the OPERATOR's day, not the UTC day. Ledger
            # timestamps are UTC and that is right for storage, but a DAILY
            # CEILING is a business quantity and this business runs on WITA
            # (UTC+8). Bucketing by UTC date would slide the reset to 08:00
            # local and, worse, do it in the DANGEROUS direction: spend made
            # between 00:00 and 08:00 WITA carries the PREVIOUS UTC date, so
            # from 08:00 that same local morning it stops being counted and
            # the ceiling silently regains headroom it never had.
            # Measured 2026-08-23: a 07:00-WITA charge is counted at 07:00
            # and uncounted at 09:00, on the same local day. That is an
            # UNDER-count in a spend gate — the failure mode that burns
            # credits, not the one that blocks a render.
            # Compared as absolute instants against local-day boundaries, so
            # rows written in any offset land in the right bucket.
            local_tz, business_tz_label = _business_tz()
            day_start = datetime.now(local_tz).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)
            spent_today_cr = 0
            try:
                ledger_rows = read_records()
            except OSError as e:
                # BELT, and honestly a TOCTOU-only one. This branch is reached
                # only after the malformed scan already opened the same path
                # successfully, so no test can enter it deterministically —
                # mutation-checked: deleting this handler leaves the whole suite
                # green. It is kept anyway because the window is real (a chmod
                # or an unmount landing between the two opens) and the
                # difference it makes is a verdict saying "cannot certify"
                # instead of a crash with no verdict at all. Guarded here rather
                # than inside read_records() because report/backfill/dedupe also
                # call it and their contract is not this PR's concern.
                # Do not read its presence as coverage.
                cost_fail = True
                cost_reasons.append(
                    f"ledger unreadable while summing today's spend ({e}) — "
                    "refusing to spend rather than reading 0 spent today"
                )
                ledger_rows = []
            for rec in ledger_rows:
                if rec.get("mode") != "real":
                    continue
                ts = _parse_ts(rec.get("ts"))
                if ts is None:
                    continue
                if not (day_start <= ts.astimezone(local_tz) < day_end):
                    continue
                try:
                    spent_today_cr += int(rec.get("credits", 0))
                except (TypeError, ValueError):
                    continue

            if projected_cr > expected_cr * 1.10:
                cost_fail = True
                cost_reasons.append(f"projected {projected_cr}cr > expected {expected_cr}cr x1.10")
            if projected_cr > balance * 0.5:
                cost_fail = True
                cost_reasons.append(f"projected {projected_cr}cr > 50% of balance {balance}cr")
            # B4 — armed: this used to compute the condition and `pass`.
            if spent_today_cr + projected_cr > daily_ceiling_cr:
                cost_fail = True
                cost_reasons.append(
                    f"daily ceiling: spent_today {spent_today_cr}cr + projected "
                    f"{projected_cr}cr > daily_ceiling_cr {daily_ceiling_cr}cr"
                )
            # B5 — enforce hard_ceiling: reported before, never compared.
            if projected_cr > hard_ceiling:
                cost_fail = True
                cost_reasons.append(f"projected {projected_cr}cr > hard_ceiling {hard_ceiling}cr")

# --- Shot count sanity ---
max_shots = math.ceil(target_dur / 8) + 1  # 19 for 145.4
count_fail = (n > 20) or (n > max_shots)

# --- Per-shot checks (cliche / safety / Tier-1 dialect / identity token) ---
STYLE_RE = re.compile(r"\b(editorial\s+documentary|documentary|cinematic|journalistic|press\s+photography|magazine\s+cover|National\s+Geographic|award-winning)\b", re.I)
SENSITIVE_RE = re.compile(r"\b(passport|visa\s+stamp|visa\s+document|stamp\s+page)\b", re.I)
CITY_RE = re.compile(r"\b(Jakarta|Bali|Surabaya|Denpasar|Medan)\b")
SAFETY_RE = re.compile(r"\b(prison|prisons|punishes|punish|violence|violent|shooting|shoot|kill|killed|dead|death|handcuff|handcuffs|weapon|weapons|officer|officers|uniform|arrest|deport|deportation|gun|blood)\b", re.I)
# Cliche library (inline core set — anti-cliche per constitution Art 5.3 + WR3 b-roll bans)
CLICHE_RE = re.compile(r"\b(beach|palm\s+tree|palm\s+trees|infinity\s+pool|sunset|sunrise|rice\s+paddy|rice\s+terrace|temple|laptop\s+on\s+beach|coffee\s+cup|coconut|boho|influencer|handshake|smiling\s+team|stock\s+photo|drone\s+over\s+ocean)\b", re.I)

per_shot = []
shots_to_reroll = set()
cliche_failed = 0
cliche_passed = 0
flagged_words = []
safety_passed = True

for s in shots:
    sid = s["shot_id"]
    pos = s["prompt_positive"]
    wc = len(pos.split())
    issues = []
    # Cliche scan on POSITIVE prompt only
    cm = CLICHE_RE.findall(pos)
    if cm:
        issues.append(f"cliche:{cm}")
        shots_to_reroll.add(sid)
        cliche_failed += 1
    else:
        cliche_passed += 1
    # Style modifier scan
    sm = STYLE_RE.findall(pos)
    if sm:
        issues.append(f"style-modifier:{sm}")
        shots_to_reroll.add(sid)
    # Sensitive content
    sc = SENSITIVE_RE.findall(pos)
    if sc:
        issues.append(f"sensitive:{sc}")
        shots_to_reroll.add(sid)
    # City names
    cn = CITY_RE.findall(pos)
    if cn:
        issues.append(f"city:{cn}")
        shots_to_reroll.add(sid)
    # Safety words (audio filter) on positive prompt
    sw = SAFETY_RE.findall(pos)
    if sw:
        issues.append(f"safety:{sw}")
        flagged_words.extend(sw)
        safety_passed = False
        shots_to_reroll.add(sid)
    # Word count cap
    if wc > 25:
        issues.append(f"wordcount:{wc}>25")
        shots_to_reroll.add(sid)
    # Identity token check: Zantara shots must carry A007
    is_zantara = "zantara" in s["shot_type"].lower()
    if is_zantara and "A007" not in s.get("identity_tokens", []):
        issues.append("missing-A007")
        # this is FAIL-class, not reroll
    per_shot.append({"shot_id": sid, "word_count": wc, "zantara": is_zantara, "issues": issues})

identity_fail = any("missing-A007" in p["issues"] for p in per_shot)

# --- Verdict ---
verdict = "PASS"
retry_reasons = []
if cost_fail or count_fail or identity_fail:
    verdict = "FAIL"
    if cost_fail:
        retry_reasons += cost_reasons
    if count_fail:
        retry_reasons.append(f"shot_count {n} > sanity bound {max_shots} (or >20)")
    if identity_fail:
        retry_reasons.append("Zantara shot missing A007 identity token")
elif shots_to_reroll:
    verdict = "REROLL"
    retry_reasons.append(f"per-shot recoverable flags on {sorted(shots_to_reroll)}")

out = {
    "verdict": verdict,
    "checks": {
        "cliche": {"passed": cliche_passed, "failed": cliche_failed,
                   "details": [p for p in per_shot if any(i.startswith("cliche") for i in p["issues"])]},
        "cost": {"projected_cr": projected_cr, "budget_remaining_cr": balance,
                 "expected_cr": expected_cr, "hard_ceiling_cr": hard_ceiling,
                 "mode": cost_mode,
                 "daily_ceiling_cr": daily_ceiling_cr,
                 "spent_today_cr": spent_today_cr,
                 "spent_today_source": "ledger (business-day window)" if spent_today_cr is not None else None,
                 # Which zone actually resolved is otherwise an unlogged runtime
                 # fact — the exact shape of the defect this fixes.
                 "business_tz": business_tz_label,
                 "quota_as_of": quota_as_of,
                 "reasons": cost_reasons,
                 "passed": not cost_fail},
        "safety": {"flagged_words": sorted(set(flagged_words)), "passed": safety_passed},
        "tier1_dialect": {"max_word_count": max((p["word_count"] for p in per_shot), default=0),
                          "passed": all(p["word_count"] <= 25 for p in per_shot)},
        "shot_count": {"n": n, "sanity_bound": max_shots, "passed": not count_fail},
        "identity_tokens": {"passed": not identity_fail},
    },
    "shots_passed": n - len(shots_to_reroll),
    "shots_to_reroll": sorted(shots_to_reroll),
    "retry_reasons": retry_reasons,
    "reviewer": "wr3-pre-render-gatekeeper (deterministic check matrix, inline ruleset)",
    "note": "External cliche-library.md absent on disk (infra gap, seeded-empty 2026-05-18). Ran agent-definition inline Hard-rules ruleset. Cost gate derives per-clip cost from wr3_credit_ledger.CLIP_COST_CR SSOT and fails closed on a missing/stale flow-quota snapshot (2026-08-23 cost-truth fix).",
}
(EP / "gate-verdict.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))

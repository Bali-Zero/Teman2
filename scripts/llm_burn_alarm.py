#!/usr/bin/env python3
"""llm_burn_alarm.py — burn-rate alarm on ``llm_cost_events``.

BORN 2026-08-20: the 2026-08-10 spike ($11.11, 20.9M input tokens, 2238 calls
against a baseline of $0.11-$0.30/day — measured live on Postgres, see the PR
this ships in) sat in ``llm_cost_events`` for the whole day. Nothing read it.
The 4th Gemini prepay depletion (2026-08-11, WA silent) traces back to that
spike. This script is the reader that did not exist.

WHAT THIS IS NOT: a circuit-breaker. It never touches traffic and never picks
a fallback tier — that already exists (``scripts/cost_breaker.py``, a
per-PROVIDER fixed-budget advisory breaker) and interrupting
``rag.gateway.chat`` is a business decision (Legge 5), not a script's call.
This is the SIGNALER: it reads the ledger, compares the trailing 24h to a
MOVING baseline, and names the cause.

WHY NOT ``cost_breaker.py``: measured live on Pro 2026-08-20 — it is armed
(hourly LaunchAgent, real Telegram push wired) but structurally cannot have
caught the 08-10 spike even if the world had been healthy that day: (1) its
budget is a FIXED constant ($10/day for the whole ``gemini`` provider — a
frozen proxy, cicatrix W106), not a moving baseline, so it says nothing about
"5x your own normal"; (2) it sums by PROVIDER only, never by
(endpoint, model), so a STOP push never names ``rag.gateway.chat`` vs
``rag.verifier``; (3) DEGRADE — the state a fail-closed read produces — pushes
NOTHING (only STOP does), so a starved data source is silent, not urgent; and
(4) live logs show it reads via a JSONL export bridge
(``~/.agent/cost-ledger``) that was measured near-empty for 2026-08-12
through 2026-08-17 (85-169 byte files) — the exact aftermath of the incident
this alarm exists for. This script reads Postgres directly through
``scripts/pg.sh`` (the same "one true way" ``cost_ledger_export.py`` itself
targets), with no intermediate bridge to starve.

DESIGN CONTRACTS (each answers a scar this repo has already paid for):

  - Names its own cause (W116): the alarm text always states endpoint, model,
    call count, input tokens, and the baseline comparison. A verdict with no
    named cause is the alarm nobody reads.
  - Relative threshold, not a frozen constant (W106): the trigger is
    ``current_24h >= median(preceding 7 FULL UTC days) * multiplier``, never
    a hardcoded USD number alone. The one literal constant
    (``DEFAULT_FLOOR_USD``) is a floor beneath which even an infinite ratio is
    not worth an interrupt (a $0.03 day tripling to $0.09 is noise) — and it
    is named as exactly that here, not smuggled in as "the threshold".
  - CANNOT-VERIFY is its own state (W106b): a failed/empty query is never
    reported as "clean". A literally-empty ``llm_cost_events`` table is ALSO
    CANNOT-VERIFY, not "burn zero" — an ingestion pipeline gone silent must
    not read as a quiet day.
  - Judges the REPLY, never the exit code alone (W104): every ``pg.sh`` call
    is checked for BOTH rc==0 AND parseable, expected-shape output before its
    numbers are trusted; the Telegram dispatch captures ``tg_notify.notify``'s
    returned status string (not a subprocess rc — there is no subprocess here,
    the module is imported and called in-process on purpose).
  - No PII (Legge 2): only aggregates (endpoint, model, counts, tokens, USD).
    ``request_id`` is read nowhere in this script.
  - Never a circuit-breaker (Legge 5): this script's only side effect is a
    Telegram message. It has no opinion on whether to keep serving
    ``rag.gateway.chat``.

Run: ``python3 scripts/llm_burn_alarm.py`` (needs ``scripts/pg.sh`` reachable
— Postgres via the Fly proxy — and, for a real send, ``TELEGRAM_BOT_TOKEN`` /
``TELEGRAM_OWNER_CHAT_ID`` in the environment via ``tg_notify.py``'s own
resolution chain). ``--dry-run`` builds the message and logs it without
sending. Exit codes mirror ``cost_breaker.py``'s severity convention:
0 OK, 1 ALARM (message dispatched), 2 CANNOT-VERIFY (message dispatched to
the digest tier, distinct from both).
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from statistics import median as _median
from types import ModuleType

logger = logging.getLogger("llm_burn_alarm")

REPO_ROOT = Path(__file__).resolve().parent.parent
PG_SH = REPO_ROOT / "scripts" / "pg.sh"
TG_NOTIFY_PATH = REPO_ROOT / "scripts" / "tg_notify.py"

# ---------------------------------------------------------------------------
# Tunables — every one overridable from the CLI, none silently hardcoded.
# ---------------------------------------------------------------------------

BASELINE_DAYS = 7
# Trigger multiplier against the 7-day MEDIAN daily spend. 5x comfortably
# separates the measured guilt case (2026-08-10: ~55x its own week's median)
# from the measured innocent case (a normal day sits within ~1x of the week
# it belongs to) — see test_llm_burn_alarm.py for both, taken from live
# Postgres reads, not invented numbers.
DEFAULT_MULTIPLIER = Decimal("5")
# Plan-minimum floor (2026-08-20, this file): below this USD amount, even an
# infinite ratio (median == 0) is not worth an interrupt — the whole ledger's
# baseline days sit at $0.11-$1.70, so a $1 floor cannot fire on ordinary
# quiet-day noise while still catching every measured incident (all >= $3.75).
DEFAULT_FLOOR_USD = Decimal("1.00")
TOP_N_OFFENDERS = 3
PG_TIMEOUT_SECONDS = 30


class Verdict(str, Enum):
    OK = "OK"
    ALARM = "ALARM"
    CANNOT_VERIFY = "CANNOT_VERIFY"


@dataclass(frozen=True)
class WindowStats:
    usd: Decimal
    input_tokens: int
    calls: int


@dataclass(frozen=True)
class Offender:
    endpoint: str
    model: str
    calls: int
    usd: Decimal
    avg_input_tokens: int


# ---------------------------------------------------------------------------
# Pure decision logic — no I/O, fully unit-testable.
# ---------------------------------------------------------------------------


def compute_verdict(
    baseline_daily_usd: list[Decimal],
    current: WindowStats,
    *,
    multiplier: Decimal,
    floor_usd: Decimal,
) -> tuple[Verdict, Decimal]:
    """(Verdict, median) for the trailing-24h window against the baseline.

    ``baseline_daily_usd`` MUST be non-empty (a caller with no baseline data
    should map that to CANNOT_VERIFY before ever reaching here — this
    function has no CANNOT_VERIFY case of its own, only OK/ALARM, because it
    never touches I/O).

    - current.usd below the floor -> OK regardless of ratio (plan-minimum).
    - median == 0 (every preceding day was genuinely $0) and current clears
      the floor -> ALARM (the ratio is undefined/infinite; do not divide).
    - current.usd >= median * multiplier -> ALARM.
    - else -> OK.
    """
    if not baseline_daily_usd:
        raise ValueError("baseline_daily_usd must not be empty")
    med = _median(baseline_daily_usd)
    if current.usd < floor_usd:
        return Verdict.OK, med
    if med <= 0:
        return Verdict.ALARM, med
    if current.usd >= med * multiplier:
        return Verdict.ALARM, med
    return Verdict.OK, med


def _it_int(n: int) -> str:
    """Format an int with '.' as the thousands separator (Italian convention).

    Applied ONLY to the numeric substring — never a blanket ``.replace(",", ".")``
    on a whole sentence, which would also corrupt the sentence's own commas.
    """
    return f"{n:,}".replace(",", ".")


def build_alarm_message(
    current: WindowStats,
    median_usd: Decimal,
    multiplier: Decimal,
    offenders: list[Offender],
    baseline_days: int,
) -> str:
    """Names endpoint, model, calls, tokens, and the baseline comparison.

    An alarm that says "spend is high" and nothing else is the alarm nobody
    reads (W116). Every field below is load-bearing for that reason.
    """
    if median_usd > 0:
        ratio = current.usd / median_usd
        cmp_line = (
            f"${current.usd:.2f} nelle ultime 24h vs mediana ${median_usd:.2f}/giorno "
            f"sui {baseline_days} giorni precedenti ({ratio:.1f}x, soglia {multiplier}x)"
        )
    else:
        cmp_line = (
            f"${current.usd:.2f} nelle ultime 24h — i {baseline_days} giorni precedenti "
            f"erano tutti a $0 (rapporto indefinito, qualunque spesa sopra il floor è anomala)"
        )
    lines = [
        f"🔥 LLM cost burn anomalo: {cmp_line}.",
        f"{current.calls} chiamate, {_it_int(current.input_tokens)} token di input "
        f"totali nella finestra.",
    ]
    if offenders:
        lines.append("Causa principale (per costo, finestra 24h):")
        for o in offenders:
            lines.append(
                f"  • {o.endpoint} / {o.model}: {o.calls} chiamate, ${o.usd:.2f}, "
                f"~{_it_int(o.avg_input_tokens)} token input/chiamata",
            )
    else:
        lines.append(
            "Nessuna riga di breakdown per endpoint/model letta (best-effort, "
            "non blocca l'allarme) — il totale sopra resta l'evidenza.",
        )
    return "\n".join(lines)


def build_cannot_verify_message(reason: str) -> str:
    return (
        f"⚠️ llm_burn_alarm: impossibile misurare il burn LLM ({reason}). "
        f"Questo NON è 'tutto tranquillo' — è un buco di osservabilità sul "
        f"canale che ha già mancato un picco di $11 il 2026-08-10."
    )


# ---------------------------------------------------------------------------
# I/O: Postgres via scripts/pg.sh (judge rc AND shape, never rc alone — W104)
# ---------------------------------------------------------------------------


def run_pg(sql: str, *, timeout: int = PG_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run one statement through pg.sh. Never raises — a hung/absent binary
    is reported as a failing rc, exactly like a SQL error would be."""
    try:
        proc = subprocess.run(
            [str(PG_SH), "-tA", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def fetch_table_has_rows() -> bool | None:
    """None = could not verify. True/False = a genuine read."""
    rc, out, err = run_pg("SELECT COUNT(*) FROM llm_cost_events;")
    if rc != 0:
        logger.error("llm_burn_alarm: sanity COUNT failed rc=%s stderr=%s", rc, err[:300])
        return None
    line = out.strip().splitlines()[0] if out.strip() else ""
    try:
        return int(line) > 0
    except ValueError:
        logger.error("llm_burn_alarm: sanity COUNT unparseable output=%r", out[:200])
        return None


def fetch_baseline_daily_usd(days: int) -> list[Decimal] | None:
    """Trailing ``days`` FULL UTC calendar days (excludes today), each day
    present even if it had zero events (LEFT JOIN against generate_series —
    a day missing from the ledger is a KNOWN $0, not a dropped row)."""
    sql = f"""
        WITH days AS (
          SELECT generate_series(
            ((now() AT TIME ZONE 'UTC')::date - {days}),
            ((now() AT TIME ZONE 'UTC')::date - 1),
            interval '1 day'
          )::date AS d
        )
        SELECT days.d, COALESCE(SUM(e.cost_usd), 0)
        FROM days
        LEFT JOIN llm_cost_events e
          ON e.ts_utc >= (days.d::timestamp AT TIME ZONE 'UTC')
         AND e.ts_utc <  ((days.d + 1)::timestamp AT TIME ZONE 'UTC')
        GROUP BY days.d
        ORDER BY days.d;
    """
    rc, out, err = run_pg(sql)
    if rc != 0:
        logger.error("llm_burn_alarm: baseline query failed rc=%s stderr=%s", rc, err[:300])
        return None
    rows = [r for r in out.splitlines() if r.strip()]
    if len(rows) != days:
        logger.error(
            "llm_burn_alarm: baseline query returned %d rows, expected %d — output=%r",
            len(rows), days, out[:300],
        )
        return None
    result: list[Decimal] = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) != 2:
            logger.error("llm_burn_alarm: malformed baseline row %r", row)
            return None
        try:
            result.append(Decimal(parts[1]))
        except InvalidOperation:
            logger.error("llm_burn_alarm: unparseable baseline usd %r", parts[1])
            return None
    return result


def fetch_current_window() -> WindowStats | None:
    sql = """
        SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(input_tokens),0), COUNT(*)
        FROM llm_cost_events
        WHERE ts_utc >= now() - interval '24 hours';
    """
    rc, out, err = run_pg(sql)
    if rc != 0:
        logger.error("llm_burn_alarm: current-window query failed rc=%s stderr=%s", rc, err[:300])
        return None
    line = out.strip()
    if not line:
        logger.error("llm_burn_alarm: current-window query returned no output")
        return None
    parts = line.splitlines()[0].split("\t")
    if len(parts) != 3:
        logger.error("llm_burn_alarm: malformed current-window row %r", line)
        return None
    try:
        return WindowStats(
            usd=Decimal(parts[0]),
            input_tokens=int(parts[1]),
            calls=int(parts[2]),
        )
    except (InvalidOperation, ValueError):
        logger.error("llm_burn_alarm: unparseable current-window row %r", line)
        return None


def fetch_offenders(limit: int) -> list[Offender] | None:
    """Best-effort breakdown for naming the cause. Returns [] (not None) on a
    genuinely-empty result set — only a failed/malformed READ returns None,
    and the caller treats that as 'no breakdown available', not fatal (the
    totals from fetch_current_window already carry the alarm's evidence)."""
    sql = f"""
        SELECT COALESCE(endpoint,'(none)'), model, COUNT(*),
               COALESCE(SUM(cost_usd),0), COALESCE(AVG(input_tokens),0)::bigint
        FROM llm_cost_events
        WHERE ts_utc >= now() - interval '24 hours'
        GROUP BY 1,2
        ORDER BY 4 DESC
        LIMIT {limit};
    """
    rc, out, err = run_pg(sql)
    if rc != 0:
        logger.warning("llm_burn_alarm: offenders query failed rc=%s stderr=%s", rc, err[:300])
        return None
    offenders: list[Offender] = []
    for row in out.splitlines():
        if not row.strip():
            continue
        parts = row.split("\t")
        if len(parts) != 5:
            logger.warning("llm_burn_alarm: malformed offender row %r — skipping", row)
            continue
        try:
            offenders.append(
                Offender(
                    endpoint=parts[0],
                    model=parts[1],
                    calls=int(parts[2]),
                    usd=Decimal(parts[3]),
                    avg_input_tokens=int(parts[4]),
                ),
            )
        except (InvalidOperation, ValueError):
            logger.warning("llm_burn_alarm: unparseable offender row %r — skipping", row)
            continue
    return offenders


# ---------------------------------------------------------------------------
# Dispatch — imports tg_notify in-process and judges its RETURNED STATUS
# (never a subprocess exit code — there is no subprocess on this path).
# ---------------------------------------------------------------------------

_TG_MODULE: ModuleType | None = None


def _tg_notify_module() -> ModuleType:
    global _TG_MODULE
    if _TG_MODULE is None:
        spec = importlib.util.spec_from_file_location("tg_notify", str(TG_NOTIFY_PATH))
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load tg_notify from {TG_NOTIFY_PATH}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _TG_MODULE = mod
    return _TG_MODULE


def send(
    *,
    tier: str,
    source: str,
    text: str,
    dedup_key: str,
    dry_run: bool,
    notify_fn=None,
) -> str:
    """Dispatch via tg_notify.notify (or an injected fake for tests).

    Returns the STATUS STRING tg_notify hands back ("sent" / "deduped" /
    "spooled" / "p0_overflow_spooled" / ...) — that string IS the reply this
    function judges, not any process exit code. Never raises: tg_notify.py
    itself is documented to never fail its caller, and the import step here
    is wrapped defensively so a corrupt/missing tg_notify.py degrades to a
    logged, undelivered alarm rather than crashing this script.
    """
    if dry_run:
        logger.info("llm_burn_alarm: --dry-run, NOT sending. Message:\n%s", text)
        return "dry_run"
    try:
        fn = notify_fn or _tg_notify_module().notify
        status = fn(tier, source, text, dedup_key)
    except Exception as exc:  # noqa: BLE001 — a dispatch failure must not crash the alarm
        logger.error("llm_burn_alarm: tg_notify dispatch raised: %s", exc)
        return "dispatch_error"
    logger.info("llm_burn_alarm: tg_notify status=%s", status)
    return status


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline-days", type=int, default=BASELINE_DAYS)
    parser.add_argument("--multiplier", type=Decimal, default=DEFAULT_MULTIPLIER)
    parser.add_argument("--floor-usd", type=Decimal, default=DEFAULT_FLOOR_USD)
    parser.add_argument("--top-n", type=int, default=TOP_N_OFFENDERS)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="build the message but do not dispatch via tg_notify",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    has_rows = fetch_table_has_rows()
    if has_rows is None:
        reason = "impossibile eseguire la query di sanity su llm_cost_events (Postgres irraggiungibile o query fallita)"
        send(tier="digest", source="llm-burn-alarm", text=build_cannot_verify_message(reason),
             dedup_key="llm-burn-cannot-verify", dry_run=args.dry_run)
        logger.error("llm_burn_alarm: CANNOT_VERIFY — %s", reason)
        return 2
    if has_rows is False:
        reason = "llm_cost_events esiste ma ha ZERO righe — non è un burn a zero, è la pipeline di ingest ferma"
        send(tier="digest", source="llm-burn-alarm", text=build_cannot_verify_message(reason),
             dedup_key="llm-burn-cannot-verify", dry_run=args.dry_run)
        logger.error("llm_burn_alarm: CANNOT_VERIFY — %s", reason)
        return 2

    baseline = fetch_baseline_daily_usd(args.baseline_days)
    if baseline is None:
        reason = f"impossibile leggere i {args.baseline_days} giorni di baseline da llm_cost_events"
        send(tier="digest", source="llm-burn-alarm", text=build_cannot_verify_message(reason),
             dedup_key="llm-burn-cannot-verify", dry_run=args.dry_run)
        logger.error("llm_burn_alarm: CANNOT_VERIFY — %s", reason)
        return 2

    current = fetch_current_window()
    if current is None:
        reason = "impossibile leggere la finestra corrente (ultime 24h) da llm_cost_events"
        send(tier="digest", source="llm-burn-alarm", text=build_cannot_verify_message(reason),
             dedup_key="llm-burn-cannot-verify", dry_run=args.dry_run)
        logger.error("llm_burn_alarm: CANNOT_VERIFY — %s", reason)
        return 2

    verdict, median_usd = compute_verdict(
        baseline, current, multiplier=args.multiplier, floor_usd=args.floor_usd,
    )

    if verdict is Verdict.OK:
        logger.info(
            "llm_burn_alarm: OK — $%.2f/24h vs mediana $%.2f su %d giorni (soglia %sx, floor $%s)",
            current.usd, median_usd, args.baseline_days, args.multiplier, args.floor_usd,
        )
        return 0

    offenders = fetch_offenders(args.top_n)
    message = build_alarm_message(
        current, median_usd, args.multiplier, offenders or [], args.baseline_days,
    )
    send(tier="p0", source="llm-burn-alarm", text=message,
         dedup_key="llm-burn-anomaly", dry_run=args.dry_run)
    logger.warning("llm_burn_alarm: ALARM\n%s", message)
    return 1


if __name__ == "__main__":
    sys.exit(main())

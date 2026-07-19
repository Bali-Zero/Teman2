#!/usr/bin/env python3
"""cost_breaker.py — P9 (GOVERN) cost-breaker on the local LLM cost ledger.

The SAFE SLICE of the SOTA meta-dev-loop's GOVERN piece. This module READS the
already-shipped cost ledger (Postgres ``llm_cost_events`` migration 117, or the
JSONL fallback ``${LLM_COST_JSONL_ROOT:-/data}/llm_cost_log.{date}.jsonl``) and
TRIGGERS the already-shipped cascade fallback (claude_oauth -> gemini ->
kimi -> openrouter -> ollama). It NEVER spends, NEVER calls a paid endpoint,
NEVER sees client PII — it only sums ``cost_usd`` per provider over a time
window and emits a verdict.

Design (gate map):
- G1: in the ALLOW (normal) state it pushes ZERO notifications.
- G2: between threshold and budget it DEGRADEs (cascade to next tier), it does
      NOT hard-STOP and it does NOT blindly continue.
- G3: the STOP push is a CHOICE ([D]egrade/[P]ause/[C]ontinue), never a bare
      diagnosis.
- G4: it FAILS CLOSED. When spend is UNKNOWN (no data source available, or the
      consulted source errored) for a GUARDED provider, the verdict is DEGRADE
      (cascade down), NEVER ALLOW. ALLOW is correct only when spend is KNOWN to
      be under threshold. A genuine, successfully-read $0 is KNOWN and ALLOWs;
      an unread/errored source is UNKNOWN and DEGRADEs.
- G5: the dead-man's switch (companion ``cost_breaker_deadman.sh``) is the
      second-observer that watches the governance alive-signals.
- G6: every cascade provider with a budget is guarded — no provider unguarded.

CASCADE-CONSUMER CONTRACT (read before wiring this in): the breaker is
ONE-SHOT per provider. ``decide(provider, …)`` evaluates ONLY ``provider``'s
spend and, on DEGRADE/STOP, names the next tier — it does NOT recursively
verify that the next tier is itself under budget. The CONSUMER is responsible
for RE-INVOKING the breaker on the degraded tier (``decision.next_tier``)
before spending on it; otherwise it may cascade onto a tier that is also
exhausted. Iterate down ``CASCADE_ORDER`` calling ``decide`` per tier until a
tier returns ALLOW (or you hit the unguarded floor, ollama).

Reuse note: the window-sum mirrors ``CostAdvisor.run_daily_cap_check`` /
``analyze_last_window`` SQL idiom (SUM(cost_usd) over a ts_utc window, riding the
``idx_llm_cost_provider_ts`` index) rather than re-deriving it. The Telegram
idiom mirrors ``cost_advisor_cli.send_telegram`` (urllib, swallow-on-error,
TELEGRAM_OWNER_CHAT_ID default 1125336968).

HONEST LIMIT: the per-provider budget is a PROXY threshold (a configurable USD
estimate), NOT the opaque flat-rate MAX/subscription quota. The breaker degrades
on a money-proxy, not on the provider's real remaining quota — which is not
machine-readable. The ultimate backstop is still a human (the STOP push asks).

Importable with NO network and NO DB access at import time (everything that
touches a pool/JSONL/HTTP is inside a function).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("cost_breaker")


# ---------------------------------------------------------------------------
# Cascade topology (mirrors the regulatory-watcher-run.sh tier order)
# ---------------------------------------------------------------------------

# claude_oauth -> gemini -> kimi -> openrouter -> ollama -> None (terminal).
# ollama is local/$0 — it has NO budget and is the floor of the cascade.
# kimi is a flat-subscription seat (Moonshot Allegro plan) — zero marginal
# cost, same posture as ollama, so it is ALSO unguarded (deepseek RETIRED
# 2026-07-19, owner order, pre-auth revoked — never top up; its $5.00 budget
# slot is not carried forward, kimi does not need one).
# openrouter is a PAID per-token path with no flat subscription, so it is the
# last PAID tier before the free floor and it carries a conservative budget.
CASCADE_ORDER: tuple[str, ...] = (
    "claude_oauth",
    "gemini",
    "kimi",
    "openrouter",
    "ollama",
)

# Providers that carry a money cost and therefore a budget (G6 coverage set).
# ollama and kimi are excluded on purpose: local inference and Kimi's flat
# subscription are both free at the margin — nothing to break.
GUARDED_PROVIDERS: tuple[str, ...] = (
    "claude_oauth",
    "gemini",
    "openrouter",
)

# Conservative default per-provider budgets (USD, per window). These are PROXY
# numbers, deliberately small, override via env COST_BREAKER_BUDGET_<P>_USD.
_DEFAULT_BUDGET_USD: dict[str, Decimal] = {
    "claude_oauth": Decimal("20.00"),
    "gemini": Decimal("10.00"),
    "openrouter": Decimal("5.00"),
}

# Provider-label normalization: the ledger stores the caller's verbatim string,
# which drifts (model suffixes, vendor-vs-tier names) from the breaker's
# canonical cascade keys. This map folds raw labels onto canonical providers so
# an ``anthropic`` ledger row counts toward the ``claude_oauth`` budget, a
# ``gemini-flash`` row toward ``gemini``, etc. Applied BOTH when summing ledger
# rows AND when building the PG alias set. Case-insensitive; longest model
# suffixes are stripped by the prefix rules below.
_PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "claude_oauth",
    "claude-oauth": "claude_oauth",
    "claude_oauth": "claude_oauth",
    "claude": "claude_oauth",
    "gemini": "gemini",
    "google": "gemini",
    "kimi": "kimi",
    "openrouter": "openrouter",
    "ollama": "ollama",
}

# Canonical providers whose model-suffixed variants (``<prefix>-<model>`` or
# ``<prefix>_<model>`` or ``<prefix>/<model>``) fold onto the prefix, e.g.
# ``gemini-2.0`` / ``kimi-code/k3`` / ``claude-3-5-sonnet``.
_PROVIDER_PREFIXES: tuple[str, ...] = (
    "claude_oauth",
    "claude",
    "anthropic",
    "gemini",
    "kimi",
    "openrouter",
    "ollama",
)

# DEGRADE fires at this fraction of budget — conservative 85% (in the 80-90%
# band the spec asks for). Override via COST_BREAKER_THRESHOLD_FRACTION.
_DEFAULT_THRESHOLD_FRACTION: Decimal = Decimal("0.85")

# Default window: 24h, matching cost_advisor_cli's daily cap horizon.
_DEFAULT_WINDOW_SECONDS: int = 24 * 60 * 60

# Telegram (mirrors cost_advisor_cli idiom).
_TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")

# STOP-push cooldown (P2-1): suppress duplicate STOP pushes for the same
# provider within this many seconds, so a per-tick re-check (the CLI runs on a
# cron) does not re-spam the operator. Mirrors the deadman's COOLDOWN_SEC idiom
# with a per-provider state file. Override via COST_BREAKER_PUSH_COOLDOWN_SEC.
_DEFAULT_PUSH_COOLDOWN_SEC: int = 3600  # 1h
_COOLDOWN_STATE_DIR: Path = Path.home() / ".agent" / "decisions" / "state"


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    """The three breaker states.

    ALLOW    spend below threshold — proceed on the current tier, ZERO push (G1).
    DEGRADE  threshold <= spend < budget — cascade to the next tier (G2).
    STOP     spend >= budget — no tier left / hard stop, push a CHOICE (G3).
    """

    ALLOW = "ALLOW"
    DEGRADE = "DEGRADE"
    STOP = "STOP"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakerConfig:
    """Per-provider budgets + the shared threshold fraction + window.

    ``budgets_usd`` maps provider -> hard budget. ``threshold_fraction`` is the
    fraction of budget at which DEGRADE engages. Everything is overridable from
    the environment via :meth:`from_env`.
    """

    budgets_usd: Mapping[str, Decimal] = field(
        default_factory=lambda: dict(_DEFAULT_BUDGET_USD),
    )
    threshold_fraction: Decimal = _DEFAULT_THRESHOLD_FRACTION
    window_seconds: int = _DEFAULT_WINDOW_SECONDS

    def budget_for(self, provider: str) -> Decimal | None:
        """Hard budget for a provider, or None if the provider is unguarded.

        A non-positive budget (<= 0) is treated as UNGUARDED (P1-3): a directly-
        constructed ``BreakerConfig(budgets_usd={"x": 0})`` would otherwise STOP
        at every spend >= 0 (STOP-spam). Zero budget = "no budget" = ALLOW.
        """
        budget = self.budgets_usd.get(provider)
        if budget is None or budget <= 0:
            return None
        return budget

    def threshold_for(self, provider: str) -> Decimal | None:
        """DEGRADE threshold (= budget * fraction) for a provider, or None."""
        budget = self.budget_for(provider)
        if budget is None:
            return None
        return budget * self.threshold_fraction

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BreakerConfig:
        """Build a config from environment overrides.

        - COST_BREAKER_BUDGET_CLAUDE_OAUTH_USD / _GEMINI_USD / _OPENROUTER_USD
        - COST_BREAKER_THRESHOLD_FRACTION
        - COST_BREAKER_WINDOW_SECONDS
        Invalid values fall back to the conservative defaults (never crash the
        breaker on a typo'd env var).
        """
        env = os.environ if env is None else env
        budgets: dict[str, Decimal] = dict(_DEFAULT_BUDGET_USD)
        for provider in GUARDED_PROVIDERS:
            key = f"COST_BREAKER_BUDGET_{provider.upper()}_USD"
            raw = env.get(key)
            if raw is not None:
                parsed = _safe_decimal(raw)
                if parsed is not None and parsed > 0:
                    budgets[provider] = parsed
                else:
                    logger.warning(
                        "cost_breaker: ignoring invalid %s=%r, using default %s",
                        key,
                        raw,
                        budgets[provider],
                    )

        fraction = _DEFAULT_THRESHOLD_FRACTION
        raw_fraction = env.get("COST_BREAKER_THRESHOLD_FRACTION")
        if raw_fraction is not None:
            parsed_fraction = _safe_decimal(raw_fraction)
            if parsed_fraction is not None and Decimal("0") < parsed_fraction <= Decimal("1"):
                fraction = parsed_fraction
            else:
                logger.warning(
                    "cost_breaker: ignoring invalid COST_BREAKER_THRESHOLD_FRACTION=%r",
                    raw_fraction,
                )

        window = _DEFAULT_WINDOW_SECONDS
        raw_window = env.get("COST_BREAKER_WINDOW_SECONDS")
        if raw_window is not None:
            try:
                candidate = int(raw_window)
                if candidate > 0:
                    window = candidate
                else:
                    raise ValueError
            except (TypeError, ValueError):
                logger.warning(
                    "cost_breaker: ignoring invalid COST_BREAKER_WINDOW_SECONDS=%r",
                    raw_window,
                )

        return cls(
            budgets_usd=budgets,
            threshold_fraction=fraction,
            window_seconds=window,
        )


def _safe_decimal(value: Any) -> Decimal | None:
    """Decimal(str(value)) that returns None instead of raising.

    Hardened (P1-3): NaN/Inf are REJECTED (return None) — a NaN slipping into a
    running sum makes the whole provider sum NaN, and ``NaN >= budget`` is
    False, which would fail-OPEN to ALLOW. Negatives are also rejected so a
    spurious credit/refund row cannot mask real spend. One bad row must never
    poison the sum nor flip the verdict.
    """
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None
    if not parsed.is_finite():  # NaN / Infinity / -Infinity
        return None
    if parsed < 0:
        return None
    return parsed


def _normalize_provider(raw: Any) -> str:
    """Fold a raw ledger ``provider`` string onto its canonical cascade key.

    - case-insensitive, whitespace-stripped
    - exact alias hits first (``anthropic`` -> ``claude_oauth``)
    - else strip a model suffix on a known prefix (``gemini-flash`` ->
      ``gemini``, ``kimi-code/k3`` -> ``kimi``, ``claude-3-5-sonnet`` ->
      ``claude_oauth`` via the ``claude`` prefix alias)
    - else return the lower-cased token unchanged (an unknown provider stays
      unknown; the caller decides how to treat it — never silently ALLOW a paid
      one).
    """
    if raw is None:
        return ""
    token = str(raw).strip().lower()
    if not token:
        return ""
    if token in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[token]
    for prefix in _PROVIDER_PREFIXES:
        for sep in ("-", "_", "/", "."):
            if token.startswith(prefix + sep):
                return _PROVIDER_ALIASES.get(prefix, prefix)
    return token


# ---------------------------------------------------------------------------
# Cascade helper
# ---------------------------------------------------------------------------


def next_tier(provider: str) -> str | None:
    """Return the next cascade tier after ``provider``, or None at the floor.

    claude_oauth -> gemini -> kimi -> openrouter -> ollama -> None. An unknown
    provider yields None (no safe downgrade we can assert).
    """
    try:
        idx = CASCADE_ORDER.index(provider)
    except ValueError:
        return None
    if idx + 1 < len(CASCADE_ORDER):
        return CASCADE_ORDER[idx + 1]
    return None


# ---------------------------------------------------------------------------
# Evaluate (pure)
# ---------------------------------------------------------------------------


def evaluate(provider: str, spend: Decimal | None, config: BreakerConfig) -> Verdict:
    """Map (provider, spend, config) -> Verdict. Pure, no I/O.

    - spend is None (UNKNOWN) + guarded -> DEGRADE  (G4 fail-closed)
    - spend < threshold                 -> ALLOW
    - threshold <= spend < budget       -> DEGRADE  (G2)
    - spend >= budget                   -> STOP     (G2 hard stop / G6)

    FAIL-CLOSED (G4): ``spend is None`` means spend is UNKNOWN — no source could
    be consulted or the consulted source errored. For a GUARDED provider this is
    NOT ALLOW (which would spend blind on the priciest tier); it is DEGRADE —
    cascade down to a cheaper/free tier. A genuine, successfully-read $0 is a
    Decimal("0"), NOT None, and ALLOWs correctly.

    Unguarded providers (no budget, e.g. ollama) always ALLOW — there is no
    money to break, even when spend is unknown. Known spend is coerced to
    Decimal defensively (a corrupt non-None spend that fails coercion is treated
    as UNKNOWN -> fail-closed, not as $0).
    """
    budget = config.budget_for(provider)
    threshold = config.threshold_for(provider)
    if budget is None or threshold is None:
        # Unguarded (e.g. ollama / unknown) — nothing to break.
        return Verdict.ALLOW
    if spend is None:
        # UNKNOWN spend on a guarded provider — fail closed (G4).
        logger.warning(
            "cost_breaker: spend UNKNOWN for %s -> fail-closed DEGRADE", provider,
        )
        return Verdict.DEGRADE
    spend_dec = _safe_decimal(spend)
    if spend_dec is None:
        # A non-None but uncoercible spend (NaN/garbage) is still UNKNOWN, not $0.
        logger.warning(
            "cost_breaker: spend value %r for %s is not a finite non-negative "
            "Decimal -> fail-closed DEGRADE",
            spend,
            provider,
        )
        return Verdict.DEGRADE
    if spend_dec >= budget:
        return Verdict.STOP
    if spend_dec >= threshold:
        return Verdict.DEGRADE
    return Verdict.ALLOW


# ---------------------------------------------------------------------------
# Window-sum: pure core + data-source adapters
# ---------------------------------------------------------------------------


def sum_rows_in_window(
    rows: Iterable[Mapping[str, Any]],
    provider: str,
    window_start: datetime,
    window_end: datetime | None = None,
) -> Decimal:
    """Sum ``cost_usd`` over rows for ``provider`` with ``ts`` inside the window.

    The PURE, testable core: given any iterable of row-like mappings (DB rows,
    parsed JSONL dicts, or fakes), it isolates one CANONICAL provider's spend in
    the window ``[window_start, window_end]`` (both inclusive). ``provider`` is
    matched after :func:`_normalize_provider`, so a raw ledger row labelled
    ``anthropic`` / ``gemini-flash`` counts toward ``claude_oauth`` / ``gemini``
    respectively (P0-2). Rows missing/None ts_utc or cost_usd are skipped; a
    NaN/Inf/negative cost is skipped (P1-3) so one bad row cannot poison the sum.
    Rows after ``window_end`` (a future-dated/clock-skewed row) are excluded
    (P1-2). ts_utc may be a datetime or an ISO-8601 string (the JSONL form).
    """
    want = _normalize_provider(provider)
    total = Decimal("0")
    for row in rows:
        if _normalize_provider(row.get("provider")) != want:
            continue
        ts = _coerce_ts(row.get("ts_utc"))
        if ts is None or ts < window_start:
            continue
        if window_end is not None and ts > window_end:
            continue
        cost = _safe_decimal(row.get("cost_usd"))
        if cost is None:
            continue
        total += cost
    return total


def _coerce_ts(value: Any) -> datetime | None:
    """Coerce a ts value (datetime | ISO string) to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _iter_jsonl_rows(
    jsonl_root: Path,
    window_start: datetime,
    now: datetime,
) -> Iterable[Mapping[str, Any]]:
    """Yield parsed JSONL rows from the daily files overlapping the window.

    Files are named ``llm_cost_log.{YYYY-MM-DD}.jsonl`` (UTC date). We read the
    files for each UTC day from window_start..now inclusive. Malformed lines and
    missing files are skipped silently (last-resort log, best-effort read).
    """
    day = window_start.astimezone(timezone.utc).date()
    end_day = now.astimezone(timezone.utc).date()
    while day <= end_day:
        path = jsonl_root / f"llm_cost_log.{day.isoformat()}.jsonl"
        if path.is_file():
            try:
                with path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
            except OSError as exc:
                logger.warning("cost_breaker: cannot read %s: %s", path, exc)
        day += timedelta(days=1)


async def provider_spend_in_window(
    provider: str,
    window_seconds: int,
    *,
    conn_or_pool: Any = None,
    jsonl_root: str | Path | None = None,
    now: datetime | None = None,
) -> Decimal | None:
    """SUM(cost_usd) for ``provider`` over the trailing ``window_seconds``.

    Data-source resolution (first that is available wins):
      1. ``conn_or_pool`` — an asyncpg Connection (has ``.fetchval``) or Pool
         (has ``.acquire``). Uses the parameterised SUM riding
         ``idx_llm_cost_provider_ts``, anchored on the injected ``now`` so the
         window is ``[now - window, now]`` (P1-1/P1-2 — same clock-injectable
         semantics as the JSONL path, not the DB wall-clock).
      2. ``jsonl_root`` — directory of daily JSONL files (fallback when no DB).
      3. ``${LLM_COST_JSONL_ROOT:-/data}`` — last-resort default JSONL root.

    TRISTATE return (P0-1, G4 fail-closed):
      - ``Decimal`` — a GENUINE successful read (even a real $0).
      - ``None``    — spend is UNKNOWN: the DB read raised, OR there was no data
        source at all (no pool AND no JSONL file present for the window). The
        caller (``evaluate``/``decide``) maps None -> DEGRADE for a guarded
        provider rather than ALLOW-ing blind. A read that succeeds but finds no
        matching rows in a PRESENT source is Decimal("0"), NOT None — empty-but-
        read is KNOWN-zero, unread is UNKNOWN.

    Async only because asyncpg is async; the JSONL path runs synchronously.
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)

    if conn_or_pool is not None:
        return await _pg_provider_spend(
            conn_or_pool, provider, window_start, now,
        )

    root = Path(
        jsonl_root
        if jsonl_root is not None
        else os.environ.get("LLM_COST_JSONL_ROOT", "/data"),
    )
    if not _jsonl_window_has_source(root, window_start, now):
        # No DB pool AND no JSONL file present for the window = no source could
        # be consulted -> UNKNOWN (P0-1). Returning Decimal("0") here is exactly
        # the fail-open bug: a missing ledger is not proof of zero spend.
        logger.warning(
            "cost_breaker: no data source for %s (no pool, no JSONL under %s) "
            "-> spend UNKNOWN",
            provider,
            root,
        )
        return None
    rows = list(_iter_jsonl_rows(root, window_start, now))
    return sum_rows_in_window(rows, provider, window_start, now)


def _jsonl_window_has_source(
    jsonl_root: Path,
    window_start: datetime,
    now: datetime,
) -> bool:
    """True if at least one daily JSONL file overlapping the window exists.

    Distinguishes "source present but empty" (KNOWN zero) from "no source at
    all" (UNKNOWN). A present-but-unreadable file (OSError on open) also counts
    as a consultable source here; the read itself logs + skips it, but its mere
    presence is treated as "we tried" — conservatively, callers that want to
    fail closed on an unreadable file rely on the DB path's try/except. The
    common fail-open trap is the *missing* ledger, which this catches.
    """
    day = window_start.astimezone(timezone.utc).date()
    end_day = now.astimezone(timezone.utc).date()
    while day <= end_day:
        if (jsonl_root / f"llm_cost_log.{day.isoformat()}.jsonl").is_file():
            return True
        day += timedelta(days=1)
    return False


async def _pg_provider_spend(
    conn_or_pool: Any,
    provider: str,
    window_start: datetime,
    now: datetime,
) -> Decimal | None:
    """Run the provider window-sum against asyncpg (Connection or Pool).

    Mirrors cost_advisor_cli.run_daily_cap_check's SUM(cost_usd) idiom but
    scoped to the provider ALIAS SET (so ``anthropic`` rows count toward
    ``claude_oauth``, P0-2) and a parameterised window anchored on the injected
    ``now`` (``ts_utc >= window_start AND ts_utc <= now``, P1-1/P1-2 — clock
    injectable + future-dated rows excluded), riding
    idx_llm_cost_provider_ts (provider, ts_utc DESC).

    FAIL-CLOSED (P0-1/G4): any DB error is caught and surfaced as ``None``
    (spend UNKNOWN) — never a crash (which would abort the whole run) and never
    a silent Decimal("0") (which would fail OPEN to ALLOW).
    """
    aliases = _pg_alias_set(provider)
    sql = """
        SELECT COALESCE(SUM(cost_usd), 0)
        FROM llm_cost_events
        WHERE provider = ANY($1::text[])
          AND ts_utc >= $2
          AND ts_utc <= $3
    """
    try:
        if hasattr(conn_or_pool, "acquire"):
            async with conn_or_pool.acquire() as conn:
                value = await conn.fetchval(sql, aliases, window_start, now)
        else:
            value = await conn_or_pool.fetchval(sql, aliases, window_start, now)
    except Exception as exc:  # noqa: BLE001 — fail-closed on ANY DB error (P0-1)
        # asyncpg raises a wide tree (PostgresError, InterfaceError, OSError,
        # asyncio.TimeoutError, ...). A money-guard must treat ALL of them as
        # spend-UNKNOWN, not crash and not fall through to ALLOW.
        logger.warning(
            "cost_breaker: PG spend read failed for %s (%s) -> spend UNKNOWN",
            provider,
            exc,
        )
        return None
    return _safe_decimal(value) or Decimal("0")


def _pg_alias_set(provider: str) -> list[str]:
    """All raw ledger labels that fold onto ``provider``'s canonical key.

    The PG ``provider`` column stores caller-verbatim strings, so to count an
    ``anthropic`` row toward ``claude_oauth`` we query ``provider = ANY(aliases)``
    where ``aliases`` is every exact alias mapping to the same canonical key.
    Model-suffixed variants (``gemini-flash``) are NOT enumerable as exact
    strings, so the PG path matches exact aliases only; the JSONL/pure path
    handles suffix-folding in Python. Conservative: the canonical key itself is
    always included.
    """
    canonical = _normalize_provider(provider)
    aliases = {canonical}
    for raw, mapped in _PROVIDER_ALIASES.items():
        if mapped == canonical:
            aliases.add(raw)
    return sorted(aliases)


# ---------------------------------------------------------------------------
# Telegram push (STOP only — G1 keeps ALLOW silent)
# ---------------------------------------------------------------------------


def build_stop_message(
    provider: str, spend: Decimal | None, config: BreakerConfig,
) -> str:
    """Build the STOP push — a CHOICE, never a bare diagnosis (G3).

    Always contains the action options [D]egrade / [P]ause / [C]ontinue so a
    human can act, not just be told. The diagnosis (provider/spend/window) is
    context, the options are the point. ``spend`` is normally a known Decimal
    (STOP only fires on a known overspend); a defensive None renders as "n/a".
    """
    budget = config.budget_for(provider)
    window_h = config.window_seconds / 3600.0
    budget_str = f"${budget}" if budget is not None else "n/a"
    spend_str = f"${spend:.2f}" if spend is not None else "$n/a"
    return (
        f"🛑 cost-breaker: budget {provider} exhausted "
        f"(spend {spend_str} / {budget_str} in last {window_h:.0f}h). "
        f"What do you want? [D]egrade to next tier ({next_tier(provider) or 'none'}) "
        f"/ [P]ause provider / [C]ontinue anyway?"
    )


def send_telegram(text: str, *, chat_id: str = _TELEGRAM_CHAT_ID) -> bool:
    """Send a Telegram message via direct Bot API. Logs + swallows errors.

    Returns True if a POST was attempted (token present), False if skipped.
    Mirrors cost_advisor_cli.send_telegram. Never raises.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning(
            "cost_breaker: TELEGRAM_BOT_TOKEN unset — would have sent: %s",
            text[:200],
        )
        return False
    try:
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — fixed api.telegram.org host
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=15,
        )
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("cost_breaker: telegram delivery failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Decision (verdict + side-effects glue) — pure verdict + injectable push
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakerDecision:
    """Result of a full provider check: the verdict + the chosen next tier.

    ``spend_usd`` is ``None`` when spend was UNKNOWN (fail-closed DEGRADE, G4) —
    a genuine read is a Decimal (possibly 0).
    """

    provider: str
    spend_usd: Decimal | None
    verdict: Verdict
    next_tier: str | None


def _push_cooldown_active(provider: str, cooldown_sec: int, *, now: float | None = None) -> bool:
    """True if a STOP push for ``provider`` fired within ``cooldown_sec`` (P2-1).

    Best-effort: a missing/unreadable state file means NOT in cooldown (push
    proceeds — fail toward notifying, since this guards money). ``now`` is
    injectable for tests.
    """
    if cooldown_sec <= 0:
        return False
    path = _COOLDOWN_STATE_DIR / f"cost_breaker_cooldown_{provider}"
    try:
        last = path.stat().st_mtime
    except OSError:
        return False
    current = now if now is not None else datetime.now(timezone.utc).timestamp()
    return (current - last) < cooldown_sec


def _push_cooldown_set(provider: str) -> None:
    """Mark a STOP push for ``provider`` as just-sent (touch the state file)."""
    path = _COOLDOWN_STATE_DIR / f"cost_breaker_cooldown_{provider}"
    try:
        _COOLDOWN_STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError as exc:
        logger.warning("cost_breaker: cannot set push cooldown for %s: %s", provider, exc)


def _push_cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the STOP-push cooldown from env, default 1h. Invalid -> default."""
    env = os.environ if env is None else env
    raw = env.get("COST_BREAKER_PUSH_COOLDOWN_SEC")
    if raw is None:
        return _DEFAULT_PUSH_COOLDOWN_SEC
    try:
        candidate = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_PUSH_COOLDOWN_SEC
    return candidate if candidate >= 0 else _DEFAULT_PUSH_COOLDOWN_SEC


def decide(
    provider: str,
    spend: Decimal | None,
    config: BreakerConfig,
    *,
    push: Any = None,
    cooldown_sec: int | None = None,
) -> BreakerDecision:
    """Compute the verdict and run side-effects per gate contract.

    - ALLOW  -> ZERO push (G1). Returns next_tier = None (stay put).
    - DEGRADE-> returns next_tier (G2). No push (degrade is automatic, silent).
      This includes the fail-closed DEGRADE when ``spend is None`` (UNKNOWN, G4).
    - STOP   -> push a CHOICE message (G3) via ``push`` (defaults to
      send_telegram), SUBJECT TO a per-provider cooldown (P2-1) so a cron re-tick
      does not re-spam. Returns next_tier (may be None at the floor).

    CASCADE-CONSUMER CONTRACT: on DEGRADE/STOP the consumer MUST re-invoke
    ``decide`` on ``next_tier`` before spending on it — this call verifies ONLY
    ``provider`` (see the module docstring).

    ``push`` is injectable for testing (G1/G3 assertions). It must accept the
    message string as its first positional arg and return truthy on send.
    ``cooldown_sec`` is injectable for tests (None -> resolve from env).
    """
    push_fn = send_telegram if push is None else push
    # Preserve None (UNKNOWN) through to the verdict — do NOT coerce to 0 here,
    # that was the fail-open bug. A non-None-but-uncoercible value is handled by
    # evaluate (treated as UNKNOWN -> fail-closed).
    verdict = evaluate(provider, spend, config)
    spend_known = spend if spend is None else _safe_decimal(spend)

    if verdict is Verdict.ALLOW:
        return BreakerDecision(provider, spend_known, verdict, None)

    if verdict is Verdict.DEGRADE:
        return BreakerDecision(provider, spend_known, verdict, next_tier(provider))

    # STOP — the one and only push, gated by the per-provider cooldown (P2-1).
    effective_cooldown = (
        _push_cooldown_seconds() if cooldown_sec is None else cooldown_sec
    )
    if not _push_cooldown_active(provider, effective_cooldown):
        push_fn(build_stop_message(provider, spend_known, config))
        _push_cooldown_set(provider)
    else:
        logger.info(
            "cost_breaker: STOP push for %s suppressed (cooldown %ss active)",
            provider,
            effective_cooldown,
        )
    return BreakerDecision(provider, spend_known, verdict, next_tier(provider))


# ---------------------------------------------------------------------------
# CLI (operator one-shot check; no scheduled side-effects on import)
# ---------------------------------------------------------------------------


async def _check_all(config: BreakerConfig) -> int:
    """Check every guarded provider against the live ledger. Returns max-severity
    exit code: 0 ALLOW-only, 1 any DEGRADE, 2 any STOP.

    A spend-read that returns None (UNKNOWN — DB error or no source) is mapped
    by ``decide`` to a fail-closed DEGRADE (G4), so it contributes exit code 1,
    NOT 0. The read never crashes the run (``_pg_provider_spend`` catches).
    """
    worst = 0
    for provider in GUARDED_PROVIDERS:
        spend = await provider_spend_in_window(provider, config.window_seconds)
        decision = decide(provider, spend, config)
        spend_repr = "UNKNOWN" if decision.spend_usd is None else f"${decision.spend_usd}"
        logger.info(
            "cost_breaker: %s spend=%s verdict=%s next_tier=%s",
            provider,
            spend_repr,
            decision.verdict.value,
            decision.next_tier,
        )
        if decision.verdict is Verdict.STOP:
            worst = max(worst, 2)
        elif decision.verdict is Verdict.DEGRADE:
            worst = max(worst, 1)
    return worst


def main(argv: list[str] | None = None) -> int:
    """Operator CLI: `python3 scripts/cost_breaker.py` checks all providers."""
    import argparse
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=None,
        help="Override the window (default from env or 24h).",
    )
    args = parser.parse_args(argv)
    config = BreakerConfig.from_env()
    if args.window_seconds is not None and args.window_seconds > 0:
        config = BreakerConfig(
            budgets_usd=config.budgets_usd,
            threshold_fraction=config.threshold_fraction,
            window_seconds=args.window_seconds,
        )
    return asyncio.run(_check_all(config))


if __name__ == "__main__":
    raise SystemExit(main())

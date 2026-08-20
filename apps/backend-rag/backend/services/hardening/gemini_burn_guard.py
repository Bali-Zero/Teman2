"""GeminiBurnGuard — early warning on an accelerating Gemini prepay burn.

``llm_credit_sentinel`` (2026-07-28) catches a depletion *after* it happens,
in minutes instead of the ~34h it used to take. It cannot do better than
that by construction: Google's AI Studio pay-as-you-go API exposes no
remaining-balance figure anywhere — verified against the installed
``google-genai`` SDK (2026-08-20), which carries no billing/balance call,
only a `quota_project_id` auth concept and per-request billing *labels*.
So a "days of autonomy left" projection, the kind you can compute for a
gas tank, is not obtainable here: nobody, including this code, knows the
size of the tank.

What IS obtainable — and what this module watches — is the *rate* of
spend, from ``llm_cost_events`` (the ledger every Gemini call already
writes to, migration 117). Checked this against the real incident this
module exists for: of the failure timestamps in
``cron-llm-credit-sentinel`` run history, most (2026-08-06, two of the
three 08-12 blips, 08-17) turned out on inspection to be GitHub Actions
infrastructure noise unrelated to Gemini at all (the `setup-flyctl`
action download hitting GitHub's own rate limit / a transient socket
error — verified by reading each run's raw log, not inferred from the
"failure" conclusion). The one genuine, sustained depletion in that
window — the one that silenced WhatsApp — was NOT flat: llm_cost_events
at hourly resolution shows spend jump from near-zero to ~$1-2.4/hour
starting 2026-08-09 18:00 UTC and stay elevated for ~56 hours (with two
brief self-recovering flutters) before the sustained wall on 08-11
~05:00. A 72h-vs-14d guard sampling every 3h would have measured that
ramp on its first tick after onset, ~32 hours before the wall. This
module does not claim to catch every future depletion — Google's API
still exposes no balance to make that guarantee possible — but the one
real case checked here IS the ramp shape, not the flat one.

Two numbers only, both honest about what they are:
    recent   — total $ spent on Gemini in the last N hours (default 72h)
    baseline — the SAME window length's worth of spend, from a trailing
               14-day average (excludes the recent window itself)

``recent / baseline > ratio_threshold`` (default 3.0x — the same
multiplier ``quota_monitor`` and ``cost_advisor`` already use for spike
detection on this exact ledger, not a new number invented for this
module) is the only thing this guard alerts on. It never asserts a
remaining-balance number, and it says so in the alert text every time.

Fail-open by construction: a failure to read the ledger produces
``CANNOT_VERIFY``, never ``NORMAL`` (which would be a false all-clear)
and never ``ACCELERATING`` (which would be a false alarm on a premise
that was never measured). See cicatrix-superscar.md family #9 (W106b):
"a healer that reads 'there is a fork' when the truth is 'I could not
check' spends a session on a false premise" — the same doctrine applies
to an alerter.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_RATIO_THRESHOLD = 3.0
DEFAULT_MIN_RECENT_USD = Decimal("1.00")


class BurnState(str, Enum):
    """What the guard could establish. CANNOT_VERIFY never alerts."""

    NORMAL = "normal"
    ACCELERATING = "accelerating"
    CANNOT_VERIFY = "cannot_verify"


@dataclass(frozen=True)
class BurnWindowStats:
    """Pre-aggregated numbers for one window. The guard does no SQL itself —
    the caller (the CLI's DB layer) computes these, so the comparison logic
    below stays unit-testable without a database.

    ``baseline`` windows MUST already be normalised to the SAME wall-clock
    length as the recent window (e.g. a 14-day trailing average scaled down
    to a 72h-equivalent figure) — this module does no unit conversion, only
    a straight ratio.
    """

    total_usd: Decimal
    call_count: int
    top_model: str | None = None
    top_model_usd: Decimal = Decimal("0")


@dataclass(frozen=True)
class BurnVerdict:
    state: BurnState
    detail: str = ""
    recent_usd: Decimal = Decimal("0")
    baseline_usd: Decimal = Decimal("0")
    ratio: float | None = None

    @property
    def should_alert(self) -> bool:
        """Only a positively-measured acceleration is worth waking anyone for."""
        return self.state is BurnState.ACCELERATING


FetchFn = Callable[[], Awaitable[tuple[BurnWindowStats, BurnWindowStats]]]
NotifyFn = Callable[[str], Awaitable[bool]]

_AUTONOMY_DISCLAIMER = (
    "Non conosco il credito residuo (Google non lo espone via API): questo è un "
    "segnale di RITMO di consumo, non un conto alla rovescia."
)


class GeminiBurnGuard:
    """Compare recent Gemini spend against its own trailing baseline.

    ``fetch`` returns ``(recent, baseline)`` — both already computed by the
    caller against ``llm_cost_events``. Every notifier is tried even if an
    earlier one fails, matching ``LLMCreditSentinel``'s doctrine: one dead
    channel must never mute the others.
    """

    def __init__(
        self,
        fetch: FetchFn,
        notifiers: dict[str, NotifyFn],
        *,
        ratio_threshold: float = DEFAULT_RATIO_THRESHOLD,
        min_recent_usd: Decimal = DEFAULT_MIN_RECENT_USD,
        window_label: str = "72h",
    ) -> None:
        self._fetch = fetch
        self._notifiers = notifiers
        self._ratio_threshold = ratio_threshold
        self._min_recent_usd = min_recent_usd
        self._window_label = window_label

    async def check(self) -> BurnVerdict:
        try:
            recent, baseline = await self._fetch()
        except BaseException as exc:  # broad on purpose: classifying, not handling
            verdict = BurnVerdict(
                BurnState.CANNOT_VERIFY,
                f"{type(exc).__name__}: {exc}"[:400],
            )
            logger.warning(
                "🔎 [GeminiBurnGuard] impossibile leggere llm_cost_events — %s",
                verdict.detail,
            )
            return verdict

        verdict = self._classify(recent, baseline)

        if not verdict.should_alert:
            logger.info(
                "🔎 [GeminiBurnGuard] state=%s (nessun allarme) — %s",
                verdict.state.value,
                verdict.detail[:200],
            )
            return verdict

        logger.warning("⚡ [GeminiBurnGuard] BURN IN ACCELERAZIONE — %s", verdict.detail)
        text = _alert_text(verdict, self._window_label)
        for channel, notify in self._notifiers.items():
            try:
                ok = await notify(text)
                logger.info(
                    "⚡ [GeminiBurnGuard] alert su %s: %s",
                    channel,
                    "consegnato" if ok else "NON consegnato",
                )
            except Exception as exc:  # one dead channel must not mute the others
                logger.warning("⚡ [GeminiBurnGuard] alert su %s fallito: %s", channel, exc)
        return verdict

    def _classify(self, recent: BurnWindowStats, baseline: BurnWindowStats) -> BurnVerdict:
        # No baseline history yet (cold data, or a ledger gap) — a ratio
        # against zero is undefined, not "infinite acceleration". Stay quiet,
        # same doctrine as quota_monitor's "spike_without_prior_history".
        if baseline.total_usd <= 0:
            return BurnVerdict(
                BurnState.NORMAL,
                f"nessuna baseline (14gg) contro cui confrontare — recent=${recent.total_usd:.4f}",
                recent_usd=recent.total_usd,
                baseline_usd=baseline.total_usd,
            )

        # Below the noise floor — $0.01 vs $0.001 is technically "10x" and
        # means nothing. Same doctrine as quota_monitor's spike_min_abs_usd.
        if recent.total_usd < self._min_recent_usd:
            return BurnVerdict(
                BurnState.NORMAL,
                f"sotto la soglia di rilevanza (${self._min_recent_usd}) — "
                f"recent=${recent.total_usd:.4f}",
                recent_usd=recent.total_usd,
                baseline_usd=baseline.total_usd,
            )

        ratio = float(recent.total_usd / baseline.total_usd)
        if ratio <= self._ratio_threshold:
            return BurnVerdict(
                BurnState.NORMAL,
                f"ritmo normale — recent=${recent.total_usd:.4f} "
                f"baseline=${baseline.total_usd:.4f} ({ratio:.1f}x)",
                recent_usd=recent.total_usd,
                baseline_usd=baseline.total_usd,
                ratio=ratio,
            )

        cause = (
            f"{recent.top_model} (${recent.top_model_usd:.4f} dei ${recent.total_usd:.4f})"
            if recent.top_model
            else "modello non attribuibile (endpoint/model non taggato sulla riga)"
        )
        return BurnVerdict(
            BurnState.ACCELERATING,
            f"recent=${recent.total_usd:.4f} vs baseline=${baseline.total_usd:.4f} "
            f"({ratio:.1f}x soglia {self._ratio_threshold}x) — trainato da {cause}",
            recent_usd=recent.total_usd,
            baseline_usd=baseline.total_usd,
            ratio=ratio,
        )


def _alert_text(verdict: BurnVerdict, window_label: str) -> str:
    return (
        f"⚡ Gemini burn-rate in accelerazione ({window_label})\n\n"
        f"{verdict.detail}\n\n"
        f"{_AUTONOMY_DISCLAIMER}\n\n"
        "Se il ritmo continua e i crediti si esauriscono, il sentinel esistente "
        "(cron ogni 20 min) lo rileva entro minuti — questo alert serve a "
        "muoversi PRIMA di quel punto, verificando se il volume è atteso "
        "(campagna, picco traffico) o un guasto (loop, retry impazzito)."
    )

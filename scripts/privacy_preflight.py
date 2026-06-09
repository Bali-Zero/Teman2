"""P2 confine-PII router — the Law-2 gate in front of every cloud dispatch.

CRITICO-2 / Pezzo 2, MVL Step B+C. Decides LOCAL-vs-CLOUD for a prompt BEFORE
any cloud LLM (Gemini/Codex/DeepSeek) can see it. The posture is
air-gap-first + defense-in-depth (spec `research/operations/specs/
P2-router-confine-pii.md` §3): NOT "clean-then-send", but "decide local-vs-
cloud first; if it touches PII it runs LOCAL only and the cloud key is never
reached on that path".

Honesty (DeepSeek council §7.3.2): this is the MOST ROBUST available
countermeasure, NOT a guarantee. Every strato is best-effort; their
COMPOSITION lowers the false-negative floor. Default is LOCAL on any ambiguity
or error (fail-closed).

Strata, evaluated cheapest-first:

  STRATO A — whitelist-positiva. A DECLARED task_type that is NOT in the
             cloud-safe whitelist → LOCAL. A DECLARED whitelisted type is a
             cloud CANDIDATE (still gated by B/B+/C). An UNDECLARED type
             (task_type=None, the production chokepoint) is NOT denied here —
             it is content-gated by B/B+/C — unless `strict_default_deny=True`.
             So STRATO A is default-DENY only for declared non-whitelisted
             types, NOT a blanket default-DENY at the chokepoint (see HONEST
             posture note below). POSITIVE whitelist, never a PII blacklist.
  STRATO B — deterministic structured-PII regex backstop (KTP / NPWP /
             passport / +62 phone / WhatsApp-JID), seeded from `pii_scanner.py`
             and hardened against separator/case false-negatives (scans the raw
             AND digit-normalized prompt). A match forces LOCAL. Immune to a
             wrong LLM classifier; false-positives are SAFE (route local, never
             leak).
  STRATO B+ — deterministic PII-CONTEXT backstop. A bare CRM name cannot be
             regex-matched, but client/PII prompts almost always carry a
             context signal (an ID-type word, a CRM/client reference, an
             Indonesian honorific before a name, a contact handle). Any signal
             forces LOCAL. Dependency-free — this is what holds the line when
             STRATO C is degraded (PG out of scope). Closes the bare-name leak
             the council flagged, except for a truly context-free bare name.
  STRATO C — `_redact_pii.py` redactor, fail-closed. If the redactor refuses
             (raises) OR MODIFIES the text (PII was present), → LOCAL
             (Codex §7.2.1: redactor-modifies ⇒ cloud-vietato). Only an
             unchanged prompt passes to CLOUD.

HONEST posture at the wired chokepoint (panel F2): `run_dispatch` calls this
with task_type=None, so STRATO A whitelist does NOT default-DENY there — the
chokepoint gate is STRATO B + B+ + C. STRATO A's whitelist-DENY applies only
when a caller passes a DECLARED task_type. The whole gate is best-effort
multi-strato (spec §0), NOT a guarantee.

Posture of STRATO C (`require_redactor`):
  - True  (cloud-egress strict): the redactor MUST be buildable and must not
            raise; any failure → LOCAL (fail-CLOSED). Use when un-redacted CRM
            names leaving the machine is unacceptable AND PG is wired in.
  - False (federation MVL default): the regex backstop (STRATO B) is the hard,
            dependency-free gate. The redactor is best-effort: if it cannot be
            built (e.g. Postgres out of scope, no DATABASE_URL) the gate
            DEGRADES to regex-only with a WARN — strictly better than the prior
            zero-gate state, without making federation unusable (which would
            get the gate bypassed — Gemini council §7.1.5). A redactor that
            builds but RAISES is still treated as a PII signal → LOCAL.

Deferred beyond this MVL (honest scope, spec §9 defines MVL = preflight +
fix-2-bug + whitelist-positiva):
  - The Qwen-9B LLM sensitivity auto-detect (the FULLER form of STRATO A in
    spec §3) is NOT included. The deterministic whitelist-positiva is the
    primary STRATO A gate here; an LLM refinement would add latency + a network
    dependency + non-determinism for best-effort coverage. It can be layered in
    later as a downgrade-only tightener (it may move CLOUD→LOCAL, never the
    reverse).
  - STRATO D (Presidio guardrail) and the burst-cloud capability layer
    (BURST_CLOUD_ENABLED, requires an empirical threshold benchmark — Law 7)
    are separate follow-ups.
  - P2 → P3 dependency stands: this gate sanitises the PROMPT, but a cloud
    agent that reads repo files directly can still leak (spec §7.1.3). The
    sandbox (P3, #1170) is the complementary control.
  - Chokepoint scope (panel F5): the gate lives in
    `federation_orchestrator.run_dispatch`. A caller that invokes
    `scripts/ai-dispatch.sh <cloud-cmd>` DIRECTLY bypasses it. The complete fix
    is to move the preflight into `ai-dispatch.sh` (or a shared egress wrapper)
    so every cloud path is funneled through it — deferred (bash-side). For now,
    federation is the enforced path.
  - Residual best-effort floor: a truly context-free bare CRM name
    ("fix the bug for <Name>", no ID, no context word) with PG out of scope can
    still reach CLOUD. Wiring DATABASE_URL into federation's env +
    PRIVACY_PREFLIGHT_STRICT=true (full CRM-name redaction) or the deferred
    local Qwen-NER closes it. This matches spec §0: structurally best-effort.

Compliance: Symbiosis Law 2 (OSINT/PII never leaves the Pro), UU PDP.
Audit logs hash+length+decision ONLY — NEVER the raw prompt (it may carry PII).
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_AUDIT_PATH = _PROJECT_ROOT / "ai-dispatch-output" / "privacy_preflight_audit.jsonl"


class Route(enum.Enum):
    LOCAL = "local"
    CLOUD = "cloud"


# STRATO A — POSITIVE whitelist of cloud-safe DECLARED task types (Codex §7.2.3).
# Anything not listed here is NOT a cloud candidate (default-DENY). This is the
# opposite of a PII blacklist: we name what is safe, not what is dangerous.
CLOUD_SAFE_TASK_TYPES = frozenset(
    {
        "PUBLIC_CODE_REPO",  # public/non-client repo code
        "PUBLIC_DOCS_RESEARCH",  # public docs / web research
        "SYNTHETIC_TEST",  # synthetic fixtures, no real PII
        "ARCHITECTURE_META",  # architecture / meta reasoning, no client data
    }
)


@dataclass(frozen=True)
class Decision:
    """The routing verdict. `route` is the only load-bearing field; `layer`
    and `blocked_reason` are for audit/observability."""

    route: Route
    layer: str
    blocked_reason: Optional[str] = None

    @property
    def is_cloud(self) -> bool:
        return self.route is Route.CLOUD


# STRATO B — deterministic structured-PII regex backstop. Seeded from the
# Indonesian recognizers in apps/backend-rag/backend/middleware/pii_scanner.py,
# then hardened against the panel's separator/case false-negatives (DeepSeek
# §3, Codex §4). The scan runs against BOTH the raw prompt AND a
# digit-separator-normalized copy, so "3171 2345 6789 0123" / "3171.2345..."
# / "+62 812-3456-7890" all reduce to the contiguous form and still match.
# False-POSITIVES are SAFE here: a wrong match only routes LOCAL, it never leaks.
_BACKSTOP_PATTERNS: dict[str, re.Pattern[str]] = {
    "KTP_16": re.compile(r"\b\d{16}\b"),
    "NPWP_15": re.compile(r"\b\d{15}\b"),  # plain 15-digit NPWP (DeepSeek §3)
    "NPWP_DOTTED": re.compile(r"\b0?\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b"),
    # case-insensitive + tolerates ONE separator between the letters and digits
    # ("A 1234567" / "A-1234567"), DeepSeek round-2. Boundary-preserving (no
    # string mutation), so it can't merge neighbouring words like the global
    # digit-normalizer would.
    "PASSPORT_ID": re.compile(r"\b[A-Za-z]{1,2}[ .\-]?\d{6,7}\b"),
    "PHONE_62": re.compile(r"\+?62\d{8,13}"),  # +62 / 62, separators normalized
    "PHONE_08": re.compile(r"\b08\d{8,11}\b"),
    "WA_JID": re.compile(r"\b\d{8,15}@s\.whatsapp\.net\b"),
}

# Collapse a RUN of separator characters that sits BETWEEN TWO DIGITS so an ID
# or phone pasted from a spreadsheet/copy reduces to its contiguous form before
# the structured scan. The M5 24-agent review reproduced a Law-2 leak where
# "3171,2345,6789,0123" (comma) + underscore/slash/NBSP/zero-width variants were
# NOT normalized, so \b\d{16}\b never matched and the prompt routed CLOUD. The
# follow-up re-panel (DeepSeek+Codex) then proved the dash FAMILY and fullwidth
# punctuation (autocorrect/CJK paste) still leaked - U+2010 plain hyphen,
# U+2011/2013/2014 dashes, U+00AD soft-hyphen, U+2060 word-joiner, U+FF0C/FF0E
# fullwidth comma/period, etc. Rather than enumerate code points (brittle), the
# separator class is built from Unicode CATEGORIES via the stdlib `unicodedata`
# (no 3rd-party `regex` dep): every dash (Pd), every format/invisible char (Cf -
# soft-hyphen, zero-width, word-joiner, BOM), every space (Zs), plus an explicit
# ASCII + fullwidth punctuation set. Stays current with Unicode automatically.
#
# STRICTLY between-digits (lookbehind+lookahead both \d) so it NEVER merges a
# neighbouring WORD into the digit run (that would destroy the \b boundaries the
# patterns rely on) and leaves alphabetic prose between numbers intact
# ("4 cats and 8 dogs"). Letter-then-digit cases (passport "A 1234567") are
# handled by the separator-tolerant PASSPORT_ID pattern. Applied ONLY to a
# match-copy - the dispatched prompt is NEVER mutated. Any over-match is safe
# (routes LOCAL).
_DIGIT_SEP_EXPLICIT = set("\t .,;:_/|-'，．／：；＿｜−")


def _build_digit_separator_class() -> str:
    chars = set(_DIGIT_SEP_EXPLICIT)
    for _cp in range(0xA0, 0x10000):
        if unicodedata.category(chr(_cp)) in ("Zs", "Cf", "Pd"):
            chars.add(chr(_cp))
    return "".join(re.escape(c) for c in sorted(chars))


_DIGIT_SEP_RE = re.compile("(?<=\\d)[\\s" + _build_digit_separator_class() + "]+(?=\\d)")


def _structured_backstop(prompt: str) -> Optional[str]:
    """Return the first structured-PII pattern name that matches (raw OR
    digit-normalized), else None. Deterministic; a hit forces LOCAL."""
    normalized = _DIGIT_SEP_RE.sub("", prompt)
    for name, pattern in _BACKSTOP_PATTERNS.items():
        if pattern.search(prompt) or pattern.search(normalized):
            return name
    return None


# STRATO B+ — deterministic PII-CONTEXT backstop (closes panel F1: the
# bare-CRM-name leak when the redactor is degraded/static-only because PG is out
# of scope). A bare name cannot be regex-matched, but client/PII prompts almost
# always carry a CONTEXT signal — an ID-type word, a CRM/client reference, an
# Indonesian honorific that precedes a person's name, or a contact handle. Any
# such signal forces LOCAL. This is dependency-free (no PG, no LLM) and
# case-insensitive. It does NOT catch a truly context-free bare name — that
# residual is documented (wire PG / the deferred local Qwen-NER closes it).
# Single-token signals matched on WORD BOUNDARIES (\b), case-insensitive — so
# "SKCK Budi" at the START of a prompt and "Pak, Budi" with punctuation BOTH
# match (the prior leading/trailing-space substring hack missed those — Codex
# round-2, and the W73 `_guard_*` bare-substring/space-hack scar). Boundaries
# also avoid matching inside longer words (no "pak" in "package").
_PII_CONTEXT_WORDS: tuple[str, ...] = (
    # ID / document types
    "ktp", "nik", "npwp", "kitas", "kitap", "imta", "paspor", "passport",
    "akta", "akte", "skck", "rekening", "norek",
    # CRM / client references
    "crm", "klien", "cliente",
    # Indonesian honorifics that precede a person name
    "bapak", "ibu", "pak", "bu", "bpk", "sdr", "sdri", "saudara", "saudari",
    # contact handle
    "whatsapp",
)
_PII_CONTEXT_WORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _PII_CONTEXT_WORDS) + r")\b",
    re.IGNORECASE,
)

# Multi-token / punctuated phrases — distinctive enough to match as plain
# case-insensitive substrings (their internal spaces/dots ARE the signal).
_PII_CONTEXT_PHRASES: tuple[str, ...] = (
    "the client", "our client", "this client", "client's",
    "atas nama", "a.n.", "a/n", "data pribadi", "personal data",
    "bank account", "no rekening", "no. rekening",
    "visa applicant", "wa number", "nomor wa", "no wa", "s.whatsapp.net",
    "mr.", "mrs.", "ms.",
)


def _context_backstop(prompt: str) -> Optional[str]:
    """Return the first PII-context signal found (case-insensitive), else None.
    Word-boundary for single tokens, substring for punctuated phrases."""
    m = _PII_CONTEXT_WORDS_RE.search(prompt)
    if m:
        return m.group(0).lower()
    low = prompt.lower()
    for phrase in _PII_CONTEXT_PHRASES:
        if phrase in low:
            return phrase
    return None


def _default_redactor(strict: bool) -> Any:
    """Build the production redactor. `strict` maps to the FASE-2
    `require_dynamic_names` flag: True = PG MUST yield CRM names (cloud-egress),
    False = static passes only when PG is out of scope."""
    from _redact_pii import Redactor  # bare import (scripts/ on sys.path)

    return Redactor.load_default(require_dynamic_names=strict)


def _normalize_task_type(task_type: Optional[str]) -> Optional[str]:
    """Panel F4: a caller-supplied task_type is UNTRUSTED — it could itself be
    a client name. Only echo a recognized, declared type into the audit log;
    anything else collapses to a constant so the audit never becomes a PII
    side-channel."""
    if task_type is None:
        return None
    return task_type if task_type in CLOUD_SAFE_TASK_TYPES else "<non-standard>"


def _audit(
    prompt: str, task_type: Optional[str], decision: Decision, audit_path: Optional[Path]
) -> None:
    """Append ONE decision row. Law 2: hash + length only, NEVER the raw prompt
    and NEVER an untrusted caller string (task_type is normalized)."""
    path = audit_path or _DEFAULT_AUDIT_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "prompt_sha256_16": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            "prompt_len": len(prompt),
            "task_type": _normalize_task_type(task_type),
            "route": decision.route.value,
            "layer": decision.layer,
            "blocked_reason": decision.blocked_reason,
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # audit must never break the gate
        logger.warning("privacy_preflight audit write failed", exc_info=True)


def _decide(
    prompt: str,
    task_type: Optional[str],
    redactor: Any,
    redactor_factory: Optional[Callable[[bool], Any]],
    require_redactor: bool,
    strict_default_deny: bool,
) -> Decision:
    if not prompt or not prompt.strip():
        return Decision(Route.LOCAL, "empty", "empty_prompt")

    # STRATO A — whitelist-positiva (default-DENY for DECLARED types). The raw
    # task_type is NEVER interpolated into the reason (panel F4: a caller could
    # pass task_type="CLIENT_BUDI_SANTOSO" — that name must not reach the audit
    # log or the blocked response). The normalized task_type is recorded by the
    # audit layer separately.
    if task_type is not None and task_type not in CLOUD_SAFE_TASK_TYPES:
        return Decision(Route.LOCAL, "whitelist", "task_type_not_cloud_safe")
    if task_type is None and strict_default_deny:
        return Decision(Route.LOCAL, "whitelist", "undeclared_task_type_strict_deny")

    # STRATO B — deterministic structured-PII regex backstop (dependency-free).
    hit = _structured_backstop(prompt)
    if hit:
        return Decision(Route.LOCAL, "regex_backstop", f"regex:{hit}")

    # STRATO B+ — deterministic PII-CONTEXT backstop. Closes the bare-CRM-name
    # leak (panel F1) WITHOUT needing PG: a client/PII prompt almost always
    # carries a context signal even when no structured ID is present. Runs
    # BEFORE STRATO C so the gate holds even when the redactor is degraded.
    ctx = _context_backstop(prompt)
    if ctx:
        return Decision(Route.LOCAL, "context_backstop", f"context:{ctx}")

    # STRATO C — redactor, fail-closed.
    redactor_obj = redactor
    if redactor_obj is None:
        factory = redactor_factory or _default_redactor
        try:
            redactor_obj = factory(require_redactor)
        except Exception as exc:
            if require_redactor:
                return Decision(
                    Route.LOCAL, "redactor", f"redactor_init_failclosed:{type(exc).__name__}"
                )
            # degraded MVL posture: regex already gated structured PII; proceed
            # to CLOUD on a clean prompt but make the gap observable.
            logger.warning(
                "privacy_preflight: redactor unavailable (%s) — STRATO C DEGRADED to "
                "regex-only for this dispatch (PG out of scope?). CRM-name coverage "
                "is reduced; set PRIVACY_PREFLIGHT_STRICT=true to fail-closed instead.",
                type(exc).__name__,
            )
            redactor_obj = None

    if redactor_obj is not None:
        try:
            redacted = redactor_obj.redact(prompt)
        except Exception as exc:
            # a redactor that refuses is a strong PII signal → LOCAL, in BOTH
            # strict and degraded modes.
            return Decision(Route.LOCAL, "redactor", f"redactor_refused:{type(exc).__name__}")
        if redacted != prompt:
            return Decision(Route.LOCAL, "redactor", "redactor_found_pii")

    # all strata passed (or STRATO C degraded with a clean regex result) → CLOUD.
    return Decision(Route.CLOUD, "clean", None)


def privacy_preflight(
    prompt: str,
    task_type: Optional[str] = None,
    *,
    redactor: Any = None,
    redactor_factory: Optional[Callable[[bool], Any]] = None,
    require_redactor: Optional[bool] = None,
    strict_default_deny: bool = False,
    audit_path: Optional[Path] = None,
) -> Decision:
    """Decide whether `prompt` may go to a cloud LLM. Returns a `Decision`.

    Args:
        prompt: the text about to be dispatched.
        task_type: a DECLARED task type (STRATO A whitelist). None = undeclared
            (content-only gate; the run_dispatch chokepoint uses this).
        redactor: inject a redactor (duck-typed `.redact(str)->str`); tests use
            this. Production builds one lazily.
        redactor_factory: `(strict: bool) -> redactor`; overrides the default
            `_redact_pii.Redactor.load_default`.
        require_redactor: STRATO C posture. None → read env
            `PRIVACY_PREFLIGHT_STRICT` (default False = degraded-ok).
        strict_default_deny: when True, an undeclared task_type (None) routes
            LOCAL at STRATO A. Default False (rely on B+C for undeclared).
        audit_path: override the audit JSONL path (tests).

    Any unexpected internal error fails closed → LOCAL.
    """
    if require_redactor is None:
        require_redactor = os.environ.get("PRIVACY_PREFLIGHT_STRICT", "false").lower() == "true"

    try:
        decision = _decide(
            prompt,
            task_type,
            redactor,
            redactor_factory,
            require_redactor,
            strict_default_deny,
        )
    except Exception as exc:  # fail-closed: NEVER leak on an unexpected error
        logger.warning("privacy_preflight internal error → fail-closed LOCAL", exc_info=True)
        decision = Decision(Route.LOCAL, "exception", f"internal_error:{type(exc).__name__}")

    _audit(prompt, task_type, decision, audit_path)
    return decision

"""Privacy redactor for the agent-library-evolver pipeline.

Loads `agent-library/config/redaction-rules.yaml` and applies the rules
to an input text BEFORE the text is sent to any external LLM (DeepSeek
API, Gemini OAuth, NotebookLM). Fail-closed: any rule application error
or output shorter than `gate.min_remaining_chars` aborts the run.

Compliance:
    Symbiosis Law 2 (OSINT blindato) — OSINT data NEVER leaves Pro.
    UU PDP (Indonesian privacy law) — NPWP, NIB, KTP, KITAS, IMTA,
        passport, client/company names, phone, email, bank account.

Architecture:
    Four-pass logic (panel R2 finding L8/L22 — YAML alone leaks):

      pass1: identifier + internal patterns (NPWP, NIB, KITAS, SHM,
             AKTA, AJB, AHU, OSINT block, IP, ssh alias, fly internal)
      pass2_team_first: team @balizero.com emails + owner gmail +
             phone E.164 / 08xx / WhatsApp JID. Runs BEFORE pass3 so
             that team emails are tokenised BEFORE the generic email
             pattern matches them.
      pass3_generic: generic email (remaining = client/partner/third-
             party), IBAN strict, SWIFT BIC with context, bank account.
      pass4_dynamic: client/company names from PG `clients.full_name`
             + `companies.company_name` (built at runtime, regex alternation).

Usage as module:
    from scripts._redact_pii import Redactor
    r = Redactor.load_default()
    safe = r.redact(raw_context)
    assert len(safe) >= r.config.gate.min_remaining_chars

Usage as CLI:
    python3 scripts/_redact_pii.py < raw_context.md > redacted_context.md

Phase: 1 (addresses L8/L19/L20/L21/L22 from
agent-library/proposals/.known-limitations-v1.md)
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "agent-library"
    / "config"
    / "redaction-rules.yaml"
)


class RedactionError(RuntimeError):
    """Raised when the redactor refuses to produce output (fail-closed)."""


@dataclass
class GateConfig:
    min_remaining_chars: int = 100
    fail_on_error: bool = True
    idempotent: bool = True


@dataclass
class RedactionConfig:
    pass1: list[dict[str, Any]]
    pass2_team_first: list[dict[str, Any]]
    pass3_generic: list[dict[str, Any]]
    pass4_dynamic: list[dict[str, Any]]
    gate: GateConfig


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> RedactionConfig:
    """Parse the YAML config into a typed RedactionConfig."""
    path = Path(path)
    if not path.is_file():
        raise RedactionError(
            f"redaction-rules.yaml not found at {path}. "
            f"Phase 1 redactor cannot run without rules."
        )

    with path.open() as f:
        raw = yaml.safe_load(f)

    gate_raw = raw.get("gate", {}) or {}
    gate = GateConfig(
        min_remaining_chars=int(gate_raw.get("min_remaining_chars", 100)),
        fail_on_error=bool(gate_raw.get("fail_on_error", True)),
        idempotent=bool(gate_raw.get("idempotent", True)),
    )

    return RedactionConfig(
        pass1=raw.get("pass1", []) or [],
        pass2_team_first=raw.get("pass2_team_first", []) or [],
        pass3_generic=raw.get("pass3_generic", []) or [],
        pass4_dynamic=raw.get("pass4_dynamic", []) or [],
        gate=gate,
    )


def _compile_rule(rule: dict[str, Any]) -> re.Pattern[str] | None:
    """Compile a YAML rule's pattern. Returns None for placeholder rules."""
    if "placeholder_id" in rule and "pattern" not in rule:
        return None
    pattern = rule["pattern"]
    return re.compile(pattern)


def _apply_rule(text: str, rule: dict[str, Any], compiled: re.Pattern[str]) -> str:
    """Apply a single rule to text.

    Supports three substitution modes:
        - `replace: "<token>"` — substitute the entire match.
        - `replace_group_<name>: "<token>"` — substitute only the named
          capture group, preserving everything else. Used for context-
          aware rules like NPWP-bare and bank-account that need to keep
          the surrounding label in the output.
        - placeholder rules (no `pattern` key, only `placeholder_id`) are
          handled by `_apply_dynamic_rule`.
    """
    if "replace" in rule:
        return compiled.sub(rule["replace"], text)

    group_replace_keys = [k for k in rule if k.startswith("replace_group_")]
    if not group_replace_keys:
        raise RedactionError(
            f"Rule {rule.get('id', '<no id>')!r} has neither 'replace' "
            f"nor 'replace_group_<name>'."
        )

    def _sub_named_groups(match: re.Match[str]) -> str:
        out = match.group(0)
        for k in group_replace_keys:
            group_name = k.removeprefix("replace_group_")
            try:
                original_group = match.group(group_name)
            except IndexError:
                raise RedactionError(
                    f"Rule {rule.get('id', '<no id>')!r} references group "
                    f"{group_name!r} but the regex has no such named group."
                ) from None
            if original_group is None:
                continue
            out = out.replace(original_group, rule[k])
        return out

    return compiled.sub(_sub_named_groups, text)


def _apply_dynamic_rule(
    text: str, rule: dict[str, Any], runtime_names: dict[str, list[str]]
) -> str:
    """Apply a pass4 dynamic rule by building the alternation at runtime.

    runtime_names maps placeholder_id -> list of names to alternate. If
    no names are available (PG unreachable, empty table), the rule is a
    no-op — but `gate.fail_on_error=True` will catch a hard PG error
    upstream in `Redactor.load_dynamic_names`.
    """
    placeholder_id = rule.get("placeholder_id")
    if not placeholder_id:
        raise RedactionError(
            f"Dynamic rule {rule.get('id', '<no id>')!r} missing placeholder_id."
        )
    names = runtime_names.get(placeholder_id, [])
    if not names:
        logger.warning(
            "Dynamic redaction rule %s has 0 runtime names — no-op.",
            rule.get("id"),
        )
        return text

    # Escape each name (avoid regex injection from a name like "John (Mr.)")
    # then build a single \b(?:Name1|Name2|...)\b alternation.
    escaped = [re.escape(n) for n in names if n.strip()]
    if not escaped:
        return text
    # Sort longest-first so multi-word names match BEFORE their substrings
    # ("Sofia Mueller" before "Sofia").
    escaped.sort(key=len, reverse=True)
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    compiled = re.compile(pattern)
    return compiled.sub(rule["replace"], text)


def _load_pg_names(query: str, pg_url: str | None = None) -> list[str]:
    """Load a single column from PG. Returns empty list if PG unreachable.

    Phase 1 design: the redactor is fail-closed on rule-application
    errors but DEGRADES gracefully when PG is unavailable (LaunchAgent
    may run before postgresql@18 is started). Empty list → dynamic
    rule no-ops with a warning. Operator MUST verify PG was reachable
    by checking the run telemetry.
    """
    # Read DATABASE_URL (canonical name used by wrapper + secrets template),
    # PGURL as legacy fallback. Mismatch was caught by Codex panel R5
    # BLOCKING #6 — wrapper sets DATABASE_URL but redactor was looking
    # at PGURL, causing pass4 dynamic CRM names to silently no-op
    # (CRM client/company names could leak to external LLMs).
    pg_url = pg_url or os.environ.get("DATABASE_URL") or os.environ.get("PGURL")
    if not pg_url:
        logger.warning(
            "DATABASE_URL/PGURL env not set — skipping dynamic name load."
        )
        return []
    try:
        result = subprocess.run(
            ["psql", pg_url, "-tAc", query],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("psql unavailable for dynamic name load: %s", e)
        return []
    if result.returncode != 0:
        logger.warning(
            "psql query failed (rc=%d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class Redactor:
    """Stateful redactor — loads config once + applies on each `.redact()`."""

    def __init__(self, config: RedactionConfig, runtime_names: dict[str, list[str]]):
        self.config = config
        self.runtime_names = runtime_names
        # Pre-compile every rule's pattern at __init__ so a broken regex
        # fails LOUDLY at module load, not on first call.
        self._compiled: dict[str, re.Pattern[str]] = {}
        for pass_list in (
            config.pass1,
            config.pass2_team_first,
            config.pass3_generic,
        ):
            for rule in pass_list:
                rid = rule.get("id")
                if not rid:
                    raise RedactionError(
                        f"Rule missing 'id' field: {rule!r}"
                    )
                compiled = _compile_rule(rule)
                if compiled is not None:
                    self._compiled[rid] = compiled

    @classmethod
    def load_default(cls, pg_url: str | None = None) -> "Redactor":
        """Load config from the canonical path + populate runtime names."""
        config = load_config()
        runtime_names = {
            "__DYNAMIC_CRM_CLIENT_NAMES__": _load_pg_names(
                "SELECT full_name FROM clients WHERE full_name IS NOT NULL;",
                pg_url=pg_url,
            ),
            "__DYNAMIC_CRM_COMPANY_NAMES__": _load_pg_names(
                "SELECT company_name FROM companies WHERE company_name IS NOT NULL;",
                pg_url=pg_url,
            ),
        }
        return cls(config=config, runtime_names=runtime_names)

    def _apply_pass(
        self, text: str, pass_list: list[dict[str, Any]], pass_name: str
    ) -> str:
        for rule in pass_list:
            rid = rule.get("id", "<no id>")
            compiled = self._compiled.get(rid)
            if compiled is None:
                # Static rules from pass1/2/3 all have a compiled pattern;
                # placeholder rules are pass4 and not applied here.
                continue
            try:
                text = _apply_rule(text, rule, compiled)
            except Exception as e:
                if self.config.gate.fail_on_error:
                    raise RedactionError(
                        f"{pass_name} rule {rid!r} raised {type(e).__name__}: {e}"
                    ) from e
                logger.warning("%s rule %s failed: %s", pass_name, rid, e)
        return text

    def _apply_dynamic_pass(self, text: str) -> str:
        for rule in self.config.pass4_dynamic:
            try:
                text = _apply_dynamic_rule(text, rule, self.runtime_names)
            except Exception as e:
                if self.config.gate.fail_on_error:
                    raise RedactionError(
                        f"pass4 dynamic rule {rule.get('id', '?')!r} failed: {e}"
                    ) from e
                logger.warning("pass4 rule %s failed: %s", rule.get("id"), e)
        return text

    def redact(self, text: str) -> str:
        """Apply all 4 passes in order. Returns the redacted text.

        Raises RedactionError if `gate.min_remaining_chars` is violated
        OR (when `gate.idempotent`) a second application produces
        different output.
        """
        if not text or not text.strip():
            raise RedactionError(
                "input text is empty — fail-closed (Phase 1 redactor refuses "
                "to produce empty output that an LLM could interpret as 'no PII')"
            )

        # Pass order is load-bearing (panel R2 finding L8): team emails
        # MUST be substituted before the generic email pattern.
        text = self._apply_pass(text, self.config.pass1, "pass1")
        text = self._apply_pass(text, self.config.pass2_team_first, "pass2")
        text = self._apply_pass(text, self.config.pass3_generic, "pass3")
        text = self._apply_dynamic_pass(text)

        if len(text) < self.config.gate.min_remaining_chars:
            raise RedactionError(
                f"redacted output too short ({len(text)} < "
                f"gate.min_remaining_chars={self.config.gate.min_remaining_chars}). "
                f"Either the redactor over-redacted or the input was nearly "
                f"all PII. Fail-closed."
            )

        if self.config.gate.idempotent:
            # Idempotency check: applying the redactor twice MUST produce
            # the same output. Catches any substitution that introduces
            # new PII-shaped tokens (e.g., a [TEAM-EMAIL-REDACTED] tag
            # that itself looks like an email — it doesn't, but defensive).
            second = text
            second = self._apply_pass(second, self.config.pass1, "pass1-idem")
            second = self._apply_pass(
                second, self.config.pass2_team_first, "pass2-idem"
            )
            second = self._apply_pass(
                second, self.config.pass3_generic, "pass3-idem"
            )
            second = self._apply_dynamic_pass(second)
            if second != text:
                raise RedactionError(
                    "redactor is NOT idempotent (panel R2 finding L4): "
                    "applying twice produces different output. This means "
                    "a substitution token itself matches a redaction "
                    "pattern. Fix the rule that introduces the loop."
                )

        return text


def _cli_main() -> int:
    """CLI entrypoint: read stdin, write redacted stdout."""
    logging.basicConfig(
        level=os.environ.get("REDACT_LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(levelname)s _redact_pii: %(message)s",
    )
    raw = sys.stdin.read()
    try:
        r = Redactor.load_default()
        out = r.redact(raw)
    except RedactionError as e:
        logger.error("RedactionError: %s", e)
        sys.stderr.write(f"FAIL-CLOSED: {e}\n")
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())

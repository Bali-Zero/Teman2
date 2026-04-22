"""L0 YAML rule matcher with payload template substitution.

The RuleMatcher is the first decision tier (L0) of the Supervisor. It loads
a flat list of rules from YAML and returns the first matching ActionDecision
for a given Event — or None if no rule fires. W2 will add L1 (Ollama
classifier), L2 (Claude CLI), and L3 (Consiglio) tiers on top.

Rule schema (see apps/organism/organism/rules/base.yaml):
    rules:
      - id: <human name>
        match:
          kind: <event.kind literal>
          severity: [<allowed severities>]        # optional, defaults to any
          payload.<field>: <literal>              # optional, exact equality
          payload.<field>_gte: <number>           # optional, >= numeric
        action:
          actuator: <actuator name>
          params: {<k>: <v>}                      # "{payload.x}" substituted
        confidence: <float 0..1>

Events with is_actuation=True are always ignored to prevent feedback loops
(e.g. an actuator emitting a follow-up event that would re-trigger the
same rule).
"""
from __future__ import annotations

import re
from typing import Any

import yaml

from organism.schemas import ActionDecision, Event


_TEMPLATE_RE = re.compile(r"\{payload\.(\w+)\}")


class RuleMatcher:
    """Match events against a YAML rule set and emit ActionDecisions."""

    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self.rules = rules

    @classmethod
    def from_yaml_text(cls, text: str) -> "RuleMatcher":
        data = yaml.safe_load(text) or {}
        return cls(rules=data.get("rules", []))

    def match(self, event: Event) -> ActionDecision | None:
        """Return the first matching L0 ActionDecision, or None.

        is_actuation events are skipped to avoid self-triggering loops.
        """
        if event.is_actuation:
            return None
        for rule in self.rules:
            if self._matches(rule.get("match", {}), event):
                params = self._render_params(
                    rule.get("action", {}).get("params", {}), event,
                )
                return ActionDecision(
                    actuator=rule["action"]["actuator"],
                    params=params,
                    confidence=float(rule.get("confidence", 0.8)),
                    tier="L0_yaml",
                    reasoning=f"matched rule {rule.get('id', '<unnamed>')}",
                )
        return None

    def _matches(self, match_spec: dict[str, Any], event: Event) -> bool:
        """True iff every predicate in match_spec holds for the event."""
        for k, v in match_spec.items():
            if k == "kind":
                if event.kind != v:
                    return False
            elif k == "severity":
                allowed = v if isinstance(v, list) else [v]
                if event.severity.value not in allowed:
                    return False
            elif k.startswith("payload."):
                pkey = k[len("payload."):]
                if pkey.endswith("_gte"):
                    real_key = pkey[: -len("_gte")]
                    try:
                        if float(event.payload.get(real_key, 0)) < float(v):
                            return False
                    except (TypeError, ValueError):
                        return False
                else:
                    if event.payload.get(pkey) != v:
                        return False
            # unknown keys are ignored (forward-compat with W2 richer match)
        return True

    def _render_params(
        self, params_tmpl: dict[str, Any], event: Event,
    ) -> dict[str, Any]:
        """Substitute {payload.x} tokens in string params with event.payload values."""
        def _sub(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            out = value
            for m in _TEMPLATE_RE.finditer(value):
                token = m.group(0)
                field = m.group(1)
                out = out.replace(token, str(event.payload.get(field, "")))
            return out

        return {k: _sub(v) for k, v in params_tmpl.items()}

"""Consiglio v1 orchestrator — 4-LLM deliberation for playbook synthesis.

Gate 6 invariant: every final claim has ≥3/4 LLMs agreeing (default).
Disputed claims (≤2 agreement) are kept in the playbook, flagged ⚠️.

Current members:
  claude     — Claude Opus 4.7 via OAuth CLI (primary analyst)
  gemini     — Gemini 3.1 Pro (1M ctx) via CLI — gracefully degrades
               on 429 rate limit; result simply omits gemini votes
  deepseek   — DeepSeek Reasoner ($0.01/query, audited exception)
  notebooklm — NotebookLM MCP query — grounded authority validator

If a member fails (network error, rate limit, no binary), the orchestrator
proceeds with available voters. `ConsiglioResult.meta["active_llms"]`
records how many actually responded so Gate 6 thresholds can be adapted
honestly.

The Consiglio is read-only. It does not trigger publishing. Its outputs
feed Task 20 driver, which writes `08_playbook.md` + `09_wr2_weights.json`.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MIN_AGREEMENT = 3  # 3/4 threshold
CLAIM_QUERY_TIMEOUT_SEC = 600  # 10 min per LLM per deliberation round


@dataclass
class ConsiglioClaim:
    """A single claim voted on by each LLM that responded."""

    key: str  # stable snake_case (e.g. "cadence_instagram_posts_per_day")
    value: Any
    votes: dict[str, bool]  # llm_name → agrees with canonical value

    def agreement_count(self) -> int:
        return sum(1 for v in self.votes.values() if v)

    def is_disputed(self, *, min_agreement: int = DEFAULT_MIN_AGREEMENT) -> bool:
        return self.agreement_count() < min_agreement


@dataclass
class ConsiglioResult:
    claims: list[ConsiglioClaim]
    meta: dict[str, Any] = field(default_factory=dict)

    def gate_6_passes(self, *, min_agreement: int = DEFAULT_MIN_AGREEMENT) -> bool:
        return all(not c.is_disputed(min_agreement=min_agreement) for c in self.claims)

    def disputed_keys(
        self,
        *,
        min_agreement: int = DEFAULT_MIN_AGREEMENT,
    ) -> list[str]:
        return [
            c.key
            for c in self.claims
            if c.is_disputed(min_agreement=min_agreement)
        ]


class ConsiglioV1:
    """Runs deliberation across Claude/Gemini/DeepSeek/NotebookLM."""

    LLMS = ("claude", "gemini", "deepseek", "notebooklm")

    def __init__(self, timeout_sec: int = CLAIM_QUERY_TIMEOUT_SEC) -> None:
        self.timeout = timeout_sec

    def deliberate(
        self,
        question_prompt: str,
        *,
        context_files: list[str] | None = None,
        members: tuple[str, ...] | None = None,
    ) -> ConsiglioResult:
        """Ask the same question to each LLM, collect structured answers.

        Each member returns JSON: ``{"claims": [{key, value, confidence}]}``.
        The orchestrator then merges by key — a claim's value is the first
        response seen, and each LLM votes True if its response for the
        same key has an agreeing value.

        Members that fail the subprocess call (non-zero exit, no JSON,
        timeout) simply don't vote. ``meta["active_llms"]`` counts how
        many members produced at least one claim.
        """
        target_llms = tuple(members) if members else self.LLMS
        answers: dict[str, list[dict[str, Any]]] = {}
        for llm in target_llms:
            try:
                answers[llm] = self._ask(llm, question_prompt, context_files)
            except Exception as exc:  # noqa: BLE001 — keep orchestration alive
                logger.warning("LLM %s failed: %s", llm, exc)
                answers[llm] = []

        active_llms = [llm for llm, cs in answers.items() if len(cs) > 0]
        logger.info(
            "Consiglio responded: %d/%d LLMs active (%s)",
            len(active_llms), len(target_llms), ",".join(active_llms),
        )

        # Merge: group by key across all responses
        all_keys: set[str] = set()
        for lst in answers.values():
            for c in lst:
                if "key" in c:
                    all_keys.add(c["key"])

        claims: list[ConsiglioClaim] = []
        for key in sorted(all_keys):
            votes: dict[str, bool] = {}
            canonical_value: Any = None
            for llm, lst in answers.items():
                match = next((c for c in lst if c.get("key") == key), None)
                if match is None:
                    votes[llm] = False
                    continue
                if canonical_value is None:
                    canonical_value = match.get("value")
                votes[llm] = self._values_agree(match.get("value"), canonical_value)
            claims.append(
                ConsiglioClaim(key=key, value=canonical_value, votes=votes)
            )

        return ConsiglioResult(
            claims=claims,
            meta={
                "active_llms": len(active_llms),
                "llm_answer_counts": {k: len(v) for k, v in answers.items()},
                "members_queried": list(target_llms),
            },
        )

    def _ask(
        self,
        llm: str,
        prompt: str,
        context_files: list[str] | None,
    ) -> list[dict[str, Any]]:
        cmd = self._build_cmd(llm, prompt, context_files)
        if cmd is None:
            return []
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{llm} rc={result.returncode}: {result.stderr[-300:]}")
        return self._parse_claims(result.stdout)

    def _build_cmd(
        self,
        llm: str,
        prompt: str,
        context_files: list[str] | None,
    ) -> list[str] | None:
        """Return subprocess command list, or None if this LLM isn't wired.

        Context files are inlined into the prompt (capped at 50k chars each
        to avoid prompt bloat). The orchestrator is deliberately naive
        about long context — Task 20 driver can pre-summarize if needed.
        """
        ctx = ""
        if context_files:
            for f in context_files:
                try:
                    ctx += f"\n\n## CONTEXT {f}:\n" + open(f).read()[:50_000]
                except OSError:
                    pass
        full_prompt = f"{prompt}\n\n{ctx}"

        if llm == "claude":
            return ["claude", "-p", full_prompt]
        if llm == "gemini":
            return ["gemini", "-m", "gemini-3.1-pro-preview", "-p", full_prompt]
        if llm == "deepseek":
            return ["deepseek-ask", full_prompt]
        if llm == "notebooklm":
            return ["nlm-query", full_prompt]
        return None

    @staticmethod
    def _parse_claims(stdout: str) -> list[dict[str, Any]]:
        """Parse {claims: [...]} from stdout.

        Tries strict last-line JSON first, then a raw_decode fallback on
        the first ``{`` — same pattern as sota_infer_personas Task 15.
        """
        if not stdout:
            return []
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    return data.get("claims", []) if isinstance(data, dict) else []
                except json.JSONDecodeError:
                    continue
        first_brace = stdout.find("{")
        if first_brace >= 0:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(stdout[first_brace:])
                if isinstance(obj, dict):
                    return obj.get("claims", [])
            except json.JSONDecodeError:
                pass
        return []

    @staticmethod
    def _values_agree(a: Any, b: Any) -> bool:
        """Agreement heuristic — strict for scalars, fuzzy for strings."""
        if type(a) is not type(b):
            return False
        if isinstance(a, str):
            return a.strip().lower() == b.strip().lower()
        return a == b

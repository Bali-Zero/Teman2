"""Dual-voice QA Judge: qwen2.5vl flags + Claude Haiku final decision.

Pattern (design §4.4):
1. OllamaVisionClient returns structured VisionFlags.
2. QAJudge feeds (flags + original prompt) to Claude Haiku CLI.
3. Haiku returns QAVerdict: pass | retry_with_modified_prompt | hard_reject.

If Haiku unavailable or outputs invalid JSON, deterministic fallback applies:
flags.rejects_any → retry; else pass.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum

from backend.services.council.cli_runners import CLIRunner
from backend.services.visual.vision_qa import VisionFlags

logger = logging.getLogger(__name__)


class QAVerdict(str, Enum):
    PASS = "pass"
    RETRY = "retry_with_modified_prompt"
    REJECT = "hard_reject"


@dataclass
class QADecision:
    verdict: QAVerdict
    rationale: str = ""
    suggested_prompt_fix: str | None = None
    flags: VisionFlags | None = None
    judge_raw: str = ""
    fallback_used: bool = False


_JUDGE_PROMPT_TEMPLATE = """Sei il giudice qualità visiva di Bali Zero.

Prompt originale: {prompt}

Output modello vision locale (qwen2.5vl:7b):
{flags_json}

DECIDI il destino di questa immagine. Rispondi SOLO JSON:

{{
  "verdict": "pass" | "retry_with_modified_prompt" | "hard_reject",
  "rationale": "1-2 righe motivazione",
  "suggested_prompt_fix": "prompt modificato da inviare a Imagen 4 per retry, o null se verdict=pass o hard_reject"
}}

Criteri:
- pass: matches_brief=true, brand_fit>=7, nessun banned element, readability ok
- retry_with_modified_prompt: difetto correggibile tramite modifica prompt (es. 'add hands' ha prodotto dita deformi -> togliere "hands holding")
- hard_reject: contenuto offensivo, violazione legal/brand gravissima, oppure errore del modello che non si corregge con retry"""


class QAJudge:
    """Uses a Claude (Haiku) CLI runner as the judge voice."""

    def __init__(
        self,
        judge_runner: CLIRunner,
        *,
        max_retries_for_slide: int = 3,
        min_brand_fit_pass: int = 7,
        min_text_area_ratio: float = 0.2,
    ) -> None:
        self.judge_runner = judge_runner
        self.max_retries_for_slide = max_retries_for_slide
        self.min_brand_fit_pass = min_brand_fit_pass
        self.min_text_area_ratio = min_text_area_ratio

    async def judge(
        self,
        *,
        prompt: str,
        flags: VisionFlags,
    ) -> QADecision:
        if not flags.ok:
            # vision qa itself failed — treat as retry (maybe transient)
            return QADecision(
                verdict=QAVerdict.RETRY,
                rationale=f"vision qa unavailable: {flags.error}",
                flags=flags,
                fallback_used=True,
            )

        judge_prompt = _JUDGE_PROMPT_TEMPLATE.format(
            prompt=prompt[:600],
            flags_json=json.dumps(
                {
                    "matches_brief": flags.matches_brief,
                    "has_banned_elements": flags.has_banned_elements,
                    "brand_fit_score_0_10": flags.brand_fit_score_0_10,
                    "text_area_available_ratio": flags.text_area_available_ratio,
                    "readability_issues": flags.readability_issues,
                },
                ensure_ascii=False,
            ),
        )
        parsed, result = await self.judge_runner.run_json(judge_prompt, timeout=45)

        if not result.ok or parsed is None:
            logger.info(
                "qa judge fallback: runner=%s err=%s",
                self.judge_runner.name,
                result.error,
            )
            return self._deterministic_fallback(flags, judge_raw=result.output)

        raw_verdict = str(parsed.get("verdict", "")).strip().lower()
        try:
            verdict = QAVerdict(raw_verdict)
        except ValueError:
            return self._deterministic_fallback(flags, judge_raw=result.output)

        suggested = parsed.get("suggested_prompt_fix")
        if isinstance(suggested, str):
            suggested = suggested.strip() or None
        elif suggested is not None:
            suggested = str(suggested)

        return QADecision(
            verdict=verdict,
            rationale=str(parsed.get("rationale", "")).strip(),
            suggested_prompt_fix=suggested,
            flags=flags,
            judge_raw=result.output,
        )

    def _deterministic_fallback(
        self,
        flags: VisionFlags,
        *,
        judge_raw: str,
    ) -> QADecision:
        """Safety net when Haiku is offline / returns garbage.

        Rules:
        - rejects_any → RETRY
        - else → PASS
        (Never hard_reject deterministically — that requires human judgment.)
        """
        if flags.rejects_any:
            reasons = []
            if not flags.matches_brief:
                reasons.append("matches_brief=false")
            if flags.has_banned_elements:
                reasons.append(f"banned={flags.has_banned_elements}")
            if flags.brand_fit_score_0_10 < self.min_brand_fit_pass:
                reasons.append(f"brand_fit={flags.brand_fit_score_0_10}<{self.min_brand_fit_pass}")
            if flags.text_area_available_ratio < self.min_text_area_ratio:
                reasons.append(
                    f"text_area={flags.text_area_available_ratio}<{self.min_text_area_ratio}"
                )
            return QADecision(
                verdict=QAVerdict.RETRY,
                rationale=f"deterministic: {', '.join(reasons)}",
                flags=flags,
                judge_raw=judge_raw,
                fallback_used=True,
            )
        return QADecision(
            verdict=QAVerdict.PASS,
            rationale="deterministic: no rejection flags",
            flags=flags,
            judge_raw=judge_raw,
            fallback_used=True,
        )

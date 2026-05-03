"""VisualGenerator — orchestrates Imagen 4 generation + QA loop + cost tracking.

Pipeline per slide (design §4, §5):

    1. build_imagen_prompt(scene_core, ...)
    2. route quality:  slide #1 (cover) → ULTRA, others → FAST
    3. Imagen.generate(prompt, quality) — retry inner on transient error (up to 2)
    4. OllamaVisionClient.analyze(image, brief) → VisionFlags
    5. QAJudge.judge(prompt, flags) → QADecision
       5a. PASS  → record_cost + done
       5b. RETRY → modify prompt using suggested_prompt_fix, loop (max 3)
       5c. REJECT → final; placeholder + escalate

If Imagen fails N consecutive times for same slide → fallback to Fireworks.
If both fail → placeholder image + escalation flag.

Every image generated (pass/fail) is recorded in war_room_costs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.services.visual.fireworks_fallback import (
    FireworksClient,
    FireworksResult,
)
from backend.services.visual.imagen_client import (
    ImagenClient,
    ImagenQuality,
)
from backend.services.visual.prompt_builder import (
    NEGATIVE_PROMPT,
    build_imagen_prompt,
)
from backend.services.visual.qa_judge import QADecision, QAJudge, QAVerdict
from backend.services.visual.vision_qa import OllamaVisionClient, VisionFlags
from backend.services.war_room.models import CostType
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


@dataclass
class SlideSpec:
    slide_number: int
    image_prompt: str            # scene_core
    is_cover: bool = False


@dataclass
class SlideResult:
    slide_number: int
    ok: bool
    image_bytes: bytes | None = None
    mime_type: str = "image/png"
    final_prompt: str = ""
    quality_used: str = ""
    provider: str = ""
    qa_decision: QADecision | None = None
    attempts: int = 0
    total_cost_usd: Decimal = Decimal("0")
    error: str | None = None
    needs_escalation: bool = False


@dataclass
class VisualGeneratorResult:
    draft_id: UUID | None
    slides: list[SlideResult] = field(default_factory=list)
    total_cost_usd: Decimal = Decimal("0")

    @property
    def all_ok(self) -> bool:
        return all(s.ok for s in self.slides)

    @property
    def ok_count(self) -> int:
        return sum(1 for s in self.slides if s.ok)

    @property
    def escalation_count(self) -> int:
        return sum(1 for s in self.slides if s.needs_escalation)


_COST_TYPE_BY_QUALITY: dict[ImagenQuality, CostType] = {
    ImagenQuality.ULTRA: CostType.IMAGEN_ULTRA,
    ImagenQuality.FAST: CostType.IMAGEN_FAST,
    ImagenQuality.STANDARD: CostType.IMAGEN_OTHER,
}


class VisualGenerator:
    """End-to-end pipeline orchestrator."""

    def __init__(
        self,
        imagen: ImagenClient,
        vision: OllamaVisionClient,
        judge: QAJudge,
        *,
        fireworks: FireworksClient | None = None,
        cost_repo: WarRoomRepository | None = None,
        max_retries: int = 3,
    ) -> None:
        self.imagen = imagen
        self.vision = vision
        self.judge = judge
        self.fireworks = fireworks
        self.cost_repo = cost_repo
        self.max_retries = max_retries
        self.logger = logger

    async def generate_carousel(
        self,
        slides: list[SlideSpec],
        *,
        draft_id: UUID | None = None,
    ) -> VisualGeneratorResult:
        result = VisualGeneratorResult(draft_id=draft_id)
        for spec in slides:
            slide_result = await self.generate_slide(spec, draft_id=draft_id)
            result.slides.append(slide_result)
            result.total_cost_usd += slide_result.total_cost_usd
        return result

    async def generate_slide(
        self,
        spec: SlideSpec,
        *,
        draft_id: UUID | None = None,
    ) -> SlideResult:
        quality = ImagenQuality.ULTRA if spec.is_cover else ImagenQuality.FAST
        result = SlideResult(
            slide_number=spec.slide_number,
            ok=False,
            quality_used=quality.value,
        )

        current_prompt_core = spec.image_prompt

        for attempt in range(1, self.max_retries + 1):
            result.attempts = attempt
            full_prompt = build_imagen_prompt(current_prompt_core)
            result.final_prompt = full_prompt

            imagen_result = await self.imagen.generate(
                full_prompt,
                quality=quality,
                negative_prompt=NEGATIVE_PROMPT,
            )

            if imagen_result.ok and imagen_result.image_bytes:
                await self._record_cost(
                    draft_id=draft_id,
                    quality=quality,
                    cost_usd=imagen_result.cost_usd,
                    meta={
                        "slide": spec.slide_number,
                        "attempt": attempt,
                        "model": imagen_result.model_id,
                    },
                )
                result.total_cost_usd += imagen_result.cost_usd
                result.provider = "imagen"
                result.image_bytes = imagen_result.image_bytes
                result.mime_type = imagen_result.mime_type

                decision = await self._run_qa(
                    prompt=current_prompt_core,
                    image_bytes=imagen_result.image_bytes,
                )
                result.qa_decision = decision

                if decision.verdict == QAVerdict.PASS:
                    result.ok = True
                    return result
                if decision.verdict == QAVerdict.REJECT:
                    result.error = f"hard_reject: {decision.rationale}"
                    result.needs_escalation = True
                    return result
                # RETRY: mutate prompt and continue loop
                if decision.suggested_prompt_fix:
                    current_prompt_core = decision.suggested_prompt_fix
                # else keep same core; we've already logged the attempt
                continue

            # Imagen failed on this attempt. Log error and potentially fallback.
            self.logger.info(
                "imagen fail slide=%s attempt=%s err=%s",
                spec.slide_number,
                attempt,
                imagen_result.error,
            )
            if attempt == self.max_retries:
                # Exhausted retries — try Fireworks as final safety net
                if self.fireworks is not None:
                    fallback_result = await self._run_fireworks_fallback(
                        spec=spec,
                        prompt_core=current_prompt_core,
                        draft_id=draft_id,
                    )
                    if fallback_result is not None:
                        # fallback_result already mutated; merge into result
                        result.provider = fallback_result.provider
                        result.image_bytes = fallback_result.image_bytes
                        result.mime_type = fallback_result.mime_type
                        result.final_prompt = fallback_result.final_prompt
                        result.total_cost_usd += fallback_result.total_cost_usd
                        if fallback_result.ok:
                            result.ok = True
                            return result
                result.error = (
                    f"imagen exhausted ({attempt} attempts): {imagen_result.error}"
                )
                result.needs_escalation = True
                return result

        # Loop exited without return — QA kept requesting retries beyond max
        result.error = f"qa retry budget exceeded ({self.max_retries})"
        result.needs_escalation = True
        return result

    # ── Internal helpers ────────────────────────────────────────────────

    async def _run_qa(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
    ) -> QADecision:
        flags: VisionFlags = await self.vision.analyze(image_bytes, brief=prompt)
        return await self.judge.judge(prompt=prompt, flags=flags)

    async def _run_fireworks_fallback(
        self,
        *,
        spec: SlideSpec,
        prompt_core: str,
        draft_id: UUID | None,
    ) -> SlideResult | None:
        if self.fireworks is None:
            return None
        full_prompt = build_imagen_prompt(prompt_core)
        fw_result: FireworksResult = await self.fireworks.generate(
            full_prompt,
            negative_prompt=NEGATIVE_PROMPT,
        )
        partial = SlideResult(
            slide_number=spec.slide_number,
            ok=fw_result.ok,
            image_bytes=fw_result.image_bytes,
            mime_type=fw_result.mime_type,
            final_prompt=full_prompt,
            quality_used="fireworks_flux",
            provider="fireworks",
            error=fw_result.error,
            total_cost_usd=fw_result.cost_usd,
        )
        if fw_result.ok and fw_result.cost_usd > 0:
            await self._record_cost(
                draft_id=draft_id,
                quality=None,
                cost_usd=fw_result.cost_usd,
                meta={
                    "slide": spec.slide_number,
                    "provider": "fireworks_flux",
                },
                cost_type_override=CostType.FIREWORKS_FLUX,
            )
        if not fw_result.ok:
            # Still record a failure marker so we track attempted spend
            await self._record_cost(
                draft_id=draft_id,
                quality=None,
                cost_usd=Decimal("0"),
                meta={
                    "slide": spec.slide_number,
                    "provider": "fireworks_flux",
                    "error": fw_result.error,
                },
                cost_type_override=CostType.FIREWORKS_FLUX,
            )
        return partial

    async def _record_cost(
        self,
        *,
        draft_id: UUID | None,
        quality: ImagenQuality | None,
        cost_usd: Decimal,
        meta: dict[str, Any],
        cost_type_override: CostType | None = None,
    ) -> None:
        if self.cost_repo is None:
            return
        cost_type = (
            cost_type_override
            if cost_type_override is not None
            else _COST_TYPE_BY_QUALITY.get(quality, CostType.OTHER)
            if quality is not None
            else CostType.OTHER
        )
        try:
            await self.cost_repo.record_cost(
                draft_id=draft_id,
                cost_type=cost_type,
                cost_usd=cost_usd,
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001 — cost tracking must never fail generation
            self.logger.warning("cost record failed: %s", exc)

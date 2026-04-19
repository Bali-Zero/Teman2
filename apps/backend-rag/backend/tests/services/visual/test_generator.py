"""Unit tests for VisualGenerator orchestration (retry loop + fallback + costs)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from backend.services.visual.fireworks_fallback import FireworksResult
from backend.services.visual.generator import (
    _COST_TYPE_BY_QUALITY,
    SlideSpec,
    VisualGenerator,
)
from backend.services.visual.imagen_client import ImagenQuality, ImagenResult
from backend.services.visual.qa_judge import QADecision, QAVerdict
from backend.services.visual.vision_qa import VisionFlags
from backend.services.war_room.models import CostType


class _MockImagen:
    def __init__(self, results: list[ImagenResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, ImagenQuality, str | None]] = []

    async def generate(self, prompt, *, quality, negative_prompt=None, aspect_ratio=None):
        self.calls.append((prompt, quality, negative_prompt))
        if not self._results:
            return ImagenResult(ok=False, quality=quality, model_id="?", error="exhausted mock")
        return self._results.pop(0)


class _MockVision:
    def __init__(self, flags_sequence: list[VisionFlags]) -> None:
        self._flags = list(flags_sequence)
        self.calls: list[str] = []

    async def analyze(self, image_bytes, brief):
        self.calls.append(brief)
        if not self._flags:
            raise AssertionError("ran out of mock vision flags")
        return self._flags.pop(0)


class _MockJudge:
    def __init__(self, decisions: list[QADecision]) -> None:
        self._decisions = list(decisions)
        self.calls: list[str] = []

    async def judge(self, *, prompt, flags):
        self.calls.append(prompt)
        if not self._decisions:
            raise AssertionError("ran out of mock judge decisions")
        d = self._decisions.pop(0)
        d.flags = flags
        return d


class _MockFireworks:
    def __init__(self, result: FireworksResult) -> None:
        self.result = result
        self.calls = 0

    async def generate(self, prompt, *, width=None, height=None, negative_prompt=None):
        self.calls += 1
        return self.result


class _MockRepo:
    def __init__(self) -> None:
        self.recorded: list[tuple[Any, CostType, Decimal, dict]] = []

    async def record_cost(self, *, draft_id, cost_type, cost_usd, meta):
        self.recorded.append((draft_id, cost_type, cost_usd, meta))


def _good_flags() -> VisionFlags:
    return VisionFlags(
        matches_brief=True,
        has_banned_elements=[],
        brand_fit_score_0_10=9,
        text_area_available_ratio=0.6,
        readability_issues=[],
        ok=True,
    )


def _pass_decision() -> QADecision:
    return QADecision(verdict=QAVerdict.PASS, rationale="looks good")


def _retry_decision(new_prompt: str = "softer scene") -> QADecision:
    return QADecision(
        verdict=QAVerdict.RETRY,
        rationale="banned element",
        suggested_prompt_fix=new_prompt,
    )


def _reject_decision() -> QADecision:
    return QADecision(verdict=QAVerdict.REJECT, rationale="brand violation")


def _imagen_ok(quality: ImagenQuality = ImagenQuality.FAST) -> ImagenResult:
    return ImagenResult(
        ok=True,
        quality=quality,
        model_id=quality.model_id,
        image_bytes=b"fake_image_bytes",
        cost_usd=quality.cost_usd,
    )


def _imagen_fail(quality: ImagenQuality = ImagenQuality.FAST) -> ImagenResult:
    return ImagenResult(
        ok=False,
        quality=quality,
        model_id=quality.model_id,
        error="HTTP 429 quota",
    )


# ── Cost type routing ────────────────────────────────────────────

def test_cost_type_mapping_covers_three_qualities():
    assert _COST_TYPE_BY_QUALITY[ImagenQuality.ULTRA] == CostType.IMAGEN_ULTRA
    assert _COST_TYPE_BY_QUALITY[ImagenQuality.FAST] == CostType.IMAGEN_FAST
    assert _COST_TYPE_BY_QUALITY[ImagenQuality.STANDARD] == CostType.IMAGEN_OTHER


# ── Single-slide happy path ──────────────────────────────────────

@pytest.mark.asyncio
async def test_cover_uses_ultra_quality():
    imagen = _MockImagen([_imagen_ok(ImagenQuality.ULTRA)])
    vision = _MockVision([_good_flags()])
    judge = _MockJudge([_pass_decision()])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=1, image_prompt="hero shot", is_cover=True),
    )
    assert result.ok is True
    assert result.quality_used == "ultra"
    assert result.provider == "imagen"
    assert result.total_cost_usd == Decimal("0.06")
    # called Imagen with ULTRA
    assert imagen.calls[0][1] == ImagenQuality.ULTRA
    # cost recorded with IMAGEN_ULTRA
    assert repo.recorded[0][1] == CostType.IMAGEN_ULTRA


@pytest.mark.asyncio
async def test_slide_uses_fast_quality():
    imagen = _MockImagen([_imagen_ok(ImagenQuality.FAST)])
    vision = _MockVision([_good_flags()])
    judge = _MockJudge([_pass_decision()])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=2, image_prompt="body slide"),
    )
    assert result.ok is True
    assert result.quality_used == "fast"
    assert repo.recorded[0][1] == CostType.IMAGEN_FAST


# ── QA retry loop ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_with_prompt_modification_eventually_passes():
    imagen = _MockImagen([
        _imagen_ok(ImagenQuality.FAST),
        _imagen_ok(ImagenQuality.FAST),
    ])
    vision = _MockVision([_good_flags(), _good_flags()])
    judge = _MockJudge([
        _retry_decision("scene without hands"),
        _pass_decision(),
    ])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=2, image_prompt="scene with hands"),
    )
    assert result.ok is True
    assert result.attempts == 2
    # second call used the modified prompt core
    assert "without hands" in imagen.calls[1][0]
    # cost recorded twice (both generations paid)
    assert len(repo.recorded) == 2


@pytest.mark.asyncio
async def test_max_retries_exhausted_flags_escalation():
    imagen = _MockImagen([_imagen_ok(ImagenQuality.FAST)] * 3)
    vision = _MockVision([_good_flags()] * 3)
    judge = _MockJudge([_retry_decision()] * 3)
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=3, image_prompt="tough slide"),
    )
    assert result.ok is False
    assert result.needs_escalation is True
    # Exhausting QA retries keeps going until max_retries, but only fallback
    # fires when Imagen fails — here Imagen succeeded each time but QA said
    # retry. Implementation: loop exits after max_retries with error message.
    assert "retry budget exceeded" in (result.error or "")


@pytest.mark.asyncio
async def test_hard_reject_stops_immediately():
    imagen = _MockImagen([_imagen_ok(ImagenQuality.FAST)])
    vision = _MockVision([_good_flags()])
    judge = _MockJudge([_reject_decision()])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=1, image_prompt="x", is_cover=True),
    )
    assert result.ok is False
    assert result.needs_escalation is True
    assert "hard_reject" in (result.error or "")


# ── Imagen failure + Fireworks fallback ──────────────────────────

@pytest.mark.asyncio
async def test_imagen_fails_all_retries_fallback_fireworks_succeeds():
    imagen = _MockImagen([_imagen_fail()] * 3)
    vision = _MockVision([_good_flags()])  # not used if no imagen image
    judge = _MockJudge([_pass_decision()])  # not used
    fireworks = _MockFireworks(FireworksResult(
        ok=True,
        image_bytes=b"flux_bytes",
        cost_usd=Decimal("0.03"),
    ))
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge,
        fireworks=fireworks, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=4, image_prompt="tough"),
    )
    assert result.ok is True
    assert result.provider == "fireworks"
    assert result.total_cost_usd == Decimal("0.03")
    # fireworks called once
    assert fireworks.calls == 1
    # fireworks cost recorded with FIREWORKS_FLUX type
    assert any(r[1] == CostType.FIREWORKS_FLUX for r in repo.recorded)


@pytest.mark.asyncio
async def test_imagen_fails_no_fireworks_configured_escalates():
    imagen = _MockImagen([_imagen_fail()] * 3)
    vision = _MockVision([])
    judge = _MockJudge([])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge,
        fireworks=None, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=5, image_prompt="hard"),
    )
    assert result.ok is False
    assert result.needs_escalation is True


@pytest.mark.asyncio
async def test_imagen_fails_fireworks_also_fails():
    imagen = _MockImagen([_imagen_fail()] * 3)
    vision = _MockVision([])
    judge = _MockJudge([])
    fireworks = _MockFireworks(FireworksResult(
        ok=False, error="fireworks down",
    ))
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge,
        fireworks=fireworks, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_slide(
        SlideSpec(slide_number=5, image_prompt="hard"),
    )
    assert result.ok is False
    assert result.needs_escalation is True
    # failure marker cost recorded with cost_usd=0
    failure_records = [
        r for r in repo.recorded if r[1] == CostType.FIREWORKS_FLUX
    ]
    assert failure_records
    assert failure_records[0][2] == Decimal("0")


# ── Carousel end-to-end ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_carousel_mixes_cover_and_slides():
    imagen = _MockImagen([
        _imagen_ok(ImagenQuality.ULTRA),  # cover
        _imagen_ok(ImagenQuality.FAST),
        _imagen_ok(ImagenQuality.FAST),
    ])
    vision = _MockVision([_good_flags()] * 3)
    judge = _MockJudge([_pass_decision()] * 3)
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge, cost_repo=repo,
    )
    draft_id = uuid4()
    result = await gen.generate_carousel(
        [
            SlideSpec(1, "cover scene", is_cover=True),
            SlideSpec(2, "body slide A"),
            SlideSpec(3, "body slide B"),
        ],
        draft_id=draft_id,
    )
    assert result.all_ok
    assert result.ok_count == 3
    # cost: 0.06 + 0.02 + 0.02 = 0.10
    assert result.total_cost_usd == Decimal("0.10")
    # each record carries the draft_id
    for record in repo.recorded:
        assert record[0] == draft_id


@pytest.mark.asyncio
async def test_carousel_escalation_count_accurate():
    imagen = _MockImagen([
        _imagen_ok(ImagenQuality.ULTRA),
        _imagen_fail(),
        _imagen_fail(),
        _imagen_fail(),
    ])
    vision = _MockVision([_good_flags()])
    judge = _MockJudge([_pass_decision()])
    repo = _MockRepo()
    gen = VisualGenerator(
        imagen=imagen, vision=vision, judge=judge,
        fireworks=None, cost_repo=repo, max_retries=3,
    )
    result = await gen.generate_carousel(
        [
            SlideSpec(1, "cover", is_cover=True),
            SlideSpec(2, "body"),
        ],
    )
    assert result.ok_count == 1
    assert result.escalation_count == 1

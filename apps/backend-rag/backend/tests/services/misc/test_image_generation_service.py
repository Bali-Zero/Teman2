from __future__ import annotations

from backend.services.misc.image_generation_service import ImageGenerationService


async def test_generate_image_returns_pollinations_url_with_encoded_prompt() -> None:
    service = ImageGenerationService(api_key="ignored")

    result = await service.generate_image("villa & beach")

    assert result == {
        "success": True,
        "url": "https://image.pollinations.ai/prompt/villa%20%26%20beach",
        "prompt": "villa & beach",
        "service": "pollinations",
    }


async def test_generate_image_rejects_empty_prompt() -> None:
    result = await ImageGenerationService().generate_image("  ")

    assert result == {
        "success": False,
        "error": "Invalid prompt",
        "details": "Prompt cannot be empty",
    }

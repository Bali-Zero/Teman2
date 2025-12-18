"""
ZANTARA MEDIA - AI Writer Router
Intelligent content generation using OpenRouter's FREE models

Uses task-aware routing to select the best model for each job:
- Long-form: Gemini 2.5 Pro, Llama 4 Scout
- Short-form: Mistral Small, Gemini Flash
- Reasoning: DeepSeek R1, Gemini Thinking
- Creative: Llama 4 Maverick, DeepSeek V3.1
"""

import logging
from fastapi import APIRouter, HTTPException
from app.models import (
    AIGenerateRequest,
    AIGenerateResponse,
    ContentType,
    ContentCategory,
    APIResponse,
)
from app.config import settings
from app.services.ai_engine import (
    AIEngine,
    TaskType,
    FREE_MODELS,
    TASK_FALLBACK_CHAINS,
    get_ai_engine,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_engine() -> AIEngine:
    """Get AI engine instance."""
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")
    return get_ai_engine(settings.openrouter_api_key)


def _content_type_to_task(content_type: ContentType) -> TaskType:
    """Map content type to task type for model selection."""
    mapping = {
        ContentType.ARTICLE: TaskType.LONG_FORM,
        ContentType.SOCIAL_POST: TaskType.SHORT_FORM,
        ContentType.NEWSLETTER: TaskType.LONG_FORM,
        ContentType.THREAD: TaskType.THREAD,
    }
    return mapping.get(content_type, TaskType.LONG_FORM)


def parse_generated_content(raw_content: str, content_type: ContentType) -> dict:
    """Parse generated content to extract title, body, summary."""
    lines = raw_content.strip().split("\n")

    # Try to extract title from first line if it looks like a header
    title = None
    body_start = 0

    if lines and (lines[0].startswith("#") or lines[0].startswith("**")):
        title = lines[0].lstrip("#").strip().strip("*")
        body_start = 1

    # Extract summary (first paragraph after title)
    summary = None
    body_lines = lines[body_start:]
    for i, line in enumerate(body_lines):
        if line.strip() and not line.startswith("#"):
            summary = line.strip()
            break

    body = "\n".join(lines[body_start:]).strip()

    return {
        "title": title or f"Generated {content_type.value}",
        "body": body,
        "summary": summary[:300] if summary else None,
    }


@router.post("/generate", response_model=AIGenerateResponse)
async def generate_content(request: AIGenerateRequest):
    """
    Generate content using intelligent model routing.

    The system automatically selects the best FREE model based on content type:
    - Articles/Newsletters → Gemini 2.5 Pro, Llama 4 Scout, DeepSeek V3.1
    - Social Posts → Mistral Small, Gemini Flash, DeepSeek Chat
    - Threads → DeepSeek Chat, Llama 3.3 70B, Llama 4 Scout

    Falls back through the chain if a model fails.
    """
    try:
        engine = _get_engine()
        task_type = _content_type_to_task(request.content_type)

        # Generate based on content type
        if request.content_type == ContentType.ARTICLE:
            raw_content, model = await engine.generate_article(
                topic=request.topic,
                language=request.language,
                tone=request.tone,
            )
        elif request.content_type == ContentType.SOCIAL_POST:
            raw_content, model = await engine.generate_social_post(
                topic=request.topic,
                platform="twitter",  # Default, could be parameterized
            )
        elif request.content_type == ContentType.THREAD:
            raw_content, model = await engine.generate_thread(
                topic=request.topic,
            )
        elif request.content_type == ContentType.NEWSLETTER:
            raw_content, model = await engine.generate_newsletter(
                topic=request.topic,
            )
        else:
            # Generic generation
            raw_content, model = await engine.generate(
                prompt=f"Write content about: {request.topic}",
                task_type=task_type,
            )

        parsed = parse_generated_content(raw_content, request.content_type)

        logger.info(f"Content generated with {model.name} ({model.provider})")

        return AIGenerateResponse(
            success=True,
            title=parsed["title"],
            body=parsed["body"],
            summary=parsed["summary"],
            model_used=model.name,
        )

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        return AIGenerateResponse(
            success=False,
            error=str(e),
        )


@router.post("/generate-from-signal", response_model=AIGenerateResponse)
async def generate_from_intel_signal(
    signal_id: str,
    content_type: ContentType = ContentType.ARTICLE,
):
    """
    Generate content from an intel signal.
    Uses reasoning models to analyze the signal first.
    """
    # TODO: Fetch signal from intel store
    # For now, return not implemented
    return AIGenerateResponse(
        success=False,
        error="Not implemented yet - signal fetch needed",
    )


@router.post("/analyze")
async def analyze_content(
    topic: str,
    source: str = "Unknown",
    category: str = "business",
):
    """
    Analyze a topic using reasoning models (DeepSeek R1, Gemini Thinking).
    Best for intel signal analysis before content creation.
    """
    try:
        engine = _get_engine()
        analysis, model = await engine.analyze_intel(
            intel_summary=topic,
            source=source,
            category=category,
        )

        return {
            "success": True,
            "analysis": analysis,
            "model_used": model.name,
        }

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/summarize")
async def summarize_content(
    content: str,
    length: str = "medium",  # short, medium, long
):
    """
    Summarize long content.
    Uses fast models optimized for summarization.
    """
    try:
        engine = _get_engine()
        summary, model = await engine.summarize(content, length)

        return {
            "success": True,
            "summary": summary,
            "model_used": model.name,
        }

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/translate")
async def translate_content(
    content: str,
    source_lang: str = "en",
    target_lang: str = "id",
):
    """
    Translate content between languages.
    Supports: English (en), Indonesian (id), and others.
    """
    try:
        engine = _get_engine()
        translation, model = await engine.translate(content, source_lang, target_lang)

        return {
            "success": True,
            "translation": translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model_used": model.name,
        }

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/models")
async def list_available_models():
    """
    List all available FREE models and their capabilities.
    All models are free via OpenRouter.
    """
    models_list = []

    for key, model in FREE_MODELS.items():
        models_list.append({
            "key": key,
            "name": model.name,
            "id": model.id,
            "provider": model.provider,
            "context_length": model.context_length,
            "strengths": model.strengths,
            "best_for": [t.value for t in model.best_for],
            "speed": model.speed,
            "supports_vision": model.supports_vision,
            "is_free": True,
        })

    return {
        "total": len(models_list),
        "note": "All models are FREE via OpenRouter (:free suffix)",
        "models": models_list,
    }


@router.get("/models/by-task/{task_type}")
async def get_models_for_task(task_type: str):
    """
    Get the fallback chain of models for a specific task type.

    Task types:
    - long_form: Articles, newsletters
    - short_form: Social posts, captions
    - thread: Twitter threads
    - reasoning: Analysis, complex thinking
    - creative: Storytelling, hooks
    - translation: Multi-language
    - summarization: Condensing content
    - multimodal: Image understanding
    """
    try:
        task = TaskType(task_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task type. Valid types: {[t.value for t in TaskType]}",
        )

    chain_keys = TASK_FALLBACK_CHAINS.get(task, [])
    chain_models = []

    for key in chain_keys:
        model = FREE_MODELS.get(key)
        if model:
            chain_models.append({
                "key": key,
                "name": model.name,
                "provider": model.provider,
                "speed": model.speed,
            })

    return {
        "task_type": task_type,
        "fallback_chain": chain_models,
        "note": "Models are tried in order until one succeeds",
    }


@router.get("/models/status")
async def get_models_status():
    """
    Get real-time health status of all models.
    Shows success/failure counts and health scores.
    """
    try:
        engine = _get_engine()
        return {
            "models": engine.get_model_status(),
            "healthy_count": len(engine.get_healthy_models()),
            "total_count": len(FREE_MODELS),
        }
    except Exception as e:
        return {
            "error": str(e),
            "models": [],
        }


@router.post("/models/health-check")
async def perform_health_check():
    """
    Perform active health check on key models.
    Tests a sample of models and updates their health scores.
    """
    try:
        engine = _get_engine()
        result = await engine.health_check()
        return result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "overall": "error",
            "error": str(e),
        }


@router.post("/estimate-cost")
async def estimate_generation_cost(
    content_type: ContentType,
    length: str = "medium",
):
    """
    Estimate cost for generating content.

    Spoiler: It's FREE! All models use OpenRouter's free tier.
    """
    return {
        "estimated_cost_usd": 0.0,
        "note": "All models are FREE via OpenRouter (:free suffix)",
        "content_type": content_type.value,
        "length": length,
        "models_available": len(FREE_MODELS),
    }

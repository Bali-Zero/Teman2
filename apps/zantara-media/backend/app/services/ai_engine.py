"""
ZANTARA MEDIA - Intelligent AI Engine
Smart model routing using OpenRouter's free models

Philosophy:
- Use ONLY free models (:free suffix)
- Route tasks to the best model for the job
- Smart fallback chains per task type
- Real-time health monitoring

Updated: December 2025 with current OpenRouter free models
"""

import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of content generation tasks."""
    LONG_FORM = "long_form"          # Articles, newsletters, in-depth content
    SHORT_FORM = "short_form"        # Social posts, tweets, captions
    THREAD = "thread"                # Twitter threads, sequential content
    REASONING = "reasoning"          # Analysis, research, complex thinking
    CREATIVE = "creative"            # Storytelling, engaging hooks
    TRANSLATION = "translation"      # Multi-language content
    SUMMARIZATION = "summarization"  # Condensing long content
    CODING = "coding"                # Code generation/review


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    id: str                          # OpenRouter model ID
    name: str                        # Human-readable name
    provider: str                    # Meta, Google, DeepSeek, etc.
    context_length: int              # Max tokens
    strengths: list[str]             # What it's good at
    best_for: list[TaskType]         # Optimal task types
    speed: str = "medium"            # fast, medium, slow
    is_free: bool = True             # Only free models

    # Runtime stats
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_latency_ms: float = 0

    @property
    def health_score(self) -> float:
        """Calculate health score (0-1) based on recent performance."""
        if self.success_count + self.failure_count == 0:
            return 0.5  # Unknown, neutral score

        success_rate = self.success_count / (self.success_count + self.failure_count)

        # Penalize recent failures
        if self.last_failure:
            minutes_since_failure = (datetime.utcnow() - self.last_failure).total_seconds() / 60
            if minutes_since_failure < 5:
                success_rate *= 0.5
            elif minutes_since_failure < 30:
                success_rate *= 0.8

        return min(1.0, success_rate)

    @property
    def is_healthy(self) -> bool:
        """Check if model is considered healthy enough to use."""
        return self.health_score > 0.3


# =============================================================================
# FREE MODELS REGISTRY - Updated December 2025
# All models verified on OpenRouter
# =============================================================================

FREE_MODELS: dict[str, ModelConfig] = {
    # -------------------------------------------------------------------------
    # META LLAMA - Reliable workhorses
    # -------------------------------------------------------------------------
    "llama-3.3-70b": ModelConfig(
        id="meta-llama/llama-3.3-70b-instruct:free",
        name="Llama 3.3 70B",
        provider="Meta",
        context_length=131_072,
        strengths=["instruction following", "quality", "versatile", "reliable"],
        best_for=[TaskType.LONG_FORM, TaskType.CREATIVE, TaskType.THREAD, TaskType.TRANSLATION],
        speed="medium",
    ),
    "llama-3.2-3b": ModelConfig(
        id="meta-llama/llama-3.2-3b-instruct:free",
        name="Llama 3.2 3B",
        provider="Meta",
        context_length=131_072,
        strengths=["fast", "lightweight", "simple tasks"],
        best_for=[TaskType.SHORT_FORM, TaskType.SUMMARIZATION],
        speed="fast",
    ),

    # -------------------------------------------------------------------------
    # GOOGLE - Fast and capable
    # -------------------------------------------------------------------------
    "gemini-flash": ModelConfig(
        id="google/gemini-2.0-flash-exp:free",
        name="Gemini 2.0 Flash",
        provider="Google",
        context_length=1_048_576,
        strengths=["speed", "1M context", "multilingual", "efficient"],
        best_for=[TaskType.SUMMARIZATION, TaskType.TRANSLATION, TaskType.SHORT_FORM],
        speed="fast",
    ),
    "gemma-3-27b": ModelConfig(
        id="google/gemma-3-27b-it:free",
        name="Gemma 3 27B",
        provider="Google",
        context_length=131_072,
        strengths=["balanced", "quality", "efficient"],
        best_for=[TaskType.LONG_FORM, TaskType.CREATIVE, TaskType.SHORT_FORM],
        speed="medium",
    ),
    "gemma-3-12b": ModelConfig(
        id="google/gemma-3-12b-it:free",
        name="Gemma 3 12B",
        provider="Google",
        context_length=32_768,
        strengths=["fast", "efficient", "good quality"],
        best_for=[TaskType.SHORT_FORM, TaskType.SUMMARIZATION],
        speed="fast",
    ),
    "gemma-3-4b": ModelConfig(
        id="google/gemma-3-4b-it:free",
        name="Gemma 3 4B",
        provider="Google",
        context_length=32_768,
        strengths=["very fast", "lightweight"],
        best_for=[TaskType.SHORT_FORM],
        speed="fast",
    ),

    # -------------------------------------------------------------------------
    # MISTRAL - Structured output specialist
    # -------------------------------------------------------------------------
    "mistral-small": ModelConfig(
        id="mistralai/mistral-small-3.1-24b-instruct:free",
        name="Mistral Small 3.1",
        provider="Mistral",
        context_length=128_000,
        strengths=["structured output", "JSON", "function calling", "European languages"],
        best_for=[TaskType.SHORT_FORM, TaskType.SUMMARIZATION, TaskType.CODING],
        speed="fast",
    ),
    "devstral": ModelConfig(
        id="mistralai/devstral-2512:free",
        name="Devstral",
        provider="Mistral",
        context_length=262_144,
        strengths=["coding", "development", "technical"],
        best_for=[TaskType.CODING, TaskType.REASONING],
        speed="medium",
    ),

    # -------------------------------------------------------------------------
    # QWEN - Chinese & reasoning
    # -------------------------------------------------------------------------
    "qwen3-235b": ModelConfig(
        id="qwen/qwen3-235b-a22b:free",
        name="Qwen 3 235B",
        provider="Qwen",
        context_length=131_072,
        strengths=["massive scale", "reasoning", "multilingual", "Chinese"],
        best_for=[TaskType.REASONING, TaskType.LONG_FORM, TaskType.TRANSLATION],
        speed="slow",
    ),
    "qwen3-coder": ModelConfig(
        id="qwen/qwen3-coder:free",
        name="Qwen 3 Coder",
        provider="Qwen",
        context_length=262_000,
        strengths=["coding", "technical", "long context"],
        best_for=[TaskType.CODING],
        speed="medium",
    ),
    "qwen3-4b": ModelConfig(
        id="qwen/qwen3-4b:free",
        name="Qwen 3 4B",
        provider="Qwen",
        context_length=40_960,
        strengths=["fast", "lightweight", "Chinese"],
        best_for=[TaskType.SHORT_FORM, TaskType.TRANSLATION],
        speed="fast",
    ),

    # -------------------------------------------------------------------------
    # NVIDIA - Optimized performance
    # -------------------------------------------------------------------------
    "nemotron-nano-12b": ModelConfig(
        id="nvidia/nemotron-nano-12b-v2-vl:free",
        name="Nemotron Nano 12B VL",
        provider="NVIDIA",
        context_length=128_000,
        strengths=["vision", "multimodal", "efficient"],
        best_for=[TaskType.SHORT_FORM, TaskType.CREATIVE],
        speed="fast",
    ),
    "nemotron-nano-9b": ModelConfig(
        id="nvidia/nemotron-nano-9b-v2:free",
        name="Nemotron Nano 9B",
        provider="NVIDIA",
        context_length=128_000,
        strengths=["fast", "efficient"],
        best_for=[TaskType.SHORT_FORM, TaskType.SUMMARIZATION],
        speed="fast",
    ),

    # -------------------------------------------------------------------------
    # AMAZON NOVA - Long context
    # -------------------------------------------------------------------------
    "nova-lite": ModelConfig(
        id="amazon/nova-2-lite-v1:free",
        name="Nova 2 Lite",
        provider="Amazon",
        context_length=1_000_000,
        strengths=["1M context", "efficient", "balanced"],
        best_for=[TaskType.LONG_FORM, TaskType.SUMMARIZATION],
        speed="medium",
    ),

    # -------------------------------------------------------------------------
    # SPECIALIZED MODELS
    # -------------------------------------------------------------------------
    "hermes-405b": ModelConfig(
        id="nousresearch/hermes-3-llama-3.1-405b:free",
        name="Hermes 3 405B",
        provider="NousResearch",
        context_length=131_072,
        strengths=["massive scale", "quality", "reasoning"],
        best_for=[TaskType.REASONING, TaskType.LONG_FORM, TaskType.CREATIVE],
        speed="slow",
    ),
    "kimi-k2": ModelConfig(
        id="moonshotai/kimi-k2:free",
        name="Kimi K2",
        provider="Moonshot",
        context_length=32_768,
        strengths=["Chinese", "Asian languages", "creative"],
        best_for=[TaskType.CREATIVE, TaskType.TRANSLATION],
        speed="medium",
    ),
    "dolphin-mistral": ModelConfig(
        id="cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        name="Dolphin Mistral 24B",
        provider="CognitiveComputations",
        context_length=32_768,
        strengths=["uncensored", "creative", "flexible"],
        best_for=[TaskType.CREATIVE, TaskType.LONG_FORM],
        speed="medium",
    ),
    "gpt-oss-120b": ModelConfig(
        id="openai/gpt-oss-120b:free",
        name="GPT OSS 120B",
        provider="OpenAI",
        context_length=131_072,
        strengths=["large scale", "quality", "versatile"],
        best_for=[TaskType.LONG_FORM, TaskType.REASONING, TaskType.CREATIVE],
        speed="medium",
    ),
    "longcat-flash": ModelConfig(
        id="meituan/longcat-flash-chat:free",
        name="Longcat Flash",
        provider="Meituan",
        context_length=131_072,
        strengths=["long context", "fast", "Chinese"],
        best_for=[TaskType.SUMMARIZATION, TaskType.LONG_FORM],
        speed="fast",
    ),
    "glm-4.5-air": ModelConfig(
        id="z-ai/glm-4.5-air:free",
        name="GLM 4.5 Air",
        provider="Zhipu",
        context_length=131_072,
        strengths=["Chinese", "balanced", "efficient"],
        best_for=[TaskType.TRANSLATION, TaskType.SHORT_FORM],
        speed="fast",
    ),
    "olmo-3-32b-think": ModelConfig(
        id="allenai/olmo-3-32b-think:free",
        name="OLMo 3 32B Think",
        provider="AllenAI",
        context_length=65_536,
        strengths=["reasoning", "thinking", "open source"],
        best_for=[TaskType.REASONING],
        speed="medium",
    ),
}


# =============================================================================
# TASK-BASED MODEL ROUTING
# =============================================================================

TASK_FALLBACK_CHAINS: dict[TaskType, list[str]] = {
    TaskType.LONG_FORM: [
        "llama-3.3-70b",       # Best quality, reliable
        "gemma-3-27b",         # Good balance
        "gpt-oss-120b",        # Large scale
        "nova-lite",           # 1M context
        "hermes-405b",         # Massive fallback
        "dolphin-mistral",     # Creative
    ],
    TaskType.SHORT_FORM: [
        "gemma-3-12b",         # Fast, good quality
        "mistral-small",       # Structured
        "gemini-flash",        # Super fast
        "llama-3.2-3b",        # Lightweight
        "gemma-3-4b",          # Very fast
        "nemotron-nano-9b",    # NVIDIA optimized
    ],
    TaskType.THREAD: [
        "llama-3.3-70b",       # Quality threads
        "gemma-3-27b",         # Good structure
        "mistral-small",       # Organized output
        "gemini-flash",        # Fast
        "dolphin-mistral",     # Creative
    ],
    TaskType.REASONING: [
        "qwen3-235b",          # Massive reasoning
        "hermes-405b",         # Deep thinking
        "olmo-3-32b-think",    # Thinking model
        "gpt-oss-120b",        # Large scale
        "llama-3.3-70b",       # Reliable fallback
    ],
    TaskType.CREATIVE: [
        "dolphin-mistral",     # Uncensored creative
        "llama-3.3-70b",       # Quality writing
        "gemma-3-27b",         # Good creativity
        "kimi-k2",             # Asian flair
        "hermes-405b",         # Deep creative
    ],
    TaskType.TRANSLATION: [
        "gemini-flash",        # Multi-language, fast
        "llama-3.3-70b",       # Quality
        "qwen3-235b",          # Chinese expert
        "glm-4.5-air",         # Asian languages
        "kimi-k2",             # Chinese
        "mistral-small",       # European
    ],
    TaskType.SUMMARIZATION: [
        "gemini-flash",        # Fast, 1M context
        "nova-lite",           # 1M context
        "gemma-3-12b",         # Efficient
        "mistral-small",       # Structured
        "longcat-flash",       # Long context
        "llama-3.2-3b",        # Simple summaries
    ],
    TaskType.CODING: [
        "qwen3-coder",         # Coding specialist
        "devstral",            # Development focus
        "mistral-small",       # Structured code
        "llama-3.3-70b",       # General coding
        "gpt-oss-120b",        # Large scale
    ],
}


class AIEngine:
    """
    Intelligent AI Engine using OpenRouter's free models.

    Features:
    - Task-aware model selection
    - Smart fallback chains
    - Health monitoring
    - Automatic retry with different models
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.models = {k: ModelConfig(
            id=v.id, name=v.name, provider=v.provider,
            context_length=v.context_length, strengths=v.strengths,
            best_for=v.best_for, speed=v.speed, is_free=v.is_free
        ) for k, v in FREE_MODELS.items()}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://balizero.com",
                    "X-Title": "Zantara Media",
                },
                timeout=120.0,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def get_best_model(self, task_type: TaskType) -> ModelConfig:
        """Get the best healthy model for a task type."""
        chain = TASK_FALLBACK_CHAINS.get(task_type, TASK_FALLBACK_CHAINS[TaskType.LONG_FORM])

        for model_key in chain:
            model = self.models.get(model_key)
            if model and model.is_healthy:
                return model

        for model in self.models.values():
            if model.is_healthy:
                return model

        return self.models[chain[0]]

    def get_fallback_chain(self, task_type: TaskType) -> list[ModelConfig]:
        """Get ordered list of models to try for a task type."""
        chain = TASK_FALLBACK_CHAINS.get(task_type, TASK_FALLBACK_CHAINS[TaskType.LONG_FORM])
        return [self.models[key] for key in chain if key in self.models]

    async def generate(
        self,
        prompt: str,
        task_type: TaskType,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, ModelConfig]:
        """Generate content with intelligent model routing."""
        chain = self.get_fallback_chain(task_type)
        errors = []

        for model in chain:
            if not model.is_healthy and len(errors) == 0:
                logger.debug(f"Skipping unhealthy model: {model.name}")
                continue

            try:
                logger.info(f"Attempting {model.name} for {task_type.value}...")
                start_time = datetime.utcnow()

                content = await self._call_model(
                    model=model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt,
                )

                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._record_success(model, latency)

                logger.info(f"Success with {model.name} ({latency:.0f}ms)")
                return content, model

            except Exception as e:
                self._record_failure(model)
                error_msg = f"{model.name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Model failed: {error_msg}")

        raise Exception(f"All models failed for {task_type.value}: {errors}")

    async def _call_model(
        self,
        model: ModelConfig,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> str:
        """Make API call to OpenRouter."""
        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.post(
            "/chat/completions",
            json={
                "model": model.id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _record_success(self, model: ModelConfig, latency_ms: float):
        """Record successful model call."""
        model.success_count += 1
        model.last_success = datetime.utcnow()
        if model.avg_latency_ms == 0:
            model.avg_latency_ms = latency_ms
        else:
            model.avg_latency_ms = (model.avg_latency_ms * 0.9) + (latency_ms * 0.1)

    def _record_failure(self, model: ModelConfig):
        """Record failed model call."""
        model.failure_count += 1
        model.last_failure = datetime.utcnow()

    # =========================================================================
    # SPECIALIZED GENERATORS
    # =========================================================================

    async def generate_article(
        self,
        topic: str,
        context: str = "",
        language: str = "en",
        tone: str = "professional",
    ) -> tuple[str, ModelConfig]:
        """Generate a long-form article."""
        system_prompt = f"""You are ZANTARA, the AI content writer for Bali Zero - a premium business intelligence platform for Indonesia.
Write in {language}. Tone: {tone}.
Target audience: Expats, entrepreneurs, and business professionals in Indonesia."""

        prompt = f"""Write a professional article about: {topic}

{f"Context: {context}" if context else ""}

Structure:
1. Compelling headline (use #)
2. Executive summary (2-3 sentences)
3. Key points as bullet points
4. Detailed analysis sections
5. Practical action items
6. Professional closing

Format: Markdown"""

        return await self.generate(prompt, TaskType.LONG_FORM, max_tokens=3000, temperature=0.7, system_prompt=system_prompt)

    async def generate_social_post(
        self,
        topic: str,
        platform: str = "twitter",
        context: str = "",
    ) -> tuple[str, ModelConfig]:
        """Generate a social media post."""
        char_limits = {"twitter": 280, "linkedin": 3000, "instagram": 2200, "telegram": 4096}
        limit = char_limits.get(platform, 280)

        system_prompt = """You are ZANTARA, creating engaging social media content for Bali Zero.
Be concise, engaging, and include relevant hashtags."""

        prompt = f"""Write a {platform} post about: {topic}

{f"Context: {context}" if context else ""}

Requirements:
- Hook that grabs attention
- Key information
- Call to action
- Relevant hashtags (3-5)
- Maximum {limit} characters"""

        return await self.generate(prompt, TaskType.SHORT_FORM, max_tokens=500, temperature=0.8, system_prompt=system_prompt)

    async def generate_thread(
        self,
        topic: str,
        num_posts: int = 7,
        context: str = "",
    ) -> tuple[str, ModelConfig]:
        """Generate a Twitter/X thread."""
        system_prompt = """You are ZANTARA, creating engaging Twitter threads for Bali Zero.
Each tweet should be under 280 characters and numbered."""

        prompt = f"""Write a Twitter/X thread about: {topic}

{f"Context: {context}" if context else ""}

Requirements:
- {num_posts} tweets total
- First tweet: Hook + overview
- Middle tweets: One key point each
- Last tweet: Summary + CTA
- Number each (1/, 2/, etc.)
- Each under 280 characters"""

        return await self.generate(prompt, TaskType.THREAD, max_tokens=2000, temperature=0.7, system_prompt=system_prompt)

    async def generate_newsletter(
        self,
        topic: str,
        context: str = "",
    ) -> tuple[str, ModelConfig]:
        """Generate newsletter content."""
        system_prompt = """You are ZANTARA, writing newsletters for Bali Zero's business intelligence platform.
Professional but engaging tone. Clear, scannable formatting."""

        prompt = f"""Write a newsletter section about: {topic}

{f"Context: {context}" if context else ""}

Structure:
1. Engaging subject line
2. Brief intro (why this matters)
3. 3-5 key points with details
4. Action items or next steps
5. Professional sign-off

Format: Clean, scannable, mobile-friendly markdown."""

        return await self.generate(prompt, TaskType.LONG_FORM, max_tokens=2000, temperature=0.6, system_prompt=system_prompt)

    async def analyze_intel(
        self,
        intel_summary: str,
        source: str,
        category: str,
    ) -> tuple[str, ModelConfig]:
        """Analyze an intelligence signal with reasoning."""
        system_prompt = """You are ZANTARA, analyzing business intelligence for Indonesia.
Provide clear, actionable analysis with practical implications."""

        prompt = f"""Analyze this intelligence signal:

Source: {source}
Category: {category}
Summary: {intel_summary}

Provide:
1. Key implications for businesses/expats
2. Who is affected and how
3. Timeline and urgency
4. Recommended actions
5. Related regulations or context

Be specific and actionable."""

        return await self.generate(prompt, TaskType.REASONING, max_tokens=1500, temperature=0.5, system_prompt=system_prompt)

    async def summarize(
        self,
        content: str,
        target_length: str = "medium",
    ) -> tuple[str, ModelConfig]:
        """Summarize long content."""
        length_tokens = {"short": 100, "medium": 300, "long": 500}
        max_tokens = length_tokens.get(target_length, 300)

        prompt = f"""Summarize the following content in a {target_length} summary:

{content}

Focus on key points, actionable information, and main conclusions."""

        return await self.generate(prompt, TaskType.SUMMARIZATION, max_tokens=max_tokens, temperature=0.3)

    async def translate(
        self,
        content: str,
        source_lang: str,
        target_lang: str,
    ) -> tuple[str, ModelConfig]:
        """Translate content between languages."""
        prompt = f"""Translate the following from {source_lang} to {target_lang}.
Maintain the tone, style, and formatting of the original.

Content:
{content}"""

        return await self.generate(prompt, TaskType.TRANSLATION, max_tokens=len(content.split()) * 3, temperature=0.3)

    # =========================================================================
    # HEALTH & STATUS
    # =========================================================================

    def get_model_status(self) -> list[dict]:
        """Get status of all models."""
        return [
            {
                "name": m.name,
                "id": m.id,
                "provider": m.provider,
                "health_score": round(m.health_score, 2),
                "is_healthy": m.is_healthy,
                "success_count": m.success_count,
                "failure_count": m.failure_count,
                "avg_latency_ms": round(m.avg_latency_ms, 0),
                "best_for": [t.value for t in m.best_for],
            }
            for m in self.models.values()
        ]

    def get_healthy_models(self) -> list[ModelConfig]:
        """Get list of currently healthy models."""
        return [m for m in self.models.values() if m.is_healthy]

    async def health_check(self) -> dict:
        """Perform health check on key models."""
        results = {}
        test_prompt = "Say 'OK' if you're working."
        test_models = ["gemini-flash", "llama-3.3-70b", "gemma-3-12b"]

        for model_key in test_models:
            model = self.models.get(model_key)
            if not model:
                continue

            try:
                start = datetime.utcnow()
                await self._call_model(model, test_prompt, 10, 0, None)
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                results[model_key] = {"status": "ok", "latency_ms": round(latency)}
                self._record_success(model, latency)
            except Exception as e:
                results[model_key] = {"status": "error", "error": str(e)}
                self._record_failure(model)

        healthy_count = len([r for r in results.values() if r["status"] == "ok"])

        return {
            "overall": "healthy" if healthy_count >= 2 else "degraded" if healthy_count >= 1 else "down",
            "models": results,
            "timestamp": datetime.utcnow().isoformat(),
        }


_engine: Optional[AIEngine] = None


def get_ai_engine(api_key: str) -> AIEngine:
    """Get or create the AI engine singleton."""
    global _engine
    if _engine is None:
        _engine = AIEngine(api_key)
    return _engine


# Create default instance for imports (will be initialized when config loaded)
class _DeferredAIEngine:
    """Deferred AI engine that loads config on first use."""
    def __init__(self):
        self._engine: Optional[AIEngine] = None

    def _get_engine(self) -> AIEngine:
        if self._engine is None:
            from app.config import settings
            self._engine = get_ai_engine(settings.openrouter_api_key)
        return self._engine

    async def generate_with_fallback(self, prompt: str) -> tuple[str, str]:
        """Generate content with model fallback."""
        engine = self._get_engine()
        content, model = await engine.generate_article(prompt)
        return content, model.name


ai_engine = _DeferredAIEngine()

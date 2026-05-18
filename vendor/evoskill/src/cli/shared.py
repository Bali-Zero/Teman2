"""Shared CLI helpers used by run/eval without importing the full run command."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.cli.config import ProjectConfig


def load_and_split(cfg: ProjectConfig):
    from src.api.data_utils import stratified_split

    data = pd.read_csv(cfg.dataset_path)

    renames: dict[str, str] = {}
    if cfg.dataset.question_column != "question":
        renames[cfg.dataset.question_column] = "question"
    if cfg.dataset.ground_truth_column != "ground_truth":
        renames[cfg.dataset.ground_truth_column] = "ground_truth"
    if renames:
        data.rename(columns=renames, inplace=True)

    if cfg.dataset.category_column and cfg.dataset.category_column in data.columns:
        if cfg.dataset.category_column != "category":
            data.rename(columns={cfg.dataset.category_column: "category"}, inplace=True)
    elif "category" not in data.columns:
        data["category"] = "default"

    return stratified_split(
        data,
        train_ratio=cfg.dataset.train_ratio,
        val_ratio=cfg.dataset.val_ratio,
    )


def infer_provider(model: str) -> str:
    """Infer the LLM provider from the configured model name."""
    normalized = model.strip()
    if normalized.startswith("openrouter/"):
        return "openrouter"
    if normalized.startswith("anthropic/"):
        return "anthropic"
    if normalized.startswith("openai/"):
        return "openai"
    if normalized.startswith("google/"):
        return "google"
    # Bali Zero Nuzantara Phase 1 Task #22 (L9 fix from .known-limitations-v1):
    # explicit deepseek prefix support MUST come before the model.startswith
    # fallback chain — without it, "deepseek-v4-pro" falls into the last
    # `return "anthropic"` branch (because none of the startswith() guards
    # match), and the subsequent call_llm("anthropic", ...) raises
    # ImportError per CLAUDE.md hard rule. Bug surface: any `cfg.scorer`
    # that omits explicit `provider=` config falls back to infer_provider
    # on the model name. With this fix, deepseek-v4-pro routes correctly.
    if normalized.startswith("deepseek/"):
        return "deepseek"
    if model.startswith("deepseek"):
        return "deepseek"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if model.startswith("gemini"):
        return "google"
    # Phase 1: keep upstream fallback to "anthropic" so the loud raise in
    # call_llm catches genuinely-unknown model names rather than silently
    # routing them to DeepSeek. Explicit deepseek prefix above is required.
    return "anthropic"


def _normalize_provider_model(provider: str, model: str) -> str:
    """Strip provider prefixes that the downstream SDKs do not expect."""
    normalized = model.strip()

    if provider == "openrouter" and normalized.startswith("openrouter/"):
        return normalized[len("openrouter/") :]
    if provider == "anthropic" and normalized.startswith("anthropic/"):
        return normalized[len("anthropic/") :]
    if provider == "openai" and normalized.startswith("openai/"):
        return normalized[len("openai/") :]
    if provider == "google" and normalized.startswith("google/"):
        return normalized[len("google/") :]
    # Bali Zero Nuzantara Phase 1 Task #22 — DeepSeek API is
    # OpenAI-compatible (base_url=https://api.deepseek.com/v1); strip
    # the `deepseek/` prefix if a user wrote `deepseek/deepseek-v4-pro`
    # by analogy with the other providers.
    if provider == "deepseek" and normalized.startswith("deepseek/"):
        return normalized[len("deepseek/") :]

    return normalized


async def call_llm(provider: str, model: str, prompt: str) -> str:
    """Call the requested LLM provider and return the raw text response."""
    from src.harness.provider_auth import ensure_provider_api_key

    provider = provider.strip().lower()
    normalized_model = _normalize_provider_model(provider, model)

    # Bali Zero Nuzantara vendor strip (panel round 3 Codex BLOCKING #2):
    # the anthropic raise MUST happen BEFORE ensure_provider_api_key().
    # The upstream flow asked for ANTHROPIC_API_KEY first, which would
    # produce a misleading error message ("Set ANTHROPIC_API_KEY")
    # suggesting that setting the key is the fix — when actually
    # anthropic is disabled entirely by CLAUDE.md hard rule. Fail loud
    # FIRST, before exposing the banned auth path.
    if provider == "anthropic":
        # Bali Zero Nuzantara vendor strip (CLAUDE.md hard rule):
        # the original `import anthropic` + AsyncAnthropic block was
        # physically removed. We never call the paid Anthropic API by
        # token (Antonello holds 2 Claude MAX x20 OAuth subscriptions —
        # paying per token would duplicate flat fee). Configure DeepSeek
        # V4 Pro via `provider=deepseek` for proposer/skill-builder, or
        # Gemini 3.1 Pro free OAuth via `provider=google` for entailment.
        # See vendor/evoskill/UPSTREAM.md for the full diff list.
        raise ImportError(
            "Anthropic provider disabled per Bali Zero Nuzantara CLAUDE.md "
            "hard rule (no paid Anthropic API ever). The original block "
            "called anthropic.AsyncAnthropic with a per-token API key, "
            "which is banned. Switch to provider=deepseek (DeepSeek V4 Pro "
            "API) or provider=google (Gemini 3.1 Pro free OAuth)."
        )

    api_key = ensure_provider_api_key(provider)

    if provider == "openai":
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run: uv add openai"
            ) from exc

        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=normalized_model,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    if provider == "openrouter":
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run: uv add openai"
            ) from exc

        default_headers: dict[str, str] = {}
        if referer := os.environ.get("OPENROUTER_HTTP_REFERER"):
            default_headers["HTTP-Referer"] = referer
        if title := (os.environ.get("OPENROUTER_APP_TITLE") or os.environ.get("OPENROUTER_TITLE")):
            default_headers["X-OpenRouter-Title"] = title

        client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers=default_headers or None,
        )
        response = await client.chat.completions.create(
            model=normalized_model,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    # Bali Zero Nuzantara Phase 1 Task #22:
    # DeepSeek V4 Pro is OpenAI-API-compatible (per DeepSeek docs:
    # "uses an API format compatible with OpenAI/Anthropic"). Reuses the
    # existing openai package — no new dependency — by pointing
    # `base_url` at https://api.deepseek.com/v1. Same Chat-Completions
    # shape, same response.choices[0].message.content extraction.
    #
    # `max_tokens=16` matches the upstream pattern for other providers
    # (this `call_llm` is the cheap-path for short responses like
    # scorer rubric "0.0"/"1.0" and infer-provider probes). The real
    # heavyweight DeepSeek call (executor.py — Task #23) uses a
    # separate code path with full token budget.
    if provider == "deepseek":
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run: uv add openai"
            ) from exc

        client = openai.AsyncOpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
        )
        response = await client.chat.completions.create(
            model=normalized_model,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    if provider == "google":
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package not installed. Run: uv add google-genai"
            ) from exc

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(model=normalized_model, contents=prompt)
        return response.text

    raise ValueError(f"Unknown provider: {provider}")


def make_scorer(cfg: ProjectConfig):
    from src.loop.runner import _score_multi_tolerance

    if cfg.scorer.type == "exact":

        def exact(question: str, predicted: str, ground_truth: str) -> float:
            return (
                1.0
                if str(predicted).strip().lower()
                == str(ground_truth).strip().lower()
                else 0.0
            )

        return exact

    if cfg.scorer.type == "multi_tolerance":
        return _score_multi_tolerance

    if cfg.scorer.type == "llm":
        rubric = cfg.scorer.rubric or "Award 1.0 if correct, 0.0 if wrong."
        # Bali Zero Nuzantara Phase 1 Task #22 (L9 fix from
        # .known-limitations-v1): upstream default was
        # "claude-sonnet-4-6" which routes to provider="anthropic" and
        # then hits the hard-rule ImportError in call_llm. Switch
        # default to "deepseek-v4-pro" so an unconfigured scorer
        # works out of the box on this fork.
        model = cfg.scorer.model or "deepseek-v4-pro"
        provider = cfg.scorer.provider or infer_provider(model)

        async def llm_score(question: str, predicted: str, ground_truth: str) -> float:
            prompt = (
                f"Question: {question}\n"
                f"Expected: {ground_truth}\n"
                f"Got: {predicted}\n\n"
                f"Rubric: {rubric}\n\n"
                "Reply with only a number between 0.0 and 1.0."
            )
            try:
                text = await call_llm(provider, model, prompt)
                return float(text.strip())
            except ValueError:
                import logging
                logging.getLogger(__name__).warning(
                    "LLM scorer: could not parse response as float: %r", text
                )
                return 0.0
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error(
                    "LLM scorer failed (%s: %s) — returning 0.0",
                    type(exc).__name__, exc,
                )
                return 0.0

        def llm_scorer(question: str, predicted: str, ground_truth: str) -> float:
            coro = llm_score(question, predicted, ground_truth)
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No running loop — safe to use asyncio.run()
                return asyncio.run(coro)
            else:
                # Inside a running loop (e.g. SelfImprovingLoop) —
                # run in a separate thread with its own event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()

        return llm_scorer

    if cfg.scorer.type == "script":
        import shlex
        import subprocess

        if not cfg.scorer.command:
            raise ValueError(
                "scorer.type is 'script' but scorer.command is not set in config.toml"
            )

        def script_scorer(question: str, predicted: str, ground_truth: str) -> float:
            # Use Template-style substitution to avoid KeyError on { } in answers
            cmd = cfg.scorer.command.replace("{predicted}", predicted).replace("{expected}", ground_truth)
            try:
                result = subprocess.run(
                    shlex.split(cmd), capture_output=True, text=True, timeout=30,
                )
            except subprocess.TimeoutExpired:
                import logging
                logging.getLogger(__name__).warning(
                    "Script scorer timed out (30s): %s", cmd[:120],
                )
                return 0.0
            try:
                return float(result.stdout.strip())
            except ValueError:
                return 0.0

        return script_scorer

    return _score_multi_tolerance

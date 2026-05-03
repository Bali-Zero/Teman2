"""
Mata Garuda — Relevance Scorer Worker.

Reads from garuda:enriched, scores items 1-5 using Ollama (local, $0),
publishes scored items back to garuda:enriched with score field,
triggers TG alert for items scoring >= SCORE_SIGNAL.

Layer 2 Kognitif — scoring worker.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime

from mata_garuda.config import (
    RELEVANCE_WEIGHTS,
    SCORE_SIGNAL,
    STREAM_ALERTS,
    STREAM_ENRICHED,
)
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.base_worker import (
    redis_cmd,
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers")

CONSUMER_GROUP = "scorer"
CONSUMER_NAME = "scorer-1"

SCORE_PROMPT_TEMPLATE = """Rate the relevance of this item for an Indonesian business services company (visa, tax, company setup, property) in Bali.

Title: {title}
Content: {content}
Source: {source}

Score 1-5:
1 = irrelevant noise
2 = tangentially related
3 = moderately relevant
4 = highly relevant, affects clients
5 = critical, requires immediate action

Also classify the topic. Choose ONE:
immigration_visa, tax_fiscal, investment_licensing, labor_manpower, provincial_bali,
financial_banking, property, environmental, ai_research, procurement, other

Output ONLY a JSON object:
{{"score": N, "topic": "...", "reason": "one sentence"}}"""


def score_with_ollama(title: str, content: str, source: str) -> dict:
    """Score an item using local Ollama (qwen3:8b — MoE, always hot on Pro).

    qwen3:8b is preferred over qwen3.5:9b because:
    - MoE architecture = fast inference even at 26B params
    - Always loaded in memory on Pro (H24)
    - qwen3.5:9b requires cold start at 02:00 and has think-mode latency
    """
    prompt = SCORE_PROMPT_TEMPLATE.format(
        title=title,
        content=content[:500],
        source=source,
    )

    try:
        result = subprocess.run(
            [
                "curl", "-s", "http://localhost:11434/api/generate",
                "-d", json.dumps({
                    "model": "qwen3:8b",
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 120},
                }),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            response = json.loads(result.stdout)
            text = response.get("response", "")
            # Qwen with think:false + format:json returns clean JSON.
            # Strip any residual <think> tags from older responses as guard.
            import re
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            try:
                return json.loads(text.strip())
            except json.JSONDecodeError:
                # Fallback: grab first {...} block (greedy across newlines)
                m = re.search(r"\{.*\}", text, flags=re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group())
                    except json.JSONDecodeError:
                        pass

    except (subprocess.TimeoutExpired, Exception) as e:
        logger.warning(f"[scorer] Ollama failed: {e}")

    # Fallback: default score
    return {"score": 2, "topic": "other", "reason": "scoring unavailable"}


def run_scorer(kb: KnowledgeBase, max_items: int = 20) -> dict:
    """Run one pass of the scorer worker.

    Returns stats: {processed, alerts, stored}
    """
    stats = {"processed": 0, "alerts": 0, "stored": 0}

    items = stream_read_new(STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items)

    if not items:
        logger.info("[scorer] No new items in garuda:enriched")
        return stats

    for item in items:
        msg_id = item["id"]
        data = item["data"]
        stats["processed"] += 1

        title = data.get("title", "")
        content = data.get("content", "")
        source = data.get("source", "")

        scoring = score_with_ollama(title, content, source)
        score = scoring.get("score", 2)
        topic = scoring.get("topic", "other")
        reason = scoring.get("reason", "")

        # Apply domain weight bonus
        weight = RELEVANCE_WEIGHTS.get(topic, 1)
        weighted_score = min(5, score + (weight - 3) * 0.5)  # Slight bonus for high-weight topics

        # Store scored item in KB with FULL content for digest agent
        if weighted_score >= 2:
            content_preview = content[:400] if content else ""
            kb.store(
                agent="scorer",
                entry_type="scored_item",
                content=(
                    f"TITLE: {title}\n"
                    f"SCORE: {weighted_score:.1f}/5 | TOPIC: {topic}\n"
                    f"REASON: {reason}\n"
                    f"URL: {data.get('url', '')}\n"
                    f"SOURCE: {source}\n"
                    f"CONTENT: {content_preview}"
                ),
                source=data.get("url", source),
                confidence=weighted_score / 5.0,
            )
            stats["stored"] += 1

        # Alert if high score
        if weighted_score >= SCORE_SIGNAL:
            alert_data = {
                "title": title,
                "url": data.get("url", ""),
                "source": source,
                "score": str(weighted_score),
                "topic": topic,
                "reason": reason,
                "alert_time": datetime.now().isoformat(timespec="seconds"),
            }
            stream_publish(STREAM_ALERTS, alert_data)
            stats["alerts"] += 1

        stream_ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[scorer] Done: {stats['processed']} scored, "
        f"{stats['alerts']} alerts, {stats['stored']} stored"
    )
    return stats

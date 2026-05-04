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
import re
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


# Keyword fast-path — applied BEFORE the LLM call.
# Saves ~2-3s/item on average (qwen3:8b cold load is ~3-5s, warm eval ~0.2-1s
# but timeout=60s when GPU is occupied by qwen2.5vl:7b vision worker).
# Empirically ~70-80% of sentinel intake (arxiv AI papers) routes via the
# first regex; Indonesian-business titles route via patterns 2-7. Only items
# that match no pattern fall through to the LLM call.
#
# Returned tuples: (regex, topic, default_score)
# The score is conservative — Ollama would refine it if called.
_KEYWORD_FAST_PATH: list[tuple[str, str, int]] = [
    (r"\b(arxiv|preprint|neural|transformer|llm|gpt|diffusion|embedding|rag\b|hugging\s*face|pytorch|tensorflow)",
     "ai_research", 2),
    (r"\b(visa|kitas|kitap|imigrasi|immigration|e[-_ ]?vo[ah]|golden[- ]visa)",
     "immigration_visa", 4),
    (r"\b(pajak|tax(ation)?|spt|coretax|djp|npwp|pph|ppn|fiscal)",
     "tax_fiscal", 4),
    (r"\b(pt[ _-]?pma|kbli|oss[- ]?rba|nib|investment|bkpm|izin[ _]usaha)",
     "investment_licensing", 4),
    (r"\b(property|villa|land|sertifikat|shgb|hak[- ]?(guna|pakai)|ppjb|akta|pbg|imb)",
     "property", 4),
    (r"\b(bali|denpasar|badung|gianyar|ubud|canggu|kuta|seminyak|jimbaran|nusa[- ]dua)",
     "provincial_bali", 3),
    (r"\b(prabowo|jokowi|menteri|kementerian|peraturan|undang[- ]?undang|perpres|permen)",
     "political_risk", 3),
]


def classify_by_keyword(title: str, content: str) -> dict | None:
    """Best-effort topic classifier via title/content regex.

    Returns a scoring dict on first match, or None to fall through to LLM.
    Pattern order matters — `ai_research` is first because most arxiv items
    contain Bali-irrelevant terms that would otherwise hit "other".
    """
    blob = f"{title} {content[:200]}".lower()
    for pattern, topic, default_score in _KEYWORD_FAST_PATH:
        if re.search(pattern, blob, flags=re.IGNORECASE):
            return {
                "score": default_score,
                "topic": topic,
                "reason": f"keyword fast-path: {topic}",
            }
    return None


def score_with_ollama(title: str, content: str, source: str) -> dict:
    """Score an item using local Ollama (qwen3:8b).

    Tries keyword fast-path first (zero cost, ~70-80% hit rate on sentinel
    intake). Only falls through to the LLM when no keyword pattern matches.

    The fallback chain on LLM error: returns score=2 / topic=other.
    """
    fast = classify_by_keyword(title, content)
    if fast is not None:
        return fast

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

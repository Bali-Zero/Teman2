"""WhatsApp → Client Dossier synthesizer for NotebookLM ingestion.

Reads CRM-resolved WhatsApp conversations from `whatsapp_message_context_enriched`,
calls Ollama qwen3.5:9b with deterministic settings (temperature=0, seed=42,
format=json), validates the output against a Pydantic 3-layer schema, and merges
with approved `workspace_ai_snapshots` rows.

Sovereignty: Ollama LOCAL only (Symbiosis Law 2 / Law 6). Never cloud LLM for
PII-bearing WhatsApp content (UU PDP scope).

Reference scar: cicatrix `GDRIVE_COMPANIES_FOLDER_ID phantom + wa-mirror bypass`
(2026-05-21) — `client_id` is NULL on raw `whatsapp_message_context`; we use the
`crm_client_id_resolved` column from the enriched view which phone-matches into
`clients.phone`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Literal

import asyncpg
import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 180.0
OLLAMA_SEED = 42
OLLAMA_NUM_CTX = 8192

MAX_MESSAGES_PER_CLIENT = 200
DEFAULT_WINDOW_DAYS = 180


class Decision(BaseModel):
    date: str = Field(description="ISO date YYYY-MM-DD or 'unknown'")
    what: str = Field(description="Short description of the decision taken")
    who: str = Field(default="client", description="client | team | joint")


class DocRef(BaseModel):
    kind: str = Field(description="Document type, e.g. 'passport copy', 'akta', 'NPWP'")
    ref_date: str = Field(description="ISO date or 'unknown' — NEVER include the document number")


class Deadline(BaseModel):
    date: str
    what: str


class QuoteApproval(BaseModel):
    date: str
    service: str
    amount_idr: int | None = Field(default=None, description="Amount in IDR if explicit, else null")


class Warning(BaseModel):
    date: str
    topic: str
    note: str = Field(description="Short description of the warning/disclaimer given to the client")


class Promise(BaseModel):
    date: str
    by: str = Field(description="Email or name of who promised")
    what: str


class Episode(BaseModel):
    date: str
    note: str


class Handoff(BaseModel):
    date: str
    from_operator: str
    to_operator: str
    reason: str = ""


class HardFacts(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    documents_delivered: list[DocRef] = Field(default_factory=list)
    declared_deadlines: list[Deadline] = Field(default_factory=list)
    quotes_approved: list[QuoteApproval] = Field(default_factory=list)


class SoftFacts(BaseModel):
    client_business_goals: list[str] = Field(default_factory=list)
    warnings_given: list[Warning] = Field(default_factory=list)
    promises_sla: list[Promise] = Field(default_factory=list)


class HumanLayer(BaseModel):
    sentiment_trend: Literal["positive", "neutral", "frustrated", "mixed"] = "neutral"
    frustration_episodes: list[Episode] = Field(default_factory=list)
    operator_handoffs: list[Handoff] = Field(default_factory=list)


class ClientDossier(BaseModel):
    client_id: int
    display_name: str
    msg_count: int
    period_start: str
    period_end: str
    hard_facts: HardFacts = Field(default_factory=HardFacts)
    soft_facts: SoftFacts = Field(default_factory=SoftFacts)
    human_layer: HumanLayer = Field(default_factory=HumanLayer)
    workspace_facts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Approved CRM workspace_ai_snapshots facts (merged, not synthesized)",
    )


_NPWP_PATTERN = re.compile(
    r"\bNPWP\b[\s:]*\d{2}[.\s]?\d{3}[.\s]?\d{3}[.\s]?\d[-\s]?\d{3}[.\s]?\d{3}\b",
    re.IGNORECASE,
)
_PASSPORT_PATTERN = re.compile(r"\b[A-Z]\d{7}\b")
_NIK_PATTERN = re.compile(r"\b\d{16}\b")
_NIB_PATTERN = re.compile(r"\b\d{13}\b")
_FULL_PHONE_PATTERN = re.compile(r"\+\d{1,3}(?:[\s-]?\d{2,5}){2,5}")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[\w.-]+")
_EFIN_PATTERN = re.compile(r"\bEFIN[\s:]*\d{10}\b", re.IGNORECASE)


def strip_pii(text: str) -> str:
    """Mask hard-PII before sending to LLM.

    Preserves intent (e.g. "passport sent on 12/05") while removing the document
    number itself. Money amounts are preserved — they're not PII per UU PDP scope.
    """
    if not text:
        return ""
    text = _NPWP_PATTERN.sub("[NPWP-MASKED]", text)
    text = _EFIN_PATTERN.sub("[EFIN-MASKED]", text)
    text = _PASSPORT_PATTERN.sub("[PASSPORT-MASKED]", text)
    text = _NIK_PATTERN.sub("[NIK-MASKED]", text)
    text = _NIB_PATTERN.sub("[NIB-MASKED]", text)
    text = _FULL_PHONE_PATTERN.sub("[PHONE-MASKED]", text)
    text = _EMAIL_PATTERN.sub("[EMAIL-MASKED]", text)
    return text


SYNTHESIZE_PROMPT = """\
You are an analyst extracting structured facts from a WhatsApp conversation between Bali Zero (an Indonesian business-services agency) and a client.

CONVERSATION (chronological, → = outbound from team, ← = inbound from client):
{conversation}

Extract the conversation into THREE LAYERS. Return ONLY valid JSON matching exactly this schema:

{{
  "hard_facts": {{
    "decisions": [{{"date": "YYYY-MM-DD", "what": "<short>", "who": "client|team|joint"}}],
    "documents_delivered": [{{"kind": "<doctype>", "ref_date": "YYYY-MM-DD"}}],
    "declared_deadlines": [{{"date": "YYYY-MM-DD", "what": "<short>"}}],
    "quotes_approved": [{{"date": "YYYY-MM-DD", "service": "<short>", "amount_idr": <int or null>}}]
  }},
  "soft_facts": {{
    "client_business_goals": ["<short goal sentence>"],
    "warnings_given": [{{"date": "YYYY-MM-DD", "topic": "<short>", "note": "<short>"}}],
    "promises_sla": [{{"date": "YYYY-MM-DD", "by": "<team email or name>", "what": "<short>"}}]
  }},
  "human_layer": {{
    "sentiment_trend": "positive|neutral|frustrated|mixed",
    "frustration_episodes": [{{"date": "YYYY-MM-DD", "note": "<short>"}}],
    "operator_handoffs": [{{"date": "YYYY-MM-DD", "from_operator": "<email>", "to_operator": "<email>", "reason": "<short>"}}]
  }}
}}

RULES:
1. NEVER include document numbers, passport IDs, NPWP, NIK, NIB, full phone numbers, or EFIN codes. The conversation has them masked as [*-MASKED]; keep them masked.
2. If a field is unknown, use "unknown" for date strings, empty list [] for arrays, null for amount_idr.
3. dates MUST be ISO YYYY-MM-DD or the literal string "unknown".
4. amounts in IDR only as integer (no decimals, no currency symbols).
5. Output JSON only. No prose before or after.
"""


async def _call_ollama_json(prompt: str, model: str = OLLAMA_MODEL) -> dict[str, Any] | None:
    """Single Ollama call with format=json + seed=42 + temperature=0."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "seed": OLLAMA_SEED,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": 2048,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()
            if not raw:
                logger.warning("Ollama returned empty response")
                return None
            return json.loads(raw)
    except httpx.ConnectError:
        logger.error("Ollama unreachable at %s — is `ollama serve` running?", OLLAMA_URL)
        return None
    except httpx.TimeoutException:
        logger.warning("Ollama timeout after %ss", OLLAMA_TIMEOUT)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Ollama returned non-JSON: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Ollama call failed: %s", exc)
        return None


def _format_conversation(messages: list[dict[str, Any]]) -> str:
    """Render messages into chronological strip-PII text for the LLM prompt."""
    lines: list[str] = []
    for msg in messages:
        ts = msg["message_date"]
        ts_str = ts.strftime("%Y-%m-%d %H:%M") if isinstance(ts, datetime) else str(ts)
        arrow = "→" if msg["direction"] == "outbound" else "←"
        operator = msg.get("team_member_email") or ""
        body = strip_pii((msg.get("body") or msg.get("message_text") or "").strip())
        if not body:
            continue
        prefix = f"[{ts_str}] {arrow}"
        if operator and msg["direction"] == "outbound":
            prefix += f" {operator}"
        lines.append(f"{prefix}: {body}")
    return "\n".join(lines)


async def synthesize_client_dossier(
    *,
    client_id: int,
    display_name: str,
    messages: list[dict[str, Any]],
    workspace_facts: list[dict[str, Any]] | None = None,
    model: str = OLLAMA_MODEL,
) -> ClientDossier | None:
    """Synthesize a 3-layer dossier for one client. Returns None on hard failure.

    Deterministic: same input → same output (temperature=0, seed=42).
    """
    if not messages:
        logger.info("client_id=%s: no messages, skipping", client_id)
        return None

    period_start = min(m["message_date"] for m in messages)
    period_end = max(m["message_date"] for m in messages)

    conversation_text = _format_conversation(messages)
    prompt = SYNTHESIZE_PROMPT.format(conversation=conversation_text)

    raw = await _call_ollama_json(prompt, model=model)
    if raw is None:
        logger.warning("client_id=%s: LLM call failed, skipping", client_id)
        return None

    try:
        dossier = ClientDossier(
            client_id=client_id,
            display_name=display_name,
            msg_count=len(messages),
            period_start=period_start.strftime("%Y-%m-%d") if isinstance(period_start, (date, datetime)) else str(period_start),
            period_end=period_end.strftime("%Y-%m-%d") if isinstance(period_end, (date, datetime)) else str(period_end),
            hard_facts=HardFacts.model_validate(raw.get("hard_facts", {})),
            soft_facts=SoftFacts.model_validate(raw.get("soft_facts", {})),
            human_layer=HumanLayer.model_validate(raw.get("human_layer", {})),
            workspace_facts=workspace_facts or [],
        )
    except ValidationError as exc:
        logger.warning("client_id=%s: schema validation failed: %s", client_id, exc)
        return None

    return dossier


async def fetch_clients_with_wa_messages(
    conn: asyncpg.Connection,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Return list of CRM-resolved clients with WhatsApp activity in the window."""
    rows = await conn.fetch(
        """
        SELECT
            crm_client_id_resolved AS client_id,
            MIN(COALESCE(display_name, crm_full_name, wa_contact_name)) AS display_name,
            COUNT(*) AS msg_count,
            MIN(message_date) AS first_msg,
            MAX(message_date) AS last_msg
        FROM whatsapp_message_context_enriched
        WHERE crm_client_id_resolved IS NOT NULL
          AND message_date > NOW() - ($1::text || ' days')::interval
        GROUP BY crm_client_id_resolved
        ORDER BY msg_count DESC
        """,
        str(window_days),
    )
    return [dict(r) for r in rows]


async def fetch_messages_for_client(
    conn: asyncpg.Connection,
    *,
    client_id: int,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = MAX_MESSAGES_PER_CLIENT,
) -> list[dict[str, Any]]:
    """Fetch chronological messages for one client (cap at `limit` most recent)."""
    rows = await conn.fetch(
        """
        SELECT
            id,
            direction,
            message_date,
            team_member_email,
            body,
            message_text
        FROM whatsapp_message_context_enriched
        WHERE crm_client_id_resolved = $1
          AND message_date > NOW() - ($2::text || ' days')::interval
        ORDER BY message_date DESC
        LIMIT $3
        """,
        client_id,
        str(window_days),
        limit,
    )
    msgs = [dict(r) for r in rows]
    msgs.reverse()
    return msgs


async def fetch_workspace_facts_for_client(
    conn: asyncpg.Connection,
    *,
    client_id: int,
) -> list[dict[str, Any]]:
    """Look up company_id via client_company_links + fetch approved snapshot."""
    try:
        company_row = await conn.fetchrow(
            """
            SELECT company_id
            FROM client_company_links
            WHERE client_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            client_id,
        )
    except asyncpg.UndefinedTableError:
        return []

    if not company_row or not company_row["company_id"]:
        return []

    try:
        snap = await conn.fetchrow(
            """
            SELECT facts
            FROM crm_workspace_ai_snapshots
            WHERE company_id = $1
              AND status = 'approved'
            ORDER BY approved_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            company_row["company_id"],
        )
    except asyncpg.UndefinedTableError:
        return []

    if not snap or not snap["facts"]:
        return []

    facts = snap["facts"]
    if isinstance(facts, str):
        try:
            facts = json.loads(facts)
        except json.JSONDecodeError:
            return []
    return list(facts) if isinstance(facts, list) else []

#!/usr/bin/env python3
"""wa-mirror attention classifier (Phase 1 — Owner Attention Queue)

Cron 5min. For every unclassified inbound message in `whatsapp_message_context`:
1. Rules-first: regex over keyword packs → returns priority + reason codes
2. Ollama qwen3.5:9b fallback ONLY on rules-ambiguous (no keyword hit, length >30)
3. Decay rule: if HIGH inbound got outbound team response within 2h → resolve

Skip rules:
- Team phones (whatsapp_contacts.contact_type='team') → priority=LOW silent
- Zero (628213107363) → skip entirely
- direction='outbound' → skip entirely
- Already classified (attention_priority IS NOT NULL) → skip

Reason codes:
  refund, complaint, deadline, payment_dispute, lawyer, audit, urgent_keyword,
  new_lead, unanswered_thread_3plus, media_on_active_practice,
  question_about_pricing, status_check, document_request, generic_inbound

OSINT-safe: Ollama LOCAL only, raw body never sent to cloud.
Audit: ~/logs/wa-mirror-attention.jsonl
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import asyncpg

ENV_FILE = Path.home() / ".wa-mirror.env"
DB_URL = None
for raw_line in ENV_FILE.read_text().splitlines():
    line = raw_line.strip()
    if line.startswith("WA_MIRROR_DATABASE_URL="):
        DB_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
if not DB_URL:
    print("ERR: WA_MIRROR_DATABASE_URL missing", file=sys.stderr); sys.exit(2)
# W57 (2026-05-26): removed legacy rewrite `@host/ → @localhost:15432/` (pg-proxy Fly).
# Post-cutover 2026-05-24 wa-mirror is LOCAL-ONLY (decision_wa_mirror_local_only_cutover):
# writes to 127.0.0.1:5432/nuzantara_dev (Postgres local). Honoring URL as written.
DB_URL = DB_URL.replace("postgres://", "postgresql://")

DRY_RUN = os.environ.get("WA_ATTENTION_DRY_RUN", "0") == "1"
USE_OLLAMA = os.environ.get("WA_ATTENTION_USE_OLLAMA", "1") == "1"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3.5:9b"
AUDIT_LOG = Path.home() / "logs" / "wa-mirror-attention.jsonl"
AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

ZERO_PHONES = {"628213107363"}
DECAY_WINDOW = timedelta(hours=2)

# --- Keyword packs (case-insensitive). Order matters: HIGH > MEDIUM > LOW.

HIGH_KEYWORDS = {
    "refund":          [r"\brefund\b", r"\brimbors", r"\bpengemb", r"\buang\s*kembali\b"],
    "complaint":       [r"\bcomplain", r"\bunhappy\b", r"\bdelusion", r"\bscam\b",
                        r"\btruffa\b", r"\bbohong\b", r"\btipu\b", r"\bdiscriminat",
                        r"\bawful\b", r"\bterrible\b", r"\bpessim", r"\bangry\b",
                        r"\bmarah\b", r"\bkecewa\b"],
    "deadline":        [r"\bovers?tay(ed|ing|s)?\b", r"\bscadenz", r"\bjatuh\s*tempo\b",
                        r"\bdeadline\b", r"\bexpir", r"\bkadaluars", r"\btoday\b",
                        r"\bbesok\b", r"\bdomani\b", r"\bsegera\b",
                        r"\burgent(e|ly|ly+|t+)?\b",
                        r"\basap\b", r"\bemergenc"],
    "payment_dispute": [r"\bnot\s*paid\b", r"\bnon\s*pagat", r"\bbelum\s*dibayar\b",
                        r"\bpaid\s*twice\b", r"\bdouble\s*charg", r"\bcharged\s*wrong\b",
                        r"\bwrong\s*amount\b"],
    "lawyer":          [r"\blawyer\b", r"\bavvocat", r"\bpengacara\b", r"\battorne",
                        r"\blegal\s*action\b", r"\bsu\s*you\b", r"\btuntut\b"],
    "audit":           [r"\baudit\b", r"\bpemeriksaan\b", r"\bdjp\b", r"\bkpp\b",
                        r"\bdgt\b", r"\btax\s*office\b"],
}

MEDIUM_KEYWORDS = {
    "question_about_pricing": [r"\bberapa\b", r"\bharga\b", r"\bquanto\b", r"\bcosto?\b",
                                r"\bprezzo\b", r"\bprice\b", r"\bcost\b", r"\bfee\b",
                                r"\bbiaya\b", r"\bquotation\b", r"\bquote\b"],
    "status_check":           [r"\bstatus\b", r"\bbagaimana\b", r"\bgimana\b", r"\bkapan\b",
                                r"\bwhen\b", r"\bquando\b", r"\bany\s*update\b",
                                r"\baggiornament", r"\bprogres", r"\bupdate\?"],
    "document_request":       [r"\bsurat\b", r"\bdokumen\b", r"\bcertific", r"\bsertifik",
                                r"\bnpwp\b", r"\bkitas\b", r"\bvisa\b", r"\bnib\b",
                                r"\bdokument", r"\bdocumento?\b"],
}

def looks_junk_body(s: Optional[str]) -> bool:
    if not s: return True
    s2 = s.strip()
    if not s2: return True
    if len(s2) <= 2: return True
    # emoji-only / sticker
    if all(not ch.isalnum() for ch in s2): return True
    return False


def rules_classify(body: str, n_inbound_unresolved: int, has_active_practice: bool,
                   is_new_lead: bool, has_media: bool) -> tuple[Optional[str], list[str]]:
    """Returns (priority, reasons[]).

    priority: HIGH | MEDIUM | LOW | None (None = ambiguous, send to Ollama)
    """
    body_low = (body or "").lower()
    reasons: list[str] = []

    # 1) HIGH triggers (any single match → HIGH)
    for code, patterns in HIGH_KEYWORDS.items():
        for p in patterns:
            if re.search(p, body_low):
                reasons.append(code)
                break
    if reasons:
        if n_inbound_unresolved >= 3:
            reasons.append("unanswered_thread_3plus")
        if has_media and has_active_practice:
            reasons.append("media_on_active_practice")
        if is_new_lead:
            reasons.append("new_lead")
        return ("HIGH", reasons)

    # 2) MEDIUM triggers
    for code, patterns in MEDIUM_KEYWORDS.items():
        for p in patterns:
            if re.search(p, body_low):
                reasons.append(code)
                break
    if reasons:
        if is_new_lead:
            reasons.insert(0, "new_lead")
        if has_media and has_active_practice:
            reasons.append("media_on_active_practice")
        return ("MEDIUM", reasons)

    # 3) Structural signals that bump priority even without keywords
    if is_new_lead and n_inbound_unresolved >= 2:
        return ("MEDIUM", ["new_lead", "unanswered_thread_2plus"])
    if n_inbound_unresolved >= 3:
        return ("MEDIUM", ["unanswered_thread_3plus"])
    if has_media and has_active_practice:
        return ("MEDIUM", ["media_on_active_practice"])
    if has_media:
        return ("LOW", ["media_no_text"])

    # 4) Short body without keywords → LOW deterministic
    if looks_junk_body(body) or len(body_low.strip()) <= 30:
        return ("LOW", ["short_ack_or_sticker"])

    # 5) Medium-length body, no keywords → ambiguous, send to Ollama
    return (None, [])


async def ollama_classify(body: str, has_practice: bool) -> tuple[str, list[str]]:
    """Fallback for ambiguous mid-length bodies. Returns (priority, reasons)."""
    import urllib.request
    prompt = (
        "You are a triage classifier for a Bali business-services agency. "
        "A client sent this WhatsApp message. Classify ONLY as HIGH, MEDIUM, or LOW.\n\n"
        f"Active practice with this client: {'yes' if has_practice else 'no'}\n\n"
        f"Message:\n```\n{body[:500]}\n```\n\n"
        "Rules:\n"
        "- HIGH = needs owner attention TODAY (deadline, complaint, payment dispute, urgent question)\n"
        "- MEDIUM = needs reply within 24h but not critical (price question, status check, doc request)\n"
        "- LOW = ack, thanks, sticker-like, no clear ask\n\n"
        "Respond ONLY with one word: HIGH or MEDIUM or LOW. Nothing else."
    )
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_predict": 8},
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        out = (d.get("response") or "").strip().upper()
        # Extract first valid token
        for tok in re.findall(r"\b(HIGH|MEDIUM|LOW)\b", out):
            return (tok, ["ollama_classified"])
    except Exception as e:
        return ("MEDIUM", [f"ollama_fail:{type(e).__name__}"])
    return ("MEDIUM", ["ollama_indeterminate"])


async def fetch_unclassified_inbound(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch("""
      WITH unclassified AS (
        SELECT
          m.id,
          m.created_at,
          m.client_id,
          m.practice_id,
          REGEXP_REPLACE(m.raw_baileys_event->'key'->>'senderPn', '@.*', '') AS phone,
          COALESCE(NULLIF(m.body,''), NULLIF(m.message_text,'')) AS body,
          m.media_type,
          m.media_stored_path
        FROM whatsapp_message_context m
        WHERE m.direction = 'inbound'
          AND m.attention_priority IS NULL
          AND m.raw_baileys_event->'key'->>'senderPn' ~ '^[0-9]+@'
        ORDER BY m.created_at DESC
        LIMIT 200
      )
      SELECT u.*,
             EXISTS(SELECT 1 FROM whatsapp_contacts wc
                    WHERE wc.phone_normalized = u.phone AND wc.contact_type = 'team') AS is_team,
             (u.phone = '628213107363') AS is_zero,
             EXISTS(SELECT 1 FROM clients c
                    WHERE c.phone_normalized = u.phone
                      AND c.deleted_at IS NULL) AS is_known_client,
             EXISTS(SELECT 1 FROM practices p
                    JOIN clients c2 ON c2.id = p.client_id
                    WHERE c2.phone_normalized = u.phone
                      AND p.status NOT IN ('completed','cancelled','rejected')
                      AND p.actual_completion_date IS NULL) AS has_active_practice,
             (SELECT COUNT(*) FROM whatsapp_message_context m2
              WHERE REGEXP_REPLACE(m2.raw_baileys_event->'key'->>'senderPn','@.*','') = u.phone
                AND m2.direction='inbound'
                AND m2.attention_resolved_at IS NULL
                AND m2.created_at >= u.created_at - INTERVAL '48 hours'
             ) AS n_inbound_unresolved
      FROM unclassified u
    """)
    return [dict(r) for r in rows]


async def apply_decay(conn: asyncpg.Connection) -> int:
    """Resolve HIGH messages that got an outbound team response within 2h.

    Decay rule: HIGH inbound on phone X at T → if any outbound from team member
    on phone X between T and T+2h → mark attention_resolved_at = first outbound time.
    """
    if DRY_RUN:
        return 0
    res = await conn.execute("""
      UPDATE whatsapp_message_context AS hi
      SET attention_resolved_at = sub.first_response
      FROM (
        SELECT inb.id,
               (SELECT MIN(out_.created_at) FROM whatsapp_message_context out_
                WHERE REGEXP_REPLACE(out_.raw_baileys_event->'key'->>'senderPn','@.*','')
                      = REGEXP_REPLACE(inb.raw_baileys_event->'key'->>'senderPn','@.*','')
                  AND out_.direction='outbound'
                  AND out_.created_at > inb.created_at
                  AND out_.created_at <= inb.created_at + INTERVAL '2 hours'
               ) AS first_response
        FROM whatsapp_message_context inb
        WHERE inb.attention_priority='HIGH'
          AND inb.attention_resolved_at IS NULL
          AND inb.direction='inbound'
      ) sub
      WHERE hi.id = sub.id AND sub.first_response IS NOT NULL
    """)
    # res like 'UPDATE 0' or 'UPDATE 3'
    try:
        return int(res.split()[-1])
    except Exception:
        return 0


async def classify_one(conn: asyncpg.Connection, cand: dict) -> dict:
    audit = {"ts": datetime.now(timezone.utc).isoformat(),
             "id": cand["id"], "phone": cand["phone"]}

    # Hard skips
    if cand["is_zero"]:
        # Still write LOW to avoid infinite re-queueing
        priority, reasons = "LOW", ["zero_self_message"]
    elif cand["is_team"]:
        priority, reasons = "LOW", ["team_member_silent"]
    else:
        body = cand["body"] or ""
        has_media = bool(cand["media_type"]) or bool(cand["media_stored_path"])
        is_new_lead = not cand["is_known_client"]
        priority, reasons = rules_classify(
            body=body,
            n_inbound_unresolved=cand["n_inbound_unresolved"] or 0,
            has_active_practice=cand["has_active_practice"],
            is_new_lead=is_new_lead,
            has_media=has_media,
        )
        if priority is None and USE_OLLAMA:
            priority, llm_reasons = await ollama_classify(body, cand["has_active_practice"])
            reasons += llm_reasons
        elif priority is None:
            priority, reasons = "LOW", ["unclassified_no_ollama"]

    audit["priority"] = priority
    audit["reasons"] = reasons

    if DRY_RUN:
        audit["action"] = "DRY_RUN_CLASSIFY"
        return audit

    await conn.execute("""
      UPDATE whatsapp_message_context
      SET attention_priority = $1,
          attention_reason = $2::text[],
          attention_computed_at = NOW()
      WHERE id = $3 AND attention_priority IS NULL
    """, priority, reasons, cand["id"])
    audit["action"] = "CLASSIFIED"
    return audit


async def main():
    started = datetime.now(timezone.utc)
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, ssl=False,
                                      max_inactive_connection_lifetime=30.0)
    counters = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "skipped": 0, "decayed": 0}
    try:
        async with pool.acquire() as conn:
            # 1) Decay rule first
            counters["decayed"] = await apply_decay(conn)

            # 2) Classify unclassified inbound
            candidates = await fetch_unclassified_inbound(conn)
            for cand in candidates:
                rec = await classify_one(conn, cand)
                if rec["action"] in ("CLASSIFIED", "DRY_RUN_CLASSIFY"):
                    p = rec.get("priority","LOW")
                    counters[p] = counters.get(p,0) + 1
                with AUDIT_LOG.open("a") as f:
                    f.write(json.dumps(rec, default=str) + "\n")

            summary = {
                "ts": started.isoformat(),
                "candidates": len(candidates),
                "classified": counters,
                "dry_run": DRY_RUN,
            }
            print(json.dumps(summary, default=str))
            with AUDIT_LOG.open("a") as f:
                f.write(json.dumps(summary) + "\n")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

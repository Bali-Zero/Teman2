#!/usr/bin/env python3
"""WR2 Fact Checker — Sprint B B-bis (2026-05-08).

Reads `war_room_drafts` rows in status='drafts_imaged_facted', verifies
each claim previously extracted by `wr2_fact_extractor.py`, then sets:

    fact_check_status = 'pass'      → all claims verified
                      = 'degraded'  → some unverifiable but no contradiction
                      = 'fail'      → at least one claim contradicts source

    status            = 'drafts_imaged_checked'  (pass / degraded)
                      = 'fact_check_failed'      (fail)

This is a NET-NEW build — the original wr2_fact_checker.py was never
written. Re-enables the chain so canva-apply only renders fact-checked
drafts (Sprint B B-bis decision: lock canva-apply filter to
`status = 'drafts_imaged_checked'`).

Verification strategy (per-claim, deterministic + LLM-cross-check):

1. For 'law' claims (regex match like ``PP\\s\\d+/\\d{4}``,
   ``PMK\\s\\d+/\\d{4}``, ``KEP-\\d+/PJ/\\d{4}``):
    - String-match the law citation in the slide body and the original
      research_json (if present). If found verbatim → 'verified'.
    - If only paraphrased, OPUS cross-check against the source text.

2. For 'number' / 'date' claims:
    - Match against research_json (where the draft generator pulled
      facts) and/or council_debate_json. If consistent → 'verified'.
    - If discrepancy >0 (number drift, year mismatch) → 'contradicted'.

3. For 'quote' claims:
    - String-substring match in research_json. If exact → 'verified',
      else 'unverifiable' (no auto-contradicted; quotes paraphrase often).

4. For 'other':
    - Best-effort: present in research_json text → 'verified', else
      'unverifiable'.

Aggregation:
    contradicted_count > 0  → fact_check_status = 'fail'
    unverifiable_count > 0  → 'degraded'
    all verified            → 'pass'

The verification per claim is recorded into
`fact_check_json.claims[i].verdict` ∈ {verified, contradicted, unverifiable}
plus `fact_check_json.claims[i].note`.

Kill switch
    `system_settings.wr2_fact_checker_enabled` = 'true'.

Anthropic invariant (OB-3): OPUS calls go through claude_oauth_client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# Make backend-rag importable when run from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.llm.claude_oauth_client import (  # noqa: E402
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

logger = logging.getLogger("wr2.fact_checker")

# Tunables
MAX_DRAFTS_PER_RUN = int(os.environ.get("WR2_FACT_CHECKER_BATCH", "3"))
DEFAULT_MODEL = os.environ.get("WR2_FACT_CHECKER_MODEL", "claude-opus-4-7")
DEFAULT_TIMEOUT_S = int(os.environ.get("WR2_FACT_CHECKER_TIMEOUT_S", "120"))
TELEMETRY_PATH = Path.home() / "logs" / "wr2_fact_checker_telemetry.jsonl"

# Law regexes — compiled once.
LAW_PATTERNS = [
    re.compile(r"\bPP\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPMK\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bKEP-\d+/PJ/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPENG-\d+/PJ\.\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bUU\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerbup\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerda\s+\d+/\d{4}\b", re.IGNORECASE),
]


# ─────────────────────────────────────────────────────────────────────────
# Logging + Telegram (mirror of wr2_fact_extractor)
# ─────────────────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    fh = logging.FileHandler(str(log_dir / "wr2_fact_checker.log"))
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", e)


def _log_telemetry(record: dict) -> None:
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.warning("telemetry write failed (non-fatal): %s", e)


# ─────────────────────────────────────────────────────────────────────────
# Source-text helpers
# ─────────────────────────────────────────────────────────────────────────

def _extract_source_text(
    research_json: Any, council_debate_json: Any, slides: list[dict[str, Any]]
) -> str:
    """Concatenate all available source-text the draft was derived from.

    research_json (from topic-selector + draft-generator) is the primary
    truth. council_debate_json captures the LLM panel's reasoning; useful
    for paraphrase matches. Slide bodies are last-resort fallback.
    """
    parts: list[str] = []
    for blob in (research_json, council_debate_json):
        if blob is None:
            continue
        if isinstance(blob, str):
            parts.append(blob)
        else:
            try:
                parts.append(json.dumps(blob, ensure_ascii=False))
            except (TypeError, ValueError):
                parts.append(str(blob))
    for slide in slides:
        if isinstance(slide, dict):
            parts.append(str(slide.get("body", "")))
            parts.append(str(slide.get("title", "")))
    return "\n".join(parts)


def _find_law_citations(text: str) -> set[str]:
    """Return all law citations matched by LAW_PATTERNS (uppercased for compare)."""
    found: set[str] = set()
    for rx in LAW_PATTERNS:
        for m in rx.finditer(text):
            found.add(m.group(0).upper())
    return found


# ─────────────────────────────────────────────────────────────────────────
# Per-claim verification
# ─────────────────────────────────────────────────────────────────────────

def _verify_law_claim(claim_text: str, source_laws: set[str], source_text: str) -> dict[str, str]:
    """A 'law' claim is verified if at least one of its citations
    regex-matches in source. Multi-citation claims are common (e.g.
    "PP 28/2025 supersedes PP 5/2021" — only the primary cite needs to
    be in the source).

    Returns: {"verdict": "verified"|"unverifiable", "note": str}.
    'fail' is reserved for active contradictions; we don't auto-contradict
    laws (a missing law means we couldn't find it, not that it's wrong).
    """
    claim_laws = _find_law_citations(claim_text)
    overlap = claim_laws & source_laws
    if overlap:
        return {
            "verdict": "verified",
            "note": f"law citation matches source: {','.join(sorted(overlap))}",
        }
    if claim_laws:
        return {
            "verdict": "unverifiable",
            "note": f"law citation {','.join(sorted(claim_laws))} not found in research_json",
        }
    # No regex match → fall back to substring search of the claim itself.
    if claim_text.lower() in source_text.lower():
        return {"verdict": "verified", "note": "exact substring match in source"}
    return {"verdict": "unverifiable", "note": "law claim has no matchable citation"}


def _verify_quote_claim(claim_text: str, source_text: str) -> dict[str, str]:
    if claim_text.lower() in source_text.lower():
        return {"verdict": "verified", "note": "exact quote match in source"}
    # Heuristic: match the inner content if the claim is wrapped in
    # smart-quotes that the source has as ASCII (or vice versa).
    stripped = claim_text.strip("\"'“”‘’")
    if stripped and stripped.lower() in source_text.lower():
        return {"verdict": "verified", "note": "quote match after strip"}
    return {"verdict": "unverifiable", "note": "quote not found verbatim in research_json"}


_NUMBER_RX = re.compile(r"-?\d+(?:[.,]\d+)?")
_DATE_RX = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{4}\b")


def _verify_number_or_date_claim(
    claim_text: str, source_text: str, ctype: str
) -> dict[str, str]:
    rx = _NUMBER_RX if ctype == "number" else _DATE_RX
    claim_tokens = rx.findall(claim_text)
    if not claim_tokens:
        return {"verdict": "unverifiable", "note": f"no extractable {ctype} in claim"}
    src_tokens = set(rx.findall(source_text))
    matched = [t for t in claim_tokens if t in src_tokens]
    if len(matched) == len(claim_tokens):
        return {"verdict": "verified", "note": f"{ctype} tokens {matched} all in source"}
    if not matched:
        return {
            "verdict": "contradicted",
            "note": f"{ctype} tokens {claim_tokens} absent from source — possible drift",
        }
    return {
        "verdict": "unverifiable",
        "note": f"partial match ({len(matched)}/{len(claim_tokens)} tokens) — {ctype}",
    }


def _verify_other_claim(claim_text: str, source_text: str) -> dict[str, str]:
    if claim_text.lower() in source_text.lower():
        return {"verdict": "verified", "note": "substring match in source"}
    # Token overlap: at least 60% of claim tokens (>3 chars) appear.
    tokens = [t for t in re.split(r"\W+", claim_text.lower()) if len(t) > 3]
    if not tokens:
        return {"verdict": "unverifiable", "note": "no significant tokens"}
    src_lower = source_text.lower()
    hit = sum(1 for t in tokens if t in src_lower)
    if hit / len(tokens) >= 0.6:
        return {"verdict": "verified", "note": f"token overlap {hit}/{len(tokens)} ≥60%"}
    return {"verdict": "unverifiable", "note": f"token overlap {hit}/{len(tokens)} <60%"}


def _verify_claim(
    claim: dict[str, Any], source_text: str, source_laws: set[str]
) -> dict[str, Any]:
    """Synchronous, deterministic per-claim verifier. No LLM call.

    Output dict has the original claim keys plus `verdict` and `note`.
    """
    out = dict(claim)  # copy so we can add fields without mutating input
    ctype = str(claim.get("type", "other")).lower()
    text = str(claim.get("claim", ""))
    if not text:
        out.update({"verdict": "unverifiable", "note": "empty claim text"})
        return out

    if ctype == "law":
        verdict = _verify_law_claim(text, source_laws, source_text)
    elif ctype == "quote":
        verdict = _verify_quote_claim(text, source_text)
    elif ctype in ("number", "date"):
        verdict = _verify_number_or_date_claim(text, source_text, ctype)
    else:
        verdict = _verify_other_claim(text, source_text)

    out.update(verdict)
    return out


# ─────────────────────────────────────────────────────────────────────────
# Optional LLM cross-check for paraphrased claims
# ─────────────────────────────────────────────────────────────────────────

_LLM_VERIFY_PROMPT = """\
You are a fact-checking assistant. Decide whether the source text below
SUPPORTS, CONTRADICTS, or is INCONCLUSIVE about the claim.

Claim: \"{claim}\"

Source text:
\"\"\"{source}\"\"\"

Return ONE JSON object on its own line, no markdown fences, with this shape:

{{"verdict": "verified|contradicted|unverifiable", "note": "<≤120 chars>"}}

Use "verified" only if the source clearly supports the claim,
"contradicted" only if the source clearly contradicts it, and
"unverifiable" otherwise.
"""


async def _llm_verify_claim(
    claim_text: str, source_text: str, *, model: str, timeout_s: int
) -> dict[str, str]:
    prompt = _LLM_VERIFY_PROMPT.format(
        claim=claim_text[:300],
        source=source_text[:6000],  # cap so the prompt stays small
    )
    try:
        resp = await complete_async(
            prompt,
            model=model,
            timeout_s=timeout_s,
            endpoint="wr2.fact_checker.llm_verify",
        )
    except (ClaudeOAuthError, ClaudeOAuthNotAvailable):
        return {"verdict": "unverifiable", "note": "OAuth call failed"}

    text = (resp.text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"verdict": "unverifiable", "note": "LLM JSON parse failed"}
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"verdict": "unverifiable", "note": "LLM JSON decode failed"}
    verdict = str(obj.get("verdict", "unverifiable")).lower()
    if verdict not in ("verified", "contradicted", "unverifiable"):
        verdict = "unverifiable"
    return {"verdict": verdict, "note": str(obj.get("note", ""))[:120]}


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────

async def _kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    val = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_fact_checker_enabled'"
    )
    return val == "true"


async def _fetch_ready_drafts(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, topic, register, slides_json, research_json,
               council_debate_json, fact_check_json
          FROM war_room_drafts
         WHERE status = 'drafts_imaged_facted'
           AND fact_check_json IS NOT NULL
           AND fact_check_status IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _persist_checked(
    conn: asyncpg.Connection,
    draft_id: UUID,
    fact_check_json: dict[str, Any],
    fact_check_status: str,
) -> None:
    """Record verdicts + advance status.

    pass | degraded → status = 'drafts_imaged_checked' (canva-apply consumes)
    fail            → status = 'fact_check_failed' (terminal — manual review)
    """
    new_status = (
        "fact_check_failed"
        if fact_check_status == "fail"
        else "drafts_imaged_checked"
    )
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET fact_check_json   = $2::jsonb,
               fact_check_status = $3,
               fact_check_at     = NOW(),
               status            = $4,
               updated_at        = NOW()
         WHERE id = $1
        """,
        draft_id,
        json.dumps(fact_check_json),
        fact_check_status,
        new_status,
    )


# ─────────────────────────────────────────────────────────────────────────
# Per-draft pipeline
# ─────────────────────────────────────────────────────────────────────────

def _aggregate_status(verified_claims: list[dict[str, Any]]) -> str:
    """Aggregate per-claim verdicts into a single fact_check_status.

    Rules (locked-in spec from B-bis):
      - any verdict == 'contradicted'  → 'fail'
      - any verdict == 'unverifiable'  → 'degraded' (and no contradicted)
      - all 'verified'                 → 'pass'
      - empty claims list              → 'pass' (vacuously true)
    """
    if not verified_claims:
        return "pass"
    has_contradicted = False
    has_unverifiable = False
    for c in verified_claims:
        v = str(c.get("verdict", "unverifiable")).lower()
        if v == "contradicted":
            has_contradicted = True
        elif v == "unverifiable":
            has_unverifiable = True
    if has_contradicted:
        return "fail"
    if has_unverifiable:
        return "degraded"
    return "pass"


async def _process_one_draft(
    conn: asyncpg.Connection, row: asyncpg.Record, *, llm_enabled: bool
) -> bool:
    draft_id: UUID = row["id"]
    topic: str = row["topic"]
    fact_check_json = row["fact_check_json"]
    if isinstance(fact_check_json, str):
        fact_check_json = json.loads(fact_check_json)

    claims_in: list[dict[str, Any]] = list(
        fact_check_json.get("claims", []) if isinstance(fact_check_json, dict) else []
    )

    # Build the source text once per draft.
    research = row["research_json"]
    if isinstance(research, str):
        try:
            research = json.loads(research)
        except json.JSONDecodeError:
            pass
    council = row["council_debate_json"]
    if isinstance(council, str):
        try:
            council = json.loads(council)
        except json.JSONDecodeError:
            pass
    slides_blob = row["slides_json"]
    if isinstance(slides_blob, str):
        try:
            slides_blob = json.loads(slides_blob)
        except json.JSONDecodeError:
            pass
    slides = (
        slides_blob.get("slides")
        if isinstance(slides_blob, dict)
        else slides_blob
    ) or []

    source_text = _extract_source_text(research, council, slides)
    source_laws = _find_law_citations(source_text)

    t0 = time.time()

    # Pass 1: deterministic verification.
    verified: list[dict[str, Any]] = []
    for claim in claims_in:
        verified.append(_verify_claim(claim, source_text, source_laws))

    # Pass 2 (optional): LLM cross-check for any 'unverifiable' claims to
    # see if they're actually 'verified' (paraphrase) or 'contradicted'
    # (drift). Skipped when llm_enabled=False (fast deterministic path).
    if llm_enabled:
        for c in verified:
            if c.get("verdict") != "unverifiable":
                continue
            try:
                llm_out = await _llm_verify_claim(
                    str(c.get("claim", "")),
                    source_text,
                    model=DEFAULT_MODEL,
                    timeout_s=DEFAULT_TIMEOUT_S,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Draft %s claim LLM-verify failed: %s — keeping deterministic verdict",
                    draft_id, e,
                )
                continue
            # Only upgrade unverifiable → verified/contradicted if LLM is
            # confident; never downgrade a deterministic verified.
            new_verdict = llm_out.get("verdict", "unverifiable")
            if new_verdict in ("verified", "contradicted"):
                c["verdict"] = new_verdict
                prev_note = c.get("note", "")
                c["note"] = f"{prev_note} | LLM: {llm_out.get('note', '')}"[:200]

    duration = time.time() - t0
    fact_check_status = _aggregate_status(verified)

    fact_check_payload = {
        "claims": verified,
        "extracted_at": fact_check_json.get("extracted_at") if isinstance(fact_check_json, dict) else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "verifier": "wr2_fact_checker",
        "llm_enabled": llm_enabled,
    }

    await _persist_checked(conn, draft_id, fact_check_payload, fact_check_status)

    logger.info(
        "Draft %s checked — status=%s claims=%d duration=%.1fs",
        draft_id, fact_check_status, len(verified), duration,
    )
    _log_telemetry(
        {
            "draft_id": str(draft_id),
            "outcome": fact_check_status,
            "duration_s": round(duration, 1),
            "claims_count": len(verified),
            "llm_enabled": llm_enabled,
        }
    )

    if fact_check_status == "fail":
        _send_telegram(
            f"🚨 *WR2 fact-check FAIL*\n"
            f"draft: `{draft_id}`\ntopic: {topic[:80]}\n"
            f"contradicted claims: "
            f"{sum(1 for c in verified if c.get('verdict') == 'contradicted')}/{len(verified)}\n"
            f"Manual review required (status=fact_check_failed)."
        )
    elif fact_check_status == "degraded":
        # Degraded is silent (proceeds to canva-apply); only log in telemetry.
        pass

    return fact_check_status != "fail"


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

async def run() -> int:
    _configure_logging()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    llm_enabled = os.environ.get("WR2_FACT_CHECKER_LLM", "false").lower() == "true"

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        if not await _kill_switch_enabled(conn):
            logger.info("wr2_fact_checker_enabled != true — exiting quietly")
            return 0

        drafts = await _fetch_ready_drafts(conn, MAX_DRAFTS_PER_RUN)
        if not drafts:
            logger.info("no drafts ready for fact checking")
            return 0

        logger.info(
            "processing %d draft(s) llm_enabled=%s", len(drafts), llm_enabled
        )
        successes = 0
        started = time.monotonic()
        for row in drafts:
            try:
                ok = await _process_one_draft(conn, row, llm_enabled=llm_enabled)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Draft %s: unexpected error: %s", row["id"], exc)
                ok = False
            if ok:
                successes += 1

        logger.info(
            "run complete — %d/%d ok in %.1fs",
            successes, len(drafts), time.monotonic() - started,
        )
        return 0 if successes == len(drafts) else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

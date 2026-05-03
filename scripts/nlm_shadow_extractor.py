#!/usr/bin/env python3
"""Sprint 2 Shadow Graphing — extract claims from NB into Qdrant nlm_shadow_hybrid.

For each NB domain in the registry:
  1. ask NLM (via nlm CLI) for atomic claims in JSON-strict format
  2. validate each candidate with DeepSeek Reasoner
  3. embed claim_text via OpenAI text-embedding-3-small (FROZEN model)
  4. upsert into Qdrant collection nlm_shadow_hybrid as NLMShadowChunk

Designed to run as nightly cron after NB-2..NB-10 pipelines complete.

Usage:
    python scripts/nlm_shadow_extractor.py --notebook NB-2 [--dry-run] [--limit 10]
    python scripts/nlm_shadow_extractor.py --all-domains [--dry-run]

Env required (when not --dry-run):
    DEEPSEEK_API_KEY      — for claim validation
    OPENAI_API_KEY        — for claim embedding
    QDRANT_URL            — for upsert (default http://localhost:6333)
    QDRANT_API_KEY        — for cloud Qdrant only

Vincolo Anthropic OAuth-only (Golden Rule #13): NEVER calls Claude API
directly. NLM CLI uses the user's Max OAuth subscription. DeepSeek and
OpenAI are paid per-token but allowed (not banned by the rule).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("nlm_shadow_extractor")

# ── Domain → notebook mapping (canonical, mirrors backend nlm_notebook_registry) ──
DOMAIN_TO_NB: dict[str, dict[str, str]] = {
    "immigration": {
        "id": "cff93ab0-813a-42f2-a8de-36987e724271",
        "label": "immigration",
        "extract_prompt_subject": "immigration & visa requirements (KITAS, KITAP, TKA)",
    },
    "company": {
        "id": "933509f9-1561-403d-bd44-4a7a67a36df2",
        "label": "company",
        "extract_prompt_subject": "company setup, KBLI, PMA, OSS, NIB",
    },
    "tax": {
        "id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
        "label": "tax",
        "extract_prompt_subject": "Indonesian tax obligations (PPh, PPN, NPWP, BPJS)",
    },
    "property": {
        "id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
        "label": "property",
        "extract_prompt_subject": "property, zoning, HGB, Hak Pakai, leasehold",
    },
    "operations": {
        "id": "85207af3-352f-4554-8d2a-18f42cc541ba",
        "label": "operations",
        "extract_prompt_subject": "operations, manpower, HR, BPJS",
    },
}

EXTRACTION_PROMPT = (
    "Extract atomic claims from the sources of this notebook about "
    "{subject}. Each claim must be:\n"
    "  - one self-contained statement\n"
    "  - factual, attributable to a source in this notebook\n"
    "  - 50-300 characters\n"
    "Return STRICT JSON: a list of objects with keys 'claim' and "
    "'source_id'. No prose, no markdown, no explanation. "
    "Maximum {limit} claims. Example:\n"
    '[{{"claim": "...", "source_id": "..."}}, ...]\n'
)

DEEPSEEK_VALIDATE_PROMPT = (
    "You are validating an atomic legal/regulatory claim about Indonesia. "
    "The claim is: {claim}\n\n"
    "Reply with strict JSON: {{\"valid\": true|false, \"confidence\": 0.0-1.0, "
    "\"notes\": \"short reason\"}}. A claim is INVALID if it is vague, "
    "self-contradictory, or makes a numeric assertion without a clear basis. "
    "If you are unsure, prefer valid=true with confidence < 0.6 and a note."
)


def _run_nlm_extract(notebook_id: str, subject: str, limit: int, timeout: int = 180) -> list[dict]:
    """Ask NLM for claims as JSON list. Returns [] on parse failure."""
    prompt = EXTRACTION_PROMPT.format(subject=subject, limit=limit)
    logger.info("Querying NLM for %d claims (NB=%s)", limit, notebook_id[:8])
    try:
        proc = subprocess.run(
            ["nlm", "notebook", "query", notebook_id, prompt, "--timeout", str(timeout)],
            capture_output=True, text=True, timeout=timeout + 20,
        )
        if proc.returncode != 0:
            logger.error("nlm CLI exit %d: %s", proc.returncode, proc.stderr.strip()[:200])
            return []
        wrapper = json.loads(proc.stdout)
        # nlm CLI wraps response in {"value": {...}}
        if "value" in wrapper:
            wrapper = wrapper["value"]
        answer = wrapper.get("answer", "")
        # Extract JSON list from answer (NLM sometimes wraps in markdown)
        return _parse_json_list(answer)
    except subprocess.TimeoutExpired:
        logger.warning("NLM query timed out after %ds", timeout)
        return []
    except Exception as exc:
        logger.exception("NLM extraction failed: %s", exc)
        return []


def _parse_json_list(text: str) -> list[dict]:
    """Best-effort parse of a JSON list from a possibly-wrapped answer."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Find the first [ ... ] block
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning("no JSON list found in answer")
        return []
    try:
        parsed = json.loads(text[start:end + 1])
        if isinstance(parsed, list):
            return [c for c in parsed if isinstance(c, dict) and "claim" in c]
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed: %s", exc)
    return []


def _validate_with_deepseek(claim: str, api_key: str, timeout: int = 60) -> dict:
    """Call DeepSeek Reasoner to validate a single claim."""
    import urllib.request
    body = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": "You validate atomic claims and reply only with strict JSON."},
            {"role": "user", "content": DEEPSEEK_VALIDATE_PROMPT.format(claim=claim)},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        msg = payload["choices"][0]["message"].get("content", "")
        # Strip optional markdown fences
        msg = msg.strip().strip("```json").strip("```").strip()
        parsed = json.loads(msg)
        return {
            "valid": bool(parsed.get("valid", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "notes": str(parsed.get("notes", ""))[:200],
        }
    except Exception as exc:
        logger.warning("DeepSeek validation failed for claim: %s", exc)
        return {"valid": False, "confidence": 0.0, "notes": f"validator_error: {exc}"}


def _embed_openai(text: str, api_key: str, timeout: int = 30) -> Optional[list[float]]:
    """Embed text via OpenAI text-embedding-3-small (FROZEN per Nuzantara golden rule)."""
    import urllib.request
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps({"model": "text-embedding-3-small", "input": text}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        return payload["data"][0]["embedding"]
    except Exception as exc:
        logger.error("OpenAI embed failed: %s", exc)
        return None


def extract_for_notebook(
    domain: str,
    *,
    limit: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the full pipeline for one domain. Returns summary dict."""
    nb = DOMAIN_TO_NB.get(domain)
    if nb is None:
        return {"domain": domain, "status": "unknown_domain", "claims_emitted": 0}

    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(tz=timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "domain": domain,
        "run_id": run_id,
        "started_at": started,
        "notebook_id": nb["id"],
        "claims_extracted": 0,
        "claims_validated": 0,
        "claims_emitted": 0,
        "errors": [],
    }

    if dry_run:
        summary["status"] = "dry_run"
        return summary

    # 1. Extract claims via NLM
    raw_claims = _run_nlm_extract(nb["id"], nb["extract_prompt_subject"], limit=limit)
    summary["claims_extracted"] = len(raw_claims)
    if not raw_claims:
        summary["status"] = "no_claims_extracted"
        return summary

    # 2. Validate each via DeepSeek
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not deepseek_key:
        summary["status"] = "missing_DEEPSEEK_API_KEY"
        summary["errors"].append("DEEPSEEK_API_KEY not set — claims emitted with deepseek_validated=False")

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        summary["status"] = "missing_OPENAI_API_KEY"
        return summary

    # Lazy-import Qdrant + the chunk model so the script is importable
    # without those deps (e.g. for unit tests).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend-rag"))
    from backend.core.nlm_shadow_chunk import NLMShadowChunk  # type: ignore
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import PointStruct, VectorParams, Distance

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
    qclient = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Ensure the collection exists with 1536 OpenAI dim
    collection_name = "nlm_shadow_hybrid"
    try:
        qclient.get_collection(collection_name)
    except Exception:
        logger.info("Creating Qdrant collection %s (vector_size=1536)", collection_name)
        qclient.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )

    points: list[PointStruct] = []
    for idx, raw in enumerate(raw_claims, start=1):
        claim_text = (raw.get("claim") or "").strip()
        if len(claim_text) < 10:
            continue

        # 2. validate
        validation = (
            _validate_with_deepseek(claim_text, deepseek_key)
            if deepseek_key else
            {"valid": False, "confidence": 0.0, "notes": "no_validator_configured"}
        )
        if not validation["valid"] or validation["confidence"] < 0.5:
            continue
        summary["claims_validated"] += 1

        # 3. embed
        vec = _embed_openai(claim_text, openai_key)
        if vec is None:
            summary["errors"].append(f"embed_failed: {claim_text[:40]}")
            continue

        # 4. build chunk + upsert
        chunk = NLMShadowChunk(
            chunk_id=f"nlm_shadow_{nb['label']}_{run_id}_{idx:03d}",
            claim_text=claim_text,
            nb_id=nb["id"],
            nb_label=nb["label"],
            nlm_source_id=raw.get("source_id"),
            extraction_run_id=run_id,
            deepseek_validated=True,
            deepseek_confidence=validation["confidence"],
            deepseek_notes=validation["notes"] or None,
        )
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload=chunk.to_qdrant_payload(),
        ))

    if points:
        qclient.upsert(collection_name=collection_name, points=points)
        summary["claims_emitted"] = len(points)
    summary["status"] = "ok" if points else "no_valid_claims"
    summary["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sprint 2 NLM Shadow Graphing extractor")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--notebook", help="Single domain (e.g. immigration, company, tax)")
    g.add_argument("--all-domains", action="store_true",
                   help="Run extractor for all 5 domains sequentially")
    parser.add_argument("--limit", type=int, default=20, help="Max claims per notebook")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip CLI calls; print plan only")
    args = parser.parse_args()

    if args.notebook:
        domains = [args.notebook]
    else:
        domains = list(DOMAIN_TO_NB.keys())

    overall: list[dict[str, Any]] = []
    for domain in domains:
        result = extract_for_notebook(domain, limit=args.limit, dry_run=args.dry_run)
        overall.append(result)
        print(json.dumps(result, indent=2, default=str))
        # Throttle between NBs to avoid CLI rate limits
        if not args.dry_run and len(domains) > 1:
            time.sleep(5)

    # Final summary line for cron logs
    total_emitted = sum(r.get("claims_emitted", 0) for r in overall)
    print(f"\n=== Shadow extraction complete: {total_emitted} claim(s) emitted across {len(domains)} domain(s) ===")
    sys.exit(0 if total_emitted > 0 or all(r.get("status") == "dry_run" for r in overall) else 1)


if __name__ == "__main__":
    main()

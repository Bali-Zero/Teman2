#!/usr/bin/env python3
"""Devils Advocate runner v2 — NB-grounded red-team via DeepSeek v4-pro.

Architecture (post-2026-05-10 cross-LLM consultation):

  Stage 1: regex extractor — find regulation codes in target document
  Stage 2: NB ground-truth verification (cached, batched per notebook)
           - Redis cache (TTL 24h positive, 6h negative)
           - asyncio.Semaphore(5) parallel queries to NotebookLM
           - State enum: VERIFIED_EXISTS / NOT_FOUND_IN_QUERIED / CONFLICTED / UNKNOWN
           - Failure mode: degraded (NEEDS_FIX_GROUNDING_UNAVAILABLE, not BLOCK)
  Stage 3: DeepSeek v4-pro red-team WITH ground_truth dict
           - System prompt safety net: any reg_code in doc NOT in ground_truth → UNVERIFIED_CITATION
  Stage 4: post-processing override
           - DeepSeek verdict=PASS but ground_truth has NOT_FOUND → override to BLOCK
  Stage 5: publish redteam.completed (extended payload with ground_truth + nb_available + degraded)

Cost: ~$0.013/run DeepSeek + $0 NotebookLM. Latency: 30-90s (cache hit) or 60-180s (cache miss).
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import publish

LOG_PATH = Path.home() / "logs" / "devils-advocate-runner.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("da-runner")

# ────────────────────────────────────────────────────────────────────────────
# Brand cortex paths (read-only, loaded into system prompt)
# ────────────────────────────────────────────────────────────────────────────
REDTEAM_CORTEX_DIR = Path.home() / ".claude/skills/bali-zero-brand/redteam-cortex"
CONSTITUTION = Path.home() / ".claude/skills/bali-zero-brand/constitution.md"
FORBIDDEN_PHRASES = Path.home() / ".claude/skills/bali-zero-brand/voice/forbidden-phrases.md"

# ────────────────────────────────────────────────────────────────────────────
# DeepSeek config
# ────────────────────────────────────────────────────────────────────────────
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"
DEEPSEEK_TIMEOUT_SEC = 300

# ────────────────────────────────────────────────────────────────────────────
# NotebookLM registry (domain → ordered list of notebooks)
# Trust tier: lower number = higher trust (curated > intel feed)
# ────────────────────────────────────────────────────────────────────────────
NB_REGISTRY = {
    "tax": [
        {"uuid": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853", "name": "NB-4", "tier": 1, "role": "primary_curated"},
        {"uuid": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f", "name": "NB-INTEL-Tax", "tier": 2, "role": "intel_feed"},
        {"uuid": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76", "name": "NB-INTEL-Regulation", "tier": 2, "role": "intel_feed"},
        {"uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe", "name": "NB-INTEL-Press", "tier": 3, "role": "press_signal"},
    ],
    "regulatory": [
        {"uuid": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76", "name": "NB-INTEL-Regulation", "tier": 1, "role": "primary_intel"},
        {"uuid": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853", "name": "NB-4", "tier": 2, "role": "cross_check_tax"},
        {"uuid": "933509f9-1561-403d-bd44-4a7a67a36df2", "name": "NB-3", "tier": 2, "role": "cross_check_company"},
        {"uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe", "name": "NB-INTEL-Press", "tier": 3, "role": "press_signal"},
    ],
    "visa": [
        {"uuid": "cff93ab0-813a-42f2-a8de-36987e724271", "name": "NB-2", "tier": 1, "role": "primary_curated"},
        {"uuid": "1ed02e54-542f-426a-94f8-53c5ffde4b7d", "name": "NB-INTEL-Immigration", "tier": 2, "role": "intel_feed"},
        {"uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe", "name": "NB-INTEL-Press", "tier": 3, "role": "press_signal"},
    ],
    "property": [
        {"uuid": "d9438180-5e63-4e2a-a473-6061101f6a8d", "name": "NB-5", "tier": 1, "role": "primary_curated"},
        {"uuid": "85207af3-352f-4554-8d2a-18f42cc541ba", "name": "NB-6", "tier": 2, "role": "ops_compliance"},
        {"uuid": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76", "name": "NB-INTEL-Regulation", "tier": 2, "role": "cross_check_regulation"},
        {"uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe", "name": "NB-INTEL-Press", "tier": 3, "role": "press_signal"},
    ],
    "company": [  # PT PMA setup, KBLI, OSS NIB
        {"uuid": "933509f9-1561-403d-bd44-4a7a67a36df2", "name": "NB-3", "tier": 1, "role": "primary_curated"},
        {"uuid": "85207af3-352f-4554-8d2a-18f42cc541ba", "name": "NB-6", "tier": 2, "role": "ops_compliance"},
        {"uuid": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76", "name": "NB-INTEL-Regulation", "tier": 2, "role": "intel_feed"},
        {"uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe", "name": "NB-INTEL-Press", "tier": 3, "role": "press_signal"},
    ],
    "other": [],  # no NB grounding for low-stakes / generic
}

NB_QUERY_TIMEOUT_SEC = 90      # per single nlm batch query call
NB_PARALLEL_LIMIT = 5          # asyncio.Semaphore for nlm parallel calls
NB_CACHE_TTL_POSITIVE = 86400  # 24h for VERIFIED_EXISTS
NB_CACHE_TTL_NEGATIVE = 21600  # 6h for NOT_FOUND_IN_QUERIED

# ────────────────────────────────────────────────────────────────────────────
# Stage 1 — Regex extractor for Indonesian regulation codes
# ────────────────────────────────────────────────────────────────────────────
# Patterns ordered by specificity (more specific first)
REG_PATTERNS = [
    # KEP-NN/PJ/YYYY (DJP director general decisions)
    (re.compile(r"\bKEP[-\s]?(\d+)/PJ/(\d{4})\b", re.IGNORECASE), "KEP", lambda m: f"KEP-{m.group(1)}/PJ/{m.group(2)}"),
    # PMK NN/YYYY or NN/PMK.03/YYYY (Ministry of Finance regs — multiple variants)
    (re.compile(r"\bPMK[-\s]+(\d+)/(\d{4})\b", re.IGNORECASE), "PMK", lambda m: f"PMK-{m.group(1)}/{m.group(2)}"),
    (re.compile(r"\b(\d+)/PMK\.\d{2}/(\d{4})\b", re.IGNORECASE), "PMK", lambda m: f"PMK-{m.group(1)}/{m.group(2)}"),
    (re.compile(r"\bPMK\s+Nomor\s+(\d+)\s+Tahun\s+(\d{4})\b", re.IGNORECASE), "PMK", lambda m: f"PMK-{m.group(1)}/{m.group(2)}"),
    # PER-NN/PJ/YYYY (DJP regulations)
    (re.compile(r"\bPER[-\s]?(\d+)/PJ/(\d{4})\b", re.IGNORECASE), "PER", lambda m: f"PER-{m.group(1)}/PJ/{m.group(2)}"),
    # Permenkumham NN/YYYY
    (re.compile(r"\bPermenkumham[-\s]+(\d+)/(\d{4})\b", re.IGNORECASE), "Permenkumham",
     lambda m: f"Permenkumham-{m.group(1)}/{m.group(2)}"),
    # SKB Nomor NN/YYYY (Joint Decrees)
    (re.compile(r"\bSKB[-\s]+(?:Nomor[-\s]+)?(\d+)[-\s]?(?:Tahun[-\s]+)?(\d{4})\b", re.IGNORECASE), "SKB",
     lambda m: f"SKB-Nomor-{m.group(1)}/{m.group(2)}"),
    # PP NN/YYYY (Government Regulations)
    (re.compile(r"\bPP[-\s]+(?:No\.?[-\s]+)?(\d+)/(\d{4})\b", re.IGNORECASE), "PP",
     lambda m: f"PP-{m.group(1)}/{m.group(2)}"),
    (re.compile(r"\bPP\s+(?:Nomor|No\.?)\s+(\d+)\s+Tahun\s+(\d{4})\b", re.IGNORECASE), "PP",
     lambda m: f"PP-{m.group(1)}/{m.group(2)}"),
    # Perpres NN/YYYY (Presidential Regulations)
    (re.compile(r"\bPerpres[-\s]+(\d+)/(\d{4})\b", re.IGNORECASE), "Perpres",
     lambda m: f"Perpres-{m.group(1)}/{m.group(2)}"),
    # UU NN/YYYY (Laws)
    (re.compile(r"\bUU[-\s]+(?:No\.?[-\s]+)?(\d+)/(\d{4})\b", re.IGNORECASE), "UU",
     lambda m: f"UU-{m.group(1)}/{m.group(2)}"),
]


def extract_reg_codes(target_text: str) -> list[dict]:
    """Stage 1: extract all regulation codes from the document.

    Returns list of dicts: {canonical, raw_match, type, position}.
    De-duplicates by canonical form.
    """
    found = {}
    for pat, reg_type, canonicalize in REG_PATTERNS:
        for m in pat.finditer(target_text):
            try:
                canonical = canonicalize(m).upper()
            except Exception:
                continue
            # Skip if already seen (canonical dedup)
            if canonical in found:
                continue
            found[canonical] = {
                "canonical": canonical,
                "raw_match": m.group(0),
                "type": reg_type,
                "first_position": m.start(),
            }
    out = sorted(found.values(), key=lambda x: x["first_position"])
    log.info("Stage 1 extracted %d unique reg codes: %s",
             len(out), [r["canonical"] for r in out[:10]])
    return out


# ────────────────────────────────────────────────────────────────────────────
# Stage 2 — NB ground-truth verification (cached + parallel)
# ────────────────────────────────────────────────────────────────────────────
def _cache_key(canonical: str) -> str:
    """Redis key for cached NB ground-truth lookup."""
    return f"da:nb_reg:{canonical}"


def _redis_get_cache(canonical: str) -> dict | None:
    """Fetch from Redis cache if present + not expired."""
    try:
        from eventbus.publisher import _client
        raw = _client().get(_cache_key(canonical))
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        log.debug("cache get failed for %s: %s", canonical, e)
        return None


def _redis_set_cache(canonical: str, value: dict, ttl: int) -> None:
    """Store in Redis with TTL (positive=24h, negative=6h)."""
    try:
        from eventbus.publisher import _client
        _client().setex(_cache_key(canonical), ttl, json.dumps(value))
    except Exception as e:
        log.warning("cache set failed for %s: %s", canonical, e)


async def _nlm_query_async(notebook_uuid: str, question: str, sem: asyncio.Semaphore) -> tuple[bool, str]:
    """Run nlm batch query as subprocess. Returns (success, raw_output)."""
    async with sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                "/Users/nuzantara/.local/bin/nlm", "batch", "query",
                "--notebooks", notebook_uuid, question,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(),
                                                        timeout=NB_QUERY_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return (False, f"timeout after {NB_QUERY_TIMEOUT_SEC}s")
            output = stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return (False, f"exit={proc.returncode}: {stderr.decode('utf-8', errors='replace')[:300]}")
            return (True, output)
        except Exception as e:
            return (False, f"exception: {e}")


def _parse_nlm_answer(raw_output: str, canonical: str) -> dict:
    """Parse nlm batch query stdout to extract YES/NO + citation.

    nlm batch query output is a TUI table. Look for the answer line.
    Returns: {exists: bool|None, raw_answer: str, citation: str}
    """
    # Look for "answer" key in the JSON-ish output line
    answer_match = re.search(r"\{['\"]answer['\"]:\s*['\"]([^'\"]+)['\"]", raw_output)
    if answer_match:
        answer = answer_match.group(1)
    else:
        # Fallback: look for YES/NO in the table cells
        if re.search(r"\bYES\b", raw_output, re.IGNORECASE):
            answer = "YES"
        elif re.search(r"\bNO\b", raw_output, re.IGNORECASE):
            answer = "NO"
        else:
            return {"exists": None, "raw_answer": raw_output[:500], "citation": ""}

    answer_upper = answer.upper().strip()
    exists: bool | None
    if answer_upper.startswith("YES"):
        exists = True
    elif answer_upper.startswith("NO"):
        exists = False
    else:
        # Ambiguous — extract any inline citation
        exists = None

    return {
        "exists": exists,
        "raw_answer": answer[:1000],
        "citation": "",
    }


async def _verify_one_reg_in_nbs(canonical: str, nb_list: list[dict],
                                 sem: asyncio.Semaphore) -> dict:
    """Verify one reg_code across all relevant notebooks.

    Returns ground-truth dict with state enum:
      - VERIFIED_EXISTS: at least one curated NB confirms
      - NOT_FOUND_IN_QUERIED: no NB confirms (not "doesn't exist", just "not in our DB")
      - CONFLICTED: curated says exists but intel says not (or vice versa)
      - UNKNOWN: all queries failed
      - DEGRADED: NotebookLM unreachable
    """
    # Cache check
    cached = _redis_get_cache(canonical)
    if cached:
        cached["from_cache"] = True
        return cached

    question = (
        f"Does {canonical} (Indonesian government regulation) exist in your sources? "
        f"Answer YES or NO. If YES, give a 1-line description of what it covers."
    )

    # Query each NB in parallel
    tasks = [_nlm_query_async(nb["uuid"], question, sem) for nb in nb_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed_per_nb = []
    for nb, res in zip(nb_list, results):
        if isinstance(res, Exception):
            parsed_per_nb.append({
                "nb": nb["name"], "tier": nb["tier"], "uuid": nb["uuid"],
                "exists": None, "raw_answer": f"exception: {res}", "ok": False,
            })
            continue
        ok, raw = res
        if not ok:
            parsed_per_nb.append({
                "nb": nb["name"], "tier": nb["tier"], "uuid": nb["uuid"],
                "exists": None, "raw_answer": raw, "ok": False,
            })
            continue
        parsed = _parse_nlm_answer(raw, canonical)
        parsed_per_nb.append({
            "nb": nb["name"], "tier": nb["tier"], "uuid": nb["uuid"],
            "exists": parsed["exists"], "raw_answer": parsed["raw_answer"], "ok": True,
        })

    # Aggregate state per trust hierarchy
    successful = [p for p in parsed_per_nb if p["ok"]]
    if not successful:
        result = {
            "canonical": canonical,
            "state": "DEGRADED",
            "rationale": "all NB queries failed",
            "per_nb": parsed_per_nb,
            "from_cache": False,
        }
        # Don't cache degraded — retry next time
        return result

    curated_says = [p for p in successful if p["tier"] == 1]
    intel_says = [p for p in successful if p["tier"] >= 2]

    # Conflict detection
    curated_exists = [p["exists"] for p in curated_says if p["exists"] is not None]
    intel_exists = [p["exists"] for p in intel_says if p["exists"] is not None]

    if curated_exists:
        # Curated NB has authoritative answer
        if all(curated_exists):
            state = "VERIFIED_EXISTS"
        elif not any(curated_exists):
            # Curated says NO — check intel for warning
            if intel_exists and any(intel_exists):
                state = "CONFLICTED"  # curated NO, intel YES — likely scraping noise
            else:
                state = "NOT_FOUND_IN_QUERIED"
        else:
            state = "CONFLICTED"  # mixed signals from curated NBs
    elif intel_exists:
        # Only intel feed has data
        if all(intel_exists):
            state = "VERIFIED_EXISTS"  # intel-only is weaker but still positive
        else:
            state = "NOT_FOUND_IN_QUERIED"
    else:
        state = "UNKNOWN"

    result = {
        "canonical": canonical,
        "state": state,
        "rationale": f"curated={len(curated_says)} intel={len(intel_says)} state={state}",
        "per_nb": parsed_per_nb,
        "from_cache": False,
    }

    # Cache result with appropriate TTL
    if state == "VERIFIED_EXISTS":
        _redis_set_cache(canonical, result, NB_CACHE_TTL_POSITIVE)
    elif state == "NOT_FOUND_IN_QUERIED":
        _redis_set_cache(canonical, result, NB_CACHE_TTL_NEGATIVE)
    # CONFLICTED / UNKNOWN / DEGRADED: don't cache

    return result


async def verify_reg_codes_async(reg_codes: list[dict], domain: str) -> dict:
    """Stage 2 main entry: returns ground_truth dict + nb_available flag."""
    nb_list = NB_REGISTRY.get(domain, [])
    if not nb_list:
        log.warning("Stage 2 skipped: no NB configured for domain=%s", domain)
        return {"ground_truth": {}, "nb_available": False, "reason": "no_nb_for_domain"}
    if not reg_codes:
        log.info("Stage 2 skipped: no reg_codes extracted in Stage 1")
        return {"ground_truth": {}, "nb_available": True, "reason": "no_reg_codes"}

    log.info("Stage 2 verifying %d reg codes against %d notebooks (domain=%s)",
             len(reg_codes), len(nb_list), domain)
    t0 = time.time()
    sem = asyncio.Semaphore(NB_PARALLEL_LIMIT)
    tasks = [_verify_one_reg_in_nbs(r["canonical"], nb_list, sem) for r in reg_codes]
    results = await asyncio.gather(*tasks)

    ground_truth = {r["canonical"]: r for r in results}
    elapsed = time.time() - t0

    # Statistics
    states = {}
    cache_hits = 0
    for r in results:
        states[r["state"]] = states.get(r["state"], 0) + 1
        if r.get("from_cache"):
            cache_hits += 1
    log.info("Stage 2 complete in %.1fs: %s (cache_hits=%d/%d)",
             elapsed, states, cache_hits, len(results))

    # Determine if NB is "available" — if >=50% queries returned non-DEGRADED, mark available
    degraded = sum(1 for r in results if r["state"] == "DEGRADED")
    nb_available = degraded < (len(results) / 2)

    return {
        "ground_truth": ground_truth,
        "nb_available": nb_available,
        "stats": {"states": states, "cache_hits": cache_hits, "elapsed_sec": round(elapsed, 1)},
    }


# ────────────────────────────────────────────────────────────────────────────
# Stage 3 — DeepSeek with ground truth
# ────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT_BASE = """You are a brutal legal/tax/audit reviewer for Bali Zero \
(Indonesian business services agency: visa, company, tax, property).

Your ONLY job: find what is BROKEN in the document. Find errors, contradictions, \
missing regulations, hallucinated regulation codes (KEP, PMK, Permenkumham, PER, SKB), \
vague claims that need concrete numbers, paraphrased citations that should be verbatim, \
taboo phrases.

Do NOT congratulate. Do NOT summarize what is good. Do NOT pad. Be terse, surgical, irreverent.

# Brand cortex scope

The "Brand context" section below has been pre-filtered to match the document type \
you are reviewing. Apply ONLY the rules listed there. If a rule about typography, \
body length, hero images, or layout is NOT in your cortex, it does NOT apply to this \
document — do not invent rules from outside the cortex.

# NotebookLM ground truth (CRITICAL — overrides your training)

The "Ground truth from NotebookLM" section below has authoritative verification \
of every regulation code mentioned in the document, sourced from Bali Zero's \
NotebookLM database (60 notebooks, 2970 indonesian regulatory documents).

For each regulation code, the ground_truth dict has a STATE enum:

- VERIFIED_EXISTS: NotebookLM confirms this regulation exists. The document \
may cite it without disclaimer.
- NOT_FOUND_IN_QUERIED: NotebookLM has no record. This is a strong signal of \
HALLUCINATION. Flag as CRITICAL regulatory_hallucination unless the document \
itself explicitly disclaims it as "unverified" or "pending JDIH lookup".
- CONFLICTED: curated NB and intel feed disagree. The document MUST disclaim \
this code as "pending verification". If cited as fact, flag HIGH.
- UNKNOWN / DEGRADED: ground truth unavailable. Treat conservatively — flag any \
unverified citation as HIGH unless explicitly disclaimed.

# Safety net (CRITICAL)

If the document cites ANY regulation code (KEP-NN/PJ/YYYY, PMK NN/YYYY, \
PER-NN/PJ/YYYY, SKB Nomor NN, etc.) that is NOT in the ground_truth dict, \
this means our regex extractor missed it. Flag as HIGH "UNVERIFIED_CITATION" \
finding so we can investigate.
"""


def _load_brand_context(target_path: str = "") -> str:
    """Load the document-type-specific cortex split."""
    doc_type = _classify_target(target_path)
    cortex_file = REDTEAM_CORTEX_DIR / f"{doc_type}.md"

    if cortex_file.exists():
        try:
            txt = cortex_file.read_text()
            log.info("loaded redteam-cortex split: %s (%d chars)", doc_type, len(txt))
            return f"# Bali Zero red-team rules — scope: {doc_type.upper()}\n\n{txt}"
        except Exception as e:
            log.warning("cortex split %s load failed: %s", cortex_file, e)
    log.warning("cortex split not found at %s — using empty context", cortex_file)
    return ""


def _classify_target(target_path: str) -> str:
    """Return one of: research | slide | quote (default research)."""
    p = target_path.lower()
    if "/research/" in p or (p.endswith(".md") and "research" in p):
        return "research"
    if "slides.json" in p or "/war-room/output/" in p or "/carousel/" in p:
        return "slide"
    if "internal-print-a4" in p or "/quote/" in p or "/email-template/" in p:
        return "quote"
    if p.endswith(".md"):
        return "research"
    return "research"


def _format_ground_truth_for_prompt(ground_truth: dict) -> str:
    """Render ground_truth dict as compact prompt-friendly markdown table."""
    if not ground_truth:
        return "(no regulation codes verified — none found in document)"
    lines = ["| Code | State | Rationale |", "|---|---|---|"]
    for code, info in sorted(ground_truth.items()):
        rationale = info.get("rationale", "")[:80]
        lines.append(f"| `{code}` | **{info['state']}** | {rationale} |")
    return "\n".join(lines)


def call_deepseek(target_text: str, target_path: str, brand_ctx: str,
                  ground_truth_payload: dict) -> dict:
    """Stage 3: DeepSeek v4-pro with ground truth injected."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        secrets = Path.home() / ".nuzantara-secrets.env"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                if line.startswith("export DEEPSEEK_API_KEY=") or line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY missing")

    system = SYSTEM_PROMPT_BASE
    if brand_ctx:
        system += f"\n\n# Brand context\n\n{brand_ctx}"

    gt_md = _format_ground_truth_for_prompt(ground_truth_payload.get("ground_truth", {}))
    nb_status = "AVAILABLE" if ground_truth_payload.get("nb_available") else "DEGRADED"
    system += f"\n\n# Ground truth from NotebookLM (status: {nb_status})\n\n{gt_md}"

    system += """

# Output format (REQUIRED — strict JSON, no markdown wrapper)

{
  "verdict": "PASS" | "NEEDS_FIX" | "BLOCK",
  "findings": [
    {
      "category": "regulatory_hallucination" | "numerical_error" | "internal_contradiction" | "vague_claim" | "taboo_violation" | "unverified_citation",
      "severity": "critical" | "high" | "medium" | "low",
      "evidence": "verbatim quote from the document",
      "proposed_fix": "one concrete sentence"
    }
  ],
  "verdict_rationale": "1-2 sentences"
}

# Verdict rules

- 1+ critical → BLOCK
- 1+ high (no critical) → NEEDS_FIX
- 3+ medium/low total → NEEDS_FIX
- 0-2 medium/low only → PASS
- 0 findings → PASS
"""

    user_msg = (
        f"Target document path: {target_path}\n\n"
        f"---BEGIN DOCUMENT---\n{target_text}\n---END DOCUMENT---\n\n"
        f"Attack this document. Use the ground_truth table to verify every regulation "
        f"code citation. Return JSON only."
    )

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 16000,
        "reasoning_effort": "high",
    }

    log.info("calling DeepSeek (model=%s, target=%s, doc_chars=%d, ground_truth_codes=%d)",
             DEEPSEEK_MODEL, target_path, len(target_text),
             len(ground_truth_payload.get("ground_truth", {})))
    t0 = time.time()
    result = subprocess.run(
        ["curl", "-sf", "-X", "POST", DEEPSEEK_URL,
         "-H", f"Authorization: Bearer {api_key}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(body)],
        capture_output=True, text=True, timeout=DEEPSEEK_TIMEOUT_SEC,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        raise RuntimeError(f"curl failed exit={result.returncode}: {result.stderr[:500]}")
    parsed = json.loads(result.stdout)
    log.info("DeepSeek responded in %.1fs (model=%s, finish=%s)",
             elapsed, parsed.get("model", "?"),
             parsed.get("choices", [{}])[0].get("finish_reason", "?"))
    return parsed


def parse_da_response(deepseek_raw: dict) -> dict:
    """Extract verdict + findings from DeepSeek response."""
    try:
        content = deepseek_raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"DeepSeek response missing content: {e}")

    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        report = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            report = json.loads(content[start:end + 1])
        else:
            raise RuntimeError("DeepSeek content not JSON-parseable")

    report.setdefault("verdict", "NEEDS_FIX")
    report["verdict"] = str(report["verdict"]).upper()
    if report["verdict"] not in ("PASS", "NEEDS_FIX", "BLOCK"):
        report["verdict"] = "NEEDS_FIX"
    report.setdefault("findings", [])

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in report["findings"]:
        sev = (f.get("severity") or "").lower()
        if sev in counts:
            counts[sev] += 1
    report["counts"] = counts
    return report


# ────────────────────────────────────────────────────────────────────────────
# Stage 4 — Post-processing override
# ────────────────────────────────────────────────────────────────────────────
def post_process_override(report: dict, ground_truth_payload: dict) -> dict:
    """If DeepSeek says PASS but ground_truth has hallucinations, override to BLOCK.

    This is the safety net for cases where DeepSeek ignores ground_truth.
    """
    gt = ground_truth_payload.get("ground_truth", {})
    not_found_codes = [code for code, info in gt.items() if info["state"] == "NOT_FOUND_IN_QUERIED"]

    if not_found_codes and report["verdict"] == "PASS":
        log.warning("OVERRIDE: DeepSeek said PASS but ground_truth has NOT_FOUND for: %s",
                    not_found_codes)
        # Inject synthetic findings + override verdict
        for code in not_found_codes:
            report["findings"].append({
                "category": "regulatory_hallucination",
                "severity": "critical",
                "evidence": f"Document cites '{code}' which NotebookLM ground-truth could not verify",
                "proposed_fix": f"Verify {code} against JDIH primary text or remove citation",
                "source": "post_process_override",
            })
        report["counts"]["critical"] = sum(1 for f in report["findings"]
                                            if f.get("severity") == "critical")
        report["verdict"] = "BLOCK"
        report["verdict_rationale"] = (report.get("verdict_rationale", "") +
                                       f" [POST-PROCESS OVERRIDE: {len(not_found_codes)} hallucinations from NB]")

    if not ground_truth_payload.get("nb_available") and report["verdict"] == "PASS":
        log.warning("OVERRIDE: NB unavailable, downgrading PASS to NEEDS_FIX (degraded mode)")
        report["verdict"] = "NEEDS_FIX"
        report["verdict_rationale"] = (report.get("verdict_rationale", "") +
                                       " [DEGRADED: NotebookLM ground-truth unavailable]")

    return report


# ────────────────────────────────────────────────────────────────────────────
# Stage 5 — Publish + persist
# ────────────────────────────────────────────────────────────────────────────
def _slug_from_target(target: str) -> str:
    name = Path(target).stem
    m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", name)
    return m.group(1) if m else name


def _expected_report_path(slug: str) -> Path:
    return Path(f"/tmp/devils-advocate-{slug}-report.json")


def _expected_deepseek_path(slug: str) -> Path:
    return Path(f"/tmp/devils-advocate-{slug}-deepseek.json")


def write_report(report: dict, deepseek_raw: dict, ground_truth_payload: dict,
                 target: str, slug: str) -> Path:
    deepseek_path = _expected_deepseek_path(slug)
    deepseek_path.write_text(json.dumps(deepseek_raw, indent=2))

    full_report = {
        "target": target,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "deepseek_response_path": str(deepseek_path),
        "verdict": report["verdict"],
        "findings": report["findings"],
        "verdict_rationale": report.get("verdict_rationale", ""),
        "counts": report["counts"],
        "ground_truth": ground_truth_payload.get("ground_truth", {}),
        "nb_available": ground_truth_payload.get("nb_available", False),
        "nb_stats": ground_truth_payload.get("stats", {}),
        "runner_version": "v2-nb-grounded-2026-05-10",
    }
    report_path = _expected_report_path(slug)
    report_path.write_text(json.dumps(full_report, indent=2))
    log.info("wrote report=%s deepseek=%s", report_path, deepseek_path)
    return report_path


def emit_redteam_event(report: dict, ground_truth_payload: dict,
                       target: str, topic_slug: str, domain: str,
                       trace_id: str | None) -> str:
    verdict = report["verdict"]
    counts = report["counts"]
    slug = _slug_from_target(target)
    payload = {
        "source": "devils-advocate",
        "target_path": target,
        "topic_slug": topic_slug,
        "domain": domain,
        "status": verdict,
        "critical_count": int(counts.get("critical", 0)),
        "high_count": int(counts.get("high", 0)),
        "medium_count": int(counts.get("medium", 0)),
        "low_count": int(counts.get("low", 0)),
        "report_path": str(_expected_report_path(slug)),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    event_id = publish("redteam.completed", payload, emitted_by="devils-advocate-runner",
                       trace_id=trace_id)
    log.info("published redteam.completed event_id=%s verdict=%s counts=%s nb_avail=%s",
             event_id, verdict, counts, ground_truth_payload.get("nb_available"))
    return event_id


def emit_block_fallback(target: str, topic_slug: str, domain: str,
                        trace_id: str | None, reason: str) -> str:
    slug = _slug_from_target(target)
    payload = {
        "source": "devils-advocate",
        "target_path": target,
        "topic_slug": topic_slug,
        "domain": domain,
        "status": "BLOCK",
        "critical_count": 1, "high_count": 0, "medium_count": 0, "low_count": 0,
        "report_path": f"/tmp/da-runner-failure-{slug}.txt",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(payload["report_path"]).write_text(f"DA runner failure: {reason}\n")
    event_id = publish("redteam.completed", payload, emitted_by="devils-advocate-runner",
                       trace_id=trace_id)
    log.warning("emitted BLOCK fallback event_id=%s reason=%s", event_id, reason)
    return event_id


# ────────────────────────────────────────────────────────────────────────────
# Main orchestration (sync entry, uses asyncio.run for Stage 2)
# ────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--topic-slug", required=True)
    ap.add_argument("--domain", required=True,
                    choices=["tax", "regulatory", "property", "visa", "other"])
    ap.add_argument("--trace-id", default=None)
    ap.add_argument("--source-event-id", default=None)
    ap.add_argument("--skip-nb", action="store_true",
                    help="Skip Stage 2 (NB grounding) — useful for debug")
    args = ap.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        emit_block_fallback(args.target, args.topic_slug, args.domain, args.trace_id,
                            f"target not found: {args.target}")
        return 1

    try:
        target_text = target_path.read_text()
    except Exception as e:
        emit_block_fallback(args.target, args.topic_slug, args.domain, args.trace_id,
                            f"target read failed: {e}")
        return 1

    if len(target_text) > 60000:
        log.warning("target too large (%d chars), truncating to 60k", len(target_text))
        target_text = target_text[:60000] + "\n\n[...TRUNCATED]"

    # Stage 1: extract reg codes
    reg_codes = extract_reg_codes(target_text)

    # Stage 2: NB ground-truth (async)
    if args.skip_nb or args.domain == "other":
        log.info("Stage 2 SKIPPED (skip_nb=%s, domain=%s)", args.skip_nb, args.domain)
        ground_truth_payload = {"ground_truth": {}, "nb_available": False, "reason": "skipped"}
    else:
        try:
            ground_truth_payload = asyncio.run(verify_reg_codes_async(reg_codes, args.domain))
        except Exception as e:
            log.exception("Stage 2 failed catastrophically: %s", e)
            ground_truth_payload = {"ground_truth": {}, "nb_available": False, "reason": f"exception: {e}"}

    # Stage 3: DeepSeek with ground truth
    brand_ctx = _load_brand_context(args.target)
    slug = _slug_from_target(args.target)
    try:
        deepseek_raw = call_deepseek(target_text, args.target, brand_ctx, ground_truth_payload)
    except Exception as e:
        log.exception("DeepSeek call failed: %s", e)
        emit_block_fallback(args.target, args.topic_slug, args.domain, args.trace_id,
                            f"DeepSeek failed: {e}")
        return 1

    try:
        report = parse_da_response(deepseek_raw)
    except Exception as e:
        log.exception("response parse failed: %s", e)
        emit_block_fallback(args.target, args.topic_slug, args.domain, args.trace_id,
                            f"parse failed: {e}")
        return 1

    # Stage 4: post-process override
    report = post_process_override(report, ground_truth_payload)

    # Stage 5: persist + publish
    write_report(report, deepseek_raw, ground_truth_payload, args.target, slug)
    emit_redteam_event(report, ground_truth_payload, args.target, args.topic_slug,
                       args.domain, args.trace_id)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("DA runner interrupted")
        sys.exit(130)

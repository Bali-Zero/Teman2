# KBLI Full-Spectrum Enrichment Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich all 1,241 unenriched KBLI codes with tiered editorial content (gold/silver/bronze) using a local multi-model pipeline orchestrated by a single Python script.

**Architecture:** 4-phase pipeline: (0) Gemini CLI classifies codes into HIGH/MEDIUM/LOW Bali relevance, (1) three parallel tracks enrich each tier using DeepSeek-R1:32b + NLM (HIGH), Qwen3.5:9b (MEDIUM), and deterministic-only (LOW), (2) Gemma3:12b validates all output against source JSON, (3) merged output is written to `apps/mouth/data/kbli-gold-all.json`. SQLite checkpoint enables resume-from-failure.

**Tech Stack:** Python 3.11, Ollama (deepseek-r1:32b, qwen3.5:9b, gemma3:12b), Gemini CLI 0.35+, NotebookLM MCP (nlm CLI), SQLite3, asyncio/subprocess

**Key Codebase References:**

- Source JSON: `apps/kbli-navigator/data/kbli-2025.json` (1,563 codes)
- Output target: `apps/mouth/data/kbli-gold-all.json` (flat `{code: {fields...}}`)
- Existing gold TS: `apps/kbli-navigator/lib/kbli-gold-content.ts` (322 entries — reference only, NOT write target)
- Existing script: `apps/kbli-navigator/scripts/generate_gold_content.py` (deterministic builders + LLM batch)
- Data flow: `kbli-gold-all.json` → `apps/mouth/src/lib/kbli-data.ts:transformCode()` → `page.tsx` (gold overrides intel_2026)
- NLM notebooks: company=`2e84b9b9-...`, tax=`837b620b-...`, operations=`3e1baa5f-...`

---

## File Structure

| File                                   | Action           | Responsibility                                                         |
| -------------------------------------- | ---------------- | ---------------------------------------------------------------------- |
| `scripts/kbli_enrich_pipeline.py`      | Create           | Main orchestrator: phases 0-3, CLI args, logging                       |
| `scripts/kbli_enrich_triage.py`        | Create           | Phase 0: Gemini CLI triage (parallel batch classification)             |
| `scripts/kbli_enrich_generate.py`      | Create           | Phase 1: LLM content generation (DeepSeek, Qwen, deterministic)        |
| `scripts/kbli_enrich_validate.py`      | Create           | Phase 2: Gemma validation + hallucination filter                       |
| `scripts/kbli_enrich_write.py`         | Create           | Phase 3: Merge to kbli-gold-all.json + build test                      |
| `scripts/kbli_enrich_db.py`            | Create           | SQLite checkpoint database (state machine per code)                    |
| `scripts/kbli_enrich_deterministic.py` | Create           | Deterministic field builders (extracted from generate_gold_content.py) |
| `scripts/kbli_enrich_nlm.py`           | Create           | NLM query wrapper (cross_notebook_query + research_start)              |
| `data/kbli_enrich.db`                  | Create (runtime) | SQLite checkpoint database                                             |
| `data/triage_results.json`             | Create (runtime) | Phase 0 output: tier classification per code                           |

---

## Task 1: SQLite Checkpoint Database

**Files:**

- Create: `scripts/kbli_enrich_db.py`

- [ ] **Step 1: Write the checkpoint database module**

```python
#!/usr/bin/env python3
"""SQLite checkpoint database for KBLI enrichment pipeline.
Each code has a state: PENDING → TRIAGED → GENERATING → GENERATED → VALIDATING → COMPLETED | FAILED
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "kbli_enrich.db"

STATES = ("PENDING", "TRIAGED", "GENERATING", "GENERATED", "VALIDATING", "COMPLETED", "FAILED")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kbli_enrichment (
            code TEXT PRIMARY KEY,
            tier TEXT DEFAULT 'PENDING',       -- HIGH / MEDIUM / LOW
            state TEXT DEFAULT 'PENDING',
            triage_score REAL DEFAULT 0,
            triage_reasoning TEXT DEFAULT '',
            nlm_context TEXT DEFAULT '',        -- NLM regulatory intel (HIGH tier only)
            generated_content TEXT DEFAULT '',  -- JSON blob of 6 fields
            validation_errors TEXT DEFAULT '',  -- JSON array of errors
            retry_count INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def init_codes(conn: sqlite3.Connection, codes: list[dict]) -> int:
    """Initialize all codes as PENDING. Returns count of newly inserted codes."""
    inserted = 0
    for c in codes:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO kbli_enrichment (code) VALUES (?)",
                (c["kode_kbli_2025"],)
            )
            inserted += conn.total_changes
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def set_triage(conn: sqlite3.Connection, code: str, tier: str, score: float, reasoning: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET tier=?, triage_score=?, triage_reasoning=?, state='TRIAGED', updated_at=datetime('now') WHERE code=?",
        (tier, score, reasoning, code)
    )
    conn.commit()


def set_state(conn: sqlite3.Connection, code: str, state: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state=?, updated_at=datetime('now') WHERE code=?",
        (state, code)
    )
    conn.commit()


def set_nlm_context(conn: sqlite3.Connection, code: str, context: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET nlm_context=?, updated_at=datetime('now') WHERE code=?",
        (context, code)
    )
    conn.commit()


def set_generated(conn: sqlite3.Connection, code: str, content: dict) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET generated_content=?, state='GENERATED', updated_at=datetime('now') WHERE code=?",
        (json.dumps(content, ensure_ascii=False), code)
    )
    conn.commit()


def set_validated(conn: sqlite3.Connection, code: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state='COMPLETED', updated_at=datetime('now') WHERE code=?",
        (code,)
    )
    conn.commit()


def set_failed(conn: sqlite3.Connection, code: str, errors: list[str]) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state='FAILED', validation_errors=?, retry_count=retry_count+1, updated_at=datetime('now') WHERE code=?",
        (json.dumps(errors), code)
    )
    conn.commit()


def get_codes_by_state(conn: sqlite3.Connection, state: str) -> list[dict]:
    cur = conn.execute("SELECT * FROM kbli_enrichment WHERE state=?", (state,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_codes_by_tier(conn: sqlite3.Connection, tier: str) -> list[dict]:
    cur = conn.execute("SELECT * FROM kbli_enrichment WHERE tier=?", (tier,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_stats(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT state, COUNT(*) FROM kbli_enrichment GROUP BY state")
    return dict(cur.fetchall())


def get_tier_stats(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT tier, COUNT(*) FROM kbli_enrichment GROUP BY tier")
    return dict(cur.fetchall())


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO pipeline_meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    cur = conn.execute("SELECT value FROM pipeline_meta WHERE key=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None
```

- [ ] **Step 2: Verify module imports correctly**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -c "from scripts.kbli_enrich_db import get_conn, STATES; print('OK:', STATES)"`
Expected: `OK: ('PENDING', 'TRIAGED', ...)`

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_db.py
git commit -m "feat(kbli): add SQLite checkpoint database for enrichment pipeline"
```

---

## Task 2: Deterministic Field Builders

**Files:**

- Create: `scripts/kbli_enrich_deterministic.py`

Extract and adapt the deterministic builders from `apps/kbli-navigator/scripts/generate_gold_content.py` (lines 35-398). These functions generate `whatYouNeed`, `whatChanged`, and `youllAlsoNeed` from raw JSON data without any LLM call.

- [ ] **Step 1: Create the deterministic module**

```python
#!/usr/bin/env python3
"""Deterministic field builders for KBLI enrichment.
Extracted from apps/kbli-navigator/scripts/generate_gold_content.py.
Generates whatYouNeed, whatChanged, youllAlsoNeed from raw JSON data — no LLM.
"""
import re
import json
from pathlib import Path

# --- Copy RISK_MAP, SCALE_MAP, STATUS_MAP, SECTOR_RELATED, _KEWAJIBAN_TRANSLATIONS
# --- from apps/kbli-navigator/scripts/generate_gold_content.py lines 35-220
# --- (exact copy, do not modify)

# Then copy these functions verbatim:
# - _translate_kewajiban(raw: str) -> str           (lines 222-239)
# - build_what_you_need(code: dict) -> str           (lines 242-362)
# - build_what_changed(code: dict) -> str            (lines 365-378)
# - build_youll_also_need(code: dict) -> str         (lines 381-398)

def build_deterministic_fields(code: dict) -> dict:
    """Build all 3 deterministic fields for a KBLI code entry."""
    return {
        "whatYouNeed": build_what_you_need(code),
        "whatChanged": build_what_changed(code),
        "youllAlsoNeed": build_youll_also_need(code),
    }
```

The step here is to literally copy the functions from the existing script. Do NOT rewrite them — they are battle-tested.

- [ ] **Step 2: Test against a known code**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
import json
from scripts.kbli_enrich_deterministic import build_deterministic_fields
with open('apps/kbli-navigator/data/kbli-2025.json') as f:
    data = json.load(f)
code_56101 = next(c for c in data['data'] if c['kode_kbli_2025'] == '56101')
result = build_deterministic_fields(code_56101)
print('whatYouNeed (first 200):', result['whatYouNeed'][:200])
print('whatChanged:', result['whatChanged'])
print('youllAlsoNeed (first 100):', result['youllAlsoNeed'][:100])
"
```

Expected: Non-empty strings for all 3 fields. `whatChanged` should contain "direct match" or similar.

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_deterministic.py
git commit -m "feat(kbli): extract deterministic field builders for enrichment pipeline"
```

---

## Task 3: Gemini CLI Triage Module (Phase 0)

**Files:**

- Create: `scripts/kbli_enrich_triage.py`

- [ ] **Step 1: Create the triage module**

````python
#!/usr/bin/env python3
"""Phase 0: Classify 1,241 KBLI codes into HIGH/MEDIUM/LOW Bali relevance using Gemini CLI.
Runs 6 parallel Gemini CLI processes (batches of ~200 codes each).
"""
import json
import subprocess
import tempfile
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

GEMINI_BIN = "/opt/homebrew/bin/gemini"

TRIAGE_PROMPT_TEMPLATE = """You are an expert on Indonesian business classification (KBLI 2025) and foreign investment in Bali.

Classify each KBLI code below into exactly one tier based on Bali relevance for foreign investors (PT PMA):

**HIGH** — Directly relevant to Bali's economy: tourism, hospitality, F&B, real estate, wellness/spa, tech/digital nomad services, creative industries, education (yoga/surf/beauty academies), healthcare (clinics/IV drips), sports facilities (padel/gyms), transport (rental/ride-hailing), professional services commonly used by expats (legal, consulting, architecture, photography).

**MEDIUM** — Indirectly relevant or general business: wholesale/retail trade, general manufacturing, logistics, financial services, HR/staffing, general education, telecoms, media production, environmental services. Could serve Bali market but not specifically Bali-centric.

**LOW** — Minimal Bali relevance: heavy industry, mining, oil/gas, large-scale agriculture (non-Bali crops), government services, military/defense, public utilities, highly restricted sectors, obscure niche manufacturing. Also includes BPS_ONLY codes with no PP28 licensing data.

For each code, respond with ONLY a JSON array. No extra text, no markdown fences:
[{{"code": "XXXXX", "tier": "HIGH|MEDIUM|LOW", "score": 0-100, "reasoning": "one sentence"}}]

Here are the codes to classify:

{codes_block}
"""


def format_code_block(codes: list[dict]) -> str:
    """Format codes for the Gemini prompt."""
    lines = []
    for c in codes:
        per_skala_summary = "none" if not c.get("per_skala") else f"{len(c['per_skala'])} scale(s)"
        lines.append(
            f"- {c['kode_kbli_2025']}: {c['judul']} | PMA: {c.get('pma_status', '?')} | "
            f"Mapping: {c.get('status_mapping', '?')} | Licensing: {per_skala_summary}"
        )
    return "\n".join(lines)


def run_gemini_batch(batch_id: int, codes: list[dict], output_dir: Path) -> Path:
    """Run a single Gemini CLI triage batch. Returns path to output JSON file."""
    codes_block = format_code_block(codes)
    prompt = TRIAGE_PROMPT_TEMPLATE.format(codes_block=codes_block)

    output_file = output_dir / f"triage_batch_{batch_id}.json"

    # Write prompt to temp file to avoid shell escaping issues
    prompt_file = output_dir / f"triage_prompt_{batch_id}.txt"
    prompt_file.write_text(prompt)

    try:
        result = subprocess.run(
            [GEMINI_BIN, "-p", prompt],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path(__file__).parent.parent)
        )

        raw = result.stdout.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        output_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
        print(f"  Batch {batch_id}: {len(parsed)} codes classified ✓")
        return output_file

    except subprocess.TimeoutExpired:
        print(f"  Batch {batch_id}: TIMEOUT (300s)")
        return output_file
    except json.JSONDecodeError as e:
        print(f"  Batch {batch_id}: JSON parse error: {e}")
        # Save raw for debugging
        (output_dir / f"triage_raw_{batch_id}.txt").write_text(result.stdout if result else "")
        return output_file
    except Exception as e:
        print(f"  Batch {batch_id}: Error: {e}")
        return output_file


def run_triage(codes: list[dict], batch_size: int = 200, max_workers: int = 6) -> list[dict]:
    """Run Phase 0 triage: classify all codes in parallel Gemini CLI batches.
    Returns list of {code, tier, score, reasoning} dicts.
    """
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Split into batches
    batches = [codes[i:i + batch_size] for i in range(0, len(codes), batch_size)]
    print(f"Phase 0 — Triage: {len(codes)} codes in {len(batches)} batches (max {max_workers} parallel)")

    all_results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_gemini_batch, i, batch, output_dir): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_id = futures[future]
            try:
                output_file = future.result()
                if output_file.exists():
                    batch_results = json.loads(output_file.read_text())
                    all_results.extend(batch_results)
            except Exception as e:
                print(f"  Batch {batch_id} failed: {e}")

    # Save merged results
    merged_file = output_dir / "triage_results.json"
    merged_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"  Total classified: {len(all_results)} codes → {merged_file}")

    return all_results
````

- [ ] **Step 2: Test with a dry run of 10 codes**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
import json
from scripts.kbli_enrich_triage import run_triage
with open('apps/kbli-navigator/data/kbli-2025.json') as f:
    data = json.load(f)
# Pick 10 diverse codes for testing
test_codes = [c for c in data['data'] if c['kode_kbli_2025'] in ['56101','62199','01111','38211','84111','10710','55203','06100','93114','96230']]
results = run_triage(test_codes, batch_size=10, max_workers=1)
for r in results:
    print(f\"{r['code']}: {r['tier']} (score {r.get('score', '?')}) — {r.get('reasoning', '')[:60]}\")
"
```

Expected: 56101/62199/55203/93114/96230 → HIGH, 10710/38211 → HIGH or MEDIUM, 06100/84111 → LOW, 01111 → MEDIUM or LOW.

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_triage.py
git commit -m "feat(kbli): add Gemini CLI triage module for enrichment pipeline"
```

---

## Task 4: NLM Query Wrapper

**Files:**

- Create: `scripts/kbli_enrich_nlm.py`

- [ ] **Step 1: Create the NLM query module**

```python
#!/usr/bin/env python3
"""NLM (NotebookLM) query wrapper for KBLI enrichment.
Queries NB-company, NB-tax, NB-operations via nlm CLI for regulatory intel.
"""
import subprocess
import json
from pathlib import Path

NLM_BIN = str(Path.home() / ".local/bin/nlm")

# NLM notebook IDs from NLM_NOTEBOOKS registry
NB_COMPANY = "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4"
NB_TAX = "837b620b-2aca-43ab-812e-97ca92bdad1d"
NB_OPERATIONS = "3e1baa5f-680f-4499-9430-23a901576bcc"


def query_notebook(notebook_id: str, query: str, timeout: int = 120) -> str:
    """Query a single NLM notebook. Returns the response text."""
    try:
        result = subprocess.run(
            [NLM_BIN, "query", notebook_id, query],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[NLM TIMEOUT after {timeout}s]"
    except Exception as e:
        return f"[NLM ERROR: {e}]"


def query_regulatory_intel(codes: list[dict], timeout: int = 120) -> dict[str, str]:
    """Query NLM for regulatory intelligence on 1-2 KBLI codes.
    Queries company (licensing), tax, and operations notebooks.
    Returns {code: combined_intel_text}.
    """
    code_list = ", ".join(c["kode_kbli_2025"] for c in codes)
    titles = ", ".join(f"{c['kode_kbli_2025']} ({c['judul']})" for c in codes)

    query = (
        f"For KBLI codes {titles}: What are the specific licensing requirements, "
        f"risk level, PMA restrictions, mandatory certifications, "
        f"and any recent regulatory changes under PP28/2025 and BKPM 5/2025? "
        f"Include any Bali-specific enforcement or compliance requirements."
    )

    # Query all 3 notebooks
    company_resp = query_notebook(NB_COMPANY, query, timeout)
    tax_resp = query_notebook(NB_TAX, f"Tax implications for KBLI {code_list}: PBJT, PPh, PPN, LKPM obligations", timeout)
    ops_resp = query_notebook(NB_OPERATIONS, f"Operational compliance for KBLI {code_list}: permits, inspections, reporting", timeout)

    combined = f"## Licensing & Company\n{company_resp}\n\n## Tax\n{tax_resp}\n\n## Operations\n{ops_resp}"

    # Map combined intel to each code
    result = {}
    for c in codes:
        result[c["kode_kbli_2025"]] = combined
    return result


def research_bps_only(code: str, judul: str) -> str:
    """Run NLM fast research for a BPS_ONLY code to find sector-specific regulations."""
    try:
        result = subprocess.run(
            [NLM_BIN, "research", "start",
             "--query", f"Indonesian KBLI {code} {judul} licensing requirements regulations 2025 2026",
             "--mode", "fast",
             "--notebook", NB_COMPANY],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout.strip()
    except Exception as e:
        return f"[NLM Research Error: {e}]"
```

- [ ] **Step 2: Test with a single query**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
from scripts.kbli_enrich_nlm import query_notebook, NB_COMPANY
result = query_notebook(NB_COMPANY, 'What are the licensing requirements for KBLI 56101 restaurant in Bali?')
print('Response length:', len(result))
print('First 300 chars:', result[:300])
"
```

Expected: Non-empty response with licensing details from NB-company.

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_nlm.py
git commit -m "feat(kbli): add NLM query wrapper for enrichment pipeline"
```

---

## Task 5: LLM Content Generation Module (Phase 1)

**Files:**

- Create: `scripts/kbli_enrich_generate.py`

This is the core module. It handles all 3 tiers:

- HIGH: NLM context → DeepSeek-R1:32b (3 narrative fields) + deterministic (3 fields)
- MEDIUM: Qwen3.5:9b (3 narrative fields) + deterministic (3 fields)
- LOW: Qwen3.5:9b (whatItMeans only) + deterministic (3 fields)

- [ ] **Step 1: Create the generation module**

````python
#!/usr/bin/env python3
"""Phase 1: Generate editorial content for all KBLI codes.
HIGH tier: NLM + DeepSeek-R1:32b (3 narrative) + deterministic (3 structured)
MEDIUM tier: Qwen3.5:9b (3 narrative) + deterministic (3 structured)
LOW tier: Qwen3.5:9b (whatItMeans only) + deterministic (3 structured)
"""
import json
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DEEPSEEK_MODEL = "deepseek-r1:32b"
QWEN_MODEL = "qwen3.5:9b"

# Reuse the exact system prompt from generate_gold_content.py
# It asks for 3 fields: whatItMeans, baliContext, zantaraOpener
SYSTEM_PROMPT_3FIELDS = """You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.

For each KBLI 2025 business code provided, generate THREE fields:

1. whatItMeans: Plain English explanation, 3-4 sentences, ~250-400 chars.
   - Lead with the core activity using a dash
   - Name SPECIFIC examples from the uraian — translate them
   - Include scope clarifications when the uraian mentions them
   - Translate ALL Indonesian terms. No bureaucratic language.

2. baliContext: Bali-specific practical intelligence, 3-5 sentences, ~350-550 chars.
   - Include at least ONE of: price range (IDR), Bali location, enforcement reality, named permit
   - Include ONE insider tip or common mistake specific to THIS code
   - Write in English

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.
   - Start with Bali context
   - Be specific to the business activity

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

SYSTEM_PROMPT_DEEPSEEK = """You are a senior Indonesian regulatory analyst. You have access to NotebookLM regulatory intelligence below.

Using BOTH the raw KBLI data AND the regulatory context provided, generate THREE editorial fields for each KBLI code. Your output must be more detailed and regulatory-precise than generic LLM output because you have actual regulatory citations.

For each code generate:

1. whatItMeans: 3-5 sentences explaining the business activity in plain English. Include specific examples from the uraian. Mention what IS and is NOT covered. ~300-500 chars.

2. baliContext: 4-6 sentences of Bali-specific practical intelligence. Include: specific permits beyond NIB, enforcement realities, pricing/location specifics, insider tips. Reference the regulatory context provided. ~400-700 chars.

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

SYSTEM_PROMPT_MINIMAL = """For each KBLI code, write a plain English explanation of what this business activity covers.
2-3 sentences, ~200-300 chars. Lead with the core activity. Translate all Indonesian terms.
Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "..."}]}
No extra text."""


def ollama_generate(prompt: str, model: str, system: str = "", timeout: int = 360) -> str:
    """Call Ollama generate endpoint. Returns raw response text."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 8192},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def parse_llm_response(raw: str) -> list[dict]:
    """Parse LLM JSON response, handling markdown fences and thinking tags."""
    text = raw
    # Strip <think>...</think> blocks (DeepSeek-R1)
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown fences
    if "```" in text:
        text = text.split("```json")[-1] if "```json" in text else text.split("```")[1]
        text = text.split("```")[0]
    text = text.strip()
    parsed = json.loads(text)
    return parsed.get("results", []) if isinstance(parsed, dict) else parsed


def generate_high_tier(codes: list[dict], nlm_contexts: dict[str, str], batch_size: int = 2) -> dict[str, dict]:
    """Generate 3 narrative fields for HIGH tier codes using DeepSeek-R1:32b + NLM context."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt_parts = []
        for c in batch:
            code = c["kode_kbli_2025"]
            nlm = nlm_contexts.get(code, "No regulatory context available.")
            prompt_parts.append(
                f"code: {code}\njudul: {c['judul']}\n"
                f"uraian: {c.get('uraian', '')[:800]}\n"
                f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
                f"sektor_id: {c.get('sektor_id', 'N/A')}\n\n"
                f"--- REGULATORY CONTEXT (from NotebookLM) ---\n{nlm[:2000]}\n---"
            )

        prompt = "\n\n".join(prompt_parts)
        print(f"  HIGH batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}: {[c['kode_kbli_2025'] for c in batch]}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, DEEPSEEK_MODEL, system=SYSTEM_PROMPT_DEEPSEEK, timeout=600)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results


def generate_medium_tier(codes: list[dict], batch_size: int = 5) -> dict[str, dict]:
    """Generate 3 narrative fields for MEDIUM tier codes using Qwen3.5:9b."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\njudul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:600]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )
        print(f"  MEDIUM batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, QWEN_MODEL, system=SYSTEM_PROMPT_3FIELDS)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results


def generate_low_tier(codes: list[dict], batch_size: int = 10) -> dict[str, dict]:
    """Generate whatItMeans only for LOW tier codes using Qwen3.5:9b."""
    results = {}
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i:i + batch_size]
        prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\njudul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:400]}"
            for c in batch
        )
        print(f"  LOW batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...", end="", flush=True)

        try:
            raw = ollama_generate(prompt, QWEN_MODEL, system=SYSTEM_PROMPT_MINIMAL, timeout=180)
            parsed = parse_llm_response(raw)
            for item in parsed:
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {"whatItMeans": item.get("whatItMeans", "")}
            print(f" ✓")
        except Exception as e:
            print(f" ✗ {e}")

    return results
````

- [ ] **Step 2: Smoke test with one code per tier**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
import json
from scripts.kbli_enrich_generate import generate_low_tier
with open('apps/kbli-navigator/data/kbli-2025.json') as f:
    data = json.load(f)
test = [c for c in data['data'] if c['kode_kbli_2025'] == '01111']
result = generate_low_tier(test, batch_size=1)
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```

Expected: `{"01111": {"whatItMeans": "..."}}` with a non-empty string.

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_generate.py
git commit -m "feat(kbli): add LLM content generation module (DeepSeek/Qwen/deterministic)"
```

---

## Task 6: Validation Module (Phase 2)

**Files:**

- Create: `scripts/kbli_enrich_validate.py`

- [ ] **Step 1: Create the validation module**

```python
#!/usr/bin/env python3
"""Phase 2: Validate generated content against source JSON using Gemma3:12b.
Cross-checks: risk levels, PMA status, hallucinated numbers.
"""
import json
import re
import urllib.request

OLLAMA_URL = "http://localhost:11434"
GEMMA_MODEL = "gemma3:12b"

# Known capital amounts that are correct (whitelist)
VALID_CAPITAL_AMOUNTS = {
    "2.5 Billion", "2,5 Miliardi", "2.5B", "Rp 2.5B", "IDR 2.5B",
    "10 Billion", "10B", "IDR 10B", "Rp 10B",
    "25 Billion", "25B",  # OJK Manajer Investasi
    "50 Billion", "50B",  # Construction SBU
}


def validate_pma_consistency(generated: dict, source: dict) -> list[str]:
    """Check that generated content doesn't contradict PMA status."""
    errors = []
    pma_status = source.get("pma_status", "")
    content_text = " ".join(str(v) for v in generated.values())

    if pma_status == "TERTUTUP" and "100% foreign" in content_text.lower():
        errors.append(f"PMA CONTRADICTION: Source says TERTUTUP but content mentions 100% foreign ownership")
    if pma_status == "TERBUKA" and "closed to foreign" in content_text.lower():
        errors.append(f"PMA CONTRADICTION: Source says TERBUKA but content says closed to foreign")

    return errors


def validate_risk_consistency(generated: dict, source: dict) -> list[str]:
    """Check that risk levels mentioned match per_skala data."""
    errors = []
    per_skala = source.get("per_skala", [])
    content_text = " ".join(str(v) for v in generated.values()).lower()

    valid_risks = {s.get("kategori_risiko", "").lower() for s in per_skala}
    valid_risks_en = set()
    for r in valid_risks:
        if "rendah" in r and "menengah" not in r:
            valid_risks_en.add("low risk")
        elif "menengah rendah" in r:
            valid_risks_en.add("medium-low")
        elif "menengah tinggi" in r:
            valid_risks_en.add("medium-high")
        elif "tinggi" in r and "menengah" not in r:
            valid_risks_en.add("high risk")

    # Check for contradictions (only if per_skala has data)
    if valid_risks_en and not per_skala == []:
        if "high risk" in content_text and "high risk" not in valid_risks_en and "high" not in " ".join(valid_risks):
            errors.append(f"RISK MISMATCH: Content says 'high risk' but source has {valid_risks}")
        if "low risk" in content_text and "low risk" not in valid_risks_en and "rendah" not in " ".join(valid_risks):
            if "menengah rendah" not in " ".join(valid_risks):  # medium-low contains "low"
                errors.append(f"RISK MISMATCH: Content says 'low risk' but source has {valid_risks}")

    return errors


def validate_no_hallucinated_numbers(generated: dict) -> list[str]:
    """Check for suspicious invented numbers (capital amounts, percentages, fees)."""
    errors = []
    content_text = " ".join(str(v) for v in generated.values())

    # Check for IDR amounts that aren't in the whitelist
    idr_pattern = r"IDR\s+[\d,.]+\s*(?:Billion|Million|Trillion|B|M|T)"
    matches = re.findall(idr_pattern, content_text, re.IGNORECASE)
    for m in matches:
        if not any(valid in m for valid in VALID_CAPITAL_AMOUNTS):
            errors.append(f"SUSPICIOUS AMOUNT: '{m}' — verify against source data")

    return errors


def validate_entry(generated: dict, source: dict) -> list[str]:
    """Run all validation checks on a single generated entry."""
    errors = []
    errors.extend(validate_pma_consistency(generated, source))
    errors.extend(validate_risk_consistency(generated, source))
    errors.extend(validate_no_hallucinated_numbers(generated))

    # Check required fields are non-empty
    for field in ("whatItMeans", "whatYouNeed", "whatChanged"):
        if not generated.get(field, "").strip():
            errors.append(f"EMPTY FIELD: {field} is empty or missing")

    return errors


def validate_batch(entries: dict[str, dict], source_data: dict[str, dict]) -> dict[str, list[str]]:
    """Validate all generated entries. Returns {code: [errors]} for codes with issues."""
    results = {}
    for code, content in entries.items():
        source = source_data.get(code, {})
        errors = validate_entry(content, source)
        if errors:
            results[code] = errors
    return results
```

- [ ] **Step 2: Test validation with a known-good entry**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
from scripts.kbli_enrich_validate import validate_entry
good = {'whatItMeans': 'Restaurant in Bali', 'whatYouNeed': 'NIB + Standard', 'whatChanged': 'Direct match', 'baliContext': 'Seminyak area', 'youllAlsoNeed': '56301', 'zantaraOpener': 'Opening a restaurant?'}
source = {'pma_status': 'TERBUKA', 'per_skala': [{'kategori_risiko': 'Menengah Tinggi'}]}
errors = validate_entry(good, source)
print('Errors:', errors)
# Should be empty or minimal
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_validate.py
git commit -m "feat(kbli): add validation module for enrichment pipeline"
```

---

## Task 7: JSON Writer Module (Phase 3)

**Files:**

- Create: `scripts/kbli_enrich_write.py`

- [ ] **Step 1: Create the writer module**

```python
#!/usr/bin/env python3
"""Phase 3: Write enriched content to kbli-gold-all.json and test build.
Output format: flat JSON object {code: {6 fields + optional tkaInfo}}.
Merges with existing entries (preserves tkaInfo, overwrites content fields).
"""
import json
import subprocess
from pathlib import Path

GOLD_JSON = Path(__file__).parent.parent / "apps" / "mouth" / "data" / "kbli-gold-all.json"
KBLI_NAV_ROOT = Path(__file__).parent.parent / "apps" / "kbli-navigator"


def load_existing_gold() -> dict:
    """Load existing kbli-gold-all.json."""
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            return json.load(f)
    return {}


def merge_and_write(new_entries: dict[str, dict], dry_run: bool = False) -> int:
    """Merge new entries into kbli-gold-all.json.
    Preserves existing tkaInfo. Overwrites content fields.
    Returns count of entries written.
    """
    existing = load_existing_gold()
    merged_count = 0

    for code, content in new_entries.items():
        if code in existing:
            # Preserve tkaInfo if it exists
            tka_info = existing[code].get("tkaInfo")
            existing[code].update(content)
            if tka_info:
                existing[code]["tkaInfo"] = tka_info
        else:
            existing[code] = content
        merged_count += 1

    if dry_run:
        print(f"DRY RUN: Would write {merged_count} entries to {GOLD_JSON}")
        return merged_count

    # Write with sorted keys for stable diffs
    with open(GOLD_JSON, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"  Wrote {merged_count} entries to {GOLD_JSON}")
    print(f"  Total entries in file: {len(existing)}")
    return merged_count


def test_build() -> bool:
    """Run Next.js build to verify SSG pages generate correctly."""
    print("  Running Next.js build test...")
    try:
        result = subprocess.run(
            ["npx", "next", "build"],
            capture_output=True, text=True, timeout=600,
            cwd=str(KBLI_NAV_ROOT),
        )
        if result.returncode == 0:
            # Check for SSG page count
            if "1595" in result.stdout or "Generating static pages" in result.stdout:
                print("  Build OK ✓")
                return True
        print(f"  Build FAILED (exit {result.returncode})")
        print(f"  stderr: {result.stderr[:500]}")
        return False
    except subprocess.TimeoutExpired:
        print("  Build TIMEOUT")
        return False
```

- [ ] **Step 2: Test merge with dry run**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
from scripts.kbli_enrich_write import merge_and_write
test = {'99999': {'whatItMeans': 'Test', 'whatYouNeed': 'Test', 'whatChanged': 'Test', 'baliContext': 'Test', 'youllAlsoNeed': 'Test', 'zantaraOpener': 'Test'}}
merge_and_write(test, dry_run=True)
"
```

Expected: `DRY RUN: Would write 1 entries`

- [ ] **Step 3: Commit**

```bash
git add scripts/kbli_enrich_write.py
git commit -m "feat(kbli): add JSON writer module for enrichment pipeline"
```

---

## Task 8: Main Orchestrator

**Files:**

- Create: `scripts/kbli_enrich_pipeline.py`

- [ ] **Step 1: Create the orchestrator**

```python
#!/usr/bin/env python3
"""
KBLI Full-Spectrum Enrichment Pipeline
Orchestrates all 4 phases: Triage → Generate → Validate → Write

Usage:
  python scripts/kbli_enrich_pipeline.py                    # Full run
  python scripts/kbli_enrich_pipeline.py --phase 0          # Triage only
  python scripts/kbli_enrich_pipeline.py --phase 1          # Generate only (requires triage)
  python scripts/kbli_enrich_pipeline.py --phase 2          # Validate only
  python scripts/kbli_enrich_pipeline.py --phase 3          # Write only
  python scripts/kbli_enrich_pipeline.py --resume            # Resume from last checkpoint
  python scripts/kbli_enrich_pipeline.py --dry-run           # Don't write final output
  python scripts/kbli_enrich_pipeline.py --tier HIGH         # Process only HIGH tier
  python scripts/kbli_enrich_pipeline.py --limit 10          # Process max 10 codes
"""
import json
import sys
import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kbli_enrich_db import (
    get_conn, init_codes, set_triage, set_state, set_nlm_context,
    set_generated, set_validated, set_failed, get_codes_by_state,
    get_codes_by_tier, get_stats, get_tier_stats, set_meta, get_meta,
)
from scripts.kbli_enrich_triage import run_triage
from scripts.kbli_enrich_deterministic import build_deterministic_fields
from scripts.kbli_enrich_generate import generate_high_tier, generate_medium_tier, generate_low_tier
from scripts.kbli_enrich_nlm import query_regulatory_intel
from scripts.kbli_enrich_validate import validate_batch
from scripts.kbli_enrich_write import merge_and_write, test_build

DATA_JSON = Path(__file__).parent.parent / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
GOLD_JSON = Path(__file__).parent.parent / "apps" / "mouth" / "data" / "kbli-gold-all.json"


def load_source_data() -> tuple[list[dict], dict[str, dict]]:
    """Load KBLI source data. Returns (list, {code: entry} lookup)."""
    with open(DATA_JSON) as f:
        data = json.load(f)
    entries = data["data"]
    lookup = {c["kode_kbli_2025"]: c for c in entries}
    return entries, lookup


def get_unenriched_codes(all_codes: list[dict]) -> list[dict]:
    """Filter to codes not already in kbli-gold-all.json."""
    existing = set()
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            existing = set(json.load(f).keys())
    return [c for c in all_codes if c["kode_kbli_2025"] not in existing]


def phase_0_triage(conn, codes: list[dict]) -> None:
    """Phase 0: Classify codes into HIGH/MEDIUM/LOW via Gemini CLI."""
    print(f"\n{'='*60}")
    print(f"PHASE 0 — TRIAGE ({len(codes)} codes)")
    print(f"{'='*60}")

    already_triaged = get_codes_by_state(conn, "TRIAGED")
    if already_triaged:
        print(f"  {len(already_triaged)} codes already triaged, skipping...")
        codes = [c for c in codes if c["kode_kbli_2025"] not in {r["code"] for r in already_triaged}]

    if not codes:
        print("  All codes already triaged.")
        return

    results = run_triage(codes)

    for r in results:
        set_triage(conn, r["code"], r.get("tier", "LOW"), r.get("score", 0), r.get("reasoning", ""))

    stats = get_tier_stats(conn)
    print(f"\n  Tier distribution: {stats}")
    set_meta(conn, "phase_0_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_1_generate(conn, source_lookup: dict, tier_filter: str = None) -> None:
    """Phase 1: Generate content for all tiers."""
    print(f"\n{'='*60}")
    print(f"PHASE 1 — GENERATE")
    print(f"{'='*60}")

    for tier in (["HIGH", "MEDIUM", "LOW"] if not tier_filter else [tier_filter]):
        tier_codes = get_codes_by_tier(conn, tier)
        # Filter to only TRIAGED state (not already GENERATED/COMPLETED)
        pending = [c for c in tier_codes if c["state"] == "TRIAGED"]
        if not pending:
            print(f"\n  {tier}: No pending codes.")
            continue

        print(f"\n  {tier} TIER: {len(pending)} codes to process")

        # Get source data for these codes
        code_data = [source_lookup[c["code"]] for c in pending if c["code"] in source_lookup]

        if tier == "HIGH":
            # NLM enrichment first (pairs of 2)
            print("  Querying NLM for regulatory intel...")
            nlm_contexts = {}
            for i in range(0, len(code_data), 2):
                batch = code_data[i:i+2]
                try:
                    contexts = query_regulatory_intel(batch)
                    nlm_contexts.update(contexts)
                    for code in contexts:
                        set_nlm_context(conn, code, contexts[code])
                except Exception as e:
                    print(f"    NLM error: {e}")

            # DeepSeek generation
            print("  Generating with DeepSeek-R1:32b...")
            narrative = generate_high_tier(code_data, nlm_contexts, batch_size=2)

        elif tier == "MEDIUM":
            print("  Generating with Qwen3.5:9b...")
            narrative = generate_medium_tier(code_data, batch_size=5)

        else:  # LOW
            print("  Generating minimal content with Qwen3.5:9b...")
            narrative = generate_low_tier(code_data, batch_size=10)

        # Merge narrative + deterministic for each code
        for c in code_data:
            code = c["kode_kbli_2025"]
            set_state(conn, code, "GENERATING")

            # Deterministic fields (always generated)
            det = build_deterministic_fields(c)

            # Narrative fields (from LLM)
            narr = narrative.get(code, {})

            # Merge: narrative fields + deterministic fields
            merged = {
                "whatItMeans": narr.get("whatItMeans", ""),
                "whatYouNeed": det["whatYouNeed"],
                "whatChanged": det["whatChanged"],
                "baliContext": narr.get("baliContext", ""),
                "youllAlsoNeed": det["youllAlsoNeed"],
                "zantaraOpener": narr.get("zantaraOpener", ""),
            }

            set_generated(conn, code, merged)

    set_meta(conn, "phase_1_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_2_validate(conn, source_lookup: dict) -> None:
    """Phase 2: Validate all GENERATED entries."""
    print(f"\n{'='*60}")
    print(f"PHASE 2 — VALIDATE")
    print(f"{'='*60}")

    generated = get_codes_by_state(conn, "GENERATED")
    if not generated:
        print("  No entries to validate.")
        return

    print(f"  Validating {len(generated)} entries...")

    entries = {}
    for row in generated:
        code = row["code"]
        content = json.loads(row["generated_content"]) if row["generated_content"] else {}
        entries[code] = content

    errors = validate_batch(entries, source_lookup)

    passed = 0
    failed = 0
    for code in entries:
        code_errors = errors.get(code, [])
        if code_errors:
            set_failed(conn, code, code_errors)
            failed += 1
        else:
            set_validated(conn, code)
            passed += 1

    print(f"  Passed: {passed}, Failed: {failed}")
    if failed > 0:
        print(f"  Run with --phase 1 to retry failed codes")

    set_meta(conn, "phase_2_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_3_write(conn, dry_run: bool = False) -> None:
    """Phase 3: Write all COMPLETED entries to kbli-gold-all.json."""
    print(f"\n{'='*60}")
    print(f"PHASE 3 — WRITE")
    print(f"{'='*60}")

    completed = get_codes_by_state(conn, "COMPLETED")
    if not completed:
        print("  No completed entries to write.")
        return

    entries = {}
    for row in completed:
        content = json.loads(row["generated_content"]) if row["generated_content"] else {}
        entries[row["code"]] = content

    count = merge_and_write(entries, dry_run=dry_run)

    if not dry_run and count > 0:
        print("\n  Running build test...")
        if test_build():
            set_meta(conn, "phase_3_completed", time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            print("  WARNING: Build failed! Check output manually.")


def main():
    parser = argparse.ArgumentParser(description="KBLI Full-Spectrum Enrichment Pipeline")
    parser.add_argument("--phase", type=int, choices=[0, 1, 2, 3], help="Run specific phase only")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Don't write final output")
    parser.add_argument("--tier", choices=["HIGH", "MEDIUM", "LOW"], help="Process only this tier")
    parser.add_argument("--limit", type=int, help="Max codes to process")
    args = parser.parse_args()

    all_codes, source_lookup = load_source_data()
    unenriched = get_unenriched_codes(all_codes)

    if args.limit:
        unenriched = unenriched[:args.limit]

    print(f"KBLI Enrichment Pipeline")
    print(f"  Total codes: {len(all_codes)}")
    print(f"  Unenriched: {len(unenriched)}")
    print(f"  Phase: {'ALL' if args.phase is None else args.phase}")

    conn = get_conn()
    init_codes(conn, unenriched)

    if args.resume:
        stats = get_stats(conn)
        print(f"  Resuming from checkpoint: {stats}")

    if args.phase is None or args.phase == 0:
        pending = get_codes_by_state(conn, "PENDING")
        pending_data = [source_lookup[c["code"]] for c in pending if c["code"] in source_lookup]
        if pending_data:
            phase_0_triage(conn, pending_data)

    if args.phase is None or args.phase == 1:
        phase_1_generate(conn, source_lookup, tier_filter=args.tier)

    if args.phase is None or args.phase == 2:
        phase_2_validate(conn, source_lookup)

    if args.phase is None or args.phase == 3:
        phase_3_write(conn, dry_run=args.dry_run)

    # Final stats
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*60}")
    stats = get_stats(conn)
    print(f"  State distribution: {stats}")
    tier_stats = get_tier_stats(conn)
    print(f"  Tier distribution: {tier_stats}")
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the orchestrator with --help**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 scripts/kbli_enrich_pipeline.py --help`

Expected: Help text showing all flags.

- [ ] **Step 3: Smoke test with --limit 5 --dry-run**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 scripts/kbli_enrich_pipeline.py --limit 5 --dry-run`

Expected: Pipeline runs through all 4 phases on 5 codes without writing to disk.

- [ ] **Step 4: Commit**

```bash
git add scripts/kbli_enrich_pipeline.py
git commit -m "feat(kbli): add main orchestrator for enrichment pipeline"
```

---

## Task 9: Integration Test — 20 Codes End-to-End

- [ ] **Step 1: Run pipeline on 20 codes**

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 scripts/kbli_enrich_pipeline.py --limit 20
```

Expected: Pipeline completes all 4 phases. ~2-5 HIGH, ~8-12 MEDIUM, ~5-8 LOW codes.

- [ ] **Step 2: Verify output in kbli-gold-all.json**

```bash
python3 -c "
import json
with open('apps/mouth/data/kbli-gold-all.json') as f:
    d = json.load(f)
print(f'Total entries: {len(d)}')
# Check one new entry has all 6 fields
for code, entry in list(d.items())[-3:]:
    fields = [k for k in ['whatItMeans','whatYouNeed','whatChanged','baliContext','youllAlsoNeed','zantaraOpener'] if entry.get(k)]
    print(f'{code}: {len(fields)}/6 fields populated')
"
```

Expected: ~340+ total entries (319 existing + ~20 new). Each new entry has 6/6 fields.

- [ ] **Step 3: Run Next.js build**

```bash
cd apps/kbli-navigator && npx next build 2>&1 | tail -5
```

Expected: Build succeeds with 1,595 SSG pages.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/data/kbli-gold-all.json data/kbli_enrich.db
git commit -m "feat(kbli): first 20 codes enriched via pipeline"
```

---

## Task 10: Full Production Run

- [ ] **Step 1: Run full pipeline**

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 scripts/kbli_enrich_pipeline.py 2>&1 | tee data/kbli_enrich.log
```

Expected runtime: ~6-8 hours. Monitor with:

```bash
# In another terminal:
watch -n 30 "cd /Users/nuzantara/Desktop/nuzantara && python3 -c \"
from scripts.kbli_enrich_db import get_conn, get_stats, get_tier_stats
conn = get_conn()
print('States:', get_stats(conn))
print('Tiers:', get_tier_stats(conn))
\""
```

- [ ] **Step 2: Verify completion and retry failures**

```bash
python3 -c "
from scripts.kbli_enrich_db import get_conn, get_stats
conn = get_conn()
stats = get_stats(conn)
print(stats)
if stats.get('FAILED', 0) > 0:
    print('Retrying failed codes...')
" && python3 scripts/kbli_enrich_pipeline.py --phase 1 --resume && python3 scripts/kbli_enrich_pipeline.py --phase 2 --resume && python3 scripts/kbli_enrich_pipeline.py --phase 3
```

- [ ] **Step 3: Final build test and commit**

```bash
cd apps/kbli-navigator && npx next build 2>&1 | tail -5
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/data/kbli-gold-all.json
git commit -m "feat(kbli): full-spectrum enrichment — all 1,563 codes with tiered content"
```

---

## Appendix: Runtime Estimates

| Phase        | Codes | Model                             | Estimated Time |
| ------------ | ----- | --------------------------------- | -------------- |
| 0 — Triage   | 1,241 | Gemini CLI (6 parallel)           | ~3 min         |
| 1a — HIGH    | ~200  | NLM + DeepSeek-R1:32b             | ~2.5 hours     |
| 1b — MEDIUM  | ~600  | Qwen3.5:9b                        | ~2 hours       |
| 1c — LOW     | ~400  | Qwen3.5:9b (minimal)              | ~30 min        |
| 2 — Validate | 1,241 | Gemma3:12b (deterministic checks) | ~20 min        |
| 3 — Write    | 1,241 | None (JSON merge + build)         | ~5 min         |
| **TOTAL**    |       |                                   | **~5-6 hours** |

## Appendix: Recovery Commands

```bash
# Check pipeline status
python3 -c "from scripts.kbli_enrich_db import get_conn, get_stats; print(get_stats(get_conn()))"

# Resume from failure
python3 scripts/kbli_enrich_pipeline.py --resume

# Retry only failed codes
python3 scripts/kbli_enrich_pipeline.py --phase 1 --resume

# Run only HIGH tier
python3 scripts/kbli_enrich_pipeline.py --tier HIGH

# Reset database (nuclear option)
rm data/kbli_enrich.db && python3 scripts/kbli_enrich_pipeline.py
```

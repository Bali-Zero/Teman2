# Zan & The Specialists — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three agentic Python skills to OpenClaw (ZAN): KBLI Validator (PydanticAI), CRM Query Agent (Agno), and War Room Crew (CrewAI).

**Architecture:** Each skill lives in `~/.openclaw/workspace/skills/<name>/` with its own venv, SKILL.md, and entry-point script. All LLM calls go through Claude MAX Proxy at `localhost:3456/v1` ($0). ZAN launches each as a subprocess and reads JSON from stdout.

**Tech Stack:** PydanticAI 1.65.0, Agno 2.5.6, CrewAI 1.9.3, Python 3.11+, Claude MAX Proxy (OpenAI-compatible)

**Design Doc:** `docs/plans/2026-03-04-zan-specialists-design.md`

---

## Task 1: KBLI Validator Skill — Setup and Models

**Files:**

- Create: `~/.openclaw/workspace/skills/kbli-validator/SKILL.md`
- Create: `~/.openclaw/workspace/skills/kbli-validator/models.py`
- Create: `~/.openclaw/workspace/skills/kbli-validator/requirements.txt`

**Step 1: Create skill directory and venv**

```bash
mkdir -p ~/.openclaw/workspace/skills/kbli-validator
cd ~/.openclaw/workspace/skills/kbli-validator
python3 -m venv .venv
```

**Step 2: Create requirements.txt**

```
pydantic-ai>=1.65.0
httpx
```

**Step 3: Install dependencies**

```bash
cd ~/.openclaw/workspace/skills/kbli-validator
.venv/bin/pip install -r requirements.txt
```

Expected: Successfully installed pydantic-ai, httpx, and deps

**Step 4: Create models.py**

```python
"""Pydantic models for KBLI validation output."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class KBLIValidation(BaseModel):
    """Structured output from KBLI code validation."""

    kbli_code: str = Field(description="KBLI 2025 code, e.g. '47911'")
    kbli_title_id: str = Field(description="Official Indonesian title from BPS")
    kbli_title_en: str = Field(description="English title")
    confidence: float = Field(ge=0.0, le=1.0, description="Match confidence 0-1")
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        description="Business risk level based on kategori_risiko in per_skala"
    )
    pma_eligible: bool = Field(description="Whether PMA (foreign investment) is allowed")
    pma_max_ownership: Optional[int] = Field(
        default=None, description="Max foreign ownership percentage, e.g. 67"
    )
    pma_status: str = Field(description="PMA status: TERBUKA, TERTUTUP, TERBATAS, etc.")
    coretax_flags: list[str] = Field(
        default_factory=list,
        description="Flags: DNI_RESTRICTED, REQUIRES_SPECIAL_LICENSE, KEMITRAAN_REQUIRED, etc.",
    )
    requires_special_license: bool = Field(
        description="Whether special licenses beyond NIB are needed"
    )
    notes: str = Field(description="Brief explanation of the classification reasoning")
```

**Step 5: Create SKILL.md**

````yaml
---
name: kbli-validator
description: |
  Validate KBLI 2025 codes from natural language business descriptions.
  Returns type-safe JSON with risk level, PMA eligibility, and Coretax flags.
  Uses PydanticAI for guaranteed output schema compliance.
  Use when a client describes their business activity and needs KBLI classification.
compatibility: Requires Claude Desktop running (localhost:3456 proxy)
metadata:
  author: balizero
  version: "1.0"
---

# KBLI Validator

Validates business descriptions against the official KBLI 2025 dataset (1,563 codes).

## Usage

```bash
# From ZAN or terminal
~/.openclaw/workspace/skills/kbli-validator/.venv/bin/python \
  ~/.openclaw/workspace/skills/kbli-validator/validate.py \
  --input "ristorante italiano con delivery a Bali"
````

## Output

Returns JSON to stdout with fields: kbli_code, kbli_title_id, kbli_title_en,
confidence, risk_level, pma_eligible, pma_max_ownership, pma_status,
coretax_flags, requires_special_license, notes.

## Data Source

`source_documents/KBLI_2025_FINAL_CLEAN.json` — 1,563 codes with per_skala
licensing data and intel_2026 enrichment (504 codes).

````

**Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/kbli-validator/SKILL.md \
           ~/.openclaw/workspace/skills/kbli-validator/models.py \
           ~/.openclaw/workspace/skills/kbli-validator/requirements.txt
git commit -m "feat(skills): kbli-validator — models and skill definition"
````

Note: `.venv/` should NOT be committed. It's gitignored by default.

---

## Task 2: KBLI Validator — Entry Point and Test

**Files:**

- Create: `~/.openclaw/workspace/skills/kbli-validator/validate.py`

**Step 1: Write validate.py**

```python
#!/usr/bin/env python3
"""KBLI Validator — PydanticAI skill for OpenClaw.

Usage:
    python validate.py --input "ristorante italiano con delivery a Bali"
    python validate.py --input "software development company" --model claude-opus-4
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import KBLIValidation

# Path to KBLI dataset — relative to nuzantara project root
KBLI_DATA_PATH = Path.home() / "Desktop/nuzantara/source_documents/KBLI_2025_FINAL_CLEAN.json"

# Claude MAX Proxy
PROXY_BASE_URL = "http://localhost:3456/v1"
PROXY_API_KEY = "not-needed"
DEFAULT_MODEL = "claude-sonnet-4"


def load_kbli_context() -> str:
    """Load KBLI dataset as context string for the agent.

    Returns a condensed version: code, title, PMA status, risk levels.
    Full uraian is too large (~600KB); we send a summary table.
    """
    with open(KBLI_DATA_PATH) as f:
        data = json.load(f)

    codes = data[list(data.keys())[1]]  # second key is the codes list

    lines = []
    for entry in codes:
        code = entry.get("kode_kbli_2025", "")
        title = entry.get("judul", "")
        pma = entry.get("pma_status", "N/A")
        pma_max = entry.get("pma_max_asing", "N/A")
        risk_levels = set()
        for skala in entry.get("per_skala", []):
            risk_levels.add(skala.get("kategori_risiko", ""))
        risks = ", ".join(sorted(risk_levels)) if risk_levels else "N/A"
        lines.append(f"{code}|{title}|PMA:{pma}({pma_max}%)|Risk:{risks}")

    return "\n".join(lines)


def build_system_prompt(kbli_context: str) -> str:
    """Build the system prompt with KBLI reference data."""
    return f"""You are an expert KBLI 2025 classifier for Indonesian business licensing.

Your task: Given a business description in any language, identify the most appropriate
KBLI 2025 code and provide a structured assessment.

RULES:
- Match to the most specific 5-digit KBLI code possible
- Use the reference data below for codes, PMA status, and risk levels
- If no exact match, find the closest parent category and note lower confidence
- PMA status: TERBUKA (open), TERTUTUP (closed), TERBATAS (restricted with conditions)
- Risk levels from per_skala: Rendah, Menengah Rendah, Menengah Tinggi, Tinggi
- Map to output risk: Rendah→LOW, Menengah Rendah→MEDIUM, Menengah Tinggi→HIGH, Tinggi→CRITICAL
- For coretax_flags, check: DNI restrictions, special licenses, kemitraan requirements
- Always provide reasoning in notes field

KBLI 2025 REFERENCE DATA (code|title|PMA|risk):
{kbli_context}"""


def run_validation(business_description: str, model_name: str = DEFAULT_MODEL) -> str:
    """Run KBLI validation and return JSON string."""
    kbli_context = load_kbli_context()
    system_prompt = build_system_prompt(kbli_context)

    model = OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=PROXY_BASE_URL, api_key=PROXY_API_KEY),
    )

    agent = Agent(
        model,
        output_type=KBLIValidation,
        system_prompt=system_prompt,
    )

    result = agent.run_sync(f"Classify this business: {business_description}")
    return result.output.model_dump_json(indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="KBLI 2025 Validator (PydanticAI)")
    parser.add_argument("--input", required=True, help="Business description to classify")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name (default: claude-sonnet-4)")
    args = parser.parse_args()

    try:
        result = run_validation(args.input, args.model)
        print(result)
    except Exception as e:
        error = {"error": str(e), "type": type(e).__name__}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Test the script works (requires Claude Desktop running)**

```bash
cd ~/.openclaw/workspace/skills/kbli-validator
.venv/bin/python validate.py --input "Italian restaurant with food delivery in Bali"
```

Expected: JSON output with kbli_code, confidence, risk_level, pma fields

**Step 3: Test with an edge case**

```bash
.venv/bin/python validate.py --input "software development and cloud hosting"
```

Expected: JSON with appropriate IT-sector KBLI code

**Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/kbli-validator/validate.py
git commit -m "feat(skills): kbli-validator — entry point with PydanticAI agent"
```

---

## Task 3: CRM Query Agent Skill — Setup

**Files:**

- Create: `~/.openclaw/workspace/skills/crm-query/SKILL.md`
- Create: `~/.openclaw/workspace/skills/crm-query/requirements.txt`

**Step 1: Create skill directory and venv**

```bash
mkdir -p ~/.openclaw/workspace/skills/crm-query
cd ~/.openclaw/workspace/skills/crm-query
python3 -m venv .venv
```

**Step 2: Create requirements.txt**

```
agno>=2.5.0
psycopg2-binary
```

**Step 3: Install dependencies**

```bash
cd ~/.openclaw/workspace/skills/crm-query
.venv/bin/pip install -r requirements.txt
```

Expected: Successfully installed agno, psycopg2-binary, and deps

**Step 4: Create SKILL.md**

````yaml
---
name: crm-query
description: |
  Query the Bali Zero CRM database using natural language.
  Translates questions into SQL (read-only), executes against PostgreSQL,
  and returns formatted results. Uses Agno framework with PostgresTools.
  Use when asked about client data, practice status, invoices, interactions.
compatibility: Requires Claude Desktop (localhost:3456) and PostgreSQL (localhost:5432)
metadata:
  author: balizero
  version: "1.0"
---

# CRM Query Agent

Natural language interface to the Bali Zero CRM database.

## Usage

```bash
~/.openclaw/workspace/skills/crm-query/.venv/bin/python \
  ~/.openclaw/workspace/skills/crm-query/query.py \
  --question "Quanti clienti italiani hanno practice attive?"
````

## Database Schema (key tables)

- **clients**: id, full_name, email, phone, nationality, status, tags
- **practices**: id, client_id, practice_type_code, title, status, priority, quoted_price
- **interactions**: id, client_id, practice_id, type, channel, content, sentiment
- **invoices**: id, client_id, practice_id, amount, status, due_date
- **companies**: id, name, type, kbli_codes, status

## Security

All queries are READ-ONLY. The agent cannot INSERT, UPDATE, or DELETE.

````

**Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/crm-query/SKILL.md \
           ~/.openclaw/workspace/skills/crm-query/requirements.txt
git commit -m "feat(skills): crm-query — skill definition and deps"
````

---

## Task 4: CRM Query Agent — Entry Point and Test

**Files:**

- Create: `~/.openclaw/workspace/skills/crm-query/query.py`

**Step 1: Write query.py**

```python
#!/usr/bin/env python3
"""CRM Query Agent — Agno skill for OpenClaw.

Usage:
    python query.py --question "How many Italian clients have active practices?"
    python query.py --question "Mostrami le ultime 5 interazioni del cliente Rossi"
"""

import argparse
import json
import sys

from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from agno.tools.postgres import PostgresTools

# Claude MAX Proxy
PROXY_BASE_URL = "http://localhost:3456/v1"
PROXY_API_KEY = "not-needed"
DEFAULT_MODEL = "claude-sonnet-4"

# Local PostgreSQL
DB_URL = "postgresql://nuzantara@localhost:5432/nuzantara_dev"

SYSTEM_INSTRUCTIONS = [
    "You are the CRM Archivista of Bali Zero, a consultancy in Bali, Indonesia.",
    "You answer questions about clients, practices (visa/permit cases), interactions, and invoices.",
    "ALWAYS query the database. NEVER guess or make up data.",
    "Use SELECT only. You have read-only access.",
    "Key tables: clients, practices, interactions, invoices, companies.",
    "clients.nationality stores country names like 'Italian', 'Australian', 'Indonesian'.",
    "practices.status can be: 'active', 'completed', 'pending', 'cancelled'.",
    "practices.practice_type_code indicates service type (e.g., 'KITAS', 'PT_PMA', 'VISA_B211').",
    "Format results clearly. Use tables for multiple rows. Summarize counts.",
    "Respond in the same language as the question.",
]


def run_query(question: str, model_name: str = DEFAULT_MODEL) -> str:
    """Run CRM query and return the agent's response."""
    model = OpenAILike(
        id=model_name,
        api_key=PROXY_API_KEY,
        base_url=PROXY_BASE_URL,
    )

    agent = Agent(
        model=model,
        tools=[PostgresTools(db_url=DB_URL, read_only=True)],
        instructions=SYSTEM_INSTRUCTIONS,
        markdown=True,
    )

    response = agent.run(question)
    return response.content


def main() -> None:
    parser = argparse.ArgumentParser(description="CRM Query Agent (Agno)")
    parser.add_argument("--question", required=True, help="Natural language question about CRM data")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name (default: claude-sonnet-4)")
    args = parser.parse_args()

    try:
        result = run_query(args.question, args.model)
        print(result)
    except Exception as e:
        error = {"error": str(e), "type": type(e).__name__}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Test with a simple count query**

```bash
cd ~/.openclaw/workspace/skills/crm-query
.venv/bin/python query.py --question "How many clients are in the database?"
```

Expected: A number and formatted response

**Step 3: Test with a filtered query**

```bash
.venv/bin/python query.py --question "Show me clients with nationality 'Italian' and their active practices"
```

Expected: Table of Italian clients with practice details

**Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/crm-query/query.py
git commit -m "feat(skills): crm-query — Agno agent with PostgresTools"
```

---

## Task 5: War Room Crew Skill — Setup and Tools

**Files:**

- Create: `~/.openclaw/workspace/skills/war-room-crew/SKILL.md`
- Create: `~/.openclaw/workspace/skills/war-room-crew/requirements.txt`
- Create: `~/.openclaw/workspace/skills/war-room-crew/tools.py`

**Step 1: Create skill directory and venv**

```bash
mkdir -p ~/.openclaw/workspace/skills/war-room-crew
cd ~/.openclaw/workspace/skills/war-room-crew
python3 -m venv .venv
```

**Step 2: Create requirements.txt**

```
crewai>=1.9.0
crewai-tools>=0.40.0
```

**Step 3: Install dependencies**

```bash
cd ~/.openclaw/workspace/skills/war-room-crew
.venv/bin/pip install -r requirements.txt
```

Expected: Successfully installed crewai, crewai-tools, and deps

**Step 4: Create tools.py (wrappers for war_room scripts)**

```python
"""Tool wrappers for existing ~/war_room/ scripts.

Each tool calls the corresponding war_room agent as a subprocess,
capturing stdout/stderr and returning the result to CrewAI agents.
"""

import json
import subprocess
from pathlib import Path

from crewai.tools import tool

WAR_ROOM = Path.home() / "war_room"
WAR_VENV_PYTHON = str(WAR_ROOM / ".venv/bin/python3")
OUTPUT_DIR = WAR_ROOM / "output"


def _run_agent(script: str, args: list[str], timeout: int = 180) -> str:
    """Run a war_room agent script and return its output."""
    cmd = [WAR_VENV_PYTHON, str(WAR_ROOM / "agents" / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        return f"ERROR (exit {result.returncode}): {result.stderr[:500]}"
    return result.stdout or "OK (no stdout)"


@tool
def run_grok_scraper(topic: str) -> str:
    """Search X/Twitter for the last 72h of posts on a topic using Grok 4.

    Requires Chrome with remote debugging on port 9222.
    Returns JSON with scraped posts and sentiment.
    """
    output_path = str(OUTPUT_DIR / "raw/grok_dump.json")
    return _run_agent(
        "01_grok_scraper.py",
        ["--topic", topic, "--output", output_path],
        timeout=180,
    )


@tool
def check_intel_scraper_data() -> str:
    """Check if bali-intel-scraper has fresh data (< 8h old).

    If fresh data exists, returns the intel JSON content.
    If stale or missing, returns empty result.
    """
    intel_path = Path.home() / "Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json"
    if not intel_path.exists():
        return json.dumps({"fresh": False, "reason": "File not found"})

    import time

    age_seconds = time.time() - intel_path.stat().st_mtime
    if age_seconds > 28800:  # 8 hours
        return json.dumps({"fresh": False, "age_hours": round(age_seconds / 3600, 1)})

    with open(intel_path) as f:
        data = json.load(f)

    return json.dumps(
        {
            "fresh": True,
            "age_hours": round(age_seconds / 3600, 1),
            "article_count": len(data.get("articles", [])),
            "data": data,
        },
        ensure_ascii=False,
    )


@tool
def run_qwen_preprocessor(grok_path: str, manus_path: str) -> str:
    """Pre-process scraped data with Qwen3.5-27B (local, free).

    Deduplicates and classifies raw intelligence data.
    """
    output_path = str(OUTPUT_DIR / "raw/processed_dump.json")
    return _run_agent(
        "015_qwen_preprocessor.py",
        ["--grok", grok_path, "--manus", manus_path, "--output", output_path],
        timeout=120,
    )


@tool
def run_gemini_strategist(dump_path: str, topic: str) -> str:
    """Generate 3 asymmetric narrative concepts using Gemini 3.1 Pro Deep Think."""
    output_path = str(OUTPUT_DIR / "strategy/gemini_concepts.json")
    return _run_agent(
        "03_gemini_strategist.py",
        ["--dump", dump_path, "--topic", topic, "--output", output_path],
        timeout=120,
    )


@tool
def run_creative_director(concepts_path: str) -> str:
    """Pick best concept, validate claims, produce JSON slides + image prompts."""
    output_path = str(OUTPUT_DIR / "strategy/claude_slides.json")
    return _run_agent(
        "04_claude_director.py",
        ["--concepts", concepts_path, "--output", output_path],
        timeout=120,
    )


@tool
def run_image_generator(slides_path: str) -> str:
    """Generate images via Gemini Ultra browser automation.

    Requires Chrome with remote debugging on port 9222.
    """
    output_path = str(OUTPUT_DIR / "images/")
    return _run_agent(
        "05_gemini_images.py",
        ["--slides", slides_path, "--output", output_path],
        timeout=300,
    )


@tool
def run_keynote_builder(slides_path: str, images_path: str) -> str:
    """Build Keynote presentation (1080x1350) and export JPGs."""
    output_path = str(OUTPUT_DIR / "keynote/")
    master_path = str(OUTPUT_DIR / "master/")
    return _run_agent(
        "06_keynote_builder.py",
        ["--slides", slides_path, "--images", images_path, "--output", output_path, "--master", master_path],
        timeout=120,
    )
```

**Step 5: Create SKILL.md**

````yaml
---
name: war-room-crew
description: |
  AI-orchestrated marketing pipeline for Bali Zero.
  Uses CrewAI to intelligently coordinate the war_room multi-agent pipeline:
  scraping → strategy → creative direction → image gen → Keynote → delivery.
  Smarter than pipeline.sh: handles failures, retries, and dynamic decisions.
compatibility: Requires Claude Desktop, Chrome CDP (port 9222), war_room scripts
metadata:
  author: balizero
  version: "1.0"
---

# War Room Crew

CrewAI orchestrator for the Bali Zero content pipeline.
Uses existing ~/war_room/ scripts as tools — does not modify them.

## Usage

```bash
~/.openclaw/workspace/skills/war-room-crew/.venv/bin/python \
  ~/.openclaw/workspace/skills/war-room-crew/crew.py \
  --topic "Coretax 2026 updates"
````

## Agents

1. **Intel Gatherer** — checks intel_scraper data, runs Grok if needed
2. **Strategist** — generates 3 narrative concepts via Gemini
3. **Creative Director** — picks best, validates, produces slides JSON
4. **Producer** — generates images, builds Keynote, prepares delivery

## Advantages over pipeline.sh

- AI-driven failure handling (not bash if/else)
- Intelligent retry with modified prompts
- Typed handoff between agents
- Structured logging of every decision

````

**Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/war-room-crew/SKILL.md \
           ~/.openclaw/workspace/skills/war-room-crew/requirements.txt \
           ~/.openclaw/workspace/skills/war-room-crew/tools.py
git commit -m "feat(skills): war-room-crew — tools wrappers and skill definition"
````

---

## Task 6: War Room Crew — Agents, Tasks, and Entry Point

**Files:**

- Create: `~/.openclaw/workspace/skills/war-room-crew/agents.py`
- Create: `~/.openclaw/workspace/skills/war-room-crew/tasks.py`
- Create: `~/.openclaw/workspace/skills/war-room-crew/crew.py`

**Step 1: Write agents.py**

```python
"""CrewAI agent definitions for the War Room pipeline."""

from crewai import Agent, LLM

from tools import (
    check_intel_scraper_data,
    run_creative_director,
    run_gemini_strategist,
    run_grok_scraper,
    run_image_generator,
    run_keynote_builder,
    run_qwen_preprocessor,
)

PROXY_BASE_URL = "http://localhost:3456/v1"

llm = LLM(
    model="openai/claude-sonnet-4",
    base_url=PROXY_BASE_URL,
    api_key="not-needed",
)


intel_gatherer = Agent(
    role="Intelligence Gatherer",
    goal="Collect the freshest intelligence data about the given topic from multiple sources",
    backstory=(
        "You are the intelligence arm of Bali Zero's newsroom. "
        "You first check if the intel scraper has fresh data (< 8h). "
        "If yes, use that. If not, run the Grok scraper for X/Twitter data. "
        "Then pre-process all gathered data with the Qwen preprocessor. "
        "Your output is the path to the processed dump JSON file."
    ),
    tools=[check_intel_scraper_data, run_grok_scraper, run_qwen_preprocessor],
    llm=llm,
    verbose=True,
)

strategist = Agent(
    role="Narrative Strategist",
    goal="Generate 3 asymmetric narrative concepts from the intelligence data",
    backstory=(
        "You are Bali Zero's strategic thinker. "
        "Given processed intelligence data, you find the real story — "
        "the secondary effects, the contrarian angles, the insights "
        "that show asymmetric information. Never fear-monger. "
        "Be authoritative and logical. Your output is 3 distinct concepts."
    ),
    tools=[run_gemini_strategist],
    llm=llm,
    verbose=True,
)

creative_director = Agent(
    role="Creative Director",
    goal="Pick the sharpest concept and produce validated slide content",
    backstory=(
        "You are Bali Zero's editorial voice. "
        "You criticize the strategist's angles, pick the best one, "
        "validate all legal/technical claims, and produce a JSON "
        "with slide copy and image generation prompts. "
        "Zero fluff. Bali Zero voice: sharp, informed, helpful."
    ),
    tools=[run_creative_director],
    llm=llm,
    verbose=True,
)

producer = Agent(
    role="Content Producer",
    goal="Generate images, build Keynote, and prepare final deliverables",
    backstory=(
        "You are the production arm. You take the creative director's "
        "slides JSON and image prompts, generate images via Gemini, "
        "assemble everything into a Keynote at 1080x1350, and export JPGs. "
        "If image generation fails, continue with placeholder text slides."
    ),
    tools=[run_image_generator, run_keynote_builder],
    llm=llm,
    verbose=True,
)
```

**Step 2: Write tasks.py**

```python
"""CrewAI task definitions for the War Room pipeline."""

from crewai import Task

from agents import creative_director, intel_gatherer, producer, strategist


def create_tasks(topic: str) -> list[Task]:
    """Create the task chain for a given topic."""

    gather_intel = Task(
        description=(
            f"Gather intelligence about '{topic}'. "
            "1. Check intel_scraper for fresh data (< 8h). "
            "2. If fresh, use it directly. If not, run Grok scraper. "
            "3. Pre-process the combined data with Qwen preprocessor. "
            "Output: path to the processed dump JSON file."
        ),
        expected_output="Path to processed_dump.json with classified and deduplicated intel data",
        agent=intel_gatherer,
    )

    generate_concepts = Task(
        description=(
            f"Generate 3 asymmetric narrative concepts about '{topic}'. "
            "Use the processed dump from the previous step. "
            "Each concept must have: angle, hook, target audience, tone. "
            "Find the real story, not the obvious headline."
        ),
        expected_output="Path to gemini_concepts.json with 3 narrative concepts",
        agent=strategist,
    )

    direct_creative = Task(
        description=(
            "Review the 3 concepts. Pick the sharpest one. "
            "Validate all legal/technical claims. "
            "Produce JSON slides (6-12 slides) with copy and image prompts. "
            "Bali Zero voice: sharp, informed, zero fluff."
        ),
        expected_output="Path to claude_slides.json with validated slide content and image prompts",
        agent=creative_director,
    )

    produce_content = Task(
        description=(
            "Generate images from the slide prompts via Gemini. "
            "Build Keynote at 1080x1350 with Bali Zero branding. "
            "Export JPGs to master folder. "
            "If image generation fails, continue with text-only slides."
        ),
        expected_output="Confirmation that Keynote and JPGs are ready in output/master/",
        agent=producer,
    )

    return [gather_intel, generate_concepts, direct_creative, produce_content]
```

**Step 3: Write crew.py (entry point)**

```python
#!/usr/bin/env python3
"""War Room Crew — CrewAI orchestrator for Bali Zero content pipeline.

Usage:
    python crew.py --topic "Coretax 2026 updates"
    python crew.py --topic "KBLI error blocca visto" --verbose
"""

import argparse
import json
import sys

from crewai import Crew, Process

from tasks import create_tasks


def run_crew(topic: str, verbose: bool = False) -> str:
    """Run the War Room Crew pipeline."""
    tasks = create_tasks(topic)

    crew = Crew(
        agents=[t.agent for t in tasks],
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )

    result = crew.kickoff()
    return str(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="War Room Crew (CrewAI)")
    parser.add_argument("--topic", required=True, help="Topic for the content pipeline")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose CrewAI output")
    args = parser.parse_args()

    try:
        result = run_crew(args.topic, args.verbose)
        output = {"status": "completed", "topic": args.topic, "result": result}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except Exception as e:
        error = {"error": str(e), "type": type(e).__name__, "topic": args.topic}
        print(json.dumps(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 4: Test import chain (no execution)**

```bash
cd ~/.openclaw/workspace/skills/war-room-crew
.venv/bin/python -c "from crew import run_crew; print('Import OK')"
```

Expected: "Import OK"

**Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add -f ~/.openclaw/workspace/skills/war-room-crew/agents.py \
           ~/.openclaw/workspace/skills/war-room-crew/tasks.py \
           ~/.openclaw/workspace/skills/war-room-crew/crew.py
git commit -m "feat(skills): war-room-crew — CrewAI agents, tasks, and entry point"
```

---

## Task 7: Integration Test — All Three Skills

**Step 1: Verify all three skills are visible to OpenClaw**

```bash
ls -la ~/.openclaw/workspace/skills/kbli-validator/SKILL.md
ls -la ~/.openclaw/workspace/skills/crm-query/SKILL.md
ls -la ~/.openclaw/workspace/skills/war-room-crew/SKILL.md
```

Expected: All three files exist

**Step 2: Test KBLI Validator end-to-end**

```bash
~/.openclaw/workspace/skills/kbli-validator/.venv/bin/python \
  ~/.openclaw/workspace/skills/kbli-validator/validate.py \
  --input "villa rental and property management in Seminyak"
```

Expected: JSON with KBLI code in real estate sector, PMA status, risk level

**Step 3: Test CRM Query end-to-end**

```bash
~/.openclaw/workspace/skills/crm-query/.venv/bin/python \
  ~/.openclaw/workspace/skills/crm-query/query.py \
  --question "How many clients are there grouped by nationality? Show top 5."
```

Expected: Formatted table with nationality counts from PostgreSQL

**Step 4: Test War Room Crew import (dry run — full pipeline needs Chrome CDP)**

```bash
~/.openclaw/workspace/skills/war-room-crew/.venv/bin/python -c "
from agents import intel_gatherer, strategist, creative_director, producer
from tasks import create_tasks
tasks = create_tasks('test topic')
print(f'Agents: {len(set(t.agent for t in tasks))}')
print(f'Tasks: {len(tasks)}')
print('All imports OK')
"
```

Expected: "Agents: 4, Tasks: 4, All imports OK"

**Step 5: Final commit with all skills**

```bash
cd ~/Desktop/nuzantara
git add -A docs/plans/2026-03-04-zan-specialists-plan.md
git commit -m "docs(plan): Zan & The Specialists implementation plan"
```

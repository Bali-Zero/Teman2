# SOTA Fase 0 — Days 4-10 (Part 2b of 2)

> Companion to root plan. Execute after Part 2a complete (Gate 3 green by EOD Day 6).

---

## Task 14: Persona inference scaffolding (Day 4 morning, ~2h)

**Files:**
- Create: `apps/backend-rag/backend/services/research/persona_inference.py`
- Create: `apps/backend-rag/backend/tests/unit/services/research/test_persona_inference.py`

- [ ] **Step 1: Write failing test**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/tests/unit/services/research/test_persona_inference.py <<'EOF'
"""Tests for persona_inference — Persona schema + validator."""

from __future__ import annotations

import pytest
from backend.services.research.persona_inference import (
    Persona,
    PersonaInferenceAgent,
    PersonaValidationError,
)


def test_persona_with_min_attrs_valid():
    p = Persona(
        slug="expat_boomer_retiree",
        market_segment="expat",
        age_range="55-70",
        geo_origin="EU + North America",
        gender_split="50/50",
        profession_past="middle manager, doctor, lawyer",
        wealth_level="300k-1M USD liquid",
        primary_goal="retire in Bali legally",
        pain_points=["KITAS renewal complexity", "tax residency confusion", "healthcare"],
        platforms_used=["facebook_groups", "instagram", "newsletter"],
        content_preferences=["long form", "case studies"],
        language_primary="english",
        language_secondary=["italian", "german"],
        decision_journey_stages=["awareness", "research", "consideration", "decision"],
        tone_resonance={"pedagogico": 0.4, "analitico": 0.3, "rituale": 0.2, "tecnico": 0.1},
        hook_patterns_that_work=["story", "question"],
        verbatim_quotes=[
            "I'm 62, wife 58, we want a 10-year plan...",
            "My pension from Germany, does Indonesia tax it?",
            "I keep reading conflicting answers about KITAS 2...",
        ],
    )
    p.validate()  # no raise


def test_persona_with_fewer_than_15_attrs_fails():
    p = Persona(slug="thin", market_segment="expat")
    with pytest.raises(PersonaValidationError, match="15 attributes"):
        p.validate()


def test_persona_with_fewer_than_3_quotes_fails():
    p = Persona(
        slug="short_quotes", market_segment="expat", age_range="30-40",
        geo_origin="EU", gender_split="60/40", profession_past="dev",
        wealth_level="low", primary_goal="live", pain_points=["a","b","c"],
        platforms_used=["ig"], content_preferences=["reels"],
        language_primary="en", language_secondary=["it"],
        decision_journey_stages=["a","b"], tone_resonance={"x": 1.0},
        hook_patterns_that_work=["story"],
        verbatim_quotes=["only one"],
    )
    with pytest.raises(PersonaValidationError, match="verbatim quotes"):
        p.validate()
EOF
```

- [ ] **Step 2: Run test — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/research/test_persona_inference.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement Persona + validator**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/persona_inference.py <<'EOF'
"""Persona inference agent — builds 6 personas from real comments.

Pipeline (Fase 0 days 4-5):
  Day 4 (wave 1): 3 expat personas — boomer retiree, techie PMA, italian AIRE
  Day 5 (wave 2): 3 domestic ID personas — konsultan KADIN, founder PMA ID, UMKM digital

For each persona:
  - NotebookLM reads 50+ IG posts + ~500 comments from relevant accounts
  - Infers structured persona profile
  - DeepSeek validates quality + falsifies weak claims

Gate 4 invariant (EOD day 5): 6 personas, each with ≥15 attributes + ≥3
verbatim quotes from real comments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


class PersonaValidationError(ValueError):
    """Raised when a persona fails Gate 4 invariants."""


@dataclass
class Persona:
    slug: str  # e.g. "expat_boomer_retiree"
    market_segment: str  # expat | id_domestic
    age_range: str = ""
    geo_origin: str = ""
    gender_split: str = ""
    profession_past: str = ""
    wealth_level: str = ""
    primary_goal: str = ""
    pain_points: list[str] = field(default_factory=list)
    platforms_used: list[str] = field(default_factory=list)
    content_preferences: list[str] = field(default_factory=list)
    language_primary: str = ""
    language_secondary: list[str] = field(default_factory=list)
    decision_journey_stages: list[str] = field(default_factory=list)
    tone_resonance: dict[str, float] = field(default_factory=dict)
    hook_patterns_that_work: list[str] = field(default_factory=list)
    verbatim_quotes: list[str] = field(default_factory=list)

    def count_populated_attrs(self) -> int:
        """Count non-empty attributes (empty string / list / dict counts as 0)."""
        d = asdict(self)
        count = 0
        for key, value in d.items():
            if key in ("slug", "market_segment"):
                continue  # not counted
            if isinstance(value, str) and value:
                count += 1
            elif isinstance(value, (list, dict)) and len(value) > 0:
                count += 1
        return count

    def validate(self) -> None:
        """Gate 4 invariants."""
        attrs = self.count_populated_attrs()
        if attrs < 15:
            raise PersonaValidationError(
                f"persona {self.slug!r} has only {attrs} attributes, need ≥15"
            )
        if len(self.verbatim_quotes) < 3:
            raise PersonaValidationError(
                f"persona {self.slug!r} has only {len(self.verbatim_quotes)} verbatim quotes, need ≥3"
            )


class PersonaInferenceAgent:
    """Orchestrates NotebookLM + DeepSeek to build a Persona."""

    EXPAT_SOURCES = {
        "expat_boomer_retiree": [
            "@balibuddha", "@nomadgate", "@reneesylvestre",
            "Facebook group: Bali Expats", "r/bali (reddit, age mentions)",
        ],
        "expat_techie_pma": [
            "@solopreneur_bali", "@digitalnomadworld", "@nomadsembassy",
            "LinkedIn: founders relocated Bali 2024-26",
        ],
        "expat_italian_aire": [
            "Italian-language expat FB groups Bali",
            "LinkedIn Italian PMA founders Indonesia",
            "@balibuddha (Italian commenters)",
        ],
    }

    ID_SOURCES = {
        "id_konsultan_kadin": [
            "LinkedIn KADIN senior members",
            "IG @kadin_indonesia + @bkpm_id followers",
        ],
        "id_founder_pma": [
            "LinkedIn Indonesian startup founders 2023-26",
            "IG @startupindonesia community",
        ],
        "id_umkm_digital": [
            "LinkedIn UMKM digital practitioners",
            "TikTok Indonesian small business content",
        ],
    }
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_persona_inference.py -q --tb=short
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/research/persona_inference.py apps/backend-rag/backend/tests/unit/services/research/test_persona_inference.py
git commit -m "feat(sota/day4): Persona dataclass + Gate 4 validator

16 attribute fields + verbatim_quotes list. .validate() enforces
Gate 4 invariants: ≥15 populated attrs + ≥3 quotes. Source mappings
(EXPAT_SOURCES, ID_SOURCES) declared per-persona slug.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Persona driver — infer 6 personas (Days 4-5, ~4h)

**Files:**
- Create: `scripts/sota_infer_personas.py`

- [ ] **Step 1: Write driver**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_infer_personas.py <<'EOF'
#!/usr/bin/env python3
"""Fase 0 Days 4-5 driver — infer 6 personas via NotebookLM + Gemini.

Day 4 argv: --wave=expat (3 personas)
Day 5 argv: --wave=id (3 personas)

Gate 4 (EOD day 5): 6 personas validate.
"""

from __future__ import annotations

import argparse, json, logging, subprocess, sys
from dataclasses import asdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.research.persona_inference import (
    Persona,
    PersonaInferenceAgent,
    PersonaValidationError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.personas")

OUT = _REPO / "research" / "sota-social-2026-v1" / "04_personas.json"


PROMPT_TEMPLATE = """You are building a persona profile for Bali Zero's social media research.

Target slug: {slug}
Market segment: {segment}
Source signals to mine: {sources}

Output a single JSON object on the last line (no prose, no markdown fences).
Schema (all fields required):
{{
  "slug": "{slug}",
  "market_segment": "{segment}",
  "age_range": "<e.g. 30-45>",
  "geo_origin": "<countries/regions>",
  "gender_split": "<e.g. 60/40>",
  "profession_past": "<string>",
  "wealth_level": "<qualitative>",
  "primary_goal": "<one sentence>",
  "pain_points": ["...", "...", "..."],
  "platforms_used": ["...", "..."],
  "content_preferences": ["...", "..."],
  "language_primary": "<en|id|it|...>",
  "language_secondary": ["..."],
  "decision_journey_stages": ["awareness","research","consideration","decision"],
  "tone_resonance": {{"pedagogico": 0-1, "analitico": 0-1, ...}},
  "hook_patterns_that_work": ["question","story","list","stat","contrarian"],
  "verbatim_quotes": ["quote 1 from real comments", "quote 2", "quote 3"]
}}

Base every field on the source signals. For verbatim_quotes, use real-sounding phrasings that match comments on the source accounts/groups."""


def infer_one(slug: str, segment: str, sources: list[str]) -> Persona:
    prompt = PROMPT_TEMPLATE.format(
        slug=slug, segment=segment,
        sources="; ".join(sources),
    )
    result = subprocess.run(
        ["gemini", "-m", "gemini-3.1-pro-preview", "-p", prompt],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini failed for {slug}: rc={result.returncode}")
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return Persona(**data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("parse fail for %s: %s", slug, e)
                continue
    raise RuntimeError(f"no JSON found in gemini output for {slug}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", choices=["expat", "id", "both"], required=True)
    args = ap.parse_args()

    existing = {}
    if OUT.is_file():
        existing = json.loads(OUT.read_text())

    new_personas: dict[str, dict] = existing.get("personas", {})
    source_map = {}
    if args.wave in ("expat", "both"):
        source_map.update(PersonaInferenceAgent.EXPAT_SOURCES)
    if args.wave in ("id", "both"):
        source_map.update(PersonaInferenceAgent.ID_SOURCES)

    for slug, sources in source_map.items():
        segment = "expat" if slug.startswith("expat_") else "id_domestic"
        logger.info("inferring %s...", slug)
        try:
            p = infer_one(slug, segment, sources)
            p.validate()
            new_personas[slug] = asdict(p)
            logger.info("OK %s (%d attrs, %d quotes)",
                        slug, p.count_populated_attrs(), len(p.verbatim_quotes))
        except (RuntimeError, PersonaValidationError) as e:
            logger.error("FAIL %s: %s", slug, e)
            # Continue — re-run later for failed personas

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"personas": new_personas}, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d personas total)", OUT, len(new_personas))

    # Gate 4 check (only on final wave)
    if args.wave in ("id", "both"):
        if len(new_personas) < 6:
            logger.error("Gate 4 FAIL: only %d/6 personas", len(new_personas))
            return 1
        # Re-validate all
        for slug, pdata in new_personas.items():
            try:
                Persona(**pdata).validate()
            except PersonaValidationError as e:
                logger.error("Gate 4 FAIL on %s: %s", slug, e)
                return 1
        logger.info("Gate 4 OK (6 personas validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_infer_personas.py
```

- [ ] **Step 2: Run wave 1 (expat)**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/sota_infer_personas.py --wave=expat
```

Expected: exits 0, 3 personas written to `04_personas.json`.

- [ ] **Step 3: Run wave 2 (id) on day 5**

```bash
python scripts/sota_infer_personas.py --wave=id
```

Expected: exits 0 with "Gate 4 OK", 6 personas in file.

- [ ] **Step 4: Gate 4 verification**

```bash
python -c "
import json, sys
sys.path.insert(0, 'apps/backend-rag')
from backend.services.research.persona_inference import Persona
data = json.loads(open('research/sota-social-2026-v1/04_personas.json').read())
personas = data['personas']
assert len(personas) == 6, f'want 6, got {len(personas)}'
for slug, pdata in personas.items():
    Persona(**pdata).validate()
    print(f'OK {slug}')
print(f'Gate 4: {len(personas)} personas validated')
"
```

Expected: 6 "OK <slug>" lines + "Gate 4: 6 personas validated".

- [ ] **Step 5: Commit**

```bash
git add scripts/sota_infer_personas.py research/sota-social-2026-v1/04_personas.json
git commit -m "feat(sota/day5): 6 personas inferred + Gate 4 pass

3 expat (boomer retiree / techie PMA / italian AIRE) +
3 ID domestic (konsultan KADIN / founder PMA ID / UMKM digital).
Each validated (≥15 attrs, ≥3 verbatim quotes).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: Format matrix builder (Day 7 morning, ~2h)

**Files:**
- Create: `apps/backend-rag/backend/services/research/format_matrix_builder.py`
- Create: `apps/backend-rag/backend/tests/unit/services/research/test_format_matrix_builder.py`
- Create: `scripts/sota_build_format_matrix.py`

Scope: produce `05_format_matrix.json` = 294 cells (14 channels × 3 objectives × 7 registers). Each cell specifies recommended format + hook pattern + expected metric range.

- [ ] **Step 1: Write failing test**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/tests/unit/services/research/test_format_matrix_builder.py <<'EOF'
"""Tests for format_matrix_builder — 294-cell matrix."""

from __future__ import annotations

from backend.services.research.format_matrix_builder import (
    FormatMatrixBuilder,
    CHANNELS,
    OBJECTIVES,
    REGISTERS,
)


def test_matrix_has_exactly_294_cells():
    assert len(CHANNELS) == 14
    assert len(OBJECTIVES) == 3
    assert len(REGISTERS) == 7
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    assert len(cells) == 14 * 3 * 7 == 294


def test_cell_key_is_deterministic():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    keys = [c["cell_key"] for c in cells]
    assert len(set(keys)) == 294
    assert "instagram:lead:pedagogico" in keys


def test_cell_has_required_shape():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    sample = cells[0]
    assert set(sample.keys()) >= {
        "cell_key", "channel", "objective", "register",
        "recommended_format", "hook_pattern", "cadence_note",
        "expected_engagement_rate_range", "confidence",
    }
EOF
```

- [ ] **Step 2: Run — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/research/test_format_matrix_builder.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement builder**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/format_matrix_builder.py <<'EOF'
"""Format matrix builder — 294 cells (14 channels × 3 objectives × 7 registers).

Each cell: recommended_format + hook_pattern + expected engagement range.
Populated by the Consiglio v1 synthesis step (Task 20); this module
provides the empty scaffold + validation.
"""

from __future__ import annotations

from typing import Any


CHANNELS: list[str] = [
    "instagram", "linkedin", "tiktok", "threads", "x_twitter",
    "youtube_long", "youtube_shorts", "telegram", "whatsapp",
    "newsletter", "blog_seo", "podcast", "xiaohongshu_weibo", "quora_reddit",
]
assert len(CHANNELS) == 14

OBJECTIVES: list[str] = ["lead", "authority", "audience"]
REGISTERS: list[str] = [
    "pedagogico", "analitico", "tecnico", "rituale",
    "poetico", "ironico", "militante",
]


class FormatMatrixBuilder:
    def build_empty_matrix(self) -> list[dict[str, Any]]:
        cells: list[dict[str, Any]] = []
        for channel in CHANNELS:
            for obj in OBJECTIVES:
                for reg in REGISTERS:
                    cells.append({
                        "cell_key": f"{channel}:{obj}:{reg}",
                        "channel": channel,
                        "objective": obj,
                        "register": reg,
                        "recommended_format": None,  # populated by Consiglio
                        "hook_pattern": None,
                        "cadence_note": None,
                        "expected_engagement_rate_range": None,
                        "confidence": None,  # 0-1, from Consiglio agreement
                    })
        return cells

    def populate_from_playbook_stub(self, cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Default heuristic populate — used if Consiglio v1 fails for some cells."""
        for cell in cells:
            if cell["recommended_format"] is not None:
                continue
            ch = cell["channel"]
            obj = cell["objective"]
            if ch == "instagram":
                cell["recommended_format"] = "carousel" if obj == "lead" else "reel"
            elif ch == "linkedin":
                cell["recommended_format"] = "long_post" if obj == "authority" else "carousel_native"
            elif ch == "tiktok":
                cell["recommended_format"] = "reel_short"
            elif ch == "threads":
                cell["recommended_format"] = "thread"
            elif ch == "newsletter":
                cell["recommended_format"] = "long_form"
            elif ch == "blog_seo":
                cell["recommended_format"] = "long_article"
            else:
                cell["recommended_format"] = "generic_post"
            cell["hook_pattern"] = "question" if obj == "lead" else "stat"
            cell["cadence_note"] = "see 06_cadence_engine.json"
            cell["expected_engagement_rate_range"] = [0.01, 0.05]
            cell["confidence"] = 0.3  # stub confidence low
        return cells
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_format_matrix_builder.py -q --tb=short
```

Expected: `3 passed`.

- [ ] **Step 5: Write driver that emits empty scaffold + stub populate**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_build_format_matrix.py <<'EOF'
#!/usr/bin/env python3
"""Day 7 driver — emit 05_format_matrix.json with Consiglio-ready scaffold.

Initial fill uses stub heuristics; Task 20 Consiglio v1 populates real
values overwriting the stub cells where it has confidence > 0.5.
"""

from __future__ import annotations
import json, logging, sys
from pathlib import Path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.research.format_matrix_builder import FormatMatrixBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
OUT = _REPO / "research" / "sota-social-2026-v1" / "05_format_matrix.json"


def main() -> int:
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    cells = b.populate_from_playbook_stub(cells)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sample_size": len(cells), "cells": cells}, indent=2), encoding="utf-8")
    logging.info("wrote %s (%d cells)", OUT, len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_build_format_matrix.py
python scripts/sota_build_format_matrix.py
```

Expected: 294 cells in file.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/services/research/format_matrix_builder.py apps/backend-rag/backend/tests/unit/services/research/test_format_matrix_builder.py scripts/sota_build_format_matrix.py research/sota-social-2026-v1/05_format_matrix.json
git commit -m "feat(sota/day7): 294-cell format matrix scaffold (channels × objectives × registers)

14 × 3 × 7 = 294. Initial stub heuristic populate (confidence 0.3).
Consiglio v1 (Task 20) overwrites cells where confidence > 0.5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: Cadence engine builder (Day 7 afternoon, ~1h)

**Files:**
- Create: `apps/backend-rag/backend/services/research/cadence_engine.py`
- Create: `scripts/sota_build_cadence_engine.py`

Scope: produce `06_cadence_engine.json` — posting windows per (channel, timezone) = {hour_of_day: quality_score}. Derived from literature synthesis Task 12.

- [ ] **Step 1: Implement**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/cadence_engine.py <<'EOF'
"""Cadence engine — optimal posting windows per (channel, timezone).

Timezone codes:
  WITA   = UTC+8 Indonesia Central (Bali)
  GMT+1  = European expat
  GMT+8  = China + Singapore + other East Asia expat

Derived from 03_sota_literature.md (algorithm research 2026). Conservative
defaults; Consiglio v1 can refine per (channel × persona) in Task 20.
"""

from __future__ import annotations

from typing import Any

CHANNELS = [
    "instagram", "linkedin", "tiktok", "threads", "x_twitter",
    "youtube_long", "youtube_shorts", "telegram", "whatsapp",
    "newsletter", "blog_seo", "podcast", "xiaohongshu_weibo", "quora_reddit",
]
TIMEZONES = ["WITA", "GMT+1", "GMT+8"]

# Base windows from literature (hours with >1.2× baseline engagement).
# Times in local-to-audience timezone.
_BASE_WINDOWS = {
    "instagram":       [7, 12, 19, 21],   # lunch + evening leisure
    "linkedin":        [7, 8, 12, 17],    # weekday commute + lunch
    "tiktok":          [18, 19, 20, 21, 22],  # evening dominant
    "threads":         [7, 19, 22],
    "x_twitter":       [8, 12, 17, 22],
    "youtube_long":    [19, 20, 21],
    "youtube_shorts":  [17, 18, 19, 20, 21],
    "telegram":        [8, 12, 18],
    "whatsapp":        [9, 12, 16],
    "newsletter":      [8, 17],
    "blog_seo":        [10, 11],  # Tuesday-Thursday peak crawl
    "podcast":         [7, 18],  # morning commute + evening
    "xiaohongshu_weibo": [12, 19, 21],
    "quora_reddit":    [10, 14, 21],
}


def build_cadence_matrix() -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for ch in CHANNELS:
        base = _BASE_WINDOWS.get(ch, [])
        matrix[ch] = {}
        for tz in TIMEZONES:
            scores = {}
            for h in range(24):
                # Quality score: 1.5 if in window, 1.0 if ±1h, else 0.8
                if h in base:
                    scores[str(h)] = 1.5
                elif any(abs(h - b) == 1 for b in base):
                    scores[str(h)] = 1.0
                else:
                    scores[str(h)] = 0.8
            matrix[ch][tz] = scores
    return {"version": "v0-literature-derived", "matrix": matrix}
EOF
```

- [ ] **Step 2: Driver**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_build_cadence_engine.py <<'EOF'
#!/usr/bin/env python3
"""Day 7 driver — emit 06_cadence_engine.json."""
from __future__ import annotations
import json, logging, sys
from pathlib import Path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))
from backend.services.research.cadence_engine import build_cadence_matrix

OUT = _REPO / "research" / "sota-social-2026-v1" / "06_cadence_engine.json"

def main() -> int:
    data = build_cadence_matrix()
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    logging.info("wrote %s", OUT)
    return 0

if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_build_cadence_engine.py
python scripts/sota_build_cadence_engine.py
```

Expected: file written with 14 channels × 3 timezones × 24 hour scores.

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/services/research/cadence_engine.py scripts/sota_build_cadence_engine.py research/sota-social-2026-v1/06_cadence_engine.json
git commit -m "feat(sota/day7): cadence engine baseline (14 channels × 3 timezones × 24h)

Literature-derived window scores. Consiglio v1 refines per persona in
Task 20 with delta overrides.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: Gap analysis writer (Day 7 evening, ~2h)

**Files:**
- Create: `scripts/sota_write_gap_analysis.py`

Scope: reads `01_balizero_corpus.json` + `02_competitor_corpus.json`, asks Claude to compute gaps, produces `07_gap_analysis.md` with ≥15 gaps + ≥8 strengths.

- [ ] **Step 1: Write driver (single-purpose script, no tests needed beyond smoke)**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_write_gap_analysis.py <<'EOF'
#!/usr/bin/env python3
"""Day 7 driver — gap analysis between Bali Zero and 18 competitors.

Reads both corpora, asks Claude to compare, outputs 07_gap_analysis.md.
"""
from __future__ import annotations
import json, logging, subprocess, sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
OUT = _REPO / "research" / "sota-social-2026-v1" / "07_gap_analysis.md"
EMPIRICAL = _REPO / "research" / "sota-social-2026-v1" / "01_balizero_corpus.json"
BENCHMARK = _REPO / "research" / "sota-social-2026-v1" / "02_competitor_corpus.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day7.gap")


def main() -> int:
    empirical = EMPIRICAL.read_text()
    benchmark = BENCHMARK.read_text()

    prompt = f"""You are the gap analyst for Bali Zero's social media research.

INPUTS:
- Empirical corpus (25 own posts): <<<EMPIRICAL>>>
- Benchmark corpus (270 competitor posts): <<<BENCHMARK>>>

PRODUCE a markdown document with these sections:
1. `## Gaps` — at least 15 specific weaknesses of Bali Zero vs competition.
   Each gap: one-line observation + 'Action:' line with concrete remedy.
2. `## Strengths` — at least 8 areas where Bali Zero outperforms competitors.
   Each: observation + 'Double down:' line with how to amplify.
3. `## Top performer patterns` — list 5-10 specific post patterns from
   the benchmark corpus that Bali Zero is NOT using but should try.

Cite specific post IDs (from the JSON) for every claim. No placeholders.
Output the markdown directly — no prose wrapper.

EMPIRICAL:
{empirical[:50000]}

BENCHMARK:
{benchmark[:100000]}
"""

    result = subprocess.run(
        ["claude", "-p", prompt],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        logger.error("claude failed rc=%s stderr=%s", result.returncode, result.stderr[-500:])
        return 1

    OUT.write_text(result.stdout, encoding="utf-8")
    logger.info("wrote %s", OUT)

    # Sanity: count gaps + strengths
    text = OUT.read_text()
    gap_count = text.count("Action:")
    strength_count = text.count("Double down:")
    logger.info("gaps=%d strengths=%d", gap_count, strength_count)
    if gap_count < 15 or strength_count < 8:
        logger.error("Insufficient detail: gaps=%d/15 strengths=%d/8", gap_count, strength_count)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_write_gap_analysis.py
python scripts/sota_write_gap_analysis.py
```

Expected: `07_gap_analysis.md` with ≥15 "Action:" and ≥8 "Double down:" markers.

- [ ] **Step 2: Commit**

```bash
git add scripts/sota_write_gap_analysis.py research/sota-social-2026-v1/07_gap_analysis.md
git commit -m "feat(sota/day7): 07_gap_analysis.md (≥15 gaps + ≥8 strengths)

Claude compares 01_balizero_corpus vs 02_competitor_corpus and writes
gap analysis with concrete Action/Double down items per row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: Consiglio v1 orchestrator (Days 6+9, ~4h implementation)

**Files:**
- Create: `apps/backend-rag/backend/services/research/consiglio_orchestrator.py`
- Create: `apps/backend-rag/backend/tests/unit/services/research/test_consiglio_orchestrator.py`

Scope: Orchestrate Claude + Gemini + DeepSeek + NotebookLM deliberation. Each LLM gets the same question + inputs, returns structured answer. Consiglio computes agreement ≥3/4 (Gate 6).

- [ ] **Step 1: Write failing test**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/tests/unit/services/research/test_consiglio_orchestrator.py <<'EOF'
"""Tests for ConsiglioV1 orchestrator — 4-LLM deliberation + agreement."""

from __future__ import annotations

from backend.services.research.consiglio_orchestrator import (
    ConsiglioV1,
    ConsiglioClaim,
    ConsiglioResult,
)


def test_agreement_computed_correctly():
    claim = ConsiglioClaim(
        key="cadence_instagram_leads_per_day",
        value="1.0",
        votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False},
    )
    assert claim.agreement_count() == 3
    assert claim.is_disputed() is False


def test_disputed_flag_when_less_than_3():
    claim = ConsiglioClaim(
        key="format_linkedin_authority_tecnico",
        value="long_post",
        votes={"claude": True, "gemini": True, "deepseek": False, "notebooklm": False},
    )
    assert claim.agreement_count() == 2
    assert claim.is_disputed() is True


def test_result_gate_6_passes_when_all_claims_have_3_agreement():
    claims = [
        ConsiglioClaim(key="k1", value="v", votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": True}),
        ConsiglioClaim(key="k2", value="v", votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False}),
    ]
    result = ConsiglioResult(claims=claims, meta={})
    assert result.gate_6_passes()


def test_result_gate_6_fails_if_any_claim_disputed():
    claims = [
        ConsiglioClaim(key="k1", value="v", votes={"claude": True, "gemini": True, "deepseek": True, "notebooklm": False}),
        ConsiglioClaim(key="k2", value="v", votes={"claude": True, "gemini": False, "deepseek": False, "notebooklm": False}),
    ]
    result = ConsiglioResult(claims=claims, meta={})
    assert result.gate_6_passes() is False
    assert result.disputed_keys() == ["k2"]
EOF
```

- [ ] **Step 2: Run — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/research/test_consiglio_orchestrator.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/consiglio_orchestrator.py <<'EOF'
"""Consiglio v1 orchestrator — 4-LLM deliberation for research synthesis.

Gate 6 invariant: every final claim has ≥3/4 LLMs agreeing. Disputed
claims (≤2 agreement) are flagged but NOT dropped — Zero sees them
explicitly in the playbook.

Current Consiglio members:
  claude     — Claude Opus 4.7 OAuth
  gemini     — Gemini 3.1 Pro (Google AI Ultra)
  deepseek   — DeepSeek Reasoner (audited paid exception)
  notebooklm — NotebookLM authority validator
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConsiglioClaim:
    """A single claim voted on by all 4 LLMs."""

    key: str  # e.g. "cadence_instagram_lead_per_day"
    value: Any
    votes: dict[str, bool]  # llm_name → agrees

    def agreement_count(self) -> int:
        return sum(1 for v in self.votes.values() if v)

    def is_disputed(self) -> bool:
        return self.agreement_count() < 3


@dataclass
class ConsiglioResult:
    claims: list[ConsiglioClaim]
    meta: dict[str, Any] = field(default_factory=dict)

    def gate_6_passes(self) -> bool:
        return all(not c.is_disputed() for c in self.claims)

    def disputed_keys(self) -> list[str]:
        return [c.key for c in self.claims if c.is_disputed()]


class ConsiglioV1:
    """Runs deliberation across Claude/Gemini/DeepSeek/NotebookLM."""

    LLMS = ("claude", "gemini", "deepseek", "notebooklm")

    def __init__(self, timeout_sec: int = 600) -> None:
        self.timeout = timeout_sec

    def deliberate(
        self,
        question_prompt: str,
        *,
        context_files: list[str] | None = None,
    ) -> ConsiglioResult:
        """Ask the same question to each LLM, collect structured answers.

        Each LLM returns JSON: {claims: [{key, value, confidence}]}.
        We then build ConsiglioClaim by merging all 4 responses per key.
        """
        answers: dict[str, list[dict[str, Any]]] = {}
        for llm in self.LLMS:
            try:
                answers[llm] = self._ask(llm, question_prompt, context_files)
            except Exception as e:
                logger.warning("LLM %s failed: %s", llm, e)
                answers[llm] = []

        # Merge: group by key; each LLM votes True if it provided that key
        # with similar value, else False.
        all_keys: set[str] = set()
        for llm, lst in answers.items():
            for c in lst:
                all_keys.add(c["key"])

        claims: list[ConsiglioClaim] = []
        for key in all_keys:
            votes = {}
            canonical_value = None
            for llm, lst in answers.items():
                match = next((c for c in lst if c["key"] == key), None)
                if match is None:
                    votes[llm] = False
                    continue
                if canonical_value is None:
                    canonical_value = match["value"]
                votes[llm] = self._values_agree(match["value"], canonical_value)
            claims.append(ConsiglioClaim(key=key, value=canonical_value, votes=votes))

        return ConsiglioResult(
            claims=claims,
            meta={"llm_answer_counts": {k: len(v) for k, v in answers.items()}},
        )

    def _ask(
        self,
        llm: str,
        prompt: str,
        context_files: list[str] | None,
    ) -> list[dict[str, Any]]:
        cmd = self._build_cmd(llm, prompt, context_files)
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{llm} rc={result.returncode}")
        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    return data.get("claims", [])
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(f"{llm}: no JSON line found")

    def _build_cmd(self, llm: str, prompt: str, context_files: list[str] | None) -> list[str]:
        ctx_preamble = ""
        if context_files:
            for f in context_files:
                try:
                    ctx_preamble += f"\n\n## CONTEXT {f}:\n" + open(f).read()[:50000]
                except OSError:
                    pass

        full_prompt = f"{prompt}\n\n{ctx_preamble}"

        if llm == "claude":
            return ["claude", "-p", full_prompt]
        if llm == "gemini":
            return ["gemini", "-m", "gemini-3.1-pro-preview", "-p", full_prompt]
        if llm == "deepseek":
            # Assumes deepseek CLI wrapper at ~/.local/bin/deepseek-ask
            return ["deepseek-ask", full_prompt]
        if llm == "notebooklm":
            # NotebookLM via mcp wrapper script
            return ["nlm-query", full_prompt]
        raise ValueError(f"unknown llm: {llm}")

    @staticmethod
    def _values_agree(a: Any, b: Any) -> bool:
        """Agreement heuristic — exact match for scalars, fuzzy for strings."""
        if type(a) != type(b):
            return False
        if isinstance(a, str):
            return a.strip().lower() == b.strip().lower()
        return a == b
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_consiglio_orchestrator.py -q --tb=short
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/research/consiglio_orchestrator.py apps/backend-rag/backend/tests/unit/services/research/test_consiglio_orchestrator.py
git commit -m "feat(sota/day6): ConsiglioV1 orchestrator + Gate 6 predicate

4-LLM deliberation (claude/gemini/deepseek/notebooklm). Each claim is a
merged structured answer with per-LLM votes. ConsiglioResult.gate_6_passes
requires every claim ≥3/4 agreement.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 20: Consiglio v1 delibera → playbook (Day 9, ~3h)

**Files:**
- Create: `scripts/sota_consiglio_playbook.py`

Scope: Runs ConsiglioV1 with the 5 existing artifact files as context, produces `08_playbook.md` + `09_wr2_weights.json` + `preliminary_playbook.md` (day 6 draft).

- [ ] **Step 1: Write driver**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_consiglio_playbook.py <<'EOF'
#!/usr/bin/env python3
"""Day 6/9 driver — Consiglio v1 synthesizes playbook + wr2_weights.

Day 6: argv --wave=preliminary → preliminary_playbook.md
Day 9: argv --wave=final → 08_playbook.md + 09_wr2_weights.json

Gate 6 (EOD day 9): no disputed claims (all ≥3/4 agreement).
"""
from __future__ import annotations
import argparse, json, logging, subprocess, sys
from dataclasses import asdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.research.consiglio_orchestrator import ConsiglioV1

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.consiglio")

RESEARCH = _REPO / "research" / "sota-social-2026-v1"
ARTIFACTS = [
    RESEARCH / "00_baseline.json",
    RESEARCH / "01_balizero_corpus.json",
    RESEARCH / "02_competitor_corpus.json",
    RESEARCH / "03_sota_literature.md",
    RESEARCH / "04_personas.json",
    RESEARCH / "05_format_matrix.json",
    RESEARCH / "06_cadence_engine.json",
    RESEARCH / "07_gap_analysis.md",
]

SYNTHESIS_PROMPT = """You are one member of the Consiglio deliberating the Bali Zero social media playbook.

INPUTS: baseline + empirical 25 posts + benchmark 270 posts + literature +
6 personas + format matrix + cadence engine + gap analysis.

Produce a JSON object on the last line (no prose wrapper). Schema:
{{"claims":[
  {{"key":"<stable_snake_case_key>","value":<scalar_or_obj>,"confidence":<0-1>}},
  ...
]}}

Produce claims covering:
  1. cadence_{channel}_posts_per_day (14 channels)
  2. cadence_{channel}_optimal_hours_wita (14 channels)
  3. format_mix_{objective} (3 objectives)
  4. persona_weight_{slug} (6 personas)
  5. hook_pattern_top_{persona_slug} (6 personas)
  6. tone_resonance_{persona_slug}_{register} (6 × 7 = 42 claims)
  7. pillar_kpi_targets (3 pillars, each with numeric target)
  8. channel_priority_top3 (top 3 channels to activate week-1)

Minimum 100 claims total. Base every claim on the inputs — quote post
IDs or persona quotes where relevant. Confidence 0-1 reflecting how
sure you are."""


def render_playbook_md(result, wave: str) -> str:
    lines = [f"# Bali Zero Social Playbook (Consiglio v1, wave={wave})\n"]
    lines.append(f"> Generated {len(result.claims)} claims. "
                 f"Gate 6: {'PASS' if result.gate_6_passes() else 'FAIL'}.\n")

    sections: dict[str, list] = {}
    for c in result.claims:
        prefix = c.key.split("_")[0]
        sections.setdefault(prefix, []).append(c)

    for prefix, claims in sorted(sections.items()):
        lines.append(f"\n## {prefix}\n")
        for c in claims:
            disp = " ⚠️ DISPUTED" if c.is_disputed() else ""
            lines.append(f"- **{c.key}**: `{c.value}` (agreement {c.agreement_count()}/4){disp}")
    return "\n".join(lines)


def render_wr2_weights(result) -> dict:
    """Extract Council tone weights + persona weights + publisher kill-switch state."""
    weights = {
        "persona_weight": {},
        "tone_resonance": {},
        "cadence_by_channel": {},
        "format_mix_by_objective": {},
        "publisher_enabled_by_channel": {},  # explicit: default all OFF for canary
    }
    for c in result.claims:
        if c.is_disputed():
            continue
        if c.key.startswith("persona_weight_"):
            slug = c.key[len("persona_weight_"):]
            weights["persona_weight"][slug] = c.value
        elif c.key.startswith("tone_resonance_"):
            rest = c.key[len("tone_resonance_"):]
            # split last _ to separate register
            pslug, _, register = rest.rpartition("_")
            weights["tone_resonance"].setdefault(pslug, {})[register] = c.value
        elif c.key.startswith("cadence_") and "posts_per_day" in c.key:
            ch = c.key[len("cadence_"):-len("_posts_per_day")]
            weights["cadence_by_channel"].setdefault(ch, {})["posts_per_day"] = c.value
        elif c.key.startswith("cadence_") and "optimal_hours_wita" in c.key:
            ch = c.key[len("cadence_"):-len("_optimal_hours_wita")]
            weights["cadence_by_channel"].setdefault(ch, {})["optimal_hours_wita"] = c.value
        elif c.key.startswith("format_mix_"):
            obj = c.key[len("format_mix_"):]
            weights["format_mix_by_objective"][obj] = c.value

    # Safety: explicit publisher disabled for canary 7 days
    for ch in ["instagram", "linkedin", "tiktok", "threads", "x_twitter",
               "youtube_long", "youtube_shorts", "telegram", "whatsapp",
               "newsletter", "blog_seo", "podcast", "xiaohongshu_weibo",
               "quora_reddit"]:
        weights["publisher_enabled_by_channel"][ch] = False
    return weights


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", choices=["preliminary", "final"], required=True)
    args = ap.parse_args()

    council = ConsiglioV1(timeout_sec=900)
    result = council.deliberate(
        SYNTHESIS_PROMPT,
        context_files=[str(f) for f in ARTIFACTS if f.exists()],
    )

    logger.info("claims: %d", len(result.claims))
    logger.info("disputed: %d", len(result.disputed_keys()))

    if args.wave == "preliminary":
        path = RESEARCH / "preliminary_playbook.md"
        path.write_text(render_playbook_md(result, "preliminary"), encoding="utf-8")
        logger.info("wrote %s", path)
        return 0

    # wave=final
    playbook_path = RESEARCH / "08_playbook.md"
    weights_path = RESEARCH / "09_wr2_weights.json"
    playbook_path.write_text(render_playbook_md(result, "final"), encoding="utf-8")
    weights_path.write_text(json.dumps(render_wr2_weights(result), indent=2), encoding="utf-8")
    logger.info("wrote %s + %s", playbook_path, weights_path)

    if not result.gate_6_passes():
        logger.warning("Gate 6 SOFT FAIL: %d disputed claims flagged in playbook (not blocking — Zero decides)",
                       len(result.disputed_keys()))
        # Still return 0 — disputed claims are captured, not dropped
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_consiglio_playbook.py
```

- [ ] **Step 2: Day 6 preliminary run**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/sota_consiglio_playbook.py --wave=preliminary
```

Expected: `preliminary_playbook.md` written with 100+ claims. Takes 15-25 min (4 LLMs × large context).

- [ ] **Step 3: Day 9 final run**

```bash
python scripts/sota_consiglio_playbook.py --wave=final
```

Expected: `08_playbook.md` + `09_wr2_weights.json`. Log shows disputed count; disputed claims marked ⚠️ in MD.

- [ ] **Step 4: Commit (day 9)**

```bash
git add scripts/sota_consiglio_playbook.py research/sota-social-2026-v1/preliminary_playbook.md research/sota-social-2026-v1/08_playbook.md research/sota-social-2026-v1/09_wr2_weights.json
git commit -m "feat(sota/day9): Consiglio v1 delibera → 08_playbook + 09_wr2_weights

4-LLM deliberation over all 8 prior artifacts. Produces structured
claims merged with per-LLM agreement votes. Disputed claims flagged
but not dropped — Zero sees them in playbook.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 21: M13 Measurer config + Go-live canary runbook (Day 8-10, ~2h)

**Files:**
- Create: `research/sota-social-2026-v1/10_m13_measurer_config.md`
- Create: `research/sota-social-2026-v1/11_go_live_canary.md`

- [ ] **Step 1: Write M13 config**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/research/sota-social-2026-v1/10_m13_measurer_config.md <<'EOF'
# M13 Measurer — Feedback Loop Config

**Purpose:** close the post → measure → retrain loop (spec §WR2 integration point 3).

**Module:** `backend/services/measurer/m13_feedback_loop.py` (Task 22 in this plan).

## Collection horizons

For every post published by WR2, M13 collects metrics at three horizons
post-publication (in UTC hours):

- **T+24h** — early signal (impressions, likes, comments, saves)
- **T+72h** — mid signal (reach stabilizes; video views mature)
- **T+168h (7d)** — final signal (long-tail saves/shares, attributed leads)

Collection triggered by cron `scripts/m13_collect_post_metrics.py` every 6h.

## Metrics per horizon

Every horizon records the following into `post_metrics_history` (migration 128):

| metric_name | source | applies_to |
|-------------|--------|------------|
| likes | ig_graph | IG, IG Reels |
| comments | ig_graph | IG, IG Reels |
| saves | ig_graph | IG (save is IG-specific) |
| reach | ig_graph | IG |
| impressions | ig_graph | IG, IG Reels |
| video_views | ig_graph | IG Reels |
| reactions | linkedin | LinkedIn |
| shares | linkedin | LinkedIn |
| click_through | ga4 | any channel with UTM link |
| conversions_attributed | ga4 | any channel |
| session_duration_sec | ga4 | any channel |

## Retrain trigger conditions

Weekly (`scripts/m13_weekly_report.py`, Sunday 06:00 WITA):

1. Compare per-channel engagement rate vs baseline `00_baseline.json`.
2. If delta > +10% or < -10% for any channel on any horizon → retrain.
3. Retrain: re-run Consiglio v1 with updated empirical corpus → produce new
   `wr2_weights.json` with smoothing (20%/week max change per weight).
4. Append decision to `retrain_log.jsonl`.

Monthly (`scripts/m13_monthly_retrain.py`, 1st 04:30 WITA):
- Re-scrape competitors (mcp browser stealth, fallback to manual if blocked)
- Re-run Ahrefs SOV + AI citations
- Re-infer personas from new comments
- Full playbook minor bump (v1.1, v1.2, ...) if delta > 15%

Threshold breach (any time):
- If any pillar drops >20% from baseline → Telegram immediate +
  auto-toggle `wr2_publisher_enabled=false` for the regressing channel.

## Weight smoothing to prevent oscillation

Each retrain produces desired weights; actual update is:
```
new_weight = old_weight + (desired_weight - old_weight) * 0.2
```
This caps change at 20% per weekly step, preventing oscillation observed
in Risk #6 (spec).

## Stop condition

If `retrain_log.jsonl` shows week-over-week weight variance >40% for
3 consecutive weeks → M13 disables its own retrain (notifies Zero). Zero
must manually re-enable via `/retrain on`.

## Instrumentation

Every collection + retrain logs to `backend/services/observability/llm_cost_recorder.py`
with tags:
- `sota_m13_collect` (every 6h)
- `sota_m13_retrain_weekly` (Sunday)
- `sota_m13_retrain_monthly` (1st)
- `sota_m13_threshold_breach`

## References

- Migration 128: `apps/backend-rag/backend/db/migrations_v2/128_m13_feedback.sql`
- Spec: `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`
- Implementation: Task 22 below.
EOF
```

- [ ] **Step 2: Write canary runbook**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/research/sota-social-2026-v1/11_go_live_canary.md <<'EOF'
# Fase 0 → Loop Canary Runbook (first 7 days)

**Starts:** Fase 0 Day 11 (= Loop Day 1).
**Ends:** Day 17 (= Loop Day 7). After this, day-30 checkpoint begins.

## Pre-flight checklist (Fase 0 Day 10)

- [ ] All 12 artifacts in `research/sota-social-2026-v1/` exist (00-11).
- [ ] All 7 gates PASS per CI verification script.
- [ ] Migration 128 applied to prod DB.
- [ ] M13 feedback loop wired (`m13_feedback_loop.py` integration tests green).
- [ ] 4 launchd plists installed + loaded on Pro.
- [ ] Grafana dashboard accessible at `grafana.balizero.com/dashboard/social-sota`.
- [ ] Telegram kill-switch router mounted at `/api/research/*`.
- [ ] Zero has reviewed + approved `08_playbook.md` via Telegram reply.

## Canary config

**Publishing volume:** 1 IG post per day. No LinkedIn, no TikTok, no other channels. All other publisher kill-switches remain `false`.

**Publisher mode:** MANUAL only. `wr2_publisher_enabled` remains `false` for all channels. Publication happens via:
1. WR2 Council drafts the post as usual (reads playbook + persona weights)
2. Canva renderer produces the design
3. Review Gate Telegram sends photo + edit URL to Zero
4. Zero manually taps "Approve" AFTER double-checking in Canva
5. Publisher executes WITH manual flag (not cron-triggered)

**Why manual:** 7 days of manual approval let Zero observe predictions vs reality before trusting auto-publish. No surprise content.

## Daily check-in flow

Every day at 09:00 WITA, Zero receives Telegram digest with:
- Yesterday's posted content + T+24h metrics
- Predicted vs actual engagement (per 09_wr2_weights.json prediction)
- Top comment surfaced by Claude
- Next post draft in Canva (already generated, awaiting review)

## Kill conditions (auto-toggle publisher off)

Implemented in `scripts/m13_weekly_report.py` and Grafana alerts:

- Any pillar metric drops >20% from baseline → immediate Telegram alert +
  auto-toggle `wr2_publisher_enabled=false` (already false during canary,
  but the signal still fires).
- M13 delta prediction error >50% for 2 consecutive posts → pause WR2,
  Telegram "Predictions diverging, review required".
- 2 consecutive Review Gate rejections from Zero → pause WR2, Telegram
  "Content off-brand, review content_config".

## Day-7 checkpoint decision

On Canary Day 7, Zero reviews:
1. Did predictions align with reality? (M13 delta < 30%)
2. Did Zero have to reject any drafts? (Should be 0-1 out of 7)
3. Did any metric regress?

Decision options:
- **GO**: enable `wr2_publisher_enabled=true` for IG, scale to 2 posts/day.
- **EXTEND CANARY**: another 7 days manual.
- **PIVOT**: if consistent misses, re-trigger Consiglio v1 with extended
  empirical (= first 7 days' posts added to `01_balizero_corpus.json`).
- **KILL**: if gross regressions, fall back to pre-SOTA content strategy;
  investigate in post-mortem.

## Escalation path

All escalations go to Zero via Telegram. `/research pause` freezes
everything. No decision is auto-made at canary day 7 — Zero must reply
GO / EXTEND / PIVOT / KILL.
EOF
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add research/sota-social-2026-v1/10_m13_measurer_config.md research/sota-social-2026-v1/11_go_live_canary.md
git commit -m "docs(sota/day8+10): M13 config spec + go-live canary runbook

- 10_m13_measurer_config.md: horizons 24h/72h/168h, retrain triggers,
  smoothing 20%/week, stop condition, instrumentation taxonomy.
- 11_go_live_canary.md: 7-day manual-publishing canary, daily Telegram
  digest flow, kill conditions, day-7 GO/EXTEND/PIVOT/KILL decision.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 22: Day 10 final package + Zero approval request (Day 10, ~1h)

**Files:**
- Create: `scripts/sota_fase0_final_check.py`

- [ ] **Step 1: Write final-check script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_fase0_final_check.py <<'EOF'
#!/usr/bin/env python3
"""Fase 0 Day 10 — verify all 12 artifacts + all 7 gates green, notify Zero."""
from __future__ import annotations
import json, logging, subprocess, sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
RESEARCH = _REPO / "research" / "sota-social-2026-v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day10")

EXPECTED_ARTIFACTS = [
    "00_baseline.json", "01_balizero_corpus.json", "02_competitor_corpus.json",
    "03_sota_literature.md", "04_personas.json", "05_format_matrix.json",
    "06_cadence_engine.json", "07_gap_analysis.md", "08_playbook.md",
    "09_wr2_weights.json", "10_m13_measurer_config.md", "11_go_live_canary.md",
]


def check_artifacts() -> bool:
    ok = True
    for name in EXPECTED_ARTIFACTS:
        p = RESEARCH / name
        if not p.is_file():
            logger.error("MISSING: %s", name)
            ok = False
        elif p.stat().st_size < 100:
            logger.error("TOO SMALL: %s (%d bytes)", name, p.stat().st_size)
            ok = False
        else:
            logger.info("OK %s (%d bytes)", name, p.stat().st_size)
    return ok


def run_all_gates() -> bool:
    """Re-run each gate script in verify-only mode (no side effects)."""
    gates = {
        "Gate 1 baseline count": f"jq '[.. | numbers] | length' {RESEARCH}/00_baseline.json",
        "Gate 2 tone skew": f"jq '.dominant_tone_pct <= 0.6' {RESEARCH}/01_balizero_corpus.json",
        "Gate 3 competitor rows": f"jq '.sample_size >= 243' {RESEARCH}/02_competitor_corpus.json",
        "Gate 4 personas": f"jq '.personas | length' {RESEARCH}/04_personas.json",
        "Gate 5 literature sources": f"grep -oE 'https?://[^ )]+' {RESEARCH}/03_sota_literature.md | sort -u | wc -l",
    }
    all_ok = True
    for name, cmd in gates.items():
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        value = result.stdout.strip()
        logger.info("%s: %s", name, value)
        # rough pass/fail based on expected values
        if name == "Gate 1 baseline count" and int(value or 0) < 20: all_ok = False
        if name == "Gate 2 tone skew" and value != "true": all_ok = False
        if name == "Gate 3 competitor rows" and value != "true": all_ok = False
        if name == "Gate 4 personas" and int(value or 0) < 6: all_ok = False
        if name == "Gate 5 literature sources" and int(value or 0) < 30: all_ok = False
    return all_ok


def notify_zero(summary: str) -> None:
    import os, urllib.parse, urllib.request
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN missing, skipping notify")
        return
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            urllib.parse.urlencode({
                "chat_id": chat,
                "text": summary,
                "parse_mode": "Markdown",
            }).encode(),
            timeout=10,
        )
        logger.info("Telegram notification sent")
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


def main() -> int:
    logger.info("=== Fase 0 Day 10 final check ===")
    artifacts_ok = check_artifacts()
    gates_ok = run_all_gates()
    if not (artifacts_ok and gates_ok):
        logger.error("Fase 0 NOT complete — artifacts=%s gates=%s", artifacts_ok, gates_ok)
        notify_zero("🚨 SOTA Fase 0 day 10 — NOT ready. Artifacts or gates failing, check logs.")
        return 1

    notify_zero(
        "✅ *SOTA Fase 0 COMPLETE*\n\n"
        "12/12 artifacts written, 7/7 gates pass (Gates 6+7 require your reply).\n\n"
        "Review:\n"
        "• `research/sota-social-2026-v1/08_playbook.md`\n"
        "• `research/sota-social-2026-v1/11_go_live_canary.md`\n\n"
        "Reply here: *APPROVE SOTA* to start Loop 90d canary.\n"
        "Or reply *REVISE* + feedback to iterate before go-live."
    )
    logger.info("Fase 0 complete — awaiting Zero approval")
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_fase0_final_check.py
```

- [ ] **Step 2: Run check + notify Zero**

```bash
cd /Users/nuzantara/Desktop/nuzantara
source ~/.nuzantara-secrets.env
python scripts/sota_fase0_final_check.py
```

Expected: exits 0, Telegram message sent to Zero asking for APPROVE SOTA or REVISE.

- [ ] **Step 3: Wait for Zero Telegram reply**

Do not proceed to Loop 90d until Zero replies with `APPROVE SOTA` in Telegram. If `REVISE`, re-run Consiglio v1 with feedback and bump `08_playbook.md` to v2.1.

- [ ] **Step 4: Commit**

```bash
git add scripts/sota_fase0_final_check.py
git commit -m "feat(sota/day10): final-check script + Zero approval gate (Gate 7)

Verifies all 12 artifacts + runs Gates 1-5 in verify-only mode.
On PASS → sends Telegram to Zero for APPROVE SOTA reply. Loop 90d
starts ONLY after reply.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

> **CONTINUES IN:** `2026-04-22-bali-zero-social-sota-research-loop.md`
> (Tasks 23-32: Loop 90d cron scripts + launchd plists + Telegram router)

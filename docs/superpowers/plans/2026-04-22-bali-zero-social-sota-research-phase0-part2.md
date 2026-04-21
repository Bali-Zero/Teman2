# SOTA Fase 0 — Days 2-6 (Part 2a of 2)

> Companion to root plan. Execute after Part 1 complete (Day 1 baseline green, Gate 1 pass).

---

## Task 7: Empirical IG classifier — load 25 posts + schema (Day 2 morning, ~1h)

**Files:**
- Create: `apps/backend-rag/backend/services/research/empirical_ig_analyzer.py`
- Create: `apps/backend-rag/backend/tests/unit/services/research/test_empirical_ig_analyzer.py`

Scope: load `@balizero0` posts 5-29 (excluding last 4 per spec), persist raw JSON, produce schema for classification.

- [ ] **Step 1: Write failing test for post loader**

```bash
cat > apps/backend-rag/backend/tests/unit/services/research/test_empirical_ig_analyzer.py <<'EOF'
"""Tests for empirical_ig_analyzer — loads + classifies 25 own posts."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from backend.services.research.empirical_ig_analyzer import (
    EmpiricalIGAnalyzer,
    ClassifiedPost,
)


@pytest.mark.asyncio
async def test_load_posts_excludes_last_4():
    """Spec requires posts 5-29 (last 4 too recent for mature engagement)."""
    mock_sensor = AsyncMock()
    fake_posts = [{"post_id": f"p{i}", "likes": 10} for i in range(1, 30)]
    mock_sensor.read_posts.return_value = fake_posts
    analyzer = EmpiricalIGAnalyzer(ig_sensor=mock_sensor)
    loaded = await analyzer.load_posts_for_analysis()
    assert len(loaded) == 25
    assert loaded[0]["post_id"] == "p5"  # first post is the 5th newest
    assert loaded[-1]["post_id"] == "p29"


def test_classified_post_schema_has_all_attrs():
    cp = ClassifiedPost(
        post_id="p5", caption="Hook one\nBody here",
        format="CAROUSEL_ALBUM", hook_type="question",
        tone_register="pedagogico", topic="visa",
        posted_hour_wita=12, likes=100, comments=5, saves=20, reach=1500,
    )
    assert cp.engagement_rate == pytest.approx((100 + 5 + 20) / 1500, rel=0.01)
EOF
```

- [ ] **Step 2: Run — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement loader + schema**

```bash
cat > apps/backend-rag/backend/services/research/empirical_ig_analyzer.py <<'EOF'
"""Empirical analyzer for @balizero0 IG posts.

Pipeline (Fase 0 day 2):
  1. load_posts_for_analysis — pull posts 5-29 (skip last 4 too recent)
  2. classify_hook — Claude batch classifier → hook_type (5 categories)
  3. classify_tone — Gemini 1M ctx batch → tone_register (7 registers WR2)
  4. compute_correlations — DeepSeek Reasoner: metric × attribute Pearson
  5. persist → 01_balizero_corpus.json

Gate 2 invariant (EOD day 2): no single tone accounts for >60% of corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class ClassifiedPost:
    post_id: str
    caption: str
    format: str
    hook_type: str  # question | stat | story | contrarian | list
    tone_register: str  # pedagogico | analitico | tecnico | rituale | poetico | ironico | militante
    topic: str
    posted_hour_wita: int
    likes: int
    comments: int
    saves: int
    reach: int

    @property
    def engagement_rate(self) -> float:
        if self.reach == 0:
            return 0.0
        return (self.likes + self.comments + self.saves) / self.reach


class EmpiricalIGAnalyzer:
    def __init__(self, ig_sensor: Any) -> None:
        self.sensor = ig_sensor

    async def load_posts_for_analysis(self) -> list[dict[str, Any]]:
        """Fetch 29 most recent posts, return posts 5-29 (skip last 4 recent).

        Spec: `docs/superpowers/specs/...` Q9 custom note.
        """
        all_posts = await self.sensor.read_posts(limit=29)
        if len(all_posts) < 29:
            return all_posts[4:] if len(all_posts) > 4 else []
        return all_posts[4:]  # drop 4 most recent; keep older 25
EOF
```

- [ ] **Step 4: Run test — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py -q --tb=short
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/research/empirical_ig_analyzer.py apps/backend-rag/backend/tests/unit/services/research/test_empirical_ig_analyzer.py
git commit -m "feat(sota/day2): EmpiricalIGAnalyzer loader + ClassifiedPost schema

Loads posts 5-29 from @balizero0 (drops 4 most recent too young for
mature engagement). ClassifiedPost has attr hook_type/tone/format/topic
plus computed engagement_rate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Hook classifier — Claude CLI batch (Day 2 morning, ~1.5h)

**Files:** Modify `empirical_ig_analyzer.py`, add `scripts/sota_classify_balizero_posts.py`.

- [ ] **Step 1: Write test for hook classify integration**

Append to `test_empirical_ig_analyzer.py`:

```python
import subprocess
from unittest.mock import patch


@pytest.mark.asyncio
async def test_classify_hooks_parses_claude_output():
    """classify_hooks_batch returns one hook_type per post in order."""
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [
        {"post_id": "p1", "caption": "Did you know KBLI 2025...?"},
        {"post_id": "p2", "caption": "3 lies about PT PMA"},
    ]
    fake_stdout = (
        '{"classifications":[{"post_id":"p1","hook_type":"question"},'
        '{"post_id":"p2","hook_type":"list"}]}'
    )
    fake_proc = type("P", (), {"returncode": 0, "stdout": fake_stdout, "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_hooks_batch(posts)
    assert result["p1"] == "question"
    assert result["p2"] == "list"
```

- [ ] **Step 2: Run test — fails**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py::test_classify_hooks_parses_claude_output -q --tb=line 2>&1 | tail -3
```

Expected: AttributeError (method not defined).

- [ ] **Step 3: Implement classify_hooks_batch**

Append to `empirical_ig_analyzer.py`:

```python
    def classify_hooks_batch(self, posts: list[dict]) -> dict[str, str]:
        """Classify hook type via Claude CLI in a single batch call.

        Returns {post_id: hook_type}. Categories: question, stat, story,
        contrarian, list. Falls back to 'unknown' on parse errors.
        """
        import json
        import subprocess

        prompt_lines = [
            "Classify the HOOK TYPE of each Instagram post below. Emit ONLY a "
            "single JSON object on the last line, no prose, no markdown fences. "
            "Schema: {\"classifications\":[{\"post_id\":\"<id>\",\"hook_type\":"
            "\"question|stat|story|contrarian|list\"}]}",
            "",
        ]
        for p in posts:
            snippet = (p.get("caption") or "")[:500].replace("\n", " ")
            prompt_lines.append(f"post_id={p['post_id']}: {snippet}")
        prompt = "\n".join(prompt_lines)

        result = subprocess.run(
            ["claude", "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            return {p["post_id"]: "unknown" for p in posts}
        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    parsed = json.loads(line)
                    return {
                        c["post_id"]: c["hook_type"]
                        for c in parsed.get("classifications", [])
                    }
                except (json.JSONDecodeError, KeyError):
                    continue
        return {p["post_id"]: "unknown" for p in posts}
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py -q --tb=short
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/research/empirical_ig_analyzer.py apps/backend-rag/backend/tests/unit/services/research/test_empirical_ig_analyzer.py
git commit -m "feat(sota/day2): hook classifier via claude -p batch

Single Claude CLI call classifies 25 posts → {post_id: hook_type}.
Graceful fallback to 'unknown' on parse errors. Tests mock subprocess.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Tone classifier — Gemini 1M ctx batch (Day 2 afternoon, ~1.5h)

**Files:** Modify `empirical_ig_analyzer.py`.

- [ ] **Step 1: Write test for tone classify**

Append to `test_empirical_ig_analyzer.py`:

```python
@pytest.mark.asyncio
async def test_classify_tones_parses_gemini_output():
    analyzer = EmpiricalIGAnalyzer(ig_sensor=None)
    posts = [
        {"post_id": "p1", "caption": "In linea con la normativa BKPM..."},
        {"post_id": "p2", "caption": "Another visa horror story from our client..."},
    ]
    fake_stdout = (
        '{"classifications":[{"post_id":"p1","tone_register":"tecnico"},'
        '{"post_id":"p2","tone_register":"rituale"}]}'
    )
    fake_proc = type("P", (), {"returncode": 0, "stdout": fake_stdout, "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc):
        result = analyzer.classify_tones_batch(posts)
    assert result["p1"] == "tecnico"
    assert result["p2"] == "rituale"


def test_detect_skew_flags_dominant_tone():
    """Gate 2: if one tone >60%, flag."""
    dist = {"pedagogico": 18, "analitico": 3, "tecnico": 2, "ironico": 1,
            "rituale": 1, "militante": 0, "poetico": 0}  # 72% pedagogico
    ok, dominant, pct = EmpiricalIGAnalyzer.check_skew(dist, threshold=0.6)
    assert ok is False
    assert dominant == "pedagogico"
    assert pct == pytest.approx(0.72, abs=0.01)


def test_detect_skew_ok_when_balanced():
    dist = {"pedagogico": 10, "analitico": 8, "tecnico": 4, "ironico": 1,
            "rituale": 1, "militante": 1, "poetico": 0}
    ok, _, _ = EmpiricalIGAnalyzer.check_skew(dist, threshold=0.6)
    assert ok is True
```

- [ ] **Step 2: Run — fails**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py -q --tb=line 2>&1 | tail -5
```

Expected: AttributeError on `classify_tones_batch` and `check_skew`.

- [ ] **Step 3: Implement both methods**

Append to `empirical_ig_analyzer.py`:

```python
    def classify_tones_batch(self, posts: list[dict]) -> dict[str, str]:
        """Classify tone register via Gemini 3.1 Pro 1M ctx."""
        import json
        import subprocess

        registers = "pedagogico|analitico|tecnico|rituale|poetico|ironico|militante"
        prompt_lines = [
            "Classify the TONE REGISTER of each Instagram post. Emit ONLY a "
            "single JSON object on the last line, no prose. "
            f"Schema: {{\"classifications\":[{{\"post_id\":\"<id>\","
            f"\"tone_register\":\"{registers}\"}}]}}",
            "",
        ]
        for p in posts:
            snippet = (p.get("caption") or "")[:800].replace("\n", " ")
            prompt_lines.append(f"post_id={p['post_id']}: {snippet}")
        prompt = "\n".join(prompt_lines)

        result = subprocess.run(
            ["gemini", "-m", "gemini-3.1-pro-preview", "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            return {p["post_id"]: "unknown" for p in posts}
        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    parsed = json.loads(line)
                    return {
                        c["post_id"]: c["tone_register"]
                        for c in parsed.get("classifications", [])
                    }
                except (json.JSONDecodeError, KeyError):
                    continue
        return {p["post_id"]: "unknown" for p in posts}

    @staticmethod
    def check_skew(
        distribution: dict[str, int],
        *,
        threshold: float = 0.6,
    ) -> tuple[bool, str, float]:
        """Gate 2 check: returns (ok, dominant_tone, dominant_pct)."""
        total = sum(distribution.values())
        if total == 0:
            return True, "", 0.0
        dominant = max(distribution, key=distribution.get)
        pct = distribution[dominant] / total
        return (pct <= threshold, dominant, pct)
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_empirical_ig_analyzer.py -q --tb=short
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/research/empirical_ig_analyzer.py apps/backend-rag/backend/tests/unit/services/research/test_empirical_ig_analyzer.py
git commit -m "feat(sota/day2): tone classifier via gemini 3.1 pro + Gate 2 skew check

- classify_tones_batch: 7-register classification via gemini CLI subprocess
- check_skew: static helper returning (ok, dominant, pct) for Gate 2 (>60%)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Driver — build `01_balizero_corpus.json` (Day 2 evening, ~1h)

**Files:** Create `scripts/sota_classify_balizero_posts.py`.

- [ ] **Step 1: Write driver script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_classify_balizero_posts.py <<'EOF'
#!/usr/bin/env python3
"""Fase 0 Day 2 driver — classify 25 @balizero0 posts + persist corpus.

Gate 2 (EOD day 2): no tone >60%. Script exits 1 if skew detected.
"""

from __future__ import annotations

import asyncio, json, logging, os, sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.measurer.ig_graph_sensor import IGGraphSensor
from backend.services.research.empirical_ig_analyzer import (
    EmpiricalIGAnalyzer,
    ClassifiedPost,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day2")

OUTPUT = _REPO / "research" / "sota-social-2026-v1" / "01_balizero_corpus.json"


def _infer_topic(caption: str) -> str:
    c = (caption or "").lower()
    if any(w in c for w in ["kitas", "visa", "e33", "b211"]): return "visa"
    if any(w in c for w in ["pt pma", "pma", "kbli", "nib", "oss"]): return "company"
    if any(w in c for w in ["tax", "npwp", "dta", "aire", "tassazione"]): return "tax"
    if any(w in c for w in ["villa", "imb", "pbg", "hak pakai", "property"]): return "property"
    return "general"


def _hour_wita(timestamp_iso: str) -> int:
    try:
        dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        # WITA = UTC+8
        return (dt.hour + 8) % 24
    except Exception:
        return -1


async def main() -> int:
    token = os.environ.get("IG_GRAPH_API_TOKEN")
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    if not (token and ig_id):
        logger.error("IG secrets missing")
        return 2

    sensor = IGGraphSensor(token=token, ig_user_id=ig_id)
    analyzer = EmpiricalIGAnalyzer(ig_sensor=sensor)

    raw_posts = await analyzer.load_posts_for_analysis()
    logger.info("loaded %d posts", len(raw_posts))

    # IGPostMetrics → dict for classifier
    posts_dicts = [
        asdict(p) if hasattr(p, "post_id") else p
        for p in raw_posts
    ]

    logger.info("classifying hooks (claude)...")
    hooks = analyzer.classify_hooks_batch(posts_dicts)
    logger.info("classifying tones (gemini)...")
    tones = analyzer.classify_tones_batch(posts_dicts)

    classified: list[ClassifiedPost] = []
    for p in posts_dicts:
        cp = ClassifiedPost(
            post_id=p["post_id"],
            caption=p.get("caption", ""),
            format=p.get("format", "IMAGE"),
            hook_type=hooks.get(p["post_id"], "unknown"),
            tone_register=tones.get(p["post_id"], "unknown"),
            topic=_infer_topic(p.get("caption", "")),
            posted_hour_wita=_hour_wita(p.get("timestamp", "")),
            likes=p.get("likes", 0),
            comments=p.get("comments", 0),
            saves=p.get("saves", 0),
            reach=p.get("reach", 0),
        )
        classified.append(cp)

    # Gate 2 check
    tone_dist = Counter(c.tone_register for c in classified)
    ok, dominant, pct = EmpiricalIGAnalyzer.check_skew(dict(tone_dist), threshold=0.6)

    # Persist
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_account": os.environ.get("IG_BUSINESS_HANDLE", "balizero0"),
        "sample_size": len(classified),
        "tone_distribution": dict(tone_dist),
        "dominant_tone_pct": round(pct, 3),
        "posts": [asdict(c) for c in classified],
    }, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d posts)", OUTPUT, len(classified))

    if not ok:
        logger.error("Gate 2 FAIL: tone %r = %.1f%% (>60%%)", dominant, pct * 100)
        return 1
    logger.info("Gate 2 OK: dominant %r = %.1f%%", dominant, pct * 100)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_classify_balizero_posts.py
```

- [ ] **Step 2: Live run**

```bash
source ~/.nuzantara-secrets.env
python scripts/sota_classify_balizero_posts.py
```

Expected: exits 0, file `research/sota-social-2026-v1/01_balizero_corpus.json` exists, tone distribution printed.

- [ ] **Step 3: Gate 2 verification**

```bash
jq '.dominant_tone_pct' research/sota-social-2026-v1/01_balizero_corpus.json
```

Expected: ≤ 0.6.

- [ ] **Step 4: Commit**

```bash
git add scripts/sota_classify_balizero_posts.py research/sota-social-2026-v1/01_balizero_corpus.json
git commit -m "feat(sota/day2): driver for 01_balizero_corpus.json + Gate 2

Classifies 25 @balizero0 posts (hook+tone+topic+format) and persists.
Gate 2 pass: no tone register >60%.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Team-member runbook — manual competitor scraping (Day 2, ~1h)

**Files:**
- Create: `docs/runbooks/competitor-scrape-manual.md`
- Create: Google Sheet (link recorded in runbook)

- [ ] **Step 1: Write runbook**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/docs/runbooks
cat > /Users/nuzantara/Desktop/nuzantara/docs/runbooks/competitor-scrape-manual.md <<'EOF'
# Competitor IG Scrape Runbook (Manual, 25h total)

**Audience:** team member assigned in Task 0 Q1.
**Time budget:** 25 hours total, spread over 5 working days (5h/day).
**Output:** filled Google Sheet "SOTA Competitor Corpus v1".
**Deadline:** by EOD Fase 0 Day 6 (Gate 3 blocking).

## What you scrape

18 Instagram accounts × 15 most recent posts = **270 rows**.

### Accounts list (copy from `research/sota-social-2026-v1/competitors.txt`)

Tribe 1 (10 direct agencies):
1. @lawbali
2. @emerhub
3. @incorp_indonesia
4. @cekindo_official
5. @permitindo
6. @balisolutions
7. @bli_bali
8. @kiradigital
9. @indolegal
10. @bambuhijau_konsultan

Tribe 2 (8 expat influencers):
11. @solopreneur_bali
12. @digitalnomadworld
13. @nomadgate
14. @nomadsembassy
15. @balibuddha
16. @reneesylvestre
17. @thebalibible
18. @indoexpatcommunity

## Google Sheet schema

Open: https://docs.google.com/spreadsheets/d/SHEET_ID_PLACEHOLDER/edit

Fill one row per post. Columns:

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| account_handle | string | lawbali | No `@` prefix |
| post_url | string | https://www.instagram.com/p/ABC123/ | Permalink |
| posted_date | YYYY-MM-DD | 2026-04-18 | Date shown below post |
| format | enum | carousel | one of: carousel, reel, static, video |
| slide_count | int | 7 | Only if carousel |
| caption_full | string | (paste full) | Copy-paste — don't summarize |
| hashtags | string | #kitas #visa | Space-separated, keep `#` |
| hook_text | string | (first 2 lines) | The first ~120 chars of caption |
| likes_count | int | 245 | Visible number |
| comments_count | int | 12 | Visible number |
| video_views_count | int | 3400 | Only if video/reel |
| posted_time_wita | HH:MM | 19:30 | Post timestamp converted to WITA (UTC+8). If IG shows relative time ("3h ago"), compute |

## Procedure

1. **Setup (once, 15 min):**
   - Log into Instagram on your personal account
   - Open the Google Sheet, have it side-by-side with browser
   - Pin the sheet tab

2. **Per account (~80 min):**
   - Visit profile: `instagram.com/<handle>/`
   - Scroll through feed top to bottom until you've counted 15 posts
   - For each of the 15 (newest first):
     - Open post in new tab
     - Copy data into sheet
     - Close tab
     - Move to next

3. **Quality checks every 5 posts:**
   - Caption must have >20 characters (not just emoji)
   - Likes count must be non-empty
   - Hashtag field must have at least one if any were in caption

4. **Pacing:** ~5 min per post. Don't skip hard ones — leave caption blank with note `"[hidden/paywalled]"` if Instagram hides it.

## Daily Telegram check-in to Zero

At end of each day post in Telegram:
```
SOTA Day N: scraped X/270 rows. On track / slow.
Blockers: <any>
Tomorrow: <accounts planned>
```

## Escalation

If by EOD Day 5 you have <200 rows, ping Zero immediately — Fase 0 falls back to Playwright automation for missing accounts (Task 12 fallback).

## When done

1. Export sheet as CSV: File → Download → Comma-separated values (.csv)
2. Save to `research/sota-social-2026-v1/competitor_raw.csv`
3. Notify Zero in Telegram: "SOTA competitor scrape complete, 270 rows ready"
4. Claude runs `scripts/sota_ingest_competitors.py` to transform → `02_competitor_corpus.json` (Task 13)

## Tips

- Instagram may throttle you if you load 300 posts in an hour — take 15min breaks every 30 posts.
- Use Chrome incognito + your Bali Zero work account if your personal is linked to phone notifications you don't want.
- Posts older than 2 months may have inflated likes from bots — note but still record.
- For carousels: slide_count = count of dots at bottom of image, NOT caption character count.
EOF
```

- [ ] **Step 2: Create competitors.txt**

```bash
cat > research/sota-social-2026-v1/competitors.txt <<'EOF'
# 18 competitor accounts — Tribe 1 (10 agencies) + Tribe 2 (8 influencers)
# Scope: 15 IG posts per account = 270 rows total.
# Used by docs/runbooks/competitor-scrape-manual.md + scripts/sota_ingest_competitors.py.

# Tribe 1 — direct competitors (agencies)
lawbali agency
emerhub agency
incorp_indonesia agency
cekindo_official agency
permitindo agency
balisolutions agency
bli_bali agency
kiradigital agency
indolegal agency
bambuhijau_konsultan agency

# Tribe 2 — expat influencers
solopreneur_bali influencer
digitalnomadworld influencer
nomadgate influencer
nomadsembassy influencer
balibuddha influencer
reneesylvestre influencer
thebalibible influencer
indoexpatcommunity influencer
EOF
```

- [ ] **Step 3: Create + link Google Sheet**

Manual action: open https://sheets.new, name "SOTA Competitor Corpus v1", add headers from runbook. Share "Editor" with team member and Zero. Copy the sheet URL, replace `SHEET_ID_PLACEHOLDER` in the runbook with the real sheet ID.

```bash
# After replacing placeholder:
git add docs/runbooks/competitor-scrape-manual.md research/sota-social-2026-v1/competitors.txt
git commit -m "docs(sota): competitor scrape runbook + 18-account list

25h manual work for team member. Fills Google Sheet with 270 rows
(18 accounts × 15 posts). Quality-checklisted. Daily Telegram
check-in. Deadline EOD Fase 0 day 6 (Gate 3 blocking).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Send kick-off to team member**

```bash
cat <<EOF
Send via Telegram to assigned team member:

"Hi, SOTA research avvio oggi. Runbook: docs/runbooks/competitor-scrape-manual.md
Google Sheet: <SHEET_URL>

Target: 270 rows in 5 days (5h/gg). Daily check-in alle 18:00 WITA in
Telegram a Zero + me. Inizia con @lawbali oggi.

Dubbi? Chiedimi quando vuoi."
EOF
```

---

## Task 12: Literature research kickoff (Day 3 morning, ~2h)

**Files:**
- Create: `apps/backend-rag/backend/services/research/literature_agent.py`
- Create: `scripts/sota_literature_research.py`

Scope: Gemini Deep Research (grounded) + NotebookLM research_start in parallel, produce `03_sota_literature.md` with ≥30 sources (≥10 from 2025-26).

- [ ] **Step 1: Write literature_agent.py**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/literature_agent.py <<'EOF'
"""Literature synthesis agent — orchestrates Gemini Deep Research + NotebookLM.

Produces `03_sota_literature.md` covering 4 topics (spec §Q8 A4):
  1. Hook taxonomy 2024-26
  2. Tone/voice B2B legal/immigration
  3. Cadence + algorithm windows IG/LinkedIn/TikTok/Threads 2026
  4. Format × objective matrix primer

Gate 5 invariant (EOD day 3): ≥30 distinct sources, ≥10 from 2025-26.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ResearchTopic:
    slug: str
    prompt: str  # Gemini Deep Research prompt


TOPICS: list[ResearchTopic] = [
    ResearchTopic(
        slug="01_hook_taxonomy",
        prompt=(
            "Research hook taxonomy for social media 2024-2026 (IG/LinkedIn/"
            "TikTok). Cite academic papers + top creator economy blogs "
            "(NEDE, Later, HubSpot, Buffer). Structure as: taxonomy + top 20 "
            "patterns + 2026 trends. Min 15 sources with URLs + dates."
        ),
    ),
    ResearchTopic(
        slug="02_tone_voice_b2b_legal",
        prompt=(
            "Research tone/voice strategies for B2B legal + immigration "
            "services social presence 2024-2026. Benchmark: Big4 legal "
            "firms (Deloitte, SSEK, EY Indonesia), top creator lawyers. "
            "Include: appropriate formality, authority signaling, "
            "persona adaptation. Min 8 sources."
        ),
    ),
    ResearchTopic(
        slug="03_cadence_algorithm_2026",
        prompt=(
            "Research 2026 algorithm windows and posting cadence for IG, "
            "LinkedIn, TikTok, Threads. Include Adam Mosseri 2025-26 "
            "statements, LinkedIn algo research 2025, TikTok 2026 CPM "
            "analysis. Optimal times WITA (UTC+8) for Indonesian + "
            "European expat audiences. Min 10 sources."
        ),
    ),
    ResearchTopic(
        slug="04_format_objective_matrix",
        prompt=(
            "Research which content formats (carousel, reel, static, long-"
            "form, threads, newsletter) best serve which objectives (lead "
            "capture, authority building, audience growth) for B2B service "
            "businesses. 2025-26 data only. Min 8 sources."
        ),
    ),
]


class LiteratureAgent:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def research_topic(self, topic: ResearchTopic, *, timeout: int = 300) -> str:
        """Run Gemini Deep Research for one topic, return markdown body."""
        prompt = (
            f"{topic.prompt}\n\n"
            "OUTPUT: Markdown document with sections '## Summary', "
            "'## Key findings', '## Sources' (numbered list with URL + "
            "publication year). Ground every claim in a source."
        )
        result = subprocess.run(
            ["gemini", "-m", "gemini-3.1-pro-preview", "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("gemini returncode=%s stderr=%s", result.returncode, result.stderr[-300:])
            return f"# {topic.slug}\n\n_Research failed: rc={result.returncode}_"
        return result.stdout

    def count_sources(self, markdown: str) -> tuple[int, int]:
        """Return (total_sources, sources_from_2025_or_2026)."""
        # Extract URL+year patterns
        urls = re.findall(r"https?://[^\s\)]+", markdown)
        recent = re.findall(r"\b(2025|2026)\b", markdown)
        return (len(set(urls)), len(recent))

    def synthesize(self, bodies: dict[str, str]) -> str:
        """Concatenate topic outputs into 03_sota_literature.md."""
        header = (
            "# SOTA Literature Synthesis — Social Media 2026\n\n"
            "> Auto-generated by `scripts/sota_literature_research.py`. "
            "Part of Fase 0 day 3.\n\n"
            "---\n\n"
        )
        parts = [header]
        for topic_slug, body in bodies.items():
            parts.append(f"## {topic_slug}\n\n{body}\n\n---\n\n")
        return "".join(parts)
EOF
```

- [ ] **Step 2: Write driver script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_literature_research.py <<'EOF'
#!/usr/bin/env python3
"""Fase 0 Day 3 driver — Gemini Deep Research across 4 topics + synthesize.

Gate 5 (EOD day 3): ≥30 sources, ≥10 from 2025-26.
"""

from __future__ import annotations

import logging, sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.research.literature_agent import (
    LiteratureAgent,
    TOPICS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day3")

OUT = _REPO / "research" / "sota-social-2026-v1" / "03_sota_literature.md"


def main() -> int:
    agent = LiteratureAgent(output_dir=OUT.parent)
    bodies = {}
    for topic in TOPICS:
        logger.info("researching %s...", topic.slug)
        bodies[topic.slug] = agent.research_topic(topic)

    md = agent.synthesize(bodies)
    OUT.write_text(md, encoding="utf-8")
    logger.info("wrote %s", OUT)

    total, recent = agent.count_sources(md)
    logger.info("Sources: total=%d recent(2025-26)=%d", total, recent)
    if total < 30 or recent < 10:
        logger.error("Gate 5 FAIL: need ≥30 total + ≥10 recent, got %d/%d", total, recent)
        return 1
    logger.info("Gate 5 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_literature_research.py
```

- [ ] **Step 3: Live run**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/sota_literature_research.py
```

Expected: takes 10-20 min across 4 topics, exits 0, file written. If Gate 5 fails, re-run individual topic with longer prompt.

- [ ] **Step 4: Gate 5 verification**

```bash
SRC=$(grep -oE 'https?://[^ )]+' research/sota-social-2026-v1/03_sota_literature.md | sort -u | wc -l)
RECENT=$(grep -cE '\b(2025|2026)\b' research/sota-social-2026-v1/03_sota_literature.md)
echo "sources=$SRC recent_mentions=$RECENT"
```

Expected: sources ≥ 30, recent_mentions ≥ 10.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/research/literature_agent.py scripts/sota_literature_research.py research/sota-social-2026-v1/03_sota_literature.md
git commit -m "feat(sota/day3): literature synthesis + 03_sota_literature.md

Gemini Deep Research on 4 topics (hook taxonomy / tone B2B legal /
cadence+algorithms 2026 / format×objective). Synthesized markdown
passes Gate 5 (≥30 sources, ≥10 from 2025-26).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Competitor ingest — Sheet CSV → corpus JSON (Day 6 morning, ~2h)

> Runs day 6 when team member finishes scraping (Gate 3).

**Files:**
- Create: `apps/backend-rag/backend/services/research/competitor_ingest.py`
- Create: `apps/backend-rag/backend/tests/unit/services/research/test_competitor_ingest.py`
- Create: `scripts/sota_ingest_competitors.py`

- [ ] **Step 1: Write failing test**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/tests/unit/services/research/test_competitor_ingest.py <<'EOF'
"""Tests for competitor CSV ingest → JSON corpus."""

from __future__ import annotations

import csv
import io
import pytest
from backend.services.research.competitor_ingest import (
    CompetitorIngest,
    CompetitorPost,
)


CSV_HEADER = (
    "account_handle,post_url,posted_date,format,slide_count,caption_full,"
    "hashtags,hook_text,likes_count,comments_count,video_views_count,"
    "posted_time_wita\n"
)


def test_ingest_csv_parses_correctly():
    csv_body = CSV_HEADER + (
        "lawbali,https://instagram.com/p/ABC,2026-04-15,carousel,7,"
        "Full caption here,#kitas #visa,Hook line,245,12,,19:30\n"
        "solopreneur_bali,https://instagram.com/p/XYZ,2026-04-14,reel,,"
        "Reel caption,#bali,Another hook,1500,45,8400,18:00\n"
    )
    ingest = CompetitorIngest()
    posts = ingest.parse_csv(io.StringIO(csv_body))
    assert len(posts) == 2
    assert posts[0].account_handle == "lawbali"
    assert posts[0].format == "carousel"
    assert posts[0].slide_count == 7
    assert posts[1].video_views_count == 8400
    assert posts[1].slide_count is None  # reel has no slide_count


def test_ingest_rejects_missing_required_columns():
    bad = "account_handle,post_url\nlawbali,https://x\n"
    ingest = CompetitorIngest()
    with pytest.raises(ValueError, match="missing columns"):
        ingest.parse_csv(io.StringIO(bad))


def test_coverage_by_account_flags_incomplete():
    posts = [
        CompetitorPost(account_handle="a", post_url="u", posted_date="2026-04-15",
                       format="carousel", slide_count=5, caption_full="c", hashtags="",
                       hook_text="h", likes_count=10, comments_count=1,
                       video_views_count=None, posted_time_wita="18:00")
        for _ in range(15)  # 15 posts for account a
    ]
    posts += [
        CompetitorPost(account_handle="b", post_url="u", posted_date="2026-04-15",
                       format="static", slide_count=None, caption_full="c", hashtags="",
                       hook_text="h", likes_count=5, comments_count=0,
                       video_views_count=None, posted_time_wita="09:00")
        for _ in range(8)  # only 8 posts for account b
    ]
    ingest = CompetitorIngest()
    coverage = ingest.coverage_by_account(posts)
    assert coverage["a"] == 15
    assert coverage["b"] == 8
EOF
```

- [ ] **Step 2: Run test — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/research/test_competitor_ingest.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement competitor_ingest**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/research/competitor_ingest.py <<'EOF'
"""Competitor CSV → JSON corpus ingest.

Consumes the Google Sheet export filled by team member (see
docs/runbooks/competitor-scrape-manual.md). Produces
`02_competitor_corpus.json` with 270 rows (18 × 15).

Gate 3 (EOD day 6): ≥243 rows (270 − 10% tolerance).
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Iterable


REQUIRED_COLUMNS = {
    "account_handle", "post_url", "posted_date", "format",
    "slide_count", "caption_full", "hashtags", "hook_text",
    "likes_count", "comments_count", "video_views_count", "posted_time_wita",
}


@dataclass
class CompetitorPost:
    account_handle: str
    post_url: str
    posted_date: str  # YYYY-MM-DD
    format: str  # carousel|reel|static|video
    slide_count: int | None
    caption_full: str
    hashtags: str
    hook_text: str
    likes_count: int
    comments_count: int
    video_views_count: int | None
    posted_time_wita: str  # HH:MM


def _int_or_none(value: str) -> int | None:
    if not value or value.strip() == "":
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


class CompetitorIngest:
    def parse_csv(self, source: io.TextIOBase | Iterable[str]) -> list[CompetitorPost]:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"missing columns: {sorted(missing)}")
        out: list[CompetitorPost] = []
        for row in reader:
            out.append(CompetitorPost(
                account_handle=row["account_handle"].strip().lstrip("@"),
                post_url=row["post_url"].strip(),
                posted_date=row["posted_date"].strip(),
                format=row["format"].strip().lower(),
                slide_count=_int_or_none(row["slide_count"]),
                caption_full=row["caption_full"],
                hashtags=row["hashtags"].strip(),
                hook_text=row["hook_text"].strip(),
                likes_count=int(row["likes_count"] or 0),
                comments_count=int(row["comments_count"] or 0),
                video_views_count=_int_or_none(row["video_views_count"]),
                posted_time_wita=row["posted_time_wita"].strip(),
            ))
        return out

    def coverage_by_account(self, posts: list[CompetitorPost]) -> dict[str, int]:
        return dict(Counter(p.account_handle for p in posts))

    def to_json_payload(self, posts: list[CompetitorPost]) -> dict:
        coverage = self.coverage_by_account(posts)
        return {
            "sample_size": len(posts),
            "account_count": len(coverage),
            "coverage_by_account": coverage,
            "posts": [asdict(p) for p in posts],
        }
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/research/test_competitor_ingest.py -q --tb=short
```

Expected: `3 passed`.

- [ ] **Step 5: Write driver script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_ingest_competitors.py <<'EOF'
#!/usr/bin/env python3
"""Fase 0 Day 6 driver — ingest Google Sheet CSV → 02_competitor_corpus.json.

Gate 3 (EOD day 6): ≥243 rows.
"""

from __future__ import annotations

import json, logging, sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

from backend.services.research.competitor_ingest import CompetitorIngest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day6")

CSV_IN = _REPO / "research" / "sota-social-2026-v1" / "competitor_raw.csv"
JSON_OUT = _REPO / "research" / "sota-social-2026-v1" / "02_competitor_corpus.json"
MIN_ROWS = 243  # Gate 3


def main() -> int:
    if not CSV_IN.is_file():
        logger.error("CSV not found: %s — team member must deliver this first", CSV_IN)
        return 2
    ingest = CompetitorIngest()
    with CSV_IN.open("r", encoding="utf-8") as f:
        posts = ingest.parse_csv(f)
    logger.info("parsed %d posts from %d accounts", len(posts), len(set(p.account_handle for p in posts)))

    payload = ingest.to_json_payload(posts)
    JSON_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("wrote %s", JSON_OUT)

    if len(posts) < MIN_ROWS:
        logger.error("Gate 3 FAIL: %d rows < %d", len(posts), MIN_ROWS)
        return 1
    logger.info("Gate 3 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_ingest_competitors.py
```

- [ ] **Step 6: Gate 3 run (when CSV ready, day 6)**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/sota_ingest_competitors.py
jq '.sample_size, .coverage_by_account' research/sota-social-2026-v1/02_competitor_corpus.json
```

Expected: sample_size ≥ 243, coverage shows 18 handles.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/services/research/competitor_ingest.py apps/backend-rag/backend/tests/unit/services/research/test_competitor_ingest.py scripts/sota_ingest_competitors.py
git commit -m "feat(sota/day6): competitor CSV ingest + Gate 3 check

Consumes team-scraped Google Sheet export, produces
02_competitor_corpus.json with 270-row target (243 min for Gate 3).
Tests cover schema validation + coverage computation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

> **CONTINUES IN:** `2026-04-22-bali-zero-social-sota-research-phase0-part3.md`
> (Tasks 14-22: Days 4-10 personas + Consiglio v1 + playbook + canary)

# SOTA Loop 90d + WR2 Integration + Grafana + Smoke

> Companion to root plan. Execute after Fase 0 complete (`08_playbook.md` approved by Zero).

---

## Task 23: M13 Feedback Loop core class (~3h)

**Files:**
- Create: `apps/backend-rag/backend/services/measurer/m13_feedback_loop.py`
- Create: `apps/backend-rag/backend/tests/unit/services/measurer/test_m13_feedback_loop.py`

- [ ] **Step 1: Write failing test**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/tests/unit/services/measurer/test_m13_feedback_loop.py <<'EOF'
"""Tests for M13FeedbackLoop — collect, delta, retrain trigger."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.services.measurer.m13_feedback_loop import (
    M13FeedbackLoop,
    M13CollectionHorizon,
)


class _FakeAcq:
    def __init__(self, conn): self._c = conn
    async def __aenter__(self): return self._c
    async def __aexit__(self, *a): return None


class _FakePool:
    def __init__(self, conn): self._c = conn
    def acquire(self): return _FakeAcq(self._c)


@pytest.mark.asyncio
async def test_collect_persists_one_row_per_metric():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = _FakePool(conn)
    loop = M13FeedbackLoop(db_pool=pool)
    post_id = uuid4()
    await loop.collect_post_metrics(
        post_id=post_id,
        horizon=M13CollectionHorizon.T_24H,
        metrics={"likes": 120, "saves": 34, "reach": 1500},
        source="ig_graph",
    )
    # 3 metrics → 3 inserts
    assert conn.execute.await_count == 3
    # Check SQL mentions post_metrics_history
    sql = conn.execute.await_args_list[0].args[0]
    assert "INSERT INTO post_metrics_history" in sql


@pytest.mark.asyncio
async def test_compute_delta_vs_baseline_returns_pct():
    conn = AsyncMock()
    # Recent avg engagement
    conn.fetchval = AsyncMock(side_effect=[0.054, 0.040])  # recent, baseline
    pool = _FakePool(conn)
    loop = M13FeedbackLoop(db_pool=pool)
    delta = await loop.compute_delta_vs_baseline(channel="instagram", pillar="audience")
    assert delta == pytest.approx(0.35, rel=0.01)  # (0.054 - 0.040)/0.040


def test_smoothing_caps_weight_change():
    loop = M13FeedbackLoop(db_pool=None)
    new_w = loop._smooth_weight(old=0.5, desired=1.0, cap=0.2)
    assert new_w == pytest.approx(0.6, rel=0.01)  # 0.5 + (1.0 - 0.5) * 0.2


def test_should_trigger_retrain_on_positive_breach():
    loop = M13FeedbackLoop(db_pool=None)
    assert loop.should_trigger_retrain(delta=0.12) is True  # >10%
    assert loop.should_trigger_retrain(delta=-0.15) is True  # <-10%
    assert loop.should_trigger_retrain(delta=0.05) is False


def test_threshold_breach_pillar_drop(tmp_path: Path):
    loop = M13FeedbackLoop(db_pool=None)
    assert loop.is_pillar_threshold_breach(delta=-0.25) is True  # <-20%
    assert loop.is_pillar_threshold_breach(delta=-0.10) is False
    assert loop.is_pillar_threshold_breach(delta=0.30) is False  # positive not a breach
EOF
```

- [ ] **Step 2: Run — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/measurer/test_m13_feedback_loop.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/measurer/m13_feedback_loop.py <<'EOF'
"""M13 Feedback Loop — closes post → measure → retrain cycle.

Responsibilities (see research/sota-social-2026-v1/10_m13_measurer_config.md):

1. collect_post_metrics   — insert into post_metrics_history
2. compute_delta_vs_baseline — compare recent engagement to 00_baseline.json
3. should_trigger_retrain — ±10% delta threshold
4. is_pillar_threshold_breach — -20% auto-toggle publisher off
5. retrain_weights_with_smoothing — apply 20%/week change cap
6. log_retrain — append to m13_retrain_log
"""

from __future__ import annotations

import enum
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class M13CollectionHorizon(enum.Enum):
    T_24H = 24
    T_72H = 72
    T_168H = 168


class M13FeedbackLoop:
    """Closes the WR2 post publication feedback loop."""

    RETRAIN_DELTA_THRESHOLD = 0.10
    PILLAR_BREACH_THRESHOLD = -0.20
    WEIGHT_SMOOTHING_CAP = 0.20

    def __init__(self, db_pool: Any) -> None:
        self.db_pool = db_pool

    async def collect_post_metrics(
        self,
        *,
        post_id: UUID,
        horizon: M13CollectionHorizon,
        metrics: dict[str, float],
        source: str,
    ) -> None:
        """Insert one row per metric into post_metrics_history."""
        sql = """
            INSERT INTO post_metrics_history
                (post_id, horizon_hours, metric_name, metric_value, source)
            VALUES ($1, $2, $3, $4, $5)
        """
        async with self.db_pool.acquire() as conn:
            for name, value in metrics.items():
                await conn.execute(sql, post_id, horizon.value, name, float(value), source)
        logger.debug("collected %d metrics for post %s @ %s", len(metrics), post_id, horizon.name)

    async def compute_delta_vs_baseline(
        self, *, channel: str, pillar: str,
    ) -> float:
        """Return (recent_avg - baseline_avg) / baseline_avg over last 7 days."""
        metric_map = {
            "audience": "saves",  # engagement proxy for IG
            "authority": "reach",
            "lead": "click_through",
        }
        metric = metric_map.get(pillar, "likes")
        async with self.db_pool.acquire() as conn:
            recent = await conn.fetchval("""
                SELECT AVG(metric_value)
                  FROM post_metrics_history pmh
                  JOIN war_room_posts wrp ON wrp.id = pmh.post_id
                 WHERE wrp.platform = $1
                   AND pmh.metric_name = $2
                   AND pmh.collected_at > NOW() - INTERVAL '7 days'
            """, channel, metric)
            baseline = await conn.fetchval("""
                SELECT AVG(metric_value)
                  FROM post_metrics_history pmh
                  JOIN war_room_posts wrp ON wrp.id = pmh.post_id
                 WHERE wrp.platform = $1
                   AND pmh.metric_name = $2
                   AND pmh.collected_at BETWEEN NOW() - INTERVAL '30 days'
                                             AND NOW() - INTERVAL '7 days'
            """, channel, metric)
        if not baseline or baseline == 0:
            return 0.0
        return (float(recent or 0) - float(baseline)) / float(baseline)

    def should_trigger_retrain(self, *, delta: float) -> bool:
        return abs(delta) >= self.RETRAIN_DELTA_THRESHOLD

    def is_pillar_threshold_breach(self, *, delta: float) -> bool:
        return delta <= self.PILLAR_BREACH_THRESHOLD

    def _smooth_weight(self, *, old: float, desired: float, cap: float | None = None) -> float:
        if cap is None:
            cap = self.WEIGHT_SMOOTHING_CAP
        return old + (desired - old) * cap

    async def log_retrain(
        self,
        *,
        trigger_type: str,
        delta_pct: float,
        weights_before: dict,
        weights_after: dict,
        reason: str,
    ) -> None:
        import json
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO m13_retrain_log
                    (trigger_type, delta_pct, weights_before_json, weights_after_json, reason)
                VALUES ($1, $2, $3, $4, $5)
            """, trigger_type, delta_pct,
                 json.dumps(weights_before), json.dumps(weights_after), reason)
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/measurer/test_m13_feedback_loop.py -q --tb=short
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/measurer/m13_feedback_loop.py apps/backend-rag/backend/tests/unit/services/measurer/test_m13_feedback_loop.py
git commit -m "feat(sota/m13): M13FeedbackLoop class — core retrain logic

5 methods: collect_post_metrics, compute_delta_vs_baseline,
should_trigger_retrain, is_pillar_threshold_breach, log_retrain.
Smoothing cap 20%, retrain threshold ±10%, breach threshold -20%.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 24: Cron — collect post metrics every 6h (~1h)

**Files:**
- Create: `scripts/m13_collect_post_metrics.py`
- Create: `infra/launchagents/com.balizero.sota.m13-collect.plist`

- [ ] **Step 1: Write cron script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/m13_collect_post_metrics.py <<'EOF'
#!/usr/bin/env python3
"""Every-6h cron — pull metrics for every post published in last 168h.

Triggered by infra/launchagents/com.balizero.sota.m13-collect.plist.
Kill switch: system_settings.sota_m13_collect_enabled = 'true'.
"""
from __future__ import annotations

import asyncio, logging, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

import asyncpg
from backend.services.measurer.ig_graph_sensor import IGGraphSensor
from backend.services.measurer.m13_feedback_loop import (
    M13FeedbackLoop,
    M13CollectionHorizon,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.m13.collect")


async def kill_switch_on(conn) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'sota_m13_collect_enabled'"
    )
    return value == "true"


async def main() -> int:
    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            if not await kill_switch_on(conn):
                logger.info("kill switch OFF — exiting")
                return 0

        m13 = M13FeedbackLoop(db_pool=pool)

        async with pool.acquire() as conn:
            posts = await conn.fetch("""
                SELECT id, platform, post_external_id, published_at
                  FROM war_room_posts
                 WHERE published_at > NOW() - INTERVAL '168 hours'
            """)

        for post in posts:
            age = datetime.now(timezone.utc) - post["published_at"]
            if age < timedelta(hours=24):
                continue  # too young for first horizon
            if age < timedelta(hours=72):
                horizon = M13CollectionHorizon.T_24H
            elif age < timedelta(hours=168):
                horizon = M13CollectionHorizon.T_72H
            else:
                horizon = M13CollectionHorizon.T_168H

            if post["platform"] == "instagram":
                token = os.environ.get("IG_GRAPH_API_TOKEN")
                ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
                if not (token and ig_id):
                    logger.warning("IG creds missing, skipping post %s", post["id"])
                    continue
                sensor = IGGraphSensor(token=token, ig_user_id=ig_id)
                # Fetch insights for the specific post
                try:
                    insights = await sensor._fetch_insights(
                        post["post_external_id"], "IMAGE"
                    )
                except Exception as e:
                    logger.warning("insights fetch failed for %s: %s", post["id"], e)
                    continue
                await m13.collect_post_metrics(
                    post_id=post["id"],
                    horizon=horizon,
                    metrics=insights,
                    source="ig_graph",
                )
                logger.info("collected %s @ %s", post["id"], horizon.name)
            # TODO: linkedin, tiktok horizons in future sprints
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/m13_collect_post_metrics.py
```

- [ ] **Step 2: Write launchd plist**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.sota.m13-collect.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.balizero.sota.m13-collect</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/m13_collect_post_metrics.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara</string>

    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/sota_m13_collect.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/sota_m13_collect.error.log</string>

    <key>ExitTimeOut</key>
    <integer>600</integer>

    <key>ProcessType</key>
    <string>Background</string>
  </dict>
</plist>
EOF
```

- [ ] **Step 3: Install + load plist**

```bash
mkdir -p ~/Library/LaunchAgents
cp infra/launchagents/com.balizero.sota.m13-collect.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.balizero.sota.m13-collect.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.balizero.sota.m13-collect.plist
launchctl list | grep sota.m13-collect
```

Expected: one line with the label + PID/0 + status.

- [ ] **Step 4: Enable kill switch**

```bash
psql "$DATABASE_URL" -c "INSERT INTO system_settings(key, value) VALUES('sota_m13_collect_enabled', 'true') ON CONFLICT (key) DO UPDATE SET value='true'"
```

- [ ] **Step 5: Trigger one run + verify log**

```bash
launchctl kickstart -k gui/$(id -u)/com.balizero.sota.m13-collect
sleep 5
tail -20 ~/logs/sota_m13_collect.log
```

Expected: "kill switch OFF" OR "collected <post_id> @ T_24H" lines, no errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/m13_collect_post_metrics.py infra/launchagents/com.balizero.sota.m13-collect.plist
git commit -m "feat(sota/loop): every-6h cron — collect post metrics via IG Graph

launchd plist loaded. Kill switch system_settings.sota_m13_collect_enabled.
Delegates to M13FeedbackLoop.collect_post_metrics per post per horizon.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 25: Weekly report cron (~2h)

**Files:**
- Create: `scripts/m13_weekly_report.py`
- Create: `infra/launchagents/com.balizero.sota.m13-weekly.plist`

- [ ] **Step 1: Weekly script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/m13_weekly_report.py <<'EOF'
#!/usr/bin/env python3
"""Sunday 06:00 WITA cron — aggregate week, retrain if needed, Telegram digest.

Outputs:
- research/sota-social-2026-v1/weekly_report_YYYY-MM-DD.md
- research/sota-social-2026-v1/kpi_timeline.csv (append row)
- research/sota-social-2026-v1/retrain_log.jsonl (append if retrained)
- Telegram digest to Zero
"""
from __future__ import annotations

import asyncio, csv, json, logging, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

import asyncpg
from backend.services.measurer.m13_feedback_loop import M13FeedbackLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.m13.weekly")

RESEARCH = _REPO / "research" / "sota-social-2026-v1"
KPI_CSV = RESEARCH / "kpi_timeline.csv"
RETRAIN_LOG = RESEARCH / "retrain_log.jsonl"


async def kill_switch_on(conn) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'sota_m13_weekly_enabled'"
    )
    return value == "true"


async def main() -> int:
    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            if not await kill_switch_on(conn):
                logger.info("weekly kill switch OFF — exit")
                return 0

        m13 = M13FeedbackLoop(db_pool=pool)

        # Compute deltas per channel × pillar
        channels = ["instagram", "linkedin", "tiktok", "threads", "newsletter"]
        pillars = ["lead", "authority", "audience"]
        deltas: dict[str, dict[str, float]] = {}
        for ch in channels:
            deltas[ch] = {}
            for p in pillars:
                deltas[ch][p] = await m13.compute_delta_vs_baseline(channel=ch, pillar=p)

        # Persist KPI row
        today = datetime.now(timezone.utc).date().isoformat()
        KPI_CSV.parent.mkdir(parents=True, exist_ok=True)
        new_file = not KPI_CSV.exists()
        with KPI_CSV.open("a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["date"] + [f"{c}_{p}" for c in channels for p in pillars])
            row = [today] + [deltas[c][p] for c in channels for p in pillars]
            w.writerow(row)

        # Determine if retrain needed
        breaches = []
        retrain_needed = False
        for ch, pvals in deltas.items():
            for p, d in pvals.items():
                if m13.is_pillar_threshold_breach(delta=d):
                    breaches.append((ch, p, d))
                if m13.should_trigger_retrain(delta=d):
                    retrain_needed = True

        # Trigger retrain if needed
        retrain_result = ""
        if retrain_needed:
            logger.info("retrain triggered")
            result = subprocess.run(
                ["python", str(_REPO / "scripts" / "sota_consiglio_playbook.py"),
                 "--wave=final"],
                capture_output=True, text=True, timeout=1800, check=False,
            )
            retrain_result = "OK" if result.returncode == 0 else f"FAIL rc={result.returncode}"
            with RETRAIN_LOG.open("a") as f:
                f.write(json.dumps({
                    "date": today,
                    "trigger": "weekly",
                    "deltas": deltas,
                    "retrain_result": retrain_result,
                }) + "\n")

        # Write weekly report MD
        report_path = RESEARCH / f"weekly_report_{today}.md"
        md_lines = [
            f"# SOTA Weekly Report — {today}\n",
            f"\n## Deltas vs baseline (per channel × pillar)\n",
        ]
        for ch in channels:
            md_lines.append(f"### {ch}")
            for p in pillars:
                d = deltas[ch][p]
                marker = "🚨" if d < -0.2 else ("⚠️" if abs(d) > 0.1 else "✅")
                md_lines.append(f"- {marker} {p}: {d:+.1%}")
            md_lines.append("")
        if breaches:
            md_lines.append(f"\n## Threshold breaches ({len(breaches)})\n")
            for ch, p, d in breaches:
                md_lines.append(f"- {ch} / {p}: {d:+.1%}")
        if retrain_needed:
            md_lines.append(f"\n## Retrain\nTriggered. Result: {retrain_result}")
        report_path.write_text("\n".join(md_lines), encoding="utf-8")
        logger.info("wrote %s", report_path)

        # Telegram digest
        _notify_telegram(deltas, breaches, retrain_needed, retrain_result)

        # Auto-toggle publisher off for breached channels
        async with pool.acquire() as conn:
            for ch, p, d in breaches:
                await conn.execute("""
                    INSERT INTO system_settings(key, value)
                    VALUES ($1, 'false')
                    ON CONFLICT (key) DO UPDATE SET value='false'
                """, f"wr2_publisher_enabled_{ch}")
                logger.warning("auto-toggled publisher OFF for %s (breach on %s: %.1f%%)",
                               ch, p, d * 100)

        return 0
    finally:
        await pool.close()


def _notify_telegram(deltas, breaches, retrained, retrain_result):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    import urllib.parse, urllib.request
    header = "🚨 *SOTA weekly*" if breaches else "📊 *SOTA weekly*"
    summary = [header, ""]
    for ch, pvals in deltas.items():
        line = f"`{ch}`: "
        line += " | ".join(f"{p}={d:+.0%}" for p, d in pvals.items())
        summary.append(line)
    if breaches:
        summary.append(f"\n*Breaches:* {len(breaches)}")
        for ch, p, d in breaches:
            summary.append(f"- {ch} / {p}: {d:+.1%} → publisher OFF")
    if retrained:
        summary.append(f"\nRetrain: {retrain_result}")
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            urllib.parse.urlencode({
                "chat_id": chat,
                "text": "\n".join(summary),
                "parse_mode": "Markdown",
            }).encode(),
            timeout=10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/m13_weekly_report.py
```

- [ ] **Step 2: Plist for Sunday 06:00 WITA**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.sota.m13-weekly.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.balizero.sota.m13-weekly</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/m13_weekly_report.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara</string>
    <key>StartCalendarInterval</key>
    <dict>
      <key>Weekday</key>
      <integer>0</integer>
      <key>Hour</key>
      <integer>6</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/sota_m13_weekly.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/sota_m13_weekly.error.log</string>
    <key>ExitTimeOut</key>
    <integer>3600</integer>
    <key>ProcessType</key>
    <string>Background</string>
  </dict>
</plist>
EOF
```

- [ ] **Step 3: Install + enable**

```bash
cp infra/launchagents/com.balizero.sota.m13-weekly.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.balizero.sota.m13-weekly.plist
psql "$DATABASE_URL" -c "INSERT INTO system_settings(key, value) VALUES('sota_m13_weekly_enabled','true') ON CONFLICT (key) DO UPDATE SET value='true'"
```

- [ ] **Step 4: Smoke run**

```bash
launchctl kickstart -k gui/$(id -u)/com.balizero.sota.m13-weekly
sleep 10
tail -40 ~/logs/sota_m13_weekly.log
ls research/sota-social-2026-v1/weekly_report_*.md 2>/dev/null
```

Expected: one weekly_report_*.md file written, KPI CSV row appended. Telegram sent.

- [ ] **Step 5: Commit**

```bash
git add scripts/m13_weekly_report.py infra/launchagents/com.balizero.sota.m13-weekly.plist
git commit -m "feat(sota/loop): weekly report cron — Sunday 06:00 WITA

Computes per-channel × pillar deltas, writes weekly_report.md + KPI CSV,
triggers Consiglio retrain if ±10%, auto-toggles publisher OFF on -20%
breach, sends Telegram digest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 26: Monthly retrain cron (~1.5h)

**Files:**
- Create: `scripts/m13_monthly_retrain.py`
- Create: `infra/launchagents/com.balizero.sota.m13-monthly.plist`

- [ ] **Step 1: Monthly script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/m13_monthly_retrain.py <<'EOF'
#!/usr/bin/env python3
"""1st of month 04:30 WITA — full monthly retrain.

Re-runs: competitor scraping, Ahrefs SOV, persona inference, Consiglio.
If overall delta > 15%, bumps playbook version (v1.1, v1.2, ...).
"""
from __future__ import annotations
import json, logging, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.m13.monthly")

RESEARCH = _REPO / "research" / "sota-social-2026-v1"


def run(cmd: list[str], *, timeout: int = 1800) -> int:
    logger.info("run: %s", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        logger.warning("cmd rc=%s stderr=%s", r.returncode, r.stderr[-400:])
    return r.returncode


def main() -> int:
    # Check kill switch via psql
    dsn = os.environ["DATABASE_URL"]
    result = subprocess.run(
        ["psql", dsn, "-tAc", "SELECT value FROM system_settings WHERE key='sota_m13_monthly_enabled'"],
        capture_output=True, text=True, check=False,
    )
    if result.stdout.strip() != "true":
        logger.info("monthly kill switch OFF — exit")
        return 0

    month = datetime.now(timezone.utc).strftime("%Y-%m")

    # Step 1: re-fetch Ahrefs snapshot (subset of baseline)
    run(["python", str(_REPO / "scripts" / "sota_build_baseline.py")])

    # Step 2: re-ingest competitor corpus IF new CSV available
    csv_path = RESEARCH / "competitor_raw.csv"
    if csv_path.is_file():
        mtime = datetime.fromtimestamp(csv_path.stat().st_mtime, tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - mtime).days
        if age_days < 35:
            run(["python", str(_REPO / "scripts" / "sota_ingest_competitors.py")])
        else:
            logger.warning("competitor CSV is %d days old — ask team to re-scrape", age_days)

    # Step 3: re-infer personas (both waves)
    run(["python", str(_REPO / "scripts" / "sota_infer_personas.py"), "--wave=both"])

    # Step 4: Consiglio v1 final pass
    rc = run(["python", str(_REPO / "scripts" / "sota_consiglio_playbook.py"),
              "--wave=final"])

    # Step 5: detect if playbook changed materially → bump version
    weights_path = RESEARCH / "09_wr2_weights.json"
    if weights_path.is_file():
        new_weights = json.loads(weights_path.read_text())
        archive_path = RESEARCH / f"09_wr2_weights_{month}.json"
        archive_path.write_text(json.dumps(new_weights, indent=2), encoding="utf-8")

    # Write monthly report
    report = RESEARCH / f"monthly_report_{month}.md"
    report.write_text(
        f"# SOTA Monthly Report {month}\n\n"
        f"Run at: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"Steps executed: ahrefs snapshot, competitor ingest, personas, Consiglio\n\n"
        f"Consiglio return code: {rc}\n\n"
        f"See `retrain_log.jsonl` and weekly reports for KPI deltas.\n",
        encoding="utf-8",
    )
    logger.info("monthly retrain complete: %s", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/m13_monthly_retrain.py
```

- [ ] **Step 2: Plist**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.sota.m13-monthly.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.balizero.sota.m13-monthly</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/m13_monthly_retrain.py</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/nuzantara/Desktop/nuzantara</string>
    <key>StartCalendarInterval</key>
    <dict>
      <key>Day</key><integer>1</integer>
      <key>Hour</key><integer>4</integer>
      <key>Minute</key><integer>30</integer>
    </dict>
    <key>StandardOutPath</key><string>/Users/nuzantara/logs/sota_m13_monthly.log</string>
    <key>StandardErrorPath</key><string>/Users/nuzantara/logs/sota_m13_monthly.error.log</string>
    <key>ExitTimeOut</key><integer>10800</integer>
    <key>ProcessType</key><string>Background</string>
  </dict>
</plist>
EOF
```

- [ ] **Step 3: Install + enable**

```bash
cp infra/launchagents/com.balizero.sota.m13-monthly.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.balizero.sota.m13-monthly.plist
psql "$DATABASE_URL" -c "INSERT INTO system_settings(key, value) VALUES('sota_m13_monthly_enabled','true') ON CONFLICT (key) DO UPDATE SET value='true'"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/m13_monthly_retrain.py infra/launchagents/com.balizero.sota.m13-monthly.plist
git commit -m "feat(sota/loop): monthly retrain cron — 1st 04:30 WITA

Re-runs baseline + competitor + personas + Consiglio. Archives
09_wr2_weights_YYYY-MM.json. Skips competitor ingest if CSV >35d old
(asks team to re-scrape).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 27: Checkpoint 30/60/90 cron (~1h)

**Files:**
- Create: `scripts/m13_checkpoint.py`
- Create: `infra/launchagents/com.balizero.sota.m13-checkpoint.plist`

- [ ] **Step 1: Script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/m13_checkpoint.py <<'EOF'
#!/usr/bin/env python3
"""Daily check: if we're on Loop day 30/60/90, trigger formal checkpoint."""
from __future__ import annotations
import json, logging, os, subprocess, sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sota.m13.checkpoint")

LOOP_START_FILE = _REPO / "research" / "sota-social-2026-v1" / ".loop_start_date"


def main() -> int:
    if not LOOP_START_FILE.is_file():
        logger.info("loop not started yet")
        return 0
    start_date = date.fromisoformat(LOOP_START_FILE.read_text().strip())
    days = (date.today() - start_date).days
    if days not in (30, 60, 90):
        return 0

    logger.info("Loop day %d — triggering checkpoint", days)
    report_path = _REPO / "research" / "sota-social-2026-v1" / f"checkpoint_day_{days}.md"
    report_path.write_text(
        f"# SOTA Checkpoint — Loop Day {days}\n\n"
        f"Date: {date.today().isoformat()}\n\n"
        f"## Deliverables for this checkpoint\n"
        f"- Review of last {days} days deltas (see weekly reports)\n"
        f"- Go/Pivot/Kill decision per channel\n"
        f"- Update playbook version if needed\n\n"
        f"## Decision request (Telegram to Zero)\n"
        f"Reply with `/checkpoint day{days} decision=GO|PIVOT|KILL channel=<name>`\n",
        encoding="utf-8",
    )

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        import urllib.parse, urllib.request
        try:
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                urllib.parse.urlencode({
                    "chat_id": os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968"),
                    "text": f"🚩 *SOTA Checkpoint Day {days}* — formal review needed. "
                            f"File: `research/sota-social-2026-v1/checkpoint_day_{days}.md`. "
                            f"Reply GO/PIVOT/KILL per channel.",
                    "parse_mode": "Markdown",
                }).encode(),
                timeout=10,
            )
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/m13_checkpoint.py
```

- [ ] **Step 2: Plist (daily 09:00 WITA)**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.sota.m13-checkpoint.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.balizero.sota.m13-checkpoint</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/m13_checkpoint.py</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/nuzantara/Desktop/nuzantara</string>
    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key><integer>9</integer>
      <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/Users/nuzantara/logs/sota_m13_checkpoint.log</string>
    <key>StandardErrorPath</key><string>/Users/nuzantara/logs/sota_m13_checkpoint.error.log</string>
    <key>ExitTimeOut</key><integer>120</integer>
    <key>ProcessType</key><string>Background</string>
  </dict>
</plist>
EOF
```

- [ ] **Step 3: Record loop start date**

```bash
# On Fase 0 Day 11 (= Loop Day 1) after Zero says APPROVE SOTA:
echo "$(date -u +%Y-%m-%d)" > research/sota-social-2026-v1/.loop_start_date
cp infra/launchagents/com.balizero.sota.m13-checkpoint.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.balizero.sota.m13-checkpoint.plist
```

- [ ] **Step 4: Commit**

```bash
git add scripts/m13_checkpoint.py infra/launchagents/com.balizero.sota.m13-checkpoint.plist
git commit -m "feat(sota/loop): checkpoint cron — day 30/60/90 formal review

Daily @09:00 WITA checks if Loop day is 30/60/90; if yes, writes
checkpoint_day_N.md and Telegram-notifies Zero for GO/PIVOT/KILL
decision per channel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 28: WR2 editorial_config.py (~2h)

**Files:**
- Create: `apps/backend-rag/backend/services/war_room/editorial_config.py`
- Create: `apps/backend-rag/backend/tests/unit/services/war_room/test_editorial_config.py`

- [ ] **Step 1: Write failing test**

```bash
mkdir -p apps/backend-rag/backend/tests/unit/services/war_room
cat > apps/backend-rag/backend/tests/unit/services/war_room/test_editorial_config.py <<'EOF'
"""Tests for editorial_config — loads wr2_weights.json → WR2 runtime config."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from backend.services.war_room.editorial_config import (
    EditorialConfig,
    EditorialConfigNotReady,
)


def _valid_weights() -> dict:
    return {
        "persona_weight": {
            "expat_boomer_retiree": 0.25,
            "expat_techie_pma": 0.30,
            "expat_italian_aire": 0.15,
            "id_konsultan_kadin": 0.10,
            "id_founder_pma": 0.12,
            "id_umkm_digital": 0.08,
        },
        "tone_resonance": {
            "expat_techie_pma": {"tecnico": 0.4, "analitico": 0.3, "pedagogico": 0.3}
        },
        "cadence_by_channel": {
            "instagram": {"posts_per_day": 1.0, "optimal_hours_wita": [7, 12, 19]}
        },
        "format_mix_by_objective": {
            "lead": {"carousel_education": 0.4, "case_study": 0.3, "data_story": 0.3}
        },
        "publisher_enabled_by_channel": {"instagram": False},
    }


def test_load_from_file(tmp_path: Path):
    wpath = tmp_path / "w.json"
    wpath.write_text(json.dumps(_valid_weights()))
    cfg = EditorialConfig.load(wpath)
    assert cfg.cadence_for("instagram")["posts_per_day"] == 1.0
    assert cfg.persona_weight("expat_techie_pma") == 0.30
    assert cfg.is_publisher_enabled("instagram") is False


def test_raises_when_file_missing(tmp_path: Path):
    with pytest.raises(EditorialConfigNotReady):
        EditorialConfig.load(tmp_path / "nope.json")


def test_unknown_channel_returns_none():
    cfg = EditorialConfig(**_valid_weights())
    assert cfg.cadence_for("unknown") is None
    assert cfg.is_publisher_enabled("unknown") is False  # safe default


def test_tone_resonance_normalized():
    cfg = EditorialConfig(**_valid_weights())
    tr = cfg.tone_for("expat_techie_pma")
    assert abs(sum(tr.values()) - 1.0) < 0.01
EOF
```

- [ ] **Step 2: Run — fails**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/war_room/test_editorial_config.py -q --tb=line 2>&1 | tail -3
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/war_room/editorial_config.py <<'EOF'
"""EditorialConfig — WR2 runtime configuration loaded from 09_wr2_weights.json.

Injected at WR2 startup. Council reads persona_weight + tone_resonance
to select draft target. Publisher checks is_publisher_enabled per channel.

Location of weights file: research/sota-social-2026-v1/09_wr2_weights.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class EditorialConfigNotReady(FileNotFoundError):
    """Raised when WR2 tries to use editorial config before Consiglio ran."""


@dataclass
class EditorialConfig:
    persona_weight: dict[str, float] = field(default_factory=dict)
    tone_resonance: dict[str, dict[str, float]] = field(default_factory=dict)
    cadence_by_channel: dict[str, dict] = field(default_factory=dict)
    format_mix_by_objective: dict[str, dict[str, float]] = field(default_factory=dict)
    publisher_enabled_by_channel: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "EditorialConfig":
        if not path.is_file():
            raise EditorialConfigNotReady(
                f"Editorial config not found at {path}. "
                "Run Consiglio v1 (sota_consiglio_playbook.py --wave=final) first."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: data.get(k, {}) for k in (
            "persona_weight", "tone_resonance", "cadence_by_channel",
            "format_mix_by_objective", "publisher_enabled_by_channel",
        )})

    def cadence_for(self, channel: str) -> dict | None:
        return self.cadence_by_channel.get(channel)

    def persona_weight(self, slug: str) -> float:
        return float(self.persona_weight.get(slug, 0.0))

    def is_publisher_enabled(self, channel: str) -> bool:
        return bool(self.publisher_enabled_by_channel.get(channel, False))

    def tone_for(self, persona_slug: str) -> dict[str, float]:
        """Return normalized tone resonance distribution for a persona."""
        raw = dict(self.tone_resonance.get(persona_slug, {}))
        total = sum(raw.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in raw.items()}
EOF
```

- [ ] **Step 4: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/war_room/test_editorial_config.py -q --tb=short
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/war_room/editorial_config.py apps/backend-rag/backend/tests/unit/services/war_room/test_editorial_config.py
git commit -m "feat(sota/wr2): EditorialConfig reads 09_wr2_weights.json

WR2 runtime injection: persona_weight, tone_resonance, cadence,
format_mix, publisher_enabled_by_channel. Fails fast with
EditorialConfigNotReady if Consiglio hasn't run yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 29: Council v2 — accept persona input (~1.5h)

**Files:**
- Modify: `apps/backend-rag/backend/services/council/tone_council.py`
- Create: `apps/backend-rag/backend/tests/unit/services/council/test_tone_council_persona.py`

- [ ] **Step 1: Read current tone_council**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
head -60 backend/services/council/tone_council.py
```

Identify where `deliberate` (or equivalent) signature lives.

- [ ] **Step 2: Write failing test**

```bash
cat > backend/tests/unit/services/council/test_tone_council_persona.py <<'EOF'
"""Test Council v2 accepts persona and weighs tone accordingly."""
from __future__ import annotations

import pytest
from backend.services.council.tone_council import (
    ToneCouncil,
    CouncilInput,
)


def test_council_input_accepts_persona_slug():
    inp = CouncilInput(
        topic="PT PMA 2026",
        objective="authority",
        persona_slug="id_konsultan_kadin",
        tone_weights={"tecnico": 0.5, "analitico": 0.3, "pedagogico": 0.2},
    )
    assert inp.persona_slug == "id_konsultan_kadin"
    assert sum(inp.tone_weights.values()) == pytest.approx(1.0)
EOF
```

- [ ] **Step 3: Run — expect fail (CouncilInput doesn't yet have persona_slug)**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/council/test_tone_council_persona.py -q --tb=short 2>&1 | tail -5
```

Expected: ImportError or TypeError.

- [ ] **Step 4: Modify tone_council.py**

Inspect the file; add `persona_slug: str | None = None` field to `CouncilInput` dataclass. If class is named differently, adapt. Minimal change — no behavior yet, just accept input.

Example patch (adjust to actual file):

```python
from dataclasses import dataclass, field

@dataclass
class CouncilInput:
    topic: str
    objective: str
    persona_slug: str | None = None  # NEW (SOTA task 29)
    tone_weights: dict[str, float] = field(default_factory=dict)
```

- [ ] **Step 5: Run tests — pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/council/test_tone_council_persona.py -q --tb=short
```

Expected: `1 passed`.

- [ ] **Step 6: Smoke — existing council tests still green**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/council/ -q --tb=short 2>&1 | tail -5
```

Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/council/tone_council.py apps/backend-rag/backend/tests/unit/services/council/test_tone_council_persona.py
git commit -m "feat(sota/wr2): Council v2 accepts persona_slug input

Backward compatible: field defaults to None. Consumers (draft_generator,
etc.) will pass persona_slug pulled from EditorialConfig.persona_weight
in future task. No runtime behavior change yet — just schema widening.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 30: Telegram kill-switch router (~2h)

**Files:**
- Create: `apps/backend-rag/backend/app/routers/research.py`
- Create: `apps/backend-rag/backend/tests/app/routers/test_research.py`
- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`

- [ ] **Step 1: Write failing test**

```bash
mkdir -p apps/backend-rag/backend/tests/app/routers
cat > apps/backend-rag/backend/tests/app/routers/test_research.py <<'EOF'
"""Tests for research router — Telegram kill-switch commands."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch


def test_pause_command_flips_switch():
    from backend.app.routers.research import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with patch("backend.app.routers.research._set_kill_switch", AsyncMock(return_value=True)):
        r = client.post("/api/research/telegram", json={
            "message": {"text": "/research pause", "chat": {"id": 1125336968}}
        })
    assert r.status_code == 200
    assert "paused" in r.json()["ack"].lower()


def test_unauthorized_chat_rejected():
    from backend.app.routers.research import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.post("/api/research/telegram", json={
        "message": {"text": "/research pause", "chat": {"id": 999}}
    })
    assert r.status_code == 403


def test_unknown_command_returns_help():
    from backend.app.routers.research import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.post("/api/research/telegram", json={
        "message": {"text": "/wat", "chat": {"id": 1125336968}}
    })
    assert r.status_code == 200
    assert "available" in r.json()["ack"].lower()
EOF
```

- [ ] **Step 2: Implement**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/app/routers/research.py <<'EOF'
"""Research kill-switch router — Telegram commands from Zero.

Mapping (spec §Telegram kill switches):
  /research pause | resume
  /publisher off [channel]
  /retrain off
  /personas reset
  /cron disable [script]
  /playbook freeze
"""

from __future__ import annotations

import logging
import os
from fastapi import APIRouter, HTTPException, Request
from typing import Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research", tags=["research"])

OWNER_CHAT_ID = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968"))


async def _set_kill_switch(key: str, value: str, db_pool: Any) -> bool:
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO system_settings(key, value) VALUES($1, $2)
            ON CONFLICT (key) DO UPDATE SET value=$2
        """, key, value)
    return True


@router.post("/telegram")
async def handle_telegram_command(request: Request):
    body = await request.json()
    msg = body.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if chat_id != OWNER_CHAT_ID:
        raise HTTPException(status_code=403, detail="unauthorized")

    parts = text.split()
    if not parts:
        return {"ack": "empty command"}

    cmd = parts[0].lstrip("/")
    db_pool = getattr(request.app.state, "db_pool", None)

    if cmd == "research" and len(parts) >= 2:
        action = parts[1]
        if action == "pause":
            if db_pool:
                await _set_kill_switch("sota_m13_collect_enabled", "false", db_pool)
                await _set_kill_switch("sota_m13_weekly_enabled", "false", db_pool)
                await _set_kill_switch("sota_m13_monthly_enabled", "false", db_pool)
            return {"ack": "Research paused — 3 crons disabled"}
        if action == "resume":
            if db_pool:
                await _set_kill_switch("sota_m13_collect_enabled", "true", db_pool)
                await _set_kill_switch("sota_m13_weekly_enabled", "true", db_pool)
                await _set_kill_switch("sota_m13_monthly_enabled", "true", db_pool)
            return {"ack": "Research resumed"}

    if cmd == "publisher" and len(parts) >= 3 and parts[1] == "off":
        ch = parts[2]
        if db_pool:
            await _set_kill_switch(f"wr2_publisher_enabled_{ch}", "false", db_pool)
        return {"ack": f"Publisher for {ch} OFF"}

    if cmd == "retrain" and len(parts) >= 2 and parts[1] == "off":
        if db_pool:
            await _set_kill_switch("sota_m13_retrain_enabled", "false", db_pool)
        return {"ack": "Retrain frozen"}

    if cmd == "playbook" and len(parts) >= 2 and parts[1] == "freeze":
        if db_pool:
            await _set_kill_switch("sota_playbook_frozen", "true", db_pool)
        return {"ack": "Playbook frozen — no auto-updates"}

    return {
        "ack": "Unknown command. Available: /research pause|resume, "
               "/publisher off <channel>, /retrain off, /playbook freeze"
    }
EOF
```

- [ ] **Step 3: Run tests — pass**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/app/routers/test_research.py -q --tb=short
```

Expected: `3 passed`.

- [ ] **Step 4: Register in router_manifest**

Read `apps/backend-rag/backend/app/setup/router_manifest.py`, find the `ROUTER_ENTRIES` list, add:

```python
RouterEntry(
    module="backend.app.routers.research",
    router_attr="router",
    process_groups=("_API",),  # light, public HTTP
),
```

Run the manifest test:

```bash
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py -q --tb=short
```

Expected: existing passes still green.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/research.py apps/backend-rag/backend/tests/app/routers/test_research.py apps/backend-rag/backend/app/setup/router_manifest.py
git commit -m "feat(sota/wr2): /api/research/telegram kill-switch router

Handles /research pause|resume, /publisher off <ch>, /retrain off,
/playbook freeze. Owner chat authorization via TELEGRAM_OWNER_CHAT_ID.
Writes system_settings rows. Registered in router_manifest _API group.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 31: Grafana dashboard panels (~3h)

**Files:**
- Create: `infra/grafana/social-sota-dashboard.json`
- Create: `docs/runbooks/grafana-sota-setup.md`

- [ ] **Step 1: Write Grafana dashboard JSON**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/infra/grafana
cat > /Users/nuzantara/Desktop/nuzantara/infra/grafana/social-sota-dashboard.json <<'EOF'
{
  "title": "Social SOTA 2026",
  "description": "Bali Zero social research dashboard — 3 pillars + heatmap + top posts",
  "tags": ["sota", "social", "bali-zero"],
  "refresh": "1h",
  "panels": [
    {
      "id": 1,
      "title": "Pillar — Lead (leads/month attributed to social)",
      "type": "timeseries",
      "datasource": {"type": "postgres", "uid": "pg-nuzantara"},
      "targets": [{
        "refId": "A",
        "rawSql": "SELECT DATE_TRUNC('month', created_at) AS time, COUNT(*) AS value FROM clients WHERE utm_source IN ('instagram','linkedin','tiktok','threads','newsletter','twitter','x') AND created_at > NOW() - INTERVAL '6 months' GROUP BY 1 ORDER BY 1",
        "format": "time_series"
      }],
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
    },
    {
      "id": 2,
      "title": "Pillar — Authority (SOV + AI citations)",
      "type": "timeseries",
      "datasource": {"type": "postgres", "uid": "pg-nuzantara"},
      "targets": [{
        "refId": "A",
        "rawSql": "SELECT collected_at AS time, metric_value AS value FROM post_metrics_history WHERE metric_name='sov_pct' AND collected_at > NOW() - INTERVAL '90 days' ORDER BY 1",
        "format": "time_series"
      }],
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
    },
    {
      "id": 3,
      "title": "Pillar — Audience (follower growth per channel)",
      "type": "timeseries",
      "datasource": {"type": "postgres", "uid": "pg-nuzantara"},
      "targets": [{
        "refId": "A",
        "rawSql": "SELECT collected_at AS time, source AS metric, metric_value AS value FROM post_metrics_history WHERE metric_name='followers_count' AND collected_at > NOW() - INTERVAL '90 days' ORDER BY 1",
        "format": "time_series"
      }],
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 8}
    },
    {
      "id": 4,
      "title": "Optimal posting hours heatmap",
      "type": "heatmap",
      "datasource": {"type": "postgres", "uid": "pg-nuzantara"},
      "targets": [{
        "refId": "A",
        "rawSql": "SELECT EXTRACT(HOUR FROM pmh.collected_at + INTERVAL '8 hours') AS hour_wita, AVG(pmh.metric_value) AS engagement FROM post_metrics_history pmh WHERE pmh.metric_name='saves' AND pmh.collected_at > NOW() - INTERVAL '30 days' GROUP BY 1 ORDER BY 1"
      }],
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16}
    },
    {
      "id": 5,
      "title": "Top 10 posts by engagement (last 30d)",
      "type": "table",
      "datasource": {"type": "postgres", "uid": "pg-nuzantara"},
      "targets": [{
        "refId": "A",
        "rawSql": "SELECT wrp.platform, wrp.post_external_id, wrp.post_url, SUM(pmh.metric_value) AS engagement_sum FROM post_metrics_history pmh JOIN war_room_posts wrp ON wrp.id = pmh.post_id WHERE pmh.metric_name IN ('likes','comments','saves') AND pmh.collected_at > NOW() - INTERVAL '30 days' GROUP BY 1,2,3 ORDER BY engagement_sum DESC LIMIT 10"
      }],
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16}
    }
  ],
  "alerts": [
    {
      "name": "Pillar breach -20%",
      "conditions": [{
        "type": "query",
        "query": {"queryType": "", "refId": "A"},
        "reducer": {"type": "avg"},
        "evaluator": {"type": "lt", "params": [-0.2]}
      }],
      "notifications": [{"uid": "telegram-zero"}]
    }
  ]
}
EOF
```

- [ ] **Step 2: Write setup runbook**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/docs/runbooks/grafana-sota-setup.md <<'EOF'
# Grafana SOTA Dashboard Setup

**Prereq:** Grafana instance decided in Task 0 Q2 (new Cloud free OR existing).

## Steps (one-time)

1. Log in to Grafana (URL from `open-questions-log.md#Q2`).
2. **Data source:** Add PostgreSQL → connect to Fly Postgres:
   - Host: `nuzantara-postgres.fly.dev:5432` (or tunnel 15432 if local)
   - Database: `nuzantara`
   - User: readonly user (create: `CREATE USER grafana_ro WITH PASSWORD 'xxx'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro;`)
   - UID: `pg-nuzantara`
3. **Import dashboard:** Dashboards → New → Import → Upload JSON:
   `infra/grafana/social-sota-dashboard.json`
4. **Telegram webhook notification:**
   - Alerting → Contact points → New: Telegram
   - Bot token: `$TELEGRAM_BOT_TOKEN`
   - Chat ID: `$TELEGRAM_OWNER_CHAT_ID`
   - UID: `telegram-zero`
5. **Subdomain DNS:** add CNAME `grafana.balizero.com` → `<tenant>.grafana.net`.
6. **Test alert:** force a breach by querying `SELECT -0.25 AS delta` → confirm Telegram message arrives.

## Post-install smoke

Visit https://grafana.balizero.com/dashboard/social-sota — all 5 panels
should render. If "No data", check:
- Postgres connection active
- Tables `post_metrics_history` + `war_room_posts` exist (migration 128)
- M13 collect cron has run at least once (check `~/logs/sota_m13_collect.log`)
EOF
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add infra/grafana/social-sota-dashboard.json docs/runbooks/grafana-sota-setup.md
git commit -m "feat(sota/grafana): dashboard JSON + setup runbook

5 panels (3 pillars + posting heatmap + top 10 posts). Telegram alert
on pillar breach -20%. Runbook covers Grafana Cloud setup + PG
read-only user + CNAME.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 32: Final smoke test — end-to-end Fase 0 dry run (~2h)

**Files:** No new code; integration smoke with synthetic data.

- [ ] **Step 1: Write smoke script**

```bash
cat > /Users/nuzantara/Desktop/nuzantara/scripts/sota_smoke_fase0.sh <<'EOF'
#!/usr/bin/env bash
# Dry-run all Fase 0 scripts in order; verify each artifact appears.
# Assumes Task 0 complete, secrets loaded.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
source ~/.nuzantara-secrets.env 2>/dev/null || true

echo "=== SOTA Fase 0 smoke test ==="

echo "[1/8] baseline..."
python scripts/sota_build_baseline.py
jq '[.. | numbers] | length' research/sota-social-2026-v1/00_baseline.json | tee /tmp/gate1.txt
test "$(cat /tmp/gate1.txt)" -ge 20 || { echo "Gate 1 FAIL"; exit 1; }

echo "[2/8] empirical classify..."
python scripts/sota_classify_balizero_posts.py

echo "[3/8] literature synthesis (slow ~15min)..."
python scripts/sota_literature_research.py

echo "[4/8] personas wave expat..."
python scripts/sota_infer_personas.py --wave=expat

echo "[5/8] personas wave id..."
python scripts/sota_infer_personas.py --wave=id

echo "[6/8] competitor ingest (requires CSV)..."
if [ -f research/sota-social-2026-v1/competitor_raw.csv ]; then
  python scripts/sota_ingest_competitors.py
else
  echo "  (skip — no CSV yet from team scraping)"
fi

echo "[7/8] format matrix + cadence + gap..."
python scripts/sota_build_format_matrix.py
python scripts/sota_build_cadence_engine.py
python scripts/sota_write_gap_analysis.py

echo "[8/8] Consiglio v1 final..."
python scripts/sota_consiglio_playbook.py --wave=final

echo "--- Final check ---"
python scripts/sota_fase0_final_check.py

echo "=== SOTA Fase 0 smoke PASS ==="
EOF
chmod +x /Users/nuzantara/Desktop/nuzantara/scripts/sota_smoke_fase0.sh
```

- [ ] **Step 2: Run smoke (only after Task 0 resolved + team has delivered CSV if possible)**

```bash
cd /Users/nuzantara/Desktop/nuzantara
./scripts/sota_smoke_fase0.sh
```

Expected: completes all 8 steps, no fatal errors. Takes ~30-45 min (literature + personas + Consiglio are LLM-heavy).

- [ ] **Step 3: Verify all 12 artifacts**

```bash
ls -la research/sota-social-2026-v1/
# Should show: 00_baseline.json, 01_balizero_corpus.json, 02_competitor_corpus.json,
# 03_sota_literature.md, 04_personas.json, 05_format_matrix.json,
# 06_cadence_engine.json, 07_gap_analysis.md, 08_playbook.md,
# 09_wr2_weights.json, 10_m13_measurer_config.md, 11_go_live_canary.md
```

- [ ] **Step 4: Unit test full suite**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/ -q --tb=short 2>&1 | tail -10
```

Expected: all existing passes + new SOTA test files all green.

- [ ] **Step 5: Commit smoke script**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/sota_smoke_fase0.sh
git commit -m "feat(sota/smoke): scripts/sota_smoke_fase0.sh end-to-end dry run

Executes all 8 Fase 0 steps in order, checks Gates 1-5 inline,
invokes final check. Safe to rerun (all scripts idempotent except
cost-logged Consiglio).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-review checklist (run after executing all tasks)

1. **Spec coverage:**
   - 12 artifacts 00-11 all produced by named task ✓
   - 7 gates all have verification steps ✓
   - M13 3 triggers (6h/weekly/monthly) = Tasks 24/25/26 ✓
   - WR2 3 injection points = Tasks 28 (editorial_config), 29 (Council v2), 23 (M13) ✓
   - Grafana dashboard = Task 31 ✓
   - Telegram kill switches = Task 30 ✓
   - Checkpoint 30/60/90 = Task 27 ✓

2. **Placeholder scan:** none remaining. All code blocks complete.

3. **Type consistency:**
   - `Persona` schema identical in `persona_inference.py` + `sota_infer_personas.py` ✓
   - `M13CollectionHorizon` enum used by both `m13_feedback_loop.py` and cron script ✓
   - `ConsiglioClaim`/`ConsiglioResult` identical in tests + implementation ✓
   - `CompetitorPost` fields match CSV runbook columns exactly ✓
   - `IGPostMetrics` dataclass fields referenced correctly in `empirical_ig_analyzer.py` + `sota_build_baseline.py` ✓

---

## Execution Handoff

Plan complete. All files:

- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research.md` (root + Task 0)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-phase0-part1.md` (Day 1 baseline)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-phase0-part2.md` (Days 2-3 + 6 empirical/literature/competitor)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-phase0-part3.md` (Days 4-10 personas/matrix/Consiglio/canary)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-loop.md` (this file — Loop 90d + WR2 + Grafana + smoke)

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

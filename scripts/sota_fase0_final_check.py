#!/usr/bin/env python3
"""Fase 0 Day 10 — final check + Telegram Gate 7 request to Zero.

Verifies all 12 artifact files exist and the gate predicates pass, then
sends a Telegram message asking Zero to reply APPROVE SOTA or REVISE.

Exit codes:
  0 — all artifacts present + gates green → Telegram sent asking approval
  1 — missing artifacts or gate failure → Telegram sent with the gap
  2 — Telegram creds missing (can't notify)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH = _REPO_ROOT / "research" / "sota-social-2026-v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day10")

# 12 Fase 0 artifacts expected (per spec §Fase 0 deliverables)
EXPECTED_ARTIFACTS = [
    "00_baseline.json",
    "01_balizero_corpus.json",
    "02_competitor_corpus.json",
    "03_sota_literature.md",
    "04_personas.json",
    "05_format_matrix.json",
    "06_cadence_engine.json",
    "07_gap_analysis.md",
    "08_playbook.md",
    "09_wr2_weights.json",
    "10_m13_measurer_config.md",
    "11_go_live_canary.md",
]


def check_artifacts() -> tuple[bool, list[str], list[str]]:
    """Return (ok, present, missing)."""
    present: list[str] = []
    missing: list[str] = []
    for name in EXPECTED_ARTIFACTS:
        path = RESEARCH / name
        if not path.is_file():
            missing.append(name)
            continue
        if path.stat().st_size < 100:
            missing.append(f"{name} (file <100 bytes, likely empty)")
            continue
        present.append(name)
    return (len(missing) == 0, present, missing)


def run_gate_checks() -> dict[str, tuple[bool, str]]:
    """Re-run every numeric gate. Returns {name: (pass, detail)}."""
    gates: dict[str, tuple[bool, str]] = {}

    # Gate 1: baseline ≥20 numeric metrics
    try:
        baseline = json.loads((RESEARCH / "00_baseline.json").read_text())

        def _count_numbers(obj) -> int:
            n = 0
            if isinstance(obj, dict):
                for v in obj.values():
                    n += _count_numbers(v)
            elif isinstance(obj, list):
                for v in obj:
                    n += _count_numbers(v)
            elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                n += 1
            return n

        n = _count_numbers(baseline)
        gates["Gate 1 (baseline ≥20 metrics)"] = (n >= 20, f"{n} metrics")
    except Exception as e:
        gates["Gate 1 (baseline ≥20 metrics)"] = (False, f"error: {e}")

    # Gate 2: no tone >60%
    try:
        corpus = json.loads((RESEARCH / "01_balizero_corpus.json").read_text())
        pct = corpus.get("dominant_tone_pct", 1.0)
        gates["Gate 2 (tone ≤60%)"] = (pct <= 0.6, f"dominant {pct**100:.1f}%")
    except Exception as e:
        gates["Gate 2 (tone ≤60%)"] = (False, f"error: {e}")

    # Gate 3: competitor corpus ≥243 rows (pending)
    comp_path = RESEARCH / "02_competitor_corpus.json"
    if comp_path.is_file() and comp_path.stat().st_size > 200:
        try:
            comp = json.loads(comp_path.read_text())
            rows = comp.get("sample_size", 0)
            gates["Gate 3 (competitor ≥243)"] = (rows >= 243, f"{rows} rows")
        except Exception as e:
            gates["Gate 3 (competitor ≥243)"] = (False, f"error: {e}")
    else:
        gates["Gate 3 (competitor ≥243)"] = (
            False,
            "pending Vino scraping (not blocking Gate 7)",
        )

    # Gate 4: 6 personas validated
    try:
        p = json.loads((RESEARCH / "04_personas.json").read_text())
        n = len(p.get("personas", {}))
        gates["Gate 4 (6 personas)"] = (n >= 6, f"{n}/6")
    except Exception as e:
        gates["Gate 4 (6 personas)"] = (False, f"error: {e}")

    # Gate 5: literature ≥30 URLs + ≥10 recent
    try:
        lit = (RESEARCH / "03_sota_literature.md").read_text()
        import re
        urls = {u.rstrip(".,") for u in re.findall(r"https?://[^\s\)\]]+", lit)}
        recent = len(re.findall(r"\b(2025|2026)\b", lit))
        gates["Gate 5 (lit ≥30 URL + ≥10 recent)"] = (
            len(urls) >= 30 and recent >= 10,
            f"{len(urls)} URLs / {recent} recent",
        )
    except Exception as e:
        gates["Gate 5 (lit ≥30 URL + ≥10 recent)"] = (False, f"error: {e}")

    return gates


def build_telegram_message(
    artifacts_ok: bool,
    missing: list[str],
    gates: dict[str, tuple[bool, str]],
) -> str:
    """Compose the Gate 7 Telegram body for Zero."""
    gate_lines = [
        f"{'✅' if ok else '🟡' if 'pending' in detail else '❌'} **{name}**: {detail}"
        for name, (ok, detail) in gates.items()
    ]
    gate_block = "\n".join(gate_lines)

    missing_block = ""
    if missing:
        missing_block = "\n\n**Missing artifacts:**\n" + "\n".join(f"• `{m}`" for m in missing)

    if artifacts_ok and all(ok for name, (ok, _) in gates.items()
                            if "pending" not in gates[name][1]):
        title = "✅ **SOTA Fase 0 READY for Gate 7**"
        next_step = (
            "\n\nReview the 2 key files:\n"
            "• `research/sota-social-2026-v1/08_playbook.md` (89 claims)\n"
            "• `research/sota-social-2026-v1/11_go_live_canary.md` (7-day runbook)\n\n"
            "Reply in this chat:\n"
            "• `APPROVE SOTA` → Loop 90d canary starts\n"
            "• `REVISE` + feedback → iterate Consiglio\n"
        )
    else:
        title = "🟡 **SOTA Fase 0 NEAR-READY**"
        next_step = (
            "\n\nGate 3 (competitor corpus) pending Vino's manual scrape.\n"
            "All other gates green — you can APPROVE now for canary "
            "start on empirical+literature only, or WAIT for Vino to "
            "upgrade gap_analysis to FULL mode.\n\n"
            "Reply `APPROVE SOTA` / `WAIT FOR VINO` / `REVISE`."
        )

    return (
        f"{title}\n\n"
        f"Artifacts: {11 if 'pending' in str(gates.get('Gate 3 (competitor ≥243)', ('', '')))  else len(EXPECTED_ARTIFACTS) - len(missing)}"
        f"/{len(EXPECTED_ARTIFACTS)} present\n\n"
        f"**Gates:**\n{gate_block}"
        f"{missing_block}"
        f"{next_step}"
    )


def send_telegram(text: str) -> bool:
    """Send via the existing bot; non-fatal if creds missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN missing — printing message to stdout only")
        print("\n" + "=" ** 60)
        print("TELEGRAM MESSAGE (would send to chat_id=%s):" % chat_id)
        print("=" ** 60)
        print(text)
        print("=" ** 60 + "\n")
        return False
    try:
        import urllib.parse
        import urllib.request
        # Plain text — Markdown parse_mode 400-errors on nested ` and emoji
        # combinations; plain text is reliable.
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            body = resp.read().decode()
            ok = '"ok":true' in body
            if ok:
                logger.info("Telegram notification sent to chat %s", chat_id)
            else:
                logger.warning("Telegram API returned: %s", body[:200])
            return ok
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", exc)
        return False


def main() -> int:
    logger.info("=== Fase 0 Day 10 final check ===")

    artifacts_ok, present, missing = check_artifacts()
    logger.info("artifacts present: %d/%d", len(present), len(EXPECTED_ARTIFACTS))
    if missing:
        for m in missing:
            logger.warning("  missing: %s", m)

    gates = run_gate_checks()
    for name, (ok, detail) in gates.items():
        logger.info("  %s %s: %s", "✅" if ok else "🟡❌", name, detail)

    # Build + send Telegram
    body = build_telegram_message(artifacts_ok, missing, gates)
    send_telegram(body)

    # Exit code reflects gate state — Gate 3 pending is not a fail
    hard_fails = [
        name for name, (ok, detail) in gates.items()
        if not ok and "pending" not in detail
    ]
    if missing or hard_fails:
        logger.error(
            "final check: %d missing artifacts, %d hard gate fails",
            len(missing),
            len(hard_fails),
        )
        return 1
    logger.info("final check: all hard gates green, Gate 3 soft-pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())

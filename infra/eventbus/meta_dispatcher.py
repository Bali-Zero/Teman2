#!/usr/bin/env python3
"""Meta-Dispatcher — central event router for Bali Zero ecosystem.

Long-running daemon. Subscribes to ALL bz:* streams. For each event, applies
routing rules and triggers downstream actions:

- Telegram alert (urgency: critical/high)
- launchctl kickstart (wake up dependent agent)
- HTTP POST (queue server flag)
- File-based fallback (write trigger sentinel)

Routing rules are declarative in ROUTING_RULES dict — easy to extend.
NO LLM calls in the dispatcher itself (it's a router, not an agent).
LLM-grade decisions stay in the consumers.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# Add eventbus to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eventbus import EventSubscriber, EventEnvelope, beat, start_background_beater

LOG = Path.home() / "logs" / "meta-dispatcher.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)
log = logging.getLogger("meta-dispatcher")

ALL_EVENT_TYPES = [
    "intel.collected",
    "intel.deduped",
    "regulatory.delta.detected",
    "topic.candidate.created",
    "content.draft.ready",
    "redteam.completed",  # 2026-05-10: devils-advocate post-redteam dispatch
    "human.review.completed",
    "publish.completed",
    "engagement.measured",
    "learning.updated",
]

# Routing rules: event_type → list of actions to fire
# Each action is a dict with keys: type, params
ROUTING_RULES = {
    "intel.collected": [
        # No automatic action — dedup gate handles next step
    ],
    "intel.deduped": [
        # Wake up topic-selector to re-score
        {"type": "launchctl_kickstart", "label": "com.balizero.wr2.topic-selector"},
    ],
    "regulatory.delta.detected": [
        {"type": "telegram_if_urgent", "min_urgency": "high"},
        {"type": "launchctl_kickstart", "label": "com.balizero.wr2.topic-selector"},
    ],
    "topic.candidate.created": [
        {"type": "launchctl_kickstart", "label": "com.balizero.wr2.supervisor"},
    ],
    "content.draft.ready": [
        # 2026-05-10: gate high-stakes domains through devils-advocate BEFORE canva-apply.
        # If domain in {tax,regulatory,property,visa}, spawn DA red-team async; canva-apply
        # waits on redteam.completed verdict (handled by separate route below).
        # If domain NOT high-stakes, fall through to canva-apply directly.
        {"type": "spawn_devils_advocate_if_high_stakes",
         "high_stakes_domains": ["tax", "regulatory", "property", "visa"],
         "status_value": "pass"},
        # Trigger canva-apply skill via spawned claude subprocess if status=pass AND domain low-stakes
        # (canva-apply lives as skill not LaunchAgent — spawn invocation here)
        {"type": "spawn_canva_apply_if_status_and_low_stakes",
         "status_value": "pass",
         "high_stakes_domains": ["tax", "regulatory", "property", "visa"]},
        # Telegram Damar if needs_human_edit
        {"type": "telegram_if_status", "status_value": "needs_human_edit", "msg_template": "WR2 carousel '{topic_slug}' STUCK — needs human edit"},
    ],
    "redteam.completed": [
        # After devils-advocate completes, if verdict=PASS, spawn canva-apply.
        # If verdict=BLOCK or NEEDS_FIX, Telegram Damar with red-team report path.
        {"type": "spawn_canva_apply_if_status", "status_value": "PASS"},
        {"type": "telegram_if_status", "status_value": "BLOCK",
         "msg_template": "WR2 RED-TEAM BLOCK — '{topic_slug}' has {critical_count} critical findings. Report: {report_path}"},
        {"type": "telegram_if_status", "status_value": "NEEDS_FIX",
         "msg_template": "WR2 RED-TEAM NEEDS_FIX — '{topic_slug}' has {high_count} high findings. Report: {report_path}"},
    ],
    "human.review.completed": [
        # Update queue server (best-effort; queue server is also event source so this is observability only)
    ],
    "publish.completed": [
        # Schedule IG metrics scrape in 24h (handled by daily cron, no immediate action)
    ],
    "engagement.measured": [
        # Reflexion is weekly batch — no immediate action
    ],
    "learning.updated": [
        {"type": "telegram_digest", "msg_template": "Weekly learning '{source}' updated. Lessons: {lessons_count}"},
    ],
}

URGENCY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _send_telegram(text: str) -> bool:
    """Best-effort Telegram send via env-sourced bot token."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not token or not chat_id:
        log.warning("telegram skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_CHAT_ID not set")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        result = subprocess.run(
            ["curl", "-sf", "-X", "POST", url,
             "-d", f"chat_id={chat_id}",
             "-d", f"text={text[:4000]}",
             "-d", "disable_web_page_preview=true"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        log.warning("telegram send failed: %s", e)
        return False


def _check_redis_health() -> bool:
    """PING Mini Redis. Returns True if reachable. Caches state to detect 3-fail streaks."""
    import redis
    try:
        r = redis.Redis(host="100.93.236.6", port=6379, socket_timeout=3, socket_connect_timeout=3)
        r.ping()
        return True
    except Exception:
        return False


_redis_health_state = {"consecutive_fails": 0, "last_check": 0, "alerted": False}


def _maybe_check_redis_health() -> None:
    """Throttled health check: every 5 min, alert after 3 consecutive fails."""
    now = time.time()
    if now - _redis_health_state["last_check"] < 300:  # 5 min
        return
    _redis_health_state["last_check"] = now

    ok = _check_redis_health()
    if ok:
        if _redis_health_state["consecutive_fails"] > 0:
            log.info("Redis recovered after %d fails", _redis_health_state["consecutive_fails"])
            if _redis_health_state["alerted"]:
                _send_telegram("EVENTBUS RECOVERED — Redis Mini reachable again")
        _redis_health_state["consecutive_fails"] = 0
        _redis_health_state["alerted"] = False
    else:
        _redis_health_state["consecutive_fails"] += 1
        log.warning("Redis health PING failed (%d consecutive)",
                    _redis_health_state["consecutive_fails"])
        if _redis_health_state["consecutive_fails"] >= 3 and not _redis_health_state["alerted"]:
            _send_telegram(
                "EVENTBUS DOWN — Redis Mini (100.93.236.6:6379) unreachable for 3+ checks. "
                "Check Tailscale + Mini status. Bus stalled."
            )
            _redis_health_state["alerted"] = True


def _kickstart(label: str) -> bool:
    """launchctl kickstart -k gui/$(id -u)/<label>. Returns True if succeeded."""
    uid = os.getuid()
    try:
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        if not ok:
            log.warning("kickstart %s failed: %s", label, result.stderr.strip())
        return ok
    except Exception as e:
        log.warning("kickstart %s exception: %s", label, e)
        return False


def _process_action(action: dict, env: EventEnvelope) -> None:
    atype = action["type"]
    p = env.payload

    if atype == "launchctl_kickstart":
        ok = _kickstart(action["label"])
        log.info("kickstart %s -> %s (event %s)", action["label"], ok, env.event_id)

    elif atype == "launchctl_kickstart_if_status":
        if p.get("status") == action["status_value"]:
            ok = _kickstart(action["label"])
            log.info("kickstart-if %s [status=%s] -> %s (event %s)",
                     action["label"], action["status_value"], ok, env.event_id)

    elif atype == "telegram_if_urgent":
        urgency = p.get("urgency", "low")
        min_rank = URGENCY_RANK.get(action["min_urgency"], 2)
        if URGENCY_RANK.get(urgency, 0) >= min_rank:
            txt = (
                f"REGULATORY ALERT [{urgency.upper()}]\n"
                f"{p.get('citation', '?')}: {p.get('summary', '')[:300]}\n"
                f"Service lines: {', '.join(p.get('service_lines', []))}\n"
                f"Source: {p.get('source', '?')}"
            )
            ok = _send_telegram(txt)
            log.info("telegram-urgent [%s] -> %s (event %s)", urgency, ok, env.event_id)

    elif atype == "telegram_if_status":
        if p.get("status") == action["status_value"]:
            txt = action["msg_template"].format(**p)
            ok = _send_telegram(txt)
            log.info("telegram-status [%s] -> %s (event %s)", action["status_value"], ok, env.event_id)

    elif atype == "spawn_canva_apply_if_status":
        if p.get("status") == action["status_value"]:
            # canva-apply is a Claude Code skill (markdown-driven, MCP Canva tools)
            # Spawn a one-shot claude --print invocation to execute the skill if canva_pending.json exists
            pending = "/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json"
            if not os.path.exists(pending):
                log.info("spawn-canva-apply skip: %s missing (event %s)", pending, env.event_id)
                return
            cmd = [
                "/Users/nuzantara/scripts/claude-cascade.sh",
                "Run the canva-apply skill: read canva_pending.json, apply via MCP Canva tools, mark applied.",
                "--model", "claude-sonnet-4-6",
            ]
            try:
                # Fire-and-forget: don't block dispatcher loop
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                log.info("spawn-canva-apply launched (event %s, pending=%s)", env.event_id, pending)
            except Exception as e:
                log.warning("spawn-canva-apply launch failed: %s", e)

    elif atype == "spawn_canva_apply_if_status_and_low_stakes":
        # Variant: only spawn canva-apply directly when domain is NOT high-stakes.
        # High-stakes domains go through devils-advocate first (separate route).
        if p.get("status") != action["status_value"]:
            return
        domain = (p.get("domain") or "").lower()
        if domain in [d.lower() for d in action.get("high_stakes_domains", [])]:
            log.info("canva-apply gated by devils-advocate for high-stakes domain=%s (event %s)",
                     domain, env.event_id)
            return
        # Low-stakes path: same spawn logic as spawn_canva_apply_if_status
        pending = "/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json"
        if not os.path.exists(pending):
            log.info("spawn-canva-apply (low-stakes) skip: %s missing (event %s)", pending, env.event_id)
            return
        cmd = [
            "/Users/nuzantara/scripts/claude-cascade.sh",
            "Run the canva-apply skill: read canva_pending.json, apply via MCP Canva tools, mark applied.",
            "--model", "claude-sonnet-4-6",
        ]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            log.info("spawn-canva-apply (low-stakes domain=%s) launched (event %s)",
                     domain, env.event_id)
        except Exception as e:
            log.warning("spawn-canva-apply (low-stakes) launch failed: %s", e)

    elif atype == "spawn_devils_advocate_if_high_stakes":
        # 2026-05-10: pre-publish gate via devils-advocate sub-agent (DeepSeek Reasoner).
        # Trigger only when status=pass AND domain is high-stakes.
        # devils_advocate_runner.py wraps the DA invocation: spawns claude-cascade with
        # --agent devils-advocate, sniffs the JSON report, then publishes redteam.completed.
        # The redteam route then either spawns canva-apply (verdict=PASS) or alerts Damar.
        if p.get("status") != action["status_value"]:
            return
        domain = (p.get("domain") or "").lower()
        high_stakes = [d.lower() for d in action.get("high_stakes_domains", [])]
        if domain not in high_stakes:
            log.info("devils-advocate skip: domain=%s not high-stakes (event %s)",
                     domain, env.event_id)
            return
        target = p.get("target_path") or p.get("draft_path") or p.get("slides_path")
        if not target:
            log.warning("devils-advocate skip: no target_path/draft_path/slides_path in payload (event %s)",
                        env.event_id)
            return
        topic_slug = p.get("topic_slug", "unknown")
        cmd = [
            "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3",
            "/Users/nuzantara/scripts/eventbus/devils_advocate_runner.py",
            "--target", target,
            "--topic-slug", topic_slug,
            "--domain", domain if domain in ("tax", "regulatory", "property", "visa") else "other",
            "--trace-id", env.trace_id or "",
            "--source-event-id", env.event_id,
        ]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            log.info("spawn-devils-advocate-runner launched (event %s, domain=%s, target=%s)",
                     env.event_id, domain, target)
        except Exception as e:
            log.warning("spawn-devils-advocate-runner launch failed: %s", e)

    elif atype == "telegram_digest":
        try:
            kwargs = dict(p)
            kwargs["lessons_count"] = len(p.get("lessons", []))
            txt = action["msg_template"].format(**kwargs)
            ok = _send_telegram(txt)
            log.info("telegram-digest -> %s (event %s)", ok, env.event_id)
        except KeyError as e:
            log.warning("telegram-digest template missing key: %s", e)

    else:
        log.warning("unknown action type %s", atype)


def main() -> int:
    log.info("Meta-Dispatcher starting. Listening on %d streams.", len(ALL_EVENT_TYPES))
    start_background_beater("meta-dispatcher", interval=30)
    sub = EventSubscriber(
        agent_name="meta-dispatcher",
        event_types=ALL_EVENT_TYPES,
        start_from="$",  # only new events from boot time
    )

    for env in sub.listen(block_ms=10000, count=20):
        # Risk 3 fix: emit heartbeat (throttled to 30s)
        beat("meta-dispatcher")
        # Risk 2 fix: throttled Redis health probe (5min cadence, 3-fail Telegram alert)
        _maybe_check_redis_health()

        # Poison-pill check (Risk 1 fix): if redelivered N+ times, park to DLQ
        attempts = sub.get_delivery_count(env)
        if attempts > sub.MAX_DELIVERY_ATTEMPTS:
            sub.park_to_dlq(env, f"exceeded {sub.MAX_DELIVERY_ATTEMPTS} delivery attempts")
            continue

        # Idempotency check
        if sub.is_seen(env.event_id):
            log.debug("skipping seen event %s", env.event_id)
            sub.ack(env)
            continue

        log.info(
            "event %s type=%s emitted_by=%s trace=%s attempts=%d",
            env.event_id, env.event_type, env.emitted_by, env.trace_id, attempts,
        )

        actions = ROUTING_RULES.get(env.event_type, [])
        action_failures = 0
        for action in actions:
            try:
                _process_action(action, env)
            except Exception as e:
                log.exception("action %s failed for event %s: %s", action.get("type"), env.event_id, e)
                action_failures += 1

        # If ALL actions failed AND retry budget remains, do NOT ack — let Redis redeliver
        if actions and action_failures == len(actions) and attempts < sub.MAX_DELIVERY_ATTEMPTS:
            log.warning("event %s: ALL %d actions failed, leaving in PEL for retry %d",
                        env.event_id, len(actions), attempts + 1)
            continue

        sub.ack(env)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Meta-Dispatcher interrupted")
        sys.exit(0)

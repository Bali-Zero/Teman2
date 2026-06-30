"""Mata Garuda — pipeline health monitor (real operativity, not exit-0).

Council + cicatrix #2 ("green != working — read the OUTPUT, not the exit code"):
a cron that exits 0 proves nothing. This monitor reads the ACTUAL pipeline
state from Redis + NLM and emits a verdict + heartbeat sidecar + (optional) TG
alert when the pipeline is degraded.

What it checks (each a falsifiable signal, not a PID):
  1. STREAM RAM       — sum of XLEN across streams vs STREAM_MAXLEN headroom.
  2. CONSUMER LAG     — per-group lag on garuda:enriched + nexus:gaps; flags any
                        group whose lag is GROWING run-over-run (the real "stuck"
                        signal). Stream 0 below probes Redis reachability first so
                        a total outage is RED, never a silent GREEN (cicatrix #2).
  3. FRESHNESS        — age of the newest entry per stream (is harvest alive?).
  4. NLM THROUGHPUT   — did the feeder actually add sources in the last window?
                        (compares NLM source_count snapshots run-over-run).
  5. SCORER DRAIN     — is the scorer lag shrinking, or stuck (intel un-scored)?

Verdict: GREEN / YELLOW / RED with the specific failing signal. Writes a
heartbeat sidecar (~/.organism/last_seen/) so the organism-level watchers see it,
and on RED fires a single TG alert to Zero.

Pure stdlib + redis-cli + nlm CLI (no new deps — pydantic/pytest only rule).
State across runs is kept in a small JSON snapshot so deltas are real.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from mata_garuda.workers.base_worker import redis_cmd as _bw_redis_cmd

# ── config (env-overridable, no hardcoded secrets) ────────────────────────
STREAM_MAXLEN = int(os.environ.get("GARUDA_STREAM_MAXLEN", "100000"))
STREAMS = ["garuda:raw", "garuda:enriched", "garuda:alerts"]
ENRICHED = "garuda:enriched"
# Streams whose consumer-group lag is monitored. enriched fans out to the
# classifier/ner/scorer/nlm_feeder workers; nexus:gaps drives gap_consumer.
# (RR-H1: pre-fix only enriched was scanned, so a stuck gap_consumer was invisible.)
LAG_STREAMS = [ENRICHED, "nexus:gaps"]
STATE_FILE = Path(os.environ.get(
    "GARUDA_HEALTH_STATE",
    str(Path.home() / ".organism" / "pipeline_health.state.json"),
))
SIDECAR = Path.home() / ".organism" / "last_seen" / "mata_garuda.pipeline_health.json"
# lag above this AND growing = RED; above this but shrinking = YELLOW
LAG_RED = int(os.environ.get("GARUDA_LAG_RED", "8000"))
LAG_YELLOW = int(os.environ.get("GARUDA_LAG_YELLOW", "3000"))
# newest entry older than this many hours = stale harvest
FRESH_MAX_H = float(os.environ.get("GARUDA_FRESH_MAX_H", "26"))


def _r(*args: str) -> str:
    """Run a redis-cli command via the canonical base_worker topology.

    RR-H3 (Stage 1 single-writer, 2026-06-29): host/port/auth/cli-path
    resolution lives in ONE place — base_worker._resolve_redis_host()
    (GARUDA_REDIS_HOST → GARUDA_CANONICAL_REDIS_HOST → local sentinel) +
    REDISCLI_AUTH (cicatrix #4, never -a) + abs-path redis-cli. This monitor
    used to carry its own localhost default + duplicate cli/env logic, the
    last organ outside the canonical cure. On any failure redis_cmd returns
    "[ERROR] ..."; assess()'s reachability probe keys on the "[ER" prefix so
    both that and a legacy "[ERR ...]" read as a failed probe (RR-H4).
    """
    return _bw_redis_cmd(*args, timeout=15)


def _now_ms() -> int:
    t = _r("TIME").split("\n")
    try:
        return int(t[0]) * 1000 + int(t[1]) // 1000
    except Exception:
        return 0


def _xlen(stream: str) -> int:
    v = _r("XLEN", stream)
    return int(v) if v.isdigit() else 0


def _newest_age_h(stream: str, now_ms: int) -> float | None:
    """Age in hours of the newest entry (entry ids are ms-prefixed)."""
    out = _r("XREVRANGE", stream, "+", "-", "COUNT", "1")
    line = out.split("\n")[0].strip() if out else ""
    if "-" not in line:
        return None
    try:
        eid_ms = int(line.split("-")[0])
        return round((now_ms - eid_ms) / 3_600_000, 1)
    except Exception:
        return None


def _group_lags(stream: str) -> dict[str, int]:
    """Parse XINFO GROUPS flat output → {group: lag}."""
    out = _r("XINFO", "GROUPS", stream)
    toks = out.split("\n")
    lags, name = {}, None
    for i, t in enumerate(toks):
        if t == "name" and i + 1 < len(toks):
            name = toks[i + 1]
        elif t == "lag" and name and i + 1 < len(toks):
            try:
                lags[name] = int(toks[i + 1])
            except ValueError:
                pass
    return lags


def _nlm_source_total() -> int | None:
    nlm = shutil.which("nlm") or os.path.expanduser("~/.local/bin/nlm")
    if not os.path.exists(nlm):
        return None
    try:
        p = subprocess.run([nlm, "notebook", "list"],
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return None
        data = json.loads(p.stdout)
        return sum(int(n.get("source_count", 0)) for n in data
                   if str(n.get("title", "")).startswith("NB-INTEL"))
    except Exception:
        return None


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def _emit_sidecar(status: str, metadata: dict, now_ms: int) -> None:
    SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": now_ms // 1000,
        "status": status,            # ok | degraded | fail
        "organ_id": "mata_garuda.pipeline_health",
        "metadata": metadata,
    }
    tmp = SIDECAR.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(SIDECAR)


def _tg_alert(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return False
    try:
        import urllib.parse
        import urllib.request
        body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=body)
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception:
        return False


def assess() -> dict:
    """Pure assessment → returns the report dict. No side effects (testable)."""
    findings: list[str] = []
    verdict = "GREEN"

    # 0. REDIS REACHABILITY (RR-H4 / cicatrix #2 — green-but-dead).
    # _r() returns "[ERR ...]" on any subprocess/connection failure. If Redis is
    # unreachable, every numeric signal below silently reads as 0/None and the
    # monitor would otherwise stay GREEN through a TOTAL OUTAGE — the exact
    # failure this monitor exists to catch. A failed PING is hard RED, full stop.
    ping = _r("PING")
    # "[ER..." covers both base_worker's "[ERROR] ..." and the legacy "[ERR ...]"
    # error sentinels; a live Redis answers exactly "PONG".
    if ping.startswith("[ER") or "PONG" not in ping.upper():
        return {
            "verdict": "RED",
            "ts": 0,
            "xlens": {},
            "total_entries": 0,
            "maxlen": STREAM_MAXLEN,
            "lags": {},
            "ages_h": {},
            "nlm_total": None,
            "nlm_delta": None,
            "findings": [f"redis probe FAILED (PING -> {ping!r}) — pipeline blind, total outage"],
        }

    now_ms = _now_ms()
    prev = _load_state()
    prev_lags = prev.get("lags", {})
    prev_nlm = prev.get("nlm_total")

    # 1. RAM / stream sizes
    xlens = {s: _xlen(s) for s in STREAMS}
    total = sum(xlens.values())
    over_cap = {s: n for s, n in xlens.items() if n > STREAM_MAXLEN}
    if over_cap:
        verdict = "RED"
        findings.append(f"stream over MAXLEN {STREAM_MAXLEN}: {over_cap}")

    # 2. consumer lag (growing = real stuck) across ALL monitored streams
    # (RR-H1: enriched + nexus:gaps, not enriched-only).
    lags: dict[str, int] = {}
    for s in LAG_STREAMS:
        lags.update(_group_lags(s))
    for g, lag in lags.items():
        prev_lag = prev_lags.get(g)
        growing = prev_lag is not None and lag > prev_lag
        if lag >= LAG_RED and growing:
            verdict = "RED"
            findings.append(f"group '{g}' lag={lag} RED+growing (was {prev_lag})")
        elif lag >= LAG_RED:
            verdict = max(verdict, "YELLOW", key=_sev)
            findings.append(f"group '{g}' lag={lag} high but draining (was {prev_lag})")
        elif lag >= LAG_YELLOW and growing:
            verdict = max(verdict, "YELLOW", key=_sev)
            findings.append(f"group '{g}' lag={lag} growing (was {prev_lag})")

    # 3. freshness (harvest alive?)
    ages = {s: _newest_age_h(s, now_ms) for s in STREAMS}
    raw_age = ages.get("garuda:raw")
    if raw_age is not None and raw_age > FRESH_MAX_H:
        verdict = "RED"
        findings.append(f"garuda:raw newest entry {raw_age}h old (>{FRESH_MAX_H}h) — harvest stalled")

    # 4. NLM throughput (did feeder add sources since last run?)
    nlm_total = _nlm_source_total()
    nlm_delta = None
    if nlm_total is not None and prev_nlm is not None:
        nlm_delta = nlm_total - prev_nlm
    # not a hard fail (cap legitimately blocks), informational

    # 5. scorer drain
    scorer_lag = lags.get("scorer")
    if scorer_lag is not None and prev_lags.get("scorer") is not None:
        if scorer_lag >= LAG_RED and scorer_lag >= prev_lags["scorer"]:
            verdict = max(verdict, "YELLOW", key=_sev)
            findings.append(f"scorer not draining: lag={scorer_lag} (was {prev_lags['scorer']}) — high-relevance intel ages un-scored")

    report = {
        "verdict": verdict,
        "ts": now_ms // 1000,
        "xlens": xlens,
        "total_entries": total,
        "maxlen": STREAM_MAXLEN,
        "lags": lags,
        "ages_h": ages,
        "nlm_total": nlm_total,
        "nlm_delta": nlm_delta,
        "findings": findings or ["all signals nominal"],
    }
    return report


def _sev(v: str) -> int:
    return {"GREEN": 0, "YELLOW": 1, "RED": 2}.get(v, 0)


def main() -> int:
    report = assess()
    verdict = report["verdict"]

    # persist state for next-run deltas
    _save_state({"lags": report["lags"], "nlm_total": report["nlm_total"], "ts": report["ts"]})

    # heartbeat sidecar (organism-level watchers read this)
    status = {"GREEN": "ok", "YELLOW": "degraded", "RED": "fail"}[verdict]
    _emit_sidecar(status, {
        "verdict": verdict,
        "total_entries": report["total_entries"],
        "lags": report["lags"],
        "findings": report["findings"],
    }, report["ts"] * 1000)

    print(json.dumps(report, indent=2))

    # alert ONLY on RED (avoid noise — cicatrix #7/#8 single-attempt is fine here
    # because the cron re-runs; YELLOW is visible in the sidecar)
    if verdict == "RED":
        msg = "🔴 Mata Garuda pipeline RED\n" + "\n".join(f"• {f}" for f in report["findings"][:5])
        _tg_alert(msg)

    # exit code mirrors verdict so launchd ALSO shows honest red (defense in depth)
    return 0 if verdict == "GREEN" else (1 if verdict == "YELLOW" else 2)


if __name__ == "__main__":
    sys.exit(main())

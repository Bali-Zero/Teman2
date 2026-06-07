#!/usr/bin/env python3
"""Bridge selected LaunchAgent liveness into organism last_seen receipts.

The monitored labels are daemons or external services whose code cannot emit
their own heartbeat. This bridge is read-only with respect to launchd: it only
runs `launchctl list` and writes JSON receipts.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_LAST_SEEN_DIR = Path("~/.organism/last_seen").expanduser()
DEFAULT_LEGACY_STATE_DIR = Path("~/.agent/decisions/state").expanduser()
HEALTHY_EXIT_CODES = {0}


@dataclass(frozen=True)
class BridgedLaunchAgent:
    label: str
    organ_id: str
    daemon: bool
    legacy_job_id: str = ""


@dataclass(frozen=True)
class TcpProbe:
    organ_id: str
    host: str
    port: int
    timeout_seconds: float = 2.0


BRIDGED_LABELS: tuple[BridgedLaunchAgent, ...] = (
    BridgedLaunchAgent(
        label="com.nuzantara.launchagent-state-bridge",
        organ_id="pro.launchagent_state_bridge",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.prime-tunnel",
        organ_id="pro.prime_tunnel",
        daemon=True,
        legacy_job_id="prime_tunnel",
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.pg-proxy",
        organ_id="wr2.pg_proxy",
        daemon=True,
        legacy_job_id="wr2_pg_proxy",
    ),
    # P0h import: live Pro LaunchAgents that cannot reliably emit their own
    # heartbeat because they are home-runtime wrappers, external services, or
    # daemon shims. The bridge owns liveness receipts only; launchd still owns
    # process supervision.
    BridgedLaunchAgent(
        label="com.balizero.cron-log-sentinel",
        organ_id="pro.cron_log_sentinel",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.observatory",
        organ_id="pro.eventbus_observatory",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-dedup-gateway",
        organ_id="pro.eventbus_intel_dedup_gateway",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.meta-dispatcher",
        organ_id="pro.eventbus_meta_dispatcher",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.research-sentinel",
        organ_id="pro.eventbus_research_sentinel",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.mos-plus.compression",
        organ_id="pro.mos_plus_compression",
        daemon=False,
    ),
    # P0n import: scheduled monitors/probes with non-zero exit codes. These
    # jobs intentionally surface operational failures via launchd status; the
    # bridge turns that status into organism receipts without muting alerts.
    BridgedLaunchAgent(
        label="com.balizero.audit-launchd.daily",
        organ_id="pro.audit_launchd_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-lake.e2e-probe.6h",
        organ_id="intel_lake.e2e_probe_6h",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.nuzantara-drive-sync",
        organ_id="pro.nuzantara_drive_sync",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.e2e-probe.daily",
        organ_id="wr2.e2e_probe_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.plist-watchdog",
        organ_id="wr2.plist_watchdog",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.consumer-lag.check",
        organ_id="mata_garuda.consumer_lag_check",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.redis-split-brain.check",
        organ_id="mata_garuda.redis_split_brain_check",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.codex-spark-alarm",
        organ_id="codex.spark_alarm",
        daemon=False,
    ),
    # P0o import: scheduled-ok and event-driven LaunchAgents that were
    # live in Pro launchd with matching plist labels but no genome edge.
    # The bridge records launchd status only; script-level success remains
    # a separate heartbeat upgrade for the high-value jobs.
    BridgedLaunchAgent(
        label="com.balizero.agent-library-evolver.daily",
        organ_id="pro.agent_library_evolver_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.agent-library-evolver.weekly",
        organ_id="pro.agent_library_evolver_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.cicatrix-rotation.monthly",
        organ_id="pro.cicatrix_rotation_monthly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.claude-settings-watcher",
        organ_id="pro.claude_settings_watcher",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.competitor-monitor.monthly",
        organ_id="pro.competitor_monitor_monthly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.competitor-signal-router.weekly",
        organ_id="pro.competitor_signal_router_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.crm-guardian-cli-worker",
        organ_id="pro.crm_guardian_cli_worker",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.curiosity.weekly",
        organ_id="pro.curiosity_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.fly-cost-alert.weekly",
        organ_id="pro.fly_cost_alert_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-lake-nb-pusher.15min",
        organ_id="intel_lake.nb_pusher_15min",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-lake-router.5min",
        organ_id="intel_lake.router_5min",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-lake.outbox-drain.minute",
        organ_id="intel_lake.outbox_drain_minute",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.intel-lake.shadow-validate.6h",
        organ_id="intel_lake.shadow_validate_6h",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.l5-2-phase2b-trigger",
        organ_id="pro.l5_2_phase2b_trigger",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.mos-plus.qdrant-indexer",
        organ_id="pro.mos_plus_qdrant_indexer",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.nextdns-tamper-detect.weekly",
        organ_id="pro.nextdns_tamper_detect_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.nuzantara.disk-watchdog",
        organ_id="pro.disk_watchdog",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.nuzantara.log-size-watchdog",
        organ_id="pro.log_size_watchdog",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-lid-refresh",
        organ_id="pro.wa_lid_refresh",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-attention-classifier",
        organ_id="pro.wa_mirror_attention_classifier",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-attention-digest",
        organ_id="pro.wa_mirror_attention_digest",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-attention-realtime",
        organ_id="pro.wa_mirror_attention_realtime",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-strategic-recap",
        organ_id="pro.wa_mirror_strategic_recap",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.canva-gc.weekly",
        organ_id="wr2.canva_gc_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.canva-lease-watchdog",
        organ_id="wr2.canva_lease_watchdog_launchd",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.canva-token-watchdog",
        organ_id="wr2.canva_token_watchdog_launchd",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.daily-metrics",
        organ_id="wr2.daily_metrics",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.external-bench.monthly",
        organ_id="wr2.external_bench_monthly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.ig-metrics-analyst.weekly",
        organ_id="wr2.ig_metrics_analyst_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.pg-queue-sync",
        organ_id="wr2.pg_queue_sync",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.worktree-gc.daily",
        organ_id="wr2.worktree_gc_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr3.editorial-bench.monthly",
        organ_id="wr3.editorial_bench_monthly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr3.reflexion.weekly",
        organ_id="wr3.reflexion_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.yield-optimizer.weekly",
        organ_id="pro.yield_optimizer_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.pel-cleaner.weekly",
        organ_id="mata_garuda.pel_cleaner_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.sentinel.hourly",
        organ_id="mata_garuda.sentinel_hourly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.unmapped-audit.daily",
        organ_id="mata_garuda.unmapped_audit_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.archive-empty-sessions.daily",
        organ_id="pro.archive_empty_sessions_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.branch-cleanup.weekly",
        organ_id="pro.branch_cleanup_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.codex-openclaw-analysis",
        organ_id="codex.openclaw_analysis",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.codex-spark-harvester",
        organ_id="codex.spark_harvester",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.daily-indexing-sweep",
        organ_id="pro.daily_indexing_sweep_launchd",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.gh-auth-healthcheck.weekly",
        organ_id="pro.gh_auth_healthcheck_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.openclaw.guardian-board",
        organ_id="pro.openclaw_guardian_board",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.outbox-prune.weekly",
        organ_id="pro.outbox_prune_weekly",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.repomap.15min",
        organ_id="pro.repomap_15min",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.skills-bridge-consumer",
        organ_id="cell.skills_bridge_consumer_launchd",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.worktree-gc-universal.daily",
        organ_id="pro.worktree_gc_universal_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.guardrails-daemon",
        organ_id="pro.guardrails_daemon",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.nb-curator.daily",
        organ_id="pro.nb_curator_daily",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.observatory-server",
        organ_id="pro.observatory_server",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.observatory-export",
        organ_id="pro.observatory_export",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.profile-monitor-wrapper",
        organ_id="pro.profile_monitor_wrapper",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.qdrant.daemon",
        organ_id="infra.qdrant_pro",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-dashboard-m1",
        organ_id="pro.wa_dashboard_m1",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-meta-inbox",
        organ_id="pro.wa_meta_inbox",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-auto-promote",
        organ_id="pro.wa_mirror_auto_promote",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-mirror-launcher",
        organ_id="pro.wa_mirror_launcher",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wa-viewer",
        organ_id="pro.wa_viewer",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.carousel-dispatcher",
        organ_id="wr2.carousel_dispatcher",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr2.telegram-gate",
        organ_id="wr2.telegram_gate",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.balizero.wr3.supervisor",
        organ_id="wr3.supervisor",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.classifier.adaptive",
        organ_id="mata_garuda.classifier_adaptive.pro",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.matagaruda.ner.adaptive",
        organ_id="mata_garuda.ner_adaptive.pro",
        daemon=False,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.codex-spark-loop",
        organ_id="codex.spark_loop",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.openclaw-whatsapp-bridge",
        organ_id="pro.openclaw_whatsapp_bridge",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="com.nuzantara.openclaw-whatsapp-tunnel",
        organ_id="pro.openclaw_whatsapp_tunnel",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="homebrew.mxcl.postgresql@17",
        organ_id="infra.local_postgres_pro",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="homebrew.mxcl.syncthing",
        organ_id="infra.syncthing_pro",
        daemon=True,
    ),
    BridgedLaunchAgent(
        label="homebrew.mxcl.ollama",
        organ_id="infra.ollama_pro",
        daemon=True,
    ),
)

BRIDGED_TCP_PROBES: tuple[TcpProbe, ...] = (
    TcpProbe(
        organ_id="infra.eventbus_redis_mini",
        host="100.93.236.6",
        port=6379,
    ),
)


def parse_launchctl(text: str) -> dict[str, dict[str, int | None]]:
    """Parse `launchctl list` output into {label: {pid, exit_code}}."""
    agents: dict[str, dict[str, int | None]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("pid"):
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid_s, exit_s, label = parts
        agents[label] = {
            "pid": None if pid_s == "-" else int(pid_s),
            "exit_code": int(exit_s) if exit_s.lstrip("-").isdigit() else 0,
        }
    return agents


def read_launchctl() -> dict[str, dict[str, int | None]]:
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return parse_launchctl(result.stdout)


def build_receipt(
    spec: BridgedLaunchAgent,
    agents: dict[str, dict[str, int | None]],
    *,
    now: int,
    host: str,
) -> dict[str, Any]:
    agent = agents.get(spec.label)
    if agent is None:
        return {
            "organ_id": spec.organ_id,
            "job": spec.organ_id,
            "ts": now,
            "status": "failed",
            "host": host,
            "source": "launchagent-state-bridge",
            "label": spec.label,
            "last_error": "label not loaded",
        }

    pid = agent.get("pid")
    exit_code = agent.get("exit_code", 0)

    if spec.daemon:
        status = "ok" if pid is not None else "failed"
        last_error = "" if pid is not None else "daemon not running"
    else:
        status = "ok" if exit_code in HEALTHY_EXIT_CODES else "failed"
        last_error = "" if status == "ok" else f"exit code {exit_code}"

    receipt: dict[str, Any] = {
        "organ_id": spec.organ_id,
        "job": spec.organ_id,
        "ts": now,
        "status": status,
        "host": host,
        "source": "launchagent-state-bridge",
        "label": spec.label,
    }
    if pid is not None:
        receipt["pid"] = pid
    if exit_code not in (None, 0):
        receipt["exit_code"] = exit_code
    if last_error:
        receipt["last_error"] = last_error
    return receipt


def build_tcp_receipt(spec: TcpProbe, *, now: int, host: str) -> dict[str, Any]:
    target = f"{spec.host}:{spec.port}"
    started = time.monotonic()
    try:
        conn = socket.create_connection(
            (spec.host, spec.port),
            timeout=spec.timeout_seconds,
        )
        conn.close()
    except OSError as exc:
        return {
            "organ_id": spec.organ_id,
            "job": spec.organ_id,
            "ts": now,
            "status": "failed",
            "host": host,
            "source": "launchagent-state-bridge",
            "target": target,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "last_error": f"tcp connect failed: {exc}",
        }

    return {
        "organ_id": spec.organ_id,
        "job": spec.organ_id,
        "ts": now,
        "status": "ok",
        "host": host,
        "source": "launchagent-state-bridge",
        "target": target,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")


def write_receipts(
    agents: dict[str, dict[str, int | None]],
    *,
    last_seen_dir: Path = DEFAULT_LAST_SEEN_DIR,
    legacy_state_dir: Path | None = DEFAULT_LEGACY_STATE_DIR,
    host: str | None = None,
    tcp_probes: tuple[TcpProbe, ...] = BRIDGED_TCP_PROBES,
) -> list[dict[str, Any]]:
    now = int(time.time())
    host_name = host or os.uname().nodename
    receipts: list[dict[str, Any]] = []

    for spec in BRIDGED_LABELS:
        receipt = build_receipt(spec, agents, now=now, host=host_name)
        write_receipt(last_seen_dir / f"{spec.organ_id}.json", receipt)
        if legacy_state_dir is not None and spec.legacy_job_id:
            legacy = dict(receipt)
            legacy["job"] = spec.legacy_job_id
            write_receipt(legacy_state_dir / f"{spec.legacy_job_id}.last.json", legacy)
        receipts.append(receipt)

    for spec in tcp_probes:
        receipt = build_tcp_receipt(spec, now=now, host=host_name)
        write_receipt(last_seen_dir / f"{spec.organ_id}.json", receipt)
        receipts.append(receipt)

    return receipts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launchctl-file")
    parser.add_argument("--last-seen-dir", default=str(DEFAULT_LAST_SEEN_DIR))
    parser.add_argument("--legacy-state-dir", default=str(DEFAULT_LEGACY_STATE_DIR))
    parser.add_argument("--no-legacy", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.launchctl_file:
        agents = parse_launchctl(Path(args.launchctl_file).read_text(encoding="utf-8"))
    else:
        agents = read_launchctl()

    legacy_state_dir = None if args.no_legacy else Path(args.legacy_state_dir).expanduser()
    receipts = write_receipts(
        agents,
        last_seen_dir=Path(args.last_seen_dir).expanduser(),
        legacy_state_dir=legacy_state_dir,
    )
    if args.json:
        print(json.dumps(receipts, indent=2, sort_keys=True))
    else:
        ok = sum(1 for receipt in receipts if receipt["status"] == "ok")
        print(f"[launchagent-state-bridge] Written {len(receipts)} receipts ({ok} ok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "launchagent-state-bridge.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("launchagent_state_bridge", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_launchctl_accepts_whitespace_rows() -> None:
    mod = _load_module()

    result = mod.parse_launchctl(
        "PID\tStatus\tLabel\n"
        "123\t0\tcom.nuzantara.prime-tunnel\n"
        "-\t1\tcom.example.failed\n"
    )

    assert result["com.nuzantara.prime-tunnel"] == {"pid": 123, "exit_code": 0}
    assert result["com.example.failed"] == {"pid": None, "exit_code": 1}


def test_build_receipt_marks_daemon_without_pid_failed() -> None:
    mod = _load_module()
    spec = mod.BridgedLaunchAgent(
        label="com.nuzantara.prime-tunnel",
        organ_id="pro.prime_tunnel",
        daemon=True,
    )

    receipt = mod.build_receipt(
        spec,
        {"com.nuzantara.prime-tunnel": {"pid": None, "exit_code": 0}},
        now=123,
        host="Pro",
    )

    assert receipt["status"] == "failed"
    assert receipt["last_error"] == "daemon not running"


def test_build_receipt_marks_missing_label_failed() -> None:
    mod = _load_module()
    spec = mod.BridgedLaunchAgent(
        label="com.nuzantara.missing",
        organ_id="pro.missing",
        daemon=False,
    )

    receipt = mod.build_receipt(spec, {}, now=123, host="Pro")

    assert receipt["status"] == "failed"
    assert receipt["last_error"] == "label not loaded"


def test_write_receipts_emits_standard_and_legacy_files(tmp_path: Path) -> None:
    mod = _load_module()
    last_seen_dir = tmp_path / "last_seen"
    legacy_dir = tmp_path / "legacy"
    agents = {
        "com.nuzantara.launchagent-state-bridge": {"pid": 111, "exit_code": 0},
        "com.nuzantara.prime-tunnel": {"pid": 222, "exit_code": 0},
        "com.balizero.wr2.pg-proxy": {"pid": 333, "exit_code": 0},
    }

    receipts = mod.write_receipts(
        agents,
        last_seen_dir=last_seen_dir,
        legacy_state_dir=legacy_dir,
        host="Pro",
    )

    assert {
        "pro.launchagent_state_bridge",
        "pro.prime_tunnel",
        "wr2.pg_proxy",
    }.issubset({receipt["organ_id"] for receipt in receipts})
    prime = json.loads((last_seen_dir / "pro.prime_tunnel.json").read_text())
    legacy = json.loads((legacy_dir / "prime_tunnel.last.json").read_text())
    assert prime["status"] == "ok"
    assert prime["source"] == "launchagent-state-bridge"
    assert legacy["job"] == "prime_tunnel"


def test_write_receipts_emits_tcp_probe_files(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    last_seen_dir = tmp_path / "last_seen"
    calls = []

    class DummyConnection:
        def close(self) -> None:
            calls.append("closed")

    def fake_create_connection(target, timeout):
        calls.append((target, timeout))
        return DummyConnection()

    monkeypatch.setattr(mod.socket, "create_connection", fake_create_connection)

    probe = mod.TcpProbe(
        organ_id="infra.eventbus_redis_mini",
        host="100.93.236.6",
        port=6379,
        timeout_seconds=1.5,
    )

    receipts = mod.write_receipts(
        {},
        last_seen_dir=last_seen_dir,
        legacy_state_dir=None,
        host="Pro",
        tcp_probes=(probe,),
    )

    receipt = json.loads((last_seen_dir / "infra.eventbus_redis_mini.json").read_text())
    assert receipt["status"] == "ok"
    assert receipt["target"] == "100.93.236.6:6379"
    assert ("100.93.236.6", 6379) in {call[0] for call in calls if isinstance(call, tuple)}
    assert receipt in receipts


def test_bridge_includes_p0h_running_import_labels() -> None:
    mod = _load_module()

    specs = {spec.organ_id: spec.label for spec in mod.BRIDGED_LABELS}

    assert {
        "pro.cron_log_sentinel": "com.balizero.cron-log-sentinel",
        "pro.eventbus_observatory": "com.balizero.observatory",
        "pro.eventbus_intel_dedup_gateway": "com.balizero.intel-dedup-gateway",
        "pro.eventbus_meta_dispatcher": "com.balizero.meta-dispatcher",
        "pro.eventbus_research_sentinel": "com.balizero.research-sentinel",
        "pro.mos_plus_compression": "com.balizero.mos-plus.compression",
        "pro.audit_launchd_daily": "com.balizero.audit-launchd.daily",
        "intel_lake.e2e_probe_6h": "com.balizero.intel-lake.e2e-probe.6h",
        "pro.nuzantara_drive_sync": "com.balizero.nuzantara-drive-sync",
        "wr2.e2e_probe_daily": "com.balizero.wr2.e2e-probe.daily",
        "wr2.plist_watchdog": "com.balizero.wr2.plist-watchdog",
        "mata_garuda.consumer_lag_check": "com.matagaruda.consumer-lag.check",
        "mata_garuda.redis_split_brain_check": "com.matagaruda.redis-split-brain.check",
        "codex.spark_alarm": "com.nuzantara.codex-spark-alarm",
    "pro.agent_library_evolver_daily": "com.balizero.agent-library-evolver.daily",
    "pro.agent_library_evolver_weekly": "com.balizero.agent-library-evolver.weekly",
    "pro.cicatrix_rotation_monthly": "com.balizero.cicatrix-rotation.monthly",
    "pro.claude_settings_watcher": "com.balizero.claude-settings-watcher",
    "pro.competitor_monitor_monthly": "com.balizero.competitor-monitor.monthly",
    "pro.competitor_signal_router_weekly": "com.balizero.competitor-signal-router.weekly",
    "pro.crm_guardian_cli_worker": "com.balizero.crm-guardian-cli-worker",
    "pro.curiosity_weekly": "com.balizero.curiosity.weekly",
    "pro.fly_cost_alert_weekly": "com.balizero.fly-cost-alert.weekly",
    "intel_lake.nb_pusher_15min": "com.balizero.intel-lake-nb-pusher.15min",
    "intel_lake.router_5min": "com.balizero.intel-lake-router.5min",
    "intel_lake.outbox_drain_minute": "com.balizero.intel-lake.outbox-drain.minute",
    "intel_lake.shadow_validate_6h": "com.balizero.intel-lake.shadow-validate.6h",
    "pro.l5_2_phase2b_trigger": "com.balizero.l5-2-phase2b-trigger",
    "pro.mos_plus_qdrant_indexer": "com.balizero.mos-plus.qdrant-indexer",
    "pro.nextdns_tamper_detect_weekly": "com.balizero.nextdns-tamper-detect.weekly",
    "pro.disk_watchdog": "com.balizero.nuzantara.disk-watchdog",
    "pro.log_size_watchdog": "com.balizero.nuzantara.log-size-watchdog",
    "pro.wa_lid_refresh": "com.balizero.wa-lid-refresh",
    "pro.wa_mirror_attention_classifier": "com.balizero.wa-mirror-attention-classifier",
    "pro.wa_mirror_attention_digest": "com.balizero.wa-mirror-attention-digest",
    "pro.wa_mirror_attention_realtime": "com.balizero.wa-mirror-attention-realtime",
    "pro.wa_mirror_strategic_recap": "com.balizero.wa-mirror-strategic-recap",
    "wr2.canva_gc_weekly": "com.balizero.wr2.canva-gc.weekly",
    "wr2.canva_lease_watchdog_launchd": "com.balizero.wr2.canva-lease-watchdog",
    "wr2.canva_token_watchdog_launchd": "com.balizero.wr2.canva-token-watchdog",
    "wr2.daily_metrics": "com.balizero.wr2.daily-metrics",
    "wr2.external_bench_monthly": "com.balizero.wr2.external-bench.monthly",
    "wr2.ig_metrics_analyst_weekly": "com.balizero.wr2.ig-metrics-analyst.weekly",
    "wr2.pg_queue_sync": "com.balizero.wr2.pg-queue-sync",
    "wr2.worktree_gc_daily": "com.balizero.wr2.worktree-gc.daily",
    "wr3.editorial_bench_monthly": "com.balizero.wr3.editorial-bench.monthly",
    "wr3.reflexion_weekly": "com.balizero.wr3.reflexion.weekly",
    "pro.yield_optimizer_weekly": "com.balizero.yield-optimizer.weekly",
    "mata_garuda.pel_cleaner_weekly": "com.matagaruda.pel-cleaner.weekly",
    "mata_garuda.sentinel_hourly": "com.matagaruda.sentinel.hourly",
    "mata_garuda.unmapped_audit_daily": "com.matagaruda.unmapped-audit.daily",
    "pro.archive_empty_sessions_daily": "com.nuzantara.archive-empty-sessions.daily",
    "pro.branch_cleanup_weekly": "com.nuzantara.branch-cleanup.weekly",
    "codex.openclaw_analysis": "com.nuzantara.codex-openclaw-analysis",
    "codex.spark_harvester": "com.nuzantara.codex-spark-harvester",
    "pro.daily_indexing_sweep_launchd": "com.nuzantara.daily-indexing-sweep",
    "pro.gh_auth_healthcheck_weekly": "com.nuzantara.gh-auth-healthcheck.weekly",
    "pro.openclaw_guardian_board": "com.nuzantara.openclaw.guardian-board",
    "pro.outbox_prune_weekly": "com.nuzantara.outbox-prune.weekly",
    "pro.repomap_15min": "com.nuzantara.repomap.15min",
    "cell.skills_bridge_consumer_launchd": "com.nuzantara.skills-bridge-consumer",
    "pro.worktree_gc_universal_daily": "com.nuzantara.worktree-gc-universal.daily",
        "pro.guardrails_daemon": "com.balizero.guardrails-daemon",
        "pro.nb_curator_daily": "com.balizero.nb-curator.daily",
        "pro.observatory_server": "com.balizero.observatory-server",
        "pro.observatory_export": "com.balizero.observatory-export",
        "pro.profile_monitor_wrapper": "com.balizero.profile-monitor-wrapper",
        "infra.qdrant_pro": "com.balizero.qdrant.daemon",
        "pro.wa_dashboard_m1": "com.balizero.wa-dashboard-m1",
        "pro.wa_meta_inbox": "com.balizero.wa-meta-inbox",
        "pro.wa_mirror_auto_promote": "com.balizero.wa-mirror-auto-promote",
        "pro.wa_mirror_launcher": "com.balizero.wa-mirror-launcher",
        "pro.wa_viewer": "com.balizero.wa-viewer",
        "wr2.carousel_dispatcher": "com.balizero.wr2.carousel-dispatcher",
        "wr2.telegram_gate": "com.balizero.wr2.telegram-gate",
        "wr3.supervisor": "com.balizero.wr3.supervisor",
        "mata_garuda.classifier_adaptive.pro": "com.matagaruda.classifier.adaptive",
        "mata_garuda.ner_adaptive.pro": "com.matagaruda.ner.adaptive",
        "codex.spark_loop": "com.nuzantara.codex-spark-loop",
        "pro.openclaw_whatsapp_bridge": "com.nuzantara.openclaw-whatsapp-bridge",
        "pro.openclaw_whatsapp_tunnel": "com.nuzantara.openclaw-whatsapp-tunnel",
        "infra.local_postgres_pro": "homebrew.mxcl.postgresql@17",
        "infra.syncthing_pro": "homebrew.mxcl.syncthing",
        "infra.ollama_pro": "homebrew.mxcl.ollama",
    }.items() <= specs.items()

    tcp_specs = {spec.organ_id: f"{spec.host}:{spec.port}" for spec in mod.BRIDGED_TCP_PROBES}
    assert tcp_specs["infra.eventbus_redis_mini"] == "100.93.236.6:6379"

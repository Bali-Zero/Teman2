from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "apps/organism/organism/organs_registry.yaml"

EXPECTED_BRIDGES = {
    "wr2.image_generator": {
        "owner_module": "scripts/wr2_image_generator.py",
        "bridge_source": "~/.organism/last_seen/wr2.image_generator.json",
        "source_file": ROOT / "scripts/wr2_image_generator.py",
        "heartbeat_marker": '_write_organism_heartbeat("wr2.image_generator"',
    },
    "wr2.deploy_puller": {
        "owner_module": "scripts/wr2-deploy-pull.sh",
        "bridge_source": "~/.organism/last_seen/wr2.deploy_puller.json",
        "source_file": ROOT / "scripts/wr2-deploy-pull.sh",
        "heartbeat_marker": 'organism_heartbeat "wr2.deploy_puller"',
    },
    "wr2.supervisor_watchdog": {
        "owner_module": "scripts/wr2_supervisor_watchdog.py",
        "bridge_source": "~/.organism/last_seen/wr2.supervisor_watchdog.json",
        "source_file": ROOT / "scripts/wr2_supervisor_watchdog.py",
        "heartbeat_marker": '_write_organism_heartbeat("wr2.supervisor_watchdog"',
    },
    "pro.codex_autofix_ci": {
        "owner_module": "scripts/codex/codex-nightly-autofix-ci.sh",
        "bridge_source": "~/.organism/last_seen/pro.codex_autofix_ci.json",
        "source_file": ROOT / "scripts/codex/codex-nightly-autofix-ci.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.codex_autofix_ci"',
    },
    "pro.automap_watchdog": {
        "owner_module": "scripts/automap/automap_watchdog.py",
        "bridge_source": "~/.organism/last_seen/pro.automap_watchdog.json",
        "source_file": Path.home() / "scripts/automap/automap_watchdog.py",
        "heartbeat_marker": '_write_organism_heartbeat("pro.automap_watchdog"',
        "home_runtime": True,
    },
    "pro.openclaw_children_watchdog": {
        "owner_module": "scripts/openclaw-children-watchdog.sh",
        "bridge_source": "~/.organism/last_seen/pro.openclaw_children_watchdog.json",
        "source_file": Path.home() / "scripts/openclaw-children-watchdog.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.openclaw_children_watchdog"',
        "home_runtime": True,
    },
    "pro.nb_intel_delta_watcher": {
        "owner_module": "scripts/nb-intel-delta-watcher.sh",
        "bridge_source": "~/.organism/last_seen/pro.nb_intel_delta_watcher.json",
        "source_file": Path.home() / "scripts/nb-intel-delta-watcher.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.nb_intel_delta_watcher"',
        "home_runtime": True,
    },
    "wr2.canva_oauth_watchdog": {
        "owner_module": "scripts/wr2-canva-oauth-watchdog.sh",
        "bridge_source": "~/.organism/last_seen/wr2.canva_oauth_watchdog.json",
        "source_file": Path.home() / "scripts/wr2-canva-oauth-watchdog.sh",
        "heartbeat_marker": 'organism_heartbeat "wr2.canva_oauth_watchdog"',
        "home_runtime": True,
    },
    "pro.supervisor_liveness_watchdog": {
        "owner_module": "scripts/supervisor_liveness_watchdog.sh",
        "bridge_source": "~/.organism/last_seen/pro.supervisor_liveness_watchdog.json",
        "source_file": ROOT / "scripts/supervisor_liveness_watchdog.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.supervisor_liveness_watchdog"',
    },
    "cell.observatory_selfcheck": {
        "owner_module": "apps/cell-observatory-collector/scripts/healthcheck.sh",
        "bridge_source": "~/.organism/last_seen/cell.observatory_selfcheck.json",
        "source_file": ROOT / "apps/cell-observatory-collector/scripts/healthcheck.sh",
        "heartbeat_marker": 'organism_heartbeat "cell.observatory_selfcheck"',
    },
    "pro.indexing_sweep_daily": {
        "owner_module": "scripts/daily_indexing_cron_wrapper.sh",
        "bridge_source": "~/.organism/last_seen/pro.indexing_sweep_daily.json",
        "source_file": ROOT / "scripts/daily_indexing_cron_wrapper.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.indexing_sweep_daily"',
    },
    "pro.agent_worktree_cleanup": {
        "owner_module": "scripts/agent_worktree_cleanup_cron.sh",
        "bridge_source": "~/.organism/last_seen/pro.agent_worktree_cleanup.json",
        "source_file": ROOT / "scripts/agent_worktree_cleanup_cron.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.agent_worktree_cleanup"',
    },
    "pro.setup_team_daily": {
        "owner_module": "infra/scripts/setup-team-cron.sh",
        "bridge_source": "~/.organism/last_seen/pro.setup_team_daily.json",
        "source_file": ROOT / "infra/scripts/setup-team-cron.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.setup_team_daily"',
    },
    "pro.launchd_env_loader": {
        "owner_module": "scripts/launchd_env_loader.sh",
        "bridge_source": "~/.organism/last_seen/pro.launchd_env_loader.json",
        "source_file": ROOT / "scripts/launchd_env_loader.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.launchd_env_loader"',
    },
    "pro.openclaw_logrotate": {
        "owner_module": "scripts/openclaw-logrotate.sh",
        "bridge_source": "~/.organism/last_seen/pro.openclaw_logrotate.json",
        "source_file": ROOT / "scripts/openclaw-logrotate.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.openclaw_logrotate"',
    },
    "pro.memory_sync_bidirectional": {
        "owner_module": "scripts/mini-setup/memory-sync-bidirectional.sh",
        "bridge_source": "~/.organism/last_seen/pro.memory_sync_bidirectional.json",
        "source_file": Path.home() / "scripts/mini-setup/memory-sync-bidirectional.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.memory_sync_bidirectional"',
        "home_runtime": True,
    },
    "pro.claude_config_sync": {
        "owner_module": "scripts/mini-setup/claude-config-sync.sh",
        "bridge_source": "~/.organism/last_seen/pro.claude_config_sync.json",
        "source_file": Path.home() / "scripts/mini-setup/claude-config-sync.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.claude_config_sync"',
        "home_runtime": True,
    },
    "pro.seo_cell_daily": {
        "owner_module": "scripts/openclaw-cron/seo-cell-daily.sh",
        "bridge_source": "~/.organism/last_seen/pro.seo_cell_daily.json",
        "source_file": Path.home() / "scripts/openclaw-cron/seo-cell-daily.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.seo_cell_daily"',
        "home_runtime": True,
    },
    "pro.seo_cell_28d_check": {
        "owner_module": "scripts/openclaw-cron/seo-cell-28d-check.sh",
        "bridge_source": "~/.organism/last_seen/pro.seo_cell_28d_check.json",
        "source_file": Path.home() / "scripts/openclaw-cron/seo-cell-28d-check.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.seo_cell_28d_check"',
        "home_runtime": True,
    },
    "pro.bz_daily_visual_pipeline": {
        "owner_module": "scripts/bz-daily-visual-pipeline.sh",
        "bridge_source": "~/.organism/last_seen/pro.bz_daily_visual_pipeline.json",
        "source_file": Path.home() / "scripts/bz-daily-visual-pipeline.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.bz_daily_visual_pipeline"',
        "home_runtime": True,
    },
    "pro.domain_mesh_foundations_daily": {
        "owner_module": "scripts/domain-mesh-foundations-cron.sh",
        "bridge_source": "~/.organism/last_seen/pro.domain_mesh_foundations_daily.json",
        "source_file": Path.home() / "scripts/domain-mesh-foundations-cron.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.domain_mesh_foundations_daily"',
        "home_runtime": True,
    },
    "pro.client_value_predictor": {
        "owner_module": "scripts/openclaw-cron/client-value-predictor.sh",
        "bridge_source": "~/.organism/last_seen/pro.client_value_predictor.json",
        "source_file": Path.home() / "scripts/openclaw-cron/client-value-predictor.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.client_value_predictor"',
        "home_runtime": True,
    },
    "pro.automations_reference": {
        "owner_module": "scripts/generate-automations-all.sh",
        "bridge_source": "~/.organism/last_seen/pro.automations_reference.json",
        "source_file": Path.home() / "scripts/generate-automations-all.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.automations_reference"',
        "home_runtime": True,
    },
    "pro.regulatory_watcher_daily": {
        "owner_module": "scripts/regulatory-watcher-run.sh",
        "bridge_source": "~/.organism/last_seen/pro.regulatory_watcher_daily.json",
        "source_file": Path.home() / "scripts/regulatory-watcher-run.sh",
        "heartbeat_marker": '"pro.regulatory_watcher_daily"',
        "home_runtime": True,
    },
    "sota.m13_checkpoint": {
        "owner_module": "apps/backend-rag/backend/services/sota_loop/m13_checkpoint.py",
        "bridge_source": "~/.organism/last_seen/sota.m13_checkpoint.json",
        "source_file": ROOT / "apps/backend-rag/backend/services/sota_loop/m13_checkpoint.py",
        "heartbeat_marker": 'organism_heartbeat("sota.m13_checkpoint"',
    },
    "sota.m13_collect": {
        "owner_module": "apps/backend-rag/backend/services/sota_loop/m13_collect.py",
        "bridge_source": "~/.organism/last_seen/sota.m13_collect.json",
        "source_file": ROOT / "apps/backend-rag/backend/services/sota_loop/m13_collect.py",
        "heartbeat_marker": 'organism_heartbeat("sota.m13_collect"',
    },
    "sota.m13_monthly": {
        "owner_module": "apps/backend-rag/backend/services/sota_loop/m13_monthly.py",
        "bridge_source": "~/.organism/last_seen/sota.m13_monthly.json",
        "source_file": ROOT / "apps/backend-rag/backend/services/sota_loop/m13_monthly.py",
        "heartbeat_marker": 'organism_heartbeat("sota.m13_monthly"',
    },
    "sota.m13_weekly": {
        "owner_module": "apps/backend-rag/backend/services/sota_loop/m13_weekly.py",
        "bridge_source": "~/.organism/last_seen/sota.m13_weekly.json",
        "source_file": ROOT / "apps/backend-rag/backend/services/sota_loop/m13_weekly.py",
        "heartbeat_marker": 'organism_heartbeat("sota.m13_weekly"',
    },
    "mata_garuda.reg_alert_30min.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_regulation_alert.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.reg_alert_30min.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_regulation_alert.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.reg_alert_30min.pro"',
    },
    "mata_garuda.kg_linker.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_kg_linker.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.kg_linker.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_kg_linker.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.kg_linker.pro"',
    },
    "mata_garuda.wr_topic.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_wr_topic.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.wr_topic.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_wr_topic.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.wr_topic.pro"',
    },
    "mata_garuda.wr2_bridge_hourly.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_wr2_bridge.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.wr2_bridge_hourly.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_wr2_bridge.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.wr2_bridge_hourly.pro"',
    },
    "mata_garuda.intel_bridge_daily.mini": {
        "owner_module": "apps/mata-garuda/scripts/run_intel_bridge.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.intel_bridge_daily.mini.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_intel_bridge.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.intel_bridge_daily.mini"',
    },
    "mata_garuda.daily_briefing.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_daily_briefing.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.daily_briefing.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_daily_briefing.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.daily_briefing.pro"',
    },
    "mata_garuda.kita_feed_daily.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_kita_feed.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.kita_feed_daily.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_kita_feed.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.kita_feed_daily.pro"',
    },
    "mata_garuda.public_channel.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_public_channel.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.public_channel.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_public_channel.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.public_channel.pro"',
    },
    "mata_garuda.weekly_digest.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_weekly_digest.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.weekly_digest.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_weekly_digest.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.weekly_digest.pro"',
    },
    "mata_garuda.gap_consumer.pro": {
        "owner_module": "apps/mata-garuda/mata_garuda/workers/gap_consumer.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.gap_consumer.pro.json",
        "source_file": ROOT / "apps/mata-garuda/mata_garuda/workers/gap_consumer.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.gap_consumer.pro"',
    },
    "mata_garuda.nlm_feeder_stream_hourly.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_nlm_feeder_stream.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.nlm_feeder_stream_hourly.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_nlm_feeder_stream.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.nlm_feeder_stream_hourly.pro"',
    },
    "mata_garuda.nlm_expander_weekly.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_nlm_expander.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.nlm_expander_weekly.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_nlm_expander.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.nlm_expander_weekly.pro"',
    },
    "mata_garuda.ner_worker_hourly.mini": {
        "owner_module": "apps/mata-garuda/scripts/run_ner_worker.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.ner_worker_hourly.mini.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_ner_worker.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.ner_worker_hourly.mini"',
    },
    "mata_garuda.normalizer_hourly.mini": {
        "owner_module": "apps/mata-garuda/scripts/run_normalizer.py",
        "bridge_source": "~/.organism/last_seen/mata_garuda.normalizer_hourly.mini.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_normalizer.py",
        "heartbeat_marker": 'run_with_heartbeat("mata_garuda.normalizer_hourly.mini"',
    },
    "pro.nb_mitochondrial_monitor_daily": {
        "owner_module": "apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py",
        "bridge_source": "~/.organism/last_seen/pro.nb_mitochondrial_monitor_daily.json",
        "source_file": ROOT / "apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py",
        "heartbeat_marker": 'run_with_heartbeat("pro.nb_mitochondrial_monitor_daily"',
    },
    "pro.cost_advisor_daily_cap": {
        "owner_module": "apps/backend-rag/backend/scripts/cost_advisor_cli.py",
        "bridge_source": "~/.organism/last_seen/pro.cost_advisor_daily_cap.json",
        "source_file": ROOT / "apps/backend-rag/backend/scripts/cost_advisor_cli.py",
        "heartbeat_marker": '"pro.cost_advisor_daily_cap"',
    },
    "cell.observatory_prune": {
        "owner_module": "apps/cell-observatory-collector/cell_observatory/prune.py",
        "bridge_source": "~/.organism/last_seen/cell.observatory_prune.json",
        "source_file": ROOT / "apps/cell-observatory-collector/cell_observatory/prune.py",
        "heartbeat_marker": 'organism_heartbeat("cell.observatory_prune"',
    },
    "pro.post_publish_poller": {
        "owner_module": "apps/bali-intel-scraper/scripts/post_publish_poller.py",
        "bridge_source": "~/.organism/last_seen/pro.post_publish_poller.json",
        "source_file": ROOT / "apps/bali-intel-scraper/scripts/post_publish_poller.py",
        "heartbeat_marker": 'organism_heartbeat(organ_id, status, note)',
    },
    "pro.cost_advisor_weekly": {
        "owner_module": "apps/backend-rag/backend/scripts/cost_advisor_cli.py",
        "bridge_source": "~/.organism/last_seen/pro.cost_advisor_weekly.json",
        "source_file": ROOT / "apps/backend-rag/backend/scripts/cost_advisor_cli.py",
        "heartbeat_marker": '"pro.cost_advisor_weekly"',
    },
    "organism.scheduled_tick": {
        "owner_module": "apps/organism/organism/scheduled_tick.py",
        "bridge_source": "~/.organism/last_seen/organism.scheduled_tick.json",
        "source_file": ROOT / "apps/organism/organism/scheduled_tick.py",
        "heartbeat_marker": 'organism_heartbeat("organism.scheduled_tick"',
    },
    "wr2.canva_apply": {
        "owner_module": "scripts/wr2_canva_desktop_apply.py",
        "bridge_source": "~/.organism/last_seen/wr2.canva_apply.json",
        "source_file": ROOT / "scripts/wr2_canva_desktop_apply.py",
        "heartbeat_marker": 'ORGAN_ID = "wr2.canva_apply"',
    },
    "pro.launchagent_state_bridge": {
        "owner_module": "scripts/launchagent-state-bridge.py",
        "bridge_source": "~/.organism/last_seen/pro.launchagent_state_bridge.json",
        "source_file": ROOT / "scripts/launchagent-state-bridge.py",
        "heartbeat_marker": '"pro.launchagent_state_bridge"',
    },
    "pro.intel_radar_daily_digest": {
        "owner_module": "scripts/cron-agent-python/intel_radar_daily_digest.py",
        "bridge_source": "~/.cron-agent-python/intel-radar-daily-digest.state.json",
        "source_file": Path.home() / "scripts/cron-agent-python/intel_radar_daily_digest.py",
        "heartbeat_marker": 'name = "intel-radar-daily-digest"',
        "home_runtime": True,
    },
    "pro.ollama_warm_pin": {
        "owner_module": "scripts/ollama-warm-pin.sh",
        "bridge_source": "~/.organism/last_seen/pro.ollama_warm_pin.json",
        "source_file": ROOT / "scripts/ollama-warm-pin.sh",
        "heartbeat_marker": 'ORGAN_ID="pro.ollama_warm_pin"',
    },
    "pro.vector_reindex_check": {
        "owner_module": "scripts/vector-reindex-check.py",
        "bridge_source": "~/.agent/decisions/state/vector_reindex_check.last.json",
        "source_file": Path.home() / "scripts/vector-reindex-check.py",
        "heartbeat_marker": '"vector_reindex_check"',
        "home_runtime": True,
    },
    "wr2.ig_scraper_daily": {
        "owner_module": ".claude/skills/bali-zero-brand/_ig-metrics-scraper.py",
        "bridge_source": "~/.organism/last_seen/wr2.ig_scraper_daily.json",
        "source_file": Path.home() / ".claude/skills/bali-zero-brand/_ig-metrics-scraper.py",
        "heartbeat_marker": 'organism_heartbeat(organ_id, status, f"rc={rc}")',
        "home_runtime": True,
    },
    "wr2.queue_server": {
        "owner_module": ".claude/skills/bali-zero-brand/_damar-queue-server.py",
        "bridge_source": "~/.organism/last_seen/wr2.queue_server.json",
        "source_file": Path.home() / ".claude/skills/bali-zero-brand/_damar-queue-server.py",
        "heartbeat_marker": 'organism_heartbeat("wr2.queue_server", "ok", "queue server alive")',
        "home_runtime": True,
    },
    "wr2.reflexion_weekly": {
        "owner_module": ".claude/skills/bali-zero-brand/_reflexion-synthesis.py",
        "bridge_source": "~/.organism/last_seen/wr2.reflexion_weekly.json",
        "source_file": Path.home() / ".claude/skills/bali-zero-brand/_reflexion-synthesis.py",
        "heartbeat_marker": 'organism_heartbeat(organ_id, status, f"rc={rc}")',
        "home_runtime": True,
    },
    "wr2.voyager_weekly": {
        "owner_module": ".claude/skills/bali-zero-brand/_voyager-curriculum.py",
        "bridge_source": "~/.organism/last_seen/wr2.voyager_weekly.json",
        "source_file": Path.home() / ".claude/skills/bali-zero-brand/_voyager-curriculum.py",
        "heartbeat_marker": 'organism_heartbeat(organ_id, status, f"rc={rc}")',
        "home_runtime": True,
    },
    "backend.api": {
        "owner_module": "apps/backend-rag/backend/app/main.py",
        "bridge_source": "https://kita.balizero.com/health",
        "bridge_type": "http",
        "source_file": ROOT / "apps/backend-rag/backend/app/routers/health.py",
        "heartbeat_marker": "async def health_check",
    },
    "backend.surface_router": {
        "owner_module": "apps/backend-rag/backend/services/routing/surface_router.py",
        "bridge_source": "https://kita.balizero.com/health/detailed",
        "bridge_type": "http",
        "source_file": ROOT / "apps/backend-rag/backend/app/routers/health.py",
        "heartbeat_marker": 'services["router"]',
    },
    "mata_garuda.watcher_daily.pro": {
        "owner_module": "apps/mata-garuda/scripts/run_watcher.sh",
        "bridge_source": "~/.organism/last_seen/mata_garuda.watcher_daily.pro.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_watcher.sh",
        "heartbeat_marker": 'organism_heartbeat "mata_garuda.watcher_daily.pro"',
    },
    "nlm.bridge": {
        "owner_module": "apps/nlm-bridge/main.py",
        "bridge_source": "http://127.0.0.1:18790/nlm/health",
        "bridge_type": "http",
        "source_file": ROOT / "apps/nlm-bridge/main.py",
        "heartbeat_marker": '@app.get("/nlm/health"',
    },
    "pro.automap_server": {
        "owner_module": "scripts/automap/automap_server.py",
        "bridge_source": "http://127.0.0.1:18791/health",
        "bridge_type": "http",
        "source_file": Path.home() / "scripts/automap/automap_server.py",
        "heartbeat_marker": 'path == "/health"',
        "home_runtime": True,
    },
    "pro.automap_telegram": {
        "owner_module": "scripts/automap/automap_telegram.py",
        "bridge_source": "~/.organism/last_seen/pro.automap_telegram.json",
        "source_file": Path.home() / "scripts/automap/automap_telegram.py",
        "heartbeat_marker": 'organism_heartbeat("pro.automap_telegram"',
        "home_runtime": True,
    },
    "organism.supervisor": {
        "owner_module": "apps/organism/organism/supervisor/daemon.py",
        "bridge_source": "~/.organism/last_seen/organism.supervisor.json",
        "source_file": ROOT / "apps/organism/organism/supervisor/daemon.py",
        "heartbeat_marker": 'organism_heartbeat("organism.supervisor"',
    },
    "pro.heartbeat_bridge": {
        "owner_module": "apps/cell/scripts/launch_heartbeat_bridge.sh",
        "bridge_source": "~/.organism/last_seen/pro.heartbeat_bridge.json",
        "source_file": ROOT / "apps/cell/scripts/heartbeat_bridge_loop.py",
        "heartbeat_marker": 'organism_heartbeat("pro.heartbeat_bridge"',
    },
    "pro.post_publish_webhook": {
        "owner_module": "apps/bali-intel-scraper/scripts/post_publish_webhook.py",
        "bridge_source": "~/.organism/last_seen/pro.post_publish_webhook.json",
        "source_file": ROOT / "apps/bali-intel-scraper/scripts/post_publish_webhook.py",
        "heartbeat_marker": 'organism_heartbeat("pro.post_publish_webhook"',
    },
    "infra.postgres": {
        "owner_module": "infra/fly/nuzantara-postgres",
        "bridge_source": "https://kita.balizero.com/health/detailed",
        "bridge_type": "http",
        "source_file": ROOT / "apps/backend-rag/backend/app/routers/health.py",
        "heartbeat_marker": 'services["database"]',
    },
    "infra.redis": {
        "owner_module": "brew/redis",
        "bridge_source": "https://kita.balizero.com/health/detailed",
        "bridge_type": "http",
        "source_file": ROOT / "apps/backend-rag/backend/app/routers/health.py",
        "heartbeat_marker": 'services["redis"]',
    },
    "infra.qdrant": {
        "owner_module": "infra/fly/nuzantara-qdrant",
        "bridge_source": "https://kita.balizero.com/health/detailed",
        "bridge_type": "http",
        "source_file": ROOT / "apps/backend-rag/backend/app/routers/health.py",
        "heartbeat_marker": 'services["search"]',
    },
    "infra.pg_organism_bridge_watchdog": {
        "owner_module": "infra/scripts/pg-organism-bridge-watchdog.sh",
        "bridge_source": "~/.organism/last_seen/infra.pg_organism_bridge_watchdog.json",
        "source_file": ROOT / "infra/scripts/pg-organism-bridge-watchdog.sh",
        "heartbeat_marker": 'organism_heartbeat "$ORGAN_ID"',
    },
    "mata_garuda.bridge_adaptive.pro": {
        "owner_module": "scripts/matagaruda-bridge.sh",
        "bridge_source": "~/.organism/last_seen/mata_garuda.bridge_adaptive.pro.json",
        "source_file": Path.home() / "scripts/matagaruda-bridge.sh",
        "heartbeat_marker": 'ORGAN_ID="mata_garuda.bridge_adaptive.pro"',
        "home_runtime": True,
    },
    "mata_garuda.sentinel_daily.mini": {
        "owner_module": "apps/mata-garuda/scripts/run_sentinel.sh",
        "bridge_source": "~/.organism/last_seen/mata_garuda.sentinel_daily.mini.json",
        "source_file": ROOT / "apps/mata-garuda/scripts/run_sentinel.sh",
        "heartbeat_marker": 'ORGAN_ID="mata_garuda.sentinel_daily.mini"',
    },
    "mata_garuda.invalidation_sweep.pro": {
        "owner_module": "scripts/mata_garuda_invalidation_sweep_wrapper.sh",
        "bridge_source": "~/.organism/last_seen/mata_garuda.invalidation_sweep.pro.json",
        "source_file": ROOT / "scripts/mata_garuda_invalidation_sweep_wrapper.sh",
        "heartbeat_marker": 'organism_heartbeat "mata_garuda.invalidation_sweep.pro"',
    },
    "wr2.connector": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.connector.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.connector"',
    },
    "wr2.dossier_compiler": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.dossier_compiler.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.dossier_compiler"',
    },
    "wr2.draft_generator": {
        "owner_module": "scripts/wr2_draft_generator.py",
        "bridge_source": "~/.organism/last_seen/wr2.draft_generator.json",
        "source_file": ROOT / "scripts/wr2_draft_generator.py",
        "heartbeat_marker": '_run_with_heartbeat("wr2.draft_generator"',
    },
    "wr2.hardening": {
        "owner_module": "scripts/wr2-hardening-chain.sh",
        "bridge_source": "~/.organism/last_seen/wr2.hardening.json",
        "source_file": ROOT / "scripts/wr2-hardening-chain.sh",
        "heartbeat_marker": 'organism_heartbeat "wr2.hardening"',
    },
    "wr2.learner_nightly": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.learner_nightly.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.learner_nightly"',
    },
    "wr2.measurer": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.measurer.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.measurer"',
    },
    "wr2.pg_proxy": {
        "owner_module": "infra/launchagents/com.balizero.wr2.pg-proxy.plist",
        "bridge_source": "~/.organism/last_seen/wr2.pg_proxy.json",
        "source_file": ROOT / "infra/launchagents/com.balizero.wr2.pg-proxy.plist",
        "heartbeat_file": ROOT / "scripts/launchagent-state-bridge.py",
        "heartbeat_marker": '"com.balizero.wr2.pg-proxy"',
    },
    "wr2.sla_worker": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.sla_worker.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.sla_worker"',
    },
    "wr2.strategos": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.strategos.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.strategos"',
    },
    "wr2.topic_selector": {
        "owner_module": "scripts/wr2_topic_selector.py",
        "bridge_source": "~/.organism/last_seen/wr2.topic_selector.json",
        "source_file": ROOT / "scripts/wr2_topic_selector.py",
        "heartbeat_marker": '_run_with_heartbeat("wr2.topic_selector"',
    },
    "wr2.trend_hunter": {
        "owner_module": "scripts/wr2-cron-wrapper.sh",
        "bridge_source": "~/.organism/last_seen/wr2.trend_hunter.json",
        "source_file": ROOT / "scripts/wr2-cron-wrapper.sh",
        "heartbeat_marker": 'ORGANISM_HB_ID="wr2.trend_hunter"',
    },
    "pro.codex_overnight_runner": {
        "owner_module": "scripts/codex/codex-overnight-runner.sh",
        "bridge_source": "~/.organism/last_seen/pro.codex_overnight_runner.json",
        "source_file": ROOT / "scripts/codex/codex-overnight-runner.sh",
        "heartbeat_marker": 'organism_heartbeat "pro.codex_overnight_runner"',
    },
    "pro.sentinel_meta_watchdog": {
        "owner_module": "scripts/sentinel_meta_watchdog.sh",
        "bridge_source": "~/.organism/last_seen/pro.sentinel_meta_watchdog.json",
        "source_file": ROOT / "scripts/sentinel_meta_watchdog.sh",
        "heartbeat_marker": 'ORGAN_ID="pro.sentinel_meta_watchdog"',
    },
    "pro.federation_alert_dispatcher": {
        "owner_module": "apps/backend-rag/backend/scripts/federation_alert_daemon.py",
        "bridge_source": "~/.organism/last_seen/pro.federation_alert_dispatcher.json",
        "source_file": ROOT / "apps/backend-rag/backend/scripts/federation_alert_daemon.py",
        "heartbeat_marker": 'ORGAN_ID = "pro.federation_alert_dispatcher"',
    },
    "pro.secrets_sync_mini": {
        "owner_module": "scripts/mini-setup/secrets-sync-cron.sh",
        "bridge_source": "~/.organism/last_seen/pro.secrets_sync_mini.json",
        "source_file": Path.home() / "scripts/mini-setup/secrets-sync-cron.sh",
        "heartbeat_marker": 'ORGAN_ID="pro.secrets_sync_mini"',
        "home_runtime": True,
    },
    "wr2.fact_checker": {
        "owner_module": "scripts/wr2_fact_checker.py",
        "bridge_source": "~/.organism/last_seen/wr2.fact_checker.json",
        "source_file": ROOT / "scripts/wr2_fact_checker.py",
        "heartbeat_marker": '_run_with_heartbeat("wr2.fact_checker"',
    },
    "wr2.fact_extractor": {
        "owner_module": "scripts/wr2_fact_extractor.py",
        "bridge_source": "~/.organism/last_seen/wr2.fact_extractor.json",
        "source_file": ROOT / "scripts/wr2_fact_extractor.py",
        "heartbeat_marker": '_run_with_heartbeat("wr2.fact_extractor"',
    },
    "codex.spalla_calibrate": {
        "owner_module": "scripts/codex/spalla-calibrate.sh",
        "bridge_source": "~/.organism/last_seen/codex.spalla_calibrate.json",
        "source_file": Path.home() / "scripts/codex/spalla-calibrate.sh",
        "heartbeat_marker": 'organism_heartbeat "codex.spalla_calibrate"',
        "home_runtime": True,
    },
    "codex.coverage_improver": {
        "owner_module": "scripts/codex/codex-nightly-coverage-improver.sh",
        "bridge_source": "~/.organism/last_seen/codex.coverage_improver.json",
        "source_file": ROOT / "scripts/codex/codex-nightly-coverage-improver.sh",
        "heartbeat_marker": 'organism_heartbeat "codex.coverage_improver"',
    },
    "codex.overnight_feeder": {
        "owner_module": "scripts/codex/codex-overnight-queue-feeder.sh",
        "bridge_source": "~/.organism/last_seen/codex.overnight_feeder.json",
        "source_file": ROOT / "scripts/codex/codex-overnight-queue-feeder.sh",
        "heartbeat_marker": 'organism_heartbeat "codex.overnight_feeder"',
    },
    "codex.research_actor": {
        "owner_module": "scripts/codex/codex-daily-research-actor.sh",
        "bridge_source": "~/.organism/last_seen/codex.research_actor.json",
        "source_file": ROOT / "scripts/codex/codex-daily-research-actor.sh",
        "heartbeat_marker": 'organism_heartbeat "codex.research_actor"',
    },
    "pro.prime_tunnel": {
        "owner_module": "scripts/launchagent-state-bridge.py",
        "bridge_source": "~/.organism/last_seen/pro.prime_tunnel.json",
        "source_file": ROOT / "scripts/launchagent-state-bridge.py",
        "heartbeat_marker": '"com.nuzantara.prime-tunnel"',
    },
}

P0H_LAUNCHAGENT_BRIDGED_LABELS = {
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
}


def _registry_organ(organ_id: str) -> dict:
    data = yaml.safe_load(REGISTRY.read_text())
    for organ in data["organs"]:
        if organ["id"] == organ_id:
            return organ
    raise AssertionError(f"{organ_id} missing from registry")


def _registry_data() -> dict:
    return yaml.safe_load(REGISTRY.read_text())


def test_registry_declares_bridge_sources_for_closed_p0_wave() -> None:
    for organ_id, expected in EXPECTED_BRIDGES.items():
        organ = _registry_organ(organ_id)
        assert organ["owner_module"] == expected["owner_module"]
        assert "bridge_source" in organ
        bridge_type = expected.get("bridge_type", "state_file")
        assert organ["bridge_source"]["type"] == bridge_type
        assert organ["bridge_source"]["path"] == expected["bridge_source"]


def test_p0h_running_launchagents_are_registry_bridged() -> None:
    bridge_source = (ROOT / "scripts/launchagent-state-bridge.py").read_text()

    for organ_id, label in P0H_LAUNCHAGENT_BRIDGED_LABELS.items():
        organ = _registry_organ(organ_id)
        assert organ["recovery_params"]["label"] == label
        assert organ["owner_module"]
        assert organ["bridge_source"] == {
            "type": "state_file",
            "path": f"~/.organism/last_seen/{organ_id}.json",
            "timestamp_field": "ts",
            "status_field": "status",
        }
        assert label in bridge_source
        assert f'organ_id="{organ_id}"' in bridge_source


def test_registry_owner_modules_exist_for_closed_p0_wave() -> None:
    for expected in EXPECTED_BRIDGES.values():
        if expected.get("home_runtime") and not expected["source_file"].exists():
            continue
        assert expected["source_file"].exists()


def test_closed_p0_wave_scripts_emit_organism_heartbeat() -> None:
    for expected in EXPECTED_BRIDGES.values():
        heartbeat_file = expected.get("heartbeat_file", expected["source_file"])
        if expected.get("home_runtime") and not heartbeat_file.exists():
            continue
        source = heartbeat_file.read_text()
        assert expected["heartbeat_marker"] in source


def test_all_enabled_organs_have_bridge_source() -> None:
    data = _registry_data()
    missing = [
        organ["id"]
        for organ in data["organs"]
        if organ.get("enabled") is not False and not isinstance(organ.get("bridge_source"), dict)
    ]
    assert missing == []


def test_all_enabled_bridge_sources_are_supported_by_consumers() -> None:
    data = _registry_data()
    unsupported = []
    http_without_path = []
    state_file_without_path = []
    for organ in data["organs"]:
        if organ.get("enabled") is False:
            continue
        bridge = organ.get("bridge_source")
        if not isinstance(bridge, dict):
            continue
        bridge_type = bridge.get("type")
        if bridge_type not in {"state_file", "http"}:
            unsupported.append((organ["id"], bridge_type))
            continue
        if bridge_type == "http" and not bridge.get("path"):
            http_without_path.append(organ["id"])
        if bridge_type == "state_file" and not bridge.get("path"):
            state_file_without_path.append(organ["id"])

    assert unsupported == []
    assert http_without_path == []
    assert state_file_without_path == []

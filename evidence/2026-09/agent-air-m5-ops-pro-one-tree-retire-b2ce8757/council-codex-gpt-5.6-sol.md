1. [scripts/runtime-reconcile.sh:112](/Users/balizero/nuzantara/scripts/runtime-reconcile.sh:112) — clean: `runtime_exists` is initialized before every read; no removed variable remains.

2. [infra/launchagents/wrappers/pro-git-pull-main.sh:67](/Users/balizero/nuzantara/infra/launchagents/wrappers/pro-git-pull-main.sh:67) — `RC` and the empty-snapshot trap are clean. But executing the temporary copy changes `$0`, so [scripts/pro/pro-git-pull.sh:67](/Users/balizero/nuzantara/scripts/pro/pro-git-pull.sh:67) resolves `SELF_DIR` under `/tmp`; consequently the allowlist and Telegram gateway paths at lines 83 and 103 disappear, disabling protected-file handling and alerts.

3. [infra/launchagents/com.balizero.nuzantara.log-size-watchdog.plist:45](/Users/balizero/nuzantara/infra/launchagents/com.balizero.nuzantara.log-size-watchdog.plist:45) — clean: once A and B are identical, the executable test changes no resulting behavior.

4. [scripts/runtime-reconcile.sh:162](/Users/balizero/nuzantara/scripts/runtime-reconcile.sh:162) — a multiline `<string>\nexec /Users/nuzantara/nuzantara-deploy/…\n</string>` executes but evades the line-based regex. A harmless `StandardOutPath` containing `nuzantara-deploy` matches and causes recurring false pages.

5. [scripts/cost_breaker_run.sh:24](/Users/balizero/nuzantara/scripts/cost_breaker_run.sh:24) and [scripts/cost_ledger_export_run.sh:20](/Users/balizero/nuzantara/scripts/cost_ledger_export_run.sh:20) still default internally to the retired checkout, so the repointed LaunchAgents immediately fail. Also, [scripts/runtime-reconcile.sh:140](/Users/balizero/nuzantara/scripts/runtime-reconcile.sh:140) treats heartbeat freshness as pull freshness; a permanently hung payload causes later ticks to emit fresh `status=ok` “previous run alive” heartbeats at [pro-git-pull-main.sh:44](/Users/balizero/nuzantara/infra/launchagents/wrappers/pro-git-pull-main.sh:44), hiding the dead puller.
   hook: Stop
   hook: Stop Completed
   tokens used
   96.550
6. [scripts/runtime-reconcile.sh:112](/Users/balizero/nuzantara/scripts/runtime-reconcile.sh:112) — clean: `runtime_exists` is initialized before every read; no removed variable remains.

7. [infra/launchagents/wrappers/pro-git-pull-main.sh:67](/Users/balizero/nuzantara/infra/launchagents/wrappers/pro-git-pull-main.sh:67) — `RC` and the empty-snapshot trap are clean. But executing the temporary copy changes `$0`, so [scripts/pro/pro-git-pull.sh:67](/Users/balizero/nuzantara/scripts/pro/pro-git-pull.sh:67) resolves `SELF_DIR` under `/tmp`; consequently the allowlist and Telegram gateway paths at lines 83 and 103 disappear, disabling protected-file handling and alerts.

8. [infra/launchagents/com.balizero.nuzantara.log-size-watchdog.plist:45](/Users/balizero/nuzantara/infra/launchagents/com.balizero.nuzantara.log-size-watchdog.plist:45) — clean: once A and B are identical, the executable test changes no resulting behavior.

9. [scripts/runtime-reconcile.sh:162](/Users/balizero/nuzantara/scripts/runtime-reconcile.sh:162) — a multiline `<string>\nexec /Users/nuzantara/nuzantara-deploy/…\n</string>` executes but evades the line-based regex. A harmless `StandardOutPath` containing `nuzantara-deploy` matches and causes recurring false pages.

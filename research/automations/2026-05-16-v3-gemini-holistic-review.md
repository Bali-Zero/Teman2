---
date: 2026-05-16
domain: automations
reviewer: gemini-3.1-pro
---

This is a comprehensive review of the `v3` automation cleanup plan against the `v2` BLOCK verdict and holistic execution safety.

### A. Internal Consistency & Architecture
The v3 plan demonstrates a massive leap in maturity. The state-management architecture (`~/.automation-cleanup-2026-05-16/`) provides an excellent, centralized paper trail. The rollback alignment is consistent, utilizing CTE snapshots with `FOR UPDATE` and `FOR SHARE` locks to ensure atomicity. 
However, there is one critical consistency flaw: **The TTL sentinel scheduled in F0.6 (`at now + 4 hours`) is never cancelled.** Phase 9 (Post-cleanup verification) lacks an `atrm` command. 

### B. Coverage of v2 BLOCK Findings
The plan rigorously tackles the v2 reviewer objections:
*   **K1 (crontab wipe): ADDRESSED.** Bare `crontab -` pipes are eradicated in favor of one-shot LaunchAgents and atomic temporary files.
*   **K6 (Telegram alert trap): ADDRESSED.** Superb empirical discovery. Identifying that `alert_dispatcher_enabled` doesn't exist and targeting `federation_alert_mode` is correct. The decision to **skip bootout** for the 25 direct-senders is operationally sound; killing watchdogs during a massive cleanup is a recipe for a blind outage.
*   **K7 (canva rollback): ADDRESSED.** Unconditional `true` is replaced with `$PRIOR_RENDERER` snapshot.
*   **H1-H11 & Regressions: ADDRESSED.** 
    *   **H3** uses the verbatim README validator path.
    *   **H6** adds the grandfathered `Test:` citation stub.
    *   **H7** correctly enumerates Telegram-direct senders dynamically at F1.2.
    *   **H9 & F6.2** were smartly **DROPPED-WITH-RATIONALE** to a follow-up PR to enforce Symbiosis L4 via TDD rather than documentation-only bypasses.
    *   **F2.3** watchdog script is now correctly placed in `infra/scripts/` for Git tracking.

### C. Missing Controls
*   **Dry-run:** Well integrated. The Mini-touching phases are gated by `ssh` reachability checks, and complex AIL decisions (like F8.1/F8.2) rely on 24h log diffs *before* action.
*   **Post-cleanup audit:** Phase 9 metrics extraction is solid.
*   **Missing teardown:** As noted, the failure to tear down the F0.6 TTL sentinel means a rogue background job is left ticking. 

### D. Real-World Execution Risk (Friday Afternoon Scenario)
If executed on a Friday afternoon, the immediate risk stems from the **uncancelled TTL sentinel**. 
Imagine the cleanup finishes successfully in 2 hours. Antonello verifies everything, commits, and logs off. Two hours later (at the +4h mark), the `at` job fires. It blindly runs the `UPDATE system_settings SET value='$PRIOR_FAM'` query. While resetting to the prior value might align with the cleanup's end-state, if Antonello or another system made intentional adjustments post-cleanup, this ghost job will overwrite them silently.

Furthermore, the check for `atrun` in F0.5 might not be sufficient if macOS SIP (System Integrity Protection) or Privacy & Security settings block `at` execution entirely, despite the daemon being loaded. 

### Final Assessment
**REJECT**

**Top Concerns:**
1.  **Timebomb Sentinel (F0.6 / F9):** Phase 9 *must* include `atrm $(cat $DATED_BACKUP/state/at-schedule.txt | awk '{print $1}')` to defuse the 4-hour TTL sentinel upon successful completion. You cannot leave an automated state-revert job scheduled after the cleanup successfully finishes.
2.  **macOS `atrun` unreliability:** Modern macOS heavily deprecates `at`. F0.5 should ideally run a benign test job (`echo "test" | at now + 1 minute`) to definitively prove `at` works, rather than just checking if the daemon is loaded, to prevent a false sense of security regarding the TTL fallback.

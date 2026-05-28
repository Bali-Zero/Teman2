# Codex autofix-ci exit 128 triage

Date: 2026-05-28

## Live finding

`com.nuzantara.codex-autofix-ci` was exiting with code 128 after selecting a failed GitHub Actions run whose source branch no longer existed on `origin`.

Latest observed failure:

- run: `26558623369`
- workflow: `Security Scanning`
- branch: `agent/nuzantara/backend-rag/inbox-admin-gate-2026-05-28`
- log signature: `fatal: couldn't find remote ref agent/nuzantara/backend-rag/inbox-admin-gate-2026-05-28`

## One-pass checks

1. State freshness and corruption:

   ```bash
   jq . ~/.agent/decisions/state/codex_com_nuzantara_codex_autofix_ci.state.json
   tail -20 ~/.agent/decisions/state/codex_autofix_ci.state
   cat ~/.agent/decisions/state/codex_autofix_ci_count_$(date +%F)
   ```

2. Latest error signature:

   ```bash
   tail -120 ~/logs/codex-autofix-ci/launchd.err.log
   tail -160 ~/logs/codex-autofix-ci/launchd.out.log
   tail -160 ~/logs/codex-autofix-ci/run-*.log
   ```

3. Restart and guard conditions:

   ```bash
   launchctl print gui/$(id -u)/com.nuzantara.codex-autofix-ci | sed -n '1,120p'
   CODEX_AUTOFIX_DRY_RUN=1 ~/scripts/codex/nightly-autofix-ci.sh
   ```

## Remediation applied

The fetch/checkout/reset stage now treats deleted, un-fetchable, or un-resettable source branches as skipped outcomes and exits `0`. The daily cap and attempt state are written only after workflow logs are fetched and the failing source commit is checked out successfully, immediately before Codex is launched.

This keeps dedupe key reuse intact for real Codex attempts while avoiding stale `attempt_started` state for runs that cannot be checked out.

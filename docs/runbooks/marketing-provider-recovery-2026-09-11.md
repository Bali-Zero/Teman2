# Marketing provider recovery evidence — 2026-09-11

Mandate: `01a08dfd-9561-7300-9353-331250cfed7e`. BLUE; external builder,
prepare-only. Damar authorized runtime recovery and a durable repair, with no
article publication. No merge, auto-merge arming, code deployment or message
to a third party was performed.

## Observed cause and live recovery

- Mini and Pro started at `b534a71972`.
- The real bridge call `newsroom_fact_gate` for
  `news_20260909_173558_cb32eac2` returned provider unavailable, not a verdict.
- Pro's provider log identified `nlm` exiting nonzero with expired credentials.
  A direct `nlm login --check` under the verifier environment exited 2 and
  confirmed expired authentication. Two bounded official login attempts using
  the existing profile exited 1; interactive operator recovery remains open.
- Two tunnel processes used the same marketing profile. One belonged to the
  existing launchd job, already configured with `KeepAlive` and `RunAtLoad`.
  The other was tracked by `tunnel-client runtimes`.
- Stopped only the confirmed duplicate through `runtimes stop`, then restarted
  the existing launchd job. Confirmed one marketing process, both local health
  endpoints healthy, and a real bridge `workspace_health` response with
  `ok=true`, `ready=true`, `backend_reachable=true` at 03:14:59 UTC.
  The previously configured write flag was preserved.
- The alias tracker now says stopped while the launchd service is healthy.
  Do not use that stale ownership signal to create a second process.
- A real independent-reviewer probe returned valid JSON and a valid verdict.
  It was a synthetic provider probe, not the requested article's fact gate.

## Candidate and validation

Branch: `agent/mini-pro2/infra/marketing-provider-recovery`.
Dedicated worktree on each machine:
`/Users/nuzantara/nuzantara/.worktrees/infra-marketing-provider-recovery`.
The Pro copy is an isolated test checkout; the live server still uses main.

- Known provider authentication failures return fixed actionable messages.
  Provider logs carry only provider, exit code and closed status, not output.
- `workspace_health.editorial_verification` makes bounded real authentication
  checks with the same isolated verifier environments. It separates these
  checks from the News Room contract and explicitly reports `verdict: not_run`.
- The installer refuses to create another runtime when the launchd job is
  already loaded, before changing configuration or reading a runtime key.
- On Pro, 81 tests passed across `test_editorial_provider_health.py` and
  `test_workspace_marketing_bridge.py`. Shell syntax and `git diff --check`
  passed. Tests include successful evidence containing auth-related words,
  expired auth, timeouts, malformed reviewer status, missing binaries, no
  provider-output logging, and the loaded/unloaded launchd installer boundary.
- The candidate's real auth probe on Pro returned `notebooklm_auth=auth_required`,
  `reviewer_identity=configured`, `authentication_ready=false`, `verdict=not_run`.
  This proves detection on the isolated candidate, not deployment.

## Exact remaining actions

1. Operator on Pro: run `nlm login` with the existing profile and complete any
   browser authentication; then `nlm login --check` must succeed. Do not delete
   the profile, export cookies, or substitute a different provider.
2. Invoke the canonical bridge `newsroom_fact_gate` with
   `item_id=news_20260909_173558_cb32eac2`. Record its real PASS or BLOCK verdict
   and checked claims. A provider outage is not an acceptable verdict.
3. An authorized independent Claude release session reviews this candidate,
   runs the tests, and applies the repository's BLUE merge/deployment gates.
   This external builder must not merge, arm or deploy its code.
4. After the approved code is on Pro's runtime checkout, restart the existing
   service with
   `launchctl kickstart -k gui/$(id -u)/com.nuzantara.chatgpt-marketing-tunnel`.
   Preserve the profile and authorized write mode. Do not rerun the installer
   or `runtimes connect` alongside launchd.
5. Prove the live `workspace_health` includes the new authentication fields,
   verify one tunnel process and healthy endpoints, and repeat the real article
   gate. No article publication is part of this mandate.

Acceptance A remains open until step 2 produces a real editorial verdict.
The runtime recovery is live; the code repair is prepared and tested only.

# NotebookLM runtime maintenance

The validated package target is `notebooklm-mcp-cli==0.15.5`.
The package supplies both `nlm` and `notebooklm-mcp`.

## Execution environments

- CLI on M5, Pro and Mini: `~/.local/bin/nlm`, managed as a uv tool.
- Pro bridge: `~/venvs/nlm-bridge/bin/uvicorn`, as configured by
  `~/Library/LaunchAgents/com.balizero.nlm-bridge.plist`.
- Corpus exports on Pro should use the bridge environment, rather than the
  separate historical `apps/nlm-bridge/.venv`.
- The bridge dependency is pinned in `apps/nlm-bridge/requirements.txt`.

Updating a uv tool does not update a separate virtual environment or an
already running MCP process. Check all execution environments independently.
After an MCP package update, reconnect its owning app when convenient; do not
terminate unrelated running agent sessions.

## Accounts and recovery

`NLM_PROFILE` selects the account for the bridge, corpus exporter and auth
sentinel; its default is `default`. Direct-library clients preserve the
credential host and revision, so recovery and token rotation stay associated
with the account that supplied the credentials.

For a confirmed authentication failure:

1. Try `nlm auth refresh --http-only --profile <profile>` once and revalidate.
2. If browser-dependent cookies need renewal, try
   `nlm auth refresh --profile <profile>`.
3. If Google sign-in is fully expired, use `nlm login --profile <profile>`.

Do not use `login --clear` as routine recovery. Explicit refresh bypasses the
library's automatic recovery limits: never place it in an unbounded retry loop.
Network errors and timeouts are inconclusive, not proof of expired credentials.
Never copy raw login output, notebook titles, account identities or credentials
into reports or alerts. The sentinel performs only one HTTP-only refresh per
probe; it does not launch an interactive sign-in.

Keep unattended server storage in its validated mode. Protected storage requires
keystore access in the actual daemon or SSH context; do not enable it as an
incidental part of an upgrade.

## Skills and MCP registration

Install the current bundled skill for actual consumers:

```sh
nlm skill install codex --level user
nlm skill install claude-code --level user
nlm skill install antigravity --level user
```

Codex and generic agents share `~/.agents/skills/nlm-skill`.
Verify the installed `SKILL.md` version; updating the executable alone does not
update an installed skill. Uploaded cloud skills require their own upload.

The existing Codex server name `notebooklm-mcp` is intentional:
`infra/codex-hooks/install_seat_profile.py` depends on it. Do not accept a wizard
rename to `gemini-notebook-mcp` without updating and verifying every exact-name
consumer. MCP profile switching affects subsequent calls across chats sharing
the same server; prefer a profile-specific refresh instead of switching to
repair another account.

The default eight-inflight limit is for MCP `notebook_query_start`, not all CLI
subprocesses or direct Python queries. Do not raise it without measured demand.

## Verification

Run the bridge, auth sentinel and watchdog tests against the target dependency.
Validate the real library signatures in addition to mocked tests. Check login
validity and the notebook-list API without displaying account or notebook data.
Probe `http://127.0.0.1:18790/nlm/health` for the Pro bridge; `/health` is not its
route. Keep the previous environment available until post-restart checks pass.

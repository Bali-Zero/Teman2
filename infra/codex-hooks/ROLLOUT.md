# Codex workflow rollout — 9 September 2026

Historical v1.0 evidence below. Child-adapter v1.1 installation and coverage are recorded separately in CHILD-ROLLOUT-2026-09-09.md.

The context and verification adapter is installed on all three hosts and seven
Codex profiles. The final source hash, six trusted event definitions, and
preservation of previous hooks were independently checked on every profile.

| Host   | Profiles configured                   | Actual model probe     | Actual handoff probe                          |
| ------ | ------------------------------------- | ---------------------- | --------------------------------------------- |
| Air-M5 | `.codex`, `.codex-o2`, `.codex-acct2` | Astra, primary profile | Two continuations and failed-launch retention |
| Pro    | `.codex`, `.codex-acct2`              | Astra, primary profile | Two continuations and failed-launch retention |
| Mini   | `.codex`, `.codex-acct2`              | Astra, primary profile | Two continuations and failed-launch retention |

The adapter measures Codex's current reported context window, with a 20% limit
for the imperator role and 40% for other roles. Fresh continuations carry the
original text mandate, intervening instructions and checkpoint; the destination
must acknowledge the exact source and start actual model work before the source
turn stops. Failed launches retain the source. Verification receipts bind real
command exit codes to the file state and become invalid after further edits.

Validation: 18 regression tests and Ruff passed. Real sessions exercised
SessionStart, PreToolUse, PostToolUse and Stop on all three hosts. A separate
Air-M5 probe exercised checkpoint and verification helpers in a read-only
sandbox. PreCompact and PostCompact have regression coverage, without forcing
compaction in an operator session.

The final revision adds rejection of tool calls from an unacknowledged child.
Its regression passed and its installed hash was rechecked on all seven profiles.
The live positive probes preceded that final guard; the exact tested revision
and session identifiers are recorded in the evidence file. Secondary profiles
have configuration and trust verification, not separate live model probes.

New sessions consume these hooks. Existing operator sessions were not restarted.
The existing isolated nightly autofix runner uses `--ignore-user-config` and
`--ephemeral`, so it remains outside this installation. Verification receipts
also do not serialize other hooks or control their memory writes. This rollout
therefore does not establish universal automatic repair or proof-before-memory.

The selected bundled Codex runtime is 0.153.4 on all three hosts. Global terminal
CLI installations, credentials and Claude/Fable hook files were left unchanged.
Each profile retains local pre-install and update backups. The source is prepared
on `agent/air-m5/infra/codex-context-bridge` for independent review; no repository
merge or application deployment was performed.

- [Machine-readable evidence](FLEET-VERIFICATION-2026-09-09.json)
- [Adapter behavior, installation and rollback](README.md)

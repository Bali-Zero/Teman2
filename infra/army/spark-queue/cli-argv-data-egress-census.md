# CLI argv data-egress census: call-sites passing free text as command-line arguments to LLM CLIs

Read-only analysis — no plan to edit/commit/push anything.

W115 GOTCHA-3 (cicatrix-superscar.md family #3): `draft.py` passed a client's
ENTIRE message as `claude -p <prompt>` — on the command line, readable by
`ps` for every process on the machine. That one call-site was cured; this
census hunts the class.

Sweep `scripts/`, `infra/`, and `apps/` for invocations of LLM CLIs
(`claude`, `codex`, `agy`, `kimi`, `qwen`, `ollama run`) where
the prompt argument is built from VARIABLE free text (an email body, a chat
message, file contents, DB rows) rather than a fixed literal string.

For each hit answer:

- file:line and which CLI
- where the variable text originates (user/client content? repo file? log?)
- whether it could contain client PII (Law 2 boundary) — judged from the
  originating surface, not from variable names alone
- whether a file-based alternative exists in that code path (prompt file,
  stdin where the CLI supports it)

Output a markdown table sorted: potential-PII argv first, then large-content
argv (>1KB plausible), then fixed-literal (safe, list only the count). N of
M, never a silent cap. This is a census for a later cure PR — do not propose
diffs, just anchor the sites.

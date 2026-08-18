# exit-code-vs-output judgment census: shell call-sites that trust rc where the tool reports errors on stdout

Read-only analysis — no plan to edit/commit/push anything.

W104 (cicatrix-superscar.md family #2): `redis-cli` exits 0 and puts `NOAUTH`
on STDOUT — every call-site judging the exit code (or comparing stdout to a
happy value) mistook a refusal for success; two organs were dead for weeks.
The cure covered the redis-cli class. This census hunts the SIBLINGS.

Sweep `scripts/` and `infra/` shell + Python subprocess call-sites for tools
known to (or plausibly able to) report failure in their OUTPUT while exiting
0, or to exit non-zero for reasons the caller misreads: `redis-cli`, `psql`,
`curl` (HTTP errors exit 0 without `-f`), `gh` (some subcommands), `fly`,
`osascript`, `security`, `launchctl`, `mail`/`sendmail`, `az`/`aws`-style
CLIs if present.

For each call-site answer: does the surrounding code judge (a) rc only,
(b) output only, (c) both? If (a), can the tool put an error on
stdout/stderr and still exit 0 — name the concrete failure string it would
miss (e.g. `NOAUTH`, an HTTP 500 body under curl-without--f).

Output a markdown table: file:line | tool | judgment form (a/b/c) | concrete
missable failure | risk (HIGH if the call gates an alert, a backup, or a
state-file write; MEDIUM cron-only; LOW cosmetic). Sort HIGH first. N of M,
never a silent cap.

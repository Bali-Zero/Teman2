# dead-flags: env vars read but never set

Read-only analysis. Census every environment variable that `scripts/*.py`
reads (via `os environ.get(...)` / `os.getenv(...)` / `os.environ[...]`,
whatever pattern you find) and cross-check it against every `.plist` in
`infra/launchagents/*.plist` and every crontab-style wrapper in
`infra/launchagents/wrappers/*.sh` and `scripts/*.sh` to find variables that
are READ by a Python script but never SET by any live plist
`EnvironmentVariables` block or any wrapper `export`/inline assignment
found in this repo.

A variable counting as "dead" means: no plist, no wrapper, and no obvious
caller in this repo ever sets it — so the script always falls back to
whatever default (or `None`) the `.get()` call supplies. That is not
automatically a bug (some are legitimate test-only overrides), so for each
finding say which category it looks like: (a) genuinely dead — the feature
gate it guards can never be flipped in production, (b) test/dev-only
override (name suggests `..._TEST`, appears near a `monkeypatch`/pytest
fixture), (c) unclear — flag it for a human to check.

Output as a markdown table: env var | reading script:line | category |
one-line evidence for the category call. Cap the list at the 25 most
interesting findings if there are more; say how many you found in total.

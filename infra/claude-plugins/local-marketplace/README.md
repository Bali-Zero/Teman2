# nuzantara-local marketplace

Repo declaration for the Claude Code plugin directory marketplace installed at
`~/.claude/local-marketplace` on every machine. Install/verify with
`infra/claude-plugins/install_local_marketplace.py`; drift from this repo is
declared to `infra/home-fork/declared-pairs.json` (authored files) and
`vendor.lock.json` (vendored files, checked by `--check`, not by pairs).

## Why each fork exists

**superpowers** (obra/superpowers 6.3.0, 5 skills kept: receiving/requesting
code review, systematic debugging, TDD, verification-before-completion).
Upstream's `SessionStart` hook injects ~7KB — an "invoke a skill before ANY
response" block — into every session, including headless dashboard crons, and
competes with the `modus` skill for the first turn. Claude Code has no
per-plugin-hook toggle, so `hooks/` is dropped entirely rather than fought.
`skillOverrides` (off/name-only/none) does NOT cut real prompt tokens for
PLUGIN skills — measured identical across all three settings — only pruning
the skill directory does, which is why this fork keeps 5 of the upstream set
instead of toggling the rest off.

**caveman** (JuliusBrussee/caveman, only `skills/caveman/` + `src/hooks/`).
Upstream defaults to always-on `full` mode and ships 3 `cavecrew` agents plus
19 side skills that are never invoked here. This fork keeps just the
`/caveman` skill and its mode hooks (default off), with the plugin version
suffixed `-nzlean` to mark the trim.

**typescript-lsp** (`.claude-plugin/plugin.json` only, per machine under
`machines/`). `typescript-language-server` needs a `tsserver.js` to fall back
to in any root without its own `node_modules` (scratch dirs, every
`.worktrees/` dir). TS 7.x is a native rewrite that ships no `tsserver.js` at
all, so the fallback must point at a classic TypeScript 5.x install — here,
each host's own repo checkout of TypeScript 5.9.3. `lspServers` must live in
the plugin's OWN `plugin.json` to reach the LSP registry; a copy in
`marketplace.json` is silently inert, so that block is dropped from
`marketplace.json` here (identical on every host) and only `fallbackPath`
differs across the three `machines/*/typescript-lsp.plugin.json` files.

## Install / verify

```
python3 infra/claude-plugins/install_local_marketplace.py --machine auto
python3 infra/claude-plugins/install_local_marketplace.py --check
```

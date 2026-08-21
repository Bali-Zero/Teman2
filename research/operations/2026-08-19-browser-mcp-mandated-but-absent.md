---
date: 2026-08-19
domain: compliance
client_case: none
sources:
  - CLAUDE.md (lines 155 and 243 — the default-browser-MCP declaration and the mandatory post-deploy QA step)
  - .mcp.json (repo MCP inventory)
  - .claude/agents/frontend-browser.md (the agent whose tools list names the server)
  - ~/.claude/settings.json (two hook matchers referencing the tool)
  - claude mcp list (23 servers, measured this session)
adversarial_review: exempt-measurement-note
---

# A mandatory QA step runs through a tool that is not configured

Found while trying to close the one open claim in the CRM/portal handoff simulation. That report
asserts the shared-cookie handover produces "no loop and no broken render"; a cross-family reviewer
objected, correctly, that this is a statement about browser behaviour and had only ever been read
out of the source. So the obvious next move was to drive a real browser. It could not be done, and
the reason is worth more than the test would have been.

## Measured

| Where | What it says |
|---|---|
| `CLAUDE.md:155` | "Default browser MCP: `mcp__claude-in-chrome__*` (NEVER `mcp__playwright__*` unless ordered)" — and points to `.mcp.json` as the inventory |
| `CLAUDE.md:243` | "**Post-deploy QA OBBLIGATORIO**: … screenshot via `mcp__claude-in-chrome__*`" |
| `.claude/agents/frontend-browser.md:4` | `tools: Bash, Read, Grep, Glob, WebFetch, mcp__claude-in-chrome` |
| `~/.claude/settings.json:195,300` | two hook matchers naming the tool |
| `.mcp.json` | declares exactly one server: `nuzantara-knowledge` |
| `git log -S"claude-in-chrome" -- .mcp.json` | empty — the server has **never** been in that file |
| `claude mcp list` | 23 servers, **none** of them `claude-in-chrome` |
| `ToolSearch select:mcp__claude-in-chrome__*` | "No matching deferred tools found" |

The doctrine cites `.mcp.json` as its inventory, and that inventory contradicts it. The only
configuration that mentions the tool at all is a pair of hook matchers — rules that would fire if
the tool existed, waiting on something that never arrives.

## Scope, stated rather than implied

This is measured on **this machine, in this session**. `claude-in-chrome` is extension-backed, so it
is possible it materialises only when Chrome is running with the extension connected and paired —
which would make this a "not connected right now" rather than "never worked". What is *not*
session-dependent, and is established: the repo's own MCP inventory has never listed it, on any
commit, while three separate places in the doctrine treat it as present — one of them marked
OBBLIGATORIO.

## Why it matters more than the missing test

A `frontend-browser` agent was dispatched for exactly its declared purpose. It went idle twice
without delivering anything, and asked directly, it stayed silent. From the orchestrator's side that
is indistinguishable from a lane still working — which is how a QA step that cannot run gets read as
a QA step in progress, and then as one that passed.

So the mandatory post-deploy QA in `CLAUDE.md:243` is, on this machine, unperformable as written.
Nothing reports that. The step exists, the agent exists, the hook matchers exist, and the thing they
all depend on does not — which is the same disease the simulation this came from is named after:
**existence mistaken for participation**, one layer beneath the report that describes it.

## What this does not claim

- Not that the browser MCP is broken or should be removed — only that it is absent where the
  doctrine says it is present.
- Not that past post-deploy QA never happened. Screenshots may have been taken in sessions where the
  extension was connected. Untested either way.
- The handover claim in `03-existence-mistaken-for-participation.md` remains **unproven**, and is
  already recorded there as standing against it. This note does not resolve it; it explains why the
  attempt failed.

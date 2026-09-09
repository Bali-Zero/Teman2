# Website corner: shared agent entry point

Created 2026-09-07. Canonical instructions:
[`../../../.agents/skills/website/SKILL.md`](../../../.agents/skills/website/SKILL.md).

The corner contains the mandate, approved design decisions, active worktree,
product boundaries, acceptance loop, production comparison and review protocol.
Edit the canonical source, never a vendor-specific copy.

## Entry points

| Agent | Discovery / explicit entry |
| --- | --- |
| Codex | `.agents/skills/website`, plus the installed user alias; select `website` in the skill picker or use `$website` |
| Claude Code | `.claude/skills/website`; invoke `/website` |
| Gemini through Antigravity | `.agents/skills/website`; global alias in `~/.gemini/config/skills/website`; ask to use the website skill or select it in slash completion |
| Kimi Code | `.agents/skills/website`; user alias in `~/.kimi-code/skills/website`; invoke `/skill:website` |
| Qwen Code | `.qwen/skills/website`; user alias in `~/.qwen/skills/website`; ask to use the website skill |

The name is shared; literal slash syntax differs between clients. A universal
fallback is: "Read the website SKILL.md, verify its current state, and resume
the next bounded website task." Existing sessions may need a skill refresh or a
new session before their discovery inventory includes this newly installed skill.
No claim is made that five independent inference sessions have loaded it: the
installation check validates paths, shared identity and frontmatter.

## Installation on this machine

The project aliases for Claude, Codex and Qwen are relative symlinks to the
canonical folder. Kimi and Antigravity discover `.agents` directly.

User aliases in `~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`,
`~/.qwen/skills`, `~/.kimi-code/skills` and `~/.gemini/config/skills` all resolve
to the active website worktree. They contain no duplicate instruction content.
If this worktree is relocated or retired, repoint those aliases together. No
files in the main checkout were changed to install this corner.

For another machine, use project discovery or recreate user aliases pointing at
that machine's checked-out canonical folder. Do not copy Air-M5 absolute paths
and assume they exist elsewhere.

## Sources used to choose discovery locations

- Installed Antigravity documentation:
  `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/SKILL.md` and
  `docs/skills.md`: workspace `.agents` roots and global `~/.gemini/config`.
- [Kimi Code skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html):
  shared `.agents` discovery and explicit `/skill:website` convention.
- [Qwen Code skills](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/skills.md):
  project and user `.qwen/skills` directories.
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/): `.agents` aliases
  also support the separate Gemini CLI. The operational Gemini client in this
  workspace remains Antigravity; no legacy inference client was installed.

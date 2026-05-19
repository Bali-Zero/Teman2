# AI Developer Discipline Contract

This contract applies to every AI developer that touches this repository:
Claude Code, Codex, Gemini CLI, DeepSeek, Aider, overnight runners, local
LaunchAgents, and any wrapper that dispatches them.

The goal is simple: useful work should become a reviewed branch or PR; local
noise should not survive in `main`; user work must never be deleted by cleanup.

## Required Close-Out

Before any AI developer says work is finished, it must run:

```bash
./scripts/ai_dev_closeout.sh --strict
```

The command is intentionally read-only. It reports branch state, dirty files,
known artifact classes, and common integrity checks. In strict mode the working
tree must be clean, so run it after the final commit and before handoff. A
strict failure means the AI developer must either:

- commit the valid work on a branch and open a PR;
- move clearly local-only artifacts to an ignored local location;
- write a status explaining why the dirty state remains; or
- ask the user only if deletion or destructive cleanup would be required.

## Main Checkout Rule

`main` is an integration target, not an AI scratchpad.

- Non-trivial AI work must happen on a branch or isolated worktree.
- Dirty `main` at close-out is a blocker.
- If dirty files are found on `main`, classify them first. Do not run `git reset`,
  `git checkout --`, `git clean`, or `rm` as a cleanup reflex.
- Preserve user and automation output by moving it to a branch or PR when it is
  valid, as with generated content, research notes, or operational scripts.

## Dirty File Triage

Every dirty file must be put in one of these buckets:

| Bucket               | Examples                                              | Correct action                                 |
| -------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| Product content      | MDX articles, scraper registries, public data indexes | Validate, commit on branch, PR                 |
| Operational research | `research/operations/*.md`, audit notes, runbooks     | Format, commit on branch, PR                   |
| Tooling              | `scripts/*.sh`, local checkers, LaunchAgent helpers   | `bash -n`, run safely, commit on branch        |
| Local-only artifact  | logs, temp reports, downloaded outputs                | Move to ignored local path or leave ignored    |
| Sensitive or secret  | env files, credentials, private exports               | Do not commit; move to `.secrets/` or keychain |
| Unknown              | Anything else                                         | Stop and write a status before cleanup         |

## Localized MDX Rule

Locale article files such as `slug.it.mdx` and `slug.id.mdx` are valid only when:

- the base `slug.mdx` exists;
- frontmatter `locale` matches the file suffix;
- the file can be serialized by the app MDX pipeline;
- obvious generated UI residue is cleaned before PR.

## Registry Rule

Generated registry files, especially
`apps/bali-intel-scraper/data/published_articles.json`, are not disposable
noise by default. They are dedup state. Validate JSON shape and duplicate URLs
before deciding whether to keep them.

## PR Rule

Every AI-authored PR must state:

- which agent or automation produced it;
- whether the main checkout was dirty and how it was resolved;
- verification commands and exact blockers;
- whether failures are related to the diff or pre-existing suite state.

## Forbidden Cleanup

These commands are forbidden unless the user explicitly asks for them and the
target paths are named:

```bash
git reset --hard
git checkout -- .
git clean -fd
rm -rf <repo-path>
```

If cleanup requires one of those commands, stop and ask.

---
name: subhi
description: Subhi corner for the Subhi and Zero collaboration on Indonesian article translation and polish batches for balizero.com. Use when Zero pastes a /subhi update, asks for a reply to Subhi, or works on the Indonesian .id.mdx article pipeline.
---

# Subhi Corner

## Participants and language

- Subhi is the external Indonesian-language collaborator for `.id.mdx` articles,
  including `seoTitle`, `seoDescription`, and native-language polish.
- Zero is the owner and relays operational updates.
- Angel is the content approver.
- Write replies to Subhi in Indonesian, with a warm but technical tone.
- Keep code, commits, PR bodies, and repository documentation in English.

## Non-negotiable workflow

1. Work in an isolated worktree and keep one coherent content batch per PR.
2. Use PR #2957 as the reference for Indonesian polish quality.
3. Require a complete Indonesian `seoTitle`, a clean `seoDescription` without
   Markdown residue, and valid `relatedArticles`.
4. Run the reasoning-leak lint and all path-aware repository hooks.
5. Never bypass hooks with `--no-verify`. Route heavy verification from Air-M5
   to Pro when necessary.
6. Subhi prepares content; Angel reviews it; an independent owner-side session
   merges it.
7. Never arm auto-merge and never publish client-facing content from an agent.

## Content quality checks

- Preserve frontmatter schema and nearby canonical article conventions.
- Verify legal, tax, immigration, and numeric claims against authoritative
  sources; never translate an unsupported claim into a second language.
- Compare translated files with their source-language siblings for omissions,
  changed numbers, altered deadlines, and broken links.
- Reject reasoning traces, prompt fragments, placeholder prose, and literal
  machine-translation artifacts.
- Treat a green syntax check as necessary but insufficient; native review is
  still required.

## Live state verified on 2026-07-23

- PR #2946 merged: 20 Indonesian files retranslated after reasoning-leak
  detection.
- PR #2957 merged: tax polish batch 1 and the reference implementation.
- PR #2997 merged: Sharp/libvips security floor that removed the earlier
  dependency blocker.
- PR #2998 merged: seven-article Indonesian polish batch.
- PR #2999 merged: thirteen-article Indonesian immigration polish batch.
- PR #2991 remains an open draft for one structural-fix file. It is mergeable
  but blocked and must be refreshed and reviewed before promotion.
- PRs #2992, #2993, and #2994 are closed. Do not revive or merge them without a
  new exact-SHA audit and an explicit canonicalization decision.

## Open investigation

The Brave Shields report for `WhatsAppLeadButton` is not yet proven. The bare
WhatsApp fallback occurs when `/api/lead/capture` rejects, returns non-OK, or
cannot be parsed. Require the Brave Network or Console error from the same
browser session before changing the capture flow. Do not treat a separate curl
success as evidence that the browser request succeeded.

## Repository facts

- GitHub repository: `Balizero1987/Teman2`.
- Root npm lockfile: `package-lock.json`.
- Dependency security overrides belong in the root `package.json` under both
  `resolutions` and `overrides`, following existing conventions.

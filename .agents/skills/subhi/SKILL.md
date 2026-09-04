---
name: subhi
description: "Subhi corner for the Subhi/Zero collaboration on Indonesian article translation for balizero.com. Use when Zero pastes a /subhi update, asks for a reply, or works on the .id.mdx pipeline."
---

## Notes (moved from description 2026-09-02)

Also covers polish batches, and replies specifically to Subhi.

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

## Live handoff saved on 2026-08-12

- PR #4099 is merged but was not yet served when Subhi measured production;
  production was 12 commits behind `origin/main`, so promotion remains an
  owner-side action.
- Measurement correction for the homepage: HTML contained `D01033` twice and
  `FF2D4C` zero times; CSS bundle `5f405efd3f70e089.css` contained `FF2D4C`
  once and `D01033` zero times. `D01033` enters through an inline style from
  `rumahVars.ts`; `FF2D4C` intentionally remains the global token in
  `primitives.css:15`. Never claim that `FF2D4C` is gone site-wide.
- PR #4105 removed the dead `robots.txt` block from `proxy.ts` without touching
  the existing `X-Robots-Tag`. Auto-merge was enabled at
  `2026-08-12T02:00:44Z` and the PR merged at `2026-08-12T02:48:40Z`, before
  the instruction to disable it reached Subhi. Any revert is owner-side; do not
  describe the late instruction as a scope violation by Subhi.
- PR #4106 adds `X-Robots-Tag: noindex, nofollow` to both Zantara exits in
  `proxy.ts` and remains a two-line, single-file change. Its failing
  `guard-pins-pytest` check was traced to a main-branch Telegram-sender lint
  regression introduced through PR #4102 in `secret_log_redaction.py` and its
  test. Do not expand #4106 into backend code or touch the guard pins; repair
  the main-branch blocker separately.
- `apps/mouth/src/app/robots.ts` is the actual `robots.txt` serving layer. Any
  Zantara-specific robots change belongs in a separate PR after #4106 is live.
- Required post-live proof for #4106: verify `X-Robots-Tag` on
  `zantara.balizero.com/`, `zantara.balizero.com/login`, and the positive control
  `kita.balizero.com/login`, always naming the served commit.
- `/visas` baseline is recorded from PageSpeed Insights mobile lab at
  `2026-08-12 16:06 GMT+8`, Moto G Power with slow-4G throttling, served commit
  `9894a431c3`: LCP 8.9 s, FCP 1.7 s, TBT 420 ms, CLS 0, Speed Index 7.3 s,
  performance score 57. There is no field data for this URL.
- The LCP element was the server-rendered `Visas & Immigration` H1, with TTFB
  20 ms and element render delay 3.26 s. The trace also reported 5.1 s of main
  thread work, 8 long tasks, 1.8 s execution time, 773 links, and 1.88 MB HTML.
  Treat pagination as the scoped next experiment, not as proven causality until
  the same-tool, same-device after measurement confirms the delta.
- Crawl evidence at the same served commit remained intact: 305 article `href`
  occurrences from PR #3982. Report every before/after delta, including zero.
- An Indonesian reply draft was prepared for Zero. No email was sent by the
  agent, in accordance with Legge 5.

## Repository facts

- GitHub repository: `Balizero1987/Teman2`.
- Root npm lockfile: `package-lock.json`.
- Dependency security overrides belong in the root `package.json` under both
  `resolutions` and `overrides`, following existing conventions.

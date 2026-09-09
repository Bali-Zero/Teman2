# Resume after the local Magazine to R19 slice

Date: 2026-09-07 WITA. The bounded local integration is complete. Production is
unarmed. This file supersedes the execution instructions in the earlier Pro
loop prompt; do not restart that entire loop.

## Workspace and evidence

Use only /Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro, branch
codex/website-pro-continuation. Base HEAD is
b740b2cc3e94b1a46c9e9811bb369289fc21ea3d. The working tree includes essential
inherited changes and this slice; do not reset, clean, mutate main or create a
replacement worktree. The M5 checkpoint is historical and inactive.

Read .agents/skills/website/SKILL.md, references/state.md and
apps/website/docs/reviews/2026-09-07-pro-slice/REPORT.md plus DECISION.md.
Independent review receipts, test logs, HTTP evidence and browser metrics are
in the report folder. Screenshots: output/playwright/website-r19-pro/.
Exact checkpoint bundle:
/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro/output/checkpoints/2026-09-07-pro-slice/.
Read CHECKPOINT.json and VERIFIED.json and verify hashes before restoration.
The directory is covered by the existing /output/ ignore rule. RELOCATION.json
records the eight-artifact move and removal of the former external finished-slice
copy. The original /Users/nuzantara/website-handoffs/2026-09-07-r19 transfer package
was left untouched. The final overlay includes all original 152 paths, scoped
current changes, the full review directory including ignored logs, and the
screenshots. It excludes checkpoints recursively and runtime caches; the
immutable fixture-preview-startup.log is retained, not the active preview log.
No commit was made. The base commit by itself omits the required overlay.

The Gemini stage is complete. Read gemini-research.md and its receipt in the
final review directory; gemini-primary-sources.json separates actual Gemini
browse calls from coordinator/audit source validation. The requested/runtime
model was gemini-3.1-pro-high, with no independent backend-model attestation.
Only web reads were observed; enforced read-only sandboxing was not established.

## Current behavior

/ and /journal call src/lib/server/journal-feed.ts per request. Without
WEBSITE_EDITORIAL_FIXTURE=1 the feed is unavailable. With explicit value 1,
fresh local SQLite applies the real Magazine migrations and repository methods
to three synthetic records, demonstrating publication, quarantine, amendment,
source disclosure and eligible/missing images. The fixture does not test machine
ingress auth, audit/promotion or canonical asset bytes. Fixture destinations are
inert and the preview labels them as sample content.

One built fixture preview was retained on 127.0.0.1:3100. Check lsof and process
ownership before replacing it. The final closeout observed one owned listener,
HTTP 200 for / and /journal, preview noindex and private/no-store; PREVIEW.json
in the checkpoint records the timestamp and transient PID. Starting command,
from the worktree:

```sh
WEBSITE_EDITORIAL_FIXTURE=1 npm --prefix apps/website start
```

Verified on Node 26.5.0 and the inherited npm 11.19.0 lockfile. Final results:
55 website tests, 47 architecture tests, typecheck and build passed. Run build
and typecheck sequentially because Next recreates generated type files.
These are the last product checks; documentation/research closeout did not
change product files and did not rerun the full suites.

```sh
npm --prefix apps/website test
npm --prefix apps/website run test:architecture
npm --prefix apps/website run build
npm --prefix apps/website run typecheck
```

## Next bounded task

Design and verify a read contract from the existing Magazine authority to the
website, with authenticated transport, a stable publication version/snapshot,
withdrawal consistency, approved public evidence, canonical access and media
delivery/cache policy. Define current-edition versus breaking-news coverage.
Begin with source and contract tests; production transport is not authorized by
this handoff. The final adapter recheck mitigates observed concurrent changes
but is not an atomic D1 snapshot.

The qualified research adds no local-fixture blocker. CORP same-origin restricts
ordinary cross-origin no-cors image use; a new media path must be explicitly
proven. Request-time rendering, no-store and D1 sessions do not by themselves
prove a frozen multi-read snapshot or recall content already delivered. Define
the freshness requirement before choosing cache invalidation or open-screen
refresh mechanisms. Do not treat a single SQL query or SSE/WebSockets as a
mandatory architecture decision already approved by this handoff.

Preserve the R19 palette, logo and ocean book, founder-only homepage band,
complete 16-person /team roster and owner-approved project responsibilities.
No new biographies, prices, unverified regulatory content or substitute photos.
The historical MDX proof remains isolated.

Stop after the next explicitly authorized bounded mandate. No main mutation,
merge, auto-merge, deployment, publication or access changes follow from this
handoff. Send a terminal-only completion/block/decision callback to coordinator
task 01a077dd-523c-74e1-9cd8-8855fe4178d2 if that coordination is still active.

# Bounded UI batch and validation plan

Date: 2026-09-07 WITA. Requested and accepted for integration by `/root`.
No release action is authorized. The existing dirty overlay is inherited;
repository-wide changes cannot be attributed to this small batch.

## Changes executed by the source/coverage worker

- `src/app/page.tsx`, `src/app/team/page.tsx` and
  `src/components/services/ServiceJourneys.tsx`: make the existing main skip
  targets programmatically focusable with `tabIndex={-1}`. They do not become
  extra stops in ordinary Tab navigation.
- `src/components/services/service-journeys.module.css`: 44px minimum height
  for isolated header, footer, card, tool and action links; 32px for breadcrumb
  links. Existing primary actions retain their larger minimum. This is touch
  target comfort, not a source-only WCAG failure claim.
- New `src/app/not-found.tsx` and `src/app/not-found.module.css`: a clear 404,
  meaningful H1/main and Home/Services recovery actions using the existing
  logo, typography, paper/forest/copper tokens, Container and ButtonLink.
- The four Services overview card links retain visible “Explore this service”
  text and add that text plus the service title as their accessible name. The
  independent capture worker noted that isolated link lists otherwise repeat
  the same name. This is a small usability improvement, not a WCAG failure claim.
- Extended existing `src/app/page.test.tsx`,
  `src/components/Team.test.tsx` and `src/app/services/services.test.tsx` with
  main focusability and 404 recovery checks. No CSS snapshot tests added.

No Journal/server/global-style/roster/image file was edited by this worker.
Installed Next 16.3.1 not-found and accessibility documentation were read
before the framework file was added. The default 404 adapts to OS color
scheme; custom `app/not-found.tsx` is the documented route-level replacement
and also handles unmatched URLs. No experimental global-not-found flag needed.

## Checks completed

`npm test -- src/app/page.test.tsx src/components/Team.test.tsx src/app/services/services.test.tsx`
passed **13 tests in 3 files**, 2.12s, at 02:53:57 WITA. The existing Vite native
config-loader compatibility notice was emitted; it did not fail the tests.
These focused DOM tests prove that main accepts focus, not that a real browser
has completed the skip-link navigation. The integrator will test that after
the shared build.

After the parent authorized the final unique service-link names, the focused
`npm test -- src/app/services/services.test.tsx` passed **9 tests in 1 file**,
1.77s, at 03:00:57 WITA. The overview test verifies the four unique accessible
names against their respective routes. The scoped tracked diff check passed.

The scoped tracked `git diff --check` passed. The whole-worktree tracked
`git diff --check` also returned zero, including inherited and sibling changes;
that command alone does not inspect untracked files. New files were checked
separately. Build and typecheck were deliberately not run during parallel work.

`source-http.json` is explicitly a **pre-rebuild inherited preview** receipt.
The running process serves the earlier build, so it cannot prove the newly
written UI. At this snapshot all eight implemented routes returned 200 and
the four unknown paths returned 404.

## Integrated command plan — pending Track A readiness

From `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`, execute each
command separately and continue only after its result is understood:

```sh
npm --prefix apps/website test
npm --prefix apps/website run test:architecture
npm --prefix apps/website run build
npm --prefix apps/website run typecheck
```

The website suite includes `src/**/*.test.{ts,tsx}`. Architecture configuration
includes `proofs/architecture/*.test.tsx`, uses one worker and disables file
parallelism; it discovers the three existing proof files and any correctly
named Track A proof added before integration. Confirm the actual new proof is
collected, not merely present on disk. Build and typecheck must be sequential
because Next regenerates type files. Record fresh totals; do not inherit the
previous slice's totals.

## Single-preview ownership and refresh

The last read-only check found PID 12876 (next-server 16.3.1), parent PID 12825
(`npm start`), cwd exactly this worktree's `apps/website`, and one listener on
127.0.0.1:3100. These are transient observations, not permission to signal a
future process with the same ID.

Before the shared build, rediscover the listener with `lsof -nP -iTCP:3100
-sTCP:LISTEN`, verify that PID's cwd and launcher, stop only that owned preview,
and confirm the port is clear. Avoid rebuilding `.next` under a serving process.
After successful validation, launch exactly one preview. The previous slice's
explicit UI fixture command was:

```sh
WEBSITE_EDITORIAL_FIXTURE=1 npm --prefix apps/website start
```

Track A's new transport proof may require a different explicit local test
arrangement; use the agreed interface, never production credentials or an
implicit fallback. Keep new startup logs inside this review's directory and
do not overwrite the completed slice's evidence. Check the new PID/cwd,
loopback binding, route headers and expected fixture provenance. Then repeat
changed-route keyboard/404/mobile checks and final image-decoding screenshots.

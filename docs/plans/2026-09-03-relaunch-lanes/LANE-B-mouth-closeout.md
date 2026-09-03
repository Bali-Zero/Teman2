# LANE B — `apps/mouth` close-out: E33 Second Home, KBLI pages, brand PRs, WR3 landing

**Machine:** M5 (only machine that typechecks TypeScript reliably; Mini cannot). **Corners:**
`.agents/skills/secondhome/SKILL.md` §4bis LIVE STATE, `.agents/skills/kbli-navigator/SKILL.md`
for the page work, `.claude/skills/bali-zero-brand/` for anything brand-shaped.
**Contract:** `README.md` in this directory.

You are the mouth close-out session on M5. Four independent sub-lanes; each PR ≤ 400 lines, one
concern. Run vitest with cwd = `apps/mouth` (`npm --prefix` does NOT move vitest's cwd — it silently
tests the main checkout). Prove every UI change on `balizero.com`, not in a test.

## B1 — E33 Second Home (corner §4bis rows still ⚠️)

- `fr.json` / `ru.json` miss the entire `portal` section (12 leaf keys) while `types.ts` comments
  call those locales complete — add the keys, add the test that fails on a missing section.
- E33 forbidden-claim guard (#5360/#5370/#5384/#5388): sounder, **not armed**; and in FR/RU all 7
  claims are evadable by synonym or negation. Build the FR/RU guilt corpus first, then the guard.
  The ENFORCE flip in Fly secrets is Zero's (`ZERO-DECISIONS.md` item 5) — do not flip it.
- IBM Plex Mono is named by the identity law but not loaded — load it for the surfaces the law
  names; **IDR amounts stay Cormorant + `tabular-nums`** (Zero ruling 2026-09-01) — do not touch them.
- Radius-12 law applied but not armed — one test.
- Merah Putih DAY contrast guard runs and goes red but does not block (`merah-putih-day-contrast.yml`
  has no entry in `infra/required.d/contexts.json`) — make it green, then required, in that order.
- Studio commercial-honesty row (2026-08-24): the public Studio can hand a hard "not eligible" while a
  priced Bali Zero product fits — route those verdicts to a "talk to us" exit, never a dead end.
- "E33E client-facing price" ledger row (2026-08-31): read the row on `origin/main`, then act.

## B2 — Open PRs that are CLEAN and simply not armed

- #5589 `fix(kbli): derive the visible KBLI code count from the dataset` — review, arm.
- #5579 `fix(brand): lock official anthracite to #363A3E` — review, arm (worktree
  `.worktrees/wr2-brand-antracite-363a3e` on this machine).
- #5591 DRAFT `CTAHandoff stacking context + 44px tap target` — finish or close with a reason.
- #5572 docs (queue_unstick sender host) — arm.
- After each merge: prove on production (Vercel auto-deploys on push to main; wait for the served
  commit, curl the marker), then `bash scripts/mq.sh handoff`.

## B3 — KBLI pages (`apps/mouth` KBLI route tree)

- Three fixes landed 2026-09-02 (#5583 JTBD anchors, #5586 autofocus scroll, #5588 shared footer):
  prove all three on `balizero.com` — the ledger has no PROVE-LIVE row for them yet.
- Client-facing licensing text for the 17 placeholder codes (`PENDING_REGULATION` rendered as a
  licence) is a DATA defect owned by Lane D — do not patch it in the page.

## B4 — WR3 Zantara Video Factory: land the branch, spend nothing

- Branch `agent/air-m5/wr3/zantara-video-factory-v3` (worktree
  `.worktrees/wr3-zantara-video-factory-v3`): 16 commits ahead of main, no PR, 2 dirty files.
  Phase `OWNER_VISUAL_REVIEW_REQUIRED` — Zero must accept or reject clip M05-v11
  (`ZERO-DECISIONS.md` item 4). Independently of that verdict, the factory state, control plane
  (`scripts/cli/factory`) and probe ledger belong on main: split into ≤ 3 PRs (docs / control plane /
  tests), no Flow credit spend, `publication_allowed: false` stays.
- WR2 runs only on command (Zero 2026-09-01) — never re-arm a WR2 plist from this lane.

## LIVE STATE (update before ending the session)

- 2026-09-03: nothing proved yet. Suggested order: B2 (cheap, unblocks the board) → B3 prove-live
  → B1 → B4.

# W3-SH-EDITORIAL — durable state (re-entry file)

Session acc186e3-89f8-4e08-86c5-b93782918d61, M5, Dux Opus 5 xhigh, BLUE.
Imperator: Fable 5.1, session 116b2671-9748-485b-ade4-db76a770af08.
Worktree `.worktrees/mouth-shweb-w3-editorial-20260911`, branch
`agent/air-m5/mouth/shweb-w3-editorial-20260911`, base `70b43c5459` (W1 `6734f95a34` IS an ancestor).

## STATE: BOZZA (updated as it advances)

## Measured at GROUND (2026-09-12 ~02:2x-02:4xZ, M5)

- origin/main `70b43c5459`; W1 present in base, so the post-W1-integration rebase is a NO-OP.
- Live `/visas/second-home-visa-indonesia`: 200, `index, follow`, canonical is the /visas/ URL,
  1 entry in sitemap.xml, 40 occurrences of the superseded threshold in the served HTML.
  `/immigration/second-home-visa-indonesia` → 308.
- Served `/llms-full.txt`: 450507 lines; **27** lines carry BOTH a Second Home marker and the
  superseded threshold, across **10** article families (not 12 lines / 1 family as FINAL §2.1 says).
- Family sources: en 14, it 14, id 14, ru 14, **fr 12** lines.
  **FINAL §2.13 is WRONG: fr is NOT already correct.** Report to the imperator.
- E33-touching corpus: 128 families / 498 files / 19 noIndex files.
- `canonicalUrl:` in MDX frontmatter has NO consumer in apps/mouth — inert. The served canonical is
  computed by `articleUrl()`; this family's frontmatter says /immigration/ and is wrong-but-inert.

## Order of work

1. BOZZA: brief.yml + contract-lock.json + probe → PRE-review cross-family (Codex refuter). [done/pending below]
2. BUILD: 5-locale family; then the 9 secondary families' co-occurrence claims; then the census.
3. Freshness tie-break in generate-llms-full.ts + test (the ONE named exception; mutant M3 must go RED).
4. VERIFY: vitest, real build, probe on the generated export, preview page.
5. Gate request to the imperator on a FROZEN head; then arm, queue, prove live.

## Checkpoints sent

- (appended as they go)

## Imperator disposition 2026-09-12T02:24Z (ACK of BOZZA)

ONE PR = ONE concern. **PR-1 = this branch = the canonical family only** (5 locales, fr included).
PR-2 (new branch from origin/main, after PR-1 is armed) = the 25 superseded-threshold claims in
the 9 other families + the inert `canonicalUrl` alignment. The 4 noIndex E33 slugs: census only,
rewrite-or-delete needs Zero's ruling.
PR-1 acceptance: 0 occurrences in the 5 sources; real build; 0 Second Home + old-threshold lines
**for this family** in the generated llms-full.txt (the other families' 23 lines stay until PR-2 —
say so in `Bites:` rather than implying a clean corpus).

## Work list for PR-1 (measured line numbers, base 70b43c5459)

Per locale, 14 lines (fr 12): 6 description · 7 excerpt · 41 seoDescription · 44/45 answerSnippet ·
55/56 FAQ Q1 · 83 "Path 1" heading (absent in fr) · 85/87 the threshold sentence · 89/91 bank
statements bullet · 114/116 property min-value bullet (absent in fr) · 137/139 document step ·
210/212 comparison table row · 263/265 renewal bullet · 302/304 "not ideal for" bullet.
Beyond the threshold: the Path 2 property block (Hak Pakai / PT PMA / province-varying value — all
outside the registry), the invented "Costs Breakdown" fee table (decomposition is forbidden by the
2026-07-23 owner ruling; PricingTool says E33 Second Home 5 Years = IDR 35,000,000 all-inclusive),
the comparison table's 5-year cost, the renewal section (Pasal 113 cumulative cap), the E33G line.

## Seats

- Codex Sol (CODEX_HOME=~/.codex-acct2, read-only sandbox, effort high): PRE-review, running.
  Already reported: the probe UNDER-matches two French spellings; the enArticles.sort tie-break
  does make mutant M3 go red.
- Gemini 3.1 Pro (High) via agy: long read of the 5 MDX vs the registry, running.

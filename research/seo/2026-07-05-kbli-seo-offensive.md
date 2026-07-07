---
date: 2026-07-05
domain: seo
client_case: none (site-wide KBLI acquisition organ)
sources:
  - research/marketing/kbli-gsc-clean-window-2026-07-03.md (GSC clean-window investigation, PR #1949)
  - agy Gemini 3.1 Pro live research 2026-07-05 ×2 (programmatic-SEO best practices; SERP/competitor landscape)
  - apps/mouth source audit this session (sitemap.ts, robots.ts, kbli/[code]/page.tsx, KBLIStructuredData.tsx, kbli-data.ts)
  - Codex GPT-5.5 red-team pass on the shipped diffs (2 confirmed findings)
status: FINAL — autonomous Fable 5 session (fable-seo, M5), mandate ~/.fable-mandates/seo.md
---

# KBLI SEO Offensive — 2026-07-05

## TL;DR

The /kbli/* impressions collapse is a **crawl-priority gap** (GSC investigation 2026-07-03),
and the codebase contained five concrete mechanisms feeding it. All five are fixed, merged
and **verified live** (4 PRs). Batch 3 (title/meta v3) is **prepared and gated** on PR #1967 —
unpause is Zero's call; recommendation below. Google now needs 2-3 weeks of recrawl before
the effect is measurable in GSC.

## Problem (grounded)

GSC clean-window (commit a9b713396d): KBLI cluster impressions collapsed (~250 active
queries → ~10; the /kbli/* deficit accounts for nearly the whole site-wide drop). Root
cause: crawl-budget/priority deprioritization of long-tail /kbli/* (recrawl gaps 40-51
days; 122 pages Crawled/Discovered-not-indexed). NOT title/meta quality.

## What was found and shipped (all verified live on balizero.com)

| # | Finding | Fix | PR | Live proof |
|---|---------|-----|----|------------|
| F1 | Specific robots UA groups (`Googlebot` etc.) declared `allow: /` with no disallow — specific groups REPLACE `*`, so Googlebot could crawl /api/, /dashboard, all workspace routes: crawl budget bled exactly where the gap is | Disallow list on every group; Googlebot group removed (falls back to `*`) | #1963 MERGED | live robots.txt: 0 `Googlebot` groups, disallows present in every group |
| F1b | (red-team on F1 fix) applying disallows everywhere newly blocked `/_next/` for renderers — Google fetches CSS/JS to evaluate pages | `Allow: /_next/static/` + `/_next/image` beat the `/_next/` disallow (longest-match) | #1974 (replaces #1968, W88 continuation-branch conflict) | robots.txt shows the Allow lines post-merge |
| F2 | Only 50/1,559 pages pre-rendered; ISR cache wiped on every deploy (several/day) → Googlebot hit cold SSR renders → TTFB spikes → crawl throttling | Full SSG: all 1,559 pages at build (+13s build cost, 1,560 HTML verified in .next) | #1965 MERGED | /kbli/85104 (51-day-gap sample) 200 static |
| F3 | `getRelatedCodes` filled from section HEAD → head codes got every inbound link, long-tail got none | Deterministic neighbor-window in both phases; regression test | #1966 MERGED | /kbli/49297 live related = exact computed window 49292-49296+49299 |
| F5/F6 | Fabricated freshness: JSON-LD `dateModified: new Date()` per render; sitemap `lastModified: new Date()` on ~50 static pages; priority/changefreq bloat (ignored by Google) | priority/changefreq dropped; fabricated lastmods removed; honest sources only | #1963 | sitemap live: 2,385 URLs, 0 priority, 0 changefreq |
| F5b | (red-team) file **mtime is clone time** on git/Vercel checkouts — the #1950 mtime "fix" never worked in prod; every deploy claimed all 1,559 pages "modified today" | Committed sidecar `data/kbli-dataset-version.json` (real last-change date 2026-07-02 + dataset sha256) + **vitest guard** that fails when the dataset changes without a sidecar bump | #1965 + #1974 | live JSON-LD `dateModified: "2026-07-02"` (was: deploy date) |
| F4 | FAQPage JSON-LD emitted on ALL pages but visible FAQ only on non-Gold layouts (436 gold pages had markup without visible content — dishonest per Google guidelines); the two texts had also drifted (JSON-LD had the Bali-block qualification, visible didn't; visible had capSpecial, JSON-LD didn't) | Single source `buildKbliFaq()` feeds BOTH the JSON-LD and a visible Common Questions section rendered on gold AND non-gold; answers are the union of the two previous texts (all facts from dataset fields already rendered on the same pages) | #1977 (faq-parity) | FAQ section visible on a gold page + JSON-LD matches |
| F7 | Invalid codes (/kbli/10314) render soft-404 | `dynamicParams=false` — **PARTIAL**: the phantom KBLI detail render is gone, but unknown /kbli/* now falls through to the blog `[category]/[slug]` catch-all: still HTTP 200, `noindex` (harmless to the index, still crawl-waste). True 404 needs a category whitelist in the blog catch-all — follow-up below | #1965 | /kbli/10314 → 200 + `<meta name="robots" content="noindex">` |

## External research (agy, 2026-07-05)

**Programmatic-SEO best practice** confirms the levers: full SSG for programmatic sets
(ISR-with-cache-wipe is the classic crawl-budget killer); Google ignores priority/changefreq
and only uses lastmod it can TRUST (bulk-identical dates destroy trust); IndexNow still not
used by Google (our /api/indexnow stays Bing/Yandex-only); Indexing API still JobPosting-only —
do not use; hub&spoke + even link distribution is the recovery lever; template sets need
30-40% unique data per page to escape "scaled content abuse" classification.

**SERP landscape**: low-competition long-tail families = `KBLI [code] foreign ownership`,
`KBLI [code] risk level`, `OSS requirements for KBLI [code]`, plus compliance troubleshooting
(`lkpm reporting deadline 2026`, `how to change KBLI 2020 to KBLI 2025 OSS`). Competitors:
Emerhub (authoritative, article-based, no searchable KBLI DB, Jakarta-centric), Lets Move
Indonesia (visa-strong, KBLI-shallow), Flado (portal-first, low organic footprint). **None
has a KBLI database** — our 1,559-page cluster is the structural advantage once indexed.
The five data points research says each page needs (code+description, ownership limit, risk,
capital, Bali specifics) are ALL already on our pages — content is not the bottleneck; crawl is.

## Impact estimate (per intervention)

1. **robots fix (F1+F1b)** — HIGH: stops crawl-budget bleed into ~30+ workspace/api paths;
   directly feeds the recrawl economy of the long-tail. Effect visible in GSC Crawl Stats in 1-2 weeks.
2. **Full SSG (F2)** — HIGH: consistent fast TTFB for every /kbli/* fetch; removes the
   deploy-frequency × cache-wipe interaction entirely. This is the mechanism most tightly
   coupled to the "40-51 day gap" symptom.
3. **lastmod honesty (F5/F5b/F6)** — MEDIUM-HIGH: restores the one sitemap signal Google
   uses; the sidecar guard prevents regression forever.
4. **Link distribution (F3)** — MEDIUM: every long-tail page now has 6+ inbound links from
   neighbors (was ~0 beyond hubs); accelerates discovery + recrawl of exactly the 122
   not-indexed pages.
5. **FAQ parity (F4)** — MEDIUM: honest markup (rich-result / AI-answer eligibility without
   penalty risk) + adds visible unique text per page (differentiation, per the 30-40% rule).
6. **Batch 3 (gated)** — CTR multiplier AFTER impressions recover; near-zero effect while
   pages aren't being recrawled.

## Batch 3 — prepared, gated (PR #1967, NO auto-merge)

Branch `agent/air-m5/mouth/seo-batch3-title-meta-v3`: data-differentiated titles per PMA
status (incl. the Bali-blocked variant for 520 codes), answer-first descriptions,
`riskLabelEn()` helper (tests 13/13), full queue doc with per-page quality checklist:
`research/seo/2026-07-05-batch3-title-meta-queue.md`.

**Recommendation to Zero**: unpause AFTER the crawl fixes have been live 2-3 weeks AND GSC
shows the gap closing (long-tail /kbli/* last-crawl <14 days, impressions recovering).
Sequencing it earlier adds title-churn during re-evaluation with no indexing benefit.
The crawl-priority gap is now closed on our side — what remains is Google's recrawl clock.

## §Meta-pattern (the disease behind the findings)

**The crawler saw a different site than the one we maintained, because every crawler-facing
signal was derived from build-time state instead of content-time state.** Three expressions
of the same defective belief:

1. *"build time ≈ content time"* — `new Date()` in sitemap, `dateModified` per render,
   mtime-as-lastmod (which is clone-time on every CI/Vercel checkout). Every deploy
   re-stamped 1,600 URLs as "changed today" → Google learned to distrust all our freshness signals.
2. *"the specific inherits from the general"* — robots UA groups (specific REPLACES `*`,
   it does not inherit) and the route fall-through (/kbli/* unknown → blog catch-all).
   Local rules silently replace global ones; nobody probed the composed result.
3. *"serving humans = serving crawlers"* — ISR-on-demand is fine for users (one slow hit),
   fatal for a crawl-budget algorithm sampling TTFB; head-concentrated related-links are
   invisible to users but starve long-tail discovery.

Antidote (now partially executable): probe the CRAWLER's view, not the code — curl the live
robots/sitemap/page artifacts after every SEO-touching deploy; the sidecar hash-guard makes
freshness-honesty a red build instead of a discipline.

## §Solo-operatore

1. **Batch 3 unpause** — merge PR #1967 when the GO criteria hold (Legge 5).
2. **GSC actions** (need Search Console UI access): after this deploy settles, re-submit the
   investigation's sample URLs (/kbli/10296, /kbli/49297, /kbli/85104) via URL Inspection;
   read Crawl Stats weekly; run the next clean-window comparison ~2026-07-26.
3. **Sister-session boundary**: INDEX.md docs-sync drift on main (proprioception P3) kept
   re-materializing in this worktree via hooks — discarded here (out of fence), still open on main.

## Next steps (in-fence, not done — deliberately)

- True 404 for unknown /kbli/* codes: category whitelist + notFound() in the blog
  `[category]/[slug]` catch-all (today: 200+noindex fall-through).
- Sitemap segmentation (kbli/blog/core) for per-cluster GSC diagnostics — needs operator
  GSC re-submission, low urgency.
- Per-code lastmod (hash per entry) if/when per-code content editing starts (gold rewrites).
- 2-digit division hub pages (adds a middle hub layer) — new routes = content gate, propose
  only after recrawl recovers.

## Session ledger

- PRs merged: #1963 (robots+sitemap), #1965 (full SSG + honest dateModified + sidecar guard),
  #1966 (neighbor-window links), #1974 (red-team follow-up). PR #1977 (FAQ parity) armed.
- PR gated: #1967 (Batch 3, operator).
- PR closed unmerged: #1968 (post-squash continuation conflict — replaced by #1974, W88).
- Red-team: Codex found 2 real issues (mtime=clone-time; /_next/ block) — both confirmed by
  direct verification and fixed before/after merge; 1 loop misfire recorded in modus
  AMENDMENTS (auto-merge armed before the red-team verdict returned → #1963 merged with a
  known-fixable regression for ~1h).
- Memory: 3 entries saved (mtime trap, robots group trap, offensive decisions).

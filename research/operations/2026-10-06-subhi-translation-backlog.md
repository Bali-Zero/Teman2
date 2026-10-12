---
adversarial_review: kimi-k3
---

# Subhi `.id.mdx` Translation Backlog — Bulk Audit (Batch B)

**Date:** 2026-10-06
**Branch:** `agent/m5/docs/subhi-backlog-1006` (base: `origin/main` @ `83237f8f93`)
**Scope:** `apps/mouth/src/content/articles/**` — Indonesian (`.id.mdx`) translation coverage of the
balizero.com English article corpus. Read-only measurement; no content was edited.

## TL;DR

| Metric | Count |
| --- | --- |
| English source articles (base `.mdx`) | **851** |
| With a `.id.mdx` sibling | **851** (100%) |
| Missing `.id.mdx` (the classic "backlog") | **0** |
| `.id.mdx` STALE (source has newer commits than the translation) | **163** (19.2%) |

The missing-translation backlog is **empty** — every source article has an Indonesian sibling.
The live backlog is now a **staleness backlog**: 163 sources were edited after their `.id.mdx`
was last touched, plus a wide frontmatter-convention gap (see verdict below).

## Method (commands quoted, reproducible)

Worktree on fresh origin/main:

```bash
python3 scripts/agent_start.py --lane docs --task-id subhi-backlog-1006
git fetch origin main && git checkout -b agent/m5/docs/subhi-backlog-1006 origin/main
```

Coverage / backlog (source = base `.mdx`; siblings matched by replacing the suffix with `.id.mdx`):

```bash
git ls-files apps/mouth/src/content/articles | grep -c '\.id\.mdx$'      # 851
git ls-files apps/mouth/src/content/articles | grep '\.id\.mdx$' | wc -l # 851
git ls-files 'apps/mouth/src/content/articles/**/*.id.mdx' | grep -v '\.id\.mdx$' \
  | while read f; do [ -f "${f%.mdx}.id.mdx" ] || echo "$f"; done | wc -l # 0 missing
```

Staleness (per file pair: last commit timestamp of source vs `.id.mdx` via
`git log -1 --format=%ct -- <path>`; stale when source's is newer). Depth measured with
`git rev-list --count --no-merges --since=<id-mtime+1> HEAD -- <source>`. Frontmatter fields
parsed with a Python frontmatter-block regex (script in /tmp during the run; logic quoted below):

```python
fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
field = lambda name: re.search(rf"^{name}:\s*(.*)$", fm, re.M)  # presence/absence counts
```

Language sanity check: 30-file random sample, Indonesian vs English marker-word counts in the
body — 30/30 Indonesian-dominant (3515 ID markers vs 9 EN markers). The `.id.mdx` bodies are
genuinely Indonesian.

## Backlog by category (missing `.id.mdx`)

**None.** All 13 categories are at 100% sibling coverage:

| Category | Sources | `.id.mdx` present | Missing |
| --- | --- | --- | --- |
| immigration | 318 | 318 | 0 |
| business | 181 | 181 | 0 |
| tax-legal | 77 | 77 | 0 |
| business_regulations | 83 | 83 | 0 |
| lifestyle | 56 | 56 | 0 |
| tax | 50 | 50 | 0 |
| property | 32 | 32 | 0 |
| emerging_trends | 24 | 24 | 0 |
| tech | 20 | 20 | 0 |
| digital-nomad | 5 | 5 | 0 |
| bali_news | 2 | 2 | 0 |
| social_media | 2 | 2 | 0 |
| news | 1 | 1 | 0 |

## Stale translations (source newer than `.id.mdx`)

163 of 851 pairs. Depth bands (non-merge source commits after the translation's last commit):

| Band | Count |
| --- | --- |
| 1 commit behind | 29 |
| 2–5 commits behind | 130 |
| 6–20 commits behind | 4 |
| >20 | 0 |

By category:

| Category | Stale | Notes / examples |
| --- | --- | --- |
| immigration | **77** | Largest cluster. Example: `immigration/germany-national-deported-after-unauthorized-research-in-indonesian-park` (src 2026-09-24, id 2026-03-25). |
| business_regulations | **29** | Mostly regulatory news touched by the September cleanup. Example: `bank-indonesia-confirms-no-cap-on-usd-purchases-above-50k-monthly`. |
| business | **18** | Includes the 4 deepest stale files (6 source commits behind): `bali-investment-market-separating-real-opportunity-from-the-hype`, `bali-property-2026-whos-really-buying-and-what-could-go-wrong`, `bali-vs-koh-samui-where-your-property-money-actually-works-harder`, `business-set-up-transaction-support-finance-and-accounting-outsourcing-regulatory-compliance-tax-advisory-transfer-prici` (slug truncated in repo). |
| tax-legal | **15** | Example: `immigration`-adjacent PP 28/2025 property analysis lives here in `business/` but tax-law updates cluster in `tax-legal/`. |
| emerging_trends | **13** | AI/regulation news items. |
| lifestyle | 7 | — |
| bali_news | 1 | `16-warga-bali-tewas-digigit-anjing-rabies` (src 2026-09-24, id 2026-03-25). |
| social_media | 2 | — |
| tax | 1 | — |
| property, tech, digital-nomad, news | 0 | Clean. |

**Root cause of most staleness:** two bulk events. (1) `ae9418ff5e` (2026-09-24,
`fix(mouth): strip invented converter TL;DR and Next Steps filler — chunk 1/6 (#7325)`) edited
~107 source files without touching the `.id.mdx` siblings; (2) `2501e55b1d` (2026-08-11,
`fix(mouth): 107 Indonesian articles rendered the whole article where the headline goes (#4063)`)
was itself a translation-side fix, but sources re-edited after it are stale again. So the
bulk of the 163 are "source cleaned/polished after the Indonesian version was written", not
missing work.

## Frontmatter convention compliance (verdict)

The skill (`.kimi-code/skills/subhi/SKILL.md`) requires: complete Indonesian `seoTitle`, clean
`seoDescription` (no Markdown residue), valid `relatedArticles`, preserved frontmatter schema.
Measured across all 851 `.id.mdx`:

| Check | Result | Verdict |
| --- | --- | --- |
| Frontmatter block present | 851/851 | PASS |
| `title` present | 851/851 | PASS |
| `slug` present + matches source slug | 851/851, 0 mismatches | PASS |
| `seoDescription` free of Markdown residue | 851/851 clean | PASS |
| `seoTitle` present | **830/851** (21 missing) | FAIL (2.5%) |
| `seoDescription` present | **825/851** (26 missing) | FAIL (3.1%) |
| `relatedArticles` present | **295/851** (556 missing) | FAIL (65%) |
| `lang: id` present | **129/851** (722 missing) | FAIL (85%) |
| `translatedAt` timestamp field | 132/851 | Inconsistent (only 15%) |
| `translationStatus`-style field | none found (`translatedAt` is the only one in use) | Convention undefined |

**Verdict: NOT consistently applied.** The reference-polished files (PRs #2957/#2998/#2999
families, e.g. `business/accounting-software-indonesia.id.mdx`) carry the full schema —
`lang: id`, `seoTitle`, `seoDescription`, `relatedArticles`, `translatedAt` — but the bulk
backfill (the `id@2026-03-25 (86e6308535)` and `id@2026-08-11 (2501e55b1d)` waves) mostly
ships frontmatter without `lang`, `seoTitle`, `seoDescription`, and `relatedArticles`.
There is no single enforced status field; if Subhi's pipeline needs one, the convention
must be written down before it can be audited.

## Suggested batching plan (for the next translation/polish waves)

Order by (staleness depth × category traffic). No new-article batches are needed — all work is
refresh + polish.

1. **Batch 1 — "Deep-6 + legal risk" (4 files, ~6 source commits behind).** The four `business/`
   files listed above. Property/investment money numbers are exactly the class of claim the
   skill says to re-verify against authoritative sources after a source edit.
2. **Batch 2 — immigration refresh (77 files).** Biggest cluster; mostly 2–5 source commits
   behind. Split into visa-procedural evergreen vs news items; news items with only the
   TL;DR-strip delta are the cheapest re-syncs (source change was a deletion, not a rewrite —
   the Indonesian version may only need the same filler removed).
3. **Batch 3 — business_regulations + tax-legal (44 files combined).** Regulatory content,
   same re-verify-claims caveat as Batch 1.
4. **Batch 4 — emerging_trends + lifestyle + bali_news + social_media + tax (24 files).**
   News-flavored, low depth.
5. **Parallel "frontmatter schema backfill" lane (not translation work).** Add the missing
   `lang: id`, `seoTitle`, `seoDescription`, `relatedArticles` to the 722/21/26/556 files —
   mechanical, scriptable, and independent of the per-article re-translation batches above.
   Recommend deciding on a single status field (`translatedAt` vs new) in the same pass.

## What was NOT checked

- **Content diff of stale pairs** — staleness is commit-timestamp based, not a body diff. Some
  stale pairs may differ only by the removed TL;DR filler (trivial re-sync), others by real
  rewrites. A body-level delta is the first step of each refresh batch.
- **Reasoning-leak lint / repository hooks** — not run (measurement only, no new content).
- **Quality of the Indonesian prose** — only a 30-file marker-word language sanity sample,
  not native review (Angel's lane per the skill).
- **`apps/mouth/src/content/visa/**`** (4 non-article pages: `comparisons`, `expat-life`,
  `kitas`, `procedures`) — no `.id.mdx` siblings exist there; whether localized versions of
  those hub pages are wanted is an owner decision, outside the article pipeline.
- **Other locales** (`.it/.fr/.ru.mdx`) — out of scope for this audit.

## Open risks

- The 2026-09-24 cleanup (#7325, "strip invented converter TL;DR and Next Steps filler") is
  recorded as chunk **1/6** — five more chunks may land and re-stale translations again;
  any refresh batch should re-measure immediately before starting.
- 21 files missing `seoTitle` and 26 missing `seoDescription` may render empty/derived meta
  on the Indonesian pages — worth a quick production spot-check before assuming SEO parity.
- PR #2991 (the open draft for one structural-fix file) was not examined for overlap with
  the stale list; check before assigning that file to a batch.

## Adversarial review

Seat: kimi-k3 (self-review of the measurement, before Claude verifies). Objections raised
against this audit and how they survived:

1. **Timestamp staleness ≠ content staleness** — survives as a documented limitation: a pair
   can be flagged stale where the source edit only touched the TL;DR filler (trivial re-sync),
   or be timestamp-clean where a same-day bulk commit edited both sides inconsistently. The
   report states this in "What was NOT checked" and makes body-diff the first step of every
   refresh batch.
2. **Frontmatter regex parsing is shallow** — survives: fields were counted by
   `^key: value` line match only; a field present but nested/malformed (e.g. broken YAML
   continuation) would be mis-counted as present. Spot checks on reference files
   (`accounting-software-indonesia.id.mdx`) matched the regex verdict, so the counts are
   treated as directionally correct, not exact.
3. **Language sanity sample is a heuristic** — survives: 30 random files, marker-word counts,
   no human/native review. It excludes English-placeholder translations only at the body
   level, not at the quality level.
4. **`translatedAt` may be a stale-mechanics artifact, not a pipeline field** — survives: the
   report recommends an explicit convention decision rather than assuming the 132 files that
   carry it define the standard.


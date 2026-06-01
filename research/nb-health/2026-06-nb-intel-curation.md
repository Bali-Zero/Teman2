# NB Arsenal Health Report — 2026-06-01 (Monthly + Mode B+C full pass)

> Mode B+C run by nb-curator agent. Read-only — no NB mutations.
> Baseline comparison: 2026-05-31 (daily run, stored in nb-health/2026-05-31-health.md).
> Exact-URL deduplication pre-step: 0 removed today (deterministic, not reported here).
> Trigger: First Monday of month (2026-06-01) → **full pass** (all 5 NB-INTEL + stale-all).

---

## Summary

| Metric                              | May-31 | Jun-01    | Delta |
| ----------------------------------- | ------ | --------- | ----- |
| Total notebooks (default profile)   | 73     | **73**    | 0     |
| Total sources                       | 3,525  | **3,528** | +3    |
| Healthy (with sources, queryable)   | 56     | **56**    | 0     |
| Stale (updated_at >30d)             | 0      | **0**     | 0 ✅  |
| Empty (0 sources)                   | 17     | **17**    | 0     |
| Broken (timeout/error, has sources) | 0      | **0**     | 0 ✅  |
| New notebooks                       | 0      | 0         | 0     |

**Overall health: EXCELLENT.** 56/56 queryable NBs responded correctly. All NB-INTEL 5/5 healthy. All MATA GARUDA 4/4 healthy. Zero broken, zero stale.

---

## Source Count Changes Today (+3 total)

| NB                                | UUID     | May-31 | Jun-01  | Delta | Notes                                           |
| --------------------------------- | -------- | ------ | ------- | ----- | ----------------------------------------------- |
| NB-4: Tax & Fiscal                | d4b2eedb | 152    | **155** | +3    | 3 new sources added; YouTube dups still present |
| NB-14: Claude Code Session Memory | 1e5f9b04 | 11     | **12**  | +1    | 1 new source added                              |
| NB-1: Nuzantara Codebase          | f6ecd115 | 75     | **75**  | 0     | Stable                                          |
| NB-2: Immigration & Visa          | cff93ab0 | 109    | **109** | 0     | Stable                                          |

Changes organic and expected. NB-4 +3 may include legitimate new fiscal docs (alongside the 13 YouTube dups still pending removal).

---

## NB-INTEL Family — Status ✅

All 5 NB-INTEL queryable and healthy. **Feeder remains paused — week 7 (day 9/23).**

| NB                | UUID     | Sources | May-31 | Delta | Status     | Latest content date         |
| ----------------- | -------- | ------- | ------ | ----- | ---------- | --------------------------- |
| INTEL-AIResearch  | dc5d01cd | 356     | 356    | 0     | ✅ Healthy | (archive — no new feed)     |
| INTEL-Press       | 9d262101 | 216     | 216    | 0     | ✅ Healthy | 2026-05-11 (WNA Kedonganan) |
| INTEL-Immigration | 1ed02e54 | 80      | 80     | 0     | ✅ Healthy | 2026-05-06 test marker      |
| INTEL-Regulation  | a17f134e | 41      | 41     | 0     | ✅ Healthy | PP 28/2025 (OSS RBA news)   |
| INTEL-Tax         | 7fb12c9c | 17      | 17     | 0     | ✅ Healthy | 2026-05-12 (PER 6/2026 DJP) |

**⚠️ Feeder paused — 7th consecutive week.** Content NOT yet stale per 30-day threshold, but window is closing:

| NB-INTEL                       | Paused since | Stale alarm at | Days remaining |
| ------------------------------ | ------------ | -------------- | -------------- |
| Immigration / Regulation / Tax | 2026-05-23   | **2026-06-22** | **21 days**    |
| Press / AIResearch             | 2026-05-25   | **2026-06-24** | **23 days**    |

**Critical**: if feeder not restarted before 2026-06-22, Immigration/Regulation/Tax will cross the 30-day stale threshold and the next health report will flag them stale.

---

## NB-INTEL Monthly Inventory Snapshot

| NB-INTEL          | Jun-01 sources | May-01 baseline (approx) | Monthly delta                                |
| ----------------- | -------------- | ------------------------ | -------------------------------------------- |
| INTEL-AIResearch  | 356            | ~599 (pre-drain)         | −243 (drain event 2026-05-25/26, now stable) |
| INTEL-Press       | 216            | ~200 (est.)              | +16 (approx)                                 |
| INTEL-Immigration | 80             | ~70 (est.)               | +10 (approx)                                 |
| INTEL-Regulation  | 41             | ~35 (est.)               | +6 (approx)                                  |
| INTEL-Tax         | 17             | ~15 (est.)               | +2 (approx)                                  |

Note: AIResearch drain (599→356) occurred 2026-05-25/26, cause unknown but stable at 356 for 7 days. No further loss.

---

## MATA GARUDA Family — Status ✅

All 4 healthy. Sources unchanged.

| NB                                 | UUID     | Sources | Status     |
| ---------------------------------- | -------- | ------- | ---------- |
| Self-Improving Agent Research      | 5af11152 | 102     | ✅ Healthy |
| Open Source Intel Tools            | e00d497a | 89      | ✅ Healthy |
| Self-Evolving Agent Research       | 305f5f2e | 57      | ✅ Healthy |
| Intelligence Architecture Research | 76de5123 | 51      | ✅ Healthy |

---

## Core Stack — Probe Results ✅

All core stack NBs queried and responded with coherent domain-relevant answers:

| NB                 | UUID     | Sources | Status     |
| ------------------ | -------- | ------- | ---------- |
| NB-1 Codebase      | f6ecd115 | 75      | ✅ Healthy |
| NB-2 Immigration   | cff93ab0 | 109     | ✅ Healthy |
| NB-3 Company Setup | 933509f9 | 193     | ✅ Healthy |
| NB-4 Tax           | d4b2eedb | 155     | ✅ Healthy |
| NB-5 Property      | d9438180 | 141     | ✅ Healthy |
| NB-6 Compliance    | 85207af3 | 199     | ✅ Healthy |
| NB-7 Editorial     | f51ab8a0 | 99      | ✅ Healthy |
| NB-8 Expat Life    | 4fd8cd0f | 150     | ✅ Healthy |
| NB-9 Research Lab  | d2a05271 | 197     | ✅ Healthy |
| NB-10 Team Guides  | f0307c2c | 161     | ✅ Healthy |
| NB-AGENTS          | 6d449787 | 157     | ✅ Healthy |
| NB-DESIGN-AGENT    | 815b081c | 12      | ✅ Healthy |
| NB-0 Zantara       | f03b5c70 | 4       | ✅ Healthy |

---

## Mode C — Full Pass Dedup/Summarize Proposals

### Scope: First Monday of month → all 5 NB-INTEL + stale-all pass

---

### NB-INTEL-Press (216 sources)

**Source type breakdown**: 215 `generated_text` (hash-named `nlm_feed_*.txt`), 1 `web_page`

**Near-dup analysis**: No new clusters found. All 215 generated_text sources have opaque hash names — title-based dedup not possible without content inspection. No web_page additions since last report.

**Summarization candidates (≥10 from same topic in one week)**: Not detectable from titles alone (all `nlm_feed_<hash>.txt`). Would require content inspection to cluster by topic. **0 summarization proposals** this pass.

**Carried forward proposals (UNCHANGED from May-29):**

```
CLUSTER NB-INTEL-Press PRESS-1
  keep: (none — garbage source)
  remove: b7a6ee97 "Neoregelia lillyae - Wikipedia"
  reason: URL is wikipedia.org/wiki/Special:Random — random article, zero press value
  action: Manual deletion via NotebookLM UI → Manage sources → delete b7a6ee97
```

**New proposals this pass: 0**
**Total Press proposals: 1** (unchanged)

---

### NB-INTEL-AIResearch (356 sources)

**Source type breakdown**: 220 `web_page`, 120 `generated_text`, 10 `pasted_text`, 6 `pdf`

**Exact title duplicates found**: 3 groups

#### AIR-1 — 9× Cloudflare "Just a moment..." (UNCHANGED — remove all 9)

```
CLUSTER NB-INTEL-AIResearch AIR-1
  keep: (none — all are Cloudflare bot-challenge pages)
  remove: 50bf613a, 88a840bc, 8d600b73, 9c7ad762, ad88f4db, b85199c9, bda8a48e, cda0e126, e143f418
  reason: title="Just a moment..." = Cloudflare bot challenge interstitial, zero content value
  URLs: confirmed different (tcude.net, sealos.io, ai.plainenglish.io, gamesbeat.com, etc.)
         — all legitimate AI research URLs blocked by Cloudflare at scrape time
  note: underlying articles (Claude Code monitoring, multi-agent, etc.) are valuable topics
        but content was never captured. Remove entries; re-add if URLs become accessible.
  action: Manual deletion via NotebookLM UI → remove all 9 source IDs
```

#### AIR-2 — 4× Maltego Knowledge Base (CONFIRMED NOT DUP — DO NOT REMOVE)

```
NOT A DUP CLUSTER — RETAIN ALL 4
  5a2d4999: docs.maltego.com/…/what-is-a-transform-distribution-server
  7b43831a: docs.maltego.com/…/system-architecture
  b0c8cdeb: docs.maltego.com/…/tds-transforms
  eec390b2: docs.maltego.com/…/guide-to-building-maltego-integrations
  reason: same site brand name "Maltego Knowledge Base" but 4 DIFFERENT article URLs
  — confirmed multiple times. Keep all 4. Do NOT touch.
```

#### AIR-3 — 4× Vercel Security Checkpoint (UNCHANGED — remove all 4)

```
CLUSTER NB-INTEL-AIResearch AIR-3
  keep: (none — all are Vercel bot-challenge pages)
  remove: 0a48f083, 1ef262e8, 9cb188a0, ef5a2a75
  reason: title="Vercel Security Checkpoint" = Vercel bot-challenge interstitial
  URLs: venturebeat.com (×2), mcpmarket.com (×2) — legitimate AI research blocked at scrape
  note: Anthropic Claude Code releases (VentureBeat) are high-value missing content.
        Remove entries; monitor if VentureBeat unblocks Vercel proxy.
  action: Manual deletion via NotebookLM UI → remove all 4 source IDs
```

**AIResearch total proposed removals: 13** (9 AIR-1 + 4 AIR-3). After removal: 343 effective sources.

**Summarization proposals (AIResearch)**: None — regulation/research citations must stay verbatim per spec.

---

### NB-INTEL-Immigration (80 sources)

**Source type breakdown**: 79 `generated_text`, 1 `web_page`

**Exact title duplicates**: 0 groups ✅

**Near-dup clusters (Levenshtein ≤3, same domain/week)**: None detected.

**No proposals for Immigration.**

---

### NB-INTEL-Regulation (41 sources)

**Source type breakdown**: 38 `generated_text`, 3 `web_page`

**Title match analysis — 1 apparent group found, INVESTIGATED:**

```
NOT A DUP CLUSTER — RETAIN BOTH
  370c6e89: "OSS RBA - Sistem Perizinan Berusaha Terintegrasi Secara Elektronik"
             URL: oss.go.id/id/berita/oss-contact-center-service-hours
  574f0767: "OSS RBA - Sistem Perizinan Berusaha Terintegrasi Secara Elektronik"
             URL: oss.go.id/id/berita/rosan-perkasa-roeslani-officially-assumes-office-...
  reason: Both share the oss.go.id header/navigation title "OSS RBA - Sistem..."
          but are 2 DIFFERENT articles (contact center hours vs. minister appointment).
          This is a website-header-as-page-title artifact. Content is distinct. KEEP BOTH.
  note: Third source eba1e6a2 "OSS RBA - Partisipasi Perempuan..." has unique title — unrelated.
```

**No proposals for Regulation.**

---

### NB-INTEL-Tax (17 sources)

**Source type breakdown**: 15 `generated_text`, 2 `web_page`

**Exact title duplicates**: 0 groups ✅

**No proposals for Tax.**

---

### NB-4 Tax — YouTube Dups (FULL PASS RECONFIRMATION)

NB-4 now has **155 sources** (was 152 on May-31, +3 organic additions today). YouTube dups confirmed still present:

**Source type breakdown**: 19 `youtube`, 56 `web_page`, 38 `pasted_text`, 20 `generated_text`, 19 `pdf`, 3 `word_doc`

YouTube dups: **13 sources** across 3 clusters (UNCHANGED from May-30):

#### TAX-1 — 9× duplicate YouTube video (remove 8, keep 1)

```
CLUSTER NB-4 TAX-1
  keep: 0044a518 "Step by Step Belajar Mudah Mengisi SPT PPh Badan di Coretax Jilid 2"
  remove: 31b1e576, 5fa290ff, 6d966bdd, 9f036179, a9167e83, c119363c, f3be654f, fea0725e
  reason: identical title (Levenshtein=0), type=youtube, url=null — pre-step URL dedup bypassed
  action: Remove 8 sources from NB-4 via NotebookLM UI
```

#### TAX-2 — 2× duplicate YouTube video (remove 1, keep 1)

```
CLUSTER NB-4 TAX-2
  keep: 1320d061 "Tutorial Pelaporan SPT Tahunan Orang Pribadi — CoreTax"
  remove: 7531256f
  reason: identical title, type=youtube, url=null
  action: Remove 1 source from NB-4 via NotebookLM UI
```

#### TAX-3 — 2× duplicate YouTube video (remove 1, keep 1)

```
CLUSTER NB-4 TAX-3
  keep: 0b889bda "[Podcast Cermati Eps. 34] SPT Tahunan PPh 2025"
  remove: 65e3a6be
  reason: identical title, type=youtube, url=null
  action: Remove 1 source from NB-4 via NotebookLM UI
```

**NB-4 YouTube dup total proposed removals: 10** (8+1+1). After removal: 145 effective sources.

---

## Summary of All Proposals

| NB                  | Cluster | Type                       | Proposed removals | Action                         |
| ------------------- | ------- | -------------------------- | ----------------- | ------------------------------ |
| NB-INTEL-Press      | PRESS-1 | Garbage (Wikipedia Random) | 1                 | Remove b7a6ee97                |
| NB-4 Tax            | TAX-1   | YouTube exact dup (9×)     | 8                 | Keep 0044a518, remove 8        |
| NB-4 Tax            | TAX-2   | YouTube exact dup (2×)     | 1                 | Keep 1320d061, remove 7531256f |
| NB-4 Tax            | TAX-3   | YouTube exact dup (2×)     | 1                 | Keep 0b889bda, remove 65e3a6be |
| NB-INTEL-AIResearch | AIR-1   | Garbage (Cloudflare 9×)    | 9                 | Remove all 9                   |
| NB-INTEL-AIResearch | AIR-3   | Garbage (Vercel 4×)        | 4                 | Remove all 4                   |
| **TOTAL**           |         |                            | **24**            |                                |

**Not proposed** (confirmed NOT dups, carry-forward from May-31):

- AIR-2 (Maltego KB 4×): 4 different article URLs — keep all.
- REG OSS-RBA (2×): different article URLs under same site header — keep both.

---

## Stale Sources >90 Days

Source-level `created_at` timestamp NOT available in current `nlm source list` schema (fields: `id`, `title`, `type`, `url` only). NB-level stale detection only.

**NB-level stale check**: All 56 healthy NBs have `updated_at` within 30 days. **0 stale NBs.**

---

## Routing Log Analysis — Last 7 Days (2026-05-25 → 2026-06-01)

**Mode A queries recorded:**

- 2026-05-26: NB-2 (cff93ab0) queried 2× by `card-building-pipeline` and `docs-kepmen-visa-taxonomy` (visa/legal domain). Confidence 0.95.

**Underused NBs** (0 Mode A queries in last 7 days):

- 71 of 73 NBs queried 0× via Mode A routing.
- Mode A pipeline not yet fully wired into all agent chains — this is structural, not a health signal.
- Candidates for archive review if 0 queries persist 90+ days:
  - NB-PROBE-SANDBOX (0 sources, clearly transient)
  - ARCHIVED/MERGED group (6 NBs, tagged for deletion 2026-05-07, still present)
  - Research ad-hoc empty NBs (17 empty NBs — see housekeeping)

**Gap warnings filed last 7 days**: **0**

---

## Transitions Since May-31

| NB                       | Transition         | Notes                                        |
| ------------------------ | ------------------ | -------------------------------------------- |
| NB-4                     | sources: 152 → 155 | +3 organic additions; YouTube dups unchanged |
| NB-14                    | sources: 11 → 12   | +1 organic addition                          |
| All other 54 healthy NBs | —                  | Unchanged                                    |

No healthy→broken, no broken→healthy, no healthy→stale transitions.

---

## Recommended Actions (Antonello — Monthly Review June 2026)

### 🔴 P1 — Feeder restart (URGENT — 21 days to stale)

- [ ] **Restart NB-INTEL feeder** (`bali-intel-scraper` cron on Mini). All 5 NB-INTEL frozen since 2026-05-23/25.
  - Check status: `ssh mini 'launchctl list | grep intel'`
  - If not running: `ssh mini 'launchctl start com.balizero.bali-intel-scraper'`
  - **Hard deadline**: 2026-06-22 before Immigration/Regulation/Tax cross 30-day stale threshold.

### 🟡 P2 — Dedup execution (24 total pending, unchanged from May-31)

- [ ] **NB-4 YouTube dups**: Remove 10 sources (TAX-1: 8, TAX-2: 1, TAX-3: 1).
  - All type=`youtube`, url=null (URL dedup pre-step cannot catch these — manual only).
  - Via NotebookLM UI → NB-4 → Manage sources → delete by source ID.
  - After: NB-4 drops from 155 → 145 effective sources.

- [ ] **NB-INTEL-AIResearch garbage**: Remove 13 sources (AIR-1: 9 Cloudflare, AIR-3: 4 Vercel).
  - Via NotebookLM UI → NB-INTEL-AIResearch → Manage sources.
  - After: AIResearch drops from 356 → 343 effective sources.

- [ ] **NB-INTEL-Press anomaly**: Remove 1 source (PRESS-1: Wikipedia Special:Random `b7a6ee97`).
  - Via NotebookLM UI → NB-INTEL-Press → Manage sources → delete b7a6ee97.

### 🟠 P3 — AIResearch drain investigation

- [ ] **Investigate AIResearch 599→356 drain** (−243 sources, occurred 2026-05-25/26).
  - Now stable at 356 for 7 days. No further loss.
  - Was content actually removed or was the May-25 count inflated by ARCHIVED NBs?
  - Check: `nlm notebook list -p default --json | jq '[.[] | select(.title | contains("AIResearch"))] | .[] | {title, sources}'`

### 🟢 P4 — Inventory housekeeping

- [ ] **Delete ARCHIVED-DELETE NBs**: `46b4dfe0` (NB-NLM-ELEVATION, 6 src) + `4a8f3162` (Analisi Video AI Agency, 67 src) — tagged for deletion 2026-05-07, still present after 25 days.

- [ ] **Decide fate of 17 empty NBs**: 9 are research scaffolds (KITAP/KITAS/Tax Changes/Immigration Search/HGB Property/Veo Competitors/etc.) — either populate within 30 days or delete.

- [ ] **Decide MERGED-INTO NBs** (4 NBs, 322 sources): `d97ff70b` (Nexus/Palantir 44 src), `917a1300` (World Models 49 src), `201b4b94` (Digital Sovereignty 150 src), `50396b3e` (Claude Code 129 src) — all tagged MERGED-INTO-... on 2026-05-07. Still live with sources. Safe to delete if content is confirmed in target NBs.

- [ ] **Confirm MATA GARUDA Gov deletion**: 313 src permanently absent since May-17. No recovery needed per Antonello acceptance.

### ℹ️ INFO

- **Feeder pause impact summary**: NB-INTEL content frozen as of May-23/25. No new regulatory changes, press coverage, or AI research captured for 9 days. INTEL-based agent queries remain valid for historical content but should be supplemented by web search for anything post-May-23.
- **NB-4 +3 today**: may include fiscal regulation updates. If urgent tax query needed, use full 155-source NB-4 (note: the 13 YouTube dups consume 10 source slots but don't degrade query quality significantly).
- **Mode A routing**: Only NB-2 queried in last 7 days (visa/legal cards). Mode A pipeline not yet fully wired to all agent chains.

---

## No Telegram Sent

Criteria: 3+ broken NBs OR new critical gap warnings.

- Broken NBs: **0** (threshold: 3)
- New gap warnings: **0**
- Telegram: **NOT dispatched** ✅

---

_Report generated: 2026-06-01 by nb-curator agent (Mode B+C full monthly pass)_
_Previous report: nb-health/2026-05-31-health.md_
_Next scheduled full pass: 2026-07-06 (first Monday of July)_
_Next weekly press-only pass: 2026-06-08 (Monday)_
_Inventory snapshot basis: `nlm notebook list -p default --json` (2026-06-01 WITA)_

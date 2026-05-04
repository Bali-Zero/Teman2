# Hari 7 — Pick 12 Money Pages

**Mission ref:** §4 D2 12 money pages (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 2-3 jam
**Pre-req:** Day 5 selesai (article-inventory CSV ada)

## Tujuan

Dari 149 artikel, pick 12 yang paling potensi untuk dikonversi jadi
"money pages" — artikel yang attract organic traffic dengan intent
commercial yang tinggi. Output: list 12 slug + 1-line bahasa rationale
per slug, save di `exercises/_outputs/12_money_pages.md`.

## Konteks

Day 6 = weekend, kamu istirahat. Senin (Day 7), pick 12 money pages.

Definisi money page: artikel yang:

1. Intent commercial atau hybrid (orang yang baca cenderung mau beli)
2. SEO potential (search volume Indonesia ada)
3. Bali Zero punya service yang match (visa/company/tax/property)
4. Currently underperforming (lead < 1/bulan tapi traffic ada)

Dari 12 ini, kamu akan transform per-1-per-1 di Day 8+ dengan add CTA
+ internal link + WhatsApp click.

## Pre-requisiti

- [ ] CSV `article-inventory-*.csv` exists (Day 5 output)
- [ ] Akses NB-2, NB-9 via tutor
- [ ] Akses Search Console (viewer role) — kalau belum, ping Antonello

## Langkah-langkah

### 1. Buat branch

```bash
cd ~/Projects/nuzantara
git checkout main && git pull
git checkout -b sancho/d7-money-pages
```

### 2. Filter CSV — commercial only

```bash
# Filter only commercial intent rows
grep ",commercial," article-inventory-*.csv | head -30 > /tmp/commercial-articles.txt

wc -l /tmp/commercial-articles.txt
# Kalau jumlah ≥30 → bagus, kita punya pool yang cukup untuk filter
# Kalau <20 → re-classify some informational ke commercial (Day 5 heuristic perlu tweak)
```

### 3. Tanya NB-9 tentang queries komersial Indonesia 2026

```
/agent zantara-onboarding query NB-9: queries paling commercial / high-intent untuk Indonesia 2026 di domain visa, PT PMA, tax, property. Saya butuh top 5 keyword tiap cluster.
```

Tutor balikin keyword list per cluster, mis:

```
Visa cluster:
- "biaya KITAS investor 2026"
- "KITAS C7 syarat"
- "Golden Visa Indonesia"
- ...

PT PMA cluster:
- "biaya PT PMA Bali"
- "syarat PT PMA hospitality"
- "KBLI hospitality 2026"
- ...
```

### 4. Cross-reference dengan article inventory

Dari list keyword, find article yang ada di CSV dengan slug yang
match topic. Pakai grep:

```bash
# Visa cluster
grep -i "kitas" article-inventory-*.csv
grep -i "visa" article-inventory-*.csv

# Property cluster
grep -i "property\|sewa\|hak-pakai" article-inventory-*.csv
```

Catat di `local/notes-day7-cross-ref.md`:

```
Visa cluster:
- Article: panduan-kitas-investor.md (slug: panduan-kitas-investor)
  Match keyword: "biaya KITAS investor 2026"
  Word count: 2400 words
  Notes: artikel panjang, ada step-by-step, bisa add CTA Apply KITAS
- ...
```

### 5. Cross-reference dengan Search Console (optional, kalau access ready)

Buka Search Console → Performance → Queries.

Filter by impressions ≥100 last 90 days, click ≥10. Sort by CTR ascending.

Catat artikel-artikel yang dapat impressions tapi CTR rendah — ini
indikator: orang search, lihat snippet, tidak klik. Money page candidate.

Kalau Search Console belum siap, skip step ini.

### 6. Pick 12 final — 3 per cluster

Visa: 3 articles
PT PMA / Company: 3 articles
Tax: 3 articles
Property: 3 articles

Pertimbangan pick:

- Word count ≥1000 (long enough to rank)
- Intent commercial (Day 5 classification)
- Match high-volume keyword (NB-9 list)
- Bali Zero punya service yang match (cek dengan tutor:
  `apakah Bali Zero offer service untuk topic X?`)

### 7. Tulis 1-line rationale per slug

Format:

```markdown
1. **panduan-kitas-investor** (visa cluster)
   - Match keyword: "biaya KITAS investor 2026" (NB-9, high commercial intent)
   - Word count: 2400 — rankable
   - Why money page: artikel sudah ada, missing CTA Apply KITAS C7
   - Service match: Bali Zero offer KITAS C7 application

2. **kbli-hospitality-2026** (company cluster)
   - Match keyword: "KBLI hospitality 2026" (NB-9)
   - Word count: 1800
   - Why: artikel mention 5 KBLI codes, missing internal link ke KBLI Navigator
   - Service match: PT PMA setup hospitality

... (10 more)
```

### 8. Save output

```bash
mkdir -p apps/zantara-onboarding/exercises/_outputs
# Tunggu: ini di onboarding workspace, BUKAN di main repo. Output Subhi
# yang akan jadi PR di main repo:

# Save di main repo workspace (~/Projects/nuzantara/) untuk PR:
mkdir -p docs/growth-systems/
code docs/growth-systems/12-money-pages-2026-Q2.md
```

Paste 12 entries dengan rationale.

### 9. Tutor review

```
/agent zantara-onboarding saya pick 12 money pages: [paste list]. Tolong sanity-check: ada cluster yang underrepresented? Ada artikel yang seharusnya di-skip karena scope ROSSO atau service mismatch?
```

Tutor review, kasih feedback. Adjust list kalau ada issue.

### 10. Commit + push

```bash
git add docs/growth-systems/12-money-pages-2026-Q2.md

git commit -m "$(cat <<'EOF'
docs(growth-systems): pick 12 money pages 2026-Q2 (D7)

Selection of 12 articles (3 per cluster: visa, PT PMA, tax, property)
to transform into money pages over the next 2 weeks. Each entry has
1-line rationale referencing NB-9 keyword research, word count
threshold (≥1000), and service match.

This is the input for Day 8+ workstream: add CTA + internal links +
WhatsApp click on these 12 pages, target ≥8 lead/bulan attribution by
day 30.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push origin sancho/d7-money-pages

gh pr create --title "docs(growth-systems): pick 12 money pages 2026-Q2 (D7)" \
  --body "$(cat <<'EOF'
## Summary
- 12 money pages picked (3 per cluster: visa/PT PMA/tax/property)
- Source: article-inventory CSV (Day 5) + NB-9 keyword research
- Each entry has 1-line rationale + service match check

## Methodology
- Filter CSV `intent=commercial` (~30 candidates)
- Cross-reference NB-9 high-volume keywords Indonesia 2026
- Filter word_count ≥ 1000
- Service match check (Bali Zero offer service untuk topic ini?)
- Tutor sanity-check distribusi cluster

## Next
- Day 8-21: transform 12 pages (1-2 per day) — add CTA + internal links + WA click
- Day 30: measure attribution, target ≥8 lead/bulan

## Test plan
- [x] Tutor sanity-check distribusi cluster — green
- [x] Service match per entry verified
- [ ] Antonello review pick + rationale
EOF
)"
```

## Verifikasi

- [ ] 12 entries di file
- [ ] 3 per cluster (visa/PT PMA/tax/property)
- [ ] Tiap entry punya: slug, cluster, keyword match, word count, why money page, service match
- [ ] PR open

## Kalau ada blocker

| Masalah | Fix |
| --- | --- |
| Pool commercial < 12 | Day 5 heuristic kurang baik. Re-classify some informational (yang ada "harga" atau "biaya" di body). |
| 1 cluster cuma 1-2 article (mis. property) | OK — pilih dari informational yang bisa "upgrade" jadi commercial dengan rewrite. Catat di rationale. |
| Tidak ada Search Console access | Skip step 5, pakai NB-9 only. Cukup. |
| Service match tidak jelas (Bali Zero offer atau tidak?) | Tanya Antonello langsung — service catalog PRICING_REFERENCE.md di main repo |

## Selesai?

PR open + Antonello review. Lanjut Day 8: transform money page pertama
(pick 1 dari 12 dan kerjakan).

Tutor akan auto-generate exercise Day 8+ on demand sesuai mission §4.

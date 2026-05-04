# Hari 5 — Article Inventory CSV

**Mission ref:** §4 D2 money pages prep (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 90 menit
**Pre-req:** Day 4 selesai

## Tujuan

Bikin inventory 149 article di `apps/mouth/src/content/articles/`,
classify by category, output CSV dengan kolom `slug,category,intent,
word_count`. Ini foundation untuk Day 7 (pick 12 money pages).

## Konteks

Bali Zero punya 149 artikel. Banyak di antaranya tidak ada CTA atau
internal link. Sebagai Growth Systems Owner, Subhi perlu visibility:

- Berapa artikel per kategori?
- Mana yang panjang (≥1000 kata) vs pendek (<500 kata)?
- Apa intent setiap artikel? (informational / commercial / navigational)

CSV ini jadi data source untuk pick top 3 per cluster di Day 7.

## Pre-requisiti

- [ ] Day 4 selesai
- [ ] CWD `~/Projects/nuzantara/`
- [ ] Branch baru `sancho/d5-article-inventory`

## Langkah-langkah

### 1. Buat branch

```bash
cd ~/Projects/nuzantara
git checkout main && git pull
git checkout -b sancho/d5-article-inventory
```

### 2. Eksplor struktur articles

```bash
ls apps/mouth/src/content/articles/
```

Output category dirs:

```
business/
general/
immigration/
property/
tax/
```

Cek sample article:

```bash
ls apps/mouth/src/content/articles/immigration/ | head -5
cat apps/mouth/src/content/articles/immigration/<sample>.md | head -30
```

Catat frontmatter pattern:

```yaml
---
title: ...
slug: ...
date: ...
category: ...
description: ...
---
```

### 3. Tulis script inventory

Buat script di `scripts/article-inventory.sh`:

```bash
#!/bin/bash
# scripts/article-inventory.sh
# Generate CSV inventory of all articles

OUTPUT="article-inventory-$(date +%Y%m%d).csv"
echo "slug,category,intent,word_count" > "$OUTPUT"

cd apps/mouth/src/content/articles

for category in */; do
  category_name="${category%/}"

  for article in "$category"*.md; do
    [[ -f "$article" ]] || continue

    slug=$(basename "$article" .md)
    word_count=$(wc -w < "$article" | tr -d ' ')

    # Heuristic intent classification
    if grep -qE "(harga|price|biaya|cost)" "$article"; then
      intent="commercial"
    elif grep -qE "(bagaimana|how to|cara|step)" "$article"; then
      intent="informational"
    elif grep -qE "(panduan|guide|complete)" "$article"; then
      intent="commercial"
    else
      intent="informational"
    fi

    echo "${slug},${category_name},${intent},${word_count}" >> "../../../../$OUTPUT"
  done
done

echo "Generated $OUTPUT"
echo "Total rows:"
wc -l < "$OUTPUT"
```

Make executable:

```bash
chmod +x scripts/article-inventory.sh
```

Run:

```bash
./scripts/article-inventory.sh
```

### 4. Verifikasi CSV

```bash
ls -la article-inventory-*.csv
head -5 article-inventory-*.csv
wc -l article-inventory-*.csv
```

Output minimum:

```
150 article-inventory-20260507.csv
# (149 articles + 1 header row)
```

### 5. Spot-check classification

Open CSV di VSCode atau LibreOffice. Sample 5 rows random, verify:

- `category` correct (matches dir name)
- `intent` reasonable (kalau title ada "Harga KITAS" → commercial, kalau "Apa itu KITAS" → informational)
- `word_count` non-zero

Kalau ada anomali (semua intent = informational, atau word_count = 0),
debug script.

### 6. Tutor review

```
/agent zantara-onboarding saya generate article-inventory CSV dengan 149 row. Distribusi kategori: business=X, immigration=Y, tax=Z, property=W, general=V. Distribusi intent: commercial=A, informational=B. Apakah heuristic intent ini reasonable atau ada artikel yang misclassified?
```

Tutor sample 5-10 row, check, kasih saran improve heuristic kalau perlu.

### 7. Improve heuristic (optional)

Berdasarkan tutor feedback, tweak script. Misal:

- Tambah pattern "biaya kapan", "berapa lama" → informational (timeline question)
- Pattern "vs", "perbedaan" → comparison (commercial)
- Pattern "FAQ", "pertanyaan umum" → informational

Re-run script, re-verify CSV.

### 8. Commit + push

```bash
git add scripts/article-inventory.sh article-inventory-*.csv

git commit -m "$(cat <<'EOF'
feat(scripts): article inventory CSV generator (D5)

Adds scripts/article-inventory.sh that walks
apps/mouth/src/content/articles/ and outputs CSV with columns
slug,category,intent,word_count for all 149 articles.

Intent classification is heuristic-based (regex on body text):
- commercial: harga|price|biaya|cost|panduan|guide|complete|vs|perbedaan
- informational: bagaimana|how to|cara|step|FAQ|pertanyaan

CSV is foundation for Day 7 money pages selection (pick top 3 per
cluster). Output file timestamped to allow comparison over time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push origin sancho/d5-article-inventory
```

### 9. Open PR

```bash
gh pr create --title "feat(scripts): article inventory CSV generator (D5)" \
  --body "$(cat <<'EOF'
## Summary
- Script bash untuk generate CSV inventory 149 article
- Kolom: slug, category, intent (commercial/informational), word_count
- Heuristic classification reasonable per tutor review

## Test plan
- [x] Run lokal — 149 row generated (+1 header)
- [x] Spot-check 10 rows manual
- [x] Tutor review distribusi
- [ ] Antonello review

## Output preview
[paste 5 sample row di sini]

## Next
- Day 7: pick top 3 commercial per cluster (visa/company/tax/property) = 12 money pages
EOF
)"
```

## Verifikasi

- [ ] CSV file generated
- [ ] 149+ rows (kalau lebih, kemungkinan duplicate atau ada di subfolder)
- [ ] Distribusi category masuk akal (mostly business + immigration + tax + property)
- [ ] PR open

## Kalau ada error

| Masalah | Fix |
| --- | --- |
| Bash script error "permission denied" | `chmod +x scripts/article-inventory.sh` |
| Path articles berbeda (mungkin restructure) | Tutor cek path, update script |
| Word count 0 untuk beberapa file | Kemungkinan article kosong (TODO file) — flag, exclude dari CSV |
| Encoding issue (special chars) | `iconv -f utf-8 -t utf-8 < file` validate, atau tweak script |

## Selesai?

PR open. Lanjut weekend (Day 6 = istirahat). Day 7 Senin: pick 12 money
pages dari CSV ini.

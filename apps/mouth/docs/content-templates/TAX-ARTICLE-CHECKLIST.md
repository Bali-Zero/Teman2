# Tax Article SEO Checklist

Pre-commit checklist sebelum push artikel baru di cluster tax.

## Frontmatter

- [ ] `title` 50-65 chars, primary keyword di awal, year 2026 included
- [ ] `description` 150-160 chars, ada primary keyword + action verb
- [ ] `category` = "tax" (BUKAN "tax-legal" atau category lain)
- [ ] `canonicalUrl` pakai `/tax/[slug]` (BUKAN `/tax-legal/`)
- [ ] `updatedAt` dan `publishedAt` real date
- [ ] `seoTitle` 50-60 chars
- [ ] `seoDescription` 150-160 chars
- [ ] `relatedArticles` = 5 sibling dari cluster yang sama
- [ ] `image` path: `/og/tax/[slug].png`

## Structure

- [ ] Import block setelah frontmatter:
  - [ ] `HeaderWhatsAppCTA`
  - [ ] `ArticleClusterCTA`
  - [ ] `KeyTakeaway`
- [ ] H1 muncul TEPAT setelah import (SEO critical — jangan lewat)
- [ ] `<KeyTakeaway>` TL;DR setelah H1
- [ ] `<HeaderWhatsAppCTA />` setelah TL;DR (above the fold)
- [ ] Minimum 4 H2 sections
- [ ] `<ArticleClusterCTA slug="..." />` di tengah artikel
- [ ] FAQ section dengan minimum 5 long-tail questions
- [ ] CTA footer "Get Help With [TOPIC]"
- [ ] `<HeaderWhatsAppCTA />` di footer

## Content Integrity

- [ ] Hanya gunakan verified regulatory facts (cek NB-4 verification list)
- [ ] Tidak hardcode phone/email/WA URL
- [ ] Internal links pakai `/tax/[slug]` path
- [ ] Minimum 1 tabel dengan rate/scenario comparison
- [ ] Minimum 3 scenario examples
- [ ] Regulation citation jelas (KEP, PMK, UU referenced eksplisit)

## Technical

- [ ] File path: `apps/mouth/src/content/articles/tax/[slug].mdx`
- [ ] Slug: kebab-case, descriptive, contains primary keyword
- [ ] `npx tsc --noEmit` clean
- [ ] `npx prettier --write [file]` applied
- [ ] No `console.log` atau debug statements
- [ ] No leftover `[BRACKETS]` placeholders

## Pre-Commit

- [ ] Branch naming: `feat/c[X]-[topic]-[YYYY-MM-DD]`
- [ ] Commit format: `content(tax): [description]`
- [ ] Pre-commit hooks pass (husky)
- [ ] PR description: cluster, target GSC position, key claims, regulatory references

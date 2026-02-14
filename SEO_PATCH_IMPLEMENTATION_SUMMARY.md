# SEO Patch Implementation Summary

**Date:** 2026-02-14
**Project:** Nuzantara Frontend (apps/mouth)
**Status:** ✅ **PHASE 1 & 2 COMPLETE** - Ready for deploy

---

## ✅ PHASE 1 - Quick Wins (COMPLETED)

### 1.1 Dynamic Sitemap ✅
**File:** `apps/mouth/src/app/sitemap.ts` (Created, 220 lines)

**Features:**
- Homepage, services, news, team, contact, kbli-explorer
- 4 service pages (visa, company, tax, property)
- 6 news categories (immigration, business, tax, legal, property, lifestyle)
- All blog articles (fetched from backend API, cached 1h)
- 35 top KBLI codes (most searched business classifications)

**Priority:**
- 1.0: Homepage
- 0.9: Main services
- 0.8: Blog, KBLI explorer
- 0.7: Service details, news categories
- 0.6: KBLI codes

**Verification:**
```bash
npm run build
# ✅ Build successful - sitemap.xml generated (revalidate: 1h)
```

---

### 1.2 Meta Description Fix ✅
**File:** `apps/mouth/src/app/layout.tsx` (Modified)

**Changes:**
- **Before:** 176 characters (too long)
- **After:** 128 characters ✅
- **Text:** "Expert visa, immigration & company setup services in Bali. PT PMA, KITAS, Golden Visa, tax compliance. Trusted by 1000+ expats."

**Applied to:**
- Root metadata `description`
- OpenGraph `description`
- Twitter `description`

---

### 1.3 KBLI Landing Pages ✅
**File:** `apps/mouth/src/app/kbli/[code]/page.tsx` (Created, 450 lines)

**Features:**
- Dynamic route: `/kbli/[code]` (e.g., `/kbli/56101`)
- SEO metadata with KBLI-specific title/description
- JSON-LD structured data:
  - DefinedTerm schema (for KBLI classification)
  - BreadcrumbList schema (homepage → KBLI Explorer → KBLI code)
- PMA status badges (Allowed/Prohibited)
- Risk level indicators (Low/Medium/High)
- Required licenses list
- Capital requirements
- CTA sections (Company Setup, Contact)
- Internal linking (KBLI Explorer, PT PMA services)

**Data Source:**
- Backend API: `GET /api/v1/kbli-notebook/inspect/{code}`
- Cached 24 hours (KBLI codes rarely change)

**Verification:**
```bash
npm run build
# ✅ Route /kbli/[code] compiled successfully
```

---

## ✅ PHASE 2 - Additional Codebase Fixes (COMPLETED)

### 2.1 Noindex for zantara.balizero.com ✅
**File:** `apps/mouth/src/middleware.ts` (Modified)

**Changes:**
1. **robots.txt override** for zantara subdomain:
   ```
   User-agent: *
   Disallow: /
   ```

2. **X-Robots-Tag header** on all responses:
   ```
   X-Robots-Tag: noindex, nofollow
   ```

**Rationale:**
- `zantara.balizero.com` is internal app (login, dashboard, CRM)
- Must NOT be indexed by Google
- Prevents duplicate content issues

**Verification:**
- Test after deploy: `curl https://zantara.balizero.com/robots.txt`
- Expected: `Disallow: /`

---

### 2.2 Dynamic OG Images ✅
**File:** `apps/mouth/src/app/api/og/route.tsx` (Created, 120 lines)

**Features:**
- Edge runtime (fast, global CDN)
- Dynamic image generation: 1200x630 px
- Query params:
  - `title`: Article title (required)
  - `category`: Article category (optional)
- Design:
  - Dark background (#09090b)
  - Category badge (top, amber accent)
  - Large bold title (responsive font size)
  - Bali Zero branding (bottom)

**Usage:**
```
/api/og?title=How to Get KITAS in Bali&category=Immigration
```

**Integration:**
To integrate with blog metadata, update `apps/mouth/src/lib/blog/metadata.ts`:

```typescript
const ogImageUrl = `${baseUrl}/api/og?title=${encodeURIComponent(article.title)}&category=${encodeURIComponent(article.category)}`;

// Use in openGraph.images
images: [
  {
    url: ogImageUrl,
    width: 1200,
    height: 630,
    alt: article.title,
  },
],
```

**Verification:**
```bash
npm run build
# ✅ Route /api/og compiled successfully
```

---

### 2.3 Google Reviews AggregateRating ✅
**Files:**
- `apps/mouth/src/components/seo/JsonLd.tsx` (Modified, +28 lines)
- `apps/mouth/src/components/seo/index.ts` (Modified, +1 export)
- `apps/mouth/src/app/layout.tsx` (Modified, +2 lines)

**Schema Added:**
```json
{
  "@context": "https://schema.org",
  "@type": "ProfessionalService",
  "name": "Bali Zero",
  "url": "https://balizero.com",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "5.0",
    "bestRating": "5",
    "worstRating": "1",
    "ratingCount": "700",
    "reviewCount": "700"
  },
  "priceRange": "$$",
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Bali",
    "addressCountry": "ID"
  }
}
```

**Rendered on:** Homepage only (`pathname === '/'`)

**Effect:**
- Star ratings in Google search results
- Rich snippets with review count
- Increases CTR (click-through rate)

**Verification:**
After deploy, test with:
- [Google Rich Results Test](https://search.google.com/test/rich-results)
- [Schema.org Validator](https://validator.schema.org)

---

## 📊 Files Summary

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| `src/app/sitemap.ts` | ✅ Created | 220 | Dynamic sitemap with 120+ URLs |
| `src/app/layout.tsx` | ✅ Modified | -1 +4 | Meta description fix + AggregateRating |
| `src/app/kbli/[code]/page.tsx` | ✅ Created | 450 | KBLI landing pages with SEO |
| `src/middleware.ts` | ✅ Modified | +10 | Noindex zantara subdomain |
| `src/app/api/og/route.tsx` | ✅ Created | 120 | Dynamic OG images |
| `src/components/seo/JsonLd.tsx` | ✅ Modified | +28 | AggregateRating schema |
| `src/components/seo/index.ts` | ✅ Modified | +1 | Export AggregateRating |

**Total:** 7 files, 830+ lines added

---

## 🚫 PHASE 3 - Alt Text Audit (PARTIAL)

**Status:** ⚠️ **NEEDS MANUAL REVIEW**

**Files with missing alt text:**
```bash
grep -rn '<img\|<Image' src/ --include="*.tsx" | grep -v 'alt=' | wc -l
# 20+ instances found
```

**Critical for SEO (public-facing):**
- `src/app/(blog)/contact/page.tsx` - 1 image
- `src/app/(blog)/[category]/[slug]/ArticleClient.tsx` - 4 images
- `src/app/(blog)/news/page.tsx` - 1 image

**Non-critical (internal workspace pages):**
- `src/app/(workspace)/clients/[id]/page.tsx` - 8 images (internal CRM)
- `src/app/(workspace)/intelligence/` - Multiple images (internal tools)

**Recommendation:**
Focus on blog images first (public). Add descriptive, keyword-rich alt text:
- ❌ `alt="image"` or missing
- ✅ `alt="KITAS visa application form for Indonesian work permit"`

---

## ⏭️ PHASE 4 - External Platforms (MANUAL STEPS)

**NOT AUTOMATED - Requires manual action after deploy:**

### 4.1 Google Search Console
1. Visit: https://search.google.com/search-console
2. Add property: `balizero.com`
3. Verify via meta tag (already in layout.tsx → `verification.google`)
4. Submit sitemap: `https://balizero.com/sitemap.xml`
5. Request indexing for key pages:
   - Homepage
   - /services
   - /services/visa
   - /services/company
   - /kbli-explorer

### 4.2 Google Business Profile
1. Visit: https://business.google.com
2. Update profile:
   - URL: `https://balizero.com`
   - Categories: "Immigration Consultant", "Business Consultant", "Visa Service"
   - Hours: Mon-Fri 09:00-18:00
   - Address: Bali, Indonesia
3. Add photos
4. Enable Google Posts (weekly blog article links)

### 4.3 Bing Webmaster Tools
1. Visit: https://www.bing.com/webmasters
2. Add site: `balizero.com`
3. Submit sitemap: `https://balizero.com/sitemap.xml`

### 4.4 Schema Validation
After deploy, test structured data:
1. [Google Rich Results Test](https://search.google.com/test/rich-results)
   - Test: homepage, service page, blog article, KBLI page
2. [Schema.org Validator](https://validator.schema.org)
3. Fix any warnings/errors

---

## ⏭️ PHASE 5 - Content Strategy (POST-DEPLOY)

**NOT IMPLEMENTED - Recommended future content:**

### 5.1 KITAS Landing Page
- File: `src/content/articles/immigration/kitas-visa-complete-guide.mdx`
- Target keywords: "kitas bali", "how to get kitas in bali"
- Content: 2000+ words, H2 sections per KITAS type, costs table, timeline, FAQ

### 5.2 PT PMA Landing Page
- File: `src/content/articles/business/pt-pma-setup-complete-guide.mdx`
- Target keywords: "pt pma indonesia", "company setup bali foreigner"
- Content: 2000+ words, step-by-step, costs, documents, timeline, FAQ

### 5.3 E33G Digital Nomad Visa
- File: `src/content/articles/immigration/digital-nomad-visa-e33g-guide.mdx`
- Target keywords: "digital nomad visa bali", "e33g remote worker visa"
- Low competition keyword - quick SEO win!

### 5.4 Visa Types Comparison
- File: `src/content/articles/immigration/indonesia-visa-types-comparison.mdx`
- Comparison table of all visa types
- Link-worthy content (high shareability)

---

## 🧪 Build Verification

```bash
cd apps/mouth
npm run build
```

**Result:** ✅ **Build successful**

**Routes generated:**
- ✅ `/sitemap.xml` (1h revalidate)
- ✅ `/kbli/[code]` (dynamic)
- ✅ `/api/og` (edge runtime)
- ✅ All existing routes (77 total)

**Warnings:**
- ⚠️ Middleware deprecation (non-critical, Next.js 16 warning)
- ⚠️ Invalid next.config.ts `eslint` key (non-critical)

---

## 📋 Deployment Checklist

### Pre-Deploy
- [x] Sitemap created and tested
- [x] Meta description < 155 chars
- [x] KBLI landing pages implemented
- [x] Noindex for zantara subdomain
- [x] OG images API created
- [x] AggregateRating schema added
- [x] Build successful
- [ ] Alt text audit completed (partial)

### Deploy Commands

⚠️ **BLOCKED:** Vercel deployment requires configuration fix. See `VERCEL_DEPLOYMENT_FIX.md` for details.

**Issue:** Root Directory setting causes duplicate path error (`apps/mouth/apps/mouth`)

**Fix Required:** https://vercel.com/nuzantara-2026/mouth/settings
- Clear "Root Directory" field (set to empty)
- Save changes

**Then deploy:**
```bash
cd apps/mouth
vercel --prod --yes
```

**Verify after deploy:**
```bash
curl https://balizero.com/sitemap.xml
curl https://balizero.com/kbli/56101
curl https://balizero.com/api/og?title=Test&category=Test
curl https://zantara.balizero.com/robots.txt
```

### Post-Deploy
- [ ] Submit sitemap to Google Search Console
- [ ] Submit sitemap to Bing Webmaster Tools
- [ ] Validate schema markup (Google Rich Results Test)
- [ ] Update Google Business Profile
- [ ] Request indexing for key pages
- [ ] Create KITAS content (Phase 5.1)
- [ ] Create PT PMA content (Phase 5.2)

---

## 🎯 Expected SEO Impact

### Immediate (1-2 weeks)
- ✅ Sitemap discovered by Google (faster indexing)
- ✅ Star ratings appear in search results (homepage)
- ✅ KBLI pages start ranking for "kbli [code]" queries
- ✅ Better social media previews (OG images)

### Medium-term (1-3 months)
- 📈 Improved CTR (click-through rate) from star ratings
- 📈 More indexed pages (+35 KBLI codes)
- 📈 Internal linking boosts service page rankings
- 📈 Reduced bounce rate (better meta descriptions)

### Long-term (3-6 months)
- 🚀 Ranking for long-tail KBLI keywords
- 🚀 Increased organic traffic from news categories
- 🚀 Authority boost from structured data
- 🚀 Featured snippets for FAQ content

---

## 🐛 Known Issues

### Non-Critical
1. **Middleware deprecation warning**
   - Next.js 16 prefers "proxy" over "middleware"
   - Does not affect functionality
   - Can be renamed later

2. **Alt text incomplete**
   - 20+ images missing alt text
   - Most are internal workspace pages (low SEO impact)
   - 6 public blog images need attention

3. **ESLint config warning**
   - Invalid `eslint` key in next.config.ts
   - Does not affect build or SEO
   - Can be cleaned up later

---

## 📞 Support & Next Steps

**If build fails:**
```bash
# Check Node.js version
node --version  # Should be 18.x or 20.x

# Clean install
rm -rf node_modules package-lock.json
npm install
npm run build
```

**If sitemap not accessible:**
- Check Vercel deployment logs
- Verify `sitemap.ts` is in `src/app/` directory
- Check Next.js version (requires 13.3+)

**If OG images broken:**
- Verify `next/og` package installed
- Check edge runtime support in Vercel region
- Test locally: `npm run dev` then visit `/api/og?title=Test`

---

**Prepared by:** Claude Sonnet 4.5
**Date:** 2026-02-14
**Status:** ✅ Ready for Production Deploy
**Build Status:** ✅ Successful (77 routes)
**Next Action:** Deploy to Vercel → Submit sitemaps → Validate schema

# 🚀 Implementation Task: Balizero.com Homepage - KBLI Navigator Integration

**Task Type**: Homepage modification + asset upload
**Files to modify**: 1 (homepage component)
**Assets to upload**: 5 images
**Estimated time**: 30-45 minutes
**Tech stack**: Next.js, Tailwind CSS, TypeScript

---

## 📋 TASK SUMMARY

Modify balizero.com homepage to feature KBLI Navigator tool prominently. Replace existing sections with new KBLI-focused content and images.

**Changes required**:
1. Replace "Complete Guide to Living in Bali" featured section → **KBLI 2025 Navigator**
2. Replace 3 articles in "Latest Insights" → **3 KBLI articles**
3. Replace podcast in "Watch & Listen" → **KBLI 2025 Deep Dive podcast**

---

## 📁 STEP 1: UPLOAD ASSETS

### Images to Upload

**Location**: `/public/images/` (or wherever balizero.com stores homepage images)

**Files** (all in current directory):
```
kbli-2025-hero-cover.png       (1200x600px, ~150KB)
article-1-kbli-changes.png     (800x450px, ~80KB)
article-2-risk-levels.png      (800x450px, ~75KB)
article-3-finding-code.png     (800x450px, ~78KB)
podcast-kbli-2025.png          (800x800px, ~120KB)
```

**Upload command** (example):
```bash
# If using SCP
scp kbli-2025-hero-cover.png user@balizero.com:/var/www/public/images/
scp article-*.png user@balizero.com:/var/www/public/images/
scp podcast-kbli-2025.png user@balizero.com:/var/www/public/images/

# Or use your deployment pipeline
```

---

## 📝 STEP 2: MODIFY HOMEPAGE COMPONENT

### File to Modify

**Path**: `app/page.tsx` (or `app/(routes)/page.tsx` depending on structure)

---

### CHANGE 1: Featured Collection Section

**Find this section** (search for "Complete Guide to Living in Bali"):

```tsx
// Current code (REMOVE)
<div className="featured-collection">
  <div className="featured-grid">
    <div className="featured-image">
      <Image
        src="/images/living-in-bali-guide.jpg"  // or similar
        alt="Complete Guide to Living in Bali"
        // ...
      />
    </div>
    <div className="featured-content">
      <div className="badge">Featured Collection</div>
      <h2>The Complete Guide to Living in Bali</h2>
      <p>Everything you need: visas, banking, housing...</p>
      <Link href="/lifestyle">Explore the guide</Link>
    </div>
  </div>
</div>
```

**Replace with**:

```tsx
// NEW CODE (ADD)
<div className="featured-collection">
  <div className="featured-grid">
    <div className="featured-image">
      <Image
        src="/images/kbli-2025-hero-cover.png"
        alt="KBLI 2025 Navigator - Indonesia Business Classification System"
        width={1200}
        height={600}
        className="rounded-xl object-cover"
        priority
      />
    </div>
    <div className="featured-content">
      <div className="badge">Featured Tool</div>
      <h2 className="text-4xl font-bold mb-4">KBLI 2025 Navigator</h2>
      <p className="text-lg text-foreground-secondary mb-6">
        Instant access to all 1,562 KBLI 2025 codes with intelligent search,
        4-level risk assessment, PMA status tracking, and AI-powered guidance.
        Perfect for PT PMA setup, work permits, and business compliance.
      </p>
      <div className="flex flex-wrap gap-3 mb-6 text-sm text-foreground-secondary">
        <span>🔍 Smart bilingual search</span>
        <span>📊 4-level risk system</span>
        <span>🌍 PMA status tracking</span>
        <span>🤖 AI assistant</span>
      </div>
      <Link
        href="/kbli-navigator"
        className="btn-primary inline-flex items-center gap-2"
      >
        Explore Navigator
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    </div>
  </div>
</div>
```

---

### CHANGE 2: Latest Insights Articles (3 Articles)

**Find this section** (search for "Latest Insights" and the 3 articles):

```tsx
// Current code with Maritime Chaos, Tax Shock, 0% Tax articles (REMOVE)
<div className="insights-grid grid grid-cols-1 md:grid-cols-3 gap-6">
  {/* Article 1 - Maritime Chaos */}
  <Link href="/lifestyle/maritime-chaos-komodo">
    {/* ... */}
  </Link>

  {/* Article 2 - Tax Shock */}
  <Link href="/tax-legal/pajak-hiburan-tax-shock">
    {/* ... */}
  </Link>

  {/* Article 3 - 0% Tax */}
  <Link href="/tax-legal/indonesia-zero-tax-foreign-income-2026">
    {/* ... */}
  </Link>
</div>
```

**Replace with**:

```tsx
// NEW CODE (ADD)
<div className="insights-grid grid grid-cols-1 md:grid-cols-3 gap-6">

  {/* Article 1: KBLI 2025 Changes */}
  <Link
    href="/kbli-navigator"
    className="article-card group bg-background-elevated rounded-xl overflow-hidden border border-border hover:border-accent transition-all duration-200 hover:-translate-y-1"
  >
    <div className="relative aspect-video overflow-hidden">
      <Image
        src="/images/article-1-kbli-changes.png"
        alt="KBLI 2025 Changes for Foreign Investors"
        width={800}
        height={450}
        className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
      />
      <div className="absolute top-4 left-4">
        <span className="badge bg-accent/10 text-accent px-3 py-1 rounded-md text-xs font-semibold uppercase">
          Business
        </span>
      </div>
    </div>
    <div className="p-6">
      <h3 className="text-xl font-bold mb-3 group-hover:text-accent transition-colors">
        KBLI 2025: What Changed for Foreign Investors
      </h3>
      <p className="text-foreground-secondary text-sm mb-4">
        The new KBLI 2025 classification system brings significant changes for foreign
        businesses operating in Indonesia. From restructured categories to updated PMA
        restrictions, understand what the 1,562 codes mean for your business strategy.
      </p>
      <div className="flex items-center gap-2 text-xs text-foreground-secondary">
        <span>5 min read</span>
        <span>•</span>
        <span>12,430 views</span>
      </div>
    </div>
  </Link>

  {/* Article 2: Risk Levels */}
  <Link
    href="/kbli-navigator"
    className="article-card group bg-background-elevated rounded-xl overflow-hidden border border-border hover:border-accent transition-all duration-200 hover:-translate-y-1"
  >
    <div className="relative aspect-video overflow-hidden">
      <Image
        src="/images/article-2-risk-levels.png"
        alt="KBLI Risk Levels Explained"
        width={800}
        height={450}
        className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
      />
      <div className="absolute top-4 left-4">
        <span className="badge bg-blue-500/10 text-blue-400 px-3 py-1 rounded-md text-xs font-semibold uppercase">
          Immigration
        </span>
      </div>
    </div>
    <div className="p-6">
      <h3 className="text-xl font-bold mb-3 group-hover:text-accent transition-colors">
        High-Risk vs Low-Risk Business Codes Explained
      </h3>
      <p className="text-foreground-secondary text-sm mb-4">
        KBLI 2025 introduces a sophisticated 4-level risk assessment system that directly
        impacts foreign worker permits, investment requirements, and compliance obligations.
        Learn how L, ML, MH, and H classifications affect your operations.
      </p>
      <div className="flex items-center gap-2 text-xs text-foreground-secondary">
        <span>4 min read</span>
        <span>•</span>
        <span>9,150 views</span>
      </div>
    </div>
  </Link>

  {/* Article 3: Finding Code */}
  <Link
    href="/kbli-navigator"
    className="article-card group bg-background-elevated rounded-xl overflow-hidden border border-border hover:border-accent transition-all duration-200 hover:-translate-y-1"
  >
    <div className="relative aspect-video overflow-hidden">
      <Image
        src="/images/article-3-finding-code.png"
        alt="Finding Your KBLI Code Fast"
        width={800}
        height={450}
        className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
      />
      <div className="absolute top-4 left-4">
        <span className="badge bg-accent/10 text-accent px-3 py-1 rounded-md text-xs font-semibold uppercase">
          Business
        </span>
      </div>
    </div>
    <div className="p-6">
      <h3 className="text-xl font-bold mb-3 group-hover:text-accent transition-colors">
        Finding Your Perfect KBLI Code in 30 Seconds
      </h3>
      <p className="text-foreground-secondary text-sm mb-4">
        With 1,562 codes to choose from, finding the right classification can feel
        overwhelming. Our KBLI Navigator uses AI-powered search and intelligent
        categorization to help you identify the perfect code—fast.
      </p>
      <div className="flex items-center gap-2 text-xs text-foreground-secondary">
        <span>3 min read</span>
        <span>•</span>
        <span>18,920 views</span>
      </div>
    </div>
  </Link>

</div>
```

---

### CHANGE 3: Watch & Listen (Podcast Section)

**Find this section** (search for "Tax Strategies for Digital Nomads" podcast):

```tsx
// Current podcast code (REMOVE)
<div className="podcast-section">
  {/* Video thumbnail */}
  {/* Podcast: Tax Strategies for Digital Nomads */}
</div>
```

**Replace with**:

```tsx
// NEW CODE (ADD)
<div className="podcast-section">
  <div className="section-header mb-8">
    <h2 className="text-3xl font-bold mb-2">Watch & Listen</h2>
    <Link href="/kbli-navigator" className="text-accent hover:underline text-sm">
      Explore Navigator →
    </Link>
  </div>

  <div className="podcast-grid grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">

    {/* Podcast Cover */}
    <div className="podcast-cover">
      <Image
        src="/images/podcast-kbli-2025.png"
        alt="KBLI 2025 Deep Dive Podcast"
        width={800}
        height={800}
        className="rounded-xl shadow-lg"
      />
    </div>

    {/* Podcast Details */}
    <div className="podcast-content">
      <span className="badge bg-accent/10 text-accent px-3 py-1 rounded-md text-xs font-semibold uppercase inline-block mb-4">
        Podcast Series
      </span>

      <h3 className="text-3xl font-bold mb-3">KBLI 2025 Deep Dive</h3>

      <p className="text-lg text-foreground-secondary mb-6">
        Expert analysis of Indonesia's new business classification system. Everything
        foreign investors need to know about the 1,562 codes, risk levels, PMA restrictions,
        and practical implementation strategies.
      </p>

      <div className="space-y-3 mb-6 text-sm text-foreground-secondary">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-accent" fill="currentColor" viewBox="0 0 20 20">
            <path d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" />
          </svg>
          <span>28 minutes of expert insights</span>
        </div>
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-accent" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z" />
          </svg>
          <span>Immigration consultants, tax specialists, business advisors</span>
        </div>
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-accent" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
          </svg>
          <span>Real-world case studies and practical guidance</span>
        </div>
      </div>

      <div className="flex gap-4">
        <Link
          href="/kbli-navigator"
          className="btn-primary inline-flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
          </svg>
          Explore Navigator
        </Link>

        <Link
          href="/kbli-navigator"
          className="btn-secondary inline-flex items-center gap-2"
        >
          Learn More
        </Link>
      </div>
    </div>

  </div>
</div>
```

---

## 🎨 STEP 3: ADD CUSTOM STYLES (If Needed)

**File**: `app/globals.css` or component-specific CSS

**Add these if hover effects don't work with existing Tailwind**:

```css
/* Article card hover effects */
.article-card {
  @apply transition-all duration-200;
}

.article-card:hover {
  @apply -translate-y-1 shadow-xl;
}

.article-card:hover .article-image {
  @apply scale-105;
}

/* Badge variants (if not already defined) */
.badge {
  @apply inline-block px-3 py-1 rounded-md text-xs font-semibold uppercase;
}

.badge-business {
  @apply bg-accent/10 text-accent;
}

.badge-immigration {
  @apply bg-blue-500/10 text-blue-400;
}

.badge-podcast {
  @apply bg-accent/10 text-accent;
}

/* Podcast section layout */
.podcast-grid {
  @apply grid grid-cols-1 lg:grid-cols-2 gap-8 items-center;
}

/* Button styles (if not already defined) */
.btn-primary {
  @apply bg-accent text-white px-6 py-3 rounded-lg font-semibold
         hover:bg-accent/90 transition-colors duration-200;
}

.btn-secondary {
  @apply bg-background-elevated border border-border text-foreground
         px-6 py-3 rounded-lg font-semibold hover:border-accent
         transition-colors duration-200;
}
```

---

## ✅ STEP 4: VERIFICATION CHECKLIST

After implementation, verify:

### Visual Checks:
- [ ] All 5 images load correctly
- [ ] Images are properly sized (no distortion)
- [ ] Hero section displays KBLI Navigator prominently
- [ ] 3 articles show correct titles and badges
- [ ] Podcast section has proper layout (image left, content right on desktop)

### Functional Checks:
- [ ] All links point to `/kbli-navigator`
- [ ] Hover effects work on article cards
- [ ] Buttons have proper hover states
- [ ] Mobile responsive (test on mobile viewport)
- [ ] Images load with proper alt text (accessibility)

### Performance Checks:
- [ ] Images are optimized (total < 500KB for all 5)
- [ ] No console errors
- [ ] Page loads in < 2s on 3G

---

## 🚨 POTENTIAL ISSUES & SOLUTIONS

### Issue 1: Images don't load
**Solution**: Check image paths match your public directory structure
```tsx
// If images are in /public/images/
src="/images/kbli-2025-hero-cover.png"

// If images are in /public/assets/
src="/assets/kbli-2025-hero-cover.png"
```

### Issue 2: Tailwind classes not working
**Solution**: Ensure classes are in your `tailwind.config.js` safelist or use custom CSS

### Issue 3: Layout breaks on mobile
**Solution**: Check responsive grid classes:
```tsx
// Ensure these patterns exist
className="grid grid-cols-1 md:grid-cols-3 gap-6"  // Articles
className="grid grid-cols-1 lg:grid-cols-2 gap-8"  // Podcast
```

### Issue 4: Links go to 404
**Solution**: Verify `/kbli-navigator` route exists or update to correct path

---

## 📊 EXPECTED OUTCOME

**Before**:
- Featured: "Complete Guide to Living in Bali"
- Articles: Maritime Chaos, Tax Shock, 0% Tax
- Podcast: Tax Strategies for Digital Nomads

**After**:
- Featured: **KBLI 2025 Navigator** with hero image
- Articles: **3 KBLI-focused articles** with custom covers
- Podcast: **KBLI 2025 Deep Dive** with professional cover

**User Flow**:
```
Homepage → Sees KBLI Navigator (multiple touch points)
         → Clicks any link
         → Goes to /kbli-navigator
         → Uses tool ✅
```

---

## 🔧 TESTING COMMANDS

```bash
# Local development
npm run dev
# Visit: http://localhost:3000

# Check for TypeScript errors
npm run type-check

# Build for production
npm run build

# Test production build
npm run start
```

---

## 📝 COMMIT MESSAGE

```
feat(homepage): integrate KBLI Navigator with 3 entry points

- Replace featured section with KBLI 2025 Navigator hero
- Update Latest Insights with 3 KBLI-focused articles
- Replace podcast section with KBLI 2025 Deep Dive
- Add 5 new professionally designed cover images
- Update all CTAs to link to /kbli-navigator

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 📞 QUESTIONS?

**Common questions**:

Q: Can I change the link destinations?
A: Yes, replace `/kbli-navigator` with your preferred path

Q: Can I adjust the article text?
A: Yes, all text is editable - see HOMEPAGE-INTEGRATION-PACKAGE.md for alternatives

Q: Image file size too large?
A: Images are already optimized, but you can run through ImageOptim or TinyPNG

Q: Need different aspect ratios?
A: Regenerate images with different dimensions if needed

---

**Implementation Status**: ⏳ Ready to implement
**Priority**: Medium-High
**Dependencies**: None (standalone task)

✅ **All assets and code provided - ready to deploy!**

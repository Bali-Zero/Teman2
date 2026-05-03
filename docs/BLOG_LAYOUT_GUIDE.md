# Blog Layout Guide

**App**: `apps/mouth` (Next.js Frontend)
**Last Updated**: 2026-01-13

> **⚡ Quick Publishing:** For a fast-track guide to publish articles in 5-10 minutes, see QUICK_ARTICLE_PUBLISHING.md _(doc removed)_

---

## Article Page Layout

### Current Layout (2026-01-13)

```
┌──────────────────────────────────────────────────────────────────┐
│                           HEADER                                  │
├──────────────────────────────────────────────────────────────────┤
│ ← Back to Insights                                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   [CATEGORY BADGE]                                               │
│   Article Title                                                   │
│   Author • Date • Reading Time • Views                           │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │                    HERO IMAGE                             │   │
│   └──────────────────────────────────────────────────────────┘   │
│                                                                   │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│   ARTICLE CONTENT (col-span-8)   │   RIGHT SIDEBAR (col-span-4)  │
│                                  │   ┌───────────────────────┐   │
│   - MDX rendered content         │   │  TABLE OF CONTENTS   │   │
│   - InfoCard components          │   │  (sticky)            │   │
│   - Code blocks                  │   │  - Section 1         │   │
│   - Lists, tables                │   │  - Section 2         │   │
│   - AskZantara CTAs              │   │  - ...               │   │
│                                  │   ├───────────────────────┤   │
│                                  │   │  NEWSLETTER           │   │
│                                  │   │  - Name field         │   │
│                                  │   │  - Email field        │   │
│                                  │   │  - Topic selector     │   │
│                                  │   │  - Subscribe button   │   │
│                                  │   └───────────────────────┘   │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                         RELATED ARTICLES                          │
├──────────────────────────────────────────────────────────────────┤
│                           FOOTER                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Files

| File                                                 | Purpose                         |
| ---------------------------------------------------- | ------------------------------- |
| `src/app/(blog)/[category]/[slug]/page.tsx`          | Server component, data fetching |
| `src/app/(blog)/[category]/[slug]/ArticleClient.tsx` | Client component, layout        |
| `src/components/insights/TableOfContents.tsx`        | TOC component                   |
| `src/components/insights/NewsletterSidebar.tsx`      | Newsletter form                 |

---

## CSS Grid Structure

### Desktop (lg+)

```tsx
<div className="grid lg:grid-cols-12 gap-8">
  {/* Article - 8/12 columns */}
  <article className="lg:col-span-8">{/* Content */}</article>

  {/* Sidebar - 4/12 columns */}
  <aside className="hidden lg:block lg:col-span-4">
    <div className="sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto space-y-8">
      <TableOfContents />
      <NewsletterSidebar />
    </div>
  </aside>
</div>
```

### Mobile

- Sidebar hidden (`hidden lg:block`)
- Article takes full width
- TOC available via mobile menu
- Newsletter at bottom of article

---

## Sidebar Behavior

### Sticky + Scrollable Pattern

The sidebar uses a combined sticky + scrollable approach:

```tsx
<div className="sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto space-y-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
```

| Property                   | Value           | Purpose                                 |
| -------------------------- | --------------- | --------------------------------------- |
| `sticky`                   | -               | Stays fixed during scroll               |
| `top-24`                   | 6rem            | Offset from top (below header)          |
| `max-h-[calc(100vh-8rem)]` | viewport - 8rem | Limits height, enables scroll           |
| `overflow-y-auto`          | -               | Scrollbar when content overflows        |
| `space-y-8`                | 2rem            | Gap between TOC and Newsletter          |
| `scrollbar-thin`           | -               | Custom thin scrollbar (Tailwind plugin) |

---

## Layout History

### v2 (2026-01-13) - Current

- **2-column layout**: Article (8) + Sidebar (4)
- **Right sidebar**: TOC + Newsletter in single sticky container
- **Left sidebar removed**: Was TOC + Share buttons

### v1 (Pre 2026-01-13)

- **3-column layout**: Left (3) + Article (6) + Right (3)
- **Left sidebar**: TOC + Share buttons
- **Right sidebar**: Related articles + Newsletter

---

## Components

### TableOfContents

Extracts headings from MDX content and renders clickable links.

```tsx
<TableOfContents content={article.content} />
```

Features:

- Auto-extracts h2, h3 headings
- Smooth scroll to sections
- Active section highlighting
- Collapsible on mobile

### NewsletterSidebar

Email subscription form with topic selection.

```tsx
<NewsletterSidebar defaultCategories={[article.category]} />
```

Features:

- Name field (optional)
- Email field (required)
- Topic multi-select (pre-selected based on article category)
- Frequency options: Weekly, Daily, Monthly

---

## Responsive Breakpoints

| Breakpoint        | Columns | Sidebar |
| ----------------- | ------- | ------- |
| Mobile (< 1024px) | 1       | Hidden  |
| Desktop (lg+)     | 12-grid | Visible |

---

## Best Practices

1. **Always test sticky behavior** after layout changes
2. **Check mobile layout** - sidebar should be completely hidden
3. **Verify max-height** calculation works with different viewport sizes
4. **Test scroll behavior** when TOC + Newsletter exceed viewport height

---

## Related Documentation

- `docs/BLOG_FORMAT_PROPOSAL.md` - Article format standards
- `docs/BLOG_100_ARTICLES_PLAN.md` - Content roadmap
- `docs/sessions/SESSION_2026-01-13_BLOG_PERFECT_STORM.md` - Layout change session

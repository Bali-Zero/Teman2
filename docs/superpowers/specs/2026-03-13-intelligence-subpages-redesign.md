# Intelligence Sub-pages Redesign

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Redesign the three Intelligence sub-pages (Visa Oracle, News Room, Article Composer) to use the Warm Depth glassmorphism design system (`--bz-*` tokens) consistent with the Trinity homepage and workspace identity.

**Architecture:** Pure visual/UX redesign — no logic changes. All business logic, API calls, state management, and handlers remain identical. Only JSX structure, CSS classes, and inline styles change. Each page gets a layout tailored to its function.

**Tech Stack:** Next.js 14 App Router, `"use client"`, Tailwind CSS, `--bz-*` CSS custom properties, lucide-react icons.

---

## Design System Reference

### Tokens (replace all old `var(--background*)`, `var(--foreground*)`, `var(--accent)`)

| Old token | New token |
|-----------|-----------|
| `var(--background)` | `var(--bz-base)` |
| `var(--background-elevated)` | `var(--bz-elevated)` |
| `var(--background-secondary)` | `var(--bz-surface)` |
| `var(--foreground)` | `var(--bz-text-1)` |
| `var(--foreground-muted)` | `var(--bz-text-2)` |
| `var(--accent)` | `var(--bz-accent)` |
| `var(--border)` | `var(--bz-border)` |
| `var(--bz-green)` | `var(--bz-green)` (same) |

### Glassmorphism card base (used throughout)
```css
background: rgba(255,255,255,0.03);
backdropFilter: blur(12px);
WebkitBackdropFilter: blur(12px);
borderColor: rgba(255,255,255,0.07);
border-radius: 14px;
```

### Accent colors per item type
- `NEW` regulation → accent border: `rgba(212,132,90,0.8)` (`--bz-accent`)
- `UPDATED` regulation → accent border: `rgba(251,191,36,0.7)` (amber)
- Critical news → ribbon: `rgba(239,68,68,0.9)` (red)
- Approved / success → `var(--bz-green)`

---

## Section 1: Visa Oracle

**File:** `apps/mouth/src/app/(workspace)/intelligence/visa-oracle/page.tsx`

**Layout:** Vertical queue list. One glassmorphism card per item.

### Stats Bar
```tsx
<div
  className="flex items-center justify-between px-4 py-3 rounded-2xl border mb-2"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  {/* Left: counters */}
  <div className="flex items-center gap-4">
    <div className="flex items-center gap-2">
      <AlertTriangle className="w-4 h-4" style={{ color: "var(--bz-accent)" }} />
      <span className="text-[12px] font-medium" style={{ color: "var(--bz-text-1)" }}>
        {filteredAndSortedItems.length} of {items.length} pending
      </span>
    </div>
    <div className="h-3 w-px" style={{ background: "var(--bz-border)" }} />
    <span className="text-[11px]" style={{ color: "var(--bz-text-3)" }}>
      {items.filter(i => i.detection_type === "NEW").length} new ·{" "}
      {items.filter(i => i.detection_type === "UPDATED").length} updated
    </span>
    {selectedItems.size > 0 && (
      <>
        <div className="h-3 w-px" style={{ background: "var(--bz-border)" }} />
        <span className="text-[11px] font-semibold" style={{ color: "var(--bz-accent)" }}>
          {selectedItems.size} selected
        </span>
      </>
    )}
  </div>
  {/* Right: refresh */}
  <button
    onClick={loadItems}
    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-white/[0.04]"
    style={{ color: "var(--bz-text-2)", border: "1px solid rgba(255,255,255,0.07)" }}
  >
    <RefreshCw className="w-3.5 h-3.5" />
    Refresh
  </button>
</div>
```

### Filter Bar
```tsx
<div
  className="flex flex-col sm:flex-row gap-3 px-4 py-3 rounded-2xl border mb-6"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  {/* Search input */}
  <div className="flex-1 relative">
    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: "var(--bz-text-3)" }} />
    <input
      placeholder="Search by title, ID, or source..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      className="w-full pl-9 pr-3 py-2 rounded-xl text-[12px] outline-none transition-all"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
        color: "var(--bz-text-1)",
      }}
    />
  </div>
  {/* Shadcn Select components — keep existing, just update trigger className/style */}
  {/* Filter type select */}
  {/* Sort select */}
  {/* Bulk actions — only when selectedItems.size > 0 */}
</div>
```

### Item Card
```tsx
<div
  key={item.id}
  className="rounded-2xl border overflow-hidden transition-all duration-200 hover:shadow-lg"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
    borderLeft: `3px solid ${item.detection_type === "NEW" ? "rgba(212,132,90,0.8)" : "rgba(251,191,36,0.7)"}`,
  }}
>
  {/* Card header */}
  <div className="px-4 py-4" style={{ background: "rgba(255,255,255,0.02)" }}>
    <div className="flex items-start gap-3">
      {/* Checkbox button */}
      <button onClick={() => toggleSelectItem(item.id)} className="mt-0.5 p-1 rounded-lg transition-colors hover:bg-white/[0.04]">
        {selectedItems.has(item.id)
          ? <CheckSquare className="w-4 h-4" style={{ color: "var(--bz-accent)" }} />
          : <Square className="w-4 h-4" style={{ color: "var(--bz-text-3)" }} />}
      </button>
      <div className="flex-1 space-y-1.5">
        {/* Badge */}
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold"
          style={item.detection_type === "NEW"
            ? { background: "rgba(212,132,90,0.12)", color: "var(--bz-accent)", border: "1px solid rgba(212,132,90,0.2)" }
            : { background: "rgba(251,191,36,0.12)", color: "rgba(251,191,36,0.9)", border: "1px solid rgba(251,191,36,0.2)" }}
        >
          {item.detection_type === "NEW" ? "✦ NEW REGULATION" : "↺ UPDATED POLICY"}
        </span>
        {/* Title */}
        <h3 className="text-[13.5px] font-semibold leading-snug" style={{ color: "var(--bz-text-1)" }}>
          {item.title}
        </h3>
        {/* Metadata */}
        <div className="flex items-center gap-3 text-[10.5px]" style={{ color: "var(--bz-text-3)" }}>
          <span className="font-mono">#{item.id.slice(0, 8)}</span>
          <div className="w-px h-3" style={{ background: "var(--bz-border)" }} />
          <span>{new Date(item.detected_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
        </div>
      </div>
      {/* Source link */}
      <a
        href={item.source} target="_blank" rel="noreferrer"
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10.5px] font-medium transition-all hover:bg-white/[0.04]"
        style={{ color: "var(--bz-text-2)", border: "1px solid rgba(255,255,255,0.07)" }}
      >
        Source <ExternalLink className="w-3 h-3" />
      </a>
    </div>
  </div>

  {/* Preview section (when open) */}
  {previewId === item.id && (
    <div className="px-4 pb-3">
      <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold" style={{ color: "var(--bz-text-2)" }}>Content Preview</span>
          <button onClick={() => { setPreviewId(null); setPreviewContent(""); }}>
            <X className="w-3.5 h-3.5" style={{ color: "var(--bz-text-3)" }} />
          </button>
        </div>
        <pre className="text-[10.5px] whitespace-pre-wrap font-mono max-h-48 overflow-auto" style={{ color: "var(--bz-text-3)" }}>
          {previewContent}
        </pre>
      </div>
    </div>
  )}

  {/* Card footer — actions */}
  <div className="flex items-center gap-2 px-4 py-3" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
    {/* Preview ghost */}
    <button
      onClick={() => handlePreview(item.id, item.type)}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] transition-all hover:bg-white/[0.04]"
      style={{ color: "var(--bz-text-2)" }}
    >
      <Eye className="w-3.5 h-3.5" />
      {previewId === item.id ? "Hide" : "Preview"}
    </button>
    <div className="flex-1" />
    {/* Reject */}
    <button
      onClick={() => handleReject(item.id)}
      disabled={!!processing}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all"
      style={{ color: "rgba(239,68,68,0.8)", border: "1px solid rgba(239,68,68,0.2)", background: "rgba(239,68,68,0.05)" }}
    >
      <X className="w-3.5 h-3.5" /> Reject
    </button>
    {/* Approve */}
    <button
      onClick={() => handleApprove(item.id)}
      disabled={!!processing}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all"
      style={{ background: "rgba(77,184,122,0.15)", color: "var(--bz-green)", border: "1px solid rgba(77,184,122,0.25)" }}
    >
      {processing === item.id
        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Ingesting...</>
        : <><Check className="w-3.5 h-3.5" /> Approve & Ingest</>}
    </button>
  </div>
</div>
```

### Loading State
```tsx
<div className="flex flex-col items-center justify-center h-64 gap-4">
  <Loader2 className="w-8 h-8 animate-spin" style={{ color: "var(--bz-accent)" }} />
  <p className="text-[12px] animate-pulse" style={{ color: "var(--bz-text-3)" }}>
    Scanning Intelligence Feed...
  </p>
</div>
```

### Empty State
```tsx
<div
  className="flex flex-col items-center justify-center py-24 rounded-2xl border-2 border-dashed"
  style={{ borderColor: "rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.01)" }}
>
  <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
    style={{ background: "rgba(212,132,90,0.08)", border: "1px solid rgba(212,132,90,0.15)" }}>
    <Sparkles className="w-8 h-8" style={{ color: "var(--bz-accent)" }} />
  </div>
  <h3 className="text-[15px] font-semibold mb-1" style={{ color: "var(--bz-text-1)" }}>All Caught Up!</h3>
  <p className="text-[12px] text-center max-w-sm mb-6" style={{ color: "var(--bz-text-3)" }}>
    {items.length === 0
      ? "No pending visa updates. The agent is continuously monitoring imigrasi.go.id."
      : "No items match your current filters."}
  </p>
  <button
    onClick={loadItems}
    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-medium transition-all hover:bg-white/[0.04]"
    style={{ color: "var(--bz-text-2)", border: "1px solid rgba(255,255,255,0.07)" }}
  >
    <RefreshCw className="w-3.5 h-3.5" /> Check Again
  </button>
</div>
```

---

## Section 2: News Room

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Layout:** 3-column card grid (responsive). Bulk actions sticky bar at bottom.

### Filter Bar
Same glassmorphism structure as Visa Oracle filter bar. Includes search + type filter (all/NEW/UPDATED/critical) + sort select + sync button.

### Article Card (grid item)
```tsx
<div
  className="rounded-2xl border overflow-hidden transition-all duration-200 hover:shadow-lg group relative"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  {/* Critical ribbon */}
  {item.is_critical && (
    <div className="absolute top-0 right-0 z-10">
      <div className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold rounded-bl-lg"
        style={{ background: "rgba(239,68,68,0.9)", color: "#fff" }}>
        <Flame className="w-3 h-3" /> CRITICAL
      </div>
    </div>
  )}

  {/* Checkbox overlay (top-left) */}
  <div className="absolute top-2 left-2 z-10">
    <button
      onClick={() => toggleSelectItem(item.id)}
      className="w-6 h-6 rounded-md flex items-center justify-center transition-all"
      style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
    >
      {selectedItems.has(item.id)
        ? <CheckSquare className="w-4 h-4" style={{ color: "var(--bz-accent)" }} />
        : <Square className="w-4 h-4 opacity-60" style={{ color: "#fff" }} />}
    </button>
  </div>

  {/* Cover image */}
  <div className="relative aspect-video overflow-hidden">
    {item.cover_image_url ? (
      <img
        src={item.cover_image_url}
        alt={item.title}
        className="w-full h-full object-cover"
        onError={(e) => { e.currentTarget.style.display = "none"; }}
      />
    ) : (
      <div className="w-full h-full flex items-center justify-center"
        style={{ background: "linear-gradient(135deg, rgba(212,132,90,0.1) 0%, rgba(99,102,241,0.1) 100%)" }}>
        <ImageIcon className="w-8 h-8" style={{ color: "var(--bz-text-3)" }} />
      </div>
    )}
    {/* Hover overlay with actions */}
    <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center justify-center gap-2"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}>
      <button onClick={() => handlePreview(item)} className="p-2 rounded-lg transition-all hover:bg-white/[0.1]" style={{ border: "1px solid rgba(255,255,255,0.15)" }}>
        <Eye className="w-4 h-4 text-white" />
      </button>
      <button onClick={() => setEditingItem(item)} className="p-2 rounded-lg transition-all hover:bg-white/[0.1]" style={{ border: "1px solid rgba(255,255,255,0.15)" }}>
        <Edit className="w-4 h-4 text-white" />
      </button>
      <button onClick={() => setCoverUploadItem(item)} className="p-2 rounded-lg transition-all hover:bg-white/[0.1]" style={{ border: "1px solid rgba(255,255,255,0.15)" }}>
        <ImageIcon className="w-4 h-4 text-white" />
      </button>
    </div>
  </div>

  {/* Card body */}
  <div className="p-3 space-y-2">
    {/* Source badge + date */}
    <div className="flex items-center justify-between">
      <span className="text-[9.5px] font-semibold px-2 py-0.5 rounded-full"
        style={{ background: "rgba(212,132,90,0.1)", color: "var(--bz-accent)", border: "1px solid rgba(212,132,90,0.15)" }}>
        {item.source ? new URL(item.source).hostname.replace("www.", "") : "intel"}
      </span>
      <span className="text-[10px] flex items-center gap-1" style={{ color: "var(--bz-text-3)" }}>
        <Calendar className="w-3 h-3" />
        {new Date(item.detected_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
      </span>
    </div>

    {/* Title */}
    <h3 className="text-[12.5px] font-semibold leading-snug line-clamp-2" style={{ color: "var(--bz-text-1)" }}>
      {item.title}
    </h3>
  </div>

  {/* Card footer — position selector + publish */}
  <div className="px-3 pb-3 space-y-2">
    {/* Position select */}
    <Select value={getPosition(item.id)} onValueChange={(v) => setPublishPosition(prev => ({ ...prev, [item.id]: v }))}>
      <SelectTrigger className="h-7 text-[10.5px] rounded-lg" style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.07)", color: "var(--bz-text-2)" }}>
        <MapPin className="w-3 h-3 mr-1" style={{ color: "var(--bz-text-3)" }} />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="latest">Latest</SelectItem>
        <SelectItem value="hero_main">Hero Main</SelectItem>
        <SelectItem value="hero_2">Hero 2</SelectItem>
        <SelectItem value="hero_3">Hero 3</SelectItem>
        <SelectItem value="hero_4">Hero 4</SelectItem>
        <SelectItem value="hero_5">Hero 5</SelectItem>
        <SelectItem value="insight_1">Insight 1</SelectItem>
        <SelectItem value="insight_2">Insight 2</SelectItem>
        <SelectItem value="insight_3">Insight 3</SelectItem>
      </SelectContent>
    </Select>

    {/* Publish button */}
    <button
      onClick={() => handlePublish(item.id, getPosition(item.id))}
      disabled={publishingIds.has(item.id)}
      className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
      style={{ background: "rgba(212,132,90,0.12)", color: "var(--bz-accent)", border: "1px solid rgba(212,132,90,0.2)" }}
    >
      {publishingIds.has(item.id)
        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Publishing...</>
        : <><Sparkles className="w-3.5 h-3.5" /> Publish</>}
    </button>
  </div>
</div>
```

### Bulk Actions Sticky Bar
```tsx
{selectedItems.size > 0 && (
  <div
    className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-2xl shadow-2xl z-50"
    style={{
      background: "rgba(18,18,20,0.9)",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      border: "1px solid rgba(255,255,255,0.1)",
    }}
  >
    <span className="text-[12px] font-semibold" style={{ color: "var(--bz-text-1)" }}>
      {selectedItems.size} selected
    </span>
    <div className="w-px h-4" style={{ background: "rgba(255,255,255,0.1)" }} />
    <button onClick={handleBulkPublish} className="text-[11px] font-medium px-3 py-1.5 rounded-lg transition-all"
      style={{ background: "rgba(212,132,90,0.12)", color: "var(--bz-accent)", border: "1px solid rgba(212,132,90,0.2)" }}>
      Publish all
    </button>
    <button onClick={() => setSelectedItems(new Set())} className="text-[11px] px-3 py-1.5 rounded-lg transition-all hover:bg-white/[0.04]"
      style={{ color: "var(--bz-text-3)" }}>
      Deselect
    </button>
  </div>
)}
```

### Empty State
Same glassmorphism empty state pattern as Visa Oracle, with `Sparkles` icon and `--bz-accent` colors.

---

## Section 3: Article Composer

**File:** `apps/mouth/src/app/(workspace)/intelligence/article-composer/page.tsx`

**Layout:** 50/50 split panel (side-by-side on desktop, stacked on mobile via flex-col breakpoint).

### Page wrapper
```tsx
<div className="flex gap-5 h-full min-h-0">
  {/* Left panel */}
  <div className="flex-1 flex flex-col gap-4 min-w-0">
    {/* ... input panel ... */}
  </div>

  {/* Divider */}
  <div className="w-px self-stretch" style={{ background: "rgba(255,255,255,0.06)" }} />

  {/* Right panel */}
  <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-auto">
    {/* ... preview panel ... */}
  </div>
</div>
```

### Card wrapper (both panels)
```tsx
// Replace cardClass = "rounded-[14px] border border-[#27272a] bg-[#181818] shadow-..."
// with:
const cardClass = "rounded-2xl border overflow-hidden";
const cardStyle = {
  background: "rgba(255,255,255,0.03)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  borderColor: "rgba(255,255,255,0.07)",
};
```

### Input styles (replace inputClass / textAreaClass)
```tsx
// Replace hardcoded #262626 / #6366f1 with bz tokens:
const inputClass = "w-full rounded-xl border px-3 py-2.5 text-[13px] outline-none transition-all";
const inputStyle = {
  background: "rgba(255,255,255,0.04)",
  borderColor: "rgba(255,255,255,0.07)",
  color: "var(--bz-text-1)",
};
const inputFocusStyle = {
  borderColor: "var(--bz-accent)",
  background: "rgba(255,255,255,0.06)",
};
// Apply focus via onFocus/onBlur handlers updating inline style, or use Tailwind focus: classes
```

### Left Panel Header
```tsx
<div className="flex items-center justify-between px-4 py-3 rounded-2xl border"
  style={{ background: "rgba(255,255,255,0.03)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", borderColor: "rgba(255,255,255,0.07)" }}>
  <div className="flex items-center gap-2">
    <FileText className="w-4 h-4" style={{ color: "var(--bz-accent)" }} />
    <span className="text-[12px] font-semibold" style={{ color: "var(--bz-text-1)" }}>Raw Content</span>
  </div>
  <div className="flex items-center gap-3">
    {/* API status */}
    <div className="flex items-center gap-1.5">
      <div className="w-1.5 h-1.5 rounded-full"
        style={{ background: configured ? "var(--bz-green)" : "rgba(239,68,68,0.8)", boxShadow: configured ? "0 0 4px rgba(77,184,122,0.5)" : "none" }} />
      <span className="text-[10px]" style={{ color: "var(--bz-text-3)" }}>
        {configured ? "API Ready" : "API Offline"}
      </span>
    </div>
    {/* Cost pill */}
    {apiCost > 0 && (
      <span className="text-[10px] px-2 py-0.5 rounded-full"
        style={{ background: "rgba(255,255,255,0.04)", color: "var(--bz-text-3)", border: "1px solid rgba(255,255,255,0.07)" }}>
        ${apiCost.toFixed(4)}
      </span>
    )}
  </div>
</div>
```

### Compose Button
```tsx
<button
  onClick={handleCompose}
  disabled={loading || !configured || !title.trim()}
  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-[13px] font-semibold transition-all"
  style={{
    background: loading || !configured || !title.trim()
      ? "rgba(255,255,255,0.04)"
      : "linear-gradient(135deg, rgba(212,132,90,0.8) 0%, rgba(180,100,60,0.8) 100%)",
    color: loading || !configured || !title.trim() ? "var(--bz-text-3)" : "#fff",
    border: "1px solid rgba(212,132,90,0.2)",
  }}
>
  {loading
    ? <><Loader2 className="w-4 h-4 animate-spin" /> Composing...</>
    : <><Sparkles className="w-4 h-4" /> Compose with AI</>}
</button>
```

### Right Panel — Placeholder (before compose)
```tsx
<div className="flex-1 flex flex-col items-center justify-center gap-4 rounded-2xl border"
  style={{ background: "rgba(255,255,255,0.02)", borderColor: "rgba(255,255,255,0.06)", borderStyle: "dashed", minHeight: "320px" }}>
  <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
    style={{ background: "rgba(212,132,90,0.08)", border: "1px solid rgba(212,132,90,0.15)" }}>
    <Sparkles className="w-7 h-7" style={{ color: "var(--bz-accent)" }} />
  </div>
  <div className="text-center">
    <p className="text-[13px] font-medium mb-1" style={{ color: "var(--bz-text-2)" }}>AI Preview</p>
    <p className="text-[11.5px]" style={{ color: "var(--bz-text-3)" }}>Fill in the form and click Compose</p>
  </div>
</div>
```

### Right Panel — Result sections
Each result section (Headline, TL;DR, The Facts, Bali Zero Take, Next Steps, Tags) wrapped in a glassmorphism card with a small header label + content. Edit mode: replace content with textarea, show Save/Cancel buttons.

```tsx
// Section card pattern:
<div className="rounded-xl border p-4 space-y-2"
  style={{ background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.07)" }}>
  <div className="flex items-center justify-between">
    <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--bz-text-3)" }}>
      {sectionLabel}
    </span>
    <button onClick={() => startEditing(sectionKey)} className="p-1 rounded-md hover:bg-white/[0.04] transition-colors">
      <Pencil className="w-3 h-3" style={{ color: "var(--bz-text-3)" }} />
    </button>
  </div>
  {/* content or textarea */}
</div>
```

### Right Panel Footer (sticky)
```tsx
<div className="flex items-center gap-2 px-4 py-3 rounded-2xl border mt-auto"
  style={{ background: "rgba(255,255,255,0.03)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", borderColor: "rgba(255,255,255,0.07)" }}>
  {/* Position select */}
  <Select value={position} onValueChange={setPosition}>
    <SelectTrigger className="flex-1 h-8 text-[11px]" style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.07)", color: "var(--bz-text-2)" }}>
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {POSITIONS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
    </SelectContent>
  </Select>

  {/* Publish button */}
  <button
    onClick={handlePublish}
    disabled={publishing || !result}
    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[11.5px] font-semibold transition-all"
    style={{ background: "rgba(212,132,90,0.12)", color: "var(--bz-accent)", border: "1px solid rgba(212,132,90,0.2)" }}
  >
    {publishing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
    {publishing ? "Publishing..." : "Publish"}
  </button>

  {/* Copy JSON */}
  <button onClick={handleCopyJson} className="p-2 rounded-xl transition-all hover:bg-white/[0.04]"
    style={{ border: "1px solid rgba(255,255,255,0.07)", color: "var(--bz-text-3)" }}>
    <Copy className="w-3.5 h-3.5" />
  </button>

  {/* Export JSON */}
  <button onClick={handleExportJson} className="p-2 rounded-xl transition-all hover:bg-white/[0.04]"
    style={{ border: "1px solid rgba(255,255,255,0.07)", color: "var(--bz-text-3)" }}>
    <Download className="w-3.5 h-3.5" />
  </button>
</div>
```

---

## Token Migration Map (exhaustive)

Replace every occurrence in all three files:

| From | To |
|------|----|
| `bg-[var(--background-elevated)]` | inline style `background: "var(--bz-elevated)"` |
| `bg-[var(--background-secondary)]` | inline style `background: "var(--bz-surface)"` |
| `bg-[var(--background)]` | inline style `background: "var(--bz-base)"` |
| `text-[var(--foreground)]` | inline style `color: "var(--bz-text-1)"` |
| `text-[var(--foreground-muted)]` | inline style `color: "var(--bz-text-2)"` |
| `border-[var(--border)]` | inline style `borderColor: "var(--bz-border)"` |
| `text-[var(--accent)]` | inline style `color: "var(--bz-accent)"` |
| `bg-[var(--accent)]/10` | inline style `background: "rgba(212,132,90,0.1)"` |
| `border border-[#27272a]` | inline style `border: "1px solid rgba(255,255,255,0.07)"` |
| `bg-[#181818]` | inline style `background: "rgba(255,255,255,0.03)"` |
| `bg-[#262626]` | inline style `background: "rgba(255,255,255,0.04)"` |
| `text-[#f5f5f5]` | inline style `color: "var(--bz-text-1)"` |
| `text-[#737373]` | inline style `color: "var(--bz-text-3)"` |
| Shadcn `<Card>/<CardHeader>/<CardContent>` | plain `<div>` with glassmorphism inline styles |
| Shadcn `<Button>` (where replaceable) | plain `<button>` with inline styles |

> **Note:** Shadcn `<Select>`, `<Dialog>`, `<Input>` components can be kept where the behavior is needed; update their `className`/`style` props.

---

## Files Changed

| File | Change |
|------|--------|
| `apps/mouth/src/app/(workspace)/intelligence/visa-oracle/page.tsx` | Full JSX/style rewrite, logic untouched |
| `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx` | Full JSX/style rewrite, logic untouched |
| `apps/mouth/src/app/(workspace)/intelligence/article-composer/page.tsx` | Full JSX/style rewrite, logic untouched |

## Files NOT Changed

- All API modules (`intelligence.api.ts`, `articles.api.ts`)
- All handler functions and state management
- `news-room/components/ArticleEditor.tsx` — minor token migration only
- `news-room/components/CoverImageUploader.tsx` — minor token migration only
- All test files (tests verify behavior not styles)

# Intelligence Sub-pages Redesign

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Redesign the three Intelligence sub-pages (Visa Oracle, News Room, Article Composer) to use the Warm Depth glassmorphism design system (`--bz-*` tokens) consistent with the Trinity homepage and workspace identity.

**Architecture:** Pure visual/UX redesign — no logic changes. All business logic, API calls, state management, and handlers remain identical. Only JSX structure, CSS classes, and inline styles change. Each page gets a layout tailored to its function.

**Tech Stack:** Next.js 14 App Router, `"use client"`, Tailwind CSS, `--bz-*` CSS custom properties, lucide-react icons.

---

## Design System Reference

### Tokens (replace all old `var(--background*)`, `var(--foreground*)`, `var(--accent)`)

All `--bz-*` tokens are defined in `packages/core/styles/bz-tokens.css`.

| Old token                     | New token            | Purpose                                                                                                                                                                                |
| ----------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `var(--background)`           | `var(--bz-base)`     | Page background (`#0c0c0e`)                                                                                                                                                            |
| `var(--background-elevated)`  | `var(--bz-elevated)` | Sidebar/elevated surfaces                                                                                                                                                              |
| `var(--background-secondary)` | `var(--bz-surface)`  | Secondary surfaces                                                                                                                                                                     |
| `var(--foreground)`           | `var(--bz-text-1)`   | Primary text                                                                                                                                                                           |
| `var(--foreground-muted)`     | `var(--bz-text-2)`   | Secondary text                                                                                                                                                                         |
| _(none — new)_                | `var(--bz-text-3)`   | Tertiary/hint text — **decorative only** (`#575350`, very dark on dark bg). Use only for separators, dividers, icon hints. For readable timestamps/metadata use `--bz-text-2` instead. |
| `var(--accent)`               | `var(--bz-accent)`   | Brand accent (`#d4845a`)                                                                                                                                                               |
| `var(--border)`               | `var(--bz-border)`   | Borders                                                                                                                                                                                |
| `var(--bz-green)`             | `var(--bz-green)`    | Success green (`#4db87a`)                                                                                                                                                              |

### Glassmorphism card base (used throughout)

```css
background: rgba(255, 255, 255, 0.03);
backdropfilter: blur(12px);
webkitbackdropfilter: blur(12px);
bordercolor: rgba(255, 255, 255, 0.07);
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
      <AlertTriangle
        className="w-4 h-4"
        style={{ color: "var(--bz-accent)" }}
      />
      <span
        className="text-[12px] font-medium"
        style={{ color: "var(--bz-text-1)" }}
      >
        {filteredAndSortedItems.length} of {items.length} pending
      </span>
    </div>
    <div className="h-3 w-px" style={{ background: "var(--bz-border)" }} />
    <span className="text-[11px]" style={{ color: "var(--bz-text-2)" }}>
      {items.filter((i) => i.detection_type === "NEW").length} new ·{" "}
      {items.filter((i) => i.detection_type === "UPDATED").length} updated
    </span>
    {selectedItems.size > 0 && (
      <>
        <div className="h-3 w-px" style={{ background: "var(--bz-border)" }} />
        <span
          className="text-[11px] font-semibold"
          style={{ color: "var(--bz-accent)" }}
        >
          {selectedItems.size} selected
        </span>
      </>
    )}
  </div>
  {/* Right: refresh */}
  <button
    onClick={loadItems}
    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-white/[0.04]"
    style={{
      color: "var(--bz-text-2)",
      border: "1px solid rgba(255,255,255,0.07)",
    }}
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
    <Search
      className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
      style={{ color: "var(--bz-text-3)" }}
    />
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
  {/* Shadcn Select components — keep existing, just update SelectTrigger className/style */}
  <Select
    value={filterType}
    onValueChange={(v) => setFilterType(v as FilterType)}
  >
    <SelectTrigger
      className="w-[130px] h-8 text-[11px] rounded-xl"
      style={{
        background: "rgba(255,255,255,0.04)",
        borderColor: "rgba(255,255,255,0.07)",
        color: "var(--bz-text-2)",
      }}
    >
      <Filter
        className="w-3 h-3 mr-1.5"
        style={{ color: "var(--bz-text-3)" }}
      />
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Types</SelectItem>
      <SelectItem value="NEW">New Only</SelectItem>
      <SelectItem value="UPDATED">Updated Only</SelectItem>
    </SelectContent>
  </Select>
  {/* Sort select — same SelectTrigger style */}

  {/* Bulk actions inline — only when selectedItems.size > 0 */}
  {selectedItems.size > 0 && (
    <div className="flex gap-2 ml-auto">
      <button
        onClick={toggleSelectAll}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium transition-all hover:bg-white/[0.04]"
        style={{
          color: "var(--bz-text-2)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        {selectedItems.size === filteredAndSortedItems.length ? (
          <>
            <CheckSquare className="w-3.5 h-3.5" /> Deselect All
          </>
        ) : (
          <>
            <Square className="w-3.5 h-3.5" /> Select All
          </>
        )}
      </button>
      <button
        onClick={handleBulkApprove}
        disabled={!!processing}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
        style={{
          background: "rgba(77,184,122,0.12)",
          color: "var(--bz-green)",
          border: "1px solid rgba(77,184,122,0.2)",
        }}
      >
        <Check className="w-3.5 h-3.5" /> Approve ({selectedItems.size})
      </button>
      <button
        onClick={handleBulkReject}
        disabled={!!processing}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
        style={{
          background: "rgba(239,68,68,0.08)",
          color: "rgba(239,68,68,0.8)",
          border: "1px solid rgba(239,68,68,0.2)",
        }}
      >
        <X className="w-3.5 h-3.5" /> Reject ({selectedItems.size})
      </button>
    </div>
  )}
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
      <button
        onClick={() => toggleSelectItem(item.id)}
        className="mt-0.5 p-1 rounded-lg transition-colors hover:bg-white/[0.04]"
      >
        {selectedItems.has(item.id) ? (
          <CheckSquare
            className="w-4 h-4"
            style={{ color: "var(--bz-accent)" }}
          />
        ) : (
          <Square className="w-4 h-4" style={{ color: "var(--bz-text-3)" }} />
        )}
      </button>
      <div className="flex-1 space-y-1.5">
        {/* Badge */}
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold"
          style={
            item.detection_type === "NEW"
              ? {
                  background: "rgba(212,132,90,0.12)",
                  color: "var(--bz-accent)",
                  border: "1px solid rgba(212,132,90,0.2)",
                }
              : {
                  background: "rgba(251,191,36,0.12)",
                  color: "rgba(251,191,36,0.9)",
                  border: "1px solid rgba(251,191,36,0.2)",
                }
          }
        >
          {item.detection_type === "NEW"
            ? "✦ NEW REGULATION"
            : "↺ UPDATED POLICY"}
        </span>
        {/* Title */}
        <h3
          className="text-[13.5px] font-semibold leading-snug"
          style={{ color: "var(--bz-text-1)" }}
        >
          {item.title}
        </h3>
        {/* Metadata */}
        <div
          className="flex items-center gap-3 text-[10.5px]"
          style={{ color: "var(--bz-text-2)" }}
        >
          <span className="font-mono">#{item.id.slice(0, 8)}</span>
          <div
            className="w-px h-3"
            style={{ background: "var(--bz-border)" }}
          />
          <span>
            {new Date(item.detected_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
        </div>
      </div>
      {/* Source link */}
      <a
        href={item.source}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10.5px] font-medium transition-all hover:bg-white/[0.04]"
        style={{
          color: "var(--bz-text-2)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        Source <ExternalLink className="w-3 h-3" />
      </a>
    </div>
  </div>

  {/* Preview section (when open) */}
  {previewId === item.id && (
    <div className="px-4 pb-3">
      <div
        className="rounded-xl p-3"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <span
            className="text-[11px] font-semibold"
            style={{ color: "var(--bz-text-2)" }}
          >
            Content Preview
          </span>
          <button
            onClick={() => {
              setPreviewId(null);
              setPreviewContent("");
            }}
          >
            <X className="w-3.5 h-3.5" style={{ color: "var(--bz-text-3)" }} />
          </button>
        </div>
        <pre
          className="text-[10.5px] whitespace-pre-wrap font-mono max-h-48 overflow-auto"
          style={{ color: "var(--bz-text-2)" }}
        >
          {previewContent}
        </pre>
      </div>
    </div>
  )}

  {/* Card footer — actions */}
  <div
    className="flex items-center gap-2 px-4 py-3"
    style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
  >
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
      style={{
        color: "rgba(239,68,68,0.8)",
        border: "1px solid rgba(239,68,68,0.2)",
        background: "rgba(239,68,68,0.05)",
      }}
    >
      <X className="w-3.5 h-3.5" /> Reject
    </button>
    {/* Approve */}
    <button
      onClick={() => handleApprove(item.id)}
      disabled={!!processing}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all"
      style={{
        background: "rgba(77,184,122,0.15)",
        color: "var(--bz-green)",
        border: "1px solid rgba(77,184,122,0.25)",
      }}
    >
      {processing === item.id ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Ingesting...
        </>
      ) : (
        <>
          <Check className="w-3.5 h-3.5" /> Approve & Ingest
        </>
      )}
    </button>
  </div>
</div>
```

### Loading State

```tsx
<div className="flex flex-col items-center justify-center h-64 gap-4">
  <Loader2
    className="w-8 h-8 animate-spin"
    style={{ color: "var(--bz-accent)" }}
  />
  <p
    className="text-[12px] animate-pulse"
    style={{ color: "var(--bz-text-2)" }}
  >
    Scanning Intelligence Feed...
  </p>
</div>
```

### Empty State

```tsx
<div
  className="flex flex-col items-center justify-center py-24 rounded-2xl border-2 border-dashed"
  style={{
    borderColor: "rgba(255,255,255,0.07)",
    background: "rgba(255,255,255,0.01)",
  }}
>
  <div
    className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
    style={{
      background: "rgba(212,132,90,0.08)",
      border: "1px solid rgba(212,132,90,0.15)",
    }}
  >
    <Sparkles className="w-8 h-8" style={{ color: "var(--bz-accent)" }} />
  </div>
  <h3
    className="text-[15px] font-semibold mb-1"
    style={{ color: "var(--bz-text-1)" }}
  >
    All Caught Up!
  </h3>
  <p
    className="text-[12px] text-center max-w-sm mb-6"
    style={{ color: "var(--bz-text-2)" }}
  >
    {items.length === 0
      ? "No pending visa updates. The agent is continuously monitoring imigrasi.go.id."
      : "No items match your current filters."}
  </p>
  <button
    onClick={loadItems}
    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-medium transition-all hover:bg-white/[0.04]"
    style={{
      color: "var(--bz-text-2)",
      border: "1px solid rgba(255,255,255,0.07)",
    }}
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
      <div
        className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold rounded-bl-lg"
        style={{ background: "rgba(239,68,68,0.9)", color: "#fff" }}
      >
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
      {selectedItems.has(item.id) ? (
        <CheckSquare
          className="w-4 h-4"
          style={{ color: "var(--bz-accent)" }}
        />
      ) : (
        <Square className="w-4 h-4 opacity-60" style={{ color: "#fff" }} />
      )}
    </button>
  </div>

  {/* Cover image — use item.cover_image (NOT cover_image_url, which doesn't exist on StagingItem) */}
  <div className="relative aspect-video overflow-hidden">
    {item.cover_image ? (
      <img
        src={item.cover_image}
        alt={item.title}
        className="w-full h-full object-cover"
        onError={(e) => {
          e.currentTarget.style.display = "none";
        }}
      />
    ) : (
      <div
        className="w-full h-full flex items-center justify-center"
        style={{
          background:
            "linear-gradient(135deg, rgba(212,132,90,0.08) 0%, rgba(99,102,241,0.08) 100%)",
        }}
      >
        <ImageIcon className="w-8 h-8" style={{ color: "var(--bz-text-3)" }} />
      </div>
    )}
    {/* Hover overlay with actions — shown on hover (desktop) and always-visible on touch */}
    <div
      className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center justify-center gap-2"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
    >
      <button
        onClick={() => handlePreview(item)}
        className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
        style={{ border: "1px solid rgba(255,255,255,0.15)" }}
      >
        <Eye className="w-4 h-4 text-white" />
      </button>
      <button
        onClick={() => setEditingItem(item)}
        className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
        style={{ border: "1px solid rgba(255,255,255,0.15)" }}
      >
        <Edit className="w-4 h-4 text-white" />
      </button>
      <button
        onClick={() => setCoverUploadItem(item)}
        className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
        style={{ border: "1px solid rgba(255,255,255,0.15)" }}
      >
        <ImageIcon className="w-4 h-4 text-white" />
      </button>
    </div>
    {/* Touch fallback: small icon buttons always visible bottom-right */}
    <div className="absolute bottom-2 right-2 flex gap-1 sm:hidden">
      <button
        onClick={() => setEditingItem(item)}
        className="p-1.5 rounded-md"
        style={{
          background: "rgba(0,0,0,0.7)",
          border: "1px solid rgba(255,255,255,0.15)",
        }}
      >
        <Edit className="w-3 h-3 text-white" />
      </button>
      <button
        onClick={() => setCoverUploadItem(item)}
        className="p-1.5 rounded-md"
        style={{
          background: "rgba(0,0,0,0.7)",
          border: "1px solid rgba(255,255,255,0.15)",
        }}
      >
        <ImageIcon className="w-3 h-3 text-white" />
      </button>
    </div>
  </div>

  {/* Card body */}
  <div className="p-3 space-y-2">
    {/* Source badge + date */}
    <div className="flex items-center justify-between">
      <span
        className="text-[9.5px] font-semibold px-2 py-0.5 rounded-full"
        style={{
          background: "rgba(212,132,90,0.1)",
          color: "var(--bz-accent)",
          border: "1px solid rgba(212,132,90,0.15)",
        }}
      >
        {item.source
          ? new URL(item.source).hostname.replace("www.", "")
          : "intel"}
      </span>
      <span
        className="text-[10px] flex items-center gap-1"
        style={{ color: "var(--bz-text-2)" }}
      >
        <Calendar className="w-3 h-3" />
        {new Date(item.detected_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        })}
      </span>
    </div>

    {/* Title */}
    <h3
      className="text-[12.5px] font-semibold leading-snug line-clamp-2"
      style={{ color: "var(--bz-text-1)" }}
    >
      {item.title}
    </h3>
  </div>

  {/* Card footer — position selector + publish */}
  <div className="px-3 pb-3 space-y-2">
    {/* Position select */}
    <Select
      value={getPosition(item.id)}
      onValueChange={(v) =>
        setPublishPosition((prev) => ({ ...prev, [item.id]: v }))
      }
    >
      <SelectTrigger
        className="h-7 text-[10.5px] rounded-lg"
        style={{
          background: "rgba(255,255,255,0.04)",
          borderColor: "rgba(255,255,255,0.07)",
          color: "var(--bz-text-2)",
        }}
      >
        <MapPin
          className="w-3 h-3 mr-1"
          style={{ color: "var(--bz-text-3)" }}
        />
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

    {/* Publish button — handlePublish takes the full StagingItem object, not (id, position) */}
    <button
      onClick={() => handlePublish(item)}
      disabled={publishingIds.has(item.id)}
      className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
      style={{
        background: "rgba(212,132,90,0.12)",
        color: "var(--bz-accent)",
        border: "1px solid rgba(212,132,90,0.2)",
      }}
    >
      {publishingIds.has(item.id) ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Publishing...
        </>
      ) : (
        <>
          <Sparkles className="w-3.5 h-3.5" /> Publish
        </>
      )}
    </button>
  </div>
</div>
```

### Bulk Actions Sticky Bar

```tsx
{
  selectedItems.size > 0 && (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-2xl shadow-2xl z-50"
      style={{
        background: "rgba(18,18,20,0.9)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.1)",
      }}
    >
      <span
        className="text-[12px] font-semibold"
        style={{ color: "var(--bz-text-1)" }}
      >
        {selectedItems.size} selected
      </span>
      <div
        className="w-px h-4"
        style={{ background: "rgba(255,255,255,0.1)" }}
      />
      <button
        onClick={handleBulkPublish}
        className="text-[11px] font-medium px-3 py-1.5 rounded-lg transition-all"
        style={{
          background: "rgba(212,132,90,0.12)",
          color: "var(--bz-accent)",
          border: "1px solid rgba(212,132,90,0.2)",
        }}
      >
        Publish all
      </button>
      <button
        onClick={() => setSelectedItems(new Set())}
        className="text-[11px] px-3 py-1.5 rounded-lg transition-all hover:bg-white/[0.04]"
        style={{ color: "var(--bz-text-2)" }}
      >
        Deselect
      </button>
    </div>
  );
}
```

### Loading State

```tsx
<div className="flex flex-col items-center justify-center h-64 gap-4">
  <Loader2
    className="w-8 h-8 animate-spin"
    style={{ color: "var(--bz-accent)" }}
  />
  <p
    className="text-[12px] animate-pulse"
    style={{ color: "var(--bz-text-2)" }}
  >
    Gathering Intelligence...
  </p>
</div>
```

### Empty State

Same glassmorphism empty state pattern as Visa Oracle, with `Sparkles` icon and `--bz-accent` colors.

---

## Section 3: Article Composer

**File:** `apps/mouth/src/app/(workspace)/intelligence/article-composer/page.tsx`

**Layout:** 50/50 split panel (side-by-side on desktop, stacked on mobile via flex-col breakpoint).

### Structural changes

**Remove the sticky `<header>` top bar** (lines 367–390 in source) — it duplicates the workspace layout nav. Replace it with just the left panel header (see below).

**Remove the `<main>` wrapper and the `<h1>Article Composer</h1>` subtitle** (lines 393–407) — the workspace layout already provides page context.

**Remove the `<style>` tag** with custom scrollbar CSS (lines 353–365) — no longer needed.

**Replace `min-h-screen bg-[#111111]`** outer wrapper with clean `space-y-0` or nothing — content fits workspace scroll.

### statusLoading state

```tsx
if (statusLoading) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <Loader2
        className="w-8 h-8 animate-spin"
        style={{ color: "var(--bz-accent)" }}
      />
      <p
        className="text-[12px] animate-pulse"
        style={{ color: "var(--bz-text-2)" }}
      >
        Initializing Intelligence Center...
      </p>
    </div>
  );
}
```

### Page wrapper (split panel)

```tsx
{
  /* Mobile: stacked. Desktop (lg+): side by side */
}
<div className="flex flex-col lg:flex-row gap-5 min-h-0">
  {/* Left panel */}
  <div className="flex-1 flex flex-col gap-4 min-w-0">
    {/* ... input panel ... */}
  </div>

  {/* Divider — hidden on mobile */}
  <div
    className="hidden lg:block w-px self-stretch"
    style={{ background: "rgba(255,255,255,0.06)" }}
  />

  {/* Right panel */}
  <div className="flex-1 flex flex-col gap-4 min-w-0">
    {/* ... preview panel ... */}
  </div>
</div>;
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
const inputClass =
  "w-full rounded-xl border px-3 py-2.5 text-[13px] outline-none transition-all";
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
<div
  className="flex items-center justify-between px-4 py-3 rounded-2xl border"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  <div className="flex items-center gap-2">
    <FileText className="w-4 h-4" style={{ color: "var(--bz-accent)" }} />
    <span
      className="text-[12px] font-semibold"
      style={{ color: "var(--bz-text-1)" }}
    >
      Raw Content
    </span>
  </div>
  <div className="flex items-center gap-3">
    {/* API status */}
    <div className="flex items-center gap-1.5">
      <div
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background: configured ? "var(--bz-green)" : "rgba(239,68,68,0.8)",
          boxShadow: configured ? "0 0 4px rgba(77,184,122,0.5)" : "none",
        }}
      />
      <span className="text-[10px]" style={{ color: "var(--bz-text-2)" }}>
        {configured ? "API Ready" : "API Offline"}
      </span>
    </div>
    {/* Cost pill */}
    {apiCost > 0 && (
      <span
        className="text-[10px] px-2 py-0.5 rounded-full"
        style={{
          background: "rgba(255,255,255,0.04)",
          color: "var(--bz-text-2)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
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
    background:
      loading || !configured || !title.trim()
        ? "rgba(255,255,255,0.04)"
        : "linear-gradient(135deg, rgba(212,132,90,0.8) 0%, rgba(180,100,60,0.8) 100%)",
    color:
      loading || !configured || !title.trim() ? "var(--bz-text-2)" : "#fff",
    border: "1px solid rgba(212,132,90,0.2)",
  }}
>
  {loading ? (
    <>
      <Loader2 className="w-4 h-4 animate-spin" /> Composing...
    </>
  ) : (
    <>
      <Sparkles className="w-4 h-4" /> Compose with AI
    </>
  )}
</button>
```

### Right Panel — Placeholder (before compose)

```tsx
<div
  className="flex-1 flex flex-col items-center justify-center gap-4 rounded-2xl border"
  style={{
    background: "rgba(255,255,255,0.02)",
    borderColor: "rgba(255,255,255,0.06)",
    borderStyle: "dashed",
    minHeight: "320px",
  }}
>
  <div
    className="w-14 h-14 rounded-2xl flex items-center justify-center"
    style={{
      background: "rgba(212,132,90,0.08)",
      border: "1px solid rgba(212,132,90,0.15)",
    }}
  >
    <Sparkles className="w-7 h-7" style={{ color: "var(--bz-accent)" }} />
  </div>
  <div className="text-center">
    <p
      className="text-[13px] font-medium mb-1"
      style={{ color: "var(--bz-text-2)" }}
    >
      AI Preview
    </p>
    <p className="text-[11.5px]" style={{ color: "var(--bz-text-2)" }}>
      Fill in the form and click Compose
    </p>
  </div>
</div>
```

### Left Panel — Error state

Shown when `error` is non-null (after a failed compose attempt):

```tsx
{
  error && (
    <div
      className="px-3 py-2.5 rounded-xl text-[12px]"
      style={{
        background: "rgba(239,68,68,0.08)",
        border: "1px solid rgba(239,68,68,0.2)",
        color: "rgba(239,68,68,0.9)",
      }}
    >
      {error}
    </div>
  );
}
```

### Right Panel — Result sections

The source uses a **single global `isEditing` boolean** (not per-section). Keep that exact logic. The Edit button calls `startEditing()` (no arguments) and puts the entire preview into edit mode. Save calls `saveEdits()`, Cancel calls `cancelEditing()`.

All result sections (Headline, TL;DR, The Facts, Bali Zero Take, Next Steps, Tags) are wrapped in glassmorphism section cards. In view mode: rendered content. In edit mode: textarea with `updateEditedField(path, value)`.

```tsx
{
  /* Single "Edit Article" button — top of right panel, only when result exists and not editing */
}
{
  result && !isEditing && (
    <div className="flex justify-end">
      <button
        onClick={startEditing}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium transition-all hover:bg-white/[0.04]"
        style={{
          color: "var(--bz-text-2)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <Pencil className="w-3.5 h-3.5" /> Edit Article
      </button>
    </div>
  );
}
{
  isEditing && (
    <div className="flex gap-2 justify-end">
      <button
        onClick={cancelEditing}
        className="px-3 py-1.5 rounded-xl text-[11px]"
        style={{ color: "var(--bz-text-2)" }}
      >
        Cancel
      </button>
      <button
        onClick={saveEdits}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold"
        style={{
          background: "rgba(77,184,122,0.12)",
          color: "var(--bz-green)",
          border: "1px solid rgba(77,184,122,0.2)",
        }}
      >
        <Save className="w-3.5 h-3.5" /> Save Changes
      </button>
    </div>
  );
}

{
  /* Section card pattern (view mode example): */
}
<div
  className="rounded-xl border p-4 space-y-2"
  style={{
    background: "rgba(255,255,255,0.03)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  <span
    className="text-[10px] font-semibold uppercase tracking-wider"
    style={{ color: "var(--bz-text-2)" }}
  >
    {sectionLabel}
  </span>
  {/* view mode: rendered content */}
  {/* edit mode: textarea with updateEditedField(path, value) */}
</div>;
```

### Right Panel Footer (sticky)

```tsx
<div
  className="flex items-center gap-2 px-4 py-3 rounded-2xl border mt-auto"
  style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.07)",
  }}
>
  {/* Position select */}
  <Select value={position} onValueChange={setPosition}>
    <SelectTrigger
      className="flex-1 h-8 text-[11px]"
      style={{
        background: "rgba(255,255,255,0.04)",
        borderColor: "rgba(255,255,255,0.07)",
        color: "var(--bz-text-2)",
      }}
    >
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {POSITIONS.map((p) => (
        <SelectItem key={p.value} value={p.value}>
          {p.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>

  {/* Publish button */}
  <button
    onClick={handlePublish}
    disabled={publishing || !result}
    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[11.5px] font-semibold transition-all"
    style={{
      background: "rgba(212,132,90,0.12)",
      color: "var(--bz-accent)",
      border: "1px solid rgba(212,132,90,0.2)",
    }}
  >
    {publishing ? (
      <Loader2 className="w-3.5 h-3.5 animate-spin" />
    ) : (
      <Send className="w-3.5 h-3.5" />
    )}
    {publishing ? "Publishing..." : "Publish"}
  </button>

  {/* Copy JSON */}
  <button
    onClick={handleCopyJson}
    className="p-2 rounded-xl transition-all hover:bg-white/[0.04]"
    style={{
      border: "1px solid rgba(255,255,255,0.07)",
      color: "var(--bz-text-3)",
    }}
  >
    <Copy className="w-3.5 h-3.5" />
  </button>

  {/* Export JSON */}
  <button
    onClick={handleExportJson}
    className="p-2 rounded-xl transition-all hover:bg-white/[0.04]"
    style={{
      border: "1px solid rgba(255,255,255,0.07)",
      color: "var(--bz-text-3)",
    }}
  >
    <Download className="w-3.5 h-3.5" />
  </button>
</div>
```

---

## Token Migration Map (exhaustive)

Replace every occurrence in all three files:

| From                                         | To                                                                                                                        |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `bg-[var(--background-elevated)]`            | inline style `background: "var(--bz-elevated)"`                                                                           |
| `bg-[var(--background-secondary)]`           | inline style `background: "var(--bz-surface)"`                                                                            |
| `bg-[var(--background)]`                     | inline style `background: "var(--bz-base)"`                                                                               |
| `text-[var(--foreground)]`                   | inline style `color: "var(--bz-text-1)"`                                                                                  |
| `text-[var(--foreground-muted)]`             | inline style `color: "var(--bz-text-2)"`                                                                                  |
| `border-[var(--border)]`                     | inline style `borderColor: "var(--bz-border)"`                                                                            |
| `text-[var(--accent)]`                       | inline style `color: "var(--bz-accent)"`                                                                                  |
| `bg-[var(--accent)]/10`                      | inline style `background: "rgba(212,132,90,0.1)"`                                                                         |
| `bg-[var(--accent)]/20`                      | inline style `background: "rgba(212,132,90,0.2)"`                                                                         |
| `border-[var(--accent)]/20`                  | inline style `borderColor: "rgba(212,132,90,0.2)"`                                                                        |
| `border-[var(--accent)]/30`                  | inline style `borderColor: "rgba(212,132,90,0.3)"`                                                                        |
| `text-[var(--accent)]/90`                    | inline style `color: "rgba(212,132,90,0.9)"`                                                                              |
| `border border-[#27272a]`                    | inline style `border: "1px solid rgba(255,255,255,0.07)"`                                                                 |
| `bg-[#111]` / `bg-[#111111]`                 | inline style `background: "var(--bz-base)"`                                                                               |
| `bg-[#181818]`                               | inline style `background: "rgba(255,255,255,0.03)"`                                                                       |
| `bg-[#262626]`                               | inline style `background: "rgba(255,255,255,0.04)"`                                                                       |
| `bg-[#101010]`                               | inline style `background: "var(--bz-elevated)"`                                                                           |
| `text-[#f5f5f5]`                             | inline style `color: "var(--bz-text-1)"`                                                                                  |
| `text-[#737373]`                             | inline style `color: "var(--bz-text-2)"` for readable content; `color: "var(--bz-text-3)"` only for decorative/icon hints |
| `text-[#a3a3a3]`                             | inline style `color: "var(--bz-text-2)"`                                                                                  |
| `border-[#27272a]`                           | inline style `borderColor: "rgba(255,255,255,0.07)"`                                                                      |
| `text-[#6366f1]` (indigo accent in composer) | inline style `color: "var(--bz-accent)"`                                                                                  |
| `focus:border-[#6366f1]`                     | use `onFocus`/`onBlur` with `borderColor: "var(--bz-accent)"`                                                             |
| `text-green-500` / `bg-green-500/10`         | inline style `color: "var(--bz-green)"` / `background: "rgba(77,184,122,0.1)"`                                            |
| `border-green-500/40`                        | inline style `borderColor: "rgba(77,184,122,0.4)"`                                                                        |
| Shadcn `<Card>/<CardHeader>/<CardContent>`   | plain `<div>` with glassmorphism inline styles                                                                            |
| Shadcn `<Button>` (where replaceable)        | plain `<button>` with inline styles                                                                                       |

> **Note:** Shadcn `<Select>`, `<Dialog>`, `<Input>` components can be kept where the behavior is needed; update their `className`/`style` props.

---

## Files Changed

| File                                                                    | Change                                  |
| ----------------------------------------------------------------------- | --------------------------------------- |
| `apps/mouth/src/app/(workspace)/intelligence/visa-oracle/page.tsx`      | Full JSX/style rewrite, logic untouched |
| `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`        | Full JSX/style rewrite, logic untouched |
| `apps/mouth/src/app/(workspace)/intelligence/article-composer/page.tsx` | Full JSX/style rewrite, logic untouched |

## Files NOT Changed

- All API modules (`intelligence.api.ts`, `articles.api.ts`)
- All handler functions and state management
- `news-room/components/ArticleEditor.tsx` — minor token migration only
- `news-room/components/CoverImageUploader.tsx` — minor token migration only
- All test files (tests verify behavior not styles)

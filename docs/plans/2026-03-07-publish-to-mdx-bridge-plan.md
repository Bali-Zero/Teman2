# Publish-to-MDX Bridge with Homepage Position Control — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add homepage position selection to the newsroom publish flow so articles land in the right hero/insight slot on balizero.com.

**Architecture:** The publish pipeline already works (Qdrant + GitHub MDX + news_items). We add: (1) a `homepage-layout.json` config file replacing hardcoded slugs in `NewsPageClient.tsx`, (2) a position parameter to the publish API, and (3) a position dropdown in the newsroom UI.

**Tech Stack:** Next.js (frontend), FastAPI (backend), TypeScript, Python, JSON config

---

### Task 1: Create homepage-layout.json with current hardcoded slugs

**Files:**

- Create: `apps/mouth/src/content/homepage-layout.json`

**Step 1: Create the config file with current hardcoded values**

Extract the 8 hardcoded slugs from `NewsPageClient.tsx` lines 53-76 into JSON:

```json
{
  "hero_main": "slow-paralysis-kbli-2025",
  "hero_2": "constitutional-clash-bank-statements",
  "hero_3": "kbli-2025-bali-transformation",
  "hero_4": "art-of-strategic-patience",
  "hero_5": "ota-data-crackdown-bali-2026",
  "insight_1": "capital-evolution-bkpm-5-2025",
  "insight_2": "ota-delisting-bali-2026",
  "insight_3": "glamping-trap-kbli-55209"
}
```

**Step 2: Commit**

```bash
git add apps/mouth/src/content/homepage-layout.json
git commit -m "feat(mouth): add homepage-layout.json config for article positions"
```

---

### Task 2: Wire NewsPageClient.tsx to read from homepage-layout.json

**Files:**

- Modify: `apps/mouth/src/app/(blog)/NewsPageClient.tsx:52-79`

**Step 1: Replace hardcoded slugs with layout import**

At the top of the file (after imports), add:

```typescript
import homepageLayout from "@/content/homepage-layout.json";
```

Then replace lines 52-79 (the hardcoded slug lookups) with:

```typescript
// Get articles for hero collage from layout config
const mainNews1 = articles.find((a) => a.slug === homepageLayout.hero_main);
const mainNews2 = articles.find((a) => a.slug === homepageLayout.hero_2);
const mainNews3 = articles.find((a) => a.slug === homepageLayout.hero_3);
const mainNews4 = articles.find((a) => a.slug === homepageLayout.hero_4);
const mainNews5 = articles.find((a) => a.slug === homepageLayout.hero_5);

// Get insight articles from layout config
const kbliInsight1 = articles.find((a) => a.slug === homepageLayout.insight_1);
const kbliInsight2 = articles.find((a) => a.slug === homepageLayout.insight_2);
const kbliInsight3 = articles.find((a) => a.slug === homepageLayout.insight_3);
```

**Step 2: Verify build**

```bash
cd apps/mouth && npm run build
```

Expected: Build succeeds — JSON import is natively supported by Next.js.

**Step 3: Commit**

```bash
git add apps/mouth/src/app/(blog)/NewsPageClient.tsx
git commit -m "feat(mouth): read homepage article positions from layout JSON config"
```

---

### Task 3: Add position parameter to backend publish endpoint

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/intel.py:888-1048`

**Step 1: Add position parameter to publish_staging_item**

At line 888, change the function signature to accept a request body with position:

```python
class PublishToSiteRequest(BaseModel):
    """Optional request body for publish with homepage position."""
    position: str = "latest"  # hero_main, hero_2-5, insight_1-3, or "latest"

@router.post("/api/intel/staging/publish/{type}/{item_id}")
async def publish_staging_item(
    type: str,
    item_id: str,
    body: PublishToSiteRequest | None = None,
    request: Request = None,
) -> dict[str, Any]:
```

**Step 2: Pass position to publish_article call**

At line 1048, replace:

```python
position="normal",
```

with:

```python
position=body.position if body else "latest",
```

**Step 3: After GitHub publish succeeds, update homepage-layout.json via GitHub API**

After line 1074 (inside the `if publish_result.success:` block), add:

```python
                # Update homepage-layout.json if position is not "latest"
                publish_position = body.position if body else "latest"
                if publish_position != "latest":
                    try:
                        await update_homepage_layout(
                            slug=publish_result.slug or item_id,
                            position=publish_position,
                        )
                        logger.info(
                            "✅ Homepage layout updated",
                            extra={
                                "position": publish_position,
                                "slug": publish_result.slug or item_id,
                            },
                        )
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to update homepage layout: {e}",
                            extra={"position": publish_position},
                        )
```

**Step 4: Implement `update_homepage_layout` function**

Add this function above the endpoint (around line 130):

```python
async def update_homepage_layout(slug: str, position: str) -> None:
    """
    Update homepage-layout.json in the GitHub repo.
    Reads current file, updates the position, commits the change.
    """
    import httpx

    github_token = os.getenv("GITHUB_TOKEN")
    github_owner = os.getenv("GITHUB_OWNER", "Balizero1987")
    github_repo = os.getenv("GITHUB_REPO", "Teman2")
    file_path = "apps/mouth/src/content/homepage-layout.json"

    if not github_token:
        raise ValueError("GITHUB_TOKEN not configured")

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        # Get current file content + SHA
        url = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/{file_path}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        file_data = resp.json()
        current_sha = file_data["sha"]

        # Decode and parse current layout
        import base64
        current_content = base64.b64decode(file_data["content"]).decode("utf-8")
        layout = json.loads(current_content)

        # Update the position
        valid_positions = {
            "hero_main", "hero_2", "hero_3", "hero_4", "hero_5",
            "insight_1", "insight_2", "insight_3",
        }
        if position not in valid_positions:
            raise ValueError(f"Invalid position: {position}")

        layout[position] = slug

        # Commit the updated layout
        new_content = json.dumps(layout, indent=2) + "\n"
        encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

        update_resp = await client.put(
            url,
            headers=headers,
            json={
                "message": f"feat(layout): set {position} to {slug}",
                "content": encoded,
                "sha": current_sha,
                "branch": "main",
            },
        )
        update_resp.raise_for_status()
```

**Step 5: Commit**

```bash
cd apps/backend-rag
git add backend/app/routers/intel.py
git commit -m "feat(intel): add homepage position control to publish endpoint"
```

---

### Task 4: Add position dropdown to newsroom UI

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
- Modify: `apps/mouth/src/lib/api/intelligence.api.ts`

**Step 1: Update intelligence API to pass position**

In `apps/mouth/src/lib/api/intelligence.api.ts`, change `publishItem` (line 241):

```typescript
  publishItem: async (
    type: "visa" | "news",
    id: string,
    position: string = "latest",
  ): Promise<PublishResponse> => {
    const endpoint = `/api/intel/staging/publish/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, "POST", {
      itemType: type,
      itemId: id,
      action: "publish",
      position,
    });

    try {
      const response = await api.request<PublishResponse>(endpoint, {
        method: "POST",
        body: JSON.stringify({ position }),
      });
```

**Step 2: Add position state and dropdown to newsroom page**

In `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`:

Add import at top:

```typescript
import { MapPin } from "lucide-react";
```

Add state after line 62 (after `const toast = useToast();`):

```typescript
const [publishPosition, setPublishPosition] = useState<Record<string, string>>(
  {},
);
```

Add a helper to get the position for an item:

```typescript
const getPosition = (id: string) => publishPosition[id] || "latest";
```

Replace the `handlePublish` function (lines 253-301) to pass position:

```typescript
const handlePublish = async (item: StagingItem) => {
  const position = getPosition(item.id);

  logger.info("Publishing item", {
    component: "NewsRoomPage",
    action: "publish_item",
    itemId: item.id,
    metadata: { title: item.title, position },
  });

  setPublishingIds((prev) => new Set(prev).add(item.id));

  try {
    const response = await intelligenceApi.publishItem(
      item.type,
      item.id,
      position,
    );

    logger.info("Item published successfully", {
      component: "NewsRoomPage",
      action: "publish_success",
      itemId: item.id,
      metadata: { published_url: response.published_url, position },
    });

    toast.success(
      "Published!",
      `"${response.title}" published${position !== "latest" ? ` to ${position.replace("_", " ")}` : ""}`,
    );

    loadNews();
  } catch (error) {
    logger.error(
      "Failed to publish item",
      { component: "NewsRoomPage", action: "publish_error", itemId: item.id },
      error as Error,
    );
    toast.error("Error", "Failed to publish article");
  } finally {
    setPublishingIds((prev) => {
      const next = new Set(prev);
      next.delete(item.id);
      return next;
    });
  }
};
```

**Step 3: Add position selector in card footer**

In the `<CardFooter>` section (around line 543), add a position dropdown BEFORE the Publish button:

```tsx
                <div className="flex flex-wrap gap-2 w-full">
                  {/* Position selector */}
                  <Select
                    value={getPosition(item.id)}
                    onValueChange={(value) =>
                      setPublishPosition((prev) => ({ ...prev, [item.id]: value }))
                    }
                  >
                    <SelectTrigger className="w-[140px]" title="Homepage position">
                      <MapPin className="w-3 h-3 mr-1" />
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
                  <Button
                    className="flex-1 gap-2 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white min-w-[100px]"
                    size="sm"
                    onClick={() => handlePublish(item)}
                    disabled={publishingIds.has(item.id)}
                  >
                    {/* ... existing publish button content ... */}
                  </Button>
```

Also add the same dropdown in the preview dialog (around line 664), before the "Publish Article" button:

```tsx
            <div className="flex gap-2 mt-6">
              <Select
                value={previewItem ? getPosition(previewItem.id) : "latest"}
                onValueChange={(value) =>
                  previewItem &&
                  setPublishPosition((prev) => ({
                    ...prev,
                    [previewItem.id]: value,
                  }))
                }
              >
                <SelectTrigger className="w-[160px]">
                  <MapPin className="w-3 h-3 mr-1" />
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
              <Button ... />
            </div>
```

**Step 4: Verify build**

```bash
cd apps/mouth && npm run build
```

**Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/intelligence/news-room/page.tsx apps/mouth/src/lib/api/intelligence.api.ts
git commit -m "feat(newsroom): add homepage position dropdown to publish flow"
```

---

### Task 5: Add position to bulk publish

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx:173-230`

**Step 1: Update bulk publish to use "latest" position**

In `handleBulkPublish`, change line 194:

```typescript
await intelligenceApi.publishItem(item.type, id, getPosition(id));
```

This allows each selected item to have its own position if set, defaulting to "latest".

**Step 2: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/intelligence/news-room/page.tsx
git commit -m "feat(newsroom): bulk publish respects per-item position selection"
```

---

### Task 6: End-to-end verification

**Step 1: Verify the full pipeline locally**

```bash
# 1. Check frontend builds
cd apps/mouth && npm run build

# 2. Check backend syntax
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.intel import publish_staging_item; print('OK')"

# 3. Verify homepage-layout.json is valid
python -c "import json; json.load(open('apps/mouth/src/content/homepage-layout.json')); print('OK')"
```

**Step 2: Manual test flow**

1. Open `kita.balizero.com/intelligence/news-room`
2. Select a position from the dropdown on any article card
3. Click "Publish"
4. Verify article appears at balizero.com/news in the chosen position
5. Verify `homepage-layout.json` was updated in GitHub

**Step 3: Final commit and push**

```bash
git push origin main
```

This triggers Vercel auto-deploy for frontend.

---

## Summary of Changes

| File                                                             | Action | Description                                      |
| ---------------------------------------------------------------- | ------ | ------------------------------------------------ |
| `apps/mouth/src/content/homepage-layout.json`                    | Create | JSON config mapping 8 positions to article slugs |
| `apps/mouth/src/app/(blog)/NewsPageClient.tsx`                   | Modify | Import layout config instead of hardcoded slugs  |
| `apps/backend-rag/backend/app/routers/intel.py`                  | Modify | Add position param + `update_homepage_layout()`  |
| `apps/mouth/src/lib/api/intelligence.api.ts`                     | Modify | Pass position in `publishItem()`                 |
| `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx` | Modify | Add position dropdown to card footer + preview   |

## Dependencies

- `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` — already configured as Fly.io secrets
- `httpx` — already in backend requirements
- Next.js JSON imports — natively supported, no config needed

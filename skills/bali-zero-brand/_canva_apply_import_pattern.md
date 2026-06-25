# Canva Apply via import-from-url — pattern dimostrato 2026-05-10

> **Status**: Manual procedure validated. Production runbook re-write deferred.
> **First successful run**: 2026-05-10 21:40 WITA, design `DAHJRpG2QIs` for KEP-71 SPT extension.
> **Why this exists**: the legacy `mcp__claude_ai_Canva__*` editing-transaction primitives
> (`start-editing-transaction`, `perform-editing-operations`, `commit-editing-transaction`)
> are NOT exposed by the current `canva-cloud` MCP server (22 tools, none of them transaction-
> based). The old runbook in `~/.claude/skills/canva-apply.md` is therefore non-functional
> and must be re-written when time allows.

## Manual procedure (validated)

Given a finished WR2 carousel at `apps/war-room/output/carousel/<slug>/slides/{1..N}.png`:

### Step 1 — Build single multi-page PDF from PNG slides

```python
from PIL import Image
import os
slides_dir = "~/Desktop/nuzantara/apps/war-room/output/carousel/<slug>/slides"
pngs = sorted([f for f in os.listdir(slides_dir)
               if f.endswith('.png') and not f.startswith('logo')],
              key=lambda x: int(x.split('.')[0]))
images = [Image.open(os.path.join(slides_dir, p)).convert('RGB') for p in pngs]
out_pdf = f"/tmp/<slug>.pdf"
images[0].save(out_pdf, save_all=True, append_images=images[1:],
               format='PDF', resolution=144.0)
```

Result: ~0.9 MB PDF for an 8-slide carousel.

### Step 2 — Upload PDF to Tigris bucket

```bash
/bin/zsh -lc '
  set -a
  source ~/.nuzantara-secrets.env
  set +a
  ~/Desktop/nuzantara/apps/backend-rag/.venv/bin/python << PYEOF
import os, boto3, time
ENDPOINT = "https://fly.storage.tigris.dev"
BUCKET = "nuzantara-warroom-images"
key = f"warroom/carousel-test/<slug>-{int(time.time())}.pdf"
s3 = boto3.client("s3", endpoint_url=ENDPOINT,
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
s3.upload_file("/tmp/<slug>.pdf", BUCKET, key,
               ExtraArgs={"ContentType": "application/pdf", "ACL": "public-read"})
print(f"https://{BUCKET}.fly.storage.tigris.dev/{key}")
PYEOF
'
```

**Critical gotcha**: `~/.nuzantara-secrets.env` does NOT use `export`. Without
`set -a` / `set +a` around the source, `AWS_ACCESS_KEY_ID` is not propagated
to the Python child and boto3 raises `KeyError`.

### Step 3 — Import into Canva via MCP

```
mcp__canva-cloud__import-design-from-url(
  url="<tigris-pdf-url>",
  name="<topic title>",
  user_intent="..."
)
```

Returns `{job: {status: success, result: {designs: [{id, urls: {edit_url, view_url}, page_count}]}}}`.

The `edit_url` and `view_url` are short-form (`canva.com/d/<slug>`) — NOT the
long-form `canva.com/design/<id>/edit`. Both resolve correctly.

### Step 4 — Move to Carousel folder

```
mcp__canva-cloud__move-item-to-folder(
  item_id="<design_id>",
  to_folder_id="FAHEwkTYduI",
  user_intent="..."
)
```

The hardcoded `FAHEwkTYduI` is the Carousel folder ID from `canva_pending.json`
template metadata.

### Step 5 — Persist outputs

Write `apps/war-room/output/canva/carousel_canva.json` with `status: applied`
and the design URLs. Append item to `human-review-queue.json` with
`state: applied_ready_for_damar` and `canva_url` set.

### Step 6 — Notify Damar

The queue server (`localhost:8765`) renders the queue UI. Damar opens
`http://localhost:8765/`, sees the item with `applied_ready_for_damar`,
clicks the Canva URL, opens it on his side, and publishes to IG manually.

Telegram bot integration for "Mark as Published" with IG URL form is a
future Phase E task — for now, Damar tells you verbally and you POST
`/api/mark-published` manually.

## Known limitations

- **Lossless but uneditable text**: PDF preserves exact 1080×1350 PNG render.
  Damar can't edit text inside Canva — he can only re-render from WR2 if a
  fix is needed. This is opposite to the old in-place pattern (where Canva
  was the editor of last resort). Trade-off accepted for now.
- **No template Phase 0/A/C reset semantics**: the import creates a fresh
  design every run, so template residue is irrelevant. The complexity of the
  old runbook is gone.
- **No element_id remap**: not needed — the design is built from scratch.
- **PDF size limit**: Canva accepts up to 25 MB. WR2 8-10 slide carousels are
  ~0.9-1.5 MB, well under.

## Next: formal runbook re-write

Replace `~/.claude/skills/canva-apply.md` with a runbook that:

1. Reads `canva_pending.json`.
2. Locates `slides/*.png` from `source_carousel_path`.
3. Runs Steps 1-5 above via shell + MCP.
4. Updates `pending` → `applied`.
5. Posts to queue server.

Estimated effort: 3h (scriptable in Python with claude `--mcp` invocation pattern).

## Memory ref

- decision_wr2_canva_pattern_shift_2026_05_10.md (importance 9)
- discovery_wr2_first_prod_publish_2026_05_10.md (importance 8)
- wr2-episodic-log.md entry 2026-05-10 kep71-spt-extension-test6-FIRSTPROD

# Canva Apply — Image Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `canva-apply` skill (Phase 0 + Phase C) to wipe `image_frame` elements with a Tigris-hosted transparent 1×1 PNG, eliminating template image residue between carousel runs.

**Architecture:** Add a constant `IMAGE_PLACEHOLDER_TRANSPARENT_URL` in `pending_builder.py`, expose it in the pending JSON, and update the markdown skill to upload it once per run + `update_fill` every `image_frame`. One-shot Tigris asset upload via existing `boto3` pattern reused from `wr2_image_generator._upload_to_tigris`.

**Tech Stack:** Python 3.11 (pending_builder), pytest, Tigris S3 (boto3), Markdown skill (canva-apply.md), Canva MCP tools (`upload-asset-from-url`, `perform-editing-operations` with `update_fill`).

**Spec:** `docs/superpowers/specs/2026-05-08-canva-apply-image-residue-cleanup.md` (commit `7b1823843`)

---

## File Structure

| File                                                                                  | Responsibility                                                                                        | Action             |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------ |
| `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`                 | Defines the pending JSON schema. Adds new constant + exposes it in `build_canva_pending` return dict. | Modify             |
| `apps/backend-rag/backend/services/canva_renderer/__init__.py`                        | Re-exports public API. Adds new constant to `__all__`.                                                | Modify             |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py` | Unit test that the constant flows through to the pending dict.                                        | Modify             |
| `~/.claude/skills/canva-apply.md`                                                     | The markdown skill Claude Desktop interprets. Phase 0 + Phase C extended with image_frame wipe.       | Modify             |
| `/tmp/upload_transparent_placeholder.py`                                              | One-shot script to upload `transparent-1x1.png` to Tigris. Discarded after use.                       | Create then delete |

The skill markdown is the operational source of truth — Phase 0 and Phase C edits are surgical insertions, not rewrites. The Python constant gives downstream tooling a single source of truth for the placeholder URL (so a future audit script or alt builder can reference it).

---

## Task 1: Generate transparent 1×1 PNG bytes

**Files:**

- No file changes. Verifies the binary blob we will upload.

**Why:** Before touching code, confirm the asset content. The smallest valid PNG with alpha channel and a single transparent pixel is 67 bytes (verified via Python `struct`). We need to know the exact bytes to upload and to assert content-length in the preflight curl.

- [ ] **Step 1: Generate the bytes via stdlib**

Run:

```bash
python3 -c "
import zlib, struct, sys

def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)  # 1x1 RGBA 8-bit
idat = zlib.compress(b'\x00\x00\x00\x00\x00')  # filter byte + RGBA(0,0,0,0)
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
sys.stdout.buffer.write(png)
" > /tmp/transparent-1x1.png
ls -la /tmp/transparent-1x1.png
file /tmp/transparent-1x1.png
```

Expected:

```
-rw-r--r--  1 nuzantara  wheel  67 May  8 09:30 /tmp/transparent-1x1.png
/tmp/transparent-1x1.png: PNG image data, 1 x 1, 8-bit/color RGBA, non-interlaced
```

- [ ] **Step 2: Verify it renders as transparent**

Run:

```bash
python3 -c "
from PIL import Image
im = Image.open('/tmp/transparent-1x1.png')
print('mode:', im.mode, 'size:', im.size, 'pixel(0,0):', im.getpixel((0,0)))
"
```

Expected:

```
mode: RGBA size: (1, 1) pixel(0,0): (0, 0, 0, 0)
```

- [ ] **Step 3: No commit (this is preflight)**

The PNG stays in `/tmp/` until Task 2 uploads it.

---

## Task 2: Upload transparent PNG to Tigris (one-shot)

**Files:**

- Create: `/tmp/upload_transparent_placeholder.py` (discarded after use)

**Why:** Reuse the Tigris S3 pattern from `wr2_image_generator._upload_to_tigris`. The asset must exist publicly before any code referencing its URL is committed — otherwise the first carousel run hits a 404.

- [ ] **Step 1: Create upload script**

Write file `/tmp/upload_transparent_placeholder.py`:

```python
"""One-shot: upload /tmp/transparent-1x1.png to Tigris template-assets path.

Reuses the boto3 pattern from scripts/wr2_image_generator._upload_to_tigris.
Idempotent — overwrites if the key already exists.
"""
import os
from pathlib import Path

import boto3

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
KEY = "warroom/template-assets/transparent-1x1.png"
SRC = Path("/tmp/transparent-1x1.png")

assert SRC.exists() and SRC.stat().st_size == 67, f"unexpected size: {SRC.stat().st_size}"

aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
assert aws_key and aws_secret, "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY must be set"

s3 = boto3.client(
    "s3",
    endpoint_url=TIGRIS_ENDPOINT,
    region_name="auto",
    aws_access_key_id=aws_key,
    aws_secret_access_key=aws_secret,
)
s3.put_object(
    Bucket=TIGRIS_BUCKET,
    Key=KEY,
    Body=SRC.read_bytes(),
    ContentType="image/png",
    ACL="public-read",
)
url = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev/{KEY}"
print(f"uploaded: {url}")
```

- [ ] **Step 2: Run the upload**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-secrets.env && set +a
python3 /tmp/upload_transparent_placeholder.py
```

Expected:

```
uploaded: https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/template-assets/transparent-1x1.png
```

- [ ] **Step 3: Verify the asset is publicly retrievable**

Run:

```bash
curl -sI https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/template-assets/transparent-1x1.png | head -5
```

Expected (order may vary):

```
HTTP/2 200
content-type: image/png
content-length: 67
```

- [ ] **Step 4: Cleanup the one-shot script**

Run:

```bash
rm -f /tmp/upload_transparent_placeholder.py /tmp/transparent-1x1.png
```

- [ ] **Step 5: No git commit needed**

The asset is now on Tigris. No code change yet.

---

## Task 3: Add `IMAGE_PLACEHOLDER_TRANSPARENT_URL` constant to pending_builder

**Files:**

- Modify: `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`
- Test: `apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py`

**Why:** Single source of truth for the placeholder URL. Downstream tools (audit scripts, future alt-builders) reference this constant rather than the literal URL string.

- [ ] **Step 1: Write the failing test**

Edit `apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py` and append at the end of the file:

```python
def test_image_placeholder_transparent_url_is_tigris_template_asset() -> None:
    """The placeholder URL must point at the Tigris template-assets path
    so canva-apply Phase 0 / C can wipe image_frames idempotently."""
    from backend.services.canva_renderer.pending_builder import (
        IMAGE_PLACEHOLDER_TRANSPARENT_URL,
    )
    assert IMAGE_PLACEHOLDER_TRANSPARENT_URL == (
        "https://nuzantara-warroom-images.fly.storage.tigris.dev/"
        "warroom/template-assets/transparent-1x1.png"
    )


def test_build_canva_pending_exposes_image_placeholder_url() -> None:
    """The pending JSON must carry the placeholder URL so the skill
    can pick it up without re-deriving it."""
    from backend.services.canva_renderer.pending_builder import (
        IMAGE_PLACEHOLDER_TRANSPARENT_URL,
        build_canva_pending,
    )
    pending = build_canva_pending(
        topic="test topic",
        tone="analitico",
        slides=_slides_fixture(),
    )
    assert pending["image_placeholder_url"] == IMAGE_PLACEHOLDER_TRANSPARENT_URL
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer/test_pending_builder.py::test_image_placeholder_transparent_url_is_tigris_template_asset -v
```

Expected: FAIL with `ImportError: cannot import name 'IMAGE_PLACEHOLDER_TRANSPARENT_URL'`.

- [ ] **Step 3: Add the constant + expose it in build_canva_pending**

Edit `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`. Find the `LEGIBILITY_ARMOR_URL` block (around line 30) and add immediately after it:

```python
# Transparent 1x1 PNG used by the canva-apply skill (Phase 0 + Phase C)
# to wipe every image_frame on the master template before applying the
# new carousel. Without this, non-hero slides keep whatever image was
# left over from the previous run (Bangkok skylines / mangrove placards
# / calendar timelines all observed in the Badung Horeka run 2026-05-08).
# Hosted as a static template asset; regenerate via the design plan
# task 1+2 if the URL ever changes.
IMAGE_PLACEHOLDER_TRANSPARENT_URL = (
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/"
    "warroom/template-assets/transparent-1x1.png"
)
```

Then find `build_canva_pending` (around line 197). In the return dict, add the new key right after `"folder_id": CAROUSEL_FOLDER_ID,`:

```python
        "image_placeholder_url": IMAGE_PLACEHOLDER_TRANSPARENT_URL,
```

The full return dict end state (relevant slice):

```python
    return {
        "template_design_id": TEMPLATE_DESIGN_ID,
        "folder_id": CAROUSEL_FOLDER_ID,
        "image_placeholder_url": IMAGE_PLACEHOLDER_TRANSPARENT_URL,
        "design_id": None,
        "design_url": None,
        "topic": topic,
        "tone": tone,
        # ... rest unchanged
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer/test_pending_builder.py -v
```

Expected: all tests in `test_pending_builder.py` PASS, including the two new ones.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer/pending_builder.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py
git commit -m "$(cat <<'EOF'
feat(canva_renderer): expose IMAGE_PLACEHOLDER_TRANSPARENT_URL

Adds the Tigris-hosted transparent 1x1 PNG URL as a constant in
pending_builder and surfaces it via build_canva_pending() so the
canva-apply skill (next commit) can pick it up without re-deriving.

Single source of truth for the asset that Phase 0 + Phase C use to
wipe image_frame elements on the master template — preventing image
residue from prior carousels (Bali Zero Badung Horeka run 2026-05-08
shipped 3 slides with bleed: Bangkok skyline, mangrove SHGB,
calendar timeline).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Re-export `IMAGE_PLACEHOLDER_TRANSPARENT_URL` from package `__init__`

**Files:**

- Modify: `apps/backend-rag/backend/services/canva_renderer/__init__.py`
- Test: `apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py`

**Why:** The package's `__all__` is the public API. Keep the new constant first-class so callers can `from backend.services.canva_renderer import IMAGE_PLACEHOLDER_TRANSPARENT_URL`.

- [ ] **Step 1: Write the failing test**

Append to `test_pending_builder.py`:

```python
def test_image_placeholder_url_reexported_from_package() -> None:
    """The constant must be reachable via the package-level import."""
    import backend.services.canva_renderer as pkg
    assert hasattr(pkg, "IMAGE_PLACEHOLDER_TRANSPARENT_URL")
    assert "IMAGE_PLACEHOLDER_TRANSPARENT_URL" in pkg.__all__
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer/test_pending_builder.py::test_image_placeholder_url_reexported_from_package -v
```

Expected: FAIL with `AttributeError: module 'backend.services.canva_renderer' has no attribute 'IMAGE_PLACEHOLDER_TRANSPARENT_URL'`.

- [ ] **Step 3: Update `__init__.py`**

Edit `apps/backend-rag/backend/services/canva_renderer/__init__.py`. Replace the import + `__all__` block (the entire bottom of the file) with:

```python
from backend.services.canva_renderer.pending_builder import (
    IMAGE_PLACEHOLDER_TRANSPARENT_URL,
    TEMPLATE_DESIGN_ID,
    TEMPLATE_SLOTS,
    build_canva_pending,
    slides_to_operations,
)

__all__ = [
    "IMAGE_PLACEHOLDER_TRANSPARENT_URL",
    "TEMPLATE_DESIGN_ID",
    "TEMPLATE_SLOTS",
    "build_canva_pending",
    "slides_to_operations",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer/test_pending_builder.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer/__init__.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py
git commit -m "$(cat <<'EOF'
feat(canva_renderer): re-export IMAGE_PLACEHOLDER_TRANSPARENT_URL

Adds the placeholder constant to the package __all__ so the rest of
the codebase can import it from the package root.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Extend `canva-apply` skill Phase 0 to wipe `image_frame` elements

**Files:**

- Modify: `~/.claude/skills/canva-apply.md`

**Why:** This is the operational fix. The skill currently wipes only richtext in Phase 0 — image_frames keep whatever was on the master from the prior run. Extension: upload the placeholder once, then `update_fill` every image_frame.

The skill is markdown prose interpreted by Claude Desktop. There is no programmatic test — coverage is the live E2E in Task 7.

- [ ] **Step 1: Edit Phase 0 in the skill**

Open `~/.claude/skills/canva-apply.md`. Find the Phase 0 block (starts with `## Phase 0 — PRE-RESET master template (DO THIS FIRST)`, ends right before `## Phase A`).

Replace step 5 (the line `5. Call \`commit-editing-transaction\` with \`transaction_id_prereset\`. Master template is now blank-text. Save \`prereset_count\` = number of elements wiped.`) with this expanded sequence:

```markdown
5. **Image-frame wipe (NEW 2026-05-08, SP-1 image residue cleanup).**
   Read `image_placeholder_url` from the pending JSON (always present
   from pending_builder >= 2026-05-08).

   a. Call `upload-asset-from-url` with the placeholder URL. Save the
   returned `asset_id` as `asset_id_blank`. If upload fails, log
   `⚠️ image-wipe upload failed: <reason>` and SKIP the rest of
   step 5 — proceed directly to step 6 with richtext-only wipe.
   Image bleed will persist for this run, but text content is
   correct.

   b. From the live template map built in step 3 (or from the same
   `start-editing-transaction` response from step 2 if you kept
   it), enumerate every element where `type == "image_frame"`.
   Build the list of `(page_index, element_id)` pairs. If the
   response uses a different type label, fall back to a regex
   match on the element type containing `image|frame|placeholder`.
   If still nothing matches, log `⚠️ no image_frame elements found`
   and skip the wipe (proceed to step 6).

   c. Call `perform-editing-operations` (a SECOND call within the
   same `transaction_id_prereset`) with:
   - `transaction_id = transaction_id_prereset`
   - `user_intent = "wipe image_frame elements with transparent placeholder"`
   - `pages = [1..live_pages]`
   - `operations`: one `{"type":"update_fill","element_id":<id>,"asset_type":"image","asset_id":<asset_id_blank>,"alt_text":"blank placeholder"}` per every `image_frame` you enumerated.

   d. Track failures: if more than 50% of `image_frame` `update_fill`
   ops fail, ABORT Phase 0 with `ERROR phase0_image_wipe_failed:
{n_failed}/{n_total}`. Do NOT proceed to Phase A on a partially
   wiped master — the next run's Phase 0 will retry from a clean
   transaction. Otherwise log `🪂 image-wipe skip page {N} elem
{id[:12]}: {err}` per failed element and continue.

   Save `prereset_image_count` = number of image_frames successfully
   wiped (0 if upload failed in step 5a).

6. Call `commit-editing-transaction` with `transaction_id_prereset`.
   Master template is now blank-text + blank-images. Save
   `prereset_count` = number of richtext elements wiped (from step 4).
```

(Note: the pre-existing step numbered "5" in the file was the commit. We renumbered: image-wipe is now step 5, commit becomes step 6. The OLD numbers 6, 7, 8, 9, 10 in Phase A (`Call \`start-editing-transaction\` on \`template_design_id\` AGAIN ...`, etc.) must be bumped to 7, 8, 9, 10, 11. Keep step numbers stable across phases for log readability.)

Renumber Phase A steps 6 → 7, 7 → 8, 8 → 9, 9 → 10, 10 → 11. Renumber Phase B steps 11 → 12, 12 → 13. Renumber Phase C steps 13 → 14, 14 → 15, 15 → 16, 16 → 17. Renumber Phase D steps 17 → 18, 18 → 19.

- [ ] **Step 2: Add Phase C image wipe (defense-in-depth)**

Find the Phase C block (starts with `## Phase C — Reset master template AGAIN`). Locate step 15 (now renumbered) which currently reads `Call \`perform-editing-operations\`: replace all enumerated richtexts with " ". Save \`postreset_count\`.`. Replace it with:

```markdown
15. Call `perform-editing-operations` on `transaction_id_postreset`:
    replace all enumerated richtexts with `" "`. Save `postreset_count`.

15a. **Image-frame wipe (NEW 2026-05-08, SP-1 defense-in-depth).**
If `asset_id_blank` from Phase 0 step 5a is still in scope, reuse
it. Otherwise call `upload-asset-from-url` again with
`image_placeholder_url` from the pending JSON.

    Enumerate `image_frame` elements (same logic as Phase 0 step 5b).
    Call `perform-editing-operations` (second call within
    `transaction_id_postreset`): one `update_fill` per element with
    `asset_id_blank`.

    Failure handling: NON-blocking. Log `⚠️ phase_c image wipe
    failed: <n>/<total>` and proceed to step 16. The next run's
    Phase 0 will clean residue.

    Save `postreset_image_count` = number of image_frames wiped.
```

- [ ] **Step 3: Update Phase D persist outputs to surface the new counters**

Find Phase D step 18 (now renumbered, currently step 17 in the file). In the `carousel_canva.json` payload object, add two fields right after `"prereset_count": <n elements wiped in Phase 0>,`:

```markdown
       "prereset_image_count": <n image_frames wiped in Phase 0>,
```

And right after `"postreset_count": <n elements wiped in Phase C>,`:

```markdown
       "postreset_image_count": <n image_frames wiped in Phase C>,
```

- [ ] **Step 4: Update the final response line**

Find the line `Respond with: \`APPLIED <new_design_id> | PRERESET <p> | REMAPS <r> | DROPPED <d> | POSTRESET <q>\``. Change it to:

```markdown
Respond with: `APPLIED <new_design_id> | PRERESET <p>+<pi> | REMAPS <r> | DROPPED <d> | POSTRESET <q>+<qi>`
where `<pi>` is `prereset_image_count` and `<qi>` is `postreset_image_count`.
```

- [ ] **Step 5: Update Hard rules to mention Phase 0 image wipe**

In the `## Hard rules` section, find the line:

```markdown
- **Phase 0 is MANDATORY**. Always pre-reset before applying. If Phase 0 commit fails, abort the whole flow with `ERROR phase0_failed: <reason>` — do NOT attempt Phase A on a dirty master.
```

Append immediately after it as a new bullet:

```markdown
- **Phase 0 image wipe is best-effort**. The richtext wipe (steps 3-4) is mandatory; the image_frame wipe (step 5) is best-effort and degrades gracefully on upload failure (text content still correct, image bleed persists for this run only). Hard abort only triggers when >50% of `update_fill` ops fail (step 5d) — that signals the template structure has changed.
```

- [ ] **Step 6: Verify the skill markdown still parses cleanly**

The skill is loaded by Claude Desktop on next session. There's no offline lint, but we can sanity-check the rendered structure:

```bash
cd ~/Desktop/nuzantara
grep -c "^##" ~/.claude/skills/canva-apply.md
grep -c "^- \[ \]\|^[0-9]\+\." ~/.claude/skills/canva-apply.md
```

Expected: same number of `##` headings as before edit (5: Phase 0, A, B, C, D), and the numbered steps are continuous (no gaps in 1, 2, 3, ..., 19).

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara
# The skill lives outside the repo at ~/.claude/skills/, but if it's
# git-tracked there, commit there. Otherwise it's tracked via dotfiles.
# Check first:
git -C ~/.claude rev-parse --git-dir 2>/dev/null && cd ~/.claude && \
  git add skills/canva-apply.md && \
  git commit -m "feat(canva-apply): Phase 0 + Phase C wipe image_frame elements

Adds image residue cleanup to the canva-apply skill. Phase 0 uploads
a transparent 1x1 PNG once and update_fills every image_frame on the
master template; Phase C does the same defense-in-depth at the end of
the run.

Eliminates the bug observed in Badung Horeka run 2026-05-08 where
non-hero slides 3, 5, 7 inherited image assets from prior carousels
(Bangkok skyline, mangrove SHGB, calendar timeline).

Phase 0 image wipe is best-effort — degrades gracefully on upload
failure. Hard abort only on >50% update_fill failures.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" \
|| echo "skill not git-tracked at ~/.claude — manual backup recommended"
```

If `~/.claude` is not a git repo, take a manual snapshot:

```bash
cp ~/.claude/skills/canva-apply.md \
   ~/.claude/skills/canva-apply.md.pre-sp1-image-wipe-2026-05-08.bak
```

---

## Task 6: Re-build pending JSON for Badung Horeka draft

**Files:**

- Read: `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`
- Write: `/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json` (live path the skill reads)

**Why:** The skill reads the canonical pending JSON at the path `apps/war-room/output/canva/canva_pending.json`. After Tasks 3-4 the builder emits the new `image_placeholder_url` field; we need to regenerate the pending JSON for the Badung Horeka draft so the skill (Task 7) picks it up.

The Badung Horeka draft `a3fd4007-52a6-47cc-be54-8452d8b2d530` is at status `drafts_imaged` with `slides_json` already populated. We rebuild the pending without re-running draft_generator or image_generator.

- [ ] **Step 1: Reset the draft's `canva_*` columns so apply will re-process it**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-secrets.env && set +a
PROXY_DSN="$(python3 -c "
import os
from urllib.parse import urlparse, urlunparse
v = os.environ['DATABASE_URL']
p = urlparse(v)
print(urlunparse(p._replace(netloc=f'{p.username}:{p.password}@localhost:15432')))
")"

python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(dsn='$PROXY_DSN', command_timeout=15)
    try:
        await conn.execute('''
            UPDATE war_room_drafts
               SET canva_design_id = NULL,
                   canva_edit_url  = NULL,
                   canva_view_url  = NULL,
                   canva_applied_at = NULL,
                   status = 'drafts_imaged',
                   updated_at = NOW()
             WHERE id = \$1::uuid
        ''', 'a3fd4007-52a6-47cc-be54-8452d8b2d530')
        row = await conn.fetchrow(
            'SELECT id, status, canva_edit_url FROM war_room_drafts WHERE id = \$1::uuid',
            'a3fd4007-52a6-47cc-be54-8452d8b2d530'
        )
        print(dict(row))
    finally:
        await conn.close()
asyncio.run(main())
"
```

Expected:

```
{'id': UUID('a3fd4007-52a6-47cc-be54-8452d8b2d530'), 'status': 'drafts_imaged', 'canva_edit_url': None}
```

- [ ] **Step 2: Re-build the pending JSON**

Write `/tmp/rebuild_badung_pending.py`:

```python
import asyncio, json, os, re, sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg

REPO = Path(os.path.expanduser("~/Desktop/nuzantara"))
sys.path.insert(0, str(REPO / "apps" / "backend-rag"))
from backend.services.canva_renderer.pending_builder import build_canva_pending

DRAFT_ID = "a3fd4007-52a6-47cc-be54-8452d8b2d530"
OUT_PATH = REPO / "apps/war-room/output/canva/canva_pending.json"

with open(os.path.expanduser("~/.nuzantara-secrets.env")) as f:
    text = f.read()
m = re.search(
    r'^(?:export\s+)?DATABASE_URL\s*=\s*[\'"]?([^\'"\n]+)[\'"]?\s*$',
    text, re.MULTILINE,
)
v = m.group(1)
p = urlparse(v)
proxy_dsn = urlunparse(p._replace(netloc=f"{p.username}:{p.password}@localhost:15432"))


async def main():
    conn = await asyncpg.connect(dsn=proxy_dsn, command_timeout=15)
    try:
        row = await conn.fetchrow(
            "SELECT id, topic, register, slides_json::text AS sj "
            "FROM war_room_drafts WHERE id = $1::uuid", DRAFT_ID,
        )
        sj = json.loads(row["sj"])
        slides = sj.get("slides", sj if isinstance(sj, list) else [])
        pending = build_canva_pending(
            topic=row["topic"], tone=row["register"] or "analitico",
            slides=slides,
        )
        pending["draft_id"] = str(row["id"])
        pending["status"] = "pending"
        OUT_PATH.write_text(json.dumps(pending, indent=2, ensure_ascii=False))
        print("wrote", OUT_PATH)
        print("image_placeholder_url:", pending.get("image_placeholder_url"))
        print("operations_count:", pending["operations_count"])
        print("hero_slide_indices:", pending["hero_slide_indices"])
    finally:
        await conn.close()


asyncio.run(main())
```

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python3 /tmp/rebuild_badung_pending.py
```

Expected:

```
wrote /Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json
image_placeholder_url: https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/template-assets/transparent-1x1.png
operations_count: 19
hero_slide_indices: [1, 4, 8, 11]
```

- [ ] **Step 3: Verify the field is present**

Run:

```bash
jq '{topic, status, image_placeholder_url, hero_slide_indices, operations_count}' \
  ~/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json
```

Expected: object containing `image_placeholder_url` set to the Tigris URL, `status: "pending"`, and the same operations_count as before (19).

- [ ] **Step 4: Cleanup the one-shot script**

```bash
rm -f /tmp/rebuild_badung_pending.py
```

- [ ] **Step 5: No commit (the pending JSON is regenerated on every run; if it is gitignored, do not stage it)**

Verify it is gitignored:

```bash
cd ~/Desktop/nuzantara && git check-ignore apps/war-room/output/canva/canva_pending.json && echo "ignored OK" || echo "WARNING: not ignored — investigate before committing"
```

Expected: `apps/war-room/output/canva/canva_pending.json` followed by `ignored OK`.

---

## Task 7: Live E2E — re-apply Badung Horeka with the patched skill

**Files:**

- Run: `scripts/wr2_canva_desktop_apply.py --draft-id a3fd4007-52a6-47cc-be54-8452d8b2d530`

**Why:** The skill is markdown — only Claude Desktop interpreting it during a real `wr2_canva_desktop_apply` run can validate behavior. This is the acceptance test.

**Operator preconditions** (do NOT skip):

- Claude Desktop is running and you have a fresh chat ready.
- Your laptop's MAX OAuth token has quota (the prior run on 2026-05-08 09:13 hit quota mid-flow).
- Do NOT click the keyboard, mouse, or change focus during the run — AppleScript paste verifies frontmost on every keystroke.

- [ ] **Step 1: Confirm kill-switch is on**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-secrets.env && set +a
PROXY_DSN="$(python3 -c "
import os
from urllib.parse import urlparse, urlunparse
v = os.environ['DATABASE_URL']
p = urlparse(v)
print(urlunparse(p._replace(netloc=f'{p.username}:{p.password}@localhost:15432')))
")"

python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(dsn='$PROXY_DSN', command_timeout=15)
    try:
        v = await conn.fetchval(
            \"SELECT value FROM system_settings WHERE key = 'wr2_canva_desktop_apply_enabled'\"
        )
        print('kill_switch:', v)
    finally:
        await conn.close()
asyncio.run(main())
"
```

Expected: `kill_switch: true`. If `false` or missing, set it via SQL UPDATE before proceeding.

- [ ] **Step 2: Trigger the run**

Run:

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-secrets.env && set +a
PROXY_DSN="$(python3 -c "
import os
from urllib.parse import urlparse, urlunparse
v = os.environ['DATABASE_URL']
p = urlparse(v)
print(urlunparse(p._replace(netloc=f'{p.username}:{p.password}@localhost:15432')))
")"
DATABASE_URL="$PROXY_DSN" python3 ~/Desktop/nuzantara/scripts/wr2_canva_desktop_apply.py \
  --draft-id a3fd4007-52a6-47cc-be54-8452d8b2d530
```

Expected interactive flow (3-10 minutes, do not touch the machine):

- AppleScript activates Claude Desktop.
- Cmd+N opens a new chat.
- `/canva-apply` is pasted.
- Skill runs Phase 0 → Phase A → Phase B → Phase C → Phase D.
- Script polls `apps/war-room/output/canva/carousel_canva.json` for the new design URL.

Final stdout includes a line like:

```
Draft a3fd4007-... → status=rendered (canva_edit_url=https://www.canva.com/design/...)
```

If the run aborts (quota exhausted, focus stolen, MCP timeout), retry — Phase 0 is idempotent.

- [ ] **Step 3: Inspect the new carousel_canva.json**

```bash
jq '{
  design_id, design_url,
  prereset_count, prereset_image_count,
  postreset_count, postreset_image_count,
  remaps_applied, ops_dropped, applied_at
}' ~/Desktop/nuzantara/apps/war-room/output/canva/carousel_canva.json
```

Expected: `prereset_image_count` and `postreset_image_count` are integers >= 4 (slides 1, 4, 8, 11 each have an image_frame; non-hero slides may have additional ones). `applied_at` is a fresh ISO timestamp from this run.

- [ ] **Step 4: Open the design in Canva and visually verify**

Open the `design_url` from step 3 in a browser. Page through all 11 slides. For each one, check the image_frame status:

| Slide                     | Hero? | Expected image                                            |
| ------------------------- | ----- | --------------------------------------------------------- |
| 1 (cover)                 | Yes   | Codex aerial shot of waste bins at dusk (slide-01-...png) |
| 2                         | No    | TRANSPARENT (template background visible)                 |
| 3 (41%)                   | No    | TRANSPARENT — NOT Bangkok/KL/Dubai skylines               |
| 4 (TPA Suwung)            | Yes   | Codex landfill golden hour (slide-04-...png)              |
| 5 (organic waste)         | No    | TRANSPARENT — NOT mangrove/SHGB placards                  |
| 6 (single-use plastic)    | No    | TRANSPARENT — NOT the woman in blazer                     |
| 7 (reporting duty)        | No    | TRANSPARENT — NOT calendar timeline                       |
| 8 (inspectors walking)    | Yes   | Codex two-person uniform corridor (slide-08-...png)       |
| 9 (where rule comes from) | No    | TRANSPARENT                                               |
| 10 (price tag)            | No    | TRANSPARENT                                               |
| 11 (CTA)                  | Yes   | Codex hands-on-documents (slide-11-...png)                |

If any non-hero slide STILL shows the prior carousel's image, the wipe failed for that page — check `carousel_canva.json.prereset_image_count` and the run logs.

- [ ] **Step 5: Export PDF and compare to the buggy 2026-05-08 export**

Use Canva's PDF export. Compare side-by-side with `~/Downloads/WR2 Automation standard (6).pdf`. Slides 3, 5, 7 must differ — same headlines, different (transparent) backgrounds.

- [ ] **Step 6: No commit (this is verification, not implementation)**

Run results live in `carousel_canva.json` (gitignored). If the visual check passes, mark Task 7 done.

---

## Task 8: Regression check on a previously-applied draft

**Files:**

- No code changes. Re-runs an existing draft to confirm hero-image flow still works.

**Why:** Defense against breaking what already works. Pick the Golden Visa draft `de69f035-7467-42e8-9ed4-95f600dfca90` (still in the queue at canva_edit_url=NULL when last checked).

- [ ] **Step 1: Verify the draft is still eligible**

Run (same DSN setup as Task 7 step 1):

```bash
python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(dsn='$PROXY_DSN', command_timeout=15)
    try:
        row = await conn.fetchrow(
            \"SELECT id, status, canva_edit_url FROM war_room_drafts WHERE id = '\\\$1::uuid'\",
            'de69f035-7467-42e8-9ed4-95f600dfca90'
        )
        print(dict(row))
    finally:
        await conn.close()
asyncio.run(main())
"
```

Expected: `status` in `{drafts_imaged, drafts}` and `canva_edit_url` is None. If not, skip this task — Golden Visa got applied while we were working.

- [ ] **Step 2: Rebuild Golden Visa pending JSON**

Edit `/tmp/rebuild_badung_pending.py` (or write a sibling file) and change `DRAFT_ID = "de69f035-7467-42e8-9ed4-95f600dfca90"`. Run it. Expected:

```
wrote /Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json
image_placeholder_url: https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/template-assets/transparent-1x1.png
```

- [ ] **Step 3: Apply via the same script**

Run:

```bash
DATABASE_URL="$PROXY_DSN" python3 ~/Desktop/nuzantara/scripts/wr2_canva_desktop_apply.py \
  --draft-id de69f035-7467-42e8-9ed4-95f600dfca90
```

- [ ] **Step 4: Visual check on Golden Visa hero slides**

Open the resulting design URL. Confirm the Golden Visa hero slides (per `hero_slide_indices` in carousel_canva.json) still show their generated hero images — the placeholder should have been overwritten in Phase A. Non-hero slides should be transparent.

- [ ] **Step 5: No commit**

Same as Task 7. If Golden Visa hero slides also look right, the regression check passes.

---

## Task 9: Push branch and open PR

**Files:**

- Push to: `origin/feat/wr2-manual-topic-override-2026-05-08` (existing branch from PR #539, where SP-1 commits should land — or a new sibling branch)

**Why:** Get the change reviewed + into main. PR #539 already collects the manual-override + draft-id flags from earlier in the session. SP-1 work fits on the same branch as a third related WR2 quality fix.

- [ ] **Step 1: Confirm the commits from Tasks 3 + 4 + 5 are on the right branch**

```bash
cd ~/Desktop/nuzantara
git log --oneline -5
git branch --show-current
```

Expected: current branch is `feat/wr2-manual-topic-override-2026-05-08` (or a sibling branch you intentionally created), and recent commits include the three from Tasks 3-5.

If commits ended up on a different branch (sibling automation hijack — see scar `cicatrix-scars.md` "Untracked files lost"), cherry-pick them to the right branch:

```bash
# Suppose commits are on `wrong-branch` and we want them on `feat/wr2-manual-topic-override-2026-05-08`:
git log --oneline wrong-branch -3  # note the SHAs
git checkout feat/wr2-manual-topic-override-2026-05-08
git cherry-pick <sha-task-3> <sha-task-4> <sha-task-5>
```

- [ ] **Step 2: Push**

```bash
cd ~/Desktop/nuzantara
git push origin feat/wr2-manual-topic-override-2026-05-08
```

- [ ] **Step 3: Update PR #539 description**

```bash
cd ~/Desktop/nuzantara
gh pr view 539 --json body --jq .body > /tmp/pr539-body.md
# Append SP-1 section
cat >> /tmp/pr539-body.md <<'EOF'

---

## SP-1 update (2026-05-08): image residue cleanup

Adds `IMAGE_PLACEHOLDER_TRANSPARENT_URL` to pending_builder + extends
canva-apply skill Phase 0 + Phase C to wipe image_frame elements.
Eliminates the bug observed in Badung Horeka run 2026-05-08 where
non-hero slides 3, 5, 7 inherited stale image assets.

Verified live: re-applied draft a3fd4007-... → slides 3, 5, 7 now
show transparent template background. Hero slides 1, 4, 8, 11 still
present and on-topic.

Spec: docs/superpowers/specs/2026-05-08-canva-apply-image-residue-cleanup.md
Plan: docs/superpowers/plans/2026-05-08-canva-apply-image-residue-cleanup.md
EOF
gh pr edit 539 --body-file /tmp/pr539-body.md
rm -f /tmp/pr539-body.md
```

- [ ] **Step 4: Save a memory entry**

Run:

```bash
~/.claude/scripts/mem save discovery "SP-1 image residue cleanup: canva-apply Phase 0 + Phase C now wipe image_frame with Tigris transparent 1x1 PNG. Verified live on Badung Horeka draft a3fd4007. Pattern reusable for any template residue. Spec+plan at docs/superpowers/{specs,plans}/2026-05-08-canva-apply-image-residue-cleanup.md" 8
```

---

## Self-Review

**Spec coverage:**

- ✅ Goal (extend Phase 0+C to wipe image_frame) → Tasks 5, 6, 7
- ✅ Architecture (transparent PNG on Tigris, expose URL via builder) → Tasks 1, 2, 3, 4
- ✅ Idempotency of placeholder upload → Task 5 step 2 (Phase C reuses asset_id_blank if in scope)
- ✅ Hero priority (Phase A overwrites placeholder) → Task 7 step 4 (regression check on hero slides)
- ✅ image_frame filter → Task 5 step 1 sub-step b (regex fallback for type label)
- ✅ Error handling: upload fails → Task 5 step 1 sub-step a
- ✅ Error handling: >50% update_fill fail → Task 5 step 1 sub-step d
- ✅ Phase C non-blocking → Task 5 step 2 last paragraph
- ✅ Asset preflight curl → Task 2 step 3
- ✅ Live E2E acceptance → Task 7
- ✅ Regression on prior draft → Task 8

**Placeholder scan:** No "TBD"/"TODO" in the plan. Every code block is concrete. Every command has expected output.

**Type consistency:**

- Constant name: `IMAGE_PLACEHOLDER_TRANSPARENT_URL` (consistent across Tasks 3, 4, 5)
- Variable name in skill: `asset_id_blank` (consistent in Task 5 steps 1 + 2)
- Counter names: `prereset_image_count` and `postreset_image_count` (consistent in Task 5 steps 1d, 2, 3, and Task 7 step 3)
- Function call: `update_fill` (consistent across all skill steps)

No issues found.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-08-canva-apply-image-residue-cleanup.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for the Python tasks (3, 4) which have clear pass/fail tests. Tasks 5 (skill markdown), 7 (live E2E), 8 (regression) need YOU at the keyboard — they involve Claude Desktop GUI automation.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Same caveat about the GUI tasks.

Which approach?

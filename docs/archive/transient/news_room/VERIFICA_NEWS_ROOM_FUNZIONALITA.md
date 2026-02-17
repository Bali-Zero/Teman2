# Verifica Funzionalità News Room

**Data:** 2026-01-24  
**Status:** ⚠️ FUNZIONALITÀ MANCANTI IDENTIFICATE

---

## ✅ FUNZIONALITÀ IMPLEMENTATE

### 1. Preview Articolo

- ✅ **Frontend:** Button "VIEW" nella card articolo
- ✅ **Frontend:** Dialog con preview completo
- ✅ **Backend:** `GET /api/intel/staging/preview/{type}/{item_id}`
- ✅ **API Client:** `intelligenceApi.getPreview(type, id)`

### 2. Publish Articolo

- ✅ **Frontend:** Button "Publish" nella card articolo
- ✅ **Frontend:** Bulk publish per articoli selezionati
- ✅ **Backend:** `POST /api/intel/staging/publish/{type}/{item_id}`
- ✅ **API Client:** `intelligenceApi.publishItem(type, id)`

---

## ❌ FUNZIONALITÀ MANCANTI

### 1. Editing Articolo (Titolo, Contenuto, Categoria)

**Status:** ❌ NON IMPLEMENTATO

**Cosa serve:**

#### Backend:

- ❌ Endpoint `PUT /api/intel/staging/{type}/{item_id}` per modificare:
  - `title` (titolo)
  - `content` (contenuto markdown)
  - `category` (categoria)

#### Frontend API Client:

- ❌ `intelligenceApi.editItem(type, id, updates)` function

#### Frontend UI:

- ❌ Component `ArticleEditor.tsx` per editing inline o dialog
- ❌ Button "Edit" nella card articolo
- ❌ Form con campi: title, content (textarea markdown), category (select)

---

### 2. Cover Image Upload

**Status:** ❌ NON IMPLEMENTATO

**Cosa serve:**

#### Backend:

- ❌ Endpoint `POST /api/intel/staging/{type}/{item_id}/cover` per upload:
  - Accetta `cover_image_base64` (base64 encoded)
  - Accetta `cover_image_filename` (opzionale)
  - Salva cover image in `data/staging/{type}/covers/{item_id}.{ext}`
  - Aggiorna staging JSON con `cover_image` path

#### Frontend API Client:

- ❌ `intelligenceApi.uploadCoverImage(type, id, base64, filename)` function

#### Frontend UI:

- ❌ Component `CoverImageUploader.tsx` con:
  - Drag & drop area
  - File picker button
  - Preview immagine caricata
  - Button "Upload Cover" nella card articolo

---

## 📋 PIANO IMPLEMENTAZIONE

### STEP 1: Backend - Edit Endpoint

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Aggiungere:**

```python
class EditStagingItemRequest(BaseModel):
    """Request body for editing staging item"""
    title: str | None = None
    content: str | None = None
    category: str | None = None

@router.put("/api/intel/staging/{type}/{item_id}")
async def edit_staging_item(
    type: str,
    item_id: str,
    request: EditStagingItemRequest
):
    """
    Edit staging item (title, content, category).

    Only updates provided fields (partial update).
    """
    # Load existing staging item
    data = staging_service.load_staging_item(type, item_id)
    if not data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update only provided fields
    if request.title:
        data["title"] = request.title
    if request.content:
        data["content"] = request.content
    if request.category:
        data["category"] = request.category

    # Save updated staging item
    staging_service.save_staging_item(type, item_id, data)

    return {
        "success": True,
        "message": "Item updated successfully",
        "id": item_id,
        "updated_fields": {
            k: v for k, v in request.dict(exclude_unset=True).items()
        }
    }
```

---

### STEP 2: Backend - Cover Image Upload Endpoint

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Aggiungere:**

```python
class CoverImageUploadRequest(BaseModel):
    """Request body for cover image upload"""
    cover_image_base64: str = Field(..., description="Base64 encoded image")
    cover_image_filename: str | None = Field(None, description="Image filename (optional)")

@router.post("/api/intel/staging/{type}/{item_id}/cover")
async def upload_cover_image(
    type: str,
    item_id: str,
    request: CoverImageUploadRequest
):
    """
    Upload cover image for staging item.

    Saves image to data/staging/{type}/covers/{item_id}.{ext}
    Updates staging JSON with cover_image path.
    """
    import base64
    from pathlib import Path

    # Load existing staging item
    data = staging_service.load_staging_item(type, item_id)
    if not data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Decode base64 image
    try:
        image_data = base64.b64decode(request.cover_image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    # Determine file extension
    filename = request.cover_image_filename or f"{item_id}.jpg"
    ext = Path(filename).suffix or ".jpg"

    # Save cover image
    covers_dir = staging_service.get_staging_dir(type) / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    cover_path = covers_dir / f"{item_id}{ext}"
    cover_path.write_bytes(image_data)

    # Update staging JSON
    data["cover_image"] = str(cover_path.relative_to(staging_service.get_staging_dir(type)))
    staging_service.save_staging_item(type, item_id, data)

    return {
        "success": True,
        "message": "Cover image uploaded successfully",
        "id": item_id,
        "cover_image_path": str(cover_path),
        "cover_image_url": f"/api/intel/staging/{type}/{item_id}/cover/preview"
    }
```

---

### STEP 3: Frontend API Client

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Aggiungere:**

```typescript
export interface EditStagingItemRequest {
  title?: string;
  content?: string;
  category?: string;
}

export interface CoverImageUploadRequest {
  cover_image_base64: string;
  cover_image_filename?: string;
}

export const intelligenceApi = {
  // ... existing methods ...

  /**
   * Edit staging item (title, content, category)
   */
  editItem: async (
    type: "visa" | "news",
    id: string,
    updates: EditStagingItemRequest,
  ): Promise<{ success: boolean; message: string; id: string }> => {
    const endpoint = `/api/intel/staging/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, "PUT", {
      itemType: type,
      itemId: id,
      action: "edit",
    });

    try {
      const response = await api.request<{
        success: boolean;
        message: string;
        id: string;
      }>(endpoint, {
        method: "PUT",
        body: JSON.stringify(updates),
      });
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        action: "edit",
        metadata: { success: response.success },
      });

      logger.userAction("edit_item", type, id);

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, {
        itemType: type,
        itemId: id,
        action: "edit",
      });
      throw error;
    }
  },

  /**
   * Upload cover image for staging item
   */
  uploadCoverImage: async (
    type: "visa" | "news",
    id: string,
    base64: string,
    filename?: string,
  ): Promise<{
    success: boolean;
    message: string;
    id: string;
    cover_image_path: string;
  }> => {
    const endpoint = `/api/intel/staging/${type}/${id}/cover`;
    const startTime = performance.now();

    logger.apiCall(endpoint, "POST", {
      itemType: type,
      itemId: id,
      action: "upload_cover",
    });

    try {
      const response = await api.request<{
        success: boolean;
        message: string;
        id: string;
        cover_image_path: string;
      }>(endpoint, {
        method: "POST",
        body: JSON.stringify({
          cover_image_base64: base64,
          cover_image_filename: filename,
        }),
      });
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        action: "upload_cover",
        metadata: { success: response.success },
      });

      logger.userAction("upload_cover_image", type, id);

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, {
        itemType: type,
        itemId: id,
        action: "upload_cover",
      });
      throw error;
    }
  },
};
```

---

### STEP 4: Frontend UI - ArticleEditor Component

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`

**Creare nuovo componente:**

```typescript
'use client';

import { useState } from 'react';
import { intelligenceApi, StagingItem } from '@/lib/api/intelligence.api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { Loader2, Edit } from 'lucide-react';

interface ArticleEditorProps {
  item: StagingItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

export function ArticleEditor({ item, open, onOpenChange, onSaved }: ArticleEditorProps) {
  const [title, setTitle] = useState(item.title);
  const [content, setContent] = useState(item.content || '');
  const [category, setCategory] = useState(item.category || 'news');
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const handleSave = async () => {
    setSaving(true);
    try {
      await intelligenceApi.editItem(item.type, item.id, {
        title,
        content,
        category,
      });
      toast.success('Saved!', 'Article updated successfully');
      onSaved();
      onOpenChange(false);
    } catch (error) {
      toast.error('Error', 'Failed to update article');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit className="h-5 w-5" />
            Edit Article
          </DialogTitle>
          <DialogDescription>Modify article title, content, and category</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title"
            />
          </div>

          <div>
            <Label htmlFor="category">Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="category">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="immigration">Immigration</SelectItem>
                <SelectItem value="property">Property</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="news">News</SelectItem>
                <SelectItem value="visa">Visa</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="content">Content (Markdown)</Label>
            <textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full min-h-[400px] p-3 border rounded-md font-mono text-sm"
              placeholder="Article content in Markdown format..."
            />
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving} className="gap-2">
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Edit className="h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

### STEP 5: Frontend UI - CoverImageUploader Component

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Creare nuovo componente:**

```typescript
'use client';

import { useState, useRef } from 'react';
import { intelligenceApi, StagingItem } from '@/lib/api/intelligence.api';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { Loader2, Upload, Image as ImageIcon, X } from 'lucide-react';

interface CoverImageUploaderProps {
  item: StagingItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded: () => void;
}

export function CoverImageUploader({
  item,
  open,
  onOpenChange,
  onUploaded,
}: CoverImageUploaderProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const handleFileSelect = (selectedFile: File) => {
    if (!selectedFile.type.startsWith('image/')) {
      toast.error('Invalid file', 'Please select an image file');
      return;
    }

    setFile(selectedFile);

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreview(e.target?.result as string);
    };
    reader.readAsDataURL(selectedFile);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleUpload = async () => {
    if (!file || !preview) {
      toast.error('No file', 'Please select an image first');
      return;
    }

    setUploading(true);
    try {
      // Convert to base64
      const base64 = preview.split(',')[1]; // Remove data:image/...;base64, prefix
      const filename = file.name;

      await intelligenceApi.uploadCoverImage(item.type, item.id, base64, filename);
      toast.success('Uploaded!', 'Cover image uploaded successfully');
      onUploaded();
      onOpenChange(false);
      setFile(null);
      setPreview(null);
    } catch (error) {
      toast.error('Error', 'Failed to upload cover image');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Upload Cover Image
          </DialogTitle>
          <DialogDescription>Upload a cover image for this article</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-[var(--accent)] transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            {preview ? (
              <div className="relative">
                <img
                  src={preview}
                  alt="Preview"
                  className="max-h-64 mx-auto rounded-lg object-cover"
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPreview(null);
                    setFile(null);
                  }}
                  className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="h-12 w-12 mx-auto text-[var(--foreground-muted)]" />
                <p className="text-[var(--foreground-muted)]">
                  Drag & drop an image here, or click to select
                </p>
                <p className="text-sm text-[var(--foreground-muted)]">
                  Supports: JPG, PNG, WebP
                </p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];
                if (selectedFile) {
                  handleFileSelect(selectedFile);
                }
              }}
            />
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploading} className="gap-2">
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Upload Cover Image
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

### STEP 6: Integrare nella News Room Page

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:**

1. Importare i nuovi componenti:

```typescript
import { ArticleEditor } from "./components/ArticleEditor";
import { CoverImageUploader } from "./components/CoverImageUploader";
```

2. Aggiungere state per editing e cover upload:

```typescript
const [editingItem, setEditingItem] = useState<StagingItem | null>(null);
const [coverUploadItem, setCoverUploadItem] = useState<StagingItem | null>(
  null,
);
```

3. Aggiungere buttons nella card articolo (CardFooter):

```typescript
<Button
  variant="outline"
  size="sm"
  onClick={() => setEditingItem(item)}
  className="gap-2"
>
  <Edit className="h-4 w-4" />
  Edit
</Button>

<Button
  variant="outline"
  size="sm"
  onClick={() => setCoverUploadItem(item)}
  className="gap-2"
>
  <ImageIcon className="h-4 w-4" />
  Cover
</Button>
```

4. Aggiungere i dialog components:

```typescript
{editingItem && (
  <ArticleEditor
    item={editingItem}
    open={!!editingItem}
    onOpenChange={(open) => !open && setEditingItem(null)}
    onSaved={() => {
      loadNews();
      setEditingItem(null);
    }}
  />
)}

{coverUploadItem && (
  <CoverImageUploader
    item={coverUploadItem}
    open={!!coverUploadItem}
    onOpenChange={(open) => !open && setCoverUploadItem(null)}
    onUploaded={() => {
      loadNews();
      setCoverUploadItem(null);
    }}
  />
)}
```

---

## ✅ CHECKLIST IMPLEMENTAZIONE

### Backend

- [ ] Creare `EditStagingItemRequest` Pydantic model
- [ ] Creare endpoint `PUT /api/intel/staging/{type}/{item_id}`
- [ ] Creare `CoverImageUploadRequest` Pydantic model
- [ ] Creare endpoint `POST /api/intel/staging/{type}/{item_id}/cover`
- [ ] Testare endpoint con Postman/curl

### Frontend API Client

- [ ] Aggiungere `editItem()` function
- [ ] Aggiungere `uploadCoverImage()` function
- [ ] Testare API calls

### Frontend UI

- [ ] Creare `ArticleEditor.tsx` component
- [ ] Creare `CoverImageUploader.tsx` component
- [ ] Integrare nella News Room page
- [ ] Aggiungere buttons "Edit" e "Cover" nelle card
- [ ] Testare UI flow completo

---

## 🎯 RISULTATO FINALE

Quando un articolo arriva nella News Room:

1. ✅ **Preview:** Button "VIEW" → Dialog con preview completo
2. ✅ **Edit:** Button "Edit" → Dialog per modificare title, content, category
3. ✅ **Cover Image:** Button "Cover" → Dialog per upload cover image (drag & drop)
4. ✅ **Publish:** Button "Publish" → Approva e pubblica automaticamente

---

**Status:** ⚠️ MANCANO EDITING E COVER IMAGE UPLOAD  
**Next:** Implementare funzionalità mancanti seguendo il piano sopra

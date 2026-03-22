"use client";

import { useState } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { Loader2, Edit } from "lucide-react";
import { logger } from "@/lib/logger";
import { AutoResizeTextarea } from "@/components/ui/auto-resize-textarea";

interface ArticleEditorProps {
  item: StagingItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

export function ArticleEditor({
  item,
  open,
  onOpenChange,
  onSaved,
}: ArticleEditorProps) {
  const [title, setTitle] = useState(item.title);
  const [content, setContent] = useState(item.content || "");
  const [category, setCategory] = useState(item.category || "news");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const handleSave = async () => {
    if (!title.trim()) {
      toast.error("Error", "Title is required");
      return;
    }

    setSaving(true);
    try {
      await intelligenceApi.editItem(item.type, item.id, {
        title: title.trim(),
        content: content.trim(),
        category,
      });
      toast.success("Saved!", "Article updated successfully");
      onSaved();
      onOpenChange(false);
    } catch (error) {
      toast.error("Error", "Failed to update article");
      logger.error(
        "Failed to edit article",
        {
          component: "ArticleEditor",
          action: "edit_article",
          itemId: item.id,
        },
        error as Error,
      );
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
          <DialogDescription>
            Modify article title, content, and category
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <div>
            <Label htmlFor="title">Title *</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title"
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="category">Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="category" className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="visas">Visas</SelectItem>
                <SelectItem value="property">Property</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="news">News</SelectItem>
                <SelectItem value="visa">Visa</SelectItem>
                <SelectItem value="tax">Taxes</SelectItem>
                <SelectItem value="living">Living</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="content">Content (Markdown)</Label>
            <AutoResizeTextarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full min-h-[400px] p-3 border rounded-md font-mono text-sm mt-1"
              placeholder="Article content in Markdown format..."
            />
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="gap-2"
          >
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

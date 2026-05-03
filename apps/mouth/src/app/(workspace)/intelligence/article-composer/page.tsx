"use client";

import { useState, useEffect, useRef } from "react";
import {
  articlesApi,
  ComposeRequest,
  EnrichedArticle,
  PublishRequest,
} from "@/lib/api/articles.api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { AutoResizeTextarea } from "@/components/ui/auto-resize-textarea";
import { renderMiniMarkdown, fileToBase64 } from "@/lib/utils";
import { safeMiniMarkdown } from "@/lib/utils/safe-html";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  Sparkles,
  FileText,
  Globe,
  ImageIcon,
  X,
  Save,
  Pencil,
  Copy,
  Download,
  Send,
} from "lucide-react";

const CATEGORIES = [
  { value: "business", label: "Business & Company" },
  { value: "visas", label: "Visas & Visas" },
  { value: "tax", label: "Taxes" },
  { value: "property", label: "Property & Real Estate" },
  { value: "living", label: "Living" },
  { value: "trends", label: "Trends & Insights" },
  { value: "legal", label: "Legal Updates" },
];

const POSITIONS = [
  { value: "normal", label: "Normal Article" },
  { value: "secondary", label: "Secondary Featured" },
  { value: "main_featured", label: "Main Featured (Homepage Hero)" },
];

const DRAFT_KEY = "bz_composer_draft_v2";

// Warm Depth glassmorphism reusable styles
const cardClass = "rounded-2xl border overflow-hidden";
const cardStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  borderColor: "rgba(255,255,255,0.07)",
};
const inputClass =
  "w-full rounded-xl border px-3 py-2.5 text-[13px] outline-none transition-all";
const inputBaseStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  borderColor: "rgba(255,255,255,0.07)",
  color: "var(--bz-text-1)",
};
const inputFocusStyle: React.CSSProperties = {
  ...inputBaseStyle,
  borderColor: "var(--bz-accent)",
};

export default function ArticleComposerPage() {
  const toast = useToast();

  // --- STATE ---
  const [statusLoading, setStatusLoading] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [publishConfigured, setPublishConfigured] = useState(false);

  // Form State
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("business");
  const [sourceUrl, setSourceUrl] = useState("");
  const [author, setAuthor] = useState("Marketing Team");

  // Media State
  const [coverImage, setCoverImage] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Process State
  const [loading, setLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiCost, setApiCost] = useState<number>(0);

  // Data State
  const [result, setResult] = useState<EnrichedArticle | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedResult, setEditedResult] = useState<EnrichedArticle | null>(
    null,
  );

  // Publish State
  const [position, setPosition] = useState<
    "normal" | "secondary" | "main_featured"
  >("normal");
  const [customSlug, setCustomSlug] = useState("");
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);

  // Focus tracking for inputs
  const [focusedInput, setFocusedInput] = useState<string | null>(null);

  const getInputStyle = (name: string): React.CSSProperties =>
    focusedInput === name ? inputFocusStyle : inputBaseStyle;

  // --- LIFECYCLE ---

  useEffect(() => {
    logger.componentMount("ArticleComposerPage");

    const init = async () => {
      setStatusLoading(true);
      try {
        const [composeStatus, publishStatus] = await Promise.all([
          articlesApi.getStatus().catch(() => ({ configured: false })),
          articlesApi.getPublishStatus().catch(() => ({ configured: false })),
        ]);
        setConfigured(composeStatus.configured);
        setPublishConfigured(publishStatus.configured);
      } catch (err) {
        logger.error(
          "API Check failed",
          { component: "ArticleComposerPage" },
          err as Error,
        );
      } finally {
        setStatusLoading(false);
      }
    };
    init();

    // Load Draft
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.title) setTitle(draft.title);
        if (draft.content) setContent(draft.content);
        if (draft.category) setCategory(draft.category);
        if (draft.source) setSourceUrl(draft.source);
        if (draft.author) setAuthor(draft.author);
      }
    } catch (e) {
      logger.warn(
        "Failed to load draft from localStorage",
        { component: "ArticleComposerPage" },
        e as Error,
      );
    }
  }, []);

  // Autosave Draft
  useEffect(() => {
    const timer = setTimeout(() => {
      if (title || content) {
        try {
          localStorage.setItem(
            DRAFT_KEY,
            JSON.stringify({
              title,
              content,
              category,
              source: sourceUrl,
              author,
            }),
          );
        } catch (e) {
          /* Silent fail quota exceeded */
        }
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [title, content, category, sourceUrl, author]);

  // --- HANDLERS ---

  const handleCompose = async () => {
    if (!title.trim() || !content.trim()) {
      toast.error("Missing Data", "Please enter both a title and content.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      logger.info("Starting article composition", {
        component: "ArticleComposerPage",
        metadata: { category },
      });
      const req: ComposeRequest = {
        title,
        content,
        category,
        source_url: sourceUrl || undefined,
        author,
      };

      const res = await articlesApi.compose(req);

      if (res.success && res.article) {
        setResult(res.article);
        setApiCost(res.api_cost_cents);
        toast.success(
          "Article Enriched!",
          `Cost: $${(res.api_cost_cents / 100).toFixed(4)}`,
        );
        localStorage.removeItem(DRAFT_KEY);
      } else {
        throw new Error(res.error || "Unknown error");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      logger.error(
        "Composition failed",
        { component: "ArticleComposerPage" },
        err as Error,
      );
      toast.error("Enrichment Failed", msg);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!result) return;
    setPublishing(true);
    const articleToPublish = isEditing && editedResult ? editedResult : result;

    try {
      logger.info("Publishing article", {
        component: "ArticleComposerPage",
        metadata: { position },
      });
      const req: PublishRequest = {
        article: articleToPublish,
        position,
        slug: customSlug || undefined,
      };
      if (coverImage) {
        req.cover_image_base64 = await fileToBase64(coverImage);
        req.cover_image_filename = coverImage.name;
      }

      const res = await articlesApi.publish(req);
      if (res.success) {
        setPublishedUrl(res.article_url || "#");
        toast.success("Published!", "Article is live.");
      } else {
        throw new Error(res.error);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Publish failed";
      logger.error(
        "Publish failed",
        { component: "ArticleComposerPage" },
        err as Error,
      );
      toast.error("Publish Error", msg);
    } finally {
      setPublishing(false);
    }
  };

  // Helper: Images
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Invalid File", "Not an image.");
      return;
    }
    setCoverImage(file);
    const reader = new FileReader();
    reader.onloadend = () => setCoverPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const removeCoverImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCoverImage(null);
    setCoverPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Helper: Editing
  const startEditing = () => {
    if (result) {
      setEditedResult(JSON.parse(JSON.stringify(result)));
      setIsEditing(true);
    }
  };

  const saveEdits = () => {
    if (editedResult) {
      setResult(editedResult);
      setIsEditing(false);
      toast.success("Saved", "Changes updated locally.");
    }
  };

  const cancelEditing = () => {
    setEditedResult(null);
    setIsEditing(false);
  };

  const updateEditedField = (path: string, value: unknown) => {
    if (!editedResult) return;
    const newResult = JSON.parse(JSON.stringify(editedResult));
    const parts = path.split(".");
    let current = newResult;
    for (let i = 0; i < parts.length - 1; i++) {
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    setEditedResult(newResult);
  };

  // Helper: Copy/Export
  const handleCopyJson = () => {
    const data = isEditing ? editedResult : result;
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    toast.success("Copied", "JSON copied to clipboard");
  };

  const handleExportJson = () => {
    const data = isEditing ? editedResult : result;
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `article-${(data.headline || "draft").slice(0, 30).replace(/\s+/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // --- RENDER ---

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

  const activeArticle = isEditing && editedResult ? editedResult : result;

  return (
    <div className="flex flex-col lg:flex-row gap-5 min-h-0">
      {/* ──── LEFT PANEL: Raw Content Input ──── */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className={cardClass} style={cardStyle}>
          {/* Left panel header */}
          <div
            className="flex items-center justify-between px-4 py-3 border-b"
            style={{ borderColor: "rgba(255,255,255,0.06)" }}
          >
            <div className="flex items-center gap-2.5">
              <FileText
                className="w-4 h-4"
                style={{ color: "var(--bz-accent)" }}
              />
              <span
                className="text-[13px] font-medium"
                style={{ color: "var(--bz-text-1)" }}
              >
                Raw Content
              </span>
            </div>
            <div className="flex items-center gap-2.5">
              <div
                className={`h-2 w-2 rounded-full ${configured ? "bg-emerald-500" : "bg-red-500"}`}
              />
              {apiCost > 0 && (
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium border"
                  style={{
                    color: "var(--bz-accent)",
                    borderColor: "rgba(212,132,90,0.3)",
                    background: "rgba(212,132,90,0.08)",
                  }}
                >
                  ${(apiCost / 100).toFixed(4)}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-4 p-4">
            {/* Title */}
            <div className="flex flex-col gap-1">
              <label
                className="text-[11px] font-medium"
                style={{ color: "var(--bz-text-2)" }}
              >
                Article Title <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Es. New KITAS Rules..."
                className={inputClass}
                style={getInputStyle("title")}
                onFocus={() => setFocusedInput("title")}
                onBlur={() => setFocusedInput(null)}
              />
            </div>

            {/* Content */}
            <div className="flex flex-col gap-1">
              <label
                className="text-[11px] font-medium"
                style={{ color: "var(--bz-text-2)" }}
              >
                Raw Content <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <AutoResizeTextarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Incolla contenuto..."
                className={`${inputClass} min-h-[140px] resize-none`}
                style={getInputStyle("content")}
                onFocus={() => setFocusedInput("content")}
                onBlur={() => setFocusedInput(null)}
              />
              <div
                className="text-right text-[11px]"
                style={{ color: "var(--bz-text-2)" }}
              >
                {content.length}/8000 chars
              </div>
            </div>

            {/* Category */}
            <div className="flex flex-col gap-1">
              <label
                className="text-[11px] font-medium"
                style={{ color: "var(--bz-text-2)" }}
              >
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={`${inputClass} appearance-none cursor-pointer`}
                style={getInputStyle("category")}
                onFocus={() => setFocusedInput("category")}
                onBlur={() => setFocusedInput(null)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Source URL + Author */}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label
                  className="text-[11px] font-medium"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Source URL
                </label>
                <input
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  className={inputClass}
                  style={getInputStyle("sourceUrl")}
                  onFocus={() => setFocusedInput("sourceUrl")}
                  onBlur={() => setFocusedInput(null)}
                  placeholder="https://..."
                />
              </div>
              <div className="flex flex-col gap-1">
                <label
                  className="text-[11px] font-medium"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Author
                </label>
                <input
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  className={inputClass}
                  style={getInputStyle("author")}
                  onFocus={() => setFocusedInput("author")}
                  onBlur={() => setFocusedInput(null)}
                />
              </div>
            </div>

            {/* Cover Image */}
            <div className="flex flex-col gap-1">
              <label
                className="text-[11px] font-medium"
                style={{ color: "var(--bz-text-2)" }}
              >
                Cover Image (optional)
              </label>
              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                className="hidden"
                onChange={handleImageSelect}
              />
              {!coverPreview ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed p-4 text-center transition-colors hover:bg-white/[0.02]"
                  style={{ borderColor: "rgba(255,255,255,0.1)" }}
                >
                  <ImageIcon
                    className="h-5 w-5"
                    style={{ color: "var(--bz-text-2)" }}
                  />
                  <div
                    className="text-[11px]"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    Click per caricare (1200x630)
                  </div>
                </div>
              ) : (
                <div
                  className="relative overflow-hidden rounded-xl border"
                  style={{ borderColor: "rgba(255,255,255,0.07)" }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element --
                      blob:/data: preview cannot use next/image; explicit
                      dimensions prevent CLS on first paint. */}
                  <img
                    src={coverPreview}
                    alt="Article cover preview"
                    width={1200}
                    height={630}
                    className="h-[180px] w-full object-cover"
                  />
                  <button
                    type="button"
                    onClick={removeCoverImage}
                    aria-label="Remove cover image"
                    className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/80 text-white hover:bg-red-900/80"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Error state */}
            {error && (
              <div
                className="rounded-xl border px-3 py-2.5 text-[12px]"
                style={{
                  background: "rgba(239,68,68,0.08)",
                  backdropFilter: "blur(12px)",
                  WebkitBackdropFilter: "blur(12px)",
                  borderColor: "rgba(239,68,68,0.3)",
                  color: "#fca5a5",
                }}
              >
                {error}
              </div>
            )}

            {/* Compose button */}
            <button
              onClick={handleCompose}
              disabled={loading || !configured}
              className="group mt-2 flex w-full items-center justify-center gap-2 rounded-full border-none px-4 py-2.5 text-[13px] font-medium text-white transition-all hover:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background:
                  loading || !configured
                    ? "rgba(255,255,255,0.06)"
                    : "linear-gradient(135deg, var(--bz-accent), #c06a3a)",
                boxShadow:
                  loading || !configured
                    ? "none"
                    : "0 8px 24px rgba(212,132,90,0.35)",
                color: loading || !configured ? "var(--bz-text-2)" : "#fff",
              }}
            >
              {loading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {loading ? "Enriching with Claude..." : "Compose Executive Brief"}
            </button>
          </div>
        </div>
      </div>

      {/* ──── Vertical divider ──── */}
      <div
        className="hidden lg:block w-px self-stretch"
        style={{ background: "rgba(255,255,255,0.06)" }}
      />

      {/* ──── RIGHT PANEL: Preview / Result ──── */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className={cardClass} style={cardStyle}>
          {/* Right panel header */}
          <div
            className="flex items-center justify-between px-4 py-3 border-b"
            style={{ borderColor: "rgba(255,255,255,0.06)" }}
          >
            <div className="flex items-center gap-2.5">
              <Sparkles
                className="w-4 h-4"
                style={{ color: "var(--bz-accent)" }}
              />
              <span
                className="text-[13px] font-medium"
                style={{ color: "var(--bz-text-1)" }}
              >
                Executive Brief Preview
              </span>
            </div>
            {activeArticle && (
              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={saveEdits}
                      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all"
                      style={{
                        color: "var(--bz-accent)",
                        border: "1px solid rgba(212,132,90,0.4)",
                        background: "rgba(212,132,90,0.1)",
                      }}
                    >
                      <Save size={11} /> Save
                    </button>
                    <button
                      onClick={cancelEditing}
                      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all"
                      style={{
                        color: "#fca5a5",
                        border: "1px solid rgba(239,68,68,0.3)",
                        background: "rgba(239,68,68,0.08)",
                      }}
                    >
                      <X size={11} /> Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={startEditing}
                    className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all hover:bg-white/[0.04]"
                    style={{
                      color: "var(--bz-text-2)",
                      border: "1px solid rgba(255,255,255,0.07)",
                    }}
                  >
                    <Pencil size={11} /> Edit
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="p-4 flex flex-col gap-5 min-h-[400px]">
            {!activeArticle ? (
              /* Empty / placeholder state */
              <div
                className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed p-8 text-center"
                style={{ borderColor: "rgba(255,255,255,0.1)" }}
              >
                <div
                  className="mb-4 rounded-full p-4"
                  style={{ background: "rgba(255,255,255,0.04)" }}
                >
                  <Sparkles
                    className="h-8 w-8"
                    style={{ color: "var(--bz-text-2)" }}
                  />
                </div>
                <h3
                  className="text-[14px] font-medium"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  AI Preview
                </h3>
                <p
                  className="mt-1 max-w-xs text-[12px]"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Fill in the raw content to generate the brief.
                </p>
              </div>
            ) : (
              <>
                {/* ── Headline & Summary ── */}
                <div className="flex flex-col gap-2">
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium mb-1"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    Headline & Summary
                  </div>
                  {isEditing ? (
                    <div className="flex flex-col gap-2">
                      <AutoResizeTextarea
                        value={activeArticle.headline}
                        onChange={(e) =>
                          updateEditedField("headline", e.target.value)
                        }
                        className={`${inputClass} text-[16px] font-bold min-h-[50px] resize-none`}
                        style={getInputStyle("headline")}
                        onFocus={() => setFocusedInput("headline")}
                        onBlur={() => setFocusedInput(null)}
                      />
                      <AutoResizeTextarea
                        value={activeArticle.ai_summary}
                        onChange={(e) =>
                          updateEditedField("ai_summary", e.target.value)
                        }
                        className={`${inputClass} min-h-[70px] resize-none`}
                        style={getInputStyle("ai_summary")}
                        onFocus={() => setFocusedInput("ai_summary")}
                        onBlur={() => setFocusedInput(null)}
                      />
                    </div>
                  ) : (
                    <div>
                      <h2
                        className="text-[18px] font-semibold leading-[1.2]"
                        style={{ color: "var(--bz-text-1)" }}
                      >
                        {activeArticle.headline}
                      </h2>
                      <p
                        className="mt-1 text-[13px]"
                        style={{ color: "var(--bz-text-2)" }}
                      >
                        {activeArticle.ai_summary}
                      </p>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    <span
                      className="rounded-full border px-2 py-0.5 text-[11px]"
                      style={{
                        borderColor: "rgba(255,255,255,0.1)",
                        background: "rgba(255,255,255,0.04)",
                        color: "var(--bz-text-2)",
                      }}
                    >
                      {activeArticle.category}
                    </span>
                    <span
                      className="rounded-full border px-2 py-0.5 text-[11px]"
                      style={{
                        borderColor: "rgba(255,255,255,0.1)",
                        background: "rgba(255,255,255,0.04)",
                        color: "var(--bz-text-2)",
                      }}
                    >
                      Relevance: {activeArticle.relevance_score}/100
                    </span>
                  </div>
                </div>

                {/* ── TL;DR ── */}
                <div className="flex flex-col gap-2">
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    TL;DR
                  </div>
                  {isEditing ? (
                    <div className="grid gap-2 text-[12px]">
                      <div className="grid grid-cols-2 gap-2">
                        <select
                          value={activeArticle.tldr.should_worry}
                          onChange={(e) =>
                            updateEditedField(
                              "tldr.should_worry",
                              e.target.value,
                            )
                          }
                          className={`${inputClass} appearance-none cursor-pointer`}
                          style={getInputStyle("tldr_worry")}
                          onFocus={() => setFocusedInput("tldr_worry")}
                          onBlur={() => setFocusedInput(null)}
                        >
                          <option>Yes</option>
                          <option>No</option>
                          <option>Maybe</option>
                        </select>
                        <select
                          value={activeArticle.tldr.risk_level}
                          onChange={(e) =>
                            updateEditedField("tldr.risk_level", e.target.value)
                          }
                          className={`${inputClass} appearance-none cursor-pointer`}
                          style={getInputStyle("tldr_risk")}
                          onFocus={() => setFocusedInput("tldr_risk")}
                          onBlur={() => setFocusedInput(null)}
                        >
                          <option>Low</option>
                          <option>Medium</option>
                          <option>High</option>
                        </select>
                      </div>
                      <AutoResizeTextarea
                        value={activeArticle.tldr.what}
                        onChange={(e) =>
                          updateEditedField("tldr.what", e.target.value)
                        }
                        className={`${inputClass} min-h-[60px] resize-none`}
                        style={getInputStyle("tldr_what")}
                        onFocus={() => setFocusedInput("tldr_what")}
                        onBlur={() => setFocusedInput(null)}
                        placeholder="What"
                      />
                      <input
                        value={activeArticle.tldr.who}
                        onChange={(e) =>
                          updateEditedField("tldr.who", e.target.value)
                        }
                        className={inputClass}
                        style={getInputStyle("tldr_who")}
                        onFocus={() => setFocusedInput("tldr_who")}
                        onBlur={() => setFocusedInput(null)}
                        placeholder="Who"
                        aria-label="Who"
                      />
                      <input
                        value={activeArticle.tldr.when}
                        onChange={(e) =>
                          updateEditedField("tldr.when", e.target.value)
                        }
                        className={inputClass}
                        style={getInputStyle("tldr_when")}
                        onFocus={() => setFocusedInput("tldr_when")}
                        onBlur={() => setFocusedInput(null)}
                        placeholder="When"
                        aria-label="When"
                      />
                    </div>
                  ) : (
                    <div className="text-[12px]">
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <div>
                          <span style={{ color: "var(--bz-text-2)" }}>
                            Worry:{" "}
                          </span>
                          <span
                            className={
                              activeArticle.tldr.should_worry === "Yes"
                                ? "text-[#fecaca]"
                                : activeArticle.tldr.should_worry === "No"
                                  ? "text-[#bbf7d0]"
                                  : "text-[#fed7aa]"
                            }
                          >
                            {activeArticle.tldr.should_worry}
                          </span>
                        </div>
                        <div>
                          <span style={{ color: "var(--bz-text-2)" }}>
                            Risk:{" "}
                          </span>
                          <span
                            className={
                              activeArticle.tldr.risk_level === "High"
                                ? "text-[#fecaca]"
                                : activeArticle.tldr.risk_level === "Low"
                                  ? "text-[#bbf7d0]"
                                  : "text-[#fed7aa]"
                            }
                          >
                            {activeArticle.tldr.risk_level}
                          </span>
                        </div>
                      </div>
                      <div className="space-y-1 text-[13px]">
                        <div>
                          <strong style={{ color: "var(--bz-text-1)" }}>
                            What:
                          </strong>{" "}
                          {activeArticle.tldr.what}
                        </div>
                        <div>
                          <strong style={{ color: "var(--bz-text-1)" }}>
                            Who:
                          </strong>{" "}
                          {activeArticle.tldr.who}
                        </div>
                        <div>
                          <strong style={{ color: "var(--bz-text-1)" }}>
                            When:
                          </strong>{" "}
                          {activeArticle.tldr.when}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* ── Facts ── */}
                <div className="flex flex-col gap-2">
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    The Facts
                  </div>
                  {isEditing ? (
                    <AutoResizeTextarea
                      value={activeArticle.facts}
                      onChange={(e) =>
                        updateEditedField("facts", e.target.value)
                      }
                      className={`${inputClass} min-h-[120px] resize-none`}
                      style={getInputStyle("facts")}
                      onFocus={() => setFocusedInput("facts")}
                      onBlur={() => setFocusedInput(null)}
                    />
                  ) : (
                    <div
                      className="text-[13px] leading-relaxed whitespace-pre-line"
                      style={{ color: "var(--bz-text-1)" }}
                      dangerouslySetInnerHTML={safeMiniMarkdown(
                        renderMiniMarkdown(activeArticle.facts),
                      )}
                    />
                  )}
                </div>

                {/* ── Bali Zero Take ── */}
                <div className="flex flex-col gap-2">
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    Bali Zero Take
                  </div>
                  <div className="flex flex-col gap-3 text-[13px]">
                    {["hidden_insight", "our_analysis", "our_advice"].map(
                      (key) => {
                        const val = (activeArticle.bali_zero_take as any)[key];
                        return (
                          <div key={key}>
                            <strong
                              className="block mb-1 capitalize"
                              style={{ color: "var(--bz-text-1)" }}
                            >
                              {key.replace("_", " ")}
                            </strong>
                            {isEditing ? (
                              <AutoResizeTextarea
                                value={val}
                                onChange={(e) =>
                                  updateEditedField(
                                    `bali_zero_take.${key}`,
                                    e.target.value,
                                  )
                                }
                                className={`${inputClass} min-h-[60px] resize-none`}
                                style={getInputStyle(`bzt_${key}`)}
                                onFocus={() => setFocusedInput(`bzt_${key}`)}
                                onBlur={() => setFocusedInput(null)}
                              />
                            ) : (
                              <div style={{ color: "var(--bz-text-2)" }}>
                                {val}
                              </div>
                            )}
                          </div>
                        );
                      },
                    )}
                  </div>
                </div>

                {/* ── Next Steps ── */}
                <div className="flex flex-col gap-2">
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    Next Steps
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
                    {["expat", "investor"].map((type) => (
                      <div key={type}>
                        <div
                          className="font-medium mb-1 capitalize"
                          style={{ color: "var(--bz-text-1)" }}
                        >
                          For {type}s
                        </div>
                        {isEditing ? (
                          <AutoResizeTextarea
                            value={activeArticle.next_steps[
                              type as "expat" | "investor"
                            ].join("\n")}
                            onChange={(e) =>
                              updateEditedField(
                                `next_steps.${type}`,
                                e.target.value.split("\n"),
                              )
                            }
                            className={`${inputClass} min-h-[100px] resize-none`}
                            style={getInputStyle(`ns_${type}`)}
                            onFocus={() => setFocusedInput(`ns_${type}`)}
                            onBlur={() => setFocusedInput(null)}
                            placeholder="One per line..."
                          />
                        ) : (
                          <ul className="space-y-1">
                            {activeArticle.next_steps[
                              type as "expat" | "investor"
                            ].map((s, i) => (
                              <li key={i} className="flex gap-2 items-start">
                                <span
                                  className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                                  style={{ background: "var(--bz-accent)" }}
                                />
                                <span
                                  dangerouslySetInnerHTML={safeMiniMarkdown(
                                    renderMiniMarkdown(s),
                                  )}
                                />
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── AI Tags ── */}
                <div
                  className="mt-2 pt-3 border-t"
                  style={{ borderColor: "rgba(255,255,255,0.06)" }}
                >
                  <div
                    className="flex items-center gap-1.5 text-[12px] font-medium mb-2"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--bz-accent)" }}
                    />
                    AI Tags
                  </div>
                  {isEditing ? (
                    <input
                      value={activeArticle.ai_tags.join(", ")}
                      aria-label="AI Tags"
                      onChange={(e) =>
                        updateEditedField(
                          "ai_tags",
                          e.target.value.split(",").map((s) => s.trim()),
                        )
                      }
                      className={inputClass}
                      style={getInputStyle("ai_tags")}
                      onFocus={() => setFocusedInput("ai_tags")}
                      onBlur={() => setFocusedInput(null)}
                    />
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {activeArticle.ai_tags.map((tag, i) => (
                        <span
                          key={i}
                          className="rounded-full border px-2 py-0.5 text-[11px]"
                          style={{
                            borderColor: "rgba(255,255,255,0.1)",
                            background: "rgba(255,255,255,0.04)",
                            color: "var(--bz-text-2)",
                          }}
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* ── Publish + Footer actions ── */}
                {publishConfigured && (
                  <div
                    className="rounded-xl border p-3.5 flex flex-col gap-3 mt-2"
                    style={{
                      background: "rgba(77,184,122,0.04)",
                      borderColor: "rgba(77,184,122,0.2)",
                    }}
                  >
                    <div
                      className="flex items-center gap-1.5 text-[13px] font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      <Globe
                        size={14}
                        style={{ color: "var(--bz-green, #4db87a)" }}
                      />
                      <span>Publish to Site</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <label
                          className="text-[11px]"
                          style={{ color: "var(--bz-text-2)" }}
                        >
                          Position
                        </label>
                        <Select
                          value={position}
                          onValueChange={(v) =>
                            setPosition(
                              v as "normal" | "secondary" | "main_featured",
                            )
                          }
                          disabled={isEditing}
                        >
                          <SelectTrigger
                            className="h-8 text-[12px] rounded-xl"
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
                      </div>
                      <div className="flex flex-col gap-1">
                        <label
                          className="text-[11px]"
                          style={{ color: "var(--bz-text-2)" }}
                        >
                          Slug
                        </label>
                        <input
                          value={customSlug}
                          onChange={(e) => setCustomSlug(e.target.value)}
                          disabled={isEditing}
                          className={inputClass}
                          style={getInputStyle("slug")}
                          onFocus={() => setFocusedInput("slug")}
                          onBlur={() => setFocusedInput(null)}
                          placeholder="auto-generated-slug"
                        />
                      </div>
                    </div>
                    <button
                      onClick={handlePublish}
                      disabled={publishing || isEditing}
                      className="mt-1 w-full rounded-full py-1.5 text-[12px] font-medium transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
                      style={{
                        background: "var(--bz-green, #4db87a)",
                        color: "#052e16",
                      }}
                    >
                      {publishing ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Send size={12} />
                      )}
                      {publishing ? "Publishing..." : "Publish Article"}
                    </button>
                    {publishedUrl && (
                      <div className="text-[11px]">
                        <span style={{ color: "var(--bz-text-2)" }}>
                          Published:{" "}
                        </span>
                        <a
                          href={publishedUrl}
                          target="_blank"
                          className="underline break-all"
                          style={{ color: "var(--bz-green, #4db87a)" }}
                        >
                          {publishedUrl}
                        </a>
                      </div>
                    )}
                  </div>
                )}

                {/* Copy/Export — only visible when NOT editing */}
                {!isEditing && (
                  <div className="flex items-center gap-2 pt-2">
                    <button
                      onClick={handleCopyJson}
                      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all hover:bg-white/[0.04]"
                      style={{
                        color: "var(--bz-text-2)",
                        border: "1px solid rgba(255,255,255,0.07)",
                      }}
                    >
                      <Copy size={11} /> Copy JSON
                    </button>
                    <button
                      onClick={handleExportJson}
                      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all hover:bg-white/[0.04]"
                      style={{
                        color: "var(--bz-text-2)",
                        border: "1px solid rgba(255,255,255,0.07)",
                      }}
                    >
                      <Download size={11} /> Export
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

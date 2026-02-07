'use client';

import { useState, useEffect, useRef } from 'react';
import {
  articlesApi,
  ComposeRequest,
  EnrichedArticle,
  PublishRequest,
} from '@/lib/api/articles.api';
import { useToast } from '@/components/ui/toast';
import { logger } from '@/lib/logger';
// 👇 Importiamo i moduli appena creati
import { AutoResizeTextarea } from '@/components/ui/auto-resize-textarea';
import { renderMiniMarkdown, fileToBase64 } from '@/lib/utils';
import {
  Loader2,
  Menu,
  Activity,
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
} from 'lucide-react';

const CATEGORIES = [
  { value: 'business', label: 'Business & Company' },
  { value: 'immigration', label: 'Immigration & Visas' },
  { value: 'tax', label: 'Tax & Legal' },
  { value: 'property', label: 'Property & Real Estate' },
  { value: 'lifestyle', label: 'Lifestyle' },
  { value: 'tech', label: 'Technology' },
  { value: 'legal', label: 'Legal Updates' },
];

const POSITIONS = [
  { value: 'normal', label: 'Normal Article' },
  { value: 'secondary', label: 'Secondary Featured' },
  { value: 'main_featured', label: 'Main Featured (Homepage Hero)' },
];

const DRAFT_KEY = 'bz_composer_draft_v2';

// Classi CSS riutilizzabili (Tailwind arbitrary values per matchare il design HTML)
const cardClass =
  'rounded-[14px] border border-[#27272a] bg-[#181818] shadow-[0_18px_40px_rgba(0,0,0,0.45)]';
const inputClass =
  'w-full rounded-[9px] border border-[#27272a] bg-[#262626] px-3 py-2.5 text-[13px] text-[#f5f5f5] placeholder-[#737373] outline-none transition-all focus:border-[#6366f1] focus:bg-[#1d1d25] focus:shadow-[0_0_0_1px_rgba(99,102,241,0.4)]';
const textAreaClass =
  'w-full rounded-[9px] border border-[#27272a] bg-[#262626] px-3 py-2.5 text-[13px] text-[#f5f5f5] placeholder-[#737373] outline-none transition-all focus:border-[#6366f1] focus:bg-[#1d1d25] focus:shadow-[0_0_0_1px_rgba(99,102,241,0.4)] resize-none';

export default function ArticleComposerPage() {
  const toast = useToast();

  // --- STATE ---
  const [statusLoading, setStatusLoading] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [publishConfigured, setPublishConfigured] = useState(false);

  // Form State
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('business');
  const [sourceUrl, setSourceUrl] = useState('');
  const [author, setAuthor] = useState('Marketing Team');

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
  const [editedResult, setEditedResult] = useState<EnrichedArticle | null>(null);

  // Publish State
  const [position, setPosition] = useState<'normal' | 'secondary' | 'main_featured'>('normal');
  const [customSlug, setCustomSlug] = useState('');
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);

  // --- LIFECYCLE ---

  useEffect(() => {
    logger.componentMount('ArticleComposerPage');

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
        logger.error('API Check failed', { component: 'ArticleComposerPage' }, err as Error);
      } finally {
        setStatusLoading(false);
      }
    };
    init();

    // Load Draft (FIX: uso del logger invece di console.warn)
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
        'Failed to load draft from localStorage',
        { component: 'ArticleComposerPage' },
        e as Error
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
            JSON.stringify({ title, content, category, source: sourceUrl, author })
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
      toast.error('Missing Data', 'Inserisci titolo e contenuto.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      logger.info('Starting article composition', {
        component: 'ArticleComposerPage',
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
        toast.success('Article Enriched!', `Cost: $${(res.api_cost_cents / 100).toFixed(4)}`);
        localStorage.removeItem(DRAFT_KEY);
      } else {
        throw new Error(res.error || 'Unknown error');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
      logger.error('Composition failed', { component: 'ArticleComposerPage' }, err as Error);
      toast.error('Enrichment Failed', msg);
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!result) return;
    setPublishing(true);
    const articleToPublish = isEditing && editedResult ? editedResult : result;

    try {
      logger.info('Publishing article', {
        component: 'ArticleComposerPage',
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
        setPublishedUrl(res.article_url || '#');
        toast.success('Published!', 'Article is live.');
      } else {
        throw new Error(res.error);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Publish failed';
      logger.error('Publish failed', { component: 'ArticleComposerPage' }, err as Error);
      toast.error('Publish Error', msg);
    } finally {
      setPublishing(false);
    }
  };

  // Helper: Images
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Invalid File', 'Not an image.');
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
    if (fileInputRef.current) fileInputRef.current.value = '';
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
      toast.success('Saved', 'Changes updated locally.');
    }
  };

  const cancelEditing = () => {
    setEditedResult(null);
    setIsEditing(false);
  };

  const updateEditedField = (path: string, value: any) => {
    if (!editedResult) return;
    const newResult = JSON.parse(JSON.stringify(editedResult));
    const parts = path.split('.');
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
    toast.success('Copied', 'JSON copied to clipboard');
  };

  const handleExportJson = () => {
    const data = isEditing ? editedResult : result;
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `article-${(data.headline || 'draft').slice(0, 30).replace(/\s+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // --- RENDER ---

  if (statusLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center bg-[#111] text-[#f5f5f5]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-10 w-10 animate-spin text-[#6366f1]" />
          <p className="animate-pulse text-[#737373]">Initializing Intelligence Center...</p>
        </div>
      </div>
    );
  }

  const activeArticle = isEditing && editedResult ? editedResult : result;

  return (
    <div className="min-h-screen bg-[#111111] text-[#f5f5f5] font-sans selection:bg-[#6366f1] selection:text-white pb-20">
      <style>{`
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #111; }
        ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
        .custom-select {
          background-image: linear-gradient(45deg, transparent 50%, #a3a3a3 50%),
                            linear-gradient(135deg, #a3a3a3 50%, transparent 50%);
          background-position: calc(100% - 14px) 13px, calc(100% - 9px) 13px;
          background-size: 6px 6px;
          background-repeat: no-repeat;
        }
      `}</style>

      {/* TOP BAR */}
      <header className="flex h-14 items-center justify-between border-b border-[#27272a] bg-[#101010] px-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full border border-[#27272a] text-[#a3a3a3] hover:bg-[#18181b] hover:text-white">
            <Menu size={16} />
          </div>
          <span className="font-medium text-[#f5f5f5]">Intelligence Center</span>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${configured ? 'border-green-500/40 bg-green-500/10 text-green-500' : 'border-red-500/40 bg-red-500/10 text-red-500'}`}
          >
            <div className={`h-2 w-2 rounded-full ${configured ? 'bg-green-500' : 'bg-red-500'}`} />
            {configured ? 'API Ready' : 'API Missing'}
          </div>
          <div className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full border border-[#27272a] bg-gradient-to-br from-[#a855f7] to-[#1d1b4f] text-xs text-white">
            BZ
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="mx-auto flex max-w-[1200px] flex-col gap-6 p-4 md:p-6">
        <div className="flex items-end justify-between border-b border-[#27272a] pb-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-wide text-[#f5f5f5]">
              Article Composer
            </h1>
            <p className="mt-1 text-sm text-[#737373]">
              Transform raw content into Bali Zero style Executive Briefs
            </p>
          </div>
          <div className="hidden items-center gap-1.5 rounded-lg border border-green-500/40 bg-green-500/10 px-2.5 py-1.5 text-[11px] font-medium text-green-500 md:flex">
            <Activity size={14} />
            <span>Anthropic Online</span>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1.2fr]">
          {/* LEFT: INPUT */}
          <section className={`${cardClass} flex flex-col h-fit`}>
            <div className="flex flex-col gap-1 border-b border-[#27272a]/90 px-4 py-3.5">
              <div className="flex items-center gap-2 text-sm font-medium text-[#f5f5f5]">
                <div className="flex h-[18px] w-[18px] items-center justify-center rounded-md bg-gradient-to-br from-[#4f46e5] to-[#818cf8] text-[10px]">
                  📝
                </div>
                <span>Raw Content Input</span>
              </div>
              <p className="text-xs text-[#a3a3a3]">
                Incolla la fonte (news, regulation) e lascia che il sistema la riscriva.
              </p>
            </div>

            <div className="flex flex-col gap-4 p-4">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#a3a3a3]">
                  Article Title <span className="text-[#ef4444]">*</span>
                </label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Es. New KITAS Rules..."
                  className={inputClass}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#a3a3a3]">
                  Raw Content <span className="text-[#ef4444]">*</span>
                </label>
                <AutoResizeTextarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Incolla contenuto..."
                  className={`${inputClass} min-h-[140px]`}
                />
                <div className="text-right text-[11px] text-[#737373]">
                  {content.length}/8000 chars
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#a3a3a3]">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className={`${inputClass} custom-select appearance-none cursor-pointer`}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-[#a3a3a3]">Source URL</label>
                  <input
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    className={inputClass}
                    placeholder="https://..."
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-[#a3a3a3]">Author</label>
                  <input
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Cover Image (Re-styled) */}
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#a3a3a3]">Cover Image (optional)</label>
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
                    className="flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-[10px] border border-dashed border-[#27272a] bg-[#18181b] p-4 text-center transition-colors hover:border-[#3f3f46] hover:bg-[#1f1f24]"
                  >
                    <ImageIcon className="text-[#a3a3a3] h-5 w-5" />
                    <div className="text-[11px] text-[#737373]">Click per caricare (1200×630)</div>
                  </div>
                ) : (
                  <div className="relative overflow-hidden rounded-[10px] border border-[#27272a]">
                    <img src={coverPreview} alt="Cover" className="h-[180px] w-full object-cover" />
                    <button
                      onClick={removeCoverImage}
                      className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/80 text-white hover:bg-red-900/80"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>

              {error && (
                <div className="rounded-[9px] border border-red-500/50 bg-red-900/20 px-3 py-2 text-[12px] text-red-300">
                  {error}
                </div>
              )}

              <button
                onClick={handleCompose}
                disabled={loading || !configured}
                className="group mt-2 flex w-full items-center justify-center gap-2 rounded-full border-none bg-gradient-to-br from-[#6366f1] to-[#4f46e5] px-4 py-2.5 text-[13px] font-medium text-white shadow-[0_16px_35px_rgba(79,70,229,0.5)] transition-all hover:-translate-y-px hover:shadow-[0_20px_40px_rgba(79,70,229,0.75)] disabled:opacity-60 disabled:shadow-none"
              >
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {loading ? 'Enriching with Claude...' : 'Compose Executive Brief'}
              </button>

              {apiCost > 0 && (
                <div className="flex gap-2 text-[11px] text-[#737373] mt-1">
                  <span className="rounded-full border border-[#6366f1]/80 bg-[#1e40af]/35 px-2 py-0.5 text-[#c7d2fe]">
                    Cost: ${(apiCost / 100).toFixed(4)}
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* --- RIGHT: RESULT --- */}
          <section className={`${cardClass} flex flex-col h-fit relative`}>
            <div className="flex flex-col gap-1 border-b border-[#27272a]/90 px-4 py-3.5">
              <div className="flex items-center gap-2 text-sm font-medium text-[#f5f5f5]">
                <div className="flex h-[18px] w-[18px] items-center justify-center rounded-md bg-gradient-to-br from-[#22c55e] to-[#a3e635] text-[10px] text-black">
                  ✨
                </div>
                <span>Executive Brief Preview</span>
              </div>
              <p className="text-xs text-[#a3a3a3]">
                Rivedi, modifica e pubblica la versione Bali Zero.
              </p>
            </div>

            <div className="p-4 flex flex-col gap-5 min-h-[400px]">
              {!activeArticle ? (
                <div className="flex flex-1 flex-col items-center justify-center opacity-40 text-center">
                  <div className="mb-4 rounded-full bg-[#27272a] p-4">
                    <FileText className="h-8 w-8 text-[#525252]" />
                  </div>
                  <h3 className="text-[#a3a3a3] font-medium">Ready to Transform</h3>
                  <p className="mt-1 max-w-xs text-[12px] text-[#525252]">
                    Fill in the raw content to generate the brief.
                  </p>
                </div>
              ) : (
                <>
                  {/* Actions */}
                  <div className="flex flex-wrap gap-2 mb-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={saveEdits}
                          className="flex h-[28px] items-center gap-1.5 rounded-full border border-[#6366f1] bg-[#6366f1]/20 px-3 text-[11px] text-[#c7d2fe] hover:bg-[#6366f1]/30 transition-colors"
                        >
                          <Save size={12} /> Save Changes
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="flex h-[28px] items-center gap-1.5 rounded-full border border-[#ef4444]/40 bg-[#ef4444]/10 px-3 text-[11px] text-[#fca5a5] hover:bg-[#ef4444]/20 transition-colors"
                        >
                          <X size={12} /> Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={startEditing}
                        className="flex h-[28px] items-center gap-1.5 rounded-full border border-[#27272a] bg-transparent px-3 text-[11px] text-[#a3a3a3] hover:bg-[#18181b] hover:text-[#f5f5f5] transition-colors"
                      >
                        <Pencil size={12} /> Edit Article
                      </button>
                    )}

                    {!isEditing && (
                      <>
                        <button
                          onClick={handleCopyJson}
                          className="flex h-[28px] items-center gap-1.5 rounded-full border border-[#27272a] bg-transparent px-3 text-[11px] text-[#a3a3a3] hover:bg-[#18181b] hover:text-[#f5f5f5] transition-colors"
                        >
                          <Copy size={12} /> Copy JSON
                        </button>
                        <button
                          onClick={handleExportJson}
                          className="flex h-[28px] items-center gap-1.5 rounded-full border border-[#27272a] bg-transparent px-3 text-[11px] text-[#a3a3a3] hover:bg-[#18181b] hover:text-[#f5f5f5] transition-colors"
                        >
                          <Download size={12} /> Export
                        </button>
                      </>
                    )}
                  </div>

                  {/* PUBLISH CARD */}
                  {publishConfigured && (
                    <div className="rounded-[12px] border border-[#22c55e]/40 bg-[#202020] bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.15),transparent)] p-3.5 flex flex-col gap-3">
                      <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5]">
                        <Globe size={14} className="text-[#22c55e]" />
                        <span>Publish to Site</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] text-[#bbf7d0]">Position</label>
                          <select
                            value={position}
                            onChange={(e) => setPosition(e.target.value as any)}
                            disabled={isEditing}
                            className="w-full rounded-[9px] border border-[#16a34a]/40 bg-[#052e16]/60 px-2.5 py-1.5 text-[12px] text-[#bbf7d0] outline-none custom-select appearance-none cursor-pointer"
                          >
                            {POSITIONS.map((p) => (
                              <option key={p.value} value={p.value}>
                                {p.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-[11px] text-[#bbf7d0]">Slug</label>
                          <input
                            value={customSlug}
                            onChange={(e) => setCustomSlug(e.target.value)}
                            disabled={isEditing}
                            className="w-full rounded-[9px] border border-[#16a34a]/40 bg-[#052e16]/60 px-2.5 py-1.5 text-[12px] text-[#bbf7d0] placeholder-[#86efac]/50 outline-none"
                            placeholder="auto-generated-slug"
                          />
                        </div>
                      </div>
                      <button
                        onClick={handlePublish}
                        disabled={publishing || isEditing}
                        className="mt-1 w-full rounded-full bg-[#22c55e] py-1.5 text-[12px] font-medium text-[#052e16] hover:bg-[#16a34a] disabled:opacity-50 transition-colors flex justify-center items-center gap-2"
                      >
                        {publishing ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Send size={12} />
                        )}
                        {publishing ? 'Publishing...' : 'Publish Article'}
                      </button>
                      {publishedUrl && (
                        <div className="text-[11px]">
                          <span className="text-[#bbf7d0]">Published: </span>
                          <a
                            href={publishedUrl}
                            target="_blank"
                            className="text-[#4ade80] underline break-all"
                          >
                            {publishedUrl}
                          </a>
                        </div>
                      )}
                    </div>
                  )}

                  {/* SECTIONS */}

                  {/* Headline */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5] mb-2">
                      <div className="w-2 h-2 rounded-full bg-[#6366f1]" /> Headline & Summary
                    </div>
                    {isEditing ? (
                      <div className="flex flex-col gap-2">
                        <AutoResizeTextarea
                          value={activeArticle.headline}
                          onChange={(e) => updateEditedField('headline', e.target.value)}
                          className={`${inputClass} text-[16px] font-bold min-h-[50px]`}
                        />
                        <AutoResizeTextarea
                          value={activeArticle.ai_summary}
                          onChange={(e) => updateEditedField('ai_summary', e.target.value)}
                          className={`${inputClass} min-h-[70px]`}
                        />
                      </div>
                    ) : (
                      <div>
                        <h2 className="text-[18px] font-semibold leading-[1.2]">
                          {activeArticle.headline}
                        </h2>
                        <p className="mt-1 text-[13px] text-[#a3a3a3]">
                          {activeArticle.ai_summary}
                        </p>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      <span className="rounded-full border border-[#3f3f46]/80 bg-[#27272a]/90 px-2 py-0.5 text-[11px] text-[#a3a3a3]">
                        {activeArticle.category}
                      </span>
                      <span className="rounded-full border border-[#3f3f46]/80 bg-[#27272a]/90 px-2 py-0.5 text-[11px] text-[#a3a3a3]">
                        Relevance: {activeArticle.relevance_score}/100
                      </span>
                    </div>
                  </div>

                  {/* TL;DR */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5]">
                      <div className="h-2 w-2 rounded-full bg-[#6366f1]" /> TL;DR
                    </div>
                    {isEditing ? (
                      <div className="grid gap-2 text-[12px]">
                        <div className="grid grid-cols-2 gap-2">
                          <select
                            value={activeArticle.tldr.should_worry}
                            onChange={(e) => updateEditedField('tldr.should_worry', e.target.value)}
                            className={`${inputClass} custom-select appearance-none cursor-pointer`}
                          >
                            <option>Yes</option>
                            <option>No</option>
                            <option>Maybe</option>
                          </select>
                          <select
                            value={activeArticle.tldr.risk_level}
                            onChange={(e) => updateEditedField('tldr.risk_level', e.target.value)}
                            className={`${inputClass} custom-select appearance-none cursor-pointer`}
                          >
                            <option>Low</option>
                            <option>Medium</option>
                            <option>High</option>
                          </select>
                        </div>
                        <AutoResizeTextarea
                          value={activeArticle.tldr.what}
                          onChange={(e) => updateEditedField('tldr.what', e.target.value)}
                          className={`${inputClass} min-h-[60px]`}
                          placeholder="What"
                        />
                        <input
                          value={activeArticle.tldr.who}
                          onChange={(e) => updateEditedField('tldr.who', e.target.value)}
                          className={inputClass}
                          placeholder="Who"
                        />
                        <input
                          value={activeArticle.tldr.when}
                          onChange={(e) => updateEditedField('tldr.when', e.target.value)}
                          className={inputClass}
                          placeholder="When"
                        />
                      </div>
                    ) : (
                      <div className="text-[12px]">
                        <div className="grid grid-cols-2 gap-2 mb-2">
                          <div>
                            <span className="text-[#a3a3a3]">Worry: </span>
                            <span
                              className={
                                activeArticle.tldr.should_worry === 'Yes'
                                  ? 'text-[#fecaca]'
                                  : activeArticle.tldr.should_worry === 'No'
                                    ? 'text-[#bbf7d0]'
                                    : 'text-[#fed7aa]'
                              }
                            >
                              {activeArticle.tldr.should_worry}
                            </span>
                          </div>
                          <div>
                            <span className="text-[#a3a3a3]">Risk: </span>
                            <span
                              className={
                                activeArticle.tldr.risk_level === 'High'
                                  ? 'text-[#fecaca]'
                                  : activeArticle.tldr.risk_level === 'Low'
                                    ? 'text-[#bbf7d0]'
                                    : 'text-[#fed7aa]'
                              }
                            >
                              {activeArticle.tldr.risk_level}
                            </span>
                          </div>
                        </div>
                        <div className="space-y-1 text-[13px]">
                          <div>
                            <strong className="text-white">What:</strong> {activeArticle.tldr.what}
                          </div>
                          <div>
                            <strong className="text-white">Who:</strong> {activeArticle.tldr.who}
                          </div>
                          <div>
                            <strong className="text-white">When:</strong> {activeArticle.tldr.when}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Facts (Markdown Enabled) */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5]">
                      <div className="h-2 w-2 rounded-full bg-[#6366f1]" /> The Facts
                    </div>
                    {isEditing ? (
                      <AutoResizeTextarea
                        value={activeArticle.facts}
                        onChange={(e) => updateEditedField('facts', e.target.value)}
                        className={`${inputClass} min-h-[120px]`}
                      />
                    ) : (
                      <div
                        className="text-[13px] leading-relaxed whitespace-pre-line text-[#f5f5f5]"
                        dangerouslySetInnerHTML={renderMiniMarkdown(activeArticle.facts)}
                      />
                    )}
                  </div>

                  {/* Bali Zero Take */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5]">
                      <div className="h-2 w-2 rounded-full bg-[#6366f1]" /> Bali Zero Take
                    </div>
                    <div className="flex flex-col gap-3 text-[13px]">
                      {['hidden_insight', 'our_analysis', 'our_advice'].map((key) => {
                        const val = (activeArticle.bali_zero_take as any)[key];
                        return (
                          <div key={key}>
                            <strong className="block text-[#f5f5f5] mb-1 capitalize">
                              {key.replace('_', ' ')}
                            </strong>
                            {isEditing ? (
                              <AutoResizeTextarea
                                value={val}
                                onChange={(e) =>
                                  updateEditedField(`bali_zero_take.${key}`, e.target.value)
                                }
                                className={`${inputClass} min-h-[60px]`}
                              />
                            ) : (
                              <div className="text-[#a3a3a3]">{val}</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Next Steps */}
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5]">
                      <div className="h-2 w-2 rounded-full bg-[#6366f1]" /> Next Steps
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
                      {['expat', 'investor'].map((type) => (
                        <div key={type}>
                          <div className="font-medium text-[#f5f5f5] mb-1 capitalize">
                            For {type}s
                          </div>
                          {isEditing ? (
                            <AutoResizeTextarea
                              value={activeArticle.next_steps[type as 'expat' | 'investor'].join(
                                '\n'
                              )}
                              onChange={(e) =>
                                updateEditedField(`next_steps.${type}`, e.target.value.split('\n'))
                              }
                              className={`${inputClass} min-h-[100px]`}
                              placeholder="One per line..."
                            />
                          ) : (
                            <ul className="space-y-1">
                              {activeArticle.next_steps[type as 'expat' | 'investor'].map(
                                (s, i) => (
                                  <li key={i} className="flex gap-2 items-start">
                                    <span className="text-[#6366f1] mt-1.5 w-1.5 h-1.5 rounded-full bg-current shrink-0"></span>
                                    <span dangerouslySetInnerHTML={renderMiniMarkdown(s)} />
                                  </li>
                                )
                              )}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="mt-2 pt-2 border-t border-[#27272a]">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium text-[#f5f5f5] mb-2">
                      <div className="h-2 w-2 rounded-full bg-[#6366f1]" /> AI Tags
                    </div>
                    {isEditing ? (
                      <input
                        value={activeArticle.ai_tags.join(', ')}
                        onChange={(e) =>
                          updateEditedField(
                            'ai_tags',
                            e.target.value.split(',').map((s) => s.trim())
                          )
                        }
                        className={inputClass}
                      />
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {activeArticle.ai_tags.map((tag, i) => (
                          <span
                            key={i}
                            className="rounded-full border border-[#3f3f46]/80 bg-[#27272a]/90 px-2 py-0.5 text-[11px] text-[#a3a3a3]"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

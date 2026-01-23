'use client';

import { useState, useEffect, useRef } from 'react';
import {
  articlesApi,
  ComposeRequest,
  EnrichedArticle,
  PublishRequest,
} from '@/lib/api/articles.api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { logger } from '@/lib/logger';
import {
  Loader2,
  Sparkles,
  FileText,
  AlertTriangle,
  CheckCircle,
  Copy,
  Download,
  User,
  Link as LinkIcon,
  Tag,
  Lightbulb,
  TrendingUp,
  Users,
  Calendar,
  Upload,
  ImageIcon,
  Send,
  Globe,
  X,
  Pencil,
  Save,
} from 'lucide-react';

const CATEGORIES = [
  { value: 'immigration', label: 'Immigration & Visas' },
  { value: 'business', label: 'Business & Company' },
  { value: 'tax', label: 'Tax & Legal' },
  { value: 'property', label: 'Property & Real Estate' },
  { value: 'lifestyle', label: 'Lifestyle' },
  { value: 'tech', label: 'Technology' },
  { value: 'legal', label: 'Legal Updates' },
];

const POSITIONS = [
  { value: 'main_featured', label: 'Main Featured (Homepage Hero)' },
  { value: 'secondary', label: 'Secondary Featured' },
  { value: 'normal', label: 'Normal Article' },
];

export default function ArticleComposerPage() {
  const [loading, setLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [publishConfigured, setPublishConfigured] = useState(false);
  const [result, setResult] = useState<EnrichedArticle | null>(null);
  const [apiCost, setApiCost] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  // Form state
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('business');
  const [sourceUrl, setSourceUrl] = useState('');
  const [author, setAuthor] = useState('Marketing Team');

  // Cover image state
  const [coverImage, setCoverImage] = useState<File | null>(null);
  const [coverImagePreview, setCoverImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Publish state
  const [position, setPosition] = useState<'main_featured' | 'secondary' | 'normal'>('normal');
  const [customSlug, setCustomSlug] = useState('');
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editedResult, setEditedResult] = useState<EnrichedArticle | null>(null);

  useEffect(() => {
    logger.componentMount('ArticleComposerPage');
    checkStatus();

    return () => {
      logger.componentUnmount('ArticleComposerPage');
    };
  }, []);

  const checkStatus = async () => {
    setStatusLoading(true);
    try {
      const [composeStatus, publishStatus] = await Promise.all([
        articlesApi.getStatus(),
        articlesApi.getPublishStatus().catch(() => ({ configured: false })),
      ]);
      setConfigured(composeStatus.configured);
      setPublishConfigured(publishStatus.configured);
      logger.info('Article composer status', {
        component: 'ArticleComposerPage',
        metadata: { composeStatus, publishStatus },
      });
    } catch (err) {
      logger.error(
        'Failed to check composer status',
        {
          component: 'ArticleComposerPage',
        },
        err as Error
      );
      setConfigured(false);
    } finally {
      setStatusLoading(false);
    }
  };

  // Handle cover image selection
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        toast.error('Invalid File', 'Please select an image file');
        return;
      }
      setCoverImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setCoverImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // Remove cover image
  const removeCoverImage = () => {
    setCoverImage(null);
    setCoverImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Convert file to base64
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  // Publish article
  const handlePublish = async () => {
    if (!result) {
      toast.error('No Article', 'Please compose an article first');
      return;
    }

    setPublishing(true);
    setError(null);

    try {
      const request: PublishRequest = {
        article: result,
        position,
        slug: customSlug || undefined,
      };

      // Add cover image if provided
      if (coverImage) {
        request.cover_image_base64 = await fileToBase64(coverImage);
        request.cover_image_filename = coverImage.name;
      }

      const response = await articlesApi.publish(request);

      if (response.success) {
        setPublishedUrl(response.article_url || null);
        toast.success('Published!', response.message);
        logger.info('Article published', {
          component: 'ArticleComposerPage',
          action: 'publish_success',
          metadata: { url: response.article_url, commit: response.commit_sha },
        });
      } else {
        setError(response.error || 'Unknown error');
        toast.error('Publish Failed', response.error || 'Unknown error');
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errMsg);
      toast.error('Publish Error', errMsg);
      logger.error(
        'Publish failed',
        {
          component: 'ArticleComposerPage',
          action: 'publish_error',
        },
        err as Error
      );
    } finally {
      setPublishing(false);
    }
  };

  const handleCompose = async () => {
    if (!title.trim() || !content.trim()) {
      toast.error('Missing Fields', 'Please enter both title and content');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    logger.info('Composing article', {
      component: 'ArticleComposerPage',
      action: 'compose_start',
      metadata: { title, category },
    });

    try {
      const request: ComposeRequest = {
        title,
        content,
        category,
        source_url: sourceUrl || undefined,
        author,
      };

      const response = await articlesApi.compose(request);

      if (response.success && response.article) {
        setResult(response.article);
        setApiCost(response.api_cost_cents);
        toast.success('Article Enriched!', `Cost: $${(response.api_cost_cents / 100).toFixed(4)}`);
        logger.info('Article composed successfully', {
          component: 'ArticleComposerPage',
          action: 'compose_success',
          metadata: { cost: response.api_cost_cents },
        });
      } else {
        setError(response.error || 'Unknown error');
        toast.error('Enrichment Failed', response.error || 'Unknown error');
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errMsg);
      toast.error('Error', errMsg);
      logger.error(
        'Compose failed',
        {
          component: 'ArticleComposerPage',
          action: 'compose_error',
        },
        err as Error
      );
    } finally {
      setLoading(false);
    }
  };

  // Start editing mode
  const startEditing = () => {
    if (result) {
      setEditedResult(JSON.parse(JSON.stringify(result))); // Deep copy
      setIsEditing(true);
    }
  };

  // Save edits
  const saveEdits = () => {
    if (editedResult) {
      setResult(editedResult);
      setIsEditing(false);
      toast.success('Saved!', 'Article changes saved');
    }
  };

  // Cancel editing
  const cancelEditing = () => {
    setEditedResult(null);
    setIsEditing(false);
  };

  // Update edited field helper
  const updateEditedField = (path: string, value: string | string[]) => {
    if (!editedResult) return;
    const updated = { ...editedResult };
    const keys = path.split('.');
    let obj: Record<string, unknown> = updated;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]] as Record<string, unknown>;
    }
    obj[keys[keys.length - 1]] = value;
    setEditedResult(updated as EnrichedArticle);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied!', 'Content copied to clipboard');
  };

  const exportAsJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `article-${result.headline.slice(0, 30).replace(/\s+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (statusLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Checking API Configuration...
        </p>
      </div>
    );
  }

  if (!configured) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <div className="bg-amber-100 p-6 rounded-full mb-6">
          <AlertTriangle className="h-12 w-12 text-amber-600" />
        </div>
        <h3 className="text-xl font-semibold mb-2 text-[var(--foreground)]">API Not Configured</h3>
        <p className="text-[var(--foreground-muted)] max-w-md text-center">
          The Anthropic API key is not configured. Please contact the admin to set up the
          ANTHROPIC_API_KEY secret on Fly.io.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-[var(--border)] pb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            Article Composer
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Transform raw content into Bali Zero style Executive Briefs
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle className="w-4 h-4 text-emerald-500" />
          <span className="text-sm font-medium text-emerald-600">API Ready</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Input Form */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-[var(--accent)]" />
              Raw Content Input
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">Article Title *</Label>
              <Input
                id="title"
                placeholder="e.g., New KITAS Rules for Digital Nomads in 2026"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            {/* Content */}
            <div className="space-y-2">
              <Label htmlFor="content">Raw Content *</Label>
              <Textarea
                id="content"
                placeholder="Paste your raw article content here. This can be from a news source, government announcement, or your own draft..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="min-h-[200px] resize-y"
              />
              <p className="text-xs text-[var(--foreground-muted)]">
                {content.length}/8000 characters (max)
              </p>
            </div>

            {/* Category */}
            <div className="space-y-2">
              <Label htmlFor="category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((cat) => (
                    <SelectItem key={cat.value} value={cat.value}>
                      {cat.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Source URL */}
            <div className="space-y-2">
              <Label htmlFor="sourceUrl" className="flex items-center gap-2">
                <LinkIcon className="h-4 w-4" />
                Source URL (optional)
              </Label>
              <Input
                id="sourceUrl"
                type="url"
                placeholder="https://..."
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>

            {/* Author */}
            <div className="space-y-2">
              <Label htmlFor="author" className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Author
              </Label>
              <Input
                id="author"
                placeholder="Marketing Team"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
              />
            </div>

            {/* Cover Image Upload */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4" />
                Cover Image (optional)
              </Label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
              />
              {coverImagePreview ? (
                <div className="relative">
                  <img
                    src={coverImagePreview}
                    alt="Cover preview"
                    className="w-full h-48 object-cover rounded-lg border border-[var(--border)]"
                  />
                  <Button
                    variant="destructive"
                    size="icon"
                    className="absolute top-2 right-2 h-8 w-8"
                    onClick={removeCoverImage}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <p className="mt-1 text-xs text-[var(--foreground-muted)]">{coverImage?.name}</p>
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-[var(--border)] rounded-lg cursor-pointer hover:bg-[var(--background-secondary)] transition-colors"
                >
                  <Upload className="h-8 w-8 text-[var(--foreground-muted)] mb-2" />
                  <p className="text-sm text-[var(--foreground-muted)]">
                    Click to upload cover image
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">
                    PNG, JPG, WebP (recommended 1200x630)
                  </p>
                </div>
              )}
            </div>

            {/* Submit Button */}
            <Button
              onClick={handleCompose}
              disabled={loading || !title.trim() || !content.trim()}
              className="w-full gap-2 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-12 text-lg"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Enriching with Claude...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Compose Executive Brief
                </>
              )}
            </Button>

            {error && (
              <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-700">
                <p className="font-medium">Error:</p>
                <p className="text-sm">{error}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Result Preview */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Actions Bar */}
              <div className="flex flex-wrap gap-2 justify-between items-center">
                <div className="flex gap-2">
                  {isEditing ? (
                    <>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={saveEdits}
                        className="gap-2 bg-emerald-600 hover:bg-emerald-700"
                      >
                        <Save className="h-4 w-4" />
                        Save Changes
                      </Button>
                      <Button variant="outline" size="sm" onClick={cancelEditing} className="gap-2">
                        <X className="h-4 w-4" />
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={startEditing}
                        className="gap-2 border-amber-500/50 text-amber-600 hover:bg-amber-50"
                      >
                        <Pencil className="h-4 w-4" />
                        Edit Article
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
                        className="gap-2"
                      >
                        <Copy className="h-4 w-4" />
                        Copy JSON
                      </Button>
                      <Button variant="outline" size="sm" onClick={exportAsJson} className="gap-2">
                        <Download className="h-4 w-4" />
                        Export
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {/* Publish Section */}
              {publishConfigured ? (
                <Card
                  className={`border-emerald-500/30 bg-emerald-500/5 ${isEditing ? 'opacity-50' : ''}`}
                >
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Globe className="h-5 w-5 text-emerald-500" />
                      Publish to Site
                      {isEditing && (
                        <span className="text-xs text-amber-600 ml-2">(Save changes first)</span>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      {/* Position Selector */}
                      <div className="space-y-2">
                        <Label>Position</Label>
                        <Select
                          value={position}
                          onValueChange={(v) => setPosition(v as typeof position)}
                          disabled={isEditing}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {POSITIONS.map((pos) => (
                              <SelectItem key={pos.value} value={pos.value}>
                                {pos.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {/* Custom Slug */}
                      <div className="space-y-2">
                        <Label>Custom Slug (optional)</Label>
                        <Input
                          placeholder="my-custom-article-url"
                          value={customSlug}
                          onChange={(e) => setCustomSlug(e.target.value)}
                          disabled={isEditing}
                        />
                      </div>
                    </div>

                    {/* Publish Button */}
                    <Button
                      onClick={handlePublish}
                      disabled={publishing || isEditing}
                      className="w-full gap-2 bg-emerald-600 hover:bg-emerald-700 text-white h-11"
                    >
                      {publishing ? (
                        <>
                          <Loader2 className="h-5 w-5 animate-spin" />
                          Publishing to BaliZero.com...
                        </>
                      ) : (
                        <>
                          <Send className="h-5 w-5" />
                          Publish Article
                        </>
                      )}
                    </Button>

                    {/* Published URL */}
                    {publishedUrl && (
                      <div className="p-3 rounded-lg bg-emerald-100 border border-emerald-300 text-emerald-800">
                        <p className="font-medium flex items-center gap-2">
                          <CheckCircle className="h-4 w-4" />
                          Published Successfully!
                        </p>
                        <a
                          href={publishedUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm underline hover:text-emerald-600"
                        >
                          {publishedUrl}
                        </a>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-amber-500/30 bg-amber-500/5">
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-3 text-amber-700">
                      <AlertTriangle className="h-5 w-5" />
                      <div>
                        <p className="font-medium">Publishing Not Configured</p>
                        <p className="text-sm">
                          Set GITHUB_TOKEN environment variable to enable direct publishing.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Headline Card */}
              <Card className={isEditing ? 'border-amber-500/50' : ''}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-[var(--accent)] uppercase">
                      {result.category} | {result.priority} priority
                    </span>
                    <span className="text-xs text-[var(--foreground-muted)]">
                      Relevance: {result.relevance_score}/100
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  {isEditing && editedResult ? (
                    <div className="space-y-3">
                      <div>
                        <Label className="text-xs text-amber-600">Headline</Label>
                        <Input
                          value={editedResult.headline}
                          onChange={(e) => updateEditedField('headline', e.target.value)}
                          className="text-lg font-bold"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">Summary</Label>
                        <Textarea
                          value={editedResult.ai_summary}
                          onChange={(e) => updateEditedField('ai_summary', e.target.value)}
                          className="min-h-[80px]"
                        />
                      </div>
                    </div>
                  ) : (
                    <>
                      <h3 className="text-2xl font-bold text-[var(--foreground)] leading-tight">
                        {result.headline}
                      </h3>
                      <p className="mt-2 text-[var(--foreground-muted)]">{result.ai_summary}</p>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* TL;DR Card */}
              <Card className={isEditing ? 'border-amber-500/50' : ''}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                    TL;DR
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {isEditing && editedResult ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-xs text-amber-600">Should Worry</Label>
                          <Select
                            value={editedResult.tldr.should_worry}
                            onValueChange={(v) => updateEditedField('tldr.should_worry', v)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Yes">Yes</SelectItem>
                              <SelectItem value="No">No</SelectItem>
                              <SelectItem value="Maybe">Maybe</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs text-amber-600">Risk Level</Label>
                          <Select
                            value={editedResult.tldr.risk_level}
                            onValueChange={(v) => updateEditedField('tldr.risk_level', v)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Low">Low</SelectItem>
                              <SelectItem value="Medium">Medium</SelectItem>
                              <SelectItem value="High">High</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">What</Label>
                        <Textarea
                          value={editedResult.tldr.what}
                          onChange={(e) => updateEditedField('tldr.what', e.target.value)}
                          className="min-h-[60px]"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">Who</Label>
                        <Input
                          value={editedResult.tldr.who}
                          onChange={(e) => updateEditedField('tldr.who', e.target.value)}
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">When</Label>
                        <Input
                          value={editedResult.tldr.when}
                          onChange={(e) => updateEditedField('tldr.when', e.target.value)}
                        />
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">Should Worry:</span>
                          <span
                            className={
                              result.tldr.should_worry === 'Yes'
                                ? 'text-red-600 font-bold'
                                : result.tldr.should_worry === 'No'
                                  ? 'text-green-600'
                                  : 'text-amber-600'
                            }
                          >
                            {result.tldr.should_worry}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">Risk Level:</span>
                          <span
                            className={
                              result.tldr.risk_level === 'High'
                                ? 'text-red-600 font-bold'
                                : result.tldr.risk_level === 'Low'
                                  ? 'text-green-600'
                                  : 'text-amber-600'
                            }
                          >
                            {result.tldr.risk_level}
                          </span>
                        </div>
                      </div>
                      <div>
                        <strong>What:</strong> {result.tldr.what}
                      </div>
                      <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-[var(--foreground-muted)]" />
                        <strong>Who:</strong> {result.tldr.who}
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-[var(--foreground-muted)]" />
                        <strong>When:</strong> {result.tldr.when}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Facts Card */}
              <Card className={isEditing ? 'border-amber-500/50' : ''}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <FileText className="h-5 w-5 text-blue-500" />
                    The Facts
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {isEditing && editedResult ? (
                    <Textarea
                      value={editedResult.facts}
                      onChange={(e) => updateEditedField('facts', e.target.value)}
                      className="min-h-[150px]"
                    />
                  ) : (
                    <p className="text-[var(--foreground)] whitespace-pre-line">{result.facts}</p>
                  )}
                </CardContent>
              </Card>

              {/* Bali Zero Take Card */}
              <Card
                className={`border-[var(--accent)]/30 bg-[var(--accent)]/5 ${isEditing ? 'border-amber-500/50' : ''}`}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Lightbulb className="h-5 w-5 text-[var(--accent)]" />
                    Bali Zero Take
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isEditing && editedResult ? (
                    <>
                      <div>
                        <Label className="text-xs text-amber-600">Hidden Insight</Label>
                        <Textarea
                          value={editedResult.bali_zero_take.hidden_insight}
                          onChange={(e) =>
                            updateEditedField('bali_zero_take.hidden_insight', e.target.value)
                          }
                          className="min-h-[80px]"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">Our Analysis</Label>
                        <Textarea
                          value={editedResult.bali_zero_take.our_analysis}
                          onChange={(e) =>
                            updateEditedField('bali_zero_take.our_analysis', e.target.value)
                          }
                          className="min-h-[80px]"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600">Our Advice</Label>
                        <Textarea
                          value={editedResult.bali_zero_take.our_advice}
                          onChange={(e) =>
                            updateEditedField('bali_zero_take.our_advice', e.target.value)
                          }
                          className="min-h-[80px]"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <p className="text-sm font-semibold text-[var(--accent)] mb-1">
                          Hidden Insight
                        </p>
                        <p className="text-[var(--foreground)]">
                          {result.bali_zero_take.hidden_insight}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[var(--accent)] mb-1">
                          Our Analysis
                        </p>
                        <p className="text-[var(--foreground)]">
                          {result.bali_zero_take.our_analysis}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[var(--accent)] mb-1">
                          Our Advice
                        </p>
                        <p className="text-[var(--foreground)]">
                          {result.bali_zero_take.our_advice}
                        </p>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Next Steps Card */}
              <Card className={isEditing ? 'border-amber-500/50' : ''}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <TrendingUp className="h-5 w-5 text-emerald-500" />
                    Next Steps
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-6">
                  {isEditing && editedResult ? (
                    <>
                      <div>
                        <Label className="text-xs text-amber-600 mb-2 block">
                          For Expats (one per line)
                        </Label>
                        <Textarea
                          value={editedResult.next_steps.expat.join('\n')}
                          onChange={(e) =>
                            updateEditedField(
                              'next_steps.expat',
                              e.target.value.split('\n').filter((s) => s.trim())
                            )
                          }
                          className="min-h-[120px]"
                          placeholder="Enter each step on a new line"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600 mb-2 block">
                          For Investors (one per line)
                        </Label>
                        <Textarea
                          value={editedResult.next_steps.investor.join('\n')}
                          onChange={(e) =>
                            updateEditedField(
                              'next_steps.investor',
                              e.target.value.split('\n').filter((s) => s.trim())
                            )
                          }
                          className="min-h-[120px]"
                          placeholder="Enter each step on a new line"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <p className="font-semibold text-[var(--foreground)] mb-2">For Expats</p>
                        <ul className="space-y-1">
                          {result.next_steps.expat.map((step, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <span className="text-[var(--accent)]">•</span>
                              {step}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="font-semibold text-[var(--foreground)] mb-2">For Investors</p>
                        <ul className="space-y-1">
                          {result.next_steps.investor.map((step, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <span className="text-[var(--accent)]">•</span>
                              {step}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Tags & Components */}
              <Card className={isEditing ? 'border-amber-500/50' : ''}>
                <CardContent className="pt-4 space-y-4">
                  {isEditing && editedResult ? (
                    <>
                      <div>
                        <Label className="text-xs text-amber-600 mb-2 flex items-center gap-2">
                          <Tag className="h-4 w-4" />
                          AI Tags (comma separated)
                        </Label>
                        <Input
                          value={editedResult.ai_tags.join(', ')}
                          onChange={(e) =>
                            updateEditedField(
                              'ai_tags',
                              e.target.value
                                .split(',')
                                .map((s) => s.trim())
                                .filter((s) => s)
                            )
                          }
                          placeholder="tag1, tag2, tag3"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-600 mb-2 block">
                          Suggested Components (comma separated)
                        </Label>
                        <Input
                          value={editedResult.suggested_components.join(', ')}
                          onChange={(e) =>
                            updateEditedField(
                              'suggested_components',
                              e.target.value
                                .split(',')
                                .map((s) => s.trim())
                                .filter((s) => s)
                            )
                          }
                          placeholder="checklist, comparison-table, alert-box"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <p className="font-semibold text-[var(--foreground)] mb-2 flex items-center gap-2">
                          <Tag className="h-4 w-4" />
                          AI Tags
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {result.ai_tags.map((tag, i) => (
                            <span
                              key={i}
                              className="px-2 py-1 rounded-full text-xs bg-[var(--background-elevated)] text-[var(--foreground-muted)] border border-[var(--border)]"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="font-semibold text-[var(--foreground)] mb-2">
                          Suggested Components
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {result.suggested_components.map((comp, i) => (
                            <span
                              key={i}
                              className="px-2 py-1 rounded text-xs bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20"
                            >
                              {comp}
                            </span>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Image Prompt Card */}
              {(result.image_prompt || isEditing) && (
                <Card className={isEditing ? 'border-amber-500/50' : ''}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Cover Image Prompt</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {isEditing && editedResult ? (
                      <Textarea
                        value={editedResult.image_prompt || ''}
                        onChange={(e) => updateEditedField('image_prompt', e.target.value)}
                        className="min-h-[150px] font-mono text-sm"
                        placeholder="Enter AI image generation prompt..."
                      />
                    ) : (
                      <>
                        <div className="p-3 rounded bg-[var(--background-secondary)] text-sm font-mono text-[var(--foreground-muted)] whitespace-pre-line">
                          {result.image_prompt}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(result.image_prompt || '')}
                          className="mt-2 gap-2"
                        >
                          <Copy className="h-4 w-4" />
                          Copy Prompt
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Cost Info */}
              <div className="text-center text-sm text-[var(--foreground-muted)]">
                API Cost: ${(apiCost / 100).toFixed(4)} | Enriched at:{' '}
                {new Date(result.enriched_at).toLocaleString()}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-32 bg-[var(--background-secondary)] rounded-2xl border-2 border-dashed border-[var(--border)]">
              <div className="bg-[var(--accent)]/10 p-6 rounded-full mb-6">
                <Sparkles className="h-12 w-12 text-[var(--accent)]" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-[var(--foreground)]">
                Ready to Transform
              </h3>
              <p className="text-[var(--foreground-muted)] max-w-md text-center">
                Enter your raw content on the left and click "Compose Executive Brief" to generate a
                Bali Zero style article with TL;DR, strategic analysis, and actionable next steps.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

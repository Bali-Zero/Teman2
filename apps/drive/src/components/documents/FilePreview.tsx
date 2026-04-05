'use client';

import React, { useState, useEffect } from 'react';
import { Download, X, ExternalLink, FileText, Image as ImageIcon, Video, Music, File, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { api } from '@/lib/api';

interface FilePreviewProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (file: FileItem) => void;
}

type PreviewType = 'image' | 'pdf' | 'text' | 'video' | 'audio' | 'google-doc' | 'unsupported';

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'js', 'ts', 'jsx', 'tsx', 'py', 'json', 'yaml', 'yml',
  'html', 'css', 'scss', 'sh', 'bash', 'env', 'toml', 'ini', 'xml', 'csv',
]);

function getPreviewType(file: FileItem): PreviewType {
  const mime = file.mime_type || '';
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';

  if (mime.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) return 'image';
  if (mime === 'application/pdf' || ext === 'pdf') return 'pdf';
  if (mime.startsWith('video/') || ['mp4', 'mov', 'webm', 'avi', 'mkv'].includes(ext)) return 'video';
  if (mime.startsWith('audio/') || ['mp3', 'wav', 'ogg', 'm4a', 'flac'].includes(ext)) return 'audio';
  if (TEXT_EXTENSIONS.has(ext) || mime.startsWith('text/')) return 'text';
  if (
    mime === 'application/vnd.google-apps.document' ||
    mime === 'application/vnd.google-apps.spreadsheet' ||
    mime === 'application/vnd.google-apps.presentation'
  ) return 'google-doc';
  return 'unsupported';
}

function getPreviewIcon(type: PreviewType): React.ReactNode {
  const cls = 'h-10 w-10 text-slate-400';
  switch (type) {
    case 'image': return <ImageIcon className={cls} />;
    case 'video': return <Video className={cls} />;
    case 'audio': return <Music className={cls} />;
    case 'pdf':
    case 'text':
    case 'google-doc': return <FileText className={cls} />;
    default: return <File className={cls} />;
  }
}

function formatSize(bytes: number | undefined): string {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let i = 0;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
  return `${size.toFixed(1)} ${units[i]}`;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('it-IT', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function FilePreview({ file, isOpen, onClose, onDownload }: FilePreviewProps) {
  const [loading, setLoading] = useState(true);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);

  const previewType = file ? getPreviewType(file) : 'unsupported';

  useEffect(() => {
    if (!isOpen || !file) {
      setLoading(true);
      setTextContent(null);
      setMediaUrl(null);
      setPreviewError(false);
      return;
    }

    setLoading(true);
    setPreviewError(false);

    if (previewType === 'image' || previewType === 'video' || previewType === 'audio') {
      setMediaUrl(api.drive.getDownloadUrl(file.id));
      // loading cleared by media element callbacks
    } else if (previewType === 'pdf') {
      setMediaUrl(api.drive.getDownloadUrl(file.id));
      // loading cleared by iframe onLoad
    } else if (previewType === 'google-doc' && file.web_view_link) {
      const embedUrl = file.web_view_link
        .replace('/edit', '/preview')
        .replace('/view', '/preview');
      setMediaUrl(embedUrl);
    } else if (previewType === 'text') {
      // Fetch text content
      fetch(api.drive.getDownloadUrl(file.id))
        .then((r) => r.text())
        .then((t) => {
          setTextContent(t.slice(0, 8000)); // cap at 8KB for display
          setLoading(false);
        })
        .catch(() => {
          setPreviewError(true);
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [file, isOpen, previewType]);

  if (!file) return null;

  const meta = [
    file.size ? formatSize(file.size) : null,
    file.modified_time ? formatDate(file.modified_time) : null,
  ].filter(Boolean).join(' · ');

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col bg-[#141416] border border-white/10 p-0 gap-0">
        {/* Header */}
        <DialogHeader className="flex flex-row items-center justify-between px-5 py-4 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {getPreviewIcon(previewType)}
            <div className="min-w-0">
              <DialogTitle className="text-[#E6E7EB] text-base font-semibold truncate max-w-[500px]">
                {file.name}
              </DialogTitle>
              {meta && (
                <p className="text-xs text-[#9AA0AE] mt-0.5">{meta}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-lg p-2 text-[#9AA0AE] hover:bg-white/10 hover:text-[#E6E7EB] transition-colors ml-4"
            aria-label="Chiudi anteprima"
          >
            <X className="h-5 w-5" />
          </button>
        </DialogHeader>

        {/* Content */}
        <div className="flex-1 overflow-auto min-h-[300px] flex items-center justify-center bg-[#0c0c0e]">
          {loading && previewType !== 'unsupported' ? (
            <div className="flex flex-col items-center gap-3 text-[#9AA0AE]">
              <Loader2 className="h-8 w-8 animate-spin text-[#d4845a]" />
              <span className="text-sm">Caricamento...</span>
            </div>
          ) : previewError ? (
            <PreviewUnavailable file={file} onDownload={onDownload} />
          ) : (
            <>
              {/* Image */}
              {previewType === 'image' && mediaUrl && (
                <img
                  src={mediaUrl}
                  alt={file.name}
                  className="max-h-[70vh] max-w-full object-contain rounded-lg shadow-2xl"
                  onLoad={() => setLoading(false)}
                  onError={() => { setLoading(false); setPreviewError(true); }}
                  ref={(img) => { if (img?.complete) setLoading(false); }}
                />
              )}

              {/* PDF */}
              {previewType === 'pdf' && mediaUrl && (
                <iframe
                  src={`${mediaUrl}#view=FitH`}
                  className="w-full h-[70vh] rounded-lg bg-white shadow-2xl"
                  title={file.name}
                  onLoad={() => setLoading(false)}
                />
              )}

              {/* Text/Code */}
              {previewType === 'text' && textContent !== null && (
                <div className="w-full h-[60vh] overflow-auto p-4">
                  <pre className="text-xs text-[#E6E7EB] font-mono leading-relaxed whitespace-pre-wrap break-words">
                    {textContent}
                  </pre>
                </div>
              )}

              {/* Video */}
              {previewType === 'video' && mediaUrl && (
                <video
                  src={mediaUrl}
                  controls
                  className="max-h-[70vh] max-w-full rounded-lg shadow-2xl"
                  onLoadedData={() => setLoading(false)}
                  onError={() => { setLoading(false); setPreviewError(true); }}
                />
              )}

              {/* Audio */}
              {previewType === 'audio' && mediaUrl && (
                <div className="flex flex-col items-center gap-6 p-8">
                  <div className="flex h-24 w-24 items-center justify-center rounded-full bg-[#d4845a]/10">
                    <Music className="h-12 w-12 text-[#d4845a]" />
                  </div>
                  <p className="text-[#E6E7EB] font-medium">{file.name}</p>
                  <audio
                    src={mediaUrl}
                    controls
                    className="w-full max-w-md"
                    onLoadedData={() => setLoading(false)}
                    onError={() => { setLoading(false); setPreviewError(true); }}
                  />
                </div>
              )}

              {/* Google Docs */}
              {previewType === 'google-doc' && mediaUrl && (
                <iframe
                  src={mediaUrl}
                  className="w-full h-[70vh] rounded-lg bg-white shadow-2xl"
                  title={file.name}
                  onLoad={() => setLoading(false)}
                  allow="autoplay"
                />
              )}

              {/* Unsupported */}
              {previewType === 'unsupported' && (
                <PreviewUnavailable file={file} onDownload={onDownload} />
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="flex flex-row items-center justify-between px-5 py-3 border-t border-white/10 shrink-0">
          <div className="flex items-center gap-2">
            {file.web_view_link && (
              <a
                href={file.web_view_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-1.5 text-sm text-[#9AA0AE] hover:bg-white/10 hover:text-[#E6E7EB] transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                Apri in Drive
              </a>
            )}
          </div>
          <div className="flex items-center gap-2">
            {onDownload && !file.is_folder && (
              <button
                onClick={() => onDownload(file)}
                className="flex items-center gap-2 rounded-lg bg-[#d4845a] px-4 py-1.5 text-sm text-white hover:bg-[#bf7350] transition-colors"
              >
                <Download className="h-4 w-4" />
                Scarica
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded-lg border border-white/10 px-4 py-1.5 text-sm text-[#9AA0AE] hover:bg-white/10 hover:text-[#E6E7EB] transition-colors"
            >
              Chiudi
            </button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PreviewUnavailable({
  file,
  onDownload,
}: {
  file: FileItem;
  onDownload?: (file: FileItem) => void;
}) {
  return (
    <div className="flex flex-col items-center gap-5 p-12 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-white/5">
        <File className="h-10 w-10 text-[#9AA0AE]" />
      </div>
      <div>
        <p className="text-[#E6E7EB] font-medium">Anteprima non disponibile</p>
        <p className="text-sm text-[#9AA0AE] mt-1">
          Questo tipo di file non supporta l&apos;anteprima inline.
        </p>
      </div>
      {onDownload && (
        <button
          onClick={() => onDownload(file)}
          className="flex items-center gap-2 rounded-lg bg-[#d4845a] px-5 py-2 text-sm text-white hover:bg-[#bf7350] transition-colors"
        >
          <Download className="h-4 w-4" />
          Scarica il file
        </button>
      )}
    </div>
  );
}

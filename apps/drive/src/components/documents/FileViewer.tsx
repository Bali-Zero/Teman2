'use client';

import { useState, useEffect } from 'react';
import {
  X,
  Download,
  ExternalLink,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Loader2,
  FileText,
  Image as ImageIcon,
  Video,
  Music,
  File,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { api } from '@/lib/api';

interface FileViewerProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (file: FileItem) => void;
}

// Map MIME types to viewer types
type ViewerType = 'image' | 'video' | 'audio' | 'pdf' | 'google-doc' | 'unsupported';

function getViewerType(mimeType?: string): ViewerType {
  if (!mimeType) return 'unsupported';

  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (mimeType === 'application/pdf') return 'pdf';

  // Google Docs types
  if (
    mimeType === 'application/vnd.google-apps.document' ||
    mimeType === 'application/vnd.google-apps.spreadsheet' ||
    mimeType === 'application/vnd.google-apps.presentation' ||
    mimeType === 'application/vnd.google-apps.drawing'
  ) {
    return 'google-doc';
  }

  return 'unsupported';
}

function getFileTypeIcon(viewerType: ViewerType) {
  switch (viewerType) {
    case 'image':
      return ImageIcon;
    case 'video':
      return Video;
    case 'audio':
      return Music;
    case 'pdf':
    case 'google-doc':
      return FileText;
    default:
      return File;
  }
}

export function FileViewer({ file, isOpen, onClose, onDownload }: FileViewerProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);

  const viewerType = file ? getViewerType(file.mime_type) : 'unsupported';
  const FileIcon = getFileTypeIcon(viewerType);

  useEffect(() => {
    if (!isOpen || !file) {
      setLoading(true);
      setError(null);
      setMediaUrl(null);
      setZoom(100);
      setRotation(0);
      return;
    }

    // For images, keep loading state - will be cleared by onLoad/onError handlers
    if (viewerType === 'image') {
      const url = api.drive.getDownloadUrl(file.id);
      setMediaUrl(url);
      // Don't set loading=false here - let the img onLoad event handle it
    } else if (viewerType === 'video' || viewerType === 'audio') {
      const url = api.drive.getDownloadUrl(file.id);
      setMediaUrl(url);
      // Keep loading for video/audio - onLoadedData will clear it
    } else if (viewerType === 'pdf') {
      const url = api.drive.getDownloadUrl(file.id);
      setMediaUrl(url);
      // Keep loading for PDF - iframe onLoad will clear it
    } else if (viewerType === 'google-doc') {
      // For Google Docs, use the embedded viewer URL
      if (file.web_view_link) {
        // Convert edit link to preview/embed link
        const embedUrl = file.web_view_link
          .replace('/edit', '/preview')
          .replace('/view', '/preview');
        setMediaUrl(embedUrl);
        // Keep loading for iframe - onLoad will clear it
      } else {
        setError('Anteprima non disponibile');
        setLoading(false);
      }
    } else {
      setError("Tipo di file non supportato per l'anteprima");
      setLoading(false);
    }
  }, [file, isOpen, viewerType]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen || !file) return null;

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50));
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex flex-col">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/90 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Header */}
        <motion.div
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -50, opacity: 0 }}
          className="relative z-10 flex items-center justify-between border-b border-white/10 bg-black/50 px-4 py-3 backdrop-blur"
        >
          <div className="flex items-center gap-3">
            <FileIcon className="h-5 w-5 text-gray-300" />
            <h2 className="max-w-md truncate text-lg font-medium text-white">{file.name}</h2>
          </div>

          <div className="flex items-center gap-2">
            {/* Zoom controls for images */}
            {viewerType === 'image' && (
              <>
                <button
                  onClick={handleZoomOut}
                  className="rounded-lg p-2 text-gray-300 hover:bg-white/10 hover:text-white"
                  title="Zoom out"
                  aria-label="Zoom out"
                >
                  <ZoomOut className="h-5 w-5" />
                </button>
                <span className="text-sm text-gray-400">{zoom}%</span>
                <button
                  onClick={handleZoomIn}
                  className="rounded-lg p-2 text-gray-300 hover:bg-white/10 hover:text-white"
                  title="Zoom in"
                  aria-label="Zoom in"
                >
                  <ZoomIn className="h-5 w-5" />
                </button>
                <button
                  onClick={handleRotate}
                  className="rounded-lg p-2 text-gray-300 hover:bg-white/10 hover:text-white"
                  title="Ruota"
                  aria-label="Ruota immagine"
                >
                  <RotateCw className="h-5 w-5" />
                </button>
                <div className="mx-2 h-6 w-px bg-white/20" />
              </>
            )}

            {/* Download button */}
            {onDownload && viewerType !== 'google-doc' && (
              <button
                onClick={() => onDownload(file)}
                className="flex items-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-sm text-white hover:bg-white/20"
                aria-label={`Scarica ${file.name}`}
              >
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">Scarica</span>
              </button>
            )}

            {/* Open in new tab */}
            {file.web_view_link && (
              <button
                onClick={() => window.open(file.web_view_link, '_blank')}
                className="flex items-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-sm text-white hover:bg-white/20"
                title="Apri in nuova scheda"
              >
                <ExternalLink className="h-4 w-4" />
                <span className="hidden sm:inline">Apri</span>
              </button>
            )}

            {/* Close button */}
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-gray-300 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </motion.div>

        {/* Content */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative z-10 flex flex-1 items-center justify-center overflow-auto p-4"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          {loading ? (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-10 w-10 animate-spin text-emerald-500" />
              <p className="text-gray-400">Caricamento...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-red-500/10">
                <FileIcon className="h-10 w-10 text-red-400" />
              </div>
              <p className="text-lg text-gray-300">{error}</p>
              {file.web_view_link && (
                <button
                  onClick={() => window.open(file.web_view_link, '_blank')}
                  className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  Apri in Google Drive
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Image viewer */}
              {viewerType === 'image' && mediaUrl && (
                <div
                  className="flex items-center justify-center"
                  style={{
                    transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
                    transition: 'transform 0.2s ease-out',
                  }}
                >
                  <img
                    src={mediaUrl}
                    alt={file.name}
                    className="max-h-[80vh] max-w-full rounded-lg object-contain shadow-2xl"
                    onLoad={(e) => {
                      setLoading(false);
                    }}
                    onError={() => {
                      setLoading(false);
                      setError("Impossibile caricare l'immagine");
                    }}
                    ref={(img) => {
                      // Handle cached images that load instantly
                      if (img && img.complete) {
                        setLoading(false);
                      }
                    }}
                  />
                </div>
              )}

              {/* Video viewer */}
              {viewerType === 'video' && mediaUrl && (
                <video
                  src={mediaUrl}
                  controls
                  autoPlay
                  className="max-h-[80vh] max-w-full rounded-lg shadow-2xl"
                  onLoadedData={() => setLoading(false)}
                  onError={() => setError('Impossibile caricare il video')}
                >
                  Il tuo browser non supporta il tag video.
                </video>
              )}

              {/* Audio viewer */}
              {viewerType === 'audio' && mediaUrl && (
                <div className="flex flex-col items-center gap-6">
                  <div className="flex h-32 w-32 items-center justify-center rounded-full bg-emerald-500/10">
                    <Music className="h-16 w-16 text-emerald-400" />
                  </div>
                  <p className="text-lg text-white">{file.name}</p>
                  <audio
                    src={mediaUrl}
                    controls
                    autoPlay
                    className="w-full max-w-md"
                    onLoadedData={() => setLoading(false)}
                    onError={() => setError("Impossibile caricare l'audio")}
                  />
                </div>
              )}

              {/* PDF viewer */}
              {viewerType === 'pdf' && mediaUrl && (
                <iframe
                  src={`${mediaUrl}#view=FitH`}
                  className="h-[85vh] w-full max-w-5xl rounded-lg bg-white shadow-2xl"
                  title={file.name}
                  onLoad={() => setLoading(false)}
                />
              )}

              {/* Google Docs viewer */}
              {viewerType === 'google-doc' && mediaUrl && (
                <iframe
                  src={mediaUrl}
                  className="h-[85vh] w-full max-w-5xl rounded-lg bg-white shadow-2xl"
                  title={file.name}
                  onLoad={() => setLoading(false)}
                  allow="autoplay"
                />
              )}
            </>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

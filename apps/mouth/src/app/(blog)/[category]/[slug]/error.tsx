'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, RefreshCw, ArrowLeft } from 'lucide-react';
import { logger } from '@/lib/logger';

export default function ArticleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error('Article Error', {}, error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
        </div>
        <h2 className="text-2xl font-bold text-white mb-3">Couldn&apos;t load this article</h2>
        <p className="text-muted-cool mb-8">
          Something went wrong while loading the article. Please try again.
        </p>
        <div className="flex justify-center gap-3">
          <button
            onClick={() => reset()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent-blue-editorial text-white text-sm font-medium hover:bg-[#1a3fd9] transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-white/10 text-white text-sm font-medium hover:bg-white/5 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            All Articles
          </Link>
        </div>
      </div>
    </div>
  );
}

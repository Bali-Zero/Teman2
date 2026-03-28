'use client';

import { useEffect } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { logger } from '@/lib/logger';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error(`Page error: ${error.message}`, { component: 'ErrorBoundary' });
  }, [error]);

  return (
    <div className="flex h-full items-center justify-center bg-[#0c0c0e] p-8">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-7 w-7 text-red-400" />
        </div>
        <h2 className="text-lg font-semibold text-[#f1f1f1]">Qualcosa è andato storto</h2>
        <p className="text-sm text-[#f1f1f1]/50">
          Si è verificato un errore durante il caricamento di Drive. Riprova o torna alla home.
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-lg bg-[#d4845a] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#c0764e]"
          >
            <RefreshCw className="h-4 w-4" />
            Riprova
          </button>
          <a
            href="https://kita.balizero.com"
            className="inline-flex items-center rounded-lg border border-white/10 px-4 py-2 text-sm font-medium text-[#f1f1f1]/70 transition-colors hover:bg-white/5"
          >
            Torna alla home
          </a>
        </div>
      </div>
    </div>
  );
}

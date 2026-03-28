'use client';

import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex h-screen items-center justify-center bg-[#0c0c0e] p-8">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-7 w-7 text-red-400" />
        </div>
        <h2 className="text-lg font-semibold text-[#f1f1f1]">Qualcosa è andato storto</h2>
        <p className="text-sm text-[#f1f1f1]/50">
          Si è verificato un errore con Zantara Chat. Riprova.
        </p>
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 rounded-lg bg-[#d4845a] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#c0764e]"
        >
          <RefreshCw className="h-4 w-4" />
          Riprova
        </button>
      </div>
    </div>
  );
}

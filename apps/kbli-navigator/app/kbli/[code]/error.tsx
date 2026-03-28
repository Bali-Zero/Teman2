'use client';

import { useEffect } from 'react';
import Link from 'next/link';

export default function KBLICodeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('KBLI code page error:', error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center space-y-4">
      <p className="text-4xl">⚠️</p>
      <h2 className="text-xl font-semibold text-white">Code not available</h2>
      <p className="text-sm text-[var(--foreground-muted)] max-w-sm">
        Could not load this KBLI code. It may not exist or there was a temporary error.
      </p>
      <div className="flex gap-3 mt-2">
        <button
          type="button"
          onClick={reset}
          className="rounded-full border border-[#d4845a]/40 bg-[#d4845a]/10 px-4 py-2 text-sm font-medium text-[#d4845a] hover:bg-[#d4845a]/20 transition-all"
        >
          Try again
        </button>
        <Link
          href="/kbli"
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-white/10 transition-all"
        >
          Back to Navigator
        </Link>
      </div>
    </div>
  );
}

'use client';

export function StatusBar() {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-between px-6 py-2 pointer-events-none">
      <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
        SISMOGRAFO DEL POTERE v0.1
      </span>
      <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
        bolt://localhost:17687
      </span>
    </div>
  );
}

'use client';

import { CHAPTERS } from './book-data';

interface BookNavProps {
  activeChapter: string;
  onNavigate: (id: string) => void;
}

export function BookNav({ activeChapter, onNavigate }: BookNavProps) {
  const activeIndex = CHAPTERS.findIndex((c) => c.id === activeChapter);

  return (
    <>
      {/* Desktop sidebar — hidden on mobile */}
      <aside className="fixed left-6 top-1/2 -translate-y-1/2 z-50 hidden md:flex flex-col items-center gap-3">
        <div className="w-px bg-white/10 absolute left-1/2 -translate-x-1/2 top-0 bottom-0 -z-10" />
        <div
          className="w-px bg-[#d4845a] absolute left-1/2 -translate-x-1/2 top-0 origin-top transition-transform duration-500 -z-10"
          style={{
            transform: `scaleY(${activeIndex / (CHAPTERS.length - 1)})`,
            height: '100%',
          }}
        />
        {CHAPTERS.map((chapter) => (
          <button
            key={chapter.id}
            onClick={() => onNavigate(chapter.id)}
            aria-label={`Vai al capitolo: ${chapter.title}`}
            title={chapter.title}
            className={`w-2.5 h-2.5 rounded-full transition-all duration-300 border ${
              activeChapter === chapter.id
                ? 'bg-[#d4845a] border-[#d4845a] scale-125'
                : 'bg-transparent border-white/30 hover:border-white/60'
            }`}
          />
        ))}
      </aside>

      {/* Mobile bottom bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden flex items-center justify-between px-6 py-4 bg-[#0c0c0e]/90 backdrop-blur border-t border-white/10">
        <button
          onClick={() => {
            const prev = CHAPTERS[activeIndex - 1];
            if (prev) onNavigate(prev.id);
          }}
          disabled={activeIndex === 0}
          className="text-white/50 disabled:opacity-20 hover:text-white transition-colors text-xl"
          aria-label="Capitolo precedente"
        >
          ←
        </button>
        <span className="text-white/60 text-xs text-center">
          {activeIndex + 1} / {CHAPTERS.length}
          <br />
          <span className="text-white/40 text-[10px]">{CHAPTERS[activeIndex]?.id}</span>
        </span>
        <button
          onClick={() => {
            const next = CHAPTERS[activeIndex + 1];
            if (next) onNavigate(next.id);
          }}
          disabled={activeIndex === CHAPTERS.length - 1}
          className="text-white/50 disabled:opacity-20 hover:text-white transition-colors text-xl"
          aria-label="Capitolo successivo"
        >
          →
        </button>
      </nav>
    </>
  );
}

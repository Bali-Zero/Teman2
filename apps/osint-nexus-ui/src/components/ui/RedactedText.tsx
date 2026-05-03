'use client';

import { useState } from 'react';

interface RedactedTextProps {
  text: string;
  className?: string;
}

export function RedactedText({ text, className = '' }: RedactedTextProps) {
  const [revealed, setRevealed] = useState(false);

  return (
    <span
      className={`relative inline-block cursor-pointer select-none ${className}`}
      onMouseEnter={() => setRevealed(true)}
      onMouseLeave={() => setRevealed(false)}
    >
      <span
        className="transition-colors duration-300"
        style={{ color: revealed ? 'var(--sg-copper)' : 'transparent' }}
      >
        {text}
      </span>
      <span
        className="absolute inset-0 bg-[var(--sg-text-redacted)] transition-all duration-300"
        style={{
          transform: revealed ? 'translateX(110%)' : 'translateX(0)',
        }}
        onMouseEnter={(e) => {
          const el = e.currentTarget;
          el.style.animation = 'redacted-glitch 150ms ease-out';
          setTimeout(() => { el.style.animation = ''; }, 150);
        }}
      />
    </span>
  );
}

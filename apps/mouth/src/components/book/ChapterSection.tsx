'use client';

import { useEffect, useRef } from 'react';
import { useBookShell } from './BookShell';

interface ChapterSectionProps {
  id: string;
  children: React.ReactNode;
  className?: string;
}

export function ChapterSection({ id, children, className = '' }: ChapterSectionProps) {
  const ref = useRef<HTMLElement>(null);
  const { onVisible } = useBookShell();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onVisible(id);
      },
      { threshold: 0.4 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [id, onVisible]);

  return (
    <section
      ref={ref}
      id={id}
      data-chapter={id}
      className={`min-h-screen relative ${className}`}
      style={{ contentVisibility: 'auto', containIntrinsicSize: '0 100vh' } as React.CSSProperties}
    >
      {children}
    </section>
  );
}

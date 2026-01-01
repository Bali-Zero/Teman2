'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { List } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TableOfContentsProps } from '@/lib/blog/types';

interface TocItem {
  id: string;
  text: string;
  level: number;
}

// Extract headings from MDX content
function extractHeadings(content: string): TocItem[] {
  const headingRegex = /^(#{2,4})\s+(.+)$/gm;
  const headings: TocItem[] = [];
  let match;

  while ((match = headingRegex.exec(content)) !== null) {
    const level = match[1].length;
    const text = match[2].trim();
    // Generate ID from heading text
    const id = text
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-');

    headings.push({ id, text, level });
  }

  return headings;
}

export function TableOfContents({ content, className }: TableOfContentsProps) {
  const [activeId, setActiveId] = React.useState<string>('');
  const [isExpanded, setIsExpanded] = React.useState(true);
  const headings = React.useMemo(() => extractHeadings(content), [content]);

  // Intersection observer to track active heading
  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        });
      },
      {
        rootMargin: '-80px 0px -80% 0px',
        threshold: 0,
      }
    );

    // Observe all heading elements
    headings.forEach((heading) => {
      const element = document.getElementById(heading.id);
      if (element) {
        observer.observe(element);
      }
    });

    return () => observer.disconnect();
  }, [headings]);

  // Scroll to heading
  const scrollToHeading = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100;
      const bodyRect = document.body.getBoundingClientRect().top;
      const elementRect = element.getBoundingClientRect().top;
      const elementPosition = elementRect - bodyRect;
      const offsetPosition = elementPosition - offset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth',
      });
    }
  };

  if (headings.length === 0) {
    return null;
  }

  return (
    <nav className={cn('relative', className)}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-white/60 hover:text-white transition-colors mb-4"
      >
        <List className="w-4 h-4" />
        Table of Contents
      </button>

      {/* TOC list */}
      <motion.div
        initial={false}
        animate={{ height: isExpanded ? 'auto' : 0, opacity: isExpanded ? 1 : 0 }}
        className="overflow-hidden"
      >
        <ul className="space-y-1 border-l border-white/10">
          {headings.map((heading, index) => {
            const isActive = activeId === heading.id;
            const indent = (heading.level - 2) * 12;

            return (
              <motion.li
                key={heading.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <button
                  onClick={() => scrollToHeading(heading.id)}
                  className={cn(
                    'block w-full text-left py-1.5 pl-4 text-sm transition-all duration-200 border-l-2 -ml-[2px]',
                    isActive
                      ? 'text-violet-400 border-violet-400 bg-violet-400/5'
                      : 'text-white/50 border-transparent hover:text-white hover:border-white/30'
                  )}
                  style={{ paddingLeft: `${16 + indent}px` }}
                >
                  {heading.text}
                </button>
              </motion.li>
            );
          })}
        </ul>
      </motion.div>
    </nav>
  );
}

// Floating TOC for mobile
export function FloatingToc({ content }: { content: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const headings = React.useMemo(() => extractHeadings(content), [content]);

  if (headings.length === 0) {
    return null;
  }

  const scrollToHeading = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100;
      const bodyRect = document.body.getBoundingClientRect().top;
      const elementRect = element.getBoundingClientRect().top;
      const elementPosition = elementRect - bodyRect;
      const offsetPosition = elementPosition - offset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth',
      });
      setIsOpen(false);
    }
  };

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'fixed bottom-4 right-4 z-40 p-3 rounded-full shadow-lg',
          'bg-violet-600 text-white',
          'hover:bg-violet-500 transition-colors',
          'md:hidden'
        )}
      >
        <List className="w-5 h-5" />
      </button>

      {/* Drawer */}
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 md:hidden"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          {/* Drawer content */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            className="absolute bottom-0 left-0 right-0 max-h-[60vh] bg-zinc-900 border-t border-white/10 rounded-t-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
              <span className="text-sm font-medium text-white">
                Table of Contents
              </span>
              <button
                onClick={() => setIsOpen(false)}
                className="text-white/60 hover:text-white"
              >
                Close
              </button>
            </div>

            {/* List */}
            <ul className="p-4 space-y-2 overflow-y-auto max-h-[calc(60vh-60px)]">
              {headings.map((heading) => {
                const indent = (heading.level - 2) * 12;

                return (
                  <li key={heading.id}>
                    <button
                      onClick={() => scrollToHeading(heading.id)}
                      className="w-full text-left py-2 px-3 rounded-lg text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                      style={{ paddingLeft: `${12 + indent}px` }}
                    >
                      {heading.text}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </>
  );
}

// Reading progress bar
export function ReadingProgress({ className }: { className?: string }) {
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    const updateProgress = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const newProgress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      setProgress(Math.min(100, Math.max(0, newProgress)));
    };

    window.addEventListener('scroll', updateProgress, { passive: true });
    updateProgress();

    return () => window.removeEventListener('scroll', updateProgress);
  }, []);

  return (
    <div className={cn('fixed top-0 left-0 right-0 z-50 h-1 bg-white/5', className)}>
      <motion.div
        className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
        style={{ width: `${progress}%` }}
        initial={{ width: 0 }}
        transition={{ duration: 0.1 }}
      />
    </div>
  );
}

export { extractHeadings };

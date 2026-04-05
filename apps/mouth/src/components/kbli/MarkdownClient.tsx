'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import type { Components } from 'react-markdown';

const ReactMarkdown = dynamic(() => import('react-markdown'), { ssr: false });

const kbliComponents: Components = {
  a: ({ href, children }) => {
    if (href?.startsWith('/kbli/')) {
      return (
        <Link
          href={href}
          className="inline-flex items-center gap-1 font-mono font-bold text-[var(--kbli-accent)] transition-colors hover:text-[var(--kbli-accent-hover)]"
        >
          {children}
          <span className="text-[10px] opacity-50">→</span>
        </Link>
      );
    }
    return <a href={href}>{children}</a>;
  },
};

interface MarkdownClientProps {
  children: string;
  withKbliLinks?: boolean;
}

export function MarkdownClient({ children, withKbliLinks }: MarkdownClientProps) {
  return (
    <ReactMarkdown components={withKbliLinks ? kbliComponents : undefined}>
      {children}
    </ReactMarkdown>
  );
}

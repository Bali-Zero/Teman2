'use client';

import { MDXRemote, MDXRemoteSerializeResult } from 'next-mdx-remote';
import Image from 'next/image';
import Link from 'next/link';

// Import all interactive components
import {
  DecisionTree,
  Calculator,
  ComparisonTable,
  JourneyMap,
  LegalDecoder,
  AskZantara,
  ConfidenceMeter,
  Checklist,
  InfoCard,
  GlossaryTerm,
} from '@/components/blog/interactive';

// Custom components for MDX
const mdxComponents = {
  // Interactive blog components
  DecisionTree,
  Calculator,
  ComparisonTable,
  JourneyMap,
  LegalDecoder,
  AskZantara,
  ConfidenceMeter,
  Checklist,
  InfoCard,
  GlossaryTerm,

  // Override default HTML elements with styled versions
  h1: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="font-serif text-3xl md:text-4xl font-bold text-white mt-12 mb-6 first:mt-0" {...props} />
  ),
  h2: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="font-serif text-2xl md:text-3xl font-bold text-white mt-10 mb-4 scroll-mt-24" {...props} />
  ),
  h3: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="font-serif text-xl md:text-2xl font-semibold text-white mt-8 mb-3 scroll-mt-24" {...props} />
  ),
  h4: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h4 className="font-semibold text-lg text-white mt-6 mb-2" {...props} />
  ),
  p: (props: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="text-white/80 leading-relaxed mb-4" {...props} />
  ),
  a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    const href = props.href || '';
    const isExternal = href.startsWith('http');

    if (isExternal) {
      return (
        <a
          className="text-[#2251ff] hover:text-[#4d73ff] underline underline-offset-2 transition-colors"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        />
      );
    }

    return (
      <Link
        href={href}
        className="text-[#2251ff] hover:text-[#4d73ff] underline underline-offset-2 transition-colors"
      >
        {props.children}
      </Link>
    );
  },
  ul: (props: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc list-outside ml-6 mb-4 space-y-2 text-white/80" {...props} />
  ),
  ol: (props: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal list-outside ml-6 mb-4 space-y-2 text-white/80" {...props} />
  ),
  li: (props: React.LiHTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed pl-2" {...props} />
  ),
  blockquote: (props: React.BlockquoteHTMLAttributes<HTMLQuoteElement>) => (
    <blockquote className="border-l-4 border-[#2251ff] pl-6 py-2 my-6 italic text-white/70 bg-white/5 rounded-r-lg" {...props} />
  ),
  code: (props: React.HTMLAttributes<HTMLElement>) => {
    // Check if it's inline code or code block
    const isInline = !props.className;

    if (isInline) {
      return (
        <code className="px-1.5 py-0.5 bg-white/10 rounded text-[#ff6b6b] font-mono text-sm" {...props} />
      );
    }

    return <code className="font-mono text-sm" {...props} />;
  },
  pre: (props: React.HTMLAttributes<HTMLPreElement>) => (
    <pre className="bg-[#0a1929] border border-white/10 rounded-xl p-4 overflow-x-auto my-6 text-sm" {...props} />
  ),
  table: (props: React.TableHTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto my-6 rounded-xl border border-white/10">
      <table className="w-full text-left" {...props} />
    </div>
  ),
  thead: (props: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="bg-white/5 border-b border-white/10" {...props} />
  ),
  tbody: (props: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <tbody className="divide-y divide-white/5" {...props} />
  ),
  tr: (props: React.HTMLAttributes<HTMLTableRowElement>) => (
    <tr className="hover:bg-white/5 transition-colors" {...props} />
  ),
  th: (props: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-white/60" {...props} />
  ),
  td: (props: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="px-4 py-3 text-white/80" {...props} />
  ),
  hr: () => (
    <hr className="my-8 border-white/10" />
  ),
  strong: (props: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-semibold text-white" {...props} />
  ),
  em: (props: React.HTMLAttributes<HTMLElement>) => (
    <em className="italic text-white/90" {...props} />
  ),
  img: (props: React.ImgHTMLAttributes<HTMLImageElement>) => {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <span className="block my-6">
        <img
          className="rounded-xl w-full"
          loading="lazy"
          alt={props.alt || ''}
          {...props}
        />
        {props.alt && (
          <span className="block text-center text-sm text-white/50 mt-2">
            {props.alt}
          </span>
        )}
      </span>
    );
  },
  // Next.js Image component for MDX
  Image: (props: React.ComponentProps<typeof Image>) => (
    <span className="block my-6">
      <Image className="rounded-xl" {...props} />
    </span>
  ),
};

interface MDXContentProps {
  source: MDXRemoteSerializeResult;
}

export function MDXContent({ source }: MDXContentProps) {
  return (
    <div className="mdx-content">
      <MDXRemote {...source} components={mdxComponents} />
    </div>
  );
}

export { mdxComponents };

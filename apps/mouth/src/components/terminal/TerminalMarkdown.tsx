/**
 * TerminalMarkdown — ReactMarkdown wrapper styled for the terminal.
 *
 * Wraps react-markdown + remark-gfm with custom components matching Warm
 * Depth tokens. Code blocks use plain <pre>/<code> (react-syntax-highlighter
 * is not installed in this app). Links are opened in a new tab and styled
 * in the accent colour.
 */

"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";
import remarkGfm from "remark-gfm";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

interface TerminalMarkdownProps {
  children: string;
}

export function TerminalMarkdown({ children }: TerminalMarkdownProps) {
  return (
    <div className="terminal-md text-[13.5px] leading-relaxed text-white/90">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children: c }: { children?: ReactNode }) => (
            <p className="mb-2 last:mb-0">{c}</p>
          ),
          ul: ({ children: c }: { children?: ReactNode }) => (
            <ul className="list-disc ml-5 mb-2 space-y-1">{c}</ul>
          ),
          ol: ({ children: c }: { children?: ReactNode }) => (
            <ol className="list-decimal ml-5 mb-2 space-y-1">{c}</ol>
          ),
          li: ({ children: c }: { children?: ReactNode }) => (
            <li className="text-white/90">{c}</li>
          ),
          strong: ({ children: c }: { children?: ReactNode }) => (
            <strong className="font-semibold text-white">{c}</strong>
          ),
          em: ({ children: c }: { children?: ReactNode }) => (
            <em className="italic text-white/85">{c}</em>
          ),
          h1: ({ children: c }: { children?: ReactNode }) => (
            <h1 className="text-base font-semibold text-white mb-2 mt-3 first:mt-0">
              {c}
            </h1>
          ),
          h2: ({ children: c }: { children?: ReactNode }) => (
            <h2 className="text-[14.5px] font-semibold text-white mb-2 mt-3 first:mt-0">
              {c}
            </h2>
          ),
          h3: ({ children: c }: { children?: ReactNode }) => (
            <h3 className="text-[13.5px] font-semibold text-white mb-1.5 mt-2 first:mt-0">
              {c}
            </h3>
          ),
          a: ({ children: c, href }: { children?: ReactNode; href?: string }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--bz-accent)] hover:text-[var(--bz-accent-hover)] underline underline-offset-2 transition-colors"
            >
              {c}
            </a>
          ),
          code: ({
            children: c,
            className,
          }: {
            children?: ReactNode;
            className?: string;
          }) => {
            const isBlock = Boolean(className);
            if (isBlock) {
              return (
                <code
                  className={`block font-mono text-[12.5px] leading-relaxed text-white/90 ${className ?? ""}`}
                >
                  {c}
                </code>
              );
            }
            return (
              <code className="px-1.5 py-0.5 rounded bg-white/10 border border-white/10 font-mono text-[12px] text-[var(--bz-accent-warm)]">
                {c}
              </code>
            );
          },
          pre: ({ children: c }: { children?: ReactNode }) => (
            <pre className="my-3 rounded-lg border border-white/10 bg-black/40 px-3 py-2.5 overflow-x-auto font-mono text-[12.5px] leading-relaxed text-white/90">
              {c}
            </pre>
          ),
          blockquote: ({ children: c }: { children?: ReactNode }) => (
            <blockquote className="my-2 border-l-2 border-[var(--bz-accent)]/60 pl-3 text-white/75 italic">
              {c}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-white/10" />,
          table: ({ children: c }: { children?: ReactNode }) => (
            <div className="my-3 overflow-x-auto rounded-lg border border-white/10">
              <table className="min-w-full text-[12.5px]">{c}</table>
            </div>
          ),
          thead: ({ children: c }: { children?: ReactNode }) => (
            <thead className="bg-white/5 text-white/80">{c}</thead>
          ),
          th: ({ children: c }: { children?: ReactNode }) => (
            <th className="px-3 py-2 text-left font-semibold border-b border-white/10">
              {c}
            </th>
          ),
          td: ({ children: c }: { children?: ReactNode }) => (
            <td className="px-3 py-2 border-b border-white/5 text-white/85">
              {c}
            </td>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

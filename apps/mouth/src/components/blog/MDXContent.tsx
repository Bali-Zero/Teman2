import { MDXRemote, MDXRemoteSerializeResult } from "next-mdx-remote";
import Image from "next/image";
import Link from "next/link";
import { cloneElement, isValidElement, type ReactNode } from "react";

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
  AnswerBox,
  KeyTakeaway,
} from "@/components/blog/interactive";
import { ArticleToolEmbed } from "@/components/blog/ArticleToolEmbed";
import { ArticleClusterCTA } from "@/components/blog/ArticleClusterCTA";
import { HeaderWhatsAppCTA as FunnelHeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";

// Blog MDX wrapper — funnel optional, defaults "tax" for article context
// TODO Phase 2: pipe category through MDXContent for accurate funnel attribution
function HeaderWhatsAppCTA({
  funnel = "tax" as const,
}: {
  funnel?: "tax" | "property" | "visa" | "kbli";
}) {
  return <FunnelHeaderWhatsAppCTA funnel={funnel} />;
}

// The `pre` mapping clones its `code` child with this marker so the `code`
// mapping can tell a fenced block with NO language (no className) apart from
// real inline code in a paragraph (also no className) — see the `code`/`pre`
// entries below (C3).
const PRE_CODE_MARKER = "data-mdx-pre-code";

function markPreChildAsBlock(children: ReactNode): ReactNode {
  if (isValidElement(children)) {
    return cloneElement(
      children as React.ReactElement<Record<string, unknown>>,
      {
        [PRE_CODE_MARKER]: true,
      },
    );
  }
  return children;
}

// Generate a URL-friendly ID from heading text (must match TableOfContents.tsx logic)
function headingId(children: React.ReactNode): string {
  const text =
    typeof children === "string"
      ? children
      : Array.isArray(children)
        ? children.map((c) => (typeof c === "string" ? c : "")).join("")
        : "";
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
}

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
  CheckList: Checklist,
  InfoCard,
  GlossaryTerm,
  AnswerBox,
  KeyTakeaway,
  ArticleToolEmbed,
  ArticleClusterCTA,
  HeaderWhatsAppCTA,

  // Override default HTML elements with styled versions (30% larger text)
  // Headings get auto-generated IDs matching TOC extraction logic.
  // R19: headings ink, Fraunces, weight 400-500 (never bold-black); body
  // Manrope ink/muted; accent is copper only. Colors are `--r19-*` tokens —
  // on the article route the ancestor `.rumah-putih .mdx-content …` rules in
  // globals.css (out of this lane) also retint several of these tags with
  // `!important` (headings/paragraphs/blockquote/code/pre/table); these
  // inline values are the correct source and the fallback for any consumer
  // outside that wrapper.
  h1: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1
      className="font-serif font-medium tracking-tight mt-12 mb-6 first:mt-0 text-4xl md:text-5xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2
      id={headingId(children)}
      className="font-serif font-medium tracking-tight mt-10 mb-4 scroll-mt-24 text-3xl md:text-4xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3
      id={headingId(children)}
      className="font-serif font-medium tracking-tight mt-8 mb-3 scroll-mt-24 text-2xl md:text-3xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    >
      {children}
    </h3>
  ),
  h4: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h4
      className="font-sans font-semibold mt-6 mb-2 text-xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  h5: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h5
      className="font-sans font-semibold mt-5 mb-2 text-lg"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  h6: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h6
      className="font-sans font-semibold mt-5 mb-2 text-base uppercase tracking-wide"
      style={{ color: "var(--r19-muted)" }}
      {...props}
    />
  ),
  p: (props: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p
      className="leading-relaxed mb-5 text-xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    const href = props.href || "";
    const isExternal = href.startsWith("http");
    const className =
      "text-[color:var(--r19-copper)] underline underline-offset-2 transition-opacity hover:opacity-75";

    if (isExternal) {
      return (
        <a
          className={className}
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        />
      );
    }

    return (
      <Link href={href} className={className}>
        {props.children}
      </Link>
    );
  },
  ul: (props: React.HTMLAttributes<HTMLUListElement>) => (
    <ul
      className="list-disc list-outside ml-6 mb-5 space-y-3 text-xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  ol: (props: React.HTMLAttributes<HTMLOListElement>) => (
    <ol
      className="list-decimal list-outside ml-6 mb-5 space-y-3 text-xl"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  li: (props: React.LiHTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed pl-2 text-xl" {...props} />
  ),
  blockquote: (props: React.BlockquoteHTMLAttributes<HTMLQuoteElement>) => (
    <blockquote
      className="border-l-2 pl-6 py-3 my-6 italic rounded-r-[8px] text-xl"
      style={{
        borderLeftColor: "var(--r19-copper)",
        color: "var(--r19-muted)",
        background: "var(--r19-wash)",
      }}
      {...props}
    />
  ),
  code: ({
    [PRE_CODE_MARKER]: isBlockMarker,
    ...props
  }: React.HTMLAttributes<HTMLElement> & { [PRE_CODE_MARKER]?: boolean }) => {
    // A fenced block with no language has no className, same as real inline
    // code in a paragraph — the marker the `pre` mapping attaches below is
    // what tells the two apart (C3).
    const isInline = !props.className && !isBlockMarker;

    if (isInline) {
      return (
        <code
          className="px-1.5 py-0.5 rounded font-mono text-base"
          style={{ background: "var(--r19-wash)", color: "var(--r19-ink)" }}
          {...props}
        />
      );
    }

    return <code className="font-mono text-base" {...props} />;
  },
  pre: ({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) => (
    <pre
      className="rounded-[8px] border p-4 overflow-x-auto my-6 text-base"
      style={{ background: "var(--r19-wash)", borderColor: "var(--r19-line)" }}
      {...props}
    >
      {markPreChildAsBlock(children)}
    </pre>
  ),
  table: (props: React.TableHTMLAttributes<HTMLTableElement>) => (
    <div
      className="overflow-x-auto my-6 rounded-[8px] border"
      style={{ borderColor: "var(--r19-line)" }}
    >
      <table className="w-full text-left" {...props} />
    </div>
  ),
  thead: (props: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead
      className="border-b"
      style={{ background: "var(--r19-wash)", borderColor: "var(--r19-line)" }}
      {...props}
    />
  ),
  tbody: (props: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <tbody className="divide-y divide-[color:var(--r19-line)]" {...props} />
  ),
  tr: (props: React.HTMLAttributes<HTMLTableRowElement>) => (
    <tr
      className="transition-colors hover:bg-[color:var(--r19-wash)]"
      {...props}
    />
  ),
  th: (props: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th
      className="px-4 py-3 text-sm font-semibold uppercase tracking-wider"
      style={{ color: "var(--r19-muted)" }}
      {...props}
    />
  ),
  td: (props: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td
      className="px-4 py-3 text-lg"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  hr: () => <hr className="my-8" style={{ borderColor: "var(--r19-line)" }} />,
  strong: (props: React.HTMLAttributes<HTMLElement>) => (
    <strong
      className="font-semibold"
      style={{ color: "var(--r19-ink)" }}
      {...props}
    />
  ),
  em: (props: React.HTMLAttributes<HTMLElement>) => (
    <em className="italic" style={{ color: "var(--r19-ink)" }} {...props} />
  ),
  img: (props: React.ImgHTMLAttributes<HTMLImageElement>) => {
    return (
      <span className="block my-6">
        <img
          className="rounded-[8px] w-full border"
          style={{ borderColor: "var(--r19-line)" }}
          loading="lazy"
          alt={props.alt || ""}
          {...props}
        />
        {props.alt && (
          <span
            className="block text-center text-sm mt-2"
            style={{ color: "var(--r19-muted)" }}
          >
            {props.alt}
          </span>
        )}
      </span>
    );
  },
  // Next.js Image component for MDX
  Image: (props: React.ComponentProps<typeof Image>) => (
    <span className="block my-6">
      <Image
        className="rounded-[8px] border"
        style={{ borderColor: "var(--r19-line)" }}
        {...props}
      />
    </span>
  ),
};

interface MDXContentProps {
  source: MDXRemoteSerializeResult;
}

export function MDXContent({ source }: MDXContentProps) {
  return (
    <div
      className="mdx-content"
      style={{ fontSize: "1.3rem", lineHeight: "1.8" }}
    >
      <MDXRemote {...source} components={mdxComponents} />
    </div>
  );
}

export { mdxComponents };

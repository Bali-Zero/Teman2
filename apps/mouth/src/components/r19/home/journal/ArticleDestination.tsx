import type { ReactNode } from "react";
import type { JournalArticle } from "./types";

export function ArticleDestination({
  article,
  children,
  className,
  id,
  inline = false,
}: {
  article: JournalArticle;
  children: ReactNode;
  className?: string;
  id?: string;
  inline?: boolean;
}) {
  const Tag = inline ? "span" : "div";
  return article.destinationStatus === "unavailable" ? (
    <Tag className={className} id={id}>
      {children}
    </Tag>
  ) : (
    <a
      className={className}
      id={id}
      href={article.localHref ?? article.finalSourceUrl ?? article.sourceUrl}
    >
      {children}
    </a>
  );
}

import ReactMarkdown from "react-markdown";
import { dataText, parseArticle, type ReadingDocument, type ReadingNode } from "./article-model";
import { SafeArticleComponent } from "./ArticleComponents";
import { ArticleGlossary } from "./ArticleGlossary";
import { safeArticleImage, safeArticleUrl } from "./article-urls";
import styles from "./ArticleReader.module.css";
export { safeArticleUrl } from "./article-urls";

export function ReadingNodes({ nodes, articleUrl, articleTitle }: { nodes: ReadingNode[]; articleUrl: string; articleTitle: string }) {
  return nodes.map((node, index) => node.kind === "component"
    ? <SafeArticleComponent key={`${node.offset}-${index}`} node={node} articleUrl={articleUrl} articleTitle={articleTitle}><ReadingNodes nodes={node.children} articleUrl={articleUrl} articleTitle={articleTitle} /></SafeArticleComponent>
    : <ReactMarkdown key={`${node.offset}-${index}`} remarkPlugins={[() => () => node.tree]} skipHtml urlTransform={safeArticleUrl} components={{
      table: ({ children }) => <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Article table"><table>{children}</table></div>,
      img: ({ src, alt }) => typeof src === "string" && safeArticleImage(src) ? <img src={safeArticleImage(src)} alt={alt ?? ""} loading="lazy" /> : <span className={styles.mediaNote}>{alt ? `Image: ${alt}. ` : ""}This image is not available in this edition.</span>,
      a: ({ href, children }) => href ? <a href={href}>{children}</a> : <span>{children}</span>,
      span: ({ node: element, children, ...props }) => {
        const id = typeof element?.properties.id === "string" ? element.properties.id : "";
        const linked = id.startsWith("linked-");
        const glossary = node.inlineGlossaries?.[linked ? id.slice(7) : id];
        if (!glossary) return <span {...props}>{children}</span>;
        const label = typeof children === "string" ? children : dataText(glossary.props.term);
        const definition = dataText(glossary.props.definition);
        if (linked) return <abbr title={definition || undefined}>{children}</abbr>;
        return <ArticleGlossary label={label} definition={definition} indonesian={dataText(glossary.props.indonesian)} related={Array.isArray(glossary.props.relatedTerms) ? glossary.props.relatedTerms.filter((item): item is string => typeof item === "string").slice(0, 20) : []} />;
      },
    }}>{node.source}</ReactMarkdown>);
}

export function ArticleBody({ source, originalUrl, document, title = "Bali Zero Journal article" }: { source: string; originalUrl: string; document?: ReadingDocument; title?: string }) {
  return <div className={styles.prose} data-article-body><ReadingNodes nodes={(document ?? parseArticle(source)).nodes} articleUrl={originalUrl} articleTitle={title} /></div>;
}

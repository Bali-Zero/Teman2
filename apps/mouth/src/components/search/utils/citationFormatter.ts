import { KnowledgeSearchResult } from '@/lib/api';

export function formatCitation(result: KnowledgeSearchResult): string {
  const title = result.metadata.book_title || 'Untitled';
  const author = result.metadata.book_author || 'Unknown';
  const tier = result.metadata.tier || 'C';
  const page =
    typeof result.metadata.page_number === 'number' ? `p.${result.metadata.page_number}` : 'p.?';
  const scorePct = Number.isFinite(result.similarity_score)
    ? `${Math.round(result.similarity_score * 100)}%`
    : '?';

  const file = result.metadata.file_path ? `\nFile: ${result.metadata.file_path}` : '';

  return `Source: ${title} — ${author} (${tier}, ${page}, ${scorePct})${file}\nExcerpt: ${result.text}`;
}

export function buildSourcesBlock(results: KnowledgeSearchResult[]): string {
  const lines: string[] = [];
  results.forEach((r, idx) => {
    lines.push(`\n[${idx + 1}]\n${formatCitation(r)}\n`);
  });
  return lines.join('\n');
}


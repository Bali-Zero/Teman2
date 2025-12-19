import { describe, it, expect } from 'vitest';
import { formatCitation, buildSourcesBlock } from './citationFormatter';
import type { KnowledgeSearchResult } from '@/lib/api';

describe('citationFormatter', () => {
  describe('formatCitation', () => {
    it('should format citation with all fields', () => {
      const result: KnowledgeSearchResult = {
        text: 'This is the excerpt text',
        similarity_score: 0.95,
        metadata: {
          book_title: 'Test Book',
          book_author: 'Test Author',
          tier: 'A',
          page_number: 42,
          file_path: '/path/to/file.pdf',
        },
      };

      const citation = formatCitation(result);
      expect(citation).toContain('Test Book');
      expect(citation).toContain('Test Author');
      expect(citation).toContain('A');
      expect(citation).toContain('p.42');
      expect(citation).toContain('95%');
      expect(citation).toContain('/path/to/file.pdf');
      expect(citation).toContain('This is the excerpt text');
    });

    it('should handle missing optional fields', () => {
      const result: KnowledgeSearchResult = {
        text: 'Excerpt text',
        similarity_score: 0.8,
        metadata: {
          book_title: 'Test Book',
        },
      };

      const citation = formatCitation(result);
      expect(citation).toContain('Test Book');
      expect(citation).toContain('Unknown');
      expect(citation).toContain('C');
      expect(citation).toContain('p.?');
      expect(citation).toContain('80%');
      expect(citation).not.toContain('File:');
    });

    it('should handle invalid similarity score', () => {
      const result: KnowledgeSearchResult = {
        text: 'Excerpt',
        similarity_score: NaN,
        metadata: {
          book_title: 'Test',
        },
      };

      const citation = formatCitation(result);
      expect(citation).toContain('?');
    });
  });

  describe('buildSourcesBlock', () => {
    it('should build sources block with multiple results', () => {
      const results: KnowledgeSearchResult[] = [
        {
          text: 'First excerpt',
          similarity_score: 0.9,
          metadata: {
            book_title: 'Book 1',
            book_author: 'Author 1',
            tier: 'A',
            page_number: 1,
          },
        },
        {
          text: 'Second excerpt',
          similarity_score: 0.85,
          metadata: {
            book_title: 'Book 2',
            book_author: 'Author 2',
            tier: 'B',
            page_number: 2,
          },
        },
      ];

      const block = buildSourcesBlock(results);
      expect(block).toContain('[1]');
      expect(block).toContain('[2]');
      expect(block).toContain('Book 1');
      expect(block).toContain('Book 2');
      expect(block).toContain('First excerpt');
      expect(block).toContain('Second excerpt');
    });

    it('should handle empty results array', () => {
      const results: KnowledgeSearchResult[] = [];
      const block = buildSourcesBlock(results);
      expect(block).toBe('');
    });

    it('should number sources sequentially', () => {
      const results: KnowledgeSearchResult[] = [
        {
          text: 'First',
          similarity_score: 0.9,
          metadata: { book_title: 'Book 1' },
        },
        {
          text: 'Second',
          similarity_score: 0.8,
          metadata: { book_title: 'Book 2' },
        },
        {
          text: 'Third',
          similarity_score: 0.7,
          metadata: { book_title: 'Book 3' },
        },
      ];

      const block = buildSourcesBlock(results);
      const lines = block.split('\n');
      expect(lines.filter((l) => l.includes('[1]')).length).toBeGreaterThan(0);
      expect(lines.filter((l) => l.includes('[2]')).length).toBeGreaterThan(0);
      expect(lines.filter((l) => l.includes('[3]')).length).toBeGreaterThan(0);
    });
  });
});


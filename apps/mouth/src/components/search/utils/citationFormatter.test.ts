import { describe, it, expect } from 'vitest';
import { formatCitation, buildSourcesBlock } from './citationFormatter';
import type { KnowledgeSearchResult } from '@/lib/api';
import { TierLevel } from '@/lib/api';

describe('citationFormatter', () => {
  describe('formatCitation', () => {
    it('should format citation with all fields', () => {
      const result: KnowledgeSearchResult = {
        text: 'This is the excerpt text',
        similarity_score: 0.95,
        metadata: {
          book_title: 'Test Book',
          book_author: 'Test Author',
          tier: TierLevel.A,
          min_level: 1,
          chunk_index: 0,
          page_number: 42,
          file_path: '/path/to/file.pdf',
          total_chunks: 100,
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
          book_author: 'Unknown Author',
          tier: TierLevel.C,
          min_level: 1,
          chunk_index: 0,
          file_path: '/path/to/test.pdf',
          total_chunks: 1,
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
          book_author: 'Test Author',
          tier: TierLevel.C,
          min_level: 1,
          chunk_index: 0,
          file_path: '/path/to/test.pdf',
          total_chunks: 1,
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
            tier: TierLevel.A,
            min_level: 1,
            chunk_index: 0,
            page_number: 1,
            file_path: '/path/to/book1.pdf',
            total_chunks: 100,
          },
        },
        {
          text: 'Second excerpt',
          similarity_score: 0.85,
          metadata: {
            book_title: 'Book 2',
            book_author: 'Author 2',
            tier: TierLevel.B,
            min_level: 1,
            chunk_index: 0,
            page_number: 2,
            file_path: '/path/to/book2.pdf',
            total_chunks: 50,
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
          metadata: {
            book_title: 'Book 1',
            book_author: 'Author 1',
            tier: TierLevel.A,
            min_level: 1,
            chunk_index: 0,
            file_path: '/path/to/book1.pdf',
            total_chunks: 100,
          },
        },
        {
          text: 'Second',
          similarity_score: 0.8,
          metadata: {
            book_title: 'Book 2',
            book_author: 'Author 2',
            tier: TierLevel.B,
            min_level: 1,
            chunk_index: 0,
            file_path: '/path/to/book2.pdf',
            total_chunks: 50,
          },
        },
        {
          text: 'Third',
          similarity_score: 0.7,
          metadata: {
            book_title: 'Book 3',
            book_author: 'Author 3',
            tier: TierLevel.C,
            min_level: 1,
            chunk_index: 0,
            file_path: '/path/to/book3.pdf',
            total_chunks: 75,
          },
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

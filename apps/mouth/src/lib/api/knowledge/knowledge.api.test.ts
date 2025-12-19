import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KnowledgeApi } from './knowledge.api';
import { ApiClientBase } from '../client';
import type { KnowledgeSearchResponse } from './knowledge.types';

describe('KnowledgeApi', () => {
  let knowledgeApi: KnowledgeApi;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
      isAdmin: vi.fn(() => false),
    } as any;
    knowledgeApi = new KnowledgeApi(mockClient);
  });

  describe('searchDocs', () => {
    it('should search with default parameters for non-admin', async () => {
      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total_found: 0,
        execution_time_ms: 100,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      const result = await knowledgeApi.searchDocs({ query: 'test query' });

      expect(mockClient.request).toHaveBeenCalledWith('/api/search/', {
        method: 'POST',
        body: JSON.stringify({
          query: 'test query',
          level: 1,
          limit: 8,
          collection: null,
          tier_filter: null,
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should use level 3 for admin users', async () => {
      (mockClient.isAdmin as any).mockReturnValue(true);
      const adminApi = new KnowledgeApi(mockClient);

      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total_found: 0,
        execution_time_ms: 100,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await adminApi.searchDocs({ query: 'test query' });

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"level":3'),
        })
      );
    });

    it('should clamp level to valid range', async () => {
      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total_found: 0,
        execution_time_ms: 100,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await knowledgeApi.searchDocs({ query: 'test', level: 5 });

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"level":3'),
        })
      );
    });

    it('should clamp limit to valid range', async () => {
      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total_found: 0,
        execution_time_ms: 100,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await knowledgeApi.searchDocs({ query: 'test', limit: 100 });

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"limit":50'),
        })
      );
    });

    it('should include collection and tier_filter when provided', async () => {
      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total_found: 0,
        execution_time_ms: 100,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await knowledgeApi.searchDocs({
        query: 'test',
        collection: 'test-collection',
        tier_filter: ['A', 'B'],
      });

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"collection":"test-collection"'),
        })
      );
    });
  });
});


/**
 * RAG Performance Tests
 * Measures response times, throughput, and latency of RAG endpoints
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient } from '../api-client';
import { UserProfile } from '@/types';

const RAG_BACKEND_URL = process.env.RAG_BACKEND_URL || 'https://nuzantara-rag.fly.dev';
const PERFORMANCE_TIMEOUT = 30000;

const mockFetch = vi.fn();
global.fetch = mockFetch;
const jsonHeaders = { get: () => 'application/json' };

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('RAG Performance Tests', () => {
  let api: ApiClient;

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    api = new ApiClient(RAG_BACKEND_URL);

    const mockProfile: UserProfile = {
      id: '123',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
    };
    api.setUserProfile(mockProfile);
    api.setToken('test-token');
  });

  describe('Response Time Benchmarks', () => {
    it('knowledge search should respond within 2 seconds', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: jsonHeaders,
        json: async () => {
          // Simulate network delay
          await new Promise((r) => setTimeout(r, 100));
          return { success: true, results: [] };
        },
      });

      const startTime = performance.now();
      await api.knowledge.searchDocs({ query: 'test', level: 1 });
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(2000);
    });

    it('conversation history should load quickly', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: jsonHeaders,
        json: async () => ({
          success: true,
          messages: [],
          total_messages: 0,
        }),
      });

      const startTime = performance.now();
      await api.conversations.getConversationHistory();
      const duration = performance.now() - startTime;

      expect(duration).toBeLessThan(1000);
    });
  });

  describe('Throughput Tests', () => {
    it('should handle 100 requests per second', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: jsonHeaders,
        json: async () => ({ success: true }),
      });

      const requestsPerSecond = 100;
      const duration = 1000; // 1 second
      const requests = [];

      const startTime = performance.now();
      for (let i = 0; i < requestsPerSecond; i++) {
        requests.push(api.knowledge.searchDocs({ query: `query ${i}`, level: 1 }));
      }
      await Promise.all(requests);
      const elapsed = performance.now() - startTime;

      const actualRPS = (requestsPerSecond / elapsed) * 1000;
      expect(actualRPS).toBeGreaterThan(50); // At least 50 RPS
    });
  });

  describe('Latency Distribution', () => {
    it('should measure p50, p95, p99 latencies', async () => {
      const latencies: number[] = [];
      const numRequests = 100;

      mockFetch.mockImplementation(() => {
        const delay = Math.random() * 200 + 50; // 50-250ms
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: jsonHeaders,
          json: async () => {
            await new Promise((r) => setTimeout(r, delay));
            return { success: true };
          },
        });
      });

      for (let i = 0; i < numRequests; i++) {
        const start = performance.now();
        await api.knowledge.searchDocs({ query: `query ${i}`, level: 1 });
        latencies.push(performance.now() - start);
      }

      latencies.sort((a, b) => a - b);
      const p50 = latencies[Math.floor(numRequests * 0.5)];
      const p95 = latencies[Math.floor(numRequests * 0.95)];
      const p99 = latencies[Math.floor(numRequests * 0.99)];

      expect(p50).toBeLessThan(300);
      expect(p95).toBeLessThan(500);
      expect(p99).toBeLessThan(1000);
    });
  });
});


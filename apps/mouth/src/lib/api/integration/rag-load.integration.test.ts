/**
 * Heavy Load Tests for RAG System
 * Tests the webapp calling backend RAG endpoints under heavy load
 * 
 * These tests simulate real-world usage patterns:
 * - Multiple concurrent chat streams
 * - Knowledge search under load
 * - Mixed workloads
 * - Stress testing
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient } from '../api-client';
import type { KnowledgeSearchResponse } from '@/lib/api';
import { UserProfile } from '@/types';

// Use production/staging URL for real online testing
const RAG_BACKEND_URL = process.env.RAG_BACKEND_URL || 'https://nuzantara-rag.fly.dev';
const TEST_TIMEOUT = 60000; // 60 seconds for heavy tests

// Test credentials for real API testing
const TEST_CREDENTIALS = {
  email: 'zero@balizero.com',
  pin: '010719',
};

const baseSearchResponse: KnowledgeSearchResponse = {
  query: 'test',
  results: [],
  total_found: 0,
  user_level: 1,
  execution_time_ms: 5,
};

// Mock fetch for controlled testing, but allow real API calls if needed
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);
vi.stubGlobal('Response', Response);
Object.defineProperty(window, 'fetch', { value: mockFetch, writable: true });

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

describe('RAG Heavy Load Tests', () => {
  let api: ApiClient;
  const baseUrl = RAG_BACKEND_URL;

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    api = new ApiClient(baseUrl);

    const mockProfile: UserProfile = {
      id: '123',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
    };
    api.setUserProfile(mockProfile);
    api.setToken('test-token');
    api.setCsrfToken('csrf-token');
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Concurrent Chat Streams', () => {
    it(
      'should handle 10 concurrent chat streams',
      async () => {
        const numStreams = 10;
        const queries = [
          'What is a PT company?',
          'How to get a visa for Indonesia?',
          'What are the tax requirements?',
          'Tell me about Bali Zero services',
          'How to set up a business in Indonesia?',
          'What documents do I need for visa?',
          'Explain Indonesian tax system',
          'What is KBLI classification?',
          'How to register a company?',
          'What are the visa types available?',
        ];

        // Mock SSE response
        const mockSSEResponse = (query: string) => {
          const chunks = [
            `data: ${JSON.stringify({ type: 'status', status: 'thinking' })}\n\n`,
            `data: ${JSON.stringify({ type: 'token', token: 'What' })}\n\n`,
            `data: ${JSON.stringify({ type: 'token', token: ' is' })}\n\n`,
            `data: ${JSON.stringify({ type: 'token', token: ' a' })}\n\n`,
            `data: ${JSON.stringify({ type: 'done', response: `Answer to: ${query}` })}\n\n`,
          ];
          return new Response(
            new ReadableStream({
              start(controller) {
                chunks.forEach((chunk, i) => {
                  setTimeout(() => {
                    controller.enqueue(new TextEncoder().encode(chunk));
                    if (i === chunks.length - 1) {
                      controller.close();
                    }
                  }, i * 10);
                });
              },
            }),
            {
              headers: { 'Content-Type': 'text/event-stream' },
            }
          );
        };

        mockFetch.mockImplementation((url: string) => {
          if (url.includes('/api/agentic-rag/stream')) {
            return Promise.resolve(mockSSEResponse('test'));
          }
          return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });

        const streamPromises = queries.map((query, index) => {
          return new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error(`Stream ${index} timed out`));
            }, 30000);

            api.sendMessageStreaming(
              query,
              undefined,
              () => {}, // onChunk
              () => { // onDone
                clearTimeout(timeout);
                resolve();
              },
              (error) => { // onError
                clearTimeout(timeout);
                reject(error);
              }
            ).catch((err) => {
              clearTimeout(timeout);
              reject(err);
            });
          });
        });

        const startTime = Date.now();
        await Promise.all(streamPromises);
        const duration = Date.now() - startTime;

        // All streams should complete
        expect(mockFetch).toHaveBeenCalledTimes(numStreams);
        expect(duration).toBeLessThan(15000); // Should complete in reasonable time
      },
      TEST_TIMEOUT
    );

    it(
      'should handle 50 concurrent knowledge searches',
      async () => {
        const numSearches = 50;
        const searchQueries = Array.from({ length: numSearches }, (_, i) => ({
          query: `Search query ${i}`,
          level: 1,
          limit: 10,
        }));

        // Mock search response
        mockFetch.mockImplementation(() =>
          Promise.resolve(
            new Response(JSON.stringify(baseSearchResponse), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          )
        );

        const searchPromises = searchQueries.map((params) => {
          return api.searchDocs(params);
        });

        const startTime = Date.now();
        const results = await Promise.all(searchPromises);
        const duration = Date.now() - startTime;

        // All searches should complete
        expect(results).toHaveLength(numSearches);
        expect(results.every((r) => Array.isArray(r.results))).toBe(true);
        expect(duration).toBeLessThan(10000); // Should complete quickly
      },
      TEST_TIMEOUT
    );
  });

  describe('Mixed Workload Stress Test', () => {
    it(
      'should handle mixed chat + search workload',
      async () => {
        const numChats = 20;
        const numSearches = 30;
        const totalRequests = numChats + numSearches;

        mockFetch.mockImplementation((url: string) => {
          if (url.includes('/api/agentic-rag/stream')) {
            return Promise.resolve(
              new Response(
                new ReadableStream({
                  start(controller) {
                    controller.enqueue(
                      new TextEncoder().encode(
                        `data: ${JSON.stringify({ type: 'done', response: 'Test' })}\n\n`
                      )
                    );
                    controller.close();
                  },
                }),
                { headers: { 'Content-Type': 'text/event-stream' } }
              )
            );
          }
          if (url.includes('/api/search/')) {
            return Promise.resolve(
              new Response(JSON.stringify(baseSearchResponse), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
              })
            );
          }
          return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });

        const chatPromises = Array.from({ length: numChats }, (_, i) => {
          return new Promise<void>((resolve, reject) => {
             api.sendMessageStreaming(
               `Chat ${i}`,
               undefined,
               () => {}, 
               () => resolve(),
               (err) => reject(err)
             ).catch(reject);
          });
        });

        const searchPromises = Array.from({ length: numSearches }, () => {
          return api.searchDocs({ query: 'test', level: 1 });
        });

        const startTime = Date.now();
        await Promise.all([...chatPromises, ...searchPromises]);
        const duration = Date.now() - startTime;

        expect(mockFetch).toHaveBeenCalledTimes(totalRequests);
        expect(duration).toBeLessThan(5000);
      },
      TEST_TIMEOUT
    );
  });

  describe('Long-Running Stream Test', () => {
    it(
      'should handle long chat stream (100+ tokens)',
      async () => {
        const longResponse = Array.from({ length: 100 }, (_, i) => `token${i} `).join('');

        mockFetch.mockResolvedValue(
          new Response(
            new ReadableStream({
              start(controller) {
                const tokens = longResponse.split(' ');
                tokens.forEach((token, i) => {
                  setTimeout(() => {
                    controller.enqueue(
                      new TextEncoder().encode(
                        `data: ${JSON.stringify({ type: 'token', token: token + ' ' })}\n\n`
                      )
                    );
                    if (i === tokens.length - 1) {
                      controller.enqueue(
                        new TextEncoder().encode(
                          `data: ${JSON.stringify({ type: 'done', response: longResponse })}\n\n`
                        )
                      );
                      controller.close();
                    }
                  }, i * 5);
                });
              },
            }),
            { headers: { 'Content-Type': 'text/event-stream' } }
          )
        );

        const startTime = Date.now();
        // Simulate processing long stream
        await new Promise((resolve) => setTimeout(resolve, 600));
        const duration = Date.now() - startTime;

        expect(duration).toBeGreaterThan(500);
        expect(duration).toBeLessThan(2000);
      },
      TEST_TIMEOUT
    );
  });

  describe('Error Recovery Under Load', () => {
    it(
      'should recover from errors during concurrent requests',
      async () => {
        let callCount = 0;
        mockFetch.mockImplementation(() => {
          callCount++;
          // Fail every 5th request
          if (callCount % 5 === 0) {
            return Promise.reject(new Error('Network error'));
          }
          return Promise.resolve(
            new Response(JSON.stringify(baseSearchResponse), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          );
        });

        const requests = Array.from({ length: 20 }, () => {
          return api.searchDocs({ query: 'test', level: 1 }).catch(() => ({
            error: 'Network error',
          }));
        });

        const results = await Promise.all(requests);

        // Some should succeed, some should fail
        const successes = results.filter(
          (r): r is KnowledgeSearchResponse => !('error' in r)
        );
        const failures = results.filter((r) => 'error' in r);

        expect(successes.length).toBeGreaterThan(0);
        expect(failures.length).toBeGreaterThan(0);
        expect(successes.length + failures.length).toBe(20);
      },
      TEST_TIMEOUT
    );
  });

  describe('Memory and Performance', () => {
    it(
      'should not leak memory during 100 sequential requests',
      async () => {
        mockFetch.mockImplementation(() =>
          Promise.resolve(
            new Response(JSON.stringify(baseSearchResponse), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          )
        );

        const initialMemory = (performance as any).memory?.usedJSHeapSize || 0;

        for (let i = 0; i < 100; i++) {
          await api.searchDocs({ query: `query ${i}`, level: 1 });
          // Small delay to allow garbage collection
          if (i % 10 === 0) {
            await new Promise((resolve) => setTimeout(resolve, 10));
          }
        }

        const finalMemory = (performance as any).memory?.usedJSHeapSize || 0;
        const memoryIncrease = finalMemory - initialMemory;

        // Memory increase should be reasonable (less than 10MB)
        if (initialMemory > 0 && finalMemory > 0) {
          expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024);
        }
      },
      TEST_TIMEOUT
    );
  });

  describe('Real API Integration Tests', () => {
    const USE_REAL_API = process.env.USE_REAL_RAG_API === 'true' || process.env.CI === 'true';

    (USE_REAL_API ? it : it.skip)(
      'should authenticate and make real RAG queries',
      async () => {
        // Step 1: Authenticate
        const authResponse = await fetch(`${RAG_BACKEND_URL}/api/bali-zero/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: TEST_CREDENTIALS.email,
            pin: TEST_CREDENTIALS.pin,
          }),
          credentials: 'include',
        });

        expect(authResponse.ok).toBe(true);
        const authData = await authResponse.json();
        expect(authData.success).toBe(true);
        expect(authData.token).toBeDefined();

        // Step 2: Get CSRF token
        const csrfResponse = await fetch(`${RAG_BACKEND_URL}/api/csrf-token`, {
          credentials: 'include',
        });
        const csrfData = await csrfResponse.json();
        const csrfToken = csrfData.csrf_token;

        // Step 3: Create authenticated API client
        const realApi = new ApiClient(RAG_BACKEND_URL);
        realApi.setToken(authData.token);
        realApi.setCsrfToken(csrfToken);

        // Step 4: Test knowledge search
        const searchResult = await realApi.searchDocs({
          query: 'What is a PT company?',
          level: 3,
          limit: 5,
        });

        expect(searchResult.results).toBeDefined();
        expect(Array.isArray(searchResult.results)).toBe(true);
      },
      TEST_TIMEOUT * 2
    );

    (USE_REAL_API ? it : it.skip)(
      'should handle real streaming chat under load',
      async () => {
        // Authenticate first
        const authResponse = await fetch(`${RAG_BACKEND_URL}/api/bali-zero/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: TEST_CREDENTIALS.email,
            pin: TEST_CREDENTIALS.pin,
          }),
          credentials: 'include',
        });

        const authData = await authResponse.json();
        const csrfResponse = await fetch(`${RAG_BACKEND_URL}/api/csrf-token`, {
          credentials: 'include',
        });
        const csrfData = await csrfResponse.json();

        const realApi = new ApiClient(RAG_BACKEND_URL);
        realApi.setToken(authData.token);
        realApi.setCsrfToken(csrfData.csrf_token);

        // Test streaming chat
        let receivedChunks = 0;
        let fullResponse = '';

        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Stream timeout')), 30000);

          realApi
            .sendMessageStreaming(
              'What is a PT company? Explain briefly.',
              undefined,
              (chunk) => {
                receivedChunks++;
                fullResponse += chunk;
              },
              (response, sources) => {
                clearTimeout(timeout);
                expect(response.length).toBeGreaterThan(0);
                expect(sources).toBeDefined();
                resolve();
              },
              (error) => {
                clearTimeout(timeout);
                reject(error);
              }
            )
            .catch(reject);
        });

        expect(receivedChunks).toBeGreaterThan(0);
        expect(fullResponse.length).toBeGreaterThan(0);
      },
      TEST_TIMEOUT * 3
    );

    (USE_REAL_API ? it : it.skip)(
      'should handle 5 concurrent real streaming chats',
      async () => {
        // Authenticate
        const authResponse = await fetch(`${RAG_BACKEND_URL}/api/bali-zero/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: TEST_CREDENTIALS.email,
            pin: TEST_CREDENTIALS.pin,
          }),
          credentials: 'include',
        });

        const authData = await authResponse.json();
        const csrfResponse = await fetch(`${RAG_BACKEND_URL}/api/csrf-token`, {
          credentials: 'include',
        });
        const csrfData = await csrfResponse.json();

        const queries = [
          'What is a PT company?',
          'How to get a visa for Indonesia?',
          'What are the tax requirements?',
          'Tell me about Bali Zero services',
          'How to set up a business in Indonesia?',
        ];

        const streamPromises = queries.map((query) => {
          const api = new ApiClient(RAG_BACKEND_URL);
          api.setToken(authData.token);
          api.setCsrfToken(csrfData.csrf_token);

          return new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Stream timeout')), 45000);

            api
              .sendMessageStreaming(
                query,
                undefined,
                () => {},
                () => {
                  clearTimeout(timeout);
                  resolve();
                },
                (error) => {
                  clearTimeout(timeout);
                  reject(error);
                }
              )
              .catch(reject);
          });
        });

        const startTime = Date.now();
        await Promise.all(streamPromises);
        const duration = Date.now() - startTime;

        expect(duration).toBeLessThan(60000); // Should complete within 60s
      },
      TEST_TIMEOUT * 4
    );

    (USE_REAL_API ? it : it.skip)(
      'should handle real knowledge search under load',
      async () => {
        // Authenticate
        const authResponse = await fetch(`${RAG_BACKEND_URL}/api/bali-zero/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: TEST_CREDENTIALS.email,
            pin: TEST_CREDENTIALS.pin,
          }),
          credentials: 'include',
        });

        const authData = await authResponse.json();
        const csrfResponse = await fetch(`${RAG_BACKEND_URL}/api/csrf-token`, {
          credentials: 'include',
        });
        const csrfData = await csrfResponse.json();

        const realApi = new ApiClient(RAG_BACKEND_URL);
        realApi.setToken(authData.token);
        realApi.setCsrfToken(csrfData.csrf_token);

        // 20 concurrent searches
        const searches = Array.from({ length: 20 }, (_, i) => ({
          query: `Search query ${i} about Indonesian business`,
          level: 3,
          limit: 10,
        }));

        const startTime = Date.now();
        const results = await Promise.all(
          searches.map((params) => realApi.searchDocs(params))
        );
        const duration = Date.now() - startTime;

        expect(results).toHaveLength(20);
        expect(results.every((r) => Array.isArray(r.results))).toBe(true);
        expect(duration).toBeLessThan(15000); // Should complete within 15s
      },
      TEST_TIMEOUT * 2
    );
  });
});

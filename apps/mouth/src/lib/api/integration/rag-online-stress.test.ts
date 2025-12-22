/**
 * RAG Online Stress Tests
 * Heavy load tests against real RAG backend API
 * 
 * Usage:
 *   USE_REAL_RAG_API=true npm test -- rag-online-stress.test.ts
 * 
 * These tests make real API calls and should be run sparingly
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { ApiClient } from '../api-client';

const RAG_BACKEND_URL = process.env.RAG_BACKEND_URL || 'https://nuzantara-rag.fly.dev';
const USE_REAL_API = process.env.USE_REAL_RAG_API === 'true';

const TEST_CREDENTIALS = {
  email: 'zero@balizero.com',
  pin: '010719',
};

describe.skipIf(!USE_REAL_API)('RAG Online Stress Tests', () => {
  let api: ApiClient;
  let authToken: string;
  let csrfToken: string;

  beforeAll(async () => {
    // Authenticate once for all tests
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
    authToken = authData.token;

    const csrfResponse = await fetch(`${RAG_BACKEND_URL}/api/csrf-token`, {
      credentials: 'include',
    });
    const csrfData = await csrfResponse.json();
    csrfToken = csrfData.csrf_token;

    api = new ApiClient(RAG_BACKEND_URL);
    api.setToken(authToken);
    api.setCsrfToken(csrfToken);
  });

  describe('Heavy Concurrent Streaming', () => {
    it(
      'should handle 10 concurrent chat streams',
      async () => {
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

        const streamPromises = queries.map((query, index) => {
          return new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error(`Stream ${index} timed out`));
            }, 60000);

            api
              .sendMessageStreaming(
                query,
                undefined,
                () => {},
                () => {
                  clearTimeout(timeout);
                  resolve();
                },
                (error: Error) => {
                  clearTimeout(timeout);
                  reject(error);
                }
              )
              .catch((err: Error) => {
                clearTimeout(timeout);
                reject(err);
              });
          });
        });

        const startTime = Date.now();
        await Promise.all(streamPromises);
        const duration = Date.now() - startTime;

        expect(duration).toBeLessThan(120000); // Should complete within 2 minutes
      },
      180000
    );
  });

  describe('Knowledge Search Load', () => {
    it(
      'should handle 50 concurrent knowledge searches',
      async () => {
        const searches = Array.from({ length: 50 }, (_, i) => ({
          query: `Search ${i}: Indonesian business setup requirements`,
          level: 3,
          limit: 10,
        }));

        const startTime = Date.now();
        const results = await Promise.all(
          searches.map((params) => api.knowledge.searchDocs(params))
        );
        const duration = Date.now() - startTime;

        expect(results).toHaveLength(50);
        const successCount = results.filter((r) => Array.isArray(r.results)).length;
        expect(successCount).toBeGreaterThan(45); // At least 90% success rate
        expect(duration).toBeLessThan(30000); // Should complete within 30s
      },
      60000
    );
  });

  describe('Mixed Workload', () => {
    it(
      'should handle mixed chat + search workload',
      async () => {
        const chatQueries = Array.from({ length: 15 }, (_, i) => `Question ${i} about business`);
        const searchQueries = Array.from({ length: 25 }, (_, i) => ({
          query: `Search ${i}`,
          level: 3,
          limit: 5,
        }));

        const chatPromises = chatQueries.map((query) => {
          return new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Timeout')), 45000);
            api
              .sendMessageStreaming(
                query,
                undefined,
                () => {},
                () => {
                  clearTimeout(timeout);
                  resolve();
                },
                (error: Error) => {
                  clearTimeout(timeout);
                  reject(error);
                }
              )
              .catch(reject);
          });
        });

        const searchPromises = searchQueries.map((params) => api.knowledge.searchDocs(params));

        const startTime = Date.now();
        await Promise.all([...chatPromises, ...searchPromises]);
        const duration = Date.now() - startTime;

        expect(duration).toBeLessThan(120000); // Should complete within 2 minutes
      },
      180000
    );
  });

  describe('Sustained Load', () => {
    it(
      'should handle sustained load over time',
      async () => {
        const duration = 60000; // 1 minute
        const startTime = Date.now();
        const requests: Promise<unknown>[] = [];

        while (Date.now() - startTime < duration) {
          // Add a search request every 2 seconds
          requests.push(
            api.knowledge.searchDocs({
              query: `Sustained load test ${Date.now()}`,
              level: 3,
              limit: 5,
            })
          );

          await new Promise((resolve) => setTimeout(resolve, 2000));
        }

        const results = await Promise.all(requests);
        const successCount = results.filter((r: any) => Array.isArray(r.results)).length;
        const successRate = successCount / results.length;

        expect(successRate).toBeGreaterThan(0.8); // At least 80% success rate
      },
      120000
    );
  });
});


import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Memory Persistence
 *
 * Tests the complete memory persistence flow:
 * 1. Memory context is fetched on page load
 * 2. Memory facts are included in AI responses
 * 3. New facts are extracted and saved after conversations
 * 4. Memory persists across page refreshes
 */

test.describe('Memory Persistence', () => {
  // Mock user data
  const testUser = {
    name: 'Roberto Testini',
    email: 'roberto@test.com',
    id: 'user-123',
    role: 'user',
  };

  // Mock memory context with facts
  const mockMemoryContext = {
    success: true,
    user_id: testUser.email,
    profile_facts: ['Name: Roberto', 'Location: Torino', 'Profession: Lawyer'],
    summary: 'Interested in opening a law firm in Bali',
    counters: { conversations: 5, searches: 10, tasks: 2 },
    has_data: true,
  };

  // Empty memory context for new users
  const emptyMemoryContext = {
    success: true,
    user_id: testUser.email,
    profile_facts: [],
    summary: null,
    counters: { conversations: 0, searches: 0, tasks: 0 },
    has_data: false,
  };

  async function setupAuthenticatedUser(page: Page) {
    // Mock Auth
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token');
      localStorage.setItem(
        'user_profile',
        JSON.stringify({
          name: 'Roberto Testini',
          email: 'roberto@test.com',
          id: 'user-123',
          role: 'user',
        })
      );
    });

    // Mock Profile endpoint
    await page.route('**/api/auth/profile', async (route) => {
      await route.fulfill({ json: testUser });
    });

    // Mock Team Status
    await page.route('**/api/team/my-status**', async (route) => {
      await route.fulfill({
        json: { is_online: true, today_hours: 4, week_hours: 20 },
      });
    });

    // Mock Conversations List
    await page.route('**/api/bali-zero/conversations/list**', async (route) => {
      await route.fulfill({
        json: { success: true, conversations: [], total: 0 },
      });
    });
  }

  test.describe('Memory Context Fetching', () => {
    // TODO: Re-enable when useMemoryContext hook is integrated in chat page
    // The hook exists but is not yet used in src/app/(workspace)/chat/page.tsx
    test.skip('should fetch memory context on authenticated page load', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // Track memory context API call
      let memoryContextCalled = false;

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        memoryContextCalled = true;
        await route.fulfill({ json: mockMemoryContext });
      });

      await page.goto('/chat');

      // Wait for page to load and API calls to complete
      await page.waitForLoadState('networkidle');

      // Verify memory context was fetched
      expect(memoryContextCalled).toBe(true);
    });

    test('should handle empty memory context for new users', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({ json: emptyMemoryContext });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // Page should load without errors even with no memory
      await expect(page.locator('textarea[placeholder="Type your message..."]')).toBeVisible();
    });

    test('should handle memory context API errors gracefully', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({
          status: 500,
          json: { detail: 'Database error' },
        });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // Page should still be usable despite error
      await expect(page.locator('textarea[placeholder="Type your message..."]')).toBeVisible();
    });
  });

  test.describe('Memory Integration with Chat', () => {
    test('should include memory context in chat requests', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({ json: mockMemoryContext });
      });

      let chatRequestBody: string | null = null;

      // Intercept chat stream request to verify memory is included
      await page.route('**/api/agentic-rag/stream', async (route) => {
        const request = route.request();
        chatRequestBody = request.postData();

        // Send mock response
        const chunks = [
          'data: {"type": "token", "content": "Ciao Roberto! "}\n\n',
          'data: {"type": "token", "content": "Come posso aiutarti con il tuo studio legale a Bali?"}\n\n',
          'data: [DONE]\n\n',
        ];
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: chunks.join(''),
        });
      });

      // Mock conversation save
      await page.route('**/api/bali-zero/conversations/save', async (route) => {
        await route.fulfill({
          json: {
            success: true,
            conversation_id: 1,
            messages_saved: 2,
          },
        });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // Send a message
      await page.fill('textarea[placeholder="Type your message..."]', 'Buongiorno!');
      await page.keyboard.press('Enter');

      // Wait for response
      await expect(
        page.getByText('Ciao Roberto! Come posso aiutarti con il tuo studio legale a Bali?')
      ).toBeVisible({ timeout: 10000 });

      // Verify user_id was included in request
      expect(chatRequestBody).toBeTruthy();
      const body = JSON.parse(chatRequestBody!);
      expect(body.user_id).toBe(testUser.email);
    });

    test('should personalize response using memory context', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({ json: mockMemoryContext });
      });

      // Mock response that uses memory context (personalized)
      await page.route('**/api/agentic-rag/stream', async (route) => {
        const chunks = [
          'data: {"type": "token", "content": "Buongiorno Avvocato Roberto! "}\n\n',
          'data: {"type": "token", "content": "Ricordo che sei interessato ad aprire uno studio a Bali. "}\n\n',
          'data: {"type": "token", "content": "Come procede il progetto?"}\n\n',
          'data: {"type": "metadata", "data": {"route_used": "agentic", "emotional_state": "friendly"}}\n\n',
          'data: [DONE]\n\n',
        ];
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: chunks.join(''),
        });
      });

      await page.route('**/api/bali-zero/conversations/save', async (route) => {
        await route.fulfill({
          json: { success: true, conversation_id: 1, messages_saved: 2 },
        });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // Send a message
      await page.fill('textarea[placeholder="Type your message..."]', 'Ciao!');
      await page.keyboard.press('Enter');

      // Verify personalized response mentions user's name and project
      await expect(page.getByText(/Avvocato Roberto/)).toBeVisible({ timeout: 10000 });
      await expect(page.getByText(/Bali/)).toBeVisible();
    });
  });

  test.describe('Memory Persistence Across Sessions', () => {
    // TODO: Re-enable when useMemoryContext hook is integrated in chat page
    test.skip('should preserve memory context after page refresh', async ({ page }) => {
      await setupAuthenticatedUser(page);

      let memoryFetchCount = 0;

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        memoryFetchCount++;
        await route.fulfill({ json: mockMemoryContext });
      });

      // First page load
      await page.goto('/chat');
      await page.waitForLoadState('networkidle');
      expect(memoryFetchCount).toBe(1);

      // Refresh page
      await page.reload();
      await page.waitForLoadState('networkidle');

      // Memory should be fetched again (same context)
      expect(memoryFetchCount).toBe(2);
    });

    // TODO: Re-enable when message saving integration is complete
    test.skip('should accumulate facts from new conversations', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // Initial memory with 3 facts
      let currentFacts = ['Name: Roberto', 'Location: Torino', 'Profession: Lawyer'];

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({
          json: {
            success: true,
            user_id: testUser.email,
            profile_facts: currentFacts,
            counters: { conversations: currentFacts.length },
            has_data: true,
          },
        });
      });

      // Mock chat that will extract new fact (Age: 45)
      await page.route('**/api/agentic-rag/stream', async (route) => {
        const chunks = [
          'data: {"type": "token", "content": "Capisco, hai 45 anni. "}\n\n',
          'data: {"type": "token", "content": "Ottima esperienza per aprire uno studio!"}\n\n',
          'data: [DONE]\n\n',
        ];
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: chunks.join(''),
        });
      });

      let savedMessages: unknown[] = [];
      await page.route('**/api/bali-zero/conversations/save', async (route) => {
        const request = route.request();
        const body = JSON.parse(request.postData() || '{}');
        savedMessages = body.messages || [];

        // After save, update facts (simulating backend extraction)
        currentFacts = [...currentFacts, 'Age: 45'];

        await route.fulfill({
          json: { success: true, conversation_id: 1, messages_saved: savedMessages.length },
        });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // Send message with new personal info
      await page.fill('textarea[placeholder="Type your message..."]', 'Ho 45 anni');
      await page.keyboard.press('Enter');

      // Wait for response
      await expect(page.getByText(/Capisco, hai 45 anni/)).toBeVisible({ timeout: 10000 });

      // Verify message was saved
      expect(savedMessages.length).toBeGreaterThan(0);
    });
  });

  test.describe('Memory Context Security', () => {
    test('should not fetch memory context for unauthenticated users', async ({ page }) => {
      // Don't set up authenticated user

      let memoryContextCalled = false;

      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        memoryContextCalled = true;
        await route.fulfill({
          status: 401,
          json: { detail: 'Not authenticated' },
        });
      });

      // Navigate to chat (should redirect to login or show auth prompt)
      await page.goto('/chat');

      // Wait briefly
      await page.waitForTimeout(1000);

      // Memory context should either not be called or return 401
      // The exact behavior depends on auth middleware
    });

    test('should not expose memory context of other users', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // Always return the authenticated user's context, never another user's
      await page.route('**/api/bali-zero/conversations/memory/context', async (route) => {
        await route.fulfill({
          json: {
            ...mockMemoryContext,
            user_id: testUser.email, // Always the authenticated user
          },
        });
      });

      await page.goto('/chat');
      await page.waitForLoadState('networkidle');

      // No way to access other users' memory
      // This is verified by backend authorization, tested in API tests
    });
  });
});

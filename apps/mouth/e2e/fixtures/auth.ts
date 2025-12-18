/* eslint-disable react-hooks/rules-of-hooks */
import { test as base, Page } from '@playwright/test';

/**
 * Auth fixtures per test E2E
 * Fornisce helper per login/logout
 */

type AuthFixtures = {
  authenticatedPage: Page;
  loginUser: (email: string, pin: string) => Promise<void>;
  logoutUser: () => Promise<void>;
};

export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }: { page: Page }, use: (r: Page) => Promise<void>) => {
    // Login di default con utente di test
    await page.goto('/login');
    await page.fill('[name="email"]', 'test@balizero.com');
    await page.fill('[name="pin"]', '123456');
    await page.click('button[type="submit"]');

    // Attendi redirect alla chat
    await page.waitForURL('/chat', { timeout: 10000 });

    await use(page);
  },

  loginUser: async (
    { page }: { page: Page },
    use: (fn: (email: string, pin: string) => Promise<void>) => Promise<void>
  ) => {
    const login = async (email: string, pin: string) => {
      await page.goto('/login');
      await page.fill('[name="email"]', email);
      await page.fill('[name="pin"]', pin);
      await page.click('button[type="submit"]');
      await page.waitForURL('/chat', { timeout: 10000 });
    };

    await use(login);
  },

  logoutUser: async ({ page }: { page: Page }, use: (fn: () => Promise<void>) => Promise<void>) => {
    const logout = async () => {
      // Implementa logout se necessario
      await page.goto('/login');
    };

    await use(logout);
  },
});

export { expect } from '@playwright/test';

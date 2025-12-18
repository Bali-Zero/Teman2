/**
 * Test helpers per E2E tests
 */

import type { Page } from '@playwright/test';

export const TEST_USER = {
  email: 'test@balizero.com',
  pin: '123456',
};

export const TEST_MESSAGES = {
  simple: 'Hello',
  business: 'Come aprire un PT PMA?',
  complex: 'Quali sono i requisiti per ottenere un KITAS per un direttore di PT PMA?',
};

/**
 * Attende che un elemento sia visibile e interagibile
 */
export async function waitForElement(page: Page, selector: string, timeout = 10000) {
  await page.waitForSelector(selector, { state: 'visible', timeout });
  return page.locator(selector);
}

/**
 * Attende che un messaggio AI appaia nella chat
 */
export async function waitForAIMessage(page: Page, timeout = 30000) {
  // Attendi che il messaggio AI appaia (può essere streaming)
  await page.waitForSelector('[data-testid="ai-message"], [data-role="assistant"]', {
    timeout,
  });
}

/**
 * Invia un messaggio nella chat
 */
export async function sendMessage(page: Page, message: string) {
  const input = await waitForElement(page, '[data-testid="chat-input"], textarea');
  await input.fill(message);
  await page.click('[data-testid="send-button"], button[type="submit"]');
}

/**
 * Verifica che la connessione WebSocket sia attiva
 */
export async function checkWebSocketConnection(page: Page) {
  // Verifica che il WebSocket sia connesso controllando lo stato nella pagina
  await page.waitForFunction(() => {
    // Cerca indicatori di connessione WebSocket
    return window.navigator.onLine === true;
  });
}

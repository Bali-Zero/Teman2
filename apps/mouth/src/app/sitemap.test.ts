import { describe, it, expect } from 'vitest';
import sitemap from './sitemap';

describe('sitemap', () => {
  it('should return sitemap with correct structure', () => {
    const result = sitemap();

    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it('should include home page', () => {
    const result = sitemap();

    const homePage = result.find((item) => item.url === 'https://nuzantara-rag.fly.dev');
    expect(homePage).toBeDefined();
    expect(homePage?.priority).toBe(1);
    expect(homePage?.changeFrequency).toBe('daily');
  });

  it('should include login page', () => {
    const result = sitemap();

    const loginPage = result.find((item) => item.url === 'https://nuzantara-rag.fly.dev/login');
    expect(loginPage).toBeDefined();
    expect(loginPage?.priority).toBe(0.8);
    expect(loginPage?.changeFrequency).toBe('monthly');
  });

  it('should include chat page', () => {
    const result = sitemap();

    const chatPage = result.find((item) => item.url === 'https://nuzantara-rag.fly.dev/chat');
    expect(chatPage).toBeDefined();
    expect(chatPage?.priority).toBe(0.9);
    expect(chatPage?.changeFrequency).toBe('always');
  });

  it('should have lastModified dates', () => {
    const result = sitemap();

    result.forEach((item) => {
      expect(item.lastModified).toBeInstanceOf(Date);
    });
  });

  it('should have valid URLs', () => {
    const result = sitemap();

    result.forEach((item) => {
      expect(item.url).toMatch(/^https:\/\//);
    });
  });

  it('should have valid priorities', () => {
    const result = sitemap();

    result.forEach((item) => {
      expect(item.priority).toBeGreaterThanOrEqual(0);
      expect(item.priority).toBeLessThanOrEqual(1);
    });
  });
});

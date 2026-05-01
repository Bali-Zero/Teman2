import { describe, it, expect, vi, beforeEach } from 'vitest';
import { observatoryClient } from '../app/observatory/lib/observatory-client';

describe('observatoryClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('health() hits the /health endpoint with X-Observatory-Key header', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ alive: true, uptime_s: 0, events_total: 0, events_24h: 0 }),
    } as Response);

    const result = await observatoryClient.health();

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/observatory/health'),
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-Observatory-Key': expect.any(String) }),
        cache: 'no-store',
      })
    );
    expect(result.alive).toBe(true);
  });

  it('pulses() includes cell_id and since query params when provided', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);

    await observatoryClient.pulses('organism', '2026-05-01T00:00:00Z');

    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toContain('cell_id=organism');
    expect(url).toContain('since=');
  });

  it('throws Error on non-2xx response', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    } as Response);

    await expect(observatoryClient.health()).rejects.toThrow('401');
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { GET, POST } from './route';

// Marker present ONLY in the gated codex content (never in the door page).
const CONTENT_MARKER = 'Explicit dies prima';
// Marker present ONLY in the door page.
const DOOR_MARKER = 'Da mihi signum';

const URL_ = 'https://balizero.com/codex';

function postRequest(pin: string, headers: Record<string, string> = {}): Request {
  return new Request(URL_, {
    method: 'POST',
    body: new URLSearchParams({ pin }),
    headers,
  });
}

describe('/codex PIN gate', () => {
  it('GET without cookie serves the door, never the codex content', async () => {
    const res = await GET(new Request(URL_));
    const body = await res.text();
    expect(res.status).toBe(200);
    expect(body).toContain(DOOR_MARKER);
    expect(body).not.toContain(CONTENT_MARKER);
    expect(res.headers.get('x-robots-tag')).toContain('noindex');
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('POST with wrong pin returns the door with error and sets no cookie', async () => {
    const res = await POST(postRequest('123'));
    const body = await res.text();
    expect(res.status).toBe(401);
    expect(res.headers.get('set-cookie')).toBeNull();
    expect(body).toContain('Signum falsum est');
    expect(body).not.toContain(CONTENT_MARKER);
  });

  it('POST with the right pin sets the signed cookie and redirects', async () => {
    const res = await POST(postRequest('666'));
    expect(res.status).toBe(303);
    expect(res.headers.get('location')).toBe('/codex');
    const cookie = res.headers.get('set-cookie') ?? '';
    expect(cookie).toMatch(/codex_sig=[0-9a-f]{64}/);
    expect(cookie).toContain('HttpOnly');
  });

  it('GET with the signed cookie serves the codex content', async () => {
    const post = await POST(postRequest('666'));
    const sig = (post.headers.get('set-cookie') ?? '').match(/codex_sig=([0-9a-f]{64})/)?.[1];
    expect(sig).toBeTruthy();
    const res = await GET(new Request(URL_, { headers: { cookie: `codex_sig=${sig}` } }));
    const body = await res.text();
    expect(res.status).toBe(200);
    expect(body).toContain(CONTENT_MARKER);
    expect(body).not.toContain(DOOR_MARKER);
  });

  it('GET with a forged cookie value still serves the door', async () => {
    const res = await GET(
      new Request(URL_, { headers: { cookie: `codex_sig=${'0'.repeat(64)}` } }),
    );
    const body = await res.text();
    expect(body).toContain(DOOR_MARKER);
    expect(body).not.toContain(CONTENT_MARKER);
  });
});

describe('/codex door alert (guilt + innocence)', () => {
  const fetchMock = vi.fn(async () => new Response('{"messages":[{"id":"x"}]}', { status: 200 }));

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    vi.stubEnv('CODEX_WA_TOKEN', 'test-token');
    vi.stubEnv('CODEX_WA_PHONE_ID', '12345');
    fetchMock.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('guilt: correct pin from Italy sends the ENTERED WhatsApp', async () => {
    const res = await POST(postRequest('666', { 'x-vercel-ip-country': 'IT', 'x-vercel-ip-city': 'Roma' }));
    expect(res.status).toBe(303);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('graph.facebook.com');
    const body = JSON.parse(String(init.body));
    expect(body.text.body).toContain('ENTRATO');
    expect(body.text.body).toContain('IT (Roma)');
  });

  it('guilt: wrong pin from Italy sends the door WhatsApp', async () => {
    const res = await POST(postRequest('123', { 'x-vercel-ip-country': 'IT' }));
    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body));
    expect(body.text.body).toContain('sbagliato');
  });

  it('innocence: correct pin from a skip-listed country stays silent', async () => {
    const res = await POST(postRequest('666', { 'x-vercel-ip-country': 'US' }));
    expect(res.status).toBe(303);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('innocence: alert not configured — door still works, nothing sent', async () => {
    vi.stubEnv('CODEX_WA_TOKEN', '');
    const res = await POST(postRequest('666', { 'x-vercel-ip-country': 'IT' }));
    expect(res.status).toBe(303);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('innocence: WhatsApp API failure never blocks the reader', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'));
    const res = await POST(postRequest('666', { 'x-vercel-ip-country': 'IT' }));
    expect(res.status).toBe(303);
  });
});


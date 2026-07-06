import { describe, expect, it } from 'vitest';

import { GET, POST } from './route';

// Marker present ONLY in the gated codex content (never in the door page).
const CONTENT_MARKER = 'Explicit dies prima';
// Marker present ONLY in the door page.
const DOOR_MARKER = 'Da mihi signum';

const URL_ = 'https://balizero.com/codex';

function postRequest(pin: string): Request {
  return new Request(URL_, {
    method: 'POST',
    body: new URLSearchParams({ pin }),
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

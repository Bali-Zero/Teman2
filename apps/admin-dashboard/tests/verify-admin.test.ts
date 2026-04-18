import { SignJWT } from 'jose';
import { beforeAll, describe, expect, it } from 'vitest';

import { verifyAdminToken } from '@/lib/auth/verify-admin';

const SECRET_STRING = 'test-secret-please-ignore-32bytes-minimum-length!!';
const secret = new TextEncoder().encode(SECRET_STRING);

async function signToken(
  payload: Record<string, unknown>,
  opts?: { alg?: string; expSecondsFromNow?: number | null }
): Promise<string> {
  const alg = opts?.alg ?? 'HS256';
  let builder = new SignJWT(payload).setProtectedHeader({ alg });
  if (opts?.expSecondsFromNow !== null) {
    const exp = Math.floor(Date.now() / 1000) + (opts?.expSecondsFromNow ?? 3600);
    builder = builder.setExpirationTime(exp);
  }
  return await builder.sign(secret);
}

describe('verifyAdminToken', () => {
  beforeAll(() => {
    process.env.JWT_SECRET_KEY = SECRET_STRING;
    delete process.env.ADMIN_EMAILS;
  });

  it('returns missing_cookie when token is empty', async () => {
    const outcome = await verifyAdminToken(undefined);
    expect(outcome).toEqual({ ok: false, reason: 'missing_cookie' });
  });

  it('returns missing_cookie for empty string', async () => {
    const outcome = await verifyAdminToken('');
    expect(outcome).toEqual({ ok: false, reason: 'missing_cookie' });
  });

  it('returns bad_token for a token signed with a different secret', async () => {
    const otherSecret = new TextEncoder().encode('wrong-secret-wrong-secret-wrong-secret!');
    const token = await new SignJWT({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    })
      .setProtectedHeader({ alg: 'HS256' })
      .setExpirationTime(Math.floor(Date.now() / 1000) + 3600)
      .sign(otherSecret);
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'bad_token' });
  });

  it('returns bad_token for an expired token', async () => {
    const token = await new SignJWT({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    })
      .setProtectedHeader({ alg: 'HS256' })
      .setExpirationTime(Math.floor(Date.now() / 1000) - 60)
      .sign(secret);
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'bad_token' });
  });

  it('returns bad_token when type is refresh', async () => {
    const token = await signToken({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'refresh',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'bad_token' });
  });

  it('returns bad_token when email is missing', async () => {
    const token = await signToken({ role: 'admin', type: 'access' });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'bad_token' });
  });

  it('returns forbidden_role for role=client', async () => {
    const token = await signToken({
      email: 'client@example.com',
      role: 'client',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'forbidden_role' });
  });

  it('returns forbidden_role for role=user (non-admin team member)', async () => {
    const token = await signToken({
      email: 'staff@balizero.com',
      role: 'user',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({ ok: false, reason: 'forbidden_role' });
  });

  it('accepts role=admin', async () => {
    const token = await signToken({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toEqual({
      ok: true,
      email: 'zero@balizero.com',
      role: 'admin',
    });
  });

  it('accepts role=super_admin and role=owner', async () => {
    const tokenSuper = await signToken({
      email: 'asya@balizero.com',
      role: 'super_admin',
      type: 'access',
    });
    const tokenOwner = await signToken({
      email: 'owner@balizero.com',
      role: 'owner',
      type: 'access',
    });
    expect(await verifyAdminToken(tokenSuper)).toMatchObject({
      ok: true,
      role: 'super_admin',
    });
    expect(await verifyAdminToken(tokenOwner)).toMatchObject({
      ok: true,
      role: 'owner',
    });
  });

  it('accepts token without type claim (backward compat with pre-S03 tokens)', async () => {
    const token = await signToken({
      email: 'zero@balizero.com',
      role: 'admin',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toMatchObject({ ok: true, email: 'zero@balizero.com' });
  });

  it('honours ADMIN_EMAILS allowlist (defence in depth)', async () => {
    const token = await signToken({
      email: 'rogue@balizero.com',
      role: 'admin',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token, {
      allowedEmails: new Set(['zero@balizero.com']),
    });
    expect(outcome).toEqual({ ok: false, reason: 'forbidden_role' });
  });

  it('allows email in ADMIN_EMAILS allowlist', async () => {
    const token = await signToken({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token, {
      allowedEmails: new Set(['zero@balizero.com']),
    });
    expect(outcome).toMatchObject({ ok: true });
  });

  it('lowercases the role claim before comparison', async () => {
    const token = await signToken({
      email: 'zero@balizero.com',
      role: 'ADMIN',
      type: 'access',
    });
    const outcome = await verifyAdminToken(token);
    expect(outcome).toMatchObject({ ok: true, role: 'admin' });
  });
});

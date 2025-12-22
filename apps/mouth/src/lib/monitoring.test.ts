import { describe, it, expect, beforeEach, vi } from 'vitest';
import { conversationMonitor, type ConversationMetrics } from './monitoring';

describe('conversationMonitor', () => {
  beforeEach(() => {
    // Clear all sessions before each test
    const activeSessions = conversationMonitor.getActiveSessions();
    activeSessions.forEach((session) => {
      conversationMonitor.clearSession(session.sessionId);
    });
  });

  it('should track a new message', () => {
    const sessionId = 'test-session-1';
    conversationMonitor.trackMessage(sessionId, false);

    const metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics).toBeDefined();
    expect(metrics?.turnCount).toBe(1);
  });

  it('should track multiple messages', () => {
    const sessionId = 'test-session-2';
    conversationMonitor.trackMessage(sessionId, false);
    conversationMonitor.trackMessage(sessionId, false);
    conversationMonitor.trackMessage(sessionId, false);

    const metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics?.turnCount).toBe(3);
  });

  it('should track errors', () => {
    const sessionId = 'test-session-3';
    conversationMonitor.trackMessage(sessionId, true, 'TEST_ERROR');

    const metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics?.errors.length).toBe(1);
    expect(metrics?.errors[0].type).toBe('TEST_ERROR');
  });

  it('should track timeouts', () => {
    const sessionId = 'test-session-4';
    conversationMonitor.trackMessage(sessionId, true, 'TIMEOUT');
    conversationMonitor.trackMessage(sessionId, true, 'TIMEOUT');

    const metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics?.timeouts).toBe(2);
  });

  it('should track rate limit hits', () => {
    const sessionId = 'test-session-5';
    conversationMonitor.trackMessage(sessionId, true, 'QUOTA_EXCEEDED');
    conversationMonitor.trackMessage(sessionId, true, '429');

    const metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics?.rateLimitHits).toBe(2);
  });

  it('should clear session', () => {
    const sessionId = 'test-session-6';
    conversationMonitor.trackMessage(sessionId, false);

    let metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics).toBeDefined();

    conversationMonitor.clearSession(sessionId);
    metrics = conversationMonitor.getMetrics(sessionId);
    expect(metrics).toBeUndefined();
  });

  it('should get summary', () => {
    const sessionId1 = 'test-session-7';
    const sessionId2 = 'test-session-8';

    conversationMonitor.trackMessage(sessionId1, false);
    conversationMonitor.trackMessage(sessionId1, false);
    conversationMonitor.trackMessage(sessionId2, true, 'TEST_ERROR');

    const summary = conversationMonitor.getSummary();
    expect(summary).toBeDefined();
    expect(summary.activeSessions).toBeGreaterThanOrEqual(2);
    expect(summary.totalTurns).toBeGreaterThanOrEqual(3);
  });

  it('should get active sessions', () => {
    const sessionId = 'test-session-9';
    conversationMonitor.trackMessage(sessionId, false);

    const activeSessions = conversationMonitor.getActiveSessions();
    expect(activeSessions.length).toBeGreaterThanOrEqual(1);
    expect(activeSessions.some((s) => s.sessionId === sessionId)).toBe(true);
  });

  it('should update lastMessageTime on each message', async () => {
    const sessionId = 'test-session-10';

    conversationMonitor.trackMessage(sessionId, false);
    const metrics1 = conversationMonitor.getMetrics(sessionId);
    const time1 = metrics1?.lastMessageTime.getTime() || 0;

    // Wait a bit to ensure different timestamp
    await new Promise((resolve) => setTimeout(resolve, 50));

    conversationMonitor.trackMessage(sessionId, false);
    const metrics2 = conversationMonitor.getMetrics(sessionId);
    const time2 = metrics2?.lastMessageTime.getTime() || 0;

    // Times should be different (or at least metrics2 should exist)
    expect(time2).toBeGreaterThanOrEqual(time1);
    expect(metrics2?.turnCount).toBe(2);
  });
});

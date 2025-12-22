/**
 * Tests for monitoring-dashboard.ts
 * Covers all branches and mappers
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { monitoringDashboard, monitoringHelpers } from './monitoring-dashboard';
import { conversationMonitor } from './monitoring';

// Mock conversationMonitor
vi.mock('./monitoring', () => ({
  conversationMonitor: {
    getSummary: vi.fn(),
    getActiveSessions: vi.fn(),
    getMetrics: vi.fn(),
    clearSession: vi.fn(),
  },
}));

describe('MonitoringDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage
    localStorage.clear();
  });

  describe('showSummary', () => {
    it('should display summary with active sessions', () => {
      const mockSummary = {
        activeSessions: 2,
        totalTurns: 10,
        totalErrors: 1,
        totalTimeouts: 0,
        totalRateLimitHits: 0,
      };

      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(Date.now() - 60000),
          lastMessageTime: new Date(),
          errors: [],
          timeouts: 0,
          rateLimitHits: 0,
        },
      ];

      vi.mocked(conversationMonitor.getSummary).mockReturnValue(mockSummary);
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const consoleSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      monitoringDashboard.showSummary();

      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleLogSpy).toHaveBeenCalled();
    });

    it('should display summary without active sessions', () => {
      const mockSummary = {
        activeSessions: 0,
        totalTurns: 0,
        totalErrors: 0,
        totalTimeouts: 0,
        totalRateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getSummary).mockReturnValue(mockSummary);
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([]);

      const consoleSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
      monitoringDashboard.showSummary();

      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should display alert history when present', () => {
      const mockSummary = {
        activeSessions: 0,
        totalTurns: 0,
        totalErrors: 0,
        totalTimeouts: 0,
        totalRateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getSummary).mockReturnValue(mockSummary);
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([]);

      // Add alert history
      monitoringDashboard.recordAlert('TEST_ALERT', { test: 'data' });

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showSummary();

      expect(consoleWarnSpy).toHaveBeenCalled();
    });
  });

  describe('showAlerts', () => {
    it('should show no alerts when none exist', () => {
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([]);

      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      monitoringDashboard.showAlerts();

      expect(consoleLogSpy).toHaveBeenCalledWith('✅ No active alerts');
    });

    it('should detect LONG_CONVERSATION alert', () => {
      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 15,
          startTime: new Date(),
          lastMessageTime: new Date(),
          errors: [],
          timeouts: 0,
          rateLimitHits: 0,
        },
      ];

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showAlerts();

      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('should detect MULTIPLE_ERRORS alert', () => {
      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(),
          lastMessageTime: new Date(),
          errors: [
            { type: 'error1', message: 'msg1', timestamp: new Date() },
            { type: 'error2', message: 'msg2', timestamp: new Date() },
            { type: 'error3', message: 'msg3', timestamp: new Date() },
          ],
          timeouts: 0,
          rateLimitHits: 0,
        },
      ];

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showAlerts();

      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('should detect MULTIPLE_TIMEOUTS alert', () => {
      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(),
          lastMessageTime: new Date(),
          errors: [],
          timeouts: 2,
          rateLimitHits: 0,
        },
      ];

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showAlerts();

      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('should detect RATE_LIMIT_ISSUES alert', () => {
      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(),
          lastMessageTime: new Date(),
          errors: [],
          timeouts: 0,
          rateLimitHits: 2,
        },
      ];

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showAlerts();

      expect(consoleWarnSpy).toHaveBeenCalled();
    });
  });

  describe('showSessionDetails', () => {
    it('should display session details when session exists', () => {
      const mockMetrics = {
        sessionId: 'session-123',
        turnCount: 5,
        startTime: new Date(Date.now() - 60000),
        lastMessageTime: new Date(),
        errors: [],
        timeouts: 0,
        rateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getMetrics).mockReturnValue(mockMetrics);

      const consoleSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
      monitoringDashboard.showSessionDetails('session-123');

      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should warn when session does not exist', () => {
      vi.mocked(conversationMonitor.getMetrics).mockReturnValue(undefined);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      monitoringDashboard.showSessionDetails('nonexistent');

      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('should display error history when present', () => {
      const mockMetrics = {
        sessionId: 'session-123',
        turnCount: 5,
        startTime: new Date(),
        lastMessageTime: new Date(),
        errors: [{ type: 'error1', message: 'msg1', timestamp: new Date() }],
        timeouts: 0,
        rateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getMetrics).mockReturnValue(mockMetrics);

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      monitoringDashboard.showSessionDetails('session-123');

      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('exportMetrics', () => {
    it('should export metrics as JSON string', () => {
      const mockSummary = {
        activeSessions: 1,
        totalTurns: 5,
        totalErrors: 0,
        totalTimeouts: 0,
        totalRateLimitHits: 0,
      };

      const mockSessions = [
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(),
          lastMessageTime: new Date(),
          errors: [],
          timeouts: 0,
          rateLimitHits: 0,
        },
      ];

      vi.mocked(conversationMonitor.getSummary).mockReturnValue(mockSummary);
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue(mockSessions);

      const result = monitoringDashboard.exportMetrics();
      const parsed = JSON.parse(result);

      expect(parsed).toHaveProperty('timestamp');
      expect(parsed).toHaveProperty('summary');
      expect(parsed).toHaveProperty('sessions');
      expect(parsed).toHaveProperty('alerts');
    });
  });

  describe('clearOldSessions', () => {
    it('should clear sessions older than default (60 minutes)', () => {
      const oldSession = {
        sessionId: 'old-session',
        turnCount: 5,
        startTime: new Date(Date.now() - 70 * 60 * 1000),
        lastMessageTime: new Date(Date.now() - 70 * 60 * 1000),
        errors: [],
        timeouts: 0,
        rateLimitHits: 0,
      };

      const newSession = {
        sessionId: 'new-session',
        turnCount: 5,
        startTime: new Date(),
        lastMessageTime: new Date(),
        errors: [],
        timeouts: 0,
        rateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([oldSession, newSession]);

      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      monitoringDashboard.clearOldSessions();

      expect(consoleLogSpy).toHaveBeenCalled();
      expect(conversationMonitor.clearSession).toHaveBeenCalledWith('old-session');
    });

    it('should clear sessions older than custom maxAgeMinutes', () => {
      const oldSession = {
        sessionId: 'old-session',
        turnCount: 5,
        startTime: new Date(Date.now() - 35 * 60 * 1000),
        lastMessageTime: new Date(Date.now() - 35 * 60 * 1000),
        errors: [],
        timeouts: 0,
        rateLimitHits: 0,
      };

      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([oldSession]);

      monitoringDashboard.clearOldSessions(30);

      expect(conversationMonitor.clearSession).toHaveBeenCalledWith('old-session');
    });
  });

  describe('recordAlert', () => {
    it('should record alert and keep only MAX_ALERT_HISTORY', () => {
      // Add more than MAX_ALERT_HISTORY alerts
      for (let i = 0; i < 150; i++) {
        monitoringDashboard.recordAlert(`ALERT_${i}`, { index: i });
      }

      const exported = monitoringDashboard.exportMetrics();
      const parsed = JSON.parse(exported);

      expect(parsed.alerts.length).toBeLessThanOrEqual(100);
    });
  });

  describe('monitoringHelpers', () => {
    it('should provide summary helper', () => {
      const consoleSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
      monitoringHelpers.summary();
      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should provide alerts helper', () => {
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([]);
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      monitoringHelpers.alerts();
      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should provide export helper', () => {
      vi.mocked(conversationMonitor.getSummary).mockReturnValue({
        activeSessions: 0,
        totalTurns: 0,
        totalErrors: 0,
        totalTimeouts: 0,
        totalRateLimitHits: 0,
      });
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([]);

      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
        writable: true,
      });

      monitoringHelpers.export();
      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should provide clear helper', () => {
      // Mock active sessions so clearSession gets called
      vi.mocked(conversationMonitor.getActiveSessions).mockReturnValue([
        {
          sessionId: 'session-123',
          turnCount: 5,
          startTime: new Date(Date.now() - 120 * 60 * 1000), // 120 minutes ago
          lastMessageTime: new Date(Date.now() - 120 * 60 * 1000),
          errors: [],
          timeouts: 0,
          rateLimitHits: 0,
        },
      ]);
      monitoringHelpers.clear(60);
      expect(conversationMonitor.clearSession).toHaveBeenCalled();
    });

    it('should provide help helper', () => {
      const consoleSpy = vi.spyOn(console, 'group').mockImplementation(() => {});
      monitoringHelpers.help();
      expect(consoleSpy).toHaveBeenCalled();
    });
  });
});

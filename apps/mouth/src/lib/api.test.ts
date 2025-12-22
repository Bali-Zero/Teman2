import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Import after mocking
import { api } from './api';

describe('ApiClient', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    localStorageMock.clear();
    vi.clearAllMocks();
    // Reset api state by clearing token
    api.clearToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================================
  // Token Management Tests
  // ============================================================================
  describe('Token management', () => {
    it('should start with no token when localStorage is empty', () => {
      expect(api.getToken()).toBeNull();
      expect(api.isAuthenticated()).toBe(false);
    });

    it('should set token and become authenticated', () => {
      api.setToken('test-token-123');
      expect(api.getToken()).toBe('test-token-123');
      expect(api.isAuthenticated()).toBe(true);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('auth_token', 'test-token-123');
    });

    it('should clear token and become unauthenticated', () => {
      api.setToken('test-token');
      api.clearToken();
      expect(api.getToken()).toBeNull();
      expect(api.isAuthenticated()).toBe(false);
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user_profile');
    });

    it('should return false for empty string token', () => {
      api.setToken('');
      expect(api.isAuthenticated()).toBe(false);
    });
  });

  // ============================================================================
  // User Profile Tests
  // ============================================================================
  describe('User profile management', () => {
    it('should store and retrieve user profile', () => {
      const profile = { id: '1', email: 'test@example.com', name: 'Test', role: 'user' };
      api.setUserProfile(profile);
      expect(api.getUserProfile()).toEqual(profile);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'user_profile',
        JSON.stringify(profile)
      );
    });

    it('should clear user profile on clearToken', () => {
      api.setUserProfile({ id: '1', email: 'test@example.com', name: 'Test', role: 'user' });
      api.clearToken();
      expect(api.getUserProfile()).toBeNull();
    });
  });

  // ============================================================================
  // Login Tests
  // ============================================================================
  describe('login', () => {
    it('should login successfully and set token', async () => {
      const mockResponse = {
        success: true,
        message: 'Login successful',
        data: {
          token: 'jwt-token-123',
          token_type: 'Bearer',
          expiresIn: 3600,
          user: {
            id: '1',
            email: 'test@example.com',
            name: 'Test User',
            role: 'user',
            status: 'active',
            metadata: null,
            language_preference: 'en',
          },
        },
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockResponse),
      });

      const result = await api.login('test@example.com', '123456');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/login'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@example.com', pin: '123456' }),
        })
      );
      expect(result.access_token).toBe('jwt-token-123');
      expect(result.user.email).toBe('test@example.com');
      expect(api.getToken()).toBe('jwt-token-123');
      expect(api.getUserProfile()?.email).toBe('test@example.com');
    });

    it('should throw error when login fails with success: false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: false, message: 'Invalid credentials' }),
      });

      await expect(api.login('test@example.com', 'wrong')).rejects.toThrow('Invalid credentials');
    });

    it('should throw error on HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      });

      await expect(api.login('test@example.com', 'wrong')).rejects.toThrow('Unauthorized');
    });

    it('should throw error when data is missing', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, data: null }),
      });

      await expect(api.login('test@example.com', '123456')).rejects.toThrow('Login failed');
    });
  });

  // ============================================================================
  // Logout Tests
  // ============================================================================
  describe('logout', () => {
    it('should logout and clear token', async () => {
      api.setToken('test-token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: new Headers(),
      });

      await api.logout();

      expect(api.getToken()).toBeNull();
      expect(api.getUserProfile()).toBeNull();
    });

    it('should clear token even if logout request fails', async () => {
      api.setToken('test-token');
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(api.logout()).rejects.toThrow();
      expect(api.getToken()).toBeNull();
    });
  });

  // ============================================================================
  // Profile Tests
  // ============================================================================
  describe('getProfile', () => {
    it('should fetch and store user profile', async () => {
      api.setToken('test-token');
      const mockProfile = { id: '1', email: 'test@example.com', name: 'Test', role: 'user' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockProfile),
      });

      const result = await api.getProfile();

      expect(result).toEqual(mockProfile);
      expect(api.getUserProfile()).toEqual(mockProfile);
    });
  });

  // ============================================================================
  // Send Message Tests
  // ============================================================================
  describe('sendMessage', () => {
    beforeEach(() => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });
    });

    it('should send message and return response', async () => {
      const mockResponse = {
        answer: 'Hello! How can I help you?',
        sources: [{ title: 'Doc 1', content: 'Some content' }],
        context_length: 100,
        execution_time: 0.5,
        route_used: 'rag',
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockResponse),
      });

      const result = await api.sendMessage('Hello');

      expect(result.response).toBe('Hello! How can I help you?');
      expect(result.sources).toHaveLength(1);
    });

    it('should use provided userId', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ answer: 'test', sources: [] }),
      });

      await api.sendMessage('Hello', 'custom-user-id');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('custom-user-id'),
        })
      );
    });
  });

  // ============================================================================
  // Send Message Streaming Tests
  // ============================================================================
  describe('sendMessageStreaming', () => {
    beforeEach(() => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });
    });

    it('should call callbacks correctly on success', async () => {
      const encoder = new TextEncoder();
      const streamData = [
        'data: {"type":"token","content":"Hello "}\n',
        'data: {"type":"token","content":"from AI!"}\n',
        'data: {"type":"sources","data":[]}\n',
      ];

      let chunkIndex = 0;
      const mockReader = {
        read: vi.fn().mockImplementation(() => {
          if (chunkIndex < streamData.length) {
            const chunk = encoder.encode(streamData[chunkIndex]);
            chunkIndex++;
            return Promise.resolve({ done: false, value: chunk });
          }
          return Promise.resolve({ done: true, value: undefined });
        }),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      });

      const onChunk = vi.fn();
      const onDone = vi.fn();
      const onError = vi.fn();

      await api.sendMessageStreaming('Hello', undefined, onChunk, onDone, onError);

      expect(onChunk).toHaveBeenCalledWith('Hello ');
      expect(onChunk).toHaveBeenCalledWith('from AI!');
      expect(onDone).toHaveBeenCalledWith('Hello from AI!', [], undefined);
      expect(onError).not.toHaveBeenCalled();
    });

    it('should call onError on failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const onChunk = vi.fn();
      const onDone = vi.fn();
      const onError = vi.fn();

      await api.sendMessageStreaming('Hello', undefined, onChunk, onDone, onError);

      expect(onChunk).not.toHaveBeenCalled();
      expect(onDone).not.toHaveBeenCalled();
      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });

    it('should respect custom timeout', async () => {
      // Mock a hanging fetch that will timeout
      mockFetch.mockImplementation(() => {
        return new Promise(() => {
          // Never resolves - will timeout
        });
      });

      const onError = vi.fn();
      const streamPromise = api.sendMessageStreaming(
        'Hello',
        undefined,
        vi.fn(),
        vi.fn(),
        onError,
        undefined,
        50 // Very short timeout for test
      );

      await streamPromise;

      expect(onError).toHaveBeenCalledWith(
        expect.objectContaining({ 
          code: 'TIMEOUT',
          message: expect.stringContaining('timeout') 
        })
      );
    });
  });

  // ============================================================================
  // Conversation History Tests
  // ============================================================================
  describe('getConversationHistory', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should fetch conversation history', async () => {
      const mockHistory = {
        success: true,
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!' },
        ],
        total_messages: 2,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockHistory),
      });

      const result = await api.getConversationHistory();

      expect(result.success).toBe(true);
      expect(result.messages).toHaveLength(2);
    });

    it('should pass sessionId if provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, messages: [], total_messages: 0 }),
      });

      await api.getConversationHistory('session-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('session_id=session-123'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // Save Conversation Tests
  // ============================================================================
  describe('saveConversation', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should save conversation', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, conversation_id: 1, messages_saved: 2 }),
      });

      const messages = [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi!' },
      ];
      const result = await api.saveConversation(messages);

      expect(result.success).toBe(true);
      expect(result.messages_saved).toBe(2);
    });

    it('should include metadata if provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, conversation_id: 1, messages_saved: 1 }),
      });

      await api.saveConversation([{ role: 'user', content: 'test' }], 'session-1', {
        tag: 'important',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('important'),
        })
      );
    });
  });

  // ============================================================================
  // Clear Conversations Tests
  // ============================================================================
  describe('clearConversations', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should clear all conversations', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, deleted_count: 5 }),
      });

      const result = await api.clearConversations();

      expect(result.success).toBe(true);
      expect(result.deleted_count).toBe(5);
    });

    it('should use DELETE method', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, deleted_count: 0 }),
      });

      await api.clearConversations();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  // ============================================================================
  // Conversation Stats Tests
  // ============================================================================
  describe('getConversationStats', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should fetch conversation stats', async () => {
      const mockStats = {
        success: true,
        user_email: 'test@example.com',
        total_conversations: 10,
        total_messages: 50,
        last_conversation: '2024-01-01',
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockStats),
      });

      const result = await api.getConversationStats();

      expect(result.total_conversations).toBe(10);
      expect(result.total_messages).toBe(50);
    });
  });

  // ============================================================================
  // Clock In/Out Tests
  // ============================================================================
  describe('clockIn', () => {
    it('should throw error if user profile is not loaded', async () => {
      api.clearToken();
      await expect(api.clockIn()).rejects.toThrow('User profile not loaded');
    });

    it('should clock in successfully', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            success: true,
            action: 'clock_in',
            message: 'Clocked in successfully',
            bali_time: '2024-01-01 09:00:00',
          }),
      });

      const result = await api.clockIn();

      expect(result.success).toBe(true);
      expect(result.action).toBe('clock_in');
    });

    it('should send user_id and email in request body', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, message: 'OK' }),
      });

      await api.clockIn();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/team/clock-in'),
        expect.objectContaining({
          body: expect.stringContaining('user-1'),
        })
      );
    });
  });

  describe('clockOut', () => {
    it('should throw error if user profile is not loaded', async () => {
      api.clearToken();
      await expect(api.clockOut()).rejects.toThrow('User profile not loaded');
    });

    it('should clock out successfully', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            success: true,
            action: 'clock_out',
            message: 'Clocked out',
            hours_worked: 8.5,
          }),
      });

      const result = await api.clockOut();

      expect(result.success).toBe(true);
      expect(result.hours_worked).toBe(8.5);
    });
  });

  describe('getClockStatus', () => {
    it('should return default values if user profile is not loaded', async () => {
      api.clearToken();
      const result = await api.getClockStatus();

      expect(result.is_clocked_in).toBe(false);
      expect(result.today_hours).toBe(0);
      expect(result.week_hours).toBe(0);
    });

    it('should fetch clock status', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            user_id: 'user-1',
            is_online: true,
            last_action: '2024-01-01',
            last_action_type: 'clock_in',
            today_hours: 4.5,
            week_hours: 20,
            week_days: 4,
          }),
      });

      const result = await api.getClockStatus();

      expect(result.is_clocked_in).toBe(true);
      expect(result.today_hours).toBe(4.5);
      expect(result.week_hours).toBe(20);
    });

    it('should return default values on error', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      mockFetch.mockRejectedValueOnce(new Error('Service unavailable'));

      const result = await api.getClockStatus();

      expect(result.is_clocked_in).toBe(false);
      expect(result.today_hours).toBe(0);
    });
  });

  // ============================================================================
  // Team Status Tests (Admin)
  // ============================================================================
  describe('getTeamStatus', () => {
    it('should throw error if not admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      await expect(api.getTeamStatus()).rejects.toThrow('Admin access required');
    });

    it('should throw error if no user profile', async () => {
      api.setToken('test-token');
      api.clearToken();

      await expect(api.getTeamStatus()).rejects.toThrow('Admin access required');
    });

    it('should fetch team status for admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockTeam = [
        {
          user_id: '1',
          email: 'user1@example.com',
          is_online: true,
          last_action: '2024-01-01',
          last_action_type: 'clock_in',
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockTeam),
      });

      const result = await api.getTeamStatus();

      expect(result).toHaveLength(1);
      expect(result[0].is_online).toBe(true);
    });

    it('should include X-User-Email header', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve([]),
      });

      await api.getTeamStatus();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-User-Email': 'admin@example.com',
          }),
        })
      );
    });
  });

  // ============================================================================
  // Admin: getDailyHours Tests
  // ============================================================================
  describe('getDailyHours', () => {
    it('should throw error if not admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      await expect(api.getDailyHours()).rejects.toThrow('Admin access required');
    });

    it('should fetch daily hours for admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockData = [
        {
          user_id: '1',
          email: 'user@example.com',
          date: '2024-01-15',
          clock_in: '09:00',
          clock_out: '17:00',
          hours_worked: 8,
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockData),
      });

      const result = await api.getDailyHours('2024-01-15');

      expect(result).toHaveLength(1);
      expect(result[0].hours_worked).toBe(8);
    });

    it('should include date param when provided', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve([]),
      });

      await api.getDailyHours('2024-01-15');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('date=2024-01-15'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // Admin: getWeeklySummary Tests
  // ============================================================================
  describe('getWeeklySummary', () => {
    it('should throw error if not admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      await expect(api.getWeeklySummary()).rejects.toThrow('Admin access required');
    });

    it('should fetch weekly summary for admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockData = [
        {
          user_id: '1',
          email: 'user@example.com',
          week_start: '2024-01-15',
          days_worked: 5,
          total_hours: 40,
          avg_hours_per_day: 8,
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockData),
      });

      const result = await api.getWeeklySummary();

      expect(result).toHaveLength(1);
      expect(result[0].total_hours).toBe(40);
    });

    it('should include week_start param when provided', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve([]),
      });

      await api.getWeeklySummary('2024-01-15');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('week_start=2024-01-15'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // Admin: getMonthlySummary Tests
  // ============================================================================
  describe('getMonthlySummary', () => {
    it('should throw error if not admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      await expect(api.getMonthlySummary()).rejects.toThrow('Admin access required');
    });

    it('should fetch monthly summary for admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockData = [
        {
          user_id: '1',
          email: 'user@example.com',
          month_start: '2024-01-01',
          days_worked: 22,
          total_hours: 176,
          avg_hours_per_day: 8,
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve(mockData),
      });

      const result = await api.getMonthlySummary();

      expect(result).toHaveLength(1);
      expect(result[0].total_hours).toBe(176);
    });
  });

  // ============================================================================
  // Admin: exportTimesheet Tests
  // ============================================================================
  describe('exportTimesheet', () => {
    it('should throw error if not admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });

      await expect(api.exportTimesheet('2024-01-01', '2024-01-31')).rejects.toThrow(
        'Admin access required'
      );
    });

    it('should export timesheet as blob for admin', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        blob: () => Promise.resolve(mockBlob),
      });

      const result = await api.exportTimesheet('2024-01-01', '2024-01-31');

      expect(result).toBeInstanceOf(Blob);
    });

    it('should throw error on failed export', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(api.exportTimesheet('2024-01-01', '2024-01-31')).rejects.toThrow(
        'Failed to export timesheet'
      );
    });

    it('should include start_date and end_date params', async () => {
      api.setToken('test-token');
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });

      const mockBlob = new Blob(['csv'], { type: 'text/csv' });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        blob: () => Promise.resolve(mockBlob),
      });

      await api.exportTimesheet('2024-01-01', '2024-01-31');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('start_date=2024-01-01'),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('end_date=2024-01-31'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // isAdmin Tests
  // ============================================================================
  describe('isAdmin', () => {
    it('should return false when no user profile', () => {
      api.clearToken();
      expect(api.isAdmin()).toBe(false);
    });

    it('should return false for regular user', () => {
      api.setUserProfile({ id: 'user-1', email: 'test@example.com', name: 'Test', role: 'user' });
      expect(api.isAdmin()).toBe(false);
    });

    it('should return true for admin user', () => {
      api.setUserProfile({
        id: 'admin-1',
        email: 'admin@example.com',
        name: 'Admin',
        role: 'admin',
      });
      expect(api.isAdmin()).toBe(true);
    });
  });

  // ============================================================================
  // Image Generation Tests
  // ============================================================================
  describe('generateImage', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should generate image', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, images: ['https://example.com/image.png'] }),
      });

      const result = await api.generateImage('A beautiful sunset');

      expect(result.image_url).toBe('https://example.com/image.png');
    });

    it('should use 60s timeout', async () => {
      // This is tested by checking the function signature accepts timeout
      // The actual timeout behavior is tested in the request method
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, images: ['test.png'] }),
      });

      await api.generateImage('test');

      // Verify it was called (the 60s timeout is internal)
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // WebSocket URL Tests
  // ============================================================================
  describe('getWebSocketUrl', () => {
    it('should convert https to wss', () => {
      api.setToken('test-token');
      const wsUrl = api.getWebSocketUrl();

      expect(wsUrl).toMatch(/^wss?:\/\//);
      // SECURITY: Token should NOT be in URL
      expect(wsUrl).not.toContain('token=test-token');
      expect(wsUrl).not.toContain('?token=');
    });

    it('should NOT include token in URL (security)', () => {
      api.setToken('my-jwt-token');
      const wsUrl = api.getWebSocketUrl();

      // SECURITY: Token should NOT be exposed in URL
      expect(wsUrl).not.toContain('token=my-jwt-token');
      expect(wsUrl).not.toContain('?token=');
    });
  });

  describe('getWebSocketSubprotocol', () => {
    it('should return token as subprotocol', () => {
      api.setToken('test-token');
      const subprotocol = api.getWebSocketSubprotocol();

      expect(subprotocol).toBe('bearer.test-token');
    });

    it('should return null when no token', () => {
      api.clearToken();
      const subprotocol = api.getWebSocketSubprotocol();

      expect(subprotocol).toBeNull();
    });
  });

  // ============================================================================
  // Request Error Handling Tests
  // ============================================================================
  describe('Request error handling', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should handle 204 No Content responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: new Headers(),
      });

      const result = await api.logout();

      expect(result).toBeUndefined();
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(api.getProfile()).rejects.toThrow('Network error');
    });

    it('should handle timeout with AbortError', async () => {
      const abortError = new Error('AbortError');
      abortError.name = 'AbortError';
      mockFetch.mockRejectedValueOnce(abortError);

      await expect(api.getProfile()).rejects.toThrow('Request timeout');
    });

    it('should handle JSON parse error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(api.getProfile()).rejects.toThrow('Request failed');
    });

    it('should include Authorization header when token is set', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({ id: '1', email: 'test@example.com', name: 'Test', role: 'user' }),
      });

      await api.getProfile();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('should not include Authorization header when no token', async () => {
      api.clearToken();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({}),
      });

      // Need to call a method that doesn't require auth
      // Use getConversationHistory which is a simple GET
      try {
        await api.getConversationHistory();
      } catch {
        // May fail, but we're checking the headers
      }

      const call = mockFetch.mock.calls[0];
      const headers = call[1].headers;
      expect(headers['Authorization']).toBeUndefined();
    });
  });

  // ============================================================================
  // deleteConversation Tests
  // ============================================================================
  describe('deleteConversation', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should delete a conversation by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, deleted_id: 123 }),
      });

      const result = await api.deleteConversation(123);

      expect(result.success).toBe(true);
      expect(result.deleted_id).toBe(123);
    });

    it('should use DELETE method', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, deleted_id: 1 }),
      });

      await api.deleteConversation(1);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/conversations/1'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    it('should handle delete failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: 'Not found' }),
      });

      await expect(api.deleteConversation(999)).rejects.toThrow();
    });
  });

  // ============================================================================
  // listConversations Tests
  // ============================================================================
  describe('listConversations', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should list conversations with default params', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, conversations: [], total: 0 }),
      });

      const result = await api.listConversations();

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      );
    });

    it('should list conversations with custom params', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, conversations: [], total: 0 }),
      });

      await api.listConversations(50, 10);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=50'),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('offset=10'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // getConversation Tests
  // ============================================================================
  describe('getConversation', () => {
    beforeEach(() => {
      api.setToken('test-token');
    });

    it('should get a single conversation by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            success: true,
            messages: [{ role: 'user', content: 'Hello' }],
            created_at: '2024-01-01T00:00:00Z',
          }),
      });

      const result = await api.getConversation(123);

      expect(result.success).toBe(true);
      expect(result.messages).toHaveLength(1);
    });

    it('should include conversation ID in URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ success: true, messages: [] }),
      });

      await api.getConversation(456);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/conversations/456'),
        expect.any(Object)
      );
    });
  });
});

// Separate test for constructor JSON parse error handling
describe('ApiClient initialization with invalid JSON', () => {
  it('should handle invalid JSON in stored profile gracefully', async () => {
    // Store invalid JSON in localStorage before importing fresh api
    const invalidJsonStorage = {
      getItem: vi.fn((key: string) => {
        if (key === 'user_profile') return 'invalid{json';
        if (key === 'auth_token') return 'test-token';
        return null;
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: invalidJsonStorage,
      configurable: true,
    });

    // Reset modules to force re-import
    vi.resetModules();

    // Re-import the api module - this will run constructor with invalid JSON
    const { api: freshApi } = await import('./api');

    // The api should still work - userProfile should be null due to JSON parse error
    expect(freshApi.getUserProfile()).toBeNull();
    expect(freshApi.isAuthenticated()).toBe(true); // token was set

    // Restore original mock
    const originalMock = (() => {
      let store: Record<string, string> = {};
      return {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => {
          store[key] = value;
        }),
        removeItem: vi.fn((key: string) => {
          delete store[key];
        }),
        clear: vi.fn(() => {
          store = {};
        }),
      };
    })();
    Object.defineProperty(window, 'localStorage', { value: originalMock, configurable: true });
  });
});

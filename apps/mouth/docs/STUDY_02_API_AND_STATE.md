# 🔌 PARTE 2: API Client & State Management

> Come il frontend comunica con il backend

---

## Overview

Il frontend usa un API client custom che gestisce:
- HTTP requests (GET, POST, PUT, DELETE)
- SSE streaming
- Authentication (JWT)
- Error handling
- Caching

---

## API Client Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Component Layer                         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Custom Hooks                           │
│   useChatPage, useDrive, useDashboardData, etc.            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Domain API Modules                       │
│   chatApi, crmApi, driveApi, intelligenceApi, etc.         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Base API Client                        │
│                  lib/api/client.ts (11KB)                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                              │
│               NEXT_PUBLIC_API_URL                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Base API Client

**File:** `lib/api/client.ts`

```typescript
class APIClient {
  private baseURL: string;
  private token: string | null = null;
  
  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || '';
    this.loadToken();
  }
  
  // ─────────────────────────────────────────────────────────
  // TOKEN MANAGEMENT
  // ─────────────────────────────────────────────────────────
  
  private loadToken(): void {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token');
    }
  }
  
  setToken(token: string): void {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
    }
  }
  
  getToken(): string | null {
    return this.token;
  }
  
  clearToken(): void {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  }
  
  // ─────────────────────────────────────────────────────────
  // HTTP METHODS
  // ─────────────────────────────────────────────────────────
  
  private async request<T>(
    method: string,
    path: string,
    data?: unknown,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseURL}${path}`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      ...options?.headers,
    };
    
    const config: RequestInit = {
      method,
      headers,
      ...options,
    };
    
    if (data) {
      config.body = JSON.stringify(data);
    }
    
    const response = await fetch(url, config);
    
    // Handle errors
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new APIError(
        error.message || response.statusText,
        response.status,
        error
      );
    }
    
    // Handle empty response
    if (response.status === 204) {
      return undefined as T;
    }
    
    return response.json();
  }
  
  async get<T>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>('GET', path, undefined, options);
  }
  
  async post<T>(path: string, data?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>('POST', path, data, options);
  }
  
  async put<T>(path: string, data?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>('PUT', path, data, options);
  }
  
  async delete<T>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>('DELETE', path, undefined, options);
  }
  
  // ─────────────────────────────────────────────────────────
  // STREAMING (SSE)
  // ─────────────────────────────────────────────────────────
  
  async *stream(
    path: string,
    data?: unknown
  ): AsyncGenerator<string, void, unknown> {
    const url = `${this.baseURL}${path}`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      throw new APIError('Stream failed', response.status);
    }
    
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    
    if (!reader) {
      throw new APIError('No response body', 500);
    }
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      
      // Parse SSE format
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6);
          if (jsonStr === '[DONE]') {
            return;
          }
          try {
            const data = JSON.parse(jsonStr);
            if (data.content) {
              yield data.content;
            }
          } catch {
            // Ignore parse errors
          }
        }
      }
    }
  }
  
  // ─────────────────────────────────────────────────────────
  // FILE UPLOAD
  // ─────────────────────────────────────────────────────────
  
  async upload<T>(
    path: string,
    formData: FormData,
    onProgress?: (percent: number) => void
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      xhr.open('POST', `${this.baseURL}${path}`);
      
      if (this.token) {
        xhr.setRequestHeader('Authorization', `Bearer ${this.token}`);
      }
      
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress((e.loaded / e.total) * 100);
        }
      };
      
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new APIError('Upload failed', xhr.status));
        }
      };
      
      xhr.onerror = () => {
        reject(new APIError('Upload failed', 0));
      };
      
      xhr.send(formData);
    });
  }
  
  // ─────────────────────────────────────────────────────────
  // AUTHENTICATION
  // ─────────────────────────────────────────────────────────
  
  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await this.post<AuthResponse>('/api/auth/login', {
      email,
      password,
    });
    
    if (response.token) {
      this.setToken(response.token);
    }
    
    return response;
  }
  
  async logout(): Promise<void> {
    try {
      await this.post('/api/auth/logout');
    } finally {
      this.clearToken();
      this.clearUserProfile();
    }
  }
  
  // ─────────────────────────────────────────────────────────
  // USER PROFILE
  // ─────────────────────────────────────────────────────────
  
  async getProfile(): Promise<UserProfile> {
    const profile = await this.get<UserProfile>('/api/users/me');
    this.setUserProfile(profile);
    return profile;
  }
  
  setUserProfile(profile: UserProfile): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem('user_profile', JSON.stringify(profile));
    }
  }
  
  getUserProfile(): UserProfile | null {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('user_profile');
      return stored ? JSON.parse(stored) : null;
    }
    return null;
  }
  
  clearUserProfile(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('user_profile');
    }
  }
}

// Singleton export
export const api = new APIClient();
```

---

## Domain API Modules

### Chat API
**File:** `lib/api/chat/index.ts`

```typescript
import { api } from '../client';

export const chatApi = {
  send: (data: SendMessageRequest) => 
    api.post<SendMessageResponse>('/api/chat/send', data),
  
  stream: (data: SendMessageRequest) =>
    api.stream('/api/chat/stream', data),
  
  getConversation: (id: string) =>
    api.get<Conversation>(`/api/conversations/${id}`),
  
  listConversations: (params?: ListParams) =>
    api.get<Conversation[]>('/api/conversations', { params }),
  
  deleteConversation: (id: string) =>
    api.delete(`/api/conversations/${id}`),
  
  feedback: (messageId: string, rating: number) =>
    api.post('/api/feedback', { messageId, rating }),
};
```

### CRM API
**File:** `lib/api/crm/index.ts`

```typescript
export const crmApi = {
  // Clients
  listClients: (params?: ListParams) =>
    api.get<Client[]>('/api/crm/clients', { params }),
  
  getClient: (id: string) =>
    api.get<Client>(`/api/crm/clients/${id}`),
  
  createClient: (data: CreateClientRequest) =>
    api.post<Client>('/api/crm/clients', data),
  
  updateClient: (id: string, data: UpdateClientRequest) =>
    api.put<Client>(`/api/crm/clients/${id}`, data),
  
  deleteClient: (id: string) =>
    api.delete(`/api/crm/clients/${id}`),
  
  // Practices
  listPractices: (clientId: string) =>
    api.get<Practice[]>(`/api/crm/clients/${clientId}/practices`),
  
  createPractice: (clientId: string, data: CreatePracticeRequest) =>
    api.post<Practice>(`/api/crm/clients/${clientId}/practices`, data),
  
  // Interactions
  logInteraction: (clientId: string, data: InteractionRequest) =>
    api.post(`/api/crm/clients/${clientId}/interactions`, data),
};
```

### Drive API
**File:** `lib/api/drive/index.ts`

```typescript
export const driveApi = {
  listFiles: (folderId?: string) =>
    api.get<DriveFile[]>('/api/drive/files', { 
      params: folderId ? { folderId } : undefined 
    }),
  
  getFile: (fileId: string) =>
    api.get<DriveFile>(`/api/drive/files/${fileId}`),
  
  uploadFile: (file: File, folderId?: string, onProgress?: (p: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    if (folderId) formData.append('folderId', folderId);
    return api.upload<DriveFile>('/api/drive/upload', formData, onProgress);
  },
  
  createFolder: (name: string, parentId?: string) =>
    api.post<DriveFile>('/api/drive/folders', { name, parentId }),
  
  moveFile: (fileId: string, targetFolderId: string) =>
    api.put(`/api/drive/files/${fileId}/move`, { targetFolderId }),
  
  deleteFile: (fileId: string) =>
    api.delete(`/api/drive/files/${fileId}`),
  
  search: (query: string) =>
    api.get<DriveFile[]>('/api/drive/search', { params: { q: query } }),
};
```

### Intelligence API
**File:** `lib/api/intelligence.api.ts`

```typescript
export const intelligenceApi = {
  // News/Articles
  listArticles: (params?: ArticleListParams) =>
    api.get<Article[]>('/api/intel/articles', { params }),
  
  getArticle: (id: string) =>
    api.get<Article>(`/api/intel/articles/${id}`),
  
  createArticle: (data: CreateArticleRequest) =>
    api.post<Article>('/api/intel/articles', data),
  
  publishArticle: (id: string) =>
    api.post(`/api/intel/articles/${id}/publish`),
  
  // AI Article Composer
  generateArticle: (topic: string, style?: string) =>
    api.stream('/api/intel/compose', { topic, style }),
  
  // Analytics
  getAnalytics: (dateRange?: DateRange) =>
    api.get<AnalyticsData>('/api/intel/analytics', { params: dateRange }),
  
  // System Pulse
  getSystemPulse: () =>
    api.get<SystemPulse>('/api/intel/pulse'),
};
```

---

## State Management

### Pattern: Custom Hooks + Local State

Il frontend NON usa Redux/Zustand globali. Invece:

```typescript
// Pattern 1: Hook with internal state
function useFeature() {
  const [data, setData] = useState<Data | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await api.get('/api/feature');
      setData(result);
    } catch (e) {
      setError(e as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  return { data, isLoading, error, load };
}

// Pattern 2: Hook composition
function useComplexFeature() {
  const { data: users } = useUsers();
  const { data: settings } = useSettings();
  
  // Derive state
  const filteredUsers = useMemo(() => 
    users?.filter(u => settings?.showInactive || u.active),
    [users, settings]
  );
  
  return { filteredUsers };
}
```

### Context Providers

```typescript
// providers/AuthProvider.tsx
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    // Check auth on mount
    const token = api.getToken();
    if (token) {
      api.getProfile()
        .then(setUser)
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);
  
  const login = async (email: string, password: string) => {
    const response = await api.login(email, password);
    setUser(response.user);
    return response;
  };
  
  const logout = async () => {
    await api.logout();
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

---

## Error Handling

```typescript
// Custom error class
class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
  
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
  
  get isNotFound(): boolean {
    return this.status === 404;
  }
  
  get isServerError(): boolean {
    return this.status >= 500;
  }
}

// Global error handler
function handleAPIError(error: unknown) {
  if (error instanceof APIError) {
    if (error.isUnauthorized) {
      // Redirect to login
      router.push('/login');
      return;
    }
    
    // Show toast
    toast.error(error.message);
  } else {
    toast.error('An unexpected error occurred');
  }
}
```

---

## Caching Strategy

```typescript
// Simple in-memory cache for hooks
const cache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function useCachedData<T>(key: string, fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(() => {
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data as T;
    }
    return null;
  });
  
  const [isLoading, setIsLoading] = useState(!data);
  
  useEffect(() => {
    if (data) return; // Already have cached data
    
    fetcher()
      .then(result => {
        setData(result);
        cache.set(key, { data: result, timestamp: Date.now() });
      })
      .finally(() => setIsLoading(false));
  }, [key, fetcher, data]);
  
  const invalidate = useCallback(() => {
    cache.delete(key);
    setData(null);
    setIsLoading(true);
  }, [key]);
  
  return { data, isLoading, invalidate };
}
```

---

## WebSocket Connection

**File:** `lib/api/websocket/index.ts`

```typescript
class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners = new Map<string, Set<Function>>();
  
  connect(url: string, token: string): void {
    this.ws = new WebSocket(`${url}?token=${token}`);
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.emit('connected');
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.emit(data.type, data.payload);
    };
    
    this.ws.onclose = () => {
      this.emit('disconnected');
      this.scheduleReconnect();
    };
    
    this.ws.onerror = (error) => {
      this.emit('error', error);
    };
  }
  
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }
    
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    
    setTimeout(() => {
      if (this.ws?.readyState === WebSocket.CLOSED) {
        this.connect(this.ws.url, ''); // Re-get token
      }
    }, delay);
  }
  
  on(event: string, callback: Function): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    
    return () => this.listeners.get(event)?.delete(callback);
  }
  
  private emit(event: string, data?: unknown): void {
    this.listeners.get(event)?.forEach(cb => cb(data));
  }
  
  send(type: string, payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    }
  }
  
  disconnect(): void {
    this.ws?.close();
  }
}

export const wsClient = new WebSocketClient();
```

---

## Types

**File:** `lib/types/api.ts`

```typescript
// Common
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

interface ListParams {
  page?: number;
  pageSize?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

// Auth
interface AuthResponse {
  token: string;
  user: User;
  expiresAt: string;
}

// User
interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'member' | 'client';
  avatar?: string;
}

// Message
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  sources?: Source[];
}

// Conversation
interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}
```

---

*"Clean API, clean code" 🔌*

# Logger with Sentry Integration - Usage Guide

## Overview

The logger utility (`src/lib/logger.ts`) now includes full Sentry integration for production error tracking and monitoring.

## Features

- ✅ **Console Logging** - Formatted logs with emojis and timestamps
- ✅ **Sentry Integration** - Automatic error/warning reporting in production
- ✅ **Local Storage Backup** - Error logs stored locally for debugging
- ✅ **Log History** - In-memory log buffer (last 100 entries)
- ✅ **User Context** - Track errors by user
- ✅ **Convenience Methods** - Specialized logging for common scenarios

## Basic Usage

### Import the Logger

```typescript
import { logger } from '@/lib/logger';
```

### Log Levels

```typescript
// DEBUG - Development only, not sent to Sentry
logger.debug('Debug message', { component: 'MyComponent' });

// INFO - Console only, not sent to Sentry
logger.info('User logged in', { component: 'AuthProvider', userId: 'user123' });

// WARN - Console + Sentry in production
logger.warn('API rate limit approaching', { component: 'ApiClient', endpoint: '/api/users' });

// ERROR - Console + Sentry in production
logger.error('Failed to load data', { component: 'DataLoader' }, error);
```

## User Context (Important!)

### Set User Context on Login

```typescript
import { logger } from '@/lib/logger';

// After successful authentication
const handleLogin = async (email: string, password: string) => {
  try {
    const user = await loginUser(email, password);

    // Set user context for Sentry
    logger.setUser(user.id, user.email, user.name);

    logger.info('User logged in successfully', {
      component: 'LoginForm',
      userId: user.id,
    });
  } catch (error) {
    logger.error('Login failed', { component: 'LoginForm' }, error);
  }
};
```

### Clear User Context on Logout

```typescript
const handleLogout = () => {
  // Clear user context from Sentry
  logger.clearUser();

  logger.info('User logged out', { component: 'LogoutButton' });
};
```

## Error Logging with Context

### With Exception Object

```typescript
try {
  await api.fetchUserData(userId);
} catch (error) {
  logger.error(
    'Failed to fetch user data',
    {
      component: 'UserProfile',
      action: 'fetch_data',
      userId,
    },
    error instanceof Error ? error : new Error(String(error))
  );
}
```

### Without Exception (Simple Message)

```typescript
if (!isValidInput(input)) {
  logger.error('Invalid input received', {
    component: 'FormValidator',
    action: 'validate',
    reason: 'missing_required_fields',
  });
}
```

## Convenience Methods

### API Logging

```typescript
// Before API call
logger.apiCall('/api/users', 'GET', { component: 'UserService' });

// On success
logger.apiSuccess('/api/users', 150, { component: 'UserService' }); // 150ms response time

// On error
try {
  await fetch('/api/users');
} catch (error) {
  logger.apiError('/api/users', error, { component: 'UserService' });
}
```

### User Action Logging

```typescript
// Track user interactions
logger.userAction(
  'click_button',
  'visa', // itemType (optional)
  'visa123', // itemId (optional)
  { component: 'VisaCard' }
);
```

### Component Lifecycle

```typescript
useEffect(() => {
  logger.componentMount('UserDashboard', { userId: user.id });

  return () => {
    logger.componentUnmount('UserDashboard', { userId: user.id });
  };
}, []);
```

## Log Context Structure

```typescript
interface LogContext {
  component?: string; // Component name (e.g., 'UserProfile')
  action?: string; // Action being performed (e.g., 'fetch_data')
  user?: string; // User ID
  itemId?: string; // Item ID (e.g., 'visa123')
  itemType?: 'visa' | 'news' | 'all'; // Item type
  code?: number | string; // Error code
  reason?: string; // Error reason
  note?: string; // Additional notes
  metadata?: Record<string, unknown>; // Additional metadata
}
```

## Accessing Logs

### Get Log History (In-Memory)

```typescript
const history = logger.getHistory(); // Last 100 log entries
console.log(history);
```

### Get Stored Error Logs (localStorage)

```typescript
const storedErrors = logger.getStoredLogs(); // Last 50 errors
console.log(storedErrors);
```

### Clear Logs

```typescript
logger.clearHistory(); // Clear in-memory history
logger.clearStoredLogs(); // Clear localStorage backup
```

## Production vs Development Behavior

### Development (NODE_ENV !== 'production')

- ✅ All logs shown in console
- ❌ Nothing sent to Sentry
- ❌ Nothing stored in localStorage
- ✅ Debug logs enabled

### Production (NODE_ENV === 'production')

- ✅ Info/Warn/Error logs shown in console
- ✅ Errors sent to Sentry (with exception)
- ✅ Warnings sent to Sentry (as messages)
- ✅ Errors stored in localStorage (backup)
- ❌ Debug logs disabled
- ❌ Info logs NOT sent to Sentry (reduce noise)

## Sentry Dashboard

All errors and warnings are automatically sent to Sentry in production:

**Dashboard:** https://sentry.io/organizations/bali-zero-7p/issues/

What you'll see:
- ✅ Error message and stack trace
- ✅ User context (if set)
- ✅ Component and action tags
- ✅ Full context data
- ✅ Browser info, URL, timestamp
- ✅ Session replay (if available)

## Best Practices

### 1. Always Provide Context

```typescript
// ❌ Bad - No context
logger.error('Something went wrong');

// ✅ Good - With context
logger.error('Failed to save user profile', {
  component: 'ProfileEditor',
  action: 'save',
  userId: user.id,
});
```

### 2. Use Appropriate Log Levels

```typescript
// DEBUG - Detailed technical info (dev only)
logger.debug('Component state updated', { state: newState });

// INFO - General informational messages
logger.info('User completed onboarding', { userId: user.id });

// WARN - Potential issues that should be monitored
logger.warn('API response time exceeded threshold', { responseTime: 5000 });

// ERROR - Actual errors that need attention
logger.error('Payment processing failed', { orderId: '123' }, error);
```

### 3. Set User Context Early

```typescript
// ✅ Set on login
const handleLogin = async () => {
  const user = await login();
  logger.setUser(user.id, user.email, user.name);
};

// ✅ Clear on logout
const handleLogout = () => {
  logger.clearUser();
};
```

### 4. Handle Errors Properly

```typescript
try {
  await riskyOperation();
} catch (error) {
  // ✅ Log with proper error object
  logger.error(
    'Operation failed',
    { component: 'MyComponent', action: 'riskyOperation' },
    error instanceof Error ? error : new Error(String(error))
  );

  // Show user-friendly message
  toast.error('Something went wrong. Please try again.');
}
```

### 5. Use Convenience Methods

```typescript
// ✅ Use specific methods for common scenarios
logger.apiCall('/api/users', 'POST');
logger.apiSuccess('/api/users', 120);
logger.apiError('/api/users', error);

logger.userAction('submit_form', 'visa', visaId);

logger.componentMount('UserDashboard');
logger.componentUnmount('UserDashboard');
```

## Common Patterns

### Form Submission

```typescript
const handleSubmit = async (formData: FormData) => {
  logger.userAction('submit_form', undefined, undefined, {
    component: 'VisaApplicationForm',
  });

  try {
    await api.submitApplication(formData);

    logger.info('Form submitted successfully', {
      component: 'VisaApplicationForm',
      action: 'submit',
    });

    toast.success('Application submitted!');
  } catch (error) {
    logger.error(
      'Form submission failed',
      {
        component: 'VisaApplicationForm',
        action: 'submit',
      },
      error
    );

    toast.error('Failed to submit. Please try again.');
  }
};
```

### API Request with Retry

```typescript
const fetchWithRetry = async (url: string, retries = 3) => {
  logger.apiCall(url, 'GET', { component: 'ApiClient' });

  for (let i = 0; i < retries; i++) {
    try {
      const startTime = Date.now();
      const response = await fetch(url);
      const responseTime = Date.now() - startTime;

      logger.apiSuccess(url, responseTime, { component: 'ApiClient' });

      return response;
    } catch (error) {
      if (i === retries - 1) {
        logger.apiError(url, error, {
          component: 'ApiClient',
          note: `Failed after ${retries} retries`,
        });
        throw error;
      }

      logger.warn(`API retry ${i + 1}/${retries}`, {
        component: 'ApiClient',
        action: 'retry',
        metadata: { url, attempt: i + 1 },
      });
    }
  }
};
```

### React Query Integration

```typescript
import { useQuery } from '@tanstack/react-query';
import { logger } from '@/lib/logger';

export const useUserData = (userId: string) => {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: async () => {
      logger.apiCall(`/api/users/${userId}`, 'GET', {
        component: 'useUserData',
      });

      try {
        const response = await fetch(`/api/users/${userId}`);
        if (!response.ok) throw new Error('Failed to fetch user');

        logger.apiSuccess(`/api/users/${userId}`, 0, {
          component: 'useUserData',
        });

        return response.json();
      } catch (error) {
        logger.apiError(`/api/users/${userId}`, error, {
          component: 'useUserData',
        });
        throw error;
      }
    },
  });
};
```

## Testing

The logger is fully tested with Vitest. Run tests:

```bash
cd apps/mouth
pnpm test src/lib/logger.test.ts
```

## Debugging

### View Logs in Browser Console

All logs are output to console with formatted messages and emojis.

### View Stored Error Logs

```typescript
// In browser console
const logs = logger.getStoredLogs();
console.table(logs);
```

### View Log History

```typescript
// In browser console
const history = logger.getHistory();
console.table(history);
```

### Export Logs for Support

```typescript
// Create a download link for logs
const downloadLogs = () => {
  const logs = logger.getStoredLogs();
  const blob = new Blob([JSON.stringify(logs, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `error-logs-${new Date().toISOString()}.json`;
  a.click();
};
```

## Related Documentation

- [Sentry Configuration](../../../docs/SENTRY_CONFIGURATION.md)
- [Sentry Usage Examples](../../../docs/SENTRY_USAGE_EXAMPLES.md)
- [Logger Source Code](./logger.ts)
- [Logger Tests](./logger.test.ts)

## Support

For issues or questions:
- Check Sentry dashboard: https://sentry.io/organizations/bali-zero-7p/issues/
- Review stored logs: `logger.getStoredLogs()`
- Check log history: `logger.getHistory()`

# Sentry Error Tracking - Usage Examples

## Basic Error Capture

### 1. Capture Exceptions

```typescript
import * as Sentry from "@sentry/nextjs";

try {
  // Your code
  await riskyOperation();
} catch (error) {
  Sentry.captureException(error);
  console.error("Operation failed:", error);
}
```

### 2. Capture Messages

```typescript
import * as Sentry from "@sentry/nextjs";

// Log important events
Sentry.captureMessage("User completed onboarding", "info");

// Log warnings
Sentry.captureMessage("API rate limit approaching", "warning");

// Log errors
Sentry.captureMessage("Payment webhook failed", "error");
```

### 3. Add Context to Errors

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.setUser({
  id: user.id,
  email: user.email,
  username: user.name,
});

Sentry.setContext("company", {
  id: company.id,
  name: company.name,
  plan: company.subscription_plan,
});

Sentry.setTag("feature", "visa-application");
Sentry.setTag("environment", process.env.NODE_ENV);
```

## React Error Boundaries

### Custom Error Boundary with Sentry

```typescript
'use client';

import * as Sentry from '@sentry/nextjs';
import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo.componentStack,
        },
      },
    });
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="p-4 text-center">
          <h2>Something went wrong</h2>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### Usage

```typescript
import { ErrorBoundary } from '@/components/ErrorBoundary';

export default function Page() {
  return (
    <ErrorBoundary fallback={<div>Error loading this section</div>}>
      <YourComponent />
    </ErrorBoundary>
  );
}
```

## API Route Error Tracking

### Next.js API Route

```typescript
// app/api/example/route.ts
import * as Sentry from "@sentry/nextjs";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Your logic
    const result = await processData(body);

    return NextResponse.json({ success: true, data: result });
  } catch (error) {
    // Capture error with request context
    Sentry.captureException(error, {
      contexts: {
        request: {
          url: request.url,
          method: request.method,
          headers: Object.fromEntries(request.headers),
        },
      },
      tags: {
        endpoint: "/api/example",
      },
    });

    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
```

## Server Actions Error Tracking

```typescript
"use server";

import * as Sentry from "@sentry/nextjs";

export async function updateUserProfile(formData: FormData) {
  try {
    const userId = formData.get("userId");
    const name = formData.get("name");

    // Update user
    await db.user.update({
      where: { id: userId },
      data: { name },
    });

    return { success: true };
  } catch (error) {
    Sentry.captureException(error, {
      tags: {
        action: "updateUserProfile",
      },
      extra: {
        userId: formData.get("userId"),
      },
    });

    return { error: "Failed to update profile" };
  }
}
```

## Performance Monitoring

### Trace Custom Operations

```typescript
import * as Sentry from "@sentry/nextjs";

export async function expensiveOperation() {
  const transaction = Sentry.startTransaction({
    op: "task",
    name: "Expensive Operation",
  });

  try {
    // Your expensive operation
    const span1 = transaction.startChild({
      op: "db.query",
      description: "Fetch user data",
    });
    const users = await fetchUsers();
    span1.finish();

    const span2 = transaction.startChild({
      op: "processing",
      description: "Process data",
    });
    const result = processUsers(users);
    span2.finish();

    return result;
  } finally {
    transaction.finish();
  }
}
```

### Measure Component Performance

```typescript
'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export function HeavyComponent() {
  useEffect(() => {
    const transaction = Sentry.startTransaction({
      op: 'component.mount',
      name: 'HeavyComponent',
    });

    // Component mounted
    return () => {
      transaction.finish();
    };
  }, []);

  return <div>Heavy content...</div>;
}
```

## Breadcrumbs (User Journey Tracking)

```typescript
import * as Sentry from '@sentry/nextjs';

// Add breadcrumb for user actions
export function trackUserAction(action: string, data?: Record<string, any>) {
  Sentry.addBreadcrumb({
    category: 'user.action',
    message: action,
    level: 'info',
    data,
  });
}

// Usage in components
function VisaApplicationForm() {
  const handleSubmit = (data: FormData) => {
    trackUserAction('visa_application_submitted', {
      visaType: data.visaType,
      country: data.country,
    });

    // Submit form
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

## Filter Sensitive Data

### Custom beforeSend Hook

Add to `sentry.client.config.ts` or `sentry.server.config.ts`:

```typescript
Sentry.init({
  // ... other config
  beforeSend(event, hint) {
    // Filter sensitive data from URLs
    if (event.request?.url) {
      event.request.url = event.request.url.replace(
        /token=[^&]*/g,
        "token=[FILTERED]",
      );
    }

    // Filter sensitive headers
    if (event.request?.headers) {
      delete event.request.headers["authorization"];
      delete event.request.headers["cookie"];
    }

    // Filter breadcrumb data
    if (event.breadcrumbs) {
      event.breadcrumbs = event.breadcrumbs.map((breadcrumb) => {
        if (breadcrumb.data?.password) {
          breadcrumb.data.password = "[FILTERED]";
        }
        return breadcrumb;
      });
    }

    return event;
  },
});
```

## Ignore Specific Errors

```typescript
Sentry.init({
  // ... other config
  ignoreErrors: [
    // Ignore browser extensions
    "top.GLOBALS",
    "chrome-extension://",

    // Ignore network errors
    "NetworkError",
    "Failed to fetch",

    // Ignore known third-party errors
    "ResizeObserver loop limit exceeded",
  ],

  beforeSend(event) {
    // Custom ignore logic
    if (event.exception) {
      const error = event.exception.values?.[0];
      if (error?.value?.includes("User cancelled")) {
        return null; // Don't send to Sentry
      }
    }
    return event;
  },
});
```

## Integration with React Query

```typescript
import * as Sentry from "@sentry/nextjs";
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      onError: (error) => {
        Sentry.captureException(error, {
          tags: {
            errorType: "react-query",
          },
        });
      },
    },
    mutations: {
      onError: (error, variables, context) => {
        Sentry.captureException(error, {
          tags: {
            errorType: "react-query-mutation",
          },
          extra: {
            variables,
            context,
          },
        });
      },
    },
  },
});
```

## Testing Sentry Integration

### Manual Test Error

```typescript
// Add to a test page temporarily
'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function SentryTestPage() {
  const testError = () => {
    throw new Error('[TEST] Sentry is working!');
  };

  const testMessage = () => {
    Sentry.captureMessage('[TEST] Sentry message', 'info');
  };

  const testException = () => {
    try {
      throw new Error('[TEST] Caught exception');
    } catch (error) {
      Sentry.captureException(error);
    }
  };

  return (
    <div className="p-8">
      <h1>Sentry Test Page</h1>
      <div className="space-y-4">
        <button onClick={testError}>Throw Error</button>
        <button onClick={testMessage}>Send Message</button>
        <button onClick={testException}>Capture Exception</button>
      </div>
    </div>
  );
}
```

### Verify in Sentry Dashboard

After triggering test errors:

1. Go to https://sentry.io/organizations/[your-org]/issues/
2. Verify:
   - Error appears within seconds
   - Stack trace shows correct file/line numbers (source maps working)
   - User context is attached (if logged in)
   - Breadcrumbs show user journey
   - Session replay available (if enabled)

## Production Best Practices

### 1. Set User Context on Login

```typescript
// After successful login
Sentry.setUser({
  id: user.id,
  email: user.email,
  username: user.name,
});
```

### 2. Clear User Context on Logout

```typescript
// On logout
Sentry.setUser(null);
```

### 3. Add Release Tracking

Add to `next.config.ts`:

```typescript
const sentryWebpackPluginOptions = {
  // ... existing config
  release: process.env.VERCEL_GIT_COMMIT_SHA || process.env.FLY_DEPLOYMENT_ID,
};
```

### 4. Monitor Performance Budget

```typescript
Sentry.init({
  // ... other config
  tracesSampler: (samplingContext) => {
    // Sample more for slow endpoints
    if (samplingContext.transactionContext.name?.includes("/api/slow")) {
      return 1.0; // 100%
    }

    // Sample less for fast endpoints
    return 0.1; // 10%
  },
});
```

## Common Patterns

### Wrap Async Operations

```typescript
import * as Sentry from "@sentry/nextjs";

export async function safeAsync<T>(
  operation: () => Promise<T>,
  fallback: T,
  context?: Record<string, any>,
): Promise<T> {
  try {
    return await operation();
  } catch (error) {
    Sentry.captureException(error, { extra: context });
    return fallback;
  }
}

// Usage
const users = await safeAsync(() => fetchUsers(), [], {
  endpoint: "/api/users",
});
```

### Rate Limiting Errors

```typescript
import * as Sentry from "@sentry/nextjs";

const errorCache = new Map<string, number>();
const RATE_LIMIT = 10; // Max 10 errors per minute

export function rateLimitedCapture(error: Error, context?: any) {
  const key = error.message;
  const count = errorCache.get(key) || 0;

  if (count < RATE_LIMIT) {
    Sentry.captureException(error, context);
    errorCache.set(key, count + 1);

    // Reset after 1 minute
    setTimeout(() => errorCache.delete(key), 60000);
  }
}
```

## Resources

- [Sentry Next.js SDK Docs](https://docs.sentry.io/platforms/javascript/guides/nextjs/)
- [Sentry Best Practices](https://docs.sentry.io/platforms/javascript/best-practices/)
- [Sentry Performance Monitoring](https://docs.sentry.io/product/performance/)
- [Session Replay](https://docs.sentry.io/product/session-replay/)

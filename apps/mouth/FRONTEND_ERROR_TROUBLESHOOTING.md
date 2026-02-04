# Frontend Error Troubleshooting Guide

## 🐛 Current Errors

### Error 1: Failed to get auth URL
```
Failed to get auth URL: Error: Request failed
at k.request (36b6329e32e940aa.js:1:7233)
```

### Error 2: React DOM removeChild
```
NotFoundError: Failed to execute 'removeChild' on 'Node': 
The node to be removed is not a child of this node.
```

---

## 🔧 Root Causes & Solutions

### 1. Auth URL Error

**Cause:** Backend API not reachable or environment variable misconfigured

**Check:**

```bash
# 1. Verify environment variables exist
cat apps/mouth/.env.local

# Should contain:
# NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev  # Production
# NEXT_PUBLIC_API_URL=http://localhost:8080          # Local dev
```

**Fix Option A: Missing .env.local**

```bash
cd apps/mouth

# Create from example
cp .env.example .env.local

# Edit .env.local
nano .env.local

# Add:
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NEXT_PUBLIC_WS_URL=wss://nuzantara-rag.fly.dev/ws
```

**Fix Option B: Backend Down**

```bash
# Check backend health
curl https://nuzantara-rag.fly.dev/health

# Should return:
# {"status":"healthy"}

# If not, check Fly.io status
fly status -a nuzantara-rag

# Restart if needed
fly scale count 2 -a nuzantara-rag
```

**Fix Option C: CORS Issue**

If backend returns but browser blocks request:

```python
# apps/backend-rag/backend/app/core/config.py
# Add mouth frontend URL to ALLOWED_ORIGINS

ALLOWED_ORIGINS = [
    "http://localhost:3000",           # Local dev
    "https://mouth.balizero.com",      # Production (add actual URL)
    "https://your-vercel-app.vercel.app"  # Vercel preview
]
```

Then redeploy:

```bash
cd apps/backend-rag
fly deploy -a nuzantara-rag
```

---

### 2. React DOM RemoveChild Error

**Cause:** Component unmounting race condition, likely in Drive or WebSocket components

**Common Scenarios:**

#### A. WebSocket Cleanup Issue

**Problem:** WebSocket connection cleanup called twice or after component unmount

**Fix:** Update WebSocket hook cleanup

```typescript
// apps/mouth/src/hooks/useWebSocket.ts

useEffect(() => {
  let isMounted = true;
  let ws: WebSocket | null = null;

  const connect = () => {
    if (!isMounted) return;
    
    ws = new WebSocket(wsUrl);
    
    ws.onclose = () => {
      if (isMounted) {
        // Only reconnect if still mounted
        setTimeout(connect, 1000);
      }
    };
  };

  connect();

  return () => {
    isMounted = false;
    if (ws) {
      ws.close();
      ws = null;
    }
  };
}, [wsUrl]);
```

#### B. Drive Component Unmount Issue

**Problem:** FileGrid/FileList components unmounting while refs still active

**Fix:** Add ref cleanup guards

```tsx
// apps/mouth/src/app/(workspace)/documents/components/FileGrid.tsx

useEffect(() => {
  const currentRef = containerRef.current;
  
  return () => {
    // Guard: Only cleanup if ref still exists
    if (currentRef && currentRef.parentNode) {
      // Safe cleanup
    }
  };
}, []);
```

#### C. Skeleton Loader Double Unmount

**Problem:** Skeleton components unmounting twice during fast navigation

**Fix:** Add unmount guards

```tsx
// apps/mouth/src/app/(workspace)/documents/components/FileGridSkeleton.tsx

export function FileGridSkeleton() {
  const isMountedRef = useRef(true);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Only render if mounted
  if (!isMountedRef.current) return null;

  return (
    <div className="grid grid-cols-4 gap-4">
      {/* Skeleton items */}
    </div>
  );
}
```

---

## 🚀 Quick Fix Commands

### Full Reset (Nuclear Option)

```bash
cd apps/mouth

# 1. Clean everything
rm -rf .next node_modules .env.local

# 2. Reinstall
npm install

# 3. Create env
cp .env.example .env.local
nano .env.local  # Edit with correct values

# 4. Build & run
npm run build
npm start
```

### Dev Mode Restart

```bash
cd apps/mouth

# Kill all Next.js processes
pkill -f "next dev"

# Clear Next.js cache
rm -rf .next

# Restart
npm run dev
```

### Production Build Test

```bash
cd apps/mouth

# Test production build locally
npm run build
npm start

# Visit http://localhost:3000
# Check browser console for errors
```

---

## 🔍 Debugging Steps

### 1. Enable Verbose Logging

```typescript
// apps/mouth/src/lib/api/client.ts
// Add at top of file

if (typeof window !== 'undefined') {
  (window as any).DEBUG_API = true;
}

// In ApiClientBase.request()
protected async request<T>(options: ApiRequestOptions): Promise<T> {
  if ((window as any).DEBUG_API) {
    console.log('[API] Request:', options.method, options.path);
    console.log('[API] BaseURL:', this.baseUrl);
    console.log('[API] Token:', this.token ? 'Present' : 'Missing');
  }
  
  // ... rest of implementation
}
```

### 2. Check Network Tab

Open browser DevTools → Network tab:

1. Filter by "Fetch/XHR"
2. Look for failed requests (red)
3. Click failed request
4. Check:
   - Request URL (is baseUrl correct?)
   - Status code (404, 500, CORS?)
   - Response body (error message?)

### 3. Check Console Warnings

Look for React warnings:

```
Warning: Can't perform a React state update on an unmounted component
```

This indicates the source component causing the removeChild error.

### 4. React DevTools Profiler

1. Install React DevTools extension
2. Go to Profiler tab
3. Start recording
4. Navigate to page with error
5. Stop recording
6. Look for components with long unmount times

---

## 📋 Environment Variables Checklist

**Production (Vercel/Fly.io):**

```bash
# Vercel Dashboard → Project → Settings → Environment Variables
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NEXT_PUBLIC_WS_URL=wss://nuzantara-rag.fly.dev/ws
```

**Local Development:**

```bash
# apps/mouth/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
```

**Test Environment:**

```bash
# Vercel Preview Deployments
NEXT_PUBLIC_API_URL=https://nuzantara-rag-staging.fly.dev
NEXT_PUBLIC_WS_URL=wss://nuzantara-rag-staging.fly.dev/ws
```

---

## 🎯 Most Likely Fix (80% of cases)

```bash
# 1. Go to mouth app
cd apps/mouth

# 2. Check if .env.local exists
ls -la .env.local

# 3. If missing, create it
cp .env.example .env.local

# 4. Add production API URL
echo "NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev" >> .env.local
echo "NEXT_PUBLIC_WS_URL=wss://nuzantara-rag.fly.dev/ws" >> .env.local

# 5. Restart dev server
pkill -f "next dev"
npm run dev
```

---

## 🔄 If Deployed to Vercel

### Set Environment Variables

```bash
# Via Vercel CLI
cd apps/mouth
vercel env add NEXT_PUBLIC_API_URL

# Enter value: https://nuzantara-rag.fly.dev

vercel env add NEXT_PUBLIC_WS_URL

# Enter value: wss://nuzantara-rag.fly.dev/ws

# Redeploy
vercel --prod
```

### Or Via Dashboard

1. Go to Vercel Dashboard
2. Select `mouth` project
3. Settings → Environment Variables
4. Add:
   - `NEXT_PUBLIC_API_URL` = `https://nuzantara-rag.fly.dev`
   - `NEXT_PUBLIC_WS_URL` = `wss://nuzantara-rag.fly.dev/ws`
5. Redeploy from Deployments tab

---

## 📊 Verification

After applying fixes, verify:

1. **Backend Reachable:**
   ```bash
   curl https://nuzantara-rag.fly.dev/health
   # Should return: {"status":"healthy"}
   ```

2. **Frontend API Calls Work:**
   - Open browser console
   - Navigate to app
   - Check Network tab for successful API calls

3. **No React Errors:**
   - Console should be clean (no red errors)
   - No "removeChild" errors

4. **WebSocket Connected:**
   - Console shows "WebSocket connected"
   - Real-time updates work

---

## 🆘 Still Not Working?

### Collect Debug Info

```bash
# 1. Check backend logs
fly logs -a nuzantara-rag | tail -100

# 2. Check frontend console
# Copy full error stack trace from browser console

# 3. Check environment
cd apps/mouth
cat .env.local
echo "Node version: $(node -v)"
echo "npm version: $(npm -v)"

# 4. Test API directly
curl -I https://nuzantara-rag.fly.dev/api/health
```

### Create GitHub Issue

```markdown
Title: [Frontend] Auth URL error + React DOM removeChild

**Environment:**
- Frontend: [Vercel/Local/Other]
- Backend: Fly.io (nuzantara-rag.fly.dev)
- Browser: [Chrome/Safari/Firefox] [Version]

**Error Logs:**
[Paste full browser console errors]

**Backend Logs:**
[Paste fly logs output]

**Environment Variables:**
NEXT_PUBLIC_API_URL=[value]
NEXT_PUBLIC_WS_URL=[value]

**Steps to Reproduce:**
1. Navigate to...
2. Click on...
3. Error appears

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]
```

---

**Last Updated:** 2026-02-02  
**Status:** Ready for troubleshooting

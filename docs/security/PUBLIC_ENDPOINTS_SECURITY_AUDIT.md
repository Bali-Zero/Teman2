# 🔒 SECURITY AUDIT: Public Endpoints Analysis

**Date:** 2026-01-13  
**Auditor:** AI Security Audit  
**Scope:** Analysis of all public endpoints in `backend/middleware/hybrid_auth.py`

---

## 📊 EXECUTIVE SUMMARY

### Quantification

- **Total Public Endpoints:** 32
- **TEMPORARY Endpoints:** 3 (9.4%)
- **RISKY Endpoints:** 8 (25%)
- **CRITICAL Endpoints:** 21 (65.6%)

### Critical Findings

1. **3 TEMPORARY endpoints** listed in `public_endpoints` but **NOT FOUND** as actual router implementations
2. **8 RISKY endpoints** lack proper rate limiting or verification mechanisms
3. **1 debug endpoint** (`/api/debug/migrate`) marked as public without authentication
4. **Webhook endpoints** have verification but some are optional

---

## 📋 CLASSIFICATION OF PUBLIC ENDPOINTS

### ✅ CRITICAL (Must Be Public) - 21 endpoints

These endpoints **MUST** remain public for legitimate functionality:

| Endpoint                                       | Purpose                | Security Measures          | Status    |
| ---------------------------------------------- | ---------------------- | -------------------------- | --------- |
| `/health`                                      | Health check           | ✅ No sensitive data       | ✅ SAFE   |
| `/health/`                                     | Health check (alt)     | ✅ No sensitive data       | ✅ SAFE   |
| `/docs`                                        | API documentation      | ⚠️ Only in dev/staging     | ✅ SAFE   |
| `/docs/`                                       | API docs (alt)         | ⚠️ Only in dev/staging     | ✅ SAFE   |
| `/openapi.json`                                | OpenAPI spec           | ✅ Public contract         | ✅ SAFE   |
| `/api/v1/openapi.json`                         | OpenAPI spec v1        | ✅ Public contract         | ✅ SAFE   |
| `/redoc`                                       | ReDoc UI               | ⚠️ Only in dev/staging     | ✅ SAFE   |
| `/metrics`                                     | Prometheus metrics     | ⚠️ Should be IP-restricted | ⚠️ REVIEW |
| `/metrics/`                                    | Metrics (alt)          | ⚠️ Should be IP-restricted | ⚠️ REVIEW |
| `/api/auth/team/login`                         | Team login             | ✅ Rate limited            | ✅ SAFE   |
| `/api/auth/login`                              | User login             | ✅ Rate limited            | ✅ SAFE   |
| `/api/auth/csrf-token`                         | CSRF token             | ✅ No sensitive data       | ✅ SAFE   |
| `/api/portal/invite/validate/`                 | Invite validation      | ✅ Token-based             | ✅ SAFE   |
| `/api/portal/invite/complete`                  | Client registration    | ✅ Token-based             | ✅ SAFE   |
| `/api/integrations/zoho/callback`              | Zoho OAuth             | ✅ OAuth flow              | ✅ SAFE   |
| `/api/integrations/google-drive/callback`      | Google OAuth           | ✅ OAuth flow              | ✅ SAFE   |
| `/api/integrations/google-drive/system/status` | OAuth status           | ⚠️ Should be protected     | ⚠️ REVIEW |
| `/api/blog/newsletter/subscribe`               | Newsletter signup      | ✅ Rate limited            | ✅ SAFE   |
| `/api/blog/newsletter/confirm`                 | Newsletter confirm     | ✅ Token-based             | ✅ SAFE   |
| `/api/blog/newsletter/unsubscribe`             | Newsletter unsubscribe | ✅ Token-based             | ✅ SAFE   |
| `/api/blog/ask`                                | AskZantara widget      | ✅ Rate limited            | ✅ SAFE   |

**Notes:**

- `/metrics` endpoints expose internal system metrics - should be IP whitelisted or require authentication
- `/api/integrations/google-drive/system/status` exposes OAuth status - should require authentication

---

### ⚠️ RISKY (Should Be Protected) - 8 endpoints

These endpoints expose sensitive operations or data without proper protection:

| Endpoint                      | Risk Level | Issues                      | Recommendation                              |
| ----------------------------- | ---------- | --------------------------- | ------------------------------------------- |
| `/api/debug/migrate`          | 🔴 HIGH    | Debug endpoint, no auth     | Remove from public or require ADMIN_API_KEY |
| `/api/legal/parent-documents` | 🟡 MEDIUM  | Internal ingestion, no auth | Add API key or IP whitelist                 |
| `/api/intel/scraper/submit`   | 🟡 MEDIUM  | No verification token       | Add secret token verification               |
| `/api/intel/staging/approve/` | 🔴 HIGH    | Auto-approve without auth   | Require authentication or secret token      |
| `/api/audio/`                 | 🟡 MEDIUM  | TTS/STT endpoints, no auth  | Add rate limiting + API key                 |
| `/api/voice/elevenlabs`       | 🟡 MEDIUM  | Webhook, no verification    | Add signature verification                  |
| `/api/knowledge/visa`         | 🟢 LOW     | Public knowledge base       | Add rate limiting                           |
| `/preview/`                   | 🟢 LOW     | Article previews            | Add rate limiting                           |

**Detailed Analysis:**

#### 1. `/api/debug/migrate` - 🔴 HIGH RISK

- **Issue:** Debug endpoint marked as public
- **Risk:** Exposes migration functionality without authentication
- **Impact:** Could allow unauthorized database migrations
- **Fix:** Remove from `public_endpoints` or require `ADMIN_API_KEY`

#### 2. `/api/legal/parent-documents` - 🟡 MEDIUM RISK

- **Issue:** Internal ingestion endpoint without authentication
- **Risk:** Could allow unauthorized document ingestion
- **Impact:** Data pollution, resource exhaustion
- **Fix:** Add API key authentication or IP whitelist

#### 3. `/api/intel/scraper/submit` - 🟡 MEDIUM RISK

- **Issue:** No secret token verification
- **Risk:** Any service can submit articles
- **Impact:** Spam, data pollution
- **Fix:** Add secret token header verification (similar to Telegram webhook)

#### 4. `/api/intel/staging/approve/` - 🔴 HIGH RISK

- **Issue:** Auto-approve endpoint without authentication
- **Risk:** Unauthorized approval of staging items
- **Impact:** Malicious content could be auto-approved
- **Fix:** Require authentication or secret token verification

#### 5. `/api/audio/` - 🟡 MEDIUM RISK

- **Issue:** TTS/STT endpoints without authentication
- **Risk:** Resource exhaustion, cost abuse
- **Impact:** High API costs, service degradation
- **Fix:** Add rate limiting (strict) + API key authentication

#### 6. `/api/voice/elevenlabs` - 🟡 MEDIUM RISK

- **Issue:** Webhook without signature verification
- **Risk:** Spoofed webhook calls
- **Impact:** Unauthorized voice processing
- **Fix:** Add ElevenLabs signature verification

#### 7. `/api/knowledge/visa` - 🟢 LOW RISK

- **Issue:** Public knowledge base without rate limiting
- **Risk:** Potential abuse for scraping
- **Impact:** Resource consumption
- **Fix:** Add rate limiting (moderate: 100/min)

#### 8. `/preview/` - 🟢 LOW RISK

- **Issue:** Article previews without rate limiting
- **Risk:** Potential scraping
- **Impact:** Resource consumption
- **Fix:** Add rate limiting (moderate: 60/min)

---

### 🗑️ TEMPORARY (Must Be Removed) - 3 endpoints

These endpoints are marked as TEMPORARY but **DO NOT EXIST** as router implementations:

| Endpoint               | Status       | Issue                                             |
| ---------------------- | ------------ | ------------------------------------------------- |
| `/api/fix/users-auth`  | ❌ NOT FOUND | Listed in `public_endpoints` but no router exists |
| `/api/fix/check-user/` | ❌ NOT FOUND | Listed in `public_endpoints` but no router exists |
| `/api/fix/test-login`  | ❌ NOT FOUND | Listed in `public_endpoints` but no router exists |

**Analysis:**

- These endpoints are **dead code** - they exist only in the `public_endpoints` list
- No actual router implementation found in codebase
- **Recommendation:** Remove immediately from `public_endpoints` list

**Files to check:**

- `apps/backend-rag/backend/scripts/fix_user_auth.py` - Script exists but no router
- No router files found matching `/api/fix/` pattern

---

### 🔐 WEBHOOK ENDPOINTS - 4 endpoints

Webhook endpoints have verification mechanisms but some are optional:

| Endpoint                | Verification                             | Status    | Risk      |
| ----------------------- | ---------------------------------------- | --------- | --------- |
| `/webhook/whatsapp`     | ✅ Token verification (optional)         | ⚠️ REVIEW | 🟡 MEDIUM |
| `/webhook/instagram`    | ✅ Token verification (optional)         | ⚠️ REVIEW | 🟡 MEDIUM |
| `/api/telegram/webhook` | ✅ Secret token (required if configured) | ✅ SAFE   | 🟢 LOW    |
| `/preview/upload`       | ❌ No verification                       | 🔴 HIGH   | 🔴 HIGH   |

**Detailed Analysis:**

#### `/webhook/whatsapp` & `/webhook/instagram`

- **Verification:** Token verification exists but is **optional** (only if `whatsapp_verify_token` is set)
- **Risk:** In production, default token is rejected, but if not configured, no verification
- **Fix:** Ensure `WHATSAPP_VERIFY_TOKEN` and `INSTAGRAM_VERIFY_TOKEN` are set in production
- **Status:** ✅ Configuration validation exists in `config.py` (rejects default in production)

#### `/api/telegram/webhook`

- **Verification:** Secret token verification (required if `telegram_webhook_secret` is configured)
- **Risk:** If secret not configured, webhook is open
- **Fix:** Ensure `TELEGRAM_WEBHOOK_SECRET` is set in production
- **Status:** ✅ Properly implemented with conditional verification

#### `/preview/upload`

- **Verification:** ❌ None
- **Risk:** 🔴 HIGH - Anyone can upload preview files
- **Impact:** Storage abuse, malicious file uploads
- **Fix:** Add authentication or secret token verification

---

## 🛡️ SECURITY MEASURES ANALYSIS

### Rate Limiting Status

**Current Implementation:**

- ✅ Rate limiting middleware exists (`backend/middleware/rate_limiter.py`)
- ✅ Redis-backed with in-memory fallback
- ✅ Configurable per endpoint pattern

**Coverage:**

- ✅ Most authenticated endpoints have rate limits
- ⚠️ **Public endpoints NOT covered** - Rate limiter skips health/docs but applies to others
- ⚠️ **Webhook endpoints** - No specific rate limits configured

**Missing Rate Limits:**

- `/api/intel/scraper/submit` - Should have strict limit (10/min)
- `/api/intel/staging/approve/` - Should have strict limit (20/min)
- `/api/audio/` - Should have strict limit (30/min)
- `/api/voice/elevenlabs` - Should have moderate limit (60/min)
- `/api/knowledge/visa` - Should have moderate limit (100/min)
- `/preview/` - Should have moderate limit (60/min)
- `/preview/upload` - Should have strict limit (10/min)

**Recommendation:** Add rate limits to `RATE_LIMITS` dict in `rate_limiter.py`:

```python
RATE_LIMITS = {
    # ... existing limits ...
    "/api/intel/scraper/submit": (10, 60),  # 10 per minute
    "/api/intel/staging/approve/": (20, 60),  # 20 per minute
    "/api/audio/": (30, 60),  # 30 per minute
    "/api/voice/elevenlabs": (60, 60),  # 60 per minute
    "/api/knowledge/visa": (100, 60),  # 100 per minute
    "/preview/": (60, 60),  # 60 per minute
    "/preview/upload": (10, 60),  # 10 per minute
}
```

---

### Input Validation Status

**Current Implementation:**

- ✅ Pydantic models for request validation
- ✅ FastAPI automatic validation
- ✅ Custom validators in some endpoints

**Coverage:**

- ✅ Most endpoints have Pydantic models
- ⚠️ **Webhook endpoints** - Basic JSON parsing, no strict schema validation
- ⚠️ **Scraper submit** - Has Pydantic model but no additional validation

**Recommendations:**

- Add strict Pydantic models for all webhook endpoints
- Validate source IPs for webhook endpoints (if possible)
- Add content-length limits for file upload endpoints

---

### Logging/Audit Trail Status

**Current Implementation:**

- ✅ Structured logging configured (`app/setup/logging_config.py`)
- ✅ JSON logging in production
- ✅ Correlation IDs for request tracing

**Coverage:**

- ✅ Most endpoints log requests
- ⚠️ **Public endpoints** - Limited logging (debug level)
- ⚠️ **Webhook endpoints** - Basic logging, no audit trail

**Missing Audit Trail:**

- `/api/intel/scraper/submit` - Should log: source IP, submission content hash, item_id
- `/api/intel/staging/approve/` - Should log: approver (if auth added), item_id, timestamp
- `/api/debug/migrate` - Should log: executor IP, migration details
- `/preview/upload` - Should log: uploader IP, file hash, file size

**Recommendation:** Add audit logging for all state-changing public endpoints:

```python
logger.info(
    "Public endpoint accessed",
    extra={
        "endpoint": request.url.path,
        "method": request.method,
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "correlation_id": correlation_id,
    }
)
```

---

### IP Whitelisting Status

**Current Implementation:**

- ❌ No IP whitelisting middleware
- ⚠️ Only CORS origin whitelisting exists

**Recommendations:**

- Add IP whitelist for `/metrics` endpoints (Prometheus server IPs)
- Add IP whitelist for `/api/intel/scraper/submit` (scraper server IPs)
- Add IP whitelist for `/api/legal/parent-documents` (internal ingestion IPs)

---

## 🔧 RECOMMENDED ACTIONS

### Priority 1: CRITICAL (Immediate)

1. **Remove TEMPORARY endpoints** from `public_endpoints`:

   ```python
   # REMOVE THESE:
   "/api/fix/users-auth",
   "/api/fix/check-user/",
   "/api/fix/test-login",
   ```

2. **Remove `/api/debug/migrate`** from public endpoints or require `ADMIN_API_KEY`

3. **Add authentication to `/api/intel/staging/approve/`** or add secret token verification

4. **Add authentication to `/preview/upload`** or add secret token verification

### Priority 2: HIGH (This Week)

5. **Add rate limiting** to all RISKY endpoints (see Rate Limiting section)

6. **Add secret token verification** to `/api/intel/scraper/submit`:

   ```python
   # In intel.py router
   scraper_secret = request.headers.get("X-Scraper-Secret")
   if scraper_secret != settings.scraper_secret_token:
       raise HTTPException(403, "Invalid scraper secret")
   ```

7. **Add signature verification** to `/api/voice/elevenlabs` webhook

8. **Add IP whitelisting** for `/metrics` endpoints

### Priority 3: MEDIUM (This Month)

9. **Add API key authentication** to `/api/legal/parent-documents`

10. **Add API key authentication** to `/api/audio/` endpoints

11. **Add audit logging** to all state-changing public endpoints

12. **Review and restrict** `/api/integrations/google-drive/system/status` - should require auth

---

## 📝 IMPLEMENTATION CHECKLIST

### Step 1: Remove Dead Code

- [ ] Remove 3 TEMPORARY endpoints from `public_endpoints` list
- [ ] Verify no references exist in codebase
- [ ] Test that removal doesn't break anything

### Step 2: Secure Debug Endpoint

- [ ] Remove `/api/debug/migrate` from public endpoints
- [ ] Add `ADMIN_API_KEY` requirement to debug router
- [ ] Test authentication requirement

### Step 3: Add Rate Limiting

- [ ] Add rate limits to `RATE_LIMITS` dict
- [ ] Test rate limiting works correctly
- [ ] Monitor rate limit hits in production

### Step 4: Add Authentication/Verification

- [ ] Add secret token to `/api/intel/scraper/submit`
- [ ] Add authentication to `/api/intel/staging/approve/`
- [ ] Add authentication to `/preview/upload`
- [ ] Add signature verification to `/api/voice/elevenlabs`
- [ ] Update scraper to include secret token
- [ ] Test all changes

### Step 5: Add Audit Logging

- [ ] Add audit logging to state-changing endpoints
- [ ] Verify logs are captured correctly
- [ ] Set up log aggregation/alerts

### Step 6: Add IP Whitelisting

- [ ] Create IP whitelist middleware
- [ ] Configure whitelist for `/metrics`
- [ ] Configure whitelist for scraper endpoints
- [ ] Test IP restrictions

---

## 🔍 VERIFICATION COMMANDS

### Check for TEMPORARY endpoints in codebase:

```bash
grep -r "api/fix" apps/backend-rag/backend/
```

### Check rate limiting coverage:

```bash
grep -A 5 "RATE_LIMITS" apps/backend-rag/backend/middleware/rate_limiter.py
```

### Check webhook verification:

```bash
grep -A 10 "webhook" apps/backend-rag/backend/app/routers/telegram.py | grep -i "secret\|verify\|token"
```

### Test public endpoint access:

```bash
# Test TEMPORARY endpoint (should 404)
curl https://nuzantara-rag.fly.dev/api/fix/users-auth

# Test debug endpoint (should 401)
curl https://nuzantara-rag.fly.dev/api/debug/migrate

# Test scraper endpoint (should work but log warning)
curl -X POST https://nuzantara-rag.fly.dev/api/intel/scraper/submit \
  -H "Content-Type: application/json" \
  -d '{"title": "test"}'
```

---

## 📚 REFERENCES

- **Hybrid Auth Middleware:** `apps/backend-rag/backend/middleware/hybrid_auth.py`
- **Rate Limiter:** `apps/backend-rag/backend/middleware/rate_limiter.py`
- **Telegram Webhook:** `apps/backend-rag/backend/app/routers/telegram.py:767`
- **Intel Router:** `apps/backend-rag/backend/app/routers/intel.py:301`
- **Config Settings:** `apps/backend-rag/backend/app/core/config.py`

---

**Next Audit Date:** 2026-02-13 (Monthly)

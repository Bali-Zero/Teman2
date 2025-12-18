# 🔐 API Keys & Secrets Configuration

## Overview

This document tracks all API keys and secrets used across the Nuzantara platform. All secrets are now loaded from environment variables with **no hardcoded defaults**.

## 🔑 Production Secrets

### Backend (nuzantara-rag.fly.dev)

**JWT_SECRET_KEY:**
```
07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0=
```
- **Location:** Fly.io secrets (`nuzantara-rag`)
- **Usage:** JWT token signing and validation
- **Validation:** Minimum 32 characters, cannot be default value

**API_KEYS:**
```
DZII3oBeLIFaEKRbeQCxD2IZYTlxaUng6uKTXLydGK9CkwKoQfjsU45t2izjQKvi,OHqJi3m4pMECevSgINt8VpR5V-ueDZ3Oet_WpEChLne6yJ2hXcfJpGLQRuAKXFaK
```
- **Location:** Fly.io secrets (`nuzantara-rag`)
- **Usage:** API key authentication for backend endpoints
- **Format:** Comma-separated list of keys
- **Loaded by:** `apps/backend-rag/backend/app/services/api_key_auth.py`

### Frontend (nuzantara-webapp.fly.dev)

**NUZANTARA_API_KEY:**
```
Rfzo3FWjqPGHuAdV_P3sU6fpusR-16cOH7KYttSnPBLTF-IEntMV3y2HTmpll1wx
```
- **Location:** Fly.io secrets (`nuzantara-webapp`)
- **Usage:** API key for frontend-to-backend communication
- **Used in:**
  - `apps/webapp-next/src/app/api/chat/stream/route.ts`
  - `apps/webapp-next/src/app/api/image/generate/route.ts`
  - `apps/webapp-next/src/lib/api/client.ts`

## 🔧 Automated Testing Secrets

**NUZANTARA_API_KEY:**
```
Rfzo3FWjqPGHuAdV_P3sU6fpusR-16cOH7KYttSnPBLTF-IEntMV3y2HTmpll1wx
```
- **Location:** Testing environment secrets/variables
- **Usage:** E2E tests and frontend workflows
- **Used in:** Automated testing configuration

**Note:** Configure this in your testing environment secrets/variables settings.

## 📋 Codebase Verification

### ✅ Backend Security

- **`apps/backend-rag/backend/app/core/config.py`**
  - `jwt_secret_key`: `Field(...)` - **REQUIRED**, no default
  - `api_keys`: `Field(...)` - **REQUIRED**, no default
  - Validator enforces minimum 32 characters for JWT secret

- **`apps/backend-rag/backend/app/services/api_key_auth.py`**
  - Loads API keys from `settings.api_keys` (environment variable)
  - **No hardcoded keys**

- **`apps/backend-rag/backend/app/main_cloud.py`**
  - `dev-token-bypass` **REMOVED**

### ✅ Frontend Security

- **`apps/webapp-next/src/app/api/chat/stream/route.ts`**
  - `NUZANTARA_API_KEY` required (throws error if missing)

- **`apps/webapp-next/src/app/api/image/generate/route.ts`**
  - `NUZANTARA_API_KEY` required (throws error if missing)

- **`apps/webapp-next/src/lib/api/client.ts`**
  - `createServerClient()`: `NUZANTARA_API_KEY` required
  - `createPublicClient()`: `NUZANTARA_API_KEY` required
  - **No fallback to empty string**

## 🧪 Test Configuration

Test files use appropriate test values:
- `test-api-key`
- `test-key`
- `test-secret-key-for-ci` (JWT for CI)

**No production keys in test files.**

## 🔄 Update Process

When updating secrets:

1. **Fly.io Backend:**
   ```bash
   flyctl secrets set JWT_SECRET_KEY="new-value" --app nuzantara-rag
   flyctl secrets set API_KEYS="key1,key2" --app nuzantara-rag
   ```

2. **Fly.io Frontend:**
   ```bash
   flyctl secrets set NUZANTARA_API_KEY="new-value" --app nuzantara-webapp
   ```

3. **Testing Secrets:**
   - Update via your testing environment's secrets/variables settings

4. **Verify:**
   ```bash
   flyctl secrets list --app nuzantara-rag
   flyctl secrets list --app nuzantara-webapp
   ```

## 🚨 Security Notes

- ✅ All hardcoded credentials removed
- ✅ All secrets loaded from environment variables
- ✅ No default fallback values in production code
- ✅ Validators enforce security requirements
- ✅ Dev bypass tokens removed

## 📝 Last Updated

2025-12-01 - Security patch applied, all secrets migrated to environment variables
































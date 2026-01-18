# Deploying Nuzantara Admin to Fly.io

To make the dashboard "permanently online" and accessible without localhost/proxy, follow these steps to deploy it directly to Fly.io internal network.

## 1. Create the App

Register the application name with Fly.io:

```bash
fly apps create nuzantara-admin
```

## 2. Set Production Secrets

Configure the app to connect directly to your databases via the internal Fly network (no proxy needed).

```bash
# Set secrets for nuzantara-admin
fly secrets set -a nuzantara-admin \
  DATABASE_URL="postgres://backend_rag_v2:2zEjit43IF6gNUV@nuzantara-postgres.internal:5432/nuzantara_rag?sslmode=disable" \
  QDRANT_URL="http://nuzantara-qdrant.internal:6333" \
  QDRANT_API_KEY="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
```

> **Note**: We use `.internal` addresses here. faster and more secure.

## 3. Deploy

Build and release the application to the cloud:

```bash
cd apps/admin-dashboard
fly deploy
```

## 4. Access

Your dashboard will be permanently available at:
**https://nuzantara-admin.fly.dev**

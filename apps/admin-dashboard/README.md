# Nuzantara Admin Dashboard

A standalone Next.js application to inspect and control Nuzantara data.

## Features

- **PostgreSQL**: Browse tables, row counts, and paginated data.
- **Qdrant**: Browse collections, vector counts, and payload inspection.

## Configuration

The application is auto-configured to use:

- **PostgreSQL**: `localhost:15432` (Requires Fly Proxy)
- **Qdrant**: `https://nuzantara-qdrant.fly.dev` (Production)

## ⚠️ Important: Connecting to Database

Since the PostgreSQL database is hosted on Fly.io, you **MUST** open a tunnel before running the dashboard:

```bash
# In a separate terminal run:
fly proxy 15432:5432 -a nuzantara-postgres
```

Once the proxy is running, the dashboard can connect to your live data.

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```
2. Build the project:
   ```bash
   npm run build
   ```
3. Start the server:
   ```bash
   npm run dev
   ```
4. Access at `http://localhost:3000`

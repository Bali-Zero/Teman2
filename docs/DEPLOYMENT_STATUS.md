# Deployment Status

**Last Updated:** 2026-01-18 16:50 UTC

## 🟢 Production Environment

### Backend Services (Fly.io)

| Service        | App Name             | Region            | Status         | URL                                | Version |
| -------------- | -------------------- | ----------------- | -------------- | ---------------------------------- | ------- |
| **Core API**   | `nuzantara-rag`      | `sin` (Singapore) | ✅ **Healthy** | `https://nuzantara-rag.fly.dev`    | v1630   |
| **Vector DB**  | `nuzantara-qdrant`   | `sin` (Singapore) | ✅ **Healthy** | `https://nuzantara-qdrant.fly.dev` | v100    |
| **PostgreSQL** | `nuzantara-postgres` | `sin` (Singapore) | ✅ **Healthy** | Internal (6PN)                     | 15.x    |

### Frontend (Vercel)

| App       | Branch | Status          | URL                        |
| --------- | ------ | --------------- | -------------------------- |
| **Mouth** | `main` | ✅ **Deployed** | `https://www.balizero.com` |

---

## 🏗️ Infrastructure Details

### Connectivity

- **Frontend -> Backend:** HTTPS (Public Internet) secured via JWT/Cookies.
- **Backend -> Qdrant:** Internal WireGuard Network (6PN). Zero-latency.
- **Backend -> Postgres:** Internal WireGuard Network (6PN).

### Security

- **API Keys:** Stored in Fly.io Secrets (Backend) and Vercel Env Vars (Frontend).
- **CORS:** Backend restricts access to `*.balizero.com` and `nuzantara-mouth.vercel.app`.
- **LLM Access:** **Server-Side Only**. Frontend never accesses LLM APIs directly.

### Configuration

- **Backend Timeout:** 600s (10 minutes) for long-running RAG tasks.
- **Allowed Origins:**
  - `https://balizero.com`
  - `https://www.balizero.com`
  - `https://zantara.balizero.com`
  - `https://nuzantara-mouth.vercel.app`

## 🔄 Recent Deployments

- **2026-01-18:** Backend stabilization deploy. Added Omnichannel support, fixed startup crashes, increased timeouts.

# ZANTARA MEDIA

**Autonomous Editorial Production System for Bali Zero**

A satellite application in the NUZANTARA ecosystem that transforms intelligence signals into multi-platform content through AI-powered generation and human-in-the-loop review.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZANTARA MEDIA ORGANISM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INTEL SCRAPING (630+ sources)                                  │
│         ↓                                                       │
│  ┌─────────────────┐                                           │
│  │ Intel Processor │ → Prioritize → Route                       │
│  └─────────────────┘                                           │
│         ↓                                                       │
│  ┌─────────────────┐                                           │
│  │ Content Pipeline│ → AI Draft → Human Review → Publish        │
│  └─────────────────┘                                           │
│         ↓                                                       │
│  ┌─────────────────┐                                           │
│  │  Distributor    │ → Twitter/LinkedIn/Instagram/TikTok/etc    │
│  └─────────────────┘                                           │
│         ↓                                                       │
│  NUZANTARA (Qdrant indexing, CRM sync, Analytics)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Dashboard (Next.js 16)
- React 19.2 with TypeScript
- Tailwind CSS v4 with NUZANTARA theme
- shadcn/ui components (new-york style)
- Zustand for state management

### Backend (Python FastAPI)
- Async API with Pydantic models
- Multi-tier AI generation (Llama → Gemini → Claude)
- Integration with NUZANTARA and INTEL SCRAPING
- APScheduler for background jobs

## Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- pnpm (recommended) or npm

### Dashboard Setup

```bash
cd apps/zantara-media/dashboard

# Install dependencies
pnpm install

# Create environment file
cp .env.example .env.local

# Run development server
pnpm dev
```

Dashboard runs at http://localhost:3001

### Backend Setup

```bash
cd apps/zantara-media/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env

# Run development server
uvicorn app.main:app --reload --port 8001
```

Backend runs at http://localhost:8001

API docs at http://localhost:8001/docs

## Environment Variables

### Dashboard (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### Backend (.env)
```
# Core
DEBUG=true
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost:5432/zantara_media

# NUZANTARA Integration
NUZANTARA_API_URL=http://localhost:8000
NUZANTARA_API_KEY=your-nuzantara-key

# INTEL SCRAPING Integration
INTEL_API_URL=http://localhost:8002
INTEL_API_KEY=your-intel-key

# AI Models
OPENROUTER_API_KEY=your-openrouter-key
GOOGLE_API_KEY=your-google-key

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
```

## API Endpoints

### Dashboard
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dashboard/platforms/status` - Platform connection status

### Content
- `GET /api/content` - List content with filters
- `POST /api/content` - Create new content
- `POST /api/content/{id}/publish` - Publish content
- `POST /api/content/{id}/schedule` - Schedule for future

### Intel
- `GET /api/intel` - List intel signals
- `POST /api/intel/{id}/process` - Process signal (create content/dismiss)
- `POST /api/intel/refresh` - Trigger intel refresh

### Distribution
- `GET /api/distribution` - List distributions
- `POST /api/distribution` - Create distribution
- `POST /api/distribution/{id}/publish` - Publish to platform

### AI Writer
- `POST /api/ai/generate` - Generate content with AI
- `GET /api/ai/models` - List available AI models
- `POST /api/ai/estimate-cost` - Estimate generation cost

## Content Workflow

```
Draft → Review → Approved → Scheduled → Published → Archived
```

1. **Draft**: Initial content (AI-generated or manual)
2. **Review**: Pending human approval
3. **Approved**: Ready for publication
4. **Scheduled**: Queued for future publication
5. **Published**: Live on platform
6. **Archived**: Removed from active use

## AI Model Fallback

Content generation uses cost-optimized 3-tier fallback:

1. **Llama 4 Scout** (cheapest) - via OpenRouter
2. **Gemini 2.0 Flash** - via Google AI
3. **Claude Haiku** (fallback) - via OpenRouter

## Integration Points

### NUZANTARA
- Qdrant vector indexing of published content
- CRM lead sync from content engagement
- Auth token validation
- Analytics reporting

### INTEL SCRAPING
- Fetch signals from 630+ Indonesian sources
- Trigger scraping jobs
- Signal prioritization and routing

## Project Structure

```
apps/zantara-media/
├── dashboard/              # Next.js frontend
│   ├── src/
│   │   ├── app/           # Pages and routes
│   │   ├── components/    # UI and layout components
│   │   ├── lib/           # Utilities
│   │   └── types/         # TypeScript types
│   └── package.json
│
└── backend/               # Python FastAPI backend
    ├── app/
    │   ├── routers/       # API endpoints
    │   ├── services/      # Business logic
    │   ├── integrations/  # External clients
    │   ├── models.py      # Pydantic models
    │   └── config.py      # Settings
    └── requirements.txt
```

## Development

### Running Tests
```bash
# Backend
cd backend
pytest

# Dashboard
cd dashboard
pnpm test
```

### Type Checking
```bash
# Dashboard
pnpm typecheck

# Backend
mypy app
```

## Deployment

Designed for Fly.io deployment alongside NUZANTARA:

```bash
# Dashboard
fly deploy --config fly.dashboard.toml

# Backend
fly deploy --config fly.backend.toml
```

## License

Proprietary - Bali Zero 2025

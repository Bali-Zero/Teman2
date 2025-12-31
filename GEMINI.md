# Nuzantara Project Context

## Project Overview

Nuzantara is a comprehensive, production-ready AI platform designed as an **Intelligent Business Operating System**. It leverages advanced Agentic RAG (Retrieval-Augmented Generation) to provide intelligent business assistance, CRM capabilities, and multi-channel communication.

The project is structured as a **Monorepo** managed with `npm workspaces` and Docker, integrating a Python FastAPI backend with a Next.js frontend.

### Core Technologies

*   **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4.
*   **Backend:** Python 3.11+, FastAPI, Uvicorn.
*   **Database:**
    *   **PostgreSQL:** Relational data (CRM, Auth, Memory).
    *   **Qdrant:** Vector database for RAG (53,000+ documents).
    *   **Redis:** Caching and queue management.
*   **AI/LLM:**
    *   **Orchestration:** Agentic RAG with ReAct Pattern.
    *   **Models:** Google Gemini (primary), OpenAI (embeddings), OpenRouter (fallback).
    *   **Reranking:** ZeroEntropy (zerank-2).
*   **Infrastructure:** Docker, Fly.io (deployment).

## Architecture

The system operates on a **4-Dimensional System Map**: Space (Structure), Time (Flow), Logic (Relationships), and Scale (Metrics).

### Directory Structure

*   `apps/backend-rag/`: **Core Intelligence Engine**. Python FastAPI backend handling RAG, CRM, and business logic.
*   `apps/mouth/`: **Primary Interface**. Next.js web application for user interaction.
*   `apps/bali-intel-scraper/`: Satellite service for intelligence gathering (630+ sources).
*   `apps/zantara-media/`: Satellite service for editorial production.
*   `apps/evaluator/`: RAG evaluation harness.
*   `docs/`: Comprehensive project documentation.
*   `scripts/`: Utility scripts for deployment, testing, and data management.

## Building and Running

### Prerequisites

*   Node.js 20+
*   Python 3.11+
*   Docker & Docker Compose
*   Fly.io CLI (`flyctl`)

### Local Development

The project emphasizes a **local development workflow** using Docker Compose.

1.  **Start the Stack:**
    ```bash
    docker compose up --build
    ```
    This starts the Backend (`localhost:8080`), Qdrant (`localhost:6333`), and Observability stack (Grafana, Jaeger, Prometheus).

2.  **Frontend Development:**
    Run the frontend separately for interactive development:
    ```bash
    cd apps/mouth
    npm run dev
    ```
    Access at `http://localhost:3000`.

### Key Commands

*   **Install Dependencies:**
    *   Root/Frontend: `npm install`
    *   Backend: `pip install -r apps/backend-rag/requirements.txt`
*   **Run Tests:**
    *   Backend: `pytest` (in `apps/backend-rag`)
    *   Frontend: `npm test` (in `apps/mouth`)
*   **Quality Control:**
    *   Run `./sentinel` in the root directory to verify integrity (linting, tests) before review.

## Development Conventions

### General
*   **Monorepo:** Uses `npm workspaces` for managing multiple packages.
*   **Documentation:** Extensive documentation in `docs/`. Follow `AI_ONBOARDING.md` and `AI_HANDOVER_PROTOCOL.md`.
*   **No CI/CD:** Deployment is strictly **manual** and **local** via `flyctl` to ensure control.

### Backend (Python/FastAPI)
*   **Type Hints:** Mandatory for all functions.
*   **Async:** Use `async/await` for I/O operations.
*   **Style:** Follows PEP 8.
*   **Testing:** High coverage requirement (>90%). Uses `pytest`.

### Frontend (Next.js/React)
*   **TypeScript:** Strict typing (no `any`).
*   **Components:** Functional components with Hooks.
*   **Styling:** Tailwind CSS.

## Key Documentation Files

*   `docs/AI_ONBOARDING.md`: **START HERE**. Operational standards and rules.
*   `docs/ai/AI_HANDOVER_PROTOCOL.md`: Golden rules and tech stack summary for AI agents.
*   `docs/LIVING_ARCHITECTURE.md`: Auto-generated API and module reference.
*   `docs/SYSTEM_MAP_4D.md`: High-level system architecture and metrics.

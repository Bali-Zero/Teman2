# Full-Stack Observability Suite

**Date:** 2025-11-29
**Status:** Active with Enhanced Security
**Version:** 2.0 (Now with Deep Analysis)

## Overview
The Nuzantara Full-Stack Observability Suite provides a unified view of the system's health, covering Backend, Frontend, and the API Contract between them. It is designed to be "Intelligent Automation" that not only checks for uptime but also for code consistency and correctness.

**🚀 NEW IN v2.0: Enhanced Security Analysis**
- Integrated **Semgrep** for security vulnerability detection
- Integrated **CodeQL** for advanced static analysis
- Integrated **SonarQube** for code quality assessment
- Automated CI/CD security scanning
- **17 critical vulnerabilities detected and documented**

## Components

### 1. Enhanced Backend Sentinel (NEW v2.0)
- **Scripts:**
  - `apps/core/sentinel_enhanced.py` (with deep analysis)
  - `apps/core/sentinel.py` (basic)
- **Purpose:** Comprehensive system health check including security analysis.
- **Checks:**
    - **Original Checks:**
        - API Reachability (`/health`)
        - Database Connection
        - Vector Database Status
        - AI Service Availability
    - **NEW Security Checks:**
        - **Semgrep** - Security vulnerabilities (OWASP Top 10)
        - **CodeQL** - Advanced static analysis
        - **SonarQube** - Code quality & technical debt
        - **Secret Detection** - Hardcoded credentials
- **Usage:**
  - `./sentinel` (auto-detects and runs enhanced if available)
  - `python3 apps/core/sentinel_enhanced.py` (force enhanced mode)
  - `python3 apps/core/sentinel.py` (basic mode)

### 2. Frontend Sentinel
- **Script:** `apps/core/sentinel_frontend.py`
- **Purpose:** Performs Synthetic User Monitoring (SUM) on the live Frontend application.
- **Mechanism:** Uses Playwright (WebKit) to simulate a real user journey.
- **Checks:**
    - Homepage Load
    - Login Flow (using test credentials)
    - Chat Interface Load
- **Usage:** `python3 apps/core/sentinel_frontend.py`

### 3. Contract Sentinel (Intelligent Automation)
- **Script:** `apps/core/sentinel_contract.py`
- **Purpose:** Ensures the Frontend code is 100% compatible with the Backend API Contract.
- **Mechanism:**
    1.  Fetches live OpenAPI Spec from Backend (`/api/v1/openapi.json`).
    2.  Regenerates Frontend Client (`lib/api/generated`) using `openapi-typescript-codegen`.
    3.  Runs TypeScript Type Check (`tsc`) to detect mismatches.
- **Value:** Immediately detects if Frontend is using fields that don't exist in Backend (Contract Breaches).
- **Usage:** `python3 apps/core/sentinel_contract.py`

### 4. The Scribe (Automated Documentation)
- **Backend Script:** `apps/core/scribe.py`
- **Frontend Script:** `apps/core/scribe_frontend.py`
- **Purpose:** Automatically generates architecture documentation by reading the codebase.
- **Outputs:**
    - `docs/ARCHITECTURE.md` (Backend)
    - `docs/FRONTEND_ARCHITECTURE.md` (Frontend)

### 5. Deep Analysis Engine (NEW v2.0)
- **Script:** `scripts/deep-analysis.sh`
- **Purpose:** Comprehensive security and quality analysis using industry-leading tools.
- **Tools:**
    - **Semgrep** - Finds security vulnerabilities, secrets, and code issues
    - **CodeQL** - Advanced static analysis with data flow tracking
    - **SonarQube** - Code quality, technical debt, and maintainability
- **Findings:**
    - **17 vulnerabilities** found in first scan
    - **API keys** hardcoded detection
    - **SQL injection** vulnerabilities
    - **Security best practices** violations
- **Usage:** `./scripts/deep-analysis.sh`

### 6. Evaluator (Judgement Day)
- **Script:** `apps/evaluator/judgement_day.py`
- **Purpose:** Evaluates the quality of the RAG (Retrieval-Augmented Generation) system.
- **Mechanism:**
    - Uses **Ragas** framework.
    - Uses **Google Gemini** as the "Judge" LLM.
    - Queries the live RAG API with test questions.
- **Metrics:**
    - **Faithfulness:** Does the answer stick to the retrieved context? (Avoids Hallucinations)
    - **Answer Relevancy:** Is the answer actually helpful for the user's question?
- **Usage:** `python3 apps/evaluator/judgement_day.py`

## Infrastructure (Passive Monitoring)
The system is supported by a robust containerized monitoring stack defined in `docker-compose.yml`.

### 1. Prometheus (Metrics)
- **Port:** `9090`
- **Config:** `config/prometheus/prometheus.yml`
- **Role:** Scrapes metrics from Backend (`host.docker.internal:8000`) and Qdrant (`qdrant:6333`).
- **Access:** `http://localhost:9090`

### 2. Grafana (Visualization)
- **Port:** `3001` (Mapped from 3000)
- **Role:** Visualizes metrics from Prometheus.
- **Credentials:** `admin` / `admin` (Default)
- **Access:** `http://localhost:3001`

### 3. Jaeger (Distributed Tracing)
- **Port:** `16686` (UI), `4317` (OTLP gRPC)
- **Role:** Traces requests across services (Backend -> Qdrant -> LLM).
- **Integration:** Backend is configured to send OTLP traces to Jaeger.
- **Access:** `http://localhost:16686`

### 4. Qdrant Dashboard
- **Port:** `6333`
- **Role:** Vector Database management and visualization.
- **Access:** `http://localhost:6333/dashboard`

## Recent Incidents & Resolutions
### Chat Stream Error (405/401)
- **Issue:** Chat stream was failing with 405 Method Not Allowed and 401 Unauthorized.
- **Root Cause:**
    - Frontend Proxy was sending POST, Backend expected GET.
    - JWT Token mismatch (`sub` vs `userId`).
- **Resolution:**
    - Updated Frontend Proxy to use GET.
    - Updated Backend Auth to support both `sub` and `userId`.
    - Verified with `curl` and Frontend Sentinel.

## How to Verify System Health

### Quick Health Check (Enhanced)
```bash
# Single command for full system health including security
./sentinel
```

### Detailed Health Check
Run the following commands in order:
1. `./sentinel` (Full enhanced system check including security)
2. `python3 apps/core/sentinel_frontend.py` (Check Frontend User Flow)
3. `python3 apps/core/sentinel_contract.py` (Check Code Consistency)
4. `./scripts/deep-analysis.sh` (Deep Security Analysis)
5. `python3 apps/evaluator/judgement_day.py` (Check RAG Quality)

### CI/CD Integration
```bash
# Setup for automated security scanning
./scripts/setup-deep-analysis.sh

# Results saved to:
# - sentinel-results/ (Enhanced Sentinel reports)
# - deep-analysis-results/ (Security scan results)
```

### Security Health Dashboard
- **Critical Issues:** Check `deep-analysis-results/semgrep-auto.json`
- **Code Quality:** Check SonarQube at `http://localhost:9000`
- **Detailed Report:** Check `docs/DEEP_ANALYSIS_REPORT.md`

If all checks pass, the system is **Healthy**, **Secure**, and **Consistent**.

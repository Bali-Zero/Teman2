# Nuzantara Platform - Complete Workflow Guide

## 📋 Overview

This guide explains the complete development workflow from local development to production deployment, including all tools, configurations, and best practices.

## 🏗️ System Architecture

### Repository Structure
```
nuzantara/
├── apps/
│   ├── backend-rag/          # FastAPI backend service
│   ├── webapp-next/          # Next.js frontend application
│   ├── core/                 # Sentinel & monitoring tools
│   ├── evaluator/            # RAG quality testing
│   └── scraper/              # Web scraping utilities
├── docs/                     # Documentation
├── scripts/                  # Automation scripts
├── [testing-config]/         # Testing and deployment configuration
└── docker-compose.yml        # Local development stack
```

### Production Infrastructure
```
Production Stack:
├── Backend API:   https://nuzantara-rag.fly.dev
├── Frontend App:  https://nuzantara-webapp.fly.dev
├── Database:      Qdrant Vector DB
├── Monitoring:    Grafana/Prometheus
└── Observability: Custom Sentinel System
```

## 🔧 Local Development Setup

### Prerequisites
```bash
# Required tools
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Fly.io CLI (flyctl)
- Git
```

### Environment Setup

#### 1. Backend Setup
```bash
cd apps/backend-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment variables (.env file)
cp .env.example .env
# Edit .env with your configuration
```

#### 3. Frontend Setup
```bash
cd apps/webapp-next

# Install dependencies
npm install

# Environment variables (.env.local file)
cp .env.example .env.local
# Edit with your API URLs and keys
```

#### 4. Fly.io Authentication
```bash
# Authenticate with Fly.io
flyctl auth login

# Verify authentication
flyctl auth whoami
```

### Local Development Commands

#### Backend Development
```bash
cd apps/backend-rag

# Run local development server
uvicorn backend.main_cloud:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/ -v --cov=backend

# Run linting
ruff check . --fix

# Run health check
curl http://localhost:8000/health
```

#### Frontend Development
```bash
cd apps/webapp-next

# Run development server
npm run dev

# Run type checking
npm run typecheck

# Run linting
npm run lint

# Build for production
npm run build
```

#### Database Setup (Optional Local)
```bash
# Using Docker Compose for local services
docker-compose up -d qdrant postgres

# Run migrations
python -m db.migrate apply --number 10
```

## 🔄 Git Workflow

### Branch Strategy
```
main                    # Production-ready code
├── develop            # Integration branch (optional)
└── feature/*          # Feature development branches
```

### Development Workflow

#### 1. Create Feature Branch
```bash
# Always work from latest main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/user-authentication
```

#### 2. Development Process
```bash
# Regular commits during development
git add .
git commit -m "feat: Add user login functionality"

# Push for backup/collaboration
git push origin feature/user-authentication
```

#### 3. Pre-Commit Quality Checks
The system automatically runs pre-commit hooks:
```bash
# These run automatically on git commit
- ruff linting (Python code)
- prettier formatting
- TypeScript checking (frontend)
```

#### 4. Creating Pull Request
```bash
# Push feature branch
git push origin feature/user-authentication

# Create Pull/Merge Request
# - Title: Clear, concise description
# - Description: Detailed explanation of changes
# - Link to issue if applicable
```

### Commit Message Convention
```bash
# Format: <type>(<scope>): <description>
feat: Add new feature
fix: Bug fix
docs: Documentation update
style: Code formatting
refactor: Code refactoring
test: Add/update tests
chore: Build process/dependency update

# Examples:
feat(auth): Add PIN-based authentication
fix(api): Resolve memory leak in chat service
docs(readme): Update setup instructions
```

## 🧪 Testing Strategy

### Backend Testing
```bash
cd apps/backend-rag

# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/unit/test_identity_service.py -v

# Run with coverage
python -m pytest tests/ --cov=backend --cov-report=html

# Run tests by marker
python -m pytest tests/ -m "unit"
python -m pytest tests/ -m "integration"
```

### Frontend Testing
```bash
cd apps/webapp-next

# Run type checking
npm run typecheck

# Run linting
npm run lint

# Fix linting automatically
npm run lint:fix

# Run CI tests (combined)
npm run test:ci
```

### System Integration Testing
```bash
# Run Sentinel (system health checks)
python apps/core/sentinel.py
python apps/core/sentinel_contract.py
python apps/core/sentinel_frontend.py

# Run RAG quality evaluator
export GOOGLE_API_KEY=your_api_key
python apps/evaluator/judgement_day.py
```

## 🚀 Deployment Process

### Automated Deployment (Main Branch)

#### What Happens on Push to Main
```bash
# This flow triggers automatically when:
git push origin main
```

**CI/CD Pipeline Execution:**
1. **Backend CI Pipeline**
   - Code checkout
   - Python environment setup
   - Dependency installation
   - Ruff linting
   - pytest execution with coverage
   - Upload results to Codecov

2. **Frontend CI Pipeline**
   - Node.js environment setup
   - Dependency installation
   - ESLint checking
   - TypeScript validation
   - Production build
   - Bundle analysis

3. **Security Scanning**
   - Trivy vulnerability scanning
   - Safety package security check
   - Bandit code security analysis

4. **Quality Gate Validation**
   - All CI checks must pass
   - Security scans must be clean
   - Tests must achieve minimum coverage

5. **Production Deployment**
   - Backend deployment to Fly.io
   - Frontend deployment to Fly.io
   - Health check validation
   - Rollback on failure

#### Deployment Status Monitoring
```bash
# Check deployment status
# View logs from your testing/deployment platform

# View logs
- Check workflow run status
- Expand job sections
- View detailed logs
```

### Manual Deployments

#### Manual Backend Deploy
1. Go to your testing/deployment platform
2. Select "Backend Deployment" workflow
3. Choose options:
   - Environment: production/staging
   - Force deploy: bypass tests if needed
4. Trigger workflow

#### Manual Frontend Deploy
1. Go to your testing/deployment platform
2. Select "Frontend Deployment" workflow
3. Choose options:
   - Environment: production/staging
   - Force build: bypass linting if needed
4. Trigger workflow

### Local Manual Deploy

#### Backend Deploy
```bash
cd apps/backend-rag

# Deploy to production
fly deploy

# Deploy with specific configuration
fly deploy --config fly.toml

# Deploy to staging (if configured)
fly deploy --app nuzantara-rag-staging
```

#### Frontend Deploy
```bash
cd apps/webapp-next

# Deploy to production
fly deploy

# Monitor deployment
flyctl logs --app nuzantara-webapp
```

## 📊 Production Monitoring

### Health Monitoring
```bash
# Backend health
curl https://nuzantara-rag.fly.dev/health

# Expected response:
{
  "status": "healthy",
  "version": "v100-qdrant",
  "database": {
    "status": "connected",
    "total_documents": 25415
  },
  "embeddings": {
    "status": "operational",
    "provider": "openai"
  }
}

# Frontend health
curl -I https://nuzantara-webapp.fly.dev

# Expected: HTTP/1.1 200 OK
```

### Fly.io Monitoring
```bash
# View application logs
flyctl logs --app nuzantara-rag
flyctl logs --app nuzantara-webapp

# View application status
flyctl status --app nuzantara-rag
flyctl status --app nuzantara-webapp

# Open application in browser
flyctl open --app nuzantara-rag
flyctl open --app nuzantara-webapp

# SSH into application
flyctl ssh console --app nuzantara-rag
```

### Scheduled Health Checks
Automated health monitoring runs every 30 minutes:
- Checks backend API health
- Verifies frontend accessibility
- Tests API connectivity
- Generates health reports
- Creates alerts for failures

## 🔧 Troubleshooting

### Common Issues & Solutions

#### 1. Deployment Failures

**Backend Deploy Failed:**
```bash
# Check logs
flyctl logs --app nuzantara-rag --recent

# Check machine status
flyctl status --app nuzantara-rag

# Common fixes:
- Ensure .env variables are set on Fly.io
- Check for syntax errors in Python code
- Verify requirements.txt is valid
- Check Fly.io region availability
```

**Frontend Deploy Failed:**
```bash
# Check build logs
flyctl logs --app nuzantara-webapp --recent

# Common fixes:
- Check package.json syntax
- Verify NEXT_PUBLIC_* environment variables
- Ensure build completes locally
- Check for memory issues during build
```

#### 2. CI/CD Pipeline Failures

**Backend Tests Failed:**
```bash
# Run tests locally
cd apps/backend-rag
python -m pytest tests/ -v

# Fix linting issues
ruff check . --fix

# Check for import errors
python -c "import backend.main_cloud"
```

**Frontend Build Failed:**
```bash
# Run build locally
cd apps/webapp-next
npm run build

# Fix TypeScript errors
npm run typecheck

# Fix linting errors
npm run lint:fix
```

#### 3. Environment Issues

**Missing Environment Variables:**
```bash
# Set Fly.io secrets
flyctl secrets set DATABASE_URL=your_url --app nuzantara-rag
flyctl secrets set OPENAI_API_KEY=your_key --app nuzantara-rag

# Check current secrets
flyctl secrets list --app nuzantara-rag
```

**Database Connection Issues:**
```bash
# Check database connectivity
curl https://nuzantara-rag.fly.dev/health | jq .database

# Restart database if needed
flyctl restart --app nuzantara-qdrant
```

### Emergency Procedures

#### Rollback Deployment
```bash
# View deployment history
flyctl deployments list --app nuzantara-rag

# Rollback to previous deployment
flyctl rollback --app nuzantara-rag --version <previous_version_id>
```

#### Emergency Debug Access
```bash
# SSH into production machine
flyctl ssh console --app nuzantara-rag

# View application logs
tail -f /app/logs/app.log

# Check system resources
df -h
free -m
top
```

#### Service Restart
```bash
# Restart application
flyctl restart --app nuzantara-rag
flyctl restart --app nuzantara-webapp

# Scale up if needed
flyctl scale count 2 --app nuzantara-rag
```

## 📋 Configuration Files

### Backend Configuration

#### apps/backend-rag/fly.toml
```toml
app = 'nuzantara-rag'
primary_region = 'sin'

[build]
  dockerfile = 'Dockerfile'

[deploy]
  strategy = 'rolling'

[env]
  EMBEDDING_PROVIDER = 'openai'
  LOG_LEVEL = 'DEBUG'
  PORT = '8080'

[[mounts]]
  source = 'nuzantara_rag_data'
  destination = '/data'
```

#### apps/backend-rag/.env (Local)
```env
# Database
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://user:pass@localhost:5432/nuzantara

# External APIs
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
HF_API_KEY=your_huggingface_key

# Application
DEBUG=true
LOG_LEVEL=DEBUG
```

### Frontend Configuration

#### apps/webapp-next/next.config.js
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    domains: ['example.com'],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
}

module.exports = nextConfig
```

#### apps/webapp-next/.env.local (Local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 📚 Development Best Practices

### Code Quality
- Run tests locally before pushing
- Follow commit message conventions
- Use meaningful variable names
- Add type hints (Python/TypeScript)
- Keep functions small and focused

### Security
- Never commit secrets or API keys
- Use environment variables for configuration
- Regularly update dependencies
- Run security scans before deployment
- Review dependency vulnerabilities

### Performance
- Monitor application metrics
- Optimize database queries
- Use caching strategies
- Optimize bundle sizes (frontend)
- Monitor memory usage

### Collaboration
- Write clear PR descriptions
- Review code carefully
- Add tests for new features
- Update documentation
- Communicate breaking changes

## 🔍 Debugging Tools

### Local Debugging

#### Backend Debugging
```bash
# Enable debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with debugger
python -m pdb backend/main_cloud.py

# View detailed logs
uvicorn backend.main_cloud:app --log-level debug
```

#### Frontend Debugging
```bash
# Run with debugging
npm run dev -- --debug

# Chrome DevTools:
# - Network tab: API calls
# - Console tab: JavaScript errors
# - React DevTools: Component state
```

### Production Debugging

#### Remote Debugging
```bash
# SSH into production
flyctl ssh console --app nuzantara-rag

# Check processes
ps aux | grep python

# Check memory usage
free -h

# Check disk usage
df -h

# View application logs
journalctl -u flyctl
```

## 📈 Performance Monitoring

### Metrics to Monitor
1. **Application Performance**
   - Response times
   - Error rates
   - Throughput
   - Memory usage

2. **Infrastructure Performance**
   - CPU utilization
   - Memory consumption
   - Network I/O
   - Database performance

3. **User Experience**
   - Page load times
   - API response times
   - Error rates
   - User engagement

### Monitoring Tools
```bash
# Fly.io metrics
flyctl metrics --app nuzantara-rag

# Application metrics
curl https://nuzantara-rag.fly.dev/metrics

# Health checks
python apps/core/sentinel.py
```

## 🎯 Quick Reference Commands

### Development Commands
```bash
# Backend
cd apps/backend-rag && python -m pytest tests/ && ruff check .
cd apps/backend-rag && uvicorn backend.main_cloud:app --reload

# Frontend
cd apps/webapp-next && npm run dev
cd apps/webapp-next && npm run build

# System Tests
python apps/core/sentinel.py
python apps/evaluator/judgement_day.py
```

### Deployment Commands
```bash
# Automated
git push origin main  # Triggers full CI/CD

# Manual
cd apps/backend-rag && fly deploy
cd apps/webapp-next && fly deploy

# Monitoring
flyctl status --app nuzantara-rag
flyctl logs --app nuzantara-rag --recent
```

### Emergency Commands
```bash
# Rollback
flyctl rollback --app nuzantara-rag

# Restart
flyctl restart --app nuzantara-rag

# Scale
flyctl scale count 2 --app nuzantara-rag

# Debug
flyctl ssh console --app nuzantara-rag
```

## 🚀 Deployment Checklist

### Pre-Deployment Checklist
- [ ] All tests passing locally
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Environment variables configured
- [ ] Security scans passing
- [ ] Performance tests passing
- [ ] Backup plan ready

### Post-Deployment Checklist
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Rollback plan tested
- [ ] Team notified
- [ ] Documentation updated
- [ ] Performance verified
- [ ] User testing complete

---

## 🎉 Success Metrics

Your deployment is successful when:
- ✅ All CI/CD checks pass
- ✅ Health endpoints return 200 OK
- ✅ User flows work end-to-end
- ✅ Monitoring shows normal metrics
- ✅ Error rates are within limits
- ✅ Performance meets requirements

With this comprehensive workflow, you have a robust, automated system from local development to production deployment with full monitoring and rollback capabilities! 🚀

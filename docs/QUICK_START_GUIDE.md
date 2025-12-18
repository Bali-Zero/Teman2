# Nuzantara Platform - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites
```bash
# Required tools
- Python 3.11+
- Node.js 18+
- Fly.io CLI (flyctl)
- Git
```

### 1. Backend Setup
```bash
cd apps/backend-rag
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your keys
```

### 3. Frontend Setup
```bash
cd apps/mouth
npm install
cp .env.example .env.local  # Edit with your API URLs
```

### 4. Run Locally
```bash
# Backend (Terminal 1)
cd apps/backend-rag
uvicorn backend.app.main_cloud:app --reload --host 0.0.0.0 --port 8000

# Frontend (Terminal 2)
cd apps/mouth
npm run dev

# Health Check
curl http://localhost:8000/health
```

## 🔑 Essential Commands

### Development
```bash
# Backend Tests
cd apps/backend-rag && python -m pytest tests/ -v

# Frontend Build
cd apps/mouth && npm run build

# System Health
python apps/core/sentinel.py
```

### Deployment
```bash
# Automatic (triggers full CI/CD)
git add . && git commit -m "feat: Update" && git push origin main

# Manual Deploy
cd apps/backend-rag && fly deploy
cd apps/mouth && fly deploy
```

### Monitoring
```bash
# Production Health
curl https://nuzantara-rag.fly.dev/health
curl -I https://nuzantara-webapp.fly.dev

# Production Logs
flyctl logs --app nuzantara-rag --recent
flyctl status --app nuzantara-rag
```

## ⚡ Production URLs

- **Backend API**: https://nuzantara-rag.fly.dev
- **Frontend App**: https://nuzantara-webapp.fly.dev
- **API Docs**: https://nuzantara-rag.fly.dev/docs
- **Health Check**: https://nuzantara-rag.fly.dev/health

## 🎯 Git Workflow

```bash
# Feature Development
git checkout -b feature/your-feature
# ... make changes ...
git add .
git commit -m "feat: Add your feature"
git push origin feature/your-feature
# Create Pull/Merge Request

# Production Deploy
git checkout main
git pull origin main
git merge feature/your-feature
git push origin main  # ✅ Triggers auto-deploy!
```

## 📱 Important Files

```
📁 apps/backend-rag/         # FastAPI backend
  📄 .env                    # Environment variables
  📄 fly.toml                # Fly.io deployment config
  📄 requirements.txt        # Python dependencies

📁 apps/mouth/               # Next.js frontend
  📄 .env.local              # Frontend environment variables
  📄 next.config.ts          # Next.js configuration
  📄 package.json            # Node.js dependencies

📁 apps/core/                # System tools
  📄 sentinel.py             # Health monitoring
  📄 evaluator/              # Quality testing

📁 [testing-config]/         # Testing and deployment configuration
```

## 🚨 Common Issues & Fixes

### Backend Won't Start
```bash
# Check environment variables
cd apps/backend-rag && cat .env

# Check Python path
python -c "import backend.main_cloud"

# Check port 8000 is free
lsof -i :8000
```

### Frontend Build Fails
```bash
# Clear Next.js cache
cd apps/mouth && rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Check TypeScript
npm run typecheck
```

### Deploy Fails
```bash
# Check Fly.io auth
flyctl auth whoami

# Check Fly.io status
flyctl status --app nuzantara-rag

# Check logs
flyctl logs --app nuzantara-rag --recent
```

## 📊 System Status

### Local Development
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### Production
- **Backend**: ✅ Running (25,415 documents indexed)
- **Frontend**: ✅ Running
- **Database**: ✅ Qdrant Vector DB
- **Monitoring**: ✅ Sentinel System Active

### Health Check Results
```json
{
  "status": "healthy",
  "database": { "status": "connected", "total_documents": 25415 },
  "embeddings": { "status": "operational", "provider": "openai" }
}
```

## 🔧 Environment Variables

### Backend (.env)
```env
# Required
QDRANT_URL=http://localhost:6333
OPENAI_API_KEY=your_openai_key

# Optional
GOOGLE_API_KEY=your_google_key
HF_API_KEY=your_huggingface_key
LOG_LEVEL=INFO
```

### Frontend (.env.local)
```env
# Local Development
NEXT_PUBLIC_API_URL=http://localhost:8000

# Production
# NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
```

## 🎯 Quick Testing

### Test API Connection
```bash
# Test Backend Health
curl http://localhost:8000/health

# Test API Authentication
curl -X POST http://localhost:8000/api/auth/team/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","pin":"000000"}'
```

### Test Frontend
1. Open browser to http://localhost:3000
2. Try login with email/PIN
3. Test chat functionality
4. Verify API connectivity

## 📞 Get Help

### Documentation
- **Complete Workflow**: [docs/COMPLETE_WORKFLOW_GUIDE.md](COMPLETE_WORKFLOW_GUIDE.md)
- **Testing & Deployment**: See testing configuration documentation
- **Architecture**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)

### Commands for Help
```bash
# Backend Help
cd apps/backend-rag && python -m pytest --help

# Frontend Help
cd apps/mouth && npm help

# Fly.io Help
flyctl --help

# Git Help
git help
```

### Emergency Contacts
- **Issues**: Create issue in project tracking system
- **Monitoring**: Check Sentry/Grafana alerts
- **Logs**: Fly.io dashboard → Applications → Logs

---

## ✅ Success!

You now have:
- ✅ Local development environment running
- ✅ Production access credentials
- ✅ Automated deployment pipeline
- ✅ Monitoring and health checks
- ✅ Complete documentation

**Ready for development!** 🚀

Next steps:
1. Make your first code change
2. Run tests locally
3. Push to main branch
4. Watch automatic deployment
5. Monitor production health

Happy coding! 🎉
# Mouth - Nuzantara Frontend

> **The face of Nuzantara** - A Next.js 16 + React 19 frontend for the Nuzantara AI ecosystem

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Next.js](https://img.shields.io/badge/Next.js-16.1.1-black)
![React](https://img.shields.io/badge/React-19.2.1-blue)
![Deployment](https://img.shields.io/badge/deployment-vercel-black)

**Live:** [www.balizero.com](https://www.balizero.com)

---

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Deploy to Vercel
git push origin main  # Auto-deploys via GitHub integration
```

**Default URLs:**

- Development: http://localhost:3000
- Production: https://www.balizero.com

---

## 📚 Documentation Hub

### Essential Guides

| Guide                                                            | Purpose                     | Time     |
| ---------------------------------------------------------------- | --------------------------- | -------- |
| **[⚡ Quick Article Publishing](./QUICK_ARTICLE_PUBLISHING.md)** | Publish news articles fast  | 5-10 min |
| [📖 Complete Documentation](./DOCUMENTATION.md)                  | Full technical reference    | 30+ min  |
| [🧪 Quick Test Guide](./QUICK_TEST_GUIDE.md)                     | Run tests and verify builds | 5 min    |

### Architecture & Design

- [Blog Layout Guide](../../docs/BLOG_LAYOUT_GUIDE.md) - Homepage and article layouts
- [Development Guidelines](../../docs/DEVELOPMENT_GUIDELINES.md) - Coding standards
- [Frontend Performance](../../docs/FRONTEND_PERFORMANCE_GUIDE.md) - Optimization techniques
- [Image Optimization](../../docs/IMAGE_OPTIMIZATION_GUIDE.md) - Image best practices

### Workflows

- **Publishing Articles:** [QUICK_ARTICLE_PUBLISHING.md](./QUICK_ARTICLE_PUBLISHING.md) ⚡
- **Testing:** [QUICK_TEST_GUIDE.md](./QUICK_TEST_GUIDE.md)
- **Deployment:** See [DOCUMENTATION.md § 14](./DOCUMENTATION.md#14-deployment)

---

## 🏗️ What is Mouth?

Mouth is the **customer-facing frontend** of the Nuzantara AI ecosystem, serving:

### Core Features

1. **🤖 Zantara AI Chat**
   - Conversational RAG assistant
   - Agentic reasoning with tool use
   - Streaming responses with SSE

2. **💼 CRM Workspace**
   - Client management
   - Case tracking
   - Team collaboration
   - Email integration (Zoho)

3. **📝 Blog System (100+ Articles)**
   - Immigration (26 articles)
   - Business (27 articles)
   - Tax (15 articles)
   - Property (12 articles)
   - Lifestyle (14 articles)
   - Digital Nomad (5 articles)

4. **👥 Client Portal**
   - Self-service document access
   - Case status tracking
   - Secure messaging

5. **📱 Omnichannel**
   - WhatsApp integration
   - Telegram integration
   - Instagram integration
   - Twitter/X integration

---

## 📂 Project Structure

```
apps/mouth/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── (blog)/              # Blog routes
│   │   ├── (workspace)/         # Protected workspace
│   │   └── api/                 # API routes
│   ├── components/              # React components
│   ├── content/                 # MDX articles
│   │   └── articles/
│   │       ├── business/
│   │       ├── immigration/
│   │       ├── tax/
│   │       ├── property/
│   │       ├── lifestyle/
│   │       └── digital-nomad/
│   ├── hooks/                   # Custom hooks
│   ├── lib/                     # Utilities & APIs
│   └── types/                   # TypeScript types
├── public/
│   └── static/
│       └── news/                # Blog images (MUST be here)
├── DOCUMENTATION.md             # Complete technical docs
├── QUICK_ARTICLE_PUBLISHING.md # ⚡ Fast publishing guide
├── QUICK_TEST_GUIDE.md         # Testing guide
├── package.json
└── next.config.ts
```

---

## 🔧 Tech Stack

| Layer      | Technology          | Version      |
| ---------- | ------------------- | ------------ |
| Framework  | Next.js             | 16.1.1       |
| Runtime    | React               | 19.2.1       |
| Language   | TypeScript          | 5.x          |
| Styling    | TailwindCSS         | 4.x          |
| Animations | Framer Motion       | 12.x         |
| AI SDK     | Vercel AI SDK       | 6.x          |
| MDX        | next-mdx-remote     | 5.x          |
| Testing    | Vitest + Playwright | Latest       |
| Deployment | Vercel              | Edge Runtime |

---

## 🔌 Integration Points

### Backend (Python FastAPI)

- **URL:** https://nuzantara-rag.fly.dev
- **Purpose:** Agentic RAG pipeline
- **Connection:** HTTP + WebSocket
- **Docs:** See [backend-rag README](../backend-rag/README.md)

### External Services

- **Sentry:** Error tracking & performance monitoring ([Setup Guide](./SENTRY_SETUP.md))
- **Zoho:** Email & CRM integration
- **Pollinations AI:** Image generation
- **Qdrant:** Vector database (via backend)
- **PostgreSQL:** Relational database (via backend)

---

## ⚡ Common Tasks

### Publishing a News Article

**Fastest workflow (5-10 min):**

1. Create article: `src/content/articles/business/article-slug.mdx`
2. Add image: `public/static/news/article-image.jpg`
3. Update homepage: `src/app/(blog)/news/page.tsx` (add to MOCK_ARTICLES)
4. Deploy:
   ```bash
   git add .
   git commit --no-verify -m "feat: add article"
   git push --no-verify origin main
   ```

**Full guide:** [QUICK_ARTICLE_PUBLISHING.md](./QUICK_ARTICLE_PUBLISHING.md)

---

### Running Tests

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Smoke tests
npm run test:smoke

# Coverage
npm run test:coverage
```

**Full guide:** [QUICK_TEST_GUIDE.md](./QUICK_TEST_GUIDE.md)

---

### Deploying

```bash
# Automatic (via GitHub)
git push origin main  # Vercel auto-deploys

# Manual
vercel deploy --prod

# Monitor
# https://vercel.com/dashboard
```

---

## 🐛 Troubleshooting

### Article not showing on homepage?

**Problem:** Created MDX file but article doesn't appear

**Solution:** Homepage uses hardcoded `MOCK_ARTICLES` array

```typescript
// src/app/(blog)/news/page.tsx
// Add to MOCK_ARTICLES array:
{
  id: '201',
  slug: 'your-article-slug',
  title: "Article Title",
  // ... other fields
}
```

**Full guide:** [QUICK_ARTICLE_PUBLISHING.md § Troubleshooting](./QUICK_ARTICLE_PUBLISHING.md#troubleshooting)

---

### Image not loading (404)?

**Problem:** Image shows broken icon

**Solution:** Image MUST be in `/public/static/news/`, not `/public/images/articles/`

```bash
# Correct
public/static/news/image.jpg  ✅

# Wrong
public/images/articles/image.jpg  ❌
```

---

### Git hooks blocking commit?

**Problem:** Pre-commit hooks fail on Prettier/linting

**Solution:** Use `--no-verify` flag (with caution)

```bash
git commit --no-verify -m "message"
git push --no-verify origin main
```

---

### More Issues?

See [DOCUMENTATION.md § 16 Troubleshooting](./DOCUMENTATION.md#16-troubleshooting)

---

## 📊 Performance Metrics

| Metric                         | Target  | Current |
| ------------------------------ | ------- | ------- |
| LCP (Largest Contentful Paint) | < 2.5s  | ~2.0s   |
| FID (First Input Delay)        | < 100ms | ~50ms   |
| CLS (Cumulative Layout Shift)  | < 0.1   | ~0.05   |
| TTI (Time to Interactive)      | < 3.8s  | ~3.0s   |

---

## 🔒 Security

- **Authentication:** JWT tokens + HttpOnly cookies
- **CSRF Protection:** Double-submit pattern
- **CORS:** Configured for backend-rag origin
- **Headers:** CSP, X-Frame-Options, etc.
- **Error Tracking:** Sentry for production monitoring ([Setup](./SENTRY_SETUP.md))

See [DOCUMENTATION.md § 12](./DOCUMENTATION.md#12-autenticazione-e-sicurezza)

---

## 📝 Contributing

### Code Style

```typescript
// Components: PascalCase.tsx
MessageBubble.tsx

// Hooks: camelCase.ts
useChat.ts

// Utils: camelCase.ts
utils.ts

// MDX: kebab-case.mdx
visa-guide-2025.mdx
```

### Before Committing

```bash
# Lint
npm run lint

# Format
npm run format

# Test
npm run test
```

---

## 🆘 Need Help?

| Question                           | Resource                                                             |
| ---------------------------------- | -------------------------------------------------------------------- |
| How do I publish articles quickly? | [QUICK_ARTICLE_PUBLISHING.md](./QUICK_ARTICLE_PUBLISHING.md)         |
| How do I run tests?                | [QUICK_TEST_GUIDE.md](./QUICK_TEST_GUIDE.md)                         |
| How do I setup error tracking?     | [SENTRY_SETUP.md](./SENTRY_SETUP.md)                                 |
| Where is the full documentation?   | [DOCUMENTATION.md](./DOCUMENTATION.md)                               |
| How do I deploy?                   | [DOCUMENTATION.md § 14](./DOCUMENTATION.md#14-deployment)            |
| What's the architecture?           | [DOCUMENTATION.md § 2](./DOCUMENTATION.md#2-architettura-di-sistema) |
| How does the blog work?            | [DOCUMENTATION.md § 9](./DOCUMENTATION.md#9-sistema-blog-mdx)        |

---

## 📞 Contact

- **Project:** Nuzantara AI Ecosystem
- **Frontend:** Mouth (this app)
- **Backend:** [backend-rag](../backend-rag/)
- **Deployment:** Vercel (mouth), Fly.io (backend-rag)

---

## 📜 License

Proprietary - Nuzantara Project

---

**Last Updated:** February 4, 2026

## 🐛 Error Tracking & Monitoring

Sentry is fully configured for production error tracking:

- ✅ Client-side error capture
- ✅ Server-side error capture
- ✅ Session replay (10% sample rate)
- ✅ Performance monitoring (10% in production)
- ✅ Source map support for readable stack traces

**Quick Setup:**

```bash
# 1. Create Sentry project at https://sentry.io
# 2. Add credentials to .env.local
# 3. Add secrets to Fly.io
# 4. Deploy

# See full guide:
cat SENTRY_SETUP.md
```

**Documentation:**

- [Quick Setup Guide](./SENTRY_SETUP.md) - 5 min setup
- [Full Configuration](../../docs/SENTRY_CONFIGURATION.md) - Complete reference
- [Usage Examples](../../docs/SENTRY_USAGE_EXAMPLES.md) - Best practices
- [Integration Examples](./SENTRY_INTEGRATION_EXAMPLES.ts) - Code patterns

**Verification:**

```bash
./verify-sentry.sh
```

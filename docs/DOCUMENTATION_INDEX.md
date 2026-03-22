# 📚 NUZANTARA DOCUMENTATION INDEX

**Master Index** | Last Updated: 2026-02-08  
**Total Active Documents**: 75 in `docs/` root + 19 in `docs/ai/` + 18 in `docs/operations/`

---

## 🎯 START HERE

New to the project? Read these in order:

1. **[AI_ONBOARDING.md](AI_ONBOARDING.md)** - Quick-start for AI assistants
2. **[AI_HANDOVER_PROTOCOL.md](ai/AI_HANDOVER_PROTOCOL.md)** - System prompt / project brain
3. **[SYSTEM_MAP_4D.md](SYSTEM_MAP_4D.md)** - Architecture overview
4. **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - This file

---

## 📂 DOCUMENTATION STRUCTURE

```
docs/
├── 📄 DOCUMENTATION_INDEX.md       # This master index
├── 📄 AI_ONBOARDING.md             # Quick-start guide
├── 📄 SYSTEM_MAP_4D.md             # 4D architecture map
├── 📄 PROJECT_STRUCTURE.md         # Monorepo structure
├── 📄 DEVELOPMENT_GUIDELINES.md    # Coding standards
│
├── 📁 ai/                          # AI/Session documentation
│   ├── AI_HANDOVER_PROTOCOL.md     # System prompt
│   └── ... (19 files)
│
├── 📁 operations/                  # Operations & runbooks
│   ├── OBSERVABILITY_GUIDE.md      # Monitoring stack
│   ├── DEPLOY_CHECKLIST.md         # Deploy procedures
│   └── ... (18 files)
│
├── 📁 architecture/                # Architecture decisions
│   ├── OMNICHANNEL_STRATEGY.md
│   └── ... (3 files)
│
├── 📁 features/                    # Feature documentation
│   └── KBLI_NOTEBOOK_EXPLORER.md
│
├── 📁 security/                    # Security docs
│   └── ... (3 files)
│
├── 📁 client_briefs/               # Client work
│   └── ...
│
└── 📁 archive/                     # 📦 ARCHIVED DOCUMENTS
    ├── MANIFEST.md                 # Archive index
    ├── 2026-02-07_session/         # Session reports
    ├── transient/                  # Old docs by feature
    ├── duplicates/                 # Duplicated files
    └── deprecated/                 # Obsolete docs
```

---

## 🚀 QUICK REFERENCE BY TOPIC

### 🔧 Development

| Topic                   | Document                                                          |
| ----------------------- | ----------------------------------------------------------------- |
| **Onboarding**          | [AI_ONBOARDING.md](AI_ONBOARDING.md)                              |
| **Code Standards**      | [DEVELOPMENT_GUIDELINES.md](DEVELOPMENT_GUIDELINES.md)            |
| **Project Structure**   | [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)                      |
| **System Overview**     | [SYSTEM_MAP_4D.md](SYSTEM_MAP_4D.md)                              |
| **Living Architecture** | [LIVING_ARCHITECTURE.md](LIVING_ARCHITECTURE.md) (auto-generated) |

### 🗄️ Database

| Topic                  | Document                                                   |
| ---------------------- | ---------------------------------------------------------- |
| **DB Architecture V2** | [DATABASE_ARCHITECTURE_V2.md](DATABASE_ARCHITECTURE_V2.md) |
| **DB Guide**           | [DATABASE_V2_GUIDE.md](DATABASE_V2_GUIDE.md)               |

### 👥 CRM System

| Topic                 | Document                                                                     |
| --------------------- | ---------------------------------------------------------------------------- |
| **CRM Complete**      | [CRM_COMPLETE.md](CRM_COMPLETE.md)                                           |
| **CRM Vision**        | [CRM_VISION_AND_ROADMAP.md](CRM_VISION_AND_ROADMAP.md)                       |
| **Drive Integration** | [CRM_GOOGLE_DRIVE_INTEGRATION_PLAN.md](CRM_GOOGLE_DRIVE_INTEGRATION_PLAN.md) |

### 🔍 Operations

| Topic          | Document                                                               |
| -------------- | ---------------------------------------------------------------------- |
| **Monitoring** | [operations/OBSERVABILITY_GUIDE.md](operations/OBSERVABILITY_GUIDE.md) |
| **Deploy**     | [operations/DEPLOY_CHECKLIST.md](operations/DEPLOY_CHECKLIST.md)       |
| **Testing**    | [operations/LOCAL_TESTING_GUIDE.md](operations/LOCAL_TESTING_GUIDE.md) |

### 🤖 AI/ML

| Topic                  | Document                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| **System Prompt**      | [ai/AI_HANDOVER_PROTOCOL.md](ai/AI_HANDOVER_PROTOCOL.md)                                         |
| **KG Assessment**      | [KG_VALUE_ASSESSMENT_2026_01_18.md](KG_VALUE_ASSESSMENT_2026_01_18.md)                           |
| **Architecture Brief** | [../BRIEF_KB_ARCHITECTURE_REASONING.md](../BRIEF_KB_ARCHITECTURE_REASONING.md)                   |
| **KG Strategy**        | [architecture/SUPER_KNOWLEDGE_GRAPH_STRATEGY.md](architecture/SUPER_KNOWLEDGE_GRAPH_STRATEGY.md) |

### ✨ Features

| Topic                | Document                                                                 |
| -------------------- | ------------------------------------------------------------------------ |
| **KBLI Explorer**    | [features/KBLI_NOTEBOOK_EXPLORER.md](features/KBLI_NOTEBOOK_EXPLORER.md) |
| **Article Composer** | [ARTICLE_COMPOSER_API.md](ARTICLE_COMPOSER_API.md)                       |
| **Intel Scraper**    | [INTEL_ROUTER_API.md](INTEL_ROUTER_API.md)                               |

### 🔐 Security & CDN

| Topic                          | Document                                                                                    |
| ------------------------------ | ------------------------------------------------------------------------------------------- |
| **CloudFlare CDN Plan**        | [CLOUDFLARE_IMPLEMENTATION_PLAN.md](CLOUDFLARE_IMPLEMENTATION_PLAN.md) - Complete CDN setup |
| **CloudFlare CDN Quick Start** | [CLOUDFLARE_CDN_SETUP.md](CLOUDFLARE_CDN_SETUP.md)                                          |
| **CloudFlare DNS Setup**       | [CLOUDFLARE_DNS_SETUP.md](CLOUDFLARE_DNS_SETUP.md)                                          |
| **CloudFlare DNS Status**      | [CLOUDFLARE_DNS_SETUP_COMPLETE.md](CLOUDFLARE_DNS_SETUP_COMPLETE.md)                        |
| **Public Endpoints Audit**     | [security/PUBLIC_ENDPOINTS_SECURITY_AUDIT.md](security/PUBLIC_ENDPOINTS_SECURITY_AUDIT.md)  |

---

## 📊 SYSTEM STATISTICS

From [SYSTEM_MAP_4D.md](SYSTEM_MAP_4D.md) (auto-updated):

| Metric             | Value                      |
| ------------------ | -------------------------- |
| Router Files       | 68                         |
| Services           | 228 Python files           |
| Test Files         | 477                        |
| API Endpoints      | 406                        |
| Test Cases         | ~5,308+                    |
| Database Tables    | 24                         |
| Qdrant Collections | 9 (66,595+ documents)      |
| Knowledge Graph    | 34,606 nodes, 30,628 edges |

---

## 📦 ARCHIVE

Old session reports, transient documentation, and superseded files are archived in:

**`docs/archive/MANIFEST.md`**

### What's in the Archive?

- Session reports (2026-02-07 session)
- Deploy reports (multiple)
- Monitoring reports
- Type safety migration docs
- Article Composer (16 files)
- Intel Scraper (14 files)
- Telegram setup (10 files)
- News Room docs (20 files)
- Old CRM docs (v2.0)

**Total Archived**: 110+ files

---

## 🔄 DOCUMENTATION MAINTENANCE

### Auto-Generated

These files are automatically updated:

| File                     | Generated By | Frequency     |
| ------------------------ | ------------ | ------------- |
| `LIVING_ARCHITECTURE.md` | Scribe tool  | On-demand     |
| `SYSTEM_MAP_4D.md`       | Scribe tool  | Manual update |

### Manual Updates Required

| File                      | When to Update                           |
| ------------------------- | ---------------------------------------- |
| `AI_ONBOARDING.md`        | New critical fixes, architecture changes |
| `AI_HANDOVER_PROTOCOL.md` | System stats change                      |
| `DOCUMENTATION_INDEX.md`  | New docs added, structure changes        |
| `CRM_COMPLETE.md`         | CRM features modified                    |

---

## 🆘 NEED HELP?

### For AI Assistants

1. Read [AI_ONBOARDING.md](AI_ONBOARDING.md)
2. Check [AI_HANDOVER_PROTOCOL.md](ai/AI_HANDOVER_PROTOCOL.md)
3. Search this index for relevant topic

### For Developers

1. Check [DEVELOPMENT_GUIDELINES.md](DEVELOPMENT_GUIDELINES.md)
2. See [operations/OBSERVABILITY_GUIDE.md](operations/OBSERVABILITY_GUIDE.md) for debugging
3. See [operations/DEPLOY_CHECKLIST.md](operations/DEPLOY_CHECKLIST.md) for deploy

### Looking for Old Docs?

Check the archive: `docs/archive/MANIFEST.md`

---

**Documentation Maintained By**: AI Dev Team  
**Last Consolidation**: 2026-02-07

---

_"Documentation is a conversation across time"_

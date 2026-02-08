# 📦 NUZANTARA DOCUMENTATION ARCHIVE

**Archivio creato:** 2026-02-07  
**Operazione:** Pulizia e consolidamento documentazione  
**Documenti archiviati:** 109

---

## 🗂️ STRUTTURA ARCHIVIO

```
docs/archive/
├── MANIFEST.md                          # Questo file
├── 2026-02-07_session/                  # Report sessione corrente
│   ├── cleanup_streaming/               # 4 file
│   ├── deploy_reports/                  # 13 file
│   ├── monitoring_reports/              # 6 file
│   ├── type_safety/                     # 6 file
│   └── DASHBOARD_FIXES_2026_01_21.md
├── deprecated/                          # Documenti obsoleti
│   └── 4 file
├── duplicates/                          # Documenti duplicati
│   └── 3 file
└── transient/                           # Documenti transient
    ├── article_composer/                # 16 file
    ├── intel_scraper/                   # 14 file
    ├── news_room/                       # 20 file
    ├── session_reports/                 # 3 file
    ├── telegram/                        # 10 file
    └── 7 file root
```

---

## 📋 INDICE PER CATEGORIA

### 1. SESSIONE 2026-02-07 (26 file)

Report di sessione AI organizzati per tema.

| Sottocartella | File | Descrizione |
|--------------|------|-------------|
| `cleanup_streaming/` | 4 | Cleanup e consolidamento streaming |
| `deploy_reports/` | 13 | Report deploy multipli |
| `monitoring_reports/` | 6 | Setup e report monitoring |
| `type_safety/` | 6 | Migrazione type safety |

**File chiave mantenuti in docs/ principale:**
- `docs/operations/DEPLOY_CHECKLIST.md` ← Usare questo per deploy
- `docs/operations/OBSERVABILITY_GUIDE.md` ← Guida monitoring ufficiale

---

### 2. DEPRECATED (4 file)

Documenti obsoleti o sostituiti.

| File | Motivo |
|------|--------|
| `DOCUMENTATION_CHANGELOG.md` | Sostituito da nuovo sistema documentazione |
| `DOCUMENTATION_UPDATE_*.md` | Transient, aggiornamenti specifici |
| `WINDSURF_PHASE2_PATCH.md` | Specifico tool AI esterno |

---

### 3. DUPLICATES (3 file)

Documenti duplicati rispetto a docs/ai/ o altre locazioni.

| File | Duplicato di |
|------|-------------|
| `DEPLOY_STATUS.md` | docs/ai/DEPLOY_STATUS.md (spostato in session/) |
| `DEPLOY_COMPLETE.md` | docs/ai/DEPLOY_COMPLETED.md (spostato in session/) |
| `DEPLOYMENT_STATUS.md` | docs/DEPLOYMENT_STATUS.md |

---

### 4. TRANSIENT (70 file)

Documenti temporanei di sessioni passate.

#### 4.1 Article Composer (16 file)
Documentazione feature Article Composer - la maggior parte sono report intermedi.

**Mantenuti in docs/ principale:**
- `docs/ARTICLE_COMPOSER_API.md` ← API reference
- `docs/ARTICLE_COMPOSER_BEST_PRACTICES_2026.md` ← Best practices
- `docs/ARTICLE_COMPOSER_QUICK_START.md` ← Quick start

#### 4.2 Intel Scraper (14 file)
Documentazione Intel Scraper - cron, fix, configurazioni.

**Mantenuti in docs/ principale:**
- `docs/INTEL_ROUTER_API.md` ← API reference
- `docs/INTEL_DEPLOYMENT_GUIDE.md` ← Deployment
- `docs/INTEL_SCRAPER_ANALYSIS_REPORT.md` ← Analisi

#### 4.3 News Room (20 file)
Piani, analisi e report per la News Room.

**Nota:** Tutti i piani sono stati eseguiti. Per lo stato attuale vedere:
- `docs/operations/LOCAL_TESTING_GUIDE.md`
- `docs/operations/OBSERVABILITY_GUIDE.md`

#### 4.4 Session Reports (3 file)
Report specifici di sessione.

#### 4.5 Telegram (10 file)
Setup e fix Telegram Bot. La maggior parte sono stati di configurazione.

**Mantenuto in docs/ principale:**
- `docs/TELEGRAM_BOT_START_GUIDE.md` ← Guida avvio bot

#### 4.6 Root Transient (7 file)
| File | Categoria |
|------|-----------|
| `ANALISI_ARTICLE_COMPOSER.md` | Analisi |
| `CLEANUP_SUMMARY.md` | Transient |
| `SENTRY_*.txt` | Log non-markdown |
| `VERCEL_*.md` | Fix specifici Vercel |
| `WORKSPACE_CLEANUP_COMPLETE.md` | Transient |

---

## 🔍 RICERCA RAPIDA

### Se cerchi informazioni su...

| Argomento | Vai a |
|-----------|-------|
| **Deploy** | `docs/operations/DEPLOY_CHECKLIST.md` |
| **Monitoring** | `docs/operations/OBSERVABILITY_GUIDE.md` |
| **Architettura** | `docs/SYSTEM_MAP_4D.md` |
| **Database** | `docs/DATABASE_ARCHITECTURE_V2.md` |
| **Onboarding** | `docs/AI_ONBOARDING.md` |
| **API Article Composer** | `docs/ARTICLE_COMPOSER_API.md` |
| **API Intel** | `docs/INTEL_ROUTER_API.md` |
| **CRM** | `docs/CRM_SYSTEM.md` |
| **KBLI** | `docs/features/KBLI_NOTEBOOK_EXPLORER.md` |

---

## ⚠️ NOTE IMPORTANTI

### Documenti con "*_COMPLETE.md", "*_SUCCESS.md", "*_FINAL.md"
Questi sono stati di completamento temporanei. Lo stato attuale del sistema è documentato in:
- `docs/AI_ONBOARDING.md` (ultimo aggiornamento: 2026-02-07)
- `docs/SYSTEM_MAP_4D.md` (auto-generated: 2026-02-02)
- `docs/LIVING_ARCHITECTURE.md` (auto-generated)

### Documenti tool-specifici
File come `WINDSURF_*.md`, `VERCEL_*_FIX_*.md` sono relativi a problemi specifici risolti.

---

## 📊 STATISTICHE

| Categoria | Count | % Totale |
|-----------|-------|----------|
| Sessione 2026-02-07 | 26 | 23.9% |
| Transient | 70 | 64.2% |
| Duplicati | 3 | 2.8% |
| Deprecated | 4 | 3.7% |
| **TOTALE** | **109** | **100%** |

---

## 🔄 PROCESSO DI ARCHIVIAZIONE

### Criteri utilizzati:
1. **Duplicati** → Identici o con contenuto sovrapposto
2. **Transient** → Report di sessione, stati intermedi, fix specifici
3. **Deprecated** → Sostituiti da documentazione più recente
4. **Sessione** → Report AI raggruppati per data e tema

### Documenti mantenuti in docs/ principale:
- Documentazione architetturale stabile
- Guide operative attuali
- API reference
- Feature documentation
- Onboarding e handover protocols

---

**Ultimo aggiornamento:** 2026-02-07  
**Archiviato da:** AI Assistant Session  
**Stato:** ✅ Completo

---

## Aggiornamento 2026-02-07

### Documenti CRM Consolidati

| File Originale | Archiviato Come | Motivo |
|----------------|-----------------|--------|
| `docs/CRM_SYSTEM.md` | `transient/CRM_SYSTEM_v2.0.md` | Consolidato in `CRM_COMPLETE.md` |
| `docs/CRM_SYSTEM_DOCUMENTATION.md` | `transient/CRM_SYSTEM_DOCUMENTATION_v2.0.md` | Consolidato in `CRM_COMPLETE.md` |

### Nuovo Documento Unificato

**`docs/CRM_COMPLETE.md`** - Documentazione CRM consolidata v3.0

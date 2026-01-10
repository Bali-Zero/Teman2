# 🤖 AGENTIC TEST FORCE - Piano di Implementazione

**Data:** 2026-01-10  
**Autore:** Cascade AI  
**Target:** Nuzantara Backend RAG + Frontend

---

## 📊 ANALISI CODEBASE ATTUALE

### Test Esistenti
| Metrica | Valore |
|---------|--------|
| **File Test Totali** | 553 |
| **File Sorgente** | 705 |
| **Rapporto Test/Sorgente** | 78% |
| **Framework** | pytest + pytest-asyncio |
| **Conftest Files** | 7 |

### Struttura Test
```
tests/
├── api/           # 94 items - Test endpoint API
├── integration/   # 151 items - Test integrazione
├── unit/          # 303 items - Test unitari
├── services/      # 17 items - Test servizi
├── load/          # Load testing
└── performance/   # Performance testing
```

### Agenti Esistenti (Base per Test Force)
1. **TestGuardian** (`test_guardian.py`) - ✅ GIÀ ESISTENTE
   - Analizza coverage
   - Genera test con LLM
   - Self-healing (run → fail → fix → pass)
   
2. **ConversationTrainer** (`conversation_trainer.py`)
   - Pattern di apprendimento da conversazioni
   - Genera miglioramenti automatici

3. **BackendAgent** (`backend_agent.py`)
   - Self-healing del backend
   - Health monitoring

---

## 🏗️ ARCHITETTURA AGENTIC TEST FORCE

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENTIC TEST FORCE                       │
│                    (Orchestratore Centrale)                 │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  TestCreator  │    │ TestMaintainer│    │  TestCleaner  │
│   Agent       │    │    Agent      │    │    Agent      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   Genera test          Aggiorna test         Elimina test
   per nuovo code       esistenti             obsoleti/duplicati
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │   LLM Layer   │
                    │ (Qwen 7B o    │
                    │  Gemini API)  │
                    └───────────────┘
```

---

## 🧠 INTEGRAZIONE LLM LOCALE (Qwen 7B)

### Requisiti Hardware
| Risorsa | Disponibile | Richiesto Qwen 7B | Note |
|---------|-------------|-------------------|------|
| **RAM** | 16GB | ~8GB | ✅ Fattibile |
| **Chip** | M4 | ARM64 | ✅ Ottimizzato |
| **VRAM** | Unified | ~6GB | ✅ Metal GPU |

### Configurazione Consigliata
```bash
# Installa Ollama (ottimizzato per Apple Silicon)
brew install ollama

# Scarica Qwen 7B (quantizzato Q4 per risparmiare RAM)
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# Verifica
ollama run qwen2.5-coder:7b-instruct-q4_K_M "Hello"
```

### Modelli Alternativi Leggeri
| Modello | RAM | Qualità Code | Velocità |
|---------|-----|--------------|----------|
| `qwen2.5-coder:7b-instruct-q4_K_M` | ~5GB | ⭐⭐⭐⭐ | Veloce |
| `codellama:7b-instruct-q4_K_M` | ~5GB | ⭐⭐⭐ | Veloce |
| `deepseek-coder:6.7b-instruct-q4_K_M` | ~4GB | ⭐⭐⭐⭐ | Veloce |

### Fallback Strategy
```python
# Priority Chain
1. Qwen 7B Local (Ollama) → Gratuito, veloce, privato
2. Gemini API → Se locale non disponibile
3. Mock Mode → Per testing senza LLM
```

---

## 🎯 COMPONENTI DA IMPLEMENTARE

### 1. TestCreatorAgent (Nuovo)
**Responsabilità:** Generare test per nuovo codice

```python
class TestCreatorAgent:
    """
    Monitora git diff per nuovo codice e genera test automaticamente.
    
    Workflow:
    1. Rileva nuovi file/funzioni (git diff)
    2. Analizza contesto (imports, dipendenze)
    3. Genera test con LLM
    4. Valida sintassi
    5. Esegue test
    6. Se fallisce → auto-fix → retry
    7. Commit su branch dedicato
    """
    
    def watch_for_changes(self): ...
    def analyze_new_code(self, file_path): ...
    def generate_tests(self, context): ...
    def validate_and_run(self, test_code): ...
    def self_heal(self, error): ...
```

### 2. TestMaintainerAgent (Nuovo)
**Responsabilità:** Aggiornare test esistenti quando il codice cambia

```python
class TestMaintainerAgent:
    """
    Mantiene i test allineati con le modifiche al codice.
    
    Workflow:
    1. Rileva modifiche a file sorgente
    2. Trova test correlati
    3. Analizza se test sono ancora validi
    4. Se breaking → genera fix con LLM
    5. Valida e commit
    """
    
    def find_related_tests(self, source_file): ...
    def check_test_validity(self, test_file): ...
    def update_test(self, test_file, changes): ...
```

### 3. TestCleanerAgent (Nuovo)
**Responsabilità:** Eliminare test obsoleti, duplicati, legacy

```python
class TestCleanerAgent:
    """
    Pulisce la test suite da cruft accumulato.
    
    Workflow:
    1. Scansiona tutti i test
    2. Rileva:
       - Test per codice rimosso
       - Test duplicati (semanticamente simili)
       - Test mai eseguiti
       - Test sempre verdi (mock tutto)
    3. Propone eliminazione
    4. Archivia in backup prima di eliminare
    """
    
    def scan_all_tests(self): ...
    def detect_orphaned_tests(self): ...
    def detect_duplicates(self): ...
    def detect_useless_tests(self): ...
    def archive_and_remove(self, tests): ...
```

### 4. TestForceOrchestrator (Centrale)
**Responsabilità:** Coordina tutti gli agenti

```python
class TestForceOrchestrator:
    """
    Orchestratore centrale della Test Force.
    
    Modes:
    - WATCH: Monitoraggio continuo (daemon)
    - SCAN: Scansione completa una tantum
    - FIX: Fix automatico problemi rilevati
    - REPORT: Solo reportistica
    """
    
    def __init__(self, llm_provider="local"):
        self.creator = TestCreatorAgent(llm_provider)
        self.maintainer = TestMaintainerAgent(llm_provider)
        self.cleaner = TestCleanerAgent(llm_provider)
        self.guardian = TestGuardian(llm_provider)  # Esistente
    
    async def run_full_scan(self): ...
    async def watch_mode(self): ...
    async def generate_report(self): ...
```

---

## 📋 PIANO IMPLEMENTAZIONE (FASI)

### Fase 1: Setup LLM Locale (1-2 ore)
- [ ] Installare Ollama
- [ ] Scaricare Qwen 7B quantizzato
- [ ] Testare integrazione con TestGuardian esistente
- [ ] Creare wrapper unificato per LLM

### Fase 2: TestCreatorAgent (4-6 ore)
- [ ] Implementare git diff watcher
- [ ] Code context analyzer (usa esistente `CodeContextAnalyzer`)
- [ ] Prompt engineering per generazione test
- [ ] Self-healing loop
- [ ] Unit tests per il creator stesso

### Fase 3: TestMaintainerAgent (3-4 ore)
- [ ] Mapping source → test files
- [ ] Diff analyzer per modifiche
- [ ] Test validity checker
- [ ] Update generator

### Fase 4: TestCleanerAgent (3-4 ore)
- [ ] Orphan detector
- [ ] Semantic duplicate finder (embedding-based)
- [ ] Archive system
- [ ] Cleanup executor

### Fase 5: Orchestrator & CLI (2-3 ore)
- [ ] Orchestratore centrale
- [ ] CLI interface
- [ ] Daemon mode per watch continuo
- [ ] Report generator (HTML/MD)

### Fase 6: Integrazione & Testing (2-3 ore)
- [ ] Test end-to-end
- [ ] Performance tuning
- [ ] Documentazione
- [ ] Pre-commit hook (opzionale)

---

## 🔧 STRUTTURA FILE PROPOSTA

```
backend/agents/
├── agents/
│   ├── test_guardian.py          # ✅ Esistente
│   ├── test_creator.py           # 🆕 Nuovo
│   ├── test_maintainer.py        # 🆕 Nuovo
│   ├── test_cleaner.py           # 🆕 Nuovo
│   └── test_force_orchestrator.py # 🆕 Nuovo
├── services/
│   ├── llm_adapter.py            # 🆕 Wrapper unificato LLM
│   ├── code_analyzer.py          # 🆕 AST analyzer potenziato
│   └── test_mapper.py            # 🆕 Source ↔ Test mapping
└── __init__.py
```

---

## 💻 ESEMPIO USO FINALE

```bash
# Scansione completa con report
python -m backend.agents.test_force --mode=scan --report=html

# Watch mode (daemon)
python -m backend.agents.test_force --mode=watch --llm=local

# Fix automatico coverage gaps
python -m backend.agents.test_force --mode=fix --target=coverage

# Cleanup test obsoleti
python -m backend.agents.test_force --mode=clean --dry-run

# Genera test per file specifico
python -m backend.agents.test_force --mode=create --file=backend/services/new_service.py
```

---

## ⚡ QUICK START (Primo Passo)

```bash
# 1. Installa Ollama
brew install ollama

# 2. Scarica modello leggero
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# 3. Testa TestGuardian esistente con LLM locale
cd apps/backend-rag
python -m backend.agents.agents.test_guardian --mode=auto --provider=local
```

---

## 📊 METRICHE DI SUCCESSO

| Metrica | Target |
|---------|--------|
| Coverage automatica | > 90% |
| Test obsoleti rimossi | < 5% del totale |
| Tempo generazione test | < 30s per file |
| Self-healing success rate | > 80% |
| False positives (test inutili) | < 10% |

---

## 🚀 PROSSIMI PASSI IMMEDIATI

1. **Conferma modello LLM** - Qwen 7B Q4 ok per M4 16GB
2. **Inizia Fase 1** - Setup Ollama + test integrazione
3. **Estendi TestGuardian** - Base per altri agenti

---

**Vuoi procedere con l'implementazione?**

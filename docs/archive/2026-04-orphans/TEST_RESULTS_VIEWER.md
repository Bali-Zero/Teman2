# Test Results Viewer

## 📊 Visualizzazione Risultati Test

### Quick View

```bash
./scripts/view_test_results.sh
```

**Mostra:**

- ✅ Ultimi risultati test
- ✅ Log files con timestamp
- ✅ Coverage reports disponibili
- ✅ Summary pass/fail
- ✅ Comandi utili

### Log Files

**Agent Test Log:**

```bash
tail -f logs/agent_test.log
```

**Ollama Status Log:**

```bash
tail -f logs/ollama_cron.log
```

### HTML Reports

**Genera report completo:**

```bash
./scripts/generate_test_report.sh
```

**Cosa genera:**

- 📄 Test report HTML (self-contained)
- 📈 Coverage report HTML
- 📊 Statistiche dettagliate

**Apri report:**

```bash
# macOS
open reports/test-report-*.html

# Linux
xdg-open reports/test-report-*.html
```

## 📋 Struttura Logs

```
logs/
├── agent_test.log          # Risultati test agenti
├── ollama_cron.log         # Status Ollama
├── coverage_test.log       # Coverage test results
└── ...

reports/
├── test-report-*.html      # Report HTML test
└── coverage-*/             # Coverage HTML reports
```

## 🔍 Cosa Vedere nei Log

### Agent Test Log (`logs/agent_test.log`)

**Successo:**

```
✅ test_reasoning PASSED
✅ test_agentic_tools_comprehensive PASSED
✅ All agent tests passed!
```

**Fallimento:**

```
❌ test_reasoning FAILED
❌ Failed tests: test_reasoning
```

**Con Ollama:**

```
✅ Ollama is running
✅ Using real Qwen LLM for tests
```

**Con Mock:**

```
⚠️  Ollama not available - using mocks
```

### Ollama Cron Log (`logs/ollama_cron.log`)

**Avvio:**

```
🚀 Starting Ollama for agent tests...
✅ Ollama started (PID: 12345)
```

**Stop:**

```
🛑 Stopping Ollama after test window...
✅ Ollama stopped
```

## 📈 Coverage Reports

**Genera coverage:**

```bash
./scripts/run_coverage_test.sh
```

**Report HTML:**

- `htmlcov/index.html` - Coverage overview
- `htmlcov/llm/` - LLM coverage
- `htmlcov/agentic/` - Agentic coverage

**Apri:**

```bash
open htmlcov/index.html
```

## 🎯 Esempio Output

```bash
$ ./scripts/view_test_results.sh

📊 Test Results Viewer
================================

📝 Log Files:

✅ Agent Test Log:
   Location: /path/to/logs/agent_test.log
   Last modified: 2026-01-18 03:30:15

   Last 20 lines:
   ──────────────────────────────────────
   [2026-01-18 03:30:15] ✅ test_reasoning PASSED
   [2026-01-18 03:30:16] ✅ test_agentic_tools_comprehensive PASSED
   [2026-01-18 03:30:20] ✅ All agent tests passed!
   ──────────────────────────────────────

📈 Coverage Reports:

✅ Coverage reports available:
   Location: /path/to/htmlcov

   Open in browser:
   open htmlcov/index.html

📋 Quick Summary:

   Last run summary:
     Passed: 10
     Failed: 0
     ✅ All agent tests passed!
```

## 🔧 Integrazione

I risultati sono automaticamente:

- ✅ Salvati in `logs/agent_test.log`
- ✅ Accessibili via `view_test_results.sh`
- ✅ Generabili come HTML con `generate_test_report.sh`
- ✅ Visibili dopo ogni esecuzione automatica (cron)

## 💡 Tips

**Monitor real-time:**

```bash
tail -f logs/agent_test.log
```

**Cerca errori:**

```bash
grep -i "fail\|error" logs/agent_test.log
```

**Ultimo run:**

```bash
tail -50 logs/agent_test.log | grep -A 10 "Summary"
```

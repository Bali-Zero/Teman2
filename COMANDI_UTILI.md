# 🎯 COMANDI UTILI - Test Force

## 🚀 ESECUZIONE

### **Test Completo (Default):**

```bash
./scripts/auto_test_force.sh
```

### **Solo Coverage Analysis:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=coverage --provider=local
```

### **Solo Test Generation:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=create --provider=local --max-files=10
```

### **Solo Test Maintenance:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=maintain --provider=local
```

### **Solo Test Cleanup (DRY RUN - sicuro):**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=clean --provider=local
```

### **Test Cleanup REALE (cancella file):**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=clean --provider=local --no-dry-run
```

---

## 📊 MONITORAGGIO

### **Log in tempo reale:**

```bash
tail -f logs/test_force.log
```

### **Ultimi 100 log:**

```bash
tail -100 logs/test_force.log
```

### **Cerca Qwen usage:**

```bash
grep -i "qwen\|ollama\|circuit" logs/test_force.log | tail -20
```

### **Vedi solo errori:**

```bash
grep -i "error\|failed\|❌" logs/test_force.log | tail -20
```

---

## 🔧 OPZIONI AVANZATE

### **Parallel Execution (default):**

```bash
# Parallel attivo (default)
python3 scripts/run_test_force.py --mode=scan --provider=local

# Disabilita parallel
python3 scripts/run_test_force.py --mode=scan --provider=local --no-parallel

# Max concurrent agents
python3 scripts/run_test_force.py --mode=scan --provider=local --max-concurrent=5
```

### **Skip agenti specifici:**

```bash
# Solo Guardian + Creator
python3 scripts/run_test_force.py --mode=scan --provider=local --no-maintainer --no-cleaner

# Solo Cleaner
python3 scripts/run_test_force.py --mode=clean --provider=local
```

### **Max files da processare:**

```bash
python3 scripts/run_test_force.py --mode=create --provider=local --max-files=5
```

---

## 🧹 CLEANUP

### **Vedi cosa verrebbe cancellato (DRY RUN):**

```bash
python3 scripts/run_test_force.py --mode=clean --provider=local
```

### **Cancella realmente (ATTENZIONE!):**

```bash
python3 scripts/run_test_force.py --mode=clean --provider=local --no-dry-run
```

### **Cleanup aggressivo:**

```bash
python3 scripts/run_test_force.py --mode=clean --provider=local --aggressive --no-dry-run
```

---

## 🔍 VERIFICA QWEN

### **Test Qwen direttamente:**

```bash
cd apps/backend-rag
python3 -c "
import sys; sys.path.insert(0, 'backend')
from backend.agents.services.llm_adapter import get_llm_adapter, LLMProvider, LLMRequest
import asyncio

async def test():
    adapter = get_llm_adapter()
    request = LLMRequest(
        prompt='Generate a pytest test for a function that adds two numbers.',
        max_tokens=200,
        provider=LLMProvider.OLLAMA
    )
    response = await adapter.generate(request)
    print(f'Provider: {response.provider.value}')
    print(f'Response: {response.text[:300]}')
    await adapter.close()

asyncio.run(test())
"
```

### **Verifica Circuit Breaker:**

```bash
cd apps/backend-rag
python3 -c "
import sys; sys.path.insert(0, 'backend')
from backend.agents.services.llm_adapter import get_llm_adapter
import asyncio

async def check():
    adapter = get_llm_adapter()
    metrics = adapter.get_metrics()
    print('Circuit Breaker State:', metrics['circuit_breaker_state'])
    print('Success Rate:', f\"{metrics['success_rate']:.1f}%\")
    print('Total Requests:', metrics['total_requests'])
    await adapter.close()

asyncio.run(check())
"
```

---

## 📅 CRON

### **Vedi cron jobs:**

```bash
crontab -l | grep test_force
```

### **Modifica cron:**

```bash
crontab -e
```

### **Riconfigura cron:**

```bash
./scripts/setup_all_automation.sh
```

---

## 🎯 ESEMPI PRATICI

### **1. Genera test per 5 file nuovi:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=create --provider=local --max-files=5
```

### **2. Analizza coverage e mostra gaps:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=coverage --provider=local
```

### **3. Vedi cosa pulirebbe (sicuro):**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py --mode=clean --provider=local | grep -E "orphans|duplicates|useless"
```

### **4. Test completo con report:**

```bash
cd apps/backend-rag
python3 scripts/run_test_force.py \
    --mode=scan \
    --provider=local \
    --report=markdown \
    --output=test_force_report.md
```

---

## ⚠️ NOTE IMPORTANTI

1. **DRY RUN è default** - Nessun file viene cancellato senza `--no-dry-run`
2. **Parallel è default** - Usa `--no-parallel` per disabilitare
3. **Qwen è sempre usato** - `--provider=local` significa Qwen
4. **Cron esegue alle 2:15 AM** - Automatico ogni notte

# Agent Test with Ollama Qwen Local LLM

## Overview

Gli Agent Tests ora supportano **Ollama Qwen locale** per test reali invece di solo mock.

## Setup

### Automatic Setup (Recommended)

Il sistema **avvia automaticamente Ollama** se non è già running:

```bash
# Nessun setup necessario! Il sistema gestisce tutto automaticamente
./scripts/auto_agent_test.sh
```

Il script `ensure_ollama_ready.sh`:

- ✅ Verifica se Ollama è installato
- ✅ Avvia Ollama se non è running
- ✅ Scarica modello Qwen se non disponibile
- ✅ Verifica che tutto funzioni

### Manual Setup (Optional)

#### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

#### 2. Setup as Persistent Service (Optional)

```bash
# macOS/Linux - Ollama starts automatically on boot
./scripts/setup_ollama_service.sh
```

#### 3. Manual Start (if needed)

```bash
ollama serve
```

## Usage

### Automatic - Always Available

Il sistema **garantisce che Ollama sia sempre disponibile**:

```bash
./scripts/auto_agent_test.sh
```

**Cosa fa automaticamente:**

1. ✅ Verifica se Ollama è installato
2. ✅ Avvia Ollama se non è running
3. ✅ Scarica modello Qwen se non disponibile
4. ✅ Verifica che tutto funzioni
5. ✅ Usa Qwen reale per test LLM
6. ✅ Cleanup automatico dopo i test

**Risultato:**

- ✅ **Sempre disponibile** - Ollama viene avviato automaticamente
- ✅ Test realistici con Qwen reale
- ✅ Zero cost, no rate limits
- ✅ Nessun intervento manuale necessario

### Environment Variables

```bash
export OLLAMA_URL="http://localhost:11434"  # Default
export OLLAMA_MODEL="qwen2.5:latest"        # Default
export USE_OLLAMA_FOR_TESTS=true            # Force Ollama usage
```

## Intelligent Coverage Generation

Usa Qwen per generare test completi:

```bash
python3 scripts/intelligent_coverage_test.py
```

**Cosa fa:**

1. Analizza il codebase per trovare moduli senza test
2. Usa Qwen per generare test completi con alta coverage
3. Crea file di test automaticamente

**Esempio:**

```bash
$ python3 scripts/intelligent_coverage_test.py
✅ Ollama available with model: qwen2.5:latest
🔍 Analyzing codebase for coverage gaps...
📊 Found 15 modules without tests

[1/10] Generating test for services/rag/agentic/reasoning.py...
  ✅ Created: apps/backend-rag/backend/tests/unit/services/rag/agentic/test_reasoning.py
```

## Test Configuration

### Using Ollama in Tests

I test possono usare Ollama tramite fixture:

```python
import pytest
from backend.tests.unit.services.rag.agentic.conftest_ollama import ollama_provider

@pytest.mark.asyncio
async def test_with_ollama(ollama_provider):
    if ollama_provider:
        # Real Ollama call
        response = await ollama_provider.generate([...])
    else:
        # Fallback to mock
        ...
```

### Fixtures Available

- `ollama_available`: Check if Ollama is available
- `ollama_provider`: OllamaProvider instance (or None)
- `llm_gateway_with_ollama`: LLMGateway with Ollama if available
- `mock_llm_gateway`: Backward compatible alias

## Benefits

### Real LLM Testing

- ✅ Test comportamento reale degli agenti
- ✅ Verifica prompt engineering
- ✅ Test tool calling reale
- ✅ Validazione risposte LLM

### Cost Effective

- ✅ Zero cost (locale)
- ✅ No rate limits
- ✅ No API keys needed
- ✅ Privacy completa

### Intelligent Coverage

- ✅ Qwen genera test completi
- ✅ Alta coverage automatica
- ✅ Edge cases inclusi
- ✅ Best practices seguite

## Troubleshooting

### Ollama not detected

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check model
ollama list
```

### Model not found

```bash
# Pull Qwen model
ollama pull qwen2.5:latest

# Or use different model
export OLLAMA_MODEL="llama3.2:7b"
```

### Tests still using mocks

```bash
# Force Ollama usage
export USE_OLLAMA_FOR_TESTS=true
./scripts/auto_agent_test.sh
```

## Performance

**With Ollama (real LLM):**

- Slower but more realistic
- ~2-5s per test (depending on model size)
- Better coverage validation

**With Mocks:**

- Faster execution
- ~0.1s per test
- Less realistic but sufficient for unit tests

## Best Practices

1. **Development**: Use Ollama for realistic testing
2. **CI/CD**: Use mocks for speed (unless Ollama available)
3. **Coverage**: Run `intelligent_coverage_test.py` regularly
4. **Monitoring**: Check logs for Ollama availability

## Integration with Cron

Il cron job `auto_agent_test.sh` ora:

- Rileva automaticamente Ollama
- Usa Qwen se disponibile
- Fallback a mock se non disponibile
- Log completo in `logs/agent_test.log`
